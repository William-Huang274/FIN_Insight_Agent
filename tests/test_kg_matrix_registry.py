from __future__ import annotations

from pathlib import Path

from sec_agent.kg_matrix_registry import (
    KG_MATRIX_REGISTRY_SCHEMA_VERSION,
    compact_kg_matrix_registry,
    derive_minimal_kg_registry,
    load_kg_matrix_registry,
    validate_kg_matrix_registry,
)
from sec_agent.kg_minimal_registry import load_kg_minimal_registry, validate_kg_minimal_registry


def test_kg_matrix_registry_loads_full_k1_k2_k3_contracts() -> None:
    registry = load_kg_matrix_registry()
    validation = validate_kg_matrix_registry(registry)
    compact = compact_kg_matrix_registry(registry)

    assert registry["schema_version"] == KG_MATRIX_REGISTRY_SCHEMA_VERSION
    assert validation["status"] == "pass"
    assert {"ProductFamily", "ProductModel", "ProductSpec", "ChannelOffer", "FieldInquiryNote"} <= set(
        compact["product_spec_node_types"]
    )
    assert {
        "CapitalStructure",
        "DebtInstrument",
        "CreditFacility",
        "EquityOffering",
        "OwnershipPosition",
        "InsiderTransaction",
    } <= set(compact["capital_ownership_node_types"])
    assert {"MacroDriver", "CompanyExposureToDriver"} <= set(compact["macro_exposure_node_types"])
    assert "product_model_has_spec" in compact["edge_types"]
    assert "company_exposed_to_macro_driver" in compact["edge_types"]
    assert "product_technology_subagent" in compact["subagent_ids"]
    assert "commerce_product_surface" in compact["source_class_boundaries"]


def test_kg_matrix_registry_preserves_channel_and_field_inquiry_boundaries() -> None:
    registry = load_kg_matrix_registry()
    compact = compact_kg_matrix_registry(registry)
    product_spec = registry["product_spec_ontology"]
    source_policy = registry["source_policy"]
    product_subagent = registry["subagent_slices"]["product_technology_subagent"]

    assert "sell_through" in compact["channel_offer_forbidden_claims"]
    assert "company_ASP" in compact["channel_offer_forbidden_claims"]
    assert "authority_fact" in compact["field_inquiry_forbidden_claims"]
    assert "impersonate_credentials_or_authorization" in source_policy["public_buyer_observer"]["forbidden_actions"]
    assert "submit_false_forms_or_orders" in source_policy["public_buyer_observer"]["forbidden_actions"]
    assert "channel_offer_as_sell_through" in product_subagent["forbidden"]
    assert "ProductSpecPack" in product_subagent["outputs"]
    assert "source_id" in product_spec["common_required_fields"]
    assert "observed_at" in product_spec["channel_offer_required_fields"]


def test_kg_matrix_registry_derives_minimal_view_for_existing_d7_d8_consumers() -> None:
    registry = load_kg_matrix_registry()
    minimal = derive_minimal_kg_registry(registry)
    validation = validate_kg_minimal_registry(minimal)

    assert minimal["schema_version"] == "fin_agent_kg_minimal_p0_k1_k2_k3_registry_v0.1"
    assert validation["status"] == "pass"
    assert "ProductFamily" in minimal["p0_business_product_kpi_graph"]["object_types"]
    assert "ProductModel" not in minimal["p0_business_product_kpi_graph"]["object_types"]
    assert "field_inquiry_boundary" in minimal["k2_product_spec_ontology"]
    assert "source_class_claim_boundaries" in minimal["k3_source_policy_minimal"]


def test_load_minimal_registry_accepts_full_matrix_registry_path() -> None:
    path = Path("configs/kg_matrix_registry_v0_1.yaml")
    minimal = load_kg_minimal_registry(path)

    assert minimal["schema_version"] == "fin_agent_kg_minimal_p0_k1_k2_k3_registry_v0.1"
    assert minimal["registry_id"] == "derived_from_kg_matrix_registry_v0_1"
    assert validate_kg_minimal_registry(minimal)["status"] == "pass"
