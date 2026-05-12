# `facility_notebook_smoke.py`

Facility-aware end-to-end smoke test for the IRI Facility API. Acquires an
auth token, discovers resources, submits a small bash compute job, polls for
completion, and exercises the full filesystem operation set (`mkdir`,
`upload`, `ls`, `chmod`, `head`, `tail`, `view`, `checksum`, `cp`, `mv`,
`symlink`, `compress`, `extract`, `download`, `rm`).

It is the script equivalent of the example notebooks
(`compute-jobs.ipynb`, `filesystem.ipynb`) and is the recommended way to verify
a facility deployment in one run.

---

## Supported facilities

| `--facility` | Base URL | Auth mode |
|---|---|---|
| `esnet-east` | `https://iri-dev.ppg.es.net/api/v1` | OAuth2 password (SENSE) |
| `esnet-west` | `https://esnet-west.sdn-sense.net/api/v1` | OAuth2 password (SENSE) |
| `nersc`      | `https://api.iri.nersc.gov/api/v1` | Globus Confidential App |
| `alcf`       | `https://api.alcf.anl.gov/api/v1` | Globus Native App |

Override the URL with `--base-url` if you are pointing at a dev / staging
deployment.

---

## Prerequisites

- Python 3.13 (matches `pyproject.toml`)
- `requests`, `globus-sdk` (already in the project's `pyproject.toml`)
- Optional: `python-dotenv` — if installed, a `.env` file in the working
  directory is loaded automatically.

From the repo root:

```bash
.venv/bin/python tools/facility_notebook_smoke.py --facility nersc --auto-pick
```

---

## Environment variables

Every variable is checked first in its facility-prefixed form, then in its
generic form. So `EAST_USERNAME` overrides `USERNAME`, `NERSC_GLOBUS_ID`
overrides `GLOBUS_ID`, etc.

### ESnet East / West (SENSE password grant)

| Variable | Required | Notes |
|---|---|---|
| `{PREFIX}_SENSE_AUTH_ENDPOINT` | yes | OAuth2 token endpoint |
| `{PREFIX}_SENSE_CLIENT_ID`     | yes | OAuth2 client id |
| `{PREFIX}_SENSE_SECRET`        | yes | OAuth2 client secret |
| `{PREFIX}_SENSE_USERNAME`      | yes | User account |
| `{PREFIX}_SENSE_PASSWORD`      | yes | User password |
| `{PREFIX}_SENSE_VERIFY_TLS`    | no  | `false` to disable TLS verify |

`{PREFIX}` is `EAST` or `WEST`. The unprefixed `SENSE_*` forms also work.

### NERSC (Globus Confidential App)

| Variable | Required | Default |
|---|---|---|
| `NERSC_GLOBUS_ID`                 | yes | — |
| `NERSC_GLOBUS_SECRET`             | yes | — |
| `NERSC_GLOBUS_RS_ID`              | no  | `ed3e577d-f7f3-4639-b96e-ff5a8445d699` |
| `NERSC_GLOBUS_RS_SCOPE_SUFFIX`    | no  | `iri_api` |
| `NERSC_GLOBUS_RS_SCOPE`           | no  | derived from RS_ID + suffix |
| `NERSC_GLOBUS_REDIRECT_URI`       | no  | `http://localhost:5000/callback` |

The flow opens a browser URL for you to authorize; paste the `code=…` value
back into the terminal.

### ALCF (Globus Native App — `juztas/iri-fs` filesystem scope)

| Variable | Required | Default |
|---|---|---|
| `ALCF_GLOBUS_CLIENT_ID`        | no | `8b84fc2d-49e9-49ea-b54d-b3a29a70cf31` |
| `ALCF_GLOBUS_SCOPE_CLIENT_ID`  | no | `6be511f6-a071-471f-9bc0-02a0d0836723` |
| `ALCF_GLOBUS_SCOPE`            | no | derived `…/filesystem` scope |

### Skipping interactive auth

You can always bypass the auth flow by exporting a token directly:

```bash
export NERSC_IRI_API_TOKEN="eyJhbGc...."   # facility-scoped form
# or
export IRI_API_TOKEN="eyJhbGc...."          # generic form
```

If both are set, the facility-scoped form wins.

### Job parameters

| Variable | Maps to | Default |
|---|---|---|
| `{PREFIX}_IRI_JOB_DIR` / `IRI_JOB_DIR` | `--job-dir` | facility-specific |
| `{PREFIX}_IRI_QUEUE` / `IRI_QUEUE`     | `--queue`   | `debug` |
| `{PREFIX}_IRI_ACCOUNT` / `IRI_ACCOUNT` | `--account` | `interactive` (NERSC: `amsc013`) |

---

## Token caching

After a successful interactive login the token is cached at:

```
~/.iri_token_east.json
~/.iri_token_west.json
~/.iri_token_nersc.json
~/.iri_token_alcf.json
```

Plus a legacy `~/.iri_token.json` for backward compat with older notebooks.

To reuse a cached token (and only fall back to live auth if it is missing):

```bash
… --reuse-token
```

Environment-supplied tokens always take precedence over cached ones.

---

## CLI options

```
--facility {esnet-east,esnet-west,nersc,alcf}   (required)
--base-url URL              Override the default facility base URL
--username NAME             Used to derive the default job directory
--job-dir PATH              Remote directory the smoke job runs in
--queue NAME                Queue/partition name
--account NAME              Account / project / repo
--compute-resource-id ID    Skip auto-discovery for compute
--fs-resource-id ID         Skip auto-discovery for filesystem
--log-file PATH             Full untruncated output (default: facility_notebook_smoke_full_output.log)
--timeout SECONDS           Per-request and per-task timeout (default: 180)
--poll-interval SECONDS     Task polling interval (default: 5)
--reuse-token               Use a cached token if present
--auto-pick                 Auto-select first matching resource instead of prompting
```

---

## Common usage

### NERSC, fully automated (env-supplied token)

```bash
export NERSC_IRI_API_TOKEN="…"
.venv/bin/python tools/facility_notebook_smoke.py \
    --facility nersc \
    --reuse-token \
    --auto-pick
```

### ESnet East against a dev base URL

```bash
.venv/bin/python tools/facility_notebook_smoke.py \
    --facility esnet-east \
    --base-url https://iri-dev.ppg.es.net/api/v1 \
    --auto-pick
```

### ALCF, pin specific resources

```bash
.venv/bin/python tools/facility_notebook_smoke.py \
    --facility alcf \
    --compute-resource-id 55c1c993-1124-47f9-b823-514ba3849a9a \
    --fs-resource-id      <fs-uuid> \
    --reuse-token
```

### ESnet West with a custom job directory and queue

```bash
.venv/bin/python tools/facility_notebook_smoke.py \
    --facility esnet-west \
    --job-dir /data/home/jbalcas/iri-smoke \
    --queue   debug \
    --account interactive \
    --auto-pick
```

---

## What the run does

1. **Setup**: prints the resolved configuration (facility, base URL, job
   dir, queue, account, log file).
2. **Auth**: env token → cached token (with `--reuse-token`) → live flow.
   On a successful live flow, the new token is written to the per-facility
   cache file.
3. **Discovery**: lists projects, capabilities, project allocations, and
   resources. Filters resources into compute and filesystem candidates.
4. **Compute job**: submits a `bash -lc` job that prints `env`, writes a
   log file under `--job-dir`, and exits. Polls
   `/compute/status/{resource}/{job}` until terminal.
5. **Job artifacts**: lists `--job-dir`, downloads the job's log,
   `stdout_path`, and `stderr_path` (best effort — warnings only).
6. **Filesystem smoke**: full lifecycle on a per-run sandbox directory
   (`iri-fs-test-<facility>-<ts>/…`), each operation submitted as a task
   and polled until it completes. Cleanup deletes the sandbox.
7. **Summary**: a table of every API call with method, status code,
   PASS/FAIL marker, and a short detail string.

---

## Output

- **stdout** — truncated to 30 lines per JSON block; the rest is referenced
  by path. Failures are highlighted in red and listed in the final summary.
- **`--log-file`** (default `facility_notebook_smoke_full_output.log`) —
  every JSON payload, response body, and downloaded file content in full.
  Reset on each run.

The script returns exit code **0** only when the compute job reaches state
`completed` with `exit_code` `0` (or `null`). Filesystem-operation failures
are logged as warnings and do not change the exit code, but the corresponding
rows in the final summary are marked `FAIL`.

---

## Troubleshooting

- **`Missing required environment variable`** — print the variable list above
  for the facility and source a `.env` (or export them) before re-running.
- **`No access_token received`** (ESnet) — check the `SENSE_*` credentials
  and `_VERIFY_TLS` setting; the script prints the raw response body.
- **`No IRI API token found in Globus token response`** (NERSC) — the
  paste-back code was wrong, or the resource server id / scope suffix
  doesn't match the deployment. Double-check `NERSC_GLOBUS_RS_ID` and
  `NERSC_GLOBUS_RS_SCOPE_SUFFIX` against the server config.
- **Compute job hangs** — increase `--timeout` and `--poll-interval`, or
  watch the queue directly. The script will record a `timed_out` state
  rather than killing the job.
- **Filesystem ops fail with 403** — the picked filesystem resource may not
  be writable for your user; pin one with `--fs-resource-id`.
- **`python-dotenv not installed`** — purely informational. Either
  `pip install python-dotenv` or export your variables explicitly.
