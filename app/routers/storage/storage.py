from typing import Annotated

from fastapi import Depends, HTTPException, Query, Request, status as http_status

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
    "/locations/{resource_id}",
    summary="Get resolved storage locations for a resource",
    description=(
        "Return the resolved storage paths for the authenticated user at the specified "
        "resource. The response includes both placement and access semantics for that "
        "resource context, so it can be used in place of a separate mounts endpoint. "
        "Optionally filter by logical name, project/allocation, and intent.\n\n"
        "Intent semantics:\n"
        "- `staging`: excludes archive (too slow for staging workflows)\n"
        "- `long-term-storage`: returns only archive\n"
        "- `write`: excludes paths that are read-only in a compute-job context\n"
        "- `read`: no filtering\n"
    ),
    status_code=http_status.HTTP_200_OK,
    response_model=list[models.StorageInstance],
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
) -> list[models.StorageInstance]:
    resource = await status_router.adapter.get_resource(resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    locations = await router.adapter.get_locations(resource, user, logicalpath, project, allocation, intent)
    if logicalpath and not locations:
        raise HTTPException(status_code=404, detail=f"No storage location found for logical name '{logicalpath}'")
    return locations


@router.get(
    "/access-endpoints/{resource_id}",
    summary="Get data access endpoints for a storage resource",
    description=(
        "Return the list of data access endpoints for the given storage resource for the "
        "authenticated user. Each entry describes a protocol (Globus, XRootD, S3, ...) and "
        "the connection details needed to use it. Adapters may use the authenticated identity "
        "to include user-specific paths (e.g. home directories, per-user Globus collections). "
        "Protocol-specific fields (endpoint_id, uri, bucket, etc.) are present only for the "
        "relevant protocol; unrelated fields are omitted.\n\n"
        "Optionally filter by protocol and/or endpoint ID."
    ),
    status_code=http_status.HTTP_200_OK,
    response_model=list[models.AccessEndpoint],
    response_model_exclude_none=True,
    responses=DEFAULT_RESPONSES,
    operation_id="getStorageAccessEndpoints",
    openapi_extra=iri_meta_dict("in_development", "required"),
)
async def get_access_endpoints(
    resource_id: str,
    request: Request,
    protocol: Annotated[
        models.AccessProtocol | None,
        Query(description="Filter by access protocol"),
    ] = None,
    endpoint_id: Annotated[
        str | None,
        Query(description="Filter by endpoint ID"),
    ] = None,
    user: User = Depends(router.current_user),
    _forbid=Depends(forbidExtraQueryParams("protocol", "endpoint_id")),
) -> list[models.AccessEndpoint]:
    resource = await status_router.adapter.get_resource(resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    return await router.adapter.get_access_endpoints(resource, user, protocol, endpoint_id)
