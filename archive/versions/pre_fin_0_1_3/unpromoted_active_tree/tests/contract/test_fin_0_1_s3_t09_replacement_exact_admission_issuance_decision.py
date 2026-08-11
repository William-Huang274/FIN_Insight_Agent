from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (
    S3ThreeCellBoundedAgentAdmission,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from sec_agent.canonical_runtime.models import canonical_digest


DECISION = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s3_t09_replacement_exact_admission_issuance_decision_v1_0.json"
)
BACKLOG = ROOT / "configs" / "releases" / "fin_ia_0_1_program_release_backlog_v2_0.json"
CONSUMED_ADMISSION = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s3_t09_three_cell_deepseek_segmented_exact_admission_v1_0.json"
)


def _decision() -> dict[str, object]:
    return json.loads(DECISION.read_text(encoding="utf-8"))


def test_decision_recommends_future_issuance_but_does_not_issue_or_execute() -> None:
    decision = _decision()
    assert decision["status"] == (
        "pass_issue_recommended_pending_separate_replacement_exact_admission_issuance_authority"
    )
    authority = decision["authority"]
    assert authority["replacement_exact_admission_issuance_decision_authorized"] is True
    assert authority["replacement_exact_admission_issuance_authorized"] is False
    assert authority["replacement_exact_admission_consumption_or_execution_authorized"] is False
    assert decision["decision"]["replacement_exact_admission_may_be_issued_after_separate_authority"] is True
    assert decision["decision"]["issue_replacement_exact_admission_now"] is False
    assert decision["decision"]["consume_or_execute_replacement_exact_admission_now"] is False
    assert set(decision["observed_counts"].values()) == {0}
    assert decision["next_action"] == "S3-T09-REPLACEMENT-EXACT-ADMISSION-ISSUANCE"


def test_prospective_output_v2_admission_is_exact_and_factory_admissible() -> None:
    prospective = _decision()["prospective_admission"]
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(prospective["payload"])
    admission.assert_profile_admissible()
    build_s3_three_cell_bounded_agent_executor_for_admission(
        admission, chat_completion_fn=lambda **_: {}
    )
    assert admission.output_contract_ref == "fin01.s3.bounded_agent_three_cell_output:v2"
    assert admission.specialist_max_output_tokens == 2200
    assert canonical_digest(admission.digest_payload()) == prospective["admission_digest"]
    assert prospective["admission_digest"] == (
        "7871e5e93ff9f4c01db73205726a72ef899beb18ce1fce84da027f2856d1c829"
    )
    assert prospective["admission_file_exists_after_this_decision"] is False


def test_fresh_identity_and_input_are_distinct_from_consumed_r1() -> None:
    decision = _decision()
    consumed = json.loads(CONSUMED_ADMISSION.read_text(encoding="utf-8"))
    evidence = decision["input_evidence"]
    prospective = decision["prospective_admission"]["payload"]
    assert evidence["double_prepare_equal"] is True
    assert evidence["canonical_counts_before"] == evidence["canonical_counts_after"]
    assert set(evidence["fresh_predicted_state_absent"].values()) == {True}
    assert prospective["admission_id"] != consumed["admission_id"]
    assert prospective["input_digest"] != consumed["input_digest"]
    assert evidence["execution_identity"] != (
        "fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1"
    )


def test_model_views_budget_and_credential_review_remain_closed() -> None:
    decision = _decision()
    views = decision["model_view_review"]
    assert views["model_view_contract_ref"] == "fin01.s3.specialist_model_view:v1"
    assert views["output_contract_ref"] == "fin01.s3.bounded_agent_three_cell_output:v2"
    assert [item["request_bytes"] for item in views["views"]] == [8331, 12461, 8969]
    budget = decision["budget_review"]
    assert budget["maximum_output_tokens_total"] == 10200
    assert budget["output_only_cost_ceiling_usd"] == 0.008874
    assert budget["remaining_cost_for_input_usd_at_full_output_ceiling"] == 0.091126
    assert budget["retry_budget"] == 0
    review = decision["independent_preissuance_review"]
    assert review["credential_present"] is True
    assert review["credential_value_read_output_or_persisted"] is False
    assert review["provider_health_probe_performed"] is False


def test_backlog_preserves_decision_and_records_later_execution_boundary() -> None:
    backlog = json.loads(BACKLOG.read_text(encoding="utf-8"))
    next_action = backlog["next_action"]
    assert next_action["item_id"] == (
        "S3-T09-OWNER-GRADE-V3-SEGMENTED-TRANSPORT-V5-RESEARCH-LEAD-OUTPUT-TRUNCATION-RESULT-AND-ROOT-CAUSE-DECISION"
    )
    assert next_action["fresh_v3_agent_proof_decision_authorized"] is True
    assert next_action["fresh_v3_exact_admission_issuance_authorized"] is True
    assert next_action["fresh_v3_exact_admission_issued"] is True
    assert next_action["fresh_v3_exact_live_execution_authorized"] is True
    assert next_action["S3_T09_replacement_exact_admission_issuance_decision_authorized"] is True
    assert next_action["S3_T09_replacement_exact_admission_issuance_authorized"] is True
    assert next_action["S3_T09_replacement_exact_admission_issued"] is True
    assert next_action["S3_T09_replacement_exact_admission_consumed"] is True
    assert next_action["S3_T09_replacement_exact_live_execution_authorized"] is True
    assert next_action[
        "S3_T09_replacement_artifact_paired_baseline_validation_authorized"
    ] is True
    assert next_action["deterministic_baseline_materialization_authorized"] is True
    assert next_action["replacement_admission_or_execution_authorized"] is False
    assert next_action["source_network_or_external_tool_execution_authorized"] is False
    assert next_action["release_or_production_authorized"] is False
