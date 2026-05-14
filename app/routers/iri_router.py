from abc import ABC, abstractmethod
import asyncio
import json
import os
import logging
import importlib
import time
from functools import lru_cache
from typing import Any
import jwt
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError
from urllib.error import URLError
from urllib.request import Request as UrlRequest, urlopen
from fastapi import Request, Depends, HTTPException, APIRouter
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ..types.user import User

bearer_scheme = HTTPBearer()


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


@lru_cache(maxsize=8)
def _load_oidc_discovery_document(discovery_uri: str) -> dict[str, Any]:
    request = UrlRequest(
        discovery_uri,
        headers={"Accept": "application/json"},
    )
    with urlopen(request, timeout=10) as response:
        payload = response.read().decode("utf-8")
    metadata = json.loads(payload)
    jwks_uri = metadata.get("jwks_uri")
    if not jwks_uri:
        raise RuntimeError("OIDC discovery document is missing jwks_uri")
    return metadata


@lru_cache(maxsize=8)
def _jwks_client(discovery_uri: str) -> PyJWKClient:
    metadata = _load_oidc_discovery_document(discovery_uri)
    return PyJWKClient(metadata["jwks_uri"])


def _normalize_scope_claim(scope: Any) -> set[str]:
    if isinstance(scope, str):
        return {item for item in scope.split() if item}
    if isinstance(scope, list):
        return {str(item) for item in scope if str(item)}
    return set()


def _decode_oidc_jwt(
    api_key: str,
    *,
    discovery_uri: str,
    required_audience: str,
) -> dict[str, Any]:
    metadata = _load_oidc_discovery_document(discovery_uri)
    signing_key = _jwks_client(discovery_uri).get_signing_key_from_jwt(api_key)
    return jwt.decode(
        api_key,
        signing_key.key,
        algorithms=["RS256", "RS384", "RS512", "ES256", "ES384", "ES512", "PS256", "PS384", "PS512", "EdDSA"],
        audience=required_audience,
        issuer=metadata["issuer"],
        options={"require": ["exp", "iat", "nbf", "iss"]},
    )


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
                discovery_uri=config["discovery_uri"],
                required_audience=config["required_audience"],
            )
        except URLError as exc:
            raise RuntimeError(f"OIDC discovery/JWKS request failed: {exc.reason}") from exc
        except InvalidTokenError as exc:
            raise RuntimeError(f"OIDC JWT validation failed: {exc}") from exc

        logging.getLogger().info("PING OIDC JWT VALIDATION CLAIMS:")
        logging.getLogger().info(token_info)

        # Check exp (expiration time) claim
        exp = token_info.get("exp")
        if exp and time.time() >= exp:
            raise Exception("Token has expired")

        # Check nbf (not before) claim
        nbf = token_info.get("nbf")
        if nbf and time.time() < nbf:
            raise Exception("Token not yet valid")

        required_scopes = config["required_scopes"]
        if required_scopes:
            token_scope = _normalize_scope_claim(token_info.get("scope"))
            missing_scopes = [scope for scope in required_scopes if scope not in token_scope]
            if missing_scopes:
                raise Exception(f"Token missing required scopes: {', '.join(missing_scopes)}")

        return token_info


    async def current_user(
        self,
        request: Request,
        credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    ):
        token = credentials.credentials
        ip_address = get_client_ip(request)
        user_id = None
        token_info = None
        exc_msg = ""
        try:
            if _oidc_auth_config():
                try:
                    token_info = await self.get_oidc_token_info(token)
                    user_id = await self.adapter.get_current_user_oidc(token, ip_address, token_info)
                except Exception as oidc_exc:
                    logging.getLogger().exception("OIDC auth error:", exc_info=oidc_exc)
                    exc_msg = f"OIDC authentication failed: {str(oidc_exc)}. || "
            if not user_id:
                user_id = await self.adapter.get_current_user(token, ip_address)
        except Exception as exc:
            logging.getLogger().exception("Facility Specific auth failed: ", exc_info=exc)
            exc_msg += f"Facility Specific authentication failed: {str(exc)}"
            raise HTTPException(status_code=401, detail=exc_msg) from exc
        if not user_id:
            raise HTTPException(status_code=403, detail="Authentication succeeded but no user ID was identified. Contact Facility Admin.")

        user = await self.adapter.get_user(
            user_id=user_id,
            api_key=token,
            client_ip=ip_address,
            token_info=token_info,
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
    async def get_user(self: "AuthenticatedAdapter", user_id: str, api_key: str, client_ip: str | None, token_info: dict | None) -> User:
        """
        Retrieve additional user information (name, email, etc.) for the given user_id.
        """
        pass
