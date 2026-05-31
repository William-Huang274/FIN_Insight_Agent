from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "multi_agent_chain_performance_cases_v0_1.jsonl"
SCRIPT_PATH = REPO_ROOT / "scripts" / "eval_multi_agent_chain_performance.py"


def test_multi_agent_chain_performance_fixture_schema() -> None:
    rows = _read_jsonl(FIXTURE_PATH)

    assert len(rows) == 7
    assert {row["category"] for row in rows} == {
        "exact_lookup",
        "focused_answer",
        "standard_memo",
        "deep_relationship",
        "run_artifact",
        "safety_block",
        "repair_loop",
    }
    assert all(row["case_id"].startswith("ma_chain_") for row in rows)
    assert any(row["expected_execution_mode"] == "deep_research" for row in rows)


def test_multi_agent_chain_performance_eval_passes_deterministic_gate(tmp_path: Path) -> None:
    module = _load_script_module()

    aggregate = module.run_eval(cases_path=FIXTURE_PATH, output_dir=tmp_path, fail_on_gate=True)

    assert aggregate["gate_status"] == "pass"
    assert aggregate["case_count"] == 7
    assert aggregate["passed"] == 7
    assert (tmp_path / "chain_performance_summary.json").exists()
    assert (tmp_path / "chain_performance_scores.jsonl").exists()


def _read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _load_script_module():
    spec = importlib.util.spec_from_file_location("eval_multi_agent_chain_performance_under_test", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
