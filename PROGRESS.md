# Milestone 2 Progress

## Status: COMPLETE

## Tickets

| Ticket | Description | Status |
|--------|-------------|--------|
| T-001 | Auto-collect metrics_summary on run completion | DONE |
| T-002 | Run Summary + Checkpoints API | DONE |
| T-003 | Compare API endpoint | DONE |
| T-004 | Fix Compare frontend page | DONE |
| T-005 | Smoke test for metrics collection + compare | DONE |

## Completion Criteria
- [x] Training process end → metrics_summary auto-saved to DB
- [x] GET /api/runs/{run_id}/summary works
- [x] GET /api/runs/{run_id}/checkpoints works
- [x] /compare page: config diff + metric charts + final table with trophy
- [x] Experiment list checkbox → Compare button works
- [x] gate.sh PASS

## Changes Summary

### Backend
- **process_manager.py**: Added `_collect_final_metrics()` — auto-aggregates last metric values,
  training duration, step/epoch counts into `metrics_summary` on run completion
- **runs.py**: Added `GET /api/runs/{run_id}/summary` and `GET /api/runs/{run_id}/checkpoints`
- **experiments.py**: Added `POST /api/experiments/compare` (bulk compare) and
  `GET /api/experiments/{id}/metrics` (convenience: latest run metrics)
- **schemas/experiment.py**: Added RunSummaryResponse, CheckpointsResponse, CompareRequest/Response

### Frontend
- **App.tsx**: Added `/experiments/compare` route (matches list page navigation)
- **ExperimentComparePage.tsx**: Already had config diff, metric overlay charts, final table with 🏆
  — now works with the new `/api/experiments/{id}/metrics` endpoint
- **ExperimentListPage.tsx**: Checkbox selection + Compare button already functional

### Tests
- **test_milestone2.py**: 13 tests covering config diff, metrics summary logic, schema validation
- All 60 tests pass, gate.sh PASS
