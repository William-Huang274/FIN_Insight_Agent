from __future__ import annotations

import argparse
import json
import shutil
import socket
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


TERMINAL_STATUSES = {"SUCCESS", "FAILED", "CANCELLED"}


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
    once: bool


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
        "schema_version": "finsight_python_research_worker_v0_1",
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
    if not files:
        return None
    source = files[0]
    target = inflight / source.name
    shutil.move(str(source), str(target))
    payload = json.loads(target.read_text(encoding="utf-8"))
    shutil.move(str(target), str(done / target.name))
    return payload


def _process_payload(payload: dict[str, Any], config: WorkerConfig) -> None:
    task_id = str(payload.get("task_id") or "").strip()
    callback_url = str(payload.get("callback_url") or "").strip()
    if not task_id:
        raise ValueError("task_id_required")
    if not callback_url:
        callback_url = f"{config.gateway_url.rstrip('/')}/api/research/tasks/{task_id}/worker-events"
    try:
        _post_update(callback_url, {"status": "RUNNING", "progress": 20}, token=config.worker_token)
        result = _run_deterministic_research(payload)
        _post_update(
            callback_url,
            {
                "status": "SUCCESS",
                "progress": 100,
                "memo": result["memo"],
                "evidence": result["evidence"],
                "error_message": "",
            },
            token=config.worker_token,
        )
    except Exception as exc:  # pragma: no cover - exercised by integration failures
        _post_update(
            callback_url,
            {"status": "FAILED", "progress": 100, "error_message": f"{type(exc).__name__}: {exc}"},
            token=config.worker_token,
        )
        raise


def _run_deterministic_research(payload: dict[str, Any]) -> dict[str, Any]:
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
    return {"memo": memo, "evidence": evidence}


def _post_update(callback_url: str, payload: dict[str, Any], *, token: str = "") -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
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
    parser.add_argument("--once", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
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
            once=args.once,
        )
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
