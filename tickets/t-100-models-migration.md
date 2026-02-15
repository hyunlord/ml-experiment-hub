# T-100: Project Model Expansion + GitCredential + Migration

## Objective
Extend Project model with 4 source types (github/local/template/upload), add GitCredential model for private repos, and create Alembic migration.

## Non-goals
- No API endpoint changes (handled in T-102–T-105)
- No frontend changes
- No service logic changes

## Scope
Files to touch:
- `shared/schemas.py` — Add CLONING to ProjectStatus
- `backend/models/experiment.py` — Extend Project model fields, add GitCredential model
- `backend/models/__init__.py` — Export GitCredential
- `backend/schemas/project.py` — Add source_type, git_branch, template fields to schemas; add GitCredential schemas; add CloneRequest/Response, FileBrowseEntry, UploadResponse schemas
- `backend/config.py` — Add PROJECTS_STORE_DIR setting
- `alembic/versions/` — New migration for Project field additions + git_credentials table

## Acceptance Criteria
- [ ] ProjectStatus has CLONING value
- [ ] Project model has: source_type, git_branch, git_token_id (FK→git_credentials), template_type, template_task, template_model, local_path (renamed from path)
- [ ] GitCredential model exists with: id, name, provider, token, created_at
- [ ] PROJECTS_STORE_DIR in Settings (default: ./projects)
- [ ] Alembic migration applies cleanly
- [ ] All existing tests pass
- [ ] Gate passes: ./scripts/gate.sh

## Risk Notes
- Renaming `path` to `local_path` on Project model will break existing code referencing `project.path` — must update all references
- Migration must handle existing data (add columns with defaults, rename column)
