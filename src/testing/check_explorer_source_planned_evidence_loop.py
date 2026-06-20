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


SAFE_PUBLIC_SEARCH_AUDIT_SAFETY_FLAGS = (
    "external_write_performed",
    "real_execution_enabled",
    "production_paths_mutated",
    "production_secrets_accessed",
)


def _safe_public_search_template_audit(
    result: Mapping[str, Any],
) -> Mapping[str, Any]:
    """Return planning-time safe public search audit when present."""
    audit = result.get("safe_public_search_template_audit")
    if isinstance(audit, Mapping):
        return audit

    source_plan_audit = result.get("source_plan_audit")
    if isinstance(source_plan_audit, Mapping):
        nested = source_plan_audit.get("safe_public_search_template_audit")
        if isinstance(nested, Mapping):
            return nested

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


SAFE_PUBLIC_SEARCH_TELEMETRY_KEYS = {
    "safe_public_search_templates_seen",
    "safe_public_search_templates_selected",
    "safe_public_search_templates_fetched",
    "safe_public_search_templates_blocked",
    "unsafe_public_search_templates_detected",
}


def _validate_safe_public_search_template_telemetry(
    result: Mapping[str, Any],
    errors: list[str],
) -> None:
    """Validate safe public search template telemetry when present."""
    node = _last_node_result(result)
    if not node:
        return

    has_template_telemetry = any(key in node for key in SAFE_PUBLIC_SEARCH_TELEMETRY_KEYS)
    if not has_template_telemetry:
        return

    seen = _safe_int(node.get("safe_public_search_templates_seen"), default=0)
    selected = _safe_int(
        node.get("safe_public_search_templates_selected"),
        default=0,
    )
    fetched = _safe_int(
        node.get("safe_public_search_templates_fetched"),
        default=0,
    )
    blocked = _safe_int(
        node.get("safe_public_search_templates_blocked"),
        default=0,
    )
    unsafe = _safe_int(
        node.get("unsafe_public_search_templates_detected"),
        default=0,
    )

    if unsafe != 0:
        errors.append(
            "unsafe public search templates detected: "
            f"unsafe_public_search_templates_detected={unsafe}"
        )

    if seen <= 0:
        errors.append(
            "safe public search template telemetry is present but no templates were seen"
        )

    if selected > seen:
        errors.append(
            "safe public search templates selected must be <= seen "
            f"(selected={selected}, seen={seen})"
        )

    if fetched > selected:
        errors.append(
            "safe public search templates fetched must be <= selected "
            f"(fetched={fetched}, selected={selected})"
        )

    if blocked > fetched:
        errors.append(
            "safe public search templates blocked must be <= fetched "
            f"(blocked={blocked}, fetched={fetched})"
        )


def _validate_safe_public_search_template_audit_contract(
    result: Mapping[str, Any],
    errors: list[str],
) -> None:
    """Validate planning-time safe public search audit when present.

    Backward-compatible: older runtime JSON without this audit is accepted.
    """
    audit = _safe_public_search_template_audit(result)
    if not audit:
        return

    audit_type = str(audit.get("type") or "").strip()
    if audit_type != "safe_public_search_template_audit":
        errors.append(
            "safe public search template audit has invalid type: "
            f"{audit_type!r}"
        )

    for flag in SAFE_PUBLIC_SEARCH_AUDIT_SAFETY_FLAGS:
        if bool(audit.get(flag)):
            errors.append(
                "safe public search template audit has unsafe flag true: "
                f"{flag}"
            )

    generated_count = _safe_int(audit.get("generated_count"), default=0)
    accepted_count = _safe_int(audit.get("accepted_count"), default=0)
    rejected_count = _safe_int(audit.get("rejected_count"), default=0)
    unsafe_rejected_count = _safe_int(
        audit.get("unsafe_rejected_count"),
        default=0,
    )
    deduped_count = _safe_int(audit.get("deduped_count"), default=0)

    if generated_count < 0:
        errors.append("safe public search audit generated_count must be >= 0")
    if accepted_count < 0:
        errors.append("safe public search audit accepted_count must be >= 0")
    if rejected_count < 0:
        errors.append("safe public search audit rejected_count must be >= 0")
    if unsafe_rejected_count < 0:
        errors.append(
            "safe public search audit unsafe_rejected_count must be >= 0"
        )
    if deduped_count < 0:
        errors.append("safe public search audit deduped_count must be >= 0")

    if generated_count and accepted_count > generated_count:
        errors.append(
            "safe public search audit accepted_count must be <= generated_count "
            f"(accepted_count={accepted_count}, generated_count={generated_count})"
        )

    node = _last_node_result(result)
    runtime_seen = 0
    runtime_unsafe = 0
    search_seen = 0

    if node:
        runtime_seen = _safe_int(
            node.get("safe_public_search_templates_seen"),
            default=0,
        )
        runtime_unsafe = _safe_int(
            node.get("unsafe_public_search_templates_detected"),
            default=0,
        )

        source_adapter_targets_seen = node.get("source_adapter_targets_seen")
        if isinstance(source_adapter_targets_seen, Mapping):
            search_seen = _safe_int(
                source_adapter_targets_seen.get("search"),
                default=0,
            )

    if runtime_unsafe != 0:
        errors.append(
            "unsafe public search templates detected at runtime: "
            f"unsafe_public_search_templates_detected={runtime_unsafe}"
        )

    # If the new audit is present and the runtime saw search/safe-template
    # activity, the planning audit should show accepted safe templates.
    if (runtime_seen > 0 or search_seen > 0) and accepted_count <= 0:
        errors.append(
            "safe public search audit accepted_count must be > 0 when "
            "runtime search template telemetry is present"
        )

    by_site = audit.get("by_site")
    by_kind = audit.get("by_kind")
    queries = audit.get("queries")

    if accepted_count > 0 and not isinstance(by_site, Mapping):
        errors.append("safe public search audit by_site must be a mapping")
    if accepted_count > 0 and not isinstance(by_kind, Mapping):
        errors.append("safe public search audit by_kind must be a mapping")
    if accepted_count > 0 and not isinstance(queries, list):
        errors.append("safe public search audit queries must be a list")


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
    _validate_safe_public_search_template_telemetry(result, errors)
    _validate_safe_public_search_template_audit_contract(result, errors)

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