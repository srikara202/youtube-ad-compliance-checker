import unittest
from unittest.mock import patch

from backend.src.api import audit_jobs


class AuditJobsTests(unittest.TestCase):
    def setUp(self):
        with audit_jobs._jobs_lock:
            audit_jobs._jobs.clear()

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
