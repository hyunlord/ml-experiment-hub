"""Base adapter interface for ML frameworks."""

from abc import ABC, abstractmethod
from typing import Any

from shared.schemas import ExperimentConfig, MetricPoint


class BaseAdapter(ABC):
    """
    Abstract base class for ML framework adapters.

    Adapters handle framework-specific logic for launching experiments,
    collecting metrics, and managing experiment lifecycle.
    """

    @abstractmethod
    async def validate_config(self, config: ExperimentConfig) -> None:
        """
        Validate that the experiment configuration is valid for this framework.

        Args:
            config: Experiment configuration to validate

        Raises:
            ValueError: If configuration is invalid
        """
        pass

    @abstractmethod
    async def launch_experiment(self, experiment_id: str, config: ExperimentConfig) -> str:
        """
        Launch an experiment with the given configuration.

        Args:
            experiment_id: Unique identifier for this experiment
            config: Experiment configuration

        Returns:
            Process ID or job ID for the launched experiment

        Raises:
            RuntimeError: If experiment fails to launch
        """
        pass

    @abstractmethod
    async def stop_experiment(self, process_id: str) -> None:
        """
        Stop a running experiment.

        Args:
            process_id: Process or job ID returned by launch_experiment

        Raises:
            RuntimeError: If experiment cannot be stopped
        """
        pass

    @abstractmethod
    async def get_metrics(self, experiment_id: str) -> list[MetricPoint]:
        """
        Retrieve metrics for an experiment.

        Args:
            experiment_id: Unique identifier for the experiment

        Returns:
            List of metric measurements

        Raises:
            RuntimeError: If metrics cannot be retrieved
        """
        pass

    async def cleanup(self, experiment_id: str) -> None:
        """
        Clean up resources after experiment completion (optional).

        Args:
            experiment_id: Unique identifier for the experiment
        """
        pass
