"""Scalar types for the IRI Facility API"""

# pylint: disable=unused-argument
import datetime
import re
from enum import Enum
from typing import Annotated

from pydantic import BeforeValidator, WithJsonSchema
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
        return {"type": "boolean", "description": "Strict boolean. Only true/false allowed (bool or string).", "example": True}


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
        return {"type": "string", "format": "date-time", "description": "Strict ISO8601 datetime. Only valid ISO8601 datetime strings are accepted.", "example": "2026-02-21T12:00:00Z"}


# -----------------------------------------------------------------------
# DOE IRI URN validation

DOE_IRI_URN_PREFIX = "urn:doe-iri:"
_DOMAIN = r"[A-Za-z0-9][A-Za-z0-9-]{0,31}"
_SEGMENT_CHAR = r"(?:[A-Za-z0-9._~-]|%[0-9A-Fa-f]{2}|[!$&'()*+,;=@]|/)"
_DOMAIN_SPECIFIC_SEGMENT = rf"{_SEGMENT_CHAR}+"
_DOMAIN_SPECIFIC_STRING = rf"{_DOMAIN_SPECIFIC_SEGMENT}(?::{_DOMAIN_SPECIFIC_SEGMENT})*"
DOE_IRI_URN_PATTERN = re.compile(rf"^{DOE_IRI_URN_PREFIX}(?P<domain>{_DOMAIN}):(?P<nss>{_DOMAIN_SPECIFIC_STRING})$")
# General URN pattern and minimum length — use these for query parameters that accept any domain.
DOE_IRI_URN_SCHEMA_PATTERN = rf"^{DOE_IRI_URN_PREFIX}{_DOMAIN}:{_DOMAIN_SPECIFIC_STRING}$"
DOE_IRI_URN_MIN_LENGTH = len(DOE_IRI_URN_PREFIX) + 1 + 1 + 1  # prefix + 1 domain char + colon + 1 nss char


def validate_doe_iri_urn(value: str) -> str:
    """Validate a DOE IRI URN string. Raises ValueError on failure."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Invalid DOE IRI URN. Expected a non-empty string.")
    candidate = value.strip()
    if not DOE_IRI_URN_PATTERN.fullmatch(candidate):
        raise ValueError("Invalid DOE IRI URN. Expected format urn:doe-iri:<domain>:<domain-specific-string>.")
    return candidate


def _validate_urn_domain(value: str, domain: str, label: str) -> str:
    """Validate a DOE IRI URN and enforce that its domain matches the expected value."""
    urn = validate_doe_iri_urn(value)
    actual_domain = urn.split(":", 3)[2]
    if actual_domain != domain:
        raise ValueError(f"Invalid {label}. Expected domain '{domain}', got '{actual_domain}'.")
    return urn


def doe_iri_domain_urn_schema_pattern(domain: str) -> str:
    """Return the JSON schema pattern for DOE IRI URNs in one domain."""
    return rf"^{DOE_IRI_URN_PREFIX}{domain}:{_DOMAIN_SPECIFIC_STRING}$"


def doe_iri_domain_urn_min_length(domain: str) -> int:
    """Return the minimum length for DOE IRI URNs in one domain."""
    return len(f"{DOE_IRI_URN_PREFIX}{domain}:") + 1


def _domain_urn_schema(domain: str, description: str, examples: list[str]) -> dict[str, object]:
    return {
        "type": "string",
        "minLength": doe_iri_domain_urn_min_length(domain),
        "pattern": doe_iri_domain_urn_schema_pattern(domain),
        "description": description,
        "examples": examples,
    }


def urn_has_complete_prefix(parent_urn: str, candidate_urn: str) -> bool:
    """Return True when parent_urn is an exact or parent segment match of candidate_urn."""
    parent_segments = validate_doe_iri_urn(parent_urn).split(":")
    candidate_segments = validate_doe_iri_urn(candidate_urn).split(":")
    if len(parent_segments) > len(candidate_segments):
        return False
    return candidate_segments[: len(parent_segments)] == parent_segments


# -----------------------------------------------------------------------
# Canonical enum types


class ResourceType(str, Enum):
    """Canonical DOE IRI resource type URNs (spec §3.1).

    Note: `service` lives in the `service` domain per spec, not `resource`.
    ResourceTypeValue accepts any valid DOE IRI URN to allow facility extensions.
    """
    website = "urn:doe-iri:service:website"
    service = "urn:doe-iri:service:generic"
    compute = "urn:doe-iri:resource:compute"
    system = "urn:doe-iri:resource:system"
    storage = "urn:doe-iri:resource:storage"
    network = "urn:doe-iri:resource:network"
    unknown = "urn:doe-iri:resource:unknown"


class AllocationUnit(str, Enum):
    """Canonical DOE IRI allocation-unit URNs (spec §3.2)."""
    node_hours = "urn:doe-iri:allocation:compute:node-hours"
    bytes = "urn:doe-iri:allocation:storage:bytes"
    inodes = "urn:doe-iri:allocation:storage:inodes"


class CompressionType(str, Enum):
    """Canonical DOE IRI compression URNs (spec §3.3)."""
    none = "urn:doe-iri:compression:none"
    bzip2 = "urn:doe-iri:compression:bzip2"
    gzip = "urn:doe-iri:compression:gzip"
    xz = "urn:doe-iri:compression:xz"


# -----------------------------------------------------------------------
# Pydantic annotated field types

# ResourceTypeValue accepts any valid DOE IRI URN.
# No domain constraint: `service` lives in the `service` domain (spec §3.1),
# and facilities may use their own domains for local extensions (spec §5).
ResourceTypeValue = Annotated[
    str,
    BeforeValidator(validate_doe_iri_urn),
    WithJsonSchema({
        "type": "string",
        "description": "DOE IRI resource type URN (urn:doe-iri:<domain>:<nss>). Facility-local extensions accepted.",
        "examples": [ResourceType.compute, ResourceType.storage, ResourceType.service],
    }),
]

AllocationUnitValue = Annotated[
    str,
    BeforeValidator(lambda v: _validate_urn_domain(v, "allocation", "allocation unit")),
    WithJsonSchema(
        _domain_urn_schema(
            "allocation",
            "DOE IRI allocation-unit URN.",
            [AllocationUnit.node_hours, AllocationUnit.bytes],
        )
    ),
]

CompressionTypeValue = Annotated[
    str,
    BeforeValidator(lambda v: _validate_urn_domain(v, "compression", "compression type")),
    WithJsonSchema(
        _domain_urn_schema(
            "compression",
            "DOE IRI compression URN.",
            [CompressionType.gzip, CompressionType.none],
        )
    ),
]
