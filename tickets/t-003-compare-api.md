# T-003: Compare API endpoint

## Objective
Add a bulk comparison endpoint and convenience metrics endpoint per experiment.

## Endpoints
- `POST /api/experiments/compare` body: {ids: [1,3]} → returns experiments + their latest run metrics
- `GET /api/experiments/{id}/metrics` → convenience: returns metrics from the latest run

## Files to touch
- `backend/api/experiments.py` — add compare endpoint
- `backend/api/runs.py` — add experiment-level metrics convenience endpoint
- `backend/schemas/experiment.py` — add CompareRequest, CompareResponse

## Acceptance criteria
- Compare endpoint returns config + final metrics for each experiment
- Convenience metrics endpoint fetches latest run's metrics
- Works for 2-3 experiments
