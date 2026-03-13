#!/usr/bin/env python3
"""
Utility for generating the IRI OpenAPI extension metadata.
It generates:
{
    "x-iri": {
        "maturity": "graduated",
        "implementation": {
            "level": "required",
            "required_if_capability": "dpu"
        }
    }
}
"""


def iri_meta_dict(
    maturity: str | None = None,
    implementation_level: str | None = None,
    required_if: str | None = None,
) -> dict:
    """Generate the IRI OpenAPI extension metadata."""

    out_obj = {}

    if maturity is not None:
        out_obj["maturity"] = maturity

    if implementation_level is not None:
        out_obj.setdefault("implementation", {})["level"] = implementation_level

    if required_if is not None:
        out_obj.setdefault("implementation", {})["required_if_capability"] = required_if

    if not out_obj:
        return {}

    return {"x-iri": out_obj}