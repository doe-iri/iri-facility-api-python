from fastapi import Request, HTTPException, Depends, Query
from .. import iri_router
from ..error_handlers import DEFAULT_RESPONSES
from .import models, facility_adapter


router = iri_router.IriRouter(
    facility_adapter.FacilityAdapter,
    prefix="/facility",
    tags=["facility"],
)

@router.get("", responses=DEFAULT_RESPONSES, operation_id="getFacility")
async def get_facility(
    request: Request,
    modified_since: iri_router.StrictDateTime = Query(default=None),
    _forbid = Depends(iri_router.forbidExtraQueryParams("modified_since")),
    ) -> models.Facility:
    """Get facility information"""
    return await router.adapter.get_facility(modified_since=modified_since)

@router.get("/sites", responses=DEFAULT_RESPONSES, operation_id="getSites")
async def list_sites(
    request: Request,
    modified_since: iri_router.StrictDateTime = Query(default=None),
    name: str = Query(default=None, min_length=1),
    offset: int = Query(default=0, ge=0, le=1000),
    limit: int = Query(default=100, ge=0, le=1000),
    short_name: str = Query(default=None, min_length=1),
    _forbid = Depends(iri_router.forbidExtraQueryParams("modified_since", "name", "offset", "limit", "short_name")),
    )-> list[models.Site]:
    """List sites"""
    return await router.adapter.list_sites(modified_since=modified_since, name=name, offset=offset, limit=limit, short_name=short_name)

@router.get("/sites/{site_id}", responses=DEFAULT_RESPONSES, operation_id="getSite")
async def get_site(
    request: Request,
    site_id: str,
    modified_since: iri_router.StrictDateTime = Query(default=None),
    _forbid = Depends(iri_router.forbidExtraQueryParams("modified_since")),
    )-> models.Site:
    """Get site by ID"""
    return await router.adapter.get_site(site_id=site_id, modified_since=modified_since)

@router.get("/sites/{site_id}/location", responses=DEFAULT_RESPONSES, operation_id="getLocationBySite")
async def get_site_location(
    request : Request,
    site_id: str,
    modified_since: iri_router.StrictDateTime = Query(default=None),
    _forbid = Depends(iri_router.forbidExtraQueryParams("modified_since")),
    )-> models.Location:
    """Get site location by site ID"""
    return await router.adapter.get_site_location(site_id=site_id, modified_since=modified_since)

@router.get("/locations", responses=DEFAULT_RESPONSES, operation_id="getLocations")
async def list_locations(
    request : Request,
    modified_since: iri_router.StrictDateTime = Query(default=None),
    name: str = Query(default=None, min_length=1),
    offset: int = Query(default=0, ge=0, le=1000),
    limit: int = Query(default=100, ge=0, le=1000),
    short_name: str = Query(default=None, min_length=1),
    country_name: str = Query(default=None, min_length=1),
    _forbid = Depends(iri_router.forbidExtraQueryParams("modified_since", "name", "offset", "limit", "short_name", "country_name")),
    )-> list[models.Location]:
    """List locations"""
    return await router.adapter.list_locations(modified_since=modified_since, name=name, offset=offset, limit=limit, short_name=short_name, country_name=country_name)

@router.get("/locations/{location_id}", responses=DEFAULT_RESPONSES, operation_id="getLocation")
async def get_location(
    request : Request,
    location_id: str,
    modified_since: iri_router.StrictDateTime = Query(default=None),
    _forbid = Depends(iri_router.forbidExtraQueryParams("modified_since")),
    )-> models.Location:
    """Get location by ID"""
    return await router.adapter.get_location(location_id=location_id, modified_since=modified_since)