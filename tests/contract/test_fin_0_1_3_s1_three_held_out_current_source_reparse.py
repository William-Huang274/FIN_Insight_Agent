from __future__ import annotations

import json
from pathlib import Path

import pytest

from evidence.schema import EvidenceObject
from evidence.structured_objects import MetricObject
from evidence.structured_extractor import extract_structured_objects
from ingestion.parse_sec_filing import extract_sec_html_text_content
from sec_agent.financial_research_candidate_bundle_v2 import project_candidate_bundle_v2
from sec_agent.financial_research_current_source_reparse import (
    classify_financial_object_slot,
    classify_captured_document,
    load_current_source_reparse_policy,
    validate_current_source_reparse_result,
)


pytestmark = pytest.mark.fast_contract

ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s1_three_held_out_"
    "current_source_reparse_policy_v1_0.json"
)
RESULT_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_three_held_out_"
    "current_source_reparse_result_v1_0.json"
)


def _asml_extraction():
    html = """
    <html><body>
      <table>
        <tr><th>Figures in millions of euros unless otherwise indicated</th><th>Q1 2026</th><th>Q2 2026</th></tr>
        <tr><td>Total net sales</td><td>8,767</td><td>9,326</td></tr>
        <tr><td>New lithography systems sold (units)</td><td>67</td><td>86</td></tr>
        <tr><td>Gross margin (%)</td><td>53.0</td><td>54.0</td></tr>
        <tr><td>Net income</td><td>2,757</td><td>2,918</td></tr>
        <tr><td>Earnings per ordinary share</td><td>6.00</td><td>6.41</td></tr>
      </table>
      <table>
        <tr><td>Investor Relations</td><td>+31 40 268 3000</td></tr>
        <tr><td>Media Relations</td><td>+31 40 268 2028</td></tr>
      </table>
    </body></html>
    """
    text = extract_sec_html_text_content(html)
    evidence = EvidenceObject(
        evidence_id="ASML_CURRENT_FIXTURE",
        source_type="6-K",
        source_tier="primary_sec_filing",
        ticker="ASML",
        company="ASML Holding N.V.",
        fiscal_year=2026,
        period_end="2026-06-28",
        fiscal_period="Q2",
        publication_date="2026-07-15",
        evidence_type="company_authored_disclosure",
        text=text,
        source_url="https://www.sec.gov/example/asml-results.htm",
        metadata={"form_type": "6-K", "reporting_currency": "EUR"},
    )
    return evidence, extract_structured_objects(evidence)


def _projection_inputs():
    parent, extracted = _asml_extraction()
    metric = next(
        row
        for row in extracted.metrics
        if row.row_label == "Total net sales" and row.column_label == "Q2 2026"
    )
    lane = {
        "lane_id": "asml_current_operating_performance",
        "slot_id": "operating_performance",
        "asset_id": "current_financial_objects",
        "evidence_owner_entity_key": "ASML_HOLDING",
        "evidence_owner_ticker": "ASML",
        "relationship_direction": "subject_self_disclosure",
    }
    candidate = {
        "asset_id": "current_financial_objects",
        "target_id": metric.object_id,
        "source_record_id": parent.evidence_id,
        "object_type": "metric",
        "ticker": "ASML",
    }
    return parent.model_dump(mode="json"), metric.model_dump(mode="json"), lane, candidate


def _project(child: dict, *, parent: dict | None = None) -> dict:
    base_parent, _, lane, candidate = _projection_inputs()
    return project_candidate_bundle_v2(
        case_key="ASML",
        research_as_of="2026-08-06",
        reporting_currency="EUR",
        reporting_currency_authority="fixture_profile",
        lane=lane,
        candidate=candidate,
        parent=base_parent if parent is None else parent,
        child=child,
    )


def test_policy_freezes_three_cases_and_blocks_index_build_during_reparse() -> None:
    policy = load_current_source_reparse_policy(POLICY_PATH, repo_root=ROOT)
    assert tuple(row.case_key for row in policy.source_bindings) == ("ORCL", "ASML", "ANET")
    assert policy.hard_boundaries["index_build_allowed_during_reparse"] is False
    assert policy.hard_boundaries["ticker_specific_parser_branch_allowed"] is False
    assert policy.hard_boundaries["directory_mime_is_parser_authority"] is False


def test_html_signature_and_actual_mime_override_bad_directory_mime() -> None:
    route = classify_captured_document(
        final_url="https://issuer.example/results.htm",
        actual_content_type="text/html",
        directory_declared_type="text.gif",
        body=b"<html><body>results</body></html>",
    )
    assert route["terminal_state"] == "parser_ready"
    assert route["parser_family"] == "html_table_preserving"
    assert "directory_mime_is_advisory_not_parser_authority" in route["finding_codes"]


def test_pdf_without_layout_adapter_is_typed_gap_not_fake_html() -> None:
    route = classify_captured_document(
        final_url="https://issuer.example/results.pdf",
        actual_content_type="application/pdf",
        directory_declared_type="application/pdf",
        body=b"%PDF-1.7\nfixture",
    )
    assert route["terminal_state"] == "typed_parser_capability_gap"
    assert route["gap_code"] == "pdf_layout_preserving_table_adapter_pending"


def test_eur_quarter_table_preserves_headers_units_and_exact_cell_lineage() -> None:
    _, extracted = _asml_extraction()
    table = extracted.tables[0]
    assert table.candidate_periods == ["Q1 2026", "Q2 2026"]
    metrics = {
        (row.row_label, row.column_label): row
        for row in extracted.metrics
        if row.extraction_method == "table_row_heuristic"
    }
    assert ("Figures in millions of euros unless otherwise indicated", "Q1 2026") not in metrics
    assert metrics[("Total net sales", "Q2 2026")].unit == "eur_millions"
    assert metrics[("New lithography systems sold (units)", "Q2 2026")].unit == "count"
    assert metrics[("Gross margin (%)", "Q2 2026")].unit == "percent"
    assert metrics[("Earnings per ordinary share", "Q2 2026")].unit == "eur_per_share"
    sales = metrics[("Total net sales", "Q2 2026")]
    assert sales.metadata["source_table_id"] == table.table_id
    assert sales.metadata["table_cell_key"]


def test_header_and_contact_numbers_are_not_admitted_as_table_metrics() -> None:
    _, extracted = _asml_extraction()
    table_metrics = [
        row for row in extracted.metrics if row.extraction_method == "table_row_heuristic"
    ]
    assert not any("Figures in millions" in str(row.row_label) for row in table_metrics)
    assert not any("Relations" in str(row.row_label) for row in table_metrics)
    assert len(extracted.tables[1].cells) == 0


def test_grouped_year_and_descriptor_headers_preserve_amount_rate_coordinates() -> None:
    html = """
    <html><body><table>
      <tr><th>May 31,</th></tr>
      <tr><th>2026</th><th>2025</th></tr>
      <tr><th>(Amounts in millions)</th><th>Date of Issuance</th><th>Amount</th>
          <th>Effective Interest Rate</th><th>Amount</th><th>Effective Interest Rate</th></tr>
      <tr><td>$ 1,500, 4.10%, due March 2061</td><td>March 2021</td>
          <td>1,500</td><td>4.13%</td><td>1,500</td><td>4.13%</td></tr>
    </table></body></html>
    """
    evidence = EvidenceObject(
        evidence_id="ORCL_DEBT_HEADER_FIXTURE",
        source_type="10-K",
        source_tier="primary_sec_filing",
        ticker="ORCL",
        fiscal_year=2026,
        period_end="2026-05-31",
        fiscal_period="FY",
        evidence_type="filing_disclosure",
        text=extract_sec_html_text_content(html),
        metadata={"form_type": "10-K", "reporting_currency": "USD"},
    )
    extracted = extract_structured_objects(evidence)
    metrics = {
        (row.column_label, row.raw_value): row
        for row in extracted.metrics
        if row.extraction_method == "table_row_heuristic"
    }
    assert ("Amount 2026", "1,500") in metrics, sorted(map(repr, metrics))
    assert metrics[("Amount 2026", "1,500")].period == "2026"
    assert metrics[("Amount 2026", "1,500")].unit == "usd_millions"
    assert metrics[("Effective Interest Rate 2026", "4.13%")].unit == "percent"
    assert metrics[("Amount 2025", "1,500")].period == "2025"
    assert metrics[("Effective Interest Rate 2025", "4.13%")].unit == "percent"


def test_bundle_uses_bound_source_table_and_source_cell_key() -> None:
    _, child, _, _ = _projection_inputs()
    result = _project(child)
    assert result["terminal_state"] == "bundle_projected"
    assert result["bundle"]["table_path"]["table_id"] == child["metadata"]["source_table_id"]
    assert result["bundle"]["table_path"]["cell_key"] == child["metadata"]["table_cell_key"]
    assert result["bundle"]["currency_unit_authority"]["canonical_unit"] == "eur_millions"


def test_wrong_table_and_cell_lineage_fail_closed() -> None:
    _, child, _, _ = _projection_inputs()
    wrong_table = json.loads(json.dumps(child))
    wrong_table["metadata"]["source_table_id"] = "wrong-table"
    table_result = _project(wrong_table)
    assert table_result["terminal_state"] == "rejected_typed_gap"
    assert "table_semantic_path_missing" in table_result["finding_codes"]

    wrong_cell = json.loads(json.dumps(child))
    wrong_cell["metadata"]["table_cell_key"] = "wrong-cell"
    cell_result = _project(wrong_cell)
    assert cell_result["terminal_state"] == "rejected_typed_gap"
    assert "table_cell_key_mismatch" in cell_result["finding_codes"]


def test_non_monetary_dimensions_are_not_coerced_to_currency() -> None:
    parent, extracted = _asml_extraction()
    for row_label, expected_unit in (
        ("New lithography systems sold (units)", "count"),
        ("Gross margin (%)", "percent"),
    ):
        metric = next(
            row
            for row in extracted.metrics
            if row.row_label == row_label and row.column_label == "Q2 2026"
        )
        lane = {
            "lane_id": "asml_dimension_fixture",
            "slot_id": "pricing_mix_value_capture",
            "asset_id": "current_financial_objects",
            "evidence_owner_entity_key": "ASML_HOLDING",
            "evidence_owner_ticker": "ASML",
            "relationship_direction": "subject_self_disclosure",
        }
        candidate = {
            "asset_id": "current_financial_objects",
            "target_id": metric.object_id,
            "source_record_id": parent.evidence_id,
            "object_type": "metric",
            "ticker": "ASML",
        }
        result = project_candidate_bundle_v2(
            case_key="ASML",
            research_as_of="2026-08-06",
            reporting_currency="EUR",
            reporting_currency_authority="fixture_profile",
            lane=lane,
            candidate=candidate,
            parent=parent.model_dump(mode="json"),
            child=metric.model_dump(mode="json"),
        )
        assert result["terminal_state"] == "bundle_projected"
        authority = result["bundle"]["currency_unit_authority"]
        assert authority["canonical_unit"] == expected_unit
        assert authority["status"] == "non_monetary_dimension_preserved"


@pytest.mark.parametrize(
    ("row_label", "metric_name", "expected_slot"),
    (
        (
            "Notes payable and other borrowings, non-current",
            "Assets | Cash and cash equivalents | Notes payable and other borrowings",
            "capital_allocation_and_valuation",
        ),
        (
            "Risk-free interest rate",
            "Risk factors | Cash flow assumptions | Risk-free interest rate",
            "capital_allocation_and_valuation",
        ),
        (
            "% of Total Revenues",
            "Statements of Operations | Revenue | % of Total Revenues",
            "pricing_mix_value_capture",
        ),
        (
            "Deferred tax assets",
            "Risk factors | Cash and cash equivalents | Other borrowings",
            None,
        ),
        (
            "Proceeds from maturities of marketable securities",
            "Investing activities | maturities",
            "cash_conversion_balance_sheet",
        ),
        (
            "Customer relationships",
            "Intangible assets | customer relationships",
            "capital_allocation_and_valuation",
        ),
    ),
)
def test_metric_slot_routing_uses_row_semantics_not_table_context(
    row_label: str,
    metric_name: str,
    expected_slot: str | None,
) -> None:
    metric = MetricObject(
        object_id="ROUTING_FIXTURE",
        source_evidence_id="ROUTING_PARENT",
        ticker="FIX",
        metric_name=metric_name,
        raw_value="42",
        value=42.0,
        unit="usd_millions",
        row_label=row_label,
        column_label="2026",
        context="Unrelated table-wide risk, cash and debt words",
        extraction_method="table_row_heuristic",
    )
    assert classify_financial_object_slot(metric) == expected_slot


def test_materialized_result_is_digest_valid_and_only_admits_next_index_step() -> None:
    if not RESULT_PATH.exists():
        pytest.skip("current-source reparse result not materialized")
    payload = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    validate_current_source_reparse_result(payload)
    assert payload["stage_acceptance"]["three_case_source_object_migration"] is True
    assert payload["stage_acceptance"]["sparse_dense_rebuild_admitted"] is True
    assert payload["stage_acceptance"]["held_out_product_generalization"] is False
    assert payload["stage_acceptance"]["model_research_admitted"] is False
    for case_result in payload["case_results"]:
        metric_examples = [
            row
            for row in case_result["public_bundle_examples"]
            if row["object_type"] == "metric"
        ]
        assert metric_examples
        assert all(row["object_summary"]["period"] == "2026" for row in metric_examples)
