from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DECISION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s3_t09_final_hard_failure_disposition_decision_v1_0.json"
)
FINAL_RESULT = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s3_t09_research_lead_v5_profile_v3_"
    "final_exact_live_execution_result_v1_0.json"
)
BACKLOG = ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
PROGRAM_PLAN = (
    ROOT
    / "docs/architecture/repository/"
    "FIN_0_1_PROGRAM_EXECUTION_PLAN_DRAFT_20260719.zh-CN.md"
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_disposition_is_grounded_in_the_final_hard_failure() -> None:
    decision = _read(DECISION)
    result = _read(FINAL_RESULT)
    source = decision["source_failure"]
    assessment = decision["independent_disposition_assessment"]

    assert source["research_run_id"] == result["identity"]["research_run_id"]
    assert source["failure_code"] == result["failure"]["failure_code"]
    assert source["claim_support_items"] == 6
    assert source["items_matching_validated_local_fact_ids"] == 0
    assert source["items_matching_underlying_numeric_support_refs"] == 6
    assert source["artifact_count"] == 0
    assert assessment["hard_integrity_failure_confirmed"] is True
    assert assessment["ordinary_style_or_alpha_gap"] is False
    assert assessment["cannot_be_deferred_while_claiming_S3_NVDA_R2"] is True


def test_selected_policy_uses_closed_fact_aliases_and_local_expansion() -> None:
    policy = _read(DECISION)["selected_generalized_contract"]

    assert policy["contract_ref"] == "fin01.s3.claim_fact_link_policy:v1"
    assert policy["policy_name"] == "ClaimFactLinkPolicy"
    assert policy["provider_response_field"] == "support_fact_aliases"
    assert policy["local_canonical_output_field"] == "support_fact_ids"
    assert policy["request_local_alias_examples"] == ["F001", "F002"]
    assert "underlying_Numeric_refs" in policy[
        "provider_hidden_from_claim_link_selection_surface"
    ]
    assert policy["canonical_fact_lineage_preserved"] is True
    assert policy["request_local_alias_persisted_as_authoritative_identity"] is False
    assert policy[
        "fuzzy_match_normalize_trim_prefix_guess_or_silent_rewrite_allowed"
    ] is False
    assert policy["transport_version_number_branch_controls_behavior"] is False
    assert policy["new_specialist_v8_required_only_to_special_case_this_failure"] is False


def test_decision_authorizes_no_implementation_or_live_execution() -> None:
    decision = _read(DECISION)
    authority = decision["authority"]
    counts = decision["observed_counts"]
    proof = decision["future_fresh_proof_governance_if_separately_authorized"]

    assert set(counts.values()) == {0}
    assert authority["final_hard_failure_disposition_decision_authorized"] is True
    assert authority["generalized_repair_direction_selection_authorized"] is True
    assert authority[
        "runtime_code_prompt_schema_or_validator_implementation_authorized"
    ] is False
    assert authority["new_admission_issuance_or_consumption_authorized"] is False
    assert authority["fresh_live_proof_or_rerun_authorized"] is False
    assert proof["maximum_fresh_exact_live_executions"] == 1
    assert proof["retry_fallback_rerun"] == [0, 0, 0]
    assert proof["first_credible_hard_failure_stops"] is True
    assert decision["next_action"].endswith("ZERO-CALL-IMPLEMENTATION")


def test_historical_disposition_is_preserved_but_superseded_by_layered_reassessment() -> None:
    backlog = _read(BACKLOG)
    next_action = backlog["next_action"]
    plan_text = PROGRAM_PLAN.read_text(encoding="utf-8")
    decision = _read(DECISION)

    assert decision["next_action"].endswith("ZERO-CALL-IMPLEMENTATION")
    assert next_action["item_id"] == (
        "S3-T09-LAYERED-ACCEPTANCE-RUNTIME-ALIGNMENT-ZERO-CALL-IMPLEMENTATION"
    )
    assert next_action["RC_P36_047_status"].startswith("reclassified_L3_L4")
    assert next_action["RC_P36_037_status"].endswith(
        "nine_artifact_product_still_missing"
    )
    assert next_action["layered_acceptance_runtime_alignment_authorized"] is False
    assert next_action["agent_rerun_authorized"] is False
    assert next_action["owner_review_or_T10_authorized"] is False
    assert next_action["item_id"] in plan_text
    assert "PER-FIELD-NARRATIVE-LENGTH-FAILURE-ZERO-CALL-ROOT-CAUSE-DECISION" not in (
        plan_text.split("## 9. 当前下一步", 1)[1]
    )


def test_program_plan_digest_is_refreshed_in_the_backlog() -> None:
    backlog = _read(BACKLOG)
    expected = {
        row["path"]: row["sha256"] for row in backlog["stable_source_digests"]
    }[
        "docs/architecture/repository/"
        "FIN_0_1_PROGRAM_EXECUTION_PLAN_DRAFT_20260719.zh-CN.md"
    ]
    actual = hashlib.sha256(PROGRAM_PLAN.read_bytes()).hexdigest()

    assert actual == expected
