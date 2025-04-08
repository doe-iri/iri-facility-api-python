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
    return await request.app.state.adapter.get_resources(name, description)


@router.get(
    "/resources/{id}",
    summary="Get a specific resource",
    description="Get a specific resource for a given id"
)
async def get_resource(
    request : Request, 
    id : str
    ) -> models.Resource:
    item = await request.app.state.adapter.get_resource(id)
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
    return await request.app.state.adapter.get_events_resource(resource_id, name, description, status, start, end)


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
    return await request.app.state.adapter.get_events(name, description, status, start, end)


@router.get(
    "/events/{id}",
    summary="Get a specific event",
    description="Get a specific event for a given id"
)
async def get_event(
    request : Request,
    id : str
    ) -> models.Event:
    item = await request.app.state.adapter.get_event(id)
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
    return await request.app.state.adapter.get_incidents(name, description, status, type, start, end)


@router.get(
    "/incidents/{id}",
    summary="Get a specific incident and its events",
    description="Get a specific incident for a given id. The incident's events will also be included.  You can optionally filter the returned list by specifying attribtes."
)
async def get_incident(
    request : Request,
    id : str
    ) -> models.Incident:
    item = await request.app.state.adapter.get_incident(id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item
