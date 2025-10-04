from fastapi import HTTPException, Request, Depends
from . import models, facility_adapter
from .. import iri_router
import psij

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
)
async def submit_job(
    resource_id: str,
    job_request : models.JobRequest,
    request : Request,
    ):
    """
    Submit a job on a compute resource

    - **resource**: the name of the compute resource to use
    - **job_request**: a PSIJ job spec as defined <a href="https://exaworks.org/psij-python/docs/v/0.9.11/.generated/tree.html#jobspec">here</a>
    
    This command will attempt to submit a job and return its id.
    """
    user = await router.adapter.get_user(request, request.state.current_user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Uer not found")
    
    # convert BaseModel to psij.JobSpec
    # it would be ideal to just specify psij.JobSpec as the model for job_request, 
    # but fastapi wants a pydantic object so we duplicate it ¯\_(ツ)_/¯
    d = job_request.model_dump()
    # expand the sub-models (these are converted to dict-s)
    for k,v in { 
        "resources": psij.ResourceSpecV1, 
        "attributes": psij.JobAttributes }.items():
        if k in d:
            d[k] = v(**d[k])    
    job = psij.Job(spec=psij.JobSpec(**d))
    
    # look up the resource (todo: maybe ensure it's available)
    resource = await router.adapter.get_resource(resource_id)

    # the handler can use whatever means it wants to submit the job and then fill in its id
    # see: https://exaworks.org/psij-python/docs/v/0.9.11/user_guide.html#submitting-jobs
    await router.adapter.submit_job(resource, user, job)
    
    return models.Job(job_id=job.native_id)


@router.get(
    "/command/{resource_id:str}/{job_id:str}",
    dependencies=[Depends(router.current_user)],
    response_model=models.CommandResult,
    response_model_exclude_unset=True,
)
async def get_job_status(
    resource_id : str,
    job_id : str,
    request : Request,
    ):
    """Get a job's status"""
    user = await router.adapter.get_user(request, request.state.current_user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Uer not found")

    # look up the resource (todo: maybe ensure it's available)
    # This could be done via slurm (in the adapter) or via psij's "attach" (https://exaworks.org/psij-python/docs/v/0.9.11/user_guide.html#detaching-and-attaching-jobs)
    resource = await router.adapter.get_resource(resource_id)

    job = await router.adapter.get_job(resource, user, job_id)

    return models.CommandResult(status=job.status.state.name)


@router.delete(
    "/command/{resource_id:str}/{job_id:str}",
    dependencies=[Depends(router.current_user)],
    response_model=models.CommandResult,
    response_model_exclude_unset=True,
)
async def cancel_job(
    resource_id : str,
    job_id : str,
    request : Request,
    ):
    """Cancel a job"""
    user = await router.adapter.get_user(request, request.state.current_user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Uer not found")
    
    # look up the resource (todo: maybe ensure it's available)
    resource = await router.adapter.get_resource(resource_id)

    job = await router.adapter.get_job(resource, user, job_id)

    cr = models.CommandResult(status="OK")
    try:
        await router.adapter.cancel_job(resource, user, job)
    except Exception as exc:
        cr.status = "ERROR"
        cr.result = str(exc)
    return cr
