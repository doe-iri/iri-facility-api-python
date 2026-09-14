"""HAL hypermedia primitives shared by every IRI implementation.

See iri-facility-api-docs/registry/relations/README.md for the authoritative
source of information.
"""
from dataclasses import dataclass

IRI_RELS_TEMPLATE = "https://iri.science/rels/{rel}"

IRI_CURIE = {
    "name": "iri",
    "href": IRI_RELS_TEMPLATE,
    "templated": True,
}

PROFILE_FACILITY = "https://iri.science/profiles/facility"
PROFILE_FACILITY_SITE = "https://iri.science/profiles/facility/site"
PROFILE_STATUS_RESOURCE = "https://iri.science/profiles/status/resource"
PROFILE_ACCOUNT_CAPABILITY = "https://iri.science/profiles/account/capability"

_RD = "https://iri.science/profiles/resource-definition"

RESOURCE_TYPE_PROFILE: dict[str, str] = {
    "urn:doe-iri:resource:compute:system": f"{_RD}/compute/system",
    "urn:doe-iri:resource:compute:node": f"{_RD}/compute/node",
    "urn:doe-iri:resource:compute:cpu": f"{_RD}/compute/cpu",
    "urn:doe-iri:resource:compute:gpu": f"{_RD}/compute/gpu",
    "urn:doe-iri:resource:storage:system": f"{_RD}/storage/system",
    "urn:doe-iri:resource:storage:filesystem": f"{_RD}/storage/filesystem",
    "urn:doe-iri:resource:storage:mount": f"{_RD}/storage/mount",
    "urn:doe-iri:resource:storage:block": f"{_RD}/storage/block",
    "urn:doe-iri:resource:storage:object": f"{_RD}/storage/object",
    "urn:doe-iri:resource:service:dtn": f"{_RD}/service/dtn",
    "urn:doe-iri:resource:service:inference": f"{_RD}/service/inference",
}


def resource_type_profile(resource_type: str) -> str | None:
    """Return the Resource Definition profile URI for a resource_type URN."""
    return RESOURCE_TYPE_PROFILE.get(resource_type)


def build_hal_link(href: str, profile: str | None = None, media_type: str | None = "application/hal+json") -> dict:
    """Build one HAL link object, omitting unset optional fields."""
    link: dict[str, str] = {"href": href}
    if media_type is not None:
        link["type"] = media_type
    if profile is not None:
        link["profile"] = profile
    return link


@dataclass(frozen=True)
class RelationSpec:
    """Static metadata for one registered Resource-to-Resource iri:* relation."""
    cardinality: str  # "one" | "many"
    target_profile: str | None
    source_type: str | tuple[str, ...]


RELATION_METADATA: dict[str, RelationSpec] = {
    "provides-filesystem": RelationSpec("many", RESOURCE_TYPE_PROFILE["urn:doe-iri:resource:storage:filesystem"], "urn:doe-iri:resource:storage:system"),
    "provides-block": RelationSpec("many", RESOURCE_TYPE_PROFILE["urn:doe-iri:resource:storage:block"], "urn:doe-iri:resource:storage:system"),
    "provides-object": RelationSpec("many", RESOURCE_TYPE_PROFILE["urn:doe-iri:resource:storage:object"], "urn:doe-iri:resource:storage:system"),
    "has-mount": RelationSpec("many", RESOURCE_TYPE_PROFILE["urn:doe-iri:resource:storage:mount"], "urn:doe-iri:resource:storage:filesystem"),
    "mounted-on": RelationSpec("one", RESOURCE_TYPE_PROFILE["urn:doe-iri:resource:compute:system"], "urn:doe-iri:resource:storage:mount"),
    "attached-to": RelationSpec("many", None, "urn:doe-iri:resource:storage:block"),
    "has-node": RelationSpec("many", RESOURCE_TYPE_PROFILE["urn:doe-iri:resource:compute:node"], "urn:doe-iri:resource:compute:system"),
    "has-cpu": RelationSpec("many", RESOURCE_TYPE_PROFILE["urn:doe-iri:resource:compute:cpu"], "urn:doe-iri:resource:compute:node"),
    "has-gpu": RelationSpec("many", RESOURCE_TYPE_PROFILE["urn:doe-iri:resource:compute:gpu"], "urn:doe-iri:resource:compute:node"),
    "hosted-on": RelationSpec("many", None, ("urn:doe-iri:resource:service:dtn", "urn:doe-iri:resource:service:inference")),
    "accesses-mount": RelationSpec("many", RESOURCE_TYPE_PROFILE["urn:doe-iri:resource:storage:mount"], "urn:doe-iri:resource:service:dtn"),
}
