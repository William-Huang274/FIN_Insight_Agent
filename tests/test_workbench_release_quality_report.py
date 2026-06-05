import json
import importlib.util
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "workbench" / "generate_backend_release_quality_report.py"
SPEC = importlib.util.spec_from_file_location("generate_backend_release_quality_report", SCRIPT_PATH)
assert SPEC and SPEC.loader
report_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(report_module)

build_release_quality_report = report_module.build_release_quality_report
parse_validation = report_module.parse_validation
render_markdown = report_module.render_markdown


def test_release_quality_report_summarizes_pressure_tokens_and_latency(tmp_path: Path) -> None:
    child_a = _write_child_summary(
        tmp_path / "run_a" / "real_chain_eval_summary.json",
        elapsed_ms=90_000,
        research_tokens=1_000,
        memo_tokens=2_000,
        verifier_tokens=300,
        specialist_tokens=[],
        evidence_elapsed_ms=12_000,
    )
    child_b = _write_child_summary(
        tmp_path / "run_b" / "real_chain_eval_summary.json",
        elapsed_ms=110_000,
        research_tokens=1_500,
        memo_tokens=2_500,
        verifier_tokens=400,
        specialist_tokens=[(600, 450, 150), (700, 500, 200)],
        evidence_elapsed_ms=15_000,
    )
    pressure_summary = {
        "benchmark_id": "pressure_test",
        "benchmark_dir": str(tmp_path),
        "gate_status": "pass",
        "users": 2,
        "iterations": 1,
        "case_ids": ["focused", "standard"],
        "case_run_count": 2,
        "pass_count": 2,
        "fail_count": 0,
        "timeout_count": 0,
        "exit_fail_count": 0,
        "elapsed_ms": 130_000,
        "api_key_env": "DEEPSEEK_API_KEY",
        "api_key_saved": False,
        "raw_llm_response_saved": False,
        "results": [
            _pressure_row("focused", 1, 100_000, child_a),
            _pressure_row("standard", 2, 120_000, child_b),
        ],
    }
    summary_path = tmp_path / "pressure_summary.json"
    summary_path.write_text(json.dumps(pressure_summary), encoding="utf-8")

    report = build_release_quality_report(
        pressure_summary_path=summary_path,
        report_id="unit_report",
        validations=[parse_validation("pytest|pass|2 passed")],
        ci_checks=[{"name": "docker-smoke", "state": "SUCCESS", "link": "https://example.test"}],
    )

    assert report["overall_status"] == "pass"
    pressure = report["pressure"]
    assert pressure["pass_rate"] == 1.0
    assert pressure["duration_ms"]["p50"] == 100_000
    assert pressure["duration_ms"]["p95"] == 120_000
    assert pressure["token_usage"]["total"] == 9_000
    assert pressure["token_usage"]["avg"] == 4_500
    assert pressure["token_usage"]["known_input_total"] == 950
    assert pressure["token_usage"]["known_output_total"] == 350
    assert pressure["latency_breakdown_ms"]["evidence_context_max_avg"] == 13_500
    assert pressure["throughput"]["concurrency_gain"] == pytest.approx(1.692, abs=0.001)
    assert pressure["case_groups"][0]["case_id"] == "focused"
    assert pressure["case_groups"][1]["avg_estimated_total_tokens"] == 5_700

    markdown = render_markdown(report)
    assert "Workbench Backend Release Quality Report" in markdown
    assert "Tokens/run p50 / p95 / max" in markdown
    assert "`docker-smoke`" in markdown


def test_parse_validation_rejects_malformed_values() -> None:
    assert parse_validation("frontend_smoke|passed|no console errors") == {
        "name": "frontend_smoke",
        "status": "pass",
        "detail": "no console errors",
    }
    with pytest.raises(ValueError):
        parse_validation("missing_status")


def _write_child_summary(
    path: Path,
    *,
    elapsed_ms: int,
    research_tokens: int,
    memo_tokens: int,
    verifier_tokens: int,
    specialist_tokens: list[tuple[int, int, int]],
    evidence_elapsed_ms: int,
) -> Path:
    path.parent.mkdir(parents=True)
    payload = {
        "gate_status": "pass",
        "elapsed_ms": elapsed_ms,
        "metrics": {"case_count": 1, "passed": 1, "failed": 0, "total_tool_calls": 3},
        "cases": [
            {
                "elapsed_ms": elapsed_ms - 1_000,
                "agent_audit": {
                    "research_lead": {
                        "diagnostics": {
                            "latency_ms": 10_000,
                            "total_tokens": research_tokens,
                        }
                    },
                    "specialists": {
                        "route_results": [
                            {
                                "latency_ms": 5_000,
                                "total_tokens": total,
                                "input_tokens": input_tokens,
                                "output_tokens": output_tokens,
                            }
                            for total, input_tokens, output_tokens in specialist_tokens
                        ]
                    },
                    "memo_writer": {
                        "diagnostics": {
                            "latency_ms": 11_000,
                            "total_tokens": memo_tokens,
                        }
                    },
                    "verifier": {
                        "diagnostics": {
                            "latency_ms": 1_000,
                            "total_tokens": verifier_tokens,
                        }
                    },
                    "evidence_operators": {
                        "tool_calls": [
                            {
                                "runtime_summary": {
                                    "context_runtime": {"elapsed_ms": evidence_elapsed_ms}
                                }
                            },
                            {
                                "runtime_summary": {
                                    "context_runtime": {"elapsed_ms": evidence_elapsed_ms - 1_000}
                                }
                            },
                        ]
                    },
                },
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _pressure_row(case_id: str, user_id: int, elapsed_ms: int, child_path: Path) -> dict[str, object]:
    return {
        "user_id": user_id,
        "iteration": 1,
        "ordinal": user_id,
        "case_id": case_id,
        "run_id": f"run_{user_id}",
        "elapsed_ms": elapsed_ms,
        "exit_code": 0,
        "timed_out": False,
        "child_gate_status": "pass",
        "child_total_tool_calls": 3,
        "summary_path": str(child_path),
    }
