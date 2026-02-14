"""PyTorch Lightning adapter for experiment execution.

Handles vlm_quantization (Cross-Modal Deep Hashing) project:
- Converts flat UI config → nested YAML with extra_datasets path resolution
- Builds train command with project venv Python detection
- Parses JSON metric lines from stdout
- Provides metrics mapping for dashboard chart grouping
"""

import json
import os
import re
from pathlib import Path
from typing import Any

import yaml

from adapters.base import BaseAdapter

# Registry mapping UI dataset keys → relative path structure.
# Paths are relative to DATA_DIR (mounted at /ml-data in Docker).
DATASET_REGISTRY: dict[str, dict[str, str]] = {
    "coco_ko": {
        "jsonl_path": "coco_ko/coco_ko.jsonl",
        "data_root": "coco",  # reuses COCO images
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


class PyTorchLightningAdapter(BaseAdapter):
    """Adapter for PyTorch Lightning / custom train.py scripts.

    Designed for projects like vlm_quantization where the training script
    accepts a --config YAML file and prints JSON metrics to stdout.
    """

    def inject_monitor_config(
        self, config: dict[str, Any], run_id: int, server_url: str = "http://localhost:8000"
    ) -> dict[str, Any]:
        """Inject monitor settings so MonitorCallback reports to the hub.

        Sets monitor.enabled=true, monitor.server_url, and monitor.run_id
        so the training script's MonitorCallback posts metrics to the
        hub's compatibility bridge endpoints with the correct run ID.
        """
        config = {**config}
        monitor = config.get("monitor", {})
        if not isinstance(monitor, dict):
            monitor = {}
        monitor["enabled"] = True
        monitor["server_url"] = server_url
        monitor["run_id"] = str(run_id)
        config["monitor"] = monitor
        return config

    def config_to_yaml(self, config: dict[str, Any]) -> str:
        """Convert nested config dict to YAML for train.py --config.

        Handles special fields:
        - data.extra_datasets: converts UI keys ["coco_ko", "aihub"] to full
          path structures using DATASET_REGISTRY and DATA_DIR env var
        - training.batch_size: "auto" string passed through as-is
        - model.bit_list: ensures list type for YAML array output
        """
        config = {**config}  # shallow copy

        # Resolve extra_datasets keys → full path dicts
        if "data" in config and isinstance(config["data"], dict):
            data = config["data"] = {**config["data"]}
            extra = data.get("extra_datasets")
            if isinstance(extra, list) and extra:
                data_dir = os.environ.get("DATA_DIR", "./data")
                resolved = []
                for item in extra:
                    if isinstance(item, str):
                        # UI key like "coco_ko" → resolve to path dict
                        entry = DATASET_REGISTRY.get(item)
                        if entry:
                            resolved.append(
                                {
                                    "jsonl_path": str(Path(data_dir) / entry["jsonl_path"]),
                                    "data_root": str(Path(data_dir) / entry["data_root"]),
                                }
                            )
                    elif isinstance(item, dict):
                        # Already a full path dict (from clone/direct edit)
                        resolved.append(item)
                data["extra_datasets"] = resolved if resolved else None
            elif extra is not None and not extra:
                # Empty list → remove key so train.py uses COCO only
                data.pop("extra_datasets", None)

        # Ensure bit_list is a list (UI might send as other types)
        if "model" in config and isinstance(config["model"], dict):
            bit_list = config["model"].get("bit_list")
            if isinstance(bit_list, str):
                try:
                    config["model"]["bit_list"] = json.loads(bit_list)
                except json.JSONDecodeError:
                    pass

        # Handle batch_size: keep "auto" as string, convert numeric strings
        if "training" in config and isinstance(config["training"], dict):
            bs = config["training"].get("batch_size")
            if isinstance(bs, str) and bs != "auto":
                try:
                    config["training"]["batch_size"] = int(bs)
                except ValueError:
                    pass

        return yaml.dump(config, default_flow_style=False, allow_unicode=True)

    def get_train_command(self, yaml_path: str) -> list[str]:
        """Build the training command.

        Detects project environment:
        - If project has a uv-managed venv (pyproject.toml + uv.lock), uses uv run
        - Otherwise uses plain python (env_manager handles venv Python path)
        """
        projects_dir = os.environ.get("PROJECTS_DIR", "./projects")
        uv_lock = Path(projects_dir) / "uv.lock"
        pyproject = Path(projects_dir) / "pyproject.toml"

        if uv_lock.exists() and pyproject.exists():
            return ["uv", "run", "python", "train.py", "--config", yaml_path]

        return ["python", "train.py", "--config", yaml_path]

    def parse_metrics(self, log_line: str) -> dict[str, Any] | None:
        """Parse JSON metric lines from stdout.

        Expected format:
            {"step": 100, "epoch": 1, "train/loss": 0.5, "val/map": 0.8}

        Also handles prefixed lines like:
            [METRICS] {"step": 100, ...}
        """
        # Try to find JSON with "step" key
        match = re.search(r'\{[^{}]*"step"\s*:\s*\d+[^{}]*\}', log_line)
        if not match:
            return None

        try:
            data = json.loads(match.group())
            if isinstance(data, dict) and "step" in data:
                return data
        except (json.JSONDecodeError, TypeError):
            pass

        return None

    def get_metrics_mapping(self) -> dict[str, dict[str, str]]:
        """Return metric keys with chart grouping and display metadata.

        Based on MonitorCallback metric structure from vlm_quantization.
        """
        return {
            # ── Training Losses ──
            "train/total": {
                "group": "Loss",
                "label": "Total Loss",
                "direction": "minimize",
            },
            "train/contrastive": {
                "group": "Loss",
                "label": "Contrastive (InfoNCE)",
                "direction": "minimize",
            },
            "train/eaql": {
                "group": "Loss",
                "label": "Quantization (EAQL)",
                "direction": "minimize",
            },
            "train/ortho": {
                "group": "Loss",
                "label": "Orthogonal",
                "direction": "minimize",
            },
            "train/balance": {
                "group": "Loss",
                "label": "Bit Balance",
                "direction": "minimize",
            },
            "train/consistency": {
                "group": "Loss",
                "label": "Consistency",
                "direction": "minimize",
            },
            "train/lcs": {
                "group": "Loss",
                "label": "LCS Distillation",
                "direction": "minimize",
            },
            "train/distillation": {
                "group": "Loss",
                "label": "Distillation",
                "direction": "minimize",
            },
            "train/adapter_align": {
                "group": "Loss",
                "label": "Adapter Alignment",
                "direction": "minimize",
            },
            # ── Validation Losses ──
            "val/total": {
                "group": "Validation Loss",
                "label": "Val Total Loss",
                "direction": "minimize",
            },
            "val/contrastive": {
                "group": "Validation Loss",
                "label": "Val Contrastive",
                "direction": "minimize",
            },
            "val/eaql": {
                "group": "Validation Loss",
                "label": "Val Quantization",
                "direction": "minimize",
            },
            "val/ortho": {
                "group": "Validation Loss",
                "label": "Val Orthogonal",
                "direction": "minimize",
            },
            "val/balance": {
                "group": "Validation Loss",
                "label": "Val Balance",
                "direction": "minimize",
            },
            "val/consistency": {
                "group": "Validation Loss",
                "label": "Val Consistency",
                "direction": "minimize",
            },
            "val/lcs": {
                "group": "Validation Loss",
                "label": "Val LCS",
                "direction": "minimize",
            },
            # ── Retrieval Metrics ──
            "val/map_i2t": {
                "group": "Retrieval",
                "label": "mAP I→T",
                "direction": "maximize",
            },
            "val/map_t2i": {
                "group": "Retrieval",
                "label": "mAP T→I",
                "direction": "maximize",
            },
            "val/p1": {
                "group": "Retrieval",
                "label": "P@1",
                "direction": "maximize",
            },
            "val/p5": {
                "group": "Retrieval",
                "label": "P@5",
                "direction": "maximize",
            },
            "val/p10": {
                "group": "Retrieval",
                "label": "P@10",
                "direction": "maximize",
            },
            # ── Backbone Baseline ──
            "val/backbone_map_i2t": {
                "group": "Backbone Baseline",
                "label": "Backbone mAP I→T",
                "direction": "maximize",
            },
            "val/backbone_map_t2i": {
                "group": "Backbone Baseline",
                "label": "Backbone mAP T→I",
                "direction": "maximize",
            },
            "val/backbone_p1": {
                "group": "Backbone Baseline",
                "label": "Backbone P@1",
                "direction": "maximize",
            },
            "val/backbone_p5": {
                "group": "Backbone Baseline",
                "label": "Backbone P@5",
                "direction": "maximize",
            },
            "val/backbone_p10": {
                "group": "Backbone Baseline",
                "label": "Backbone P@10",
                "direction": "maximize",
            },
            # ── Hash Quality ──
            "val/8_bit_entropy": {
                "group": "Hash Quality",
                "label": "8-bit Entropy",
                "direction": "maximize",
            },
            "val/16_bit_entropy": {
                "group": "Hash Quality",
                "label": "16-bit Entropy",
                "direction": "maximize",
            },
            "val/32_bit_entropy": {
                "group": "Hash Quality",
                "label": "32-bit Entropy",
                "direction": "maximize",
            },
            "val/48_bit_entropy": {
                "group": "Hash Quality",
                "label": "48-bit Entropy",
                "direction": "maximize",
            },
            "val/64_bit_entropy": {
                "group": "Hash Quality",
                "label": "64-bit Entropy",
                "direction": "maximize",
            },
            "val/128_bit_entropy": {
                "group": "Hash Quality",
                "label": "128-bit Entropy",
                "direction": "maximize",
            },
            "val/8_quant_error": {
                "group": "Hash Quality",
                "label": "8-bit Quant Error",
                "direction": "minimize",
            },
            "val/16_quant_error": {
                "group": "Hash Quality",
                "label": "16-bit Quant Error",
                "direction": "minimize",
            },
            "val/32_quant_error": {
                "group": "Hash Quality",
                "label": "32-bit Quant Error",
                "direction": "minimize",
            },
            "val/48_quant_error": {
                "group": "Hash Quality",
                "label": "48-bit Quant Error",
                "direction": "minimize",
            },
            "val/64_quant_error": {
                "group": "Hash Quality",
                "label": "64-bit Quant Error",
                "direction": "minimize",
            },
            "val/128_quant_error": {
                "group": "Hash Quality",
                "label": "128-bit Quant Error",
                "direction": "minimize",
            },
            # ── Learning Rate ──
            "lr": {
                "group": "Training",
                "label": "Learning Rate",
                "direction": "minimize",
            },
            "train/temperature": {
                "group": "Training",
                "label": "Temperature",
                "direction": "minimize",
            },
        }
