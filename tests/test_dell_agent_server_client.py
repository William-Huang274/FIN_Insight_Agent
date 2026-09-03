from __future__ import annotations

from collections.abc import Iterator
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
    PersistedAgentSessionBinding,
    PersistedResearchRunAggregate,
    PersistedResearchRunIdentity,
    PersistedRunInvocationBinding,
    agent_session_identity_digest,
    research_run_identity_digest,
    run_invocation_identity_digest,
)
from sec_agent.canonical_runtime.contracts_v1_2 import (
    AgentSessionV1_2,
    ResearchRun,
    RunInvocation,
    create_agent_session_v1_2,
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
        self.session_bind_calls = 0
        self.invocation_bind_calls = 0
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

    def bind_run_invocation(
        self,
        *,
        research_run: ResearchRun,
        run_invocation: RunInvocation,
        server_thread_id: str,
        server_run_id: str,
        server_invocation_kind: str,
        first_server_status: str,
        assistant_id: str,
    ) -> PersistedRunInvocationBinding:
        self.invocation_bind_calls += 1
        if self.fail_next_invocation_bind:
            self.fail_next_invocation_bind = False
            raise RuntimeError("simulated bind failure")
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
        return self.invocations[run_invocation.invocation_id]

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
    assert "langsmith_tracing" not in kwargs
    assert "command" not in kwargs


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


def test_durable_legacy_v1_0_run_is_read_only_compatible() -> None:
    sdk = _FakeSdk()
    repository = _MemoryIdentityRepository()
    client, _ = _client(sdk, repository, prebound_session=True)
    first = client.start_run(
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


def test_unknown_create_transport_outcome_is_not_retried_inside_one_call() -> None:
    sdk = _FakeSdk()
    sdk.runs.raise_before_create = True
    client, _ = _client(sdk, prebound_session=True)

    with pytest.raises(DellAgentServerClientError) as failure:
        client.start_run(
            session=_session(),
            research_run=_research_run_contract(),
            run_invocation=_run_invocation_contract(),
            graph_input=_graph_input(),
        )

    assert failure.value.code == "agent_server_run_start_failed_outcome_unknown"
    assert len(sdk.runs.create_calls) == 1


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


def test_multiple_exact_remote_candidates_fail_closed_without_selection() -> None:
    sdk = _FakeSdk()
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

    with pytest.raises(DellAgentServerClientError) as ambiguous:
        client.start_run(
            session=_session(),
            research_run=_research_run_contract(),
            run_invocation=_run_invocation_contract(),
            graph_input=_graph_input(),
        )

    assert ambiguous.value.code == "agent_server_run_reconciliation_ambiguous"
    assert len(sdk.runs.create_calls) == 1


def test_remote_same_invocation_with_different_request_digest_blocks_create() -> None:
    sdk = _FakeSdk()
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

    assert (
        conflict.value.code
        == "agent_server_run_reconciliation_identity_conflict"
    )
    assert len(sdk.runs.create_calls) == 1


def test_reconciliation_scans_beyond_the_first_hundred_runs() -> None:
    sdk = _FakeSdk()
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

    recovered = client.start_run(
        session=_session(),
        research_run=_research_run_contract(),
        run_invocation=_run_invocation_contract(),
        graph_input=_graph_input(),
    )

    assert recovered.server_run_id == START_RUN_ID
    assert len(sdk.runs.create_calls) == 1
    assert any(call[1]["offset"] == 100 for call in sdk.runs.list_calls)


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
