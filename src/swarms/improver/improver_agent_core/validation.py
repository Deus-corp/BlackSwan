from __future__ import annotations

import ast
import dataclasses
import difflib
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from shutil import which
from typing import Any, Dict, List, Optional, Tuple

from .models import FileItem, PatchOperation, ValidationResult


def fingerprint_text(text: str) -> str:
    normalized = (text or "").replace("\r\n", "\n")
    return hashlib.sha256(normalized.encode("utf-8", errors="ignore")).hexdigest()


def changed_line_ratio(old: str, new: str) -> float:
    old_lines = (old or "").splitlines()
    new_lines = (new or "").splitlines()

    if not old_lines and not new_lines:
        return 0.0
    if not old_lines or not new_lines:
        return 1.0

    matcher = difflib.SequenceMatcher(a=old_lines, b=new_lines)
    same = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            same += max(i2 - i1, j2 - j1)

    total = max(len(old_lines), len(new_lines), 1)
    changed = 1.0 - (same / total)
    return max(0.0, min(1.0, changed))


def guess_language(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext in {".py", ".pyi"}:
        return "python"
    if ext in {".js", ".jsx"}:
        return "javascript"
    if ext in {".ts", ".tsx"}:
        return "typescript"
    if ext in {".md", ".markdown"}:
        return "markdown"
    if ext in {".json"}:
        return "json"
    if ext in {".yml", ".yaml"}:
        return "yaml"
    if ext in {".toml"}:
        return "toml"
    if ext in {".html", ".htm"}:
        return "html"
    if ext in {".css"}:
        return "css"
    if ext in {".sh"}:
        return "shell"
    return "text"


def extract_python_imports(code: str) -> List[str]:
    imports: List[str] = []
    try:
        tree = ast.parse(code)
    except Exception:
        return imports

    seen = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name.split(".")[0].strip()
                if name and name not in seen:
                    seen.add(name)
                    imports.append(name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                name = node.module.split(".")[0].strip()
                if name and name not in seen:
                    seen.add(name)
                    imports.append(name)

    return imports


def safe_output_path(base_dir: Path, relative_path: str) -> Path:
    """
    Build a safe output path under base_dir without allowing traversal.
    """
    base_dir = Path(base_dir).resolve()
    raw = Path(str(relative_path).replace("\\", "/"))

    safe_parts: List[str] = []
    for part in raw.parts:
        if part in {"", ".", "/"}:
            continue
        if part == "..":
            continue
        if ":" in part:
            part = part.replace(":", "_")
        safe_parts.append(part)

    if not safe_parts:
        safe_parts = [raw.name or "output.py"]

    candidate = base_dir.joinpath(*safe_parts).resolve()
    if candidate != base_dir and base_dir not in candidate.parents:
        raise ValueError(f"Unsafe output path: {relative_path}")
    return candidate


def atomic_write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(content)
        os.replace(tmp_path, path)
    finally:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception:
            pass


def command_exists(cmd: str) -> bool:
    return which(cmd) is not None

def subprocess_diagnostics(
    proc: subprocess.CompletedProcess[bytes],
    *,
    command: List[str],
    output_limit: int = 4000,
) -> Dict[str, Any]:
    """Build compact diagnostics for subprocess-based validators."""
    stdout_raw = proc.stdout or b""
    stderr_raw = proc.stderr or b""

    stdout = stdout_raw.decode("utf-8", errors="replace")
    stderr = stderr_raw.decode("utf-8", errors="replace")

    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout_tail": stdout[-output_limit:],
        "stderr_tail": stderr[-output_limit:],
    }

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
    """
    Conservative JSON repair for LLM output.
    """
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


def normalize_patch_operation(raw: Dict[str, Any]) -> Optional[PatchOperation]:
    if not isinstance(raw, dict):
        return None

    patch_type = str(raw.get("type", "") or "").strip()
    target = str(raw.get("target", "") or "").strip()
    if not patch_type or not target:
        return None

    try:
        confidence = float(raw.get("confidence", 0.0) or 0.0)
    except Exception:
        confidence = 0.0

    return PatchOperation(
        type=patch_type,  # type: ignore[arg-type]
        target=target,
        new_code=str(raw.get("new_code", "") or ""),
        summary=str(raw.get("summary", "") or ""),
        reason=str(raw.get("reason", "") or ""),
        confidence=max(0.0, min(1.0, confidence)),
        scope=str(raw.get("scope", "") or ""),
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
    if patch.type != "delete" and patch.type != "replace_import" and not patch.new_code.strip():
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
        validation.notes.append(f"syntax_error:{e}")
    except Exception as e:
        validation.notes.append(f"compile_error:{e}")


def _run_ruff_on_text_with_diagnostics(code: str) -> Tuple[Optional[bool], Dict[str, Any]]:
    command = ["ruff", "check", "--quiet", "-"]

    try:
        proc = subprocess.run(
            command,
            input=code.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
            check=False,
        )
        return proc.returncode == 0, subprocess_diagnostics(proc, command=command)
    except Exception as exc:
        return None, {
            "command": command,
            "error": str(exc),
        }


def _run_ruff_on_text(code: str) -> Optional[bool]:
    ok, _diagnostics = _run_ruff_on_text_with_diagnostics(code)
    return ok


def _run_mypy_on_temp_file_with_diagnostics(
    code: str,
    path: str,
    staging_dir: Path,
) -> Tuple[Optional[bool], Dict[str, Any]]:
    temp_dir = staging_dir / "mypy"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_file = temp_dir / (Path(path).name or "temp.py")
    command = ["mypy", "--ignore-missing-imports", str(temp_file)]

    try:
        temp_file.write_text(code, encoding="utf-8")
        proc = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
            check=False,
        )
        return proc.returncode == 0, subprocess_diagnostics(proc, command=command)
    except Exception as exc:
        return None, {
            "command": command,
            "error": str(exc),
        }


def _run_mypy_on_temp_file(code: str, path: str, staging_dir: Path) -> Optional[bool]:
    ok, _diagnostics = _run_mypy_on_temp_file_with_diagnostics(code, path, staging_dir)
    return ok


def run_pytest_smoke_with_diagnostics(project_root: Path) -> Tuple[Optional[bool], Dict[str, Any]]:
    project_root = Path(project_root)

    candidates = [
        project_root / "pytest.ini",
        project_root / "pyproject.toml",
        project_root / "setup.cfg",
        project_root / "tests",
    ]
    if not any(c.exists() for c in candidates):
        return None, {
            "reason": "no_pytest_config_or_tests",
            "project_root": str(project_root),
        }

    command = [sys.executable, "-m", "pytest", "-q", "--maxfail=1"]

    try:
        proc = subprocess.run(
            command,
            cwd=str(project_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120,
            check=False,
        )
        diagnostics = subprocess_diagnostics(proc, command=command)
        diagnostics["cwd"] = str(project_root)
        return proc.returncode == 0, diagnostics
    except Exception as exc:
        return None, {
            "command": command,
            "cwd": str(project_root),
            "error": str(exc),
        }
    
def run_pytest_paths_with_diagnostics(
    project_root: Path,
    paths: List[str],
    *,
    timeout: int = 120,
) -> Tuple[Optional[bool], Dict[str, Any]]:
    """Run pytest against selected paths with compact diagnostics."""
    project_root = Path(project_root)

    selected = []
    for raw_path in paths:
        path = Path(raw_path)
        if path.is_absolute():
            try:
                path = path.relative_to(project_root)
            except Exception:
                pass

        candidate = project_root / path
        if candidate.exists():
            selected.append(str(path))

    if not selected:
        return None, {
            "reason": "no_existing_pytest_paths",
            "project_root": str(project_root),
            "paths": paths,
        }

    command = [sys.executable, "-m", "pytest", "-q", "--maxfail=1", *selected]

    try:
        proc = subprocess.run(
            command,
            cwd=str(project_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
        diagnostics = subprocess_diagnostics(proc, command=command)
        diagnostics["cwd"] = str(project_root)
        diagnostics["selected_paths"] = selected
        return proc.returncode == 0, diagnostics
    except Exception as exc:
        return None, {
            "command": command,
            "cwd": str(project_root),
            "selected_paths": selected,
            "error": str(exc),
        }

def run_pytest_smoke(project_root: Path) -> Optional[bool]:
    ok, _diagnostics = run_pytest_smoke_with_diagnostics(project_root)
    return ok


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

    language = (original.language or guess_language(original.path)).lower()

    if language != "python":
        validation.syntactically_valid = True
        validation.compile_ok = True
        return validation

    _validate_python_syntax(original, code, validation)
    if not validation.syntactically_valid:
        return validation

    ratio = changed_line_ratio(original.content, code)
    if ratio > max_changed_lines_ratio:
        validation.notes.append("changed_too_much")

    if not enable_validation:
        return validation

    if command_exists("ruff"):
        ruff_ok, ruff_diagnostics = _run_ruff_on_text_with_diagnostics(code)
        validation.ruff_ok = ruff_ok
        if ruff_diagnostics:
            validation.diagnostics["ruff"] = ruff_diagnostics
        if validation.ruff_ok is False:
            validation.notes.append("ruff_failed")

    if command_exists("mypy"):
        mypy_ok, mypy_diagnostics = _run_mypy_on_temp_file_with_diagnostics(
            code,
            original.path,
            staging_dir,
        )
        validation.mypy_ok = mypy_ok
        if mypy_diagnostics:
            validation.diagnostics["mypy"] = mypy_diagnostics
        if validation.mypy_ok is False:
            validation.notes.append("mypy_failed")

    return validation