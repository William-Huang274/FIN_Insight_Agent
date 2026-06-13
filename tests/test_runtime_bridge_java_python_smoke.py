from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
JAVA_SRC = REPO_ROOT / "apps" / "research_gateway" / "java" / "src"


def test_java_gateway_to_python_worker_file_queue_smoke(tmp_path: Path) -> None:
    javac = shutil.which("javac")
    java = shutil.which("java")
    if not javac or not java:
        pytest.skip("JDK is required for Java gateway smoke")

    classes_dir = tmp_path / "classes"
    classes_dir.mkdir()
    sources = sorted(str(path) for path in JAVA_SRC.rglob("*.java"))
    subprocess.run([javac, "-encoding", "UTF-8", "-d", str(classes_dir), *sources], cwd=REPO_ROOT, check=True)

    port = _free_port()
    state_dir = tmp_path / "gateway_state"
    queue_dir = tmp_path / "gateway_queue"
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
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
    )
    try:
        _wait_for_health(port)
        task = _request_json(
            f"http://127.0.0.1:{port}/api/research/tasks",
            method="POST",
            payload={"query": "Check NVDA runtime bridge", "user_id": "pytest_user", "mode": "local_smoke"},
            expected_status=202,
        )
        assert task["status"] == "PENDING"
        assert (queue_dir / "pending").exists()

        worker = subprocess.run(
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
            text=True,
            capture_output=True,
            check=True,
        )
        assert '"processed": 1' in worker.stdout

        completed = _request_json(f"http://127.0.0.1:{port}/api/research/tasks/{task['task_id']}")
        assert completed["status"] == "SUCCESS"
        assert completed["progress"] == 100
        assert "Runtime bridge smoke passed" in completed["memo"]
        assert completed["evidence"][0]["source_family"] == "runtime_bridge_smoke"
        assert (state_dir / "tasks" / f"{task['task_id']}.json").exists()
        events = _request_json(f"http://127.0.0.1:{port}/api/research/tasks/{task['task_id']}/events?limit=50")
        event_messages = [event["message"] for event in events["events"]]
        assert any("task accepted and queued" in message for message in event_messages)
        assert any("task dequeued by Python worker" in message for message in event_messages)
        assert any("status=SUCCESS progress=100" in message for message in event_messages)

        cancellable = _request_json(
            f"http://127.0.0.1:{port}/api/research/tasks",
            method="POST",
            payload={"query": "Check cancellation surface", "user_id": "pytest_user", "mode": "local_smoke"},
            expected_status=202,
        )
        cancelled = _request_json(
            f"http://127.0.0.1:{port}/api/research/tasks/{cancellable['task_id']}/cancel",
            method="POST",
            payload={},
            expected_status=202,
        )
        assert cancelled["status"] == "CANCEL_REQUESTED"
        cancel_events = _request_json(f"http://127.0.0.1:{port}/api/research/tasks/{cancellable['task_id']}/events")
        assert any(event["message"] == "cancel requested" for event in cancel_events["events"])
    finally:
        gateway.terminate()
        try:
            gateway.wait(timeout=10)
        except subprocess.TimeoutExpired:
            gateway.kill()
            gateway.wait(timeout=10)


def _request_json(url: str, *, method: str = "GET", payload: dict | None = None, expected_status: int = 200) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=10) as response:
        assert response.status == expected_status
        return json.loads(response.read().decode("utf-8"))


def _wait_for_health(port: int) -> None:
    deadline = time.time() + 10
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            payload = _request_json(f"http://127.0.0.1:{port}/api/health")
            if payload["status"] == "ok":
                return
        except Exception as exc:  # pragma: no cover - polling path
            last_error = exc
            time.sleep(0.1)
    raise AssertionError(f"gateway did not start: {last_error}")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
