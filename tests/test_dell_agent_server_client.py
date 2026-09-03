from __future__ import annotations

from collections.abc import Iterator
from typing import Any

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


THREAD_ID = "01a065aa-23ec-72f3-bf4e-09cf92ac08c7"
START_RUN_ID = "01a065aa-7091-7a93-8153-7956fb32f946"
RESUME_RUN_ID = "01a065aa-7311-7e62-b147-93aca9a4ee82"


class _FakeThreads:
    def __init__(self) -> None:
        self.create_calls: list[dict[str, Any]] = []
        self.get_state_calls: list[tuple[str, dict[str, Any]]] = []
        self.create_result: Any = {
            "thread_id": THREAD_ID,
            "metadata": {"agent_session_id": "fin-session-001"},
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
        return self.create_result

    def get_state(self, thread_id: str, **kwargs: Any) -> Any:
        self.get_state_calls.append((thread_id, kwargs))
        return self.state_result


class _FakeRuns:
    def __init__(self) -> None:
        self.create_calls: list[tuple[str, str, dict[str, Any]]] = []
        self.join_calls: list[tuple[str, str, dict[str, Any]]] = []
        self.create_results: list[Any] = [
            {"thread_id": THREAD_ID, "run_id": START_RUN_ID, "status": "pending"},
            {"thread_id": THREAD_ID, "run_id": RESUME_RUN_ID, "status": "pending"},
        ]
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
        return self.create_results.pop(0)

    def join_stream(
        self,
        thread_id: str,
        run_id: str,
        **kwargs: Any,
    ) -> Iterator[StreamPart]:
        self.join_calls.append((thread_id, run_id, kwargs))
        return iter(self.stream_parts)


class _FakeSdk:
    def __init__(self) -> None:
        self.threads = _FakeThreads()
        self.runs = _FakeRuns()
        self.close_count = 0

    def close(self) -> None:
        self.close_count += 1


def _client(sdk: _FakeSdk | None = None) -> tuple[DellAgentServerClient, _FakeSdk]:
    actual_sdk = sdk or _FakeSdk()
    return (
        DellAgentServerClient(actual_sdk),
        actual_sdk,
    )


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
        timeout=30,
    )

    assert isinstance(connected, DellAgentServerClient)
    assert calls == [{"url": "http://127.0.0.1:2024", "timeout": 30}]
    assert "api_key" not in calls[0]

    with pytest.raises(DellAgentServerClientError) as embedded_secret:
        DellAgentServerClient.connect(
            url="https://secret@example.test",
        )
    assert embedded_secret.value.code == "agent_server_url_credentials_forbidden"
    assert "secret" not in str(embedded_secret.value)


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
    ) as connected:
        assert sdk.close_count == 0
        assert isinstance(connected, DellAgentServerClient)

    assert sdk.close_count == 1
    connected.close()
    assert sdk.close_count == 1
    with pytest.raises(DellAgentServerClientError) as closed:
        connected.create_agent_session(agent_session_id="fin-session-001")
    assert closed.value.code == "agent_server_client_closed"


def test_injected_sdk_remains_caller_owned_when_wrapper_closes() -> None:
    sdk = _FakeSdk()
    client, _ = _client(sdk)

    client.close()
    client.close()

    assert sdk.close_count == 0


def test_create_agent_session_lets_server_assign_uuid_and_binds_metadata() -> None:
    client, sdk = _client()

    binding = client.create_agent_session(agent_session_id="fin-session-001")

    assert binding == _session()
    assert sdk.threads.create_calls == [
        {
            "metadata": {
                "fin_client_schema_version": (
                    client_module.DELL_AGENT_SERVER_CLIENT_SCHEMA_VERSION
                ),
                "agent_session_id": "fin-session-001",
            },
            "if_exists": "raise",
            "graph_id": DELL_AGENT_SERVER_ASSISTANT_ID,
        }
    ]
    assert "thread_id" not in sdk.threads.create_calls[0]


def test_start_run_uses_only_qualified_agent_server_options() -> None:
    client, sdk = _client()
    graph_input = _graph_input()

    run = client.start_run(
        session=_session(),
        research_run_id="fin-research-run-001",
        run_invocation_id="fin-run-invocation-001",
        graph_input=graph_input,
    )

    assert run == _start_run()
    assert len(sdk.runs.create_calls) == 1
    thread_id, assistant_id, kwargs = sdk.runs.create_calls[0]
    assert thread_id == THREAD_ID
    assert assistant_id == DELL_AGENT_SERVER_ASSISTANT_ID
    assert kwargs == {
        "input": graph_input,
        "stream_mode": ["updates"],
        "stream_resumable": True,
        "durability": "sync",
        "multitask_strategy": "reject",
        "if_not_exists": "reject",
        "context": {
            "agent_session_id": "fin-session-001",
            "research_run_id": "fin-research-run-001",
            "run_invocation_id": "fin-run-invocation-001",
        },
        "metadata": {
            "fin_client_schema_version": (
                client_module.DELL_AGENT_SERVER_CLIENT_SCHEMA_VERSION
            ),
            "agent_session_id": "fin-session-001",
            "research_run_id": "fin-research-run-001",
            "run_invocation_id": "fin-run-invocation-001",
            "invocation_kind": "start",
        },
    }
    assert "langsmith_tracing" not in kwargs
    assert "command" not in kwargs


def test_resume_creates_new_server_run_with_same_research_run_and_new_invocation() -> None:
    client, sdk = _client()
    sdk.runs.create_results.pop(0)

    resumed = client.resume_run(
        prior_run=_start_run(),
        run_invocation_id="fin-run-invocation-002",
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


def test_resume_refuses_reused_invocation_before_calling_server() -> None:
    client, sdk = _client()

    with pytest.raises(DellAgentServerClientError) as failure:
        client.resume_run(
            prior_run=_start_run(),
            run_invocation_id="fin-run-invocation-001",
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
            research_run_id="fin-research-run-001",
            run_invocation_id="fin-run-invocation-001",
            graph_input=graph_input,
        )

    assert failure.value.code == "fin_research_run_input_mismatch"
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
            research_run_id="fin-research-run-001",
            run_invocation_id="fin-run-invocation-001",
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
        raise RuntimeError("sk-test-secret-must-not-escape")

    sdk.threads.create = fail  # type: ignore[method-assign]
    with pytest.raises(DellAgentServerClientError) as failure:
        client.create_agent_session(agent_session_id="fin-session-001")

    assert failure.value.code == "agent_server_session_create_failed"
    assert "sk-test-secret" not in str(failure.value)
    assert "sk-test-secret" not in repr(failure.value)
