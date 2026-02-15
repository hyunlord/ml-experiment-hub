# T-105: Template Registry

## Objective
Implement a template registry that provides predefined project templates for common ML frameworks and tasks.

## Non-goals
- No actual code generation from templates (just metadata/schema for now)
- No HuggingFace Hub auto-complete
- No frontend UI (T-107)

## Scope
Files to touch:
- `backend/services/template_registry.py` — NEW: Template definitions + registry
- `backend/api/templates.py` — NEW: GET /api/templates, GET /api/templates/{id}/schema
- `backend/main.py` — Register templates router

## Acceptance Criteria
- [ ] GET /api/templates returns list of available templates
- [ ] Each template has: id, framework, name, description, tasks[]
- [ ] GET /api/templates/{id}/schema returns config schema for template
- [ ] Templates: pytorch-lightning, huggingface, plain-pytorch, custom-script
- [ ] Tasks per framework (e.g., image-classification, causal-lm, etc.)
- [ ] Gate passes

## Risk Notes
- Hardcoded templates for now — future: user-defined templates
