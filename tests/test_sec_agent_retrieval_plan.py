from __future__ import annotations

import sys
import importlib.util
from argparse import Namespace
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.retrieval_plan import build_evidence_requirement_plan, build_retrieval_plan, validate_retrieval_plan  # noqa: E402
from sec_agent.ledger_store import write_ledger_store  # noqa: E402


def _load_benchmark_module():
    path = REPO_ROOT / "scripts" / "eval_sec_benchmark" / "run_sec_benchmark_eval.py"
    spec = importlib.util.spec_from_file_location("run_sec_benchmark_eval_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _load_interactive_module():
    path = REPO_ROOT / "scripts" / "cloud" / "sec_agent_interactive.py"
    spec = importlib.util.spec_from_file_location("sec_agent_interactive_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_retrieval_plan_derives_structured_market_and_8k_routes() -> None:
    contract = {
        "source_policy": "SEC_PRIMARY_MIXED_WITH_8K_AND_MARKET_SNAPSHOT",
        "focus_tickers": ["NVDA", "AMD"],
        "search_scope_tickers": ["NVDA", "AMD"],
        "years": [2025, 2026],
        "filing_types": ["10-K", "10-Q", "8-K"],
        "source_tiers": [
            "primary_sec_filing",
            "company_authored_unaudited_sec_filing",
            "market_snapshot",
        ],
        "metric_families": ["data_center_revenue", "capex"],
        "market_snapshot": {
            "required": True,
            "fields": ["return_3m", "pe_ttm"],
            "analysis_tools": ["fundamental_market_divergence"],
        },
        "decomposed_tasks": [
            {
                "task_id": "ai_fundamental_market",
                "priority": "primary",
                "question_zh": "比较 AI 基本面、管理层解释、市场反应和估值分歧",
                "required_tickers": ["NVDA", "AMD"],
                "required_metric_families": ["data_center_revenue", "capex"],
            }
        ],
    }

    plan = build_retrieval_plan(contract, case={"case_id": "unit", "companies": ["NVDA", "AMD"], "years": [2025, 2026]})
    route_names = {route["retrieval_route"] for route in plan["routes"]}

    assert (plan["retrieval_plan_validation"] or {})["status"] == "pass"
    assert {"ledger_first", "filing_text", "8k_commentary", "market_snapshot"} <= route_names
    assert all(route["rerank_budget"] == 0 for route in plan["routes"] if route["retrieval_route"] in {"ledger_first", "market_snapshot"})
    assert any(route["rerank_budget"] > 0 for route in plan["routes"] if route["retrieval_route"] == "filing_text")
    assert plan["summary"]["second_pass_enabled"] is True


def test_planner_evidence_requirements_drive_physical_routes() -> None:
    contract = {
        "source_policy": "SEC_PRIMARY_MIXED_WITH_8K_AND_MARKET_SNAPSHOT",
        "focus_tickers": ["NVDA"],
        "search_scope_tickers": ["NVDA", "AMD"],
        "years": [2026],
        "filing_types": ["10-K", "10-Q", "8-K"],
        "source_tiers": [
            "primary_sec_filing",
            "company_authored_unaudited_sec_filing",
            "market_snapshot",
        ],
        "metric_families": ["capex"],
        "decomposed_tasks": [
            {
                "task_id": "management_explanation",
                "question_zh": "解释资本开支变化的管理层口径",
                "required_tickers": ["NVDA"],
                "required_metric_families": ["capex"],
            }
        ],
        "evidence_requirements": [
            {
                "requirement_id": "req_8k_management",
                "task_id": "management_explanation",
                "question_zh": "查找 8-K 业绩新闻稿中的 capex 解释",
                "tickers": ["NVDA", "BAD"],
                "years": [2026, 2030],
                "filing_types": ["8-K"],
                "source_tiers": ["company_authored_unaudited_sec_filing"],
                "metric_families": ["capex"],
                "period_roles": ["QTD", "YTD"],
                "evidence_routes": ["8k_commentary", "web_search"],
                "route_selection_reason": "8-K earnings release commentary is the narrowest company-authored source.",
                "route_cost_tier": "medium",
                "route_selection_policy": "cost_and_query_type_aware_v0_1",
                "candidate_budget": 16,
                "rerank_budget": 8,
            }
        ],
    }

    erp = build_evidence_requirement_plan(contract)
    plan = build_retrieval_plan(contract)
    routes = plan["routes"]

    assert erp["source"] == "planner_output_evidence_requirements"
    assert erp["requirements"][0]["tickers"] == ["NVDA"]
    assert erp["requirements"][0]["years"] == [2026]
    assert erp["requirements"][0]["evidence_routes"] == ["8k_commentary"]
    assert erp["requirements"][0]["route_selection_reason"].startswith("8-K earnings")
    assert erp["requirements"][0]["route_cost_tier"] == "medium"
    assert (plan["retrieval_plan_validation"] or {})["status"] == "pass"
    assert [route["retrieval_route"] for route in routes] == ["8k_commentary"]
    assert routes[0]["route_selection_reason"].startswith("8-K earnings")
    assert routes[0]["route_cost_tier"] == "medium"
    assert routes[0]["route_selection_policy"] == "cost_and_query_type_aware_v0_1"
    assert routes[0]["candidate_budget"] == 16
    assert routes[0]["rerank_budget"] == 8
    assert plan["evidence_requirement_plan"]["source"] == "planner_output_evidence_requirements"


def test_run_artifact_evidence_requirement_allows_empty_company_scope() -> None:
    contract = {
        "source_tiers": ["run_artifact"],
        "evidence_requirements": [
            {
                "requirement_id": "req_run_artifacts",
                "task_id": "inspect_run",
                "question_zh": "Inspect existing run coverage and graph state.",
                "source_tiers": ["primary_sec_filing"],
                "evidence_routes": ["run_artifact"],
            }
        ],
    }

    erp = build_evidence_requirement_plan(contract)
    plan = build_retrieval_plan(contract)

    assert erp["evidence_requirement_validation"]["status"] == "pass"
    assert erp["requirements"][0]["source_tiers"] == ["run_artifact"]
    assert erp["requirements"][0]["tickers"] == []
    assert erp["requirements"][0]["years"] == []
    assert plan["routes"][0]["retrieval_route"] == "run_artifact"
    assert plan["routes"][0]["source_tiers"] == ["run_artifact"]


def test_retrieval_plan_scopes_route_values_to_query_contract() -> None:
    plan = {
        "schema_version": "bad",
        "tasks": [{"task_id": "task_1"}],
        "routes": [
            {
                "route_id": "task_1::filing_text",
                "task_id": "task_1",
                "retrieval_route": "filing_text",
                "tickers": ["NVDA", "BAD"],
                "years": [2026, 2030],
                "filing_types": ["10-Q", "S-1"],
                "source_tiers": ["primary_sec_filing", "external_news"],
                "candidate_budget": 5000,
                "rerank_budget": 5000,
            }
        ],
    }
    result = validate_retrieval_plan(
        plan,
        query_contract={
            "search_scope_tickers": ["NVDA"],
            "years": [2026],
            "filing_types": ["10-Q"],
            "source_tiers": ["primary_sec_filing"],
        },
    )
    route = result["plan"]["routes"][0]

    assert result["report"]["status"] == "pass"
    assert route["tickers"] == ["NVDA"]
    assert route["years"] == [2026]
    assert route["filing_types"] == ["10-Q"]
    assert route["source_tiers"] == ["primary_sec_filing"]
    assert route["candidate_budget"] == 1000
    assert route["rerank_budget"] == 1000


def test_retrieval_plan_fails_closed_on_unknown_route() -> None:
    result = validate_retrieval_plan(
        {
            "tasks": [{"task_id": "task_1"}],
            "routes": [{"task_id": "task_1", "retrieval_route": "web_search"}],
        },
        query_contract={"search_scope_tickers": ["NVDA"], "years": [2026]},
    )

    assert result["report"]["status"] == "fail"
    assert result["report"]["errors"][0]["type"] == "invalid_retrieval_route"


def test_route_executor_keeps_ledger_first_out_of_bge_rerank() -> None:
    benchmark = _load_benchmark_module()
    case = {
        "case_id": "route_unit",
        "prompt": "compare revenue and management commentary",
        "retrieval_plan": {
            "schema_version": "sec_agent_retrieval_plan_v0.1",
            "retrieval_plan_validation": {"status": "pass"},
            "tasks": [
                {"task_id": "task_1", "question_zh": "compare revenue and management commentary"},
            ],
            "routes": [
                {
                    "route_id": "task_1::ledger_first",
                    "task_id": "task_1",
                    "retrieval_route": "ledger_first",
                    "tickers": ["NVDA"],
                    "years": [2026],
                    "filing_types": ["10-Q"],
                    "source_tiers": ["primary_sec_filing"],
                    "metric_families": ["revenue"],
                    "candidate_budget": 8,
                    "rerank_budget": 0,
                },
                {
                    "route_id": "task_1::filing_text",
                    "task_id": "task_1",
                    "retrieval_route": "filing_text",
                    "tickers": ["NVDA"],
                    "years": [2026],
                    "filing_types": ["10-Q"],
                    "source_tiers": ["primary_sec_filing"],
                    "metric_families": ["revenue"],
                    "section_hints": ["md&a"],
                    "candidate_budget": 8,
                    "rerank_budget": 4,
                },
            ],
        },
    }

    rows, policy = benchmark._pipeline_context_rows_from_retrieval_plan(
        case,
        case["retrieval_plan"],
        FakeBM25(),
        FakeObjectBM25(),
        evidence_top_k=4,
        object_top_k=2,
    )
    reranker = FakeReranker()
    reranked = benchmark._rerank_context_rows(
        case,
        rows,
        reranker,
        Namespace(
            context_reranker_candidate_limit=10,
            context_reranker_doc_max_chars=1000,
            context_reranker_batch_size=8,
            context_reranker_model="fake",
            context_reranker_top_k=4,
        ),
    )

    assert policy["retrieval_plan_enabled"] is True
    assert {row["retrieval_route"] for row in rows} == {"ledger_first", "filing_text"}
    assert [row["rerank_eligible"] for row in rows] == [False, True]
    assert len(reranker.pairs) == 1
    assert any(row["retrieval_route"] == "ledger_first" for row in reranked)


def test_route_executor_uses_ledger_store_for_ledger_first(tmp_path: Path) -> None:
    benchmark = _load_benchmark_module()
    store_path = tmp_path / "ledger.duckdb"
    write_ledger_store(
        [
            _ledger_fact_row(metric_id="store::NVDA::2026::revenue::total_value::qtd", period_role="qtd"),
            _ledger_fact_row(metric_id="store::NVDA::2026::revenue::total_value::annual", period_role="annual"),
        ],
        store_path,
    )
    case = {
        "case_id": "route_ledger_store_unit",
        "prompt": "compare revenue",
        "retrieval_plan": {
            "schema_version": "sec_agent_retrieval_plan_v0.1",
            "retrieval_plan_validation": {"status": "pass"},
            "tasks": [{"task_id": "task_1", "question_zh": "compare revenue"}],
            "routes": [
                {
                    "route_id": "task_1::ledger_first",
                    "task_id": "task_1",
                    "retrieval_route": "ledger_first",
                    "tickers": ["NVDA"],
                    "years": [2026],
                    "filing_types": ["10-Q"],
                    "source_tiers": ["primary_sec_filing"],
                    "metric_families": ["revenue"],
                    "period_roles": ["qtd"],
                    "candidate_budget": 8,
                    "rerank_budget": 0,
                }
            ],
        },
    }

    rows, policy = benchmark._pipeline_context_rows_from_retrieval_plan(
        case,
        case["retrieval_plan"],
        FakeBM25(),
        ExplodingObjectBM25(),
        evidence_top_k=4,
        object_top_k=2,
        ledger_store_path=store_path,
    )

    assert len(rows) == 1
    assert rows[0]["selection_method"] == "route_ledger_first_ledger_store"
    assert rows[0]["period_role"] == "qtd"
    assert rows[0]["rerank_eligible"] is False
    assert policy["ledger_store_path"] == str(store_path)


def test_interactive_context_args_forward_ledger_store_path() -> None:
    interactive = _load_interactive_module()
    args = Namespace(
        manifest_path="manifest.jsonl",
        bm25_index_dir="bm25",
        object_bm25_index_dir="objects",
        evidence_top_k=4,
        object_top_k=2,
        max_context_rows=120,
        bge_model="fake-bge",
        bge_device="cuda",
        reranker_batch_size=8,
        reranker_max_length=512,
        reranker_doc_max_chars=1000,
        reranker_candidate_limit=64,
        reranker_top_k=32,
        ledger_store_path="data/processed_private/ledger/test.duckdb",
    )

    bench_args = interactive._benchmark_context_args(args, Path("case.jsonl"), Path("trace"))

    assert bench_args.ledger_store_path == "data/processed_private/ledger/test.duckdb"


def test_route_scoped_merge_keeps_text_rows_when_pinned_rows_exceed_top_k() -> None:
    benchmark = _load_benchmark_module()
    pinned = [
        {
            "source_kind": "structured_object",
            "object_id": f"obj_{index}",
            "retrieval_route": "ledger_first",
            "rerank_eligible": False,
        }
        for index in range(5)
    ]
    selected = [
        {
            "source_kind": "evidence_object",
            "evidence_id": "text_1",
            "retrieval_route": "8k_commentary",
            "rerank_eligible": True,
        }
    ]

    merged = benchmark._merge_route_scoped_context_rows(pinned, selected, top_k=1)

    assert len(merged) == 6
    assert sum(1 for row in merged if row["retrieval_route"] == "ledger_first") == 5
    assert any(row["retrieval_route"] == "8k_commentary" for row in merged)


def test_route_scoped_rerank_candidates_respect_route_budget() -> None:
    benchmark = _load_benchmark_module()
    rows = [
        {
            "source_kind": "evidence_object",
            "evidence_id": f"filing_{index}",
            "selection_route_id": "task::filing_text",
            "selection_rerank_budget": 2,
            "rerank_eligible": True,
        }
        for index in range(4)
    ] + [
        {
            "source_kind": "evidence_object",
            "evidence_id": f"eightk_{index}",
            "selection_route_id": "task::8k_commentary",
            "selection_rerank_budget": 1,
            "rerank_eligible": True,
        }
        for index in range(3)
    ]

    selected = benchmark._select_route_scoped_rerank_candidates(rows, candidate_limit=10)

    assert [row["evidence_id"] for row in selected] == ["filing_0", "filing_1", "eightk_0"]


def test_route_coverage_reservation_promotes_source_tier_and_ticker_slots() -> None:
    benchmark = _load_benchmark_module()
    plan = {
        "routes": [
            {"retrieval_route": "filing_text", "tickers": ["NVDA", "AMD"]},
            {"retrieval_route": "8k_commentary", "tickers": ["NVDA", "AMD"]},
        ]
    }
    rows = [
        {
            "source_kind": "evidence_object",
            "evidence_id": "nvda_10q",
            "selection_task_id": "task",
            "retrieval_route": "filing_text",
            "ticker": "NVDA",
            "source_tier": "primary_sec_filing",
            "selection_metric_families": ["revenue"],
        },
        {
            "source_kind": "evidence_object",
            "evidence_id": "amd_8k",
            "selection_task_id": "task",
            "retrieval_route": "8k_commentary",
            "ticker": "AMD",
            "source_tier": "company_authored_unaudited_sec_filing",
            "selection_metric_families": ["revenue"],
        },
        {
            "source_kind": "evidence_object",
            "evidence_id": "tail",
            "selection_task_id": "task",
            "retrieval_route": "filing_text",
            "ticker": "NVDA",
            "source_tier": "primary_sec_filing",
            "selection_metric_families": ["revenue"],
        },
    ]

    merged, policy = benchmark._apply_route_coverage_reservations(rows, plan)

    assert policy["enabled"] is True
    assert policy["reserved_count"] >= 2
    assert merged[0]["coverage_reservation_reason"] == "task_route_minimum"
    assert any(row.get("retrieval_route") == "8k_commentary" for row in merged[:2])


def test_route_executor_reuses_identical_route_searches() -> None:
    benchmark = _load_benchmark_module()
    bm25 = CountingBM25()
    case = {
        "case_id": "route_cache_unit",
        "prompt": "compare revenue",
        "retrieval_plan": {
            "schema_version": "sec_agent_retrieval_plan_v0.1",
            "retrieval_plan_validation": {"status": "pass"},
            "tasks": [
                {"task_id": "task_1", "question_zh": "compare revenue"},
            ],
            "routes": [
                {
                    "route_id": "task_1::filing_text_a",
                    "task_id": "task_1",
                    "retrieval_route": "filing_text",
                    "tickers": ["NVDA"],
                    "years": [2026],
                    "filing_types": ["10-Q"],
                    "source_tiers": ["primary_sec_filing"],
                    "metric_families": ["revenue"],
                    "candidate_budget": 8,
                    "rerank_budget": 4,
                },
                {
                    "route_id": "task_1::filing_text_b",
                    "task_id": "task_1",
                    "retrieval_route": "filing_text",
                    "tickers": ["NVDA"],
                    "years": [2026],
                    "filing_types": ["10-Q"],
                    "source_tiers": ["primary_sec_filing"],
                    "metric_families": ["revenue"],
                    "candidate_budget": 8,
                    "rerank_budget": 4,
                },
            ],
        },
    }

    rows, policy = benchmark._pipeline_context_rows_from_retrieval_plan(
        case,
        case["retrieval_plan"],
        bm25,
        FakeObjectBM25(),
        evidence_top_k=4,
        object_top_k=2,
    )

    assert bm25.calls == 1
    assert policy["route_search_cache_entries"] == 1
    assert len(rows) == 1
    assert set(rows[0]["selection_route_ids"]) == {"task_1::filing_text_a", "task_1::filing_text_b"}
    assert policy["route_search_merge"]["shared_route_attributions"] == 1


def test_second_pass_requirements_compile_searchable_coverage_gaps() -> None:
    interactive = _load_interactive_module()
    contract = {
        "focus_tickers": ["NVDA", "AMD"],
        "search_scope_tickers": ["NVDA", "AMD"],
        "years": [2025, 2026],
        "filing_types": ["10-K", "10-Q", "8-K"],
        "source_tiers": ["primary_sec_filing", "company_authored_unaudited_sec_filing", "market_snapshot"],
        "metric_families": ["revenue", "capex"],
    }
    coverage = {
        "summary": {"coverage_complete": False, "primary_task_support_complete": False},
        "source_coverage_gaps": [],
        "tasks": [
            {
                "task_id": "task_ai_compare",
                "question_zh": "比较 AI 基本面和管理层解释",
                "priority": "primary",
                "support_level": "partial",
                "required_tickers": ["NVDA", "AMD"],
                "missing_tickers": ["AMD"],
                "missing_metric_families": ["capex"],
                "missing_filing_types": ["8-K"],
                "missing_source_tiers": ["company_authored_unaudited_sec_filing"],
            }
        ],
    }

    requirements = interactive._second_pass_requirements_from_coverage(contract, coverage)

    assert len(requirements) == 1
    assert requirements[0]["tickers"] == ["AMD"]
    assert requirements[0]["filing_types"] == ["8-K"]
    assert requirements[0]["source_tiers"] == ["company_authored_unaudited_sec_filing"]
    assert requirements[0]["metric_families"] == ["capex"]
    assert requirements[0]["evidence_routes"] == ["8k_commentary"]


def test_second_pass_requirements_skip_inventory_source_gaps() -> None:
    interactive = _load_interactive_module()
    contract = {
        "focus_tickers": ["MSFT"],
        "search_scope_tickers": ["MSFT"],
        "years": [2026],
        "filing_types": ["8-K"],
        "source_tiers": ["company_authored_unaudited_sec_filing"],
        "metric_families": ["capex"],
    }
    coverage = {
        "summary": {"coverage_complete": False, "primary_task_support_complete": False},
        "source_coverage_gaps": [
            {
                "ticker": "MSFT",
                "year": 2026,
                "form_type": "8-K",
                "source_tier": "company_authored_unaudited_sec_filing",
                "reason": "no_item_2_02_8k_for_filing_year",
            }
        ],
        "tasks": [
            {
                "task_id": "task_8k",
                "question_zh": "查找 8-K 中的 capex 管理层解释",
                "priority": "primary",
                "support_level": "insufficient",
                "required_tickers": ["MSFT"],
                "missing_tickers": ["MSFT"],
                "missing_metric_families": ["capex"],
                "missing_filing_types": ["8-K"],
                "missing_source_tiers": ["company_authored_unaudited_sec_filing"],
            }
        ],
    }

    assert interactive._second_pass_requirements_from_coverage(contract, coverage) == []


def test_second_pass_requirement_aligns_forms_with_source_tiers() -> None:
    interactive = _load_interactive_module()
    contract = {
        "focus_tickers": ["NVDA"],
        "search_scope_tickers": ["NVDA"],
        "years": [2026],
        "filing_types": ["10-Q", "8-K"],
        "source_tiers": ["primary_sec_filing", "company_authored_unaudited_sec_filing"],
        "metric_families": ["capex"],
    }
    coverage = {
        "summary": {"coverage_complete": False, "primary_task_support_complete": False},
        "source_coverage_gaps": [],
        "tasks": [
            {
                "task_id": "task_primary_gap",
                "question_zh": "查找 10-Q 中的 capex 证据",
                "priority": "primary",
                "support_level": "partial",
                "required_tickers": ["NVDA"],
                "missing_metric_families": ["capex"],
                "missing_source_tiers": ["primary_sec_filing"],
            }
        ],
    }

    requirements = interactive._second_pass_requirements_from_coverage(contract, coverage)

    assert requirements[0]["filing_types"] == ["10-Q"]
    assert requirements[0]["source_tiers"] == ["primary_sec_filing"]
    assert requirements[0]["evidence_routes"] == ["ledger_first", "filing_text"]


def test_second_pass_stage_merges_context_and_writes_trace(tmp_path, monkeypatch) -> None:
    interactive = _load_interactive_module()
    state = interactive.SecAgentState.create(
        run_id="second_pass_unit",
        user_query="比较 NVDA 和 AMD 的资本开支证据",
        output_dir=tmp_path / "run",
        selected_tickers=["NVDA", "AMD"],
        selected_years=[2026],
    )
    query_contract = {
        "source_policy": "SEC_PRIMARY_MIXED_WITH_8K_EARNINGS",
        "focus_tickers": ["NVDA", "AMD"],
        "search_scope_tickers": ["NVDA", "AMD"],
        "years": [2026],
        "filing_types": ["10-Q", "8-K"],
        "source_tiers": ["primary_sec_filing", "company_authored_unaudited_sec_filing"],
        "metric_families": ["capex"],
    }
    coverage = {
        "summary": {"coverage_complete": False, "primary_task_support_complete": False},
        "source_coverage_gaps": [],
        "tasks": [
            {
                "task_id": "task_capex",
                "question_zh": "比较资本开支和管理层解释",
                "priority": "primary",
                "support_level": "partial",
                "required_tickers": ["NVDA", "AMD"],
                "missing_tickers": ["AMD"],
                "missing_metric_families": ["capex"],
                "missing_filing_types": ["10-Q"],
            }
        ],
    }
    paths = {
        "second_pass_trace_path": tmp_path / "run" / "second_pass_retrieval_trace.json",
        "trace_dir": tmp_path / "run" / "trace",
    }

    def fake_run_context(args, cases_path, trace_dir):
        interactive._write_jsonl(
            trace_dir / "trace_logs.jsonl",
            [
                {
                    "case_id": "second_pass_case",
                    "context_rows": [
                        {
                            "source_kind": "evidence_object",
                            "evidence_id": "AMD_2026_10Q_CAPEX",
                            "ticker": "AMD",
                            "fiscal_year": 2026,
                            "form_type": "10-Q",
                            "source_tier": "primary_sec_filing",
                            "retrieval_route": "filing_text",
                            "text": "AMD capex discussion",
                        }
                    ],
                    "context_policy": {"retrieval_plan_enabled": True},
                }
            ],
        )
        return {"context_runtime": {"fake": True}}

    monkeypatch.setattr(interactive, "_run_context", fake_run_context)

    result = interactive._stage_maybe_second_pass_retrieval(
        Namespace(),
        state,
        {"case_id": "unit_case", "query_contract": query_contract},
        query_contract,
        paths,
        {"context_rows": [], "context_summary": {}},
        [],
        coverage,
        lambda *args, **kwargs: None,
    )

    assert result["triggered"] is True
    assert result["added_context_row_count"] == 1
    assert result["context_rows"][0]["evidence_id"] == "AMD_2026_10Q_CAPEX"
    assert paths["second_pass_trace_path"].exists()
    assert result["trace"]["context_policy"]["second_pass_retrieval"]["added_context_rows"] == 1


class FakeObjectBM25:
    def search(self, query, top_k, filters):
        return [
            {
                "rank": 1,
                "score": 10.0,
                "object_id": "obj_nvda_revenue",
                "object_type": "metric",
                "source_evidence_id": "NVDA_2026_10Q_ITEM2",
                "ticker": "NVDA",
                "fiscal_year": 2026,
                "section": "Item 2",
                "preview": "revenue metric",
                "record": {
                    "object_type": "metric",
                    "ticker": "NVDA",
                    "fiscal_year": 2026,
                    "form_type": "10-Q",
                    "source_tier": "primary_sec_filing",
                    "metric_name": "revenue",
                    "raw_value": "100",
                    "source_evidence_id": "NVDA_2026_10Q_ITEM2",
                },
            }
        ][:top_k]


class ExplodingObjectBM25:
    def search(self, query, top_k, filters):
        raise AssertionError("ObjectBM25 should not be called when ledger_store_path is available")


class FakeBM25:
    def search(self, query, top_k, filters):
        return [
            {
                "rank": 1,
                "score": 5.0,
                "evidence_id": "evidence_nvda_mda",
                "ticker": "NVDA",
                "fiscal_year": 2026,
                "section": "Item 2",
                "text_preview": "management discussion explains revenue growth",
                "record": {
                    "ticker": "NVDA",
                    "fiscal_year": 2026,
                    "form_type": "10-Q",
                    "source_tier": "primary_sec_filing",
                    "text": "management discussion explains revenue growth",
                },
            }
        ][:top_k]


class CountingBM25(FakeBM25):
    def __init__(self):
        self.calls = 0

    def search(self, query, top_k, filters):
        self.calls += 1
        return super().search(query, top_k, filters)


class FakeReranker:
    def __init__(self):
        self.pairs = []

    def predict(self, pairs, batch_size, show_progress_bar):
        self.pairs = list(pairs)
        return [1.0 for _ in self.pairs]


def _ledger_fact_row(*, metric_id: str, period_role: str) -> dict:
    return {
        "metric_id": metric_id,
        "case_id": "store_case",
        "ticker": "NVDA",
        "fiscal_year": 2026,
        "source_fiscal_year": 2026,
        "period": "2026",
        "period_role": period_role,
        "source_type": "10-Q",
        "form_type": "10-Q",
        "source_tier": "primary_sec_filing",
        "metric_family": "revenue",
        "metric_role": "total_value",
        "metric_name": "Revenue",
        "raw_value_text": "$12,000",
        "display_value_zh": "12,000（百万美元）",
        "value": 12000.0,
        "unit": "usd_millions",
        "object_id": f"obj_nvda_revenue_{period_role}",
        "source_evidence_id": "NVDA_2026_10Q_ITEM2",
        "section": "Item 2",
        "source_text": "Revenue was $12,000 million.",
    }
