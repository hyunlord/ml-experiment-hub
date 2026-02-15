# T-101: Enhanced Scan Service

## Objective
Extend the project scan to detect directory structure, parse requirements/dependencies, and include git last commit info.

## Non-goals
- No model changes (T-100)
- No new API endpoints (scan endpoint already exists)
- No frontend changes

## Scope
Files to touch:
- `backend/schemas/project.py` — Add StructureInfo, GitLastCommit to ScanResponse
- `backend/services/project_service.py` — Add _detect_structure(), _parse_requirements(), _get_last_commit(); update scan_directory()

## Acceptance Criteria
- [ ] ScanResponse includes `structure: {has_src, has_tests, has_docker, main_dirs}`
- [ ] ScanResponse includes `git_last_commit: {hash, message, date}`
- [ ] ScanResponse includes `requirements: ["torch", "transformers", ...]`
- [ ] Existing scan tests still pass
- [ ] Gate passes

## Risk Notes
- requirements parsing from pyproject.toml needs toml library — use tomllib (stdlib in 3.11+)
