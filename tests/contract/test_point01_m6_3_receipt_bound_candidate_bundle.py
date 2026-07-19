from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

from sec_agent.canonical_runtime.receipt_bound_candidate_bundle import (
    ReceiptBoundCandidateBundleError,
    ReceiptBoundCandidateBundlePolicy,
    ReceiptBoundCandidateBundleService,
)


pytestmark = pytest.mark.fast_contract


ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "configs/engineering_handoff/point01_m6_3_receipt_bound_candidate_bundle_policy_v1_0.json"
RUNNER_PATH = ROOT / "scripts/engineering/run_point01_m6_3_receipt_bound_candidate_bundle.py"
M6_2_PILOT_RUNNER_PATH = ROOT / "scripts/engineering/run_point01_m6_2_real_bounded_sec_metadata_pilot.py"
M6_2_TEST_PATH = ROOT / "tests/contract/test_point01_m6_2_real_bounded_sec_metadata_execution.py"
SPEC = importlib.util.spec_from_file_location("point01_m6_2_real_execution_helpers", M6_2_TEST_PATH)
assert SPEC and SPEC.loader
M6_2 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M6_2)
PILOT_SPEC = importlib.util.spec_from_file_location("point01_m6_2_pilot_runner_helpers", M6_2_PILOT_RUNNER_PATH)
assert PILOT_SPEC and PILOT_SPEC.loader
PILOT_RUNNER = importlib.util.module_from_spec(PILOT_SPEC)
PILOT_SPEC.loader.exec_module(PILOT_RUNNER)
RUNNER_SPEC = importlib.util.spec_from_file_location("point01_m6_3_receipt_bundle_runner_helpers", RUNNER_PATH)
assert RUNNER_SPEC and RUNNER_SPEC.loader
RUNNER = importlib.util.module_from_spec(RUNNER_SPEC)
RUNNER_SPEC.loader.exec_module(RUNNER)


def _policy() -> ReceiptBoundCandidateBundlePolicy:
    raw = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    return ReceiptBoundCandidateBundlePolicy.model_validate(
        {field: raw[field] for field in ReceiptBoundCandidateBundlePolicy.model_fields}
    )


def _successful_receipt(tmp_path: Path):
    facade, security, budgets, command, reservation = M6_2._runtime(tmp_path)
    request = M6_2._request()
    plan = M6_2._plan(request)
    session = M6_2._Session()
    client = M6_2.SingleCallSecSubmissionsClient(
        user_agent="FINInsight-Agent/1.0 compliance@finsight.test",
        timeout_seconds=20,
        session=session,
    )
    execution = M6_2._executor(facade, security, budgets).execute(
        command=command,
        request=request,
        plan=plan,
        capability_grant_id="grant-m6-2-sec-live",
        reservation=reservation,
        target_cik="0001045810",
        client=client,
    )
    assert execution.status == "succeeded"
    return facade, command, request, plan, execution.receipt, session


def test_successful_exact_receipt_persists_only_a_typed_exhaustion_bundle(tmp_path: Path) -> None:
    facade, command, request, plan, receipt, session = _successful_receipt(tmp_path)
    service = ReceiptBoundCandidateBundleService(facade=facade, policy=_policy())
    receipt_ref = f"{receipt.invocation_id}:v{receipt.invocation_version}"
    first = service.persist(command=command, request=request, plan=plan, receipt_version_ref=receipt_ref)
    assert first.status == "typed_exhaustion_persisted"
    bundle = first.version.bundle
    assert bundle.status == "retrieval_exhausted"
    assert bundle.candidate_count == 0
    assert bundle.candidates == ()
    assert bundle.typed_gap_codes == (
        "required_context_kind_missing:period_binding",
        "required_context_kind_missing:neighbor_section",
        "required_context_kind_missing:table_context",
    )
    assert bundle.execution_admission == "receipt_bound_no_new_execution"
    assert bundle.persistence_admission == "m6_3_receipt_bound_synthetic_pilot_only"
    assert len(session.calls) == 1
    stored = facade.store.list_versions("canonical_candidate_bundle_versions")
    assert len(stored) == 1
    assert stored[0]["receipt_version_ref"] == receipt_ref
    event = [item for item in facade.store.list_events() if item["event_type"] == "RECEIPT_BOUND_CANDIDATE_BUNDLE_PERSISTED"]
    assert len(event) == 1
    assert event[0]["state_version_before"] == 0 and event[0]["state_version_after"] == 1
    replay = service.persist(command=command, request=request, plan=plan, receipt_version_ref=receipt_ref)
    assert replay.reused_idempotent_result is True
    assert len(facade.store.list_versions("canonical_candidate_bundle_versions")) == 1
    assert len(session.calls) == 1


def test_prepared_receipt_or_lineage_bypass_fails_before_bundle_write(tmp_path: Path) -> None:
    facade, command, request, plan, receipt, _ = _successful_receipt(tmp_path)
    service = ReceiptBoundCandidateBundleService(facade=facade, policy=_policy())
    with pytest.raises(ReceiptBoundCandidateBundleError, match="successful_single_call_receipt_required"):
        service.persist(
            command=command,
            request=request,
            plan=plan,
            receipt_version_ref=f"{receipt.invocation_id}:v1",
        )
    with pytest.raises(ReceiptBoundCandidateBundleError, match="receipt_plan_lineage_mismatch"):
        service.persist(
            command=command,
            request=request,
            plan=plan.model_copy(update={"plan_digest": "tampered-plan-digest"}),
            receipt_version_ref=f"{receipt.invocation_id}:v{receipt.invocation_version}",
        )
    assert not facade.store.list_versions("canonical_candidate_bundle_versions")


def test_policy_is_bound_to_the_current_human_approved_pilot_scope() -> None:
    raw = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    assert raw["approval_ref"] == "approve_m6_2_5_real_bounded_sec_metadata_pilot_only"
    assert raw["allowed_network_host"] == "data.sec.gov"
    assert raw["allowed_cik"] == "0001045810"
    assert raw["authority_boundary"]["new_network_or_tool_execution"] == "forbidden"


def test_runner_fails_closed_when_the_isolated_pilot_store_does_not_exist(tmp_path: Path) -> None:
    output = tmp_path / "result.json"
    completed = subprocess.run(
        [sys.executable, str(RUNNER_PATH), "--receipt-ref", "tool_invocation_missing:v2", "--store-root", str(tmp_path / "missing-store"), "--output", str(output)],
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


def test_runner_consumes_an_exact_successful_receipt_without_a_new_network_call(tmp_path: Path) -> None:
    policy = PILOT_RUNNER._policy()
    facade, security, budgets, command, reservation = PILOT_RUNNER._runtime(tmp_path, policy)
    request = PILOT_RUNNER._request()
    plan = PILOT_RUNNER._registry_plan(request)
    session = M6_2._Session()
    execution = PILOT_RUNNER.BoundedSecMetadataExecutor(
        facade=facade,
        security=security,
        budgets=budgets,
        policy=policy,
        global_approval_service=M6_2.seed_global_approval(
            tmp_path,
            command=command,
            request=request,
            plan=plan,
            policy=policy,
        )[0],
        global_approval_id=M6_2.TEST_APPROVAL_ID,
        pilot_package=M6_2.compute_m6_pilot_package(
            root=M6_2.ROOT,
            manifest_path=M6_2.PACKAGE_MANIFEST_PATH,
        ),
    ).execute(
        command=command,
        request=request,
        plan=plan,
        capability_grant_id="grant-point01-m6-sec-pilot",
        reservation=reservation,
        target_cik="0001045810",
        client=M6_2.SingleCallSecSubmissionsClient(
            user_agent="FINInsight-Agent/1.0 compliance@finsight.test",
            timeout_seconds=20,
            session=session,
        ),
    )
    result = RUNNER.build_result(
        store_root=tmp_path,
        receipt_version_ref=f"{execution.receipt.invocation_id}:v{execution.receipt.invocation_version}",
    )
    assert result["status"] == "pass"
    assert result["external_call_count"] == 0
    assert result["candidate_bundle"]["status"] == "retrieval_exhausted"
    assert len(session.calls) == 1
