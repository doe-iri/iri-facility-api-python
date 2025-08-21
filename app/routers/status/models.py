from pydantic import BaseModel, computed_field, Field
import datetime
import enum
from ... import config

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
    capability_ids: list[str]
    current_status: Status | None = Field("The current status comes from the status of the last event for this resource")


class Event(NamedResource):
    timestamp : datetime.datetime
    status : Status
    resource : Resource = Field(exclude=True) 


    @computed_field(description="The resource belonging to this event")
    @property
    def resource_uri(self) -> str:
        return f"/{config.API_URL}/resources/{self.resource.id}"
    

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


class Incident(NamedResource):
    status : Status
    resources : list[Resource] = Field(exclude=True)
    events : list[Event] = Field(exclude=True)
    start : datetime.datetime
    end : datetime.datetime | None
    type : IncidentType
    resolution : str


    @computed_field(description="The list of past events in this incident")
    @property
    def event_uris(self) -> list[str]:
        return [f"/{config.API_URL}/events/{e.id}" for e in self.events]


    @computed_field(description="The list of resources that may be impacted by this incident")
    @property
    def resource_uris(self) -> list[str]:
        return [f"/{config.API_URL}/resources/{r.id}" for r in self.resources]


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
