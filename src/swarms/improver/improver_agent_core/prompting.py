from __future__ import annotations

import json
import re
from typing import Any, Dict, Mapping, Optional, Sequence

from .models import FileItem, ImprovementResult, MemoryHit

PYTHON_CONTENT_LIMIT = 32_000
NON_PYTHON_CONTENT_LIMIT = 14_000
MEMORY_HIT_LIMIT = 8
CRITIC_HIT_LIMIT = 6
PROJECT_CONTEXT_LIMIT = 9_000


def trim_text(text: str, limit: int) -> str:
    """Truncate text to a safe size for prompts."""
    if len(text) <= limit:
        return text
    keep = max(0, limit - 40)
    return f"{text[:keep]}\n# [TRUNCATED]\n"


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences from model output."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json|python|py)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _extract_balanced_json(text: str) -> Optional[str]:
    """Extract the first balanced JSON object or array from a string."""
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
    """Attempt to repair malformed JSON into a parseable form."""
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
        balanced = re.sub(r",(\s*[}\]])", r"\1", balanced)
        try:
            json.loads(balanced)
            return balanced
        except (json.JSONDecodeError, ValueError):
            pass

    return cleaned


def safe_json_extract(text: str) -> Optional[Any]:
    """Safely extract JSON from raw model output."""
    repaired = repair_json_text(text)
    if not repaired:
        return None

    for candidate in (repaired, _strip_code_fences(text)):
        try:
            return json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            continue
    return None


def _compact_hit(hit: MemoryHit) -> Dict[str, Any]:
    """Reduce memory payload size for prompt context."""
    payload = dict(hit.payload)
    for key in ("summary", "critique", "description", "notes"):
        if isinstance(payload.get(key), str) and len(payload[key]) > 700:
            payload[key] = payload[key][:700]
    return {"kind": hit.kind, "score": hit.score, "payload": payload}


def _serialize_file(item: FileItem) -> Dict[str, Any]:
    """Serialize a file item into prompt-friendly JSON."""
    content_limit = PYTHON_CONTENT_LIMIT if item.language == "python" else NON_PYTHON_CONTENT_LIMIT
    return {
        "path": item.path,
        "language": item.language,
        "size_kb": round(item.size_kb, 2),
        "imports": item.imports,
        "fingerprint": item.fingerprint,
        "content": trim_text(item.content, content_limit),
    }


def build_python_prompt(
    file_item: FileItem,
    context_hits: Sequence[MemoryHit],
    strategy: str,
    project_context: Optional[Mapping[str, Any]] = None,
) -> str:
    """Build a prompt for full Python-file rewrites."""
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
            "Add type hints and docstrings where appropriate.",
            "Do not include markdown or explanations.",
            "Use project_context to preserve module boundaries, imports, and public APIs.",
            "Prefer minimal semantic changes unless the context clearly supports a deeper refactor.",
            "Do not change numeric thresholds, defaults, timing, limits, scoring constants, or risk parameters unless necessary and explicitly justified in notes.",
            "If changing numeric/default semantics, set risk >= 0.35 and explain why in notes.",
        ],
        "output_schema": {
            "files": [
                {
                    "path": file_item.path,
                    "action": "replace_file",
                    "summary": "short summary",
                    "risk": 0.0,
                    "tags": ["refactor"],
                    "code": "full file source",
                    "notes": "",
                }
            ],
            "overall_summary": "short overall summary",
            "overall_risk": 0.0,
            "should_repair": False,
            "critique_notes": "",
        },
        "file": _serialize_file(file_item),
        "project_context": project_context or {},
        "context": [_compact_hit(hit) for hit in context_hits[:MEMORY_HIT_LIMIT]],
    }
    return json.dumps(prompt_obj, ensure_ascii=False)


def build_non_python_prompt(
    file_item: FileItem,
    context_hits: Sequence[MemoryHit],
    strategy: str,
    prefer_patch: bool = False,
    project_context: Optional[Mapping[str, Any]] = None,
) -> str:
    """Build a prompt for non-Python file improvements."""
    prompt_obj = {
        "task": "Rewrite the file and return ONLY valid JSON.",
        "model_behavior": {
            "priority": "patch_or_full_rewrite" if prefer_patch else "full_file_rewrite",
            "prefer_patch": prefer_patch,
        },
        "strategy": strategy,
        "constraints": [
            "Return exactly one JSON object.",
            "Do not include markdown or explanations.",
            "Keep the output focused on a single file.",
            "Use project_context to preserve surrounding structure and references.",
            "Prefer minimal semantic changes unless the context clearly supports a deeper refactor.",
        ],
        "output_schema": {
            "files": [
                {
                    "path": file_item.path,
                    "action": "patch" if prefer_patch else "replace_file",
                    "summary": "short summary",
                    "risk": 0.0,
                    "tags": ["refactor"],
                    "code": "full file source or empty when patching",
                    "notes": "",
                    "patches": [
                        {
                            "type": "replace_block",
                            "target": "symbol or block name",
                            "before": "original text",
                            "after": "replacement text",
                            "new_code": "replacement text",
                            "summary": "short summary",
                            "reason": "why this change helps",
                            "confidence": 0.0,
                            "scope": "file/symbol scope",
                        }
                    ],
                }
            ],
            "overall_summary": "short overall summary",
            "overall_risk": 0.0,
            "should_repair": False,
            "critique_notes": "",
        },
        "file": _serialize_file(file_item),
        "project_context": project_context or {},
        "context": [_compact_hit(hit) for hit in context_hits[:MEMORY_HIT_LIMIT]],
    }
    return json.dumps(prompt_obj, ensure_ascii=False)


def build_critic_prompt(
    file_items: Sequence[FileItem],
    drafted_results: Sequence[ImprovementResult],
    context_hits: Sequence[MemoryHit],
    strategy: str,
) -> str:
    """Build a prompt for critiquing a draft plan."""
    proposals = [
        {
            "path": item.path,
            "result_summary": result.summary,
            "risk": result.risk,
            "code_preview": trim_text(result.code, 3500),
        }
        for item, result in zip(file_items, drafted_results)
    ]

    prompt_obj = {
        "task": "Critique the proposed file changes. Return ONLY JSON.",
        "strategy": strategy,
        "context": [_compact_hit(hit) for hit in context_hits[:CRITIC_HIT_LIMIT]],
        "proposals": proposals,
        "output_schema": {
            "approved": False,
            "overall_risk": 0.0,
            "blocking_issues": [],
            "non_blocking_suggestions": [],
            "preferred_action": "revise",
            "critique": "short critique text",
        },
    }
    return json.dumps(prompt_obj, ensure_ascii=False)


def build_json_repair_prompt(raw_text: str, expected_schema: Dict[str, Any]) -> str:
    """Build a prompt for repairing malformed JSON."""
    return json.dumps(
        {
            "task": "Repair the text into valid JSON only.",
            "expected_schema": expected_schema,
            "raw_text": trim_text(raw_text, 18_000),
        },
        ensure_ascii=False,
    )


def build_proposals_prompt(
    memory_patterns: Sequence[Dict[str, Any]],
    strategy_stats: Dict[str, Dict[str, float]],
    project_dirs: Sequence[str],
) -> str:
    """Build a prompt for generating higher-level improvement proposals."""
    prompt_obj = {
        "task": "Analyze the project and propose 2-3 new Python modules or subfolders that could improve quality, reliability, or autonomy.",
        "project_dirs": list(project_dirs),
        "memory_patterns": list(memory_patterns),
        "strategy_stats": strategy_stats,
        "constraints": [
            "Return only JSON.",
            "Keep proposal descriptions concrete.",
            "Avoid vague 'improve everything' style suggestions.",
        ],
        "output_schema": {
            "proposals": [
                {
                    "path": "src/new_module.py",
                    "description": "...",
                    "reason": "...",
                    "code_skeleton": "...",
                    "risk": 0.0,
                    "tags": ["memory", "metrics"],
                }
            ],
            "summary": "short summary",
        },
    }
    return json.dumps(prompt_obj, ensure_ascii=False, separators=(",", ":"))