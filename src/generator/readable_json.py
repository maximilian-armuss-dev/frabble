from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence

Scalar = str | int | float | bool | None


def dumps_readable_json(data: object, *, indent: int = 2) -> str:
    return _format_value(data, level=0, indent=indent) + "\n"


def _format_value(data: object, *, level: int, indent: int) -> str:
    if isinstance(data, Mapping):
        return _format_mapping(data, level=level, indent=indent)
    if _is_sequence(data):
        return _format_sequence(data, level=level, indent=indent)
    return _format_scalar(data)


def _format_mapping(data: Mapping[object, object], *, level: int, indent: int) -> str:
    if not data:
        return "{}"
    current = " " * (level * indent)
    child = " " * ((level + 1) * indent)
    lines = ["{"]
    items = list(data.items())
    for index, (key, value) in enumerate(items):
        suffix = "," if index < len(items) - 1 else ""
        rendered_key = json.dumps(str(key), ensure_ascii=False)
        rendered_value = _format_value(value, level=level + 1, indent=indent)
        lines.append(f"{child}{rendered_key}: {rendered_value}{suffix}")
    lines.append(f"{current}}}")
    return "\n".join(lines)


def _format_sequence(data: Sequence[object], *, level: int, indent: int) -> str:
    if not data:
        return "[]"
    if _can_inline(data):
        return "[" + ", ".join(_format_inline_value(value) for value in data) + "]"

    current = " " * (level * indent)
    child = " " * ((level + 1) * indent)
    lines = ["["]
    for index, value in enumerate(data):
        suffix = "," if index < len(data) - 1 else ""
        rendered_value = _format_value(value, level=level + 1, indent=indent)
        lines.append(f"{child}{rendered_value}{suffix}")
    lines.append(f"{current}]")
    return "\n".join(lines)


def _can_inline(data: Sequence[object]) -> bool:
    if len(data) > 12:
        return False
    return all(_can_inline_value(value, depth=0) for value in data)


def _can_inline_value(value: object, *, depth: int) -> bool:
    if _is_scalar(value):
        return True
    if depth >= 1 or not _is_sequence(value):
        return False
    return len(value) <= 12 and all(
        _is_scalar(child) for child in value
    )


def _format_inline_value(value: object) -> str:
    if _is_sequence(value):
        return "[" + ", ".join(_format_scalar(child) for child in value) + "]"
    return _format_scalar(value)


def _format_scalar(value: object) -> str:
    if not _is_scalar(value):
        raise TypeError(f"Cannot format non-JSON scalar: {type(value).__name__}")
    if isinstance(value, float):
        return _format_float(value)
    return json.dumps(value, ensure_ascii=False)


def _format_float(value: float) -> str:
    if not math.isfinite(value):
        raise ValueError("JSON output does not support non-finite floats.")
    truncated = math.trunc(value * 10_000) / 10_000
    rendered = f"{truncated:.4f}".rstrip("0").rstrip(".")
    if rendered == "-0":
        return "0"
    return rendered


def _is_sequence(value: object) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray)


def _is_scalar(value: object) -> bool:
    return value is None or isinstance(value, str | int | float | bool)
