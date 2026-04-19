# Youtube Add Compliance Checker

Youtube Add Compliance Checker audits YouTube advertisement videos against compliance rules. The repo now includes:

- A FastAPI backend with both synchronous and asynchronous audit endpoints
- A React + Vite frontend for submitting YouTube URLs and polling audit results

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
