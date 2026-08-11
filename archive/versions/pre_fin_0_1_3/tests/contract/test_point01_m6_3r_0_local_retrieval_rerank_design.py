from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / "configs/engineering_handoff/point01_m6_3r_0_local_retrieval_rerank_context_expansion_design_v1_0.json"
INVENTORY = ROOT / "configs/engineering_handoff/point01_m6_3r_0_local_adapter_inventory_v1_0.json"
POLICY = ROOT / "configs/engineering_handoff/point01_m6_3r_0_topk_reranker_policy_v1_0.json"
MANIFEST = ROOT / "configs/engineering_handoff/point01_m6_3r_0_local_retrieval_rerank_test_manifest_v1_0.json"
LINT = ROOT / "scripts/engineering/run_point01_m6_3r_0_local_retrieval_rerank_design_lint.py"


def _read(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _lint_module() -> object:
    spec = importlib.util.spec_from_file_location("point01_m6_3r_0_design_lint", LINT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_m6_3r_topk_is_request_bound_with_tech02_defaults_and_bounds() -> None:
    design = _read(DESIGN)
    policy = _read(POLICY)
    default = policy["default_profile"]

    assert design["execution_stage"] == "design_repair_independently_accepted"
    assert design["topk_resolution_contract"]["source_of_request"].startswith("EvidenceRequest.topk_policy")
    assert default["defaults"] == {
        "candidate_bundle_top_k": 50,
        "rerank_top_k": 20,
        "evidence_gate_candidate_top_k": 5,
    }
    assert default["allowed_bounds"] == {
        "candidate_bundle_top_k": {"minimum": 20, "maximum": 50},
        "rerank_top_k": {"minimum": 8, "maximum": 20},
        "evidence_gate_candidate_top_k": {"minimum": 1, "maximum": 5},
    }


def test_m6_3r_topk_negative_conflicts_fail_static_policy_checks() -> None:
    lint = _lint_module()
    policy = _read(POLICY)

    bad_cap = copy.deepcopy(policy)
    bad_cap["default_profile"]["defaults"]["evidence_gate_candidate_top_k"] = 8
    assert lint.evaluate_topk_policy(bad_cap)["evidence_gate_cap_at_most_five"] is False

    bad_global = copy.deepcopy(policy)
    bad_global["request_binding"]["request_source"] = "global_constant"
    assert lint.evaluate_topk_policy(bad_global)["request_bound_not_global"] is False

    bad_audit = copy.deepcopy(policy)
    bad_audit["audit_projection_required"].remove("clamp_or_reject_reason")
    assert lint.evaluate_topk_policy(bad_audit)["audit_projection_complete"] is False


def test_m6_3r_separates_bundle_from_future_evidence_gate_input() -> None:
    design = _read(DESIGN)
    policy = _read(POLICY)
    contracts = design["proposed_ephemeral_contracts"]

    assert "CandidateBundleProjection" in contracts
    assert "EvidenceGateCandidateProjection" in contracts
    assert "candidate_bundle_candidate_ids" in policy["candidate_role_separation"]
    assert "evidence_gate_candidate_ids" in policy["candidate_role_separation"]
    assert "not_an_evidence_promotion" in contracts["EvidenceGateCandidateProjection"]


def test_m6_3r_reranker_is_zero_model_baseline_and_model_route_is_separate() -> None:
    policy = _read(POLICY)
    profiles = policy["reranker_profiles"]

    assert profiles["local_lexical_metadata_reranker:v1"]["kind"] == "deterministic_zero_model_baseline"
    assert profiles["local_lexical_metadata_reranker:v1"]["model_call_count"] == 0
    assert profiles["future_model_reranker"]["status"] == "separate_authorization_required"
    assert profiles["future_model_reranker"]["cannot_share_execution_route"] is True


def test_m6_3r_inventory_audits_exact_value_sql_mcp_and_d_series_boundaries() -> None:
    inventory = _read(INVENTORY)
    adapters = {row["adapter_id"]: row for row in inventory["adapters"]}

    assert adapters["exact_value_ledger_query"]["disposition"] == "read_only_exact_value_sql_candidate"
    assert len(adapters["exact_value_ledger_query"]["mandatory_downstream_validation"]) >= 7
    assert adapters["mcp_exact_value_ledger_contract"]["disposition"] == "reuse_typed_tool_boundary_only_future_receipt_required"
    assert adapters["mcp_tool_registry_exact_value_handler"]["disposition"] == "reject_direct_handler_reuse_receipt_bypass"
    assert adapters["d_series_governance_readers"]["disposition"] == "governance_history_context_only_not_exact_fact_adapter"
    assert adapters["d_series_governed_fact_selection"]["disposition"] == "reject_as_downstream_governed_selection"


def test_m6_3r_inventory_negative_direct_handler_and_fact_selection_are_rejected() -> None:
    lint = _lint_module()
    inventory = _read(INVENTORY)

    bad_handler = copy.deepcopy(inventory)
    for row in bad_handler["adapters"]:
        if row["adapter_id"] == "mcp_tool_registry_exact_value_handler":
            row["disposition"] = "read_only_adapter_candidate"
    assert lint.evaluate_adapter_inventory(bad_handler)["mcp_direct_handler_rejected"] is False

    bad_selection = copy.deepcopy(inventory)
    for row in bad_selection["adapters"]:
        if row["adapter_id"] == "d_series_governed_fact_selection":
            row["disposition"] = "read_only_adapter_candidate"
    assert lint.evaluate_adapter_inventory(bad_selection)["fact_selection_rejected_as_retrieval"] is False


def test_m6_3r_design_has_no_second_state_model_or_execution_authority() -> None:
    design = _read(DESIGN)
    assert design["no_second_state_model"]["persistence"] == "not_authorized"
    assert all(value == 0 for value in design["authority_and_count_gates"].values())
    assert "local adapter invocation" in design["prohibited_execution"]


def test_m6_3r_manifest_requires_static_only_gates_and_future_sql_calibration() -> None:
    design = _read(DESIGN)
    manifest = _read(MANIFEST)
    full_scope = design["future_execution_points"][2]["scope"]

    assert manifest["stage"] == "design_repair_independently_accepted"
    assert manifest["expected_counts"] == {
        "network_request_count": 0,
        "external_tool_call_count": 0,
        "model_call_count": 0,
        "canonical_store_write_count": 0,
        "adapter_execution_count": 0,
    }
    assert [row["stage"] for row in design["future_execution_points"]] == ["skeleton", "fixture", "full", "calibrated"]
    assert "exact-value ledger SQL lane" in full_scope
    assert "ToolInvocationReceipt" in full_scope
    assert len(design["calibration_corpus_plan"]["negative_cases"]) >= 13
