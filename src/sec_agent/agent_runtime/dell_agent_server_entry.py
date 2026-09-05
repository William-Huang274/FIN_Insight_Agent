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
import json
from threading import Lock
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any, Literal

from langchain_core.runnables import RunnableConfig
from langgraph_sdk.runtime import ServerRuntime
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from .dell_reference_vertical_contracts import canonical_sha256
from .dell_agent_server_data_composition import (
    DellApprovedDataCompositionError,
    open_dell_approved_data_composition,
)
from .dell_agent_server_identity import (
    DELL_AGENT_SERVER_ASSISTANT_ID,
    DellAgentServerIdentityStoreError,
    PersistedExecutableRunBinding,
    PostgresDellAgentServerIdentityRepository,
    persisted_run_binding_digest,
)
from .dell_reference_vertical_graph import (
    DellAgentServerRunContext,
    DellReferenceVerticalDependencies,
    build_dell_reference_vertical_state_graph,
)
from .deepseek_structured_agents import (
    DeepSeekStructuredAgentAdapter,
    DeepSeekStructuredAgentError,
    load_deepseek_structured_agent_config,
)
from .dell_specialist_agentic_composition import (
    DellSpecialistAgenticCompositionError,
    open_dell_specialist_receipted_composition,
)
from .dell_specialist_agentic_graph import (
    DellSpecialistAgenticDependencies,
    build_dell_specialist_agentic_state_graph,
)
from .dell_specialist_paid_shadow import (
    DELL_IMPLEMENTATION_COMMIT_ENV,
    DELL_Q1_PAID_SHADOW_AUTHORITY_ENV,
    DELL_Q1_PAID_SHADOW_SERVING_MODE,
    DELL_Q1_REVIEW_SERVING_MODE,
    DellSpecialistPaidShadowError,
    build_public_model_audit_sink,
    build_private_model_audit_sink,
    file_sha256,
    load_dell_q1_paid_shadow_authority,
    require_data_authority_binding,
    require_runtime_authority_binding,
)
from .dell_workpaper_review_graph import build_dell_workpaper_review_graph
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
DELL_SERVING_MODE_ENV = "FINSIGHT_DELL_SERVING_MODE"
DELL_REFERENCE_VERTICAL_SERVING_MODE = "reference_vertical"


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

_SCHEMA_ONLY_SPECIALIST_GRAPH = build_dell_specialist_agentic_state_graph(
    dependencies=DellSpecialistAgenticDependencies(
        model_turn=_schema_only_unavailable,
        evidence_tool=_schema_only_unavailable,
        finance_tool=_schema_only_unavailable,
        turn_source="provider_model",
    )
).compile(name=DELL_AGENT_SERVER_GRAPH_ID)
_SCHEMA_ONLY_REVIEW_GRAPH = build_dell_workpaper_review_graph(
    expected_input=None, seed_state=None, run_child=_schema_only_unavailable,
).compile(name=DELL_AGENT_SERVER_GRAPH_ID)


def _require_serving_mode() -> Literal[
    "reference_vertical",
    "q1_specialist_paid_shadow_v1",
    "q1_workpaper_review_repair_v1",
]:
    raw = os.environ.get(
        DELL_SERVING_MODE_ENV,
        DELL_REFERENCE_VERTICAL_SERVING_MODE,
    ).strip()
    if raw not in {
        DELL_REFERENCE_VERTICAL_SERVING_MODE,
        DELL_Q1_PAID_SHADOW_SERVING_MODE,
        DELL_Q1_REVIEW_SERVING_MODE,
    }:
        raise DellAgentServerEntryError("dell_serving_mode_invalid")
    return raw  # type: ignore[return-value]


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
) -> PersistedExecutableRunBinding | None:
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
        return repository.get_execution_binding_with_lifecycle(
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
    *,
    execution_profile: DellExecutionProfile,
) -> None:
    """Reject an unbound or spoofed server run before opening any data port."""

    projection = _read_durable_run_binding(identity)
    if projection is None:
        raise DellAgentServerEntryError(
            "fin_server_run_durable_binding_missing"
        )
    persisted = projection.binding
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
    lifecycle = projection.lifecycle
    if lifecycle is None or lifecycle.reconciled is None:
        raise DellAgentServerEntryError(
            "fin_server_run_create_lifecycle_not_reconciled"
        )
    reconciled = lifecycle.reconciled
    if (
        lifecycle.pending.execution_profile != execution_profile
        or reconciled.execution_profile != execution_profile
    ):
        raise DellAgentServerEntryError(
            "fin_server_run_execution_profile_conflict"
        )
    if (
        reconciled.run_invocation_id != persisted.run_invocation_id
        or reconciled.bound_run_invocation_id != persisted.run_invocation_id
        or reconciled.research_run_id != persisted.research_run_id
        or reconciled.agent_session_id != persisted.agent_session_id
        or reconciled.invocation_ordinal != persisted.invocation_ordinal
        or reconciled.canonical_invocation_kind
        != persisted.canonical_invocation_kind
        or reconciled.server_invocation_kind != persisted.server_invocation_kind
        or reconciled.server_thread_id != persisted.server_thread_id
        or reconciled.server_run_id != persisted.server_run_id
        or reconciled.assistant_id != persisted.assistant_id
        or reconciled.run_invocation_identity_digest
        != persisted.invocation_identity_digest
        or reconciled.server_run_status != persisted.first_server_status
        or reconciled.final_binding_digest
        != persisted_run_binding_digest(persisted)
    ):
        raise DellAgentServerEntryError(
            "fin_server_run_create_lifecycle_conflict"
        )


@asynccontextmanager
async def _open_execution_dependencies(
    identity: DellAgentServerIdentityBinding,
    context: DellAgentServerRunContext,
    *,
    execution_profile: DellExecutionProfile,
) -> AsyncIterator[DellReferenceVerticalDependencies]:
    """Open the exact approved readers and one MCP lifecycle for this run.

    The Owner decision authorizes only zero-network data composition.  Model
    callables remain fail-closed until a separate paid-execution decision.
    """

    if identity.research_run_id != context.research_run_id:
        raise DellAgentServerEntryError("fin_research_run_id_mismatch")
    _require_durable_execution_binding(
        identity,
        execution_profile=execution_profile,
    )
    try:
        with open_dell_approved_data_composition(
            run_invocation_id=identity.run_invocation_id
        ) as composition:
            yield composition.dependencies
    except DellApprovedDataCompositionError as exc:
        raise DellAgentServerEntryError(exc.code) from None


@asynccontextmanager
async def _open_q1_paid_shadow_graph(
    identity: DellAgentServerIdentityBinding,
    context: DellAgentServerRunContext,
    *,
    execution_profile: DellExecutionProfile,
) -> AsyncIterator[Any]:
    """Open the one Owner-authorized DeepSeek Specialist graph."""

    if execution_profile != PRODUCT_EXECUTION_PROFILE:
        raise DellAgentServerEntryError(
            "paid_shadow_requires_product_execution_profile"
        )
    if identity.research_run_id != context.research_run_id:
        raise DellAgentServerEntryError("fin_research_run_id_mismatch")
    _require_durable_execution_binding(
        identity,
        execution_profile=execution_profile,
    )
    authority_path = os.environ.get(
        DELL_Q1_PAID_SHADOW_AUTHORITY_ENV,
        "",
    ).strip()
    implementation_commit = os.environ.get(
        DELL_IMPLEMENTATION_COMMIT_ENV,
        "",
    ).strip()
    repository_root = os.environ.get("FIN_REPO_ROOT", "").strip()
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not authority_path:
        raise DellAgentServerEntryError("paid_shadow_authority_path_required")
    if not implementation_commit:
        raise DellAgentServerEntryError(
            "paid_shadow_implementation_commit_required"
        )
    if not repository_root:
        raise DellAgentServerEntryError("paid_shadow_repository_root_required")
    if not api_key:
        raise DellAgentServerEntryError("deepseek_api_key_required")
    try:
        authority = load_dell_q1_paid_shadow_authority(authority_path)
        if authority.serving_mode != _require_serving_mode():
            raise DellSpecialistPaidShadowError("paid_shadow_serving_mode_authority_mismatch")
        require_runtime_authority_binding(
            authority,
            agent_session_id=identity.agent_session_id,
            research_run_id=identity.research_run_id,
            run_invocation_id=identity.run_invocation_id,
            implementation_commit=implementation_commit,
        )
        config_path = (
            Path(repository_root)
            / "configs"
            / "research"
            / authority.deepseek_config_filename
        )
        if file_sha256(config_path) != authority.deepseek_config_sha256:
            raise DellSpecialistPaidShadowError(
                "paid_shadow_deepseek_config_binding_invalid"
            )
        model_config = load_deepseek_structured_agent_config(config_path)
        budget = model_config.token_budget_basis["specialist"]
        if (
            model_config.provider != authority.provider
            or model_config.model != authority.model
            or budget.max_input_characters
            != authority.max_input_characters_per_turn
            or budget.max_output_tokens
            != authority.max_output_tokens_per_turn
            or budget.timeout_seconds != authority.timeout_seconds_per_turn
            or budget.max_transport_attempts
            != authority.max_transport_attempts_per_turn
            or budget.retry_policy != authority.retry_policy
            or budget.truncation_stop_behavior != authority.truncation_behavior
        ):
            raise DellSpecialistPaidShadowError(
                "paid_shadow_model_budget_binding_invalid"
            )
        public_sink = build_public_model_audit_sink(authority)
        private_sink = build_private_model_audit_sink(authority)
        # Serialize append calls within this process only; no distributed lock service.
        sink_lock = Lock()
        def locked_sink(sink):
            if sink is None:
                return None
            def write(event):
                with sink_lock:
                    sink(event)
            return write
        public_sink, private_sink = locked_sink(public_sink), locked_sink(private_sink)
        adapter = DeepSeekStructuredAgentAdapter.from_config(
            config=model_config,
            api_key=SecretStr(api_key),
            audit_sink=public_sink,
            private_audit_sink=private_sink,
        )
        with open_dell_specialist_receipted_composition(
            run_id=identity.research_run_id,
            run_invocation_id=identity.run_invocation_id,
            branch_id=authority.branch_id,
            turn_source="provider_model",
            model_turn=adapter.specialist_model_turn,
            max_model_turns=authority.max_model_turns,
            max_tool_actions=authority.max_tool_actions,
            source_read_enabled=authority.source_read_enabled,
        ) as composition:
            if (
                composition.graph_input.agent_id != authority.node_id
                or composition.graph_input.task.branch_id
                != authority.branch_id
                or composition.graph_input.task.research_as_of
                != authority.research_as_of
            ):
                raise DellSpecialistPaidShadowError(
                    "paid_shadow_specialist_input_binding_invalid"
                )
            require_data_authority_binding(
                authority,
                owner_data_gate_decision_digest=(
                    composition.owner_data_gate_decision_digest
                ),
                inventory_snapshot_digest=(
                    composition.inventory_snapshot_digest
                ),
                source_route_catalog_digest=(
                    composition.source_route_catalog_digest
                ),
            )
            if authority.workflow == "workpaper_review_repair":
                scope = authority.review_scope
                seed_path = Path("/run/fin-insight/review-seed.json")
                if file_sha256(seed_path) != scope.seed_state_sha256:
                    raise DellSpecialistPaidShadowError("review_seed_file_binding_invalid")
                seed = json.loads(seed_path.read_text(encoding="utf-8"))

                def run_child(role, collaboration, child_config):
                    basis = scope.node_budgets[role]
                    child_model_config = model_config.model_copy(update={
                        "token_budget_basis": {**model_config.token_budget_basis, "specialist": basis}})
                    child_adapter = DeepSeekStructuredAgentAdapter.from_config(
                        config=child_model_config, api_key=SecretStr(api_key),
                        audit_sink=public_sink, private_audit_sink=private_sink)
                    with open_dell_specialist_receipted_composition(
                        run_id=identity.research_run_id, run_invocation_id=identity.run_invocation_id,
                        branch_id=authority.branch_id, turn_source="provider_model",
                        model_turn=child_adapter.specialist_model_turn,
                        max_model_turns=authority.max_model_turns if role == "repair" else scope.max_reviewer_model_turns,
                        max_tool_actions=authority.max_tool_actions if role == "repair" else scope.max_reviewer_tool_actions,
                        source_read_enabled=True, collaboration_context=collaboration,
                    ) as child:
                        # Native subgraph invocation: Agent Server owns inherited persistence.
                        return child.graph.invoke(child.graph_input.model_dump(mode="json"),
                            config={**child_config, "recursion_limit": 128})

                yield build_dell_workpaper_review_graph(expected_input=composition.graph_input,
                    seed_state=seed, run_child=run_child).compile(name=DELL_AGENT_SERVER_GRAPH_ID)
            else:
                yield composition.graph
    except (
        DellSpecialistPaidShadowError,
        DellSpecialistAgenticCompositionError,
        DeepSeekStructuredAgentError,
    ) as exc:
        raise DellAgentServerEntryError(
            getattr(exc, "code", str(exc))
        ) from None
    except OSError:
        raise DellAgentServerEntryError(
            "paid_shadow_dependency_open_failed"
        ) from None


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

    serving_mode = _require_serving_mode()
    execution_runtime = runtime.execution_runtime
    if execution_runtime is None:
        if serving_mode == DELL_Q1_REVIEW_SERVING_MODE:
            yield _SCHEMA_ONLY_REVIEW_GRAPH
            return
        yield (
            _SCHEMA_ONLY_SPECIALIST_GRAPH
            if serving_mode == DELL_Q1_PAID_SHADOW_SERVING_MODE
            else _SCHEMA_ONLY_GRAPH
        )
        return

    execution_profile = _require_execution_profile()
    _require_langsmith_execution_environment(config)
    identity = bind_agent_server_identity(
        config=config,
        run_context=execution_runtime.context,
    )
    context = DellAgentServerRunContext.model_validate(execution_runtime.context)
    if serving_mode in {DELL_Q1_PAID_SHADOW_SERVING_MODE, DELL_Q1_REVIEW_SERVING_MODE}:
        async with _open_q1_paid_shadow_graph(
            identity,
            context,
            execution_profile=execution_profile,
        ) as graph:
            yield graph
        return
    async with _open_execution_dependencies(
        identity,
        context,
        execution_profile=execution_profile,
    ) as dependencies:
        yield _compile_graph(
            _bind_dependencies_to_identity(dependencies, identity),
            execution_profile=execution_profile,
        )


__all__ = [
    "DELL_AGENT_SERVER_GRAPH_ID",
    "DELL_EXECUTION_PROFILE_ENV",
    "DELL_SERVING_MODE_ENV",
    "DELL_LANGSMITH_PROJECT",
    "FIN_RUNTIME_POSTGRES_URI_ENV",
    "DellAgentServerEntryError",
    "DellAgentServerIdentityBinding",
    "bind_agent_server_identity",
    "dell_reference_vertical_graph",
]
