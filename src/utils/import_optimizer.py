"""Utilities for optimizing Python imports and applying lightweight Ruff fixes."""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)


def optimize_imports(file_path: str | Path, *, extra_args: Iterable[str] = ()) -> bool:
    """Run Ruff import/lint autofixes for a Python file."""
    path = Path(file_path)

    if not path.exists() or not path.is_file():
        logger.warning("Cannot optimize imports: file not found: %s", path)
        return False

    if path.suffix != ".py":
        logger.warning("Cannot optimize imports: not a Python file: %s", path)
        return False

    ruff_bin = shutil.which("ruff")
    if not ruff_bin:
        logger.warning("Ruff command not found. Install ruff to enable import optimization.")
        return False

    command = [
        ruff_bin,
        "check",
        "--fix",
        "--select",
        "I,F401",
        str(path),
        *[str(arg) for arg in extra_args],
    ]

    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode == 0:
            logger.debug("Ruff import optimization completed for %s.", path)
            return True

        logger.error(
            "Ruff failed for %s with code=%s stdout=%s stderr=%s",
            path,
            result.returncode,
            result.stdout.strip(),
            result.stderr.strip(),
        )
        return False

    except subprocess.TimeoutExpired:
        logger.error("Ruff timed out while optimizing %s.", path)
        return False
    except OSError as exc:
        logger.warning("Ruff execution failed for %s: %s", path, exc)
        return False


def optimize_many(file_paths: Iterable[str | Path]) -> dict[str, bool]:
    """Optimize imports for multiple Python files and return per-file status."""
    return {str(path): optimize_imports(path) for path in file_paths}