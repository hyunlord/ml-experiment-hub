"""ML framework adapters for experiment execution."""

from adapters.base import BaseAdapter
from adapters.dummy_classifier.adapter import DummyClassifierAdapter
from adapters.huggingface import HuggingFaceAdapter
from adapters.pytorch_lightning import PyTorchLightningAdapter
from adapters.vlm_quantization.adapter import VLMQuantizationAdapter

# Adapter registry for dynamic loading
ADAPTER_REGISTRY: dict[str, type[BaseAdapter]] = {
    "pytorch_lightning": PyTorchLightningAdapter,
    "huggingface": HuggingFaceAdapter,
    "vlm_quantization": VLMQuantizationAdapter,
    "dummy_classifier": DummyClassifierAdapter,
}


def get_adapter(framework: str) -> BaseAdapter:
    """Get an adapter instance for the specified framework.

    Args:
        framework: Name of the ML framework.

    Returns:
        Instantiated adapter for the framework.

    Raises:
        ValueError: If framework is not supported.
    """
    adapter_class = ADAPTER_REGISTRY.get(framework)
    if adapter_class is None:
        supported = ", ".join(ADAPTER_REGISTRY.keys())
        raise ValueError(f"Unsupported framework: {framework}. Supported: {supported}")
    return adapter_class()


__all__ = [
    "BaseAdapter",
    "DummyClassifierAdapter",
    "HuggingFaceAdapter",
    "PyTorchLightningAdapter",
    "VLMQuantizationAdapter",
    "ADAPTER_REGISTRY",
    "get_adapter",
]
