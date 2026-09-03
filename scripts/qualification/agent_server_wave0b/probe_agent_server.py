from __future__ import annotations

import argparse
import hashlib
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx


SCHEMA_VERSION = "fin_agent_server_wave0b_zero_model_probe_v1_0"
GRAPH_IDS = {
    "counter": "wave0b_counter",
    "approval": "wave0b_approval",
    "slow": "wave0b_slow",
    "parallel": "wave0b_parallel",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def require_qualification_root(path: Path) -> Path:
    resolved = path.resolve()
    expected = Path(
        r"Z:\FIN_Insight_Agent_qualification\20260903_agent_server_wave0b_v1"
    ).resolve()
    if resolved != expected and expected not in resolved.parents:
        raise ValueError(f"output path must stay below {expected}")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


class Recorder:
    def __init__(self, client: httpx.Client) -> None:
        self.client = client
        self.exchanges: list[dict[str, Any]] = []

    def request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        expected: set[int] | None = None,
        headers: dict[str, str] | None = None,
        record_body: bool = True,
    ) -> httpx.Response:
        started = time.perf_counter()
        response = self.client.request(method, path, json=payload, headers=headers)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        body: Any = None
        if record_body:
            try:
                body = response.json()
            except ValueError:
                body = response.text
        self.exchanges.append(
            {
                "method": method,
                "path": path,
                "request": payload,
                "status_code": response.status_code,
                "response": body,
                "response_bytes": len(response.content),
                "response_sha256": hashlib.sha256(response.content).hexdigest(),
                "response_content_type": response.headers.get("content-type"),
                "elapsed_ms": elapsed_ms,
            }
        )
        allowed = expected or {200}
        if response.status_code not in allowed:
            raise RuntimeError(
                f"{method} {path} returned {response.status_code}, expected {sorted(allowed)}"
            )
        return response


def poll_run_status(
    recorder: Recorder,
    thread_id: str,
    run_id: str,
    wanted: set[str],
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    latest: dict[str, Any] = {}
    while time.monotonic() < deadline:
        latest = recorder.request(
            "GET", f"/threads/{thread_id}/runs/{run_id}"
        ).json()
        if latest.get("status") in wanted:
            return latest
        time.sleep(0.1)
    raise TimeoutError(
        f"run {run_id} did not reach {sorted(wanted)}; latest={latest.get('status')}"
    )


def summarize_sse(payload: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for block in payload.replace("\r\n", "\n").split("\n\n"):
        if not block.strip():
            continue
        fields: dict[str, str] = {}
        data_lines: list[str] = []
        for line in block.splitlines():
            if line.startswith("data:"):
                data_lines.append(line.removeprefix("data:").strip())
            elif ":" in line:
                key, value = line.split(":", 1)
                fields[key.strip()] = value.strip()
        data = "\n".join(data_lines)
        events.append(
            {
                "id": fields.get("id"),
                "event": fields.get("event"),
                "data_bytes": len(data.encode("utf-8")),
                "data_sha256": hashlib.sha256(data.encode("utf-8")).hexdigest(),
            }
        )
    return events


def execution_windows_overlap(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return max(float(left["started"]), float(right["started"])) < min(
        float(left["finished"]), float(right["finished"])
    )


def run_probe(base_url: str, output_root: Path) -> dict[str, Any]:
    output_root = require_qualification_root(output_root)
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "started_at": utc_now(),
        "base_url": base_url,
        "zero_model": True,
        "provider_calls": 0,
        "network_sources": [],
        "python": platform.python_version(),
        "checks": {},
    }
    with httpx.Client(base_url=base_url, timeout=20.0) as client:
        recorder = Recorder(client)
        health = recorder.request("GET", "/ok").json()
        info = recorder.request("GET", "/info").json()
        openapi = recorder.request(
            "GET", "/openapi.json", record_body=False
        ).json()
        required_paths_present = {
            path: path in openapi.get("paths", {})
            for path in (
                "/threads",
                "/threads/{thread_id}/runs",
                "/threads/{thread_id}/runs/stream",
                "/threads/{thread_id}/runs/{run_id}/cancel",
                "/threads/{thread_id}/state",
            )
        }
        if not all(required_paths_present.values()):
            raise AssertionError(f"required API paths missing: {required_paths_present}")
        result["checks"]["server_surface"] = {
            "health": health,
            "info": info,
            "openapi_path_count": len(openapi.get("paths", {})),
            "required_paths_present": required_paths_present,
        }

        assistants = recorder.request(
            "POST", "/assistants/search", payload={"limit": 20, "offset": 0}
        ).json()
        graph_ids = {item["graph_id"] for item in assistants}
        missing_graphs = set(GRAPH_IDS.values()) - graph_ids
        if missing_graphs:
            raise RuntimeError(f"missing system assistants for graphs: {sorted(missing_graphs)}")
        result["checks"]["assistants"] = {
            "count": len(assistants),
            "graph_ids": sorted(graph_ids),
        }

        counter_thread = recorder.request(
            "POST",
            "/threads",
            payload={"metadata": {"fin_probe": "counter_continuity"}},
        ).json()
        counter_thread_id = counter_thread["thread_id"]
        counter_first = recorder.request(
            "POST",
            f"/threads/{counter_thread_id}/runs/wait",
            payload={
                "assistant_id": GRAPH_IDS["counter"],
                "input": {"case_id": "DELL", "delta": 2, "total": 0},
                "durability": "sync",
            },
        ).json()
        counter_second = recorder.request(
            "POST",
            f"/threads/{counter_thread_id}/runs/wait",
            payload={
                "assistant_id": GRAPH_IDS["counter"],
                "input": {"delta": 3},
                "durability": "sync",
            },
        ).json()
        counter_runs = recorder.request(
            "GET", f"/threads/{counter_thread_id}/runs"
        ).json()
        if counter_first.get("total") != 2 or counter_second.get("total") != 5:
            raise AssertionError(
                f"thread state continuity failed: first={counter_first}, second={counter_second}"
            )
        result["checks"]["thread_multi_run_continuity"] = {
            "thread_id": counter_thread_id,
            "run_ids": [run["run_id"] for run in counter_runs],
            "first_total": counter_first["total"],
            "second_total": counter_second["total"],
        }

        approval_thread = recorder.request(
            "POST",
            "/threads",
            payload={"metadata": {"fin_probe": "interrupt_resume"}},
        ).json()
        approval_thread_id = approval_thread["thread_id"]
        interrupted_output = recorder.request(
            "POST",
            f"/threads/{approval_thread_id}/runs/wait",
            payload={
                "assistant_id": GRAPH_IDS["approval"],
                "input": {
                    "case_id": "DELL",
                    "proposed_action": {
                        "action": "publish_candidate",
                        "digest": "sha256:wave0b-fixture",
                    },
                },
                "durability": "sync",
            },
        ).json()
        interrupted_state = recorder.request(
            "GET", f"/threads/{approval_thread_id}/state"
        ).json()
        resumed_output = recorder.request(
            "POST",
            f"/threads/{approval_thread_id}/runs/wait",
            payload={
                "assistant_id": GRAPH_IDS["approval"],
                "command": {
                    "resume": {
                        "approved": True,
                        "reviewer": "wave0b-human-fixture",
                    }
                },
                "durability": "sync",
            },
        ).json()
        approval_runs = recorder.request(
            "GET", f"/threads/{approval_thread_id}/runs"
        ).json()
        if not interrupted_state.get("interrupts"):
            raise AssertionError("server did not expose the graph interrupt in thread state")
        if resumed_output.get("result", {}).get("disposition") != "execute_allowed":
            raise AssertionError(f"resume did not reach expected result: {resumed_output}")
        result["checks"]["interrupt_resume"] = {
            "thread_id": approval_thread_id,
            "run_ids": [run["run_id"] for run in approval_runs],
            "interrupted_output": interrupted_output,
            "interrupt_count": len(interrupted_state.get("interrupts", [])),
            "resumed_result": resumed_output.get("result"),
        }

        stream_thread = recorder.request(
            "POST",
            "/threads",
            payload={"metadata": {"fin_probe": "sse"}},
        ).json()
        stream_thread_id = stream_thread["thread_id"]
        stream_response = recorder.request(
            "POST",
            f"/threads/{stream_thread_id}/runs/stream",
            payload={
                "assistant_id": GRAPH_IDS["counter"],
                "input": {"case_id": "DELL", "delta": 1, "total": 0},
                "stream_mode": ["updates", "values"],
                "stream_resumable": True,
                "durability": "sync",
            },
            record_body=False,
        )
        stream_text = stream_response.text
        stream_runs = recorder.request(
            "GET", f"/threads/{stream_thread_id}/runs"
        ).json()
        stream_run_id = stream_runs[0]["run_id"]
        replay_response = recorder.request(
            "GET",
            f"/threads/{stream_thread_id}/runs/{stream_run_id}/stream",
            headers={"Last-Event-ID": "-1"},
            record_body=False,
        )
        live_events = summarize_sse(stream_text)
        replay_events = summarize_sse(replay_response.text)
        live_ids = [event["id"] for event in live_events]
        replay_ids = [event["id"] for event in replay_events]
        if not live_events or any(event_id is None for event_id in live_ids):
            raise AssertionError(f"live SSE events did not have stable IDs: {live_events}")
        if len(set(live_ids)) != len(live_ids) or live_ids != sorted(live_ids):
            raise AssertionError(f"live SSE IDs were not unique and ordered: {live_ids}")
        if replay_events != live_events:
            raise AssertionError(
                f"SSE replay did not reproduce the persisted stream: {replay_events}"
            )
        result["checks"]["sse_and_replay"] = {
            "thread_id": stream_thread_id,
            "run_id": stream_run_id,
            "live_content_type": stream_response.headers.get("content-type"),
            "live_events": live_events,
            "replay_content_type": replay_response.headers.get("content-type"),
            "replay_events": replay_events,
        }

        parallel_thread = recorder.request(
            "POST",
            "/threads",
            payload={"metadata": {"fin_probe": "in_run_parallel"}},
        ).json()
        parallel_thread_id = parallel_thread["thread_id"]
        parallel_output = recorder.request(
            "POST",
            f"/threads/{parallel_thread_id}/runs/wait",
            payload={
                "assistant_id": GRAPH_IDS["parallel"],
                "input": {"case_id": "DELL", "branch_duration_seconds": 1.5},
                "durability": "sync",
            },
        ).json()
        branch_windows = parallel_output.get("branch_windows", [])
        if len(branch_windows) != 2 or not execution_windows_overlap(
            branch_windows[0], branch_windows[1]
        ):
            raise AssertionError(
                f"parallel branches did not overlap in one server run: {branch_windows}"
            )
        result["checks"]["in_run_branch_parallelism"] = {
            "thread_id": parallel_thread_id,
            "branch_windows": branch_windows,
            "overlap_observed": True,
        }

        slow_thread = recorder.request(
            "POST",
            "/threads",
            payload={"metadata": {"fin_probe": "cancel"}},
        ).json()
        slow_thread_id = slow_thread["thread_id"]
        slow_run = recorder.request(
            "POST",
            f"/threads/{slow_thread_id}/runs",
            payload={
                "assistant_id": GRAPH_IDS["slow"],
                "input": {"case_id": "DELL", "duration_seconds": 8.0},
                "durability": "sync",
                "multitask_strategy": "reject",
            },
        ).json()
        slow_run_id = slow_run["run_id"]
        running = poll_run_status(
            recorder, slow_thread_id, slow_run_id, {"running", "success"}
        )
        if running["status"] == "success":
            raise AssertionError("slow fixture completed before cancellation could be tested")
        rejected_concurrent = recorder.request(
            "POST",
            f"/threads/{slow_thread_id}/runs",
            payload={
                "assistant_id": GRAPH_IDS["counter"],
                "input": {"case_id": "DELL", "delta": 1},
                "multitask_strategy": "reject",
            },
            expected={409},
        )
        recorder.request(
            "POST",
            f"/threads/{slow_thread_id}/runs/{slow_run_id}/cancel?wait=true&action=interrupt",
            expected={200, 204},
        )
        cancelled = poll_run_status(
            recorder,
            slow_thread_id,
            slow_run_id,
            {"interrupted", "error", "success"},
        )
        if cancelled["status"] != "interrupted":
            raise AssertionError(f"cancel did not produce interrupted status: {cancelled}")
        result["checks"]["cancel"] = {
            "thread_id": slow_thread_id,
            "run_id": slow_run_id,
            "status_before_cancel": running["status"],
            "status_after_cancel": cancelled["status"],
            "same_thread_concurrent_reject_status": rejected_concurrent.status_code,
        }

        first_parallel_thread = recorder.request(
            "POST",
            "/threads",
            payload={"metadata": {"fin_probe": "cross_thread_parallel_a"}},
        ).json()["thread_id"]
        second_parallel_thread = recorder.request(
            "POST",
            "/threads",
            payload={"metadata": {"fin_probe": "cross_thread_parallel_b"}},
        ).json()["thread_id"]
        first_parallel_run = recorder.request(
            "POST",
            f"/threads/{first_parallel_thread}/runs",
            payload={
                "assistant_id": GRAPH_IDS["slow"],
                "input": {"case_id": "DELL-A", "duration_seconds": 2.0},
                "durability": "sync",
            },
        ).json()["run_id"]
        second_parallel_run = recorder.request(
            "POST",
            f"/threads/{second_parallel_thread}/runs",
            payload={
                "assistant_id": GRAPH_IDS["slow"],
                "input": {"case_id": "DELL-B", "duration_seconds": 2.0},
                "durability": "sync",
            },
        ).json()["run_id"]
        poll_run_status(
            recorder,
            first_parallel_thread,
            first_parallel_run,
            {"success"},
            timeout_seconds=8.0,
        )
        poll_run_status(
            recorder,
            second_parallel_thread,
            second_parallel_run,
            {"success"},
            timeout_seconds=8.0,
        )
        first_parallel_state = recorder.request(
            "GET", f"/threads/{first_parallel_thread}/state"
        ).json()
        second_parallel_state = recorder.request(
            "GET", f"/threads/{second_parallel_thread}/state"
        ).json()
        first_window = first_parallel_state["values"]["execution_window"]
        second_window = second_parallel_state["values"]["execution_window"]
        if not execution_windows_overlap(first_window, second_window):
            raise AssertionError(
                "different server threads did not execute concurrently; "
                f"first={first_window}, second={second_window}"
            )
        result["checks"]["cross_thread_parallelism"] = {
            "first": {
                "thread_id": first_parallel_thread,
                "run_id": first_parallel_run,
                "execution_window": first_window,
            },
            "second": {
                "thread_id": second_parallel_thread,
                "run_id": second_parallel_run,
                "execution_window": second_window,
            },
            "overlap_observed": True,
        }

        invalid_assistant = recorder.request(
            "POST",
            f"/threads/{counter_thread_id}/runs",
            payload={
                "assistant_id": "00000000-0000-0000-0000-000000000000",
                "input": {},
            },
            expected={404},
        )
        malformed_thread = recorder.request(
            "GET", "/threads/not-a-uuid/state", expected={422}
        )
        result["checks"]["invalid_input_fail_closed"] = {
            "unknown_assistant_status": invalid_assistant.status_code,
            "malformed_thread_status": malformed_thread.status_code,
        }

        result["http_exchanges"] = recorder.exchanges

    result["finished_at"] = utc_now()
    result["passed"] = True
    output_path = output_root / "agent_server_zero_model_probe.json"
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:2024")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(
            r"Z:\FIN_Insight_Agent_qualification\20260903_agent_server_wave0b_v1\receipts"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_probe(args.base_url, args.output_root)
    print(
        json.dumps(
            {
                "schema_version": result["schema_version"],
                "passed": result["passed"],
                "check_names": sorted(result["checks"]),
                "exchange_count": len(result["http_exchanges"]),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
