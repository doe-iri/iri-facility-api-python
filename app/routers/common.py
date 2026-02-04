"""Default models used by multiple routers."""
import datetime
from email.utils import parsedate_to_datetime
import enum
from typing import Optional
from urllib.parse import parse_qs
from collections.abc import Iterable
from pydantic_core import core_schema
from pydantic import BaseModel, ConfigDict, Field, computed_field, model_serializer, field_validator
from fastapi import Request, HTTPException, status

from .. import config


def paginate_list(items, offset: int | None, limit: int | None):
    """Return a sliced items using offset and limit."""
    if offset is not None and offset > 0:
        items = items[offset:]
    if limit is not None and limit >= 0:
        items = items[:limit]
    return items

# These are Pydantic custom types for strict validation
# that are not implmented in Pydantic by default.
# -----------------------------------------------------------------------
# StrictBool: a strict boolean type
class StrictBool:
    """Strict boolean:
       - Accepts: real booleans, 'true', 'false'
       - Rejects everything else.
    """

    @classmethod
    def __get_pydantic_core_schema__(cls, source, handler):
        return core_schema.no_info_plain_validator_function(cls.validate)

    @staticmethod
    def validate(value):
        """Validate the input value as a strict boolean."""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            v = value.strip().lower()
            if v == "true":
                return True
            if v == "false":
                return False
            raise ValueError("Invalid boolean value. Expected 'true' or 'false'.")
        raise ValueError("Invalid boolean value. Expected true/false or 'true'/'false'.")

    @classmethod
    def __get_pydantic_json_schema__(cls, schema, handler):
        return {
            "type": "boolean",
            "description": "Strict boolean. Only true/false allowed (bool or string)."
        }

# -----------------------------------------------------------------------
# StrictDateTime: a strict ISO8601 datetime type

class StrictDateTime:
    """
    Strict ISO8601 datetime:
      - Accepts datetime objects
      - Accepts ISO8601 strings: 2025-12-06T10:00:00Z, 2025-12-06T10:00:00+00:00
      - Converts 'Z' → UTC
      - Converts naive datetimes → UTC
      - Rejects integers ("0"), null, garbage strings, etc.
    """

    @classmethod
    def __get_pydantic_core_schema__(cls, source, handler):
        return core_schema.no_info_plain_validator_function(cls.validate)

    @staticmethod
    def validate(value):
        if isinstance(value, datetime.datetime):
            return StrictDateTime._normalize(value)
        if not isinstance(value, str):
            raise ValueError("Invalid datetime value. Expected ISO8601 datetime string.")
        v = value.strip()
        if v.endswith("Z"):
            v = v[:-1] + "+00:00"
        try:
            dt = datetime.datetime.fromisoformat(v)
        except Exception as ex:
            raise ValueError("Invalid datetime format. Expected ISO8601 string.") from ex

        return StrictDateTime._normalize(dt)


    @staticmethod
    def modifiedSinceDatetime(
        modified_since: str | None,
        header_modified_since: str | None
    ) -> datetime.datetime | None:
        """
        Combine modified_since (ISO8601) and If-Modified-Since (RFC1123).
        If both are provided, the most recent timestamp is used.
        """

        parsed_times: list[datetime.datetime] = []

        # Query param (ISO 8601)
        if modified_since is not None:
            try:
                dt = StrictDateTime.validate(modified_since)
                parsed_times.append(dt)
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid modified_since query param: {exc}",
                ) from exc

        # Header (RFC 1123)
        if header_modified_since is not None:
            try:
                dt = parsedate_to_datetime(header_modified_since)
                if dt is None:
                    raise ValueError("Invalid RFC1123 date")
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=datetime.timezone.utc)
                parsed_times.append(dt.astimezone(datetime.timezone.utc))
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid If-Modified-Since header format (must be RFC1123)",
                ) from exc

        if not parsed_times:
            return None

        # Stricter constraint wins
        return max(parsed_times)

    @staticmethod
    def _normalize(dt: datetime.datetime) -> datetime.datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=datetime.timezone.utc)
        return dt

    @classmethod
    def __get_pydantic_json_schema__(cls, schema, handler):
        return {
            "type": "string",
            "format": "date-time",
            "description": "Strict ISO8601 datetime. Only valid ISO8601 datetime strings are accepted."
        }


def forbidExtraQueryParams(*allowedParams: str, multiParams: set[str] | None = None):
    multiParams = multiParams or set()

    async def checker(req: Request):
        if "*" in allowedParams:
            return

        raw_qs = req.scope.get("query_string", b"")
        parsed = parse_qs(raw_qs.decode("utf-8", errors="strict"), keep_blank_values=True)

        allowed = set(allowedParams)

        for key, values in parsed.items():
            if key not in allowed:
                raise HTTPException(status_code=422,
                                    detail=[{"type": "extra_forbidden",
                                             "loc": ["query", key],
                                             "msg": f"Unexpected query parameter: {key}"}])


            if len(values) > 1 and key not in multiParams:
                raise HTTPException(status_code=422,
                                    detail=[{"type": "duplicate_forbidden",
                                             "loc": ["query", key],
                                             "msg": f"Duplicate query parameter: {key}"}])

    return checker


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
        return getattr(self, "__pydantic_extra__", {}).get(key, default)


class NamedObject(IRIBaseModel):
    id: str = Field(..., description="The unique identifier for the object. Typically a UUID or URN.")
    def _self_path(self) -> str:
        raise NotImplementedError

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
        """ Find an object by its id or name == id. """
        # Find a resource by its id.
        # If allow_name is True, the id parameter can also match the resource's name.
        matches = [r for r in items if r.id == id_ or (allow_name and r.name == id_)]
        if not matches:
            return None
        if len(matches) > 1:
            raise ValueError(f"Multiple {cls.__name__} objects matched identifier '{id}'")

        return matches[0]

    @classmethod
    def find(cls, items, name=None, description=None, modified_since=None):
        """ Find objects matching the given criteria. """
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
            items = [item for item in items if item.last_modified >= modified_since]

        if single:
            return items[0] if items else None
        return items


class AllocationUnit(enum.Enum):
    node_hours = "node_hours"
    bytes = "bytes"
    inodes = "inodes"


class Capability(IRIBaseModel):
    """
        An aspect of a resource that can have an allocation.
        For example, Perlmutter nodes with GPUs
        For some resources at a facility, this will be 1 to 1 with the resource.
        It is a way to further subdivide a resource into allocatable sub-resources.
        The word "capability" is also known to users as something they need for a job to run. (eg. gpu)
    """
    id: str
    name: str
    units: list[AllocationUnit]
