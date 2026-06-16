from tests.unit.swarms.test_check_sandbox_materialization_preflight_scaffold_observability import (
    _envelope_record,
    _materialization_record,
    _matrix_record,
    _preflight_record,
    _valid_scaffold_record,
)
from src.testing.build_real_execution_sandbox_workspace_plan_scaffold import (
    build_real_execution_sandbox_workspace_plan_scaffold_record,
)
from src.testing.check_sandbox_workspace_plan_scaffold_observability import (
    _exit_code_for_result,
    _format_result,
    check_sandbox_workspace_plan_scaffold_observability_from_records,
)


def _workspace_plan_record(**overrides):
    item = build_real_execution_sandbox_workspace_plan_scaffold_record(
        _materialization_record()
    )
    item.update(overrides)
    item["payload"] = {
        **dict(item.get("payload") or {}),
        **{
            key: value
            for key, value in overrides.items()
            if key != "payload"
        },
    }
    return item


def test_check_sandbox_workspace_plan_scaffold_observability_passes_for_fail_closed_plan() -> None:
    result = check_sandbox_workspace_plan_scaffold_observability_from_records(
        [
            _matrix_record(),
            _valid_scaffold_record(),
            _preflight_record(),
            _envelope_record(),
            _materialization_record(),
            _workspace_plan_record(),
        ],
        proposal_id="proposal-1",
        rendered_command_id="rendered-1",
    )

    assert result["status"] == "passed"
    assert result["failed_checks"] == []
    assert result["sandbox_workspace_plan_scaffold_observed"] is True
    assert result["sandbox_workspace_plan_scaffold_records"] == 1
    assert result["sandbox_workspace_plan_scaffold_linkage_complete"] is True
    assert result["sandbox_workspace_plan_scaffold_orphans"] == 0
    assert result["sandbox_workspace_plan_scaffold_blocked"] == 1
    assert result["sandbox_workspace_plan_scaffold_fail_closed"] == 1
    assert result["sandbox_workspace_plan_scaffold_deny_by_default"] == 1
    assert result["sandbox_workspace_plan_scaffold_plan_generation_enabled"] == 0
    assert result["sandbox_workspace_plan_scaffold_plan_materialized"] == 0
    assert result["sandbox_workspace_plan_scaffold_plan_executable"] == 0
    assert result["sandbox_workspace_plan_scaffold_directory_creation_enabled"] == 0
    assert result["sandbox_workspace_plan_scaffold_workspace_created"] == 0
    assert result["sandbox_workspace_plan_scaffold_cleanup_registered"] == 0
    assert (
        result["sandbox_workspace_plan_scaffold_materialization_preflight_enabled"]
        == 0
    )
    assert (
        result["sandbox_workspace_plan_scaffold_materialization_preflight_passed"]
        == 0
    )
    assert result["sandbox_workspace_plan_scaffold_workspace_creation_enabled"] == 0
    assert result["sandbox_workspace_plan_scaffold_input_materialization_enabled"] == 0
    assert result["sandbox_workspace_plan_scaffold_sandbox_execution_enabled"] == 0
    assert result["sandbox_workspace_plan_scaffold_execution_performed"] == 0
    assert result["sandbox_workspace_plan_scaffold_subprocess_invoked"] == 0
    assert result["sandbox_workspace_plan_scaffold_real_execution_enabled"] == 0
    assert (
        result["brief_key_metrics"][
            "security_real_execution_sandbox_workspace_plan_scaffolds"
        ]
        == 1
    )
    assert "Sandbox workspace plan scaffold observed" in result["brief_summary"]


def test_check_sandbox_workspace_plan_scaffold_observability_fails_when_plan_generation_enabled() -> None:
    result = check_sandbox_workspace_plan_scaffold_observability_from_records(
        [
            _matrix_record(),
            _valid_scaffold_record(),
            _preflight_record(),
            _envelope_record(),
            _materialization_record(),
            _workspace_plan_record(
                sandbox_workspace_plan_generation_enabled=True,
            ),
        ],
        proposal_id="proposal-1",
        rendered_command_id="rendered-1",
    )

    assert result["status"] == "failed"
    assert "sandbox_workspace_plan_scaffold_does_not_generate_plan" in result[
        "failed_checks"
    ]


def test_check_sandbox_workspace_plan_scaffold_observability_fails_when_plan_executable() -> None:
    result = check_sandbox_workspace_plan_scaffold_observability_from_records(
        [
            _matrix_record(),
            _valid_scaffold_record(),
            _preflight_record(),
            _envelope_record(),
            _materialization_record(),
            _workspace_plan_record(
                sandbox_workspace_plan_executable=True,
            ),
        ],
        proposal_id="proposal-1",
        rendered_command_id="rendered-1",
    )

    assert result["status"] == "failed"
    assert "sandbox_workspace_plan_scaffold_plan_not_executable" in result[
        "failed_checks"
    ]


def test_check_sandbox_workspace_plan_scaffold_observability_fails_when_workspace_created() -> None:
    result = check_sandbox_workspace_plan_scaffold_observability_from_records(
        [
            _matrix_record(),
            _valid_scaffold_record(),
            _preflight_record(),
            _envelope_record(),
            _materialization_record(),
            _workspace_plan_record(
                sandbox_workspace_created=True,
            ),
        ],
        proposal_id="proposal-1",
        rendered_command_id="rendered-1",
    )

    assert result["status"] == "failed"
    assert "sandbox_workspace_plan_scaffold_does_not_create_workspace" in result[
        "failed_checks"
    ]


def test_check_sandbox_workspace_plan_scaffold_observability_fails_when_executes() -> None:
    result = check_sandbox_workspace_plan_scaffold_observability_from_records(
        [
            _matrix_record(),
            _valid_scaffold_record(),
            _preflight_record(),
            _envelope_record(),
            _materialization_record(),
            _workspace_plan_record(
                sandbox_execution_enabled=True,
                execution_performed=True,
                subprocess_invoked=True,
            ),
        ],
        proposal_id="proposal-1",
        rendered_command_id="rendered-1",
    )

    assert result["status"] == "failed"
    assert "sandbox_workspace_plan_scaffold_does_not_enable_sandbox_execution" in result[
        "failed_checks"
    ]
    assert "sandbox_workspace_plan_scaffold_does_not_execute" in result[
        "failed_checks"
    ]
    assert "sandbox_workspace_plan_scaffold_does_not_invoke_subprocess" in result[
        "failed_checks"
    ]


def test_check_sandbox_workspace_plan_scaffold_observability_format_and_exit_code() -> None:
    result = check_sandbox_workspace_plan_scaffold_observability_from_records(
        [
            _matrix_record(),
            _valid_scaffold_record(),
            _preflight_record(),
            _envelope_record(),
            _materialization_record(),
            _workspace_plan_record(),
        ],
        proposal_id="proposal-1",
        rendered_command_id="rendered-1",
    )

    text = _format_result(result)

    assert _exit_code_for_result(result) == 0
    assert "Sandbox workspace plan scaffold observability: status=passed" in text
    assert "observed=true" in text
    assert "plan_generation_enabled=0" in text
    assert "plan_executable=0" in text
    assert "workspace_created=0" in text
    assert "sandbox_execution_enabled=0" in text
    assert "real_execution_enabled=0" in text