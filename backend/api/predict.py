"""Generic prediction API — routes through adapter registry.

Provides a single POST /api/predict/image endpoint that delegates
to the adapter's predict() method. Adapter-agnostic: any adapter
that implements predict() can be used.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from adapters import get_adapter
from adapters.base import BaseAdapter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/predict", tags=["predict"])


def _get_adapter(adapter_name: str) -> BaseAdapter:
    """Resolve adapter by name, returning 404 on unknown."""
    try:
        return get_adapter(adapter_name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# In-memory model cache (adapter_name:checkpoint_path → model)
_model_cache: dict[str, Any] = {}


@router.post("/image")
async def predict_image(
    file: UploadFile = File(...),
    adapter_name: str = Form("dummy_classifier"),
    checkpoint_path: str = Form(...),
    class_names: str = Form(""),
) -> dict[str, Any]:
    """Classify an uploaded image using the specified adapter.

    Args:
        file: Image file to classify.
        adapter_name: Adapter to use (must implement predict()).
        checkpoint_path: Path to model checkpoint.
        class_names: Comma-separated class names (optional).

    Returns:
        Adapter-specific prediction result dict.
    """
    adapter = _get_adapter(adapter_name)

    # Load model (cached)
    cache_key = f"{adapter_name}:{checkpoint_path}"
    if cache_key not in _model_cache:
        try:
            _model_cache[cache_key] = adapter.load_model(checkpoint_path)
        except NotImplementedError:
            raise HTTPException(
                status_code=400,
                detail=f"Adapter '{adapter_name}' does not support model loading",
            )
        except Exception as exc:
            logger.exception("Failed to load model: %s", checkpoint_path)
            raise HTTPException(status_code=500, detail=f"Model load error: {exc}") from exc

    model = _model_cache[cache_key]
    image_bytes = await file.read()

    # Parse class names if provided
    kwargs: dict[str, Any] = {}
    if class_names:
        kwargs["class_names"] = [n.strip() for n in class_names.split(",")]

    try:
        result = adapter.predict(model, image_bytes, **kwargs)
    except NotImplementedError:
        raise HTTPException(
            status_code=400,
            detail=f"Adapter '{adapter_name}' does not support prediction",
        )
    except Exception as exc:
        logger.exception("Prediction failed")
        raise HTTPException(status_code=500, detail=f"Prediction error: {exc}") from exc

    return result
