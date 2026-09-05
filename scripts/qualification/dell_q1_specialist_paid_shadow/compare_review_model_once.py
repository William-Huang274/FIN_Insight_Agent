"""One paid next-action comparison on archived source/workpaper input, no tools executed.

Diagnostic only: this is not an Agent Server research run or a passed full case.
Uses the existing ChatDeepSeek SDK and native review schemas, not a new harness.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from time import perf_counter

from langchain_core.messages import messages_from_dict
from langchain_core.tracers.langchain import wait_for_all_tracers
from langsmith import tracing_context
from pydantic import SecretStr

from sec_agent.agent_runtime.deepseek_structured_agents import (
    ReasoningPreservingChatDeepSeek, _NATIVE_REVIEW_TOOLS, _provider_function_schema, _usage_audit_fields,
)
from scripts.qualification.dell_q1_specialist_paid_shadow.run_once import _dotenv, _write_new


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-audit", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model", choices=("deepseek-v4-pro", "deepseek-v4-flash"), required=True)
    parser.add_argument("--effort", choices=("low", "high"), required=True)
    args = parser.parse_args()
    # Exclusive directory is just ordinary file safety, not another execution protocol.
    args.output_dir.mkdir(exist_ok=False)
    with args.source_audit.open(encoding="utf-8") as stream:
        source = next(json.loads(line) for line in stream if line.strip())
    if not source["actor"].startswith("verifier:") or [m["type"] for m in source["messages"]] != ["system", "human"]:
        raise ValueError("comparison_requires_first_verifier_turn_without_private_reasoning_history")
    secrets = _dotenv()
    for name, value in secrets.items():
        if name.startswith("LANGSMITH_") or name in {"LANGCHAIN_API_KEY", "LANGCHAIN_TRACING_V2", "LANGCHAIN_PROJECT"}:
            os.environ[name] = value
    project = secrets.get("LANGSMITH_PROJECT", "fin-dell-reference-vertical")
    manifest = {"purpose": "known-input Q1 review next-action model/effort diagnostic; no tool execution or research admission",
        "source_call_id": source["call_id"], "source_actor": source["actor"], "model": args.model,
        "reasoning_effort": args.effort, "thinking": "enabled", "max_output_tokens": 32000,
        "input_characters": sum(len(m["content"]) for m in source["messages"]),
        "timeout_seconds": 480, "transport_attempts_allowed": 1, "retry": False,
        "TokenBudgetBasis": "docs/worklog/fin_0_1_3_s3/190_dell_cost_external_and_interactive_delivery.md",
        "langsmith_project": project, "recorded_at": datetime.now(timezone.utc).isoformat()}
    _write_new(args.output_dir / "request.json", manifest)
    model = ReasoningPreservingChatDeepSeek(model=args.model, reasoning_effort=args.effort,
        api_key=SecretStr(secrets["DEEPSEEK_API_KEY"]), base_url="https://api.deepseek.com",
        max_tokens=32000, timeout=480, max_retries=0, streaming=False, use_responses_api=False,
        extra_body={"thinking": {"type": "enabled"}})
    messages = messages_from_dict([{"type": m["type"], "data": m} for m in source["messages"]])
    runnable = model.bind_tools([_provider_function_schema(tool, strict=False) for tool in _NATIVE_REVIEW_TOOLS.values()],
                               tool_choice="auto", strict=False)
    started = perf_counter()
    raw = None
    try:
        with tracing_context(enabled=True, project_name=project):
            raw = runnable.invoke(messages, config={"run_name": args.output_dir.name,
                "tags": ["cost-model-comparison", "diagnostic-only", "no-tool-execution"]})
        _write_new(args.output_dir / "response.private.json", raw.model_dump(mode="json"))
        valid = not raw.invalid_tool_calls and bool(raw.tool_calls)
        for call in raw.tool_calls:
            if call["name"] not in _NATIVE_REVIEW_TOOLS:
                valid = False
            else:
                _NATIVE_REVIEW_TOOLS[call["name"]].model_validate_json(json.dumps(call["args"]))
        result = {"status": ("provider_output_truncated" if raw.response_metadata.get("finish_reason") == "length"
                             else "next_action_schema_valid" if valid else "next_action_invalid"),
                  "finish_reason": raw.response_metadata.get("finish_reason"),
                  "actions": [call["name"] for call in raw.tool_calls],
                  "full_task_passed": False, "elapsed_seconds": round(perf_counter() - started, 3),
                  **_usage_audit_fields(raw)}
    except Exception as exc:
        result = {"status": "failed", "error_type": type(exc).__name__, "http_status_code": getattr(exc, "status_code", None),
                  "full_task_passed": False, "elapsed_seconds": round(perf_counter() - started, 3),
                  **(_usage_audit_fields(raw) if raw is not None else {"usage_reported": False})}
    finally:
        wait_for_all_tracers()
    _write_new(args.output_dir / "outcome.json", result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
