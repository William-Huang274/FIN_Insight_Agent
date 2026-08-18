from __future__ import annotations

import json
from pathlib import Path
import random

import pytest

from retrieval.evidence_set_coverage import (
    EvidenceSetCoverageError,
    PLAN_SCHEMA_V1_1,
    PLAN_SCHEMA_V1_2,
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
CURRENT_POLICY = json.loads(
    (
        ROOT
        / "configs/retrieval/fin_ia_0_1_3_s1_product_material_evidence_runtime_policy_v1_1.json"
    ).read_text(encoding="utf-8")
)
CURRENT_ONTOLOGY = json.loads(
    (
        ROOT
        / "configs/retrieval/fin_ia_0_1_3_s1_financial_intent_ontology_v1_3.json"
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
    assert plan["schema_version"] == PLAN_SCHEMA_V1_2
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


def test_v12_non_temporal_metrics_are_retrieval_context_not_duplicate_numeric_gate() -> None:
    request = {
        "request_id": "ER::V12::AUTHORITY",
        "case_key": "DELL",
        "target_entities": ["DELL"],
        "metric_intents": ["revenue", "operating income", "gross margin"],
        "product_intents": ["AI server revenue contribution"],
        "requested_facet_ids": ["reported_results"],
        "period": {"fiscal_years": []},
    }
    plan = compile_requirement_plan(
        evidence_request=request,
        material_requirements=[
            {
                "requirement_id": "REQ::V12::AUTHORITY",
                "facet_id": "reported_results",
                "role": "direct",
                "metric_ids": list(request["metric_intents"]),
                "metric_coverage_mode": "retrieval_context_only",
                "product_ids": list(request["product_intents"]),
                "product_coverage_mode": "all_of",
                "target_entities": ["DELL"],
                "period_mode": "any",
                "fiscal_years": [],
                "minimum_candidates": 1,
                "coverage_mode": "collective_axes",
                "priority": 1,
            }
        ],
        review_k=4,
        schema_version=PLAN_SCHEMA_V1_2,
    )
    assert plan["maximum_reserved_capacity"] == 1
    candidate = _candidate(
        "COBJ::AI_SERVER_RESULT",
        1,
        ticker="DELL",
        case_key="DELL",
        bindings=[
            {
                "facet_id": "reported_results",
                "role": "direct",
                "metric_ids": [],
                "product_ids": ["AI server revenue contribution"],
                "fiscal_years": [2027],
                "same_basis_key": "",
            }
        ],
    )
    result = select_request_bound_review(candidates=[candidate], plan=plan)
    assert result["met_requirement_ids"] == ["REQ::V12::AUTHORITY"]
    receipt = result["requirement_receipts"][0]
    assert receipt["metric_coverage_mode"] == "retrieval_context_only"
    assert receipt["missing_required_metric_ids"] == []
    assert result["numeric_fact_authority"] is False


def test_v12_all_of_capacity_is_satisfiable_and_partial_axes_are_receipted() -> None:
    request = {
        "request_id": "ER::V12::ALL",
        "case_key": "MU",
        "target_entities": ["MU"],
        "metric_intents": [],
        "product_intents": ["capacity", "shipments", "yield"],
        "requested_facet_ids": ["subject_execution"],
        "period": {"fiscal_years": []},
    }
    plan = compile_requirement_plan(
        evidence_request=request,
        material_requirements=[
            {
                "requirement_id": "REQ::V12::ALL",
                "facet_id": "subject_execution",
                "role": "direct",
                "metric_ids": [],
                "metric_coverage_mode": "retrieval_context_only",
                "product_ids": list(request["product_intents"]),
                "product_coverage_mode": "all_of",
                "target_entities": ["MU"],
                "period_mode": "any",
                "fiscal_years": [],
                "minimum_candidates": 1,
                "coverage_mode": "collective_axes",
                "priority": 1,
            }
        ],
        review_k=3,
        schema_version=PLAN_SCHEMA_V1_2,
    )
    assert plan["maximum_reserved_capacity"] == 3
    common = {
        "facet_id": "subject_execution",
        "role": "direct",
        "metric_ids": [],
        "fiscal_years": [2026],
        "same_basis_key": "",
    }
    candidates = [
        _candidate(
            "COBJ::CAPACITY",
            1,
            ticker="MU",
            case_key="MU",
            bindings=[{**common, "product_ids": ["capacity"]}],
        ),
        _candidate(
            "COBJ::SHIPMENTS",
            2,
            ticker="MU",
            case_key="MU",
            bindings=[{**common, "product_ids": ["shipments"]}],
        ),
    ]
    result = select_request_bound_review(candidates=candidates, plan=plan)
    assert result["unmet_requirement_ids"] == ["REQ::V12::ALL"]
    receipt = result["requirement_receipts"][0]
    assert receipt["partial_coverage_observed"] is True
    assert receipt["observed_product_ids"] == ["capacity", "shipments"]
    assert receipt["missing_required_product_ids"] == ["yield"]


def test_v12_any_of_product_topics_accepts_one_explicit_alternative() -> None:
    request = {
        "request_id": "ER::V12::ANY",
        "case_key": "NVDA",
        "target_entities": ["NVDA"],
        "metric_intents": [],
        "product_intents": ["GPU supply capacity", "data center platform"],
        "requested_facet_ids": ["issuer_policy_exposure"],
        "period": {"fiscal_years": []},
    }
    plan = compile_requirement_plan(
        evidence_request=request,
        material_requirements=[
            {
                "requirement_id": "REQ::V12::ANY",
                "facet_id": "issuer_policy_exposure",
                "role": "counter",
                "metric_ids": [],
                "metric_coverage_mode": "retrieval_context_only",
                "product_ids": list(request["product_intents"]),
                "product_coverage_mode": "any_of",
                "target_entities": ["NVDA"],
                "period_mode": "any",
                "fiscal_years": [],
                "minimum_candidates": 1,
                "coverage_mode": "collective_axes",
                "priority": 1,
            }
        ],
        review_k=1,
        schema_version=PLAN_SCHEMA_V1_2,
    )
    assert plan["maximum_reserved_capacity"] == 1
    candidate = _candidate(
        "COBJ::EXPORT_CONTROL",
        1,
        ticker="NVDA",
        case_key="NVDA",
        bindings=[
            {
                "facet_id": "issuer_policy_exposure",
                "role": "counter",
                "metric_ids": [],
                "product_ids": ["GPU supply capacity"],
                "fiscal_years": [2026],
                "same_basis_key": "",
            }
        ],
    )
    result = select_request_bound_review(candidates=[candidate], plan=plan)
    assert result["met_requirement_ids"] == ["REQ::V12::ANY"]
    assert result["requirement_receipts"][0][
        "missing_required_product_ids"
    ] == []


def test_collective_natural_need_can_enter_review_without_becoming_evidence() -> None:
    request = {
        "request_id": "ER::NATURAL",
        "case_key": "DELL",
        "target_entities": ["DELL"],
        "metric_intents": ["backlog", "orders"],
        "product_intents": ["AI server order growth", "backlog composition"],
        "requested_facet_ids": ["orders_and_backlog"],
        "period": {"fiscal_years": []},
    }
    plan = compile_requirement_plan(
        evidence_request=request,
        material_requirements=[
            {
                "requirement_id": "REQ::NATURAL",
                "facet_id": "orders_and_backlog",
                "role": "direct",
                "metric_ids": ["backlog", "orders"],
                "product_ids": [
                    "AI server order growth",
                    "backlog composition",
                ],
                "target_entities": ["DELL"],
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
        "facet_id": "orders_and_backlog",
        "role": "direct",
        "fiscal_years": [2026],
        "same_basis_key": "",
        "financial_intent_compatibility": "abstain",
        "candidate_comparability_only": True,
        "numeric_relation_authority": False,
    }
    candidates = [
        _candidate(
            "COBJ::DELL::BACKLOG",
            1,
            ticker="DELL",
            case_key="DELL",
            bindings=[
                {
                    **base,
                    "metric_ids": ["backlog", "orders"],
                    "product_ids": [],
                    "contextual_or_unclassified_need_product_intents": [
                        "AI server order growth",
                        "backlog composition",
                    ],
                }
            ],
        )
    ]
    result = select_request_bound_review(candidates=candidates, plan=plan)
    assert result["met_requirement_ids"] == ["REQ::NATURAL"]
    assert result["selected_candidate_ids"] == ["COBJ::DELL::BACKLOG"]
    assert result["candidate_is_not_evidence"] is True
    assert result["numeric_fact_authority"] is False
    assert candidates[0]["material_bindings"][0]["product_ids"] == []
    assert candidates[0]["material_bindings"][0][
        "financial_intent_compatibility"
    ] == "abstain"


def test_collective_bundle_requires_every_selected_metric_and_product_term() -> None:
    request = {
        "request_id": "ER::EVERY_AXIS",
        "case_key": "DELL",
        "target_entities": ["DELL"],
        "metric_intents": ["backlog", "orders"],
        "product_intents": ["AI demand", "customer concentration"],
        "requested_facet_ids": ["orders_and_backlog"],
        "period": {"fiscal_years": []},
    }
    plan = compile_requirement_plan(
        evidence_request=request,
        material_requirements=[
            {
                "requirement_id": "REQ::EVERY_AXIS",
                "facet_id": "orders_and_backlog",
                "role": "direct",
                "metric_ids": ["backlog", "orders"],
                "product_ids": ["AI demand", "customer concentration"],
                "target_entities": ["DELL"],
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
    partial = _candidate(
        "COBJ::PARTIAL",
        1,
        ticker="DELL",
        case_key="DELL",
        bindings=[
            {
                "facet_id": "orders_and_backlog",
                "role": "direct",
                "metric_ids": ["backlog"],
                "product_ids": [],
                "contextual_or_unclassified_need_product_intents": ["AI demand"],
                "fiscal_years": [2026],
                "same_basis_key": "",
            }
        ],
    )
    result = select_request_bound_review(candidates=[partial], plan=plan)
    assert result["met_requirement_ids"] == []
    assert result["unmet_requirement_ids"] == ["REQ::EVERY_AXIS"]


def test_collective_natural_need_remains_facet_role_and_exact_phrase_bound() -> None:
    request = {
        "request_id": "ER::BOUND_NATURAL",
        "case_key": "DELL",
        "target_entities": ["DELL"],
        "metric_intents": [],
        "product_intents": ["supplier constraints on GPUs"],
        "requested_facet_ids": ["upstream_or_demand_counterevidence"],
        "period": {"fiscal_years": []},
    }
    plan = compile_requirement_plan(
        evidence_request=request,
        material_requirements=[
            {
                "requirement_id": "REQ::BOUND_NATURAL",
                "facet_id": "upstream_or_demand_counterevidence",
                "role": "counter",
                "metric_ids": [],
                "product_ids": ["supplier constraints on GPUs"],
                "target_entities": ["DELL"],
                "period_mode": "any",
                "fiscal_years": [],
                "minimum_candidates": 1,
                "coverage_mode": "collective_axes",
                "priority": 1,
            }
        ],
        review_k=3,
        schema_version=PLAN_SCHEMA_V1_1,
    )
    common = {
        "metric_ids": [],
        "product_ids": [],
        "fiscal_years": [2026],
        "same_basis_key": "",
    }
    candidates = [
        _candidate(
            "COBJ::WRONG_ROLE",
            1,
            ticker="DELL",
            case_key="DELL",
            bindings=[
                {
                    **common,
                    "facet_id": "upstream_or_demand_counterevidence",
                    "role": "context",
                    "contextual_or_unclassified_need_product_intents": [
                        "supplier constraints on GPUs"
                    ],
                }
            ],
        ),
        _candidate(
            "COBJ::ADJACENT_PHRASE",
            2,
            ticker="DELL",
            case_key="DELL",
            bindings=[
                {
                    **common,
                    "facet_id": "upstream_or_demand_counterevidence",
                    "role": "counter",
                    "contextual_or_unclassified_need_product_intents": [
                        "memory industry supply constraints"
                    ],
                }
            ],
        ),
    ]
    result = select_request_bound_review(candidates=candidates, plan=plan)
    assert result["selected_candidate_ids"] == []
    assert result["request_alignment_excluded_candidate_ids"] == [
        "COBJ::WRONG_ROLE",
        "COBJ::ADJACENT_PHRASE",
    ]
    assert result["unmet_requirement_ids"] == ["REQ::BOUND_NATURAL"]


def test_single_binding_does_not_use_unclassified_natural_review_phrase() -> None:
    request = {
        "request_id": "ER::TEMPORAL_NATURAL",
        "case_key": "DELL",
        "target_entities": ["DELL"],
        "metric_intents": ["revenue"],
        "product_intents": ["AI server revenue contribution"],
        "requested_facet_ids": ["reported_results"],
        "period": {"fiscal_years": [2025, 2026]},
    }
    plan = compile_requirement_plan(
        evidence_request=request,
        material_requirements=[
            {
                "requirement_id": "REQ::TEMPORAL_NATURAL",
                "facet_id": "reported_results",
                "role": "direct",
                "metric_ids": ["revenue"],
                "product_ids": ["AI server revenue contribution"],
                "target_entities": ["DELL"],
                "period_mode": "all_periods_same_basis",
                "fiscal_years": [2025, 2026],
                "minimum_candidates": 1,
                "coverage_mode": "single_binding",
                "priority": 1,
            }
        ],
        review_k=2,
        schema_version=PLAN_SCHEMA_V1_1,
    )
    candidate = _candidate(
        "COBJ::TEMPORAL_CONTEXT_ONLY",
        1,
        ticker="DELL",
        case_key="DELL",
        bindings=[
            {
                "facet_id": "reported_results",
                "role": "direct",
                "metric_ids": ["revenue"],
                "product_ids": [],
                "contextual_or_unclassified_need_product_intents": [
                    "AI server revenue contribution"
                ],
                "fiscal_years": [2025, 2026],
                "same_basis_key": "BASIS::REVENUE",
            }
        ],
    )
    result = select_request_bound_review(candidates=[candidate], plan=plan)
    assert result["selected_candidate_ids"] == []
    assert result["unmet_requirement_ids"] == ["REQ::TEMPORAL_NATURAL"]


def test_v11_policy_splits_mixed_business_topics_into_atomic_propositions() -> None:
    runtime_input = {
        "case_identity": {"accounting_basis": "US_GAAP", "case_key": "MU"},
        "evidence_request": {
            "request_id": "ER::MU::ATOMIC_DEMAND",
            "case_key": "MU",
            "target_entities": ["MU"],
            "metric_intents": ["revenue"],
            "product_intents": [
                "HBM and data center business",
                "HBM4 shipment and capacity",
                "customer commitment and purchase structure",
            ],
            "requested_facet_ids": ["orders_and_backlog"],
            "period": {"fiscal_years": [2026]},
            "unit": "issuer_reported_native_unit",
        },
        "retrieval_execution_plan": {
            "narrative_requests": [
                {
                    "facet_ids": ["orders_and_backlog"],
                    "metric_context_ids": ["revenue"],
                    "product_intents": [
                        "HBM and data center business",
                        "HBM4 shipment and capacity",
                        "customer commitment and purchase structure",
                    ],
                }
            ]
        },
    }

    plan, receipt = compile_material_requirement_plan_from_runtime_input(
        runtime_input=runtime_input,
        policy=CURRENT_POLICY,
        ontology=CURRENT_ONTOLOGY,
    )

    assert receipt["schema_version"] == (
        "fin_ia_material_requirement_compiler_receipt_v1_2"
    )
    assert receipt["promoted_contextual_intents_by_facet"] == {
        "orders_and_backlog": ["customer commitment and purchase structure"]
    }
    groups = plan["requirement_groups"]
    assert len(groups) == 6
    assert {tuple(group["product_ids"]) for group in groups} == {
        ("HBM and data center business",),
        ("HBM4 shipment and capacity",),
        ("customer commitment and purchase structure",),
    }
    assert all(len(group["product_ids"]) == 1 for group in groups)
    assert plan["maximum_reserved_capacity"] <= CURRENT_POLICY["review_k"]


def test_v11_adapter_binds_executed_commitment_to_demand_proposition() -> None:
    request = {
        "request_id": "ER::MU::COMMITMENT",
        "case_key": "MU",
        "target_entities": ["MU"],
        "metric_intents": [],
        "product_intents": ["customer commitment and purchase structure"],
        "requested_facet_ids": ["orders_and_backlog"],
        "period": {"fiscal_years": [2026]},
    }
    object_row = {
        "compiled_object_id": "COBJ::MU::COMMITMENT",
        "object_kind": "claim",
        "model_text": (
            "We entered into strategic customer agreements with binding "
            "commitments for specific volumes over multi-year terms."
        ),
        "base_object_view": {
            "ticker": "MU",
            "fiscal_year": 2026,
            "source_type": "10-Q",
            "publication_date": "2026-07-01",
        },
        "structured_projection": {"period_hints": ["FY2026"]},
    }
    feature = {
        "facet_id": "orders_and_backlog",
        "feature": {
            "compiled_object_id": "COBJ::MU::COMMITMENT",
            "best_retrieval_need": {
                "need_id": "NEED::COMMITMENT",
                "need_kind": "product",
                "intent_terms": ["strategic customer agreement"],
            },
            "evidence_role": {
                "compatibility": "compatible",
                "labels": ["direct_demand_signal"],
            },
            "financial_intent": {
                "compatibility": "compatible",
                "metric_compatibility": "not_requested",
                "product_compatibility": "compatible",
            },
        },
    }

    candidate = adapt_material_candidate_from_feature_views(
        case_key="MU",
        candidate_row={
            "compiled_object_id": "COBJ::MU::COMMITMENT",
            "rank": 14,
            "score": 0.31,
        },
        object_row=object_row,
        feature_views=[feature],
        evidence_request=request,
        accounting_basis="US_GAAP",
        policy=CURRENT_POLICY,
        ontology=CURRENT_ONTOLOGY,
    )

    direct = next(
        binding
        for binding in candidate["material_bindings"]
        if binding["role"] == "direct"
    )
    assert direct["product_ids"] == [
        "customer commitment and purchase structure"
    ]
    assert direct["contextual_or_unclassified_need_product_intents"] == []
