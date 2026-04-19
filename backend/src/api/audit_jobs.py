"""
Async audit job orchestration for the frontend polling flow.
"""
from __future__ import annotations

import copy
import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from backend.src.graph.workflow import app as compliance_graph

logger = logging.getLogger("audit-jobs")

_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = threading.Lock()


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_compliance_audit(video_url: str, video_id: str) -> dict[str, Any]:
    initial_inputs = {
        "video_url": video_url,
        "video_id": video_id,
        "compliance_results": [],
        "errors": [],
    }
    return compliance_graph.invoke(initial_inputs)


def create_audit_job(video: dict[str, str]) -> dict[str, Any]:
    audit_id = str(uuid.uuid4())
    timestamp = _utc_timestamp()
    record = {
        "audit_id": audit_id,
        "job_status": "QUEUED",
        "video": video,
        "result": None,
        "error": None,
        "created_at": timestamp,
        "updated_at": timestamp,
    }

    with _jobs_lock:
        _jobs[audit_id] = record

    return copy.deepcopy(record)


def get_audit_job(audit_id: str) -> dict[str, Any] | None:
    with _jobs_lock:
        record = _jobs.get(audit_id)
        if record is None:
            return None
        return copy.deepcopy(record)


def update_audit_job(audit_id: str, **changes: Any) -> dict[str, Any] | None:
    with _jobs_lock:
        record = _jobs.get(audit_id)
        if record is None:
            return None
        record.update(changes)
        record["updated_at"] = _utc_timestamp()
        return copy.deepcopy(record)


def start_audit_job(audit_id: str) -> None:
    worker = threading.Thread(target=_run_audit_job, args=(audit_id,), daemon=True)
    worker.start()


def _run_audit_job(audit_id: str) -> None:
    job = get_audit_job(audit_id)
    if job is None:
        logger.warning("Audit job %s could not be started because it was not found.", audit_id)
        return

    video = job["video"]
    video_id = f"vid_{audit_id[:8]}"

    try:
        update_audit_job(audit_id, job_status="PROCESSING")
        final_state = run_compliance_audit(video["video_url"], video_id)
        errors = final_state.get("errors") or []
        if errors:
            update_audit_job(
                audit_id,
                job_status="FAILED",
                error=errors[0],
                result=None,
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
        )
    except Exception as exc:
        logger.exception("Audit job %s failed.", audit_id)
        update_audit_job(
            audit_id,
            job_status="FAILED",
            error=str(exc),
            result=None,
        )
