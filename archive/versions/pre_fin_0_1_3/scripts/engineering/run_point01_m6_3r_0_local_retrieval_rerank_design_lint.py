"""Static design lint for M6.3R.0; it never opens an adapter or store."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / "configs/engineering_handoff/point01_m6_3r_0_local_retrieval_rerank_context_expansion_design_v1_0.json"
INVENTORY = ROOT / "configs/engineering_handoff/point01_m6_3r_0_local_adapter_inventory_v1_0.json"
POLICY = ROOT / "configs/engineering_handoff/point01_m6_3r_0_topk_reranker_policy_v1_0.json"
MANIFEST = ROOT / "configs/engineering_handoff/point01_m6_3r_0_local_retrieval_rerank_test_manifest_v1_0.json"
DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m6_3r_0_local_retrieval_rerank_design_lint_result_v1_0.json"

REQUIRED_TOPK_AUDIT_FIELDS = {
    "requested_topk_policy",
    "resolved_topk_policy",
    "resolver_profile_id",
    "resolver_profile_version",
    "source_type_and_evidence_role",
    "clamp_or_reject_reason",
    "candidate_bundle_candidate_ids",
    "evidence_gate_candidate_ids",
}


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"object_required:{path.name}")
    return value


def evaluate_topk_policy(policy: dict[str, Any]) -> dict[str, bool]:
    default = policy.get("default_profile") or {}
    defaults = default.get("defaults") or {}
    bounds = default.get("allowed_bounds") or {}
    lowering_profiles = policy.get("source_role_lowering_profiles") or []
    audit_fields = set(policy.get("audit_projection_required") or [])
    rerankers = policy.get("reranker_profiles") or {}
    default_reranker = rerankers.get("local_lexical_metadata_reranker:v1") or {}
    future_reranker = rerankers.get("future_model_reranker") or {}

    expected_defaults = {
        "candidate_bundle_top_k": 50,
        "rerank_top_k": 20,
        "evidence_gate_candidate_top_k": 5,
    }
    expected_bounds = {
        "candidate_bundle_top_k": {"minimum": 20, "maximum": 50},
        "rerank_top_k": {"minimum": 8, "maximum": 20},
        "evidence_gate_candidate_top_k": {"minimum": 1, "maximum": 5},
    }
    lower_profiles_valid = bool(lowering_profiles) and all(
        isinstance(row, dict)
        and str(row.get("profile_id") or "").strip()
        and str(row.get("profile_version") or "").strip()
        and str(row.get("lowering_authority") or "").strip()
        and isinstance(row.get("matches"), dict)
        and isinstance(row.get("resolved_values"), dict)
        and 1 <= int((row.get("resolved_values") or {}).get("evidence_gate_candidate_top_k") or 0) <= 5
        for row in lowering_profiles
    )
    return {
        "request_bound_not_global": policy.get("request_binding", {}).get("request_source") == "EvidenceRequest.topk_policy" and policy.get("request_binding", {}).get("agent_free_parameterization") == "forbidden",
        "default_values_tech02_aligned": defaults == expected_defaults,
        "allowed_bounds_tech02_aligned": bounds == expected_bounds,
        "evidence_gate_cap_at_most_five": int(defaults.get("evidence_gate_candidate_top_k") or 0) <= 5,
        "explicit_lowering_profiles_only": lower_profiles_valid,
        "increase_requires_profile_version_authority": (policy.get("increase_policy") or {}).get("current_status") == "not_authorized" and len((policy.get("increase_policy") or {}).get("requires") or []) >= 4,
        "audit_projection_complete": REQUIRED_TOPK_AUDIT_FIELDS.issubset(audit_fields),
        "bundle_and_evidence_gate_names_separate": isinstance(policy.get("candidate_role_separation"), dict) and "never evidence acceptance" in str((policy.get("candidate_role_separation") or {}).get("candidate_bundle_candidate_ids") or "") and "at most five" in str((policy.get("candidate_role_separation") or {}).get("evidence_gate_candidate_ids") or ""),
        "deterministic_reranker_is_zero_model_baseline": default_reranker.get("kind") == "deterministic_zero_model_baseline" and default_reranker.get("model_call_count") == 0,
        "future_model_reranker_separately_authorized": future_reranker.get("status") == "separate_authorization_required" and future_reranker.get("cannot_share_execution_route") is True,
    }


def evaluate_adapter_inventory(inventory: dict[str, Any]) -> dict[str, bool]:
    adapters = {
        str(row.get("adapter_id")): row
        for row in inventory.get("adapters") or []
        if isinstance(row, dict)
    }
    exact_ledger = adapters.get("exact_value_ledger_query") or {}
    mcp_contract = adapters.get("mcp_exact_value_ledger_contract") or {}
    mcp_handler = adapters.get("mcp_tool_registry_exact_value_handler") or {}
    d_series = adapters.get("d_series_governance_readers") or {}
    fact_selection = adapters.get("d_series_governed_fact_selection") or {}
    return {
        "lexical_graph_boundaries_explicit": (adapters.get("bm25_sqlite_fts") or {}).get("disposition") == "read_only_adapter_candidate" and (adapters.get("relationship_graph_lookup") or {}).get("disposition") == "read_only_adapter_candidate",
        "exact_value_sql_lane_inventory_complete": exact_ledger.get("disposition") == "read_only_exact_value_sql_candidate" and len(exact_ledger.get("mandatory_downstream_validation") or []) >= 7 and "never direct Evidence promotion" in str(exact_ledger.get("prohibited_claim") or ""),
        "mcp_contract_requires_tool_receipt": mcp_contract.get("disposition") == "reuse_typed_tool_boundary_only_future_receipt_required" and "ToolInvocationReceipt" in str(mcp_contract.get("permitted_future_use") or ""),
        "mcp_direct_handler_rejected": mcp_handler.get("disposition") == "reject_direct_handler_reuse_receipt_bypass" and "relaxed" in str(mcp_handler.get("observed_behavior") or "") and "fallback" in str(mcp_handler.get("observed_behavior") or ""),
        "d_series_limited_to_governance_context": d_series.get("disposition") == "governance_history_context_only_not_exact_fact_adapter" and "never issuer exact-value recall" in str(d_series.get("permitted_future_use") or ""),
        "fact_selection_rejected_as_retrieval": fact_selection.get("disposition") == "reject_as_downstream_governed_selection" and "leak selection authority backward" in str(fact_selection.get("blocking_gap") or ""),
        "model_retrievers_deferred": (adapters.get("hybrid_rrf_dense") or {}).get("disposition") == "defer_until_separate_model_resource_authority" and (adapters.get("dense_numpy_retriever") or {}).get("disposition") == "defer_until_separate_model_resource_authority",
    }


def build_result() -> dict[str, Any]:
    design = _read(DESIGN)
    inventory = _read(INVENTORY)
    policy = _read(POLICY)
    manifest = _read(MANIFEST)
    gates = design.get("authority_and_count_gates") or {}
    neighbor_limits = design.get("neighbor_diversity_limits") or {}
    required_refs = {
        "previous_section_ref", "next_section_ref", "parent_section_ref", "table_ref",
        "previous_page_ref", "next_page_ref", "previous_row_refs", "next_row_refs",
    }
    topk_checks = evaluate_topk_policy(policy)
    inventory_checks = evaluate_adapter_inventory(inventory)
    future_points = design.get("future_execution_points") or []
    full_scope = str((future_points[2] if len(future_points) > 2 and isinstance(future_points[2], dict) else {}).get("scope") or "")
    checks = {
        "design_repair_stage_only": design.get("execution_stage") == "design_repair_independently_accepted" and manifest.get("stage") == "design_repair_independently_accepted",
        "policy_file_bound": design.get("topk_resolution_contract", {}).get("policy_file") == str(POLICY.relative_to(ROOT)).replace("\\", "/"),
        **topk_checks,
        "diversity_defined": neighbor_limits.get("max_candidates_per_source_artifact") == 2 and neighbor_limits.get("require_two_source_families_when_available") is True,
        "neighbor_coordinates_complete": required_refs.issubset(set((design.get("neighbor_expansion") or {}).get("allowed_refs") or [])),
        "neighbor_stop_rules_defined": len((design.get("neighbor_expansion") or {}).get("stop_rules") or []) >= 4,
        "typed_exhaustion_no_fallback": "retrieval_exhausted_no_recall_hit" in set((design.get("typed_exhaustion") or {}).get("codes") or []) and "fallback" in str((design.get("typed_exhaustion") or {}).get("prohibition") or ""),
        "zero_execution_counts": all(value == 0 for value in gates.values()),
        "no_second_state_model": (design.get("no_second_state_model") or {}).get("persistence") == "not_authorized",
        **inventory_checks,
        "future_sequence_complete": [row.get("stage") for row in future_points if isinstance(row, dict)] == ["skeleton", "fixture", "full", "calibrated"],
        "future_full_scope_includes_exact_value_sql_lane": "exact-value ledger SQL lane" in full_scope and "ToolInvocationReceipt" in full_scope and "no relaxed-filter fallback" in full_scope,
        "corpus_and_negative_plan": len((design.get("calibration_corpus_plan") or {}).get("coverage_buckets") or []) >= 8 and len((design.get("calibration_corpus_plan") or {}).get("negative_cases") or []) >= 13,
        "static_test_manifest_complete": len(manifest.get("required_static_gates") or []) >= 13 and manifest.get("expected_counts") == {"network_request_count": 0, "external_tool_call_count": 0, "model_call_count": 0, "canonical_store_write_count": 0, "adapter_execution_count": 0},
    }
    return {
        "result_version": "finsight_point01_m6_3r_0_local_retrieval_rerank_design_lint_result_v1_1_topk_sql_inventory_repair",
        "status": "pass" if all(checks.values()) else "fail_closed",
        "execution_stage": "design_repair_independently_accepted",
        "checks": checks,
        "network_request_count": 0,
        "external_tool_call_count": 0,
        "model_call_count": 0,
        "provider_call_count": 0,
        "canonical_store_write_count": 0,
        "evidence_promotion_count": 0,
        "adapter_execution_count": 0,
        "note": "Static design manifest only. No adapter, store, network, parser, promotion or model was opened."
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint the M6.3R.0 static design only.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = build_result()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "adapter_execution_count": 0, "network_request_count": 0}))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
