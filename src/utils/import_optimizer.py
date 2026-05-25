"""Automate import optimization using ruff."""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

def optimize_imports(file_path: Path) -> bool:
    """
    Run ruff to fix import sorting and remove unused imports.

    Args:
        file_path: The filesystem path to the Python file to be optimized.

    Returns:
        bool: True if the operation succeeded, False otherwise.
    """
    try:
        # Ensure we are invoking ruff correctly with the target file
        subprocess.run(
            ["ruff", "check", "--fix", str(file_path)],
            check=True,
            capture_output=True,
            text=True
        )
        return True
    except subprocess.CalledProcessError as e:
        logger.error("Ruff failed to optimize %s: %s", file_path, e.stderr)
        return False
    except (FileNotFoundError, OSError) as e:
        logger.warning("Ruff execution failed or command not found: %s", e)
        return False