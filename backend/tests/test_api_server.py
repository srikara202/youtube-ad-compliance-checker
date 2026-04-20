from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.src.api import server


def build_job(job_status="QUEUED", result=None, error=None):
    return {
        "audit_id": "audit-123",
        "job_status": job_status,
        "video": {
            "video_url": "https://www.youtube.com/watch?v=abc123xyz45",
            "source_type": "youtube",
            "source_label": "abc123xyz45",
            "youtube_video_id": "abc123xyz45",
            "title": "Acme Spring Promo",
            "thumbnail_url": "https://example.com/thumb.jpg",
        },
        "source": {
            "source_type": "youtube",
            "source_url": "https://www.youtube.com/watch?v=abc123xyz45",
            "local_file_path": None,
        },
        "result": result,
        "error": error,
        "created_at": "2026-04-19T00:00:00+00:00",
        "updated_at": "2026-04-19T00:00:00+00:00",
    }


class ApiServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(server.app)

    def test_create_audit_returns_preview_and_job_id(self):
        created_job = build_job()

        with patch(
            "backend.src.api.server.extract_youtube_metadata",
            return_value=created_job["video"],
        ) as metadata_mock, patch(
            "backend.src.api.server.create_audit_job",
            return_value=created_job,
        ) as create_job_mock, patch(
            "backend.src.api.server.start_audit_job"
        ) as start_job_mock:
            response = self.client.post(
                "/audits",
                json={"video_url": "https://youtu.be/abc123xyz45"},
            )

        self.assertEqual(response.status_code, 202)
        payload = response.json()
        self.assertEqual(payload["audit_id"], "audit-123")
        self.assertEqual(payload["job_status"], "QUEUED")
        self.assertEqual(payload["video"]["title"], "Acme Spring Promo")
        self.assertEqual(payload["video"]["thumbnail_url"], "https://example.com/thumb.jpg")
        metadata_mock.assert_called_once()
        create_job_mock.assert_called_once()
        start_job_mock.assert_called_once_with("audit-123")
        self.assertEqual(create_job_mock.call_args.kwargs["execution_target"], "azure")

    def test_create_audit_accepts_remote_media_urls(self):
        created_job = build_job()
        created_job["video"] = {
            "video_url": "https://storageaccount.blob.core.windows.net/videos/ad.mp4?sig=test",
            "source_type": "media_url",
            "source_label": "ad.mp4",
            "youtube_video_id": None,
            "title": "Ad",
            "thumbnail_url": None,
        }
        created_job["source"] = {
            "source_type": "media_url",
            "source_url": "https://storageaccount.blob.core.windows.net/videos/ad.mp4?sig=test",
            "local_file_path": None,
        }

        with patch(
            "backend.src.api.server.extract_media_url_metadata",
            return_value=created_job["video"],
        ) as metadata_mock, patch(
            "backend.src.api.server.create_audit_job",
            return_value=created_job,
        ) as create_job_mock, patch(
            "backend.src.api.server.start_audit_job"
        ) as start_job_mock:
            response = self.client.post(
                "/audits",
                json={
                    "source_url": "https://storageaccount.blob.core.windows.net/videos/ad.mp4?sig=test",
                    "source_type": "media_url",
                },
            )

        self.assertEqual(response.status_code, 202)
        payload = response.json()
        self.assertEqual(payload["video"]["source_type"], "media_url")
        self.assertEqual(payload["video"]["source_label"], "ad.mp4")
        metadata_mock.assert_called_once()
        create_job_mock.assert_called_once()
        start_job_mock.assert_called_once_with("audit-123")
        self.assertEqual(create_job_mock.call_args.kwargs["execution_target"], "azure")

    def test_create_audit_can_queue_youtube_for_self_hosted_worker(self):
        created_job = build_job()

        with patch.dict("os.environ", {"YOUTUBE_AUDIT_EXECUTION_TARGET": "self_hosted"}), patch(
            "backend.src.api.server.extract_youtube_metadata",
            return_value=created_job["video"],
        ), patch(
            "backend.src.api.server.create_audit_job",
            return_value=created_job,
        ) as create_job_mock, patch(
            "backend.src.api.server.start_audit_job"
        ) as start_job_mock:
            response = self.client.post(
                "/audits",
                json={"video_url": "https://youtu.be/abc123xyz45"},
            )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(create_job_mock.call_args.kwargs["execution_target"], "self_hosted")
        start_job_mock.assert_called_once_with("audit-123")

    def test_create_upload_audit_returns_preview_and_job_id(self):
        created_job = build_job()
        created_job["video"] = {
            "video_url": "uploaded://ad.mp4",
            "source_type": "upload",
            "source_label": "ad.mp4",
            "youtube_video_id": None,
            "title": "Ad",
            "thumbnail_url": None,
        }
        created_job["source"] = {
            "source_type": "upload",
            "source_url": "uploaded://ad.mp4",
            "local_file_path": "/tmp/ad.mp4",
        }

        with patch(
            "backend.src.api.server.save_uploaded_media",
            return_value=Path("/tmp/ad.mp4"),
        ) as save_mock, patch(
            "backend.src.api.server.build_uploaded_file_preview",
            return_value=created_job["video"],
        ) as preview_mock, patch(
            "backend.src.api.server.create_audit_job",
            return_value=created_job,
        ) as create_job_mock, patch(
            "backend.src.api.server.start_audit_job"
        ) as start_job_mock:
            response = self.client.post(
                "/audits/upload",
                files={"file": ("ad.mp4", b"video-bytes", "video/mp4")},
            )

        self.assertEqual(response.status_code, 202)
        payload = response.json()
        self.assertEqual(payload["video"]["source_type"], "upload")
        self.assertEqual(payload["video"]["source_label"], "ad.mp4")
        save_mock.assert_called_once()
        preview_mock.assert_called_once_with("ad.mp4")
        create_job_mock.assert_called_once()
        start_job_mock.assert_called_once_with("audit-123")
        self.assertEqual(create_job_mock.call_args.kwargs["execution_target"], "azure")

    def test_create_audit_rejects_invalid_youtube_urls(self):
        with patch(
            "backend.src.api.server.extract_youtube_metadata",
            side_effect=ValueError("Please provide a valid YouTube URL."),
        ), patch("backend.src.api.server.create_audit_job") as create_job_mock, patch(
            "backend.src.api.server.start_audit_job"
        ) as start_job_mock:
            response = self.client.post(
                "/audits",
                json={"video_url": "https://example.com/not-youtube"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Please provide a valid YouTube URL.")
        create_job_mock.assert_not_called()
        start_job_mock.assert_not_called()

    def test_get_audit_returns_completed_payload_shape(self):
        completed_job = build_job(
            job_status="COMPLETED",
            result={
                "status": "FAIL",
                "compliance_results": [
                    {
                        "category": "FTC Disclosure",
                        "severity": "CRITICAL",
                        "description": "Missing sponsorship disclosure in the spoken content.",
                    }
                ],
                "final_report": "Disclosure issue detected.",
            },
        )

        with patch(
            "backend.src.api.server.get_audit_job",
            return_value=completed_job,
        ):
            response = self.client.get("/audits/audit-123")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["job_status"], "COMPLETED")
        self.assertEqual(payload["result"]["status"], "FAIL")
        self.assertEqual(payload["result"]["compliance_results"][0]["category"], "FTC Disclosure")
        self.assertEqual(payload["result"]["final_report"], "Disclosure issue detected.")

    def test_status_endpoint_surfaces_each_job_state(self):
        queued_job = build_job(job_status="QUEUED")
        processing_job = build_job(job_status="PROCESSING")
        completed_job = build_job(
            job_status="COMPLETED",
            result={
                "status": "PASS",
                "compliance_results": [],
                "final_report": "No issues found.",
            },
        )
        failed_job = build_job(job_status="FAILED", error="Video indexing failed in Azure.")

        jobs = [queued_job, processing_job, completed_job, failed_job]
        expected_statuses = ["QUEUED", "PROCESSING", "COMPLETED", "FAILED"]

        with patch("backend.src.api.server.get_audit_job", side_effect=jobs):
            for expected_status in expected_statuses:
                response = self.client.get("/audits/audit-123")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["job_status"], expected_status)

    def test_sync_audit_endpoint_keeps_existing_contract(self):
        final_state = {
            "video_id": "vid_demo123",
            "final_status": "FAIL",
            "final_report": "Audit summary",
            "compliance_results": [
                {
                    "category": "Claim Validation",
                    "severity": "WARNING",
                    "description": "Claim needs stronger evidence.",
                }
            ],
        }

        with patch(
            "backend.src.api.server.run_compliance_audit",
            return_value=final_state,
        ) as audit_mock:
            response = self.client.post(
                "/audit",
                json={"video_url": "https://youtu.be/abc123xyz45"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("session_id", payload)
        self.assertEqual(payload["video_id"], "vid_demo123")
        self.assertEqual(payload["status"], "FAIL")
        self.assertEqual(payload["final_report"], "Audit summary")
        self.assertEqual(payload["compliance_results"][0]["severity"], "WARNING")
        audit_mock.assert_called_once()

    def test_root_serves_built_frontend_index_when_available(self):
        with TemporaryDirectory() as temp_dir:
            dist_dir = Path(temp_dir)
            (dist_dir / "index.html").write_text(
                "<html><body>Frontend shell</body></html>",
                encoding="utf-8",
            )

            with patch.object(server, "FRONTEND_DIST_DIR", dist_dir):
                response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Frontend shell", response.text)

    def test_client_side_routes_fallback_to_index(self):
        with TemporaryDirectory() as temp_dir:
            dist_dir = Path(temp_dir)
            (dist_dir / "index.html").write_text(
                "<html><body>Client route shell</body></html>",
                encoding="utf-8",
            )

            with patch.object(server, "FRONTEND_DIST_DIR", dist_dir):
                response = self.client.get("/review/session-123")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Client route shell", response.text)
