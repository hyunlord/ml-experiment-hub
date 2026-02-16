# Progress Log

## Milestone 10: Experiment Create Page Redesign

### Status: COMPLETE

### Summary
Full redesign of the experiment creation page with a config-driven workflow. Users now select
a project, pick a base config YAML file, and get an auto-generated editable form with type-aware
inputs. Three view modes (Form/YAML/Diff) provide flexibility for editing and reviewing changes.
Backend config parser service reads YAML files, infers value types, and groups parameters.

### Tasks
| # | Task | Status |
|---|------|--------|
| T-120 | Backend config parser service (YAML parse + type inference + grouping) | DONE |
| T-121 | Backend API endpoint + schema changes (parse-config, ExperimentCreate extension) | DONE |
| T-122 | Frontend API client + types for config parsing | DONE |
| T-123 | Frontend ExperimentCreatePage full redesign (Form/YAML/Diff views) | DONE |
| T-124 | Gate verification + commit | DONE |

### New Files Created
- `backend/services/config_parser.py` — YAML/JSON config parser with type inference (string, integer, float, boolean, array, object) and top-level key grouping

### Files Modified
- `backend/api/projects.py` — Added `POST /{project_id}/parse-config` endpoint
- `backend/schemas/project.py` — Added `ParseConfigRequest`, `ParseConfigResponse` schemas
- `backend/schemas/experiment.py` — Added `project_id`, `base_config_path` to `ExperimentCreate`
- `backend/services/experiment_service.py` — Pass `project_id` on experiment creation
- `frontend/src/types/project.ts` — Added `ParsedConfigValue`, `ParsedConfigResponse` types
- `frontend/src/api/projects.ts` — Added `parseConfig()` API function
- `frontend/src/pages/ExperimentCreatePage.tsx` — Complete rewrite (1200+ lines)

### New API Endpoints
| Method | Path | Description |
|--------|------|-------------|
| POST | /api/projects/{id}/parse-config | Parse project config YAML into typed groups |

### Key Features
- **Project-first workflow**: Select project → pick config file → auto-parse → edit → create
- **Config parser**: Reads YAML/JSON, infers types, groups by top-level keys, preserves raw content
- **Form View**: Collapsible groups with type-specific inputs (text, number with step, boolean toggle, array tags, object JSON)
- **YAML View**: Raw YAML editing with Apply button for one-way sync to form
- **Diff View**: Line-by-line comparison of original vs modified config with color highlighting
- **Change tracking**: Blue dot indicators on modified fields, change count badge on Diff tab
- **Per-field actions**: Copy to clipboard, reset to original, delete parameter (on hover)
- **Add Parameter**: Dialog to add new parameters with group/key/type/value selection
- **Query param linking**: `?project_id=X&config=Y` from ProjectDetailPage for deep-linking
- **Auto-naming**: Experiment name auto-generated as `{project}_{configName}_001`
- **Confirmation dialogs**: Warn before switching project/config with unsaved changes

### Gate
- 258 tests passed, 0 failures
- Lint clean (ruff check + format)
- TypeScript clean (tsc --noEmit)
- Smoke test passed

---

## Milestone 9 v2: Enhanced Project Registration (4 Source Types)

### Status: COMPLETE

### Summary
Major expansion of project registration to support 4 source types: GitHub clone, Local Path,
Template selection, and File Upload. Added async clone service with progress tracking,
filesystem browser API, template registry, git credentials management, and a 4-tab
registration wizard UI.

### Tasks (v2 expansion)
| # | Task | Status |
|---|------|--------|
| T-100 | Models + Migration + Config (GitCredential, extended Project, PROJECTS_STORE_DIR) | DONE |
| T-101 | Enhanced scan service (git_last_commit, structure, requirements) | DONE |
| T-102 | Clone service + API (async clone with job tracking) | DONE |
| T-103 | Filesystem browse + Upload + Git Pull APIs | DONE |
| T-104 | Git credentials CRUD (token masking) | DONE |
| T-105 | Template registry (4 frameworks, tasks, config schemas) | DONE |
| T-106 | Frontend types + API client (clone, upload, browse, templates, credentials) | DONE |
| T-107 | ProjectCreatePage 4-tab wizard (GitHub/Local/Template/Upload) | DONE |
| T-108 | ProjectDetail + ListPage updates (source_type badges, Pull Latest, template info) | DONE |

### New Files Created
- `backend/services/clone_service.py` — Async git clone with progress tracking (in-memory job store)
- `backend/services/git_credential_service.py` — GitCredential CRUD with token masking
- `backend/services/template_registry.py` — Template definitions (PyTorch Lightning, HuggingFace, Plain PyTorch, Custom)
- `backend/api/filesystem.py` — Filesystem browse API with security path restrictions
- `backend/api/templates.py` — Template list + schema endpoints
- `alembic/versions/b3f9a1c2d4e5_extend_projects_add_git_credentials.py` — Migration: git_credentials table + new project columns
- `frontend/src/api/filesystem.ts` — browseDirectory() API client
- `frontend/src/api/templates.ts` — getTemplates(), getTemplateSchema() API client
- `frontend/src/api/gitCredentials.ts` — getGitCredentials(), createGitCredential(), deleteGitCredential()

### Files Modified
- `shared/schemas.py` — Added CLONING to ProjectStatus
- `backend/config.py` — Added PROJECTS_STORE_DIR setting
- `backend/models/experiment.py` — Added GitCredential model, extended Project with source_type/git_branch/git_token_id/template fields
- `backend/models/__init__.py` — Export GitCredential
- `backend/schemas/project.py` — Added CloneRequest/Response, FileBrowse, Upload, GitCredential, Template schemas; extended ProjectCreate/Response
- `backend/services/project_service.py` — Enhanced scan: git_last_commit, structure detection, requirements parsing
- `backend/api/projects.py` — Added clone, upload, pull endpoints
- `backend/api/settings.py` — Added git-credentials CRUD endpoints
- `backend/main.py` — Registered filesystem + templates routers
- `alembic/env.py` — Import GitCredential
- `frontend/src/types/project.ts` — All new types (Clone, Browse, Upload, Credential, Template, GitLastCommit, StructureInfo)
- `frontend/src/api/projects.ts` — Added cloneRepository, getCloneStatus, uploadProjectFiles, pullProject
- `frontend/src/pages/ProjectCreatePage.tsx` — Complete rewrite: 4-tab wizard (GitHub/Local/Template/Upload)
- `frontend/src/pages/ProjectDetailPage.tsx` — Source type badge, Pull Latest button, git branch display, template info card
- `frontend/src/pages/ProjectListPage.tsx` — Source type badge with icon, git URL display

### New API Endpoints
| Method | Path | Description |
|--------|------|-------------|
| POST | /api/projects/clone | Start async GitHub clone |
| GET | /api/projects/clone/{job_id} | Get clone job status |
| POST | /api/projects/upload | Upload project files |
| POST | /api/projects/{id}/pull | Git pull (GitHub projects only) |
| GET | /api/filesystem/browse | Browse server directories |
| GET | /api/templates | List available templates |
| GET | /api/templates/{id} | Get template details |
| GET | /api/templates/{id}/schema | Get template config schema |
| POST | /api/settings/git-credentials | Store git credential |
| GET | /api/settings/git-credentials | List credentials (masked) |
| DELETE | /api/settings/git-credentials/{id} | Delete credential |

### Key Features
- **4 registration methods**: GitHub URL+clone, Local Path+browse, Template selection, File upload
- **Async clone**: Shallow clone (--depth 1) with progress polling, auto-scan on completion
- **Filesystem browser**: Modal directory tree for local path selection, security-restricted paths
- **Template registry**: PyTorch Lightning, HuggingFace, Plain PyTorch, Custom Script with task-specific configs
- **Git credentials**: Token storage with masking (first 4 + last 4 chars), private repo support
- **Enhanced scan**: Structure detection (src/tests/docker), requirements parsing, git last commit
- **Source type badges**: Visual indicators on list and detail pages with distinct colors/icons
- **Pull Latest**: One-click git pull for GitHub-sourced projects with auto-rescan

### Gate
- 258 tests passed, 0 failures
- Lint clean (ruff check + format)
- TypeScript clean (tsc --noEmit)
- Smoke test passed

---

## Milestone 9 v1: Basic Project Registration

### Status: COMPLETE (merged as PR #22)

Basic project registration with CRUD API, 3-step wizard, and directory scanning.

---

## Previous Milestones

### M8: System Monitor Enhancement + Multi-Server Support
GPU/CPU/RAM/Disk/Net monitoring, multi-server registration, history charts, alert thresholds, remote agent.

### M1-M4: Core Platform
Experiment CRUD, run orchestration, metrics, schemas, datasets, HP search (Optuna).

### M5: Queue & Notifications
Experiment queue, scheduler, Discord/Slack webhooks, browser notifications.

### M6: Search Engine Plugin Interface
Generic search adapter registry, Optuna search engine.

### M7: Adapter Plugin System
Generic model adapter registry, dummy_classifier reference adapter, adapter guide.

---

## DB Path Unification Fix — 2026-02-16

### Status: ✅ COMPLETE

### Context
Fix database path mismatch where alembic creates DB at `/app/ml_experiments.db` (with migrations) but the app uses `/data/ml_hub.db` (without migrations), causing 500 errors. Unify all DB path references to `/app/data/ml_hub.db`.

### Root Cause Analysis
- **Alembic**: Reads from `alembic.ini` → `sqlite+aiosqlite:///./ml_experiments.db` → creates `/app/ml_experiments.db`
- **Backend app**: Reads from `docker-compose.yml` env var → `sqlite+aiosqlite:////data/ml_hub.db` → uses `/data/ml_hub.db`
- **alembic/env.py**: Currently reads from alembic.ini, does NOT read from backend.config.settings
- Result: Two different databases, app uses the one without migrations

### Tickets
| Ticket | Title | Action | Dispatch Tool | Reason |
|--------|-------|--------|---------------|--------|
| t-001 | Unify DB path configuration | 🔴 DIRECT | — | Atomic config change across 6 files; infrastructure wiring |

### Dispatch ratio: 0/1 = 0% (Infrastructure fix, all DIRECT)

### Dispatch strategy
N/A — Single atomic configuration change

### Implementation Plan
1. **backend/config.py**: Change default to `sqlite+aiosqlite:///./data/ml_hub.db`
2. **alembic.ini**: Change to placeholder (will be overridden by env.py)
3. **alembic/env.py**: Read DATABASE_URL from backend.config.settings
4. **docker-compose.yml**: Change to `DATABASE_URL=sqlite+aiosqlite:////app/data/ml_hub.db`
5. **backend/entrypoint.sh**: Add `mkdir -p /app/data` before migrations
6. **backend/Dockerfile**: Add `/app/data` to RUN mkdir command

### Files Modified
- backend/config.py — Changed default to `sqlite+aiosqlite:///./data/ml_hub.db`
- alembic.ini — Changed to placeholder (will be overridden by env.py)
- alembic/env.py — Added backend.config import, set sqlalchemy.url from settings.DATABASE_URL
- docker-compose.yml — Changed to `DATABASE_URL=sqlite+aiosqlite:////app/data/ml_hub.db`
- backend/entrypoint.sh — Added `mkdir -p /app/data`
- backend/Dockerfile — Added `/app/data` to RUN mkdir command

### Gate Results
- ✅ 258 tests passed, 1 skipped
- ✅ Lint/format clean (96 files formatted)
- ✅ Mypy errors are pre-existing (yaml/psutil stubs - expected)
- ✅ Smoke test passed

### Docker Verification Steps
After rebuilding containers, verify the fix:
```bash
# 1. Clean up old containers and volumes
docker compose down -v

# 2. Rebuild and start
docker compose up -d --build

# 3. Verify DB created at correct path with migrations
docker compose exec backend python -c "
import sqlite3
conn = sqlite3.connect('/app/data/ml_hub.db')
cols = conn.execute('PRAGMA table_info(experiment_configs)').fetchall()
print('Columns:', [c[1] for c in cols])
print('project_name present:', 'project_name' in [c[1] for c in cols])
conn.close()
"

# 4. Test API endpoint
curl http://localhost:8002/api/experiments
# Should return 200, not 500
```

### Summary
All database path references unified to `/app/data/ml_hub.db`. Both alembic migrations and the backend app now use the same database path through environment variable configuration. The alembic.ini placeholder is overridden by alembic/env.py reading from backend.config.settings, ensuring a single source of truth.
