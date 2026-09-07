from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from retrieval.contracts import (  # noqa: E402
    load_evidence_request,
    load_financial_research_kernel,
)
from retrieval.financial_intent_v3 import (  # noqa: E402
    concept_aliases,
    evaluate_financial_intent,
)
from retrieval.evidence_role_v4 import (  # noqa: E402
    evaluate_evidence_role,
)
from retrieval.hybrid_candidate_runtime import (  # noqa: E402
    HYBRID_RESULT_GROUPED_RECALL_SCHEMA_VERSION,
    HYBRID_RUNTIME_POLICY_GROUPED_RECALL_SCHEMA_VERSION,
    _policy_feature_flags,
    retrieve_hybrid_candidates,
)
from retrieval.query_plan_v3 import (  # noqa: E402
    QUERY_PLAN_V3_GROUPED_RECALL_SCHEMA_VERSION,
    compile_query_facet_plan_for_request,
)
from retrieval.route_compiler import (  # noqa: E402
    load_query_object_fact_route_policy,
)


def _read(ref: str) -> dict[str, object]:
    return json.loads((ROOT / ref).read_text(encoding="utf-8"))


def _contracts():
    kernel = load_financial_research_kernel(
        _read(
            "configs/retrieval/"
            "fin_ia_0_1_3_s1_financial_research_kernel_v1_4.json"
        )
    )
    route = load_query_object_fact_route_policy(
        _read(
            "configs/retrieval/"
            "fin_ia_0_1_3_s1c_query_object_fact_route_policy_v1_4.json"
        ),
        kernel,
    )
    ontology = _read(
        "configs/retrieval/"
        "fin_ia_0_1_3_s1_financial_intent_ontology_v1_4.json"
    )
    program = _read(
        "configs/retrieval/"
        "fin_ia_0_1_3_s1_dell_proposition_coverage_execution_program_v1_2.json"
    )
    request_row = next(
        row
        for row in program["evidence_requests"]
        if row["request_id"]
        == "REQ::DELL::SUPPLY_UPSTREAM_CAPACITY::V1"
    )
    request = load_evidence_request(request_row, kernel)
    return kernel, route, ontology, program, request


def _object(identity: str, *, ticker: str, text: str) -> dict[str, object]:
    return {
        "schema_version": "fin_ia_compiled_financial_object_view_v1_3",
        "compiled_object_id": identity,
        "object_kind": "claim",
        "model_text": text,
        "base_object_view": {
            "source_record_id": f"SRC::{identity}",
            "ticker": ticker,
            "company": ticker,
            "source_type": "10-Q",
            "source_tier": "primary_sec_filing",
            "publication_date": "2026-05-20",
            "period_end": "2026-04-26",
            "fiscal_year": 2027,
            "section": "Management's Discussion and Analysis",
            "subsection": "Supply and demand",
        },
        "lineage_source_record_ids": [f"SRC::{identity}"],
        "candidate_not_evidence": True,
        "numeric_authority": False,
        "evidence_promoted": False,
    }


def test_dell_program_intents_are_typed_in_successor_ontology() -> None:
    _, _, ontology, program, _ = _contracts()
    mappings: list[tuple[str, str]] = []
    for request in program["evidence_requests"]:
        for family, key in (
            ("metric_concepts", "metric_intents"),
            ("product_concepts", "product_intents"),
        ):
            for intent in request[key]:
                concept_id, _ = concept_aliases(
                    intent,
                    family=family,
                    ontology=ontology,
                )
                mappings.append((intent, concept_id))

    assert mappings
    assert all(not concept_id.startswith("unmapped::") for _, concept_id in mappings)
    assert ontology["authority"][
        "grouped_recall_surfaces_are_candidate_only"
    ] is True
    assert ontology["authority"][
        "grouped_recall_has_no_result_or_label_access"
    ] is True


def test_grouped_plan_exposes_supply_state_and_transition_without_labels() -> None:
    kernel, _, ontology, _, request = _contracts()
    plan = compile_query_facet_plan_for_request(
        kernel,
        request,
        ontology=ontology,
        grouped_surface_recall_enabled=True,
    )
    grouped = [
        row
        for row in plan.lanes[0].lexical_subqueries
        if row.query_kind == "product_grouped_disclosure_surface"
    ]
    surfaces = "\n".join(row.lexical_query for row in grouped)

    assert plan.schema_version == QUERY_PLAN_V3_GROUPED_RECALL_SCHEMA_VERSION
    assert "sold out" in surfaces
    assert "ramping at full speed" in surfaces
    assert "advanced packaging capacity" in surfaces
    assert "COBJ::" not in surfaces and "http" not in surfaces


def test_grouped_ontology_propagates_through_intent_evaluator() -> None:
    _, _, ontology, _, _ = _contracts()
    result = evaluate_financial_intent(
        {
            "model_text": "GPU supply release improved during the quarter.",
            "object_kind": "claim",
            "structured_projection": {},
        },
        metric_intents=(),
        product_intents=("GPU supply release",),
        acceptable_proxy=True,
        ontology=ontology,
    )

    assert result.schema_version == "fin_ia_financial_intent_evaluation_v1_4"
    assert result.product_compatibility == "compatible"

    grouped = evaluate_financial_intent(
        {
            "model_text": "Blackwell GPUs are sold out while production is ramping.",
            "object_kind": "claim",
            "structured_projection": {},
        },
        metric_intents=(),
        product_intents=("GPU supply release",),
        acceptable_proxy=True,
        ontology=ontology,
    )
    assert grouped.product_compatibility == "compatible"
    assert "product_grouped_recall_surface_matched_candidate_only" in (
        grouped.reason_codes
    )


def test_observed_public_supply_state_is_review_compatible_not_evidence() -> None:
    result = evaluate_evidence_role(
        {
            "ticker": "NVDA",
            "section": "Reviewed public source",
            "subsection": "NVIDIA Investor Relations",
            "source_type": "PUBLIC_WEB",
            "object_kind": "claim",
            "document_text": (
                "Blackwell production is ramping at full speed and cloud GPUs "
                "are sold out."
            ),
            "structured_projection": {},
        },
        slot_id="capacity_inputs_execution",
        facet_id="upstream_capacity_context",
        subject_ticker="DELL",
        evidence_owner_ticker="NVDA",
        relationship_direction="upstream_supplier_to_subject",
    )

    assert result.compatibility == "compatible"
    assert "direct_supply_capacity_signal" in result.labels
    assert "supply_risk_or_counterevidence" in result.labels
    assert result.evidence_promoted is False


def test_owner_union_admits_owner_candidate_crowded_out_of_global_prefix() -> None:
    kernel, route, ontology, _, request = _contracts()
    crowded = [
        _object(
            f"AA-DELL-{index:03d}",
            ticker="DELL",
            text=(
                "Blackwell production is ramping at full speed while cloud GPUs "
                "are sold out and demand is extraordinary."
            ),
        )
        for index in range(24)
    ]
    target = _object(
        "ZZ-NVDA-TARGET",
        ticker="NVDA",
        text=(
            "Blackwell production is ramping at full speed while cloud GPUs "
            "are sold out and demand is extraordinary."
        ),
    )
    other_owners = [
        _object(
            f"YY-{owner}-{index}",
            ticker=owner,
            text=f"{owner} capacity and supply discussion {index}",
        )
        for owner in ("NVDA", "MU", "TSM")
        for index in range(2)
    ]
    objects = tuple([*crowded, target, *other_owners])
    embeddings = np.zeros((len(objects), 4), dtype=np.float32)
    common = {
        "request": request,
        "kernel": kernel,
        "route_policy": route,
        "objects": objects,
        "qwen_document_embeddings": embeddings,
        "qwen_query_embedding": np.zeros(4, dtype=np.float32),
        "first_stage_limit": 8,
        "candidate_union_limit": 12,
        "output_limit": 8,
        "max_candidates_per_source_record": 2,
        "minimum_candidates_per_owner": 1,
        "intent_ontology": ontology,
        "typed_balanced_lexical_enabled": True,
        "grouped_surface_recall_enabled": True,
        "lexical_positive_scores_only": True,
    }

    global_only = retrieve_hybrid_candidates(
        **common,
        owner_candidate_union_minimum=0,
    )
    balanced = retrieve_hybrid_candidates(
        **common,
        owner_candidate_union_minimum=3,
    )
    global_ids = {
        row["compiled_object_id"]
        for row in global_only["candidate_decision_seed"]
    }
    balanced_by_id = {
        row["compiled_object_id"]: row
        for row in balanced["candidate_decision_seed"]
    }

    assert "ZZ-NVDA-TARGET" not in global_ids
    assert "ZZ-NVDA-TARGET" in balanced_by_id
    assert "bm25_lexical" in balanced_by_id["ZZ-NVDA-TARGET"][
        "route_membership"
    ]
    assert balanced["schema_version"] == HYBRID_RESULT_GROUPED_RECALL_SCHEMA_VERSION
    trace = balanced["summary"]["owner_candidate_union"]
    assert trace["mode"] == "owner_floor_then_global_fill_v1"
    assert trace["admitted_outside_global_union_count"] > 0
    assert trace["result_or_label_access"] is False


def test_grouped_policy_inherits_all_predecessor_capabilities() -> None:
    assert _policy_feature_flags(
        HYBRID_RUNTIME_POLICY_GROUPED_RECALL_SCHEMA_VERSION
    ) == (True, True, True)
    policy = _read(
        "configs/retrieval/"
        "fin_ia_0_1_3_s1c_hybrid_candidate_runtime_policy_v1_6.json"
    )
    assert policy["schema_version"] == (
        HYBRID_RUNTIME_POLICY_GROUPED_RECALL_SCHEMA_VERSION
    )
    assert policy["typed_query_recall"]["zero_score_candidates_excluded"] is True
    assert policy["owner_balance"][
        "candidate_union_minimum_per_owner"
    ] == 12
