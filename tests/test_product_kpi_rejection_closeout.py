from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "data_expansion" / "audit_product_kpi_rejection_repair_closeout.py"
SPEC = importlib.util.spec_from_file_location("audit_product_kpi_rejection_repair_closeout", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_classifies_already_covered_as_non_gap() -> None:
    decision = MODULE.classify_rejection({"rejection_reason": "claim_already_covered_by_baseline", "ticker": "CAT"}, {})
    assert decision["action_class"] == "already_covered_not_gap"
    assert decision["target_phase"] == "closeout_only"


def test_classifies_wbd_subscriber_unit_correction_candidate() -> None:
    decision = MODULE.classify_rejection(
        {"rejection_reason": "not_product_revenue", "ticker": "WBD"},
        {"metric_family": "subscribers_or_arpu", "unit": "USD"},
    )
    assert decision["action_class"] == "operating_metric_candidate"
    assert decision["closeout_reason"] == "subscriber_table_unit_correction_candidate"


def test_classifies_ed_gas_delivered_as_subrow_candidate() -> None:
    decision = MODULE.classify_rejection(
        {"rejection_reason": "not_product_revenue", "ticker": "ED"},
        {"metric_family": "unit_sales_or_deliveries", "unit": "systems"},
    )
    assert decision["target_phase"] == "operating_metric_repair"
    assert decision["closeout_reason"] == "gas_delivered_row_subrow_ambiguity_candidate"


def test_classifies_currency_sentence_as_local_verifier_candidate() -> None:
    decision = MODULE.classify_rejection(
        {"rejection_reason": "not_structured_table_metric", "ticker": "MU"},
        {
            "metric_family": "product_revenue",
            "unit": "USD",
            "source_id": "company_product_kpi_facts_structured_sentence_metric_parser",
        },
    )
    assert decision["action_class"] == "sentence_verifier_candidate"
    assert decision["target_phase"] == "sentence_local_verifier"


def test_classifies_gpc_as_versioned_schema_required() -> None:
    decision = MODULE.classify_rejection(
        {"rejection_reason": "missing_strong_revenue_table_context", "ticker": "GPC"},
        {"metric_family": "product_revenue", "unit": "USD"},
    )
    assert decision["action_class"] == "versioned_schema_required"
    assert decision["closeout_reason"] == "public_disclosure_restatement_conflict_requires_versioned_schema"


def test_classifies_tsn_truncated_segment_context_as_not_promotable() -> None:
    decision = MODULE.classify_rejection(
        {"rejection_reason": "forbidden_financial_statement_context", "ticker": "TSN"},
        {"metric_family": "product_revenue", "unit": "USD", "row_label": "Chicken"},
    )

    assert decision["action_class"] == "not_promotable_public_disclosure_cell"
    assert decision["closeout_reason"] == "truncated_segment_table_context_not_locally_verifiable"


def test_classifies_es_residual_wholesale_transmission_as_already_covered() -> None:
    decision = MODULE.classify_rejection(
        {"rejection_reason": "missing_strong_revenue_table_context", "ticker": "ES"},
        {
            "metric_family": "product_revenue",
            "unit": "USD",
            "product_or_segment": "Transmission",
            "row_label": "Wholesale Transmission Revenues",
        },
    )

    assert decision["action_class"] == "already_covered_not_gap"
    assert decision["closeout_reason"] == "source_specific_revenue_claim_already_covered"


def test_classifies_ice_cds_clearing_as_period_column_group_candidate() -> None:
    decision = MODULE.classify_rejection(
        {"rejection_reason": "missing_strong_revenue_table_context", "ticker": "ICE"},
        {
            "metric_family": "product_revenue",
            "unit": "USD",
            "product_or_segment": "CDS",
            "row_label": "CDS clearing",
            "column_label": "2023",
        },
    )

    assert decision["action_class"] == "period_column_group_candidate"
    assert decision["closeout_reason"] == "ice_cds_clearing_column_group_ambiguous"


def test_classifies_financial_row_label_binding_as_not_product_kpi() -> None:
    decision = MODULE.classify_rejection(
        {"rejection_reason": "not_bound_to_structured_row_label", "ticker": "AMT"},
        {"metric_family": "product_revenue", "unit": "USD", "row_label": "Operating activities"},
    )

    assert decision["action_class"] == "not_promotable_public_disclosure_cell"
    assert decision["closeout_reason"] == "row_label_is_financial_or_company_total_not_product_kpi"


def test_final_accepted_fact_overrides_candidate_state() -> None:
    decision = MODULE.classify_with_final_phase_outcome(
        rejection={"rejection_reason": "not_product_revenue", "ticker": "ED"},
        full={"metric_family": "unit_sales_or_deliveries"},
        fact_id="accepted-source-id",
        accepted_fact_ids={"accepted-source-id"},
        phase_rejections={},
    )

    assert decision["action_class"] == "final_accepted_not_gap"
    assert decision["target_phase"] == "closeout_only"


def test_phase_rejection_overrides_candidate_state() -> None:
    decision = MODULE.classify_with_final_phase_outcome(
        rejection={"rejection_reason": "not_product_revenue", "ticker": "ED"},
        full={"metric_family": "unit_sales_or_deliveries"},
        fact_id="low-value-id",
        accepted_fact_ids=set(),
        phase_rejections={
            "low-value-id": {
                "phase": "operating_metric_repair",
                "reason": "ed_gas_delivered_customer_count_or_subtotal_not_total_mdt",
            }
        },
    )

    assert decision["action_class"] == "phase_verified_rejection_not_gap"
    assert decision["closeout_reason"] == "operating_metric_repair_ed_gas_delivered_customer_count_or_subtotal_not_total_mdt"
