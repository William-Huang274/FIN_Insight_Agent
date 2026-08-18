from __future__ import annotations

import json
from pathlib import Path
import random

import pytest

from retrieval.evidence_set_coverage import (
    EvidenceSetCoverageError,
    PLAN_SCHEMA_V1_1,
    compile_requirement_plan,
    select_request_bound_review,
    validate_requirement_plan,
)
from retrieval.material_evidence_runtime import (
    MaterialEvidenceRuntimeError,
    adapt_material_candidate_from_feature_views,
    compile_material_requirement_plan_from_runtime_input,
)


ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads(
    (
        ROOT
        / "configs/retrieval/fin_ia_0_1_3_s1_material_evidence_runtime_policy_v1_0.json"
    ).read_text(encoding="utf-8")
)
ONTOLOGY = json.loads(
    (
        ROOT
        / "configs/retrieval/fin_ia_0_1_3_s1_financial_intent_ontology_v1_2.json"
    ).read_text(encoding="utf-8")
)


def _temporal_runtime_input() -> dict:
    return {
        "case_identity": {
            "accounting_basis": "US_GAAP",
            "case_key": "COST",
        },
        "evidence_request": {
            "request_id": "ER::DEV::COST::TEMPORAL",
            "case_key": "COST",
            "target_entities": ["COST"],
            "metric_intents": [
                "revenue",
                "gross margin",
                "operating cash flow",
            ],
            "product_intents": ["FY2024 FY2025 comparison"],
            "requested_facet_ids": [
                "reported_results",
                "margin_and_incremental_profit",
                "working_capital_risk",
            ],
            "period": {"fiscal_years": [2024, 2025]},
            "unit": "issuer_reported_native_unit",
        },
        "retrieval_execution_plan": {
            "narrative_requests": [
                {
                    "facet_ids": ["reported_results"],
                    "metric_context_ids": ["revenue", "gross_margin"],
                    "product_intents": ["FY2024 FY2025 comparison"],
                },
                {
                    "facet_ids": ["margin_and_incremental_profit"],
                    "metric_context_ids": ["revenue", "gross_margin"],
                    "product_intents": ["FY2024 FY2025 comparison"],
                },
                {
                    "facet_ids": ["working_capital_risk"],
                    "metric_context_ids": ["operating_cash_flow"],
                    "product_intents": ["FY2024 FY2025 comparison"],
                },
            ]
        },
    }


def _object(
    object_id: str,
    *,
    ticker: str = "COST",
    fiscal_year: int = 2025,
    metric: str = "Total revenue",
    years: str = "2025 | 2024 | 2023",
) -> dict:
    return {
        "compiled_object_id": object_id,
        "object_kind": "metric_row",
        "model_text": f"Header: {years}\nRow: {metric} | 100 | 90 | 80",
        "base_object_view": {
            "ticker": ticker,
            "fiscal_year": fiscal_year,
            "source_type": "10-K",
            "publication_date": f"{fiscal_year}-10-01",
        },
        "structured_projection": {
            "period_hints": [years],
            "header_lines": [years],
            "metric_row_label": metric,
        },
    }


def _feature(
    object_id: str,
    *,
    facet_id: str = "reported_results",
    role_labels: tuple[str, ...] = ("financial_statement_or_reconciliation",),
    metric: str = "revenue",
) -> dict:
    return {
        "facet_id": facet_id,
        "feature": {
            "compiled_object_id": object_id,
            "composite_compatibility": "compatible",
            "best_retrieval_need": {
                "need_id": "NEED::1",
                "need_kind": "metric",
                "intent_terms": [metric],
            },
            "evidence_role": {
                "compatibility": "compatible",
                "labels": list(role_labels),
            },
            "financial_intent": {
                "compatibility": "compatible",
                "metric_compatibility": "compatible",
                "product_compatibility": "not_requested",
            },
        },
    }


def _candidate(
    object_id: str,
    rank: int,
    *,
    bindings: list[dict],
    ticker: str = "COST",
    case_key: str = "COST",
) -> dict:
    return {
        "schema_version": "fin_ia_material_candidate_metadata_v1_1",
        "compiled_object_id": object_id,
        "base_rank": rank,
        "score": 1.0 / rank,
        "case_key": case_key,
        "target_entities": [ticker],
        "material_bindings": bindings,
    }


def test_real_temporal_directive_is_not_fabricated_as_product_scope() -> None:
    plan, receipt = compile_material_requirement_plan_from_runtime_input(
        runtime_input=_temporal_runtime_input(),
        policy=POLICY,
        ontology=ONTOLOGY,
    )
    assert plan["schema_version"] == PLAN_SCHEMA_V1_1
    assert len(plan["requirement_groups"]) == 6
    assert plan["maximum_reserved_capacity"] == 11
    assert all(not group["product_ids"] for group in plan["requirement_groups"])
    counter = next(
        row for row in plan["requirement_groups"] if row["role"] == "counter"
    )
    assert counter["metric_ids"] == []
    assert counter["period_mode"] == "any"
    assert receipt["temporal_directives_excluded_from_product_scope"] == [
        "FY2024 FY2025 comparison"
    ]
    assert receipt["candidate_or_reference_inputs_read"] is False


def test_v10_temporal_rule_remains_strict_while_v11_allows_no_product() -> None:
    request = _temporal_runtime_input()["evidence_request"]
    group = {
        "requirement_id": "REQ::TEMP",
        "facet_id": "reported_results",
        "role": "direct",
        "metric_ids": ["revenue"],
        "product_ids": [],
        "target_entities": ["COST"],
        "period_mode": "all_periods_same_basis",
        "fiscal_years": [2024, 2025],
        "minimum_candidates": 1,
        "priority": 1,
    }
    with pytest.raises(EvidenceSetCoverageError, match="temporal_scope_not_atomic"):
        validate_requirement_plan(
            evidence_request=request,
            plan={
                "schema_version": "fin_ia_material_evidence_requirement_plan_v1_0",
                "request_id": request["request_id"],
                "requirement_groups": [group],
            },
            review_k=20,
        )
    plan = compile_requirement_plan(
        evidence_request=request,
        material_requirements=[group],
        review_k=20,
        schema_version=PLAN_SCHEMA_V1_1,
    )
    assert plan["requirement_groups"][0]["product_ids"] == []


def test_v10_selection_shape_does_not_inherit_v11_receipt_fields() -> None:
    request = {
        "request_id": "ER::V10::COMPAT",
        "case_key": "COST",
        "target_entities": ["COST"],
        "metric_intents": ["revenue"],
        "product_intents": ["membership"],
        "requested_facet_ids": ["reported_results"],
        "period": {"fiscal_years": []},
    }
    plan = compile_requirement_plan(
        evidence_request=request,
        material_requirements=[
            {
                "requirement_id": "REQ::V10::COMPAT",
                "facet_id": "reported_results",
                "role": "direct",
                "metric_ids": ["revenue"],
                "product_ids": ["membership"],
                "target_entities": ["COST"],
                "period_mode": "any",
                "fiscal_years": [],
                "minimum_candidates": 1,
                "priority": 1,
            }
        ],
        review_k=2,
    )
    selection = select_request_bound_review(
        candidates=[
            {
                "compiled_object_id": "COBJ::V10",
                "base_rank": 1,
                "score": 1.0,
                "case_key": "COST",
                "target_entities": ["COST"],
                "facet_ids": ["reported_results"],
                "roles": ["direct"],
                "metric_ids": ["revenue"],
                "product_ids": ["membership"],
                "fiscal_years": [],
                "same_basis_key": "",
            }
        ],
        plan=plan,
    )
    assert selection["schema_version"] == "fin_ia_request_bound_candidate_review_v1_0"
    assert "request_alignment_excluded_candidate_ids" not in selection
    assert "coverage_mode" not in selection["requirement_receipts"][0]


def test_adapter_keeps_facet_role_intent_binding_and_multiyear_basis() -> None:
    runtime = _temporal_runtime_input()
    obj = _object("COBJ::REVENUE")
    candidate = adapt_material_candidate_from_feature_views(
        case_key="COST",
        candidate_row={
            "compiled_object_id": "COBJ::REVENUE",
            "rank": 7,
            "score": 0.77,
        },
        object_row=obj,
        feature_views=[_feature("COBJ::REVENUE")],
        evidence_request=runtime["evidence_request"],
        accounting_basis="US_GAAP",
        policy=POLICY,
        ontology=ONTOLOGY,
    )
    assert candidate["fiscal_years"] == [2024, 2025]
    assert {(row["facet_id"], row["role"]) for row in candidate["material_bindings"]} == {
        ("reported_results", "direct"),
        ("reported_results", "bridge"),
    }
    assert all(row["metric_ids"] == ["revenue"] for row in candidate["material_bindings"])
    assert all(row["product_ids"] == [] for row in candidate["material_bindings"])
    assert all(row["same_basis_key"].startswith("BASIS::") for row in candidate["material_bindings"])
    assert candidate["candidate_is_not_evidence"] is True
    assert candidate["numeric_fact_authority"] is False


def test_counter_role_does_not_require_primary_metric_compatibility() -> None:
    runtime = _temporal_runtime_input()
    obj = _object(
        "COBJ::COUNTER",
        metric="Risk Factors",
        years="2025",
    )
    feature = _feature(
        "COBJ::COUNTER",
        facet_id="working_capital_risk",
        role_labels=("demand_risk_or_counterevidence",),
        metric="operating cash flow",
    )
    feature["feature"]["financial_intent"]["metric_compatibility"] = "incompatible"

    candidate = adapt_material_candidate_from_feature_views(
        case_key="COST",
        candidate_row={
            "compiled_object_id": "COBJ::COUNTER",
            "rank": 21,
            "score": 0.12,
        },
        object_row=obj,
        feature_views=[feature],
        evidence_request=runtime["evidence_request"],
        accounting_basis="US_GAAP",
        policy=POLICY,
        ontology=ONTOLOGY,
    )

    assert len(candidate["material_bindings"]) == 1
    binding = candidate["material_bindings"][0]
    assert binding["facet_id"] == "working_capital_risk"
    assert binding["role"] == "counter"
    assert binding["metric_ids"] == []
    assert binding["same_basis_key"] == ""


def test_correlated_bindings_prevent_false_flat_cross_product_match() -> None:
    request = {
        "request_id": "ER::CROSS",
        "case_key": "COST",
        "target_entities": ["COST"],
        "metric_intents": ["revenue", "gross margin"],
        "product_intents": [],
        "requested_facet_ids": ["reported_results", "issuer_counterevidence"],
        "period": {"fiscal_years": []},
    }
    plan = compile_requirement_plan(
        evidence_request=request,
        material_requirements=[
            {
                "requirement_id": "REQ::IMPOSSIBLE_CROSS",
                "facet_id": "reported_results",
                "role": "counter",
                "metric_ids": ["gross margin"],
                "product_ids": [],
                "target_entities": ["COST"],
                "period_mode": "any",
                "fiscal_years": [],
                "minimum_candidates": 1,
                "priority": 1,
            }
        ],
        review_k=20,
        schema_version=PLAN_SCHEMA_V1_1,
    )
    candidate = _candidate(
        "COBJ::CORRELATED",
        1,
        bindings=[
            {
                "facet_id": "reported_results",
                "role": "direct",
                "metric_ids": ["revenue"],
                "product_ids": [],
                "fiscal_years": [],
                "same_basis_key": "",
            },
            {
                "facet_id": "issuer_counterevidence",
                "role": "counter",
                "metric_ids": ["gross margin"],
                "product_ids": [],
                "fiscal_years": [],
                "same_basis_key": "",
            },
        ],
    )
    result = select_request_bound_review(candidates=[candidate], plan=plan)
    assert result["met_requirement_ids"] == []
    assert result["selected_candidate_ids"] == []
    assert result["request_alignment_excluded_candidate_ids"] == [
        "COBJ::CORRELATED"
    ]


def test_v11_review_filler_excludes_wrong_entity_and_unaligned_noise() -> None:
    request = _temporal_runtime_input()["evidence_request"]
    group = {
        "requirement_id": "REQ::REVENUE",
        "facet_id": "reported_results",
        "role": "direct",
        "metric_ids": ["revenue"],
        "product_ids": [],
        "target_entities": ["COST"],
        "period_mode": "all_periods_same_basis",
        "fiscal_years": [2024, 2025],
        "minimum_candidates": 1,
        "priority": 1,
    }
    plan = compile_requirement_plan(
        evidence_request=request,
        material_requirements=[group],
        review_k=20,
        schema_version=PLAN_SCHEMA_V1_1,
    )
    aligned_binding = {
        "facet_id": "reported_results",
        "role": "direct",
        "metric_ids": ["revenue"],
        "product_ids": [],
        "fiscal_years": [2024, 2025],
        "same_basis_key": "BASIS::REV",
    }
    candidates = [
        _candidate("COBJ::WRONG", 1, bindings=[aligned_binding], ticker="OTHER"),
        _candidate("COBJ::NOISE", 2, bindings=[]),
        _candidate("COBJ::RIGHT", 30, bindings=[aligned_binding]),
    ]
    result = select_request_bound_review(candidates=candidates, plan=plan)
    assert result["selected_candidate_ids"] == ["COBJ::RIGHT"]
    assert result["hard_boundary_rejected_candidate_ids"] == ["COBJ::WRONG"]
    assert result["request_alignment_excluded_candidate_ids"] == ["COBJ::NOISE"]


def test_v11_two_object_temporal_bundle_is_stable_under_permutation() -> None:
    request = _temporal_runtime_input()["evidence_request"]
    plan = compile_requirement_plan(
        evidence_request=request,
        material_requirements=[
            {
                "requirement_id": "REQ::OCF",
                "facet_id": "working_capital_risk",
                "role": "bridge",
                "metric_ids": ["operating cash flow"],
                "product_ids": [],
                "target_entities": ["COST"],
                "period_mode": "all_periods_same_basis",
                "fiscal_years": [2024, 2025],
                "minimum_candidates": 1,
                "priority": 1,
            }
        ],
        review_k=20,
        schema_version=PLAN_SCHEMA_V1_1,
    )
    candidates = []
    for rank, year in ((9, 2024), (4, 2025)):
        candidates.append(
            _candidate(
                f"COBJ::OCF::{year}",
                rank,
                bindings=[
                    {
                        "facet_id": "working_capital_risk",
                        "role": "bridge",
                        "metric_ids": ["operating cash flow"],
                        "product_ids": [],
                        "fiscal_years": [year],
                        "same_basis_key": "BASIS::OCF",
                    }
                ],
            )
        )
    expected = select_request_bound_review(candidates=candidates, plan=plan)
    random.Random(20260818).shuffle(candidates)
    actual = select_request_bound_review(candidates=candidates, plan=plan)
    assert expected["met_requirement_ids"] == ["REQ::OCF"]
    assert expected["selected_candidate_ids"][:2] == [
        "COBJ::OCF::2024",
        "COBJ::OCF::2025",
    ]
    assert actual["selection_digest"] == expected["selection_digest"]


def test_temporal_multi_product_fallback_requires_explicit_blueprint() -> None:
    runtime = _temporal_runtime_input()
    runtime["evidence_request"]["product_intents"] = [
        "FY2024 FY2025 comparison",
        "data center platform",
        "advanced packaging and CoWoS capacity",
    ]
    runtime["retrieval_execution_plan"]["narrative_requests"][0][
        "product_intents"
    ] = ["data center platform", "advanced packaging and CoWoS capacity"]
    with pytest.raises(
        MaterialEvidenceRuntimeError,
        match="temporal_product_scope_requires_blueprint",
    ):
        compile_material_requirement_plan_from_runtime_input(
            runtime_input=runtime,
            policy=POLICY,
            ontology=ONTOLOGY,
        )


def test_unclassified_product_topic_requires_blueprint_without_becoming_hard_axis() -> None:
    runtime = _temporal_runtime_input()
    runtime["evidence_request"]["product_intents"] = [
        "AI server customer concentration, pricing and cancellation risk"
    ]
    runtime["evidence_request"]["period"]["fiscal_years"] = []
    runtime["retrieval_execution_plan"]["narrative_requests"] = [
        {
            "facet_ids": ["reported_results"],
            "metric_context_ids": ["revenue"],
            "product_intents": [
                "AI server customer concentration, pricing and cancellation risk"
            ],
        }
    ]
    plan, receipt = compile_material_requirement_plan_from_runtime_input(
        runtime_input=runtime,
        policy=POLICY,
        ontology=ONTOLOGY,
    )
    assert all(not row["product_ids"] for row in plan["requirement_groups"])
    assert receipt["explicit_blueprint_required_for_full_product_scope"] is True
    assert receipt[
        "unclassified_product_intents_excluded_from_hard_material_scope"
    ] == ["AI server customer concentration, pricing and cancellation risk"]


def test_collective_axis_bundle_can_join_metric_table_and_mechanism_narrative() -> None:
    request = {
        "request_id": "ER::COLLECTIVE",
        "case_key": "COST",
        "target_entities": ["COST"],
        "metric_intents": ["gross margin"],
        "product_intents": ["wages"],
        "requested_facet_ids": ["margin_and_incremental_profit"],
        "period": {"fiscal_years": []},
    }
    plan = compile_requirement_plan(
        evidence_request=request,
        material_requirements=[
            {
                "requirement_id": "REQ::COLLECTIVE",
                "facet_id": "margin_and_incremental_profit",
                "role": "bridge",
                "metric_ids": ["gross margin"],
                "product_ids": ["wages"],
                "target_entities": ["COST"],
                "period_mode": "any",
                "fiscal_years": [],
                "minimum_candidates": 1,
                "coverage_mode": "collective_axes",
                "priority": 1,
            }
        ],
        review_k=2,
        schema_version=PLAN_SCHEMA_V1_1,
    )
    base = {
        "facet_id": "margin_and_incremental_profit",
        "role": "bridge",
        "fiscal_years": [],
        "same_basis_key": "",
    }
    candidates = [
        _candidate(
            "COBJ::TABLE",
            2,
            bindings=[
                {**base, "metric_ids": ["gross margin"], "product_ids": []}
            ],
        ),
        _candidate(
            "COBJ::NARRATIVE",
            4,
            bindings=[{**base, "metric_ids": [], "product_ids": ["wages"]}],
        ),
    ]
    result = select_request_bound_review(candidates=candidates, plan=plan)
    assert result["met_requirement_ids"] == ["REQ::COLLECTIVE"]
    assert result["selected_candidate_ids"] == [
        "COBJ::TABLE",
        "COBJ::NARRATIVE",
    ]
