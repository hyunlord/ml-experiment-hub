"""Cross-modal hash model for inference.

Re-implements the inference path of CrossModalHashModel from vlm_quantization.
Supports both real SigLIP2 backbones and a DummyBackbone for testing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import torch
import torch.nn as nn

from adapters.vlm_quantization.hash_layer import DEFAULT_BIT_LIST, NestedHashLayer

logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """Configuration for CrossModalHashModel."""

    backbone_name: str = "dummy"
    backbone_dim: int = 768
    bit_list: list[int] | None = None
    hidden_dim: int | None = None
    dropout: float = 0.1
    image_size: int = 384


class DummyVisionModel(nn.Module):
    """Dummy vision encoder that replaces SigLIP2 for testing.

    Accepts images of any size and projects to backbone_dim via
    adaptive pooling + linear projection.
    """

    def __init__(self, output_dim: int = 768) -> None:
        super().__init__()
        self.output_dim = output_dim
        self.conv = nn.Conv2d(3, 64, kernel_size=3, padding=1)
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.proj = nn.Linear(64, output_dim)

    def forward(self, pixel_values: torch.Tensor) -> Any:
        """Forward pass. Returns object with pooler_output attribute."""
        x = self.conv(pixel_values)
        x = torch.relu(x)
        x = self.pool(x).squeeze(-1).squeeze(-1)  # (batch, 64)
        x = self.proj(x)  # (batch, output_dim)

        class _Output:
            def __init__(self, pooler: torch.Tensor) -> None:
                self.pooler_output = pooler

        return _Output(x)


class DummyTextModel(nn.Module):
    """Dummy text encoder that replaces SigLIP2 for testing.

    Accepts token IDs and projects to backbone_dim via embedding + mean pool.
    """

    def __init__(self, vocab_size: int = 32000, output_dim: int = 768) -> None:
        super().__init__()
        self.output_dim = output_dim
        self.embed = nn.Embedding(vocab_size, 128)
        self.proj = nn.Linear(128, output_dim)

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor | None = None,
    ) -> Any:
        """Forward pass. Returns object with pooler_output attribute."""
        x = self.embed(input_ids)  # (batch, seq_len, 128)

        if attention_mask is not None:
            mask = attention_mask.unsqueeze(-1).float()
            x = (x * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1)
        else:
            x = x.mean(dim=1)

        x = self.proj(x)  # (batch, output_dim)

        class _Output:
            def __init__(self, pooler: torch.Tensor) -> None:
                self.pooler_output = pooler

        return _Output(x)


class DummyBackbone(nn.Module):
    """Combined dummy backbone with vision + text models."""

    def __init__(self, output_dim: int = 768) -> None:
        super().__init__()
        self.vision_model = DummyVisionModel(output_dim)
        self.text_model = DummyTextModel(output_dim=output_dim)
        self.output_dim = output_dim


class CrossModalHashModel(nn.Module):
    """Cross-modal hashing model for image-text retrieval.

    Architecture:
        image → vision_model → pool → image_hash → binary codes
        text  → text_model  → pool → text_hash  → binary codes

    The image and text hash layers share the same bit_list so that
    cross-modal hamming distance comparison is valid.
    """

    def __init__(self, config: ModelConfig | None = None) -> None:
        super().__init__()
        if config is None:
            config = ModelConfig()
        self.config = config

        bit_list = config.bit_list or DEFAULT_BIT_LIST
        backbone_dim = config.backbone_dim

        # Backbone
        if config.backbone_name == "dummy":
            self.backbone = DummyBackbone(backbone_dim)
        else:
            # Real backbone loading would go here
            raise ValueError(
                f"Real backbone '{config.backbone_name}' not supported yet. "
                "Use 'dummy' for testing."
            )

        # Separate hash layers for image and text
        self.image_hash = NestedHashLayer(
            input_dim=backbone_dim,
            bit_list=bit_list,
            hidden_dim=config.hidden_dim,
            dropout=config.dropout,
        )
        self.text_hash = NestedHashLayer(
            input_dim=backbone_dim,
            bit_list=bit_list,
            hidden_dim=config.hidden_dim,
            dropout=config.dropout,
        )

    @property
    def bit_list(self) -> list[int]:
        return self.image_hash.bit_list

    def _pool(self, output: Any) -> torch.Tensor:
        """Extract pooled features from backbone output.

        Uses pooler_output if available, otherwise mean-pools
        the last hidden state.
        """
        if hasattr(output, "pooler_output") and output.pooler_output is not None:
            return output.pooler_output
        if hasattr(output, "last_hidden_state"):
            return output.last_hidden_state.mean(dim=1)
        raise ValueError("Cannot pool backbone output: no pooler_output or last_hidden_state")

    @torch.no_grad()
    def encode_image(
        self,
        pixel_values: torch.Tensor,
        bit_length: int | None = None,
        binary: bool = True,
        return_features: bool = False,
    ) -> torch.Tensor | tuple[torch.Tensor, torch.Tensor]:
        """Encode images to hash codes.

        Args:
            pixel_values: Image tensor (batch, 3, H, W).
            bit_length: Specific bit length. None = max_bit.
            binary: If True, return binary codes ({-1, +1}).
            return_features: If True, also return backbone features.

        Returns:
            Hash codes (batch, bit_length), or tuple of (codes, features).
        """
        self.eval()
        output = self.backbone.vision_model(pixel_values)
        features = self._pool(output)
        codes = self.image_hash(features, bit_length=bit_length, binary=binary)
        if return_features:
            return codes, features
        return codes

    @torch.no_grad()
    def encode_text(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor | None = None,
        bit_length: int | None = None,
        binary: bool = True,
        return_features: bool = False,
    ) -> torch.Tensor | tuple[torch.Tensor, torch.Tensor]:
        """Encode text to hash codes.

        Args:
            input_ids: Token IDs (batch, seq_len).
            attention_mask: Attention mask (batch, seq_len).
            bit_length: Specific bit length. None = max_bit.
            binary: If True, return binary codes ({-1, +1}).
            return_features: If True, also return backbone features.

        Returns:
            Hash codes (batch, bit_length), or tuple of (codes, features).
        """
        self.eval()
        output = self.backbone.text_model(input_ids=input_ids, attention_mask=attention_mask)
        features = self._pool(output)
        codes = self.text_hash(features, bit_length=bit_length, binary=binary)
        if return_features:
            return codes, features
        return codes

    @torch.no_grad()
    def encode_image_all_bits(
        self,
        pixel_values: torch.Tensor,
        binary: bool = True,
        return_features: bool = False,
    ) -> dict[int, torch.Tensor] | tuple[dict[int, torch.Tensor], torch.Tensor]:
        """Encode images to hash codes at all bit lengths."""
        self.eval()
        output = self.backbone.vision_model(pixel_values)
        features = self._pool(output)
        codes = self.image_hash.forward_all_bits(features, binary=binary)
        if return_features:
            return codes, features
        return codes

    @torch.no_grad()
    def encode_text_all_bits(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor | None = None,
        binary: bool = True,
        return_features: bool = False,
    ) -> dict[int, torch.Tensor] | tuple[dict[int, torch.Tensor], torch.Tensor]:
        """Encode text to hash codes at all bit lengths."""
        self.eval()
        output = self.backbone.text_model(input_ids=input_ids, attention_mask=attention_mask)
        features = self._pool(output)
        codes = self.text_hash.forward_all_bits(features, binary=binary)
        if return_features:
            return codes, features
        return codes


def load_model(
    checkpoint_path: str,
    device: str = "cpu",
    config: ModelConfig | None = None,
) -> CrossModalHashModel:
    """Load a CrossModalHashModel from a checkpoint.

    Args:
        checkpoint_path: Path to .pt checkpoint file.
        device: Device to load model on.
        config: Model config. If None, tries to load from checkpoint.

    Returns:
        Loaded model in eval mode.
    """
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)

    # Try to get config from checkpoint
    if config is None:
        ckpt_config = checkpoint.get("config", {})
        config = ModelConfig(
            backbone_name=ckpt_config.get("backbone_name", "dummy"),
            backbone_dim=ckpt_config.get("backbone_dim", 768),
            bit_list=ckpt_config.get("bit_list"),
            hidden_dim=ckpt_config.get("hidden_dim"),
            dropout=ckpt_config.get("dropout", 0.1),
        )

    model = CrossModalHashModel(config)

    # Load state dict
    state_dict = checkpoint.get("state_dict", checkpoint.get("model_state_dict", checkpoint))
    if isinstance(state_dict, dict) and not any(k.startswith("backbone.") for k in state_dict):
        # Might be the full checkpoint dict itself
        if "state_dict" not in state_dict and "model_state_dict" not in state_dict:
            state_dict = state_dict

    # Handle potential key prefix mismatches
    model_keys = set(model.state_dict().keys())
    if model_keys and not any(k in model_keys for k in state_dict.keys()):
        # Try removing common prefixes
        for prefix in ["model.", "module."]:
            new_state = {
                k[len(prefix) :] if k.startswith(prefix) else k: v for k, v in state_dict.items()
            }
            if any(k in model_keys for k in new_state.keys()):
                state_dict = new_state
                break

    model.load_state_dict(state_dict, strict=False)
    model.to(device)
    model.eval()

    logger.info(
        "Loaded model from %s (bit_list=%s, backbone_dim=%d)",
        checkpoint_path,
        config.bit_list or DEFAULT_BIT_LIST,
        config.backbone_dim,
    )
    return model
