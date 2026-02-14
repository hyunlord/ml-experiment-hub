"""Utility functions for ML Experiment Hub."""

from typing import Any


def flatten_dict(nested: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """Convert a nested dict to flat dot-notation keys.

    Example:
        {"model": {"backbone": "resnet50", "freeze": True}, "training": {"lr": 0.01}}
        → {"model.backbone": "resnet50", "model.freeze": True, "training.lr": 0.01}
    """
    flat: dict[str, Any] = {}
    for key, value in nested.items():
        full_key = f"{prefix}{key}" if not prefix else f"{prefix}.{key}"
        if isinstance(value, dict):
            flat.update(flatten_dict(value, full_key))
        else:
            flat[full_key] = value
    return flat


def unflatten_dict(flat: dict[str, Any]) -> dict[str, Any]:
    """Convert flat dot-notation keys to a nested dict.

    Example:
        {"model.backbone": "resnet50", "model.freeze": True, "training.lr": 0.01}
        → {"model": {"backbone": "resnet50", "freeze": True}, "training": {"lr": 0.01}}
    """
    nested: dict[str, Any] = {}
    for key, value in flat.items():
        parts = key.split(".")
        current = nested
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value
    return nested


def diff_configs(base: dict[str, Any], other: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Compare two flat config dicts and return differences.

    Returns:
        {
            "added": {key: value} — keys in base but not in other,
            "removed": {key: value} — keys in other but not in base,
            "changed": {key: {"from": old, "to": new}} — keys with different values,
        }
    """
    base_keys = set(base.keys())
    other_keys = set(other.keys())

    added = {k: base[k] for k in sorted(base_keys - other_keys)}
    removed = {k: other[k] for k in sorted(other_keys - base_keys)}
    changed = {}
    for k in sorted(base_keys & other_keys):
        if base[k] != other[k]:
            changed[k] = {"from": other[k], "to": base[k]}

    return {"added": added, "removed": removed, "changed": changed}
