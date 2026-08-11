from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


SRC_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = SRC_ROOT.parent
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.runtime_bridge.data_quality import evaluate_data_processing_quality
from sec_agent.runtime_bridge.eval_store import record_eval_case_result, record_eval_gold_promotion
from sec_agent.runtime_bridge.resource_scheduler import InferenceTask, schedule_inference_tasks
from sec_agent.workbench.job_runner import build_eval_command


TERMINAL_STATUSES = {"SUCCESS", "FAILED", "CANCELLED"}
REAL_EVAL_IDS = {
    "context_api_smoke",
    "context_api_load_smoke",
    "agent_graph_vnext_run_audit_smoke",
    "agent_graph_vnext_diagnostic_probe",
    "agent_graph_vnext_g11_full_chain",
    "agent_graph_vnext_r12_successor_12",
    "agent_graph_vnext_broader_release_20",
    "agent_graph_vnext_load_mix_15",
}


@dataclass(frozen=True)
class WorkerConfig:
    queue_mode: str
    queue_dir: Path
    redis_host: str
    redis_port: int
    redis_queue_key: str
    gateway_url: str
    worker_token: str
    poll_interval_s: float
    timeout_s: float
    run_timeout_s: float
    once: bool
    repo_root: Path
    eval_store_path: Path
    default_eval_id: str
    python_executable: str
    bge_device: str
    api_key_env: str


def run_worker(config: WorkerConfig) -> dict[str, Any]:
    started = time.monotonic()
    processed = 0
    while True:
        payload = _pop_task(config)
        if payload:
            processed += 1
            _process_payload(payload, config)
            if config.once:
                break
        elif config.once:
            break
        elif time.monotonic() - started > config.timeout_s:
            break
        else:
            time.sleep(config.poll_interval_s)
    return {
        "schema_version": "finsight_python_research_worker_v0_2",
        "processed": processed,
        "queue_mode": config.queue_mode,
        "status": "ok",
    }


def _pop_task(config: WorkerConfig) -> dict[str, Any] | None:
    if config.queue_mode == "redis":
        raw = _redis_rpop(config.redis_host, config.redis_port, config.redis_queue_key)
        return json.loads(raw) if raw else None
    return _pop_file_task(config.queue_dir)


def _pop_file_task(queue_dir: Path) -> dict[str, Any] | None:
    pending = queue_dir / "pending"
    inflight = queue_dir / "inflight"
    done = queue_dir / "done"
    pending.mkdir(parents=True, exist_ok=True)
    inflight.mkdir(parents=True, exist_ok=True)
    done.mkdir(parents=True, exist_ok=True)
    files = sorted(path for path in pending.glob("*.json") if path.is_file())
    for source in files:
        target = inflight / source.name
        try:
            shutil.move(str(source), str(target))
        except (FileNotFoundError, PermissionError, OSError):
            # Another local worker may have claimed this file after glob().
            continue
        payload = json.loads(target.read_text(encoding="utf-8"))
        shutil.move(str(target), str(done / target.name))
        return payload
    return None


def _process_payload(payload: dict[str, Any], config: WorkerConfig) -> None:
    task_id = str(payload.get("task_id") or "").strip()
    callback_url = str(payload.get("callback_url") or "").strip()
    if not task_id:
        raise ValueError("task_id_required")
    if not callback_url:
        callback_url = f"{config.gateway_url.rstrip('/')}/api/research/tasks/{task_id}/worker-events"
    try:
        _post_update(
            callback_url,
            {
                "status": "RUNNING",
                "progress": 10,
                "events": [{"stream": "worker", "message": "task dequeued by Python worker"}],
            },
            token=config.worker_token,
        )
        if _is_cancel_requested(config, task_id):
            _post_update(
                callback_url,
                {
                    "status": "CANCELLED",
                    "progress": 100,
                    "error_message": "cancelled before execution",
                    "events": [{"stream": "worker", "message": "cancelled before execution"}],
                },
                token=config.worker_token,
            )
            return

        mode = str(payload.get("mode") or "local_smoke").strip()
        if _is_real_eval_mode(mode, payload):
            result = _run_workbench_eval(payload, config, callback_url=callback_url)
        else:
            result = _run_deterministic_research(payload)
        _post_update(
            callback_url,
            {
                "status": result.get("status", "SUCCESS"),
                "progress": 100,
                "memo": result.get("memo", ""),
                "evidence": result.get("evidence", []),
                "error_message": result.get("error_message", ""),
                "events": result.get("events", []),
            },
            token=config.worker_token,
        )
    except Exception as exc:  # pragma: no cover - exercised by integration failures
        _post_update(
            callback_url,
            {
                "status": "FAILED",
                "progress": 100,
                "error_message": f"{type(exc).__name__}: {exc}",
                "events": [{"stream": "worker", "message": f"worker failed: {type(exc).__name__}: {exc}"}],
            },
            token=config.worker_token,
        )
        raise


def _is_real_eval_mode(mode: str, payload: Mapping[str, Any]) -> bool:
    metadata = _metadata(payload)
    eval_id = str(metadata.get("eval_id") or mode or "").strip()
    return mode == "workbench_eval" or eval_id in REAL_EVAL_IDS


def _run_workbench_eval(payload: Mapping[str, Any], config: WorkerConfig, *, callback_url: str) -> dict[str, Any]:
    metadata = _metadata(payload)
    task_id = str(payload.get("task_id") or "").strip()
    eval_id = str(metadata.get("eval_id") or payload.get("mode") or config.default_eval_id).strip()
    if eval_id == "workbench_eval":
        eval_id = config.default_eval_id
    if eval_id not in REAL_EVAL_IDS:
        raise ValueError(f"unsupported_workbench_eval_id: {eval_id}")
    run_id = _safe_id(str(metadata.get("run_id") or f"{task_id}_{eval_id}"))
    limit = _optional_int(metadata.get("limit"))
    selected_case_ids = _metadata_case_ids(metadata)
    output_path = config.repo_root / "reports" / "quality" / "workbench_eval" / f"{run_id}_{eval_id}.json"
    eval_store_path = _resolve_path(metadata.get("eval_store_path"), default=config.eval_store_path, repo_root=config.repo_root)

    spec = build_eval_command(repo_root=config.repo_root, eval_id=eval_id, job_id=run_id)
    args = list(spec.args)
    args[0] = config.python_executable
    if limit is not None and eval_id.startswith("agent_graph_vnext_"):
        args = _replace_or_append_arg(args, "--limit", str(limit))
    if selected_case_ids and eval_id.startswith("agent_graph_vnext_"):
        args = _append_repeatable_args(args, "--case-id", selected_case_ids)
    if "--summary-output-path" in args:
        args[args.index("--summary-output-path") + 1] = str(output_path)
    if "--bge-device" in args:
        args = _replace_or_append_arg(args, "--bge-device", config.bge_device)
    fanout_workers = _optional_int(metadata.get("evidence_operator_fanout_workers"))
    if fanout_workers is not None:
        args = _replace_or_append_arg(args, "--evidence-operator-fanout-workers", str(fanout_workers))

    env = os.environ.copy()
    env.update({key: str(value) for key, value in spec.env_overrides.items() if value is not None})
    env["BGE_DEVICE"] = config.bge_device
    env["API_KEY_ENV"] = config.api_key_env
    env.setdefault("LLM_BACKEND", "deepseek")
    _load_env_file_secrets(config.repo_root / ".env", env, allowed_keys={config.api_key_env})

    scheduler_rows = schedule_inference_tasks(
        [
            InferenceTask(f"{run_id}:retrieval", route="retrieval", priority=1, requires_cuda_bge=True),
            InferenceTask(f"{run_id}:lead_review", route="deterministic_gate", priority=2),
            InferenceTask(f"{run_id}:specialist", route="specialist", priority=3, requires_cuda_bge=True, model_tier="standard"),
            InferenceTask(f"{run_id}:memo", route="memo_writer", priority=4, model_tier="pro"),
            InferenceTask(f"{run_id}:verifier", route="deterministic_gate", priority=5),
        ],
        cuda_bge_slots=int(metadata.get("cuda_bge_slots") or 3),
        cpu_spillover_allowed=bool(metadata.get("cpu_spillover_allowed", True)),
        token_budget_pressure=bool(metadata.get("token_budget_pressure", False)),
    )
    _post_update(
        callback_url,
        {
            "status": "RUNNING",
            "progress": 25,
            "events": [
                {"stream": "worker", "message": f"starting Workbench eval {eval_id} run_id={run_id}"},
                {"stream": "resource", "message": json.dumps([row.__dict__ for row in scheduler_rows], ensure_ascii=False)},
            ],
        },
        token=config.worker_token,
    )

    command_result = _run_subprocess_with_events(
        args,
        cwd=config.repo_root,
        env=env,
        timeout_s=config.run_timeout_s,
        callback_url=callback_url,
        worker_token=config.worker_token,
        task_id=task_id,
        config=config,
    )
    summary = _read_json(output_path)
    status = _status_from_eval(command_result["return_code"], summary)
    node_results = _node_results_from_eval(summary, command_result=command_result, scheduler_rows=scheduler_rows)
    failure_events = _failure_events_from_eval(summary, command_result=command_result)
    data_quality = evaluate_data_processing_quality(_data_quality_records_from_summary(summary))
    if data_quality["status"] != "pass":
        failure_events.extend(data_quality["failure_events"])
    eval_record = record_eval_case_result(
        eval_store_path,
        {
            "eval_id": eval_id,
            "case_id": ",".join(selected_case_ids) if selected_case_ids else str(payload.get("case_id") or metadata.get("case_id") or task_id),
            "run_id": run_id,
            "status": "pass" if status == "SUCCESS" else "fail",
            "score": 1.0 if status == "SUCCESS" else 0.0,
            "criteria_version": "p0_p9_runtime_bridge_eval_v0_2",
            "data_snapshot_id": str(metadata.get("data_snapshot_id") or ""),
            "node_results": node_results,
            "failure_events": failure_events,
            "artifact_refs": _artifact_refs(summary, output_path=output_path),
        },
    )
    gold_promotion_record = _record_gold_candidates(
        eval_store_path,
        eval_id=eval_id,
        run_id=run_id,
        summary=summary,
    )
    evidence = [
        {
            "evidence_id": f"runtime_bridge_workbench_eval_{run_id}",
            "source_family": "runtime_bridge_workbench_eval",
            "claim_scope": "runtime_and_eval_verification",
            "eval_id": eval_id,
            "run_id": run_id,
            "gate_status": summary.get("gate_status") or summary.get("status") or "",
            "case_count": summary.get("case_count") or summary.get("metrics", {}).get("case_count") if isinstance(summary.get("metrics"), Mapping) else summary.get("case_count"),
            "pass_count": summary.get("pass_count") or summary.get("metrics", {}).get("passed") if isinstance(summary.get("metrics"), Mapping) else summary.get("pass_count"),
            "failure_count": summary.get("failure_count") or summary.get("metrics", {}).get("failed") if isinstance(summary.get("metrics"), Mapping) else summary.get("failure_count"),
            "artifact_refs": _artifact_refs(summary, output_path=output_path),
            "eval_store": eval_record,
            "gold_promotion": gold_promotion_record,
            "data_quality": data_quality,
            "resource_schedule": [row.__dict__ for row in scheduler_rows],
        }
    ]
    memo = (
        f"Workbench eval {eval_id} finished with status={status}; "
        f"run_id={run_id}; gate={summary.get('gate_status') or summary.get('status') or 'unknown'}; "
        f"summary={output_path}."
    )
    return {
        "status": status,
        "memo": memo,
        "evidence": evidence,
        "error_message": "" if status == "SUCCESS" else _failure_message(summary, command_result),
        "events": [{"stream": "worker", "message": memo}],
    }


def _run_deterministic_research(payload: Mapping[str, Any]) -> dict[str, Any]:
    query = str(payload.get("query") or "").strip()
    mode = str(payload.get("mode") or "local_smoke")
    words = [word.strip(".,;:!?()[]{}") for word in query.split() if word.strip()]
    tickers = sorted({word for word in words if word.isalpha() and 1 <= len(word) <= 5 and word.upper() == word})
    evidence = [
        {
            "evidence_id": f"bridge_query_digest_{abs(hash(query)) % 10_000_000}",
            "source_family": "runtime_bridge_smoke",
            "claim_scope": "process_verification_only",
            "text": "Java gateway accepted the task, the queue delivered it, and Python worker wrote back a bounded memo.",
            "mode": mode,
        }
    ]
    memo = (
        "Runtime bridge smoke passed. "
        "This memo is deterministic and only verifies Java task intake, queue dispatch, Python worker execution, "
        "status callback, and evidence payload shape. It is not an investment conclusion."
    )
    if tickers:
        memo += f" Detected ticker-like tokens for routing audit: {', '.join(tickers)}."
    return {"status": "SUCCESS", "memo": memo, "evidence": evidence}


def _run_subprocess_with_events(
    args: list[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    timeout_s: float,
    callback_url: str,
    worker_token: str,
    task_id: str,
    config: WorkerConfig,
) -> dict[str, Any]:
    started = time.monotonic()
    tail: deque[str] = deque(maxlen=40)
    process = subprocess.Popen(
        args,
        cwd=str(cwd),
        env=dict(env),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    assert process.stdout is not None
    last_callback = started
    line_count = 0
    try:
        while True:
            line = process.stdout.readline()
            if line:
                line_count += 1
                message = line.rstrip("\r\n")
                if message:
                    tail.append(message)
                now = time.monotonic()
                if now - last_callback >= 8.0 or line_count in {1, 5, 20}:
                    _post_update(
                        callback_url,
                        {
                            "status": "RUNNING",
                            "progress": 40,
                            "events": [{"stream": "stdout", "message": _truncate(message, 1800)}],
                        },
                        token=worker_token,
                    )
                    last_callback = now
            elif process.poll() is not None:
                break
            else:
                if time.monotonic() - started > timeout_s:
                    process.kill()
                    return {"return_code": 124, "tail": list(tail), "timed_out": True, "line_count": line_count}
                if _is_cancel_requested(config, task_id):
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                    return {"return_code": 130, "tail": list(tail), "cancelled": True, "line_count": line_count}
                time.sleep(0.2)
        return {"return_code": process.wait(), "tail": list(tail), "line_count": line_count}
    finally:
        if process.poll() is None:
            process.kill()


def _post_update(callback_url: str, payload: Mapping[str, Any], *, token: str = "") -> None:
    data = json.dumps(dict(payload), ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        callback_url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    if token:
        request.add_header("X-Worker-Token", token)
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status >= 300:
            raise RuntimeError(f"worker_callback_failed: {response.status}")


def _fetch_task(config: WorkerConfig, task_id: str) -> dict[str, Any] | None:
    url = f"{config.gateway_url.rstrip('/')}/api/research/tasks/{task_id}"
    try:
        request = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status != 200:
                return None
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return None


def _is_cancel_requested(config: WorkerConfig, task_id: str) -> bool:
    task = _fetch_task(config, task_id)
    return str((task or {}).get("status") or "").upper() == "CANCEL_REQUESTED"


def _status_from_eval(return_code: int, summary: Mapping[str, Any]) -> str:
    if return_code == 130:
        return "CANCELLED"
    if return_code != 0:
        return "FAILED"
    if summary.get("all_pass") is True:
        return "SUCCESS"
    status = str(summary.get("status") or summary.get("gate_status") or "").lower()
    return "SUCCESS" if status in {"pass", "ok", "completed"} else "FAILED"


def _failure_message(summary: Mapping[str, Any], command_result: Mapping[str, Any]) -> str:
    if command_result.get("cancelled"):
        return "cancelled by request"
    if command_result.get("timed_out"):
        return "workbench eval timed out"
    failed_cases = summary.get("failed_cases") or []
    tail = command_result.get("tail") or []
    return f"workbench eval failed; failed_cases={failed_cases}; tail={tail[-3:]}"


def _node_results_from_eval(
    summary: Mapping[str, Any],
    *,
    command_result: Mapping[str, Any],
    scheduler_rows: list[Any],
) -> list[dict[str, Any]]:
    status = "pass" if _status_from_eval(int(command_result.get("return_code") or 0), summary) == "SUCCESS" else "fail"
    nodes = [
        {"node": "java_gateway", "status": "pass", "metric_count": 1, "metrics": [{"name": "task_accepted", "value": 1}]},
        {
            "node": "python_worker",
            "status": "pass" if command_result.get("return_code") in {0, None} else "fail",
            "metric_count": 2,
            "metrics": [
                {"name": "stdout_line_count", "value": int(command_result.get("line_count") or 0)},
                {"name": "return_code", "value": int(command_result.get("return_code") or 0)},
            ],
        },
        {"node": "workbench_eval", "status": status, "metric_count": 1, "metrics": [{"name": "case_count", "value": int(summary.get("case_count") or 0)}]},
        {
            "node": "resource_scheduler",
            "status": "pass",
            "metric_count": len(scheduler_rows),
            "metrics": [{"name": "scheduled_tasks", "value": len(scheduler_rows)}],
        },
    ]
    for case in summary.get("cases") or []:
        if isinstance(case, Mapping):
            metrics = _case_eval_metrics(case)
            nodes.append(
                {
                    "node": f"case:{case.get('case_id') or 'unknown'}",
                    "status": "pass" if case.get("gate_status") == "pass" else "fail",
                    "metric_count": len(metrics),
                    "metrics": metrics,
                    "payload": dict(case),
                }
            )
    return nodes


def _case_eval_metrics(case: Mapping[str, Any]) -> list[dict[str, Any]]:
    metrics: list[dict[str, Any]] = []
    numeric_fields = (
        "elapsed_ms",
        "tool_call_count",
        "budgeted_tool_call_count",
        "cached_tool_call_count",
        "rendered_answer_chars",
        "memo_claim_count",
        "memo_dimension_analysis_count",
    )
    for field in numeric_fields:
        value = _number(case.get(field))
        if value is not None:
            metrics.append({"name": field, "value": value})
    total_tokens = _case_total_tokens(case)
    if total_tokens is not None:
        metrics.append({"name": "total_tokens", "value": total_tokens})
        rendered_chars = _number(case.get("rendered_answer_chars")) or 0.0
        if total_tokens > 0 and rendered_chars > 0:
            metrics.append({"name": "chars_per_token", "value": rendered_chars / total_tokens})
    return metrics


def _case_total_tokens(case: Mapping[str, Any]) -> float | None:
    values: list[float] = []
    audit = case.get("agent_audit")
    if not isinstance(audit, Mapping):
        return None
    for row in audit.values():
        if not isinstance(row, Mapping):
            continue
        diagnostics = row.get("diagnostics")
        if not isinstance(diagnostics, Mapping):
            continue
        value = _number(diagnostics.get("total_tokens"))
        if value is not None:
            values.append(value)
    return sum(values) if values else None


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except ValueError:
        return None


def _record_gold_candidates(db_path: Path, *, eval_id: str, run_id: str, summary: Mapping[str, Any]) -> dict[str, Any]:
    promoted = 0
    for case in summary.get("cases") or []:
        if not isinstance(case, Mapping) or case.get("gate_status") != "pass":
            continue
        case_id = str(case.get("case_id") or "").strip()
        if not case_id:
            continue
        record_eval_gold_promotion(
            db_path,
            {
                "eval_id": eval_id,
                "case_id": case_id,
                "state": "candidate",
                "criteria_version": "p0_p9_runtime_bridge_eval_v0_2",
                "review_method": "automatic_candidate_from_r12_pass_requires_human_review",
                "run_id": run_id,
                "gate_status": case.get("gate_status"),
                "artifact_refs": case.get("artifact_refs") or [],
            },
        )
        promoted += 1
    return {"status": "pass", "candidate_count": promoted}


def _failure_events_from_eval(summary: Mapping[str, Any], *, command_result: Mapping[str, Any]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    if command_result.get("return_code") not in {0, None}:
        failures.append(
            {
                "failure_type": "workbench_process_failed",
                "node": "workbench_eval",
                "expected": "return code 0",
                "actual": str(command_result.get("return_code")),
                "artifact_refs": command_result.get("tail") or [],
            }
        )
    for case_id in summary.get("failed_cases") or []:
        failures.append(
            {
                "failure_type": "case_gate_failed",
                "node": "workbench_eval",
                "expected": "case gate pass",
                "actual": str(case_id),
                "artifact_refs": _artifact_refs(summary, output_path=None),
            }
        )
    return failures


def _artifact_refs(summary: Mapping[str, Any], *, output_path: Path | None) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    if output_path is not None:
        refs.append({"kind": "workbench_summary", "uri": str(output_path.resolve())})
    for key in ("source_summary_path", "output_dir", "run_audit_db_path", "quality_audit_path"):
        value = summary.get(key)
        if value:
            refs.append({"kind": key, "uri": str(value)})
    return refs


def _data_quality_records_from_summary(summary: Mapping[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    source_summary_path = str(summary.get("source_summary_path") or "").strip()
    output_dir = str(summary.get("output_dir") or "").strip()
    if source_summary_path:
        records.append({"record_id": "source_summary_path", "text": source_summary_path})
    if output_dir:
        records.append({"record_id": "output_dir", "text": output_dir})
    for case in summary.get("cases") or []:
        if isinstance(case, Mapping):
            records.append(
                {
                    "record_id": f"case_{case.get('case_id') or len(records)}",
                    "text": json.dumps(case, ensure_ascii=False, sort_keys=True),
                }
            )
    return records


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"status": "fail", "gate_status": "missing_summary", "missing_path": str(path)}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"status": "fail", "gate_status": "invalid_summary_json", "error": str(exc), "path": str(path)}
    return value if isinstance(value, dict) else {"status": "fail", "gate_status": "summary_not_object", "path": str(path)}


def _metadata(payload: Mapping[str, Any]) -> dict[str, Any]:
    value = payload.get("metadata")
    return dict(value) if isinstance(value, Mapping) else {}


def _replace_or_append_arg(args: list[str], key: str, value: str) -> list[str]:
    updated = list(args)
    if key in updated:
        index = updated.index(key)
        if index + 1 < len(updated):
            updated[index + 1] = value
        else:
            updated.append(value)
        return updated
    updated.extend([key, value])
    return updated


def _append_repeatable_args(args: list[str], key: str, values: list[str]) -> list[str]:
    updated = list(args)
    for value in values:
        updated.extend([key, value])
    return updated


def _metadata_case_ids(metadata: Mapping[str, Any]) -> list[str]:
    raw = metadata.get("case_ids")
    if raw is None:
        raw = metadata.get("case_id")
    if raw is None:
        return []
    if isinstance(raw, str):
        return [part.strip() for part in raw.split(",") if part.strip()]
    if isinstance(raw, (list, tuple, set)):
        return [str(item).strip() for item in raw if str(item).strip()]
    return [str(raw).strip()]


def _load_env_file_secrets(path: Path, env: dict[str, str], *, allowed_keys: set[str]) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in allowed_keys or env.get(key):
            continue
        env[key] = _strip_env_value(value.strip())


def _strip_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _resolve_path(value: Any, *, default: Path, repo_root: Path) -> Path:
    if not value:
        return default
    path = Path(str(value))
    return path if path.is_absolute() else repo_root / path


def _safe_id(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "_.-" else "_" for ch in value).strip("_")
    return cleaned or "runtime_bridge_run"


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    try:
        return int(float(str(value)))
    except ValueError:
        return None


def _truncate(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: limit - 3] + "..."


def _redis_rpop(host: str, port: int, key: str) -> str | None:
    with socket.create_connection((host, port), timeout=5) as sock:
        sock.sendall(_redis_command("RPOP", key))
        return _read_redis_bulk(sock)


def _redis_command(*parts: str) -> bytes:
    chunks: list[bytes] = [f"*{len(parts)}\r\n".encode("utf-8")]
    for part in parts:
        raw = part.encode("utf-8")
        chunks.append(f"${len(raw)}\r\n".encode("utf-8"))
        chunks.append(raw + b"\r\n")
    return b"".join(chunks)


def _read_redis_bulk(sock: socket.socket) -> str | None:
    line = _readline(sock)
    if line == b"$-1\r\n":
        return None
    if not line.startswith(b"$"):
        raise RuntimeError(f"unexpected_redis_response: {line!r}")
    length = int(line[1:-2])
    data = _read_exact(sock, length)
    _read_exact(sock, 2)
    return data.decode("utf-8")


def _readline(sock: socket.socket) -> bytes:
    data = bytearray()
    while not data.endswith(b"\r\n"):
        chunk = sock.recv(1)
        if not chunk:
            break
        data.extend(chunk)
    return bytes(data)


def _read_exact(sock: socket.socket, length: int) -> bytes:
    data = bytearray()
    while len(data) < length:
        chunk = sock.recv(length - len(data))
        if not chunk:
            raise RuntimeError("redis_connection_closed")
        data.extend(chunk)
    return bytes(data)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Consume Java gateway research tasks and write back worker results.")
    parser.add_argument("--queue-mode", choices=("file", "redis"), default="file")
    parser.add_argument("--queue-dir", type=Path, default=Path("data/runtime_bridge/java_gateway/queue"))
    parser.add_argument("--redis-host", default="127.0.0.1")
    parser.add_argument("--redis-port", type=int, default=6379)
    parser.add_argument("--redis-queue-key", default="finsight:research_tasks")
    parser.add_argument("--gateway-url", default="http://127.0.0.1:8780")
    parser.add_argument("--worker-token", default="")
    parser.add_argument("--poll-interval-s", type=float, default=0.2)
    parser.add_argument("--timeout-s", type=float, default=30.0)
    parser.add_argument("--run-timeout-s", type=float, default=2400.0)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--eval-store-path", type=Path, default=Path("data/workbench_private/runtime_bridge/eval_store.sqlite"))
    parser.add_argument("--default-eval-id", default="agent_graph_vnext_run_audit_smoke")
    parser.add_argument("--python-executable", default=sys.executable)
    parser.add_argument("--bge-device", default=os.environ.get("BGE_DEVICE", "cpu"))
    parser.add_argument("--api-key-env", default=os.environ.get("API_KEY_ENV", "DEEPSEEK_API_KEY"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    eval_store_path = args.eval_store_path if args.eval_store_path.is_absolute() else repo_root / args.eval_store_path
    result = run_worker(
        WorkerConfig(
            queue_mode=args.queue_mode,
            queue_dir=args.queue_dir.resolve(),
            redis_host=args.redis_host,
            redis_port=args.redis_port,
            redis_queue_key=args.redis_queue_key,
            gateway_url=args.gateway_url,
            worker_token=args.worker_token,
            poll_interval_s=args.poll_interval_s,
            timeout_s=args.timeout_s,
            run_timeout_s=args.run_timeout_s,
            once=args.once,
            repo_root=repo_root,
            eval_store_path=eval_store_path,
            default_eval_id=args.default_eval_id,
            python_executable=args.python_executable,
            bge_device=args.bge_device,
            api_key_env=args.api_key_env,
        )
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
