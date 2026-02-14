"""Comprehensive tests for vlm_quantization config round-trip and utility functions.

Tests cover:
1. Config round-trip (YAML → flatten → unflatten → YAML)
2. Preset config structure validation
3. Flatten/unflatten edge cases
4. Adapter config_to_yaml functionality
5. Dataset resolution in adapter
"""

from pathlib import Path
from typing import Any

import pytest
import yaml

# Import from project modules
from adapters.pytorch_lightning import PyTorchLightningAdapter, DATASET_REGISTRY
from backend.seeds.vlm_quantization import PRESETS
from shared.utils import flatten_dict, unflatten_dict


# =============================================================================
# Test Configuration
# =============================================================================

VLM_CONFIGS_DIR = Path("/Users/rexxa/github/vlm_quantization/configs")
CONFIG_FILES = [
    "default.yaml",
    "colab.yaml",
    "dgx_spark.yaml",
    "colab_multilingual.yaml",
]


# =============================================================================
# 1. Config Round-Trip Tests
# =============================================================================


@pytest.mark.parametrize("config_filename", CONFIG_FILES)
def test_config_roundtrip_preserves_structure(config_filename: str) -> None:
    """Test that YAML → flatten → unflatten → YAML preserves structure.

    This is the critical test: ensures our flatten/unflatten pipeline
    doesn't corrupt config data during the hub workflow.
    """
    config_path = VLM_CONFIGS_DIR / config_filename

    if not config_path.exists():
        pytest.skip(f"vlm_quantization config not found: {config_path}")

    # Load original YAML
    with open(config_path, "r", encoding="utf-8") as f:
        original_nested = yaml.safe_load(f)

    # Round-trip: nested → flat → nested
    flat = flatten_dict(original_nested)
    roundtrip_nested = unflatten_dict(flat)

    # Assert semantic equality
    assert roundtrip_nested == original_nested, (
        f"Round-trip failed for {config_filename}. "
        f"Differences: {_deep_diff(original_nested, roundtrip_nested)}"
    )


@pytest.mark.parametrize("config_filename", CONFIG_FILES)
def test_config_roundtrip_preserves_bit_list(config_filename: str) -> None:
    """Test that model.bit_list remains a list of ints after round-trip.

    Critical: bit_list must be [8, 16, 32, 48, 64, 128], not ["8", "16", ...].
    """
    config_path = VLM_CONFIGS_DIR / config_filename

    if not config_path.exists():
        pytest.skip(f"vlm_quantization config not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        original_nested = yaml.safe_load(f)

    # Round-trip
    flat = flatten_dict(original_nested)
    roundtrip_nested = unflatten_dict(flat)

    # Verify bit_list is still a list of ints
    bit_list = roundtrip_nested.get("model", {}).get("bit_list")
    assert isinstance(bit_list, list), f"bit_list is not a list: {type(bit_list)}"
    assert all(isinstance(x, int) for x in bit_list), (
        f"bit_list contains non-int values: {bit_list}"
    )
    assert bit_list == [8, 16, 32, 48, 64, 128], f"bit_list corrupted: {bit_list}"


@pytest.mark.parametrize("config_filename", CONFIG_FILES)
def test_config_roundtrip_preserves_extra_datasets(config_filename: str) -> None:
    """Test that data.extra_datasets list structure survives round-trip.

    Extra datasets are list[dict] with jsonl_path and data_root keys.
    These should survive flatten → unflatten without corruption.
    """
    config_path = VLM_CONFIGS_DIR / config_filename

    if not config_path.exists():
        pytest.skip(f"vlm_quantization config not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        original_nested = yaml.safe_load(f)

    # Only test if extra_datasets exists in original
    original_extra = original_nested.get("data", {}).get("extra_datasets")
    if not original_extra:
        pytest.skip(f"{config_filename} has no extra_datasets")

    # Round-trip
    flat = flatten_dict(original_nested)
    roundtrip_nested = unflatten_dict(flat)

    # Verify extra_datasets structure
    roundtrip_extra = roundtrip_nested.get("data", {}).get("extra_datasets")
    assert isinstance(roundtrip_extra, list), (
        f"extra_datasets is not a list: {type(roundtrip_extra)}"
    )
    assert len(roundtrip_extra) == len(original_extra), (
        f"extra_datasets length changed: {len(original_extra)} → {len(roundtrip_extra)}"
    )

    # Verify each entry is a dict with required keys
    for i, entry in enumerate(roundtrip_extra):
        assert isinstance(entry, dict), f"extra_datasets[{i}] is not a dict: {entry}"
        assert "jsonl_path" in entry, f"extra_datasets[{i}] missing jsonl_path"
        assert "data_root" in entry, f"extra_datasets[{i}] missing data_root"

    # Verify exact equality
    assert roundtrip_extra == original_extra


@pytest.mark.parametrize("config_filename", CONFIG_FILES)
def test_config_roundtrip_preserves_batch_size_type(config_filename: str) -> None:
    """Test that batch_size type is preserved (int or 'auto' string).

    - default.yaml: batch_size: 128 (int) → must stay int
    - colab.yaml: batch_size: auto (str) → must stay str
    """
    config_path = VLM_CONFIGS_DIR / config_filename

    if not config_path.exists():
        pytest.skip(f"vlm_quantization config not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        original_nested = yaml.safe_load(f)

    original_batch_size = original_nested.get("training", {}).get("batch_size")

    # Round-trip
    flat = flatten_dict(original_nested)
    roundtrip_nested = unflatten_dict(flat)

    roundtrip_batch_size = roundtrip_nested.get("training", {}).get("batch_size")

    # Type must match exactly
    assert type(original_batch_size) is type(roundtrip_batch_size), (
        f"batch_size type changed: {type(original_batch_size)} → {type(roundtrip_batch_size)}"
    )
    assert original_batch_size == roundtrip_batch_size


# =============================================================================
# 2. Preset Config Structure Tests
# =============================================================================


@pytest.mark.parametrize("preset_idx", range(len(PRESETS)))
def test_preset_has_required_fields(preset_idx: int) -> None:
    """Test that presets have all required top-level fields."""
    preset = PRESETS[preset_idx]

    assert "name" in preset
    assert "description" in preset
    assert "config_json" in preset
    assert isinstance(preset["config_json"], dict)


@pytest.mark.parametrize("preset_idx", range(len(PRESETS)))
def test_preset_config_has_model_fields(preset_idx: int) -> None:
    """Test that preset configs have required model.* fields."""
    preset = PRESETS[preset_idx]
    config = preset["config_json"]

    assert "model.backbone" in config
    assert "model.bit_list" in config
    assert isinstance(config["model.bit_list"], list)
    assert config["model.bit_list"] == [8, 16, 32, 48, 64, 128]


@pytest.mark.parametrize("preset_idx", range(len(PRESETS)))
def test_preset_config_batch_size_types(preset_idx: int) -> None:
    """Test that batch_size is either int or 'auto' string."""
    preset = PRESETS[preset_idx]
    config = preset["config_json"]

    batch_size = config["training.batch_size"]
    assert isinstance(batch_size, (int, str))
    if isinstance(batch_size, str):
        assert batch_size == "auto"


@pytest.mark.parametrize("preset_idx", range(len(PRESETS)))
def test_preset_config_has_temperature(preset_idx: int) -> None:
    """Test that loss.temperature is present and is 0.07."""
    preset = PRESETS[preset_idx]
    config = preset["config_json"]

    assert "loss.temperature" in config
    assert config["loss.temperature"] == 0.07
    assert isinstance(config["loss.temperature"], float)


# =============================================================================
# 3. Flatten/Unflatten Edge Cases
# =============================================================================


def test_flatten_unflatten_empty_dict() -> None:
    """Test that empty dict round-trips correctly."""
    original = {}
    flat = flatten_dict(original)
    roundtrip = unflatten_dict(flat)

    assert roundtrip == original
    assert flat == {}


def test_flatten_unflatten_deeply_nested() -> None:
    """Test that deeply nested dicts (3+ levels) round-trip correctly."""
    original = {
        "level1": {
            "level2": {
                "level3": {
                    "value": 42
                }
            }
        }
    }

    flat = flatten_dict(original)
    assert flat == {"level1.level2.level3.value": 42}

    roundtrip = unflatten_dict(flat)
    assert roundtrip == original


def test_flatten_unflatten_preserves_list_values() -> None:
    """Test that list values survive round-trip."""
    original = {
        "model": {
            "bit_list": [8, 16, 32, 48, 64, 128],
            "layers": [1, 2, 3]
        }
    }

    flat = flatten_dict(original)
    roundtrip = unflatten_dict(flat)

    assert roundtrip == original
    assert roundtrip["model"]["bit_list"] == [8, 16, 32, 48, 64, 128]
    assert roundtrip["model"]["layers"] == [1, 2, 3]


def test_flatten_unflatten_preserves_boolean_values() -> None:
    """Test that boolean values survive round-trip."""
    original = {
        "model": {
            "freeze_backbone": True
        },
        "monitor": {
            "enabled": False
        }
    }

    flat = flatten_dict(original)
    roundtrip = unflatten_dict(flat)

    assert roundtrip == original
    assert roundtrip["model"]["freeze_backbone"] is True
    assert roundtrip["monitor"]["enabled"] is False


def test_flatten_unflatten_preserves_string_auto() -> None:
    """Test that string 'auto' survives round-trip."""
    original = {
        "training": {
            "batch_size": "auto"
        }
    }

    flat = flatten_dict(original)
    roundtrip = unflatten_dict(flat)

    assert roundtrip == original
    assert roundtrip["training"]["batch_size"] == "auto"
    assert isinstance(roundtrip["training"]["batch_size"], str)


def test_flatten_unflatten_preserves_float_precision() -> None:
    """Test that float values maintain precision through round-trip."""
    original = {
        "loss": {
            "temperature": 0.07,
            "weight_decay": 0.01,
            "lr": 5e-6
        }
    }

    flat = flatten_dict(original)
    roundtrip = unflatten_dict(flat)

    assert roundtrip == original
    assert roundtrip["loss"]["temperature"] == 0.07
    assert roundtrip["loss"]["weight_decay"] == 0.01
    assert roundtrip["loss"]["lr"] == 5e-6


def test_flatten_unflatten_mixed_types() -> None:
    """Test round-trip with mixed value types."""
    original = {
        "config": {
            "name": "test",
            "enabled": True,
            "count": 42,
            "ratio": 0.5,
            "items": [1, 2, 3],
            "nested": {
                "value": "deep"
            }
        }
    }

    flat = flatten_dict(original)
    roundtrip = unflatten_dict(flat)

    assert roundtrip == original


# =============================================================================
# 4. Adapter config_to_yaml Tests
# =============================================================================


def test_adapter_config_to_yaml_handles_string_batch_size() -> None:
    """Test that string batch_size '128' is converted to int 128 in YAML."""
    adapter = PyTorchLightningAdapter()

    config = {
        "training": {
            "batch_size": "128"
        }
    }

    yaml_str = adapter.config_to_yaml(config)
    parsed = yaml.safe_load(yaml_str)

    assert parsed["training"]["batch_size"] == 128
    assert isinstance(parsed["training"]["batch_size"], int)


def test_adapter_config_to_yaml_preserves_auto_batch_size() -> None:
    """Test that 'auto' batch_size stays as string in YAML."""
    adapter = PyTorchLightningAdapter()

    config = {
        "training": {
            "batch_size": "auto"
        }
    }

    yaml_str = adapter.config_to_yaml(config)
    parsed = yaml.safe_load(yaml_str)

    assert parsed["training"]["batch_size"] == "auto"
    assert isinstance(parsed["training"]["batch_size"], str)


def test_adapter_config_to_yaml_preserves_int_batch_size() -> None:
    """Test that int batch_size stays as int in YAML."""
    adapter = PyTorchLightningAdapter()

    config = {
        "training": {
            "batch_size": 128
        }
    }

    yaml_str = adapter.config_to_yaml(config)
    parsed = yaml.safe_load(yaml_str)

    assert parsed["training"]["batch_size"] == 128
    assert isinstance(parsed["training"]["batch_size"], int)


# =============================================================================
# 5. Dataset Resolution Tests (via config_to_yaml)
# =============================================================================


def test_adapter_resolves_dataset_ids_to_paths() -> None:
    """Test that dataset IDs are converted to full path dicts in YAML."""
    adapter = PyTorchLightningAdapter()

    config = {
        "data": {
            "extra_datasets": ["coco_ko", "aihub"]
        }
    }

    yaml_str = adapter.config_to_yaml(config)
    parsed = yaml.safe_load(yaml_str)

    extra = parsed["data"]["extra_datasets"]
    assert len(extra) == 2

    # Verify structure (paths will use DATA_DIR env var or default "./data")
    for entry in extra:
        assert isinstance(entry, dict)
        assert "jsonl_path" in entry
        assert "data_root" in entry


def test_adapter_passes_through_resolved_dicts() -> None:
    """Test that already-resolved dicts are passed through unchanged."""
    adapter = PyTorchLightningAdapter()

    config = {
        "data": {
            "extra_datasets": [
                {
                    "jsonl_path": "/custom/path/data.jsonl",
                    "data_root": "/custom/root"
                }
            ]
        }
    }

    yaml_str = adapter.config_to_yaml(config)
    parsed = yaml.safe_load(yaml_str)

    extra = parsed["data"]["extra_datasets"]
    assert len(extra) == 1
    assert extra[0]["jsonl_path"] == "/custom/path/data.jsonl"
    assert extra[0]["data_root"] == "/custom/root"


def test_adapter_handles_empty_extra_datasets() -> None:
    """Test that empty extra_datasets list is removed from YAML."""
    adapter = PyTorchLightningAdapter()

    config = {
        "data": {
            "extra_datasets": []
        }
    }

    yaml_str = adapter.config_to_yaml(config)
    parsed = yaml.safe_load(yaml_str)

    # Empty list should be removed (None or missing key)
    extra = parsed["data"].get("extra_datasets")
    assert extra is None or "extra_datasets" not in parsed["data"]


def test_adapter_resolves_all_registry_entries() -> None:
    """Test resolution for all entries in DATASET_REGISTRY."""
    adapter = PyTorchLightningAdapter()

    config = {
        "data": {
            "extra_datasets": list(DATASET_REGISTRY.keys())
        }
    }

    yaml_str = adapter.config_to_yaml(config)
    parsed = yaml.safe_load(yaml_str)

    extra = parsed["data"]["extra_datasets"]
    assert len(extra) == len(DATASET_REGISTRY)

    # Verify all entries have required keys
    for entry in extra:
        assert "jsonl_path" in entry
        assert "data_root" in entry


# =============================================================================
# 6. Integration Tests
# =============================================================================


def test_adapter_full_workflow_with_nested_config() -> None:
    """Test the complete workflow: nested config → YAML string."""
    adapter = PyTorchLightningAdapter()

    nested_config = {
        "model": {
            "backbone": "google/siglip2-so400m-patch14-384",
            "bit_list": [8, 16, 32, 48, 64, 128],
        },
        "training": {
            "batch_size": "auto",
        },
        "loss": {
            "temperature": 0.07,
        },
        "data": {
            "extra_datasets": ["coco_ko"],
        },
    }

    yaml_str = adapter.config_to_yaml(nested_config)
    parsed = yaml.safe_load(yaml_str)

    assert parsed["model"]["backbone"] == "google/siglip2-so400m-patch14-384"
    assert parsed["model"]["bit_list"] == [8, 16, 32, 48, 64, 128]
    assert parsed["training"]["batch_size"] == "auto"
    assert parsed["loss"]["temperature"] == 0.07
    assert len(parsed["data"]["extra_datasets"]) == 1


def test_flatten_to_nested_to_yaml_workflow() -> None:
    """Test flat config → nested → YAML workflow using utils and adapter."""
    flat_config = {
        "model.backbone": "google/siglip2-so400m-patch14-384",
        "model.bit_list": [8, 16, 32, 48, 64, 128],
        "training.batch_size": 128,
        "loss.temperature": 0.07,
    }

    # Flatten → unflatten to get nested
    nested = unflatten_dict(flat_config)

    # Use adapter to convert to YAML
    adapter = PyTorchLightningAdapter()
    yaml_str = adapter.config_to_yaml(nested)
    parsed = yaml.safe_load(yaml_str)

    assert parsed["model"]["backbone"] == "google/siglip2-so400m-patch14-384"
    assert parsed["model"]["bit_list"] == [8, 16, 32, 48, 64, 128]
    assert parsed["training"]["batch_size"] == 128
    assert parsed["loss"]["temperature"] == 0.07


# =============================================================================
# Helper Functions
# =============================================================================


def _deep_diff(dict1: dict[str, Any], dict2: dict[str, Any], path: str = "") -> list[str]:
    """Recursively find differences between two nested dicts."""
    diffs = []

    all_keys = set(dict1.keys()) | set(dict2.keys())

    for key in all_keys:
        current_path = f"{path}.{key}" if path else key

        if key not in dict1:
            diffs.append(f"{current_path}: missing in dict1")
        elif key not in dict2:
            diffs.append(f"{current_path}: missing in dict2")
        else:
            val1, val2 = dict1[key], dict2[key]

            if isinstance(val1, dict) and isinstance(val2, dict):
                diffs.extend(_deep_diff(val1, val2, current_path))
            elif val1 != val2:
                diffs.append(f"{current_path}: {val1!r} != {val2!r}")

    return diffs
