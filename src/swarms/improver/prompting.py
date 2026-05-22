from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Sequence

from src.swarms.improver.models import FileItem, MemoryHit, ImprovementResult


def trim_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    keep = max(0, limit - 40)
    return text[:keep] + "\n# [TRUNCATED]\n"


def _strip_code_fences(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json|python|py)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _extract_balanced_json(text: str) -> str | None:
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
    """Best-effort cleanup for model output before json.loads."""
    if not text:
        return ""

    cleaned = text.strip().lstrip("\ufeff")
    cleaned = _strip_code_fences(cleaned)
    cleaned = cleaned.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    cleaned = re.sub(r",(\s*[}\]])", r"\1", cleaned)

    try:
        json.loads(cleaned)
        return cleaned
    except Exception:
        pass

    balanced = _extract_balanced_json(cleaned)
    if balanced:
        balanced = re.sub(r",(\s*[}\]])", r"\1", balanced)
        try:
            json.loads(balanced)
            return balanced
        except Exception:
            pass

    start = min([i for i in [cleaned.find("{"), cleaned.find("[")] if i != -1], default=-1)
    end = max(cleaned.rfind("}"), cleaned.rfind("]"))
    if start != -1 and end != -1 and end > start:
        snippet = cleaned[start : end + 1]
        snippet = re.sub(r"\s+", " ", snippet)
        snippet = re.sub(r",(\s*[}\]])", r"\1", snippet)
        try:
            json.loads(snippet)
            return snippet
        except Exception:
            pass

    return cleaned


def safe_json_extract(text: str) -> Any | None:
    if not text:
        return None

    repaired = repair_json_text(text)
    if not repaired:
        return None

    for candidate in (repaired, _strip_code_fences(text)):
        try:
            return json.loads(candidate)
        except Exception:
            pass
    return None


def _compact_hit(hit: MemoryHit) -> Dict[str, Any]:
    payload = dict(hit.payload)
    for key in ("summary", "critique", "description"):
        if isinstance(payload.get(key), str) and len(payload[key]) > 500:
            payload[key] = payload[key][:500]
    return {"kind": hit.kind, "score": hit.score, "payload": payload}


def _serialize_file(item: FileItem, *, content_limit: int = 12_000) -> Dict[str, Any]:
    return {
        "path": item.path,
        "language": item.language,
        "size_kb": round(item.size_kb, 2),
        "imports": item.imports,
        "fingerprint": item.fingerprint,
        "content": trim_text(item.content, content_limit),
    }


def _python_full_file_schema() -> Dict[str, Any]:
    return {
        "files": [
            {
                "path": "path/to/file.py",
                "code": "full improved file content",
                "summary": "short summary",
                "risk": 0.0,
                "tags": ["typing", "refactor"],
            }
        ],
        "overall_summary": "short summary",
        "overall_risk": 0.0,
        "should_repair": False,
        "critique_notes": "",
    }


def _non_python_optional_patch_schema() -> Dict[str, Any]:
    return {
        "files": [
            {
                "path": "path/to/file.txt",
                "action": "replace_file",
                "code": "full improved file content",
                "summary": "short summary",
                "risk": 0.0,
                "tags": ["cleanup"],
                "patches": [
                    {
                        "type": "replace_block",
                        "target": "target-name",
                        "new_code": "replacement text",
                        "summary": "why this patch exists",
                        "reason": "why this is safe",
                        "confidence": 0.0,
                        "scope": "file",
                    }
                ],
                "notes": "",
            }
        ],
        "overall_summary": "short summary",
        "overall_risk": 0.0,
        "should_repair": False,
        "critique_notes": "",
    }


def build_python_prompt(
    file_item: FileItem,
    context_hits: Sequence[MemoryHit],
    strategy: str,
) -> str:
    """Strict Python prompt: full-file JSON only. No patch schema exposed."""
    prompt_obj = {
        "task": "Improve the Python file and return ONLY valid JSON.",
        "strategy": strategy,
        "constraints": [
            "Return exactly one JSON object.",
            "The JSON must contain a 'files' array.",
            "Each file object must include 'path', 'code', 'summary', 'risk', and 'tags'.",
            "For Python files, 'code' must contain the full improved source code.",
            "Do not return patches or partial edits for Python files.",
            "Do not add markdown, explanations, or extra keys outside the schema.",
            "Preserve runtime behavior unless fixing a clear bug.",
        ],
        "file": _serialize_file(file_item),
        "context": [_compact_hit(hit) for hit in context_hits[:8]],
        "output_schema": _python_full_file_schema(),
    }
    return json.dumps(prompt_obj, ensure_ascii=False, separators=(",", ":"))


def build_non_python_prompt(
    file_item: FileItem,
    context_hits: Sequence[MemoryHit],
    strategy: str,
    prefer_patch: bool = True,
) -> str:
    """Non-Python prompt can still allow patches, but full-file output remains supported."""
    prompt_obj = {
        "task": "Improve the file and return ONLY valid JSON.",
        "strategy": strategy,
        "constraints": [
            "Return exactly one JSON object.",
            "The JSON must contain a 'files' array.",
            "For non-Python files, patches are allowed if helpful.",
            "If using patches, include target and new_code.",
            "If a full replacement is safer, provide 'code'.",
            "Do not add markdown, explanations, or extra commentary.",
        ],
        "file": _serialize_file(file_item),
        "context": [_compact_hit(hit) for hit in context_hits[:8]],
        "preferred_output_mode": "patch" if prefer_patch else "replace_file",
        "output_schema": _non_python_optional_patch_schema(),
    }
    return json.dumps(prompt_obj, ensure_ascii=False, separators=(",", ":"))


def build_critic_prompt(
    file_items: Sequence[FileItem],
    drafted_results: Sequence[ImprovementResult],
    context_hits: Sequence[MemoryHit],
    strategy: str,
) -> str:
    proposals = []
    for item, result in zip(file_items, drafted_results):
        proposals.append(
            {
                "path": item.path,
                "original_fingerprint": item.fingerprint,
                "result_summary": result.summary,
                "risk": result.risk,
                "strategy": result.strategy,
                "tags": result.memory_tags,
                "changed_lines_ratio": round(result.changed_lines_ratio, 4),
                "code_preview": trim_text(result.code, 2500),
            }
        )

    prompt_obj = {
        "task": "Critique the proposed file changes. Return ONLY JSON.",
        "strategy": strategy,
        "rules": [
            "Focus on correctness, risk, scope creep, and whether changes are too broad.",
            "Point out any output that looks unsafe or under-specified.",
            "Prefer concise but actionable critique.",
        ],
        "context": [_compact_hit(hit) for hit in context_hits[:6]],
        "proposals": proposals,
        "output_schema": {
            "approved": False,
            "overall_risk": 0.0,
            "blocking_issues": ["..."],
            "non_blocking_suggestions": ["..."],
            "preferred_action": "accept|revise|reject",
            "critique": "short review text",
        },
    }
    return json.dumps(prompt_obj, ensure_ascii=False, separators=(",", ":"))


def build_proposals_prompt(
    memory_patterns: Sequence[Dict[str, Any]],
    strategy_stats: Dict[str, Dict[str, float]],
    project_dirs: Sequence[str],
) -> str:
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


def build_json_repair_prompt(raw_text: str, expected_schema: Dict[str, Any]) -> str:
    prompt_obj = {
        "task": "Repair the text into valid JSON only. No markdown, no explanation.",
        "expected_schema": expected_schema,
        "raw_text": trim_text(raw_text, 18_000),
        "constraints": [
            "Return only the repaired JSON object or array.",
            "Preserve the original meaning.",
            "Do not add commentary.",
        ],
    }
    return json.dumps(prompt_obj, ensure_ascii=False, separators=(",", ":"))
