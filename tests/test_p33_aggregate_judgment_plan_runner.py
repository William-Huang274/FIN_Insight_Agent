from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = REPO_ROOT / "scripts" / "eval_multi_agent" / "run_p33_aggregate_judgment_plan_from_specialist_checkpoint.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("p33_aggregate_runner", RUNNER_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _args(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(specialist_node_result=tmp_path / "specialist_node_result.json")


def _base_result() -> dict:
    return {
        "status": "stopped_after_node",
        "native_stop_after_node": "aggregate_judgment_plan",
        "node_trace": ["aggregate_judgment_plan"],
        "judgment_plan": {
            "supported_claims": [{"claim_id": "c1", "claim": "judgment"}],
            "unsupported_claims": [],
            "conflicts": [],
            "memo_outline": [{"memo_slot": "thesis", "status": "supported"}],
            "judgment_cards": [{"judgment_id": "j1"}],
            "judgment_state": {"judgment_cards": [{"judgment_id": "j1"}]},
            "thesis_path": {"status": "ready"},
            "thesis_driver_pack": {"status": "ready"},
        },
        "specialist_verification": {"status": "pass", "memo_writer_allowed": True},
    }


def test_aggregate_runner_gate_requires_memo_logic_plan(tmp_path: Path) -> None:
    runner = _load_runner()
    summary = runner._summary(
        state={},
        result=_base_result(),
        preflight={"status": "pass"},
        elapsed_sec=0.1,
        run_id="run",
        case_id="case",
        case_dir=tmp_path,
        args=_args(tmp_path),
    )

    assert summary["gate_status"] == "fail"
    assert summary["checks"]["memo_logic_plan_present"] is False
    assert summary["checks"]["memo_logic_plan_validation_pass"] is False


def test_aggregate_runner_persists_memo_logic_and_lead_checkpoint(tmp_path: Path) -> None:
    runner = _load_runner()
    result = {
        **_base_result(),
        "research_objective_contract": {"case_id": "case", "required_items": ["req1"]},
        "lead_review_checkpoint": {"status": "pass", "writer_order": ["thesis"]},
        "memo_logic_plan": {
            "validation": {"status": "pass"},
            "sections": [{"section_id": "thesis"}],
            "section_order": ["thesis"],
            "required_question_items": [{"item_id": "req1"}],
            "required_item_answer_plan": [{"item_id": "req1", "answer_status": "supported"}],
            "writer_thesis_skeleton": {"initial_view": "bounded thesis"},
            "product_reasoning_frame": {"status": "ready"},
        },
        "fundamental_statement_pack": {"status": "ready"},
    }
    summary = runner._summary(
        state={},
        result=result,
        preflight={"status": "pass"},
        elapsed_sec=0.1,
        run_id="run",
        case_id="case",
        case_dir=tmp_path,
        args=_args(tmp_path),
    )
    runner._write_summary(tmp_path, summary, result=result)

    node_result = json.loads((tmp_path / "aggregate_judgment_plan_node_result.json").read_text(encoding="utf-8"))
    assert summary["gate_status"] == "pass"
    assert summary["memo_logic_plan_stats"]["validation_status"] == "pass"
    assert node_result["memo_logic_plan"]["validation"]["status"] == "pass"
    assert node_result["lead_review_checkpoint"]["status"] == "pass"
    assert node_result["research_objective_contract"]["case_id"] == "case"
    assert node_result["fundamental_statement_pack"]["status"] == "ready"


def test_aggregate_runner_gate_requires_required_item_answer_plan(tmp_path: Path) -> None:
    runner = _load_runner()
    result = {
        **_base_result(),
        "memo_logic_plan": {
            "validation": {"status": "pass"},
            "sections": [{"section_id": "thesis"}],
            "section_order": ["thesis"],
            "required_question_items": [],
            "required_item_answer_plan": [],
            "writer_thesis_skeleton": {"initial_view": "bounded thesis"},
            "product_reasoning_frame": {"status": "ready"},
        },
    }
    summary = runner._summary(
        state={},
        result=result,
        preflight={"status": "pass"},
        elapsed_sec=0.1,
        run_id="run",
        case_id="case",
        case_dir=tmp_path,
        args=_args(tmp_path),
    )

    assert summary["gate_status"] == "fail"
    assert summary["checks"]["required_question_items_present"] is False
    assert summary["checks"]["required_item_answer_plan_present"] is False


def test_aggregate_runner_hydrates_missing_case_contract_fields(tmp_path: Path) -> None:
    runner = _load_runner()
    specialist_node = {
        "specialist_outputs": [],
        "specialist_route_results": [],
        "status": "stopped_after_node",
        "native_stop_after_node": "optional_specialist_subgraph",
    }
    state = runner._hydrate_state(
        {"case_id": "p33_3_ai_semis_accelerator_dell_gold_case_v0_1"},
        specialist_node,
        run_id="run",
        case_id="p33_3_ai_semis_accelerator_dell_gold_case_v0_1",
        case_dir=tmp_path,
    )

    assert state["user_query"].startswith("围绕 NVDA")
    assert state["focus_tickers"] == ["NVDA", "AMD", "GOOGL", "DELL"]
    assert "Assess DELL AI server revenue quality" in state["required_answer_moves"][3]
