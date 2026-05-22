#!/usr/bin/env python3
"""Focused tests for OIDC JWT authentication in the IRI router."""

import json
import os
import unittest
from unittest.mock import patch
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest, urlopen

from fastapi.testclient import TestClient

os.environ.setdefault("IRI_SHOW_MISSING_ROUTES", "true")

from app.main import APP
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


def _exchange_live_authorization_code() -> str:
    token_endpoint = os.environ["OIDC_TOKEN_ENDPOINT"]
    client_id = os.environ["OIDC_CLIENT_ID"]
    client_secret = os.environ["OIDC_CLIENT_SECRET"]
    redirect_uri = os.environ.get("OIDC_REDIRECT_URI", "urn:ietf:wg:oauth:2.0:oob")
    authorization_code = os.environ["OIDC_AUTHORIZATION_CODE"]

    request = UrlRequest(
        token_endpoint,
        data=urlencode(
            {
                "grant_type": "authorization_code",
                "client_id": client_id,
                "client_secret": client_secret,
                "code": authorization_code,
                "redirect_uri": redirect_uri,
            }
        ).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    with urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    access_token = payload.get("access_token")
    if not access_token:
        raise AssertionError(f"No access_token found in live token response: {payload}")
    return access_token


class OidcAuthTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        iri_router._oidc_remote_cache.clear()

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
        iri_router._oidc_remote_cache[discovery_uri] = (0, cached_metadata, cached_key_set)

        async def fail_fetch(uri: str):
            raise RuntimeError("temporary IdP outage")

        with patch("app.routers.iri_router._fetch_oidc_remote_state", side_effect=fail_fetch):
            metadata, key_set = await iri_router._load_oidc_remote_state(discovery_uri)

        self.assertIs(metadata, cached_metadata)
        self.assertIs(key_set, cached_key_set)

    def test_account_projects_accepts_live_oidc_token_when_configured(self):
        discovery_uri = os.environ.get("OIDC_DISCOVERY_URI")
        client_id = os.environ.get("OIDC_CLIENT_ID")
        client_secret = os.environ.get("OIDC_CLIENT_SECRET")
        live_access_token = os.environ.get("OIDC_LIVE_ACCESS_TOKEN")
        authorization_code = os.environ.get("OIDC_AUTHORIZATION_CODE")
        token_endpoint = os.environ.get("OIDC_TOKEN_ENDPOINT")

        if not discovery_uri or not client_id:
            self.skipTest("Live OIDC test requires OIDC_DISCOVERY_URI and OIDC_CLIENT_ID.")
        if not live_access_token and not authorization_code:
            self.skipTest("Live OIDC test requires OIDC_LIVE_ACCESS_TOKEN or OIDC_AUTHORIZATION_CODE.")
        if authorization_code and (not token_endpoint or not client_secret):
            self.skipTest("Live OIDC authorization-code exchange requires OIDC_TOKEN_ENDPOINT and OIDC_CLIENT_SECRET.")

        access_token = live_access_token or _exchange_live_authorization_code()
        client = TestClient(APP)
        response = client.get("/api/v1/account/projects", headers={"authorization": f"Bearer {access_token}"})

        print(f"LIVE OIDC token: {access_token}")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertGreaterEqual(len(response.json()), 1)


if __name__ == "__main__":
    unittest.main()
