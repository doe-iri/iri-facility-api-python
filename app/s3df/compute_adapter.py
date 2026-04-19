"""
SLAC S3DF Slurm Compute Adapter for IRI Facility API

Auth model: IRI acts as JWT broker.
- IRI holds the shared jwt_hs256.key (same key mounted on slurmrestd).
- On every request IRI mints a short-lived HS256 JWT with `sun` = unix username.
- That JWT is forwarded as X-SLURM-USER-TOKEN to slurmrestd.
- slurmrestd validates it locally — no external auth call.

Required env vars:
  SLURM_REST_URL        e.g. http://slurmrestd:6820
  SLURM_JWT_KEY_PATH    path to jwt_hs256.key file (binary, 32 bytes)
  SLURM_JWT_LIFETIME    JWT lifetime in seconds (default: 3600)
"""

import os
import time
import logging
import base64
from typing import Optional
from ..routers.compute import models as compute_models
from ..routers.compute import facility_adapter as compute_adapter
import jwt  # PyJWT
from slurmrestd_client.api_client import ApiClient
from slurmrestd_client.api.slurm_api import SlurmApi
from slurmrestd_client.configuration import Configuration
from slurmrestd_client.exceptions import ApiException
from slurmrestd_client.models.slurm_v0041_post_job_submit_request import (
    SlurmV0041PostJobSubmitRequest,
)
from slurmrestd_client.models.slurm_v0041_post_job_submit_request_job import (
    SlurmV0041PostJobSubmitRequestJob,
)
from slurmrestd_client.models.slurm_v0041_post_job_submit_request_jobs_inner_time_limit import (
    SlurmV0041PostJobSubmitRequestJobsInnerTimeLimit,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Slurm → IRI state mapping
# ---------------------------------------------------------------------------
# Import JobState from wherever IRI defines it — adjust path as needed.
# from app.routers.compute.models import JobState, Job, JobStatus, JobSpec

SLURM_TO_IRI_STATE: dict = {
    "PENDING":     "QUEUED",
    "CONFIGURING": "NEW",
    "RUNNING":     "ACTIVE",
    "COMPLETED":   "COMPLETED",
    "CANCELLED":   "CANCELED",
    "FAILED":      "FAILED",
    "TIMEOUT":     "FAILED",
    "PREEMPTED":   "FAILED",
    "NODE_FAIL":   "FAILED",
    "SUSPENDED":   "CANCELED",
    "COMPLETING":  "ACTIVE",
    "STAGE_OUT":   "ACTIVE",
    "BOOT_FAIL":   "FAILED",
    "DEADLINE":    "FAILED",
    "OUT_OF_MEMORY": "FAILED",
    "RESIZING":    "ACTIVE",
    "REQUEUED":    "QUEUED",
    "REVOKED":     "FAILED",
    "SIGNALING":   "ACTIVE",
    "SPECIAL_EXIT": "FAILED",
    "STOPPED":     "CANCELED",
}


# ---------------------------------------------------------------------------
# JWT minting — IRI signs tokens using the shared key
# ---------------------------------------------------------------------------

def _load_jwt_key() -> bytes:
    """Load the HS256 shared key from environment variable."""
    key_str = os.environ.get("slurm_jwt")
    
    return base64.b64decode(key_str)

def _mint_slurm_jwt(unix_username: str) -> str:
    """
    Mint a short-lived HS256 JWT accepted by slurmrestd.

    Claims required by Slurm (https://slurm.schedmd.com/jwt.html):
      sun  — Slurm user name (unix username)
      exp  — expiry (unix timestamp)
      iat  — issued at
    """
    lifetime = int(os.environ.get("SLURM_JWT_LIFETIME", 3600))
    now = int(time.time())
    payload = {
        "sun": unix_username, #slurm rest user -> authenticated via jwt
        "exp": now + lifetime,
    }
    key = _load_jwt_key()
    token = jwt.encode(payload, key, algorithm="HS256")
    # PyJWT ≥2.0 returns str; older versions return bytes
    return token if isinstance(token, str) else token.decode()


# ---------------------------------------------------------------------------
# slurmrestd_client helpers
# ---------------------------------------------------------------------------

def _build_slurm_api(token: str) -> SlurmApi:
    url = os.environ.get("SLURM_REST_URL")
    if not url:
        raise RuntimeError("SLURM_REST_URL environment variable is not set")
    cfg = Configuration(host=url)
    cfg.verify_ssl = False #os.environ.get("SLURM_VERIFY_SSL", "true").lower() == "true"
    # api_key on the config is not used for header auth — we pass headers manually
    return SlurmApi(ApiClient(cfg))


def _auth_headers(unix_username: str, token: str) -> dict:
    return {
        "X-SLURM-USER-NAME": unix_username,
        "X-SLURM-USER-TOKEN": token,
    }


def _primary_state(job_state) -> str:
    """Extract the primary state string from whatever slurmrestd returns."""
    if isinstance(job_state, list):
        return job_state[0].upper() if job_state else "UNKNOWN"
    if isinstance(job_state, str):
        return job_state.upper()
    if hasattr(job_state, "value"):          # enum wrapper
        return str(job_state.value).upper()
    return str(job_state).upper()


def _map_state(slurm_state) -> str:
    primary = _primary_state(slurm_state)
    mapped = SLURM_TO_IRI_STATE.get(primary)
    if not mapped:
        logger.warning("Unknown Slurm state %r — mapping to FAILED", primary)
        return "FAILED"
    return mapped


def _job_from_slurm_info(job_info, include_spec: bool = False) -> dict:
    """
    Convert a slurmrestd job info object to a plain dict that IRI can
    deserialise into its Job model.  Adjust field names to match your
    exact IRI Job / JobStatus / JobSpec models.
    """
    state_str = _map_state(job_info.job_state)
    job_dict = {
        "id": str(job_info.job_id),
        "status": {
            "state": state_str,
        },
    }
    if include_spec:
        job_dict["spec"] = {
            "name": getattr(job_info, "name", None),
            "executable": getattr(job_info, "batch_script", None),
            "resources": {
                "node_count": getattr(job_info, "num_nodes", None),
            },
            "attributes": {
                "queue_name": getattr(job_info, "partition", None),
                "account": getattr(job_info, "account", None),
                "duration": (getattr(job_info, "time_limit", None) or 0) * 60,
            },
        }
    return job_dict


# ---------------------------------------------------------------------------
# The adapter
# ---------------------------------------------------------------------------

class SLACComputeAdapter(compute_adapter.FacilityAdapter):
    """
    IRI FacilityAdapter backed by SLAC S3DF slurmrestd.

    Implements every method called by the IRI compute router:
      submit_job, submit_job_script, update_job,
      get_job, get_jobs, cancel_job
    plus the user helper used by the router:
      get_user
    """

    # -- AuthenticatedAdapter methods ---------------------------------------

    async def get_current_user(self, api_key: str, client_ip: str | None) -> str:
        """Extract user ID from the Bearer token."""
        return api_key[7:] if api_key.startswith("Bearer ") else api_key

    async def get_user(self, user_id: str, api_key: str, client_ip: str | None):
        """
        Return a minimal user object.  The unix_username is the critical field —
        it becomes the `sun` claim in the Slurm JWT.

        In production, resolve user_id → unix username via your LDAP / IRIS lookup.
        For now we use user_id directly (adjust as needed).
        """
        class _User:
            def __init__(self, uid: str):
                self.id = uid                # IRI user id
                self.unix_username = uid     # maps to Slurm `sun` claim
                self.api_key = api_key

        return _User(user_id)

    # -- internal helpers ---------------------------------------------------

    def _get_slurm_context(self, user):
        """Return (api, headers) for the authenticated user."""
        unix_user = getattr(user, "unix_username", user.id)
        token = _mint_slurm_jwt(unix_user)
        api = _build_slurm_api(token)
        headers = _auth_headers(unix_user, token)
        return api, headers

    # -- submit_job ---------------------------------------------------------

    async def submit_job(self, resource, user, job_spec) -> dict:
        """
        POST /compute/job/{resource_id}
        Maps IRI JobSpec → SlurmV0041PostJobSubmitRequest and submits.
        """
        api, headers = self._get_slurm_context(user)

        # --- resource fields with safe defaults ---
        node_count = 1
        duration_mins = 60
        partition = None
        account = None
        environment = ["PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"]
        name = None
        executable = None
        cwd = None
        stdout = None
        stderr = None

        if job_spec:
            name = getattr(job_spec, "name", None)
            executable = getattr(job_spec, "executable", None)
            cwd = str(job_spec.directory) if getattr(job_spec, "directory", None) else None
            stdout = getattr(job_spec, "stdout_path", None)
            stderr = getattr(job_spec, "stderr_path", None)

            if getattr(job_spec, "environment", None):
                environment = [f"{k}={v}" for k, v in job_spec.environment.items()]

            resources = getattr(job_spec, "resources", None)
            if resources:
                node_count = getattr(resources, "node_count", 1) or 1

            attributes = getattr(job_spec, "attributes", None)
            if attributes:
                duration = getattr(attributes, "duration", None)
                if duration is not None:
                    # duration may be timedelta or int (seconds)
                    total_secs = (
                        duration.total_seconds()
                        if hasattr(duration, "total_seconds")
                        else float(duration)
                    )
                    duration_mins = max(1, int(total_secs // 60))
                partition = getattr(attributes, "queue_name", None)
                account = getattr(attributes, "account", None)

        slurm_job = SlurmV0041PostJobSubmitRequestJob(
            nodes=str(node_count),
            time_limit=SlurmV0041PostJobSubmitRequestJobsInnerTimeLimit(
                set=True, number=duration_mins
            ),
            name=name,
            script=executable,
            partition=partition,
            account=account,
            environment=environment,
            current_working_directory=cwd,
            standard_output=stdout,
            standard_error=stderr,
        )

        # Job array support: e.g. custom_attributes={"array": "0-19"}
        if job_spec:
            attributes = getattr(job_spec, "attributes", None)
            if attributes:
                ca = getattr(attributes, "custom_attributes", {}) or {}
                if "array" in ca:
                    slurm_job.array = ca["array"]

        req = SlurmV0041PostJobSubmitRequest(job=slurm_job)

        try:
            resp = api.slurm_v0041_post_job_submit(
                slurm_v0041_post_job_submit_request=req,
                _headers=headers,
            )
            logger.info("Job submitted: job_id=%s", resp.job_id)
            return {
                "id": str(resp.job_id),
                "status": {"state": "QUEUED"},
            }
        except ApiException as exc:
            logger.error("submit_job failed: %s", exc)
            raise RuntimeError(f"Slurm submission failed: {exc}") from exc

    # -- submit_job_script --------------------------------------------------

    async def submit_job_script(
        self, resource, user, job_script_path: str, args: list = []
    ) -> dict:
        """
        POST /compute/job/script/{resource_id}

        job_script_path is a path on the COMPUTE NODE filesystem.
        We build a minimal wrapper script that executes it.
        slurmrestd requires the script to be inlined in the request body.
        """
        if args:
            arg_str = " ".join(str(a) for a in args)
            script = f"#!/bin/bash\n{job_script_path} {arg_str}\n"
        else:
            script = f"#!/bin/bash\n{job_script_path}\n"

        # Reuse submit_job with a minimal spec carrying just the script
        class _MinimalSpec:
            executable = script
            name = os.path.basename(job_script_path)
            directory = None
            stdout_path = None
            stderr_path = None
            environment = None
            resources = None
            attributes = None

        return await self.submit_job(resource, user, _MinimalSpec())

    # -- update_job ---------------------------------------------------------

    async def update_job(self, resource, user, job_spec, job_id: str) -> dict:
        """
        PUT /compute/job/{resource_id}/{job_id}

        slurmrestd v0.0.41 exposes POST /slurm/v0.0.41/job/{job_id} for updates.
        Only a subset of fields can be changed after submission (time_limit,
        priority, partition, etc.).  Fields not supported by Slurm are ignored.
        """
        api, headers = self._get_slurm_context(user)

        update_fields: dict = {}

        if job_spec:
            attributes = getattr(job_spec, "attributes", None)
            if attributes:
                duration = getattr(attributes, "duration", None)
                if duration is not None:
                    total_secs = (
                        duration.total_seconds()
                        if hasattr(duration, "total_seconds")
                        else float(duration)
                    )
                    update_fields["time_limit"] = max(1, int(total_secs // 60))
                partition = getattr(attributes, "queue_name", None)
                if partition:
                    update_fields["partition"] = partition

        try:
            # v0041 job update endpoint
            api.slurm_v0041_post_job(job_id, update_fields, _headers=headers)
        except ApiException as exc:
            logger.warning("update_job %s: slurmrestd returned %s", job_id, exc)
            # Non-fatal: fall through and return current status

        return await self.get_job(resource, user, job_id)

    # -- get_job ------------------------------------------------------------

    async def get_job(
        self,
        resource,
        user,
        job_id: str,
        historical: bool = False,
        include_spec: bool = False,
    ) -> dict:
        """GET /compute/status/{resource_id}/{job_id}"""
        api, headers = self._get_slurm_context(user)

        try:
            # Try active jobs first
            resp = api.slurm_v0041_get_job(job_id, _headers=headers)
            if resp and resp.jobs:
                return _job_from_slurm_info(resp.jobs[0], include_spec)
        except ApiException as exc:
            if exc.status != 414:
                raise RuntimeError(f"Slurm get_job failed: {exc}") from exc

        if historical:
            # Fall back to job history endpoint
            try:
                resp = api.slurm_v0041_get_job_history(job_id, _headers=headers)
                if resp and resp.jobs:
                    return _job_from_slurm_info(resp.jobs[0], include_spec)
            except ApiException as exc:
                raise RuntimeError(f"Slurm job history failed: {exc}") from exc

        raise RuntimeError(f"Job {job_id} not found")

    # -- get_jobs -----------------------------------------------------------

    async def get_jobs(
        self,
        resource,
        user,
        offset: int = 0,
        limit: int = 100,
        filters: Optional[dict] = None,
        historical: bool = False,
        include_spec: bool = False,
    ) -> list:
        """POST /compute/status/{resource_id}"""
        api, headers = self._get_slurm_context(user)

        try:
            resp = api.slurm_v0041_get_jobs(_headers=headers)
        except ApiException as exc:
            raise RuntimeError(f"Slurm get_jobs failed: {exc}") from exc

        jobs = resp.jobs or []

        # Basic server-side filtering by unix username (jobs owned by this user)
        unix_user = getattr(user, "unix_username", user.id)
        jobs = [j for j in jobs if getattr(j, "user_name", None) == unix_user]

        # Apply caller-supplied filters (key = Slurm job_info attribute name)
        if filters:
            for key, value in filters.items():
                jobs = [j for j in jobs if getattr(j, key, None) == value]

        # Pagination
        jobs = jobs[offset: offset + limit]

        return [_job_from_slurm_info(j, include_spec) for j in jobs]

    # -- cancel_job ---------------------------------------------------------

    async def cancel_job(self, resource, user, job_id: str) -> bool:
        """DELETE /compute/cancel/{resource_id}/{job_id}"""
        api, headers = self._get_slurm_context(user)

        try:
            api.slurm_v0041_delete_job(job_id, _headers=headers)
            logger.info("Cancelled job %s", job_id)
            return True
        except ApiException as exc:
            raise RuntimeError(f"Slurm cancel failed for job {job_id}: {exc}") from exc