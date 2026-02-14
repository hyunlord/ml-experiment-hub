"""Nested hash layer for multi-resolution binary codes.

Re-implements NestedHashLayer from vlm_quantization for inference only.
Training-specific code (SignSTE gradient, loss functions) is excluded.
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


DEFAULT_BIT_LIST: list[int] = [8, 16, 32, 48, 64, 128]


class NestedHashLayer(nn.Module):
    """Multi-resolution hash layer with prefix-compatible binary codes.

    Architecture:
        input → Linear → LayerNorm → GELU → Dropout → Linear(max_bit)
        then for each bit_length in bit_list:
            prefix_slice[:bit_length] → BatchNorm → L2 normalize → sign

    The nested structure ensures that shorter codes are always a prefix
    of longer codes, enabling multi-resolution retrieval.
    """

    def __init__(
        self,
        input_dim: int,
        bit_list: list[int] | None = None,
        hidden_dim: int | None = None,
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        self.bit_list = bit_list or DEFAULT_BIT_LIST
        self.max_bit = max(self.bit_list)

        if hidden_dim is None:
            hidden_dim = input_dim

        # Projection layers
        self.fc1 = nn.Linear(input_dim, hidden_dim)
        self.layer_norm = nn.LayerNorm(hidden_dim)
        self.dropout = nn.Dropout(dropout)
        self.fc2 = nn.Linear(hidden_dim, self.max_bit)

        # Per-bit-length batch normalization
        self.bn_layers = nn.ModuleDict({str(b): nn.BatchNorm1d(b) for b in self.bit_list})

    def forward(
        self,
        x: torch.Tensor,
        bit_length: int | None = None,
        binary: bool = True,
    ) -> torch.Tensor:
        """Compute hash codes from input features.

        Args:
            x: Input tensor of shape (batch, input_dim).
            bit_length: Specific bit length to output. If None, uses max_bit.
            binary: If True, apply sign() for binary codes. If False, return
                continuous codes (tanh).

        Returns:
            Hash codes of shape (batch, bit_length).
        """
        if bit_length is None:
            bit_length = self.max_bit

        if bit_length not in self.bit_list:
            raise ValueError(f"bit_length {bit_length} not in bit_list {self.bit_list}")

        # Projection
        h = self.fc1(x)
        h = self.layer_norm(h)
        h = F.gelu(h)
        h = self.dropout(h)
        h = self.fc2(h)  # (batch, max_bit)

        # Prefix slice
        h = h[:, :bit_length]

        # BatchNorm (skip if batch_size == 1 during eval)
        bn = self.bn_layers[str(bit_length)]
        if h.size(0) > 1 or not self.training:
            h = bn(h)

        # L2 normalize
        h = F.normalize(h, p=2, dim=-1)

        # Binary or continuous
        if binary:
            h = h.sign()
        else:
            h = torch.tanh(h)

        return h

    def forward_all_bits(self, x: torch.Tensor, binary: bool = True) -> dict[int, torch.Tensor]:
        """Compute hash codes for all bit lengths at once.

        Args:
            x: Input tensor of shape (batch, input_dim).
            binary: If True, apply sign() for binary codes.

        Returns:
            Dict mapping bit_length to hash codes tensor.
        """
        # Shared projection
        h = self.fc1(x)
        h = self.layer_norm(h)
        h = F.gelu(h)
        h = self.dropout(h)
        h = self.fc2(h)  # (batch, max_bit)

        results: dict[int, torch.Tensor] = {}
        for bit_length in sorted(self.bit_list):
            prefix = h[:, :bit_length]

            bn = self.bn_layers[str(bit_length)]
            if prefix.size(0) > 1 or not self.training:
                prefix = bn(prefix)

            prefix = F.normalize(prefix, p=2, dim=-1)

            if binary:
                prefix = prefix.sign()
            else:
                prefix = torch.tanh(prefix)

            results[bit_length] = prefix

        return results
