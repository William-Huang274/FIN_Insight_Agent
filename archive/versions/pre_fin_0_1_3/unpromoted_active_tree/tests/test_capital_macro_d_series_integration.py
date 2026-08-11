from __future__ import annotations

from pathlib import Path

from sec_agent.analyst_view_layer import build_analyst_view_research_memory_layer
from sec_agent.capital_macro_pack import build_capital_macro_pack
from sec_agent.d_series_database_store import (
    materialize_d_series_governance_store,
    read_d_series_governance_counts,
    read_d_series_research_context,
)
from sec_agent.entity_master import build_entity_security_master
from sec_agent.provenance_vintage import build_provenance_vintage_layers


def test_capital_macro_pack_feeds_d3_d4_d5_d11_and_sqlite(tmp_path: Path) -> None:
    state = _capital_macro_state()
    pack = build_capital_macro_pack(state, max_items=20)
    enriched = {**state, "capital_macro_pack": pack}

    entity_master = build_entity_security_master(enriched)
    provenance_vintage = build_provenance_vintage_layers(enriched)
    analyst_memory = build_analyst_view_research_memory_layer(
        {
            **enriched,
            "claim_evidence_ledger": {"claims": []},
            "typed_gap_ledger": {"gaps": []},
            "derived_metric_layer": {"derived_metrics": []},
        }
    )

    assert entity_master["validation"]["status"] == "pass"
    assert any(row["ticker"] == "A" for row in entity_master["entities"])
    assert any(row.get("entity_role") == "investor" for row in entity_master["unresolved_references"])
    assert provenance_vintage["raw_source_provenance_store"]["validation"]["status"] == "pass"
    assert provenance_vintage["asof_vintage_layer"]["validation"]["status"] == "pass"
    assert any(
        row["channel"] == "capital_macro_source_adapter.capital_ownership_rows"
        and row["ticker"] == "A"
        and row["raw_url"].startswith("https://www.sec.gov/")
        for row in provenance_vintage["raw_source_provenance_store"]["records"]
    )
    assert any(
        row["channel"] == "capital_macro_pack.macro_drivers"
        and row["macro_vintage_date"] == "2026-05-01"
        for row in provenance_vintage["asof_vintage_layer"]["records"]
    )
    assert any(view["view_type"] == "capital_macro_context_view" for view in analyst_memory["analyst_views"])

    artifacts = {
        "run_id": "unit-k5-dseries",
        "claim_evidence_ledger": {"claims": []},
        "typed_gap_ledger": {"gaps": []},
        "entity_security_master": entity_master,
        **provenance_vintage,
        "reconciliation_ledger": {"candidates": [], "reconciliation_groups": [], "conflict_gaps": []},
        "metric_product_ontology_snapshot": {"metrics": [], "alias_index": {}, "observed_metric_mappings": []},
        "source_capability_router": {"source_capabilities": [], "route_decisions": []},
        "gate_registry_eval_matrix": {"gate_registry": [], "gate_history": [], "eval_matrix": []},
        "derived_metric_layer": {"formula_registry": [], "derived_metrics": []},
        "analyst_view_research_memory": analyst_memory,
    }
    db_path = tmp_path / "capital_macro_d_series.sqlite"
    report = materialize_d_series_governance_store(db_path, artifacts)
    counts = read_d_series_governance_counts(db_path, run_id="unit-k5-dseries")
    context = read_d_series_research_context(db_path, tickers=["A"], run_id="unit-k5-dseries", limit=20)

    assert report["layers"]["raw_source_provenance_store"]["parity_status"] == "pass"
    assert report["layers"]["asof_vintage_layer"]["parity_status"] == "pass"
    assert report["layers"]["analyst_view_research_memory"]["parity_status"] == "pass"
    assert counts["raw_source_documents"] == artifacts["raw_source_provenance_store"]["record_count"]
    assert counts["asof_vintage_records"] == artifacts["asof_vintage_layer"]["record_count"]
    assert context["contexts"]["source_provenance"]["raw_documents"]
    assert any(
        row["view_type"] == "capital_macro_context_view"
        for row in context["contexts"]["analyst_memory"]["views"]
    )


def _capital_macro_state() -> dict:
    return {
        "run_id": "unit-k5-dseries",
        "capital_macro_source_adapter": {
            "capital_ownership_rows": [
                {
                    "evidence_ref": "a-debt-2030",
                    "object_type": "DebtInstrument",
                    "source_family": "primary_sec_filing",
                    "source_id": "sec_annual_debt_footnote_chunk",
                    "company_id": "A",
                    "principal": "500",
                    "currency": "USD millions",
                    "maturity_date": "2030-06-04",
                    "coupon": "2.10%",
                    "interest_rate_type": "fixed",
                    "source_url": "https://www.sec.gov/Archives/edgar/data/1090872/a-20231031.htm",
                    "local_path": "data/raw_private/sec_tier1_sp500_annual/2023/health_care/A/10-K.html",
                    "accession_number": "0001090872-23-000020",
                    "filing_date": "2023-12-20",
                    "period_end": "2023-10-31",
                    "source_statement": "The 2030 senior notes will mature on June 4, 2030 and bear interest at 2.10%.",
                    "claim_scope": "company_disclosed_debt_context",
                },
                {
                    "evidence_ref": "13f-aapl",
                    "object_type": "OwnershipPosition",
                    "source_family": "public_source_context",
                    "source_id": "sec_ownership_and_13f",
                    "investor_id": "Example Capital LLC",
                    "company_id": "A",
                    "issuer_name": "Agilent Technologies Inc.",
                    "shares": "1000",
                    "value": "250",
                    "filing_date": "2026-05-15",
                    "report_period": "2026-03-31",
                    "lag_days": "45",
                    "not_realtime_flag": True,
                    "lag_policy": "sec_13f_lagged_long_position_context_not_realtime_flow",
                    "claim_scope": "lagged_ownership_context_only",
                },
            ],
            "macro_driver_rows": [
                {
                    "evidence_ref": "fred-fedfunds",
                    "object_type": "MacroDriver",
                    "source_family": "public_source_context",
                    "source_id": "fred_graph_csv",
                    "series_id": "FEDFUNDS",
                    "variable_name": "Federal funds effective rate",
                    "value": "4.33",
                    "date": "2026-05-01",
                    "frequency": "monthly",
                    "claim_scope": "macro_or_industry_context_only",
                }
            ],
            "macro_exposure_rows": [
                {
                    "evidence_ref": "a-fedfunds-exposure",
                    "object_type": "CompanyExposureToDriver",
                    "source_family": "public_source_context",
                    "source_id": "fred_graph_csv",
                    "company_id": "A",
                    "driver_id": "fred-fedfunds",
                    "exposure_type": "rate_cycle_context",
                    "claim_scope": "company_exposure_bridge_context_only",
                }
            ],
            "vertical_official_object_rows": [],
        },
    }
