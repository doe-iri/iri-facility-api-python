"""Scalar types for the IRI Facility API"""

# pylint: disable=unused-argument
import datetime
import re
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


DOE_IRI_URN_PREFIX = "urn:doe-iri:"
_DOMAIN = r"[A-Za-z0-9][A-Za-z0-9-]{0,31}"
_SEGMENT_CHAR = r"(?:[A-Za-z0-9._~-]|%[0-9A-Fa-f]{2}|[!$&'()*+,;=@]|/)"
_DOMAIN_SPECIFIC_SEGMENT = rf"{_SEGMENT_CHAR}+"
_DOMAIN_SPECIFIC_STRING = rf"{_DOMAIN_SPECIFIC_SEGMENT}(?::{_DOMAIN_SPECIFIC_SEGMENT})*"
DOE_IRI_URN_SCHEMA_PATTERN = rf"^{DOE_IRI_URN_PREFIX}{_DOMAIN}:{_DOMAIN_SPECIFIC_STRING}$"
DOE_IRI_URN_PATTERN = re.compile(rf"^{DOE_IRI_URN_PREFIX}(?P<domain>{_DOMAIN}):(?P<nss>{_DOMAIN_SPECIFIC_STRING})$")

CANONICAL_RESOURCE_TYPES = {
    "website": "urn:doe-iri:resource:website",
    "service": "urn:doe-iri:resource:service",
    "compute": "urn:doe-iri:resource:compute",
    "system": "urn:doe-iri:resource:system",
    "storage": "urn:doe-iri:resource:storage",
    "network": "urn:doe-iri:resource:network",
    "unknown": "urn:doe-iri:resource:unknown",
}

CANONICAL_ALLOCATION_UNITS = {
    "node-hours": "urn:doe-iri:allocation:compute:node-hours",
    "bytes": "urn:doe-iri:allocation:storage:bytes",
    "inodes": "urn:doe-iri:allocation:storage:inodes",
}

CANONICAL_COMPRESSION_TYPES = {
    "none": "urn:doe-iri:compression:none",
    "bzip2": "urn:doe-iri:compression:bzip2",
    "gzip": "urn:doe-iri:compression:gzip",
    "xz": "urn:doe-iri:compression:xz",
}

LEGACY_RESOURCE_TYPE_MAP = {
    **CANONICAL_RESOURCE_TYPES,
}

LEGACY_ALLOCATION_UNIT_MAP = {
    **CANONICAL_ALLOCATION_UNITS,
    "node_hours": CANONICAL_ALLOCATION_UNITS["node-hours"],
}

LEGACY_COMPRESSION_TYPE_MAP = {
    **CANONICAL_COMPRESSION_TYPES,
}


def _ensure_text(value, label: str) -> str:
    if isinstance(value, str):
        candidate = value.strip()
        if candidate:
            return candidate
    raise ValueError(f"Invalid {label}. Expected a non-empty string.")


def validate_doe_iri_urn(value: str) -> str:
    """Validate a DOE IRI URN string."""
    candidate = _ensure_text(value, "DOE IRI URN")
    if not DOE_IRI_URN_PATTERN.fullmatch(candidate):
        raise ValueError("Invalid DOE IRI URN. Expected format urn:doe-iri:<domain>:<domain-specific-string>.")
    return candidate


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


def _get_doe_iri_domain(value: str) -> str:
    return validate_doe_iri_urn(value).split(":", 3)[2]


def urn_has_complete_prefix(parent_urn: str, candidate_urn: str) -> bool:
    """Return True when parent_urn is an exact or parent segment match of candidate_urn."""
    parent_segments = validate_doe_iri_urn(parent_urn).split(":")
    candidate_segments = validate_doe_iri_urn(candidate_urn).split(":")
    if len(parent_segments) > len(candidate_segments):
        return False
    return candidate_segments[: len(parent_segments)] == parent_segments


def _coerce_domain_urn(value: str, domain: str, legacy_map: dict[str, str], label: str) -> str:
    candidate = _ensure_text(value, label)
    if not candidate.startswith("urn:"):
        mapped = legacy_map.get(candidate)
        if mapped:
            return mapped
        raise ValueError(f"Invalid {label}. Expected a DOE IRI URN or one of: {', '.join(sorted(legacy_map))}.")

    urn = validate_doe_iri_urn(candidate)
    urn_domain = _get_doe_iri_domain(urn)
    if urn_domain != domain:
        raise ValueError(f"Invalid {label}. Expected DOE IRI URN domain '{domain}', got '{urn_domain}'.")
    return urn


def canonicalize_resource_type(value: str) -> str:
    """Return the canonical DOE IRI resource type URN."""
    return _coerce_domain_urn(value, "resource", LEGACY_RESOURCE_TYPE_MAP, "resource type")


def canonicalize_allocation_unit(value: str) -> str:
    """Return the canonical DOE IRI allocation-unit URN."""
    return _coerce_domain_urn(value, "allocation", LEGACY_ALLOCATION_UNIT_MAP, "allocation unit")


def canonicalize_compression_type(value: str) -> str:
    """Return the canonical DOE IRI compression URN."""
    return _coerce_domain_urn(value, "compression", LEGACY_COMPRESSION_TYPE_MAP, "compression type")


class ResourceType:
    """Canonical DOE IRI resource type URNs."""

    website = CANONICAL_RESOURCE_TYPES["website"]
    service = CANONICAL_RESOURCE_TYPES["service"]
    compute = CANONICAL_RESOURCE_TYPES["compute"]
    system = CANONICAL_RESOURCE_TYPES["system"]
    storage = CANONICAL_RESOURCE_TYPES["storage"]
    network = CANONICAL_RESOURCE_TYPES["network"]
    unknown = CANONICAL_RESOURCE_TYPES["unknown"]


ResourceTypeValue = Annotated[
    str,
    BeforeValidator(canonicalize_resource_type),
    WithJsonSchema(
        _domain_urn_schema(
            "resource",
            "DOE IRI resource type URN. Legacy short tokens are accepted only as input compatibility aliases and are normalized to canonical URNs.",
            [ResourceType.compute, ResourceType.storage],
        )
    ),
]


class AllocationUnit:
    """Canonical DOE IRI allocation-unit URNs."""

    node_hours = CANONICAL_ALLOCATION_UNITS["node-hours"]
    bytes = CANONICAL_ALLOCATION_UNITS["bytes"]
    inodes = CANONICAL_ALLOCATION_UNITS["inodes"]


AllocationUnitValue = Annotated[
    str,
    BeforeValidator(canonicalize_allocation_unit),
    WithJsonSchema(
        _domain_urn_schema(
            "allocation",
            "DOE IRI allocation-unit URN. Legacy short tokens are accepted only as input compatibility aliases and are normalized to canonical URNs.",
            [AllocationUnit.node_hours, AllocationUnit.bytes],
        )
    ),
]


class CompressionType:
    """Canonical DOE IRI compression URNs."""

    none = CANONICAL_COMPRESSION_TYPES["none"]
    bzip2 = CANONICAL_COMPRESSION_TYPES["bzip2"]
    gzip = CANONICAL_COMPRESSION_TYPES["gzip"]
    xz = CANONICAL_COMPRESSION_TYPES["xz"]


CompressionTypeValue = Annotated[
    str,
    BeforeValidator(canonicalize_compression_type),
    WithJsonSchema(
        _domain_urn_schema(
            "compression",
            "DOE IRI compression URN. Legacy short tokens are accepted only as input compatibility aliases and are normalized to canonical URNs.",
            [CompressionType.gzip, CompressionType.none],
        )
    ),
]
