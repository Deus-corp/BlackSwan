#!/usr/bin/env python3
"""
Скрипт для подготовки тренировочных данных из памяти.
"""
from __future__ import annotations
import sys
import argparse
from typing import Dict, List
import json

from src.memory.gold_filter import filter_gold_samples
from src.memory.exporter import save_jsonl

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def load_memory_entries(memory_dir: str | Path) -> List[Dict]:
    memory_path = Path(memory_dir)
    entries: List[Dict] = []

    if not memory_path.exists():
        return entries

    for file_path in sorted(memory_path.glob("*.json")):
        try:
            with file_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                entries.append(data)
            elif isinstance(data, list):
                entries.extend([item for item in data if isinstance(item, dict)])
        except Exception:
            continue

    return entries


def main() -> None:
    parser = argparse.ArgumentParser(description="Подготовить тренировочные данные из памяти.")
    parser.add_argument("--memory-dir", required=True, help="Директория с JSON‑файлами памяти")
    parser.add_argument("--output", required=True, help="Выходной JSONL‑файл")
    parser.add_argument("--threshold", type=float, default=0.8, help="Порог gold‑фильтра")
    args = parser.parse_args()

    entries = load_memory_entries(args.memory_dir)
    samples = filter_gold_samples(entries, threshold=args.threshold)
    out = save_jsonl(samples, args.output)

    print(f"loaded_entries={len(entries)}")
    print(f"gold_samples={len(samples)}")
    print(f"saved_to={out}")


if __name__ == "__main__":
    main()