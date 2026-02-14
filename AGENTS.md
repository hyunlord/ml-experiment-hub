# AGENTS.md (Codex Working Agreement) — ml-experiment-hub

## Goal
Implement small PRs for ML/DL training & evaluation platform.

## Non-negotiables
- One ticket = one PR.
- Do NOT touch secrets (.env, credentials, keys).
- Do NOT leak tokens/paths in logs.
- Avoid refactors unless explicitly requested.

## Gate checks
Run: ./scripts/gate.sh

## ML platform guidelines
- Preserve reproducibility: seed/config snapshot/dataset versioning if present.
- Any pipeline change must include a smoke test (tiny run).
- Metrics must be deterministic for identical inputs.

## PR checklist
- [ ] Scoped to ticket
- [ ] ./scripts/gate.sh passes
- [ ] Smoke path exists or updated
- [ ] Tests added/updated
- [ ] No secrets/log leaks
