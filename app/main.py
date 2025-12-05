import logging
from fastapi import FastAPI
from . import config

# include other sub-components as needed
from app.routers.status import status
from app.routers.account import account
from app.routers.compute import compute
from app.routers.filesystem import filesystem


api_app = FastAPI(**config.API_CONFIG)
api_app.include_router(status.router)
api_app.include_router(account.router)
api_app.include_router(compute.router)
api_app.include_router(filesystem.router)

app = FastAPI()

app.mount(f"{config.API_PREFIX}{config.API_URL}", api_app)

logging.getLogger().info(f"API path: {config.API_PREFIX}{config.API_URL}")
