import json
from pathlib import Path

from src.testing.run_explorer_network_read_loop import _write_json_output


def test_write_json_output_writes_clean_result_file(tmp_path: Path) -> None:
    output_path = tmp_path / "nested" / "explorer_result.json"

    result = {
        "type": "explorer_network_read_loop_result",
        "status": "completed",
        "source_plan_enabled": True,
        "total_memory_records_published": 1,
    }

    _write_json_output(str(output_path), result)

    loaded = json.loads(output_path.read_text(encoding="utf-8"))

    assert loaded == result


def test_write_json_output_ignores_empty_path(tmp_path: Path) -> None:
    _write_json_output("", {"ok": True})

    assert list(tmp_path.iterdir()) == []