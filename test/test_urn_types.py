#!/usr/bin/env python3
"""Focused DOE IRI URN regression tests."""

import unittest

from pydantic import TypeAdapter

from app.routers.filesystem import models as filesystem_models
from app.routers.status import models as status_models
from app.types.scalars import (
    AllocationUnit,
    AllocationUnitValue,
    CompressionType,
    CompressionTypeValue,
    ResourceType,
    ResourceTypeValue,
    canonicalize_allocation_unit,
    validate_doe_iri_urn,
    urn_has_complete_prefix,
)


class DoeIriUrnTests(unittest.TestCase):
    def test_allocation_unit_legacy_token_normalizes_to_canonical_urn(self):
        self.assertEqual(
            canonicalize_allocation_unit("node_hours"),
            AllocationUnit.node_hours,
        )

    def test_resource_model_normalizes_legacy_type_to_canonical_urn(self):
        resource = status_models.Resource(
            id="resource-1",
            site_id="site-1",
            capability_ids=[],
            name="GPU Partition",
            description="Compute partition",
            last_modified="2026-05-12T12:00:00Z",
            current_status=status_models.Status.up,
            resource_type="compute",
        )
        self.assertEqual(resource.resource_type, ResourceType.compute)

    def test_unregistered_facility_resource_urn_is_accepted(self):
        resource = status_models.Resource(
            id="resource-1",
            site_id="site-1",
            capability_ids=[],
            name="XRootD Endpoint",
            description="Facility-local XRootD resource",
            last_modified="2026-05-12T12:00:00Z",
            current_status=status_models.Status.up,
            resource_type="urn:doe-iri:resource:xrootd",
        )
        self.assertEqual(resource.resource_type, "urn:doe-iri:resource:xrootd")

    def test_resource_find_supports_parent_prefix_matching(self):
        parent = status_models.Resource(
            id="resource-1",
            site_id="site-1",
            capability_ids=[],
            name="Scratch",
            description="Scratch filesystem",
            last_modified="2026-05-12T12:00:00Z",
            current_status=status_models.Status.up,
            resource_type="urn:doe-iri:resource:storage:filesystem:scratch",
        )
        matches = status_models.Resource.find([parent], resource_type=ResourceType.storage)
        self.assertEqual([item.id for item in matches], ["resource-1"])

    def test_unregistered_resource_subtype_matches_registered_parent(self):
        resource = status_models.Resource(
            id="resource-1",
            site_id="site-1",
            capability_ids=[],
            name="XRootD Storage",
            description="Facility-local storage subtype",
            last_modified="2026-05-12T12:00:00Z",
            current_status=status_models.Status.up,
            resource_type="urn:doe-iri:resource:storage:xrootd",
        )
        matches = status_models.Resource.find([resource], resource_type=ResourceType.storage)
        self.assertEqual([item.id for item in matches], ["resource-1"])

    def test_prefix_matching_requires_complete_segments(self):
        self.assertFalse(
            urn_has_complete_prefix(
                "urn:doe-iri:resource:stor",
                "urn:doe-iri:resource:storage:filesystem:scratch",
            )
        )

    def test_domain_specific_string_allows_rfc8141_slash(self):
        self.assertEqual(
            validate_doe_iri_urn("urn:doe-iri:resource:facility-code/scanner"),
            "urn:doe-iri:resource:facility-code/scanner",
        )

    def test_domain_specific_string_rejects_empty_hierarchy_segments(self):
        invalid_values = [
            "urn:doe-iri:resource::xrootd",
            "urn:doe-iri:resource:storage::xrootd",
            "urn:doe-iri:resource:storage:",
            "urn:doe-iri:resource::",
        ]
        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    validate_doe_iri_urn(value)

    def test_typed_urn_schemas_include_openapi_hints(self):
        cases = [
            (ResourceTypeValue, "resource", ResourceType.storage),
            (AllocationUnitValue, "allocation", AllocationUnit.node_hours),
            (CompressionTypeValue, "compression", CompressionType.gzip),
        ]
        for type_annotation, domain, example in cases:
            with self.subTest(domain=domain):
                schema = TypeAdapter(type_annotation).json_schema()
                self.assertEqual(schema["type"], "string")
                self.assertEqual(schema["minLength"], len(f"urn:doe-iri:{domain}:") + 1)
                self.assertIn("pattern", schema)
                self.assertRegex(example, schema["pattern"])
                self.assertIn("input compatibility aliases", schema["description"])

    def test_filesystem_request_normalizes_legacy_compression_token(self):
        request = filesystem_models.PostCompressRequest(
            path="/tmp/src",
            target_path="/tmp/out.tar.gz",
            compression="gzip",
        )
        self.assertEqual(request.compression, CompressionType.gzip)

    def test_filesystem_request_rejects_wrong_urn_domain(self):
        with self.assertRaises(ValueError):
            filesystem_models.PostExtractRequest(
                path="/tmp/archive.tar",
                target_path="/tmp/out",
                compression=ResourceType.storage,
            )


if __name__ == "__main__":
    unittest.main()
