from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pytest
import requests

from sec_agent.canonical_runtime.bounded_sec_metadata_execution import (
    BoundedSecMetadataExecutionPolicy,
    BoundedSecMetadataExecutor,
    SingleCallSecSubmissionsClient,
)
from sec_agent.canonical_runtime.budget_control import BudgetControlService, BudgetPolicy, BudgetReservationRequest
from sec_agent.canonical_runtime.capability_security import CapabilityGrant, CapabilitySecurityService, ToolManifest
from sec_agent.canonical_runtime.durable_scheduler import DurableSchedulerService
from sec_agent.canonical_runtime.evidence_request import EvidenceRequest
from sec_agent.canonical_runtime.facade import RuntimeFacade
from sec_agent.canonical_runtime.feature_flags import FeatureFlagRegistry
from sec_agent.canonical_runtime.m6_pilot_global_approval import (
    M6GlobalOneShotApprovalReceipt,
    M6GlobalOneShotApprovalService,
    build_m6_pilot_scope,
)
from sec_agent.canonical_runtime.m6_pilot_package import compute_m6_pilot_package
from sec_agent.canonical_runtime.models import CommandEnvelope, canonical_digest, utc_now
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.canonical_runtime.store import SQLiteCanonicalStore
from sec_agent.canonical_runtime.tool_planner import ToolSelectionPlan, ToolSelectionStep


pytestmark = pytest.mark.fast_contract


ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "configs/engineering_handoff/point01_m6_2_real_bounded_sec_metadata_pilot_policy_v1_0.json"
LIVE_RUNNER_PATH = ROOT / "scripts/engineering/run_point01_m6_2_real_bounded_sec_metadata_pilot.py"
PACKAGE_MANIFEST_PATH = ROOT / "configs/engineering_handoff/point01_m6_2_global_one_shot_package_manifest_v1_0.json"
TEST_APPROVAL_ID = "approval-point01-m6-2-test-global-one-shot"


class _Response:
    status_code = 200

    @staticmethod
    def json() -> dict:
        return {
            "name": "NVIDIA CORP",
            "tickers": ["NVDA"],
            "filings": {
                "recent": {
                    "form": ["10-K", "10-Q"],
                    "filingDate": ["2026-02-25", "2026-05-28"],
                    "reportDate": ["2026-01-25", "2026-04-26"],
                    "accessionNumber": ["0001045810-26-000001", "0001045810-26-000002"],
                    "primaryDocument": ["nvda-20260125.htm", "nvda-20260426.htm"],
                }
            },
        }


class _Session:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def get(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        return _Response()


class _FailingSession(_Session):
    def get(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        raise requests.ConnectionError("simulated connection reset after send boundary")


class _RevokingSecurity:
    """Inject a durable revocation exactly between prepare admission and send."""

    def __init__(self, security: CapabilitySecurityService, command: CommandEnvelope) -> None:
        self._security = security
        self._command = command
        self._admission_count = 0

    def admit(self, command: CommandEnvelope, request):
        decision = self._security.admit(command, request)
        self._admission_count += 1
        if self._admission_count == 1:
            persisted = self._security.facade.store.get_latest("canonical_capability_grant_versions", "grant-m6-2-sec-live")
            assert persisted is not None
            revoked = CapabilityGrant.model_validate(persisted["grant"]).model_copy(
                update={"revoked_at": utc_now() - timedelta(seconds=1)}
            )
            self._security.register_authority(
                self._command.model_copy(
                    update={
                        "command_id": f"{self._command.command_id}:revoke-before-send",
                        "command_type": "CAPABILITY_GRANT_RECORDED",
                        "idempotency_key": "grant-revoke-before-send",
                        "requested_at": utc_now(),
                        "payload": {},
                    }
                ),
                revoked,
            )
        return decision


class _FailOnceConsumeBudget:
    """Crash-point substitute: remote send happened, local consume fails once."""

    def __init__(self, delegate: BudgetControlService) -> None:
        self.delegate = delegate
        self.fail_consume = True

    def reserve(self, request):
        return self.delegate.reserve(request)

    def refund(self, reservation_id: str, **kwargs):
        return self.delegate.refund(reservation_id, **kwargs)

    def consume(self, reservation_id: str, **kwargs):
        if self.fail_consume:
            self.fail_consume = False
            raise RuntimeError("simulated_budget_consume_write_failure_after_send")
        return self.delegate.consume(reservation_id, **kwargs)


def _flags() -> FeatureFlagRegistry:
    return FeatureFlagRegistry(
        {
            "default_deny": True,
            "flags": [
                {
                    "flag_id": "decision_surface_shadow_v0_1",
                    "default_mode": "off",
                    "allowed_modes": ["off", "shadow"],
                    "required_capability_grants": ["point01.shadow.write"],
                    "allowed_consumers": ["point01_shadow_compiler"],
                    "forbidden_consumers": ["memo_writer", "evidence_runtime"],
                }
            ],
        }
    )


def _command(command_type: str, payload: dict, *, idem: str, expected: int = 0) -> CommandEnvelope:
    return CommandEnvelope(
        command_id=f"cmd-m6-2-live-{idem}",
        command_type=command_type,
        tenant_id="tenant-m6-2-live",
        project_id="project-m6-2-live",
        case_id="case-m6-2-live-synthetic",
        actor_snapshot_ref="actor-m6-2-live",
        permission_snapshot_ref="permission-m6-2-live",
        policy_config_refs=("point01-m6-2-live-test",),
        idempotency_key=idem,
        expected_state_version=expected,
        correlation_id="correlation-m6-2-live",
        requested_at=utc_now(),
        payload=payload,
    )


def _request() -> EvidenceRequest:
    payload = {
        "tenant_id": "tenant-m6-2-live",
        "project_id": "project-m6-2-live",
        "case_id": "case-m6-2-live-synthetic",
        "decision_surface_id": "surface-m6-2-live",
        "decision_surface_contract_version_id": "surface-m6-2-live:v1",
        "cell_id": "cell-m6-2-live",
        "cell_version_id": "cell-m6-2-live:v1",
        "evidence_slot_id": "slot-m6-2-live",
        "evidence_slot_version_id": "slot-m6-2-live:v1",
        "requester_role": "research_lead",
        "accepted_evidence_role": "numeric_fact",
        "evidence_domain": "issuer_disclosure",
        "target_entities": ("NVDA",),
        "target_periods": ("FY2026",),
        "metric_intent": ("revenue",),
        "product_intent": (),
        "granularity": "cell_slot",
        "unit": "USD",
        "source_policy": "issuer_first",
        "metadata_binding_requirements": ("document_id", "document_version", "section_or_table_ref", "source_authority"),
        "numeric_binding_requirements": ("row_label", "unit", "period", "source_coordinate"),
        "acceptable_proxy": (),
        "forbidden_substitutions": ("relationship_graph_only",),
        "preferred_routes": ("issuer_disclosure_metadata_route",),
        "fallback_routes": ("official_company_commentary_metadata_route",),
        "topk_policy": {"top_k": 3, "candidate_limit": 12},
        "budget": {"tool_call_limit": 3, "elapsed_seconds_limit": 90},
        "stop_condition": "exact_issuer_metadata_bound",
        "required": True,
        "compiler_policy_ref": "point01-m6-1-evidence-request-policy-v1",
        "compiled_from_refs": ("surface-m6-2-live:v1", "cell-m6-2-live:v1", "slot-m6-2-live:v1", "point01-m6-1-evidence-request-policy-v1"),
        "planning_authority": "shadow",
        "execution_admission": "not_admitted",
    }
    digest = canonical_digest(payload)
    return EvidenceRequest(request_id=f"evidence_request_{digest[:20]}", request_digest=digest, **payload)


def _plan(request: EvidenceRequest) -> ToolSelectionPlan:
    step = ToolSelectionStep(
        planner_step_id=f"{request.request_id}:step:1",
        request_id=request.request_id,
        state="SELECT_TOOL",
        selected_tool_id="issuer_disclosure_metadata_tool",
        selected_route_id="issuer_disclosure_metadata_route",
        selection_rationale="test-primary",
        budget_before=1,
        budget_after=0,
        required_capability="evidence.metadata.read",
    )
    payload = {
        "request_id": request.request_id,
        "request_digest": request.request_digest,
        "registry_snapshot_id": "point01-m6-2-tool-registry:v1",
        "registry_snapshot_digest": "registry-digest-m6-2-live",
        "planner_policy_ref": "point01-m6-2-bounded-planner-policy-v1",
        "permission_snapshot_ref": "permission-m6-2-live",
        "status": "await_execution_admission",
        "steps": (step,),
        "planned_tool_call_count": 1,
        "remaining_tool_call_budget": 0,
        "stop_reason": None,
        "execution_admission": "required_m5_4_capability_check",
        "persistence_admission": "not_admitted",
    }
    digest = canonical_digest({key: (value if key != "steps" else [step.model_dump(mode="json")]) for key, value in payload.items()})
    return ToolSelectionPlan(plan_id=f"tool_selection_plan_{digest[:20]}", plan_digest=digest, **payload)


def _policy() -> BoundedSecMetadataExecutionPolicy:
    source = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    return BoundedSecMetadataExecutionPolicy.model_validate(
        {field: source[field] for field in BoundedSecMetadataExecutionPolicy.model_fields}
    )


def seed_global_approval(tmp_path: Path, *, command: CommandEnvelope, request: EvidenceRequest, plan: ToolSelectionPlan, policy: BoundedSecMetadataExecutionPolicy):
    store = SQLiteCanonicalStore(tmp_path / "global-approval" / "canonical.sqlite")
    service = M6GlobalOneShotApprovalService(store=store)
    package = compute_m6_pilot_package(root=ROOT, manifest_path=PACKAGE_MANIFEST_PATH)
    scope = build_m6_pilot_scope(
        command=command,
        request=request,
        plan=plan,
        approval_ref=policy.approval_ref,
        approved_execution_scope=policy.approved_execution_scope,
        tool_id=policy.tool_id,
        route_id=policy.route_id,
        network_host=policy.allowed_network_host,
        target_cik=policy.allowed_cik,
    )
    receipt = M6GlobalOneShotApprovalReceipt.create(
        tenant_id="tenant-m6-global-approval-test",
        project_id="project-m6-global-approval-test",
        actor_snapshot_ref="human:william:003",
        permission_snapshot_ref="human-review:test",
        policy_config_refs=("point01-m6-2-global-one-shot-authority-policy-v1",),
        correlation_id="correlation-m6-global-approval-test",
        current_status="active",
        approval_id=TEST_APPROVAL_ID,
        approval_version=1,
        state_version=1,
        approval_state="active",
        approval_nonce="test-global-one-shot-nonce-0001",
        scope_digest=scope.scope_digest,
        package_ref=package.package_ref,
        package_digest=package.package_digest,
        package_manifest_digest=package.manifest_digest,
        reviewer_name="william",
        reviewer_employee_id="003",
        reviewer_role="total_reviewer",
        expires_at=utc_now() + timedelta(hours=1),
        authority_store_identity=store.store_identity(),
    )
    service.register_authoritative_receipt(receipt)
    return service, package


def _runtime(tmp_path: Path):
    facade = RuntimeFacade(
        SQLiteCanonicalStore(tmp_path / "canonical.sqlite"),
        FileCanonicalObjectStore(tmp_path / "objects"),
        _flags(),
        mode="shadow",
        grants={"point01.shadow.write"},
    )
    facade.create_research_case(_command("CREATE_RESEARCH_CASE", {"query": "M6.2 real bounded synthetic", "accountable_owner_ref": "owner-m6-2"}, idem="case"))
    scheduler = DurableSchedulerService(facade)
    scheduler.enqueue(_command("CREATE_WORK_UNIT", {"work_unit_id": "wu-m6-2-live", "input_version_refs": ["surface-m6-2-live:v1"], "queue_name": "m6-2-live", "max_attempts": 1}, idem="enqueue"))
    scheduler.claim_next(
        _command(
            "SCHEDULER_CLAIM_NEXT",
            {"queue_name": "m6-2-live", "work_unit_id": "wu-m6-2-live", "worker_ref": "worker-m6-2-live", "attempt_id": "attempt-m6-2-live-1", "lease_duration_seconds": 300},
            idem="claim",
        )
    )
    grant = CapabilityGrant(
        grant_id="grant-m6-2-sec-live",
        tenant_id="tenant-m6-2-live",
        project_id="project-m6-2-live",
        case_id="case-m6-2-live-synthetic",
        permission_snapshot_ref="permission-m6-2-live",
        capabilities=("evidence.metadata.read",),
        allowed_tool_ids=("issuer_disclosure_metadata_tool",),
        allowed_network_hosts=("data.sec.gov",),
        allowed_path_prefixes=("submissions",),
        allowed_data_classifications=("public",),
        issued_at=utc_now() - timedelta(minutes=5),
        expires_at=utc_now() + timedelta(hours=1),
    )
    security = CapabilitySecurityService(
        facade,
        grants=(grant,),
        tool_manifests=(
            ToolManifest(
                tool_id="issuer_disclosure_metadata_tool",
                capabilities=("evidence.metadata.read",),
                allowed_network_hosts=("data.sec.gov",),
                allowed_path_prefixes=("submissions",),
                allowed_data_classifications=("public",),
            ),
        ),
    )
    security.register_authority(_command("CAPABILITY_GRANT_RECORDED", {}, idem="grant"), grant)
    budgets = BudgetControlService(
        facade,
        policy=BudgetPolicy(
            policy_id="m6-2-live-budget",
            case_token_units=10,
            work_unit_token_units=10,
            attempt_token_units=10,
            case_tool_calls=1,
            work_unit_tool_calls=1,
            attempt_tool_calls=1,
            case_time_seconds=60,
            work_unit_time_seconds=60,
            attempt_time_seconds=60,
        ),
    )
    command = _command(
        "EXECUTE_M6_2_REAL_BOUNDED_SEC_METADATA",
        {"work_unit_id": "wu-m6-2-live", "attempt_id": "attempt-m6-2-live-1", "worker_ref": "worker-m6-2-live", "lease_fencing_token": 1},
        idem="execute",
        expected=1,
    )
    reservation = BudgetReservationRequest(
        reservation_id="reservation-m6-2-live",
        work_unit_id="wu-m6-2-live",
        attempt_id="attempt-m6-2-live-1",
        token_units=0,
        tool_calls=1,
        time_seconds=10,
    )
    global_service, package = seed_global_approval(
        tmp_path,
        command=command,
        request=_request(),
        plan=_plan(_request()),
        policy=_policy(),
    )
    facade._m6_global_approval_service = global_service
    facade._m6_pilot_package = package
    return facade, security, budgets, command, reservation


def _executor(facade, security, budgets) -> BoundedSecMetadataExecutor:
    return BoundedSecMetadataExecutor(
        facade=facade,
        security=security,
        budgets=budgets,
        policy=_policy(),
        global_approval_service=facade._m6_global_approval_service,
        global_approval_id=TEST_APPROVAL_ID,
        pilot_package=facade._m6_pilot_package,
    )


def _reopened_executor(tmp_path: Path) -> tuple[BoundedSecMetadataExecutor, RuntimeFacade, BudgetControlService]:
    """Open only durable local/global state after a child process exit."""
    facade = RuntimeFacade(
        SQLiteCanonicalStore(tmp_path / "canonical.sqlite"),
        FileCanonicalObjectStore(tmp_path / "objects"),
        _flags(),
        mode="shadow",
        grants={"point01.shadow.write"},
    )
    budgets = BudgetControlService(
        facade,
        policy=BudgetPolicy(
            policy_id="m6-2-live-budget",
            case_token_units=10,
            work_unit_token_units=10,
            attempt_token_units=10,
            case_tool_calls=1,
            work_unit_tool_calls=1,
            attempt_tool_calls=1,
            case_time_seconds=60,
            work_unit_time_seconds=60,
            attempt_time_seconds=60,
        ),
    )
    executor = BoundedSecMetadataExecutor(
        facade=facade,
        security=CapabilitySecurityService(facade, grants=(), tool_manifests=()),
        budgets=budgets,
        policy=_policy(),
        global_approval_service=M6GlobalOneShotApprovalService(
            store=SQLiteCanonicalStore(tmp_path / "global-approval" / "canonical.sqlite")
        ),
        global_approval_id=TEST_APPROVAL_ID,
        pilot_package=compute_m6_pilot_package(root=ROOT, manifest_path=PACKAGE_MANIFEST_PATH),
    )
    return executor, facade, budgets


def test_one_mocked_sec_metadata_call_is_admitted_budgeted_and_append_only(tmp_path: Path) -> None:
    facade, security, budgets, command, reservation = _runtime(tmp_path)
    request = _request()
    plan = _plan(request)
    session = _Session()
    client = SingleCallSecSubmissionsClient(user_agent="FINInsight-Agent/1.0 compliance@finsight.test", timeout_seconds=20, session=session)
    result = _executor(facade, security, budgets).execute(
        command=command,
        request=request,
        plan=plan,
        capability_grant_id="grant-m6-2-sec-live",
        reservation=reservation,
        target_cik="0001045810",
        client=client,
    )
    assert result.status == "succeeded"
    assert len(session.calls) == 1
    assert session.calls[0][0] == "https://data.sec.gov/submissions/CIK0001045810.json"
    assert session.calls[0][1]["allow_redirects"] is False
    assert result.receipt.external_call_count == 1
    assert result.receipt.source_metadata and result.receipt.source_metadata.issuer_name == "NVIDIA CORP"
    assert "raw" not in result.receipt.source_metadata.model_dump_json().lower()
    receipts = facade.store.list_versions("canonical_tool_invocation_receipt_versions")
    assert [row["invocation_state"] for row in receipts] == ["prepared", "send_authorized", "send_started", "succeeded"]
    assert [row["state_version"] for row in receipts] == [1, 2, 3, 4]
    assert all("@" not in row["user_agent_fingerprint"] for row in receipts)
    assert facade.store.get_latest("canonical_budget_reservation_versions", reservation.reservation_id)["reservation_state"] == "consumed"
    repeated = _executor(facade, security, budgets).execute(
        command=command,
        request=request,
        plan=plan,
        capability_grant_id="grant-m6-2-sec-live",
        reservation=reservation,
        target_cik="0001045810",
        client=client,
    )
    assert repeated.reused_terminal_receipt is True
    assert len(session.calls) == 1


def test_transport_failure_is_one_send_outcome_unknown_and_never_retried(tmp_path: Path) -> None:
    facade, security, budgets, command, reservation = _runtime(tmp_path)
    request = _request()
    plan = _plan(request)
    session = _FailingSession()
    client = SingleCallSecSubmissionsClient(user_agent="FINInsight-Agent/1.0 compliance@finsight.test", timeout_seconds=20, session=session)
    executor = _executor(facade, security, budgets)
    result = executor.execute(command=command, request=request, plan=plan, capability_grant_id="grant-m6-2-sec-live", reservation=reservation, target_cik="0001045810", client=client)
    assert result.status == "outcome_unknown"
    assert result.receipt.error_code == "sec_single_call_transport_error"
    assert len(session.calls) == 1
    assert facade.store.get_latest("canonical_budget_reservation_versions", reservation.reservation_id)["reservation_state"] == "consumed"
    repeated = executor.execute(command=command, request=request, plan=plan, capability_grant_id="grant-m6-2-sec-live", reservation=reservation, target_cik="0001045810", client=client)
    assert repeated.reused_terminal_receipt is True
    assert len(session.calls) == 1


def test_unapproved_cik_fails_before_admission_budget_or_network(tmp_path: Path) -> None:
    facade, security, budgets, command, reservation = _runtime(tmp_path)
    session = _Session()
    client = SingleCallSecSubmissionsClient(user_agent="FINInsight-Agent/1.0 compliance@finsight.test", timeout_seconds=20, session=session)
    with pytest.raises(RuntimeError, match="execution_cik_not_approved"):
        _executor(facade, security, budgets).execute(
            command=command,
            request=_request(),
            plan=_plan(_request()),
            capability_grant_id="grant-m6-2-sec-live",
            reservation=reservation,
            target_cik="0000789019",
            client=client,
        )
    assert not session.calls
    assert not facade.store.list_versions("canonical_tool_invocation_receipt_versions")
    assert not facade.store.list_versions("canonical_budget_reservation_versions")


def test_revocation_after_prepare_is_rechecked_before_send_and_refunded(tmp_path: Path) -> None:
    facade, security, budgets, command, reservation = _runtime(tmp_path)
    session = _Session()
    client = SingleCallSecSubmissionsClient(user_agent="FINInsight-Agent/1.0 compliance@finsight.test", timeout_seconds=20, session=session)
    executor = BoundedSecMetadataExecutor(
        facade=facade,
        security=_RevokingSecurity(security, command),
        budgets=budgets,
        policy=_policy(),
        global_approval_service=facade._m6_global_approval_service,
        global_approval_id=TEST_APPROVAL_ID,
        pilot_package=facade._m6_pilot_package,
    )
    result = executor.execute(
        command=command,
        request=_request(),
        plan=_plan(_request()),
        capability_grant_id="grant-m6-2-sec-live",
        reservation=reservation,
        target_cik="0001045810",
        client=client,
    )
    assert result.status == "blocked_before_send"
    assert not session.calls
    assert [row["invocation_state"] for row in facade.store.list_versions("canonical_tool_invocation_receipt_versions")] == ["prepared", "blocked_before_send"]
    reservation_row = facade.store.get_latest("canonical_budget_reservation_versions", reservation.reservation_id)
    assert reservation_row and reservation_row["reservation_state"] == "released"


def test_budget_consume_failure_after_send_reconciles_without_resend(tmp_path: Path) -> None:
    facade, security, budgets, command, reservation = _runtime(tmp_path)
    session = _Session()
    client = SingleCallSecSubmissionsClient(user_agent="FINInsight-Agent/1.0 compliance@finsight.test", timeout_seconds=20, session=session)
    executor = _executor(facade, security, _FailOnceConsumeBudget(budgets))
    with pytest.raises(RuntimeError, match="simulated_budget_consume_write_failure_after_send"):
        executor.execute(
            command=command,
            request=_request(),
            plan=_plan(_request()),
            capability_grant_id="grant-m6-2-sec-live",
            reservation=reservation,
            target_cik="0001045810",
            client=client,
        )
    assert len(session.calls) == 1
    assert facade.store.get_latest("canonical_tool_invocation_receipt_versions", _executor(facade, security, budgets)._invocation_id(request=_request(), plan=_plan(_request()), target_cik="0001045810"))["invocation_state"] == "send_started"
    reconciled = _executor(facade, security, budgets).reconcile(
        command=command,
        request=_request(),
        plan=_plan(_request()),
        reservation=reservation,
        target_cik="0001045810",
    )
    assert reconciled.status == "outcome_unknown"
    assert facade.store.get_latest("canonical_budget_reservation_versions", reservation.reservation_id)["reservation_state"] == "consumed"
    repeated = _executor(facade, security, budgets).execute(
        command=command,
        request=_request(),
        plan=_plan(_request()),
        capability_grant_id="grant-m6-2-sec-live",
        reservation=reservation,
        target_cik="0001045810",
        client=client,
    )
    assert repeated.reused_terminal_receipt is True
    assert len(session.calls) == 1


def test_terminal_receipt_write_failure_after_send_reconciles_without_resend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    facade, security, budgets, command, reservation = _runtime(tmp_path)
    session = _Session()
    client = SingleCallSecSubmissionsClient(user_agent="FINInsight-Agent/1.0 compliance@finsight.test", timeout_seconds=20, session=session)
    executor = _executor(facade, security, budgets)
    original = executor._record_receipt

    def fail_terminal(**kwargs):
        if kwargs["invocation_state"] == "succeeded":
            raise RuntimeError("simulated_terminal_receipt_write_failure_after_send")
        return original(**kwargs)

    monkeypatch.setattr(executor, "_record_receipt", fail_terminal)
    with pytest.raises(RuntimeError, match="simulated_terminal_receipt_write_failure_after_send"):
        executor.execute(
            command=command,
            request=_request(),
            plan=_plan(_request()),
            capability_grant_id="grant-m6-2-sec-live",
            reservation=reservation,
            target_cik="0001045810",
            client=client,
        )
    assert len(session.calls) == 1
    monkeypatch.setattr(executor, "_record_receipt", original)
    reconciled = executor.reconcile(
        command=command,
        request=_request(),
        plan=_plan(_request()),
        reservation=reservation,
        target_cik="0001045810",
    )
    assert reconciled.status == "outcome_unknown"
    repeated = executor.execute(
        command=command,
        request=_request(),
        plan=_plan(_request()),
        capability_grant_id="grant-m6-2-sec-live",
        reservation=reservation,
        target_cik="0001045810",
        client=client,
    )
    assert repeated.reused_terminal_receipt is True
    assert len(session.calls) == 1


@pytest.mark.requires_subprocess
def test_child_process_exit_after_http_send_reopens_and_never_resends(tmp_path: Path) -> None:
    """The child exits after mocked HTTP return; parent only reconciles durable facts."""
    child = "\n".join(
        (
            "import importlib.util, os, sys",
            f"sys.path.insert(0, {str(ROOT / 'src')!r})",
            f"spec = importlib.util.spec_from_file_location('m6_child_helpers', {str(Path(__file__).resolve())!r})",
            "module = importlib.util.module_from_spec(spec)",
            "spec.loader.exec_module(module)",
            "facade, security, budgets, command, reservation = module._runtime(__import__('pathlib').Path(sys.argv[1]))",
            "executor = module.BoundedSecMetadataExecutor(facade=facade, security=security, budgets=budgets, policy=module._policy(), global_approval_service=facade._m6_global_approval_service, global_approval_id=module.TEST_APPROVAL_ID, pilot_package=facade._m6_pilot_package, after_http_send_hook=lambda: os._exit(73))",
            "executor.execute(command=command, request=module._request(), plan=module._plan(module._request()), capability_grant_id='grant-m6-2-sec-live', reservation=reservation, target_cik='0001045810', client=module.SingleCallSecSubmissionsClient(user_agent='FINInsight-Agent/1.0 compliance@finsight.test', timeout_seconds=20, session=module._Session()))",
        )
    )
    environment = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    completed = subprocess.run(
        [sys.executable, "-c", child, str(tmp_path)],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 73, completed.stderr
    executor, facade, _ = _reopened_executor(tmp_path)
    command = _command(
        "EXECUTE_M6_2_REAL_BOUNDED_SEC_METADATA",
        {"work_unit_id": "wu-m6-2-live", "attempt_id": "attempt-m6-2-live-1", "worker_ref": "worker-m6-2-live", "lease_fencing_token": 1},
        idem="execute",
        expected=1,
    )
    reservation = BudgetReservationRequest(
        reservation_id="reservation-m6-2-live",
        work_unit_id="wu-m6-2-live",
        attempt_id="attempt-m6-2-live-1",
        token_units=0,
        tool_calls=1,
        time_seconds=10,
    )
    reconciled = executor.reconcile(command=command, request=_request(), plan=_plan(_request()), reservation=reservation, target_cik="0001045810")
    assert reconciled.status == "outcome_unknown"
    assert facade.store.get_latest("canonical_budget_reservation_versions", reservation.reservation_id)["reservation_state"] == "consumed"
    receipt_rows = facade.store.list_versions("canonical_tool_invocation_receipt_versions")
    assert [row["invocation_state"] for row in receipt_rows] == ["prepared", "send_authorized", "send_started", "outcome_unknown"]


def test_live_runner_refuses_to_invent_missing_sec_user_agent(tmp_path: Path) -> None:
    output = tmp_path / "missing-user-agent.json"
    environment = {key: value for key, value in os.environ.items() if key != "SEC_USER_AGENT"}
    completed = subprocess.run(
        [sys.executable, str(LIVE_RUNNER_PATH), "--execute-live", "--output", str(output)],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 1
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["status"] == "fail_closed"
    assert result["reason"] == "required_environment_variable_missing:SEC_USER_AGENT"
    assert result["external_call_count"] == result["store_write_count"] == 0
