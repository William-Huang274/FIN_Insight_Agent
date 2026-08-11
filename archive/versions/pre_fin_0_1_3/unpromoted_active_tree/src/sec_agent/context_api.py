from __future__ import annotations

import threading
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any

from sec_agent.context_manager import SecAgentContextManager
from sec_agent.tool_controller import DeepSeekToolController
from sec_agent.tool_harness import SecAgentToolHarness


REQUEST_RESULT_SCHEMA_VERSION = "sec_agent_context_request_result_v0.1"
EXECUTION_CAPABLE_TOOLS = {"start_memo_analysis", "revise_memo_scope", "resume_analysis"}


@dataclass
class SecAgentContextRequestHandler:
    """Request-level ContextManager control loop for future API integration.

    The handler is intentionally transport-agnostic. A web API can call this
    after authenticating the tenant/user and before serializing the result.
    JSON-backed context/session state is protected by a process-local lock in
    this v1 handler; multi-process serving should replace it with DB/Redis
    transactions or file locks.
    """

    context_manager: SecAgentContextManager
    controller: DeepSeekToolController
    harness: SecAgentToolHarness
    lock_requests: bool = True

    def __post_init__(self) -> None:
        self._lock = threading.RLock()

    def handle_turn(
        self,
        *,
        tenant_id: str,
        user_id: str,
        user_message: str,
        session_id: str = "",
        expected_context: dict[str, Any] | None = None,
        prior_tool_calls: list[dict[str, Any]] | None = None,
        allow_new_session: bool = False,
        execute_tools: bool = False,
        graph_args: list[str] | None = None,
    ) -> dict[str, Any]:
        if self.lock_requests:
            with self._lock:
                return self._handle_turn_unlocked(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    user_message=user_message,
                    session_id=session_id,
                    expected_context=expected_context,
                    prior_tool_calls=prior_tool_calls,
                    allow_new_session=allow_new_session,
                    execute_tools=execute_tools,
                    graph_args=graph_args,
                )
        return self._handle_turn_unlocked(
            tenant_id=tenant_id,
            user_id=user_id,
            user_message=user_message,
            session_id=session_id,
            expected_context=expected_context,
            prior_tool_calls=prior_tool_calls,
            allow_new_session=allow_new_session,
            execute_tools=execute_tools,
            graph_args=graph_args,
        )

    def _handle_turn_unlocked(
        self,
        *,
        tenant_id: str,
        user_id: str,
        user_message: str,
        session_id: str,
        expected_context: dict[str, Any] | None,
        prior_tool_calls: list[dict[str, Any]] | None,
        allow_new_session: bool,
        execute_tools: bool,
        graph_args: list[str] | None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        tenant_id = str(tenant_id or "")
        user_id = str(user_id or "")
        user_message = str(user_message or "")
        requested_session_id = str(session_id or "").strip()

        snapshot = self.context_manager.build_controller_context(
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=requested_session_id,
            user_message=user_message,
        )
        if snapshot.get("status") != "ready":
            if allow_new_session and _can_bootstrap_new_session(snapshot):
                return self._handle_new_session_bootstrap(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    user_message=user_message,
                    requested_session_id=requested_session_id,
                    expected_context=expected_context,
                    prior_tool_calls=prior_tool_calls,
                    snapshot=snapshot,
                    execute_tools=execute_tools,
                    graph_args=graph_args,
                    started=started,
                )
            return self._early_result(
                status=str(snapshot.get("status") or "context_error"),
                reason=str(snapshot.get("reason") or ""),
                snapshot=snapshot,
                started=started,
            )

        if requested_session_id:
            active_update = self.context_manager.set_active_session(
                tenant_id=tenant_id,
                user_id=user_id,
                session_id=requested_session_id,
            )
            if active_update.get("status") != "ready":
                return self._early_result(
                    status=str(active_update.get("status") or "context_error"),
                    reason=str(active_update.get("reason") or ""),
                    snapshot=active_update,
                    started=started,
                )
            snapshot = self.context_manager.build_controller_context(
                tenant_id=tenant_id,
                user_id=user_id,
                session_id="",
            user_message=user_message,
        )

        lossless = snapshot.get("lossless_fields") if isinstance(snapshot.get("lossless_fields"), dict) else {}
        resolved_session_id = str(lossless.get("session_id") or requested_session_id or "")
        active_answer_id = str(lossless.get("active_answer_id") or "")
        runtime_context = {
            "context_snapshot": snapshot,
            "expected_context": expected_context or {},
            "prior_tool_calls": prior_tool_calls or [],
        }
        controller_result = self.controller.run_turn(
            user_message=user_message,
            session_id=resolved_session_id,
            user_id=user_id,
            tenant_id=tenant_id,
            active_answer_id=active_answer_id,
            runtime_context=runtime_context,
            route_only=True,
        )
        tool_calls = controller_result.get("tool_calls") or []
        if not tool_calls:
            return {
                "schema_version": REQUEST_RESULT_SCHEMA_VERSION,
                "status": "controller_no_tool_call",
                "reason": "controller returned no tool calls",
                "context_snapshot": _compact_snapshot(snapshot),
                "controller_result": _compact_controller_result(controller_result),
                "tool_call": {},
                "tool_result": {},
                "context_update": {},
                "post_context_snapshot": {},
                "latency_ms": int((time.perf_counter() - started) * 1000),
            }

        tool_call = tool_calls[0]
        dispatch_arguments = _dispatch_arguments(
            tool_call=tool_call,
            execute_tools=execute_tools,
            graph_args=graph_args or [],
        )
        tool_result = self.harness.dispatch(
            str(tool_call.get("name") or ""),
            dispatch_arguments,
        ).to_dict()
        context_update = self.context_manager.apply_tool_result(
            tool_call={**tool_call, "arguments": dispatch_arguments},
            tool_result=tool_result,
        )
        post_snapshot = self.context_manager.build_controller_context(
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=resolved_session_id,
            user_message=user_message,
        )
        status = "completed" if tool_result.get("status") in {"completed", "planned"} else "tool_error"
        return {
            "schema_version": REQUEST_RESULT_SCHEMA_VERSION,
            "status": status,
            "reason": "",
            "context_snapshot": _compact_snapshot(snapshot),
            "controller_result": _compact_controller_result(controller_result),
            "tool_call": {
                "name": tool_call.get("name") or "",
                "arguments": dispatch_arguments,
            },
            "tool_result": _compact_tool_result(tool_result),
            "context_update": context_update,
            "post_context_snapshot": _compact_snapshot(post_snapshot),
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }

    def _handle_new_session_bootstrap(
        self,
        *,
        tenant_id: str,
        user_id: str,
        user_message: str,
        requested_session_id: str,
        expected_context: dict[str, Any] | None,
        prior_tool_calls: list[dict[str, Any]] | None,
        snapshot: dict[str, Any],
        execute_tools: bool,
        graph_args: list[str] | None,
        started: float,
    ) -> dict[str, Any]:
        resolved_session_id = requested_session_id or _new_session_id()
        runtime_context = {
            "initial_state": {
                "precondition": "new_context_session_bootstrap",
                "active_answer_id": "",
                "available_artifacts": [],
                "missing_artifacts": [],
            },
            "expected_context": expected_context or {},
            "prior_tool_calls": prior_tool_calls or [],
            "bootstrap": {
                "allow_new_session": True,
                "source_policy": _default_source_policy(),
            },
        }
        controller_result = self.controller.run_turn(
            user_message=user_message,
            session_id=resolved_session_id,
            user_id=user_id,
            tenant_id=tenant_id,
            active_answer_id="",
            runtime_context=runtime_context,
            route_only=True,
        )
        tool_calls = controller_result.get("tool_calls") or []
        if not tool_calls:
            return {
                "schema_version": REQUEST_RESULT_SCHEMA_VERSION,
                "status": "controller_no_tool_call",
                "reason": "controller returned no tool calls during new session bootstrap",
                "context_snapshot": _compact_snapshot(snapshot),
                "controller_result": _compact_controller_result(controller_result),
                "tool_call": {},
                "tool_result": {},
                "context_update": {},
                "post_context_snapshot": {},
                "latency_ms": int((time.perf_counter() - started) * 1000),
            }

        tool_call = dict(tool_calls[0])
        if str(tool_call.get("name") or "") != "start_memo_analysis":
            tool_call["name"] = "start_memo_analysis"
            tool_call["arguments"] = {
                "query": user_message,
                "session_id": resolved_session_id,
                "user_id": user_id,
                "tenant_id": tenant_id,
                "source_policy": _default_source_policy(),
                "preferred_output": "investment_memo",
            }
        dispatch_arguments = _dispatch_arguments(
            tool_call=tool_call,
            execute_tools=execute_tools,
            graph_args=graph_args or [],
        )
        dispatch_arguments["query"] = user_message
        dispatch_arguments["session_id"] = resolved_session_id
        dispatch_arguments["user_id"] = user_id
        dispatch_arguments["tenant_id"] = tenant_id
        dispatch_arguments["source_policy"] = _default_source_policy()
        dispatch_arguments.setdefault("preferred_output", "investment_memo")

        tool_result = self.harness.dispatch(str(tool_call.get("name") or ""), dispatch_arguments).to_dict()
        context_update = self.context_manager.apply_tool_result(
            tool_call={**tool_call, "arguments": dispatch_arguments},
            tool_result=tool_result,
        )
        post_snapshot = self.context_manager.build_controller_context(
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=resolved_session_id,
            user_message=user_message,
        )
        status = "completed" if tool_result.get("status") in {"completed", "planned"} else "tool_error"
        return {
            "schema_version": REQUEST_RESULT_SCHEMA_VERSION,
            "status": status,
            "reason": "new_session_bootstrap",
            "context_snapshot": _compact_snapshot(snapshot),
            "controller_result": _compact_controller_result(controller_result),
            "tool_call": {
                "name": tool_call.get("name") or "",
                "arguments": dispatch_arguments,
            },
            "tool_result": _compact_tool_result(tool_result),
            "context_update": context_update,
            "post_context_snapshot": _compact_snapshot(post_snapshot),
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }

    @staticmethod
    def _early_result(*, status: str, reason: str, snapshot: dict[str, Any], started: float) -> dict[str, Any]:
        return {
            "schema_version": REQUEST_RESULT_SCHEMA_VERSION,
            "status": status,
            "reason": reason,
            "context_snapshot": _compact_snapshot(snapshot),
            "controller_result": {},
            "tool_call": {},
            "tool_result": {},
            "context_update": {},
            "post_context_snapshot": {},
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }


def _compact_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    lossless = snapshot.get("lossless_fields") if isinstance(snapshot.get("lossless_fields"), dict) else {}
    return {
        "status": snapshot.get("status"),
        "reason": snapshot.get("reason", ""),
        "identity": snapshot.get("identity") or {},
        "session_id": lossless.get("session_id") or "",
        "active_answer_id": lossless.get("active_answer_id") or "",
        "active_scope": lossless.get("active_scope") or {},
        "artifact_state": lossless.get("artifact_state") or {},
        "resume": lossless.get("resume") or {},
        "session_candidates": snapshot.get("session_candidates") or [],
        "compression": snapshot.get("compression") or {},
        "validation_errors": snapshot.get("validation_errors") or [],
    }


def _compact_controller_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": result.get("status"),
        "controller_backend": result.get("controller_backend"),
        "route_only": result.get("route_only"),
        "latency_ms": result.get("latency_ms"),
        "tool_call_count": len(result.get("tool_calls") or []),
    }


def _compact_tool_result(result: dict[str, Any]) -> dict[str, Any]:
    payload = result.get("payload") if isinstance(result.get("payload"), dict) else {}
    return {
        "tool_name": result.get("tool_name"),
        "status": result.get("status"),
        "message": result.get("message", ""),
        "payload_keys": sorted(str(key) for key in payload.keys()),
        "payload": payload,
    }


def _dispatch_arguments(*, tool_call: dict[str, Any], execute_tools: bool, graph_args: list[str]) -> dict[str, Any]:
    name = str(tool_call.get("name") or "")
    arguments = dict(tool_call.get("arguments") or {})
    if name in EXECUTION_CAPABLE_TOOLS:
        arguments["execute"] = bool(execute_tools)
        if execute_tools:
            arguments["graph_args"] = list(graph_args or [])
    if name == "reformat_answer":
        arguments["execute"] = False
    return arguments


def _can_bootstrap_new_session(snapshot: dict[str, Any]) -> bool:
    if snapshot.get("status") != "error":
        return False
    reason = str(snapshot.get("reason") or "")
    return reason == "no_sessions_for_user" or reason.startswith("session not found:")


def _default_source_policy() -> str:
    value = str(os.environ.get("SEC_AGENT_SOURCE_POLICY") or "SEC_ONLY_10K").strip()
    if value in {"SEC_ONLY_10K", "SEC_PRIMARY_MIXED_RECENT", "SEC_PRIMARY_MIXED_WITH_8K_EARNINGS"}:
        return value
    return "SEC_ONLY_10K"


def _new_session_id() -> str:
    return f"session_{int(time.time())}_{uuid.uuid4().hex[:10]}"
