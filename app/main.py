import os
import importlib
import logging
import json
from fastapi import FastAPI
from contextlib import asynccontextmanager
from .facility_adapter import FacilityAdapter

# include other sub-components as needed
from app.routers.status import status

logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)

API_VERSION = "1.0.0"

# lines in the description can't have indentation (markup format)
description = """
A simple implementation of the IRI facility API using python and the fastApi library.

For more information, see: [https://iri.science/](https://iri.science/)

<img src="https://iri.science/images/doe-icon-old.png" height=50 />
"""

# version is the openapi.json spec version
# /api/current mount point means it's the latest backward-compatible url
d = {
    "title": "IRI Facility API reference implementation",
    "description": description,
    "version": API_VERSION,
    "docs_url": "/",
    "contact": {
        "name": "Facility API contact",
        "url": "https://www.somefacility.gov/about/contact-us/"
    },
    "terms_of_service": "https://www.somefacility.gov/terms-of-service"
}
try:
    # optionally overload the init params
    d2 = json.loads(os.environ.get("IRI_API_PARAMS", "{}"))
    d.update(d2)
except Exception as exc:
    logging.getLogger().error(f"Error parsing IRI_API_PARAMS: {exc}")
api_app = FastAPI(**d)
api_app.include_router(status.router)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the facility-specific adapter
    adapter_name = os.environ.get("IRI_API_ADAPTER", "app.demo_adapter.DemoAdapter")
    logging.getLogger().info(f"Using adapter: {adapter_name}")
    parts = adapter_name.rsplit(".", 1)
    module = importlib.import_module(parts[0])    
    AdapterClass = getattr(module, parts[1])
    if not issubclass(AdapterClass, FacilityAdapter):
        raise Exception(f"{adapter_name} should implement FacilityAdapter")
    logging.getLogger().info("\tSuccessfully loaded adapter.")
    api_app.state.adapter = AdapterClass()

    yield


app = FastAPI(lifespan=lifespan)


# for non-backward compatible versions, we can mount specific versions, eg. /api/v1
# but, /api/current is always the latest
app.mount("/api/current", api_app)

