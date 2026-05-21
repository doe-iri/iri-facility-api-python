from abc import ABC, abstractmethod
import asyncio
import os
import logging
import importlib
import threading
import time
from typing import Any
import globus_sdk
import httpx
from authlib.jose import JsonWebKey, JsonWebToken, KeySet
from authlib.jose.errors import JoseError
from fastapi import Request, Depends, HTTPException, APIRouter
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ..types.user import User

bearer_scheme = HTTPBearer()
_DISCOVERY_TIMEOUT_SECONDS = float(os.environ.get("OIDC_DISCOVERY_TIMEOUT_SECONDS", "10"))
_DISCOVERY_CACHE_TTL_SECONDS = float(os.environ.get("OIDC_DISCOVERY_CACHE_TTL_SECONDS", "300"))
_oidc_remote_cache_lock = threading.Lock()
_oidc_remote_cache: dict[str, tuple[float, dict[str, Any], KeySet]] = {}

# Globus introspection (kept alongside AmSC PingAM OIDC). Each external
# IdP path can be independently turned on/off with IRI_AUTH_AMSC / IRI_AUTH_GLOBUS.
GLOBUS_RS_ID = os.environ.get("GLOBUS_RS_ID")
GLOBUS_RS_SECRET = os.environ.get("GLOBUS_RS_SECRET")
GLOBUS_RS_SCOPE_SUFFIX = os.environ.get("GLOBUS_RS_SCOPE_SUFFIX")


def _env_true(name: str, default: bool = False) -> bool:
    """Boolean env var checker."""
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() not in {"0", "false", "off", "no"}


def _amsc_oidc_enabled() -> bool:
    """AmSC PingAM OIDC: on if IRI_AUTH_AMSC != off AND OIDC_DISCOVERY_URI/CLIENT_ID configured."""
    return _env_true("IRI_AUTH_AMSC", False) and _oidc_auth_config() is not None


def _globus_enabled() -> bool:
    """Globus introspection: on if IRI_AUTH_GLOBUS != off AND GLOBUS_RS_ID/SECRET/SCOPE_SUFFIX configured."""
    return bool(_env_true("IRI_AUTH_GLOBUS", False) and GLOBUS_RS_ID
                and GLOBUS_RS_SECRET and GLOBUS_RS_SCOPE_SUFFIX)


def _oidc_auth_config() -> dict[str, str] | None:
    discovery_uri = os.environ.get("OIDC_DISCOVERY_URI")
    client_id = os.environ.get("OIDC_CLIENT_ID")

    if not discovery_uri or not client_id:
        return None

    required_scopes = tuple(
        scope
        for scope in (
            os.environ.get("OIDC_REQUIRED_SCOPES")
            or os.environ.get("OIDC_REQUIRED_SCOPE")
            or ""
        ).replace(",", " ").split()
        if scope
    )

    return {
        "discovery_uri": discovery_uri,
        "client_id": client_id,
        "required_scopes": required_scopes,
        "required_audience": os.environ.get("OIDC_REQUIRED_AUDIENCE") or client_id,
    }


def _fetch_oidc_remote_state(discovery_uri: str) -> tuple[dict[str, Any], KeySet]:
    """Fetch the OIDC discovery."""
    with httpx.Client(timeout=_DISCOVERY_TIMEOUT_SECONDS) as client:
        metadata_resp = client.get(discovery_uri, headers={"Accept": "application/json"})
        metadata_resp.raise_for_status()
        metadata = metadata_resp.json()
        jwks_uri = metadata.get("jwks_uri")
        if not jwks_uri:
            raise RuntimeError("OIDC discovery document is missing jwks_uri")
        jwks_resp = client.get(jwks_uri, headers={"Accept": "application/json"})
        jwks_resp.raise_for_status()
        return metadata, JsonWebKey.import_key_set(jwks_resp.json())


def _load_oidc_remote_state(discovery_uri: str) -> tuple[dict[str, Any], KeySet]:
    """TTL-cached wrapper around fetching oidc remote state. 
    On refresh failure we fall back to the last cached state so a transient
    IdP outage doesn't take the whole IRI service down.
    """
    _log = logging.getLogger(__name__)
    now = time.time()
    cached: tuple[float, dict[str, Any], KeySet] | None = None
    with _oidc_remote_cache_lock:
        cached = _oidc_remote_cache.get(discovery_uri)
        if cached and now - cached[0] < _DISCOVERY_CACHE_TTL_SECONDS:
            age = now - cached[0]
            _log.info("OIDC JWKS cache HIT for %s (age %.0fs, TTL %.0fs)", discovery_uri, age, _DISCOVERY_CACHE_TTL_SECONDS)
            return cached[1], cached[2]

    _log.info("OIDC JWKS cache MISS for %s — fetching discovery + JWKS", discovery_uri)
    try:
        metadata, key_set = _fetch_oidc_remote_state(discovery_uri)
    except Exception:
        if cached:
            logging.getLogger(__name__).warning(
                "OIDC discovery refresh failed for %s; reusing cached metadata + JWKS",
                discovery_uri,
                exc_info=True,
            )
            return cached[1], cached[2]
        raise

    with _oidc_remote_cache_lock:
        _oidc_remote_cache[discovery_uri] = (now, metadata, key_set)
    _log.info("OIDC JWKS cache STORED for %s (TTL %.0fs)", discovery_uri, _DISCOVERY_CACHE_TTL_SECONDS)
    return metadata, key_set


def _decode_oidc_jwt(api_key: str, discovery_uri: str, required_audience: str) -> dict[str, Any]:
    """Verify the JWT signature against the IdP's JWKS and enforce required claims."""
    metadata, key_set = _load_oidc_remote_state(discovery_uri)
    # Use algorithms from the discovery document; exclude HS* (HMAC) — a leaked
    # HMAC secret can forge tokens, so only asymmetric algorithms are acceptable.
    algs_advertised = metadata.get("id_token_signing_alg_values_supported") or []
    algorithms = [alg for alg in algs_advertised if not alg.startswith("HS")]
    if not algorithms:
        raise RuntimeError("OIDC discovery document advertises no asymmetric signing algorithms")
    claims_options = {
        "iss": {"essential": True, "value": metadata["issuer"]},
        "aud": {"essential": True, "value": required_audience},
        "exp": {"essential": True},
        "nbf": {"essential": True},
        "iat": {"essential": True},
    }
    claims = JsonWebToken(algorithms).decode(api_key, key_set, claims_options=claims_options)
    claims.validate()
    return dict(claims)


async def _get_userinfo(bearer_token: str, discovery_uri: str, token_info: dict[str, Any]) -> dict[str, Any]:
    """PingAM (and some other IdPs) issue access tokens that contain only sub.
    Profile claims (name, email, given_name, ...) are available via the standard
    UserInfo endpoint.

    Fails gracefully — if the UserInfo call fails for any reason the original
    token_info is returned unchanged and auth still succeeds.
    """
    _log = logging.getLogger(__name__)

    # Fast path: profile claims already present (e.g. Keycloak embeds them)
    if token_info.get("name") or token_info.get("email"):
        return token_info

    metadata, _ = _load_oidc_remote_state(discovery_uri)
    userinfo_endpoint = metadata.get("userinfo_endpoint")
    if not userinfo_endpoint:
        _log.warning("OIDC discovery document missing userinfo_endpoint; profile claims unavailable")
        return token_info

    try:
        async with httpx.AsyncClient(timeout=_DISCOVERY_TIMEOUT_SECONDS) as client:
            resp = await client.get(
                userinfo_endpoint,
                headers={"Authorization": f"Bearer {bearer_token}", "Accept": "application/json"},
            )
            resp.raise_for_status()
            userinfo = resp.json()
            _log.info("OIDC UserInfo returned claims: %s", list(userinfo.keys()))
            for key, value in userinfo.items():
                if key not in token_info:
                    token_info[key] = value
    except Exception:
        _log.warning("Failed to fetch OIDC UserInfo; proceeding without profile claims", exc_info=True)

    return token_info


def get_client_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    else:
        ip_addr = request.headers.get("HTTP_X_REAL_IP")
        if not ip_addr:
            ip_addr = request.headers.get("x-real-ip")
            if not ip_addr:
                ip_addr = request.client.host
        return ip_addr


class IriRouter(APIRouter):
    def __init__(self, router_adapter=None, task_router_adapter=None, **kwargs):
        super().__init__(**kwargs)
        router_name = self.get_router_name()
        self.adapter = IriRouter.create_adapter(router_name, router_adapter)
        if self.adapter:
            logging.getLogger().info(f"Successfully loaded {router_name} adapter: {self.adapter.__class__.__name__}")
        else:
            logging.getLogger().info(f"Hiding {router_name}")
            self.include_in_schema = False
        self.task_adapter = None
        if task_router_adapter:
            self.task_adapter = IriRouter.create_adapter("task", task_router_adapter)
            if not self.task_adapter:
                logging.getLogger().info(f'Hiding {router_name} because "task" adapter was not found')
                self.include_in_schema = False

    def get_router_name(self):
        return self.prefix.replace("/", "").strip()

    @staticmethod
    def _get_adapter_name(router_name: str) -> str | None:
        """Return the adapter name, or None if it's not configured and IRI_SHOW_MISSING_ROUTES is true"""
        # if there is no adapter specified for this router,
        # and IRI_SHOW_MISSING_ROUTES is not true,
        # hide the router
        env_var = f"IRI_API_ADAPTER_{router_name}"
        if env_var not in os.environ and os.environ.get("IRI_SHOW_MISSING_ROUTES") not in ["true", "1", "on", "yes"]:
            return None

        # find and load the actual implementation
        return os.environ.get(env_var, "app.demo_adapter.DemoAdapter")

    @staticmethod
    def create_adapter(router_name, router_adapter):
        # Load the facility-specific adapter
        adapter_name = IriRouter._get_adapter_name(router_name)
        if not adapter_name:
            return None

        parts = adapter_name.rsplit(".", 1)
        module = importlib.import_module(parts[0])
        AdapterClass = getattr(module, parts[1])
        if not issubclass(AdapterClass, router_adapter):
            raise Exception(f"{adapter_name} should implement FacilityAdapter")

        # assign it
        return AdapterClass()


    async def get_oidc_token_info(self, api_key: str) -> dict[str, Any]:
        """Validate a bearer JWT against the configured OIDC provider."""
        config = _oidc_auth_config()
        if not config:
            raise RuntimeError("OIDC auth is not configured")

        try:
            token_info = await asyncio.to_thread(
                _decode_oidc_jwt,
                api_key,
                config["discovery_uri"],
                config["required_audience"],
            )
        except httpx.HTTPError as exc:
            raise RuntimeError(f"OIDC discovery/JWKS request failed: {exc}") from exc
        except JoseError as exc:
            raise RuntimeError(f"OIDC JWT validation failed: {exc}") from exc

        logging.getLogger().info("PING OIDC JWT VALIDATION CLAIMS:")
        logging.getLogger().info(token_info)

        # PingAM access tokens contain only sub; name/email/etc. come from the UserInfo endpoint.
        token_info = await _get_userinfo(api_key, config["discovery_uri"], token_info)

        required_scopes = config["required_scopes"]
        if required_scopes:
            raw_scope = token_info.get("scope")
            if isinstance(raw_scope, str):
                token_scope = {s for s in raw_scope.split() if s}
            elif isinstance(raw_scope, list):
                token_scope = {str(s) for s in raw_scope if str(s)}
            else:
                token_scope = set()
            missing_scopes = [s for s in required_scopes if s not in token_scope]
            if missing_scopes:
                raise Exception(f"Token missing required scopes: {', '.join(missing_scopes)}")

        return token_info


    async def get_globus_info(self, api_key: str) -> dict:
        """Returns the linked identities and the session info objects.

        Introspects the IRI API token against Globus Auth using the resource-server
        client credentials. Enforces active/exp/nbf, the required IRI scope, and
        a recent session_info.authentications presence (RFC §3F session freshness).
        """
        globus_client = globus_sdk.ConfidentialAppAuthClient(GLOBUS_RS_ID, GLOBUS_RS_SECRET)
        introspect = globus_client.oauth2_token_introspect(api_key, include="identity_set_detail,session_info")
        logging.getLogger().info("IRI TOKEN INTROSPECTION:")
        logging.getLogger().info(introspect)
        if not introspect.get("active"):
            raise Exception("Inactive token")

        exp = introspect.get("exp")
        if exp and time.time() >= exp:
            raise Exception("Token has expired")

        nbf = introspect.get("nbf")
        if nbf and time.time() < nbf:
            raise Exception("Token not yet valid")

        token_scope = introspect.get("scope", "").split()
        required_scope = f"https://auth.globus.org/scopes/{GLOBUS_RS_ID}/{GLOBUS_RS_SCOPE_SUFFIX}"
        if required_scope not in token_scope:
            raise Exception(f"Token missing required scope: {required_scope}")

        session_info = introspect.get("session_info")
        if not session_info:
            raise Exception(
                "No recent login was found in the token (missing session_info). "
                "Please re-authenticate to obtain a valid session."
            )
        authentications = session_info.get("authentications")
        if not authentications:
            raise Exception(
                "No recent login was found in the token (empty session_info.authentications). "
                "Please re-authenticate to obtain a valid session."
            )

        return introspect


    async def current_user(
        self,
        request: Request,
        credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    ):
        """Authenticate user by using the configured IdP chain.
        Order:
          1. AmSC PingAM OIDC  —> JWKS validation, controlled by IRI_AUTH_AMSC.
          2. Globus            —> token introspection, controlled by IRI_AUTH_GLOBUS.
          3. Facility-specific —> adapter.get_current_user(). Always on
        Breaks on the first successful auth mode.
        """
        token = credentials.credentials
        ip_address = get_client_ip(request)
        user_id = None
        token_info = None
        globus_introspect = None
        exc_msg = ""

        # 1. AmSC PingAM OIDC
        if _amsc_oidc_enabled():
            try:
                token_info = await self.get_oidc_token_info(token)
                user_id = await self.adapter.get_current_user_oidc(token, ip_address, token_info)
            except Exception as oidc_exc:
                logging.getLogger().exception("AmSC OIDC auth error:", exc_info=oidc_exc)
                exc_msg += f"AmSC OIDC authentication failed: {str(oidc_exc)}. || "
                token_info = None

        # 2. Globus introspection
        if not user_id and _globus_enabled():
            try:
                globus_introspect = await self.get_globus_info(token)
                user_id = await self.adapter.get_current_user_globus(token, ip_address, globus_introspect)
            except Exception as globus_exc:
                logging.getLogger().exception("Globus auth error:", exc_info=globus_exc)
                exc_msg += f"Globus authentication failed: {str(globus_exc)}. || "
                globus_introspect = None

        # 3. Facility-specific
        if not user_id:
            try:
                user_id = await self.adapter.get_current_user(token, ip_address)
            except Exception as exc:
                logging.getLogger().exception("Facility Specific auth failed:", exc_info=exc)
                exc_msg += f"Facility Specific authentication failed: {str(exc)}"
                raise HTTPException(status_code=401, detail=exc_msg) from exc

        if not user_id:
            raise HTTPException(status_code=403, detail="Authentication succeeded but no user ID was identified. Contact Facility Admin.")

        user = await self.adapter.get_user(
            user_id=user_id,
            api_key=token,
            client_ip=ip_address,
            token_info=token_info,
            globus_introspect=globus_introspect,
        )

        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user

class AuthenticatedAdapter(ABC):
    @abstractmethod
    async def get_current_user(self: "AuthenticatedAdapter", api_key: str, client_ip: str | None) -> str:
        """
        Decode the api_key and return the authenticated user's id.
        This method is not called directly, rather authorized endpoints "depend" on it.
        (https://fastapi.tiangolo.com/tutorial/dependencies/)
        """
        pass

    @abstractmethod
    async def get_current_user_oidc(self: "AuthenticatedAdapter", api_key: str, client_ip: str | None, token_info: dict | None) -> str:
        """
        Decode the api_key and return the authenticated user's id from information returned by an OIDC token.
        This method is not called directly, rather authorized endpoints "depend" on it.
        (https://fastapi.tiangolo.com/tutorial/dependencies/)
        """
        pass

    @abstractmethod
    async def get_current_user_globus(self: "AuthenticatedAdapter", api_key: str, client_ip: str | None, globus_introspect: dict | None) -> str:
        """
        Decode the api_key and return the authenticated user's id from information returned by introspecting a globus token.
        This method is not called directly, rather authorized endpoints "depend" on it.
        (https://fastapi.tiangolo.com/tutorial/dependencies/)
        """
        pass

    @abstractmethod
    async def get_user(self: "AuthenticatedAdapter", user_id: str, api_key: str, client_ip: str | None, token_info: dict | None, globus_introspect: dict | None) -> User:
        """
        Retrieve additional user information (name, email, etc.) for the given user_id.
        ``token_info`` is populated when AmSC OIDC validation produced it;
        ``globus_introspect`` is populated when Globus introspection produced it.
        Both may be None when the request was authenticated via the
        facility-specific api_key path.
        """
        pass
