"""REST API endpoints for cross-modal search demo.

Routes search requests through the adapter registry — no adapter-specific
imports in this module.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from adapters import get_adapter
from adapters.base import BaseAdapter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["search"])

# In-memory cache for loaded indexes and models
_index_cache: dict[str, dict[str, Any]] = {}
_model_cache: dict[str, Any] = {}


def _get_adapter(adapter_name: str) -> BaseAdapter:
    """Get adapter by name, raising 400 on unknown."""
    try:
        return get_adapter(adapter_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


def _get_or_load_index(adapter: BaseAdapter, index_path: str) -> dict[str, Any]:
    """Load index from cache or disk via adapter."""
    if index_path not in _index_cache:
        _index_cache[index_path] = adapter.load_index(index_path)
    return _index_cache[index_path]


def _get_or_load_model(adapter: BaseAdapter, checkpoint_path: str) -> Any:
    """Load model from cache or disk via adapter."""
    if checkpoint_path not in _model_cache:
        _model_cache[checkpoint_path] = adapter.load_model(checkpoint_path)
    return _model_cache[checkpoint_path]


@router.post("/text")
async def search_by_text(
    query: str = Form(...),
    index_path: str = Form(...),
    checkpoint_path: str = Form(...),
    bit_length: int = Form(default=64),
    top_k: int = Form(default=20),
    method: str = Form(default="hamming"),
    adapter_name: str = Form(...),
) -> dict[str, Any]:
    """Text-to-image search: find similar images for a text query.

    Args:
        query: Text query string.
        index_path: Path to the search index .pt file.
        checkpoint_path: Path to the model checkpoint.
        bit_length: Bit length for code comparison.
        top_k: Number of results to return.
        method: Search method ('hamming' or 'cosine').
        adapter_name: Adapter to use for search.

    Returns:
        Search results with thumbnails and scores.
    """
    adapter = _get_adapter(adapter_name)

    try:
        model = _get_or_load_model(adapter, checkpoint_path)
        index_data = _get_or_load_index(adapter, index_path)
    except NotImplementedError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to load: {e}") from e

    try:
        return adapter.search_by_text(
            model=model,
            query=query,
            index_data=index_data,
            bit_length=bit_length,
            top_k=top_k,
            method=method,
        )
    except NotImplementedError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/image")
async def search_by_image(
    image: UploadFile = File(...),
    index_path: str = Form(...),
    checkpoint_path: str = Form(...),
    bit_length: int = Form(default=64),
    top_k: int = Form(default=20),
    method: str = Form(default="hamming"),
    adapter_name: str = Form(...),
) -> dict[str, Any]:
    """Image-to-text search: find similar texts for an image query.

    Args:
        image: Uploaded image file.
        index_path: Path to the search index .pt file.
        checkpoint_path: Path to the model checkpoint.
        bit_length: Bit length for code comparison.
        top_k: Number of results to return.
        method: Search method ('hamming' or 'cosine').
        adapter_name: Adapter to use for search.

    Returns:
        Search results with captions and scores.
    """
    adapter = _get_adapter(adapter_name)

    try:
        model = _get_or_load_model(adapter, checkpoint_path)
        index_data = _get_or_load_index(adapter, index_path)
    except NotImplementedError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to load: {e}") from e

    try:
        image_bytes = await image.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image: {e}") from e

    try:
        return adapter.search_by_image(
            model=model,
            image_bytes=image_bytes,
            index_data=index_data,
            bit_length=bit_length,
            top_k=top_k,
            method=method,
        )
    except NotImplementedError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
