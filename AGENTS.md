# AGENTS.md (Codex) — ml-experiment-hub

## Goal
Small, reviewable PRs for ML/DL training & evaluation platform.

## Non-negotiables
- One ticket = one PR.
- Do NOT touch secrets or leak tokens/paths in logs.
- Keep changes minimal; avoid refactors unless requested.

## Gate
Run: ./scripts/gate.sh

## ML guidelines
- Reproducibility first: seeds/config snapshots/dataset versioning if present.
- Any pipeline change must include a smoke path (tiny run).
- Metrics should be deterministic for identical inputs.

# AGENTS.md (Codex Pro)

## Goal
Implement requested features end-to-end with minimal diffs and passing Gate.

## Must Do
- Run `./scripts/gate.sh` before finishing.
- Add/extend UI and API routes as requested.
- Keep changes scoped and documented.

## Must NOT Do
- Do not modify secrets or add tokens.
- Do not run destructive commands.

## Default assumptions
- If UI framework is Next.js: implement pages + API routes under /app or /pages.
- If backend is FastAPI: add endpoints under backend/api and use existing service patterns.
- If unknown, scan repository and choose the most consistent approach already used in codebase.
