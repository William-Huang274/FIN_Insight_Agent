from __future__ import annotations

from pathlib import Path
from typing import Any

from sec_agent.context_api import SecAgentContextRequestHandler
from sec_agent.context_manager import SecAgentContextManager
from sec_agent.tool_controller import ControllerConfig, DeepSeekToolController
from sec_agent.tool_harness import SecAgentToolHarness, _scope_revision_query


class _StalePolicyController:
    def run_turn(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "schema_version": "test_controller_result_v0",
            "status": "routed",
            "controller_backend": "fixture",
            "route_only": True,
            "tool_calls": [
                {
                    "id": "call_fixture_stale_policy",
                    "type": "function",
                    "name": "start_memo_analysis",
                    "arguments": {
                        "query": "stale",
                        "years": [2023, 2024, 2025],
                        "source_policy": "SEC_ONLY_10K",
                        "preferred_output": "investment_memo",
                        "execute": True,
                    },
                }
            ],
            "trace": [],
            "latency_ms": 0,
        }


def test_context_bootstrap_runtime_source_policy_overrides_controller_argument(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SEC_AGENT_SOURCE_POLICY", "SEC_PRIMARY_MIXED_RECENT")
    session_root = tmp_path / "session_harness"
    context_root = tmp_path / "context_store"
    handler = SecAgentContextRequestHandler(
        context_manager=SecAgentContextManager(session_root=session_root, context_root=context_root),
        controller=_StalePolicyController(),  # type: ignore[arg-type]
        harness=SecAgentToolHarness(session_root=session_root, python="__no_execute__"),
    )

    result = handler.handle_turn(
        tenant_id="tenant",
        user_id="user",
        user_message="比较MSFT 2025年10-K和2026年10-Q的云业务表现",
        session_id="mixed_session",
        allow_new_session=True,
        execute_tools=False,
    )

    tool_args = result["tool_call"]["arguments"]
    active_scope = result["post_context_snapshot"]["active_scope"]
    assert result["status"] == "completed"
    assert tool_args["query"] == "比较MSFT 2025年10-K和2026年10-Q的云业务表现"
    assert tool_args["execute"] is False
    assert tool_args["source_policy"] == "SEC_PRIMARY_MIXED_RECENT"
    assert active_scope["source_policy"] == "SEC_PRIMARY_MIXED_RECENT"


def test_heuristic_controller_keeps_bootstrap_source_policy_and_chinese_years(tmp_path: Path) -> None:
    harness = SecAgentToolHarness(session_root=tmp_path / "session_harness", python="__no_execute__")
    controller = DeepSeekToolController(
        harness=harness,
        config=ControllerConfig(controller_backend="heuristic", max_steps=1, execute_tools=False),
    )

    result = controller.run_turn(
        user_message="比较MSFT 2025年10-K和2026年10-Q的云业务表现",
        session_id="mixed_session",
        user_id="user",
        tenant_id="tenant",
        runtime_context={
            "initial_state": {"precondition": "new_context_session_bootstrap"},
            "bootstrap": {"source_policy": "SEC_PRIMARY_MIXED_RECENT"},
        },
        route_only=True,
    )

    args = result["tool_calls"][0]["arguments"]
    assert result["tool_calls"][0]["name"] == "start_memo_analysis"
    assert args["years"] == [2025, 2026]
    assert args["source_policy"] == "SEC_PRIMARY_MIXED_RECENT"


def test_controller_fills_missing_start_years_from_chinese_prompt(tmp_path: Path) -> None:
    harness = SecAgentToolHarness(session_root=tmp_path / "session_harness", python="__no_execute__")
    controller = DeepSeekToolController(
        harness=harness,
        config=ControllerConfig(controller_backend="heuristic", max_steps=1, execute_tools=False),
    )

    call = controller._prepare_tool_call(
        {
            "id": "call_without_years",
            "name": "start_memo_analysis",
            "arguments": {"source_policy": "SEC_ONLY_10K"},
        },
        user_message="比较MSFT 2025年10-K和2026年10-Q的云业务表现",
        runtime_context={
            "session_id": "mixed_session",
            "user_id": "user",
            "tenant_id": "tenant",
            "bootstrap": {"source_policy": "SEC_PRIMARY_MIXED_RECENT"},
        },
        route_only=True,
    )

    assert call["arguments"]["years"] == [2025, 2026]
    assert call["arguments"]["source_policy"] == "SEC_PRIMARY_MIXED_RECENT"


def test_scope_revision_query_preserves_mixed_8k_source_boundary() -> None:
    query = _scope_revision_query(
        "结合MSFT和AMZN 2026 10-Q与8-K业绩新闻稿解释云业务表现",
        ["AMZN", "MSFT"],
        [2026],
        source_policy="SEC_PRIMARY_MIXED_WITH_8K_EARNINGS",
    )

    assert "SEC 10-K/10-Q/8-K 混合投资备忘录" in query
    assert "公司 8-K 业绩新闻稿" in query
    assert "不能替代 10-K/10-Q 财务报表数值" in query
    assert "只使用 SEC 10-K；" not in query


def test_controller_reroutes_non_scope_followup_to_scoped_analysis(tmp_path: Path) -> None:
    harness = SecAgentToolHarness(session_root=tmp_path / "session_harness", python="__no_execute__")
    controller = DeepSeekToolController(
        harness=harness,
        config=ControllerConfig(controller_backend="heuristic", max_steps=1, execute_tools=False),
    )

    call = controller._prepare_tool_call(
        {
            "id": "call_bad_revise",
            "name": "revise_memo_scope",
            "arguments": {"execute": True},
        },
        user_message="继续比较两家公司AI资本开支或云需求表述的差异，只基于同一session的上下文。",
        runtime_context={
            "session_id": "mixed_8k_session",
            "user_id": "user",
            "tenant_id": "tenant",
            "active_answer_id": "answer_1",
            "active_scope": {
                "selected_tickers": ["MSFT", "AMZN"],
                "selected_years": [2026],
                "source_policy": "SEC_PRIMARY_MIXED_WITH_8K_EARNINGS",
            },
        },
        route_only=True,
    )

    args = call["arguments"]
    assert call["name"] == "start_memo_analysis"
    assert args["source_policy"] == "SEC_PRIMARY_MIXED_WITH_8K_EARNINGS"
    assert args["years"] == [2026]
    assert "目标公司: MSFT, AMZN" in args["query"]
    assert "用户追问: 继续比较两家公司AI资本开支" in args["query"]


def test_controller_reroutes_substantive_continue_away_from_resume(tmp_path: Path) -> None:
    harness = SecAgentToolHarness(session_root=tmp_path / "session_harness", python="__no_execute__")
    controller = DeepSeekToolController(
        harness=harness,
        config=ControllerConfig(controller_backend="heuristic", max_steps=1, execute_tools=False),
    )

    call = controller._prepare_tool_call(
        {
            "id": "call_bad_resume",
            "name": "resume_analysis",
            "arguments": {"execute": True},
        },
        user_message="继续比较两家公司AI资本开支或云需求表述的差异，只基于同一session的上下文。",
        runtime_context={
            "session_id": "mixed_8k_session",
            "user_id": "user",
            "tenant_id": "tenant",
            "active_answer_id": "answer_1",
            "active_scope": {
                "selected_tickers": ["MSFT", "AMZN"],
                "selected_years": [2026],
                "source_policy": "SEC_PRIMARY_MIXED_WITH_8K_EARNINGS",
            },
        },
        route_only=True,
    )

    assert call["name"] == "start_memo_analysis"
    assert call["arguments"]["years"] == [2026]
    assert "用户追问: 继续比较两家公司AI资本开支" in call["arguments"]["query"]


def test_controller_keeps_explicit_interrupted_run_resume(tmp_path: Path) -> None:
    harness = SecAgentToolHarness(session_root=tmp_path / "session_harness", python="__no_execute__")
    controller = DeepSeekToolController(
        harness=harness,
        config=ControllerConfig(controller_backend="heuristic", max_steps=1, execute_tools=False),
    )

    call = controller._prepare_tool_call(
        {
            "id": "call_resume",
            "name": "resume_analysis",
            "arguments": {"execute": True},
        },
        user_message="刚才中断了，继续执行这个 state path 的缺失 artifacts。",
        runtime_context={
            "session_id": "mixed_8k_session",
            "user_id": "user",
            "tenant_id": "tenant",
            "active_answer_id": "answer_1",
        },
        route_only=True,
    )

    assert call["name"] == "resume_analysis"
