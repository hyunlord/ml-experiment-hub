"""PyTorch Lightning adapter for experiment execution."""

from shared.schemas import ExperimentConfig, MetricPoint

from adapters.base import BaseAdapter


class PyTorchLightningAdapter(BaseAdapter):
    """
    Adapter for PyTorch Lightning experiments.

    Handles launching, monitoring, and stopping PyTorch Lightning training jobs.
    """

    async def validate_config(self, config: ExperimentConfig) -> None:
        """
        Validate PyTorch Lightning experiment configuration.

        Args:
            config: Experiment configuration to validate

        Raises:
            ValueError: If configuration is invalid
        """
        # TODO: Implement validation logic
        # - Check script_path exists and is executable
        # - Validate hyperparameters contain required fields
        # - Verify PyTorch Lightning is installed
        if not config.script_path:
            raise ValueError("script_path is required for PyTorch Lightning experiments")

    async def launch_experiment(self, experiment_id: str, config: ExperimentConfig) -> str:
        """
        Launch a PyTorch Lightning experiment.

        Args:
            experiment_id: Unique identifier for this experiment
            config: Experiment configuration

        Returns:
            Process ID for the launched training job

        Raises:
            RuntimeError: If experiment fails to launch
        """
        # TODO: Implement launcher logic
        # - Set up logging callbacks
        # - Configure checkpoint directory
        # - Launch subprocess with hyperparameters
        # - Set up metric collection hooks
        raise NotImplementedError("PyTorch Lightning launcher coming soon")

    async def stop_experiment(self, process_id: str) -> None:
        """
        Stop a running PyTorch Lightning experiment.

        Args:
            process_id: Process ID returned by launch_experiment

        Raises:
            RuntimeError: If experiment cannot be stopped
        """
        # TODO: Implement stop logic
        # - Send SIGTERM to process
        # - Wait for graceful shutdown
        # - Force kill if necessary
        raise NotImplementedError("PyTorch Lightning stop coming soon")

    async def get_metrics(self, experiment_id: str) -> list[MetricPoint]:
        """
        Retrieve metrics from a PyTorch Lightning experiment.

        Args:
            experiment_id: Unique identifier for the experiment

        Returns:
            List of metric measurements

        Raises:
            RuntimeError: If metrics cannot be retrieved
        """
        # TODO: Implement metric collection
        # - Parse TensorBoard logs
        # - Read from checkpoint metadata
        # - Convert to MetricPoint format
        return []

    async def cleanup(self, experiment_id: str) -> None:
        """
        Clean up PyTorch Lightning experiment resources.

        Args:
            experiment_id: Unique identifier for the experiment
        """
        # TODO: Implement cleanup
        # - Remove temporary files
        # - Archive checkpoints
        # - Clear GPU memory
        pass
