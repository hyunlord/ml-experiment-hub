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

## Autopilot workflow (NO follow-up questions)
When the user gives a feature request:
1) Create an implementation plan and split it into 3–7 tickets.
2) Implement tickets in order, making small commits.
3) After each ticket, run the Gate: `./scripts/gate.sh`.
4) If Gate fails, fix and re-run until it passes.
5) Do not ask the user for additional commands. Only ask questions if something is truly ambiguous; otherwise make reasonable defaults.
6) Prefer using Codex Pro for isolated implementation tickets and keep Claude as integrator/reviewer.
7) End by summarizing what changed and how to run the demo end-to-end.

- For implementation tickets, call `./tools/codex_ticket.sh "<ticket prompt>"` to delegate to Codex.

