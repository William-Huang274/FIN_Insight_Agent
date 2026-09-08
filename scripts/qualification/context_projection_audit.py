"""Replay saved requests through native context edits without any model call.

Input is explicitly selected private audit evidence. Output contains counts and
invariant checks only; no source text, prompts or provider reasoning is exported.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path

from langchain.agents.middleware import ClearToolUsesEdit
from langchain_core.messages import AIMessage, ToolMessage, messages_from_dict
from langchain_core.messages.utils import count_tokens_approximately
from sec_agent.agent_runtime.model_context import REREADABLE_TOOLS, project_tool_history


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-audit", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--trigger-tokens", type=int, default=50000)
    parser.add_argument("--keep", type=int, default=6)
    args = parser.parse_args()
    if args.trigger_tokens < 1000 or args.keep < 1:
        raise ValueError("invalid_projection_qualification_parameters")
    if args.output.exists():
        raise ValueError("preserve_previous_attempt")
    rows = []
    for line in args.private_audit.open(encoding="utf-8"):
        record = json.loads(line)
        if record.get("event") != "request" or not record.get("messages"):
            continue
        messages = messages_from_dict([{"type": m["type"], "data": m} for m in record["messages"]])
        original = deepcopy(messages)
        names = {c["id"]: c["name"] for m in messages if isinstance(m, AIMessage) for c in m.tool_calls}
        protected = {m.name or names.get(m.tool_call_id) for m in messages if isinstance(m, ToolMessage) and m.status == "error"}
        known = set(names.values()) | {m.name for m in messages if isinstance(m, ToolMessage)}
        old = deepcopy(messages)
        ClearToolUsesEdit(trigger=50000, keep=6, clear_tool_inputs=False,
            exclude_tools=tuple(n for n in known if n and (n not in REREADABLE_TOOLS or n in protected)),
            placeholder="[Older read result omitted from this request; the host retains the original. Repeat the same read tool and arguments when its source context is needed.]").apply(old, count_tokens=count_tokens_approximately)
        new = project_tool_history(messages, trigger_tokens=args.trigger_tokens, keep=args.keep)
        assert messages == original
        assert [m for m in new if isinstance(m, AIMessage)] == [m for m in original if isinstance(m, AIMessage)]
        assert all(new[i] == m for i, m in enumerate(original) if isinstance(m, ToolMessage) and m.status == "error")
        def chars(ms):
            return len(json.dumps([m.model_dump(mode="json", exclude={"artifact"}) for m in ms], ensure_ascii=False))
        rows.append({"call_id": record["call_id"], "actor": record["actor"], "original_characters": chars(original),
                     "old_projection_characters": chars(old), "new_projection_characters": chars(new)})
    result = {"qualification": "offline_projection_only_not_paid_savings_or_answer_accuracy", "model_calls": 0,
              "candidate_trigger_tokens": args.trigger_tokens, "candidate_keep": args.keep,
              "saved_requests": len(rows), "originals_and_errors_and_tool_calls_preserved": True, "requests": rows}
    for field in ("original_characters", "old_projection_characters", "new_projection_characters"):
        result[field] = sum(r[field] for r in rows)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k != "requests"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
