"""Evaluation utilities for the dummy classifier adapter.

Computes accuracy, per-class precision/recall/F1 — returns a dict
suitable for the platform's generic result rendering.
"""

from __future__ import annotations

from typing import Any

import torch
from torch.utils.data import DataLoader


def evaluate(
    model: torch.nn.Module,
    dataloader: DataLoader,
    class_names: list[str] | None = None,
    device: str = "cpu",
) -> dict[str, Any]:
    """Run evaluation and return a classification report dict.

    Returns:
        {
            "accuracy": float,
            "per_class": [{"class": str, "precision": float, "recall": float, "f1": float}, ...],
            "macro_precision": float,
            "macro_recall": float,
            "macro_f1": float,
            "total_samples": int,
        }
    """
    model.eval()
    num_classes = 0
    all_preds: list[int] = []
    all_labels: list[int] = []

    with torch.no_grad():
        for images, labels in dataloader:
            images, labels = images.to(device), labels.to(device)
            outputs = model(images)
            num_classes = max(num_classes, outputs.size(1))
            _, predicted = outputs.max(1)
            all_preds.extend(predicted.cpu().tolist())
            all_labels.extend(labels.cpu().tolist())

    if class_names is None:
        class_names = [str(i) for i in range(num_classes)]

    # Per-class stats
    per_class = []
    macro_p, macro_r, macro_f1 = 0.0, 0.0, 0.0

    for c in range(len(class_names)):
        tp = sum(1 for p, lb in zip(all_preds, all_labels) if p == c and lb == c)
        fp = sum(1 for p, lb in zip(all_preds, all_labels) if p == c and lb != c)
        fn = sum(1 for p, lb in zip(all_preds, all_labels) if p != c and lb == c)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        per_class.append(
            {
                "class": class_names[c],
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "f1": round(f1, 4),
            }
        )
        macro_p += precision
        macro_r += recall
        macro_f1 += f1

    n = max(len(class_names), 1)
    correct = sum(1 for p, lb in zip(all_preds, all_labels) if p == lb)
    accuracy = correct / max(len(all_labels), 1)

    return {
        "accuracy": round(accuracy, 4),
        "per_class": per_class,
        "macro_precision": round(macro_p / n, 4),
        "macro_recall": round(macro_r / n, 4),
        "macro_f1": round(macro_f1 / n, 4),
        "total_samples": len(all_labels),
    }
