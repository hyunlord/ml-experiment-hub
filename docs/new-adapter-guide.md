# Adding a New Adapter

This guide walks through adding a new model type to ML Experiment Hub using the adapter plugin interface. The `dummy_classifier` adapter is used as a concrete example throughout.

## Overview

An adapter teaches the platform how to:

1. **Configure** — convert a config dict to framework-specific YAML
2. **Train** — build the subprocess command that launches training
3. **Parse** — extract metrics from training stdout
4. **Infer** — load a checkpoint and run prediction (optional)
5. **Search** — define hyperparameter search ranges (optional)

The platform never imports your model code directly. Everything flows through the `BaseAdapter` interface.

## Step 1: Create the Adapter Directory

```
adapters/
├── base.py                    # BaseAdapter ABC (don't modify)
├── __init__.py                # Adapter registry (you'll add one line)
└── my_model/                  # Your new adapter
    ├── __init__.py
    ├── adapter.py             # BaseAdapter implementation (required)
    ├── model.py               # Model definition
    └── train.py               # Standalone training script
```

Create the directory:

```bash
mkdir -p adapters/my_model
touch adapters/my_model/__init__.py
```

## Step 2: Define Your Model

Create `adapters/my_model/model.py` with your model class and a `load_model()` function.

**Example** (`adapters/dummy_classifier/model.py`):

```python
import torch
import torch.nn as nn

class SimpleCNN(nn.Module):
    def __init__(self, in_channels: int = 1, num_classes: int = 10) -> None:
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(in_channels, 32, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d(4),
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(64 * 4 * 4, 128),
            nn.ReLU(inplace=True),
            nn.Linear(128, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.classifier(self.features(x))

def load_model(checkpoint_path: str, device: str = "cpu") -> SimpleCNN:
    ckpt = torch.load(checkpoint_path, map_location=device, weights_only=False)
    model = SimpleCNN(
        in_channels=ckpt.get("in_channels", 1),
        num_classes=ckpt.get("num_classes", 10),
    )
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()
    return model
```

**Key rules:**
- Lazy-import heavy dependencies (`torch`, `torchvision`) inside functions, not at module top level. This keeps API startup fast.
- The `load_model` function should return a ready-to-use model from a checkpoint path.

## Step 3: Write the Training Script

Create `adapters/my_model/train.py` — a standalone script the platform runs as a subprocess.

**Requirements:**
- Accept `--config <yaml_path>` as the entry point
- Print JSON metric lines to **stdout** (the platform parses these)
- Each metric line must include a `"step"` key

**Example output format:**

```json
{"step": 50, "epoch": 1, "train/loss": 0.4523, "train/accuracy": 0.8712}
{"step": 100, "epoch": 1, "train/loss": 0.2341, "val/loss": 0.1892, "val/accuracy": 0.9456}
```

**Example** (`adapters/dummy_classifier/train.py` — abbreviated):

```python
import json
import yaml
import torch

def _emit(data: dict) -> None:
    """Print a JSON metric line to stdout."""
    print(json.dumps(data), flush=True)

def main(config_path: str) -> None:
    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    # ... setup model, data, optimizer ...

    for epoch in range(1, epochs + 1):
        for batch_idx, (images, labels) in enumerate(train_loader):
            # ... training step ...
            global_step += 1

            if global_step % 50 == 0:
                _emit({
                    "step": global_step,
                    "epoch": epoch,
                    "train/loss": round(loss.item(), 4),
                    "train/accuracy": round(correct / total, 4),
                })

        # Emit epoch summary with validation metrics
        _emit({
            "step": global_step,
            "epoch": epoch,
            "train/loss": round(train_loss, 4),
            "val/loss": round(val_loss, 4),
            "val/accuracy": round(val_acc, 4),
        })

        # Save checkpoint
        torch.save({
            "model_state_dict": model.state_dict(),
            "epoch": epoch,
            "in_channels": in_channels,
            "num_classes": num_classes,
            "config": cfg,
        }, checkpoint_path)
```

## Step 4: Implement the Adapter

Create `adapters/my_model/adapter.py` implementing `BaseAdapter`.

### Required Methods

| Method | Purpose |
|--------|---------|
| `config_to_yaml(config)` | Convert config dict to YAML string |
| `get_train_command(yaml_path)` | Return subprocess command as `list[str]` |
| `parse_metrics(log_line)` | Parse stdout line into metric dict (or `None`) |

### Optional Methods

| Method | Purpose |
|--------|---------|
| `get_name()` | Human-readable name for the UI |
| `get_metrics_mapping()` | Metric display metadata (groups, labels, direction) |
| `get_search_ranges()` | Hyperparameter search space for Optuna |
| `load_model(checkpoint_path)` | Load checkpoint for inference |
| `predict(model, image_bytes, **kwargs)` | Run single-input prediction |
| `load_index(index_path)` | Load search index (retrieval models) |
| `search_by_text(...)` | Text-based search (retrieval models) |
| `search_by_image(...)` | Image-based search (retrieval models) |

**Example** (`adapters/dummy_classifier/adapter.py` — key parts):

```python
import json
import re
import yaml
from adapters.base import BaseAdapter

class DummyClassifierAdapter(BaseAdapter):

    def config_to_yaml(self, config: dict) -> str:
        return yaml.dump(config, default_flow_style=False)

    def get_train_command(self, yaml_path: str) -> list[str]:
        return ["python", "-m", "adapters.dummy_classifier.train",
                "--config", yaml_path]

    def parse_metrics(self, log_line: str) -> dict | None:
        if "{" in log_line:
            try:
                data = json.loads(log_line.strip())
                if isinstance(data, dict) and "step" in data:
                    return data
            except json.JSONDecodeError:
                pass
        return None

    def get_name(self) -> str:
        return "Image Classifier (MNIST / CIFAR-10)"

    def get_metrics_mapping(self) -> dict:
        return {
            "train/loss":     {"group": "Training",   "label": "Training Loss",      "direction": "minimize"},
            "train/accuracy": {"group": "Training",   "label": "Training Accuracy",  "direction": "maximize"},
            "val/loss":       {"group": "Validation", "label": "Validation Loss",    "direction": "minimize"},
            "val/accuracy":   {"group": "Validation", "label": "Validation Accuracy", "direction": "maximize"},
        }

    def get_search_ranges(self) -> dict:
        return {
            "learning_rate": {"type": "float", "low": 1e-5, "high": 1e-1, "log": True},
            "batch_size":    {"type": "categorical", "choices": [32, 64, 128, 256]},
            "epochs":        {"type": "int", "low": 3, "high": 20},
        }

    def load_model(self, checkpoint_path: str):
        from adapters.dummy_classifier.model import load_model
        return load_model(checkpoint_path)

    def predict(self, model, image_bytes: bytes, **kwargs) -> dict:
        # ... preprocessing, inference, return predictions ...
        return {"predictions": [...], "top_class": "7", "confidence": 0.98}
```

## Step 5: Register the Adapter

Edit `adapters/__init__.py` — add two lines:

```python
from adapters.my_model.adapter import MyModelAdapter  # add import

ADAPTER_REGISTRY: dict[str, type[BaseAdapter]] = {
    "pytorch_lightning": PyTorchLightningAdapter,
    "huggingface": HuggingFaceAdapter,
    "vlm_quantization": VLMQuantizationAdapter,
    "dummy_classifier": DummyClassifierAdapter,
    "my_model": MyModelAdapter,  # add entry
}
```

The registry key (`"my_model"`) is what users select in the UI when creating experiments.

## Step 6: Add Dependencies (if needed)

If your adapter requires additional packages, add them to `pyproject.toml`:

```toml
[project]
dependencies = [
    # ... existing deps ...
    "my-framework>=1.0.0",
]
```

Then run `uv sync --all-extras`.

## Step 7: Test Your Adapter

Add tests in `tests/test_my_model.py`:

```python
from adapters import get_adapter, ADAPTER_REGISTRY

def test_registered():
    assert "my_model" in ADAPTER_REGISTRY

def test_get_adapter():
    adapter = get_adapter("my_model")
    assert adapter.get_name()

def test_config_to_yaml():
    adapter = get_adapter("my_model")
    yaml_str = adapter.config_to_yaml({"lr": 0.001, "epochs": 5})
    assert "lr" in yaml_str

def test_parse_metrics():
    adapter = get_adapter("my_model")
    result = adapter.parse_metrics('{"step": 1, "loss": 0.5}')
    assert result is not None
    assert result["step"] == 1

def test_train_command():
    adapter = get_adapter("my_model")
    cmd = adapter.get_train_command("/tmp/config.yaml")
    assert "/tmp/config.yaml" in cmd
```

Run tests:

```bash
uv run pytest tests/test_my_model.py -v
```

## Step 8: Verify with Gate

Run the full gate check to make sure nothing is broken:

```bash
./scripts/gate.sh
```

## Using Your Adapter

Once registered, your adapter is available everywhere in the platform:

1. **Training**: Select `my_model` as the framework when creating an experiment
2. **Dashboard**: Live metrics appear on the run monitor page (parsed by `parse_metrics`)
3. **Comparison**: Side-by-side metric charts work automatically
4. **Hyperparameter Search**: If `get_search_ranges()` is implemented, the search UI pre-fills ranges
5. **Inference Demo**: If `predict()` is implemented, the Classifier Demo page can use your model
6. **Search Demo**: If search methods are implemented, the Search Demo page can use your model

## Genericity Rules

The platform enforces strict genericity. Your adapter code lives in `adapters/my_model/` and must not leak into core platform code:

- `backend/api/`, `backend/core/`, `shared/schemas.py` must never import or reference your adapter directly
- All routing goes through `get_adapter(name)` from the registry
- The gate script checks for forbidden adapter-specific terms in core code

## Reference

- `adapters/base.py` — full `BaseAdapter` interface with docstrings
- `adapters/dummy_classifier/` — complete working example (classification)
- `adapters/vlm_quantization/` — complete working example (cross-modal retrieval)
- `adapters/pytorch_lightning.py` — skeleton for PyTorch Lightning
- `adapters/huggingface.py` — skeleton for HuggingFace Trainer
