"""VLM Quantization adapter — inference-only re-implementation.

Provides cross-modal hashing inference, evaluation, index building,
and search without depending on the original vlm_quantization package.
"""

from adapters.vlm_quantization.adapter import VLMQuantizationAdapter

__all__ = ["VLMQuantizationAdapter"]
