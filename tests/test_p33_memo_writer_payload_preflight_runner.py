from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "eval_multi_agent" / "run_p33_memo_writer_payload_preflight_from_aggregate.py"
spec = importlib.util.spec_from_file_location("p33_memo_writer_payload_preflight_runner", SCRIPT_PATH)
assert spec is not None and spec.loader is not None
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def _claim(index: int) -> dict:
    return {
        "claim_id": f"claim_{index}",
        "claim": f"Supported judgment {index}.",
        "claim_type": "business_observation",
        "memo_slot": [
            "thesis",
            "fundamentals",
            "product_and_production",
            "industry_supply_chain",
            "market_valuation",
            "risk_and_counterevidence",
        ][index % 6],
        "evidence_refs": [f"ref_{index}"],
        "source_families": [["primary_sec_filing"], ["market_snapshot"], ["industry_snapshot"], ["relationship_graph"]][index % 4],
        "claim_rank_bucket": "memo_ready",
    }


def test_p33_memo_writer_payload_preflight_accepts_complete_deep_contract(tmp_path: Path) -> None:
    state = {
        "case_contract": {
            "case_id": "p33_3_ai_semis_accelerator_dell_gold_case_v0_1",
            "prompt": "围绕 NVDA、DELL 和 AI server 判断产品、客户部署、供应链和财务传导。",
            "required_answer_moves": [f"Required answer move {index}" for index in range(1, 8)],
            "required_dimensions": [
                "opening_thesis",
                "fundamentals",
                "product_architecture",
                "customer_deployment",
                "industry_supply_chain",
                "capital_market_feedback",
                "counter_thesis_and_what_would_change",
            ],
            "eval_focus": ["p33_gold_workpaper_quality"],
        },
        "memo_logic_plan": {
            "schema_version": "finsight_memo_logic_plan_v0_1",
            "plan_id": "test_plan",
            "memo_intent": "answer_first_deep_research",
            "section_order": [
                "fundamentals",
                "product_and_production",
                "capital_and_financing",
                "competition_and_market_position",
                "industry_supply_chain",
                "risk_and_counterevidence",
                "evidence_gap",
            ],
            "sections": [
                {"section_id": section_id, "title": section_id, "required_item_ids": [f"required_item_{index}"]}
                for index, section_id in enumerate(
                    [
                        "fundamentals",
                        "product_and_production",
                        "capital_and_financing",
                        "competition_and_market_position",
                        "industry_supply_chain",
                        "risk_and_counterevidence",
                        "evidence_gap",
                    ],
                    start=1,
                )
            ],
            "required_item_answer_plan": [
                {
                    "question_item_id": f"required_item_{index}",
                    "dimension": "fundamentals",
                    "answer_role": "bounded_judgment",
                    "answer_first_judgment_prompt": f"Answer item {index}",
                    "evidence_bridge_prompt": f"Bridge item {index}",
                    "counter_read_prompt": f"Counter item {index}",
                    "what_would_change_prompt": f"Change item {index}",
                }
                for index in range(1, 11)
            ],
            "validation": {"status": "pass"},
        },
        "verified_judgment_plan": {
            "supported_claims": [_claim(index) for index in range(1, 9)],
            "unsupported_claims": [],
            "conflicts": [],
            "claim_card_stats": {"supported_claim_count": 8, "memo_ready_claim_count": 8, "memo_slot_supported_count": 5},
            "memo_thesis_plan": {"status": "ready"},
            "memo_thesis_pack": {"status": "ready"},
            "memo_writer_allowed": True,
        },
        "specialist_verification": {"status": "pass", "memo_writer_allowed": True},
    }

    summary = runner.build_preflight_summary(
        state,
        run_id="test_run",
        case_id="p33_3_ai_semis_accelerator_dell_gold_case_v0_1",
        aggregate_node_result=tmp_path / "aggregate.json",
        case_dir=tmp_path,
        elapsed_sec=0.0,
        max_prompt_chars=70000,
    )

    assert summary["gate_status"] == "pass"
    assert summary["writer_payload"]["memo_profile"] == "deep_research"
    assert summary["writer_payload"]["response_language"]["language"] == "zh-CN"
    assert summary["writer_payload"]["compact_required_item_count"] == 10
    assert summary["writer_payload"]["compact_section_count"] == 7


def test_deep_contract_preserves_gold_depth_required_items(tmp_path: Path) -> None:
    state = {
        "case_contract": {
            "case_id": "p33_gold_case_from_contract",
            "prompt": "围绕 NVDA、DELL 和 AI server 判断产品、客户部署、供应链和财务传导。",
            "expected_execution_mode": "deep_research",
            "required_answer_moves": [f"Required answer move {index}" for index in range(1, 8)],
            "required_dimensions": [
                "opening_thesis",
                "fundamentals",
                "product_architecture",
                "customer_deployment",
                "industry_supply_chain",
                "capital_market_feedback",
                "counter_thesis_and_what_would_change",
            ],
            "eval_focus": ["p33_gold_workpaper_quality"],
        },
        "memo_logic_plan": {
            "schema_version": "finsight_memo_logic_plan_v0_1",
            "plan_id": "gold_depth_plan",
            "memo_intent": "answer_first_deep_research",
            "section_order": [
                "fundamentals",
                "product_and_production",
                "capital_and_financing",
                "competition_and_market_position",
                "industry_supply_chain",
                "risk_and_counterevidence",
                "evidence_gap",
            ],
            "sections": [
                {"section_id": section_id, "title": section_id}
                for section_id in [
                    "fundamentals",
                    "product_and_production",
                    "capital_and_financing",
                    "competition_and_market_position",
                    "industry_supply_chain",
                    "risk_and_counterevidence",
                    "evidence_gap",
                ]
            ],
            "required_item_answer_plan": [
                {
                    "question_item_id": f"gold_required_item_{index}",
                    "dimension": "product_and_production",
                    "answer_role": "required_question_answer",
                    "answer_first_judgment_prompt": f"Answer gold-depth item {index}",
                    "evidence_bridge_prompt": f"Bridge gold-depth item {index}",
                    "counter_read_prompt": f"Counter gold-depth item {index}",
                    "what_would_change_prompt": f"Change gold-depth item {index}",
                }
                for index in range(1, 17)
            ],
            "validation": {"status": "pass"},
        },
        "verified_judgment_plan": {
            "supported_claims": [_claim(index) for index in range(1, 9)],
            "claim_card_stats": {"supported_claim_count": 8, "memo_ready_claim_count": 8, "memo_slot_supported_count": 5},
            "memo_thesis_plan": {"status": "ready"},
        },
        "specialist_verification": {"status": "pass", "memo_writer_allowed": True},
    }

    summary = runner.build_preflight_summary(
        state,
        run_id="test_run",
        case_id=runner._case_id_from_state(state, fallback="fallback_case"),
        aggregate_node_result=tmp_path / "aggregate.json",
        case_dir=tmp_path,
        elapsed_sec=0.0,
        max_prompt_chars=70000,
    )

    assert runner._case_id_from_state(state, fallback="fallback_case") == "p33_gold_case_from_contract"
    assert summary["gate_status"] == "pass"
    assert summary["writer_payload"]["original_required_item_count"] == 16
    assert summary["writer_payload"]["compact_required_item_count"] == 16
    assert summary["writer_payload"]["dropped_required_item_ids"] == []
