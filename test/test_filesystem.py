#!/usr/bin/env python3
"""
IRI Filesystem API smoke test via async tasks.
"""

import sys
import time
import datetime as dt
import requests


# =========================
# CONFIG — EDIT THESE AS NEEDED
# =========================

BASE_URL = "http://localhost:8000/api/v1"
TOKEN = "12345"
RESOURCE_ID = "bcc15dde-0ab6-5d31-9f20-7336adb60968"
# =========================

HEADERS = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/json"}

POLL_INTERVAL = 2
TIMEOUT = 180


def die(msg):
    """Print error message and exit."""
    print(f"\nERROR: {msg}")
    sys.exit(1)


def submit(method, path, **kwargs):
    """Submit a task and return its ID."""
    url = f"{BASE_URL}{path}"
    r = requests.request(method, url, headers=HEADERS, timeout=TIMEOUT, **kwargs)

    if not r.ok:
        die(f"{method} {url} failed: {r.status_code} {r.text}")

    data = r.json()
    if not data.get("task_id"):
        die(f"No task_id in response: {data}")
    if not data.get("task_uri"):
        die(f"No task_uri in response: {data}")

    return data


def wait_task(task):
    """Wait for a task to complete and return its result."""
    deadline = time.time() + TIMEOUT

    while time.time() < deadline:
        r = requests.get(task["task_uri"], headers=HEADERS, timeout=TIMEOUT)

        if not r.ok:
            die(f"Task query failed: {r.status_code} {r.text}")

        t = r.json()
        status = t["status"]

        print(f"   Task {task['task_id']}: {status}")

        if status == "completed":
            return t.get("result")

        if status in ("failed", "canceled"):
            die(f"Task {task['task_id']} ended with status {status}: {t}")

        time.sleep(POLL_INTERVAL)

    die(f"Task {task['task_id']} timed out")


# ============================================================
# Sandbox setup
# ============================================================

timestamp = dt.datetime.utcnow().strftime("%Y%m%d-%H%M%S")

# NOTE/TODO: /Users/jbalcas/work/amsc/iri/iri-facility-api-python/iri_sandbox/
# While we can use absolute paths, there is a need to return relative paths from the API
# As this directory can be mounted at different locations at different facilities
base_dir = f"iri-fs-test-{timestamp}"
file_path = f"{base_dir}/hello.txt"
copy_path = f"{base_dir}/hello_copy.txt"
moved_path = f"{base_dir}/hello_moved.txt"
link_path = f"{base_dir}/hello_link.txt"
archive_path = f"{base_dir}.tar.gz"
extract_dir = f"{base_dir}_extracted"

content = f"hello world {timestamp}\n"


print("\n" + "="*40)
print("=== CREATE DIRECTORY ===")

task = submit("POST", f"/filesystem/mkdir/{RESOURCE_ID}", json={"path": base_dir, "parent": True})
wait_task(task)

print("\n" + "="*40)
print("=== UPLOAD FILE ===")

task = submit("POST", f"/filesystem/upload/{RESOURCE_ID}?path={file_path}", files={"file": ("hello.txt", content.encode())})
wait_task(task)

print("\n" + "="*40)
print("=== FILE TYPE ===")

task = submit("GET", f"/filesystem/file/{RESOURCE_ID}", params={"path": file_path})
wait_task(task)

print("\n" + "="*40)
print("=== STAT ===")

task = submit("GET", f"/filesystem/stat/{RESOURCE_ID}", params={"path": file_path})
wait_task(task)

print("\n" + "="*40)
print("=== LS ===")

task = submit("GET", f"/filesystem/ls/{RESOURCE_ID}", params={"path": base_dir})
wait_task(task)

print("\n" + "="*40)
print("=== CHMOD ===")

task = submit("PUT", f"/filesystem/chmod/{RESOURCE_ID}", json={"path": file_path, "mode": "644"})
wait_task(task)

print("\n" + "="*40)
print("=== HEAD ===")

task = submit("GET", f"/filesystem/head/{RESOURCE_ID}", params={"path": file_path, "lines": 1})
wait_task(task)

print("\n" + "="*40)
print("=== TAIL ===")

task = submit("GET", f"/filesystem/tail/{RESOURCE_ID}", params={"path": file_path, "lines": 1})
wait_task(task)

print("\n" + "="*40)
print("=== VIEW ===")

task = submit("GET", f"/filesystem/view/{RESOURCE_ID}", params={"path": file_path, "size": 4096, "offset": 0})
print(wait_task(task))

print("\n" + "="*40)
print("=== CHECKSUM ===")

task = submit("GET", f"/filesystem/checksum/{RESOURCE_ID}", params={"path": file_path})
print(wait_task(task))

print("\n" + "="*40)
print("=== COPY FILE ===")

task = submit("POST", f"/filesystem/cp/{RESOURCE_ID}", json={"sourcePath": file_path, "targetPath": copy_path})
wait_task(task)

print("\n" + "="*40)
print("=== MOVE FILE ===")

task = submit("POST", f"/filesystem/mv/{RESOURCE_ID}", json={"sourcePath": copy_path, "targetPath": moved_path})
wait_task(task)

print("\n" + "="*40)
print("=== CREATE SYMLINK ===")

task = submit("POST", f"/filesystem/symlink/{RESOURCE_ID}", json={"path": moved_path, "linkPath": link_path})
wait_task(task)

print("\n" + "="*40)
print("=== COMPRESS DIRECTORY ===")

task = submit("POST", f"/filesystem/compress/{RESOURCE_ID}", json={"sourcePath": base_dir, "targetPath": archive_path, "compression": "gzip"})
wait_task(task)

print("\n" + "="*40)
print("=== EXTRACT ARCHIVE ===")

task = submit("POST", f"/filesystem/extract/{RESOURCE_ID}", json={"sourcePath": archive_path, "targetPath": extract_dir, "compression": "gzip"})
wait_task(task)

print("\n" + "="*40)
print("=== DOWNLOAD FILE ===")

task = submit("GET", f"/filesystem/download/{RESOURCE_ID}", params={"path": moved_path})
print(wait_task(task))

print("\n" + "="*40)
print("=== CLEANUP ===")

for p in [base_dir, archive_path, extract_dir]:
    task = submit("DELETE", f"/filesystem/rm/{RESOURCE_ID}", params={"path": p})
    wait_task(task)

print("\n" + "="*40)
print("ALL FILESYSTEM TESTS COMPLETED SUCCESSFULLY")
print("="*40)
