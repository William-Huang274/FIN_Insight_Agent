import importlib.util
import json
from pathlib import Path


def _load_post_gates_module():
    script = Path(__file__).resolve().parents[1] / "scripts" / "run_sec_benchmark_post_gates.py"
    spec = importlib.util.spec_from_file_location("run_sec_benchmark_post_gates", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_api_model_clean_answers_count_for_model_usage_gate(tmp_path):
    module = _load_post_gates_module()
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_jsonl(
        run_dir / "agent_outputs.jsonl",
        [
            {"case_id": "api_clean", "status": "answered", "answer_status": "answered_api_model"},
            {
                "case_id": "api_repaired",
                "status": "answered",
                "answer_status": "answered_api_model_truncation_repair",
            },
        ],
    )

    usage = module._qwen_usage(run_dir, {})

    assert usage["qwen_ratio"] == 0.0
    assert usage["api_model_answered"] == 1
    assert usage["api_model_repaired"] == 1
    assert usage["model_answered"] == 1
    assert usage["model_repaired"] == 1
    assert usage["model_ratio"] == 0.5


def test_api_model_usage_excludes_trap_rows(tmp_path):
    module = _load_post_gates_module()
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_jsonl(
        run_dir / "agent_outputs.jsonl",
        [
            {"case_id": "normal", "status": "answered", "answer_status": "answered_api_model"},
            {"case_id": "trap", "status": "answered", "answer_status": "answered_api_model"},
        ],
    )

    usage = module._qwen_usage(run_dir, {"trap": "anti_hallucination_source_gap"})

    assert usage["eligible_outputs"] == 1
    assert usage["trap_outputs_excluded"] == 1
    assert usage["api_model_answered"] == 1
    assert usage["model_ratio"] == 1.0
