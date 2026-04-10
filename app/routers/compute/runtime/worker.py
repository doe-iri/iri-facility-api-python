#!/usr/bin/env python3
"""IRI Workflow Worker — runs inside a scheduler allocation.

Responsibilities:
  1. Write heartbeat to workers/worker-<id>.json
  2. Claim local / per_node tasks from Pending/ via atomic rename to Running/
  3. Execute tasks (foreground blocks, background tracked)
  4. Move completed tasks to Finished/ or Failed/
"""
import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

HEARTBEAT_INTERVAL = 2  # seconds between loop iterations


def _task_dir(base: Path, state: str) -> Path:
    return base / "tasks" / state


def _write_heartbeat(workers_dir: Path, worker_id: str, host: str):
    heartbeat = {"id": worker_id, "host": host, "ts": time.time()}
    path = workers_dir / f"{worker_id}.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(heartbeat))
    os.rename(tmp, path)


def _claim_tasks(base: Path, claimed_per_node: set) -> list[tuple[dict, Path]]:
    """Claim local and per_node tasks from Pending/ via atomic rename."""
    pending_dir = _task_dir(base, "Pending")
    running_dir = _task_dir(base, "Running")
    claimed = []
    if not pending_dir.exists():
        return claimed
    for task_file in list(pending_dir.iterdir()):
        if task_file.suffix != ".json":
            continue
        try:
            task = json.loads(task_file.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        kind = task.get("kind", "local")
        task_id = task["task_id"]

        if kind == "coordinated":
            continue  # leader handles these
        if kind == "per_node" and task_id in claimed_per_node:
            continue  # already running one instance on this node

        running_path = running_dir / task_file.name
        try:
            os.rename(task_file, running_path)
        except OSError:
            continue  # another worker claimed it

        if kind == "per_node":
            claimed_per_node.add(task_id)

        claimed.append((task, running_path))
    return claimed


def _execute(task: dict, running_path: Path, bg_procs: dict):
    """Execute a task; foreground blocks, background is tracked."""
    task_id = task["task_id"]
    cmd = task["command"]
    run_mode = task.get("run", "foreground")
    base = running_path.parent.parent.parent  # tasks/Running/<file> -> tasks/ -> workflow root

    proc = subprocess.Popen(cmd, shell=True)

    if run_mode == "background":
        bg_procs[task_id] = (proc, running_path)
    else:
        rc = proc.wait()
        dest = "Finished" if rc == 0 else "Failed"
        try:
            os.rename(running_path, _task_dir(base, dest) / running_path.name)
        except OSError:
            pass


def _reap_background(base: Path, bg_procs: dict):
    """Check background processes and finalise completed ones."""
    for task_id in list(bg_procs):
        proc, running_path = bg_procs[task_id]
        if proc.poll() is not None:
            rc = proc.returncode
            dest = "Finished" if rc == 0 else "Failed"
            try:
                os.rename(running_path, _task_dir(base, dest) / running_path.name)
            except OSError:
                pass
            del bg_procs[task_id]


def main():
    parser = argparse.ArgumentParser(description="IRI Workflow Worker")
    parser.add_argument("--work-dir", required=True, help="Shared workflow root directory")
    parser.add_argument("--res-id", required=True, help="Resource ID")
    parser.add_argument("--work-id", required=True, help="Workflow ID")
    parser.add_argument("--worker-id", default=None, help="Worker identifier (defaults to worker-<pid>)")
    args = parser.parse_args()

    base = Path(args.work_dir) / ".workflows" / args.res_id / args.work_id
    workers_dir = base / "workers"

    worker_id = args.worker_id or f"worker-{os.getpid()}"
    host = socket.gethostname()
    bg_procs: dict[str, tuple[subprocess.Popen, Path]] = {}
    claimed_per_node: set[str] = set()

    running = True

    def _shutdown(signum, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    while running:
        try:
            _write_heartbeat(workers_dir, worker_id, host)
            _reap_background(base, bg_procs)

            for task, running_path in _claim_tasks(base, claimed_per_node):
                _execute(task, running_path, bg_procs)

            # Check if all work is done
            active_states = ("New", "Pending", "Running")
            active = sum(
                1
                for s in active_states
                if _task_dir(base, s).exists()
                for f in _task_dir(base, s).iterdir()
                if f.suffix == ".json"
            )
            if active == 0 and not bg_procs:
                done = sum(
                    1
                    for s in ("Finished", "Failed")
                    if _task_dir(base, s).exists()
                    for f in _task_dir(base, s).iterdir()
                    if f.suffix == ".json"
                )
                if done > 0:
                    break

        except Exception as exc:
            print(f"[worker {worker_id}] error: {exc}", file=sys.stderr)

        time.sleep(HEARTBEAT_INTERVAL)

    # Final heartbeat
    _write_heartbeat(workers_dir, worker_id, host)


if __name__ == "__main__":
    main()
