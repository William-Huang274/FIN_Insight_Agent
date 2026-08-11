from __future__ import annotations

from sec_agent.relationships.edge_schema import relationship_edge_to_graph_row, validate_relationship_edge


def test_high_confidence_direct_customer_supplier_requires_resolved_target() -> None:
    result = validate_relationship_edge(
        {
            "source_ticker": "NVDA",
            "target_name_raw": "Microsoft Corporation",
            "relation_type": "direct_customer_supplier",
            "direction": "source_sells_to_target",
            "confidence": "high",
            "source_tier": "primary_sec_filing",
            "source_doc_type": "10-K",
            "evidence_id": "ev_nvda_msft",
            "evidence_text": "Microsoft Corporation accounted for 15% of revenue.",
        }
    )

    assert result["status"] == "fail"
    assert "high_confidence_direct_edge_requires_resolved_target" in {item["type"] for item in result["errors"]}


def test_high_confidence_resolved_direct_edge_passes_and_converts_to_graph_row() -> None:
    result = validate_relationship_edge(
        {
            "source_ticker": "NVDA",
            "target_ticker": "MSFT",
            "target_cik": "789019",
            "target_name_raw": "Microsoft Corporation",
            "relation_type": "direct_customer_supplier",
            "direction": "source_sells_to_target",
            "confidence": "high",
            "source_tier": "primary_sec_filing",
            "source_doc_type": "10-K",
            "evidence_id": "ev_nvda_msft",
            "evidence_text": "Microsoft Corporation accounted for 15% of revenue.",
            "verifier_status": "verified",
        }
    )
    graph_row = relationship_edge_to_graph_row(result["edge"])

    assert result["status"] == "pass"
    assert result["edge"]["relationship_type"] == "customer"
    assert graph_row["relationship_type"] == "customer"
    assert graph_row["inference_level"] == "confirmed_direct"
    assert graph_row["claim_scope"] == "scope_or_hypothesis_only"


def test_sector_exposure_cannot_be_high_confidence_direct_fact() -> None:
    result = validate_relationship_edge(
        {
            "source_ticker": "NVDA",
            "target_name_raw": "data center power demand",
            "relation_type": "sector_exposure",
            "direction": "unclear",
            "confidence": "high",
            "source_tier": "industry_snapshot",
            "source_doc_type": "industry",
            "evidence_id": "industry_power_ref",
            "evidence_text": "Data center load growth may increase power demand.",
        }
    )

    assert result["status"] == "fail"
    error_types = {item["type"] for item in result["errors"]}
    assert "sector_exposure_cannot_be_high_confidence_direct_fact" in error_types
    assert "high_confidence_source_tier_not_allowed" in error_types


def test_direct_customer_supplier_rejects_generic_or_geographic_targets() -> None:
    result = validate_relationship_edge(
        {
            "source_ticker": "GE",
            "target_name_raw": "U.S",
            "relation_type": "direct_customer_supplier",
            "direction": "target_sells_to_source",
            "confidence": "medium",
            "source_tier": "primary_sec_filing",
            "source_doc_type": "10-K",
            "evidence_id": "ge_supplier_risk",
            "evidence_text": "The company depends on U.S suppliers for certain components.",
        }
    )

    assert result["status"] == "fail"
    assert "direct_customer_supplier_target_is_generic_or_geographic" in {item["type"] for item in result["errors"]}


def test_direct_customer_supplier_rejects_generic_major_customer_label() -> None:
    result = validate_relationship_edge(
        {
            "source_ticker": "TXN",
            "target_name_raw": "Major customer One of our end customers",
            "relation_type": "direct_customer_supplier",
            "direction": "source_sells_to_target",
            "confidence": "medium",
            "source_tier": "primary_sec_filing",
            "source_doc_type": "10-K",
            "evidence_id": "txn_major_customer",
            "evidence_text": "Major customer One of our end customers accounted for more than 10% of revenue.",
        }
    )

    assert result["status"] == "fail"
    assert "direct_customer_supplier_target_is_generic_or_geographic" in {item["type"] for item in result["errors"]}
