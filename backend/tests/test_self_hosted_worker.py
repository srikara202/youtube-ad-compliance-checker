import unittest
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
