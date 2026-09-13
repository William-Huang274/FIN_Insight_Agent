"""LangGraph Agent Server entry points for research and review."""

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

from .research_graph_contracts import canonical_sha256
from .agent_server_data_composition import (
    ApprovedDataCompositionError,
    open_approved_data_composition,
)
from .agent_server_identity import (
    AGENT_SERVER_ASSISTANT_ID,
    AgentServerIdentityStoreError,
    PersistedExecutableRunBinding,
    PostgresAgentServerIdentityRepository,
    persisted_run_binding_digest,
)
from .research_graph import (
    AgentServerRunContext,
    ResearchGraphDependencies,
    build_research_state_graph,
)
from .deepseek_structured_agents import (
    DeepSeekStructuredAgentAdapter,
    DeepSeekStructuredAgentError,
    load_deepseek_structured_agent_config,
)
from .specialist_composition import (
    SpecialistAgenticCompositionError,
    open_specialist_receipted_composition,
)
from .specialist_graph import (
    SpecialistAgenticDependencies,
    build_specialist_agentic_state_graph,
)
from .model_execution_policy import (
    IMPLEMENTATION_COMMIT_ENV,
    Q1_PAID_SHADOW_AUTHORITY_ENV,
    Q1_PAID_SHADOW_SERVING_MODE,
    Q1_REVIEW_SERVING_MODE,
    LEAD_RESEARCH_SERVING_MODE,
    CASE_REVIEW_SERVING_MODE,
    CASE_CONVERGENCE_SERVING_MODE,
    ModelExecutionPolicyError,
    build_public_model_audit_sink,
    build_private_model_audit_sink,
    file_sha256,
    load_q1_paid_shadow_authority,
    require_data_authority_binding,
    require_runtime_authority_binding,
)
from .workpaper_review_graph import build_workpaper_review_graph
from .lead_research_graph import build_lead_research_graph
from .case_review_agent import open_case_review_composition, schema_only_case_review_graph
from .report_synthesis_agent import schema_only_case_convergence_graph
from sec_agent.research_foundation.contracts import load_research_graph_foundation
from .execution_profile_checks import (
    ExecutionProfile,
    ExecutionProfileCheckError,
    PRODUCT_EXECUTION_PROFILE,
    require_execution_profile,
)


AGENT_SERVER_GRAPH_ID = "dell_reference_vertical"
LANGSMITH_PROJECT = "fin-insight-dell-reference-vertical"
FIN_RUNTIME_POSTGRES_URI_ENV = "FIN_RUNTIME_POSTGRES_URI"
EXECUTION_PROFILE_ENV = "FINSIGHT_DELL_EXECUTION_PROFILE"
SERVING_MODE_ENV = "FINSIGHT_DELL_SERVING_MODE"
REFERENCE_VERTICAL_SERVING_MODE = "reference_vertical"


class AgentServerEntryError(RuntimeError):
    """Typed, secret-free Agent Server composition failure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class AgentServerIdentityBinding(BaseModel):
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
        raise AgentServerEntryError(code)
    return value.strip()


def bind_agent_server_identity(
    *,
    config: Mapping[str, Any],
    run_context: Any,
) -> AgentServerIdentityBinding:
    """Validate independent FIN identities against server-assigned IDs.

    Agent Server 0.13.3 supplies both identifiers in ``configurable`` during
    the ``threads.create_run`` factory call.  The server run identifier is not
    a top-level RunnableConfig key and must never be inferred from the thread
    or any FIN identifier.
    """

    try:
        context = AgentServerRunContext.model_validate(run_context)
    except Exception:
        raise AgentServerEntryError("fin_run_context_invalid") from None
    configurable = config.get("configurable")
    if not isinstance(configurable, Mapping):
        raise AgentServerEntryError("agent_server_configurable_missing")
    return AgentServerIdentityBinding(
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
    raise AgentServerEntryError("schema_introspection_graph_not_executable")


def _schema_only_dependencies() -> ResearchGraphDependencies:
    return ResearchGraphDependencies(
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
    dependencies: ResearchGraphDependencies,
    *,
    execution_profile: ExecutionProfile = PRODUCT_EXECUTION_PROFILE,
) -> Any:
    graph = build_research_state_graph(
        dependencies=dependencies,
        execution_profile=execution_profile,
    )
    return graph.compile(name=AGENT_SERVER_GRAPH_ID)


_SCHEMA_ONLY_GRAPH = _compile_graph(_schema_only_dependencies())

_SCHEMA_ONLY_SPECIALIST_GRAPH = build_specialist_agentic_state_graph(
    dependencies=SpecialistAgenticDependencies(
        model_turn=_schema_only_unavailable,
        evidence_tool=_schema_only_unavailable,
        finance_tool=_schema_only_unavailable,
        turn_source="provider_model",
    )
).compile(name=AGENT_SERVER_GRAPH_ID)
_SCHEMA_ONLY_REVIEW_GRAPH = build_workpaper_review_graph(
    expected_input=None, seed_state=None, run_child=_schema_only_unavailable,
).compile(name=AGENT_SERVER_GRAPH_ID)
_SCHEMA_ONLY_LEAD_GRAPH = build_lead_research_graph(
    expected_input=None, research_question="", branch_catalog=[], allowed_branch_ids=(),
    seed_workpapers={}, model_turn=_schema_only_unavailable, run_child=_schema_only_unavailable,
).compile(name=AGENT_SERVER_GRAPH_ID)
_SCHEMA_ONLY_CASE_REVIEW_GRAPH = schema_only_case_review_graph()
_SCHEMA_ONLY_CASE_CONVERGENCE_GRAPH = schema_only_case_convergence_graph()


def _require_serving_mode() -> Literal[
    "reference_vertical",
    "q1_specialist_paid_shadow_v1",
    "q1_workpaper_review_repair_v1",
    "lead_research_delegation_v1",
    "case_workpaper_review_v1",
    "case_convergence_v1",
]:
    raw = os.environ.get(
        SERVING_MODE_ENV,
        REFERENCE_VERTICAL_SERVING_MODE,
    ).strip()
    if raw not in {
        REFERENCE_VERTICAL_SERVING_MODE,
        Q1_PAID_SHADOW_SERVING_MODE,
        Q1_REVIEW_SERVING_MODE,
        LEAD_RESEARCH_SERVING_MODE,
        CASE_REVIEW_SERVING_MODE,
        CASE_CONVERGENCE_SERVING_MODE,
    }:
        raise AgentServerEntryError("dell_serving_mode_invalid")
    return raw  # type: ignore[return-value]


def _require_execution_profile() -> ExecutionProfile:
    raw = os.environ.get(EXECUTION_PROFILE_ENV, PRODUCT_EXECUTION_PROFILE)
    try:
        return require_execution_profile(raw)
    except ExecutionProfileCheckError:
        raise AgentServerEntryError("dell_execution_profile_invalid") from None


def _require_langsmith_execution_environment(config: Mapping[str, Any]) -> None:
    """Enforce one deployment-owned LangSmith trace destination.

    Agent Server 0.13.3 already traces through its deployment environment.
    A run-level project override creates an additional trace replica, so the
    product seam rejects it instead of consuming quota twice or allowing trace
    destinations to drift by caller.
    """

    tracing = os.environ.get("LANGSMITH_TRACING", "").strip().lower()
    if tracing != "true":
        raise AgentServerEntryError("langsmith_tracing_required")
    if not os.environ.get("LANGSMITH_API_KEY", "").strip():
        raise AgentServerEntryError("langsmith_api_key_required")
    project = os.environ.get("LANGSMITH_PROJECT", "").strip()
    if project != LANGSMITH_PROJECT:
        raise AgentServerEntryError("langsmith_project_mismatch")
    configurable = config.get("configurable")
    if isinstance(configurable, Mapping) and configurable.get(
        "__langsmith_project__"
    ) is not None:
        raise AgentServerEntryError("langsmith_run_project_override_forbidden")
    # The pinned LangSmith client enables this control only for the literal
    # string ``true``.  Accepting truthy aliases here would let the entry gate
    # pass while the tracer still exported payloads.
    if os.environ.get("LANGSMITH_HIDE_INPUTS", "").strip().lower() != "true":
        raise AgentServerEntryError("langsmith_inputs_must_be_hidden")
    if os.environ.get("LANGSMITH_HIDE_OUTPUTS", "").strip().lower() != "true":
        raise AgentServerEntryError("langsmith_outputs_must_be_hidden")


def _bind_dependencies_to_identity(
    dependencies: ResearchGraphDependencies,
    identity: AgentServerIdentityBinding,
) -> ResearchGraphDependencies:
    foundation_binder = dependencies.foundation_binder

    def bound_foundation_binder(request: Mapping[str, Any]) -> Mapping[str, Any]:
        if request.get("run_id") != identity.research_run_id:
            raise AgentServerEntryError("fin_research_run_id_mismatch")
        return foundation_binder(request)

    return replace(dependencies, foundation_binder=bound_foundation_binder)


def _read_durable_run_binding(
    identity: AgentServerIdentityBinding,
) -> PersistedExecutableRunBinding | None:
    """Read FIN-owned identity state without exposing its credential or DSN."""

    uri = os.environ.get(FIN_RUNTIME_POSTGRES_URI_ENV, "").strip()
    if not uri:
        raise AgentServerEntryError("fin_runtime_postgres_uri_required")
    try:
        import psycopg

        repository = PostgresAgentServerIdentityRepository(
            lambda: psycopg.connect(
                uri,
                connect_timeout=5,
                application_name="fin_dell_agent_server_identity_guard",
            )
        )
        return repository.get_execution_binding_with_lifecycle(
            run_invocation_id=identity.run_invocation_id
        )
    except AgentServerIdentityStoreError as exc:
        raise AgentServerEntryError(
            f"fin_durable_identity_guard_failed:{exc.code}"
        ) from None
    except Exception:
        raise AgentServerEntryError(
            "fin_durable_identity_guard_read_failed"
        ) from None


def _require_durable_execution_binding(
    identity: AgentServerIdentityBinding,
    *,
    execution_profile: ExecutionProfile,
) -> None:
    """Reject an unbound or spoofed server run before opening any data port."""

    projection = _read_durable_run_binding(identity)
    if projection is None:
        raise AgentServerEntryError(
            "fin_server_run_durable_binding_missing"
        )
    persisted = projection.binding
    if (
        persisted.agent_session_id != identity.agent_session_id
        or persisted.research_run_id != identity.research_run_id
        or persisted.run_invocation_id != identity.run_invocation_id
        or persisted.server_thread_id != identity.server_thread_id
        or persisted.server_run_id != identity.server_run_id
        or persisted.assistant_id != AGENT_SERVER_ASSISTANT_ID
    ):
        raise AgentServerEntryError(
            "fin_server_run_durable_binding_conflict"
        )
    lifecycle = projection.lifecycle
    if lifecycle is None or lifecycle.reconciled is None:
        raise AgentServerEntryError(
            "fin_server_run_create_lifecycle_not_reconciled"
        )
    reconciled = lifecycle.reconciled
    if (
        lifecycle.pending.execution_profile != execution_profile
        or reconciled.execution_profile != execution_profile
    ):
        raise AgentServerEntryError(
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
        raise AgentServerEntryError(
            "fin_server_run_create_lifecycle_conflict"
        )


@asynccontextmanager
async def _open_execution_dependencies(
    identity: AgentServerIdentityBinding,
    context: AgentServerRunContext,
    *,
    execution_profile: ExecutionProfile,
) -> AsyncIterator[ResearchGraphDependencies]:
    """Open the exact approved readers and one MCP lifecycle for this run.

    The Owner decision authorizes only zero-network data composition.  Model
    callables remain fail-closed until a separate paid-execution decision.
    """

    if identity.research_run_id != context.research_run_id:
        raise AgentServerEntryError("fin_research_run_id_mismatch")
    _require_durable_execution_binding(
        identity,
        execution_profile=execution_profile,
    )
    try:
        with open_approved_data_composition(
            run_invocation_id=identity.run_invocation_id
        ) as composition:
            yield composition.dependencies
    except ApprovedDataCompositionError as exc:
        raise AgentServerEntryError(exc.code) from None


@asynccontextmanager
async def _open_q1_paid_shadow_graph(
    identity: AgentServerIdentityBinding,
    context: AgentServerRunContext,
    *,
    execution_profile: ExecutionProfile,
) -> AsyncIterator[Any]:
    """Open the one Owner-authorized DeepSeek Specialist graph."""

    if execution_profile != PRODUCT_EXECUTION_PROFILE:
        raise AgentServerEntryError(
            "paid_shadow_requires_product_execution_profile"
        )
    if identity.research_run_id != context.research_run_id:
        raise AgentServerEntryError("fin_research_run_id_mismatch")
    _require_durable_execution_binding(
        identity,
        execution_profile=execution_profile,
    )
    authority_path = os.environ.get(
        Q1_PAID_SHADOW_AUTHORITY_ENV,
        "",
    ).strip()
    implementation_commit = os.environ.get(
        IMPLEMENTATION_COMMIT_ENV,
        "",
    ).strip()
    repository_root = os.environ.get("FIN_REPO_ROOT", "").strip()
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not authority_path:
        raise AgentServerEntryError("paid_shadow_authority_path_required")
    if not implementation_commit:
        raise AgentServerEntryError(
            "paid_shadow_implementation_commit_required"
        )
    if not repository_root:
        raise AgentServerEntryError("paid_shadow_repository_root_required")
    if not api_key:
        raise AgentServerEntryError("deepseek_api_key_required")
    try:
        authority = load_q1_paid_shadow_authority(authority_path)
        if authority.serving_mode != _require_serving_mode():
            raise ModelExecutionPolicyError("paid_shadow_serving_mode_authority_mismatch")
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
            raise ModelExecutionPolicyError(
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
            raise ModelExecutionPolicyError(
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
        if authority.workflow in {"case_workpaper_review", "case_convergence"}:
            async with open_case_review_composition(authority=authority, model_config=model_config,
                    api_key=SecretStr(api_key), public_sink=public_sink, private_sink=private_sink) as graph:
                yield graph
            return
        adapter = DeepSeekStructuredAgentAdapter.from_config(
            config=model_config,
            api_key=SecretStr(api_key),
            audit_sink=public_sink,
            private_audit_sink=private_sink,
        )
        with open_specialist_receipted_composition(
            run_id=identity.research_run_id,
            run_invocation_id=identity.run_invocation_id,
            branch_id=authority.branch_id,
            turn_source="provider_model",
            model_turn=adapter.specialist_model_turn,
            max_model_turns=authority.max_model_turns,
            max_tool_actions=authority.max_tool_actions,
            source_read_enabled=authority.source_read_enabled,
            live_web_read_enabled=authority.live_external_calls_authorized,
        ) as composition:
            if (
                composition.graph_input.agent_id != authority.node_id
                or composition.graph_input.task.branch_id
                != authority.branch_id
                or composition.graph_input.task.research_as_of
                != authority.research_as_of
            ):
                raise ModelExecutionPolicyError(
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
            if authority.workflow == "lead_research_delegation":
                scope = authority.lead_scope
                seed_path = Path("/run/fin-insight/review-seed.json")
                if file_sha256(seed_path) != scope.seed_state_sha256:
                    raise ModelExecutionPolicyError("lead_seed_file_binding_invalid")
                seed_envelope = json.loads(seed_path.read_text(encoding="utf-8"))["values"]
                if seed_envelope.get("phase") != "review_cycle_accepted":
                    raise ModelExecutionPolicyError("lead_requires_reviewed_seed_workpaper")
                seed = seed_envelope["target_state"]
                foundation_path = Path(repository_root) / "configs/research/fin_ia_0_1_3_dell_reference_vertical_foundation_v1_0.json"
                foundation = load_research_graph_foundation(foundation_path)
                if canonical_sha256(foundation) != composition.graph_input.task.foundation_digest:
                    raise ModelExecutionPolicyError("lead_foundation_binding_invalid")
                if not model_config.agentic_message_history:
                    raise ModelExecutionPolicyError("lead_requires_independent_agentic_contexts")
                if any(basis.reasoning_profile != "agentic_message_history_thinking_" +
                       model_config.profile_for(role).thinking for role, basis in scope.node_budgets.items()):
                    raise ModelExecutionPolicyError("lead_budget_thinking_profile_mismatch")
                qualified_config = model_config.model_copy(update={"token_budget_basis": {
                    **model_config.token_budget_basis, **scope.node_budgets}})
                lead_adapter = DeepSeekStructuredAgentAdapter.from_config(
                    config=qualified_config, api_key=SecretStr(api_key),
                    audit_sink=public_sink, private_audit_sink=private_sink)

                def run_research_child(task, dependency_workpapers, child_config):
                    # A new SDK history and MCP lifecycle per task; LangGraph owns
                    # fan-out and inherited Agent Server checkpoint persistence.
                    child_adapter = DeepSeekStructuredAgentAdapter.from_config(
                        config=qualified_config, api_key=SecretStr(api_key),
                        audit_sink=public_sink, private_audit_sink=private_sink)
                    with open_specialist_receipted_composition(
                        run_id=identity.research_run_id, run_invocation_id=identity.run_invocation_id,
                        branch_id=task["coverage_obligation_ids"][0], turn_source="provider_model",
                        model_turn=child_adapter.specialist_model_turn,
                        max_model_turns=authority.max_model_turns, max_tool_actions=authority.max_tool_actions,
                        source_read_enabled=True, research_task=task, dependency_workpapers=dependency_workpapers,
                        live_web_read_enabled=authority.live_external_calls_authorized,
                    ) as child:
                        return child.graph.invoke(child.graph_input.model_dump(mode="json"),
                            config={**child_config, "recursion_limit": 160})

                yield build_lead_research_graph(
                    expected_input=composition.graph_input,
                    research_question=foundation.case_identity.top_level_question_zh,
                    branch_catalog=[row.model_dump(mode="json") for row in foundation.question_branches],
                    allowed_branch_ids=scope.allowed_branch_ids,
                    seed_workpapers={seed["task"]["task_id"]: seed},
                    model_turn=lead_adapter.lead_research_turn, run_child=run_research_child,
                    max_lead_turns=scope.max_lead_model_turns, max_tasks=scope.max_tasks,
                    max_parallel_tasks=scope.max_parallel_tasks, turn_source="provider_model",
                ).compile(name=AGENT_SERVER_GRAPH_ID).with_config({"recursion_limit": 128})
            elif authority.workflow == "workpaper_review_repair":
                scope = authority.review_scope
                seed_path = Path("/run/fin-insight/review-seed.json")
                if file_sha256(seed_path) != scope.seed_state_sha256:
                    raise ModelExecutionPolicyError("review_seed_file_binding_invalid")
                seed = json.loads(seed_path.read_text(encoding="utf-8"))

                def run_child(role, collaboration, child_config):
                    basis = scope.node_budgets[role]
                    child_model_config = model_config.model_copy(update={
                        "token_budget_basis": {**model_config.token_budget_basis, "specialist": basis}})
                    child_adapter = DeepSeekStructuredAgentAdapter.from_config(
                        config=child_model_config, api_key=SecretStr(api_key),
                        audit_sink=public_sink, private_audit_sink=private_sink)
                    with open_specialist_receipted_composition(
                        run_id=identity.research_run_id, run_invocation_id=identity.run_invocation_id,
                        branch_id=authority.branch_id, turn_source="provider_model",
                        model_turn=child_adapter.specialist_model_turn,
                        max_model_turns=authority.max_model_turns if role == "repair" else scope.max_reviewer_model_turns,
                        max_tool_actions=authority.max_tool_actions if role == "repair" else scope.max_reviewer_tool_actions,
                        source_read_enabled=True, collaboration_context=collaboration,
                        live_web_read_enabled=authority.live_external_calls_authorized,
                    ) as child:
                        # Native subgraph invocation: Agent Server owns inherited persistence.
                        return child.graph.invoke(child.graph_input.model_dump(mode="json"),
                            config={**child_config, "recursion_limit": 128})

                yield build_workpaper_review_graph(expected_input=composition.graph_input,
                    seed_state=seed, run_child=run_child).compile(name=AGENT_SERVER_GRAPH_ID)
            else:
                yield composition.graph
    except (
        ModelExecutionPolicyError,
        SpecialistAgenticCompositionError,
        DeepSeekStructuredAgentError,
    ) as exc:
        raise AgentServerEntryError(
            getattr(exc, "code", str(exc))
        ) from None
    except OSError:
        raise AgentServerEntryError(
            "paid_shadow_dependency_open_failed"
        ) from None


@asynccontextmanager
async def research_graph(
    config: RunnableConfig,
    runtime: ServerRuntime[AgentServerRunContext],
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
        if serving_mode == CASE_CONVERGENCE_SERVING_MODE:
            yield _SCHEMA_ONLY_CASE_CONVERGENCE_GRAPH
            return
        if serving_mode == CASE_REVIEW_SERVING_MODE:
            yield _SCHEMA_ONLY_CASE_REVIEW_GRAPH
            return
        if serving_mode == LEAD_RESEARCH_SERVING_MODE:
            yield _SCHEMA_ONLY_LEAD_GRAPH
            return
        if serving_mode == Q1_REVIEW_SERVING_MODE:
            yield _SCHEMA_ONLY_REVIEW_GRAPH
            return
        yield (
            _SCHEMA_ONLY_SPECIALIST_GRAPH
            if serving_mode == Q1_PAID_SHADOW_SERVING_MODE
            else _SCHEMA_ONLY_GRAPH
        )
        return

    execution_profile = _require_execution_profile()
    _require_langsmith_execution_environment(config)
    identity = bind_agent_server_identity(
        config=config,
        run_context=execution_runtime.context,
    )
    context = AgentServerRunContext.model_validate(execution_runtime.context)
    if serving_mode in {Q1_PAID_SHADOW_SERVING_MODE, Q1_REVIEW_SERVING_MODE, LEAD_RESEARCH_SERVING_MODE, CASE_REVIEW_SERVING_MODE, CASE_CONVERGENCE_SERVING_MODE}:
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
    "AGENT_SERVER_GRAPH_ID",
    "EXECUTION_PROFILE_ENV",
    "SERVING_MODE_ENV",
    "LANGSMITH_PROJECT",
    "FIN_RUNTIME_POSTGRES_URI_ENV",
    "AgentServerEntryError",
    "AgentServerIdentityBinding",
    "bind_agent_server_identity",
    'research_graph',
]
