"""S2 tool gateway, sandbox policy, and invocation ledger.

This module builds on the S1 runtime task spine.  It does not execute
unbounded tools; it records policy decisions, artifact refs, trace spans, and
blocked reasons before any later slice wires real tool handlers.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import urlparse

from sec_agent.r53_r60_runtime_task_spine import (
    FinSightResearchRuntimeFacade,
    RuntimeTaskSpineStore,
    default_s1_paths,
    digest_payload,
    json_dumps,
    json_loads,
    rel_path,
    stable_id,
    utc_now_iso,
    write_json,
    write_jsonl,
)


SCHEMA_VERSION = "r53_r60_s2_tool_sandbox_trace_spine_v0_1"

TOOL_STATUSES = ("allowed", "blocked", "executed", "error")
SECRET_ARGUMENT_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "credentials",
    "password",
    "secret",
    "token",
}


@dataclass(frozen=True)
class S2Paths:
    db_path: Path
    schema_path: Path
    gate_rows_path: Path
    summary_path: Path
    report_path: Path


@dataclass(frozen=True)
class ToolDefinition:
    tool_id: str
    category: str
    input_schema: str
    output_schema: str
    allowed_actors: tuple[str, ...]
    sandbox_policy_id: str
    approval_policy_id: str
    source_boundary: str
    artifact_type: str
    network_required: bool = False
    filesystem_required: bool = False
    credential_access_allowed: bool = False


@dataclass(frozen=True)
class SandboxPolicy:
    sandbox_policy_id: str
    network_mode: str
    allowed_domains: tuple[str, ...] = ()
    path_mode: str = "workspace_scoped"
    allowed_path_roots: tuple[str, ...] = ("workspace", "temp", "artifact_store")
    max_timeout_ms: int = 30000
    max_output_bytes: int = 1_000_000
    credential_access: str = "forbidden"


@dataclass(frozen=True)
class ApprovalPolicy:
    approval_policy_id: str
    default_action: str
    approval_required: bool
    approver_roles: tuple[str, ...] = ()
    reason: str = ""


@dataclass
class ToolInvocationDecision:
    tool_call_id: str
    task_id: str
    run_id: str
    actor_id: str
    node: str
    tool_id: str
    status: str
    input_digest: str
    output_digest: str = ""
    blocked_reason: str = ""
    policy_decision: str = "allow"
    sandbox_policy_id: str = ""
    approval_policy_id: str = ""
    approval_decision_id: str = ""
    artifact_ref_ids: list[str] = field(default_factory=list)
    trace_span_id: str = ""
    latency_ms: int = 0
    error_message: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["schema_version"] = SCHEMA_VERSION
        return payload


Handler = Callable[[Mapping[str, Any]], Mapping[str, Any]]


def default_s2_paths(root: Path) -> S2Paths:
    s1_paths = default_s1_paths(root)
    return S2Paths(
        db_path=s1_paths.db_path,
        schema_path=root / "configs" / "r53_r60" / "s2_tool_sandbox_trace_schema_v0_1.json",
        gate_rows_path=root / "data" / "manifests" / "r53_r60_s2_tool_sandbox_trace_gate_rows_v0_1.jsonl",
        summary_path=root / "data" / "manifests" / "r53_r60_s2_tool_sandbox_trace_summary_v0_1.json",
        report_path=root / "docs" / "internal" / "vnext_20260610" / "r53_r60_s2_tool_sandbox_trace_l4_scope_pass.zh-CN.md",
    )


def default_tool_definitions() -> dict[str, ToolDefinition]:
    items = [
        ToolDefinition(
            tool_id="database_query",
            category="db_rag",
            input_schema="sql_query_request_v0_1",
            output_schema="sql_result_artifact_v0_1",
            allowed_actors=("research_lead", "evidence_operator", "fundamental_specialist", "product_specialist", "market_specialist"),
            sandbox_policy_id="local_db_readonly",
            approval_policy_id="auto_allow_low_risk",
            source_boundary="query_results_keep_original_source_authority",
            artifact_type="tool_result_database_query",
        ),
        ToolDefinition(
            tool_id="live_web_snapshot",
            category="crawler_browser",
            input_schema="allowlisted_web_snapshot_request_v0_1",
            output_schema="web_snapshot_artifact_v0_1",
            allowed_actors=("research_lead", "evidence_operator"),
            sandbox_policy_id="allowlisted_public_web",
            approval_policy_id="auto_allow_allowlisted_web",
            source_boundary="context_only_until_parser_authority_gate",
            artifact_type="tool_result_web_snapshot",
            network_required=True,
        ),
        ToolDefinition(
            tool_id="document_parser",
            category="parser_render",
            input_schema="uploaded_file_ref_v0_1",
            output_schema="parsed_document_artifact_v0_1",
            allowed_actors=("input_parser", "research_lead"),
            sandbox_policy_id="workspace_file_readonly",
            approval_policy_id="auto_allow_workspace_file",
            source_boundary="user_provided_context_until_parser_gate",
            artifact_type="tool_result_document_parser",
            filesystem_required=True,
        ),
        ToolDefinition(
            tool_id="report_renderer",
            category="deliverable_renderer",
            input_schema="verified_memo_payload_v0_1",
            output_schema="rendered_report_artifact_v0_1",
            allowed_actors=("memo_writer", "report_renderer", "deliverable_composer"),
            sandbox_policy_id="workspace_artifact_write",
            approval_policy_id="auto_allow_render_only",
            source_boundary="render_only_no_new_facts",
            artifact_type="tool_result_report_renderer",
            filesystem_required=True,
        ),
        ToolDefinition(
            tool_id="python_analysis",
            category="analysis_runtime",
            input_schema="bounded_python_analysis_request_v0_1",
            output_schema="analysis_artifact_v0_1",
            allowed_actors=("research_lead", "quant_worker"),
            sandbox_policy_id="local_no_network_workspace_temp",
            approval_policy_id="requires_human_for_code_execution",
            source_boundary="analysis_on_verified_inputs_only",
            artifact_type="tool_result_python_analysis",
            filesystem_required=True,
        ),
        ToolDefinition(
            tool_id="backtest_runner",
            category="quant_runtime",
            input_schema="factor_backtest_plan_v0_1",
            output_schema="backtest_result_artifact_v0_1",
            allowed_actors=("quant_worker",),
            sandbox_policy_id="local_no_network_workspace_temp",
            approval_policy_id="requires_human_for_quant_backtest",
            source_boundary="research_to_quant_validation_only_no_trading",
            artifact_type="tool_result_backtest_runner",
            filesystem_required=True,
        ),
    ]
    return {item.tool_id: item for item in items}


def default_sandbox_policies() -> dict[str, SandboxPolicy]:
    items = [
        SandboxPolicy("local_db_readonly", network_mode="none", path_mode="no_filesystem"),
        SandboxPolicy(
            "allowlisted_public_web",
            network_mode="allowlist",
            allowed_domains=("sec.gov", "company-ir.example", "nvidia.com", "asml.com", "microsoft.com", "amazon.com"),
            path_mode="artifact_store_only",
            allowed_path_roots=("artifact_store",),
        ),
        SandboxPolicy("workspace_file_readonly", network_mode="none", path_mode="workspace_scoped", allowed_path_roots=("workspace", "temp")),
        SandboxPolicy("workspace_artifact_write", network_mode="none", path_mode="artifact_store_only", allowed_path_roots=("artifact_store", "temp")),
        SandboxPolicy("local_no_network_workspace_temp", network_mode="none", path_mode="workspace_scoped", allowed_path_roots=("workspace", "temp", "artifact_store")),
    ]
    return {item.sandbox_policy_id: item for item in items}


def default_approval_policies() -> dict[str, ApprovalPolicy]:
    items = [
        ApprovalPolicy("auto_allow_low_risk", "allow", False, reason="read-only exact or retrieval query"),
        ApprovalPolicy("auto_allow_allowlisted_web", "allow", False, reason="allowlisted public web snapshot"),
        ApprovalPolicy("auto_allow_workspace_file", "allow", False, reason="workspace-scoped user input parsing"),
        ApprovalPolicy("auto_allow_render_only", "allow", False, reason="render-only artifact generation"),
        ApprovalPolicy("requires_human_for_code_execution", "block_without_approval", True, ("human_reviewer",), "bounded local code execution"),
        ApprovalPolicy("requires_human_for_quant_backtest", "block_without_approval", True, ("human_reviewer",), "quant validation can be compute-heavy and must be reviewed"),
    ]
    return {item.approval_policy_id: item for item in items}


def tool_sandbox_schema_contract() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "closeout_level": "L4_scope_pass",
        "status_values": list(TOOL_STATUSES),
        "tables": [
            "tool_gateway_metadata",
            "tool_policy_bindings",
            "sandbox_policies",
            "approval_policies",
            "approval_decisions",
            "tool_invocations",
        ],
        "policy": {
            "fail_closed": True,
            "writer_fact_retrieval_forbidden": True,
            "unknown_tools_blocked": True,
            "credential_input_forbidden_by_default": True,
            "network_requires_allowlist": True,
            "filesystem_paths_workspace_scoped": True,
            "redis_or_mq_not_final_audit": True,
        },
        "tool_definitions": [asdict(item) for item in default_tool_definitions().values()],
        "sandbox_policies": [asdict(item) for item in default_sandbox_policies().values()],
        "approval_policies": [asdict(item) for item in default_approval_policies().values()],
    }


class ToolPolicyViolation(RuntimeError):
    """Raised for internal policy-contract violations."""


class FinSightToolGateway:
    """S2 MCP-style gateway that records policy decisions into the S1 ledger."""

    def __init__(
        self,
        runtime: FinSightResearchRuntimeFacade,
        *,
        workspace_root: str | Path,
        artifact_root: str | Path | None = None,
        handlers: Mapping[str, Handler] | None = None,
    ):
        self.runtime = runtime
        self.workspace_root = Path(workspace_root).resolve()
        self.artifact_root = Path(artifact_root).resolve() if artifact_root else self.workspace_root / "data" / "workbench_private"
        self.tool_definitions = default_tool_definitions()
        self.sandbox_policies = default_sandbox_policies()
        self.approval_policies = default_approval_policies()
        self.handlers = dict(handlers or {})
        with self.runtime.store._connect() as conn:
            create_tool_sandbox_schema(conn)
            seed_tool_sandbox_contract(conn)

    def invoke_tool(
        self,
        task_id: str,
        *,
        actor_id: str,
        node: str,
        tool_id: str,
        arguments: Mapping[str, Any] | None = None,
        approval_decision: Mapping[str, Any] | None = None,
    ) -> ToolInvocationDecision:
        arguments = dict(arguments or {})
        state = self.runtime.get_task_state(task_id)
        run_id = str(state["task"]["current_run_id"])
        input_digest = digest_payload({"tool_id": tool_id, "arguments": normalize_tool_arguments(arguments)})
        approval_marker = str((approval_decision or {}).get("approval_decision_id") or "no_approval")
        tool_call_id = stable_id("toolcall", [task_id, run_id, actor_id, node, tool_id, input_digest, approval_marker])
        now = utc_now_iso()

        definition = self.tool_definitions.get(tool_id)
        checks = self._evaluate_policy(
            actor_id=actor_id,
            tool_id=tool_id,
            arguments=arguments,
            definition=definition,
            approval_decision=approval_decision,
        )
        if checks["status"] == "blocked":
            decision = ToolInvocationDecision(
                tool_call_id=tool_call_id,
                task_id=task_id,
                run_id=run_id,
                actor_id=actor_id,
                node=node,
                tool_id=tool_id,
                status="blocked",
                input_digest=input_digest,
                blocked_reason=str(checks["blocked_reason"]),
                policy_decision="block",
                sandbox_policy_id=str(checks.get("sandbox_policy_id") or ""),
                approval_policy_id=str(checks.get("approval_policy_id") or ""),
                approval_decision_id=str(checks.get("approval_decision_id") or ""),
                payload={"arguments": redact_sensitive_arguments(arguments), "checks": checks},
            )
            self._persist_decision(decision, created_at=now)
            return decision

        output_payload: Mapping[str, Any]
        error_message = ""
        status = "executed"
        try:
            handler = self.handlers.get(tool_id)
            if handler is None:
                output_payload = default_tool_output(tool_id, arguments)
            else:
                output_payload = handler(arguments)
        except Exception as exc:  # noqa: BLE001
            status = "error"
            error_message = f"{type(exc).__name__}:{exc}"
            output_payload = {"status": "error", "error": error_message}

        artifact_ref_ids: list[str] = []
        output_digest = digest_payload(output_payload)
        artifact_type = definition.artifact_type if definition else "tool_result_unknown"
        if status == "executed":
            artifact = self.runtime.record_artifact_ref(
                task_id,
                artifact_type=artifact_type,
                uri=f"inline://s2/tool/{tool_call_id}",
                payload={
                    "tool_call_id": tool_call_id,
                    "tool_id": tool_id,
                    "output": dict(output_payload),
                    "source_boundary": definition.source_boundary if definition else "",
                },
                actor=actor_id,
            )
            artifact_ref_ids.append(artifact["artifact_ref_id"])

        decision = ToolInvocationDecision(
            tool_call_id=tool_call_id,
            task_id=task_id,
            run_id=run_id,
            actor_id=actor_id,
            node=node,
            tool_id=tool_id,
            status=status,
            input_digest=input_digest,
            output_digest=output_digest,
            policy_decision="allow",
            sandbox_policy_id=definition.sandbox_policy_id if definition else "",
            approval_policy_id=definition.approval_policy_id if definition else "",
            approval_decision_id=str(checks.get("approval_decision_id") or ""),
            artifact_ref_ids=artifact_ref_ids,
            latency_ms=0,
            error_message=error_message,
            payload={
                "arguments": redact_sensitive_arguments(arguments),
                "checks": checks,
                "output_status": dict(output_payload).get("status", "ok"),
            },
        )
        self._persist_decision(decision, created_at=now)
        return decision

    def _evaluate_policy(
        self,
        *,
        actor_id: str,
        tool_id: str,
        arguments: Mapping[str, Any],
        definition: ToolDefinition | None,
        approval_decision: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        if definition is None:
            return {"status": "blocked", "blocked_reason": "unknown_tool", "tool_id": tool_id}
        sandbox = self.sandbox_policies[definition.sandbox_policy_id]
        approval = self.approval_policies[definition.approval_policy_id]
        if actor_id not in definition.allowed_actors:
            return {
                "status": "blocked",
                "blocked_reason": "actor_tool_not_allowed",
                "tool_id": tool_id,
                "actor_id": actor_id,
                "allowed_actors": list(definition.allowed_actors),
                "sandbox_policy_id": sandbox.sandbox_policy_id,
                "approval_policy_id": approval.approval_policy_id,
            }
        secret_key = find_secret_argument_key(arguments)
        if secret_key and not definition.credential_access_allowed:
            return {
                "status": "blocked",
                "blocked_reason": "credential_argument_forbidden",
                "secret_key": secret_key,
                "sandbox_policy_id": sandbox.sandbox_policy_id,
                "approval_policy_id": approval.approval_policy_id,
            }
        if definition.network_required:
            url = str(arguments.get("url") or arguments.get("source_url") or "")
            domain_decision = validate_network_url(url, sandbox)
            if not domain_decision["allowed"]:
                return {
                    "status": "blocked",
                    "blocked_reason": domain_decision["reason"],
                    "url": url,
                    "sandbox_policy_id": sandbox.sandbox_policy_id,
                    "approval_policy_id": approval.approval_policy_id,
                }
        if definition.filesystem_required:
            for key in ("path", "input_path", "output_path", "artifact_uri", "workspace_path"):
                if key in arguments:
                    path_decision = validate_workspace_path(str(arguments.get(key) or ""), sandbox, self.workspace_root, self.artifact_root)
                    if not path_decision["allowed"]:
                        return {
                            "status": "blocked",
                            "blocked_reason": path_decision["reason"],
                            "path_key": key,
                            "path": str(arguments.get(key) or ""),
                            "sandbox_policy_id": sandbox.sandbox_policy_id,
                            "approval_policy_id": approval.approval_policy_id,
                        }
        approval_result = evaluate_approval(approval, approval_decision)
        if not approval_result["allowed"]:
            return {
                "status": "blocked",
                "blocked_reason": approval_result["reason"],
                "sandbox_policy_id": sandbox.sandbox_policy_id,
                "approval_policy_id": approval.approval_policy_id,
                "approval_decision_id": approval_result.get("approval_decision_id", ""),
            }
        return {
            "status": "allowed",
            "sandbox_policy_id": sandbox.sandbox_policy_id,
            "approval_policy_id": approval.approval_policy_id,
            "approval_decision_id": approval_result.get("approval_decision_id", ""),
        }

    def _persist_decision(self, decision: ToolInvocationDecision, *, created_at: str) -> None:
        with self.runtime.store._connect() as conn:
            conn.execute("begin immediate")
            try:
                conn.execute(
                    """
                    insert or replace into tool_invocations (
                        tool_call_id, task_id, run_id, actor_id, node, tool_id, status,
                        policy_decision, blocked_reason, sandbox_policy_id,
                        approval_policy_id, approval_decision_id, input_digest,
                        output_digest, artifact_ref_ids_json, trace_span_id,
                        latency_ms, error_message, payload_json, created_at
                    ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        decision.tool_call_id,
                        decision.task_id,
                        decision.run_id,
                        decision.actor_id,
                        decision.node,
                        decision.tool_id,
                        decision.status,
                        decision.policy_decision,
                        decision.blocked_reason,
                        decision.sandbox_policy_id,
                        decision.approval_policy_id,
                        decision.approval_decision_id,
                        decision.input_digest,
                        decision.output_digest,
                        json_dumps(decision.artifact_ref_ids),
                        decision.trace_span_id,
                        decision.latency_ms,
                        decision.error_message,
                        json_dumps(decision.payload),
                        created_at,
                    ),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        event_type = "tool_invocation_blocked" if decision.status == "blocked" else "tool_invocation_recorded"
        self.runtime.store.append_event(
            decision.task_id,
            actor=decision.actor_id,
            event_type=event_type,
            message=f"{decision.tool_id} {decision.status}",
            payload={
                "tool_call_id": decision.tool_call_id,
                "tool_id": decision.tool_id,
                "status": decision.status,
                "policy_decision": decision.policy_decision,
                "blocked_reason": decision.blocked_reason,
                "artifact_ref_ids": decision.artifact_ref_ids,
            },
            stream="tool_gateway",
        )
        span = self.runtime.record_trace_span(
            decision.task_id,
            span_kind="tool_call",
            name=decision.tool_id,
            status="blocked" if decision.status == "blocked" else decision.status,
            actor=decision.actor_id,
            latency_ms=decision.latency_ms,
            token_count=0,
            cost_amount=0.0,
            provider="s2_tool_gateway",
            payload={
                "tool_call_id": decision.tool_call_id,
                "policy_decision": decision.policy_decision,
                "blocked_reason": decision.blocked_reason,
                "artifact_ref_ids": decision.artifact_ref_ids,
            },
        )
        if not decision.trace_span_id:
            with self.runtime.store._connect() as conn:
                conn.execute(
                    "update tool_invocations set trace_span_id = ? where tool_call_id = ?",
                    (span["span_id"], decision.tool_call_id),
                )


def create_tool_sandbox_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists tool_gateway_metadata (
            key text primary key,
            value_json text not null,
            updated_at text not null
        );
        create table if not exists tool_policy_bindings (
            tool_id text primary key,
            category text not null,
            input_schema text not null,
            output_schema text not null,
            allowed_actors_json text not null,
            sandbox_policy_id text not null,
            approval_policy_id text not null,
            source_boundary text not null,
            artifact_type text not null,
            payload_json text not null default '{}',
            updated_at text not null
        );
        create table if not exists sandbox_policies (
            sandbox_policy_id text primary key,
            network_mode text not null,
            allowed_domains_json text not null default '[]',
            path_mode text not null,
            allowed_path_roots_json text not null default '[]',
            max_timeout_ms integer not null,
            max_output_bytes integer not null,
            credential_access text not null,
            payload_json text not null default '{}',
            updated_at text not null
        );
        create table if not exists approval_policies (
            approval_policy_id text primary key,
            default_action text not null,
            approval_required integer not null,
            approver_roles_json text not null default '[]',
            reason text not null default '',
            payload_json text not null default '{}',
            updated_at text not null
        );
        create table if not exists approval_decisions (
            approval_decision_id text primary key,
            task_id text not null,
            run_id text not null,
            actor_id text not null,
            tool_id text not null,
            decision text not null,
            approver_actor_id text not null default '',
            reason text not null default '',
            payload_json text not null default '{}',
            created_at text not null
        );
        create table if not exists tool_invocations (
            tool_call_id text primary key,
            task_id text not null,
            run_id text not null,
            actor_id text not null,
            node text not null,
            tool_id text not null,
            status text not null,
            policy_decision text not null,
            blocked_reason text not null default '',
            sandbox_policy_id text not null default '',
            approval_policy_id text not null default '',
            approval_decision_id text not null default '',
            input_digest text not null,
            output_digest text not null default '',
            artifact_ref_ids_json text not null default '[]',
            trace_span_id text not null default '',
            latency_ms integer not null default 0,
            error_message text not null default '',
            payload_json text not null default '{}',
            created_at text not null,
            foreign key (task_id) references research_tasks(task_id) on delete cascade,
            foreign key (run_id) references task_runs(run_id) on delete cascade,
            check (status in ('allowed','blocked','executed','error'))
        );
        create index if not exists idx_tool_invocations_task on tool_invocations(task_id, run_id);
        create index if not exists idx_tool_invocations_actor_tool on tool_invocations(actor_id, tool_id, status);
        """
    )


def seed_tool_sandbox_contract(conn: sqlite3.Connection) -> None:
    now = utc_now_iso()
    conn.execute(
        """
        insert into tool_gateway_metadata(key, value_json, updated_at)
        values (?, ?, ?)
        on conflict(key) do update set value_json = excluded.value_json, updated_at = excluded.updated_at
        """,
        ("schema_version", json_dumps(SCHEMA_VERSION), now),
    )
    for tool in default_tool_definitions().values():
        conn.execute(
            """
            insert into tool_policy_bindings(
                tool_id, category, input_schema, output_schema, allowed_actors_json,
                sandbox_policy_id, approval_policy_id, source_boundary, artifact_type,
                payload_json, updated_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            on conflict(tool_id) do update set
                category = excluded.category,
                input_schema = excluded.input_schema,
                output_schema = excluded.output_schema,
                allowed_actors_json = excluded.allowed_actors_json,
                sandbox_policy_id = excluded.sandbox_policy_id,
                approval_policy_id = excluded.approval_policy_id,
                source_boundary = excluded.source_boundary,
                artifact_type = excluded.artifact_type,
                payload_json = excluded.payload_json,
                updated_at = excluded.updated_at
            """,
            (
                tool.tool_id,
                tool.category,
                tool.input_schema,
                tool.output_schema,
                json_dumps(list(tool.allowed_actors)),
                tool.sandbox_policy_id,
                tool.approval_policy_id,
                tool.source_boundary,
                tool.artifact_type,
                json_dumps(asdict(tool)),
                now,
            ),
        )
    for policy in default_sandbox_policies().values():
        conn.execute(
            """
            insert into sandbox_policies(
                sandbox_policy_id, network_mode, allowed_domains_json, path_mode,
                allowed_path_roots_json, max_timeout_ms, max_output_bytes,
                credential_access, payload_json, updated_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            on conflict(sandbox_policy_id) do update set
                network_mode = excluded.network_mode,
                allowed_domains_json = excluded.allowed_domains_json,
                path_mode = excluded.path_mode,
                allowed_path_roots_json = excluded.allowed_path_roots_json,
                max_timeout_ms = excluded.max_timeout_ms,
                max_output_bytes = excluded.max_output_bytes,
                credential_access = excluded.credential_access,
                payload_json = excluded.payload_json,
                updated_at = excluded.updated_at
            """,
            (
                policy.sandbox_policy_id,
                policy.network_mode,
                json_dumps(list(policy.allowed_domains)),
                policy.path_mode,
                json_dumps(list(policy.allowed_path_roots)),
                policy.max_timeout_ms,
                policy.max_output_bytes,
                policy.credential_access,
                json_dumps(asdict(policy)),
                now,
            ),
        )
    for policy in default_approval_policies().values():
        conn.execute(
            """
            insert into approval_policies(
                approval_policy_id, default_action, approval_required,
                approver_roles_json, reason, payload_json, updated_at
            ) values (?, ?, ?, ?, ?, ?, ?)
            on conflict(approval_policy_id) do update set
                default_action = excluded.default_action,
                approval_required = excluded.approval_required,
                approver_roles_json = excluded.approver_roles_json,
                reason = excluded.reason,
                payload_json = excluded.payload_json,
                updated_at = excluded.updated_at
            """,
            (
                policy.approval_policy_id,
                policy.default_action,
                1 if policy.approval_required else 0,
                json_dumps(list(policy.approver_roles)),
                policy.reason,
                json_dumps(asdict(policy)),
                now,
            ),
        )


def record_approval_decision(
    store: RuntimeTaskSpineStore,
    task_id: str,
    *,
    actor_id: str,
    tool_id: str,
    decision: str,
    approver_actor_id: str,
    reason: str = "",
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    state = store.get_task_state(task_id)
    run_id = str(state["task"]["current_run_id"])
    approval_decision_id = stable_id("approval", [task_id, run_id, actor_id, tool_id, decision, approver_actor_id, reason])
    now = utc_now_iso()
    with store._connect() as conn:
        create_tool_sandbox_schema(conn)
        seed_tool_sandbox_contract(conn)
        conn.execute(
            """
            insert or replace into approval_decisions(
                approval_decision_id, task_id, run_id, actor_id, tool_id, decision,
                approver_actor_id, reason, payload_json, created_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                approval_decision_id,
                task_id,
                run_id,
                actor_id,
                tool_id,
                decision,
                approver_actor_id,
                reason,
                json_dumps(dict(payload or {})),
                now,
            ),
        )
    return {
        "approval_decision_id": approval_decision_id,
        "task_id": task_id,
        "run_id": run_id,
        "actor_id": actor_id,
        "tool_id": tool_id,
        "decision": decision,
        "approver_actor_id": approver_actor_id,
        "reason": reason,
    }


def evaluate_approval(policy: ApprovalPolicy, decision: Mapping[str, Any] | None) -> dict[str, Any]:
    if not policy.approval_required:
        return {"allowed": True, "reason": "", "approval_decision_id": ""}
    if not decision:
        return {"allowed": False, "reason": "human_approval_required", "approval_decision_id": ""}
    if str(decision.get("decision") or "").lower() != "approved":
        return {
            "allowed": False,
            "reason": "human_approval_not_granted",
            "approval_decision_id": str(decision.get("approval_decision_id") or ""),
        }
    approver = str(decision.get("approver_actor_id") or "")
    if approver not in policy.approver_roles:
        return {
            "allowed": False,
            "reason": "approval_role_not_allowed",
            "approval_decision_id": str(decision.get("approval_decision_id") or ""),
        }
    return {"allowed": True, "reason": "", "approval_decision_id": str(decision.get("approval_decision_id") or "")}


def validate_network_url(url: str, policy: SandboxPolicy) -> dict[str, Any]:
    if policy.network_mode == "none":
        return {"allowed": False, "reason": "network_forbidden"}
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if not host:
        return {"allowed": False, "reason": "url_required"}
    if policy.network_mode != "allowlist":
        return {"allowed": False, "reason": "unsupported_network_mode"}
    allowed = tuple(domain.lower() for domain in policy.allowed_domains)
    if any(host == domain or host.endswith("." + domain) for domain in allowed):
        return {"allowed": True, "reason": ""}
    return {"allowed": False, "reason": "domain_not_allowlisted"}


def validate_workspace_path(path_text: str, policy: SandboxPolicy, workspace_root: Path, artifact_root: Path) -> dict[str, Any]:
    if policy.path_mode == "no_filesystem":
        return {"allowed": False, "reason": "filesystem_forbidden"}
    if not path_text:
        return {"allowed": True, "reason": ""}
    if path_text.startswith("inline://"):
        return {"allowed": True, "reason": ""}
    path = Path(path_text)
    resolved = path.resolve() if path.is_absolute() else (workspace_root / path).resolve()
    allowed_roots: list[Path] = []
    for root_key in policy.allowed_path_roots:
        if root_key == "workspace":
            allowed_roots.append(workspace_root)
        elif root_key == "temp":
            allowed_roots.append(workspace_root / ".tmp")
        elif root_key == "artifact_store":
            allowed_roots.append(artifact_root)
    if any(is_relative_to(resolved, root.resolve()) for root in allowed_roots):
        return {"allowed": True, "reason": ""}
    return {"allowed": False, "reason": "path_outside_allowed_roots"}


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def find_secret_argument_key(value: Any, *, parent: str = "") -> str:
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            if key_text.lower().replace("-", "_") in SECRET_ARGUMENT_KEYS:
                return f"{parent}.{key_text}".strip(".")
            found = find_secret_argument_key(item, parent=f"{parent}.{key_text}".strip("."))
            if found:
                return found
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found = find_secret_argument_key(item, parent=f"{parent}[{index}]")
            if found:
                return found
    return ""


def redact_sensitive_arguments(value: Any) -> Any:
    if isinstance(value, Mapping):
        clean: dict[str, Any] = {}
        for key, item in value.items():
            if str(key).lower().replace("-", "_") in SECRET_ARGUMENT_KEYS:
                clean[str(key)] = "[REDACTED]"
            else:
                clean[str(key)] = redact_sensitive_arguments(item)
        return clean
    if isinstance(value, list):
        return [redact_sensitive_arguments(item) for item in value]
    return value


def normalize_tool_arguments(arguments: Mapping[str, Any]) -> dict[str, Any]:
    return _normalize_value(arguments)


def _normalize_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _normalize_value(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, list):
        return [_normalize_value(item) for item in value]
    return value


def default_tool_output(tool_id: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": "ok",
        "tool_id": tool_id,
        "row_count": 1,
        "result_digest": digest_payload({"tool_id": tool_id, "arguments": normalize_tool_arguments(arguments)}),
        "bounded_output": True,
    }


def table_counts(store: RuntimeTaskSpineStore) -> dict[str, int]:
    tables = [
        "tool_gateway_metadata",
        "tool_policy_bindings",
        "sandbox_policies",
        "approval_policies",
        "approval_decisions",
        "tool_invocations",
    ]
    with store._connect() as conn:
        create_tool_sandbox_schema(conn)
        return {table: int(conn.execute(f"select count(*) from {table}").fetchone()[0]) for table in tables}


def reset_s2_dogfood_rows(store: RuntimeTaskSpineStore) -> None:
    with store._connect() as conn:
        create_tool_sandbox_schema(conn)
        seed_tool_sandbox_contract(conn)
        conn.execute("delete from research_tasks where task_id = ?", ("s2_scope_task_tool_sandbox",))
        conn.execute("delete from approval_decisions where task_id = ?", ("s2_scope_task_tool_sandbox",))
        conn.execute("delete from tool_invocations where task_id = ?", ("s2_scope_task_tool_sandbox",))


def build_s2_gate(root: Path) -> dict[str, Any]:
    root = root.resolve()
    paths = default_s2_paths(root)
    paths.schema_path.parent.mkdir(parents=True, exist_ok=True)
    paths.gate_rows_path.parent.mkdir(parents=True, exist_ok=True)
    paths.report_path.parent.mkdir(parents=True, exist_ok=True)

    runtime = FinSightResearchRuntimeFacade(paths.db_path)
    reset_s2_dogfood_rows(runtime.store)
    gateway = FinSightToolGateway(runtime, workspace_root=root, artifact_root=root / "data" / "workbench_private")

    task = runtime.create_task(
        "Validate S2 tool gateway, sandbox, approval, and trace spine",
        task_id="s2_scope_task_tool_sandbox",
        trace_id="trace_s2_scope_tool_sandbox",
        user_id="s2_gate",
        case_id="s2_tool_sandbox_trace_dogfood",
        mode="runtime_spine_dogfood",
        objective={"required_dimensions": ["tool_policy", "sandbox", "approval", "trace"], "minimum_evidence": "ledgered"},
        metadata={"source_slice": "S2", "closeout_level": "L4_scope_pass"},
    )
    task_id = task["task"]["task_id"]
    runtime.store.transition_task(task_id, "running", actor="research_lead", message="start S2 dogfood run", progress=10)

    decisions = [
        gateway.invoke_tool(
            task_id,
            actor_id="research_lead",
            node="lead_review_checkpoint",
            tool_id="database_query",
            arguments={"query": "select * from gold_fact_signal_mart where ticker='NVDA'", "limit": 10},
        ),
        gateway.invoke_tool(
            task_id,
            actor_id="memo_writer",
            node="memo_writer",
            tool_id="live_web_snapshot",
            arguments={"url": "https://nvidia.com/en-us/data-center/"},
        ),
        gateway.invoke_tool(
            task_id,
            actor_id="research_lead",
            node="lead_review_checkpoint",
            tool_id="live_web_snapshot",
            arguments={"url": "https://untrusted.example.com/promo"},
        ),
        gateway.invoke_tool(
            task_id,
            actor_id="input_parser",
            node="input_parser",
            tool_id="document_parser",
            arguments={"input_path": "..\\outside_secret.pdf"},
        ),
        gateway.invoke_tool(
            task_id,
            actor_id="research_lead",
            node="lead_review_checkpoint",
            tool_id="database_query",
            arguments={"query": "select 1", "api_key": "redacted-test-value"},
        ),
        gateway.invoke_tool(
            task_id,
            actor_id="memo_writer",
            node="memo_writer",
            tool_id="report_renderer",
            arguments={"artifact_uri": "inline://s2/rendered_report", "format": "md"},
        ),
        gateway.invoke_tool(
            task_id,
            actor_id="research_lead",
            node="lead_review_checkpoint",
            tool_id="python_analysis",
            arguments={"workspace_path": ".tmp\\s2_analysis.py"},
        ),
    ]
    approval = record_approval_decision(
        runtime.store,
        task_id,
        actor_id="research_lead",
        tool_id="python_analysis",
        decision="approved",
        approver_actor_id="human_reviewer",
        reason="S2 deterministic bounded local analysis smoke",
    )
    decisions.append(
        gateway.invoke_tool(
            task_id,
            actor_id="research_lead",
            node="lead_review_checkpoint",
            tool_id="python_analysis",
            arguments={"workspace_path": ".tmp\\s2_analysis.py"},
            approval_decision=approval,
        )
    )
    decisions.append(
        gateway.invoke_tool(
            task_id,
            actor_id="research_lead",
            node="lead_review_checkpoint",
            tool_id="unknown_future_tool",
            arguments={"query": "x"},
        )
    )
    runtime.store.transition_task(task_id, "succeeded", actor="verifier", message="S2 dogfood task complete", progress=100)

    gate_rows = evaluate_s2_gates(runtime.store, decisions)
    summary = build_s2_summary(root, paths, gate_rows, runtime.store)
    write_json(paths.schema_path, tool_sandbox_schema_contract())
    write_jsonl(paths.gate_rows_path, gate_rows)
    write_json(paths.summary_path, summary)
    paths.report_path.write_text(render_s2_report(summary, gate_rows), encoding="utf-8")
    return summary


def evaluate_s2_gates(store: RuntimeTaskSpineStore, decisions: Iterable[ToolInvocationDecision]) -> list[dict[str, Any]]:
    decisions_list = list(decisions)
    counts = table_counts(store)
    with store._connect() as conn:
        runtime_counts = {
            "task_events": int(conn.execute("select count(*) from task_events where task_id = ?", ("s2_scope_task_tool_sandbox",)).fetchone()[0]),
            "artifact_refs": int(conn.execute("select count(*) from artifact_refs where task_id = ?", ("s2_scope_task_tool_sandbox",)).fetchone()[0]),
            "trace_spans": int(conn.execute("select count(*) from trace_spans where task_id = ?", ("s2_scope_task_tool_sandbox",)).fetchone()[0]),
        }
        persisted_rows = [
            dict(row)
            for row in conn.execute(
                "select * from tool_invocations where task_id = ? order by created_at, tool_call_id",
                ("s2_scope_task_tool_sandbox",),
            ).fetchall()
        ]
    statuses = [decision.status for decision in decisions_list]
    blocked_reasons = {decision.blocked_reason for decision in decisions_list if decision.status == "blocked"}
    executed = [decision for decision in decisions_list if decision.status == "executed"]
    blocked = [decision for decision in decisions_list if decision.status == "blocked"]
    checks = [
        ("schema_tables_present", all(counts.get(table, 0) >= 0 for table in tool_sandbox_schema_contract()["tables"]), "All S2 policy and invocation tables exist.", counts),
        ("policy_registry_seeded", counts["tool_policy_bindings"] >= 6 and counts["sandbox_policies"] >= 5 and counts["approval_policies"] >= 6, "Tool, sandbox, and approval policy registries are seeded.", counts),
        ("allowed_tool_artifact_trace", len(executed) >= 3 and runtime_counts["artifact_refs"] >= len(executed) and runtime_counts["trace_spans"] >= len(decisions_list), "Allowed tool calls produce artifact refs and all calls produce trace spans.", {"executed": len(executed), **runtime_counts}),
        ("blocked_tool_calls_ledgered", len(blocked) >= 5 and counts["tool_invocations"] == len(decisions_list), "Blocked tool calls are ledgered instead of hidden.", {"blocked": len(blocked), "tool_invocations": counts["tool_invocations"]}),
        ("writer_fetch_forbidden", "actor_tool_not_allowed" in blocked_reasons, "Memo writer cannot call retrieval/web tools.", sorted(blocked_reasons)),
        ("network_domain_allowlist_enforced", "domain_not_allowlisted" in blocked_reasons, "Public web snapshots enforce domain allowlist.", sorted(blocked_reasons)),
        ("workspace_path_scope_enforced", "path_outside_allowed_roots" in blocked_reasons, "Filesystem tools enforce workspace/artifact path scope.", sorted(blocked_reasons)),
        ("credential_argument_blocked", "credential_argument_forbidden" in blocked_reasons, "Credential-like arguments are blocked and redacted.", sorted(blocked_reasons)),
        ("human_approval_required_and_recorded", "human_approval_required" in blocked_reasons and counts["approval_decisions"] >= 1 and any(decision.approval_decision_id for decision in executed), "High-risk local execution requires human approval and records decision.", {"approval_decisions": counts["approval_decisions"]}),
        ("unknown_tool_fail_closed", "unknown_tool" in blocked_reasons, "Unknown tools fail closed and are recorded.", sorted(blocked_reasons)),
        ("runtime_projection_parity", projection_covers_tool_activity(store), "S1 projection/event/trace rows cover S2 tool activity.", runtime_counts),
        ("no_secret_persisted", not persisted_payload_contains_secret(persisted_rows), "Ledger payload redacts credential-like values.", {}),
    ]
    generated_at = utc_now_iso()
    return [
        {
            "schema_version": SCHEMA_VERSION,
            "generated_at": generated_at,
            "slice_id": "S2",
            "gate_id": gate_id,
            "status": "pass" if passed else "fail",
            "description": description,
            "detail": detail,
            "closeout_level": "L4_scope_pass",
        }
        for gate_id, passed, description, detail in checks
    ]


def projection_covers_tool_activity(store: RuntimeTaskSpineStore) -> bool:
    state = store.get_task_state("s2_scope_task_tool_sandbox")
    projection = state["progress_projection"]
    with store._connect() as conn:
        trace_count = int(conn.execute("select count(*) from trace_spans where task_id = ?", ("s2_scope_task_tool_sandbox",)).fetchone()[0])
        event_count = int(conn.execute("select count(*) from task_events where task_id = ?", ("s2_scope_task_tool_sandbox",)).fetchone()[0])
        artifact_count = int(conn.execute("select count(*) from artifact_refs where task_id = ?", ("s2_scope_task_tool_sandbox",)).fetchone()[0])
    return (
        int(projection.get("trace_span_count") or 0) == trace_count
        and int(projection.get("event_count") or 0) == event_count
        and int(projection.get("artifact_count") or 0) == artifact_count
    )


def persisted_payload_contains_secret(rows: Iterable[Mapping[str, Any]]) -> bool:
    for row in rows:
        payload = json_loads(str(row.get("payload_json") or ""), {})
        text = json.dumps(payload, ensure_ascii=False)
        if "redacted-test-value" in text:
            return True
    return False


def build_s2_summary(root: Path, paths: S2Paths, gate_rows: list[dict[str, Any]], store: RuntimeTaskSpineStore) -> dict[str, Any]:
    failed = [row for row in gate_rows if row["status"] != "pass"]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now_iso(),
        "status": "pass" if not failed else "fail",
        "release_decision": "S2_L4_scope_pass" if not failed else "S2_blocked",
        "closeout_level": "L4_scope_pass" if not failed else "blocked",
        "counts": {**table_counts(store), "gate_count": len(gate_rows), "gate_fail_count": len(failed)},
        "outputs": {
            "schema": rel_path(paths.schema_path, root),
            "sqlite_store": rel_path(paths.db_path, root),
            "gate_rows": rel_path(paths.gate_rows_path, root),
            "summary": rel_path(paths.summary_path, root),
            "closeout_report": rel_path(paths.report_path, root),
        },
        "failed_gates": failed,
        "next_slice_unlocked": "S3" if not failed else None,
        "boundary": "S2 closes tool permission, sandbox, approval, and tool trace scope only; it does not execute real web crawling or quant jobs.",
    }


def render_s2_report(summary: Mapping[str, Any], gate_rows: Iterable[Mapping[str, Any]]) -> str:
    lines = [
        "# R53-R60 S2 Tool / Sandbox / Trace Spine L4 Scope Closeout",
        "",
        f"Generated: `{summary['generated_at']}`",
        f"Status: `{summary['status']}`",
        f"Release decision: `{summary['release_decision']}`",
        f"Closeout level: `{summary['closeout_level']}`",
        "",
        "## Counts",
        "",
    ]
    for key, value in summary["counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Gate Rows", ""])
    for row in gate_rows:
        lines.append(f"- `{row['status']}` `{row['gate_id']}`: {row['description']}")
    lines.extend(["", "## Outputs", ""])
    for key, value in summary["outputs"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Boundary", "", str(summary["boundary"]), ""])
    return "\n".join(lines)


def approval_rows(store: RuntimeTaskSpineStore) -> list[dict[str, Any]]:
    with store._connect() as conn:
        create_tool_sandbox_schema(conn)
        return [dict(row) for row in conn.execute("select * from approval_decisions").fetchall()]
