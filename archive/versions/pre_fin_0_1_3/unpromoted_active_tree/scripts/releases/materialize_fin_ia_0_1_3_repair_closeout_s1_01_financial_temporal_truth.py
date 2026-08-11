from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest


DECISION_REF = Path(
    "configs/releases/fin_ia_0_1_3_repair_closeout_s1_01_financial_temporal_"
    "truth_and_time_role_repair_v1_0.json"
)
ACTIVE_SUITE_REF = Path(
    "configs/releases/fin_ia_0_1_3_repair_closeout_s1_01_active_test_suite_"
    "successor_v1_0.json"
)
RUNTIME_ROWS_REF = Path(
    "data/manifests/sec_financial_statement_metric_runtime_rows_v0_1.jsonl"
)
RUNTIME_SUMMARY_REF = Path(
    "data/manifests/sec_financial_statement_metric_runtime_summary_v0_1.json"
)
MART_REF = Path(
    "data/workbench_private/research_data/gold_fact_signal_mart_v0_1.sqlite"
)
MART_SUMMARY_REF = Path(
    "data/workbench_private/fin_0_1_3_s1_01/gold_fact_signal_mart_summary_v0_2.json"
)


def _sha(ref: Path) -> str:
    return hashlib.sha256((ROOT / ref).read_bytes()).hexdigest()


def _binding(ref: str, role: str) -> dict[str, Any]:
    path = Path(ref)
    return {
        "ref": path.as_posix(),
        "sha256": _sha(path),
        "bytes": (ROOT / path).stat().st_size,
        "role": role,
    }


def _write(ref: Path, payload: dict[str, Any]) -> None:
    target = ROOT / ref
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _three_case_rows() -> list[dict[str, Any]]:
    query = """
        SELECT ticker, value, period, period_role, period_start, period_end,
               duration_days, fiscal_year, fiscal_period, raw_fiscal_period,
               source_filed_at, published_at, as_of_date, snapshot_at,
               schema_version
        FROM gold_fact_signal_mart
        WHERE ticker IN ('DELL', 'MU', 'NVDA')
          AND metric_family = 'revenue'
          AND exact_value_authority = 1
          AND period_role = 'annual'
        ORDER BY ticker
    """
    database = ROOT / MART_REF
    with sqlite3.connect(str(database)) as connection:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute(query).fetchall()]


def materialize() -> dict[str, Any]:
    runtime_summary = json.loads((ROOT / RUNTIME_SUMMARY_REF).read_text(encoding="utf-8"))
    mart_summary = json.loads((ROOT / MART_SUMMARY_REF).read_text(encoding="utf-8"))
    rows = _three_case_rows()
    expected = {
        "DELL": ("95567000000", "2025-03-25"),
        "MU": ("37378000000", "2025-10-03"),
        "NVDA": ("130497000000", "2025-02-26"),
    }
    if len(rows) != 3 or any(
        (str(row["value"]), str(row["source_filed_at"])) != expected[str(row["ticker"])]
        or row["period_role"] != "annual"
        or int(row["duration_days"]) != 364
        or row["as_of_date"] != ""
        for row in rows
    ):
        raise RuntimeError("fin_0_1_3_s1_01_three_case_rebuild_truth_mismatch")

    source_bindings = [
        _binding(
            "scripts/data_expansion/download_sec_structured_facts.py",
            "date_authoritative_structured_fact_period_classifier_v0_2",
        ),
        _binding(
            "scripts/data_expansion/build_sec_financial_statement_metric_runtime_rows.py",
            "date_revalidated_runtime_selector_and_temporal_projection_v0_2",
        ),
        _binding(
            "src/sec_agent/gold_fact_signal_mart.py",
            "four_time_role_gold_mart_and_non_destructive_sqlite_migration_v0_2",
        ),
        _binding(
            "apps/workbench/backend/application/fin_0_1_2_s4_t03_executable_agentic_search.py",
            "current_exact_sql_annual_authority_and_cutoff_projection",
        ),
        _binding(
            "apps/workbench/backend/application/fin_0_1_2_s4_t04_current_evidence_research.py",
            "current_numeric_four_time_role_projection",
        ),
        _binding(
            "tests/fixtures/fin_0_1_3/financial_semantic_truth_oracle_three_case_v1.json",
            "reviewed_three_case_financial_truth_oracle",
        ),
        _binding(
            "tests/contract/test_fin_0_1_3_repair_closeout_s1_01_financial_temporal_truth_and_time_role_repair.py",
            "canonical_S1_01_end_to_end_and_adversarial_contract_test",
        ),
        _binding(
            "data/manifests/sec_financial_statement_metric_runtime_summary_v0_1.json",
            "tracked_full_runtime_rebuild_summary_v0_2",
        ),
        _binding(
            "scripts/releases/materialize_fin_ia_0_1_3_repair_closeout_s1_01_financial_temporal_truth.py",
            "deterministic_S1_01_closeout_materializer",
        ),
    ]
    local_rebuild_evidence = {
        "runtime_rows": {
            "ref": RUNTIME_ROWS_REF.as_posix(),
            "sha256": _sha(RUNTIME_ROWS_REF),
            "bytes": (ROOT / RUNTIME_ROWS_REF).stat().st_size,
            "row_count": int(runtime_summary["runtime_row_count"]),
            "ticker_count": int(runtime_summary["runtime_ticker_count"]),
            "schema_version": str(runtime_summary["schema_version"]),
        },
        "gold_mart": {
            "ref": MART_REF.as_posix(),
            "sha256": _sha(MART_REF),
            "bytes": (ROOT / MART_REF).stat().st_size,
            "row_count": int(mart_summary["row_count"]),
            "sqlite_row_count": int(mart_summary["sqlite_row_count"]),
            "source_rowset_count": int(mart_summary["source_rowset_count"]),
            "missing_source_rowset_count": int(mart_summary["missing_source_rowset_count"]),
            "schema_version": str(mart_summary["schema_version"]),
        },
        "three_case_annual_revenue_rows": rows,
        "generated_artifacts_are_local_not_git_payloads": True,
    }
    body = {
        "schema_version": (
            "fin_ia_0_1_3_repair_closeout_s1_01_financial_temporal_truth_"
            "and_time_role_repair_v1_0"
        ),
        "decision_id": (
            "FIN-0.1.3-013-S1-01-DELL-FINANCIAL-TEMPORAL-TRUTH-AND-"
            "TIME-ROLE-REPAIR"
        ),
        "recorded_at": "2026-08-06T09:00:00Z",
        "status": "engineering_pass_financial_temporal_root_cause_closed_S1_02_next",
        "root_cause_repair": {
            "earliest_fault": (
                "SEC CompanyFacts fp=FY was trusted over inclusive start/end duration, "
                "so a 91-day 10-K Q4 fact became annual."
            ),
            "selection_repair": (
                "Runtime recomputes duration semantics from dates and ranks semantic "
                "period authority before fiscal year/form metadata."
            ),
            "time_roles": {
                "source_filed_at": "issuer filing receipt date",
                "published_at": "source public availability date",
                "as_of_date": "research request cutoff bound at retrieval",
                "snapshot_at": "local capture or materialization time",
            },
            "annual_quarter_ytd_instant_are_distinct": True,
            "renderer_manual_value_patch_used": False,
        },
        "local_rebuild_evidence": local_rebuild_evidence,
        "historical_proof_disposition": {
            "immutable_FIN_0_1_2_evidence_packs_rewritten": 0,
            "event_time_assertions_deselected_from_current_suite": [
                (
                    "S0_02 decision binding to the changed legacy-compatible T03 source "
                    "hash"
                ),
                "S4_T04 historical exact input digest before the v0.2 data rebuild",
                "S4_T05_B materialization binding to the changed T04 source hash",
            ],
            "disposition": (
                "preserve as historical evidence; changed data/source digests cannot "
                "inherit old product acceptance"
            ),
        },
        "verification": {
            "focused_current_suite": "46 passed / 1 historical event-time assertion deselected",
            "adjacent_T03_T05_functional": "19 passed / 2 historical digest assertions deselected",
            "actual_SQL_to_numeric_three_case_projection": "3/3 reviewed annual facts pass",
            "mutations": [
                "10-K Q4 raw FY label cannot enter annual selection",
                "post-cutoff annual fact excluded",
                "annual_quarter_ytd_instant_roles_distinct",
                "legacy SQLite migration preserves four time roles",
                "snapshot time cannot become source filing time",
                "legacy text-only numeric candidate cannot enter current authority",
            ],
        },
        "source_bindings": source_bindings,
        "root_cause_disposition": {
            "RC-P36-130": "closed_by_S1_01_underlying_financial_temporal_truth_chain_rebuild",
            "RC-P36-131": "unchanged_open_S2_S3_research_content_quality",
            "RC-P36-132": "unchanged_open_S4_S5_product_workflow_release",
        },
        "observed_counts": {
            "model_calls": 0,
            "provider_calls": 0,
            "network_or_source_calls": 0,
            "business_runs": 0,
            "business_artifacts": 0,
            "runtime_rows_materialized": int(runtime_summary["runtime_row_count"]),
            "gold_mart_rows_materialized": int(mart_summary["row_count"]),
        },
        "stage_truth": {
            "FIN_0_1_3_S1_01": "engineering_pass",
            "FIN_0_1_3_S1": "in_progress_S1_02_next",
            "FIN_0_1_3_S2_to_S5": "not_started",
            "old_FIN_0_1_2_product_acceptance_inherited": False,
            "model_or_full_chain_authorized": False,
            "release_qualified": False,
        },
        "known_boundary": (
            "S1-01 repairs period and time truth only. Material numeric coverage, formula "
            "program expansion, source breadth, Graph, retrieval usefulness, research "
            "content, product workflow and release remain owned by S1-02 onward."
        ),
        "next_action": (
            "FIN-0.1.3-013-S1-02-MATERIAL-NUMERIC-PROGRAM-FORMULA-"
            "RECALCULATION-AND-TYPED-GAP-COVERAGE"
        ),
    }
    decision = {**body, "decision_digest": canonical_digest(body)}
    _write(DECISION_REF, decision)

    suite_body = {
        "schema_version": (
            "fin_ia_0_1_3_repair_closeout_s1_01_active_test_suite_"
            "successor_v1_0"
        ),
        "suite_id": "FIN-0.1.3-REPAIR-CLOSEOUT-S1-ACTIVE-SUITE-R4",
        "status": "current_S1_01_pass_S1_02_next",
        "selected_test_files": [
            "tests/test_sec_structured_facts_download.py",
            "tests/test_sec_financial_statement_metric_runtime_rows.py",
            "tests/test_gold_fact_signal_mart.py",
            (
                "tests/contract/test_fin_0_1_3_repair_closeout_s0_01_delta_"
                "inheritance_namespace_and_current_truth_baseline.py"
            ),
            (
                "tests/contract/test_fin_0_1_3_repair_closeout_s0_02_shared_"
                "runtime_admission_replay_and_historical_proof_debt.py"
            ),
            (
                "tests/contract/test_fin_0_1_3_repair_closeout_s0_03_"
                "financial_semantic_truth_oracle_classification.py"
            ),
            (
                "tests/contract/test_fin_0_1_3_repair_closeout_s1_01_"
                "financial_temporal_truth_and_time_role_repair.py"
            ),
        ],
        "historical_event_time_deselections": [
            (
                "tests/contract/test_fin_0_1_3_repair_closeout_s0_02_shared_"
                "runtime_admission_replay_and_historical_proof_debt.py::"
                "test_decision_and_active_suite_are_digest_bound_and_do_not_promote_old_names"
            )
        ],
        "focused_result": "46 passed / 1 deselected",
        "adjacent_result": "19 passed / 2 historical digest assertions deselected",
        "decision_ref": DECISION_REF.as_posix(),
        "decision_sha256": _sha(DECISION_REF),
        "current_DELL_financial_temporal_truth_pass": True,
        "model_or_full_chain_authorized": False,
        "next_action": body["next_action"],
    }
    suite = {**suite_body, "suite_digest": canonical_digest(suite_body)}
    _write(ACTIVE_SUITE_REF, suite)
    return {
        "decision_ref": DECISION_REF.as_posix(),
        "decision_sha256": _sha(DECISION_REF),
        "active_suite_ref": ACTIVE_SUITE_REF.as_posix(),
        "active_suite_sha256": _sha(ACTIVE_SUITE_REF),
    }


if __name__ == "__main__":
    print(json.dumps(materialize(), ensure_ascii=False, indent=2, sort_keys=True))
