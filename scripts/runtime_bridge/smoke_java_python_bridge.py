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


REPO_ROOT = Path(__file__).resolve().parents[2]
JAVA_SRC = REPO_ROOT / "apps" / "research_gateway" / "java" / "src"


def main() -> None:
    args = parse_args()
    javac = shutil.which("javac")
    java = shutil.which("java")
    if not javac or not java:
        raise SystemExit("JDK javac/java are required for this smoke")
    work_root = Path(args.work_root).resolve() if args.work_root else Path(tempfile.mkdtemp(prefix="finsight_bridge_smoke_"))
    classes_dir = work_root / "classes"
    state_dir = work_root / "gateway_state"
    queue_dir = work_root / "gateway_queue"
    classes_dir.mkdir(parents=True, exist_ok=True)
    sources = sorted(str(path) for path in JAVA_SRC.rglob("*.java"))
    subprocess.run([javac, "-encoding", "UTF-8", "-d", str(classes_dir), *sources], cwd=REPO_ROOT, check=True)
    port = args.port or free_port()
    env = gateway_env(args, port=port, state_dir=state_dir, queue_dir=queue_dir)
    classpath = str(classes_dir)
    if args.jdbc_driver_jar:
        classpath = os.pathsep.join([classpath, str(Path(args.jdbc_driver_jar).resolve())])
    gateway_log_path = work_root / "gateway.log"
    gateway_log = gateway_log_path.open("w", encoding="utf-8")
    gateway = subprocess.Popen(
        [java, "-cp", classpath, "finsight.gateway.TaskGatewayServer"],
        cwd=REPO_ROOT,
        env=env,
        stdout=gateway_log,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        wait_for_health(port, gateway_log_path=gateway_log_path)
        payload = {
            "query": args.query,
            "user_id": "smoke_user",
            "mode": args.task_mode,
            "metadata": {},
        }
        if args.task_mode == "workbench_eval" or args.task_mode.startswith("agent_graph_vnext_") or args.task_mode.startswith("context_api_"):
            payload["metadata"] = {
                "eval_id": args.eval_id,
                "limit": args.limit,
                "run_id": args.run_id or f"runtime_bridge_{args.task_mode}_{int(time.time())}",
                "token_budget_pressure": args.token_budget_pressure,
            }
        task = request_json(
            f"http://127.0.0.1:{port}/api/research/tasks",
            method="POST",
            payload=payload,
            expected_status=202,
        )
        worker_args = [
            sys.executable,
            str(REPO_ROOT / "src" / "sec_agent" / "runtime_bridge" / "task_worker.py"),
            "--once",
            "--queue-mode",
            args.queue_mode,
            "--gateway-url",
            f"http://127.0.0.1:{port}",
            "--run-timeout-s",
            str(args.worker_run_timeout_s),
            "--repo-root",
            str(REPO_ROOT),
            "--bge-device",
            args.bge_device,
        ]
        if args.queue_mode == "file":
            worker_args.extend(["--queue-dir", str(queue_dir)])
        else:
            worker_args.extend(
                [
                    "--redis-host",
                    args.redis_host,
                    "--redis-port",
                    str(args.redis_port),
                    "--redis-queue-key",
                    args.redis_queue_key,
                ]
            )
        subprocess.run(worker_args, cwd=REPO_ROOT, check=True)
        completed = request_json(f"http://127.0.0.1:{port}/api/research/tasks/{task['task_id']}")
        events = request_json(f"http://127.0.0.1:{port}/api/research/tasks/{task['task_id']}/events?limit=500")
        if completed["status"] != args.expected_status:
            raise RuntimeError(f"task status {completed['status']} != expected {args.expected_status}: {completed.get('error_message')}")
        print(
            json.dumps(
                {
                    "work_root": str(work_root),
                    "store_mode": args.store_mode,
                    "queue_mode": args.queue_mode,
                    "task": completed,
                    "event_count": len(events.get("events") or []),
                    "latest_events": (events.get("events") or [])[-5:],
                },
                ensure_ascii=True,
                indent=2,
            )
        )
    finally:
        gateway.terminate()
        try:
            gateway.wait(timeout=10)
        except subprocess.TimeoutExpired:
            gateway.kill()
            gateway.wait(timeout=10)
        gateway_log.close()


def gateway_env(args: argparse.Namespace, *, port: int, state_dir: Path, queue_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "FINSIGHT_GATEWAY_HOST": "127.0.0.1",
            "FINSIGHT_GATEWAY_PORT": str(port),
            "FINSIGHT_GATEWAY_STORE_MODE": args.store_mode,
            "FINSIGHT_GATEWAY_STATE_DIR": str(state_dir),
            "FINSIGHT_GATEWAY_QUEUE_MODE": args.queue_mode,
            "FINSIGHT_GATEWAY_QUEUE_DIR": str(queue_dir),
            "FINSIGHT_REDIS_HOST": args.redis_host,
            "FINSIGHT_REDIS_PORT": str(args.redis_port),
            "FINSIGHT_REDIS_QUEUE_KEY": args.redis_queue_key,
        }
    )
    if args.store_mode == "jdbc":
        env["FINSIGHT_JDBC_URL"] = args.jdbc_url or os.environ.get("FINSIGHT_JDBC_URL", "")
        env["FINSIGHT_JDBC_USER"] = args.jdbc_user or os.environ.get("FINSIGHT_JDBC_USER", "")
        env["FINSIGHT_JDBC_PASSWORD"] = os.environ.get(args.jdbc_password_env, "")
    return env


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-test Java gateway -> queue -> Python worker -> Java callback.")
    parser.add_argument("--query", default="Check NVDA runtime bridge")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--work-root", type=Path, default=None)
    parser.add_argument("--store-mode", choices=("file", "jdbc"), default="file")
    parser.add_argument("--queue-mode", choices=("file", "redis"), default="file")
    parser.add_argument("--redis-host", default="127.0.0.1")
    parser.add_argument("--redis-port", type=int, default=6379)
    parser.add_argument("--redis-queue-key", default="finsight:research_tasks")
    parser.add_argument("--jdbc-url", default="")
    parser.add_argument("--jdbc-user", default="")
    parser.add_argument("--jdbc-password-env", default="FINSIGHT_JDBC_PASSWORD")
    parser.add_argument("--jdbc-driver-jar", type=Path, default=None)
    parser.add_argument("--task-mode", default="local_smoke")
    parser.add_argument("--eval-id", default="agent_graph_vnext_run_audit_smoke")
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--worker-run-timeout-s", type=float, default=2400.0)
    parser.add_argument("--bge-device", default=os.environ.get("BGE_DEVICE", "cpu"))
    parser.add_argument("--token-budget-pressure", action="store_true")
    parser.add_argument("--expected-status", choices=("SUCCESS", "FAILED", "CANCELLED"), default="SUCCESS")
    return parser.parse_args()


def request_json(url: str, *, method: str = "GET", payload: dict | None = None, expected_status: int = 200) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=10) as response:
        if response.status != expected_status:
            raise RuntimeError(f"unexpected_status: {response.status}")
        return json.loads(response.read().decode("utf-8"))


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
    log_tail = ""
    if gateway_log_path.exists():
        log_tail = gateway_log_path.read_text(encoding="utf-8", errors="replace")[-2000:]
    raise RuntimeError(f"gateway did not start: {last_error}; gateway_log_tail={log_tail}")


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


if __name__ == "__main__":
    main()
