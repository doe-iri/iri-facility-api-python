from typing import Annotated

from fastapi import Depends, HTTPException, Query, Request, status

from ...types.http import forbidExtraQueryParams
from ...types.user import User
from .. import iri_router
from ..error_handlers import DEFAULT_RESPONSES
from ..iri_meta import iri_meta_dict
from ..status.status import router as status_router
from . import facility_adapter, models


router = iri_router.IriRouter(
    facility_adapter.FacilityAdapter,
    prefix="/storage",
    tags=["storage"],
)


@router.get(
    "/locations",
    summary="List supported logical filesystem names",
    description=(
        "Return the logical filesystem tier names supported at this facility "
        "(e.g. home, scratch, project, archive). Not every facility is required to "
        "support all names."
    ),
    status_code=status.HTTP_200_OK,
    response_model=list[models.LogicalName],
    responses=DEFAULT_RESPONSES,
    operation_id="getStorageLogicalNames",
    openapi_extra=iri_meta_dict("in_development", "optional"),
)
async def get_logical_names(
    request: Request,
    _forbid=Depends(forbidExtraQueryParams()),
) -> list[models.LogicalName]:
    return await router.adapter.get_logical_names()


@router.get(
    "/locations/{resource_id}",
    summary="Get resolved storage locations for a resource",
    description=(
        "Return the resolved storage paths for the authenticated user at the specified "
        "resource. Optionally filter by logical name, project/allocation, and intent.\n\n"
        "Intent semantics:\n"
        "- `staging`: excludes archive (too slow for staging workflows)\n"
        "- `long-term-storage`: returns only archive\n"
        "- `write`: excludes paths that are read-only in a compute-job context\n"
        "- `read`: no filtering\n"
    ),
    status_code=status.HTTP_200_OK,
    response_model=list[models.StorageLocation],
    responses=DEFAULT_RESPONSES,
    operation_id="getStorageLocations",
    openapi_extra=iri_meta_dict("in_development", "optional"),
)
async def get_locations(
    resource_id: str,
    request: Request,
    logicalpath: Annotated[
        models.LogicalName | None,
        Query(description="Filter to a specific logical filesystem tier"),
    ] = None,
    project: Annotated[
        str | None,
        Query(description="Project or allocation identifier for project-scoped paths"),
    ] = None,
    allocation: Annotated[
        str | None,
        Query(description="Allocation identifier (alternative to project)"),
    ] = None,
    intent: Annotated[
        models.StorageIntent | None,
        Query(description="Intended use to guide which locations are returned"),
    ] = None,
    user: User = Depends(router.current_user),
    _forbid=Depends(forbidExtraQueryParams("logicalpath", "project", "allocation", "intent")),
) -> list[models.StorageLocation]:
    resource = await status_router.adapter.get_resource(resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    locations = await router.adapter.get_locations(resource, user, logicalpath, project, allocation, intent)
    if logicalpath and not locations:
        raise HTTPException(status_code=404, detail=f"No storage location found for logical name '{logicalpath}'")
    return locations


@router.get(
    "/mounts/{resource_id}",
    summary="Get storage mount points for a resource",
    description=(
        "Return all storage volumes mounted at the specified resource, together with "
        "both in-job and outside-job (login / data-transfer node) access permissions.\n\n"
        "This answers: for a given resource in a given execution context "
        "(inside a running job, or on a login/DTN node), what volumes are mounted "
        "and with what read/write/execute permissions?"
    ),
    status_code=status.HTTP_200_OK,
    response_model=list[models.StorageMount],
    responses=DEFAULT_RESPONSES,
    operation_id="getStorageMounts",
    openapi_extra=iri_meta_dict("in_development", "optional"),
)
async def get_mounts(
    resource_id: str,
    request: Request,
    project: Annotated[
        str | None,
        Query(description="Project or allocation identifier for project-scoped paths"),
    ] = None,
    intent: Annotated[
        models.StorageIntent | None,
        Query(description="Intended use to filter returned mounts"),
    ] = None,
    user: User = Depends(router.current_user),
    _forbid=Depends(forbidExtraQueryParams("project", "intent")),
) -> list[models.StorageMount]:
    resource = await status_router.adapter.get_resource(resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    return await router.adapter.get_mounts(resource, user, project, intent)
