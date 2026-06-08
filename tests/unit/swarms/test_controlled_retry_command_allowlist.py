import pytest

from src.testing.controlled_retry_command_allowlist import (
    ALLOWED_MODULE,
    parse_controlled_retry_command,
)


def _command(**overrides):
    values = {
        "scenario_id": "replay-controlled-1",
        "directive_id": "runtime-run-controlled-1",
        "timeout_profile": "standard",
        "db_path": "data/cluster_runtime/latest/ledgers/swarm_crdt.local.db",
        "module": ALLOWED_MODULE,
        "python": "python",
    }
    values.update(overrides)
    return (
        f"{values['python']} -m {values['module']} "
        f"--scenario-id {values['scenario_id']} "
        "--action REDUCE_RISK "
        f"--directive-id {values['directive_id']} "
        f"--timeout-profile {values['timeout_profile']} "
        f"--db-path {values['db_path']}"
    )


def test_parse_controlled_retry_command_accepts_allowlisted_command() -> None:
    result = parse_controlled_retry_command(_command())

    assert result["valid"] is True
    assert result["allowlist_matched"] is True
    assert result["module"] == ALLOWED_MODULE
    assert result["args"]["scenario_id"] == "replay-controlled-1"
    assert result["args"]["directive_id"] == "runtime-run-controlled-1"
    assert result["args"]["timeout_profile"] == "standard"
    assert result["execution_performed"] is False
    assert result["reasons"] == []


def test_parse_controlled_retry_command_accepts_python3() -> None:
    result = parse_controlled_retry_command(_command(python="python3"))

    assert result["valid"] is True
    assert result["allowlist_matched"] is True


def test_parse_controlled_retry_command_rejects_unknown_module() -> None:
    result = parse_controlled_retry_command(
        _command(module="src.testing.other_module")
    )

    assert result["valid"] is False
    assert result["allowlist_matched"] is False
    assert "module_not_allowlisted" in result["reasons"]


def test_parse_controlled_retry_command_rejects_shell_chaining() -> None:
    result = parse_controlled_retry_command(_command() + " && echo pwned")

    assert result["valid"] is False
    assert result["allowlist_matched"] is False
    assert "forbidden_token:&&" in result["reasons"]


def test_parse_controlled_retry_command_rejects_shell_redirection() -> None:
    result = parse_controlled_retry_command(_command() + " > /tmp/out")

    assert result["valid"] is False
    assert "forbidden_token:>" in result["reasons"]


def test_parse_controlled_retry_command_rejects_missing_required_flags() -> None:
    result = parse_controlled_retry_command(
        "python -m src.testing.run_replay_evidence_check --timeout-profile standard"
    )

    assert result["valid"] is False
    assert "missing_scenario_id" in result["reasons"]
    assert "missing_directive_id" in result["reasons"]


def test_parse_controlled_retry_command_rejects_invalid_timeout_profile() -> None:
    result = parse_controlled_retry_command(_command(timeout_profile="fast"))

    assert result["valid"] is False
    assert "invalid_timeout_profile" in result["reasons"]


def test_parse_controlled_retry_command_rejects_unknown_flag() -> None:
    result = parse_controlled_retry_command(_command() + " --unsafe true")

    assert result["valid"] is False
    assert "unknown_flag:--unsafe" in result["reasons"]


def test_parse_controlled_retry_command_rejects_unsafe_db_path() -> None:
    result = parse_controlled_retry_command(_command(db_path="../secret.db"))

    assert result["valid"] is False
    assert "unsafe_db_path" in result["reasons"]


def test_parse_controlled_retry_command_rejects_empty_command() -> None:
    result = parse_controlled_retry_command("")

    assert result["valid"] is False
    assert result["allowlist_matched"] is False
    assert result["reasons"] == ["missing_command"]
