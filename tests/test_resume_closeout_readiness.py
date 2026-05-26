from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_module():
    path = REPO_ROOT / "scripts" / "evaluate_sec_agent_resume_closeout_readiness.py"
    spec = importlib.util.spec_from_file_location("resume_closeout_readiness_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


closeout = _load_module()


def _load_market_smoke_module():
    path = REPO_ROOT / "scripts" / "market" / "60_smoke_market_snapshot_main_chain.py"
    spec = importlib.util.spec_from_file_location("market_main_chain_smoke_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_manifest_summary_counts_forms_and_periods(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    rows = [
        {"ticker": "NVDA", "fiscal_year": 2025, "form_type": "10-K", "source_tier": "primary_sec_filing", "period_type": "annual"},
        {"ticker": "NVDA", "fiscal_year": 2026, "form_type": "10-Q", "source_tier": "primary_sec_filing", "fiscal_period": "Q1"},
        {
            "ticker": "NVDA",
            "fiscal_year": 2026,
            "form_type": "8-K",
            "source_tier": "company_authored_unaudited_sec_filing",
            "period_type": "current",
        },
    ]
    _write_jsonl(manifest, rows)

    summary = closeout._manifest_summary(manifest)

    assert summary["exists"] is True
    assert summary["row_count"] == 3
    assert summary["ticker_count"] == 1
    assert summary["years"] == [2025, 2026]
    assert summary["form_counts"] == {"10-K": 1, "10-Q": 1, "8-K": 1}
    assert summary["source_tier_counts"]["primary_sec_filing"] == 2


def test_market_evidence_summary_tracks_fields_and_valuation(tmp_path: Path) -> None:
    evidence = tmp_path / "market.jsonl"
    _write_jsonl(
        evidence,
        [
            {
                "ticker": "NVDA",
                "snapshot_id": "snap_v1",
                "as_of_date": "2026-05-22",
                "provider": "fixture",
                "field_refs": [
                    {"field_name": "return_3m", "value": 0.2},
                    {"field_name": "pe_ttm", "value": 42.0},
                    {"field_name": "ev_sales_ttm", "value": None},
                ],
            },
            {
                "ticker": "AMD",
                "snapshot_id": "snap_v1",
                "as_of_date": "2026-05-22",
                "provider": "fixture",
                "field_refs": [{"field_name": "return_3m", "value": -0.1}],
            },
        ],
    )

    summary = closeout._market_evidence_summary(evidence)

    assert summary["exists"] is True
    assert summary["row_count"] == 2
    assert summary["ticker_count"] == 2
    assert summary["snapshot_ids"] == {"snap_v1": 2}
    assert summary["field_counts"]["return_3m"] == 2
    assert summary["field_counts"]["pe_ttm"] == 1
    assert summary["valuation_non_null_counts"] == {"pe_ttm": 1}


def test_saved_full_source_run_passes_when_required_artifacts_are_green(tmp_path: Path) -> None:
    run_dir = _write_saved_run(tmp_path, gate_fail=False, fallback=False)

    result = closeout._inspect_saved_full_source_run(run_dir)

    assert result["status"] == "pass"
    assert result["gate_fail_keys"] == []
    assert result["fallback_answer_count"] == 0
    assert result["market_context_row_count"] == 1
    assert result["rendered_boundary_labels"]["mentions_market_snapshot"] is True


def test_saved_full_source_run_fails_on_gate_or_fallback(tmp_path: Path) -> None:
    gate_fail_dir = _write_saved_run(tmp_path / "gate_fail", gate_fail=True, fallback=False)
    fallback_dir = _write_saved_run(tmp_path / "fallback", gate_fail=False, fallback=True)

    gate_fail = closeout._inspect_saved_full_source_run(gate_fail_dir)
    fallback = closeout._inspect_saved_full_source_run(fallback_dir)

    assert gate_fail["status"] == "fail"
    assert gate_fail["gate_fail_keys"] == ["v2_semantic_contract_gate_pass"]
    assert fallback["status"] == "fail"
    assert fallback["fallback_answer_count"] == 1


def test_aggregate_warns_on_optional_skips_but_fails_on_critical_failures() -> None:
    warn = closeout._aggregate_checks(
        [
            {"check_id": "critical_green", "dimension": "a", "critical": True, "status": "pass"},
            {"check_id": "optional_skip", "dimension": "b", "critical": False, "status": "skipped"},
        ]
    )
    fail = closeout._aggregate_checks(
        [
            {"check_id": "critical_red", "dimension": "a", "critical": True, "status": "fail", "reason": "bad"},
            {"check_id": "optional_green", "dimension": "b", "critical": False, "status": "pass"},
        ]
    )

    assert warn["overall_status"] == "warn"
    assert warn["blocker_fail_count"] == 0
    assert fail["overall_status"] == "fail"
    assert fail["blocker_fail_count"] == 1


def test_p0_readiness_tracks_latency_load_and_saved_run_status() -> None:
    result = closeout._p0_readiness(
        [
            {"check_id": "latency_profile_local", "status": "pass"},
            {"check_id": "context_api_small_pressure_local", "status": "pass"},
            {"check_id": "context_state_replay", "status": "pass"},
            {"check_id": "context_managed_dispatch_replay", "status": "pass"},
            {"check_id": "main_chain_case_suite_local", "status": "pass"},
            {
                "check_id": "source_inventory_artifacts",
                "status": "warn",
                "missing_full_source_paths": ["full_source_manifest"],
            },
            {
                "check_id": "saved_full_source_deepseek_run",
                "status": "pass",
                "state": {"stage_statuses": {"retrieve_context": "completed"}},
            },
        ]
    )

    assert result["overall_status"] == "warn"
    by_id = {item["item_id"]: item for item in result["items"]}
    assert by_id["p0_performance_resource"]["status"] == "pass"
    assert by_id["p0_stage_timing_observability"]["status"] == "pass"
    assert by_id["p0_data_index_versioning"]["status"] == "warn"


def test_main_chain_smoke_passes_sec_only_negative_control_without_market_rows(tmp_path: Path) -> None:
    market_smoke = _load_market_smoke_module()

    summary = market_smoke._summary(
        run_root=tmp_path,
        query_contract={"source_policy": "SEC_PRIMARY_MIXED_RECENT", "source_tiers": ["primary_sec_filing"]},
        context_rows=[{"source_tier": "primary_sec_filing"}],
        ledger_rows=[{"metric_id": "m1"}],
        coverage_matrix={"summary": {"coverage_complete": True, "primary_task_support_complete": True}},
        judgment_plan={"plans": []},
        elapsed_sec=1.25,
    )

    assert summary["status"] == "pass"
    assert summary["market_requested"] is False
    assert summary["market_context_row_count"] == 0


def _write_saved_run(root: Path, *, gate_fail: bool, fallback: bool) -> Path:
    run_dir = root / "run" if root.name != "run" else root
    (run_dir / "qwen").mkdir(parents=True, exist_ok=True)
    (run_dir / "post_gates").mkdir(parents=True, exist_ok=True)
    _write_json(
        run_dir / "sec_agent_state.json",
        {
            "run_id": "fixture_run",
            "status": "completed",
            "source_policy": "SEC_PRIMARY_MIXED_WITH_8K_AND_MARKET_SNAPSHOT",
            "selected_tickers": ["NVDA", "AMD"],
            "selected_years": [2023, 2024, 2025, 2026, 2027],
            "metadata": {"total_elapsed_sec": 123.4},
            "stages": [{"name": "render_answer", "status": "completed"}],
        },
    )
    _write_json(
        run_dir / "runtime_evidence_coverage_matrix.json",
        {
            "summary": {"coverage_complete": True, "primary_task_support_complete": True, "context_row_count": 10, "ledger_row_count": 4},
            "market_snapshot_coverage": {"market_snapshot_support_complete": True, "market_snapshot_as_of_dates": ["2026-05-22"]},
        },
    )
    _write_json(run_dir / "runtime_exact_value_ledger.json", {"rows": [{"metric_id": "m1"}]})
    _write_json(run_dir / "runtime_judgment_plan.json", {"plans": []})
    _write_json(
        run_dir / "post_gates" / "sec_benchmark_post_gates_summary.json",
        {"v2_semantic_contract_gate_pass": not gate_fail, "answer_vs_judgment_plan_gate_pass": True},
    )
    answer_status = "answered_contract_fallback" if fallback else "answered_api_model"
    _write_jsonl(run_dir / "qwen" / "agent_outputs.jsonl", [{"status": "answered", "answer_status": answer_status}])
    (run_dir / "qwen" / "rendered_answer.md").write_text(
        "10-Q unaudited; 8-K earnings release; market_snapshot as_of_date=2026-05-22",
        encoding="utf-8",
    )
    _write_jsonl(run_dir / "market_snapshot_context_rows.jsonl", [{"source_tier": "market_snapshot"}])
    return run_dir


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
