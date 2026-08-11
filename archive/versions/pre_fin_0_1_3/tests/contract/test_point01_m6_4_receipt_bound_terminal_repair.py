from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

from sec_agent.canonical_runtime.receipt_bound_candidate_bundle import ReceiptBoundCandidateBundleService
from sec_agent.canonical_runtime.receipt_bound_repair_ticket import (
    ReceiptBoundRepairTicketError,
    ReceiptBoundRepairTicketPolicy,
    ReceiptBoundRepairTicketService,
)


pytestmark = pytest.mark.fast_contract


ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "configs/engineering_handoff/point01_m6_4_receipt_bound_terminal_repair_policy_v1_0.json"
RUNNER_PATH = ROOT / "scripts/engineering/run_point01_m6_4_receipt_bound_terminal_repair.py"
M6_3_TEST_PATH = ROOT / "tests/contract/test_point01_m6_3_receipt_bound_candidate_bundle.py"
SPEC = importlib.util.spec_from_file_location("point01_m6_3_receipt_bundle_helpers_for_m6_4", M6_3_TEST_PATH)
assert SPEC and SPEC.loader
M6_3 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M6_3)
RUNNER_SPEC = importlib.util.spec_from_file_location("point01_m6_4_terminal_repair_runner_helpers", RUNNER_PATH)
assert RUNNER_SPEC and RUNNER_SPEC.loader
RUNNER = importlib.util.module_from_spec(RUNNER_SPEC)
RUNNER_SPEC.loader.exec_module(RUNNER)


def _policy() -> ReceiptBoundRepairTicketPolicy:
    raw = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    return ReceiptBoundRepairTicketPolicy.model_validate(
        {field: raw[field] for field in ReceiptBoundRepairTicketPolicy.model_fields}
    )


def _typed_exhaustion(tmp_path: Path):
    facade, command, request, plan, receipt, session = M6_3._successful_receipt(tmp_path)
    bundle = ReceiptBoundCandidateBundleService(facade=facade, policy=M6_3._policy()).persist(
        command=command,
        request=request,
        plan=plan,
        receipt_version_ref=f"{receipt.invocation_id}:v{receipt.invocation_version}",
    )
    return facade, command, request, bundle, session


def _runner_compatible_typed_exhaustion(tmp_path: Path):
    policy = M6_3.PILOT_RUNNER._policy()
    facade, security, budgets, command, reservation = M6_3.PILOT_RUNNER._runtime(tmp_path, policy)
    request = M6_3.PILOT_RUNNER._request()
    plan = M6_3.PILOT_RUNNER._registry_plan(request)
    session = M6_3.M6_2._Session()
    execution = M6_3.PILOT_RUNNER.BoundedSecMetadataExecutor(
        facade=facade,
        security=security,
        budgets=budgets,
        policy=policy,
        global_approval_service=M6_3.M6_2.seed_global_approval(
            tmp_path,
            command=command,
            request=request,
            plan=plan,
            policy=policy,
        )[0],
        global_approval_id=M6_3.M6_2.TEST_APPROVAL_ID,
        pilot_package=M6_3.M6_2.compute_m6_pilot_package(
            root=M6_3.M6_2.ROOT,
            manifest_path=M6_3.M6_2.PACKAGE_MANIFEST_PATH,
        ),
    ).execute(
        command=command,
        request=request,
        plan=plan,
        capability_grant_id="grant-point01-m6-sec-pilot",
        reservation=reservation,
        target_cik="0001045810",
        client=M6_3.M6_2.SingleCallSecSubmissionsClient(
            user_agent="FINInsight-Agent/1.0 compliance@finsight.test",
            timeout_seconds=20,
            session=session,
        ),
    )
    bundle = ReceiptBoundCandidateBundleService(facade=facade, policy=M6_3._policy()).persist(
        command=command,
        request=request,
        plan=plan,
        receipt_version_ref=f"{execution.receipt.invocation_id}:v{execution.receipt.invocation_version}",
    )
    return facade, command, request, bundle, session


def test_exact_typed_exhaustion_persists_a_terminal_zero_attempt_repair_ticket(tmp_path: Path) -> None:
    facade, command, request, bundle, session = _typed_exhaustion(tmp_path)
    service = ReceiptBoundRepairTicketService(facade=facade, policy=_policy())
    first = service.persist(
        command=command,
        request=request,
        candidate_bundle_version_ref=bundle.version.candidate_bundle_version_id,
    )
    ticket = first.version.ticket
    assert first.status == "terminal_repair_ticket_persisted"
    assert ticket.gap_code == "pilot_tool_call_budget_exhausted"
    assert ticket.classification == "bounded_pilot_call_budget_exhausted"
    assert ticket.permitted_route_scope == ()
    assert ticket.attempt_budget == 0
    assert ticket.terminal is True
    assert ticket.execution_admission == "not_admitted"
    assert first.external_call_count == first.tool_invocation_count == first.model_call_count == 0
    assert len(session.calls) == 1
    stored = facade.store.list_versions("canonical_repair_ticket_versions")
    assert len(stored) == 1
    event = [event for event in facade.store.list_events() if event["event_type"] == "RECEIPT_BOUND_TERMINAL_REPAIR_TICKET_PERSISTED"]
    assert len(event) == 1
    assert event[0]["state_version_before"] == 0 and event[0]["state_version_after"] == 1
    replay = service.persist(command=command, request=request, candidate_bundle_version_ref=bundle.version.candidate_bundle_version_id)
    assert replay.reused_idempotent_result is True
    assert len(facade.store.list_versions("canonical_repair_ticket_versions")) == 1
    assert len(session.calls) == 1


def test_missing_or_non_exact_bundle_reference_fails_before_ticket_write(tmp_path: Path) -> None:
    facade, command, request, bundle, _ = _typed_exhaustion(tmp_path)
    service = ReceiptBoundRepairTicketService(facade=facade, policy=_policy())
    with pytest.raises(ReceiptBoundRepairTicketError, match="candidate_bundle_exact_version_not_found"):
        service.persist(command=command, request=request, candidate_bundle_version_ref=f"{bundle.version.candidate_bundle_id}:v2")
    with pytest.raises(ReceiptBoundRepairTicketError, match="candidate_bundle_exact_version_not_found"):
        service.persist(command=command, request=request, candidate_bundle_version_ref="candidate_bundle_unknown:v1")
    assert not facade.store.list_versions("canonical_repair_ticket_versions")


def test_policy_prohibits_repair_execution_fallback_and_retry() -> None:
    raw = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    assert raw["approval_ref"] == "approve_m6_2_5_real_bounded_sec_metadata_pilot_only"
    assert raw["authority_boundary"]["repair_attempt_execution"] == "forbidden"
    assert raw["authority_boundary"]["new_tool_or_network_call"] == "forbidden"
    assert raw["authority_boundary"]["fallback_or_retry"] == "forbidden"


def test_runner_fails_closed_when_the_isolated_pilot_store_does_not_exist(tmp_path: Path) -> None:
    output = tmp_path / "result.json"
    completed = subprocess.run(
        [sys.executable, str(RUNNER_PATH), "--candidate-bundle-ref", "candidate_bundle_missing:v1", "--store-root", str(tmp_path / "missing-store"), "--output", str(output)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 1
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["status"] == "fail_closed"
    assert result["reason"] == "pilot_store_not_found"
    assert result["external_call_count"] == result["store_write_count"] == 0


def test_runner_persists_terminal_ticket_without_a_second_network_call(tmp_path: Path) -> None:
    facade, command, request, bundle, session = _runner_compatible_typed_exhaustion(tmp_path)
    result = RUNNER.build_result(store_root=tmp_path, candidate_bundle_version_ref=bundle.version.candidate_bundle_version_id)
    assert result["status"] == "pass"
    assert result["external_call_count"] == 0
    assert result["repair_ticket"]["terminal"] is True
    assert result["repair_ticket"]["attempt_budget"] == 0
    assert len(session.calls) == 1
