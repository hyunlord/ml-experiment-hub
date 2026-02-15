# Milestone 7 Progress

## Status: COMPLETE

## Objective

Real model E2E pipeline + production stabilization + universality proof.
Prove the platform is genuinely generic by adding a second, completely different
model type (image classification) alongside the existing cross-modal retrieval adapter.

## Completion Criteria

### Dummy Classifier Adapter (Universality Proof)
- [x] `adapters/dummy_classifier/model.py` — SimpleCNN (MNIST + CIFAR-10)
- [x] `adapters/dummy_classifier/train.py` — Standalone training script with JSON metric output
- [x] `adapters/dummy_classifier/evaluator.py` — Per-class precision/recall/F1
- [x] `adapters/dummy_classifier/adapter.py` — Full BaseAdapter implementation
- [x] Registered in adapter registry (`adapters/__init__.py`)
- [x] Training, metrics parsing, hyperparameter search ranges all work

### Predict API (Generic Inference)
- [x] `POST /api/predict/image` — generic endpoint routing through adapter registry
- [x] Supports any adapter with `predict()` method
- [x] Model cache for loaded checkpoints
- [x] Frontend Classifier Demo page (`/demo/classifier`)
- [x] Drag-and-drop image upload, confidence bar chart

### Platform Genericity Hardening
- [x] Removed `vlm_quantization` default from search API (adapter_name now required)
- [x] Removed vlm-specific comments from `system.py`, `compat.py`, `search.py`
- [x] Frontend search API updated to pass `adapter_name` parameter
- [x] No forbidden terms (vlm, siglip, hash, coco) in `backend/api/`, `backend/core/`, `shared/schemas.py`

### Production Stabilization (Pre-existing from earlier milestones)
- [x] SQLite WAL mode + composite indexes on MetricLog
- [x] Server restart recovery (PID liveness check, orphan run cleanup)
- [x] OOM detection (CUDA out of memory parsing)
- [x] Disk space warnings (< 2 GB threshold)
- [x] GPU temperature alerts (85°C warning, 95°C critical)
- [x] Log rotation + compression (7-day archive)
- [x] Metric archival for old runs
- [x] Docker healthcheck + memory limits
- [x] DGX Spark config preset

### Documentation
- [x] `docs/new-adapter-guide.md` — Step-by-step guide using dummy_classifier as example
- [x] `README.md` — Updated with adapter system, available adapters table, classifier demo
- [x] PROGRESS.md updated

### Tests & Gate
- [x] 258 tests pass, 1 skipped
- [x] ruff lint: all checks pass
- [x] ruff format: all files formatted
- [x] TypeScript: 0 errors (tsc --noEmit)

## Changes Summary

### Adapters — Dummy Classifier (NEW)
- **adapters/dummy_classifier/__init__.py**: Re-export
- **adapters/dummy_classifier/model.py**: SimpleCNN — Conv2d(in→32)→ReLU→Pool→Conv2d(32→64)→
  AdaptiveAvgPool(4)→Linear(1024→128)→Linear(128→num_classes); load_model() from checkpoint
- **adapters/dummy_classifier/train.py**: Standalone training — MNIST/CIFAR-10 via torchvision,
  JSON metric lines to stdout, per-epoch checkpoints with best.pt tracking
- **adapters/dummy_classifier/evaluator.py**: evaluate() returns accuracy, per-class P/R/F1, macro_f1
- **adapters/dummy_classifier/adapter.py**: DummyClassifierAdapter — config_to_yaml, get_train_command,
  parse_metrics (JSON + key=value fallback), get_metrics_mapping (train/val loss + accuracy),
  get_search_ranges (lr/batch_size/epochs), load_model, predict (top-5 with confidence)

### Adapters — Base Interface
- **adapters/base.py**: Added predict(model, image_bytes, **kwargs) optional method
- **adapters/__init__.py**: Registered DummyClassifierAdapter in ADAPTER_REGISTRY

### Backend — Predict API (NEW)
- **backend/api/predict.py**: POST /api/predict/image — multipart form (file, adapter_name,
  checkpoint_path, class_names); in-memory model cache; routes through adapter.predict()
- **backend/main.py**: Registered predict router

### Backend — Genericity Fixes
- **backend/api/search.py**: Changed adapter_name from Form(default="vlm_quantization") to
  Form(...) (required); removed vlm references from docstrings
- **backend/api/system.py**: Changed vlm_quantization comment to generic text
- **backend/api/compat.py**: Changed vlm_quantization docstring to generic "adapter"

### Frontend — Classifier Demo (NEW)
- **frontend/src/pages/ClassifierDemoPage.tsx**: Image upload with drag-and-drop, checkpoint/adapter
  config, calls POST /api/predict/image, displays top prediction + confidence bar chart
- **frontend/src/App.tsx**: Added /demo/classifier route
- **frontend/src/components/Layout.tsx**: Added Shapes icon, Classify Demo nav item

### Frontend — Search API Update
- **frontend/src/api/jobs.ts**: Added adapter_name parameter to searchByText and searchByImage

### Dependencies
- **pyproject.toml**: Added torchvision>=0.15.0

### Documentation
- **docs/new-adapter-guide.md**: Step-by-step guide (8 steps) using dummy_classifier as example
- **README.md**: Updated with adapter plugin system, available adapters table, classifier demo

### Tests
- **tests/test_milestone7.py**: Added 28 new tests in 8 classes:
  - TestDummyClassifierRegistration (3): registry presence, get_adapter, instance type
  - TestSimpleCNN (3): MNIST forward, CIFAR-10 forward, save/load roundtrip
  - TestDummyClassifierAdapter (10): all interface methods including predict
  - TestEvaluator (1): classification report structure
  - TestPredictAPI (2): route existence, router registration
  - TestBaseAdapterPredict (1): raises NotImplementedError on base
  - TestGenericity (4): no forbidden terms in api/schemas/core/predict
  - TestTwoAdaptersCoexist (4): both adapters in registry with different names/metrics/ranges
- 258 tests pass total, 1 skipped, gate.sh PASS

---

# Milestone 6 Progress

## Status: COMPLETE

## Completion Criteria

### Dataset Registration
- [x] "Register Dataset" button on /datasets page
- [x] Input: name, path, format (jsonl/csv/parquet/huggingface/directory), type (image-text/text-only/image-only/tabular/custom)
- [x] Auto-detect: path input → infer format/type/entry count
- [x] Status display: Ready / Raw Only / Not Found / Preparing
- [x] Status computed from file system checks on server

### Split Settings
- [x] Ratio preset: train 80% / val 10% / test 10%
- [x] File-based split: separate files per split
- [x] Field-based split: JSON field value (Karpathy style)
- [x] Custom splits: user-defined split names and filters
- [x] Split preview: per-split sample counts

### Data Preparation
- [x] Prepare button on raw-only datasets (pre-existing from M5)
- [x] Progress tracking via job system (pre-existing)
- [x] Adapter prepare logic (coco_karpathy, jsonl_copy workers)

### Preview
- [x] Dataset click → random 5 samples with auto-rendering
- [x] image-text: thumbnail + caption; text-only: text; tabular: key-value
- [x] Basic stats: entry count, size, language distribution

### Experiment Form Integration
- [x] Dataset selector in experiment creation form
- [x] Ready datasets selectable with checkbox (multi-select)
- [x] Unavailable datasets shown but disabled with status badge
- [x] Selected dataset IDs included in experiment config

### Platform Genericity
- [x] No vlm/siglip/hash terms in core API or shared schemas
- [x] gate.sh PASS (231 tests, 1 skipped, smoke OK)

## Changes Summary

### Shared — New Enums
- **shared/schemas.py**: Added DatasetType (image-text/text-only/image-only/tabular/custom),
  DatasetFormat (jsonl/csv/parquet/huggingface/directory),
  SplitMethod (ratio/file/field/custom/none)

### Backend — Model Expansion
- **models/experiment.py**: Expanded DatasetDefinition with dataset_type, dataset_format,
  split_method, splits_config (JSON), is_seed fields

### Backend — Dataset Registry Service
- **services/dataset_registry.py**: Updated SEED_DATASETS with new fields (type, format,
  split_method, splits_config, is_seed=True); added detect_dataset() with sub-detectors
  for directory/jsonl/json/csv; added compute_split_preview() for ratio/field/file/custom/none;
  added _count_jsonl_lines() and _count_by_field() helpers

### Backend — Dataset API
- **api/datasets.py**: Full CRUD — POST /api/datasets (register), PUT /api/datasets/{id}
  (update), DELETE /api/datasets/{id}; POST /api/datasets/detect (auto-detect from path);
  PUT /api/datasets/{id}/splits (update split config); GET /api/datasets/{id}/splits/preview
  (per-split counts); added CreateDatasetRequest, UpdateDatasetRequest, DetectRequest/Response,
  SplitUpdateRequest/PreviewResponse schemas; added _slugify() helper; duplicate key detection

### Frontend — API Client
- **api/datasets.ts**: Added DatasetType, DatasetFormat, SplitMethod types; updated Dataset
  interface with new fields; added createDataset, updateDataset, deleteDataset, detectDataset,
  updateSplits, previewSplits functions; added payload interfaces

### Frontend — Datasets Page
- **pages/DatasetsPage.tsx**: RegisterModal with auto-detect button, type/format selectors,
  split configuration (ratio/field/custom); SplitInfo component on cards; updated DatasetCard
  with 4-column stats (entries, size, type, format), SEED badge, delete button; updated
  PreviewModal with dataset_type-aware rendering

### Frontend — Experiment Create Page
- **pages/ExperimentCreatePage.tsx**: Added dataset selector section with checkbox multi-select;
  ready datasets selectable, unavailable datasets shown disabled with status badges;
  selected dataset_ids included in experiment config payload

### Tests
- **test_milestone6.py**: Added 19 new tests (sections 13-19): DatasetType/DatasetFormat/
  SplitMethod enum values, model creation with new fields, auto-detect (jsonl/csv/directory/
  json/missing), split preview (ratio/field/none), CRUD request/response schemas, _slugify,
  seed data new fields, genericity checks (no vlm terms in API or schemas)
- 231 tests pass total, 1 skipped, gate.sh PASS

---

# Milestone 5 Progress

## Status: COMPLETE

## Completion Criteria

### Notifications
- [x] Browser Notification on training complete/fail (even in background tabs)
- [x] Settings page with Discord webhook URL input field
- [x] Settings page with Slack webhook URL input field
- [x] Webhook sends on training start/complete/fail (experiment name, status, duration, metrics)
- [x] Failed run notification includes last log lines
- [x] Test Webhook button for both Discord and Slack
- [x] No error if webhook is not configured (browser notification only)

### Experiment Queue
- [x] Add experiments to queue from experiment list ("Add to Queue" button)
- [x] /queue page with drag-and-drop reordering (dnd-kit)
- [x] Status icons (waiting/running/completed/failed/cancelled)
- [x] Auto-start next queued experiment when GPU is free (5s polling scheduler)
- [x] Remove from queue, reorder support
- [x] Configurable concurrency limit (default 1, max 8 in Settings)
- [x] Queue history view

### Platform Genericity
- [x] No vlm-specific terms in notification/queue code
- [x] gate.sh PASS (212 tests, 1 skipped, smoke OK)

## Changes Summary

### Backend — Notification Service
- **services/notifier.py**: Added Slack webhook support (`send_slack_webhook`),
  `test_webhook(provider)` function, Slack calls in `notify_run_started`,
  `notify_run_completed`, `notify_run_failed`; hub settings persistence with
  `slack_webhook_url` field
- **api/settings.py**: Added `slack_webhook_url` to `HubSettingsResponse` and
  `UpdateSettingsRequest`; added `POST /api/settings/test-webhook` endpoint with
  `TestWebhookRequest`/`TestWebhookResponse` schemas

### Backend — Queue System (pre-existing from M4)
- **models/experiment.py**: QueueEntry model (already complete)
- **services/queue_scheduler.py**: 5s polling scheduler with start/stop (already complete)
- **api/queue.py**: Full CRUD — list, add, delete, reorder, history (already complete)

### Frontend — Settings Page
- **SettingsPage.tsx**: Added Slack webhook URL field, Test Webhook buttons
  for both Discord and Slack with send/result feedback
- **api/queue.ts**: Added `slack_webhook_url` to `HubSettings` type,
  `testWebhook(provider)` API function

### Frontend — Experiment List
- **ExperimentListPage.tsx**: Added "Add to Queue" button (ListPlus icon)
  for draft/failed/cancelled/completed experiments

### Frontend — Queue & Notifications (pre-existing)
- **QueuePage.tsx**: Full queue management with dnd-kit, status icons, add modal, history
- **hooks/useNotifications.ts**: WebSocket connection + browser Notification API
- **components/Layout.tsx**: `useNotifications()` at app level

### Tests
- **test_milestone5.py**: 36 tests covering hub settings persistence, Discord/Slack
  webhook construction, notification events (start/complete/fail), test webhook,
  queue model/schemas, scheduler structure, WS endpoint, process manager integration,
  genericity checks, API route existence, lifespan integration
- 212 tests pass total, 1 skipped, gate.sh PASS

---

# Milestone 4 Progress

## Status: COMPLETE

## Tickets

| Ticket | Description | Status |
|--------|-------------|--------|
| T-015 | BaseSearchEngine plugin interface + registry | DONE |
| T-016 | OptunaEngine implementation (with graceful fallback) | DONE |
| T-017 | Adapter get_search_ranges() method | DONE |
| T-018 | Study DB model + API endpoints | DONE (pre-existing) |
| T-019 | Study creation / monitoring frontend | DONE (pre-existing) |
| T-020 | Param importance calculation | DONE (pre-existing) |
| T-021 | Best trial → new experiment button | DONE (pre-existing) |
| T-022 | Fix genericity (val/map_i2t default) | DONE |
| T-023 | Optuna optional dependency + tests | DONE |

## Completion Criteria
- [x] Search setup UI: parameter fixed/search toggle + min/max ranges
- [x] Adapter recommended ranges (get_search_ranges())
- [x] Search engine plugin structure (BaseSearchEngine interface)
- [x] Optuna engine with TPE (real) + random fallback (no optuna)
- [x] Settings: n_trials, search_epochs, subset_ratio, pruner, direction
- [x] Start Search → background job execution
- [x] Trial progress monitoring (current trial # / total)
- [x] Objective value chart (trial-by-trial + best-so-far line)
- [x] Best trial highlight with params summary
- [x] Parameter importance chart (after search completion)
- [x] "Create Experiment from Best Trial" button
- [x] No vlm-specific terms in core code
- [x] gate.sh PASS (176 tests, 1 skipped, smoke OK)

## Changes Summary

### Backend — Search Engine Plugin Interface
- **core/search_engine.py**: BaseSearchEngine ABC with run_search(), get_name(),
  get_param_importance(); engine registry (register_engine/get_engine/list_engines);
  TrialResult/SearchResult dataclasses
- **engines/__init__.py**: Auto-imports OptunaEngine on load
- **engines/optuna_engine.py**: OptunaEngine — uses real optuna.create_study + TPE
  when installed, falls back to random sampling; dummy objective for E2E testing;
  fANOVA param importance via optuna.importance when available

### Backend — Adapter Search Ranges
- **adapters/base.py**: Added get_search_ranges() optional method
- **adapters/vlm_quantization/adapter.py**: Implemented recommended ranges
  (lr, temperature, quantization_weight, balance_weight, hash_dim)

### Backend — Genericity Fix
- **models/experiment.py**: Changed default objective_metric from "val/map_i2t" to "val/loss"
- **schemas/optuna.py**: Same default change in CreateStudyRequest

### Dependencies
- **pyproject.toml**: Added `optuna = ["optuna>=3.0.0"]` as optional dependency

### Tests
- **test_milestone4.py**: 29 tests covering engine registry, run_search, param sampling,
  importance, adapter ranges, schema validation, genericity checks
- 176 tests pass total, 1 skipped, gate.sh PASS

---

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
