"""Standalone training script for dummy image classifier.

Invoked by the platform as a subprocess:
    python -m adapters.dummy_classifier.train --config <yaml_path>

Outputs JSON metric lines to stdout so the platform can parse them.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, random_split

from adapters.dummy_classifier.model import SimpleCNN


def _get_dataset(name: str, data_root: str) -> tuple:
    """Download and return (train_dataset, test_dataset, in_channels, num_classes, class_names)."""
    from torchvision import datasets, transforms

    if name == "cifar10":
        transform = transforms.Compose(
            [
                transforms.ToTensor(),
                transforms.Normalize((0.4914, 0.4822, 0.4465), (0.2470, 0.2435, 0.2616)),
            ]
        )
        train_ds = datasets.CIFAR10(data_root, train=True, download=True, transform=transform)
        test_ds = datasets.CIFAR10(data_root, train=False, download=True, transform=transform)
        return train_ds, test_ds, 3, 10, train_ds.classes
    else:  # mnist (default)
        transform = transforms.Compose(
            [
                transforms.ToTensor(),
                transforms.Normalize((0.1307,), (0.3081,)),
            ]
        )
        train_ds = datasets.MNIST(data_root, train=True, download=True, transform=transform)
        test_ds = datasets.MNIST(data_root, train=False, download=True, transform=transform)
        class_names = [str(i) for i in range(10)]
        return train_ds, test_ds, 1, 10, class_names


def _emit(data: dict) -> None:
    """Print a JSON metric line to stdout (platform picks this up)."""
    print(json.dumps(data), flush=True)


def main(config_path: str) -> None:
    import yaml

    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    # Config defaults
    dataset_name: str = cfg.get("dataset", "mnist")
    data_root: str = cfg.get("data_root", os.environ.get("DATA_DIR", "./data"))
    lr: float = float(cfg.get("learning_rate", 0.001))
    batch_size: int = int(cfg.get("batch_size", 64))
    epochs: int = int(cfg.get("epochs", 5))
    checkpoint_dir: str = cfg.get(
        "checkpoint_dir",
        os.environ.get("CHECKPOINT_BASE_DIR", "./checkpoints"),
    )
    val_ratio: float = float(cfg.get("val_ratio", 0.1))

    device = "cuda" if torch.cuda.is_available() else "cpu"
    Path(checkpoint_dir).mkdir(parents=True, exist_ok=True)

    # Data
    train_full, test_ds, in_channels, num_classes, class_names = _get_dataset(
        dataset_name, data_root
    )
    val_size = max(1, int(len(train_full) * val_ratio))
    train_ds, val_ds = random_split(
        train_full,
        [len(train_full) - val_size, val_size],
        generator=torch.Generator().manual_seed(42),
    )

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=2)
    val_loader = DataLoader(val_ds, batch_size=batch_size * 2, num_workers=2)

    # Model
    model = SimpleCNN(in_channels=in_channels, num_classes=num_classes).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = nn.CrossEntropyLoss()

    global_step = 0
    best_val_acc = 0.0

    for epoch in range(1, epochs + 1):
        # ── Train ──
        model.train()
        running_loss = 0.0
        correct = 0
        total = 0
        t0 = time.time()

        for batch_idx, (images, labels) in enumerate(train_loader):
            images, labels = images.to(device), labels.to(device)

            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()

            running_loss += loss.item() * images.size(0)
            _, predicted = outputs.max(1)
            correct += predicted.eq(labels).sum().item()
            total += labels.size(0)
            global_step += 1

            # Emit per-step metrics every 50 steps
            if global_step % 50 == 0:
                _emit(
                    {
                        "step": global_step,
                        "epoch": epoch,
                        "train/loss": round(loss.item(), 4),
                        "train/accuracy": round(correct / total, 4),
                        "lr": lr,
                    }
                )

        train_loss = running_loss / total
        train_acc = correct / total

        # ── Validate ──
        model.eval()
        val_loss_sum = 0.0
        val_correct = 0
        val_total = 0

        with torch.no_grad():
            for images, labels in val_loader:
                images, labels = images.to(device), labels.to(device)
                outputs = model(images)
                loss = criterion(outputs, labels)
                val_loss_sum += loss.item() * images.size(0)
                _, predicted = outputs.max(1)
                val_correct += predicted.eq(labels).sum().item()
                val_total += labels.size(0)

        val_loss = val_loss_sum / max(val_total, 1)
        val_acc = val_correct / max(val_total, 1)
        elapsed = time.time() - t0

        # Emit epoch summary
        _emit(
            {
                "step": global_step,
                "epoch": epoch,
                "train/loss": round(train_loss, 4),
                "train/accuracy": round(train_acc, 4),
                "val/loss": round(val_loss, 4),
                "val/accuracy": round(val_acc, 4),
                "epoch_time_s": round(elapsed, 1),
            }
        )

        # Save checkpoint
        ckpt_path = Path(checkpoint_dir) / f"epoch_{epoch}.pt"
        torch.save(
            {
                "model_state_dict": model.state_dict(),
                "epoch": epoch,
                "global_step": global_step,
                "val_accuracy": val_acc,
                "in_channels": in_channels,
                "num_classes": num_classes,
                "class_names": class_names,
                "config": cfg,
            },
            ckpt_path,
        )

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_path = Path(checkpoint_dir) / "best.pt"
            torch.save(
                {
                    "model_state_dict": model.state_dict(),
                    "epoch": epoch,
                    "global_step": global_step,
                    "val_accuracy": val_acc,
                    "in_channels": in_channels,
                    "num_classes": num_classes,
                    "class_names": class_names,
                    "config": cfg,
                },
                best_path,
            )

    print(f"Training complete. Best val accuracy: {best_val_acc:.4f}", file=sys.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train dummy classifier")
    parser.add_argument("--config", required=True, help="Path to YAML config")
    args = parser.parse_args()
    main(args.config)
