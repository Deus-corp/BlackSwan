"""Check Explorer source-planned evidence loop runtime result.

This checker validates the useful read-only Explorer path:

research goal
  -> deterministic source plan
  -> evidence candidates
  -> network_read findings
  -> USEFUL classification
  -> memory_record

It does not perform network I/O by itself. It validates a JSON result emitted by
`src.testing.run_explorer_network_read_loop`.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping


def _load_json(path: Path) -> Mapping[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise AssertionError("Explorer runtime result must be a JSON object.")
    return data


def _source_adapter_selected_count(result: Mapping[str, Any], adapter: str) -> int:
    ticks = result.get("tick_results")
    if not isinstance(ticks, list):
        return 0

    total = 0
    for item in ticks:
        if not isinstance(item, Mapping):
            continue
        node = item.get("node")
        if not isinstance(node, Mapping):
            continue
        selected = node.get("source_adapter_targets_selected")
        if not isinstance(selected, Mapping):
            continue
        total += int(selected.get(adapter, 0) or 0)

    return total


def _source_adapter_seen_count(result: Mapping[str, Any], adapter: str) -> int:
    ticks = result.get("tick_results")
    if not isinstance(ticks, list):
        return 0

    total = 0
    for item in ticks:
        if not isinstance(item, Mapping):
            continue
        node = item.get("node")
        if not isinstance(node, Mapping):
            continue
        seen = node.get("source_adapter_targets_seen")
        if not isinstance(seen, Mapping):
            continue
        total += int(seen.get(adapter, 0) or 0)

    return total


def assert_source_planned_evidence_loop(result: Mapping[str, Any]) -> None:
    if result.get("type") != "explorer_network_read_loop_result":
        raise AssertionError("Expected explorer_network_read_loop_result.")

    if result.get("status") != "completed":
        raise AssertionError("Explorer runtime result must be completed.")

    if not bool(result.get("source_plan_enabled")):
        raise AssertionError("source_plan_enabled must be true.")

    source_plan = result.get("source_plan")
    if not isinstance(source_plan, Mapping):
        raise AssertionError("source_plan must be present.")

    if source_plan.get("type") != "explorer_research_source_plan":
        raise AssertionError("source_plan.type must be explorer_research_source_plan.")

    if source_plan.get("execution_risk_tier") != "network_read":
        raise AssertionError("source_plan must stay in network_read tier.")

    if source_plan.get("external_write_performed") is not False:
        raise AssertionError("source_plan must not perform external writes.")

    if source_plan.get("real_execution_enabled") is not False:
        raise AssertionError("source_plan must not enable real execution.")

    source_plan_targets = result.get("source_plan_targets")
    if not isinstance(source_plan_targets, list) or not source_plan_targets:
        raise AssertionError("source_plan_targets must be non-empty.")

    evidence_targets = [
        target
        for target in source_plan_targets
        if isinstance(target, Mapping)
        and target.get("source_adapter") == "evidence"
        and target.get("preferred_evidence_target") is True
    ]
    if not evidence_targets:
        raise AssertionError(
            "source_plan_targets must include preferred evidence candidates."
        )

    evidence_seen = _source_adapter_seen_count(result, "evidence")
    evidence_selected = _source_adapter_selected_count(result, "evidence")

    if evidence_seen < 1:
        raise AssertionError("Explorer node must see at least one evidence target.")

    if evidence_selected < 1:
        raise AssertionError("Explorer node must select at least one evidence target.")

    total_findings = int(result.get("total_findings_emitted", 0) or 0)
    if total_findings < 1:
        raise AssertionError("Explorer node must emit at least one finding.")

    total_memory_records = int(result.get("total_memory_records_published", 0) or 0)
    if total_memory_records < 1:
        raise AssertionError(
            "Explorer source-planned evidence loop must publish memory_record."
        )

    if result.get("external_write_performed") is not False:
        raise AssertionError("Explorer runtime must not perform external writes.")

    if result.get("real_execution_enabled") is not False:
        raise AssertionError("Explorer runtime must not enable real execution.")

    if result.get("production_paths_mutated") is not False:
        raise AssertionError("Explorer runtime must not mutate production paths.")

    if result.get("production_secrets_accessed") is not False:
        raise AssertionError("Explorer runtime must not access production secrets.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate Explorer source-planned evidence runtime JSON."
    )
    parser.add_argument(
        "result_json",
        type=Path,
        help="Path to JSON emitted by run_explorer_network_read_loop --json.",
    )
    args = parser.parse_args()

    result = _load_json(args.result_json)
    assert_source_planned_evidence_loop(result)
    print("✅ explorer source-planned evidence loop contract OK")


if __name__ == "__main__":
    main()