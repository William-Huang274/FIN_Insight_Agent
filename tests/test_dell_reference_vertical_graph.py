from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
import json
from threading import Barrier, Lock
from typing import Any

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from sec_agent.agent_runtime.dell_reference_vertical_contracts import (
    AgentRuntimeScopeCeiling,
    BoundBranchTask,
    BranchAgentInput,
    BranchMethodBinding,
    BranchWorkpaper,
    CaseFoundationBinding,
    EvidenceIntentRequest,
    RuntimeReceipt,
    ToolLaneResult,
    ToolLaneTask,
    canonical_sha256,
)
from sec_agent.agent_runtime.dell_reference_vertical_graph import (
    DellReferenceVerticalDependencies,
    DellReferenceVerticalGraphError,
    _join_initial_lane_results,
    _validate_agent_step_budget,
    _validate_cumulative_branch_external_budget,
    _validate_specialist_round_authority,
    _validate_workpaper,
    build_dell_reference_vertical_state_graph,
)
from sec_agent.agent_runtime.dell_zero_model_graph_qualification import (
    ZERO_MODEL_EXECUTION_PROFILE,
)


RUN_ID = "dell-reference-run-001"
CASE_ID = "DELL"
RESEARCH_AS_OF = "2026-09-02T04:35:00+08:00"
SNAPSHOT_ID = "dell-e1-snapshot-20260902"
FOUNDATION_DIGEST = canonical_sha256({"foundation": "v1"})
QUESTION = "DELL AI server demand conversion, economics, risks, and what would change?"


def _reviewed_evidence_request(
    query: str,
    *,
    branch_id: str = "Q1_ISSUER_TRUTH",
    limit: int = 3,
) -> dict[str, Any]:
    return {
        "minimum_route_obligation_id": f"route:{branch_id}:required-reviewed",
        "intent": {
            "intent_kind": "reviewed_evidence",
            "query": query,
            "purpose": f"Bound reviewed evidence for {branch_id}.",
            "entity_refs": ["DELL"],
            "period_intents": [],
            "expected_information_gain": (
                "Determine whether reviewed evidence supports the branch."
            ),
            "limit": limit,
            "topic_refs": [branch_id],
            "evidence_role_refs": [],
            "minimum_authority_tier": "reviewed",
        },
    }


def _external_evidence_request(
    query: str,
    *,
    branch_id: str = "Q1_ISSUER_TRUTH",
    limit: int = 3,
) -> dict[str, Any]:
    return {
        "minimum_route_obligation_id": f"route:{branch_id}:test-external",
        "intent": {
            "intent_kind": "external_source",
            "query": query,
            "purpose": "Bound one current external source.",
            "entity_refs": ["DELL"],
            "period_intents": [],
            "expected_information_gain": (
                "Determine whether a current primary source changes the branch."
            ),
            "limit": limit,
            "semantic_source_family_refs": ["F8"],
            "domain_allowlist": [],
            "published_not_before": None,
            "published_not_after": None,
        },
    }


def _source_route_catalog() -> dict[str, Any]:
    rows = []
    for branch_id in ("Q1_ISSUER_TRUTH", "Q2_DEMAND_QUALITY"):
        rows.extend(
            (
                {
                    "minimum_route_obligation_id": (
                        f"route:{branch_id}:required-reviewed"
                    ),
                    "coverage_obligation_id": branch_id,
                    "requirement": "required",
                    "intent_kind": "reviewed_evidence",
                    "semantic_source_family_refs": ["F8"],
                    "entity_refs": [],
                    "period_intents": [],
                    "required_authority_refs": ["authority:reviewed-read"],
                },
                {
                    "minimum_route_obligation_id": (
                        f"route:{branch_id}:test-external"
                    ),
                    "coverage_obligation_id": branch_id,
                    "requirement": "optional",
                    "intent_kind": "external_source",
                    "semantic_source_family_refs": ["F8"],
                    "entity_refs": [],
                    "period_intents": [],
                    "required_authority_refs": ["authority:primary-read"],
                },
            )
        )
    rows.sort(key=lambda row: row["minimum_route_obligation_id"])
    unsigned = {
        "schema_version": "fin_ia_dell_provider_source_route_catalog_v1_0",
        "inventory_snapshot_digest": "1" * 64,
        "baseline_source_plan_digest": "2" * 64,
        "routes": rows,
        "physical_selectors_exposed": False,
        "answer_free": True,
    }
    return {**unsigned, "catalog_digest": canonical_sha256(unsigned)}


class _DellReferenceVerticalTestGraph:
    """Test-only local adapter; production must use Agent Server and its SDK."""

    def __init__(self, compiled: Any) -> None:
        self._compiled = compiled

    @staticmethod
    def _thread_id(config: Mapping[str, Any] | None) -> str:
        configurable = config.get("configurable") if isinstance(config, Mapping) else None
        thread_id = configurable.get("thread_id") if isinstance(configurable, Mapping) else None
        if not isinstance(thread_id, str) or not thread_id.strip():
            raise DellReferenceVerticalGraphError("thread_id_required")
        return thread_id.strip()

    @classmethod
    def _safe_input(
        cls,
        value: Any,
        config: Mapping[str, Any] | None,
    ) -> Any:
        thread_id = cls._thread_id(config)
        if isinstance(value, Command):
            if value.update is not None:
                raise DellReferenceVerticalGraphError("command_update_not_allowed")
            if value.goto:
                raise DellReferenceVerticalGraphError("command_goto_not_allowed")
            if value.graph is not None:
                raise DellReferenceVerticalGraphError("command_graph_override_not_allowed")
            if value.resume is None:
                raise DellReferenceVerticalGraphError("command_resume_value_required")
            return value
        if not isinstance(value, Mapping):
            raise DellReferenceVerticalGraphError("initial_graph_input_must_be_mapping")
        initial = dict(value)
        if initial.get("run_id") != thread_id:
            raise DellReferenceVerticalGraphError("thread_id_run_id_mismatch")
        return initial

    def invoke(
        self,
        value: Any,
        config: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        return self._compiled.invoke(self._safe_input(value, config), config, **kwargs)

    def get_state(self, config: Mapping[str, Any], **kwargs: Any) -> Any:
        self._thread_id(config)
        return self._compiled.get_state(config, **kwargs)


def _build_dell_reference_vertical_test_graph(
    *,
    dependencies: DellReferenceVerticalDependencies,
    checkpointer: Any,
    execution_profile: str = "product",
) -> _DellReferenceVerticalTestGraph:
    if checkpointer is None:
        raise DellReferenceVerticalGraphError(
            "checkpointer_required_for_interrupt_resume"
        )
    builder = build_dell_reference_vertical_state_graph(
        dependencies=dependencies,
        execution_profile=execution_profile,
    )
    return _DellReferenceVerticalTestGraph(
        builder.compile(
            checkpointer=checkpointer,
            name="dell_reference_vertical_test_graph",
        )
    )


def _planner_tool_capabilities() -> dict[str, Any]:
    unsigned = {
        "schema_version": "fin_ia_dell_planner_tool_capabilities_v1_0",
        "snapshot_id": SNAPSHOT_ID,
        "mart_sha256": "a" * 64,
        "data_cutoff_kind": "latest_through_observation_accepted_at",
        "data_latest_through_accepted_at": "2026-08-31T18:21:23+00:00",
        "point_in_time_claimed": False,
        "finance": {
            "supported_tickers": ["DELL", "NVDA"],
            "metrics": [
                {
                    "metric_id": "revenue",
                    "unit_family": "monetary",
                    "availability": "direct_observation",
                    "formula": None,
                    "observed_tickers": ["DELL", "NVDA"],
                }
            ],
            "canonical_granularities": ["quarter_discrete", "fiscal_year"],
            "date_format": "YYYY-MM-DD",
            "latest_query_rule": (
                "omit_period_bounds_and_fiscal_years_for_latest_available_observations"
            ),
            "maximum_fiscal_year_count": 4,
            "non_capabilities": ["backlog_or_orders"],
            "derived_metric_rule": (
                "derived_metrics_are_computed_by_the_existing_fact_executor_and_may_return_typed_gap_when_inputs_do_not_align"
            ),
        },
        "evidence_routes": [
            {
                "source_route": route,
                "semantics": f"Use the {route} route without admitting candidates.",
                "candidate_is_not_evidence": True,
            }
            for route in ("reviewed_first", "local_only", "external_required")
        ],
    }
    return {**unsigned, "projection_digest": canonical_sha256(unsigned)}


def _receipt(
    *,
    kind: str,
    actor: str,
    request: Any,
    body: Any | None,
    success: bool = True,
) -> dict[str, Any]:
    request_digest = canonical_sha256(request)
    return RuntimeReceipt(
        receipt_id=f"receipt:{actor}:{request_digest[:20]}",
        kind=kind,
        actor=actor,
        status="success" if success else "failure",
        request_digest=request_digest,
        output_digest=canonical_sha256(body) if success else None,
        elapsed_ms=1.0,
        input_tokens=2 if kind == "model" else 0,
        output_tokens=1 if kind == "model" else 0,
        total_tokens=3 if kind == "model" else 0,
        usage_reported=True if kind == "model" else None,
        transport_attempts=1,
    ).model_dump(mode="json")


def _tool_body(
    *,
    status: str,
    result_states: list[str],
    items: list[dict[str, Any]],
    failure: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "status": status,
        "result_states": result_states,
        "items": items,
        "failure": failure,
    }


@dataclass
class FakeRuntime:
    reroute_branch: str | None = None
    tool_failure_branch: str | None = None
    tool_failure_lane: str = "evidence"
    tool_failure_terminal_state: str = "incomplete_tool_failure"
    bad_tool_binding_branch: str | None = None
    planner_failure_receipt: bool = False
    barriers: dict[int, Barrier] = field(default_factory=dict)
    calls: list[tuple[str, str, int]] = field(default_factory=list)
    specialist_inputs: list[dict[str, Any]] = field(default_factory=list)
    planner_calls: int = 0
    counter_calls: int = 0
    lead_calls: int = 0
    _lock: Lock = field(default_factory=Lock)

    @staticmethod
    def method_bindings() -> tuple[BranchMethodBinding, ...]:
        values = []
        for branch_id, priority in (("Q1_ISSUER_TRUTH", "high"), ("Q2_DEMAND_QUALITY", "high")):
            context = {
                "schema_version": "answer_free_method_v1",
                "branch_id": branch_id,
                "rules": ["candidate_is_not_evidence", "tool_failure_is_not_gap"],
            }
            values.append(
                BranchMethodBinding(
                    branch_id=branch_id,
                    priority=priority,
                    objective=f"Investigate {branch_id}",
                    method_digest=canonical_sha256(context),
                    method_context=context,
                )
            )
        return tuple(values)

    def foundation_binder(self, request: Mapping[str, Any]) -> dict[str, Any]:
        return CaseFoundationBinding(
            case_id=str(request["case_id"]),
            research_as_of=str(request["research_as_of"]),
            snapshot_id=str(request["snapshot_id"]),
            foundation_digest=str(request["foundation_digest"]),
            scope_ceiling=AgentRuntimeScopeCeiling(
                maximum_external_search_rounds_per_high_materiality_branch=2,
                maximum_results_per_search=6,
                maximum_captured_pages_per_branch=4,
                maximum_live_pages_per_run=24,
                maximum_sources_visible_per_agent_step=10,
                maximum_specialist_model_rounds=2,
                maximum_targeted_counter_reroutes=1,
            ),
            branch_methods=self.method_bindings(),
            required_branch_ids=("Q1_ISSUER_TRUTH", "Q2_DEMAND_QUALITY"),
        ).model_dump(mode="json")

    def planner(self, request: Mapping[str, Any]) -> dict[str, Any]:
        with self._lock:
            self.planner_calls += 1
        capabilities = dict(request["planner_tool_capabilities"])
        digest = capabilities.pop("projection_digest")
        assert digest == request["planner_tool_capabilities_digest"]
        assert canonical_sha256(capabilities) == digest
        # Deliberately reverse catalog order; the graph must canonicalize it.
        tasks = [
            {
                "branch_id": branch_id,
                "objective": f"Bounded objective for {branch_id}",
                "evidence_requests": [
                    _reviewed_evidence_request(
                        f"evidence for {branch_id}",
                        branch_id=branch_id,
                    )
                ],
                "fact_requests": [{"metric_id": f"metric_{branch_id}"}],
            }
            for branch_id in ("Q2_DEMAND_QUALITY", "Q1_ISSUER_TRUTH")
        ]
        body = {"tasks": tasks}
        return {
            **body,
            "runtime_receipt": _receipt(
                kind="model",
                actor=str(request["agent_id"]),
                request=request,
                body=body,
                success=not self.planner_failure_receipt,
            ),
        }

    def _tool(self, request: Mapping[str, Any], lane: str) -> dict[str, Any]:
        lane_task = ToolLaneTask.model_validate_json(
            __import__("json").dumps(request)
        )
        task = lane_task.task
        with self._lock:
            self.calls.append((lane, task.branch_id, task.revision))
        barrier = self.barriers.get(task.revision)
        if barrier is not None:
            barrier.wait(timeout=5)

        if (
            lane == self.tool_failure_lane
            and task.branch_id == self.tool_failure_branch
        ):
            failure = {
                "code": "fixture_source_timeout",
                "owner_layer": "s1_tool" if lane == "evidence" else "s2_tool",
                "retryable": False,
                "exception_type": "TimeoutError",
            }
            body = _tool_body(
                status="tool_failure",
                result_states=["tool_failure"],
                items=[],
                failure=failure,
            )
            success = False
        elif lane == "evidence":
            body = _tool_body(
                status="success",
                result_states=["reviewed_evidence"],
                items=[
                    {
                        "evidence_id": f"E:{task.branch_id}:r{task.revision}",
                        "authority_state": "reviewed_evidence",
                        "writer_citable": True,
                        "target_id": f"TARGET:{task.branch_id}:r{task.revision}",
                        "evidence_role": "issuer_direct_source",
                        "publication_date": "2026-09-01",
                        "source_reporting_period_end": "2026-07-31",
                        "research_as_of": "2026-09-02",
                        "source_type": "8-K",
                        "source_tier": "issuer_primary",
                        "source_url": "https://example.com/dell-evidence",
                        "source_record_id": f"SRC:{task.branch_id}:r{task.revision}",
                        "source_locator": {"section": task.branch_id},
                        "source_content_digest": "1" * 64,
                        "bounded_excerpt": (
                            f"Reviewed evidence for {task.branch_id}"
                        ),
                        "excerpt_truncated": False,
                        "numeric_use_boundary": "Textual evidence only.",
                        "causal_attribution_authorized": False,
                        "evidence_item_digest": "2" * 64,
                        "result_state": "reviewed_evidence",
                    }
                ],
                failure=None,
            )
            success = True
        else:
            body = _tool_body(
                status="success",
                result_states=["numeric_fact"],
                items=[
                    {
                        "fact_id": f"F:{task.branch_id}:r{task.revision}",
                        "numeric_fact_id": f"F:{task.branch_id}:r{task.revision}",
                        "fact_request_id": f"FR:{task.branch_id}:r{task.revision}",
                        "ticker": "DELL",
                        "metric_id": "revenue",
                        "value_decimal": "1",
                        "unit": "USD",
                        "unit_family": "monetary",
                        "period_start": "2026-05-02",
                        "period_end": "2026-07-31",
                        "period_role": "quarter_discrete",
                        "fiscal_year": 2027,
                        "fiscal_period": "Q2",
                        "research_as_of": "2026-09-02",
                        "authority_mode": "direct_observation",
                        "accession_numbers": ["0001571996-26-000039"],
                        "accepted_at": "2026-09-01T16:10:14Z",
                        "source_observation_ids": ["OBS:1"],
                        "citation_urls": ["https://www.sec.gov/example"],
                        "source_digests": ["3" * 64],
                        "formula_trace": None,
                        "numeric_fact_authority": True,
                        "result_state": "numeric_fact",
                    }
                ],
                failure=None,
            )
            success = True

        branch_id = (
            "Q1_ISSUER_TRUTH"
            if task.branch_id == self.bad_tool_binding_branch
            and task.branch_id != "Q1_ISSUER_TRUTH"
            else task.branch_id
        )
        return {
            "lane": lane,
            "task_id": task.task_id,
            "case_id": task.case_id,
            "branch_id": branch_id,
            "revision": task.revision,
            "research_as_of": task.research_as_of,
            "snapshot_id": task.snapshot_id,
            "foundation_digest": task.foundation_digest,
            "method_digest": task.method_digest,
            "plan_digest": task.plan_digest,
            **body,
            "runtime_receipt": _receipt(
                kind="tool",
                actor=f"{lane}_tool",
                request=request,
                body=body,
                success=success,
            ),
        }

    def evidence_tool(self, request: Mapping[str, Any]) -> dict[str, Any]:
        return self._tool(request, "evidence")

    def finance_tool(self, request: Mapping[str, Any]) -> dict[str, Any]:
        return self._tool(request, "finance")

    def specialist(self, request: Mapping[str, Any]) -> dict[str, Any]:
        request_dict = dict(request)
        with self._lock:
            self.specialist_inputs.append(request_dict)
        task = request["task"]
        evidence = request["evidence_result"]
        finance = request["finance_result"]
        evidence_ids = [
            row["evidence_id"]
            for row in evidence["items"]
            if "evidence_id" in row
        ]
        fact_ids = [
            row["fact_id"] for row in finance["items"] if "fact_id" in row
        ]
        has_tool_failure = (
            evidence["status"] == "tool_failure"
            or finance["status"] == "tool_failure"
        )
        if has_tool_failure:
            terminal_state = self.tool_failure_terminal_state
        else:
            terminal_state = "supported"
        body = {
            "branch_id": task["branch_id"],
            "revision": task["revision"],
            "agent_id": request["agent_id"],
            "context_digest": request["context_digest"],
            "snapshot_id": task["snapshot_id"],
            "foundation_digest": task["foundation_digest"],
            "method_digest": task["method_digest"],
            "plan_digest": task["plan_digest"],
            "terminal_state": terminal_state,
            "thesis": f"Thesis for {task['branch_id']} revision {task['revision']}",
            "mechanism": f"Mechanism for {task['branch_id']} revision {task['revision']}",
            "counterevidence": [f"Counter for {task['branch_id']}"],
            "what_would_change": [f"WWC for {task['branch_id']}"],
            "evidence_ids": evidence_ids,
            "fact_ids": fact_ids,
            "open_gaps": ["typed tool failure"] if has_tool_failure else [],
            "tool_receipt_ids": [
                evidence["runtime_receipt"]["receipt_id"],
                finance["runtime_receipt"]["receipt_id"],
            ],
        }
        return {
            **body,
            "runtime_receipt": _receipt(
                kind="model",
                actor=str(request["agent_id"]),
                request=request,
                body=body,
            ),
        }

    def counter(self, request: Mapping[str, Any]) -> dict[str, Any]:
        with self._lock:
            self.counter_calls += 1
        reroute = None
        if self.reroute_branch is not None:
            reroute = {
                "target_branch_id": self.reroute_branch,
                "challenge_id": "counter-challenge-1",
                "reason": "One material issue needs one bounded refresh.",
                "owner_layer": "agent",
                "evidence_requests": [
                    _reviewed_evidence_request(
                        "targeted counter refresh",
                        branch_id=self.reroute_branch,
                    )
                ],
                "fact_requests": [{"metric_id": "targeted_metric"}],
            }
        body = {
            "agent_id": request["agent_id"],
            "context_digest": request["context_digest"],
            "snapshot_id": request["snapshot_id"],
            "foundation_digest": request["foundation_digest"],
            "plan_digest": request["plan_digest"],
            "strongest_counter_thesis": "Demand timing may not convert at the expected economics.",
            "challenges": ["Test conversion quality and unit economics."],
            "what_would_change": ["A source-bound conversion cohort would change the view."],
            "reroute": reroute,
        }
        return {
            **body,
            "runtime_receipt": _receipt(
                kind="model",
                actor=str(request["agent_id"]),
                request=request,
                body=body,
            ),
        }

    def lead(self, request: Mapping[str, Any]) -> dict[str, Any]:
        with self._lock:
            self.lead_calls += 1
        conclusions = [
            {
                "branch_id": row["branch_id"],
                "conclusion": f"Lead conclusion for {row['branch_id']}",
                "evidence_ids": row["evidence_ids"],
                "fact_ids": row["fact_ids"],
            }
            for row in request["workpapers"]
        ]
        body = {
            "agent_id": request["agent_id"],
            "context_digest": request["context_digest"],
            "snapshot_id": request["snapshot_id"],
            "foundation_digest": request["foundation_digest"],
            "plan_digest": request["plan_digest"],
            "verdict": "mixed_positive",
            "confidence": 65,
            "headline": "DELL demand conversion is positive but economics remain mixed.",
            "executive_summary": "The branch workpapers support a bounded, source-linked conclusion.",
            "branch_conclusions": conclusions,
            "counter_response": "The strongest countercase remains visible in monitoring conditions.",
        }
        return {
            **body,
            "runtime_receipt": _receipt(
                kind="model",
                actor=str(request["agent_id"]),
                request=request,
                body=body,
            ),
        }

    def dependencies(self) -> DellReferenceVerticalDependencies:
        return DellReferenceVerticalDependencies(
            foundation_binder=self.foundation_binder,
            planner_tool_capabilities=_planner_tool_capabilities(),
            planner_source_route_catalog=_source_route_catalog(),
            planner_agent=self.planner,
            evidence_tool=self.evidence_tool,
            finance_tool=self.finance_tool,
            specialist_agent=self.specialist,
            counter_agent=self.counter,
            lead_agent=self.lead,
        )


def _start_input() -> dict[str, Any]:
    return {
        "run_id": RUN_ID,
        "case_id": CASE_ID,
        "research_question": QUESTION,
        "research_as_of": RESEARCH_AS_OF,
        "snapshot_id": SNAPSHOT_ID,
        "foundation_digest": FOUNDATION_DIGEST,
    }


def _config(run_id: str = RUN_ID) -> dict[str, dict[str, str]]:
    return {"configurable": {"thread_id": run_id}}


def test_model_output_with_failure_receipt_is_rejected() -> None:
    runtime = FakeRuntime(planner_failure_receipt=True)
    graph = _build_dell_reference_vertical_test_graph(
        dependencies=runtime.dependencies(),
        checkpointer=InMemorySaver(),
    )

    with pytest.raises(
        DellReferenceVerticalGraphError,
        match="model_output_failure_receipt_not_allowed",
    ):
        graph.invoke(_start_input(), _config())


def test_foundation_scope_ceiling_blocks_unbounded_planner_and_reroute_requests() -> None:
    runtime = FakeRuntime()
    binding = CaseFoundationBinding.model_validate_json(
        json.dumps(runtime.foundation_binder(_start_input()))
    )
    external = lambda query: EvidenceIntentRequest.model_validate_json(
        json.dumps(_external_evidence_request(query))
    )

    with pytest.raises(
        DellReferenceVerticalGraphError,
        match="external_round_limit_exceeded",
    ):
        _validate_agent_step_budget(
            (external("one"), external("two"), external("three")),
            binding=binding,
            label="fixture",
        )

    reviewed = EvidenceIntentRequest.model_validate_json(
        json.dumps(_reviewed_evidence_request("reviewed", limit=6))
    )
    with pytest.raises(
        DellReferenceVerticalGraphError,
        match="visible_source_limit_exceeded",
    ):
        _validate_agent_step_budget(
            (
                reviewed,
                EvidenceIntentRequest.model_validate_json(
                    json.dumps(
                        _reviewed_evidence_request("reviewed two", limit=6)
                    )
                ),
            ),
            binding=binding,
            label="fixture",
        )

    with pytest.raises(
        DellReferenceVerticalGraphError,
        match="cumulative_capture_limit_exceeded",
    ):
        _validate_cumulative_branch_external_budget(
            (external("initial"), external("reroute"), external("reroute two")),
            binding=binding.model_copy(
                update={
                    "scope_ceiling": binding.scope_ceiling.model_copy(
                        update={
                            "maximum_external_search_rounds_per_high_materiality_branch": 3
                        }
                    )
                }
            ),
            label="fixture",
        )


def test_foundation_owns_specialist_round_ceiling_and_third_round_is_blocked() -> None:
    runtime = FakeRuntime()
    binding = CaseFoundationBinding.model_validate_json(
        json.dumps(runtime.foundation_binder(_start_input()))
    )

    assert binding.scope_ceiling.maximum_specialist_model_rounds == 2
    assert binding.scope_ceiling.maximum_specialist_model_rounds == (
        1 + binding.scope_ceiling.maximum_targeted_counter_reroutes
    )

    with pytest.raises(
        ValueError,
        match="specialist_round_ceiling_must_equal_initial_plus_counter_reroutes",
    ):
        AgentRuntimeScopeCeiling(
            maximum_external_search_rounds_per_high_materiality_branch=2,
            maximum_results_per_search=6,
            maximum_captured_pages_per_branch=4,
            maximum_live_pages_per_run=24,
            maximum_sources_visible_per_agent_step=10,
            maximum_specialist_model_rounds=1,
            maximum_targeted_counter_reroutes=1,
        )

    with pytest.raises(
        DellReferenceVerticalGraphError,
        match="specialist_round_limit_exceeded",
    ):
        _validate_specialist_round_authority(
            binding=binding,
            completed_rounds=2,
            requested_round=3,
        )


def _build(runtime: FakeRuntime, *, execution_profile: str = "product"):
    return _build_dell_reference_vertical_test_graph(
        dependencies=runtime.dependencies(),
        checkpointer=InMemorySaver(),
        execution_profile=execution_profile,
    )


def test_zero_model_qualification_calls_each_real_lane_once_and_resumes() -> None:
    runtime = FakeRuntime()

    def forbidden_model_port(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("zero-model qualification reached a model-owned port")

    dependencies = replace(
        runtime.dependencies(),
        planner_agent=forbidden_model_port,
        specialist_agent=forbidden_model_port,
        counter_agent=forbidden_model_port,
        lead_agent=forbidden_model_port,
    )
    graph = _build_dell_reference_vertical_test_graph(
        dependencies=dependencies,
        checkpointer=InMemorySaver(),
        execution_profile=ZERO_MODEL_EXECUTION_PROFILE,
    )

    interrupted = graph.invoke(_start_input(), _config())

    assert interrupted["phase"] == "zero_model_mcp_qualified"
    assert "__interrupt__" in interrupted
    assert Counter(runtime.calls) == Counter(
        {
            ("evidence", "Q1_ISSUER_TRUTH", 0): 1,
            ("finance", "Q1_ISSUER_TRUTH", 0): 1,
        }
    )
    assert runtime.planner_calls == 0
    assert runtime.specialist_inputs == []
    assert runtime.counter_calls == 0
    assert runtime.lead_calls == 0
    assert interrupted["final_report"] is None

    summary_json = json.dumps(
        interrupted["zero_model_qualification_summary"],
        ensure_ascii=False,
        sort_keys=True,
    )
    for forbidden in (
        "bounded_excerpt",
        "source_url",
        "value_decimal",
        "citation_urls",
        "D:/",
        "D:\\\\",
        "Z:/",
        "Z:\\\\",
        "/run/fin-insight",
        "postgres://",
        "redis://",
        "LANGSMITH_API_KEY",
    ):
        assert forbidden not in summary_json

    calls_before_resume = list(runtime.calls)
    completed = graph.invoke(
        Command(
            resume={
                "action": "complete_zero_model_qualification",
                "reason": "checkpoint/restart readback passed",
            }
        ),
        _config(),
    )

    assert completed["phase"] == "zero_model_control_plane_completed"
    assert completed["final_report"] is None
    assert runtime.calls == calls_before_resume
    assert completed["zero_model_qualification_decision"] == {
        "action": "complete_zero_model_qualification",
        "reason_provided": True,
        "reason_digest": canonical_sha256(
            {"reason": "checkpoint/restart readback passed"}
        ),
    }
    assert "checkpoint/restart readback passed" not in json.dumps(
        completed["zero_model_qualification_decision"]
    )


@pytest.mark.parametrize("failure_lane", ["evidence", "finance"])
def test_zero_model_qualification_tool_failure_cannot_reach_interrupt(
    failure_lane: str,
) -> None:
    runtime = FakeRuntime(
        tool_failure_branch="Q1_ISSUER_TRUTH",
        tool_failure_lane=failure_lane,
    )
    graph = _build(runtime, execution_profile=ZERO_MODEL_EXECUTION_PROFILE)

    with pytest.raises(
        DellReferenceVerticalGraphError,
        match=f"zero_model_qualification_{failure_lane}_not_success",
    ):
        graph.invoke(_start_input(), _config())
    assert runtime.planner_calls == 0
    assert runtime.specialist_inputs == []


def test_zero_model_qualification_resume_contract_is_strict() -> None:
    runtime = FakeRuntime()
    graph = _build(runtime, execution_profile=ZERO_MODEL_EXECUTION_PROFILE)
    graph.invoke(_start_input(), _config())
    calls_before_resume = list(runtime.calls)

    with pytest.raises(
        DellReferenceVerticalGraphError,
        match="zero_model_qualification_decision_invalid",
    ):
        graph.invoke(
            Command(
                resume={
                    "action": "approve",
                    "extra": "not allowed",
                }
            ),
            _config(),
        )
    assert runtime.calls == calls_before_resume


def test_execution_profile_is_strict_and_does_not_change_public_input() -> None:
    runtime = FakeRuntime()
    with pytest.raises(
        DellReferenceVerticalGraphError,
        match="dell_execution_profile_invalid",
    ):
        build_dell_reference_vertical_state_graph(
            dependencies=runtime.dependencies(),
            execution_profile="qualification",
        )

    graph = build_dell_reference_vertical_state_graph(
        dependencies=runtime.dependencies(),
        execution_profile=ZERO_MODEL_EXECUTION_PROFILE,
    ).compile(name="dell_zero_model_schema_test")
    schema = graph.input_schema.model_json_schema()
    assert set(schema["required"]) == {
        "run_id",
        "case_id",
        "research_question",
        "research_as_of",
        "snapshot_id",
        "foundation_digest",
    }
    assert "execution_profile" not in schema["properties"]
    assert "zero_model_qualification_summary" not in schema["properties"]


def test_dynamic_graph_parallel_fanout_agent_isolation_and_hitl_resume() -> None:
    runtime = FakeRuntime(barriers={0: Barrier(4)})
    graph = _build(runtime)

    interrupted = graph.invoke(_start_input(), _config())

    assert interrupted["phase"] == "awaiting_review"
    assert "__interrupt__" in interrupted
    assert Counter(runtime.calls) == Counter(
        {
            ("evidence", "Q1_ISSUER_TRUTH", 0): 1,
            ("finance", "Q1_ISSUER_TRUTH", 0): 1,
            ("evidence", "Q2_DEMAND_QUALITY", 0): 1,
            ("finance", "Q2_DEMAND_QUALITY", 0): 1,
        }
    )
    assert list(interrupted["initial_branch_inputs"]) == [
        "Q1_ISSUER_TRUTH",
        "Q2_DEMAND_QUALITY",
    ]
    assert len(runtime.specialist_inputs) == 2
    assert len({row["agent_id"] for row in runtime.specialist_inputs}) == 2
    assert len({row["context_digest"] for row in runtime.specialist_inputs}) == 2
    for row in runtime.specialist_inputs:
        branch_id = row["task"]["branch_id"]
        serialized = str(row)
        other = (
            "Q2_DEMAND_QUALITY"
            if branch_id == "Q1_ISSUER_TRUTH"
            else "Q1_ISSUER_TRUTH"
        )
        assert other not in serialized

    calls_before_resume = list(runtime.calls)
    specialist_count_before_resume = len(runtime.specialist_inputs)
    completed = graph.invoke(
        Command(resume={"action": "approve", "reason": "fixture accepted"}),
        _config(),
    )

    assert completed["phase"] == "completed"
    assert completed["final_report"]["reroute_count"] == 0
    assert [
        row["branch_id"] for row in completed["final_report"]["branch_workpapers"]
    ] == ["Q1_ISSUER_TRUTH", "Q2_DEMAND_QUALITY"]
    assert completed["final_report"]["runtime_summary"] == {
        "node_receipt_count": 9,
        "model_receipt_count": 5,
        "successful_model_call_count": 5,
        "failed_model_call_count": 0,
        "model_usage_reported_count": 5,
        "model_usage_missing_count": 0,
        "tool_lane_receipt_count": 4,
        "host_receipt_count": 0,
        "mcp_call_count": 0,
        "mcp_error_call_count": 0,
        "mcp_tool_call_counts": {},
        "input_tokens": 10,
        "output_tokens": 5,
        "total_tokens": 15,
        "node_receipt_elapsed_ms_sum_not_wall_clock": 9.0,
        "mcp_call_elapsed_ms_sum_not_wall_clock": 0.0,
        "failed_node_receipt_count": 0,
    }
    assert runtime.calls == calls_before_resume
    assert len(runtime.specialist_inputs) == specialist_count_before_resume
    assert runtime.counter_calls == 1
    assert runtime.lead_calls == 1


def test_counter_reroutes_only_one_branch_once_and_preserves_other_workpaper() -> None:
    runtime = FakeRuntime(
        reroute_branch="Q2_DEMAND_QUALITY",
        barriers={0: Barrier(4), 1: Barrier(2)},
    )
    graph = _build(runtime)

    interrupted = graph.invoke(_start_input(), _config())

    assert interrupted["phase"] == "awaiting_review"
    assert interrupted["reroute_count"] == 1
    assert Counter(runtime.calls) == Counter(
        {
            ("evidence", "Q1_ISSUER_TRUTH", 0): 1,
            ("finance", "Q1_ISSUER_TRUTH", 0): 1,
            ("evidence", "Q2_DEMAND_QUALITY", 0): 1,
            ("finance", "Q2_DEMAND_QUALITY", 0): 1,
            ("evidence", "Q2_DEMAND_QUALITY", 1): 1,
            ("finance", "Q2_DEMAND_QUALITY", 1): 1,
        }
    )
    turns = Counter(
        (row["task"]["branch_id"], row["turn_index"])
        for row in runtime.specialist_inputs
    )
    assert turns == Counter(
        {
            ("Q1_ISSUER_TRUTH", 1): 1,
            ("Q2_DEMAND_QUALITY", 1): 1,
            ("Q2_DEMAND_QUALITY", 2): 1,
        }
    )
    q2_turns = [
        row
        for row in runtime.specialist_inputs
        if row["task"]["branch_id"] == "Q2_DEMAND_QUALITY"
    ]
    assert q2_turns[0]["agent_id"] == q2_turns[1]["agent_id"]
    assert q2_turns[0]["context_digest"] != q2_turns[1]["context_digest"]
    assert q2_turns[1]["prior_workpaper"]["revision"] == 0
    assert q2_turns[1]["counter_challenge"]["challenge_id"] == "counter-challenge-1"
    assert interrupted["effective_workpapers_by_branch"]["Q1_ISSUER_TRUTH"]["revision"] == 0
    assert interrupted["effective_workpapers_by_branch"]["Q2_DEMAND_QUALITY"]["revision"] == 1
    assert runtime.counter_calls == 1
    assert runtime.lead_calls == 1

    calls_before_resume = list(runtime.calls)
    specialist_count_before_resume = len(runtime.specialist_inputs)
    completed = graph.invoke(Command(resume={"action": "approve"}), _config())
    assert completed["phase"] == "completed"
    assert completed["final_report"]["reroute_count"] == 1
    assert runtime.calls == calls_before_resume
    assert len(runtime.specialist_inputs) == specialist_count_before_resume
    assert runtime.counter_calls == 1
    assert runtime.lead_calls == 1


@pytest.mark.parametrize(
    ("failure_lane", "owner_layer"),
    [("evidence", "s1_tool"), ("finance", "s2_tool")],
)
def test_expected_tool_failure_stays_typed_and_blocks_approval(
    failure_lane: str,
    owner_layer: str,
) -> None:
    runtime = FakeRuntime(
        tool_failure_branch="Q2_DEMAND_QUALITY",
        tool_failure_lane=failure_lane,
    )
    graph = _build(runtime)

    interrupted = graph.invoke(_start_input(), _config())

    failed = next(
        row
        for row in interrupted[f"initial_{failure_lane}_results"]
        if row["branch_id"] == "Q2_DEMAND_QUALITY"
    )
    assert failed["status"] == "tool_failure"
    assert failed["result_states"] == ["tool_failure"]
    assert failed["failure"]["owner_layer"] == owner_layer
    workpapers = interrupted["initial_workpapers_by_branch"]
    assert workpapers["Q2_DEMAND_QUALITY"][
        "terminal_state"
    ] == "incomplete_tool_failure"
    assert workpapers["Q2_DEMAND_QUALITY"]["runtime_receipt"]["kind"] == "host"
    assert workpapers["Q1_ISSUER_TRUTH"]["terminal_state"] == "supported"
    assert len(runtime.specialist_inputs) == 1
    assert runtime.specialist_inputs[0]["task"]["branch_id"] == "Q1_ISSUER_TRUTH"
    assert interrupted.get("verification") is None
    assert interrupted["fatal_tool_failure_branches"] == ["Q2_DEMAND_QUALITY"]
    assert interrupted["phase"] == "fatal_tool_failure_before_synthesis"
    assert runtime.counter_calls == 0
    assert runtime.lead_calls == 0
    assert "__interrupt__" not in interrupted
    assert interrupted.get("final_report") is None


@pytest.mark.parametrize("terminal_state", ["supported", "not_material", "bounded_gap"])
def test_tool_failure_cannot_be_consumed_as_completed_branch_state(
    terminal_state: str,
) -> None:
    runtime = FakeRuntime(
        tool_failure_branch="Q2_DEMAND_QUALITY",
        tool_failure_terminal_state=terminal_state,
    )
    graph = _build(runtime)
    result = graph.invoke(_start_input(), _config())
    agent_input = BranchAgentInput.model_validate_json(
        __import__("json").dumps(
            result["initial_branch_inputs"]["Q2_DEMAND_QUALITY"]
        )
    )
    malicious = BranchWorkpaper.model_validate_json(
        __import__("json").dumps(
            runtime.specialist(agent_input.model_dump(mode="json"))
        )
    )
    with pytest.raises(
        DellReferenceVerticalGraphError,
        match="tool_failure_requires_incomplete_workpaper",
    ):
        _validate_workpaper(malicious, agent_input=agent_input)


def test_join_rejects_duplicate_missing_and_cross_branch_lane_results() -> None:
    runtime = FakeRuntime()
    methods = {row.branch_id: row for row in runtime.method_bindings()}
    plan_digest = canonical_sha256({"plan": "fixture"})
    tasks = {
        branch_id: BoundBranchTask(
            task_id=f"task:{branch_id}",
            case_id=CASE_ID,
            branch_id=branch_id,
            revision=0,
            priority="high",
            objective=f"Objective {branch_id}",
            evidence_requests=(
                _reviewed_evidence_request(branch_id, branch_id=branch_id),
            ),
            fact_requests=({"metric_id": branch_id},),
            research_as_of=RESEARCH_AS_OF,
            snapshot_id=SNAPSHOT_ID,
            foundation_digest=FOUNDATION_DIGEST,
            method_digest=methods[branch_id].method_digest,
            plan_digest=plan_digest,
        )
        for branch_id in methods
    }
    evidence = [
        runtime.evidence_tool(
            ToolLaneTask(lane="evidence", task=task).model_dump(mode="json")
        )
        for task in tasks.values()
    ]
    finance = [
        runtime.finance_tool(
            ToolLaneTask(lane="finance", task=task).model_dump(mode="json")
        )
        for task in tasks.values()
    ]

    with pytest.raises(DellReferenceVerticalGraphError, match="duplicate"):
        _join_initial_lane_results(
            tasks=tasks,
            evidence_values=[evidence[0], evidence[0], evidence[1]],
            finance_values=finance,
        )
    with pytest.raises(DellReferenceVerticalGraphError, match="set_mismatch"):
        _join_initial_lane_results(
            tasks=tasks,
            evidence_values=evidence[:1],
            finance_values=finance,
        )

    cross_branch = dict(evidence[0])
    cross_branch["branch_id"] = "Q2_DEMAND_QUALITY"
    with pytest.raises(DellReferenceVerticalGraphError, match="binding_mismatch"):
        _join_initial_lane_results(
            tasks=tasks,
            evidence_values=[cross_branch, evidence[1]],
            finance_values=finance,
        )


def test_local_test_wrapper_requires_checkpointer_and_exact_thread_binding() -> None:
    runtime = FakeRuntime()
    with pytest.raises(
        DellReferenceVerticalGraphError,
        match="checkpointer_required",
    ):
        _build_dell_reference_vertical_test_graph(
            dependencies=runtime.dependencies(),
            checkpointer=None,
        )

    graph = _build(runtime)
    with pytest.raises(DellReferenceVerticalGraphError, match="thread_id_run_id_mismatch"):
        graph.invoke(_start_input(), _config("another-thread"))
    with pytest.raises(DellReferenceVerticalGraphError, match="command_update_not_allowed"):
        graph.invoke(Command(update={"phase": "completed"}), _config())


def test_agent_server_builder_has_strict_public_input_and_no_app_persistence() -> None:
    runtime = FakeRuntime()
    builder = build_dell_reference_vertical_state_graph(
        dependencies=runtime.dependencies()
    )
    graph = builder.compile(name="dell_reference_vertical_agent_server_test")

    assert graph.checkpointer is None
    assert graph.store is None
    schema = graph.input_schema.model_json_schema()
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {
        "run_id",
        "case_id",
        "research_question",
        "research_as_of",
        "snapshot_id",
        "foundation_digest",
    }
    assert not {
        "phase",
        "planner_output",
        "human_review",
        "final_report",
    }.intersection(schema["properties"])


def test_tool_result_identity_drift_fails_before_specialist() -> None:
    runtime = FakeRuntime(bad_tool_binding_branch="Q2_DEMAND_QUALITY")
    graph = _build(runtime)

    with pytest.raises(
        DellReferenceVerticalGraphError,
        match="tool_lane_result_binding_mismatch",
    ):
        graph.invoke(_start_input(), _config())
    assert runtime.specialist_inputs == []
