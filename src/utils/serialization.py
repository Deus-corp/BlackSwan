from __future__ import annotations

import json
from typing import Any, Dict


def json_dumps(obj: Any) -> str:
    """Serialize object to compact UTF-8 JSON."""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str)


def json_loads_safe(text: str) -> Dict[str, Any]:
    """Parse JSON object safely, returning empty dict on failure."""
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {}

    return parsed if isinstance(parsed, dict) else {}