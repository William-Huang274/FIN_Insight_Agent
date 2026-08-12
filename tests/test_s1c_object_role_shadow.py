from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULT = (
    ROOT
    / "configs"
    / "retrieval"
    / "fin_ia_0_1_3_s1c_object_role_shadow_result_v1_0.json"
)


def test_object_role_shadow_is_fixed_model_and_non_promoting() -> None:
    payload = json.loads(RESULT.read_text(encoding="utf-8"))
    execution = payload["execution"]
    assert execution["scored_pair_count"] == 35
    assert execution["network_calls"] == 0
    assert execution["training_steps"] == 0
    assert execution["generation_model_calls"] == 0
    assert execution["labels_joined_after_scoring"] is True
    assert payload["authority"] == {
        "candidate_is_not_evidence": True,
        "evidence_promoted": False,
        "cross_encoder_runtime_promoted": False,
        "legacy_rule_role_runtime_promoted": False,
        "fine_tuning_authorized": False,
        "s1d_authorized": False,
        "s1_complete_claimed": False,
    }


def test_object_projection_alone_does_not_qualify_current_models() -> None:
    payload = json.loads(RESULT.read_text(encoding="utf-8"))
    ranking = payload["cross_encoder_development_review"]
    role = payload["legacy_rule_role_development_review"]
    decision = payload["decision"]

    assert ranking["positive_over_hard_negative_pairwise_accuracy"] == 0.5
    assert ranking["judged_query_top1_positive_rate"] == 0.6
    assert ranking["judged_query_top3_positive_rate"] == 1.0
    assert role["positive_role_compatibility_rate"] == 0.705882
    assert role["hard_negative_role_suppression_rate"] == 0.416667
    assert role["multi_label_role_micro_f1"] == 0.507936
    assert decision["cross_encoder_object_projection_credible"] is False
    assert decision["legacy_rule_role_credible"] is False
    assert decision["fine_tuning_eligible"] is False
    assert decision["next_disposition"].startswith(
        "repair_query_decomposition_or_object_projection"
    )


def test_tsm_gap_and_pack_representation_gap_stay_in_owning_stages() -> None:
    payload = json.loads(RESULT.read_text(encoding="utf-8"))
    source_gap = payload["decision"]["real_source_semantic_gap"]
    representation_gap = payload["decision"]["representation_gap"]

    assert source_gap["affected_qrels"] == [
        "s1c_qrel_06",
        "s1c_qrel_12",
        "s1c_qrel_18",
    ]
    assert source_gap["owning_stage"] == "S1-D targeted source supplementation"
    assert source_gap["currently_authorized"] is False
    assert representation_gap["affected_evidence_item_count"] == 45
    assert representation_gap["owning_stage"].startswith("S1-C")
