from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from retrieval.contracts import load_evidence_request, load_financial_research_kernel
from retrieval.evidence_role_v2 import evaluate_evidence_role
from retrieval.evaluation_assets import load_qualification_preregistration
from retrieval.financial_evidence_shortlist_v2 import (
    rank_financial_evidence_shortlist,
)
from retrieval.financial_intent_v2 import evaluate_financial_intent
from retrieval.qualification_runtime_v2 import load_qualification_runtime_bundle
from retrieval.query_plan import QueryLane
from retrieval.query_plan_v2 import compile_query_facet_plan_for_request
from retrieval.retrieval_need import compile_retrieval_needs
from sec_agent.runtime_resource_registry import resolve_registered_runtime_resource


POLICY_PATH = (
    ROOT
    / "configs/retrieval/fin_ia_0_1_3_s1_vs5_retrieval_need_compiler_policy_v1_2.json"
)
ONTOLOGY_PATH = (
    ROOT / "configs/retrieval/fin_ia_0_1_3_s1_financial_intent_ontology_v1_2.json"
)
PREREG_PATH = ROOT / "eval_sets/fin_0_1_3_s1/qualification_preregistration_v1_0.json"
OVERLAY_PATH = (
    ROOT
    / "configs/retrieval/fin_ia_0_1_3_s1_vs5_qualification_runtime_overlay_v1_0.json"
)
VALID_INPUT_PATH = (
    ROOT
    / "eval_sets/fin_0_1_3_s1/inputs/valid_temporal/vs5_qualification_inputs_v1_1.jsonl"
)
SUCCESSOR_POLICY_PATH = (
    ROOT
    / "configs/retrieval/fin_ia_0_1_3_s1_vs5_candidate_execution_policy_v1_1.json"
)


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _standalone(needs) -> set[tuple[str, tuple[str, ...]]]:
    return {
        (need.need_kind, tuple(need.intent_terms))
        for need in needs
        if need.need_kind in {"metric", "product"}
    }


def _assert_request_materiality_is_preserved(kernel, request) -> None:
    policy = _load_json(POLICY_PATH)
    ontology = _load_json(ONTOLOGY_PATH)
    plan = compile_query_facet_plan_for_request(kernel, request)
    expected = {
        *(('metric', (value,)) for value in request.metric_intents),
        *(('product', (value,)) for value in request.product_intents),
    }
    for lane in plan.lanes:
        lane_request = replace(request, requested_facet_ids=(lane.facet_id,))
        need_set = compile_retrieval_needs(
            request=lane_request,
            lane=lane,
            policy=policy,
            intent_ontology=ontology,
        )
        assert expected.issubset(_standalone(need_set.needs))

        reversed_request = replace(
            lane_request,
            metric_intents=tuple(reversed(lane_request.metric_intents)),
            product_intents=tuple(reversed(lane_request.product_intents)),
        )
        reversed_lane = compile_query_facet_plan_for_request(
            kernel, reversed_request
        ).lanes[0]
        reversed_set = compile_retrieval_needs(
            request=reversed_request,
            lane=reversed_lane,
            policy=policy,
            intent_ontology=ontology,
        )
        assert _standalone(need_set.needs) == _standalone(reversed_set.needs)


def test_observed_cases_preserve_request_terms_without_generic_facet_pollution() -> None:
    kernel_path = resolve_registered_runtime_resource(
        ROOT, "application.config.current_financial_research_kernel"
    )
    kernel = load_financial_research_kernel(_load_json(kernel_path))
    case_terms = {
        "DELL": ("AI-optimized servers", "server backlog"),
        "MU": ("HBM shipments", "data center demand"),
        "NVDA": ("data center compute", "cloud service provider demand"),
    }
    for case_key, products in case_terms.items():
        profile = kernel.cases[case_key]
        request = load_evidence_request(
            {
                "schema_version": "fin_ia_evidence_request_v1_0",
                "request_id": f"REQ-VS5-SUCCESSOR-{case_key}",
                "cell_id": f"CELL-VS5-SUCCESSOR-{case_key}",
                "requester_role": "qualification_researcher",
                "evidence_domain": "demand",
                "case_key": case_key,
                "subject_ticker": case_key,
                "research_as_of": profile.research_as_of.isoformat(),
                "target_entities": [case_key],
                "requested_facet_ids": ["orders_and_backlog"],
                "metric_intents": ["orders", "backlog"],
                "product_intents": list(products),
                "period": {
                    "start_date": None,
                    "end_date": profile.research_as_of.isoformat(),
                    "fiscal_years": [],
                },
                "granularity": "claim_table_and_bounded_context",
                "unit": "issuer_reported_native_unit",
                "acceptable_sources": ["10-K", "10-Q", "8-K", "20-F", "6-K"],
                "acceptable_proxy": False,
                "forbidden_proxy": ["wrong issuer", "wrong period"],
                "stop_condition": "return candidates or typed gap",
                "clarification_policy": "return_typed_gap",
            },
            kernel,
        )
        lane = compile_query_facet_plan_for_request(kernel, request).lanes[0]
        assert "bookings" not in lane.lexical_query
        assert all(value in lane.lexical_query for value in products)
        _assert_request_materiality_is_preserved(kernel, request)


def test_cost_successor_runtime_is_reproducible_and_temporal_pair_is_explicit() -> None:
    prereg = load_qualification_preregistration(PREREG_PATH)
    bundle = load_qualification_runtime_bundle(
        repo_root=ROOT,
        preregistration=prereg,
        overlay_path=OVERLAY_PATH,
    )
    materialized = {
        value["example_id"]: value
        for value in (
            json.loads(line)
            for line in VALID_INPUT_PATH.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    }
    policy = _load_json(POLICY_PATH)
    ontology = _load_json(ONTOLOGY_PATH)

    for row in bundle.inputs_by_split["valid_temporal"]:
        assert row.model_dump(mode="json") == materialized[row.example_id]
        request = load_evidence_request(
            row.runtime_input["evidence_request"], bundle.kernel
        )
        plan = compile_query_facet_plan_for_request(bundle.kernel, request)
        for lane in plan.lanes:
            lane_request = replace(request, requested_facet_ids=(lane.facet_id,))
            need_set = compile_retrieval_needs(
                request=lane_request,
                lane=lane,
                policy=policy,
                intent_ontology=ontology,
            )
            expected = {
                *(('metric', (value,)) for value in request.metric_intents),
                *(
                    ('product', (value,))
                    for value in request.product_intents
                    if value != "FY2024 FY2025 comparison"
                ),
            }
            assert expected.issubset(_standalone(need_set.needs))
            assert all("bookings" not in need.lexical_query for need in need_set.needs)
            if row.example_id.endswith("COST_TEMPORAL_CHANGE"):
                assert all(
                    need.fiscal_years == (2024, 2025)
                    and need.same_basis_comparison_required
                    for need in need_set.needs
                )
                assert all(
                    "FY2024 FY2025 comparison" not in need.intent_terms
                    for need in need_set.needs
                )


def test_successor_policy_binds_only_label_blind_r2_runtime_and_cuda_budget() -> None:
    policy = _load_json(SUCCESSOR_POLICY_PATH)
    assert policy["status"] == "frozen_before_successor_qualification_ranking"
    assert policy["lineage"]["attempt_disposition"] == (
        "valid_temporal_r2_of_maximum_two"
    )
    assert policy["lineage"]["thresholds_changed"] is False
    assert policy["lineage"]["hidden_inputs_or_references_opened"] is False
    for binding in policy["bound_inputs"].values():
        path = ROOT / binding["ref"]
        assert path.is_file()
        assert _sha256(path) == binding["sha256"]

    runtime_result = _load_json(
        ROOT
        / policy["bound_inputs"]["runtime_inputs_result"]["ref"]
    )
    assert [row["split"] for row in runtime_result["outputs"]] == [
        "valid_temporal"
    ]
    contract = policy["candidate_contract"]
    assert contract["learned_vector_device"] == "cuda:0"
    assert contract["learned_vector_precision"] == "fp16"
    assert contract["cpu_vector_fallback_allowed"] is False
    assert contract["final_review_prefix_length"] == contract["candidate_review_k"]
    assert contract["same_basis_temporal_candidate_reservation"] is True
    assert contract["standalone_request_intents_before_cross_products"] is True
    basis = policy["token_budget_basis"]["reranker_per_model"]
    assert basis["maximum_pair_count"] == (
        5
        * contract["reranker_pool_limit"]
        * contract["maximum_relevant_needs_per_candidate"]
    )


def test_v2_exact_unmapped_intent_and_request_bound_role_do_not_grant_synonyms() -> None:
    ontology = _load_json(ONTOLOGY_PATH)
    exact = evaluate_financial_intent(
        {
            "model_text": "Revenue and comparable sales increased 6%.",
            "object_kind": "claim",
            "structured_projection": {},
        },
        metric_intents=("revenue",),
        product_intents=("comparable sales",),
        acceptable_proxy=False,
        ontology=ontology,
    )
    synonym = evaluate_financial_intent(
        {
            "model_text": "Revenue and same-store sales increased 6%.",
            "object_kind": "claim",
            "structured_projection": {},
        },
        metric_intents=("revenue",),
        product_intents=("comparable sales",),
        acceptable_proxy=False,
        ontology=ontology,
    )
    role = evaluate_evidence_role(
        {
            "ticker": "TEST",
            "section": "Management's Discussion and Analysis",
            "document_text": (
                "Comparable sales increased 6%. Shopping frequency increased 5%."
            ),
            "object_kind": "claim",
        },
        slot_id="demand_volume_quality",
        facet_id="conversion_and_durability",
        subject_ticker="TEST",
        request_intent_terms=("comparable sales", "shopping frequency"),
    )
    accounting_policy = evaluate_evidence_role(
        {
            "ticker": "TEST",
            "section": "Financial Statements",
            "document_text": "The company recognizes revenue on a gross basis.",
            "object_kind": "claim",
        },
        slot_id="operating_performance",
        facet_id="reported_results",
        subject_ticker="TEST",
        request_intent_terms=("revenue",),
    )

    assert exact.compatibility == "compatible"
    assert exact.matched_product_aliases == ("comparable sales",)
    assert synonym.product_compatibility == "abstain"
    assert role.compatibility == "compatible"
    assert "direct_demand_signal" in role.labels
    assert "observed_operating_result" not in accounting_policy.labels


def test_v2_shortlist_reserves_same_metric_candidate_from_each_requested_year() -> None:
    def obj(identity: str, text: str, fiscal_year: int) -> dict[str, object]:
        return {
            "compiled_object_id": identity,
            "object_kind": "claim",
            "model_text": text,
            "structured_projection": {},
            "base_object_view": {
                "ticker": "TEST",
                "section": "Item 7",
                "subsection": "Results",
                "source_type": "10-K",
                "source_tier": "primary_sec_filing",
                "publication_date": f"{fiscal_year}-10-01",
                "period_end": f"{fiscal_year}-08-31",
                "fiscal_year": fiscal_year,
            },
        }

    lane = QueryLane(
        lane_id="lane::reported_results",
        slot_id="operating_performance",
        facet_id="reported_results",
        business_question_zh="结果如何？",
        execution_mode="local_lexical_candidate_generation",
        subject_ticker="TEST",
        evidence_owner_tickers=("TEST",),
        relationship_constraints=("subject_self_disclosure",),
        publication_date_lte="2026-12-31",
        source_types=("10-K",),
        required_source_roles=("issuer_disclosure",),
        exact_queries=(),
        lexical_query="revenue",
        lexical_tokens=("revenue",),
        owner_queries=(),
        semantic_query="Compare revenue across periods.",
        graph_constraints=(),
        forbidden_expansions=(),
        candidate_budget=8,
    )
    need = {
        "need_id": "need::revenue",
        "need_kind": "metric",
        "facet_id": "reported_results",
        "intent_terms": ["revenue"],
    }
    objects = {
        "noise": obj("noise", "Revenue recognition policy is described below.", 2026),
        "fy25": obj("fy25", "Revenue increased to 100 in fiscal 2025.", 2025),
        "fy26": obj("fy26", "Revenue increased to 120 in fiscal 2026.", 2026),
    }
    route_membership = {
        object_id: [
            {
                "route_id": "bm25_need_lexical",
                "need_id": need["need_id"],
                "rank": rank,
            }
        ]
        for rank, object_id in enumerate(("noise", "fy26", "fy25"), start=1)
    }
    ranking = rank_financial_evidence_shortlist(
        union_object_ids=("noise", "fy26", "fy25"),
        objects_by_id=objects,
        lane=lane,
        route_membership=route_membership,
        cross_encoder_ranks_by_id={},
        request={
            "metric_intents": ["revenue"],
            "product_intents": [],
            "acceptable_proxy": False,
            "period": {"fiscal_years": [2025, 2026]},
        },
        intent_ontology=_load_json(ONTOLOGY_PATH),
        retrieval_needs=[need],
    )

    assert [row["compiled_object_id"] for row in ranking[:2]] == ["fy25", "fy26"]
