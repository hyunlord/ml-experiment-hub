"""Largest Triangle Three Buckets (LTTB) downsampling algorithm.

Reduces the number of data points while preserving the visual shape of the data.
Reference: Sveinn Steinarsson, "Downsampling Time Series for Visual Representation"
"""

from typing import Any


def downsample_lttb(
    data: list[dict[str, Any]],
    threshold: int,
    x_key: str = "step",
    y_key: str | None = None,
) -> list[dict[str, Any]]:
    """Downsample data points using the LTTB algorithm.

    Args:
        data: List of data point dicts, sorted by x_key.
        threshold: Target number of output points. If len(data) <= threshold,
            returns data unchanged.
        x_key: Key for the x-axis value (default: "step").
        y_key: Key for the y-axis value. If None, uses the first numeric
            value in the dict that isn't x_key.

    Returns:
        Downsampled list of data point dicts.
    """
    data_length = len(data)
    if threshold >= data_length or threshold < 3:
        return data

    # Determine y_key if not provided
    if y_key is None:
        for key, val in data[0].items():
            if key != x_key and isinstance(val, (int, float)):
                y_key = key
                break
        if y_key is None:
            return data

    sampled: list[dict[str, Any]] = []

    # Always include first point
    sampled.append(data[0])

    # Bucket size (excluding first and last points)
    bucket_size = (data_length - 2) / (threshold - 2)

    a = 0  # Index of previously selected point

    for i in range(1, threshold - 1):
        # Calculate bucket range
        bucket_start = int((i - 1) * bucket_size) + 1
        bucket_end = int(i * bucket_size) + 1
        bucket_end = min(bucket_end, data_length - 1)

        # Calculate average point of next bucket (for triangle area)
        next_bucket_start = int(i * bucket_size) + 1
        next_bucket_end = int((i + 1) * bucket_size) + 1
        next_bucket_end = min(next_bucket_end, data_length)

        avg_x = 0.0
        avg_y = 0.0
        next_count = next_bucket_end - next_bucket_start
        if next_count > 0:
            for j in range(next_bucket_start, next_bucket_end):
                avg_x += _get_numeric(data[j], x_key)
                avg_y += _get_numeric(data[j], y_key)
            avg_x /= next_count
            avg_y /= next_count

        # Find point in current bucket that forms largest triangle
        max_area = -1.0
        max_idx = bucket_start

        point_a_x = _get_numeric(data[a], x_key)
        point_a_y = _get_numeric(data[a], y_key)

        for j in range(bucket_start, bucket_end):
            # Triangle area using cross product
            area = abs(
                (point_a_x - avg_x) * (_get_numeric(data[j], y_key) - point_a_y)
                - (point_a_x - _get_numeric(data[j], x_key)) * (avg_y - point_a_y)
            )
            if area > max_area:
                max_area = area
                max_idx = j

        sampled.append(data[max_idx])
        a = max_idx

    # Always include last point
    sampled.append(data[-1])

    return sampled


def _get_numeric(d: dict[str, Any], key: str) -> float:
    """Extract a numeric value from a dict, defaulting to 0.0."""
    val = d.get(key, 0)
    return float(val) if isinstance(val, (int, float)) else 0.0
