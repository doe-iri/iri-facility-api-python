import os
import logging
import json

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
# /api/v1 mount point means it's the latest backward-compatible url
API_CONFIG = {
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
    API_CONFIG.update(d2)
except Exception as exc:
    logging.getLogger().error(f"Error parsing IRI_API_PARAMS: {exc}")


API_URL_ROOT = os.environ.get("API_URL_ROOT", "https://api.iri.nersc.gov")
API_PREFIX = os.environ.get("API_PREFIX", "/")
API_URL = os.environ.get("API_URL", "api/v1")
