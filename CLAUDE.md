# CLAUDE.md — ml-experiment-hub (Lead)

## Role
Lead engineer: architecture, integration, refactors, data model boundaries.

## Worktree rules
- Work here: ml-experiment-hub-wt/lead (Claude Code)
- Tickets: ml-experiment-hub-wt/t-<id>-<slug> (Codex Pro)
- Gate: ml-experiment-hub-wt/gate (Codex CLI verification)

## Guardrails
- Reproducibility and evaluation integrity are non-negotiable.
- Separate API/scheduler/worker/artifacts/metadata DB/UI.
- Add a smoke test for any training/eval change.

## Delegation template for Codex tickets
- Objective / Non-goals
- Files/dirs to touch
- Acceptance criteria: tests + ./scripts/gate.sh
- Risk notes: cost/perf/security
