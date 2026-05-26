from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from sec_agent.graph_state import SecAgentState


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_interactive() -> Any:
    path = REPO_ROOT / "scripts" / "cloud" / "sec_agent_interactive.py"
    spec = importlib.util.spec_from_file_location("sec_agent_interactive_p0_observability", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_timed_stage_call_stamps_stage_elapsed_fields(tmp_path: Path) -> None:
    interactive = _load_interactive()
    state = SecAgentState.create(run_id="run1", user_query="query", output_dir=tmp_path)

    def _mark() -> str:
        state.mark_stage("dummy_stage", "completed", metadata={"row_count": 1})
        return "ok"

    result = interactive._timed_stage_call(state, tmp_path, ("dummy_stage",), _mark)

    assert result == "ok"
    assert len(state.stages) == 1
    stage = state.stages[0]
    assert stage.started_at
    assert stage.finished_at
    assert isinstance(stage.elapsed_ms, int)
    assert state.metadata["stage_timing_ms"]["dummy_stage"] == stage.elapsed_ms
    assert (tmp_path / "sec_agent_state.json").exists()


def test_run_data_fingerprint_records_inputs_and_runtime_knobs(tmp_path: Path) -> None:
    interactive = _load_interactive()
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(json.dumps({"ticker": "NVDA"}) + "\n", encoding="utf-8")
    market = tmp_path / "market.jsonl"
    market.write_text(json.dumps({"ticker": "NVDA"}) + "\n", encoding="utf-8")
    bm25_dir = tmp_path / "bm25"
    object_dir = tmp_path / "objects"
    for index_dir, records in ((bm25_dir, 2), (object_dir, 3)):
        index_dir.mkdir()
        (index_dir / "metadata.json").write_text(json.dumps({"records": records}), encoding="utf-8")
        (index_dir / "records.jsonl").write_text("{}\n", encoding="utf-8")
        (index_dir / "bm25.pkl").write_bytes(b"fake")
    args = SimpleNamespace(
        manifest_path=str(manifest),
        source_gap_path="",
        bm25_index_dir=str(bm25_dir),
        object_bm25_index_dir=str(object_dir),
        market_evidence_path=str(market),
        evidence_top_k=4,
        object_top_k=4,
        max_context_rows=120,
        reranker_top_k=120,
        reranker_candidate_limit=240,
        reranker_batch_size=16,
        reranker_max_length=1024,
        reranker_doc_max_chars=3000,
        ledger_max_rows=80,
    )
    query_contract = {
        "focus_tickers": ["NVDA"],
        "years": [2026],
        "filing_types": ["10-K", "10-Q"],
        "source_tiers": ["primary_sec_filing", "market_snapshot"],
        "source_policy": "SEC_PRIMARY_MIXED_WITH_8K_AND_MARKET_SNAPSHOT",
    }

    output_path = interactive._write_run_data_fingerprint(
        args,
        tmp_path,
        {"inventory_digest": "abc123"},
        query_contract,
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["inventory_digest"] == "abc123"
    assert payload["inputs"]["manifest"]["row_count"] == 1
    assert payload["inputs"]["market_evidence"]["row_count"] == 1
    assert payload["inputs"]["bm25_index"]["metadata"]["records"] == 2
    assert payload["inputs"]["object_bm25_index"]["metadata"]["records"] == 3
    assert payload["runtime_knobs"]["reranker_candidate_limit"] == 240


def test_run_performance_report_includes_all_stage_record_timings(tmp_path: Path) -> None:
    interactive = _load_interactive()
    state = SecAgentState.create(run_id="run1", user_query="query", output_dir=tmp_path)
    state.mark_stage(
        "plan_query",
        "completed",
        started_at="2026-05-26T00:00:00+00:00",
        finished_at="2026-05-26T00:00:01+00:00",
        elapsed_ms=1000,
    )
    state.mark_stage(
        "retrieve_context",
        "completed",
        started_at="2026-05-26T00:00:01+00:00",
        finished_at="2026-05-26T00:00:03+00:00",
        elapsed_ms=2000,
    )
    paths = {"run_performance_path": tmp_path / "run_performance.json"}

    output_path = interactive._write_run_performance_report(
        state,
        tmp_path,
        0.0,
        paths,
        qwen_result=None,
        post_gate_ok=True,
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["stage_timing_ms"]["plan_query"] == 1000
    assert payload["stage_timing_ms"]["retrieve_context"] == 2000


def test_context_runner_auto_uses_subprocess_for_local_qwen_bge_first() -> None:
    interactive = _load_interactive()
    args = SimpleNamespace(llm_backend="qwen_vllm", bge_first=True, context_runner="auto")

    assert interactive._context_runner_mode(args) == "subprocess"


def test_run_context_in_process_writes_benchmark_compatible_artifacts(tmp_path: Path, monkeypatch: Any) -> None:
    interactive = _load_interactive()
    case = {
        "case_id": "case1",
        "prompt": "compare revenue",
        "evaluation_modes": ["pipeline_context"],
    }
    cases_path = tmp_path / "case.jsonl"
    cases_path.write_text(json.dumps(case) + "\n", encoding="utf-8")
    trace_dir = tmp_path / "trace"
    args = SimpleNamespace(
        manifest_path=str(tmp_path / "manifest.jsonl"),
        bm25_index_dir=str(tmp_path / "bm25"),
        object_bm25_index_dir=str(tmp_path / "objects"),
        bge_model="fake-bge",
        bge_device="cpu",
        evidence_top_k=4,
        object_top_k=3,
        max_context_rows=20,
        reranker_batch_size=2,
        reranker_max_length=128,
        reranker_doc_max_chars=256,
        reranker_candidate_limit=10,
        reranker_top_k=8,
    )

    def _fake_prepare_trace(**kwargs: Any) -> dict[str, Any]:
        return {
            "case_id": kwargs["case"]["case_id"],
            "mode": kwargs["mode"],
            "status": "context_prepared",
            "context_summary": {"context_row_count": 1},
            "context_policy": {"timing_ms": {"candidate_generation": 1, "context_rerank": 2}},
            "context_rows": [{"evidence_id": "E1", "text": "Revenue increased."}],
        }

    fake_benchmark = SimpleNamespace(
        _enforce_pipeline_context_policy=lambda *a, **k: None,
        _base_trace=lambda case, mode, status: {"case_id": case.get("case_id"), "mode": mode, "status": status},
        _prepare_trace=_fake_prepare_trace,
        _run_synthesis_backend=lambda **kwargs: {
            "agent_status": "context_prepared",
            "answer_status": "not_run_context_only",
            "answer": None,
            "limitations": [],
            "claim_status": "not_run_context_only",
            "claims": [],
            "unsupported_claim_count": None,
            "score_status": "not_scored_context_only",
            "score_total": None,
            "scores": None,
            "failure_types": [],
            "score_notes": [],
        },
        _summary=lambda bench_args, output_dir, traces, outputs: {
            "trace_count": len(traces),
            "agent_output_count": len(outputs),
        },
        _write_bad_cases=lambda path, traces: path.write_text("No context-preparation failures.\n", encoding="utf-8"),
    )
    monkeypatch.setattr(interactive, "benchmark_context", fake_benchmark)
    monkeypatch.setattr(interactive, "_load_manifest_index_cached", lambda path: {})
    monkeypatch.setattr(
        interactive,
        "_get_context_runtime_resources",
        lambda source_args, bench_args: (
            {"bm25": object(), "object_bm25": object(), "context_reranker": object()},
            {"context_cache_hit": True, "context_cache_key": "fake"},
        ),
    )

    result = interactive._run_context_in_process(args, cases_path, trace_dir)

    trace = json.loads((trace_dir / "trace_logs.jsonl").read_text(encoding="utf-8").splitlines()[0])
    summary = json.loads((trace_dir / "run_summary.json").read_text(encoding="utf-8"))
    assert result["context_runtime"]["context_runner"] == "in_process"
    assert trace["context_policy"]["context_runtime"]["context_cache_hit"] is True
    assert summary["trace_count"] == 1
    assert (trace_dir / "agent_outputs.jsonl").exists()


def test_query_contract_repair_removes_negated_market_snapshot_request() -> None:
    interactive = _load_interactive()
    project_inventory = {
        "companies": [
            {
                "ticker": "MSFT",
                "filings": [
                    {"year": 2026, "form_type": "10-Q", "source_tier": "primary_sec_filing"},
                    {"year": 2026, "form_type": "8-K", "source_tier": "company_authored_unaudited_sec_filing"},
                ],
            }
        ]
    }
    contract = {
        "task_type": "general_sec_financial_question",
        "focus_tickers": ["MSFT"],
        "years": [2026],
        "filing_types": ["10-Q", "8-K"],
        "source_tiers": ["primary_sec_filing", "company_authored_unaudited_sec_filing", "market_snapshot"],
        "source_policy": "SEC_PRIMARY_MIXED_WITH_8K_AND_MARKET_SNAPSHOT",
        "market_snapshot": {"required": True, "fields": ["return_3m"], "analysis_tools": ["return_summary"]},
        "decomposed_tasks": [
            {
                "task_id": "cloud",
                "required_tickers": ["MSFT"],
                "required_metric_families": ["cloud_revenue"],
                "required_market_fields": ["return_3m"],
            }
        ],
    }

    repaired = interactive._repair_query_contract_from_prompt(
        contract,
        "只使用 SEC 10-K、10-Q 和公司8-K业绩新闻稿；不要引入外部新闻、股价、分析师观点或当前市场数据。",
        ["MSFT"],
        [2026],
        project_inventory,
    )

    assert "market_snapshot" not in repaired
    assert "market_snapshot" not in repaired["source_tiers"]
    assert repaired["source_policy"] == "SEC_PRIMARY_MIXED_WITH_8K_EARNINGS"
    assert "required_market_fields" not in repaired["decomposed_tasks"][0]


def test_ledger_supplement_scope_filters_records_before_expensive_table_parse() -> None:
    interactive = _load_interactive()
    records = {
        "keep": {
            "object_id": "keep",
            "object_type": "table",
            "ticker": "NVDA",
            "fiscal_year": 2026,
            "title": "Capital expenditures",
            "metadata": {"form_type": "10-Q", "source_tier": "primary_sec_filing"},
            "cells": [{"row_label": "Purchases of property and equipment", "period": "2026"}],
        },
        "wrong_ticker": {
            "object_id": "wrong_ticker",
            "object_type": "table",
            "ticker": "AMD",
            "fiscal_year": 2026,
            "title": "Capital expenditures",
            "metadata": {"form_type": "10-Q", "source_tier": "primary_sec_filing"},
            "cells": [{"row_label": "Purchases of property and equipment", "period": "2026"}],
        },
        "wrong_year": {
            "object_id": "wrong_year",
            "object_type": "table",
            "ticker": "NVDA",
            "fiscal_year": 2024,
            "title": "Capital expenditures",
            "metadata": {"form_type": "10-Q", "source_tier": "primary_sec_filing"},
            "cells": [{"row_label": "Purchases of property and equipment", "period": "2024"}],
        },
        "wrong_family": {
            "object_id": "wrong_family",
            "object_type": "table",
            "ticker": "NVDA",
            "fiscal_year": 2026,
            "title": "Share-based compensation",
            "metadata": {"form_type": "10-Q", "source_tier": "primary_sec_filing"},
            "cells": [{"row_label": "Stock awards", "period": "2026"}],
        },
    }
    case = {"years": [2026], "filing_types": ["10-Q"], "source_tiers": ["primary_sec_filing"]}
    query_contract = {
        "focus_tickers": ["NVDA"],
        "filing_types": ["10-Q"],
        "source_tiers": ["primary_sec_filing"],
        "metric_families": ["capital_expenditure_proxy"],
    }

    scoped = interactive._ledger_supplement_scope_records(case, records, query_contract)
    scoped_ids = {row["object_id"] for row in scoped}
    prefiltered_ids = {
        row["object_id"]
        for row in scoped
        if interactive._record_may_match_metric_families(row, {"capital_expenditure_proxy"})
    }

    assert scoped_ids == {"keep", "wrong_family"}
    assert prefiltered_ids == {"keep"}


def test_contract_required_family_tickers_uses_planner_task_scope() -> None:
    interactive = _load_interactive()
    query_contract = {
        "focus_tickers": ["MSFT", "NVDA", "JPM"],
        "metric_families": ["revenue", "net_interest_margin"],
        "decomposed_tasks": [
            {
                "required_metric_families": ["revenue", "operating_income"],
                "required_tickers": ["MSFT", "NVDA"],
            },
            {
                "required_metric_families": ["net_interest_margin", "net_charge_offs"],
                "required_tickers": ["JPM"],
            },
        ],
    }

    mapping = interactive._contract_required_family_tickers(query_contract)

    assert mapping["revenue"] == {"MSFT", "NVDA"}
    assert mapping["operating_income"] == {"MSFT", "NVDA"}
    assert mapping["net_interest_margin"] == {"JPM"}
    assert mapping["net_charge_offs"] == {"JPM"}


def test_ledger_derives_percentage_rate_from_table_change_column() -> None:
    interactive = _load_interactive()
    record = {
        "object_id": "JPM_2026_10Q_TABLE",
        "object_type": "table",
        "source_evidence_id": "JPM_2026_10Q_ITEM1",
        "ticker": "JPM",
        "fiscal_year": 2026,
        "form_type": "10-Q",
        "source_tier": "primary_sec_filing",
        "period_end": "2026-03-31",
        "period_type": "quarterly",
        "duration_months": 3,
        "fiscal_period": "Q1",
        "section": "Item 1",
        "cells": [
            {
                "row_index": 10,
                "row_label": "Total net revenue",
                "column_label": "Three months ended March 31,",
                "period": "2026",
                "period_role": "qtd",
                "raw_value": "6,374",
                "value": 6374.0,
                "unit": "usd_millions",
            },
            {
                "row_index": 10,
                "row_label": "Total net revenue",
                "column_label": "Three months ended March 31,",
                "period": "2025",
                "period_role": "qtd",
                "raw_value": "5,731",
                "value": 5731.0,
                "unit": "usd_millions",
            },
            {
                "row_index": 10,
                "row_label": "Total net revenue",
                "column_label": None,
                "period": None,
                "period_role": "qtd",
                "raw_value": "11",
                "value": 11.0,
                "unit": "usd_millions",
            },
        ],
    }

    rows = interactive._ledger_rows_from_table("case", record, {2026})
    change_rows = [row for row in rows if row.get("cell_kind") == "period_change_rate"]

    assert len(change_rows) == 1
    assert change_rows[0]["metric_family"] == "revenue"
    assert change_rows[0]["metric_role"] == "percentage_rate"
    assert change_rows[0]["period_role"] == "qtd"
    assert change_rows[0]["raw_value_text"] == "11%"
    assert interactive._ledger_row_allowed(change_rows[0], {"ledger_rules": {}})
