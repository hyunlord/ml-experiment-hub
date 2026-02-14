# T-004: Fix Compare frontend page

## Objective
Fix the ExperimentComparePage data fetching and route.

## Issues
1. Route mismatch: list navigates to `/experiments/compare?ids=...` but App.tsx route is `/compare`
2. Compare page calls `/experiments/${id}/metrics` which doesn't exist
3. Need to fetch experiment's runs, then latest run's metrics

## Files to touch
- `frontend/src/App.tsx` — fix route path
- `frontend/src/pages/ExperimentComparePage.tsx` — fix data fetching
- `frontend/src/pages/ExperimentListPage.tsx` — fix compare navigation URL

## Acceptance criteria
- Compare button in experiment list navigates to correct route
- Compare page loads experiment data + metrics from latest runs
- Config diff table shows differences highlighted
- Metric overlay charts work with recharts
- Final metrics table shows best with trophy emoji
