from __future__ import annotations

import json
import re
from typing import Any, Dict, Sequence, Optional

from src.swarms.improver.models import FileItem, ImprovementResult, MemoryHit

PYTHON_CONTENT_LIMIT = 32_000
NON_PYTHON_CONTENT_LIMIT = 14_000
MEMORY_HIT_LIMIT = 8
CRITIC_HIT_LIMIT = 6


def trim_text(text: str, limit: int) -> str:
    """Truncates text if it exceeds the specified character limit."""
    if len(text) <= limit:
        return text
    keep = max(0, limit - 40)
    return f"{text[:keep]}\n# [TRUNCATED]\n"


def _strip_code_fences(text: str) -> str:
    """Removes markdown code fences from the provided text."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json|python|py)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _extract_balanced_json(text: str) -> Optional[str]:
    """Finds and extracts a balanced JSON object or array from a string."""
    start_obj = text.find("{")
    start_arr = text.find("[")
    
    if start_obj == -1 and start_arr == -1:
        return None

    if start_arr != -1 and (start_obj == -1 or start_arr < start_obj):
        start = start_arr
        open_ch, close_ch = "[", "]"
    else:
        start = start_obj
        open_ch, close_ch = "{", "}"

    depth = 0
    in_string = False
    escape = False

    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
        elif ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def repair_json_text(text: str) -> str:
    """Attempts to repair malformed JSON string into a parseable format."""
    if not text:
        return ""

    cleaned = text.strip().lstrip("\ufeff")
    cleaned = _strip_code_fences(cleaned)
    cleaned = cleaned.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    cleaned = re.sub(r",(\s*[}\]])", r"\1", cleaned)

    try:
        json.loads(cleaned)
        return cleaned
    except (json.JSONDecodeError, ValueError):
        pass

    balanced = _extract_balanced_json(cleaned)
    if balanced:
        try:
            json.loads(balanced)
            return balanced
        except (json.JSONDecodeError, ValueError):
            pass

    return cleaned


def safe_json_extract(text: str) -> Optional[Any]:
    """Attempts to extract and parse JSON from raw text safely."""
    repaired = repair_json_text(text)
    if not repaired:
        return None

    try:
        return json.loads(repaired)
    except (json.JSONDecodeError, ValueError):
        return None


def _compact_hit(hit: MemoryHit) -> Dict[str, Any]:
    """Reduces memory hit payloads to fit context windows."""
    payload = dict(hit.payload)
    for key in ("summary", "critique", "description", "notes"):
        if isinstance(payload.get(key), str) and len(payload[key]) > 700:
            payload[key] = payload[key][:700]
    return {"kind": hit.kind, "score": hit.score, "payload": payload}


def _serialize_file(item: FileItem) -> Dict[str, Any]:
    """Serializes a file item into a dictionary for prompts."""
    content_limit = PYTHON_CONTENT_LIMIT if item.language == "python" else NON_PYTHON_CONTENT_LIMIT
    return {
        "path": item.path,
        "language": item.language,
        "size_kb": round(item.size_kb, 2),
        "imports": item.imports,
        "fingerprint": item.fingerprint,
        "content": trim_text(item.content, content_limit),
    }


def build_python_prompt(file_item: FileItem, context_hits: Sequence[MemoryHit], strategy: str) -> str:
    """Builds a prompt for Python file optimization."""
    prompt_obj = {
        "task": "Rewrite the entire Python file and return ONLY valid JSON.",
        "model_behavior": {
            "priority": "full_file_rewrite",
            "allowed_style": "safe_deep_refactor",
            "large_file_policy": "do_not_shorten_or_truncate_the_file",
        },
        "strategy": strategy,
        "constraints": [
            "Return exactly one JSON object.",
            "The JSON must contain a 'files' array.",
            "For Python files, 'code' must contain the complete improved source code.",
            "Do not return patches or partial edits.",
            "Preserve public behavior and interfaces.",
            "Add type hints and docstrings.",
            "Do not include markdown or explanations."
        ],
        "file": _serialize_file(file_item),
        "context": [_compact_hit(hit) for hit in context_hits[:MEMORY_HIT_LIMIT]],
    }
    return json.dumps(prompt_obj, ensure_ascii=False)


def build_non_python_prompt(file_item: FileItem, context_hits: Sequence[MemoryHit], strategy: str) -> str:
    """Builds a prompt for non-Python file optimization."""
    prompt_obj = {
        "task": "Rewrite the file and return ONLY valid JSON.",
        "model_behavior": {"priority": "full_file_rewrite"},
        "strategy": strategy,
        "file": _serialize_file(file_item),
        "context": [_compact_hit(hit) for hit in context_hits[:MEMORY_HIT_LIMIT]],
    }
    return json.dumps(prompt_obj, ensure_ascii=False)


def build_critic_prompt(file_items: Sequence[FileItem], drafted_results: Sequence[ImprovementResult], context_hits: Sequence[MemoryHit], strategy: str) -> str:
    """Builds a prompt for critiquing proposed changes."""
    proposals = [
        {
            "path": item.path,
            "result_summary": result.summary,
            "risk": result.risk,
            "code_preview": trim_text(result.code, 3500),
        } for item, result in zip(file_items, drafted_results)
    ]
    
    prompt_obj = {
        "task": "Critique the proposed file changes. Return ONLY JSON.",
        "strategy": strategy,
        "context": [_compact_hit(hit) for hit in context_hits[:CRITIC_HIT_LIMIT]],
        "proposals": proposals,
    }
    return json.dumps(prompt_obj, ensure_ascii=False)


def build_json_repair_prompt(raw_text: str, expected_schema: Dict[str, Any]) -> str:
    """Builds a prompt specifically for fixing broken JSON output."""
    return json.dumps({
        "task": "Repair the text into valid JSON only.",
        "expected_schema": expected_schema,
        "raw_text": trim_text(raw_text, 18_000),
    }, ensure_ascii=False)