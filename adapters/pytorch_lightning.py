"""PyTorch Lightning adapter for experiment execution."""

import json
import re
from typing import Any

import yaml

from adapters.base import BaseAdapter


class PyTorchLightningAdapter(BaseAdapter):
    """Adapter for PyTorch Lightning / custom train.py scripts.

    Designed for projects like vlm_quantization where the training script
    accepts a --config YAML file and prints JSON metrics to stdout.
    """

    def config_to_yaml(self, config: dict[str, Any]) -> str:
        """Convert nested config dict to YAML for train.py --config."""
        return yaml.dump(config, default_flow_style=False, allow_unicode=True)

    def get_train_command(self, yaml_path: str) -> list[str]:
        """Build: python train.py --config <yaml_path>."""
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
