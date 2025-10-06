from fastapi import HTTPException, Request, Query
import datetime
from . import models, facility_adapter
from .. import iri_router

router = iri_router.IriRouter(
    facility_adapter.FacilityAdapter,
    prefix="/status",
    tags=["status"],
)

@router.get(
    "/resources",
    summary="Get all resources",
    description="Get a list of all resources at this facility. You can optionally filter the returned list by specifying attribtes."
)
async def get_resources(
    request : Request,
    name : str | None = None,
    description : str | None = None,
    group : str | None = None,
    offset : int | None = 0,
    limit : int | None = 100,
    modified_since : datetime.datetime | None = None,
    resource_type : models.ResourceType | None = None,
    ) -> list[models.Resource]:
    return await router.adapter.get_resources(offset, limit, name, description, group, modified_since, resource_type)


@router.get(
    "/resources/{resource_id}",
    summary="Get a specific resource",
    description="Get a specific resource for a given id"
)
async def get_resource(
    request : Request, 
    resource_id : str
    ) -> models.Resource:
    item = await router.adapter.get_resource(resource_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.get(
    "/incidents",
    summary="Get all incidents without their events",
    description="Get a list of all incidents. Each incident will be returned without its events.  You can optionally filter the returned list by specifying attribtes."
)
async def get_incidents(
    request : Request,
    name : str | None = None,
    description : str | None = None,
    status : models.Status | None = None,
    type : models.IncidentType | None = None,
    from_ : datetime.datetime | None = Query(alias="from", default=None),
    time_ : datetime.datetime | None = Query(alias="time", default=None),
    to : datetime.datetime | None = None,
    modified_since : datetime.datetime | None = None,
    resource_id : str | None = None,
    offset : int | None = 0,
    limit : int | None = 100,
    ) -> list[models.Incident]:
    return await router.adapter.get_incidents(offset, limit, name, description, status, type, from_, to, time_, modified_since, resource_id)


@router.get(
    "/incidents/{incident_id}",
    summary="Get a specific incident and its events",
    description="Get a specific incident for a given id. The incident's events will also be included.  You can optionally filter the returned list by specifying attribtes."
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
    description="Get a list of all events in this incident.  You can optionally filter the returned list by specifying attribtes."
)
async def get_events(
    request : Request,
    incident_id : str,
    resource_id : str | None = None,
    name : str | None = None,
    description : str | None = None,
    status : models.Status | None = None,
    from_ : datetime.datetime | None = Query(alias="from", default=None),
    time_ : datetime.datetime | None = Query(alias="time", default=None),
    to : datetime.datetime | None = None,
    offset : int | None = 0,
    limit : int | None = 100,
    modified_since : datetime.datetime | None = None,
    ) -> list[models.Event]:
    return await router.adapter.get_events(incident_id, offset, limit, resource_id, name, description, status, from_, to, time_, modified_since)


@router.get(
    "/incidents/{incident_id}/events/{event_id}",
    summary="Get a specific event",
    description="Get a specific event for a given id"
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
