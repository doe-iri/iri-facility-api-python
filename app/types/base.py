"""Default models used by multiple routers."""

import datetime
from collections.abc import Iterable
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_serializer

from .. import config
from .scalars import StrictDateTime


class IRIBaseModel(BaseModel):
    """Base model for IRI models."""

    model_config = ConfigDict(extra="allow")

    @model_serializer(mode="wrap")
    def _hide_extra(self, handler, info):
        data = handler(self)

        model_fields = set(self.model_fields or {})
        computed_fields = set(self.model_computed_fields or {})
        extra = getattr(self, "__pydantic_extra__", {}) or {}
        for k in extra:
            if k not in model_fields and k not in computed_fields:
                data.pop(k, None)
        return data

    def get_extra(self, key, default=None):
        """Get an extra field value that is not defined in the model. Returns default if not found."""
        return getattr(self, "__pydantic_extra__", {}).get(key, default)

    @classmethod
    def normalize_dt(cls, dt: datetime | None) -> datetime | None:
        """Normalize datetime to UTC-aware."""
        # Convert naive datetimes into UTC-aware versions
        if dt is None:
            return None
        if isinstance(dt, str):
            dt = StrictDateTime.validate(dt)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=datetime.timezone.utc)
        return dt


class NamedObject(IRIBaseModel):
    """Base model for named objects."""

    id: str = Field(..., description="The unique identifier for the object. Typically a UUID or URN.")

    def _self_path(self) -> str:
        raise NotImplementedError

    @field_validator("last_modified", mode="before")
    @classmethod
    def _norm_dt_field(cls, v):
        return cls.normalize_dt(v)

    @computed_field(description="The canonical URL of this object")
    @property
    def self_uri(self) -> str:
        """Computed self URI property."""
        return f"{config.API_URL_ROOT}{config.API_PREFIX}{config.API_URL}{self._self_path()}"

    name: Optional[str] = Field(None, description="The long name of the object.")
    description: Optional[str] = Field(None, description="Human-readable description of the object.")
    last_modified: StrictDateTime = Field(..., description="ISO 8601 timestamp when this object was last modified.")

    @classmethod
    def find_by_id(cls, items, id_, allow_name: bool = False):
        """Find an object by its id or name == id."""
        # Find a resource by its id.
        # If allow_name is True, the id parameter can also match the resource's name.
        matches = [r for r in items if r.id == id_ or (allow_name and r.name == id_)]
        if not matches:
            return None
        if len(matches) > 1:
            raise ValueError(f"Multiple {cls.__name__} objects matched identifier '{id_}'")

        return matches[0]

    @classmethod
    def find(cls, items, name=None, description=None, modified_since=None):
        """Find objects matching the given criteria."""
        single = False
        if not any((name, description, modified_since)):
            return items

        if not isinstance(items, Iterable) or isinstance(items, BaseModel):
            items = [items]
            single = True

        if name:
            items = [item for item in items if item.name == name]
        if description:
            items = [item for item in items if item.description and description in item.description]
        if modified_since:
            modified_since = cls.normalize_dt(modified_since)
            items = [item for item in items if item.last_modified and item.last_modified >= modified_since]
        if single:
            return items[0] if items else None
        return items
