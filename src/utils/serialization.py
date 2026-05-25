from __future__ import annotations

import json
from typing import Any, Dict


def json_dumps(obj: Any) -> str:
    """
    Serialize an object to a compact, sorted UTF-8 JSON string.

    Args:
        obj: The object to serialize. Non-serializable types will be
            converted to strings via the default handler.

    Returns:
        A string representation of the JSON object.
    """
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str)


def json_loads_safe(text: str) -> Dict[str, Any]:
    """
    Parse a JSON string safely into a dictionary.

    Args:
        text: The JSON-formatted string to parse.

    Returns:
        The parsed dictionary if successful and valid, otherwise an empty dict.
    """
    try:
        parsed: Any = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {}

    if isinstance(parsed, dict):
        return parsed
    return {}