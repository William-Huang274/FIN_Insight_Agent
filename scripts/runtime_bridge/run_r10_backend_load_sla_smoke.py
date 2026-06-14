from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
JAVA_SRC = REPO_ROOT / "apps" / "research_gateway" / "java" / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

from sec_agent.runtime_bridge.object_store import put_json_object
from sec_agent.run_audit_store import materialize_run_audit_store, read_run_audit_counts
from sec_agent.runtime_readiness import _sample_state


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    work_root = Path(args.work_root).resolve() if args.work_root else Path(tempfile.mkdtemp(prefix="finsight_r10_load_"))
    report = run_load_smoke(args, work_root=work_root, output_dir=output_dir)
    out = output_dir / "r10_backend_load_sla_smoke_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    if report["status"] != "pass":
        raise SystemExit(1)


def run_load_smoke(args: argparse.Namespace, *, work_root: Path, output_dir: Path) -> dict[str, Any]:
    started = time.monotonic()
    javac = shutil.which("javac")
    java = shutil.which("java")
    if not javac or not java:
        return {"schema_version": "finsight_r10_backend_load_sla_smoke_v0_1", "status": "fail", "errors": [{"type": "jdk_missing"}]}
    classes_dir = work_root / "classes"
    state_dir = work_root / "gateway_state"
    queue_dir = work_root / "gateway_queue"
    classes_dir.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)
    queue_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run([javac, "-encoding", "UTF-8", "-d", str(classes_dir), *[str(path) for path in sorted(JAVA_SRC.rglob("*.java"))]], cwd=REPO_ROOT, check=True)
    port = free_port()
    gateway_log_path = work_root / "gateway.log"
    gateway_log = gateway_log_path.open("w", encoding="utf-8")
    gateway = subprocess.Popen(
        [java, "-cp", str(classes_dir), "finsight.gateway.TaskGatewayServer"],
        cwd=REPO_ROOT,
        env=_gateway_env(port=port, state_dir=state_dir, queue_dir=queue_dir),
        stdout=gateway_log,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        wait_for_health(port, gateway_log_path=gateway_log_path)
        task_timings: dict[str, dict[str, Any]] = {}
        for idx in range(args.tasks):
            created_started = time.monotonic()
            payload = {
                "query": f"R10 load smoke task {idx} NVDA MSFT",
                "user_id": "r10_smoke",
                "mode": "local_smoke",
                "metadata": {"run_id": f"r10_load_smoke_{idx:03d}"},
            }
            task = request_json(f"http://127.0.0.1:{port}/api/research/tasks", method="POST", payload=payload, expected_status=202)
            task_timings[task["task_id"]] = {"created_ms": int((time.monotonic() - created_started) * 1000), "submitted_at": time.monotonic()}

        workers_started = time.monotonic()
        _drain_with_worker_pool(args, port=port, queue_dir=queue_dir, worker_count=args.workers, expected_success=args.tasks)
        task_results = []
        for task_id, timing in task_timings.items():
            completed = request_json(f"http://127.0.0.1:{port}/api/research/tasks/{task_id}")
            events = request_json(f"http://127.0.0.1:{port}/api/research/tasks/{task_id}/events?limit=200")
            elapsed_ms = int((time.monotonic() - float(timing["submitted_at"])) * 1000)
            task_results.append(
                {
                    "task_id": task_id,
                    "status": completed.get("status"),
                    "progress": completed.get("progress"),
                    "elapsed_ms": elapsed_ms,
                    "event_count": len(events.get("events") or []),
                    "memo_present": bool(completed.get("memo")),
                    "evidence_count": len(completed.get("evidence") or []),
                }
            )
        sse_text = request_text(f"http://127.0.0.1:{port}/api/research/tasks/{next(iter(task_timings))}/events?limit=100", accept="text/event-stream")
        resume_report = _resume_one(args, port=port, queue_dir=queue_dir, task_id=next(iter(task_timings)))
        audit_pressure = _audit_object_store_pressure(output_dir, rows=args.audit_rows)
        latencies = [int(item["elapsed_ms"]) for item in task_results]
        status_counts: dict[str, int] = {}
        for item in task_results:
            status = str(item.get("status") or "")
            status_counts[status] = status_counts.get(status, 0) + 1
        p95 = _percentile(latencies, 95)
        errors = []
        if status_counts.get("SUCCESS", 0) != args.tasks:
            errors.append({"type": "not_all_tasks_succeeded", "status_counts": status_counts})
        if p95 > args.p95_threshold_ms:
            errors.append({"type": "p95_latency_exceeded", "p95_ms": p95, "threshold_ms": args.p95_threshold_ms})
        if "event: heartbeat" not in sse_text or "event: task-event" not in sse_text:
            errors.append({"type": "sse_missing_heartbeat_or_task_event"})
        if resume_report.get("status") != "pass":
            errors.append({"type": "resume_failed", "resume_report": resume_report})
        if audit_pressure.get("status") != "pass":
            errors.append({"type": "audit_object_store_pressure_failed", "audit_pressure": audit_pressure})
        return {
            "schema_version": "finsight_r10_backend_load_sla_smoke_v0_1",
            "status": "fail" if errors else "pass",
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "work_root": str(work_root),
            "policy": {
                "tasks": args.tasks,
                "workers": args.workers,
                "queue_mode": "file",
                "store_mode": "file",
                "p95_threshold_ms": args.p95_threshold_ms,
                "provider_latency": "not_applicable_local_smoke",
                "token_cost": "not_applicable_local_smoke",
            },
            "worker_elapsed_ms": int((time.monotonic() - workers_started) * 1000),
            "status_counts": status_counts,
            "latency_ms": {"p50": _percentile(latencies, 50), "p95": p95, "max": max(latencies) if latencies else 0},
            "task_results": task_results,
            "sse_event_count": sse_text.count("event: task-event"),
            "sse_heartbeat_present": "event: heartbeat" in sse_text,
            "resume_report": resume_report,
            "audit_object_store_pressure": audit_pressure,
            "errors": errors,
        }
    finally:
        gateway.terminate()
        try:
            gateway.wait(timeout=10)
        except subprocess.TimeoutExpired:
            gateway.kill()
            gateway.wait(timeout=10)
        gateway_log.close()


def _drain_with_worker_pool(args: argparse.Namespace, *, port: int, queue_dir: Path, worker_count: int, expected_success: int) -> None:
    completed = 0
    deadline = time.time() + args.timeout_s
    while completed < expected_success and time.time() < deadline:
        batch = []
        for _ in range(min(worker_count, expected_success - completed)):
            batch.append(_start_worker(args, port=port, queue_dir=queue_dir))
        for proc in batch:
            try:
                output, _ = proc.communicate(timeout=args.worker_timeout_s)
            except subprocess.TimeoutExpired:
                proc.kill()
                output, _ = proc.communicate(timeout=10)
                raise RuntimeError(f"worker timed out; output_tail={_tail(output)}")
            if proc.returncode != 0:
                raise RuntimeError(f"worker failed with {proc.returncode}; output_tail={_tail(output)}")
            completed += _processed_count_from_worker_output(output)
    if completed < expected_success:
        raise RuntimeError(f"worker_pool_timeout completed={completed} expected={expected_success}")


def _processed_count_from_worker_output(output: str | None) -> int:
    if not output:
        return 0
    for line in reversed(output.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        return int(value.get("processed") or 0)
    return 0


def _tail(output: str | None, *, limit: int = 2000) -> str:
    text = output or ""
    return text[-limit:]


def _start_worker(args: argparse.Namespace, *, port: int, queue_dir: Path) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [
            sys.executable,
            str(REPO_ROOT / "src" / "sec_agent" / "runtime_bridge" / "task_worker.py"),
            "--once",
            "--queue-mode",
            "file",
            "--queue-dir",
            str(queue_dir),
            "--gateway-url",
            f"http://127.0.0.1:{port}",
            "--run-timeout-s",
            str(args.worker_timeout_s),
            "--repo-root",
            str(REPO_ROOT),
            "--bge-device",
            args.bge_device,
        ],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _resume_one(args: argparse.Namespace, *, port: int, queue_dir: Path, task_id: str) -> dict[str, Any]:
    resumed = request_json(f"http://127.0.0.1:{port}/api/research/tasks/{task_id}/resume", method="POST", expected_status=202)
    progress = resumed.get("progress")
    if resumed.get("status") != "PENDING" or progress is None or int(progress) != 0:
        return {"status": "fail", "reason": "resume_did_not_reset", "task": resumed}
    proc = _start_worker(args, port=port, queue_dir=queue_dir)
    proc.wait(timeout=args.worker_timeout_s)
    completed = request_json(f"http://127.0.0.1:{port}/api/research/tasks/{task_id}")
    return {"status": "pass" if proc.returncode == 0 and completed.get("status") == "SUCCESS" else "fail", "worker_returncode": proc.returncode, "task": completed}


def _audit_object_store_pressure(output_dir: Path, *, rows: int) -> dict[str, Any]:
    started = time.monotonic()
    db_path = output_dir / "r10_run_audit_pressure.sqlite"
    object_root = output_dir / "r10_object_store"
    for idx in range(rows):
        state = json.loads(json.dumps(_sample_state(), ensure_ascii=False))
        state["run_id"] = f"r10_audit_pressure_{idx:04d}"
        ref = put_json_object({"idx": idx, "payload": "r10 pressure"}, object_store_root=object_root, namespace="r10", stem=f"sample_{idx:04d}")
        state["artifact_refs"]["r10_object_ref"] = ref["artifact_uri"]
        materialize_run_audit_store(db_path, state)
    counts = read_run_audit_counts(db_path)
    errors = []
    if counts.get("run", 0) < rows:
        errors.append({"type": "run_rows_missing", "expected": rows, "actual": counts.get("run", 0)})
    if counts.get("artifact_ref", 0) < rows:
        errors.append({"type": "artifact_rows_missing", "expected_min": rows, "actual": counts.get("artifact_ref", 0)})
    return {
        "status": "fail" if errors else "pass",
        "rows": rows,
        "elapsed_ms": int((time.monotonic() - started) * 1000),
        "db_path": str(db_path),
        "object_store_root": str(object_root),
        "counts": counts,
        "errors": errors,
    }


def _gateway_env(*, port: int, state_dir: Path, queue_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "FINSIGHT_GATEWAY_HOST": "127.0.0.1",
            "FINSIGHT_GATEWAY_PORT": str(port),
            "FINSIGHT_GATEWAY_STORE_MODE": "file",
            "FINSIGHT_GATEWAY_STATE_DIR": str(state_dir),
            "FINSIGHT_GATEWAY_QUEUE_MODE": "file",
            "FINSIGHT_GATEWAY_QUEUE_DIR": str(queue_dir),
        }
    )
    return env


def request_json(url: str, *, method: str = "GET", payload: dict | None = None, expected_status: int = 200) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=20) as response:
        if response.status != expected_status:
            raise RuntimeError(f"unexpected_status: {response.status}")
        return json.loads(response.read().decode("utf-8"))


def request_text(url: str, *, method: str = "GET", payload: dict | None = None, accept: str = "text/plain", expected_status: int = 200) -> str:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=data, method=method, headers={"Accept": accept, "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=20) as response:
        if response.status != expected_status:
            raise RuntimeError(f"unexpected_status: {response.status}")
        return response.read().decode("utf-8")


def wait_for_health(port: int, *, gateway_log_path: Path) -> None:
    deadline = time.time() + 20
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            if request_json(f"http://127.0.0.1:{port}/api/health")["status"] == "ok":
                return
        except Exception as exc:
            last_error = exc
            time.sleep(0.2)
    log_tail = gateway_log_path.read_text(encoding="utf-8", errors="replace")[-2000:] if gateway_log_path.exists() else ""
    raise RuntimeError(f"gateway did not start: {last_error}; gateway_log_tail={log_tail}")


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _percentile(values: list[int], percentile: int) -> int:
    if not values:
        return 0
    if len(values) == 1:
        return int(values[0])
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((percentile / 100) * (len(ordered) - 1))))
    return int(ordered[index])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run R10 backend load/SLA smoke over Java gateway and Python workers.")
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "reports" / "quality" / "r10_backend_load_sla_smoke")
    parser.add_argument("--work-root", type=Path, default=None)
    parser.add_argument("--tasks", type=int, default=8)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--audit-rows", type=int, default=24)
    parser.add_argument("--timeout-s", type=float, default=120.0)
    parser.add_argument("--worker-timeout-s", type=float, default=30.0)
    parser.add_argument("--p95-threshold-ms", type=int, default=45000)
    parser.add_argument("--bge-device", default=os.environ.get("BGE_DEVICE", "auto"))
    return parser.parse_args()


if __name__ == "__main__":
    main()
