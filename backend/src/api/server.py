import logging
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import List, Literal, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.src.api.audit_jobs import (
    create_audit_job,
    get_audit_job,
    run_compliance_audit,
    start_audit_job,
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


@app.post("/audit", response_model=AuditResponse)
async def audit_video(request: AuditRequest):
    """
    Main API endpoint that triggers the compliance audit workflow.
    """
    session_id = str(uuid.uuid4())
    video_id_short = f"vid_{session_id[:8]}"
    logger.info("Received the audit request : %s (Session : %s)", request.video_url, session_id)

    try:
        final_state = run_compliance_audit(request.video_url, video_id_short)
        return AuditResponse(
            session_id=session_id,
            video_id=final_state.get("video_id"),
            status=final_state.get("final_status", "UNKNOWN"),
            final_report=final_state.get("final_report", "No Report Generated"),
            compliance_results=final_state.get("compliance_results", []),
        )
    except Exception as exc:
        logger.error("Audit Failed : %s", str(exc))
        raise HTTPException(
            status_code=500,
            detail=f"Workflow Execution Failed : {str(exc)}",
        ) from exc


@app.post("/audits", response_model=AuditJobResponse, status_code=202)
async def create_video_audit(request: AuditUrlRequest):
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
        else:
            video = extract_media_url_metadata(source_url)
            source = {
                "source_type": "media_url",
                "source_url": video["video_url"],
                "local_file_path": None,
            }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    job = create_audit_job(video, source)
    logger.info("Created audit job %s for %s", job["audit_id"], video["video_url"])
    start_audit_job(job["audit_id"])
    return AuditJobResponse.model_validate(job)


@app.post("/audits/upload", response_model=AuditJobResponse, status_code=202)
async def create_uploaded_audit(file: UploadFile = File(...)):
    """
    Creates an asynchronous audit job for a directly uploaded video file.
    """
    saved_file: Path | None = None
    try:
        saved_file = save_uploaded_media(file)
        video = build_uploaded_file_preview(file.filename)
        source = {
            "source_type": "upload",
            "source_url": video["video_url"],
            "local_file_path": str(saved_file),
        }
        job = create_audit_job(video, source)
        logger.info("Created upload audit job %s for %s", job["audit_id"], file.filename)
        start_audit_job(job["audit_id"])
        return AuditJobResponse.model_validate(job)
    except HTTPException:
        if saved_file and saved_file.exists():
            saved_file.unlink(missing_ok=True)
        raise
    except Exception as exc:
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
