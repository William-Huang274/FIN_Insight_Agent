"""Import-safe LangGraph Agent Server entry for the Dell reference vertical.

This is the only product serving seam.  It deliberately contains no direct
invoke path, application-owned saver/store, HTTP server, queue, or SQLite
runtime.  Agent Server owns those concerns and injects its checkpointer/store.

The current data/source authority successor is still Owner-gated.  Until it is
approved, execution stops before provider, MCP, corpus, or database resources
are opened.  Schema and state-read calls still receive the exact graph
topology, using dependencies that cannot execute.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import replace
from typing import Any, Literal

from langchain_core.runnables import RunnableConfig
from langgraph_sdk.runtime import ServerRuntime
from pydantic import BaseModel, ConfigDict, Field

from .dell_reference_vertical_contracts import canonical_sha256
from .dell_reference_vertical_graph import (
    DellAgentServerRunContext,
    DellReferenceVerticalDependencies,
    build_dell_reference_vertical_state_graph,
)


DELL_AGENT_SERVER_GRAPH_ID = "dell_reference_vertical"
DELL_LANGSMITH_PROJECT = "fin-insight-dell-reference-vertical"


class DellAgentServerEntryError(RuntimeError):
    """Typed, secret-free Agent Server composition failure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class DellAgentServerIdentityBinding(BaseModel):
    """Validated identity relation observed for one factory lifecycle.

    This value is deliberately not called a durable receipt.  Agent Server
    persists its own thread/run records; the product ingress/BFF must persist
    the FIN-to-server relation when a run is created.  The factory validates
    the same relation before opening any execution resource, but it must not
    pretend that a closure-local model is durable state.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["fin_ia_dell_agent_server_identity_binding_v1_0"]
    agent_session_id: str = Field(min_length=1, max_length=180)
    research_run_id: str = Field(min_length=1, max_length=180)
    run_invocation_id: str = Field(min_length=1, max_length=180)
    server_thread_id: str = Field(min_length=1, max_length=180)
    server_run_id: str = Field(min_length=1, max_length=180)
    agent_session_to_server_thread: Literal["one_to_one"] = "one_to_one"
    research_run_to_server_runs: Literal["one_to_many"] = "one_to_many"
    run_invocation_to_server_run: Literal["one_to_one"] = "one_to_one"
    action_attempt_to_server_task: Literal["no_mapping_fin_receipt_only"] = (
        "no_mapping_fin_receipt_only"
    )


def _required_config_identifier(value: Any, *, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DellAgentServerEntryError(code)
    return value.strip()


def bind_agent_server_identity(
    *,
    config: Mapping[str, Any],
    run_context: Any,
) -> DellAgentServerIdentityBinding:
    """Validate independent FIN identities against server-assigned IDs.

    Agent Server 0.13.3 supplies both identifiers in ``configurable`` during
    the ``threads.create_run`` factory call.  The server run identifier is not
    a top-level RunnableConfig key and must never be inferred from the thread
    or any FIN identifier.
    """

    try:
        context = DellAgentServerRunContext.model_validate(run_context)
    except Exception as exc:
        raise DellAgentServerEntryError("fin_run_context_invalid") from exc
    configurable = config.get("configurable")
    if not isinstance(configurable, Mapping):
        raise DellAgentServerEntryError("agent_server_configurable_missing")
    return DellAgentServerIdentityBinding(
        schema_version="fin_ia_dell_agent_server_identity_binding_v1_0",
        agent_session_id=context.agent_session_id,
        research_run_id=context.research_run_id,
        run_invocation_id=context.run_invocation_id,
        server_thread_id=_required_config_identifier(
            configurable.get("thread_id"),
            code="agent_server_thread_id_missing",
        ),
        server_run_id=_required_config_identifier(
            configurable.get("run_id"),
            code="agent_server_run_id_missing",
        ),
    )


def _schema_only_capability_projection() -> dict[str, Any]:
    """Return shape-valid metadata that is unreachable from execution."""

    unsigned = {
        "schema_version": "fin_ia_dell_planner_tool_capabilities_v1_0",
        "snapshot_id": "agent-server-schema-introspection-only",
        "mart_sha256": canonical_sha256(
            {"kind": "agent_server_schema_introspection_only"}
        ),
        "data_cutoff_kind": "latest_through_observation_accepted_at",
        "data_latest_through_accepted_at": "1970-01-01T00:00:00+00:00",
        "point_in_time_claimed": False,
        "finance": {
            "supported_tickers": ["DELL"],
            "metrics": [
                {
                    "metric_id": "revenue",
                    "unit_family": "monetary",
                    "availability": "direct_observation",
                    "formula": None,
                    "observed_tickers": ["DELL"],
                }
            ],
            "canonical_granularities": ["quarter_discrete"],
            "date_format": "YYYY-MM-DD",
            "latest_query_rule": (
                "omit_period_bounds_and_fiscal_years_for_latest_available_observations"
            ),
            "maximum_fiscal_year_count": 4,
            "non_capabilities": ["schema_introspection_is_not_execution"],
            "derived_metric_rule": (
                "derived_metrics_are_computed_by_the_existing_fact_executor_and_may_return_typed_gap_when_inputs_do_not_align"
            ),
        },
        "evidence_routes": [
            {
                "source_route": route,
                "semantics": "Schema introspection only; execution is unavailable.",
                "candidate_is_not_evidence": True,
            }
            for route in ("reviewed_first", "local_only", "external_required")
        ],
    }
    return {**unsigned, "projection_digest": canonical_sha256(unsigned)}


def _schema_only_unavailable(*_args: Any, **_kwargs: Any) -> Any:
    raise DellAgentServerEntryError("schema_introspection_graph_not_executable")


def _schema_only_dependencies() -> DellReferenceVerticalDependencies:
    return DellReferenceVerticalDependencies(
        foundation_binder=_schema_only_unavailable,
        planner_tool_capabilities=_schema_only_capability_projection(),
        planner_agent=_schema_only_unavailable,
        evidence_tool=_schema_only_unavailable,
        finance_tool=_schema_only_unavailable,
        specialist_agent=_schema_only_unavailable,
        counter_agent=_schema_only_unavailable,
        lead_agent=_schema_only_unavailable,
    )


def _compile_graph(dependencies: DellReferenceVerticalDependencies) -> Any:
    graph = build_dell_reference_vertical_state_graph(dependencies=dependencies)
    return graph.compile(name=DELL_AGENT_SERVER_GRAPH_ID)


_SCHEMA_ONLY_GRAPH = _compile_graph(_schema_only_dependencies())


def _require_langsmith_execution_environment(config: Mapping[str, Any]) -> None:
    """Enforce one deployment-owned LangSmith trace destination.

    Agent Server 0.13.3 already traces through its deployment environment.
    A run-level project override creates an additional trace replica, so the
    product seam rejects it instead of consuming quota twice or allowing trace
    destinations to drift by caller.
    """

    tracing = os.environ.get("LANGSMITH_TRACING", "").strip().lower()
    if tracing not in {"1", "true"}:
        raise DellAgentServerEntryError("langsmith_tracing_required")
    if not os.environ.get("LANGSMITH_API_KEY", "").strip():
        raise DellAgentServerEntryError("langsmith_api_key_required")
    project = os.environ.get("LANGSMITH_PROJECT", "").strip()
    if project != DELL_LANGSMITH_PROJECT:
        raise DellAgentServerEntryError("langsmith_project_mismatch")
    configurable = config.get("configurable")
    if isinstance(configurable, Mapping) and configurable.get(
        "__langsmith_project__"
    ) is not None:
        raise DellAgentServerEntryError("langsmith_run_project_override_forbidden")


def _bind_dependencies_to_identity(
    dependencies: DellReferenceVerticalDependencies,
    identity: DellAgentServerIdentityBinding,
) -> DellReferenceVerticalDependencies:
    foundation_binder = dependencies.foundation_binder

    def bound_foundation_binder(request: Mapping[str, Any]) -> Mapping[str, Any]:
        if request.get("run_id") != identity.research_run_id:
            raise DellAgentServerEntryError("fin_research_run_id_mismatch")
        return foundation_binder(request)

    return replace(dependencies, foundation_binder=bound_foundation_binder)


@asynccontextmanager
async def _open_execution_dependencies(
    _identity: DellAgentServerIdentityBinding,
    _context: DellAgentServerRunContext,
) -> AsyncIterator[DellReferenceVerticalDependencies]:
    """Hard gate awaiting the Owner-approved RC-S3-105 data successor.

    This context-manager boundary is where the approved composition will later
    open per-run provider/MCP/data resources and close them in ``finally``.
    There is intentionally no legacy CLI, no-op, or local runtime fallback.
    """

    raise DellAgentServerEntryError("dell_execution_data_authority_not_approved")
    yield  # pragma: no cover - keeps this an async context manager


@asynccontextmanager
async def dell_reference_vertical_graph(
    config: RunnableConfig,
    runtime: ServerRuntime[DellAgentServerRunContext],
) -> AsyncIterator[Any]:
    """Yield the one Dell graph with Agent Server-owned persistence.

    Agent Server invokes this factory for schema/state reads as well as runs.
    Only ``threads.create_run`` has an execution runtime; all other calls get
    the same topology without opening configuration, credentials, MCP, corpus,
    or database resources.
    """

    execution_runtime = runtime.execution_runtime
    if execution_runtime is None:
        yield _SCHEMA_ONLY_GRAPH
        return

    _require_langsmith_execution_environment(config)
    identity = bind_agent_server_identity(
        config=config,
        run_context=execution_runtime.context,
    )
    context = DellAgentServerRunContext.model_validate(execution_runtime.context)
    async with _open_execution_dependencies(identity, context) as dependencies:
        yield _compile_graph(_bind_dependencies_to_identity(dependencies, identity))


__all__ = [
    "DELL_AGENT_SERVER_GRAPH_ID",
    "DELL_LANGSMITH_PROJECT",
    "DellAgentServerEntryError",
    "DellAgentServerIdentityBinding",
    "bind_agent_server_identity",
    "dell_reference_vertical_graph",
]
