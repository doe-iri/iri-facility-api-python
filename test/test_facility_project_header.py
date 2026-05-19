#!/usr/bin/env python3
"""Regression tests for facility-project header propagation into compute submission."""

import os
import unittest

from fastapi.testclient import TestClient

os.environ.setdefault("IRI_SHOW_MISSING_ROUTES", "true")

from app.main import APP


class FacilityProjectHeaderTests(unittest.TestCase):
    def test_compute_submit_uses_forwarded_facility_project_header(self):
        client = TestClient(APP)

        resources_response = client.get("/api/v1/status/resources")
        self.assertEqual(resources_response.status_code, 200)
        resource_id = resources_response.json()[0]["id"]

        response = client.post(
            f"/api/v1/compute/job/{resource_id}",
            headers={
                "authorization": "Bearer 12345",
                "x-iri-facility-project": "ns011",
            },
            json={"executable": "/bin/echo", "arguments": ["hello"]},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"]["meta_data"]["account"], "ns011")

    def test_compute_submit_uses_job_spec_account_when_header_absent(self):
        client = TestClient(APP)

        resources_response = client.get("/api/v1/status/resources")
        self.assertEqual(resources_response.status_code, 200)
        resource_id = resources_response.json()[0]["id"]

        response = client.post(
            f"/api/v1/compute/job/{resource_id}",
            headers={"authorization": "Bearer 12345"},
            json={
                "executable": "/bin/echo",
                "arguments": ["hello"],
                "attributes": {"account": "ns011"},
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"]["meta_data"]["account"], "ns011")

    def test_compute_submit_rejects_missing_project_account(self):
        client = TestClient(APP)

        resources_response = client.get("/api/v1/status/resources")
        self.assertEqual(resources_response.status_code, 200)
        resource_id = resources_response.json()[0]["id"]

        response = client.post(
            f"/api/v1/compute/job/{resource_id}",
            headers={"authorization": "Bearer 12345"},
            json={"executable": "/bin/echo", "arguments": ["hello"]},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("exactly one place", response.json()["detail"])

    def test_compute_submit_rejects_duplicate_project_account_sources(self):
        client = TestClient(APP)

        resources_response = client.get("/api/v1/status/resources")
        self.assertEqual(resources_response.status_code, 200)
        resource_id = resources_response.json()[0]["id"]

        response = client.post(
            f"/api/v1/compute/job/{resource_id}",
            headers={
                "authorization": "Bearer 12345",
                "x-iri-facility-project": "ns011",
            },
            json={
                "executable": "/bin/echo",
                "arguments": ["hello"],
                "attributes": {"account": "also-present"},
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("not both", response.json()["detail"])

    def test_compute_submit_requires_authorization_before_project_validation(self):
        client = TestClient(APP)

        response = client.post(
            "/api/v1/compute/job/0",
            json={"executable": "/bin/echo", "arguments": ["hello"]},
        )

        self.assertEqual(response.status_code, 401)

    def test_compute_update_requires_authorization_before_project_validation(self):
        client = TestClient(APP)

        response = client.put(
            "/api/v1/compute/job/0/0",
            json={"executable": "/bin/echo", "arguments": ["hello"]},
        )

        self.assertEqual(response.status_code, 401)

    def test_compute_submit_malformed_attributes_does_not_500(self):
        client = TestClient(APP)
        resources_response = client.get("/api/v1/status/resources")
        self.assertEqual(resources_response.status_code, 200)
        resource_id = resources_response.json()[0]["id"]

        response = client.post(
            f"/api/v1/compute/job/{resource_id}",
            headers={"authorization": "Bearer 12345"},
            json={"executable": "/bin/echo", "arguments": ["hello"], "attributes": [None, None]},
        )

        self.assertIn(response.status_code, {400, 422})

    def test_compute_update_malformed_attributes_does_not_500(self):
        client = TestClient(APP)
        resources_response = client.get("/api/v1/status/resources")
        self.assertEqual(resources_response.status_code, 200)
        resource_id = resources_response.json()[0]["id"]

        response = client.put(
            f"/api/v1/compute/job/{resource_id}/0",
            headers={"authorization": "Bearer 12345"},
            json={"executable": "/bin/echo", "arguments": ["hello"], "attributes": [None, None]},
        )

        self.assertIn(response.status_code, {400, 422})


if __name__ == "__main__":
    unittest.main()
