"""
A demo adapter for the IRI Facility API that returns hardcoded data.
This is useful for testing and development of the API without needing to connect to real resources
"""
import base64
import datetime
import glob
import grp
import json
import os
import pathlib
import pwd
import random
import stat
import subprocess
import time
import uuid

import redis.asyncio as aioredis
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from redis.exceptions import WatchError

from .routers.account import facility_adapter as account_adapter
from .routers.account import models as account_models
from .routers.compute import facility_adapter as compute_adapter
from .routers.compute import models as compute_models
from .routers.facility import facility_adapter
from .routers.facility import models as facility_models
from .routers.filesystem import facility_adapter as filesystem_adapter
from .routers.filesystem import models as filesystem_models
from .routers.storage import facility_adapter as storage_adapter
from .routers.storage import models as storage_models
from .routers.status import facility_adapter as status_adapter
from .routers.status import models as status_models
from .routers.task import facility_adapter as task_adapter
from .routers.task import models as task_models
from .request_context import get_iri_facility_project
from .types.models import Capability
from .types.user import User
from .types.scalars import AllocationUnit
from .apilogger import get_stream_logger
from .config import LOG_LEVEL
from .idempotency import IdempotencyStore, LockState

logger = get_stream_logger(__name__, LOG_LEVEL)

DEMO_QUEUE_UPDATE_SECS = int(os.environ.get("DEMO_QUEUE_UPDATE_SECS", 5))


def paginate_list(items, offset: int | None, limit: int | None):
    """Return a sliced items using offset and limit."""
    if offset is not None and offset > 0:
        items = items[offset:]
    if limit is not None and limit >= 0:
        items = items[:limit]
    return items


_LOCK_TTL_SECONDS = int(os.environ.get("LOCK_TTL_SECONDS", 60))


class InMemoryIdempotencyStore(IdempotencyStore):
    """In-process dict store. NOT FOR PROD USE. Enable with:
      IRI_IDEMPOTENCY_STORE=app.demo_adapter.InMemoryIdempotencyStore
    """

    def __init__(self, ttl: int | None = None):
        self._ttl = ttl if ttl is not None else int(os.environ.get("IDEMPOTENCY_TTL_SECONDS", "86400"))
        self._data: dict[str, tuple[dict, float]] = {}

    def _get(self, key: str) -> dict | None:
        entry = self._data.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.monotonic() > expires_at:
            del self._data[key]
            return None
        return value

    def _set(self, key: str, value: dict, ttl: int) -> None:
        self._data[key] = (value, time.monotonic() + ttl)

    def _delete(self, key: str) -> None:
        self._data.pop(key, None)

    async def check_and_lock(self, cache_key: str, body_hash: str) -> tuple[str, dict | None, int | None]:
        data = self._get(cache_key)

        if data is None:
            self._set(cache_key, {"state": LockState.LOCKED, "body_hash": body_hash}, _LOCK_TTL_SECONDS)
            return ("proceed", None, None)

        if data["state"] == LockState.LOCKED:
            return ("conflict", None, None)

        if data["state"] == LockState.DONE:
            if data["body_hash"] != body_hash:
                return ("fingerprint_mismatch", None, None)
            return ("hit", data["response_body"], data["response_status"])

        return ("conflict", None, None)

    async def store_result(self, cache_key: str, body_hash: str, response_body: dict, response_status: int) -> None:
        data = self._get(cache_key)
        if data is None or data.get("state") != LockState.LOCKED or data.get("body_hash") != body_hash:
            return
        self._set(cache_key, {"state": LockState.DONE, "body_hash": body_hash, "response_body": response_body, "response_status": response_status}, self._ttl)

    async def delete_lock(self, cache_key: str) -> None:
        data = self._get(cache_key)
        if data is not None and data.get("state") == LockState.LOCKED:
            self._delete(cache_key)

    async def close(self) -> None:
        pass


class RedisIdempotencyStore(IdempotencyStore):
    """Redis-backed store. Enable with:
      IRI_IDEMPOTENCY_STORE=app.demo_adapter.RedisIdempotencyStore
    Requires: REDIS installed, REDIS_URL env var
    """

    def __init__(self, redis_url: str | None = None, ttl: int | None = None):
        _url = redis_url if redis_url is not None else os.environ.get("REDIS_URL", "")
        if not _url:
            raise ValueError("REDIS_URL must be set to use RedisIdempotencyStore")
        self._client = aioredis.from_url(_url, decode_responses=True)
        self._ttl = ttl if ttl is not None else int(os.environ.get("IDEMPOTENCY_TTL_SECONDS", "86400"))

    def _rkey(self, cache_key: str) -> str:
        return f"iri:idem:{cache_key}"

    async def check_and_lock(self, cache_key: str, body_hash: str) -> tuple[str, dict | None, int | None]:
        rkey = self._rkey(cache_key)
        lock_value = json.dumps({"state": LockState.LOCKED, "body_hash": body_hash})

        is_new = await self._client.set(rkey, lock_value, nx=True, ex=_LOCK_TTL_SECONDS)
        if is_new:
            return ("proceed", None, None)

        raw = await self._client.get(rkey)
        if raw is None:
            # Key expired between our SET NX and GET; try once more.
            is_new2 = await self._client.set(rkey, lock_value, nx=True, ex=_LOCK_TTL_SECONDS)
            if is_new2:
                return ("proceed", None, None)
            return ("conflict", None, None)

        data = json.loads(raw)
        if data["state"] == LockState.LOCKED:
            return ("conflict", None, None)

        if data["state"] == LockState.DONE:
            if data["body_hash"] != body_hash:
                return ("fingerprint_mismatch", None, None)
            return ("hit", data["response_body"], data["response_status"])

        return ("conflict", None, None)

    async def store_result(self, cache_key: str, body_hash: str, response_body: dict, response_status: int) -> None:
        """Write DONE only if we still own the lock, using WATCH/MULTI/EXEC optimistic locking."""
        rkey = self._rkey(cache_key)
        expected_lock = json.dumps({"state": LockState.LOCKED, "body_hash": body_hash})
        done_value = json.dumps({"state": LockState.DONE, "body_hash": body_hash, "response_body": response_body, "response_status": response_status})

        async with self._client.pipeline() as pipe:
            try:
                await pipe.watch(rkey)
                if await pipe.get(rkey) != expected_lock:
                    await pipe.reset()
                    return
                pipe.multi()
                pipe.set(rkey, done_value, ex=self._ttl)
                await pipe.execute()
            except WatchError:
                pass  # key changed between watch and execute; another request owns it now

    async def delete_lock(self, cache_key: str) -> None:
        """Delete the lock entry only if still in LOCKED state, using WATCH/MULTI/EXEC."""
        rkey = self._rkey(cache_key)

        async with self._client.pipeline() as pipe:
            try:
                await pipe.watch(rkey)
                current = await pipe.get(rkey)
                if not current:
                    await pipe.reset()
                    return
                data = json.loads(current)
                if data.get("state") != LockState.LOCKED:
                    await pipe.reset()
                    return
                pipe.multi()
                pipe.delete(rkey)
                await pipe.execute()
            except WatchError:
                pass  # key changed between watch and execute; leave it alone

    async def close(self) -> None:
        await self._client.aclose()


class CommandError(RuntimeError):
    """Raised when an external subprocess command fails."""

    def __init__(self, cmd, returncode=None, stdout=None, stderr=None):
        self.cmd = cmd
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

        super().__init__(f"Command failed: {cmd} (rc={returncode})")


class PathSandbox:
    """A simple sandbox for file operations."""
    _base_temp_dir = None

    @classmethod
    def get_base_temp_dir(cls):
        """Get the base temporary directory for the sandbox."""
        if cls._base_temp_dir is None:
            # Create in system temp with a fixed name
            cls._base_temp_dir = os.path.join(os.getcwd(), "iri_sandbox")
            os.makedirs(cls._base_temp_dir, exist_ok=True)

            # create a test file
            with open(f"{cls._base_temp_dir}/test.txt", encoding="utf-8", mode="w") as f:
                f.write("hello world")
            logger.info(f"Created test file in sandbox: {cls._base_temp_dir}/test.txt")
        return cls._base_temp_dir


def demo_uuid(kind: str, name: str) -> str:
    """Generate a deterministic UUID based on the kind and name."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"demo:{kind}:{name}"))


def utc_now() -> datetime.datetime:
    """Return current UTC datetime timestamp"""
    return datetime.datetime.now(datetime.timezone.utc)


def utc_timestamp() -> int:
    """Return current UTC datetime timestamp as integer"""
    return int(utc_now().timestamp())


class DemoAdapter(
    status_adapter.FacilityAdapter, account_adapter.FacilityAdapter, compute_adapter.FacilityAdapter,
    filesystem_adapter.FacilityAdapter, storage_adapter.FacilityAdapter,
    task_adapter.FacilityAdapter, facility_adapter.FacilityAdapter
):
    """A demo implementation of the FacilityAdapter that returns hardcoded data."""
    def __init__(self):
        self.resources = []
        self.incidents = []
        self.events = []
        self.capabilities = {}
        self.user = User(id="gtorok", name="Gabor Torok", api_key="12345", client_ip="1.2.3.4")
        self.projects = []
        self.project_allocations = []
        self.user_allocations = []
        self.facility = {}
        self.locations = {}  # resource_id -> list[StorageInstance templates]
        self.access_endpoints = {}  # resource_id -> list[AccessEndpoint]
        self.sites = []
        self._init_state()

    def _init_state(self):
        now = utc_now()

        site1 = facility_models.Site(
            id=demo_uuid("site", "demo_site_1"),
            name="Demo Site 1",
            description="The first demo site",
            last_modified=now,
            short_name="DS1",
            operating_organization="Demo Org",
            country_name="USA",
            locality_name="Demo City",
            state_or_province_name="DC",
            latitude=36.173357,
            longitude=-234.51452,
            resource_ids=[],
        )

        site2 = facility_models.Site(
            id=demo_uuid("site", "demo_site_2"),
            name="Demo Site 2",
            description="The second demo site",
            last_modified=now,
            short_name="DS2",
            operating_organization="Demo Org",
            country_name="USA",
            locality_name="Example Town",
            state_or_province_name="ET",
            latitude=38.410558,
            longitude=-286.36999,
            resource_ids=[],
        )

        self.facility = facility_models.Facility(
            id=demo_uuid("facility", "demo_facility"),
            name="Demo Facility",
            description="A demo facility for testing the IRI Facility API",
            last_modified=now,
            short_name="DEMO",
            organization_name="Demo Organization",
            support_uri="https://support.demo.example",
            site_ids=[site1.id, site2.id],
        )

        self.sites = [site1, site2]

        day_ago = utc_now() - datetime.timedelta(days=1)
        self.capabilities = {
            "cpu": Capability(id=demo_uuid("capability", "cpu"), name="CPU Nodes", units=[AllocationUnit.node_hours]),
            "gpu": Capability(id=demo_uuid("capability", "gpu"), name="GPU Nodes", units=[AllocationUnit.node_hours]),
            "hpss": Capability(id=demo_uuid("capability", "hpss"), name="Tape Storage", units=[AllocationUnit.bytes, AllocationUnit.inodes]),
            "gpfs": Capability(id=demo_uuid("capability", "gpfs"), name="GPFS Storage", units=[AllocationUnit.bytes, AllocationUnit.inodes]),
        }

        pm = status_models.Resource(
            id=demo_uuid("resource", "perlmutter_compute_nodes"),
            site_id=site1.id,
            group="perlmutter",
            name="compute nodes",
            description="the perlmutter computer compute nodes",
            capability_ids=[
                self.capabilities["cpu"].id,
                self.capabilities["gpu"].id,
            ],
            current_status=status_models.Status.degraded,
            last_modified=day_ago,
            resource_type=status_models.ResourceType.compute,
            supported_endpoints=[status_models.Endpoint.compute],
        )

        hpss = status_models.Resource(
            id=demo_uuid("resource", "hpss"),
            site_id=site1.id,
            group="hpss",
            name="hpss",
            description="hpss tape storage",
            capability_ids=[self.capabilities["hpss"].id],
            current_status=status_models.Status.up,
            last_modified=day_ago,
            resource_type=status_models.ResourceType.storage,
            supported_endpoints=[status_models.Endpoint.filesystem],
        )

        cfs = status_models.Resource(
            id=demo_uuid("resource", "cfs"),
            site_id=site1.id,
            group="cfs",
            name="cfs",
            description="cfs storage",
            capability_ids=[self.capabilities["gpfs"].id],
            current_status=status_models.Status.up,
            last_modified=day_ago,
            resource_type=status_models.ResourceType.storage,
            supported_endpoints=[status_models.Endpoint.filesystem],
        )

        login = status_models.Resource(
            id=demo_uuid("resource", "login_nodes"),
            site_id=site2.id,
            group="perlmutter",
            name="login nodes",
            description="the perlmutter computer login nodes",
            capability_ids=[],
            current_status=status_models.Status.degraded,
            last_modified=day_ago,
            resource_type=status_models.ResourceType.system,
        )

        iris = status_models.Resource(
            id=demo_uuid("resource", "iris"),
            site_id=site2.id,
            group="services",
            name="Iris",
            description="Iris webapp",
            capability_ids=[],
            current_status=status_models.Status.down,
            last_modified=day_ago,
            resource_type=status_models.ResourceType.website,
        )
        sfapi = status_models.Resource(
            id=demo_uuid("resource", "sfapi"),
            site_id=site2.id,
            group="services",
            name="sfapi",
            description="the Superfacility API",
            capability_ids=[],
            current_status=status_models.Status.up,
            last_modified=day_ago,
            resource_type=status_models.ResourceType.service,
        )

        self.resources = [pm, hpss, cfs, login, iris, sfapi]

        _rw = storage_models.AccessPermissions(read=True, write=True, execute=True)
        _ro = storage_models.AccessPermissions(read=True, write=False, execute=True)

        # Paths use {user}, {first} (first letter of username), and {project} as placeholders.
        # Project-scoped entries (containing {project}) are expanded per-project at query time.
        # Each resource_id carries the access semantics for its own context — a compute
        # resource shows in-job permissions, a login/DTN/Globus resource shows what that
        # endpoint can do. There is no separate access_outside_of_job field.

        # Perlmutter compute nodes: in-job semantics. Home is read-only inside a job;
        # archive (HPSS) is not accessible from compute, so it isn't mounted here at all.
        self.locations[pm.id] = [
            storage_models.StorageInstance(
                logical_name=storage_models.LogicalName.home,
                path="/global/homes/{first}/{user}",
                access=_ro,
                filesystem="gpfs-homes",
                performance_tier="medium",
                purge_policy_days=None,
                shared=False,
            ),
            storage_models.StorageInstance(
                logical_name=storage_models.LogicalName.scratch,
                path="/pscratch/sd/{first}/{user}",
                access=_rw,
                filesystem="lustre-scratch",
                performance_tier="high",
                purge_policy_days=30,
                shared=False,
            ),
            storage_models.StorageInstance(
                logical_name=storage_models.LogicalName.project,
                path="/global/project/projectdirs/{project}/{user}",
                access=_rw,
                filesystem="gpfs-project",
                performance_tier="medium",
                purge_policy_days=None,
                shared=True,
            ),
            storage_models.StorageInstance(
                logical_name=storage_models.LogicalName.campaign,
                path="/global/cfs/cdirs/{project}/campaign/{user}",
                access=_rw,
                filesystem="gpfs-cfs",
                performance_tier="medium",
                purge_policy_days=120,
                shared=True,
            ),
        ]

        # HPSS tape system: archive only; user accesses it through this resource_id
        # (typically via login nodes or htar). Archive is rw from this resource.
        self.locations[hpss.id] = [
            storage_models.StorageInstance(
                logical_name=storage_models.LogicalName.archive,
                path="/home/{first}/{user}",
                access=_rw,
                filesystem="hpss",
                performance_tier="tape",
                purge_policy_days=None,
                shared=False,
            ),
        ]

        # CFS / GPFS resource (queried via login nodes / DTN-style endpoint): all tiers rw,
        # shared is read-only because it's the project-shared landing area.
        self.locations[cfs.id] = [
            storage_models.StorageInstance(
                logical_name=storage_models.LogicalName.home,
                path="/global/homes/{first}/{user}",
                access=_rw,
                filesystem="gpfs-homes",
                performance_tier="medium",
                purge_policy_days=None,
                shared=False,
            ),
            storage_models.StorageInstance(
                logical_name=storage_models.LogicalName.scratch,
                path="/pscratch/sd/{first}/{user}",
                access=_rw,
                filesystem="lustre-scratch",
                performance_tier="high",
                purge_policy_days=30,
                shared=False,
            ),
            storage_models.StorageInstance(
                logical_name=storage_models.LogicalName.project,
                path="/global/project/projectdirs/{project}/{user}",
                access=_rw,
                filesystem="gpfs-project",
                performance_tier="medium",
                purge_policy_days=None,
                shared=True,
            ),
            storage_models.StorageInstance(
                logical_name=storage_models.LogicalName.campaign,
                path="/global/cfs/cdirs/{project}/campaign/{user}",
                access=_rw,
                filesystem="gpfs-cfs",
                performance_tier="medium",
                purge_policy_days=120,
                shared=True,
            ),
            storage_models.StorageInstance(
                logical_name=storage_models.LogicalName.shared,
                path="/global/cfs/cdirs/{project}/shared",
                access=_ro,
                filesystem="gpfs-cfs",
                performance_tier="medium",
                purge_policy_days=None,
                shared=True,
            ),
            storage_models.StorageInstance(
                logical_name=storage_models.LogicalName.temporary,
                path="/tmp/{user}",
                access=_rw,
                filesystem="tmpfs",
                performance_tier="high",
                purge_policy_days=7,
                shared=False,
            ),
        ]

        # Login nodes: same filesystem layout as CFS — outside-of-job semantics for everything.
        self.locations[login.id] = self.locations[cfs.id]

        globus_cfs_id = demo_uuid("endpoint", "globus-cfs")
        globus_hpss_id = demo_uuid("endpoint", "globus-hpss")

        self.access_endpoints[cfs.id] = [
            storage_models.AccessEndpoint(
                id="globus-cfs-demo",
                resource_id=cfs.id,
                protocol=storage_models.AccessProtocol.globus,
                display_name="Demo CFS Globus",
                endpoint_id=globus_cfs_id,
                uri=f"globus://{globus_cfs_id}/",
                root_path="/",
                auth_type="globus",
                capabilities=[
                    storage_models.AccessCapability.list,
                    storage_models.AccessCapability.read,
                    storage_models.AccessCapability.write,
                    storage_models.AccessCapability.transfer,
                ],
            ),
            storage_models.AccessEndpoint(
                id="xrootd-cfs-demo",
                resource_id=cfs.id,
                protocol=storage_models.AccessProtocol.xrootd,
                display_name="Demo CFS XRootD",
                endpoint="root://cfs.demo.example/",
                auth_type="x509",
                capabilities=[
                    storage_models.AccessCapability.read,
                    storage_models.AccessCapability.streaming,
                ],
            ),
            storage_models.AccessEndpoint(
                id="s3-cfs-demo",
                resource_id=cfs.id,
                protocol=storage_models.AccessProtocol.s3,
                display_name="Demo CFS S3",
                bucket="demo-cfs",
                region="us-east-1",
                endpoint_url="https://s3.demo.example",
                auth_type="aws_s3",
                capabilities=[
                    storage_models.AccessCapability.list,
                    storage_models.AccessCapability.read,
                    storage_models.AccessCapability.write,
                ],
            ),
        ]

        self.access_endpoints[hpss.id] = [
            storage_models.AccessEndpoint(
                id="globus-hpss-demo",
                resource_id=hpss.id,
                protocol=storage_models.AccessProtocol.globus,
                display_name="Demo HPSS Globus",
                endpoint_id=globus_hpss_id,
                uri=f"globus://{globus_hpss_id}/",
                root_path="/home",
                auth_type="globus",
                capabilities=[
                    storage_models.AccessCapability.list,
                    storage_models.AccessCapability.read,
                    storage_models.AccessCapability.write,
                    storage_models.AccessCapability.transfer,
                ],
            ),
        ]

        # Populate site resource_ids based on which resources are at each site
        site1.resource_ids = [r.id for r in self.resources if r.site_id == site1.id]
        site2.resource_ids = [r.id for r in self.resources if r.site_id == site2.id]

        self.projects = [
            account_models.Project(
                id=demo_uuid("project", "staff_research"),
                name="Staff research project",
                description="Compute and storage allocation for staff research use",
                user_ids=["gtorok"],
                last_modified=day_ago,
            ),
            account_models.Project(
                id=demo_uuid("project", "test_project"),
                name="Test project",
                description="Compute and storage allocation for testing use",
                user_ids=["gtorok"],
                last_modified=day_ago,
            ),
        ]

        for p in self.projects:
            for c in self.capabilities.values():
                pa = account_models.ProjectAllocation(
                    id=demo_uuid("project_allocation", f"{p.id}_{c.id}"),
                    project_id=p.id,
                    capability_id=c.id,
                    entries=[
                        account_models.AllocationEntry(
                            allocation=500 + random.random() * 500,
                            usage=100 + random.random() * 100,
                            unit=cu,
                        )
                        for cu in c.units
                    ],
                )
                self.project_allocations.append(pa)
                self.user_allocations.append(
                    account_models.UserAllocation(
                        id=demo_uuid("user_allocation", f"{pa.id}_gtorok"),
                        project_id=pa.project_id,
                        project_allocation_id=pa.id,
                        user_id="gtorok",
                        entries=[account_models.AllocationEntry(allocation=a.allocation / 10, usage=a.usage / 10, unit=a.unit) for a in pa.entries],
                    )
                )

        statuses = {r.name: status_models.Status.up for r in self.resources}
        last_incidents = {}
        d = datetime.datetime(2025, 3, 1, 10, 0, 0, tzinfo=datetime.timezone.utc)

        # generate some events and incidents
        # here every incident only has events from a single resource,
        # but in reality it is possible for an incident to have events from multiple resources
        for _i in range(0, 1000):
            r = random.choice(self.resources)
            status = statuses[r.name]
            event = status_models.Event(
                id=demo_uuid("event", f"{r.name}_{d.isoformat()}"),
                name=f"{r.name} is {status.value}",
                description=f"{r.name} is {status.value}",
                occurred_at=d,
                status=status,
                resource_id=r.id,
                last_modified=day_ago,
            )
            self.events.append(event)
            if r.name in last_incidents:
                inc = last_incidents[r.name]
                event.incident_id = inc.id
                inc.event_ids.append(event.id)
                if status == status_models.Status.up:
                    inc.end = d
                    del last_incidents[r.name]

            if random.random() > 0.9:
                if status == status_models.Status.down:
                    statuses[r.name] = status_models.Status.up
                else:
                    statuses[r.name] = status_models.Status.down
                    dstr = d.strftime("%Y-%m-%d %H:%M:%S.%f%z")
                    incident = status_models.Incident(
                        id=demo_uuid("incident", f"{r.name}_{dstr}"),
                        name=f"{r.name} incident at {dstr}",
                        description=f"{r.name} incident at {dstr}",
                        status=status_models.Status.down,
                        event_ids=[],
                        resource_ids=random.choices([r.id for r in self.resources], k=3),
                        start=d,
                        end=d,
                        type=random.choice(list(status_models.IncidentType)),
                        resolution=random.choice(list(status_models.Resolution)),
                        last_modified=d,
                    )
                    self.incidents.append(incident)
                    last_incidents[r.name] = incident

            d += datetime.timedelta(minutes=int(random.random() * 15 + 1))

    # ----------------------------
    # Facility API
    # ----------------------------

    async def get_facility(self: "DemoAdapter", modified_since: str | None = None) -> facility_models.Facility:
        return self.facility

    async def list_sites(
        self: "DemoAdapter", modified_since: str | None = None, name: str | None = None, offset: int | None = None, limit: int | None = None, short_name: str | None = None
    ) -> list[facility_models.Site]:
        sites = self.sites

        if name:
            sites = [s for s in sites if name.lower() in s.name.lower()]  # pylint: disable=no-member

        if short_name:
            sites = [s for s in sites if s.short_name == short_name]

        if modified_since:
            ms = datetime.datetime.fromisoformat(str(modified_since))
            sites = [s for s in sites if s.last_modified > ms]

        o = offset or 0
        l = limit or len(sites)
        return sites[o : o + l]

    async def get_site(self: "DemoAdapter", site_id: str, modified_since: str | None = None) -> facility_models.Site:
        site = next((s for s in self.sites if s.id == site_id), None)
        if not site:
            raise HTTPException(status_code=404, detail="Site not found")

        if modified_since:
            ms = datetime.datetime.fromisoformat(str(modified_since))
            if site.last_modified <= ms:
                raise HTTPException(status_code=304, headers={"Last-Modified": site.last_modified.isoformat()})

        return site

    # ----------------------------
    # Status API
    # ----------------------------

    async def get_resources(
        self: "DemoAdapter",
        offset: int,
        limit: int,
        name: str | None = None,
        description: str | None = None,
        group: str | None = None,
        modified_since: datetime.datetime | None = None,
        resource_type: status_models.ResourceType | None = None,
        current_status: status_models.Status | None = None,
        capability: Capability | None = None,
        site_id: str | None = None,
    ) -> list[status_models.Resource]:
        resources = status_models.Resource.find(
            self.resources,
            name=name,
            description=description,
            group=group,
            modified_since=modified_since,
            resource_type=resource_type,
            current_status=current_status,
            capability=capability,
            site_id=site_id,
        )
        return paginate_list(resources, offset, limit)

    async def get_resource(self: "DemoAdapter", id_: str) -> status_models.Resource:
        return status_models.Resource.find_by_id(self.resources, id_)

    async def get_resources_for_endpoint(self: "DemoAdapter", endpoint: status_models.Endpoint) -> list[status_models.Resource]:
        return [r for r in self.resources if endpoint in r.supported_endpoints]

    async def get_events(
        self: "DemoAdapter",
        offset: int,
        limit: int,
        incident_id: str | None = None,
        resource_id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        status: status_models.Status | None = None,
        from_: datetime.datetime | None = None,
        to: datetime.datetime | None = None,
        time_: datetime.datetime | None = None,
        modified_since: datetime.datetime | None = None,
    ) -> list[status_models.Event]:
        events = status_models.Event.find(
            self.events,
            incident_id=incident_id,
            resource_id=resource_id,
            name=name,
            description=description,
            status=status,
            from_=from_,
            to=to,
            time_=time_,
            modified_since=modified_since,
        )
        return paginate_list(events, offset, limit)

    async def get_event(self: "DemoAdapter", id_: str) -> status_models.Event:
        return status_models.Event.find_by_id(self.events, id_)

    async def get_incidents(
        self: "DemoAdapter",
        offset: int,
        limit: int,
        name: str | None = None,
        description: str | None = None,
        status: status_models.Status | None = None,
        type_: status_models.IncidentType | None = None,
        from_: datetime.datetime | None = None,
        to: datetime.datetime | None = None,
        time_: datetime.datetime | None = None,
        modified_since: datetime.datetime | None = None,
        resource_id: str | None = None,
        resolution: status_models.Resolution | None = None,
    ) -> list[status_models.Incident]:
        incidents = status_models.Incident.find(
            self.incidents,
            name=name,
            description=description,
            status=status,
            type_=type_,
            from_=from_,
            to=to,
            time_=time_,
            modified_since=modified_since,
            resource_id=resource_id,
            resolution=resolution,
        )
        return paginate_list(incidents, offset, limit)

    async def get_incident(self: "DemoAdapter", id_: str) -> status_models.Incident:
        return status_models.Incident.find_by_id(self.incidents, id_)

    async def get_capabilities(self: "DemoAdapter", name: str | None = None, modified_since: str | None = None, offset: int = 0, limit: int = 1000) -> list[Capability]:
        return self.capabilities.values()

    async def get_current_user(
        self: "DemoAdapter",
        api_key: str,
        client_ip: str,
    ) -> str:
        """
        In a real deployment, this would decode the api_key jwt and return the current user's id.
        This method is not async.
        """
        if api_key != self.user.api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return "gtorok"

    async def get_current_user_globus(
            self: "DemoAdapter",
            api_key: str,
            client_ip: str,
            globus_introspect: dict | None,
        ) -> str:
        """
        Decode the api_key and return the authenticated user's id from information returned by introspecting a globus token.
        This method is not called directly, rather authorized endpoints "depend" on it.
        (https://fastapi.tiangolo.com/tutorial/dependencies/)
        """
        return "gtorok"

    async def get_user(
        self: "DemoAdapter",
        user_id: str,
        api_key: str,
        client_ip: str | None,
        globus_introspect: dict | None,
    ) -> User:
        if user_id != self.user.id:
            raise HTTPException(status_code=403, detail="User not found")
        if api_key.startswith("Bearer "):
            api_key = api_key[len("Bearer ") :]
        return self.user

    async def get_projects(self: "DemoAdapter", user: User) -> list[account_models.Project]:
        return self.projects

    async def get_project_allocations(
        self: "DemoAdapter",
        project: account_models.Project,
        user: User,
    ) -> list[account_models.ProjectAllocation]:
        return [pa for pa in self.project_allocations if pa.project_id == project.id]

    async def get_user_allocations(
        self: "DemoAdapter",
        user: User,
        project_allocation: account_models.ProjectAllocation,
    ) -> list[account_models.UserAllocation]:
        return [ua for ua in self.user_allocations if ua.project_allocation_id == project_allocation.id]

    async def submit_job(
        self: "DemoAdapter",
        resource: status_models.Resource,
        user: User,
        job_spec: compute_models.JobSpec,
    ) -> compute_models.Job:
        facility_project = get_iri_facility_project()
        account = facility_project or (job_spec.attributes.account if job_spec.attributes else None)
        return compute_models.Job(
            id="job_123",
            status=compute_models.JobStatus(
                state=compute_models.JobState.NEW,
                time=utc_timestamp(),
                message="job submitted",
                exit_code=0,
                meta_data={"account": account},
            ),
        )

    async def update_job(
        self: "DemoAdapter",
        resource: status_models.Resource,
        user: User,
        job_spec: compute_models.JobSpec,
        job_id: str,
    ) -> compute_models.Job:
        facility_project = get_iri_facility_project()
        account = facility_project or (job_spec.attributes.account if job_spec.attributes else None)
        return compute_models.Job(
            id=job_id,
            status=compute_models.JobStatus(
                state=compute_models.JobState.ACTIVE,
                time=utc_timestamp(),
                message="job updated",
                exit_code=0,
                meta_data={"account": account},
            ),
        )

    async def get_job(
        self: "DemoAdapter",
        resource: status_models.Resource,
        user: User,
        job_id: str,
        historical: bool = False,
        include_spec: bool = False,
    ) -> compute_models.Job:
        return compute_models.Job(
            id=job_id,
            status=compute_models.JobStatus(
                state=compute_models.JobState.COMPLETED,
                time=utc_timestamp(),
                message="job completed successfully",
                exit_code=0,
                meta_data={"account": "account1"},
            ),
        )

    async def get_jobs(
        self: "DemoAdapter",
        resource: status_models.Resource,
        user: User,
        offset: int,
        limit: int,
        filters: dict[str, object] | None = None,
        historical: bool = False,
        include_spec: bool = False,
    ) -> list[compute_models.Job]:
        return [
            compute_models.Job(
                id=f"job_{i}",
                status=compute_models.JobStatus(
                    state=random.choice([s for s in compute_models.JobState]),
                    time=utc_timestamp() - int(random.random() * 100),
                    message="",
                    exit_code=random.choice([0, 0, 0, 0, 0, 1, 1, 128, 127]),
                    meta_data={"account": "account1"},
                ),
            )
            for i in range(random.randint(3, 10))
        ]

    async def cancel_job(
        self: "DemoAdapter",
        resource: status_models.Resource,
        user: User,
        job_id: str,
    ) -> bool:
        # call slurm/etc. to cancel job
        return True

# ----------------------------------------------
# Storage API
# ----------------------------------------------

    @staticmethod
    def _slugify_project(name: str) -> str:
        """Convert a project name to a path-safe slug (real facilities use codes like 'm1234')."""
        return name.lower().replace(" ", "_")

    def _user_project_codes(self, user: User) -> list[str]:
        """Return the path-slug codes of all projects the user belongs to."""
        return [self._slugify_project(p.name) for p in self.projects if user.id in p.user_ids]

    def _user_member_of(self, user: User, project_code: str) -> bool:
        """Authorization check: is the user a member of the named project?"""
        return any(
            user.id in p.user_ids and self._slugify_project(p.name) == project_code
            for p in self.projects
        )

    def _resolve_path(self, template: str, user: User, project: str | None) -> str:
        first = user.id[0] if user.id else "u"
        path = template.replace("{user}", user.id).replace("{first}", first)
        if project:
            path = path.replace("{project}", project)
        return path

    def _apply_intent_filter(
        self,
        instance: storage_models.StorageInstance,
        intent: storage_models.StorageIntent | None,
    ) -> bool:
        """Return False if this storage instance should be excluded for the given intent."""
        if intent == storage_models.StorageIntent.long_term_storage:
            return instance.logical_name == storage_models.LogicalName.archive
        if intent == storage_models.StorageIntent.staging:
            return instance.logical_name != storage_models.LogicalName.archive
        if intent == storage_models.StorageIntent.write:
            return instance.access.write
        return True

    async def get_locations(
        self,
        resource: status_models.Resource,
        user: User,
        logicalpath: storage_models.LogicalName | None,
        project: str | None,
        allocation: str | None,
        intent: storage_models.StorageIntent | None,
    ) -> list[storage_models.StorageInstance]:
        templates = self.locations.get(resource.id, [])
        effective_project = project or allocation

        # Authorization: a user can only resolve paths for their own projects
        if effective_project and not self._user_member_of(user, effective_project):
            raise HTTPException(status_code=403, detail=f"User is not a member of project '{effective_project}'")

        # Expand project-scoped paths across ALL of the user's projects when none specified
        project_codes = [effective_project] if effective_project else self._user_project_codes(user)

        result = []
        for m in templates:
            if logicalpath and m.logical_name != logicalpath:
                continue
            if not self._apply_intent_filter(m, intent):
                continue

            is_project_scoped = "{project}" in m.path
            expand_over = project_codes if is_project_scoped else [None]

            for code in expand_over:
                result.append(storage_models.StorageInstance(
                    logical_name=m.logical_name,
                    path=self._resolve_path(m.path, user, code),
                    filesystem=m.filesystem,
                    performance_tier=m.performance_tier,
                    purge_policy_days=m.purge_policy_days,
                    shared=m.shared,
                    access=m.access,
                ))
        return result

    async def get_access_endpoints(
        self,
        resource: status_models.Resource,
        user: User,
        protocol: storage_models.AccessProtocol | None,
        endpoint_id: str | None,
    ) -> list[storage_models.AccessEndpoint]:
        endpoints = self.access_endpoints.get(resource.id, [])
        if protocol:
            endpoints = [e for e in endpoints if e.protocol == protocol]
        if endpoint_id:
            endpoints = [e for e in endpoints if e.id == endpoint_id]
        return endpoints

    def validate_path(self, path: str, allow_symlinks: bool = True) -> str:
        """Validate that the given path is within the sandbox base directory and optionally check for symlinks."""
        basedir = PathSandbox.get_base_temp_dir()
        real_path = os.path.realpath(os.path.join(basedir, path))

        # Check within sandbox
        if not real_path.startswith(basedir + os.sep) and real_path != basedir:
            raise HTTPException(status_code=400, detail=f"Path outside sandbox: {path}")

        # Optionally block symlinks that point outside sandbox
        if not allow_symlinks and os.path.islink(os.path.join(basedir, path)):
            link_target = os.readlink(os.path.join(basedir, path))
            if os.path.isabs(link_target):
                raise HTTPException(status_code=400, detail=f"Absolute symlink not allowed: {path}")

        return real_path

# ----------------------------------------------
# Filesystem API
# ----------------------------------------------
    def _run(self, args, *, shell: bool = False, timeout: int | None = 3600, text: bool = True) -> subprocess.CompletedProcess:
        """
        Run a subprocess command and catch exceptions.
        Raises CommandError on failure with captured diagnostics.
        """
        try:
            return subprocess.run(args, shell=shell, capture_output=True, text=text, check=True, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            logger.warning(f"Command timed out: {args} (after {timeout} seconds)")
            raise CommandError(cmd=args, returncode=None, stdout=exc.stdout, stderr=exc.stderr) from exc
        except subprocess.CalledProcessError as exc:
            logger.warning(f"Command failed: {args} (rc={exc.returncode})\nstdout: {exc.stdout}\nstderr: {exc.stderr}")
            raise CommandError(cmd=args, returncode=exc.returncode, stdout=exc.stdout, stderr=exc.stderr) from exc
        except OSError as exc:
            logger.warning(f"OS error running command: {args}\nError: {exc}")
            raise CommandError(cmd=args, returncode=None, stdout=None, stderr=str(exc)) from exc


    def _file(self, path: str) -> filesystem_models.File:
        # Get file stats (follows symlinks by default)
        rp = self.validate_path(path)
        file_stat = os.stat(rp)  # Use lstat to not follow symlinks

        # Get file type
        if stat.S_ISDIR(file_stat.st_mode):
            file_type = "directory"
        elif stat.S_ISLNK(file_stat.st_mode):
            file_type = "symlink"
        elif stat.S_ISREG(file_stat.st_mode):
            file_type = "file"
        else:
            file_type = "other"

        # Get link target if it's a symlink
        link_target = None
        if stat.S_ISLNK(file_stat.st_mode):
            link_target = os.readlink(rp)

        # Get user and group names
        user = pwd.getpwuid(file_stat.st_uid).pw_name
        group = grp.getgrgid(file_stat.st_gid).gr_name

        # Get permissions in rwxrwxrwx format
        permissions = stat.filemode(file_stat.st_mode)

        # Get last modified time
        last_modified = datetime.datetime.fromtimestamp(file_stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")

        # Get size
        size = str(file_stat.st_size)
        data = dict(
            name=os.path.basename(rp),
            type=file_type,
            user=user,
            group=group,
            permissions=permissions,
            last_modified=last_modified,
            size=size,
        )

        if link_target is not None:
            data["link_target"] = link_target

        return filesystem_models.File(**data)


    async def chmod(self: "DemoAdapter", resource: status_models.Resource, user: User, request_model: filesystem_models.PutFileChmodRequest) -> filesystem_models.PutFileChmodResponse:
        rp = self.validate_path(request_model.path)
        os.chmod(rp, int(request_model.mode, 8))
        return filesystem_models.PutFileChmodResponse(output=self._file(rp))

    async def chown(
        self: "DemoAdapter",
        resource: status_models.Resource,
        user: User,
        request_model: filesystem_models.PutFileChownRequest,
    ) -> filesystem_models.PutFileChownResponse:
        rp = self.validate_path(request_model.path)
        os.chown(rp, request_model.owner, request_model.group)
        return filesystem_models.PutFileChownResponse(output=self._file(rp))

    async def ls(
        self: "DemoAdapter",
        resource: status_models.Resource,
        user: User,
        path: str,
        show_hidden: bool,
        numeric_uid: bool,
        recursive: bool,
        dereference: bool,
    ) -> filesystem_models.GetDirectoryLsResponse:
        rp = self.validate_path(path)
        files = glob.glob(rp, recursive=recursive)
        return filesystem_models.GetDirectoryLsResponse(output=[self._file(f) for f in files])

    def _headtail(
        self: "DemoAdapter",
        cmd: str,
        path: str,
        file_bytes: int | None,
        lines: int | None,
        skip_heading: bool = False,
        skip_trailing: bool = False,
    ) -> str:
        args = [cmd]

        if cmd == "tail" and skip_heading:
            if file_bytes is not None:
                args.extend(["-c", f"+{file_bytes + 1}"])
            elif lines is not None:
                args.extend(["-n", f"+{lines + 1}"])
        if cmd == "head" and skip_trailing:
            if file_bytes is not None:
                args.extend(["-c", f"-{file_bytes}"])
            elif lines is not None:
                args.extend(["-n", f"-{lines}"])
        else:
            if file_bytes is not None:
                args.extend(["-c", str(file_bytes)])
            elif lines is not None:
                args.extend(["-n", str(lines)])

        rp = self.validate_path(path)
        args.append(rp)

        result = self._run(args)
        return result.stdout

    async def head(
        self: "DemoAdapter",
        resource: status_models.Resource,
        user: User,
        path: str,
        file_bytes: int | None,
        lines: int | None,
        skip_trailing: bool = False,
    ) -> filesystem_models.GetFileHeadResponse:
        content = self._headtail("head", path, file_bytes, lines, skip_trailing=skip_trailing)

        fc = filesystem_models.FileContent(
            content=content,
            content_type=(filesystem_models.ContentUnit.bytes
                          if file_bytes is not None
                          else filesystem_models.ContentUnit.lines),
            start_position=0,
            end_position=len(content))

        return filesystem_models.GetFileHeadResponse(output=fc)

    async def tail(
        self: "DemoAdapter",
        resource: status_models.Resource,
        user: User,
        path: str,
        file_bytes: int | None,
        lines: int | None,
        skip_heading: bool = False,
    ) -> filesystem_models.GetFileTailResponse:

        content = self._headtail("tail", path, file_bytes, lines, skip_heading=skip_heading)

        fc = filesystem_models.FileContent(
            content=content,
            content_type=(filesystem_models.ContentUnit.bytes
                          if file_bytes is not None
                          else filesystem_models.ContentUnit.lines),
            start_position=0,
            end_position=len(content))

        return filesystem_models.GetFileTailResponse(output=fc)



    async def view(self: "DemoAdapter", resource: status_models.Resource, user: User, path: str, size: int, offset: int) -> filesystem_models.GetViewFileResponse:
        rp = self.validate_path(path)
        result = self._run(f"tail -c +{offset + 1} {rp} | head -c {size}", shell=True)
        content = result.stdout
        return filesystem_models.GetViewFileResponse(
            output=filesystem_models.FileContent(
                content=content,
                content_type=filesystem_models.ContentUnit.bytes,
                start_position=offset,
                end_position=offset + len(content)
            ),
        )

    async def checksum(self: "DemoAdapter", resource: status_models.Resource, user: User, path: str) -> filesystem_models.GetFileChecksumResponse:
        rp = self.validate_path(path)
        result = self._run(["sha256sum", rp])
        checksum = result.stdout.split()[0]
        return filesystem_models.GetFileChecksumResponse(
            output=filesystem_models.FileChecksum(
                checksum=checksum,
            )
        )

    async def file(self: "DemoAdapter", resource: status_models.Resource, user: User, path: str) -> filesystem_models.GetFileTypeResponse:
        rp = self.validate_path(path)
        result = self._run(["file", "-b", rp])
        return filesystem_models.GetFileTypeResponse(
            output=result.stdout.strip(),
        )

    async def stat(self: "DemoAdapter", resource: status_models.Resource, user: User, path: str, dereference: bool) -> filesystem_models.GetFileStatResponse:
        rp = self.validate_path(path)
        if dereference:
            stat_info = os.stat(rp)
        else:
            stat_info = os.lstat(rp)
        return filesystem_models.GetFileStatResponse(
            output=filesystem_models.FileStat(
                mode=stat_info.st_mode,
                ino=stat_info.st_ino,
                dev=stat_info.st_dev,
                nlink=stat_info.st_nlink,
                uid=stat_info.st_uid,
                gid=stat_info.st_gid,
                size=stat_info.st_size,
                atime=int(stat_info.st_atime),
                ctime=int(stat_info.st_ctime),
                mtime=int(stat_info.st_mtime),
            )
        )

    async def rm(
        self: "DemoAdapter",
        resource: status_models.Resource,
        user: User,
        path: str,
    ) -> filesystem_models.RemoveResponse:
        rp = self.validate_path(path)
        if rp == PathSandbox.get_base_temp_dir():
            raise HTTPException(status_code=400, detail="Cannot delete sandbox")
        self._run(["rm", "-rf", rp])
        return filesystem_models.RemoveResponse(output=f"Removed {rp}")

    async def mkdir(self: "DemoAdapter", resource: status_models.Resource, user: User, request_model: filesystem_models.PostMakeDirRequest) -> filesystem_models.PostMkdirResponse:
        rp = self.validate_path(request_model.path)
        args = ["mkdir"]
        if request_model.parent:
            args.append("-p")
        args.append(rp)
        self._run(args)
        return filesystem_models.PostMkdirResponse(output=self._file(rp))

    async def symlink(
        self: "DemoAdapter", resource: status_models.Resource, user: User, request_model: filesystem_models.PostFileSymlinkRequest
    ) -> filesystem_models.PostFileSymlinkResponse:
        rp_src = self.validate_path(request_model.path)
        rp_dst = self.validate_path(request_model.link_path)
        self._run(["ln", "-s", rp_src, rp_dst])
        return filesystem_models.PostFileSymlinkResponse(output=self._file(rp_dst))

    async def download(self: "DemoAdapter", resource: status_models.Resource, user: User, path: str) -> filesystem_models.GetFileDownloadResponse:
        rp = self.validate_path(path)
        raw_content = pathlib.Path(rp).read_bytes()

        if len(raw_content) > filesystem_adapter.OPS_SIZE_LIMIT:
            raise Exception("File to download is too large.")

        return filesystem_models.GetFileDownloadResponse(
            output=base64.b64encode(raw_content).decode("utf-8"),
        )

    async def upload(self: "DemoAdapter", resource: status_models.Resource, user: User, path: str, content: str) -> filesystem_models.PutFileUploadResponse:
        rp = self.validate_path(path)
        if isinstance(content, bytes):
            pathlib.Path(rp).write_bytes(content)
        elif isinstance(content, str):
            pathlib.Path(rp).write_bytes(base64.b64decode(content))
        else:
            raise Exception(f"Don't know how to handle variable of type: {type(content)}")
        return filesystem_models.PutFileUploadResponse(output=f"Uploaded to {rp}")

    async def compress(
        self: "DemoAdapter", resource: status_models.Resource, user: User, request_model: filesystem_models.PostCompressRequest
    ) -> filesystem_models.PostCompressResponse:
        src_rp = self.validate_path(request_model.path)
        dst_rp = self.validate_path(request_model.target_path)

        args = ["tar"]
        if request_model.compression == filesystem_models.CompressionType.gzip:
            args.append("-czf")
        elif request_model.compression == filesystem_models.CompressionType.bzip2:
            args.append("-cjf")
        elif request_model.compression == filesystem_models.CompressionType.xz:
            args.append("-cJf")
        args.append(dst_rp)
        if request_model.dereference:
            args.append("--dereference")
        if request_model.match_pattern:
            args.append(f"--include={request_model.match_pattern}")

        args.append("-C")
        args.append(PathSandbox.get_base_temp_dir())
        p = pathlib.Path(src_rp)
        args.append(p.relative_to(PathSandbox.get_base_temp_dir()))
        subprocess.run(args, check=True)

        return filesystem_models.PostCompressResponse(output=self._file(dst_rp))

    async def extract(self: "DemoAdapter", resource: status_models.Resource, user: User, request_model: filesystem_models.PostExtractRequest) -> filesystem_models.PostExtractResponse:
        src_rp = self.validate_path(request_model.path)
        dst_rp = self.validate_path(request_model.target_path)

        if os.path.exists(dst_rp):
            if os.path.isdir(dst_rp):
                raise Exception(f"Target path already exists: {request_model.target_path}")
            else:
                raise Exception(f"Target path already exists and is not a directory: {request_model.target_path}")
        os.makedirs(dst_rp)

        args = ["tar"]
        if request_model.compression == filesystem_models.CompressionType.gzip:
            args.append("-xzf")
        elif request_model.compression == filesystem_models.CompressionType.bzip2:
            args.append("-xjf")
        elif request_model.compression == filesystem_models.CompressionType.xz:
            args.append("-xJf")
        else:
            args.append("-xf")
        args.append(src_rp)
        args.append("-C")
        args.append(dst_rp)
        subprocess.run(args, check=True)

        return filesystem_models.PostExtractResponse(output=self._file(dst_rp))

    async def mv(self: "DemoAdapter", resource: status_models.Resource, user: User, request_model: filesystem_models.PostMoveRequest) -> filesystem_models.PostMoveResponse:
        src_rp = self.validate_path(request_model.path)
        dst_rp = self.validate_path(request_model.target_path)
        subprocess.run(["mv", src_rp, dst_rp], check=True)
        return filesystem_models.PostMoveResponse(output=self._file(dst_rp))

    async def cp(self: "DemoAdapter", resource: status_models.Resource, user: User, request_model: filesystem_models.PostCopyRequest) -> filesystem_models.PostCopyResponse:
        src_rp = self.validate_path(request_model.path)
        dst_rp = self.validate_path(request_model.target_path)
        args = ["cp"]
        if request_model.dereference:
            args.append("-L")
        args.append(src_rp)
        args.append(dst_rp)
        subprocess.run(args, check=True)
        return filesystem_models.PostCopyResponse(output=self._file(dst_rp))

    async def get_task(self: "DemoAdapter", user: User, task_id: str) -> task_models.Task | None:
        await DemoTaskQueue.process_tasks(self)
        return next((t for t in DemoTaskQueue.tasks if t.user.name == user.name and t.id == task_id), None)

    async def get_tasks(self: "DemoAdapter", user: User) -> list[task_models.Task]:
        await DemoTaskQueue.process_tasks(self)
        return [t for t in DemoTaskQueue.tasks if t.user.name == user.name]

    async def put_task(self: "DemoAdapter", user: User, resource: status_models.Resource, task: str) -> task_models.TaskSubmitResponse:
        await DemoTaskQueue.process_tasks(self)
        return DemoTaskQueue.create_task(user, resource, task)

    async def delete_task(self: "DemoAdapter", user: User, task_id: str) -> None:
        await DemoTaskQueue.process_tasks(self)
        for t in DemoTaskQueue.tasks:
            if t.user.name == user.name and t.id == task_id:
                t.status = task_models.TaskStatus.canceled
                t.result = None
                break


class DemoTask(BaseModel):
    """A simple in-memory task queue for demonstration purposes."""
    id: str
    task: str
    resource: status_models.Resource
    user: User
    start: float
    status: task_models.TaskStatus = task_models.TaskStatus.pending
    result: dict | None = None


class DemoTaskQueue:
    """A simple in-memory task queue for demonstration purposes."""
    tasks = []

    @staticmethod
    async def process_tasks(da: DemoAdapter):
        """Process tasks in the queue, simulating task execution and completion."""
        now = utc_timestamp()
        _tasks = []
        for t in DemoTaskQueue.tasks:
            if now - t.start > 5 * 60 and t.status in [task_models.TaskStatus.completed, task_models.TaskStatus.canceled, task_models.TaskStatus.failed]:
                # delete old tasks
                continue
            if t.status == task_models.TaskStatus.pending and now - t.start > DEMO_QUEUE_UPDATE_SECS:
                t.status = task_models.TaskStatus.active
                t.start = now
            elif t.status == task_models.TaskStatus.active and now - t.start > DEMO_QUEUE_UPDATE_SECS:
                cmd = task_models.TaskCommand.model_validate_json(t.task)
                (result, status) = await DemoAdapter.on_task(t.resource, t.user, cmd)
                if isinstance(result, BaseModel):
                    t.result = result.model_dump()
                elif isinstance(result, dict):
                    t.result = result
                else:
                    t.result = {"output": result}
                t.status = status
            _tasks.append(t)
        DemoTaskQueue.tasks = _tasks

    @staticmethod
    def create_task(user: User, resource: status_models.Resource, command: task_models.TaskCommand) -> task_models.TaskSubmitResponse:
        """Create a new task in the queue."""
        task_id = f"task_{len(DemoTaskQueue.tasks)}"
        DemoTaskQueue.tasks.append(DemoTask(id=task_id, task=command.model_dump_json(), user=user, resource=resource, start=utc_timestamp()))
        logger.info(f"Created task: {task_id}")
        return task_models.TaskSubmitResponse(task_id=task_id)
