from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Iterable

from .gold_filter import ExperienceSample

logger = logging.getLogger(__name__)


def save_jsonl(samples: Iterable[ExperienceSample], output_file: str | Path) -> Path:
    """Serialize ExperienceSample objects to newline-delimited JSON."""
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    count = 0

    try:
        with tmp_path.open("w", encoding="utf-8") as file:
            for sample in samples:
                row = _sample_to_row(sample)
                file.write(json.dumps(row, ensure_ascii=False, sort_keys=True, default=str) + "\n")
                count += 1

        tmp_path.replace(output_path)
        logger.info("Saved %s experience sample(s) to %s.", count, output_path)
        return output_path

    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            logger.debug("Failed to remove temporary JSONL file %s.", tmp_path, exc_info=True)
        logger.exception("Failed to save JSONL export to %s.", output_path)
        raise


def load_jsonl(input_file: str | Path) -> list[dict[str, Any]]:
    """Load JSONL rows from a file, skipping malformed empty lines only."""
    input_path = Path(input_file)
    if not input_path.exists() or not input_path.is_file():
        raise FileNotFoundError(f"JSONL file not found: {input_path}")

    rows: list[dict[str, Any]] = []

    with input_path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            raw = line.strip()
            if not raw:
                continue

            try:
                row = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_number} in {input_path}: {exc}") from exc

            if not isinstance(row, dict):
                raise ValueError(f"Expected JSON object on line {line_number} in {input_path}")

            rows.append(row)

    return rows


def _sample_to_row(sample: ExperienceSample) -> dict[str, Any]:
    required_attrs = ("instruction", "input_text", "output_text", "score", "meta")
    missing = [attr for attr in required_attrs if not hasattr(sample, attr)]
    if missing:
        raise TypeError(f"sample is missing required attribute(s): {', '.join(missing)}")

    return {
        "instruction": str(sample.instruction),
        "input": str(sample.input_text),
        "output": str(sample.output_text),
        "score": float(sample.score),
        "meta": dict(sample.meta) if isinstance(sample.meta, dict) else sample.meta,
    }