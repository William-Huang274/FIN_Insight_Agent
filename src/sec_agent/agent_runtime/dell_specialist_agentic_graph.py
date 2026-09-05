"""LangGraph-native, provider-neutral Specialist inner loop for the Dell slice.

The legacy Dell graph pre-fetches tools and calls each Specialist once.  This
module is the parallel Wave-2 successor: one Specialist may inspect its compact
context, request one bounded action at a time, observe typed tool feedback, and
revise its submission.  It deliberately owns no provider SDK, MCP server,
database, queue, or checkpointer.  Those are injected composition concerns.

Only structured action summaries and typed observations enter graph state.
Provider chain-of-thought, raw messages, credentials, clients, and exceptions
are never checkpoint fields.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    field_validator,
    model_validator,
)

from .dell_agentic_contracts import ProviderEvidenceIntent
from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest
from .dell_reference_vertical_contracts import (
    BoundBranchTask,
    RuntimeReceipt,
    canonical_sha256,
)


SPECIALIST_AGENTIC_GRAPH_SCHEMA_VERSION = (
    "fin_ia_dell_specialist_agentic_graph_v1_0"
)
_DIGEST_PATTERN = r"^[0-9a-f]{64}$"


class DellSpecialistAgenticGraphError(RuntimeError):
    """Typed graph/composition failure with no provider or secret payload."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class _StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
        str_strip_whitespace=True,
    )


class SpecialistL0Context(_StrictModel):
    """Answer-free context disclosed before the first model decision."""

    owner_data_gate_decision_digest: str = Field(pattern=_DIGEST_PATTERN)
    source_route_catalog_digest: str = Field(pattern=_DIGEST_PATTERN)
    inventory_snapshot_digest: str = Field(pattern=_DIGEST_PATTERN)
    disclosure_runtime_state: Literal[
        "current_state_authority_unavailable_fail_closed"
    ] = "current_state_authority_unavailable_fail_closed"
    capability_summaries: tuple[dict[str, Any], ...] = Field(min_length=1)
    skill_summaries: tuple[dict[str, Any], ...] = ()
    source_read_enabled: bool = False


class SpecialistAgenticInput(_StrictModel):
    schema_version: Literal[
        "fin_ia_dell_specialist_agentic_graph_v1_0"
    ] = SPECIALIST_AGENTIC_GRAPH_SCHEMA_VERSION
    run_id: str = Field(min_length=1, max_length=240)
    run_invocation_id: str = Field(min_length=1, max_length=240)
    agent_id: str = Field(min_length=1, max_length=240)
    task: BoundBranchTask
    required_route_obligation_ids: tuple[str, ...] = Field(
        min_length=1,
        max_length=16,
    )
    l0_context: SpecialistL0Context
    max_model_turns: int = Field(default=8, ge=2, le=24)
    max_tool_actions: int = Field(default=12, ge=1, le=48)

    @model_validator(mode="after")
    def validate_required_routes(self) -> "SpecialistAgenticInput":
        if len(self.required_route_obligation_ids) != len(
            set(self.required_route_obligation_ids)
        ):
            raise ValueError("specialist_required_route_duplicate")
        seeded = tuple(
            str(row["minimum_route_obligation_id"])
            for row in self.task.evidence_requests
            if row.get("minimum_route_obligation_id")
        )
        if (
            len(seeded) != len(set(seeded))
            or set(seeded) != set(self.required_route_obligation_ids)
        ):
            raise ValueError("specialist_required_route_task_binding_invalid")
        return self


class SpecialistDisclosureSelection(_StrictModel):
    kind: Literal["capability", "data_inventory", "skill", "artifact"]
    ref: str = Field(min_length=1, max_length=500)
    depth: Literal["summary", "metadata", "content"]
    reason: str = Field(min_length=1, max_length=1_000)
    expected_use: str = Field(min_length=1, max_length=1_000)
    parent_receipt_digest: str | None = Field(
        default=None,
        pattern=_DIGEST_PATTERN,
    )


class SpecialistFinanceIntent(_StrictModel):
    ticker: str = Field(min_length=1, max_length=16)
    metric_ids: tuple[str, ...] = Field(min_length=1, max_length=12)
    granularity: Literal[
        "quarter_discrete", "fiscal_ytd", "fiscal_year", "instant"
    ]
    selection_mode: Literal["exact_period_end", "latest_on_or_before"]
    period_start: str | None = Field(default=None, max_length=10)
    period_end: str | None = Field(default=None, max_length=10)
    fiscal_years: tuple[int, ...] = Field(default=(), max_length=4)
    requested_unit: str = Field(
        default="reported_source_unit",
        min_length=1,
        max_length=64,
    )
    unit_family: str | None = Field(default=None, min_length=1, max_length=64)

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized != "DELL":
            raise ValueError("specialist_finance_ticker_out_of_scope")
        return normalized

    @model_validator(mode="after")
    def validate_period(self) -> "SpecialistFinanceIntent":
        if (
            self.period_start is not None
            and self.period_end is not None
            and self.period_start > self.period_end
        ):
            raise ValueError("specialist_finance_period_inverted")
        if self.selection_mode == "exact_period_end" and self.period_end is None:
            raise ValueError("specialist_finance_exact_period_end_required")
        if len(self.metric_ids) != len(set(self.metric_ids)):
            raise ValueError("specialist_finance_metric_duplicate")
        if len(self.fiscal_years) != len(set(self.fiscal_years)):
            raise ValueError("specialist_finance_fiscal_year_duplicate")
        return self


class RequestDisclosureAction(_StrictModel):
    action: Literal["request_disclosure"]
    context_digest: str = Field(pattern=_DIGEST_PATTERN)
    reason_summary: str = Field(min_length=1, max_length=1_000)
    selection: SpecialistDisclosureSelection


class RequestEvidenceAction(_StrictModel):
    action: Literal["request_evidence"]
    context_digest: str = Field(pattern=_DIGEST_PATTERN)
    reason_summary: str = Field(min_length=1, max_length=1_000)
    minimum_route_obligation_id: str = Field(min_length=1, max_length=240)
    intent: ProviderEvidenceIntent


class RequestFinanceAction(_StrictModel):
    action: Literal["request_finance"]
    context_digest: str = Field(pattern=_DIGEST_PATTERN)
    reason_summary: str = Field(min_length=1, max_length=1_000)
    intent: SpecialistFinanceIntent


class RequestSourceAction(_StrictModel):
    action: Literal["request_source"]
    context_digest: str = Field(pattern=_DIGEST_PATTERN)
    reason_summary: str = Field(min_length=1, max_length=1_000)
    selection: SourceDocumentRequest


class RequestHumanReviewAction(_StrictModel):
    action: Literal["request_human_review"]
    context_digest: str = Field(pattern=_DIGEST_PATTERN)
    reason_summary: str = Field(min_length=1, max_length=1_000)
    blocker_code: str = Field(min_length=1, max_length=240)


ClaimKind = Literal[
    "reported_fact",
    "numeric_fact",
    "calculation",
    "inference",
    "hypothesis",
    "boundary",
]


class SpecialistClaim(_StrictModel):
    claim_id: str = Field(min_length=1, max_length=240)
    kind: ClaimKind
    materiality: Literal["high", "medium", "low"]
    statement: str = Field(min_length=1, max_length=4_000)
    evidence_ids: tuple[str, ...] = Field(default=(), max_length=32)
    fact_ids: tuple[str, ...] = Field(default=(), max_length=48)
    numeric_authority: Literal[
        "authoritative", "non_authoritative", "not_applicable"
    ] = "not_applicable"
    authority_note: str | None = Field(default=None, min_length=1, max_length=1_000)
    reasoning_summary: str | None = Field(default=None, max_length=4_000)
    citation_quotes: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_claim_shape(self) -> "SpecialistClaim":
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("specialist_claim_evidence_id_duplicate")
        if len(self.fact_ids) != len(set(self.fact_ids)):
            raise ValueError("specialist_claim_fact_id_duplicate")
        if self.kind == "reported_fact" and not self.evidence_ids:
            raise ValueError("reported_fact_requires_evidence")
        if self.kind == "numeric_fact" and (
            not self.fact_ids or self.numeric_authority != "authoritative"
        ):
            raise ValueError("numeric_fact_requires_authoritative_fact")
        if self.kind == "calculation" and (
            not (self.evidence_ids or self.fact_ids)
            or self.numeric_authority != "non_authoritative"
            or self.authority_note is None
        ):
            raise ValueError("calculation_requires_non_authoritative_disclosure")
        if self.kind in {"inference", "hypothesis", "boundary"} and (
            self.authority_note is None
        ):
            raise ValueError("analytical_claim_requires_authority_note")
        if self.kind not in {"numeric_fact", "calculation"} and (
            self.numeric_authority != "not_applicable"
        ):
            raise ValueError("non_numeric_claim_numeric_authority_invalid")
        return self


class SubmitWorkpaperAction(_StrictModel):
    action: Literal["submit_workpaper"]
    context_digest: str = Field(pattern=_DIGEST_PATTERN)
    reason_summary: str = Field(min_length=1, max_length=1_000)
    terminal_state: Literal["supported", "countered", "bounded_gap", "not_material"]
    thesis: str = Field(min_length=1, max_length=4_000)
    mechanism: str = Field(min_length=1, max_length=6_000)
    narrative_markdown: str = Field(min_length=1, max_length=30_000)
    claims: tuple[SpecialistClaim, ...] = Field(default=(), max_length=64)
    counterevidence: tuple[str, ...] = Field(min_length=1, max_length=12)
    what_would_change: tuple[str, ...] = Field(min_length=1, max_length=12)
    open_gaps: tuple[str, ...] = Field(default=(), max_length=16)

    @model_validator(mode="after")
    def validate_submission_shape(self) -> "SubmitWorkpaperAction":
        claim_ids = tuple(claim.claim_id for claim in self.claims)
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("specialist_submission_claim_id_duplicate")
        if self.terminal_state in {"supported", "countered"} and not self.claims:
            raise ValueError("supported_submission_requires_claims")
        return self


SpecialistAction = Annotated[
    RequestEvidenceAction
    | RequestSourceAction
    | RequestFinanceAction
    | RequestHumanReviewAction
    | SubmitWorkpaperAction,
    Field(discriminator="action"),
]


SpecialistModelTurnSource = Literal[
    "scripted_qualification",
    "saved_response_replay",
    "provider_model",
]


class SpecialistModelTurnRecord(_StrictModel):
    """One composition-attributed model decision and its optional host receipt."""

    schema_version: Literal[
        "fin_ia_dell_specialist_model_turn_record_v1_1"
    ] = "fin_ia_dell_specialist_model_turn_record_v1_1"
    turn_index: int = Field(ge=1, le=24)
    turn_source: SpecialistModelTurnSource = "scripted_qualification"
    model_execution_evidence: bool = False
    context_digest: str = Field(pattern=_DIGEST_PATTERN)
    action: SpecialistAction
    action_digest: str = Field(pattern=_DIGEST_PATTERN)
    runtime_receipt: RuntimeReceipt | None = None
    turn_record_digest: str = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_turn_record(self) -> "SpecialistModelTurnRecord":
        action_digest = canonical_sha256(self.action.model_dump(mode="json"))
        if self.action.context_digest != self.context_digest:
            raise ValueError("specialist_model_turn_context_mismatch")
        if self.action_digest != action_digest:
            raise ValueError("specialist_model_turn_action_digest_mismatch")
        if self.turn_source == "scripted_qualification":
            if self.model_execution_evidence or self.runtime_receipt is not None:
                raise ValueError("scripted_model_turn_receipt_forbidden")
        else:
            if self.runtime_receipt is None:
                raise ValueError("receipted_model_turn_receipt_required")
            if self.model_execution_evidence != (self.turn_source == "provider_model"):
                raise ValueError("model_turn_execution_evidence_invalid")
        unsigned = self.model_dump(mode="json", exclude={"turn_record_digest"})
        if canonical_sha256(unsigned) != self.turn_record_digest:
            raise ValueError("specialist_model_turn_record_digest_mismatch")
        return self


class SpecialistObservedReference(_StrictModel):
    ref_id: str = Field(min_length=1, max_length=500)
    artifact_digest: str = Field(pattern=_DIGEST_PATTERN)
    authority_state: Literal[
        "source_bound_passage",
        "reviewed_evidence",
        "retrieval_candidate",
        "captured_source_candidate",
        "numeric_fact",
        "non_authoritative_metric",
        "research_scenario",
        "typed_gap",
    ]
    writer_citable: bool = False
    numeric_fact_authority: bool = False

    @model_validator(mode="after")
    def validate_authority_flags(self) -> "SpecialistObservedReference":
        if self.writer_citable != (self.authority_state in {"reviewed_evidence", "source_bound_passage"}):
            raise ValueError("specialist_reference_writer_authority_invalid")
        if self.numeric_fact_authority != (self.authority_state == "numeric_fact"):
            raise ValueError("specialist_reference_numeric_authority_invalid")
        return self


class SpecialistToolFailure(_StrictModel):
    code: str = Field(min_length=1, max_length=240)
    owning_plane: Literal[
        "runtime_data_binding", "s1_data", "s2_data", "tool_adapter"
    ]
    retryability: Literal[
        "not_retryable",
        "correctable_with_new_information",
        "owner_repair_required",
    ]
    public_information_gap_proved: Literal[False] = False


class SpecialistRouteCompletion(_StrictModel):
    schema_version: Literal[
        "fin_ia_dell_specialist_route_completion_v1_0"
    ] = "fin_ia_dell_specialist_route_completion_v1_0"
    route_obligation_id: str = Field(min_length=1, max_length=240)
    owner_data_gate_decision_digest: str = Field(pattern=_DIGEST_PATTERN)
    source_route_catalog_digest: str = Field(pattern=_DIGEST_PATTERN)
    inventory_snapshot_digest: str = Field(pattern=_DIGEST_PATTERN)
    baseline_source_plan_digest: str = Field(pattern=_DIGEST_PATTERN)
    compilation_receipt_digest: str = Field(pattern=_DIGEST_PATTERN)
    reviewed_index_digests: tuple[str, ...] = Field(min_length=1, max_length=16)
    filter_receipt_digests: tuple[str, ...] = Field(min_length=1, max_length=64)
    expected_target_refs: tuple[str, ...] = Field(min_length=1, max_length=64)
    observed_target_refs: tuple[str, ...] = Field(min_length=1, max_length=64)
    source_family_refs: tuple[str, ...] = Field(min_length=1, max_length=32)
    evidence_ids: tuple[str, ...] = Field(min_length=1, max_length=256)
    authority_status: Literal["reviewed_evidence_complete"] = (
        "reviewed_evidence_complete"
    )
    completion_digest: str = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_completion(self) -> "SpecialistRouteCompletion":
        for field_name in (
            "reviewed_index_digests",
            "filter_receipt_digests",
            "expected_target_refs",
            "observed_target_refs",
            "source_family_refs",
            "evidence_ids",
        ):
            values = tuple(getattr(self, field_name))
            if values != tuple(sorted(set(values))):
                raise ValueError(f"specialist_route_{field_name}_not_canonical")
        if self.observed_target_refs != self.expected_target_refs:
            raise ValueError("specialist_route_target_coverage_incomplete")
        unsigned = self.model_dump(mode="json", exclude={"completion_digest"})
        if canonical_sha256(unsigned) != self.completion_digest:
            raise ValueError("specialist_route_completion_digest_mismatch")
        return self


class SpecialistToolObservation(_StrictModel):
    schema_version: Literal[
        "fin_ia_dell_specialist_tool_observation_v1_0"
    ] = "fin_ia_dell_specialist_tool_observation_v1_0"
    action_attempt_id: str = Field(min_length=1, max_length=500)
    kind: Literal["disclosure", "evidence", "finance"]
    provenance_kind: Literal["direct_tool", "mcp_bridge", "runtime_failure"]
    status: Literal["success", "denied", "empty", "tool_failure"]
    request_digest: str = Field(pattern=_DIGEST_PATTERN)
    references: tuple[SpecialistObservedReference, ...] = ()
    content: tuple[dict[str, Any], ...] = Field(default=(), max_length=64)
    route_completions: tuple[SpecialistRouteCompletion, ...] = Field(
        default=(),
        max_length=16,
    )
    failure: SpecialistToolFailure | None = None
    source_runtime_receipt: RuntimeReceipt | None = None
    runtime_receipt: RuntimeReceipt
    observation_digest: str = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_observation(self) -> "SpecialistToolObservation":
        if self.provenance_kind == "mcp_bridge":
            if (
                self.source_runtime_receipt is None
                or self.source_runtime_receipt.kind != "tool"
                or self.source_runtime_receipt.actor != f"{self.kind}_tool"
                or self.runtime_receipt.kind != "host"
                or self.runtime_receipt.actor
                != "dell_specialist_agentic_mcp_bridge"
            ):
                raise ValueError("specialist_observation_mcp_identity_invalid")
        elif self.provenance_kind == "direct_tool":
            if (
                self.source_runtime_receipt is not None
                or self.runtime_receipt.kind != "tool"
                or self.runtime_receipt.actor != f"{self.kind}_tool"
            ):
                raise ValueError("specialist_observation_tool_identity_invalid")
        elif (
            self.source_runtime_receipt is not None
            or self.status != "tool_failure"
            or self.runtime_receipt.kind != "host"
            or self.runtime_receipt.actor
            != "dell_specialist_agentic_runtime"
        ):
            raise ValueError("specialist_observation_runtime_failure_identity_invalid")
        if self.runtime_receipt.request_digest != self.request_digest:
            raise ValueError("specialist_observation_request_receipt_mismatch")
        if self.status == "tool_failure":
            if self.failure is None or self.runtime_receipt.status != "failure":
                raise ValueError("specialist_observation_failure_invalid")
        elif self.failure is not None or self.runtime_receipt.status != "success":
            raise ValueError("specialist_observation_success_invalid")
        if self.status in {"denied", "empty", "tool_failure"} and self.references:
            raise ValueError("specialist_observation_non_success_refs_forbidden")
        completion_route_ids = tuple(
            row.route_obligation_id for row in self.route_completions
        )
        if len(completion_route_ids) != len(set(completion_route_ids)):
            raise ValueError("specialist_observation_route_completion_duplicate")
        if self.route_completions and (
            self.kind != "evidence"
            or self.status != "success"
            or self.provenance_kind != "mcp_bridge"
        ):
            raise ValueError("specialist_observation_route_completion_invalid")
        expected_output_digest = canonical_sha256(
            {
                "schema_version": self.schema_version,
                "action_attempt_id": self.action_attempt_id,
                "kind": self.kind,
                "provenance_kind": self.provenance_kind,
                "status": self.status,
                "request_digest": self.request_digest,
                "references": tuple(
                    row.model_dump(mode="json") for row in self.references
                ),
                "content": self.content,
                "route_completions": tuple(
                    row.model_dump(mode="json")
                    for row in self.route_completions
                ),
                "failure": (
                    self.failure.model_dump(mode="json")
                    if self.failure is not None
                    else None
                ),
                "source_runtime_receipt": (
                    self.source_runtime_receipt.model_dump(mode="json")
                    if self.source_runtime_receipt is not None
                    else None
                ),
            }
        )
        if self.runtime_receipt.output_digest != expected_output_digest:
            raise ValueError("specialist_observation_output_receipt_mismatch")
        unsigned = self.model_dump(mode="json", exclude={"observation_digest"})
        if canonical_sha256(unsigned) != self.observation_digest:
            raise ValueError("specialist_observation_digest_mismatch")
        return self


class SpecialistFeedback(_StrictModel):
    code: str = Field(min_length=1, max_length=240)
    message: str = Field(min_length=1, max_length=2_000)
    owner_layer: Literal["agent", "runtime", "tool", "data"]
    available_next_actions: tuple[str, ...] = Field(min_length=1, max_length=8)
    public_information_gap_proved: Literal[False] = False


class SpecialistNotebook(_StrictModel):
    schema_version: Literal[
        "fin_ia_dell_specialist_notebook_v1_0"
    ] = "fin_ia_dell_specialist_notebook_v1_0"
    run_id: str = Field(min_length=1, max_length=240)
    run_invocation_id: str = Field(min_length=1, max_length=240)
    agent_id: str = Field(min_length=1, max_length=240)
    task_id: str = Field(min_length=1, max_length=240)
    branch_id: str = Field(min_length=1, max_length=120)
    task_revision: int = Field(ge=0, le=100)
    owner_data_gate_decision_digest: str = Field(pattern=_DIGEST_PATTERN)
    source_route_catalog_digest: str = Field(pattern=_DIGEST_PATTERN)
    inventory_snapshot_digest: str = Field(pattern=_DIGEST_PATTERN)
    model_turn_count: int = Field(ge=0, le=24)
    tool_action_count: int = Field(ge=0, le=48)
    required_route_obligation_ids: tuple[str, ...] = Field(
        min_length=1,
        max_length=16,
    )
    satisfied_route_obligation_ids: tuple[str, ...] = Field(
        default=(),
        max_length=16,
    )
    model_turn_records: tuple[SpecialistModelTurnRecord, ...] = ()
    observations: tuple[SpecialistToolObservation, ...] = ()
    feedback: tuple[SpecialistFeedback, ...] = ()
    dispatched_action_digests: tuple[str, ...] = ()
    status: Literal["researching", "submitted", "human_review_required"]
    source_read_enabled: bool = False
    notebook_digest: str = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_notebook(self) -> "SpecialistNotebook":
        if len(self.required_route_obligation_ids) != len(
            set(self.required_route_obligation_ids)
        ):
            raise ValueError("specialist_notebook_required_route_duplicate")
        if len(self.satisfied_route_obligation_ids) != len(
            set(self.satisfied_route_obligation_ids)
        ):
            raise ValueError("specialist_notebook_satisfied_route_duplicate")
        if not set(self.satisfied_route_obligation_ids).issubset(
            self.required_route_obligation_ids
        ):
            raise ValueError("specialist_notebook_satisfied_route_out_of_scope")
        if len(self.dispatched_action_digests) != len(
            set(self.dispatched_action_digests)
        ):
            raise ValueError("specialist_notebook_action_digest_duplicate")
        if self.tool_action_count != len(self.dispatched_action_digests):
            raise ValueError("specialist_notebook_tool_action_count_mismatch")
        if self.model_turn_count != len(self.model_turn_records):
            raise ValueError("specialist_notebook_model_turn_count_mismatch")
        if tuple(record.turn_index for record in self.model_turn_records) != tuple(
            range(1, self.model_turn_count + 1)
        ):
            raise ValueError("specialist_notebook_model_turn_sequence_invalid")
        unsigned = self.model_dump(mode="json", exclude={"notebook_digest"})
        if "source_read_enabled" not in self.model_fields_set:
            unsigned.pop("source_read_enabled", None)
        if canonical_sha256(unsigned) != self.notebook_digest:
            raise ValueError("specialist_notebook_digest_mismatch")
        return self


class SpecialistToolRequest(_StrictModel):
    schema_version: Literal[
        "fin_ia_dell_specialist_tool_request_v1_0"
    ] = "fin_ia_dell_specialist_tool_request_v1_0"
    action_attempt_id: str = Field(min_length=1, max_length=500)
    run_id: str = Field(min_length=1, max_length=240)
    run_invocation_id: str = Field(min_length=1, max_length=240)
    agent_id: str = Field(min_length=1, max_length=240)
    task: BoundBranchTask
    owner_data_gate_decision_digest: str = Field(pattern=_DIGEST_PATTERN)
    source_route_catalog_digest: str = Field(pattern=_DIGEST_PATTERN)
    inventory_snapshot_digest: str = Field(pattern=_DIGEST_PATTERN)
    disclosure_runtime_state: Literal[
        "current_state_authority_unavailable_fail_closed"
    ] = "current_state_authority_unavailable_fail_closed"
    action: SpecialistAction
    request_digest: str = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_request_digest(self) -> "SpecialistToolRequest":
        unsigned = self.model_dump(mode="json", exclude={"request_digest"})
        if canonical_sha256(unsigned) != self.request_digest:
            raise ValueError("specialist_tool_request_digest_mismatch")
        return self


class SpecialistHumanReviewHandoff(_StrictModel):
    """Terminal handoff until a canonical durable intervention path exists."""

    schema_version: Literal[
        "fin_ia_dell_specialist_human_review_handoff_v1_0"
    ] = "fin_ia_dell_specialist_human_review_handoff_v1_0"
    handoff_id: str = Field(min_length=1, max_length=240)
    run_id: str = Field(min_length=1, max_length=240)
    run_invocation_id: str = Field(min_length=1, max_length=240)
    agent_id: str = Field(min_length=1, max_length=240)
    task_id: str = Field(min_length=1, max_length=240)
    branch_id: str = Field(min_length=1, max_length=120)
    owner_data_gate_decision_digest: str = Field(pattern=_DIGEST_PATTERN)
    source_route_catalog_digest: str = Field(pattern=_DIGEST_PATTERN)
    inventory_snapshot_digest: str = Field(pattern=_DIGEST_PATTERN)
    notebook_digest: str = Field(pattern=_DIGEST_PATTERN)
    trigger: Literal["model_request", "model_turn_ceiling", "tool_action_ceiling"]
    reason_code: str = Field(min_length=1, max_length=240)
    continuation_authorized: Literal[False] = False
    required_resume_authority: Literal[
        "canonical_intervention_authority_unavailable"
    ] = "canonical_intervention_authority_unavailable"
    server_checkpoint_binding_state: Literal[
        "qualification_terminal_not_server_bound"
    ] = "qualification_terminal_not_server_bound"
    handoff_digest: str = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_handoff_digest(self) -> "SpecialistHumanReviewHandoff":
        unsigned = self.model_dump(mode="json", exclude={"handoff_digest"})
        if canonical_sha256(unsigned) != self.handoff_digest:
            raise ValueError("specialist_human_review_handoff_digest_mismatch")
        return self


class DellSpecialistAgenticState(TypedDict, total=False):
    schema_version: str
    run_id: str
    run_invocation_id: str
    agent_id: str
    task: dict[str, Any]
    required_route_obligation_ids: tuple[str, ...]
    l0_context: dict[str, Any]
    max_model_turns: int
    max_tool_actions: int
    notebook: dict[str, Any]
    pending_action: dict[str, Any] | None
    final_submission: dict[str, Any] | None
    human_review_handoff: dict[str, Any] | None
    review_reason: str | None
    review_trigger: str | None
    phase: str


ModelTurnPort = Callable[[Mapping[str, Any]], Mapping[str, Any]]
SpecialistToolPort = Callable[[Mapping[str, Any]], Mapping[str, Any]]


@dataclass(frozen=True)
class DellSpecialistAgenticDependencies:
    model_turn: ModelTurnPort
    evidence_tool: SpecialistToolPort
    finance_tool: SpecialistToolPort
    turn_source: SpecialistModelTurnSource = "scripted_qualification"
    expected_graph_input_digest: str | None = None


_ACTION_ADAPTER = TypeAdapter(SpecialistAction)


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    return value


def _validate_model_json(model: type[BaseModel], value: Any, *, code: str) -> Any:
    try:
        return model.model_validate_json(
            json.dumps(value, ensure_ascii=False, allow_nan=False)
        )
    except Exception:
        raise DellSpecialistAgenticGraphError(code) from None


def _validate_action(value: Any) -> SpecialistAction:
    try:
        return _ACTION_ADAPTER.validate_json(
            json.dumps(value, ensure_ascii=False, allow_nan=False)
        )
    except Exception:
        raise DellSpecialistAgenticGraphError(
            "specialist_model_action_invalid"
        ) from None


def _build_notebook(**fields: Any) -> SpecialistNotebook:
    body = {
        "schema_version": "fin_ia_dell_specialist_notebook_v1_0",
        **fields,
    }
    return SpecialistNotebook(**body, notebook_digest=canonical_sha256(body))


def _replace_notebook(
    notebook: SpecialistNotebook,
    **updates: Any,
) -> SpecialistNotebook:
    body = notebook.model_dump(mode="json", exclude={"notebook_digest"})
    body.update({key: _jsonable(value) for key, value in updates.items()})
    return _validate_model_json(
        SpecialistNotebook,
        {**body, "notebook_digest": canonical_sha256(body)},
        code="specialist_notebook_update_invalid",
    )


def _model_request(
    *,
    state: DellSpecialistAgenticState,
    notebook: SpecialistNotebook,
) -> dict[str, Any]:
    l0 = _validate_model_json(
        SpecialistL0Context,
        state["l0_context"],
        code="specialist_l0_context_invalid",
    )
    allowed_actions = [
        "request_evidence",
        "request_finance",
        "submit_workpaper",
        "request_human_review",
    ]
    if l0.source_read_enabled:
        allowed_actions.append("request_source")
    body = {
        "schema_version": SPECIALIST_AGENTIC_GRAPH_SCHEMA_VERSION,
        "agent_id": state["agent_id"],
        "task": state["task"],
        "l0_context": state["l0_context"],
        "notebook": notebook.model_dump(mode="json"),
        "execution_budget": {
            "max_model_turns": int(state["max_model_turns"]),
            "used_model_turns": notebook.model_turn_count,
            "remaining_model_turns": max(
                int(state["max_model_turns"]) - notebook.model_turn_count,
                0,
            ),
            "max_tool_actions": int(state["max_tool_actions"]),
            "used_tool_actions": notebook.tool_action_count,
            "remaining_tool_actions": max(
                int(state["max_tool_actions"]) - notebook.tool_action_count,
                0,
            ),
            "ceiling_semantics": "hard_anomaly_stop_not_completion_target",
        },
        "allowed_actions": allowed_actions,
        "privacy_contract": {
            "return_structured_action_only": True,
            "hidden_reasoning_must_not_be_returned": True,
            "reason_summary_is_decision_rationale_not_chain_of_thought": True,
        },
    }
    return {**body, "context_digest": canonical_sha256(body)}


def _build_model_turn_record(
    *,
    turn_index: int,
    request: Mapping[str, Any],
    action: SpecialistAction,
    turn_source: SpecialistModelTurnSource,
    runtime_receipt: RuntimeReceipt | None,
) -> SpecialistModelTurnRecord:
    body = {
        "schema_version": "fin_ia_dell_specialist_model_turn_record_v1_1",
        "turn_index": turn_index,
        "turn_source": turn_source,
        "model_execution_evidence": turn_source == "provider_model",
        "context_digest": request["context_digest"],
        "action": action.model_dump(mode="json"),
        "action_digest": canonical_sha256(action.model_dump(mode="json")),
        "runtime_receipt": (
            runtime_receipt.model_dump(mode="json")
            if runtime_receipt is not None
            else None
        ),
    }
    return _validate_model_json(
        SpecialistModelTurnRecord,
        {**body, "turn_record_digest": canonical_sha256(body)},
        code="specialist_model_turn_record_invalid",
    )


def _action_attempt_id(
    state: DellSpecialistAgenticState,
    *,
    notebook: SpecialistNotebook,
    action: SpecialistAction,
) -> str:
    digest = canonical_sha256(
        {
            "run_invocation_id": state["run_invocation_id"],
            "agent_id": state["agent_id"],
            "task_id": notebook.task_id,
            "model_turn_count": notebook.model_turn_count,
            "action": action.model_dump(mode="json"),
        }
    )
    return f"action-attempt:{digest[:32]}"


def _semantic_action_digest(action: SpecialistAction) -> str:
    """Identify a repeated tool request independently of a fresh context hash."""

    return canonical_sha256(
        action.model_dump(
            mode="json",
            exclude={"context_digest", "reason_summary"},
        )
    )


def _build_tool_request(
    state: DellSpecialistAgenticState,
    *,
    notebook: SpecialistNotebook,
    action: SpecialistAction,
) -> SpecialistToolRequest:
    l0 = _validate_model_json(
        SpecialistL0Context,
        state["l0_context"],
        code="specialist_l0_context_invalid",
    )
    body = {
        "schema_version": "fin_ia_dell_specialist_tool_request_v1_0",
        "action_attempt_id": _action_attempt_id(
            state,
            notebook=notebook,
            action=action,
        ),
        "run_id": state["run_id"],
        "run_invocation_id": state["run_invocation_id"],
        "agent_id": state["agent_id"],
        "task": state["task"],
        "owner_data_gate_decision_digest": (
            l0.owner_data_gate_decision_digest
        ),
        "source_route_catalog_digest": l0.source_route_catalog_digest,
        "inventory_snapshot_digest": l0.inventory_snapshot_digest,
        "disclosure_runtime_state": l0.disclosure_runtime_state,
        "action": action.model_dump(mode="json"),
    }
    return _validate_model_json(
        SpecialistToolRequest,
        {**body, "request_digest": canonical_sha256(body)},
        code="specialist_tool_request_invalid",
    )


def _feedback(
    code: str,
    message: str,
    *,
    owner_layer: Literal["agent", "runtime", "tool", "data"],
    next_actions: tuple[str, ...],
) -> SpecialistFeedback:
    return SpecialistFeedback(
        code=code,
        message=message,
        owner_layer=owner_layer,
        available_next_actions=next_actions,
        public_information_gap_proved=False,
    )


def _submission_errors(
    submission: SubmitWorkpaperAction,
    notebook: SpecialistNotebook,
) -> tuple[str, ...]:
    errors: list[str] = []
    references: dict[str, SpecialistObservedReference] = {}
    for observation in notebook.observations:
        for reference in observation.references:
            prior = references.get(reference.ref_id)
            if prior is not None and prior != reference:
                errors.append(f"reference_identity_conflict:{reference.ref_id}")
                continue
            references[reference.ref_id] = reference
    missing_routes = sorted(
        set(notebook.required_route_obligation_ids)
        - set(notebook.satisfied_route_obligation_ids)
    )
    if notebook.source_read_enabled and notebook.branch_id == "Q1_ISSUER_TRUTH":
        # Owner-approved division of work: issuer narrative and S2 financial
        # observations can arrive in different actions/periods. Do not claim
        # that the original all-Reviewed route receipt has been satisfied.
        items = [item for obs in notebook.observations for item in obs.content]
        f2_ids = {str(item.get("evidence_id")) for item in items
                  if item.get("result_state") == "reviewed_evidence"
                  and item.get("source_family_ref") == "F2_DELL_IR_EARNINGS"}
        cited_evidence = {ref for c in submission.claims for ref in c.evidence_ids}
        cited_facts = {ref for c in submission.claims for ref in c.fact_ids}
        if not f2_ids.intersection(cited_evidence):
            errors.append("q1_issuer_narrative_source_required")
        if not any(r.authority_state == "numeric_fact" and ref in cited_facts
                   for ref, r in references.items()):
            errors.append("q1_s2_financial_source_required")
    else:
        errors.extend(f"required_route_unsatisfied:{route_id}" for route_id in missing_routes)
    if submission.terminal_state == "bounded_gap":
        errors.append("bounded_gap_requires_canonical_gap_eligibility_receipt")
    for claim in submission.claims:
        if claim.kind == "calculation":
            errors.append(
                f"calculation_requires_canonical_receipt:{claim.claim_id}"
            )
        for evidence_id in claim.evidence_ids:
            reference = references.get(evidence_id)
            if reference is None:
                errors.append(f"unknown_evidence_id:{evidence_id}")
            elif not reference.writer_citable:
                errors.append(f"non_evidence_reference_cited:{evidence_id}")
            elif reference.authority_state == "source_bound_passage":
                passages = [item for obs in notebook.observations for item in obs.content
                            if item.get("passage_id") == evidence_id]
                quote = claim.citation_quotes.get(evidence_id, "")
                if not quote.strip() or not any(quote in str(p.get("passage", "")) for p in passages):
                    errors.append(f"source_quote_not_in_observed_passage:{evidence_id}")
                if not claim.authority_note:
                    errors.append(f"source_passage_requires_authority_note:{claim.claim_id}")
        for fact_id in claim.fact_ids:
            reference = references.get(fact_id)
            if reference is None:
                errors.append(f"unknown_fact_id:{fact_id}")
                continue
            allowed_fact_states = {
                "numeric_fact": {"numeric_fact"},
                "calculation": {"numeric_fact", "non_authoritative_metric"},
                "inference": {"numeric_fact", "non_authoritative_metric"},
                "hypothesis": {
                    "numeric_fact",
                    "non_authoritative_metric",
                    "research_scenario",
                },
                "boundary": {
                    "numeric_fact",
                    "non_authoritative_metric",
                    "research_scenario",
                },
                "reported_fact": set(),
            }[claim.kind]
            if reference.authority_state not in allowed_fact_states:
                errors.append(
                    f"fact_reference_authority_invalid:{claim.kind}:{fact_id}"
                )
        if claim.kind in {"reported_fact", "numeric_fact", "calculation", "inference"} and not (
            claim.evidence_ids or claim.fact_ids
        ):
            errors.append(f"unsupported_deliverable_claim:{claim.claim_id}")
    return tuple(dict.fromkeys(errors))


def build_dell_specialist_agentic_state_graph(
    *,
    dependencies: DellSpecialistAgenticDependencies,
) -> StateGraph[DellSpecialistAgenticState]:
    """Build one cyclic Specialist graph with injected model and tool ports."""

    def initialize(
        state: DellSpecialistAgenticState,
    ) -> DellSpecialistAgenticState:
        validated = _validate_model_json(
            SpecialistAgenticInput,
            state,
            code="specialist_agentic_input_invalid",
        )
        if (
            dependencies.expected_graph_input_digest is not None
            and canonical_sha256(validated.model_dump(mode="json"))
            != dependencies.expected_graph_input_digest
        ):
            raise DellSpecialistAgenticGraphError(
                "specialist_agentic_input_binding_invalid"
            )
        notebook = _build_notebook(
            run_id=validated.run_id,
            run_invocation_id=validated.run_invocation_id,
            agent_id=validated.agent_id,
            task_id=validated.task.task_id,
            branch_id=validated.task.branch_id,
            task_revision=validated.task.revision,
            owner_data_gate_decision_digest=(
                validated.l0_context.owner_data_gate_decision_digest
            ),
            source_route_catalog_digest=(
                validated.l0_context.source_route_catalog_digest
            ),
            inventory_snapshot_digest=(
                validated.l0_context.inventory_snapshot_digest
            ),
            model_turn_count=0,
            tool_action_count=0,
            required_route_obligation_ids=(
                validated.required_route_obligation_ids
            ),
            satisfied_route_obligation_ids=(),
            model_turn_records=(),
            observations=(),
            feedback=(),
            dispatched_action_digests=(),
            status="researching",
            source_read_enabled=validated.l0_context.source_read_enabled,
        )
        return {
            **validated.model_dump(mode="json"),
            "notebook": notebook.model_dump(mode="json"),
            "pending_action": None,
            "final_submission": None,
            "human_review_handoff": None,
            "review_reason": None,
            "review_trigger": None,
            "phase": "ready_for_model_decision",
        }

    def model_decide(
        state: DellSpecialistAgenticState,
    ) -> DellSpecialistAgenticState:
        notebook = _validate_model_json(
            SpecialistNotebook,
            state.get("notebook"),
            code="specialist_notebook_invalid",
        )
        if notebook.model_turn_count >= int(state["max_model_turns"]):
            return {
                "pending_action": None,
                "review_reason": "model_turn_ceiling_reached_no_silent_completion",
                "review_trigger": "model_turn_ceiling",
                "notebook": _replace_notebook(
                    notebook,
                    status="human_review_required",
                ).model_dump(mode="json"),
                "phase": "human_review_required",
            }
        request = _model_request(state=state, notebook=notebook)
        try:
            raw = dependencies.model_turn(request)
        except Exception:
            raise DellSpecialistAgenticGraphError(
                "specialist_model_turn_failed"
            ) from None
        runtime_receipt: RuntimeReceipt | None = None
        if dependencies.turn_source == "scripted_qualification":
            action = _validate_action(raw)
        else:
            if not isinstance(raw, Mapping) or set(raw) != {
                "action",
                "runtime_receipt",
            }:
                raise DellSpecialistAgenticGraphError(
                    "specialist_model_turn_receipt_envelope_invalid"
                )
            action = _validate_action(raw.get("action"))
            runtime_receipt = _validate_model_json(
                RuntimeReceipt,
                raw.get("runtime_receipt"),
                code="specialist_model_turn_receipt_invalid",
            )
            expected_receipt_kind = (
                "model"
                if dependencies.turn_source == "provider_model"
                else "host"
            )
            expected_receipt_actor = (
                request["agent_id"]
                if dependencies.turn_source == "provider_model"
                else "dell_specialist_saved_response_replay"
            )
            if (
                runtime_receipt.kind != expected_receipt_kind
                or runtime_receipt.status != "success"
                or runtime_receipt.actor != expected_receipt_actor
                or runtime_receipt.request_digest != canonical_sha256(request)
                or runtime_receipt.output_digest
                != canonical_sha256(action.model_dump(mode="json"))
                or runtime_receipt.transport_attempts != 1
            ):
                raise DellSpecialistAgenticGraphError(
                    "specialist_model_turn_receipt_binding_invalid"
                )
        if action.context_digest != request["context_digest"]:
            raise DellSpecialistAgenticGraphError(
                "specialist_model_turn_context_binding_invalid"
            )
        updated = _replace_notebook(
            notebook,
            model_turn_count=notebook.model_turn_count + 1,
            model_turn_records=(
                *notebook.model_turn_records,
                _build_model_turn_record(
                    turn_index=notebook.model_turn_count + 1,
                    request=request,
                    action=action,
                    turn_source=dependencies.turn_source,
                    runtime_receipt=runtime_receipt,
                ),
            ),
        )
        review_reason = (
            action.blocker_code
            if isinstance(action, RequestHumanReviewAction)
            else None
        )
        review_trigger = (
            "model_request" if isinstance(action, RequestHumanReviewAction) else None
        )
        if action.action not in request["allowed_actions"]:
            feedback = _feedback(
                "specialist_action_not_available_in_current_runtime",
                f"Action {action.action} is not available in the current runtime state.",
                owner_layer="runtime",
                next_actions=tuple(request["allowed_actions"]),
            )
            return {
                "notebook": _replace_notebook(
                    updated,
                    feedback=(*updated.feedback, feedback),
                ).model_dump(mode="json"),
                "pending_action": None,
                "review_reason": None,
                "review_trigger": None,
                "phase": "typed_feedback_ready",
            }
        if isinstance(action, RequestEvidenceAction):
            assigned_route_ids = {
                str(row.get("minimum_route_obligation_id") or "")
                for row in state["task"].get("evidence_requests", ())
                if isinstance(row, Mapping)
            }
            if action.minimum_route_obligation_id not in assigned_route_ids:
                feedback = _feedback(
                    "specialist_evidence_route_not_assigned",
                    "The requested evidence route is outside this Specialist task assignment.",
                    owner_layer="runtime",
                    next_actions=(
                        "request_evidence",
                        "request_human_review",
                    ),
                )
                return {
                    "notebook": _replace_notebook(
                        updated,
                        feedback=(*updated.feedback, feedback),
                    ).model_dump(mode="json"),
                    "pending_action": None,
                    "review_reason": None,
                    "review_trigger": None,
                    "phase": "typed_feedback_ready",
                }
        return {
            "notebook": updated.model_dump(mode="json"),
            "pending_action": action.model_dump(mode="json"),
            "review_reason": review_reason,
            "review_trigger": review_trigger,
            "phase": "model_action_selected",
        }

    def route_model_action(state: DellSpecialistAgenticState) -> str:
        raw = state.get("pending_action")
        if raw is None:
            if state.get("phase") == "typed_feedback_ready":
                return "decide"
            return "human_review"
        return _validate_action(raw).action

    def execute_tool(
        state: DellSpecialistAgenticState,
        *,
        port: SpecialistToolPort,
        expected_kind: Literal["evidence", "finance"],
    ) -> DellSpecialistAgenticState:
        notebook = _validate_model_json(
            SpecialistNotebook,
            state.get("notebook"),
            code="specialist_notebook_invalid",
        )
        action = _validate_action(state.get("pending_action"))
        if notebook.tool_action_count >= int(state["max_tool_actions"]):
            return {
                "pending_action": None,
                "review_reason": "tool_action_ceiling_reached_no_silent_completion",
                "review_trigger": "tool_action_ceiling",
                "notebook": _replace_notebook(
                    notebook,
                    status="human_review_required",
                ).model_dump(mode="json"),
                "phase": "human_review_required",
            }
        request = _build_tool_request(
            state,
            notebook=notebook,
            action=action,
        )
        action_digest = _semantic_action_digest(action)
        if action_digest in notebook.dispatched_action_digests:
            feedback = _feedback(
                "duplicate_tool_request_blocked_before_dispatch",
                "The identical request already ran; choose a different source, period, metric, or action.",
                owner_layer="agent",
                next_actions=(
                    "revise_request",
                    "request_disclosure",
                    "submit_workpaper",
                    "request_human_review",
                ),
            )
            return {
                "pending_action": None,
                "notebook": _replace_notebook(
                    notebook,
                    feedback=(*notebook.feedback, feedback),
                ).model_dump(mode="json"),
                "phase": "typed_feedback_ready",
            }
        try:
            raw = port(request.model_dump(mode="json"))
        except Exception:
            tool_failure = SpecialistToolFailure(
                code="tool_port_exception",
                owning_plane="tool_adapter",
                retryability="owner_repair_required",
            )
            failure_body = {
                "schema_version": "fin_ia_dell_specialist_tool_observation_v1_0",
                "action_attempt_id": request.action_attempt_id,
                "kind": expected_kind,
                "provenance_kind": "runtime_failure",
                "status": "tool_failure",
                "request_digest": request.request_digest,
                "references": (),
                "content": (),
                "route_completions": (),
                "failure": tool_failure.model_dump(mode="json"),
                "source_runtime_receipt": None,
                "runtime_receipt": {
                    "receipt_id": (
                        f"specialist-tool-failure:{request.request_digest[:24]}"
                    ),
                    "kind": "host",
                    "actor": "dell_specialist_agentic_runtime",
                    "status": "failure",
                    "request_digest": request.request_digest,
                    "output_digest": None,
                    "elapsed_ms": 0.0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "usage_reported": None,
                    "transport_attempts": 1,
                },
            }
            failure_body["runtime_receipt"]["output_digest"] = canonical_sha256(
                {
                    key: value
                    for key, value in failure_body.items()
                    if key != "runtime_receipt"
                }
            )
            failure_observation = _validate_model_json(
                SpecialistToolObservation,
                {
                    **failure_body,
                    "observation_digest": canonical_sha256(failure_body),
                },
                code="specialist_tool_failure_observation_invalid",
            )
            failure = _feedback(
                "tool_port_exception",
                "The tool did not return a valid receipt. This is a tool/runtime failure, not proof that public information is absent.",
                owner_layer="tool",
                next_actions=(
                    "choose_alternative_route",
                    "request_human_review",
                ),
            )
            updated = _replace_notebook(
                notebook,
                tool_action_count=notebook.tool_action_count + 1,
                dispatched_action_digests=(
                    *notebook.dispatched_action_digests,
                    action_digest,
                ),
                observations=(*notebook.observations, failure_observation),
                feedback=(*notebook.feedback, failure),
            )
            return {
                "pending_action": None,
                "notebook": updated.model_dump(mode="json"),
                "phase": "typed_feedback_ready",
            }
        observation = _validate_model_json(
            SpecialistToolObservation,
            raw,
            code="specialist_tool_observation_invalid",
        )
        if (
            observation.kind != expected_kind
            or observation.request_digest != request.request_digest
            or observation.action_attempt_id != request.action_attempt_id
        ):
            raise DellSpecialistAgenticGraphError(
                "specialist_tool_observation_binding_invalid"
            )
        if observation.route_completions:
            if (
                observation.provenance_kind != "mcp_bridge"
                or not isinstance(action, RequestEvidenceAction)
                or any(
                    completion.route_obligation_id
                    != action.minimum_route_obligation_id
                    or completion.owner_data_gate_decision_digest
                    != notebook.owner_data_gate_decision_digest
                    or completion.source_route_catalog_digest
                    != notebook.source_route_catalog_digest
                    or completion.inventory_snapshot_digest
                    != notebook.inventory_snapshot_digest
                    for completion in observation.route_completions
                )
            ):
                raise DellSpecialistAgenticGraphError(
                    "specialist_route_completion_action_binding_invalid"
                )
        updated = _replace_notebook(
            notebook,
            tool_action_count=notebook.tool_action_count + 1,
            dispatched_action_digests=(
                *notebook.dispatched_action_digests,
                action_digest,
            ),
            observations=(*notebook.observations, observation),
        )
        if (
            expected_kind == "evidence"
            and isinstance(action, RequestEvidenceAction)
            and action.minimum_route_obligation_id
            in notebook.required_route_obligation_ids
            and any(
                completion.route_obligation_id
                == action.minimum_route_obligation_id
                for completion in observation.route_completions
            )
        ):
            updated = _replace_notebook(
                updated,
                satisfied_route_obligation_ids=tuple(
                    dict.fromkeys(
                        (
                            *updated.satisfied_route_obligation_ids,
                            action.minimum_route_obligation_id,
                        )
                    )
                ),
            )
        if observation.failure is not None:
            updated = _replace_notebook(
                updated,
                feedback=(
                    *updated.feedback,
                    _feedback(
                        observation.failure.code,
                        "The tool returned a typed failure. Correct the request, choose an allowed alternative, or ask for human review; do not claim a public-information gap.",
                        owner_layer="data",
                        next_actions=(
                            "revise_request",
                            "choose_alternative_route",
                            "request_human_review",
                        ),
                    ),
                ),
            )
        return {
            "pending_action": None,
            "notebook": updated.model_dump(mode="json"),
            "phase": "tool_observation_ready",
        }

    def execute_evidence(
        state: DellSpecialistAgenticState,
    ) -> DellSpecialistAgenticState:
        return execute_tool(
            state,
            port=dependencies.evidence_tool,
            expected_kind="evidence",
        )

    def execute_finance(
        state: DellSpecialistAgenticState,
    ) -> DellSpecialistAgenticState:
        return execute_tool(
            state,
            port=dependencies.finance_tool,
            expected_kind="finance",
        )

    def validate_submission(
        state: DellSpecialistAgenticState,
    ) -> DellSpecialistAgenticState:
        notebook = _validate_model_json(
            SpecialistNotebook,
            state.get("notebook"),
            code="specialist_notebook_invalid",
        )
        action = _validate_action(state.get("pending_action"))
        if not isinstance(action, SubmitWorkpaperAction):
            raise DellSpecialistAgenticGraphError(
                "specialist_submission_action_invalid"
            )
        errors = _submission_errors(action, notebook)
        if errors:
            feedback = _feedback(
                "specialist_submission_reference_validation_failed",
                "Submission rejected: " + "; ".join(errors),
                owner_layer="agent",
                next_actions=(
                    "correct_claim_ledger",
                    "request_evidence",
                    "request_finance",
                    "request_human_review",
                ),
            )
            return {
                "pending_action": None,
                "notebook": _replace_notebook(
                    notebook,
                    feedback=(*notebook.feedback, feedback),
                ).model_dump(mode="json"),
                "phase": "submission_rejected_with_typed_feedback",
            }
        return {
            "pending_action": None,
            "final_submission": action.model_dump(mode="json"),
            "notebook": _replace_notebook(
                notebook,
                status="submitted",
            ).model_dump(mode="json"),
            "phase": "specialist_submission_accepted",
        }

    def route_after_submission(state: DellSpecialistAgenticState) -> str:
        return "end" if state.get("final_submission") is not None else "decide"

    def route_after_tool(state: DellSpecialistAgenticState) -> str:
        return (
            "human_review"
            if state.get("phase") == "human_review_required"
            else "decide"
        )

    def human_review(
        state: DellSpecialistAgenticState,
    ) -> DellSpecialistAgenticState:
        notebook = _validate_model_json(
            SpecialistNotebook,
            state.get("notebook"),
            code="specialist_notebook_invalid",
        )
        trigger = state.get("review_trigger")
        if trigger not in {
            "model_request",
            "model_turn_ceiling",
            "tool_action_ceiling",
        }:
            raise DellSpecialistAgenticGraphError(
                "specialist_human_review_trigger_invalid"
            )
        terminal_notebook = _replace_notebook(
            notebook,
            status="human_review_required",
        )
        reason_code = (
            state.get("review_reason") or "specialist_requested_human_review"
        )
        handoff_identity = {
            "run_id": state["run_id"],
            "run_invocation_id": state["run_invocation_id"],
            "agent_id": state["agent_id"],
            "task_id": terminal_notebook.task_id,
            "branch_id": terminal_notebook.branch_id,
            "owner_data_gate_decision_digest": (
                terminal_notebook.owner_data_gate_decision_digest
            ),
            "source_route_catalog_digest": (
                terminal_notebook.source_route_catalog_digest
            ),
            "inventory_snapshot_digest": (
                terminal_notebook.inventory_snapshot_digest
            ),
            "notebook_digest": terminal_notebook.notebook_digest,
            "trigger": trigger,
            "reason_code": reason_code,
        }
        handoff_id = (
            "specialist-human-review-handoff:"
            f"{canonical_sha256(handoff_identity)[:32]}"
        )
        handoff_body = {
            "schema_version": (
                "fin_ia_dell_specialist_human_review_handoff_v1_0"
            ),
            "handoff_id": handoff_id,
            **handoff_identity,
            "continuation_authorized": False,
            "required_resume_authority": (
                "canonical_intervention_authority_unavailable"
            ),
            "server_checkpoint_binding_state": (
                "qualification_terminal_not_server_bound"
            ),
        }
        handoff = _validate_model_json(
            SpecialistHumanReviewHandoff,
            {
                **handoff_body,
                "handoff_digest": canonical_sha256(handoff_body),
            },
            code="specialist_human_review_handoff_invalid",
        )
        return {
            "pending_action": None,
            "human_review_handoff": handoff.model_dump(mode="json"),
            "review_reason": reason_code,
            "review_trigger": trigger,
            "notebook": terminal_notebook.model_dump(mode="json"),
            "phase": "specialist_human_review_handoff_emitted",
        }

    graph = StateGraph(
        DellSpecialistAgenticState,
        input_schema=SpecialistAgenticInput,
    )
    graph.add_node("initialize", initialize)
    graph.add_node("model_decide", model_decide)
    graph.add_node("execute_evidence", execute_evidence)
    graph.add_node("execute_finance", execute_finance)
    graph.add_node("validate_submission", validate_submission)
    graph.add_node("human_review", human_review)
    graph.add_edge(START, "initialize")
    graph.add_edge("initialize", "model_decide")
    graph.add_conditional_edges(
        "model_decide",
        route_model_action,
        {
            "request_evidence": "execute_evidence",
            "request_source": "execute_evidence",
            "request_finance": "execute_finance",
            "submit_workpaper": "validate_submission",
            "request_human_review": "human_review",
            "decide": "model_decide",
            "human_review": "human_review",
        },
    )
    graph.add_conditional_edges(
        "execute_evidence",
        route_after_tool,
        {"decide": "model_decide", "human_review": "human_review"},
    )
    graph.add_conditional_edges(
        "execute_finance",
        route_after_tool,
        {"decide": "model_decide", "human_review": "human_review"},
    )
    graph.add_conditional_edges(
        "validate_submission",
        route_after_submission,
        {"decide": "model_decide", "end": END},
    )
    graph.add_edge("human_review", END)
    return graph


__all__ = [
    "SPECIALIST_AGENTIC_GRAPH_SCHEMA_VERSION",
    "DellSpecialistAgenticDependencies",
    "DellSpecialistAgenticGraphError",
    "DellSpecialistAgenticState",
    "ModelTurnPort",
    "RequestDisclosureAction",
    "RequestEvidenceAction",
    "RequestFinanceAction",
    "RequestHumanReviewAction",
    "SpecialistAction",
    "SpecialistAgenticInput",
    "SpecialistClaim",
    "SpecialistFinanceIntent",
    "SpecialistHumanReviewHandoff",
    "SpecialistL0Context",
    "SpecialistModelTurnRecord",
    "SpecialistModelTurnSource",
    "SpecialistNotebook",
    "SpecialistObservedReference",
    "SpecialistRouteCompletion",
    "SpecialistToolFailure",
    "SpecialistToolObservation",
    "SpecialistToolRequest",
    "SubmitWorkpaperAction",
    "build_dell_specialist_agentic_state_graph",
]
