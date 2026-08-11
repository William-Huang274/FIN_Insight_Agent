from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_access_plan_module():
    path = REPO_ROOT / "scripts" / "data_expansion" / "build_public_source_access_plan.py"
    spec = importlib.util.spec_from_file_location("public_source_access_plan_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _load_probe_module():
    path = REPO_ROOT / "scripts" / "data_expansion" / "probe_public_source_access.py"
    spec = importlib.util.spec_from_file_location("public_source_probe_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_public_source_registry_validation_and_phase_classification(monkeypatch) -> None:
    module = _load_access_plan_module()
    registry = {
        "auth_status_definitions": {
            "no_key": "No key.",
            "free_key": "Free key.",
            "official_portal_pending": "Portal.",
            "commercial_deferred": "Commercial.",
        },
        "gap_type_definitions": {
            "none": "None.",
            "auth_gap": "Auth.",
            "endpoint_validation_gap": "Endpoint.",
            "commercial_deferred": "Commercial.",
        },
        "sources": [
            {
                "source_id": "sec_edgar_apis",
                "provider": "SEC",
                "official_url": "https://data.sec.gov",
                "auth_status": "no_key",
                "source_families": ["sec_primary_filing"],
                "claim_scope": "company_reported_financial_fact",
                "current_repo_status": "implemented_partial",
                "collector_status": "implemented",
                "parser_status": "implemented",
                "priority": "P0",
                "gap_type": "none",
                "boundary_notes": "SEC filings only.",
            },
            {
                "source_id": "eia_open_data",
                "provider": "EIA",
                "official_url": "https://api.eia.gov",
                "auth_status": "free_key",
                "env_var": "EIA_API_KEY",
                "source_families": ["macro_industry_indicator"],
                "claim_scope": "industry_context_only",
                "current_repo_status": "configured_requires_key",
                "collector_status": "configured_not_normalized",
                "parser_status": "not_started",
                "priority": "P2",
                "gap_type": "auth_gap",
                "boundary_notes": "Context only.",
            },
            {
                "source_id": "hkexnews_portal",
                "provider": "HKEX",
                "official_url": "https://www.hkexnews.hk",
                "auth_status": "official_portal_pending",
                "source_families": ["global_public_annual_report"],
                "claim_scope": "primary_company_disclosure",
                "current_repo_status": "planned",
                "collector_status": "not_started",
                "parser_status": "not_started",
                "priority": "P3",
                "gap_type": "endpoint_validation_gap",
                "boundary_notes": "Validate portal.",
            },
            {
                "source_id": "commercial_market_data_and_consensus",
                "provider": "Vendor",
                "official_url": "vendor_specific",
                "auth_status": "commercial_deferred",
                "source_families": ["market_price_snapshot"],
                "claim_scope": "commercial_deferred",
                "current_repo_status": "deferred",
                "collector_status": "not_applicable",
                "parser_status": "not_applicable",
                "priority": "deferred",
                "gap_type": "commercial_deferred",
                "boundary_notes": "Deferred.",
            },
        ],
    }
    source_families = {
        "sec_primary_filing": {},
        "macro_industry_indicator": {},
        "global_public_annual_report": {},
        "market_price_snapshot": {},
    }
    monkeypatch.delenv("EIA_API_KEY", raising=False)

    validation = module.validate_registry(registry=registry, source_families=source_families)
    rows = module.build_access_plan_rows(registry)
    by_source = {row["source_id"]: row for row in rows}
    portal_tasks = module.build_portal_validation_tasks(rows)

    assert validation["error_count"] == 0
    assert by_source["sec_edgar_apis"]["phase"] == "P1"
    assert by_source["sec_edgar_apis"]["live_probe_supported"] is True
    assert by_source["eia_open_data"]["phase"] == "P2"
    assert by_source["eia_open_data"]["action_status"] == "key_missing"
    assert by_source["hkexnews_portal"]["phase"] == "P3"
    assert by_source["commercial_market_data_and_consensus"]["phase"] == "deferred"
    assert portal_tasks[0]["source_id"] == "hkexnews_portal"


def test_public_source_access_plan_cli_writes_outputs(tmp_path: Path) -> None:
    coverage = tmp_path / "coverage.yaml"
    families = tmp_path / "families.yaml"
    output = tmp_path / "plan.jsonl"
    summary = tmp_path / "summary.json"
    portal_tasks = tmp_path / "portal.jsonl"
    coverage.write_text(
        """
auth_status_definitions:
  no_key: No key
gap_type_definitions:
  none: None
sources:
  - source_id: fred_graph_csv
    provider: FRED
    official_url: https://fred.stlouisfed.org/graph/fredgraph.csv
    auth_status: no_key
    source_families: [macro_industry_indicator]
    claim_scope: industry_context_only
    current_repo_status: configured
    collector_status: implemented_partial
    parser_status: implemented_partial
    priority: P1
    gap_type: none
    boundary_notes: Context only.
""".strip()
        + "\n",
        encoding="utf-8",
    )
    families.write_text(
        """
source_families:
  macro_industry_indicator: {}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            "python",
            "scripts/data_expansion/build_public_source_access_plan.py",
            "--coverage-registry",
            str(coverage),
            "--source-families",
            str(families),
            "--output",
            str(output),
            "--summary-output",
            str(summary),
            "--portal-tasks-output",
            str(portal_tasks),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(result.stdout)
    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]

    assert payload["status"] == "pass"
    assert payload["phase_counts"] == {"P1": 1}
    assert rows[0]["source_id"] == "fred_graph_csv"
    assert rows[0]["action_status"] == "ready_for_live_probe"


def test_public_source_probe_parsers_and_skip_live() -> None:
    module = _load_probe_module()
    fred = module.parse_fred_csv(b"observation_date,FEDFUNDS\n2026-01-01,4.33\n")
    fdic = module.parse_fdic_payload(b'{"data":[{"data":{"NAME":"Test Bank","CERT":"1"}}]}')
    sec = module.parse_sec_submissions_payload(
        b'{"name":"Apple Inc.","cik":"0000320193","filings":{"recent":{"form":["10-K","10-Q"]}}}'
    )

    assert fred["normalized_row_count"] == 1
    assert fred["latest_value"] == "4.33"
    assert fdic["normalized_row_count"] == 1
    assert "CERT" in fdic["sample_fields"]
    assert sec["normalized_row_count"] == 2
    assert sec["sample_company_name"] == "Apple Inc."

    row = {
        "source_id": "fred_graph_csv",
        "provider": "FRED",
        "phase": "P1",
        "auth_status": "no_key",
        "claim_scope": "industry_context_only",
        "boundary_notes": "Context only.",
    }
    skipped = module.probe_source(row, timeout_s=1, skip_live=True)
    assert skipped["probe_status"] == "skipped_live"
    assert "FEDFUNDS" in skipped["probe_url"]


def test_public_source_probe_redacts_query_key_on_skip_live(monkeypatch) -> None:
    module = _load_probe_module()
    monkeypatch.setenv("FRED_API_KEY", "unit-test-secret")
    row = {
        "source_id": "fred_api",
        "provider": "FRED",
        "phase": "P2",
        "auth_status": "free_key",
        "claim_scope": "industry_context_only",
        "boundary_notes": "Context only.",
    }

    skipped = module.probe_source(row, timeout_s=1, skip_live=True)

    assert skipped["probe_status"] == "skipped_live"
    assert skipped["env_present"] is True
    assert "unit-test-secret" not in skipped["probe_url"]
    assert "api_key=REDACTED" in skipped["probe_url"]
