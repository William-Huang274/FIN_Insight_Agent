from __future__ import annotations

from pathlib import Path

from scripts.data_retrieval.materialize_s1_vs3_product_gate import materialize


ROOT = Path(__file__).resolve().parents[1]


def _path(value: str) -> Path:
    return ROOT / value


def test_current_vs3_product_gate_consumes_final_successors() -> None:
    result = materialize(
        ranking_summary_path=_path(
            "configs/retrieval/fin_ia_0_1_3_s1_vs3_candidate_ranking_result_v1_8.json"
        ),
        financial_shortlist_path=_path(
            "configs/retrieval/fin_ia_0_1_3_s1_vs3_financial_shortlist_result_v1_8.json"
        ),
        evidence_role_replay_path=_path(
            "configs/retrieval/fin_ia_0_1_3_s1_vs3_evidence_role_replay_result_v1_4.json"
        ),
        vs1_result_path=_path(
            "configs/retrieval/fin_ia_0_1_3_s1_vs3_vs1_same_runtime_replay_result_v1_4.json"
        ),
        vs1_financial_shortlist_path=_path(
            "configs/retrieval/fin_ia_0_1_3_s1_vs3_vs1_financial_shortlist_result_v1_1.json"
        ),
        vs2_result_path=_path(
            "configs/retrieval/fin_ia_0_1_3_s1_vs3_vs2_same_runtime_replay_result_v1_2.json"
        ),
        legacy_financial_result_path=_path(
            "configs/retrieval/fin_ia_0_1_3_s1c_financial_ranking_shadow_result_v1_0.json"
        ),
        pack_result_path=_path(
            "configs/runtime/fin_ia_current_research_evidence_pack_result_v1_1.json"
        ),
    )

    assert result["gate_results"] == {
        "candidate_generation_gate_passed": True,
        "vs1_reviewed_target_recall_gate_passed": True,
        "vs2_complex_object_pool_gate_passed": True,
        "head_quality_gate_passed": True,
        "evidence_role_quality_gate_passed": True,
        "object_candidate_decision_contract_passed": True,
        "vs3_vertical_slice_integration_gate_passed": True,
        "legacy_financial_ranker_remains_rejected": True,
    }
    assert result["summary"]["combined_union_positive_atom_count"] == 15
    assert result["summary"]["financial_shortlist_positive_top10_count"] == 15
    assert result["summary"]["financial_shortlist_hard_negative_top10_count"] == 0
    assert result["summary"]["vs1_reviewed_objects_in_candidate_pool"] == 2
    assert result["summary"]["vs2_reviewed_objects_in_candidate_pool"] == 4
    assert result["decision"]["vs3_stage_status"] == "vertical_slice_integrated"
    assert result["decision"]["vs4_acquisition_authorized"] is True
    assert result["decision"]["runtime_evidence_promotion_authorized"] is False
    assert result["decision"]["s1_complete_claimed"] is False

    for payload in result["payloads"]:
        ledger = payload["candidate_decision_ledger"]
        assert sum(ledger["decision_counts"].values()) == ledger["candidate_count"]
        assert ledger["authority"]["candidate_text_promoted"] is False
        assert ledger["authority"]["numeric_authority"] is False

