from __future__ import annotations

import copy
import hashlib
import hmac
import json
import logging
import math
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Protocol

import jwt
import requests
from azure.core import MatchConditions
from azure.core.exceptions import HttpResponseError, ResourceExistsError, ResourceNotFoundError
from azure.storage.blob import BlobClient, BlobServiceClient

logger = logging.getLogger("billing")

DEFAULT_BILLING_CONTAINER = "billing"
DEFAULT_BILLING_BLOB_NAME = "portfolio-paywall-state.json"
DEFAULT_TOKEN_TTL_SECONDS = 60 * 60 * 24 * 30
DEFAULT_STRIPE_API_BASE_URL = "https://api.stripe.com"


class BillingError(Exception):
    """Base class for paywall-specific errors."""


class BillingConfigurationError(BillingError):
    """Raised when required paywall configuration is missing."""


class BillingAuthError(BillingError):
    """Raised when a billing access token is missing or invalid."""


class InsufficientCreditsError(BillingError):
    """Raised when a user does not have enough credits for an audit."""


class InviteCodeError(BillingError):
    """Raised when an invite code cannot be redeemed."""


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_email(email: str) -> str:
    normalized = (email or "").strip().lower()
    if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
        raise ValueError("Enter a valid email address.")
    return normalized


def normalize_invite_code(code: str) -> str:
    return (code or "").strip().upper()


def parse_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class InviteCodeConfig:
    credits: int
    max_redemptions: int


@dataclass(frozen=True)
class PaywallSettings:
    enabled: bool
    stripe_secret_key: str
    stripe_webhook_secret: str
    public_site_url: str
    token_secret: str
    pack_cents: int
    pack_credits: int
    max_audit_video_seconds: int
    credit_seconds: int
    invite_codes: dict[str, InviteCodeConfig]
    stripe_api_base_url: str = DEFAULT_STRIPE_API_BASE_URL


def get_paywall_settings() -> PaywallSettings:
    enabled = parse_bool(os.getenv("PAYWALL_ENABLED"), default=False)
    pack_cents = int(os.getenv("PAYWALL_CREDIT_PACK_CENTS", "300"))
    pack_credits = int(os.getenv("PAYWALL_CREDIT_PACK_CREDITS", "3"))
    max_seconds = int(os.getenv("MAX_AUDIT_VIDEO_SECONDS", "180"))
    credit_seconds = int(os.getenv("PAYWALL_CREDIT_SECONDS", "60"))

    token_secret = os.getenv("BILLING_TOKEN_SECRET", "").strip()
    stripe_secret_key = os.getenv("STRIPE_SECRET_KEY", "").strip()
    stripe_webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
    public_site_url = os.getenv("PUBLIC_SITE_URL", "http://localhost:5173").strip().rstrip("/")
    stripe_api_base_url = os.getenv("STRIPE_API_BASE_URL", DEFAULT_STRIPE_API_BASE_URL).strip().rstrip("/")

    if enabled:
        if not token_secret:
            raise BillingConfigurationError("BILLING_TOKEN_SECRET is required when PAYWALL_ENABLED=true.")
        if not stripe_secret_key:
            raise BillingConfigurationError("STRIPE_SECRET_KEY is required when PAYWALL_ENABLED=true.")
        if pack_cents <= 0 or pack_credits <= 0:
            raise BillingConfigurationError("Credit pack price and credit count must be positive.")
        if max_seconds <= 0 or credit_seconds <= 0:
            raise BillingConfigurationError("Audit video limits must be positive.")

    return PaywallSettings(
        enabled=enabled,
        stripe_secret_key=stripe_secret_key,
        stripe_webhook_secret=stripe_webhook_secret,
        public_site_url=public_site_url,
        token_secret=token_secret,
        pack_cents=pack_cents,
        pack_credits=pack_credits,
        max_audit_video_seconds=max_seconds,
        credit_seconds=credit_seconds,
        invite_codes=parse_invite_codes(os.getenv("BILLING_INVITE_CODES_JSON", "{}")),
        stripe_api_base_url=stripe_api_base_url,
    )


def parse_invite_codes(raw_value: str) -> dict[str, InviteCodeConfig]:
    try:
        payload = json.loads(raw_value or "{}")
    except json.JSONDecodeError as exc:
        raise BillingConfigurationError("BILLING_INVITE_CODES_JSON must be valid JSON.") from exc

    if not isinstance(payload, dict):
        raise BillingConfigurationError("BILLING_INVITE_CODES_JSON must be a JSON object.")

    invite_codes: dict[str, InviteCodeConfig] = {}
    for raw_code, raw_config in payload.items():
        code = normalize_invite_code(str(raw_code))
        if not code:
            continue

        if isinstance(raw_config, int):
            credits = raw_config
            max_redemptions = 1
        elif isinstance(raw_config, dict):
            credits = int(raw_config.get("credits", 0))
            max_redemptions = int(raw_config.get("max_redemptions", raw_config.get("max_uses", 1)))
        else:
            raise BillingConfigurationError(f"Invite code '{code}' must map to an object or integer.")

        if credits <= 0 or max_redemptions <= 0:
            raise BillingConfigurationError(f"Invite code '{code}' must grant positive credits and uses.")
        invite_codes[code] = InviteCodeConfig(credits=credits, max_redemptions=max_redemptions)

    return invite_codes


def credits_for_duration(duration_seconds: float, settings: PaywallSettings) -> int:
    return max(1, math.ceil(duration_seconds / settings.credit_seconds))


def max_audit_credits(settings: PaywallSettings) -> int:
    return credits_for_duration(settings.max_audit_video_seconds, settings)


def empty_billing_state() -> dict[str, Any]:
    return {
        "accounts": {},
        "transactions": {},
        "invite_redemptions": {},
    }


def normalize_state(state: dict[str, Any] | None) -> dict[str, Any]:
    normalized = empty_billing_state()
    if isinstance(state, dict):
        normalized.update({key: value for key, value in state.items() if isinstance(value, dict)})
    return normalized


def account_snapshot(email: str, account: dict[str, Any] | None = None) -> dict[str, Any]:
    if account is None:
        return {
            "email": email,
            "credits": 0,
            "created_at": utc_timestamp(),
            "updated_at": utc_timestamp(),
        }
    return copy.deepcopy(account)


class BillingStore(Protocol):
    def get_account(self, email: str) -> dict[str, Any]:
        raise NotImplementedError

    def grant_credits(self, email: str, credits: int, *, reason: str, idempotency_key: str) -> dict[str, Any]:
        raise NotImplementedError

    def consume_credits(self, email: str, credits: int, *, reason: str, idempotency_key: str) -> dict[str, Any]:
        raise NotImplementedError

    def refund_credits(self, email: str, credits: int, *, reason: str, idempotency_key: str) -> dict[str, Any]:
        raise NotImplementedError

    def redeem_invite(
        self,
        email: str,
        code: str,
        invite_config: InviteCodeConfig,
    ) -> dict[str, Any]:
        raise NotImplementedError


class StateBillingStore:
    def _read_state(self) -> tuple[dict[str, Any], str | None]:
        raise NotImplementedError

    def _write_state(self, state: dict[str, Any], etag: str | None) -> None:
        raise NotImplementedError

    def _mutate_state(self, mutator: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
        for _ in range(5):
            state, etag = self._read_state()
            state = normalize_state(state)
            result = mutator(state)
            try:
                self._write_state(state, etag)
                return copy.deepcopy(result)
            except HttpResponseError:
                logger.info("Billing state changed during update; retrying.")
                continue
        raise RuntimeError("Could not update billing state because it kept changing.")

    @staticmethod
    def _get_or_create_account(state: dict[str, Any], email: str) -> dict[str, Any]:
        accounts = state["accounts"]
        if email not in accounts:
            now = utc_timestamp()
            accounts[email] = {
                "email": email,
                "credits": 0,
                "created_at": now,
                "updated_at": now,
            }
        return accounts[email]

    @staticmethod
    def _record_transaction(
        state: dict[str, Any],
        *,
        email: str,
        credits: int,
        transaction_type: str,
        reason: str,
        idempotency_key: str,
    ) -> None:
        state["transactions"][idempotency_key] = {
            "email": email,
            "credits": credits,
            "type": transaction_type,
            "reason": reason,
            "created_at": utc_timestamp(),
        }

    def get_account(self, email: str) -> dict[str, Any]:
        state, _ = self._read_state()
        state = normalize_state(state)
        return account_snapshot(email, state["accounts"].get(email))

    def grant_credits(self, email: str, credits: int, *, reason: str, idempotency_key: str) -> dict[str, Any]:
        def mutator(state: dict[str, Any]) -> dict[str, Any]:
            account = self._get_or_create_account(state, email)
            if idempotency_key in state["transactions"]:
                return account
            account["credits"] = int(account.get("credits", 0)) + credits
            account["updated_at"] = utc_timestamp()
            self._record_transaction(
                state,
                email=email,
                credits=credits,
                transaction_type="grant",
                reason=reason,
                idempotency_key=idempotency_key,
            )
            return account

        return self._mutate_state(mutator)

    def consume_credits(self, email: str, credits: int, *, reason: str, idempotency_key: str) -> dict[str, Any]:
        def mutator(state: dict[str, Any]) -> dict[str, Any]:
            account = self._get_or_create_account(state, email)
            if idempotency_key in state["transactions"]:
                return account
            current_credits = int(account.get("credits", 0))
            if current_credits < credits:
                raise InsufficientCreditsError("Not enough credits for this audit.")
            account["credits"] = current_credits - credits
            account["updated_at"] = utc_timestamp()
            self._record_transaction(
                state,
                email=email,
                credits=-credits,
                transaction_type="consume",
                reason=reason,
                idempotency_key=idempotency_key,
            )
            return account

        return self._mutate_state(mutator)

    def refund_credits(self, email: str, credits: int, *, reason: str, idempotency_key: str) -> dict[str, Any]:
        def mutator(state: dict[str, Any]) -> dict[str, Any]:
            account = self._get_or_create_account(state, email)
            if idempotency_key in state["transactions"]:
                return account
            account["credits"] = int(account.get("credits", 0)) + credits
            account["updated_at"] = utc_timestamp()
            self._record_transaction(
                state,
                email=email,
                credits=credits,
                transaction_type="refund",
                reason=reason,
                idempotency_key=idempotency_key,
            )
            return account

        return self._mutate_state(mutator)

    def redeem_invite(
        self,
        email: str,
        code: str,
        invite_config: InviteCodeConfig,
    ) -> dict[str, Any]:
        def mutator(state: dict[str, Any]) -> dict[str, Any]:
            account = self._get_or_create_account(state, email)
            redemptions = state["invite_redemptions"].setdefault(code, {"redeemed_by": {}})
            redeemed_by = redemptions.setdefault("redeemed_by", {})
            if email in redeemed_by:
                return account
            if len(redeemed_by) >= invite_config.max_redemptions:
                raise InviteCodeError("This invite code has reached its redemption limit.")

            account["credits"] = int(account.get("credits", 0)) + invite_config.credits
            account["updated_at"] = utc_timestamp()
            redeemed_by[email] = {
                "credits": invite_config.credits,
                "redeemed_at": utc_timestamp(),
            }
            self._record_transaction(
                state,
                email=email,
                credits=invite_config.credits,
                transaction_type="invite",
                reason=f"invite:{code}",
                idempotency_key=f"invite:{code}:{email}",
            )
            return account

        return self._mutate_state(mutator)


class InMemoryBillingStore(StateBillingStore):
    def __init__(self):
        self._state = empty_billing_state()
        self._lock = threading.Lock()

    def _mutate_state(self, mutator: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
        with self._lock:
            state = normalize_state(copy.deepcopy(self._state))
            result = mutator(state)
            self._state = copy.deepcopy(state)
            return copy.deepcopy(result)

    def _read_state(self) -> tuple[dict[str, Any], str | None]:
        with self._lock:
            return copy.deepcopy(self._state), None

    def _write_state(self, state: dict[str, Any], etag: str | None) -> None:
        with self._lock:
            self._state = copy.deepcopy(state)


class BlobBillingStore(StateBillingStore):
    def __init__(
        self,
        *,
        connection_string: str,
        container_name: str = DEFAULT_BILLING_CONTAINER,
        blob_name: str = DEFAULT_BILLING_BLOB_NAME,
    ):
        self._blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        self._container_client = self._blob_service_client.get_container_client(container_name)
        self._blob_client: BlobClient = self._container_client.get_blob_client(blob_name)
        try:
            self._container_client.create_container()
        except ResourceExistsError:
            pass

    def _read_state(self) -> tuple[dict[str, Any], str | None]:
        try:
            properties = self._blob_client.get_blob_properties()
            payload = self._blob_client.download_blob().readall().decode("utf-8")
            return json.loads(payload), properties.etag
        except ResourceNotFoundError:
            return empty_billing_state(), None

    def _write_state(self, state: dict[str, Any], etag: str | None) -> None:
        payload = json.dumps(state, separators=(",", ":"), sort_keys=True).encode("utf-8")
        kwargs: dict[str, Any] = {
            "blob_type": "BlockBlob",
            "overwrite": True,
        }
        if etag is not None:
            kwargs["etag"] = etag
            kwargs["match_condition"] = MatchConditions.IfNotModified
        self._blob_client.upload_blob(payload, **kwargs)


_billing_store: BillingStore | None = None


def set_billing_store(store: BillingStore | None) -> None:
    global _billing_store
    _billing_store = store


def reset_billing_store() -> None:
    set_billing_store(None)


def get_billing_store() -> BillingStore:
    global _billing_store
    if _billing_store is None:
        connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "").strip()
        if connection_string:
            _billing_store = BlobBillingStore(
                connection_string=connection_string,
                container_name=os.getenv("BILLING_BLOB_CONTAINER", DEFAULT_BILLING_CONTAINER).strip()
                or DEFAULT_BILLING_CONTAINER,
                blob_name=os.getenv("BILLING_BLOB_NAME", DEFAULT_BILLING_BLOB_NAME).strip()
                or DEFAULT_BILLING_BLOB_NAME,
            )
        elif parse_bool(os.getenv("PAYWALL_ENABLED"), default=False):
            raise BillingConfigurationError(
                "AZURE_STORAGE_CONNECTION_STRING is required for billing storage when PAYWALL_ENABLED=true."
            )
        else:
            _billing_store = InMemoryBillingStore()
    return _billing_store


def create_billing_token(email: str, settings: PaywallSettings | None = None) -> str:
    settings = settings or get_paywall_settings()
    if not settings.token_secret:
        raise BillingConfigurationError("BILLING_TOKEN_SECRET is required to create access tokens.")
    now = int(time.time())
    payload = {
        "sub": email,
        "typ": "billing_access",
        "iat": now,
        "exp": now + DEFAULT_TOKEN_TTL_SECONDS,
    }
    return jwt.encode(payload, settings.token_secret, algorithm="HS256")


def decode_billing_token(token: str, settings: PaywallSettings | None = None) -> str:
    settings = settings or get_paywall_settings()
    try:
        payload = jwt.decode(token, settings.token_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise BillingAuthError("Billing access token is invalid or expired.") from exc
    if payload.get("typ") != "billing_access" or not payload.get("sub"):
        raise BillingAuthError("Billing access token is invalid.")
    return normalize_email(str(payload["sub"]))


def email_from_authorization_header(
    authorization: str | None,
    settings: PaywallSettings | None = None,
) -> str:
    if not authorization:
        raise BillingAuthError("Sign in with an email, buy credits, or redeem an invite code first.")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise BillingAuthError("Billing access token is missing.")
    return decode_billing_token(token, settings)


@dataclass(frozen=True)
class CreditCharge:
    email: str
    credits: int
    transaction_id: str


def consume_audit_credits(
    *,
    authorization: str | None,
    credits: int,
    reason: str,
    settings: PaywallSettings | None = None,
) -> CreditCharge | None:
    settings = settings or get_paywall_settings()
    if not settings.enabled:
        return None
    email = email_from_authorization_header(authorization, settings)
    transaction_id = f"audit:{hashlib.sha256(f'{email}:{reason}:{time.time_ns()}'.encode()).hexdigest()}"
    get_billing_store().consume_credits(
        email,
        credits,
        reason=reason,
        idempotency_key=transaction_id,
    )
    return CreditCharge(email=email, credits=credits, transaction_id=transaction_id)


def refund_audit_credits(charge: CreditCharge | None, *, reason: str) -> None:
    if charge is None:
        return
    get_billing_store().refund_credits(
        charge.email,
        charge.credits,
        reason=reason,
        idempotency_key=f"refund:{charge.transaction_id}",
    )


def create_stripe_checkout_session(email: str, settings: PaywallSettings | None = None) -> dict[str, Any]:
    settings = settings or get_paywall_settings()
    if not settings.enabled:
        raise BillingConfigurationError("The paywall is not enabled.")

    success_url = f"{settings.public_site_url}/?checkout_session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{settings.public_site_url}/"
    response = requests.post(
        f"{settings.stripe_api_base_url}/v1/checkout/sessions",
        auth=(settings.stripe_secret_key, ""),
        data={
            "mode": "payment",
            "success_url": success_url,
            "cancel_url": cancel_url,
            "customer_email": email,
            "client_reference_id": email,
            "metadata[email]": email,
            "metadata[credits]": str(settings.pack_credits),
            "metadata[purpose]": "portfolio_audit_credits",
            "line_items[0][quantity]": "1",
            "line_items[0][price_data][currency]": "usd",
            "line_items[0][price_data][unit_amount]": str(settings.pack_cents),
            "line_items[0][price_data][product_data][name]": "Portfolio demo audit credits",
        },
        timeout=20,
    )
    if response.status_code >= 400:
        logger.error("Stripe checkout session creation failed: %s", response.text)
        raise BillingConfigurationError("Could not create a Stripe Checkout session.")
    return response.json()


def retrieve_stripe_checkout_session(
    session_id: str,
    settings: PaywallSettings | None = None,
) -> dict[str, Any]:
    settings = settings or get_paywall_settings()
    response = requests.get(
        f"{settings.stripe_api_base_url}/v1/checkout/sessions/{session_id}",
        auth=(settings.stripe_secret_key, ""),
        timeout=20,
    )
    if response.status_code >= 400:
        raise BillingAuthError("Could not verify that Stripe checkout session.")
    return response.json()


def grant_checkout_credits(session: dict[str, Any]) -> dict[str, Any]:
    if session.get("payment_status") != "paid":
        raise BillingAuthError("Stripe checkout has not completed payment yet.")

    metadata = session.get("metadata") or {}
    email = normalize_email(
        metadata.get("email")
        or session.get("customer_email")
        or session.get("client_reference_id")
        or ""
    )
    credits = int(metadata.get("credits") or get_paywall_settings().pack_credits)
    if credits <= 0:
        raise BillingConfigurationError("Stripe checkout metadata did not include a valid credit count.")
    return get_billing_store().grant_credits(
        email,
        credits,
        reason="stripe_checkout",
        idempotency_key=f"stripe_checkout:{session['id']}",
    )


def verify_stripe_webhook_event(
    payload: bytes,
    signature_header: str | None,
    settings: PaywallSettings | None = None,
) -> dict[str, Any]:
    settings = settings or get_paywall_settings()
    if not settings.stripe_webhook_secret:
        raise BillingConfigurationError("STRIPE_WEBHOOK_SECRET is required for Stripe webhooks.")
    if not signature_header:
        raise BillingAuthError("Missing Stripe-Signature header.")

    values: dict[str, list[str]] = {}
    for part in signature_header.split(","):
        key, _, value = part.partition("=")
        values.setdefault(key, []).append(value)

    timestamp_values = values.get("t", [])
    signatures = values.get("v1", [])
    if not timestamp_values or not signatures:
        raise BillingAuthError("Invalid Stripe-Signature header.")

    timestamp = int(timestamp_values[0])
    if abs(time.time() - timestamp) > 300:
        raise BillingAuthError("Stripe webhook signature timestamp is too old.")

    signed_payload = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(
        settings.stripe_webhook_secret.encode("utf-8"),
        signed_payload,
        hashlib.sha256,
    ).hexdigest()
    if not any(hmac.compare_digest(expected, signature) for signature in signatures):
        raise BillingAuthError("Stripe webhook signature verification failed.")
    return json.loads(payload.decode("utf-8"))
