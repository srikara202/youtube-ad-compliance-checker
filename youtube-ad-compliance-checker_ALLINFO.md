# YouTube Ad Compliance Checker - ALLINFO

## 1. Executive Summary

YouTube Ad Compliance Checker is an AI-assisted review system for advertisement videos. The repository combines a FastAPI backend, a LangGraph two-step audit workflow, Azure Video Indexer extraction, Azure AI Search retrieval over policy PDFs, Azure OpenAI reasoning, optional Azure Blob-backed async job storage, a self-hosted worker for YouTube jobs, and a React/Vite frontend for creating and tracking audit jobs.

The problem it solves is the manual, repetitive work of reviewing ad creative against platform and disclosure guidance. A reviewer normally has to inspect video content, capture spoken words and on-screen text, cross-reference policy material, decide whether content is compliant, and summarize the decision. This project turns that into a retrieval-backed workflow: extract transcript/OCR, retrieve policy chunks, ask an LLM for a structured judgment, then display the result in a web UI.

The target users visible from repo evidence are developers, demo reviewers, and technical evaluators who need to audit ad videos, especially YouTube-oriented creative. The README describes the repo as an MVP and deployable demo rather than a finished enterprise platform.

The core workflow is: submit an upload, YouTube URL, or remote media URL; create an async audit job; index the media through Azure Video Indexer or YouTube transcript fallback; retrieve policy context from Azure AI Search; call Azure OpenAI for JSON compliance results; store job state; poll the result from the browser.

The main technical achievement is the split execution model. The cloud-hosted FastAPI app can queue YouTube jobs for a local self-hosted worker through Azure Blob Storage when YouTube downloads are blocked from Azure IP ranges, while uploads and direct media URLs can still run in the Azure-hosted process.

Interview pitch: "I built a full-stack AI compliance review demo for ad videos. It uses FastAPI and React for the product surface, LangGraph for a clear two-stage audit pipeline, Azure Video Indexer for transcript/OCR extraction, Azure AI Search plus Azure OpenAI for retrieval-backed decisions, and an async job system that can offload YouTube processing to a self-hosted worker when cloud downloads are blocked."

## 2. Project Metadata

| Field | Evidence-based value |
|---|---|
| Inferred project name | YouTube Ad Compliance Checker, from `README.md`, repo directory, deployed URL, and UI copy. |
| Filesystem-safe document name | `youtube-ad-compliance-checker_ALLINFO.md`. |
| Python package name | `complianceqapipeline` in `pyproject.toml`. |
| Frontend package name | `youtube-add-compliance-checker-frontend` in `frontend/package.json`; note the repo has several "Add" spellings where "Ad" appears intended. |
| Repository type | Full-stack AI web app plus Azure deployment scripts. |
| Main languages | Python 3.12, TypeScript/TSX, CSS, PowerShell, shell, YAML. |
| Backend framework | FastAPI with Pydantic models and Uvicorn/Gunicorn runtime. |
| AI/workflow stack | LangGraph, LangChain, Azure OpenAI embeddings/chat, Azure AI Search vector store. |
| Video/media stack | Azure Video Indexer, `yt-dlp`, YouTube oEmbed, `youtube-transcript-api`, `requests`. |
| Frontend framework | React 19, Vite, React Query, React Markdown. |
| Testing frameworks | Python `unittest`, FastAPI `TestClient`, Vitest, Testing Library, jsdom. |
| Package/build tools | `uv` via `pyproject.toml` and `uv.lock`, `pip` via `requirements.txt`, npm via `frontend/package-lock.json`, TypeScript build via `tsc -b`. |
| Runtime assumptions | Python 3.12, Node 20 in CI, Azure App Service Linux, Azure resources configured through environment variables. |
| External services | Azure OpenAI, Azure AI Search, Azure Video Indexer, Azure Blob Storage, Azure Monitor/Application Insights, YouTube, GitHub Actions, GitHub branch protection API. |
| Main backend entrypoints | `backend/src/api/server.py`, `backend/src/graph/workflow.py`, `backend/src/worker/self_hosted_worker.py`, `main.py`. |
| Main frontend entrypoints | `frontend/index.html`, `frontend/src/main.tsx`, `frontend/src/App.tsx`. |
| Important config files | `pyproject.toml`, `requirements.txt`, `uv.lock`, `frontend/package.json`, `frontend/package-lock.json`, Vite and TS configs, `.github/workflows/ci-cd.yml`, `startup.sh`. |
| Backend test command found | `python -m unittest discover -s backend/tests`. |
| Frontend test command found | `npm --prefix frontend run test` in CI and `npm.cmd run test` in README examples. |
| Frontend build command found | `npm --prefix frontend run build` or from `frontend`, `npm.cmd run build`. |
| Backend dev command found | README documents `uv run uvicorn backend.src.api.server:app --reload`. |
| Deployment clues | Azure App Service docs/scripts, `startup.sh`, GitHub Actions OIDC deploy, App Service build settings, managed identity role assignment. |
| Database/storage layer | No relational database used by current code. Job storage is in-memory or Azure Blob JSON records. Policy retrieval uses Azure AI Search. |
| Auth/authz | No application user authentication visible. Azure service auth uses managed identity/DefaultAzureCredential and secrets/app settings. |

## 3. Quick Start Guide

### Prerequisites

- Python 3.12, confirmed by `.python-version`, `pyproject.toml`, CI, and App Service scripts.
- Node.js 20 or compatible, confirmed by GitHub Actions setup and package lock engines.
- npm for the frontend.
- Azure resources for Azure OpenAI, Azure AI Search, Azure Video Indexer, and optionally Azure Blob Storage.
- Azure CLI for deployment scripts.

### Install Backend Dependencies

Two dependency paths are present:

```powershell
uv sync
```

or:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

The repo evidence suggests local development leans toward `uv` (`pyproject.toml`, `uv.lock`), while CI/App Service uses `requirements.txt`.

### Install Frontend Dependencies

```powershell
cd frontend
npm.cmd install
```

CI uses:

```powershell
npm ci --prefix frontend
```

### Environment Variables

No `.env.example` is tracked. `.env` is ignored by `.gitignore`, so values are intentionally absent from the repo. Based on code, docs, and scripts, these names matter:

| Variable | Purpose |
|---|---|
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint for embeddings/chat. |
| `AZURE_OPENAI_API_KEY` | Key-based auth for Azure OpenAI where used. Value must be secret. |
| `AZURE_OPENAI_API_VERSION` | API version passed to Azure OpenAI clients. |
| `AZURE_OPENAI_CHAT_DEPLOYMENT` | Chat model deployment for `audit_content_node`. |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | Embedding deployment for indexing and retrieval. |
| `AZURE_SEARCH_ENDPOINT` | Azure AI Search service endpoint. |
| `AZURE_SEARCH_API_KEY` | Search admin/query key. Value must be secret. |
| `AZURE_SEARCH_INDEX_NAME` | Search index name for policy chunks. |
| `AZURE_VI_ACCOUNT_ID` | Azure Video Indexer account ID. |
| `AZURE_VI_LOCATION` | Video Indexer region. |
| `AZURE_VI_NAME` | Video Indexer account resource name. |
| `AZURE_SUBSCRIPTION_ID` | Azure subscription for ARM calls. |
| `AZURE_RESOURCE_GROUP` | Resource group containing Video Indexer. |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | Enables Azure Monitor OpenTelemetry. Value must be secret-ish operational config. |
| `AUDIT_JOB_STORE` | `memory` or `azure_blob`. |
| `AZURE_STORAGE_CONNECTION_STRING` | Required for Azure Blob job store. Value must be secret. |
| `AUDIT_JOB_BLOB_CONTAINER` | Job container, defaults to `audit-jobs`. |
| `AUDIT_JOB_BLOB_PREFIX` | Blob prefix, defaults to `jobs`. |
| `YOUTUBE_AUDIT_EXECUTION_TARGET` | `azure` or `self_hosted` for YouTube jobs. |
| `SELF_HOSTED_WORKER_ID` | Optional ID written to claimed jobs. |
| `SELF_HOSTED_WORKER_POLL_SECONDS` | Worker polling interval. |
| `FRONTEND_ORIGINS` | CORS allowlist. |
| `FRONTEND_DIST_DIR` | Override for served built frontend path. |
| `UPLOAD_TEMP_DIR` | Base temp directory for upload staging. |
| `VITE_API_BASE_URL` | Frontend API base URL override. |
| `GUNICORN_TIMEOUT` | Optional App Service runtime timeout, default `600` in `startup.sh`. |
| `GUNICORN_WORKERS` | Optional worker count, default `1` in `startup.sh`. |
| `PORT` | Runtime bind port, default `8000` in `startup.sh`. |
| `LANGCHAIN_TRACING_V2`, `LANGCHAIN_ENDPOINT`, `LANGCHAIN_API_KEY`, `LANGCHAIN_PROJECT` | Mentioned in README as optional tracing configuration. |

Secret values are not present in tracked files and should not be committed.

### Run Backend Locally

```powershell
uv run uvicorn backend.src.api.server:app --reload
```

Expected URL: `http://127.0.0.1:8000`.

### Run Frontend Locally

```powershell
cd frontend
npm.cmd run dev
```

Expected URL: `http://127.0.0.1:5173`. `frontend/vite.config.ts` proxies `/audit`, `/audits`, and `/health` to `http://127.0.0.1:8000`.

### Build

Frontend:

```powershell
cd frontend
npm.cmd run build
```

Backend has no separate compile/build step. Production uses Gunicorn/Uvicorn with `backend.src.api.server:app`.

### Test

Backend:

```powershell
python -m unittest discover -s backend/tests
```

Frontend:

```powershell
cd frontend
npm.cmd run test
```

Validation attempted in this workspace:

- Backend tests failed to import because the active Python environment lacks dependencies such as `fastapi`, Azure SDK packages, `langchain_openai`, and `yt_dlp`.
- Frontend tests could not start because `npm.cmd` is not available in this shell.
- `python -m py_compile` succeeded for `main.py`, `backend/src/api/server.py`, and `backend/scripts/index_documents.py`; generated `__pycache__` directories were removed afterward.

### Common Troubleshooting

| Symptom | Repo-evident cause | Where to look |
|---|---|---|
| `/` returns frontend not built | `frontend/dist` missing | `resolve_frontend_asset` in `backend/src/api/server.py` |
| Jobs stay `QUEUED` | Self-hosted target without worker, or memory store instead of shared Blob | `backend/src/api/audit_jobs.py`, `backend/src/worker/self_hosted_worker.py` |
| YouTube audits fail in Azure | YouTube bot/auth challenge or cloud download blocking | `is_youtube_download_blocked_error`, self-hosted worker docs |
| Upload rejected | Unsupported extension or missing filename | `ALLOWED_UPLOAD_EXTENSIONS`, `save_uploaded_media` |
| Audit returns `FAILED` with no report | Indexer or auditor put errors into LangGraph state | `index_video_node`, `audit_content_node`, `_execute_audit_job` |
| Document indexing appears to do nothing | `if __name__ == "__main__": index_docs` references function but does not call it | `backend/scripts/index_documents.py` |

## 4. What The Project Does

### Main User-Facing Features

- Upload a local video from the React UI.
- Create an async audit job.
- See video preview/source details after job creation.
- See job status: `QUEUED`, `PROCESSING`, `COMPLETED`, or `FAILED`.
- See a pass/fail compliance result.
- See compliance issue cards containing category, severity, and description.
- See the final report rendered as markdown.

The backend supports more than the current visible UI:

- YouTube URL audits through `POST /audits`.
- Remote media URL audits through `POST /audits`.
- Uploaded file audits through `POST /audits/upload`.
- Legacy synchronous audit through `POST /audit`.

The current checked-in `frontend/src/App.tsx` exposes only upload mode. `frontend/src/api.ts`, `frontend/src/utils/youtube.ts`, and `frontend/src/utils/media.ts` still contain support utilities for URL-based modes.

### Main Developer-Facing Features

- Direct graph invocation via `main.py`.
- Policy document indexing function in `backend/scripts/index_documents.py`.
- Unit tests for API shape, job orchestration, worker behavior, frontend upload UX, and Video Indexer helpers.
- Azure App Service bootstrap and GitHub OIDC scripts.
- Branch protection helper script.

### Inputs

- YouTube URLs in supported forms: `youtu.be`, `/watch?v=`, `/shorts/`, `/embed/`, `/live/`.
- Remote `http` or `https` media URLs.
- Uploaded files with extensions `.mp4`, `.mov`, `.m4v`, `.webm`, `.avi`, `.mkv`, `.mpeg`, `.mpg`.
- Policy PDFs stored under `backend/data`.

### Outputs

- Job records with preview metadata, status, timestamps, result/error, and worker metadata.
- Compliance result JSON with `status`, `compliance_results`, and `final_report`.
- UI rendering of issue cards and markdown report.
- Azure AI Search index records when indexing documents.

### Happy Path

1. User selects a local video in the React app.
2. `createUploadAudit` submits multipart form data to `/audits/upload`.
3. FastAPI validates/saves the upload, builds preview metadata, creates a job, and starts a background thread.
4. The graph runs `index_video_node` and `audit_content_node`.
5. Video Indexer extracts transcript and OCR.
6. Azure AI Search retrieves policy chunks.
7. Azure OpenAI returns strict JSON.
8. Job store updates result to `COMPLETED`.
9. React Query polling stops and the UI renders result/report.

### Important Failure Paths

- Invalid URL or empty URL: FastAPI returns `400`.
- Upload extension not allowed: FastAPI returns `400`.
- Upload job creation error: temporary file is deleted and FastAPI returns `500`.
- Uploaded temp file missing during graph processing: indexer returns an error state.
- YouTube cloud download blocked: code may fall back to public transcript; if no transcript, the job fails.
- Azure Video Indexer returns failed/quarantined state: graph returns error, job becomes `FAILED`.
- LLM returns malformed JSON: auditor catches exception, stores error, job becomes `FAILED`.
- Blob job update keeps conflicting: `BlobAuditJobStore.update_job` raises after five failed ETag attempts.

### Known Limitations Visible From Code

- No user accounts, authentication, authorization, or audit history UI.
- In-memory job store loses data on process restart.
- Blob store is JSON-per-job and manually polled; no queue service or event trigger.
- `start_audit_job` uses a daemon thread inside the API process, which is simple but not robust for long production jobs.
- The final audit depends on model JSON compliance; no schema repair or Pydantic validation is applied in `audit_content_node`.
- `main.py` invokes the graph with minimal initial state and a hardcoded YouTube URL.
- `backend/scripts/index_documents.py` contains indexing logic but its `__main__` block does not actually call `index_docs()`.
- `backend/Dockerfile` is tracked but empty.
- Several dependencies in `pyproject.toml` and `requirements.txt` are not used by current tracked source, including Redis, SQLAlchemy, psycopg2, Streamlit, Firecrawl, and pandas.

## 5. High-Level Architecture

### Component Diagram

```text
Browser / React UI
  |
  | POST /audits/upload, GET /audits/{id}
  v
FastAPI server
  |
  | creates/updates jobs
  v
Audit job store
  |-- memory for local single-process runs
  |-- Azure Blob JSON records for shared cloud/local worker runs
  |
  | starts graph directly for azure target
  v
LangGraph workflow
  |
  +--> indexer node
  |      |-- upload/download media
  |      |-- Azure Video Indexer
  |      |-- YouTube transcript fallback
  |
  +--> auditor node
         |-- Azure OpenAI embeddings
         |-- Azure AI Search retrieval
         |-- Azure OpenAI chat JSON judgment

Optional local self-hosted worker
  |
  | polls/claims self_hosted jobs from Blob store
  v
same LangGraph workflow
```

### Major Modules

- API surface: `backend/src/api/server.py`.
- Job orchestration: `backend/src/api/audit_jobs.py`.
- Job persistence: `backend/src/api/job_store.py`.
- Telemetry: `backend/src/api/telemetry.py`.
- Graph state/schema: `backend/src/graph/state.py`.
- Graph topology: `backend/src/graph/workflow.py`.
- Graph node logic: `backend/src/graph/nodes.py`.
- Video/media/Azure helpers: `backend/src/services/video_indexer.py`.
- Worker loop: `backend/src/worker/self_hosted_worker.py`.
- Frontend app: `frontend/src/App.tsx`.
- Frontend API client/types/utils: `frontend/src/api.ts`, `frontend/src/types.ts`, `frontend/src/utils/*`.

### Frontend/Backend Split

The React frontend is a client-side app built by Vite. During development, Vite proxies API requests to FastAPI. In production, FastAPI serves `frontend/dist` when present and falls back to `index.html` for client-side routes.

### Storage

No database tables or ORM models are used in current source. The job store abstraction has:

- `InMemoryAuditJobStore`: process-local dictionary protected by a threading lock.
- `BlobAuditJobStore`: Azure Blob container with one JSON blob per job, ETag-based optimistic concurrency for updates/claims.

Policy content lives in PDFs in `backend/data` and is indexed into Azure AI Search by `index_docs()`.

### Auth and Authorization

There is no app-level user auth. Azure service access uses:

- `DefaultAzureCredential` for ARM token acquisition in `VideoIndexerService`.
- Azure OpenAI and Search environment variables/API keys for LangChain clients.
- GitHub Actions OIDC for deployment.
- GitHub PAT only for the branch protection helper script, passed as a script parameter.

### AI/RAG Components

- `index_video_node` extracts video text.
- `audit_content_node` embeds transcript/OCR query text and retrieves top 3 Azure Search documents.
- The auditor prompt includes retrieved policy text, transcript, OCR, and metadata.
- Azure Chat OpenAI is expected to return strict JSON.

### Background Jobs

- API-process background jobs use `threading.Thread(..., daemon=True)`.
- Self-hosted jobs are claimed by `backend/src/worker/self_hosted_worker.py` from a shared job store.

### Observability

- Standard Python logging is used throughout backend modules.
- `backend/src/api/telemetry.py` configures Azure Monitor/OpenTelemetry only when `APPLICATIONINSIGHTS_CONNECTION_STRING` exists.
- No custom metrics, trace spans, dashboards, or structured log schema are visible in tracked code.

## 6. End-to-End Workflows

### Workflow A: Upload Audit From Current UI

| Step | Detail |
|---|---|
| Trigger | User selects a video file and submits the React form. |
| Frontend files | `frontend/src/App.tsx`, `frontend/src/api.ts`, `frontend/src/types.ts`. |
| Backend files | `backend/src/api/server.py`, `backend/src/api/audit_jobs.py`, `backend/src/api/job_store.py`, graph/service files. |
| Inputs | Browser `File` object, multipart form field `file`. |
| Outputs | `AuditJobResponse`, then final `AuditJobResult`. |
| Side effects | Temp file written under `UPLOAD_TEMP_DIR` or OS temp; job record created; background thread started; temp file deleted by indexer `finally`. |
| Failure behavior | Invalid/missing filename or extension returns `400`; job creation exception deletes saved file and returns `500`; workflow errors mark job `FAILED`. |

Step-by-step:

1. `handleUploadChange` stores the chosen `File`.
2. `handleSubmit` checks that a file exists and runs `createAuditMutation`.
3. `createUploadAudit` builds `FormData` and calls `/audits/upload`.
4. `create_uploaded_audit` calls `save_uploaded_media`.
5. `save_uploaded_media` validates filename/extension and streams upload to a temp file.
6. `build_uploaded_file_preview` creates `uploaded://<filename>` metadata.
7. `create_audit_job` delegates to the configured job store.
8. `start_audit_job` starts `_run_audit_job` if `execution_target` is `azure`.
9. React Query seeds the returned job into cache and polls `GET /audits/{audit_id}` every 3 seconds until terminal.
10. `_execute_audit_job` runs the LangGraph workflow, then stores `COMPLETED` or `FAILED`.
11. The UI renders preview, progress, issues, and markdown report.

### Workflow B: YouTube URL Audit Through Backend

| Step | Detail |
|---|---|
| Trigger | `POST /audits` with `source_type: "youtube"` and `source_url` or `video_url`. |
| Metadata | `extract_youtube_metadata` normalizes the URL, tries oEmbed, then falls back to `yt-dlp`. |
| Execution target | `resolve_youtube_execution_target` reads `YOUTUBE_AUDIT_EXECUTION_TARGET`; default `azure`, optional `self_hosted`. |
| Direct Azure path | Starts a backend thread if target is `azure`. |
| Self-hosted path | Leaves job `QUEUED`; a worker must claim it. |
| Failure behavior | Invalid URL or metadata lookup errors become `400`; later download/index/audit errors become job failure. |

In the graph, `index_video_node` validates the URL, tries to download YouTube media, uploads the file to Azure Video Indexer, waits for processing, and extracts transcript/OCR. If download fails with a recognized YouTube blocking/auth challenge, it calls `extract_youtube_transcript` and continues transcript-only.

### Workflow C: Remote Media URL Audit

| Step | Detail |
|---|---|
| Trigger | `POST /audits` with `source_type: "media_url"`. |
| Metadata | `extract_media_url_metadata` validates `http`/`https` and derives label/title from URL path/host. |
| Execution target | Always `azure` in `create_video_audit`. |
| Graph path | `index_video_node` calls `upload_video_url`, then waits for Video Indexer. |
| Failure behavior | Invalid URL returns `400`; Azure upload/index failures mark job `FAILED`. |

### Workflow D: Self-Hosted Worker

| Step | Detail |
|---|---|
| Trigger | `python -m backend.src.worker.self_hosted_worker` or `--once`. |
| Required mode | Shared store, currently `azure_blob`. |
| Claiming | `claim_next_audit_job(execution_target="self_hosted")`. |
| Processing | `run_claimed_audit_job` runs `_execute_audit_job` without re-marking processing because claim already did it. |
| Output | Updates same shared job record to `COMPLETED` or `FAILED`. |
| Failure behavior | If store is not shared and cannot infer Blob from connection string, exits `1`. |

### Workflow E: Synchronous Legacy Audit

| Step | Detail |
|---|---|
| Trigger | `POST /audit` with `video_url`. |
| Session | `audit_video` creates a UUID session and `vid_<prefix>`. |
| Processing | Calls `run_compliance_audit` directly and waits. |
| Output | `AuditResponse` with `session_id`, `video_id`, `status`, `final_report`, and `compliance_results`. |
| Failure behavior | Catches exceptions and returns HTTP `500`. |

### Workflow F: Policy Document Indexing

| Step | Detail |
|---|---|
| Trigger | Intended via `backend/scripts/index_documents.py`; current `__main__` block references `index_docs` but does not call it. |
| Inputs | PDFs under `backend/data`. |
| Processing | `PyPDFLoader` loads documents; `RecursiveCharacterTextSplitter` chunks with size 1000 and overlap 200; Azure OpenAI embeddings vectorize; Azure Search stores chunks. |
| Output | Azure AI Search index populated with document chunks and source metadata. |
| Failure behavior | Missing env vars or Azure client init failures are logged and return without raising. |

### Workflow G: CI/CD Deployment

1. Pull request or push to `main` triggers `.github/workflows/ci-cd.yml`.
2. Python 3.12 is installed.
3. `requirements.txt` dependencies are installed.
4. Backend unittest suite runs.
5. Node 20 is installed with npm cache.
6. Frontend dependencies install with `npm ci --prefix frontend`.
7. Frontend tests and build run.
8. On push, Python packages are vendored into `python_packages/lib/site-packages` inside a Python Docker container.
9. Artifact excludes `.git`, `.github`, venv, caches, backend tests, frontend source, and node modules.
10. Deploy job logs into Azure through OIDC and deploys the package to App Service.

## 7. Data Model, State, And Configuration

### LangGraph State

`backend/src/graph/state.py` defines `VideoAuditState` as a `TypedDict`.

| Field | Meaning |
|---|---|
| `video_url` | Main video URL used by legacy and graph code. |
| `video_id` | Internal ID like `vid_<uuid-prefix>`. |
| `source_type` | `youtube`, `media_url`, or `upload`. |
| `source_url` | Source URL or uploaded pseudo-URL. |
| `local_file_path` | Temporary upload path or downloaded YouTube path. |
| `video_metadata` | Metadata dictionary from Video Indexer or transcript fallback. |
| `transcript` | Speech-to-text string. |
| `ocr_text` | List of on-screen text strings. |
| `compliance_results` | Annotated with `operator.add` so LangGraph can accumulate lists. |
| `final_status` | `PASS` or `FAIL` according to prompt, with code fallback `UNKNOWN` in API job result. |
| `final_report` | Markdown/plain text final report. |
| `errors` | Annotated with `operator.add` for accumulated system errors. |

### Compliance Issue

Python `ComplianceIssue` in `state.py` includes `category`, `description`, `severity`, and optional `timestamp`. API/TypeScript issue models include `category`, `severity`, and `description`; timestamp is not exposed in the current API response model.

### Job Record

`build_job_record` returns:

```json
{
  "audit_id": "uuid",
  "job_status": "QUEUED",
  "execution_target": "azure",
  "video": {},
  "source": {},
  "result": null,
  "error": null,
  "created_at": "UTC ISO timestamp",
  "updated_at": "UTC ISO timestamp",
  "worker_id": null,
  "processing_started_at": null,
  "completed_at": null
}
```

The API response model exposes only a subset: audit ID, status, video, result, error, created/updated timestamps.

### Frontend Types

`frontend/src/types.ts` mirrors the API:

- `JobStatus`: `QUEUED | PROCESSING | COMPLETED | FAILED`.
- `ComplianceStatus`: `PASS | FAIL | UNKNOWN`.
- `AuditSourceType`: `youtube | media_url | upload`.
- Interfaces for issue, video preview, result, and job response.

### Validation Rules

- Backend upload extensions are in `ALLOWED_UPLOAD_EXTENSIONS`.
- Backend YouTube URL validation accepts supported YouTube hosts/routes and requires video ID pattern `^[A-Za-z0-9_-]{6,}$`.
- Backend media URL validation requires `http` or `https` and a host.
- Frontend utility validation mirrors YouTube/media URL logic, although current UI does not call these utilities.

### Configuration Objects

- FastAPI app metadata: title `"Youtube Add Compliance Checker API"`, description, version `1.0.0`.
- CORS origins: from `FRONTEND_ORIGINS` or local Vite defaults.
- Vite dev server: port `5173`, proxy to backend port `8000`.
- React Query: app-wide retry/focus defaults in `main.tsx`; job polling defaults in `App.tsx`.
- Azure Blob defaults: container `audit-jobs`, prefix `jobs`, mode `memory`.

## 8. API, Routes, Commands, And Entrypoints

| Entrypoint | Type | Defined in | Calls | Result |
|---|---|---|---|---|
| `POST /audit` | HTTP API | `backend/src/api/server.py` | `run_compliance_audit` | Synchronous `AuditResponse`. |
| `POST /audits` | HTTP API | `backend/src/api/server.py` | metadata helpers, `create_audit_job`, `start_audit_job` | Async job created for YouTube/media URL. |
| `POST /audits/upload` | HTTP API | `backend/src/api/server.py` | `save_uploaded_media`, `build_uploaded_file_preview`, job functions | Async upload job created. |
| `GET /audits/{audit_id}` | HTTP API | `backend/src/api/server.py` | `get_audit_job` | Current job state or `404`. |
| `GET /health` | HTTP API | `backend/src/api/server.py` | none | Health JSON. |
| `GET /`, `GET /{full_path}` | Frontend serving | `backend/src/api/server.py` | `resolve_frontend_asset`, `FileResponse` | Static asset or SPA fallback. |
| `create_graph()` | Graph factory | `backend/src/graph/workflow.py` | LangGraph `StateGraph` | Compiled graph. |
| `app = create_graph()` | Graph runnable | `backend/src/graph/workflow.py` | nodes | Imported by API and `main.py`. |
| `python -m backend.src.worker.self_hosted_worker` | CLI | `backend/src/worker/self_hosted_worker.py` | worker loop | Polls shared queue. |
| `python -m backend.src.worker.self_hosted_worker --once` | CLI | same | `process_next_job` once | Processes at most one job. |
| `run_cli_simulation()` | Dev harness | `main.py` | graph app | Prints audit report for hardcoded URL. |
| `index_docs()` | Script function | `backend/scripts/index_documents.py` | loaders, splitter, Azure OpenAI/Search | Indexes PDFs into Azure Search. |
| `npm run dev` | Frontend dev | `frontend/package.json` | Vite | Local frontend server. |
| `npm run build` | Frontend build | `frontend/package.json` | `tsc -b`, `vite build` | `frontend/dist`. |
| `npm run test` | Frontend tests | `frontend/package.json` | Vitest | UI test suite. |
| `bash startup.sh` | App Service startup | `startup.sh` | Gunicorn/Uvicorn | Runs backend server. |
| `.github/workflows/ci-cd.yml` | CI/CD | GitHub Actions | tests/build/deploy | Azure App Service deployment. |
| Azure bootstrap scripts | Operations | `scripts/azure/*` | Azure CLI | Provision and auth configuration. |
| Branch protection script | Operations | `scripts/github/set-main-branch-protection.ps1` | GitHub REST API | Protects `main`. |

## 9. Full Repository Map

```text
.
|-- .gitattributes                         # Forces shell scripts to LF.
|-- .github/
|   `-- workflows/
|       `-- ci-cd.yml                       # Test/build/deploy pipeline.
|-- .gitignore                              # Ignores env, caches, build outputs, docs/interview-prep-pack.md.
|-- .python-version                         # Python 3.12 marker.
|-- README.md                               # Main project overview and operating guide.
|-- backend/
|   |-- Dockerfile                          # Empty tracked Dockerfile placeholder.
|   |-- data/
|   |   |-- 1001a-influencer-guide-508_1.pdf # Policy/reference PDF for indexing.
|   |   `-- youtube-ad-specs.pdf            # YouTube ad specs/reference PDF for indexing.
|   |-- scripts/
|   |   `-- index_documents.py              # PDF to Azure AI Search indexing logic.
|   |-- src/
|   |   |-- api/
|   |   |   |-- audit_jobs.py               # Async audit orchestration.
|   |   |   |-- job_store.py                # Memory and Azure Blob job storage.
|   |   |   |-- server.py                   # FastAPI app, API models/routes, static serving.
|   |   |   `-- telemetry.py                # Azure Monitor setup.
|   |   |-- graph/
|   |   |   |-- __init__.py                 # Empty package marker.
|   |   |   |-- nodes.py                    # Indexer and auditor LangGraph nodes.
|   |   |   |-- state.py                    # LangGraph state TypedDicts.
|   |   |   `-- workflow.py                 # Graph topology.
|   |   |-- services/
|   |   |   |-- __init__.py                 # Empty package marker.
|   |   |   `-- video_indexer.py            # YouTube/media/Video Indexer helpers.
|   |   `-- worker/
|   |       |-- __init__.py                 # Worker package docstring.
|   |       `-- self_hosted_worker.py       # Local worker polling shared jobs.
|   `-- tests/
|       |-- test_api_server.py              # FastAPI endpoint and frontend-serving tests.
|       |-- test_audit_jobs.py              # Job transition/claim tests.
|       |-- test_graph_nodes.py             # Indexer fallback test.
|       |-- test_self_hosted_worker.py      # Worker behavior tests.
|       `-- test_video_indexer.py           # Metadata/download/transcript helper tests.
|-- docs/
|   `-- azure-app-service.md                # Azure deployment guide.
|-- frontend/
|   |-- index.html                          # Vite HTML shell.
|   |-- package-lock.json                   # npm lockfile.
|   |-- package.json                        # Frontend package scripts/deps.
|   |-- src/
|   |   |-- App.test.tsx                    # React UI tests.
|   |   |-- App.tsx                         # Main UI.
|   |   |-- api.ts                          # Fetch client.
|   |   |-- main.tsx                        # React bootstrap.
|   |   |-- styles.css                      # Frontend styling.
|   |   |-- test/
|   |   |   `-- setup.ts                    # Vitest cleanup/jest-dom setup.
|   |   |-- types.ts                        # API TypeScript types.
|   |   |-- utils/
|   |   |   |-- media.ts                     # Remote media URL validation.
|   |   |   `-- youtube.ts                   # YouTube URL validation.
|   |   `-- vite-env.d.ts                   # Vite env typing.
|   |-- tsconfig.app.json                   # App TS compiler options.
|   |-- tsconfig.json                       # TS project references.
|   |-- tsconfig.node.json                  # Node/Vite config TS options.
|   `-- vite.config.ts                      # Vite dev proxy and Vitest config.
|-- main.py                                 # Legacy graph runner.
|-- pyproject.toml                          # Python package metadata/deps.
|-- requirements.txt                        # Pinned Python deps for CI/App Service.
|-- scripts/
|   |-- azure/
|   |   |-- bootstrap_app_service.ps1        # Provision/configure App Service.
|   |   `-- create_github_oidc.ps1          # Configure GitHub OIDC Azure identity.
|   `-- github/
|       `-- set-main-branch-protection.ps1  # Configure branch protection.
|-- startup.sh                              # App Service Gunicorn startup.
`-- uv.lock                                 # uv Python lockfile.
```

## 10. File-By-File Deep Dive

### `.gitattributes`

**Role:** Git attributes configuration.

**Why it matters:** Ensures `*.sh` files use LF line endings, important for Linux App Service startup scripts.

**Key dependencies/imports:** None.

**Exports/public surface:** None.

**Used by:** Git checkout behavior.

| Lines/Section | Code Chunk | What It Does | Inputs | Outputs | Side Effects | Notes/Edge Cases |
|---|---|---|---|---|---|---|
| 1 | `*.sh text eol=lf` | Normalizes shell scripts to LF. | Shell script files. | Consistent line endings. | Affects Git working tree normalization. | Helps `startup.sh` run on Linux. |

**Potential interview talking points:** Small deployment hygiene detail for cross-platform repos.

**Possible improvements or risks:** None obvious.

### `.github/workflows/ci-cd.yml`

**Role:** GitHub Actions pipeline for tests, frontend build, packaging, and Azure App Service deployment.

**Why it matters:** This is the main automated validation and deployment path.

**Key dependencies/imports:** GitHub Actions `actions/checkout`, `actions/setup-python`, `actions/setup-node`, `actions/upload-artifact`, `actions/download-artifact`, `azure/login`, `azure/webapps-deploy`; Docker for vendoring Python packages.

**Exports/public surface:** Workflow named `CI/CD` with jobs `test-and-build` and `deploy`.

**Used by:** GitHub on pull requests and pushes to `main`.

| Lines/Section | Code Chunk | What It Does | Inputs | Outputs | Side Effects | Notes/Edge Cases |
|---|---|---|---|---|---|---|
| Trigger | `pull_request` and `push` on `main` | Runs CI for PRs and deploy path for pushes. | GitHub events. | Workflow run. | Uses GitHub-hosted runners. | Deploy job is push-only. |
| `test-and-build` | Python setup/install/tests | Installs Python 3.12 deps from `requirements.txt` and runs backend tests. | `requirements.txt`, `backend/tests`. | Pass/fail test result. | Downloads dependencies. | Does not use `uv.lock`. |
| Frontend steps | Node setup, npm ci/test/build | Installs Node 20 deps, runs Vitest, builds Vite app. | `frontend/package-lock.json`. | `frontend/dist`. | Uses npm cache. | Frontend source excluded from deployment artifact after build. |
| Vendoring | Docker `python:3.12-bullseye` | Installs Python packages into `python_packages/lib/site-packages`. | `requirements.txt`. | Vendored site-packages folder. | Removes/recreates `python_packages`. | Push-only; uses Docker in CI. |
| Artifact upload | `path` include/exclude list | Packages repo minus source/caches/tests. | Built repo state. | `webapp-package`. | Stores 7-day artifact. | Excludes `frontend/src` and backend tests. |
| `deploy` | Azure login and deploy | Uses GitHub OIDC secrets. | `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `AZURE_WEBAPP_NAME`. | Azure Web App updated. | Production deployment. | Requires environment `production`. |

**Potential interview talking points:** One pipeline supports PR validation and push deployment; OIDC avoids storing Azure passwords.

**Possible improvements or risks:** Backend dependency source differs from `uv.lock`; vendoring with Docker can mask local platform issues; no artifact integrity/signing; no smoke test after deployment in workflow.

### `.gitignore`

**Role:** Defines ignored files and directories.

**Why it matters:** Protects secrets and keeps generated artifacts out of Git.

**Key dependencies/imports:** None.

**Exports/public surface:** Ignore patterns.

**Used by:** Git.

| Lines/Section | Code Chunk | What It Does | Inputs | Outputs | Side Effects | Notes/Edge Cases |
|---|---|---|---|---|---|---|
| `docs/interview-prep-pack.md` | Ignores a docs artifact | Keeps a separate interview pack out of Git. | That path. | Ignored file. | None. | This ALLINFO file is not ignored. |
| Python ignores | `__pycache__/`, `*.py[oc]`, build outputs | Excludes generated Python artifacts. | Python runtime/build outputs. | Clean status. | None. | Useful after tests/compilation. |
| `.venv`, `.env` | Ignores venv and env file | Protects secrets and local deps. | Local developer files. | Not tracked. | None. | No `.env.example` is present. |
| Frontend ignores | `node_modules`, `dist`, tsbuildinfo | Excludes dependency/build outputs. | npm/Vite output. | Not tracked. | None. | CI builds `frontend/dist` for deployment artifact. |
| Test caches | `.pytest_cache`, `coverage` | Excludes test artifacts. | Test runs. | Clean repo. | None. | Tests use unittest/Vitest, not pytest currently. |

**Potential interview talking points:** Secrets are intentionally externalized; generated frontend/backend artifacts are deploy-time products.

**Possible improvements or risks:** Add `.env.example` while keeping `.env` ignored.

### `.python-version`

**Role:** Python version marker.

**Why it matters:** Aligns local tooling with Python 3.12 used by CI and App Service.

**Key dependencies/imports:** None.

**Exports/public surface:** Version `3.12`.

**Used by:** pyenv/asdf/uv-compatible tooling.

| Section | What It Does | Notes |
|---|---|---|
| `3.12` | Pins intended Python major/minor. | Matches `pyproject.toml` and CI. |

**Potential interview talking points:** Runtime version consistency.

**Possible improvements or risks:** None.

### `README.md`

**Role:** Main project documentation.

**Why it matters:** Provides the strongest project identity, architecture overview, setup commands, API overview, deployment notes, limitations, and future improvements.

**Key dependencies/imports:** Not code.

**Exports/public surface:** Human-readable docs.

**Used by:** Developers, interviewers, maintainers.

| Section | What It Does | Inputs | Outputs | Notes/Edge Cases |
|---|---|---|---|---|
| Title/overview | Defines product as an AI-powered compliance review system. | Repo evidence and architecture. | Project framing. | Mentions deployed Azure URL. |
| Why/features | Describes ad review problem and key features. | Product goals. | Value proposition. | Clearly marks MVP/demo nature. |
| Architecture | Mermaid graph and component list. | Code modules. | System map. | Accurately highlights self-hosted worker. |
| Workflow | Explains job creation, indexer, retrieval, audit, delivery. | API/graph code. | End-to-end guide. | Notes current frontend is upload-only. |
| Config/running | Lists environment variables and commands. | Code and scripts. | Developer setup. | No `.env.example` exists. |
| API/deployment/testing | Documents endpoints, Azure deployment, tests. | Backend/frontend/CI. | Operational guide. | Notes empty Dockerfile caveat. |
| Troubleshooting/limitations | Names known failure modes. | Code behavior. | Maintenance guide. | Good source for interview risk discussion. |

**Potential interview talking points:** The README itself is unusually explicit about operational tradeoffs and limitations.

**Possible improvements or risks:** Keep it synchronized if UI re-adds URL modes or indexing entrypoint changes.

### `backend/Dockerfile`

**Role:** Empty tracked placeholder.

**Why it matters:** Its presence could imply Docker support, but it contains no instructions.

**Key dependencies/imports:** None.

**Exports/public surface:** None.

**Used by:** No repo evidence of active use.

| Section | What It Does | Notes |
|---|---|---|
| Empty file | No Docker build definition. | README correctly says Docker is not wired despite this file. |

**Potential interview talking points:** Distinguish deployment evidence from placeholder files.

**Possible improvements or risks:** Either remove it or add a real Dockerfile if container deployment becomes supported.

### `backend/data/1001a-influencer-guide-508_1.pdf`

**Role:** Tracked policy/reference PDF.

**Why it matters:** It is part of the knowledge base intended for Azure AI Search indexing.

**Key dependencies/imports:** Loaded by `PyPDFLoader` in `backend/scripts/index_documents.py`.

**Exports/public surface:** PDF content; code does not decode it directly at runtime.

**Used by:** `index_docs()` when scanning `backend/data/*.pdf`.

| Section | What It Does | Notes |
|---|---|---|
| Binary PDF | Source document for policy chunks. | Detailed code-level analysis is not applicable; file is tracked and first-party data for retrieval. |

**Potential interview talking points:** RAG quality depends on curated policy source documents.

**Possible improvements or risks:** Add metadata/version documentation and test that indexing includes expected sources.

### `backend/data/youtube-ad-specs.pdf`

**Role:** Tracked YouTube ad specs/reference PDF.

**Why it matters:** It is the most directly named policy source for YouTube ad compliance retrieval.

**Key dependencies/imports:** Loaded by `PyPDFLoader` in `backend/scripts/index_documents.py`.

**Exports/public surface:** PDF content; not code.

**Used by:** `index_docs()` through `glob("*.pdf")`.

| Section | What It Does | Notes |
|---|---|---|
| Binary PDF | Source document for policy chunks. | Detailed code-level analysis is not applicable. |

**Potential interview talking points:** The retrieval layer grounds LLM judgments in real policy material rather than only model prior knowledge.

**Possible improvements or risks:** Add source URL/date/version to reduce ambiguity over policy freshness.

### `backend/scripts/index_documents.py`

**Role:** Indexes PDF policy documents into Azure AI Search.

**Why it matters:** This is what turns static PDFs into retrievable RAG context for `audit_content_node`.

**Key dependencies/imports:** `dotenv`, `glob`, `PyPDFLoader`, `RecursiveCharacterTextSplitter`, `AzureOpenAIEmbeddings`, `AzureSearch`, `os`, `logging`.

**Exports/public surface:** Function `index_docs()`.

**Used by:** Intended manual/admin workflow; no code imports it in current tracked source.

| Lines/Section | Code Chunk | What It Does | Inputs | Outputs | Side Effects | Notes/Edge Cases |
|---|---|---|---|---|---|---|
| Imports/setup | `load_dotenv(override=True)`, logging config | Loads env and configures logging. | `.env` if present. | Logger. | May override process env values. | Secret values are logged indirectly for endpoints/names, not keys. |
| `index_docs` path setup | Computes `data_folder` | Points at `backend/data`. | Script location. | PDF folder path. | None. | Path string is a little indirect but resolves to repo `backend/data`. |
| Env check | Logs config and validates required vars | Ensures Azure OpenAI/Search names and keys exist. | Env vars. | Early return on missing vars. | Logs configuration names/endpoints. | Avoid logging secret values; current code does not log keys. |
| Embedding init | `AzureOpenAIEmbeddings(...)` | Creates embedding client. | Deployment, endpoint, API key, API version. | Embeddings object. | Network use later. | Default deployment `text-embedding-3-small`. |
| Search init | `AzureSearch(...)` | Creates vector store client. | Search endpoint/key/index, embedding function. | Vector store. | Network use later. | Uses LangChain AzureSearch wrapper. |
| PDF scan | `glob(... "*.pdf")` | Finds all tracked/current PDFs. | Filesystem. | List of PDFs. | None. | Warns if none found but continues. |
| PDF processing | `PyPDFLoader`, splitter | Loads pages, chunks text size 1000 overlap 200, tags source filename. | PDF bytes. | `all_splits`. | Reads files. | Per-PDF exceptions are logged and do not stop all indexing. |
| Upload | `vector_store.add_documents` | Sends chunks to Azure AI Search. | Document chunks. | Search index records. | External write. | Logs success/failure. |
| `__main__` | `index_docs` | References the function but does not call it. | None. | None. | None. | Should be `index_docs()` for script execution. |

**Potential interview talking points:** Clear RAG ingestion design: load, chunk, embed, index, then retrieve in audit stage.

**Possible improvements or risks:** Fix `__main__`; add CLI args for data folder/index name; fail with nonzero exit on missing config in automation; add document version metadata; add tests.

### `backend/src/api/audit_jobs.py`

**Role:** Async audit job orchestration.

**Why it matters:** Connects HTTP job creation, storage, background execution, graph invocation, and self-hosted worker execution.

**Key dependencies/imports:** `threading`, `socket`, `os`, `backend.src.api.job_store`, `backend.src.graph.workflow.app`.

**Exports/public surface:** `get_job_store`, `set_job_store`, `reset_job_store`, `get_job_store_mode`, `get_shared_job_store_modes`, `resolve_youtube_execution_target`, `run_compliance_audit`, `create_audit_job`, `get_audit_job`, `update_audit_job`, `claim_next_audit_job`, `start_audit_job`, `run_claimed_audit_job`.

**Used by:** `server.py`, `self_hosted_worker.py`, backend tests.

| Lines/Section | Code Chunk | What It Does | Inputs | Outputs | Side Effects | Notes/Edge Cases |
|---|---|---|---|---|---|---|
| Module globals | `_job_store`, `_job_store_lock` | Lazy singleton job store. | None. | Store instance. | Shared process state. | Tests swap/reset it. |
| Store accessors | `get_job_store`, `set_job_store`, `reset_job_store` | Builds or overrides store. | Env vars or test store. | `AuditJobStore`. | Thread-safe global mutation. | `build_job_store_from_env` can raise if Blob config missing. |
| Mode helpers | `get_job_store_mode`, `get_shared_job_store_modes` | Expose storage mode names. | Store. | Strings/set. | None. | Shared modes hardcoded to `azure_blob`. |
| `resolve_youtube_execution_target` | Reads `YOUTUBE_AUDIT_EXECUTION_TARGET`. | Env var. | `self_hosted` or `azure`. | None. | Unknown values silently become `azure`. |
| `run_compliance_audit` | Normalizes source and invokes graph. | Source dict/string, video ID. | Final graph state. | Calls external services through graph. | For string source defaults to YouTube. |
| CRUD wrappers | `create_audit_job`, `get_audit_job`, `update_audit_job` | Delegates to store. | Job data. | Job record or None. | Store write/read. | Keeps API isolated from store implementation. |
| `claim_next_audit_job` | Claims queued target job for worker. | Execution target, worker ID. | Claimed job or None. | Mutates job to `PROCESSING`. | Worker ID falls back to env or hostname. |
| `start_audit_job` | Starts daemon thread for Azure target. | Audit ID. | None. | Thread side effect. | Skips self-hosted jobs by design. |
| `_execute_audit_job` | Core job runner. | Audit ID or claimed job. | Job store updates. | Calls graph and writes status/result. | Marks `FAILED` if graph state has errors. |
| Exception handling | `except Exception` in `_execute_audit_job` | Converts crash to failed job. | Exception. | `FAILED` record. | Logs stack trace. | Good API behavior, but no retry. |

**Potential interview talking points:** Async API model is simple and demo-friendly; same executor supports API thread and local worker.

**Possible improvements or risks:** Daemon threads can be killed on process recycle; no retry/backoff; no job cancellation; no stale-processing recovery; `errors[0]` hides multiple errors.

### `backend/src/api/job_store.py`

**Role:** Defines job record schema and job storage backends.

**Why it matters:** Enables both local memory mode and shared Azure Blob mode for cloud/local worker coordination.

**Key dependencies/imports:** `azure.storage.blob`, `azure.core.MatchConditions`, Azure exceptions, `threading`, `uuid`, `datetime`, `json`, `copy`.

**Exports/public surface:** Constants, `utc_timestamp`, `build_job_record`, protocol `AuditJobStore`, classes `InMemoryAuditJobStore`, `BlobAuditJobStore`, `build_job_store_from_env`.

**Used by:** `audit_jobs.py`, worker, backend tests.

| Lines/Section | Code Chunk | What It Does | Inputs | Outputs | Side Effects | Notes/Edge Cases |
|---|---|---|---|---|---|---|
| Constants | defaults and shared modes | Defines default container/prefix/mode. | None. | Config defaults. | None. | Shared mode constant duplicated conceptually in `audit_jobs.py`. |
| `utc_timestamp` | UTC ISO timestamp. | Current time. | ISO string. | None. | Timezone aware. |
| `build_job_record` | Constructs full job JSON. | Video, source, execution target. | Job dict. | None. | Source defaults from video when absent. |
| `AuditJobStore` | Protocol interface. | Implementers. | Type contract. | None. | Runtime methods raise if protocol used directly. |
| `InMemoryAuditJobStore` | Dict store with lock. | Job records. | Deep-copied records. | Mutates process memory. | Lost on restart; safe from caller mutation by deep copies. |
| Memory `claim_next_job` | Sorts by `created_at`, finds queued target. | Execution target, worker ID. | Claimed job. | Marks processing/worker/time. | In-process only. |
| `BlobAuditJobStore.__init__` | Creates Blob client/container. | Connection string, container, prefix. | Store. | Creates container if absent. | Requires secret connection string. |
| Blob name/encode/decode | `_blob_name`, `_decode_job`, `_encode_job` | Maps jobs to JSON blobs. | Audit ID/blob. | JSON bytes/job+etag. | Reads blob properties/content. | Sort keys and compact JSON. |
| `_upload_job` | Uploads with optional ETag condition. | Blob client, job, etag. | None. | Writes blob. | ETag gives optimistic concurrency. |
| Blob create/get | `create_job`, `get_job` | Writes/reads job blobs. | Job fields or ID. | Job dict/None. | Blob I/O. | Missing blob returns None. |
| Blob update | retry loop up to 5 | Reads, mutates, writes if ETag unchanged. | Changes. | Updated record. | Blob I/O. | Raises if repeated conflicts. |
| Blob claim | Lists blobs, sorted by creation time | Atomically-ish claims first queued target. | Target, worker ID. | Claimed job/None. | Blob I/O. | Competing workers rely on ETag conflict handling. |
| `clear` | Deletes blobs under prefix. | None. | None. | Destructive in container prefix. | Used mostly for tests/admin; no tests for Blob shown. |
| `build_job_store_from_env` | Chooses memory or Blob. | Env vars. | Store instance. | May create Blob container. | Unknown modes warn and fall back to memory. |

**Potential interview talking points:** Azure Blob JSON records are a pragmatic queue/store for an MVP and enable self-hosted workers without introducing Redis/Service Bus.

**Possible improvements or risks:** Blob listing polling does not scale like a queue; no lease timeout or dead-letter state; no schema version on job records; no encryption configuration visible beyond Azure defaults.

### `backend/src/api/server.py`

**Role:** FastAPI application, request/response models, CORS, upload handling, audit endpoints, health check, and built frontend serving.

**Why it matters:** It is the main backend runtime entrypoint.

**Key dependencies/imports:** FastAPI, Pydantic, `dotenv`, filesystem/temp utilities, job functions, telemetry, video metadata helpers.

**Exports/public surface:** FastAPI `app`; Pydantic models; route handlers; upload/static helper functions.

**Used by:** Uvicorn/Gunicorn, tests, App Service startup.

| Lines/Section | Code Chunk | What It Does | Inputs | Outputs | Side Effects | Notes/Edge Cases |
|---|---|---|---|---|---|---|
| Env/telemetry/logging | `load_dotenv`, `setup_telemetry`, logging | Initializes runtime configuration. | Env/.env. | Configured app process. | May enable telemetry. | Runs at import time. |
| Constants | `REPO_ROOT`, `FRONTEND_DIST_DIR`, `UPLOAD_TEMP_DIR`, extensions | Centralizes path and upload config. | Env vars. | Paths/sets. | None. | `UPLOAD_TEMP_DIR` appends project folder to base temp dir. |
| `get_frontend_origins` | Parses CORS origins. | `FRONTEND_ORIGINS`. | List of origins. | None. | Defaults to Vite localhost. |
| `app = FastAPI(...)` | Creates API. | Metadata. | App instance. | None. | Title uses "Youtube Add" typo. |
| Pydantic models | Request/response schemas | Validate API data. | JSON/form-derived data. | Typed response models. | None. | `AuditUrlRequest` supports legacy `video_url` and newer `source_url`. |
| `ensure_upload_temp_dir` | Creates upload temp folder. | None. | Path. | Filesystem mkdir. | Parents created. |
| `save_uploaded_media` | Validates and writes uploaded file. | `UploadFile`. | Temp path. | File write. | Rejects missing filename/unsupported extension. |
| `POST /audit` | Legacy synchronous route. | `AuditRequest`. | `AuditResponse`. | Runs graph inline. | Exceptions become 500. |
| `POST /audits` | Async URL route. | YouTube/media request. | `AuditJobResponse` 202. | Creates job and starts/queues. | YouTube target may be self-hosted. |
| `POST /audits/upload` | Async upload route. | Multipart file. | `AuditJobResponse` 202. | Saves temp file, creates job. | Deletes saved temp file on creation failure; graph deletes after processing. |
| `GET /audits/{id}` | Status route. | Audit ID. | Job response. | Reads store. | 404 if missing. |
| `resolve_frontend_asset` | Static file resolver. | Request path. | Asset path or None. | Filesystem read checks. | Prevents path traversal via `relative_to`. |
| `GET /health` | Health endpoint. | None. | Healthy JSON. | None. | Does not verify Azure dependencies. |
| `serve_frontend` | Static/SPA route. | Path. | FileResponse or 404. | Serves files. | If built frontend missing, 404. |

**Potential interview talking points:** The API preserves a sync endpoint while adding async polling; upload cleanup and path traversal handling are practical details.

**Possible improvements or risks:** No auth/rate limiting/file size limit; daemon-thread job execution; health check is shallow; no content-type validation beyond extension.

### `backend/src/api/telemetry.py`

**Role:** Optional Azure Monitor/OpenTelemetry setup.

**Why it matters:** Gives the deployed app an observability hook without making telemetry mandatory for local runs.

**Key dependencies/imports:** `azure.monitor.opentelemetry.configure_azure_monitor`, `os`, `logging`.

**Exports/public surface:** `setup_telemetry()`.

**Used by:** `server.py` at import time.

| Lines/Section | Code Chunk | What It Does | Inputs | Outputs | Side Effects | Notes/Edge Cases |
|---|---|---|---|---|---|---|
| Logger | Dedicated telemetry logger. | None. | Logger. | None. | Logger name uses "youtube-add". |
| `setup_telemetry` | Reads connection string and configures Azure Monitor. | `APPLICATIONINSIGHTS_CONNECTION_STRING`. | None. | Enables instrumentation. | Logs warning if missing, catches setup errors. |

**Potential interview talking points:** Optional telemetry avoids blocking local development when App Insights is absent.

**Possible improvements or risks:** Could add explicit FastAPI instrumentation details, trace sampling config, and structured logging.

### `backend/src/graph/__init__.py`

**Role:** Empty package marker.

**Why it matters:** Makes `backend.src.graph` importable as a Python package.

**Key dependencies/imports:** None.

**Exports/public surface:** None.

**Used by:** Python import system.

| Section | What It Does | Notes |
|---|---|---|
| Empty | Package marker only. | No runtime behavior. |

**Potential interview talking points:** None beyond package layout.

**Possible improvements or risks:** Could export `create_graph` or app for cleaner imports, but current direct imports are fine.

### `backend/src/graph/nodes.py`

**Role:** Implements LangGraph node functions: video indexing/extraction and compliance auditing.

**Why it matters:** This file contains the core AI pipeline logic.

**Key dependencies/imports:** `AzureChatOpenAI`, `AzureOpenAIEmbeddings`, `AzureSearch`, LangChain messages, `VideoIndexerService`, YouTube transcript fallback helpers, `VideoAuditState`, `ComplianceIssue`, `json`, `re`, `os`, logging.

**Exports/public surface:** `index_video_node`, `audit_content_node`.

**Used by:** `backend/src/graph/workflow.py`, tests.

| Lines/Section | Code Chunk | What It Does | Inputs | Outputs | Side Effects | Notes/Edge Cases |
|---|---|---|---|---|---|---|
| Env/logging setup | Loads `.env` from graph folder and configures logger. | `.env` if present. | Logger/env. | May override env. | Path points to `backend/src/graph/.env`, not repo root. |
| `index_video_node` input parsing | Reads source fields and video ID. | `VideoAuditState`. | Local variables. | None. | Defaults source type to YouTube and ID to `vid_demo`. |
| Upload branch | Checks temp file and calls `upload_video`. | `local_file_path`. | Azure Video ID. | Upload to Video Indexer. | Adds uploaded path to cleanup list. |
| Media URL branch | Calls `upload_video_url`. | URL. | Azure Video ID. | External Azure request. | Requires valid source URL. |
| YouTube branch | Downloads via service then uploads file. | YouTube URL. | Azure Video ID or transcript fallback. | Downloads file and uploads. | Uses fixed local filename `temp_audit_video.mp4`; concurrent YouTube jobs in same cwd could collide. |
| YouTube fallback | Detects blocked download and calls `extract_youtube_transcript`. | Exception/source URL. | Transcript-only state. | External YouTube transcript API. | OCR unavailable in fallback. |
| Processing wait/extract | `wait_for_processing`, `extract_data` | Azure Video ID. | `transcript`, `ocr_text`, metadata. | Polls Azure every 30s. | Long blocking operation. |
| Indexer error handling | Catches all exceptions. | Exception. | Error state with `FAIL`, empty transcript/OCR. | Logs error. | Keeps graph from crashing. |
| Cleanup | Removes paths in `cleanup_paths`. | Local file paths. | None. | Deletes temp/downloaded files. | Only paths defined in local scope. |
| `audit_content_node` no transcript | Guard clause. | State transcript. | `FAIL` final report. | None. | Does not include `errors`, so sync result may be failed but async job may mark completed unless prior errors exist. |
| Azure clients | Creates chat, embeddings, vector store. | Env vars. | Client objects. | Network calls later. | Missing env may fail during client init or call. |
| Retrieval | Combines transcript and OCR, `similarity_search(k=3)`. | Extracted text. | Top docs. | Azure Search query. | Empty OCR joined without separators. |
| Prompt construction | System prompt with rules/instructions and user metadata/text. | Retrieved docs, state. | Messages. | None. | Prompt asks strict JSON. |
| LLM call/parse | `llm.invoke`, optional fenced JSON strip, `json.loads`. | Chat response. | Compliance output. | Azure OpenAI call. | Regex assumes code fence match exists if backticks present. Malformed JSON becomes error. |
| Auditor error handling | Catches exceptions, logs raw response if available. | Exception. | Error state and fail report. | Logs model output. | Raw LLM response may include sensitive content from video/policy. |

**Potential interview talking points:** The pipeline is intentionally decomposed into extraction and audit nodes, making it easy to reason about data boundaries and failures.

**Possible improvements or risks:** Fixed temp YouTube filename; no structured output parser/schema validation; prompt injection risk from transcript/OCR; no retry around Azure calls; imports `ChatPromptTemplate` and `ComplianceIssue` unused.

### `backend/src/graph/state.py`

**Role:** Type definitions for LangGraph state and compliance issues.

**Why it matters:** Documents the data contract between graph nodes and API/job orchestration.

**Key dependencies/imports:** `TypedDict`, `Annotated`, `operator.add`, typing primitives.

**Exports/public surface:** `ComplianceIssue`, `VideoAuditState`.

**Used by:** `nodes.py`, `workflow.py`.

| Lines/Section | Code Chunk | What It Does | Inputs | Outputs | Side Effects | Notes/Edge Cases |
|---|---|---|---|---|---|---|
| `ComplianceIssue` | TypedDict for issue fields. | Category/description/severity/timestamp. | Type contract. | None. | Timestamp optional but not used by API/frontend models. |
| `VideoAuditState` inputs | URL/source fields. | Initial graph invocation. | State keys. | None. | Some initial callers omit newer fields; nodes use defaults. |
| Extraction fields | Metadata, transcript, OCR. | Indexer output. | Auditor input. | None. | Transcript optional but auditor requires it. |
| Analysis/final fields | Results/status/report. | Auditor output. | API result. | None. | `compliance_results` uses additive reducer. |
| Errors | `Annotated[List[str], operator.add]` | Accumulates errors across nodes. | Node error lists. | Final state errors. | None. | Async runner treats any errors as job failure. |

**Potential interview talking points:** State schema makes the graph contract explicit and allows reducer-based accumulation.

**Possible improvements or risks:** Align timestamp field with API/frontend or remove; make optional fields total=False if partial initial states are expected.

### `backend/src/graph/workflow.py`

**Role:** Defines and compiles the LangGraph workflow.

**Why it matters:** It is the orchestration spine: `START -> indexer -> auditor -> END`.

**Key dependencies/imports:** `StateGraph`, `END`, `VideoAuditState`, `index_video_node`, `audit_content_node`.

**Exports/public surface:** `create_graph()`, `app`.

**Used by:** `audit_jobs.py`, `main.py`.

| Lines/Section | Code Chunk | What It Does | Inputs | Outputs | Side Effects | Notes/Edge Cases |
|---|---|---|---|---|---|---|
| Module docstring | Documents DAG. | None. | Human context. | None. | Matches implementation. |
| `create_graph` | Adds nodes, entry point, edges, compiles. | Node functions. | Compiled graph. | None. | Linear graph only. |
| `app = create_graph()` | Exposes runnable graph. | None. | Importable graph app. | Compile at import. | Importing graph imports nodes and service deps. |

**Potential interview talking points:** LangGraph is used for clear workflow composition even though current graph is linear.

**Possible improvements or risks:** Add conditional edge to skip auditor on indexing errors to avoid calling auditor after known failures.

### `backend/src/services/__init__.py`

**Role:** Empty package marker.

**Why it matters:** Makes service modules importable.

**Key dependencies/imports:** None.

**Exports/public surface:** None.

**Used by:** Python import system.

| Section | What It Does | Notes |
|---|---|---|
| Empty | Package marker only. | No runtime behavior. |

**Potential interview talking points:** None.

**Possible improvements or risks:** Could export service classes/helpers for cleaner imports.

### `backend/src/services/video_indexer.py`

**Role:** YouTube/media URL normalization, metadata extraction, download helpers, Azure Video Indexer token/upload/polling, and insight parsing.

**Why it matters:** This is the bridge between user media inputs and text that the compliance graph can audit.

**Key dependencies/imports:** `requests`, `yt_dlp`, `DefaultAzureCredential`, `youtube_transcript_api`, `dotenv`, `urllib.parse`, `Path`, `time`, `re`.

**Exports/public surface:** URL/media helper functions, `VideoIndexerService`.

**Used by:** `server.py`, `nodes.py`, `test_video_indexer.py`.

| Lines/Section | Code Chunk | What It Does | Inputs | Outputs | Side Effects | Notes/Edge Cases |
|---|---|---|---|---|---|---|
| Constants | oEmbed URL, challenge markers, blocked message, headers | Centralizes YouTube behavior and browser-like headers. | None. | Constants. | None. | Smart quotes marker included for bot text. |
| `normalize_youtube_url` | Validates and canonicalizes supported YouTube links. | Raw URL. | `(video_id, canonical_url)`. | None. | Adds `https://` if missing; rejects IDs under 6 chars. |
| `_build_youtube_ydl_options` | Creates yt-dlp options for metadata or download. | Download bool/path. | Options dict. | None. | Uses android/web player clients. |
| Thumbnail/title helpers | `_build_youtube_thumbnail_url`, `_build_display_title` | Generates fallback display data. | IDs/filenames. | Strings. | None. | Replaces underscores/hyphens with spaces. |
| Challenge detection | `_is_youtube_auth_challenge_error`, `is_youtube_download_blocked_error` | Detects bot/auth failures. | Exception/string. | Boolean. | None. | Enables clearer error/fallback. |
| Format helpers | `_is_direct_http_media_format`, `_youtube_format_sort_key` | Filters/sorts progressive formats. | yt-dlp format dict. | Boolean/sort tuple. | None. | Requires audio+video by default. |
| `normalize_media_source_url` | Validates remote media URLs. | Raw URL. | Canonical URL. | None. | Adds `https://` if missing; only http/https. |
| `_fetch_youtube_oembed_metadata` | Calls YouTube oEmbed. | Canonical URL, ID. | Preview metadata. | Network GET. | Raises on missing title/status errors. |
| `extract_media_url_metadata` | Builds preview for remote media. | URL. | Video preview dict. | None. | Title from path/host; no thumbnail. |
| `build_uploaded_file_preview` | Builds preview for upload. | Filename. | Video preview dict. | None. | Uses pseudo URL `uploaded://...`. |
| `extract_youtube_metadata` | Fetches preview via oEmbed, fallback yt-dlp. | YouTube URL. | Video preview dict. | Network GET/yt-dlp. | Bot challenge becomes user-facing `ValueError`. |
| `extract_youtube_transcript` | Uses public transcript API. | YouTube URL. | Transcript-only indexer payload. | Network call. | Fails if no public transcript/empty text. |
| `VideoIndexerService.__init__` | Reads Azure Video Indexer settings and creates credential. | Env vars. | Service instance. | May configure credential chain. | Does not validate missing env upfront. |
| `get_access_token` | Gets ARM token. | DefaultAzureCredential. | Bearer token. | Azure auth call. | Raises/logs on auth failure. |
| `get_account_token` | Exchanges ARM token for VI account token. | ARM token/env IDs. | Access token string. | ARM POST. | Requires Contributor scope per docs/script. |
| `_extract_uploaded_video_id` | Parses VI upload response. | `requests.Response`. | Video ID. | Reads response JSON/text. | Handles plain quoted ID fallback. |
| `resolve_youtube_stream_url` | Finds progressive direct YouTube stream. | YouTube URL. | `(stream_url, extension)`. | yt-dlp metadata call. | Raises blocked message for auth challenge. |
| `download_video_stream` | Streams media to disk. | URL/output path/headers. | Output path. | File write, network GET. | Timeout `(10, 120)`, 1 MiB chunks. |
| `download_youtube_video` | Prefer direct stream, fallback yt-dlp download. | YouTube URL/output path. | Local file path. | Network/file write. | Converts bot challenge to clear blocked message. |
| `upload_video` | Uploads local file to Video Indexer. | File path/name. | Azure video ID. | Opens file, POSTs to Azure. | Private privacy, Default preset. |
| `upload_video_url` | Submits remote URL to Video Indexer. | Media URL/name. | Azure video ID. | Azure POST. | Normalizes URL first. |
| `wait_for_processing` | Polls Video Indexer index endpoint. | Azure video ID. | Raw insights JSON. | Azure GET every 30s. | Infinite until processed/failure/quarantine/error. |
| `extract_data` | Pulls transcript/OCR from VI JSON. | VI JSON. | Graph state fields. | None. | Metadata platform hardcoded `"youtube"` even for upload/media URL. |

**Potential interview talking points:** The service wraps several brittle external integrations and deliberately handles YouTube cloud-blocking with clear errors/fallback.

**Possible improvements or risks:** Infinite polling without max timeout; metadata `platform` hardcoded to YouTube; no file size/content validation; no retry/backoff; no async I/O; local downloads may collide if output path reused.

### `backend/src/worker/__init__.py`

**Role:** Worker package marker with docstring.

**Why it matters:** Separates worker entrypoints from API code.

**Key dependencies/imports:** None.

**Exports/public surface:** None.

**Used by:** Python import system/tests.

| Section | What It Does | Notes |
|---|---|---|
| Docstring | Describes background audit worker package. | No runtime behavior. |

**Potential interview talking points:** Worker is treated as first-class package.

**Possible improvements or risks:** None.

### `backend/src/worker/self_hosted_worker.py`

**Role:** CLI process that polls the shared job store and processes queued self-hosted YouTube jobs.

**Why it matters:** Implements the architecture workaround for Azure-hosted YouTube download blocking.

**Key dependencies/imports:** `argparse`, `logging`, `os`, `socket`, `time`, `dotenv`, audit job functions.

**Exports/public surface:** `get_worker_id`, `process_next_job`, `parse_args`, `ensure_shared_job_store_mode`, `main`.

**Used by:** Manual CLI, tests, README/docs.

| Lines/Section | Code Chunk | What It Does | Inputs | Outputs | Side Effects | Notes/Edge Cases |
|---|---|---|---|---|---|---|
| `load_dotenv` | Loads local env. | `.env` if present. | Env config. | May override. | Good for local worker. |
| `get_worker_id` | Reads env or hostname. | `SELF_HOSTED_WORKER_ID`. | Worker ID. | None. | Hostname can identify machine. |
| `process_next_job` | Claims next `self_hosted` job and runs it. | Optional worker ID. | Boolean processed. | Mutates shared store; calls graph. | Returns false if queue empty. |
| `parse_args` | CLI args. | `--once`, `--poll-seconds`. | Namespace. | None. | Default poll from env or 10. |
| `ensure_shared_job_store_mode` | Verifies store is shared. | Env/store mode. | Store mode. | May set env/reset store. | Auto-switches memory to Blob if storage connection string exists. |
| `main` one-shot | Processes at most one job. | CLI args. | Exit code 0. | Job side effects. | Even if no job, returns 0. |
| `main` loop | Polls forever. | Poll interval. | None until interrupted. | Sleeps between empty polls. | No graceful shutdown handling beyond process termination. |
| `__main__` | `raise SystemExit(main())` | CLI entrypoint. | Process args. | Exit status. | None. | Standard pattern. |

**Potential interview talking points:** The worker uses the same graph as the cloud path, avoiding duplicate audit logic while changing execution location.

**Possible improvements or risks:** Polling loop has no signal handling; no concurrency control per worker beyond one job at a time; no stale job requeue if worker dies.

### `backend/tests/test_api_server.py`

**Role:** Unit tests for FastAPI routes and frontend static serving behavior.

**Why it matters:** Validates API contracts without calling external Azure/YouTube services by using mocks.

**Key dependencies/imports:** `unittest`, `unittest.mock.patch`, `TemporaryDirectory`, `Path`, `fastapi.testclient.TestClient`, `backend.src.api.server`.

**Exports/public surface:** Test helper `build_job`; class `ApiServerTests`.

**Used by:** `python -m unittest discover -s backend/tests`.

| Test/Section | What It Covers | Inputs | Outputs | Notes/Edge Cases |
|---|---|---|---|---|
| `build_job` | Shared fake job payload. | Optional status/result/error. | Dict. | Omits worker fields accepted by response model because extra fields are ignored. |
| `setUpClass` | Creates TestClient. | FastAPI app. | Client. | Imports server and telemetry setup. |
| create YouTube audit | `/audits` returns preview/job ID and starts job. | YouTube JSON. | 202 response. | Ensures execution target default `azure`. |
| create media URL audit | `/audits` with `media_url`. | SAS-like URL. | 202 response. | Ensures media URL target `azure`. |
| self-hosted target | Env var switches YouTube execution target. | Env patch. | 202 response. | Start function still called, but it should skip internally. |
| upload audit | `/audits/upload` multipart. | File bytes. | 202 response. | Mocks save/preview/job. |
| invalid YouTube | Metadata `ValueError`. | Bad URL. | 400. | Job is not created/started. |
| completed payload | `GET /audits/{id}` completed shape. | Mock job. | 200 JSON. | Covers nested result/issue. |
| all statuses | Status route surfaces queued/processing/completed/failed. | Mock sequence. | 200 each. | Polling contract. |
| sync endpoint | `/audit` legacy contract. | Video URL. | 200 response. | Session ID generated. |
| root/static routes | Built frontend index and SPA fallback. | Temp `index.html`. | 200 HTML. | Confirms `resolve_frontend_asset` integration. |

**Potential interview talking points:** Tests isolate external services with mocks and lock down API response shapes.

**Possible improvements or risks:** Add tests for upload extension rejection, frontend-not-built 404, path traversal, and file cleanup on errors.

### `backend/tests/test_audit_jobs.py`

**Role:** Tests async job orchestration and state transitions.

**Why it matters:** Job state correctness is central to the polling UI and worker model.

**Key dependencies/imports:** `unittest`, `patch`, `audit_jobs`, `InMemoryAuditJobStore`.

**Exports/public surface:** `AuditJobsTests`.

**Used by:** Backend unittest discovery.

| Test/Section | What It Covers | Inputs | Outputs | Notes/Edge Cases |
|---|---|---|---|---|
| `setUp`/`tearDown` | Injects in-memory store and resets global store. | Test store. | Isolated tests. | Avoids leakage between tests. |
| completed transition | `_run_audit_job` updates `PROCESSING` then `COMPLETED`. | Mock successful graph state. | Stored result. | Verifies final report/status. |
| failed from graph errors | Errors in graph state produce `FAILED`. | Mock errors list. | Stored error. | Uses first error only. |
| self-hosted skip | `start_audit_job` does not spawn thread for self-hosted. | Job target. | Job remains queued. | Important cloud/local split. |
| claim next job | Claims queued self-hosted job and ignores Azure target. | Two jobs. | Processing job with worker ID. | Verifies oldest/target filtering behavior. |

**Potential interview talking points:** These tests protect the async contract independently from FastAPI.

**Possible improvements or risks:** Add Blob store tests with mocked clients or Azurite; add exception path test for `_execute_audit_job`.

### `backend/tests/test_graph_nodes.py`

**Role:** Tests indexer fallback from blocked YouTube download to public transcript.

**Why it matters:** This is the project’s standout operational workaround.

**Key dependencies/imports:** `unittest`, `MagicMock`, `patch`, `index_video_node`.

**Exports/public surface:** `GraphNodeTests`.

**Used by:** Backend unittest discovery.

| Test/Section | What It Covers | Inputs | Outputs | Notes/Edge Cases |
|---|---|---|---|---|
| fallback test | Mock `download_youtube_video` blocked error and transcript fallback payload. | YouTube state. | Transcript-only result. | Ensures no immediate hard failure on recognized block. |

**Potential interview talking points:** Regression test for the self-host/cloud limitation handling.

**Possible improvements or risks:** Add auditor tests for JSON parsing, malformed JSON, no transcript, retrieval query composition.

### `backend/tests/test_self_hosted_worker.py`

**Role:** Tests self-hosted worker claiming, empty queue behavior, and Blob-mode defaulting.

**Why it matters:** Confirms worker behavior without needing real Azure Blob.

**Key dependencies/imports:** `unittest`, `argparse.Namespace`, `os`, `patch`, `audit_jobs`, `InMemoryAuditJobStore`, `self_hosted_worker`.

**Exports/public surface:** `SelfHostedWorkerTests`.

**Used by:** Backend unittest discovery.

| Test/Section | What It Covers | Inputs | Outputs | Notes/Edge Cases |
|---|---|---|---|---|
| setup/teardown | Isolated in-memory job store. | Test store. | Clean state. | Same pattern as audit jobs tests. |
| process next | Claim and complete self-hosted job. | Mock successful graph. | Completed stored job. | Worker ID preserved. |
| empty queue | Returns false with no jobs. | Empty store. | `False`. | Logs info. |
| default to Blob | Env has storage connection and store starts memory. | Patched mode sequence. | Env set to `azure_blob`, exit 0. | Verifies convenience behavior. |

**Potential interview talking points:** Worker startup tries to avoid a common misconfiguration by switching to Blob when connection string exists.

**Possible improvements or risks:** Add tests for non-shared store exit `1` and polling interval behavior.

### `backend/tests/test_video_indexer.py`

**Role:** Tests YouTube metadata, transcript, and download helper logic.

**Why it matters:** Covers brittle integration-bound code with mocks.

**Key dependencies/imports:** `unittest`, `TemporaryDirectory`, `MagicMock`, `patch`, `requests`, `VideoIndexerService`, metadata/transcript helpers.

**Exports/public surface:** `VideoIndexerMetadataTests`, `VideoIndexerDownloadTests`.

**Used by:** Backend unittest discovery.

| Test/Section | What It Covers | Inputs | Outputs | Notes/Edge Cases |
|---|---|---|---|---|
| oEmbed preferred | Metadata uses YouTube oEmbed and does not call yt-dlp. | Mock response. | Preview metadata. | Fast happy path. |
| yt-dlp fallback | oEmbed failure falls back to yt-dlp metadata. | Mock exception/info. | Preview metadata. | Ensures resilience. |
| transcript payload | Transcript API snippets become indexer payload. | Mock snippets. | Joined transcript and metadata. | No OCR. |
| stream selection | Chooses progressive HTTP format with audio/video. | Mock formats. | URL/ext. | Ignores video-only stream. |
| direct download | Direct stream writes chunks to file and avoids yt-dlp. | Mock response. | File bytes. | Uses temp dir. |
| bot challenge | yt-dlp bot challenge becomes clear blocked error. | Mock exception. | Raises expected message. | Supports fallback detection. |

**Potential interview talking points:** Tests focus on deterministic behavior around external adapters rather than hitting live services.

**Possible improvements or risks:** Add tests for `normalize_youtube_url` variants, media URL validation, upload response ID parsing, Video Indexer polling states.

### `docs/azure-app-service.md`

**Role:** Human guide for Azure App Service deployment.

**Why it matters:** Explains how scripts, runtime assumptions, GitHub OIDC, and self-hosted worker fit together.

**Key dependencies/imports:** Not code; references Azure CLI and scripts.

**Exports/public surface:** Deployment instructions.

**Used by:** Operators/developers deploying the app.

| Section | What It Does | Notes |
|---|---|---|
| Prerequisites | Lists Azure CLI, permissions, existing Azure AI resources. | Runtime resources are assumed, not provisioned by app script except App Service. |
| App Service resources | Shows `bootstrap_app_service.ps1` usage. | Script copies `.env` values to app settings. |
| GitHub OIDC | Shows `create_github_oidc.ps1` usage and secrets to add. | No runtime secrets should go to GitHub. |
| Branch protection | Shows helper script or manual settings. | Requires Test and Build status check. |
| Deployment behavior | PR tests, push deploy. | Matches workflow. |
| Self-hosted worker | Documents shared Blob mode and local worker run command. | Important for YouTube link processing. |
| App Service expectations | Requirements file, startup script, built frontend. | Matches CI artifact. |
| Smoke test | Health/root/browser audit checks. | Manual post-deploy validation. |

**Potential interview talking points:** Deployment docs explicitly separate runtime secrets from deployment identity secrets.

**Possible improvements or risks:** Add rollback instructions, log streaming command, and App Service setting examples with values redacted.

### `frontend/index.html`

**Role:** Vite HTML shell.

**Why it matters:** Provides root element and metadata for the React app.

**Key dependencies/imports:** `/src/main.tsx`.

**Exports/public surface:** HTML document.

**Used by:** Vite dev/build and FastAPI static serving after build.

| Lines/Section | Code Chunk | What It Does | Inputs | Outputs | Side Effects | Notes/Edge Cases |
|---|---|---|---|---|---|---|
| `<head>` | Charset, viewport, description, title. | None. | Browser metadata. | None. | Description/title use "Youtube Add" spelling. |
| `<div id="root">` | React mount point. | DOM. | Root node. | None. | `main.tsx` assumes it exists. |
| module script | Loads `/src/main.tsx`. | Vite dev/build. | App bootstrap. | Network request. | Rewritten by Vite in production build. |

**Potential interview talking points:** Simple Vite shell; app rendering is entirely client-side.

**Possible improvements or risks:** Fix "Add" typo; add favicon/social metadata if productized.

### `frontend/package-lock.json`

**Role:** npm lockfile for deterministic frontend installs.

**Why it matters:** CI uses `npm ci --prefix frontend`, which requires this lockfile.

**Key dependencies/imports:** Locks React, Vite, Vitest, Testing Library, React Query, React Markdown and transitive packages.

**Exports/public surface:** Dependency graph.

**Used by:** npm.

| Section | What It Does | Notes |
|---|---|---|
| Root package | Mirrors `frontend/package.json` dependencies/devDependencies. | Name is `youtube-add-compliance-checker-frontend`. |
| `packages` graph | Pins resolved package versions/integrities. | Generated/vendor-style file; detailed line-by-line analysis is not applicable. |

**Potential interview talking points:** Lockfiles make CI builds reproducible.

**Possible improvements or risks:** Keep lockfile updated with package changes; use dependency scanning.

### `frontend/package.json`

**Role:** Frontend package metadata, scripts, and dependencies.

**Why it matters:** Defines how to run/build/test the React app.

**Key dependencies/imports:** React 19, React DOM, React Query, React Markdown; dev deps for Vite, TypeScript, Vitest, Testing Library, jsdom.

**Exports/public surface:** npm scripts.

**Used by:** Developers and CI.

| Section | Code Chunk | What It Does | Inputs | Outputs | Side Effects | Notes/Edge Cases |
|---|---|---|---|---|---|---|
| Metadata | name/private/version/type | Defines private ESM package. | None. | npm metadata. | None. | Name has "add" typo. |
| `dev` | `vite` | Starts dev server. | Source files. | Local server. | Watches files. | Port configured in Vite. |
| `build` | `tsc -b && vite build` | Type-checks then builds. | TS/React source. | `dist`. | Writes build output. | CI relies on it. |
| `preview` | `vite preview` | Serves built app locally. | `dist`. | Preview server. | None. | Useful after build. |
| `test` | `vitest run` | Runs frontend tests once. | Test files. | Test results. | None. | Non-watch mode for CI. |
| Dependencies | Runtime packages. | App code. | Bundle deps. | Install/download. | React Query for polling; Markdown rendering for final report. |
| Dev deps | Tooling/test packages. | Build/test. | Tooling deps. | Install/download. | Node 20 expected by some transitive packages. |

**Potential interview talking points:** React Query is used for job polling/cache; React Markdown renders model-generated reports.

**Possible improvements or risks:** Add lint/format scripts; consider sanitization policy for markdown if raw HTML plugins are ever enabled.

### `frontend/src/App.test.tsx`

**Role:** Tests the current React UI behavior.

**Why it matters:** Confirms the checked-in UI is upload-only and submits multipart jobs correctly.

**Key dependencies/imports:** React Query provider, Testing Library, user-event, Vitest, `App`.

**Exports/public surface:** Test suite `App`.

**Used by:** `npm run test`.

| Test/Section | What It Covers | Inputs | Outputs | Notes/Edge Cases |
|---|---|---|---|---|
| `renderApp` | Wraps App in QueryClientProvider with retries disabled. | Component. | Render result. | Mirrors production provider enough for tests. |
| `jsonResponse` | Creates mocked fetch responses. | Body/status. | Response object. | Simplifies fetch tests. |
| `afterEach` | Restores mocks/globals. | Vitest state. | Clean tests. | Prevents fetch leaks. |
| upload-only render | Hero/copy/file input/GitHub link/no URL buttons/disabled submit. | No fetch calls. | DOM assertions. | Explicitly protects current upload-only UX. |
| multipart submit | Upload file and click run audit. | File object, mocked 202. | Preview/result DOM, fetch assertions. | Ensures `/audits/upload` and FormData. |
| failed state | Queued response then failed poll response. | Mock fetch sequence. | Error/status DOM. | Verifies polling renders failure. |
| disabled submit | No file selected. | Initial render. | Disabled button. | Basic validation. |

**Potential interview talking points:** UI tests double as living documentation that upload is the only visible mode right now.

**Possible improvements or risks:** Add tests for polling stop on completed, markdown rendering, API error message from upload creation, invalid file UX.

### `frontend/src/App.tsx`

**Role:** Main React application UI and interaction logic.

**Why it matters:** This is the user-facing product surface.

**Key dependencies/imports:** React state/types, React Query, React Markdown, API client, TypeScript types.

**Exports/public surface:** Default component `App`; internal components/helpers.

**Used by:** `frontend/src/main.tsx`, tests.

| Lines/Section | Code Chunk | What It Does | Inputs | Outputs | Side Effects | Notes/Edge Cases |
|---|---|---|---|---|---|---|
| Constants | `TERMINAL_STATUSES`, `JOB_STATUS_COPY`, `UPLOAD_COPY` | Centralizes status labels/details and upload copy. | Job status. | UI text/tone. | None. | Status tone drives badge/orbit classes. |
| App state | `uploadFile`, `formError`, `activeAuditId`, `seedAudit` | Tracks form and current audit. | User actions/API result. | Render state. | None. | `seedAudit` gives immediate UI before first poll. |
| Mutation | `useMutation(createUploadAudit)` | Starts upload audit and seeds cache. | File. | Audit job. | Network POST; React Query cache update. | On error clears active audit. |
| Query | `useQuery(getAudit)` | Polls current audit every 3s until terminal. | `activeAuditId`. | Latest job. | Network GET. | `initialData` from seed avoids blank gap. |
| Derived values | `audit`, status copy, issues, `canSubmit` | Computes render-friendly data. | Query/mutation state. | UI values. | None. | Defaults status to `QUEUED` before audit. |
| `resetPendingAudit` | Clears existing audit. | None. | State reset. | State mutation. | Called before new run. |
| `handleSubmit` | Validates file and starts mutation. | Form event. | None. | Prevents default, network via mutation. | Empty file sets form error. |
| `handleUploadChange` | Stores selected file. | Input event. | None. | State mutation. | Clears existing form error. |
| Hero/form render | Upload form UI. | State. | DOM. | File picker. | `accept` mirrors backend extensions plus `video/*`. |
| Preview panel | Shows thumbnail/fallback, title, URL or upload note. | Audit video. | DOM. | External link if URL is http(s). | Uploaded pseudo URL is not linked. |
| Status panel | Shows job progress, audit ID, timestamp, error. | Audit job. | DOM. | None. | `formatTimestamp` localizes. |
| Results panel | Shows issues or empty/failure placeholders. | Audit result/status. | DOM. | None. | `Compliance UNKNOWN` would be tone neutral if ever returned. |
| Report panel | Renders final report through `ReactMarkdown`. | Report string. | Markdown DOM. | None. | No raw HTML plugin configured. |
| Footer | GitHub link. | Static URL. | Link. | Navigation. | URL points to repo. |
| `PreviewArtwork` | Thumbnail or fallback block. | Video preview. | DOM. | Image load if thumbnail. | Alt text uses video title. |
| `StatusBadge` | Tone-based badge. | Children/tone. | Span. | None. | CSS class contract. |
| `IssueCard` | Issue category/description/severity. | Issue. | Article. | None. | Key generated by category/severity/index. |
| `EmptyPanel` | Placeholder content. | Title/description. | DOM. | None. | Reused across panels. |
| Helpers | source label, external URL, severity/compliance tone, timestamp formatting | Strings/statuses. | Display values. | None. | Unknown severities neutral; invalid timestamps returned as-is. |

**Potential interview talking points:** React Query makes async polling simple and keeps cache state synchronized with job lifecycle.

**Possible improvements or risks:** Visible UI omits backend URL modes; ambient decorative elements and large cards are a design choice; no client-side file extension/size validation beyond accept attribute; no accessible progress semantics beyond text.

### `frontend/src/api.ts`

**Role:** Frontend API client and error wrapper.

**Why it matters:** Centralizes fetch behavior, JSON parsing, error extraction, and endpoint functions.

**Key dependencies/imports:** `AuditJobResponse` type, `import.meta.env.VITE_API_BASE_URL`, browser `fetch`.

**Exports/public surface:** `createUrlAudit`, `createUploadAudit`, `getAudit`, `ApiError`.

**Used by:** `App.tsx`; URL audit function is currently unused by UI.

| Lines/Section | Code Chunk | What It Does | Inputs | Outputs | Side Effects | Notes/Edge Cases |
|---|---|---|---|---|---|---|
| `API_BASE_URL` | Reads optional Vite env var. | Env. | Base URL string. | None. | Empty string uses same origin/proxy. |
| `ApiError` | Error with HTTP status. | Message/status. | Error instance. | None. | Exported for callers/tests if needed. |
| `fetchJson` headers | Adds JSON content type unless body is FormData. | Path/init. | Headers. | None. | Correctly lets browser set multipart boundary. |
| `fetchJson` request | Calls fetch and parses JSON. | URL/init. | Typed JSON. | Network request. | Throws `ApiError` on non-OK. |
| Error parsing | Reads `{detail}` from response JSON. | Error response. | Message. | Consumes body. | Falls back to status text. |
| `createUrlAudit` | POST `/audits`. | `sourceType`, `sourceUrl`. | Job response. | Network POST. | Currently unused in visible UI. |
| `createUploadAudit` | POST `/audits/upload` with FormData. | File. | Job response. | Network POST. | Used by current UI. |
| `getAudit` | GET job status. | Audit ID. | Job response. | Network GET. | Used by polling query. |

**Potential interview talking points:** The FormData content-type handling avoids a common multipart bug.

**Possible improvements or risks:** Add request timeout/abort handling; use schema validation for API responses.

### `frontend/src/main.tsx`

**Role:** React bootstrap.

**Why it matters:** Mounts the app and configures React Query defaults.

**Key dependencies/imports:** React StrictMode, React DOM `createRoot`, React Query, `App`, CSS.

**Exports/public surface:** None.

**Used by:** Vite HTML script.

| Lines/Section | Code Chunk | What It Does | Inputs | Outputs | Side Effects | Notes/Edge Cases |
|---|---|---|---|---|---|---|
| QueryClient | Disables refetch on focus, sets query retry 1, mutation retry false. | None. | Client. | None. | Affects all queries/mutations. |
| `createRoot(...).render` | Mounts App inside StrictMode and QueryClientProvider. | DOM `#root`. | React app. | DOM render. | Non-null assertion assumes root exists. |
| CSS import | Loads app styles. | `styles.css`. | Bundled CSS. | None. | Global styles. |

**Potential interview talking points:** Query defaults are conservative for polling UI; mutations avoid duplicate upload retries.

**Possible improvements or risks:** Add error boundary; guard missing root for clearer failure.

### `frontend/src/styles.css`

**Role:** Global frontend styling.

**Why it matters:** Defines the visual product experience, layout, responsive behavior, animations, and component classes used by `App.tsx`.

**Key dependencies/imports:** Google Fonts import, CSS variables/classes matching App component class names.

**Exports/public surface:** CSS classes and keyframes.

**Used by:** `main.tsx` import, all rendered UI components.

| Section | Code Chunk | What It Does | Inputs | Outputs | Side Effects | Notes/Edge Cases |
|---|---|---|---|---|---|---|
| Font import | Space Grotesk and IBM Plex Sans | Loads web fonts. | Google Fonts network. | Font faces. | External request. | If blocked, falls back to system fonts. |
| `:root` | Color scheme, font stack, gradients, CSS vars. | Browser CSS. | Global theme. | Affects page. | Warm palette with teal/orange/red variables. |
| Resets | `*`, `html/body/#root`, `button/input` | Box sizing, min height, font inheritance. | DOM. | Baseline styles. | None. | Ensures full-height shell. |
| Shell/ambient/app | Page background, decorative blurred circles, max width/padding. | DOM classes. | Layout. | Visual decoration. | Uses absolute ambient elements. |
| Panels/hero/form | Card-like surfaces, hero typography, audit form, inputs, buttons. | App class names. | Styled UI controls. | Transitions/hover. | Contains unused URL/source-toggle styles from previous UI modes. |
| Workspace/results | Grid layouts for preview/status/findings/report. | Viewport width. | Responsive columns. | None. | Media query collapses under 980px. |
| Video/status/issues/report | Thumbnail fallback, badges, status orbit animation, issue cards, markdown block. | Job/result data classes. | Visual state. | Animation on status orbit. | Reduced motion disables animations. |
| Empty/footer | Placeholder panels and footer link. | App class names. | Styled placeholders/footer. | None. | Empty panels have min height. |
| Keyframes | `rise-in`, `pulse-ring` | Entrance/pulse animations. | CSS animation. | Motion. | Disabled under `prefers-reduced-motion`. |
| Media queries | `max-width: 980px`, reduced motion. | Viewport/user preference. | Responsive/reduced animation. | None. | Good accessibility nod for motion. |

**Potential interview talking points:** Styling includes responsive layout and reduced-motion support; unused URL-mode classes show product evolution.

**Possible improvements or risks:** External font dependency; no dark mode; cards and decorative backgrounds may not suit dense operational tooling if productized.

### `frontend/src/test/setup.ts`

**Role:** Vitest/Testing Library setup.

**Why it matters:** Adds jest-dom matchers and cleans rendered DOM after each test.

**Key dependencies/imports:** `@testing-library/jest-dom/vitest`, `cleanup`, Vitest `afterEach`.

**Exports/public surface:** None.

**Used by:** `vite.config.ts` test setup.

| Lines/Section | Code Chunk | What It Does | Inputs | Outputs | Side Effects | Notes/Edge Cases |
|---|---|---|---|---|---|---|
| jest-dom import | Adds DOM matchers. | Vitest environment. | Matchers like `toBeInTheDocument`. | Mutates expect. | Required by App tests. |
| cleanup afterEach | Unmounts Testing Library renders. | Rendered DOM. | Clean DOM. | DOM cleanup. | Prevents test contamination. |

**Potential interview talking points:** Basic test hygiene.

**Possible improvements or risks:** None obvious.

### `frontend/src/types.ts`

**Role:** TypeScript representation of backend API response shapes.

**Why it matters:** Keeps frontend rendering strongly typed against expected API contracts.

**Key dependencies/imports:** None.

**Exports/public surface:** `JobStatus`, `ComplianceStatus`, `AuditSourceType`, `ComplianceIssue`, `AuditVideoPreview`, `AuditJobResult`, `AuditJobResponse`.

**Used by:** `App.tsx`, `api.ts`.

| Section | What It Does | Inputs | Outputs | Notes/Edge Cases |
|---|---|---|---|---|
| Union types | Enumerates job/compliance/source states. | API strings. | Compile-time safety. | Must stay aligned with backend. |
| Interfaces | Define issue, video, result, job. | API JSON. | Typed objects. | `result` and `error` nullable like backend response. |

**Potential interview talking points:** The frontend mirrors API models enough to reduce accidental UI mistakes.

**Possible improvements or risks:** Generate types from OpenAPI or share schema to avoid drift.

### `frontend/src/utils/media.ts`

**Role:** Client-side remote media URL validation utility.

**Why it matters:** Supports a URL mode that backend and API client can handle, even though current `App.tsx` does not expose it.

**Key dependencies/imports:** Browser `URL` class.

**Exports/public surface:** `MediaUrlValidationResult`, `validateRemoteMediaUrl`.

**Used by:** No current tracked imports found in `App.tsx`; likely retained for future/previous URL UI.

| Lines/Section | Code Chunk | What It Does | Inputs | Outputs | Side Effects | Notes/Edge Cases |
|---|---|---|---|---|---|---|
| Interface | Result shape. | None. | Type contract. | None. | Includes normalized URL and host. |
| Empty input | Returns invalid with helper error. | Raw string. | Invalid result. | None. | Error text mentions direct media/SAS URL. |
| Protocol normalization | Adds `https://` if scheme missing. | Trimmed input. | Candidate URL. | None. | Mirrors backend media normalization. |
| URL parse | Uses `new URL`. | Candidate. | Parsed URL or invalid. | None. | Catches parse failure. |
| Scheme/host validation | Allows only `http:`/`https:`. | Parsed URL. | Valid/invalid result. | None. | Does not validate file extension or reachability. |

**Potential interview talking points:** Frontend validation mirrors backend enough to give faster feedback when URL mode returns.

**Possible improvements or risks:** Currently unused; add tests or remove until UI supports remote URLs.

### `frontend/src/utils/youtube.ts`

**Role:** Client-side YouTube URL validation/canonicalization.

**Why it matters:** Encodes supported YouTube URL shapes and canonical output for URL audit mode.

**Key dependencies/imports:** Browser `URL` class.

**Exports/public surface:** `YouTubeValidationResult`, `validateYouTubeUrl`.

**Used by:** No current tracked imports found in `App.tsx`; likely retained for future/previous URL UI.

| Lines/Section | Code Chunk | What It Does | Inputs | Outputs | Side Effects | Notes/Edge Cases |
|---|---|---|---|---|---|---|
| `VIDEO_ID_PATTERN` | Validates ID characters/length. | Video ID. | Boolean. | None. | Same broad pattern as backend. |
| Interface | Result shape. | None. | Type contract. | None. | Includes canonical URL and video ID. |
| Empty/parse handling | Returns helpful invalid messages. | Raw input. | Invalid result. | None. | Adds `https://` if no scheme. |
| Host/path parsing | Supports youtu.be, watch, shorts, embed, live. | Parsed URL. | Video ID. | None. | Mirrors backend accepted forms. |
| Canonical result | Returns `https://www.youtube.com/watch?v=<id>`. | Valid ID. | Valid result. | None. | Strips extra query/path context. |

**Potential interview talking points:** Shared validation semantics across frontend/backend reduce mismatched expectations.

**Possible improvements or risks:** Currently unused; add tests before exposing URL mode.

### `frontend/src/vite-env.d.ts`

**Role:** Vite and environment type declarations.

**Why it matters:** Lets TypeScript understand `import.meta.env.VITE_API_BASE_URL`.

**Key dependencies/imports:** Vite client types.

**Exports/public surface:** Global `ImportMetaEnv`, `ImportMeta`.

**Used by:** `frontend/src/api.ts`, TypeScript compiler.

| Section | What It Does | Notes |
|---|---|---|
| Vite reference | Loads Vite client typing. | Standard Vite pattern. |
| `VITE_API_BASE_URL` | Optional string env type. | Keeps API client typed. |

**Potential interview talking points:** Strong typing of runtime config.

**Possible improvements or risks:** Add any future `VITE_*` vars here.

### `frontend/tsconfig.app.json`

**Role:** TypeScript compiler config for app source.

**Why it matters:** Enforces strict typing and modern TS/DOM target.

**Key dependencies/imports:** TypeScript.

**Exports/public surface:** Compiler options.

**Used by:** `tsc -b`, Vite/IDE.

| Setting/Section | What It Controls | Notes |
|---|---|---|
| `target`, `lib` | ES2022 and DOM APIs. | Modern browser target. |
| `allowJs: false` | TS-only source. | No JS app files. |
| `strict: true` | Strict type checking. | Good maintainability. |
| `moduleResolution: Bundler` | Vite-style module resolution. | Standard for Vite TS apps. |
| `jsx: react-jsx` | React 17+ JSX transform. | No explicit React import needed for JSX. |
| `include: ["src"]` | App source scope. | Excludes config files. |

**Potential interview talking points:** Strict TS helps keep API/result rendering safer.

**Possible improvements or risks:** Add `noUnusedLocals`/`noUnusedParameters` if desired.

### `frontend/tsconfig.json`

**Role:** Root TypeScript project references.

**Why it matters:** Lets `tsc -b` build app and node config projects.

**Key dependencies/imports:** `tsconfig.app.json`, `tsconfig.node.json`.

**Exports/public surface:** TS project graph.

**Used by:** `npm run build`.

| Section | What It Does | Notes |
|---|---|---|
| `files: []` | No direct files in root config. | Reference-only root. |
| `references` | Points to app and node configs. | Standard Vite TS setup. |

**Potential interview talking points:** TS build is split between app and tooling config.

**Possible improvements or risks:** None.

### `frontend/tsconfig.node.json`

**Role:** TypeScript config for Node-side tooling files.

**Why it matters:** Type-checks `vite.config.ts`.

**Key dependencies/imports:** TypeScript.

**Exports/public surface:** Compiler options for tooling.

**Used by:** `tsc -b`.

| Setting/Section | What It Controls | Notes |
|---|---|---|
| `composite: true` | Allows project references. | Required for build mode. |
| `moduleResolution: Bundler` | Bundler-style imports. | Matches Vite. |
| `include: ["vite.config.ts"]` | Limits scope. | Only config file. |

**Potential interview talking points:** Keeps app TS and tooling TS separated.

**Possible improvements or risks:** None.

### `frontend/vite.config.ts`

**Role:** Vite dev server and Vitest configuration.

**Why it matters:** Connects frontend dev server to backend and sets up frontend tests.

**Key dependencies/imports:** `@vitejs/plugin-react`, `defineConfig` from `vitest/config`.

**Exports/public surface:** Default Vite config.

**Used by:** Vite, Vitest.

| Lines/Section | Code Chunk | What It Does | Inputs | Outputs | Side Effects | Notes/Edge Cases |
|---|---|---|---|---|---|---|
| Plugins | `react()` | Enables React transform/Fast Refresh. | TSX source. | Vite plugin. | None. | Standard. |
| Server | port `5173`, proxies `/audit`, `/audits`, `/health` | Dev API integration. | Browser requests. | Proxied backend calls. | Network proxy. | `/audits` also covers `/audits/upload` and `/audits/{id}`. |
| Test | jsdom, setup file, css true | Vitest environment. | Test files. | DOM-like tests. | None. | CSS imports allowed in tests. |

**Potential interview talking points:** Dev proxy keeps frontend code same-origin by default without hardcoding backend URL.

**Possible improvements or risks:** Make proxy target configurable if backend port changes.

### `main.py`

**Role:** Legacy/direct CLI-style workflow runner.

**Why it matters:** Useful for manual graph invocation and demonstrates original non-API execution path.

**Key dependencies/imports:** `uuid`, `json`, `logging`, `pprint` (unused), `dotenv`, graph `app`.

**Exports/public surface:** `run_cli_simulation()`.

**Used by:** Manual `python main.py`; not used by FastAPI.

| Lines/Section | Code Chunk | What It Does | Inputs | Outputs | Side Effects | Notes/Edge Cases |
|---|---|---|---|---|---|---|
| Imports/env/logging | Loads env, imports graph app, configures logger. | `.env`, graph deps. | Runtime setup. | May initialize Azure-related clients later. | `pprint` is unused. |
| `run_cli_simulation` session | Generates UUID and initial inputs. | None. | Initial LangGraph state. | Logs/prints. | Hardcoded YouTube URL. |
| Graph invocation | `app.invoke(initial_inputs)` | Initial state. | Final graph state. | Calls external services through graph. | Omits `source_type`, `source_url`, `local_file_path`, relying on defaults. |
| Report printing | Prints ID/status/issues/final report. | Final state. | Console output. | stdout. | Output is human-readable, not JSON. |
| Error handling | Logs and re-raises. | Exception. | Process error. | Logs. | No custom exit code. |
| `__main__` | Calls runner. | CLI. | Console audit. | External services. | Developer harness. |

**Potential interview talking points:** Shows evolution from a direct graph runner to a full async API/UI.

**Possible improvements or risks:** Parameterize URL; remove unused import; align initial state with full `VideoAuditState`.

### `pyproject.toml`

**Role:** Python project metadata and dependency specification for `uv`.

**Why it matters:** Defines Python requirement and broad dependency set for local development.

**Key dependencies/imports:** Azure SDKs, FastAPI, LangChain/LangGraph, OpenAI, Video/YouTube tooling, deployment/runtime libs.

**Exports/public surface:** Project package `complianceqapipeline`.

**Used by:** `uv sync`, Python packaging tools.

| Setting/Section | What It Controls | Notes |
|---|---|---|
| `[project].name` | `complianceqapipeline`. | Different from README product name. |
| `version` | `0.1.0`. | MVP/demo version. |
| `requires-python` | `>=3.12`. | Matches `.python-version` and CI. |
| dependencies | Runtime dependency ranges/pins. | Includes used packages plus unused/drift packages such as Redis/SQLAlchemy/Streamlit/Firecrawl/pandas. |

**Potential interview talking points:** The dependency file reflects experimentation plus deployed app needs; pruning unused deps is a maintenance step.

**Possible improvements or risks:** Add accurate description; reconcile dependency versions with `requirements.txt`; remove unused dependencies.

### `requirements.txt`

**Role:** Pinned Python dependency list for CI and App Service packaging.

**Why it matters:** GitHub Actions and Azure deployment install from this file.

**Key dependencies/imports:** Pin set includes FastAPI, Azure packages, LangChain, LangGraph, OpenAI, yt-dlp, youtube-transcript-api, telemetry, Gunicorn/Uvicorn, and many transitive deps.

**Exports/public surface:** Exact package pins.

**Used by:** CI backend install and deployment vendoring.

| Section | What It Does | Notes |
|---|---|---|
| Pinned package list | Provides reproducible pip install set. | Generated/lock-style file; detailed line-by-line package internals are not applicable. |
| Runtime packages | Includes app-required libs. | `fastapi`, `azure-*`, `langchain-*`, `yt-dlp`, `youtube-transcript-api`, `gunicorn`, `uvicorn`. |
| Extra packages | Includes packages not referenced by current source. | `redis`, `sqlalchemy`, `psycopg2-binary`, `streamlit`, `firecrawl-py`, `pandas` appear unused by tracked code. |

**Potential interview talking points:** Deployment uses pip pins even though local development has a uv lock.

**Possible improvements or risks:** Dependency drift between `pyproject.toml`, `uv.lock`, and `requirements.txt`.

### `scripts/azure/bootstrap_app_service.ps1`

**Role:** Provisions/configures Azure App Service resources and app settings.

**Why it matters:** Operationalizes the deployment described in docs.

**Key dependencies/imports:** Azure CLI, PowerShell, local `.env`.

**Exports/public surface:** Script parameters and functions.

**Used by:** Manual Azure setup.

| Lines/Section | Code Chunk | What It Does | Inputs | Outputs | Side Effects | Notes/Edge Cases |
|---|---|---|---|---|---|---|
| Parameters | Subscription, web app, resource names, location, runtime, env path, VI overrides | Deployment config. | Script variables. | None. | Defaults to Australia East/F1/Python 3.12. |
| `Assert-AzureCli` | Finds Azure CLI executable or Azure CLI Python module path. | Local machine. | `$AzCliExecutable`. | None. | Windows-friendly path check. |
| `Invoke-Az`, `Invoke-AzCapture` | Runs Azure CLI with error checks. | CLI args. | Output or exception. | External Azure calls. | Throws on nonzero exit. |
| `Parse-DotEnv` | Reads `.env` into app setting strings. | Env file path. | List `KEY=value`. | Reads secrets. | Does not print values directly except later appsettings command receives them. |
| Env map/defaults | Derives VI resource info and adds app settings. | Parsed env. | App setting list. | None. | Defaults job store to Blob and YouTube target to self-hosted. |
| CORS override | Replaces `FRONTEND_ORIGINS` with deployed web app origin. | Web app name. | App setting. | None. | Single deployed origin. |
| Resource group/plan/webapp | `az group`, `appservice plan`, `webapp create`. | Azure subscription. | Resources. | Creates/updates Azure resources. | Uses F1 Linux plan. |
| Managed identity/startup/settings | Assigns identity, sets `bash startup.sh`, app settings. | Web app. | Configured app. | Writes Azure settings, including secrets from `.env`. | Requires care with local `.env`. |
| VI role assignment | Assigns Contributor on Video Indexer account to app identity. | VI resource info. | Role assignment. | Azure RBAC write. | Skips with warning if missing info. |
| Final output | Prints app URL. | Web app name. | Console info. | None. | Does not run smoke test. |

**Potential interview talking points:** Script uses managed identity for Video Indexer ARM token flow and keeps GitHub runtime secrets out of repo.

**Possible improvements or risks:** Copies all `.env` values to App Service; add allowlist/redaction output; add idempotency checks around role assignment failures; add storage resource creation if required.

### `scripts/azure/create_github_oidc.ps1`

**Role:** Creates/reuses Microsoft Entra app/service principal and GitHub federated credentials for Azure deploys.

**Why it matters:** Enables secretless GitHub Actions login to Azure using OIDC.

**Key dependencies/imports:** Azure CLI, PowerShell JSON conversion.

**Exports/public surface:** Script parameters.

**Used by:** Manual deployment identity setup.

| Lines/Section | Code Chunk | What It Does | Inputs | Outputs | Side Effects | Notes/Edge Cases |
|---|---|---|---|---|---|---|
| Parameters | Subscription, resource group, repo owner/name, web app, branch, environment, app name | Deployment identity config. | Variables. | None. | Defaults branch `main`, environment `production`. |
| Azure CLI helpers | Finds/runs Azure CLI. | Local machine. | CLI output. | External Azure calls. | Similar to bootstrap script. |
| Tenant/app lookup | Reads tenant and existing Entra app by display name. | Subscription/app name. | Tenant ID/app ID. | Azure queries. | Reuses existing app if found. |
| Service principal | Creates SP if missing. | App ID. | SP object ID. | Azure AD write. | Handles not found with try/catch. |
| Role assignment | Contributor on resource group. | SP object ID/scope. | Role assignment. | Azure RBAC write. | Checks existing first. |
| Federated credentials | Creates branch and environment subjects. | Repo/branch/env. | OIDC credentials. | Writes temp JSON file then deletes it. | Uses `$env:TEMP`; secrets are not written, but app metadata is. |
| Final output | Prints GitHub secret names/values to add. | IDs/web app name. | Console instructions. | None. | Printed values are deployment identifiers, not runtime API keys. |

**Potential interview talking points:** OIDC is safer than storing Azure client secrets in GitHub.

**Possible improvements or risks:** Temp credential file deletion uses best-effort; add `finally` cleanup; scope Contributor could be narrowed.

### `scripts/github/set-main-branch-protection.ps1`

**Role:** Configures branch protection through GitHub REST API.

**Why it matters:** Enforces PR/status-check workflow around `main`.

**Key dependencies/imports:** PowerShell `Invoke-RestMethod`, GitHub token passed as parameter.

**Exports/public surface:** Script parameters.

**Used by:** Manual repo governance setup.

| Lines/Section | Code Chunk | What It Does | Inputs | Outputs | Side Effects | Notes/Edge Cases |
|---|---|---|---|---|---|---|
| Parameters | Token, owner, repo, branch, required check. | GitHub PAT/config. | Variables. | None. | `GitHubToken` is sensitive and should not be logged. |
| Headers | Authorization and API version. | Token. | REST headers. | None. | Token value stays in memory. |
| Body | Branch protection JSON. | Required check. | JSON body. | None. | Requires status check `Test and Build`; approving review count 0. |
| REST call | PUT branch protection endpoint. | URI/body/headers. | Updated branch protection. | GitHub API write. | Needs admin-capable token. |
| Final output | Prints success message. | Repo/branch. | Console info. | None. | No response details retained. |

**Potential interview talking points:** Branch protection ties CI to review discipline.

**Possible improvements or risks:** Required approving reviews set to 0; decide whether production repo should require approvals/conversation resolution.

### `startup.sh`

**Role:** Azure App Service startup script.

**Why it matters:** Starts FastAPI under Gunicorn/Uvicorn and wires vendored packages into `PYTHONPATH`.

**Key dependencies/imports:** Shell, Gunicorn, Uvicorn worker.

**Exports/public surface:** Process startup command.

**Used by:** Azure App Service `startup-file "bash startup.sh"`.

| Lines/Section | Code Chunk | What It Does | Inputs | Outputs | Side Effects | Notes/Edge Cases |
|---|---|---|---|---|---|---|
| Shebang/strict | `#!/usr/bin/env sh`, `set -eu` | POSIX shell and fail-fast. | Env. | Process behavior. | Exits on unset/error. | `.gitattributes` keeps LF. |
| `cd /home/site/wwwroot` | Moves to App Service content root. | App Service filesystem. | CWD. | Directory change. | Azure-specific. |
| `PYTHONPATH` | Prepends vendored `python_packages`. | Existing PYTHONPATH. | Runtime import path. | Env mutation. | Matches CI vendoring path. |
| `exec gunicorn` | Runs app on `0.0.0.0:${PORT:-8000}`. | `PORT`, `GUNICORN_TIMEOUT`, `GUNICORN_WORKERS`. | Web process. | Replaces shell. | Default timeout 600, workers 1. |

**Potential interview talking points:** App Service-friendly startup with vendored dependencies and Uvicorn worker class.

**Possible improvements or risks:** One worker by default limits concurrency; no preload/log config; assumes Azure path.

### `uv.lock`

**Role:** uv lockfile for Python dependency resolution.

**Why it matters:** Supports reproducible local installs through `uv sync`.

**Key dependencies/imports:** Locked packages and hashes from Python package indexes.

**Exports/public surface:** Dependency lock graph.

**Used by:** `uv`.

| Section | What It Does | Notes |
|---|---|---|
| Header | Lock version/revision and `requires-python >=3.12`. | Aligns with project. |
| Package entries | Pin versions, sources, hashes, wheels. | Generated/lock-style file; detailed package internals are not applicable. |

**Potential interview talking points:** Repo has both uv and pip deployment paths.

**Possible improvements or risks:** Keep `requirements.txt` generated from the same source as `uv.lock` to avoid drift.

## 11. Cross-Cutting Concerns

### Security and Secrets

- `.env` is ignored, and no tracked `.env` values were found.
- Azure/OpenAI/Search/Storage keys are environment variables only.
- `bootstrap_app_service.ps1` copies all parsed `.env` settings into App Service app settings. This is convenient but should be handled carefully because it may include secrets beyond app needs.
- `scripts/github/set-main-branch-protection.ps1` accepts `GitHubToken` as a parameter; the markdown does not contain a token value.
- No user authentication, authorization, CSRF protection, or rate limiting exists in the app code.
- Uploads validate extension but not content type, size, malware, duration, or quota.
- `ReactMarkdown` is used without raw HTML plugins, which is safer than rendering arbitrary HTML, but model-generated markdown is still untrusted content from an output perspective.
- Prompt injection is possible because transcript/OCR text is inserted directly into the LLM prompt alongside instructions.

### Error Handling

- API routes convert expected validation errors to `400` and missing jobs to `404`.
- Workflow exceptions inside nodes become `errors` in graph state.
- `_execute_audit_job` marks jobs failed on errors or exceptions.
- Blob update conflicts retry five times.
- External service calls often raise generic `Exception`, which is simple but makes typed handling harder.

### Logging and Observability

- Python logging is present in API, job store, nodes, service, worker, and indexing script.
- Azure Monitor can be enabled through `APPLICATIONINSIGHTS_CONNECTION_STRING`.
- Health endpoint is shallow and does not check Azure Search/OpenAI/Video Indexer/Blob connectivity.
- No frontend monitoring is visible.

### Testing Strategy

- Backend tests mock external calls and validate unit-level behavior.
- Frontend tests mock `fetch` and validate visible UI behavior.
- No integration tests against live or emulator Azure services.
- No tests for document indexing script.
- No tests for Blob store concurrency are visible.

### Performance

- Video processing is long-running and blocking; API-process jobs use daemon threads.
- `wait_for_processing` sleeps 30 seconds between polls indefinitely.
- Blob store polling lists blobs each time, which is fine for an MVP but not for high volume.
- React polls every 3 seconds while jobs are active.
- Azure Search retrieves only top 3 chunks, which is cheap but may miss relevant policy context.

### Scalability

- In-memory store is single-process only.
- Blob store enables shared state but is not a full queue.
- Gunicorn defaults to one worker in `startup.sh`.
- No backpressure, quotas, job cancellation, or worker concurrency controls are present.

### Accessibility

- The UI uses labels for file input, alt text for thumbnails, semantic sections/headings, and reduced-motion CSS.
- Status changes are visible textually but no ARIA live region is present for polling updates.
- File input relies on browser-native accessibility.

### Data Privacy

- Uploaded videos are temporarily written to disk, uploaded to Azure Video Indexer, and deleted locally after indexing.
- Transcripts/OCR and metadata are sent to Azure OpenAI/Search flow.
- Job records may include source URLs, titles, errors, and final reports.
- There is no retention policy visible for Azure Video Indexer assets, Blob job JSON, or Search index data.

### Dependency Management

- Three dependency sources exist: `pyproject.toml`, `requirements.txt`, and `uv.lock`.
- Frontend has `package.json` plus `package-lock.json`.
- Some Python deps appear unused in tracked source.

### Maintainability

- Backend modules are separated by API, graph, service, worker, tests.
- Type contracts exist in Pydantic, TypedDict, and TypeScript interfaces.
- Some naming inconsistency exists: "Ad" vs "Add", "Youtube" vs "YouTube".
- Some retained frontend URL utilities/styles are unused by the current upload-only UI.

### Deployment Readiness

- App Service deployment is well documented and automated through GitHub Actions.
- Empty Dockerfile is not a real deployment path.
- No database migration or infra-as-code beyond scripts.
- App Service bootstrap assumes existing Azure AI/Search/VI resources and local `.env`.

## 12. Testing And Validation

### Test Frameworks

- Backend: Python `unittest`, `unittest.mock`, FastAPI `TestClient`.
- Frontend: Vitest, Testing Library, user-event, jsdom, jest-dom matchers.

### Existing Backend Tests

- `test_api_server.py`: API job creation, upload flow, invalid URL, status response shapes, sync endpoint, frontend serving.
- `test_audit_jobs.py`: job transitions, failure from graph errors, self-hosted skip, claim behavior.
- `test_graph_nodes.py`: YouTube blocked-download fallback to transcript.
- `test_self_hosted_worker.py`: worker claim/complete, empty queue, default Blob mode.
- `test_video_indexer.py`: YouTube metadata oEmbed/fallback, transcript payload, progressive stream selection, direct download, bot challenge error.

### Existing Frontend Tests

- Current UI renders upload as the only supported mode.
- Upload submits multipart `FormData` to `/audits/upload`.
- Failed jobs show backend error and failure placeholder.
- Submit remains disabled until a file is selected.

### Behavior Appears Untested

- Azure Blob store create/update/claim against real or mocked Blob clients.
- Document indexing script.
- Auditor node JSON parsing success/failure and retrieval query composition.
- API upload extension rejection and temp-file cleanup paths.
- Path traversal protections in `resolve_frontend_asset`.
- Health endpoint.
- End-to-end frontend polling through completion after an initial queued state.
- Self-hosted worker non-shared-store failure exit.
- Deployment scripts.

### How To Run Tests

Backend:

```powershell
python -m unittest discover -s backend/tests
```

Frontend:

```powershell
npm --prefix frontend run test
```

### Validation Attempted Here

- `python -m unittest discover -s backend/tests` failed because the local Python environment lacks required packages.
- `npm.cmd --prefix frontend run test` failed because `npm.cmd` is not available in this shell.
- `python -m py_compile backend/scripts/index_documents.py`, `main.py`, and `backend/src/api/server.py` succeeded.

### Suggested High-Value Tests To Add

1. `audit_content_node` with mocked LLM/Search for valid JSON, fenced JSON, malformed JSON, and empty transcript.
2. `save_uploaded_media` rejection and cleanup behavior.
3. Blob store ETag conflict retry behavior with fake clients.
4. `resolve_frontend_asset` traversal and asset-missing cases.
5. `index_docs()` with temporary PDFs or mocked loaders/vector store.
6. Frontend test for completed polling stopping after terminal status.
7. Worker exits `1` when no shared store is configured.

## 13. Build, Deployment, And Operations

### Build Process

- Backend: no compile step; Python source runs under FastAPI/Gunicorn.
- Frontend: `tsc -b && vite build` writes `frontend/dist`.
- CI vendors Python packages into `python_packages/lib/site-packages` for Azure App Service deployment.

### Runtime Process

- Azure App Service runs `bash startup.sh`.
- `startup.sh` sets `PYTHONPATH` to include vendored packages.
- Gunicorn binds to `0.0.0.0:${PORT:-8000}` with Uvicorn worker class and imports `backend.src.api.server:app`.
- FastAPI serves API and built frontend.

### Docker/Kubernetes

- `backend/Dockerfile` exists but is empty.
- CI uses Docker only as a build helper to vendor dependencies, not to deploy a container.
- No Kubernetes manifests are present.

### CI/CD

- Pull requests to `main` run tests/build.
- Pushes to `main` additionally upload artifact and deploy to Azure Web App.
- Azure login uses OIDC secrets generated by `create_github_oidc.ps1`.

### Monitoring/Logging

- Application Insights/OpenTelemetry can be enabled by env var.
- Logs are standard Python logging.
- No custom alert rules, dashboards, or log queries are tracked.

### Operational Risks

- A daemon thread job can be interrupted by process recycle.
- `wait_for_processing` can block indefinitely.
- Blob job records can remain `PROCESSING` if a worker dies.
- Upload temp files are deleted by the graph after upload; if the process dies mid-job, temp cleanup is not guaranteed.
- API health does not detect dependency outages.

### Production Incident Debugging From This Codebase

1. Check `/health` for basic server responsiveness.
2. Inspect App Service logs for API/job/Video Indexer/Azure OpenAI errors.
3. Check job record in memory logs or Azure Blob JSON for `job_status`, `error`, `worker_id`, timestamps.
4. For YouTube failures, look for blocked message and decide whether self-hosted mode is configured.
5. For weak/missing policy reasoning, verify PDFs were indexed and `AZURE_SEARCH_INDEX_NAME` points to the expected index.
6. For frontend 404, verify `frontend/dist` exists in deployment artifact.

## 14. How To Modify Or Extend This Project

### Add a New User-Facing Feature

Follow the current split:

1. Add backend request/response shape in `server.py` if needed.
2. Add job source metadata helpers in `video_indexer.py` if the input type is media-related.
3. Extend `index_video_node` for new `source_type`.
4. Add TypeScript types in `frontend/src/types.ts`.
5. Add API client function in `frontend/src/api.ts`.
6. Add UI state/rendering in `App.tsx`.
7. Add backend and frontend tests.

### Add a New Route or Endpoint

- Put route handler in `backend/src/api/server.py`.
- Use Pydantic models for request/response.
- Reuse job store wrappers if route relates to audits.
- Add tests in `backend/tests/test_api_server.py`.

### Add a New Data Model or Config

- Backend API model: Pydantic in `server.py`.
- Graph state field: `VideoAuditState` in `state.py`.
- Frontend API model: `frontend/src/types.ts`.
- Env var: document in README/docs and ideally add `.env.example`.

### Add Tests

- Backend tests are standard `unittest` with mocks.
- Prefer mocking external Azure/YouTube clients.
- Frontend tests should wrap components in `QueryClientProvider` like `renderApp()`.

### Debug Common Issues

- Start with job record: status, error, timestamps, source.
- Trace from API route to `audit_jobs._execute_audit_job`.
- Then inspect graph node logs and service methods.
- For frontend, inspect fetch calls from `api.ts` and React Query state.

### Avoid Breaking Existing Patterns

- Keep async job response shape compatible with `frontend/src/types.ts`.
- Preserve the distinction between backend capabilities and current upload-only UI.
- Do not bypass `AuditJobStore` wrappers unless there is a strong reason.
- Keep Azure secrets in env/app settings only.

## 15. Interview Preparation Pack

### 15.1 Elevator Pitches

**30-second pitch:** I built an AI-powered ad compliance checker that audits video creative. Users upload a video, the backend extracts transcript and on-screen text with Azure Video Indexer, retrieves policy context from Azure AI Search, and uses Azure OpenAI to return a structured pass/fail report in a React UI.

**60-second pitch:** This project is a full-stack compliance review demo for YouTube-style ad creative. The frontend creates async audit jobs and polls progress. The FastAPI backend runs a LangGraph workflow: first it indexes video content into transcript/OCR, then it performs retrieval-augmented compliance analysis with Azure AI Search and Azure OpenAI. A notable design choice is the self-hosted worker path: YouTube jobs can be queued in Azure Blob Storage and processed from a local network when Azure-hosted downloads are blocked.

**2-minute technical pitch:** The architecture has a React/Vite UI, a FastAPI API, a job store abstraction, and a LangGraph workflow. The API supports uploads, YouTube URLs, remote media URLs, and a legacy sync endpoint. Jobs are stored either in memory or as JSON blobs in Azure Blob Storage. The workflow has two nodes. The indexer node normalizes input sources, uploads media to Azure Video Indexer, polls for completion, extracts transcript/OCR, and falls back to public YouTube transcripts when cloud download blocking is detected. The auditor node embeds transcript/OCR, retrieves the top policy chunks from Azure AI Search, and prompts Azure OpenAI to return strict JSON with compliance results and a final report. The React app uses React Query for job creation and polling, then renders issue cards and markdown reports. CI runs backend and frontend tests, builds the frontend, vendors Python packages, and deploys to Azure App Service through GitHub OIDC.

**Recruiter-friendly pitch:** It is a working AI web app that helps review advertising videos for compliance. It combines a modern React frontend, Python API, Azure AI services, and a practical deployment pipeline. It shows product thinking, cloud integration, and real-world problem solving around unreliable YouTube downloads in cloud environments.

**Senior-engineer technical pitch:** The interesting part is not just "LLM checks a video." The repo separates ingestion, retrieval, reasoning, job state, and execution location. The `AuditJobStore` abstraction allows in-process memory for local demos and Blob-backed shared state for a cloud API plus local worker. The LangGraph state contract keeps extraction and audit stages explicit. The operational limitation around YouTube/Azure IP blocking is modeled as an execution-target problem instead of being hidden as a flaky failure.

### 15.2 Architecture Questions And Answers

**Q: Why use LangGraph for a two-step workflow?**  
A: Even though the current graph is linear, LangGraph makes the state contract and node boundaries explicit. `workflow.py` wires `indexer -> auditor`, while `state.py` defines the data exchanged. That makes it easier to add conditional edges later, such as skipping audit on index failure or adding a human review node.

**Q: What are the main backend components?**  
A: `server.py` exposes HTTP routes, `audit_jobs.py` orchestrates job execution, `job_store.py` stores state, `nodes.py` performs extraction and audit, `video_indexer.py` handles media/Azure helpers, and `self_hosted_worker.py` processes queued local jobs.

**Q: How does data flow from upload to final report?**  
A: The upload route saves the file, creates a job record, starts a background thread, passes source data to the graph, uploads the file to Azure Video Indexer, extracts transcript/OCR, retrieves policy chunks from Azure Search, calls Azure OpenAI for JSON, updates the job result, and the frontend polls until it can render the report.

**Q: Why have both memory and Blob job stores?**  
A: Memory is simple for local single-process development. Blob storage enables shared job state between Azure App Service and a local self-hosted worker without adding Redis, Service Bus, or a database.

**Q: What would fail first at scale?**  
A: API-process daemon threads, indefinite Video Indexer polling, and Blob listing as a queue would likely fail before the AI services. The current design is MVP/demo-friendly, not high-throughput.

**Q: How would you scale it?**  
A: Move background execution to a real queue/worker system such as Azure Service Bus plus Container Apps/WebJobs, add a durable database for audit history, add worker concurrency controls, add retries/dead-letter queues, and separate frontend/API/workers operationally.

**Q: How is the frontend served in production?**  
A: CI builds `frontend/dist`; FastAPI's `serve_frontend` serves assets from `FRONTEND_DIST_DIR` and falls back to `index.html` for client routes.

**Q: How is YouTube blocking handled?**  
A: The service detects bot/auth challenge text and raises a clear blocked message. The graph can fall back to public transcript extraction. For full YouTube processing, the backend can mark jobs `self_hosted`, leaving them for a local worker that polls a shared Blob store.

**Q: How would you monitor it?**  
A: Enable `APPLICATIONINSIGHTS_CONNECTION_STRING` for Azure Monitor, inspect logs by audit ID, track job status transitions, and add custom metrics for queue length, processing duration, external service failures, and LLM JSON parse failures.

**Q: Where is policy knowledge stored?**  
A: Source PDFs are tracked in `backend/data`. `index_documents.py` loads and chunks them, embeds with Azure OpenAI, and writes chunks into Azure AI Search. The runtime auditor retrieves from that index.

### 15.3 Code-Level Questions And Answers

**Q: What does `AuditUrlRequest.resolved_source_url()` solve?**  
A: It supports both `source_url` and legacy `video_url` fields, returning the first non-empty trimmed value.

**Q: What happens if `YOUTUBE_AUDIT_EXECUTION_TARGET` is misspelled?**  
A: `resolve_youtube_execution_target()` returns `azure` for anything other than exact lowercase `self_hosted`, so misspellings silently run in Azure.

**Q: Why does `InMemoryAuditJobStore` return deep copies?**  
A: It prevents callers from mutating internal job records without going through `update_job`, preserving store invariants.

**Q: How does `BlobAuditJobStore` avoid two workers claiming the same job?**  
A: It reads the blob and ETag, updates status to `PROCESSING`, then uploads with `MatchConditions.IfNotModified`. If another worker changed the blob first, upload fails and the code continues.

**Q: Where does upload cleanup happen?**  
A: If job creation fails, `create_uploaded_audit` deletes the saved file. If the graph starts, `index_video_node` appends upload/download paths to `cleanup_paths` and removes them in `finally`.

**Q: What is the risk in `audit_content_node` JSON parsing?**  
A: It expects the model to return strict JSON or fenced JSON. If response contains backticks without a matching JSON block or malformed JSON, parsing fails and the job records an error.

**Q: Why does `fetchJson` skip setting `Content-Type` for `FormData`?**  
A: The browser must set the multipart boundary. Manually setting `Content-Type: multipart/form-data` would break uploads.

**Q: What is currently unused in the frontend?**  
A: `createUrlAudit`, `validateYouTubeUrl`, `validateRemoteMediaUrl`, and several URL/source-toggle CSS classes are present but current `App.tsx` exposes only upload mode.

**Q: What is currently wrong with `index_documents.py` as a script?**  
A: Its `__main__` block has `index_docs` instead of `index_docs()`, so running the file directly will not execute indexing.

**Q: Why might `main.py` still work despite missing source fields?**  
A: `index_video_node` defaults `source_type` to `youtube`, `source_url` to `video_url`, and `video_id` to `vid_demo` if missing.

### 15.4 Debugging Questions And Answers

**Scenario: Upload request returns 400.**  
Symptom: UI shows an upload error.  
Likely cause: Missing filename or unsupported extension.  
Files to inspect: `server.py` `save_uploaded_media`, `App.tsx` file input accept string.  
Reproduce: Upload a `.txt` file.  
Fix: Use allowed video extension or extend `ALLOWED_UPLOAD_EXTENSIONS`.  
Prevent: Add client-side validation and tests.

**Scenario: Job remains queued forever.**  
Symptom: UI stays `Queued`.  
Likely cause: YouTube job targeted `self_hosted` but no worker is running, or using memory store across separate processes.  
Files to inspect: `audit_jobs.py`, `self_hosted_worker.py`, env vars.  
Reproduce: Set `YOUTUBE_AUDIT_EXECUTION_TARGET=self_hosted` and do not run worker.  
Fix: Run worker with shared Blob config or set target to `azure`.  
Prevent: Add stale queued job alerts.

**Scenario: Job fails after Video Indexer upload.**  
Symptom: `FAILED` with indexing error.  
Likely cause: Video Indexer state `Failed`, `Quarantined`, bad credentials, or upload issue.  
Files to inspect: `video_indexer.py` `wait_for_processing`, App Service logs.  
Reproduce: Use invalid Azure config or unsupported media.  
Fix: Correct Azure settings/media; add clearer typed errors.  
Prevent: Add preflight credential checks.

**Scenario: Audit fails with JSON parse error.**  
Symptom: Job error references JSON parsing or raw LLM response in logs.  
Likely cause: Model did not follow strict JSON prompt.  
Files to inspect: `nodes.py` `audit_content_node`.  
Reproduce: Mock LLM to return prose.  
Fix: Add structured output parser/Pydantic validation/retry repair prompt.  
Prevent: Test fenced/malformed outputs.

**Scenario: Production root path returns 404.**  
Symptom: API works but UI does not load.  
Likely cause: `frontend/dist/index.html` missing from deployment package or `FRONTEND_DIST_DIR` wrong.  
Files to inspect: `server.py`, CI artifact path, `startup.sh`.  
Reproduce: Run backend without building frontend.  
Fix: Build frontend and include dist.  
Prevent: CI smoke test `/`.

**Scenario: YouTube metadata fails in Azure.**  
Symptom: API returns 400 about bot verification or cannot fetch metadata.  
Likely cause: YouTube blocks cloud IP.  
Files to inspect: `video_indexer.py` `extract_youtube_metadata`.  
Reproduce: Use a YouTube URL from Azure-hosted app.  
Fix: Use self-hosted worker mode or rely on upload/media URL.  
Prevent: Expose upload as primary path, document YouTube limitation.

### 15.5 Design Tradeoff Questions And Answers

**Q: Simplicity vs scalability?**  
A: The repo favors simplicity: daemon threads, in-memory/Blob job store, direct polling. It is easier to demo and reason about, but a production system would use durable queues/workers and stronger recovery.

**Q: Local vs cloud assumptions?**  
A: Cloud hosts the UX/API, but local worker mode acknowledges that some media acquisition works better off-cloud. This hybrid approach solves a real constraint without abandoning Azure deployment.

**Q: Sync vs async behavior?**  
A: `/audit` preserves a simple sync contract, but the UI uses async jobs because video indexing and LLM calls are long-running. Async polling is the better product path.

**Q: Type safety?**  
A: Pydantic validates API responses, TypedDict documents graph state, and TypeScript types mirror the API. There is still drift risk because schemas are duplicated manually.

**Q: State management?**  
A: React Query handles server state and polling; local React state handles the form and active audit. This is appropriate for a small app.

**Q: Error handling?**  
A: The code converts many failures to job state errors, which is good for UI polling. It uses broad exceptions and string matching, which is pragmatic but less robust.

**Q: Testing choices?**  
A: Unit tests mock external systems for deterministic CI. The tradeoff is limited confidence in real Azure integration and deployment scripts.

**Q: Framework choices?**  
A: FastAPI gives typed HTTP APIs quickly; React/Vite gives a modern frontend; LangGraph makes pipeline boundaries explicit; Azure services align with the deployment target.

**Q: Performance choices?**  
A: Top-3 retrieval and 3-second frontend polling are simple. Long-term, add adaptive polling, async workers, caching, and better retrieval tuning.

### 15.6 Behavioral / STAR Stories

**Building the project - evidence-based framing**  
Situation: Manual ad compliance review requires video inspection and policy lookup.  
Task: Build a demo that automates extraction, retrieval, and compliance reporting.  
Action: Created FastAPI endpoints, LangGraph extraction/audit nodes, Azure integrations, React polling UI, and CI/deployment scripts.  
Result: A deployable MVP that can accept uploaded videos and return structured compliance reports.

**Debugging a hard issue - suggested framing based on repo evidence**  
Situation: YouTube downloads can be blocked from Azure-hosted environments.  
Task: Preserve cloud-hosted UX while avoiding blocked cloud downloads.  
Action: Added execution targets, Azure Blob-backed shared job storage, and a self-hosted worker that claims queued YouTube jobs.  
Result: The architecture supports local processing for YouTube jobs while the browser still polls the cloud API.

**Architectural decision - evidence-based framing**  
Situation: Long-running video/LLM audits do not fit a simple request/response UI.  
Task: Make audits trackable without blocking the browser.  
Action: Introduced async job records, status polling, and React Query cache updates.  
Result: Users can start an audit and watch status move through queued, processing, completed, or failed states.

**Improving reliability - suggested framing**  
Situation: External APIs can fail or return malformed output.  
Task: Keep failures visible to users instead of crashing.  
Action: Wrapped graph node errors into state errors and job failures; added tests for blocked YouTube fallback and failed job rendering.  
Result: The UI can show terminal failures with error messages.

**Learning a new tool/framework - suggested framing**  
Situation: The project needed a clear AI workflow with state passing.  
Task: Use LangGraph to organize the pipeline.  
Action: Defined `VideoAuditState`, built indexer/auditor nodes, and compiled the graph in `workflow.py`.  
Result: The workflow is understandable and extensible.

**Handling ambiguity - evidence-based framing**  
Situation: The backend supports YouTube, media URLs, and uploads, but the current UI exposes only uploads.  
Task: Keep documentation and tests honest about the actual product surface.  
Action: Frontend tests assert upload-only mode, while README/API docs explain backend-supported modes.  
Result: The repo distinguishes implemented backend capability from current UI exposure.

**Testing/validation - evidence-based framing**  
Situation: Azure and YouTube integrations are hard to test live in CI.  
Task: Validate behavior deterministically.  
Action: Used mocks for metadata, graph output, downloads, and fetch responses.  
Result: Unit tests cover API contracts, job transitions, worker behavior, and key helper logic.

**Deployment/production readiness - evidence-based framing**  
Situation: The app needed a deployable cloud demo.  
Task: Package backend and built frontend for Azure App Service.  
Action: Added GitHub Actions build/test/deploy workflow, App Service startup script, Azure bootstrap, and OIDC setup script.  
Result: The repo has a documented path to deploy on pushes to `main`.

### 15.7 Explain This Project To...

**A recruiter:** It is a full-stack AI application that reviews ad videos for compliance using Azure AI services, with a React frontend, Python backend, automated tests, and cloud deployment.

**A non-technical user:** You upload an advertisement video, and the app reads what is spoken and shown on screen, checks it against advertising guidance, and gives you a pass/fail report with issues to review.

**A junior developer:** The frontend sends a file to the backend and keeps asking for status. The backend runs a two-step workflow: get text from the video, then ask an AI model to check the text against policy documents.

**A senior engineer:** The architecture is an MVP-friendly async job system around a LangGraph RAG pipeline. It separates source normalization, media extraction, retrieval, LLM judgment, job persistence, and execution target, with a Blob-backed shared store for hybrid cloud/local processing.

**A product manager:** The product reduces review time for ad creative by creating a first-pass compliance report. Current UI supports uploads; backend capabilities can support YouTube and remote media URLs when exposed.

**A hiring manager:** The repo demonstrates full-stack implementation, cloud integration, AI workflow design, testing, deployment automation, and pragmatic handling of external-service constraints.

**An ML/AI engineer:** It is a RAG application over policy PDFs. Transcript and OCR become the query. Azure OpenAI embeddings retrieve top policy chunks from Azure AI Search, and an Azure chat model produces structured compliance JSON. The main AI risks are prompt injection, retrieval coverage, and structured-output reliability.

## 16. Glossary

| Term | Meaning in this repo |
|---|---|
| Audit job | Async unit of work stored in memory or Blob with status/result/error. |
| Azure AI Search | Vector/document retrieval store for policy chunks. |
| Azure Blob job store | JSON-per-job shared storage used by cloud API and local worker. |
| Azure OpenAI | Embedding and chat model provider. |
| Azure Video Indexer | Service used to process videos and extract transcript/OCR. |
| Compliance result | LLM-produced judgment containing status, issues, and report. |
| Execution target | `azure` or `self_hosted`, deciding where YouTube jobs run. |
| Graph node | LangGraph function that reads/writes `VideoAuditState`. |
| Indexer node | Node that converts video input into transcript/OCR/metadata. |
| Auditor node | Node that retrieves policy and asks LLM for compliance JSON. |
| RAG | Retrieval-augmented generation; policy chunks are retrieved before LLM judgment. |
| Self-hosted worker | Local CLI process that polls Blob store for queued YouTube jobs. |
| `uploaded://` | Pseudo URL used in preview metadata for local uploads. |
| `VideoAuditState` | TypedDict state passed through the LangGraph workflow. |
| `AuditJobResponse` | API/frontend shape for job status polling. |
| `FRONTEND_DIST_DIR` | Directory FastAPI uses to serve built React assets. |
| `YOUTUBE_AUDIT_EXECUTION_TARGET` | Env var controlling YouTube cloud vs local worker execution. |

## 17. Risks, Gaps, And Improvement Roadmap

### Highest-Risk Code Areas

1. `backend/src/graph/nodes.py` LLM JSON parsing and prompt construction.
2. `backend/src/services/video_indexer.py` external service calls, long polling, YouTube download behavior.
3. `backend/src/api/audit_jobs.py` daemon-thread job execution.
4. `backend/src/api/job_store.py` Blob-as-queue behavior under concurrency.
5. `backend/scripts/index_documents.py` uncalled `__main__` entrypoint.

### Missing Tests

- Auditor node success/malformed output.
- Blob job store conflict and claim behavior.
- Indexing script behavior.
- Upload cleanup and rejection cases.
- Deployment script smoke tests or dry-run validation.

### Security Concerns

- No app auth/rate limiting.
- Upload size/content not enforced.
- Prompt injection from transcript/OCR.
- Broad `.env` copying to App Service.
- No retention policy for video, transcript, Search index, or job records.

### Performance Concerns

- Blocking sleeps and external calls in daemon threads.
- Indefinite Video Indexer polling.
- Blob listing for queue polling.
- Fixed top-3 retrieval.

### Maintainability Concerns

- Duplicate schemas across Pydantic, TypedDict, TypeScript.
- Dependency drift among `pyproject.toml`, `requirements.txt`, and `uv.lock`.
- Naming inconsistencies ("Ad/Add", "Youtube/YouTube").
- Unused dependencies and retained unused frontend utilities/styles.

### Documentation Gaps

- No `.env.example`.
- No source/version metadata for PDFs.
- No detailed operational runbook for stuck jobs or Blob cleanup.
- No instructions for actually invoking `index_docs()` until `__main__` is fixed.

### Suggested Improvements Ordered By Impact

1. Move background execution to a durable queue/worker service with retries and stale job recovery.
2. Add structured LLM output validation/retry repair with Pydantic or LangChain structured output.
3. Add `.env.example` with all variable names and redacted placeholders.
4. Fix `index_documents.py` script entrypoint and add tests.
5. Add upload limits/content validation and retention policy.
6. Add Blob store tests and operational job cleanup tooling.
7. Re-expose YouTube/media URL UI if desired and test it.
8. Prune unused Python dependencies.
9. Add auth if the app moves beyond demo use.

### Suggested Improvements Ordered By Effort

1. Fix naming typos in UI/API metadata.
2. Change `index_docs` to `index_docs()` under `__main__`.
3. Add `.env.example`.
4. Add upload extension rejection tests.
5. Add max polling timeout to `wait_for_processing`.
6. Add frontend client-side extension/size validation.
7. Add structured output parser.
8. Introduce durable queue/worker architecture.

## 18. Coverage Checklist

### Inventory Summary

- Total tracked files analyzed: 52.
- Total non-root tracked folders analyzed: 18.
- Notable untracked files observed before work: none from `git status --short`.
- Temporary generated `__pycache__` directories from validation were removed.
- Source-code files received meaningful deep-dive entries.
- Binary/generated/lock/vendor-style files were covered at appropriate high level.
- Secret values were not copied; no tracked secret values were observed.

### Files Covered In Deep Dive

- [x] `.gitattributes`
- [x] `.github/workflows/ci-cd.yml`
- [x] `.gitignore`
- [x] `.python-version`
- [x] `README.md`
- [x] `backend/Dockerfile`
- [x] `backend/data/1001a-influencer-guide-508_1.pdf`
- [x] `backend/data/youtube-ad-specs.pdf`
- [x] `backend/scripts/index_documents.py`
- [x] `backend/src/api/audit_jobs.py`
- [x] `backend/src/api/job_store.py`
- [x] `backend/src/api/server.py`
- [x] `backend/src/api/telemetry.py`
- [x] `backend/src/graph/__init__.py`
- [x] `backend/src/graph/nodes.py`
- [x] `backend/src/graph/state.py`
- [x] `backend/src/graph/workflow.py`
- [x] `backend/src/services/__init__.py`
- [x] `backend/src/services/video_indexer.py`
- [x] `backend/src/worker/__init__.py`
- [x] `backend/src/worker/self_hosted_worker.py`
- [x] `backend/tests/test_api_server.py`
- [x] `backend/tests/test_audit_jobs.py`
- [x] `backend/tests/test_graph_nodes.py`
- [x] `backend/tests/test_self_hosted_worker.py`
- [x] `backend/tests/test_video_indexer.py`
- [x] `docs/azure-app-service.md`
- [x] `frontend/index.html`
- [x] `frontend/package-lock.json`
- [x] `frontend/package.json`
- [x] `frontend/src/App.test.tsx`
- [x] `frontend/src/App.tsx`
- [x] `frontend/src/api.ts`
- [x] `frontend/src/main.tsx`
- [x] `frontend/src/styles.css`
- [x] `frontend/src/test/setup.ts`
- [x] `frontend/src/types.ts`
- [x] `frontend/src/utils/media.ts`
- [x] `frontend/src/utils/youtube.ts`
- [x] `frontend/src/vite-env.d.ts`
- [x] `frontend/tsconfig.app.json`
- [x] `frontend/tsconfig.json`
- [x] `frontend/tsconfig.node.json`
- [x] `frontend/vite.config.ts`
- [x] `main.py`
- [x] `pyproject.toml`
- [x] `requirements.txt`
- [x] `scripts/azure/bootstrap_app_service.ps1`
- [x] `scripts/azure/create_github_oidc.ps1`
- [x] `scripts/github/set-main-branch-protection.ps1`
- [x] `startup.sh`
- [x] `uv.lock`

### Files Covered Only At High Level, With Reason

- `backend/data/1001a-influencer-guide-508_1.pdf`: Binary PDF policy/reference file; detailed code-level analysis not applicable.
- `backend/data/youtube-ad-specs.pdf`: Binary PDF policy/reference file; detailed code-level analysis not applicable.
- `frontend/package-lock.json`: Generated npm lockfile; dependency graph summarized rather than line-by-line decoded.
- `requirements.txt`: Pinned dependency list; package roles summarized rather than every transitive package decoded.
- `uv.lock`: Generated uv lockfile; role and dependency-lock behavior summarized.
- Empty package markers `backend/src/graph/__init__.py`, `backend/src/services/__init__.py`: No code to walk through beyond package role.
- `backend/Dockerfile`: Empty placeholder; no code-level behavior.

### Files Skipped

No tracked files were skipped.

### Limitations Of This Analysis

- No live Azure, YouTube, GitHub, or App Service calls were made.
- Backend tests could not run in this local interpreter because dependencies are not installed.
- Frontend tests could not run because `npm.cmd` is not available in this shell.
- PDF content was not decoded line by line; paths, roles, and indexing relationship were documented from repo evidence.
- Runtime behavior that depends on actual Azure resource configuration is described from code paths and docs, not from live deployment verification.
