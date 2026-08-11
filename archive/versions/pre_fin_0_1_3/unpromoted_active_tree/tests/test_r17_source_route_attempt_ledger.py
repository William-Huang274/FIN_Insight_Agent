from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "data_expansion"
    / "build_r17_source_route_attempt_ledger.py"
)
SPEC = importlib.util.spec_from_file_location("build_r17_source_route_attempt_ledger", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_retryable_fetch_failure_blocks_public_boundary() -> None:
    rows = MODULE.build_source_route_attempt_ledger_rows(
        exact_closeout_rows=[
            {
                "ticker": "2317.TW",
                "company_name": "Hon Hai",
                "requirement_id": "public_order_proxy",
                "closeout_class": "public_source_exhausted_gap",
                "closeout_reason": "tw_local_tender_no_supplier_bound_award_or_no_structured_award_endpoint",
                "attempt_count": 1,
                "sample_attempts": [{"provider": "tw_pcc_eprocurement", "status": "fetch_failed"}],
            }
        ],
        product_kpi_diagnostic_rows=[],
        generated_at="2026-06-22T00:00:00Z",
    )

    exact = next(row for row in rows if row["ledger_row_type"] == "source_role_exact_gap")
    assert exact["gate_status"] == "source_route_retry_required"
    assert exact["final_boundary_allowed"] is False


def test_attempt_backed_negative_public_boundary_is_allowed() -> None:
    rows = MODULE.build_source_route_attempt_ledger_rows(
        exact_closeout_rows=[
            {
                "ticker": "BYD",
                "company_name": "BYD",
                "requirement_id": "public_order_proxy",
                "closeout_class": "public_source_exhausted_gap",
                "closeout_reason": "local_tender_no_supplier_bound_award",
                "attempt_count": 1,
                "sample_attempts": [{"provider": "hk_open_data_contract_awards", "status": "no_bound_records"}],
            }
        ],
        product_kpi_diagnostic_rows=[],
        generated_at="2026-06-22T00:00:00Z",
    )

    exact = next(row for row in rows if row["ledger_row_type"] == "source_role_exact_gap")
    assert exact["gate_status"] == "attempt_backed_public_boundary"
    assert exact["final_boundary_allowed"] is True


def test_product_operating_metric_gap_requires_reroute_not_product_exact() -> None:
    rows = MODULE.build_source_route_attempt_ledger_rows(
        exact_closeout_rows=[],
        product_kpi_diagnostic_rows=[
            {
                "ticker": "MSFT",
                "company_name": "Microsoft",
                "product_kpi_status": "product_kpi_exact_gap",
                "diagnostic_class": "verifier_operating_metric_requires_industry_slot",
                "diagnostic_reason": "metric_family_backlog_or_orders_requires_industry_operating_metric_slot",
            }
        ],
        generated_at="2026-06-22T00:00:00Z",
    )

    product = next(
        row
        for row in rows
        if row["ledger_row_type"] == "product_kpi_gap_or_ready" and row["ticker"] == "MSFT"
    )
    assert product["gate_status"] == "reroute_required"
    assert product["debt_class"] == "industry_or_business_metric_reroute_debt"
    assert product["final_boundary_allowed"] is False


def test_known_public_deck_canary_fails_when_product_kpi_is_missing() -> None:
    rows = MODULE.build_source_route_attempt_ledger_rows(
        exact_closeout_rows=[],
        product_kpi_diagnostic_rows=[
            {
                "ticker": "DECK",
                "company_name": "Deckers",
                "product_kpi_status": "product_kpi_exact_gap",
                "diagnostic_class": "product_surface_or_taxonomy_available_no_company_kpi_candidate",
            }
        ],
        generated_at="2026-06-22T00:00:00Z",
    )

    deck = next(
        row
        for row in rows
        if row["ledger_row_type"] == "known_public_canary" and row["ticker"] == "DECK"
    )
    assert deck["gate_status"] == "current_contract_route_or_parser_failure"
    assert deck["final_boundary_allowed"] is False


def test_new_contract_canaries_are_actionable_without_becoming_evidence() -> None:
    rows = MODULE.build_source_route_attempt_ledger_rows(
        exact_closeout_rows=[],
        product_kpi_diagnostic_rows=[],
        generated_at="2026-06-22T00:00:00Z",
    )

    nvda_spec = next(
        row
        for row in rows
        if row["ledger_row_type"] == "known_public_canary"
        and row["ticker"] == "NVDA"
        and row["source_role"] == "technical_product_spec"
    )
    assert nvda_spec["gate_status"] == "new_contract_required"
    assert nvda_spec["claim_boundary"] == "Canary rows are control rows only; they do not become evidence or ClaimCards."


def test_new_contract_canaries_are_covered_by_r17_product_family_evidence_rows() -> None:
    evidence_rows = [
        {"ticker": "NVDA", "source_role": "technical_product_spec", "runtime_contract": "ProductSpecSlot"},
        {"ticker": "NVDA", "source_role": "customer_deployment_proxy", "runtime_contract": "CustomerDeploymentProxy"},
        {"ticker": "MSFT", "slot_id": "cloud_revenue", "metric_family": "cloud_revenue"},
        {"ticker": "ASML", "slot_id": "semicap_system_sales_units", "metric_family": "semicap_system_sales_units"},
        {"ticker": "8035.T", "slot_id": "semicap_field_solutions_sales", "metric_family": "semicap_field_solutions_sales"},
        {"ticker": "2317.TW", "source_role": "business_mix_operating_metric", "metric_family": "business_mix_rank"},
    ]
    rows = MODULE.build_source_route_attempt_ledger_rows(
        exact_closeout_rows=[],
        product_kpi_diagnostic_rows=[],
        product_family_evidence_rows=evidence_rows,
        generated_at="2026-06-22T00:00:00Z",
    )

    new_contract_canaries = [
        row
        for row in rows
        if row["ledger_row_type"] == "known_public_canary" and row["ticker"] != "DECK"
    ]
    assert {row["gate_status"] for row in new_contract_canaries} == {"canary_covered"}
    assert all(row["final_boundary_allowed"] is True for row in new_contract_canaries)


def test_summary_exposes_action_required_without_failing_unclassified_gate() -> None:
    rows = MODULE.build_source_route_attempt_ledger_rows(
        exact_closeout_rows=[],
        product_kpi_diagnostic_rows=[
            {
                "ticker": "DECK",
                "company_name": "Deckers",
                "product_kpi_status": "product_kpi_exact_gap",
                "diagnostic_class": "product_surface_or_taxonomy_available_no_company_kpi_candidate",
            }
        ],
        generated_at="2026-06-22T00:00:00Z",
    )
    summary = MODULE.build_summary(
        rows=rows,
        generated_at="2026-06-22T00:00:00Z",
        output_rows=Path("rows.jsonl"),
        output_report=Path("report.md"),
    )

    assert summary["status"] == "action_required"
    assert summary["unclassified_count"] == 0
    assert summary["known_public_current_contract_failure_count"] == 1
