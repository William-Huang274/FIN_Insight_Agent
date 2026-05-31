from __future__ import annotations

import json
from pathlib import Path

from sec_agent.langgraph_orchestrator import (
    build_multi_agent_orchestration_graph,
    build_multi_agent_orchestration_graph_from_env,
    make_multi_agent_smoke_state,
    multi_agent_node_order,
)


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
    assert "memo_writer" in nodes
    assert summary["execution_mode"] == "focused_answer"
    assert summary["evidence_rows"]["tool_observation_count"] >= 1
    assert summary["evidence_rows"]["retrieval_route_count"] >= 1
    assert summary["payload_policy"]["raw_evidence"] == "not_included"


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
    summary = json.loads((tmp_path / "multi_agent_summary.json").read_text(encoding="utf-8"))
    assert "claim_card_stats" in summary["judgment_plan"]
    assert "claim_card_stats" in summary["verified_judgment_plan"]


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
