"""Safe parsing of LLM output for security decisions."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict

logger = logging.getLogger(__name__)


def parse_json_loose(text: str) -> Dict[str, Any]:
    if not isinstance(text, str):
        return {}

    cleaned = text.strip()
    if not cleaned:
        return {}

    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE | re.MULTILINE)

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}

    candidate = cleaned[start : end + 1]

    try:
        parsed = json.loads(candidate)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        repaired = re.sub(
            r'([{,]\s*)(?<!")([A-Za-z_][A-Za-z0-9_]*)(?=\s*:)',
            r'\1"\2"',
            candidate,
        )
        try:
            parsed = json.loads(repaired)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            logger.debug("Failed to parse LLM output as JSON.")
            return {}