from __future__ import annotations

import importlib.util
from pathlib import Path

from sec_agent.memo_llm import (
    _compact_memo_logic_plan_for_writer_prompt,
    _memo_profile_spec_from_name,
    _memo_writer_budget_spec_from_profile,
)
from sec_agent.langgraph_orchestrator import _render_memo_answer
from sec_agent.p34_lane_quality_runtime import build_ai_semis_scoped_writer_payload


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "eval_multi_agent" / "run_p34_scoped_memo_writer_payload_preflight.py"
spec = importlib.util.spec_from_file_location("p34_scoped_memo_writer_payload_preflight", SCRIPT_PATH)
assert spec is not None and spec.loader is not None
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def test_p34_scoped_writer_payload_projects_live_rows_into_judgment_material() -> None:
    state = build_ai_semis_scoped_writer_payload()

    assert state["schema_version"] == "fin_insight_p34_ai_semis_scoped_writer_payload_v0_1"
    assert state["execution_mode"] == "deep_research"
    assert state["response_language"] == "zh-CN"
    assert "full_chain" in set(state["not_run"])

    judgment = state["verified_judgment_plan"]
    claims = judgment["supported_claims"]
    assert len(claims) == 7
    assert {claim["required_item_answered"] for claim in claims} >= {
        "cloud_capex_read_through",
        "req_accelerator_architecture",
        "req_customer_deployment",
        "req_dell_margin_quality",
        "req_supply_chain",
        "req_market_price_in",
        "req_counter_thesis",
    }
    assert all(claim["evidence_refs"] for claim in claims)
    assert all(claim.get("economic_role") for claim in claims)

    gap_ids = {gap["gap_id"] for gap in state["bounded_gap_register"]}
    assert "dell_ai_server_margin_bridge_quality_gap" in gap_ids
    assert "market_price_in_exact_positioning_gap" in gap_ids


def test_p34_scoped_writer_payload_has_writer_ready_answer_plan() -> None:
    state = build_ai_semis_scoped_writer_payload()
    plan = state["memo_logic_plan"]
    assert plan["validation"]["status"] == "pass"
    answer_plan = {
        row["question_item_id"]: row
        for row in plan["required_item_answer_plan"]
        if isinstance(row, dict)
    }
    assert answer_plan["req_dell_margin_quality"]["answer"]
    assert "GPU pass-through" in answer_plan["req_dell_margin_quality"]["answer"]
    assert answer_plan["req_market_price_in"]["cannot_infer"]

    profile = _memo_profile_spec_from_name("deep_research")
    compact = _compact_memo_logic_plan_for_writer_prompt(
        plan,
        budget=_memo_writer_budget_spec_from_profile(profile),
    )
    compact_answer_plan = {
        row["question_item_id"]: row
        for row in compact["required_item_answer_plan"]
        if isinstance(row, dict)
    }
    assert compact_answer_plan["req_dell_margin_quality"]["answer"]
    assert compact_answer_plan["req_market_price_in"]["cannot_infer"]


def test_p34_scoped_writer_payload_has_analyst_fact_tables() -> None:
    state = build_ai_semis_scoped_writer_payload()
    blocks = state["analyst_fact_table_blocks"]

    assert len(blocks) >= 6
    by_id = {block["block_id"]: block for block in blocks}
    assert {
        "financial_bridge_table",
        "product_spec_architecture_table",
        "customer_deployment_oem_table",
        "capex_demand_pool_table",
        "semicap_readthrough_table",
        "market_counter_boundary_table",
        "attempt_backed_gap_table",
    }.issubset(by_id)

    spec_rows = by_id["product_spec_architecture_table"]["rows"]
    spec_text = "\n".join(str(row.get("display_value") or "") for row in spec_rows)
    assert "36 Grace CPUs" in spec_text
    assert "72 Blackwell GPUs" in spec_text
    assert "192GB HBM3" in spec_text or "192 GB HBM3" in spec_text
    assert "5.3 TB/s" in spec_text
    assert any(row["value_quality"] == "specific_technical_or_deployment_fact" for row in spec_rows)

    financial_rows = by_id["financial_bridge_table"]["rows"]
    assert any(row["evidence_ref"] == "dell_isg_revenue_margin_baseline" for row in financial_rows)
    assert any(row["value_quality"] in {"context_summary", "structured_metric_context"} for row in financial_rows)

    gap_rows = by_id["attempt_backed_gap_table"]["rows"]
    assert gap_rows
    assert all(row["value_quality"] == "attempt_backed_gap" for row in gap_rows)

    plan_blocks = state["memo_logic_plan"]["analyst_fact_table_blocks"]
    assert plan_blocks == blocks
    assert state["supervising_analyst_pack"]["analyst_fact_table_blocks"] == blocks


def test_p34_renderer_projects_analyst_fact_tables() -> None:
    state = build_ai_semis_scoped_writer_payload()
    memo = {
        "response_language": {"language": "zh-CN"},
        "direct_answer": "当前判断应先区分需求池、产品能力、部署路径和利润质量，再说明哪些仍是数据边界。",
        "memo_logic_plan": state["memo_logic_plan"],
        "memo_claims": [],
    }

    rendered = _render_memo_answer(memo, bounded=False, state=state)

    assert "关键数据表" in rendered
    assert "| 公司 | 指标/属性 | 数值或事实 | 期间/版本 | 证据强度 | 边界 | 证据 |" in rendered
    assert "36 Grace CPUs / 72 Blackwell GPUs" in rendered
    assert "192GB HBM3" in rendered or "192 GB HBM3" in rendered
    assert "specific_technical_or_deployment_fact" in rendered
    assert "attempt_backed_gap" in rendered
    assert "不能外推：" not in rendered.split("关键问题回应:", 1)[0]


def test_p34_scoped_writer_payload_preflight_passes(tmp_path: Path) -> None:
    state = build_ai_semis_scoped_writer_payload()
    input_state = tmp_path / "p34_scoped_memo_writer_input_state.json"
    input_state.write_text("{}", encoding="utf-8")
    preflight = runner.build_preflight_summary(
        state,
        run_id="test_p34_scoped_payload",
        case_id=state["case_id"],
        aggregate_node_result=input_state,
        case_dir=tmp_path,
        elapsed_sec=0.0,
        max_prompt_chars=70000,
    )
    summary = runner._p34_summary(
        state=state,
        preflight=preflight,
        run_id="test_p34_scoped_payload",
        case_id=state["case_id"],
        case_dir=tmp_path,
        input_state_path=input_state,
        elapsed_sec=0.0,
    )

    assert preflight["gate_status"] == "pass"
    assert summary["gate_status"] == "pass"
    assert summary["checks"]["dell_margin_gap_preserved"]
    assert summary["checks"]["market_price_in_gap_preserved"]
    assert summary["checks"]["seven_judgment_claims_present"]
    assert summary["p34_payload"]["analyst_fact_table_block_count"] >= 6
    assert summary["p34_payload"]["analyst_fact_table_row_count"] >= 20
