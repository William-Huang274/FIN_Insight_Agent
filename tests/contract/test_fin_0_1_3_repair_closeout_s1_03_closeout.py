from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

from sec_agent.material_numeric_program import (
    canonical_digest,
    compile_material_numeric_program,
    load_material_numeric_policy,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = (
    REPO_ROOT
    / "configs/runtime/fin_ia_0_1_3_repair_closeout_material_numeric_program_v1_1.json"
)
DECISION_PATH = (
    REPO_ROOT
    / "configs/releases/fin_ia_0_1_3_repair_closeout_s1_01_freshness_reopen_s1_02_numeric_successor_and_s1_03_official_source_closeout_v1_0.json"
)
ACTIVE_PATH = (
    REPO_ROOT
    / "configs/releases/fin_ia_0_1_3_repair_closeout_s1_03_active_test_suite_successor_v1_0.json"
)
ORACLE_PATH = (
    REPO_ROOT
    / "tests/fixtures/fin_0_1_3/financial_semantic_truth_oracle_three_case_v2.json"
)


def _gold_row(
    *,
    fiscal_year: int,
    metric_family: str,
    value: int,
    period_role: str,
    period_start: str,
    period_end: str,
    filed: str,
) -> dict:
    return {
        "gold_row_id": f"dell_{fiscal_year}_{metric_family}_{period_role}",
        "ticker": "DELL",
        "metric_family": metric_family,
        "metric_name": metric_family,
        "value": str(value),
        "unit": "USD",
        "fiscal_year": str(fiscal_year),
        "fiscal_period": "FY",
        "period_role": period_role,
        "period_start": period_start,
        "period_end": period_end,
        "duration_days": "364" if period_role == "annual" else "",
        "source_filed_at": filed,
        "published_at": filed,
        "snapshot_at": "2026-08-06T00:00:00Z",
        "source_row_id": f"sec_financial_statement_metric:{fiscal_year}:{metric_family}",
        "source_url": "https://data.sec.gov/api/xbrl/companyfacts/CIK0001571996.json",
        "payload_json": json.dumps(
            {
                "issuer_id": "0001571996",
                "source_document_id": f"0001571996-{str(fiscal_year)[-2:]}-000001",
            }
        ),
    }


def _dell_year_rows(
    *, fiscal_year: int, start: str, end: str, filed: str, revenue: int
) -> list[dict]:
    annual_values = {
        "revenue": revenue,
        "gross_profit": revenue // 5,
        "operating_income": revenue // 10,
        "operating_cash_flow": revenue // 12,
        "capital_expenditure_proxy": revenue // 50,
    }
    rows = [
        _gold_row(
            fiscal_year=fiscal_year,
            metric_family=metric,
            value=value,
            period_role="annual",
            period_start=start,
            period_end=end,
            filed=filed,
        )
        for metric, value in annual_values.items()
    ]
    for metric, value in {
        "inventory": revenue // 11,
        "accounts_receivable": revenue // 10,
        "accounts_payable": revenue // 6,
    }.items():
        rows.append(
            _gold_row(
                fiscal_year=fiscal_year,
                metric_family=metric,
                value=value,
                period_role="instant",
                period_start="",
                period_end=end,
                filed=filed,
            )
        )
    return rows


def _comparative_rows() -> list[dict]:
    rows = []
    for concept, value in {
        "InventoryNet": 6_716_000_000,
        "AccountsReceivableNetCurrent": 10_298_000_000,
        "AccountsPayableCurrent": 20_832_000_000,
    }.items():
        rows.append(
            {
                "ticker": "DELL",
                "fiscal_year": 2026,
                "fiscal_period": "FY",
                "period_end": "2025-01-31",
                "filed_date": "2026-03-16",
                "form_type": "10-K",
                "value": value,
                "unit": "USD",
                "concept": concept,
                "label": concept,
                "accession_number": "0001571996-26-000001",
                "source_url": "https://data.sec.gov/api/xbrl/companyfacts/CIK0001571996.json",
                "fact_id": f"SECFACT::DELL::{concept}",
                "snapshot_at": "2026-08-06T00:00:00Z",
            }
        )
    return rows


def test_v11_selects_latest_annual_filed_by_as_of_and_excludes_future_filing() -> None:
    policy = load_material_numeric_policy(POLICY_PATH)
    rows = [
        *_dell_year_rows(
            fiscal_year=2025,
            start="2024-02-03",
            end="2025-01-31",
            filed="2025-03-25",
            revenue=95_567_000_000,
        ),
        *_dell_year_rows(
            fiscal_year=2026,
            start="2025-02-01",
            end="2026-01-30",
            filed="2026-03-16",
            revenue=113_538_000_000,
        ),
        *_dell_year_rows(
            fiscal_year=2027,
            start="2026-01-31",
            end="2027-01-29",
            filed="2027-03-15",
            revenue=999_000_000_000,
        ),
    ]
    program = compile_material_numeric_program(
        policy=policy,
        case_key="DELL",
        gold_rows=rows,
        comparative_staging_rows=_comparative_rows(),
    )
    revenue = next(row for row in program["base_facts"] if row["slot_id"] == "revenue")
    assert program["fiscal_year"] == 2026
    assert program["annual_selection"] == {
        "mode": "latest_available_annual_as_of",
        "selected_period_end": "2026-01-30",
        "selected_source_filed_at": "2026-03-16",
    }
    assert revenue["normalized_value"] == "113538000000"


def test_closeout_binds_current_truth_official_proof_and_honest_remaining_gaps() -> None:
    decision = json.loads(DECISION_PATH.read_text(encoding="utf-8"))
    digest = decision.pop("record_digest")
    assert digest == canonical_digest(decision)
    assert decision["effective_governed_surface"] == {
        "material_numeric_slots": 48,
        "source_resolved_exact_numeric": 2,
        "effective_exact_numeric_facts": 27,
        "deterministic_formulas": 16,
        "remaining_numeric_typed_gaps": 5,
        "official_semantic_evidence_slots": 9,
        "total_governed_numeric_plus_semantic_slots": 57,
        "ungoverned_slots": 0,
    }
    selected = {
        row["case_key"]: (row["fiscal_year"], row["revenue_normalized_value"])
        for row in decision["current_annual_truth"]
    }
    assert selected == {
        "DELL": (2026, "113538000000"),
        "MU": (2025, "37378000000"),
        "NVDA": (2026, "215938000000"),
    }
    resolved = {
        (row["case_key"], row["slot_id"]): row["numeric_fact"]["normalized_value"]
        for row in decision["material_numeric_successor"]["resolved_source_numeric_facts"]
    }
    assert resolved == {
        ("DELL", "dell_server_or_isg_revenue"): "24683000000",
        ("DELL", "dell_server_or_isg_profit"): "7111000000",
    }
    remaining = {
        (row["case_key"], row["slot_id"])
        for row in decision["material_numeric_successor"]["remaining_typed_gaps"]
    }
    assert remaining == {
        ("MU", "mu_hbm_revenue"),
        ("MU", "mu_hbm_profit"),
        ("MU", "mu_price_volume_mix"),
        ("NVDA", "nvda_data_center_product_revenue"),
        ("NVDA", "nvda_data_center_product_profit"),
    }
    assert all(
        row["source_exhaustion_proven"] is False
        for row in decision["official_source_proof"]["remaining_attempt_backed_typed_gaps"]
    )
    assert decision["stage_boundary"]["S1_04_graph"] == "next_not_started"
    assert decision["stage_boundary"]["model_or_full_chain"] is False


def test_current_oracle_and_active_suite_are_successor_bound() -> None:
    oracle = json.loads(ORACLE_PATH.read_text(encoding="utf-8"))
    expected = {
        row["case_key"]: (row["fiscal_year"], row["normalized_value"])
        for row in oracle["reviewed_truth_rows"]
    }
    assert expected == {
        "DELL": (2026, "113538000000"),
        "MU": (2025, "37378000000"),
        "NVDA": (2026, "215938000000"),
    }

    active = json.loads(ACTIVE_PATH.read_text(encoding="utf-8"))
    suite_digest = active.pop("suite_digest")
    assert suite_digest == canonical_digest(active)
    assert active["decision_sha256"] == hashlib.sha256(DECISION_PATH.read_bytes()).hexdigest()
    assert active["stage_boundary"]["S1_04"] == "next"
    assert active["stage_boundary"]["model_or_full_chain_authorized"] is False
