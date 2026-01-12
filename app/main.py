#!/usr/bin/env python3
"""Main API application"""
import logging
from fastapi import FastAPI
from fastapi import Request
from fastapi.routing import APIRoute

from app.routers.error_handlers import install_error_handlers
from app.routers.facility import facility
from app.routers.status import status
from app.routers.account import account
from app.routers.compute import compute
from app.routers.filesystem import filesystem
from app.routers.task import task

from . import config


APP = FastAPI(**config.API_CONFIG)

install_error_handlers(APP)

api_prefix = f"{config.API_PREFIX}{config.API_URL}"

@APP.get(api_prefix)
async def api_discovery(request: Request):
    base = str(request.base_url).rstrip("/")
    items = []
    for route in APP.router.routes:
        if not isinstance(route, APIRoute):
            continue
        # skip docs & openapi
        if route.path.startswith("/docs") or route.path.startswith("/openapi"):
            continue
        for method in route.methods:
            if method == "HEAD" or method == "OPTIONS":
                continue
            items.append({
                "id": route.name or f"{method}_{route.path}",
                "method": method,
                "path": route.path,
                "_links": [
                    {
                        "rel": "self",
                        "href": f"{base.rstrip('/')}{route.path}",
                        "type": "application/json"
                    }
                ]
            })
    return items

# Attach routers under the prefix
APP.include_router(facility.router, prefix=api_prefix)
APP.include_router(status.router, prefix=api_prefix)
APP.include_router(account.router, prefix=api_prefix)
APP.include_router(compute.router, prefix=api_prefix)
APP.include_router(filesystem.router, prefix=api_prefix)
APP.include_router(task.router, prefix=api_prefix)

logging.getLogger().info(f"API path: {api_prefix}")