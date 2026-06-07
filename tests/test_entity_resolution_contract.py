from __future__ import annotations

from sec_agent.entities.entity_resolution import build_entity_alias_registry, normalize_entity_name, resolve_entity_name


def test_entity_resolution_exact_alias_strips_legal_suffix() -> None:
    registry = build_entity_alias_registry(
        [
            {
                "ticker": "MSFT",
                "cik": "789019",
                "company_name": "Microsoft Corporation",
                "aliases": ["Microsoft Corp."],
            }
        ]
    )

    result = resolve_entity_name("Microsoft Corp", registry)

    assert normalize_entity_name("Microsoft Corporation") == "microsoft"
    assert result["status"] == "resolved"
    assert result["confidence"] == "high"
    assert result["ticker"] == "MSFT"
    assert result["cik"] == "0000789019"


def test_entity_resolution_keeps_unknown_counterparty_unresolved() -> None:
    registry = build_entity_alias_registry([{"ticker": "NVDA", "company_name": "NVIDIA Corporation"}])

    result = resolve_entity_name("Not A Known Customer LLC", registry)

    assert result["status"] == "unresolved"
    assert result["reason"] == "no_alias_match"
