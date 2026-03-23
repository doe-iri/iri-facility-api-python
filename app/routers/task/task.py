from fastapi import Request, HTTPException, Depends
from ...types.user import User
from .. import iri_router
from ..error_handlers import DEFAULT_RESPONSES
from ..iri_meta import iri_meta_dict
from . import models, facility_adapter

router = iri_router.IriRouter(
    facility_adapter.FacilityAdapter,
    prefix="/task",
    tags=["task"],
)


@router.get(
    "/{task_id:str}",
    response_model_exclude_unset=True,
    responses=DEFAULT_RESPONSES,
    operation_id="getTask",
    openapi_extra=iri_meta_dict("beta", "required")
)
async def get_task(
    request: Request,
    task_id: str,
    user: User = Depends(router.current_user)
) -> models.Task:
    """Get a task"""
    task = await router.adapter.get_task(user=user, task_id=task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return task


@router.get("",
            dependencies=[Depends(router.current_user)],
            response_model_exclude_unset=True, responses=DEFAULT_RESPONSES,
            operation_id="getTasks",
            openapi_extra=iri_meta_dict("beta", "required"))
@router.get("/", responses=DEFAULT_RESPONSES, operation_id="getTasksWithSlash", include_in_schema=False)

async def get_tasks(
    request: Request,
    user: User = Depends(router.current_user)
) -> list[models.Task]:
    """Get all tasks"""
    return await router.adapter.get_tasks(user=user)

@router.delete(
    "/{task_id:str}",
    dependencies=[Depends(router.current_user)],
    responses=DEFAULT_RESPONSES,
    operation_id="deleteTask",
    openapi_extra=iri_meta_dict("beta", "required")
)
async def delete_task(
    request: Request,
    task_id: str,
    user: User = Depends(router.current_user)
) -> str:
    """Delete a task"""
    await router.adapter.delete_task(user=user, task_id=task_id)
    return f"Task {task_id} deleted successfully"