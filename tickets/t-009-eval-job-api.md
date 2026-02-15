# T-009: Eval Job API + Frontend

## Objective
Eval job endpoint + RunMonitor page integration.

## API
- POST /api/jobs/eval — {run_id, checkpoint, bit_lengths}
- GET /api/jobs/{job_id} — job status + progress + results
- GET /api/jobs?type=eval&run_id=X — list eval jobs for a run

## Frontend
- RunMonitorPage: "Run Evaluation" button
- Checkpoint selector (best/latest/epoch)
- Progress bar during eval
- Results table: per-bit mAP, P@K

## Acceptance Criteria
- [ ] Eval job launches subprocess
- [ ] Progress tracked in DB (0-100%)
- [ ] Results stored as job.result_json
- [ ] Frontend shows eval button + results
- [ ] gate.sh PASS

## Status: PENDING
