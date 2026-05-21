from __future__ import annotations

import ast
import dataclasses
import difflib
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from shutil import which
from typing import Any, Dict, List, Optional, Tuple

from src.swarms.improver.models import (
    FileItem,
    ImprovementResult,
    PatchOperation,
    ValidationResult,
)


def fingerprint_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def changed_line_ratio(old: str, new: str) -> float:
    old_lines = [line.rstrip("\n") for line in old.splitlines()]
    new_lines = [line.rstrip("\n") for line in new.splitlines()]
    if not old_lines and not new_lines:
        return 0.0

    matcher = difflib.SequenceMatcher(a=old_lines, b=new_lines)
    same = sum(block.size for block in matcher.get_matching_blocks())
    total = max(len(old_lines), len(new_lines), 1)
    changed = 1.0 - (same / total)
    return max(0.0, min(1.0, changed))


def guess_language(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext == ".py":
        return "python"
    if ext == ".md":
        return "markdown"
    if ext in {".js", ".jsx"}:
        return "javascript"
    if ext in {".ts", ".tsx"}:
        return "typescript"
    return "text"


def extract_python_imports(code: str) -> list[str]:
    imports: list[str] = []
    try:
        tree = ast.parse(code)
    except Exception:
        return imports

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module.split(".")[0])
    return sorted(set(imports))


def command_exists(cmd: str) -> bool:
    return which(cmd) is not None


def safe_output_path(base_dir: Path, relative_path: str) -> Path:
    base_dir = base_dir.resolve()
    candidate = (base_dir / relative_path).resolve()
    if candidate != base_dir and base_dir not in candidate.parents:
        raise ValueError(f"Unsafe output path: {relative_path}")
    return candidate


def atomic_write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(content)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except Exception:
            pass
        raise


def _strip_code_fences(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json|python|py)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _extract_balanced_json(text: str) -> str | None:
    """
    Extracts the first balanced JSON object or array from a string.
    """
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
    """
    Best-effort JSON repair for LLM outputs.

    This is intentionally conservative:
    - strips code fences
    - removes BOM
    - normalizes smart quotes
    - removes trailing commas
    - extracts the first balanced JSON object/array if needed
    """
    if not text:
        return ""

    cleaned = text.strip().lstrip("\ufeff")
    cleaned = _strip_code_fences(cleaned)
    cleaned = cleaned.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    cleaned = re.sub(r",(\s*[}\]])", r"\1", cleaned)

    # Try direct parse after cleanup.
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

    # Final attempt: collapse excessive whitespace inside the candidate region.
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
    """
    Parse JSON from a raw LLM response with tolerant repair.
    Returns dict/list if parse succeeds, otherwise None.
    """
    if not text:
        return None

    repaired = repair_json_text(text)
    if not repaired:
        return None

    for candidate in (repaired, _strip_code_fences(text)):
        try:
            parsed = json.loads(candidate)
            return parsed
        except Exception:
            pass

    return None


def normalize_patch_operation(raw: Dict[str, Any]) -> Optional[PatchOperation]:
    if not isinstance(raw, dict):
        return None

    patch_type = str(raw.get("type", "")).strip()
    target = str(raw.get("target", "")).strip()
    new_code = str(raw.get("new_code", "") or "")
    summary = str(raw.get("summary", "") or "")
    reason = str(raw.get("reason", "") or "")
    scope = str(raw.get("scope", "") or "")

    if not patch_type or not target:
        return None

    try:
        confidence = float(raw.get("confidence", 0.0) or 0.0)
    except Exception:
        confidence = 0.0

    return PatchOperation(
        type=patch_type,  # type: ignore[arg-type]
        target=target,
        new_code=new_code,
        summary=summary,
        reason=reason,
        confidence=max(0.0, min(1.0, confidence)),
        scope=scope,
        before=str(raw.get("before", "") or ""),
        after=str(raw.get("after", "") or ""),
    )


def validate_patch_operation(patch: PatchOperation) -> Tuple[bool, List[str]]:
    notes: List[str] = []
    valid_types = {
        "replace_function",
        "replace_class",
        "replace_import",
        "replace_block",
        "replace_file",
        "insert_before",
        "insert_after",
        "delete",
    }
    if patch.type not in valid_types:
        notes.append(f"invalid_patch_type:{patch.type}")
    if not patch.target.strip():
        notes.append("empty_patch_target")
    if patch.type != "delete" and not patch.new_code.strip() and patch.type != "replace_import":
        notes.append("empty_patch_code")
    if patch.confidence < 0.0 or patch.confidence > 1.0:
        notes.append("confidence_out_of_range")
    return (len(notes) == 0, notes)


def validate_patch_manifest(raw: Any) -> Tuple[List[PatchOperation], List[str]]:
    """
    Normalize a model response into patch operations.
    """
    notes: List[str] = []
    patches: List[PatchOperation] = []

    if not isinstance(raw, dict):
        return patches, ["manifest_not_dict"]

    raw_patches = raw.get("patches")
    if raw_patches is None:
        raw_patches = raw.get("operations")

    if not isinstance(raw_patches, list):
        return patches, ["manifest_missing_patches"]

    for item in raw_patches:
        patch = normalize_patch_operation(item if isinstance(item, dict) else {})
        if patch is None:
            notes.append("skipped_invalid_patch")
            continue
        ok, patch_notes = validate_patch_operation(patch)
        notes.extend(patch_notes)
        if ok:
            patches.append(patch)

    return patches, notes


def _validate_python_syntax(original: FileItem, code: str, validation: ValidationResult) -> None:
    try:
        tree = ast.parse(code)
        compile(tree, filename=original.path, mode="exec")
        validation.syntactically_valid = True
        validation.compile_ok = True
    except SyntaxError as e:
        validation.notes.append(f"syntax_error: {e}")
    except Exception as e:
        validation.notes.append(f"compile_error: {e}")


def _run_ruff_on_text(code: str, path: str) -> Optional[bool]:
    try:
        proc = subprocess.run(
            ["ruff", "check", "--quiet", "-"],
            input=code.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
            check=False,
        )
        return proc.returncode == 0
    except Exception:
        return None


def _run_mypy_on_temp_file(code: str, path: str, staging_dir: Path) -> Optional[bool]:
    temp_dir = staging_dir / "mypy"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_file = temp_dir / (Path(path).name or "temp.py")
    try:
        temp_file.write_text(code, encoding="utf-8")
        proc = subprocess.run(
            ["mypy", "--ignore-missing-imports", str(temp_file)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
            check=False,
        )
        return proc.returncode == 0
    except Exception:
        return None


def run_pytest_smoke(project_root: Path) -> Optional[bool]:
    candidates = [
        project_root / "pytest.ini",
        project_root / "pyproject.toml",
        project_root / "tests",
    ]
    if not any(c.exists() for c in candidates):
        return None

    try:
        proc = subprocess.run(
            ["pytest", "-q", "--maxfail=1"],
            cwd=str(project_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120,
            check=False,
        )
        return proc.returncode == 0
    except Exception:
        return None


def validate_result(
    original: FileItem,
    code: str,
    *,
    enable_validation: bool = True,
    staging_dir: Path = Path("./data/improver_staging"),
    max_changed_lines_ratio: float = 0.35,
) -> ValidationResult:
    validation = ValidationResult()

    if not code or not code.strip():
        validation.notes.append("empty_code")
        return validation

    if original.language != "python":
        validation.syntactically_valid = True
        validation.compile_ok = True
        return validation

    _validate_python_syntax(original, code, validation)
    if not validation.syntactically_valid:
        return validation

    if changed_line_ratio(original.content, code) > max_changed_lines_ratio:
        validation.notes.append("changed_too_much")

    if not enable_validation:
        return validation

    if command_exists("ruff"):
        validation.ruff_ok = _run_ruff_on_text(code, original.path)
        if validation.ruff_ok is False:
            validation.notes.append("ruff_failed")

    if command_exists("mypy"):
        validation.mypy_ok = _run_mypy_on_temp_file(code, original.path, staging_dir)
        if validation.mypy_ok is False:
            validation.notes.append("mypy_failed")

    return validation

def validate_patch_manifest(manifest: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """Validates a list of patch operations. Returns (is_valid, error_messages)."""
    # Простейшая проверка: манифест — список, каждый элемент имеет 'type'
    if not isinstance(manifest, list):
        return False, ["Manifest is not a list"]
    errors = []
    for i, patch in enumerate(manifest):
        if not isinstance(patch, dict):
            errors.append(f"Patch {i} is not a dict")
        elif "type" not in patch:
            errors.append(f"Patch {i} missing 'type'")
    return len(errors) == 0, errors