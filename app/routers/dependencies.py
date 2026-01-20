"""Default models used by multiple routers."""
import datetime
from typing import Optional
from urllib.parse import parse_qs

from pydantic_core import core_schema
from pydantic import BaseModel, ConfigDict, Field, computed_field, model_serializer
from fastapi import Request, HTTPException

from .. import config


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


def forbidExtraQueryParams(*allowedParams: str):
    async def checker(req: Request):
        if "*" in allowedParams:
            return

        raw_qs = req.scope.get("query_string", b"")
        parsed = parse_qs(raw_qs.decode("utf-8", errors="strict"), keep_blank_values=True)

        allowed = set(allowedParams)

        for key, values in parsed.items():
            if key not in allowed:
                raise HTTPException(
                    status_code=422,
                    detail=[{
                        "type": "extra_forbidden",
                        "loc": ["query", key],
                        "msg": f"Unexpected query parameter: {key}"
                    }])

            if len(values) > 1:
                raise HTTPException(
                    status_code=422,
                    detail=[{
                        "type": "duplicate_forbidden",
                        "loc": ["query", key],
                        "msg": f"Duplicate query parameter: {key}"
                    }])
    return checker


class IRIBaseModel(BaseModel):
    """Base model for IRI models."""
    model_config = ConfigDict(extra="allow")

    @model_serializer(mode="wrap")
    def _hide_extra(self, handler):
        data = handler(self)
        extra = getattr(self, "__pydantic_extra__", {}) or {}
        for k in extra:
            data.pop(k, None)
        return data

class NamedObject(IRIBaseModel):
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
    last_modified: StrictDateTime = Field(..., description="ISO 8601 timestamp when this object was last modified.")

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
