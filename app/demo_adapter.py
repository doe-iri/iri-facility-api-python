import base64
import datetime
import glob
import grp
import os
import pathlib
import pwd
import random
import stat
import subprocess
import uuid
from typing import Any, Tuple

from fastapi import HTTPException
from pydantic import BaseModel

from .routers.account import facility_adapter as account_adapter
from .routers.account import models as account_models
from .routers.compute import facility_adapter as compute_adapter
from .routers.compute import models as compute_models
from .routers.facility import facility_adapter
from .routers.facility import models as facility_models
from .routers.filesystem import facility_adapter as filesystem_adapter
from .routers.filesystem import models as filesystem_models
from .routers.status import facility_adapter as status_adapter
from .routers.status import models as status_models
from .routers.task import facility_adapter as task_adapter
from .routers.task import models as task_models
from .types.models import Capability
from .types.scalars import AllocationUnit

DEMO_QUEUE_UPDATE_SECS = 5


def paginate_list(items, offset: int | None, limit: int | None):
    """Return a sliced items using offset and limit."""
    if offset is not None and offset > 0:
        items = items[offset:]
    if limit is not None and limit >= 0:
        items = items[:limit]
    return items


class PathSandbox:
    _base_temp_dir = None

    @classmethod
    def get_base_temp_dir(cls):
        if cls._base_temp_dir is None:
            # Create in system temp with a fixed name
            cls._base_temp_dir = os.path.join(os.getcwd(), "iri_sandbox")
            os.makedirs(cls._base_temp_dir, exist_ok=True)

            # create a test file
            with open(f"{cls._base_temp_dir}/test.txt", encoding="utf-8", mode="w") as f:
                f.write("hello world")
        return cls._base_temp_dir


def demo_uuid(kind: str, name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"demo:{kind}:{name}"))


def utc_now() -> datetime.datetime:
    """Return current UTC datetime timestamp"""
    return datetime.datetime.now(datetime.timezone.utc)


def utc_timestamp() -> int:
    """Return current UTC datetime timestamp as integer"""
    return int(utc_now().timestamp())


class DemoAdapter(
    status_adapter.FacilityAdapter, account_adapter.FacilityAdapter, compute_adapter.FacilityAdapter, filesystem_adapter.FacilityAdapter, task_adapter.FacilityAdapter, facility_adapter.FacilityAdapter
):
    def __init__(self):
        self.resources = []
        self.incidents = []
        self.events = []
        self.capabilities = {}
        self.user = account_models.User(id="gtorok", name="Gabor Torok", api_key="12345", client_ip="1.2.3.4")
        self.projects = []
        self.project_allocations = []
        self.user_allocations = []
        self.facility = {}
        self.locations = []
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
            "cpu": Capability(id=str(uuid.uuid4()), name="CPU Nodes", units=[AllocationUnit.node_hours]),
            "gpu": Capability(id=str(uuid.uuid4()), name="GPU Nodes", units=[AllocationUnit.node_hours]),
            "hpss": Capability(id=str(uuid.uuid4()), name="Tape Storage", units=[AllocationUnit.bytes, AllocationUnit.inodes]),
            "gpfs": Capability(id=str(uuid.uuid4()), name="GPFS Storage", units=[AllocationUnit.bytes, AllocationUnit.inodes]),
        }

        pm = status_models.Resource(
            id=str(uuid.uuid4()),
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
        )

        hpss = status_models.Resource(
            id=str(uuid.uuid4()),
            site_id=site1.id,
            group="hpss",
            name="hpss",
            description="hpss tape storage",
            capability_ids=[self.capabilities["hpss"].id],
            current_status=status_models.Status.up,
            last_modified=day_ago,
            resource_type=status_models.ResourceType.storage,
        )

        cfs = status_models.Resource(
            id=str(uuid.uuid4()),
            site_id=site1.id,
            group="cfs",
            name="cfs",
            description="cfs storage",
            capability_ids=[self.capabilities["gpfs"].id],
            current_status=status_models.Status.up,
            last_modified=day_ago,
            resource_type=status_models.ResourceType.storage,
        )

        login = status_models.Resource(
            id=str(uuid.uuid4()),
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
            id=str(uuid.uuid4()),
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
            id=str(uuid.uuid4()),
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

        # Populate site resource_ids based on which resources are at each site
        site1.resource_ids = [r.id for r in self.resources if r.site_id == site1.id]
        site2.resource_ids = [r.id for r in self.resources if r.site_id == site2.id]

        self.projects = [
            account_models.Project(
                id=str(uuid.uuid4()),
                name="Staff research project",
                description="Compute and storage allocation for staff research use",
                user_ids=["gtorok"],
            ),
            account_models.Project(
                id=str(uuid.uuid4()),
                name="Test project",
                description="Compute and storage allocation for testing use",
                user_ids=["gtorok"],
            ),
        ]

        for p in self.projects:
            for c in self.capabilities.values():
                pa = account_models.ProjectAllocation(
                    id=str(uuid.uuid4()),
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
                        id=str(uuid.uuid4()),
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
                id=str(uuid.uuid4()),
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
                        id=str(uuid.uuid4()),
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
            sites = [s for s in sites if name.lower() in s.name.lower()]

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

    async def get_events(
        self: "DemoAdapter",
        incident_id: str,
        offset: int,
        limit: int,
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
            [e for e in self.events if e.incident_id == incident_id],
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

    async def get_event(self: "DemoAdapter", incident_id: str, id_: str) -> status_models.Event:
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
        return "gtorok"

    async def get_user(
        self: "DemoAdapter",
        user_id: str,
        api_key: str,
        client_ip: str | None,
    ) -> account_models.User:
        if user_id != self.user.id:
            raise HTTPException(status_code=401, detail="User not found")
        if api_key != self.user.api_key:
            raise HTTPException(status_code=403, detail="Invalid API key")
        return self.user

    async def get_projects(self: "DemoAdapter", user: account_models.User) -> list[account_models.Project]:
        return self.projects

    async def get_project_allocations(
        self: "DemoAdapter",
        project: account_models.Project,
        user: account_models.User,
    ) -> list[account_models.ProjectAllocation]:
        return [pa for pa in self.project_allocations if pa.project_id == project.id]

    async def get_user_allocations(
        self: "DemoAdapter",
        user: account_models.User,
        project_allocation: account_models.ProjectAllocation,
    ) -> list[account_models.UserAllocation]:
        return [ua for ua in self.user_allocations if ua.project_allocation_id == project_allocation.id]

    async def submit_job(
        self: "DemoAdapter",
        resource: status_models.Resource,
        user: account_models.User,
        job_spec: compute_models.JobSpec,
    ) -> compute_models.Job:
        return compute_models.Job(
            id="job_123",
            status=compute_models.JobStatus(
                state=compute_models.JobState.NEW,
                time=utc_timestamp(),
                message="job submitted",
                exit_code=None,
                meta_data={"account": "account1"},
            ),
        )

    async def submit_job_script(
        self: "DemoAdapter",
        resource: status_models.Resource,
        user: account_models.User,
        job_script_path: str,
        args: list[str] = [],
    ) -> compute_models.Job:
        return compute_models.Job(
            id="job_123",
            status=compute_models.JobStatus(
                state=compute_models.JobState.NEW,
                time=utc_timestamp(),
                message="job submitted",
                exit_code=None,
                meta_data={"account": "account1"},
            ),
        )

    async def update_job(
        self: "DemoAdapter",
        resource: status_models.Resource,
        user: account_models.User,
        job_spec: compute_models.JobSpec,
        job_id: str,
    ) -> compute_models.Job:
        return compute_models.Job(
            id=job_id,
            status=compute_models.JobStatus(
                state=compute_models.JobState.ACTIVE,
                time=utc_timestamp(),
                message="job updated",
                exit_code=None,
                meta_data={"account": "account1"},
            ),
        )

    async def get_job(
        self: "DemoAdapter",
        resource: status_models.Resource,
        user: account_models.User,
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
        user: account_models.User,
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
        user: account_models.User,
        job_id: str,
    ) -> bool:
        # call slurm/etc. to cancel job
        return True

    def validate_path(self, path: str, allow_symlinks: bool = True) -> str:
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

        return filesystem_models.File(name=os.path.basename(rp), type=file_type, link_target=link_target, user=user, group=group, permissions=permissions, last_modified=last_modified, size=size)

    async def chmod(self: "DemoAdapter", resource: status_models.Resource, user: account_models.User, request_model: filesystem_models.PutFileChmodRequest) -> filesystem_models.PutFileChmodResponse:
        rp = self.validate_path(request_model.path)
        os.chmod(rp, int(request_model.mode, 8))
        return filesystem_models.PutFileChmodResponse(output=self._file(rp))

    async def chown(
        self: "DemoAdapter",
        resource: status_models.Resource,
        user: account_models.User,
        request_model: filesystem_models.PutFileChownRequest,
    ) -> filesystem_models.PutFileChownResponse:
        rp = self.validate_path(request_model.path)
        os.chown(rp, request_model.owner, request_model.group)
        return filesystem_models.PutFileChmodResponse(output=self._file(rp))

    async def ls(
        self: "DemoAdapter",
        resource: status_models.Resource,
        user: account_models.User,
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
    ) -> Tuple[Any, int]:
        args = [cmd]
        if file_bytes:
            args.append("-c")
            args.append(str(file_bytes))
        elif lines:
            args.append("-n")
            args.append(str(lines))
        rp = self.validate_path(path)
        args.append(rp)
        result = subprocess.run(args, capture_output=True, text=True)
        content = result.stdout
        return content, -len(content)

    async def head(
        self: "DemoAdapter",
        resource: status_models.Resource,
        user: account_models.User,
        path: str,
        file_bytes: int | None,
        lines: int | None,
        skip_trailing: bool,
    ) -> Tuple[Any, int]:
        return self._headtail("head", path, file_bytes, lines)

    async def tail(self: "DemoAdapter", resource: status_models.Resource, user: account_models.User, path: str, file_bytes: int | None, lines: int | None, skip_trailing: bool) -> Tuple[Any, int]:
        return self._headtail("tail", path, file_bytes, lines)

    async def view(self: "DemoAdapter", resource: status_models.Resource, user: account_models.User, path: str, size: int, offset: int) -> filesystem_models.GetViewFileResponse:
        rp = self.validate_path(path)
        result = subprocess.run(f"tail -c +{offset + 1} {rp} | head -c {size}", shell=True, capture_output=True, text=True)
        content = result.stdout
        return filesystem_models.GetViewFileResponse(
            output=content,
        )

    async def checksum(self: "DemoAdapter", resource: status_models.Resource, user: account_models.User, path: str) -> filesystem_models.GetFileChecksumResponse:
        rp = self.validate_path(path)
        result = subprocess.run(["sha256sum", rp], capture_output=True, text=True)
        checksum = result.stdout.split()[0]
        return filesystem_models.GetFileChecksumResponse(
            output=filesystem_models.FileChecksum(
                checksum=checksum,
            )
        )

    async def file(self: "DemoAdapter", resource: status_models.Resource, user: account_models.User, path: str) -> filesystem_models.GetFileTypeResponse:
        rp = self.validate_path(path)
        result = subprocess.run(["file", "-b", rp], capture_output=True, text=True)
        return filesystem_models.GetFileTypeResponse(
            output=result.stdout.strip(),
        )

    async def stat(self: "DemoAdapter", resource: status_models.Resource, user: account_models.User, path: str, dereference: bool) -> filesystem_models.GetFileStatResponse:
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
        user: account_models.User,
        path: str,
    ):
        rp = self.validate_path(path)
        if rp == PathSandbox.get_base_temp_dir():
            raise HTTPException(status_code=400, detail="Cannot delete sandbox")
        subprocess.run(["rm", "-rf", rp], check=True)
        return None

    async def mkdir(self: "DemoAdapter", resource: status_models.Resource, user: account_models.User, request_model: filesystem_models.PostMakeDirRequest) -> filesystem_models.PostMkdirResponse:
        rp = self.validate_path(request_model.path)
        args = ["mkdir"]
        if request_model.parent:
            args.append("-p")
        args.append(rp)
        subprocess.run(args, check=True)
        return filesystem_models.PostMkdirResponse(output=self._file(rp))

    async def symlink(
        self: "DemoAdapter", resource: status_models.Resource, user: account_models.User, request_model: filesystem_models.PostFileSymlinkRequest
    ) -> filesystem_models.PostFileSymlinkResponse:
        rp_src = self.validate_path(request_model.path)
        rp_dst = self.validate_path(request_model.link_path)
        subprocess.run(["ln", "-s", rp_src, rp_dst], check=True)
        return filesystem_models.PostFileSymlinkResponse(output=self._file(rp_dst))

    async def download(self: "DemoAdapter", resource: status_models.Resource, user: account_models.User, path: str) -> Any:
        rp = self.validate_path(path)
        raw_content = pathlib.Path(rp).read_bytes()

        if len(raw_content) > filesystem_adapter.OPS_SIZE_LIMIT:
            raise Exception("File to download is too large.")

        return base64.b64encode(raw_content).decode("utf-8")

    async def upload(self: "DemoAdapter", resource: status_models.Resource, user: account_models.User, path: str, content: str) -> None:
        rp = self.validate_path(path)
        if isinstance(content, bytes):
            pathlib.Path(rp).write_bytes(content)
        elif isinstance(content, str):
            pathlib.Path(rp).write_bytes(base64.b64decode(content))
        else:
            raise Exception(f"Don't know how to handle variable of type: {type(content)}")

    async def compress(
        self: "DemoAdapter", resource: status_models.Resource, user: account_models.User, request_model: filesystem_models.PostCompressRequest
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

    async def extract(self: "DemoAdapter", resource: status_models.Resource, user: account_models.User, request_model: filesystem_models.PostExtractRequest) -> filesystem_models.PostExtractResponse:
        src_rp = self.validate_path(request_model.path)
        dst_rp = self.validate_path(request_model.target_path)

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

    async def mv(self: "DemoAdapter", resource: status_models.Resource, user: account_models.User, request_model: filesystem_models.PostMoveRequest) -> filesystem_models.PostMoveResponse:
        src_rp = self.validate_path(request_model.path)
        dst_rp = self.validate_path(request_model.target_path)
        subprocess.run(["mv", src_rp, dst_rp], check=True)
        return filesystem_models.PostMoveResponse(output=self._file(dst_rp))

    async def cp(self: "DemoAdapter", resource: status_models.Resource, user: account_models.User, request_model: filesystem_models.PostCopyRequest) -> filesystem_models.PostCopyResponse:
        src_rp = self.validate_path(request_model.path)
        dst_rp = self.validate_path(request_model.target_path)
        args = ["cp"]
        if request_model.dereference:
            args.append("-L")
        args.append(src_rp)
        args.append(dst_rp)
        subprocess.run(args, check=True)
        return filesystem_models.PostCopyResponse(output=self._file(dst_rp))

    async def get_task(self: "DemoAdapter", user: account_models.User, task_id: str) -> task_models.Task | None:
        await DemoTaskQueue._process_tasks(self)
        return next((t for t in DemoTaskQueue.tasks if t.user.name == user.name and t.id == task_id), None)

    async def get_tasks(self: "DemoAdapter", user: account_models.User) -> list[task_models.Task]:
        await DemoTaskQueue._process_tasks(self)
        return [t for t in DemoTaskQueue.tasks if t.user.name == user.name]

    async def put_task(self: "DemoAdapter", user: account_models.User, resource: status_models.Resource, task: str) -> task_models.TaskSubmitResponse:
        await DemoTaskQueue._process_tasks(self)
        return DemoTaskQueue._create_task(user, resource, task)

    async def delete_task(self: "DemoAdapter", user: account_models.User, task_id: str) -> None:
        await DemoTaskQueue._process_tasks(self)
        for t in DemoTaskQueue.tasks:
            if t.user.name == user.name and t.id == task_id:
                t.status = task_models.TaskStatus.canceled
                t.result = None
                break


class DemoTask(BaseModel):
    id: str
    task: str
    resource: status_models.Resource
    user: account_models.User
    start: float
    status: task_models.TaskStatus = task_models.TaskStatus.pending
    result: str | None = None


class DemoTaskQueue:
    tasks = []

    @staticmethod
    async def _process_tasks(da: DemoAdapter):
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
                t.result = result
                t.status = status
            _tasks.append(t)
        DemoTaskQueue.tasks = _tasks

    @staticmethod
    def _create_task(user: account_models.User, resource: status_models.Resource, command: task_models.TaskCommand) -> task_models.TaskSubmitResponse:
        task_id = f"task_{len(DemoTaskQueue.tasks)}"
        DemoTaskQueue.tasks.append(DemoTask(id=task_id, task=command.model_dump_json(), user=user, resource=resource, start=utc_timestamp()))
        return task_models.TaskSubmitResponse(task_id=task_id)
