"""Default models used by multiple routers."""
import datetime
from typing import Optional
from pydantic import BaseModel, Field, computed_field
from . import iri_router
from .. import config


class NamedObject(BaseModel):
    id: str = Field(..., description="The unique identifier for the object. Typically a UUID or URN.")
    def _self_path(self) -> str:
        raise NotImplementedError

    @computed_field(description="The canonical URL of this object")
    @property
    def self_uri(self) -> str:
        """Computed self URI property."""
        return f"{config.API_URL_ROOT}{config.API_PREFIX}{config.API_URL}{self._self_path()}"

    name: Optional[str] = Field(None, description="The long name of the object.")
    description: Optional[str] = Field(None, description="Human-readable description of the object.")
    last_modified: iri_router.StrictDateTime = Field(..., description="ISO 8601 timestamp when this object was last modified.")

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
