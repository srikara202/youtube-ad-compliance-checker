# AGENTS.md

Project guidance for Codex and other coding agents working in this repository.

## Core Working Rules

- Make the smallest safe change that addresses the user's request.
- Prefer a narrow failing test or repro command before changing implementation.
- Do not refactor unrelated code while fixing a bug.
- Do not add dependencies or change public APIs unless the task requires it.
- Preserve user changes already present in the worktree. Do not revert unrelated edits.
- Use `rg` or `rg --files` for search before slower alternatives.

## Anti-Loop Rules

When working on bugs, failing tests, or ambiguous behavior:

1. Do not repeat the same investigation path more than twice.
2. Do not re-read the same files unless there is a new question to answer.
3. Do not run the same command again unless code, configuration, dependencies, or inputs changed.
4. Before a second fix attempt, state:
   - current hypothesis
   - evidence for it
   - evidence against it
   - what changed since the previous attempt
5. If the same command fails with the same error twice, stop and report the blocker.
6. If `git diff` is empty after substantial investigation, stop and summarize what context is missing.
7. Prefer one focused code change followed by validation over broad speculative edits.
8. Do not change tests to match broken behavior unless explicitly asked.
9. After two unsuccessful autonomous attempts, stop and provide a loop diagnosis instead of continuing.

## Loop Diagnosis Format

If the work appears to be looping, stop editing and report:

- exact issue being fixed
- files inspected
- assumptions made
- repeated attempts or commands
- evidence that the previous approach is not working
- smallest next testable change, or the missing context needed to proceed

## Checkpoint Workflow

For non-trivial fixes:

1. Understand the current behavior with no edits.
2. Identify the narrowest relevant test, repro, or validation command.
3. State the implementation hypothesis before editing.
4. Apply one focused change.
5. Run the narrow validation first.
6. Run broader checks only after the narrow check passes.

Stop if the fix requires changing more than 3 files, unless you explain why the extra files are necessary.

## Repository Routing

Frontend issues usually start in:

- `frontend/src/App.tsx`
- `frontend/src/api.ts`
- `frontend/src/types.ts`
- `frontend/src/utils/`
- `frontend/src/App.test.tsx`
- `frontend/package.json`
- `frontend/vite.config.ts`

Backend API and job issues usually start in:

- `backend/src/api/server.py`
- `backend/src/api/audit_jobs.py`
- `backend/src/api/job_store.py`
- `backend/src/api/billing.py`
- `backend/tests/`

Audit workflow and media processing issues usually start in:

- `backend/src/graph/workflow.py`
- `backend/src/graph/nodes.py`
- `backend/src/graph/state.py`
- `backend/src/services/video_indexer.py`
- `backend/scripts/index_documents.py`

Self-hosted worker issues usually start in:

- `backend/src/worker/self_hosted_worker.py`
- `backend/tests/test_self_hosted_worker.py`
- `backend/tests/test_audit_jobs.py`

Deployment and operations issues usually start in:

- `.github/workflows/`
- `startup.sh`
- `docs/azure-app-service.md`
- `scripts/azure/`
- `scripts/github/`

Avoid unless directly relevant:

- generated build outputs
- vendored dependencies
- `node_modules`
- `frontend/dist`
- `python_packages`
- `__pycache__`
- large lockfiles
- PDFs in `backend/data` unless changing retrieval inputs or documentation

## Validation Commands

Use the narrowest relevant command first.

Backend tests:

```powershell
python -m unittest discover -s backend/tests
```

Frontend tests:

```powershell
npm.cmd --prefix frontend run test
```

Frontend build:

```powershell
npm.cmd --prefix frontend run build
```

Backend local server:

```powershell
uv run uvicorn backend.src.api.server:app --reload
```

Frontend dev server:

```powershell
npm.cmd --prefix frontend run dev
```

Self-hosted worker:

```powershell
python -m backend.src.worker.self_hosted_worker --once
```

## Completion Report

End coding tasks with:

- files changed
- commands run and result of each command
- concise diff summary
- remaining risks or unverified paths

