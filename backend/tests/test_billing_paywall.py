import hashlib
import hmac
import json
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.src.api import billing, server


PAYWALL_ENV = {
    "PAYWALL_ENABLED": "true",
    "BILLING_TOKEN_SECRET": "test-token-secret",
    "STRIPE_SECRET_KEY": "sk_test_example",
    "STRIPE_WEBHOOK_SECRET": "whsec_test",
    "PUBLIC_SITE_URL": "https://example.com",
    "BILLING_INVITE_CODES_JSON": json.dumps(
        {
            "RECRUITER-DEMO": {
                "credits": 3,
                "max_redemptions": 1,
            }
        }
    ),
}


def build_job():
    return {
        "audit_id": "audit-123",
        "job_status": "QUEUED",
        "video": {
            "video_url": "uploaded://ad.mp4",
            "source_type": "upload",
            "source_label": "ad.mp4",
            "youtube_video_id": None,
            "title": "Ad",
            "thumbnail_url": None,
        },
        "source": {
            "source_type": "upload",
            "source_url": "uploaded://ad.mp4",
            "local_file_path": "/tmp/ad.mp4",
        },
        "result": None,
        "error": None,
        "created_at": "2026-04-19T00:00:00+00:00",
        "updated_at": "2026-04-19T00:00:00+00:00",
    }


def stripe_signature(payload: bytes, secret: str = "whsec_test") -> str:
    timestamp = int(time.time())
    signed_payload = f"{timestamp}.".encode("utf-8") + payload
    signature = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={signature}"


class BillingPaywallTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(server.app)

    def setUp(self):
        billing.set_billing_store(billing.InMemoryBillingStore())

    def tearDown(self):
        billing.reset_billing_store()

    def test_upload_requires_billing_token_when_paywall_enabled(self):
        with patch.dict("os.environ", PAYWALL_ENV, clear=False), patch(
            "backend.src.api.server.save_uploaded_media",
            return_value=Path("/tmp/ad.mp4"),
        ):
            response = self.client.post(
                "/audits/upload",
                data={"declared_duration_seconds": "60"},
                files={"file": ("ad.mp4", b"video-bytes", "video/mp4")},
            )

        self.assertEqual(response.status_code, 401)
        self.assertIn("Sign in", response.json()["detail"])

    def test_upload_rejects_insufficient_credits(self):
        with patch.dict("os.environ", PAYWALL_ENV, clear=False), patch(
            "backend.src.api.server.save_uploaded_media",
            return_value=Path("/tmp/ad.mp4"),
        ):
            token = billing.create_billing_token("recruiter@example.com")
            response = self.client.post(
                "/audits/upload",
                headers={"Authorization": f"Bearer {token}"},
                data={"declared_duration_seconds": "60"},
                files={"file": ("ad.mp4", b"video-bytes", "video/mp4")},
            )

        self.assertEqual(response.status_code, 402)
        self.assertEqual(response.json()["detail"], "Not enough credits for this audit.")

    def test_invite_code_grants_credits_once_and_respects_quota(self):
        with patch.dict("os.environ", PAYWALL_ENV, clear=False):
            first_response = self.client.post(
                "/billing/redeem",
                json={"email": "recruiter@example.com", "invite_code": "RECRUITER-DEMO"},
            )
            duplicate_response = self.client.post(
                "/billing/redeem",
                json={"email": "recruiter@example.com", "invite_code": "RECRUITER-DEMO"},
            )
            second_email_response = self.client.post(
                "/billing/redeem",
                json={"email": "ceo@example.com", "invite_code": "RECRUITER-DEMO"},
            )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(first_response.json()["credits"], 3)
        self.assertEqual(duplicate_response.status_code, 200)
        self.assertEqual(duplicate_response.json()["credits"], 3)
        self.assertEqual(second_email_response.status_code, 400)
        self.assertIn("redemption limit", second_email_response.json()["detail"])

    def test_stripe_claim_checkout_grants_credits_idempotently(self):
        checkout_session = {
            "id": "cs_test_123",
            "payment_status": "paid",
            "customer_email": "recruiter@example.com",
            "metadata": {
                "email": "recruiter@example.com",
                "credits": "3",
            },
        }

        with patch.dict("os.environ", PAYWALL_ENV, clear=False), patch(
            "backend.src.api.server.retrieve_stripe_checkout_session",
            return_value=checkout_session,
        ):
            first_response = self.client.post(
                "/billing/claim-checkout",
                json={"session_id": "cs_test_123"},
            )
            second_response = self.client.post(
                "/billing/claim-checkout",
                json={"session_id": "cs_test_123"},
            )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(first_response.json()["credits"], 3)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(second_response.json()["credits"], 3)

    def test_stripe_webhook_grants_credits_idempotently(self):
        event = {
            "id": "evt_test_123",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_456",
                    "payment_status": "paid",
                    "customer_email": "recruiter@example.com",
                    "metadata": {
                        "email": "recruiter@example.com",
                        "credits": "3",
                    },
                }
            },
        }
        payload = json.dumps(event, separators=(",", ":")).encode("utf-8")

        with patch.dict("os.environ", PAYWALL_ENV, clear=False):
            first_response = self.client.post(
                "/billing/webhook",
                content=payload,
                headers={"Stripe-Signature": stripe_signature(payload)},
            )
            second_response = self.client.post(
                "/billing/webhook",
                content=payload,
                headers={"Stripe-Signature": stripe_signature(payload)},
            )
            token = billing.create_billing_token("recruiter@example.com")
            account_response = self.client.get(
                "/billing/me",
                headers={"Authorization": f"Bearer {token}"},
            )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(account_response.json()["credits"], 3)

    def test_successful_upload_consumes_duration_based_credits(self):
        store = billing.get_billing_store()
        store.grant_credits(
            "recruiter@example.com",
            3,
            reason="test",
            idempotency_key="test-grant",
        )
        created_job = build_job()

        with patch.dict("os.environ", PAYWALL_ENV, clear=False), patch(
            "backend.src.api.server.save_uploaded_media",
            return_value=Path("/tmp/ad.mp4"),
        ), patch(
            "backend.src.api.server.build_uploaded_file_preview",
            return_value=created_job["video"],
        ), patch(
            "backend.src.api.server.create_audit_job",
            return_value=created_job,
        ), patch(
            "backend.src.api.server.start_audit_job",
        ):
            token = billing.create_billing_token("recruiter@example.com")
            response = self.client.post(
                "/audits/upload",
                headers={"Authorization": f"Bearer {token}"},
                data={"declared_duration_seconds": "70"},
                files={"file": ("ad.mp4", b"video-bytes", "video/mp4")},
            )
            account_response = self.client.get(
                "/billing/me",
                headers={"Authorization": f"Bearer {token}"},
            )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(account_response.json()["credits"], 1)

    def test_upload_rejects_videos_over_limit_before_consuming_credits(self):
        store = billing.get_billing_store()
        store.grant_credits(
            "recruiter@example.com",
            3,
            reason="test",
            idempotency_key="test-grant",
        )

        with patch.dict("os.environ", PAYWALL_ENV, clear=False), patch(
            "backend.src.api.server.save_uploaded_media",
            return_value=Path("/tmp/ad.mp4"),
        ):
            token = billing.create_billing_token("recruiter@example.com")
            response = self.client.post(
                "/audits/upload",
                headers={"Authorization": f"Bearer {token}"},
                data={"declared_duration_seconds": "181"},
                files={"file": ("ad.mp4", b"video-bytes", "video/mp4")},
            )
            account_response = self.client.get(
                "/billing/me",
                headers={"Authorization": f"Bearer {token}"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(account_response.json()["credits"], 3)


if __name__ == "__main__":
    unittest.main()
