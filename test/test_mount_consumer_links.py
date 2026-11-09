#!/usr/bin/env python3
"""Unit tests for iri:mounted-on and iri:accesses-mount, which link a mount and its consumers both ways."""

import unittest

from app.routers.status.models import Resource
from app.types.hal import RESOURCE_TYPE_PROFILE

MOUNT = "urn:doe-iri:resource:storage:mount"
COMPUTE_SYSTEM = "urn:doe-iri:resource:compute:system"
DTN = "urn:doe-iri:resource:service:dtn"
STATUS_LOGGER = "app.routers.status.models"


def _make_resource(resource_type, related_resource_ids):
    return Resource(
        id="res-1",
        site_id="site-1",
        resource_type=resource_type,
        related_resource_ids=related_resource_ids,
        last_modified="2026-02-21T12:00:00Z",
    )


class TestMountedOn(unittest.TestCase):
    def test_a_mount_can_name_more_than_one_consumer(self):
        links = _make_resource(MOUNT, {"mounted-on": ["compute-1", "dtn-1"]})._extra_links()

        hrefs = [link["href"] for link in links["iri:mounted-on"]]
        self.assertEqual(len(hrefs), 2)
        self.assertTrue(hrefs[0].endswith("/status/resources/compute-1"))
        self.assertTrue(hrefs[1].endswith("/status/resources/dtn-1"))

    def test_a_single_consumer_is_still_an_array(self):
        links = _make_resource(MOUNT, {"mounted-on": ["compute-1"]})._extra_links()

        self.assertIsInstance(links["iri:mounted-on"], list)
        self.assertEqual(len(links["iri:mounted-on"]), 1)

    def test_no_profile_is_claimed_because_the_target_type_varies(self):
        links = _make_resource(MOUNT, {"mounted-on": ["compute-1", "dtn-1"]})._extra_links()

        self.assertTrue(all("profile" not in link for link in links["iri:mounted-on"]))


class TestAccessesMount(unittest.TestCase):
    def test_compute_system_and_dtn_are_registered_sources(self):
        for resource_type in (COMPUTE_SYSTEM, DTN):
            with self.subTest(resource_type=resource_type), self.assertNoLogs(STATUS_LOGGER, level="WARNING"):
                links = _make_resource(resource_type, {"accesses-mount": ["mount-1"]})._extra_links()

                self.assertEqual(links["iri:accesses-mount"][0]["profile"], RESOURCE_TYPE_PROFILE[MOUNT])
                self.assertTrue(links["iri:accesses-mount"][0]["href"].endswith("/status/resources/mount-1"))

    def test_any_other_source_type_is_still_reported(self):
        with self.assertLogs(STATUS_LOGGER, level="WARNING"):
            _make_resource("urn:doe-iri:resource:storage:filesystem", {"accesses-mount": ["mount-1"]})


if __name__ == "__main__":
    unittest.main()
