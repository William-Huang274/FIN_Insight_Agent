"""Import-safe LangGraph Agent Server entry for the Dell reference vertical.

This is the only product serving seam.  It deliberately contains no direct
invoke path, application-owned saver/store, HTTP server, queue, or SQLite
runtime.  Agent Server owns those concerns and injects its checkpointer/store.

The Owner-approved data/source successor is opened only for execution calls.
Schema and state-read calls still receive the exact graph topology without
opening MCP, corpus or database resources.  Model transport remains separately
gated and is not authorized by the data decision.
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
from .dell_agent_server_data_composition import (
    DellApprovedDataCompositionError,
    open_dell_approved_data_composition,
)
from .dell_agent_server_identity import (
    DELL_AGENT_SERVER_ASSISTANT_ID,
    DellAgentServerIdentityStoreError,
    PersistedRunInvocationBinding,
    PostgresDellAgentServerIdentityRepository,
)
from .dell_reference_vertical_graph import (
    DellAgentServerRunContext,
    DellReferenceVerticalDependencies,
    build_dell_reference_vertical_state_graph,
)
from .dell_zero_model_graph_qualification import (
    DellExecutionProfile,
    DellZeroModelQualificationError,
    PRODUCT_EXECUTION_PROFILE,
    require_execution_profile,
)


DELL_AGENT_SERVER_GRAPH_ID = "dell_reference_vertical"
DELL_LANGSMITH_PROJECT = "fin-insight-dell-reference-vertical"
FIN_RUNTIME_POSTGRES_URI_ENV = "FIN_RUNTIME_POSTGRES_URI"
DELL_EXECUTION_PROFILE_ENV = "FINSIGHT_DELL_EXECUTION_PROFILE"


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
    except Exception:
        raise DellAgentServerEntryError("fin_run_context_invalid") from None
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


def _schema_only_source_route_catalog() -> dict[str, Any]:
    route = {
        "minimum_route_obligation_id": "route:schema-only:required-reviewed",
        "coverage_obligation_id": "schema-only",
        "requirement": "required",
        "intent_kind": "reviewed_evidence",
        "semantic_source_family_refs": ["schema-only-family"],
        "entity_refs": [],
        "period_intents": [],
        "required_authority_refs": ["schema-only-read"],
    }
    unsigned = {
        "schema_version": "fin_ia_dell_provider_source_route_catalog_v1_0",
        "inventory_snapshot_digest": canonical_sha256(
            {"kind": "schema_only_inventory"}
        ),
        "baseline_source_plan_digest": canonical_sha256(
            {"kind": "schema_only_baseline"}
        ),
        "routes": [route],
        "physical_selectors_exposed": False,
        "answer_free": True,
    }
    return {**unsigned, "catalog_digest": canonical_sha256(unsigned)}


def _schema_only_unavailable(*_args: Any, **_kwargs: Any) -> Any:
    raise DellAgentServerEntryError("schema_introspection_graph_not_executable")


def _schema_only_dependencies() -> DellReferenceVerticalDependencies:
    return DellReferenceVerticalDependencies(
        foundation_binder=_schema_only_unavailable,
        planner_tool_capabilities=_schema_only_capability_projection(),
        planner_source_route_catalog=_schema_only_source_route_catalog(),
        planner_agent=_schema_only_unavailable,
        evidence_tool=_schema_only_unavailable,
        finance_tool=_schema_only_unavailable,
        specialist_agent=_schema_only_unavailable,
        counter_agent=_schema_only_unavailable,
        lead_agent=_schema_only_unavailable,
    )


def _compile_graph(
    dependencies: DellReferenceVerticalDependencies,
    *,
    execution_profile: DellExecutionProfile = PRODUCT_EXECUTION_PROFILE,
) -> Any:
    graph = build_dell_reference_vertical_state_graph(
        dependencies=dependencies,
        execution_profile=execution_profile,
    )
    return graph.compile(name=DELL_AGENT_SERVER_GRAPH_ID)


_SCHEMA_ONLY_GRAPH = _compile_graph(_schema_only_dependencies())


def _require_execution_profile() -> DellExecutionProfile:
    raw = os.environ.get(DELL_EXECUTION_PROFILE_ENV, PRODUCT_EXECUTION_PROFILE)
    try:
        return require_execution_profile(raw)
    except DellZeroModelQualificationError:
        raise DellAgentServerEntryError("dell_execution_profile_invalid") from None


def _require_langsmith_execution_environment(config: Mapping[str, Any]) -> None:
    """Enforce one deployment-owned LangSmith trace destination.

    Agent Server 0.13.3 already traces through its deployment environment.
    A run-level project override creates an additional trace replica, so the
    product seam rejects it instead of consuming quota twice or allowing trace
    destinations to drift by caller.
    """

    tracing = os.environ.get("LANGSMITH_TRACING", "").strip().lower()
    if tracing != "true":
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
    # The pinned LangSmith client enables this control only for the literal
    # string ``true``.  Accepting truthy aliases here would let the entry gate
    # pass while the tracer still exported payloads.
    if os.environ.get("LANGSMITH_HIDE_INPUTS", "").strip().lower() != "true":
        raise DellAgentServerEntryError("langsmith_inputs_must_be_hidden")
    if os.environ.get("LANGSMITH_HIDE_OUTPUTS", "").strip().lower() != "true":
        raise DellAgentServerEntryError("langsmith_outputs_must_be_hidden")


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


def _read_durable_run_binding(
    identity: DellAgentServerIdentityBinding,
) -> PersistedRunInvocationBinding | None:
    """Read FIN-owned identity state without exposing its credential or DSN."""

    uri = os.environ.get(FIN_RUNTIME_POSTGRES_URI_ENV, "").strip()
    if not uri:
        raise DellAgentServerEntryError("fin_runtime_postgres_uri_required")
    try:
        import psycopg

        repository = PostgresDellAgentServerIdentityRepository(
            lambda: psycopg.connect(
                uri,
                connect_timeout=5,
                application_name="fin_dell_agent_server_identity_guard",
            )
        )
        return repository.get_run_invocation(
            run_invocation_id=identity.run_invocation_id
        )
    except DellAgentServerIdentityStoreError as exc:
        raise DellAgentServerEntryError(
            f"fin_durable_identity_guard_failed:{exc.code}"
        ) from None
    except Exception:
        raise DellAgentServerEntryError(
            "fin_durable_identity_guard_read_failed"
        ) from None


def _require_durable_execution_binding(
    identity: DellAgentServerIdentityBinding,
) -> None:
    """Reject an unbound or spoofed server run before opening any data port."""

    persisted = _read_durable_run_binding(identity)
    if persisted is None:
        raise DellAgentServerEntryError(
            "fin_server_run_durable_binding_missing"
        )
    if (
        persisted.agent_session_id != identity.agent_session_id
        or persisted.research_run_id != identity.research_run_id
        or persisted.run_invocation_id != identity.run_invocation_id
        or persisted.server_thread_id != identity.server_thread_id
        or persisted.server_run_id != identity.server_run_id
        or persisted.assistant_id != DELL_AGENT_SERVER_ASSISTANT_ID
    ):
        raise DellAgentServerEntryError(
            "fin_server_run_durable_binding_conflict"
        )


@asynccontextmanager
async def _open_execution_dependencies(
    identity: DellAgentServerIdentityBinding,
    context: DellAgentServerRunContext,
) -> AsyncIterator[DellReferenceVerticalDependencies]:
    """Open the exact approved readers and one MCP lifecycle for this run.

    The Owner decision authorizes only zero-network data composition.  Model
    callables remain fail-closed until a separate paid-execution decision.
    """

    if identity.research_run_id != context.research_run_id:
        raise DellAgentServerEntryError("fin_research_run_id_mismatch")
    _require_durable_execution_binding(identity)
    try:
        with open_dell_approved_data_composition(
            run_invocation_id=identity.run_invocation_id
        ) as composition:
            yield composition.dependencies
    except DellApprovedDataCompositionError as exc:
        raise DellAgentServerEntryError(exc.code) from None


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

    execution_profile = _require_execution_profile()
    _require_langsmith_execution_environment(config)
    identity = bind_agent_server_identity(
        config=config,
        run_context=execution_runtime.context,
    )
    context = DellAgentServerRunContext.model_validate(execution_runtime.context)
    async with _open_execution_dependencies(identity, context) as dependencies:
        yield _compile_graph(
            _bind_dependencies_to_identity(dependencies, identity),
            execution_profile=execution_profile,
        )


__all__ = [
    "DELL_AGENT_SERVER_GRAPH_ID",
    "DELL_EXECUTION_PROFILE_ENV",
    "DELL_LANGSMITH_PROJECT",
    "FIN_RUNTIME_POSTGRES_URI_ENV",
    "DellAgentServerEntryError",
    "DellAgentServerIdentityBinding",
    "bind_agent_server_identity",
    "dell_reference_vertical_graph",
]
