# T-107: ProjectCreatePage — 4-Tab Registration UI

## Objective
Rewrite ProjectCreatePage with 4-tab UI: GitHub, Local Path, Template, Upload.

## Non-goals
- No HuggingFace Hub auto-complete in Template tab
- No real-time log streaming for clone progress (polling only)

## Scope
Files to touch:
- `frontend/src/pages/ProjectCreatePage.tsx` — Complete rewrite with 4 tabs

## Acceptance Criteria
- [ ] 4 tabs at top: GitHub / Local Path / Template / Upload
- [ ] GitHub tab: URL + branch input → Clone button → progress → scan results → configure → register
- [ ] Local Path tab: path input + Browse button → file browser modal → auto-scan → configure → register
- [ ] Template tab: framework cards → task selection → model input → basic config → register
- [ ] Upload tab: drag-and-drop zone → file list → auto-scan → configure → register
- [ ] Private repo checkbox → git credential dropdown (GitHub tab)
- [ ] Step 2 (scan results) shared across GitHub/Local/Upload tabs
- [ ] Step 3 (confirm + register) shared across all tabs
- [ ] tsc --noEmit passes
- [ ] Gate passes

## Risk Notes
- Large component — consider extracting tab content into sub-components
- Clone polling needs cleanup on unmount
