"""Platform adapter for the dummy image classifier.

Proves that any ML model type can plug into the platform
by implementing only the BaseAdapter interface.
"""

from __future__ import annotations

import json
import re
from typing import Any

import yaml

from adapters.base import BaseAdapter


class DummyClassifierAdapter(BaseAdapter):
    """Adapter for simple image classification (MNIST / CIFAR-10).

    Handles:
    - Config YAML generation
    - Training command construction
    - Metric log parsing
    - Model loading for inference
    """

    # ── Core interface ────────────────────────────────────────────────

    def config_to_yaml(self, config: dict[str, Any]) -> str:
        return yaml.dump(config, default_flow_style=False, allow_unicode=True)

    def get_train_command(self, yaml_path: str) -> list[str]:
        return [
            "python",
            "-m",
            "adapters.dummy_classifier.train",
            "--config",
            yaml_path,
        ]

    def parse_metrics(self, log_line: str) -> dict[str, Any] | None:
        """Parse JSON metric lines emitted by the training script."""
        if "{" in log_line:
            try:
                data = json.loads(log_line.strip())
                if isinstance(data, dict) and "step" in data:
                    return data
            except json.JSONDecodeError:
                pass

        # Fallback: key=value format
        if "step=" in log_line:
            metrics: dict[str, Any] = {}
            for match in re.finditer(r"(\S+)=([0-9.e\-+]+)", log_line):
                key, value = match.group(1), match.group(2)
                try:
                    metrics[key] = int(value)
                except ValueError:
                    try:
                        metrics[key] = float(value)
                    except ValueError:
                        metrics[key] = value
            if "step" in metrics:
                return metrics

        return None

    def get_name(self) -> str:
        return "Image Classifier (MNIST / CIFAR-10)"

    def get_metrics_mapping(self) -> dict[str, dict[str, str]]:
        return {
            "train/loss": {
                "group": "Training",
                "label": "Training Loss",
                "direction": "minimize",
            },
            "train/accuracy": {
                "group": "Training",
                "label": "Training Accuracy",
                "direction": "maximize",
            },
            "val/loss": {
                "group": "Validation",
                "label": "Validation Loss",
                "direction": "minimize",
            },
            "val/accuracy": {
                "group": "Validation",
                "label": "Validation Accuracy",
                "direction": "maximize",
            },
        }

    # ── Hyperparameter search ─────────────────────────────────────────

    def get_search_ranges(self) -> dict[str, dict[str, Any]]:
        return {
            "learning_rate": {
                "type": "float",
                "low": 1e-5,
                "high": 1e-1,
                "log": True,
            },
            "batch_size": {
                "type": "categorical",
                "choices": [32, 64, 128, 256],
            },
            "epochs": {
                "type": "int",
                "low": 3,
                "high": 20,
            },
        }

    # ── Inference ─────────────────────────────────────────────────────

    def load_model(self, checkpoint_path: str) -> Any:
        """Load a trained SimpleCNN checkpoint."""
        from adapters.dummy_classifier.model import load_model

        return load_model(checkpoint_path)

    def predict(self, model: Any, image_bytes: bytes, **kwargs: Any) -> dict[str, Any]:
        """Classify an uploaded image.

        Returns:
            {"predictions": [{"class": str, "probability": float}, ...], "top_class": str}
        """
        import io

        import torch
        from PIL import Image
        from torchvision import transforms

        # Determine preprocessing from model architecture
        in_channels = model.features[0].in_channels
        if in_channels == 1:
            transform = transforms.Compose(
                [
                    transforms.Grayscale(num_output_channels=1),
                    transforms.Resize((28, 28)),
                    transforms.ToTensor(),
                    transforms.Normalize((0.1307,), (0.3081,)),
                ]
            )
        else:
            transform = transforms.Compose(
                [
                    transforms.Resize((32, 32)),
                    transforms.ToTensor(),
                    transforms.Normalize((0.4914, 0.4822, 0.4465), (0.2470, 0.2435, 0.2616)),
                ]
            )

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB" if in_channels == 3 else "L")
        tensor = transform(img).unsqueeze(0)

        model.eval()
        with torch.no_grad():
            logits = model(tensor)
            probs = torch.softmax(logits, dim=1)[0]

        # Build top-k predictions
        class_names = kwargs.get("class_names") or [str(i) for i in range(probs.size(0))]
        top_k = min(5, len(class_names))
        top_probs, top_indices = probs.topk(top_k)

        predictions = [
            {"class": class_names[idx.item()], "probability": round(prob.item(), 4)}
            for prob, idx in zip(top_probs, top_indices)
        ]

        return {
            "predictions": predictions,
            "top_class": predictions[0]["class"],
            "confidence": predictions[0]["probability"],
        }
