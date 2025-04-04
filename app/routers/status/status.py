from fastapi import APIRouter, HTTPException, Request
import datetime
from . import models

router = APIRouter(
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
    description : str | None = None
    ) -> list[models.Resource]:
    return models.Resource.find(request.app.state.resources, name, description)


@router.get(
    "/resources/{id}",
    summary="Get a specific resource",
    description="Get a specific resource for a given id"
)
async def get_resource(
    request : Request, 
    id : str
    ) -> models.Resource:
    item = models.Resource.find_by_id(request.app.state.resources, id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.get(
    "/events/resource/{resource_id}",
    summary="Get all events for a resource",
    description="Get a list of all events for the given resource.  You can optionally filter the returned list by specifying attribtes."
)
async def get_events_resource(
    request : Request,
    resource_id : str,
    name : str | None = None,
    description : str | None = None,
    status : models.Status | None = None,
    start : datetime.datetime | None = None,
    end : datetime.datetime | None = None
    ) -> list[models.Event]:
    events = [e for e in request.app.state.events if e.resource.id == resource_id]
    return models.Event.find(events, name, description, status, start, end)


@router.get(
    "/events",
    summary="Get all events",
    description="Get a list of all events.  You can optionally filter the returned list by specifying attribtes."
)
async def get_events(
    request : Request,
    name : str | None = None,
    description : str | None = None,
    status : models.Status | None = None,
    start : datetime.datetime | None = None,
    end : datetime.datetime | None = None
    ) -> list[models.Event]:
    return models.Event.find(request.app.state.events, name, description, status, start, end)


@router.get(
    "/events/{id}",
    summary="Get a specific event",
    description="Get a specific event for a given id"
)
async def get_event(
    request : Request,
    id : str
    ) -> models.Event:
    item = models.Event.find_by_id(request.app.state.events, id)
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
    start : datetime.datetime | None = None,
    end : datetime.datetime | None = None
    ) -> list[models.IncidentResponse]:
    return models.Incident.find(request.app.state.incidents, name, description, status, type, start, end)


@router.get(
    "/incidents/{id}",
    summary="Get a specific incident and its events",
    description="Get a specific incident for a given id. The incident's events will also be included.  You can optionally filter the returned list by specifying attribtes."
)
async def get_incidents(
    request : Request,
    id : str
    ) -> models.Incident:
    item = models.Incident.find_by_id(request.app.state.incidents, id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item
