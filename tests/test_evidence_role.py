from __future__ import annotations

from retrieval.evidence_role import evaluate_evidence_role
from retrieval.evidence_role_v3 import (
    evaluate_evidence_role as evaluate_evidence_role_v3,
)


def _document(text: str, *, section: str = "Item 2. MD&A") -> dict[str, str]:
    return {
        "ticker": "NVDA",
        "section": section,
        "subsection": "",
        "document_text": text,
        "source_type": "10-Q",
    }


def test_risk_factor_cannot_substitute_for_observed_results() -> None:
    result = evaluate_evidence_role(
        _document(
            "Customers may cancel or defer orders and purchase commitments may create inventory write-downs.",
            section="Item 1A. Risk Factors",
        ),
        slot_id="operating_performance",
        subject_ticker="NVDA",
    )
    assert result.compatibility == "incompatible"
    assert "demand_risk_or_counterevidence" in result.labels
    assert result.evidence_promoted is False


def test_cash_flow_statement_is_compatible_with_cash_conversion() -> None:
    result = evaluate_evidence_role(
        _document(
            "Statements of Cash Flows. Net cash provided by operating activities was 50,344.",
            section="Item 1. Financial Statements",
        ),
        slot_id="cash_conversion_balance_sheet",
        subject_ticker="NVDA",
    )
    assert result.compatibility == "compatible"
    assert "financial_statement_or_reconciliation" in result.labels


def test_supply_risk_is_compatible_with_capacity_counterevidence() -> None:
    result = evaluate_evidence_role(
        _document(
            "We entered prepaid manufacturing and capacity agreements; production ramp and quality issues may delay supply.",
            section="Item 1A. Risk Factors",
        ),
        slot_id="capacity_inputs_execution",
        subject_ticker="NVDA",
    )
    assert result.compatibility == "compatible"
    assert "supply_risk_or_counterevidence" in result.labels


def test_unknown_semantics_abstain_instead_of_becoming_evidence() -> None:
    result = evaluate_evidence_role(
        _document("The company remains committed to long-term innovation."),
        slot_id="demand_volume_quality",
        subject_ticker="NVDA",
    )
    assert result.compatibility == "abstain"
    assert result.evidence_promoted is False


def test_legacy_combined_slot_accepts_risk_and_financial_evidence_without_qrel_leakage() -> None:
    risk = evaluate_evidence_role(
        _document(
            "Customer demand may vary and large orders may not recur.",
            section="Item 1A. Risk Factors",
        ),
        slot_id="regulatory_risk_and_financial_reconciliation",
        subject_ticker="DELL",
    )
    financial = evaluate_evidence_role(
        _document(
            "Cash flows from operating activities reconciled net income.",
            section="Item 1. Financial Statements",
        ),
        slot_id="regulatory_risk_and_financial_reconciliation",
        subject_ticker="NVDA",
    )

    assert risk.compatibility == "compatible"
    assert financial.compatibility == "compatible"


def test_current_working_capital_facet_accepts_demand_risk_inside_cash_slot() -> None:
    result = evaluate_evidence_role(
        _document(
            "Larger orders may require working capital and expose inventory to cancellations.",
            section="Item 1A. Risk Factors",
        ),
        slot_id="cash_conversion_balance_sheet",
        facet_id="working_capital_risk",
        subject_ticker="DELL",
    )

    assert result.compatibility == "compatible"
    assert "demand_risk_or_counterevidence" in result.labels
    assert result.decision_basis.startswith("deterministic_facet_aware")


def test_metric_row_is_financial_evidence_role_without_numeric_authority() -> None:
    document = _document("Revenue | 31,174 | 23,376 | 33%")
    document["object_kind"] = "metric_row"
    result = evaluate_evidence_role(
        document,
        slot_id="operating_performance",
        facet_id="reported_results",
        subject_ticker="DELL",
    )

    assert result.compatibility == "compatible"
    assert "financial_statement_or_reconciliation" in result.labels
    assert result.evidence_promoted is False


def test_metric_row_issuer_name_cannot_imply_supply_role() -> None:
    document = {
        "ticker": "TSM",
        "section": "6-K current official disclosure",
        "subsection": "Taiwan Semiconductor Manufacturing Company results",
        "document_text": (
            "Company: Taiwan Semiconductor Manufacturing Company Limited (TSM)\n"
            "Table: TSMC second quarter consolidated results\n"
            "Row: Net sales | 1,270,381 | 933,792 | 36.0"
        ),
        "source_type": "6-K",
        "object_kind": "metric_row",
        "structured_projection": {
            "header_lines": [],
            "row_context_lines": [],
            "metric_row_label": "Net sales",
            "metric_row_cells": ["1,270,381", "933,792", "36.0"],
        },
    }
    result = evaluate_evidence_role(
        document,
        slot_id="capacity_inputs_execution",
        facet_id="upstream_capacity_context",
        subject_ticker="NVDA",
        evidence_owner_ticker="TSM",
        relationship_direction="supplier_to_subject",
    )

    assert result.compatibility == "incompatible"
    assert "financial_statement_or_reconciliation" in result.labels
    assert "direct_supply_capacity_signal" not in result.labels


def test_reported_highlight_with_year_over_year_change_is_observed_result() -> None:
    result = evaluate_evidence_role(
        {
            "ticker": "DELL",
            "section": "Exhibit 99.1 Earnings Release",
            "object_kind": "claim",
            "document_text": (
                "Record revenue of $43.8 billion, up 88% year over year; "
                "record cash flow from operations of $4.1 billion."
            ),
        },
        slot_id="operating_performance",
        facet_id="reported_results",
        subject_ticker="DELL",
        evidence_owner_ticker="DELL",
        relationship_direction="subject_self_disclosure",
    )

    assert result.compatibility == "compatible"
    assert "observed_operating_result" in result.labels


def test_risk_factor_with_customer_growth_exposure_is_demand_counterevidence() -> None:
    result = evaluate_evidence_role(
        {
            "ticker": "DELL",
            "section": "Item 1A. Risk Factors",
            "object_kind": "claim",
            "document_text": (
                "If we do not expand sales to a broader base of customers, "
                "our ability to maintain growth may be limited."
            ),
        },
        slot_id="counterevidence_and_what_would_change",
        facet_id="issuer_counterevidence",
        subject_ticker="DELL",
        evidence_owner_ticker="DELL",
        relationship_direction="subject_self_disclosure",
    )

    assert result.compatibility == "compatible"
    assert "demand_risk_or_counterevidence" in result.labels


def test_subject_disclosed_binding_customer_agreement_has_relationship_role() -> None:
    result = evaluate_evidence_role(
        {
            "ticker": "MU",
            "section": "Item 2. Management's Discussion and Analysis",
            "object_kind": "claim",
            "document_text": (
                "These customer agreements include binding commitments for "
                "specific volumes over the multi-year contract terms."
            ),
        },
        slot_id="relationship_attribution",
        facet_id="subject_relationship_disclosure",
        subject_ticker="MU",
        evidence_owner_ticker="MU",
        relationship_direction="subject_self_disclosure",
    )

    assert result.compatibility == "compatible"
    assert "relationship_context" in result.labels


def test_supply_and_demand_risk_can_answer_downstream_counterevidence() -> None:
    result = evaluate_evidence_role(
        {
            "ticker": "NVDA",
            "section": "Item 1A. Risk Factors",
            "object_kind": "claim",
            "document_text": (
                "Managing our supply and demand may create volatility in revenue."
            ),
        },
        slot_id="demand_volume_quality",
        facet_id="downstream_demand_context",
        subject_ticker="MU",
        evidence_owner_ticker="NVDA",
        relationship_direction="downstream_customer_disclosure",
    )

    assert result.compatibility == "compatible"
    assert "demand_risk_or_counterevidence" in result.labels


def test_safe_harbor_boilerplate_overrides_keyword_role_hits() -> None:
    result = evaluate_evidence_role(
        {
            "ticker": "NVDA",
            "section": "Exhibit 99.1 Earnings Release",
            "document_text": (
                "Certain statements in this press release including, but not limited "
                "to, statements as to: AI factory demand, supply, growth and capacity."
            ),
            "object_kind": "claim",
        },
        slot_id="operating_performance",
        facet_id="downstream_demand_context",
        subject_ticker="MU",
        evidence_owner_ticker="NVDA",
        relationship_direction="downstream_customer_disclosure",
    )
    assert "generic_or_boilerplate" in result.labels
    assert result.compatibility == "incompatible"


def test_anaphoric_change_fragment_requires_parent_context() -> None:
    result = evaluate_evidence_role(
        {
            "ticker": "NVDA",
            "section": "Management's Discussion and Analysis",
            "document_text": (
                "The year over year increase was primarily driven by a higher mix "
                "of Data Center revenue."
            ),
            "object_kind": "claim",
        },
        slot_id="operating_performance",
        facet_id="reported_results",
        subject_ticker="NVDA",
    )
    assert "context_dependent_fragment_requires_parent" in result.reason_codes
    assert result.compatibility == "incompatible"


def test_working_capital_observed_mechanism_is_compatible() -> None:
    result = evaluate_evidence_role(
        {
            "ticker": "DELL",
            "section": "Item 7. Management's Discussion and Analysis",
            "document_text": (
                "Working capital during Fiscal 2025 was primarily impacted by AI "
                "dynamics, which led to higher inventory, accounts receivable, "
                "and accounts payable levels."
            ),
            "object_kind": "claim",
        },
        slot_id="cash_conversion_balance_sheet",
        facet_id="working_capital_risk",
        subject_ticker="DELL",
        evidence_owner_ticker="DELL",
        relationship_direction="subject_self_disclosure",
    )

    assert result.compatibility == "compatible"
    assert "observed_operating_result" in result.labels


def test_unrelated_lease_reconciliation_cannot_answer_working_capital() -> None:
    result = evaluate_evidence_role(
        {
            "ticker": "DELL",
            "section": "Item 8. Financial Statements and Supplementary Data",
            "document_text": (
                "The table reconciles undiscounted cash flows for non-cancelable "
                "leases to the recognized lease liability."
            ),
            "object_kind": "claim",
        },
        slot_id="cash_conversion_balance_sheet",
        facet_id="working_capital_risk",
        subject_ticker="DELL",
        evidence_owner_ticker="DELL",
        relationship_direction="subject_self_disclosure",
    )

    assert result.compatibility == "abstain"
    assert "working_capital_semantic_anchor_missing" in result.reason_codes


def test_transcript_analyst_question_is_not_management_evidence() -> None:
    result = evaluate_evidence_role(
        {
            "ticker": "TSM",
            "section": "TSMC Q2 2026 Earnings Call Transcript",
            "document_text": (
                "Jim Fontanelli - Arete Research LLC - Analyst Could I ask about "
                "the risk around customer concentration as AI demand grows?"
            ),
            "object_kind": "claim",
        },
        slot_id="capacity_inputs_execution",
        facet_id="upstream_capacity_context",
        subject_ticker="DELL",
        evidence_owner_ticker="TSM",
        relationship_direction="supplier_to_subject",
    )

    assert result.compatibility == "incompatible"
    assert "transcript_question_without_management_answer" in result.reason_codes


def test_transcript_ir_question_restatement_is_not_management_evidence() -> None:
    result = evaluate_evidence_role(
        {
            "ticker": "TSM",
            "section": "TSMC Q2 2026 Earnings Call Transcript",
            "document_text": (
                "Jeff Su - Taiwan Semiconductor Manufacturing Co Ltd - Director "
                "of Investor Relations. Jim's first question is risk around "
                "customer concentration."
            ),
            "object_kind": "claim",
        },
        slot_id="capacity_inputs_execution",
        facet_id="upstream_capacity_context",
        subject_ticker="DELL",
        evidence_owner_ticker="TSM",
        relationship_direction="supplier_to_subject",
    )

    assert result.compatibility == "incompatible"
    assert "transcript_question_without_management_answer" in result.reason_codes


def test_question_only_transcript_fragment_is_not_fact_evidence() -> None:
    result = evaluate_evidence_role(
        {
            "ticker": "TSM",
            "section": "TSMC Q2 2026 Earnings Call Transcript",
            "document_text": (
                "We have large customers that are getting larger. Are we worried "
                "that we have too many big customers?"
            ),
            "object_kind": "claim",
        },
        slot_id="capacity_inputs_execution",
        facet_id="upstream_capacity_context",
        subject_ticker="DELL",
        evidence_owner_ticker="TSM",
        relationship_direction="supplier_to_subject",
    )

    assert result.compatibility == "incompatible"
    assert "transcript_question_without_management_answer" in result.reason_codes


def test_management_bottleneck_and_tester_shortage_are_supply_evidence() -> None:
    for text in (
        "Sometimes we have a bottleneck, so we buy the bottleneck tools.",
        "The tester is in shortage, so we put more CapEx in packaging and testing.",
    ):
        result = evaluate_evidence_role(
            {
                "ticker": "TSM",
                "section": "TSMC Q2 2026 Earnings Call Transcript",
                "document_text": text,
                "object_kind": "claim",
            },
            slot_id="capacity_inputs_execution",
            facet_id="upstream_capacity_context",
            subject_ticker="DELL",
            evidence_owner_ticker="TSM",
            relationship_direction="supplier_to_subject",
        )

        assert result.compatibility == "compatible"
        assert "direct_supply_capacity_signal" in result.labels


def test_generic_ai_adoption_statement_is_not_direct_customer_demand() -> None:
    result = evaluate_evidence_role(
        {
            "ticker": "MSFT",
            "section": "Item 1. Business",
            "document_text": (
                "Digital transformation and adoption of AI continues to "
                "revolutionize more business workstreams for organizations in "
                "every sector across the globe."
            ),
            "object_kind": "claim",
        },
        slot_id="demand_volume_quality",
        facet_id="downstream_demand_context",
        subject_ticker="MU",
        evidence_owner_ticker="MSFT",
        relationship_direction="downstream_customer_disclosure",
    )

    assert result.compatibility == "abstain"
    assert "direct_demand_signal" not in result.labels


def test_executed_binding_customer_commitment_is_direct_demand_evidence() -> None:
    result = evaluate_evidence_role_v3(
        {
            "ticker": "MU",
            "section": "Item 2. Management's Discussion and Analysis",
            "document_text": (
                "We entered into strategic customer agreements that include "
                "binding commitments for specific volumes over multi-year terms."
            ),
            "object_kind": "claim",
        },
        slot_id="demand_volume_quality",
        facet_id="orders_and_backlog",
        subject_ticker="MU",
        evidence_owner_ticker="MU",
        relationship_direction="subject_self_disclosure",
    )

    assert result.compatibility == "compatible"
    assert "direct_demand_signal" in result.labels
    assert "executed_customer_commitment_surface" in result.reason_codes
    assert result.evidence_promoted is False


def test_hypothetical_customer_agreement_is_not_direct_demand_evidence() -> None:
    result = evaluate_evidence_role_v3(
        {
            "ticker": "MU",
            "section": "Item 1A. Risk Factors",
            "document_text": (
                "We may enter customer agreements that include binding "
                "commitments for specific volumes."
            ),
            "object_kind": "claim",
        },
        slot_id="demand_volume_quality",
        facet_id="orders_and_backlog",
        subject_ticker="MU",
        evidence_owner_ticker="MU",
        relationship_direction="subject_self_disclosure",
    )

    assert "direct_demand_signal" not in result.labels


def test_observed_hbm4_customer_shipments_are_demand_fulfillment() -> None:
    result = evaluate_evidence_role_v3(
        {
            "ticker": "MU",
            "section": "Quarterly Results",
            "document_text": (
                "HBM4 high-volume shipments for our lead customer's platform "
                "began after qualification samples shipped."
            ),
            "object_kind": "claim",
        },
        slot_id="demand_volume_quality",
        facet_id="conversion_and_durability",
        subject_ticker="MU",
        evidence_owner_ticker="MU",
        relationship_direction="subject_self_disclosure",
    )

    assert result.compatibility == "compatible"
    assert "direct_demand_signal" in result.labels
    assert "observed_customer_fulfillment_surface" in result.reason_codes


def test_production_delay_and_supply_management_challenge_is_counterevidence() -> None:
    result = evaluate_evidence_role(
        {
            "ticker": "NVDA",
            "section": "Item 1A. Risk Factors",
            "document_text": (
                "The complexity of bringing up our product architecture and "
                "sophisticated system configurations has caused and may in the "
                "future cause delays in production and create challenges in "
                "managing supply and demand."
            ),
            "object_kind": "claim",
        },
        slot_id="counterevidence_and_what_would_change",
        facet_id="issuer_counterevidence",
        subject_ticker="NVDA",
        evidence_owner_ticker="NVDA",
        relationship_direction="subject_self_disclosure",
    )

    assert result.compatibility == "compatible"
    assert "supply_risk_or_counterevidence" in result.labels
    assert "direct_supply_capacity_signal" not in result.labels
