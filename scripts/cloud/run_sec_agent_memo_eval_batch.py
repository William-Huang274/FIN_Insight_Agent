from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run SEC agent memo eval cases through the graph runner.")
    parser.add_argument("--eval-set", required=True, help="Memo eval JSONL path.")
    parser.add_argument("--output-dir", default="", help="Batch report directory. Defaults under reports/quality.")
    parser.add_argument("--run-id", default="", help="Stable run id for output naming.")
    parser.add_argument("--case-id", action="append", default=[], help="Run only selected eval case_id values.")
    parser.add_argument("--limit", type=int, default=0, help="Optional max number of cases to run.")
    parser.add_argument("--resume-completed", action="store_true", help="Skip cases already recorded with returncode 0.")
    parser.add_argument("--llm-backend", default=os.environ.get("LLM_BACKEND", "deepseek"))
    parser.add_argument("--base-url", default=os.environ.get("BASE_URL", "https://api.deepseek.com"))
    parser.add_argument("--chat-completions-path", default=os.environ.get("CHAT_COMPLETIONS_PATH", "/chat/completions"))
    parser.add_argument("--model", default=os.environ.get("MODEL_NAME", "deepseek-v4-pro"))
    parser.add_argument("--api-key-env", default=os.environ.get("API_KEY_ENV", "DEEPSEEK_API_KEY"))
    parser.add_argument("--query-planner", default=os.environ.get("QUERY_PLANNER", "llm"), choices=("heuristic", "llm"))
    parser.add_argument("--bge-device", default=os.environ.get("BGE_DEVICE", "cuda"))
    parser.add_argument("--pass-threshold", type=float, default=0.78)
    parser.add_argument("--python", default=sys.executable)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    eval_path = _resolve(args.eval_set)
    rows = _read_jsonl(eval_path)
    selected_ids = set(args.case_id or [])
    if selected_ids:
        rows = [row for row in rows if str(row.get("case_id") or "") in selected_ids]
    if args.limit > 0:
        rows = rows[: args.limit]
    if not rows:
        raise SystemExit("No eval cases selected.")

    run_id = args.run_id or datetime.now().strftime("%Y%m%d_api_memo_full30_%H%M%S")
    output_dir = _resolve(args.output_dir) if args.output_dir else REPO_ROOT / "reports" / "quality" / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = output_dir / "logs"
    logs_dir.mkdir(exist_ok=True)
    results_path = output_dir / "case_results.jsonl"
    completed = _completed_case_ids(results_path) if args.resume_completed else set()

    results: list[dict[str, Any]] = []
    if args.resume_completed and results_path.exists():
        results.extend(_read_jsonl(results_path))

    for index, row in enumerate(rows, start=1):
        case_id = str(row.get("case_id") or f"case_{index:03d}")
        if case_id in completed:
            print(f"[skip] {case_id} already completed")
            continue
        prompt = str(row.get("query") or "").strip()
        if not prompt:
            result = {"case_id": case_id, "status": "failed", "returncode": 2, "error": "missing query"}
            _append_jsonl(results_path, result)
            results.append(result)
            continue

        print(f"[{index}/{len(rows)}] {case_id}")
        started = time.time()
        log_path = logs_dir / f"{case_id}.log"
        command = _graph_command(args, prompt, f"{run_id}-{case_id}")
        with log_path.open("w", encoding="utf-8") as log_handle:
            log_handle.write("$ " + _redacted_command(command) + "\n")
            log_handle.flush()
            completed_proc = subprocess.run(
                command,
                cwd=REPO_ROOT,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )

        run_root = _find_run_root(prompt, started)
        result = _collect_case_result(
            args=args,
            eval_path=eval_path,
            case_id=case_id,
            query=prompt,
            returncode=completed_proc.returncode,
            elapsed_sec=round(time.time() - started, 4),
            run_root=run_root,
            log_path=log_path,
        )
        _append_jsonl(results_path, result)
        results.append(result)
        _write_summary(output_dir, run_id, eval_path, rows, results, in_progress=True)

    _write_summary(output_dir, run_id, eval_path, rows, results, in_progress=False)
    print(json.dumps(_summary_payload(run_id, eval_path, rows, results, in_progress=False), ensure_ascii=False, indent=2))
    return 0


def _graph_command(args: argparse.Namespace, prompt: str, thread_id: str) -> list[str]:
    command = [
        args.python,
        "scripts/cloud/sec_agent_graph_runner.py",
        "--prompt",
        prompt,
        "--thread-id",
        thread_id,
        "--llm-backend",
        args.llm_backend,
        "--base-url",
        args.base_url,
        "--chat-completions-path",
        args.chat_completions_path,
        "--model",
        args.model,
        "--query-planner",
        args.query_planner,
        "--quiet",
        "--bge-first",
        "--bge-device",
        args.bge_device,
    ]
    if args.api_key_env:
        command.extend(["--api-key-env", args.api_key_env])
    return command


def _collect_case_result(
    *,
    args: argparse.Namespace,
    eval_path: Path,
    case_id: str,
    query: str,
    returncode: int,
    elapsed_sec: float,
    run_root: Path | None,
    log_path: Path,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "case_id": case_id,
        "query": query,
        "returncode": returncode,
        "elapsed_sec": elapsed_sec,
        "log_path": str(log_path.resolve()),
        "run_root": str(run_root.resolve()) if run_root else "",
    }
    if run_root is None:
        result.update({"status": "failed", "error": "run_root_not_found"})
        return result

    memo_report_path = run_root / "memo_quality_report.json"
    score_cmd = [
        args.python,
        "scripts/score_sec_agent_memo_quality.py",
        "--run-dir",
        str(run_root),
        "--eval-set",
        str(eval_path),
        "--output-path",
        str(memo_report_path),
        "--pass-threshold",
        str(args.pass_threshold),
    ]
    score_proc = subprocess.run(score_cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=False)
    if score_proc.returncode != 0:
        (run_root / "memo_quality_score_error.log").write_text(
            (score_proc.stdout or "") + (score_proc.stderr or ""),
            encoding="utf-8",
        )

    state = _read_json(run_root / "sec_agent_state.json")
    gate_summary = _read_json(run_root / "post_gates" / "sec_benchmark_post_gates_summary.json")
    run_summary = _read_json(run_root / "qwen" / "run_summary.json")
    memo_report = _read_json(memo_report_path)
    memo_case = (memo_report.get("case_results") or [{}])[0] if isinstance(memo_report.get("case_results"), list) else {}
    gateway = run_summary.get("llm_gateway") or {}
    failed_gate_keys = sorted(key for key, value in gate_summary.items() if key.endswith("_gate_pass") and value is False)
    gate_pass_count = sum(1 for key, value in gate_summary.items() if key.endswith("_gate_pass") and value is True)
    gate_checked_count = sum(1 for key in gate_summary if key.endswith("_gate_pass"))
    result.update(
        {
            "status": state.get("status") or ("completed" if returncode == 0 else "failed"),
            "graph_status": state.get("status"),
            "gate_pass_count": gate_pass_count,
            "gate_checked_count": gate_checked_count,
            "failed_gate_keys": failed_gate_keys,
            "all_gates_green": returncode == 0 and not failed_gate_keys and gate_checked_count > 0,
            "memo_quality": memo_case.get("score_total"),
            "memo_quality_pass": (memo_case.get("score_total") or 0) >= args.pass_threshold if memo_case else None,
            "memo_eval_case_id": memo_case.get("eval_case_id"),
            "api_latency_ms": gateway.get("latency_ms"),
            "total_tokens": gateway.get("total_tokens"),
            "input_tokens": gateway.get("input_tokens"),
            "output_tokens": gateway.get("output_tokens"),
            "provider": gateway.get("provider"),
            "model": gateway.get("model"),
            "memo_quality_report": str(memo_report_path.resolve()) if memo_report_path.exists() else "",
            "gate_summary_path": str((run_root / "post_gates" / "sec_benchmark_post_gates_summary.json").resolve())
            if (run_root / "post_gates" / "sec_benchmark_post_gates_summary.json").exists()
            else "",
        }
    )
    return result


def _find_run_root(prompt: str, started: float) -> Path | None:
    output_root = REPO_ROOT / "eval" / "sec_cases" / "outputs" / "interactive_sec_agent"
    if not output_root.exists():
        return None
    candidates: list[Path] = []
    for path in output_root.iterdir():
        if not path.is_dir():
            continue
        case_path = path / "case.jsonl"
        if not case_path.exists():
            continue
        try:
            if path.stat().st_mtime < started - 10:
                continue
            case = _read_jsonl(case_path)[0]
        except Exception:
            continue
        if str(case.get("prompt") or case.get("query") or "") == prompt:
            candidates.append(path)
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.stat().st_mtime)


def _write_summary(
    output_dir: Path,
    run_id: str,
    eval_path: Path,
    selected_rows: list[dict[str, Any]],
    results: list[dict[str, Any]],
    *,
    in_progress: bool,
) -> None:
    (output_dir / "summary.json").write_text(
        json.dumps(_summary_payload(run_id, eval_path, selected_rows, results, in_progress=in_progress), ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )


def _summary_payload(
    run_id: str,
    eval_path: Path,
    selected_rows: list[dict[str, Any]],
    results: list[dict[str, Any]],
    *,
    in_progress: bool,
) -> dict[str, Any]:
    completed_results = [row for row in results if row.get("run_root")]
    memo_scores = [float(row["memo_quality"]) for row in completed_results if row.get("memo_quality") is not None]
    gate_failures = [
        {"case_id": row.get("case_id"), "failed_gate_keys": row.get("failed_gate_keys") or [], "run_root": row.get("run_root")}
        for row in completed_results
        if row.get("failed_gate_keys")
    ]
    return {
        "schema_version": "sec_agent_memo_eval_batch_summary_v0.1",
        "run_id": run_id,
        "status": "in_progress" if in_progress else "completed",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "eval_set": str(eval_path.resolve()),
        "case_count": len(selected_rows),
        "recorded_result_count": len(results),
        "completed_count": len(completed_results),
        "all_gates_green_count": sum(bool(row.get("all_gates_green")) for row in completed_results),
        "memo_quality_count": len(memo_scores),
        "mean_memo_quality": round(sum(memo_scores) / len(memo_scores), 4) if memo_scores else None,
        "mean_api_latency_ms": round(
            sum(float(row.get("api_latency_ms") or 0) for row in completed_results if row.get("api_latency_ms") is not None)
            / max(sum(1 for row in completed_results if row.get("api_latency_ms") is not None), 1),
            2,
        )
        if completed_results
        else None,
        "total_tokens": sum(int(row.get("total_tokens") or 0) for row in completed_results),
        "gate_failures": gate_failures,
        "failed_or_incomplete_cases": [
            row.get("case_id")
            for row in results
            if row.get("returncode") not in (0, None) or not row.get("run_root")
        ],
        "case_results": results,
    }


def _completed_case_ids(path: Path) -> set[str]:
    return {str(row.get("case_id") or "") for row in _read_jsonl(path) if row.get("returncode") == 0 and row.get("run_root")}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else REPO_ROOT / value


def _redacted_command(command: list[str]) -> str:
    return " ".join("'" + part.replace("'", "'\\''") + "'" if any(ch.isspace() for ch in part) else part for part in command)


if __name__ == "__main__":
    raise SystemExit(main())
