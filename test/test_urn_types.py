#!/usr/bin/env python3
"""DOE IRI URN type regression tests."""

import unittest

from pydantic import TypeAdapter, ValidationError

from app.routers.filesystem import models as filesystem_models
from app.routers.status import models as status_models
from app.types.scalars import (
    AllocationUnit,
    AllocationUnitValue,
    CompressionType,
    CompressionTypeValue,
    ResourceType,
    ResourceTypeValue,
    validate_doe_iri_urn,
    urn_has_complete_prefix,
)


def _resource(**kw):
    defaults = dict(
        id="r-1",
        site_id="site-1",
        capability_ids=[],
        name="R",
        description="desc",
        last_modified="2026-05-12T12:00:00Z",
        current_status=status_models.Status.up,
    )
    return status_models.Resource(**(defaults | kw))


class EnumBehaviorTests(unittest.TestCase):
    """str(Enum) contracts: value equality, membership, iteration."""

    def test_resource_type_is_str(self):
        self.assertIsInstance(ResourceType.compute, str)
        self.assertEqual(ResourceType.compute, "urn:doe-iri:resource:compute")

    def test_allocation_unit_is_str(self):
        self.assertIsInstance(AllocationUnit.node_hours, str)
        self.assertEqual(AllocationUnit.node_hours, "urn:doe-iri:allocation:compute:node-hours")

    def test_compression_type_is_str(self):
        self.assertIsInstance(CompressionType.gzip, str)
        self.assertEqual(CompressionType.gzip, "urn:doe-iri:compression:gzip")

    def test_enum_lookup_by_value(self):
        self.assertIs(ResourceType("urn:doe-iri:resource:storage"), ResourceType.storage)
        self.assertIs(AllocationUnit("urn:doe-iri:allocation:storage:inodes"), AllocationUnit.inodes)
        self.assertIs(CompressionType("urn:doe-iri:compression:bzip2"), CompressionType.bzip2)

    def test_resource_type_members(self):
        urns = {m.value for m in ResourceType}
        self.assertIn("urn:doe-iri:resource:compute", urns)
        self.assertIn("urn:doe-iri:resource:storage", urns)
        self.assertIn("urn:doe-iri:service:generic", urns)

    def test_service_lives_in_service_domain(self):
        """spec §3.1: legacy 'service' enum → urn:doe-iri:service:generic."""
        self.assertEqual(ResourceType.service, "urn:doe-iri:service:generic")
        self.assertTrue(ResourceType.service.startswith("urn:doe-iri:service:"))

    def test_website_lives_in_service_domain(self):
        """spec §3.1: legacy 'website' enum → urn:doe-iri:service:website."""
        self.assertEqual(ResourceType.website, "urn:doe-iri:service:website")
        self.assertTrue(ResourceType.website.startswith("urn:doe-iri:service:"))

    def test_all_allocation_units_in_allocation_domain(self):
        for member in AllocationUnit:
            self.assertTrue(member.value.startswith("urn:doe-iri:allocation:"), member.value)

    def test_all_compression_types_in_compression_domain(self):
        for member in CompressionType:
            self.assertTrue(member.value.startswith("urn:doe-iri:compression:"), member.value)


class UrnValidatorTests(unittest.TestCase):
    """validate_doe_iri_urn and urn_has_complete_prefix."""

    def test_valid_urn_passes(self):
        self.assertEqual(validate_doe_iri_urn("urn:doe-iri:resource:compute"), "urn:doe-iri:resource:compute")

    def test_domain_specific_string_allows_rfc8141_slash(self):
        self.assertEqual(
            validate_doe_iri_urn("urn:doe-iri:resource:facility-code/scanner"),
            "urn:doe-iri:resource:facility-code/scanner",
        )

    def test_empty_hierarchy_segments_rejected(self):
        for bad in [
            "urn:doe-iri:resource::xrootd",
            "urn:doe-iri:resource:storage::xrootd",
            "urn:doe-iri:resource:storage:",
            "urn:doe-iri:resource::",
        ]:
            with self.subTest(value=bad):
                with self.assertRaises(ValueError):
                    validate_doe_iri_urn(bad)

    def test_prefix_matching_requires_complete_segments(self):
        self.assertFalse(
            urn_has_complete_prefix(
                "urn:doe-iri:resource:stor",
                "urn:doe-iri:resource:storage:filesystem:scratch",
            )
        )

    def test_prefix_matching_exact(self):
        self.assertTrue(
            urn_has_complete_prefix(
                "urn:doe-iri:resource:storage",
                "urn:doe-iri:resource:storage",
            )
        )

    def test_prefix_matching_parent(self):
        self.assertTrue(
            urn_has_complete_prefix(
                "urn:doe-iri:resource:storage",
                "urn:doe-iri:resource:storage:filesystem:scratch",
            )
        )


class ResourceTypeFieldTests(unittest.TestCase):
    """ResourceTypeValue: open to any valid DOE IRI URN."""

    def test_canonical_enum_value_accepted(self):
        r = _resource(resource_type=ResourceType.compute)
        self.assertEqual(r.resource_type, ResourceType.compute)

    def test_raw_canonical_string_accepted(self):
        r = _resource(resource_type="urn:doe-iri:resource:compute")
        self.assertEqual(r.resource_type, "urn:doe-iri:resource:compute")

    def test_service_urn_accepted_despite_service_domain(self):
        """ResourceTypeValue must accept service domain URNs (spec §3.1 maps service → urn:doe-iri:service:generic)."""
        r = _resource(resource_type=ResourceType.service)
        self.assertEqual(r.resource_type, "urn:doe-iri:service:generic")

    def test_facility_local_extension_accepted(self):
        r = _resource(resource_type="urn:doe-iri:resource:xrootd")
        self.assertEqual(r.resource_type, "urn:doe-iri:resource:xrootd")

    def test_short_token_rejected(self):
        """Legacy short tokens are no longer accepted."""
        with self.assertRaises(Exception):
            _resource(resource_type="compute")

    def test_garbage_rejected(self):
        with self.assertRaises(Exception):
            _resource(resource_type="not-a-urn")

    def test_prefix_find_matches_subtype(self):
        parent = _resource(resource_type="urn:doe-iri:resource:storage:filesystem:scratch")
        matches = status_models.Resource.find([parent], resource_type=ResourceType.storage)
        self.assertEqual([r.id for r in matches], ["r-1"])

    def test_prefix_find_unregistered_subtype(self):
        r = _resource(resource_type="urn:doe-iri:resource:storage:xrootd")
        matches = status_models.Resource.find([r], resource_type=ResourceType.storage)
        self.assertEqual([i.id for i in matches], ["r-1"])


class AllocationUnitFieldTests(unittest.TestCase):
    """AllocationUnitValue: allocation domain enforced."""

    def test_canonical_value_accepted(self):
        ta = TypeAdapter(AllocationUnitValue)
        self.assertEqual(ta.validate_python(AllocationUnit.node_hours), AllocationUnit.node_hours)

    def test_wrong_domain_rejected(self):
        ta = TypeAdapter(AllocationUnitValue)
        with self.assertRaises((ValueError, ValidationError)):
            ta.validate_python(ResourceType.storage)

    def test_short_token_rejected(self):
        ta = TypeAdapter(AllocationUnitValue)
        with self.assertRaises((ValueError, ValidationError)):
            ta.validate_python("node-hours")


class CompressionTypeFieldTests(unittest.TestCase):
    """CompressionTypeValue: compression domain enforced."""

    def test_canonical_value_accepted(self):
        req = filesystem_models.PostCompressRequest(
            path="/tmp/src",
            target_path="/tmp/out.tar.gz",
            compression=CompressionType.gzip,
        )
        self.assertEqual(req.compression, CompressionType.gzip)

    def test_wrong_domain_rejected(self):
        with self.assertRaises(Exception):
            filesystem_models.PostExtractRequest(
                path="/tmp/archive.tar",
                target_path="/tmp/out",
                compression=ResourceType.storage,
            )

    def test_short_token_rejected(self):
        with self.assertRaises(Exception):
            filesystem_models.PostCompressRequest(
                path="/tmp/src",
                target_path="/tmp/out.tar.gz",
                compression="gzip",
            )


class OpenApiSchemaTests(unittest.TestCase):
    """JSON schema hints are emitted correctly."""

    def test_resource_type_schema(self):
        schema = TypeAdapter(ResourceTypeValue).json_schema()
        self.assertEqual(schema["type"], "string")
        self.assertIn("doe-iri", schema["description"])

    def test_allocation_unit_schema_has_domain_pattern(self):
        schema = TypeAdapter(AllocationUnitValue).json_schema()
        self.assertIn("allocation", schema["pattern"])
        self.assertEqual(schema["minLength"], len("urn:doe-iri:allocation:") + 1)

    def test_compression_type_schema_has_domain_pattern(self):
        schema = TypeAdapter(CompressionTypeValue).json_schema()
        self.assertIn("compression", schema["pattern"])
        self.assertRegex(CompressionType.gzip, schema["pattern"])


if __name__ == "__main__":
    unittest.main()
