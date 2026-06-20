from __future__ import annotations

from pathlib import Path

from src.swarms.runtime.cluster_cli import (
    _apply_profile_defaults,
    _build_services,
    build_parser,
)


def _parse_up(*extra: str):
    parser = build_parser()
    return parser.parse_args(["up", *extra])


def test_cluster_cli_profile_explorer_evidence_selects_explorer_only(tmp_path: Path) -> None:
    args = _parse_up(
        "--profile",
        "explorer-evidence",
        "--run-dir",
        str(tmp_path),
    )

    _apply_profile_defaults(args)

    assert args.no_trade is True
    assert args.no_security is True
    assert args.no_security_meta is True
    assert args.no_explorer is False
    assert args.no_explorer_meta is False
    assert args.memory_nodes == 0
    assert args.no_overseer is True
    assert args.execution_enabled is False
    assert args.dry_run is True


def test_cluster_cli_profile_memory_evidence_selects_memory_node(tmp_path: Path) -> None:
    args = _parse_up(
        "--profile",
        "memory-evidence",
        "--run-dir",
        str(tmp_path),
    )

    _apply_profile_defaults(args)

    assert args.no_trade is True
    assert args.no_explorer is True
    assert args.no_explorer_meta is True
    assert args.memory_nodes == 1
    assert args.memory_ingest_since_start is False
    assert args.no_overseer is True


def test_cluster_cli_profile_explorer_memory_evidence_builds_expected_services(
    tmp_path: Path,
) -> None:
    args = _parse_up(
        "--profile",
        "explorer-memory-evidence",
        "--run-dir",
        str(tmp_path),
        "--duration",
        "1",
    )

    _apply_profile_defaults(args)
    services = _build_services(args, tmp_path)

    names = [service.name for service in services]

    assert "explorer-node" in names
    assert "explorer-meta" in names
    assert "memory-1" in names
    assert "security-node" not in names
    assert "security-meta" not in names
    assert "trade-1" not in names
    assert "overseer" not in names


def test_cluster_cli_profile_full_safe_preserves_default_shape(tmp_path: Path) -> None:
    args = _parse_up(
        "--profile",
        "full-safe",
        "--run-dir",
        str(tmp_path),
    )

    _apply_profile_defaults(args)
    services = _build_services(args, tmp_path)

    names = [service.name for service in services]

    assert "trade-1" in names
    assert "security-node" in names
    assert "security-meta" in names
    assert "explorer-node" in names
    assert "explorer-meta" in names
    assert "overseer" in names


def test_cluster_cli_memory_query_hint_parser() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "memory-query",
            "--text-query",
            "agents memory",
            "--limit",
            "3",
            "--json",
        ]
    )

    assert args.command == "memory-query"
    assert args.text_query == "agents memory"
    assert args.limit == 3
    assert args.json is True