from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any

from sec_agent.llm_gateway import chat_completion
from sec_agent.tool_harness import KNOWN_TICKERS, SecAgentToolHarness, ToolResult


SEC_AGENT_CONTROLLER_SYSTEM_PROMPT = """You are the controller for an SEC-primary investment memo agent.

Your job is to choose high-level tools. Do not directly answer memo, evidence,
coverage, source, resume, or reformat requests when a tool is available.

Routing rules:
- Use start_memo_analysis for a brand-new SEC-only memo request.
- Use revise_memo_scope when the user changes tickers, years, peer scope, or analysis scope.
- Use revise_memo_scope, not explain_evidence, when the user asks to focus/drill down on a subset of companies
  from the active memo or asks for a more specific comparison such as "NVDA and AMD 对比".
  In that case pass set_tickers with exactly the requested comparison companies and execute=true.
- Use get_session_state first when the user asks which prior memo/session is active or uses ambiguous references that require session resolution.
- Use explain_evidence only when the user asks where a claim, driver, metric, or evidence came from, or asks for proof/citation/source of an existing memo item.
- Use inspect_coverage when the user asks whether evidence is complete, whether there are gaps, or asks for current/latest/buy-sell topics that exceed the active SEC source boundary.
- Use reformat_answer for style, audience, bullet, or section-only transformations of an existing memo.
- Use resume_analysis when the user asks to continue an interrupted or partial analysis.

Constraints:
- Supported source policies are SEC_ONLY_10K and SEC_PRIMARY_MIXED_RECENT.
- Use the runtime default source policy when starting or revising memo analysis.
- Never call external news, market data, price, analyst consensus, or web tools.
- Keep session_id, user_id, tenant_id, and active_answer_id isolated to the runtime context.
- Prefer one tool call per turn unless a follow-up tool is clearly required after a tool result.
"""


EXECUTE_CAPABLE_TOOLS = {
    "start_memo_analysis",
    "revise_memo_scope",
    "reformat_answer",
    "resume_analysis",
}


@dataclass
class ControllerConfig:
    controller_backend: str = "deepseek"
    llm_backend: str = "deepseek"
    base_url: str = "https://api.deepseek.com"
    chat_completions_path: str = "/chat/completions"
    model: str = "deepseek-v4-pro"
    api_key_env: str = "DEEPSEEK_API_KEY"
    temperature: float = 0.0
    max_tokens: int = 1024
    timeout_s: int = 180
    max_steps: int = 3
    execute_tools: bool = False


class DeepSeekToolController:
    """OpenAI-compatible tool-call controller for the SEC agent harness."""

    def __init__(
        self,
        *,
        harness: SecAgentToolHarness | None = None,
        config: ControllerConfig | None = None,
    ) -> None:
        self.harness = harness or SecAgentToolHarness()
        self.config = config or ControllerConfig()
        self.tool_specs = self.harness.tool_specs()
        self._allowed_args = _tool_arg_allowlist(self.tool_specs)

    def run_turn(
        self,
        *,
        user_message: str,
        session_id: str = "",
        user_id: str = "",
        tenant_id: str = "",
        active_answer_id: str = "",
        runtime_context: dict[str, Any] | None = None,
        route_only: bool = False,
    ) -> dict[str, Any]:
        started = time.time()
        context = _compact_runtime_context(
            session_id=session_id,
            user_id=user_id,
            tenant_id=tenant_id,
            active_answer_id=active_answer_id,
            runtime_context=runtime_context or {},
        )
        messages = _initial_messages(user_message=user_message, runtime_context=context)
        trace: list[dict[str, Any]] = []
        all_tool_calls: list[dict[str, Any]] = []
        final_content = ""
        status = "completed"

        for step_index in range(max(int(self.config.max_steps), 1)):
            if self.config.controller_backend == "heuristic":
                llm_result = _heuristic_chat_completion(user_message=user_message, runtime_context=context)
            else:
                llm_result = chat_completion(
                    llm_backend=self.config.llm_backend,
                    base_url=self.config.base_url,
                    chat_completions_path=self.config.chat_completions_path,
                    model=self.config.model,
                    messages=messages,
                    tools=self.tool_specs,
                    tool_choice="auto",
                    parallel_tool_calls=False,
                    api_key_env=self.config.api_key_env,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                    timeout_s=self.config.timeout_s,
                    enable_thinking=False,
                    role="tool_controller",
                    profile="sec_agent_tool_controller_v0",
                    trace_tags={"session_id": context.get("session_id"), "route_only": route_only},
                )
            if llm_result.get("status") != "ok":
                status = str(llm_result.get("status") or "controller_error")
                fallback_call = _heuristic_tool_call(user_message=user_message, runtime_context=context)
                prepared_calls = [
                    self._prepare_tool_call(
                        fallback_call,
                        user_message=user_message,
                        runtime_context=context,
                        route_only=route_only,
                    )
                ]
                all_tool_calls.extend(prepared_calls)
                trace_step = {
                    "step": step_index + 1,
                    "llm_result": _compact_llm_result(llm_result),
                    "fallback_reason": status,
                    "tool_results": [],
                    "tool_calls": prepared_calls,
                }
                trace.append(trace_step)
                if route_only:
                    status = "routed_with_fallback"
                    final_content = ""
                    break
                for call in prepared_calls:
                    tool_result = self._dispatch_tool_call(call)
                    trace_step["tool_results"].append(tool_result.to_dict())
                final_content = _tool_result_summary(trace_step["tool_results"])
                break

            tool_calls = _normalize_tool_calls(llm_result)
            trace_step: dict[str, Any] = {
                "step": step_index + 1,
                "llm_result": _compact_llm_result(llm_result),
                "tool_results": [],
            }
            if not tool_calls:
                fallback_call = _heuristic_tool_call(user_message=user_message, runtime_context=context)
                prepared_calls = [
                    self._prepare_tool_call(
                        fallback_call,
                        user_message=user_message,
                        runtime_context=context,
                        route_only=route_only,
                    )
                ]
                all_tool_calls.extend(prepared_calls)
                trace_step["fallback_reason"] = "no_tool_calls"
                trace_step["tool_calls"] = prepared_calls
                trace.append(trace_step)
                if route_only:
                    status = "routed_with_fallback"
                    final_content = ""
                    break
                for call in prepared_calls:
                    tool_result = self._dispatch_tool_call(call)
                    trace_step["tool_results"].append(tool_result.to_dict())
                final_content = _tool_result_summary(trace_step["tool_results"])
                break

            prepared_calls = [
                self._prepare_tool_call(
                    call,
                    user_message=user_message,
                    runtime_context=context,
                    route_only=route_only,
                )
                for call in tool_calls
            ]
            all_tool_calls.extend(prepared_calls)
            trace_step["tool_calls"] = prepared_calls
            trace.append(trace_step)

            if route_only:
                status = "routed"
                final_content = ""
                break

            assistant_message = _assistant_message_from_result(llm_result, prepared_calls)
            messages.append(assistant_message)
            for call in prepared_calls:
                tool_result = self._dispatch_tool_call(call)
                trace_step["tool_results"].append(tool_result.to_dict())
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "name": call["name"],
                        "content": json.dumps(tool_result.to_dict(), ensure_ascii=False),
                    }
                )

            final_content = _tool_result_summary(trace_step["tool_results"])
            if self.config.controller_backend == "heuristic":
                break
        else:
            status = "max_steps_exceeded"

        return {
            "schema_version": "sec_agent_tool_controller_result_v0.1",
            "status": status,
            "controller_backend": self.config.controller_backend,
            "route_only": bool(route_only),
            "execute_tools": bool(self.config.execute_tools),
            "runtime_context": context,
            "final_content": final_content,
            "tool_calls": all_tool_calls,
            "trace": trace,
            "latency_ms": int((time.time() - started) * 1000),
        }

    def _prepare_tool_call(
        self,
        call: dict[str, Any],
        *,
        user_message: str,
        runtime_context: dict[str, Any],
        route_only: bool,
    ) -> dict[str, Any]:
        name = _guarded_tool_name(str(call.get("name") or ""), user_message=user_message, runtime_context=runtime_context)
        args = dict(call.get("arguments") or {})
        if name in self._allowed_args:
            args = {key: value for key, value in args.items() if key in self._allowed_args[name]}
        args = _fill_runtime_defaults(name, args, runtime_context)
        args = _canonicalize_tool_arguments(name, args, user_message=user_message)
        if name in EXECUTE_CAPABLE_TOOLS and (route_only or not self.config.execute_tools):
            args["execute"] = False
        return {
            "id": str(call.get("id") or f"call_{len(args)}"),
            "type": "function",
            "name": name,
            "arguments": args,
            "function": {
                "name": name,
                "arguments": json.dumps(args, ensure_ascii=False),
            },
        }

    def _dispatch_tool_call(self, call: dict[str, Any]) -> ToolResult:
        try:
            return self.harness.dispatch(str(call.get("name") or ""), dict(call.get("arguments") or {}))
        except Exception as exc:
            return ToolResult(
                tool_name=str(call.get("name") or ""),
                status="error",
                payload={"exception_type": type(exc).__name__},
                message=str(exc)[:1000],
            )


def _initial_messages(*, user_message: str, runtime_context: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"role": "system", "content": SEC_AGENT_CONTROLLER_SYSTEM_PROMPT},
        {
            "role": "system",
            "content": "Runtime context JSON:\n"
            + json.dumps(runtime_context, ensure_ascii=False, sort_keys=True, indent=2),
        },
        {"role": "user", "content": str(user_message or "")},
    ]


def _compact_runtime_context(
    *,
    session_id: str,
    user_id: str,
    tenant_id: str,
    active_answer_id: str,
    runtime_context: dict[str, Any],
) -> dict[str, Any]:
    context_snapshot = runtime_context.get("context_snapshot") if isinstance(runtime_context, dict) else {}
    if isinstance(context_snapshot, dict) and context_snapshot:
        return _compact_context_manager_snapshot(
            session_id=session_id,
            user_id=user_id,
            tenant_id=tenant_id,
            active_answer_id=active_answer_id,
            runtime_context=runtime_context,
            context_snapshot=context_snapshot,
        )
    initial_state = runtime_context.get("initial_state") if isinstance(runtime_context, dict) else {}
    initial_state = initial_state if isinstance(initial_state, dict) else {}
    expected_context = runtime_context.get("expected_context") if isinstance(runtime_context, dict) else {}
    expected_context = expected_context if isinstance(expected_context, dict) else {}
    bootstrap = runtime_context.get("bootstrap") if isinstance(runtime_context, dict) else {}
    bootstrap = bootstrap if isinstance(bootstrap, dict) else {}
    return {
        "session_id": session_id or str(initial_state.get("session_id") or ""),
        "user_id": user_id or str(initial_state.get("user_id") or ""),
        "tenant_id": tenant_id or str(initial_state.get("tenant_id") or ""),
        "active_answer_id": active_answer_id
        or str(expected_context.get("active_answer_id") or initial_state.get("active_answer_id") or ""),
        "initial_state": {
            "precondition": initial_state.get("precondition", ""),
            "active_answer_id": initial_state.get("active_answer_id", ""),
            "available_artifacts": initial_state.get("available_artifacts") or [],
            "missing_artifacts": initial_state.get("missing_artifacts") or [],
        },
        "bootstrap": bootstrap,
        "expected_context": expected_context,
        "prior_tool_calls": runtime_context.get("prior_tool_calls") or [],
    }


def _compact_context_manager_snapshot(
    *,
    session_id: str,
    user_id: str,
    tenant_id: str,
    active_answer_id: str,
    runtime_context: dict[str, Any],
    context_snapshot: dict[str, Any],
) -> dict[str, Any]:
    identity = context_snapshot.get("identity") if isinstance(context_snapshot.get("identity"), dict) else {}
    lossless = context_snapshot.get("lossless_fields") if isinstance(context_snapshot.get("lossless_fields"), dict) else {}
    active_session = context_snapshot.get("active_session") if isinstance(context_snapshot.get("active_session"), dict) else {}
    expected_context = runtime_context.get("expected_context") if isinstance(runtime_context.get("expected_context"), dict) else {}
    artifact_state = lossless.get("artifact_state") if isinstance(lossless.get("artifact_state"), dict) else {}
    active_scope = lossless.get("active_scope") if isinstance(lossless.get("active_scope"), dict) else {}
    source_policy = str(lossless.get("source_policy") or active_scope.get("source_policy") or "")
    return {
        "session_id": session_id or str(lossless.get("session_id") or active_session.get("session_id") or ""),
        "user_id": user_id or str(identity.get("user_id") or active_session.get("user_id") or ""),
        "tenant_id": tenant_id or str(identity.get("tenant_id") or active_session.get("tenant_id") or ""),
        "active_answer_id": active_answer_id
        or str(lossless.get("active_answer_id") or active_session.get("active_answer_id") or ""),
        "active_scope": active_scope,
        "source_policy": source_policy,
        "initial_state": {
            "precondition": "context_manager_snapshot",
            "active_answer_id": lossless.get("active_answer_id", ""),
            "available_artifacts": artifact_state.get("complete_artifacts") or [],
            "missing_artifacts": artifact_state.get("missing_artifacts") or [],
        },
        "expected_context": expected_context,
        "prior_tool_calls": runtime_context.get("prior_tool_calls") or [],
        "context_snapshot": {
            "status": context_snapshot.get("status"),
            "reason": context_snapshot.get("reason", ""),
            "identity": identity,
            "lossless_fields": lossless,
            "user_profile": context_snapshot.get("user_profile") or {},
            "session_candidates": context_snapshot.get("session_candidates") or [],
            "compression": context_snapshot.get("compression") or {},
            "summary": context_snapshot.get("summary") or "",
        },
    }


def _normalize_tool_calls(llm_result: dict[str, Any]) -> list[dict[str, Any]]:
    raw_calls = llm_result.get("tool_calls") or []
    if not raw_calls:
        message = llm_result.get("message") or {}
        raw_calls = message.get("tool_calls") or []
        if not raw_calls and isinstance(message.get("function_call"), dict):
            raw_calls = [{"id": "call_1", "type": "function", "function": message["function_call"]}]
    calls = []
    for index, raw in enumerate(raw_calls, start=1):
        if not isinstance(raw, dict):
            continue
        fn = raw.get("function") if isinstance(raw.get("function"), dict) else {}
        name = str(fn.get("name") or raw.get("name") or "")
        if not name:
            continue
        arguments = _parse_arguments(fn.get("arguments") if "arguments" in fn else raw.get("arguments"))
        calls.append(
            {
                "id": str(raw.get("id") or f"call_{index}"),
                "type": "function",
                "name": name,
                "arguments": arguments,
            }
        )
    return calls


def _parse_arguments(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    text = str(value or "").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _fill_runtime_defaults(name: str, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    result = dict(args)
    for key in ("session_id", "user_id", "tenant_id"):
        if key in _COMMON_RUNTIME_FIELDS.get(name, set()) and context.get(key):
            result[key] = context[key]
    if name in {"explain_evidence", "inspect_coverage", "reformat_answer", "resume_analysis"}:
        if context.get("active_answer_id"):
            result["answer_id"] = context["active_answer_id"]
    if name == "start_memo_analysis":
        result["source_policy"] = _default_source_policy(context)
        result.setdefault("preferred_output", "investment_memo")
    if name == "reformat_answer":
        result.setdefault("preserve_citations", True)
    if name == "revise_memo_scope":
        result.setdefault("preserve_output_style", True)
    return result


def _guarded_tool_name(name: str, *, user_message: str, runtime_context: dict[str, Any]) -> str:
    if name not in _COMMON_RUNTIME_FIELDS:
        return _heuristic_tool_name(user_message)
    heuristic_name = _heuristic_tool_name(user_message)
    if heuristic_name == "get_session_state":
        return "get_session_state"
    if name == "get_session_state" and heuristic_name in {
        "resume_analysis",
        "inspect_coverage",
        "explain_evidence",
        "reformat_answer",
    }:
        return heuristic_name
    return name


def _canonicalize_tool_arguments(name: str, args: dict[str, Any], *, user_message: str) -> dict[str, Any]:
    result = dict(args)
    if name == "start_memo_analysis":
        result["query"] = str(user_message or result.get("query") or "")
        if not result.get("years"):
            years = _extract_years(user_message)
            if years:
                result["years"] = years
    if name == "reformat_answer":
        current_format = str(result.get("format") or "")
        result["format"] = (
            current_format
            if current_format in CANONICAL_REFORMAT_FORMATS
            else _infer_format((current_format + "\n" + str(user_message or "")).strip())
        )
        result["preserve_citations"] = bool(result.get("preserve_citations", True))
    if name == "explain_evidence" and not result.get("driver_index"):
        driver_index = _extract_ordinal_index(str(user_message or ""))
        if driver_index:
            result["driver_index"] = driver_index
    if name == "explain_evidence" and not result.get("claim_reference"):
        claim_reference = _extract_claim_reference(str(user_message or ""))
        if claim_reference:
            result["claim_reference"] = claim_reference
    return result


CANONICAL_REFORMAT_FORMATS = {
    "pm_5_bullets",
    "investment_committee_three_sections",
    "bullets",
    "reformatted_answer",
}


_COMMON_RUNTIME_FIELDS = {
    "start_memo_analysis": {"session_id", "user_id", "tenant_id"},
    "revise_memo_scope": {"session_id", "user_id"},
    "explain_evidence": {"session_id"},
    "inspect_coverage": {"session_id"},
    "reformat_answer": {"session_id"},
    "resume_analysis": {"session_id"},
    "get_session_state": {"session_id", "user_id"},
}


def _assistant_message_from_result(llm_result: dict[str, Any], tool_calls: list[dict[str, Any]]) -> dict[str, Any]:
    message = dict(llm_result.get("message") or {})
    message["role"] = "assistant"
    message["content"] = message.get("content") or ""
    message["tool_calls"] = [
        {
            "id": call["id"],
            "type": "function",
            "function": {
                "name": call["name"],
                "arguments": json.dumps(call["arguments"], ensure_ascii=False),
            },
        }
        for call in tool_calls
    ]
    return message


def _compact_llm_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": result.get("status"),
        "provider": result.get("provider"),
        "model": result.get("model"),
        "finish_reason": result.get("finish_reason"),
        "content": str(result.get("content") or "")[:1000],
        "tool_call_count": len(result.get("tool_calls") or []),
        "latency_ms": result.get("latency_ms"),
        "input_tokens": result.get("input_tokens"),
        "output_tokens": result.get("output_tokens"),
        "failure_reason": result.get("failure_reason", ""),
    }


def _tool_result_summary(tool_results: list[dict[str, Any]]) -> str:
    compact = [
        {
            "tool_name": item.get("tool_name"),
            "status": item.get("status"),
            "message": item.get("message", ""),
        }
        for item in tool_results
    ]
    return json.dumps(compact, ensure_ascii=False)


def _tool_arg_allowlist(tool_specs: list[dict[str, Any]]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for spec in tool_specs:
        fn = spec.get("function") if isinstance(spec, dict) else {}
        if not isinstance(fn, dict):
            continue
        params = fn.get("parameters") if isinstance(fn.get("parameters"), dict) else {}
        props = params.get("properties") if isinstance(params.get("properties"), dict) else {}
        result[str(fn.get("name") or "")] = set(str(key) for key in props)
    return result


def _heuristic_chat_completion(*, user_message: str, runtime_context: dict[str, Any]) -> dict[str, Any]:
    started = time.time()
    call = _heuristic_tool_call(user_message=user_message, runtime_context=runtime_context)
    return {
        "status": "ok",
        "provider": "heuristic",
        "model": "sec_agent_tool_router_heuristic_v0",
        "role": "tool_controller",
        "profile": "sec_agent_tool_controller_v0",
        "content": "",
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": call["id"],
                    "type": "function",
                    "function": {
                        "name": call["name"],
                        "arguments": json.dumps(call["arguments"], ensure_ascii=False),
                    },
                }
            ],
        },
        "tool_calls": [
            {
                "id": call["id"],
                "type": "function",
                "function": {
                    "name": call["name"],
                    "arguments": json.dumps(call["arguments"], ensure_ascii=False),
                },
            }
        ],
        "finish_reason": "tool_calls",
        "latency_ms": int((time.time() - started) * 1000),
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
        "cost_estimate": None,
        "failure_reason": "",
        "trace_tags": {},
        "raw_response": {},
    }


def _heuristic_tool_call(*, user_message: str, runtime_context: dict[str, Any]) -> dict[str, Any]:
    text = str(user_message or "")
    name = _heuristic_tool_name(text)
    args = _heuristic_arguments(name=name, text=text, context=runtime_context)
    return {
        "id": "call_heuristic_1",
        "name": name,
        "arguments": args,
    }


def _heuristic_tool_name(text: str) -> str:
    normalized = text.lower()
    if _looks_like_state_check(text, normalized):
        return "get_session_state"
    if _contains_any(normalized, ("resume", "unfinished")) or _contains_any(text, ("继续", "没跑完", "恢复")):
        if not _contains_any(text, ("恢复后", "确认一下", "当前状态", "有哪些 artifacts")):
            return "resume_analysis"
    if _looks_like_coverage_or_boundary(text, normalized):
        return "inspect_coverage"
    if _looks_like_scope_revision(text, normalized):
        return "revise_memo_scope"
    if _looks_like_reformat(text, normalized):
        return "reformat_answer"
    if _looks_like_evidence_question(text, normalized):
        return "explain_evidence"
    return "start_memo_analysis"


def _heuristic_arguments(name: str, text: str, context: dict[str, Any]) -> dict[str, Any]:
    session_id = str(context.get("session_id") or "")
    user_id = str(context.get("user_id") or "")
    tenant_id = str(context.get("tenant_id") or "")
    active_answer_id = str(context.get("active_answer_id") or "")
    years = _extract_years(text)
    tickers = _extract_tickers(text)

    if name == "start_memo_analysis":
        return {
            "query": text,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "session_id": session_id,
            "years": years or [2023, 2024, 2025],
            "source_policy": _default_source_policy(context),
            "preferred_output": "investment_memo",
            "execute": True,
        }
    if name == "revise_memo_scope":
        remove_tickers = _extract_removed_tickers(text, tickers)
        add_tickers = [ticker for ticker in tickers if ticker not in set(remove_tickers)]
        args: dict[str, Any] = {
            "session_id": session_id,
            "user_id": user_id,
            "preserve_output_style": True,
            "execute": True,
        }
        if add_tickers:
            args["add_tickers"] = add_tickers
        if remove_tickers:
            args["remove_tickers"] = remove_tickers
        if years:
            args["years"] = years
        return args
    if name == "get_session_state":
        return {"session_id": session_id, "user_id": user_id}
    if name == "explain_evidence":
        args = {"session_id": session_id}
        if active_answer_id:
            args["answer_id"] = active_answer_id
        driver_index = _extract_ordinal_index(text)
        if driver_index:
            args["driver_index"] = driver_index
        claim_reference = _extract_claim_reference(text)
        if claim_reference:
            args["claim_reference"] = claim_reference
        evidence_id = _extract_evidence_id(text)
        if evidence_id:
            args["evidence_id"] = evidence_id
        return args
    if name == "inspect_coverage":
        args = {"session_id": session_id}
        if active_answer_id:
            args["answer_id"] = active_answer_id
        return args
    if name == "reformat_answer":
        args = {
            "session_id": session_id,
            "format": _infer_format(text),
            "preserve_citations": True,
            "execute": False,
        }
        if active_answer_id:
            args["answer_id"] = active_answer_id
        return args
    if name == "resume_analysis":
        args = {"session_id": session_id, "execute": True}
        if active_answer_id:
            args["answer_id"] = active_answer_id
        return args
    return {"session_id": session_id}


def _default_source_policy(context: dict[str, Any]) -> str:
    context_snapshot = context.get("context_snapshot") if isinstance(context.get("context_snapshot"), dict) else {}
    lossless = context_snapshot.get("lossless_fields") if isinstance(context_snapshot.get("lossless_fields"), dict) else {}
    snapshot_scope = lossless.get("active_scope") if isinstance(lossless.get("active_scope"), dict) else {}
    candidates = [
        ((context.get("bootstrap") or {}) if isinstance(context.get("bootstrap"), dict) else {}).get("source_policy"),
        ((context.get("active_scope") or {}) if isinstance(context.get("active_scope"), dict) else {}).get("source_policy"),
        lossless.get("source_policy"),
        snapshot_scope.get("source_policy"),
        ((context.get("expected_context") or {}) if isinstance(context.get("expected_context"), dict) else {}).get("source_policy"),
        context.get("source_policy"),
        os.environ.get("SEC_AGENT_SOURCE_POLICY"),
    ]
    for value in candidates:
        policy = str(value or "").strip()
        if policy in {"SEC_ONLY_10K", "SEC_PRIMARY_MIXED_RECENT"}:
            return policy
    return "SEC_ONLY_10K"


def _looks_like_state_check(text: str, normalized: str) -> bool:
    if _contains_any(normalized, ("active memo", "current state", "session state", "active_answer_id")):
        return True
    if _contains_any(text, ("当前 active memo", "当前状态", "先看当前状态", "确认一下", "有哪些 artifacts")):
        return True
    if "刚才那个" in text and _contains_any(text, ("哪个", "还在", "接着看")):
        return True
    return False


def _looks_like_coverage_or_boundary(text: str, normalized: str) -> bool:
    if _contains_any(normalized, ("coverage", "gap", "latest", "current", "buy", "sell")):
        return True
    if _contains_any(text, ("覆盖", "缺口", "缺年份", "指标缺", "完整吗", "全吗", "最新", "值得买", "现在是不是")):
        return True
    return False


def _looks_like_evidence_question(text: str, normalized: str) -> bool:
    if _contains_any(normalized, ("evidence", "source", "metric id", "10-k snippet")):
        return True
    if _contains_any(text, ("证据", "来源", "从哪", "片段", "毛利率改善")):
        return True
    return False


def _looks_like_scope_revision(text: str, normalized: str) -> bool:
    if _contains_any(normalized, ("remove", "add", "scope", "only look", "only analyze")):
        return True
    if _contains_any(text, ("拿掉", "去掉", "只看", "加进来", "不要同行", "改年份")):
        return True
    return False


def _looks_like_reformat(text: str, normalized: str) -> bool:
    if _contains_any(normalized, ("format", "bullet", "pm", "ic memo", "investment committee")):
        return True
    if _contains_any(text, ("改成", "压缩成", "三段", "格式", "语气", "PM", "投资委员会")):
        return True
    return False


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _extract_years(text: str) -> list[int]:
    years = []
    for match in re.findall(r"(?<!\d)(20\d{2})(?!\d)", text):
        year = int(match)
        if year not in years:
            years.append(year)
    return years


def _extract_tickers(text: str) -> list[str]:
    upper = text.upper()
    result = []
    for ticker in KNOWN_TICKERS:
        if re.search(rf"(?<![A-Z0-9]){re.escape(ticker)}(?![A-Z0-9])", upper):
            result.append(ticker)
    return result


def _extract_removed_tickers(text: str, tickers: list[str]) -> list[str]:
    if not _contains_any(text, ("拿掉", "去掉", "remove", "drop")):
        return []
    upper = text.upper()
    remove = []
    for ticker in tickers:
        ticker_pos = upper.find(ticker)
        if ticker_pos < 0:
            continue
        before = text[max(0, ticker_pos - 14) : ticker_pos]
        after = text[ticker_pos + len(ticker) : ticker_pos + len(ticker) + 14]
        if _contains_any(before, ("remove", "drop")) or _contains_any(after, ("拿掉", "去掉")):
            remove.append(ticker)
    return remove


def _extract_ordinal_index(text: str) -> int | None:
    if "第二" in text:
        return 2
    if "第一" in text:
        return 1
    if "第三" in text:
        return 3
    match = re.search(r"(?:driver|evidence|第)\s*(\d+)", text, flags=re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def _extract_evidence_id(text: str) -> str:
    match = re.search(r"\b(?:evidence[\s_-]*id|ev[_-]?id)[=:：\s]+([A-Za-z0-9_.:-]+)", text, flags=re.IGNORECASE)
    return str(match.group(1)) if match else ""


def _extract_claim_reference(text: str) -> str:
    cleaned = str(text or "").strip()
    if not cleaned:
        return ""
    if _looks_like_evidence_question(cleaned, cleaned.lower()):
        return cleaned[:240]
    return ""


def _infer_format(text: str) -> str:
    normalized = text.lower()
    if "5" in text and ("bullet" in normalized or "PM" in text or "pm" in normalized):
        return "pm_5_bullets"
    if "ic memo" in normalized or "投资委员会" in text or "三段" in text:
        return "investment_committee_three_sections"
    if "bullet" in normalized:
        return "bullets"
    return "reformatted_answer"
