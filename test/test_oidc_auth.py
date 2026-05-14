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


class _FakeHTTPResponse:
    def __init__(self, payload: dict):
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeSigningKey:
    def __init__(self, key: str):
        self.key = key


class _FakeJwksClient:
    def get_signing_key_from_jwt(self, token: str) -> _FakeSigningKey:
        return _FakeSigningKey("fake-public-key")


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


class OidcAuthTests(unittest.TestCase):
    def setUp(self):
        iri_router._oidc_remote_cache.clear()

    def test_account_projects_accepts_configured_oidc_token(self):
        discovery_uri = "https://identity.example.test/.well-known/openid-configuration"
        jwks_uri = "https://identity.example.test/oauth2/jwks"
        access_token = "accepted-oidc-token"
        requests_seen = []

        def fake_urlopen(request, timeout=10):
            requests_seen.append(request)
            if request.full_url == discovery_uri:
                return _FakeHTTPResponse(
                    {"issuer": "https://identity.example.test/oauth2", "jwks_uri": jwks_uri}
                )
            raise AssertionError(f"unexpected URL opened in test: {request.full_url}")

        client = TestClient(APP)
        with patch.dict(
            os.environ,
            {
                "OIDC_DISCOVERY_URI": discovery_uri,
                "OIDC_CLIENT_ID": "test-client-id",
                "OIDC_REQUIRED_SCOPES": "openid email",
            },
            clear=False,
        ):
            with patch("app.routers.iri_router.urlopen", side_effect=fake_urlopen), \
                 patch("app.routers.iri_router.PyJWKClient", return_value=_FakeJwksClient()), \
                 patch(
                     "app.routers.iri_router.jwt.decode",
                     return_value={
                         "scope": ["openid", "profile", "email"],
                         "sub": "oidc-user-123",
                         "exp": 4102444800,
                         "iat": 1700000000,
                         "nbf": 1700000000,
                         "iss": "https://identity.example.test/oauth2",
                         "aud": "test-client-id",
                     },
                 ) as decode_mock:
                response = client.get("/api/v1/account/projects", headers={"authorization": f"Bearer {access_token}"})

        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.json()), 1)
        print(f"OIDC test token: {access_token}")
        self.assertEqual(requests_seen[0].full_url, discovery_uri)
        self.assertEqual(len(requests_seen), 1)
        self.assertEqual(decode_mock.call_args.kwargs["audience"], "test-client-id")
        self.assertEqual(decode_mock.call_args.kwargs["issuer"], "https://identity.example.test/oauth2")

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
