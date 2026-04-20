"""
Async audit job orchestration for the frontend polling flow.
"""
from __future__ import annotations

import logging
import os
import socket
import threading
from typing import Any

from backend.src.api.job_store import AuditJobStore, build_job_store_from_env, utc_timestamp
from backend.src.graph.workflow import app as compliance_graph

logger = logging.getLogger("audit-jobs")

_job_store: AuditJobStore | None = None
_job_store_lock = threading.Lock()


def get_job_store() -> AuditJobStore:
    global _job_store
    with _job_store_lock:
        if _job_store is None:
            _job_store = build_job_store_from_env()
        return _job_store


def set_job_store(store: AuditJobStore | None) -> None:
    global _job_store
    with _job_store_lock:
        _job_store = store


def reset_job_store() -> None:
    set_job_store(None)


def get_job_store_mode() -> str:
    return get_job_store().mode


def get_shared_job_store_modes() -> set[str]:
    return {"azure_blob"}


def resolve_youtube_execution_target() -> str:
    target = os.getenv("YOUTUBE_AUDIT_EXECUTION_TARGET", "azure").strip().lower()
    if target == "self_hosted":
        return "self_hosted"
    return "azure"


def run_compliance_audit(source: dict[str, Any] | str, video_id: str) -> dict[str, Any]:
    if isinstance(source, str):
        source = {
            "source_type": "youtube",
            "source_url": source,
            "video_url": source,
            "local_file_path": None,
        }

    initial_inputs = {
        "video_url": source.get("source_url") or source.get("video_url") or "",
        "video_id": video_id,
        "source_type": source.get("source_type", "youtube"),
        "source_url": source.get("source_url"),
        "local_file_path": source.get("local_file_path"),
        "compliance_results": [],
        "errors": [],
    }
    return compliance_graph.invoke(initial_inputs)


def create_audit_job(
    video: dict[str, Any],
    source: dict[str, Any] | None = None,
    *,
    execution_target: str = "azure",
) -> dict[str, Any]:
    return get_job_store().create_job(video, source=source, execution_target=execution_target)


def get_audit_job(audit_id: str) -> dict[str, Any] | None:
    return get_job_store().get_job(audit_id)


def update_audit_job(audit_id: str, **changes: Any) -> dict[str, Any] | None:
    return get_job_store().update_job(audit_id, **changes)


def claim_next_audit_job(*, execution_target: str, worker_id: str | None = None) -> dict[str, Any] | None:
    resolved_worker_id = worker_id or os.getenv("SELF_HOSTED_WORKER_ID", "").strip() or socket.gethostname()
    return get_job_store().claim_next_job(
        execution_target=execution_target,
        worker_id=resolved_worker_id,
    )


def start_audit_job(audit_id: str) -> None:
    job = get_audit_job(audit_id)
    if job is None:
        logger.warning("Audit job %s could not be started because it was not found.", audit_id)
        return

    if job.get("execution_target") != "azure":
        logger.info(
            "Audit job %s is queued for self-hosted processing and will not start on Azure.",
            audit_id,
        )
        return

    worker = threading.Thread(target=_run_audit_job, args=(audit_id,), daemon=True)
    worker.start()


def run_claimed_audit_job(job: dict[str, Any]) -> None:
    _execute_audit_job(job["audit_id"], claimed_job=job, mark_processing=False)


def _run_audit_job(audit_id: str) -> None:
    _execute_audit_job(audit_id, claimed_job=None, mark_processing=True)


def _execute_audit_job(
    audit_id: str,
    *,
    claimed_job: dict[str, Any] | None,
    mark_processing: bool,
) -> None:
    job = claimed_job or get_audit_job(audit_id)
    if job is None:
        logger.warning("Audit job %s could not be started because it was not found.", audit_id)
        return

    source = job.get("source") or {
        "source_type": job["video"].get("source_type", "youtube"),
        "source_url": job["video"].get("video_url"),
        "local_file_path": None,
    }
    video_id = f"vid_{audit_id[:8]}"

    try:
        if mark_processing:
            update_audit_job(audit_id, job_status="PROCESSING")

        final_state = run_compliance_audit(source, video_id)
        errors = final_state.get("errors") or []
        if errors:
            update_audit_job(
                audit_id,
                job_status="FAILED",
                error=errors[0],
                result=None,
                completed_at=utc_timestamp(),
            )
            return

        result = {
            "status": final_state.get("final_status", "UNKNOWN"),
            "compliance_results": final_state.get("compliance_results", []),
            "final_report": final_state.get("final_report", "No report generated"),
        }
        update_audit_job(
            audit_id,
            job_status="COMPLETED",
            result=result,
            error=None,
            completed_at=utc_timestamp(),
        )
    except Exception as exc:
        logger.exception("Audit job %s failed.", audit_id)
        update_audit_job(
            audit_id,
            job_status="FAILED",
            error=str(exc),
            result=None,
            completed_at=utc_timestamp(),
        )
