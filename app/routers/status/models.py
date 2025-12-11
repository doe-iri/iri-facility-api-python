import datetime
import enum
from pydantic import BaseModel, computed_field, Field
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
    last_modified : datetime.datetime


    @staticmethod
    def find_by_id(a, id, allow_name: bool|None=False):
        # Find a resource by its id.
        # If allow_name is True, the id parameter can also match the resource's name.
        return next((r for r in a if r.id == id or (allow_name and r.name == id)), None)


    @staticmethod
    def find(a, name, description, modified_since):
        def normalize(dt: datetime) -> datetime:
            # Convert naive datetimes into UTC-aware versions
            if dt.tzinfo is None:
                return dt.replace(tzinfo=datetime.timezone.utc)
            return dt
        if name:
            a = [aa for aa in a if aa.name == name]
        if description:
            a = [aa for aa in a if description in aa.description]
        if modified_since:
            if modified_since.tzinfo is None:
                modified_since = modified_since.replace(tzinfo=datetime.timezone.utc)
            a = [aa for aa in a if normalize(aa.last_modified) >= modified_since]
        return a


class ResourceType(enum.Enum):
    website = "website"
    service = "service"
    compute = "compute"
    system = "system"
    storage = "storage"
    network = "network"
    unknown = "unknown"


class Resource(NamedResource):
    capability_ids: list[str] = Field(exclude=True)
    group: str | None
    current_status: Status | None = Field("The current status comes from the status of the last event for this resource")
    resource_type: ResourceType


    @computed_field(description="The url of this object")
    @property
    def self_uri(self) -> str:
        return f"{config.API_URL_ROOT}{config.API_PREFIX}{config.API_URL}/status/resources/{self.id}"


    @computed_field(description="The list of past events in this incident")
    @property
    def capability_uris(self) -> list[str]:
        return [f"{config.API_URL_ROOT}{config.API_PREFIX}{config.API_URL}/account/capabilities/{e}" for e in self.capability_ids]


    @staticmethod
    def find(resources, name, description, group, modified_since, resource_type):
        a = NamedResource.find(resources, name, description, modified_since)
        if group:
            a = [aa for aa in a if aa.group == group]
        if resource_type:
            a = [aa for aa in a if aa.resource_type == resource_type]
        return a


class Event(NamedResource):
    occurred_at : datetime.datetime
    status : Status
    resource_id : str = Field(exclude=True)
    incident_id : str | None = Field(exclude=True, default=None)


    @computed_field(description="The url of this object")
    @property
    def self_uri(self) -> str:
        return f"{config.API_URL_ROOT}{config.API_PREFIX}{config.API_URL}/status/incidents/{self.incident_id}/events/{self.id}"


    @computed_field(description="The resource belonging to this event")
    @property
    def resource_uri(self) -> str:
        return f"{config.API_URL_ROOT}{config.API_PREFIX}{config.API_URL}/status/resources/{self.resource_id}"


    @computed_field(description="The event's incident")
    @property
    def incident_uri(self) -> str|None:
        return f"{config.API_URL_ROOT}{config.API_PREFIX}{config.API_URL}/status/incidents/{self.incident_id}" if self.incident_id else None


    @staticmethod
    def find(
        events : list,
        resource_id : str | None = None,
        name : str | None = None,
        description : str | None = None,
        status : Status | None = None,
        from_ : datetime.datetime | None = None,
        to : datetime.datetime | None = None,
        time_ : datetime.datetime | None = None,
        modified_since : datetime.datetime | None = None,
    ) -> list:
        events = NamedResource.find(events, name, description, modified_since)
        if resource_id:
            events = [e for e in events if e.resource_id == resource_id]
        if status:
            events = [e for e in events if e.status == status]
        if from_:
            events = [e for e in events if e.occurred_at >= from_]
        if to:
            events = [e for e in events if e.occurred_at < to]
        if time_:
            events = [e for e in events if e.occurred_at == time_]
        return events


class IncidentType(enum.Enum):
    planned = "planned"
    unplanned = "unplanned"


class Resolution(enum.Enum):
    unresolved = "unresolved"
    cancelled = "cancelled"
    completed = "completed"
    extended = "extended"
    pending = "pending"


class Incident(NamedResource):
    status : Status
    resource_ids : list[str] = Field(exclude=True)
    event_ids : list[str] = Field(exclude=True)
    start : datetime.datetime
    end : datetime.datetime | None
    type : IncidentType
    resolution : Resolution


    @computed_field(description="The url of this object")
    @property
    def self_uri(self) -> str:
        return f"{config.API_URL_ROOT}{config.API_PREFIX}{config.API_URL}/status/incidents/{self.id}"


    @computed_field(description="The list of past events in this incident")
    @property
    def event_uris(self) -> list[str]:
        return [f"{config.API_URL_ROOT}{config.API_PREFIX}{config.API_URL}/status/incidents/{self.id}/events/{e}" for e in self.event_ids]


    @computed_field(description="The list of resources that may be impacted by this incident")
    @property
    def resource_uris(self) -> list[str]:
        return [f"{config.API_URL_ROOT}{config.API_PREFIX}{config.API_URL}/status/resources/{r}" for r in self.resource_ids]

    def find(
        incidents : list,
        name : str | None = None,
        description : str | None = None,
        status : Status | None = None,
        type_ : IncidentType | None = None,
        from_ : datetime.datetime | None = None,
        to : datetime.datetime | None = None,
        time_ : datetime.datetime | None = None,
        modified_since : datetime.datetime | None = None,
        resource_id : str | None = None,
    ) -> list:
        incidents = NamedResource.find(incidents, name, description, modified_since)
        if resource_id:
            incidents = [e for e in incidents if resource_id in e.resource_ids]
        if status:
            incidents = [e for e in incidents if e.status == status]
        if type_:
            incidents = [e for e in incidents if e.type == type_]
        if from_:
            incidents = [e for e in incidents if e.start >= from_]
        if to:
            incidents = [e for e in incidents if e.end < to]
        if time_:
            incidents = [e for e in incidents if e.start <= time_ and e.end > time_]
        return incidents
