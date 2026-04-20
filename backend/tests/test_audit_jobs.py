import unittest
from unittest.mock import patch

from backend.src.api import audit_jobs
from backend.src.api.job_store import InMemoryAuditJobStore


class AuditJobsTests(unittest.TestCase):
    def setUp(self):
        self.store = InMemoryAuditJobStore()
        audit_jobs.set_job_store(self.store)

    def tearDown(self):
        audit_jobs.reset_job_store()

    def test_run_job_transitions_to_completed(self):
        job = audit_jobs.create_audit_job(
            {
                "video_url": "https://www.youtube.com/watch?v=abc123xyz45",
                "youtube_video_id": "abc123xyz45",
                "title": "Acme Spring Promo",
                "thumbnail_url": "https://example.com/thumb.jpg",
            }
        )

        with patch(
            "backend.src.api.audit_jobs.run_compliance_audit",
            return_value={
                "final_status": "PASS",
                "compliance_results": [],
                "final_report": "No violations detected.",
                "errors": [],
            },
        ), patch(
            "backend.src.api.audit_jobs.update_audit_job",
            wraps=audit_jobs.update_audit_job,
        ) as update_mock:
            audit_jobs._run_audit_job(job["audit_id"])

        statuses = [call.kwargs["job_status"] for call in update_mock.call_args_list]
        self.assertEqual(statuses, ["PROCESSING", "COMPLETED"])
        stored_job = audit_jobs.get_audit_job(job["audit_id"])
        self.assertEqual(stored_job["job_status"], "COMPLETED")
        self.assertEqual(stored_job["result"]["status"], "PASS")
        self.assertEqual(stored_job["result"]["final_report"], "No violations detected.")

    def test_run_job_transitions_to_failed_when_workflow_returns_errors(self):
        job = audit_jobs.create_audit_job(
            {
                "video_url": "https://www.youtube.com/watch?v=abc123xyz45",
                "youtube_video_id": "abc123xyz45",
                "title": "Acme Spring Promo",
                "thumbnail_url": "https://example.com/thumb.jpg",
            }
        )

        with patch(
            "backend.src.api.audit_jobs.run_compliance_audit",
            return_value={
                "final_status": "FAIL",
                "compliance_results": [],
                "final_report": "Audit failed.",
                "errors": ["Video indexing failed in Azure."],
            },
        ), patch(
            "backend.src.api.audit_jobs.update_audit_job",
            wraps=audit_jobs.update_audit_job,
        ) as update_mock:
            audit_jobs._run_audit_job(job["audit_id"])

        statuses = [call.kwargs["job_status"] for call in update_mock.call_args_list]
        self.assertEqual(statuses, ["PROCESSING", "FAILED"])
        stored_job = audit_jobs.get_audit_job(job["audit_id"])
        self.assertEqual(stored_job["job_status"], "FAILED")
        self.assertEqual(stored_job["error"], "Video indexing failed in Azure.")

    def test_start_job_skips_self_hosted_targets(self):
        job = audit_jobs.create_audit_job(
            {
                "video_url": "https://www.youtube.com/watch?v=abc123xyz45",
                "youtube_video_id": "abc123xyz45",
                "title": "Acme Spring Promo",
                "thumbnail_url": "https://example.com/thumb.jpg",
            },
            execution_target="self_hosted",
        )

        with patch("backend.src.api.audit_jobs.threading.Thread") as thread_mock:
            audit_jobs.start_audit_job(job["audit_id"])

        thread_mock.assert_not_called()
        stored_job = audit_jobs.get_audit_job(job["audit_id"])
        self.assertEqual(stored_job["job_status"], "QUEUED")

    def test_claim_next_job_marks_processing(self):
        audit_jobs.create_audit_job(
            {
                "video_url": "https://example.com/ad.mp4",
                "source_type": "media_url",
                "source_label": "ad.mp4",
                "youtube_video_id": None,
                "title": "Blob Video",
                "thumbnail_url": None,
            },
            execution_target="azure",
        )

        queued_job = audit_jobs.create_audit_job(
            {
                "video_url": "https://www.youtube.com/watch?v=abc123xyz45",
                "youtube_video_id": "abc123xyz45",
                "title": "Acme Spring Promo",
                "thumbnail_url": "https://example.com/thumb.jpg",
            },
            execution_target="self_hosted",
        )

        claimed_job = audit_jobs.claim_next_audit_job(
            execution_target="self_hosted",
            worker_id="worker-home",
        )

        self.assertIsNotNone(claimed_job)
        self.assertEqual(claimed_job["audit_id"], queued_job["audit_id"])
        self.assertEqual(claimed_job["job_status"], "PROCESSING")
        self.assertEqual(claimed_job["worker_id"], "worker-home")
