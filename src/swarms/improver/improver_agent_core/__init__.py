#!/usr/bin/env python3
"""Improver agent core package.

Specialized implementation layer for ImproverAgent:
- CLI helpers
- SQLite-backed memory
- dataclass models
- prompt builders
- validation utilities
"""

from __future__ import annotations

from .memory import MemoryStore
from .models import (
    CritiqueResponse,
    DraftResponse,
    FileItem,
    FilePatchPlan,
    ImprovementResult,
    MemoryHit,
    PatchOperation,
    ValidationResult,
)
from .prompting import (
    build_critic_prompt,
    build_json_repair_prompt,
    build_non_python_prompt,
    build_proposals_prompt,
    build_python_prompt,
    safe_json_extract,
)
from .validation import (
    atomic_write_text,
    changed_line_ratio,
    extract_python_imports,
    fingerprint_text,
    guess_language,
    run_pytest_smoke,
    safe_output_path,
    validate_result,
)

__all__ = [
    "CritiqueResponse",
    "DraftResponse",
    "FileItem",
    "FilePatchPlan",
    "ImprovementResult",
    "MemoryHit",
    "MemoryStore",
    "PatchOperation",
    "ValidationResult",
    "atomic_write_text",
    "build_critic_prompt",
    "build_json_repair_prompt",
    "build_non_python_prompt",
    "build_proposals_prompt",
    "build_python_prompt",
    "changed_line_ratio",
    "extract_python_imports",
    "fingerprint_text",
    "guess_language",
    "run_pytest_smoke",
    "safe_json_extract",
    "safe_output_path",
    "validate_result",
]