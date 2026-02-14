"""Platform adapter for VLM Quantization framework.

Integrates the cross-modal hashing model with the ML Experiment Hub
training/evaluation pipeline.
"""

from __future__ import annotations

import json
import re
from typing import Any

import yaml

from adapters.base import BaseAdapter


class VLMQuantizationAdapter(BaseAdapter):
    """Adapter for VLM Quantization (cross-modal hashing) experiments.

    Handles:
    - Config YAML generation for vlm_quantization training
    - Training command construction
    - Metric log parsing from training output
    """

    def config_to_yaml(self, config: dict[str, Any]) -> str:
        """Convert nested config to YAML for vlm_quantization."""
        return yaml.dump(config, default_flow_style=False, allow_unicode=True)

    def get_train_command(self, yaml_path: str) -> list[str]:
        """Build the vlm_quantization training command."""
        return ["python", "-m", "src.train", "--config", yaml_path]

    def parse_metrics(self, log_line: str) -> dict[str, Any] | None:
        """Parse metrics from vlm_quantization training output.

        Expected formats:
        - JSON: {"step": 100, "train/loss": 0.5, "val/map_64": 0.8}
        - Key=value: step=100 train/loss=0.5 val/map_64=0.8
        """
        # Try JSON format first
        if "{" in log_line:
            try:
                data = json.loads(log_line.strip())
                if isinstance(data, dict) and "step" in data:
                    return data
            except json.JSONDecodeError:
                pass

        # Try key=value format
        if "step=" in log_line:
            metrics: dict[str, Any] = {}
            for match in re.finditer(r"(\S+)=([0-9.e\-+]+)", log_line):
                key, value = match.group(1), match.group(2)
                try:
                    metrics[key] = int(value)
                except ValueError:
                    try:
                        metrics[key] = float(value)
                    except ValueError:
                        metrics[key] = value

            if "step" in metrics:
                return metrics

        return None

    def get_name(self) -> str:
        return "VLM Quantization (Cross-Modal Hashing)"

    def get_metrics_mapping(self) -> dict[str, dict[str, str]]:
        """Return metric display metadata for cross-modal hashing."""
        return {
            "train/loss": {
                "group": "Training",
                "label": "Training Loss",
                "direction": "minimize",
            },
            "train/quant_loss": {
                "group": "Training",
                "label": "Quantization Loss",
                "direction": "minimize",
            },
            "val/loss": {
                "group": "Validation",
                "label": "Validation Loss",
                "direction": "minimize",
            },
            "val/map_8": {
                "group": "Retrieval (mAP)",
                "label": "mAP@8bit",
                "direction": "maximize",
            },
            "val/map_16": {
                "group": "Retrieval (mAP)",
                "label": "mAP@16bit",
                "direction": "maximize",
            },
            "val/map_32": {
                "group": "Retrieval (mAP)",
                "label": "mAP@32bit",
                "direction": "maximize",
            },
            "val/map_64": {
                "group": "Retrieval (mAP)",
                "label": "mAP@64bit",
                "direction": "maximize",
            },
            "val/map_128": {
                "group": "Retrieval (mAP)",
                "label": "mAP@128bit",
                "direction": "maximize",
            },
        }

    def inject_monitor_config(
        self,
        config: dict[str, Any],
        run_id: int,
        server_url: str,
    ) -> dict[str, Any]:
        """Inject MonitorCallback config into the training config."""
        if "callbacks" not in config:
            config["callbacks"] = {}
        config["callbacks"]["monitor"] = {
            "run_id": run_id,
            "server_url": server_url,
        }
        return config
