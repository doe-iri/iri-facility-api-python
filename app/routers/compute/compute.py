from typing import List, Annotated
from fastapi import HTTPException, Request, Depends, status, Form, Query
from . import models, facility_adapter
from .. import iri_router
from ..error_handlers import DEFAULT_RESPONSES
from ..status.status import router as status_router

router = iri_router.IriRouter(
    facility_adapter.FacilityAdapter,
    prefix="/compute",
    tags=["compute"],
)


@router.post(
    "/job/{resource_id:str}",
    dependencies=[Depends(router.current_user)],
    response_model=models.Job,
    response_model_exclude_unset=True,
    responses=DEFAULT_RESPONSES,
    operation_id="launchJob",
)
async def submit_job(
    resource_id: str,
    job_spec : models.JobSpec,
    request : Request,
    ):
    """
    Submit a job on a compute resource

    - **resource**: the name of the compute resource to use
    - **job_request**: a PSIJ job spec as defined <a href="https://exaworks.org/psij-python/docs/v/0.9.11/.generated/tree.html#jobspec">here</a>

    This command will attempt to submit a job and return its id.
    """
    user = await router.adapter.get_user(request.state.current_user_id, request.state.api_key, iri_router.get_client_ip(request))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # look up the resource (todo: maybe ensure it's available)
    resource = await status_router.adapter.get_resource(resource_id)

    # the handler can use whatever means it wants to submit the job and then fill in its id
    # see: https://exaworks.org/psij-python/docs/v/0.9.11/user_guide.html#submitting-jobs
    return await router.adapter.submit_job(resource, user, job_spec)


@router.post(
    "/job/script/{resource_id:str}",
    dependencies=[Depends(router.current_user)],
    response_model=models.Job,
    response_model_exclude_unset=True,
    responses=DEFAULT_RESPONSES,
    operation_id="launchJobScript",
)
async def submit_job_path(
    resource_id: str,
    job_script_path : str,
    request : Request,
    args : Annotated[List[str], Form()] = [],
    ):
    """
    Submit a job on a compute resource

    - **resource**: the name of the compute resource to use
    - **job_script_path**: path to the job script on the compute resource
    - **args**: optional arguments to the job script

    This command will attempt to submit a job and return its id.
    """
    user = await router.adapter.get_user(request.state.current_user_id, request.state.api_key, iri_router.get_client_ip(request))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # look up the resource (todo: maybe ensure it's available)
    resource = await status_router.adapter.get_resource(resource_id)

    # the handler can use whatever means it wants to submit the job and then fill in its id
    # see: https://exaworks.org/psij-python/docs/v/0.9.11/user_guide.html#submitting-jobs
    return await router.adapter.submit_job_script(resource, user, job_script_path, args)


@router.put(
    "/job/{resource_id:str}/{job_id:str}",
    dependencies=[Depends(router.current_user)],
    response_model=models.Job,
    response_model_exclude_unset=True,
    responses=DEFAULT_RESPONSES,
    operation_id="updateJob",
)
async def update_job(
    resource_id: str,
    job_id: str,
    job_spec : models.JobSpec,
    request : Request,
    ):
    """
    Update a previously submitted job for a resource.
    Note that only some attributes of a scheduled job can be updated. Check the facility documentation for details.

    - **resource**: the name of the compute resource to use
    - **job_request**: a PSIJ job spec as defined <a href="https://exaworks.org/psij-python/docs/v/0.9.11/.generated/tree.html#jobspec">here</a>

    """
    user = await router.adapter.get_user(request.state.current_user_id, request.state.api_key, iri_router.get_client_ip(request))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # look up the resource (todo: maybe ensure it's available)
    resource = await status_router.adapter.get_resource(resource_id)

    # the handler can use whatever means it wants to submit the job and then fill in its id
    # see: https://exaworks.org/psij-python/docs/v/0.9.11/user_guide.html#submitting-jobs
    return await router.adapter.update_job(resource, user, job_spec, job_id)


@router.get(
    "/status/{resource_id:str}/{job_id:str}",
    dependencies=[Depends(router.current_user)],
    response_model=models.Job,
    response_model_exclude_unset=True,
    responses=DEFAULT_RESPONSES,
    operation_id="getJobs",
)
async def get_job_status(
    resource_id : str,
    job_id : str,
    request : Request,
    historical : bool = False,
    include_spec: bool = False,
    ):
    """Get a job's status"""
    user = await router.adapter.get_user(request.state.current_user_id, request.state.api_key, iri_router.get_client_ip(request))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # look up the resource (todo: maybe ensure it's available)
    # This could be done via slurm (in the adapter) or via psij's "attach" (https://exaworks.org/psij-python/docs/v/0.9.11/user_guide.html#detaching-and-attaching-jobs)
    resource = await status_router.adapter.get_resource(resource_id)

    job = await router.adapter.get_job(resource, user, job_id, historical, include_spec)

    return job


@router.post(
    "/status/{resource_id:str}",
    dependencies=[Depends(router.current_user)],
    response_model=list[models.Job],
    response_model_exclude_unset=True,
    responses=DEFAULT_RESPONSES,
    operation_id="getJobs",
)
async def get_job_statuses(
    resource_id : str,
    request : Request,
    offset : int = Query(default=0, ge=0),
    limit : int = Query(default=100, le=10000),
    filters : dict[str, object] | None = None,
    historical : bool = False,
    include_spec: bool = False,
    ):
    """Get multiple jobs' statuses"""
    user = await router.adapter.get_user(request.state.current_user_id, request.state.api_key, iri_router.get_client_ip(request))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # look up the resource (todo: maybe ensure it's available)
    # This could be done via slurm (in the adapter) or via psij's "attach" (https://exaworks.org/psij-python/docs/v/0.9.11/user_guide.html#detaching-and-attaching-jobs)
    resource = await status_router.adapter.get_resource(resource_id)

    jobs = await router.adapter.get_jobs(resource, user, offset, limit, filters, historical, include_spec)

    return jobs


@router.delete(
    "/cancel/{resource_id:str}/{job_id:str}",
    dependencies=[Depends(router.current_user)],
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_model_exclude_unset=True,
    responses=DEFAULT_RESPONSES,
    operation_id="cancelJob",
)
async def cancel_job(
    resource_id : str,
    job_id : str,
    request : Request,
    ):
    """Cancel a job"""
    user = await router.adapter.get_user(request.state.current_user_id, request.state.api_key, iri_router.get_client_ip(request))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # look up the resource (todo: maybe ensure it's available)
    resource = await status_router.adapter.get_resource(resource_id)

    try:
        await router.adapter.cancel_job(resource, user, job_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Unable to cancel job: {str(exc)}") from exc
    return None
