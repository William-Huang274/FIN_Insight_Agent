"""Summarize public native-run evidence without reading private model payloads."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from apps.workbench.backend.api.v1.report_sessions import public_run_usage, public_cost_estimate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--audit-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("preserve_existing_attempt_metrics")
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8-sig"))
    results = []
    for run in snapshot["runs"]:
        events, usage = public_run_usage(args.audit_root, snapshot["thread_id"], run["run_id"])
        actors = defaultdict(list)
        for event in events:
            if event.get("kind") == "model":
                actors[event.get("actor", "unknown")].append(event)
        by_actor = {}
        for actor, rows in actors.items():
            outcomes = {e["call_id"]: e for e in rows if e.get("event") == "outcome"}
            by_actor[actor] = {"recorded_requests": len({e["call_id"] for e in rows}),
                "reported_tokens": sum(e.get("total_tokens") or 0 for e in outcomes.values()),
                "peak_input_tokens": max((e.get("input_tokens") or 0 for e in outcomes.values()), default=0),
                "outcome_statuses": dict(Counter(e.get("status") for e in outcomes.values())),
                "cost": public_cost_estimate(rows)}
        results.append({"run_id": run["run_id"], "status": run["status"], "elapsed_ms": run.get("elapsed_ms"),
            "usage": usage, "cost": public_cost_estimate(events), "actors": by_actor,
            "tool_failures": dict(Counter(e.get("tool") for e in events if e.get("kind") == "tool" and e.get("event") == "outcome" and e.get("status") != "success")),
            "tasks": [e for e in events if e.get("kind") == "task"]})
    result = {"thread_id": snapshot["thread_id"], "title": snapshot.get("title"),
        "phase": snapshot.get("phase"), "report_digest": snapshot.get("report_digest"),
        "report_version": snapshot.get("report_version"), "report_charts": len(snapshot.get("report", {}).get("charts", [])),
        "notice": "Execution metrics are not research correctness or human acceptance. Unknown usage remains unknown.", "runs": results}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "runs": len(results), "model_calls": 0}))


if __name__ == "__main__":
    main()
