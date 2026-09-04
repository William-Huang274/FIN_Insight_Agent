from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from datetime import date, datetime, timezone
from typing import Any
from uuid import NAMESPACE_URL, uuid5

import pytest
from langgraph_sdk.schema import StreamPart

from sec_agent.agent_runtime import dell_agent_server_client as client_module
from sec_agent.agent_runtime.dell_agent_server_client import (
    DELL_AGENT_SERVER_ASSISTANT_ID,
    DellAgentServerClient,
    DellAgentServerClientError,
    DellAgentServerRunBinding,
    DellAgentServerSessionBinding,
)
from sec_agent.agent_runtime.dell_agent_server_identity import (
    DellAgentServerIdentityConflict,
    PersistedAgentSessionBinding,
    PersistedExecutableRunBinding,
    PersistedResearchRunAggregate,
    PersistedResearchRunIdentity,
    PersistedRunCreateLifecycle,
    PersistedRunCreateLifecycleEvent,
    PersistedRunCreateRegistration,
    PersistedRunInvocationBinding,
    agent_session_identity_digest,
    persisted_run_binding_digest,
    research_run_identity_digest,
    run_invocation_identity_digest,
)
from sec_agent.agent_runtime.dell_agent_server_recovery import (
    DellAgentServerRecoveryCase,
    create_interrupted_source_invocation,
    create_recovery_case,
    create_recovery_required_research_run,
    create_run_create_action_ambiguous,
    create_run_create_action_applied,
    create_run_create_action_dispatched,
    create_run_create_action_failed_before_dispatch,
    create_run_create_action_intent,
)
from sec_agent.canonical_runtime.contracts_v1_2 import (
    ActionAttempt,
    AgentSessionV1_2,
    ResearchRun,
    RunInvocation,
    RecoveryDisposition,
    create_agent_session_v1_2,
    create_recovery_disposition,
    create_research_run,
    create_run_invocation,
)


THREAD_NAMESPACE = uuid5(
    NAMESPACE_URL,
    "https://fin-insight.local/dell-agent-server/session/v1",
)
THREAD_ID = str(
    uuid5(THREAD_NAMESPACE, "fin-session-001\0fin-thread-001")
)
START_RUN_ID = "01a065aa-7091-7a93-8153-7956fb32f946"
RESUME_RUN_ID = "01a065aa-7311-7e62-b147-93aca9a4ee82"
SERVER_ASSISTANT_ID = "e9afdb01-5261-5cb9-a246-9fc977b958ee"
NOW = datetime(2026, 9, 3, 2, 0, tzinfo=timezone.utc)
DIGEST_A = "a" * 64
DIGEST_B = "b" * 64
DIGEST_C = "c" * 64


class _FakeThreads:
    def __init__(self) -> None:
        self.create_calls: list[dict[str, Any]] = []
        self.get_state_calls: list[tuple[str, dict[str, Any]]] = []
        self.create_result: Any = {
            "thread_id": THREAD_ID,
            "metadata": {},
        }
        self.state_result: Any = {
            "values": {"phase": "awaiting_review"},
            "next": [],
            "checkpoint": {"thread_id": THREAD_ID},
            "metadata": {},
            "created_at": None,
            "parent_checkpoint": None,
            "tasks": [],
            "interrupts": [],
        }

    def create(self, **kwargs: Any) -> Any:
        self.create_calls.append(kwargs)
        self.create_result["thread_id"] = kwargs.get("thread_id", THREAD_ID)
        self.create_result["metadata"] = dict(kwargs["metadata"])
        return self.create_result

    def get_state(self, thread_id: str, **kwargs: Any) -> Any:
        self.get_state_calls.append((thread_id, kwargs))
        return self.state_result


class _FakeRuns:
    def __init__(self) -> None:
        self.create_calls: list[tuple[str, str, dict[str, Any]]] = []
        self.get_calls: list[tuple[str, str]] = []
        self.list_calls: list[tuple[str, dict[str, Any]]] = []
        self.join_calls: list[tuple[str, str, dict[str, Any]]] = []
        self.create_results: list[Any] = [
            {
                "thread_id": THREAD_ID,
                "run_id": START_RUN_ID,
                "assistant_id": SERVER_ASSISTANT_ID,
                "status": "pending",
            },
            {
                "thread_id": THREAD_ID,
                "run_id": RESUME_RUN_ID,
                "assistant_id": SERVER_ASSISTANT_ID,
                "status": "pending",
            },
        ]
        self.remote_runs: list[dict[str, Any]] = []
        self.raise_before_create = False
        self.raise_after_create = False
        self.emit_created_header = True
        self.hidden_list_calls_remaining = 0
        self.stream_parts: list[StreamPart] = [
            StreamPart("metadata", {"run_id": START_RUN_ID}, "100-0"),
            StreamPart("updates", {"plan": {"status": "ready"}}, "101-0"),
        ]

    def create(
        self,
        thread_id: str,
        assistant_id: str,
        **kwargs: Any,
    ) -> Any:
        self.create_calls.append((thread_id, assistant_id, kwargs))
        if self.raise_before_create:
            raise TimeoutError("simulated unknown transport outcome")
        raw = self.create_results.pop(0)
        if isinstance(raw, dict):
            result = dict(raw)
            result.setdefault("thread_id", thread_id)
            result.setdefault("assistant_id", SERVER_ASSISTANT_ID)
            result.setdefault("metadata", dict(kwargs["metadata"]))
            self.remote_runs.append(dict(result))
            callback = kwargs.get("on_run_created")
            if self.emit_created_header and callable(callback):
                callback(
                    {
                        "thread_id": result["thread_id"],
                        "run_id": result["run_id"],
                    }
                )
            if self.raise_after_create:
                raise TimeoutError("simulated response loss")
            return result
        return raw

    def get(self, thread_id: str, run_id: str) -> Any:
        self.get_calls.append((thread_id, run_id))
        for row in self.remote_runs:
            if row.get("thread_id") == thread_id and row.get("run_id") == run_id:
                return dict(row)
        raise KeyError(run_id)

    def list(self, thread_id: str, **kwargs: Any) -> list[dict[str, Any]]:
        self.list_calls.append((thread_id, dict(kwargs)))
        if self.remote_runs and self.hidden_list_calls_remaining > 0:
            self.hidden_list_calls_remaining -= 1
            return []
        offset = kwargs.get("offset", 0)
        limit = kwargs.get("limit", 10)
        rows = [row for row in self.remote_runs if row.get("thread_id") == thread_id]
        return [dict(row) for row in rows[offset : offset + limit]]

    def join_stream(
        self,
        thread_id: str,
        run_id: str,
        **kwargs: Any,
    ) -> Iterator[StreamPart]:
        self.join_calls.append((thread_id, run_id, kwargs))
        return iter(self.stream_parts)


class _FakeAssistants:
    def __init__(self) -> None:
        self.search_calls: list[dict[str, Any]] = []
        self.search_result: Any = [
            {
                "assistant_id": SERVER_ASSISTANT_ID,
                "graph_id": DELL_AGENT_SERVER_ASSISTANT_ID,
                "name": DELL_AGENT_SERVER_ASSISTANT_ID,
                "version": 1,
            }
        ]

    def search(self, **kwargs: Any) -> Any:
        self.search_calls.append(dict(kwargs))
        return self.search_result


class _FakeSdk:
    def __init__(self) -> None:
        self.assistants = _FakeAssistants()
        self.threads = _FakeThreads()
        self.runs = _FakeRuns()
        self.close_count = 0

    def close(self) -> None:
        self.close_count += 1


class _MemoryIdentityRepository:
    def __init__(self) -> None:
        self.sessions: dict[str, PersistedAgentSessionBinding] = {}
        self.runs: dict[str, PersistedResearchRunIdentity] = {}
        self.invocations: dict[str, PersistedRunInvocationBinding] = {}
        self.run_create_lifecycles: dict[
            str, PersistedRunCreateLifecycle
        ] = {}
        self.action_attempts: dict[str, dict[str, ActionAttempt]] = {}
        self.recovery_cases: dict[str, DellAgentServerRecoveryCase] = {}
        self.recovery_dispositions: dict[str, RecoveryDisposition] = {}
        self.session_bind_calls = 0
        self.begin_run_create_calls = 0
        self.orphan_record_calls = 0
        self.dispatch_record_calls = 0
        self.invocation_bind_calls = 0
        self.fail_next_orphan_record = False
        self.fail_next_invocation_bind = False

    def get_agent_session(
        self,
        *,
        agent_session_id: str,
    ) -> PersistedAgentSessionBinding | None:
        return self.sessions.get(agent_session_id)

    def bind_agent_session(
        self,
        *,
        agent_session: AgentSessionV1_2,
        server_thread_id: str,
        assistant_id: str,
    ) -> PersistedAgentSessionBinding:
        self.session_bind_calls += 1
        stored = PersistedAgentSessionBinding(
            agent_session_id=agent_session.session_id,
            fin_thread_id=agent_session.thread_id,
            server_thread_id=server_thread_id,
            assistant_id=assistant_id,
            session_identity_digest=agent_session_identity_digest(agent_session),
            bound_at=NOW,
        )
        self.sessions.setdefault(agent_session.session_id, stored)
        return self.sessions[agent_session.session_id]

    def get_run_invocation(
        self,
        *,
        run_invocation_id: str,
    ) -> PersistedRunInvocationBinding | None:
        return self.invocations.get(run_invocation_id)

    def get_run_create_lifecycle(
        self,
        *,
        run_invocation_id: str,
    ) -> PersistedRunCreateLifecycle | None:
        return self.run_create_lifecycles.get(run_invocation_id)

    def get_execution_binding_with_lifecycle(
        self,
        *,
        run_invocation_id: str,
    ) -> PersistedExecutableRunBinding | None:
        binding = self.invocations.get(run_invocation_id)
        if binding is None:
            return None
        return PersistedExecutableRunBinding(
            binding=binding,
            lifecycle=self.run_create_lifecycles.get(run_invocation_id),
        )

    def begin_run_create(
        self,
        *,
        research_run: ResearchRun,
        run_invocation: RunInvocation,
        server_thread_id: str,
        server_invocation_kind: str,
        server_assistant_id: str,
        execution_profile: str,
        launch_request_digest: str,
        server_metadata_digest: str,
        assistant_id: str,
    ) -> PersistedRunCreateRegistration:
        self.begin_run_create_calls += 1
        lifecycle = self.run_create_lifecycles.get(
            run_invocation.invocation_id
        )
        ordinal_matches = [
            item
            for item in self.run_create_lifecycles.values()
            if item.pending.research_run_id == research_run.run_id
            and item.pending.invocation_ordinal == run_invocation.ordinal
        ]
        if lifecycle is None and ordinal_matches:
            raise DellAgentServerIdentityConflict(
                "run_create_pending_identity_conflict"
            )
        if lifecycle is not None:
            pending = lifecycle.pending
            session = self.sessions[research_run.session_id]
            if (
                pending.research_run_id != research_run.run_id
                or pending.agent_session_id != research_run.session_id
                or pending.invocation_ordinal != run_invocation.ordinal
                or pending.canonical_invocation_kind
                != run_invocation.invocation_kind
                or pending.server_invocation_kind != server_invocation_kind
                or pending.server_thread_id != server_thread_id
                or pending.assistant_id != assistant_id
                or pending.server_assistant_id != server_assistant_id
                or pending.execution_profile != execution_profile
                or pending.session_identity_digest
                != session.session_identity_digest
                or pending.research_run_identity_digest
                != research_run_identity_digest(research_run)
                or pending.run_invocation_identity_digest
                != run_invocation_identity_digest(run_invocation)
                or pending.launch_request_digest != launch_request_digest
                or pending.server_metadata_digest != server_metadata_digest
            ):
                raise DellAgentServerIdentityConflict(
                    "run_create_pending_identity_conflict"
                )
            return PersistedRunCreateRegistration(
                lifecycle=lifecycle,
                created_now=False,
            )

        session = self.sessions[research_run.session_id]
        event_digest = client_module.canonical_sha256(
            {
                "state": "PENDING",
                "run_invocation_id": run_invocation.invocation_id,
                "research_run_id": research_run.run_id,
                "invocation_ordinal": run_invocation.ordinal,
                "launch_request_digest": launch_request_digest,
                "server_metadata_digest": server_metadata_digest,
            }
        )
        pending = PersistedRunCreateLifecycleEvent(
            run_invocation_id=run_invocation.invocation_id,
            lifecycle_ordinal=1,
            lifecycle_state="PENDING",
            research_run_id=research_run.run_id,
            agent_session_id=research_run.session_id,
            invocation_ordinal=run_invocation.ordinal,
            canonical_invocation_kind=run_invocation.invocation_kind,
            server_invocation_kind=server_invocation_kind,
            server_thread_id=server_thread_id,
            assistant_id=assistant_id,
            server_assistant_id=server_assistant_id,
            execution_profile=execution_profile,
            session_identity_digest=session.session_identity_digest,
            research_run_identity_digest=research_run_identity_digest(
                research_run
            ),
            run_invocation_identity_digest=run_invocation_identity_digest(
                run_invocation
            ),
            launch_request_digest=launch_request_digest,
            server_metadata_digest=server_metadata_digest,
            bound_run_invocation_id=None,
            server_run_id=None,
            server_run_status=None,
            recovery_reason_code=None,
            server_observation_digest=None,
            final_binding_digest=None,
            lifecycle_event_digest=event_digest,
            recorded_at=NOW,
        )
        lifecycle = PersistedRunCreateLifecycle(
            pending=pending,
            orphan=None,
            reconciled=None,
            dispatched=None,
            orphan_observations=(),
        )
        intent = create_run_create_action_intent(
            research_run=research_run,
            source_invocation=run_invocation,
            launch_request_digest=launch_request_digest,
        )
        self.action_attempts[run_invocation.invocation_id] = {
            "INTENT_COMMITTED": intent
        }
        self.run_create_lifecycles[run_invocation.invocation_id] = lifecycle
        return PersistedRunCreateRegistration(
            lifecycle=lifecycle,
            created_now=True,
        )

    def get_run_create_action_attempt(
        self,
        *,
        run_invocation_id: str,
        action_state: str | None = None,
    ) -> ActionAttempt | None:
        rows = self.action_attempts.get(run_invocation_id, {})
        if action_state is not None:
            return rows.get(action_state)
        for state in ("TERMINAL", "DISPATCHED", "INTENT_COMMITTED"):
            if state in rows:
                return rows[state]
        return None

    def mark_run_create_dispatched(
        self,
        *,
        run_invocation_id: str,
        pending_event_digest: str,
    ) -> PersistedRunCreateLifecycle:
        self.dispatch_record_calls += 1
        lifecycle = self.run_create_lifecycles[run_invocation_id]
        if lifecycle.pending.lifecycle_event_digest != pending_event_digest:
            raise DellAgentServerIdentityConflict(
                "run_create_pending_digest_conflict"
            )
        if "TERMINAL" in self.action_attempts[run_invocation_id]:
            raise DellAgentServerIdentityConflict(
                "run_create_action_already_terminal"
            )
        if lifecycle.dispatched is not None:
            return lifecycle
        pending = lifecycle.pending
        dispatched = replace(
            pending,
            lifecycle_ordinal=2,
            lifecycle_state="DISPATCHED",
            lifecycle_event_digest=client_module.canonical_sha256(
                {
                    "state": "DISPATCHED",
                    "pending_event_digest": pending_event_digest,
                }
            ),
        )
        self.action_attempts[run_invocation_id]["DISPATCHED"] = (
            create_run_create_action_dispatched(
                self.action_attempts[run_invocation_id]["INTENT_COMMITTED"]
            )
        )
        lifecycle = PersistedRunCreateLifecycle(
            pending=pending,
            orphan=lifecycle.orphan,
            reconciled=lifecycle.reconciled,
            dispatched=dispatched,
            orphan_observations=lifecycle.orphan_observations,
        )
        self.run_create_lifecycles[run_invocation_id] = lifecycle
        return lifecycle

    def mark_run_create_failed_before_dispatch(
        self,
        *,
        run_invocation_id: str,
        pending_event_digest: str,
    ) -> ActionAttempt:
        lifecycle = self.run_create_lifecycles[run_invocation_id]
        if (
            lifecycle.pending.lifecycle_event_digest != pending_event_digest
            or lifecycle.state != "PENDING"
        ):
            raise DellAgentServerIdentityConflict(
                "run_create_before_dispatch_terminal_transition_invalid"
            )
        actions = self.action_attempts[run_invocation_id]
        if "TERMINAL" not in actions:
            actions["TERMINAL"] = create_run_create_action_failed_before_dispatch(
                actions["INTENT_COMMITTED"], terminal_at=NOW
            )
        return actions["TERMINAL"]

    def record_run_create_orphan(
        self,
        *,
        run_invocation_id: str,
        pending_event_digest: str,
        recovery_reason_code: str,
        server_observation_digest: str,
        server_run_id: str | None = None,
        server_run_status: str | None = None,
    ) -> PersistedRunCreateLifecycle:
        self.orphan_record_calls += 1
        if self.fail_next_orphan_record:
            self.fail_next_orphan_record = False
            raise RuntimeError("simulated orphan persistence failure")
        lifecycle = self.run_create_lifecycles[run_invocation_id]
        pending = lifecycle.pending
        if pending.lifecycle_event_digest != pending_event_digest:
            raise DellAgentServerIdentityConflict(
                "run_create_pending_digest_conflict"
            )
        if lifecycle.dispatched is None:
            raise DellAgentServerIdentityConflict("run_create_dispatched_missing")
        for orphan in lifecycle.orphan_observations:
            if orphan.server_observation_digest == server_observation_digest:
                if (
                    orphan.server_run_id != server_run_id
                    or orphan.server_run_status != server_run_status
                    or orphan.recovery_reason_code != recovery_reason_code
                ):
                    raise DellAgentServerIdentityConflict(
                        "run_create_orphan_observation_conflict"
                    )
                return lifecycle
        event_digest = client_module.canonical_sha256(
            {
                "state": "ORPHAN",
                "pending_event_digest": pending_event_digest,
                "server_run_id": server_run_id,
                "server_run_status": server_run_status,
                "recovery_reason_code": recovery_reason_code,
                "server_observation_digest": server_observation_digest,
            }
        )
        orphan = PersistedRunCreateLifecycleEvent(
            run_invocation_id=pending.run_invocation_id,
            lifecycle_ordinal=3 + len(lifecycle.orphan_observations),
            lifecycle_state="ORPHAN",
            research_run_id=pending.research_run_id,
            agent_session_id=pending.agent_session_id,
            invocation_ordinal=pending.invocation_ordinal,
            canonical_invocation_kind=pending.canonical_invocation_kind,
            server_invocation_kind=pending.server_invocation_kind,
            server_thread_id=pending.server_thread_id,
            assistant_id=pending.assistant_id,
            server_assistant_id=pending.server_assistant_id,
            execution_profile=pending.execution_profile,
            session_identity_digest=pending.session_identity_digest,
            research_run_identity_digest=pending.research_run_identity_digest,
            run_invocation_identity_digest=(
                pending.run_invocation_identity_digest
            ),
            launch_request_digest=pending.launch_request_digest,
            server_metadata_digest=pending.server_metadata_digest,
            bound_run_invocation_id=None,
            server_run_id=server_run_id,
            server_run_status=server_run_status,
            recovery_reason_code=recovery_reason_code,
            server_observation_digest=server_observation_digest,
            final_binding_digest=None,
            lifecycle_event_digest=event_digest,
            recorded_at=NOW,
        )
        lifecycle = PersistedRunCreateLifecycle(
            pending=pending,
            orphan=orphan,
            reconciled=None,
            dispatched=lifecycle.dispatched,
            orphan_observations=(*lifecycle.orphan_observations, orphan),
        )
        self.run_create_lifecycles[run_invocation_id] = lifecycle
        return lifecycle

    def mark_run_create_recovery_required(
        self,
        *,
        research_run: ResearchRun,
        run_invocation: RunInvocation,
        pending_event_digest: str,
        recovery_reason_code: str,
        server_observation_digest: str,
        server_run_id: str | None = None,
        server_run_status: str | None = None,
    ) -> DellAgentServerRecoveryCase:
        existing = self.recovery_cases.get(run_invocation.invocation_id)
        if existing is not None:
            return existing
        lifecycle = self.record_run_create_orphan(
            run_invocation_id=run_invocation.invocation_id,
            pending_event_digest=pending_event_digest,
            recovery_reason_code=recovery_reason_code,
            server_observation_digest=server_observation_digest,
            server_run_id=server_run_id,
            server_run_status=server_run_status,
        )
        dispatched = self.action_attempts[run_invocation.invocation_id][
            "DISPATCHED"
        ]
        ambiguous = create_run_create_action_ambiguous(
            dispatched, terminal_at=NOW
        )
        self.action_attempts[run_invocation.invocation_id]["TERMINAL"] = ambiguous
        interrupted = create_interrupted_source_invocation(
            run_invocation,
            finished_at=NOW,
        )
        recovery_case = create_recovery_case(
            recovery_run=create_recovery_required_research_run(research_run),
            source_invocation=interrupted,
            ambiguous_action=ambiguous,
            lifecycle_event_digest=lifecycle.orphan.lifecycle_event_digest,
            recovery_reason_code=recovery_reason_code,
            server_run_id=server_run_id,
            server_run_status=server_run_status,
            opened_at=NOW,
        )
        self.recovery_cases[run_invocation.invocation_id] = recovery_case
        return recovery_case

    def get_run_create_recovery_case(
        self,
        *,
        run_invocation_id: str,
    ) -> DellAgentServerRecoveryCase | None:
        return self.recovery_cases.get(run_invocation_id)

    def get_run_create_recovery_disposition(
        self,
        *,
        run_invocation_id: str,
    ) -> RecoveryDisposition | None:
        return self.recovery_dispositions.get(run_invocation_id)

    def bind_run_invocation(
        self,
        *,
        research_run: ResearchRun,
        run_invocation: RunInvocation,
        server_thread_id: str,
        server_run_id: str,
        server_invocation_kind: str,
        first_server_status: str,
        pending_event_digest: str | None = None,
        server_observation_digest: str | None = None,
        reconciliation_reason_code: str | None = None,
        assistant_id: str = DELL_AGENT_SERVER_ASSISTANT_ID,
    ) -> PersistedRunInvocationBinding:
        self.invocation_bind_calls += 1
        if self.fail_next_invocation_bind:
            self.fail_next_invocation_bind = False
            raise RuntimeError("simulated bind failure")
        lifecycle = self.run_create_lifecycles.get(
            run_invocation.invocation_id
        )
        lifecycle_arguments = (
            pending_event_digest,
            server_observation_digest,
            reconciliation_reason_code,
        )
        if any(value is not None for value in lifecycle_arguments):
            if lifecycle is None or any(
                value is None for value in lifecycle_arguments
            ):
                raise DellAgentServerIdentityConflict(
                    "run_create_pending_missing"
                )
            if (
                lifecycle.pending.lifecycle_event_digest
                != pending_event_digest
            ):
                raise DellAgentServerIdentityConflict(
                    "run_create_pending_digest_conflict"
                )
            if (
                lifecycle.dispatched is None
                or any(
                    item.server_run_id is not None
                    and item.server_run_id != server_run_id
                    for item in lifecycle.orphan_observations
                )
            ):
                raise DellAgentServerIdentityConflict(
                    "run_create_orphan_server_run_conflict"
                )
        self.runs.setdefault(
            research_run.run_id,
            PersistedResearchRunIdentity(
                research_run_id=research_run.run_id,
                agent_session_id=research_run.session_id,
                parent_research_run_id=research_run.parent_run_id,
                run_identity_digest=research_run_identity_digest(research_run),
                first_bound_at=NOW,
            ),
        )
        stored = PersistedRunInvocationBinding(
            run_invocation_id=run_invocation.invocation_id,
            research_run_id=research_run.run_id,
            agent_session_id=research_run.session_id,
            invocation_ordinal=run_invocation.ordinal,
            canonical_invocation_kind=run_invocation.invocation_kind,
            server_invocation_kind=server_invocation_kind,
            server_thread_id=server_thread_id,
            server_run_id=server_run_id,
            assistant_id=assistant_id,
            invocation_identity_digest=run_invocation_identity_digest(
                run_invocation
            ),
            first_server_status=first_server_status,
            bound_at=NOW,
        )
        self.invocations.setdefault(run_invocation.invocation_id, stored)
        persisted = self.invocations[run_invocation.invocation_id]
        if lifecycle is not None and pending_event_digest is not None:
            if lifecycle.reconciled is not None:
                return persisted
            pending = lifecycle.pending
            terminal = self.action_attempts[run_invocation.invocation_id].get(
                "TERMINAL"
            )
            if terminal is None:
                self.action_attempts[run_invocation.invocation_id]["TERMINAL"] = (
                    create_run_create_action_applied(
                        self.action_attempts[run_invocation.invocation_id][
                            "DISPATCHED"
                        ],
                        server_run_id=server_run_id,
                        server_observation_digest=server_observation_digest,
                        terminal_at=NOW,
                    )
                )
            elif (
                terminal.outcome != "AMBIGUOUS_AFTER_DISPATCH"
                or self.recovery_dispositions.get(run_invocation.invocation_id)
                is None
                or self.recovery_dispositions[
                    run_invocation.invocation_id
                ].decision
                != "DO_NOT_RETRY"
            ):
                raise DellAgentServerIdentityConflict(
                    "run_create_action_terminal_conflict"
                )
            final_digest = persisted_run_binding_digest(persisted)
            event_digest = client_module.canonical_sha256(
                {
                    "state": "RECONCILED",
                    "pending_event_digest": pending_event_digest,
                    "server_run_id": server_run_id,
                    "server_run_status": first_server_status,
                    "reconciliation_reason_code": (
                        reconciliation_reason_code
                    ),
                    "server_observation_digest": (
                        server_observation_digest
                    ),
                    "final_binding_digest": final_digest,
                }
            )
            reconciled = PersistedRunCreateLifecycleEvent(
                run_invocation_id=pending.run_invocation_id,
                lifecycle_ordinal=3 + len(lifecycle.orphan_observations),
                lifecycle_state="RECONCILED",
                research_run_id=pending.research_run_id,
                agent_session_id=pending.agent_session_id,
                invocation_ordinal=pending.invocation_ordinal,
                canonical_invocation_kind=pending.canonical_invocation_kind,
                server_invocation_kind=pending.server_invocation_kind,
                server_thread_id=pending.server_thread_id,
                assistant_id=pending.assistant_id,
                server_assistant_id=pending.server_assistant_id,
                execution_profile=pending.execution_profile,
                session_identity_digest=pending.session_identity_digest,
                research_run_identity_digest=(
                    pending.research_run_identity_digest
                ),
                run_invocation_identity_digest=(
                    pending.run_invocation_identity_digest
                ),
                launch_request_digest=pending.launch_request_digest,
                server_metadata_digest=pending.server_metadata_digest,
                bound_run_invocation_id=pending.run_invocation_id,
                server_run_id=server_run_id,
                server_run_status=first_server_status,
                recovery_reason_code=reconciliation_reason_code,
                server_observation_digest=server_observation_digest,
                final_binding_digest=final_digest,
                lifecycle_event_digest=event_digest,
                recorded_at=NOW,
            )
            self.run_create_lifecycles[run_invocation.invocation_id] = (
                PersistedRunCreateLifecycle(
                    pending=pending,
                    orphan=lifecycle.orphan,
                    reconciled=reconciled,
                    dispatched=lifecycle.dispatched,
                    orphan_observations=lifecycle.orphan_observations,
                )
            )
        return persisted

    def get_research_run_aggregate(
        self,
        *,
        research_run_id: str,
    ) -> PersistedResearchRunAggregate | None:
        run = self.runs.get(research_run_id)
        if run is None:
            return None
        invocations = tuple(
            sorted(
                (
                    item
                    for item in self.invocations.values()
                    if item.research_run_id == research_run_id
                ),
                key=lambda item: item.invocation_ordinal,
            )
        )
        return PersistedResearchRunAggregate(
            research_run=run,
            invocations=invocations,
        )


def _client(
    sdk: _FakeSdk | None = None,
    repository: _MemoryIdentityRepository | None = None,
    *,
    prebound_session: bool = False,
) -> tuple[DellAgentServerClient, _FakeSdk]:
    actual_sdk = sdk or _FakeSdk()
    actual_repository = repository or _MemoryIdentityRepository()
    if prebound_session:
        actual_repository.bind_agent_session(
            agent_session=_agent_session_contract(),
            server_thread_id=THREAD_ID,
            assistant_id=DELL_AGENT_SERVER_ASSISTANT_ID,
        )
    return (
        DellAgentServerClient(
            actual_sdk,
            identity_repository=actual_repository,
        ),
        actual_sdk,
    )


def _agent_session_contract(**overrides: Any) -> AgentSessionV1_2:
    fields = {
        "session_id": "fin-session-001",
        "thread_id": "fin-thread-001",
        "case_id": "DELL_AI_INFRA_REFERENCE_VERTICAL",
        "case_version": "FIN_0_1_3",
        "as_of_date": date(2026, 9, 3),
        "objective_ref": "objective://dell/reference-vertical",
        "objective_digest": DIGEST_A,
        "data_snapshot_ref": "snapshot://dell/accepted-data",
        "data_snapshot_digest": DIGEST_B,
        "runtime_policy_ref": "policy://dell/runtime/v1",
        "runtime_policy_digest": DIGEST_C,
        "authority_refs": ("authority://owner/data-gate",),
        "active_plan_ref": "plan://dell/1",
        "active_plan_digest": DIGEST_A,
        "status": "ACTIVE",
        "created_at": NOW,
        "updated_at": NOW,
    }
    fields.update(overrides)
    return create_agent_session_v1_2(**fields)


def _research_run_contract(**overrides: Any) -> ResearchRun:
    session = _agent_session_contract()
    fields = {
        "run_id": "fin-research-run-001",
        "session_id": session.session_id,
        "parent_run_id": None,
        "origin_kind": "INITIAL",
        "legacy_paid_full_chain_execution_label": None,
        "status": "RUNNING",
        "base_plan_ref": session.active_plan_ref,
        "base_plan_digest": session.active_plan_digest,
        "current_plan_ref": session.active_plan_ref,
        "current_plan_digest": session.active_plan_digest,
        "last_session_sequence": 0,
        "created_at": NOW,
        "terminal_at": None,
    }
    fields.update(overrides)
    return create_research_run(**fields)


def _run_invocation_contract(
    *,
    resume: bool = False,
    **overrides: Any,
) -> RunInvocation:
    run = _research_run_contract()
    fields = {
        "invocation_id": (
            "fin-run-invocation-002" if resume else "fin-run-invocation-001"
        ),
        "session_id": run.session_id,
        "run_id": run.run_id,
        "ordinal": 2 if resume else 1,
        "invocation_kind": "RESUME" if resume else "START",
        "status": "RUNNING",
        "trigger_ref": "command://resume/2" if resume else "command://start/1",
        "lease_ref": "lease://agent-server/2" if resume else "lease://agent-server/1",
        "started_at": NOW,
        "finished_at": None,
    }
    fields.update(overrides)
    return create_run_invocation(**fields)


def _record_memory_recovery_disposition(
    repository: _MemoryIdentityRepository,
    *,
    decision: str,
    invocation_id: str = "fin-run-invocation-001",
) -> RecoveryDisposition:
    case = repository.recovery_cases[invocation_id]
    disposition = create_recovery_disposition(
        recovery_disposition_id=f"RECOVERY-DISPOSITION::{invocation_id}",
        session_id=case.research_run.session_id,
        run_id=case.research_run.run_id,
        research_run_digest=case.research_run.run_digest,
        ambiguous_action_attempt_id=case.ambiguous_action.action_attempt_id,
        ambiguous_action_attempt_digest=(
            case.ambiguous_action.action_attempt_digest
        ),
        source_run_invocation_id=case.source_invocation.invocation_id,
        source_run_invocation_digest=case.source_invocation.invocation_digest,
        investigation_receipt_refs=(
            f"receipt://operator-investigation/{invocation_id}",
        ),
        potentially_duplicate_cost=case.ambiguous_action.potentially_chargeable,
        decision=decision,
        decision_authority_ref="authority://fin-runtime-operator/test",
        next_run_invocation_id=None,
        next_run_invocation_digest=None,
        replacement_action_attempt_id=None,
        replacement_action_attempt_digest=None,
        created_at=NOW,
    )
    repository.recovery_dispositions[invocation_id] = disposition
    return disposition


def _session() -> DellAgentServerSessionBinding:
    return DellAgentServerSessionBinding(
        agent_session_id="fin-session-001",
        server_thread_id=THREAD_ID,
    )


def _start_run() -> DellAgentServerRunBinding:
    return DellAgentServerRunBinding(
        agent_session_id="fin-session-001",
        research_run_id="fin-research-run-001",
        run_invocation_id="fin-run-invocation-001",
        server_thread_id=THREAD_ID,
        server_run_id=START_RUN_ID,
        invocation_kind="start",
        server_status="pending",
    )


def _graph_input() -> dict[str, Any]:
    return {
        "run_id": "fin-research-run-001",
        "case_id": "DELL",
        "research_question": "What drives Dell AI server economics?",
        "research_as_of": "2026-09-03",
        "snapshot_id": "snapshot-001",
        "foundation_digest": "a" * 64,
    }


def _specialist_graph_input() -> dict[str, Any]:
    return {
        "schema_version": "fin_ia_dell_specialist_agentic_graph_v1_0",
        "run_id": "fin-research-run-001",
        "run_invocation_id": "fin-run-invocation-001",
        "agent_id": "specialist:Q1_ISSUER_TRUTH",
        "task": {
            "task_id": "task:q1:001",
            "case_id": "DELL_AI_INFRA_REFERENCE_VERTICAL",
            "branch_id": "Q1_ISSUER_TRUTH",
            "revision": 0,
            "priority": "high",
            "objective": "Establish the current issuer-reported operating truth.",
            "evidence_requests": [
                {
                    "minimum_route_obligation_id": (
                        "route:Q1_ISSUER_TRUTH:required-reviewed"
                    ),
                    "answer_free_intent_kind": "reviewed_evidence",
                }
            ],
            "fact_requests": [],
            "research_as_of": "2026-09-02T00:00:00Z",
            "snapshot_id": "snapshot-q1",
            "foundation_digest": "a" * 64,
            "method_digest": "b" * 64,
            "plan_digest": "c" * 64,
        },
        "required_route_obligation_ids": [
            "route:Q1_ISSUER_TRUTH:required-reviewed"
        ],
        "l0_context": {
            "owner_data_gate_decision_digest": "d" * 64,
            "source_route_catalog_digest": "e" * 64,
            "inventory_snapshot_digest": "f" * 64,
            "disclosure_runtime_state": (
                "current_state_authority_unavailable_fail_closed"
            ),
            "capability_summaries": [
                {
                    "capability_ref": "capability:dell:reviewed-evidence",
                    "purpose": "Read reviewed issuer evidence.",
                }
            ],
            "skill_summaries": [],
        },
        "max_model_turns": 8,
        "max_tool_actions": 12,
    }


def test_connect_uses_official_sdk_without_accepting_or_forwarding_a_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sdk = _FakeSdk()
    calls: list[dict[str, Any]] = []

    def fake_get_sync_client(**kwargs: Any) -> _FakeSdk:
        calls.append(kwargs)
        return sdk

    monkeypatch.setattr(client_module, "get_sync_client", fake_get_sync_client)

    connected = DellAgentServerClient.connect(
        url="http://127.0.0.1:2024",
        identity_repository=_MemoryIdentityRepository(),
        timeout=30,
    )

    assert isinstance(connected, DellAgentServerClient)
    assert calls == [{"url": "http://127.0.0.1:2024", "timeout": 30}]
    assert "api_key" not in calls[0]

    with pytest.raises(DellAgentServerClientError) as embedded_secret:
        DellAgentServerClient.connect(
            url="https://secret@example.test",
            identity_repository=_MemoryIdentityRepository(),
        )
    assert embedded_secret.value.code == "agent_server_url_credentials_forbidden"
    assert "secret" not in str(embedded_secret.value)

    for invalid_url in (
        "http://127.0.0.1:2024?token=forbidden",
        "http://127.0.0.1:2024/#fragment",
    ):
        with pytest.raises(DellAgentServerClientError) as invalid:
            DellAgentServerClient.connect(
                url=invalid_url,
                identity_repository=_MemoryIdentityRepository(),
            )
        assert invalid.value.code == "agent_server_url_invalid"


def test_connect_owns_sdk_and_context_manager_closes_it_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sdk = _FakeSdk()
    monkeypatch.setattr(
        client_module,
        "get_sync_client",
        lambda **_kwargs: sdk,
    )

    with DellAgentServerClient.connect(
        url="http://127.0.0.1:2024",
        identity_repository=_MemoryIdentityRepository(),
    ) as connected:
        assert sdk.close_count == 0
        assert isinstance(connected, DellAgentServerClient)

    assert sdk.close_count == 1
    connected.close()
    assert sdk.close_count == 1
    with pytest.raises(DellAgentServerClientError) as closed:
        connected.create_agent_session(agent_session=_agent_session_contract())
    assert closed.value.code == "agent_server_client_closed"


def test_injected_sdk_remains_caller_owned_when_wrapper_closes() -> None:
    sdk = _FakeSdk()
    client, _ = _client(sdk)

    client.close()
    client.close()

    assert sdk.close_count == 0


def test_create_agent_session_ensures_deterministic_uuid_and_binds_metadata() -> None:
    client, sdk = _client()

    binding = client.create_agent_session(agent_session=_agent_session_contract())

    assert binding == _session()
    assert sdk.threads.create_calls == [
        {
            "metadata": {
                "fin_client_schema_version": (
                    client_module.DELL_AGENT_SERVER_CLIENT_SCHEMA_VERSION
                ),
                "agent_session_id": "fin-session-001",
                "fin_thread_id": "fin-thread-001",
                "session_identity_digest": agent_session_identity_digest(
                    _agent_session_contract()
                ),
            },
            "thread_id": THREAD_ID,
            "if_exists": "do_nothing",
            "graph_id": DELL_AGENT_SERVER_ASSISTANT_ID,
        }
    ]


def test_start_run_uses_only_qualified_agent_server_options() -> None:
    client, sdk = _client(prebound_session=True)
    graph_input = _graph_input()

    run = client.start_run(
        session=_session(),
        research_run=_research_run_contract(),
        run_invocation=_run_invocation_contract(),
        graph_input=graph_input,
    )

    assert run == _start_run()
    assert len(sdk.runs.create_calls) == 1
    thread_id, assistant_id, kwargs = sdk.runs.create_calls[0]
    assert thread_id == THREAD_ID
    assert assistant_id == DELL_AGENT_SERVER_ASSISTANT_ID
    context = {
        "agent_session_id": "fin-session-001",
        "research_run_id": "fin-research-run-001",
        "run_invocation_id": "fin-run-invocation-001",
    }
    assert kwargs["input"] == graph_input
    assert kwargs["stream_mode"] == ["updates"]
    assert kwargs["stream_resumable"] is True
    assert kwargs["durability"] == "sync"
    assert kwargs["multitask_strategy"] == "reject"
    assert kwargs["if_not_exists"] == "reject"
    assert kwargs["after_seconds"] == client_module._RUN_BINDING_GRACE_SECONDS
    assert kwargs["context"] == context
    metadata = kwargs["metadata"]
    assert metadata == {
        "fin_client_schema_version": (
            client_module.DELL_AGENT_SERVER_CLIENT_SCHEMA_VERSION
        ),
        "fin_assistant_graph_id": DELL_AGENT_SERVER_ASSISTANT_ID,
        "server_assistant_uuid": SERVER_ASSISTANT_ID,
        "execution_profile": "product",
        **context,
        "invocation_ordinal": 1,
        "invocation_kind": "start",
        "session_identity_digest": agent_session_identity_digest(
            _agent_session_contract()
        ),
        "research_run_identity_digest": research_run_identity_digest(
            _research_run_contract()
        ),
        "run_invocation_identity_digest": run_invocation_identity_digest(
            _run_invocation_contract()
        ),
        "launch_request_digest": client_module.canonical_sha256(
            {
                "client_schema_version": (
                    client_module.DELL_AGENT_SERVER_CLIENT_SCHEMA_VERSION
                ),
                "assistant_id": DELL_AGENT_SERVER_ASSISTANT_ID,
                "server_assistant_uuid": SERVER_ASSISTANT_ID,
                "execution_profile": "product",
                "server_thread_id": THREAD_ID,
                "invocation_kind": "start",
                "context": context,
                "graph_input": graph_input,
                "command": None,
                "transport": {
                    "stream_mode": ["updates"],
                    "stream_resumable": True,
                    "durability": "sync",
                    "multitask_strategy": "reject",
                    "if_not_exists": "reject",
                    "after_seconds": client_module._RUN_BINDING_GRACE_SECONDS,
                },
            }
        ),
        "durable_identity_gate_version": (
            "fin_ia_dell_agent_server_durable_identity_gate_v1_0"
        ),
    }
    assert sdk.assistants.search_calls == [
        {
            "graph_id": DELL_AGENT_SERVER_ASSISTANT_ID,
            "limit": 2,
            "offset": 0,
        }
    ]
    assert callable(kwargs["on_run_created"])
    assert "langsmith_tracing" not in kwargs
    assert "command" not in kwargs


def test_start_specialist_run_reuses_the_same_durable_server_options() -> None:
    client, sdk = _client(prebound_session=True)
    graph_input = _specialist_graph_input()

    run = client.start_specialist_run(
        session=_session(),
        research_run=_research_run_contract(),
        run_invocation=_run_invocation_contract(),
        graph_input=graph_input,
    )

    assert run == _start_run()
    assert len(sdk.runs.create_calls) == 1
    _, assistant_id, kwargs = sdk.runs.create_calls[0]
    assert assistant_id == DELL_AGENT_SERVER_ASSISTANT_ID
    assert kwargs["input"] == graph_input
    assert kwargs["stream_mode"] == ["updates"]
    assert kwargs["stream_resumable"] is True
    assert kwargs["durability"] == "sync"
    assert kwargs["multitask_strategy"] == "reject"
    assert kwargs["if_not_exists"] == "reject"
    assert kwargs["context"]["run_invocation_id"] == (
        graph_input["run_invocation_id"]
    )


def test_resume_creates_new_server_run_with_same_research_run_and_new_invocation() -> None:
    repository = _MemoryIdentityRepository()
    repository.bind_agent_session(
        agent_session=_agent_session_contract(),
        server_thread_id=THREAD_ID,
        assistant_id=DELL_AGENT_SERVER_ASSISTANT_ID,
    )
    repository.bind_run_invocation(
        research_run=_research_run_contract(),
        run_invocation=_run_invocation_contract(),
        server_thread_id=THREAD_ID,
        server_run_id=START_RUN_ID,
        server_invocation_kind="start",
        first_server_status="pending",
        assistant_id=DELL_AGENT_SERVER_ASSISTANT_ID,
    )
    client, sdk = _client(repository=repository)
    sdk.runs.create_results.pop(0)

    resumed = client.resume_run(
        prior_run=_start_run(),
        research_run=_research_run_contract(),
        run_invocation=_run_invocation_contract(resume=True),
        resume_payload={"action": "approve", "reason": "reviewed"},
    )

    assert resumed.server_run_id == RESUME_RUN_ID
    assert resumed.research_run_id == "fin-research-run-001"
    assert resumed.run_invocation_id == "fin-run-invocation-002"
    assert resumed.invocation_kind == "resume"
    _, _, kwargs = sdk.runs.create_calls[0]
    assert kwargs["command"] == {
        "resume": {"action": "approve", "reason": "reviewed"}
    }
    assert "input" not in kwargs
    assert kwargs["context"] == {
        "agent_session_id": "fin-session-001",
        "research_run_id": "fin-research-run-001",
        "run_invocation_id": "fin-run-invocation-002",
    }
    assert kwargs["stream_mode"] == ["updates"]
    assert kwargs["stream_resumable"] is True
    assert kwargs["durability"] == "sync"
    assert kwargs["multitask_strategy"] == "reject"
    assert "langsmith_tracing" not in kwargs

    replay_client, _ = _client(sdk, repository)
    replayed = replay_client.resume_run(
        prior_run=_start_run(),
        research_run=_research_run_contract(status="PAUSED"),
        run_invocation=_run_invocation_contract(
            resume=True,
            status="SUCCEEDED",
            finished_at=NOW,
        ),
        resume_payload={"action": "approve", "reason": "reviewed"},
    )
    assert replayed == resumed
    assert len(sdk.runs.create_calls) == 1


def test_resume_requires_durable_start_and_exact_prior_binding() -> None:
    repository = _MemoryIdentityRepository()
    repository.bind_agent_session(
        agent_session=_agent_session_contract(),
        server_thread_id=THREAD_ID,
        assistant_id=DELL_AGENT_SERVER_ASSISTANT_ID,
    )
    client, sdk = _client(repository=repository)

    with pytest.raises(DellAgentServerClientError) as missing:
        client.resume_run(
            prior_run=_start_run(),
            research_run=_research_run_contract(),
            run_invocation=_run_invocation_contract(resume=True),
            resume_payload={"action": "approve"},
        )
    assert missing.value.code == "fin_resume_durable_predecessor_missing"

    repository.bind_run_invocation(
        research_run=_research_run_contract(),
        run_invocation=_run_invocation_contract(),
        server_thread_id=THREAD_ID,
        server_run_id=START_RUN_ID,
        server_invocation_kind="start",
        first_server_status="pending",
        assistant_id=DELL_AGENT_SERVER_ASSISTANT_ID,
    )
    wrong_prior = DellAgentServerRunBinding(
        agent_session_id="fin-session-001",
        research_run_id="fin-research-run-001",
        run_invocation_id="fin-run-invocation-001",
        server_thread_id=THREAD_ID,
        server_run_id=RESUME_RUN_ID,
        invocation_kind="start",
        server_status="pending",
    )
    with pytest.raises(DellAgentServerClientError) as conflict:
        client.resume_run(
            prior_run=wrong_prior,
            research_run=_research_run_contract(),
            run_invocation=_run_invocation_contract(resume=True),
            resume_payload={"action": "approve"},
        )
    assert conflict.value.code == "fin_resume_durable_predecessor_conflict"
    assert sdk.runs.create_calls == []


def test_resume_refuses_reused_invocation_before_calling_server() -> None:
    client, sdk = _client()

    with pytest.raises(DellAgentServerClientError) as failure:
        client.resume_run(
            prior_run=_start_run(),
            research_run=_research_run_contract(),
            run_invocation=_run_invocation_contract(),
            resume_payload={"action": "approve"},
        )

    assert failure.value.code == "fin_run_invocation_id_reused"
    assert sdk.runs.create_calls == []


def test_start_refuses_graph_input_bound_to_another_research_run() -> None:
    client, sdk = _client()
    graph_input = _graph_input()
    graph_input["run_id"] = "fin-research-run-other"

    with pytest.raises(DellAgentServerClientError) as failure:
        client.start_run(
            session=_session(),
            research_run=_research_run_contract(),
            run_invocation=_run_invocation_contract(),
            graph_input=graph_input,
        )

    assert failure.value.code == "fin_research_run_input_mismatch"
    assert sdk.runs.create_calls == []


def test_start_rejects_another_ordinal_one_before_remote_side_effect() -> None:
    repository = _MemoryIdentityRepository()
    repository.bind_agent_session(
        agent_session=_agent_session_contract(),
        server_thread_id=THREAD_ID,
        assistant_id=DELL_AGENT_SERVER_ASSISTANT_ID,
    )
    repository.bind_run_invocation(
        research_run=_research_run_contract(),
        run_invocation=_run_invocation_contract(),
        server_thread_id=THREAD_ID,
        server_run_id=START_RUN_ID,
        server_invocation_kind="start",
        first_server_status="pending",
        assistant_id=DELL_AGENT_SERVER_ASSISTANT_ID,
    )
    client, sdk = _client(repository=repository)
    second_start = _run_invocation_contract(
        invocation_id="fin-run-invocation-other-start"
    )

    with pytest.raises(DellAgentServerClientError) as failure:
        client.start_run(
            session=_session(),
            research_run=_research_run_contract(),
            run_invocation=second_start,
            graph_input=_graph_input(),
        )

    assert failure.value.code == "fin_start_durable_invocation_conflict"
    assert sdk.runs.create_calls == []


@pytest.mark.parametrize(
    "mutation",
    [
        {"unexpected": "must-not-be-silently-dropped"},
        {"case_id": 123},
        {"foundation_digest": "not-a-sha256"},
    ],
)
def test_start_strictly_rejects_invalid_or_extra_graph_input_before_server_call(
    mutation: dict[str, Any],
) -> None:
    client, sdk = _client()
    graph_input = _graph_input()
    graph_input.update(mutation)

    with pytest.raises(DellAgentServerClientError) as failure:
        client.start_run(
            session=_session(),
            research_run=_research_run_contract(),
            run_invocation=_run_invocation_contract(),
            graph_input=graph_input,
        )

    assert failure.value.code == "agent_server_graph_input_invalid"
    assert sdk.runs.create_calls == []


def test_join_updates_supports_full_replay_and_exact_cursor_suffix() -> None:
    client, sdk = _client()

    parts = list(client.join_updates(_start_run(), last_event_id="-1"))

    assert parts == sdk.runs.stream_parts
    assert sdk.runs.join_calls == [
        (
            THREAD_ID,
            START_RUN_ID,
            {
                "cancel_on_disconnect": False,
                "stream_mode": "updates",
                "last_event_id": "-1",
            },
        )
    ]

    sdk.runs.stream_parts = [
        StreamPart("updates", {"lead": {"status": "ready"}}, "102-0")
    ]
    suffix = list(client.join_updates(_start_run(), last_event_id="101-0"))
    assert [part.id for part in suffix] == ["102-0"]


@pytest.mark.parametrize(
    ("parts", "code"),
    [
        (
            [StreamPart("values", {"private": "full-state"}, "100-0")],
            "agent_server_values_stream_forbidden",
        ),
        (
            [StreamPart("updates", {}, None)],
            "agent_server_stream_event_id_missing",
        ),
        (
            [
                StreamPart("updates", {}, "100-0"),
                StreamPart("updates", {}, "100-0"),
            ],
            "agent_server_stream_event_id_duplicate",
        ),
        (
            [StreamPart("custom", {}, "100-0")],
            "agent_server_stream_event_unexpected",
        ),
        (
            [StreamPart("error", {"detail": "provider secret"}, "100-0")],
            "agent_server_stream_error",
        ),
    ],
)
def test_join_updates_rejects_illegal_stream_shapes_without_echoing_payload(
    parts: list[StreamPart],
    code: str,
) -> None:
    client, sdk = _client()
    sdk.runs.stream_parts = parts

    with pytest.raises(DellAgentServerClientError) as failure:
        list(client.join_updates(_start_run()))

    assert failure.value.code == code
    assert "provider secret" not in str(failure.value)


def test_get_state_uses_public_thread_state_endpoint_contract() -> None:
    client, sdk = _client()

    state = client.get_state(_session())

    assert state["values"] == {"phase": "awaiting_review"}
    assert sdk.threads.get_state_calls == [(THREAD_ID, {"subgraphs": False})]


def test_sdk_failures_are_typed_and_secret_free() -> None:
    client, sdk = _client()

    def fail(**_kwargs: Any) -> Any:
        raise RuntimeError("test-provider-secret-must-not-leak")

    sdk.threads.create = fail  # type: ignore[method-assign]
    with pytest.raises(DellAgentServerClientError) as failure:
        client.create_agent_session(agent_session=_agent_session_contract())

    assert failure.value.code == "agent_server_session_create_failed"
    assert "test-provider-secret" not in str(failure.value)
    assert "test-provider-secret" not in repr(failure.value)


def test_session_create_persists_once_and_replay_idempotently_ensures_thread() -> None:
    sdk = _FakeSdk()
    repository = _MemoryIdentityRepository()
    first_client, _ = _client(sdk, repository)

    first = first_client.create_agent_session(
        agent_session=_agent_session_contract()
    )
    # A fresh wrapper represents a later ingress process.  It must read the
    # PostgreSQL port rather than creating a second server thread.
    replay_client, _ = _client(sdk, repository)
    replay = replay_client.create_agent_session(
        agent_session=_agent_session_contract(status="PAUSED")
    )

    assert replay == first == _session()
    assert repository.session_bind_calls == 1
    assert len(sdk.threads.create_calls) == 2
    assert {
        call["thread_id"] for call in sdk.threads.create_calls
    } == {THREAD_ID}
    assert all(
        call["if_exists"] == "do_nothing"
        for call in sdk.threads.create_calls
    )


def test_durable_session_conflict_stops_before_agent_server_call() -> None:
    repository = _MemoryIdentityRepository()
    repository.bind_agent_session(
        agent_session=_agent_session_contract(),
        server_thread_id=THREAD_ID,
        assistant_id=DELL_AGENT_SERVER_ASSISTANT_ID,
    )
    sdk = _FakeSdk()
    client, _ = _client(sdk, repository)

    with pytest.raises(DellAgentServerClientError) as failure:
        client.create_agent_session(
            agent_session=_agent_session_contract(
                objective_digest=DIGEST_B,
            )
        )

    assert failure.value.code == "fin_agent_session_durable_binding_conflict"
    assert sdk.threads.create_calls == []


def test_run_create_persists_once_and_fresh_client_reads_same_server_run() -> None:
    sdk = _FakeSdk()
    repository = _MemoryIdentityRepository()
    repository.bind_agent_session(
        agent_session=_agent_session_contract(),
        server_thread_id=THREAD_ID,
        assistant_id=DELL_AGENT_SERVER_ASSISTANT_ID,
    )
    first_client, _ = _client(sdk, repository)

    first = first_client.start_run(
        session=_session(),
        research_run=_research_run_contract(),
        run_invocation=_run_invocation_contract(),
        graph_input=_graph_input(),
    )
    replay_client, _ = _client(sdk, repository)
    replay = replay_client.start_run(
        session=_session(),
        research_run=_research_run_contract(status="PAUSED"),
        run_invocation=_run_invocation_contract(
            status="SUCCEEDED",
            finished_at=NOW,
        ),
        graph_input=_graph_input(),
    )

    assert replay == first == _start_run()
    assert repository.invocation_bind_calls == 1
    assert len(sdk.runs.create_calls) == 1


@pytest.mark.parametrize(
    "legacy_schema_version",
    [
        "fin_ia_dell_agent_server_client_v1_0",
        "fin_ia_dell_agent_server_client_v1_1",
    ],
)
def test_durable_legacy_final_run_is_read_only_compatible(
    legacy_schema_version: str,
) -> None:
    sdk = _FakeSdk()
    repository = _MemoryIdentityRepository()
    client, _ = _client(sdk, repository, prebound_session=True)
    first = client.start_run(
        session=_session(),
        research_run=_research_run_contract(),
        run_invocation=_run_invocation_contract(),
        graph_input=_graph_input(),
    )
    if legacy_schema_version.endswith("v1_0"):
        sdk.runs.remote_runs[0]["metadata"] = {
            "fin_client_schema_version": legacy_schema_version,
            "agent_session_id": "fin-session-001",
            "research_run_id": "fin-research-run-001",
            "run_invocation_id": "fin-run-invocation-001",
            "invocation_kind": "start",
        }
    else:
        sdk.runs.remote_runs[0]["metadata"] = {
            **sdk.runs.remote_runs[0]["metadata"],
            "fin_client_schema_version": legacy_schema_version,
        }

    fresh_client, _ = _client(sdk, repository)
    replay = fresh_client.start_run(
        session=_session(),
        research_run=_research_run_contract(status="PAUSED"),
        run_invocation=_run_invocation_contract(
            status="SUCCEEDED",
            finished_at=NOW,
        ),
        graph_input=_graph_input(),
    )

    assert replay == first
    assert len(sdk.runs.create_calls) == 1
    assert repository.begin_run_create_calls == 1


def test_durable_v1_1_qualification_final_run_is_read_only_compatible() -> None:
    sdk = _FakeSdk()
    repository = _MemoryIdentityRepository()
    repository.bind_agent_session(
        agent_session=_agent_session_contract(),
        server_thread_id=THREAD_ID,
        assistant_id=DELL_AGENT_SERVER_ASSISTANT_ID,
    )
    client = DellAgentServerClient(
        sdk,
        identity_repository=repository,
        execution_profile="zero_model_control_plane_v1",
    )
    first = client.start_run(
        session=_session(),
        research_run=_research_run_contract(),
        run_invocation=_run_invocation_contract(),
        graph_input=_graph_input(),
    )
    sdk.runs.remote_runs[0]["metadata"] = {
        **sdk.runs.remote_runs[0]["metadata"],
        "fin_client_schema_version": "fin_ia_dell_agent_server_client_v1_1",
    }

    fresh_client = DellAgentServerClient(
        sdk,
        identity_repository=repository,
        execution_profile="zero_model_control_plane_v1",
    )
    replay = fresh_client.start_run(
        session=_session(),
        research_run=_research_run_contract(),
        run_invocation=_run_invocation_contract(),
        graph_input=_graph_input(),
    )

    assert replay == first
    assert len(sdk.runs.create_calls) == 1
    assert repository.begin_run_create_calls == 1


def test_durable_v1_1_final_run_rejects_changed_digest() -> None:
    sdk = _FakeSdk()
    repository = _MemoryIdentityRepository()
    client, _ = _client(sdk, repository, prebound_session=True)
    client.start_run(
        session=_session(),
        research_run=_research_run_contract(),
        run_invocation=_run_invocation_contract(),
        graph_input=_graph_input(),
    )
    sdk.runs.remote_runs[0]["metadata"] = {
        **sdk.runs.remote_runs[0]["metadata"],
        "fin_client_schema_version": "fin_ia_dell_agent_server_client_v1_1",
        "launch_request_digest": "f" * 64,
    }

    with pytest.raises(DellAgentServerClientError) as conflict:
        client.start_run(
            session=_session(),
            research_run=_research_run_contract(),
            run_invocation=_run_invocation_contract(),
            graph_input=_graph_input(),
        )

    assert conflict.value.code == "agent_server_run_metadata_mismatch"
    assert len(sdk.runs.create_calls) == 1
    assert repository.begin_run_create_calls == 1


def test_legacy_v1_0_product_run_cannot_be_relabelled_as_qualification() -> None:
    sdk = _FakeSdk()
    repository = _MemoryIdentityRepository()
    product_client, _ = _client(sdk, repository, prebound_session=True)
    product_client.start_run(
        session=_session(),
        research_run=_research_run_contract(),
        run_invocation=_run_invocation_contract(),
        graph_input=_graph_input(),
    )
    sdk.runs.remote_runs[0]["metadata"] = {
        "fin_client_schema_version": "fin_ia_dell_agent_server_client_v1_0",
        "agent_session_id": "fin-session-001",
        "research_run_id": "fin-research-run-001",
        "run_invocation_id": "fin-run-invocation-001",
        "invocation_kind": "start",
    }
    qualification_client = DellAgentServerClient(
        sdk,
        identity_repository=repository,
        execution_profile="zero_model_control_plane_v1",
    )

    with pytest.raises(DellAgentServerClientError) as failure:
        qualification_client.start_run(
            session=_session(),
            research_run=_research_run_contract(status="PAUSED"),
            run_invocation=_run_invocation_contract(
                status="SUCCEEDED",
                finished_at=NOW,
            ),
            graph_input=_graph_input(),
        )

    assert failure.value.code == "agent_server_run_metadata_mismatch"
    assert len(sdk.runs.create_calls) == 1


def test_existing_pending_is_reconcile_only_when_remote_scan_recovers() -> None:
    sdk = _FakeSdk()
    repository = _MemoryIdentityRepository()
    client, _ = _client(
        sdk,
        repository,
        prebound_session=True,
    )
    original_list = sdk.runs.list

    def unavailable_list(
        _thread_id: str,
        **_kwargs: Any,
    ) -> list[dict[str, Any]]:
        raise TimeoutError("simulated list outage before create")

    sdk.runs.list = unavailable_list  # type: ignore[method-assign]
    with pytest.raises(DellAgentServerClientError) as first_failure:
        client.start_run(
            session=_session(),
            research_run=_research_run_contract(),
            run_invocation=_run_invocation_contract(),
            graph_input=_graph_input(),
        )
    assert (
        first_failure.value.code
        == "agent_server_run_reconciliation_list_failed"
    )
    assert repository.run_create_lifecycles[
        "fin-run-invocation-001"
    ].state == "PENDING"
    assert sdk.runs.create_calls == []

    sdk.runs.list = original_list  # type: ignore[method-assign]
    fresh_client, _ = _client(sdk, repository)
    with pytest.raises(DellAgentServerClientError) as retry_failure:
        fresh_client.start_run(
            session=_session(),
            research_run=_research_run_contract(),
            run_invocation=_run_invocation_contract(),
            graph_input=_graph_input(),
        )

    assert (
        retry_failure.value.code
        == "agent_server_run_pending_reconciliation_required"
    )
    assert sdk.runs.create_calls == []


def test_unknown_create_transport_outcome_is_not_retried_across_calls() -> None:
    sdk = _FakeSdk()
    sdk.runs.raise_before_create = True
    repository = _MemoryIdentityRepository()
    client, _ = _client(
        sdk,
        repository,
        prebound_session=True,
    )

    with pytest.raises(DellAgentServerClientError) as failure:
        client.start_run(
            session=_session(),
            research_run=_research_run_contract(),
            run_invocation=_run_invocation_contract(),
            graph_input=_graph_input(),
        )

    assert failure.value.code == "agent_server_run_start_failed_outcome_unknown"
    assert len(sdk.runs.create_calls) == 1
    lifecycle = repository.run_create_lifecycles["fin-run-invocation-001"]
    assert lifecycle.state == "ORPHAN"
    assert lifecycle.orphan is not None
    assert lifecycle.orphan.server_run_id is None
    assert lifecycle.orphan.recovery_reason_code == "remote_create_outcome_unknown"

    sdk.runs.raise_before_create = False
    fresh_client, _ = _client(sdk, repository)
    with pytest.raises(DellAgentServerClientError) as replay_failure:
        fresh_client.start_run(
            session=_session(),
            research_run=_research_run_contract(),
            run_invocation=_run_invocation_contract(),
            graph_input=_graph_input(),
        )
    assert (
        replay_failure.value.code
        == "agent_server_run_recovery_operator_decision_required"
    )
    recovery_case = repository.recovery_cases["fin-run-invocation-001"]
    assert recovery_case.research_run.status == "RECOVERY_REQUIRED"
    assert recovery_case.source_invocation.status == "INTERRUPTED"
    assert recovery_case.ambiguous_action.outcome == "AMBIGUOUS_AFTER_DISPATCH"
    assert len(sdk.runs.create_calls) == 1


def test_owner_abandon_run_closes_replay_without_another_remote_create() -> None:
    sdk = _FakeSdk()
    sdk.runs.raise_before_create = True
    repository = _MemoryIdentityRepository()
    client, _ = _client(sdk, repository, prebound_session=True)

    with pytest.raises(DellAgentServerClientError):
        client.start_run(
            session=_session(),
            research_run=_research_run_contract(),
            run_invocation=_run_invocation_contract(),
            graph_input=_graph_input(),
        )
    assert len(sdk.runs.create_calls) == 1

    _record_memory_recovery_disposition(
        repository,
        decision="ABANDON_RUN",
    )
    sdk.runs.raise_before_create = False
    with pytest.raises(DellAgentServerClientError) as abandoned:
        client.start_run(
            session=_session(),
            research_run=_research_run_contract(),
            run_invocation=_run_invocation_contract(),
            graph_input=_graph_input(),
        )

    assert abandoned.value.code == "agent_server_run_recovery_abandoned"
    assert len(sdk.runs.create_calls) == 1
    assert repository.invocations == {}


def test_header_observed_response_loss_persists_known_orphan() -> None:
    sdk = _FakeSdk()
    sdk.runs.raise_after_create = True
    sdk.runs.hidden_list_calls_remaining = 2
    repository = _MemoryIdentityRepository()
    client, _ = _client(
        sdk,
        repository,
        prebound_session=True,
    )

    with pytest.raises(DellAgentServerClientError) as failure:
        client.start_run(
            session=_session(),
            research_run=_research_run_contract(),
            run_invocation=_run_invocation_contract(),
            graph_input=_graph_input(),
        )

    assert failure.value.code == "agent_server_run_start_failed_outcome_unknown"
    assert len(sdk.runs.create_calls) == 1
    lifecycle = repository.run_create_lifecycles["fin-run-invocation-001"]
    assert lifecycle.state == "ORPHAN"
    assert lifecycle.orphan is not None
    assert lifecycle.orphan.server_run_id == START_RUN_ID
    assert lifecycle.orphan.server_run_status is None
    assert (
        lifecycle.orphan.recovery_reason_code
        == "server_content_location_observed"
    )
    assert repository.invocations == {}


def test_delayed_metadata_only_visibility_requires_owner_before_exact_adoption() -> None:
    sdk = _FakeSdk()
    sdk.runs.raise_after_create = True
    sdk.runs.emit_created_header = False
    sdk.runs.hidden_list_calls_remaining = 2
    repository = _MemoryIdentityRepository()
    first_client, _ = _client(
        sdk,
        repository,
        prebound_session=True,
    )

    with pytest.raises(DellAgentServerClientError):
        first_client.start_run(
            session=_session(),
            research_run=_research_run_contract(),
            run_invocation=_run_invocation_contract(),
            graph_input=_graph_input(),
        )
    assert len(sdk.runs.create_calls) == 1
    assert repository.run_create_lifecycles[
        "fin-run-invocation-001"
    ].state == "ORPHAN"
    assert repository.run_create_lifecycles[
        "fin-run-invocation-001"
    ].orphan.server_run_id is None

    recovered_client, _ = _client(sdk, repository)
    with pytest.raises(DellAgentServerClientError) as owner_gate:
        recovered_client.start_run(
            session=_session(),
            research_run=_research_run_contract(),
            run_invocation=_run_invocation_contract(),
            graph_input=_graph_input(),
        )

    assert (
        owner_gate.value.code
        == "agent_server_run_recovery_operator_decision_required"
    )
    assert repository.invocations == {}
    exact_observations = [
        item
        for item in repository.run_create_lifecycles[
            "fin-run-invocation-001"
        ].orphan_observations
        if item.server_run_id == START_RUN_ID
        and item.server_run_status == "pending"
    ]
    assert len(exact_observations) == 1

    _record_memory_recovery_disposition(
        repository,
        decision="DO_NOT_RETRY",
    )
    recovered = recovered_client.start_run(
        session=_session(),
        research_run=_research_run_contract(),
        run_invocation=_run_invocation_contract(),
        graph_input=_graph_input(),
    )

    assert recovered == _start_run()
    assert len(sdk.runs.create_calls) == 1
    assert repository.begin_run_create_calls == 3
    assert repository.run_create_lifecycles[
        "fin-run-invocation-001"
    ].state == "RECONCILED"
    assert sdk.runs.get_calls == [(THREAD_ID, START_RUN_ID)]


def test_known_orphan_recovers_by_exact_get_without_list_or_create() -> None:
    sdk = _FakeSdk()
    sdk.runs.raise_after_create = True
    sdk.runs.hidden_list_calls_remaining = 2
    repository = _MemoryIdentityRepository()
    first_client, _ = _client(
        sdk,
        repository,
        prebound_session=True,
    )
    with pytest.raises(DellAgentServerClientError):
        first_client.start_run(
            session=_session(),
            research_run=_research_run_contract(),
            run_invocation=_run_invocation_contract(),
            graph_input=_graph_input(),
        )
    list_calls_before_recovery = len(sdk.runs.list_calls)
    sdk.runs.hidden_list_calls_remaining = 100

    recovered_client, _ = _client(sdk, repository)
    recovered = recovered_client.start_run(
        session=_session(),
        research_run=_research_run_contract(),
        run_invocation=_run_invocation_contract(),
        graph_input=_graph_input(),
    )

    assert recovered == _start_run()
    assert sdk.runs.get_calls == [(THREAD_ID, START_RUN_ID)]
    assert len(sdk.runs.list_calls) == list_calls_before_recovery
    assert len(sdk.runs.create_calls) == 1
    assert repository.run_create_lifecycles[
        "fin-run-invocation-001"
    ].state == "RECONCILED"


def test_known_orphan_forged_remote_metadata_fails_closed_without_scan() -> None:
    sdk = _FakeSdk()
    sdk.runs.raise_after_create = True
    sdk.runs.hidden_list_calls_remaining = 2
    repository = _MemoryIdentityRepository()
    first_client, _ = _client(
        sdk,
        repository,
        prebound_session=True,
    )
    with pytest.raises(DellAgentServerClientError):
        first_client.start_run(
            session=_session(),
            research_run=_research_run_contract(),
            run_invocation=_run_invocation_contract(),
            graph_input=_graph_input(),
        )
    sdk.runs.remote_runs[0]["metadata"] = {
        **sdk.runs.remote_runs[0]["metadata"],
        "fin_client_schema_version": "fin_ia_dell_agent_server_client_v1_1",
    }
    list_calls_before_recovery = len(sdk.runs.list_calls)

    recovered_client, _ = _client(sdk, repository)
    with pytest.raises(DellAgentServerClientError) as conflict:
        recovered_client.start_run(
            session=_session(),
            research_run=_research_run_contract(),
            run_invocation=_run_invocation_contract(),
            graph_input=_graph_input(),
        )

    assert conflict.value.code == "agent_server_run_metadata_mismatch"
    assert sdk.runs.get_calls == [(THREAD_ID, START_RUN_ID)]
    assert len(sdk.runs.list_calls) == list_calls_before_recovery
    assert len(sdk.runs.create_calls) == 1
    assert repository.run_create_lifecycles[
        "fin-run-invocation-001"
    ].state == "ORPHAN"


def test_known_orphan_not_found_falls_back_to_exact_list_without_create() -> None:
    sdk = _FakeSdk()
    sdk.runs.raise_after_create = True
    sdk.runs.hidden_list_calls_remaining = 2
    repository = _MemoryIdentityRepository()
    first_client, _ = _client(
        sdk,
        repository,
        prebound_session=True,
    )
    with pytest.raises(DellAgentServerClientError):
        first_client.start_run(
            session=_session(),
            research_run=_research_run_contract(),
            run_invocation=_run_invocation_contract(),
            graph_input=_graph_input(),
        )

    class _KnownRunNotFound(RuntimeError):
        status_code = 404

    original_get = sdk.runs.get

    def not_found(_thread_id: str, _run_id: str) -> Any:
        sdk.runs.get_calls.append((_thread_id, _run_id))
        raise _KnownRunNotFound("simulated explicit 404")

    sdk.runs.get = not_found  # type: ignore[method-assign]
    recovered_client, _ = _client(sdk, repository)
    recovered = recovered_client.start_run(
        session=_session(),
        research_run=_research_run_contract(),
        run_invocation=_run_invocation_contract(),
        graph_input=_graph_input(),
    )
    sdk.runs.get = original_get  # type: ignore[method-assign]

    assert recovered == _start_run()
    assert sdk.runs.get_calls == [(THREAD_ID, START_RUN_ID)]
    assert len(sdk.runs.create_calls) == 1


def test_known_orphan_never_adopts_another_same_metadata_run() -> None:
    sdk = _FakeSdk()
    sdk.runs.raise_after_create = True
    sdk.runs.hidden_list_calls_remaining = 2
    repository = _MemoryIdentityRepository()
    first_client, _ = _client(
        sdk,
        repository,
        prebound_session=True,
    )
    with pytest.raises(DellAgentServerClientError):
        first_client.start_run(
            session=_session(),
            research_run=_research_run_contract(),
            run_invocation=_run_invocation_contract(),
            graph_input=_graph_input(),
        )

    class _KnownRunNotFound(RuntimeError):
        status_code = 404

    original_get = sdk.runs.get

    def not_found(_thread_id: str, _run_id: str) -> Any:
        sdk.runs.get_calls.append((_thread_id, _run_id))
        raise _KnownRunNotFound("simulated explicit 404")

    # Preserve the complete invocation metadata while changing only the
    # server-owned identity.  A metadata-only recovery would incorrectly bind
    # this duplicate-looking row to the already known ORPHAN.
    sdk.runs.remote_runs[0]["run_id"] = "01a065aa-7091-7a93-8153-7956fb32f947"
    sdk.runs.get = not_found  # type: ignore[method-assign]
    try:
        recovered_client, _ = _client(sdk, repository)
        with pytest.raises(DellAgentServerClientError) as conflict:
            recovered_client.start_run(
                session=_session(),
                research_run=_research_run_contract(),
                run_invocation=_run_invocation_contract(),
                graph_input=_graph_input(),
            )
    finally:
        sdk.runs.get = original_get  # type: ignore[method-assign]

    assert (
        conflict.value.code
        == "agent_server_run_reconciliation_identity_conflict"
    )
    assert sdk.runs.get_calls == [(THREAD_ID, START_RUN_ID)]
    assert len(sdk.runs.create_calls) == 1
    assert repository.run_create_lifecycles[
        "fin-run-invocation-001"
    ].state == "ORPHAN"


def test_header_observed_run_never_adopts_another_same_metadata_run() -> None:
    sdk = _FakeSdk()
    repository = _MemoryIdentityRepository()
    first_client, _ = _client(
        sdk,
        repository,
        prebound_session=True,
    )
    duplicate_run_id = "01a065aa-7091-7a93-8153-7956fb32f947"

    def response_lost_after_header(
        thread_id: str,
        assistant_id: str,
        **kwargs: Any,
    ) -> Any:
        sdk.runs.create_calls.append((thread_id, assistant_id, kwargs))
        observed = {
            "thread_id": thread_id,
            "run_id": START_RUN_ID,
            "assistant_id": SERVER_ASSISTANT_ID,
            "status": "pending",
            "metadata": dict(kwargs["metadata"]),
        }
        callback = kwargs["on_run_created"]
        callback({"thread_id": thread_id, "run_id": START_RUN_ID})
        sdk.runs.remote_runs = [
            {**observed, "run_id": duplicate_run_id}
        ]
        raise TimeoutError("simulated response loss after durable header")

    sdk.runs.create = response_lost_after_header  # type: ignore[method-assign]
    with pytest.raises(DellAgentServerClientError) as conflict:
        first_client.start_run(
            session=_session(),
            research_run=_research_run_contract(),
            run_invocation=_run_invocation_contract(),
            graph_input=_graph_input(),
        )

    assert (
        conflict.value.code
        == "agent_server_run_reconciliation_identity_conflict"
    )
    lifecycle = repository.run_create_lifecycles["fin-run-invocation-001"]
    assert lifecycle.state == "ORPHAN"
    assert lifecycle.orphan is not None
    assert lifecycle.orphan.server_run_id == START_RUN_ID
    assert len(sdk.runs.create_calls) == 1
    assert sdk.runs.list_calls


def test_terminal_remote_observation_is_durable_before_operator_review() -> None:
    sdk = _FakeSdk()
    sdk.runs.emit_created_header = False
    sdk.runs.raise_after_create = True
    sdk.runs.create_results[0] = {
        **sdk.runs.create_results[0],
        "status": "success",
    }
    repository = _MemoryIdentityRepository()
    client, _ = _client(
        sdk,
        repository,
        prebound_session=True,
    )

    with pytest.raises(DellAgentServerClientError) as review:
        client.start_run(
            session=_session(),
            research_run=_research_run_contract(),
            run_invocation=_run_invocation_contract(),
            graph_input=_graph_input(),
        )

    assert (
        review.value.code
        == "agent_server_run_reconciliation_operator_review_required"
    )
    lifecycle = repository.run_create_lifecycles["fin-run-invocation-001"]
    assert lifecycle.state == "ORPHAN"
    assert lifecycle.orphan is not None
    assert lifecycle.orphan.server_run_id == START_RUN_ID
    assert lifecycle.orphan.server_run_status == "success"
    assert (
        lifecycle.orphan.recovery_reason_code
        == "metadata_scan_only_server_run_requires_operator_review"
    )
    assert repository.recovery_cases[
        "fin-run-invocation-001"
    ].ambiguous_action.outcome == "AMBIGUOUS_AFTER_DISPATCH"
    assert len(sdk.runs.create_calls) == 1


@pytest.mark.parametrize("terminal_status", ["running", "success"])
def test_direct_create_response_binds_by_exact_identity_regardless_of_status(
    terminal_status: str,
) -> None:
    sdk = _FakeSdk()
    sdk.runs.create_results[0] = {
        **sdk.runs.create_results[0],
        "status": terminal_status,
    }
    repository = _MemoryIdentityRepository()
    client, _ = _client(
        sdk,
        repository,
        prebound_session=True,
    )

    bound = client.start_run(
        session=_session(),
        research_run=_research_run_contract(),
        run_invocation=_run_invocation_contract(),
        graph_input=_graph_input(),
    )

    assert bound.server_run_id == START_RUN_ID
    assert bound.server_status == terminal_status
    lifecycle = repository.run_create_lifecycles["fin-run-invocation-001"]
    assert lifecycle.state == "RECONCILED"
    assert lifecycle.orphan is not None
    assert lifecycle.orphan.server_run_id == START_RUN_ID
    assert any(
        item.server_run_id == START_RUN_ID
        and item.server_run_status == terminal_status
        and item.recovery_reason_code == "exact_server_run_observed"
        for item in lifecycle.orphan_observations
    )
    assert repository.action_attempts[
        "fin-run-invocation-001"
    ]["TERMINAL"].outcome == "APPLIED"
    assert len(sdk.runs.create_calls) == 1


def test_header_write_failure_leaves_dispatched_and_metadata_scan_needs_owner() -> None:
    sdk = _FakeSdk()
    repository = _MemoryIdentityRepository()
    repository.fail_next_orphan_record = True
    first_client, _ = _client(
        sdk,
        repository,
        prebound_session=True,
    )

    with pytest.raises(DellAgentServerClientError) as failure:
        first_client.start_run(
            session=_session(),
            research_run=_research_run_contract(),
            run_invocation=_run_invocation_contract(),
            graph_input=_graph_input(),
        )

    assert failure.value.code == "fin_identity_repository_write_failed"
    assert len(sdk.runs.create_calls) == 1
    assert len(sdk.runs.remote_runs) == 1
    assert repository.run_create_lifecycles[
        "fin-run-invocation-001"
    ].state == "DISPATCHED"

    recovered_client, _ = _client(sdk, repository)
    with pytest.raises(DellAgentServerClientError) as owner_gate:
        recovered_client.start_run(
            session=_session(),
            research_run=_research_run_contract(),
            run_invocation=_run_invocation_contract(),
            graph_input=_graph_input(),
        )

    assert (
        owner_gate.value.code
        == "agent_server_run_reconciliation_operator_review_required"
    )
    assert len(sdk.runs.create_calls) == 1
    assert repository.run_create_lifecycles[
        "fin-run-invocation-001"
    ].state == "ORPHAN"
    assert repository.recovery_cases[
        "fin-run-invocation-001"
    ].server_run_id == START_RUN_ID

    _record_memory_recovery_disposition(
        repository,
        decision="DO_NOT_RETRY",
    )
    recovered = recovered_client.start_run(
        session=_session(),
        research_run=_research_run_contract(),
        run_invocation=_run_invocation_contract(),
        graph_input=_graph_input(),
    )
    assert recovered == _start_run()
    assert len(sdk.runs.create_calls) == 1


def test_pending_replay_rejects_changed_launch_before_remote_calls() -> None:
    sdk = _FakeSdk()
    sdk.runs.raise_before_create = True
    repository = _MemoryIdentityRepository()
    first_client, _ = _client(
        sdk,
        repository,
        prebound_session=True,
    )
    with pytest.raises(DellAgentServerClientError):
        first_client.start_run(
            session=_session(),
            research_run=_research_run_contract(),
            run_invocation=_run_invocation_contract(),
            graph_input=_graph_input(),
        )
    sdk.runs.raise_before_create = False
    list_calls_before_conflict = len(sdk.runs.list_calls)
    changed_input = _graph_input()
    changed_input["research_question"] = "Changed under one durable invocation"

    with pytest.raises(DellAgentServerClientError) as conflict:
        first_client.start_run(
            session=_session(),
            research_run=_research_run_contract(),
            run_invocation=_run_invocation_contract(),
            graph_input=changed_input,
        )

    assert conflict.value.code == "run_create_pending_identity_conflict"
    assert len(sdk.runs.create_calls) == 1
    assert len(sdk.runs.list_calls) == list_calls_before_conflict


def test_pending_replay_rejects_changed_profile_before_remote_create() -> None:
    sdk = _FakeSdk()
    sdk.runs.raise_before_create = True
    repository = _MemoryIdentityRepository()
    product_client, _ = _client(
        sdk,
        repository,
        prebound_session=True,
    )
    with pytest.raises(DellAgentServerClientError):
        product_client.start_run(
            session=_session(),
            research_run=_research_run_contract(),
            run_invocation=_run_invocation_contract(),
            graph_input=_graph_input(),
        )
    sdk.runs.raise_before_create = False
    list_calls_before_conflict = len(sdk.runs.list_calls)
    qualification_client = DellAgentServerClient(
        sdk,
        identity_repository=repository,
        execution_profile="zero_model_control_plane_v1",
    )

    with pytest.raises(DellAgentServerClientError) as conflict:
        qualification_client.start_run(
            session=_session(),
            research_run=_research_run_contract(),
            run_invocation=_run_invocation_contract(),
            graph_input=_graph_input(),
        )

    assert conflict.value.code == "run_create_pending_identity_conflict"
    assert len(sdk.runs.create_calls) == 1
    assert len(sdk.runs.list_calls) == list_calls_before_conflict


def test_wrong_concrete_assistant_cannot_be_adopted_via_forged_metadata() -> None:
    sdk = _FakeSdk()
    sdk.runs.create_results[0]["assistant_id"] = str(
        uuid5(NAMESPACE_URL, "wrong-assistant")
    )
    repository = _MemoryIdentityRepository()
    client, _ = _client(sdk, repository, prebound_session=True)

    with pytest.raises(DellAgentServerClientError) as failure:
        client.start_run(
            session=_session(),
            research_run=_research_run_contract(),
            run_invocation=_run_invocation_contract(),
            graph_input=_graph_input(),
        )

    assert (
        failure.value.code
        == "agent_server_run_reconciliation_identity_conflict"
    )
    assert repository.invocations == {}


def test_resume_rejects_cross_profile_binding_before_remote_calls() -> None:
    sdk = _FakeSdk()
    client = DellAgentServerClient(
        sdk,
        identity_repository=_MemoryIdentityRepository(),
        execution_profile="zero_model_control_plane_v1",
    )

    with pytest.raises(DellAgentServerClientError) as failure:
        client.resume_run(
            prior_run=_start_run(),
            research_run=_research_run_contract(),
            run_invocation=_run_invocation_contract(resume=True),
            resume_payload={"action": "complete_zero_model_qualification"},
        )

    assert failure.value.code == "agent_server_resume_execution_profile_mismatch"
    assert sdk.runs.create_calls == []


def test_bind_failure_is_reconciled_from_exact_remote_metadata_without_recreate() -> None:
    sdk = _FakeSdk()
    repository = _MemoryIdentityRepository()
    repository.bind_agent_session(
        agent_session=_agent_session_contract(),
        server_thread_id=THREAD_ID,
        assistant_id=DELL_AGENT_SERVER_ASSISTANT_ID,
    )
    repository.fail_next_invocation_bind = True
    client, _ = _client(sdk, repository)

    with pytest.raises(DellAgentServerClientError) as first_failure:
        client.start_run(
            session=_session(),
            research_run=_research_run_contract(),
            run_invocation=_run_invocation_contract(),
            graph_input=_graph_input(),
        )
    assert first_failure.value.code == "fin_identity_repository_write_failed"
    assert len(sdk.runs.create_calls) == 1
    assert len(sdk.runs.remote_runs) == 1
    assert repository.invocations == {}
    assert repository.run_create_lifecycles[
        "fin-run-invocation-001"
    ].state == "ORPHAN"

    recovered_client, _ = _client(sdk, repository)
    recovered = recovered_client.start_run(
        session=_session(),
        research_run=_research_run_contract(),
        run_invocation=_run_invocation_contract(),
        graph_input=_graph_input(),
    )

    assert recovered == _start_run()
    assert len(sdk.runs.create_calls) == 1
    assert repository.invocation_bind_calls == 2
    assert repository.begin_run_create_calls == 2
    assert repository.run_create_lifecycles[
        "fin-run-invocation-001"
    ].state == "RECONCILED"


def test_response_loss_after_remote_commit_reconciles_in_same_client_call() -> None:
    sdk = _FakeSdk()
    sdk.runs.raise_after_create = True
    client, _ = _client(sdk, prebound_session=True)

    recovered = client.start_run(
        session=_session(),
        research_run=_research_run_contract(),
        run_invocation=_run_invocation_contract(),
        graph_input=_graph_input(),
    )

    assert recovered == _start_run()
    assert len(sdk.runs.create_calls) == 1
    assert len(sdk.runs.remote_runs) == 1


def test_bound_invocation_replay_rejects_changed_launch_payload() -> None:
    sdk = _FakeSdk()
    repository = _MemoryIdentityRepository()
    client, _ = _client(sdk, repository, prebound_session=True)
    client.start_run(
        session=_session(),
        research_run=_research_run_contract(),
        run_invocation=_run_invocation_contract(),
        graph_input=_graph_input(),
    )
    changed_input = _graph_input()
    changed_input["research_question"] = "A different request under the same invocation"

    with pytest.raises(DellAgentServerClientError) as conflict:
        client.start_run(
            session=_session(),
            research_run=_research_run_contract(status="PAUSED"),
            run_invocation=_run_invocation_contract(
                status="SUCCEEDED",
                finished_at=NOW,
            ),
            graph_input=changed_input,
        )

    assert conflict.value.code == "agent_server_run_metadata_mismatch"
    assert len(sdk.runs.create_calls) == 1


def test_durable_direct_identity_ignores_later_duplicate_metadata_candidate() -> None:
    sdk = _FakeSdk()
    sdk.runs.emit_created_header = False
    repository = _MemoryIdentityRepository()
    repository.bind_agent_session(
        agent_session=_agent_session_contract(),
        server_thread_id=THREAD_ID,
        assistant_id=DELL_AGENT_SERVER_ASSISTANT_ID,
    )
    repository.fail_next_invocation_bind = True
    client, _ = _client(sdk, repository)
    with pytest.raises(DellAgentServerClientError):
        client.start_run(
            session=_session(),
            research_run=_research_run_contract(),
            run_invocation=_run_invocation_contract(),
            graph_input=_graph_input(),
        )
    duplicate = dict(sdk.runs.remote_runs[0])
    duplicate["run_id"] = str(uuid5(NAMESPACE_URL, "duplicate-exact-run"))
    sdk.runs.remote_runs.append(duplicate)
    list_calls_before_replay = len(sdk.runs.list_calls)

    recovered = client.start_run(
        session=_session(),
        research_run=_research_run_contract(),
        run_invocation=_run_invocation_contract(),
        graph_input=_graph_input(),
    )

    assert recovered.server_run_id == START_RUN_ID
    assert sdk.runs.get_calls == [(THREAD_ID, START_RUN_ID)]
    assert len(sdk.runs.list_calls) == list_calls_before_replay
    assert len(sdk.runs.create_calls) == 1


def test_remote_same_invocation_with_different_request_digest_blocks_create() -> None:
    sdk = _FakeSdk()
    sdk.runs.emit_created_header = False
    repository = _MemoryIdentityRepository()
    repository.bind_agent_session(
        agent_session=_agent_session_contract(),
        server_thread_id=THREAD_ID,
        assistant_id=DELL_AGENT_SERVER_ASSISTANT_ID,
    )
    repository.fail_next_invocation_bind = True
    client, _ = _client(sdk, repository)
    with pytest.raises(DellAgentServerClientError):
        client.start_run(
            session=_session(),
            research_run=_research_run_contract(),
            run_invocation=_run_invocation_contract(),
            graph_input=_graph_input(),
        )
    sdk.runs.remote_runs[0]["metadata"] = dict(
        sdk.runs.remote_runs[0]["metadata"],
        launch_request_digest="f" * 64,
    )

    with pytest.raises(DellAgentServerClientError) as conflict:
        client.start_run(
            session=_session(),
            research_run=_research_run_contract(),
            run_invocation=_run_invocation_contract(),
            graph_input=_graph_input(),
        )

    assert conflict.value.code == "agent_server_run_metadata_mismatch"
    assert len(sdk.runs.create_calls) == 1


def test_reconciliation_scans_beyond_the_first_hundred_runs() -> None:
    sdk = _FakeSdk()
    sdk.runs.emit_created_header = False
    sdk.runs.raise_after_create = True
    sdk.runs.hidden_list_calls_remaining = 2
    repository = _MemoryIdentityRepository()
    repository.bind_agent_session(
        agent_session=_agent_session_contract(),
        server_thread_id=THREAD_ID,
        assistant_id=DELL_AGENT_SERVER_ASSISTANT_ID,
    )
    client, _ = _client(sdk, repository)
    with pytest.raises(DellAgentServerClientError) as unknown:
        client.start_run(
            session=_session(),
            research_run=_research_run_contract(),
            run_invocation=_run_invocation_contract(),
            graph_input=_graph_input(),
        )
    assert unknown.value.code == "agent_server_run_start_failed_outcome_unknown"
    assert repository.recovery_cases[
        "fin-run-invocation-001"
    ].server_run_id is None
    exact = sdk.runs.remote_runs[0]
    unrelated = [
        {
            "thread_id": THREAD_ID,
            "run_id": str(uuid5(NAMESPACE_URL, f"unrelated-run-{index}")),
            "assistant_id": SERVER_ASSISTANT_ID,
            "status": "success",
            "metadata": {"unrelated": index},
        }
        for index in range(100)
    ]
    sdk.runs.remote_runs = [*unrelated, exact]
    sdk.runs.hidden_list_calls_remaining = 0

    with pytest.raises(DellAgentServerClientError) as owner_gate:
        client.start_run(
            session=_session(),
            research_run=_research_run_contract(),
            run_invocation=_run_invocation_contract(),
            graph_input=_graph_input(),
        )

    assert (
        owner_gate.value.code
        == "agent_server_run_recovery_operator_decision_required"
    )
    assert len(sdk.runs.create_calls) == 1
    assert any(call[1]["offset"] == 100 for call in sdk.runs.list_calls)

    _record_memory_recovery_disposition(
        repository,
        decision="DO_NOT_RETRY",
    )
    recovered = client.start_run(
        session=_session(),
        research_run=_research_run_contract(),
        run_invocation=_run_invocation_contract(),
        graph_input=_graph_input(),
    )
    assert recovered.server_run_id == START_RUN_ID
    assert len(sdk.runs.create_calls) == 1


def test_unstable_offset_snapshot_fails_before_remote_create() -> None:
    sdk = _FakeSdk()
    client, _ = _client(sdk, prebound_session=True)
    original_list = sdk.runs.list
    list_count = 0

    def unstable_list(thread_id: str, **kwargs: Any) -> list[dict[str, Any]]:
        nonlocal list_count
        list_count += 1
        rows = original_list(thread_id, **kwargs)
        if list_count == 1:
            sdk.runs.remote_runs.append(
                {
                    "thread_id": THREAD_ID,
                    "run_id": str(uuid5(NAMESPACE_URL, "appeared-between-scans")),
                    "assistant_id": SERVER_ASSISTANT_ID,
                    "status": "pending",
                    "metadata": {"unrelated": True},
                }
            )
        return rows

    sdk.runs.list = unstable_list  # type: ignore[method-assign]

    with pytest.raises(DellAgentServerClientError) as unstable:
        client.start_run(
            session=_session(),
            research_run=_research_run_contract(),
            run_invocation=_run_invocation_contract(),
            graph_input=_graph_input(),
        )

    assert (
        unstable.value.code
        == "agent_server_run_reconciliation_snapshot_unstable"
    )
    assert sdk.runs.create_calls == []


def test_reconciliation_scan_ceiling_is_not_treated_as_no_match() -> None:
    sdk = _FakeSdk()
    client, _ = _client(sdk, prebound_session=True)
    sdk.runs.remote_runs = [
        {
            "thread_id": THREAD_ID,
            "run_id": str(uuid5(NAMESPACE_URL, f"ceiling-run-{index}")),
            "assistant_id": SERVER_ASSISTANT_ID,
            "status": "success",
            "metadata": {"unrelated": index},
        }
        for index in range(client_module._RUN_RECONCILIATION_MAX_ROWS + 1)
    ]

    with pytest.raises(DellAgentServerClientError) as ceiling:
        client.start_run(
            session=_session(),
            research_run=_research_run_contract(),
            run_invocation=_run_invocation_contract(),
            graph_input=_graph_input(),
        )

    assert (
        ceiling.value.code
        == "agent_server_run_reconciliation_scan_limit_exceeded"
    )
    assert sdk.runs.create_calls == []


def test_run_create_requires_durable_session_before_remote_side_effect() -> None:
    client, sdk = _client()

    with pytest.raises(DellAgentServerClientError) as failure:
        client.start_run(
            session=_session(),
            research_run=_research_run_contract(),
            run_invocation=_run_invocation_contract(),
            graph_input=_graph_input(),
        )

    assert failure.value.code == "fin_agent_session_durable_binding_missing"
    assert sdk.runs.create_calls == []
