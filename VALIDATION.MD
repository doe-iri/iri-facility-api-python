# API Validation with Schemathesis

On every pull request or push to `main` branch, Github Actions run the following steps below that validates an IRI Facility API implementation against OpenAPI spec using Schemathesis.

1. Builds the Facility API Docker image from Dockerfile.
2. Runs the API container with demo adapter.
3. Waits for `/openapi.json` to become available on localhost:8000.
4. Runs Schemathesis validation twice:
   - Against Facilities API’s OpenAPI spec. (http://localhost:8000/openapi.json)
   - Against the official IRI Facility API OpenAPI spec. (https://github.com/doe-iri/iri-facility-api-docs/blob/main/specification/openapi/openapi_iri_facility_api_v1.json)
5. Fails the workflow if either validation fails.
6. Saves Schemathesis HTML/XML reports as artifacts (or saves it locally when run with `act`).
7. Dumps API container logs and do clean up to stop container.

## Running locally

```bash
act -W .github/workflows/api-validator.yml -s GITHUB_TOKEN=<GITHUB_TOKEN>
```

## Known issues

Python implementation not fully aligns with the official Specification. Running against Official Spec will continue to fail, until Spec or Py implementation is fixed.
