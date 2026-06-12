from __future__ import annotations

from sec_agent.kg_minimal_registry import (
    compact_kg_minimal_registry,
    load_kg_minimal_registry,
    validate_kg_minimal_registry,
)


def test_kg_minimal_registry_loads_p0_k1_k2_k3_contracts() -> None:
    registry = load_kg_minimal_registry()
    validation = validate_kg_minimal_registry(registry)
    compact = compact_kg_minimal_registry(registry)

    assert validation["status"] == "pass"
    assert registry["schema_version"] == "fin_agent_kg_minimal_p0_k1_k2_k3_registry_v0.1"
    assert {"Company", "Segment", "ProductFamily", "ProductKPI"} <= set(compact["p0_object_types"])
    assert {"reports_segment", "segment_contains_product", "product_has_kpi"} <= set(compact["p0_edge_types"])
    assert {
        "semiconductors",
        "consumer_electronics",
        "software_saas",
        "banks",
        "pharma_biotech",
        "autos_ev",
        "energy_oil_gas",
        "retail_cpg",
    } <= set(compact["industries"])
    assert "public_source_context" in compact["source_family_boundaries"]
    assert "commerce_product_surface" in compact["public_buyer_observer_allowed_source_classes"]


def test_kg_minimal_registry_blocks_proxy_and_impersonation_boundaries() -> None:
    registry = load_kg_minimal_registry()
    p0_policy = registry["p0_business_product_kpi_graph"]["promotion_policy"]
    k2_boundary = registry["k2_product_spec_ontology"]["channel_offer_boundary"]
    public_buyer = registry["k3_source_policy_minimal"]["public_buyer_observer"]
    public_context = registry["k3_source_policy_minimal"]["source_family_claim_boundaries"]["public_source_context"]
    commercial_tracker = registry["k3_source_policy_minimal"]["source_family_claim_boundaries"]["commercial_market_tracker"]

    assert "public_proxy_to_company_sales" in p0_policy["forbidden_promotions"]
    assert "company_sales" in k2_boundary["forbidden_claims"]
    assert "impersonate_credentials_or_authorization" in public_buyer["forbidden_actions"]
    assert public_context["authority"] == "context_only"
    assert commercial_tracker["gap_policy"] == "expose_commercial_gap_do_not_proxy"
