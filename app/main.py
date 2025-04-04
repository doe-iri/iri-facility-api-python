from fastapi import FastAPI
from . import state

# include other sub-components as needed
from app.routers.status import status

app = FastAPI()

API_VERSION = "1.0.0"

# lines in the description can't have indentation (markup format)
description = """
A simple implementation of the IRI facility API using python and the fastApi library.

For more information, see: [https://iri.science/](https://iri.science/)

<img src="https://iri.science/images/doe-icon-old.png" height=50 />
"""

# version is the openapi.json spec version
# /api/current mount point means it's the latest backward-compatible url
api_app = FastAPI(
    title="IRI Facility API reference implementation",
    description=description,
    version=API_VERSION,
    docs_url="/",
    contact={
        "name": "Facility API contact",
        "url": "https://www.somefacility.gov/about/contact-us/"
    },
    terms_of_service="https://www.somefacility.gov/terms-of-service",
)
api_app.include_router(status.router)

# for non-backward compatible versions, we can mount specific versions, eg. /api/v1
# but, /api/current is always the latest
app.mount("/api/current", api_app)

@app.on_event("startup")
async def startup_event():
    # create some simulated state. In a real app this would be a db connection or similar.
    st = state.SimulatedState()
    api_app.state.resources = st.resources
    api_app.state.events = st.events
    api_app.state.incidents = st.incidents
