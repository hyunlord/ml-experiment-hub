# T-008: Job Model + Management Service

## Objective
Create a Job system for eval/index-build tasks. Jobs run as subprocesses
with DB-based progress tracking (not stdout parsing).

## Files to Create/Modify
- `backend/models/experiment.py` — Add Job model
- `backend/services/job_manager.py` — JobManager service
- `shared/schemas.py` — Add JobStatus, JobType enums
- `backend/schemas/job.py` — Job request/response schemas
- DB migration (alembic or auto-create)

## Job Model Fields
- id, type (eval/index_build), run_id, status, progress (0-100)
- config_json, result_json, error_message
- started_at, ended_at

## Acceptance Criteria
- [ ] Job model created with proper relationships
- [ ] JobManager: create_job, update_progress, get_job, list_jobs
- [ ] Progress updated via internal API (not stdout)
- [ ] gate.sh PASS

## Status: PENDING
