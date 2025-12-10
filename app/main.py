#!/usr/bin/env python3
"""Main API application"""
import logging
from fastapi import FastAPI

from app.routers.error_handlers import install_error_handlers
from app.routers.status import status
from app.routers.account import account
from app.routers.compute import compute
from app.routers.filesystem import filesystem
from app.routers.task import task

from . import config


APP = FastAPI(**config.API_CONFIG)

install_error_handlers(APP)

api_prefix = f"{config.API_PREFIX}{config.API_URL}"

# Attach routers under the prefix
APP.include_router(status.router, prefix=api_prefix)
APP.include_router(account.router, prefix=api_prefix)
APP.include_router(compute.router, prefix=api_prefix)
APP.include_router(filesystem.router, prefix=api_prefix)
APP.include_router(task.router, prefix=api_prefix)

logging.getLogger().info(f"API path: {api_prefix}")
