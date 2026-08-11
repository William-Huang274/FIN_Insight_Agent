from __future__ import annotations

from sec_agent.entities.entity_resolution import build_entity_alias_registry
from sec_agent.relationships.relationship_verifier import verify_relationship_edge
from sec_agent.relationships.sec_edge_extractor import extract_relationship_edges_from_evidence


def test_sec_customer_concentration_extractor_preserves_evidence_and_verifies() -> None:
    registry = build_entity_alias_registry(
        [
            {"ticker": "ACME", "cik": "111111", "company_name": "Acme Corp"},
            {"ticker": "SRC", "cik": "222222", "company_name": "Source Company Inc"},
        ]
    )
    evidence = {
        "evidence_id": "SRC_2025_10K_ITEM1A_CUSTOMER_0001",
        "ticker": "SRC",
        "company": "Source Company Inc",
        "source_type": "10-K",
        "source_tier": "primary_sec_filing",
        "fiscal_year": 2025,
        "period_end": "2025-12-31",
        "source_url": "https://www.sec.gov/example",
        "section": "Item 1A. Risk Factors",
        "text": "Acme Corp accounted for 15% of revenue during fiscal 2025.",
    }

    edges = extract_relationship_edges_from_evidence(evidence, entity_registry=registry)
    verified = verify_relationship_edge(edges[0])

    assert len(edges) == 1
    assert edges[0]["relation_type"] == "direct_customer_supplier"
    assert edges[0]["direction"] == "source_sells_to_target"
    assert edges[0]["target_ticker"] == "ACME"
    assert edges[0]["percentage"] == 15.0
    assert edges[0]["evidence_id"] == evidence["evidence_id"]
    assert "Acme Corp accounted" in edges[0]["evidence_text"]
    assert verified["status"] == "pass"
    assert verified["edge"]["verifier_status"] == "verified"


def test_partner_extractor_does_not_rewrite_partnership_as_customer_supplier() -> None:
    registry = build_entity_alias_registry([{"ticker": "GLOB", "cik": "333333", "company_name": "Globex LLC"}])
    evidence = {
        "evidence_id": "SRC_2026_8K_EX99_PARTNER",
        "ticker": "SRC",
        "company": "Source Company Inc",
        "source_type": "8-K",
        "source_tier": "company_authored_unaudited_sec_filing",
        "fiscal_year": 2026,
        "period_end": "2026-03-31",
        "text": "The company announced a strategic partnership agreement with Globex LLC to expand channel access.",
    }

    edges = extract_relationship_edges_from_evidence(evidence, entity_registry=registry)

    assert edges
    assert edges[0]["relation_type"] == "partner_channel"
    assert edges[0]["relationship_type"] == "other"
    assert edges[0]["target_name_raw"] == "Globex LLC"


def test_customer_concentration_extractor_rejects_geographic_region_lists() -> None:
    evidence = {
        "evidence_id": "ALB_2025_10K_NOTE_REGION_CUSTOMER",
        "ticker": "ALB",
        "company": "Albemarle Corporation",
        "source_type": "10-K",
        "source_tier": "primary_sec_filing",
        "fiscal_year": 2025,
        "period_end": "2025-12-31",
        "text": "South Korea, China and Japan accounted for 42% of revenue during fiscal 2025.",
    }

    edges = extract_relationship_edges_from_evidence(evidence, entity_registry=[])

    assert edges == []


def test_supplier_extractor_rejects_geographic_descriptor() -> None:
    evidence = {
        "evidence_id": "LLY_2025_10K_SUPPLIER_DESCRIPTOR",
        "ticker": "LLY",
        "company": "Eli Lilly and Company",
        "source_type": "10-K",
        "source_tier": "primary_sec_filing",
        "fiscal_year": 2025,
        "period_end": "2025-12-31",
        "text": "The company relies on China-based suppliers for certain components.",
    }

    edges = extract_relationship_edges_from_evidence(evidence, entity_registry=[])

    assert edges == []


def test_customer_extractor_rejects_generic_major_customer_label() -> None:
    evidence = {
        "evidence_id": "TXN_2025_10K_MAJOR_CUSTOMER",
        "ticker": "TXN",
        "company": "Texas Instruments Incorporated",
        "source_type": "10-K",
        "source_tier": "primary_sec_filing",
        "fiscal_year": 2025,
        "period_end": "2025-12-31",
        "text": "Major customer One of our end customers accounted for more than 10% of revenue.",
    }

    edges = extract_relationship_edges_from_evidence(evidence, entity_registry=[])

    assert edges == []


def test_containment_entity_match_does_not_upgrade_edge_to_high_confidence() -> None:
    registry = build_entity_alias_registry([{"ticker": "JNJ", "cik": "200406", "company_name": "Johnson & Johnson"}])
    evidence = {
        "evidence_id": "BMY_2025_10K_NOISY_PARTNER",
        "ticker": "BMY",
        "company": "Bristol-Myers Squibb Company",
        "source_type": "10-K",
        "source_tier": "primary_sec_filing",
        "fiscal_year": 2025,
        "period_end": "2025-12-31",
        "text": "The company announced a partnership with Johnson & Johnson Services to develop a new program.",
    }

    edges = extract_relationship_edges_from_evidence(evidence, entity_registry=registry)

    assert edges
    assert edges[0]["target_name_raw"] == "Johnson & Johnson Services"
    assert edges[0]["target_ticker"] == "JNJ"
    assert edges[0]["confidence"] == "medium"
