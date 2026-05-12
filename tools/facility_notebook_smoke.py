#!/usr/bin/env python3
"""
Facility-aware IRI API smoke test derived from the notebook examples.

This script covers:
- facility-specific token acquisition for esnet-east / esnet-west / nersc / alcf
- account/capability/resource discovery
- basic compute job submission + status polling
- filesystem operations from filesystem.ipynb

It is intentionally verbose and prints request/response details to stdout.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from typing import Optional

import requests

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None


ANSI_RED = "\033[31m"
ANSI_RESET = "\033[0m"
API_CALL_DELAY_SECONDS = 2
SUMMARY_URL_MAX_LENGTH = 90
TERMINAL_OUTPUT_MAX_LINES = 30
FULL_OUTPUT_LOG_PATH: Optional[Path] = None


def set_full_output_log_path(path: Path) -> None:
    global FULL_OUTPUT_LOG_PATH
    FULL_OUTPUT_LOG_PATH = path.expanduser()
    FULL_OUTPUT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    FULL_OUTPUT_LOG_PATH.write_text("")


def append_full_output_log(title: str, content: str) -> None:
    if FULL_OUTPUT_LOG_PATH is None:
        return
    with FULL_OUTPUT_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write("\n" + "=" * 80 + "\n")
        handle.write(title + "\n")
        handle.write("=" * 80 + "\n")
        handle.write(content)
        if not content.endswith("\n"):
            handle.write("\n")


def print_limited_text(text: str, max_lines: int = TERMINAL_OUTPUT_MAX_LINES) -> None:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        print(text)
        return
    print("\n".join(lines[:max_lines]))
    print(f"... ({len(lines) - max_lines} more lines; full output in {FULL_OUTPUT_LOG_PATH})")


def banner(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def api_call_banner(title: str) -> None:
    sep = "=" * 80
    print(f"\n{ANSI_RED}{sep}")
    print(title)
    print(f"{sep}{ANSI_RESET}")


def print_json(title: str, payload: Any, *, display_payload: Optional[Any] = None) -> None:
    banner(title)
    full_rendered = json.dumps(payload, indent=2, sort_keys=True, default=str)
    display_rendered = json.dumps(
        payload if display_payload is None else display_payload,
        indent=2,
        sort_keys=True,
        default=str,
    )
    append_full_output_log(title, full_rendered)
    print_limited_text(display_rendered)


def summarize_task_payload(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload

    result = payload.get("result")
    if not isinstance(result, dict):
        return payload

    output = result.get("output")
    if not isinstance(output, str):
        return payload

    command = payload.get("command")
    command_name = command.get("command") if isinstance(command, dict) else ""
    if command_name != "download":
        return payload

    summarized = dict(payload)
    summarized_result = dict(result)
    summarized_result["output"] = f"<download output: {len(output)} characters>"
    summarized["result"] = summarized_result
    return summarized


def die(message: str) -> None:
    print(f"\nERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def truncate_text(value: Any, max_length: int) -> str:
    text = str(value)
    if len(text) <= max_length:
        return text
    if max_length <= 3:
        return "." * max_length
    return text[: max_length - 3] + "..."


def print_table(headers: list[str], rows: list[list[Any]], row_colors: Optional[list[Optional[str]]] = None) -> None:
    if not rows:
        print("(no rows)")
        return

    text_rows = [[str(cell) for cell in row] for row in rows]
    widths = [len(h) for h in headers]
    for row in text_rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    fmt = " | ".join(f"{{:<{w}}}" for w in widths)
    sep = "-+-".join("-" * w for w in widths)

    print(fmt.format(*headers))
    print(sep)
    for idx, row in enumerate(text_rows):
        line = fmt.format(*row)
        color = row_colors[idx] if row_colors and idx < len(row_colors) else None
        if color:
            print(f"{color}{line}{ANSI_RESET}")
        else:
            print(line)


def decode_jwt_part(part: str) -> dict[str, Any]:
    part += "=" * (-len(part) % 4)
    return json.loads(base64.urlsafe_b64decode(part))


def decode_jwt(token: str) -> tuple[dict[str, Any], dict[str, Any]]:
    header, payload, _signature = token.split(".")
    return decode_jwt_part(header), decode_jwt_part(payload)


def human_size(value: Any) -> str:
    try:
        size = int(value)
    except Exception:
        return str(value)

    units = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]
    idx = 0
    result = float(size)
    while result >= 1024.0 and idx < len(units) - 1:
        result /= 1024.0
        idx += 1
    if idx == 0:
        return f"{int(result)} {units[idx]}"
    return f"{result:.1f} {units[idx]}"


def fmt_epoch(value: Any) -> str:
    try:
        return dt.datetime.fromtimestamp(int(str(value)), tz=dt.UTC).strftime("%Y-%m-%d %H:%M:%SZ")
    except Exception:
        return str(value)


def extract_download_text(download_result: Any) -> tuple[Optional[str], str]:
    if not isinstance(download_result, dict):
        return None, "missing"

    output = download_result.get("output")
    if isinstance(output, str):
        return output, "plain"

    if isinstance(output, dict):
        for key in ("content_base64", "base64", "data_base64", "data", "content"):
            value = output.get(key)
            if isinstance(value, str):
                if not value:
                    return "", "plain"
                try:
                    return decode_base64_to_text(value), f"base64:{key}"
                except Exception:
                    return value, f"plain:{key}"
    return None, "missing"


def decode_base64_to_text(value: str) -> str:
    try:
        raw = base64.b64decode(value, validate=True)
    except Exception:
        raw = base64.b64decode(value)

    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="replace")


@dataclass(frozen=True)
class FacilityConfig:
    name: str
    base_url: str
    auth_mode: str
    env_prefix: str
    default_username_env: str
    default_queue: str
    default_account: str
    default_job_dir: Optional[str]
    default_compute_resource_id: Optional[str]
    token_file: str


@dataclass
class ApiCallRecord:
    number: int
    operation: str
    method: str
    url: str
    status: str
    success: bool
    detail: str


FACILITIES: dict[str, FacilityConfig] = {
    "esnet-east": FacilityConfig(
        name="esnet-east",
        base_url="https://iri-dev.ppg.es.net/api/v1",
        auth_mode="esnet_password",
        env_prefix="EAST",
        default_username_env="EAST_USERNAME",
        default_queue="debug",
        default_account="interactive",
        default_job_dir=None,
        default_compute_resource_id=None,
        token_file="~/.iri_token_east.json",
    ),
    "esnet-west": FacilityConfig(
        name="esnet-west",
        base_url="https://esnet-west.sdn-sense.net/api/v1",
        auth_mode="esnet_password",
        env_prefix="WEST",
        default_username_env="WEST_USERNAME",
        default_queue="debug",
        default_account="interactive",
        default_job_dir=None,
        default_compute_resource_id=None,
        token_file="~/.iri_token_west.json",
    ),
    "nersc": FacilityConfig(
        name="nersc",
        base_url="https://api.iri.nersc.gov/api/v1",
        auth_mode="globus_confidential",
        env_prefix="NERSC",
        default_username_env="NERSC_USERNAME",
        default_queue="debug",
        default_account="amsc013",
        default_job_dir="/global/homes/j/juztas",
        default_compute_resource_id=None,
        token_file="~/.iri_token_nersc.json",
    ),
    "alcf": FacilityConfig(
        name="alcf",
        base_url="https://api.alcf.anl.gov/api/v1",
        auth_mode="alcf_native_globus",
        env_prefix="ALCF",
        default_username_env="ALCF_USERNAME",
        default_queue="debug",
        default_account="interactive",
        default_job_dir="/home/juztas",
        default_compute_resource_id="55c1c993-1124-47f9-b823-514ba3849a9a",
        token_file="~/.iri_token_alcf.json",
    ),
}


class FacilitySmokeRunner:
    def __init__(self, args: argparse.Namespace, config: FacilityConfig) -> None:
        self.args = args
        self.config = config
        self.base_url = args.base_url or config.base_url
        self.timeout = args.timeout
        self.poll_interval = args.poll_interval
        self.token_path = Path(config.token_file).expanduser()
        self.username = args.username or self._env(config.default_username_env, "USERNAME", "USER", "LOGNAME")
        default_job_dir = self.default_job_dir(config)
        self.job_dir = args.job_dir or os.getenv(
            f"{config.env_prefix}_IRI_JOB_DIR",
            os.getenv("IRI_JOB_DIR", default_job_dir),
        )
        self.queue = args.queue or os.getenv(
            f"{config.env_prefix}_IRI_QUEUE",
            os.getenv("IRI_QUEUE", config.default_queue),
        )
        self.account = args.account or os.getenv(
            f"{config.env_prefix}_IRI_ACCOUNT",
            os.getenv("IRI_ACCOUNT", config.default_account),
        )
        self.headers: dict[str, str] = {"Accept": "application/json"}
        self.api_calls: list[ApiCallRecord] = []

    def default_job_dir(self, config: FacilityConfig) -> str:
        if config.default_job_dir:
            return config.default_job_dir
        if config.name == "alcf":
            return f"/home/{self.username}"
        return f"/data/home/{self.username}"

    def _env(self, *names: str, required: bool = False, default: Optional[str] = None) -> str:
        for name in names:
            value = os.getenv(name)
            if value:
                return value
        if required:
            die(f"Missing required environment variable. Checked: {', '.join(names)}")
        return default or ""

    def _get_env_token_override(self) -> Optional[str]:
        for name in [
            f"{self.config.env_prefix}_IRI_API_TOKEN",
            f"{self.config.env_prefix}_TOKEN",
            "IRI_API_TOKEN",
            "TOKEN",
        ]:
            value = os.getenv(name)
            if value:
                print(f"Using token from environment variable: {name}")
                return value
        return None

    def _get_cached_token(self) -> Optional[str]:
        if self.token_path.exists():
            data = json.loads(self.token_path.read_text())
            token = data.get("IRI_API_TOKEN")
            if token:
                print(f"Using cached token from {self.token_path}")
                return token

        legacy_path = Path("~/.iri_token.json").expanduser()
        if legacy_path.exists():
            data = json.loads(legacy_path.read_text())
            token = data.get("IRI_API_TOKEN")
            if token:
                print(f"Using legacy cached token from {legacy_path}")
                return token
        return None

    def save_token(self, token: str, extra: Optional[dict[str, Any]] = None) -> None:
        payload: dict[str, Any] = {
            "facility": self.config.name,
            "base_url": self.base_url,
            "IRI_API_TOKEN": token,
        }
        if extra:
            payload.update(extra)

        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        self.token_path.write_text(json.dumps(payload, indent=2))
        print(f"Saved facility token to {self.token_path}")

        legacy_path = Path("~/.iri_token.json").expanduser()
        legacy_path.write_text(json.dumps({"IRI_API_TOKEN": token}, indent=2))
        print(f"Updated legacy token cache at {legacy_path}")

    def acquire_token(self) -> str:
        token = self._get_env_token_override()
        if token:
            return token

        if self.args.reuse_token:
            token = self._get_cached_token()
            if token:
                return token
            print("No reusable cached token was found; falling back to live authentication.")

        if self.config.auth_mode == "esnet_password":
            token = self.acquire_esnet_token()
        elif self.config.auth_mode == "globus_confidential":
            token = self.acquire_nersc_globus_token()
        elif self.config.auth_mode == "alcf_native_globus":
            token = self.acquire_alcf_token()
        else:  # pragma: no cover - defensive
            die(f"Unsupported auth mode: {self.config.auth_mode}")

        self.save_token(token)
        return token

    def acquire_esnet_token(self) -> str:
        banner(f"{self.config.name.upper()} TOKEN ACQUISITION (ESNET/SENSE)")
        prefix = self.config.env_prefix
        auth_endpoint = self._env(f"{prefix}_SENSE_AUTH_ENDPOINT", "SENSE_AUTH_ENDPOINT", required=True)
        client_id = self._env(f"{prefix}_SENSE_CLIENT_ID", "SENSE_CLIENT_ID", required=True)
        secret = self._env(f"{prefix}_SENSE_SECRET", "SENSE_SECRET", required=True)
        username = self._env(f"{prefix}_SENSE_USERNAME", "SENSE_USERNAME", required=True)
        password = self._env(f"{prefix}_SENSE_PASSWORD", "SENSE_PASSWORD", required=True)
        verify_tls = self._env(f"{prefix}_SENSE_VERIFY_TLS", "SENSE_VERIFY_TLS", default="true").lower() == "true"

        data = {
            "grant_type": "password",
            "username": username,
            "password": password,
            "scope": "offline_access",
        }
        print_json("AUTH REQUEST", {"endpoint": auth_endpoint, "verify_tls": verify_tls, "username": username, "data": data})

        response = requests.post(
            auth_endpoint,
            data=data,
            verify=verify_tls,
            auth=(client_id, secret),
            timeout=self.timeout,
        )
        print(f"HTTP status: {response.status_code}")
        print("\n=== RAW AUTH RESPONSE ===")
        append_full_output_log("RAW AUTH RESPONSE", response.text)
        print_limited_text(response.text)
        response.raise_for_status()

        token_data = response.json()
        if "access_token" not in token_data:
            die("No access_token received from ESnet/SENSE auth endpoint.")

        access_token = token_data["access_token"]
        header, payload = decode_jwt(access_token)
        print_json("JWT HEADER", header)
        print_json("JWT PAYLOAD", payload)

        if "iat" in payload:
            print("Issued at :", dt.datetime.fromtimestamp(payload["iat"]))
        if "exp" in payload:
            print("Expires at:", dt.datetime.fromtimestamp(payload["exp"]))

        print("\n=== USE THIS TOKEN ===")
        print(access_token)
        return access_token

    def acquire_nersc_globus_token(self) -> str:
        banner("NERSC TOKEN ACQUISITION (GLOBUS CONFIDENTIAL APP)")
        try:
            import globus_sdk
        except ImportError as exc:  # pragma: no cover - dependency error
            die(f"globus-sdk is required for NERSC auth: {exc}")

        prefix = self.config.env_prefix
        client_id = self._env(f"{prefix}_GLOBUS_ID", "GLOBUS_ID", required=True)
        client_secret = self._env(f"{prefix}_GLOBUS_SECRET", "GLOBUS_SECRET", required=True)
        resource_server_id = self._env(
            f"{prefix}_GLOBUS_RS_ID",
            "GLOBUS_RS_ID",
            default="ed3e577d-f7f3-4639-b96e-ff5a8445d699",
        )
        scope_suffix = self._env(
            f"{prefix}_GLOBUS_RS_SCOPE_SUFFIX",
            "GLOBUS_RS_SCOPE_SUFFIX",
            default="iri_api",
        )
        resource_scope = self._env(
            f"{prefix}_GLOBUS_RS_SCOPE",
            "GLOBUS_RS_SCOPE",
            default=f"https://auth.globus.org/scopes/{resource_server_id}/{scope_suffix}",
        )
        redirect_uri = self._env(
            f"{prefix}_GLOBUS_REDIRECT_URI",
            "GLOBUS_REDIRECT_URI",
            default="http://localhost:5000/callback",
        )

        client = globus_sdk.ConfidentialAppAuthClient(client_id, client_secret)
        client.oauth2_start_flow(
            redirect_uri=redirect_uri,
            requested_scopes=[
                "openid",
                "profile",
                "email",
                "urn:globus:auth:scope:auth.globus.org:view_identities",
                resource_scope,
            ],
        )

        authorize_url = client.oauth2_get_authorize_url(query_params={"prompt": "login"})
        print("\nVisit this URL in your browser and authorize:\n")
        print(authorize_url)

        auth_code = input("\nPaste the 'code' parameter from the redirect URL: ").strip()
        token_response = client.oauth2_exchange_code_for_tokens(auth_code)

        if resource_server_id not in token_response.by_resource_server:
            die("No IRI API token found in Globus token response.")

        iri_token_data = token_response.by_resource_server[resource_server_id]
        access_token = iri_token_data["access_token"]
        expires_at = iri_token_data["expires_at_seconds"]
        expiration_time = dt.datetime.fromtimestamp(expires_at)
        hours_left = (expires_at - time.time()) / 3600

        print(f"\nIRI API token expires at: {expiration_time}")
        print(f"Token expires in {hours_left:.2f} hours")
        print("\n=== USE THIS IRI API TOKEN ===")
        print(access_token)
        print("\n=== TOKEN INTROSPECT ===")
        introspect = client.oauth2_token_introspect(access_token, include="identity_set_detail,session_info")
        print(introspect)
        return access_token

    def acquire_alcf_token(self) -> str:
        banner("ALCF TOKEN ACQUISITION (GLOBUS NATIVE APP)")
        try:
            import globus_sdk
        except ImportError as exc:  # pragma: no cover - dependency error
            die(f"globus-sdk is required for ALCF auth: {exc}")

        prefix = self.config.env_prefix
        client_id = self._env(
            f"{prefix}_GLOBUS_CLIENT_ID",
            default="8b84fc2d-49e9-49ea-b54d-b3a29a70cf31",
        )
        scope_client_id = self._env(
            f"{prefix}_GLOBUS_SCOPE_CLIENT_ID",
            default="6be511f6-a071-471f-9bc0-02a0d0836723",
        )
        scopes = [
            self._env(
                f"{prefix}_GLOBUS_SCOPE",
                default=f"https://auth.globus.org/scopes/{scope_client_id}/filesystem",
            )
        ]

        client = globus_sdk.NativeAppAuthClient(client_id)
        client.oauth2_start_flow(requested_scopes=scopes, refresh_tokens=True)

        authorize_url = client.oauth2_get_authorize_url()
        print("\nVisit this URL in your browser and authorize:\n")
        print(authorize_url)

        auth_code = input("\nPaste the authorization code: ").strip()
        token_response = client.oauth2_exchange_code_for_tokens(auth_code)

        fs_token: Optional[str] = None
        expires_at: Optional[int] = None
        for _resource_server, token_data in token_response.by_resource_server.items():
            if "filesystem" in token_data.get("scope", ""):
                fs_token = token_data["access_token"]
                expires_at = token_data["expires_at_seconds"]
                break

        if not fs_token or not expires_at:
            die("No filesystem token found in ALCF token response.")

        expiration_time = dt.datetime.fromtimestamp(expires_at)
        hours_left = (expires_at - time.time()) / 3600
        print(f"\nFilesystem token expires at: {expiration_time}")
        print(f"Token expires in {hours_left:.2f} hours")
        print("\n=== USE THIS TOKEN FOR ALCF ===")
        print(fs_token)
        return fs_token

    def _next_call_number(self) -> int:
        if self.api_calls:
            print(f"\nSleeping {API_CALL_DELAY_SECONDS} seconds before next API call...")
            time.sleep(API_CALL_DELAY_SECONDS)
        return len(self.api_calls) + 1

    def _record_api_call(
        self,
        *,
        number: int,
        operation: str,
        method: str,
        url: str,
        status: Any,
        success: bool,
        detail: str,
    ) -> None:
        self.api_calls.append(
            ApiCallRecord(
                number=number,
                operation=operation,
                method=method,
                url=url,
                status=str(status) if status is not None else "-",
                success=success,
                detail=detail,
            )
        )

    def print_api_summary(self) -> None:
        banner("API CALL SUMMARY")
        rows = [
            [
                call.number,
                "PASS" if call.success else "FAIL",
                call.status,
                call.method,
                call.operation,
                truncate_text(call.url, SUMMARY_URL_MAX_LENGTH),
                call.detail,
            ]
            for call in self.api_calls
        ]
        row_colors = [None if call.success else ANSI_RED for call in self.api_calls]
        print_table(["#", "Result", "HTTP", "Method", "Operation", "URL", "Detail"], rows, row_colors=row_colors)

    def _print_call_inputs(self, kwargs: dict[str, Any]) -> None:
        params = kwargs.get("params")
        payload = kwargs.get("json")
        files = kwargs.get("files")
        if params:
            print(f"Params: {json.dumps(params, sort_keys=True, default=str)}")
        if payload:
            print(f"JSON payload: {json.dumps(payload, indent=2, sort_keys=True, default=str)}")
        if files:
            file_names = ", ".join(f"{field}={meta[0]}" for field, meta in files.items())
            print(f"Files: {file_names}")

    def request(
        self,
        method: str,
        path: str,
        *,
        expected_json: bool = True,
        operation: Optional[str] = None,
        **kwargs: Any,
    ) -> Any:
        url = f"{self.base_url}{path}"
        call_number = self._next_call_number()
        operation_name = operation or path
        api_call_banner(f"API CALL #{call_number}: {operation_name}")
        print(f"{method} {url}")
        merged_headers = {**self.headers, **kwargs.pop("headers", {})}
        self._print_call_inputs(kwargs)

        try:
            response = requests.request(method, url, headers=merged_headers, timeout=self.timeout, **kwargs)
        except requests.RequestException as exc:
            self._record_api_call(
                number=call_number,
                operation=operation_name,
                method=method,
                url=url,
                status=None,
                success=False,
                detail=exc.__class__.__name__,
            )
            print(f"Request failed: {exc.__class__.__name__}: {exc}")
            raise

        print(f"HTTP status: {response.status_code}")

        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            payload = response.json()
            print_json("RESPONSE JSON", payload)
        else:
            payload = response.text
            print("\n=== RESPONSE TEXT ===")
            append_full_output_log("RESPONSE TEXT", payload)
            print_limited_text(payload)

        success = response.ok
        detail = "ok" if success else str(payload)[:200]
        self._record_api_call(
            number=call_number,
            operation=operation_name,
            method=method,
            url=url,
            status=response.status_code,
            success=success,
            detail=detail,
        )
        response.raise_for_status()
        if expected_json:
            return payload
        return response

    def submit_task(self, method: str, path: str, *, operation: Optional[str] = None, **kwargs: Any) -> dict[str, Any]:
        data = self.request(method, path, operation=operation, **kwargs)
        if not isinstance(data, dict):
            die(f"Task submission returned unexpected payload: {data}")
        if not data.get("task_id"):
            die(f"No task_id in response: {data}")
        if not data.get("task_uri"):
            die(f"No task_uri in response: {data}")
        return data

    def wait_task(self, task: dict[str, Any]) -> Any:
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            call_number = self._next_call_number()
            operation_name = f"TASK POLL {task['task_id']}"
            api_call_banner(f"API CALL #{call_number}: {operation_name}")
            print(f"GET {task['task_uri']}")
            try:
                response = requests.get(task["task_uri"], headers=self.headers, timeout=self.timeout)
            except requests.RequestException as exc:
                self._record_api_call(
                    number=call_number,
                    operation=operation_name,
                    method="GET",
                    url=task["task_uri"],
                    status=None,
                    success=False,
                    detail=exc.__class__.__name__,
                )
                print(f"Request failed: {exc.__class__.__name__}: {exc}")
                raise
            print(f"HTTP status: {response.status_code}")
            payload = response.json()
            print_json("TASK STATUS", payload, display_payload=summarize_task_payload(payload))
            self._record_api_call(
                number=call_number,
                operation=operation_name,
                method="GET",
                url=task["task_uri"],
                status=response.status_code,
                success=response.ok,
                detail=payload.get("status", "ok") if isinstance(payload, dict) else "ok",
            )
            response.raise_for_status()
            status = payload.get("status")
            if status == "completed":
                return payload.get("result")
            if status in {"failed", "canceled", "cancelled"}:
                die(f"Task {task['task_id']} finished with status {status}")
            time.sleep(self.poll_interval)
        die(f"Task {task['task_id']} timed out")

    def discover_resources(self) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], list[dict[str, Any]], set[str]]:
        banner("DISCOVERING PROJECTS / CAPABILITIES / ALLOCATIONS / RESOURCES")
        try:
            projects = self.request("GET", "/account/projects", operation="DISCOVER PROJECTS")
        except requests.RequestException as exc:
            print(f"\nWARNING: DISCOVER PROJECTS failed; continuing with empty project list: {exc}")
            projects = []
        try:
            capabilities = self.request("GET", "/account/capabilities", operation="DISCOVER CAPABILITIES")
        except requests.RequestException as exc:
            print(f"\nWARNING: DISCOVER CAPABILITIES failed; continuing with empty capability list: {exc}")
            capabilities = []

        if not isinstance(projects, list):
            print(f"\nWARNING: DISCOVER PROJECTS returned unexpected payload; continuing with empty project list: {projects}")
            projects = []
        if not isinstance(capabilities, list):
            print(f"\nWARNING: DISCOVER CAPABILITIES returned unexpected payload; continuing with empty capability list: {capabilities}")
            capabilities = []

        cap_by_uri = {cap["self_uri"]: cap for cap in capabilities if "self_uri" in cap}
        project_rows = [[p.get("id"), p.get("name", ""), p.get("description", "")] for p in projects]
        print("\n=== PROJECTS ===")
        print_table(["Project ID", "Name", "Description"], project_rows)

        cap_rows = [[c.get("self_uri"), c.get("name"), c.get("description", "")] for c in capabilities]
        print("\n=== CAPABILITIES ===")
        print_table(["Capability URI", "Name", "Description"], cap_rows)

        allocation_rows: list[list[Any]] = []
        project_caps: set[str] = set()
        for project in projects:
            try:
                allocs = self.request(
                    "GET",
                    f"/account/projects/{project['id']}/project_allocations",
                    operation=f"DISCOVER PROJECT ALLOCATIONS {project['id']}",
                )
            except requests.RequestException as exc:
                print(f"\nWARNING: DISCOVER PROJECT ALLOCATIONS failed for {project.get('id')}; continuing: {exc}")
                continue
            if not isinstance(allocs, list):
                print(f"\nWARNING: Project allocations returned unexpected payload for {project.get('id')}; continuing: {allocs}")
                continue
            for alloc in allocs:
                cap_uri = alloc.get("capability_uri")
                allocation_rows.append(
                    [
                        project["id"],
                        alloc.get("id"),
                        self.cap_name(cap_by_uri, cap_uri),
                    ]
                )
                if cap_uri in cap_by_uri:
                    project_caps.add(cap_uri)

        print("\n=== PROJECT ALLOCATIONS ===")
        print_table(["Project ID", "Allocation ID", "Capability"], allocation_rows)

        try:
            resources = self.request(
                "GET",
                "/status/resources",
                params={"offset": 0, "limit": 100},
                operation="DISCOVER RESOURCES",
            )
        except requests.RequestException as exc:
            print(f"\nWARNING: DISCOVER RESOURCES failed; continuing with empty resource list: {exc}")
            resources = []
        if not isinstance(resources, list):
            print(f"\nWARNING: Resource listing returned unexpected payload; continuing with empty resource list: {resources}")
            resources = []

        resource_rows = []
        for resource in resources:
            caps = resource.get("capability_uris", []) or []
            resource_rows.append(
                [
                    resource.get("id"),
                    resource.get("name", ""),
                    resource.get("resource_type", ""),
                    resource.get("description", ""),
                    ", ".join(self.cap_name(cap_by_uri, cap) for cap in caps),
                    resource.get("current_status", ""),
                ]
            )

        print("\n=== DISCOVERED RESOURCES ===")
        print_table(["Resource ID", "Name", "Type", "Description", "Capabilities", "Status"], resource_rows)
        return projects, cap_by_uri, resources, project_caps

    @staticmethod
    def cap_name(allcaps: dict[str, dict[str, Any]], uri: Optional[str]) -> str:
        if not uri:
            return ""
        cap = allcaps.get(uri)
        return cap.get("name") if cap else uri

    def filter_resources(
        self,
        resources: list[dict[str, Any]],
        cap_by_uri: dict[str, dict[str, Any]],
        project_caps: set[str],
        kind: str,
    ) -> list[dict[str, Any]]:
        filtered: list[dict[str, Any]] = []
        kind = kind.lower()
        for resource in resources:
            caps = resource.get("capability_uris", []) or []
            rtype = (resource.get("resource_type") or "").lower()
            group = (resource.get("group") or "").lower()
            name = (resource.get("name") or "").lower()
            description = (resource.get("description") or "").lower()
            capnames = " ".join((self.cap_name(cap_by_uri, cap) or "").lower() for cap in caps)
            haystack = " ".join([rtype, group, name, description, capnames])

            if kind == "compute":
                if "compute" in haystack or "job" in haystack or "slurm" in haystack:
                    filtered.append(resource)
            elif kind == "filesystem":
                if "storage" in haystack or "filesystem" in haystack or rtype == "fs":
                    filtered.append(resource)
        return filtered

    def pick_resource(
        self,
        resources: list[dict[str, Any]],
        cap_by_uri: dict[str, dict[str, Any]],
        title: str,
        explicit_id: Optional[str],
    ) -> str:
        if explicit_id:
            print(f"Using provided {title.lower()} resource id: {explicit_id}")
            return explicit_id

        rows = []
        for resource in resources:
            caps = resource.get("capability_uris", []) or []
            rows.append(
                [
                    resource.get("id"),
                    resource.get("name", ""),
                    resource.get("resource_type", ""),
                    ", ".join(self.cap_name(cap_by_uri, cap) for cap in caps),
                    resource.get("current_status", ""),
                ]
            )

        banner(title)
        print_table(["Resource ID", "Name", "Type", "Capabilities", "Status"], rows)

        if not resources:
            die(f"No candidate resources found for {title.lower()}.")
        if len(resources) == 1 or self.args.auto_pick:
            picked = resources[0]["id"]
            print(f"Auto-selected {title.lower()} resource id: {picked}")
            return picked

        picked = input(f"Enter {title.lower()} resource ID: ").strip()
        if not picked:
            die(f"No {title.lower()} resource ID provided.")
        return picked

    def submit_compute_job(self, compute_resource_id: str, payload: dict[str, Any]) -> str:
        data = self.request(
            "POST",
            f"/compute/job/{compute_resource_id}",
            json=payload,
            headers={**self.headers, "Content-Type": "application/json"},
            operation="SUBMIT COMPUTE JOB",
        )
        if not isinstance(data, dict):
            die(f"Unexpected compute response: {data}")

        job_id = data.get("id") or data.get("job_id")
        if not job_id:
            die(f"Compute submit response missing job id: {data}")
        print(f"Compute job submitted: {job_id}")
        return str(job_id)

    def poll_compute_status(self, compute_resource_id: str, job_id: str) -> dict[str, Any]:
        deadline = time.time() + self.timeout
        last: dict[str, Any] = {}
        while time.time() < deadline:
            payload = self.request(
                "GET",
                f"/compute/status/{compute_resource_id}/{job_id}",
                operation=f"POLL COMPUTE JOB {job_id}",
            )
            if not isinstance(payload, dict):
                die(f"Unexpected compute status payload: {payload}")
            last = payload
            status = payload.get("status") or {}
            state = str(status.get("state", "")).lower()
            if state in {"completed", "failed", "canceled", "cancelled", "timeout", "timed_out"}:
                return last
            time.sleep(self.poll_interval)
        print(f"\nWARNING: Compute job {job_id} timed out while polling status.")
        if last:
            timed_out = dict(last)
            timed_out_status = dict(timed_out.get("status") or {})
            timed_out_status["state"] = "timed_out"
            timed_out_status["message"] = f"Polling timed out after {self.timeout} seconds"
            timed_out["status"] = timed_out_status
            timed_out["polling_timed_out"] = True
            return timed_out
        return {
            "id": job_id,
            "polling_timed_out": True,
            "status": {
                "state": "timed_out",
                "message": f"Polling timed out after {self.timeout} seconds before any status response",
            },
        }

    def build_compute_payload(self, timestamp: str) -> tuple[dict[str, Any], str, str, str]:
        job_log_name = f"{self.config.name}_iri_test_{timestamp}.log"
        job_log_path = f"{self.job_dir.rstrip('/')}/{job_log_name}"
        stdout_path = f"{self.job_dir.rstrip('/')}/{self.config.name}_stdout_{timestamp}.log"
        stderr_path = f"{self.job_dir.rstrip('/')}/{self.config.name}_stderr_{timestamp}.log"

        bash_payload = f"""
set -euo pipefail
echo "=== IRI compute smoke test ({self.config.name}) ==="
echo "UTC now: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "Hostname: $(hostname)"
echo "User: $(id || true)"
echo
echo "=== ENV (sorted) ==="
env | sort
echo
echo "=== Writing log file: {job_log_path} ==="
{{
  echo "IRI compute smoke test log"
  echo "Facility: {self.config.name}"
  echo "UTC now: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  echo "Hostname: $(hostname)"
  echo "---- ENV ----"
  env | sort
}} > "{job_log_path}"
echo "Wrote: {job_log_path}"
"""

        if self.config.name == "alcf":
            payload = {
                "executable": "/bin/bash",
                "arguments": ["-lc", bash_payload],
                "directory": self.job_dir,
                "name": f"iri-test-job-{timestamp}",
                "stdout_path": stdout_path,
                "stderr_path": stderr_path,
                "resources": {
                    "node_count": 1,
                    "memory": 268435456,
                },
                "attributes": {
                    "duration": 600,
                    "queue_name": self.queue,
                    "account": self.account,
                    "custom_attributes": {"filesystems": "eagle"},
                },
            }
            return payload, job_log_path, stdout_path, stderr_path

        payload = {
            "executable": "bash",
            "arguments": ["-lc", bash_payload],
            "directory": self.job_dir,
            "name": f"iri-{self.config.name}-smoke-{timestamp}",
            "inherit_environment": True,
            "environment": {},
            "stdout_path": stdout_path,
            "stderr_path": stderr_path,
            "resources": {
                "node_count": 1,
                "exclusive_node_use": True,
                "memory": 268435456,
                "process_count": 1,
                "processes_per_node": 1,
                "cpu_cores_per_process": 1,
            },
            "attributes": {
                "duration": 600,
                "queue_name": self.queue,
                "account": self.account,
                "custom_attributes": {},
            },
        }
        return payload, job_log_path, stdout_path, stderr_path

    def render_ls_table(self, ls_result: Any, path_label: str) -> None:
        if not isinstance(ls_result, dict):
            print(f"Unexpected ls payload for {path_label}: {ls_result}")
            return
        items = ls_result.get("output")
        if not isinstance(items, list):
            print(f"Unexpected ls output shape for {path_label}: {ls_result}")
            return

        items_sorted = sorted(
            items,
            key=lambda item: (
                0 if (item.get("type") or "").lower() == "directory" else 1,
                (item.get("name") or "").lower(),
            ),
        )

        rows = []
        for item in items_sorted:
            rows.append(
                [
                    item.get("type", ""),
                    item.get("permissions", ""),
                    item.get("user", ""),
                    item.get("group", ""),
                    human_size(item.get("size", "")),
                    fmt_epoch(item.get("last_modified", "")),
                    item.get("name", ""),
                    item.get("link_target") or "",
                ]
            )

        print(f"\nListing for: {path_label}")
        print_table(["Type", "Perm", "UID", "GID", "Size", "Last Modified (UTC)", "Name", "Link Target"], rows)

    def run_filesystem_smoke(self, fs_resource_id: str, timestamp: str) -> None:
        banner("FILESYSTEM SMOKE TEST")
        base_dir = f"iri-fs-test-{self.config.name}-{timestamp}"
        file_path = f"{base_dir}/hello.txt"
        copy_path = f"{base_dir}/hello_copy.txt"
        moved_path = f"{base_dir}/hello_moved.txt"
        link_path = f"{base_dir}/hello_link.txt"
        archive_path = f"{base_dir}.tar.gz"
        extract_dir = f"{base_dir}_extracted"
        content = f"hello world {self.config.name} {timestamp}\n"

        operations = [
            ("CREATE DIRECTORY", "POST", f"/filesystem/mkdir/{fs_resource_id}", {"json": {"path": base_dir, "parent": True}}),
            (
                "UPLOAD FILE",
                "POST",
                f"/filesystem/upload/{fs_resource_id}?path={file_path}",
                {"files": {"file": ("hello.txt", content.encode("utf-8"))}},
            ),
            ("FILE TYPE", "GET", f"/filesystem/file/{fs_resource_id}", {"params": {"path": file_path}}),
            ("STAT", "GET", f"/filesystem/stat/{fs_resource_id}", {"params": {"path": file_path}}),
            ("LS", "GET", f"/filesystem/ls/{fs_resource_id}", {"params": {"path": base_dir}}),
            ("CHMOD", "PUT", f"/filesystem/chmod/{fs_resource_id}", {"json": {"path": file_path, "mode": "644"}}),
            ("HEAD", "GET", f"/filesystem/head/{fs_resource_id}", {"params": {"path": file_path, "lines": 1}}),
            ("TAIL", "GET", f"/filesystem/tail/{fs_resource_id}", {"params": {"path": file_path, "lines": 1}}),
            ("VIEW", "GET", f"/filesystem/view/{fs_resource_id}", {"params": {"path": file_path, "size": 4096, "offset": 0}}),
            ("CHECKSUM", "GET", f"/filesystem/checksum/{fs_resource_id}", {"params": {"path": file_path}}),
            (
                "COPY FILE",
                "POST",
                f"/filesystem/cp/{fs_resource_id}",
                {"json": {"source_path": file_path, "target_path": copy_path}},
            ),
            (
                "MOVE FILE",
                "POST",
                f"/filesystem/mv/{fs_resource_id}",
                {"json": {"source_path": copy_path, "target_path": moved_path}},
            ),
            (
                "CREATE SYMLINK",
                "POST",
                f"/filesystem/symlink/{fs_resource_id}",
                {"json": {"path": moved_path, "link_path": link_path}},
            ),
            (
                "COMPRESS DIRECTORY",
                "POST",
                f"/filesystem/compress/{fs_resource_id}",
                {"json": {"source_path": base_dir, "target_path": archive_path, "compression": "gzip"}},
            ),
            (
                "EXTRACT ARCHIVE",
                "POST",
                f"/filesystem/extract/{fs_resource_id}",
                {"json": {"source_path": archive_path, "target_path": extract_dir, "compression": "gzip"}},
            ),
            ("DOWNLOAD FILE", "GET", f"/filesystem/download/{fs_resource_id}", {"params": {"path": moved_path}}),
        ]

        for label, method, path, kwargs in operations:
            banner(label)
            try:
                task = self.submit_task(method, path, operation=label, **kwargs)
                result = self.wait_task(task)
                print_json(f"{label} RESULT", result)
                if label == "LS":
                    self.render_ls_table(result, base_dir)
                if label == "DOWNLOAD FILE":
                    text, encoding = extract_download_text(result)
                    if text is not None:
                        append_full_output_log(f"{label} FILE CONTENT {file_path}", text)
                        print("\n=== DOWNLOADED FILE CONTENT ===")
                        print(f"(encoding: {encoding}, characters: {len(text)})")
                        print_limited_text(text)
            except (Exception, SystemExit) as exc:
                print(f"\nWARNING: {label} failed; continuing to next filesystem operation: {exc}")

        banner("FILESYSTEM CLEANUP")
        for path in [base_dir, archive_path, extract_dir]:
            try:
                task = self.submit_task(
                    "DELETE",
                    f"/filesystem/rm/{fs_resource_id}",
                    operation=f"CLEANUP {path}",
                    params={"path": path},
                )
                result = self.wait_task(task)
                print_json(f"DELETE {path}", result)
            except (Exception, SystemExit) as exc:
                print(f"\nWARNING: CLEANUP {path} failed; continuing cleanup: {exc}")

    def download_and_print_file(self, fs_resource_id: str, path: str, label: str) -> None:
        banner(label)
        task = self.submit_task("GET", f"/filesystem/download/{fs_resource_id}", operation=label, params={"path": path})
        result = self.wait_task(task)
        text, encoding = extract_download_text(result)
        if text is None:
            die(f"Download result for {path} did not contain printable output: {result}")
        append_full_output_log(f"{label} FILE CONTENT {path}", text)
        print(f"\n=== {label} RESULT ===")
        print(f"path      : {path}")
        print(f"encoding  : {encoding}")
        print(f"characters: {len(text)}")
        print("\n=== FILE CONTENT ===")
        print_limited_text(text)

    def try_download_and_print_file(self, fs_resource_id: str, path: str, label: str) -> bool:
        try:
            self.download_and_print_file(fs_resource_id, path, label)
        except (Exception, SystemExit) as exc:
            print(f"\nWARNING: {label} failed for {path}: {exc}")
            return False
        return True

    def run(self) -> None:
        banner("INITIAL SETUP")
        print_json(
            "RUN CONFIGURATION",
            {
                "facility": self.config.name,
                "base_url": self.base_url,
                "username": self.username,
                "job_dir": self.job_dir,
                "queue": self.queue,
                "account": self.account,
                "timeout": self.timeout,
                "poll_interval": self.poll_interval,
                "reuse_token": self.args.reuse_token,
                "auto_pick": self.args.auto_pick,
                "full_output_log": str(FULL_OUTPUT_LOG_PATH) if FULL_OUTPUT_LOG_PATH else "",
            },
        )

        token = self.acquire_token()
        self.headers["Authorization"] = f"Bearer {token}"

        projects, cap_by_uri, resources, project_caps = self.discover_resources()
        compute_candidates = self.filter_resources(resources, cap_by_uri, project_caps, "compute")
        fs_candidates = self.filter_resources(resources, cap_by_uri, project_caps, "filesystem")

        if not compute_candidates:
            print("No compute resources matched heuristics; falling back to all discovered resources.")
            compute_candidates = resources
        if not fs_candidates:
            print("No filesystem resources matched heuristics; falling back to all discovered resources.")
            fs_candidates = resources

        compute_resource_id = self.pick_resource(
            compute_candidates,
            cap_by_uri,
            "COMPUTE RESOURCE",
            self.args.compute_resource_id or self.config.default_compute_resource_id,
        )
        fs_resource_id = self.args.fs_resource_id
        if not fs_resource_id and fs_candidates:
            fs_resource_id = self.pick_resource(fs_candidates, cap_by_uri, "FILESYSTEM RESOURCE", None)
        if not fs_resource_id:
            print("\nWARNING: No filesystem resource ID available; filesystem-dependent operations will be skipped.")

        timestamp = dt.datetime.now(dt.UTC).strftime("%Y%m%d-%H%M%S")
        payload, job_log_path, stdout_path, stderr_path = self.build_compute_payload(timestamp)
        print_json("COMPUTE PAYLOAD", payload)

        final_status: dict[str, Any] = {
            "status": {
                "state": "not_submitted",
                "message": "Compute submission was not attempted.",
            },
        }
        compute_clean = False
        compute_failure_message = "Compute job did not complete cleanly (state=not_submitted, exit_code=None)."
        try:
            job_id = self.submit_compute_job(compute_resource_id, payload)
            final_status = self.poll_compute_status(compute_resource_id, job_id)
            print_json("FINAL COMPUTE STATUS", final_status)

            state = str((final_status.get("status") or {}).get("state", "")).lower()
            exit_code = (final_status.get("status") or {}).get("exit_code")
            compute_clean = state == "completed" and exit_code in (None, 0)
            compute_failure_message = f"Compute job did not complete cleanly (state={state}, exit_code={exit_code})."
        except (Exception, SystemExit) as exc:
            compute_failure_message = f"Compute submission/status failed: {exc}"
            final_status = {
                "status": {
                    "state": "submission_or_status_failed",
                    "message": str(exc),
                },
            }
            print_json("FINAL COMPUTE STATUS", final_status)
        if not compute_clean:
            print(f"\nWARNING: {compute_failure_message}")
            print("Continuing to collect job directory listing and logs.")

        if fs_resource_id:
            banner("LIST JOB DIRECTORY")
            try:
                ls_task = self.submit_task(
                    "GET",
                    f"/filesystem/ls/{fs_resource_id}",
                    operation="LIST JOB DIRECTORY",
                    params={"path": self.job_dir},
                )
                ls_result = self.wait_task(ls_task)
                print_json("JOB DIRECTORY LS RESULT", ls_result)
                self.render_ls_table(ls_result, self.job_dir)
            except (Exception, SystemExit) as exc:
                print(f"\nWARNING: LIST JOB DIRECTORY failed for {self.job_dir}: {exc}")

            self.try_download_and_print_file(fs_resource_id, job_log_path, "DOWNLOAD COMPUTE LOG FILE")
            self.try_download_and_print_file(fs_resource_id, stdout_path, "DOWNLOAD STDOUT")
            self.try_download_and_print_file(fs_resource_id, stderr_path, "DOWNLOAD STDERR")
            self.run_filesystem_smoke(fs_resource_id, timestamp)
        else:
            print("\nWARNING: Skipping job directory listing, log downloads, and filesystem smoke because no filesystem resource ID is available.")

        if not compute_clean:
            die(compute_failure_message)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Facility-aware IRI API smoke test derived from the example notebooks.",
    )
    parser.add_argument("--facility", required=True, choices=sorted(FACILITIES))
    parser.add_argument("--base-url", help="Override the default facility base URL.")
    parser.add_argument("--username", help="Username used to derive the default job directory.")
    parser.add_argument("--job-dir", help="Remote job directory. Defaults are facility-specific.")
    parser.add_argument("--queue", help="Queue name for the smoke job.")
    parser.add_argument("--account", help="Account/project name for the smoke job.")
    parser.add_argument("--compute-resource-id", help="Use a specific compute resource ID.")
    parser.add_argument("--fs-resource-id", help="Use a specific filesystem resource ID.")
    parser.add_argument(
        "--log-file",
        default="facility_notebook_smoke_full_output.log",
        help="Local file for full untruncated JSON and downloaded output.",
    )
    parser.add_argument("--timeout", type=int, default=180, help="Per-request/task timeout in seconds.")
    parser.add_argument("--poll-interval", type=int, default=5, help="Polling interval in seconds.")
    parser.add_argument(
        "--reuse-token",
        action="store_true",
        help="Reuse a cached token when present before falling back to live authentication. Env tokens always take precedence.",
    )
    parser.add_argument(
        "--auto-pick",
        action="store_true",
        help="Automatically pick the first matching compute/filesystem resource instead of prompting.",
    )
    return parser


def main() -> int:
    if load_dotenv is not None:
        load_dotenv()
        print("Loaded environment variables from .env when available.")
    else:
        print("python-dotenv not installed; skipping .env loading.")

    args = build_parser().parse_args()
    set_full_output_log_path(Path(args.log_file))
    print(f"Full untruncated output log: {FULL_OUTPUT_LOG_PATH}")
    config = FACILITIES[args.facility]
    runner = FacilitySmokeRunner(args, config)
    exit_code = 0
    try:
        runner.run()
    except SystemExit as exc:
        exit_code = int(exc.code) if isinstance(exc.code, int) else 1
        if exit_code:
            print(f"\nRUN FAILED: {exc}")
    except Exception as exc:  # pragma: no cover - top-level CLI safety net
        exit_code = 1
        print(f"\nRUN FAILED: {exc.__class__.__name__}: {exc}")
    finally:
        runner.print_api_summary()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
