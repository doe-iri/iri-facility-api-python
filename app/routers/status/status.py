from typing import Annotated, List, Optional

from fastapi import Depends, HTTPException, Query, Request

from ...types.http import forbidExtraQueryParams
from ...types.scalars import AllocationUnit, StrictDateTime
from .. import iri_router
from ..error_handlers import DEFAULT_RESPONSES
from . import facility_adapter, models

router = iri_router.IriRouter(
    facility_adapter.FacilityAdapter,
    prefix="/status",
    tags=["status"],
)

@router.get(
    "/resources",
    summary="Get all resources",
    description="Get a list of all resources at this facility. You can optionally filter the returned list by specifying attribtes.",
    responses=DEFAULT_RESPONSES,
    operation_id="getResources",
    response_model_exclude_none=True
)
async def get_resources(
    request : Request,
    name : str = Query(default=None, min_length=1),
    description : str = Query(default=None, min_length=1),
    group : str  = Query(default=None, min_length=1),
    offset : int = Query(default=0, ge=0, le=1000),
    limit : int = Query(default=100, ge=0, le=1000),
    modified_since: StrictDateTime = Query(default=None),
    resource_type: models.ResourceType = Query(default=None),
    current_status: models.Status = Query(default=None),
    capability: List[AllocationUnit] = Query(default=None, min_length=1),
    _forbid = Depends(forbidExtraQueryParams("name", "description", "group", "offset", "limit", "modified_since", "resource_type", "current_status", "capability", multiParams={"capability"})),
    ) -> list[models.Resource]:
    return await router.adapter.get_resources(offset=offset, limit=limit, name=name, description=description, group=group, modified_since=modified_since,
                                              resource_type=resource_type, current_status=current_status, capability=capability)


@router.get(
    "/resources/{resource_id}",
    summary="Get a specific resource",
    description="Get a specific resource for a given id",
    responses=DEFAULT_RESPONSES,
    operation_id="getResource",
)
async def get_resource(
    request : Request,
    resource_id : str,
    ) -> models.Resource:
    item = await router.adapter.get_resource(resource_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.get( 
    "/incidents",
    summary="Get all incidents without their events",
    description="Get a list of all incidents. Each incident will be returned without its events.  You can optionally filter the returned list by specifying attributes.",
    responses=DEFAULT_RESPONSES,
    operation_id="getIncidents",
)
async def get_incidents(
    request : Request,
    name : str = Query(default=None, min_length=1),
    description : str = Query(default=None, min_length=1),
    status : models.Status = Query(default=None),
    type_:  models.IncidentType = Query(alias="type", default=None),
    from_: StrictDateTime = Query(alias="from", default=None),
    time_ : StrictDateTime = Query(alias="time", default=None),
    to : StrictDateTime = Query(default=None),
    modified_since : StrictDateTime = Query(default=None),
    resource_id : str = Query(default=None, min_length=1),
    offset : int = Query(default=0, ge=0, le=1000),
    limit : int = Query(default=100, ge=0, le=1000),
    resolution : models.Resolution = Query(default=None),
    _forbid = Depends(forbidExtraQueryParams("name", "description", "status", "type", "from", "to", "time", "modified_since", "resource_id",
                                             "offset", "limit", "resolution", "resource_uris", "event_uris", multiParams={"resource_uris", "event_uris"})),
    ) -> list[models.Incident]:
    return await router.adapter.get_incidents(offset=offset, limit=limit, name=name, description=description, status=status, type_=type_, from_=from_, to=to,
                                              time_=time_, modified_since=modified_since, resource_id=resource_id, resolution=resolution)


@router.get(
    "/incidents/{incident_id}",
    summary="Get a specific incident and its events",
    description="Get a specific incident for a given id. The incident's events will also be included.  You can optionally filter the returned list by specifying attributes.",
    responses=DEFAULT_RESPONSES,
    operation_id="getIncident",

)
async def get_incident(
    request : Request,
    incident_id : str
    ) -> models.Incident:
    item = await router.adapter.get_incident(incident_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.get(
    "/incidents/{incident_id}/events",
    summary="Get all events for an incident",
    description="Get a list of all events in this incident.  You can optionally filter the returned list by specifying attribtes.",
    responses=DEFAULT_RESPONSES,
    operation_id="getEventsByIncident",
)
async def get_events(
    request : Request,
    incident_id : str,
    resource_id : str = Query(default=None, min_length=1),
    name : str = Query(default=None, min_length=1),
    description : str = Query(default=None, min_length=1),
    status : models.Status = Query(default=None),
    from_: StrictDateTime = Query(alias="from", default=None),
    time_ : StrictDateTime = Query(alias="time", default=None),
    to : StrictDateTime = Query(default=None),
    modified_since : StrictDateTime = Query(default=None),
    offset : int = Query(default=0, ge=0, le=1000),
    limit : int = Query(default=100, ge=0, le=1000),
    _forbid = Depends(forbidExtraQueryParams("resource_id", "name", "description", "status", "from", "to", "time", "modified_since", "offset", "limit")),
    ) -> list[models.Event]:
    return await router.adapter.get_events(incident_id, offset=offset, limit=limit, resource_id=resource_id, name=name, description=description, status=status,
                                           from_=from_, to=to, time_=time_, modified_since=modified_since)


@router.get(
    "/incidents/{incident_id}/events/{event_id}",
    summary="Get a specific event",
    description="Get a specific event for a given id",
    responses=DEFAULT_RESPONSES,
    operation_id="getEventByIncident",
)
async def get_event(
    request : Request,
    incident_id : str,
    event_id : str
    ) -> models.Event:
    item = await router.adapter.get_event(incident_id, event_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item
