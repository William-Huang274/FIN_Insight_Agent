from __future__ import annotations

import importlib.util
import io
import json
import copy
import sys
import threading
import uuid
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
HOST_PATH = (
    ROOT
    / "scripts"
    / "qualification"
    / "agent_server_rc_s3_107"
    / "qualify_live_remote_create_lifecycle.py"
)
PHASE_PATH = HOST_PATH.with_name("live_killpoint_phase.py")
CLIENT_TEST_SUPPORT_PATH = ROOT / "tests" / "test_dell_agent_server_client.py"
OVERLAY_PATH = (
    ROOT
    / "deploy"
    / "dell_agent_server"
    / "compose.zero-model-rc-s3-107-qualification.yaml"
)


def _load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def host() -> ModuleType:
    return _load(HOST_PATH, "rc_s3_107_host")


@pytest.fixture(scope="module")
def phase() -> ModuleType:
    return _load(PHASE_PATH, "rc_s3_107_phase")


@pytest.fixture(scope="module")
def client_support() -> ModuleType:
    return _load(CLIENT_TEST_SUPPORT_PATH, "rc_s3_107_client_test_support")


def _manifest(host: ModuleType) -> dict[str, Any]:
    return host._manifest(
        attempt_id="rc-s3-107-a1-20260904t000000z",
        project="finsight-dell-qualification-rc-s3-107-20260904-000000",
        port=18131,
        commit="a" * 40,
        catalog_hash="b" * 64,
    )


def _valid_receipt(
    host: ModuleType,
    manifest: dict[str, Any],
    scenario_id: str,
) -> dict[str, Any]:
    contract = next(
        item for item in host.scenario_contracts() if item.scenario_id == scenario_id
    )
    rule = host.SCENARIO_RULES[scenario_id]
    identity_rows = manifest["scenario_identities"][scenario_id]
    invocations: list[dict[str, Any]] = []
    lifecycle_event_rows = 0
    final_bindings = 0
    for identity, invocation_rule in zip(identity_rows, rule["invocations"]):
        (
            role,
            lifecycle,
            action,
            recovery,
            final_binding_count,
            sdk_create_attempts,
        ) = invocation_rule
        (
            recovery_status,
            disposition_status,
            canonical_decision,
            owner_visible,
            resolved,
        ) = recovery
        remote_status = "success" if sdk_create_attempts == 1 else None
        if scenario_id == "K5" and role == "unresolved_orphan_restart":
            remote_status = "error"
        invocations.append(
            {
                "invocation_id": identity["invocation_id"],
                "role": role,
                "lifecycle": list(lifecycle),
                "canonical_action_outcome": action,
                "recovery": {
                    "status": recovery_status,
                    "recovery_disposition_status": disposition_status,
                    "canonical_recovery_decision": canonical_decision,
                    "owner_visible": owner_visible,
                    "resolved": resolved,
                    "automatic_second_create_attempted": False,
                },
                "final_binding_count": final_binding_count,
                "sdk_create_attempts": sdk_create_attempts,
                "remote_run_status": remote_status,
                "remote_run_id": (
                    str(uuid.uuid5(uuid.NAMESPACE_URL, identity["invocation_id"]))
                    if sdk_create_attempts == 1
                    else None
                ),
            }
        )
        lifecycle_event_rows += len(lifecycle)
        final_bindings += final_binding_count
    return {
        "schema_version": "fin.rc_s3_107.scenario_receipt.v1",
        "attempt_id": manifest["attempt_id"],
        "project": manifest["project"],
        "scenario_id": scenario_id,
        "status": "PASS",
        "execution_boundary": dict(host.EXECUTION_BOUNDARY),
        "identity": {
            "attempt_id": manifest["attempt_id"],
            "project": manifest["project"],
            "scenario_id": scenario_id,
            "invocation_ids": [row["invocation_id"] for row in identity_rows],
            "cross_scenario_identity_collision_count": 0,
        },
        "counts": {
            "sdk_create_attempts": contract.expected_sdk_create_calls,
            "remote_committed_runs": contract.expected_remote_runs,
            "durable_invocations": contract.expected_invocation_count,
            "lifecycle_event_rows": lifecycle_event_rows,
            "final_bindings": final_bindings,
        },
        "observation_sources": dict(host.OBSERVATION_SOURCES),
        "invocations": invocations,
        "proof": dict(rule["proof"]),
    }


def test_matrix_is_bounded_k0_through_k6(host: ModuleType) -> None:
    scenarios = host.scenario_contracts()
    assert tuple(item.scenario_id for item in scenarios) == (
        "K0",
        "K1",
        "K2",
        "K3",
        "K4",
        "K5",
        "K6",
    )
    assert all(item.expected_sdk_create_calls in (0, 1, 2) for item in scenarios)
    assert all(item.expected_remote_runs in (0, 1, 2) for item in scenarios)
    assert scenarios[1].expected_sdk_create_calls == 0
    assert scenarios[1].expected_remote_runs == 0
    assert scenarios[5].expected_sdk_create_calls == 2
    assert scenarios[5].expected_remote_runs == 2
    assert scenarios[5].expected_invocation_count == 2


def test_claim_does_not_overstate_provider_exactly_once(host: ModuleType) -> None:
    manifest = _manifest(host)
    claim = manifest["claim_boundary"]
    assert claim["local"] == "at_most_one_sdk_create_attempt_per_durable_invocation"
    assert claim["remote"] == "one_observed_committed_run_in_tested_single_host_topology"
    assert claim["excluded"] == "provider_or_network_exactly_once"
    assert manifest["constraints"]["automatic_second_attempt"] is False
    assert manifest["constraints"]["external_research_or_model_calls"] is False
    assert manifest["constraints"]["provider_model_calls"] is False
    assert manifest["constraints"]["langsmith_observability_egress"] is True
    assert manifest["constraints"]["trace_content_in_receipt"] is False


def test_all_scenarios_are_ready_after_postgres_gate(host: ModuleType) -> None:
    assert host.incomplete_scenario_blockers() == ()
    assert all(item.implementation_state == "ready" for item in host.SCENARIOS)
    assert all(item.blocker_code is None for item in host.SCENARIOS)
    assert host._assert_phase_implementation_complete() is None


def test_static_preflight_blocks_before_docker_or_attempt(
    host: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []

    monkeypatch.setattr(host, "_assert_required_files", lambda: calls.append("files"))
    monkeypatch.setattr(host, "_assert_zero_model_surface", lambda: calls.append("model"))
    monkeypatch.setattr(
        host, "_assert_repo_state", lambda: calls.append("repo") or "c" * 40
    )
    monkeypatch.setattr(
        host, "_assert_catalog_ready", lambda: calls.append("catalog") or "d" * 64
    )

    def blocked() -> None:
        calls.append("matrix")
        raise host.QualificationError("rc_s3_107_live_matrix_incomplete")

    monkeypatch.setattr(host, "_assert_phase_implementation_complete", blocked)
    monkeypatch.setattr(
        host,
        "runtime_preflight",
        lambda *args, **kwargs: pytest.fail("Docker preflight must not run"),
    )
    monkeypatch.setattr(
        host,
        "_write_json_exclusive",
        lambda *args, **kwargs: pytest.fail("attempt directory must not be created"),
    )

    args = type(
        "Args",
        (),
        {"api_port": 18131, "artifact_root": Path("unused-artifacts")},
    )()
    with pytest.raises(host.QualificationError) as raised:
        host._run_live(args)
    assert raised.value.code == "rc_s3_107_live_matrix_incomplete"
    assert calls == ["files", "model", "repo", "catalog", "matrix"]


def test_catalog_placeholder_is_fail_closed(host: ModuleType, tmp_path: Path) -> None:
    sql = tmp_path / "catalog.sql"
    sql.write_text(host.CATALOG_PLACEHOLDER, encoding="utf-8")
    with pytest.raises(host.QualificationError) as raised:
        host._catalog_literal(sql)
    assert raised.value.code == "rc_s3_107_catalog_hash_unresolved"


def test_catalog_preflight_reads_only_v1_1_assignment(
    host: ModuleType, tmp_path: Path
) -> None:
    sql = tmp_path / "catalog.sh"
    sql.write_text(
        "expected_other_sha256=" + "a" * 64 + "\n"
        "expected_v1_1_catalog_sha256=" + "b" * 64 + "\n",
        encoding="utf-8",
    )
    assert host._catalog_literal(sql) == "b" * 64


@pytest.mark.parametrize(
    "payload,code",
    [
        ({"api_key": "present"}, "rc_s3_107_receipt_forbidden_key"),
        ({"message": "Bearer abcdefghijklmnop"}, "rc_s3_107_receipt_secret_like_value"),
        ({"path": r"D:\\private\\artifact"}, "rc_s3_107_receipt_host_path"),
        ({"raw_payload_hash": "x"}, "rc_s3_107_receipt_forbidden_key"),
    ],
)
def test_receipts_reject_sensitive_surfaces(
    host: ModuleType, payload: dict[str, Any], code: str
) -> None:
    with pytest.raises(host.QualificationError) as raised:
        host._validate_sanitized(payload)
    assert raised.value.code == code


def test_jsonl_parser_accepts_only_sanitized_objects(host: ModuleType) -> None:
    records = host._parse_jsonl(
        json.dumps(
            {
                "schema_version": "fin.rc_s3_107.killpoint_observation.v1",
                "scenario_id": "K0",
                "milestone": "final",
                "sdk_create_calls": 1,
                "remote_run_count": 1,
            }
        ),
        "K0",
    )
    assert records[0]["remote_run_count"] == 1
    with pytest.raises(host.QualificationError) as raised:
        host._parse_jsonl("not-json", "K0")
    assert raised.value.code == "rc_s3_107_phase_non_json_output"


def test_pending_killpoint_occurs_after_durable_begin(
    phase: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[Any] = []

    class Repo:
        def begin_run_create(self, value: str) -> str:
            events.append(("begin", value))
            return "PENDING"

    monkeypatch.setattr(
        phase, "emit_observation", lambda item: events.append(("emit", item.milestone))
    )

    def fake_exit(code: int) -> None:
        events.append(("exit", code))
        raise RuntimeError("expected-hard-exit")

    wrapped = phase.CrashAfterPendingRepository(
        Repo(),
        hard_exit=fake_exit,
        attempt_id="attempt-1",
        project="project-1",
    )
    with pytest.raises(RuntimeError, match="expected-hard-exit"):
        wrapped.begin_run_create("invocation")
    assert events == [
        ("begin", "invocation"),
        ("emit", "pending_committed_before_dispatch"),
        ("exit", 91),
    ]


def test_header_killpoint_runs_official_callback_before_exit(
    phase: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[Any] = []

    class Runs:
        def create(self, **kwargs: Any) -> dict[str, str]:
            events.append("remote-create")
            kwargs["on_run_created"]({"run_id": "remote-1"})
            pytest.fail("the wrapped callback must hard-exit")

    monkeypatch.setattr(
        phase, "emit_observation", lambda item: events.append(("emit", item.milestone))
    )

    def official_callback(run: Any) -> None:
        events.append(("official-callback", run["run_id"]))

    def fake_exit(code: int) -> None:
        events.append(("exit", code))
        raise RuntimeError("expected-hard-exit")

    wrapped = phase.HeaderObservedCrashRuns(
        Runs(),
        hard_exit=fake_exit,
        attempt_id="attempt-1",
        project="project-1",
    )
    with pytest.raises(RuntimeError, match="expected-hard-exit"):
        wrapped.create(on_run_created=official_callback)
    assert events == [
        "remote-create",
        ("official-callback", "remote-1"),
        ("emit", "orphan_with_run_id_committed_body_unread"),
        ("exit", 92),
    ]
    assert wrapped.create_calls == 1


def test_delayed_visibility_is_bounded_and_never_recreates(phase: ModuleType) -> None:
    class Runs:
        def __init__(self) -> None:
            self.created = 0
            self.listed = 0

        def create(self, **kwargs: Any) -> dict[str, str]:
            self.created += 1
            assert "on_run_created" not in kwargs
            return {"run_id": "remote-1"}

        def list(self, **kwargs: Any) -> list[dict[str, str]]:
            self.listed += 1
            return [{"run_id": "remote-1"}]

    delegate = Runs()
    wrapped = phase.DelayedVisibilityRuns(delegate, hidden_exact_scans=2)
    with pytest.raises(phase.ResponseBodyLost):
        wrapped.create(on_run_created=lambda run: None)
    assert wrapped.list(metadata={"invocation_id": "i"}) == []
    assert wrapped.list(metadata={"invocation_id": "i"}) == []
    assert wrapped.list(metadata={"invocation_id": "i"}) == [
        {"run_id": "remote-1"}
    ]
    assert wrapped.create_calls == 1
    assert delegate.created == 1
    assert delegate.listed == 1


def test_k4_contract_requires_owner_decision_before_exact_bind(host: ModuleType) -> None:
    manifest = _manifest(host)
    receipt = _valid_receipt(host, manifest, "K4")
    invocation = receipt["invocations"][0]
    assert invocation["lifecycle"] == [
        "PENDING",
        "DISPATCHED",
        "ORPHAN",
        "ORPHAN",
        "RECONCILED",
    ]
    assert invocation["canonical_action_outcome"] == "AMBIGUOUS_AFTER_DISPATCH"
    assert invocation["recovery"] == {
        "status": "RECOVERY_REQUIRED",
        "recovery_disposition_status": "RECORDED",
        "canonical_recovery_decision": "DO_NOT_RETRY",
        "owner_visible": True,
        "resolved": True,
        "automatic_second_create_attempted": False,
    }
    assert receipt["counts"]["sdk_create_attempts"] == 1
    assert receipt["counts"]["remote_committed_runs"] == 1
    assert receipt["counts"]["final_bindings"] == 1


def test_all_k0_k6_receipts_require_complete_semantic_proof(host: ModuleType) -> None:
    manifest = _manifest(host)
    receipts = {
        scenario_id: _valid_receipt(host, manifest, scenario_id)
        for scenario_id in host.SCENARIO_STEPS
    }
    assert set(host.validate_complete_receipts(receipts, manifest=manifest)) == set(
        host.SCENARIO_STEPS
    )


def test_empty_success_receipt_is_rejected(host: ModuleType) -> None:
    with pytest.raises(host.QualificationError):
        host.validate_scenario_receipt(
            {},
            manifest=_manifest(host),
            expected_scenario_id="K0",
        )


def test_wrong_scenario_receipt_is_rejected(host: ModuleType) -> None:
    manifest = _manifest(host)
    receipt = _valid_receipt(host, manifest, "K0")
    receipt["scenario_id"] = "K1"
    with pytest.raises(host.QualificationError) as raised:
        host.validate_scenario_receipt(
            receipt,
            manifest=manifest,
            expected_scenario_id="K0",
        )
    assert raised.value.code == "rc_s3_107_receipt_identity_or_schema_mismatch"


def test_wrong_attempt_identity_is_rejected(host: ModuleType) -> None:
    manifest = _manifest(host)
    receipt = _valid_receipt(host, manifest, "K0")
    receipt["attempt_id"] = "other-attempt"
    with pytest.raises(host.QualificationError):
        host.validate_scenario_receipt(
            receipt,
            manifest=manifest,
            expected_scenario_id="K0",
        )


def test_wrong_create_and_remote_counts_are_rejected(host: ModuleType) -> None:
    manifest = _manifest(host)
    for field in ("sdk_create_attempts", "remote_committed_runs"):
        receipt = _valid_receipt(host, manifest, "K2")
        receipt["counts"][field] = 0
        with pytest.raises(host.QualificationError) as raised:
            host.validate_scenario_receipt(
                receipt,
                manifest=manifest,
                expected_scenario_id="K2",
            )
        assert raised.value.code == "rc_s3_107_receipt_count_mismatch"


def test_control_receipt_rejects_remote_error_as_success(host: ModuleType) -> None:
    manifest = _manifest(host)
    receipt = _valid_receipt(host, manifest, "K0")
    receipt["invocations"][0]["remote_run_status"] = "error"
    with pytest.raises(host.QualificationError) as raised:
        host.validate_scenario_receipt(
            receipt,
            manifest=manifest,
            expected_scenario_id="K0",
        )
    assert raised.value.code == "rc_s3_107_receipt_remote_terminal_status_mismatch"


def test_no_create_receipt_requires_null_remote_status(host: ModuleType) -> None:
    manifest = _manifest(host)
    receipt = _valid_receipt(host, manifest, "K1")
    receipt["invocations"][0]["remote_run_status"] = "success"
    with pytest.raises(host.QualificationError) as raised:
        host.validate_scenario_receipt(
            receipt,
            manifest=manifest,
            expected_scenario_id="K1",
        )
    assert raised.value.code == "rc_s3_107_receipt_remote_status_mismatch"


def test_fault_receipt_cannot_pass_while_remote_run_is_pending(host: ModuleType) -> None:
    manifest = _manifest(host)
    receipt = _valid_receipt(host, manifest, "K2")
    receipt["invocations"][0]["remote_run_status"] = "pending"
    with pytest.raises(host.QualificationError) as raised:
        host.validate_scenario_receipt(
            receipt,
            manifest=manifest,
            expected_scenario_id="K2",
        )
    assert raised.value.code == "rc_s3_107_receipt_remote_terminal_status_mismatch"


def test_unresolved_restart_orphan_must_fail_closed_remotely(host: ModuleType) -> None:
    manifest = _manifest(host)
    receipt = _valid_receipt(host, manifest, "K5")
    receipt["invocations"][1]["remote_run_status"] = "success"
    with pytest.raises(host.QualificationError) as raised:
        host.validate_scenario_receipt(
            receipt,
            manifest=manifest,
            expected_scenario_id="K5",
        )
    assert raised.value.code == "rc_s3_107_receipt_remote_terminal_status_mismatch"


def test_remote_readback_rejects_run_id_that_disagrees_with_fin(
    host: ModuleType,
    phase: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _manifest(host)
    invocation_id = manifest["scenario_identities"]["K0"][0]["invocation_id"]
    expected_run_id = str(uuid.uuid4())
    observed_run_id = str(uuid.uuid4())

    class Runs:
        @staticmethod
        def list(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
            return [
                {
                    "run_id": observed_run_id,
                    "status": "success",
                    "metadata": {"run_invocation_id": invocation_id},
                }
            ]

    class Client:
        runs = Runs()

        @staticmethod
        def close() -> None:
            return None

    import langgraph_sdk

    monkeypatch.setattr(langgraph_sdk, "get_sync_client", lambda **kwargs: Client())
    with pytest.raises(phase.LivePhaseBlocker) as raised:
        phase._remote_readback(
            manifest,
            scenario_id="K0",
            fin_rows=[
                {
                    "invocation_id": invocation_id,
                    "server_thread_id": str(uuid.uuid4()),
                    "bound_server_run_id": expected_run_id,
                    "latest_exact_orphan_server_run_id": expected_run_id,
                }
            ],
            expected_remote_runs=1,
            required_statuses_by_invocation={
                invocation_id: frozenset({"success"})
            },
            require_fin_run_id_match=True,
        )
    assert raised.value.code == "rc_s3_107_fin_remote_run_identity_mismatch"


def test_remote_readback_rejects_extra_run_on_dedicated_thread(
    host: ModuleType,
    phase: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _manifest(host)
    invocation_id = manifest["scenario_identities"]["K0"][0]["invocation_id"]
    expected_run_id = str(uuid.uuid4())
    unexpected_run_id = str(uuid.uuid4())

    class Runs:
        @staticmethod
        def list(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
            return [
                {
                    "run_id": expected_run_id,
                    "status": "success",
                    "metadata": {"run_invocation_id": invocation_id},
                },
                {
                    "run_id": unexpected_run_id,
                    "status": "error",
                    "metadata": {"run_invocation_id": "unexpected-invocation"},
                },
            ]

    class Client:
        runs = Runs()

        @staticmethod
        def close() -> None:
            return None

    import langgraph_sdk

    monkeypatch.setattr(langgraph_sdk, "get_sync_client", lambda **kwargs: Client())
    with pytest.raises(phase.LivePhaseBlocker) as raised:
        phase._remote_readback(
            manifest,
            scenario_id="K0",
            fin_rows=[
                {
                    "invocation_id": invocation_id,
                    "server_thread_id": str(uuid.uuid4()),
                    "bound_server_run_id": expected_run_id,
                    "latest_exact_orphan_server_run_id": expected_run_id,
                }
            ],
            expected_remote_runs=1,
            required_statuses_by_invocation={
                invocation_id: frozenset({"success"})
            },
            require_fin_run_id_match=True,
        )
    assert raised.value.code == "rc_s3_107_remote_thread_contains_unexpected_run"


def test_total_create_count_cannot_hide_wrong_per_invocation_distribution(
    host: ModuleType,
) -> None:
    manifest = _manifest(host)
    receipt = _valid_receipt(host, manifest, "K5")
    receipt["invocations"][0]["sdk_create_attempts"] = 2
    receipt["invocations"][1]["sdk_create_attempts"] = 0
    assert receipt["counts"]["sdk_create_attempts"] == 2
    with pytest.raises(host.QualificationError) as raised:
        host.validate_scenario_receipt(
            receipt,
            manifest=manifest,
            expected_scenario_id="K5",
        )
    assert raised.value.code == "rc_s3_107_receipt_invocation_semantics_mismatch"


@pytest.mark.parametrize(
    ("scenario_id", "proof_key"),
    [
        ("K3", "transaction_rollback_observed"),
        ("K5", "postgres_restart_observed"),
        ("K6", "durable_winner_count"),
    ],
)
def test_missing_scenario_specific_proof_is_rejected(
    host: ModuleType,
    scenario_id: str,
    proof_key: str,
) -> None:
    manifest = _manifest(host)
    receipt = _valid_receipt(host, manifest, scenario_id)
    del receipt["proof"][proof_key]
    with pytest.raises(host.QualificationError) as raised:
        host.validate_scenario_receipt(
            receipt,
            manifest=manifest,
            expected_scenario_id=scenario_id,
        )
    assert raised.value.code == "rc_s3_107_receipt_proof_unknown_or_missing_field"


def test_missing_dispatched_or_reconciled_state_is_rejected(host: ModuleType) -> None:
    manifest = _manifest(host)
    for missing_state in ("DISPATCHED", "RECONCILED"):
        receipt = _valid_receipt(host, manifest, "K4")
        receipt["invocations"][0]["lifecycle"].remove(missing_state)
        with pytest.raises(host.QualificationError) as raised:
            host.validate_scenario_receipt(
                receipt,
                manifest=manifest,
                expected_scenario_id="K4",
            )
        assert raised.value.code == "rc_s3_107_receipt_invocation_semantics_mismatch"


def test_impossible_recovery_disposition_is_rejected(host: ModuleType) -> None:
    manifest = _manifest(host)
    receipt = _valid_receipt(host, manifest, "K0")
    receipt["invocations"][0]["recovery"]["recovery_disposition_status"] = (
        "OPERATOR_REVIEW_REQUIRED"
    )
    with pytest.raises(host.QualificationError):
        host.validate_scenario_receipt(
            receipt,
            manifest=manifest,
            expected_scenario_id="K0",
        )


def test_noncanonical_action_outcome_is_rejected(host: ModuleType) -> None:
    manifest = _manifest(host)
    receipt = _valid_receipt(host, manifest, "K3")
    receipt["invocations"][0]["canonical_action_outcome"] = (
        "BIND_RECOVERED_SOMEHOW"
    )
    with pytest.raises(host.QualificationError) as raised:
        host.validate_scenario_receipt(
            receipt,
            manifest=manifest,
            expected_scenario_id="K3",
        )
    assert raised.value.code == "rc_s3_107_receipt_invocation_semantics_mismatch"


def test_wrapper_counter_cannot_replace_remote_and_postgres_readback(
    host: ModuleType,
) -> None:
    manifest = _manifest(host)
    receipt = _valid_receipt(host, manifest, "K4")
    receipt["observation_sources"]["remote_committed_runs"] = "WRAPPER_COUNTER"
    with pytest.raises(host.QualificationError) as raised:
        host.validate_scenario_receipt(
            receipt,
            manifest=manifest,
            expected_scenario_id="K4",
        )
    assert raised.value.code == "rc_s3_107_receipt_observation_source_mismatch"


def test_unknown_receipt_field_is_rejected(host: ModuleType) -> None:
    manifest = _manifest(host)
    receipt = _valid_receipt(host, manifest, "K0")
    receipt["unreviewed_claim"] = True
    with pytest.raises(host.QualificationError) as raised:
        host.validate_scenario_receipt(
            receipt,
            manifest=manifest,
            expected_scenario_id="K0",
        )
    assert raised.value.code == "rc_s3_107_receipt_unknown_or_missing_field"


def test_langsmith_egress_cannot_be_mislabeled_as_zero_external(
    host: ModuleType,
) -> None:
    manifest = _manifest(host)
    receipt = _valid_receipt(host, manifest, "K0")
    receipt["execution_boundary"]["langsmith_observability_egress"] = False
    with pytest.raises(host.QualificationError) as raised:
        host.validate_scenario_receipt(
            receipt,
            manifest=manifest,
            expected_scenario_id="K0",
        )
    assert raised.value.code == "rc_s3_107_receipt_execution_boundary_mismatch"


def test_cross_scenario_invocation_collision_is_rejected(host: ModuleType) -> None:
    manifest = _manifest(host)
    manifest["scenario_identities"]["K1"][0]["invocation_id"] = manifest[
        "scenario_identities"
    ]["K0"][0]["invocation_id"]
    receipts = {
        scenario_id: _valid_receipt(host, manifest, scenario_id)
        for scenario_id in host.SCENARIO_STEPS
    }
    with pytest.raises(host.QualificationError) as raised:
        host.validate_complete_receipts(receipts, manifest=manifest)
    assert raised.value.code == "rc_s3_107_cross_scenario_identity_collision"


def test_single_sanitized_json_cannot_become_final_pass(
    host: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _manifest(host)
    step = host.SCENARIO_STEPS["K0"][0]
    completed = type(
        "Completed",
        (),
        {
            "returncode": 0,
            "stdout": json.dumps({"status": "PASS", "scenario_id": "K0"}),
        },
    )()
    monkeypatch.setattr(host.subprocess, "run", lambda *args, **kwargs: completed)
    with pytest.raises(host.QualificationError):
        host._run_phase_step(
            project=manifest["project"],
            port=18131,
            scenario_id="K0",
            step=step,
            manifest=manifest,
        )


def test_k1_victim_exit_is_accepted_only_with_exact_observation(
    host: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _manifest(host)
    step = host.SCENARIO_STEPS["K1"][0]
    observation = {
        "schema_version": "fin.rc_s3_107.killpoint_observation.v1",
        "attempt_id": manifest["attempt_id"],
        "project": manifest["project"],
        "scenario_id": "K1",
        "step_id": "pending_victim",
        "milestone": "pending_committed_before_dispatch",
        "sdk_create_calls": 0,
        "remote_run_count": 0,
    }
    completed = type(
        "Completed",
        (),
        {"returncode": 91, "stdout": json.dumps(observation)},
    )()
    monkeypatch.setattr(host.subprocess, "run", lambda *args, **kwargs: completed)
    assert host._run_phase_step(
        project=manifest["project"],
        port=18131,
        scenario_id="K1",
        step=step,
        manifest=manifest,
    ) == observation


def test_host_supervisor_owns_k1_k2_recovery_and_k5_restarts(host: ModuleType) -> None:
    assert [(step.step_id, step.expected_exit_code) for step in host.SCENARIO_STEPS["K1"]] == [
        ("pending_victim", 91),
        ("classify_pending_failed_before_dispatch", 0),
        ("dispatched_victim", 94),
        ("fresh_recovery_and_readback", 0),
    ]
    assert [(step.step_id, step.expected_exit_code) for step in host.SCENARIO_STEPS["K2"]] == [
        ("header_victim", 92),
        ("fresh_recovery_and_readback", 0),
    ]
    assert [
        (step.kind, step.service)
        for step in host.SCENARIO_STEPS["K5"]
        if step.kind == "restart"
    ] == [
        ("restart", "langgraph-api"),
        ("restart", "langgraph-postgres"),
    ]


def test_k5_supervisor_executes_host_restarts_before_final_readback(
    host: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _manifest(host)
    actions: list[tuple[str, str]] = []
    final = _valid_receipt(host, manifest, "K5")

    def fake_phase_step(**kwargs: Any) -> dict[str, Any]:
        step = kwargs["step"]
        actions.append(("phase", step.step_id))
        return final if step.produces_final_receipt else {"observation": True}

    def fake_restart_service(**kwargs: Any) -> None:
        actions.append(("restart", kwargs["service"]))

    def fake_operator_step(**kwargs: Any) -> dict[str, Any]:
        actions.append(("operator", kwargs["step"].step_id))
        return {"observation": True}

    monkeypatch.setattr(host, "_run_phase_step", fake_phase_step)
    monkeypatch.setattr(host, "_restart_service", fake_restart_service)
    monkeypatch.setattr(host, "_run_operator_step", fake_operator_step)
    assert host._run_scenario(
        project=manifest["project"],
        port=18131,
        scenario_id="K5",
        manifest=manifest,
    ) == final
    assert actions == [
        ("phase", "seed_restart_states"),
        ("phase", "pending_owner_handoff_readback"),
        ("operator", "record_operator_disposition"),
        ("restart", "langgraph-api"),
        ("phase", "readback_after_api_restart"),
        ("restart", "langgraph-postgres"),
        ("phase", "final_readback_after_postgres_restart"),
    ]


def test_k4_supervisor_requires_observation_then_operator_then_bind(
    host: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _manifest(host)
    actions: list[tuple[str, str]] = []
    final = _valid_receipt(host, manifest, "K4")

    def fake_phase_step(**kwargs: Any) -> dict[str, Any]:
        step = kwargs["step"]
        actions.append(("phase", step.step_id))
        return final if step.produces_final_receipt else {"observation": True}

    def fake_operator_step(**kwargs: Any) -> dict[str, Any]:
        actions.append(("operator", kwargs["step"].step_id))
        return {"observation": True}

    monkeypatch.setattr(host, "_run_phase_step", fake_phase_step)
    monkeypatch.setattr(host, "_run_operator_step", fake_operator_step)
    assert host._run_scenario(
        project=manifest["project"],
        port=18131,
        scenario_id="K4",
        manifest=manifest,
    ) == final
    assert actions == [
        ("phase", "response_loss_first_pass"),
        ("phase", "fresh_exact_observation"),
        ("operator", "record_operator_disposition"),
        ("phase", "fresh_authorized_bind_and_readback"),
    ]


def test_k5_pending_only_handoff_cannot_claim_final_pass(host: ModuleType) -> None:
    manifest = _manifest(host)
    receipt = _valid_receipt(host, manifest, "K5")
    recovery = receipt["invocations"][1]["recovery"]
    recovery.update(
        {
            "recovery_disposition_status": "PENDING_OWNER_DECISION",
            "canonical_recovery_decision": None,
            "resolved": False,
        }
    )
    with pytest.raises(host.QualificationError) as raised:
        host.validate_scenario_receipt(
            receipt,
            manifest=manifest,
            expected_scenario_id="K5",
        )
    assert raised.value.code == "rc_s3_107_receipt_recovery_semantics_mismatch"


def test_operator_observation_rejects_wrong_action_binding(
    host: ModuleType,
) -> None:
    manifest = _manifest(host)
    step = next(
        item
        for item in host.SCENARIO_STEPS["K5"]
        if item.kind == "operator"
    )
    invocation_id = next(
        item["invocation_id"]
        for item in manifest["scenario_identities"]["K5"]
        if item["role"] == "unresolved_orphan_restart"
    )
    observation = {
        "schema_version": "fin.rc_s3_107.operator_observation.v1",
        "attempt_id": manifest["attempt_id"],
        "project": manifest["project"],
        "scenario_id": "K5",
        "step_id": step.step_id,
        "milestone": step.expected_milestone,
        "source_invocation_id": invocation_id,
        "canonical_recovery_decision": "DO_NOT_RETRY",
        "exact_ambiguous_action_binding": False,
    }
    with pytest.raises(host.QualificationError) as raised:
        host._validate_operator_observation(
            observation,
            manifest=manifest,
            scenario_id="K5",
            step=step,
        )
    assert raised.value.code == "rc_s3_107_operator_observation_semantics_mismatch"


def test_dispatched_killpoint_occurs_before_sdk_create(
    phase: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[Any] = []

    class Repo:
        def mark_run_create_dispatched(self, value: str) -> str:
            events.append(("dispatched", value))
            return "DISPATCHED"

    monkeypatch.setattr(
        phase,
        "emit_observation",
        lambda item: events.append(("emit", item.milestone)),
    )

    def fake_exit(code: int) -> None:
        events.append(("exit", code))
        raise RuntimeError("expected-hard-exit")

    wrapped = phase.CrashAfterDispatchedRepository(
        Repo(),
        hard_exit=fake_exit,
        attempt_id="attempt-1",
        project="project-1",
    )
    with pytest.raises(RuntimeError, match="expected-hard-exit"):
        wrapped.mark_run_create_dispatched("invocation")
    assert events == [
        ("dispatched", "invocation"),
        ("emit", "dispatched_committed_before_sdk_create"),
        ("exit", 94),
    ]


def test_k3_fault_is_after_binding_insert_and_before_reconciled_insert(
    phase: ModuleType,
) -> None:
    queries: list[str] = []

    class Connection:
        def execute(self, query: str, params: Any = None) -> str:
            queries.append(query)
            return "ok"

    state = phase.ReconciledInsertFaultState()
    connection = phase.ReconciledInsertFaultConnection(Connection(), state)
    assert connection.execute(
        "INSERT INTO fin_runtime.research_run_invocations VALUES (...)"
    ) == "ok"
    with pytest.raises(RuntimeError, match="injected_reconciled_insert_failure"):
        connection.execute(
            """
            INSERT INTO fin_runtime.agent_server_run_create_lifecycle (
                run_invocation_id, lifecycle_state
            ) VALUES (%s, 'RECONCILED')
            """,
            ("INVOCATION::K3",),
        )
    assert state.binding_insert_observed is True
    assert state.reconciled_insert_faulted is True
    assert len(queries) == 1


def test_k6_winner_cannot_dispatch_until_loser_finishes_pending_path(
    phase: ModuleType,
    tmp_path: Path,
) -> None:
    class Registration:
        def __init__(self, created_now: bool) -> None:
            self.created_now = created_now

    class Repo:
        def __init__(self, created_now: bool) -> None:
            self.created_now = created_now

        def begin_run_create(self) -> Registration:
            return Registration(self.created_now)

    prefix = tmp_path / "barrier"
    owner = phase.ConcurrentBeginRepository(
        Repo(True), barrier_prefix=prefix, worker_id=0
    )
    loser = phase.ConcurrentBeginRepository(
        Repo(False), barrier_prefix=prefix, worker_id=1
    )
    owner_finished = threading.Event()
    loser_finished = threading.Event()

    def run_owner() -> None:
        owner.begin_run_create()
        owner_finished.set()

    def run_loser() -> None:
        loser.begin_run_create()
        loser_finished.set()

    owner_thread = threading.Thread(target=run_owner)
    loser_thread = threading.Thread(target=run_loser)
    owner_thread.start()
    loser_thread.start()
    assert loser_finished.wait(2)
    assert owner_finished.is_set() is False
    loser.release_winner_after_loser()
    assert owner_finished.wait(2)
    owner_thread.join(2)
    loser_thread.join(2)
    assert owner.created_now is True
    assert loser.created_now is False


def test_sdk_instrumentation_is_identity_bound_and_durable(
    phase: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    base_manifest = {"attempt_id": "attempt-1", "project": "project-1"}
    assert phase._instrumentation_path(
        base_manifest, scenario_id="K0"
    ) != phase._instrumentation_path(base_manifest, scenario_id="K1")
    manifest = {**base_manifest, "scenario_id": "K0"}
    path = tmp_path / "creates.jsonl"
    monkeypatch.setattr(
        phase,
        "_instrumentation_path",
        lambda _manifest, **_kwargs: path,
    )

    class Runs:
        def create(self, **kwargs: Any) -> str:
            return "created"

    instrumented = phase.InstrumentedRuns(Runs(), manifest=manifest)
    assert instrumented.create(metadata={"run_invocation_id": "i-1"}) == "created"
    assert phase._instrumented_create_counts(
        manifest,
        scenario_id="K0",
        allowed_invocation_ids={"i-1"},
    ) == {"i-1": 1}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "schema_version": "fin.rc_s3_107.sdk_create_attempt.v1",
                    "attempt_id": "attempt-1",
                    "project": "project-1",
                    "scenario_id": "K0",
                    "invocation_id": "foreign",
                }
            )
            + "\n"
        )
    with pytest.raises(phase.LivePhaseBlocker) as raised:
        phase._instrumented_create_counts(
            manifest,
            scenario_id="K0",
            allowed_invocation_ids={"i-1"},
        )
    assert raised.value.code == "rc_s3_107_sdk_instrumentation_identity_mismatch"


def test_phase_entry_returns_typed_blocker_not_fake_pass(
    host: ModuleType,
    phase: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    manifest = _manifest(host)
    monkeypatch.setattr(phase.sys, "stdin", io.StringIO(json.dumps(manifest)))
    assert phase.main(["--scenario", "K4", "--step", "not-a-real-step"]) == 78
    receipt = json.loads(capsys.readouterr().out)
    assert receipt == {
        "schema_version": "fin.rc_s3_107.phase_blocker.v1",
        "attempt_id": manifest["attempt_id"],
        "project": manifest["project"],
        "scenario_id": "K4",
        "step_id": "not-a-real-step",
        "status": "BLOCKED",
        "code": "rc_s3_107_k4_step_invalid",
    }


def test_overlay_is_zero_model_read_only_and_has_no_provider_surface() -> None:
    data = yaml.safe_load(OVERLAY_PATH.read_text(encoding="utf-8"))
    service = data["services"]["langgraph-api"]
    environment = service["environment"]
    assert environment["FIN_AGENT_SERVER_MODE"] == "zero_model_control_plane_v1"
    assert environment["FIN_AGENT_SERVER_ZERO_MODEL"] == "1"
    assert environment["FIN_AGENT_SERVER_HIDE_INPUTS"] == "1"
    assert environment["FIN_AGENT_SERVER_HIDE_OUTPUTS"] == "1"
    assert service["volumes"] == [
        {
            "type": "bind",
            "source": "../../scripts/qualification/agent_server_rc_s3_107",
            "target": "/opt/fin-insight-qualification/rc-s3-107",
            "read_only": True,
        }
    ]
    operator = data["services"]["fin-recovery-operator"]
    assert operator["profiles"] == ["rc-s3-107-operator"]
    assert "FIN_RUNTIME_OPERATOR_POSTGRES_URI" in operator["environment"]
    assert "FIN_RUNTIME_POSTGRES_URI" not in operator["environment"]
    assert "LANGSMITH_API_KEY" not in operator["environment"]
    text = OVERLAY_PATH.read_text(encoding="utf-8")
    assert "API_KEY" not in text
    assert "MODEL_PROVIDER" not in text
    assert "/var/run/docker.sock" not in text


def test_harness_has_no_destructive_cleanup_or_retry_fallback() -> None:
    host_source = HOST_PATH.read_text(encoding="utf-8")
    phase_source = PHASE_PATH.read_text(encoding="utf-8")
    forbidden = (
        "down -v",
        "docker volume rm",
        "docker rm",
        "docker system prune",
        "retry_attempt",
        "fallback_client",
        "fallback_runtime",
    )
    for fragment in forbidden:
        assert fragment not in host_source.lower()
        assert fragment not in phase_source.lower()
    assert "for scenario in SCENARIOS" in host_source
    assert "while " not in host_source


def test_contract_only_is_local_and_deterministic(host: ModuleType, capsys: Any) -> None:
    assert host.main(["--contract-only"]) == 0
    projection = json.loads(capsys.readouterr().out)
    assert projection["scenario_ids"] == ["K0", "K1", "K2", "K3", "K4", "K5", "K6"]
    assert projection["claim_boundary"]["excluded"] == "provider_or_network_exactly_once"
    assert projection["execution_boundary"] == {
        "zero_model": True,
        "external_research_or_model_calls": False,
        "provider_model_calls": False,
        "langsmith_observability_egress": True,
        "trace_content_in_receipt": False,
    }
