#!/usr/bin/env python3
"""Regression tests for reverse-proxied absolute URL generation."""

import os
import unittest

from fastapi.testclient import TestClient

os.environ.setdefault("IRI_SHOW_MISSING_ROUTES", "true")

from app.main import APP


class ProxyPrefixUrlTests(unittest.TestCase):
    def test_status_resources_uses_forwarded_prefix_in_absolute_urls(self):
        client = TestClient(APP)

        response = client.get(
            "/api/v2/status/resources",
            headers={
                "x-forwarded-host": "localhost.rig.american-science-cloud.org",
                "x-forwarded-proto": "https",
                "x-forwarded-prefix": "/esnet-east",
            },
        )

        self.assertEqual(response.status_code, 200)
        resources = response.json()
        self.assertGreater(len(resources), 0)

        first = resources[0]
        self.assertTrue(
            first["self_uri"].startswith(
                "https://localhost.rig.american-science-cloud.org/esnet-east/api/v2/status/resources/"
            )
        )
        self.assertTrue(
            first["site_uri"].startswith(
                "https://localhost.rig.american-science-cloud.org/esnet-east/api/v2/facility/sites/"
            )
        )
        self.assertTrue(
            all(
                capability_uri.startswith(
                    "https://localhost.rig.american-science-cloud.org/esnet-east/api/v2/account/capabilities/"
                )
                for capability_uri in first["capability_uris"]
            )
        )


if __name__ == "__main__":
    unittest.main()
