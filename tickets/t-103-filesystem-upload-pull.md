# T-103: Filesystem Browse + File Upload + Git Pull APIs

## Objective
Add filesystem browsing for local path selection, file upload for project scripts, and git pull for GitHub projects.

## Non-goals
- No recursive deep scanning (single directory level only for browse)
- No file editing or deletion through browse API
- No frontend UI (T-107)

## Scope
Files to touch:
- `backend/api/filesystem.py` — NEW: GET /api/filesystem/browse with security restrictions
- `backend/api/projects.py` — Add POST /{id}/pull, POST /upload
- `backend/main.py` — Register filesystem router

## Acceptance Criteria
- [ ] GET /api/filesystem/browse?path=... returns [{name, type, size, modified}]
- [ ] Browse restricted to PROJECTS_STORE_DIR and allowed paths (/home, /data, /tmp)
- [ ] POST /api/projects/upload accepts multipart files, saves to PROJECTS_STORE_DIR
- [ ] POST /api/projects/{id}/pull runs git pull on GitHub-sourced projects
- [ ] Security: path traversal attacks blocked (resolve + startswith check)
- [ ] Gate passes

## Risk Notes
- Filesystem browse is a security-sensitive API — strict path validation required
- Upload size limits needed (default 100MB per file)
