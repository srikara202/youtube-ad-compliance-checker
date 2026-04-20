"""
Polls the shared audit job store and processes queued YouTube jobs from a self-hosted machine.
"""
from __future__ import annotations

import argparse
import logging
import os
import socket
import time

from dotenv import load_dotenv

from backend.src.api.audit_jobs import (
    claim_next_audit_job,
    get_job_store_mode,
    get_shared_job_store_modes,
    reset_job_store,
    run_claimed_audit_job,
)

load_dotenv(override=True)

logger = logging.getLogger("self-hosted-worker")


def get_worker_id() -> str:
    configured = os.getenv("SELF_HOSTED_WORKER_ID", "").strip()
    return configured or socket.gethostname()


def process_next_job(worker_id: str | None = None) -> bool:
    resolved_worker_id = worker_id or get_worker_id()
    job = claim_next_audit_job(execution_target="self_hosted", worker_id=resolved_worker_id)
    if job is None:
        logger.info("No queued self-hosted YouTube jobs were found.")
        return False

    logger.info(
        "Claimed audit job %s for %s",
        job["audit_id"],
        job.get("video", {}).get("video_url"),
    )
    run_claimed_audit_job(job)
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the self-hosted YouTube audit worker.")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process at most one queued job, then exit.",
    )
    parser.add_argument(
        "--poll-seconds",
        type=int,
        default=int(os.getenv("SELF_HOSTED_WORKER_POLL_SECONDS", "10")),
        help="Seconds to sleep between polls when no job is available.",
    )
    return parser.parse_args()


def ensure_shared_job_store_mode() -> str:
    store_mode = get_job_store_mode()
    if store_mode in get_shared_job_store_modes():
        return store_mode

    storage_connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "").strip()
    if store_mode == "memory" and storage_connection_string:
        logger.warning(
            "AUDIT_JOB_STORE is not configured for shared mode. Defaulting the self-hosted worker to azure_blob because AZURE_STORAGE_CONNECTION_STRING is available."
        )
        os.environ["AUDIT_JOB_STORE"] = "azure_blob"
        os.environ.setdefault("AUDIT_JOB_BLOB_CONTAINER", "audit-jobs")
        reset_job_store()
        return get_job_store_mode()

    return store_mode


def main() -> int:
    args = parse_args()
    logging.basicConfig(level=logging.INFO)

    store_mode = ensure_shared_job_store_mode()
    if store_mode not in get_shared_job_store_modes():
        logger.error(
            "AUDIT_JOB_STORE=%s is not a shared store. Set AUDIT_JOB_STORE=azure_blob before running the self-hosted worker.",
            store_mode,
        )
        return 1

    worker_id = get_worker_id()
    logger.info("Starting self-hosted YouTube worker as '%s'", worker_id)

    if args.once:
        process_next_job(worker_id)
        return 0

    poll_seconds = max(args.poll_seconds, 1)
    while True:
        processed_job = process_next_job(worker_id)
        if not processed_job:
            time.sleep(poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
