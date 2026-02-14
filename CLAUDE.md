# CLAUDE.md — ml-experiment-hub (Lead / Integration)

## Role
Lead engineer: architecture, integration, refactors, data model boundaries.

## Branch/worktree rules
- Work in: ml-experiment-hub-wt/lead
- Ticket branches: t/<id>-<slug>
- Gate checks: ./scripts/gate.sh (run in gate worktree)

## Guardrails
- Reproducibility first (seed/config/dataset version).
- Clear separation: API / scheduler / worker / artifact store / metadata DB / UI.
- Evaluation integrity: deterministic metrics and saved artifacts with lineage.

## Delegation format for Codex tickets
Include:
- Objective / Non-goals
- Files/dirs to touch
- Acceptance criteria (tests + smoke + gate)
- Risk notes (cost/perf/security)
