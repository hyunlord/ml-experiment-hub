"""Base adapter interface for ML framework integration."""

from abc import ABC, abstractmethod
from typing import Any


class BaseAdapter(ABC):
    """Abstract base class for ML framework adapters.

    Each adapter knows how to:
    1. Convert a flat config dict into framework-specific YAML
    2. Build the shell command to launch training
    3. Parse stdout log lines into metric dicts
    """

    @abstractmethod
    def config_to_yaml(self, config: dict[str, Any]) -> str:
        """Convert a nested config dict to framework-specific YAML content.

        Args:
            config: Nested config dict (already unflattened from dot-notation).

        Returns:
            YAML string ready to write to a file.
        """

    @abstractmethod
    def get_train_command(self, yaml_path: str) -> list[str]:
        """Build the command to launch a training process.

        Args:
            yaml_path: Path to the generated YAML config file.

        Returns:
            Command as a list of strings (for subprocess).
        """

    @abstractmethod
    def parse_metrics(self, log_line: str) -> dict[str, Any] | None:
        """Try to parse a stdout line into a metrics dict.

        Args:
            log_line: A single line of stdout from the training process.

        Returns:
            Dict with at least 'step' key and metric values, or None
            if the line doesn't contain metrics.
        """

    def get_name(self) -> str:
        """Return human-readable adapter name."""
        return self.__class__.__name__
