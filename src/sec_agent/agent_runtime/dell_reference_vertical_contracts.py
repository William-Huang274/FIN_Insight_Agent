"""Strict contracts for the bounded DELL reference-vertical LangGraph.

The contracts in this module are intentionally provider-, storage-, and UI-neutral.
Every value written to graph state is plain JSON so a durable LangGraph
checkpointer can replay it without importing model, MCP, or database clients.
"""

from __future__ import annotations

import json
import operator
from hashlib import sha256
from typing import Annotated, Any, Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field, model_validator


Digest = str
ToolLane = Literal["evidence", "finance"]
ToolExecutionStatus = Literal["success", "not_applicable", "tool_failure"]
EvidenceSourceRoute = Literal["reviewed_first", "local_only", "external_required"]
ToolResultState = Literal[
    "retrieval_candidate",
    "captured_source_candidate",
    "reviewed_evidence",
    "numeric_fact",
    "deterministic_derived_metric",
    "research_scenario",
    "typed_gap",
    "typed_conflict",
    "not_applicable",
    "tool_failure",
]
BranchTerminalState = Literal[
    "supported",
    "countered",
    "bounded_gap",
    "not_material",
    "incomplete_tool_failure",
]


class _StrictFrozenModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        str_strip_whitespace=True,
    )


class RuntimeReceipt(_StrictFrozenModel):
    """Secret-free execution receipt for one tool or model actor."""

    receipt_id: str = Field(min_length=1, max_length=240)
    kind: Literal["tool", "model", "host"]
    actor: str = Field(min_length=1, max_length=240)
    status: Literal["success", "failure"]
    request_digest: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    output_digest: Digest | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    elapsed_ms: float = Field(ge=0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    usage_reported: bool | None = None
    transport_attempts: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def validate_token_total(self) -> "RuntimeReceipt":
        if self.total_tokens < self.input_tokens + self.output_tokens:
            raise ValueError("runtime_receipt_total_tokens_invalid")
        if self.status == "success" and self.output_digest is None:
            raise ValueError("runtime_receipt_success_output_digest_required")
        if self.kind != "model" and self.usage_reported is True:
            raise ValueError("non_model_receipt_usage_reported_invalid")
        return self


class ToolFailure(_StrictFrozenModel):
    code: str = Field(min_length=1, max_length=240)
    owner_layer: Literal[
        "tool_transport",
        "s1_tool",
        "s2_tool",
        "runtime",
    ]
    retryable: bool
    exception_type: str | None = Field(default=None, max_length=160)


class EvidenceRequest(_StrictFrozenModel):
    """Canonical planner-to-tool request for the bounded DELL evidence lane."""

    # MCP and model transports are JSON, so tuple fields arrive as JSON arrays.
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=False,
        str_strip_whitespace=True,
    )

    query: str = Field(min_length=1, max_length=2_000)
    purpose: str = Field(min_length=1, max_length=1_000)
    include_domains: tuple[str, ...] = Field(default=(), max_length=12)
    limit: int = Field(default=6, ge=1, le=6)
    source_route: EvidenceSourceRoute
    capture_limit: int = Field(default=2, ge=1, le=3)


class AgentRuntimeScopeCeiling(_StrictFrozenModel):
    """Foundation-owned limits that the graph must enforce before tool dispatch."""

    maximum_external_search_rounds_per_high_materiality_branch: int = Field(
        ge=1, le=8
    )
    maximum_results_per_search: int = Field(ge=1, le=32)
    maximum_captured_pages_per_branch: int = Field(ge=1, le=32)
    maximum_live_pages_per_run: int = Field(ge=1, le=256)
    maximum_sources_visible_per_agent_step: int = Field(ge=1, le=64)
    maximum_targeted_counter_reroutes: Literal[1]

    @model_validator(mode="after")
    def validate_aggregate_bounds(self) -> "AgentRuntimeScopeCeiling":
        if self.maximum_captured_pages_per_branch > self.maximum_live_pages_per_run:
            raise ValueError("branch_capture_ceiling_exceeds_run_ceiling")
        return self


class BranchMethodBinding(_StrictFrozenModel):
    branch_id: str = Field(min_length=1, max_length=120)
    priority: Literal["high", "medium", "low"]
    objective: str = Field(min_length=1, max_length=2_000)
    method_digest: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    method_context: dict[str, Any]

    @model_validator(mode="after")
    def validate_method_digest(self) -> "BranchMethodBinding":
        if canonical_sha256(self.method_context) != self.method_digest:
            raise ValueError("branch_method_digest_mismatch")
        return self


class CaseFoundationBinding(_StrictFrozenModel):
    case_id: str = Field(min_length=1, max_length=80)
    research_as_of: str = Field(min_length=1, max_length=80)
    snapshot_id: str = Field(min_length=1, max_length=240)
    foundation_digest: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    scope_ceiling: AgentRuntimeScopeCeiling
    branch_methods: tuple[BranchMethodBinding, ...] = Field(min_length=1)
    required_branch_ids: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_branch_catalog(self) -> "CaseFoundationBinding":
        branch_ids = tuple(row.branch_id for row in self.branch_methods)
        if len(branch_ids) != len(set(branch_ids)):
            raise ValueError("foundation_branch_id_duplicate")
        if len(self.required_branch_ids) != len(set(self.required_branch_ids)):
            raise ValueError("foundation_required_branch_id_duplicate")
        if not set(self.required_branch_ids).issubset(branch_ids):
            raise ValueError("foundation_required_branch_unknown")
        return self


class BranchTaskDraft(_StrictFrozenModel):
    branch_id: str = Field(min_length=1, max_length=120)
    objective: str = Field(min_length=1, max_length=2_000)
    evidence_requests: tuple[dict[str, Any], ...] = Field(min_length=1, max_length=8)
    fact_requests: tuple[dict[str, Any], ...] = Field(default=(), max_length=24)


class PlannerOutput(_StrictFrozenModel):
    tasks: tuple[BranchTaskDraft, ...] = Field(min_length=1, max_length=16)
    runtime_receipt: RuntimeReceipt

    @model_validator(mode="after")
    def validate_tasks(self) -> "PlannerOutput":
        branch_ids = tuple(row.branch_id for row in self.tasks)
        if len(branch_ids) != len(set(branch_ids)):
            raise ValueError("planner_branch_id_duplicate")
        if self.runtime_receipt.kind != "model":
            raise ValueError("planner_runtime_receipt_kind_invalid")
        return self


class BoundBranchTask(_StrictFrozenModel):
    task_id: str = Field(min_length=1, max_length=240)
    case_id: str = Field(min_length=1, max_length=80)
    branch_id: str = Field(min_length=1, max_length=120)
    revision: Literal[0, 1]
    priority: Literal["high", "medium", "low"]
    objective: str = Field(min_length=1, max_length=2_000)
    evidence_requests: tuple[dict[str, Any], ...] = Field(min_length=1, max_length=8)
    fact_requests: tuple[dict[str, Any], ...] = Field(default=(), max_length=24)
    research_as_of: str = Field(min_length=1, max_length=80)
    snapshot_id: str = Field(min_length=1, max_length=240)
    foundation_digest: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    method_digest: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    plan_digest: Digest = Field(pattern=r"^[0-9a-f]{64}$")


class ToolLaneTask(_StrictFrozenModel):
    lane: ToolLane
    task: BoundBranchTask


class ToolLaneResult(_StrictFrozenModel):
    lane: ToolLane
    task_id: str = Field(min_length=1, max_length=240)
    case_id: str = Field(min_length=1, max_length=80)
    branch_id: str = Field(min_length=1, max_length=120)
    revision: Literal[0, 1]
    research_as_of: str = Field(min_length=1, max_length=80)
    snapshot_id: str = Field(min_length=1, max_length=240)
    foundation_digest: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    method_digest: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    plan_digest: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    status: ToolExecutionStatus
    result_states: tuple[ToolResultState, ...] = Field(min_length=1)
    items: tuple[dict[str, Any], ...] = ()
    failure: ToolFailure | None = None
    runtime_receipt: RuntimeReceipt

    @model_validator(mode="after")
    def validate_status_and_lane(self) -> "ToolLaneResult":
        if self.runtime_receipt.kind not in {"tool", "host"}:
            raise ValueError("tool_lane_runtime_receipt_kind_invalid")
        if self.status == "tool_failure":
            if self.failure is None or self.result_states != ("tool_failure",):
                raise ValueError("tool_lane_failure_envelope_invalid")
            if self.runtime_receipt.status != "failure":
                raise ValueError("tool_lane_failure_receipt_status_invalid")
        else:
            if self.failure is not None:
                raise ValueError("tool_lane_nonfailure_has_failure")
            if self.runtime_receipt.status != "success":
                raise ValueError("tool_lane_success_receipt_status_invalid")
        if self.status == "not_applicable":
            if self.result_states != ("not_applicable",) or self.items:
                raise ValueError("tool_lane_not_applicable_invalid")

        evidence_states = {
            "retrieval_candidate",
            "captured_source_candidate",
            "reviewed_evidence",
            "typed_gap",
            "tool_failure",
            "not_applicable",
        }
        finance_states = {
            "numeric_fact",
            "deterministic_derived_metric",
            "research_scenario",
            "typed_gap",
            "typed_conflict",
            "tool_failure",
            "not_applicable",
        }
        allowed = evidence_states if self.lane == "evidence" else finance_states
        if not set(self.result_states).issubset(allowed):
            raise ValueError("tool_lane_result_state_invalid_for_lane")
        if len(self.result_states) != len(set(self.result_states)):
            raise ValueError("tool_lane_result_state_duplicate")
        return self


class BranchAgentInput(_StrictFrozenModel):
    agent_id: str = Field(min_length=1, max_length=240)
    turn_index: Literal[1, 2]
    context_digest: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    task: BoundBranchTask
    method_context: dict[str, Any]
    evidence_result: ToolLaneResult
    finance_result: ToolLaneResult
    prior_workpaper: dict[str, Any] | None = None
    counter_challenge: dict[str, Any] | None = None


class BranchWorkpaper(_StrictFrozenModel):
    branch_id: str = Field(min_length=1, max_length=120)
    revision: Literal[0, 1]
    agent_id: str = Field(min_length=1, max_length=240)
    context_digest: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    snapshot_id: str = Field(min_length=1, max_length=240)
    foundation_digest: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    method_digest: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    plan_digest: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    terminal_state: BranchTerminalState
    thesis: str = Field(min_length=1, max_length=4_000)
    mechanism: str = Field(min_length=1, max_length=6_000)
    counterevidence: tuple[str, ...] = Field(min_length=1, max_length=8)
    what_would_change: tuple[str, ...] = Field(min_length=1, max_length=8)
    evidence_ids: tuple[str, ...] = Field(default=(), max_length=32)
    fact_ids: tuple[str, ...] = Field(default=(), max_length=48)
    open_gaps: tuple[str, ...] = Field(default=(), max_length=16)
    tool_receipt_ids: tuple[str, ...] = Field(min_length=2, max_length=4)
    runtime_receipt: RuntimeReceipt

    @model_validator(mode="after")
    def validate_workpaper(self) -> "BranchWorkpaper":
        for label, values in (
            ("evidence_ids", self.evidence_ids),
            ("fact_ids", self.fact_ids),
            ("open_gaps", self.open_gaps),
            ("tool_receipt_ids", self.tool_receipt_ids),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"branch_workpaper_{label}_duplicate")
        expected_receipt_kind = (
            "host" if self.terminal_state == "incomplete_tool_failure" else "model"
        )
        if self.runtime_receipt.kind != expected_receipt_kind:
            raise ValueError("branch_workpaper_runtime_receipt_kind_invalid")
        if self.terminal_state == "incomplete_tool_failure" and (
            self.evidence_ids or self.fact_ids
        ):
            raise ValueError("incomplete_workpaper_references_forbidden")
        if self.terminal_state in {"supported", "countered"} and not (
            self.evidence_ids or self.fact_ids
        ):
            raise ValueError("branch_workpaper_supported_reference_required")
        return self


class CounterReroute(_StrictFrozenModel):
    target_branch_id: str = Field(min_length=1, max_length=120)
    challenge_id: str = Field(min_length=1, max_length=240)
    reason: str = Field(min_length=1, max_length=2_000)
    owner_layer: Literal["agent"]
    evidence_requests: tuple[dict[str, Any], ...] = Field(min_length=1, max_length=8)
    fact_requests: tuple[dict[str, Any], ...] = Field(default=(), max_length=24)


class CounterDecision(_StrictFrozenModel):
    agent_id: str = Field(min_length=1, max_length=240)
    context_digest: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    snapshot_id: str = Field(min_length=1, max_length=240)
    foundation_digest: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    plan_digest: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    strongest_counter_thesis: str = Field(min_length=1, max_length=4_000)
    challenges: tuple[str, ...] = Field(min_length=1, max_length=12)
    what_would_change: tuple[str, ...] = Field(min_length=1, max_length=12)
    reroute: CounterReroute | None = None
    runtime_receipt: RuntimeReceipt

    @model_validator(mode="after")
    def validate_counter_receipt(self) -> "CounterDecision":
        if self.runtime_receipt.kind != "model":
            raise ValueError("counter_runtime_receipt_kind_invalid")
        return self


class LeadBranchConclusion(_StrictFrozenModel):
    branch_id: str = Field(min_length=1, max_length=120)
    conclusion: str = Field(min_length=1, max_length=3_000)
    evidence_ids: tuple[str, ...] = Field(default=(), max_length=24)
    fact_ids: tuple[str, ...] = Field(default=(), max_length=32)


class LeadOutput(_StrictFrozenModel):
    agent_id: str = Field(min_length=1, max_length=240)
    context_digest: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    snapshot_id: str = Field(min_length=1, max_length=240)
    foundation_digest: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    plan_digest: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    verdict: Literal[
        "positive",
        "mixed_positive",
        "neutral",
        "mixed_negative",
        "negative",
    ]
    confidence: int = Field(ge=0, le=100)
    headline: str = Field(min_length=1, max_length=240)
    executive_summary: str = Field(min_length=1, max_length=8_000)
    branch_conclusions: tuple[LeadBranchConclusion, ...] = Field(min_length=1)
    counter_response: str = Field(min_length=1, max_length=4_000)
    runtime_receipt: RuntimeReceipt

    @model_validator(mode="after")
    def validate_lead_output(self) -> "LeadOutput":
        branch_ids = tuple(row.branch_id for row in self.branch_conclusions)
        if len(branch_ids) != len(set(branch_ids)):
            raise ValueError("lead_branch_conclusion_duplicate")
        if self.runtime_receipt.kind != "model":
            raise ValueError("lead_runtime_receipt_kind_invalid")
        return self


class VerificationResult(_StrictFrozenModel):
    passed: bool
    errors: tuple[str, ...]

    @model_validator(mode="after")
    def validate_pass_state(self) -> "VerificationResult":
        if self.passed == bool(self.errors):
            raise ValueError("verification_pass_error_state_invalid")
        return self


class HumanReviewDecision(_StrictFrozenModel):
    action: Literal["approve", "reject"]
    reason: str = Field(default="", max_length=2_000)


class DellReferenceVerticalState(TypedDict, total=False):
    """One LangGraph thread; parallel Agent results use append reducers only."""

    graph_contract_version: str
    run_id: str
    case_id: str
    research_question: str
    research_as_of: str
    snapshot_id: str
    foundation_digest: str
    foundation_binding: dict[str, Any]
    foundation_binding_digest: str
    planner_output: dict[str, Any]
    plan_digest: str
    branch_tasks: list[dict[str, Any]]
    initial_evidence_results: Annotated[list[dict[str, Any]], operator.add]
    initial_finance_results: Annotated[list[dict[str, Any]], operator.add]
    initial_branch_inputs: dict[str, dict[str, Any]]
    initial_workpapers: Annotated[list[dict[str, Any]], operator.add]
    initial_workpapers_by_branch: dict[str, dict[str, Any]]
    fatal_tool_failure_branches: list[str]
    counter_decision: dict[str, Any]
    reroute_count: int
    rework_task: dict[str, Any] | None
    rework_evidence_result: dict[str, Any] | None
    rework_finance_result: dict[str, Any] | None
    rework_branch_input: dict[str, Any] | None
    rework_workpaper: dict[str, Any] | None
    effective_workpapers_by_branch: dict[str, dict[str, Any]]
    lead_output: dict[str, Any] | None
    verification: dict[str, Any] | None
    runtime_summary: dict[str, Any] | None
    citation_index: dict[str, Any] | None
    human_review: dict[str, Any] | None
    final_report: dict[str, Any] | None
    phase: str


def canonical_json_bytes(value: Any) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


__all__ = [
    "AgentRuntimeScopeCeiling",
    "BoundBranchTask",
    "BranchAgentInput",
    "BranchMethodBinding",
    "BranchTaskDraft",
    "BranchTerminalState",
    "BranchWorkpaper",
    "CaseFoundationBinding",
    "CounterDecision",
    "CounterReroute",
    "DellReferenceVerticalState",
    "EvidenceRequest",
    "EvidenceSourceRoute",
    "HumanReviewDecision",
    "LeadBranchConclusion",
    "LeadOutput",
    "PlannerOutput",
    "RuntimeReceipt",
    "ToolFailure",
    "ToolLaneResult",
    "ToolLaneTask",
    "VerificationResult",
    "canonical_json_bytes",
    "canonical_sha256",
]
