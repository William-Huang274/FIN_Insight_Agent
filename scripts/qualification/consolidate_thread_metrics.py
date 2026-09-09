"""Read-only batch projection of existing model audits; never runs a model.

The manifest lists thread IDs. Each thread receives a separate receipt, so
failed attempts remain visible and missing audits never become zero cost.
No prompts, source text, credentials or private reasoning enter the output.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from uuid import UUID

from scripts.qualification.dell_q1_specialist_paid_shadow.audit_token_cost import audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--audit-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    inventory = json.loads(args.inventory.read_text(encoding="utf-8-sig"))
    ids = [str(UUID(item["thread_id"])) for item in inventory]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate thread IDs would double count costs")
    args.output.mkdir(exist_ok=False, parents=True)
    rows = []
    for item, tid in zip(inventory, ids):
        root = args.audit_root / tid
        files = list(root.glob("*/model-call-events.jsonl"))
        if not files:
            rows.append({"thread_id": tid, "audit_state": "missing", "totals": None})
            continue
        result = audit(root)
        calls = result["calls"]
        row = {"thread_id": tid, "audit_state": "available", "totals": result["totals"],
               "not_sent_outcomes": result["not_sent_outcomes"],
               "runs": result["groups"]["attempt"], "phases": result["groups"]["phase"],
               "max_reported_input_tokens": max((c["input_tokens"] for c in calls if c["input_tokens"] is not None), default=None),
               "unknown_usage_requests": len(calls) - result["totals"]["total_tokens_known_requests"],
               "unknown_cost_requests": len(calls) - result["totals"]["cost_known_requests"]}
        (args.output / f"{tid}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        rows.append(row)
        print(json.dumps({"thread_id": tid, "calls": len(calls), "tokens": result["totals"]["total_tokens"]}), flush=True)
    (args.output / "index.json").write_text(json.dumps({
        "cost_is_invoice": False, "case_count_is_not_thread_count": True,
        "note": "Thread totals include their follow-ups and failed attempts. Do not sum these again with run totals. Content quality and wall time require separate evidence.",
        "threads": rows}, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
