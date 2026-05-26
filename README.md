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

## Authentication

The IRI API supports three authentication paths, tried in order. The first path that
successfully identifies a user short-circuits the chain. If all three fail, a `401` is
returned with a combined error message from each failed attempt.

```
1. AmSC PingAM OIDC       JWKS-offline JWT validation    IRI_AUTH_AMSC=true  + OIDC_* vars
2. Globus introspection   token introspection call        IRI_AUTH_GLOBUS=true + GLOBUS_RS_* vars
3. Facility API key       adapter.get_current_user()      always active
```

Both external IdP paths default to **off** and must be explicitly opted in.
Accepted truthy values: `true`, `1`, `on`, `yes`.
Accepted falsy values: `false`, `0`, `off`, `no`.

### AmSC PingAM OIDC

Validates inbound JWTs offline via the IdP's JWKS — no introspection round-trip.
Signing algorithms are derived from the discovery document's
`id_token_signing_alg_values_supported` field; `HS*` (HMAC) algorithms are always
rejected even if advertised.

After the JWT is validated, if profile claims (`name`, `email`, etc.) are absent from
the token (common with PingAM, which issues minimal access tokens containing
only `sub`), the IRI API automatically calls the IdP's `userinfo_endpoint` with the
bearer token and merges the returned claims into `token_info`. This means
`get_current_user_oidc(api_key, client_ip, token_info)` in the adapter will always
receive a fully-enriched dict. IdPs that already embed profile claims in the token
(e.g. Keycloak) skip the extra call. The UserInfo fetch fails gracefully — if the
endpoint is unreachable the JWT claims are still passed through unchanged and
authentication succeeds.

| Variable | Default | Required | Description |
|---|---|---|---|
| `IRI_AUTH_AMSC` | `false` | — | Enable this path. Must be `true` to activate. |
| `OIDC_DISCOVERY_URI` | _(none)_ | ✓ | Full URL to the `.well-known/openid-configuration` endpoint. |
| `OIDC_CLIENT_ID` | _(none)_ | ✓ | OIDC client ID. Used as the default expected audience. |
| `OIDC_REQUIRED_AUDIENCE` | _(value of `OIDC_CLIENT_ID`)_ | — | Override the expected `aud` claim. Set this when tokens are issued for a different client ID than the one used for discovery (e.g. Kong's service-account client vs. the user-facing app client). |
| `OIDC_REQUIRED_SCOPES` | _(none)_ | — | Space- or comma-separated scopes that must be present in the token. Also accepted as `OIDC_REQUIRED_SCOPE`. |
| `OIDC_DISCOVERY_TIMEOUT_SECONDS` | `10` | — | HTTP timeout (seconds) for discovery + JWKS requests. |
| `OIDC_DISCOVERY_CACHE_TTL_SECONDS` | `300` | — | Seconds to cache the JWKS keyset in memory before re-fetching. Cache hits/misses are logged at `INFO`. |

Minimal example:
```bash
IRI_AUTH_AMSC=true
OIDC_DISCOVERY_URI=https://identity.dev.amsc.ornl.gov/am/oauth2/.well-known/openid-configuration
OIDC_CLIENT_ID=019de45f-94a0-77c8-918b-10f37667733d
```

### Globus token introspection

Calls Globus Auth to introspect the bearer token. Enforces `active`, `exp`/`nbf`,
the required IRI scope, and a recent `session_info.authentications` entry.
Implement `get_current_user_globus(api_key, client_ip, globus_introspect)` in your
facility adapter to map the Globus identity to a local user ID.

| Variable | Default | Required | Description |
|---|---|---|---|
| `IRI_AUTH_GLOBUS` | `false` | — | Enable this path. Must be `true` to activate. |
| `GLOBUS_RS_ID` | _(none)_ | ✓ | Globus resource-server client ID. |
| `GLOBUS_RS_SECRET` | _(none)_ | ✓ | Globus resource-server client secret. |
| `GLOBUS_RS_SCOPE_SUFFIX` | _(none)_ | ✓ | Appended to `https://auth.globus.org/scopes/{GLOBUS_RS_ID}/` to form the required scope. |

Minimal example:
```bash
IRI_AUTH_GLOBUS=true
GLOBUS_RS_ID=<resource-server-client-id>
GLOBUS_RS_SECRET=<resource-server-client-secret>
GLOBUS_RS_SCOPE_SUFFIX=<scope-suffix>
```

### Facility-specific API key

Always active — no env flags. Delegates entirely to
`adapter.get_current_user(api_key, client_ip)`. If this path also raises, all three
failure messages are combined into the `401` detail.

### Adapter methods called per path

| Auth path | Adapter method called on success |
|---|---|
| AmSC PingAM OIDC | `get_current_user_oidc(api_key, client_ip, token_info)` |
| Globus introspection | `get_current_user_globus(api_key, client_ip, globus_introspect)` |
| Facility API key | `get_current_user(api_key, client_ip)` |

After any path succeeds, `get_user(user_id, api_key, client_ip, token_info, globus_introspect)`
is called to load the full user object. `token_info` and `globus_introspect` are `None`
when the facility API key path won.

### Example: both external IdPs enabled

```bash
IRI_AUTH_AMSC=true
OIDC_DISCOVERY_URI=https://identity.dev.amsc.ornl.gov/am/oauth2/.well-known/openid-configuration
OIDC_CLIENT_ID=019de45f-94a0-77c8-918b-10f37667733d
OIDC_REQUIRED_AUDIENCE=019de45f-94a0-77c8-918b-10f37667733d  # optional if same as CLIENT_ID

IRI_AUTH_GLOBUS=true
GLOBUS_RS_ID=...
GLOBUS_RS_SECRET=...
GLOBUS_RS_SCOPE_SUFFIX=...
```

### Example: API key only (no external IdP)

```bash
# Leave IRI_AUTH_AMSC and IRI_AUTH_GLOBUS unset (or set to false).
# Only facility-specific adapter.get_current_user() will be tried.
```

## Next steps

- Learn more about [fastapi](https://fastapi.tiangolo.com/), including how to run it [in production](https://fastapi.tiangolo.com/advanced/behind-a-proxy/)
- Instead of the simulated state, keep real data in a database
- Specify the monitoring endpoint by setting the [OpenTelemetry](https://opentelemetry.io/docs/zero-code/python/) env vars
- Add additional routers for other API-s
- Add authenticated API-s via an [OAuth2 integration](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)
