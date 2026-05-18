# src/memory/exporter.py
"""
Экспорт отобранных сэмплов в JSONL.
Exports selected experience samples to JSONL format.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .gold_filter import ExperienceSample


def save_jsonl(samples: Iterable[ExperienceSample], output_file: str | Path) -> Path:
    """
    Saves a collection of ExperienceSample objects to a JSONL file.

    Each ExperienceSample is serialized into a JSON object and written as a new line
    in the specified output file. Parent directories for the output file will be
    created if they don't already exist.

    Args:
        samples (Iterable[ExperienceSample]): An iterable collection of experience samples to save.
        output_file (str | Path): The path to the output JSONL file. Can be a string or a Path object.

    Returns:
        Path: The pathlib.Path object representing the saved file.
    """
    output_path: Path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as f:
        for sample in samples:
            row = {
                "instruction": sample.instruction,
                "input": sample.input_text,
                "output": sample.output_text,
                "score": sample.score,
                "meta": sample.meta,
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    return output_path
