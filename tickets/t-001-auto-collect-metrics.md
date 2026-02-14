# T-001: Auto-collect metrics_summary on run completion

## Objective
When a training process finishes, automatically aggregate final metrics from MetricLog entries
and store them in ExperimentRun.metrics_summary along with training duration.

## Non-goals
- Checkpoint scanning (separate ticket)
- Frontend changes

## Files to touch
- `backend/core/process_manager.py` — add `_collect_final_metrics()` called from `_monitor()`

## Acceptance criteria
- When run completes (return_code == 0), metrics_summary is populated with last value of each metric key
- `ended_at - started_at` duration stored in metrics_summary as `_duration_seconds`
- When run fails, metrics_summary still collected (partial results useful)
- `pytest tests/test_metrics_collection.py` passes
