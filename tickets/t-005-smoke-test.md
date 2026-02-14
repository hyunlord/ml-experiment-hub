# T-005: Smoke test for metrics collection + compare

## Objective
Add tests proving the auto-collection and compare features work.

## Files to touch
- `tests/test_metrics_collection.py` — test metrics_summary auto-collection
- `tests/test_compare_api.py` — test compare + summary + checkpoints endpoints

## Acceptance criteria
- `pytest tests/` passes
- `./scripts/gate.sh` passes
