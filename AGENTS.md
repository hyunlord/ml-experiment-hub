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
