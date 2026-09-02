"""Zero-call replay receipt for the immutable Dell A02 planner payload.

This module deliberately consumes only the extracted ``parsed_payload``.  It
does not load or persist the legacy provider envelope, hidden reasoning, or
credentials, and it never owns a model or network transport.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from sec_agent.canonical_runtime.contracts_v1_2 import (
    LEGACY_A02_PAID_FULL_CHAIN_EXECUTION_ID,
    canonical_json_sha256,
)

from .deepseek_structured_agents import PlannerSemanticPayload


LEGACY_A02_PLANNER_OUTCOME_REF = (
    "qualification://dell-reference-vertical/A02/planner-outcome"
)
LEGACY_A02_PLANNER_OUTCOME_SHA256 = (
    "234b64c3b03b39d8b76f7277dfdb4f64c2686802df5dc5c254304523d71e10d7"
)
LEGACY_A02_PLANNER_PARSED_PAYLOAD_SHA256 = (
    "bdeec49fb9bf75aa8101ce9ccc928d45c4f7d80b8b8378fe2a411339aa99c0fd"
)

_KNOWN_VALIDATION_CODES = (
    "local_evidence_request_scope_underbounded",
    "external_request_local_retrieval_scope_forbidden",
)


class _StrictFrozenModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        str_strip_whitespace=True,
    )


class LegacyPlannerReplayIssue(_StrictFrozenModel):
    issue_code: str = Field(min_length=1, max_length=160)
    location: tuple[str | int, ...] = Field(max_length=16)
    branch_id: str | None = Field(default=None, min_length=1, max_length=120)
    evidence_request_index: int | None = Field(default=None, ge=0, le=64)
    owner_layer: Literal["legacy_planner_contract"] = "legacy_planner_contract"
    retryable: Literal[False] = False


class LegacyA02ReplaySourceRecord(_StrictFrozenModel):
    """Host-resolved immutable provenance for the one real A02 outcome."""

    schema_version: Literal["fin_ia_dell_a02_replay_source_record_v1_0"] = (
        "fin_ia_dell_a02_replay_source_record_v1_0"
    )
    source_record_id: str = Field(min_length=1, max_length=240)
    resolver_ref: str = Field(min_length=1, max_length=240)
    store_revision: int = Field(ge=1)
    artifact_store_snapshot_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    paid_full_chain_execution_id: Literal[
        "20260902-dell-reference-vertical-structured-a02"
    ]
    attempt_state: Literal["start_failed"] = "start_failed"
    authority_mode: Literal["immutable_audit_only"] = "immutable_audit_only"
    source_artifact_ref: Literal[
        "qualification://dell-reference-vertical/A02/planner-outcome"
    ]
    source_artifact_sha256: Literal[
        "234b64c3b03b39d8b76f7277dfdb4f64c2686802df5dc5c254304523d71e10d7"
    ]
    parsed_payload_digest: Literal[
        "bdeec49fb9bf75aa8101ce9ccc928d45c4f7d80b8b8378fe2a411339aa99c0fd"
    ]
    resume_allowed: Literal[False] = False
    successor_authorized: Literal[False] = False
    issued_by: Literal["host_immutable_artifact_resolver"] = (
        "host_immutable_artifact_resolver"
    )
    source_record_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_source_record(self) -> "LegacyA02ReplaySourceRecord":
        body = self.model_dump(mode="json", exclude={"source_record_digest"})
        if canonical_json_sha256(body) != self.source_record_digest:
            raise ValueError("legacy_a02_replay_source_record_digest_invalid")
        return self


class LegacyA02ReplaySourceResolver(Protocol):
    """Host port; request payloads cannot supply or select an A02 source row."""

    def resolve_current_immutable_a02_planner_outcome(
        self,
    ) -> LegacyA02ReplaySourceRecord | None: ...


class LegacyPlannerReplayReceipt(_StrictFrozenModel):
    schema_version: Literal["fin_ia_dell_a02_planner_replay_receipt_v1_0"] = (
        "fin_ia_dell_a02_planner_replay_receipt_v1_0"
    )
    paid_full_chain_execution_id: Literal[
        "20260902-dell-reference-vertical-structured-a02"
    ]
    a02_attempt_state: Literal["start_failed"] = "start_failed"
    authority_mode: Literal["immutable_audit_only"] = "immutable_audit_only"
    resume_allowed: Literal[False] = False
    successor_authorized: Literal[False] = False
    source_authorization_record_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_artifact_ref: Literal[
        "qualification://dell-reference-vertical/A02/planner-outcome"
    ]
    source_artifact_sha256: Literal[
        "234b64c3b03b39d8b76f7277dfdb4f64c2686802df5dc5c254304523d71e10d7"
    ]
    parsed_payload_digest: Literal[
        "bdeec49fb9bf75aa8101ce9ccc928d45c4f7d80b8b8378fe2a411339aa99c0fd"
    ]
    schema_validation_status: Literal["schema_valid", "schema_invalid"]
    task_count: int = Field(ge=0, le=64)
    evidence_request_count: int = Field(ge=0, le=512)
    fact_request_count: int = Field(ge=0, le=512)
    issue_count: int = Field(ge=0, le=512)
    issues: tuple[LegacyPlannerReplayIssue, ...] = Field(max_length=512)
    model_calls: Literal[0] = 0
    network_calls: Literal[0] = 0
    provider_calls: Literal[0] = 0
    raw_response_persisted: Literal[False] = False
    receipt_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_receipt(self) -> "LegacyPlannerReplayReceipt":
        if self.issue_count != len(self.issues):
            raise ValueError("legacy_planner_replay_issue_count_mismatch")
        if (self.schema_validation_status == "schema_valid") != (not self.issues):
            raise ValueError("legacy_planner_replay_status_issue_mismatch")
        body = self.model_dump(mode="json", exclude={"receipt_digest"})
        if canonical_json_sha256(body) != self.receipt_digest:
            raise ValueError("legacy_planner_replay_receipt_digest_invalid")
        return self


def _sequence(value: Any) -> Sequence[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return value
    return ()


def _payload_counts(payload: Mapping[str, Any]) -> tuple[int, int, int]:
    tasks = _sequence(payload.get("tasks"))
    evidence_count = 0
    fact_count = 0
    for task in tasks:
        if not isinstance(task, Mapping):
            continue
        evidence_count += len(_sequence(task.get("evidence_requests")))
        fact_count += len(_sequence(task.get("fact_requests")))
    return len(tasks), evidence_count, fact_count


def _issue_code(error: Mapping[str, Any]) -> str:
    message = str(error.get("msg", ""))
    for code in _KNOWN_VALIDATION_CODES:
        if code in message:
            return code
    error_type = str(error.get("type", "validation_error"))
    if error_type == "too_short" and "evidence_requests" in _sequence(
        error.get("loc")
    ):
        return "planner_task_evidence_requests_too_short"
    return f"pydantic:{error_type}"[:160]


def _issue_from_error(
    error: Mapping[str, Any], payload: Mapping[str, Any]
) -> LegacyPlannerReplayIssue:
    raw_location = _sequence(error.get("loc"))
    location = tuple(
        component if isinstance(component, (str, int)) else str(component)
        for component in raw_location
    )
    task_index: int | None = None
    request_index: int | None = None
    if len(location) >= 2 and location[0] == "tasks" and isinstance(location[1], int):
        task_index = location[1]
    if (
        len(location) >= 4
        and location[2] == "evidence_requests"
        and isinstance(location[3], int)
    ):
        request_index = location[3]

    branch_id: str | None = None
    tasks = _sequence(payload.get("tasks"))
    if task_index is not None and 0 <= task_index < len(tasks):
        task = tasks[task_index]
        if isinstance(task, Mapping) and isinstance(task.get("branch_id"), str):
            branch_id = task["branch_id"]

    return LegacyPlannerReplayIssue(
        issue_code=_issue_code(error),
        location=location,
        branch_id=branch_id,
        evidence_request_index=request_index,
    )


def replay_legacy_a02_planner_payload(
    *,
    parsed_payload: Mapping[str, Any],
    source_resolver: LegacyA02ReplaySourceResolver | None,
) -> LegacyPlannerReplayReceipt:
    """Validate a saved semantic payload and return typed feedback, never a crash.

    The source identity is resolved through a host trust port and is fixed to
    A02's real ``start_failed`` audit-only artifact.  This function performs no
    file, model, provider, or network I/O and never authorizes a successor.
    """

    if not isinstance(parsed_payload, Mapping):
        raise TypeError("legacy_planner_replay_payload_mapping_required")
    if source_resolver is None:
        raise ValueError("legacy_a02_replay_source_resolver_required")
    source_record = source_resolver.resolve_current_immutable_a02_planner_outcome()
    if source_record is None:
        raise ValueError("legacy_a02_replay_source_record_missing")
    if not isinstance(source_record, LegacyA02ReplaySourceRecord):
        raise TypeError("legacy_a02_replay_source_record_model_required")
    source_record = LegacyA02ReplaySourceRecord.model_validate(
        source_record.model_dump(mode="python")
    )
    source_body = source_record.model_dump(
        mode="json", exclude={"source_record_digest"}
    )
    if canonical_json_sha256(source_body) != source_record.source_record_digest:
        raise ValueError("legacy_a02_replay_source_record_digest_invalid")
    parsed_payload_digest = canonical_json_sha256(parsed_payload)
    if (
        parsed_payload_digest != LEGACY_A02_PLANNER_PARSED_PAYLOAD_SHA256
        or parsed_payload_digest != source_record.parsed_payload_digest
    ):
        raise ValueError("legacy_a02_replay_parsed_payload_not_exact_source")

    issues: tuple[LegacyPlannerReplayIssue, ...]
    try:
        # Mirror the live JSON transport boundary.  Pydantic strict tuple fields
        # accept JSON arrays through ``model_validate_json`` but intentionally
        # reject an in-process Python list passed to ``model_validate``.
        PlannerSemanticPayload.model_validate_json(
            json.dumps(parsed_payload, ensure_ascii=False, allow_nan=False)
        )
        issues = ()
    except ValidationError as exc:
        issues = tuple(
            _issue_from_error(error, parsed_payload) for error in exc.errors()
        )

    task_count, evidence_count, fact_count = _payload_counts(parsed_payload)
    body = {
        "schema_version": "fin_ia_dell_a02_planner_replay_receipt_v1_0",
        "paid_full_chain_execution_id": LEGACY_A02_PAID_FULL_CHAIN_EXECUTION_ID,
        "a02_attempt_state": "start_failed",
        "authority_mode": "immutable_audit_only",
        "resume_allowed": False,
        "successor_authorized": False,
        "source_authorization_record_digest": source_record.source_record_digest,
        "source_artifact_ref": LEGACY_A02_PLANNER_OUTCOME_REF,
        "source_artifact_sha256": LEGACY_A02_PLANNER_OUTCOME_SHA256,
        "parsed_payload_digest": parsed_payload_digest,
        "schema_validation_status": "schema_valid" if not issues else "schema_invalid",
        "task_count": task_count,
        "evidence_request_count": evidence_count,
        "fact_request_count": fact_count,
        "issue_count": len(issues),
        "issues": issues,
        "model_calls": 0,
        "network_calls": 0,
        "provider_calls": 0,
        "raw_response_persisted": False,
    }
    return LegacyPlannerReplayReceipt(
        **body,
        receipt_digest=canonical_json_sha256(body),
    )


__all__ = [
    "LEGACY_A02_PAID_FULL_CHAIN_EXECUTION_ID",
    "LEGACY_A02_PLANNER_OUTCOME_REF",
    "LEGACY_A02_PLANNER_OUTCOME_SHA256",
    "LEGACY_A02_PLANNER_PARSED_PAYLOAD_SHA256",
    "LegacyA02ReplaySourceRecord",
    "LegacyA02ReplaySourceResolver",
    "LegacyPlannerReplayIssue",
    "LegacyPlannerReplayReceipt",
    "replay_legacy_a02_planner_payload",
]
