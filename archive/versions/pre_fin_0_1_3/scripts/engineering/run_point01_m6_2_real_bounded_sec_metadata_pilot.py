"""Run the explicitly approved one-call SEC metadata pilot.

Live execution is opt-in.  The script never falls back to a placeholder SEC
identity, never retries, and keeps its temporary SQLite store under an ignored
path.  Its checked-in result contains only audit metadata and digests, never a
raw SEC response body.
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


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.canonical_runtime.bounded_sec_metadata_execution import (
    BoundedSecMetadataExecutionPolicy,
    BoundedSecMetadataExecutor,
    SingleCallSecSubmissionsClient,
)
from sec_agent.canonical_runtime.budget_control import BudgetControlService, BudgetPolicy, BudgetReservationRequest
from sec_agent.canonical_runtime.capability_security import CapabilityGrant, CapabilitySecurityService, ToolManifest
from sec_agent.canonical_runtime.durable_scheduler import DurableSchedulerService
from sec_agent.canonical_runtime.evidence_request import EvidenceRequest
from sec_agent.canonical_runtime.feature_flags import FeatureFlagRegistry
from sec_agent.canonical_runtime.facade import RuntimeFacade
from sec_agent.canonical_runtime.m6_pilot_global_approval import M6GlobalOneShotApprovalService
from sec_agent.canonical_runtime.m6_pilot_package import compute_m6_pilot_package
from sec_agent.canonical_runtime.models import CommandEnvelope, canonical_digest, utc_now
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.canonical_runtime.store import SQLiteCanonicalStore
from sec_agent.canonical_runtime.tool_planner import BoundedToolPlanner, PlannerPermissionContext, PlannerPolicy, ToolRegistryEntry, ToolRegistrySnapshot, ToolSelectionPlan


POLICY_PATH = ROOT / "configs/engineering_handoff/point01_m6_2_real_bounded_sec_metadata_pilot_policy_v1_0.json"
GLOBAL_AUTHORITY_POLICY_PATH = ROOT / "configs/engineering_handoff/point01_m6_2_global_one_shot_authority_policy_v1_0.json"
GLOBAL_PACKAGE_MANIFEST_PATH = ROOT / "configs/engineering_handoff/point01_m6_2_global_one_shot_package_manifest_v1_0.json"
REGISTRY_PATH = ROOT / "configs/engineering_handoff/point01_m6_2_tool_registry_policy_v1_0.json"
DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m6_2_real_bounded_sec_metadata_pilot_result_v1_0.json"
DEFAULT_STORE_ROOT = ROOT / ".tmp_point01_m6_2_real_bounded_sec_metadata_pilot"


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


def _policy() -> BoundedSecMetadataExecutionPolicy:
    raw = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    return BoundedSecMetadataExecutionPolicy.model_validate(
        {field: raw[field] for field in BoundedSecMetadataExecutionPolicy.model_fields}
    )


def _global_authority_policy() -> dict[str, Any]:
    raw = json.loads(GLOBAL_AUTHORITY_POLICY_PATH.read_text(encoding="utf-8"))
    relative = Path(str(raw.get("fixed_approval_store_relative_path") or ""))
    resolved = (ROOT / relative).resolve()
    if not relative or ROOT.resolve() not in resolved.parents:
        raise RuntimeError("global_approval_store_path_invalid")
    if str(raw.get("approval_id") or "").strip() == "":
        raise RuntimeError("global_approval_id_required")
    return raw


def _global_approval_store_root() -> Path:
    policy = _global_authority_policy()
    return (ROOT / str(policy["fixed_approval_store_relative_path"])).resolve()


def _command(command_type: str, payload: dict[str, Any], *, idem: str, expected: int = 0) -> CommandEnvelope:
    return CommandEnvelope(
        command_id=f"cmd-point01-m6-2-sec-pilot-{idem}",
        command_type=command_type,
        tenant_id="tenant-point01-m6-sec-pilot",
        project_id="project-point01-m6-sec-pilot",
        case_id="case-point01-m6-sec-pilot-nvda",
        actor_snapshot_ref="actor-point01-m6-sec-pilot",
        permission_snapshot_ref="permission-point01-m6-sec-pilot",
        policy_config_refs=("point01-m6-2-real-bounded-sec-metadata-pilot-policy-v1",),
        idempotency_key=idem,
        expected_state_version=expected,
        correlation_id="correlation-point01-m6-sec-pilot-nvda",
        requested_at=utc_now(),
        payload=payload,
    )


def _request() -> EvidenceRequest:
    payload: dict[str, Any] = {
        "tenant_id": "tenant-point01-m6-sec-pilot",
        "project_id": "project-point01-m6-sec-pilot",
        "case_id": "case-point01-m6-sec-pilot-nvda",
        "decision_surface_id": "surface-point01-m6-sec-pilot-nvda",
        "decision_surface_contract_version_id": "surface-point01-m6-sec-pilot-nvda:v1",
        "cell_id": "cell-point01-m6-sec-pilot-nvda",
        "cell_version_id": "cell-point01-m6-sec-pilot-nvda:v1",
        "evidence_slot_id": "slot-point01-m6-sec-pilot-nvda",
        "evidence_slot_version_id": "slot-point01-m6-sec-pilot-nvda:v1",
        "requester_role": "fundamental_analyst",
        "accepted_evidence_role": "numeric_fact",
        "evidence_domain": "issuer_disclosure",
        "target_entities": ("NVDA",),
        "target_periods": ("latest_fiscal_period",),
        "metric_intent": ("revenue_growth",),
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
        "stop_condition": "exact_issuer_metadata_bound_or_typed_gap",
        "required": True,
        "compiler_policy_ref": "point01-m6-1-evidence-request-policy-v1",
        "compiled_from_refs": (
            "surface-point01-m6-sec-pilot-nvda:v1",
            "cell-point01-m6-sec-pilot-nvda:v1",
            "slot-point01-m6-sec-pilot-nvda:v1",
            "point01-m6-1-evidence-request-policy-v1",
        ),
        "planning_authority": "shadow",
        "execution_admission": "not_admitted",
    }
    digest = canonical_digest(payload)
    return EvidenceRequest(request_id=f"evidence_request_{digest[:20]}", request_digest=digest, **payload)


def _registry_plan(request: EvidenceRequest) -> ToolSelectionPlan:
    raw = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    entries = tuple(ToolRegistryEntry.model_validate(item) for item in raw["tools"])
    registry = ToolRegistrySnapshot.create(
        registry_id=raw["registry_id"],
        registry_version=int(raw["registry_snapshot_version"]),
        entries=entries,
    )
    policy = PlannerPolicy.model_validate(raw["planner_policy"])
    result = BoundedToolPlanner(registry=registry, policy=policy).plan(
        request=request,
        permissions=PlannerPermissionContext(
            permission_snapshot_ref="permission-point01-m6-sec-pilot",
            allowed_tool_ids=tuple(entry.tool_id for entry in registry.entries),
            required_permission_scope="runtime_read_only",
        ),
    )
    return result.plan


def _runtime(store_root: Path, policy: BoundedSecMetadataExecutionPolicy) -> tuple[RuntimeFacade, CapabilitySecurityService, BudgetControlService, CommandEnvelope, BudgetReservationRequest]:
    facade = RuntimeFacade(
        SQLiteCanonicalStore(store_root / "canonical.sqlite"),
        FileCanonicalObjectStore(store_root / "objects"),
        _flags(),
        mode="shadow",
        grants={"point01.shadow.write"},
    )
    facade.create_research_case(
        _command("CREATE_RESEARCH_CASE", {"query": "Synthetic M6.2 NVDA SEC metadata pilot", "accountable_owner_ref": "point01-m6-pilot-owner"}, idem="case")
    )
    scheduler = DurableSchedulerService(facade)
    scheduler.enqueue(
        _command(
            "CREATE_WORK_UNIT",
            {"work_unit_id": "wu-point01-m6-sec-pilot", "input_version_refs": ["surface-point01-m6-sec-pilot-nvda:v1"], "queue_name": "point01-m6-sec-pilot", "max_attempts": 1},
            idem="enqueue",
        )
    )
    scheduler.claim_next(
        _command(
            "SCHEDULER_CLAIM_NEXT",
            {"queue_name": "point01-m6-sec-pilot", "work_unit_id": "wu-point01-m6-sec-pilot", "worker_ref": "worker-point01-m6-sec-pilot", "attempt_id": "attempt-point01-m6-sec-pilot-1", "lease_duration_seconds": 300},
            idem="claim",
        )
    )
    grant = CapabilityGrant(
        grant_id="grant-point01-m6-sec-pilot",
        tenant_id="tenant-point01-m6-sec-pilot",
        project_id="project-point01-m6-sec-pilot",
        case_id="case-point01-m6-sec-pilot-nvda",
        permission_snapshot_ref="permission-point01-m6-sec-pilot",
        capabilities=(policy.capability,),
        allowed_tool_ids=(policy.tool_id,),
        allowed_network_hosts=(policy.allowed_network_host,),
        allowed_path_prefixes=("submissions",),
        allowed_data_classifications=("public",),
        issued_at=utc_now() - timedelta(minutes=1),
        expires_at=utc_now() + timedelta(minutes=10),
    )
    security = CapabilitySecurityService(
        facade,
        grants=(grant,),
        tool_manifests=(
            ToolManifest(
                tool_id=policy.tool_id,
                capabilities=(policy.capability,),
                allowed_network_hosts=(policy.allowed_network_host,),
                allowed_path_prefixes=("submissions",),
                allowed_data_classifications=("public",),
            ),
        ),
    )
    security.register_authority(_command("CAPABILITY_GRANT_RECORDED", {}, idem="grant"), grant)
    budgets = BudgetControlService(
        facade,
        policy=BudgetPolicy(
            policy_id="point01-m6-sec-pilot-budget-v1",
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
        {"work_unit_id": "wu-point01-m6-sec-pilot", "attempt_id": "attempt-point01-m6-sec-pilot-1", "worker_ref": "worker-point01-m6-sec-pilot", "lease_fencing_token": 1},
        idem="execute",
        expected=1,
    )
    reservation = BudgetReservationRequest(
        reservation_id="reservation-point01-m6-sec-pilot",
        work_unit_id="wu-point01-m6-sec-pilot",
        attempt_id="attempt-point01-m6-sec-pilot-1",
        token_units=0,
        tool_calls=1,
        time_seconds=20,
    )
    return facade, security, budgets, command, reservation


def build_result(*, execute_live: bool, store_root: Path) -> dict[str, Any]:
    policy = _policy()
    authority_policy = _global_authority_policy()
    package = compute_m6_pilot_package(root=ROOT, manifest_path=GLOBAL_PACKAGE_MANIFEST_PATH)
    fixed_inputs = {
        "configs/engineering_handoff/point01_m6_2_real_bounded_sec_metadata_pilot_policy_v1_0.json": _sha256(POLICY_PATH),
        "configs/engineering_handoff/point01_m6_2_tool_registry_policy_v1_0.json": _sha256(REGISTRY_PATH),
        "scripts/engineering/run_point01_m6_2_real_bounded_sec_metadata_pilot.py": _sha256(Path(__file__).resolve()),
        "src/sec_agent/canonical_runtime/bounded_sec_metadata_execution.py": _sha256(ROOT / "src/sec_agent/canonical_runtime/bounded_sec_metadata_execution.py"),
    }
    common = {
        "result_version": "finsight_point01_m6_2_real_bounded_sec_metadata_pilot_result_v1_0",
        "generated_at": utc_now().isoformat(),
        "scope": "isolated_temporary_sqlite_synthetic_case_nvda_sec_submissions_metadata_only",
        "approval_ref": policy.approval_ref,
        "global_approval_id": authority_policy["approval_id"],
        "global_approval_store_path": str(_global_approval_store_root()),
        "approval_package": package.model_dump(mode="json"),
        "fixed_input_sha256": fixed_inputs,
        "authority_boundary": {
            "synthetic_case_only": True,
            "tool_id": policy.tool_id,
            "network_host": policy.allowed_network_host,
            "max_external_calls": 1,
            "max_fallback_calls": 0,
            "provider_or_model_execution": False,
            "raw_document_or_html_download": False,
            "formal_evidence_promotion": False,
            "writer_domain_judgment_full_chain": False,
            "business_case_mutation": False,
            "legacy_authority_change": False,
        },
    }
    if not execute_live:
        return {
            **common,
            "status": "not_run_requires_explicit_execute_live",
            "external_call_count": 0,
            "tool_invocation_count": 0,
            "store_write_count": 0,
            "reason": "live_sec_execution_is_opt_in_even_after_scoped_approval",
        }
    user_agent = os.getenv(policy.user_agent_environment_variable, "").strip()
    if not user_agent:
        return {
            **common,
            "status": "fail_closed",
            "external_call_count": 0,
            "tool_invocation_count": 0,
            "store_write_count": 0,
            "reason": f"required_environment_variable_missing:{policy.user_agent_environment_variable}",
            "store_root": str(store_root),
        }
    facade, security, budgets, command, reservation = _runtime(store_root, policy)
    request = _request()
    plan = _registry_plan(request)
    executor = BoundedSecMetadataExecutor(
        facade=facade,
        security=security,
        budgets=budgets,
        policy=policy,
        global_approval_service=M6GlobalOneShotApprovalService(
            store=SQLiteCanonicalStore(_global_approval_store_root() / "canonical.sqlite")
        ),
        global_approval_id=str(authority_policy["approval_id"]),
        pilot_package=package,
    )
    client = SingleCallSecSubmissionsClient(
        user_agent=user_agent,
        timeout_seconds=policy.timeout_seconds,
        user_agent_min_length=policy.user_agent_min_length,
        forbidden_user_agent_values=policy.forbidden_user_agent_values,
    )
    result = executor.execute(
        command=command,
        request=request,
        plan=plan,
        capability_grant_id="grant-point01-m6-sec-pilot",
        reservation=reservation,
        target_cik=policy.allowed_cik,
        client=client,
    )
    receipt = result.receipt.model_dump(mode="json")
    receipts = facade.store.list_versions("canonical_tool_invocation_receipt_versions")
    return {
        **common,
        "status": "pass" if result.status == "succeeded" else "fail_closed",
        "execution_status": result.status,
        "store_root": str(store_root),
        "store_identity": facade.store.store_identity(),
        "store_content_fingerprint": facade.store.content_fingerprint(),
        "request": {"request_id": request.request_id, "request_digest": request.request_digest},
        "plan": {"plan_id": plan.plan_id, "plan_digest": plan.plan_digest, "registry_snapshot_id": plan.registry_snapshot_id, "registry_snapshot_digest": plan.registry_snapshot_digest},
        "receipt": receipt,
        "receipt_version_digest": canonical_digest(receipts),
        "receipt_versions": len(receipts),
        "external_call_count": result.external_call_count,
        "tool_invocation_count": result.tool_invocation_count,
        "store_write_count": result.store_write_count,
        "security_admission_count": len(facade.store.list_versions("canonical_security_admission_versions")),
        "budget_reservation_state": facade.store.get_latest("canonical_budget_reservation_versions", reservation.reservation_id).get("reservation_state"),
        "boundary": "This result contains only SEC response metadata and append-only control-plane receipts; it is not a CandidateBundle, NumericFact, formal Evidence, Writer output, Domain Judgment or full-chain result.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the one-call Point01 M6.2 real bounded SEC metadata pilot.")
    parser.add_argument("--execute-live", action="store_true", help="Permit the already-approved one-call SEC metadata request.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--store-root", type=Path, default=DEFAULT_STORE_ROOT)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    store_root = args.store_root if args.store_root.is_absolute() else ROOT / args.store_root
    result = build_result(execute_live=args.execute_live, store_root=store_root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "execution_status": result.get("execution_status"), "external_call_count": result["external_call_count"], "output": str(output)}, ensure_ascii=False))
    return 0 if result["status"] in {"pass", "not_run_requires_explicit_execute_live"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
