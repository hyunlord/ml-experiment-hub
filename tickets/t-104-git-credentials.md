# T-104: Git Credentials CRUD API

## Objective
Implement CRUD endpoints for git credential management (tokens for private repos).

## Non-goals
- No OAuth integration
- No encryption at rest (plain storage for MVP, noted for future improvement)
- No frontend settings UI (existing SettingsPage will be updated separately)

## Scope
Files to touch:
- `backend/api/settings.py` — Add git-credentials endpoints (POST, GET, DELETE)
- `backend/services/git_credential_service.py` — NEW: CRUD service with token masking

## Acceptance Criteria
- [ ] POST /api/settings/git-credentials — creates credential
- [ ] GET /api/settings/git-credentials — lists credentials with masked tokens (ghp_****xxxx)
- [ ] DELETE /api/settings/git-credentials/{id} — deletes credential
- [ ] Token masking: show first 4 + last 4 chars only
- [ ] Gate passes

## Risk Notes
- Tokens stored as plain text in SQLite for MVP
- Production: should use encryption (Fernet or similar)
