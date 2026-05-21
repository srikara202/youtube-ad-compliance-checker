import logging
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import List, Literal, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.src.api.audit_jobs import (
    create_audit_job,
    get_audit_job,
    resolve_youtube_execution_target,
    run_compliance_audit,
    start_audit_job,
)
from backend.src.api.billing import (
    BillingAuthError,
    BillingConfigurationError,
    BillingError,
    CreditCharge,
    InsufficientCreditsError,
    InviteCodeError,
    consume_audit_credits,
    create_billing_token,
    create_stripe_checkout_session,
    credits_for_duration,
    email_from_authorization_header,
    get_billing_store,
    get_paywall_settings,
    grant_checkout_credits,
    max_audit_credits,
    normalize_email,
    normalize_invite_code,
    refund_audit_credits,
    retrieve_stripe_checkout_session,
    verify_stripe_webhook_event,
)
from backend.src.api.telemetry import setup_telemetry
from backend.src.services.video_indexer import (
    build_uploaded_file_preview,
    extract_media_url_metadata,
    extract_youtube_metadata,
)

# load environment variables
load_dotenv(override=True)

# initialize the telemetry
setup_telemetry()

# configure logging
logging.basicConfig(level=logging.INFO)

logger = logging.getLogger("api-server")
REPO_ROOT = Path(__file__).resolve().parents[3]
FRONTEND_DIST_DIR = Path(
    os.getenv("FRONTEND_DIST_DIR", str(REPO_ROOT / "frontend" / "dist"))
).expanduser()
UPLOAD_TEMP_DIR = Path(os.getenv("UPLOAD_TEMP_DIR", tempfile.gettempdir())) / "youtube-ad-compliance-checker"
ALLOWED_UPLOAD_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".m4v",
    ".webm",
    ".avi",
    ".mkv",
    ".mpeg",
    ".mpg",
}


def get_frontend_origins() -> list[str]:
    configured_origins = os.getenv("FRONTEND_ORIGINS", "")
    if configured_origins.strip():
        return [origin.strip() for origin in configured_origins.split(",") if origin.strip()]
    return ["http://localhost:5173", "http://127.0.0.1:5173"]


# create the fastapi application
app = FastAPI(
    title="Youtube Add Compliance Checker API",
    description="API for auditing commercial advertisement video content against the brand compliance rules.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_frontend_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AuditRequest(BaseModel):
    """
    Defines the expected structure of incoming API requests.
    """

    video_url: str


class AuditUrlRequest(BaseModel):
    source_url: Optional[str] = None
    video_url: Optional[str] = None
    source_type: Literal["youtube", "media_url"] = "youtube"

    def resolved_source_url(self) -> str:
        return (self.source_url or self.video_url or "").strip()


class BillingEmailRequest(BaseModel):
    email: str


class BillingClaimCheckoutRequest(BaseModel):
    session_id: str


class BillingRedeemRequest(BaseModel):
    email: str
    invite_code: str


class ComplianceIssue(BaseModel):
    category: str
    severity: str
    description: str


class AuditResponse(BaseModel):
    session_id: str
    video_id: str
    status: str
    final_report: str
    compliance_results: List[ComplianceIssue]


class AuditVideoPreview(BaseModel):
    video_url: str
    source_type: Literal["youtube", "media_url", "upload"]
    source_label: str
    youtube_video_id: Optional[str] = None
    title: str
    thumbnail_url: Optional[str] = None


class AuditJobResult(BaseModel):
    status: str
    compliance_results: List[ComplianceIssue]
    final_report: str


class AuditJobResponse(BaseModel):
    audit_id: str
    job_status: str
    video: AuditVideoPreview
    result: Optional[AuditJobResult] = None
    error: Optional[str] = None
    created_at: str
    updated_at: str


class PaywallConfigResponse(BaseModel):
    enabled: bool
    pack_credits: int
    pack_price_cents: int
    max_video_seconds: int
    credit_seconds: int
    invite_enabled: bool


class BillingMeResponse(BaseModel):
    email: Optional[str] = None
    credits: int = 0
    config: PaywallConfigResponse


class BillingAccessResponse(BaseModel):
    email: str
    credits: int
    access_token: str
    config: PaywallConfigResponse


class BillingCheckoutResponse(BaseModel):
    session_id: str
    checkout_url: str


def ensure_upload_temp_dir() -> Path:
    UPLOAD_TEMP_DIR.mkdir(parents=True, exist_ok=True)
    return UPLOAD_TEMP_DIR


def save_uploaded_media(file: UploadFile) -> Path:
    if not file.filename or not file.filename.strip():
        raise HTTPException(status_code=400, detail="Please choose a media file to upload.")

    extension = Path(file.filename).suffix.lower()
    if extension not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Upload an MP4, MOV, M4V, WEBM, AVI, MKV, MPEG, or MPG file.",
        )

    upload_dir = ensure_upload_temp_dir()
    with tempfile.NamedTemporaryFile(delete=False, dir=upload_dir, suffix=extension) as temp_file:
        file.file.seek(0)
        shutil.copyfileobj(file.file, temp_file)
        return Path(temp_file.name)


def paywall_config_response() -> PaywallConfigResponse:
    settings = get_paywall_settings()
    return PaywallConfigResponse(
        enabled=settings.enabled,
        pack_credits=settings.pack_credits,
        pack_price_cents=settings.pack_cents,
        max_video_seconds=settings.max_audit_video_seconds,
        credit_seconds=settings.credit_seconds,
        invite_enabled=bool(settings.invite_codes),
    )


def billing_access_response(email: str, credits: int) -> BillingAccessResponse:
    return BillingAccessResponse(
        email=email,
        credits=credits,
        access_token=create_billing_token(email),
        config=paywall_config_response(),
    )


def billing_http_exception(exc: Exception) -> HTTPException:
    if isinstance(exc, BillingAuthError):
        return HTTPException(status_code=401, detail=str(exc))
    if isinstance(exc, InsufficientCreditsError):
        return HTTPException(status_code=402, detail=str(exc))
    if isinstance(exc, InviteCodeError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, BillingConfigurationError):
        return HTTPException(status_code=503, detail=str(exc))
    return HTTPException(status_code=500, detail="Billing request failed.")


def charge_for_audit(
    authorization: str | None,
    credits: int,
    reason: str,
) -> CreditCharge | None:
    try:
        return consume_audit_credits(
            authorization=authorization,
            credits=credits,
            reason=reason,
        )
    except (BillingAuthError, BillingConfigurationError, InsufficientCreditsError) as exc:
        raise billing_http_exception(exc) from exc


def refund_if_needed(charge: CreditCharge | None, reason: str) -> None:
    try:
        refund_audit_credits(charge, reason=reason)
    except Exception:
        logger.exception("Could not refund consumed audit credits.")


def resolve_upload_credits(declared_duration_seconds: float | None) -> int:
    settings = get_paywall_settings()
    if not settings.enabled:
        return 0
    if declared_duration_seconds is None or declared_duration_seconds <= 0:
        raise HTTPException(
            status_code=400,
            detail="Could not read the video duration. Choose a valid video file and try again.",
        )
    if declared_duration_seconds > settings.max_audit_video_seconds:
        max_minutes = settings.max_audit_video_seconds // settings.credit_seconds
        raise HTTPException(
            status_code=400,
            detail=f"Portfolio demo audits are limited to {max_minutes} minutes per video.",
        )
    return credits_for_duration(declared_duration_seconds, settings)


@app.get("/billing/me", response_model=BillingMeResponse)
async def get_billing_me(authorization: Optional[str] = Header(default=None)):
    settings = get_paywall_settings()
    config = paywall_config_response()
    if not settings.enabled:
        return BillingMeResponse(email=None, credits=0, config=config)

    if not authorization:
        return BillingMeResponse(email=None, credits=0, config=config)

    try:
        email = email_from_authorization_header(authorization, settings)
        account = get_billing_store().get_account(email)
        return BillingMeResponse(email=email, credits=account["credits"], config=config)
    except BillingAuthError:
        return BillingMeResponse(email=None, credits=0, config=config)
    except BillingConfigurationError as exc:
        raise billing_http_exception(exc) from exc


@app.post("/billing/checkout", response_model=BillingCheckoutResponse)
async def create_billing_checkout(request: BillingEmailRequest):
    try:
        email = normalize_email(request.email)
        checkout_session = create_stripe_checkout_session(email)
    except (ValueError, BillingError) as exc:
        raise billing_http_exception(exc) if isinstance(exc, BillingError) else HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return BillingCheckoutResponse(
        session_id=checkout_session["id"],
        checkout_url=checkout_session["url"],
    )


@app.post("/billing/claim-checkout", response_model=BillingAccessResponse)
async def claim_billing_checkout(request: BillingClaimCheckoutRequest):
    try:
        checkout_session = retrieve_stripe_checkout_session(request.session_id)
        account = grant_checkout_credits(checkout_session)
        email = account["email"]
    except (BillingAuthError, BillingConfigurationError) as exc:
        raise billing_http_exception(exc) from exc

    return billing_access_response(email, account["credits"])


@app.post("/billing/redeem", response_model=BillingAccessResponse)
async def redeem_billing_invite(request: BillingRedeemRequest):
    try:
        settings = get_paywall_settings()
        if not settings.enabled:
            raise BillingConfigurationError("The paywall is not enabled.")
        email = normalize_email(request.email)
        code = normalize_invite_code(request.invite_code)
        invite_config = settings.invite_codes.get(code)
        if invite_config is None:
            raise InviteCodeError("That invite code is not valid.")
        account = get_billing_store().redeem_invite(email, code, invite_config)
    except (ValueError, BillingAuthError, BillingConfigurationError, InviteCodeError) as exc:
        raise billing_http_exception(exc) if isinstance(exc, BillingError) else HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return billing_access_response(email, account["credits"])


@app.post("/billing/webhook")
async def stripe_billing_webhook(request: Request):
    payload = await request.body()
    signature = request.headers.get("Stripe-Signature")
    try:
        event = verify_stripe_webhook_event(payload, signature)
        if event.get("type") == "checkout.session.completed":
            grant_checkout_credits(event["data"]["object"])
    except (BillingAuthError, BillingConfigurationError) as exc:
        raise billing_http_exception(exc) from exc

    return {"received": True}


@app.post("/audit", response_model=AuditResponse)
async def audit_video(
    request: AuditRequest,
    authorization: Optional[str] = Header(default=None),
):
    """
    Main API endpoint that triggers the compliance audit workflow.
    """
    session_id = str(uuid.uuid4())
    video_id_short = f"vid_{session_id[:8]}"
    logger.info("Received the audit request : %s (Session : %s)", request.video_url, session_id)

    try:
        charge_for_audit(
            authorization,
            max_audit_credits(get_paywall_settings()),
            reason=f"sync:{request.video_url}",
        )
        final_state = run_compliance_audit(request.video_url, video_id_short)
        return AuditResponse(
            session_id=session_id,
            video_id=final_state.get("video_id"),
            status=final_state.get("final_status", "UNKNOWN"),
            final_report=final_state.get("final_report", "No Report Generated"),
            compliance_results=final_state.get("compliance_results", []),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Audit Failed : %s", str(exc))
        raise HTTPException(
            status_code=500,
            detail=f"Workflow Execution Failed : {str(exc)}",
        ) from exc


@app.post("/audits", response_model=AuditJobResponse, status_code=202)
async def create_video_audit(
    request: AuditUrlRequest,
    authorization: Optional[str] = Header(default=None),
):
    """
    Creates an asynchronous audit job for a YouTube or remote media URL.
    """
    source_url = request.resolved_source_url()
    if not source_url:
        raise HTTPException(status_code=400, detail="Please provide a source URL.")

    try:
        if request.source_type == "youtube":
            video = extract_youtube_metadata(source_url)
            source = {
                "source_type": "youtube",
                "source_url": video["video_url"],
                "local_file_path": None,
            }
            execution_target = resolve_youtube_execution_target()
        else:
            video = extract_media_url_metadata(source_url)
            source = {
                "source_type": "media_url",
                "source_url": video["video_url"],
                "local_file_path": None,
            }
            execution_target = "azure"
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    charge = charge_for_audit(
        authorization,
        max_audit_credits(get_paywall_settings()),
        reason=f"{request.source_type}:{video['video_url']}",
    )
    try:
        job = create_audit_job(video, source, execution_target=execution_target)
        logger.info("Created audit job %s for %s", job["audit_id"], video["video_url"])
        start_audit_job(job["audit_id"])
        return AuditJobResponse.model_validate(job)
    except Exception as exc:
        refund_if_needed(charge, "audit_job_creation_failed")
        raise HTTPException(status_code=500, detail="Could not create audit job.") from exc


@app.post("/audits/upload", response_model=AuditJobResponse, status_code=202)
async def create_uploaded_audit(
    file: UploadFile = File(...),
    declared_duration_seconds: Optional[float] = Form(default=None),
    authorization: Optional[str] = Header(default=None),
):
    """
    Creates an asynchronous audit job for a directly uploaded video file.
    """
    saved_file: Path | None = None
    charge: CreditCharge | None = None
    try:
        saved_file = save_uploaded_media(file)
        audit_credits = resolve_upload_credits(declared_duration_seconds)
        video = build_uploaded_file_preview(file.filename)
        source = {
            "source_type": "upload",
            "source_url": video["video_url"],
            "local_file_path": str(saved_file),
        }
        charge = charge_for_audit(
            authorization,
            audit_credits,
            reason=f"upload:{file.filename}:{declared_duration_seconds}",
        )
        job = create_audit_job(video, source, execution_target="azure")
        logger.info("Created upload audit job %s for %s", job["audit_id"], file.filename)
        start_audit_job(job["audit_id"])
        return AuditJobResponse.model_validate(job)
    except HTTPException:
        if saved_file and saved_file.exists():
            saved_file.unlink(missing_ok=True)
        raise
    except Exception as exc:
        refund_if_needed(charge, "upload_audit_creation_failed")
        if saved_file and saved_file.exists():
            saved_file.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="Could not create upload audit job.") from exc
    finally:
        await file.close()


@app.get("/audits/{audit_id}", response_model=AuditJobResponse)
async def get_video_audit(audit_id: str):
    """
    Returns the latest known state for an audit job.
    """
    job = get_audit_job(audit_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Audit job not found.")
    return AuditJobResponse.model_validate(job)


def resolve_frontend_asset(full_path: str) -> Path | None:
    dist_dir = FRONTEND_DIST_DIR.resolve()
    if not dist_dir.is_dir():
        return None

    index_file = dist_dir / "index.html"
    requested_path = (full_path or "").lstrip("/")
    if not requested_path:
        return index_file if index_file.is_file() else None

    candidate = (dist_dir / requested_path).resolve()
    try:
        candidate.relative_to(dist_dir)
    except ValueError:
        return None

    if candidate.is_file():
        return candidate

    if requested_path.startswith("assets/") or Path(requested_path).suffix:
        return None

    return index_file if index_file.is_file() else None


@app.get("/health")
def health_check():
    """
    Endpoint to verify API is working or not.
    """
    return {"status": "healthy", "service": "Youtube Add Compliance Checker"}


@app.get("/", include_in_schema=False)
@app.get("/{full_path:path}", include_in_schema=False)
async def serve_frontend(full_path: str = ""):
    """
    Serves the built React app when frontend assets are available.
    """
    frontend_asset = resolve_frontend_asset(full_path)
    if frontend_asset is None:
        raise HTTPException(status_code=404, detail="Frontend application is not built.")
    return FileResponse(frontend_asset)
