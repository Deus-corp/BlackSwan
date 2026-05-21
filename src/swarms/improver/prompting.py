from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Sequence

from src.swarms.improver.models import FileItem, MemoryHit, ImprovementResult
from src.swarms.improver.validation import safe_json_extract as _safe_json_extract


def trim_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 40)] + "\n# [TRUNCATED]\n"


def safe_json_extract(text: str) -> Any | None:
    """
    Backwards-compatible wrapper. Real repair logic lives in validation.py.
    """
    return _safe_json_extract(text)


def _compact_hit(hit: MemoryHit) -> Dict[str, Any]:
    payload = dict(hit.payload)
    for key in ("summary", "critique", "description"):
        if isinstance(payload.get(key), str) and len(payload[key]) > 500:
            payload[key] = payload[key][:500]
    return {"kind": hit.kind, "score": hit.score, "payload": payload}


def _serialize_files(file_items: Sequence[FileItem], content_limit: int = 10_000) -> List[Dict[str, Any]]:
    files: List[Dict[str, Any]] = []
    for item in file_items:
        files.append(
            {
                "path": item.path,
                "language": item.language,
                "size_kb": round(item.size_kb, 2),
                "imports": item.imports,
                "fingerprint": item.fingerprint,
                "content": trim_text(item.content, content_limit),
            }
        )
    return files


def _patch_only_schema() -> Dict[str, Any]:
    return {
        "files": [
            {
                "path": "path/to/file.py",
                "action": "patch",
                "summary": "what changed",
                "risk": 0.0,
                "tags": ["typing", "refactor"],
                "patches": [
                    {
                        "type": "replace_function",
                        "target": "function_name",
                        "new_code": "replacement code for that function",
                        "summary": "why this patch exists",
                        "reason": "why this is safe",
                        "confidence": 0.0,
                        "scope": "function",
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


def _full_schema() -> Dict[str, Any]:
    return {
        "files": [
            {
                "path": "path/to/file.py",
                "action": "replace_file",
                "summary": "what changed",
                "risk": 0.0,
                "tags": ["typing", "refactor"],
                "patches": [],
                "full_code": "complete file contents",
                "notes": "",
            }
        ],
        "overall_summary": "short summary",
        "overall_risk": 0.0,
        "should_repair": False,
        "critique_notes": "",
    }


def build_patch_prompt(
    file_item: FileItem,
    context_hits: Sequence[MemoryHit],
    strategy: str,
    issue_summary: str,
    patch_only: bool = True,
) -> str:
    """
    Single-file prompt. In patch_only mode, the model must return only patch operations.
    This is the most stable mode for Mistral.
    """
    schema = _patch_only_schema() if patch_only else _full_schema()
    constraints = [
        "Return only JSON.",
        "Do not use markdown or code fences.",
        "Keep the change minimal.",
        "Prefer replace_function / replace_class / replace_import / delete.",
    ]
    if patch_only:
        constraints.append("Do not return full_code for this Python file.")
        constraints.append("Return only patches; do not rewrite the whole file.")
    else:
        constraints.append("If necessary, full_code is allowed.")

    prompt_obj = {
        "task": "Patch a single Python file with minimal local edits.",
        "strategy": strategy,
        "file": {
            "path": file_item.path,
            "language": file_item.language,
            "size_kb": round(file_item.size_kb, 2),
            "imports": file_item.imports,
            "fingerprint": file_item.fingerprint,
            "content": trim_text(file_item.content, 12_000),
        },
        "issue_summary": issue_summary,
        "context": [_compact_hit(hit) for hit in context_hits[:6]],
        "constraints": constraints,
        "output_mode": "patch_only" if patch_only else "full_or_patch",
        "output_schema": schema,
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
                "patches": [
                    {
                        "type": patch.type,
                        "target": patch.target,
                        "summary": patch.summary,
                        "reason": patch.reason,
                        "confidence": patch.confidence,
                        "scope": patch.scope,
                    }
                    for patch in result.patches
                ],
            }
        )

    prompt_obj = {
        "task": "Critique the proposed file changes. Return ONLY JSON.",
        "strategy": strategy,
        "rules": [
            "Focus on correctness, risk, scope creep, and whether changes are too broad.",
            "Point out any patch that looks unsafe or under-specified.",
            "Prefer a concise but actionable critique.",
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

def build_prompt(
    file_items: Sequence[FileItem],
    context_hits: Sequence[MemoryHit],
    strategy: str,
    critic_feedback: str = "",
    issue_summary: str = "",
) -> str:
    """
    Compatibility wrapper: builds a batch prompt by aggregating single-file patch prompts.
    """
    files_payload = []
    for item in file_items:
        single = build_patch_prompt(
            file_item=item,
            context_hits=context_hits,
            strategy=strategy,
            issue_summary=issue_summary or "Improve code quality, add types, fix obvious issues.",
            patch_only=True,
        )
        try:
            obj = json.loads(single)
        except Exception:
            obj = {"file": {"path": item.path, "content": item.content[:5000]}}
        files_payload.append(obj)

    return json.dumps(
        {
            "task": "Improve multiple files",
            "strategy": strategy,
            "critic_feedback": critic_feedback,
            "files": files_payload,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
