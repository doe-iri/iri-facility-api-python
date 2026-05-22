#!/usr/bin/env python3
"""Focused tests for OIDC remote state caching in the IRI router."""

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("IRI_SHOW_MISSING_ROUTES", "true")

from app.routers import iri_router


class _FakeHttpxResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        return None


class _FakeAsyncClient:
    def __init__(self, responses: dict[str, dict], requests_seen: list[str], *args, **kwargs):
        self._responses = responses
        self._requests_seen = requests_seen

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url: str, headers: dict | None = None):
        self._requests_seen.append(url)
        if url not in self._responses:
            raise AssertionError(f"unexpected URL opened in test: {url}")
        return _FakeHttpxResponse(self._responses[url])


class OidcAuthTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        iri_router._oidc_remote_cache.clear()
        iri_router._oidc_remote_stale_cache.clear()

    async def test_load_oidc_remote_state_fetches_and_caches_with_async_httpx(self):
        discovery_uri = "https://identity.example.test/.well-known/openid-configuration"
        jwks_uri = "https://identity.example.test/oauth2/jwks"
        requests_seen = []
        responses = {
            discovery_uri: {
                "issuer": "https://identity.example.test/oauth2",
                "jwks_uri": jwks_uri,
            },
            jwks_uri: {"keys": []},
        }

        def fake_async_client(*args, **kwargs):
            return _FakeAsyncClient(responses, requests_seen, *args, **kwargs)

        with patch("app.routers.iri_router.httpx.AsyncClient", side_effect=fake_async_client), \
             patch("app.routers.iri_router.JsonWebKey.import_key_set", return_value="fake-key-set"):
            metadata, key_set = await iri_router._load_oidc_remote_state(discovery_uri)
            cached_metadata, cached_key_set = await iri_router._load_oidc_remote_state(discovery_uri)

        self.assertEqual(metadata["jwks_uri"], jwks_uri)
        self.assertEqual(key_set, "fake-key-set")
        self.assertEqual(cached_metadata, metadata)
        self.assertEqual(cached_key_set, key_set)
        self.assertEqual(requests_seen, [discovery_uri, jwks_uri])

    async def test_load_oidc_remote_state_reuses_stale_cache_on_refresh_failure(self):
        discovery_uri = "https://identity.example.test/.well-known/openid-configuration"
        cached_metadata = {"issuer": "https://identity.example.test/oauth2", "jwks_uri": "cached"}
        cached_key_set = object()
        iri_router._oidc_remote_stale_cache[discovery_uri] = (cached_metadata, cached_key_set)

        async def fail_fetch(uri: str):
            raise RuntimeError("temporary IdP outage")

        with patch("app.routers.iri_router._fetch_oidc_remote_state", side_effect=fail_fetch):
            metadata, key_set = await iri_router._load_oidc_remote_state(discovery_uri)

        self.assertIs(metadata, cached_metadata)
        self.assertIs(key_set, cached_key_set)


if __name__ == "__main__":
    unittest.main()
