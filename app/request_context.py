"""Per-request URL context derived from forwarding headers. (e.g. for Kong or other API gateways)"""
from contextvars import ContextVar

from fastapi import Request

from . import config

_api_url_base: ContextVar[str | None] = ContextVar("_api_url_base", default=None)


def _first_header_value(value: str | None) -> str:
    """Return the first comma-delimited header value with surrounding whitespace removed."""
    return (value or "").split(",")[0].strip()


def external_origin(request: Request) -> str | None:
    """Return ``proto://host/prefix`` as the client addressed this API, from forwarding headers.

    Every URL the API hands back (self-links, problem ``type`` / ``instance``) is built on
    this, so a gateway that mounts the API under a path (``X-Forwarded-Prefix``) gets links
    that work through it. Returns None when no host is known.
    """
    host = _first_header_value(request.headers.get("x-forwarded-host") or request.headers.get("host", ""))
    if not host:
        return None
    proto = _first_header_value(request.headers.get("x-forwarded-proto") or request.url.scheme)
    prefix = _first_header_value(request.headers.get("x-forwarded-prefix") or request.headers.get("x-script-name")).rstrip("/")
    return f"{proto}://{host}{prefix}"


def set_api_url_base(request: Request) -> None:
    """Set the per-request API URL base from forwarding headers."""
    origin = external_origin(request)
    api_prefix = config.API_PREFIX.rstrip("/")
    api_url = config.API_URL.strip("/")
    if origin:
        _api_url_base.set(f"{origin}{api_prefix}/{api_url}")


def get_url_prefix() -> str:
    """Return the per-request API URL base, or fall back to static config."""
    value = _api_url_base.get()
    if value:
        return value
    return f"{config.API_URL_ROOT}{config.API_PREFIX}{config.API_URL}"
