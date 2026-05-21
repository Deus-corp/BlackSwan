"""Automate import optimization using ruff."""
from __future__ import annotations
from pathlib import Path
import subprocess

def optimize_imports(file_path: Path) -> bool:
    """Run ruff to fix import sorting and remove unused imports."""
    try:
        subprocess.run(["ruff", "check", "--fix", str(file_path)], check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
