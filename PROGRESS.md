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
- [x] DELETE /api/runs/{run_id}/checkpoints/{name} works
- [x] /compare page: config diff + metric charts + final table with trophy
- [x] Experiment list checkbox → Compare button works
- [x] No hardcoded metric names in core code (fully generic/dynamic)
- [x] gate.sh PASS (147 tests, smoke OK)

## Changes Summary

### Backend
- **process_manager.py**: Added `_collect_final_metrics()` — auto-aggregates last metric values,
  training duration, step/epoch counts into `metrics_summary` on run completion
- **runs.py**: Added `GET /api/runs/{run_id}/summary`, `GET /api/runs/{run_id}/checkpoints`,
  and `DELETE /api/runs/{run_id}/checkpoints/{name}` (with directory traversal protection)
- **experiments.py**: Added `POST /api/experiments/compare` (bulk compare) and
  `GET /api/experiments/{id}/metrics` (convenience: latest run metrics)
- **schemas/experiment.py**: Added RunSummaryResponse, CheckpointsResponse, CompareRequest/Response

### Frontend
- **App.tsx**: Added `/experiments/compare` and `/compare` routes
- **ExperimentComparePage.tsx**: Config diff table (diff-only toggle, highlight outliers),
  metric overlay charts (fully dynamic metric selection — no hardcoded keys),
  final metrics table with 🏆 best value highlighting (dynamic, sorted by val/ → train/ → rest)
- **ExperimentListPage.tsx**: Checkbox selection (max 3) + Compare button; "Best Metric" column (generic)

### Tests
- **test_milestone2.py**: 13 tests covering config diff, metrics summary logic, schema validation
- 147 tests pass, gate.sh PASS

### Platform Genericity Fixes (latest commit)
- Removed hardcoded `DEFAULT_CHART_METRICS` and `FINAL_TABLE_METRICS` from compare page
- Chart metrics auto-select from available `val/` keys on data load
- Final table dynamically shows all metrics found in data
- Renamed "Best mAP" → "Best Metric" in experiment list
