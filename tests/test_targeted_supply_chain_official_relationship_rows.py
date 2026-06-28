from __future__ import annotations

import importlib.util
from pathlib import Path

from sec_agent.exact_slot_contracts import build_exact_slot_rows


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "data_expansion"
    / "build_targeted_supply_chain_official_relationship_rows.py"
)
SPEC = importlib.util.spec_from_file_location("build_targeted_supply_chain_official_relationship_rows", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_targeted_supply_chain_row_requires_issuer_and_counterparty_aliases(tmp_path: Path, monkeypatch) -> None:
    def fake_fetch(url: str, *, timeout_s: float) -> tuple[str, str, str]:
        assert timeout_s == 2
        assert "nvidia" in url
        return (
            "ok",
            "<html><body>NVIDIA and Foxconn are working on an AI factory for AI server manufacturing.</body></html>",
            "",
        )

    monkeypatch.setattr(MODULE, "_fetch_text", fake_fetch)
    result = MODULE._process_seed(
        "2317.TW",
        MODULE.TARGETED_RELATIONSHIP_SEEDS["2317.TW"][0],
        generated_at="2026-06-19T00:00:00Z",
        raw_dir=tmp_path,
        timeout_s=2,
    )

    assert len(result["rows"]) == 1
    assert result["attempts"][0]["status"] == "materialized"
    row = result["rows"][0]
    assert row["ticker"] == "2317.TW"
    assert row["source_id"] == "supplier_customer_official_news"
    assert row["requirement_id"] == "supply_chain_official_relationship"
    assert row["source_role"] == "official_customer_order_or_deployment_event"
    assert row["event_type"] == "production_or_manufacturing_plan"
    assert "official_customer_order_or_deployment_event" in row["allowed_claims"]
    assert row["exact_value_authority"] is False
    assert "shipment_volume" in row["forbidden_claims"]

    payload = build_exact_slot_rows(result["rows"], generated_at="2026-06-19T00:00:00Z")
    assert payload["exact_slot_row_count"] == 2
    assert {row["requirement_id"] for row in payload["exact_rows"]} == {
        "supply_chain_official_relationship",
        "official_customer_order_or_deployment_event",
    }


def test_targeted_supply_chain_aehr_seed_requires_official_customer_order_binding(
    tmp_path: Path, monkeypatch
) -> None:
    def fake_fetch(url: str, *, timeout_s: float) -> tuple[str, str, str]:
        assert "aehr.com" in url
        return (
            "ok",
            "<html><body>Aehr Test Systems announced a production order from its lead hyperscale AI customer for FOX-XP wafer-level test and burn-in systems.</body></html>",
            "",
        )

    monkeypatch.setattr(MODULE, "_fetch_text", fake_fetch)
    result = MODULE._process_seed(
        "AEHR",
        MODULE.TARGETED_RELATIONSHIP_SEEDS["AEHR"][0],
        generated_at="2026-06-23T00:00:00Z",
        raw_dir=tmp_path,
        timeout_s=2,
    )

    assert len(result["rows"]) == 1
    row = result["rows"][0]
    assert row["ticker"] == "AEHR"
    assert row["counterparty"] == "Lead hyperscale AI customer"
    assert row["requirement_id"] == "supply_chain_official_relationship"
    assert row["source_role"] == "official_customer_order_or_deployment_event"
    assert row["event_type"] == "customer_order"
    assert row["exact_value_authority"] is False
    assert "revenue" in row["forbidden_claims"]


def test_targeted_supply_chain_row_rejects_unbound_official_page(tmp_path: Path, monkeypatch) -> None:
    def fake_fetch(url: str, *, timeout_s: float) -> tuple[str, str, str]:
        return "ok", "<html><body>NVIDIA AI factory update without the issuer alias.</body></html>", ""

    monkeypatch.setattr(MODULE, "_fetch_text", fake_fetch)
    result = MODULE._process_seed(
        "2317.TW",
        MODULE.TARGETED_RELATIONSHIP_SEEDS["2317.TW"][0],
        generated_at="2026-06-19T00:00:00Z",
        raw_dir=tmp_path,
        timeout_s=2,
    )

    assert result["rows"] == []
    assert result["attempts"][0]["status"] == "official_page_missing_required_aliases"


def test_targeted_supply_chain_targets_current_gap_tickers(tmp_path: Path, monkeypatch) -> None:
    def fake_fetch(url: str, *, timeout_s: float) -> tuple[str, str, str]:
        return "ok", "<html><body>NVIDIA and Wistron announced AI supercomputer manufacturing.</body></html>", ""

    monkeypatch.setattr(MODULE, "_fetch_text", fake_fetch)
    result = MODULE.build_targeted_supply_chain_official_relationship_rows(
        matrix_rows=[
            {
                "ticker": "3231.TW",
                "source_role_matrix": [
                    {"requirement_id": "supply_chain_official_relationship", "status": "gap"},
                    {"requirement_id": "public_order_proxy", "status": "pass"},
                ],
            },
            {
                "ticker": "2382.TW",
                "source_role_matrix": [{"requirement_id": "supply_chain_official_relationship", "status": "pass"}],
            },
        ],
        generated_at="2026-06-19T00:00:00Z",
        raw_dir=tmp_path,
        timeout_s=2,
        sleep_s=0,
    )

    assert result["targeted_gap_ticker_count"] == 1
    assert [row["ticker"] for row in result["rows"]] == ["3231.TW"]
