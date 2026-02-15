# T-014: Milestone 3 Smoke Test

## Objective
End-to-end smoke test: dummy model → tiny index build → 1 query search
completes within 90 seconds.

## Test Flow
1. Load dummy checkpoint
2. Build tiny index (10 images + captions)
3. Run text search query
4. Run image search query
5. Verify results have correct format

## Acceptance Criteria
- [ ] Smoke test completes < 90 seconds
- [ ] Index build produces valid .pt file
- [ ] Text search returns ranked results
- [ ] Image search returns ranked results
- [ ] gate.sh PASS

## Status: PENDING
