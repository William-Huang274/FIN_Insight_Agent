from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DECISION = ROOT / (
    "configs/releases/fin_ia_0_1_3_s2_selected_evidence_numeric_"
    "candidate_cocompilation_zero_call_disposition_v1_0.json"
)
PRD = ROOT / "docs/product/PRD_20260628_b2b_financial_research_workbench.zh-CN.md"
TECH = ROOT / (
    "docs/architecture/agent_graph_vnext/"
    "38_model_reasoning_numeric_authority_and_protected_narrative_contract.zh-CN.md"
)
PLAN = ROOT / (
    "docs/product/FIN_0_1_3_REPAIR_CLOSEOUT_SCOPE_AND_DELTA_"
    "S0_TO_S5_PLAN_20260805.zh-CN.md"
)
CONTEXT = ROOT / "docs/project_os/current_context_pack.zh-CN.md"
ROOT_LEDGER = ROOT / "docs/project_os/root_cause_issue_ledger.jsonl"
CAPABILITY_LEDGER = ROOT / "docs/project_os/capability_status_ledger.jsonl"


def _digest(value: dict) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_disposition_is_digest_bound_zero_call_and_no_rerun() -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    body = {key: value for key, value in decision.items() if key != "decision_digest"}

    assert decision["decision_digest"] == _digest(body)
    assert decision["status"] == "decision_complete_implementation_pending"
    assert decision["scope"] == {
        "kind": "zero_call_root_cause_and_contract_disposition",
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "source_calls": 0,
        "retries": 0,
        "automatic_dell_rerun": False,
        "runtime_implementation_in_this_item": False,
        "business_artifact_promotion": False,
    }
    assert decision["release_boundary"]["release_eligible"] is False


def test_disposition_rejects_manual_and_regex_all_and_selects_provider_neutral_design() -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    options = {row["option_id"]: row["decision"] for row in decision["option_assessment"]}

    assert options == {
        "A_manual_whitelist_extension": "rejected",
        "B_regex_promote_every_number_in_selected_source_text": "rejected",
        "C_source_aware_candidate_discovery_target_aware_deterministic_adjudication_and_bounded_model_views": "selected",
    }
    assert "no provider-specific branch is added to the core contract" in decision["selected_design"]["design_principles"]
    assert set(decision["selected_design"]["adjudication_statuses"]) == {
        "authorized_fact",
        "authorized_formula_operand",
        "descriptive_nonmaterial",
        "context_only_do_not_output",
        "forbidden_or_ambiguous",
    }


def test_candidate_contract_covers_primary_held_out_and_non_scalar_financial_surfaces() -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    required = set(decision["selected_design"]["required_candidate_fields"])

    assert {
        "source_coordinate_or_span",
        "parsed_value_or_bounds",
        "entity_or_evidence_owner",
        "period_or_as_of",
        "semantic_metric_key",
        "claim_and_output_boundary",
        "adjudication_status",
        "decision_code",
    } <= required
    assert set(decision["case_acceptance_matrix"]) == {
        "DELL",
        "MU",
        "NVDA",
        "ORCL",
        "ASML",
        "ANET",
    }
    assert {
        "count_scalar",
        "numeric_range",
        "temporal_range_or_boundary",
        "qualitative_numeric_band",
    } <= set(decision["selected_design"]["candidate_value_kinds"])
    assert len(decision["mutation_suite"]) >= 16
    assert "structured metric works when source_materials is empty" in decision["mutation_suite"]


def test_model_views_and_local_guard_preserve_analysis_without_weakening_financial_truth() -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))

    assert "does not write the research thesis" in decision["selected_design"]["design_principles"][3]
    assert decision["local_guard_contract"]["source_text_presence_bypasses_authority"] is False
    assert decision["local_guard_contract"]["model_verifier_is_sole_promotion_authority"] is False
    assert decision["local_guard_contract"]["coexisting_findings_allowed"] is True
    assert "S3 may later let a model request" in decision["model_view_contract"]["future_dynamic_request_boundary"]


def test_source_docs_project_os_and_next_implementation_are_aligned() -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    next_item = decision["current_next"]

    for path in (PRD, TECH, PLAN, CONTEXT):
        text = path.read_text(encoding="utf-8")
        assert next_item in text
        assert "MaterialNumericCandidateInventory" in text

    root_rows = _jsonl(ROOT_LEDGER)
    capability_rows = _jsonl(CAPABILITY_LEDGER)
    root = next(row for row in root_rows if row.get("sequence_after_projection") == "v2_417")
    capability = next(
        row for row in capability_rows if row.get("sequence_after_projection") == "v2_366"
    )
    assert root["issue_id"].startswith("RC-P36-170-")
    assert root["status"] == "root_cause_decided_implementation_pending"
    assert capability["status"] == "contract_disposition_complete_runtime_not_implemented"
    assert root["current_next"] == next_item
    assert capability["current_next"] == next_item
