from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "eval_multi_agent" / "run_p33_memo_writer_node_from_aggregate.py"
spec = importlib.util.spec_from_file_location("p33_memo_writer_node_runner", SCRIPT_PATH)
assert spec is not None and spec.loader is not None
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

from sec_agent.humanmade_gold_set_runtime import build_pre_writer_humanmade_gold_set_gate  # noqa: E402
from sec_agent.langgraph_orchestrator import build_multi_agent_orchestration_graph  # noqa: E402
from sec_agent.memo_llm import MemoLLMConfig, route_memo_writer_llm  # noqa: E402


ASSIMILATED_AGGREGATE = REPO_ROOT / "docs/project_os/ai_semis_gold_depth_assimilated_aggregate_v0_1.json"


def test_memo_writer_node_summary_fails_when_salvage_was_used(tmp_path: Path) -> None:
    judgment = {
        "supported_claims": [
            {"claim_id": "claim_1", "claim": "NVDA data center revenue is a supported demand context.", "evidence_refs": ["ref_1"]}
        ],
        "claim_card_stats": {"supported_claim_count": 1, "memo_ready_claim_count": 1},
    }
    result = {
        "status": "stopped_after_node",
        "native_stop_after_node": "memo_writer",
        "memo_route_result": {"status": "pass", "deterministic_salvage_used": True},
        "memo_answer": {
            "answer_status": "draft",
            "response_language": {"language": "zh-CN"},
            "memo_profile": {"profile": "deep_research"},
            "direct_answer": "这是一个足够长的中文判断。" * 12,
            "dimension_analyses": [{}, {}, {}],
            "memo_claims": [{"claim_id": "claim_1", "claim": "NVDA data center revenue is a supported demand context.", "evidence_refs": ["ref_1"]}] * 4,
            "raw_rows_consumed": False,
            "tool_calls_requested": [],
            "memo_generation_policy": "thesis_led_claim_cards_v0_1",
        },
    }
    summary = runner._summary(
        state={"verified_judgment_plan": judgment},
        result=result,
        preflight={"gate_status": "pass", "writer_payload": {}},
        humanmade_gold_set_gate={"status": "not_applicable"},
        run_id="test_run",
        case_id="case",
        case_dir=tmp_path,
        aggregate_node_result=tmp_path / "aggregate.json",
        elapsed_sec=0.0,
    )

    assert summary["checks"]["no_deterministic_salvage"] is False
    assert summary["gate_status"] == "fail"


def test_memo_writer_node_uses_case_contract_id_when_top_level_case_id_missing() -> None:
    state = {"case_contract": {"case_id": "p33_case_from_contract"}}

    assert runner._case_id_from_state(state, fallback="project_os") == "p33_case_from_contract"


def test_memo_writer_graph_state_preserves_gold_depth_runtime_fields(tmp_path: Path) -> None:
    state = json.loads(ASSIMILATED_AGGREGATE.read_text(encoding="utf-8"))
    state = {
        **state,
        "run_id": "test_gold_depth_state_preservation",
        "case_id": runner._case_id_from_state(state, fallback="case"),
        "output_dir": str(tmp_path),
        "status": "running",
    }
    assert build_pre_writer_humanmade_gold_set_gate(state)["status"] == "pass"

    captured: dict[str, object] = {}

    def _fake_memo_writer(node_state: dict) -> dict:
        gate = build_pre_writer_humanmade_gold_set_gate(node_state)
        captured["gate"] = gate
        captured["has_gold_materials"] = bool(node_state.get("gold_specialist_judgment_materials"))
        return {
            "memo_answer": {
                "answer_status": "draft",
                "response_language": {"language": "zh-CN"},
                "memo_profile": {"profile": "deep_research"},
                "direct_answer": "schema preservation smoke",
                "dimension_analyses": [],
                "memo_claims": [],
                "raw_rows_consumed": False,
            },
            "memo_route_result": {"status": "pass", "total_tokens": 0},
        }

    graph = build_multi_agent_orchestration_graph(
        use_checkpointer=False,
        entry_node="memo_writer",
        stop_after_node="memo_writer",
        memo_writer=_fake_memo_writer,
    )
    result = graph.invoke(state)

    assert result["status"] == "stopped_after_node"
    assert result["native_stop_after_node"] == "memo_writer"
    assert captured["has_gold_materials"] is True
    assert captured["gate"]["status"] == "pass"
    assert captured["gate"]["pre_writer_decision"]["allow_paid_memo_writer"] is True


def test_memo_writer_completes_thin_direct_answer_from_gold_answer_plan_without_paid_repair() -> None:
    state = json.loads(ASSIMILATED_AGGREGATE.read_text(encoding="utf-8"))
    calls = 0

    def _thin_writer(**_: object) -> dict:
        nonlocal calls
        calls += 1
        return {
            "status": "ok",
            "content": json.dumps(
                {
                    "schema_version": "sec_agent_multi_agent_memo_draft_v0.1",
                    "answer_status": "draft",
                    "direct_answer": "当前判断偏正面，但仍需跟踪更多证据。",
                    "response_language": {"language": "zh-CN"},
                    "memo_profile": {"profile": "deep_research"},
                    "memo_generation_policy": "thesis_led_claim_cards_v0_1",
                    "raw_rows_consumed": False,
                    "tool_calls_requested": [],
                    "dimension_analyses": [],
                    "memo_claims": [],
                },
                ensure_ascii=False,
            ),
            "finish_reason": "stop",
            "input_tokens": 100,
            "output_tokens": 100,
            "total_tokens": 200,
        }

    result = route_memo_writer_llm(
        state,
        config=MemoLLMConfig(max_repair_attempts=2),
        call_chat_completion=_thin_writer,
    )

    memo = result["memo_answer"]
    route = result["memo_route_result"]
    assert calls == 1
    assert route["status"] == "pass"
    assert route["attempt_count"] == 1
    assert len(memo["direct_answer"]) >= 620
    assert memo["memo_writer_diagnostics"]["direct_answer_completed_from_memo_logic_plan"] is True
    assert memo["memo_writer_diagnostics"]["dimension_analyses_completed_from_memo_logic_plan"] >= 5
    assert memo["memo_writer_diagnostics"]["action_items_completed_from_memo_logic_plan"]
    assert "AI server" in memo["direct_answer"]
    assert "不能直接说利润质量已经改善" in memo["direct_answer"]
    assert all("尚未完成中文综合" not in (row.get("summary") or "") for row in memo["dimension_analyses"])
    assert any(
        row.get("dimension_id") == "product_and_production" and row.get("evidence_refs")
        for row in memo["dimension_analyses"]
    )
    assert all(item.get("evidence_refs") for item in memo["investment_implications"])
