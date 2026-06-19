# <img src="https://iri.science/images/doe-icon-old.png" height=30 /> IRI API reference implementation in Python 3
Python reference implementation of the IRI facility API, standardizing endpoints, parameters, and return values across DOE computational facilities.

See it live:

- NERSC instance:
   - API docs: https://api.iri.nersc.gov
   - API requests: https://api.iri.nersc.gov/api/v2/
- ALCF instance:
   - API docs: https://api.alcf.anl.gov
   - API requests: https://api.alcf.anl.gov/api/v1/
- ESnet instance: https://iri-dev.ppg.es.net

## Prerequisites

- [install python3](https://www.python.org/downloads/) (version 3.12 or higher)
- [install uv](https://docs.astral.sh/uv/getting-started/installation/)
- make

## Start the dev server

`make`

This will set up a virtual environment, install the dependencies and run the fastApi dev server. Code changes will automatically reload
in the server. To exit, press ctrl+C. This will stop the server and deactivate the virtual environment.

On Windows, see the [Makefile](Makefile) and run the commands manually.

## Visit the dev server

[http://127.0.0.1:8000/](http://127.0.0.1:8000/)

## Customizing the API for your facility

The reference implementation is meant to be customized for your facility's IRI implementation. Running the IRI api unmodified will show only fake, test data. The paragraphs below describe how to customize the business logic and appearance of the API for your facility.

### Customizing the business logic for your facility
The IRI API handles the "boilerplate" of setting up the rest API. It delegates to the per-facility business logic via interface definitions. These interfaces are implemented as abstract classes, one per api group (status, account, etc.). Each router directory defines a FacilityAdapter class (eg. [the status adapter](app/routers/status/facility_adapter.py)) that is expected to be implemented by the facility who is exposing an IRI API instance.

## Forwarded Project Header For Compute Requests

Compute submission and update requests support a trusted forwarded header named `X-IRI-Facility-Project`.

This header is intended for deployments where an upstream trusted component has already resolved the caller's project/account into the facility-native value required by the downstream scheduler or execution system.

When `X-IRI-Facility-Project` is present and valid:

- IRI treats that header value as the effective project/account for the compute request.
- The downstream compute adapter receives the request as if that value were the facility-native account to use for job submission or update.
- Implementations may surface that effective value in returned job metadata, scheduler requests, labels, annotations, or similar downstream submission context.

For compute submit/update requests, the effective project/account must be specified in exactly one place:

- `job_spec.attributes.account`, or
- `X-IRI-Facility-Project`

If both are provided, IRI returns `400 Bad Request`.
If neither is provided, IRI returns `400 Bad Request`.
This behavior is specific to compute submission/update handling; read-only endpoints are unchanged.

The specific implementations can be specified via the `IRI_API_ADAPTER_*` environment variables. For example the adapter for the `status` api would be given by setting `IRI_API_ADAPTER_status` to the full python module and class implementing `app.routers.status.facility_adapter.FacilityAdapter`. (eg. `IRI_API_ADAPTER_status=myfacility.MyFacilityStatusAdapter`)

As a default implementation, this project supplies the [demo adapter](app/demo_adapter.py) which implements every facility adapter with fake data.

### Customizing the API meta-data
You can optionally override the [FastAPI metadata](https://fastapi.tiangolo.com/tutorial/metadata/), such as `name`, `description`, `terms_of_service`, etc. by providing a valid json object in the `IRI_API_PARAMS` environment variable.

If using docker (see next section), your dockerfile could extend this reference implementation via a `FROM` line and add your custom facility adapter code and init parameters in `ENV` lines.

### Environment variables

- `API_URL_ROOT`: the base url when constructing links returned by the api (eg.: https://iri.myfacility.com)
- `API_PREFIX`: the path prefix where the api is hosted. Defaults to `/`. (eg.: `/api`)
- `API_URL`: the path to the api itself. Defaults to `api/v2`.
### OpenTelemetry

The API supports OpenTelemetry for distributed tracing and metrics. Traces and metrics can be independently enabled or disabled.

| Variable | Default | Description |
|---|---|---|
| `OPENTELEMETRY_ENABLED` | `false` | Master switch. Must be `true` for any telemetry to be emitted. |
| `OTEL_TRACES_ENABLED` | `true` | Enable trace export. Only takes effect when `OPENTELEMETRY_ENABLED=true`. |
| `OTEL_METRICS_ENABLED` | `true` | Enable metric export. Only takes effect when `OPENTELEMETRY_ENABLED=true`. |
| `OTLP_ENDPOINT` | `""` | gRPC endpoint for the OTLP collector (e.g. `http://otel-collector:4317`). When empty, telemetry is printed to the console. |
| `OPENTELEMETRY_DEBUG` | `false` | Sets trace sample rate to 100% (overrides `OTEL_SAMPLE_RATE`). |
| `OTEL_SAMPLE_RATE` | `0.2` | Trace sampling rate (0.0 to 1.0). Ignored when `OPENTELEMETRY_DEBUG=true`. |
| `OTEL_METRIC_EXPORT_INTERVAL` | `60000` | Metric export interval in milliseconds. |

When metrics are enabled, the FastAPI instrumentor automatically emits standard HTTP server metrics: `http.server.active_requests`, `http.server.duration`, and `http.server.response.size`.

Examples:
```bash
# Traces and metrics to an OTLP collector
OPENTELEMETRY_ENABLED=true OTLP_ENDPOINT=http://otel-collector:4317

# Traces only, no metrics
OPENTELEMETRY_ENABLED=true OTEL_METRICS_ENABLED=false

# Metrics only, no traces
OPENTELEMETRY_ENABLED=true OTEL_TRACES_ENABLED=false

# Debug mode: 100% sampling, console output
OPENTELEMETRY_ENABLED=true OPENTELEMETRY_DEBUG=true
```

Links to data, created by this api, will concatenate these values producing links, eg: `https://iri.myfacility.com/my_api_prefix/my_api_url/projects/123`

- `IRI_API_PARAMS`: as described above, this is a way to customize the API meta-data
- `IRI_API_ADAPTER_*`: these values specify the business logic for the per-api-group implementation of a facility_adapter. For example: `IRI_API_ADAPTER_status=myfacility.MyFacilityStatusAdapter` would load the implementation of the `app.routers.status.facility_adapter.FacilityAdapter` abstract class to handle the `status` business logic for your facility.

  The full list of router adapters and the abstract base class each must implement:

  | Variable | Mounted at | Abstract base class your adapter must subclass |
  |---|---|---|
  | `IRI_API_ADAPTER_facility`   | `/facility/...`   | [`app.routers.facility.facility_adapter.FacilityAdapter`](app/routers/facility/facility_adapter.py) |
  | `IRI_API_ADAPTER_status`     | `/status/...`     | [`app.routers.status.facility_adapter.FacilityAdapter`](app/routers/status/facility_adapter.py) |
  | `IRI_API_ADAPTER_account`    | `/account/...`    | [`app.routers.account.facility_adapter.FacilityAdapter`](app/routers/account/facility_adapter.py) |
  | `IRI_API_ADAPTER_compute`    | `/compute/...`    | [`app.routers.compute.facility_adapter.FacilityAdapter`](app/routers/compute/facility_adapter.py) |
  | `IRI_API_ADAPTER_filesystem` | `/filesystem/...` | [`app.routers.filesystem.facility_adapter.FacilityAdapter`](app/routers/filesystem/facility_adapter.py) |
  | `IRI_API_ADAPTER_storage`    | `/storage/...`    | [`app.routers.storage.facility_adapter.FacilityAdapter`](app/routers/storage/facility_adapter.py) |
  | `IRI_API_ADAPTER_task`       | `/task/...`       | [`app.routers.task.facility_adapter.FacilityAdapter`](app/routers/task/facility_adapter.py) |

  Each value is a `module.path.ClassName` string. `app.demo_adapter.DemoAdapter` implements all of them and is what `make dev` wires up by default. A router whose `IRI_API_ADAPTER_*` is not set is hidden from the API at startup unless `IRI_SHOW_MISSING_ROUTES=true`.

- `IRI_SHOW_MISSING_ROUTES`: hide api groups that don't have an `IRI_API_ADAPTER_*` environment variable defined, if set to `true`. This way if your facility only wishes to expose some api groups but not others, they can be hidden. (Defaults to `false`.)

### Logging

Logs always go to stdout. Optionally, logs can also be written to a rotating file.

| Variable | Default | Description |
|---|---|---|
| `LOG_LEVEL` | `DEBUG` | Logging level for the API and adapters (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`). |
| `IRI_LOG_FILE` | _(none)_ | File path for API logs. When set, logs go to both stdout and this file. |
| `LOG_FILE` | _(none)_ | Fallback file path when `IRI_LOG_FILE` is not set. |
| `IRI_LOG_ROTATION_DAYS` | `5` | Number of daily rotated log files to retain. |
| `LOG_ROTATION_DAYS` | `5` | Fallback retention when `IRI_LOG_ROTATION_DAYS` is not set. |

For local development, `make` writes logs to `runtime-logs.log` by default and keeps `5` daily rotated files. Use `make LOG_FILE=/tmp/iri-api.log`, `make IRI_LOG_FILE=/tmp/iri-api.log`, or `make LOG_ROTATION_DAYS=10` to override those defaults. You can also put the same variables in `local.env`.

## Idempotency

Compute `submit_job` and `update_job` endpoints support an optional `Idempotency-Key` request header. When provided, the server caches the first successful response for that key and returns it on any subsequent request with the same key and body — without calling the facility adapter again. This makes it safe for clients to retry on timeout without risking duplicate job submissions.

### Behaviour

| Scenario | Response |
|---|---|
| First request | Calls adapter, caches result. Response header: `Idempotency-Key-Reply: miss` |
| Retry, same body | Returns cached result. Response header: `Idempotency-Key-Reply: hit` |
| Retry, different body | `422 Unprocessable Entity` |
| Concurrent duplicate (in-flight) | `409 Conflict` with `Retry-After: 2` |
| Adapter raises | Lock released; client may retry safely |

### Backing store

| `REDIS_URL` set? | Store used | Suitable for |
|---|---|---|
| No (default) | In-process dict | Dev / single-instance |
| Yes | Redis | Multi-replica production |

For multi-replica deployments, Redis is required. Run a local Redis instance with `make redis`.

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `REDIS_URL` | _(unset)_ | Redis connection URL (e.g. `redis://localhost:6379`). When unset, uses in-memory store. |
| `IDEMPOTENCY_TTL_SECONDS` | `86400` | How long a cached response is retained after a successful call (24 hours). |
| `LOCK_TTL_SECONDS` | `60` | Maximum seconds an in-flight request holds the lock. If the IRI process crashes mid-request, the lock auto-expires after this interval so the next retry is treated as a fresh request. Set higher if your facility's scheduler API is known to be slow. |

### Quick start (dev)

```bash
make redis                          # start Redis container on :6379
# add to local.env:
export REDIS_URL=redis://localhost:6379
make                                # start IRI dev server
```

## Docker support

You can either use the docker images created on github.com or build the image yourself.

### Use the github docker image

Github is set up to [automatically build](.github/workflows/docker-build.yml) the latest image and push it to its registry on each commit to the `main` branch.

For now (until this repo is made public), you will have to authenticate to the github container registry with your github username and Personal Access Token (PAT) as your password:

`docker login ghcr.io -u <your username>`
(For the password, enter your PAT)

Once authenticated, you can now pull:

`docker pull ghcr.io/doe-iri/iri-facility-api-python:main`

And also run the code with the demo adapter:

`docker run -p8000:8000 -e IRI_SHOW_MISSING_ROUTES=true ghcr.io/doe-iri/iri-facility-api-python:main`

Visit: http://127.0.0.1:8000/

### Build the image yourself

You can build and run the included dockerfile, for example:
`docker build -t iri . && docker run -p 8000:8000 iri`

### Using the base docker image

Rather than forking this repo, docker is recommended for running your facility implementation. For example, you could use the following example Dockerfile for your IRI api:

```Dockerfile
FROM ghcr.io/doe-iri/iri-facility-api-python:main
# or: FROM registry.myfacility.gov/isg/iri/iri:main

# The "myfacility" directory contains the adapters with business logic
# specific to your IRI implementaion.
# Here we copy them into the docker image to a location that will be
# visible to the running app.
COPY ./myfacility /app/myfacility/

# Install additional libraries your implementation needs
RUN pip install additional_libraries

# Customize your image via environment variables
ENV IRI_API_ADAPTER_status="myfacility.status_adapter.StatusAdapter"
ENV IRI_API_ADAPTER_account="myfacility.account_adapter.AccountAdapter"
ENV IRI_API_ADAPTER_compute="myfacility.compute_adapter.ComputeAdapter"
ENV API_PREFIX="/myfacility/"
ENV IRI_API_PARAMS='{ \
    "title": "Facility XYZ implementation of the IRI api", \
    "terms_of_service": "https://myfacility.gov/aup", \
    "docs_url": "/", \
    "contact": { \
        "name": "My Facility Contact", \
        "url": "https://myfacility.gov/about/contact-us/" \
    } \
}'
```

## Globus auth integration

You can optionally use globus for authorization. Steps to use globus:
- ask someone to add your globus account to the IRI Resource Server
- log into globus and make a secret for yourself for the IRI Resource Server
- if you want to create tokens during developent, also create a separate globus app
- `cp local-template.env local.env` and fill in the missing values
- to mint a token, run `make globus`, click the link and copy the code from the browser url bar back into the terminal
- you can also run `make manage-globus` but be sure to not accidentally delete the `iri-api` scope. (Maybe it's better if you don't run this app)
- now you can run `make` for the dev server and enjoy using your globus iri access tokens (in the demo adapter they will all resolve to the user `gtorok`)
- for your facility:
   - implement the `get_current_user_globus` method (see iri_adapter.py). Here you can look at the linked globus identities and session info to determine what the local username is
   - make sure the values in `local.env` are available in the deployed app

## Next steps

- Learn more about [fastapi](https://fastapi.tiangolo.com/), including how to run it [in production](https://fastapi.tiangolo.com/advanced/behind-a-proxy/)
- Instead of the simulated state, keep real data in a database
- Specify the monitoring endpoint by setting the [OpenTelemetry](https://opentelemetry.io/docs/zero-code/python/) env vars
- Add additional routers for other API-s
- Add authenticated API-s via an [OAuth2 integration](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)
