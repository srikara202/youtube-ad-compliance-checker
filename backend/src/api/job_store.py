"""
Persistent and in-memory storage backends for audit jobs.
"""
from __future__ import annotations

import copy
import json
import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Protocol

from azure.core import MatchConditions
from azure.core.exceptions import HttpResponseError, ResourceExistsError, ResourceNotFoundError
from azure.storage.blob import BlobClient, BlobServiceClient

logger = logging.getLogger("audit-job-store")

DEFAULT_JOB_CONTAINER = "audit-jobs"
DEFAULT_JOB_PREFIX = "jobs"
DEFAULT_JOB_STORE_MODE = "memory"
SHARED_JOB_STORE_MODES = {"azure_blob"}


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_job_record(
    video: dict[str, Any],
    *,
    source: dict[str, Any] | None = None,
    execution_target: str = "azure",
) -> dict[str, Any]:
    audit_id = str(uuid.uuid4())
    timestamp = utc_timestamp()
    source_record = source or {
        "source_type": video.get("source_type", "youtube"),
        "source_url": video.get("video_url"),
        "local_file_path": None,
    }
    return {
        "audit_id": audit_id,
        "job_status": "QUEUED",
        "execution_target": execution_target,
        "video": video,
        "source": source_record,
        "result": None,
        "error": None,
        "created_at": timestamp,
        "updated_at": timestamp,
        "worker_id": None,
        "processing_started_at": None,
        "completed_at": None,
    }


class AuditJobStore(Protocol):
    def create_job(
        self,
        video: dict[str, Any],
        *,
        source: dict[str, Any] | None = None,
        execution_target: str = "azure",
    ) -> dict[str, Any]:
        raise NotImplementedError

    def get_job(self, audit_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    def update_job(self, audit_id: str, **changes: Any) -> dict[str, Any] | None:
        raise NotImplementedError

    def claim_next_job(self, *, execution_target: str, worker_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    def clear(self) -> None:
        raise NotImplementedError

    @property
    def mode(self) -> str:
        raise NotImplementedError


class InMemoryAuditJobStore:
    def __init__(self):
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    @property
    def mode(self) -> str:
        return "memory"

    def create_job(
        self,
        video: dict[str, Any],
        *,
        source: dict[str, Any] | None = None,
        execution_target: str = "azure",
    ) -> dict[str, Any]:
        record = build_job_record(video, source=source, execution_target=execution_target)
        with self._lock:
            self._jobs[record["audit_id"]] = record
        return copy.deepcopy(record)

    def get_job(self, audit_id: str) -> dict[str, Any] | None:
        with self._lock:
            record = self._jobs.get(audit_id)
            if record is None:
                return None
            return copy.deepcopy(record)

    def update_job(self, audit_id: str, **changes: Any) -> dict[str, Any] | None:
        with self._lock:
            record = self._jobs.get(audit_id)
            if record is None:
                return None
            record.update(changes)
            record["updated_at"] = utc_timestamp()
            return copy.deepcopy(record)

    def claim_next_job(self, *, execution_target: str, worker_id: str) -> dict[str, Any] | None:
        with self._lock:
            jobs = sorted(self._jobs.values(), key=lambda job: job.get("created_at", ""))
            for record in jobs:
                if record.get("execution_target") != execution_target:
                    continue
                if record.get("job_status") != "QUEUED":
                    continue
                timestamp = utc_timestamp()
                record.update(
                    {
                        "job_status": "PROCESSING",
                        "worker_id": worker_id,
                        "processing_started_at": timestamp,
                        "updated_at": timestamp,
                    }
                )
                return copy.deepcopy(record)
        return None

    def clear(self) -> None:
        with self._lock:
            self._jobs.clear()


class BlobAuditJobStore:
    def __init__(
        self,
        *,
        connection_string: str,
        container_name: str = DEFAULT_JOB_CONTAINER,
        prefix: str = DEFAULT_JOB_PREFIX,
    ):
        self._blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        self._container_client = self._blob_service_client.get_container_client(container_name)
        self._prefix = prefix.strip("/ ")
        try:
            self._container_client.create_container()
        except ResourceExistsError:
            pass

    @property
    def mode(self) -> str:
        return "azure_blob"

    def _blob_name(self, audit_id: str) -> str:
        return f"{self._prefix}/{audit_id}.json"

    @staticmethod
    def _decode_job(blob_client: BlobClient) -> tuple[dict[str, Any], str]:
        properties = blob_client.get_blob_properties()
        payload = blob_client.download_blob().readall().decode("utf-8")
        return json.loads(payload), properties.etag

    @staticmethod
    def _encode_job(job: dict[str, Any]) -> bytes:
        return json.dumps(job, separators=(",", ":"), sort_keys=True).encode("utf-8")

    def _upload_job(self, blob_client: BlobClient, job: dict[str, Any], *, etag: str | None = None) -> None:
        kwargs: dict[str, Any] = {
            "blob_type": "BlockBlob",
            "overwrite": True,
        }
        if etag is not None:
            kwargs["etag"] = etag
            kwargs["match_condition"] = MatchConditions.IfNotModified
        blob_client.upload_blob(self._encode_job(job), **kwargs)

    def create_job(
        self,
        video: dict[str, Any],
        *,
        source: dict[str, Any] | None = None,
        execution_target: str = "azure",
    ) -> dict[str, Any]:
        record = build_job_record(video, source=source, execution_target=execution_target)
        blob_client = self._container_client.get_blob_client(self._blob_name(record["audit_id"]))
        self._upload_job(blob_client, record)
        return copy.deepcopy(record)

    def get_job(self, audit_id: str) -> dict[str, Any] | None:
        blob_client = self._container_client.get_blob_client(self._blob_name(audit_id))
        try:
            job, _ = self._decode_job(blob_client)
        except ResourceNotFoundError:
            return None
        return job

    def update_job(self, audit_id: str, **changes: Any) -> dict[str, Any] | None:
        blob_client = self._container_client.get_blob_client(self._blob_name(audit_id))

        for _ in range(5):
            try:
                record, etag = self._decode_job(blob_client)
            except ResourceNotFoundError:
                return None

            record.update(changes)
            record["updated_at"] = utc_timestamp()
            try:
                self._upload_job(blob_client, record, etag=etag)
                return record
            except HttpResponseError:
                continue

        raise RuntimeError(f"Could not update audit job '{audit_id}' because the record kept changing.")

    def claim_next_job(self, *, execution_target: str, worker_id: str) -> dict[str, Any] | None:
        prefix = f"{self._prefix}/"
        blobs = list(self._container_client.list_blobs(name_starts_with=prefix))
        blobs.sort(key=lambda blob: blob.creation_time or datetime.min.replace(tzinfo=timezone.utc))

        for blob in blobs:
            blob_client = self._container_client.get_blob_client(blob.name)
            try:
                record, etag = self._decode_job(blob_client)
            except ResourceNotFoundError:
                continue

            if record.get("execution_target") != execution_target:
                continue
            if record.get("job_status") != "QUEUED":
                continue

            timestamp = utc_timestamp()
            record.update(
                {
                    "job_status": "PROCESSING",
                    "worker_id": worker_id,
                    "processing_started_at": timestamp,
                    "updated_at": timestamp,
                }
            )
            try:
                self._upload_job(blob_client, record, etag=etag)
                return record
            except HttpResponseError:
                continue

        return None

    def clear(self) -> None:
        prefix = f"{self._prefix}/"
        for blob in self._container_client.list_blobs(name_starts_with=prefix):
            self._container_client.delete_blob(blob.name, delete_snapshots="include")


def build_job_store_from_env() -> AuditJobStore:
    mode = os.getenv("AUDIT_JOB_STORE", DEFAULT_JOB_STORE_MODE).strip().lower()
    if mode == "azure_blob":
        connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "").strip()
        if not connection_string:
            raise RuntimeError(
                "AUDIT_JOB_STORE is set to 'azure_blob' but AZURE_STORAGE_CONNECTION_STRING is missing."
            )
        container_name = os.getenv("AUDIT_JOB_BLOB_CONTAINER", DEFAULT_JOB_CONTAINER).strip() or DEFAULT_JOB_CONTAINER
        prefix = os.getenv("AUDIT_JOB_BLOB_PREFIX", DEFAULT_JOB_PREFIX).strip() or DEFAULT_JOB_PREFIX
        return BlobAuditJobStore(
            connection_string=connection_string,
            container_name=container_name,
            prefix=prefix,
        )

    if mode != "memory":
        logger.warning("Unknown AUDIT_JOB_STORE mode '%s'. Falling back to memory.", mode)
    return InMemoryAuditJobStore()
