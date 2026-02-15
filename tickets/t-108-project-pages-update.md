# T-108: ProjectDetailPage + ProjectListPage Updates

## Objective
Update project detail and list pages to show source_type, pull functionality, and enhanced git info.

## Non-goals
- No experiment creation form changes (future ticket)

## Scope
Files to touch:
- `frontend/src/pages/ProjectDetailPage.tsx` — Add source_type badge, Pull Latest button, enhanced git display
- `frontend/src/pages/ProjectListPage.tsx` — Add source_type badge/icon on cards

## Acceptance Criteria
- [ ] Detail page shows source_type badge (GitHub/Local/Template/Upload)
- [ ] Detail page has "Pull Latest" button for GitHub-sourced projects
- [ ] Pull triggers POST /api/projects/{id}/pull and refreshes
- [ ] List page cards show source_type icon
- [ ] tsc --noEmit passes
- [ ] Gate passes

## Risk Notes
- Pull operation may take time — show loading state
