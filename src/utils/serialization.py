"""JSON serialization helpers."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any


def json_dumps(obj: Any, *, pretty: bool = False) -> str:
    """Serialize an object to deterministic UTF-8 JSON."""
    return json.dumps(
        _to_jsonable(obj),
        ensure_ascii=False,
        sort_keys=True,
        separators=None if pretty else (",", ":"),
        indent=2 if pretty else None,
        default=str,
    )


def json_loads_safe(text: str | bytes | bytearray, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
    """Parse a JSON object string safely, returning default or {} on failure."""
    fallback = {} if default is None else dict(default)

    if isinstance(text, (bytes, bytearray)):
        text = text.decode("utf-8", errors="replace")

    if not isinstance(text, str) or not text.strip():
        return fallback

    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return fallback

    return parsed if isinstance(parsed, dict) else fallback


def json_loads_list_safe(text: str | bytes | bytearray, *, default: list[Any] | None = None) -> list[Any]:
    """Parse a JSON array string safely, returning default or [] on failure."""
    fallback = [] if default is None else list(default)

    if isinstance(text, (bytes, bytearray)):
        text = text.decode("utf-8", errors="replace")

    if not isinstance(text, str) or not text.strip():
        return fallback

    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return fallback

    return parsed if isinstance(parsed, list) else fallback


def json_dump_file(path: str | Path, obj: Any, *, pretty: bool = True) -> Path:
    """Atomically write JSON to a file."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    tmp_path.write_text(json_dumps(obj, pretty=pretty), encoding="utf-8")
    tmp_path.replace(output_path)
    return output_path


def json_load_file_safe(path: str | Path, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
    """Safely load a JSON object from a file."""
    input_path = Path(path)
    if not input_path.exists() or not input_path.is_file():
        return {} if default is None else dict(default)

    try:
        return json_loads_safe(input_path.read_text(encoding="utf-8"), default=default)
    except OSError:
        return {} if default is None else dict(default)


def _to_jsonable(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)

    if hasattr(obj, "model_dump") and callable(obj.model_dump):
        return obj.model_dump(mode="json")

    if isinstance(obj, dict):
        return {str(key): _to_jsonable(value) for key, value in obj.items()}

    if isinstance(obj, (list, tuple, set, frozenset)):
        return [_to_jsonable(item) for item in obj]

    return obj