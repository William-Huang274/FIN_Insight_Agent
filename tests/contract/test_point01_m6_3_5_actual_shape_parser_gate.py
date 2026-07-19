from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from sec_agent.canonical_runtime.bounded_sec_document_execution import (
    BoundedSecDocumentExecutionPolicy,
    SecDocumentParseError,
    extract_approved_table_value,
)


pytestmark = pytest.mark.fast_contract


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/fixtures/point01_m6_3_5_nvda_10k_actual_shape_sanitized.html"
POLICY_PATH = ROOT / "configs/engineering_handoff/point01_m6_3_5_positive_sec_document_pilot_policy_v1_0.json"
SCRIPT = ROOT / "scripts/engineering/run_point01_m6_3_5_actual_shape_parser_gate.py"
SPEC = importlib.util.spec_from_file_location("point01_m6_3_5_actual_shape_parser_gate", SCRIPT)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


def _selector():
    raw = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    policy = BoundedSecDocumentExecutionPolicy.model_validate(
        {field: raw[field] for field in BoundedSecDocumentExecutionPolicy.model_fields}
    )
    return policy.target_table_selector


def _fixture() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def _primary_transform(transform) -> str:
    prefix, primary = _fixture().split("<div>NVIDIA Corporation and Subsidiaries</div>", maxsplit=1)
    return prefix + "<div>NVIDIA Corporation and Subsidiaries</div>" + transform(primary)


def test_actual_shape_gate_uniquely_selects_primary_statement_and_emits_iso_fact() -> None:
    result = GATE.build_result(source_path=FIXTURE, source_kind="sanitized_fixture")
    assert result["status"] == "pass"
    assert result["external_call_count"] == result["store_write_count"] == 0
    output = result["post_parse_output"]
    assert output["table_index"] == 1
    assert output["parsed_value"] == "130497"
    assert output["unit"] == "USD_millions"
    assert output["normalized_period"] == "2025-01-26"
    assert output["financial_statement_role"] == "consolidated_primary_financial_statement"
    assert output["raw_value"] == "$ 130,497"


def test_mda_summary_with_same_row_period_and_value_is_not_an_eligible_primary_table() -> None:
    mda_only = _fixture().split("<div>NVIDIA Corporation and Subsidiaries</div>", maxsplit=1)[0] + "</body></html>"
    with pytest.raises(SecDocumentParseError, match="approved_primary_statement_row_or_period_not_found"):
        extract_approved_table_value(html=mda_only, selector=_selector())


def test_duplicate_primary_statement_tables_fail_closed_instead_of_selecting_one() -> None:
    duplicate = """
    <div>NVIDIA Corporation and Subsidiaries</div>
    <div>Consolidated Statements of Income</div>
    <div>(In millions, except per share data)</div>
    <table><tr><th rowspan="2">Metric</th><th colspan="3">Year Ended</th></tr>
    <tr><th colspan="3">Jan 26, 2025</th></tr>
    <tr><td>Revenue</td><td>$</td><td>130,497</td><td></td></tr></table>
    """
    html = _fixture().replace("</body>", duplicate + "</body>")
    with pytest.raises(SecDocumentParseError, match="approved_primary_statement_row_or_period_ambiguous"):
        extract_approved_table_value(html=html, selector=_selector())


def test_malformed_colspan_cannot_shift_period_group_onto_currency_cell() -> None:
    malformed = _primary_transform(lambda primary: primary.replace('colspan="3">Jan 26, 2025', 'colspan="1">Jan 26, 2025', 1))
    with pytest.raises(SecDocumentParseError, match="approved_primary_statement_row_or_period_not_found"):
        extract_approved_table_value(html=malformed, selector=_selector())


def test_month_abbreviation_and_currency_cell_are_both_required_for_the_iso_period_value() -> None:
    malformed_month = _primary_transform(lambda primary: primary.replace("Jan 26, 2025", "Feb 26, 2025", 1))
    with pytest.raises(SecDocumentParseError, match="approved_primary_statement_row_or_period_not_found"):
        extract_approved_table_value(html=malformed_month, selector=_selector())
    missing_currency = _primary_transform(lambda primary: primary.replace("<td>$</td><td>130,497</td>", "<td></td><td>130,497</td>", 1))
    with pytest.raises(SecDocumentParseError, match="approved_primary_statement_row_or_period_not_found"):
        extract_approved_table_value(html=missing_currency, selector=_selector())


def test_xbrl_hint_cannot_replace_table_role_period_unit_or_currency_lineage() -> None:
    selector = _selector().model_copy(update={"xbrl_concept_hint": "us-gaap:NonexistentConcept"})
    result = extract_approved_table_value(html=_fixture(), selector=selector)
    assert result.table_index == 1
    assert result.financial_statement_role == "consolidated_primary_financial_statement"
