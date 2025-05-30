from fastapi import APIRouter, HTTPException, Request, Depends
from . import models
from ... import auth


router = APIRouter(
    prefix="/account",
    tags=["account"],
)


@router.get(
    "/capabilities",
    summary="Get the list of capabilities",
    description="Get a list of capabilities at this facility."
)
async def get_capabilities(
    request : Request,
    ) -> list[models.Capability]:
    return await request.app.state.adapter.get_capabilities()


@router.get(
    "/projects",
    dependencies=[Depends(auth.current_user)],
    summary="Get the projects of the current user",
    description="Get a list of projects for the currently authenticated user at this facility."
)
async def get_projects(
    request : Request,
    ) -> list[models.Project]:
    user = await request.app.state.adapter.get_user(request, request.state.current_user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Uer not found")
    return await request.app.state.adapter.get_projects(request, user)


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
    user = await request.app.state.adapter.get_user(request, request.state.current_user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Uer not found")
    projects = await request.app.state.adapter.get_projects(request, user)
    project = next((p for p in projects if p.id == project_id))
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return await request.app.state.adapter.get_project_allocations(request, project)


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
    user = await request.app.state.adapter.get_user(request, request.state.current_user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Uer not found")
    projects = await request.app.state.adapter.get_projects(request, user)
    project = next((p for p in projects if p.id == project_id))
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    pas = await request.app.state.adapter.get_project_allocations(request, project)
    return await request.app.state.adapter.get_user_allocations(request, user, pas)
