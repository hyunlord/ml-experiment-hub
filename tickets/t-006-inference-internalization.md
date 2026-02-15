# T-006: Inference Code Internalization

## Objective
Re-implement inference-only code from vlm_quantization into adapters/vlm_quantization/.
No imports from the original project. Training code excluded.

## Files to Create
- `adapters/vlm_quantization/__init__.py`
- `adapters/vlm_quantization/hash_layer.py` — NestedHashLayer + sign
- `adapters/vlm_quantization/model.py` — inference wrapper (load checkpoint → encode)
- `adapters/vlm_quantization/evaluator.py` — mAP, P@K computation
- `adapters/vlm_quantization/search.py` — hamming search + cosine search
- `adapters/vlm_quantization/index_builder.py` — build_index logic
- `adapters/vlm_quantization/adapter.py` — BaseAdapter implementation

## Acceptance Criteria
- [ ] All modules importable without vlm_quantization dependency
- [ ] DummyBackbone works as SigLIP2 stand-in for testing
- [ ] NestedHashLayer produces multi-resolution binary codes
- [ ] Hamming distance + cosine similarity search works
- [ ] mAP / P@K evaluation runs on dummy data
- [ ] gate.sh PASS

## Status: PENDING
