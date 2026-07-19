from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "configs/engineering_handoff/point01_m6_0_migration_design_freeze_manifest_v1_0.json"
DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m6_0_design_lint_result_v1_0.json"
PLAN_PATH = ROOT / "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md"
TECH_PATHS = {
    "TECH_02_agentic_search_evidence_toolgateway_sourcehunter": ROOT / "docs/architecture/agent_graph_vnext/TECH_02_agentic_search_evidence_toolgateway_sourcehunter.zh-CN.md",
    "TECH_03_document_metadata_rag_knowledge_layer": ROOT / "docs/architecture/agent_graph_vnext/TECH_03_document_metadata_rag_knowledge_layer.zh-CN.md",
    "TECH_04_numeric_program_trace_parser_promotion": ROOT / "docs/architecture/agent_graph_vnext/TECH_04_numeric_program_trace_parser_promotion.zh-CN.md",
    "TECH_05_domain_evidence_operator_decision_surface_projection": ROOT / "docs/architecture/agent_graph_vnext/TECH_05_domain_evidence_operator_decision_surface_projection.zh-CN.md",
    "TECH_07_context_engine_skills_compaction_governance": ROOT / "docs/architecture/agent_graph_vnext/TECH_07_context_engine_skills_compaction_governance.zh-CN.md",
    "TECH_08_subagents_as_tools_handoff_contract": ROOT / "docs/architecture/agent_graph_vnext/TECH_08_subagents_as_tools_handoff_contract.zh-CN.md",
}
POINT_IDS = tuple(f"M6.{number}" for number in range(1, 11))
REQUIRED_ARTIFACT_OWNERS = {
    "EvidenceRequest": "M6.1_evidence_request_compiler",
    "ToolRegistrySnapshot": "M6.2_tool_registry_planner",
    "ToolSelectionPlan": "M6.2_tool_registry_planner",
    "ToolInvocationReceipt": "M6.2_tool_registry_planner",
    "CandidateBundle": "M6.3_candidate_context_expansion",
    "RepairTicket": "M6.4_source_repair_owner",
    "RepairAttempt": "M6.4_source_repair_owner",
    "ParserCandidate": "M6.5_parser_numeric_owner",
    "NormalizedNumericFact": "M6.5_parser_numeric_owner",
    "NumericProgramTrace": "M6.5_parser_numeric_owner",
    "EvidencePromotionDecision": "M6.6_evidence_gate_owner",
    "DomainJudgmentPack": "M6.7_domain_operator_owner",
    "ContextRequirement": "M6.8_lead_context_handoff_owner",
    "ContextInjectionPlan": "M6.8_lead_context_handoff_owner",
    "LeadRepairDecision": "M6.8_lead_context_handoff_owner",
}
REQUIRED_DATAFLOW = {
    ("DecisionSurfaceCell", "EvidenceRequest"),
    ("EvidenceSlot", "EvidenceRequest"),
    ("EvidenceRequest", "ToolSelectionPlan"),
    ("ToolRegistrySnapshot", "ToolSelectionPlan"),
    ("ToolSelectionPlan", "CandidateBundle"),
    ("CandidateBundle", "RepairTicket"),
    ("RepairTicket", "ToolSelectionPlan"),
    ("CandidateBundle", "ParserCandidate"),
    ("ParserCandidate", "NormalizedNumericFact"),
    ("NormalizedNumericFact", "NumericProgramTrace"),
    ("NumericProgramTrace", "EvidencePromotionDecision"),
    ("EvidencePromotionDecision", "DomainJudgmentPack"),
    ("EvidencePromotionDecision", "ContextRequirement"),
    ("ContextRequirement", "ContextInjectionPlan"),
    ("RepairTicket", "LeadRepairDecision"),
}
REQUIRED_FORBIDDEN = {
    "provider_execution",
    "external_tool_execution",
    "network_execution",
    "evidence_runtime",
    "writer_runtime",
    "full_chain",
    "business_case_mutation",
    "legacy_authority_change",
    "compound_writer",
    "paid_model_run",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path, errors: list[str]) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        errors.append("manifest_unreadable")
        return {}
    if not isinstance(value, Mapping):
        errors.append("manifest_not_mapping")
        return {}
    return value


def validate_manifest(manifest: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if manifest.get("manifest_version") != "finsight_point01_m6_0_migration_design_freeze_v1_0":
        errors.append("manifest_version_invalid")
    if manifest.get("scope") != "Point01_M6_Evidence_Repair_downstream_design_only" or manifest.get("point_id") != "M6.0":
        errors.append("manifest_scope_invalid")
    if manifest.get("status") != "design_frozen_deterministic_no_runtime_implementation":
        errors.append("manifest_status_invalid")
    if manifest.get("authorization") != "user_approved_m6_0_design_freeze_only_after_M5_closeout":
        errors.append("authorization_invalid")
    expected_prerequisites = {
        "m5_status": "M5_complete_temporary_store_full_calibrated_reviewed",
        "legacy_task_run_authority": "authoritative_execution_history_owner",
        "decision_surface_authority": "planning_pilot_only_read_contract",
    }
    if manifest.get("prerequisites") != expected_prerequisites:
        errors.append("prerequisites_invalid")
    source_techs = set(manifest.get("source_tech_contracts") or ())
    errors.extend(f"source_tech_missing:{tech}" for tech in sorted(set(TECH_PATHS) - source_techs))
    boundary = manifest.get("authority_boundary") or {}
    if boundary.get("m6_artifact_writes") != "not_admitted_in_m6_0":
        errors.append("authority_boundary_not_denied:m6_artifact_writes")
    for key in ("provider_execution", "external_tool_or_network_execution", "evidence_runtime", "writer_runtime", "full_chain", "business_case_mutation", "legacy_authority_change"):
        if boundary.get(key) != "not_admitted":
            errors.append(f"authority_boundary_not_denied:{key}")
    if boundary.get("decision_surface_contract_cell_slot") != "read_only_m6_input":
        errors.append("planning_inputs_not_read_only")

    input_contracts = manifest.get("input_contracts") or ()
    inputs = {str(row.get("artifact")) for row in input_contracts if isinstance(row, Mapping)}
    for required in {"DecisionSurfaceContract", "DecisionSurfaceCell", "EvidenceSlot", "GapRecord", "ContextSnapshot"} - inputs:
        errors.append(f"input_contract_missing:{required}")
    for row in input_contracts:
        if not isinstance(row, Mapping) or row.get("access") != "read_only_exact_version":
            errors.append("input_contract_not_exact_read_only")

    catalog = manifest.get("artifact_catalog")
    if not isinstance(catalog, list):
        return sorted(set(errors + ["artifact_catalog_not_list"]))
    by_artifact: dict[str, Mapping[str, Any]] = {}
    for row in catalog:
        if not isinstance(row, Mapping):
            errors.append("artifact_catalog_row_invalid")
            continue
        artifact = str(row.get("artifact") or "")
        if artifact in by_artifact:
            errors.append(f"artifact_duplicate_write_owner:{artifact}")
        by_artifact[artifact] = row
        if not row.get("required_refs"):
            errors.append(f"artifact_required_refs_missing:{artifact}")
    for artifact, owner in REQUIRED_ARTIFACT_OWNERS.items():
        row = by_artifact.get(artifact)
        if row is None:
            errors.append(f"artifact_missing:{artifact}")
        elif row.get("write_owner") != owner:
            errors.append(f"artifact_owner_invalid:{artifact}")

    children = manifest.get("children")
    if not isinstance(children, list):
        return sorted(set(errors + ["children_not_list"]))
    child_by_id = {str(row.get("point_id")): row for row in children if isinstance(row, Mapping)}
    errors.extend(f"child_missing:{point_id}" for point_id in POINT_IDS if point_id not in child_by_id)
    if len(child_by_id) != len(children):
        errors.append("child_point_id_duplicate_or_invalid")
    for point_id in POINT_IDS[:-1]:
        row = child_by_id.get(point_id, {})
        if row.get("status") != "not_implemented":
            errors.append(f"implementation_not_denied:{point_id}")
        if not row.get("owner") or not row.get("responsibility"):
            errors.append(f"child_contract_incomplete:{point_id}")
        for artifact in row.get("writes") or ():
            catalog_row = by_artifact.get(str(artifact))
            if catalog_row is None or catalog_row.get("write_owner") != row.get("owner"):
                errors.append(f"cross_owner_write:{point_id}:{artifact}")
    closeout = child_by_id.get("M6.10", {})
    if closeout.get("status") != "blocked_pending_m6_1_to_m6_9":
        errors.append("m6_10_must_remain_blocked")
    if set(closeout.get("dependencies") or ()) != set(POINT_IDS[:-1]):
        errors.append("m6_10_dependencies_invalid")

    dataflow = manifest.get("dataflow") or ()
    edge_rows = {(str(row.get("from")), str(row.get("to"))): row for row in dataflow if isinstance(row, Mapping)}
    errors.extend(f"dataflow_missing:{source}->{target}" for source, target in sorted(REQUIRED_DATAFLOW - set(edge_rows)))
    repair_edge = edge_rows.get(("RepairTicket", "ToolSelectionPlan"))
    if not repair_edge or repair_edge.get("mode") != "bounded_feedback" or set(repair_edge.get("required_controls") or ()) != {"origin_evidence_request_ref", "attempt_budget_ref", "stop_reason"}:
        errors.append("repair_loop_not_bounded")

    compound = manifest.get("no_compound_writer_contract") or {}
    if compound.get("status") != "required" or "compound_writer" not in set(compound.get("prohibited_patterns") or ()):
        errors.append("no_compound_writer_contract_missing")
    if "cannot mutate EvidenceRequest" not in str(compound.get("repair_loop_rule") or ""):
        errors.append("repair_loop_cross_owner_boundary_missing")
    admission = manifest.get("implementation_admission") or {}
    if admission.get("status") != "no_runtime_implementation_admitted":
        errors.append("implementation_admission_status_invalid")
    errors.extend(f"forbidden_admission_missing:{item}" for item in sorted(REQUIRED_FORBIDDEN - set(admission.get("forbidden_admissions") or ())))
    if "explicit user authorization for M6.1" not in set(admission.get("requires_before_m6_1") or ()):
        errors.append("m6_1_explicit_authorization_missing")
    review = manifest.get("cross_owner_design_review") or {}
    if review.get("status") != "structured_local_design_review_complete":
        errors.append("cross_owner_design_review_status_invalid")
    if review.get("implementation_gate") != "independent_cross_owner_review_and_explicit_user_authorization_required_before_M6_1":
        errors.append("m6_1_cross_owner_gate_invalid")
    return sorted(set(errors))


def build_result(manifest: Mapping[str, Any], *, manifest_path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    errors = validate_manifest(manifest)
    hashes = {
        str(manifest_path.relative_to(ROOT)).replace("\\", "/"): _sha256(manifest_path),
        "scripts/engineering/run_point01_m6_0_design_lint.py": _sha256(Path(__file__).resolve()),
        str(PLAN_PATH.relative_to(ROOT)).replace("\\", "/"): _sha256(PLAN_PATH),
    }
    hashes.update({str(path.relative_to(ROOT)).replace("\\", "/"): _sha256(path) for path in TECH_PATHS.values()})
    return {
        "result_version": "finsight_point01_m6_0_design_lint_result_v1_0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": manifest.get("scope"),
        "status": "pass" if not errors else "fail_closed",
        "errors": errors,
        "manifest_status": manifest.get("status"),
        "child_contract_count": len(manifest.get("children") or ()),
        "artifact_owner_count": len(manifest.get("artifact_catalog") or ()),
        "model_call_count": 0,
        "external_call_count": 0,
        "runtime_implementation_count": 0,
        "authority_boundary": manifest.get("authority_boundary"),
        "fixed_input_sha256": hashes,
        "boundary": "This M6.0 pass freezes only downstream ownership and dataflow. It does not implement M6.1, admit providers, external tools or network execution, Evidence/Writer runtime, full-chain, business Case mutation, legacy authority change, a compound writer, or paid model execution.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint the Point 01 M6.0 Evidence/Repair migration design freeze.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    manifest_path = args.manifest if args.manifest.is_absolute() else ROOT / args.manifest
    output_path = args.output if args.output.is_absolute() else ROOT / args.output
    errors: list[str] = []
    manifest = _read_json(manifest_path, errors)
    result = build_result(manifest, manifest_path=manifest_path)
    result["errors"] = sorted(set(errors + result["errors"]))
    result["status"] = "pass" if not result["errors"] else "fail_closed"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "output": str(output_path), "errors": result["errors"]}, ensure_ascii=False))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
