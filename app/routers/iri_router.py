from abc import ABC, abstractmethod
import os
import logging
import importlib
import datetime
from urllib.parse import parse_qs
from fastapi import Request, Depends, HTTPException, APIRouter
from fastapi.security import APIKeyHeader
from pydantic_core import core_schema
from .account.models import User


bearer_token = APIKeyHeader(name="Authorization")


def get_client_ip(request : Request) -> str|None:
    # logging.debug("Request headers=%s" % request.headers)
    # logging.debug("client=%s" % request.client.host)

    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    else:
        ip_addr = request.headers.get('HTTP_X_REAL_IP')
        if not ip_addr:
            ip_addr = request.headers.get('x-real-ip')
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
                logging.getLogger().info(f"Hiding {router_name} because \"task\" adapter was not found")
                self.include_in_schema = False


    def get_router_name(self):
        return self.prefix.replace("/", "").strip()


    @staticmethod
    def _get_adapter_name(router_name: str) -> str|None:
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
        request : Request,
        api_key: str = Depends(bearer_token),
    ):
        user_id = None
        try:
            user_id = await self.adapter.get_current_user(api_key, get_client_ip(request))
        except Exception as exc:
            logging.getLogger().error(f"Error parsing IRI_API_PARAMS: {exc}")
            raise HTTPException(status_code=401, detail="Invalid or malformed Authorization parameters") from exc
        if not user_id:
            raise HTTPException(status_code=403, detail="Unauthorized access")
        request.state.current_user_id = user_id
        request.state.api_key = api_key


class AuthenticatedAdapter(ABC):

    @abstractmethod
    async def get_current_user(
        self : "AuthenticatedAdapter",
        api_key: str,
        client_ip: str|None,
        ) -> str:
        """
            Decode the api_key and return the authenticated user's id.
            This method is not called directly, rather authorized endpoints "depend" on it.
            (https://fastapi.tiangolo.com/tutorial/dependencies/)
        """
        pass


    @abstractmethod
    async def get_user(
        self : "AuthenticatedAdapter",
        user_id: str,
        api_key: str,
        client_ip: str|None,
        ) -> User:
        """
            Retrieve additional user information (name, email, etc.) for the given user_id.
        """
        pass


def forbidExtraQueryParams(*allowedParams: str):
    async def checker(req: Request):
        if "*" in allowedParams:
            return

        raw_qs = req.scope.get("query_string", b"")
        parsed = parse_qs(raw_qs.decode("utf-8", errors="strict"), keep_blank_values=True)

        allowed = set(allowedParams)

        for key, values in parsed.items():
            if key not in allowed:
                raise HTTPException(
                    status_code=422,
                    detail=[{
                        "type": "extra_forbidden",
                        "loc": ["query", key],
                        "msg": f"Unexpected query parameter: {key}"
                    }])

            if len(values) > 1:
                raise HTTPException(
                    status_code=422,
                    detail=[{
                        "type": "duplicate_forbidden",
                        "loc": ["query", key],
                        "msg": f"Duplicate query parameter: {key}"
                    }])
    return checker

class StrictDateTime:
    """
    Strict ISO8601 datetime:
      ✔ Accepts datetime objects
      ✔ Accepts ISO8601 strings: 2025-12-06T10:00:00Z, 2025-12-06T10:00:00+00:00
      ✔ Converts 'Z' → UTC
      ✔ Converts naive datetimes → UTC
      ✘ Rejects integers ("0"), null, garbage strings, etc.
    """

    @classmethod
    def __get_pydantic_core_schema__(cls, source, handler):
        return core_schema.no_info_plain_validator_function(cls.validate)

    @staticmethod
    def validate(value):
        if isinstance(value, datetime.datetime):
            return StrictDateTime._normalize(value)
        if not isinstance(value, str):
            raise ValueError("Invalid datetime value. Expected ISO8601 datetime string.")
        v = value.strip()
        if v.endswith("Z"):
            v = v[:-1] + "+00:00"
        try:
            dt = datetime.datetime.fromisoformat(v)
        except Exception as ex:
            raise ValueError("Invalid datetime format. Expected ISO8601 string.") from ex

        return StrictDateTime._normalize(dt)

    @staticmethod
    def _normalize(dt: datetime.datetime) -> datetime.datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=datetime.timezone.utc)
        return dt

    @classmethod
    def __get_pydantic_json_schema__(cls, schema, handler):
        return {
            "type": "string",
            "format": "date-time",
            "description": "Strict ISO8601 datetime. Only valid ISO8601 datetime strings are accepted."
        }
