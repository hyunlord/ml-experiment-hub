"""Tests for Milestone 3: evaluation and search demo.

Covers:
1. NestedHashLayer forward pass and multi-resolution codes
2. CrossModalHashModel encode_image / encode_text
3. Hamming distance and search
4. mAP / P@K evaluation metrics
5. Index build + load round-trip
6. Job model and schemas
7. Smoke test: dummy checkpoint → index build → search
"""

import json
from datetime import datetime
from pathlib import Path

import pytest
import torch

from adapters.vlm_quantization.evaluator import (
    evaluate_retrieval,
    hamming_distance,
    mean_average_precision,
    precision_at_k,
    to_binary_01,
)
from adapters.vlm_quantization.hash_layer import NestedHashLayer
from adapters.vlm_quantization.model import CrossModalHashModel, ModelConfig, load_model
from adapters.vlm_quantization.search import hamming_search, cosine_search

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# =============================================================================
# 1. NestedHashLayer tests
# =============================================================================


def test_hash_layer_output_shape() -> None:
    """NestedHashLayer should produce correct output shapes."""
    layer = NestedHashLayer(input_dim=256, bit_list=[8, 16, 32])
    layer.eval()
    x = torch.randn(4, 256)

    out_8 = layer(x, bit_length=8)
    out_16 = layer(x, bit_length=16)
    out_32 = layer(x, bit_length=32)

    assert out_8.shape == (4, 8)
    assert out_16.shape == (4, 16)
    assert out_32.shape == (4, 32)


def test_hash_layer_binary_values() -> None:
    """Binary codes should only contain {-1, +1}."""
    layer = NestedHashLayer(input_dim=128, bit_list=[16])
    layer.eval()
    x = torch.randn(8, 128)
    codes = layer(x, bit_length=16, binary=True)

    unique_values = codes.unique().tolist()
    assert set(unique_values).issubset({-1.0, 1.0})


def test_hash_layer_continuous_values() -> None:
    """Continuous codes should be in (-1, 1) range via tanh."""
    layer = NestedHashLayer(input_dim=128, bit_list=[16])
    layer.eval()
    x = torch.randn(8, 128)
    codes = layer(x, bit_length=16, binary=False)

    assert codes.min() >= -1.0
    assert codes.max() <= 1.0


def test_hash_layer_forward_all_bits() -> None:
    """forward_all_bits should return all bit lengths."""
    bit_list = [8, 16, 32]
    layer = NestedHashLayer(input_dim=128, bit_list=bit_list)
    layer.eval()
    x = torch.randn(4, 128)
    result = layer.forward_all_bits(x)

    assert set(result.keys()) == set(bit_list)
    for bit, codes in result.items():
        assert codes.shape == (4, bit)


def test_hash_layer_invalid_bit_length() -> None:
    """Should raise ValueError for invalid bit length."""
    layer = NestedHashLayer(input_dim=128, bit_list=[8, 16])
    x = torch.randn(2, 128)
    with pytest.raises(ValueError, match="bit_length 32 not in bit_list"):
        layer(x, bit_length=32)


# =============================================================================
# 2. CrossModalHashModel tests
# =============================================================================


def test_model_encode_image() -> None:
    """Model should encode images to hash codes."""
    model = CrossModalHashModel(
        ModelConfig(backbone_name="dummy", backbone_dim=128, bit_list=[8, 16])
    )
    imgs = torch.randn(2, 3, 32, 32)
    codes = model.encode_image(imgs, bit_length=8)

    assert codes.shape == (2, 8)
    assert set(codes.unique().tolist()).issubset({-1.0, 1.0})


def test_model_encode_text() -> None:
    """Model should encode text to hash codes."""
    model = CrossModalHashModel(
        ModelConfig(backbone_name="dummy", backbone_dim=128, bit_list=[8, 16])
    )
    ids = torch.randint(0, 1000, (2, 32))
    mask = torch.ones(2, 32, dtype=torch.long)
    codes = model.encode_text(ids, attention_mask=mask, bit_length=8)

    assert codes.shape == (2, 8)


def test_model_encode_with_features() -> None:
    """Return features when requested."""
    model = CrossModalHashModel(ModelConfig(backbone_name="dummy", backbone_dim=128, bit_list=[16]))
    imgs = torch.randn(2, 3, 32, 32)
    codes, features = model.encode_image(imgs, bit_length=16, return_features=True)

    assert codes.shape == (2, 16)
    assert features.shape == (2, 128)


def test_model_all_bits_encode() -> None:
    """Encode all bit lengths at once."""
    model = CrossModalHashModel(
        ModelConfig(backbone_name="dummy", backbone_dim=128, bit_list=[8, 16, 32])
    )
    imgs = torch.randn(2, 3, 32, 32)
    codes_dict = model.encode_image_all_bits(imgs)

    assert set(codes_dict.keys()) == {8, 16, 32}
    assert codes_dict[8].shape == (2, 8)
    assert codes_dict[32].shape == (2, 32)


def test_model_load_checkpoint() -> None:
    """Load model from dummy checkpoint."""
    ckpt_path = FIXTURES_DIR / "dummy_checkpoint.pt"
    if not ckpt_path.exists():
        pytest.skip("Dummy checkpoint not generated yet")

    model = load_model(str(ckpt_path))
    assert isinstance(model, CrossModalHashModel)

    imgs = torch.randn(1, 3, 32, 32)
    codes = model.encode_image(imgs, bit_length=64)
    assert codes.shape == (1, 64)


# =============================================================================
# 3. Hamming distance and search tests
# =============================================================================


def test_hamming_distance_basic() -> None:
    """Hamming distance of identical codes should be 0."""
    a = torch.tensor([[1, -1, 1, -1]], dtype=torch.float)
    dist = hamming_distance(a, a)
    assert dist.item() == 0


def test_hamming_distance_opposite() -> None:
    """Hamming distance of opposite codes should equal dimension."""
    a = torch.tensor([[1, 1, 1, 1]], dtype=torch.float)
    b = torch.tensor([[-1, -1, -1, -1]], dtype=torch.float)
    dist = hamming_distance(a, b)
    assert dist.item() == 4


def test_hamming_distance_pairwise() -> None:
    """Pairwise Hamming distance shape should be (N, M)."""
    a = torch.randn(5, 16).sign()
    b = torch.randn(10, 16).sign()
    dist = hamming_distance(a, b)
    assert dist.shape == (5, 10)
    assert dist.min() >= 0
    assert dist.max() <= 16


def test_to_binary_01() -> None:
    """Convert {-1, +1} to {0, 1}."""
    codes = torch.tensor([1, -1, 1, -1, 1], dtype=torch.float)
    binary = to_binary_01(codes)
    assert binary.tolist() == [1, 0, 1, 0, 1]


def test_hamming_search() -> None:
    """Hamming search should return closest codes."""
    torch.manual_seed(42)
    query = torch.ones(1, 8)
    db = torch.randn(20, 8).sign()
    db[5] = query[0]  # Make one exact match

    scores, indices = hamming_search(query, db, top_k=5)
    assert scores.shape == (1, 5)
    assert indices.shape == (1, 5)
    assert 5 in indices[0].tolist()
    assert scores[0, 0].item() == 0  # Exact match has distance 0


def test_cosine_search() -> None:
    """Cosine search should return most similar vectors."""
    torch.manual_seed(42)
    query = torch.randn(1, 32)
    db = torch.randn(20, 32)
    db[7] = query[0] * 2  # Most similar (same direction)

    scores, indices = cosine_search(query, db, top_k=5)
    assert scores.shape == (1, 5)
    assert 7 in indices[0].tolist()


# =============================================================================
# 4. Evaluation metrics tests
# =============================================================================


def test_map_perfect_retrieval() -> None:
    """Perfect retrieval should give mAP = 1.0."""
    # Each query matches exactly one DB item with same label
    codes = torch.eye(4)  # orthogonal = 0 hamming distance to self
    labels = torch.arange(4)
    result = mean_average_precision(codes, codes, labels, labels)
    assert result == pytest.approx(1.0)


def test_map_random_codes() -> None:
    """mAP with random codes should be between 0 and 1."""
    torch.manual_seed(42)
    q_codes = torch.randn(10, 16).sign()
    db_codes = torch.randn(20, 16).sign()
    q_labels = torch.randint(0, 5, (10,))
    db_labels = torch.randint(0, 5, (20,))

    result = mean_average_precision(q_codes, db_codes, q_labels, db_labels)
    assert 0.0 <= result <= 1.0


def test_precision_at_k_basic() -> None:
    """P@K should be between 0 and 1."""
    torch.manual_seed(42)
    q_codes = torch.randn(5, 8).sign()
    db_codes = torch.randn(15, 8).sign()
    q_labels = torch.randint(0, 3, (5,))
    db_labels = torch.randint(0, 3, (15,))

    p1 = precision_at_k(q_codes, db_codes, q_labels, db_labels, k=1)
    p5 = precision_at_k(q_codes, db_codes, q_labels, db_labels, k=5)
    assert 0.0 <= p1 <= 1.0
    assert 0.0 <= p5 <= 1.0


def test_evaluate_retrieval_multi_bit() -> None:
    """evaluate_retrieval should return results for all bit lengths."""
    torch.manual_seed(42)
    bit_list = [8, 16]
    q_codes = {b: torch.randn(5, b).sign() for b in bit_list}
    db_codes = {b: torch.randn(10, b).sign() for b in bit_list}
    labels = torch.arange(5)
    db_labels = torch.arange(10)

    results = evaluate_retrieval(q_codes, db_codes, labels, db_labels, bit_lengths=bit_list)
    assert "8" in results
    assert "16" in results
    assert "hamming_mAP" in results["8"]
    assert "hamming_P@1" in results["8"]


# =============================================================================
# 5. Index build + load round-trip
# =============================================================================


def test_index_build_and_load(tmp_path: Path) -> None:
    """Build an index and load it back."""
    ckpt_path = FIXTURES_DIR / "dummy_checkpoint.pt"
    captions_path = FIXTURES_DIR / "dummy_captions.json"
    if not ckpt_path.exists() or not captions_path.exists():
        pytest.skip("Dummy fixtures not generated yet")

    with open(captions_path) as f:
        data = json.load(f)

    model = load_model(str(ckpt_path))
    output_path = str(tmp_path / "test_index.pt")

    from adapters.vlm_quantization.index_builder import build_index, load_index

    progress_calls: list[tuple[int, int]] = []

    def on_progress(current: int, total: int) -> None:
        progress_calls.append((current, total))

    index_data = build_index(
        model=model,
        image_paths=data["image_paths"],
        captions=data["captions"],
        output_path=output_path,
        labels=data["labels"],
        batch_size=4,
        image_size=32,
        thumbnail_size=32,
        progress_callback=on_progress,
    )

    assert Path(output_path).exists()
    assert index_data["num_items"] == 10
    assert len(index_data["thumbnails"]) == 10
    assert len(index_data["captions"]) == 10
    assert len(progress_calls) > 0

    # Load and verify
    loaded = load_index(output_path)
    assert loaded["num_items"] == 10
    assert set(loaded["image_codes"].keys()) == set(model.bit_list)


# =============================================================================
# 6. Job model and schema tests
# =============================================================================


def test_job_schema_eval_request() -> None:
    """EvalJobRequest should accept valid data."""
    from backend.schemas.job import EvalJobRequest

    req = EvalJobRequest(run_id=1, checkpoint="best", bit_lengths=[8, 16, 32])
    assert req.run_id == 1
    assert req.checkpoint == "best"


def test_job_schema_index_build_request() -> None:
    """IndexBuildJobRequest should accept valid data."""
    from backend.schemas.job import IndexBuildJobRequest

    req = IndexBuildJobRequest(run_id=1, checkpoint="latest", image_dir="/data/images")
    assert req.run_id == 1
    assert req.image_dir == "/data/images"


def test_job_schema_response() -> None:
    """JobResponse should accept valid data."""
    from backend.schemas.job import JobResponse
    from shared.schemas import JobStatus, JobType

    resp = JobResponse(
        id=1,
        job_type=JobType.EVAL,
        run_id=1,
        status=JobStatus.COMPLETED,
        progress=100,
        config_json={"checkpoint": "best"},
        result_json={"8": {"hamming_mAP": 0.5}},
        error_message=None,
        started_at=datetime(2025, 1, 1, 10, 0, 0),
        ended_at=datetime(2025, 1, 1, 10, 5, 0),
        created_at=datetime(2025, 1, 1, 9, 55, 0),
    )
    assert resp.progress == 100
    assert resp.job_type == JobType.EVAL


def test_job_enums() -> None:
    """JobType and JobStatus enums should have expected values."""
    from shared.schemas import JobStatus, JobType

    assert JobType.EVAL == "eval"
    assert JobType.INDEX_BUILD == "index_build"
    assert JobStatus.PENDING == "pending"
    assert JobStatus.RUNNING == "running"
    assert JobStatus.COMPLETED == "completed"
    assert JobStatus.FAILED == "failed"


def test_adapter_registration() -> None:
    """VLMQuantizationAdapter should be registered."""
    from adapters import get_adapter

    adapter = get_adapter("vlm_quantization")
    assert adapter.get_name() == "VLM Quantization (Cross-Modal Hashing)"


def test_adapter_parse_metrics() -> None:
    """Adapter should parse both JSON and key=value metrics."""
    from adapters import get_adapter

    adapter = get_adapter("vlm_quantization")

    m1 = adapter.parse_metrics('{"step": 100, "train/loss": 0.5}')
    assert m1 is not None
    assert m1["step"] == 100

    m2 = adapter.parse_metrics("step=200 train/loss=0.3")
    assert m2 is not None
    assert m2["step"] == 200

    m3 = adapter.parse_metrics("some random log line")
    assert m3 is None


# =============================================================================
# 7. Smoke test: end-to-end dummy pipeline
# =============================================================================


def test_smoke_dummy_pipeline(tmp_path: Path) -> None:
    """Smoke: load dummy checkpoint → build index → search (< 90s)."""
    import time

    ckpt_path = FIXTURES_DIR / "dummy_checkpoint.pt"
    captions_path = FIXTURES_DIR / "dummy_captions.json"
    if not ckpt_path.exists() or not captions_path.exists():
        pytest.skip("Dummy fixtures not generated yet")

    start = time.time()

    # 1. Load model
    model = load_model(str(ckpt_path))

    # 2. Build index
    with open(captions_path) as f:
        data = json.load(f)

    from adapters.vlm_quantization.index_builder import build_index, load_index

    index_path = str(tmp_path / "smoke_index.pt")
    build_index(
        model=model,
        image_paths=data["image_paths"],
        captions=data["captions"],
        output_path=index_path,
        labels=data["labels"],
        batch_size=10,
        image_size=32,
        thumbnail_size=32,
    )

    # 3. Load index
    index_data = load_index(index_path)

    # 4. Text search
    query_text = "고양이가 소파에 앉아있다"
    token_ids = [ord(c) % 32000 for c in query_text[:128]]
    max_len = 128
    attention_mask = [1] * len(token_ids) + [0] * (max_len - len(token_ids))
    token_ids = token_ids + [0] * (max_len - len(token_ids))

    input_ids = torch.tensor([token_ids], dtype=torch.long)
    attn_mask = torch.tensor([attention_mask], dtype=torch.long)
    query_codes = model.encode_text(input_ids, attention_mask=attn_mask, bit_length=64)

    from adapters.vlm_quantization.search import search_index

    results = search_index(
        query_codes=query_codes,
        index_data={"image_codes": index_data["image_codes"], **index_data},
        bit_length=64,
        top_k=5,
        method="hamming",
    )
    assert len(results) == 5
    assert results[0].rank == 1
    assert results[0].score >= 0

    # 5. Image search (using first test image)
    img_path = data["image_paths"][0]
    from PIL import Image
    import numpy as np

    img = Image.open(img_path).convert("RGB").resize((32, 32))
    arr = np.array(img, dtype=np.float32) / 255.0
    pixel_values = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0)
    img_codes = model.encode_image(pixel_values, bit_length=64)

    text_results = search_index(
        query_codes=img_codes,
        index_data={
            "image_codes": index_data["text_codes"],
            "captions": index_data["captions"],
        },
        bit_length=64,
        top_k=5,
        method="hamming",
    )
    assert len(text_results) == 5

    elapsed = time.time() - start
    assert elapsed < 90, f"Smoke test took {elapsed:.1f}s (max 90s)"
