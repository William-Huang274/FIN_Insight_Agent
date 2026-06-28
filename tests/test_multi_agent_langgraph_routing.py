from __future__ import annotations

import json
from pathlib import Path

from sec_agent.langgraph_orchestrator import (
    _render_deterministic_lookup_answer,
    _node_research_lead_plan,
    _node_validate_activation_plan,
    _route_after_multi_agent_reflection,
    build_multi_agent_summary_artifact_payload,
    build_multi_agent_orchestration_graph,
    build_multi_agent_orchestration_graph_from_env,
    make_multi_agent_smoke_state,
    multi_agent_node_order,
)
from sec_agent.multi_agent_runtime import build_agent_data_view, compile_multi_agent_retrieval_plan, tool_arguments_from_route
from sec_agent.tool_call_ledger import ToolCallLedger


def test_multi_agent_graph_runs_focused_path_and_writes_summary(tmp_path: Path) -> None:
    graph = build_multi_agent_orchestration_graph()
    initial = make_multi_agent_smoke_state(
        user_query="分析 AMZN 最近披露的利润率变化，并结合管理层解释给出简短判断。",
        output_dir=tmp_path,
        query_contract=_query_contract(["AMZN"], source_tiers=["primary_sec_filing", "company_authored_unaudited_sec_filing"]),
        focus_tickers=["AMZN"],
        search_scope_tickers=["AMZN"],
    )

    result = graph.invoke(initial, config={"configurable": {"thread_id": "unit-multi-agent-focused"}})
    nodes = [row["node"] for row in result["node_trace"]]
    summary = json.loads((tmp_path / "multi_agent_summary.json").read_text(encoding="utf-8"))

    assert result["status"] == "completed"
    assert result["agent_activation_plan"]["execution_mode"] == "focused_answer"
    assert result["agent_activation_validation"]["status"] == "pass"
    assert result["multi_agent_routing_trace"]["mode"] == "focused_answer"
    assert "research_lead_plan" in nodes
    assert nodes.index("evidence_fusion_selector") < nodes.index("coverage_reflection")
    assert "memo_writer" in nodes
    assert "optional_specialist_subgraph" not in nodes
    assert result["judgment_plan"]["aggregation_policy"] == "focused_answer_claim_cards_from_bounded_rows_v0_1"
    assert result["judgment_plan"]["focused_answer_bridge"]["status"] == "used"
    assert result["memo_answer"]["answer_status"] == "draft"
    assert summary["execution_mode"] == "focused_answer"
    assert summary["evidence_rows"]["tool_observation_count"] >= 1
    assert summary["evidence_rows"]["retrieval_route_count"] >= 1
    assert "evidence_fusion" in summary
    assert "bounded_gap_register" in summary
    assert summary["payload_policy"]["raw_evidence"] == "not_included"


def test_multi_agent_graph_runs_evidence_fusion_before_coverage(tmp_path: Path) -> None:
    def injected_execute(state: dict) -> dict:
        return {
            "tool_observations": [],
            "tool_call_ledger": state.get("tool_call_ledger") or ToolCallLedger().to_dict(),
            "runtime_ledger_rows": [
                {
                    "evidence_ref": "msft_capex_ledger",
                    "source_family": "primary_sec_filing",
                    "ticker": "MSFT",
                    "metric_family": "capex",
                    "value": "24242",
                }
            ],
            "source_gaps": [
                {
                    "gap_id": "gap_market_share_tracker",
                    "source_family": "public_source_context",
                    "ticker": "MSFT",
                    "reason": "commercial tracker required for true market share",
                }
            ],
        }

    graph = build_multi_agent_orchestration_graph(
        execute_evidence_operators=injected_execute,
        stop_after_node="coverage_reflection",
    )
    initial = make_multi_agent_smoke_state(
        user_query="分析 MSFT 的 capex 与产品表现支撑。",
        output_dir=tmp_path,
        query_contract=_query_contract(["MSFT"], source_tiers=["primary_sec_filing"]),
        focus_tickers=["MSFT"],
        search_scope_tickers=["MSFT"],
    )
    initial["product_evidence_rows"] = [
        {
            "evidence_ref": "msft_product_runtime",
            "source_family": "company_product_evidence_graph",
            "ticker": "MSFT",
            "product_or_segment": "Cloud",
            "metric_family": "product_revenue",
            "promotion_status": "runtime_fact_allowed",
            "value": "100",
        }
    ]  # type: ignore[literal-required]
    initial["public_source_context_rows"] = [
        {
            "evidence_ref": "msft_public_context",
            "source_family": "public_source_context",
            "ticker": "MSFT",
            "summary": "public context only",
            "exact_value_authority": True,
        }
    ]  # type: ignore[literal-required]

    result = graph.invoke(initial, config={"configurable": {"thread_id": "unit-evidence-fusion-before-coverage"}})
    nodes = [row["node"] for row in result["node_trace"]]
    fusion = result["evidence_fusion_bundle"]
    summary = build_multi_agent_summary_artifact_payload(result)

    assert nodes.index("evidence_fusion_selector") < nodes.index("coverage_reflection")
    assert result["status"] == "stopped_after_node"
    assert fusion["summary"]["exact_authority_row_count"] == 2
    assert fusion["summary"]["product_runtime_fact_count"] == 1
    assert fusion["summary"]["public_exact_authority_violation_count"] == 0
    assert result["bounded_gap_register"]["summary"]["commercial_tracker_gap_count"] == 1
    assert summary["evidence_fusion"]["exact_authority_row_count"] == 2
    assert summary["bounded_gap_register"]["commercial_tracker_gap_count"] == 1


def test_multi_agent_graph_first_pass_merges_product_and_public_source_rows(tmp_path: Path) -> None:
    def injected_execute(state: dict) -> dict:
        return {
            "tool_observations": [],
            "tool_call_ledger": state.get("tool_call_ledger") or ToolCallLedger().to_dict(),
            "product_evidence_rows": [
                {
                    "evidence_ref": "aapl_services_product_kpi",
                    "source_family": "company_product_evidence_graph",
                    "ticker": "AAPL",
                    "product_or_segment": "Services",
                    "metric_family": "product_revenue",
                    "promotion_status": "runtime_fact_allowed",
                    "exact_value_authority": True,
                    "value": "96.2 billion USD",
                }
            ],
            "public_source_context_rows": [
                {
                    "evidence_ref": "aapl_iphone_official_surface",
                    "source_family": "live_public_web_context",
                    "runtime_source_family": "public_source_context",
                    "source_id": "company_product_pages",
                    "source_layer_id": "L2",
                    "ticker": "AAPL",
                    "product_or_segment": "iPhone",
                    "structured_context_type": "product_spec_context",
                    "context_only": True,
                    "exact_value_authority": False,
                }
            ],
        }

    graph = build_multi_agent_orchestration_graph(
        execute_evidence_operators=injected_execute,
        stop_after_node="evidence_fusion_selector",
    )
    initial = make_multi_agent_smoke_state(
        user_query="分析 AAPL 产品收入和产品线证据。",
        output_dir=tmp_path,
        query_contract=_query_contract(["AAPL"], source_tiers=["company_product_evidence_graph", "public_source_context"]),
        focus_tickers=["AAPL"],
        search_scope_tickers=["AAPL"],
    )

    result = graph.invoke(initial, config={"configurable": {"thread_id": "unit-first-pass-product-public-rows"}})
    product_view = build_agent_data_view("product_technology_analyst", result)

    assert result["evidence_fusion_bundle"]["summary"]["product_runtime_fact_count"] == 1
    assert result["evidence_fusion_bundle"]["summary"]["public_exact_authority_violation_count"] == 0
    assert {row["evidence_ref"] for row in result["product_evidence_rows"]} == {"aapl_services_product_kpi"}
    assert {row["evidence_ref"] for row in result["public_source_context_rows"]} == {"aapl_iphone_official_surface"}
    product_refs = {row["evidence_ref"] for row in product_view["bounded_evidence_rows"]}
    assert {"aapl_services_product_kpi", "aapl_iphone_official_surface"} <= product_refs


def test_multi_agent_graph_attaches_runtime_source_context_store_from_state_config(tmp_path: Path) -> None:
    product_path = tmp_path / "runtime_product_rows.jsonl"
    public_path = tmp_path / "runtime_public_rows.jsonl"
    _write_jsonl(
        product_path,
        [
            {
                "evidence_ref": "nvda_data_center_product_kpi",
                "source_family": "company_product_evidence_graph",
                "runtime_source_family": "company_product_evidence_graph",
                "source_id": "company_reported_product_operating_metrics",
                "source_layer_id": "L1",
                "ticker": "NVDA",
                "fiscal_year": 2025,
                "product_or_segment": "Data Center",
                "metric_family": "product_revenue",
                "promotion_status": "runtime_fact_allowed",
                "exact_value_authority": True,
                "value": "115.2 billion USD",
            }
        ],
    )
    _write_jsonl(
        public_path,
        [
            {
                "evidence_ref": "nvda_blackwell_official_surface",
                "source_family": "live_public_web_context",
                "runtime_source_family": "public_source_context",
                "source_id": "company_product_pages",
                "source_layer_id": "L2",
                "ticker": "NVDA",
                "product_or_segment": "Blackwell",
                "structured_context_type": "product_spec_context",
                "context_only": True,
                "exact_value_authority": False,
            }
        ],
    )
    graph = build_multi_agent_orchestration_graph(stop_after_node="evidence_fusion_selector")
    initial = make_multi_agent_smoke_state(
        user_query="分析 NVDA 产品线证据。",
        output_dir=tmp_path,
        query_contract=_query_contract(["NVDA"], source_tiers=["company_product_evidence_graph", "public_source_context"]),
        focus_tickers=["NVDA"],
        search_scope_tickers=["NVDA"],
    )
    initial["multi_agent_context"] = {
        "runtime_source_context": {
            "enabled": True,
            "paths": {"product": str(product_path), "public": str(public_path)},
            "max_product_rows_per_ticker": 4,
            "max_public_rows_per_ticker": 4,
            "max_unbound_public_rows": 0,
        }
    }  # type: ignore[literal-required]

    result = graph.invoke(initial, config={"configurable": {"thread_id": "unit-runtime-source-context-store"}})
    product_view = build_agent_data_view("product_technology_analyst", result)

    assert result["runtime_source_context_store"]["summary"]["selected_row_count"] == 2
    assert result["evidence_fusion_bundle"]["summary"]["product_runtime_fact_count"] == 1
    assert result["evidence_fusion_bundle"]["summary"]["public_exact_authority_violation_count"] == 0
    product_refs = {row["evidence_ref"] for row in product_view["bounded_evidence_rows"]}
    assert {"nvda_data_center_product_kpi", "nvda_blackwell_official_surface"} <= product_refs


def test_multi_agent_graph_records_evidence_fanout_barrier_when_enabled(tmp_path: Path) -> None:
    graph = build_multi_agent_orchestration_graph(stop_after_node="evidence_fusion_selector")
    initial = make_multi_agent_smoke_state(
        user_query="比较 MSFT 的基本面和市场反应。",
        output_dir=tmp_path,
        query_contract=_query_contract(["MSFT"], source_tiers=["primary_sec_filing", "market_snapshot"]),
        focus_tickers=["MSFT"],
        search_scope_tickers=["MSFT"],
    )
    initial["multi_agent_context"] = {"evidence_operator_fanout": True, "evidence_operator_fanout_workers": 2}  # type: ignore[literal-required]

    result = graph.invoke(initial, config={"configurable": {"thread_id": "unit-evidence-fanout-barrier"}})

    barrier = result["evidence_operator_fanout_barrier"]
    assert result["status"] == "stopped_after_node"
    assert barrier["schema_version"] == "sec_agent_fanout_barrier_v0.1"
    assert barrier["input_shard_count"] >= 1
    assert barrier["failed_shard_count"] == 0
    assert result["evidence_operator_fanout_plan"]["schema_version"] == "sec_agent_evidence_operator_fanout_plan_v0.1"


def test_multi_agent_graph_deterministic_run_artifact_skips_memo(tmp_path: Path) -> None:
    graph = build_multi_agent_orchestration_graph()
    initial = make_multi_agent_smoke_state(
        user_query="查看已有 run 的 coverage 和 graph state，不要重新跑检索。",
        output_dir=tmp_path,
    )
    initial["multi_agent_context"] = {"run_dir": "eval/sec_cases/outputs/example_run"}  # type: ignore[literal-required]

    result = graph.invoke(initial, config={"configurable": {"thread_id": "unit-multi-agent-artifact"}})
    nodes = [row["node"] for row in result["node_trace"]]

    assert result["agent_activation_plan"]["execution_mode"] == "deterministic_lookup"
    assert "memo_writer" not in nodes
    assert "renderer" in nodes
    assert result["agent_activation_plan"]["allowed_source_families"] == ["run_artifact"]


def test_multi_agent_graph_standard_path_runs_specialists(tmp_path: Path) -> None:
    graph = build_multi_agent_orchestration_graph()
    initial = make_multi_agent_smoke_state(
        user_query="写一段投研 memo，比较 NVDA 和 AMD 的基本面、管理层解释、市场反应和估值分歧。",
        output_dir=tmp_path,
        query_contract=_query_contract(["NVDA", "AMD"], source_tiers=["primary_sec_filing", "company_authored_unaudited_sec_filing", "market_snapshot"]),
        focus_tickers=["NVDA", "AMD"],
        search_scope_tickers=["NVDA", "AMD"],
    )

    result = graph.invoke(initial, config={"configurable": {"thread_id": "unit-multi-agent-standard"}})
    nodes = [row["node"] for row in result["node_trace"]]

    assert result["agent_activation_plan"]["execution_mode"] == "standard_memo"
    assert "optional_specialist_subgraph" in nodes
    assert len(result["specialist_outputs"]) == 3
    assert all(output["schema_version"] == "sec_agent_specialist_memolet_v0.1" for output in result["specialist_outputs"])
    assert result["judgment_plan"]["aggregation_policy"] == "rank_supported_claim_cards_preserve_conflicts_no_average"
    assert result["judgment_plan"]["memo_outline"]
    assert result["specialist_verification"]["memo_writer_allowed"] is True
    assert result["specialist_fanout_barrier"]["schema_version"] == "sec_agent_specialist_fanout_barrier_v0.1"
    assert result["claim_card_store_barrier"]["schema_version"] == "sec_agent_claim_card_store_barrier_v0.1"
    assert result["adjudicator_barrier"]["schema_version"] == "sec_agent_adjudicator_barrier_v0.1"
    summary = json.loads((tmp_path / "multi_agent_summary.json").read_text(encoding="utf-8"))
    assert "claim_card_stats" in summary["judgment_plan"]
    assert "claim_card_stats" in summary["verified_judgment_plan"]
    assert summary["judgment_plan"]["memo_thesis_pack"]["present"] is True
    assert summary["graph_barriers"]["specialist_fanout"]["schema_version"] == "sec_agent_specialist_fanout_barrier_v0.1"
    assert summary["graph_barriers"]["claim_card_store"]["schema_version"] == "sec_agent_claim_card_store_barrier_v0.1"


def test_research_lead_enables_product_intelligence_runtime_for_product_lane() -> None:
    planned = _node_research_lead_plan(
        {
            "run_id": "unit-product-intelligence-autoload",
            "user_query": "Compare NVDA Blackwell GPU specs, AMD MI300 competitive positioning, and AI server customer deployments.",
            "query_contract": {
                "focus_tickers": ["NVDA"],
                "search_scope_tickers": ["NVDA", "AMD", "DELL"],
                "metric_families": ["product_spec", "customer_deployment", "supply_chain"],
                "source_tiers": ["primary_sec_filing", "company_product_evidence_graph"],
            },
        }
    )
    validated = _node_validate_activation_plan(planned)

    assert "product_technology_analyst" in validated["agent_activation_plan"]["activate_agents"]
    assert "company_product_evidence_graph" in validated["agent_activation_plan"]["allowed_source_families"]
    assert validated["product_intelligence_runtime_autoload"] is True
    assert validated["product_intelligence_runtime_policy"]["status"] == "enabled"
    assert "product_specialist_active" in validated["product_intelligence_runtime_policy"]["reason_codes"]
    assert validated["multi_agent_routing_trace"]["product_intelligence_runtime"]["status"] == "enabled"


def test_research_lead_respects_product_intelligence_runtime_override() -> None:
    planned = _node_research_lead_plan(
        {
            "run_id": "unit-product-intelligence-autoload-disabled",
            "user_query": "Compare NVDA Blackwell GPU specs and customer deployment evidence.",
            "query_contract": {
                "focus_tickers": ["NVDA"],
                "search_scope_tickers": ["NVDA", "AMD"],
                "metric_families": ["product_spec", "customer_deployment"],
                "source_tiers": ["primary_sec_filing", "company_product_evidence_graph"],
            },
            "product_intelligence_runtime_autoload": False,
        }
    )
    validated = _node_validate_activation_plan(planned)

    assert "product_technology_analyst" in validated["agent_activation_plan"]["activate_agents"]
    assert validated["product_intelligence_runtime_autoload"] is False
    assert validated["product_intelligence_runtime_policy"]["decision_source"] == "operator_override"
    assert validated["product_intelligence_runtime_policy"]["status"] == "disabled"


def test_validate_activation_plan_respects_direct_product_intelligence_runtime_override() -> None:
    planned = _node_research_lead_plan(
        {
            "run_id": "unit-product-intelligence-direct-override-seed",
            "user_query": "Compare NVDA Blackwell GPU specs and customer deployment evidence.",
            "query_contract": {
                "focus_tickers": ["NVDA"],
                "search_scope_tickers": ["NVDA", "AMD"],
                "metric_families": ["product_spec", "customer_deployment"],
                "source_tiers": ["primary_sec_filing", "company_product_evidence_graph"],
            },
        }
    )
    validated = _node_validate_activation_plan(
        {
            "run_id": "unit-product-intelligence-direct-override",
            "user_query": planned["user_query"],
            "query_contract": planned["query_contract"],
            "agent_activation_plan": planned["agent_activation_plan"],
            "product_intelligence_runtime_autoload": False,
        }
    )

    assert validated["agent_activation_validation"]["status"] == "pass"
    assert validated["product_intelligence_runtime_autoload"] is False
    assert validated["product_intelligence_runtime_policy"]["decision_source"] == "operator_override"


def test_multi_agent_summary_preserves_specialist_prompt_diagnostics() -> None:
    payload = build_multi_agent_summary_artifact_payload(
        {
            "run_id": "unit-run",
            "status": "completed",
            "agent_activation_plan": {"execution_mode": "deep_research", "activate_agents": ["fundamental_analyst"]},
            "specialist_route_results": [
                {
                    "agent_id": "fundamental_analyst",
                    "status": "pass",
                    "priority": "primary",
                    "input_tokens": 123,
                    "prompt_bounded_evidence_row_count": 12,
                    "prompt_relationship_summary_row_count": 0,
                    "prompt_row_distribution": {
                        "schema_version": "sec_agent_prompt_row_distribution_v0.1",
                        "row_count": 12,
                        "by_source_family": {"primary_sec_filing": 12},
                    },
                    "input_coverage_summary": {"focus_ticker_primary_row_counts": {"NVDA": 6}},
                }
            ],
        }
    )

    route = payload["specialists"]["route_results"][0]
    assert route["prompt_bounded_evidence_row_count"] == 12
    assert route["prompt_row_distribution"]["by_source_family"]["primary_sec_filing"] == 12
    assert route["input_coverage_summary"]["focus_ticker_primary_row_counts"]["NVDA"] == 6


def test_multi_agent_graph_blocks_unsupported_specialist_claims_before_memo_writer(tmp_path: Path) -> None:
    def injected_specialists(_state: dict) -> dict:
        return {
            "specialist_outputs": [
                {
                    "agent_id": "risk_counterevidence_analyst",
                    "unsupported_claims": [{"claim": "A named customer changed orders.", "reason": "not in bounded evidence"}],
                }
            ]
        }

    graph = build_multi_agent_orchestration_graph(run_specialist_analysts=injected_specialists)
    initial = make_multi_agent_smoke_state(
        user_query="写一段投研 memo，比较 NVDA 和 AMD 的基本面、管理层解释、市场反应和估值分歧。",
        output_dir=tmp_path,
        query_contract=_query_contract(["NVDA", "AMD"], source_tiers=["primary_sec_filing", "company_authored_unaudited_sec_filing", "market_snapshot"]),
        focus_tickers=["NVDA", "AMD"],
        search_scope_tickers=["NVDA", "AMD"],
    )

    result = graph.invoke(initial, config={"configurable": {"thread_id": "unit-multi-agent-specialist-block"}})

    assert result["specialist_verification"]["status"] == "fail"
    assert result["specialist_verification"]["memo_writer_allowed"] is False
    assert result["memo_answer"]["answer_status"] == "blocked_by_specialist_verification"


def test_multi_agent_graph_quality_second_pass_runs_before_memo_when_claim_cards_miss_required_ticker(tmp_path: Path) -> None:
    calls: list[dict] = []

    def injected_specialists(state: dict) -> dict:
        calls.append(dict(state))
        return {
            "specialist_outputs": [
                {
                    "agent_id": "fundamental_analyst",
                    "status": "pass",
                    "observations": [
                        {
                            "claim": "NVDA capex evidence supports the focal thesis.",
                            "ticker_scope": ["NVDA"],
                            "metric_scope": ["capex"],
                            "memo_slot": "fundamentals",
                            "materiality": "high",
                            "direction": "positive",
                            "evidence_refs": ["nvda_capex_ref"],
                            "source_families": ["primary_sec_filing"],
                        }
                    ],
                }
            ]
        }

    graph = build_multi_agent_orchestration_graph(run_specialist_analysts=injected_specialists)
    result = graph.invoke(
        make_multi_agent_smoke_state(
            user_query="从 AI capex 产业链角度分析 NVDA 和 AMD 的基本面、供应链传导和反证风险。",
            output_dir=tmp_path,
            query_contract=_query_contract(
                ["NVDA", "AMD"],
                source_tiers=["primary_sec_filing", "company_authored_unaudited_sec_filing", "market_snapshot", "industry_snapshot", "relationship_graph"],
            ),
            focus_tickers=["NVDA", "AMD"],
            search_scope_tickers=["NVDA", "AMD"],
        ),
        config={"configurable": {"thread_id": "unit-multi-agent-quality-second-pass"}},
    )
    nodes = [row["node"] for row in result["node_trace"]]

    assert result["agent_activation_plan"]["execution_mode"] == "deep_research"
    assert "optional_second_pass" in nodes
    assert result["quality_second_pass_attempted"] is True
    assert result["second_pass_result"]["trigger"] == "quality_second_pass"
    assert len(calls) >= 2


def test_quality_second_pass_caps_remaining_agent_budget_without_top_level_loop_break(tmp_path: Path) -> None:
    ledger = ToolCallLedger()
    for index in range(3):
        ledger.record_tool_call(
            turn_id="prior",
            agent_id="sec_operator",
            tool_name="sec_query_exact_value_ledger",
            arguments={"route": f"prior_{index}"},
            row_count=1,
        )

    graph = build_multi_agent_orchestration_graph(
        entry_node="optional_second_pass",
        stop_after_node="optional_second_pass",
    )
    state = make_multi_agent_smoke_state(
        user_query="quality second pass only",
        output_dir=tmp_path,
        query_contract=_query_contract(["NVDA"]),
        focus_tickers=["NVDA"],
        search_scope_tickers=["NVDA"],
    )
    state["agent_activation_plan"] = {
        "execution_mode": "deep_research",
        "activate_agents": ["research_lead", "sec_operator", "fundamental_analyst", "memo_writer"],
        "allowed_source_families": ["primary_sec_filing"],
        "max_tool_calls_total": 12,
        "max_tool_calls_per_agent": 4,
    }
    state["multi_agent_context"] = {"ledger_store_path": "unit-ledger.duckdb"}
    state["tool_call_ledger"] = ledger.to_dict()
    state["multi_agent_reflection_report"] = {
        "sufficiency_level": "partial",
        "source_available": True,
        "trigger": "quality_second_pass",
        "second_pass_requests": [
            {
                "request_id": "quality_req",
                "tickers": ["NVDA"],
                "years": [2026],
                "filing_types": ["10-Q"],
                "metric_families": ["revenue"],
                "evidence_routes": ["ledger_first", "filing_text"],
            }
        ],
    }

    result = graph.invoke(state, config={"configurable": {"thread_id": "unit-quality-second-pass-budget-suppressed"}})

    assert result["second_pass_result"]["trigger"] == "quality_second_pass"
    assert result["second_pass_result"]["added_row_count"] >= 1
    assert "suppressed_loop_break_reason" not in result["second_pass_result"]
    assert result["second_pass_retrieval_plan"]["route_budget_pruning"]["used_tool_calls_by_agent"]["sec_operator"] == 3
    assert result["second_pass_retrieval_plan"]["route_budget_pruning"]["dropped_routes"][0]["reason"] == "max_tool_calls_per_agent"
    assert result["loop_break_reason"] == ""
    assert result["tool_call_ledger"]["loop_break_reason"] == ""


def test_second_pass_hard_gate_blocks_commercial_gap_before_tools(tmp_path: Path) -> None:
    graph = build_multi_agent_orchestration_graph(
        entry_node="optional_second_pass",
        stop_after_node="optional_second_pass",
    )
    state = make_multi_agent_smoke_state(
        user_query="commercial gap second pass only",
        output_dir=tmp_path,
        query_contract=_query_contract(["PFE"], source_tiers=["public_source_context", "industry_snapshot"]),
        focus_tickers=["PFE"],
        search_scope_tickers=["PFE"],
    )
    state["agent_activation_plan"] = {
        "execution_mode": "deep_research",
        "activate_agents": ["research_lead", "industry_supply_chain_analyst", "memo_writer"],
        "allowed_source_families": ["public_source_context", "industry_snapshot"],
        "max_second_pass_rounds": 1,
    }
    state["multi_agent_reflection_report"] = {
        "sufficiency_level": "partial",
        "source_available": True,
        "trigger": "coverage_reflection",
        "missing_requirements": [
            {
                "requirement_id": "req_true_rx_volume",
                "task_id": "rx_volume",
                "source_families": ["public_source_context"],
                "source_family_gaps": ["public_source_context"],
                "evidence_routes": ["industry_snapshot"],
                "reason": "commercial tracker required for true prescription volume",
            }
        ],
        "second_pass_requests": [
            {
                "request_id": "rx_volume_req",
                "requirement_id": "rx_volume_req",
                "parent_requirement_id": "req_true_rx_volume",
                "source_families": ["public_source_context"],
                "source_family_gaps": ["public_source_context"],
                "evidence_routes": ["industry_snapshot"],
                "metric_families": ["prescription_volume"],
            }
        ],
    }

    result = graph.invoke(state, config={"configurable": {"thread_id": "unit-second-pass-commercial-hard-gate"}})

    assert result["second_pass_hard_gate"]["status"] == "blocked"
    assert result["second_pass_hard_gate"]["summary"]["executable_request_count"] == 0
    assert result["second_pass_retrieval_plan"] == {}
    assert result["bounded_gap_register"]["summary"]["commercial_tracker_gap_count"] == 1
    assert result["second_pass_result"]["status"] == "blocked_by_second_pass_hard_gate"
    assert result["second_pass_delta_audit"]["status"] == "no_authority_delta"
    assert result["tool_call_ledger"]["records"] == []


def test_market_snapshot_routes_coalesce_across_ticker_groups() -> None:
    plan = compile_multi_agent_retrieval_plan(
        {
            "requirements": [
                {
                    "requirement_id": "req_power_market",
                    "task_id": "req_power_market",
                    "tickers": ["NEE", "DUK", "SO"],
                    "years": [2026],
                    "source_tiers": ["market_snapshot"],
                    "evidence_routes": ["market_snapshot"],
                    "market_fields": ["price_return", "valuation_multiple"],
                },
                {
                    "requirement_id": "req_ai_market",
                    "task_id": "req_ai_market",
                    "tickers": ["NVDA", "MSFT", "AMZN"],
                    "years": [2026],
                    "source_tiers": ["market_snapshot"],
                    "evidence_routes": ["market_snapshot"],
                    "market_fields": ["price_return", "valuation_multiple"],
                },
            ]
        },
        query_contract={
            "focus_tickers": ["NEE", "DUK", "SO"],
            "search_scope_tickers": ["NEE", "DUK", "SO", "NVDA", "MSFT", "AMZN"],
            "years": [2026],
            "filing_types": ["10-Q"],
            "source_tiers": ["market_snapshot"],
        },
        case={"case_id": "unit_market_coalesce", "prompt": "compare market reaction"},
        activation_plan={"execution_mode": "deep_research", "max_tool_calls_total": 12},
    )

    market_routes = [route for route in plan["routes"] if route["retrieval_route"] == "market_snapshot"]

    assert len(market_routes) == 1
    assert set(market_routes[0]["tickers"]) == {"NEE", "DUK", "SO", "NVDA", "MSFT", "AMZN"}
    assert plan["route_coalescing"]["coalesced_group_count"] == 1


def test_deep_research_relationship_market_snapshot_uses_search_scope_tickers() -> None:
    args = tool_arguments_from_route(
        {
            "retrieval_route": "market_snapshot",
            "tickers": ["NEE", "DUK", "SO"],
            "coverage_requirements": {"market_fields": ["price_return"]},
        },
        user_query="utilities AI data center power readthrough",
        state_context={
            "execution_mode": "deep_research",
            "source_tiers": ["market_snapshot", "relationship_graph"],
            "search_scope_tickers": ["NEE", "DUK", "SO", "NVDA", "MSFT", "AMZN"],
        },
    )

    assert args["tickers"] == ["NEE", "DUK", "SO", "NVDA", "MSFT", "AMZN"]


def test_standard_memo_defers_coverage_second_pass_by_default(tmp_path: Path) -> None:
    def injected_coverage(state: dict) -> dict:
        return {
            "multi_agent_reflection_report": {
                "schema_version": "sec_agent_reflection_report_v0.1",
                "sufficiency_level": "partial",
                "bounded_answer_allowed": True,
                "source_available": True,
                "missing_requirements": [{"requirement_id": "req_amd_margin"}],
                "second_pass_requests": [
                    {
                        "request_id": "second_pass_1",
                        "tickers": ["AMD"],
                        "metric_families": ["operating_margin"],
                        "evidence_routes": ["ledger_first", "filing_text"],
                    }
                ],
            }
        }

    graph = build_multi_agent_orchestration_graph(
        coverage_reflection=injected_coverage,
        stop_after_node="coverage_reflection",
    )
    result = graph.invoke(
        make_multi_agent_smoke_state(
            user_query="写一段投研 memo，比较 NVDA 和 AMD 的基本面、管理层解释、市场反应和估值分歧。",
            output_dir=tmp_path,
            query_contract=_query_contract(["NVDA", "AMD"], source_tiers=["primary_sec_filing", "market_snapshot"]),
            focus_tickers=["NVDA", "AMD"],
            search_scope_tickers=["NVDA", "AMD"],
        ),
        config={"configurable": {"thread_id": "unit-standard-quality-second-pass-deferred"}},
    )
    nodes = [row["node"] for row in result["node_trace"]]

    assert "optional_second_pass" not in nodes
    assert nodes[-1] == "coverage_reflection"
    assert result["multi_agent_second_pass_decision"]["allowed"] is False
    assert result["multi_agent_second_pass_decision"]["blocked_by_execution_mode"] == "standard_memo"
    assert result["multi_agent_second_pass_decision"]["original_allowed"] is True


def test_universe_relationship_node_passes_expected_pack_ids_to_lookup(tmp_path: Path) -> None:
    sector_path = tmp_path / "sector_depth.yaml"
    sector_path.write_text(
        """
packs:
  - pack_id: "technology_ai_infrastructure_depth"
    industry_group: "information_technology"
    research_questions:
      - "AI infrastructure demand transmission."
    candidate_tickers:
      p0: ["DELL"]
      p1: ["ANET", "VRT"]
    primary_metric_families: ["revenue"]
    required_source_families: ["primary_sec_filing"]
  - pack_id: "energy_infrastructure_depth"
    industry_group: "energy"
    research_questions:
      - "Energy infrastructure production and capex."
    candidate_tickers:
      p0: ["HAL"]
      p1: ["OXY"]
    primary_metric_families: ["capex"]
    required_source_families: ["industry_snapshot"]
""",
        encoding="utf-8",
    )
    graph = build_multi_agent_orchestration_graph(stop_after_node="universe_relationship_expand")
    initial = make_multi_agent_smoke_state(
        user_query="从 AI infrastructure sector-depth pack 出发，分析 NVDA、DELL、ANET、VRT 的需求传导。",
        output_dir=tmp_path,
        query_contract=_query_contract(["NVDA", "DELL", "ANET", "VRT"], source_tiers=["relationship_graph", "industry_snapshot"]),
        focus_tickers=["NVDA", "DELL"],
        search_scope_tickers=["NVDA", "DELL", "ANET", "VRT"],
    )
    initial["multi_agent_context"] = {
        "sector_depth_pack_path": str(sector_path),
        "expected_relationship_pack_ids": ["technology_ai_infrastructure_depth"],
    }  # type: ignore[literal-required]

    result = graph.invoke(initial, config={"configurable": {"thread_id": "unit-relationship-expected-pack"}})
    refs = {
        ref
        for row in result["relationship_graph_observation"]["relationships"]
        for ref in row.get("evidence_refs", [])
    }

    assert refs
    assert all("sector_depth_pack:technology_ai_infrastructure_depth" in ref for ref in refs)
    assert not any("sector_depth_pack:energy_infrastructure_depth" in ref for ref in refs)


def test_multi_agent_graph_stop_after_node_keeps_new_state_summary(tmp_path: Path) -> None:
    graph = build_multi_agent_orchestration_graph(stop_after_node="validate_activation_plan")
    result = graph.invoke(
        make_multi_agent_smoke_state(
            user_query="MSFT 2026 capex是多少？只查这个单一指标。",
            output_dir=tmp_path,
            query_contract=_query_contract(["MSFT"]),
            focus_tickers=["MSFT"],
            search_scope_tickers=["MSFT"],
        ),
        config={"configurable": {"thread_id": "unit-multi-agent-stop"}},
    )
    checkpoint = result["node_checkpoints"][-1]

    assert multi_agent_node_order()[1] == "research_lead_plan"
    assert result["status"] == "stopped_after_node"
    assert checkpoint["state_summary"]["execution_mode"] == "deterministic_lookup"
    assert checkpoint["state_summary"]["activated_agent_count"] >= 1


def test_multi_agent_graph_stop_after_optional_second_pass_is_terminal(tmp_path: Path) -> None:
    graph = build_multi_agent_orchestration_graph(
        entry_node="optional_second_pass",
        stop_after_node="optional_second_pass",
    )
    state = make_multi_agent_smoke_state(
        user_query="second pass only",
        output_dir=tmp_path,
        query_contract=_query_contract(["AMD"]),
        focus_tickers=["AMD"],
        search_scope_tickers=["AMD"],
    )
    state["agent_activation_plan"] = {
        "execution_mode": "deep_research",
        "activate_agents": ["research_lead", "fundamental_analyst", "memo_writer"],
        "allowed_source_families": ["primary_sec_filing"],
    }
    state["multi_agent_reflection_report"] = {
        "sufficiency_level": "partial",
        "source_available": True,
        "second_pass_requests": [],
    }

    result = graph.invoke(state, config={"configurable": {"thread_id": "unit-stop-after-second-pass"}})
    nodes = [row["node"] for row in result["node_trace"]]

    assert nodes == ["optional_second_pass"]
    assert result["status"] == "stopped_after_node"
    assert result["native_stop_after_node"] == "optional_second_pass"


def test_multi_agent_graph_from_env_defaults_to_deterministic_router(tmp_path: Path) -> None:
    graph = build_multi_agent_orchestration_graph_from_env(
        env={"SEC_AGENT_MULTI_AGENT_LEAD_ROUTER": "deterministic"},
        stop_after_node="validate_activation_plan",
    )
    result = graph.invoke(
        make_multi_agent_smoke_state(
            user_query="MSFT 2026 capex是多少？只查这个单一指标。",
            output_dir=tmp_path,
            query_contract=_query_contract(["MSFT"]),
            focus_tickers=["MSFT"],
            search_scope_tickers=["MSFT"],
        ),
        config={"configurable": {"thread_id": "unit-multi-agent-env-deterministic"}},
    )

    assert result["agent_activation_plan"]["execution_mode"] == "deterministic_lookup"
    assert result["multi_agent_routing_trace"]["mode"] == "deterministic_lookup"


def test_deterministic_lookup_with_ledger_rows_skips_second_pass() -> None:
    route = _route_after_multi_agent_reflection(
        {
            "agent_activation_plan": {"execution_mode": "deterministic_lookup"},
            "runtime_ledger_rows": [{"ticker": "MSFT", "metric_family": "capex", "fiscal_year": 2026}],
            "multi_agent_second_pass_decision": {"allowed": True, "reason": "missing_supporting_context"},
        }
    )

    assert route == "renderer"


def test_deterministic_lookup_renderer_uses_generic_single_metric_boundary() -> None:
    rendered = _render_deterministic_lookup_answer(
        {
            "user_query": "JPM credit loss provision 是多少？",
            "query_contract": {"focus_tickers": ["JPM"], "metric_families": ["provision_for_credit_losses"]},
            "runtime_ledger_rows": [
                {
                    "ticker": "JPM",
                    "metric_name": "Provision for credit losses",
                    "raw_value_text": "2,507（百万美元）",
                    "fiscal_year": 2026,
                    "period_role": "QTD",
                    "source_evidence_id": "JPM_2026_10Q_ITEM1A_BLOCK_0001",
                }
            ],
        }
    )

    assert "Provision for credit losses" in rendered
    assert "全年 capex" not in rendered
    assert "单一全年口径" in rendered


def test_deterministic_lookup_renderer_prefers_amount_value_over_percentage_role() -> None:
    rendered = _render_deterministic_lookup_answer(
        {
            "user_query": "LLY 2026 revenue 是多少？",
            "query_contract": {"focus_tickers": ["LLY"], "metric_families": ["revenue"]},
            "runtime_ledger_rows": [
                {
                    "ticker": "LLY",
                    "metric_family": "revenue",
                    "metric_name": "revenue",
                    "metric_role": "percentage_rate",
                    "raw_value_text": "$ 19,799",
                    "display_value_zh": "19,799%（百分比率）",
                    "fiscal_year": 2026,
                    "period_role": "QTD",
                    "source_evidence_id": "__mcp__::LLY::2026::revenue::percentage_rate::qtd",
                },
                {
                    "ticker": "LLY",
                    "metric_family": "revenue",
                    "metric_name": "revenue",
                    "metric_role": "total_value",
                    "raw_value_text": "$ 19,799",
                    "display_value_zh": "19,799（百万美元）",
                    "fiscal_year": 2026,
                    "period_role": "QTD",
                    "source_evidence_id": "__mcp__::LLY::2026::revenue::total_value::qtd",
                },
            ],
        }
    )

    assert "19,799（百万美元）" in rendered
    assert "百分比率" not in rendered
    assert "percentage_rate" not in rendered


def test_deterministic_lookup_renderer_prefers_capex_answer_over_balance_sheet_assets() -> None:
    rendered = _render_deterministic_lookup_answer(
        {
            "user_query": "MSFT 2026 capex 是多少？",
            "query_contract": {"focus_tickers": ["MSFT"], "metric_families": ["capex"]},
            "runtime_ledger_rows": [
                {
                    "ticker": "MSFT",
                    "metric_family": "capital_expenditure_proxy",
                    "metric_name": "Property and equipment, net",
                    "metric_role": "total_value",
                    "raw_value_text": "$120,000",
                    "display_value_zh": "120,000（百万美元）",
                    "fiscal_year": 2026,
                    "period_role": "QTD",
                    "source_evidence_id": "MSFT_PPE_NET",
                },
                {
                    "ticker": "MSFT",
                    "metric_family": "capital_expenditure_proxy",
                    "metric_name": "Capital expenditures",
                    "metric_role": "total_value",
                    "raw_value_text": "$24,242",
                    "display_value_zh": "24,242（百万美元）",
                    "fiscal_year": 2026,
                    "period_role": "YTD",
                    "source_evidence_id": "MSFT_CAPEX",
                },
            ],
        }
    )

    first_metric_line = rendered.splitlines()[1]
    assert "Capital expenditures" in first_metric_line
    assert "24,242（百万美元）" in first_metric_line


def test_deterministic_lookup_renderer_prefers_credit_provision_amount_over_rate_rows() -> None:
    rendered = _render_deterministic_lookup_answer(
        {
            "user_query": "JPM 最近披露的 credit loss provision 是多少？",
            "query_contract": {
                "focus_tickers": ["JPM"],
                "metric_families": ["provision_for_credit_losses", "net_charge_offs"],
            },
            "runtime_ledger_rows": [
                {
                    "ticker": "JPM",
                    "metric_family": "provision_for_credit_losses",
                    "metric_name": "Provision for credit losses",
                    "metric_role": "percentage_rate",
                    "raw_value_text": "-24%",
                    "display_value_zh": "-24%（百分比率）",
                    "fiscal_year": 2026,
                    "period_role": "QTD",
                    "source_evidence_id": "JPM_PROVISION_RATE",
                },
                {
                    "ticker": "JPM",
                    "metric_family": "net_charge_offs",
                    "metric_name": "Net charge-offs",
                    "metric_role": "total_value",
                    "raw_value_text": "$2,100",
                    "display_value_zh": "2,100（百万美元）",
                    "fiscal_year": 2026,
                    "period_role": "QTD",
                    "source_evidence_id": "JPM_NCO",
                },
                {
                    "ticker": "JPM",
                    "metric_family": "provision_for_credit_losses",
                    "metric_name": "Provision for credit losses",
                    "metric_role": "total_value",
                    "raw_value_text": "$2,507",
                    "display_value_zh": "2,507（百万美元）",
                    "fiscal_year": 2026,
                    "period_role": "QTD",
                    "source_evidence_id": "JPM_PROVISION_AMOUNT",
                },
            ],
        }
    )

    first_metric_line = rendered.splitlines()[1]
    assert "Provision for credit losses" in first_metric_line
    assert "2,507（百万美元）" in first_metric_line
    assert "百分比率" not in first_metric_line


def test_multi_agent_graph_stops_on_invalid_activation_plan(tmp_path: Path) -> None:
    def invalid_route(_state: dict) -> dict:
        return {
            "activation_plan": {
                "execution_mode": "deep_research",
                "activate_agents": ["research_lead", "renderer"],
                "allowed_source_families": ["primary_sec_filing"],
                "max_tool_calls_total": 1,
                "max_second_pass_rounds": 0,
                "max_repair_rounds": 0,
            },
            "routing_trace": {"mode": "deep_research"},
        }

    graph = build_multi_agent_orchestration_graph(route_activation=invalid_route)
    result = graph.invoke(
        make_multi_agent_smoke_state(
            user_query="从 AI capex 产业链角度分析 NVDA。",
            output_dir=tmp_path,
            query_contract=_query_contract(["NVDA"]),
            focus_tickers=["NVDA"],
            search_scope_tickers=["NVDA"],
        ),
        config={"configurable": {"thread_id": "unit-multi-agent-invalid-stop"}},
    )

    nodes = [row["node"] for row in result["node_trace"]]

    assert result["status"] == "failed"
    assert result["loop_break_reason"] == "invalid_agent_activation_plan"
    assert "validate_activation_plan" in nodes
    assert "execute_evidence_operators" not in nodes
    assert "renderer" not in nodes


def test_multi_agent_graph_stops_on_plan_reflection_gate_failure(tmp_path: Path) -> None:
    def milvus_unavailable_route(_state: dict) -> dict:
        return {
            "activation_plan": {
                "execution_mode": "focused_answer",
                "activate_agents": ["research_lead", "sec_operator", "coverage_reflection", "memo_writer", "verifier", "renderer"],
                "allowed_source_families": ["primary_sec_filing", "milvus_semantic"],
                "model_policy_hint": {"research_lead": "balanced", "memo_writer": "strong", "verifier": "strong", "renderer": "none"},
                "max_tool_calls_total": 4,
                "max_second_pass_rounds": 1,
                "max_repair_rounds": 1,
                "metadata": {"required_source_families": ["milvus_semantic"]},
            },
            "routing_trace": {"mode": "focused_answer"},
        }

    graph = build_multi_agent_orchestration_graph(route_activation=milvus_unavailable_route)
    initial = make_multi_agent_smoke_state(
        user_query="用语义检索补充 NVDA 的供应链关系表述。",
        output_dir=tmp_path,
        query_contract=_query_contract(["NVDA"]),
        focus_tickers=["NVDA"],
        search_scope_tickers=["NVDA"],
    )
    initial["project_inventory"] = {
        "available_source_families": ["primary_sec_filing"],
        "source_family_availability": {
            "milvus_semantic": {"status": "unavailable", "available": False},
        },
        "milvus_runtime": {"status": "unavailable", "available": False, "location": "none"},
    }  # type: ignore[literal-required]

    result = graph.invoke(initial, config={"configurable": {"thread_id": "unit-plan-reflection-stop"}})
    nodes = [row["node"] for row in result["node_trace"]]

    assert result["status"] == "failed"
    assert result["loop_break_reason"] == "plan_reflection_gate_failed"
    assert result["plan_reflection_report"]["status"] == "fail"
    assert {error["type"] for error in result["plan_reflection_report"]["errors"]} == {
        "required_source_family_unavailable",
        "milvus_semantic_requested_but_unavailable",
    }
    assert "plan_reflection_gate" in nodes
    assert "execute_evidence_operators" not in nodes
    assert "renderer" not in nodes


def _query_contract(tickers: list[str], *, source_tiers: list[str] | None = None) -> dict:
    return {
        "task_type": "open_analysis",
        "search_scope_tickers": tickers,
        "focus_tickers": tickers,
        "years": [2026],
        "filing_types": ["10-Q", "8-K"],
        "source_tiers": source_tiers or ["primary_sec_filing"],
        "metric_families": ["capex"],
        "decomposed_tasks": [
            {
                "task_id": "unit_task",
                "question_zh": "unit task",
                "priority": "primary",
                "required_tickers": tickers,
                "required_metric_families": ["capex"],
            }
        ],
    }


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")
