from __future__ import annotations

from sec_agent.industry_playbooks import load_playbook_registry, match_playbook_candidates, validate_playbook_registry


def test_industry_playbook_registry_loads_required_initial_playbooks() -> None:
    registry = load_playbook_registry()
    validation = validate_playbook_registry(registry)
    playbook_ids = {item["playbook_id"] for item in registry["playbooks"]}

    assert validation["status"] == "pass"
    assert {
        "semiconductors",
        "consumer_electronics",
        "software_saas",
        "banks",
        "energy_oil_gas",
        "pharma_biotech",
        "autos_ev",
        "retail_cpg",
    } <= playbook_ids


def test_playbook_candidate_carries_source_policy_and_forbidden_claims() -> None:
    candidates = match_playbook_candidates({"consumer electronics hardware": {"AAPL", "MSFT"}}, load_playbook_registry())

    assert candidates[0]["playbook_id"] == "consumer_electronics"
    assert "company_product_evidence_graph" in candidates[0]["default_source_families"]
    assert candidates[0]["specialist_routing"]["product_technology_analyst"] == "high"
    assert "sell_through_without_tracker" in candidates[0]["forbidden_claims"]


def test_unknown_industry_uses_generic_playbook_with_coverage_gap() -> None:
    candidates = match_playbook_candidates({"miscellaneous services": {"XYZ"}}, load_playbook_registry())

    assert candidates[0]["playbook_id"] == "generic_public_research"
    assert candidates[0]["status"] == "fallback_candidate"
    assert candidates[0]["coverage_gap"]["gap_type"] == "industry_playbook_not_matched"
