"""Simple CNN model for MNIST / CIFAR-10 classification.

Intentionally minimal — exists to prove the platform can handle
any model type via the adapter interface.
"""

from __future__ import annotations

import torch
import torch.nn as nn


class SimpleCNN(nn.Module):
    """Tiny CNN that works with both MNIST (1×28×28) and CIFAR-10 (3×32×32).

    Uses AdaptiveAvgPool so the classifier head is input-size-agnostic.
    """

    def __init__(self, in_channels: int = 1, num_classes: int = 10) -> None:
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(in_channels, 32, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d(4),  # → 64×4×4 regardless of input size
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(64 * 4 * 4, 128),
            nn.ReLU(inplace=True),
            nn.Dropout(0.3),
            nn.Linear(128, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.classifier(self.features(x))


def load_model(checkpoint_path: str, device: str = "cpu") -> SimpleCNN:
    """Load a trained SimpleCNN from checkpoint.

    The checkpoint dict must contain 'model_state_dict', 'in_channels', 'num_classes'.
    """
    ckpt = torch.load(checkpoint_path, map_location=device, weights_only=False)
    model = SimpleCNN(
        in_channels=ckpt.get("in_channels", 1),
        num_classes=ckpt.get("num_classes", 10),
    )
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()
    return model
