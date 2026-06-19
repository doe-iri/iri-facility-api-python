"""Compute resource API router"""

from fastapi import Depends, Header, Query, Request, status

from ...idempotency import build_body_hash, build_cache_key, run_with_idempotency
from ...types.http import forbidExtraQueryParams
from ...types.scalars import StrictHTTPBool
from ...types.user import User
from .. import iri_router
from ..error_handlers import DEFAULT_RESPONSES
from ..iri_meta import iri_meta_dict
from ..status.status import router as status_router, models as status_models
from . import facility_adapter, models

router = iri_router.IriRouter(
    facility_adapter.FacilityAdapter,
    prefix="/compute",
    tags=["compute"],
)


@router.get(
    "/resources",
    response_model=list[status_models.Resource],
    response_model_exclude_unset=True,
    responses=DEFAULT_RESPONSES,
    operation_id="getComputeResources",
    openapi_extra=iri_meta_dict("planned"),
)
async def get_resources(
    request: Request,
    _forbid=Depends(forbidExtraQueryParams()),
):
    """Get a list of resources that can be used in this endpoint"""
    return await status_router.adapter.get_resources_for_endpoint(status_models.Endpoint.compute)


@router.post(
    "/job/{resource_id:str}",
    response_model=models.Job,
    response_model_exclude_unset=True,
    responses=DEFAULT_RESPONSES,
    operation_id="launchJob",
    openapi_extra=iri_meta_dict("production", "required")
)
async def submit_job(
    resource_id: str,
    job_spec: models.JobSpec,
    request: Request,
    user: User = Depends(router.current_user),
    project_name: str | None = Depends(router.iri_header_project),
    _forbid=Depends(forbidExtraQueryParams()),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    """
    Submit a job on a compute resource

    - **resource**: the name of the compute resource to use
    - **job_request**: a PSIJ job spec as defined <a href="https://exaworks.org/psij-python/docs/v/0.9.11/.generated/tree.html#jobspec">here</a>
    - **project/account resolution**:
      The effective project/account for the submission must be supplied in exactly one place:
      `job_spec.attributes.account` or the trusted `X-IRI-Facility-Project` request header.
      If the forwarded header is present and valid, IRI treats its value as the effective facility-native project/account
      for the downstream submission and related job metadata. If both sources are present, or neither is present,
      the request is rejected with `400 Bad Request`.
    - **Idempotency-Key**: optional client-generated UUID. A retry with the same key and body
      returns the original response without re-submitting the job. Same key with a different body
      returns 422. An in-flight duplicate returns 409.

    This command will attempt to submit a job and return its id.
    """
    resource = await status_router.adapter.get_resource(resource_id)

    if idempotency_key:
        return await run_with_idempotency(
            request.app.state.idempotency_store,
            build_cache_key(user.id, idempotency_key, "submit_job"),
            build_body_hash(job_spec.model_dump()),
            lambda: router.adapter.submit_job(resource=resource, user=user, job_spec=job_spec),
        )
    return await router.adapter.submit_job(resource=resource, user=user, job_spec=job_spec)


@router.put(
    "/job/{resource_id:str}/{job_id:str}",
    response_model=models.Job,
    response_model_exclude_unset=True,
    responses=DEFAULT_RESPONSES,
    operation_id="updateJob",
    openapi_extra=iri_meta_dict("production", "required")
)
async def update_job(
    resource_id: str,
    job_id: str,
    job_spec: models.JobSpec,
    request: Request,
    user: User = Depends(router.current_user),
    project_name: str | None = Depends(router.iri_header_project),
    _forbid=Depends(forbidExtraQueryParams()),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    """
    Update a previously submitted job for a resource.
    Note that only some attributes of a scheduled job can be updated. Check the facility documentation for details.

    - **resource**: the name of the compute resource to use
    - **job_request**: a PSIJ job spec as defined <a href="https://exaworks.org/psij-python/docs/v/0.9.11/.generated/tree.html#jobspec">here</a>
    - **project/account resolution**:
      The effective project/account for the update must be supplied in exactly one place:
      `job_spec.attributes.account` or the trusted `X-IRI-Facility-Project` request header.
      If the forwarded header is present and valid, IRI treats its value as the effective facility-native project/account
      for downstream update handling and job metadata. If both sources are present, or neither is present,
      the request is rejected with `400 Bad Request`.
    - **Idempotency-Key**: optional client-generated UUID. Same semantics as submit_job.
    """
    resource = await status_router.adapter.get_resource(resource_id)

    if idempotency_key:
        return await run_with_idempotency(
            request.app.state.idempotency_store,
            build_cache_key(user.id, idempotency_key, f"update_job:{job_id}"),
            build_body_hash(job_spec.model_dump()),
            lambda: router.adapter.update_job(resource=resource, user=user, job_spec=job_spec, job_id=job_id),
        )
    return await router.adapter.update_job(resource=resource, user=user, job_spec=job_spec, job_id=job_id)


@router.get(
    "/status/{resource_id:str}/{job_id:str}",
    response_model=models.Job,
    response_model_exclude_unset=True,
    responses=DEFAULT_RESPONSES,
    operation_id="getJob",
    openapi_extra=iri_meta_dict("production", "required")
)
async def get_job_status(
    resource_id: str,
    job_id: str,
    request: Request,
    user: User = Depends(router.current_user),
    historical: StrictHTTPBool | None = Query(default=True, description="Whether to include historical jobs. Defaults to true"),
    include_spec: StrictHTTPBool | None = Query(default=False, description="Whether to include the job specification. Defaults to false"),
    _forbid=Depends(forbidExtraQueryParams("historical", "include_spec")),
):
    """Get a job's status"""
    # look up the resource (todo: maybe ensure it's available)
    # This could be done via slurm (in the adapter) or via psij's "attach" (https://exaworks.org/psij-python/docs/v/0.9.11/user_guide.html#detaching-and-attaching-jobs)
    resource = await status_router.adapter.get_resource(resource_id)

    job = await router.adapter.get_job(resource=resource, user=user, job_id=job_id, historical=historical, include_spec=include_spec)

    return job


@router.post(
    "/status/{resource_id:str}",
    response_model=list[models.Job],
    response_model_exclude_unset=True,
    responses=DEFAULT_RESPONSES,
    operation_id="getJobs",
    openapi_extra=iri_meta_dict("production", "required")
)
async def get_job_statuses(
    resource_id: str,
    request: Request,
    user: User = Depends(router.current_user),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=0, le=1000),
    filters: dict[str, object] | None = None,
    historical: StrictHTTPBool | None = Query(default=False, description="Whether to include historical jobs. Defaults to false"),
    include_spec: StrictHTTPBool | None = Query(default=False, description="Whether to include the job specification. Defaults to false"),
    _forbid=Depends(forbidExtraQueryParams("offset", "limit", "filters", "historical", "include_spec")),
):
    """Get multiple jobs' statuses"""
    # look up the resource (todo: maybe ensure it's available)
    # This could be done via slurm (in the adapter) or via psij's "attach" (https://exaworks.org/psij-python/docs/v/0.9.11/user_guide.html#detaching-and-attaching-jobs)
    resource = await status_router.adapter.get_resource(resource_id)

    jobs = await router.adapter.get_jobs(resource=resource, user=user, offset=offset, limit=limit, filters=filters, historical=historical, include_spec=include_spec)

    return jobs


@router.delete(
    "/cancel/{resource_id:str}/{job_id:str}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_model_exclude_unset=True,
    responses=DEFAULT_RESPONSES,
    operation_id="cancelJob",
    openapi_extra=iri_meta_dict("production", "required")
)
async def cancel_job(
    resource_id: str,
    job_id: str,
    request: Request,
    user: User = Depends(router.current_user),
    _forbid=Depends(forbidExtraQueryParams()),
):
    """Cancel a job"""
    # look up the resource (todo: maybe ensure it's available)
    resource = await status_router.adapter.get_resource(resource_id)

    await router.adapter.cancel_job(resource=resource, user=user, job_id=job_id)

    return None
