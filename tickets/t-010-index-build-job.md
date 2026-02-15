# T-010: Index Build Job API + Frontend

## Objective
Index build job endpoint + UI integration.

## API
- POST /api/jobs/index-build — {run_id, checkpoint, config}
- Progress tracking via DB updates

## Frontend
- "Build Search Index" button on run page
- Progress bar during build
- Index status indicator

## Acceptance Criteria
- [ ] Index build job launches subprocess
- [ ] Progress tracked in DB
- [ ] Index file saved to disk (.pt)
- [ ] gate.sh PASS

## Status: PENDING
