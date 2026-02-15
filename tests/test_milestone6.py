"""Tests for Milestone 6: Dataset registry, status check, JSONL prepare, preview.

Covers:
1. DatasetStatus enum values
2. DatasetDefinition model creation
3. Dataset registry seed logic
4. File-system status computation
5. JSONL preview and language detection
6. Prepare worker COCO Karpathy conversion
7. Prepare worker JSONL copy
"""

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from shared.schemas import DatasetStatus, JobType


# =============================================================================
# 1. DatasetStatus enum tests
# =============================================================================


def test_dataset_status_values() -> None:
    """DatasetStatus should have the expected values."""
    assert DatasetStatus.READY == "ready"
    assert DatasetStatus.RAW_ONLY == "raw_only"
    assert DatasetStatus.NOT_FOUND == "not_found"
    assert DatasetStatus.PREPARING == "preparing"


def test_dataset_status_is_str_enum() -> None:
    """DatasetStatus values should be string-comparable."""
    assert DatasetStatus.READY.value == "ready"
    assert str(DatasetStatus.NOT_FOUND) == "DatasetStatus.NOT_FOUND"


# =============================================================================
# 2. JobType enum includes DATASET_PREPARE
# =============================================================================


def test_job_type_dataset_prepare() -> None:
    """JobType should include DATASET_PREPARE."""
    assert JobType.DATASET_PREPARE == "dataset_prepare"
    assert hasattr(JobType, "DATASET_PREPARE")


# =============================================================================
# 3. DatasetDefinition model
# =============================================================================


def test_dataset_definition_model_creation() -> None:
    """DatasetDefinition should be creatable with required fields."""
    from backend.models.experiment import DatasetDefinition

    ds = DatasetDefinition(
        key="test_ds",
        name="Test Dataset",
        description="A test dataset",
        data_root="test",
        raw_path="test/raw.json",
        jsonl_path="test/data.jsonl",
        raw_format="coco_karpathy",
    )
    assert ds.key == "test_ds"
    assert ds.name == "Test Dataset"
    assert ds.raw_format == "coco_karpathy"
    assert ds.prepare_job_id is None
    assert ds.entry_count is None


# =============================================================================
# 4. Status computation
# =============================================================================


def test_compute_status_ready() -> None:
    """READY when JSONL exists and has content."""
    from backend.models.experiment import DatasetDefinition
    from backend.services.dataset_registry import compute_status

    with tempfile.TemporaryDirectory() as tmpdir:
        jsonl = Path(tmpdir) / "data.jsonl"
        jsonl.write_text('{"image": "a.jpg", "caption": "hello"}\n')

        ds = DatasetDefinition(key="test", name="Test", jsonl_path="data.jsonl", data_root="")
        status = compute_status(ds, data_dir=tmpdir)
        assert status == DatasetStatus.READY


def test_compute_status_raw_only() -> None:
    """RAW_ONLY when raw data exists but JSONL is missing."""
    from backend.models.experiment import DatasetDefinition
    from backend.services.dataset_registry import compute_status

    with tempfile.TemporaryDirectory() as tmpdir:
        raw = Path(tmpdir) / "raw.json"
        raw.write_text("{}")

        ds = DatasetDefinition(
            key="test",
            name="Test",
            raw_path="raw.json",
            jsonl_path="data.jsonl",
            data_root="",
        )
        status = compute_status(ds, data_dir=tmpdir)
        assert status == DatasetStatus.RAW_ONLY


def test_compute_status_not_found() -> None:
    """NOT_FOUND when neither raw nor JSONL exists."""
    from backend.models.experiment import DatasetDefinition
    from backend.services.dataset_registry import compute_status

    with tempfile.TemporaryDirectory() as tmpdir:
        ds = DatasetDefinition(
            key="test",
            name="Test",
            raw_path="nonexistent.json",
            jsonl_path="nonexistent.jsonl",
            data_root="nonexistent",
        )
        status = compute_status(ds, data_dir=tmpdir)
        assert status == DatasetStatus.NOT_FOUND


def test_compute_status_preparing() -> None:
    """PREPARING when a prepare job is linked."""
    from backend.models.experiment import DatasetDefinition
    from backend.services.dataset_registry import compute_status

    with tempfile.TemporaryDirectory() as tmpdir:
        ds = DatasetDefinition(
            key="test",
            name="Test",
            jsonl_path="data.jsonl",
            data_root="",
            prepare_job_id=42,
        )
        status = compute_status(ds, data_dir=tmpdir)
        assert status == DatasetStatus.PREPARING


# =============================================================================
# 5. File stats
# =============================================================================


def test_get_file_stats() -> None:
    """get_file_stats should return count and size."""
    from backend.models.experiment import DatasetDefinition
    from backend.services.dataset_registry import get_file_stats

    with tempfile.TemporaryDirectory() as tmpdir:
        jsonl = Path(tmpdir) / "data.jsonl"
        jsonl.write_text(
            '{"image": "a.jpg", "caption": "hello"}\n'
            '{"image": "b.jpg", "caption": "world"}\n'
            '{"image": "c.jpg", "caption": "test"}\n'
        )

        ds = DatasetDefinition(key="test", name="Test", jsonl_path="data.jsonl", data_root="")
        stats = get_file_stats(ds, data_dir=tmpdir)
        assert stats["entry_count"] == 3
        assert stats["size_bytes"] is not None
        assert stats["size_bytes"] > 0


def test_get_file_stats_missing() -> None:
    """get_file_stats should return None for missing files."""
    from backend.models.experiment import DatasetDefinition
    from backend.services.dataset_registry import get_file_stats

    with tempfile.TemporaryDirectory() as tmpdir:
        ds = DatasetDefinition(key="test", name="Test", jsonl_path="missing.jsonl", data_root="")
        stats = get_file_stats(ds, data_dir=tmpdir)
        assert stats["entry_count"] is None
        assert stats["size_bytes"] is None


# =============================================================================
# 6. Language detection
# =============================================================================


def test_detect_language_korean() -> None:
    """Korean text should be detected as 'ko'."""
    from backend.services.dataset_registry import _detect_language

    assert _detect_language("테스트용 이미지입니다") == "ko"


def test_detect_language_english() -> None:
    """English text should be detected as 'en'."""
    from backend.services.dataset_registry import _detect_language

    assert _detect_language("A test image for verification") == "en"


def test_detect_language_mixed() -> None:
    """Mixed text should be detected as 'mixed'."""
    from backend.services.dataset_registry import _detect_language

    assert _detect_language("Hello 안녕하세요 world") == "mixed"


# =============================================================================
# 7. JSONL preview
# =============================================================================


def test_preview_jsonl() -> None:
    """preview_jsonl should return parsed samples with language info."""
    from backend.models.experiment import DatasetDefinition
    from backend.services.dataset_registry import preview_jsonl

    with tempfile.TemporaryDirectory() as tmpdir:
        jsonl = Path(tmpdir) / "data.jsonl"
        entries = [
            {"image": "img_000.png", "caption": "A red square"},
            {"image": "img_001.png", "caption": "초록색 사각형"},
            {"image": "img_002.png", "caption": "A blue square"},
        ]
        jsonl.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n")

        ds = DatasetDefinition(id=1, key="test", name="Test", jsonl_path="data.jsonl", data_root="")
        samples = preview_jsonl(ds, n=3, data_dir=tmpdir)
        assert len(samples) == 3
        # Each sample should have caption language annotation
        for s in samples:
            assert "caption" in s
            assert "_caption_lang" in s


def test_preview_jsonl_empty() -> None:
    """preview_jsonl should return empty list for missing JSONL."""
    from backend.models.experiment import DatasetDefinition
    from backend.services.dataset_registry import preview_jsonl

    with tempfile.TemporaryDirectory() as tmpdir:
        ds = DatasetDefinition(
            id=1, key="test", name="Test", jsonl_path="missing.jsonl", data_root=""
        )
        samples = preview_jsonl(ds, n=5, data_dir=tmpdir)
        assert samples == []


# =============================================================================
# 8. Language stats
# =============================================================================


def test_language_stats() -> None:
    """language_stats should return distribution counts."""
    from backend.models.experiment import DatasetDefinition
    from backend.services.dataset_registry import language_stats

    with tempfile.TemporaryDirectory() as tmpdir:
        jsonl = Path(tmpdir) / "data.jsonl"
        entries = [
            {"image": f"img_{i}.png", "caption": cap}
            for i, cap in enumerate(
                [
                    "A red square",
                    "A green circle",
                    "초록색 사각형",
                    "파란색 원",
                    "Hello 안녕",
                ]
            )
        ]
        jsonl.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n")

        ds = DatasetDefinition(key="test", name="Test", jsonl_path="data.jsonl", data_root="")
        stats = language_stats(ds, sample_size=10, data_dir=tmpdir)
        assert "en" in stats
        assert "ko" in stats
        assert stats["en"] == 2
        assert stats["ko"] == 2


# =============================================================================
# 9. Prepare worker — COCO Karpathy format
# =============================================================================


def test_prepare_coco_karpathy() -> None:
    """Prepare worker should convert COCO Karpathy JSON to JSONL."""
    from backend.workers.prepare_worker import prepare_coco_karpathy

    with tempfile.TemporaryDirectory() as tmpdir:
        # Use the dummy fixture
        fixture_dir = Path("tests/fixtures/dummy_dataset")
        raw_src = fixture_dir / "raw_annotations.json"
        if not raw_src.exists():
            pytest.skip("Dummy fixture not found")

        raw_path = Path(tmpdir) / "raw.json"
        shutil.copy(raw_src, raw_path)

        jsonl_path = Path(tmpdir) / "output.jsonl"

        count = prepare_coco_karpathy(
            raw_path=raw_path,
            jsonl_path=jsonl_path,
            data_root="",
            server_url="http://localhost:99999",  # won't connect, that's ok
            job_id=0,
        )

        assert jsonl_path.exists()
        assert count == 10  # 5 images × 2 sentences each

        # Verify output format
        with open(jsonl_path) as f:
            lines = [json.loads(line) for line in f if line.strip()]
        assert len(lines) == 10
        assert "image" in lines[0]
        assert "caption" in lines[0]
        assert "split" in lines[0]


def test_prepare_coco_standard_format() -> None:
    """Prepare worker should handle standard COCO annotations format."""
    from backend.workers.prepare_worker import prepare_coco_karpathy

    with tempfile.TemporaryDirectory() as tmpdir:
        raw_data = {
            "images": [
                {"id": 1, "file_name": "img1.jpg"},
                {"id": 2, "file_name": "img2.jpg"},
            ],
            "annotations": [
                {"image_id": 1, "caption": "A dog on a beach"},
                {"image_id": 1, "caption": "Dog playing in sand"},
                {"image_id": 2, "caption": "A cat sleeping"},
            ],
        }
        raw_path = Path(tmpdir) / "coco.json"
        raw_path.write_text(json.dumps(raw_data))

        jsonl_path = Path(tmpdir) / "output.jsonl"
        count = prepare_coco_karpathy(
            raw_path=raw_path,
            jsonl_path=jsonl_path,
            data_root="",
            server_url="http://localhost:99999",
            job_id=0,
        )

        assert count == 3
        with open(jsonl_path) as f:
            lines = [json.loads(line) for line in f if line.strip()]
        assert lines[0]["image"] == "img1.jpg"
        assert "caption" in lines[0]


# =============================================================================
# 10. Prepare worker — JSONL copy
# =============================================================================


def test_prepare_jsonl_copy() -> None:
    """Prepare worker should validate and copy JSONL."""
    from backend.workers.prepare_worker import prepare_jsonl_copy

    with tempfile.TemporaryDirectory() as tmpdir:
        raw_path = Path(tmpdir) / "raw.jsonl"
        raw_path.write_text(
            '{"image": "a.jpg", "caption": "hello"}\n'
            "not valid json\n"
            '{"image": "b.jpg", "caption": "world"}\n'
        )

        jsonl_path = Path(tmpdir) / "output.jsonl"
        count = prepare_jsonl_copy(
            raw_path=raw_path,
            jsonl_path=jsonl_path,
            server_url="http://localhost:99999",
            job_id=0,
        )

        assert count == 2  # 1 invalid line skipped
        with open(jsonl_path) as f:
            lines = [json.loads(line) for line in f if line.strip()]
        assert len(lines) == 2


# =============================================================================
# 11. Seed data constants
# =============================================================================


def test_seed_datasets_constants() -> None:
    """Seed dataset list should contain expected entries."""
    from backend.services.dataset_registry import SEED_DATASETS

    keys = [d["key"] for d in SEED_DATASETS]
    assert "coco" in keys
    assert "coco_ko" in keys
    assert "aihub" in keys
    assert "cc3m_ko" in keys


# =============================================================================
# 12. API response schemas
# =============================================================================


def test_dataset_response_schema() -> None:
    """DatasetResponse should accept valid data including new M6 fields."""
    from backend.api.datasets import DatasetResponse

    resp = DatasetResponse(
        id=1,
        key="coco",
        name="COCO 2014",
        description="Test",
        dataset_type="image-text",
        dataset_format="jsonl",
        data_root="coco",
        jsonl_path="coco/data.jsonl",
        raw_path="coco/raw.json",
        raw_format="coco_karpathy",
        split_method="field",
        splits_config={"field": "split"},
        status=DatasetStatus.READY,
        entry_count=5000,
        size_bytes=1024000,
        is_seed=True,
    )
    assert resp.id == 1
    assert resp.status == DatasetStatus.READY
    assert resp.dataset_type == "image-text"
    assert resp.dataset_format == "jsonl"
    assert resp.split_method == "field"
    assert resp.is_seed is True


def test_preview_response_schema() -> None:
    """PreviewResponse should accept valid data."""
    from backend.api.datasets import PreviewResponse

    resp = PreviewResponse(
        dataset_id=1,
        dataset_name="COCO 2014",
        dataset_type="image-text",
        samples=[{"image": "img.jpg", "caption": "test"}],
        language_stats={"en": 80, "ko": 20},
        total_entries=100,
    )
    assert len(resp.samples) == 1
    assert resp.language_stats["en"] == 80
    assert resp.dataset_type == "image-text"


# =============================================================================
# 13. New enum tests (DatasetType, DatasetFormat, SplitMethod)
# =============================================================================


def test_dataset_type_enum() -> None:
    """DatasetType should have the expected values."""
    from shared.schemas import DatasetType

    assert DatasetType.IMAGE_TEXT == "image-text"
    assert DatasetType.TEXT_ONLY == "text-only"
    assert DatasetType.IMAGE_ONLY == "image-only"
    assert DatasetType.TABULAR == "tabular"
    assert DatasetType.CUSTOM == "custom"


def test_dataset_format_enum() -> None:
    """DatasetFormat should have the expected values."""
    from shared.schemas import DatasetFormat

    assert DatasetFormat.JSONL == "jsonl"
    assert DatasetFormat.CSV == "csv"
    assert DatasetFormat.PARQUET == "parquet"
    assert DatasetFormat.HUGGINGFACE == "huggingface"
    assert DatasetFormat.DIRECTORY == "directory"


def test_split_method_enum() -> None:
    """SplitMethod should have the expected values."""
    from shared.schemas import SplitMethod

    assert SplitMethod.RATIO == "ratio"
    assert SplitMethod.FILE == "file"
    assert SplitMethod.FIELD == "field"
    assert SplitMethod.CUSTOM == "custom"
    assert SplitMethod.NONE == "none"


# =============================================================================
# 14. Model creation with new fields
# =============================================================================


def test_dataset_definition_new_fields() -> None:
    """DatasetDefinition should accept new M6 fields."""
    from backend.models.experiment import DatasetDefinition
    from shared.schemas import DatasetFormat, DatasetType, SplitMethod

    ds = DatasetDefinition(
        key="my_csv",
        name="My CSV",
        description="Custom CSV dataset",
        dataset_type=DatasetType.TABULAR,
        dataset_format=DatasetFormat.CSV,
        split_method=SplitMethod.RATIO,
        splits_config={"ratios": {"train": 0.8, "val": 0.1, "test": 0.1}},
        data_root="",
        raw_path="my.csv",
        jsonl_path="",
        raw_format="csv",
        is_seed=False,
    )
    assert ds.dataset_type == DatasetType.TABULAR
    assert ds.dataset_format == DatasetFormat.CSV
    assert ds.split_method == SplitMethod.RATIO
    assert ds.is_seed is False
    assert ds.splits_config["ratios"]["train"] == 0.8


# =============================================================================
# 15. Auto-detect service
# =============================================================================


def test_detect_jsonl_file() -> None:
    """detect_dataset should identify JSONL with image-text content."""
    from backend.services.dataset_registry import detect_dataset

    with tempfile.TemporaryDirectory() as tmpdir:
        jsonl = Path(tmpdir) / "data.jsonl"
        jsonl.write_text(
            '{"image": "a.jpg", "caption": "hello"}\n{"image": "b.jpg", "caption": "world"}\n'
        )
        result = detect_dataset("data.jsonl", data_dir=tmpdir)
        assert result["exists"] is True
        assert result["format"] == "jsonl"
        assert result["type"] == "image-text"
        assert result["entry_count"] == 2


def test_detect_csv_file() -> None:
    """detect_dataset should identify CSV with tabular content."""
    from backend.services.dataset_registry import detect_dataset

    with tempfile.TemporaryDirectory() as tmpdir:
        csv_file = Path(tmpdir) / "data.csv"
        csv_file.write_text("id,value,score\n1,foo,0.5\n2,bar,0.8\n")
        result = detect_dataset("data.csv", data_dir=tmpdir)
        assert result["exists"] is True
        assert result["format"] == "csv"
        assert result["type"] == "tabular"
        assert result["entry_count"] == 2


def test_detect_directory_with_images() -> None:
    """detect_dataset should identify a directory of images."""
    from backend.services.dataset_registry import detect_dataset

    with tempfile.TemporaryDirectory() as tmpdir:
        img_dir = Path(tmpdir) / "images"
        img_dir.mkdir()
        for i in range(3):
            (img_dir / f"img_{i}.jpg").write_text("fake")
        result = detect_dataset("images", data_dir=tmpdir)
        assert result["exists"] is True
        assert result["format"] == "directory"
        assert result["type"] == "image-only"
        assert result["entry_count"] == 3


def test_detect_missing_path() -> None:
    """detect_dataset should report not found."""
    from backend.services.dataset_registry import detect_dataset

    with tempfile.TemporaryDirectory() as tmpdir:
        result = detect_dataset("nonexistent.jsonl", data_dir=tmpdir)
        assert result["exists"] is False
        assert result["error"] == "Path not found"


def test_detect_json_coco_format() -> None:
    """detect_dataset should identify COCO-format JSON."""
    from backend.services.dataset_registry import detect_dataset

    with tempfile.TemporaryDirectory() as tmpdir:
        raw = Path(tmpdir) / "coco.json"
        raw.write_text(
            json.dumps(
                {
                    "images": [
                        {"id": 1, "file_name": "a.jpg", "sentences": [{"raw": "hello"}]},
                        {
                            "id": 2,
                            "file_name": "b.jpg",
                            "sentences": [{"raw": "world"}, {"raw": "test"}],
                        },
                    ]
                }
            )
        )
        result = detect_dataset("coco.json", data_dir=tmpdir)
        assert result["exists"] is True
        assert result["type"] == "image-text"
        assert result["entry_count"] == 3  # 1 + 2 sentences


# =============================================================================
# 16. Split preview computation
# =============================================================================


def test_split_preview_ratio() -> None:
    """compute_split_preview should split by ratio."""
    from backend.models.experiment import DatasetDefinition
    from backend.services.dataset_registry import compute_split_preview
    from shared.schemas import SplitMethod

    with tempfile.TemporaryDirectory() as tmpdir:
        jsonl = Path(tmpdir) / "data.jsonl"
        jsonl.write_text("\n".join(f'{{"id": {i}}}' for i in range(100)) + "\n")

        ds = DatasetDefinition(
            key="test",
            name="Test",
            jsonl_path="data.jsonl",
            data_root="",
            split_method=SplitMethod.RATIO,
            splits_config={"ratios": {"train": 0.8, "val": 0.1, "test": 0.1}},
        )
        preview = compute_split_preview(ds, data_dir=tmpdir)
        assert preview["train"] == 80
        assert preview["val"] == 10
        assert preview["test"] == 10


def test_split_preview_field() -> None:
    """compute_split_preview should count by field value."""
    from backend.models.experiment import DatasetDefinition
    from backend.services.dataset_registry import compute_split_preview
    from shared.schemas import SplitMethod

    with tempfile.TemporaryDirectory() as tmpdir:
        jsonl = Path(tmpdir) / "data.jsonl"
        entries = (
            [json.dumps({"split": "train"}) for _ in range(7)]
            + [json.dumps({"split": "val"}) for _ in range(2)]
            + [json.dumps({"split": "test"}) for _ in range(1)]
        )
        jsonl.write_text("\n".join(entries) + "\n")

        ds = DatasetDefinition(
            key="test",
            name="Test",
            jsonl_path="data.jsonl",
            data_root="",
            split_method=SplitMethod.FIELD,
            splits_config={"field": "split"},
        )
        preview = compute_split_preview(ds, data_dir=tmpdir)
        assert preview["train"] == 7
        assert preview["val"] == 2
        assert preview["test"] == 1


def test_split_preview_none() -> None:
    """compute_split_preview with method=none returns all count."""
    from backend.models.experiment import DatasetDefinition
    from backend.services.dataset_registry import compute_split_preview
    from shared.schemas import SplitMethod

    with tempfile.TemporaryDirectory() as tmpdir:
        jsonl = Path(tmpdir) / "data.jsonl"
        jsonl.write_text('{"a": 1}\n{"a": 2}\n{"a": 3}\n')

        ds = DatasetDefinition(
            key="test",
            name="Test",
            jsonl_path="data.jsonl",
            data_root="",
            split_method=SplitMethod.NONE,
            splits_config={},
        )
        preview = compute_split_preview(ds, data_dir=tmpdir)
        assert preview == {"all": 3}


# =============================================================================
# 17. CRUD request/response schemas
# =============================================================================


def test_create_dataset_request_defaults() -> None:
    """CreateDatasetRequest should have sensible defaults."""
    from backend.api.datasets import CreateDatasetRequest

    req = CreateDatasetRequest(name="My Dataset")
    assert req.name == "My Dataset"
    assert req.dataset_type == "image-text"
    assert req.dataset_format == "jsonl"
    assert req.split_method == "none"
    assert req.splits_config == {}


def test_update_dataset_request_partial() -> None:
    """UpdateDatasetRequest should allow partial updates."""
    from backend.api.datasets import UpdateDatasetRequest

    req = UpdateDatasetRequest(name="New Name", dataset_type="tabular")
    assert req.name == "New Name"
    assert req.dataset_type == "tabular"
    assert req.description is None
    assert req.data_root is None


def test_detect_response_schema() -> None:
    """DetectResponse should accept valid detect results."""
    from backend.api.datasets import DetectResponse

    resp = DetectResponse(
        exists=True,
        format="jsonl",
        type="image-text",
        entry_count=500,
        raw_format="jsonl_copy",
    )
    assert resp.exists is True
    assert resp.entry_count == 500


def test_slugify() -> None:
    """_slugify should produce URL-safe keys."""
    from backend.api.datasets import _slugify

    assert _slugify("COCO 2014 (Korean)") == "coco_2014_korean"
    assert _slugify("My Dataset!") == "my_dataset"
    assert _slugify("  test  ") == "test"
    assert _slugify("") == "dataset"


# =============================================================================
# 18. Seed data includes new fields
# =============================================================================


def test_seed_datasets_have_new_fields() -> None:
    """Each seed dataset should have dataset_type, dataset_format, split_method, is_seed."""
    from backend.services.dataset_registry import SEED_DATASETS

    for seed in SEED_DATASETS:
        assert "dataset_type" in seed, f"{seed['key']} missing dataset_type"
        assert "dataset_format" in seed, f"{seed['key']} missing dataset_format"
        assert "split_method" in seed, f"{seed['key']} missing split_method"
        assert "splits_config" in seed, f"{seed['key']} missing splits_config"
        assert seed.get("is_seed") is True, f"{seed['key']} should be is_seed=True"


# =============================================================================
# 19. Genericity — no model-specific terms in core code
# =============================================================================


def test_no_vlm_terms_in_api() -> None:
    """Core API code should not contain model-specific terms."""
    import re

    api_path = Path("backend/api/datasets.py")
    if not api_path.exists():
        pytest.skip("API file not found")

    content = api_path.read_text()
    # Allow references in comments/docstrings that explain the system,
    # but not in actual function/variable names or string literals used as values
    forbidden = ["vlm_quantization", "siglip", "cross_modal_hash"]
    for term in forbidden:
        matches = re.findall(rf"\b{term}\b", content, re.IGNORECASE)
        assert not matches, f"Found model-specific term '{term}' in core API code"


def test_no_vlm_terms_in_schemas() -> None:
    """Shared schemas should not contain model-specific terms."""
    schema_path = Path("shared/schemas.py")
    if not schema_path.exists():
        pytest.skip("Schemas file not found")

    content = schema_path.read_text()
    forbidden = ["vlm", "siglip", "coco", "hash"]
    for term in forbidden:
        # Only check outside comments
        lines = [line for line in content.split("\n") if not line.strip().startswith("#")]
        code = "\n".join(lines)
        assert term not in code.lower(), f"Found model-specific term '{term}' in shared schemas"
