from fastapi import Request, HTTPException, Depends
from .. import iri_router
from ..error_handlers import DEFAULT_RESPONSES
from . import models, facility_adapter

router = iri_router.IriRouter(
    facility_adapter.FacilityAdapter,
    prefix="/task",
    tags=["task"],
)


@router.get(
    "/{task_id:str}",
    dependencies=[Depends(router.current_user)],
    response_model_exclude_unset=True,
    responses=DEFAULT_RESPONSES,
    operation_id="getTask",
)
async def get_task(
    request: Request,
    task_id: str,
) -> models.Task:
    """Get a task"""
    user = await router.adapter.get_user(user_id=request.state.current_user_id, api_key=request.state.api_key, client_ip=iri_router.get_client_ip(request))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    task = await router.adapter.get_task(user=user, task_id=task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return task


@router.get(
    "",
    dependencies=[Depends(router.current_user)],
    response_model_exclude_unset=True,
    responses=DEFAULT_RESPONSES,
    operation_id="getTasks",
)
async def get_tasks(
    request: Request,
) -> list[models.Task]:
    """Get all tasks"""
    user = await router.adapter.get_user(user_id=request.state.current_user_id, api_key=request.state.api_key, client_ip=iri_router.get_client_ip(request))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return await router.adapter.get_tasks(user=user)
