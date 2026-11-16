"""Unit tests for registered iri:* relation links on Resource, Event, Incident, Facility, Site and Capability."""

import unittest

from app.routers.facility.models import Facility, Site
from app.routers.status.models import Event, Incident, Resource
from app.types.hal import (
    PROFILE_ACCOUNT_CAPABILITY,
    PROFILE_STATUS_EVENT,
    PROFILE_STATUS_INCIDENT,
    PROFILE_STATUS_RESOURCE,
    RESOURCE_TYPE_PROFILE,
)
from app.types.models import Capability

NOW = "2026-02-21T12:00:00Z"
MOUNT = "urn:doe-iri:resource:storage:mount"
STATUS_LOGGER = "app.routers.status.models"


def _resource(resource_type, related_resource_ids):
    return Resource(
        id="res-1",
        site_id="site-1",
        resource_type=resource_type,
        related_resource_ids=related_resource_ids,
        last_modified=NOW,
    )


class TestAccessesMount(unittest.TestCase):
    """accesses-mount 1.1.0: any configured filesystem consumer can be the source."""

    def test_any_consumer_type_is_a_valid_source(self):
        for resource_type in (
            "urn:doe-iri:resource:compute",
            "urn:doe-iri:resource:compute:system",
            "urn:doe-iri:resource:compute:node",
            "urn:doe-iri:resource:service",
            "urn:doe-iri:resource:service:dtn",
            "urn:doe-iri:resource:service:inference",
        ):
            with self.subTest(resource_type=resource_type), self.assertNoLogs(STATUS_LOGGER, level="WARNING"):
                links = _resource(resource_type, {"accesses-mount": ["mount-1", "mount-2"]})._extra_links()

                targets = links["iri:accesses-mount"]
                self.assertEqual(len(targets), 2)
                self.assertTrue(targets[0]["href"].endswith("/status/resources/mount-1"))
                self.assertTrue(all(t["profile"] == RESOURCE_TYPE_PROFILE[MOUNT] for t in targets))

    def test_a_single_mount_is_still_an_array(self):
        links = _resource("urn:doe-iri:resource:compute:node", {"accesses-mount": ["mount-1"]})._extra_links()

        self.assertIsInstance(links["iri:accesses-mount"], list)


class TestAccessedBy(unittest.TestCase):
    """accessed-by 1.0.0: inverse of accesses-mount, from exactly a mount to any consumer."""

    def test_mount_lists_its_consumers_with_the_generic_resource_profile(self):
        with self.assertNoLogs(STATUS_LOGGER, level="WARNING"):
            links = _resource(MOUNT, {"mounted-on": ["system-1"], "accessed-by": ["system-1", "dtn-1"]})._extra_links()

        consumers = links["iri:accessed-by"]
        self.assertEqual([c["href"].rsplit("/", 1)[-1] for c in consumers], ["system-1", "dtn-1"])
        self.assertTrue(all(c["profile"] == PROFILE_STATUS_RESOURCE for c in consumers))

    def test_consumers_do_not_change_the_single_mounted_on_target(self):
        links = _resource(MOUNT, {"mounted-on": ["system-1"], "accessed-by": ["system-1", "dtn-1"]})._extra_links()

        self.assertIsInstance(links["iri:mounted-on"], dict)
        self.assertEqual(links["iri:mounted-on"]["profile"], RESOURCE_TYPE_PROFILE["urn:doe-iri:resource:compute:system"])

    def test_mounted_on_still_rejects_more_than_one_system(self):
        with self.assertRaises(ValueError):
            _resource(MOUNT, {"mounted-on": ["system-1", "dtn-1"]})

    def test_a_non_mount_source_is_reported(self):
        with self.assertLogs(STATUS_LOGGER, level="WARNING"):
            _resource("urn:doe-iri:resource:service:dtn", {"accessed-by": ["system-1"]})

    def test_no_consumers_means_no_link(self):
        links = _resource(MOUNT, {"accessed-by": []})._extra_links()

        self.assertNotIn("iri:accessed-by", links)


class TestEventLinks(unittest.TestCase):

    def test_event_links_its_resource_and_incident(self):
        event = Event(id="ev-1", occurred_at=NOW, status="down", resource_id="res-1", incident_id="inc-1", last_modified=NOW)

        links = event._links
        self.assertEqual(links["self"]["profile"], PROFILE_STATUS_EVENT)
        self.assertEqual(links["iri:impacts"]["href"], event.resource_uri)
        self.assertEqual(links["iri:impacts"]["profile"], PROFILE_STATUS_RESOURCE)
        self.assertEqual(links["iri:generated-by"]["href"], event.incident_uri)
        self.assertEqual(links["iri:generated-by"]["profile"], PROFILE_STATUS_INCIDENT)

    def test_null_incident_uri_omits_generated_by(self):
        event = Event(id="ev-1", occurred_at=NOW, status="up", resource_id="res-1", last_modified=NOW)

        self.assertIsNone(event.incident_uri)
        self.assertNotIn("iri:generated-by", event._links)


class TestIncidentLinks(unittest.TestCase):

    def _incident(self, **kwargs):
        return Incident(id="inc-1", status="down", start=NOW, type="planned", resolution="pending", last_modified=NOW, **kwargs)

    def test_incident_links_events_and_possibly_impacted_resources(self):
        incident = self._incident(event_ids=["ev-1", "ev-2"], resource_ids=["res-1"])

        links = incident._links
        self.assertEqual(links["self"]["profile"], PROFILE_STATUS_INCIDENT)
        self.assertEqual([link["href"] for link in links["iri:has-event"]], incident.event_uris)
        self.assertTrue(all(link["profile"] == PROFILE_STATUS_EVENT for link in links["iri:has-event"]))
        self.assertEqual([link["href"] for link in links["iri:may-impact"]], incident.resource_uris)
        self.assertTrue(all(link["profile"] == PROFILE_STATUS_RESOURCE for link in links["iri:may-impact"]))

    def test_empty_lists_omit_the_links(self):
        links = self._incident()._links

        self.assertNotIn("iri:has-event", links)
        self.assertNotIn("iri:may-impact", links)


class TestFacilityAndSiteLinks(unittest.TestCase):

    def test_support_uri_maps_to_help(self):
        facility = Facility(id="fac-1", support_uri="https://support.example.org/", last_modified=NOW)

        self.assertEqual(facility._links["help"], {"href": "https://support.example.org/"})

    def test_no_support_uri_omits_help(self):
        self.assertNotIn("help", Facility(id="fac-1", last_modified=NOW)._links)

    def test_site_resources_use_the_generic_resource_profile(self):
        site = Site(id="site-1", operating_organization="Org", resource_ids=["res-1"], last_modified=NOW)

        self.assertEqual(site._links["iri:has-resource"][0]["profile"], PROFILE_STATUS_RESOURCE)

    def test_capability_self_link_has_its_profile(self):
        capability = Capability(id="cap-1", units=["urn:doe-iri:allocation:compute:node-hours"])

        self.assertEqual(capability._links["self"]["profile"], PROFILE_ACCOUNT_CAPABILITY)


if __name__ == "__main__":
    unittest.main()
