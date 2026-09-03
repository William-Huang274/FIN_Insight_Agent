"""Narrow zero-model qualification helpers for the Dell product graph.

This module is not a second workflow or planner.  It constructs one fixed Q1
Evidence/Finance task, validates the real tool results, and projects only a
secret- and content-free summary into the durable graph state.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .dell_reference_vertical_contracts import (
    BoundBranchTask,
    CaseFoundationBinding,
    ToolLaneResult,
    ToolLaneTask,
    canonical_sha256,
)


PRODUCT_EXECUTION_PROFILE = "product"
ZERO_MODEL_EXECUTION_PROFILE = "zero_model_control_plane_v1"
ZERO_MODEL_QUALIFICATION_SCHEMA_VERSION = (
    "fin_ia_dell_zero_model_graph_qualification_v1_0"
)

DellExecutionProfile = Literal["product", "zero_model_control_plane_v1"]

_QUALIFICATION_BRANCH_ID = "Q1_ISSUER_TRUTH"
_QUALIFICATION_ROUTE_ID = "route:Q1_ISSUER_TRUTH:required-reviewed"


class DellZeroModelQualificationError(ValueError):
    """Fail-closed qualification contract error."""


class ZeroModelQualificationDecision(BaseModel):
    """The only resume value accepted by the qualification interrupt."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        str_strip_whitespace=True,
    )

    action: Literal["complete_zero_model_qualification"]
    reason: str = Field(default="", max_length=2_000)


class ZeroModelQualificationSummary(BaseModel):
    """Content-free durable proof that the two approved lanes answered."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        str_strip_whitespace=True,
    )

    schema_version: Literal["fin_ia_dell_zero_model_graph_qualification_v1_0"]
    branch_id: Literal["Q1_ISSUER_TRUTH"]
    route_id: Literal["route:Q1_ISSUER_TRUTH:required-reviewed"]
    task_id: str = Field(min_length=1, max_length=240)
    plan_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_status: Literal["success"]
    evidence_result_states: tuple[str, ...] = Field(min_length=1)
    evidence_item_count: int = Field(ge=1)
    evidence_result_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_lane_receipt_id: str = Field(min_length=1, max_length=240)
    finance_status: Literal["success"]
    finance_result_states: tuple[str, ...] = Field(min_length=1)
    finance_item_count: int = Field(ge=1)
    finance_result_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    finance_lane_receipt_id: str = Field(min_length=1, max_length=240)
    tool_lane_execution_count: Literal[2]
    mcp_call_count: int = Field(ge=0)
    mcp_error_call_count: int = Field(ge=0)
    mcp_tool_call_counts: dict[str, int]
    model_call_count: Literal[0]
    live_external_research_call_count: Literal[0]
    paid_call_count: Literal[0]

    @model_validator(mode="after")
    def validate_expected_states(self) -> "ZeroModelQualificationSummary":
        if "reviewed_evidence" not in self.evidence_result_states:
            raise ValueError("zero_model_summary_reviewed_evidence_state_missing")
        if "numeric_fact" not in self.finance_result_states:
            raise ValueError("zero_model_summary_numeric_fact_state_missing")
        if sum(self.mcp_tool_call_counts.values()) != self.mcp_call_count:
            raise ValueError("zero_model_summary_mcp_call_count_mismatch")
        if self.mcp_error_call_count > self.mcp_call_count:
            raise ValueError("zero_model_summary_mcp_error_count_invalid")
        if any(not key or value < 1 for key, value in self.mcp_tool_call_counts.items()):
            raise ValueError("zero_model_summary_mcp_tool_count_invalid")
        return self


class SafeZeroModelQualificationDecision(BaseModel):
    """Content-free checkpoint form of the operator resume decision."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    action: Literal["complete_zero_model_qualification"]
    reason_provided: bool
    reason_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_reason_state(self) -> "SafeZeroModelQualificationDecision":
        if self.reason_provided != (self.reason_digest is not None):
            raise ValueError("zero_model_decision_reason_state_invalid")
        return self


def require_execution_profile(value: Any) -> DellExecutionProfile:
    """Accept only deployment-owned product or qualification profiles."""

    if value == PRODUCT_EXECUTION_PROFILE:
        return PRODUCT_EXECUTION_PROFILE
    if value == ZERO_MODEL_EXECUTION_PROFILE:
        return ZERO_MODEL_EXECUTION_PROFILE
    raise DellZeroModelQualificationError("dell_execution_profile_invalid")


def build_zero_model_qualification_tasks(
    *,
    binding: CaseFoundationBinding,
    run_id: str,
) -> tuple[ToolLaneTask, ToolLaneTask]:
    """Build the fixed, answer-free Q1 smoke task for the two real MCP lanes."""

    methods = [
        row for row in binding.branch_methods if row.branch_id == _QUALIFICATION_BRANCH_ID
    ]
    if len(methods) != 1:
        raise DellZeroModelQualificationError(
            "zero_model_qualification_method_binding_missing"
        )
    method = methods[0]
    evidence_request = {
        "minimum_route_obligation_id": _QUALIFICATION_ROUTE_ID,
        "intent": {
            "intent_kind": "reviewed_evidence",
            "query": "Dell operating performance and infrastructure demand",
            "purpose": "Exercise one exact Owner-approved reviewed Evidence route.",
            "entity_refs": ["DELL"],
            "period_intents": [],
            "expected_information_gain": (
                "Determine whether the frozen data plane can serve the exact route."
            ),
            "limit": 3,
            "topic_refs": ["operating_performance"],
            "evidence_role_refs": [],
            "minimum_authority_tier": "reviewed",
        },
    }
    fact_request = {
        "ticker": "DELL",
        "metric_ids": ["revenue"],
        "granularity": "quarter_discrete",
        "period_start": None,
        "period_end": None,
        "selection_mode": "latest_on_or_before",
        "fiscal_years": [],
        "requested_unit": "reported_source_unit",
        "unit_family": None,
    }
    qualification_contract = {
        "schema_version": ZERO_MODEL_QUALIFICATION_SCHEMA_VERSION,
        "run_id": run_id,
        "case_id": binding.case_id,
        "branch_id": _QUALIFICATION_BRANCH_ID,
        "research_as_of": binding.research_as_of,
        "snapshot_id": binding.snapshot_id,
        "foundation_digest": binding.foundation_digest,
        "method_digest": method.method_digest,
        "evidence_request": evidence_request,
        "fact_request": fact_request,
    }
    task = BoundBranchTask(
        task_id=(
            "qualification:Q1_ISSUER_TRUTH:"
            f"{canonical_sha256(qualification_contract)[:20]}"
        ),
        case_id=binding.case_id,
        branch_id=_QUALIFICATION_BRANCH_ID,
        revision=0,
        priority=method.priority,
        objective=(
            "Exercise the frozen Q1 Reviewed Evidence and DELL revenue MCP lanes; "
            "do not answer the research question."
        ),
        evidence_requests=(evidence_request,),
        fact_requests=(fact_request,),
        research_as_of=binding.research_as_of,
        snapshot_id=binding.snapshot_id,
        foundation_digest=binding.foundation_digest,
        method_digest=method.method_digest,
        plan_digest=canonical_sha256(qualification_contract),
    )
    return (
        ToolLaneTask(lane="evidence", task=task),
        ToolLaneTask(lane="finance", task=task),
    )


def project_zero_model_qualification_summary(
    *,
    evidence_result: ToolLaneResult,
    finance_result: ToolLaneResult,
) -> dict[str, Any]:
    """Validate the bounded smoke and retain no source or fact body in state."""

    _require_qualified_result(
        evidence_result,
        expected_lane="evidence",
        expected_state="reviewed_evidence",
    )
    _require_qualified_result(
        finance_result,
        expected_lane="finance",
        expected_state="numeric_fact",
    )
    if _result_identity(evidence_result) != _result_identity(finance_result):
        raise DellZeroModelQualificationError(
            "zero_model_qualification_cross_lane_identity_mismatch"
        )

    mcp_call_count, mcp_error_call_count, mcp_tool_call_counts = _mcp_summary(
        (evidence_result, finance_result)
    )
    summary = ZeroModelQualificationSummary(
        schema_version=ZERO_MODEL_QUALIFICATION_SCHEMA_VERSION,
        branch_id=evidence_result.branch_id,
        route_id=_QUALIFICATION_ROUTE_ID,
        task_id=evidence_result.task_id,
        plan_digest=evidence_result.plan_digest,
        evidence_status=evidence_result.status,
        evidence_result_states=evidence_result.result_states,
        evidence_item_count=len(evidence_result.items),
        evidence_result_digest=canonical_sha256(evidence_result),
        evidence_lane_receipt_id=evidence_result.runtime_receipt.receipt_id,
        finance_status=finance_result.status,
        finance_result_states=finance_result.result_states,
        finance_item_count=len(finance_result.items),
        finance_result_digest=canonical_sha256(finance_result),
        finance_lane_receipt_id=finance_result.runtime_receipt.receipt_id,
        tool_lane_execution_count=2,
        mcp_call_count=mcp_call_count,
        mcp_error_call_count=mcp_error_call_count,
        mcp_tool_call_counts=mcp_tool_call_counts,
        model_call_count=0,
        live_external_research_call_count=0,
        paid_call_count=0,
    )
    return summary.model_dump(mode="json")


def safe_zero_model_decision(value: ZeroModelQualificationDecision) -> dict[str, Any]:
    """Persist the decision without retaining free-form review text."""

    reason = value.reason.strip()
    return SafeZeroModelQualificationDecision(
        action=value.action,
        reason_provided=bool(reason),
        reason_digest=canonical_sha256({"reason": reason}) if reason else None,
    ).model_dump(mode="json")


def _require_qualified_result(
    result: ToolLaneResult,
    *,
    expected_lane: Literal["evidence", "finance"],
    expected_state: Literal["reviewed_evidence", "numeric_fact"],
) -> None:
    if result.lane != expected_lane:
        raise DellZeroModelQualificationError(
            "zero_model_qualification_lane_mismatch"
        )
    if result.status != "success":
        raise DellZeroModelQualificationError(
            f"zero_model_qualification_{expected_lane}_not_success"
        )
    if expected_state not in result.result_states:
        raise DellZeroModelQualificationError(
            f"zero_model_qualification_{expected_lane}_state_missing"
        )
    authority_field = (
        "writer_citable"
        if expected_lane == "evidence"
        else "numeric_fact_authority"
    )
    if not result.items or not any(
        item.get("result_state") == expected_state
        and item.get(authority_field) is True
        for item in result.items
        if isinstance(item, dict)
    ):
        raise DellZeroModelQualificationError(
            f"zero_model_qualification_{expected_lane}_item_missing"
        )


def _result_identity(result: ToolLaneResult) -> tuple[Any, ...]:
    return (
        result.task_id,
        result.case_id,
        result.branch_id,
        result.revision,
        result.research_as_of,
        result.snapshot_id,
        result.foundation_digest,
        result.method_digest,
        result.plan_digest,
    )


def _mcp_summary(
    results: Sequence[ToolLaneResult],
) -> tuple[int, int, dict[str, int]]:
    receipts: dict[str, dict[str, Any]] = {}
    for result in results:
        for item in result.items:
            candidates: list[Any] = []
            chain = item.get("mcp_receipt_chain")
            if isinstance(chain, Sequence) and not isinstance(
                chain, (str, bytes, bytearray)
            ):
                candidates.extend(chain)
            single = item.get("mcp_receipt")
            if isinstance(single, Mapping):
                candidates.append(single)
            for candidate in candidates:
                if not isinstance(candidate, Mapping):
                    continue
                projection = dict(candidate)
                receipt_identity = str(projection.get("call_id") or "")
                if not receipt_identity:
                    receipt_identity = canonical_sha256(projection)
                prior = receipts.get(receipt_identity)
                if prior is not None and prior != projection:
                    raise DellZeroModelQualificationError(
                        "zero_model_qualification_mcp_receipt_identity_conflict"
                    )
                receipts[receipt_identity] = projection
    tool_counts: dict[str, int] = {}
    for receipt in receipts.values():
        tool_name = str(receipt.get("tool_name") or "unknown")
        tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1
    error_count = sum(
        bool(row.get("is_error")) or bool(row.get("semantic_tool_failure"))
        for row in receipts.values()
    )
    if error_count:
        raise DellZeroModelQualificationError(
            "zero_model_qualification_mcp_receipt_error"
        )
    return len(receipts), error_count, dict(sorted(tool_counts.items()))


__all__ = [
    "DellExecutionProfile",
    "DellZeroModelQualificationError",
    "PRODUCT_EXECUTION_PROFILE",
    "SafeZeroModelQualificationDecision",
    "ZERO_MODEL_EXECUTION_PROFILE",
    "ZERO_MODEL_QUALIFICATION_SCHEMA_VERSION",
    "ZeroModelQualificationDecision",
    "ZeroModelQualificationSummary",
    "build_zero_model_qualification_tasks",
    "project_zero_model_qualification_summary",
    "require_execution_profile",
    "safe_zero_model_decision",
]
