#!/usr/bin/env python3
"""Focused regression tests for the remaining storage endpoint contract and OpenAPI wiring."""

import asyncio
import datetime
import os
import unittest

os.environ.setdefault("IRI_SHOW_MISSING_ROUTES", "true")

from app.demo_adapter import DemoAdapter
from app.main import APP
from app import config
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
        prefix = f"/{config.API_URL}"
        resolved_locations = self.openapi["paths"][f"{prefix}/storage/locations/{{resource_id}}"]["get"]
        self.assertNotIn(f"{prefix}/storage/locations", self.openapi["paths"])
        self.assertNotIn(f"{prefix}/storage/mounts/{{resource_id}}", self.openapi["paths"])
        self.assertTrue(
            resolved_locations["responses"]["200"]["content"]["application/json"]["schema"]["items"]["$ref"].endswith(
                "/StorageInstance"
            )
        )

    def test_access_endpoints_return_all_protocols_for_cfs(self):
        cfs_resource = self._resource("cfs", "cfs")

        endpoints = asyncio.run(
            self.adapter.get_access_endpoints(cfs_resource, None, None)
        )

        self.assertGreater(len(endpoints), 0)
        self.assertTrue(all(isinstance(e, storage_models.AccessEndpoint) for e in endpoints))
        protocols = {e.protocol for e in endpoints}
        self.assertEqual(
            protocols,
            {
                storage_models.AccessProtocol.globus,
                storage_models.AccessProtocol.xrootd,
                storage_models.AccessProtocol.s3,
            },
        )

    def test_access_endpoints_filter_by_protocol(self):
        cfs_resource = self._resource("cfs", "cfs")

        endpoints = asyncio.run(
            self.adapter.get_access_endpoints(cfs_resource, storage_models.AccessProtocol.globus, None)
        )

        self.assertEqual(len(endpoints), 1)
        self.assertEqual(endpoints[0].protocol, storage_models.AccessProtocol.globus)
        self.assertIsNotNone(endpoints[0].endpoint_id)
        self.assertIsNotNone(endpoints[0].uri)

    def test_access_endpoints_filter_by_endpoint_id(self):
        cfs_resource = self._resource("cfs", "cfs")

        endpoints = asyncio.run(
            self.adapter.get_access_endpoints(cfs_resource, None, "xrootd-cfs-demo")
        )

        self.assertEqual(len(endpoints), 1)
        self.assertEqual(endpoints[0].id, "xrootd-cfs-demo")
        self.assertEqual(endpoints[0].protocol, storage_models.AccessProtocol.xrootd)
        self.assertIsNotNone(endpoints[0].endpoint)

    def test_access_endpoints_hpss_has_only_globus(self):
        hpss_resource = self._resource("hpss", "hpss")

        endpoints = asyncio.run(
            self.adapter.get_access_endpoints(hpss_resource, None, None)
        )

        self.assertEqual(len(endpoints), 1)
        self.assertEqual(endpoints[0].protocol, storage_models.AccessProtocol.globus)

    def test_access_endpoints_unknown_resource_returns_empty(self):
        from app.routers.status import models as status_models

        fake_resource = status_models.Resource(
            id="does-not-exist",
            site_id="x",
            group="x",
            name="x",
            description="x",
            capability_ids=[],
            current_status=status_models.Status.up,
            resource_type=status_models.ResourceType.storage,
            last_modified=datetime.datetime.now(datetime.timezone.utc),
        )

        endpoints = asyncio.run(
            self.adapter.get_access_endpoints(fake_resource, None, None)
        )

        self.assertEqual(endpoints, [])

    def test_openapi_exposes_access_endpoints_path(self):
        prefix = f"/{config.API_URL}"
        path = self.openapi["paths"][f"{prefix}/storage/{{resource_id}}/access-endpoints"]["get"]
        self.assertTrue(
            path["responses"]["200"]["content"]["application/json"]["schema"]["items"]["$ref"].endswith(
                "/AccessEndpoint"
            )
        )


if __name__ == "__main__":
    unittest.main()
