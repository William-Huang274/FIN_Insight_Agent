"""One-time, explicit recovery of submitted prose from a legacy run audit.

Original audit/checkpoint bytes are untouched. A separate derived public file
contains only FIN submission prose; requests and provider reasoning are excluded.
"""
import argparse
import hashlib
import json
from pathlib import Path

from sec_agent.agent_runtime.public_research_output import submitted_prose


def recover(directory):
    root = Path(directory).resolve()
    source = root / "model-context-reasoning.private.jsonl"
    public = [json.loads(line) for line in (root / "model-call-events.jsonl").read_text(encoding="utf-8").splitlines()]
    timestamps = {e["call_id"]: e.get("recorded_at") for e in public if e.get("call_id")}
    events, seen = [], set()
    for line in source.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        raw = row.get("raw_response")
        if not isinstance(raw, dict):
            continue
        for call in raw.get("tool_calls", []):
            prose = submitted_prose(call.get("name"), call.get("args"))
            if not prose or call.get("id") in seen:
                continue
            seen.add(call.get("id"))
            events.append({"kind": "stage", "actor": row.get("actor", "research"), "event": "output",
                "status": "recovered_candidate", "call_id": str(call.get("id")) + ":recovered",
                "objective": prose, "recorded_at": timestamps.get(row.get("call_id"))})
    payload = {"origin": "explicit_submission_projection_not_acceptance", "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "events": events}
    destination = root / "public-output-recovery.json"
    with destination.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
    return {"recovered_outputs": len(events), "path": str(destination)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_audit_directory")
    print(json.dumps(recover(parser.parse_args().run_audit_directory)))
