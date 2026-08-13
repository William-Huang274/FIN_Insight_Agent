from __future__ import annotations

from retrieval.evidence_role import evaluate_evidence_role


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
