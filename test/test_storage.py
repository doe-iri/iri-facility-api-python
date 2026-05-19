#!/usr/bin/env python3
"""Focused regression tests for the remaining storage endpoint contract and OpenAPI wiring."""

import asyncio
import os
import unittest

os.environ.setdefault("IRI_SHOW_MISSING_ROUTES", "true")

from app.demo_adapter import DemoAdapter
from app.main import APP
from app.routers.storage import models as storage_models


class StorageEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.adapter = DemoAdapter()
        cls.user = cls.adapter.user
        cls.openapi = APP.openapi()

    @classmethod
    def _resource(cls, group: str, name: str):
        for resource in cls.adapter.resources:
            if resource.group == group and resource.name == name:
                return resource
        raise AssertionError(f"Unable to find resource {group}/{name}")

    def test_resolved_locations_return_shared_storage_instance_shape(self):
        compute_resource = self._resource("perlmutter", "compute nodes")

        payload = asyncio.run(
            self.adapter.get_locations(
                compute_resource,
                self.user,
                None,
                None,
                None,
                None,
            )
        )

        self.assertGreater(len(payload), 0)
        self.assertTrue(all(isinstance(item, storage_models.StorageInstance) for item in payload))

        first = payload[0].model_dump()
        self.assertEqual(
            set(first.keys()),
            {
                "logical_name",
                "path",
                "filesystem",
                "performance_tier",
                "quota_bytes",
                "available_bytes",
                "purge_policy_days",
                "shared",
                "access",
            },
        )
        home_entries = [entry for entry in payload if entry.logical_name == storage_models.LogicalName.home]
        self.assertEqual(len(home_entries), 1)
        self.assertFalse(home_entries[0].access.write)

    def test_project_scoped_entries_expand_under_remaining_locations_endpoint(self):
        login_resource = self._resource("perlmutter", "login nodes")

        location_payload = asyncio.run(
            self.adapter.get_locations(
                login_resource,
                self.user,
                storage_models.LogicalName.shared,
                None,
                None,
                None,
            )
        )

        self.assertGreater(len(location_payload), 0)
        self.assertTrue(
            all(entry.logical_name == storage_models.LogicalName.shared for entry in location_payload)
        )
        self.assertTrue(
            all(not entry.access.write for entry in location_payload)
        )
        self.assertEqual(len(location_payload), len(self.adapter._user_project_codes(self.user)))

    def test_openapi_exposes_only_resource_scoped_storage_locations(self):
        resolved_locations = self.openapi["paths"]["/api/v1/storage/locations/{resource_id}"]["get"]
        self.assertNotIn("/api/v1/storage/locations", self.openapi["paths"])
        self.assertNotIn("/api/v1/storage/mounts/{resource_id}", self.openapi["paths"])
        self.assertTrue(
            resolved_locations["responses"]["200"]["content"]["application/json"]["schema"]["items"]["$ref"].endswith(
                "/StorageInstance"
            )
        )


if __name__ == "__main__":
    unittest.main()
