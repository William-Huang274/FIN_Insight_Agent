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
    gateway = subprocess.Popen(
        [java, "-cp", str(classes_dir), "finsight.gateway.TaskGatewayServer"],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        wait_for_health(port)
        task = request_json(
            f"http://127.0.0.1:{port}/api/research/tasks",
            method="POST",
            payload={"query": args.query, "user_id": "smoke_user", "mode": "local_smoke"},
            expected_status=202,
        )
        subprocess.run(
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
            ],
            cwd=REPO_ROOT,
            check=True,
        )
        completed = request_json(f"http://127.0.0.1:{port}/api/research/tasks/{task['task_id']}")
        print(json.dumps({"work_root": str(work_root), "task": completed}, ensure_ascii=False, indent=2))
    finally:
        gateway.terminate()
        try:
            gateway.wait(timeout=10)
        except subprocess.TimeoutExpired:
            gateway.kill()
            gateway.wait(timeout=10)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-test Java gateway -> queue -> Python worker -> Java callback.")
    parser.add_argument("--query", default="Check NVDA runtime bridge")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--work-root", type=Path, default=None)
    return parser.parse_args()


def request_json(url: str, *, method: str = "GET", payload: dict | None = None, expected_status: int = 200) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=10) as response:
        if response.status != expected_status:
            raise RuntimeError(f"unexpected_status: {response.status}")
        return json.loads(response.read().decode("utf-8"))


def wait_for_health(port: int) -> None:
    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            if request_json(f"http://127.0.0.1:{port}/api/health")["status"] == "ok":
                return
        except Exception:
            time.sleep(0.1)
    raise RuntimeError("gateway did not start")


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


if __name__ == "__main__":
    main()
