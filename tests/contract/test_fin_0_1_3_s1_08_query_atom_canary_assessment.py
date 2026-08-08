from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.s1_08_query_atom_canary_assessment import (  # noqa: E402
    S108QueryAtomCanaryAssessmentError,
    assess_failed_query_atom_canary,
)


RESULT = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_deepseek_query_atom_canary_result_v1_0.json"
PROGRESSION = ROOT / "configs/releases/fin_ia_0_1_3_s1_retrieval_query_facet_external_internal_progression_plan_v1_1.json"


def _sealed(body: dict, key: str) -> dict:
    return {**body, key: canonical_digest(body)}


def _private_material() -> dict:
    authority = _sealed(
        {
            "schema_version": "authority",
            "decision_digest_placeholder": False,
        },
        "decision_digest",
    )
    request_body = {
        "schema_version": "request",
        "plans": [
            {
                "plan_key": [
                    "MU",
                    "regulatory_risk_and_financial_reconciliation",
                    "MU",
                    "en",
                ]
            }
        ],
    }
    request = {**request_body, "request_digest": canonical_digest(request_body)}
    output = {
        "schema_version": "fin_ia_0_1_3_s1_08_deepseek_query_atom_output_v1_0",
        "atoms": [
            {
                "case_key": "MU",
                "evidence_slot_id": "regulatory_risk_and_financial_recovery",
                "evidence_owner_entity_key": "MU",
                "language": "en",
                "atom_kind": "mechanism",
                "value": "long-term agreement prepayment",
            }
        ],
    }
    admission_body = {
        "schema_version": "admission",
        "contract_ref": "fin_0_1_3.S1_08.deepseek_query_atom_canary:v1",
        "authority_decision_digest": authority["decision_digest"],
        "request_digest": request["request_digest"],
        "execution_git_commit": "a" * 40,
        "run_id": "run_1",
        "attempt_id": "attempt_1",
        "provider": {"backend": "deepseek", "model": "deepseek-v4-pro"},
    }
    admission = _sealed(admission_body, "admission_digest")
    capture = {
        "schema_version": "capture",
        "request_digest": request["request_digest"],
        "model_visible_request": request,
        "gateway_result": {},
        "credential_or_authorization_value_saved": False,
        "provider_private_reasoning_saved": False,
        "business_evidence_or_fact_authority": False,
    }
    terminal_body = {
        "schema_version": "terminal",
        "contract_ref": admission["contract_ref"],
        "admission_digest": admission["admission_digest"],
        "run_id": admission["run_id"],
        "attempt_id": admission["attempt_id"],
        "status": "terminal_failed_no_retry",
        "terminal_code": "s1_08_query_atom_canary_output_plan_binding_invalid",
        "request_digest": request["request_digest"],
        "capture_digest": canonical_digest(capture),
        "capture_ref": "captures/01.json",
        "gateway_status": "ok",
        "finish_reason": "stop",
        "usage": {
            "input_tokens": 10,
            "output_tokens": 10,
            "total_tokens": 20,
            "transport_attempt_count": 1,
            "latency_ms": 100,
        },
        "provider_output": output,
        "provider_output_digest": canonical_digest(output),
        "accepted_atoms": [],
        "accepted_atom_count": 0,
        "completed_calls": 1,
        "retry_count": 0,
        "fallback_count": 0,
        "document_fetches": 0,
        "retrieval_calls": 0,
        "embedding_calls": 0,
        "rerank_calls": 0,
        "evidence_promotions": 0,
        "runtime_activation": False,
        "observed_at": "2026-08-08T16:31:02Z",
    }
    terminal = _sealed(terminal_body, "terminal_result_digest")
    receipt_body = {
        "schema_version": "receipt",
        "state": "terminal",
        "admission_digest": admission["admission_digest"],
        "terminal_status": terminal["status"],
        "terminal_code": terminal["terminal_code"],
        "terminal_result_digest": terminal["terminal_result_digest"],
    }
    receipt = _sealed(receipt_body, "receipt_digest")
    evaluation_body = {
        "status": "zero_call_A_B_pass_model_atom_observation_pending",
        "quality_gates": {"deterministic_local_structure_pass": True},
        "variant_summary": {
            "user_raw_query": {
                "mean_facet_coverage": 0.138889,
                "duplicate_query_rate": 0.916667,
            },
            "deterministic_local_compiler": {
                "mean_facet_coverage": 1.0,
                "minimum_facet_coverage": 1.0,
                "duplicate_query_rate": 0.0,
                "contamination_count": 0,
            },
        },
    }
    evaluation = _sealed(evaluation_body, "evaluation_digest")
    return {
        "admission": admission,
        "terminal": terminal,
        "capture": capture,
        "receipt": receipt,
        "authority": authority,
        "zero_call_evaluation": evaluation,
    }


def test_failed_canary_is_rejected_without_partial_salvage() -> None:
    result = assess_failed_query_atom_canary(**_private_material())
    assert result["status"] == "natural_query_atom_canary_terminal_failed_model_variant_rejected"
    assert result["natural_observation"]["invalid_plan_binding_count"] == 1
    assert result["natural_observation"]["partial_atom_salvage_performed"] is False
    assert result["decision"]["external_query_baseline"] == "deterministic_local_compiler_only"
    assert result["stage_acceptance"]["natural_model_atom_observation"] is True
    assert result["stage_acceptance"]["model_assisted_query_plan"] is False
    body = {key: value for key, value in result.items() if key != "record_digest"}
    assert result["record_digest"] == canonical_digest(body)


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        ("capture", "assessment_capture_digest_invalid"),
        ("terminal", "assessment_terminal_digest_invalid"),
        ("receipt", "assessment_receipt_digest_invalid"),
    ],
)
def test_private_binding_mutations_fail_closed(target: str, expected: str) -> None:
    material = _private_material()
    material[target]["mutation"] = True
    with pytest.raises(S108QueryAtomCanaryAssessmentError) as exc_info:
        assess_failed_query_atom_canary(**material)
    assert exc_info.value.code == expected


def test_versioned_result_is_sanitized_and_preserves_internal_backlog() -> None:
    assert RESULT.is_file()
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    body = {key: value for key, value in result.items() if key != "record_digest"}
    assert result["record_digest"] == canonical_digest(body)
    assert result["natural_observation"]["observed_atom_count"] == 18
    assert result["natural_observation"]["allowed_plan_binding_count"] == 17
    assert result["natural_observation"]["invalid_plan_binding_count"] == 1
    assert result["natural_observation"]["accepted_atom_count"] == 0
    assert result["observed_calls"]["provider"] == 1
    assert result["observed_calls"]["retry"] == 0
    assert result["decision"]["internal_exact_BM25_dense_graph_then_qrels_then_BGE_rerank_backlog_preserved"] is True
    serialized = json.dumps(result, ensure_ascii=False).lower()
    assert "raw_response" not in serialized
    assert '"authorization":' not in serialized
    assert "bearer " not in serialized
    assert "api_key" not in serialized


def test_progression_keeps_external_then_internal_candidate_ceiling_then_ranking() -> None:
    plan = json.loads(PROGRESSION.read_text(encoding="utf-8"))
    body = {key: value for key, value in plan.items() if key != "plan_digest"}
    assert plan["plan_digest"] == canonical_digest(body)
    rows = plan["execution_sequence"]
    assert rows[4]["status"] == "zero_call_engineering_pass_clean_authority_pending"
    assert rows[5]["routes"] == [
        "exact_SQL_and_object_lookup",
        "BM25_and_ObjectBM25_lexical",
        "dense_Milvus_semantic",
        "relationship_graph",
    ]
    assert rows[6]["work_item"] == "S1_INTERNAL_CANDIDATE_CEILING_AND_QRELS_GATE"
    assert rows[7]["work_item"] == "S1_INTERNAL_BGE_FUSION_AND_RERANK_EVALUATION"
    assert rows[7]["status"].startswith("registered_but_not_admitted")
