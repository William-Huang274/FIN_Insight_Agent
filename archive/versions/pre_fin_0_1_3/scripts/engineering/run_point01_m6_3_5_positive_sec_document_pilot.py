"""Freeze or (only after a new receipt) execute the M6.3/M6.5 NVDA 10-K pilot.

The default command is package-freeze only.  It makes no store, network,
parser or model call and is the only command run in this implementation slice.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any

import requests


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.canonical_runtime.bounded_sec_document_execution import (
    BoundedSecDocumentExecutionPolicy,
    BoundedSecDocumentExecutor,
    SingleCallSecDocumentClient,
)
from sec_agent.canonical_runtime.budget_control import BudgetControlService, BudgetPolicy, BudgetReservationRequest
from sec_agent.canonical_runtime.capability_security import CapabilityGrant, CapabilitySecurityService, ToolManifest
from sec_agent.canonical_runtime.durable_scheduler import DurableSchedulerService
from sec_agent.canonical_runtime.evidence_request import EvidenceRequest
from sec_agent.canonical_runtime.facade import RuntimeFacade
from sec_agent.canonical_runtime.feature_flags import FeatureFlagRegistry
from sec_agent.canonical_runtime.m6_pilot_global_approval import M6GlobalOneShotApprovalError, M6GlobalOneShotApprovalService, build_m6_pilot_scope
from sec_agent.canonical_runtime.m6_pilot_package import compute_m6_pilot_package
from sec_agent.canonical_runtime.models import CommandEnvelope, canonical_digest, utc_now
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.canonical_runtime.store import SQLiteCanonicalStore
from sec_agent.canonical_runtime.tool_planner import BoundedToolPlanner, PlannerPermissionContext, PlannerPolicy, ToolRegistryEntry, ToolRegistrySnapshot, ToolSelectionPlan


POLICY_PATH = ROOT / "configs/engineering_handoff/point01_m6_3_5_positive_sec_document_pilot_policy_v1_0.json"
AUTHORITY_POLICY_PATH = ROOT / "configs/engineering_handoff/point01_m6_3_5_positive_sec_document_global_one_shot_authority_policy_v1_0.json"
PACKAGE_MANIFEST_PATH = ROOT / "configs/engineering_handoff/point01_m6_3_5_positive_sec_document_package_manifest_v1_0.json"
DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m6_3_5_positive_sec_document_package_freeze_result_v1_0.json"
DEFAULT_STORE_ROOT = ROOT / ".tmp_point01_m6_3_5_positive_sec_document_pilot"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def _policy() -> BoundedSecDocumentExecutionPolicy:
    raw = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    return BoundedSecDocumentExecutionPolicy.model_validate({field: raw[field] for field in BoundedSecDocumentExecutionPolicy.model_fields})


def _authority_policy() -> dict[str, Any]:
    raw = json.loads(AUTHORITY_POLICY_PATH.read_text(encoding="utf-8"))
    relative = Path(str(raw.get("fixed_approval_store_relative_path") or ""))
    resolved = (ROOT / relative).resolve()
    if not relative or ROOT.resolve() not in resolved.parents:
        raise RuntimeError("positive_sec_document_global_approval_store_path_invalid")
    if not str(raw.get("approval_id") or "").strip():
        raise RuntimeError("positive_sec_document_global_approval_id_required")
    return raw


def _authority_store_root() -> Path:
    return (ROOT / str(_authority_policy()["fixed_approval_store_relative_path"])).resolve()


def _command(command_type: str, payload: dict[str, Any], *, idem: str, expected: int = 0) -> CommandEnvelope:
    return CommandEnvelope(
        command_id=f"cmd-point01-m6-3-5-positive-sec-document-{idem}",
        command_type=command_type,
        tenant_id="tenant-point01-m6-positive-sec-document",
        project_id="project-point01-m6-positive-sec-document",
        case_id="case-point01-m6-positive-sec-document-nvda",
        actor_snapshot_ref="actor-point01-m6-positive-sec-document",
        permission_snapshot_ref="permission-point01-m6-positive-sec-document",
        policy_config_refs=("point01-m6-3-5-positive-sec-document-pilot-policy-v4-incident-isolation-refreeze",),
        idempotency_key=idem,
        expected_state_version=expected,
        correlation_id="correlation-point01-m6-positive-sec-document-nvda",
        requested_at=utc_now(),
        payload=payload,
    )


def _request() -> EvidenceRequest:
    payload: dict[str, Any] = {
        "tenant_id": "tenant-point01-m6-positive-sec-document",
        "project_id": "project-point01-m6-positive-sec-document",
        "case_id": "case-point01-m6-positive-sec-document-nvda",
        "decision_surface_id": "surface-point01-m6-positive-sec-document-nvda",
        "decision_surface_contract_version_id": "surface-point01-m6-positive-sec-document-nvda:v1",
        "cell_id": "cell-point01-m6-positive-sec-document-nvda-revenue",
        "cell_version_id": "cell-point01-m6-positive-sec-document-nvda-revenue:v1",
        "evidence_slot_id": "slot-point01-m6-positive-sec-document-nvda-revenue",
        "evidence_slot_version_id": "slot-point01-m6-positive-sec-document-nvda-revenue:v1",
        "requester_role": "fundamental_analyst",
        "accepted_evidence_role": "numeric_fact",
        "evidence_domain": "issuer_disclosure",
        "target_entities": ("NVDA",),
        "target_periods": ("2025-01-26",),
        "metric_intent": ("revenue",),
        "product_intent": (),
        "granularity": "cell_slot",
        "unit": "USD",
        "source_policy": "issuer_first",
        "metadata_binding_requirements": ("document_id", "document_version", "section_or_table_ref", "source_authority"),
        "numeric_binding_requirements": ("row_label", "unit", "period", "source_coordinate"),
        "acceptable_proxy": (),
        "forbidden_substitutions": ("relationship_graph_only", "reviewer_oracle_value"),
        "preferred_routes": ("issuer_filing_document_table_route",),
        "fallback_routes": (),
        "topk_policy": {"top_k": 1, "candidate_limit": 1},
        "budget": {"tool_call_limit": 1, "elapsed_seconds_limit": 20},
        "stop_condition": "exact_sec_document_table_or_typed_terminal_stop",
        "required": True,
        "compiler_policy_ref": "point01-m6-1-evidence-request-policy-v1",
        "compiled_from_refs": (
            "surface-point01-m6-positive-sec-document-nvda:v1",
            "cell-point01-m6-positive-sec-document-nvda-revenue:v1",
            "slot-point01-m6-positive-sec-document-nvda-revenue:v1",
            "point01-m6-1-evidence-request-policy-v1",
        ),
        "planning_authority": "shadow",
        "execution_admission": "not_admitted",
    }
    digest = canonical_digest(payload)
    return EvidenceRequest(request_id=f"evidence_request_{digest[:20]}", request_digest=digest, **payload)


def _plan(request: EvidenceRequest, policy: BoundedSecDocumentExecutionPolicy) -> ToolSelectionPlan:
    entry = ToolRegistryEntry(
        tool_id=policy.tool_id,
        tool_name="Exact SEC filing document/table reader",
        capabilities=(policy.capability,),
        input_schema_ref="point01-m6-3-5-exact-sec-document-input-v2-parser-repair",
        output_schema_ref="point01-m6-3-5-unpromoted-table-numeric-output-v2-parser-repair",
        source_role="issuer_filing",
        source_authority="official_issuer_filing",
        source_authority_rank=4,
        can_support=("exact_sec_document_table",),
        cannot_support=("web_search", "directory_listing", "fallback", "evidence_promotion"),
        cost_class="single_public_http_get",
        cost_rank=1,
        latency_class="bounded_http",
        failure_types=("transport_unknown", "selector_missing", "selector_ambiguous"),
        permission_scope="runtime_read_only",
        forbidden_claims=("formal_evidence", "writer_citation", "domain_judgment"),
        supported_evidence_roles=("numeric_fact",),
        supported_source_policy_refs=("issuer_first",),
        declared_route_ids=(policy.route_id,),
    )
    registry = ToolRegistrySnapshot.create(registry_id="point01-m6-3-5-positive-sec-document-registry", registry_version=1, entries=(entry,))
    result = BoundedToolPlanner(
        registry=registry,
        policy=PlannerPolicy(
            policy_ref="point01-m6-3-5-positive-sec-document-planner-policy-v2-parser-repair",
            max_tool_calls=1,
            max_fallback_depth=0,
            required_permission_scope="runtime_read_only",
            minimum_source_authority_rank_by_evidence_role={"numeric_fact": 4},
            required_execution_admission="required_m5_4_capability_check",
            stop_rules=("exact_route_only", "no_fallback", "no_retry"),
        ),
    ).plan(
        request=request,
        permissions=PlannerPermissionContext(
            permission_snapshot_ref="permission-point01-m6-positive-sec-document",
            allowed_tool_ids=(policy.tool_id,),
            required_permission_scope="runtime_read_only",
        ),
    )
    return result.plan


def _runtime(store_root: Path, policy: BoundedSecDocumentExecutionPolicy) -> tuple[RuntimeFacade, CapabilitySecurityService, BudgetControlService, CommandEnvelope, BudgetReservationRequest]:
    facade = RuntimeFacade(SQLiteCanonicalStore(store_root / "canonical.sqlite"), FileCanonicalObjectStore(store_root / "objects"), _flags(), mode="shadow", grants={"point01.shadow.write"})
    facade.create_research_case(_command("CREATE_RESEARCH_CASE", {"query": "Synthetic M6.3/M6.5 exact NVDA 10-K document pilot", "accountable_owner_ref": "point01-m6-positive-sec-document-owner"}, idem="case"))
    scheduler = DurableSchedulerService(facade)
    scheduler.enqueue(_command("CREATE_WORK_UNIT", {"work_unit_id": "wu-point01-m6-positive-sec-document", "input_version_refs": ["surface-point01-m6-positive-sec-document-nvda:v1"], "queue_name": "point01-m6-positive-sec-document", "max_attempts": 1}, idem="enqueue"))
    scheduler.claim_next(_command("SCHEDULER_CLAIM_NEXT", {"queue_name": "point01-m6-positive-sec-document", "work_unit_id": "wu-point01-m6-positive-sec-document", "worker_ref": "worker-point01-m6-positive-sec-document", "attempt_id": "attempt-point01-m6-positive-sec-document-1", "lease_duration_seconds": 300}, idem="claim"))
    grant = CapabilityGrant(
        grant_id="grant-point01-m6-positive-sec-document",
        tenant_id="tenant-point01-m6-positive-sec-document",
        project_id="project-point01-m6-positive-sec-document",
        case_id="case-point01-m6-positive-sec-document-nvda",
        permission_snapshot_ref="permission-point01-m6-positive-sec-document",
        capabilities=(policy.capability,),
        allowed_tool_ids=(policy.tool_id,),
        allowed_network_hosts=(policy.allowed_network_host,),
        allowed_path_prefixes=("Archives/edgar/data",),
        allowed_data_classifications=("public",),
        issued_at=utc_now() - timedelta(minutes=1),
        expires_at=utc_now() + timedelta(minutes=10),
    )
    security = CapabilitySecurityService(
        facade,
        grants=(grant,),
        tool_manifests=(ToolManifest(tool_id=policy.tool_id, capabilities=(policy.capability,), allowed_network_hosts=(policy.allowed_network_host,), allowed_path_prefixes=("Archives/edgar/data",), allowed_data_classifications=("public",)),),
    )
    security.register_authority(_command("CAPABILITY_GRANT_RECORDED", {}, idem="grant"), grant)
    budgets = BudgetControlService(
        facade,
        policy=BudgetPolicy(
            policy_id="point01-m6-positive-sec-document-budget-v1",
            case_token_units=10, work_unit_token_units=10, attempt_token_units=10,
            case_tool_calls=1, work_unit_tool_calls=1, attempt_tool_calls=1,
            case_time_seconds=60, work_unit_time_seconds=60, attempt_time_seconds=60,
        ),
    )
    command = _command("EXECUTE_M6_3_5_POSITIVE_SEC_DOCUMENT", {"work_unit_id": "wu-point01-m6-positive-sec-document", "attempt_id": "attempt-point01-m6-positive-sec-document-1", "worker_ref": "worker-point01-m6-positive-sec-document", "lease_fencing_token": 1}, idem="execute", expected=1)
    reservation = BudgetReservationRequest(reservation_id="reservation-point01-m6-positive-sec-document", work_unit_id="wu-point01-m6-positive-sec-document", attempt_id="attempt-point01-m6-positive-sec-document-1", token_units=0, tool_calls=1, time_seconds=20)
    return facade, security, budgets, command, reservation


def _approval_scope(command: CommandEnvelope, request: EvidenceRequest, plan: ToolSelectionPlan, policy: BoundedSecDocumentExecutionPolicy):
    return build_m6_pilot_scope(
        command=command,
        request=request,
        plan=plan,
        approval_ref=policy.approval_ref,
        approved_execution_scope=policy.approved_execution_scope,
        tool_id=policy.tool_id,
        route_id=policy.route_id,
        network_host=policy.allowed_network_host,
        target_cik=policy.allowed_cik,
        endpoint_path=policy.exact_path,
        execution_policy_digest=canonical_digest(policy),
    )


def _scope_digest(command: CommandEnvelope, request: EvidenceRequest, plan: ToolSelectionPlan, policy: BoundedSecDocumentExecutionPolicy) -> str:
    return _approval_scope(command, request, plan, policy).scope_digest


def _freeze_context() -> tuple[dict[str, Any], BoundedSecDocumentExecutionPolicy, dict[str, Any], Any, EvidenceRequest, ToolSelectionPlan, CommandEnvelope]:
    """Build deterministic package/scope data without opening any authority store.

    This importable path is intentionally incapable of creating a runtime,
    constructing a transport, reading the fixed approval store, or sending a
    request.  The CLI owns those side effects behind its explicit live flag.
    """
    policy = _policy()
    authority = _authority_policy()
    package = compute_m6_pilot_package(root=ROOT, manifest_path=PACKAGE_MANIFEST_PATH)
    request = _request()
    plan = _plan(request, policy)
    command = _command("PACKAGE_FREEZE_M6_3_5_POSITIVE_SEC_DOCUMENT", {"work_unit_id": "wu-point01-m6-positive-sec-document", "attempt_id": "attempt-point01-m6-positive-sec-document-1", "worker_ref": "worker-point01-m6-positive-sec-document", "lease_fencing_token": 1}, idem="package-freeze", expected=1)
    common = {
        "result_version": "finsight_point01_m6_3_5_positive_sec_document_package_freeze_result_v1_1",
        "generated_at": utc_now().isoformat(),
        "scope": "single_exact_nvda_10k_sec_archives_document_artifact_contract_remediation_refreeze_only",
        "execution_state": "artifact_contract_remediated_refrozen_pending_total_reviewer",
        "approval_ref": policy.approval_ref,
        "global_approval_id": authority["approval_id"],
        "global_approval_store_relative_path": authority["fixed_approval_store_relative_path"],
        "approval_package": package.model_dump(mode="json"),
        "scope_digest": _scope_digest(command, request, plan, policy),
        "request": {"request_id": request.request_id, "request_digest": request.request_digest},
        "plan": {"plan_id": plan.plan_id, "plan_digest": plan.plan_digest, "registry_snapshot_id": plan.registry_snapshot_id, "registry_snapshot_digest": plan.registry_snapshot_digest},
        "fixed_target": {"cik": policy.allowed_cik, "accession_number": policy.accession_number, "exact_path": policy.exact_path, "form_type": policy.form_type, "report_period": policy.report_period, "selector_digest": canonical_digest(policy.target_table_selector)},
        "package_authority_boundary": {"max_external_calls": 1, "max_fallback_calls": 0, "max_retry_calls": 0, "live_send_requires_separate_exact_receipt": True, "old_m6_2_receipt_reusable": False, "old_user_agent_authority_reusable": False, "reviewer_blind_oracle_runtime_input": False, "raw_document_persistence": False, "evidence_promotion": False, "writer_domain_judgment_m6_7_full_chain": False, "business_case_mutation": False, "legacy_authority_change": False},
        "fixed_input_sha256": {
            "configs/engineering_handoff/point01_m6_3_5_positive_sec_document_pilot_policy_v1_0.json": _sha256(POLICY_PATH),
            "configs/engineering_handoff/point01_m6_3_5_positive_sec_document_global_one_shot_authority_policy_v1_0.json": _sha256(AUTHORITY_POLICY_PATH),
            "scripts/engineering/run_point01_m6_3_5_positive_sec_document_pilot.py": _sha256(Path(__file__).resolve()),
            "src/sec_agent/canonical_runtime/bounded_sec_document_execution.py": _sha256(ROOT / "src/sec_agent/canonical_runtime/bounded_sec_document_execution.py"),
        },
    }
    return common, policy, authority, package, request, plan, command


def build_result() -> dict[str, Any]:
    """Return a deterministic package freeze result with no authority or transport access."""
    common, *_ = _freeze_context()
    return {
        **common,
        "status": "artifact_contract_remediated_refrozen_pending_total_reviewer",
        "external_call_count": 0,
        "tool_invocation_count": 0,
        "parser_execution_count": 0,
        "numeric_fact_count": 0,
        "store_write_count": 0,
        "reason": "deterministic_package_freeze_no_authority_store_or_transport_access",
}


def _terminal_execution_state(status: str) -> str:
    return {
        "positive_chain_persisted": "approved_single_live_pilot_succeeded",
        "typed_terminal_stop": "approved_single_live_pilot_typed_stop",
        "outcome_unknown": "approved_single_live_pilot_outcome_unknown",
        "blocked_before_send": "approved_single_live_pilot_blocked_before_send",
    }[status]


def _live_terminal_result(*, common: dict[str, Any], result: Any, facade: RuntimeFacade, store_root: Path) -> dict[str, Any]:
    """Project an execution result without reusing package-freeze semantics.

    A package boundary is static policy.  A terminal result instead records the
    exact receipt that authorized this one execution and its resulting state.
    The projection contains no raw nonce, raw source document, or User-Agent.
    """
    receipt = result.receipt
    execution_state = _terminal_execution_state(result.status)
    execution_authorization_snapshot = {
        "authorization_kind": "fixed_store_exact_one_shot_receipt",
        "live_send_authorized_by_exact_receipt": True,
        "receipt_identity": f"{receipt.global_approval_id}:consumed",
        "receipt_state": "consumed",
        "approval_nonce_sha256": receipt.global_approval_nonce_sha256,
        "approval_activation_digest": receipt.global_approval_activation_digest,
        "receipt_digest": receipt.global_approval_receipt_digest,
        "authority_store_identity": receipt.global_approval_store_identity,
        "execution_instance_id": receipt.invocation_id,
    }
    execution_outcome = {
        "execution_status": result.status,
        "invocation_state": receipt.invocation_state,
        "downstream_status": receipt.downstream_status,
        "external_call_count": result.external_call_count,
        "tool_invocation_count": result.tool_invocation_count,
        "retry_call_count": receipt.retry_call_count,
        "fallback_call_count": receipt.fallback_call_count,
        "model_call_count": result.model_call_count,
        "raw_document_persisted": False,
        "source_document_sha256": receipt.source_document.document_content_sha256 if receipt.source_document else None,
        "response_status_code": receipt.source_document.response_status_code if receipt.source_document else None,
        "terminal_receipt_ref": f"{receipt.invocation_id}:v{receipt.invocation_version}",
    }
    return {
        "result_version": "finsight_point01_m6_3_5_live_terminal_result_v1_0",
        "generated_at": utc_now().isoformat(),
        "scope": common["scope"],
        "execution_state": execution_state,
        "status": "pass" if result.status == "positive_chain_persisted" else "fail_closed",
        "approval_ref": common["approval_ref"],
        "approval_package": common["approval_package"],
        "scope_digest": common["scope_digest"],
        "fixed_target": common["fixed_target"],
        "request": common["request"],
        "plan": common["plan"],
        "package_authority_boundary": common["package_authority_boundary"],
        "execution_authorization_snapshot": execution_authorization_snapshot,
        "execution_outcome": execution_outcome,
        "artifact_authority": {
            "candidate_parser_fact_trace": "unpromoted_non_citable_only",
            "evidence_promotion": False,
            "writer_citable": False,
            "domain_judgment_eligible": False,
            "downstream_consumption": "forbidden_pending_audit",
        },
        "store_root": str(store_root),
        "store_identity": facade.store.store_identity(),
        "store_content_fingerprint": facade.store.content_fingerprint(),
        "receipt": receipt.model_dump(mode="json"),
        "candidate": result.candidate.model_dump(mode="json") if result.candidate else None,
        "parser": result.parser.model_dump(mode="json") if result.parser else None,
        "fact": result.fact.model_dump(mode="json") if result.fact else None,
        "trace": result.trace.model_dump(mode="json") if result.trace else None,
        "terminal_stop": result.terminal_stop.model_dump(mode="json") if result.terminal_stop else None,
        "external_call_count": result.external_call_count,
        "tool_invocation_count": result.tool_invocation_count,
        "parser_execution_count": 1 if result.parser else 0,
        "numeric_fact_count": 1 if result.fact else 0,
        "store_write_count": result.store_write_count,
    }


def execute_with_injected_dependencies(
    *,
    store_root: Path,
    approval_service: M6GlobalOneShotApprovalService | None,
    client: SingleCallSecDocumentClient | None,
    process_local_user_agent_scope_confirmed: bool,
) -> dict[str, Any]:
    """Execute only against explicit authority and transport dependencies.

    This library seam never resolves the production approval-store path and
    never creates a real HTTP client. Missing injection fails before any
    receipt lookup, local-runtime creation, store write, or possible send.
    """
    common, policy, authority, package, request, plan, command = _freeze_context()
    denied = {
        "external_call_count": 0,
        "tool_invocation_count": 0,
        "parser_execution_count": 0,
        "numeric_fact_count": 0,
        "store_write_count": 0,
    }
    if approval_service is None:
        return {**common, **denied, "status": "fail_closed", "reason": "injected_authority_service_required_before_receipt_or_runtime_access"}
    if client is None:
        return {**common, **denied, "status": "fail_closed", "reason": "injected_non_network_or_explicit_cli_client_required_before_receipt_or_runtime_access"}
    if not process_local_user_agent_scope_confirmed:
        return {**common, **denied, "status": "fail_closed", "reason": "process_local_sec_user_agent_scope_confirmation_required"}
    try:
        approval_service.verify_active_exact_receipt(
            scope=_approval_scope(command, request, plan, policy),
            package_ref=package.package_ref,
            package_digest=package.package_digest,
            package_manifest_digest=package.manifest_digest,
            approval_id=str(authority["approval_id"]),
        )
    except M6GlobalOneShotApprovalError as exc:
        return {**common, **denied, "status": "fail_closed", "reason": str(exc)}
    facade, security, budgets, execution_command, reservation = _runtime(store_root, policy)
    try:
        result = BoundedSecDocumentExecutor(facade=facade, security=security, budgets=budgets, policy=policy, global_approval_service=approval_service, global_approval_id=str(authority["approval_id"]), pilot_package=package).execute(command=execution_command, request=request, plan=plan, capability_grant_id="grant-point01-m6-positive-sec-document", reservation=reservation, client=client)
    except M6GlobalOneShotApprovalError as exc:
        return {**common, **denied, "status": "fail_closed", "reason": str(exc)}
    return _live_terminal_result(common=common, result=result, facade=facade, store_root=store_root)


def _explicit_cli_live_dependencies(
    *,
    policy: BoundedSecDocumentExecutionPolicy,
    authority: dict[str, Any],
    package: Any,
    request: EvidenceRequest,
    plan: ToolSelectionPlan,
    command: CommandEnvelope,
) -> tuple[M6GlobalOneShotApprovalService | None, SingleCallSecDocumentClient | None, str | None]:
    """Create production authority/transport only in the explicit CLI live entrypoint."""
    user_agent = os.getenv(policy.user_agent_environment_variable, "").strip()
    scope_confirmation = os.getenv(policy.user_agent_scope_confirmation_environment_variable, "").strip()
    if not user_agent or scope_confirmation != "confirmed_for_new_receipt":
        return None, None, "new_process_local_sec_user_agent_scope_confirmation_required"
    database_path = _authority_store_root() / "canonical.sqlite"
    if not database_path.is_file():
        return None, None, "fixed_approval_store_missing"
    reviewer = authority["required_reviewer"]
    approval_service = M6GlobalOneShotApprovalService(
        store=SQLiteCanonicalStore(database_path),
        required_reviewer_name=str(reviewer["name"]),
        required_reviewer_employee_id=str(reviewer["employee_id"]),
        required_reviewer_role=str(reviewer["role"]),
    )
    try:
        approval_service.verify_active_exact_receipt(
            scope=_approval_scope(command, request, plan, policy),
            package_ref=package.package_ref,
            package_digest=package.package_digest,
            package_manifest_digest=package.manifest_digest,
            approval_id=str(authority["approval_id"]),
        )
    except M6GlobalOneShotApprovalError as exc:
        return None, None, str(exc)
    return (
        approval_service,
        SingleCallSecDocumentClient(
            user_agent=user_agent,
            timeout_seconds=policy.timeout_seconds,
            user_agent_min_length=policy.user_agent_min_length,
            forbidden_user_agent_values=policy.forbidden_user_agent_values,
            session=requests.Session(),
        ),
        None,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze or explicitly run the bounded Point01 M6.3/M6.5 SEC document pilot.")
    parser.add_argument("--execute-live", action="store_true", help="Requires a package-external, active exact one-shot receipt in the fixed approval store and a new process-local scope confirmation.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--store-root", type=Path, default=DEFAULT_STORE_ROOT)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    store_root = args.store_root if args.store_root.is_absolute() else ROOT / args.store_root
    if not args.execute_live:
        result = build_result()
    else:
        common, policy, authority, package, request, plan, command = _freeze_context()
        approval_service, client, reason = _explicit_cli_live_dependencies(
            policy=policy,
            authority=authority,
            package=package,
            request=request,
            plan=plan,
            command=command,
        )
        if reason:
            result = {
                **common,
                "status": "fail_closed",
                "reason": reason,
                "external_call_count": 0,
                "tool_invocation_count": 0,
                "parser_execution_count": 0,
                "numeric_fact_count": 0,
                "store_write_count": 0,
            }
        else:
            result = execute_with_injected_dependencies(
                store_root=store_root,
                approval_service=approval_service,
                client=client,
                process_local_user_agent_scope_confirmed=True,
            )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "external_call_count": result["external_call_count"], "output": str(output)}, ensure_ascii=False))
    return 0 if result["status"] in {"artifact_contract_remediated_refrozen_pending_total_reviewer", "pass"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
