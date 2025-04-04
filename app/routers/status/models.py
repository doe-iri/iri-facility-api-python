from pydantic import BaseModel
import datetime
import enum


class Link(BaseModel):
    rel : str
    href : str


class Status(enum.Enum):
    up = "up"
    down = "down"
    degraded = "degraded"
    unknown = "unknown"


class NamedResource(BaseModel):
    id : str
    name : str
    description : str


    @staticmethod
    def find_by_id(a, id):
        return next((r for r in a if r.id == id), None)


    @staticmethod
    def find(a, name, description):
        if name:
            a = [aa for aa in a if aa.name == name]
        if description:
            a = [aa for aa in a if description in aa.description]
        return a


class Resource(NamedResource):
    pass


class Event(NamedResource):
    timestamp : datetime.datetime
    status : Status
    resource : Resource

    @staticmethod
    def find(
        events : list,
        name : str | None = None,
        description : str | None = None,
        status : Status | None = None,
        start : datetime.datetime | None = None,
        end : datetime.datetime | None = None
    ) -> list:
        events = NamedResource.find(events, name, description)
        if status:
            events = [e for e in events if e.status == status]
        if start:
            events = [e for e in events if e.timestamp >= start]
        if end:
            events = [e for e in events if e.timestamp < end]
        return events


class IncidentType(enum.Enum):
    planned = "planned"
    unplanned = "unplanned"


# incident w/o the events
class IncidentResponse(NamedResource):
    status : Status
    start : datetime.datetime
    end : datetime.datetime
    type : IncidentType
    resolution : str


class Incident(NamedResource):
    status : Status
    events : list[Event]
    start : datetime.datetime
    end : datetime.datetime
    type : IncidentType
    resolution : str


    def find(
        incidents : list,
        name : str | None = None,
        description : str | None = None,
        status : Status | None = None,
        type : IncidentType | None = None,
        start : datetime.datetime | None = None,
        end : datetime.datetime | None = None
    ) -> list:
        incidents = NamedResource.find(incidents, name, description)
        if status:
            incidents = [e for e in incidents if e.status == status]
        if type:
            incidents = [e for e in incidents if e.type == type]
        if start:
            incidents = [e for e in incidents if e.timestamp >= start]
        if end:
            incidents = [e for e in incidents if e.timestamp < end]
        return incidents
