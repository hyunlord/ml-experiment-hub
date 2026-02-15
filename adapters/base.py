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

    def get_metrics_mapping(self) -> dict[str, dict[str, str]]:
        """Return mapping of metric keys to display metadata.

        Override to provide chart grouping, labels, and optimization direction
        for the frontend dashboard.

        Returns:
            Dict mapping metric key to {"group", "label", "direction"}.
            direction is "minimize" or "maximize".
        """
        return {}

    # ------------------------------------------------------------------
    # Optional: hyperparameter search ranges
    # Override to provide recommended search ranges for the UI.
    # ------------------------------------------------------------------

    def get_search_ranges(self) -> dict[str, dict[str, Any]]:
        """Return recommended search ranges for hyperparameter search.

        Override to suggest default min/max/type for searchable parameters.
        The UI uses this to pre-fill the search space editor.

        Returns:
            Dict mapping param key to {type, low, high, log, ...}.
            Example: {"lr": {"type": "float", "low": 1e-5, "high": 1e-2, "log": True}}
        """
        return {}

    # ------------------------------------------------------------------
    # Optional: search / index / eval capabilities
    # Override in adapter subclasses that support these features.
    # ------------------------------------------------------------------

    def load_model(self, checkpoint_path: str) -> Any:
        """Load a model checkpoint for inference.

        Returns:
            Model object ready for encoding.
        """
        raise NotImplementedError(f"{self.get_name()} does not support model loading")

    def load_index(self, index_path: str) -> dict[str, Any]:
        """Load a pre-built search index from disk.

        Returns:
            Index data dict.
        """
        raise NotImplementedError(f"{self.get_name()} does not support index loading")

    def search_by_text(
        self,
        model: Any,
        query: str,
        index_data: dict[str, Any],
        bit_length: int = 64,
        top_k: int = 20,
        method: str = "hamming",
    ) -> dict[str, Any]:
        """Text-to-image search.

        Returns:
            Dict with 'results', 'query_hash', 'search_time_ms', etc.
        """
        raise NotImplementedError(f"{self.get_name()} does not support text search")

    def search_by_image(
        self,
        model: Any,
        image_bytes: bytes,
        index_data: dict[str, Any],
        bit_length: int = 64,
        top_k: int = 20,
        method: str = "hamming",
    ) -> dict[str, Any]:
        """Image-to-text search.

        Returns:
            Dict with 'results', 'query_hash', 'search_time_ms', etc.
        """
        raise NotImplementedError(f"{self.get_name()} does not support image search")
