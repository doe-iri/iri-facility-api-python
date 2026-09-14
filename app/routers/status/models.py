"""Models for the status API."""
import datetime
import enum

from pydantic import Field, computed_field, field_validator, model_validator

from ...apilogger import get_stream_logger
from ...request_context import get_url_prefix
from ...types.base import NamedObject
from ...types.hal import PROFILE_ACCOUNT_CAPABILITY, PROFILE_FACILITY_SITE, PROFILE_STATUS_RESOURCE, RELATION_METADATA, build_hal_link
from ...types.scalars import ResourceType, ResourceTypeValue, urn_has_complete_prefix, validate_doe_iri_urn

LOGGER = get_stream_logger(__name__)


class Status(enum.Enum):
    """Represents the status of a resource."""
    up = "up"
    down = "down"
    degraded = "degraded"
    unknown = "unknown"


class Endpoint(str, enum.Enum):
    """Router endpoint a resource supports (used internally to route compute/filesystem requests)."""
    compute = "compute"
    filesystem = "filesystem"


class Resource(NamedObject):
    """Represents a resource in the system."""
    def _self_path(self) -> str:
        """Return the API path for this resource."""
        return f"/status/resources/{self.id}"

    site_id: str = Field(..., description="The site identifier this resource is located at", exclude=True, example="site-1")
    capability_ids: list[str] = Field(default_factory=list, exclude=True)
    group: str|None = Field(default=None, description="Logical grouping of the resource", example="frontend")
    current_status: Status|None = Field(default=None, description="The current status comes from the status of the last event for this resource", example="up")
    resource_type: ResourceTypeValue = Field(..., description="DOE IRI URN for the resource type", example=ResourceType.service)
    supported_endpoints: list[Endpoint] = Field(default_factory=list, description="a list of endpoints where this resource can be used")
    related_resource_ids: dict[str, list[str]] = Field(
        default_factory=dict,
        exclude=True,
        description="Resource-to-Resource relation targets, keyed by registered relation name (e.g. 'has-mount', 'mounted-on'). See app.types.hal.RELATION_METADATA for the registered set.",
    )

    @model_validator(mode="after")
    def _validate_related_resource_ids(self):
        for relation, target_ids in self.related_resource_ids.items():
            spec = RELATION_METADATA.get(relation)
            if spec is None:
                raise ValueError(
                    f"related_resource_ids: '{relation}' is not a registered Resource-to-Resource relation "
                    f"(see app.types.hal.RELATION_METADATA)"
                )
            if spec.cardinality == "one" and len(target_ids) > 1:
                raise ValueError(
                    f"related_resource_ids: relation '{relation}' has cardinality 'one' but got "
                    f"{len(target_ids)} targets: {target_ids}"
                )
            source_types = spec.source_type if isinstance(spec.source_type, tuple) else (spec.source_type,)
            if not any(urn_has_complete_prefix(t, self.resource_type) for t in source_types):
                LOGGER.warning(
                    "Resource %s declares relation 'iri:%s', whose registered source type is %s, "
                    "but resource_type is %s (allowed: a producer MAY report a broader parent type "
                    "per status/resource.md section 5.3)",
                    self.id, relation, source_types, self.resource_type,
                )
        return self

    @computed_field(description="URI of the site where this resource is located")
    @property
    def site_uri(self) -> str:
        """Return the site URI for this resource."""
        return f"{get_url_prefix()}/facility/sites/{self.site_id}"

    @computed_field(description="The list of capabilities in this resource")
    @property
    def capability_uris(self) -> list[str]:
        """Return the list of capability URIs for this resource."""
        return [f"{get_url_prefix()}/account/capabilities/{e}" for e in self.capability_ids]

    def _link_profile(self) -> str | None:
        return PROFILE_STATUS_RESOURCE

    def _extra_links(self) -> dict:
        links: dict = {
            "iri:located-at": build_hal_link(self.site_uri, profile=PROFILE_FACILITY_SITE),
        }
        if self.capability_ids:
            links["iri:has-capability"] = [
                build_hal_link(uri, profile=PROFILE_ACCOUNT_CAPABILITY) for uri in self.capability_uris
            ]
        if urn_has_complete_prefix("urn:doe-iri:resource:compute:system", self.resource_type) and "compute" in self.supported_endpoints:
            links["iri:submit-job"] = {"href": f"{get_url_prefix()}/compute/job/{self.id}"}
        for relation, target_ids in self.related_resource_ids.items():
            if not target_ids:
                continue
            spec = RELATION_METADATA[relation]  # validated in _validate_related_resource_ids
            targets = [
                build_hal_link(f"{get_url_prefix()}/status/resources/{target_id}", profile=spec.target_profile)
                for target_id in target_ids
            ]
            links[f"iri:{relation}"] = targets[0] if spec.cardinality == "one" else targets
        return links

    @classmethod
    def find(cls, items, name=None, description=None, modified_since=None, group=None, resource_type=None, current_status=None, capability=None, site_id=None) -> list:
        items = super().find(items, name=name, description=description, modified_since=modified_since)
        if group:
            items = [item for item in items if item.group == group]
        if resource_type:
            # resource_type may be a ResourceType enum (which is a str subclass) or a raw URN string.
            # Do not call str() on a str(Enum) — it returns the repr, not the value.
            rt_urn = validate_doe_iri_urn(resource_type.value if hasattr(resource_type, "value") else resource_type)
            items = [item for item in items if urn_has_complete_prefix(rt_urn, item.resource_type)]
        if current_status:
            items = [item for item in items if item.current_status == current_status]
        if capability:
            items = [item for item in items if any(cap_id in item.capability_ids for cap_id in capability)]
        if site_id:
            items = [item for item in items if item.site_id == site_id]
        return items


class Event(NamedObject):
    """Represents an event that occurred to a resource, which may be part of an incident."""
    def _self_path(self) -> str:
        """Return the API path for this event."""
        return f"/status/events/{self.id}"

    @field_validator("occurred_at", mode="before")
    @classmethod
    def _norm_dt_field(cls, v):
        return cls.normalize_dt(v)

    occurred_at: datetime.datetime = Field(..., description="Timestamp when the event occurred", example="2026-02-21T12:00:00Z")
    status: Status = Field(..., description="Status of the resource at the time of the event", example="down")
    resource_id: str = Field(..., exclude=True, description="Identifier of the affected resource", example="res-1")
    incident_id: str|None = Field(default=None, exclude=True, description="Identifier of the related incident", example="inc-1")

    @computed_field(description="The resource belonging to this event")
    @property
    def resource_uri(self) -> str:
        """Return the resource URI for this event."""
        return f"{get_url_prefix()}/status/resources/{self.resource_id}"

    @computed_field(description="The event's incident")
    @property
    def incident_uri(self) -> str | None:
        """Return the incident URI for this event."""
        return f"{get_url_prefix()}/status/incidents/{self.incident_id}" if self.incident_id else None

    @classmethod
    def find(cls, items, incident_id=None, name=None, description=None, modified_since=None, resource_id=None, status=None, from_=None, to=None, time_=None) -> list:
        items = super().find(items, name=name, description=description, modified_since=modified_since)

        if incident_id:
            items = [e for e in items if e.incident_id == incident_id]
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
    """Represents the type of an incident."""
    planned = "planned"
    unplanned = "unplanned"
    reservation = "reservation"


class Resolution(enum.Enum):
    """Represents the resolution status of an incident."""
    unresolved = "unresolved"
    cancelled = "cancelled"
    completed = "completed"
    extended = "extended"
    pending = "pending"


class Incident(NamedObject):
    """Represents an incident that may impact one or more resources."""
    def _self_path(self) -> str:
        """Return the API path for this incident."""
        return f"/status/incidents/{self.id}"

    @field_validator("start", "end", mode="before")
    @classmethod
    def _norm_dt_field(cls, v):
        return cls.normalize_dt(v)

    status: Status = Field(..., description="Current status of the incident", example="degraded")
    resource_ids: list[str] = Field(default_factory=list, exclude=True)
    event_ids: list[str] = Field(default_factory=list, exclude=True)
    start: datetime.datetime = Field(..., description="Incident start time", example="2026-02-21T12:00:00Z")
    end: datetime.datetime|None = Field(default=None, description="Incident end time", example="2026-02-21T14:00:00Z")
    type: IncidentType = Field(..., description="Type of incident", example="planned")
    resolution: Resolution = Field(..., description="Resolution status of the incident", example="pending")

    @computed_field(description="The list of past events in this incident")
    @property
    def event_uris(self) -> list[str]:
        """Return the list of event URIs for this incident."""
        return [f"{get_url_prefix()}/status/events/{e}" for e in self.event_ids]

    @computed_field(description="The list of resources that may be impacted by this incident")
    @property
    def resource_uris(self) -> list[str]:
        """Return the list of resource URIs for this incident."""
        return [f"{get_url_prefix()}/status/resources/{r}" for r in self.resource_ids]

    @classmethod
    def find(cls, items, name=None, description=None, modified_since=None, status=None, type_=None, from_=None, to=None, time_=None, resource_id=None, resolution=None) -> list:
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
            items = [e for e in items if e.start <= time_ and (e.end is None or e.end > time_)]
        return items
