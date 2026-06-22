from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Literal

PatchType = Literal[
    "replace_function",
    "replace_class",
    "replace_import",
    "replace_block",
    "replace_file",
    "insert_before",
    "insert_after",
    "delete",
]


@dataclass
class FileItem:
    """Represents a file entity within the workspace for improvement."""
    path: str
    content: str
    size_kb: float
    language: str = "python"
    imports: List[str] = field(default_factory=list)
    fingerprint: str = ""


@dataclass
class MemoryHit:
    """Represents a match found in the memory/knowledge base."""
    kind: str
    score: float
    payload: Dict[str, Any]


@dataclass
class ValidationResult:
    """Aggregates results from various validation steps."""
    syntactically_valid: bool = False
    compile_ok: bool = False
    ruff_ok: Optional[bool] = None
    mypy_ok: Optional[bool] = None
    pytest_ok: Optional[bool] = None
    patch_applied_ok: bool = False
    notes: List[str] = field(default_factory=list)
    diagnostics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PatchOperation:
    """Defines a specific, atomic edit instruction for code modification."""
    type: PatchType
    target: str
    new_code: str = ""
    summary: str = ""
    reason: str = ""
    confidence: float = 0.0
    scope: str = ""
    before: str = ""
    after: str = ""


@dataclass
class FilePatchPlan:
    """Orchestrates the application of patches to a target file."""
    path: str
    action: Literal["patch", "replace_file", "skip"] = "replace_file"
    summary: str = ""
    risk: float = 0.0
    tags: List[str] = field(default_factory=list)
    patches: List[PatchOperation] = field(default_factory=list)
    full_code: str = ""
    notes: str = ""


@dataclass
class DraftResponse:
    """Top-level structure for the initial improvement proposal from a planner model."""
    files: List[FilePatchPlan] = field(default_factory=list)
    overall_summary: str = ""
    overall_risk: float = 0.0
    should_repair: bool = False
    critique_notes: str = ""


@dataclass
class CritiqueResponse:
    """Structured feedback provided by the critic model."""
    approved: bool = False
    overall_risk: float = 0.0
    blocking_issues: List[str] = field(default_factory=list)
    non_blocking_suggestions: List[str] = field(default_factory=list)
    preferred_action: str = ""
    critique: str = ""


@dataclass
class ProposalItem:
    """A high-level improvement concept without full implementation details."""
    path: str
    description: str
    reason: str
    code_skeleton: str = ""
    risk: float = 0.0
    tags: List[str] = field(default_factory=list)


@dataclass
class ProposalResponse:
    """A collection of improvement proposals."""
    proposals: List[ProposalItem] = field(default_factory=list)
    summary: str = ""


@dataclass
class ImprovementResult:
    """The final state of an improvement process execution."""
    original_path: str
    proposed_path: str
    code: str
    language: str = "python"
    risk: float = 0.0
    summary: str = ""
    changed_lines_ratio: float = 1.0
    score: float = 0.0
    validation: ValidationResult = field(default_factory=ValidationResult)
    memory_tags: List[str] = field(default_factory=list)
    critique: str = ""
    strategy: str = "default"
    patches: List[PatchOperation] = field(default_factory=list)
    fallback_used: bool = False