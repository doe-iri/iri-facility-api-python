"""
Dex JWT verifier for S3DF.

Verifies signed JWTs against the Dex JWKS endpoint and extracts the username
claim. The PyJWKClient call is synchronous (blocking urllib); it is offloaded
to a thread executor so cache misses do not stall the event loop.
"""

import asyncio
import logging
from typing import Optional

import jwt
from fastapi import HTTPException
from jwt import PyJWKClient, PyJWKClientError

from app.s3df.config import settings

LOG = logging.getLogger(__name__)


class JwtVerifier:
    """Verifies Dex-issued JWTs via JWKS and returns the username claim."""

    def __init__(
        self,
        jwks_url: str,
        issuer: str,
        audience: str,
        username_claim: str = "name",
    ):
        self.issuer = issuer
        self.audience = audience
        self.username_claim = username_claim
        # PyJWKClient caches keys for `lifespan` seconds (default 300).
        self._jwks_client = PyJWKClient(jwks_url)

    async def verify(self, token: str) -> str:
        """
        Verify token signature, exp, iss, aud; return the username claim.
        Raises HTTPException(401) on any verification failure.
        """
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

        try:
            payload = jwt.decode(
                token,
                signing_key.key,
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
        )
        LOG.info("Initialized JwtVerifier (issuer=%s, audience=%s)",
                 settings.dex_issuer, settings.dex_audience)
    return _default_verifier
