import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.routers.status import status
from app.routers.account import account
from app.routers.compute import compute
from app.routers.filesystem import filesystem
from app.routers.task import task

from . import config

def install_fastapi_error_handlers(app: FastAPI):

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):

        if exc.status_code == 405:
            return JSONResponse(
                status_code=405,
                content={"status": "error", "message": "Method Not Allowed"},
                headers={"Allow": "GET, HEAD"},
            )

        return JSONResponse(
            status_code=exc.status_code,
            content={"status": "error", "message": exc.detail},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        print("Validation error:", exc)
        return JSONResponse(
            status_code=422,
            content={"status": "error", "message": "Validation failed"},
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "Internal server error"},
        )


def install_starlette_error_handler(app: FastAPI):

    @app.exception_handler(StarletteHTTPException)
    async def starlette_error_handler(request: Request, exc: StarletteHTTPException):

        if exc.status_code == 405:
            return JSONResponse(
                status_code=405,
                content={"status": "error", "message": "Method Not Allowed"},
                headers={"Allow": "GET, HEAD"},
            )

        if (
            request.url.path.startswith(f"{config.API_PREFIX}{config.API_URL}")
            and exc.status_code == 404
        ):
            return JSONResponse(
                status_code=404,
                content={"status": "error", "message": "Invalid resource identifier"},
            )

        return JSONResponse(
            status_code=exc.status_code,
            content={"status": "error", "message": exc.detail},
        )


app = FastAPI(**config.API_CONFIG)

install_starlette_error_handler(app)
install_fastapi_error_handlers(app)

api_prefix = f"{config.API_PREFIX}{config.API_URL}"

# Attach routers under the prefix
app.include_router(status.router, prefix=api_prefix)
app.include_router(account.router, prefix=api_prefix)
app.include_router(compute.router, prefix=api_prefix)
app.include_router(filesystem.router, prefix=api_prefix)

logging.getLogger().info(f"API path: {api_prefix}")
