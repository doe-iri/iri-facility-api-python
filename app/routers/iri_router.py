from abc import ABC, abstractmethod
import traceback
import os
import logging
import importlib
from fastapi import Request, Depends, HTTPException, APIRouter
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .account.models import User


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
    def __init__(self, router_adapter=None, task_router_adapter=None, maturity=None, implementation_level=None, required_if=None, **kwargs):
        super().__init__(**kwargs)
        self.default_openapi_extra = None
        if maturity or implementation_level or required_if:
            self.default_openapi_extra = self.gen_openapi_extra(maturity=maturity, implementation_level=implementation_level, required_if=required_if)

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

    async def current_user(
        self,
        request: Request,
        credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    ):
        token = credentials.credentials

        user_id = None
        try:
            user_id = await self.adapter.get_current_user(token, get_client_ip(request))
        except Exception as exc:
            logging.getLogger().error(f"Error parsing IRI_API_PARAMS: {exc}")
            traceback.print_exc()
            raise HTTPException(status_code=401, detail="Invalid or malformed Authorization parameters") from exc
        if not user_id:
            raise HTTPException(status_code=403, detail="Unauthorized access")
        request.state.current_user_id = user_id
        request.state.api_key = token

    @staticmethod
    def gen_openapi_extra(
        maturity: str | None = None,
        implementation_level: str | None = None,
        required_if: str | None = None,
    ) -> dict:
        """
        Generate the IRI OpenAPI extension for API maturity and implementation level. See the DOE IRI API design docs for details on what these mean.
        x-iri:
        maturity: ...
        implementation:
            level: ...
            required_if_capability: ...
        """
        out_obj = {}

        if maturity is not None:
            out_obj["maturity"] = maturity

        if implementation_level is not None:
            out_obj.setdefault("implementation", {})["level"] = implementation_level

        if required_if is not None:
            out_obj.setdefault("implementation", {})["required_if_capability"] = required_if

        if not out_obj:
            return {}
        return {"x-iri": out_obj}

    def _apply_openapi_extra(self, kwargs):
        # If route explicitly defines openapi_extra, use it. This allows us to override the router default for specific routes when needed.
        if "openapi_extra" in kwargs:
            return kwargs

        # Otherwise, apply router default
        if self.default_openapi_extra:
            kwargs["openapi_extra"] = self.default_openapi_extra

        return kwargs

    def get(self, path: str, **kwargs):
        return super().get(path, **self._apply_openapi_extra(kwargs))

    def post(self, path: str, **kwargs):
        return super().post(path, **self._apply_openapi_extra(kwargs))

    def put(self, path: str, **kwargs):
        return super().put(path, **self._apply_openapi_extra(kwargs))

    def delete(self, path: str, **kwargs):
        return super().delete(path, **self._apply_openapi_extra(kwargs))


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
    async def get_user(self: "AuthenticatedAdapter", user_id: str, api_key: str, client_ip: str | None) -> User:
        """
        Retrieve additional user information (name, email, etc.) for the given user_id.
        """
        pass
