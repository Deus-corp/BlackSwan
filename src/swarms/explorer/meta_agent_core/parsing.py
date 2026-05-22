from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

from .types import ClassificationItem
from .utils import strip_tags


def extract_json_object(text: str) -> Dict[str, Any]:
    cleaned = strip_tags(text).strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        pass

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(cleaned[start : end + 1])
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def normalize_classification_item(raw: Dict[str, Any]) -> Optional[ClassificationItem]:
    source_gid = str(raw.get("source_gid", "")).strip()
    classification = str(raw.get("classification", "")).upper().strip()
    if not source_gid or classification not in {"USEFUL", "HARMFUL", "NEUTRAL"}:
        return None

    try:
        confidence = float(raw.get("confidence", 0.5))
    except Exception:
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))

    reason = str(raw.get("reason", "") or "")[:500]
    return {
        "source_gid": source_gid,
        "url": raw.get("url") if isinstance(raw.get("url"), str) else None,
        "classification": classification,
        "confidence": confidence,
        "reason": reason,
    }
