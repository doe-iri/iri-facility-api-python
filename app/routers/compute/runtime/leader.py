#!/usr/bin/env python3
"""IRI Workflow Leader — runs inside a scheduler allocation.

Responsibilities:
  1. Write heartbeat to workers/leader-<pid>.json
  2. Resolve dependencies: move tasks New/ -> Pending/ when all wait_for are in Finished/
  3. Claim and execute coordinated tasks via atomic rename to Running/
  4. Track background subprocesses and finalise to Finished/ or Failed/
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


def _write_heartbeat(workers_dir: Path, leader_id: str, host: str):
    heartbeat = {"id": leader_id, "host": host, "ts": time.time()}
    path = workers_dir / f"{leader_id}.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(heartbeat))
    os.rename(tmp, path)


def _finished_task_ids(base: Path) -> set[str]:
    finished_dir = _task_dir(base, "Finished")
    if not finished_dir.exists():
        return set()
    return {f.stem for f in finished_dir.iterdir() if f.suffix == ".json"}


def _resolve_dependencies(base: Path, finished: set[str]):
    """Move tasks whose wait_for deps are all finished: New/ -> Pending/."""
    new_dir = _task_dir(base, "New")
    pending_dir = _task_dir(base, "Pending")
    if not new_dir.exists():
        return
    for task_file in list(new_dir.iterdir()):
        if task_file.suffix != ".json":
            continue
        try:
            task = json.loads(task_file.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        deps = task.get("wait_for", [])
        if all(d in finished for d in deps):
            try:
                os.rename(task_file, pending_dir / task_file.name)
            except OSError:
                pass  # already moved


def _claim_coordinated(base: Path) -> list[tuple[dict, Path]]:
    """Claim coordinated tasks from Pending/ via atomic rename."""
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
        if task.get("kind") != "coordinated":
            continue
        running_path = running_dir / task_file.name
        try:
            os.rename(task_file, running_path)
        except OSError:
            continue  # another process claimed it
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
    parser = argparse.ArgumentParser(description="IRI Workflow Leader")
    parser.add_argument("--work-dir", required=True, help="Shared workflow root directory")
    parser.add_argument("--res-id", required=True, help="Resource ID")
    parser.add_argument("--work-id", required=True, help="Workflow ID")
    args = parser.parse_args()

    base = Path(args.work_dir) / ".workflows" / args.res_id / args.work_id
    workers_dir = base / "workers"

    leader_id = f"leader-{os.getpid()}"
    host = socket.gethostname()
    bg_procs: dict[str, tuple[subprocess.Popen, Path]] = {}

    running = True

    def _shutdown(signum, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    while running:
        try:
            _write_heartbeat(workers_dir, leader_id, host)
            _reap_background(base, bg_procs)

            finished = _finished_task_ids(base)
            _resolve_dependencies(base, finished)

            for task, running_path in _claim_coordinated(base):
                _execute(task, running_path, bg_procs)

            # Check if all work is done (no tasks left in New/Pending/Running)
            active_states = ("New", "Pending", "Running")
            active = sum(
                1
                for s in active_states
                if _task_dir(base, s).exists()
                for f in _task_dir(base, s).iterdir()
                if f.suffix == ".json"
            )
            if active == 0 and not bg_procs:
                # Only exit if there are some finished/failed tasks (i.e. work was done)
                done = sum(
                    1
                    for s in ("Finished", "Failed")
                    if _task_dir(base, s).exists()
                    for f in _task_dir(base, s).iterdir()
                    if f.suffix == ".json"
                )
                if done > 0:
                    break  # all work complete

        except Exception as exc:
            print(f"[leader] error: {exc}", file=sys.stderr)

        time.sleep(HEARTBEAT_INTERVAL)

    # Final heartbeat
    _write_heartbeat(workers_dir, leader_id, host)


if __name__ == "__main__":
    main()
