"""Configuration for the IRI Facility API reference implementation."""
import os
import json
from .apilogger import get_stream_logger

LOG_LEVEL = os.environ.get("LOG_LEVEL", "DEBUG")

logger = get_stream_logger(__name__, LOG_LEVEL)

API_V1_VERSION = "1.0.0"  # v1 API contract version
API_V2_VERSION = "2.0.0"  # v2 API contract version

# lines in the description can't have indentation (markup format)
description = """
A simple implementation of the IRI facility API using python and the fastApi library.

For more information, see: [https://iri.science/](https://iri.science/)

<img src="https://iri.science/images/doe-icon-old.png" height=50 />
"""

# version is the openapi.json spec version
# /api/v1 mount point means it's the latest backward-compatible url
API_CONFIG = {
    "title": "IRI Facility API reference implementation",
    "description": description,
    "docs_url": None,
    "contact": {"name": "Facility API contact", "url": "https://www.somefacility.gov/about/contact-us/"},
    "terms_of_service": "https://www.somefacility.gov/terms-of-service",
}
try:
    # optionally overload the init params
    d2 = json.loads(os.environ.get("IRI_API_PARAMS", "{}"))
    API_CONFIG.update(d2)
except Exception as exc:
    logger.error(f"Error parsing IRI_API_PARAMS: {exc}")


API_URL_ROOT = os.environ.get("API_URL_ROOT", "https://api.iri.nersc.gov")
API_PREFIX = os.environ.get("API_PREFIX", "/")
API_V1_PATH = os.environ.get("API_V1_PATH", f"{API_PREFIX}api/v1")
API_V2_PATH = os.environ.get("API_V2_PATH", f"{API_PREFIX}api/v2")

# List of all versioned API paths for middleware detection
API_VERSIONED_PATHS = [API_V1_PATH, API_V2_PATH]

OPENTELEMETRY_ENABLED = os.environ.get("OPENTELEMETRY_ENABLED", "false").lower() == "true"
OPENTELEMETRY_DEBUG = os.environ.get("OPENTELEMETRY_DEBUG", "false").lower() == "true"
OTLP_ENDPOINT = os.environ.get("OTLP_ENDPOINT", "")
OTEL_SAMPLE_RATE = float(os.environ.get("OTEL_SAMPLE_RATE", "0.2"))

# Print all startup config for debugging
logger.info("IRI Facility API starting with config:")
logger.info("="*40)
logger.info(f"API_CONFIG={API_CONFIG}")
logger.info(f"API_URL_ROOT={API_URL_ROOT}")
logger.info(f"API_PREFIX={API_PREFIX}")
logger.info(f"API_V1_PATH={API_V1_PATH}")
logger.info(f"API_V2_PATH={API_V2_PATH}")
logger.info(f"API_VERSIONED_PATHS={API_VERSIONED_PATHS}")
logger.info(f"LOG_LEVEL={LOG_LEVEL}")
logger.info(f"OPENTELEMETRY_ENABLED={OPENTELEMETRY_ENABLED}")
logger.info(f"OPENTELEMETRY_DEBUG={OPENTELEMETRY_DEBUG}")
logger.info(f"OTLP_ENDPOINT={OTLP_ENDPOINT}")
logger.info(f"OTEL_SAMPLE_RATE={OTEL_SAMPLE_RATE}")
logger.info("="*40)
