import os
import unittest
from argparse import Namespace
from unittest.mock import patch

from backend.src.api import audit_jobs
from backend.src.api.job_store import InMemoryAuditJobStore
from backend.src.worker import self_hosted_worker


class SelfHostedWorkerTests(unittest.TestCase):
    def setUp(self):
        self.store = InMemoryAuditJobStore()
        audit_jobs.set_job_store(self.store)

    def tearDown(self):
        audit_jobs.reset_job_store()

    def test_process_next_job_claims_and_completes_job(self):
        job = audit_jobs.create_audit_job(
            {
                "video_url": "https://www.youtube.com/watch?v=abc123xyz45",
                "youtube_video_id": "abc123xyz45",
                "title": "Acme Spring Promo",
                "thumbnail_url": "https://example.com/thumb.jpg",
            },
            source={
                "source_type": "youtube",
                "source_url": "https://www.youtube.com/watch?v=abc123xyz45",
                "local_file_path": None,
            },
            execution_target="self_hosted",
        )

        with patch(
            "backend.src.api.audit_jobs.run_compliance_audit",
            return_value={
                "final_status": "PASS",
                "compliance_results": [],
                "final_report": "No violations detected.",
                "errors": [],
            },
        ):
            processed = self_hosted_worker.process_next_job(worker_id="worker-home")

        self.assertTrue(processed)
        stored_job = audit_jobs.get_audit_job(job["audit_id"])
        self.assertEqual(stored_job["job_status"], "COMPLETED")
        self.assertEqual(stored_job["worker_id"], "worker-home")

    def test_process_next_job_returns_false_when_queue_is_empty(self):
        processed = self_hosted_worker.process_next_job(worker_id="worker-home")
        self.assertFalse(processed)

    def test_main_defaults_to_blob_store_when_storage_connection_exists(self):
        with patch.dict(
            "os.environ",
            {
                "AZURE_STORAGE_CONNECTION_STRING": "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test;EndpointSuffix=core.windows.net"
            },
            clear=False,
        ):
            os.environ.pop("AUDIT_JOB_STORE", None)
            os.environ.pop("AUDIT_JOB_BLOB_CONTAINER", None)
            with patch(
                "backend.src.worker.self_hosted_worker.parse_args",
                return_value=Namespace(once=True, poll_seconds=10),
            ), patch(
                "backend.src.worker.self_hosted_worker.get_job_store_mode",
                side_effect=["memory", "azure_blob"],
            ), patch(
                "backend.src.worker.self_hosted_worker.reset_job_store"
            ) as reset_mock, patch(
                "backend.src.worker.self_hosted_worker.process_next_job",
                return_value=False,
            ):
                exit_code = self_hosted_worker.main()
                self.assertEqual(os.environ["AUDIT_JOB_STORE"], "azure_blob")
                self.assertEqual(os.environ["AUDIT_JOB_BLOB_CONTAINER"], "audit-jobs")

        self.assertEqual(exit_code, 0)
        reset_mock.assert_called_once()
