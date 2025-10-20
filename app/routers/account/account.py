from fastapi import HTTPException, Request, Depends
from . import models, facility_adapter
from .. import iri_router


router = iri_router.IriRouter(
    facility_adapter.FacilityAdapter,
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
    return await router.adapter.get_capabilities()


@router.get(
    "/capabilities/{capability_id}",
    summary="Get a single capability",
    description="Get a single capability at this facility."
)
async def get_capability(
    capability_id : str,
    request : Request,
    ) -> models.Capability:
    caps = await router.adapter.get_capabilities()
    cc = next((c for c in caps if c.id == capability_id), None)
    if not cc:
        raise HTTPException(status_code=404, detail="Capability not found")
    return cc


@router.get(
    "/projects",
    dependencies=[Depends(router.current_user)],
    summary="Get the projects of the current user",
    description="Get a list of projects for the currently authenticated user at this facility."
)
async def get_projects(
    request : Request,
    ) -> list[models.Project]:
    user = await router.adapter.get_user(request.state.current_user_id, request.state.api_key)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return await router.adapter.get_projects(user)


@router.get(
    "/projects/{project_id}",
    dependencies=[Depends(router.current_user)],
    summary="Get a single project",
    description="Get a single project at this facility."
)
async def get_project(
    project_id : str,
    request : Request,
    ) -> models.Project:
    user = await router.adapter.get_user(request.state.current_user_id, request.state.api_key)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    projects = await router.adapter.get_projects(user)
    pp = next((p for p in projects if p.id == project_id), None)
    if not pp:
        raise HTTPException(status_code=404, detail="Project not found")
    return pp


@router.get(
    "/projects/{project_id}/project_allocations",
    dependencies=[Depends(router.current_user)],
    summary="Get the allocations of the current user's projects",
    description="Get a list of allocations for the currently authenticated user's projects at this facility."
)
async def get_project_allocations(
    project_id: str,
    request : Request,
    ) -> list[models.ProjectAllocation]:
    user = await router.adapter.get_user(request.state.current_user_id, request.state.api_key)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    projects = await router.adapter.get_projects(user)
    project = next((p for p in projects if p.id == project_id), None)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return await router.adapter.get_project_allocations(project, user)


@router.get(
    "/projects/{project_id}/project_allocations/{project_allocation_id}",
    dependencies=[Depends(router.current_user)],
    summary="Get a single project allocation",
    description="Get a single project allocation at this facility for this user."
)
async def get_project_allocation(
    project_id: str,
    project_allocation_id : str,
    request : Request,
    ) -> models.ProjectAllocation:
    user = await router.adapter.get_user(request.state.current_user_id, request.state.api_key)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    projects = await router.adapter.get_projects(user)
    project = next((p for p in projects if p.id == project_id), None)
    pas = await router.adapter.get_project_allocations(project, user)
    pa = next((pa for pa in pas if pa.id == project_allocation_id), None)
    if not pa:
        raise HTTPException(status_code=404, detail="Project allocation not found")
    return pa


@router.get(
    "/projects/{project_id}/project_allocations/{project_allocation_id}/user_allocations",
    dependencies=[Depends(router.current_user)],
    summary="Get the user allocations of the current user's projects",
    description="Get a list of user allocations for the currently authenticated user's projects at this facility."
)
async def get_user_allocations(
    project_id: str,
    project_allocation_id : str,
    request : Request,
    ) -> list[models.UserAllocation]:
    user = await router.adapter.get_user(request.state.current_user_id, request.state.api_key)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    projects = await router.adapter.get_projects(user)
    project = next((p for p in projects if p.id == project_id), None)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    pas = await router.adapter.get_project_allocations(project, user)
    pa = next((pa for pa in pas if pa.id == project_allocation_id), None)
    if not pa:
        raise HTTPException(status_code=404, detail="Project allocation not found")
    return await router.adapter.get_user_allocations(user, pa)


@router.get(
    "/projects/{project_id}/project_allocations/{project_allocation_id}/user_allocations/{user_allocation_id}",
    dependencies=[Depends(router.current_user)],
    summary="Get a user allocation of the current user's projects",
    description="Get a user allocation for the currently authenticated user's projects at this facility."
)
async def get_user_allocation(
    project_id: str,
    project_allocation_id : str,
    user_allocation_id : str,
    request : Request,
    ) -> models.UserAllocation:
    user = await router.adapter.get_user(request.state.current_user_id, request.state.api_key)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    projects = await router.adapter.get_projects(user)
    project = next((p for p in projects if p.id == project_id), None)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    pas = await router.adapter.get_project_allocations(project, user)
    pa = next((pa for pa in pas if pa.id == project_allocation_id), None)
    if not pa:
        raise HTTPException(status_code=404, detail="Project allocation not found")
    uas = await router.adapter.get_user_allocations(user, pa)
    ua = next((ua for ua in uas if ua.id == user_allocation_id), None)
    if not ua:
        raise HTTPException(status_code=404, detail="User allocation not found")
    return ua
