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
from uuid import uuid4


REPO_ROOT = Path(__file__).resolve().parents[2]
MYSQL_DRIVER_URL = "https://repo1.maven.org/maven2/com/mysql/mysql-connector-j/8.4.0/mysql-connector-j-8.4.0.jar"


def main() -> None:
    args = parse_args()
    if not shutil.which("docker"):
        raise SystemExit("docker is required for backend smoke")
    work_root = Path(args.work_root).resolve() if args.work_root else Path(tempfile.mkdtemp(prefix="finsight_bridge_docker_smoke_"))
    work_root.mkdir(parents=True, exist_ok=True)
    redis_name = f"finsight-redis-{uuid4().hex[:10]}"
    mysql_name = f"finsight-mysql-{uuid4().hex[:10]}"
    redis_port = args.redis_port or free_port()
    mysql_port = args.mysql_port or free_port()
    mysql_password = f"finsight_{uuid4().hex[:16]}"
    driver_jar = args.jdbc_driver_jar or (work_root / "mysql-connector-j-8.4.0.jar")
    results: list[dict[str, object]] = []
    try:
        docker_run_redis(redis_name, redis_port)
        wait_for_redis(redis_port)
        results.append(
            run_bridge_smoke(
                [
                    "--store-mode",
                    "file",
                    "--queue-mode",
                    "redis",
                    "--redis-port",
                    str(redis_port),
                    "--run-id",
                    "docker_file_redis_smoke",
                    "--work-root",
                    str(work_root / "file_redis"),
                ],
                env=os.environ.copy(),
            )
        )

        download_if_missing(MYSQL_DRIVER_URL, driver_jar)
        docker_run_mysql(mysql_name, mysql_port, mysql_password)
        wait_for_mysql_ready(mysql_name, mysql_port, mysql_password)
        env = os.environ.copy()
        env["FINSIGHT_JDBC_PASSWORD"] = mysql_password
        results.append(
            run_bridge_smoke(
                [
                    "--store-mode",
                    "jdbc",
                    "--queue-mode",
                    "redis",
                    "--redis-port",
                    str(redis_port),
                    "--jdbc-url",
                    f"jdbc:mysql://127.0.0.1:{mysql_port}/finsight?useSSL=false&allowPublicKeyRetrieval=true",
                    "--jdbc-user",
                    "root",
                    "--jdbc-driver-jar",
                    str(driver_jar),
                    "--run-id",
                    "docker_jdbc_redis_smoke",
                    "--work-root",
                    str(work_root / "jdbc_redis"),
                ],
                env=env,
            )
        )
        print(json.dumps({"status": "pass", "work_root": str(work_root), "results": results}, ensure_ascii=False, indent=2))
    finally:
        docker_rm_force(redis_name)
        docker_rm_force(mysql_name)


def run_bridge_smoke(extra_args: list[str], *, env: dict[str, str]) -> dict[str, object]:
    command = [sys.executable, str(REPO_ROOT / "scripts" / "runtime_bridge" / "smoke_java_python_bridge.py"), *extra_args]
    completed = subprocess.run(command, cwd=REPO_ROOT, env=env, text=True, capture_output=True)
    if completed.returncode != 0:
        raise RuntimeError(f"bridge smoke failed with code {completed.returncode}: {completed.stdout[-2000:]} {completed.stderr[-2000:]}")
    payload = parse_last_json_object(completed.stdout)
    return {
        "command": [arg if "password" not in arg.lower() else "<redacted>" for arg in command],
        "task_status": payload.get("task", {}).get("status"),
        "store_mode": payload.get("store_mode"),
        "queue_mode": payload.get("queue_mode"),
        "event_count": payload.get("event_count"),
    }


def docker_run_redis(name: str, port: int) -> None:
    subprocess.run(
        ["docker", "run", "-d", "--rm", "--name", name, "-p", f"127.0.0.1:{port}:6379", "redis:7-alpine"],
        check=True,
        stdout=subprocess.DEVNULL,
    )


def docker_run_mysql(name: str, port: int, password: str) -> None:
    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--rm",
            "--name",
            name,
            "-e",
            f"MYSQL_ROOT_PASSWORD={password}",
            "-e",
            "MYSQL_DATABASE=finsight",
            "-p",
            f"127.0.0.1:{port}:3306",
            "mysql:8.4",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
    )


def docker_rm_force(name: str) -> None:
    subprocess.run(["docker", "rm", "-f", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def wait_for_redis(port: int) -> None:
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=2) as sock:
                sock.sendall(b"*1\r\n$4\r\nPING\r\n")
                if sock.recv(16).startswith(b"+PONG"):
                    return
        except OSError:
            time.sleep(0.5)
    raise RuntimeError("redis did not become ready")


def wait_for_mysql_ready(container_name: str, port: int, password: str) -> None:
    deadline = time.time() + 120
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=2):
                completed = subprocess.run(
                    ["docker", "exec", "-e", f"MYSQL_PWD={password}", container_name, "mysqladmin", "ping", "-uroot", "--silent"],
                    text=True,
                    capture_output=True,
                )
                if completed.returncode == 0:
                    return
        except OSError:
            pass
        time.sleep(1.0)
    raise RuntimeError("mysql did not become ready")


def download_if_missing(url: str, path: Path) -> None:
    if path.exists() and path.stat().st_size > 1024:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, path)


def parse_last_json_object(text: str) -> dict[str, object]:
    decoder = json.JSONDecoder()
    last: dict[str, object] | None = None
    index = 0
    while index < len(text):
        start = text.find("{", index)
        if start < 0:
            break
        try:
            value, end = decoder.raw_decode(text[start:])
        except json.JSONDecodeError:
            index = start + 1
            continue
        if isinstance(value, dict):
            last = value
        index = start + end
    if last is None:
        raise RuntimeError("no JSON object found in bridge smoke output")
    return last


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Docker-backed Redis/JDBC parity smokes for the research bridge.")
    parser.add_argument("--work-root", type=Path, default=None)
    parser.add_argument("--redis-port", type=int, default=0)
    parser.add_argument("--mysql-port", type=int, default=0)
    parser.add_argument("--jdbc-driver-jar", type=Path, default=None)
    return parser.parse_args()


if __name__ == "__main__":
    main()
