from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping


MIN_MEMORY_RECORDS_PUBLISHED = 5
MIN_TARGETS_PUBLISHED = 20
MIN_FINDINGS_EMITTED = 5
MIN_EVIDENCE_TARGETS_SEEN = 5
MIN_EVIDENCE_TARGETS_SELECTED = 5

SAFE_RATE_LIMIT_REASONS = {
    "robots_disallowed",
    "domain_window_rate_limited",
    "http_429",
    "policy_blocked",
}


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _ticks(result: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw_ticks = result.get("ticks")
    if not isinstance(raw_ticks, list):
        raw_ticks = result.get("tick_results")

    return [
        tick
        for tick in _as_list(raw_ticks)
        if isinstance(tick, Mapping)
    ]


def _last_node_result(result: Mapping[str, Any]) -> Mapping[str, Any]:
    direct_node = _as_mapping(result.get("node"))
    if direct_node:
        return direct_node

    for tick in reversed(_ticks(result)):
        node = _as_mapping(tick.get("node"))
        if node:
            return node

    return {}


def _total_or_sum(
    result: Mapping[str, Any],
    *,
    total_key: str,
    tick_key: str,
) -> int:
    if total_key in result:
        return _safe_int(result.get(total_key), default=0)

    return sum(_safe_int(tick.get(tick_key), default=0) for tick in _ticks(result))


def _validate_safe_flags(
    result: Mapping[str, Any],
    errors: list[str],
) -> None:
    unsafe_flags = [
        "external_write_performed",
        "real_execution_enabled",
        "production_paths_mutated",
        "production_secrets_accessed",
    ]

    for flag in unsafe_flags:
        if bool(result.get(flag, False)):
            errors.append(f"unsafe top-level flag is true: {flag}")

    for index, tick in enumerate(_ticks(result), start=1):
        for flag in unsafe_flags:
            if bool(tick.get(flag, False)):
                errors.append(f"unsafe tick {index} flag is true: {flag}")

        node = _as_mapping(tick.get("node"))
        for flag in ("external_write_performed", "real_execution_enabled"):
            if bool(node.get(flag, False)):
                errors.append(f"unsafe tick {index} node flag is true: {flag}")


def _validate_tick_completion(
    result: Mapping[str, Any],
    errors: list[str],
) -> None:
    ticks_requested = result.get("ticks_requested")
    ticks_completed = result.get("ticks_completed")

    if ticks_requested is not None and ticks_completed is not None:
        requested = _safe_int(ticks_requested, default=-1)
        completed = _safe_int(ticks_completed, default=-2)

        if requested != completed:
            errors.append(
                "ticks_completed must equal ticks_requested "
                f"(completed={completed}, requested={requested})"
            )

    if "ticks" in result and not _ticks(result):
        errors.append("ticks array is present but empty or malformed")


def _validate_evidence_yield(
    result: Mapping[str, Any],
    errors: list[str],
) -> None:
    memory_records = _total_or_sum(
        result,
        total_key="total_memory_records_published",
        tick_key="memory_records_published",
    )
    targets_published = _total_or_sum(
        result,
        total_key="total_targets_published",
        tick_key="targets_published",
    )
    findings_emitted = _total_or_sum(
        result,
        total_key="total_findings_emitted",
        tick_key="findings_emitted",
    )

    if memory_records < MIN_MEMORY_RECORDS_PUBLISHED:
        errors.append(
            "insufficient memory evidence yield: "
            f"total_memory_records_published={memory_records}, "
            f"minimum={MIN_MEMORY_RECORDS_PUBLISHED}"
        )

    if targets_published < MIN_TARGETS_PUBLISHED:
        errors.append(
            "insufficient target publication yield: "
            f"total_targets_published={targets_published}, "
            f"minimum={MIN_TARGETS_PUBLISHED}"
        )

    if findings_emitted < MIN_FINDINGS_EMITTED:
        errors.append(
            "insufficient finding yield: "
            f"total_findings_emitted={findings_emitted}, "
            f"minimum={MIN_FINDINGS_EMITTED}"
        )

    node = _last_node_result(result)
    if not node:
        errors.append("missing node result for evidence target counters")
        return

    seen = _as_mapping(node.get("source_adapter_targets_seen"))
    selected = _as_mapping(node.get("source_adapter_targets_selected"))

    if "evidence" not in seen:
        errors.append("missing node.source_adapter_targets_seen.evidence")
    if "evidence" not in selected:
        errors.append("missing node.source_adapter_targets_selected.evidence")

    evidence_seen = _safe_int(seen.get("evidence"), default=0)
    evidence_selected = _safe_int(selected.get("evidence"), default=0)

    if evidence_seen < MIN_EVIDENCE_TARGETS_SEEN:
        errors.append(
            "insufficient evidence targets seen: "
            f"seen={evidence_seen}, minimum={MIN_EVIDENCE_TARGETS_SEEN}"
        )

    if evidence_selected < MIN_EVIDENCE_TARGETS_SELECTED:
        errors.append(
            "insufficient evidence targets selected: "
            f"selected={evidence_selected}, minimum={MIN_EVIDENCE_TARGETS_SELECTED}"
        )

    if evidence_seen < evidence_selected:
        errors.append(
            "evidence targets seen must be >= selected "
            f"(seen={evidence_seen}, selected={evidence_selected})"
        )


def _validate_rate_limit_telemetry(
    result: Mapping[str, Any],
    errors: list[str],
) -> None:
    nodes: list[Mapping[str, Any]] = []

    top_node = _as_mapping(result.get("node"))
    if top_node:
        nodes.append(top_node)

    for tick in _ticks(result):
        node = _as_mapping(tick.get("node"))
        if node:
            nodes.append(node)

    for node_index, node in enumerate(nodes, start=1):
        rate_limits = _as_mapping(node.get("source_adapter_rate_limits"))

        for key in rate_limits:
            reason = str(key).rsplit(":", 1)[-1]
            if reason not in SAFE_RATE_LIMIT_REASONS:
                errors.append(
                    "unsafe or unknown source adapter rate-limit reason: "
                    f"node_index={node_index}, key={key!r}, reason={reason!r}"
                )


def validate_explorer_source_planned_evidence_loop(
    result: Mapping[str, Any],
) -> list[str]:
    """Return contract validation errors for explorer source-planned loop output."""
    errors: list[str] = []

    if result.get("type") != "explorer_network_read_loop_result":
        errors.append(
            "unexpected result type: "
            f"{result.get('type')!r}, expected 'explorer_network_read_loop_result'"
        )

    if str(result.get("status") or "completed") not in {"completed", "ok"}:
        errors.append(f"unexpected result status: {result.get('status')!r}")

    _validate_tick_completion(result, errors)
    _validate_safe_flags(result, errors)
    _validate_evidence_yield(result, errors)
    _validate_rate_limit_telemetry(result, errors)

    return errors


def assert_explorer_source_planned_evidence_loop(
    result: Mapping[str, Any],
) -> None:
    errors = validate_explorer_source_planned_evidence_loop(result)
    if errors:
        details = "\n".join(f"- {error}" for error in errors)
        raise AssertionError(
            "explorer source-planned evidence loop contract failed:\n"
            f"{details}"
        )


def validate_source_planned_evidence_loop(
    result: Mapping[str, Any],
) -> list[str]:
    """Backward-compatible legacy validator for older unit tests/imports.

    The enriched checker validates evidence-yield KPIs. This legacy entry point
    preserves the older lightweight contract used by existing unit tests.
    """
    errors: list[str] = []

    if bool(result.get("external_write_performed", False)):
        errors.append("external writes are not allowed")

    if bool(result.get("real_execution_enabled", False)):
        errors.append("real execution must remain disabled")

    if bool(result.get("production_paths_mutated", False)):
        errors.append("production paths must not be mutated")

    if bool(result.get("production_secrets_accessed", False)):
        errors.append("production secrets must not be accessed")

    ticks = _ticks(result)
    if not ticks:
        errors.append("missing tick results")
        return errors

    memory_records = _total_or_sum(
        result,
        total_key="total_memory_records_published",
        tick_key="memory_records_published",
    )
    if memory_records <= 0:
        errors.append("at least one memory_record must be published")

    evidence_selected = 0
    evidence_seen = 0

    for tick in ticks:
        node = _as_mapping(tick.get("node"))
        selected = _as_mapping(node.get("source_adapter_targets_selected"))
        seen = _as_mapping(node.get("source_adapter_targets_seen"))

        evidence_selected = max(
            evidence_selected,
            _safe_int(selected.get("evidence"), default=0),
        )
        evidence_seen = max(
            evidence_seen,
            _safe_int(seen.get("evidence"), default=0),
        )

    if evidence_selected <= 0:
        errors.append("must select at least one evidence target")

    if evidence_seen and evidence_seen < evidence_selected:
        errors.append(
            "evidence targets seen must be >= selected "
            f"(seen={evidence_seen}, selected={evidence_selected})"
        )

    return errors


def assert_source_planned_evidence_loop(
    result: Mapping[str, Any],
) -> None:
    """Backward-compatible legacy assertion for older unit tests/imports."""
    errors = validate_source_planned_evidence_loop(result)
    if errors:
        details = "\n".join(f"- {error}" for error in errors)
        raise AssertionError(
            "source-planned evidence loop contract failed:\n"
            f"{details}"
        )


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if len(argv) != 1:
        print(
            "Usage: python -m src.testing.check_explorer_source_planned_evidence_loop "
            "<result.json>",
            file=sys.stderr,
        )
        return 2

    path = Path(argv[0])
    result = json.loads(path.read_text(encoding="utf-8"))

    try:
        assert_explorer_source_planned_evidence_loop(result)
    except AssertionError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print("✅ explorer source-planned evidence loop contract OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())