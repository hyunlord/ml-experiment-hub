# T-007: Dummy Checkpoint + Test Data Generation

## Objective
Create a dummy checkpoint (random weights, tiny model) and test dataset
(10 images + captions) for smoke tests without requiring real SigLIP2.

## Files to Create
- `scripts/create_dummy_checkpoint.py`
- `tests/fixtures/dummy_checkpoint.pt` (generated)
- `tests/fixtures/dummy_images/` (10 tiny images)
- `tests/fixtures/dummy_captions.json`

## Acceptance Criteria
- [ ] Script generates reproducible checkpoint
- [ ] DummyBackbone loads checkpoint and encodes
- [ ] 10 test images (32x32 random) + 10 captions available
- [ ] gate.sh PASS

## Status: PENDING
