from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Iterable, Union

from .gold_filter import ExperienceSample

logger = logging.getLogger(__name__)

def save_jsonl(
    samples: Iterable[ExperienceSample], 
    output_file: Union[str, Path]
) -> Path:
    """
    Serializes an iterable of ExperienceSample objects into a newline-delimited JSON (JSONL) file.

    Args:
        samples: An iterable of ExperienceSample instances to export.
        output_file: The destination path for the resulting file.

    Returns:
        The pathlib.Path object of the successfully written file.

    Raises:
        OSError: If an error occurs during directory creation or file writing.
    """
    output_path = Path(output_file)

    # Ensure the parent directory structure exists
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.error("Failed to create directory %s: %s", output_path.parent, e)
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
                # Write each sample as a single line JSON string
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except (OSError, TypeError, ValueError) as e:
        logger.error("Failed to write data to %s: %s", output_path, e)
        raise

    return output_path