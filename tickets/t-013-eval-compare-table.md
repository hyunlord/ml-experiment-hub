# T-013: Eval Results Comparison Table

## Objective
Compare eval results across checkpoints in a table UI.

## Features
- Select multiple eval jobs to compare
- Table: rows = bit lengths, columns = checkpoints
- Cells: mAP, P@1, P@5, P@10
- Best value highlighted per row

## Acceptance Criteria
- [ ] GET /api/jobs?type=eval&run_id=X lists all evals
- [ ] Frontend comparison table renders
- [ ] Best values highlighted
- [ ] gate.sh PASS

## Status: PENDING
