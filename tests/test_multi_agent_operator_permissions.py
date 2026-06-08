from __future__ import annotations

from sec_agent.multi_agent_runtime import (
    compile_multi_agent_retrieval_plan,
    derive_sec_search_runtime_policy,
    execute_evidence_operator_plan,
    tool_arguments_from_route,
    validate_operator_tool_call,
    validate_tool_observation_boundary,
)
import sec_agent.multi_agent_runtime as runtime
from sec_agent.tool_call_ledger import ToolCallLedger


def test_operator_permission_bridge_blocks_cross_source_tool() -> None:
    assert validate_operator_tool_call(agent_id="sec_operator", tool_name="sec_search_filings")["status"] == "pass"
    assert validate_operator_tool_call(agent_id="sec_operator", tool_name="sec_milvus_semantic_search")["status"] == "pass"

    blocked = validate_operator_tool_call(agent_id="sec_operator", tool_name="market_get_snapshot")

    assert blocked["status"] == "fail"
    assert blocked["error"] == "tool_not_allowed_for_agent:sec_operator:market_get_snapshot"


def test_relationship_graph_lookup_has_bounded_permission_boundary() -> None:
    permission = validate_operator_tool_call(
        agent_id="universe_relationship",
        tool_name="relationship_graph_lookup",
    )

    assert permission["status"] == "pass"
    assert permission["permission_boundary"] == "bounded_relationship_lookup"


def test_sec_search_arguments_filter_context_only_source_tiers() -> None:
    filing_args = tool_arguments_from_route(
        {
            "retrieval_route": "filing_text",
            "tickers": ["NVDA"],
            "years": [2026],
            "source_tiers": ["relationship_graph", "industry_snapshot"],
        },
        user_query="AI capex relationship",
    )
    eight_k_args = tool_arguments_from_route(
        {
            "retrieval_route": "8k_commentary",
            "tickers": ["NVDA"],
            "years": [2026],
            "source_tiers": ["relationship_graph"],
        },
        user_query="management commentary",
    )

    assert filing_args["source_tiers"] == ["primary_sec_filing", "company_authored_unaudited_sec_filing"]
    assert eight_k_args["source_tiers"] == ["company_authored_unaudited_sec_filing"]


def test_sec_search_runtime_policy_expands_sector_depth_retrieval_caps() -> None:
    args = tool_arguments_from_route(
        {
            "retrieval_route": "filing_text",
            "tickers": ["NVDA", "DELL", "ANET", "VRT"],
            "years": [2026],
            "candidate_budget": 120,
            "rerank_budget": 64,
        },
        user_query="AI infrastructure sector depth",
        state_context={
            "execution_mode": "deep_research",
            "bge_device": "cpu",
            "expected_relationship_pack_ids": ["ai_infra_power_transmission_v0_2"],
        },
    )

    assert args["candidate_budget"] == 480
    assert args["rerank_budget"] == 120
    assert args["evidence_top_k"] == 10
    assert args["object_top_k"] == 8
    assert args["reranker_candidate_limit"] == 480
    assert args["reranker_top_k"] == 120
    assert args["bge_device"] == "cpu"
    assert args["retrieval_runtime_policy"]["policy_name"] == "deep_research_sector_depth"


def test_sec_search_runtime_policy_auto_uses_cuda_when_available(monkeypatch) -> None:
    monkeypatch.setattr(runtime, "_cuda_available", lambda: True)

    policy = derive_sec_search_runtime_policy(
        {"execution_mode": "deep_research", "bge_device": "auto"},
        {"retrieval_route": "filing_text", "tickers": ["NVDA"]},
    )

    assert policy["bge_device"] == "cuda"
    assert policy["bge_device_policy"] == "auto_cuda_available"


def test_sec_search_runtime_policy_auto_uses_cuda_for_focused_answer_when_available(monkeypatch) -> None:
    monkeypatch.setattr(runtime, "_cuda_available", lambda: True)

    policy = derive_sec_search_runtime_policy(
        {"execution_mode": "focused_answer", "bge_device": "auto"},
        {"retrieval_route": "filing_text", "tickers": ["AMZN"]},
    )

    assert policy["bge_device"] == "cuda"
    assert policy["bge_device_policy"] == "auto_cuda_available"


def test_zero_runtime_context_values_do_not_override_policy_defaults() -> None:
    args = tool_arguments_from_route(
        {
            "retrieval_route": "filing_text",
            "tickers": ["NVDA", "DELL", "ANET", "VRT"],
            "years": [2026],
        },
        user_query="AI infrastructure sector depth",
        state_context={
            "execution_mode": "deep_research",
            "bge_device": "cpu",
            "evidence_top_k": 0,
            "object_top_k": 0,
            "reranker_candidate_limit": 0,
            "reranker_top_k": 0,
            "reranker_doc_max_chars": 0,
        },
    )

    assert args["evidence_top_k"] == 10
    assert args["object_top_k"] == 8
    assert args["reranker_candidate_limit"] == 480
    assert args["reranker_top_k"] == 120
    assert args["reranker_doc_max_chars"] == 2400


def test_milvus_semantic_route_arguments_require_typed_vector_filter() -> None:
    args = tool_arguments_from_route(
        {
            "retrieval_route": "milvus_semantic",
            "tickers": ["NVDA", "AMD"],
            "years": [2026],
            "filing_types": ["10-Q"],
            "source_tiers": ["primary_sec_filing", "market_snapshot"],
            "metric_families": ["revenue"],
            "vector_kinds": ["relationship_context", "paraphrase_context", "unknown_kind"],
        },
        user_query="AI capex supply-chain readthrough",
        state_context={
            "milvus_db_path": "milvus_lite.db",
            "milvus_collection_name": "fin_ab_expanded",
            "milvus_top_k": 32,
            "embedding_model": "BAAI/bge-m3",
        },
    )

    assert args["retrieval_route"] == "milvus_semantic"
    assert args["source_tiers"] == ["primary_sec_filing"]
    assert args["vector_kinds"] == ["relationship_context", "paraphrase_context"]
    assert args["typed_filter_required"] is True
    assert args["milvus_top_k"] == 32
    assert args["milvus_collection_name"] == "fin_ab_expanded"
    assert args["milvus_search_policy"]["not_exact_value_authority"] is True


def test_market_and_industry_operator_arguments_include_expanded_catalog_paths() -> None:
    market_args = tool_arguments_from_route(
        {"retrieval_route": "market_snapshot", "tickers": ["NVDA"]},
        user_query="market reaction",
        state_context={
            "market_evidence_path": "market.jsonl",
            "market_catalog_path": "catalog.duckdb",
            "market_snapshot_id": "market_v1",
            "market_as_of_date": "2026-06-06",
        },
    )
    industry_args = tool_arguments_from_route(
        {"retrieval_route": "industry_snapshot", "tickers": ["NVDA"]},
        user_query="power demand context",
        state_context={
            "industry_evidence_path": "industry.jsonl",
            "industry_snapshot_db_path": "industry.duckdb",
        },
    )

    assert market_args["market_evidence_path"] == "market.jsonl"
    assert market_args["market_catalog_path"] == "catalog.duckdb"
    assert industry_args["industry_evidence_path"] == "industry.jsonl"
    assert industry_args["industry_snapshot_db_path"] == "industry.duckdb"


def test_evidence_operator_plan_executes_mcp_shaped_calls_and_records_ledger() -> None:
    retrieval_plan = {
        "routes": [
            {
                "route_id": "task::filing_text",
                "task_id": "task",
                "retrieval_route": "filing_text",
                "tickers": ["MSFT"],
                "years": [2026],
                "filing_types": ["10-Q"],
                "source_tiers": ["primary_sec_filing"],
                "metric_families": ["capex"],
                "candidate_budget": 8,
                "rerank_budget": 4,
            },
            {
                "route_id": "task::market_snapshot",
                "task_id": "task",
                "retrieval_route": "market_snapshot",
                "tickers": ["MSFT"],
                "coverage_requirements": {"market_fields": ["return_3m"]},
            },
        ]
    }
    calls: list[tuple[str, dict]] = []

    def fake_executor(tool_name: str, args: dict) -> dict:
        calls.append((tool_name, args))
        if tool_name == "sec_search_filings":
            return {"status": "ok", "context_rows": [{"evidence_id": "SEC1"}], "artifact_refs": []}
        return {
            "status": "ok",
            "market_rows": [{"ticker": "MSFT", "return_3m": 0.1}],
            "snapshot_id": "snap_1",
            "as_of_date": "2026-05-30",
            "artifact_refs": [],
        }

    result = execute_evidence_operator_plan(
        retrieval_plan,
        turn_id="turn_1",
        ledger=ToolCallLedger(),
        state_context={"user_query": "compare MSFT", "market_snapshot_id": "snap_1", "market_as_of_date": "2026-05-30"},
        tool_executor=fake_executor,
    )

    assert [call[0] for call in calls] == ["sec_search_filings", "market_get_snapshot"]
    assert result["context_rows"][0]["evidence_id"] == "SEC1"
    assert result["market_snapshot_rows"][0]["ticker"] == "MSFT"
    assert len(result["tool_call_ledger"]["records"]) == 2
    assert result["tool_observations"][1]["boundary"]["status"] == "pass"


def test_evidence_operator_plan_executes_milvus_semantic_as_recall_supplement() -> None:
    retrieval_plan = {
        "routes": [
            {
                "route_id": "task::milvus_semantic",
                "task_id": "task",
                "retrieval_route": "milvus_semantic",
                "tickers": ["NVDA"],
                "years": [2026],
                "filing_types": ["10-Q"],
                "source_tiers": ["primary_sec_filing"],
                "vector_kinds": ["relationship_context"],
            }
        ]
    }
    calls: list[tuple[str, dict]] = []

    def fake_executor(tool_name: str, args: dict) -> dict:
        calls.append((tool_name, args))
        return {
            "status": "ok",
            "context_rows": [
                {
                    "evidence_id": "NVDA_SEM_REL",
                    "source_family": "primary_sec_filing",
                    "vector_kind": "relationship_context",
                    "ticker": "NVDA",
                }
            ],
            "vector_kind_counts": {"relationship_context": 1},
            "collection_name": args["milvus_collection_name"],
            "typed_filter_required": True,
            "semantic_route_role": "semantic_recall_supplement",
            "artifact_refs": [],
        }

    result = execute_evidence_operator_plan(
        retrieval_plan,
        turn_id="turn_milvus",
        ledger=ToolCallLedger(),
        state_context={"user_query": "NVDA supply chain", "milvus_db_path": "milvus.db", "milvus_collection_name": "fin_ab"},
        tool_executor=fake_executor,
    )

    assert [call[0] for call in calls] == ["sec_milvus_semantic_search"]
    assert calls[0][1]["vector_kinds"] == ["relationship_context"]
    assert calls[0][1]["query_probes"][0] == "NVDA supply chain"
    assert len(calls[0][1]["query_probes"]) >= 2
    assert any("upstream downstream" in probe for probe in calls[0][1]["query_probes"])
    assert result["context_rows"][0]["vector_kind"] == "relationship_context"
    assert result["tool_observations"][0]["boundary"]["allowed_claim_scope"] == "filing_semantic_recall_supplement"
    assert result["tool_call_ledger"]["records"][0]["metadata"]["runtime_summary"]["semantic_route_role"] == "semantic_recall_supplement"


def test_evidence_operator_records_ledger_missing_despite_primary_context() -> None:
    retrieval_plan = {
        "routes": [
            {
                "route_id": "task::ledger_first",
                "task_id": "task",
                "retrieval_route": "ledger_first",
                "tickers": ["NVDA"],
                "years": [2026],
                "filing_types": ["10-Q"],
                "source_tiers": ["primary_sec_filing"],
                "metric_families": ["revenue"],
            },
            {
                "route_id": "task::filing_text",
                "task_id": "task",
                "retrieval_route": "filing_text",
                "tickers": ["NVDA"],
                "years": [2026],
                "filing_types": ["10-Q"],
                "source_tiers": ["primary_sec_filing"],
                "metric_families": ["revenue"],
            },
        ]
    }

    def fake_executor(tool_name: str, args: dict) -> dict:
        if tool_name == "sec_query_exact_value_ledger":
            return {"status": "ok", "rows": [], "artifact_refs": []}
        return {
            "status": "ok",
            "context_rows": [
                {
                    "evidence_id": "nvda_10q_text",
                    "source_family": "primary_sec_filing",
                    "ticker": "NVDA",
                    "fiscal_year": 2026,
                    "form_type": "10-Q",
                    "summary": "NVDA primary filing text row.",
                }
            ],
            "runtime_ledger_rows": [],
            "artifact_refs": [],
        }

    result = execute_evidence_operator_plan(
        retrieval_plan,
        turn_id="turn_ledger_gap",
        ledger=ToolCallLedger(),
        state_context={"user_query": "NVDA revenue", "focus_tickers": ["NVDA"], "ledger_store_path": "ledger.duckdb"},
        tool_executor=fake_executor,
    )

    gaps = [gap for gap in result["source_gaps"] if gap.get("reason_code") == "ledger_missing_despite_context"]
    assert gaps
    assert gaps[0]["ticker"] == "NVDA"
    assert gaps[0]["source_available"] is True
    assert gaps[0]["exact_value_available"] is False


def test_ledger_first_without_store_falls_back_to_sec_search_runtime_ledger() -> None:
    retrieval_plan = {
        "routes": [
            {
                "route_id": "task::ledger_first",
                "task_id": "task",
                "retrieval_route": "ledger_first",
                "tickers": ["MSFT"],
                "years": [2026],
                "filing_types": ["10-Q"],
                "source_tiers": ["primary_sec_filing"],
                "metric_families": ["capex"],
                "candidate_budget": 24,
                "rerank_budget": 0,
            }
        ]
    }
    calls: list[tuple[str, dict]] = []

    def fake_executor(tool_name: str, args: dict) -> dict:
        calls.append((tool_name, args))
        return {
            "status": "ok",
            "context_rows": [
                {
                    "evidence_id": "msft_10q_capex_text",
                    "source_family": "primary_sec_filing",
                    "ticker": "MSFT",
                    "fiscal_year": 2026,
                    "form_type": "10-Q",
                }
            ],
            "runtime_ledger_rows": [
                {
                    "metric_id": "msft_capex_2026",
                    "source_family": "primary_sec_filing",
                    "ticker": "MSFT",
                    "fiscal_year": 2026,
                    "form_type": "10-Q",
                    "metric_family": "capex",
                }
            ],
            "artifact_refs": [],
            "candidate_counts": {"candidate_row_count_pre_rerank": 12, "candidate_sent_to_bge": 6},
        }

    result = execute_evidence_operator_plan(
        retrieval_plan,
        turn_id="turn_runtime_ledger_fallback",
        ledger=ToolCallLedger(),
        state_context={"user_query": "MSFT capex", "focus_tickers": ["MSFT"], "build_runtime_ledger": True},
        tool_executor=fake_executor,
    )

    assert [call[0] for call in calls] == ["sec_search_filings"]
    assert calls[0][1]["retrieval_route"] == "filing_text"
    assert calls[0][1]["retrieval_plan"]["routes"][0]["retrieval_route"] == "ledger_first"
    assert calls[0][1]["retrieval_plan"]["routes"][0]["rerank_budget"] > 0
    assert calls[0][1]["build_runtime_ledger"] is True
    assert calls[0][1]["candidate_budget"] >= 120
    assert calls[0][1]["rerank_budget"] > 0
    assert result["context_rows"][0]["ticker"] == "MSFT"
    assert result["runtime_ledger_rows"][0]["metric_family"] == "capex"
    assert result["tool_call_ledger"]["records"][0]["tool_name"] == "sec_search_filings"
    assert result["tool_call_ledger"]["records"][0]["metadata"]["fallback_from_retrieval_route"] == "ledger_first"
    assert not [gap for gap in result["source_gaps"] if gap.get("reason_code") == "ledger_store_path_unavailable"]


def test_relationship_graph_route_executes_and_returns_bounded_context_rows() -> None:
    retrieval_plan = {
        "routes": [
            {
                "route_id": "relationship_scope::relationship_graph",
                "task_id": "relationship_scope",
                "retrieval_route": "relationship_graph",
                "evidence_requirement_id": "req_relationship_scope",
                "tickers": ["NVDA", "MSFT"],
            }
        ]
    }
    calls: list[tuple[str, dict]] = []

    def fake_executor(tool_name: str, args: dict) -> dict:
        calls.append((tool_name, args))
        return {
            "status": "ok",
            "relationship_rows": [
                {
                    "evidence_ref": "rel_nvda_msft",
                    "source_family": "relationship_graph",
                    "focus_ticker": "NVDA",
                    "related_ticker": "MSFT",
                }
            ],
            "artifact_refs": [],
        }

    result = execute_evidence_operator_plan(
        retrieval_plan,
        turn_id="turn_relationship",
        ledger=ToolCallLedger(),
        state_context={"user_query": "NVDA Microsoft AI infrastructure relationship"},
        tool_executor=fake_executor,
    )

    assert [call[0] for call in calls] == ["relationship_graph_lookup"]
    assert result["tool_observations"][0]["status"] == "ok"
    assert result["context_rows"][0]["source_family"] == "relationship_graph"
    assert result["tool_call_ledger"]["records"][0]["agent_id"] == "universe_relationship"


def test_evidence_operator_duplicate_call_is_blocked() -> None:
    retrieval_plan = {
        "routes": [
            {"route_id": "a", "retrieval_route": "filing_text", "tickers": ["MSFT"], "years": [2026]},
            {"route_id": "b", "retrieval_route": "filing_text", "tickers": ["MSFT"], "years": [2026]},
        ]
    }

    result = execute_evidence_operator_plan(retrieval_plan, turn_id="turn_1", ledger=ToolCallLedger(), dry_run=True)

    assert result["tool_observations"][0]["status"] == "dry_run"
    assert result["tool_observations"][1]["status"] == "blocked"
    assert result["tool_observations"][1]["error"] == "duplicate_tool_call_blocked"


def test_evidence_operator_groups_sec_search_routes_for_single_real_execution() -> None:
    retrieval_plan = {
        "schema_version": "sec_agent_retrieval_plan_v0.1",
        "tasks": [{"task_id": "task", "retrieval_routes": ["ledger_first", "filing_text", "8k_commentary"]}],
        "routes": [
            {
                "route_id": "task::ledger_first",
                "task_id": "task",
                "retrieval_route": "ledger_first",
                "tickers": ["MSFT"],
                "years": [2026],
                "filing_types": ["10-Q"],
                "source_tiers": ["primary_sec_filing"],
                "metric_families": ["capex"],
            },
            {
                "route_id": "task::filing_text",
                "task_id": "task",
                "retrieval_route": "filing_text",
                "tickers": ["MSFT"],
                "years": [2026],
                "filing_types": ["10-Q"],
                "source_tiers": ["primary_sec_filing"],
                "metric_families": ["capex"],
            },
            {
                "route_id": "task::8k_commentary",
                "task_id": "task",
                "retrieval_route": "8k_commentary",
                "tickers": ["MSFT"],
                "years": [2026],
                "filing_types": ["8-K"],
                "source_tiers": ["company_authored_unaudited_sec_filing"],
                "metric_families": ["capex"],
            },
        ],
    }
    calls: list[tuple[str, dict]] = []

    def fake_executor(tool_name: str, args: dict) -> dict:
        calls.append((tool_name, args))
        grouped_routes = args["retrieval_plan"]["routes"]
        return {
            "status": "ok",
            "context_rows": [
                {
                    "evidence_ref": "msft_text",
                    "selection_route_ids": [route["route_id"]],
                    "retrieval_route": route["retrieval_route"],
                }
                for route in grouped_routes
            ],
            "runtime_ledger_rows": [{"metric_id": "msft_capex", "ticker": "MSFT"}],
            "artifact_refs": [],
            "candidate_counts": {"candidate_row_count_pre_rerank": 12, "candidate_sent_to_bge": 6},
        }

    result = execute_evidence_operator_plan(
        retrieval_plan,
        turn_id="turn_grouped_sec",
        ledger=ToolCallLedger(),
        state_context={"user_query": "MSFT capex", "focus_tickers": ["MSFT"], "build_runtime_ledger": True},
        tool_executor=fake_executor,
    )

    assert [call[0] for call in calls] == ["sec_search_filings"]
    assert [route["retrieval_route"] for route in calls[0][1]["retrieval_plan"]["routes"]] == [
        "ledger_first",
        "filing_text",
        "8k_commentary",
    ]
    assert calls[0][1]["build_runtime_ledger"] is True
    assert len(result["context_rows"]) == 3
    assert [row["status"] for row in result["tool_observations"]] == ["ok", "cached", "cached"]
    records = result["tool_call_ledger"]["records"]
    assert [record["status"] for record in records] == ["ok", "cached", "cached"]
    assert {record["agent_id"] for record in records} == {"sec_operator", "eight_k_operator"}


def test_sec_text_route_does_not_build_runtime_ledger_without_ledger_first() -> None:
    retrieval_plan = {
        "routes": [
            {
                "route_id": "task::filing_text",
                "task_id": "task",
                "retrieval_route": "filing_text",
                "tickers": ["NVDA"],
                "years": [2026],
                "filing_types": ["10-Q"],
                "source_tiers": ["primary_sec_filing"],
                "metric_families": ["revenue"],
            }
        ],
    }
    calls: list[tuple[str, dict]] = []

    def fake_executor(tool_name: str, args: dict) -> dict:
        calls.append((tool_name, args))
        return {
            "status": "ok",
            "context_rows": [{"evidence_ref": "nvda_text", "retrieval_route": "filing_text"}],
            "runtime_ledger_rows": [],
            "artifact_refs": [],
        }

    execute_evidence_operator_plan(
        retrieval_plan,
        turn_id="turn_sec_text_no_runtime_ledger",
        ledger=ToolCallLedger(),
        state_context={"user_query": "NVDA revenue", "focus_tickers": ["NVDA"], "build_runtime_ledger": True},
        tool_executor=fake_executor,
    )

    assert [call[0] for call in calls] == ["sec_search_filings"]
    assert calls[0][1]["build_runtime_ledger"] is False


def test_market_and_industry_boundary_checks_are_explicit() -> None:
    market = validate_tool_observation_boundary("market_get_snapshot", {"snapshot_id": "snap"})
    industry = validate_tool_observation_boundary("industry_get_snapshot", {"industry_rows": []})
    milvus = validate_tool_observation_boundary("sec_milvus_semantic_search", {"context_rows": [{"vector_kind": "narrative_chunk"}]})

    assert market["status"] == "fail"
    assert market["missing"] == ["as_of_date"]
    assert industry["status"] == "pass"
    assert industry["allowed_claim_scope"] == "industry_context_only"
    assert industry["prohibited_claim_scope"] == "company_reported_financial_fact"
    assert milvus["status"] == "pass"
    assert milvus["prohibited_claim_scope"] == "exact_value_authority"


def test_evidence_requirement_plan_compiles_to_same_route_intent() -> None:
    contract = {
        "focus_tickers": ["NVDA"],
        "search_scope_tickers": ["NVDA"],
        "years": [2026],
        "filing_types": ["8-K"],
        "source_tiers": ["company_authored_unaudited_sec_filing"],
        "metric_families": ["capex"],
    }
    evidence_requirement_plan = {
        "requirements": [
            {
                "requirement_id": "req_8k",
                "task_id": "capex_commentary",
                "question": "Need 8-K management commentary on capex.",
                "tickers": ["NVDA"],
                "years": [2026],
                "filing_types": ["8-K"],
                "source_tiers": ["company_authored_unaudited_sec_filing"],
                "metric_families": ["capex"],
                "evidence_routes": ["8k_commentary"],
            }
        ]
    }

    plan = compile_multi_agent_retrieval_plan(evidence_requirement_plan, query_contract=contract, case={"case_id": "unit"})

    assert [route["retrieval_route"] for route in plan["routes"]] == ["8k_commentary"]
    assert plan["routes"][0]["source_tiers"] == ["company_authored_unaudited_sec_filing"]


def test_evidence_requirement_plan_accepts_explicit_milvus_semantic_route() -> None:
    contract = {
        "focus_tickers": ["NVDA"],
        "search_scope_tickers": ["NVDA"],
        "years": [2026],
        "filing_types": ["10-Q"],
        "source_tiers": ["primary_sec_filing"],
        "metric_families": ["capex"],
    }
    evidence_requirement_plan = {
        "requirements": [
            {
                "requirement_id": "req_semantic",
                "task_id": "semantic_recall",
                "question": "Need typed semantic recall for supply-chain discussion.",
                "tickers": ["NVDA"],
                "years": [2026],
                "filing_types": ["10-Q"],
                "source_tiers": ["primary_sec_filing"],
                "metric_families": ["capex"],
                "evidence_routes": ["milvus_semantic"],
                "coverage_requirements": {"vector_kinds": ["relationship_context"]},
            }
        ]
    }

    plan = compile_multi_agent_retrieval_plan(evidence_requirement_plan, query_contract=contract, case={"case_id": "unit"})

    assert [route["retrieval_route"] for route in plan["routes"]] == ["milvus_semantic"]
    assert plan["routes"][0]["source_tiers"] == ["primary_sec_filing"]
    assert plan["routes"][0]["section_hints"] == ["typed_semantic_vector", "semantic_scope", "vector_kind_filter"]
