from fastapi import APIRouter, HTTPException, Request, Depends
from . import models
from ... import auth


router = APIRouter(
    prefix="/account",
    tags=["account"],
)


@router.get(
    "/capabilities/{resource_id}",
    summary="Get the capabilities of a resource",
    description="Get a list of capabilities for a resource at this facility."
)
async def get_capabilities(
    resource_id: str,
    request : Request,
    ) -> list[models.Capability]:
    resource = await request.app.state.adapter.get_resource(resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    return await request.app.state.adapter.get_capabilities(resource)


@router.get(
    "/projects",
    dependencies=[Depends(auth.current_user)],
    summary="Get the projects of the current user",
    description="Get a list of projects for the currently authenticated user at this facility."
)
async def get_projects(
    request : Request,
    ) -> list[models.Project]:
    user = await request.app.state.adapter.get_user(request.state.current_user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Uer not found")
    return await request.app.state.adapter.get_projects(user)


@router.get(
    "/projects_allocations/{project_id}",
    dependencies=[Depends(auth.current_user)],
    summary="Get the allocations of the current user's projects",
    description="Get a list of allocations for the currently authenticated user's projects at this facility."
)
async def get_project_allocations(
    project_id: str,
    request : Request,
    ) -> list[models.ProjectAllocation]:
    user = await request.app.state.adapter.get_user(request.state.current_user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Uer not found")
    projects = await request.app.state.adapter.get_projects(user)
    project = next((p for p in projects if p.id == project_id))
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return await request.app.state.adapter.get_project_allocations(project)


@router.get(
    "/user_allocations/{project_id}",
    dependencies=[Depends(auth.current_user)],
    summary="Get the user allocations of the current user's projects",
    description="Get a list of user allocations for the currently authenticated user's projects at this facility."
)
async def get_user_allocations(
    project_id: str,
    request : Request,
    ) -> list[models.UserAllocation]:
    user = await request.app.state.adapter.get_user(request.state.current_user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Uer not found")
    projects = await request.app.state.adapter.get_projects(user)
    project = next((p for p in projects if p.id == project_id))
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    pas = await request.app.state.adapter.get_project_allocations(project)
    return await request.app.state.adapter.get_user_allocations(user, pas)
