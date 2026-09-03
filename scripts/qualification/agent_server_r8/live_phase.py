"""Container-side phases for the bounded Dell Agent Server r8 qualification.

This module is deliberately an acceptance probe, not another runtime.  It uses
the checked-in ``DellAgentServerClient`` and FIN PostgreSQL identity repository
against the one Agent Server deployment.  Input arrives as one immutable JSON
manifest on stdin; stdout contains one content-minimised JSON result.

The probe never prints graph state, tool results, source locators, credentials,
or LangSmith span bodies.  It retains only identifiers, counters and digests.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from hashlib import sha256
import json
import os
import sys
import time
from typing import Any, Literal
from uuid import UUID

from langgraph_sdk import get_sync_client
from langgraph_sdk.schema import StreamPart
from langsmith import Client as LangSmithClient
from psycopg_pool import ConnectionPool

from sec_agent.agent_runtime.dell_agent_server_client import (
    DELL_AGENT_SERVER_ASSISTANT_ID,
    DELL_AGENT_SERVER_CLIENT_SCHEMA_VERSION,
    DellAgentServerClient,
    DellAgentServerClientError,
    DellAgentServerRunBinding,
    DellAgentServerSessionBinding,
)
from sec_agent.agent_runtime.dell_agent_server_identity import (
    DellAgentServerIdentityStoreError,
    PostgresDellAgentServerIdentityRepository,
    agent_session_identity_digest,
    research_run_identity_digest,
    run_invocation_identity_digest,
)
from sec_agent.agent_runtime.dell_reference_vertical_contracts import (
    canonical_sha256,
)
from sec_agent.agent_runtime.dell_zero_model_graph_qualification import (
    SafeZeroModelQualificationDecision,
    ZERO_MODEL_EXECUTION_PROFILE,
    ZeroModelQualificationSummary,
)
from sec_agent.canonical_runtime.contracts_v1_2 import (
    AgentSessionV1_2,
    ResearchRun,
    RunInvocation,
)


MANIFEST_SCHEMA_VERSION = "fin_ia_dell_agent_server_live_r8_manifest_v1_0"
PHASE_RESULT_SCHEMA_VERSION = "fin_ia_dell_agent_server_live_r8_phase_v1_0"
LANGSMITH_PROJECT = "fin-insight-dell-reference-vertical"
AGENT_SERVER_URL = "http://127.0.0.1:8000"
FIN_RUNTIME_URI_ENV = "FIN_RUNTIME_POSTGRES_URI"
_PHASES = ("start", "readback", "resume", "final", "langsmith")
_FORBIDDEN_SAFE_OUTPUT_FRAGMENTS = (
    "bounded_excerpt",
    "source_url",
    "citation_urls",
    "value_decimal",
    "postgres://",
    "postgresql://",
    "redis://",
    "D:/",
    "D:\\",
    "Z:/",
    "Z:\\",
    "/run/fin-insight",
    "/deps/FIN_Insight_Agent",
)


class LivePhaseError(RuntimeError):
    """Stable, secret-free failure boundary for the qualification process."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError):
        raise LivePhaseError("r8_non_json_value") from None


def _digest(value: Any) -> str:
    return sha256(_canonical_bytes(value)).hexdigest()


def _required_string(value: Any, code: str, *, maximum: int = 512) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > maximum
    ):
        raise LivePhaseError(code)
    return value


def _required_uuid(value: Any, code: str) -> str:
    identifier = _required_string(value, code)
    try:
        parsed = UUID(identifier)
    except (TypeError, ValueError, AttributeError):
        raise LivePhaseError(code) from None
    if str(parsed) != identifier.lower():
        raise LivePhaseError(code)
    return identifier


def _load_manifest() -> dict[str, Any]:
    try:
        raw = sys.stdin.buffer.read()
        if not raw or len(raw) > 256_000:
            raise ValueError
        value = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        raise LivePhaseError("r8_manifest_invalid") from None
    if not isinstance(value, dict):
        raise LivePhaseError("r8_manifest_invalid")
    expected_keys = {
        "schema_version",
        "attempt_id",
        "compose_project",
        "git_commit",
        "trace_window_start_utc",
        "agent_session",
        "research_run",
        "start_invocation",
        "resume_invocation",
        "graph_input",
        "resume_payload",
    }
    if set(value) != expected_keys:
        raise LivePhaseError("r8_manifest_shape_invalid")
    if value["schema_version"] != MANIFEST_SCHEMA_VERSION:
        raise LivePhaseError("r8_manifest_schema_invalid")
    _required_string(value["attempt_id"], "r8_attempt_id_invalid", maximum=160)
    _required_string(
        value["compose_project"], "r8_compose_project_invalid", maximum=160
    )
    commit = _required_string(value["git_commit"], "r8_git_commit_invalid")
    if len(commit) != 40 or any(char not in "0123456789abcdef" for char in commit):
        raise LivePhaseError("r8_git_commit_invalid")
    try:
        parsed_start = datetime.fromisoformat(
            str(value["trace_window_start_utc"]).replace("Z", "+00:00")
        )
    except ValueError:
        raise LivePhaseError("r8_trace_window_invalid") from None
    if parsed_start.tzinfo is None or parsed_start.utcoffset() is None:
        raise LivePhaseError("r8_trace_window_invalid")
    return value


def _contract(model: type[Any], value: Any, code: str) -> Any:
    try:
        return model.model_validate_json(_canonical_bytes(value))
    except Exception:
        raise LivePhaseError(code) from None


def _manifest_contracts(
    manifest: Mapping[str, Any],
) -> tuple[AgentSessionV1_2, ResearchRun, RunInvocation, RunInvocation]:
    session = _contract(
        AgentSessionV1_2,
        manifest["agent_session"],
        "r8_agent_session_contract_invalid",
    )
    research_run = _contract(
        ResearchRun,
        manifest["research_run"],
        "r8_research_run_contract_invalid",
    )
    start = _contract(
        RunInvocation,
        manifest["start_invocation"],
        "r8_start_invocation_contract_invalid",
    )
    resume = _contract(
        RunInvocation,
        manifest["resume_invocation"],
        "r8_resume_invocation_contract_invalid",
    )
    if (
        research_run.session_id != session.session_id
        or start.session_id != session.session_id
        or resume.session_id != session.session_id
        or start.run_id != research_run.run_id
        or resume.run_id != research_run.run_id
        or start.ordinal != 1
        or start.invocation_kind != "START"
        or resume.ordinal != 2
        or resume.invocation_kind != "RESUME"
    ):
        raise LivePhaseError("r8_contract_lineage_invalid")
    return session, research_run, start, resume


def _require_container_environment() -> str:
    if os.environ.get("FINSIGHT_DELL_EXECUTION_PROFILE") != (
        ZERO_MODEL_EXECUTION_PROFILE
    ):
        raise LivePhaseError("r8_execution_profile_mismatch")
    if os.environ.get("LANGSMITH_PROJECT") != LANGSMITH_PROJECT:
        raise LivePhaseError("r8_langsmith_project_mismatch")
    if os.environ.get("LANGSMITH_TRACING", "").strip().lower() != "true":
        raise LivePhaseError("r8_langsmith_tracing_missing")
    if os.environ.get("LANGSMITH_HIDE_INPUTS", "").strip().lower() != "true":
        raise LivePhaseError("r8_langsmith_inputs_not_hidden")
    if os.environ.get("LANGSMITH_HIDE_OUTPUTS", "").strip().lower() != "true":
        raise LivePhaseError("r8_langsmith_outputs_not_hidden")
    if os.environ.get("DEEPSEEK_API_KEY"):
        raise LivePhaseError("r8_model_key_injected")
    uri = os.environ.get(FIN_RUNTIME_URI_ENV, "").strip()
    if not uri:
        raise LivePhaseError("r8_fin_runtime_uri_missing")
    return uri


def _assistant_uuid() -> str:
    sdk = get_sync_client(url=AGENT_SERVER_URL)
    try:
        rows = sdk.assistants.search(
            graph_id=DELL_AGENT_SERVER_ASSISTANT_ID,
            limit=2,
            offset=0,
        )
    except Exception:
        raise LivePhaseError("r8_assistant_search_failed") from None
    finally:
        sdk.close()
    if not isinstance(rows, list) or len(rows) != 1:
        raise LivePhaseError("r8_assistant_resolution_not_unique")
    row = rows[0]
    if not isinstance(row, Mapping):
        raise LivePhaseError("r8_assistant_response_invalid")
    if row.get("graph_id") != DELL_AGENT_SERVER_ASSISTANT_ID:
        raise LivePhaseError("r8_assistant_graph_mismatch")
    return _required_uuid(row.get("assistant_id"), "r8_assistant_uuid_invalid")


def _stream_projection(parts: Iterable[StreamPart]) -> list[dict[str, Any]]:
    projection: list[dict[str, Any]] = []
    for part in parts:
        data_bytes = _canonical_bytes(part.data)
        projection.append(
            {
                "id": part.id,
                "event": part.event,
                "data_bytes": len(data_bytes),
                "data_sha256": sha256(data_bytes).hexdigest(),
            }
        )
    if not projection:
        raise LivePhaseError("r8_stream_empty")
    end_indexes = [
        index for index, row in enumerate(projection) if row["event"] == "end"
    ]
    if end_indexes and end_indexes != [len(projection) - 1]:
        raise LivePhaseError("r8_stream_end_not_terminal")
    return projection


def _join_and_verify_replay(
    client: DellAgentServerClient,
    run: DellAgentServerRunBinding,
) -> dict[str, Any]:
    full = _stream_projection(client.join_updates(run, last_event_id="-1"))
    cursor_candidates = [
        (index, row["id"])
        for index, row in enumerate(full)
        if row["event"] != "end" and isinstance(row["id"], str)
    ]
    if len(cursor_candidates) < 2:
        raise LivePhaseError("r8_stream_replay_window_too_small")
    cursor_index, cursor = cursor_candidates[0]
    suffix = _stream_projection(client.join_updates(run, last_event_id=cursor))
    if not suffix:
        raise LivePhaseError("r8_stream_suffix_empty")
    if suffix != full[cursor_index + 1 :]:
        raise LivePhaseError("r8_stream_suffix_replay_mismatch")
    return {
        "full": full,
        "full_digest": _digest(full),
        "cursor": cursor,
        "suffix": suffix,
        "suffix_digest": _digest(suffix),
    }


def _walk_mappings(value: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        yield value
        for child in value.values():
            yield from _walk_mappings(child)
    elif isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        for child in value:
            yield from _walk_mappings(child)


def _safe_state(
    raw_state: Mapping[str, Any],
    *,
    expected_phase: Literal[
        "zero_model_mcp_qualified",
        "zero_model_control_plane_completed",
    ],
) -> dict[str, Any]:
    values = raw_state.get("values")
    if not isinstance(values, Mapping):
        raise LivePhaseError("r8_state_values_invalid")
    if values.get("execution_profile") != ZERO_MODEL_EXECUTION_PROFILE:
        raise LivePhaseError("r8_state_profile_mismatch")
    if values.get("phase") != expected_phase:
        raise LivePhaseError("r8_state_phase_mismatch")
    if values.get("final_report") is not None:
        raise LivePhaseError("r8_final_report_forbidden")
    summary = _contract(
        ZeroModelQualificationSummary,
        values.get("zero_model_qualification_summary"),
        "r8_qualification_summary_invalid",
    )
    if (
        summary.tool_lane_execution_count != 2
        or summary.mcp_call_count <= 0
        or summary.mcp_error_call_count != 0
        or sum(summary.mcp_tool_call_counts.values()) != summary.mcp_call_count
        or summary.model_call_count != 0
        or summary.live_external_research_call_count != 0
        or summary.paid_call_count != 0
    ):
        raise LivePhaseError("r8_qualification_counter_mismatch")

    interrupts = raw_state.get("interrupts")
    if not isinstance(interrupts, list):
        raise LivePhaseError("r8_state_interrupts_invalid")
    next_nodes = raw_state.get("next")
    if (
        not isinstance(next_nodes, Sequence)
        or isinstance(next_nodes, (str, bytes, bytearray))
        or any(not isinstance(item, str) or not item for item in next_nodes)
    ):
        raise LivePhaseError("r8_state_next_invalid")
    next_nodes = list(next_nodes)
    interrupt_contracts = [
        item
        for item in _walk_mappings(interrupts)
        if item.get("kind") == "dell_zero_model_control_plane_qualification"
    ]
    decision_value = values.get("zero_model_qualification_decision")
    if expected_phase == "zero_model_mcp_qualified":
        if (
            len(interrupt_contracts) != 1
            or decision_value is not None
            or next_nodes != ["qualification_interrupt"]
        ):
            raise LivePhaseError("r8_interrupt_contract_invalid")
    else:
        if interrupts or interrupt_contracts or next_nodes:
            raise LivePhaseError("r8_completed_state_still_interrupted")
        _contract(
            SafeZeroModelQualificationDecision,
            decision_value,
            "r8_qualification_decision_invalid",
        )

    safe = {
        "raw_state_sha256": _digest(raw_state),
        "phase": expected_phase,
        "execution_profile": ZERO_MODEL_EXECUTION_PROFILE,
        "interrupt_count": len(interrupts),
        "interrupt_kind": (
            "dell_zero_model_control_plane_qualification"
            if interrupt_contracts
            else None
        ),
        "next_nodes": next_nodes,
        "qualification_summary": summary.model_dump(mode="json"),
        "qualification_summary_sha256": canonical_sha256(summary),
        "decision": (
            None
            if decision_value is None
            else SafeZeroModelQualificationDecision.model_validate(
                decision_value
            ).model_dump(mode="json")
        ),
    }
    _require_safe_output(safe)
    return safe


def _remote_snapshot(
    *,
    server_thread_id: str,
    expected_assistant_uuid: str,
    expected_invocation_ids: set[str],
) -> dict[str, Any]:
    sdk = get_sync_client(url=AGENT_SERVER_URL)
    try:
        try:
            rows = sdk.runs.list(
                server_thread_id,
                limit=100,
                offset=0,
                select=[
                    "run_id",
                    "thread_id",
                    "assistant_id",
                    "status",
                    "metadata",
                ],
            )
        except Exception:
            raise LivePhaseError("r8_remote_run_list_failed") from None
        try:
            thread = sdk.threads.get(server_thread_id)
        except Exception:
            raise LivePhaseError("r8_remote_thread_get_failed") from None
    finally:
        sdk.close()
    if not isinstance(rows, list):
        raise LivePhaseError("r8_remote_run_list_invalid")
    if not isinstance(thread, Mapping):
        raise LivePhaseError("r8_remote_thread_invalid")
    if thread.get("thread_id") != server_thread_id:
        raise LivePhaseError("r8_remote_thread_identity_mismatch")
    thread_status = _required_string(
        thread.get("status"), "r8_remote_thread_status_invalid", maximum=80
    )
    selected: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise LivePhaseError("r8_remote_run_row_invalid")
        metadata = row.get("metadata")
        if not isinstance(metadata, Mapping):
            continue
        invocation_id = metadata.get("run_invocation_id")
        if invocation_id not in expected_invocation_ids:
            continue
        if row.get("thread_id") != server_thread_id:
            raise LivePhaseError("r8_remote_thread_identity_mismatch")
        if row.get("assistant_id") != expected_assistant_uuid:
            raise LivePhaseError("r8_remote_assistant_identity_mismatch")
        if metadata.get("execution_profile") != ZERO_MODEL_EXECUTION_PROFILE:
            raise LivePhaseError("r8_remote_profile_mismatch")
        selected.append(
            {
                "run_id": _required_uuid(
                    row.get("run_id"), "r8_remote_run_uuid_invalid"
                ),
                "thread_id": server_thread_id,
                "assistant_id": expected_assistant_uuid,
                "status": _required_string(
                    row.get("status"), "r8_remote_run_status_invalid", maximum=80
                ),
                "run_invocation_id": invocation_id,
                "metadata_sha256": _digest(metadata),
            }
        )
    if {row["run_invocation_id"] for row in selected} != expected_invocation_ids:
        raise LivePhaseError("r8_remote_invocation_set_mismatch")
    if len(selected) != len(expected_invocation_ids):
        raise LivePhaseError("r8_remote_invocation_duplicate")
    return {
        "thread": {
            "thread_id": server_thread_id,
            "status": thread_status,
        },
        "selected_run_count": len(selected),
        "runs": sorted(selected, key=lambda row: row["run_invocation_id"]),
        "all_thread_run_count": len(rows),
    }


def _identity_snapshot(
    repository: PostgresDellAgentServerIdentityRepository,
    research_run: ResearchRun,
    expected_invocation_ids: Sequence[str],
) -> dict[str, Any]:
    aggregate = repository.get_research_run_aggregate(
        research_run_id=research_run.run_id
    )
    if aggregate is None:
        raise LivePhaseError("r8_fin_aggregate_missing")
    observed_ids = [item.run_invocation_id for item in aggregate.invocations]
    if observed_ids != list(expected_invocation_ids):
        raise LivePhaseError("r8_fin_invocation_set_mismatch")
    return {
        "research_run_id": aggregate.research_run.research_run_id,
        "agent_session_id": aggregate.research_run.agent_session_id,
        "invocation_count": len(aggregate.invocations),
        "invocation_ordinals": [
            item.invocation_ordinal for item in aggregate.invocations
        ],
        "server_run_ids": [item.server_run_id for item in aggregate.invocations],
        "server_thread_ids": sorted(
            {item.server_thread_id for item in aggregate.invocations}
        ),
    }


def _run_projection(binding: DellAgentServerRunBinding) -> dict[str, Any]:
    return {
        "agent_session_id": binding.agent_session_id,
        "research_run_id": binding.research_run_id,
        "run_invocation_id": binding.run_invocation_id,
        "server_thread_id": binding.server_thread_id,
        "server_run_id": binding.server_run_id,
        "invocation_kind": binding.invocation_kind,
        "execution_profile": binding.execution_profile,
    }


def _phase_runtime(manifest: Mapping[str, Any], phase: str) -> dict[str, Any]:
    runtime_uri = _require_container_environment()
    session, research_run, start, resume = _manifest_contracts(manifest)
    graph_input = manifest["graph_input"]
    resume_payload = manifest["resume_payload"]
    if not isinstance(graph_input, Mapping) or not isinstance(
        resume_payload, Mapping
    ):
        raise LivePhaseError("r8_runtime_payload_invalid")

    assistant_uuid = _assistant_uuid()
    with ConnectionPool(
        runtime_uri,
        min_size=1,
        max_size=2,
        open=True,
        timeout=10,
    ) as pool:
        pool.wait(timeout=10)
        repository = PostgresDellAgentServerIdentityRepository(pool)
        with DellAgentServerClient.connect(
            url=AGENT_SERVER_URL,
            identity_repository=repository,
            execution_profile=ZERO_MODEL_EXECUTION_PROFILE,
        ) as client:
            session_binding = client.create_agent_session(agent_session=session)
            start_binding = client.start_run(
                session=session_binding,
                research_run=research_run,
                run_invocation=start,
                graph_input=graph_input,
            )

            if phase in {"start", "readback"}:
                stream = _join_and_verify_replay(client, start_binding)
                state = _safe_state(
                    client.get_state(session_binding),
                    expected_phase="zero_model_mcp_qualified",
                )
                expected_ids = [start.invocation_id]
                bindings = {"start": _run_projection(start_binding)}
            elif phase == "resume":
                before = _safe_state(
                    client.get_state(session_binding),
                    expected_phase="zero_model_mcp_qualified",
                )
                resume_binding = client.resume_run(
                    prior_run=start_binding,
                    research_run=research_run,
                    run_invocation=resume,
                    resume_payload=resume_payload,
                )
                stream = _join_and_verify_replay(client, resume_binding)
                state = _safe_state(
                    client.get_state(session_binding),
                    expected_phase="zero_model_control_plane_completed",
                )
                if (
                    before["qualification_summary_sha256"]
                    != state["qualification_summary_sha256"]
                ):
                    raise LivePhaseError("r8_resume_reexecuted_qualification")
                if start_binding.server_run_id == resume_binding.server_run_id:
                    raise LivePhaseError("r8_resume_server_run_not_new")
                expected_ids = [start.invocation_id, resume.invocation_id]
                bindings = {
                    "start": _run_projection(start_binding),
                    "resume": _run_projection(resume_binding),
                }
            else:  # final: exact replay after the graph is already complete
                resume_binding = client.resume_run(
                    prior_run=start_binding,
                    research_run=research_run,
                    run_invocation=resume,
                    resume_payload=resume_payload,
                )
                stream = _join_and_verify_replay(client, resume_binding)
                state = _safe_state(
                    client.get_state(session_binding),
                    expected_phase="zero_model_control_plane_completed",
                )
                if start_binding.server_run_id == resume_binding.server_run_id:
                    raise LivePhaseError("r8_resume_server_run_not_new")
                expected_ids = [start.invocation_id, resume.invocation_id]
                bindings = {
                    "start": _run_projection(start_binding),
                    "resume": _run_projection(resume_binding),
                }

        identity = _identity_snapshot(repository, research_run, expected_ids)

    remote = _remote_snapshot(
        server_thread_id=session_binding.server_thread_id,
        expected_assistant_uuid=assistant_uuid,
        expected_invocation_ids=set(expected_ids),
    )
    remote_statuses = {
        row["run_invocation_id"]: row["status"] for row in remote["runs"]
    }
    # Agent Server 0.13.3 commits a dynamic interrupt as a successful Run.
    # The resumable wait is represented by the Thread and current-state
    # checkpoint, not by Run.status.
    expected_remote_statuses = {start.invocation_id: "success"}
    if phase in {"resume", "final"}:
        expected_remote_statuses[resume.invocation_id] = "success"
    if remote_statuses != expected_remote_statuses:
        raise LivePhaseError("r8_remote_terminal_status_mismatch")
    expected_thread_status = (
        "interrupted" if phase in {"start", "readback"} else "idle"
    )
    if remote["thread"]["status"] != expected_thread_status:
        raise LivePhaseError("r8_remote_thread_status_mismatch")
    result = {
        "schema_version": PHASE_RESULT_SCHEMA_VERSION,
        "phase": phase,
        "manifest_sha256": _digest(manifest),
        "assistant_uuid": assistant_uuid,
        "session": {
            "agent_session_id": session_binding.agent_session_id,
            "server_thread_id": session_binding.server_thread_id,
        },
        "bindings": bindings,
        "identity": identity,
        "remote": remote,
        "stream": stream,
        "state": state,
        "observed_calls": {
            "model_provider_calls": 0,
            "live_external_research_calls": 0,
            "research_data_provider_paid_calls": 0,
            "langsmith_observability_egress_expected": True,
        },
    }
    _require_safe_output(result)
    return result


def _metadata(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    metadata = value.get("metadata")
    return metadata if isinstance(metadata, Mapping) else {}


def _span_safe_projection(run: Any) -> dict[str, Any]:
    return {
        "run_id": str(run.id),
        "trace_id": str(run.trace_id),
        "parent_run_id": None if run.parent_run_id is None else str(run.parent_run_id),
        "name": str(run.name),
        "run_type": str(run.run_type),
        "start_time": run.start_time.isoformat(),
        "end_time": None if run.end_time is None else run.end_time.isoformat(),
        "inputs_hidden": run.inputs in ({}, None),
        "outputs_hidden": run.outputs in ({}, None),
        "error_free": run.error is None,
        "prompt_tokens": run.prompt_tokens or 0,
        "completion_tokens": run.completion_tokens or 0,
        "total_tokens": run.total_tokens or 0,
        "total_cost": float(run.total_cost or 0),
    }


_LANGSMITH_RUN_SELECT = (
    "id",
    "trace_id",
    "parent_run_id",
    "dotted_order",
    "name",
    "run_type",
    "start_time",
    "end_time",
    "error",
    "inputs",
    "outputs",
    "extra",
    "tags",
    "events",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "total_cost",
)


def _durable_server_run_ids(
    runtime_uri: str,
    research_run: ResearchRun,
    expected_invocation_ids: Sequence[str],
) -> dict[str, str]:
    try:
        with ConnectionPool(
            runtime_uri,
            min_size=1,
            max_size=2,
            open=True,
            timeout=10,
        ) as pool:
            pool.wait(timeout=10)
            repository = PostgresDellAgentServerIdentityRepository(pool)
            aggregate = repository.get_research_run_aggregate(
                research_run_id=research_run.run_id
            )
    except DellAgentServerIdentityStoreError:
        raise
    except Exception:
        raise LivePhaseError("r8_fin_identity_trace_read_failed") from None
    if aggregate is None:
        raise LivePhaseError("r8_fin_aggregate_missing")
    by_invocation = {
        row.run_invocation_id: _required_uuid(
            row.server_run_id,
            "r8_fin_server_run_uuid_invalid",
        )
        for row in aggregate.invocations
    }
    expected = list(expected_invocation_ids)
    if list(by_invocation) != expected or len(set(by_invocation.values())) != len(
        expected
    ):
        raise LivePhaseError("r8_fin_trace_invocation_set_mismatch")
    return by_invocation


def _langsmith_result(manifest: Mapping[str, Any]) -> dict[str, Any]:
    runtime_uri = _require_container_environment()
    session, research_run, start, resume = _manifest_contracts(manifest)
    window_start = datetime.fromisoformat(
        str(manifest["trace_window_start_utc"]).replace("Z", "+00:00")
    )
    invocation_order = (start.invocation_id, resume.invocation_id)
    wanted = set(invocation_order)
    trace_ids = _durable_server_run_ids(
        runtime_uri,
        research_run,
        invocation_order,
    )
    expected_invocation_by_run = {
        server_run_id: invocation_id
        for invocation_id, server_run_id in trace_ids.items()
    }
    client = LangSmithClient(auto_batch_tracing=False)
    delays = (0, 2, 3, 5, 10, 15, 20)
    matched: dict[str, list[Any]] = {}
    root_runs: list[Any] = []
    for delay in delays:
        if delay:
            time.sleep(delay)
        try:
            root_runs = list(
                client.list_runs(
                    project_name=LANGSMITH_PROJECT,
                    start_time=window_start,
                    is_root=True,
                    run_ids=list(expected_invocation_by_run),
                    select=_LANGSMITH_RUN_SELECT,
                    limit=500,
                )
            )
        except Exception:
            if delay == delays[-1]:
                raise LivePhaseError("r8_langsmith_query_failed") from None
            continue
        matched = {invocation_id: [] for invocation_id in wanted}
        for run in root_runs:
            root_id = str(run.id)
            if root_id not in expected_invocation_by_run:
                raise LivePhaseError("r8_langsmith_unexpected_root_trace")
            if str(run.trace_id) != root_id or run.parent_run_id is not None:
                raise LivePhaseError(
                    "r8_langsmith_root_server_run_identity_mismatch"
                )
            metadata = _metadata(run.extra)
            invocation_id = expected_invocation_by_run[root_id]
            invocation = start if invocation_id == start.invocation_id else resume
            expected_metadata = {
                "fin_client_schema_version": DELL_AGENT_SERVER_CLIENT_SCHEMA_VERSION,
                "execution_profile": ZERO_MODEL_EXECUTION_PROFILE,
                "agent_session_id": session.session_id,
                "research_run_id": research_run.run_id,
                "run_invocation_id": invocation_id,
                "session_identity_digest": agent_session_identity_digest(session),
                "research_run_identity_digest": research_run_identity_digest(
                    research_run
                ),
                "run_invocation_identity_digest": run_invocation_identity_digest(
                    invocation
                ),
            }
            if any(
                metadata.get(key) != value
                for key, value in expected_metadata.items()
            ):
                raise LivePhaseError("r8_langsmith_root_metadata_mismatch")
            matched[invocation_id].append(run)
        if any(len(rows) > 1 for rows in matched.values()):
            raise LivePhaseError("r8_langsmith_root_trace_not_unique")
        if all(
            len(matched[invocation_id]) == 1
            and matched[invocation_id][0].end_time is not None
            for invocation_id in wanted
        ):
            break
    if not matched or not all(
        len(matched[invocation_id]) == 1 for invocation_id in wanted
    ):
        raise LivePhaseError("r8_langsmith_trace_identity_missing")
    if any(matched[invocation_id][0].end_time is None for invocation_id in wanted):
        raise LivePhaseError("r8_langsmith_root_trace_incomplete")
    if any(matched[invocation_id][0].error is not None for invocation_id in wanted):
        raise LivePhaseError("r8_langsmith_root_trace_error")

    for invocation_id, rows in matched.items():
        if str(rows[0].id) != trace_ids[invocation_id]:
            raise LivePhaseError("r8_langsmith_trace_identity_ambiguous")

    stable_span_sets: dict[str, tuple[tuple[str, str, str], ...]] | None = None
    spans_by_trace: dict[str, list[Any]] = {}
    for delay in delays:
        if delay:
            time.sleep(delay)
        current_spans: dict[str, list[Any]] = {}
        query_failed = False
        try:
            for trace_id in trace_ids.values():
                current_spans[trace_id] = list(
                    client.list_runs(
                        project_name=LANGSMITH_PROJECT,
                        trace_id=trace_id,
                        select=_LANGSMITH_RUN_SELECT,
                        limit=500,
                    )
                )
        except Exception:
            query_failed = True
        if query_failed:
            if delay == delays[-1]:
                raise LivePhaseError("r8_langsmith_query_failed") from None
            stable_span_sets = None
            continue
        if any(not rows for rows in current_spans.values()) or any(
            row.end_time is None
            for rows in current_spans.values()
            for row in rows
        ):
            stable_span_sets = None
            continue
        signatures = {
            trace_id: tuple(
                sorted(
                    (
                        str(row.id),
                        row.end_time.isoformat(),
                        str(row.dotted_order),
                    )
                    for row in rows
                )
            )
            for trace_id, rows in current_spans.items()
        }
        if stable_span_sets == signatures:
            spans_by_trace = current_spans
            break
        stable_span_sets = signatures
    if not spans_by_trace:
        raise LivePhaseError("r8_langsmith_span_set_not_stable")

    trace_results: list[dict[str, Any]] = []
    for invocation_id in invocation_order:
        trace_id = trace_ids[invocation_id]
        spans = spans_by_trace[trace_id]
        trace_roots = [row for row in spans if row.parent_run_id is None]
        if len(trace_roots) != 1:
            raise LivePhaseError("r8_langsmith_root_trace_not_unique")
        span_projection = [_span_safe_projection(row) for row in spans]
        if any(row["run_type"] == "llm" for row in span_projection):
            raise LivePhaseError("r8_langsmith_llm_span_forbidden")
        if any(not row["inputs_hidden"] for row in span_projection):
            raise LivePhaseError("r8_langsmith_input_payload_visible")
        if any(not row["outputs_hidden"] for row in span_projection):
            raise LivePhaseError("r8_langsmith_output_payload_visible")
        if any(not row["error_free"] for row in span_projection):
            raise LivePhaseError("r8_langsmith_span_error")
        if any(
            row["prompt_tokens"]
            or row["completion_tokens"]
            or row["total_tokens"]
            or row["total_cost"]
            for row in span_projection
        ):
            raise LivePhaseError("r8_langsmith_model_usage_nonzero")

        # Scan queried objects only in memory.  Store neither their body nor the
        # secret values used to detect an accidental leak.
        raw_span_bytes = _canonical_bytes(
            [row.model_dump(mode="json") for row in spans]
        )
        raw_text = raw_span_bytes.decode("utf-8")
        forbidden_values = [
            value
            for name in (
                "LANGSMITH_API_KEY",
                "POSTGRES_URI",
                "FIN_RUNTIME_POSTGRES_URI",
                "REDIS_URI",
            )
            if (value := os.environ.get(name))
        ]
        if any(value in raw_text for value in forbidden_values):
            raise LivePhaseError("r8_langsmith_secret_visible")
        if any(
            fragment in raw_text
            for fragment in (
                "D:/",
                "D:\\",
                "Z:/",
                "Z:\\",
                "/run/fin-insight",
                "/deps/FIN_Insight_Agent",
                "postgres://",
                "postgresql://",
                "redis://",
            )
        ):
            raise LivePhaseError("r8_langsmith_internal_locator_visible")
        trace_results.append(
            {
                "run_invocation_id": invocation_id,
                "trace_id": trace_id,
                "root_run_id": str(trace_roots[0].id),
                "span_count": len(spans),
                "spans": sorted(span_projection, key=lambda row: row["start_time"]),
                "queried_span_set_sha256": sha256(raw_span_bytes).hexdigest(),
                "privacy_scan_passed": True,
            }
        )
    result = {
        "schema_version": PHASE_RESULT_SCHEMA_VERSION,
        "phase": "langsmith",
        "manifest_sha256": _digest(manifest),
        "project": LANGSMITH_PROJECT,
        "queried_root_count": len(root_runs),
        "queried_trace_span_count": sum(
            len(rows) for rows in spans_by_trace.values()
        ),
        "trace_count": len(trace_results),
        "traces": trace_results,
        "langsmith_observability_egress_observed": True,
        "model_provider_calls": 0,
    }
    _require_safe_output(result)
    return result


def _require_safe_output(value: Any) -> None:
    text = _canonical_bytes(value).decode("utf-8")
    if any(fragment in text for fragment in _FORBIDDEN_SAFE_OUTPUT_FRAGMENTS):
        raise LivePhaseError("r8_safe_output_contains_forbidden_content")
    for name in (
        "LANGSMITH_API_KEY",
        "POSTGRES_URI",
        "FIN_RUNTIME_POSTGRES_URI",
        "REDIS_URI",
    ):
        secret = os.environ.get(name)
        if secret and secret in text:
            raise LivePhaseError("r8_safe_output_contains_secret")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=_PHASES, required=True)
    args = parser.parse_args()
    try:
        manifest = _load_manifest()
        if args.phase == "langsmith":
            result = _langsmith_result(manifest)
        else:
            result = _phase_runtime(manifest, args.phase)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    except (
        LivePhaseError,
        DellAgentServerClientError,
        DellAgentServerIdentityStoreError,
    ) as exc:
        if isinstance(exc, DellAgentServerClientError):
            failure_code = f"r8_agent_server_client:{exc.code}"
        elif isinstance(exc, DellAgentServerIdentityStoreError):
            failure_code = f"r8_fin_identity_store:{exc.code}"
        else:
            failure_code = exc.code
        print(
            json.dumps(
                {
                    "schema_version": PHASE_RESULT_SCHEMA_VERSION,
                    "phase": args.phase,
                    "status": "failed",
                    "failure_code": failure_code,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        raise SystemExit(2) from None
    except Exception:
        print(
            json.dumps(
                {
                    "schema_version": PHASE_RESULT_SCHEMA_VERSION,
                    "phase": args.phase,
                    "status": "failed",
                    "failure_code": "r8_unclassified_failure",
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        raise SystemExit(3) from None


if __name__ == "__main__":
    main()
