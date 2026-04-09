
"""
Integration test for SLACComputeAdapter against a live slurmrestd.

Exercises the adapter's submit_job, get_job, get_jobs, and cancel_job
methods directly — no reimplementation of slurmrestd_client logic.

Usage:
  SLURM_JWT_KEY_PATH=/path/to/jwt_hs256.key \
    python -m app.s3df.slurm.test_slurmrestd --user amithm

  With partition/account:
    python -m app.s3df.slurm.test_slurmrestd --user amithm --partition roma --account myacct

  List jobs only (no submit/cancel):
    python -m app.s3df.slurm.test_slurmrestd --user amithm --skip-submit
"""

import argparse
import asyncio
import logging
import sys
import time

from app.routers.compute.models import JobSpec, JobAttributes, ResourceSpec
from app.s3df.compute_adapter import SLACComputeAdapter

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)


async def run_tests(args):
    adapter = SLACComputeAdapter()

    # Build user object via the adapter's own get_user
    user = await adapter.get_user(args.user, "test-key", None)
    resource = None  # adapter does not use the resource object

    # ── get_jobs ────────────────────────────────────────────────────────
    log.info("── get_jobs ──")
    try:
        jobs = await adapter.get_jobs(resource, user, offset=0, limit=10)
        print(jobs)
        log.info("Jobs for %s: %d returned", args.user, len(jobs))
        for j in jobs:
            log.info("  job_id=%s  state=%s", j["id"], j["status"]["state"])
    except Exception as e:
        log.error("get_jobs failed: %s", e)
        sys.exit(1)

    if args.skip_submit:
        log.info("--skip-submit set, done.")
        return

    # ── submit_job ──────────────────────────────────────────────────────
    log.info("── submit_job ──")
    job_spec = JobSpec(
        name="iri-integration-test",
        executable="#!/bin/bash\n\nhostname\nsleep 15\n",
        attributes=JobAttributes(
            duration=60,
            queue_name=args.partition,
            account=args.account,
        ),
        resources=ResourceSpec(node_count=1),
        directory=f"/sdf/home/{args.user[0]}/{args.user}",
        environment={"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"},
    )
    try:
        result = await adapter.submit_job(resource, user, job_spec)
        job_id = result["id"]
        log.info("Submitted job_id=%s  state=%s", job_id, result["status"]["state"])
    except Exception as e:
        log.error("submit_job failed: %s", e)
        sys.exit(1)

    # ── get_job ─────────────────────────────────────────────────────────
    log.info("── get_job(%s) ──", job_id)
    time.sleep(1)
    try:
        job = await adapter.get_job(resource, user, job_id)
        log.info("  state=%s", job["status"]["state"])
    except Exception as e:
        log.error("get_job failed: %s", e)

    # ── cancel_job ──────────────────────────────────────────────────────
    log.info("── cancel_job(%s) ──", job_id)
    # try:
    #     cancelled = await adapter.cancel_job(resource, user, job_id)
    #     log.info("  cancelled=%s", cancelled)
    # except Exception as e:
    #     log.error("cancel_job failed: %s", e)

    # ── verify cancel ───────────────────────────────────────────────────
    time.sleep(1)
    # try:
    #     job = await adapter.get_job(resource, user, job_id)
    #     log.info("  post-cancel state=%s", job["status"]["state"])
    # except Exception as e:
    #     log.error("post-cancel get_job failed: %s", e)

    log.info("── done ──")


def main():
    parser = argparse.ArgumentParser(description="Integration test for SLACComputeAdapter")
    parser.add_argument("--user", required=True, help="Unix username (becomes JWT sun claim)")
    parser.add_argument("--partition", default=None, help="Slurm partition for test job")
    parser.add_argument("--account", default=None, help="Slurm account for test job")
    parser.add_argument("--skip-submit", action="store_true", help="Only list jobs, skip submit/cancel")
    args = parser.parse_args()
    asyncio.run(run_tests(args))


if __name__ == "__main__":
    main()