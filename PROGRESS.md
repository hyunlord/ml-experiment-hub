# Progress Log

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
