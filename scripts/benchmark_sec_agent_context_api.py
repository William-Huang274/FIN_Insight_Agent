from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
SCRIPT_ROOT = REPO_ROOT / "scripts"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from evaluate_sec_agent_context_api_smoke import (  # noqa: E402
    TENANT_ID,
    USER_ID,
    _build_handler,
    _write_api_fixture_world,
)
from evaluate_sec_agent_context_managed_tool_controller import _safe_rmtree  # noqa: E402
from evaluate_sec_agent_context_state_replay import _prepare_fixture_root  # noqa: E402


DEFAULT_FIXTURE_ROOT = REPO_ROOT / "reports" / "quality" / "local_context_api_load_fixture_runtime"
DEFAULT_OUTPUT = REPO_ROOT / "reports" / "quality" / "local_context_api_load_heuristic_v1.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Small load test for request-level ContextManager API flow.")
    parser.add_argument("--fixture-root", default=str(DEFAULT_FIXTURE_ROOT))
    parser.add_argument("--output-path", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--requests", type=int, default=120)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--warmup-requests", type=int, default=10)
    parser.add_argument("--workload", choices=("read_mostly", "mixed"), default="mixed")
    parser.add_argument("--keep-fixtures", action="store_true", default=True)
    parser.add_argument("--clean-fixtures", dest="keep_fixtures", action="store_false")
    parser.add_argument(
        "--controller-backend",
        default=os.environ.get("TOOL_CONTROLLER_BACKEND", "heuristic"),
        choices=("deepseek", "openai_compatible", "qwen_vllm", "heuristic"),
    )
    parser.add_argument("--llm-backend", default=os.environ.get("LLM_BACKEND", "deepseek"))
    parser.add_argument("--base-url", default=os.environ.get("BASE_URL", "https://api.deepseek.com"))
    parser.add_argument("--chat-completions-path", default=os.environ.get("CHAT_COMPLETIONS_PATH", "/chat/completions"))
    parser.add_argument("--model", default=os.environ.get("MODEL_NAME", "deepseek-v4-pro"))
    parser.add_argument("--api-key-env", default=os.environ.get("API_KEY_ENV", "DEEPSEEK_API_KEY"))
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--timeout-s", type=int, default=180)
    parser.add_argument("--max-steps", type=int, default=1)
    parser.add_argument("--disable-handler-lock", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    fixture_root = Path(args.fixture_root).resolve()
    _prepare_fixture_root(fixture_root)
    _write_api_fixture_world(fixture_root)
    handler = _build_handler(args=args, fixture_root=fixture_root)
    handler.context_manager.ingest_sessions()
    handler.context_manager.set_active_session(tenant_id=TENANT_ID, user_id=USER_ID, session_id="s_api_multi_nvda")

    for index in range(max(args.warmup_requests, 0)):
        template = _workload(args.workload)[index % len(_workload(args.workload))]
        handler.handle_turn(**template["request"])

    requests = [dict(_workload(args.workload)[index % len(_workload(args.workload))]) for index in range(max(args.requests, 0))]
    started = time.perf_counter()
    rows = []
    with ThreadPoolExecutor(max_workers=max(args.concurrency, 1)) as executor:
        futures = [executor.submit(_run_one, handler, index, request) for index, request in enumerate(requests)]
        for future in as_completed(futures):
            rows.append(future.result())
    elapsed_sec = time.perf_counter() - started
    rows.sort(key=lambda item: item["request_index"])

    latencies = [float(row["latency_ms"]) for row in rows]
    status_counts = Counter(str(row["status"]) for row in rows)
    tool_counts = Counter(str(row["tool"]) for row in rows)
    failures = [row for row in rows if not row["all_pass"]]
    summary = {
        "schema_version": "sec_agent_context_api_load_result_v0.1",
        "run_id": f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_context_api_load_{args.controller_backend}_{args.workload}",
        "fixture_root": str(fixture_root),
        "controller_backend": args.controller_backend,
        "handler_lock_enabled": not args.disable_handler_lock,
        "workload": args.workload,
        "request_count": len(rows),
        "concurrency": max(args.concurrency, 1),
        "warmup_requests": max(args.warmup_requests, 0),
        "elapsed_sec": round(elapsed_sec, 6),
        "throughput_rps": round(len(rows) / elapsed_sec, 4) if elapsed_sec else 0.0,
        "latency_ms": _latency_summary(latencies),
        "status_counts": dict(status_counts),
        "tool_counts": dict(tool_counts),
        "pass_count": sum(1 for row in rows if row["all_pass"]),
        "all_pass": not failures,
        "failure_count": len(failures),
        "failures": failures[:20],
        "sample_results": rows[:20],
        "notes": [
            "This is a single-process JSON-store load smoke with a process-local request lock by default.",
            "It does not prove multi-process production concurrency; use DB/Redis transactions before serving claims.",
        ],
    }
    output_path = Path(args.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not args.keep_fixtures:
        _safe_rmtree(fixture_root)
    print(json.dumps({key: summary[key] for key in _SUMMARY_KEYS}, ensure_ascii=False, indent=2))
    return 0 if summary["all_pass"] else 1


_SUMMARY_KEYS = (
    "run_id",
    "fixture_root",
    "controller_backend",
    "handler_lock_enabled",
    "workload",
    "request_count",
    "concurrency",
    "elapsed_sec",
    "throughput_rps",
    "latency_ms",
    "status_counts",
    "tool_counts",
    "pass_count",
    "all_pass",
    "failure_count",
)


def _run_one(handler: Any, request_index: int, template: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    result = handler.handle_turn(**template["request"])
    latency_ms = int((time.perf_counter() - started) * 1000)
    expected_status = template.get("expected_status")
    expected_tool = template.get("expected_tool")
    checks = [
        {"name": "status", "passed": result.get("status") == expected_status, "expected": expected_status, "actual": result.get("status")},
    ]
    if expected_tool:
        checks.append(
            {
                "name": "tool",
                "passed": (result.get("tool_call") or {}).get("name") == expected_tool,
                "expected": expected_tool,
                "actual": (result.get("tool_call") or {}).get("name"),
            }
        )
    expected_post_session_id = template.get("expected_post_session_id")
    if expected_post_session_id:
        checks.append(
            {
                "name": "post_session",
                "passed": (result.get("post_context_snapshot") or {}).get("session_id") == expected_post_session_id,
                "expected": expected_post_session_id,
                "actual": (result.get("post_context_snapshot") or {}).get("session_id"),
            }
        )
    return {
        "request_index": request_index,
        "case_id": template.get("case_id"),
        "status": result.get("status"),
        "tool": (result.get("tool_call") or {}).get("name", ""),
        "latency_ms": latency_ms,
        "handler_reported_latency_ms": result.get("latency_ms"),
        "checks": checks,
        "all_pass": all(check["passed"] for check in checks),
    }


def _workload(name: str) -> list[dict[str, Any]]:
    read_mostly = [
        {
            "case_id": "coverage_nvda",
            "request": {
                "tenant_id": TENANT_ID,
                "user_id": USER_ID,
                "session_id": "s_api_multi_nvda",
                "user_message": "覆盖完整吗？",
            },
            "expected_status": "completed",
            "expected_tool": "inspect_coverage",
            "expected_post_session_id": "s_api_multi_nvda",
        },
        {
            "case_id": "evidence_nvda",
            "request": {
                "tenant_id": TENANT_ID,
                "user_id": USER_ID,
                "session_id": "s_api_multi_nvda",
                "user_message": "第二个 why_it_matters 的证据是什么？",
            },
            "expected_status": "completed",
            "expected_tool": "explain_evidence",
            "expected_post_session_id": "s_api_multi_nvda",
        },
        {
            "case_id": "state_amzn_meta",
            "request": {
                "tenant_id": TENANT_ID,
                "user_id": USER_ID,
                "session_id": "s_api_multi_amzn_meta",
                "user_message": "当前状态是什么？",
            },
            "expected_status": "completed",
            "expected_tool": "get_session_state",
            "expected_post_session_id": "s_api_multi_amzn_meta",
        },
    ]
    if name == "read_mostly":
        return read_mostly
    return [
        *read_mostly,
        {
            "case_id": "reformat_amzn_meta",
            "request": {
                "tenant_id": TENANT_ID,
                "user_id": USER_ID,
                "session_id": "s_api_multi_amzn_meta",
                "user_message": "改成 PM 5 bullets，保留引用。",
            },
            "expected_status": "completed",
            "expected_tool": "reformat_answer",
            "expected_post_session_id": "s_api_multi_amzn_meta",
        },
        {
            "case_id": "cross_user_denied",
            "request": {
                "tenant_id": TENANT_ID,
                "user_id": "u_load_other",
                "session_id": "s_api_multi_nvda",
                "user_message": "当前状态是什么？",
            },
            "expected_status": "access_denied",
            "expected_tool": "",
        },
    ]


def _latency_summary(values: list[float]) -> dict[str, float]:
    if not values:
        return {"min": 0, "p50": 0, "p90": 0, "p95": 0, "p99": 0, "max": 0, "mean": 0}
    sorted_values = sorted(values)
    return {
        "min": round(sorted_values[0], 3),
        "p50": round(_percentile(sorted_values, 50), 3),
        "p90": round(_percentile(sorted_values, 90), 3),
        "p95": round(_percentile(sorted_values, 95), 3),
        "p99": round(_percentile(sorted_values, 99), 3),
        "max": round(sorted_values[-1], 3),
        "mean": round(statistics.mean(sorted_values), 3),
    }


def _percentile(sorted_values: list[float], percentile: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = (len(sorted_values) - 1) * (percentile / 100.0)
    lower = int(rank)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = rank - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


if __name__ == "__main__":
    raise SystemExit(main())
