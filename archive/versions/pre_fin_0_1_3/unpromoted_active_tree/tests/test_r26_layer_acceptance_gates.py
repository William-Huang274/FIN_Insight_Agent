from __future__ import annotations

import json
from pathlib import Path

from sec_agent.layer_acceptance_gates import (
    R26_COMBINED_ACCEPTANCE_SCHEMA_VERSION,
    R26_SECOND_LAYER_ACCEPTANCE_SCHEMA_VERSION,
    R26_THIRD_LAYER_ACCEPTANCE_SCHEMA_VERSION,
    build_combined_layer_acceptance_gate,
    build_second_layer_acceptance_gate,
    build_third_layer_acceptance_gate,
    load_json,
    load_jsonl,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = REPO_ROOT / "data" / "manifests"


def test_r26_second_and_third_layer_acceptance_gates_pass_on_current_manifests() -> None:
    second = build_second_layer_acceptance_gate(
        product_graph_summary=load_json(MANIFEST_DIR / "product_relationship_graph_summary_v0_1.json"),
        product_slots=load_jsonl(MANIFEST_DIR / "company_product_slots_v0_1.jsonl"),
        product_graph_edges=load_jsonl(MANIFEST_DIR / "product_relationship_graph_edges_v0_1.jsonl"),
        product_kpi_diagnostic_summary=load_json(MANIFEST_DIR / "product_kpi_deep_gap_diagnostic_summary_v0_1.json"),
        product_kpi_closeout_rows=load_jsonl(MANIFEST_DIR / "product_kpi_exact_slot_closeout_v0_1.jsonl"),
        r17_product_family_evidence_rows=load_jsonl(MANIFEST_DIR / "r17_product_family_evidence_runtime_rows_v0_1.jsonl"),
        r17_product_family_evidence_summary=load_json(MANIFEST_DIR / "r17_product_family_evidence_summary_v0_1.json"),
    )
    third = build_third_layer_acceptance_gate(
        sec_financial_statement_summary=load_json(MANIFEST_DIR / "sec_financial_statement_metric_runtime_summary_v0_1.json"),
        non_us_l1_financial_summary=load_json(MANIFEST_DIR / "non_us_l1_financial_statement_metric_runtime_summary_v0_1.json"),
        capital_context_summary=load_json(MANIFEST_DIR / "capital_funding_ownership_context_summary_v0_1.json"),
        sec_capital_event_summary=load_json(MANIFEST_DIR / "sec_capital_market_event_context_summary_v0_1.json"),
        sec_capital_event_rows=load_jsonl(MANIFEST_DIR / "sec_capital_market_event_context_rows_v0_1.jsonl"),
        r18_registry_summary=load_json(MANIFEST_DIR / "r18_source_route_registry_v2_summary.json"),
        r18_authority_mart_summary=load_json(MANIFEST_DIR / "r18_source_authority_data_mart_summary_v0_1.json"),
    )
    combined = build_combined_layer_acceptance_gate(second_layer_gate=second, third_layer_gate=third)

    assert second["schema_version"] == R26_SECOND_LAYER_ACCEPTANCE_SCHEMA_VERSION
    assert third["schema_version"] == R26_THIRD_LAYER_ACCEPTANCE_SCHEMA_VERSION
    assert combined["schema_version"] == R26_COMBINED_ACCEPTANCE_SCHEMA_VERSION
    assert second["status"] == "pass", json.dumps(second["failures"], ensure_ascii=False)
    assert third["status"] == "pass", json.dumps(third["failures"], ensure_ascii=False)
    assert combined["status"] == "pass"
    assert second["metrics"]["relationship_coverage"]["competes_with"] > 0
    assert second["metrics"]["relationship_coverage"]["supplier_or_input_edge"] > 0
    assert second["metrics"]["r17_nonfinancial_boundary_violation_count"] == 0
    assert third["metrics"]["sec_financial_statement_ticker_count"] + third["metrics"]["non_us_l1_financial_covered_target_ticker_count"] >= 603
    assert third["metrics"]["sec_capital_event_exact_violation_count"] == 0


def test_r26_second_layer_rejects_nonfinancial_signal_promoted_to_exact_fact() -> None:
    graph_summary = {
        "status": "pass",
        "validation": {"status": "pass"},
        "with_family_bound_runtime_slot_count": 1,
        "with_url_slot_count": 1,
        "product_slot_count": 1,
    }
    second = build_second_layer_acceptance_gate(
        product_graph_summary=graph_summary,
        product_slots=[{"ticker": "NVDA", "slot_status": "official_surface_slot"}],
        product_graph_edges=[
            {"relationship_type": "COMPETES_WITH"},
            {"relationship_type": "COMPONENT_INPUT_TO"},
        ],
        product_kpi_diagnostic_summary={"unclassified_count": 0, "product_kpi_status_counts": {}},
        product_kpi_closeout_rows=[{"ticker": "NVDA", "status": "product_kpi_exact_ready"}],
        r17_product_family_evidence_rows=[
            {
                "evidence_ref": "bad-exact-product-spec",
                "source_role": "technical_product_spec",
                "exact_financial_fact_authority": True,
                "can_support_company_exact_fact": True,
                "forbidden_claims": ["product_revenue"],
            },
            {"source_role": "product_generation_edge", "forbidden_claims": ["product_revenue"]},
            {"source_role": "product_benchmark_proxy", "forbidden_claims": ["product_revenue"]},
            {"source_role": "customer_deployment_proxy", "forbidden_claims": ["product_revenue"]},
        ],
        r17_product_family_evidence_summary={"status": "pass"},
        company_count=1,
    )

    assert second["status"] == "fail"
    assert second["checks"]["nonfinancial_signal_boundary_preserved"] is False
