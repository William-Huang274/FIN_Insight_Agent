from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "workbench" / "run_expanded_a6_eval.py"
SPEC = importlib.util.spec_from_file_location("run_expanded_a6_eval", SCRIPT_PATH)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_expanded_a6_workbench_summary_rolls_up_tokens_runtime_and_failures(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("SEC_AGENT_WORKBENCH_JOB_ID", "job_a6")
    monkeypatch.setenv("SEC_AGENT_TRACE_ID", "trace_a6")
    child_summary = {
        "gate_status": "fail",
        "elapsed_ms": 12_000,
        "metrics": {"case_count": 2, "passed": 1, "failed": 1, "total_tool_calls": 7},
        "categories": {"exact_lookup": {"case_count": 1, "passed": 1, "failed": 0}},
        "model_config": {"api_key_env": "DEMO_API_KEY", "api_key_saved": False, "raw_llm_response_saved": False},
        "cases": [
            {
                "case_id": "case_pass",
                "category": "exact_lookup",
                "gate_status": "pass",
                "elapsed_ms": 5_000,
                "agent_audit": {
                    "research_lead": {"diagnostics": {"total_tokens": 100}},
                    "memo_writer": {"diagnostics": {"total_tokens": 200}},
                    "verifier": {"diagnostics": {"total_tokens": 50}},
                    "specialists": {"route_results": [{"agent_id": "fundamental_analyst", "total_tokens": 300}]},
                },
            },
            {
                "case_id": "case_fail",
                "category": "sector_depth",
                "gate_status": "fail",
                "elapsed_ms": 7_000,
                "checks": {"memo_verifier.verifier_llm_pass": False, "rendered.answer": True},
                "loop_break_reason": "quality_gate_failed",
                "agent_audit": {
                    "universe_relationship": {"diagnostics": {"total_tokens": 400}},
                    "specialists": {"route_results": [{"agent_id": "industry_supply_chain_analyst", "total_tokens": 500}]},
                },
            },
        ],
    }

    report = module.build_workbench_eval_summary(
        eval_id="expanded_a6_full_chain_main",
        run_id="a6_unit",
        output_path=tmp_path / "a6.json",
        child_summary=child_summary,
        child_summary_path=tmp_path / "child" / "real_chain_eval_summary.json",
        child_output_dir=tmp_path / "child",
        child_return_code=1,
        elapsed_ms=13_000,
        selected_case_ids=[],
        prewarm_report={"enabled": True, "status": "pass", "tool_count": 2},
    )

    assert report["status"] == "fail"
    assert report["case_count"] == 2
    assert report["pass_count"] == 1
    assert report["failure_count"] == 1
    assert report["token_usage"]["total_tokens"] == 1550
    assert report["token_usage"]["by_agent"]["industry_supply_chain_analyst"] == 500
    assert report["runtime"]["child_elapsed_ms"] == 12_000
    assert report["runtime"]["tool_call_count"] == 7
    assert report["prewarm"]["status"] == "pass"
    assert report["prewarm"]["tool_count"] == 2
    assert report["trace"]["workbench_job_id"] == "job_a6"
    assert report["trace"]["workbench_trace_id"] == "trace_a6"
    assert report["secret_safety"]["api_key_saved"] is False
    assert report["secret_safety"]["raw_llm_response_saved"] is False
    assert report["failures"][0]["failed_checks"] == {"memo_verifier.verifier_llm_pass": False}


def test_expanded_a6_smoke_default_case_selection() -> None:
    args = module.parse_args(
        [
            "--eval-id",
            "expanded_a6_full_chain_smoke",
            "--output-path",
            "reports/quality/workbench_eval/a6_smoke.json",
        ]
    )

    case_ids = module._selected_case_ids(args)

    assert case_ids == [
        "fin_full_exact_msft_capex_zh",
        "fin_full_scope_nvda_basic_fundamental_zh",
        "fin_full_standard_nvda_amd_market_zh",
        "fin_full_sector_ai_infra_depth_zh",
    ]


def test_expanded_a6_prewarm_payloads_include_sec_and_milvus(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BGE_DEVICE", "auto")
    monkeypatch.setenv("MILVUS_DB_PATH", "/tmp/milvus.db")
    monkeypatch.setenv("MILVUS_COLLECTION_NAME", "collection")
    monkeypatch.setenv("MILVUS_EMBEDDING_MODEL", "/tmp/bge-m3")
    monkeypatch.setenv("MANIFEST_PATH", "/tmp/manifest.jsonl")
    monkeypatch.setenv("BM25_INDEX_DIR", "/tmp/bm25")
    monkeypatch.setenv("OBJECT_BM25_INDEX_DIR", "/tmp/object")
    cases = [
        {
            "case_id": "sector",
            "focus_tickers": ["NVDA", "DELL"],
            "search_scope_tickers": ["NVDA", "DELL", "ANET", "VRT"],
            "source_tiers": ["primary_sec_filing", "company_authored_unaudited_sec_filing", "relationship_graph"],
            "metric_families": ["revenue", "gross_margin"],
            "years": [2026],
            "required_agents": ["sec_operator", "eight_k_operator"],
            "expected_tool_names": ["sec_search_filings", "sec_milvus_semantic_search"],
        }
    ]

    payloads = module._resident_prewarm_payloads(cases=cases, run_id="run", artifact_root=tmp_path)

    assert [payload["tool_name"] for payload in payloads] == [
        "sec_search_filings",
        "sec_search_filings",
        "sec_milvus_semantic_search",
    ]
    assert payloads[0]["arguments"]["tickers"][:2] == ["NVDA", "DELL"]
    assert payloads[0]["arguments"]["candidate_budget"] == 80
    assert payloads[0]["arguments"]["bge_device"] in {"cpu", "cuda"}
    assert payloads[0]["arguments"]["bge_device"] != "auto"
    assert payloads[1]["arguments"]["filing_types"] == ["8-K"]
    assert payloads[1]["arguments"]["retrieval_route"] == "8k_commentary"
    assert payloads[2]["arguments"]["milvus_db_path"] == "/tmp/milvus.db"


def test_expanded_a6_prewarm_payloads_skip_milvus_when_case_does_not_need_it(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MILVUS_DB_PATH", "/tmp/milvus.db")
    monkeypatch.setenv("MILVUS_COLLECTION_NAME", "collection")
    cases = [
        {
            "case_id": "focused",
            "focus_tickers": ["AMZN"],
            "required_agents": ["research_lead", "sec_operator", "eight_k_operator"],
            "expected_tool_names": ["sec_search_filings"],
        }
    ]

    payloads = module._resident_prewarm_payloads(cases=cases, run_id="run", artifact_root=tmp_path)

    assert [payload["tool_name"] for payload in payloads] == ["sec_search_filings", "sec_search_filings"]
    assert [payload["arguments"]["filing_types"] for payload in payloads] == [["10-K", "10-Q"], ["8-K"]]
