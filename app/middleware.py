"""Middleware for the IRI Facility API."""
from opentelemetry import trace
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from . import config
from .context import current_api_version


class APIVersionMiddleware(BaseHTTPMiddleware):
    """Middleware to extract and set the API version context from request path."""

    async def dispatch(self, request: Request, call_next):
        # Extract API version from path by matching against configured versioned paths
        request_path = request.url.path
        api_version = None

        for versioned_path in config.API_VERSIONED_PATHS:
            if request_path.startswith(versioned_path):
                api_version = versioned_path
                current_api_version.set(versioned_path)
                break

        # Add API version to OpenTelemetry span
        if api_version and config.OPENTELEMETRY_ENABLED:
            span = trace.get_current_span()
            if span.is_recording():
                span.set_attribute("api.version", api_version)

        response: Response = await call_next(request)
        return response
