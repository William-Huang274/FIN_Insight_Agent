from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from sec_agent.canonical_runtime.shadow_calibration import (
    FiveChainDefinition,
    FiveChainPolicy,
    MultiSectorCalibrationMatrix,
    MultiSectorCalibrationPolicy,
    NegativeControl,
    NegativeControlVerifier,
    P36FiveChainEvaluator,
    PatternCandidate,
    PatternCandidateAdjudicator,
    SectorCalibrationCase,
)
from sec_agent.canonical_runtime.shadow_comparison import (
    CellAuditPolicy,
    CellCoverageGranularityAuditor,
    ComparatorPolicy,
    LegacyRequiredItem,
    LegacyRequiredItemComparator,
    SemanticMappingRow,
    ShadowCell,
)
from sec_agent.canonical_runtime.shadow_review import ReviewerAction, ShadowComparisonReviewService


DEFAULT_OUTPUT_DIR = ROOT / "data/manifests"
CASE_ID = "ai_semis_dell_nvda_anchor_v0_1"
POINTS = tuple(f"M3.{number}" for number in range(1, 8))


def _cells() -> tuple[ShadowCell, ...]:
    rows = (
        ("accelerator_economics", "accelerator", "reported_accelerator_economics"),
        ("server_oem_capture", "server_oem", "reported_server_margin"),
        ("foundry_packaging_capture", "foundry_packaging", "reported_foundry_economics"),
        ("hbm_bottleneck_capture", "hbm", "reported_hbm_economics"),
        ("semicap_readthrough", "semicap", "reported_semicap_economics"),
        ("cross_chain_price_in", "price_in", "valuation_price_in"),
        ("capex_sustainability", "capex", "hyperscaler_capex"),
        ("supply_chain_constraints", "supply_chain", "supply_chain_constraint"),
        ("counter_thesis", "risk", "counterevidence"),
        ("valuation_risk", "valuation", "valuation_risk"),
    )
    return tuple(
        ShadowCell(
            cell_key=key,
            decision_question=f"Can the {semantic_key} mechanism sustain expected value capture?",
            materiality="high",
            owner_role="fundamental_analyst",
            evidence_roles=(role,),
            source_policy_refs=("official_issuer_primary",),
            semantic_key=semantic_key,
            what_would_change=(f"falsifier_for_{key}",),
            counterevidence_owner_role="risk_counterevidence_analyst",
        )
        for key, semantic_key, role in rows
    )


def _legacy_items() -> tuple[LegacyRequiredItem, ...]:
    return (
        LegacyRequiredItem(required_item_id="accelerator_revenue", semantic_intent="accelerator economics", materiality="high"),
        LegacyRequiredItem(required_item_id="accelerator_margin", semantic_intent="accelerator margin", materiality="high"),
        LegacyRequiredItem(required_item_id="server_capture", semantic_intent="server value capture", materiality="high"),
        LegacyRequiredItem(required_item_id="foundry_capture", semantic_intent="foundry capture", materiality="high"),
        LegacyRequiredItem(required_item_id="hbm_capture", semantic_intent="HBM capture", materiality="high"),
        LegacyRequiredItem(required_item_id="semicap_lag", semantic_intent="semicap lag", materiality="medium"),
        LegacyRequiredItem(required_item_id="price_in", semantic_intent="price in", materiality="high"),
        LegacyRequiredItem(required_item_id="capex", semantic_intent="capex", materiality="high"),
        LegacyRequiredItem(required_item_id="exact_metric_lookup", semantic_intent="exact metric lookup", materiality="low", item_kind="fact_lookup"),
    )


def _mappings() -> tuple[SemanticMappingRow, ...]:
    values = (
        ("accelerator_revenue", "merge", ("accelerator_economics",), "revenue and margin are one value-capture decision"),
        ("accelerator_margin", "merge", ("accelerator_economics",), "revenue and margin are one value-capture decision"),
        ("server_capture", "split", ("server_oem_capture", "supply_chain_constraints"), "server economics and supply constraints require separate cells"),
        ("foundry_capture", "merge", ("foundry_packaging_capture",), "canonical foundry economics cell"),
        ("hbm_capture", "merge", ("hbm_bottleneck_capture",), "canonical HBM economics cell"),
        ("semicap_lag", "merge", ("semicap_readthrough",), "canonical semicap read-through cell"),
        ("price_in", "merge", ("cross_chain_price_in",), "price-in has a dedicated cross-chain cell"),
        ("capex", "merge", ("capex_sustainability",), "capex has a dedicated decision cell"),
    )
    regular = tuple(
        SemanticMappingRow(
            legacy_required_item_id=item_id,
            mapping_kind=kind,
            target_cell_keys=targets,
            information_loss_tags=("legacy_semantics_normalized",),
            rationale=rationale,
        )
        for item_id, kind, targets, rationale in values
    )
    return regular + (
        SemanticMappingRow(
            legacy_required_item_id="exact_metric_lookup",
            mapping_kind="downgrade",
            information_loss_tags=("fact_lookup_to_slot",),
            rationale="facts are EvidenceSlots rather than DecisionCells",
            downgrade_reason="exact issuer fact remains in slot policy",
        ),
    )


def build_results() -> dict[str, Any]:
    cells = _cells()
    comparison = LegacyRequiredItemComparator(ComparatorPolicy(policy_ref="point01_m3_1_semantic_comparison_policy_v1_0")).compare(
        case_id=CASE_ID, legacy_items=_legacy_items(), shadow_cells=cells, mappings=_mappings()
    )
    audit = CellCoverageGranularityAuditor(CellAuditPolicy(policy_ref="point01_m3_2_cell_audit_policy_v1_0")).audit(
        case_id=CASE_ID, cells=cells, comparison=comparison
    )
    chains = tuple(
        FiveChainDefinition(chain_id=chain, required_cell_keys=(cell_key,), required_evidence_roles=(role,))
        for chain, cell_key, role in (
            ("accelerator", "accelerator_economics", "reported_accelerator_economics"),
            ("server_oem", "server_oem_capture", "reported_server_margin"),
            ("foundry_packaging", "foundry_packaging_capture", "reported_foundry_economics"),
            ("hbm", "hbm_bottleneck_capture", "reported_hbm_economics"),
            ("semicap", "semicap_readthrough", "reported_semicap_economics"),
        )
    )
    five_chain = P36FiveChainEvaluator(FiveChainPolicy(policy_ref="point01_m3_3_p36_five_chain_policy_v1_0")).evaluate(
        case_id=CASE_ID, chains=chains, cells=cells, audit=audit, material_omission_ids=comparison.material_omission_ids
    )
    sector_cases = tuple(
        SectorCalibrationCase(
            case_id=case_id,
            sector=sector,
            report_type=report_type,
            expected_mechanism_keys=(mechanism,),
            observed_mechanism_keys=(mechanism,),
            ontology_ref=f"{sector}_ontology_v1",
            source_policy_delta_refs=(f"{sector}_source_policy_delta_v1",),
            status="pass",
        )
        for case_id, sector, report_type, mechanism in (
            (CASE_ID, "ai_semis", "initiation", "supply_chain_capex"),
            ("v3_software_cloud_developer_products_financial_product_bridge_001", "saas", "event_update", "adoption_to_financial_capture"),
            ("v4_pharma_biotech_medtech_financial_product_bridge_001", "healthcare", "initiation", "regulatory_milestone"),
            ("v6_banks_financials_capital_markets_financial_product_bridge_001", "banks", "valuation_price_in", "balance_sheet_credit"),
        )
    )
    matrix = MultiSectorCalibrationMatrix(MultiSectorCalibrationPolicy(policy_ref="point01_m3_4_multi_sector_policy_v1_0")).evaluate(cases=sector_cases)
    negative = NegativeControlVerifier().verify(
        controls=(
            NegativeControl(control_id="negative_relationship_graph_not_financial_fact_v0_1", family="relationship", attempted_promotion="primary_financial_fact", typed_gap_type="relationship_scope_only", actual_status="rejected", actual_reason="relationship_graph_is_bounded_context_only"),
            NegativeControl(control_id="negative_parser_gap_not_public_source_absent_v0_1", family="parser", attempted_promotion="public_source_absent", typed_gap_type="parser_gap", actual_status="rejected", actual_reason="parser_availability_is_not_source_absence"),
            NegativeControl(control_id="negative_commercial_tracker_boundary_v0_1", family="commercial", attempted_promotion="public_proxy_substitution", typed_gap_type="commercial_data_gap", actual_status="rejected", actual_reason="commercial_metric_cannot_be_silently_replaced"),
        )
    )
    candidates = PatternCandidateAdjudicator().adjudicate(
        candidates=(
            PatternCandidate(candidate_id="wb_prompt_structure_rejected", source_case_id="WB-S01", source_family="workbuddy", provenance="prompt_required", proposed_disposition="sector_candidate", candidate_summary="prompt-required report structure", evidence_refs=("data/manifests/workbuddy_semantic_trajectory_reaudit_v0_1.json",), reviewer_action="accept"),
            PatternCandidate(candidate_id="wb_saas_adoption_mechanism_candidate", source_case_id="WB-S01", source_family="workbuddy", provenance="independently_observed", proposed_disposition="sector_candidate", candidate_summary="SaaS adoption-to-financial-capture mechanism", evidence_refs=("data/manifests/workbuddy_semantic_trajectory_reaudit_v0_1.json",), independent_corroboration_refs=("configs/engineering_handoff/point01_m2_4_pack_selection_policy_v1_0.json", "point01_m3_saas_rubric_v1"), reviewer_action="accept"),
            PatternCandidate(candidate_id="reviewer_inferred_rejected", source_case_id="WB-S02", source_family="workbuddy", provenance="reviewer_inferred", proposed_disposition="universal_candidate", candidate_summary="unproven reviewer inference", evidence_refs=("reviewer_note",), reviewer_action="accept"),
        )
    )
    review = ShadowComparisonReviewService().build_surface(
        case_id=CASE_ID,
        query_ref="p36_ai_infrastructure_query_v1",
        contract_version_id="contract_p36_ai_infrastructure:v1",
        cells=cells,
        comparison=comparison,
        audit=audit,
        adjudication=candidates,
        actions=(
            ReviewerAction(action_id="fixture_needs_source", action="needs_source", actor_type="fixture_reviewer", reason="exercise review lifecycle", affected_cell_keys=("accelerator_economics",)),
            ReviewerAction(action_id="fixture_supersede", action="supersede", actor_type="fixture_reviewer", reason="slot policy boundary recorded", affected_cell_keys=("accelerator_economics",), supersedes_action_id="fixture_needs_source"),
        ),
    )
    return {
        "M3.1": comparison.model_dump(mode="json"),
        "M3.2": audit.model_dump(mode="json"),
        "M3.3": five_chain.model_dump(mode="json"),
        "M3.4": matrix.model_dump(mode="json"),
        "M3.5": negative.model_dump(mode="json"),
        "M3.6": candidates.model_dump(mode="json"),
        "M3.7": review.model_dump(mode="json"),
    }


def _result_document(point_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    status = str(payload.get("status") or "fail")
    return {
        "result_version": f"finsight_point01_{point_id.lower().replace('.', '_')}_fixture_result_v1_0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "point_id": point_id,
        "status": "pass" if status == "pass" else "fail_closed",
        "fixture_status": status,
        "payload": payload,
        "planning_authority": "legacy",
        "canonical_lane": "shadow_only",
        "model_call_count": 0,
        "external_call_count": 0,
        "boundary": "Deterministic M3 calibration fixture only; no model, provider, retrieval, Evidence/Writer runtime, legacy write, or authority cutover was invoked.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic Point 01 M3.1-M3.7 calibration fixtures.")
    parser.add_argument("--point", choices=("all", *POINTS), default="all")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    output_dir = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir
    outputs = build_results()
    selected = outputs if args.point == "all" else {args.point: outputs[args.point]}
    output_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, str] = {}
    for point_id, payload in selected.items():
        path = output_dir / f"point01_{point_id.lower().replace('.', '_')}_fixture_result_v1_0.json"
        path.write_text(json.dumps(_result_document(point_id, payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written[point_id] = str(path)
    aggregate = {
        "result_version": "finsight_point01_m3_calibration_fixture_result_v1_0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "pass" if all(str(payload.get("status")) == "pass" for payload in selected.values()) else "fail_closed",
        "point_statuses": {point_id: payload.get("status") for point_id, payload in selected.items()},
        "outputs": written,
        "planning_authority": "legacy",
        "canonical_lane": "shadow_only",
        "model_call_count": 0,
        "external_call_count": 0,
    }
    aggregate_path = output_dir / "point01_m3_calibration_fixture_result_v1_0.json"
    aggregate_path.write_text(json.dumps(aggregate, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": aggregate["status"], "output": str(aggregate_path), "point_statuses": aggregate["point_statuses"]}, ensure_ascii=False))
    return 0 if aggregate["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
