#!/usr/bin/env python3
"""Main API application"""

import logging
from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, BatchSpanProcessor, SimpleSpanProcessor
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased, ParentBased
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from . import config
from .apilogger import configure_logging

from app.routers.error_handlers import install_error_handlers
from app.routers.loader import load_routers, version_from_api_url

configure_logging(config.LOG_LEVEL)

# ------------------------------------------------------------------
# OpenTelemetry Tracing Configuration
# ------------------------------------------------------------------
if config.OPENTELEMETRY_ENABLED:
    resource = Resource.create({"service.name": "iri-facility-api", "service.version": config.API_VERSION, "service.endpoint": config.API_URL_ROOT})

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

APP = FastAPI(servers=[{"url": config.API_URL_ROOT}], **config.API_CONFIG)

if config.OPENTELEMETRY_ENABLED:
    FastAPIInstrumentor.instrument_app(APP)

install_error_handlers(APP)

api_prefix = f"{config.API_PREFIX}{config.API_URL}"

for loaded_router in load_routers(version_from_api_url(config.API_URL)):
    APP.include_router(loaded_router.router, prefix=api_prefix)

logging.getLogger().info(f"API path: {api_prefix}")
