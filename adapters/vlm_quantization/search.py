"""Search functions for cross-modal retrieval.

Provides Hamming distance and cosine similarity based search
over pre-built indexes.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch

from adapters.vlm_quantization.evaluator import cosine_similarity_matrix, hamming_distance


@dataclass
class SearchResult:
    """A single search result."""

    rank: int
    index: int
    score: float
    thumbnail_b64: str | None = None
    caption: str | None = None
    item_id: str | None = None


@dataclass
class SearchResponse:
    """Complete search response."""

    results: list[SearchResult]
    query_hash: list[int] | None = None
    search_time_ms: float = 0.0
    method: str = "hamming"
    bit_length: int = 128


def hamming_search(
    query_codes: torch.Tensor,
    db_codes: torch.Tensor,
    top_k: int = 20,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Search by Hamming distance (lower = more similar).

    Args:
        query_codes: (N_q, D) binary codes in {-1, +1}.
        db_codes: (N_db, D) binary codes in {-1, +1}.
        top_k: Number of nearest neighbors to return.

    Returns:
        Tuple of (distances, indices), each (N_q, top_k).
    """
    dist = hamming_distance(query_codes, db_codes)
    top_k = min(top_k, db_codes.shape[0])
    # topk with largest=False gives smallest distances
    values, indices = dist.float().topk(top_k, largest=False)
    return values, indices


def cosine_search(
    query_features: torch.Tensor,
    db_features: torch.Tensor,
    top_k: int = 20,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Search by cosine similarity (higher = more similar).

    Args:
        query_features: (N_q, D) feature vectors.
        db_features: (N_db, D) feature vectors.
        top_k: Number of nearest neighbors to return.

    Returns:
        Tuple of (similarities, indices), each (N_q, top_k).
    """
    sim = cosine_similarity_matrix(query_features, db_features)
    top_k = min(top_k, db_features.shape[0])
    values, indices = sim.topk(top_k, largest=True)
    return values, indices


def search_index(
    query_codes: torch.Tensor,
    index_data: dict,
    bit_length: int = 128,
    top_k: int = 20,
    method: str = "hamming",
    query_features: torch.Tensor | None = None,
) -> list[SearchResult]:
    """Search an index and return formatted results.

    Args:
        query_codes: (1, D) query hash codes in {-1, +1}.
        index_data: Loaded index dict with keys:
            image_codes / text_codes: {bit_length: tensor}
            image_features / text_features: tensor (optional, for cosine)
            thumbnails: list of base64 strings (optional)
            captions: list of strings (optional)
        bit_length: Which bit length to use for search.
        top_k: Number of results to return.
        method: "hamming" or "cosine".
        query_features: (1, D) continuous features (required for cosine).

    Returns:
        List of SearchResult objects.
    """
    # Determine search target (image or text codes)
    db_codes_key = "image_codes" if "image_codes" in index_data else "text_codes"
    db_codes_dict = index_data[db_codes_key]

    if isinstance(db_codes_dict, dict):
        if bit_length not in db_codes_dict:
            available = sorted(db_codes_dict.keys())
            raise ValueError(f"bit_length {bit_length} not in index. Available: {available}")
        db_codes = db_codes_dict[bit_length]
    else:
        db_codes = db_codes_dict

    if method == "hamming":
        scores, indices = hamming_search(query_codes, db_codes, top_k)
        scores = scores[0]  # single query
        indices = indices[0]
    elif method == "cosine":
        db_feat_key = "image_features" if "image_features" in index_data else "text_features"
        db_features = index_data.get(db_feat_key)
        if db_features is None or query_features is None:
            raise ValueError("Cosine search requires features in index and query")
        scores, indices = cosine_search(query_features, db_features, top_k)
        scores = scores[0]
        indices = indices[0]
    else:
        raise ValueError(f"Unknown method: {method}. Use 'hamming' or 'cosine'.")

    thumbnails = index_data.get("thumbnails", [])
    captions = index_data.get("captions", [])

    results: list[SearchResult] = []
    for rank, (idx, score) in enumerate(zip(indices.tolist(), scores.tolist())):
        results.append(
            SearchResult(
                rank=rank + 1,
                index=idx,
                score=score,
                thumbnail_b64=thumbnails[idx] if idx < len(thumbnails) else None,
                caption=captions[idx] if idx < len(captions) else None,
            )
        )

    return results
