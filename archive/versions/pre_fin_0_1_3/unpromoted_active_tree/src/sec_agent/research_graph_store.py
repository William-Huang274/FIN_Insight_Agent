from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Literal, Mapping, Sequence

from pydantic import Field

from .canonical_runtime.models import StrictModel, canonical_digest
from .product_intelligence_graph import (
    compile_s3_product_industry_projection_inputs,
)
from .research_skills import s3_graph_projection_skill_contracts
from .s4_case_runtime import (
    S4CaseRuntimeBinding,
    consume_s4_case_runtime_binding,
)


RESEARCH_GRAPH_NODE_SCHEMA_VERSION = "finsight_research_graph_node_v0_1"
RESEARCH_GRAPH_EDGE_SCHEMA_VERSION = "finsight_research_graph_edge_v0_1"
RESEARCH_GRAPH_EVIDENCE_SUPPORT_SCHEMA_VERSION = "finsight_research_graph_evidence_support_v0_1"
RESEARCH_GRAPH_SUMMARY_SCHEMA_VERSION = "finsight_research_graph_summary_v0_1"
RESEARCH_GRAPH_SQLITE_SCHEMA_VERSION = "finsight_research_graph_sqlite_v0_1"
S3_GRAPH_DECISION_CELL_PACK_CONTRACT_REF = (
    "fin01.s3.bounded_graph_product_market_risk_decision_cell_pack:v1"
)
S3_GRAPH_DECISION_CELL_OWNER_REF = (
    "src.sec_agent.research_graph_store:"
    "compile_s3_bounded_graph_decision_cell_pack"
)


DEFAULT_PRODUCT_GRAPH_NODES = "data/manifests/product_relationship_graph_nodes_v0_1.jsonl"
DEFAULT_PRODUCT_GRAPH_EDGES = "data/manifests/product_relationship_graph_edges_v0_1.jsonl"
DEFAULT_GOLD_MART_ROWS = "data/manifests/gold_fact_signal_mart_rows_v0_1.jsonl"

STRUCTURAL_PRODUCT_GRAPH_EDGE_TYPES: set[str] = {
    "HAS_PRODUCT_SLOT",
    "FAMILY_HAS_PRODUCT_SLOT",
}


class S3GraphEdgeAdmissibilityProbe(StrictModel):
    probe_id: str = Field(min_length=1)
    condition: Literal["naked", "stale", "inferred", "conflicting"]
    accepted_as_evidence: Literal[False] = False
    rejection_code: Literal[
        "graph_edge_missing_source_ref",
        "graph_edge_stale_as_of",
        "graph_edge_inferred_hypothesis",
        "graph_edge_conflicting_sources",
    ]


class S3BoundedGraphEdgeProjectionVersion(StrictModel):
    edge_projection_id: str = Field(min_length=1)
    edge_projection_digest: str = Field(min_length=1)
    program_cell_id: str = Field(min_length=1)
    use_case: Literal[
        "deployment_and_customer_context_to_demand_durability_check",
        "product_attribution_bridge_to_company_total_profitability",
        "packaging_dependency_to_counterevidence_followup",
    ]
    from_ref: str = Field(min_length=1)
    to_ref: str = Field(min_length=1)
    edge_type: str = Field(min_length=1)
    authority_mode: Literal[
        "candidate_metadata_context_only",
        "exact_financial_input_graph_bridge_hypothesis_only",
        "navigation_hypothesis_only",
    ]
    source_ref: str = Field(min_length=1)
    source_snapshot_ref: str = Field(min_length=1)
    source_as_of: str = Field(min_length=1)
    projection_as_of: str = Field(min_length=1)
    source_as_of_status: Literal[
        "bounded_period_label_not_exact_timestamp",
        "exact_reported_period",
    ]
    claim_boundary: str = Field(min_length=1)
    forbidden_claims: tuple[str, ...] = Field(min_length=1)
    followup_refs: tuple[str, ...] = Field(min_length=1)
    evidence_status: Literal[
        "context_only_claim_source_promotion_required",
        "context_only_product_attribution_source_required",
        "context_only_official_source_followup_required",
    ]
    inferred_or_hypothesis: Literal[True] = True
    conflict_status: Literal["not_evaluated_source_followup_required"] = (
        "not_evaluated_source_followup_required"
    )
    direct_evidence_authorized: Literal[False] = False
    numeric_authority: Literal[False] = False
    mechanism_path_is_fact: Literal[False] = False
    writer_citable: Literal[False] = False


class S3MarketPriceInContextVersion(StrictModel):
    market_context_id: str = Field(min_length=1)
    market_context_digest: str = Field(min_length=1)
    program_cell_id: str = Field(min_length=1)
    status: Literal[
        "typed_gap_no_same_as_of_consensus_or_price_reaction",
        "typed_gap_no_same_as_of_valuation_or_expectation_baseline",
        "typed_gap_no_same_as_of_crowding_ownership_or_volatility",
    ]
    projection_as_of: str = Field(min_length=1)
    required_source_families: tuple[str, ...] = Field(min_length=1)
    context_refs: tuple[str, ...] = ()
    authority: Literal["bounded_context_or_typed_gap_only"] = (
        "bounded_context_or_typed_gap_only"
    )
    exact_market_fact_authorized: Literal[False] = False
    writer_citable: Literal[False] = False


class S3RiskCounterevidenceContextVersion(StrictModel):
    risk_context_id: str = Field(min_length=1)
    risk_context_digest: str = Field(min_length=1)
    program_cell_id: str = Field(min_length=1)
    risk_type: str = Field(min_length=1)
    graph_edge_projection_ref: str = Field(min_length=1)
    impact_mechanism: str = Field(min_length=1)
    probability_status: Literal["typed_cannot_infer"] = "typed_cannot_infer"
    financial_impact_status: Literal["typed_cannot_infer"] = (
        "typed_cannot_infer"
    )
    support_boundary: str = Field(min_length=1)
    what_would_change: str = Field(min_length=1)
    evidence_status: Literal["context_or_gap_not_evidence"] = (
        "context_or_gap_not_evidence"
    )
    writer_citable: Literal[False] = False


class S3GraphDecisionCellProjectionVersion(StrictModel):
    cell_projection_id: str = Field(min_length=1)
    cell_projection_digest: str = Field(min_length=1)
    program_cell_id: str = Field(min_length=1)
    graph_edge_projection_ref: str = Field(min_length=1)
    product_industry_projection_input_ref: str = Field(min_length=1)
    market_context_ref: str = Field(min_length=1)
    risk_context_ref: str = Field(min_length=1)
    skill_contract_version_ref: str = Field(min_length=1)
    source_followup_refs: tuple[str, ...] = Field(min_length=1)
    typed_gaps: tuple[str, ...] = Field(min_length=1)
    accepted_evidence_refs: tuple[str, ...] = ()
    future_T06_specialist_input_eligible: Literal[True] = True
    current_specialist_model_consumed: Literal[False] = False


class S3BoundedGraphDecisionCellPackVersion(StrictModel):
    graph_pack_id: str = Field(min_length=1)
    graph_pack_version_ref: str = Field(min_length=1)
    graph_pack_digest: str = Field(min_length=1)
    graph_pack_contract_ref: str = S3_GRAPH_DECISION_CELL_PACK_CONTRACT_REF
    graph_owner_ref: str = S3_GRAPH_DECISION_CELL_OWNER_REF
    case_id: str = Field(min_length=1)
    work_unit_id: str = Field(min_length=1)
    attempt_id: str = Field(min_length=1)
    research_run_id: str = Field(min_length=1)
    execution_profile_version_ref: str = Field(min_length=1)
    decision_surface_contract_ref: str = Field(min_length=1)
    runtime_plan_version_ref: str = Field(min_length=1)
    runtime_plan_digest: str = Field(min_length=1)
    evidence_route_plan_version_ref: str = Field(min_length=1)
    evidence_route_plan_digest: str = Field(min_length=1)
    financial_pack_version_ref: str = Field(min_length=1)
    financial_pack_digest: str = Field(min_length=1)
    analysis_digest: str = Field(min_length=1)
    projection_as_of: str = Field(min_length=1)
    product_industry_inputs: tuple[dict[str, Any], ...] = Field(
        min_length=3, max_length=3
    )
    skill_contracts: tuple[dict[str, Any], ...] = Field(min_length=3, max_length=3)
    graph_edges: tuple[S3BoundedGraphEdgeProjectionVersion, ...] = Field(
        min_length=3, max_length=3
    )
    market_price_in_contexts: tuple[S3MarketPriceInContextVersion, ...] = Field(
        min_length=3, max_length=3
    )
    risk_contexts: tuple[S3RiskCounterevidenceContextVersion, ...] = Field(
        min_length=3, max_length=3
    )
    decision_cells: tuple[S3GraphDecisionCellProjectionVersion, ...] = Field(
        min_length=3, max_length=3
    )
    admissibility_probes: tuple[S3GraphEdgeAdmissibilityProbe, ...] = Field(
        min_length=4, max_length=4
    )
    existing_local_research_graph_read_count: Literal[1] = 1
    additional_graph_read_count: Literal[0] = 0
    model_calls: Literal[0] = 0
    provider_calls: Literal[0] = 0
    execution_network_calls: Literal[0] = 0
    source_network_calls: Literal[0] = 0
    external_tool_calls: Literal[0] = 0
    live_business_writes: Literal[0] = 0
    runtime_evidence_promotions: Literal[0] = 0
    graph_edges_promoted_to_evidence: Literal[0] = 0
    graph_allocated_financial_numbers: Literal[0] = 0


_S3_PROGRAM_CELLS = (
    "demand_authenticity_and_sustainability",
    "value_and_profit_capture",
    "bottleneck_counterevidence_and_what_would_change",
)


def classify_s3_graph_edge_admissibility(edge: Mapping[str, Any]) -> str:
    if not str(edge.get("source_ref") or ""):
        return "graph_edge_missing_source_ref"
    if edge.get("source_as_of_status") == "stale":
        return "graph_edge_stale_as_of"
    if edge.get("inferred_or_hypothesis") is True:
        return "graph_edge_inferred_hypothesis"
    if edge.get("conflict_status") == "conflicting":
        return "graph_edge_conflicting_sources"
    return "graph_projection_context_only_never_direct_evidence"


def _s3_graph_model_digest(model: StrictModel, *excluded: str) -> str:
    payload = model.model_dump(mode="json")
    for field in excluded:
        payload.pop(field, None)
    return canonical_digest(payload)


def _s3_graph_edge(**payload: Any) -> S3BoundedGraphEdgeProjectionVersion:
    payload = {
        **payload,
        "inferred_or_hypothesis": True,
        "conflict_status": "not_evaluated_source_followup_required",
        "direct_evidence_authorized": False,
        "numeric_authority": False,
        "mechanism_path_is_fact": False,
        "writer_citable": False,
    }
    digest = canonical_digest(payload)
    return S3BoundedGraphEdgeProjectionVersion(
        edge_projection_id=f"s3_graph_edge_projection_{digest[:24]}",
        edge_projection_digest=digest,
        **payload,
    )


def _s3_market_context(**payload: Any) -> S3MarketPriceInContextVersion:
    digest = canonical_digest(payload)
    return S3MarketPriceInContextVersion(
        market_context_id=f"s3_market_context_{digest[:24]}",
        market_context_digest=digest,
        **payload,
    )


def _s3_risk_context(**payload: Any) -> S3RiskCounterevidenceContextVersion:
    digest = canonical_digest(payload)
    return S3RiskCounterevidenceContextVersion(
        risk_context_id=f"s3_risk_context_{digest[:24]}",
        risk_context_digest=digest,
        **payload,
    )


def compile_s3_bounded_graph_decision_cell_pack(
    *,
    runtime_plan: Mapping[str, Any],
    evidence_route_plan: Mapping[str, Any],
    financial_pack: Mapping[str, Any],
    analysis_preview: Mapping[str, Any],
) -> S3BoundedGraphDecisionCellPackVersion:
    """Compile T05 from the already-read local preview; no route is executed here."""

    lineage_fields = ("case_id", "work_unit_id", "attempt_id", "research_run_id")
    if any(
        evidence_route_plan.get(field) != runtime_plan.get(field)
        or financial_pack.get(field) != runtime_plan.get(field)
        for field in lineage_fields
    ):
        raise ValueError("s3_graph_pack_runtime_lineage_mismatch")
    if (
        evidence_route_plan.get("runtime_plan_version_ref")
        != runtime_plan.get("runtime_plan_version_ref")
        or evidence_route_plan.get("runtime_plan_digest")
        != runtime_plan.get("runtime_plan_digest")
        or financial_pack.get("runtime_plan_version_ref")
        != runtime_plan.get("runtime_plan_version_ref")
        or financial_pack.get("runtime_plan_digest")
        != runtime_plan.get("runtime_plan_digest")
        or financial_pack.get("evidence_route_plan_version_ref")
        != evidence_route_plan.get("evidence_route_plan_version_ref")
        or financial_pack.get("evidence_route_plan_digest")
        != evidence_route_plan.get("evidence_route_plan_digest")
    ):
        raise ValueError("s3_graph_pack_upstream_digest_lineage_mismatch")
    counts = analysis_preview.get("execution_counts") or {}
    boundaries = analysis_preview.get("hard_boundaries") or {}
    if (
        analysis_preview.get("case_id") != runtime_plan.get("case_id")
        or analysis_preview.get("analysis_mode")
        != "bounded_local_deterministic_preview"
        or int(counts.get("research_graph_queries", -1)) != 1
        or any(
            int(counts.get(key, -1)) != 0
            for key in (
                "network_calls",
                "model_calls",
                "provider_calls",
                "external_tool_calls",
            )
        )
        or any(
            int(boundaries.get(key, -1)) != 0
            for key in (
                "case_mutations",
                "canonical_store_writes",
                "evidence_promotions",
                "network_calls",
                "model_calls",
            )
        )
    ):
        raise ValueError("s3_graph_pack_analysis_preview_boundary_invalid")
    projection_as_of = str(analysis_preview.get("as_of") or "")
    analysis_digest = str(analysis_preview.get("analysis_digest") or "")
    if not projection_as_of or not analysis_digest:
        raise ValueError("s3_graph_pack_analysis_identity_required")

    routes = {
        str(row.get("program_cell_id") or ""): row
        for row in evidence_route_plan.get("cell_routes") or ()
    }
    financial_cells = {
        str(row.get("program_cell_id") or ""): row
        for row in financial_pack.get("fundamental_decision_cells") or ()
    }
    if tuple(routes) != _S3_PROGRAM_CELLS or tuple(financial_cells) != _S3_PROGRAM_CELLS:
        raise ValueError("s3_graph_pack_cell_order_or_cardinality_invalid")
    product_inputs = compile_s3_product_industry_projection_inputs(
        evidence_route_plan=evidence_route_plan,
        financial_pack=financial_pack,
    )
    skill_contracts = s3_graph_projection_skill_contracts()
    if tuple(row["program_cell_id"] for row in skill_contracts) != _S3_PROGRAM_CELLS:
        raise ValueError("s3_graph_pack_skill_contract_scope_invalid")

    demand_route = routes[_S3_PROGRAM_CELLS[0]]
    value_route = routes[_S3_PROGRAM_CELLS[1]]
    risk_route = routes[_S3_PROGRAM_CELLS[2]]
    demand_candidate = demand_route["candidate_bundle"]["candidates"][0]
    value_candidate = value_route["candidate_bundle"]["candidates"][0]
    risk_candidate = risk_route["candidate_bundle"]["candidates"][0]
    risk_observation = risk_route.get("graph_observation") or {}
    risk_followup = risk_route.get("source_followup_request") or {}
    if (
        demand_candidate.get("source_role") != "official_issuer"
        or value_candidate.get("route_id") != "local_gold_sql_financial_table"
        or risk_candidate.get("source_role") != "relationship_graph"
        or risk_observation.get("observation_class") != "navigation_hypothesis_only"
        or risk_followup.get("execution_admission") != "not_admitted"
    ):
        raise ValueError("s3_graph_pack_source_route_semantics_invalid")
    financial_periods = {
        row["selector"]["period"]
        for row in financial_pack.get("selected_financial_rows") or ()
    }
    if len(financial_periods) != 1:
        raise ValueError("s3_graph_pack_financial_period_invalid")
    financial_period = next(iter(financial_periods))

    edges = (
        _s3_graph_edge(
            program_cell_id=_S3_PROGRAM_CELLS[0],
            use_case="deployment_and_customer_context_to_demand_durability_check",
            from_ref="entity:NVDA",
            to_ref=f"decision_cell:{_S3_PROGRAM_CELLS[0]}",
            edge_type="OFFICIAL_DISCLOSURE_TO_DEMAND_DURABILITY_CHECK",
            authority_mode="candidate_metadata_context_only",
            source_ref=str(demand_candidate["content_ref"]),
            source_snapshot_ref=str(demand_candidate["source_snapshot_ref"]),
            source_as_of=str(demand_candidate["period_ref"]),
            projection_as_of=projection_as_of,
            source_as_of_status="bounded_period_label_not_exact_timestamp",
            claim_boundary=(
                "Issuer and customer context can define a durability check; it does not "
                "establish persistent end demand or convert customer capex into NVDA revenue."
            ),
            forbidden_claims=(
                "durable_end_demand_fact",
                "customer_capex_equals_NVDA_revenue",
            ),
            followup_refs=(
                str(demand_route["promotion_assessment"]["assessment_id"]),
                str(demand_route["sourcehunter_boundary"]["boundary_id"]),
            ),
            evidence_status="context_only_claim_source_promotion_required",
        ),
        _s3_graph_edge(
            program_cell_id=_S3_PROGRAM_CELLS[1],
            use_case="product_attribution_bridge_to_company_total_profitability",
            from_ref="entity:NVDA:company_total_profitability",
            to_ref="product_context:accelerator_value_capture",
            edge_type="PRODUCT_ATTRIBUTION_BRIDGE_REQUIRED",
            authority_mode="exact_financial_input_graph_bridge_hypothesis_only",
            source_ref=str(financial_pack["financial_pack_version_ref"]),
            source_snapshot_ref=str(value_candidate["source_snapshot_ref"]),
            source_as_of=financial_period,
            projection_as_of=projection_as_of,
            source_as_of_status="exact_reported_period",
            claim_boundary=(
                "T04 company-total margins are exact deterministic inputs, while the "
                "product-to-profit bridge remains unavailable and cannot be allocated by Graph."
            ),
            forbidden_claims=(
                "accelerator_segment_margin",
                "incremental_AI_profit_capture",
                "cross_chain_economic_allocation",
            ),
            followup_refs=(
                str(financial_cells[_S3_PROGRAM_CELLS[1]]["fundamental_cell_id"]),
                str(value_route["sourcehunter_boundary"]["boundary_id"]),
            ),
            evidence_status="context_only_product_attribution_source_required",
        ),
        _s3_graph_edge(
            program_cell_id=_S3_PROGRAM_CELLS[2],
            use_case="packaging_dependency_to_counterevidence_followup",
            from_ref="entity:NVDA",
            to_ref="entity:TSM:advanced_packaging_context",
            edge_type="PACKAGING_DEPENDENCY_NAVIGATION_HYPOTHESIS",
            authority_mode="navigation_hypothesis_only",
            source_ref=str(risk_candidate["content_ref"]),
            source_snapshot_ref=str(risk_candidate["source_snapshot_ref"]),
            source_as_of=str(risk_candidate["period_ref"]),
            projection_as_of=projection_as_of,
            source_as_of_status="bounded_period_label_not_exact_timestamp",
            claim_boundary=str(risk_observation["relation_hypothesis"]),
            forbidden_claims=(
                "current_binding_packaging_constraint",
                "capacity_probability_price_revenue_margin_or_share",
            ),
            followup_refs=(
                str(risk_observation["observation_id"]),
                str(risk_followup["followup_request_id"]),
            ),
            evidence_status="context_only_official_source_followup_required",
        ),
    )

    market_statuses = (
        "typed_gap_no_same_as_of_consensus_or_price_reaction",
        "typed_gap_no_same_as_of_valuation_or_expectation_baseline",
        "typed_gap_no_same_as_of_crowding_ownership_or_volatility",
    )
    market_contexts = tuple(
        _s3_market_context(
            program_cell_id=cell_id,
            status=status,
            projection_as_of=projection_as_of,
            required_source_families=(
                "market_snapshot",
                "capital_macro_pack",
                "capital_market_feedback",
            ),
            context_refs=(),
            authority="bounded_context_or_typed_gap_only",
            exact_market_fact_authorized=False,
            writer_citable=False,
        )
        for cell_id, status in zip(_S3_PROGRAM_CELLS, market_statuses, strict=True)
    )
    risk_specs = (
        (
            "demand_durability_reversal",
            "Deployment breadth or subsequent-period conversion may reverse while current candidates remain unpromoted.",
            "Promoted same-scope subsequent-period issuer and customer evidence shows persistence without inventory or lead-time reversal.",
        ),
        (
            "product_profit_attribution_gap",
            "Company-total profitability may not represent accelerator, segment, or cross-chain economics.",
            "A reviewed same-period segment or product bridge attributes profit without exceeding source authority.",
        ),
        (
            "packaging_dependency_not_confirmed_as_constraint",
            "A relationship path may identify a dependency without showing a current binding bottleneck.",
            str(risk_followup["objective"]),
        ),
    )
    risk_contexts = tuple(
        _s3_risk_context(
            program_cell_id=cell_id,
            risk_type=risk_type,
            graph_edge_projection_ref=edge.edge_projection_id,
            impact_mechanism=mechanism,
            probability_status="typed_cannot_infer",
            financial_impact_status="typed_cannot_infer",
            support_boundary=(
                "The row is counterevidence context or a typed gap, not Evidence, "
                "probability, quantified impact, or final judgment."
            ),
            what_would_change=what_would_change,
            evidence_status="context_or_gap_not_evidence",
            writer_citable=False,
        )
        for cell_id, edge, (risk_type, mechanism, what_would_change) in zip(
            _S3_PROGRAM_CELLS, edges, risk_specs, strict=True
        )
    )

    cells: list[S3GraphDecisionCellProjectionVersion] = []
    for index, cell_id in enumerate(_S3_PROGRAM_CELLS):
        payload = {
            "program_cell_id": cell_id,
            "graph_edge_projection_ref": edges[index].edge_projection_id,
            "product_industry_projection_input_ref": product_inputs[index][
                "projection_input_ref"
            ],
            "market_context_ref": market_contexts[index].market_context_id,
            "risk_context_ref": risk_contexts[index].risk_context_id,
            "skill_contract_version_ref": skill_contracts[index][
                "contract_version_ref"
            ],
            "source_followup_refs": edges[index].followup_refs,
            "typed_gaps": tuple(product_inputs[index]["typed_gaps"])
            + (market_contexts[index].status,),
            "accepted_evidence_refs": (),
            "future_T06_specialist_input_eligible": True,
            "current_specialist_model_consumed": False,
        }
        digest = canonical_digest(payload)
        cells.append(
            S3GraphDecisionCellProjectionVersion(
                cell_projection_id=f"s3_graph_decision_cell_{digest[:24]}",
                cell_projection_digest=digest,
                **payload,
            )
        )

    probe_inputs = (
        ("naked", {"source_ref": ""}),
        ("stale", {"source_ref": "source", "source_as_of_status": "stale"}),
        (
            "inferred",
            {
                "source_ref": "source",
                "source_as_of_status": "current",
                "inferred_or_hypothesis": True,
            },
        ),
        (
            "conflicting",
            {
                "source_ref": "source",
                "source_as_of_status": "current",
                "inferred_or_hypothesis": False,
                "conflict_status": "conflicting",
            },
        ),
    )
    probes = tuple(
        S3GraphEdgeAdmissibilityProbe(
            probe_id=f"s3_graph_admissibility_probe_{condition}",
            condition=condition,
            accepted_as_evidence=False,
            rejection_code=classify_s3_graph_edge_admissibility(probe),
        )
        for condition, probe in probe_inputs
    )
    payload = {
        "graph_pack_contract_ref": S3_GRAPH_DECISION_CELL_PACK_CONTRACT_REF,
        "graph_owner_ref": S3_GRAPH_DECISION_CELL_OWNER_REF,
        "case_id": str(runtime_plan["case_id"]),
        "work_unit_id": str(runtime_plan["work_unit_id"]),
        "attempt_id": str(runtime_plan["attempt_id"]),
        "research_run_id": str(runtime_plan["research_run_id"]),
        "execution_profile_version_ref": str(
            runtime_plan["execution_profile_version_ref"]
        ),
        "decision_surface_contract_ref": str(
            runtime_plan["decision_surface_contract_ref"]
        ),
        "runtime_plan_version_ref": str(runtime_plan["runtime_plan_version_ref"]),
        "runtime_plan_digest": str(runtime_plan["runtime_plan_digest"]),
        "evidence_route_plan_version_ref": str(
            evidence_route_plan["evidence_route_plan_version_ref"]
        ),
        "evidence_route_plan_digest": str(
            evidence_route_plan["evidence_route_plan_digest"]
        ),
        "financial_pack_version_ref": str(financial_pack["financial_pack_version_ref"]),
        "financial_pack_digest": str(financial_pack["financial_pack_digest"]),
        "analysis_digest": analysis_digest,
        "projection_as_of": projection_as_of,
        "product_industry_inputs": product_inputs,
        "skill_contracts": skill_contracts,
        "graph_edges": tuple(row.model_dump(mode="json") for row in edges),
        "market_price_in_contexts": tuple(
            row.model_dump(mode="json") for row in market_contexts
        ),
        "risk_contexts": tuple(row.model_dump(mode="json") for row in risk_contexts),
        "decision_cells": tuple(row.model_dump(mode="json") for row in cells),
        "admissibility_probes": tuple(row.model_dump(mode="json") for row in probes),
        "existing_local_research_graph_read_count": 1,
        "additional_graph_read_count": 0,
        "model_calls": 0,
        "provider_calls": 0,
        "execution_network_calls": 0,
        "source_network_calls": 0,
        "external_tool_calls": 0,
        "live_business_writes": 0,
        "runtime_evidence_promotions": 0,
        "graph_edges_promoted_to_evidence": 0,
        "graph_allocated_financial_numbers": 0,
    }
    digest = canonical_digest(payload)
    pack_id = f"s3_graph_decision_cell_pack_{digest[:24]}"
    return S3BoundedGraphDecisionCellPackVersion(
        graph_pack_id=pack_id,
        graph_pack_version_ref=f"{pack_id}:v1",
        graph_pack_digest=digest,
        **payload,
    )


def consume_s3_bounded_graph_decision_cell_pack(
    pack: S3BoundedGraphDecisionCellPackVersion,
    *,
    runtime_plan: Mapping[str, Any],
    evidence_route_plan: Mapping[str, Any],
    financial_pack: Mapping[str, Any],
    analysis_preview: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    """Recompile the full T05 pack and fail closed on any lineage/boundary change."""

    expected = compile_s3_bounded_graph_decision_cell_pack(
        runtime_plan=runtime_plan,
        evidence_route_plan=evidence_route_plan,
        financial_pack=financial_pack,
        analysis_preview=analysis_preview,
    )
    if pack.model_dump(mode="json") != expected.model_dump(mode="json"):
        raise ValueError("s3_graph_decision_cell_pack_recompile_mismatch")
    if any(
        classify_s3_graph_edge_admissibility(
            {
                **edge.model_dump(mode="json"),
                "source_as_of_status": edge.source_as_of_status,
            }
        )
        != "graph_edge_inferred_hypothesis"
        for edge in pack.graph_edges
    ):
        raise ValueError("s3_graph_edge_direct_evidence_boundary_invalid")
    for model, id_field, digest_field, prefix in (
        *(
            (row, "edge_projection_id", "edge_projection_digest", "s3_graph_edge_projection_")
            for row in pack.graph_edges
        ),
        *(
            (row, "market_context_id", "market_context_digest", "s3_market_context_")
            for row in pack.market_price_in_contexts
        ),
        *(
            (row, "risk_context_id", "risk_context_digest", "s3_risk_context_")
            for row in pack.risk_contexts
        ),
        *(
            (row, "cell_projection_id", "cell_projection_digest", "s3_graph_decision_cell_")
            for row in pack.decision_cells
        ),
    ):
        digest = _s3_graph_model_digest(model, id_field, digest_field)
        if digest != getattr(model, digest_field) or getattr(model, id_field) != f"{prefix}{digest[:24]}":
            raise ValueError("s3_graph_projection_nested_digest_invalid")
    return tuple(
        {
            "program_cell_id": cell.program_cell_id,
            "cell_projection_id": cell.cell_projection_id,
            "graph_edge_projection_ref": cell.graph_edge_projection_ref,
            "market_context_ref": cell.market_context_ref,
            "risk_context_ref": cell.risk_context_ref,
            "accepted_evidence_refs": [],
            "consumption_mode": "deterministic_bounded_graph_projection_validation",
            "model_calls": 0,
            "network_calls": 0,
            "external_tool_calls": 0,
            "business_writes": 0,
        }
        for cell in pack.decision_cells
    )


def consume_s4_case_runtime_bounded_graph(
    binding: S4CaseRuntimeBinding,
) -> dict[str, Any]:
    """Inject context-only case Graph semantics into the existing Graph owner."""

    return consume_s4_case_runtime_binding(
        binding, "bounded_graph_pack"
    ).model_dump(mode="json")


def build_research_graph_store(
    repo_root: str | Path,
    *,
    generated_at: str | None = None,
    product_graph_nodes_path: str = DEFAULT_PRODUCT_GRAPH_NODES,
    product_graph_edges_path: str = DEFAULT_PRODUCT_GRAPH_EDGES,
    gold_mart_rows_path: str = DEFAULT_GOLD_MART_ROWS,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    generated_at = generated_at or _utc_now()
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}
    support_rows: list[dict[str, Any]] = []
    gold_support_map: dict[str, dict[str, Any]] = {}

    product_nodes = root / product_graph_nodes_path
    if product_nodes.exists():
        for row in _read_jsonl(product_nodes):
            node = _node_from_product_graph(row, generated_at=generated_at)
            nodes.setdefault(node["graph_node_id"], node)

    gold_path = root / gold_mart_rows_path
    if gold_path.exists():
        for row in _read_jsonl(gold_path):
            gold_support_map[row.get("gold_row_id", "")] = row
            evidence_ref = str(row.get("evidence_ref") or "")
            if evidence_ref:
                gold_support_map[evidence_ref] = row
            source_row_id = str(row.get("source_row_id") or "")
            if source_row_id:
                gold_support_map[source_row_id] = row
            for node in _nodes_from_gold_row(row, generated_at=generated_at):
                nodes.setdefault(node["graph_node_id"], node)
            edge = _edge_from_gold_row(row, generated_at=generated_at)
            edges.setdefault(edge["graph_edge_id"], edge)
            support_rows.append(_support_from_gold_row(edge["graph_edge_id"], row, generated_at=generated_at))

    product_edges = root / product_graph_edges_path
    if product_edges.exists():
        for row in _read_jsonl(product_edges):
            edge = _edge_from_product_graph(row, generated_at=generated_at)
            edges.setdefault(edge["graph_edge_id"], edge)
            for support in _supports_from_product_graph_edge(edge, row, gold_support_map, generated_at=generated_at):
                support_rows.append(support)

    summary = build_research_graph_summary(
        nodes=list(nodes.values()),
        edges=list(edges.values()),
        support_rows=support_rows,
        generated_at=generated_at,
    )
    return {
        "nodes": sorted(nodes.values(), key=lambda row: row["graph_node_id"]),
        "edges": sorted(edges.values(), key=lambda row: row["graph_edge_id"]),
        "support_rows": sorted(support_rows, key=lambda row: row["support_id"]),
        "summary": summary,
    }


def build_research_graph_summary(
    *,
    nodes: Sequence[Mapping[str, Any]],
    edges: Sequence[Mapping[str, Any]],
    support_rows: Sequence[Mapping[str, Any]],
    generated_at: str | None = None,
    sqlite_path: str = "",
    sqlite_node_count: int = 0,
    sqlite_edge_count: int = 0,
    sqlite_support_count: int = 0,
) -> dict[str, Any]:
    generated_at = generated_at or _utc_now()
    node_ids = {str(row.get("graph_node_id") or "") for row in nodes}
    dangling_edges = [
        row for row in edges if str(row.get("from_node_id") or "") not in node_ids or str(row.get("to_node_id") or "") not in node_ids
    ]
    support_counts_by_edge = Counter(str(row.get("graph_edge_id") or "") for row in support_rows)
    unsupported_edges = [row for row in edges if not support_counts_by_edge.get(str(row.get("graph_edge_id") or ""))]
    status = "pass"
    if dangling_edges or unsupported_edges:
        status = "action_required"
    if sqlite_node_count and sqlite_node_count != len(nodes):
        status = "action_required"
    if sqlite_edge_count and sqlite_edge_count != len(edges):
        status = "action_required"
    if sqlite_support_count and sqlite_support_count != len(support_rows):
        status = "action_required"
    return {
        "schema_version": RESEARCH_GRAPH_SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": status,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "evidence_support_row_count": len(support_rows),
        "dangling_edge_count": len(dangling_edges),
        "unsupported_edge_count": len(unsupported_edges),
        "sqlite_path": sqlite_path,
        "sqlite_node_count": sqlite_node_count,
        "sqlite_edge_count": sqlite_edge_count,
        "sqlite_support_count": sqlite_support_count,
        "node_type_counts": dict(Counter(str(row.get("node_type") or "") for row in nodes)),
        "edge_type_counts": dict(Counter(str(row.get("edge_type") or "") for row in edges).most_common(40)),
        "edge_authority_mode_counts": dict(Counter(str(row.get("authority_mode") or "") for row in edges)),
        "support_status_counts": dict(Counter(str(row.get("support_status") or "") for row in support_rows)),
        "unsupported_edge_samples": [_compact_edge(row) for row in unsupported_edges[:20]],
        "dangling_edge_samples": [_compact_edge(row) for row in dangling_edges[:20]],
        "policy": (
            "RD4 Research Graph Store merges product relationship graph edges with RD3 Gold Mart fact/signal edges. "
            "Every edge must have an evidence-support row. Source-evidence-only support rows remain bounded and do not "
            "create new authority."
        ),
    }


def write_research_graph_sqlite(
    sqlite_path: str | Path,
    *,
    nodes: Sequence[Mapping[str, Any]],
    edges: Sequence[Mapping[str, Any]],
    support_rows: Sequence[Mapping[str, Any]],
    replace: bool = True,
) -> dict[str, int]:
    target = Path(sqlite_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(target)) as conn:
        conn.execute(
            """
            create table if not exists research_graph_nodes (
                graph_node_id text primary key,
                schema_version text not null,
                generated_at text not null,
                node_type text not null,
                label text,
                ticker text,
                payload_json text,
                source text
            )
            """
        )
        conn.execute(
            """
            create table if not exists research_graph_edges (
                graph_edge_id text primary key,
                schema_version text not null,
                generated_at text not null,
                from_node_id text not null,
                to_node_id text not null,
                edge_type text not null,
                authority_mode text,
                can_enter_evidence_bundle integer,
                confidence real,
                source_layer text,
                source_role text,
                claim_boundary text,
                forbidden_claims_json text,
                evidence_refs_json text,
                gold_row_ids_json text,
                source_edge_id text
            )
            """
        )
        conn.execute(
            """
            create table if not exists research_graph_evidence_support (
                support_id text primary key,
                schema_version text not null,
                generated_at text not null,
                graph_edge_id text not null,
                gold_row_id text,
                source_row_id text,
                source_rowset_path text,
                evidence_ref text,
                citation_url text,
                citation_span text,
                authority_mode text,
                can_enter_evidence_bundle integer,
                support_status text
            )
            """
        )
        conn.execute("create table if not exists research_graph_metadata(key text primary key, value text not null)")
        if replace:
            conn.execute("delete from research_graph_nodes")
            conn.execute("delete from research_graph_edges")
            conn.execute("delete from research_graph_evidence_support")
        conn.executemany(
            """
            insert or replace into research_graph_nodes (
                graph_node_id, schema_version, generated_at, node_type, label, ticker, payload_json, source
            ) values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["graph_node_id"],
                    row["schema_version"],
                    row["generated_at"],
                    row["node_type"],
                    row.get("label", ""),
                    row.get("ticker", ""),
                    row.get("payload_json", "{}"),
                    row.get("source", ""),
                )
                for row in nodes
            ],
        )
        conn.executemany(
            """
            insert or replace into research_graph_edges (
                graph_edge_id, schema_version, generated_at, from_node_id, to_node_id, edge_type, authority_mode,
                can_enter_evidence_bundle, confidence, source_layer, source_role, claim_boundary,
                forbidden_claims_json, evidence_refs_json, gold_row_ids_json, source_edge_id
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["graph_edge_id"],
                    row["schema_version"],
                    row["generated_at"],
                    row["from_node_id"],
                    row["to_node_id"],
                    row["edge_type"],
                    row.get("authority_mode", ""),
                    1 if row.get("can_enter_evidence_bundle") else 0,
                    float(row.get("confidence") or 0.0),
                    row.get("source_layer", ""),
                    row.get("source_role", ""),
                    row.get("claim_boundary", ""),
                    row.get("forbidden_claims_json", "[]"),
                    row.get("evidence_refs_json", "[]"),
                    row.get("gold_row_ids_json", "[]"),
                    row.get("source_edge_id", ""),
                )
                for row in edges
            ],
        )
        conn.executemany(
            """
            insert or replace into research_graph_evidence_support (
                support_id, schema_version, generated_at, graph_edge_id, gold_row_id, source_row_id,
                source_rowset_path, evidence_ref, citation_url, citation_span, authority_mode,
                can_enter_evidence_bundle, support_status
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["support_id"],
                    row["schema_version"],
                    row["generated_at"],
                    row["graph_edge_id"],
                    row.get("gold_row_id", ""),
                    row.get("source_row_id", ""),
                    row.get("source_rowset_path", ""),
                    row.get("evidence_ref", ""),
                    row.get("citation_url", ""),
                    row.get("citation_span", ""),
                    row.get("authority_mode", ""),
                    1 if row.get("can_enter_evidence_bundle") else 0,
                    row.get("support_status", ""),
                )
                for row in support_rows
            ],
        )
        for table, column in (
            ("research_graph_nodes", "node_type"),
            ("research_graph_nodes", "ticker"),
            ("research_graph_edges", "edge_type"),
            ("research_graph_edges", "source_role"),
            ("research_graph_edges", "authority_mode"),
            ("research_graph_evidence_support", "graph_edge_id"),
            ("research_graph_evidence_support", "gold_row_id"),
        ):
            conn.execute(f"create index if not exists idx_{table}_{column} on {table}({column})")
        conn.execute(
            "insert or replace into research_graph_metadata(key, value) values (?, ?)",
            ("schema_version", RESEARCH_GRAPH_SQLITE_SCHEMA_VERSION),
        )
        conn.commit()
        return {
            "node_count": int(conn.execute("select count(*) from research_graph_nodes").fetchone()[0]),
            "edge_count": int(conn.execute("select count(*) from research_graph_edges").fetchone()[0]),
            "support_count": int(conn.execute("select count(*) from research_graph_evidence_support").fetchone()[0]),
        }


def render_research_graph_report(summary: Mapping[str, Any], *, output_paths: Mapping[str, str]) -> str:
    lines = [
        "# RD4 Research Graph Store v0.1",
        "",
        f"- Generated at: `{summary.get('generated_at', '')}`",
        f"- Status: `{summary.get('status', '')}`",
        f"- Nodes: `{summary.get('node_count', 0)}`",
        f"- Edges: `{summary.get('edge_count', 0)}`",
        f"- Evidence support rows: `{summary.get('evidence_support_row_count', 0)}`",
        f"- Dangling edges: `{summary.get('dangling_edge_count', 0)}`",
        f"- Unsupported edges: `{summary.get('unsupported_edge_count', 0)}`",
        "",
        "## Outputs",
        "",
    ]
    for key, path in output_paths.items():
        lines.append(f"- `{key}`: `{path}`")
    lines.extend(
        [
            "",
            "## Node Types",
            "",
            _markdown_counter_table(summary.get("node_type_counts") or {}, "Node type", "Count"),
            "",
            "## Edge Authority",
            "",
            _markdown_counter_table(summary.get("edge_authority_mode_counts") or {}, "Authority", "Edges"),
            "",
            "## Support Status",
            "",
            _markdown_counter_table(summary.get("support_status_counts") or {}, "Support", "Rows"),
            "",
            "## Boundary",
            "",
            "- RD4 不新增事实提权；图边 authority 继承 RD3 Gold Mart 或原 ProductRelationshipGraph 边界。",
            "- `source_evidence_ref_only` 表示原图边已有 evidence_ref 但未映射到 Gold Mart row，仍保持原 claim boundary。",
            "- Memo/ClaimCard 不能只因为图边存在就推断销量、ASP、份额、订单值、backlog 或实时资金流。",
            "",
        ]
    )
    return "\n".join(lines)


def write_jsonl(path: str | Path, rows: Sequence[Mapping[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("".join(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _node_from_product_graph(row: Mapping[str, Any], *, generated_at: str) -> dict[str, Any]:
    return {
        "schema_version": RESEARCH_GRAPH_NODE_SCHEMA_VERSION,
        "generated_at": generated_at,
        "graph_node_id": str(row.get("node_id") or ""),
        "node_type": str(row.get("node_type") or "unknown"),
        "label": str(row.get("label") or ""),
        "ticker": _ticker_from_node_id(str(row.get("node_id") or "")),
        "payload_json": json.dumps(row.get("payload") or {}, ensure_ascii=False, sort_keys=True),
        "source": "product_relationship_graph",
    }


def _nodes_from_gold_row(row: Mapping[str, Any], *, generated_at: str) -> list[dict[str, Any]]:
    ticker = str(row.get("ticker") or "").strip()
    nodes: list[dict[str, Any]] = []
    if ticker:
        nodes.append(_node(f"company:{ticker}", "company", str(row.get("company_name") or ticker), ticker=ticker, generated_at=generated_at, source="gold_fact_signal_mart"))
    else:
        nodes.append(
            _node(
                _unknown_issuer_node_id(row),
                "unknown_issuer",
                "Unknown issuer",
                generated_at=generated_at,
                source="gold_fact_signal_mart",
                payload={"gold_row_id": row.get("gold_row_id", ""), "fact_domain": row.get("fact_domain", "")},
            )
        )
    product_label = str(row.get("product_or_segment") or "").strip()
    product_family = str(row.get("product_family") or "").strip()
    if product_label:
        nodes.append(
            _node(
                _stable_node_id("product_context", ticker, product_family, product_label),
                "product_context",
                product_label,
                ticker=ticker,
                generated_at=generated_at,
                source="gold_fact_signal_mart",
                payload={"product_family": product_family},
            )
        )
    counterparty = str(row.get("counterparty") or "").strip()
    if counterparty:
        nodes.append(_node(_stable_node_id("counterparty", counterparty), "counterparty", counterparty, generated_at=generated_at, source="gold_fact_signal_mart"))
    fact_node_id = _fact_node_id(row)
    nodes.append(
        _node(
            fact_node_id,
            "fact_or_signal_type",
            str(row.get("fact_type") or row.get("fact_domain") or ""),
            ticker=ticker,
            generated_at=generated_at,
            source="gold_fact_signal_mart",
            payload={"fact_domain": row.get("fact_domain", ""), "support_surface": row.get("support_surface", "")},
        )
    )
    return nodes


def _edge_from_gold_row(row: Mapping[str, Any], *, generated_at: str) -> dict[str, Any]:
    ticker = str(row.get("ticker") or "").strip()
    from_node_id = f"company:{ticker}" if ticker else _unknown_issuer_node_id(row)
    to_node_id = _gold_target_node_id(row)
    edge_type = _edge_type_for_gold_row(row)
    evidence_ref = str(row.get("evidence_ref") or row.get("source_row_id") or row.get("gold_row_id") or "")
    return {
        "schema_version": RESEARCH_GRAPH_EDGE_SCHEMA_VERSION,
        "generated_at": generated_at,
        "graph_edge_id": _stable_id("rd4_gold_edge", row.get("gold_row_id"), from_node_id, to_node_id, edge_type),
        "from_node_id": from_node_id,
        "to_node_id": to_node_id,
        "edge_type": edge_type,
        "authority_mode": str(row.get("authority_mode") or ""),
        "can_enter_evidence_bundle": bool(row.get("can_enter_evidence_bundle")),
        "confidence": 1.0 if row.get("can_enter_evidence_bundle") else 0.0,
        "source_layer": str(row.get("source_layer") or ""),
        "source_role": str(row.get("source_role") or ""),
        "claim_boundary": str(row.get("claim_boundary") or ""),
        "forbidden_claims_json": str(row.get("forbidden_claims_json") or "[]"),
        "evidence_refs_json": json.dumps([evidence_ref] if evidence_ref else [], ensure_ascii=False),
        "gold_row_ids_json": json.dumps([row.get("gold_row_id")] if row.get("gold_row_id") else [], ensure_ascii=False),
        "source_edge_id": "",
    }


def _edge_from_product_graph(row: Mapping[str, Any], *, generated_at: str) -> dict[str, Any]:
    evidence_refs = [str(item) for item in row.get("evidence_refs") or [] if str(item).strip()]
    relationship_type = str(row.get("relationship_type") or "RELATIONSHIP_CONTEXT")
    lacks_direct_evidence = not evidence_refs and relationship_type not in STRUCTURAL_PRODUCT_GRAPH_EDGE_TYPES
    return {
        "schema_version": RESEARCH_GRAPH_EDGE_SCHEMA_VERSION,
        "generated_at": generated_at,
        "graph_edge_id": str(row.get("edge_id") or _stable_id("rd4_product_edge", row)),
        "from_node_id": str(row.get("from_node_id") or ""),
        "to_node_id": str(row.get("to_node_id") or ""),
        "edge_type": relationship_type,
        "authority_mode": "planning_or_gap_only" if lacks_direct_evidence else "bounded_thesis_driver_authority",
        "can_enter_evidence_bundle": False if lacks_direct_evidence else True,
        "confidence": 0.0 if lacks_direct_evidence else float(row.get("confidence") or 0.0),
        "source_layer": str(row.get("source_layer") or ""),
        "source_role": "product_relationship_graph",
        "claim_boundary": str(row.get("claim_boundary") or ""),
        "forbidden_claims_json": json.dumps(row.get("forbidden_claims") or [], ensure_ascii=False),
        "evidence_refs_json": json.dumps(evidence_refs, ensure_ascii=False),
        "gold_row_ids_json": "[]",
        "source_edge_id": str(row.get("edge_id") or ""),
    }


def _support_from_gold_row(graph_edge_id: str, row: Mapping[str, Any], *, generated_at: str) -> dict[str, Any]:
    return {
        "schema_version": RESEARCH_GRAPH_EVIDENCE_SUPPORT_SCHEMA_VERSION,
        "generated_at": generated_at,
        "support_id": _stable_id("rd4_support", graph_edge_id, row.get("gold_row_id")),
        "graph_edge_id": graph_edge_id,
        "gold_row_id": str(row.get("gold_row_id") or ""),
        "source_row_id": str(row.get("source_row_id") or ""),
        "source_rowset_path": str(row.get("source_rowset_path") or ""),
        "evidence_ref": str(row.get("evidence_ref") or ""),
        "citation_url": str(row.get("citation_url") or ""),
        "citation_span": str(row.get("citation_span") or ""),
        "authority_mode": str(row.get("authority_mode") or ""),
        "can_enter_evidence_bundle": bool(row.get("can_enter_evidence_bundle")),
        "support_status": "gold_mart_row",
    }


def _supports_from_product_graph_edge(
    edge: Mapping[str, Any],
    row: Mapping[str, Any],
    gold_support_map: Mapping[str, Mapping[str, Any]],
    *,
    generated_at: str,
) -> list[dict[str, Any]]:
    evidence_refs = [str(item) for item in row.get("evidence_refs") or [] if str(item).strip()]
    if not evidence_refs:
        edge_type = str(edge.get("edge_type") or "")
        support_status = (
            "structural_graph_topology_no_external_ref"
            if edge_type in STRUCTURAL_PRODUCT_GRAPH_EDGE_TYPES
            else "modelled_relationship_without_direct_evidence_ref"
        )
        return [
            {
                "schema_version": RESEARCH_GRAPH_EVIDENCE_SUPPORT_SCHEMA_VERSION,
                "generated_at": generated_at,
                "support_id": _stable_id("rd4_support", edge.get("graph_edge_id"), "missing_evidence_ref"),
                "graph_edge_id": str(edge.get("graph_edge_id") or ""),
                "gold_row_id": "",
                "source_row_id": "",
                "source_rowset_path": "",
                "evidence_ref": "",
                "citation_url": "",
                "citation_span": "",
                "authority_mode": str(edge.get("authority_mode") or ""),
                "can_enter_evidence_bundle": bool(edge.get("can_enter_evidence_bundle")),
                "support_status": support_status,
            }
        ]
    supports: list[dict[str, Any]] = []
    for evidence_ref in evidence_refs:
        gold = gold_support_map.get(evidence_ref)
        if gold:
            supports.append(_support_from_gold_row(str(edge.get("graph_edge_id") or ""), gold, generated_at=generated_at))
        else:
            supports.append(
                {
                    "schema_version": RESEARCH_GRAPH_EVIDENCE_SUPPORT_SCHEMA_VERSION,
                    "generated_at": generated_at,
                    "support_id": _stable_id("rd4_support", edge.get("graph_edge_id"), evidence_ref),
                    "graph_edge_id": str(edge.get("graph_edge_id") or ""),
                    "gold_row_id": "",
                    "source_row_id": evidence_ref,
                    "source_rowset_path": "",
                    "evidence_ref": evidence_ref,
                    "citation_url": "",
                    "citation_span": "",
                    "authority_mode": str(edge.get("authority_mode") or ""),
                    "can_enter_evidence_bundle": bool(edge.get("can_enter_evidence_bundle")),
                    "support_status": "source_evidence_ref_only",
                }
            )
    return supports


def _node(
    node_id: str,
    node_type: str,
    label: str,
    *,
    generated_at: str,
    ticker: str = "",
    source: str,
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": RESEARCH_GRAPH_NODE_SCHEMA_VERSION,
        "generated_at": generated_at,
        "graph_node_id": node_id,
        "node_type": node_type,
        "label": label,
        "ticker": ticker,
        "payload_json": json.dumps(dict(payload or {}), ensure_ascii=False, sort_keys=True),
        "source": source,
    }


def _gold_target_node_id(row: Mapping[str, Any]) -> str:
    counterparty = str(row.get("counterparty") or "").strip()
    if counterparty:
        return _stable_node_id("counterparty", counterparty)
    product_label = str(row.get("product_or_segment") or "").strip()
    if product_label:
        return _stable_node_id("product_context", row.get("ticker", ""), row.get("product_family", ""), product_label)
    return _fact_node_id(row)


def _fact_node_id(row: Mapping[str, Any]) -> str:
    return _stable_node_id("fact_type", row.get("fact_domain", ""), row.get("fact_type", ""), row.get("metric_family", ""), row.get("metric_name", ""))


def _unknown_issuer_node_id(row: Mapping[str, Any]) -> str:
    return _stable_node_id("unknown_issuer", row.get("gold_row_id", ""))


def _edge_type_for_gold_row(row: Mapping[str, Any]) -> str:
    domain = str(row.get("fact_domain") or "")
    return {
        "financial_statement_fact": "HAS_FINANCIAL_STATEMENT_FACT",
        "product_kpi_fact": "HAS_PRODUCT_KPI_FACT",
        "product_profile_or_spec_fact": "HAS_PRODUCT_PROFILE_OR_SPEC",
        "industry_operating_metric_fact": "HAS_INDUSTRY_OPERATING_METRIC",
        "customer_deployment_or_order_signal": "HAS_CUSTOMER_DEPLOYMENT_OR_ORDER_SIGNAL",
        "capital_funding_ownership_fact": "HAS_CAPITAL_FUNDING_OWNERSHIP_FACT",
        "market_liquidity_signal": "HAS_MARKET_LIQUIDITY_SIGNAL",
        "macro_industry_driver_signal": "HAS_MACRO_INDUSTRY_DRIVER_SIGNAL",
        "regulated_or_official_api_signal": "HAS_REGULATED_OR_OFFICIAL_API_SIGNAL",
        "source_authority": "HAS_SOURCE_AUTHORITY_ROW",
    }.get(domain, "HAS_BOUNDED_CONTEXT_SIGNAL")


def _read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, Mapping):
                yield dict(payload)


def _ticker_from_node_id(node_id: str) -> str:
    if node_id.startswith("company:"):
        return node_id.split(":", 1)[1]
    return ""


def _stable_node_id(prefix: str, *parts: Any) -> str:
    cleaned = [str(part or "").strip().lower() for part in parts if str(part or "").strip()]
    label = ":".join(cleaned)
    return f"{prefix}:{_stable_id(prefix, label)}"


def _stable_id(*parts: Any) -> str:
    raw = "\x1f".join(str(part or "") for part in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:24]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _compact_edge(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "graph_edge_id": row.get("graph_edge_id", ""),
        "from_node_id": row.get("from_node_id", ""),
        "to_node_id": row.get("to_node_id", ""),
        "edge_type": row.get("edge_type", ""),
    }


def _markdown_counter_table(counter: Mapping[str, Any], key_label: str, value_label: str) -> str:
    lines = [f"| {key_label} | {value_label} |", "| --- | ---: |"]
    for key, value in sorted(counter.items(), key=lambda item: str(item[0])):
        lines.append(f"| `{key}` | `{value}` |")
    return "\n".join(lines)
