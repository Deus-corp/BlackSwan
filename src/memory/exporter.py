# src/memory/exporter.py
"""
Экспорт отобранных сэмплов в JSONL.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable
import json

from .gold_filter import ExperienceSample


def save_jsonl(samples: Iterable[ExperienceSample], output_file: str | Path) -> Path:
    output_path = Path(output_file)
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