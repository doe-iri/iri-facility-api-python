#!/usr/bin/env python3
"""
Default problem schema and example responses for various HTTP status codes.
"""
import logging
from urllib.parse import unquote
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

def get_url_base(request: Request) -> str:
    """Return the base URL for the API."""
    # If behind a proxy (and x-forwarded-* headers present), use the forwarded host and protocol
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    return f"{proto}://{host}/problems"

def problem_response(*, request: Request, status: int,
                     title: str, detail: str, problem_type: str,
                     invalid_params=None, extra_headers=None):
    """Return a JSON problem response with the given status, title, and detail."""
    instance = unquote(str(request.url))
    url_base = get_url_base(request)
    body = {
        "type": f"{url_base}/{problem_type}",
        "title": title,
        "status": status,
        "detail": detail,
        "instance": instance,
    }

    if invalid_params:
        body["invalid_params"] = invalid_params

    headers = extra_headers or {}
    return JSONResponse(status_code=status, content=body, headers=headers)


def install_error_handlers(app: FastAPI):
    """Install custom error handlers for the FastAPI app."""
    # 400 — VALIDATION ERRORS
    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        invalid_params = []

        for err in exc.errors():
            loc = err.get("loc", [])
            name = loc[-1] if loc else "unknown"
            reason = err.get("msg", "Invalid parameter")
            invalid_params.append({"name": name, "reason": reason})

        detail = ", ".join(ip["reason"] for ip in invalid_params)

        return problem_response(
            request=request,
            status=400,
            title="Invalid parameter",
            detail=detail,
            problem_type="invalid-parameter",
            invalid_params=invalid_params,
        )

    # FASTAPI HTTP EXCEPTIONS
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):

        if exc.status_code == 304:
            return JSONResponse(
                status_code=304,
                content=None,
                headers=exc.headers or {})

        if exc.status_code == 401:
            return problem_response(
                request=request,
                status=401,
                title="Unauthorized",
                detail="Bearer token is missing or invalid.",
                problem_type="unauthorized",
                extra_headers={"WWW-Authenticate": "Bearer"},
            )

        if exc.status_code == 403:
            return problem_response(
                request=request,
                status=403,
                title="Forbidden",
                detail="Caller is authenticated but lacks required role.",
                problem_type="forbidden",
            )

        if exc.status_code == 404:
            return problem_response(
                request=request,
                status=404,
                title="Not Found",
                detail=exc.detail or "Invalid resource identifier.",
                problem_type="not-found",
            )

        if exc.status_code == 405:
            return problem_response(
                request=request,
                status=405,
                title="Method Not Allowed",
                detail="HTTP method is not allowed for this resource.",
                problem_type="method-not-allowed",
                extra_headers={"Allow": "GET, HEAD"},
            )

        if exc.status_code == 409:
            return problem_response(
                request=request,
                status=409,
                title="Conflict",
                detail=exc.detail or "Conflict occurred.",
                problem_type="conflict",
            )

        # Generic fallback
        return problem_response(
            request=request,
            status=exc.status_code,
            title=exc.detail or "Error",
            detail=exc.detail or "An error occurred.",
            problem_type="generic-error",
        )

    # STARLETTE HTTP EXCEPTIONS
    @app.exception_handler(StarletteHTTPException)
    async def starlette_handler(request: Request, exc: StarletteHTTPException):

        if exc.status_code == 404:
            return problem_response(
                request=request,
                status=404,
                title="Not Found",
                detail="Invalid resource identifier.",
                problem_type="not-found",
            )

        if exc.status_code == 405:
            return problem_response(
                request=request,
                status=405,
                title="Method Not Allowed",
                detail="HTTP method is not allowed for this resource.",
                problem_type="method-not-allowed",
                extra_headers={"Allow": "GET, HEAD"},
            )

        return problem_response(
            request=request,
            status=exc.status_code,
            title=exc.detail or "Error",
            detail=exc.detail or "An error occurred.",
            problem_type="generic-error",
        )

    # 500 — UNHANDLED EXCEPTIONS
    @app.exception_handler(Exception)
    async def global_handler(request: Request, exc: Exception):
        logging.getLogger().exception(exc)
        return problem_response(
            request=request,
            status=500,
            title="Internal Server Error",
            detail="An unexpected error occurred.",
            problem_type="internal-error",
        )


DEFAULT_PROBLEM_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {"type": "string"},
        "title": {"type": "string"},
        "status": {"type": "integer"},
        "detail": {"type": "string"},
        "instance": {"type": "string"},
        "invalid_params": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["name", "reason"],
            },
        },
    },
    "required": ["type", "title", "status", "detail", "instance"],
}

EXAMPLE_400 = {
    "type": "https://iri.example.com/problems/invalid-parameter",
    "title": "Invalid parameter",
    "status": 400,
    "detail": "modified_since must be in ISO 8601 format.",
    "instance": "/api/v1/status/resources?modified_since=BADVALUE",
    "invalid_params": [
        {"name": "modified_since", "reason": "Invalid datetime format"}
    ]
}

EXAMPLE_401 = {
    "type": "https://iri.example.com/problems/unauthorized",
    "title": "Unauthorized",
    "status": 401,
    "detail": "Bearer token is missing or invalid.",
    "instance": "/api/v1/status/resources"
}

EXAMPLE_403 = {
    "type": "https://iri.example.com/problems/forbidden",
    "title": "Forbidden",
    "status": 403,
    "detail": "Caller is authenticated but lacks required role.",
    "instance": "/api/v1/status/resources"
}

EXAMPLE_404 = {
    "type": "https://iri.example.com/problems/not-found",
    "title": "Not Found",
    "status": 404,
    "detail": "The resource ID 'abc123' does not exist.",
    "instance": "/api/v1/status/resources/abc123"
}

EXAMPLE_405 = {
    "type": "https://iri.example.com/problems/method-not-allowed",
    "title": "Method Not Allowed",
    "status": 405,
    "detail": "HTTP method TRACE is not allowed for this endpoint.",
    "instance": "/api/v1/status/resources"
}

EXAMPLE_409 = {
    "type": "https://iri.example.com/problems/conflict",
    "title": "Conflict",
    "status": 409,
    "detail": "A job with this ID already exists.",
    "instance": "/api/v1/compute/job/perlmutter/123"
}

EXAMPLE_422 = {
    "type": "https://iri.example.com/problems/unprocessable-entity",
    "title": "Unprocessable Entity",
    "status": 422,
    "detail": "The PSIJ JobSpec is syntactically correct but invalid.",
    "instance": "/api/v1/compute/job/perlmutter",
    "invalid_params": [
        {"name": "job_spec.executable", "reason": "Executable must be provided"}
    ]
}

EXAMPLE_500 = {
    "type": "https://iri.example.com/problems/internal-error",
    "title": "Internal Server Error",
    "status": 500,
    "detail": "An unexpected error occurred.",
    "instance": "/api/v1/status/resources"
}

EXAMPLE_501 = {
    "type": "https://iri.example.com/problems/not-implemented",
    "title": "Not Implemented",
    "status": 501,
    "detail": "This functionality is not implemented.",
    "instance": "/api/v1/status/resources"
}

EXAMPLE_503 = {
    "type": "https://iri.example.com/problems/service-unavailable",
    "title": "Service Unavailable",
    "status": 503,
    "detail": "The service is temporarily unavailable.",
    "instance": "/api/v1/status/resources"
}

EXAMPLE_504 = {
    "type": "https://iri.example.com/problems/gateway-timeout",
    "title": "Gateway Timeout",
    "status": 504,
    "detail": "The server did not receive a timely response.",
    "instance": "/api/v1/status/resources"
}

DEFAULT_RESPONSES = {
    400: {
        "description": "Invalid request parameters",
        "content": {
            "application/problem+json": {
                "schema": DEFAULT_PROBLEM_SCHEMA,
                "example": EXAMPLE_400,
            }
        },
    },

    401: {
        "description": "Unauthorized",
        "headers": {
            "WWW-Authenticate": {
                "description": "Bearer authentication challenge",
                "schema": {"type": "string"},
            }
        },
        "content": {
            "application/problem+json": {
                "schema": DEFAULT_PROBLEM_SCHEMA,
                "example": EXAMPLE_401,
            }
        },
    },

    403: {
        "description": "Forbidden",
        "content": {
            "application/problem+json": {
                "schema": DEFAULT_PROBLEM_SCHEMA,
                "example": EXAMPLE_403,
            }
        },
    },

    404: {
        "description": "Not Found",
        "content": {
            "application/problem+json": {
                "schema": DEFAULT_PROBLEM_SCHEMA,
                "example": EXAMPLE_404,
            }
        },
    },

    405: {
        "description": "Method Not Allowed",
        "headers": {
            "Allow": {
                "description": "Allowed HTTP methods",
                "schema": {"type": "string"},
            }
        },
        "content": {
            "application/problem+json": {
                "schema": DEFAULT_PROBLEM_SCHEMA,
                "example": EXAMPLE_405,
            }
        },
    },

    409: {
        "description": "Conflict",
        "content": {
            "application/problem+json": {
                "schema": DEFAULT_PROBLEM_SCHEMA,
                "example": EXAMPLE_409,
            }
        },
    },

    422: {
        "description": "Unprocessable Entity",
        "content": {
            "application/problem+json": {
                "schema": DEFAULT_PROBLEM_SCHEMA,
                "example": EXAMPLE_422,
            }
        },
    },

    500: {
        "description": "Internal Server Error",
        "content": {
            "application/problem+json": {
                "schema": DEFAULT_PROBLEM_SCHEMA,
                "example": EXAMPLE_500,
            }
        },
    },

    501: {
        "description": "Not Implemented",
        "content": {
            "application/problem+json": {
                "schema": DEFAULT_PROBLEM_SCHEMA,
                "example": EXAMPLE_501,
            }
        }
    },

    503: {
        "description": "Service Unavailable",
        "content": {
            "application/problem+json": {
                "schema": DEFAULT_PROBLEM_SCHEMA,
                "example": EXAMPLE_503,
            }
        }
    },

    504: {
        "description": "Gateway Timeout",
        "content": {
            "application/problem+json": {
                "schema": DEFAULT_PROBLEM_SCHEMA,
                "example": EXAMPLE_504,
            }
        }
    },

    304: {"description": "Not Modified"},
}
