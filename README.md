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
