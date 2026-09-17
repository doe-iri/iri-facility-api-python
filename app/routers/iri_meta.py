#!/usr/bin/env python3
"""
Utility for generating the IRI OpenAPI extension metadata.
It generates:
{
    "x-iri": {
        "maturity": "production",
        "implementation": {
            "level": "required",
            "required_if_capability": "dpu"
        }
    },
    "x-iri-relation": ["https://iri.science/rels/submit-job"]
}
"""


def iri_meta_dict(
    maturity: str | None = None,
    implementation_level: str | None = None,
    required_if: str | None = None,
    relations: list[str] | None = None,
) -> dict:
    """Generate the IRI OpenAPI extension metadata.

    `relations` binds this operation to one or more registered DOE-IRI operation-affordance
    relations (ADR 0007), as canonical relation URIs from app.types.hal.OPERATION_RELATIONS.
    """

    out_obj = {}

    if maturity is not None:
        out_obj["maturity"] = maturity

    if implementation_level is not None:
        out_obj.setdefault("implementation", {})["level"] = implementation_level

    if required_if is not None:
        out_obj.setdefault("implementation", {})["required_if_capability"] = required_if

    extra = {}

    if out_obj:
        extra["x-iri"] = out_obj

    if relations:
        extra["x-iri-relation"] = list(relations)

    return extra
