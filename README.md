# <img src="https://iri.science/images/doe-icon-old.png" height=30 /> IRI API reference implementation in Python 3
A proof-of-concept implementation of the IRI status api

See it live: https://api.iri.nersc.gov/api/current/

## Prerequisites

- [install python3](https://www.python.org/downloads/) (version 3.8 or higher)
- [install uv](https://docs.astral.sh/uv/getting-started/installation/)
- make

## Start the dev server

`make`

This will set up a virtual environment, install the dependencies and run the fastApi dev server. Code changes will automatically reload
in the server. To exit, press ctrl+C. This will stop the server and deactivate the virtual environment.

On Windows, see the [Makefile](Makefile) and run the commands manually.

## Visit the dev server

[http://127.0.0.1:8000/api/current/](http://127.0.0.1:8000/api/current/)

## Customizing the API for your facility

At start the API will load the [facility adapter](app/facility_adapter.py) specified in the `IRI_API_ADAPTER` environment variable. If not set
the value will default to the [demo adapter](app/demo_adapter.py). Implement your facility's business logic by subclassing the [facility adapter](app/facility_adapter.py).

You can also optionally override the [FastAPI metadata](https://fastapi.tiangolo.com/tutorial/metadata/), such as `name`, `description`, `terms_of_service`, etc. by providing a valid json object in the `IRI_API_PARAMS` environment variable.

If using docker (see next section), your dockerfile could extend this reference implementation via a `FROM` line and add your custom facility adapter code and init parameters in `ENV` lines.

## Docker support

You can build and run the included dockerfile, for example:
`docker build -t iri . && docker run -p 8000:8000 iri`

## Next steps

- Learn more about [fastapi](https://fastapi.tiangolo.com/), including how to run it [in production](https://fastapi.tiangolo.com/advanced/behind-a-proxy/)
- Instead of the simulated state, keep real data in a [database](/Users/gtorok/dev/iri-api-python/README.md)
- Add monitoring by [integrating with OpenTelemetry](https://opentelemetry.io/docs/zero-code/python/)
- Add additional routers for other API-s
- Add authenticated API-s via an [OAuth2 integration](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)

