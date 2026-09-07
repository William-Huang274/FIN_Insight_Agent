from __future__ import annotations

import json
from pathlib import Path
import random

import pytest

from retrieval.evidence_set_coverage import (
    EvidenceSetCoverageError,
    compile_requirement_plan,
    evaluate_material_reference,
    select_request_bound_review,
    validate_requirement_plan,
)


ROOT = Path(__file__).resolve().parents[1]
POLICY = (
    ROOT
    / "configs/retrieval/fin_ia_0_1_3_s1_material_evidence_set_coverage_policy_v1_0.json"
)
FOUR_CASE_MATRIX = (
    ROOT
    / "tests/fixtures/retrieval/fin_ia_s1_material_evidence_set_four_case_development_matrix_v1_0.json"
)


def _request() -> dict:
    return {
        "request_id": "ER::DEV::CASH",
        "case_key": "DEV",
        "target_entities": ["DEV"],
        "metric_intents": ["operating_cash_flow", "gross_margin"],
        "product_intents": ["issuer_total"],
        "requested_facet_ids": [
            "reported_results",
            "counterevidence",
            "working_capital_risk",
        ],
        "period": {"fiscal_years": [2024, 2025]},
    }


def _plan() -> dict:
    return {
        "schema_version": "fin_ia_material_evidence_requirement_plan_v1_0",
        "request_id": "ER::DEV::CASH",
        "requirement_groups": [
            {
                "requirement_id": "REQ::DIRECT",
                "facet_id": "reported_results",
                "role": "direct",
                "metric_ids": ["operating_cash_flow"],
                "product_ids": ["issuer_total"],
                "target_entities": ["DEV"],
                "period_mode": "single_period",
                "fiscal_years": [2025],
                "minimum_candidates": 1,
                "priority": 1,
            },
            {
                "requirement_id": "REQ::COUNTER",
                "facet_id": "counterevidence",
                "role": "counter",
                "metric_ids": ["gross_margin"],
                "product_ids": ["issuer_total"],
                "target_entities": ["DEV"],
                "period_mode": "any",
                "fiscal_years": [],
                "minimum_candidates": 1,
                "priority": 2,
            },
            {
                "requirement_id": "REQ::TEMPORAL",
                "facet_id": "working_capital_risk",
                "role": "bridge",
                "metric_ids": ["operating_cash_flow"],
                "product_ids": ["issuer_total"],
                "target_entities": ["DEV"],
                "period_mode": "all_periods_same_basis",
                "fiscal_years": [2024, 2025],
                "minimum_candidates": 1,
                "priority": 3,
            },
        ],
    }


def _candidate(
    object_id: str,
    rank: int,
    *,
    facet: str,
    role: str,
    metric: str,
    years: list[int],
    basis: str = "",
    case_key: str = "DEV",
) -> dict:
    return {
        "compiled_object_id": object_id,
        "base_rank": rank,
        "score": 1.0 / rank,
        "case_key": case_key,
        "target_entities": [case_key],
        "facet_ids": [facet],
        "roles": [role],
        "metric_ids": [metric],
        "product_ids": ["issuer_total"],
        "fiscal_years": years,
        "same_basis_key": basis,
    }


def _candidates() -> list[dict]:
    noise = [
        _candidate(
            f"NOISE::{index:02d}",
            index,
            facet="reported_results",
            role="direct",
            metric="gross_margin",
            years=[2025],
        )
        for index in range(1, 19)
    ]
    return noise + [
        _candidate(
            "DIRECT::OCF",
            21,
            facet="reported_results",
            role="direct",
            metric="operating_cash_flow",
            years=[2025],
        ),
        _candidate(
            "COUNTER::MARGIN",
            22,
            facet="counterevidence",
            role="counter",
            metric="gross_margin",
            years=[2025],
        ),
        _candidate(
            "PAIR::OCF",
            23,
            facet="working_capital_risk",
            role="bridge",
            metric="operating_cash_flow",
            years=[2024, 2025],
            basis="OCF::USD::ANNUAL",
        ),
    ]


def test_policy_keeps_runtime_and_reference_authority_separate() -> None:
    value = json.loads(POLICY.read_text(encoding="utf-8"))
    assert value["status"] == "zero_call_development_contract_frozen_before_replay"
    assert value["candidate_contract"]["gold_identity_visible"] is False
    assert value["candidate_contract"]["reference_visible"] is False
    assert value["evaluation_contract"]["request_alignment_is_hard_gate"] is True
    assert value["development_scope"]["existing_test_frozen_or_holdout_reference_access"] is False


def test_compiler_binds_public_request_without_candidate_identity() -> None:
    plan = compile_requirement_plan(
        evidence_request=_request(),
        material_requirements=_plan()["requirement_groups"],
        review_k=20,
    )
    assert plan["request_id"] == _request()["request_id"]
    assert plan["evidence_request_digest"]
    assert plan["plan_digest"]
    assert "compiled_object_id" not in json.dumps(plan, ensure_ascii=False)


def test_four_case_business_shapes_share_one_request_bound_contract() -> None:
    matrix = json.loads(FOUR_CASE_MATRIX.read_text(encoding="utf-8"))
    assert matrix["status"] == "development_fixture_not_qualification_gold"
    assert [row["case_key"] for row in matrix["cases"]] == [
        "DELL",
        "MU",
        "NVDA",
        "COST",
    ]
    for row in matrix["cases"]:
        plan = compile_requirement_plan(
            evidence_request=row["evidence_request"],
            material_requirements=row["material_requirements"],
            review_k=20,
        )
        selection = select_request_bound_review(
            candidates=row["candidates"], plan=plan
        )
        expected = row["expected_reserved_prefix"]
        assert selection["unmet_requirement_ids"] == []
        assert selection["selected_candidate_ids"][: len(expected)] == expected
        assert selection["candidate_is_not_evidence"] is True
        assert selection["numeric_fact_authority"] is False


def test_plan_rejects_metric_outside_request_and_gold_identity_leak() -> None:
    invalid = _plan()
    invalid["requirement_groups"][0]["metric_ids"] = ["membership_fee"]
    with pytest.raises(EvidenceSetCoverageError, match="metric_outside_request"):
        validate_requirement_plan(evidence_request=_request(), plan=invalid, review_k=20)
    leaked = _plan()
    leaked["requirement_groups"][0]["compiled_object_id"] = "GOLD::1"
    with pytest.raises(EvidenceSetCoverageError, match="leaks_gold_identity"):
        validate_requirement_plan(evidence_request=_request(), plan=leaked, review_k=20)


def test_plan_rejects_unfunded_group_capacity() -> None:
    invalid = _plan()
    invalid["requirement_groups"][0]["minimum_candidates"] = 21
    with pytest.raises(EvidenceSetCoverageError, match="review_capacity_insufficient"):
        validate_requirement_plan(evidence_request=_request(), plan=invalid, review_k=20)


def test_plan_reserves_worst_case_capacity_for_two_object_temporal_pair() -> None:
    with pytest.raises(EvidenceSetCoverageError, match="review_capacity_insufficient"):
        validate_requirement_plan(evidence_request=_request(), plan=_plan(), review_k=3)
    plan = validate_requirement_plan(
        evidence_request=_request(), plan=_plan(), review_k=4
    )
    assert plan["minimum_required_capacity"] == 3
    assert plan["maximum_reserved_capacity"] == 4


def test_request_bound_selector_preserves_complete_material_set_before_noise() -> None:
    plan = validate_requirement_plan(
        evidence_request=_request(), plan=_plan(), review_k=20
    )
    result = select_request_bound_review(candidates=_candidates(), plan=plan)
    selected = result["selected_candidate_ids"]
    assert selected[:3] == ["DIRECT::OCF", "COUNTER::MARGIN", "PAIR::OCF"]
    assert result["unmet_requirement_ids"] == []
    assert len(selected) == 20
    assert result["candidate_is_not_evidence"] is True


def test_temporal_pair_requires_same_basis_and_all_periods() -> None:
    plan = validate_requirement_plan(
        evidence_request=_request(), plan=_plan(), review_k=20
    )
    candidates = _candidates()[:-1] + [
        _candidate(
            "PAIR::2024",
            23,
            facet="working_capital_risk",
            role="bridge",
            metric="operating_cash_flow",
            years=[2024],
            basis="OCF::USD::ANNUAL",
        ),
        _candidate(
            "PAIR::2025::WRONG",
            24,
            facet="working_capital_risk",
            role="bridge",
            metric="operating_cash_flow",
            years=[2025],
            basis="OCF::NONCOMPARABLE",
        ),
    ]
    result = select_request_bound_review(candidates=candidates, plan=plan)
    assert "REQ::TEMPORAL" in result["unmet_requirement_ids"]


def test_wrong_case_candidate_never_satisfies_requirement() -> None:
    plan = validate_requirement_plan(
        evidence_request=_request(), plan=_plan(), review_k=20
    )
    candidates = [
        _candidate(
            "WRONG::DIRECT",
            1,
            facet="reported_results",
            role="direct",
            metric="operating_cash_flow",
            years=[2025],
            case_key="OTHER",
        )
    ]
    result = select_request_bound_review(candidates=candidates, plan=plan)
    assert "REQ::DIRECT" in result["unmet_requirement_ids"]
    assert result["selected_candidate_ids"] == []
    assert result["hard_boundary_rejected_candidate_ids"] == ["WRONG::DIRECT"]


def test_selection_is_stable_under_candidate_permutation() -> None:
    plan = validate_requirement_plan(
        evidence_request=_request(), plan=_plan(), review_k=20
    )
    candidates = _candidates()
    expected = select_request_bound_review(candidates=candidates, plan=plan)
    random.Random(20260818).shuffle(candidates)
    actual = select_request_bound_review(candidates=candidates, plan=plan)
    assert actual["selection_digest"] == expected["selection_digest"]


def test_alternative_object_can_satisfy_group_without_hiding_unique_group_failure() -> None:
    plan = validate_requirement_plan(
        evidence_request=_request(), plan=_plan(), review_k=20
    )
    selection = select_request_bound_review(candidates=_candidates(), plan=plan)
    reference = {
        "schema_version": "fin_ia_material_evidence_set_reference_v1_0",
        "request_id": "ER::DEV::CASH",
        "requirement_plan_digest": plan["plan_digest"],
        "material_reference_groups": [
            {
                "requirement_id": "REQ::DIRECT",
                "acceptable_candidate_sets": [
                    ["DIRECT::OLD"],
                    ["DIRECT::OCF"],
                ],
                "canonical_positive_ids": ["DIRECT::OLD"],
            },
            {
                "requirement_id": "REQ::COUNTER",
                "acceptable_candidate_sets": [["COUNTER::MARGIN"]],
                "canonical_positive_ids": ["COUNTER::MARGIN"],
            },
            {
                "requirement_id": "REQ::TEMPORAL",
                "acceptable_candidate_sets": [["PAIR::OCF"]],
                "canonical_positive_ids": ["PAIR::OCF"],
            },
        ],
    }
    result = evaluate_material_reference(selection=selection, reference=reference)
    assert result["required_group_gate_pass"] is True
    assert result["required_group_coverage"] == 1.0
    assert result["exact_object_recall_diagnostic"] == pytest.approx(2 / 3)
    missing_unique = dict(reference)
    missing_unique["material_reference_groups"] = [
        {
            "requirement_id": "REQ::DIRECT",
            "acceptable_candidate_sets": [["DIRECT::MUST_HAVE"]],
            "canonical_positive_ids": ["DIRECT::MUST_HAVE"],
        },
        *reference["material_reference_groups"][1:],
    ]
    failed = evaluate_material_reference(
        selection=selection, reference=missing_unique
    )
    assert failed["required_group_gate_pass"] is False
    assert failed["required_group_coverage"] == pytest.approx(2 / 3)


def test_reference_must_match_runtime_requirement_plan() -> None:
    plan = validate_requirement_plan(
        evidence_request=_request(), plan=_plan(), review_k=20
    )
    selection = select_request_bound_review(candidates=_candidates(), plan=plan)
    reference = {
        "schema_version": "fin_ia_material_evidence_set_reference_v1_0",
        "request_id": "ER::DEV::CASH",
        "requirement_plan_digest": plan["plan_digest"],
        "material_reference_groups": [
            {
                "requirement_id": "REQ::UNKNOWN",
                "acceptable_candidate_sets": [["DIRECT::OCF"]],
                "canonical_positive_ids": ["DIRECT::OCF"],
            }
        ],
    }
    with pytest.raises(EvidenceSetCoverageError, match="requirement_mismatch"):
        evaluate_material_reference(selection=selection, reference=reference)


def test_tampered_plan_and_selection_are_rejected() -> None:
    plan = validate_requirement_plan(
        evidence_request=_request(), plan=_plan(), review_k=20
    )
    tampered_plan = dict(plan)
    tampered_plan["review_k"] = 21
    with pytest.raises(EvidenceSetCoverageError, match="plan_digest_invalid"):
        select_request_bound_review(candidates=_candidates(), plan=tampered_plan)

    selection = select_request_bound_review(candidates=_candidates(), plan=plan)
    tampered_selection = dict(selection)
    tampered_selection["selected_candidate_ids"] = ["COUNTER::MARGIN"]
    reference = {
        "schema_version": "fin_ia_material_evidence_set_reference_v1_0",
        "request_id": "ER::DEV::CASH",
        "requirement_plan_digest": plan["plan_digest"],
        "material_reference_groups": [
            {
                "requirement_id": requirement_id,
                "acceptable_candidate_sets": [[selection["selected_candidate_ids"][0]]],
                "canonical_positive_ids": [selection["selected_candidate_ids"][0]],
            }
            for requirement_id in selection["requirement_ids"]
        ],
    }
    with pytest.raises(EvidenceSetCoverageError, match="selection_digest_invalid"):
        evaluate_material_reference(selection=tampered_selection, reference=reference)
