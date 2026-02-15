"""Config file parser with type inference and group extraction.

Reads YAML/JSON config files from project directories,
infers value types, and returns a structured representation
suitable for dynamic form generation in the frontend.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def parse_config_file(project_path: str, config_path: str) -> dict[str, Any]:
    """Parse a config file and return structured representation.

    Args:
        project_path: Absolute path to the project root directory.
        config_path: Relative path to the config file within the project.

    Returns:
        Dict with keys: raw_yaml, parsed, groups.
        ``parsed`` maps group names to dicts of {key: {value, type}}.

    Raises:
        FileNotFoundError: If the config file does not exist.
        ValueError: If the file format is unsupported or unparseable.
    """
    full_path = Path(project_path) / config_path

    if not full_path.is_file():
        raise FileNotFoundError(f"Config file not found: {full_path}")

    raw_content = full_path.read_text(encoding="utf-8")

    # Determine format from extension
    suffix = full_path.suffix.lower()
    if suffix in (".yaml", ".yml"):
        nested = _parse_yaml(raw_content)
    elif suffix == ".json":
        nested = _parse_json(raw_content)
    else:
        raise ValueError(f"Unsupported config format: {suffix}")

    # Build parsed structure grouped by top-level keys
    parsed: dict[str, dict[str, dict[str, Any]]] = {}
    groups: list[str] = []

    for top_key, top_value in nested.items():
        if isinstance(top_value, dict):
            # Top-level key becomes a group
            groups.append(top_key)
            parsed[top_key] = {}
            for sub_key, sub_value in top_value.items():
                parsed[top_key][sub_key] = {
                    "value": sub_value,
                    "type": _infer_type(sub_value),
                }
        else:
            # Non-dict top-level values go into a "general" group
            if "general" not in parsed:
                parsed["general"] = {}
                groups.insert(0, "general")
            parsed["general"][top_key] = {
                "value": top_value,
                "type": _infer_type(top_value),
            }

    return {
        "raw_yaml": raw_content,
        "parsed": parsed,
        "groups": groups,
    }


def _parse_yaml(content: str) -> dict[str, Any]:
    """Parse YAML content into a dict."""
    try:
        import yaml

        data = yaml.safe_load(content)
    except ImportError:
        # Fallback: simple line-based parser for basic YAML
        data = _simple_yaml_parse(content)

    if not isinstance(data, dict):
        raise ValueError("Config file must be a YAML mapping at the top level")
    return data


def _parse_json(content: str) -> dict[str, Any]:
    """Parse JSON content into a dict."""
    data = json.loads(content)
    if not isinstance(data, dict):
        raise ValueError("Config file must be a JSON object at the top level")
    return data


def _simple_yaml_parse(content: str) -> dict[str, Any]:
    """Minimal YAML parser fallback (no PyYAML dependency)."""
    result: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, result)]

    for line in content.split("\n"):
        stripped = line.rstrip()
        if not stripped or stripped.lstrip().startswith("#"):
            continue

        indent = len(line) - len(line.lstrip())
        content_part = stripped.strip()

        # Pop stack to find parent at correct indent level
        while len(stack) > 1 and stack[-1][0] >= indent:
            stack.pop()

        colon_idx = content_part.find(":")
        if colon_idx == -1:
            continue

        key = content_part[:colon_idx].strip()
        if key.startswith("-"):
            continue

        raw_value = content_part[colon_idx + 1 :].strip()
        parent = stack[-1][1]

        if raw_value == "" or raw_value == "|" or raw_value == ">":
            child: dict[str, Any] = {}
            parent[key] = child
            stack.append((indent, child))
        else:
            parent[key] = _parse_scalar(raw_value)

    return result


def _parse_scalar(raw: str) -> Any:
    """Parse a YAML scalar value."""
    if raw in ("true", "True", "yes", "on"):
        return True
    if raw in ("false", "False", "no", "off"):
        return False
    if raw in ("null", "~", "None"):
        return None

    # Quoted string
    if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
        return raw[1:-1]

    # Inline list [a, b, c]
    if raw.startswith("[") and raw.endswith("]"):
        items = raw[1:-1].split(",")
        return [_parse_scalar(item.strip()) for item in items if item.strip()]

    # Number
    try:
        if "." in raw or "e" in raw.lower():
            return float(raw)
        return int(raw)
    except ValueError:
        pass

    return raw


def _infer_type(value: Any) -> str:
    """Infer the config value type for frontend form generation."""
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "float"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    if value is None:
        return "string"
    return "string"
