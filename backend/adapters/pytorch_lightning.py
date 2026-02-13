"""PyTorch Lightning adapter for ML Experiment Hub.

Converts a flat dot-notation config dict (as stored in ExperimentConfig.config_json)
into a nested YAML file compatible with the vlm_quantization training script,
resolves dataset paths, and generates the train command.

Usage:
    from backend.adapters.pytorch_lightning import PyTorchLightningAdapter

    adapter = PyTorchLightningAdapter(data_root="/data")
    yaml_path = adapter.write_config(config_dict, output_dir="/tmp/exp_42")
    command = adapter.build_train_command(yaml_path)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Dataset path mapping
# ---------------------------------------------------------------------------

# Maps short dataset identifiers (used in the multi-select UI) to their
# on-disk layout. Paths are relative to `data_root`.
DATASET_REGISTRY: dict[str, dict[str, str]] = {
    "coco_ko": {
        "jsonl_path": "coco_ko/coco_ko.jsonl",
        "data_root": "coco",  # images shared with base COCO
    },
    "aihub": {
        "jsonl_path": "aihub/aihub_71454.jsonl",
        "data_root": "aihub",
    },
    "cc3m_ko": {
        "jsonl_path": "cc3m_ko/cc3m_ko.jsonl",
        "data_root": "cc3m_ko",
    },
}


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class PyTorchLightningAdapter:
    """Converts hub config dicts into PyTorch Lightning YAML configs."""

    def __init__(self, data_root: str = "./data") -> None:
        self.data_root = Path(data_root)

    # -- Public API ---------------------------------------------------------

    def to_nested(self, flat: dict[str, Any]) -> dict[str, Any]:
        """Convert dot-notation flat dict to nested dict.

        Example:
            {"model.backbone": "siglip2", "training.batch_size": 128}
            →
            {"model": {"backbone": "siglip2"}, "training": {"batch_size": 128}}
        """
        nested: dict[str, Any] = {}
        for key, value in flat.items():
            parts = key.split(".")
            current = nested
            for part in parts[:-1]:
                current = current.setdefault(part, {})
            current[parts[-1]] = value
        return nested

    def resolve_datasets(self, config: dict[str, Any]) -> dict[str, Any]:
        """Resolve extra_datasets identifiers to full path entries.

        Transforms:
            data.extra_datasets: ["coco_ko", "aihub"]
        Into:
            data.extra_datasets:
              - jsonl_path: /data/coco_ko/coco_ko.jsonl
                data_root: /data/coco
              - jsonl_path: /data/aihub/aihub_71454.jsonl
                data_root: /data/aihub
        """
        data = config.get("data", {})
        if not isinstance(data, dict):
            return config

        extra = data.get("extra_datasets")
        if not extra or not isinstance(extra, list):
            return config

        resolved = []
        for dataset_id in extra:
            if isinstance(dataset_id, str) and dataset_id in DATASET_REGISTRY:
                entry = DATASET_REGISTRY[dataset_id]
                resolved.append({
                    "jsonl_path": str(self.data_root / entry["jsonl_path"]),
                    "data_root": str(self.data_root / entry["data_root"]),
                })
            elif isinstance(dataset_id, dict):
                # Already resolved — pass through
                resolved.append(dataset_id)

        config = {**config}
        config["data"] = {**data, "extra_datasets": resolved}
        return config

    def coerce_types(self, config: dict[str, Any]) -> dict[str, Any]:
        """Coerce string-typed values back to their native Python types.

        The form UI may send numeric values as strings (e.g. batch_size "128",
        image_size "384"). Convert them back for YAML correctness.
        """
        config = _deep_copy(config)

        training = config.get("training", {})
        if isinstance(training, dict):
            bs = training.get("batch_size")
            if isinstance(bs, str) and bs != "auto":
                try:
                    training["batch_size"] = int(bs)
                except ValueError:
                    pass

        data = config.get("data", {})
        if isinstance(data, dict):
            img_size = data.get("image_size")
            if isinstance(img_size, str):
                try:
                    data["image_size"] = int(img_size)
                except ValueError:
                    pass

        return config

    def prepare(self, flat_config: dict[str, Any]) -> dict[str, Any]:
        """Full pipeline: flatten → nest → resolve datasets → coerce types.

        Also injects default data_root and karpathy_json paths when missing.
        """
        nested = self.to_nested(flat_config)
        nested = self.resolve_datasets(nested)
        nested = self.coerce_types(nested)

        # Inject data paths if missing
        data = nested.setdefault("data", {})
        data.setdefault("data_root", str(self.data_root / "coco"))
        data.setdefault(
            "karpathy_json",
            str(self.data_root / "coco" / "dataset_coco.json"),
        )

        return nested

    def to_yaml(self, flat_config: dict[str, Any]) -> str:
        """Convert a flat config dict to a YAML string."""
        nested = self.prepare(flat_config)
        return yaml.dump(
            nested,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )

    def write_config(
        self,
        flat_config: dict[str, Any],
        output_dir: str | Path,
        filename: str = "config.yaml",
    ) -> Path:
        """Write a flat config dict as a YAML file.

        Returns the absolute path to the written file.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        yaml_path = output_dir / filename
        yaml_path.write_text(self.to_yaml(flat_config), encoding="utf-8")
        return yaml_path.resolve()

    def build_train_command(
        self,
        yaml_path: str | Path,
        *,
        script: str = "train.py",
        extra_args: list[str] | None = None,
    ) -> str:
        """Generate the training CLI command.

        Returns:
            "python train.py --config /abs/path/to/config.yaml [extra_args]"
        """
        yaml_path = Path(yaml_path).resolve()
        parts = ["python", script, "--config", str(yaml_path)]
        if extra_args:
            parts.extend(extra_args)
        return " ".join(parts)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _deep_copy(d: dict[str, Any]) -> dict[str, Any]:
    """Shallow-recursive copy of a nested dict (avoids mutating the original)."""
    out: dict[str, Any] = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out[k] = _deep_copy(v)
        elif isinstance(v, list):
            out[k] = list(v)
        else:
            out[k] = v
    return out


# ---------------------------------------------------------------------------
# CLI convenience
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Quick demo: convert the default preset to YAML
    from backend.seeds.vlm_quantization import PRESET_CONFIGS

    adapter = PyTorchLightningAdapter(data_root="./data")

    for preset_name, preset in PRESET_CONFIGS.items():
        print(f"{'=' * 60}")
        print(f"Preset: {preset['name']}")
        print(f"{'=' * 60}")
        yaml_str = adapter.to_yaml(preset["config"])
        print(yaml_str)

        cmd = adapter.build_train_command(f"/tmp/{preset_name}/config.yaml")
        print(f"Command: {cmd}\n")
