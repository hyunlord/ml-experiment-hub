# T-002: Run Summary + Checkpoints API

## Objective
Add two new REST endpoints for run result access.

## Endpoints
- `GET /api/runs/{run_id}/summary` → result summary JSON (metrics_summary + duration + status)
- `GET /api/runs/{run_id}/checkpoints` → checkpoint listing with file sizes

## Files to touch
- `backend/api/runs.py` — add two endpoints
- `backend/schemas/experiment.py` — add RunSummaryResponse, CheckpointResponse

## Acceptance criteria
- Summary returns metrics_summary, duration_seconds, status, started_at, ended_at
- Checkpoints returns list of {path, size_bytes, modified_at} or empty list
- 404 for non-existent run_id
