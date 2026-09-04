from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import tomllib
import traceback
from typing import Any

import pytest

from sec_agent.agent_runtime import dell_agent_server_entry as entry
from sec_agent.agent_runtime.dell_agent_server_identity import (
    PersistedExecutableRunBinding,
    PersistedRunCreateLifecycle,
    PersistedRunCreateLifecycleEvent,
    PersistedRunInvocationBinding,
    persisted_run_binding_digest,
)
from sec_agent.agent_runtime.dell_reference_vertical_graph import (
    DellAgentServerRunContext,
    DellReferenceVerticalDependencies,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class _ReadRuntime:
    access_context = "assistants.read"
    execution_runtime = None


class _ExecutionRuntime:
    access_context = "threads.create_run"

    def __init__(self, context: Any) -> None:
        self.context = context
        self.execution_runtime = self


def _context() -> dict[str, str]:
    return {
        "agent_session_id": "fin-session-001",
        "research_run_id": "fin-research-run-001",
        "run_invocation_id": "fin-run-invocation-001",
    }


def _config() -> dict[str, dict[str, str]]:
    return {
        "configurable": {
            "thread_id": "019-server-thread",
            "run_id": "019-server-run",
        }
    }


def _persisted_binding(**overrides: Any) -> PersistedRunInvocationBinding:
    fields = {
        "run_invocation_id": "fin-run-invocation-001",
        "research_run_id": "fin-research-run-001",
        "agent_session_id": "fin-session-001",
        "invocation_ordinal": 1,
        "canonical_invocation_kind": "START",
        "server_invocation_kind": "start",
        "server_thread_id": "019-server-thread",
        "server_run_id": "019-server-run",
        "assistant_id": entry.DELL_AGENT_SERVER_ASSISTANT_ID,
        "invocation_identity_digest": "a" * 64,
        "first_server_status": "pending",
        "bound_at": datetime(2026, 9, 4, tzinfo=timezone.utc),
    }
    fields.update(overrides)
    return PersistedRunInvocationBinding(**fields)


def _persisted_projection(
    *,
    state: str = "RECONCILED",
    binding_overrides: dict[str, Any] | None = None,
    reconciled_overrides: dict[str, Any] | None = None,
) -> PersistedExecutableRunBinding:
    binding = _persisted_binding(**(binding_overrides or {}))
    common = {
        "run_invocation_id": binding.run_invocation_id,
        "research_run_id": binding.research_run_id,
        "agent_session_id": binding.agent_session_id,
        "invocation_ordinal": binding.invocation_ordinal,
        "canonical_invocation_kind": binding.canonical_invocation_kind,
        "server_invocation_kind": binding.server_invocation_kind,
        "server_thread_id": binding.server_thread_id,
        "assistant_id": binding.assistant_id,
        "server_assistant_id": "019-server-assistant",
        "execution_profile": "zero_model_control_plane_v1",
        "session_identity_digest": "b" * 64,
        "research_run_identity_digest": "c" * 64,
        "run_invocation_identity_digest": binding.invocation_identity_digest,
        "launch_request_digest": "d" * 64,
        "server_metadata_digest": "e" * 64,
        "recorded_at": datetime(2026, 9, 4, tzinfo=timezone.utc),
    }
    pending = PersistedRunCreateLifecycleEvent(
        **common,
        lifecycle_ordinal=1,
        lifecycle_state="PENDING",
        bound_run_invocation_id=None,
        server_run_id=None,
        server_run_status=None,
        recovery_reason_code=None,
        server_observation_digest=None,
        final_binding_digest=None,
        lifecycle_event_digest="f" * 64,
    )
    reconciled = None
    if state == "RECONCILED":
        fields = {
            **common,
            "lifecycle_ordinal": 2,
            "lifecycle_state": "RECONCILED",
            "bound_run_invocation_id": binding.run_invocation_id,
            "server_run_id": binding.server_run_id,
            "server_run_status": binding.first_server_status,
            "recovery_reason_code": "REMOTE_RESPONSE_EXACT",
            "server_observation_digest": "1" * 64,
            "final_binding_digest": persisted_run_binding_digest(binding),
            "lifecycle_event_digest": "2" * 64,
        }
        fields.update(reconciled_overrides or {})
        reconciled = PersistedRunCreateLifecycleEvent(**fields)
    return PersistedExecutableRunBinding(
        binding=binding,
        lifecycle=PersistedRunCreateLifecycle(
            pending=pending,
            orphan=None,
            reconciled=reconciled,
        ),
    )


def test_root_langgraph_config_exposes_only_the_dell_server_factory() -> None:
    value = json.loads((REPOSITORY_ROOT / "langgraph.json").read_text("utf-8"))

    assert value["dependencies"] == [
        ".",
        "langchain-core==1.6.1",
        "langchain-deepseek==1.1.0",
        "langchain-text-splitters==1.1.2",
        "langgraph==1.2.11",
        "langgraph-sdk==0.4.4",
        "langsmith==0.12.1",
        "mcp==2.1.1",
        "psycopg[binary,pool]==3.3.4",
    ]
    assert value["api_version"] == "0.13.3"
    assert value["python_version"] == "3.13"
    assert value["graphs"] == {
        "dell_reference_vertical": {
            "path": (
                "sec_agent.agent_runtime.dell_agent_server_entry:"
                "dell_reference_vertical_graph"
            ),
            "description": "Dell research vertical; the only product serving graph",
        }
    }
    assert value["env"] == ".env"
    assert "checkpointer" not in value


def test_agent_server_imports_are_declared_as_direct_runtime_dependencies() -> None:
    value = tomllib.loads((REPOSITORY_ROOT / "pyproject.toml").read_text("utf-8"))
    dependencies = value["project"]["optional-dependencies"]["agent-runtime"]

    assert "langchain-core==1.6.1" in dependencies
    assert "langgraph-sdk==0.4.4" in dependencies
    assert "langsmith==0.12.1" in dependencies


def test_read_and_schema_access_open_no_execution_resources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened = 0

    @asynccontextmanager
    async def forbidden(*_args: Any, **_kwargs: Any) -> AsyncIterator[Any]:
        nonlocal opened
        opened += 1
        raise AssertionError("execution resources opened during introspection")
        yield  # pragma: no cover

    monkeypatch.setattr(entry, "_open_execution_dependencies", forbidden)
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.setenv(entry.DELL_EXECUTION_PROFILE_ENV, "not-a-valid-profile")

    async def exercise() -> None:
        async with entry.dell_reference_vertical_graph({}, _ReadRuntime()) as graph:
            assert graph.checkpointer is None
            assert graph.store is None
            assert set(graph.get_graph().nodes) >= {
                "bind_case",
                "plan",
                "human_review",
            }
            assert set(graph.input_schema.model_json_schema()["required"]) == {
                "run_id",
                "case_id",
                "research_question",
                "research_as_of",
                "snapshot_id",
                "foundation_digest",
            }
            assert set(graph.get_context_jsonschema()["required"]) == {
                "agent_session_id",
                "research_run_id",
                "run_invocation_id",
            }

    asyncio.run(exercise())

    assert opened == 0


def test_execution_profile_is_deployment_owned_and_checked_before_resources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened = 0

    @asynccontextmanager
    async def forbidden(*_args: Any, **_kwargs: Any) -> AsyncIterator[Any]:
        nonlocal opened
        opened += 1
        raise AssertionError("invalid profile must not open execution resources")
        yield  # pragma: no cover

    monkeypatch.setattr(entry, "_open_execution_dependencies", forbidden)
    monkeypatch.setenv(entry.DELL_EXECUTION_PROFILE_ENV, "qualification")

    async def exercise() -> None:
        async with entry.dell_reference_vertical_graph(
            _config(), _ExecutionRuntime(_context())
        ):
            pass

    with pytest.raises(entry.DellAgentServerEntryError) as failure:
        asyncio.run(exercise())
    assert failure.value.code == "dell_execution_profile_invalid"
    assert opened == 0


def test_invalid_run_context_traceback_does_not_chain_rejected_input() -> None:
    rejected = "SECRET-REJECTED-CONTEXT-VALUE"
    try:
        entry.bind_agent_server_identity(
            config=_config(),
            run_context={"agent_session_id": rejected},
        )
    except entry.DellAgentServerEntryError as exc:
        rendered = "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        )
    else:  # pragma: no cover - the strict context must reject this input
        raise AssertionError("invalid context unexpectedly accepted")

    assert rejected not in rendered
    assert "fin_run_context_invalid" in rendered


@pytest.mark.parametrize(
    "value",
    ["product", "zero_model_control_plane_v1"],
)
def test_execution_profile_accepts_only_exact_supported_values(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    monkeypatch.setenv(entry.DELL_EXECUTION_PROFILE_ENV, value)
    assert entry._require_execution_profile() == value


def test_schema_graph_is_not_an_execution_fallback() -> None:
    async def exercise() -> None:
        async with entry.dell_reference_vertical_graph({}, _ReadRuntime()) as graph:
            with pytest.raises(
                entry.DellAgentServerEntryError,
                match="schema_introspection_graph_not_executable",
            ):
                await graph.ainvoke(
                    {
                        "run_id": "fin-research-run-001",
                        "case_id": "DELL",
                        "research_question": "test",
                        "research_as_of": "2026-09-03T00:00:00+08:00",
                        "snapshot_id": "snapshot",
                        "foundation_digest": "a" * 64,
                    },
                    context=_context(),
                )

    asyncio.run(exercise())


def test_execution_requires_langsmith_tracing_and_pat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = _ExecutionRuntime(_context())
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)

    async def missing_tracing_call() -> None:
        async with entry.dell_reference_vertical_graph(_config(), runtime):
            pass

    with pytest.raises(entry.DellAgentServerEntryError) as missing_tracing:
        asyncio.run(missing_tracing_call())
    assert missing_tracing.value.code == "langsmith_tracing_required"

    monkeypatch.setenv("LANGSMITH_TRACING", "1")
    with pytest.raises(entry.DellAgentServerEntryError) as tracing_alias:
        asyncio.run(missing_tracing_call())
    assert tracing_alias.value.code == "langsmith_tracing_required"

    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    with pytest.raises(entry.DellAgentServerEntryError) as missing_pat:
        asyncio.run(missing_tracing_call())
    assert missing_pat.value.code == "langsmith_api_key_required"

    monkeypatch.setenv("LANGSMITH_API_KEY", "test-only-not-a-real-key")
    with pytest.raises(entry.DellAgentServerEntryError) as missing_project:
        asyncio.run(missing_tracing_call())
    assert missing_project.value.code == "langsmith_project_mismatch"


def test_execution_requires_one_deployment_owned_langsmith_project(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "test-only-not-a-real-key")
    runtime = _ExecutionRuntime(_context())

    monkeypatch.setenv("LANGSMITH_PROJECT", "wrong-project")

    async def call(config: dict[str, Any]) -> None:
        async with entry.dell_reference_vertical_graph(config, runtime):
            pass

    with pytest.raises(entry.DellAgentServerEntryError) as wrong_project:
        asyncio.run(call(_config()))
    assert wrong_project.value.code == "langsmith_project_mismatch"

    monkeypatch.setenv("LANGSMITH_PROJECT", entry.DELL_LANGSMITH_PROJECT)
    config: dict[str, Any] = _config()
    config["configurable"]["__langsmith_project__"] = "per-run-replica"
    with pytest.raises(entry.DellAgentServerEntryError) as run_override:
        asyncio.run(call(config))
    assert run_override.value.code == "langsmith_run_project_override_forbidden"


def test_execution_requires_langsmith_input_and_output_redaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "test-only-not-a-real-key")
    monkeypatch.setenv("LANGSMITH_PROJECT", entry.DELL_LANGSMITH_PROJECT)
    monkeypatch.delenv("LANGSMITH_HIDE_INPUTS", raising=False)
    monkeypatch.delenv("LANGSMITH_HIDE_OUTPUTS", raising=False)
    runtime = _ExecutionRuntime(_context())

    async def call() -> None:
        async with entry.dell_reference_vertical_graph(_config(), runtime):
            pass

    with pytest.raises(entry.DellAgentServerEntryError) as missing_inputs:
        asyncio.run(call())
    assert missing_inputs.value.code == "langsmith_inputs_must_be_hidden"

    monkeypatch.setenv("LANGSMITH_HIDE_INPUTS", "true")
    with pytest.raises(entry.DellAgentServerEntryError) as missing_outputs:
        asyncio.run(call())
    assert missing_outputs.value.code == "langsmith_outputs_must_be_hidden"

    monkeypatch.setenv("LANGSMITH_HIDE_INPUTS", "1")
    monkeypatch.setenv("LANGSMITH_HIDE_OUTPUTS", "true")
    with pytest.raises(entry.DellAgentServerEntryError) as truthy_alias:
        asyncio.run(call())
    assert truthy_alias.value.code == "langsmith_inputs_must_be_hidden"

    monkeypatch.setenv("LANGSMITH_HIDE_INPUTS", "true")
    monkeypatch.setenv("LANGSMITH_HIDE_OUTPUTS", "1")
    with pytest.raises(entry.DellAgentServerEntryError) as output_alias:
        asyncio.run(call())
    assert output_alias.value.code == "langsmith_outputs_must_be_hidden"


def test_execution_requires_exact_approved_runtime_mount_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "test-only-not-a-real-key")
    monkeypatch.setenv("LANGSMITH_PROJECT", entry.DELL_LANGSMITH_PROJECT)
    monkeypatch.setenv("LANGSMITH_HIDE_INPUTS", "true")
    monkeypatch.setenv("LANGSMITH_HIDE_OUTPUTS", "true")
    monkeypatch.delenv("FIN_REPO_ROOT", raising=False)
    monkeypatch.setattr(
        entry,
        "_require_durable_execution_binding",
        lambda _identity, **_kwargs: None,
    )

    async def exercise() -> None:
        async with entry.dell_reference_vertical_graph(
            _config(), _ExecutionRuntime(_context())
        ):
            pass

    with pytest.raises(entry.DellAgentServerEntryError) as failure:
        asyncio.run(exercise())
    assert failure.value.code == "approved_repository_root_missing"


def test_durable_identity_guard_requires_uri_and_exact_persisted_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity = entry.bind_agent_server_identity(
        config=_config(), run_context=_context()
    )
    monkeypatch.delenv(entry.FIN_RUNTIME_POSTGRES_URI_ENV, raising=False)

    with pytest.raises(entry.DellAgentServerEntryError) as missing_uri:
        entry._read_durable_run_binding(identity)
    assert missing_uri.value.code == "fin_runtime_postgres_uri_required"

    monkeypatch.setattr(
        entry,
        "_read_durable_run_binding",
        lambda _identity: _persisted_projection(),
    )
    entry._require_durable_execution_binding(
        identity,
        execution_profile="zero_model_control_plane_v1",
    )

    with pytest.raises(entry.DellAgentServerEntryError) as profile_conflict:
        entry._require_durable_execution_binding(
            identity,
            execution_profile="product",
        )
    assert (
        profile_conflict.value.code
        == "fin_server_run_execution_profile_conflict"
    )

    monkeypatch.setattr(
        entry,
        "_read_durable_run_binding",
        lambda _identity: _persisted_projection(
            binding_overrides={"server_run_id": "another-server-run"}
        ),
    )
    with pytest.raises(entry.DellAgentServerEntryError) as conflict:
        entry._require_durable_execution_binding(
            identity,
            execution_profile="zero_model_control_plane_v1",
        )
    assert conflict.value.code == "fin_server_run_durable_binding_conflict"


def test_execution_rejects_pending_or_corrupt_reconciled_lifecycle() -> None:
    identity = entry.bind_agent_server_identity(
        config=_config(), run_context=_context()
    )

    original = entry._read_durable_run_binding
    try:
        entry._read_durable_run_binding = lambda _identity: _persisted_projection(
            state="PENDING"
        )
        with pytest.raises(entry.DellAgentServerEntryError) as pending:
            entry._require_durable_execution_binding(
                identity,
                execution_profile="zero_model_control_plane_v1",
            )
        assert (
            pending.value.code
            == "fin_server_run_create_lifecycle_not_reconciled"
        )

        entry._read_durable_run_binding = lambda _identity: _persisted_projection(
            reconciled_overrides={"final_binding_digest": "0" * 64}
        )
        with pytest.raises(entry.DellAgentServerEntryError) as corrupt:
            entry._require_durable_execution_binding(
                identity,
                execution_profile="zero_model_control_plane_v1",
            )
        assert corrupt.value.code == "fin_server_run_create_lifecycle_conflict"
    finally:
        entry._read_durable_run_binding = original


def test_missing_durable_binding_opens_no_data_or_mcp_resources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity = entry.bind_agent_server_identity(
        config=_config(), run_context=_context()
    )
    opened = 0

    @asynccontextmanager
    async def forbidden_data_open(*_args: Any, **_kwargs: Any) -> AsyncIterator[Any]:
        nonlocal opened
        opened += 1
        raise AssertionError("data composition must remain closed")
        yield  # pragma: no cover

    monkeypatch.setattr(entry, "_read_durable_run_binding", lambda _identity: None)
    monkeypatch.setattr(
        entry,
        "open_dell_approved_data_composition",
        forbidden_data_open,
    )

    async def exercise() -> None:
        async with entry._open_execution_dependencies(
            identity,
            DellAgentServerRunContext.model_validate(_context()),
            execution_profile="zero_model_control_plane_v1",
        ):
            pass

    with pytest.raises(entry.DellAgentServerEntryError) as failure:
        asyncio.run(exercise())
    assert failure.value.code == "fin_server_run_durable_binding_missing"
    assert opened == 0


def test_identity_binding_keeps_domain_and_server_namespaces_separate() -> None:
    identity = entry.bind_agent_server_identity(
        config=_config(),
        run_context=_context(),
    )

    assert identity.agent_session_id == "fin-session-001"
    assert identity.research_run_id == "fin-research-run-001"
    assert identity.run_invocation_id == "fin-run-invocation-001"
    assert identity.server_thread_id == "019-server-thread"
    assert identity.server_run_id == "019-server-run"
    assert identity.agent_session_to_server_thread == "one_to_one"
    assert identity.research_run_to_server_runs == "one_to_many"
    assert identity.run_invocation_to_server_run == "one_to_one"
    assert identity.action_attempt_to_server_task == "no_mapping_fin_receipt_only"


def test_server_run_id_is_read_from_configurable_not_top_level() -> None:
    config: dict[str, Any] = _config()
    config["run_id"] = "wrong-top-level-value"

    identity = entry.bind_agent_server_identity(
        config=config,
        run_context=_context(),
    )

    assert identity.server_run_id == "019-server-run"


def test_context_and_server_identity_are_both_required() -> None:
    with pytest.raises(entry.DellAgentServerEntryError) as missing_context:
        entry.bind_agent_server_identity(config=_config(), run_context={})
    assert missing_context.value.code == "fin_run_context_invalid"

    with pytest.raises(entry.DellAgentServerEntryError) as missing_server_run:
        entry.bind_agent_server_identity(
            config={"configurable": {"thread_id": "server-thread"}},
            run_context=_context(),
        )
    assert missing_server_run.value.code == "agent_server_run_id_missing"


def test_authorized_resources_are_scoped_to_one_factory_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lifecycle: list[str] = []

    def unavailable(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("test dependency must not execute")

    dependencies = DellReferenceVerticalDependencies(
        foundation_binder=unavailable,
        planner_tool_capabilities=entry._schema_only_capability_projection(),
        planner_source_route_catalog=entry._schema_only_source_route_catalog(),
        planner_agent=unavailable,
        evidence_tool=unavailable,
        finance_tool=unavailable,
        specialist_agent=unavailable,
        counter_agent=unavailable,
        lead_agent=unavailable,
    )

    @asynccontextmanager
    async def opened(
        identity: entry.DellAgentServerIdentityBinding,
        context: DellAgentServerRunContext,
        *,
        execution_profile: str,
    ) -> AsyncIterator[DellReferenceVerticalDependencies]:
        assert identity.research_run_id == context.research_run_id
        assert execution_profile == "product"
        lifecycle.append("opened")
        try:
            yield dependencies
        finally:
            lifecycle.append("closed")

    monkeypatch.setattr(entry, "_open_execution_dependencies", opened)
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "test-only-not-a-real-key")
    monkeypatch.setenv("LANGSMITH_PROJECT", entry.DELL_LANGSMITH_PROJECT)
    monkeypatch.setenv("LANGSMITH_HIDE_INPUTS", "true")
    monkeypatch.setenv("LANGSMITH_HIDE_OUTPUTS", "true")

    async def exercise() -> None:
        async with entry.dell_reference_vertical_graph(
            _config(), _ExecutionRuntime(_context())
        ) as graph:
            assert lifecycle == ["opened"]
            assert graph.checkpointer is None
            assert graph.store is None

    asyncio.run(exercise())
    assert lifecycle == ["opened", "closed"]


def test_research_run_binding_does_not_compare_to_server_thread_id() -> None:
    called: list[str] = []

    def foundation(request: dict[str, Any]) -> dict[str, Any]:
        called.append(request["run_id"])
        return {"ok": True}

    def unavailable(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("not called")

    dependencies = DellReferenceVerticalDependencies(
        foundation_binder=foundation,
        planner_tool_capabilities=entry._schema_only_capability_projection(),
        planner_source_route_catalog=entry._schema_only_source_route_catalog(),
        planner_agent=unavailable,
        evidence_tool=unavailable,
        finance_tool=unavailable,
        specialist_agent=unavailable,
        counter_agent=unavailable,
        lead_agent=unavailable,
    )
    identity = entry.bind_agent_server_identity(
        config=_config(), run_context=_context()
    )
    bound = entry._bind_dependencies_to_identity(dependencies, identity)

    assert bound.foundation_binder({"run_id": "fin-research-run-001"}) == {
        "ok": True
    }
    assert called == ["fin-research-run-001"]
    with pytest.raises(
        entry.DellAgentServerEntryError,
        match="fin_research_run_id_mismatch",
    ):
        bound.foundation_binder({"run_id": "019-server-thread"})
