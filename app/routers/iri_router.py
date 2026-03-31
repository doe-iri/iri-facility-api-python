from abc import ABC, abstractmethod
import os
import logging
import importlib
import time
import globus_sdk
from fastapi import Request, Depends, HTTPException, APIRouter
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ..types.user import User

bearer_scheme = HTTPBearer()


GLOBUS_RS_ID = os.environ.get("GLOBUS_RS_ID")
GLOBUS_RS_SECRET = os.environ.get("GLOBUS_RS_SECRET")
GLOBUS_RS_SCOPE_SUFFIX = os.environ.get("GLOBUS_RS_SCOPE_SUFFIX")


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


    async def get_globus_info(self, api_key: str) -> dict:
        """Returns the linked identities and the session info objects"""
        # Introspect the IRI API token using resource server credentials
        globus_client = globus_sdk.ConfidentialAppAuthClient(GLOBUS_RS_ID, GLOBUS_RS_SECRET)
        # grab identity_set_detail for linked identities and session_info to see how the user logged in
        introspect = globus_client.oauth2_token_introspect(api_key, include="identity_set_detail,session_info")
        logging.getLogger().info("IRI TOKEN INTROSPECTION:")
        logging.getLogger().info(introspect)
        if not introspect.get("active"):
            raise Exception("Inactive token")

        # Check exp (expiration time) claim
        exp = introspect.get("exp")
        if exp and time.time() >= exp:
            raise Exception("Token has expired")

        # Check nbf (not before) claim
        nbf = introspect.get("nbf")
        if nbf and time.time() < nbf:
            raise Exception("Token not yet valid")

        # Check if token has the required IRI scope
        token_scope = introspect.get("scope", "").split()
        GLOBUS_SCOPE = f"https://auth.globus.org/scopes/{GLOBUS_RS_ID}/{GLOBUS_RS_SCOPE_SUFFIX}"
        if GLOBUS_SCOPE not in token_scope:
            raise Exception(f"Token missing required scope: {GLOBUS_SCOPE}")

        session_info = introspect.get("session_info", {})
        if not session_info or not session_info.get("authentications", {}):
            raise Exception(f"Empty session_info.authentications block")

        return introspect


    async def current_user(
        self,
        request: Request,
        credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    ):
        token = credentials.credentials
        ip_address = get_client_ip(request)
        user_id = None
        globus_introspect = None
        exc_msg = ""
        try:
            if GLOBUS_RS_ID and GLOBUS_RS_SECRET and GLOBUS_RS_SCOPE_SUFFIX:
                try:
                    globus_introspect = await self.get_globus_info(token)
                    user_id = await self.adapter.get_current_user_globus(token, ip_address, globus_introspect)
                except Exception as globus_exc:
                    logging.getLogger().exception("Globus error:", exc_info=globus_exc)
                    exc_msg = f"Globus authentication failed: {str(globus_exc)}. || "
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
    async def get_current_user_globus(self: "AuthenticatedAdapter", api_key: str, client_ip: str | None, globus_introspect: dict | None) -> str:
        """
        Decode the api_key and return the authenticated user's id from information returned by introspecting a globus token.
        This method is not called directly, rather authorized endpoints "depend" on it.
        (https://fastapi.tiangolo.com/tutorial/dependencies/)
        """
        pass

    @abstractmethod
    async def get_user(self: "AuthenticatedAdapter", user_id: str, api_key: str, client_ip: str | None, globus_introspect: dict | None) -> User:
        """
        Retrieve additional user information (name, email, etc.) for the given user_id.
        """
        pass
