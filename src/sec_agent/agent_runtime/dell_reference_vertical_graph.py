"""Bounded dynamic multi-agent graph for the single DELL reference vertical.

The topology is deliberately fixed while branch instances are dynamic:

bind -> plan -> Evidence/Finance map -> join -> Specialist map -> join ->
Counter -> optional one-branch rework -> Lead -> verify -> HITL -> render.

All data, model, and tool behavior is injected.  This module does not import a
provider SDK, MCP client, Dagster, Workbench, or a concrete database adapter.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Literal, TypeVar, cast

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, Send, interrupt
from pydantic import BaseModel, ValidationError

from .dell_reference_vertical_contracts import (
    BoundBranchTask,
    BranchAgentInput,
    BranchMethodBinding,
    BranchWorkpaper,
    CaseFoundationBinding,
    CounterDecision,
    DellReferenceVerticalState,
    EvidenceRequest,
    HumanReviewDecision,
    LeadOutput,
    PlannerOutput,
    RuntimeReceipt,
    ToolFailure,
    ToolLaneResult,
    ToolLaneTask,
    VerificationResult,
    canonical_sha256,
)
from .planner_tool_capabilities import PlannerToolCapabilityProjection


GRAPH_CONTRACT_VERSION = "fin_ia_dell_reference_vertical_graph_v1_0"

PlainDict = dict[str, Any]
FoundationBinder = Callable[[Mapping[str, Any]], Mapping[str, Any]]
PlannerAgent = Callable[[Mapping[str, Any]], Mapping[str, Any]]
ToolExecutor = Callable[[Mapping[str, Any]], Mapping[str, Any]]
SpecialistAgent = Callable[[Mapping[str, Any]], Mapping[str, Any]]
CounterAgent = Callable[[Mapping[str, Any]], Mapping[str, Any]]
LeadAgent = Callable[[Mapping[str, Any]], Mapping[str, Any]]

ModelT = TypeVar("ModelT", bound=BaseModel)


class DellReferenceVerticalGraphError(ValueError):
    """Fail-closed graph boundary or state-invariant error."""


@dataclass(frozen=True)
class DellReferenceVerticalDependencies:
    foundation_binder: FoundationBinder
    planner_tool_capabilities: Mapping[str, Any]
    planner_agent: PlannerAgent
    evidence_tool: ToolExecutor
    finance_tool: ToolExecutor
    specialist_agent: SpecialistAgent
    counter_agent: CounterAgent
    lead_agent: LeadAgent


class DellReferenceVerticalCompiledGraph:
    """Narrow start/resume surface around the compiled LangGraph."""

    __slots__ = ("_compiled",)

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
            return Command(resume=_plain_json(value.resume, label="resume_value"))

        initial = _plain_mapping(value, label="initial_graph_input")
        allowed = {
            "run_id",
            "case_id",
            "research_question",
            "research_as_of",
            "snapshot_id",
            "foundation_digest",
        }
        unexpected = sorted(set(initial).difference(allowed))
        if unexpected:
            raise DellReferenceVerticalGraphError(
                f"initial_graph_input_unexpected_keys:{','.join(unexpected)}"
            )
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

    def continue_from_checkpoint(
        self,
        config: Mapping[str, Any],
        **kwargs: Any,
    ) -> Any:
        """Continue only the next persisted node without accepting new state.

        This narrow path exists for recovery from a process interruption after
        HITL approval was checkpointed but before the deterministic render node
        completed.  It cannot be used to start a graph or mutate checkpointed
        values.
        """

        self._thread_id(config)
        return self._compiled.invoke(None, config, **kwargs)

    async def ainvoke(
        self,
        value: Any,
        config: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        return await self._compiled.ainvoke(
            self._safe_input(value, config), config, **kwargs
        )

    def get_state(self, config: Mapping[str, Any], **kwargs: Any) -> Any:
        self._thread_id(config)
        return self._compiled.get_state(config, **kwargs)

    def get_state_history(self, config: Mapping[str, Any], **kwargs: Any) -> Any:
        self._thread_id(config)
        return self._compiled.get_state_history(config, **kwargs)

    def get_graph(self, **kwargs: Any) -> Any:
        return self._compiled.get_graph(**kwargs)


def _plain_json(value: Any, *, label: str) -> Any:
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise DellReferenceVerticalGraphError(
            f"{label}_must_be_json_serializable"
        ) from exc


def _plain_mapping(value: Any, *, label: str) -> PlainDict:
    if not isinstance(value, Mapping):
        raise DellReferenceVerticalGraphError(f"{label}_must_be_mapping")
    result = _plain_json(dict(value), label=label)
    if not isinstance(result, dict):  # pragma: no cover - guarded by Mapping
        raise DellReferenceVerticalGraphError(f"{label}_must_be_mapping")
    return cast(PlainDict, result)


def _validate_model(model: type[ModelT], value: Any, *, label: str) -> ModelT:
    """Validate at a strict JSON boundary, not through permissive Python coercion."""

    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
        return model.model_validate_json(encoded)
    except (TypeError, ValueError, ValidationError) as exc:
        raise DellReferenceVerticalGraphError(f"{label}_invalid") from exc


def _require_text(value: Any, *, label: str, maximum: int = 2_000) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DellReferenceVerticalGraphError(f"{label}_missing_or_empty")
    normalized = value.strip()
    if len(normalized) > maximum:
        raise DellReferenceVerticalGraphError(f"{label}_too_long")
    return normalized


def _model_output_body(value: BaseModel) -> PlainDict:
    body = value.model_dump(mode="json")
    body.pop("runtime_receipt", None)
    return cast(PlainDict, body)


def _validate_receipt(
    receipt: RuntimeReceipt,
    *,
    kind: Literal["model", "tool", "host"],
    actor: str,
    request: Any,
    output: Any | None,
) -> None:
    if receipt.kind != kind:
        raise DellReferenceVerticalGraphError("runtime_receipt_kind_mismatch")
    if receipt.actor != actor:
        raise DellReferenceVerticalGraphError("runtime_receipt_actor_mismatch")
    if kind == "model" and receipt.status != "success":
        raise DellReferenceVerticalGraphError(
            "model_output_failure_receipt_not_allowed"
        )
    if receipt.request_digest != canonical_sha256(request):
        raise DellReferenceVerticalGraphError("runtime_receipt_request_digest_mismatch")
    if receipt.status == "success":
        if output is None or receipt.output_digest != canonical_sha256(output):
            raise DellReferenceVerticalGraphError(
                "runtime_receipt_output_digest_mismatch"
            )


def _method_by_branch(
    binding: CaseFoundationBinding,
) -> dict[str, BranchMethodBinding]:
    return {row.branch_id: row for row in binding.branch_methods}


def _evidence_requests(
    values: Sequence[Mapping[str, Any]], *, label: str
) -> tuple[EvidenceRequest, ...]:
    return tuple(
        _validate_model(EvidenceRequest, value, label=f"{label}_request")
        for value in values
    )


def _external_budget(requests: Sequence[EvidenceRequest]) -> tuple[int, int]:
    external = tuple(
        row for row in requests if row.source_route == "external_required"
    )
    return len(external), sum(row.capture_limit for row in external)


def _validate_agent_step_budget(
    requests: Sequence[EvidenceRequest],
    *,
    binding: CaseFoundationBinding,
    label: str,
) -> None:
    ceiling = binding.scope_ceiling
    if any(row.limit > ceiling.maximum_results_per_search for row in requests):
        raise DellReferenceVerticalGraphError(f"{label}_result_limit_exceeded")
    if sum(row.limit for row in requests) > ceiling.maximum_sources_visible_per_agent_step:
        raise DellReferenceVerticalGraphError(f"{label}_visible_source_limit_exceeded")
    external_rounds, captured_pages = _external_budget(requests)
    if (
        external_rounds
        > ceiling.maximum_external_search_rounds_per_high_materiality_branch
    ):
        raise DellReferenceVerticalGraphError(f"{label}_external_round_limit_exceeded")
    if captured_pages > ceiling.maximum_captured_pages_per_branch:
        raise DellReferenceVerticalGraphError(f"{label}_capture_limit_exceeded")


def _validate_cumulative_branch_external_budget(
    requests: Sequence[EvidenceRequest],
    *,
    binding: CaseFoundationBinding,
    label: str,
) -> None:
    external_rounds, captured_pages = _external_budget(requests)
    ceiling = binding.scope_ceiling
    if (
        external_rounds
        > ceiling.maximum_external_search_rounds_per_high_materiality_branch
    ):
        raise DellReferenceVerticalGraphError(
            f"{label}_cumulative_external_round_limit_exceeded"
        )
    if captured_pages > ceiling.maximum_captured_pages_per_branch:
        raise DellReferenceVerticalGraphError(
            f"{label}_cumulative_capture_limit_exceeded"
        )


def _task_by_branch(state: Mapping[str, Any]) -> dict[str, BoundBranchTask]:
    tasks = [_validate_model(BoundBranchTask, row, label="bound_branch_task") for row in state.get("branch_tasks", [])]
    return {row.branch_id: row for row in tasks}


def _task_id(*, run_id: str, branch_id: str, revision: int, plan_digest: str) -> str:
    suffix = canonical_sha256(
        {
            "run_id": run_id,
            "branch_id": branch_id,
            "revision": revision,
            "plan_digest": plan_digest,
        }
    )[:24]
    return f"task:{branch_id}:r{revision}:{suffix}"


def _agent_id(*, run_id: str, role: str, branch_id: str | None = None) -> str:
    suffix = canonical_sha256(
        {"run_id": run_id, "role": role, "branch_id": branch_id}
    )[:16]
    return f"{role}:{branch_id or 'global'}:{suffix}"


def _tool_result_body(result: ToolLaneResult) -> PlainDict:
    body = result.model_dump(mode="json")
    body.pop("runtime_receipt", None)
    identity_fields = {
        "lane",
        "task_id",
        "case_id",
        "branch_id",
        "revision",
        "research_as_of",
        "snapshot_id",
        "foundation_digest",
        "method_digest",
        "plan_digest",
    }
    return cast(PlainDict, {key: value for key, value in body.items() if key not in identity_fields})


def _validate_tool_result(
    result: ToolLaneResult,
    *,
    lane_task: ToolLaneTask,
) -> None:
    task = lane_task.task
    expected = {
        "lane": lane_task.lane,
        "task_id": task.task_id,
        "case_id": task.case_id,
        "branch_id": task.branch_id,
        "revision": task.revision,
        "research_as_of": task.research_as_of,
        "snapshot_id": task.snapshot_id,
        "foundation_digest": task.foundation_digest,
        "method_digest": task.method_digest,
        "plan_digest": task.plan_digest,
    }
    actual = {key: getattr(result, key) for key in expected}
    if actual != expected:
        raise DellReferenceVerticalGraphError("tool_lane_result_binding_mismatch")
    _validate_receipt(
        result.runtime_receipt,
        kind="tool" if result.runtime_receipt.kind == "tool" else "host",
        actor=f"{lane_task.lane}_tool",
        request=lane_task.model_dump(mode="json"),
        output=(
            _tool_result_body(result)
            if result.runtime_receipt.status == "success"
            else None
        ),
    )


def _host_tool_result(
    *,
    lane_task: ToolLaneTask,
    status: Literal["not_applicable", "tool_failure"],
    elapsed_ms: float,
    failure: ToolFailure | None = None,
) -> ToolLaneResult:
    task = lane_task.task
    body: PlainDict
    if status == "not_applicable":
        body = {
            "status": "not_applicable",
            "result_states": ["not_applicable"],
            "items": [],
            "failure": None,
        }
        receipt_status: Literal["success", "failure"] = "success"
    else:
        body = {
            "status": "tool_failure",
            "result_states": ["tool_failure"],
            "items": [],
            "failure": failure.model_dump(mode="json") if failure else None,
        }
        receipt_status = "failure"
    receipt = RuntimeReceipt(
        receipt_id=f"{task.task_id}:{lane_task.lane}",
        kind="host",
        actor=f"{lane_task.lane}_tool",
        status=receipt_status,
        request_digest=canonical_sha256(lane_task),
        output_digest=canonical_sha256(body) if receipt_status == "success" else None,
        elapsed_ms=elapsed_ms,
    )
    return ToolLaneResult(
        lane=lane_task.lane,
        task_id=task.task_id,
        case_id=task.case_id,
        branch_id=task.branch_id,
        revision=task.revision,
        research_as_of=task.research_as_of,
        snapshot_id=task.snapshot_id,
        foundation_digest=task.foundation_digest,
        method_digest=task.method_digest,
        plan_digest=task.plan_digest,
        status=status,
        result_states=("not_applicable",) if status == "not_applicable" else ("tool_failure",),
        items=(),
        failure=failure,
        runtime_receipt=receipt,
    )


def _execute_tool(
    lane_task_value: Mapping[str, Any],
    *,
    executor: ToolExecutor,
) -> ToolLaneResult:
    lane_task = _validate_model(ToolLaneTask, lane_task_value, label="tool_lane_task")
    if lane_task.lane == "finance" and not lane_task.task.fact_requests:
        return _host_tool_result(
            lane_task=lane_task,
            status="not_applicable",
            elapsed_ms=0.0,
        )
    started = perf_counter()
    try:
        raw = executor(lane_task.model_dump(mode="json"))
        result = _validate_model(ToolLaneResult, raw, label="tool_lane_result")
        _validate_tool_result(result, lane_task=lane_task)
        return result
    except DellReferenceVerticalGraphError:
        raise
    except Exception as exc:
        owner_layer: Literal["s1_tool", "s2_tool"] = (
            "s1_tool" if lane_task.lane == "evidence" else "s2_tool"
        )
        return _host_tool_result(
            lane_task=lane_task,
            status="tool_failure",
            elapsed_ms=round((perf_counter() - started) * 1_000, 3),
            failure=ToolFailure(
                code=f"{lane_task.lane}_tool_unreceipted_failure",
                owner_layer=owner_layer,
                retryable=False,
                exception_type=type(exc).__name__,
            ),
        )


def _index_lane_results(
    values: Sequence[Mapping[str, Any]],
    *,
    label: str,
) -> dict[tuple[str, str], ToolLaneResult]:
    indexed: dict[tuple[str, str], ToolLaneResult] = {}
    for value in values:
        result = _validate_model(ToolLaneResult, value, label=label)
        key = (result.task_id, result.lane)
        if key in indexed:
            raise DellReferenceVerticalGraphError(f"{label}_duplicate")
        indexed[key] = result
    return indexed


def _join_initial_lane_results(
    *,
    tasks: Mapping[str, BoundBranchTask],
    evidence_values: Sequence[Mapping[str, Any]],
    finance_values: Sequence[Mapping[str, Any]],
) -> dict[str, tuple[ToolLaneResult, ToolLaneResult]]:
    """Validate the exact dynamic map result set and return canonical branch order."""

    evidence = _index_lane_results(
        evidence_values,
        label="initial_evidence_results",
    )
    finance = _index_lane_results(
        finance_values,
        label="initial_finance_results",
    )
    expected_evidence = {(row.task_id, "evidence") for row in tasks.values()}
    expected_finance = {(row.task_id, "finance") for row in tasks.values()}
    if set(evidence) != expected_evidence:
        raise DellReferenceVerticalGraphError("initial_evidence_result_set_mismatch")
    if set(finance) != expected_finance:
        raise DellReferenceVerticalGraphError("initial_finance_result_set_mismatch")

    joined: dict[str, tuple[ToolLaneResult, ToolLaneResult]] = {}
    for branch_id, task in sorted(tasks.items()):
        evidence_result = evidence[(task.task_id, "evidence")]
        finance_result = finance[(task.task_id, "finance")]
        _validate_tool_result(
            evidence_result,
            lane_task=ToolLaneTask(lane="evidence", task=task),
        )
        _validate_tool_result(
            finance_result,
            lane_task=ToolLaneTask(lane="finance", task=task),
        )
        joined[branch_id] = (evidence_result, finance_result)
    return joined


def _branch_context(
    *,
    run_id: str,
    task: BoundBranchTask,
    method: BranchMethodBinding,
    evidence: ToolLaneResult,
    finance: ToolLaneResult,
    turn_index: Literal[1, 2],
    prior_workpaper: BranchWorkpaper | None = None,
    counter_challenge: Mapping[str, Any] | None = None,
) -> BranchAgentInput:
    actor = _agent_id(run_id=run_id, role="specialist", branch_id=task.branch_id)
    unsigned = {
        "agent_id": actor,
        "turn_index": turn_index,
        "task": task.model_dump(mode="json"),
        "method_context": method.method_context,
        "evidence_result": evidence.model_dump(mode="json"),
        "finance_result": finance.model_dump(mode="json"),
        "prior_workpaper": (
            prior_workpaper.model_dump(mode="json") if prior_workpaper else None
        ),
        "counter_challenge": (
            _plain_mapping(counter_challenge, label="counter_challenge")
            if counter_challenge is not None
            else None
        ),
    }
    return _validate_model(
        BranchAgentInput,
        {
            "context_digest": canonical_sha256(unsigned),
            **unsigned,
        },
        label="branch_agent_input",
    )


def _reference_ids(result: ToolLaneResult) -> tuple[set[str], set[str]]:
    evidence_ids: set[str] = set()
    fact_ids: set[str] = set()
    for item in result.items:
        evidence_id = item.get("evidence_id")
        fact_id = item.get("fact_id")
        relation_id = item.get("relation_id")
        if isinstance(evidence_id, str) and evidence_id:
            evidence_ids.add(evidence_id)
        if isinstance(fact_id, str) and fact_id:
            fact_ids.add(fact_id)
        if isinstance(relation_id, str) and relation_id:
            fact_ids.add(relation_id)
    return evidence_ids, fact_ids


def _validate_workpaper(
    workpaper: BranchWorkpaper,
    *,
    agent_input: BranchAgentInput,
) -> None:
    task = agent_input.task
    expected = {
        "branch_id": task.branch_id,
        "revision": task.revision,
        "agent_id": agent_input.agent_id,
        "context_digest": agent_input.context_digest,
        "snapshot_id": task.snapshot_id,
        "foundation_digest": task.foundation_digest,
        "method_digest": task.method_digest,
        "plan_digest": task.plan_digest,
    }
    actual = {key: getattr(workpaper, key) for key in expected}
    if actual != expected:
        raise DellReferenceVerticalGraphError("branch_workpaper_binding_mismatch")
    expected_receipts = {
        agent_input.evidence_result.runtime_receipt.receipt_id,
        agent_input.finance_result.runtime_receipt.receipt_id,
    }
    if set(workpaper.tool_receipt_ids) != expected_receipts:
        raise DellReferenceVerticalGraphError("branch_workpaper_tool_receipt_mismatch")
    evidence_ids, fact_ids = _reference_ids(agent_input.evidence_result)
    more_evidence, more_facts = _reference_ids(agent_input.finance_result)
    evidence_ids.update(more_evidence)
    fact_ids.update(more_facts)
    unknown_evidence = set(workpaper.evidence_ids).difference(evidence_ids)
    unknown_facts = set(workpaper.fact_ids).difference(fact_ids)
    if unknown_evidence:
        raise DellReferenceVerticalGraphError("branch_workpaper_unknown_evidence_id")
    if unknown_facts:
        raise DellReferenceVerticalGraphError("branch_workpaper_unknown_fact_id")
    has_tool_failure = (
        agent_input.evidence_result.status == "tool_failure"
        or agent_input.finance_result.status == "tool_failure"
    )
    if has_tool_failure and workpaper.terminal_state != "incomplete_tool_failure":
        raise DellReferenceVerticalGraphError(
            "tool_failure_requires_incomplete_workpaper"
        )
    if not has_tool_failure and workpaper.terminal_state == "incomplete_tool_failure":
        raise DellReferenceVerticalGraphError(
            "incomplete_workpaper_requires_tool_failure"
        )
    receipt_kind: Literal["model", "host"] = (
        "host" if workpaper.terminal_state == "incomplete_tool_failure" else "model"
    )
    _validate_receipt(
        workpaper.runtime_receipt,
        kind=receipt_kind,
        actor=agent_input.agent_id,
        request=agent_input.model_dump(mode="json"),
        output=_model_output_body(workpaper),
    )


def _run_specialist(
    value: Mapping[str, Any],
    *,
    agent: SpecialistAgent,
) -> BranchWorkpaper:
    agent_input = _validate_model(BranchAgentInput, value, label="branch_agent_input")
    failed_lanes = [
        (lane, result)
        for lane, result in (
            ("evidence", agent_input.evidence_result),
            ("finance", agent_input.finance_result),
        )
        if result.status == "tool_failure"
    ]
    if failed_lanes:
        task = agent_input.task
        body = {
            "branch_id": task.branch_id,
            "revision": task.revision,
            "agent_id": agent_input.agent_id,
            "context_digest": agent_input.context_digest,
            "snapshot_id": task.snapshot_id,
            "foundation_digest": task.foundation_digest,
            "method_digest": task.method_digest,
            "plan_digest": task.plan_digest,
            "terminal_state": "incomplete_tool_failure",
            "thesis": (
                "No branch conclusion was formed because a required tool lane "
                "failed."
            ),
            "mechanism": (
                "The typed failure remains owned by its tool layer; the specialist "
                "model was not called and no research gap was inferred."
            ),
            "counterevidence": (
                "Counterevidence adjudication was not attempted for this branch.",
            ),
            "what_would_change": (
                "A successful scope-bound execution of every failed tool lane.",
            ),
            "evidence_ids": (),
            "fact_ids": (),
            "open_gaps": tuple(
                f"{lane}_tool_failure:{result.failure.code}"
                for lane, result in failed_lanes
                if result.failure is not None
            ),
            "tool_receipt_ids": (
                agent_input.evidence_result.runtime_receipt.receipt_id,
                agent_input.finance_result.runtime_receipt.receipt_id,
            ),
        }
        receipt = RuntimeReceipt(
            receipt_id=f"{task.task_id}:specialist:incomplete",
            kind="host",
            actor=agent_input.agent_id,
            status="success",
            request_digest=canonical_sha256(agent_input),
            output_digest=canonical_sha256(body),
            elapsed_ms=0.0,
        )
        workpaper = BranchWorkpaper(**body, runtime_receipt=receipt)
        _validate_workpaper(workpaper, agent_input=agent_input)
        return workpaper
    raw = agent(agent_input.model_dump(mode="json"))
    workpaper = _validate_model(BranchWorkpaper, raw, label="branch_workpaper")
    _validate_workpaper(workpaper, agent_input=agent_input)
    return workpaper


def _workpaper_map(
    values: Sequence[Mapping[str, Any]],
    *,
    expected_branch_ids: set[str],
    revision: int,
) -> dict[str, BranchWorkpaper]:
    indexed: dict[str, BranchWorkpaper] = {}
    for value in values:
        row = _validate_model(BranchWorkpaper, value, label="branch_workpaper")
        if row.revision != revision:
            raise DellReferenceVerticalGraphError("branch_workpaper_revision_invalid")
        if row.branch_id in indexed:
            raise DellReferenceVerticalGraphError("branch_workpaper_duplicate")
        indexed[row.branch_id] = row
    if set(indexed) != expected_branch_ids:
        raise DellReferenceVerticalGraphError("branch_workpaper_set_mismatch")
    return dict(sorted(indexed.items()))


def _lead_reference_sets(
    workpapers: Mapping[str, BranchWorkpaper],
) -> tuple[set[str], set[str]]:
    evidence_ids = {
        value for row in workpapers.values() for value in row.evidence_ids
    }
    fact_ids = {value for row in workpapers.values() for value in row.fact_ids}
    return evidence_ids, fact_ids


_EVIDENCE_CITATION_FIELDS = (
    "authority_state",
    "writer_citable",
    "evidence_id",
    "target_id",
    "evidence_role",
    "publication_date",
    "source_reporting_period_end",
    "research_as_of",
    "source_type",
    "source_tier",
    "source_url",
    "source_record_id",
    "source_locator",
    "source_content_digest",
    "bounded_excerpt",
    "excerpt_truncated",
    "numeric_use_boundary",
    "causal_attribution_authorized",
    "evidence_item_digest",
    "result_state",
)
_FACT_CITATION_FIELDS = (
    "fact_id",
    "numeric_fact_id",
    "fact_request_id",
    "ticker",
    "metric_id",
    "value_decimal",
    "unit",
    "unit_family",
    "period_start",
    "period_end",
    "period_role",
    "fiscal_year",
    "fiscal_period",
    "research_as_of",
    "authority_mode",
    "accession_numbers",
    "accepted_at",
    "source_observation_ids",
    "citation_urls",
    "source_digests",
    "formula_trace",
    "numeric_fact_authority",
    "result_state",
)


def _citation_index(state: Mapping[str, Any]) -> PlainDict:
    effective_raw = state.get("effective_workpapers_by_branch")
    if not isinstance(effective_raw, Mapping):
        raise DellReferenceVerticalGraphError("citation_workpapers_missing")
    workpapers = {
        str(branch_id): _validate_model(
            BranchWorkpaper,
            value,
            label="citation_workpaper",
        )
        for branch_id, value in effective_raw.items()
    }
    evidence_branches: dict[str, set[str]] = {}
    fact_branches: dict[str, set[str]] = {}
    for branch_id, workpaper in workpapers.items():
        for evidence_id in workpaper.evidence_ids:
            evidence_branches.setdefault(evidence_id, set()).add(branch_id)
        for fact_id in workpaper.fact_ids:
            fact_branches.setdefault(fact_id, set()).add(branch_id)

    results: list[ToolLaneResult] = []
    for key in ("initial_evidence_results", "initial_finance_results"):
        results.extend(
            _validate_model(ToolLaneResult, value, label=key)
            for value in state.get(key, [])
        )
    for key in ("rework_evidence_result", "rework_finance_result"):
        value = state.get(key)
        if isinstance(value, Mapping):
            results.append(_validate_model(ToolLaneResult, value, label=key))

    evidence_index: dict[str, PlainDict] = {}
    fact_index: dict[str, PlainDict] = {}
    for result in results:
        for item in result.items:
            evidence_id = item.get("evidence_id")
            if isinstance(evidence_id, str) and evidence_id in evidence_branches:
                if not (
                    item.get("result_state") == "reviewed_evidence"
                    and item.get("writer_citable") is True
                    and isinstance(item.get("source_url"), str)
                    and str(item.get("source_url")).startswith("https://")
                    and isinstance(item.get("source_content_digest"), str)
                    and len(str(item.get("source_content_digest"))) == 64
                ):
                    raise DellReferenceVerticalGraphError(
                        "citation_evidence_projection_incomplete"
                    )
                projection = {
                    key: _plain_json(item.get(key), label="citation_evidence_field")
                    for key in _EVIDENCE_CITATION_FIELDS
                }
                prior = evidence_index.get(evidence_id)
                if prior is not None and canonical_sha256(prior) != canonical_sha256(
                    projection
                ):
                    raise DellReferenceVerticalGraphError(
                        "citation_evidence_identity_conflict"
                    )
                evidence_index[evidence_id] = projection

            fact_id = item.get("fact_id") or item.get("relation_id")
            if isinstance(fact_id, str) and fact_id in fact_branches:
                if not (
                    item.get("result_state")
                    in {"numeric_fact", "deterministic_derived_metric"}
                    and item.get("numeric_fact_authority") is True
                    and isinstance(item.get("citation_urls"), Sequence)
                    and not isinstance(item.get("citation_urls"), (str, bytes))
                    and isinstance(item.get("source_digests"), Sequence)
                    and not isinstance(item.get("source_digests"), (str, bytes))
                ):
                    raise DellReferenceVerticalGraphError(
                        "citation_fact_projection_incomplete"
                    )
                projection = {
                    key: _plain_json(item.get(key), label="citation_fact_field")
                    for key in _FACT_CITATION_FIELDS
                }
                projection["fact_id"] = fact_id
                prior = fact_index.get(fact_id)
                if prior is not None and canonical_sha256(prior) != canonical_sha256(
                    projection
                ):
                    raise DellReferenceVerticalGraphError(
                        "citation_fact_identity_conflict"
                    )
                fact_index[fact_id] = projection

    missing_evidence = sorted(set(evidence_branches).difference(evidence_index))
    missing_facts = sorted(set(fact_branches).difference(fact_index))
    if missing_evidence or missing_facts:
        raise DellReferenceVerticalGraphError(
            "citation_reference_unresolved:"
            f"evidence={','.join(missing_evidence)};facts={','.join(missing_facts)}"
        )
    body: PlainDict = {
        "schema_version": "fin_ia_dell_reference_vertical_citation_index_v1_0",
        "evidence": [
            {
                **evidence_index[evidence_id],
                "used_by_branch_ids": sorted(evidence_branches[evidence_id]),
            }
            for evidence_id in sorted(evidence_index)
        ],
        "facts": [
            {
                **fact_index[fact_id],
                "used_by_branch_ids": sorted(fact_branches[fact_id]),
            }
            for fact_id in sorted(fact_index)
        ],
        "evidence_count": len(evidence_index),
        "fact_count": len(fact_index),
        "unresolved_reference_ids": [],
        "retrieval_candidates_promoted": False,
    }
    return {**body, "citation_index_digest": canonical_sha256(body)}


def _verification_errors(state: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if state.get("graph_contract_version") != GRAPH_CONTRACT_VERSION:
        errors.append("graph_contract_version_changed")
    binding = _validate_model(
        CaseFoundationBinding,
        state.get("foundation_binding"),
        label="foundation_binding",
    )
    if canonical_sha256(binding) != state.get("foundation_binding_digest"):
        errors.append("foundation_binding_digest_changed")
    for field in ("case_id", "research_as_of", "snapshot_id", "foundation_digest"):
        if state.get(field) != getattr(binding, field):
            errors.append(f"{field}_binding_changed")

    tasks = _task_by_branch(state)
    if not tasks:
        errors.append("branch_tasks_missing")
    if not set(binding.required_branch_ids).issubset(tasks):
        errors.append("required_branch_missing")
    if any(row.plan_digest != state.get("plan_digest") for row in tasks.values()):
        errors.append("branch_task_plan_digest_changed")

    effective_raw = state.get("effective_workpapers_by_branch")
    if not isinstance(effective_raw, Mapping):
        errors.append("effective_workpapers_missing")
        effective: dict[str, BranchWorkpaper] = {}
    else:
        effective = {
            str(branch_id): _validate_model(
                BranchWorkpaper,
                value,
                label="effective_workpaper",
            )
            for branch_id, value in effective_raw.items()
        }
    if set(effective) != set(tasks):
        errors.append("effective_workpaper_set_mismatch")
    if not set(binding.required_branch_ids).issubset(effective):
        errors.append("required_workpaper_missing")
    if not 0 <= int(state.get("reroute_count", -1)) <= 1:
        errors.append("reroute_count_invalid")

    initial_results: dict[tuple[str, str], ToolLaneResult] = {}
    for lane, key in (
        ("evidence", "initial_evidence_results"),
        ("finance", "initial_finance_results"),
    ):
        for value in state.get(key, []):
            result = _validate_model(ToolLaneResult, value, label=key)
            initial_results[(result.branch_id, lane)] = result
    for branch_id in binding.required_branch_ids:
        workpaper = effective.get(branch_id)
        if workpaper is None:
            continue
        lane_results: dict[str, ToolLaneResult] = {}
        if workpaper.revision == 1:
            for lane, key in (
                ("evidence", "rework_evidence_result"),
                ("finance", "rework_finance_result"),
            ):
                value = state.get(key)
                if isinstance(value, Mapping):
                    result = _validate_model(ToolLaneResult, value, label=key)
                    if result.branch_id == branch_id and result.revision == 1:
                        lane_results[lane] = result
        else:
            lane_results = {
                lane: result
                for (result_branch, lane), result in initial_results.items()
                if result_branch == branch_id
            }
        missing_lanes = {"evidence", "finance"}.difference(lane_results)
        if missing_lanes:
            errors.append(
                f"required_effective_tool_result_missing:{branch_id}:"
                f"{','.join(sorted(missing_lanes))}"
            )
            continue
        failed_lanes = sorted(
            lane for lane, result in lane_results.items()
            if result.status == "tool_failure"
        )
        if failed_lanes:
            errors.append(
                f"required_tool_failure:{branch_id}:{','.join(failed_lanes)}"
            )
        elif workpaper.terminal_state == "incomplete_tool_failure":
            errors.append(f"stale_incomplete_workpaper:{branch_id}")

    lead_value = state.get("lead_output")
    if not isinstance(lead_value, Mapping):
        errors.append("lead_output_missing")
        return errors
    lead = _validate_model(LeadOutput, lead_value, label="lead_output")
    if lead.plan_digest != state.get("plan_digest"):
        errors.append("lead_plan_digest_changed")
    if lead.snapshot_id != state.get("snapshot_id"):
        errors.append("lead_snapshot_changed")
    if lead.foundation_digest != state.get("foundation_digest"):
        errors.append("lead_foundation_changed")
    conclusion_ids = {row.branch_id for row in lead.branch_conclusions}
    if conclusion_ids != set(tasks):
        errors.append("lead_branch_conclusion_set_mismatch")
    for conclusion in lead.branch_conclusions:
        workpaper = effective.get(conclusion.branch_id)
        if workpaper is None:
            continue
        if not set(conclusion.evidence_ids).issubset(workpaper.evidence_ids):
            errors.append(f"lead_unknown_evidence:{conclusion.branch_id}")
        if not set(conclusion.fact_ids).issubset(workpaper.fact_ids):
            errors.append(f"lead_unknown_fact:{conclusion.branch_id}")
    return errors


def _runtime_summary(state: Mapping[str, Any]) -> PlainDict:
    receipts: list[RuntimeReceipt] = []
    tool_results: list[ToolLaneResult] = []
    planner = _validate_model(
        PlannerOutput, state.get("planner_output"), label="planner_output"
    )
    receipts.append(planner.runtime_receipt)
    for key in ("initial_evidence_results", "initial_finance_results"):
        for value in state.get(key, []):
            result = _validate_model(ToolLaneResult, value, label=key)
            tool_results.append(result)
            receipts.append(result.runtime_receipt)
    for value in state.get("initial_workpapers", []):
        receipts.append(
            _validate_model(
                BranchWorkpaper, value, label="initial_workpaper"
            ).runtime_receipt
        )
    for key in ("rework_evidence_result", "rework_finance_result"):
        value = state.get(key)
        if isinstance(value, Mapping):
            result = _validate_model(ToolLaneResult, value, label=key)
            tool_results.append(result)
            receipts.append(result.runtime_receipt)
    if isinstance(state.get("rework_workpaper"), Mapping):
        receipts.append(
            _validate_model(
                BranchWorkpaper,
                state["rework_workpaper"],
                label="rework_workpaper",
            ).runtime_receipt
        )
    receipts.append(
        _validate_model(
            CounterDecision,
            state.get("counter_decision"),
            label="counter_decision",
        ).runtime_receipt
    )
    receipts.append(
        _validate_model(
            LeadOutput, state.get("lead_output"), label="lead_output"
        ).runtime_receipt
    )
    mcp_receipts: dict[str, PlainDict] = {}
    for result in tool_results:
        for item in result.items:
            candidates: list[Any] = []
            chain = item.get("mcp_receipt_chain")
            if isinstance(chain, Sequence) and not isinstance(chain, (str, bytes)):
                candidates.extend(chain)
            single = item.get("mcp_receipt")
            if isinstance(single, Mapping):
                candidates.append(single)
            for candidate in candidates:
                if not isinstance(candidate, Mapping):
                    continue
                projection = _plain_mapping(candidate, label="mcp_call_receipt")
                receipt_identity = str(projection.get("call_id") or "")
                if not receipt_identity:
                    receipt_identity = canonical_sha256(projection)
                prior = mcp_receipts.get(receipt_identity)
                if prior is not None and prior != projection:
                    raise DellReferenceVerticalGraphError(
                        "mcp_call_receipt_identity_conflict"
                    )
                mcp_receipts[receipt_identity] = projection
    model_receipts = [row for row in receipts if row.kind == "model"]
    tool_lane_receipts = [row for row in receipts if row.kind == "tool"]
    host_receipts = [row for row in receipts if row.kind == "host"]
    mcp_tool_counts: dict[str, int] = {}
    for receipt in mcp_receipts.values():
        name = str(receipt.get("tool_name") or "unknown")
        mcp_tool_counts[name] = mcp_tool_counts.get(name, 0) + 1
    return {
        "node_receipt_count": len(receipts),
        "model_receipt_count": len(model_receipts),
        "successful_model_call_count": sum(
            row.status == "success" for row in model_receipts
        ),
        "failed_model_call_count": sum(
            row.status == "failure" for row in model_receipts
        ),
        "model_usage_reported_count": sum(
            row.usage_reported is True for row in model_receipts
        ),
        "model_usage_missing_count": sum(
            row.usage_reported is not True for row in model_receipts
        ),
        "tool_lane_receipt_count": len(tool_lane_receipts),
        "host_receipt_count": len(host_receipts),
        "mcp_call_count": len(mcp_receipts),
        "mcp_error_call_count": sum(
            bool(row.get("is_error")) or bool(row.get("semantic_tool_failure"))
            for row in mcp_receipts.values()
        ),
        "mcp_tool_call_counts": dict(sorted(mcp_tool_counts.items())),
        "input_tokens": sum(row.input_tokens for row in receipts),
        "output_tokens": sum(row.output_tokens for row in receipts),
        "total_tokens": sum(row.total_tokens for row in receipts),
        "node_receipt_elapsed_ms_sum_not_wall_clock": round(
            sum(row.elapsed_ms for row in receipts), 3
        ),
        "mcp_call_elapsed_ms_sum_not_wall_clock": round(
            sum(float(row.get("elapsed_ms") or 0) for row in mcp_receipts.values()),
            3,
        ),
        "failed_node_receipt_count": sum(
            row.status == "failure" for row in receipts
        ),
    }


def build_dell_reference_vertical_graph(
    *,
    dependencies: DellReferenceVerticalDependencies,
    checkpointer: Any,
) -> DellReferenceVerticalCompiledGraph:
    """Build the bounded dynamic DELL graph around injected dependencies."""

    if checkpointer is None:
        raise DellReferenceVerticalGraphError(
            "checkpointer_required_for_interrupt_resume"
        )
    planner_tool_capabilities = _validate_model(
        PlannerToolCapabilityProjection,
        dependencies.planner_tool_capabilities,
        label="planner_tool_capabilities",
    )

    def bind_case(state: DellReferenceVerticalState) -> DellReferenceVerticalState:
        run_id = _require_text(state.get("run_id"), label="run_id", maximum=180)
        case_id = _require_text(state.get("case_id"), label="case_id", maximum=80)
        question = _require_text(
            state.get("research_question"),
            label="research_question",
            maximum=2_000,
        )
        research_as_of = _require_text(
            state.get("research_as_of"), label="research_as_of", maximum=80
        )
        snapshot_id = _require_text(
            state.get("snapshot_id"), label="snapshot_id", maximum=240
        )
        foundation_digest = _require_text(
            state.get("foundation_digest"), label="foundation_digest", maximum=64
        )
        if len(foundation_digest) != 64 or any(
            char not in "0123456789abcdef" for char in foundation_digest
        ):
            raise DellReferenceVerticalGraphError("foundation_digest_invalid")
        request = {
            "graph_contract_version": GRAPH_CONTRACT_VERSION,
            "run_id": run_id,
            "case_id": case_id,
            "research_question": question,
            "research_as_of": research_as_of,
            "snapshot_id": snapshot_id,
            "foundation_digest": foundation_digest,
        }
        raw = dependencies.foundation_binder(request)
        binding = _validate_model(
            CaseFoundationBinding, raw, label="foundation_binding"
        )
        for field, expected in (
            ("case_id", case_id),
            ("research_as_of", research_as_of),
            ("snapshot_id", snapshot_id),
            ("foundation_digest", foundation_digest),
        ):
            if getattr(binding, field) != expected:
                raise DellReferenceVerticalGraphError(
                    f"foundation_binding_{field}_mismatch"
                )
        return {
            "graph_contract_version": GRAPH_CONTRACT_VERSION,
            "foundation_binding": binding.model_dump(mode="json"),
            "foundation_binding_digest": canonical_sha256(binding),
            "initial_evidence_results": [],
            "initial_finance_results": [],
            "initial_workpapers": [],
            "reroute_count": 0,
            "rework_task": None,
            "rework_evidence_result": None,
            "rework_finance_result": None,
            "rework_branch_input": None,
            "rework_workpaper": None,
            "lead_output": None,
            "verification": None,
            "runtime_summary": None,
            "citation_index": None,
            "human_review": None,
            "final_report": None,
            "phase": "foundation_bound",
        }

    def plan(state: DellReferenceVerticalState) -> DellReferenceVerticalState:
        binding = _validate_model(
            CaseFoundationBinding,
            state.get("foundation_binding"),
            label="foundation_binding",
        )
        actor = _agent_id(run_id=state["run_id"], role="planner")
        request = {
            "agent_id": actor,
            "graph_contract_version": GRAPH_CONTRACT_VERSION,
            "run_id": state["run_id"],
            "case_id": state["case_id"],
            "research_question": state["research_question"],
            "research_as_of": state["research_as_of"],
            "snapshot_id": state["snapshot_id"],
            "foundation_digest": state["foundation_digest"],
            "branch_catalog": [
                row.model_dump(mode="json") for row in binding.branch_methods
            ],
            "required_branch_ids": list(binding.required_branch_ids),
            "planner_tool_capabilities": planner_tool_capabilities.model_dump(
                mode="json"
            ),
            "planner_tool_capabilities_digest": (
                planner_tool_capabilities.projection_digest
            ),
        }
        raw = dependencies.planner_agent(request)
        output = _validate_model(PlannerOutput, raw, label="planner_output")
        _validate_receipt(
            output.runtime_receipt,
            kind="model",
            actor=actor,
            request=request,
            output=_model_output_body(output),
        )
        return {
            "planner_output": output.model_dump(mode="json"),
            "phase": "plan_proposed",
        }

    def validate_plan(state: DellReferenceVerticalState) -> DellReferenceVerticalState:
        binding = _validate_model(
            CaseFoundationBinding,
            state.get("foundation_binding"),
            label="foundation_binding",
        )
        output = _validate_model(
            PlannerOutput, state.get("planner_output"), label="planner_output"
        )
        methods = _method_by_branch(binding)
        drafts = {row.branch_id: row for row in output.tasks}
        unknown = set(drafts).difference(methods)
        if unknown:
            raise DellReferenceVerticalGraphError("planner_selected_unknown_branch")
        if not set(binding.required_branch_ids).issubset(drafts):
            raise DellReferenceVerticalGraphError("planner_required_branch_missing")

        ordered_drafts = [
            drafts[row.branch_id]
            for row in binding.branch_methods
            if row.branch_id in drafts
        ]
        validated_evidence_requests: dict[str, tuple[dict[str, Any], ...]] = {}
        total_live_pages = 0
        for row in ordered_drafts:
            requests = _evidence_requests(
                row.evidence_requests,
                label=f"planner_{row.branch_id}",
            )
            _validate_agent_step_budget(
                requests,
                binding=binding,
                label=f"planner_{row.branch_id}",
            )
            validated_evidence_requests[row.branch_id] = tuple(
                request.model_dump(mode="json") for request in requests
            )
            total_live_pages += _external_budget(requests)[1]
        if total_live_pages > binding.scope_ceiling.maximum_live_pages_per_run:
            raise DellReferenceVerticalGraphError(
                "planner_run_live_page_limit_exceeded"
            )
        plan_preimage = {
            "graph_contract_version": GRAPH_CONTRACT_VERSION,
            "run_id": state["run_id"],
            "case_id": state["case_id"],
            "research_question": state["research_question"],
            "research_as_of": state["research_as_of"],
            "snapshot_id": state["snapshot_id"],
            "foundation_digest": state["foundation_digest"],
            "tasks": [
                {
                    **row.model_dump(mode="json"),
                    "evidence_requests": validated_evidence_requests[row.branch_id],
                    "priority": methods[row.branch_id].priority,
                    "method_digest": methods[row.branch_id].method_digest,
                }
                for row in ordered_drafts
            ],
        }
        plan_digest = canonical_sha256(plan_preimage)
        tasks = [
            BoundBranchTask(
                task_id=_task_id(
                    run_id=state["run_id"],
                    branch_id=row.branch_id,
                    revision=0,
                    plan_digest=plan_digest,
                ),
                case_id=state["case_id"],
                branch_id=row.branch_id,
                revision=0,
                priority=methods[row.branch_id].priority,
                objective=row.objective,
                evidence_requests=validated_evidence_requests[row.branch_id],
                fact_requests=row.fact_requests,
                research_as_of=state["research_as_of"],
                snapshot_id=state["snapshot_id"],
                foundation_digest=state["foundation_digest"],
                method_digest=methods[row.branch_id].method_digest,
                plan_digest=plan_digest,
            )
            for row in ordered_drafts
        ]
        return {
            "plan_digest": plan_digest,
            "branch_tasks": [row.model_dump(mode="json") for row in tasks],
            "phase": "plan_bound",
        }

    def dispatch_initial_tools(
        state: DellReferenceVerticalState,
    ) -> list[Send]:
        tasks = [
            _validate_model(BoundBranchTask, row, label="bound_branch_task")
            for row in state.get("branch_tasks", [])
        ]
        if not tasks:
            raise DellReferenceVerticalGraphError("branch_tasks_missing")
        sends: list[Send] = []
        for task in tasks:
            sends.append(
                Send(
                    "initial_evidence_lane",
                    ToolLaneTask(lane="evidence", task=task).model_dump(mode="json"),
                )
            )
            sends.append(
                Send(
                    "initial_finance_lane",
                    ToolLaneTask(lane="finance", task=task).model_dump(mode="json"),
                )
            )
        return sends

    def initial_evidence_lane(value: Mapping[str, Any]) -> DellReferenceVerticalState:
        result = _execute_tool(value, executor=dependencies.evidence_tool)
        return {"initial_evidence_results": [result.model_dump(mode="json")]}

    def initial_finance_lane(value: Mapping[str, Any]) -> DellReferenceVerticalState:
        result = _execute_tool(value, executor=dependencies.finance_tool)
        return {"initial_finance_results": [result.model_dump(mode="json")]}

    def join_initial_tools(
        state: DellReferenceVerticalState,
    ) -> DellReferenceVerticalState:
        tasks = _task_by_branch(state)
        joined_results = _join_initial_lane_results(
            tasks=tasks,
            evidence_values=state.get("initial_evidence_results", []),
            finance_values=state.get("initial_finance_results", []),
        )
        binding = _validate_model(
            CaseFoundationBinding,
            state.get("foundation_binding"),
            label="foundation_binding",
        )
        methods = _method_by_branch(binding)
        branch_inputs: dict[str, PlainDict] = {}
        for branch_id, task in sorted(tasks.items()):
            evidence_result, finance_result = joined_results[branch_id]
            agent_input = _branch_context(
                run_id=state["run_id"],
                task=task,
                method=methods[branch_id],
                evidence=evidence_result,
                finance=finance_result,
                turn_index=1,
            )
            branch_inputs[branch_id] = agent_input.model_dump(mode="json")
        return {
            "initial_branch_inputs": branch_inputs,
            "phase": "initial_tools_joined",
        }

    def dispatch_specialists(
        state: DellReferenceVerticalState,
    ) -> list[Send]:
        values = state.get("initial_branch_inputs")
        if not isinstance(values, Mapping) or not values:
            raise DellReferenceVerticalGraphError("initial_branch_inputs_missing")
        return [
            Send("specialist_agent", _plain_mapping(values[branch_id], label="branch_input"))
            for branch_id in sorted(values)
        ]

    def specialist_agent(value: Mapping[str, Any]) -> DellReferenceVerticalState:
        workpaper = _run_specialist(value, agent=dependencies.specialist_agent)
        return {"initial_workpapers": [workpaper.model_dump(mode="json")]}

    def join_specialists(
        state: DellReferenceVerticalState,
    ) -> DellReferenceVerticalState:
        expected = set(_task_by_branch(state))
        workpapers = _workpaper_map(
            state.get("initial_workpapers", []),
            expected_branch_ids=expected,
            revision=0,
        )
        projected = {
            key: value.model_dump(mode="json") for key, value in workpapers.items()
        }
        fatal_branches = sorted(
            branch_id
            for branch_id, workpaper in workpapers.items()
            if workpaper.terminal_state == "incomplete_tool_failure"
        )
        return {
            "initial_workpapers_by_branch": projected,
            "effective_workpapers_by_branch": projected,
            "fatal_tool_failure_branches": fatal_branches,
            "phase": (
                "fatal_tool_failure_before_synthesis"
                if fatal_branches
                else "initial_workpapers_joined"
            ),
        }

    def route_after_specialists(
        state: DellReferenceVerticalState,
    ) -> Literal["counter_agent", "end"]:
        fatal = state.get("fatal_tool_failure_branches", [])
        if fatal:
            return "end"
        return "counter_agent"

    def counter_agent(state: DellReferenceVerticalState) -> DellReferenceVerticalState:
        actor = _agent_id(run_id=state["run_id"], role="counter")
        workpapers_raw = state.get("initial_workpapers_by_branch")
        if not isinstance(workpapers_raw, Mapping):
            raise DellReferenceVerticalGraphError("initial_workpapers_missing")
        request_base = {
            "agent_id": actor,
            "run_id": state["run_id"],
            "case_id": state["case_id"],
            "research_question": state["research_question"],
            "research_as_of": state["research_as_of"],
            "snapshot_id": state["snapshot_id"],
            "foundation_digest": state["foundation_digest"],
            "plan_digest": state["plan_digest"],
            "workpapers": [
                workpapers_raw[key] for key in sorted(workpapers_raw)
            ],
        }
        request = {
            **request_base,
            "context_digest": canonical_sha256(request_base),
        }
        raw = dependencies.counter_agent(request)
        decision = _validate_model(CounterDecision, raw, label="counter_decision")
        expected = {
            "agent_id": actor,
            "context_digest": request["context_digest"],
            "snapshot_id": state["snapshot_id"],
            "foundation_digest": state["foundation_digest"],
            "plan_digest": state["plan_digest"],
        }
        if {key: getattr(decision, key) for key in expected} != expected:
            raise DellReferenceVerticalGraphError("counter_decision_binding_mismatch")
        _validate_receipt(
            decision.runtime_receipt,
            kind="model",
            actor=actor,
            request=request,
            output=_model_output_body(decision),
        )

        update: DellReferenceVerticalState = {
            "counter_decision": decision.model_dump(mode="json"),
            "phase": "counter_completed",
        }
        if decision.reroute is None:
            return update
        if int(state.get("reroute_count", 0)) != 0:
            raise DellReferenceVerticalGraphError("counter_reroute_limit_exceeded")
        tasks = _task_by_branch(state)
        target = tasks.get(decision.reroute.target_branch_id)
        if target is None:
            raise DellReferenceVerticalGraphError("counter_reroute_branch_unknown")
        binding = _validate_model(
            CaseFoundationBinding,
            state.get("foundation_binding"),
            label="foundation_binding",
        )
        reroute_requests = _evidence_requests(
            decision.reroute.evidence_requests,
            label=f"counter_{target.branch_id}",
        )
        _validate_agent_step_budget(
            reroute_requests,
            binding=binding,
            label=f"counter_{target.branch_id}",
        )
        initial_target_requests = _evidence_requests(
            target.evidence_requests,
            label=f"initial_{target.branch_id}",
        )
        _validate_cumulative_branch_external_budget(
            (*initial_target_requests, *reroute_requests),
            binding=binding,
            label=f"counter_{target.branch_id}",
        )
        total_live_pages = sum(
            _external_budget(
                _evidence_requests(
                    task.evidence_requests,
                    label=f"initial_{task.branch_id}",
                )
            )[1]
            for task in tasks.values()
        )
        total_live_pages += _external_budget(reroute_requests)[1]
        if total_live_pages > binding.scope_ceiling.maximum_live_pages_per_run:
            raise DellReferenceVerticalGraphError(
                "counter_run_live_page_limit_exceeded"
            )
        rework = BoundBranchTask(
            task_id=_task_id(
                run_id=state["run_id"],
                branch_id=target.branch_id,
                revision=1,
                plan_digest=target.plan_digest,
            ),
            case_id=target.case_id,
            branch_id=target.branch_id,
            revision=1,
            priority=target.priority,
            objective=target.objective,
            evidence_requests=tuple(
                request.model_dump(mode="json") for request in reroute_requests
            ),
            fact_requests=decision.reroute.fact_requests,
            research_as_of=target.research_as_of,
            snapshot_id=target.snapshot_id,
            foundation_digest=target.foundation_digest,
            method_digest=target.method_digest,
            plan_digest=target.plan_digest,
        )
        update.update(
            {
                "reroute_count": 1,
                "rework_task": rework.model_dump(mode="json"),
                "phase": "counter_reroute_bound",
            }
        )
        return update

    def route_after_counter(
        state: DellReferenceVerticalState,
    ) -> str | list[Send]:
        value = state.get("rework_task")
        if not isinstance(value, Mapping):
            return "lead_agent"
        task = _validate_model(BoundBranchTask, value, label="rework_task")
        return [
            Send(
                "rework_evidence_lane",
                ToolLaneTask(lane="evidence", task=task).model_dump(mode="json"),
            ),
            Send(
                "rework_finance_lane",
                ToolLaneTask(lane="finance", task=task).model_dump(mode="json"),
            ),
        ]

    def rework_evidence_lane(value: Mapping[str, Any]) -> DellReferenceVerticalState:
        result = _execute_tool(value, executor=dependencies.evidence_tool)
        return {"rework_evidence_result": result.model_dump(mode="json")}

    def rework_finance_lane(value: Mapping[str, Any]) -> DellReferenceVerticalState:
        result = _execute_tool(value, executor=dependencies.finance_tool)
        return {"rework_finance_result": result.model_dump(mode="json")}

    def join_rework_tools(
        state: DellReferenceVerticalState,
    ) -> DellReferenceVerticalState:
        task = _validate_model(
            BoundBranchTask, state.get("rework_task"), label="rework_task"
        )
        evidence = _validate_model(
            ToolLaneResult,
            state.get("rework_evidence_result"),
            label="rework_evidence_result",
        )
        finance = _validate_model(
            ToolLaneResult,
            state.get("rework_finance_result"),
            label="rework_finance_result",
        )
        _validate_tool_result(
            evidence, lane_task=ToolLaneTask(lane="evidence", task=task)
        )
        _validate_tool_result(
            finance, lane_task=ToolLaneTask(lane="finance", task=task)
        )
        binding = _validate_model(
            CaseFoundationBinding,
            state.get("foundation_binding"),
            label="foundation_binding",
        )
        prior_raw = state.get("initial_workpapers_by_branch")
        if not isinstance(prior_raw, Mapping) or task.branch_id not in prior_raw:
            raise DellReferenceVerticalGraphError("rework_prior_workpaper_missing")
        prior = _validate_model(
            BranchWorkpaper,
            prior_raw[task.branch_id],
            label="rework_prior_workpaper",
        )
        decision = _validate_model(
            CounterDecision,
            state.get("counter_decision"),
            label="counter_decision",
        )
        if decision.reroute is None:
            raise DellReferenceVerticalGraphError("rework_counter_reroute_missing")
        agent_input = _branch_context(
            run_id=state["run_id"],
            task=task,
            method=_method_by_branch(binding)[task.branch_id],
            evidence=evidence,
            finance=finance,
            turn_index=2,
            prior_workpaper=prior,
            counter_challenge=decision.reroute.model_dump(mode="json"),
        )
        return {
            "rework_branch_input": agent_input.model_dump(mode="json"),
            "phase": "rework_tools_joined",
        }

    def specialist_rework(state: DellReferenceVerticalState) -> DellReferenceVerticalState:
        value = state.get("rework_branch_input")
        if not isinstance(value, Mapping):
            raise DellReferenceVerticalGraphError("rework_branch_input_missing")
        workpaper = _run_specialist(value, agent=dependencies.specialist_agent)
        return {
            "rework_workpaper": workpaper.model_dump(mode="json"),
            "phase": "specialist_rework_completed",
        }

    def merge_rework(state: DellReferenceVerticalState) -> DellReferenceVerticalState:
        task = _validate_model(
            BoundBranchTask, state.get("rework_task"), label="rework_task"
        )
        workpaper = _validate_model(
            BranchWorkpaper,
            state.get("rework_workpaper"),
            label="rework_workpaper",
        )
        if workpaper.branch_id != task.branch_id or workpaper.revision != 1:
            raise DellReferenceVerticalGraphError("rework_workpaper_binding_mismatch")
        initial = state.get("initial_workpapers_by_branch")
        if not isinstance(initial, Mapping):
            raise DellReferenceVerticalGraphError("initial_workpapers_missing")
        effective = {
            str(key): _plain_mapping(value, label="initial_workpaper")
            for key, value in initial.items()
        }
        effective[task.branch_id] = workpaper.model_dump(mode="json")
        return {
            "effective_workpapers_by_branch": dict(sorted(effective.items())),
            "phase": "rework_merged",
        }

    def lead_agent(state: DellReferenceVerticalState) -> DellReferenceVerticalState:
        effective_raw = state.get("effective_workpapers_by_branch")
        if not isinstance(effective_raw, Mapping) or not effective_raw:
            raise DellReferenceVerticalGraphError("effective_workpapers_missing")
        actor = _agent_id(run_id=state["run_id"], role="lead")
        request_base = {
            "agent_id": actor,
            "run_id": state["run_id"],
            "case_id": state["case_id"],
            "research_question": state["research_question"],
            "research_as_of": state["research_as_of"],
            "snapshot_id": state["snapshot_id"],
            "foundation_digest": state["foundation_digest"],
            "plan_digest": state["plan_digest"],
            "workpapers": [effective_raw[key] for key in sorted(effective_raw)],
            "counter_decision": state["counter_decision"],
        }
        request = {**request_base, "context_digest": canonical_sha256(request_base)}
        raw = dependencies.lead_agent(request)
        output = _validate_model(LeadOutput, raw, label="lead_output")
        expected = {
            "agent_id": actor,
            "context_digest": request["context_digest"],
            "snapshot_id": state["snapshot_id"],
            "foundation_digest": state["foundation_digest"],
            "plan_digest": state["plan_digest"],
        }
        if {key: getattr(output, key) for key in expected} != expected:
            raise DellReferenceVerticalGraphError("lead_output_binding_mismatch")
        _validate_receipt(
            output.runtime_receipt,
            kind="model",
            actor=actor,
            request=request,
            output=_model_output_body(output),
        )
        workpapers = {
            str(branch_id): _validate_model(
                BranchWorkpaper, value, label="effective_workpaper"
            )
            for branch_id, value in effective_raw.items()
        }
        if {row.branch_id for row in output.branch_conclusions} != set(workpapers):
            raise DellReferenceVerticalGraphError(
                "lead_branch_conclusion_set_mismatch"
            )
        for conclusion in output.branch_conclusions:
            source = workpapers[conclusion.branch_id]
            if not set(conclusion.evidence_ids).issubset(source.evidence_ids):
                raise DellReferenceVerticalGraphError("lead_unknown_evidence_id")
            if not set(conclusion.fact_ids).issubset(source.fact_ids):
                raise DellReferenceVerticalGraphError("lead_unknown_fact_id")
        return {
            "lead_output": output.model_dump(mode="json"),
            "phase": "lead_completed",
        }

    def verify(state: DellReferenceVerticalState) -> DellReferenceVerticalState:
        errors = _verification_errors(state)
        citation_index = _citation_index(state) if not errors else None
        result = VerificationResult(passed=not errors, errors=tuple(errors))
        return {
            "verification": result.model_dump(mode="json"),
            "runtime_summary": _runtime_summary(state),
            "citation_index": citation_index,
            "phase": "awaiting_review" if not errors else "verification_failed",
        }

    def route_after_verify(
        state: DellReferenceVerticalState,
    ) -> Literal["human_review", "end"]:
        return "human_review" if state.get("phase") == "awaiting_review" else "end"

    def human_review(state: DellReferenceVerticalState) -> DellReferenceVerticalState:
        raw = interrupt(
            {
                "kind": "dell_reference_vertical_review",
                "graph_contract_version": GRAPH_CONTRACT_VERSION,
                "run_id": state["run_id"],
                "case_id": state["case_id"],
                "research_as_of": state["research_as_of"],
                "snapshot_id": state["snapshot_id"],
                "plan_digest": state["plan_digest"],
                "lead_output": state["lead_output"],
                "counter_decision": state["counter_decision"],
                "effective_workpapers_by_branch": state[
                    "effective_workpapers_by_branch"
                ],
                "citation_index": state["citation_index"],
                "verification": state["verification"],
                "runtime_summary": state["runtime_summary"],
                "allowed_actions": ["approve", "reject"],
            }
        )
        decision = _validate_model(
            HumanReviewDecision, raw, label="human_review_decision"
        )
        return {
            "human_review": decision.model_dump(mode="json"),
            "phase": "approved" if decision.action == "approve" else "rejected",
        }

    def route_after_review(
        state: DellReferenceVerticalState,
    ) -> Literal["render", "end"]:
        return "render" if state.get("phase") == "approved" else "end"

    def render(state: DellReferenceVerticalState) -> DellReferenceVerticalState:
        errors = _verification_errors(state)
        if errors:
            raise DellReferenceVerticalGraphError("render_verification_failed")
        citation_index = _citation_index(state)
        if citation_index != state.get("citation_index"):
            raise DellReferenceVerticalGraphError("citation_index_changed_after_review")
        effective = state["effective_workpapers_by_branch"]
        report: PlainDict = {
            "schema_version": "fin_ia_dell_reference_vertical_report_v1_0",
            "graph_contract_version": GRAPH_CONTRACT_VERSION,
            "run_id": state["run_id"],
            "case_id": state["case_id"],
            "research_question": state["research_question"],
            "research_as_of": state["research_as_of"],
            "snapshot_id": state["snapshot_id"],
            "foundation_digest": state["foundation_digest"],
            "plan_digest": state["plan_digest"],
            "reroute_count": state.get("reroute_count", 0),
            "branch_workpapers": [effective[key] for key in sorted(effective)],
            "counter_decision": state["counter_decision"],
            "lead_output": state["lead_output"],
            "citation_index": citation_index,
            "human_review": state["human_review"],
            "runtime_summary": state.get("runtime_summary") or _runtime_summary(state),
        }
        report["report_digest"] = canonical_sha256(report)
        return {"final_report": report, "phase": "completed"}

    graph = StateGraph(DellReferenceVerticalState)
    graph.add_node("bind_case", bind_case)
    graph.add_node("plan", plan)
    graph.add_node("validate_plan", validate_plan)
    graph.add_node("initial_evidence_lane", initial_evidence_lane)
    graph.add_node("initial_finance_lane", initial_finance_lane)
    graph.add_node("join_initial_tools", join_initial_tools)
    graph.add_node("specialist_agent", specialist_agent)
    graph.add_node("join_specialists", join_specialists)
    graph.add_node("counter_agent", counter_agent)
    graph.add_node("rework_evidence_lane", rework_evidence_lane)
    graph.add_node("rework_finance_lane", rework_finance_lane)
    graph.add_node("join_rework_tools", join_rework_tools)
    graph.add_node("specialist_rework", specialist_rework)
    graph.add_node("merge_rework", merge_rework)
    graph.add_node("lead_agent", lead_agent)
    graph.add_node("verify", verify)
    graph.add_node("human_review", human_review)
    graph.add_node("render", render)

    graph.add_edge(START, "bind_case")
    graph.add_edge("bind_case", "plan")
    graph.add_edge("plan", "validate_plan")
    graph.add_conditional_edges("validate_plan", dispatch_initial_tools)
    graph.add_edge(
        ["initial_evidence_lane", "initial_finance_lane"],
        "join_initial_tools",
    )
    graph.add_conditional_edges("join_initial_tools", dispatch_specialists)
    graph.add_edge("specialist_agent", "join_specialists")
    graph.add_conditional_edges(
        "join_specialists",
        route_after_specialists,
        {"counter_agent": "counter_agent", "end": END},
    )
    graph.add_conditional_edges("counter_agent", route_after_counter)
    graph.add_edge(
        ["rework_evidence_lane", "rework_finance_lane"],
        "join_rework_tools",
    )
    graph.add_edge("join_rework_tools", "specialist_rework")
    graph.add_edge("specialist_rework", "merge_rework")
    graph.add_edge("merge_rework", "lead_agent")
    graph.add_edge("lead_agent", "verify")
    graph.add_conditional_edges(
        "verify",
        route_after_verify,
        {"human_review": "human_review", "end": END},
    )
    graph.add_conditional_edges(
        "human_review",
        route_after_review,
        {"render": "render", "end": END},
    )
    graph.add_edge("render", END)

    return DellReferenceVerticalCompiledGraph(
        graph.compile(
            checkpointer=checkpointer,
            name="dell_reference_vertical_graph",
        )
    )


__all__ = [
    "DellReferenceVerticalCompiledGraph",
    "DellReferenceVerticalDependencies",
    "DellReferenceVerticalGraphError",
    "GRAPH_CONTRACT_VERSION",
    "build_dell_reference_vertical_graph",
]
