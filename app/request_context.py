"""Per-request URL context derived from forwarding headers. (e.g. for Kong or other API gateways)"""
from contextvars import ContextVar

from fastapi import Request

from . import config

_api_url_base: ContextVar[str | None] = ContextVar("_api_url_base", default=None)


def set_api_url_base(request: Request) -> None:
    """Set the per-request API URL base from forwarding headers."""
    host = (request.headers.get("x-forwarded-host") or
            request.headers.get("host", "")).split(",")[0].strip()
    proto = (request.headers.get("x-forwarded-proto") or
             request.url.scheme).split(",")[0].strip()
    prefix = (request.headers.get("x-forwarded-prefix")
              or request.headers.get("x-script-name")
              or "").rstrip("/")
    api_url = config.API_URL.strip("/")
    if host:
        _api_url_base.set(f"{proto}://{host}{prefix}/{api_url}")


def get_url_prefix() -> str:
    """Return the per-request API URL base, or fall back to static config."""
    value = _api_url_base.get()
    if value:
        return value
    return f"{config.API_URL_ROOT}{config.API_PREFIX}{config.API_URL}"
