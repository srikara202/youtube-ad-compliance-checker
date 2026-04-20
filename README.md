# Youtube Add Compliance Checker

Youtube Add Compliance Checker audits YouTube advertisement videos against compliance rules. The repo now includes:

- A FastAPI backend with both synchronous and asynchronous audit endpoints
- A React + Vite frontend for submitting YouTube URLs and polling audit results
- A GitHub Actions CI/CD workflow for tests and Azure App Service deployment

## Backend

Run the API from the project root:

```powershell
uv run uvicorn backend.src.api.server:app --reload
```

Existing endpoint:

- `POST /audit`: keeps the original synchronous workflow contract for scripts and CLI usage

New frontend-oriented endpoints:

- `POST /audits`: validates the YouTube URL, fetches title and thumbnail, creates an audit job, and starts background processing
- `GET /audits/{audit_id}`: returns the current job status and final result when ready

Backend environment variables are still read from `.env`. The existing Azure and OpenAI settings remain required for full audit execution. Optional frontend integration setting:

- `FRONTEND_ORIGINS`: comma-separated list of allowed browser origins for CORS. Defaults to `http://localhost:5173,http://127.0.0.1:5173`
- `FRONTEND_DIST_DIR`: optional override for the built frontend directory when FastAPI serves the production React app
- `AUDIT_JOB_STORE`: `memory` for local-only jobs, or `azure_blob` for a shared job store between Azure App Service and a self-hosted worker
- `AUDIT_JOB_BLOB_CONTAINER`: optional Azure Blob container name for job records. Defaults to `audit-jobs`
- `AUDIT_JOB_BLOB_PREFIX`: optional blob prefix for job JSON documents. Defaults to `jobs`
- `YOUTUBE_AUDIT_EXECUTION_TARGET`: `azure` or `self_hosted`. Set this to `self_hosted` on Azure when you want pasted YouTube links to be processed by your home machine instead of App Service

## Self-Hosted YouTube Worker

The cheapest reliable fix for YouTube bot-blocking is to keep the UI and API on Azure, but process queued YouTube jobs from your own machine:

1. Set the Azure app setting `AUDIT_JOB_STORE=azure_blob`
2. Set the Azure app setting `YOUTUBE_AUDIT_EXECUTION_TARGET=self_hosted`
3. Keep `AZURE_STORAGE_CONNECTION_STRING` available to both Azure and your local worker
4. Run the worker on your machine from the repo root:

```powershell
python -m backend.src.worker.self_hosted_worker
```

Use `python -m backend.src.worker.self_hosted_worker --once` for a single queue pass.

## Frontend

Install dependencies inside the frontend workspace:

```powershell
cd frontend
npm.cmd install
```

Start the frontend dev server:

```powershell
npm.cmd run dev
```

The Vite dev server proxies `/audit`, `/audits`, and `/health` to `http://127.0.0.1:8000` by default. Optional frontend environment setting:

- `VITE_API_BASE_URL`: override the API base URL when you are not using the Vite proxy

Build the frontend for production:

```powershell
cd frontend
npm.cmd run build
```

When `frontend/dist` exists, FastAPI serves the built React app at `/` and falls back to `index.html` for client-side routes.

## Tests

Backend tests:

```powershell
python -m unittest discover -s backend/tests
```

Frontend tests:

```powershell
cd frontend
npm.cmd run test
```

## Azure App Service Deployment

This repo is set up for the cheapest single-host deployment path:

- One Linux Azure App Service running the FastAPI app
- The same FastAPI app also serves the built React frontend
- GitHub Actions deploys to Azure using OpenID Connect (OIDC)

Files added for this flow:

- `startup.sh`: Gunicorn + Uvicorn startup command for Azure App Service
- `.github/workflows/ci-cd.yml`: CI on pull requests and deploy on `main`
- `scripts/azure/bootstrap_app_service.ps1`: creates the App Service resource group, plan, web app, identity, and app settings
- `scripts/azure/create_github_oidc.ps1`: creates the Microsoft Entra app/service principal and federated credential for GitHub Actions
- `scripts/github/set-main-branch-protection.ps1`: optional helper to require CI on `main`
- `docs/azure-app-service.md`: end-to-end setup guide

See [docs/azure-app-service.md](docs/azure-app-service.md) for the full Azure and GitHub setup flow.
