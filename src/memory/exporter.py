from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Iterable

from .gold_filter import ExperienceSample

logger = logging.getLogger(__name__)

def save_jsonl(samples: Iterable[ExperienceSample], output_file: str | Path) -> Path:
    """
    Serializes a collection of ExperienceSample objects into a newline-delimited JSON (JSONL) file.

    Args:
        samples: An iterable of ExperienceSample instances to export.
        output_file: The destination path (str or Path) for the resulting file.

    Returns:
        The pathlib.Path object of the written file.

    Raises:
        IOError: If an error occurs during file writing or directory creation.
    """
    output_path = Path(output_file)
    
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.error(f"Failed to create directory {output_path.parent}: {e}")
        raise

    try:
        with output_path.open("w", encoding="utf-8") as f:
            for sample in samples:
                row: dict[str, Any] = {
                    "instruction": sample.instruction,
                    "input": sample.input_text,
                    "output": sample.output_text,
                    "score": sample.score,
                    "meta": sample.meta,
                }
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError as e:
        logger.error(f"Failed to write data to {output_path}: {e}")
        raise

    return output_path