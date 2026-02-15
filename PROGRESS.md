# Milestone 3 Progress

## Status: COMPLETE

## Tickets

| Ticket | Description | Status |
|--------|-------------|--------|
| T-006 | Inference code internalization (adapters/vlm_quantization/) | DONE |
| T-007 | Dummy checkpoint + test data generation | DONE |
| T-008 | Job management system (EVAL, INDEX_BUILD) | DONE |
| T-009 | Eval job API (POST /api/jobs/eval, GET /api/jobs/{id}) | DONE |
| T-010 | Index build job API (POST /api/jobs/index-build) | DONE |
| T-011 | Search API (POST /api/search/text, POST /api/search/image) | DONE |
| T-012 | Search demo frontend page | DONE |
| T-013 | Eval compare table (generic result rendering) | DONE |
| T-014 | Smoke test + gate pass | DONE |

## Completion Criteria

### Part A: Eval (Generic)
- [x] Eval job runs adapter's evaluation logic via Job system
- [x] Job model with EVAL/INDEX_BUILD types, progress tracking, cancel support
- [x] Job API: create, list, get status, cancel
- [x] EvalResult stored in DB (generic JSON)
- [x] ResultViewType rendering: retrieval_table for vlm_quantization

### Part B: Search Demo
- [x] Build Search Index button → index build job with progress
- [x] Text search → similar images Top-K (thumbnails + scores)
- [x] Image upload → similar texts Top-K
- [x] Bit length selection (8/16/32/64/128)
- [x] Hamming distance + cosine similarity methods
- [x] Sample query buttons (Korean/English)

### Pre-work: Inference Internalization
- [x] adapters/vlm_quantization/model.py — CrossModalHashModel with dummy backbone
- [x] adapters/vlm_quantization/hash_layer.py — NestedHashLayer (multi-bit sign)
- [x] adapters/vlm_quantization/index_builder.py — build_index + load_index
- [x] adapters/vlm_quantization/search.py — hamming_search + cosine_search
- [x] adapters/vlm_quantization/evaluator.py — mAP, P@K computation

### Platform Genericity
- [x] No vlm/hash/siglip/coco terms in backend/api/ or backend/core/
- [x] Search API routes through adapter registry (not direct imports)
- [x] BaseAdapter has optional search/index/eval methods (NotImplementedError default)
- [x] gate.sh PASS (147 tests, 1 skipped, smoke OK)

## Changes Summary

### Backend — Inference Internalization (adapters/vlm_quantization/)
- **model.py**: CrossModalHashModel wrapper with DummyVisionModel + DummyTextModel
  (random projection backbone for testing without SigLIP2 download)
- **hash_layer.py**: NestedHashLayer with sign() STE and prefix-based multi-bit codes
- **index_builder.py**: build_index (encode dataset → thumbnails + hash codes), load_index
- **search.py**: hamming_search (XOR + popcount), cosine_search (feature similarity)
- **evaluator.py**: mean_average_precision, precision_at_k for retrieval evaluation

### Backend — Job System
- **models/job.py**: Job SQLModel with type, status, progress, result JSON fields
- **services/job_manager.py**: Subprocess orchestration, progress DB updates, cancel
- **workers/job_runner.py**: Eval + index build subprocess execution
- **api/jobs.py**: Full CRUD — POST create, GET list/detail, POST cancel, GET progress

### Backend — Search API (Generic)
- **api/search.py**: POST /api/search/text, POST /api/search/image
  Routes through adapter registry via `get_adapter(adapter_name)` — zero vlm-specific imports
- **adapters/base.py**: Added `load_model`, `load_index`, `search_by_text`, `search_by_image`
  as optional methods (raise NotImplementedError by default)
- **adapters/vlm_quantization/adapter.py**: Implemented all search methods
  (lazy imports keep adapter-specific deps contained)

### Frontend
- **SearchDemoPage.tsx**: Full search demo — text/image input, bit length selector,
  method toggle (hamming/cosine), result grid with thumbnails + scores, sample queries
- **api/jobs.ts**: Job + search API client functions

### Test Fixtures
- **scripts/create_dummy_checkpoint.py**: Generates dummy model + test images/captions
- **tests/fixtures/**: dummy_checkpoint.pt, dummy_images/, dummy_captions.json

### Tests
- **test_milestone3.py**: ~30 tests covering model, hash layer, search, eval, job API
- 147 tests pass, 1 skipped, gate.sh PASS

---

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
