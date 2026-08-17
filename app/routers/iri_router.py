from abc import ABC, abstractmethod
import os
import logging
import importlib
from fastapi import Request, Depends, HTTPException, APIRouter
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .. import amsc_auth
from ..types.user import User

bearer_scheme = HTTPBearer()


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
        """Return the configured adapter dotted-path for a router, or None to hide it.

        IRI_API_ADAPTER_<router> set        -> return it.
        unset + IRI_SHOW_MISSING_ROUTES off -> return None (router hidden).
        unset + IRI_SHOW_MISSING_ROUTES on  -> raise; the library ships no demo
            fallback, so a shown route with no adapter is a misconfiguration.
        """
        env_var = f"IRI_API_ADAPTER_{router_name}"
        if env_var in os.environ:
            return os.environ[env_var]
        if os.environ.get("IRI_SHOW_MISSING_ROUTES") in ["true", "1", "on", "yes"]:
            raise RuntimeError(
                f"{env_var} is not set but IRI_SHOW_MISSING_ROUTES is enabled; "
                f"configure an adapter for '{router_name}' or disable IRI_SHOW_MISSING_ROUTES."
            )
        return None

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


    async def get_amsc_info(self, token: str) -> dict:
        """Validate an AmSC Keycard (signature/claims, optional Ping userinfo check) and return its claims."""
        claims = await amsc_auth.validate_amsc_token(token)
        if amsc_auth.userinfo_check_enabled():
            userinfo = await amsc_auth.check_amsc_userinfo(token)
            claims["amsc_name"] = userinfo.get("name")
            claims["amsc_email"] = userinfo.get("email")
        return claims


    async def current_user(
        self,
        request: Request,
        credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    ):
        token = credentials.credentials
        ip_address = get_client_ip(request)
        user_id = None
        exc_msg = ""
        try:
            if amsc_auth.enabled():
                try:
                    amsc_claims = await self.get_amsc_info(token)
                    user_id = await self.adapter.get_current_user_amsc(token, ip_address, amsc_claims)
                    logging.getLogger().info(
                        "AmSC authenticated request: sub=%s amsc_project_context=%s jti=%s name=%s email=%s -> local_user=%s",
                        amsc_claims.get("sub"),
                        amsc_claims.get("amsc_project_context"),
                        amsc_claims.get("jti"),
                        amsc_claims.get("amsc_name"),
                        amsc_claims.get("amsc_email"),
                        user_id,
                    )
                except Exception as amsc_exc:
                    logging.getLogger().exception("AmSC error:", exc_info=amsc_exc)
                    exc_msg = f"AmSC authentication failed: {str(amsc_exc)}. || "
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

    async def get_current_user_amsc(self: "AuthenticatedAdapter", api_key: str, client_ip: str | None, amsc_claims: dict) -> str:
        """
        Return the authenticated users local id for an already-validated AmSC Keycard.

        Default implementation: map the token's active `amsc_project_context`
        claim to a local facility username via the configured YAML mapping file.
        """
        return amsc_auth.resolve_amsc_project(amsc_claims["amsc_project_context"])

    @abstractmethod
    async def get_user(self: "AuthenticatedAdapter", user_id: str, api_key: str, client_ip: str | None) -> User:
        """
        Retrieve additional user information (name, email, etc.) for the given user_id.
        """
        pass
