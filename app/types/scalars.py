"""Scalar types for the IRI Facility API"""

# pylint: disable=unused-argument
import datetime
import enum

from pydantic_core import core_schema

# -----------------------------------------------------------------------
# StrictHTTPBool: a strict boolean type


class StrictHTTPBool:
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
        return {"type": "boolean", "description": "Strict boolean. Only true/false allowed (bool or string)."}


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
        """Validate the input value as a strict ISO8601 datetime."""
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
        return {"type": "string", "format": "date-time", "description": "Strict ISO8601 datetime. Only valid ISO8601 datetime strings are accepted."}


# -----------------------------------------------------------------------
# AllocationUnit: an enum for allocation units


class AllocationUnit(enum.Enum):
    """Units for allocation"""

    node_hours = "node_hours"
    bytes = "bytes"
    inodes = "inodes"
