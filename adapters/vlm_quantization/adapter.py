"""Platform adapter for VLM Quantization framework.

Integrates the cross-modal hashing model with the ML Experiment Hub
training/evaluation pipeline.
"""

from __future__ import annotations

import io
import json
import re
import time
from typing import Any

import numpy as np
import torch
import yaml
from PIL import Image

from adapters.base import BaseAdapter


class VLMQuantizationAdapter(BaseAdapter):
    """Adapter for VLM Quantization (cross-modal hashing) experiments.

    Handles:
    - Config YAML generation for vlm_quantization training
    - Training command construction
    - Metric log parsing from training output
    """

    def config_to_yaml(self, config: dict[str, Any]) -> str:
        """Convert nested config to YAML for vlm_quantization."""
        return yaml.dump(config, default_flow_style=False, allow_unicode=True)

    def get_train_command(self, yaml_path: str) -> list[str]:
        """Build the vlm_quantization training command."""
        return ["python", "-m", "src.train", "--config", yaml_path]

    def parse_metrics(self, log_line: str) -> dict[str, Any] | None:
        """Parse metrics from vlm_quantization training output.

        Expected formats:
        - JSON: {"step": 100, "train/loss": 0.5, "val/map_64": 0.8}
        - Key=value: step=100 train/loss=0.5 val/map_64=0.8
        """
        # Try JSON format first
        if "{" in log_line:
            try:
                data = json.loads(log_line.strip())
                if isinstance(data, dict) and "step" in data:
                    return data
            except json.JSONDecodeError:
                pass

        # Try key=value format
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
        return "VLM Quantization (Cross-Modal Hashing)"

    def get_metrics_mapping(self) -> dict[str, dict[str, str]]:
        """Return metric display metadata for cross-modal hashing."""
        return {
            "train/loss": {
                "group": "Training",
                "label": "Training Loss",
                "direction": "minimize",
            },
            "train/quant_loss": {
                "group": "Training",
                "label": "Quantization Loss",
                "direction": "minimize",
            },
            "val/loss": {
                "group": "Validation",
                "label": "Validation Loss",
                "direction": "minimize",
            },
            "val/map_8": {
                "group": "Retrieval (mAP)",
                "label": "mAP@8bit",
                "direction": "maximize",
            },
            "val/map_16": {
                "group": "Retrieval (mAP)",
                "label": "mAP@16bit",
                "direction": "maximize",
            },
            "val/map_32": {
                "group": "Retrieval (mAP)",
                "label": "mAP@32bit",
                "direction": "maximize",
            },
            "val/map_64": {
                "group": "Retrieval (mAP)",
                "label": "mAP@64bit",
                "direction": "maximize",
            },
            "val/map_128": {
                "group": "Retrieval (mAP)",
                "label": "mAP@128bit",
                "direction": "maximize",
            },
        }

    def inject_monitor_config(
        self,
        config: dict[str, Any],
        run_id: int,
        server_url: str,
    ) -> dict[str, Any]:
        """Inject MonitorCallback config into the training config."""
        if "callbacks" not in config:
            config["callbacks"] = {}
        config["callbacks"]["monitor"] = {
            "run_id": run_id,
            "server_url": server_url,
        }
        return config

    # ------------------------------------------------------------------
    # Search / Index capabilities
    # ------------------------------------------------------------------

    def load_model(self, checkpoint_path: str) -> Any:
        """Load cross-modal hashing model for inference."""
        from adapters.vlm_quantization.model import load_model

        return load_model(checkpoint_path)

    def load_index(self, index_path: str) -> dict[str, Any]:
        """Load pre-built search index."""
        from adapters.vlm_quantization.index_builder import load_index

        return load_index(index_path)

    def search_by_text(
        self,
        model: Any,
        query: str,
        index_data: dict[str, Any],
        bit_length: int = 64,
        top_k: int = 20,
        method: str = "hamming",
    ) -> dict[str, Any]:
        """Text-to-image search using learned hash codes."""
        from adapters.vlm_quantization.search import search_index

        start_time = time.time()

        # Tokenize query (character-level for dummy model)
        max_len = 128
        token_ids = [ord(c) % 32000 for c in query[:max_len]]
        attention_mask = [1] * len(token_ids) + [0] * (max_len - len(token_ids))
        token_ids = token_ids + [0] * (max_len - len(token_ids))

        input_ids = torch.tensor([token_ids], dtype=torch.long)
        attn_mask = torch.tensor([attention_mask], dtype=torch.long)

        if method == "cosine":
            query_codes, query_features = model.encode_text(
                input_ids, attention_mask=attn_mask, bit_length=bit_length, return_features=True
            )
        else:
            query_codes = model.encode_text(
                input_ids, attention_mask=attn_mask, bit_length=bit_length
            )
            query_features = None

        search_data = {**index_data, "image_codes": index_data.get("image_codes", {})}
        results = search_index(
            query_codes=query_codes,
            index_data=search_data,
            bit_length=bit_length,
            top_k=top_k,
            method=method,
            query_features=query_features,
        )

        elapsed_ms = (time.time() - start_time) * 1000
        return {
            "results": [r.__dict__ for r in results],
            "query_hash": query_codes[0].tolist(),
            "search_time_ms": round(elapsed_ms, 2),
            "method": method,
            "bit_length": bit_length,
            "query": query,
        }

    def search_by_image(
        self,
        model: Any,
        image_bytes: bytes,
        index_data: dict[str, Any],
        bit_length: int = 64,
        top_k: int = 20,
        method: str = "hamming",
    ) -> dict[str, Any]:
        """Image-to-text search using learned hash codes."""
        from adapters.vlm_quantization.search import search_index

        start_time = time.time()

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img = img.resize((384, 384))
        arr = np.array(img, dtype=np.float32) / 255.0
        pixel_values = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0)

        if method == "cosine":
            query_codes, query_features = model.encode_image(
                pixel_values, bit_length=bit_length, return_features=True
            )
        else:
            query_codes = model.encode_image(pixel_values, bit_length=bit_length)
            query_features = None

        search_data_for_text = {
            "image_codes": index_data.get("text_codes", {}),
            "image_features": index_data.get("text_features"),
            "thumbnails": [],
            "captions": index_data.get("captions", []),
        }

        results = search_index(
            query_codes=query_codes,
            index_data=search_data_for_text,
            bit_length=bit_length,
            top_k=top_k,
            method=method,
            query_features=query_features,
        )

        elapsed_ms = (time.time() - start_time) * 1000
        return {
            "results": [r.__dict__ for r in results],
            "query_hash": query_codes[0].tolist(),
            "search_time_ms": round(elapsed_ms, 2),
            "method": method,
            "bit_length": bit_length,
        }
