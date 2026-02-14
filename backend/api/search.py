"""REST API endpoints for cross-modal search demo."""

from __future__ import annotations

import io
import logging
import time
from typing import Any

import numpy as np
import torch
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from PIL import Image

from adapters.vlm_quantization.index_builder import load_index
from adapters.vlm_quantization.model import load_model
from adapters.vlm_quantization.search import SearchResult, search_index

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["search"])

# In-memory cache for loaded indexes and models
_index_cache: dict[str, dict[str, Any]] = {}
_model_cache: dict[str, Any] = {}


def _get_or_load_index(index_path: str) -> dict[str, Any]:
    """Load index from cache or disk."""
    if index_path not in _index_cache:
        _index_cache[index_path] = load_index(index_path)
    return _index_cache[index_path]


def _get_or_load_model(checkpoint_path: str) -> Any:
    """Load model from cache or disk."""
    if checkpoint_path not in _model_cache:
        _model_cache[checkpoint_path] = load_model(checkpoint_path)
    return _model_cache[checkpoint_path]


def _results_to_dicts(results: list[SearchResult]) -> list[dict[str, Any]]:
    """Convert SearchResult list to JSON-serializable dicts."""
    return [
        {
            "rank": r.rank,
            "index": r.index,
            "score": r.score,
            "thumbnail_b64": r.thumbnail_b64,
            "caption": r.caption,
        }
        for r in results
    ]


@router.post("/text")
async def search_by_text(
    query: str = Form(...),
    index_path: str = Form(...),
    checkpoint_path: str = Form(...),
    bit_length: int = Form(default=64),
    top_k: int = Form(default=20),
    method: str = Form(default="hamming"),
) -> dict[str, Any]:
    """Text-to-image search: find similar images for a text query.

    Args:
        query: Text query string.
        index_path: Path to the search index .pt file.
        checkpoint_path: Path to the model checkpoint.
        bit_length: Bit length for hash code comparison.
        top_k: Number of results to return.
        method: Search method ('hamming' or 'cosine').

    Returns:
        Search results with thumbnails and scores.
    """
    start_time = time.time()

    try:
        model = _get_or_load_model(checkpoint_path)
        index_data = _get_or_load_index(index_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to load: {e}") from e

    # Tokenize query (simple character-level for dummy model)
    max_len = 128
    token_ids = [ord(c) % 32000 for c in query[:max_len]]
    attention_mask = [1] * len(token_ids) + [0] * (max_len - len(token_ids))
    token_ids = token_ids + [0] * (max_len - len(token_ids))

    input_ids = torch.tensor([token_ids], dtype=torch.long)
    attn_mask = torch.tensor([attention_mask], dtype=torch.long)

    # Encode query
    if method == "cosine":
        query_codes, query_features = model.encode_text(
            input_ids,
            attention_mask=attn_mask,
            bit_length=bit_length,
            return_features=True,
        )
    else:
        query_codes = model.encode_text(
            input_ids,
            attention_mask=attn_mask,
            bit_length=bit_length,
        )
        query_features = None

    # Search against image codes in the index
    # Swap to image codes for text-to-image search
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

    # Query hash visualization
    query_hash = query_codes[0].tolist()

    return {
        "results": _results_to_dicts(results),
        "query_hash": query_hash,
        "search_time_ms": round(elapsed_ms, 2),
        "method": method,
        "bit_length": bit_length,
        "query": query,
    }


@router.post("/image")
async def search_by_image(
    image: UploadFile = File(...),
    index_path: str = Form(...),
    checkpoint_path: str = Form(...),
    bit_length: int = Form(default=64),
    top_k: int = Form(default=20),
    method: str = Form(default="hamming"),
) -> dict[str, Any]:
    """Image-to-text search: find similar texts for an image query.

    Args:
        image: Uploaded image file.
        index_path: Path to the search index .pt file.
        checkpoint_path: Path to the model checkpoint.
        bit_length: Bit length for hash code comparison.
        top_k: Number of results to return.
        method: Search method ('hamming' or 'cosine').

    Returns:
        Search results with captions and scores.
    """
    start_time = time.time()

    try:
        model = _get_or_load_model(checkpoint_path)
        index_data = _get_or_load_index(index_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to load: {e}") from e

    # Read and process uploaded image
    try:
        contents = await image.read()
        img = Image.open(io.BytesIO(contents)).convert("RGB")
        img = img.resize((384, 384))
        arr = np.array(img, dtype=np.float32) / 255.0
        pixel_values = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image: {e}") from e

    # Encode query image
    if method == "cosine":
        query_codes, query_features = model.encode_image(
            pixel_values,
            bit_length=bit_length,
            return_features=True,
        )
    else:
        query_codes = model.encode_image(
            pixel_values,
            bit_length=bit_length,
        )
        query_features = None

    # For image-to-text, we search text codes
    # Override the default key detection
    search_data_for_text = {
        "image_codes": index_data.get("text_codes", {}),  # trick: put text codes in image_codes key
        "image_features": index_data.get("text_features"),
        "thumbnails": [],  # no thumbnails for text results
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
    query_hash = query_codes[0].tolist()

    return {
        "results": _results_to_dicts(results),
        "query_hash": query_hash,
        "search_time_ms": round(elapsed_ms, 2),
        "method": method,
        "bit_length": bit_length,
    }
