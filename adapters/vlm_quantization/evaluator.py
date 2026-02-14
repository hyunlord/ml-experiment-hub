"""Evaluation metrics for cross-modal hashing retrieval.

Re-implements mAP, P@K, and related metrics from vlm_quantization.
All functions work on PyTorch tensors with {-1, +1} binary codes.
"""

from __future__ import annotations

import torch


def hamming_distance(a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
    """Compute pairwise Hamming distance between two code sets.

    For codes in {-1, +1}, Hamming distance = (D - a @ b.T) / 2
    where D is the code dimensionality.

    Args:
        a: Binary codes (N, D) with values in {-1, +1}.
        b: Binary codes (M, D) with values in {-1, +1}.

    Returns:
        Distance matrix (N, M) with integer Hamming distances.
    """
    d = a.shape[1]
    dot = a @ b.t()
    return ((d - dot) / 2).long()


def to_binary_01(codes: torch.Tensor) -> torch.Tensor:
    """Convert {-1, +1} codes to {0, 1} codes.

    Args:
        codes: Tensor with values in {-1, +1}.

    Returns:
        Tensor with values in {0, 1} (uint8).
    """
    return (codes > 0).to(torch.uint8)


def mean_average_precision(
    query_codes: torch.Tensor,
    db_codes: torch.Tensor,
    query_labels: torch.Tensor,
    db_labels: torch.Tensor,
    top_k: int | None = None,
) -> float:
    """Compute Mean Average Precision using Hamming distance ranking.

    Args:
        query_codes: (N_q, D) binary codes in {-1, +1}.
        db_codes: (N_db, D) binary codes in {-1, +1}.
        query_labels: (N_q,) integer class labels.
        db_labels: (N_db,) integer class labels.
        top_k: If set, only consider top-K retrieved items.

    Returns:
        mAP score in [0, 1].
    """
    dist = hamming_distance(query_codes, db_codes)
    n_query = query_codes.shape[0]

    ap_sum = 0.0
    for i in range(n_query):
        # Sort by Hamming distance (ascending)
        sorted_indices = dist[i].argsort()
        if top_k is not None:
            sorted_indices = sorted_indices[:top_k]

        # Relevance: same label = relevant
        relevant = (db_labels[sorted_indices] == query_labels[i]).float()
        n_relevant = relevant.sum().item()

        if n_relevant == 0:
            continue

        # Compute precision at each relevant position
        cumsum = relevant.cumsum(dim=0)
        positions = torch.arange(1, len(relevant) + 1, device=relevant.device).float()
        precision_at_positions = cumsum / positions
        ap = (precision_at_positions * relevant).sum().item() / n_relevant
        ap_sum += ap

    return ap_sum / max(n_query, 1)


def precision_at_k(
    query_codes: torch.Tensor,
    db_codes: torch.Tensor,
    query_labels: torch.Tensor,
    db_labels: torch.Tensor,
    k: int = 10,
) -> float:
    """Compute Precision@K using Hamming distance ranking.

    Args:
        query_codes: (N_q, D) binary codes in {-1, +1}.
        db_codes: (N_db, D) binary codes in {-1, +1}.
        query_labels: (N_q,) integer class labels.
        db_labels: (N_db,) integer class labels.
        k: Number of top results to consider.

    Returns:
        P@K score in [0, 1].
    """
    dist = hamming_distance(query_codes, db_codes)
    n_query = query_codes.shape[0]

    total_precision = 0.0
    for i in range(n_query):
        sorted_indices = dist[i].argsort()[:k]
        relevant = (db_labels[sorted_indices] == query_labels[i]).float()
        total_precision += relevant.mean().item()

    return total_precision / max(n_query, 1)


def cosine_similarity_matrix(a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
    """Compute pairwise cosine similarity.

    Args:
        a: (N, D) feature vectors.
        b: (M, D) feature vectors.

    Returns:
        Similarity matrix (N, M) with values in [-1, 1].
    """
    a_norm = torch.nn.functional.normalize(a, p=2, dim=-1)
    b_norm = torch.nn.functional.normalize(b, p=2, dim=-1)
    return a_norm @ b_norm.t()


def cosine_mean_average_precision(
    query_features: torch.Tensor,
    db_features: torch.Tensor,
    query_labels: torch.Tensor,
    db_labels: torch.Tensor,
    top_k: int | None = None,
) -> float:
    """Compute mAP using cosine similarity ranking.

    Args:
        query_features: (N_q, D) continuous feature vectors.
        db_features: (N_db, D) continuous feature vectors.
        query_labels: (N_q,) integer class labels.
        db_labels: (N_db,) integer class labels.
        top_k: If set, only consider top-K retrieved items.

    Returns:
        mAP score in [0, 1].
    """
    sim = cosine_similarity_matrix(query_features, db_features)
    n_query = query_features.shape[0]

    ap_sum = 0.0
    for i in range(n_query):
        # Sort by similarity (descending)
        sorted_indices = sim[i].argsort(descending=True)
        if top_k is not None:
            sorted_indices = sorted_indices[:top_k]

        relevant = (db_labels[sorted_indices] == query_labels[i]).float()
        n_relevant = relevant.sum().item()

        if n_relevant == 0:
            continue

        cumsum = relevant.cumsum(dim=0)
        positions = torch.arange(1, len(relevant) + 1, device=relevant.device).float()
        precision_at_positions = cumsum / positions
        ap = (precision_at_positions * relevant).sum().item() / n_relevant
        ap_sum += ap

    return ap_sum / max(n_query, 1)


def cosine_precision_at_k(
    query_features: torch.Tensor,
    db_features: torch.Tensor,
    query_labels: torch.Tensor,
    db_labels: torch.Tensor,
    k: int = 10,
) -> float:
    """Compute P@K using cosine similarity ranking.

    Args:
        query_features: (N_q, D) continuous feature vectors.
        db_features: (N_db, D) continuous feature vectors.
        query_labels: (N_q,) integer class labels.
        db_labels: (N_db,) integer class labels.
        k: Number of top results to consider.

    Returns:
        P@K score in [0, 1].
    """
    sim = cosine_similarity_matrix(query_features, db_features)
    n_query = query_features.shape[0]

    total_precision = 0.0
    for i in range(n_query):
        sorted_indices = sim[i].argsort(descending=True)[:k]
        relevant = (db_labels[sorted_indices] == query_labels[i]).float()
        total_precision += relevant.mean().item()

    return total_precision / max(n_query, 1)


def evaluate_retrieval(
    query_codes: torch.Tensor,
    db_codes: torch.Tensor,
    query_labels: torch.Tensor,
    db_labels: torch.Tensor,
    query_features: torch.Tensor | None = None,
    db_features: torch.Tensor | None = None,
    bit_lengths: list[int] | None = None,
    k_values: list[int] | None = None,
) -> dict[str, dict[str, float]]:
    """Run full evaluation across bit lengths and metrics.

    Args:
        query_codes: Dict or tensor of query hash codes.
        db_codes: Dict or tensor of database hash codes.
        query_labels: Query class labels.
        db_labels: Database class labels.
        query_features: Optional continuous features for cosine eval.
        db_features: Optional continuous features for cosine eval.
        bit_lengths: Specific bit lengths to evaluate.
        k_values: K values for P@K (default: [1, 5, 10]).

    Returns:
        Nested dict: {bit_length: {metric_name: value}}.
    """
    if k_values is None:
        k_values = [1, 5, 10]

    # If codes are a dict (multi-bit), evaluate each bit length
    if isinstance(query_codes, dict):
        if bit_lengths is None:
            bit_lengths = sorted(query_codes.keys())

        results: dict[str, dict[str, float]] = {}
        for bit in bit_lengths:
            qc = query_codes[bit]
            dc = db_codes[bit]
            bit_results: dict[str, float] = {
                "hamming_mAP": mean_average_precision(qc, dc, query_labels, db_labels),
            }
            for k in k_values:
                bit_results[f"hamming_P@{k}"] = precision_at_k(qc, dc, query_labels, db_labels, k=k)

            # Cosine eval if features available
            if query_features is not None and db_features is not None:
                bit_results["cosine_mAP"] = cosine_mean_average_precision(
                    query_features, db_features, query_labels, db_labels
                )
                for k in k_values:
                    bit_results[f"cosine_P@{k}"] = cosine_precision_at_k(
                        query_features, db_features, query_labels, db_labels, k=k
                    )

            results[str(bit)] = bit_results

        return results

    # Single bit length
    bit_label = str(query_codes.shape[1])
    bit_results = {
        "hamming_mAP": mean_average_precision(query_codes, db_codes, query_labels, db_labels),
    }
    for k in k_values:
        bit_results[f"hamming_P@{k}"] = precision_at_k(
            query_codes, db_codes, query_labels, db_labels, k=k
        )

    if query_features is not None and db_features is not None:
        bit_results["cosine_mAP"] = cosine_mean_average_precision(
            query_features, db_features, query_labels, db_labels
        )
        for k in k_values:
            bit_results[f"cosine_P@{k}"] = cosine_precision_at_k(
                query_features, db_features, query_labels, db_labels, k=k
            )

    return {bit_label: bit_results}
