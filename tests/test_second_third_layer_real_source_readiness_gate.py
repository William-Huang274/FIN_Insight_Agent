from __future__ import annotations

import json
from pathlib import Path

from sec_agent.layer_acceptance_gates import (
    SECOND_THIRD_LAYER_REAL_SOURCE_READINESS_SCHEMA_VERSION,
    build_second_third_layer_real_source_readiness_gate,
    load_jsonl,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = REPO_ROOT / "data" / "manifests"


def test_second_third_layer_real_source_readiness_gate_passes_on_current_parser_rows() -> None:
    payload = build_second_third_layer_real_source_readiness_gate(
        company_universe_rows=load_jsonl(MANIFEST_DIR / "company_product_slots_v0_1.jsonl"),
        second_layer_rows=_load_rows(
            [
                "sec_product_taxonomy_context_rows_v0_1.jsonl",
                "official_product_surface_context_rows_v0_1.jsonl",
                "official_product_catalog_context_rows_v0_1.jsonl",
                "company_reported_product_operating_metric_runtime_rows_v0_1.jsonl",
                "non_us_product_kpi_local_disclosure_runtime_rows_v0_1.jsonl",
                "r16_product_kpi_deep_repair_runtime_rows_v0_1.jsonl",
                "r17_product_family_evidence_runtime_rows_v0_1.jsonl",
                "targeted_official_technology_document_context_rows_v0_1.jsonl",
            ]
        ),
        third_layer_rows=_load_rows(
            [
                "sec_financial_statement_metric_runtime_rows_v0_1.jsonl",
                "non_us_l1_financial_statement_metric_runtime_rows_v0_1.jsonl",
                "capital_funding_ownership_context_rows_v0_1.jsonl",
                "sec_capital_market_event_context_rows_v0_1.jsonl",
            ]
        ),
    )

    assert payload["schema_version"] == SECOND_THIRD_LAYER_REAL_SOURCE_READINESS_SCHEMA_VERSION
    assert payload["status"] == "pass", json.dumps(payload["failures"], ensure_ascii=False)
    assert payload["metrics"]["pass_company_count"] == 603
    assert payload["metrics"]["second_layer_actual_source_company_count"] == 603
    assert payload["metrics"]["third_layer_actual_source_company_count"] == 603
    assert payload["metrics"]["third_layer_exact_financial_basis_company_count"] == 603


def test_real_source_gate_rejects_planning_only_product_slots() -> None:
    payload = build_second_third_layer_real_source_readiness_gate(
        company_universe_rows=[{"ticker": "NVDA"}],
        second_layer_rows=[
            {
                "_source_file": "company_product_slots_v0_1.jsonl",
                "ticker": "NVDA",
                "evidence_ref": "slot-only",
                "sample_urls": ["https://example.com/product"],
                "claim_boundary": "slot assignment only",
            }
        ],
        third_layer_rows=[
            {
                "_source_file": "sec_financial_statement_metric_runtime_rows_v0_1.jsonl",
                "ticker": "NVDA",
                "evidence_ref": "nvda-financial",
                "parser_status": "value_unit_period_product_citation_parser_pass",
                "source_url": "https://data.sec.gov/api/xbrl/companyfacts/CIK0001045810.json",
                "claim_boundary": "financial statement fact",
                "exact_value_authority": True,
            }
        ],
        company_count=1,
    )

    assert payload["status"] == "fail"
    assert payload["metrics"]["second_layer_actual_source_company_count"] == 0
    assert payload["company_rows"][0]["checks"]["second_layer_actual_parser_source_present"] is False


def _load_rows(names: list[str]) -> list[dict]:
    rows: list[dict] = []
    for name in names:
        path = MANIFEST_DIR / name
        if not path.exists():
            continue
        for row in load_jsonl(path):
            clean = dict(row)
            clean["_source_file"] = name
            rows.append(clean)
    return rows
