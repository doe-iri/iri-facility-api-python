#!/usr/bin/env python3
"""Main API application"""

import logging
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, BatchSpanProcessor, SimpleSpanProcessor
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased, ParentBased
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from app.routers.error_handlers import install_error_handlers
from app.routers.facility import facility
from app.routers.status import status
from app.routers.account import account
from app.routers.compute import compute
from app.routers.filesystem import filesystem
from app.routers.task import task
from app.middleware import APIVersionMiddleware

from . import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)

def _make_config(version):
    d = {**config.API_CONFIG}
    d["version"] = version
    d["title"] = f"{d['title']} - {version}"
    d["docs_url"] = "/"
    return d

# ------------------------------------------------------------------
# OpenTelemetry Tracing Configuration
# ------------------------------------------------------------------
if config.OPENTELEMETRY_ENABLED:
    resource = Resource.create({"service.name": "iri-facility-api", "service.version": "1.0.0", "service.endpoint": config.API_URL_ROOT})

    samplerate = "1.0" if config.OPENTELEMETRY_DEBUG else config.OTEL_SAMPLE_RATE
    provider = TracerProvider(resource=resource, sampler=ParentBased(TraceIdRatioBased(samplerate)))
    trace.set_tracer_provider(provider)

    if config.OTLP_ENDPOINT:
        exporter = OTLPSpanExporter(endpoint=config.OTLP_ENDPOINT, insecure=True)
        span_processor = BatchSpanProcessor(exporter)
    else:
        exporter = ConsoleSpanExporter()
        span_processor = SimpleSpanProcessor(exporter)
    provider.add_span_processor(span_processor)
    tracer = trace.get_tracer(__name__)
# ------------------------------------------------------------------

# Create main app
APP = FastAPI(servers=[{"url": config.API_URL_ROOT}], **config.API_CONFIG)

# Create v1 app
app_v1 = FastAPI(**_make_config(config.API_V1_VERSION))
app_v1.add_middleware(APIVersionMiddleware)
install_error_handlers(app_v1)
if config.OPENTELEMETRY_ENABLED:
    FastAPIInstrumentor.instrument_app(app_v1)

# Attach v1 routers
app_v1.include_router(facility.router)
app_v1.include_router(status.router)
app_v1.include_router(account.router)
app_v1.include_router(compute.router)
app_v1.include_router(filesystem.router)
app_v1.include_router(task.router)

# Create v2 app (initially identical to v1, modify as needed for breaking changes)
app_v2 = FastAPI(**_make_config(config.API_V2_VERSION))
app_v2.add_middleware(APIVersionMiddleware)
install_error_handlers(app_v2)
if config.OPENTELEMETRY_ENABLED:
    FastAPIInstrumentor.instrument_app(app_v2)

# Attach v2 routers (same as v1 for now)
app_v2.include_router(facility.router)
app_v2.include_router(status.router)
app_v2.include_router(account.router)
app_v2.include_router(compute.router)
app_v2.include_router(filesystem.router)
app_v2.include_router(task.router)

# Mount versioned apps to main app
APP.mount(config.API_V1_PATH, app_v1)
APP.mount(config.API_V2_PATH, app_v2)

logging.getLogger().info(f"API v1 mounted at: {config.API_V1_PATH}")
logging.getLogger().info(f"API v2 mounted at: {config.API_V2_PATH}")

@APP.get("/")
async def redirect_root():
    # redirect the root swagger docs to the latest version
    return RedirectResponse(url=f"{config.API_VERSIONED_PATHS[-1]}")
