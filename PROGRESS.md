# Progress Log

## Milestone 9: Project Registration

### Status: COMPLETE

### Summary
Added the ability for users to register their ML projects through the platform UI.
Projects are scanned automatically to detect git info, Python environment, config files,
and training/eval scripts. Experiments now link to a project via `project_id` FK.

### Tasks
| # | Task | Status |
|---|------|--------|
| 1 | Project model + Alembic migration + project_id FK on ExperimentConfig | DONE |
| 2 | ProjectStatus enum in shared/schemas.py | DONE |
| 3 | Backend Pydantic schemas (project.py) | DONE |
| 4 | Backend service — CRUD + directory scan + git info | DONE |
| 5 | Backend API endpoints (/api/projects CRUD + /scan + /rescan + /git + /configs) | DONE |
| 6 | Frontend types + API client | DONE |
| 7 | ProjectListPage — card grid with status badges | DONE |
| 8 | ProjectCreatePage — 3-step wizard (info → scan → confirm) | DONE |
| 9 | ProjectDetailPage — info cards, config viewer, git info, experiments | DONE |
| 10 | Sidebar "Projects" menu + routing + TopBar title mapping | DONE |

### Files Created
- `backend/schemas/project.py` — Pydantic schemas (ScanRequest/Response, ProjectCreate/Update/Response, ConfigContent, GitInfo)
- `backend/services/project_service.py` — ProjectService CRUD + scan_directory + git info + config reader
- `backend/api/projects.py` — REST API: CRUD, scan, rescan, git info, config content
- `alembic/versions/eada77caf3d3_add_projects_table_and_experiment_.py` — Migration for projects table + experiment_configs.project_id FK
- `frontend/src/types/project.ts` — TypeScript types (Project, ScanResponse, GitInfo, ConfigContent, etc.)
- `frontend/src/api/projects.ts` — API client (getProjects, createProject, scanDirectory, etc.)
- `frontend/src/pages/ProjectListPage.tsx` — Card grid with status/type/env badges, skeleton loading, empty state
- `frontend/src/pages/ProjectCreatePage.tsx` — 3-step registration wizard with real-time path scanning
- `frontend/src/pages/ProjectDetailPage.tsx` — Detail view with config viewer, git info, scripts, experiments

### Files Modified
- `shared/schemas.py` — Added ProjectStatus enum
- `backend/models/experiment.py` — Added Project model, added project_id FK + relationship on ExperimentConfig
- `backend/models/__init__.py` — Exported Project
- `backend/main.py` — Registered projects router
- `backend/schemas/experiment.py` — Added project_id to ExperimentResponse
- `alembic/env.py` — Import Project model
- `frontend/src/types/experiment.ts` — Added project_id to Experiment interface
- `frontend/src/App.tsx` — Added project routes (/projects, /projects/new, /projects/:id)
- `frontend/src/components/Layout.tsx` — Added Projects nav item (FolderGit2 icon) above Experiments, TopBar title mapping

### Key Features
- **Directory scanning**: Auto-detects git repo, Python env (uv/venv/conda/pip), config files, train/eval scripts
- **3-step wizard**: Basic info → scan results + configuration → confirmation & register
- **Real-time validation**: Path existence, git detection, env detection shown live during input
- **Config viewer**: Click any detected config file to view its contents in the detail page
- **Git integration**: Shows branch, last commit, dirty status on project detail page
- **Experiment linking**: ExperimentConfig.project_id FK connects experiments to projects
- **Suggested commands**: Auto-generates train/eval command templates based on detected env and scripts

### Gate
- 258 tests passed, 0 failures
- Lint clean (ruff check + format)
- TypeScript clean (tsc --noEmit)
- Smoke test passed

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
