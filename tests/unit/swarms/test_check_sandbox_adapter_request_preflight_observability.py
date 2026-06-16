from tests.unit.swarms.test_check_sandbox_adapter_scaffold_observability import (
    _matrix_record,
    _scaffold_record,
)
from src.testing.build_real_execution_sandbox_adapter_request_preflight import (
    build_real_execution_sandbox_adapter_request_preflight_record,
)
from src.testing.check_sandbox_adapter_request_preflight_observability import (
    _exit_code_for_result,
    _format_result,
    check_sandbox_adapter_request_preflight_observability_from_records,
)

SANDBOX_REQUIRED_FIELDS = [
    "sandbox_id",
    "sandbox_workspace_path",
    "sandbox_policy_id",
    "capability_id",
    "execution_level",
    "allowed_input_paths",
    "allowed_output_paths",
    "network_policy",
    "secret_policy",
    "filesystem_policy",
    "resource_limits",
    "rollback_strategy",
    "evidence_strategy",
]


def _valid_scaffold_record():
    return _scaffold_record(sandbox_required_fields=SANDBOX_REQUIRED_FIELDS)


def _preflight_record(**overrides):
    item = build_real_execution_sandbox_adapter_request_preflight_record(
        _valid_scaffold_record()
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


def test_check_sandbox_adapter_request_preflight_observability_passes_for_fail_closed_preflight() -> None:
    result = check_sandbox_adapter_request_preflight_observability_from_records(
        [_matrix_record(), _valid_scaffold_record(), _preflight_record()],
        proposal_id="proposal-1",
        rendered_command_id="rendered-1",
    )

    assert result["status"] == "passed"
    assert result["failed_checks"] == []
    assert result["sandbox_adapter_request_preflight_observed"] is True
    assert result["sandbox_adapter_request_preflight_records"] == 1
    assert result["sandbox_adapter_request_preflight_linkage_complete"] is True
    assert result["sandbox_adapter_request_preflight_orphans"] == 0
    assert result["sandbox_adapter_request_preflight_blocked"] == 1
    assert result["sandbox_adapter_request_preflight_fail_closed"] == 1
    assert result["sandbox_adapter_request_preflight_deny_by_default"] == 1
    assert result["sandbox_adapter_request_preflight_request_generation_enabled"] == 0
    assert result["sandbox_adapter_request_preflight_workspace_creation_enabled"] == 0
    assert result["sandbox_adapter_request_preflight_input_materialization_enabled"] == 0
    assert result["sandbox_adapter_request_preflight_command_rendering_enabled"] == 0
    assert result["sandbox_adapter_request_preflight_sandbox_execution_enabled"] == 0
    assert result["sandbox_adapter_request_preflight_result_generation_enabled"] == 0
    assert result["sandbox_adapter_request_preflight_execution_performed"] == 0
    assert result["sandbox_adapter_request_preflight_subprocess_invoked"] == 0
    assert result["sandbox_adapter_request_preflight_real_execution_enabled"] == 0
    assert result["sandbox_adapter_request_preflight_external_side_effects_performed"] == 0
    assert result["sandbox_adapter_request_preflight_production_paths_mutated"] == 0
    assert result["sandbox_adapter_request_preflight_production_secrets_accessed"] == 0
    assert (
        result["brief_key_metrics"][
            "security_real_execution_sandbox_adapter_request_preflights"
        ]
        == 1
    )
    assert "Sandbox adapter request preflight observed" in result["brief_summary"]


def test_check_sandbox_adapter_request_preflight_observability_fails_when_preflight_generates_request() -> None:
    result = check_sandbox_adapter_request_preflight_observability_from_records(
        [
            _matrix_record(),
            _valid_scaffold_record(),
            _preflight_record(
                sandbox_adapter_request_generation_enabled=True,
            ),
        ],
        proposal_id="proposal-1",
        rendered_command_id="rendered-1",
    )

    assert result["status"] == "failed"
    assert "sandbox_adapter_request_preflight_does_not_generate_requests" in result[
        "failed_checks"
    ]


def test_check_sandbox_adapter_request_preflight_observability_fails_when_preflight_executes() -> None:
    result = check_sandbox_adapter_request_preflight_observability_from_records(
        [
            _matrix_record(),
            _valid_scaffold_record(),
            _preflight_record(
                sandbox_execution_enabled=True,
                execution_performed=True,
                subprocess_invoked=True,
            ),
        ],
        proposal_id="proposal-1",
        rendered_command_id="rendered-1",
    )

    assert result["status"] == "failed"
    assert "sandbox_adapter_request_preflight_does_not_enable_sandbox_execution" in result[
        "failed_checks"
    ]
    assert "sandbox_adapter_request_preflight_does_not_execute" in result[
        "failed_checks"
    ]
    assert "sandbox_adapter_request_preflight_does_not_invoke_subprocess" in result[
        "failed_checks"
    ]


def test_check_sandbox_adapter_request_preflight_observability_format_and_exit_code() -> None:
    result = check_sandbox_adapter_request_preflight_observability_from_records(
        [_matrix_record(), _valid_scaffold_record(), _preflight_record()],
        proposal_id="proposal-1",
        rendered_command_id="rendered-1",
    )

    text = _format_result(result)

    assert _exit_code_for_result(result) == 0
    assert "Sandbox adapter request preflight observability: status=passed" in text
    assert "observed=true" in text
    assert "request_generation_enabled=0" in text
    assert "workspace_creation_enabled=0" in text
    assert "sandbox_execution_enabled=0" in text
    assert "real_execution_enabled=0" in text