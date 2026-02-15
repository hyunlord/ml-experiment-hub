# T-106: Frontend Types + API Client Update

## Objective
Update TypeScript types and API client to support all new backend features (clone, browse, upload, templates, git credentials).

## Non-goals
- No page/component changes (T-107, T-108)

## Scope
Files to touch:
- `frontend/src/types/project.ts` — Add source_type, git_branch, template fields, CloneJobStatus, FileBrowseEntry, TemplateInfo, GitCredential types
- `frontend/src/api/projects.ts` — Add cloneProject, getCloneStatus, pullProject, uploadFiles, browseFilesystem, getTemplates, git credential methods

## Acceptance Criteria
- [ ] All new backend response types have TypeScript interfaces
- [ ] API client has methods for all new endpoints
- [ ] tsc --noEmit passes
- [ ] Gate passes

## Risk Notes
- Must match backend schemas exactly
