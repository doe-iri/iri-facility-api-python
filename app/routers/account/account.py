from fastapi import Depends, HTTPException, Query, Request

from ...types.http import forbidExtraQueryParams
from ...types.models import Capability
from ...types.scalars import StrictDateTime
from ...types.user import User
from .. import iri_router
from ..error_handlers import DEFAULT_RESPONSES
from ..iri_meta import iri_meta_dict
from . import facility_adapter, models

router = iri_router.IriRouter(
    facility_adapter.FacilityAdapter,
    prefix="/account",
    tags=["account"],
)


@router.get(
    "/capabilities",
    summary="Get the list of capabilities",
    description="Get a list of capabilities at this facility.",
    responses=DEFAULT_RESPONSES,
    operation_id="getCapabilities",
    response_model_exclude_none=True,
    openapi_extra=iri_meta_dict("production", "required")
)
async def get_capabilities(
    request: Request,
    name: str | None = Query(default=None, min_length=1),
    modified_since: StrictDateTime = Query(default=None),
    offset: int = Query(default=0, ge=0, le=1000),
    limit: int = Query(default=100, ge=0, le=1000),
    _forbid=Depends(forbidExtraQueryParams("name", "modified_since", "offset", "limit")),
) -> list[Capability]:
    return await router.adapter.get_capabilities(name=name, modified_since=modified_since, offset=offset, limit=limit)


@router.get(
    "/capabilities/{capability_id}",
    summary="Get a single capability",
    description="Get a single capability at this facility.",
    responses=DEFAULT_RESPONSES,
    operation_id="getCapability",
    openapi_extra=iri_meta_dict("production", "required")
)
async def get_capability(
    capability_id: str,
    request: Request,
    modified_since: StrictDateTime = Query(default=None),
    _forbid=Depends(forbidExtraQueryParams("modified_since")),
) -> Capability:
    caps = await router.adapter.get_capabilities(name=None, modified_since=modified_since, offset=0, limit=100)
    cc = next((c for c in caps if c.id == capability_id), None)
    if not cc:
        raise HTTPException(status_code=404, detail="Capability not found")
    return cc


@router.get(
    "/projects",
    summary="Get the projects of the current user",
    description="Get a list of projects for the currently authenticated user at this facility.",
    responses=DEFAULT_RESPONSES,
    operation_id="getProjects",
    openapi_extra=iri_meta_dict("production", "required")
)
async def get_projects(
    request: Request,
    user: User = Depends(router.current_user),
    _forbid=Depends(forbidExtraQueryParams()),
) -> list[models.Project]:
    return await router.adapter.get_projects(user)


@router.get(
    "/projects/{project_id}",
    summary="Get a single project",
    description="Get a single project at this facility.",
    responses=DEFAULT_RESPONSES,
    operation_id="getProject",
    openapi_extra=iri_meta_dict("production", "required")
)
async def get_project(
    project_id: str,
    request: Request,
    user: User = Depends(router.current_user),
    _forbid=Depends(forbidExtraQueryParams()),
) -> models.Project:
    projects = await router.adapter.get_projects(user=user)
    pp = next((p for p in projects if p.id == project_id), None)
    if not pp:
        raise HTTPException(status_code=404, detail="Project not found")
    return pp


@router.get(
    "/projects/{project_id}/project_allocations",
    summary="Get the allocations of the current user's projects",
    description="Get a list of allocations for the currently authenticated user's projects at this facility.",
    responses=DEFAULT_RESPONSES,
    operation_id="getProjectAllocationsByProject",
    openapi_extra=iri_meta_dict("production", "required")
)
async def get_project_allocations(
    project_id: str,
    request: Request,
    user: User = Depends(router.current_user),
    _forbid=Depends(forbidExtraQueryParams()),
) -> list[models.ProjectAllocation]:
    projects = await router.adapter.get_projects(user=user)
    project = next((p for p in projects if p.id == project_id), None)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return await router.adapter.get_project_allocations(project=project, user=user)


@router.get(
    "/projects/{project_id}/project_allocations/{project_allocation_id}",
    summary="Get a single project allocation",
    description="Get a single project allocation at this facility for this user.",
    responses=DEFAULT_RESPONSES,
    operation_id="getProjectAllocationByProject",
    openapi_extra=iri_meta_dict("production", "required")
)
async def get_project_allocation(
    project_id: str,
    project_allocation_id: str,
    request: Request,
    user: User = Depends(router.current_user),
    _forbid=Depends(forbidExtraQueryParams()),
) -> models.ProjectAllocation:
    projects = await router.adapter.get_projects(user=user)
    project = next((p for p in projects if p.id == project_id), None)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    pas = await router.adapter.get_project_allocations(project=project, user=user)
    pa = next((pa for pa in pas if pa.id == project_allocation_id), None)
    if not pa:
        raise HTTPException(status_code=404, detail="Project allocation not found")
    return pa


@router.get(
    "/projects/{project_id}/project_allocations/{project_allocation_id}/user_allocations",
    summary="Get the user allocations of the current user's projects",
    description="Get a list of user allocations for the currently authenticated user's projects at this facility.",
    responses=DEFAULT_RESPONSES,
    operation_id="getUserAllocationsByProjectAllocation",
    openapi_extra=iri_meta_dict("production", "required")
)
async def get_user_allocations(
    project_id: str,
    project_allocation_id: str,
    request: Request,
    _forbid=Depends(forbidExtraQueryParams()),
    user: User = Depends(router.current_user),
) -> list[models.UserAllocation]:
    projects = await router.adapter.get_projects(user=user)
    project = next((p for p in projects if p.id == project_id), None)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    pas = await router.adapter.get_project_allocations(project=project, user=user)
    pa = next((pa for pa in pas if pa.id == project_allocation_id), None)
    if not pa:
        raise HTTPException(status_code=404, detail="Project allocation not found")
    return await router.adapter.get_user_allocations(user=user, project_allocation=pa)


@router.get(
    "/projects/{project_id}/project_allocations/{project_allocation_id}/user_allocations/{user_allocation_id}",
    summary="Get a user allocation of the current user's projects",
    description="Get a user allocation for the currently authenticated user's projects at this facility.",
    responses=DEFAULT_RESPONSES,
    operation_id="getUserAllocationByProjectAllocation",
    openapi_extra=iri_meta_dict("production", "required")
)
async def get_user_allocation(
    project_id: str,
    project_allocation_id: str,
    user_allocation_id: str,
    request: Request,
    _forbid=Depends(forbidExtraQueryParams()),
    user: User = Depends(router.current_user),
) -> models.UserAllocation:
    projects = await router.adapter.get_projects(user=user)
    project = next((p for p in projects if p.id == project_id), None)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    pas = await router.adapter.get_project_allocations(project=project, user=user)
    pa = next((pa for pa in pas if pa.id == project_allocation_id), None)
    if not pa:
        raise HTTPException(status_code=404, detail="Project allocation not found")
    uas = await router.adapter.get_user_allocations(user=user, project_allocation=pa)
    ua = next((ua for ua in uas if ua.id == user_allocation_id), None)
    if not ua:
        raise HTTPException(status_code=404, detail="User allocation not found")
    return ua
