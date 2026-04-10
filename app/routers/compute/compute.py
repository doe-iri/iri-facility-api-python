"""Compute resource API router"""

from fastapi import Depends, HTTPException, Query, Request, status

from ...types.http import forbidExtraQueryParams
from ...types.scalars import StrictHTTPBool
from ...types.user import User
from .. import iri_router
from ..error_handlers import DEFAULT_RESPONSES
from ..iri_meta import iri_meta_dict
from ..status.status import router as status_router
from . import facility_adapter, models

router = iri_router.IriRouter(
    facility_adapter.FacilityAdapter,
    prefix="/compute",
    tags=["compute"],
)


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
    _forbid=Depends(forbidExtraQueryParams()),
):
    """
    Submit a job on a compute resource

    - **resource**: the name of the compute resource to use
    - **job_request**: a PSIJ job spec as defined <a href="https://exaworks.org/psij-python/docs/v/0.9.11/.generated/tree.html#jobspec">here</a>

    This command will attempt to submit a job and return its id.
    """
    # look up the resource (todo: maybe ensure it's available)
    resource = await status_router.adapter.get_resource(resource_id)

    # the handler can use whatever means it wants to submit the job and then fill in its id
    # see: https://exaworks.org/psij-python/docs/v/0.9.11/user_guide.html#submitting-jobs
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
    _forbid=Depends(forbidExtraQueryParams()),
):
    """
    Update a previously submitted job for a resource.
    Note that only some attributes of a scheduled job can be updated. Check the facility documentation for details.

    - **resource**: the name of the compute resource to use
    - **job_request**: a PSIJ job spec as defined <a href="https://exaworks.org/psij-python/docs/v/0.9.11/.generated/tree.html#jobspec">here</a>

    """
    # look up the resource (todo: maybe ensure it's available)
    resource = await status_router.adapter.get_resource(resource_id)

    # the handler can use whatever means it wants to submit the job and then fill in its id
    # see: https://exaworks.org/psij-python/docs/v/0.9.11/user_guide.html#submitting-jobs
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


# ---------------------------------------------------------------------------
# Workflow endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/workflow/{resource_id:str}",
    response_model=models.Workflow,
    response_model_exclude_unset=True,
    status_code=status.HTTP_201_CREATED,
    responses=DEFAULT_RESPONSES,
    operation_id="createWorkflow",
    openapi_extra=iri_meta_dict("production", "required"),
)
async def create_workflow(
    resource_id: str,
    spec: models.WorkflowSpec,
    request: Request,
    user: User = Depends(router.current_user),
    _forbid=Depends(forbidExtraQueryParams()),
):
    """
    Create a new workflow on a compute resource.

    Provisions the filesystem layout and launches leader + worker processes
    inside a scheduler allocation.
    """
    resource = await status_router.adapter.get_resource(resource_id)
    return await router.adapter.create_workflow(resource=resource, user=user, spec=spec)


@router.post(
    "/workflow/{resource_id:str}/{workflow_id:str}/dispatch",
    response_model=models.WorkflowTaskSpec,
    response_model_exclude_unset=True,
    status_code=status.HTTP_201_CREATED,
    responses=DEFAULT_RESPONSES,
    operation_id="dispatchWorkflowTask",
    openapi_extra=iri_meta_dict("production", "required"),
)
async def dispatch_task(
    resource_id: str,
    workflow_id: str,
    task_spec: models.WorkflowTaskSpec,
    request: Request,
    user: User = Depends(router.current_user),
    _forbid=Depends(forbidExtraQueryParams()),
):
    """
    Dispatch a task into an existing workflow.

    The task JSON is written to ``tasks/New/`` on the shared filesystem.
    The leader will move it to ``Pending/`` once all dependencies are satisfied.
    """
    resource = await status_router.adapter.get_resource(resource_id)
    return await router.adapter.dispatch_task(resource=resource, user=user, workflow_id=workflow_id, task_spec=task_spec)


@router.get(
    "/workflow/{resource_id:str}/{workflow_id:str}",
    response_model=models.WorkflowStatus,
    response_model_exclude_unset=True,
    responses=DEFAULT_RESPONSES,
    operation_id="getWorkflow",
    openapi_extra=iri_meta_dict("production", "required"),
)
async def get_workflow(
    resource_id: str,
    workflow_id: str,
    request: Request,
    user: User = Depends(router.current_user),
    _forbid=Depends(forbidExtraQueryParams()),
):
    """
    Get the current status of a workflow.

    Returns task counts per lifecycle state and active worker/leader heartbeats.
    """
    resource = await status_router.adapter.get_resource(resource_id)
    return await router.adapter.get_workflow(resource=resource, user=user, workflow_id=workflow_id)
