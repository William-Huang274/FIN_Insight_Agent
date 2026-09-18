"""Quantity notation is a lexical binding, not a product interpretation."""
from hashlib import sha256

import pytest

from sec_agent.research_foundation.source_bound_calculator import SourceBoundCalculation, calculate_from_sources


def calculate_count(text, literal="8"):
    request = SourceBoundCalculation(expression="count * 2", operands={
        "count": {"source_id": "PASSAGE::fixture", "quote": text, "literal": literal}},
        result_unit="fixture_units", rationale="Synthetic quantity-notation regression, not a product fact.")
    source = {"result_state": "source_bound_passage", "writer_citable": True,
        "numeric_fact_authority": False, "passage": text,
        "content_sha256": sha256(text.encode()).hexdigest()}
    return calculate_from_sources(request, lambda _: source)


@pytest.mark.parametrize("text", ["8x accelerators", "8X accelerators", "Count: 8x"])
def test_quantity_suffix_keeps_original_binding_and_compatibility_audit(text):
    result = calculate_count(text)
    assert result["value_decimal"] == "16"
    assert not result["numeric_fact_authority"] and not result["financial_semantics_verified"]
    binding = result["operands"]["count"]
    assert binding["quote"] == text and binding["literal"] == "8"
    receipt = binding["runtime_compatibility_parse"]
    assert receipt["rule"] == "numeric_quantity_x_suffix_v1"
    start, end = receipt["quote_span"]
    assert text[start:end] == receipt["matched_text"]
    assert receipt["original_literal_preserved"] and not receipt["semantic_inference"]


@pytest.mark.parametrize("text", ["18x accelerators", "0.8x accelerators", "1,008x accelerators",
    "A8x accelerators", "model8x", "8xlarge", "8X_model", "FP8", "8.5x units",
    "8GB200", "A8GB", "8GB_model", "8GB/s_extra", "8Widgets", "8gb", "18GB", "0.8GB"])
def test_quantity_compatibility_rejects_partial_numbers_and_identifiers(text):
    with pytest.raises(ValueError, match="numeric_literal_not_in_exact_source_quote: operand=count"):
        calculate_count(text)


@pytest.mark.parametrize("text,literal,value", [
    ("Memory | 80GB | 94GB", "80", "160"),
    ("Bandwidth 3.35TB/s", "3.35", "6.70"),
    ("Power up to 700W (configurable)", "700", "1400"),
    ("Capacity 8GiB", "8", "16"),
    ("Capacity 8GB", "8", "16"),
    ("Compute 8PFLOPS", "8", "16"),
])
def test_known_specification_units_preserve_lexical_receipt_without_semantic_inference(text, literal, value):
    result = calculate_count(text, literal)
    assert result["value_decimal"] == value
    binding = result["operands"]["count"]
    assert binding["literal"] == literal and binding["quote"] == text
    receipt = binding["runtime_compatibility_parse"]
    assert receipt["rule"] == "numeric_specification_unit_suffix_v1"
    start, end = receipt["quote_span"]
    assert text[start:end] == receipt["matched_text"]
    assert not receipt["semantic_inference"] and not binding["extraction_meaning_verified"]
    assert not result["financial_semantics_verified"] and not result["numeric_fact_authority"]


def test_plain_number_retains_existing_shape_and_exact_quote_validation():
    result = calculate_count("8 accelerators")
    assert "runtime_compatibility_parse" not in result["operands"]["count"]
    request = SourceBoundCalculation(expression="count", operands={"count": {
        "source_id": "PASSAGE::fixture", "quote": "8x accelerators", "literal": "8"}},
        result_unit="units", rationale="The quote must actually be present.")
    with pytest.raises(ValueError, match="operand_quote_not_in_observed_source"):
        calculate_from_sources(request, lambda _: {"result_state": "source_bound_passage",
            "writer_citable": True, "passage": "4x accelerators"})
