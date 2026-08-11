from __future__ import annotations

import pytest

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


pytestmark = pytest.mark.fast_contract


CASE_ID = "ai_semis_dell_nvda_anchor_v0_1"


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
        LegacyRequiredItem(
            required_item_id="exact_metric_lookup",
            semantic_intent="exact metric lookup",
            materiality="low",
            item_kind="fact_lookup",
        ),
    )


def _mappings() -> tuple[SemanticMappingRow, ...]:
    return (
        SemanticMappingRow(legacy_required_item_id="accelerator_revenue", mapping_kind="merge", target_cell_keys=("accelerator_economics",), information_loss_tags=("legacy_granularity_merged",), rationale="revenue and margin are one value-capture decision"),
        SemanticMappingRow(legacy_required_item_id="accelerator_margin", mapping_kind="merge", target_cell_keys=("accelerator_economics",), information_loss_tags=("legacy_granularity_merged",), rationale="revenue and margin are one value-capture decision"),
        SemanticMappingRow(legacy_required_item_id="server_capture", mapping_kind="split", target_cell_keys=("server_oem_capture", "supply_chain_constraints"), information_loss_tags=("legacy_scope_split",), rationale="server economics and supply constraints require separate cells"),
        SemanticMappingRow(legacy_required_item_id="foundry_capture", mapping_kind="merge", target_cell_keys=("foundry_packaging_capture",), information_loss_tags=("legacy_label_normalized",), rationale="canonical foundry economics cell"),
        SemanticMappingRow(legacy_required_item_id="hbm_capture", mapping_kind="merge", target_cell_keys=("hbm_bottleneck_capture",), information_loss_tags=("legacy_label_normalized",), rationale="canonical HBM economics cell"),
        SemanticMappingRow(legacy_required_item_id="semicap_lag", mapping_kind="merge", target_cell_keys=("semicap_readthrough",), information_loss_tags=("legacy_label_normalized",), rationale="canonical semicap read-through cell"),
        SemanticMappingRow(legacy_required_item_id="price_in", mapping_kind="merge", target_cell_keys=("cross_chain_price_in",), information_loss_tags=("legacy_label_normalized",), rationale="price-in has a dedicated cross-chain cell"),
        SemanticMappingRow(legacy_required_item_id="capex", mapping_kind="merge", target_cell_keys=("capex_sustainability",), information_loss_tags=("legacy_label_normalized",), rationale="capex has a dedicated decision cell"),
        SemanticMappingRow(legacy_required_item_id="exact_metric_lookup", mapping_kind="downgrade", information_loss_tags=("fact_lookup_to_slot",), rationale="facts are evidence slots, not cells", downgrade_reason="exact issuer fact remains in evidence policy"),
    )


def _comparison():
    return LegacyRequiredItemComparator(ComparatorPolicy(policy_ref="m3_compare_v1")).compare(
        case_id=CASE_ID, legacy_items=_legacy_items(), shadow_cells=_cells(), mappings=_mappings()
    )


def _audit():
    return CellCoverageGranularityAuditor(CellAuditPolicy(policy_ref="m3_cell_audit_v1")).audit(
        case_id=CASE_ID, cells=_cells(), comparison=_comparison()
    )


def test_m3_1_semantic_comparator_uses_merge_split_and_downgrade_not_count_parity() -> None:
    report = _comparison()
    assert report.status == "pass"
    assert report.material_omission_ids == ()
    assert {row.mapping_kind for row in report.rows} == {"merge", "split", "downgrade"}
    assert "counter_thesis" in report.extra_shadow_cell_keys


def test_m3_1_rejects_decision_item_downgrade() -> None:
    bad = list(_mappings())
    bad[0] = SemanticMappingRow(
        legacy_required_item_id="accelerator_revenue",
        mapping_kind="downgrade",
        information_loss_tags=("invalid",),
        rationale="bad",
        downgrade_reason="bad",
    )
    report = LegacyRequiredItemComparator(ComparatorPolicy(policy_ref="m3_compare_v1")).compare(
        case_id=CASE_ID, legacy_items=_legacy_items(), shadow_cells=_cells(), mappings=tuple(bad)
    )
    assert report.status == "fail"
    assert "accelerator_revenue" in report.material_omission_ids


def test_m3_2_cell_audit_accepts_material_decision_cells() -> None:
    audit = _audit()
    assert audit.status == "pass"
    assert audit.materiality_weighted_coverage == 1.0


def test_m3_2_cell_audit_catches_ownerless_lookup_duplicate_and_unanswerable_cells() -> None:
    bad = list(_cells())
    bad[1] = bad[1].model_copy(
        update={
            "owner_role": None,
            "question_kind": "fact_lookup",
            "semantic_key": bad[0].semantic_key,
            "evidence_roles": (),
        }
    )
    audit = CellCoverageGranularityAuditor(CellAuditPolicy(policy_ref="m3_cell_audit_v1")).audit(
        case_id=CASE_ID, cells=tuple(bad), comparison=_comparison()
    )
    assert audit.status == "fail"
    assert bad[1].cell_key in audit.ownerless_cell_keys
    assert bad[1].cell_key in audit.lookup_cell_keys
    assert bad[1].cell_key in audit.duplicate_cell_keys
    assert bad[1].cell_key in audit.unanswerable_cell_keys


def test_m3_3_p36_five_chain_evaluator_has_failure_attribution() -> None:
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
    report = P36FiveChainEvaluator(FiveChainPolicy(policy_ref="m3_p36_v1")).evaluate(
        case_id=CASE_ID, chains=chains, cells=_cells(), audit=_audit(), material_omission_ids=_comparison().material_omission_ids
    )
    assert report.status == "pass"
    broken = P36FiveChainEvaluator(FiveChainPolicy(policy_ref="m3_p36_v1")).evaluate(
        case_id=CASE_ID,
        chains=(chains[0].model_copy(update={"required_cell_keys": ("missing_cell",)}),),
        cells=_cells(),
        audit=_audit(),
    )
    assert broken.status == "fail"
    assert broken.findings[0].failure_attribution == ("cell_coverage", "evidence_slot_coverage")


def test_m3_4_multi_sector_matrix_requires_all_four_mechanisms_and_policy_deltas() -> None:
    cases = tuple(
        SectorCalibrationCase(
            case_id=case_id,
            sector=sector,
            report_type=report_type,
            expected_mechanism_keys=(mechanism,),
            observed_mechanism_keys=(mechanism,),
            ontology_ref=f"{sector}_ontology_v1",
            source_policy_delta_refs=(f"{sector}_source_policy_v1",),
            status="pass",
        )
        for case_id, sector, report_type, mechanism in (
            (CASE_ID, "ai_semis", "initiation", "supply_chain_capex"),
            ("v3_software_cloud_developer_products_financial_product_bridge_001", "saas", "event_update", "adoption_to_financial_capture"),
            ("v4_pharma_biotech_medtech_financial_product_bridge_001", "healthcare", "initiation", "regulatory_milestone"),
            ("v6_banks_financials_capital_markets_financial_product_bridge_001", "banks", "valuation_price_in", "balance_sheet_credit"),
        )
    )
    report = MultiSectorCalibrationMatrix(MultiSectorCalibrationPolicy(policy_ref="m3_matrix_v1")).evaluate(cases=cases)
    assert report.status == "pass"
    missing_delta = cases[1].model_copy(update={"source_policy_delta_refs": ()})
    assert MultiSectorCalibrationMatrix(MultiSectorCalibrationPolicy(policy_ref="m3_matrix_v1")).evaluate(cases=(cases[0], missing_delta, cases[2], cases[3])).status == "fail"


def test_m3_5_negative_controls_fail_closed_without_material_escape() -> None:
    controls = (
        NegativeControl(control_id="relationship", family="relationship", attempted_promotion="primary_financial_fact", typed_gap_type="relationship_scope_only", actual_status="rejected", actual_reason="relationship_graph_scope_only"),
        NegativeControl(control_id="parser", family="parser", attempted_promotion="public_source_absent", typed_gap_type="parser_gap", actual_status="rejected", actual_reason="parser_availability_not_source_absence"),
        NegativeControl(control_id="commercial", family="commercial", attempted_promotion="public_proxy_substitution", typed_gap_type="commercial_data_gap", actual_status="rejected", actual_reason="commercial_metric_cannot_use_proxy"),
    )
    report = NegativeControlVerifier().verify(controls=controls)
    assert report.status == "pass"
    escaped = controls[0].model_copy(update={"actual_status": "accepted"})
    assert NegativeControlVerifier().verify(controls=(escaped, controls[1], controls[2])).material_escape_count == 1


def test_m3_6_provenance_blocks_prompt_required_and_allows_independently_corroborated_candidate() -> None:
    candidates = (
        PatternCandidate(candidate_id="wb_prompt_structure", source_case_id="WB-S01", source_family="workbuddy", provenance="prompt_required", proposed_disposition="sector_candidate", candidate_summary="prompt-imposed format", evidence_refs=("workbuddy_manifest",), reviewer_action="accept"),
        PatternCandidate(candidate_id="wb_saas_mechanism", source_case_id="WB-S01", source_family="workbuddy", provenance="independently_observed", proposed_disposition="sector_candidate", candidate_summary="adoption-to-financial-capture mechanism", evidence_refs=("workbuddy_manifest",), independent_corroboration_refs=("m3_saas_rubric_v1", "m2_4_pack_selection_fixture"), reviewer_action="accept"),
        PatternCandidate(candidate_id="reviewer_guess", source_case_id="WB-S02", source_family="workbuddy", provenance="reviewer_inferred", proposed_disposition="universal_candidate", candidate_summary="unproven guess", evidence_refs=("reviewer_note",), reviewer_action="accept"),
    )
    report = PatternCandidateAdjudicator().adjudicate(candidates=candidates)
    assert report.status == "pass"
    assert report.promotable_candidate_ids == ("wb_saas_mechanism",)
    assert report.direct_workbuddy_pack_promotion_count == 0


def test_m3_7_review_surface_traces_query_contract_cell_slot_and_supersession() -> None:
    adjudication = PatternCandidateAdjudicator().adjudicate(
        candidates=(
            PatternCandidate(candidate_id="fin_candidate", source_case_id=CASE_ID, source_family="fin_native", provenance="independently_observed", proposed_disposition="case_only", candidate_summary="risk matrix", evidence_refs=("p36_rubric",), reviewer_action="accept"),
        )
    )
    surface = ShadowComparisonReviewService().build_surface(
        case_id=CASE_ID,
        query_ref="query_p36_ai_infrastructure",
        contract_version_id="contract_p36:v1",
        cells=_cells(),
        comparison=_comparison(),
        audit=_audit(),
        adjudication=adjudication,
        actions=(
            ReviewerAction(action_id="action_needs_source", action="needs_source", actor_type="fixture_reviewer", reason="verify source policy", affected_cell_keys=("accelerator_economics",)),
            ReviewerAction(action_id="action_supersede", action="supersede", actor_type="fixture_reviewer", reason="source policy now typed", affected_cell_keys=("accelerator_economics",), supersedes_action_id="action_needs_source"),
        ),
    )
    assert surface.status == "pass"
    assert len(surface.traces) == 10
    assert surface.unresolved_action_ids == ()
