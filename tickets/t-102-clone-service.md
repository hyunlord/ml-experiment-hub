# T-102: GitHub Clone Service + API

## Objective
Implement async GitHub repo cloning with job tracking, progress reporting, and auto-scan on completion.

## Non-goals
- No private repo OAuth (token-based only via GitCredential)
- No branch switching after clone
- No frontend UI (T-107)

## Scope
Files to touch:
- `backend/services/clone_service.py` — NEW: CloneService with async subprocess, job store, progress tracking
- `backend/api/projects.py` — Add POST /clone, GET /clone/{job_id}

## Acceptance Criteria
- [ ] POST /api/projects/clone accepts {git_url, branch, token_id?, subdirectory?}
- [ ] Returns {job_id, status: "started"}
- [ ] GET /api/projects/clone/{job_id} returns {status, progress, local_path, scan_result?, error?}
- [ ] Clones to PROJECTS_STORE_DIR/{repo_name}_{short_hash}/
- [ ] Uses `git clone --depth 1 --branch {branch}`
- [ ] Private repos use token from GitCredential
- [ ] Auto-scans directory after clone completes
- [ ] Gate passes

## Risk Notes
- In-memory job store (dict) — jobs lost on server restart. Acceptable for MVP.
- Large repos: async subprocess with timeout protection
