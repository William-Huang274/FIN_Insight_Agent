from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from scripts.releases.run_fin_ia_0_1_3_s1_08_tencent_relationship_aware_semantic_comparator import (  # noqa: E402
    _is_systemic_stop,
    _safe_failure,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.s1_08_firecrawl_semantic_control import load_plan  # noqa: E402
from sec_agent.s1_08_tencent_relationship_aware_semantic_comparator import (  # noqa: E402
    AUTHORITY_SCHEMA,
    CONTRACT_REF,
    RUN_SCOPE,
    S108TencentSemanticComparatorError,
    build_terminal_result,
    evaluate_comparator,
    load_authority,
    load_scoring_contract,
)


PLAN_PATH = ROOT / "configs/runtime/fin_ia_0_1_3_s1_08_firecrawl_relationship_aware_semantic_control_plan_v1_0.json"
SCORING_PATH = ROOT / "configs/eval/fin_ia_0_1_3_s1_08_tencent_relationship_aware_semantic_comparator_scoring_v1_0.json"
VISIBLE_PATH = ROOT / "eval_sets/fin_0_1_3_same_evidence_v1/model_visible/shared_benchmark_evidence_pack_v1.json"
FIRECRAWL_ASSESSMENT_PATH = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_firecrawl_relationship_aware_semantic_control_assessment_v1_0.json"
DECISION_PATH = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_tencent_fresh_credential_and_same_matrix_comparator_decision_v1_0.json"
PROOF_PATH = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_tencent_relationship_aware_semantic_comparator_zero_call_proof_v1_0.json"
LIVE_RESULT_PATH = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_tencent_relationship_aware_semantic_comparator_result_v1_0.json"
LIVE_ASSESSMENT_PATH = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_tencent_relationship_aware_semantic_comparator_assessment_v1_0.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _authority() -> dict:
    body = {
        "schema_version": AUTHORITY_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "recorded_at": "2026-08-08",
        "status": "issued_unconsumed",
        "authorized_scope": RUN_SCOPE,
        "admission_id": "fin-ia-013-s1-08-tencent-semantic-comparator-test",
        "execution_contract": {
            "selected_lane": "semantic_open_web",
            "planned_query_count": 24,
            "provider_call_ceiling": 24,
            "network_call_ceiling": 24,
            "retry_ceiling": 0,
            "model_call_ceiling": 0,
            "document_fetch_ceiling": 0,
            "evidence_promotion_allowed": False,
            "sourcehunter_integration_allowed": False,
            "combined_46_unit_execution_allowed": False,
            "credentials_from_environment_only": True,
        },
        "immutable_bindings": {},
    }
    return {**body, "authority_digest": canonical_digest(body)}


def _locator(*, url: str, title: str, published: str, rank: int) -> dict:
    body = {
        "provider_rank": rank,
        "canonical_url": url,
        "source_domain": urlsplit(url).hostname or "",
        "title": title,
        "published_at_raw": published,
        "passage": title,
        "site": None,
        "provider_score": 0.9,
        "promotion_status": "candidate_locator_diagnostic_only",
        "evidence_promotion_allowed": False,
        "writer_citable": False,
        "financial_fact_authority": False,
        "numeric_authority": "none",
    }
    return {**body, "locator_digest": canonical_digest(body)}


def _passing_call_results() -> list[dict]:
    plan = load_plan(PLAN_PATH)
    scoring = load_scoring_contract(SCORING_PATH)
    visible = _load(VISIBLE_PATH)
    registry = {
        str(row["source_id"]): row for row in visible["source_registry"]
    }
    calls = []
    for row in plan["query_rows"]:
        target_id = scoring["target_sources_by_case_and_slot"][row["case_key"]][
            row["evidence_slot_id"]
        ][0]
        target = registry[target_id]
        owner = str(row["owner_markers"][0])
        topic = str(row["topic_markers"][0])
        ordinal = int(row["ordinal"])
        locators = [
            _locator(
                url=str(target["url"]).rstrip("/"),
                title=f"{owner} {topic} official result",
                published=str(target["published_on"]),
                rank=1,
            )
        ]
        for index in range(2, 6):
            locators.append(
                _locator(
                    url=f"https://q{ordinal}.example{index}.com/research-{index}",
                    title=f"{owner} {topic} independent research {index}",
                    published="2026-07-01",
                    rank=index,
                )
            )
        calls.append(
            {
                "ordinal": ordinal,
                "intent_id": row["intent_id"],
                "case_key": row["case_key"],
                "evidence_slot_id": row["evidence_slot_id"],
                "evidence_owner_entity_key": row["evidence_owner_entity_key"],
                "language": row["language"],
                "status": "completed",
                "terminal_code": "tencent_semantic_query_response_materialized",
                "network_call_attempted": True,
                "request_capture": {"request_body": {"Query": row["query_text"]}},
                "provider_projection": {
                    "provider_version": "standard",
                    "normalized_unique_locator_count": len(locators),
                    "published_date_count": len(locators),
                    "locators": locators,
                },
                "failure": {},
                "elapsed_ms": 100,
                "capture_refs": {},
            }
        )
    return calls


def _passing_result() -> dict:
    plan = load_plan(PLAN_PATH)
    return build_terminal_result(
        admission_id="fin-ia-013-s1-08-tencent-semantic-comparator-test",
        source_commit="a" * 40,
        control_plan_digest=plan["plan_digest"],
        call_results=_passing_call_results(),
        elapsed_ms=2400,
        sdk_version="3.1.152",
    )


def test_credential_decision_and_zero_call_proof_are_secret_safe_and_same_matrix() -> None:
    decision = _load(DECISION_PATH)
    proof = _load(PROOF_PATH)
    proof_body = dict(proof)
    supplied = proof_body.pop("proof_digest")
    serialized = json.dumps([decision, proof], ensure_ascii=False)
    assert decision["credential_readiness"]["all_required_present"] is True
    assert decision["lane_decision"]["selected_execution_units"] == 24
    assert decision["lane_decision"]["live_execution_authorized_by_this_decision"] is False
    assert supplied == canonical_digest(proof_body)
    assert len(proof["wire_rows"]) == 24
    assert all(row["request_body_fields"] == ["Query"] for row in proof["wire_rows"])
    assert all(row["send_authorized"] is False for row in proof["wire_rows"])
    assert "AKID" not in serialized
    assert "SecretKey:" not in serialized


def test_scoring_contract_and_authority_fail_closed(tmp_path: Path) -> None:
    scoring = load_scoring_contract(SCORING_PATH)
    assert scoring["tencent_provider_specific_hard_gates"][
        "maximum_documented_cost_cny"
    ] == 1.104
    authority_path = tmp_path / "authority.json"
    _write(authority_path, _authority())
    assert load_authority(authority_path)["authorized_scope"] == RUN_SCOPE
    invalid = _authority()
    invalid["execution_contract"]["combined_46_unit_execution_allowed"] = True
    body = dict(invalid)
    body.pop("authority_digest")
    invalid["authority_digest"] = canonical_digest(body)
    _write(authority_path, invalid)
    with pytest.raises(
        S108TencentSemanticComparatorError,
        match="s1_08_tencent_semantic_authority_invalid",
    ):
        load_authority(authority_path)


def test_full_fake_same_matrix_passes_without_sourcehunter_promotion() -> None:
    plan = load_plan(PLAN_PATH)
    assessment = evaluate_comparator(
        result=_passing_result(),
        control_plan=plan,
        scoring_contract=load_scoring_contract(SCORING_PATH),
        visible_pack=_load(VISIBLE_PATH),
        firecrawl_assessment=_load(FIRECRAWL_ASSESSMENT_PATH),
    )
    assert assessment["status"] == (
        "pass_domestic_candidate_for_independent_integration_authority"
    )
    assert assessment["aggregate"]["case_slot_target_in_pool"] == [6, 6]
    assert assessment["aggregate"]["matched_target_date_accuracy"] == 1.0
    assert assessment["aggregate"]["observed_standard_version_rate"] == 1.0
    assert assessment["aggregate"]["documented_cost_cny"] == 1.104
    assert all(assessment["hard_gate_results"].values())
    assert assessment["sourcehunter_integration_eligible"] is False
    assert assessment["production_capability_established"] is False


def test_wrong_tier_and_missing_target_date_fail_product_gate() -> None:
    plan = load_plan(PLAN_PATH)
    result = _passing_result()
    result["call_results"][0]["provider_projection"]["provider_version"] = "lite"
    result["call_results"][1]["provider_projection"]["locators"][0][
        "published_at_raw"
    ] = ""
    body = dict(result)
    body.pop("result_digest")
    result["result_digest"] = canonical_digest(body)
    assessment = evaluate_comparator(
        result=result,
        control_plan=plan,
        scoring_contract=load_scoring_contract(SCORING_PATH),
        visible_pack=_load(VISIBLE_PATH),
        firecrawl_assessment=_load(FIRECRAWL_ASSESSMENT_PATH),
    )
    assert assessment["status"] == "fail_diagnostic_only"
    assert assessment["hard_gate_results"]["observed_standard_version_rate"] is False
    assert assessment["hard_gate_results"]["matched_target_date_accuracy"] is False
    assert assessment["decision"] == "remain_diagnostic_only_no_reranker_rescue"


def test_terminal_requires_all_identities_and_systemic_refusal_stops() -> None:
    plan = load_plan(PLAN_PATH)
    with pytest.raises(
        S108TencentSemanticComparatorError,
        match="s1_08_tencent_semantic_terminalization_incomplete",
    ):
        build_terminal_result(
            admission_id="x",
            source_commit="a" * 40,
            control_plan_digest=plan["plan_digest"],
            call_results=_passing_call_results()[:-1],
            elapsed_ms=100,
            sdk_version="3.1.152",
        )
    assert _is_systemic_stop("AuthFailure.SignatureFailure") is True
    assert _is_systemic_stop("ResourceUnavailable") is True
    assert _is_systemic_stop("InternalError") is False
    failure = _safe_failure(
        code="provider_sdk_or_transport_error",
        provider_error={"error_code": "AuthFailure.SignatureFailure"},
    )
    assert failure["retry_allowed"] is False
    assert failure["credential_material_included"] is False


def test_result_digest_and_identity_mutation_fail_closed() -> None:
    plan = load_plan(PLAN_PATH)
    result = _passing_result()
    result["call_results"][0]["intent_id"] = "cross_case_pollution"
    body = dict(result)
    body.pop("result_digest")
    result["result_digest"] = canonical_digest(body)
    with pytest.raises(
        S108TencentSemanticComparatorError,
        match="s1_08_tencent_semantic_result_not_evaluable",
    ):
        evaluate_comparator(
            result=result,
            control_plan=plan,
            scoring_contract=load_scoring_contract(SCORING_PATH),
            visible_pack=_load(VISIBLE_PATH),
            firecrawl_assessment=_load(FIRECRAWL_ASSESSMENT_PATH),
        )


def test_scoring_cost_mutation_fails_closed(tmp_path: Path) -> None:
    scoring = deepcopy(_load(SCORING_PATH))
    scoring["tencent_provider_specific_hard_gates"][
        "maximum_documented_cost_cny"
    ] = 2.0
    path = tmp_path / "scoring.json"
    _write(path, scoring)
    with pytest.raises(
        S108TencentSemanticComparatorError,
        match="s1_08_tencent_semantic_scoring_gate_invalid",
    ):
        load_scoring_contract(path)


def test_live_terminal_and_assessment_are_digest_bound_and_honestly_failed() -> None:
    result = _load(LIVE_RESULT_PATH)
    result_body = dict(result)
    result_digest = result_body.pop("result_digest")
    assert result_digest == canonical_digest(result_body)
    assert result["status"] == "completed"
    assert result["admission_consumed"] is True
    assert result["provider_versions"] == ["standard"]
    assert result["documented_cost_cny"] == 1.104
    assert result["observed_counts"] == {
        "planned_queries": 24,
        "terminalized_queries": 24,
        "provider_calls": 24,
        "network_calls": 24,
        "successful_calls": 24,
        "typed_failed_or_not_attempted_calls": 0,
        "retry_calls": 0,
        "model_calls": 0,
        "document_fetches": 0,
        "evidence_promotions": 0,
    }
    locators = [
        locator
        for row in result["call_results"]
        for locator in (row.get("provider_projection") or {}).get("locators", [])
    ]
    assert len(locators) == 172
    assert sum(bool(row.get("published_at_raw")) for row in locators) == 172

    assessment = _load(LIVE_ASSESSMENT_PATH)
    assessment_body = dict(assessment)
    assessment_digest = assessment_body.pop("assessment_digest")
    assert assessment_digest == canonical_digest(assessment_body)
    assert assessment["result_digest"] == result_digest
    assert assessment["status"] == "fail_diagnostic_only"
    assert assessment["aggregate"]["topical_useful_count"] == 103
    assert assessment["aggregate"]["topical_useful_denominator"] == 240
    assert assessment["aggregate"]["case_slot_target_in_pool"] == [0, 6]
    assert assessment["aggregate"]["matched_target_date_observations"] == 0
    assert assessment["same_matrix_firecrawl_control"]["topical_useful"] == [
        133,
        240,
    ]
    assert assessment["same_matrix_firecrawl_control"][
        "case_slot_target_in_pool"
    ] == [5, 6]
    assert assessment["sourcehunter_integration_eligible"] is False
    assert assessment["production_capability_established"] is False
    assert assessment["decision"] == "remain_diagnostic_only_no_reranker_rescue"
