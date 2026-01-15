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
