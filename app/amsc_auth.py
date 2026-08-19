"""AmSC Keycard authentication support.


1. Validate the Keycard is well-formed and currently valid: JWKS signature verification, issuer/audience/expiry checks (``validate_amsc_token``).
2. Validate the claims carried inside it (amsc_project_context, sub) are present.
3. Optionally call the AmSC userinfo endpoint (Ping) to catch tokens revoked since issuance.
4. Map the tokens amsc_project_context to a local facility username via a facility-maintained JSON file.
   AmSC project with no local mapping entry is a hard authentication failure (401).

To turns this on with AMSC_TOKEN_ENABLED=true and supply issuer/audience/JWKS/mapping configuration.
"""
import asyncio
import json
import os
import time
from typing import Any

import httpx
import jwt
from jwt import PyJWKClient

from .apilogger import get_stream_logger

logger = get_stream_logger(__name__, os.environ.get("LOG_LEVEL", "DEBUG"))

# Fallback when neither AMSC_TOKEN_ALGORITHMS nor a usable discovery document is available.
DEFAULT_ALGORITHMS = ["RS256", "ES256", "RS384", "RS512", "ES384", "ES512"]

_ASYMMETRIC_ALGORITHMS = frozenset({"RS256", "RS384", "RS512", "ES256", "ES384", "ES512", "PS256", "PS384", "PS512", "EdDSA"})


def _isittrue(value: str | None) -> bool:
    return (value or "").strip().lower() in ("true", "1", "on", "yes")


def enabled() -> bool:
    """Whether the AmSC Keycard auth path is turned on for this deployment."""
    return _isittrue(os.environ.get("AMSC_TOKEN_ENABLED"))


def userinfo_check_enabled() -> bool:
    """Whether step 3 (userinfo check against Ping) is turned on."""
    return _isittrue(os.environ.get("AMSC_USERINFO_VALIDATION_ENABLED"))


def _discovery_url() -> str:
    return os.environ.get("AMSC_OIDC_DISCOVERY_URL", "").strip()


def _issuer() -> str:
    return os.environ.get("AMSC_TOKEN_ISSUER", "").strip()


def _audience() -> list[str]:
    raw = os.environ.get("AMSC_TOKEN_AUDIENCE", "")
    return [part.strip() for part in raw.split(",") if part.strip()]


def _skip_audience_check() -> bool:
    """Skip an audience check"""
    return _isittrue(os.environ.get("AMSC_TOKEN_SKIP_AUDIENCE_CHECK"))


def _validate_exact_audience(claims: dict) -> None:
    """Reject any token whose `aud` is not an exact match for this facility."""
    if _skip_audience_check():
        return
    configured = set(_audience())
    raw_aud = claims.get("aud")
    if isinstance(raw_aud, list):
        token_aud = set(raw_aud)
    elif raw_aud:
        token_aud = {raw_aud}
    else:
        token_aud = set()
    if not token_aud or not token_aud.issubset(configured):
        raise ValueError("AmSC token audience is not an exact match for this facility")


async def _algorithms() -> list[str]:
    """Accepted JWT signing algorithms.

    AMSC_TOKEN_ALGORITHMS prioritized if set. Otherwise, derive from the discovery
    endpoint id_token_signing_alg_values_supported. Falls back to
    DEFAULT_ALGORITHMS when discovery is unset, unreachable, or publishes no data.
    """
    raw = os.environ.get("AMSC_TOKEN_ALGORITHMS", "")
    explicit = [part.strip() for part in raw.split(",") if part.strip()]
    if explicit:
        return explicit
    try:
        document = await _fetch_discovery_document()
        supported = document.get("id_token_signing_alg_values_supported") or []
    except Exception as exc:
        logger.error(f"amsc_auth: could not derive algorithms from discovery document: {exc}")
        return DEFAULT_ALGORITHMS
    asymmetric = [alg for alg in supported if alg in _ASYMMETRIC_ALGORITHMS]
    return asymmetric or DEFAULT_ALGORITHMS


def _leeway_seconds() -> int:
    return int(os.environ.get("AMSC_TOKEN_LEEWAY_SECONDS", "30"))


def _jwks_cache_ttl_seconds() -> int:
    return int(os.environ.get("AMSC_TOKEN_JWKS_CACHE_TTL_SECONDS", "3600"))


def _userinfo_timeout_seconds() -> float:
    return float(os.environ.get("AMSC_USERINFO_TIMEOUT_SECONDS", "5"))


def _mapping_file() -> str:
    return os.environ.get("AMSC_PROJECT_MAPPING_FILE", "").strip()


# ---------------------------------------------------------------------------
# OIDC discovery document (.well-known/openid-configuration) caching
# ---------------------------------------------------------------------------

_discovery_cache: dict[str, Any] = {}
_discovery_cache_ts: float = 0.0


async def _fetch_discovery_document() -> dict:
    """Fetch and cache the OIDC discovery document for the configured issuer."""
    global _discovery_cache, _discovery_cache_ts
    url = _discovery_url()
    if not url:
        return {}
    ttl = _jwks_cache_ttl_seconds()
    now = time.time()
    if _discovery_cache and (now - _discovery_cache_ts) < ttl:
        return _discovery_cache
    try:
        async with httpx.AsyncClient(timeout=_userinfo_timeout_seconds()) as client:
            response = await client.get(url)
        response.raise_for_status()
        _discovery_cache = response.json()
        _discovery_cache_ts = now
    except Exception as exc:
        logger.error(f"amsc_auth: failed to fetch OIDC discovery document from {url}: {exc}")
        if not _discovery_cache:
            raise
    return _discovery_cache


async def _jwks_url() -> str:
    explicit = os.environ.get("AMSC_JWKS_URL", "").strip()
    if explicit:
        return explicit
    document = await _fetch_discovery_document()
    return document.get("jwks_uri", "")


async def _userinfo_url() -> str:
    explicit = os.environ.get("AMSC_USERINFO_URL", "").strip()
    if explicit:
        return explicit
    document = await _fetch_discovery_document()
    return document.get("userinfo_endpoint", "")


# ---------------------------------------------------------------------------
# Step 1 & 2: JWKS-backed signature verification and required-claims check
# ---------------------------------------------------------------------------

_jwks_clients: dict[str, PyJWKClient] = {}


def _jwks_client(jwks_url: str) -> PyJWKClient:
    client = _jwks_clients.get(jwks_url)
    if client is None:
        client = PyJWKClient(jwks_url, cache_jwk_set=True, lifespan=_jwks_cache_ttl_seconds())
        _jwks_clients[jwks_url] = client
    return client


async def validate_amsc_token(token: str) -> dict:
    """Validate an AmSC Keycard's signature, issuer, audience, and expiry.
    Also enforce presence of the sub and amsc_project_context.
    """
    if not enabled():
        raise ValueError("AmSC token authentication is disabled")

    issuer = _issuer()
    audience = _audience()
    skip_audience = _skip_audience_check()
    if not issuer or (not audience and not skip_audience):
        raise ValueError("AMSC_TOKEN_ISSUER and AMSC_TOKEN_AUDIENCE must be configured")

    jwks_url = await _jwks_url()
    if not jwks_url:
        raise ValueError("No AmSC JWKS URL available (set AMSC_JWKS_URL or AMSC_OIDC_DISCOVERY_URL)")

    try:
        signing_key_obj = await asyncio.to_thread(_jwks_client(jwks_url).get_signing_key_from_jwt, token)
        signing_key = signing_key_obj.key
    except jwt.PyJWKClientError as exc:
        raise ValueError(f"AmSC token key lookup failed: {exc}") from exc

    algorithms = await _algorithms()
    try:
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=algorithms,
            issuer=issuer,
            leeway=_leeway_seconds(),
            # `aud` is verified separately below with an exact-match check;
            options={"require": ["exp"], "verify_aud": False},
        )
    except jwt.ExpiredSignatureError as exc:
        raise ValueError("AmSC token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise ValueError(f"AmSC token is invalid: {exc}") from exc

    # Claims only (never the raw token) -- lets us see exactly what an upstream
    # IdP/exchange put in the token when a required claim is unexpectedly absent.
    logger.debug(f"amsc_auth: decoded AmSC token claims: {claims}")

    _validate_exact_audience(claims)

    if not claims.get("sub"):
        raise ValueError("AmSC token is missing the required sub (AUID) claim")
    if not claims.get("amsc_project_context"):
        raise ValueError("AmSC token is missing the required amsc_project_context claim")

    return claims


# ---------------------------------------------------------------------------
# Step 3: optional userinfo freshness check
# ---------------------------------------------------------------------------

async def check_amsc_userinfo(token: str) -> dict:
    """Call the AmSC userinfo endpoint (Ping) to confirm the token is still live."""
    url = await _userinfo_url()
    if not url:
        raise ValueError("No AmSC userinfo URL available (set AMSC_USERINFO_URL or AMSC_OIDC_DISCOVERY_URL)")

    try:
        async with httpx.AsyncClient(timeout=_userinfo_timeout_seconds()) as client:
            response = await client.get(url, headers={"Authorization": f"Bearer {token}"})
    except httpx.HTTPError as exc:
        raise ValueError(f"AmSC userinfo check failed: could not reach Ping: {exc}") from exc

    if response.status_code != 200:
        raise ValueError(f"AmSC userinfo check failed: Ping returned status {response.status_code}")

    try:
        userinfo = response.json()
    except ValueError:
        userinfo = {}
    logger.info(
        "amsc_auth: userinfo check confirmed live AmSC identity sub=%s name=%s email=%s",
        userinfo.get("sub"),
        userinfo.get("name"),
        userinfo.get("email"),
    )
    return userinfo


# ---------------------------------------------------------------------------
# Step 4: amsc_project_context -> local facility username mapping (JSON)
# ---------------------------------------------------------------------------

_mapping_cache: dict[str, str] = {}
_mapping_mtime: float = 0.0


def _load_project_mapping() -> dict[str, str]:
    """Return the amsc_project_context -> local username mapping, reloading on file change."""
    global _mapping_cache, _mapping_mtime
    path = _mapping_file()
    if not path:
        raise ValueError("AMSC_PROJECT_MAPPING_FILE is not configured")

    try:
        mtime = os.path.getmtime(path)
    except OSError as exc:
        raise ValueError(f"AmSC project mapping file not found: {path}") from exc
    if mtime == _mapping_mtime and _mapping_cache:
        return _mapping_cache
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle) or {}
    mapping = data.get("project_mapping") or {}
    if not isinstance(mapping, dict):
        raise ValueError(f"AmSC project mapping file {path}: 'project_mapping' must be a mapping")
    _mapping_cache = {str(key): str(value) for key, value in mapping.items()}
    _mapping_mtime = mtime
    logger.info(f"amsc_auth: reloaded project mapping from {path} ({len(_mapping_cache)} project(s))")
    return _mapping_cache


def resolve_amsc_project(amsc_project_context: str) -> str:
    """Map an AmSC amsc_project_context claim to a local facility username."""
    mapping = _load_project_mapping()
    username = mapping.get(amsc_project_context)
    if not username:
        raise ValueError(f"No local mapping for AmSC project '{amsc_project_context}'")
    return username


def _validate_startup_config() -> None:
    """Fail fast at import time if AMSC auth is enabled but misconfigured."""
    if not enabled():
        return
    missing = []
    if not _issuer():
        missing.append("AMSC_TOKEN_ISSUER")
    if not _audience():
        missing.append("AMSC_TOKEN_AUDIENCE")
    if not os.environ.get("AMSC_JWKS_URL", "").strip() and not _discovery_url():
        missing.append("AMSC_JWKS_URL or AMSC_OIDC_DISCOVERY_URL")
    if not _mapping_file():
        missing.append("AMSC_PROJECT_MAPPING_FILE")
    if userinfo_check_enabled() and not os.environ.get("AMSC_USERINFO_URL", "").strip() and not _discovery_url():
        missing.append("AMSC_USERINFO_URL or AMSC_OIDC_DISCOVERY_URL (required by AMSC_USERINFO_VALIDATION_ENABLED)")
    if missing:
        raise RuntimeError("AMSC_TOKEN_ENABLED is true but required configuration is missing: " + ", ".join(missing))
    logger.info(f"amsc_auth: AMSC token authentication enabled (issuer={_issuer()}, audience={_audience()}, userinfo_check={userinfo_check_enabled()})")


_validate_startup_config()
