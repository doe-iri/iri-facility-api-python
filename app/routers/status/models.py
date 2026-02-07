import datetime
import enum
from typing import Optional
from pydantic import BaseModel, computed_field, Field, field_validator, HttpUrl
from ... import config
from ..common import NamedObject


class Link(BaseModel):
    rel : str
    href : str


class Status(enum.Enum):
    up = "up"
    down = "down"
    degraded = "degraded"
    unknown = "unknown"


class ResourceType(enum.Enum):
    website = "website"
    service = "service"
    compute = "compute"
    system = "system"
    storage = "storage"
    network = "network"
    unknown = "unknown"


class Resource(NamedObject):

    def _self_path(self) -> str:
        """ Return the API path for this resource. """
        return f"/status/resources/{self.id}"

    # NOTE (TBR): If site_id is required, then located_at_uri should be also required. This can be easily identified by Site.self_uri
    # Is there a specific Resource, that has no Site?
    site_id: str = Field(..., description="The site identifier this resource is located at")
    capability_ids: list[str] = Field(default_factory=list, exclude=True)
    group: str | None
    current_status: Status | None = Field(default=None, description="The current status comes from the status of the last event for this resource")
    resource_type: ResourceType
    located_at_uri: Optional[HttpUrl] = Field(None, description="Resource located at specific Site")



    @computed_field(description="The list of capabilities in this resource")
    @property
    def capability_uris(self) -> list[str]:
        """ Return the list of capability URIs for this resource. """
        return [f"{config.API_URL_ROOT}{config.API_PREFIX}{config.API_URL}/account/capabilities/{e}" for e in self.capability_ids]

    @classmethod
    def find(cls, items, name=None, description=None, modified_since=None, group=None,
             resource_type=None, current_status=None, capability=None, site_id=None) -> list:
        items = super().find(items, name=name, description=description, modified_since=modified_since)
        if group:
            items = [item for item in items if item.group == group]
        if resource_type:
            if isinstance(resource_type, str):
                resource_type = ResourceType(resource_type)
            items = [item for item in items if item.resource_type == resource_type]
        if current_status:
            items = [item for item in items if item.current_status == current_status]
        if capability:
            items = [item for item in items
                     if any(cap_id in item.capability_ids for cap_id in capability)]
        if site_id:
            items = [item for item in items if item.site_id == site_id]
        return items

class Event(NamedObject):

    def _self_path(self) -> str:
        """ Return the API path for this event. """
        return f"/status/incidents/{self.incident_id}/events/{self.id}"

    @field_validator("occurred_at", mode="before")
    @classmethod
    def _norm_dt_field(cls, v):
        return cls.normalize_dt(v)

    occurred_at : datetime.datetime
    status : Status
    resource_id : str = Field(exclude=True)
    incident_id : str | None = Field(exclude=True, default=None)

    @computed_field(description="The resource belonging to this event")
    @property
    def resource_uri(self) -> str:
        """ Return the resource URI for this event. """
        return f"{config.API_URL_ROOT}{config.API_PREFIX}{config.API_URL}/status/resources/{self.resource_id}"

    @computed_field(description="The event's incident")
    @property
    def incident_uri(self) -> str|None:
        """ Return the incident URI for this event. """
        return f"{config.API_URL_ROOT}{config.API_PREFIX}{config.API_URL}/status/incidents/{self.incident_id}" if self.incident_id else None


    @classmethod
    def find(cls, items, name=None, description=None, modified_since=None,
             resource_id=None, status=None, from_=None, to=None, time_=None) -> list:
        items = super().find(items, name=name, description=description, modified_since=modified_since)

        if resource_id:
            items = [e for e in items if e.resource_id == resource_id]
        if status:
            if isinstance(status, str):
                status = Status(status)
            items = [e for e in items if e.status == status]

        from_ = cls.normalize_dt(from_) if from_ else None
        to = cls.normalize_dt(to) if to else None
        time_ = cls.normalize_dt(time_) if time_ else None

        if from_:
            items = [e for e in items if e.occurred_at >= from_]
        if to:
            items = [e for e in items if e.occurred_at < to]
        if time_:
            items = [e for e in items if e.occurred_at == time_]
        return items


class IncidentType(enum.Enum):
    planned = "planned"
    unplanned = "unplanned"
    reservation = "reservation"


class Resolution(enum.Enum):
    unresolved = "unresolved"
    cancelled = "cancelled"
    completed = "completed"
    extended = "extended"
    pending = "pending"



class Incident(NamedObject):

    def _self_path(self) -> str:
        """ Return the API path for this incident. """
        return f"/status/incidents/{self.id}"

    @field_validator("start", "end", mode="before")
    @classmethod
    def _norm_dt_field(cls, v):
        return cls.normalize_dt(v)

    status : Status
    resource_ids : list[str] = Field(default_factory=list, exclude=True)
    event_ids : list[str] = Field(default_factory=list, exclude=True)
    start : datetime.datetime
    end : datetime.datetime | None
    type : IncidentType
    resolution : Resolution

    @computed_field(description="The list of past events in this incident")
    @property
    def event_uris(self) -> list[str]:
        """ Return the list of event URIs for this incident. """
        return [f"{config.API_URL_ROOT}{config.API_PREFIX}{config.API_URL}/status/incidents/{self.id}/events/{e}" for e in self.event_ids]

    @computed_field(description="The list of resources that may be impacted by this incident")
    @property
    def resource_uris(self) -> list[str]:
        """ Return the list of resource URIs for this incident. """
        return [f"{config.API_URL_ROOT}{config.API_PREFIX}{config.API_URL}/status/resources/{r}" for r in self.resource_ids]

    @classmethod
    def find(cls, items, name=None, description=None, modified_since=None, status=None,
             type_=None, from_= None, to = None, time_ = None, resource_id = None, resolution=None) -> list:
        items = super().find(items, name=name, description=description, modified_since=modified_since)

        if resource_id:
            items = [e for e in items if resource_id in e.resource_ids]
        if status:
            items = [e for e in items if e.status == status]
        if type_:
            items = [e for e in items if e.type == type_]
        if resolution:
            items = [e for e in items if e.resolution == resolution]

        from_ = cls.normalize_dt(from_) if from_ else None
        to = cls.normalize_dt(to) if to else None
        time_ = cls.normalize_dt(time_) if time_ else None

        if from_:
            items = [e for e in items if e.start >= from_]
        if to:
            items = [e for e in items if e.end and e.end < to]

        if time_:
            items = [e for e in items
                     if e.start <= time_ and (e.end is None or e.end > time_)]
        return items