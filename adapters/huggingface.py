"""HuggingFace Trainer adapter for experiment execution."""

import json
import re
from typing import Any

import yaml

from adapters.base import BaseAdapter


class HuggingFaceAdapter(BaseAdapter):
    """Adapter for HuggingFace Transformers Trainer.

    Generates config compatible with HuggingFace TrainingArguments
    and parses the Trainer's log output format.
    """

    def config_to_yaml(self, config: dict[str, Any]) -> str:
        """Convert nested config dict to HuggingFace-compatible YAML."""
        return yaml.dump(config, default_flow_style=False, allow_unicode=True)

    def get_train_command(self, yaml_path: str) -> list[str]:
        """Build: python train.py --config <yaml_path>."""
        return ["python", "train.py", "--config", yaml_path]

    def parse_metrics(self, log_line: str) -> dict[str, Any] | None:
        """Parse HuggingFace Trainer log lines.

        HF Trainer outputs lines like:
            {'loss': 0.5, 'learning_rate': 5e-05, 'epoch': 1.0}
            {"step": 100, "train_loss": 0.3}
        """
        # Try JSON format first
        match = re.search(r'\{[^{}]*"step"\s*:\s*\d+[^{}]*\}', log_line)
        if match:
            try:
                data = json.loads(match.group())
                if isinstance(data, dict) and "step" in data:
                    return data
            except (json.JSONDecodeError, TypeError):
                pass

        return None
