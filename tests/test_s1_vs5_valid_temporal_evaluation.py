from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from retrieval.qualification_evaluation import (
    QualificationEvaluationError,
    evaluate_frozen_candidates,
)


ROOT = Path(__file__).resolve().parents[1]
POLICY = (
    ROOT
    / "configs/retrieval/fin_ia_0_1_3_s1_vs5_valid_temporal_evaluation_policy_v1_0.json"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture() -> tuple[dict, list[dict], list[dict], dict]:
    object_a = {
        "compiled_object_id": "OBJ-A",
        "object_kind": "claim",
        "model_text": "Membership fee revenue increased and renewal remained high.",
        "base_object_view": {
            "company": "Costco Wholesale Corporation",
            "fiscal_year": 2025,
            "publication_date": "2025-10-08",
            "source_type": "10-K",
            "source_record_id": "SRC-A",
        },
    }
    object_b = {
        "compiled_object_id": "OBJ-B",
        "object_kind": "claim",
        "model_text": "Membership loyalty may weaken when renewal behavior changes.",
        "base_object_view": {
            "company": "Costco Wholesale Corporation",
            "fiscal_year": 2025,
            "publication_date": "2025-10-08",
            "source_type": "10-K",
            "source_record_id": "SRC-B",
        },
    }
    raw = {
        "status": "candidate_generation_complete_labels_not_loaded",
        "execution": {"labels_loaded": False},
        "authority": {
            "qualification_scored": False,
            "evidence_promotion_authorized": False,
            "numeric_fact_authority": False,
        },
        "propositions": [
            {
                "example_id": "VS5::COST::MEMBERSHIP",
                "case_key": "COST",
                "question_zh": "会员费和续费率说明什么？",
                "candidate_union_top20": ["OBJ-A"],
                "bge_reranker_top20": ["OBJ-A"],
                "qwen_reranker_top20": ["OBJ-A"],
                "role_guarded_top20": ["OBJ-A"],
                "candidate_review_top20": ["OBJ-A"],
                "final_shortlist": [
                    {"rank": 1, "compiled_object_id": "OBJ-A", "score": 1.0},
                    {"rank": 21, "compiled_object_id": "OBJ-B", "score": 0.1},
                ],
                "bge_best_need_by_candidate": {"OBJ-A": "N1", "OBJ-B": "N2"},
                "qwen_best_need_by_candidate": {"OBJ-A": "N1", "OBJ-B": "N2"},
            }
        ],
    }
    references = [
        {
            "example_id": "VS5::COST::MEMBERSHIP",
            "review_state": "qualification_blinded",
            "adjudication_authority": "qualified-human pending",
            "expected_outcome": {
                "case_key": "COST",
                "proposition_id": "MEMBERSHIP",
                "required_facets": ["direct_support", "counterevidence"],
                "required_roles": ["direct", "counter"],
                "positive_candidates": [
                    {
                        "compiled_object_id": "OBJ-A",
                        "facets": ["direct_support"],
                        "roles": ["direct"],
                        "review_note_zh": "会员费与续费的直接披露",
                    },
                    {
                        "compiled_object_id": "OBJ-B",
                        "facets": ["counterevidence"],
                        "roles": ["counter"],
                        "review_note_zh": "续费走弱的反方材料",
                    },
                ],
                "authority_boundary": {
                    "runtime_may_read_reference": False,
                    "owner_or_qualified_human_review_pending": True,
                },
            },
        }
    ]
    metrics = {
        "candidate_review_k": 20,
        "proposition_any_hit_minimum": 1.0,
        "all_positive_object_recall_minimum": 0.9,
        "material_facet_coverage_minimum": 0.85,
        "required_role_coverage_minimum": 1.0,
    }
    return raw, references, [object_a, object_b], metrics


def test_valid_temporal_evaluation_policy_binds_only_frozen_temporal_inputs() -> None:
    value = json.loads(POLICY.read_text(encoding="utf-8"))
    assert value["status"] == "frozen_after_candidate_output_before_evaluation_execution"
    for binding in value["bound_inputs"].values():
        path = ROOT / binding["ref"]
        assert path.is_file()
        assert _sha256(path) == binding["sha256"]
    reference = value["bound_inputs"]["valid_temporal_evaluator_reference"]["ref"]
    assert "/valid_temporal/" in reference
    assert "test_frozen" not in reference
    assert "holdout_heterogeneous" not in reference
    contract = value["evaluation_contract"]
    assert contract["learned_vector_computation_allowed"] is False
    assert contract["cpu_vector_fallback_allowed"] is False
    assert contract["test_frozen_reference_access_allowed"] is False
    assert contract["holdout_heterogeneous_reference_access_allowed"] is False


def test_evaluator_separates_recall_from_final_ranking_and_never_promotes() -> None:
    raw, references, objects, metrics = _fixture()
    result = evaluate_frozen_candidates(
        raw=raw,
        references=references,
        objects=objects,
        metric_contract=metrics,
        business_templates_zh={"MEMBERSHIP": "反方缺失会令利润质量判断失真。"},
    )
    assert result["aggregate_metrics"]["proposition_any_hit_at_20"] == 1.0
    assert result["aggregate_metrics"]["all_positive_object_recall_at_20"] == 0.5
    assert result["candidate_ranking_metric_gate_pass"] is False
    proposition = result["propositions"][0]
    missed = proposition["positive_candidate_diagnostics"][1]
    assert missed["reranker_pool_present"] is True
    assert missed["final_rank"] == 21
    assert missed["failure_owner"] == "financial_shortlist_or_fusion_ranking"
    assert proposition["candidate_is_not_evidence"] is True
    assert proposition["numeric_fact_authority"] is False
    assert proposition["public_information_gap_declared"] is False
    assert "反方" in proposition["business_assessment_zh"]


def test_evaluator_attributes_missing_catalog_object_to_earliest_layer() -> None:
    raw, references, objects, metrics = _fixture()
    objects = [objects[0]]
    result = evaluate_frozen_candidates(
        raw=raw,
        references=references,
        objects=objects,
        metric_contract=metrics,
        business_templates_zh={},
    )
    missed = result["propositions"][0]["positive_candidate_diagnostics"][1]
    assert missed["failure_owner"] == "source_parser_or_object_compilation"
    assert result["authority_boundary"]["public_information_gap_declared"] is False


def test_evaluator_rejects_candidate_output_that_loaded_labels() -> None:
    raw, references, objects, metrics = _fixture()
    raw["execution"]["labels_loaded"] = True
    with pytest.raises(
        QualificationEvaluationError, match="candidate_runtime_was_not_label_blind"
    ):
        evaluate_frozen_candidates(
            raw=raw,
            references=references,
            objects=objects,
            metric_contract=metrics,
            business_templates_zh={},
        )
