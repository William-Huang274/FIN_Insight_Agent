from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "data_expansion" / "build_l3_minimum_coverage_gate.py"
SPEC = importlib.util.spec_from_file_location("build_l3_minimum_coverage_gate", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_l3_minimum_coverage_gate_flags_zero_and_priority_single_role() -> None:
    coverage_rows = [
        {
            "ticker": "ZERO",
            "company_name": "Zero Corp",
            "primary_lane_id": "V7",
            "industry_schema": "energy_utilities",
            "exact_slot_layers": {"L1": 1},
            "source_role_exact_slot_matrix": [
                {
                    "requirement_id": "hiring_capacity_proxy",
                    "target_layer_ids": ["L3"],
                    "status": "exact_slot_gap",
                    "gap_class": "source_gap",
                    "source_gate_gap_type": "company_specific_runtime_row_missing",
                }
            ],
        },
        {
            "ticker": "ONE",
            "company_name": "One Corp",
            "primary_lane_id": "V3",
            "industry_schema": "software_saas",
            "exact_slot_layers": {"L3": 2},
            "source_role_exact_slot_matrix": [
                {
                    "requirement_id": "app_rank_store_proxy",
                    "target_layer_ids": ["L3"],
                    "status": "exact_slot_ready",
                    "exact_slot_count": 2,
                }
            ],
        },
    ]

    summary, low_rows = MODULE.build_l3_minimum_coverage_gate(
        coverage_rows=coverage_rows,
        priority_tickers={"ONE"},
        generated_at="2026-06-19T00:00:00Z",
        min_l3_rows=1,
        priority_min_independent_roles=2,
    )

    assert summary["status"] == "gap"
    assert summary["l3_zero_company_count"] == 1
    assert summary["priority_fail_company_count"] == 1
    by_ticker = {row["ticker"]: row for row in low_rows}
    assert by_ticker["ZERO"]["failed_base_min_l3"] is True
    assert by_ticker["ONE"]["failed_priority_independent_roles"] is True


def test_l3_minimum_coverage_gate_counts_l2_l3_independent_roles_for_priority() -> None:
    coverage_rows = [
        {
            "ticker": "DEEP",
            "company_name": "Deep Corp",
            "primary_lane_id": "V8",
            "industry_schema": "retail_cpg",
            "exact_slot_layers": {"L3": 2},
            "source_role_exact_slot_matrix": [
                {
                    "requirement_id": "platform_review_proxy",
                    "target_layer_ids": ["L3"],
                    "status": "exact_slot_ready",
                    "exact_slot_count": 2,
                },
                {
                    "requirement_id": "trusted_external_context",
                    "target_layer_ids": ["L2"],
                    "status": "exact_slot_ready",
                    "exact_slot_count": 1,
                },
            ],
        }
    ]

    summary, low_rows = MODULE.build_l3_minimum_coverage_gate(
        coverage_rows=coverage_rows,
        priority_tickers={"DEEP"},
        generated_at="2026-06-19T00:00:00Z",
        min_l3_rows=1,
        priority_min_independent_roles=2,
    )

    assert summary["status"] == "pass"
    assert summary["priority_fail_company_count"] == 0
    assert low_rows == []
