"""
Dex JWT verifier for S3DF.

Two modes:
1. JWKS live — verifies against `PyJWKClient` with its own 300s cache.
2. Pinned PEM — reads the key from a local file. A background daemon thread
   (started at S3DF module import time, before the event loop exists) keeps
   the file fresh by re-fetching Dex's JWKS on a fixed interval. Used when
   the runtime host can't validate Dex's TLS chain (SLAC dev boxes missing
   the internal CA).
"""

import asyncio
import json
import logging
import os
import ssl
import threading
import time
import urllib.request
from functools import lru_cache
from typing import Optional

import jwt
from cryptography.hazmat.primitives import serialization
from fastapi import HTTPException
from jwt import PyJWKClient, PyJWKClientError

from app.s3df.config import settings

LOG = logging.getLogger(__name__)


@lru_cache(maxsize=4)
def _load_pem(path: str, mtime_ns: int):
    with open(path, "rb") as f:
        return serialization.load_pem_public_key(f.read())


def _public_key_from_file(path: str):
    # mtime is part of the cache key so an out-of-band rewrite invalidates
    # the cached key on the next stat() — no restart, no signal.
    return _load_pem(path, os.stat(path).st_mtime_ns)


def _fetch_and_write_pem(jwks_url: str, dest_path: str) -> str:
    """Blocking: fetch JWKS, pick the RSA signing key, write PEM atomically.

    Returns the kid of the written key. Uses an unverified SSL context because
    this runs against hosts whose CA isn't in the default trust store — the
    exact reason we're pinning. Integrity is preserved by the JWT *signature*
    check against the resulting PEM.
    """
    ctx = ssl._create_unverified_context()
    with urllib.request.urlopen(jwks_url, context=ctx) as resp:
        jwks = json.loads(resp.read())

    sig_keys = [
        k for k in jwks.get("keys", [])
        if k.get("kty") == "RSA" and k.get("use", "sig") == "sig"
    ]
    if not sig_keys:
        raise RuntimeError(f"No RSA signing key found in JWKS at {jwks_url}")

    key = sig_keys[0]
    pem = jwt.PyJWK(key).key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    tmp = dest_path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(pem)
    os.replace(tmp, dest_path)
    return key.get("kid", "?")


_refresh_thread: Optional[threading.Thread] = None
_refresh_lock = threading.Lock()


def _refresh_thread_loop(jwks_url: str, dest_path: str, interval_s: int) -> None:
    while True:
        time.sleep(interval_s)
        try:
            kid = _fetch_and_write_pem(jwks_url, dest_path)
            LOG.info("Refreshed pinned Dex key at %s (kid=%s)", dest_path, kid)
        except Exception:
            LOG.exception("Dex key refresh failed; will retry in %ds", interval_s)


def ensure_pinned_key_refresh_started() -> None:
    """Bootstrap the PEM from Dex and launch the background refresh thread.

    Idempotent — subsequent calls are no-ops. Called at S3DF module import
    time so the PEM exists (and the lru_cache is populated) before the first
    client request. Startup ordering:

        1. Fetch PEM from Dex and write to disk (blocking).
        2. Pre-load the lru_cache so verify() is a pure in-memory read.
        3. Spawn a daemon thread that re-fetches every interval seconds.

    Behavior on failure:
      - Fetch fails + PEM already on disk → log warning, continue with stale
        key, background thread keeps retrying.
      - Fetch fails + no PEM → raise RuntimeError so the server fails to
        start with a clear message.
    """
    global _refresh_thread
    with _refresh_lock:
        if _refresh_thread is not None and _refresh_thread.is_alive():
            return

        jwks_url = settings.dex_jwks_url
        dest = settings.dex_jwt_public_key
        interval = settings.dex_jwt_refresh_interval_seconds

        if not jwks_url or not dest:
            LOG.warning(
                "Pinned key refresh not started — DEX_JWKS_URL or DEX_JWT_PUBLIC_KEY missing"
            )
            return

        try:
            kid = _fetch_and_write_pem(jwks_url, dest)
            LOG.info("Bootstrapped pinned Dex key at %s (kid=%s)", dest, kid)
            # Warm the lru_cache so verify() is a pure in-memory read.
            _public_key_from_file(dest)
        except Exception as exc:
            if os.path.exists(dest):
                LOG.warning(
                    "Could not fetch Dex key at startup (%s); using cached PEM at %s",
                    exc, dest,
                )
            else:
                raise RuntimeError(
                    f"Unable to bootstrap pinned Dex key from {jwks_url}: {exc}"
                ) from exc

        _refresh_thread = threading.Thread(
            target=_refresh_thread_loop,
            args=(jwks_url, dest, interval),
            daemon=True,
            name="dex-jwks-refresh",
        )
        _refresh_thread.start()
        LOG.info("Started Dex key refresh thread (interval=%ds)", interval)


class JwtVerifier:
    """Verifies Dex-issued JWTs via JWKS and returns the username claim."""

    def __init__(
        self,
        jwks_url: str,
        issuer: str,
        audience: str,
        username_claim: str = "name",
        public_key_path: Optional[str] = None,
    ):
        self.jwks_url = jwks_url
        self.issuer = issuer
        self.audience = audience
        self.username_claim = username_claim
        self.public_key_path = public_key_path
        if public_key_path:
            self._jwks_client = None
        else:
            # PyJWKClient caches keys for `lifespan` seconds (default 300).
            self._jwks_client = PyJWKClient(jwks_url)

    async def verify(self, token: str) -> str:
        """
        Verify token signature, exp, iss, aud; return the username claim.
        Raises HTTPException(401) on any verification failure.
        """
        if self.public_key_path:
            try:
                signing_key_material = _public_key_from_file(self.public_key_path)
            except FileNotFoundError as exc:
                LOG.error("Pinned public key missing at %s", self.public_key_path)
                raise HTTPException(status_code=503, detail="Auth provider unavailable") from exc
        else:
            loop = asyncio.get_running_loop()
            try:
                signing_key = await loop.run_in_executor(
                    None, self._jwks_client.get_signing_key_from_jwt, token
                )
            except PyJWKClientError as exc:
                LOG.warning("JWKS lookup failed: %s", exc)
                raise HTTPException(status_code=401, detail="Untrusted token") from exc
            except Exception as exc:
                LOG.error("JWKS endpoint unreachable: %s", exc)
                raise HTTPException(status_code=503, detail="Auth provider unavailable") from exc
            signing_key_material = signing_key.key

        try:
            payload = jwt.decode(
                token,
                signing_key_material,
                algorithms=["RS256"],
                audience=self.audience,
                issuer=self.issuer,
            )
        except jwt.ExpiredSignatureError as exc:
            raise HTTPException(status_code=401, detail="Token expired") from exc
        except jwt.InvalidAudienceError as exc:
            raise HTTPException(status_code=401, detail="Token audience mismatch") from exc
        except jwt.InvalidIssuerError as exc:
            raise HTTPException(status_code=401, detail="Token issuer mismatch") from exc
        except jwt.InvalidTokenError as exc:
            raise HTTPException(status_code=401, detail="Invalid token") from exc

        username = payload.get(self.username_claim)
        if not username:
            raise HTTPException(
                status_code=401,
                detail=f"Token missing '{self.username_claim}' claim",
            )
        return username


_default_verifier: Optional[JwtVerifier] = None


def get_jwt_verifier() -> JwtVerifier:
    """Lazy singleton — fails fast with a clear error if env vars are missing."""
    global _default_verifier
    if _default_verifier is None:
        missing = [
            name for name, value in (
                ("DEX_JWKS_URL", settings.dex_jwks_url),
                ("DEX_ISSUER", settings.dex_issuer),
                ("DEX_AUDIENCE", settings.dex_audience),
            ) if not value
        ]
        if missing:
            raise RuntimeError(
                f"Cannot initialize JwtVerifier: missing env vars: {', '.join(missing)}"
            )
        _default_verifier = JwtVerifier(
            jwks_url=settings.dex_jwks_url,
            issuer=settings.dex_issuer,
            audience=settings.dex_audience,
            username_claim=settings.dex_username_claim,
            public_key_path=settings.dex_jwt_public_key,
        )
        LOG.info(
            "Initialized JwtVerifier (issuer=%s, audience=%s, source=%s)",
            settings.dex_issuer,
            settings.dex_audience,
            f"pinned:{settings.dex_jwt_public_key}" if settings.dex_jwt_public_key else "jwks",
        )
    return _default_verifier
