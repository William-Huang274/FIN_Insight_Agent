"""Zero-model canonical runtime v1.2 contracts for the Dell agentic vertical.

The module is deliberately domain-only.  It does not dispatch work, call a
provider, persist state, or create a paid successor identity.  v1.0/v1.1 are
accepted only through explicit adapters and remain byte-immutable inputs.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Literal, Mapping, Protocol, Sequence

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)
from pydantic_core import to_jsonable_python
from typing_extensions import Annotated


CONTRACT_V1_2_REF = (
    "configs/research/"
    "fin_ia_0_1_3_agent_runtime_reflection_context_continuity_contract_v1_2.json"
)
LEGACY_A02_PAID_FULL_CHAIN_EXECUTION_ID = (
    "20260902-dell-reference-vertical-structured-a02"
)
LEGACY_A02_RUN_ID = "dell-reference-vertical-structured-run-a02"
LEGACY_A02_CANONICAL_SESSION_ID = "SESSION::LEGACY::A02"
LEGACY_A02_INITIAL_INVOCATION_ID = "RUN_INVOCATION::LEGACY::A02::1"
LEGACY_A02_PLANNER_ACTION_ATTEMPT_ID = (
    "planner-f8adf0fc5bf7-5d28981f08f4acc97e3a"
)
LEGACY_A01_PAID_FULL_CHAIN_EXECUTION_ID = (
    "20260902-dell-reference-vertical-q1-a01"
)
LEGACY_A01_RUN_ID = "dell-reference-vertical-q1-run-a01"
LEGACY_A02_READ_ONLY_AUTHORITY_REF = "authority://legacy/a02/read-only"
LEGACY_A02_READ_ONLY_RUNTIME_POLICY_REF = "policy://legacy/a02/immutable-audit-only"
LEGACY_A02_SOURCE_BUNDLE_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_dell_a02_identity_import_bundle_v1_0.json"
)
LEGACY_A02_SOURCE_BUNDLE_DIGEST = (
    "1433a49707d436edb3d15f2bea4c0d4ec997bb9509f8810cb4865ab7c57a11b8"
)
LEGACY_A02_OBJECTIVE_REF = "legacy-a02://start-input/research-question"
LEGACY_A02_OBJECTIVE_DIGEST = (
    "df711d6413f4b50bf16e0dd44d68c6cfc9e14772739dcfa849c9ec47b1cab84c"
)
LEGACY_A02_DATA_SNAPSHOT_REF = (
    "legacy-a02://snapshot/20260902-dell-structured-s1-s2-external-a02"
)
LEGACY_A02_DATA_SNAPSHOT_DIGEST = (
    "c7d33aa361c388e1c6aa28c6145e50e442e4203728d9ec7022e69589bfe1edf3"
)
LEGACY_A02_BASE_PLAN_DIGEST = (
    "5f1625cfd3ba75f5b00d76710fb38f247655cad8afa542b9a6b0869d728beeeb"
)
LEGACY_A02_BASE_PLAN_REF = f"legacy-a02://foundation/{LEGACY_A02_BASE_PLAN_DIGEST}"
LEGACY_A02_RUN_STARTED_AT = "2026-09-02T23:54:51.099264+08:00"
LEGACY_A02_RUN_FAILED_AT = "2026-09-02T23:55:36.644206+08:00"
LEGACY_A02_PLANNER_STARTED_AT = "2026-09-02T23:55:04.062176+08:00"
LEGACY_A02_PLANNER_FINISHED_AT = "2026-09-02T23:55:36.6312+08:00"
LEGACY_A02_PLANNER_ACTOR_ID = "planner:global:42f6b0499b02773c"
LEGACY_A02_PLANNER_REQUEST_REF = (
    "qualification://dell-reference-vertical/A02/model-calls/"
    "planner-f8adf0fc5bf7-5d28981f08f4acc97e3a/started"
)
LEGACY_A02_PLANNER_REQUEST_DIGEST = (
    "5d28981f08f4acc97e3a2a75aaaad8cedbee62f18a02e9b844a6c4016366c304"
)
LEGACY_A02_PLANNER_FAILURE_RECEIPT_REF = (
    "qualification://dell-reference-vertical/A02/model-calls/"
    "planner-f8adf0fc5bf7-5d28981f08f4acc97e3a/outcome"
)
LEGACY_A02_PLANNER_FAILURE_RECEIPT_DIGEST = (
    "234b64c3b03b39d8b76f7277dfdb4f64c2686802df5dc5c254304523d71e10d7"
)

Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
NonEmptyStr = Annotated[str, StringConstraints(min_length=1)]


class CanonicalV1_2Error(ValueError):
    """Raised when canonical identity, lineage, digest, or stale checks fail."""


def _jsonable(value: Any) -> Any:
    # Pydantic's JSON mode is also the wire representation used after model
    # validation (notably UTC datetimes use ``Z``).  Using the same encoder
    # before and after construction keeps a digest stable across that boundary.
    return to_jsonable_python(value)


def canonical_json(value: Any) -> str:
    """Return the one canonical JSON representation used by v1.2 digests."""

    return json.dumps(
        _jsonable(value),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def canonical_json_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


LEGACY_A02_READ_ONLY_RUNTIME_POLICY_DIGEST = canonical_json_sha256(
    {
        "contract_version": "1.2",
        "profile": "legacy_a02_immutable_audit_only",
        "generation_model_calls": 0,
        "paid_tool_calls": 0,
        "paid_successor_authorized": False,
        "resume_authorized": False,
        "evidence_promotion_authorized": False,
        "s2_write_authorized": False,
    }
)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _without(value: BaseModel, digest_field: str) -> dict[str, Any]:
    return value.model_dump(mode="json", exclude={digest_field})


def _assert_own_digest(value: BaseModel, digest_field: str, code: str) -> None:
    actual = getattr(value, digest_field)
    expected = canonical_json_sha256(_without(value, digest_field))
    if actual != expected:
        raise ValueError(code)


def _unique_refs(refs: Iterable[str], code: str, *, allow_empty: bool = True) -> tuple[str, ...]:
    normalized = tuple(refs)
    if not allow_empty and not normalized:
        raise ValueError(code)
    if any(not ref or ref != ref.strip() for ref in normalized):
        raise ValueError(code)
    if len(normalized) != len(set(normalized)):
        raise ValueError(code)
    return normalized


def _aware(value: datetime, code: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(code)
    return value


def _parse_aware(value: str, code: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    fractional = re.fullmatch(
        r"(?P<prefix>.+T\d{2}:\d{2}:\d{2})\.(?P<fraction>\d{1,6})(?P<offset>[+-]\d{2}:\d{2})",
        normalized,
    )
    if fractional is not None:
        normalized = (
            f"{fractional.group('prefix')}."
            f"{fractional.group('fraction').ljust(6, '0')}"
            f"{fractional.group('offset')}"
        )
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise CanonicalV1_2Error(code) from exc
    try:
        return _aware(parsed, code)
    except ValueError as exc:
        raise CanonicalV1_2Error(code) from exc


_PHANTOM_A03_LABEL = re.compile(
    # The historical reserved label is A03, not every ordinary third attempt
    # in an unrelated workflow. Identity spelling never grants paid authority.
    r"(?<![a-z0-9])a[^a-z0-9]*0[^a-z0-9]*3(?![a-z0-9])",
    re.IGNORECASE,
)


def _contains_phantom_a03(value: Any) -> bool:
    if isinstance(value, str):
        normalized = unicodedata.normalize("NFKC", value).casefold()
        return _PHANTOM_A03_LABEL.search(normalized) is not None
    if isinstance(value, (tuple, list, set, frozenset)):
        return any(_contains_phantom_a03(item) for item in value)
    return False


class StrictFrozenModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        validate_default=True,
        revalidate_instances="always",
    )

    @model_validator(mode="after")
    def _reject_blank_or_padded_strings(self) -> "StrictFrozenModel":
        for name, item in self.__dict__.items():
            if isinstance(item, str) and (not item or item != item.strip()):
                raise ValueError(f"canonical_v1_2_string_invalid:{name}")
            if (
                name.endswith(("_id", "_ref", "_refs"))
                or name == "case_version"
            ) and _contains_phantom_a03(item):
                raise ValueError(f"canonical_v1_2_phantom_a03_forbidden:{name}")
        return self

    @model_validator(mode="after")
    def _protect_reserved_legacy_identities(self) -> "StrictFrozenModel":
        model_name = type(self).__name__
        allowed_a02_identity_fields = {
            LEGACY_A02_CANONICAL_SESSION_ID: {
                ("AgentSessionV1_2", "session_id"),
                ("AgentSessionV1_2", "thread_id"),
                ("ResearchRun", "session_id"),
                ("RunInvocation", "session_id"),
                ("ActionAttempt", "session_id"),
                ("LegacyA02SourceBundle", "canonical_session_id"),
            },
            LEGACY_A02_RUN_ID: {
                ("ResearchRun", "run_id"),
                ("RunInvocation", "run_id"),
                ("ActionAttempt", "run_id"),
                ("LegacyA02SourceBundle", "legacy_run_id"),
            },
            LEGACY_A02_INITIAL_INVOCATION_ID: {
                ("RunInvocation", "invocation_id"),
                ("ActionAttempt", "run_invocation_id"),
            },
            LEGACY_A02_PLANNER_ACTION_ATTEMPT_ID: {
                ("ActionAttempt", "action_attempt_id"),
                ("LegacyA02SourceBundle", "planner_action_attempt_id"),
            },
            LEGACY_A02_PAID_FULL_CHAIN_EXECUTION_ID: {
                ("LegacyA02SourceBundle", "paid_full_chain_execution_id"),
                ("LegacyA02IdentityMapping", "legacy_paid_full_chain_execution_id"),
            },
        }
        permanently_reserved = {
            LEGACY_A01_RUN_ID,
            LEGACY_A01_PAID_FULL_CHAIN_EXECUTION_ID,
        }
        for field_name, value in self.__dict__.items():
            if not field_name.endswith("_id") or not isinstance(value, str):
                continue
            if value in permanently_reserved:
                raise ValueError("canonical_v1_2_reserved_legacy_identity_surface")
            allowed_fields = allowed_a02_identity_fields.get(value)
            if allowed_fields is not None and (model_name, field_name) not in allowed_fields:
                raise ValueError("canonical_v1_2_reserved_a02_identity_surface")
        return self


class AgentSessionV1_2(StrictFrozenModel):
    schema_version: Literal["fin_ia_agent_session_v1_2"] = "fin_ia_agent_session_v1_2"
    session_id: NonEmptyStr
    thread_id: NonEmptyStr
    case_id: NonEmptyStr
    case_version: NonEmptyStr
    as_of_date: date
    objective_ref: NonEmptyStr
    objective_digest: Sha256
    data_snapshot_ref: NonEmptyStr
    data_snapshot_digest: Sha256
    runtime_policy_ref: NonEmptyStr
    runtime_policy_digest: Sha256
    authority_refs: tuple[NonEmptyStr, ...] = Field(min_length=1)
    active_plan_ref: NonEmptyStr
    active_plan_digest: Sha256
    status: Literal["ACTIVE", "PAUSED", "STOPPED", "COMPLETED"]
    created_at: datetime
    updated_at: datetime
    session_digest: Sha256

    @field_validator("authority_refs")
    @classmethod
    def _authority_refs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _unique_refs(value, "agent_session_authority_refs_invalid", allow_empty=False)

    @field_validator("created_at", "updated_at")
    @classmethod
    def _timestamps(cls, value: datetime) -> datetime:
        return _aware(value, "agent_session_timestamp_not_timezone_aware")

    @model_validator(mode="after")
    def _invariants(self) -> "AgentSessionV1_2":
        if self.updated_at < self.created_at:
            raise ValueError("agent_session_time_reversed")
        if (
            self.session_id == LEGACY_A02_CANONICAL_SESSION_ID
            or self.thread_id == LEGACY_A02_CANONICAL_SESSION_ID
        ) and (
            self.session_id != LEGACY_A02_CANONICAL_SESSION_ID
            or self.thread_id != LEGACY_A02_CANONICAL_SESSION_ID
            or self.case_id != "DELL_AI_INFRA_REFERENCE_VERTICAL"
            or self.case_version != "FIN_0_1_3"
            or self.as_of_date != date(2026, 9, 2)
            or self.objective_ref != LEGACY_A02_OBJECTIVE_REF
            or self.objective_digest != LEGACY_A02_OBJECTIVE_DIGEST
            or self.data_snapshot_ref != LEGACY_A02_DATA_SNAPSHOT_REF
            or self.data_snapshot_digest != LEGACY_A02_DATA_SNAPSHOT_DIGEST
            or self.runtime_policy_ref != LEGACY_A02_READ_ONLY_RUNTIME_POLICY_REF
            or self.runtime_policy_digest != LEGACY_A02_READ_ONLY_RUNTIME_POLICY_DIGEST
            or self.authority_refs != (LEGACY_A02_READ_ONLY_AUTHORITY_REF,)
            or self.active_plan_ref != LEGACY_A02_BASE_PLAN_REF
            or self.active_plan_digest != LEGACY_A02_BASE_PLAN_DIGEST
            or self.status != "STOPPED"
            or self.created_at
            != _parse_aware(LEGACY_A02_RUN_STARTED_AT, "legacy_a02_run_started_at_invalid")
            or self.updated_at
            != _parse_aware(LEGACY_A02_RUN_FAILED_AT, "legacy_a02_run_failed_at_invalid")
        ):
            raise ValueError("agent_session_reserved_a02_profile_mismatch")
        _assert_own_digest(self, "session_digest", "agent_session_digest_invalid")
        return self


class ResearchRun(StrictFrozenModel):
    schema_version: Literal["fin_ia_research_run_v1_2"] = "fin_ia_research_run_v1_2"
    run_id: NonEmptyStr
    session_id: NonEmptyStr
    parent_run_id: NonEmptyStr | None = None
    origin_kind: Literal["INITIAL", "FOLLOW_UP", "LEGACY_A02_IMPORT"]
    legacy_paid_full_chain_execution_label: Literal["A02"] | None = None
    status: Literal[
        "CREATED",
        "RUNNING",
        "PAUSING",
        "PAUSED",
        "WAITING_HUMAN",
        "RECOVERY_REQUIRED",
        "CANCELLED",
        "START_FAILED",
        "FAILED",
        "COMPLETED",
    ]
    base_plan_ref: NonEmptyStr
    base_plan_digest: Sha256
    current_plan_ref: NonEmptyStr
    current_plan_digest: Sha256
    last_session_sequence: int = Field(ge=0)
    created_at: datetime
    terminal_at: datetime | None = None
    run_digest: Sha256

    @field_validator("created_at", "terminal_at")
    @classmethod
    def _timestamps(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _aware(value, "research_run_timestamp_not_timezone_aware")

    @model_validator(mode="after")
    def _invariants(self) -> "ResearchRun":
        terminal = {"CANCELLED", "START_FAILED", "FAILED", "COMPLETED"}
        if (self.status in terminal) != (self.terminal_at is not None):
            raise ValueError("research_run_terminal_time_mismatch")
        if self.terminal_at is not None and self.terminal_at < self.created_at:
            raise ValueError("research_run_time_reversed")
        if self.parent_run_id == self.run_id:
            raise ValueError("research_run_parent_self_reference")
        if (self.origin_kind == "FOLLOW_UP") != (self.parent_run_id is not None):
            raise ValueError("research_run_follow_up_parent_mismatch")
        is_legacy = self.origin_kind == "LEGACY_A02_IMPORT"
        if is_legacy != (self.legacy_paid_full_chain_execution_label == "A02"):
            raise ValueError("research_run_legacy_identity_mismatch")
        if (
            self.run_id == LEGACY_A02_RUN_ID
            or self.session_id == LEGACY_A02_CANONICAL_SESSION_ID
            or is_legacy
            or self.legacy_paid_full_chain_execution_label == "A02"
        ) and (
            self.run_id != LEGACY_A02_RUN_ID
            or self.session_id != LEGACY_A02_CANONICAL_SESSION_ID
            or self.parent_run_id is not None
            or self.origin_kind != "LEGACY_A02_IMPORT"
            or self.legacy_paid_full_chain_execution_label != "A02"
            or self.status != "START_FAILED"
            or self.base_plan_ref != LEGACY_A02_BASE_PLAN_REF
            or self.base_plan_digest != LEGACY_A02_BASE_PLAN_DIGEST
            or self.current_plan_ref != LEGACY_A02_BASE_PLAN_REF
            or self.current_plan_digest != LEGACY_A02_BASE_PLAN_DIGEST
            or self.last_session_sequence != 0
            or self.created_at
            != _parse_aware(LEGACY_A02_RUN_STARTED_AT, "legacy_a02_run_started_at_invalid")
            or self.terminal_at
            != _parse_aware(LEGACY_A02_RUN_FAILED_AT, "legacy_a02_run_failed_at_invalid")
        ):
            raise ValueError("research_run_reserved_a02_profile_mismatch")
        _assert_own_digest(self, "run_digest", "research_run_digest_invalid")
        return self


class RunInvocation(StrictFrozenModel):
    schema_version: Literal["fin_ia_run_invocation_v1_2"] = "fin_ia_run_invocation_v1_2"
    invocation_id: NonEmptyStr
    session_id: NonEmptyStr
    run_id: NonEmptyStr
    ordinal: int = Field(ge=1)
    invocation_kind: Literal["START", "RESUME", "RECOVERY"]
    status: Literal["SCHEDULED", "RUNNING", "SUCCEEDED", "FAILED", "INTERRUPTED"]
    trigger_ref: NonEmptyStr
    lease_ref: NonEmptyStr | None = None
    started_at: datetime
    finished_at: datetime | None = None
    invocation_digest: Sha256

    @field_validator("started_at", "finished_at")
    @classmethod
    def _timestamps(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _aware(value, "run_invocation_timestamp_not_timezone_aware")

    @model_validator(mode="after")
    def _invariants(self) -> "RunInvocation":
        if (self.ordinal == 1) != (self.invocation_kind == "START"):
            raise ValueError("run_invocation_ordinal_kind_mismatch")
        terminal = {"SUCCEEDED", "FAILED", "INTERRUPTED"}
        if (self.status in terminal) != (self.finished_at is not None):
            raise ValueError("run_invocation_terminal_time_mismatch")
        if self.finished_at is not None and self.finished_at < self.started_at:
            raise ValueError("run_invocation_time_reversed")
        if (
            self.invocation_id == LEGACY_A02_INITIAL_INVOCATION_ID
            or self.session_id == LEGACY_A02_CANONICAL_SESSION_ID
            or self.run_id == LEGACY_A02_RUN_ID
        ) and (
            self.invocation_id != LEGACY_A02_INITIAL_INVOCATION_ID
            or self.session_id != LEGACY_A02_CANONICAL_SESSION_ID
            or self.run_id != LEGACY_A02_RUN_ID
            or self.ordinal != 1
            or self.invocation_kind != "START"
            or self.status != "FAILED"
            or self.trigger_ref != "legacy://paid-full-chain/A02/start"
            or self.lease_ref is not None
            or self.started_at
            != _parse_aware(LEGACY_A02_RUN_STARTED_AT, "legacy_a02_run_started_at_invalid")
            or self.finished_at
            != _parse_aware(LEGACY_A02_RUN_FAILED_AT, "legacy_a02_run_failed_at_invalid")
        ):
            raise ValueError("run_invocation_reserved_a02_profile_mismatch")
        _assert_own_digest(self, "invocation_digest", "run_invocation_digest_invalid")
        return self


class ActionAttempt(StrictFrozenModel):
    schema_version: Literal["fin_ia_action_attempt_v1_2"] = "fin_ia_action_attempt_v1_2"
    action_attempt_id: NonEmptyStr
    session_id: NonEmptyStr
    run_id: NonEmptyStr
    run_invocation_id: NonEmptyStr
    actor_id: NonEmptyStr
    action_kind: Literal["MODEL", "TOOL", "CAPTURE", "PUBLISH"]
    action_name: NonEmptyStr
    request_ref: NonEmptyStr
    request_digest: Sha256
    state: Literal["INTENT_COMMITTED", "DISPATCHED", "RECEIPTED", "TERMINAL"]
    outcome: Literal[
        "APPLIED",
        "FAILED_BEFORE_DISPATCH",
        "AMBIGUOUS_AFTER_DISPATCH",
        "REJECTED_BEFORE_DISPATCH",
    ] | None = None
    was_dispatched: bool
    potentially_chargeable: bool
    receipt_kind: Literal["SUCCESS", "FAILURE"] | None = None
    receipt_ref: NonEmptyStr | None = None
    receipt_digest: Sha256 | None = None
    failure_code: NonEmptyStr | None = None
    parent_action_attempt_id: NonEmptyStr | None = None
    created_at: datetime
    terminal_at: datetime | None = None
    action_attempt_digest: Sha256

    @field_validator("created_at", "terminal_at")
    @classmethod
    def _timestamps(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _aware(value, "action_attempt_timestamp_not_timezone_aware")

    @model_validator(mode="after")
    def _invariants(self) -> "ActionAttempt":
        terminal = self.state == "TERMINAL"
        if terminal and (self.outcome is None or self.terminal_at is None):
            raise ValueError("action_attempt_terminal_outcome_mismatch")
        if not terminal and (self.outcome is not None or self.terminal_at is not None):
            raise ValueError("action_attempt_progress_state_has_terminal_fields")
        receipt_fields = (self.receipt_kind, self.receipt_ref, self.receipt_digest)
        if len({field is None for field in receipt_fields}) != 1:
            raise ValueError("action_attempt_receipt_fields_incomplete")
        if self.receipt_kind == "FAILURE" and self.failure_code is None:
            raise ValueError("action_attempt_failure_code_missing")
        if self.receipt_kind != "FAILURE" and self.failure_code is not None:
            raise ValueError("action_attempt_failure_code_without_failure_receipt")
        if self.outcome == "APPLIED" and self.receipt_ref is None:
            raise ValueError("action_attempt_applied_receipt_missing")
        if self.outcome == "APPLIED" and not self.was_dispatched:
            raise ValueError("action_attempt_applied_without_dispatch")
        if self.outcome == "AMBIGUOUS_AFTER_DISPATCH":
            if (
                not self.was_dispatched
                or not self.potentially_chargeable
                or self.receipt_ref is not None
            ):
                raise ValueError("action_attempt_ambiguous_boundary_invalid")
        if self.outcome in {"FAILED_BEFORE_DISPATCH", "REJECTED_BEFORE_DISPATCH"} and self.was_dispatched:
            raise ValueError("action_attempt_before_dispatch_outcome_invalid")
        if self.state == "INTENT_COMMITTED" and self.was_dispatched:
            raise ValueError("action_attempt_intent_marked_dispatched")
        if self.state == "INTENT_COMMITTED" and (
            self.receipt_ref is not None or self.potentially_chargeable
        ):
            raise ValueError("action_attempt_intent_has_receipt_or_chargeability")
        if self.state in {"DISPATCHED", "RECEIPTED"} and not self.was_dispatched:
            raise ValueError("action_attempt_dispatch_state_mismatch")
        if self.state == "DISPATCHED" and self.receipt_ref is not None:
            raise ValueError("action_attempt_dispatched_has_receipt")
        if self.state == "RECEIPTED" and self.receipt_ref is None:
            raise ValueError("action_attempt_receipted_without_receipt")
        if self.outcome in {"FAILED_BEFORE_DISPATCH", "REJECTED_BEFORE_DISPATCH"}:
            if self.receipt_ref is not None or self.potentially_chargeable:
                raise ValueError("action_attempt_before_dispatch_has_receipt_or_chargeability")
        if self.terminal_at is not None and self.terminal_at < self.created_at:
            raise ValueError("action_attempt_time_reversed")
        if self.parent_action_attempt_id == self.action_attempt_id:
            raise ValueError("action_attempt_parent_self_reference")
        if (
            self.action_attempt_id == LEGACY_A02_PLANNER_ACTION_ATTEMPT_ID
            or self.session_id == LEGACY_A02_CANONICAL_SESSION_ID
            or self.run_id == LEGACY_A02_RUN_ID
            or self.run_invocation_id == LEGACY_A02_INITIAL_INVOCATION_ID
            or self.parent_action_attempt_id == LEGACY_A02_PLANNER_ACTION_ATTEMPT_ID
        ) and (
            self.action_attempt_id != LEGACY_A02_PLANNER_ACTION_ATTEMPT_ID
            or self.session_id != LEGACY_A02_CANONICAL_SESSION_ID
            or self.run_id != LEGACY_A02_RUN_ID
            or self.run_invocation_id != LEGACY_A02_INITIAL_INVOCATION_ID
            or self.actor_id != LEGACY_A02_PLANNER_ACTOR_ID
            or self.action_kind != "MODEL"
            or self.action_name != "planner"
            or self.request_ref != LEGACY_A02_PLANNER_REQUEST_REF
            or self.request_digest != LEGACY_A02_PLANNER_REQUEST_DIGEST
            or self.state != "TERMINAL"
            or self.outcome != "APPLIED"
            or not self.was_dispatched
            or not self.potentially_chargeable
            or self.receipt_kind != "FAILURE"
            or self.receipt_ref != LEGACY_A02_PLANNER_FAILURE_RECEIPT_REF
            or self.receipt_digest != LEGACY_A02_PLANNER_FAILURE_RECEIPT_DIGEST
            or self.failure_code != "host_payload_validation_failed"
            or self.parent_action_attempt_id is not None
            or self.created_at
            != _parse_aware(
                LEGACY_A02_PLANNER_STARTED_AT,
                "legacy_a02_planner_started_at_invalid",
            )
            or self.terminal_at
            != _parse_aware(
                LEGACY_A02_PLANNER_FINISHED_AT,
                "legacy_a02_planner_finished_at_invalid",
            )
        ):
            raise ValueError("action_attempt_reserved_a02_profile_mismatch")
        _assert_own_digest(self, "action_attempt_digest", "action_attempt_digest_invalid")
        return self


class RecoveryDisposition(StrictFrozenModel):
    schema_version: Literal["fin_ia_recovery_disposition_v1_2"] = "fin_ia_recovery_disposition_v1_2"
    recovery_disposition_id: NonEmptyStr
    session_id: NonEmptyStr
    run_id: NonEmptyStr
    research_run_digest: Sha256
    ambiguous_action_attempt_id: NonEmptyStr
    ambiguous_action_attempt_digest: Sha256
    source_run_invocation_id: NonEmptyStr
    source_run_invocation_digest: Sha256
    investigation_receipt_refs: tuple[NonEmptyStr, ...] = Field(min_length=1)
    potentially_duplicate_cost: bool
    decision: Literal[
        "DO_NOT_RETRY",
        "RETRY_AS_NEW_ACTION",
        "RESUME_WITHOUT_RETRY",
        "ABANDON_RUN",
        "ESCALATE_TO_HUMAN",
    ]
    decision_authority_ref: NonEmptyStr
    next_run_invocation_id: NonEmptyStr | None = None
    next_run_invocation_digest: Sha256 | None = None
    replacement_action_attempt_id: NonEmptyStr | None = None
    replacement_action_attempt_digest: Sha256 | None = None
    created_at: datetime
    recovery_disposition_digest: Sha256

    @field_validator("investigation_receipt_refs")
    @classmethod
    def _receipts(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _unique_refs(value, "recovery_investigation_refs_invalid", allow_empty=False)

    @field_validator("created_at")
    @classmethod
    def _timestamp(cls, value: datetime) -> datetime:
        return _aware(value, "recovery_disposition_timestamp_not_timezone_aware")

    @model_validator(mode="after")
    def _invariants(self) -> "RecoveryDisposition":
        continues = self.decision in {"RETRY_AS_NEW_ACTION", "RESUME_WITHOUT_RETRY"}
        if (self.next_run_invocation_id is None) != (
            self.next_run_invocation_digest is None
        ):
            raise ValueError("recovery_disposition_new_invocation_binding_incomplete")
        if continues != (self.next_run_invocation_id is not None):
            raise ValueError("recovery_disposition_new_invocation_mismatch")
        retries = self.decision == "RETRY_AS_NEW_ACTION"
        if (self.replacement_action_attempt_id is None) != (
            self.replacement_action_attempt_digest is None
        ):
            raise ValueError("recovery_disposition_replacement_binding_incomplete")
        if retries != (self.replacement_action_attempt_id is not None):
            raise ValueError("recovery_disposition_replacement_action_mismatch")
        _assert_own_digest(
            self,
            "recovery_disposition_digest",
            "recovery_disposition_digest_invalid",
        )
        return self


LegacyEventType = Literal[
    "session_created", "plan_bound", "tool_execution_requested",
    "tool_execution_completed", "tool_execution_failed", "provider_attempt_requested",
    "provider_attempt_completed", "provider_attempt_failed", "feedback_issued",
    "plan_delta_submitted", "plan_delta_accepted", "plan_delta_rejected",
    "graph_delta_submitted", "graph_delta_accepted", "graph_delta_rejected",
    "checkpoint_created", "stop_decided", "session_resumed",
]
NewEventType = Literal[
    "run_created", "run_started", "run_paused", "run_recovery_required",
    "run_completed", "run_failed", "run_invocation_started",
    "run_invocation_completed", "run_invocation_failed", "action_intent_committed",
    "action_dispatched", "action_receipted", "action_terminal",
    "disclosure_requested", "disclosure_granted", "disclosure_denied",
    "evidence_admitted", "evidence_rejected", "decision_recorded",
    "finding_opened", "finding_resolved", "intervention_requested",
    "intervention_accepted", "intervention_rejected", "artifact_created",
    "artifact_revised", "publication_intent_committed", "publication_completed",
    "publication_failed",
]


_RUN_SCOPED_EVENT_TYPES = frozenset(
    {
        "plan_bound",
        "tool_execution_requested",
        "tool_execution_completed",
        "tool_execution_failed",
        "provider_attempt_requested",
        "provider_attempt_completed",
        "provider_attempt_failed",
        "feedback_issued",
        "plan_delta_submitted",
        "plan_delta_accepted",
        "plan_delta_rejected",
        "graph_delta_submitted",
        "graph_delta_accepted",
        "graph_delta_rejected",
        "checkpoint_created",
        "stop_decided",
        "session_resumed",
        "run_created",
        "run_started",
        "run_paused",
        "run_recovery_required",
        "run_completed",
        "run_failed",
        "run_invocation_started",
        "run_invocation_completed",
        "run_invocation_failed",
        "action_intent_committed",
        "action_dispatched",
        "action_receipted",
        "action_terminal",
        "disclosure_requested",
        "disclosure_granted",
        "disclosure_denied",
        "evidence_admitted",
        "evidence_rejected",
        "decision_recorded",
        "finding_opened",
        "finding_resolved",
        "intervention_requested",
        "intervention_accepted",
        "intervention_rejected",
        "artifact_created",
        "artifact_revised",
        "publication_intent_committed",
        "publication_completed",
        "publication_failed",
    }
)
_INVOCATION_SCOPED_EVENT_TYPES = frozenset(
    {
        "tool_execution_requested",
        "tool_execution_completed",
        "tool_execution_failed",
        "provider_attempt_requested",
        "provider_attempt_completed",
        "provider_attempt_failed",
        "run_invocation_started",
        "run_invocation_completed",
        "run_invocation_failed",
        "action_intent_committed",
        "action_dispatched",
        "action_receipted",
        "action_terminal",
        "disclosure_requested",
        "disclosure_granted",
        "disclosure_denied",
        "publication_intent_committed",
        "publication_completed",
        "publication_failed",
    }
)
_ACTION_SCOPED_EVENT_TYPES = frozenset(
    {
        "tool_execution_requested",
        "tool_execution_completed",
        "tool_execution_failed",
        "provider_attempt_requested",
        "provider_attempt_completed",
        "provider_attempt_failed",
        "action_intent_committed",
        "action_dispatched",
        "action_receipted",
        "action_terminal",
        "disclosure_requested",
        "disclosure_granted",
        "disclosure_denied",
        "publication_intent_committed",
        "publication_completed",
        "publication_failed",
    }
)


class CanonicalSessionEventV1_2(StrictFrozenModel):
    schema_version: Literal["fin_ia_canonical_session_event_v1_2"] = (
        "fin_ia_canonical_session_event_v1_2"
    )
    event_id: NonEmptyStr
    session_id: NonEmptyStr
    session_sequence: int = Field(ge=1)
    event_type: LegacyEventType | NewEventType
    run_id: NonEmptyStr | None = None
    run_invocation_id: NonEmptyStr | None = None
    action_attempt_id: NonEmptyStr | None = None
    actor_id: NonEmptyStr
    input_refs: tuple[NonEmptyStr, ...] = ()
    output_refs: tuple[NonEmptyStr, ...] = ()
    feedback_refs: tuple[NonEmptyStr, ...] = ()
    prior_event_digest: Sha256 | None = None
    occurred_at: datetime
    legacy_source_event_id: NonEmptyStr | None = None
    legacy_source_event_digest: Sha256 | None = None
    event_digest: Sha256

    @field_validator("input_refs", "output_refs", "feedback_refs")
    @classmethod
    def _refs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _unique_refs(value, "canonical_session_event_refs_invalid")

    @field_validator("occurred_at")
    @classmethod
    def _timestamp(cls, value: datetime) -> datetime:
        return _aware(value, "canonical_session_event_timestamp_not_timezone_aware")

    @model_validator(mode="after")
    def _invariants(self) -> "CanonicalSessionEventV1_2":
        if self.session_sequence == 1 and self.prior_event_digest is not None:
            raise ValueError("canonical_session_event_first_prior_digest_present")
        if self.session_sequence > 1 and self.prior_event_digest is None:
            raise ValueError("canonical_session_event_prior_digest_missing")
        if self.run_invocation_id is not None and self.run_id is None:
            raise ValueError("canonical_session_event_invocation_without_run")
        if self.action_attempt_id is not None and self.run_invocation_id is None:
            raise ValueError("canonical_session_event_action_without_invocation")
        if self.event_type in _RUN_SCOPED_EVENT_TYPES and self.run_id is None:
            raise ValueError("canonical_session_event_run_identity_required")
        if (
            self.event_type in _INVOCATION_SCOPED_EVENT_TYPES
            and self.run_invocation_id is None
        ):
            raise ValueError("canonical_session_event_invocation_identity_required")
        if (
            self.event_type in _ACTION_SCOPED_EVENT_TYPES
            and self.action_attempt_id is None
        ):
            raise ValueError("canonical_session_event_action_identity_required")
        if (self.legacy_source_event_id is None) != (self.legacy_source_event_digest is None):
            raise ValueError("canonical_session_event_legacy_binding_incomplete")
        _assert_own_digest(self, "event_digest", "canonical_session_event_digest_invalid")
        return self


class CanonicalEventLedgerSnapshot(StrictFrozenModel):
    """Current-session ledger snapshot issued by the durable event repository."""

    schema_version: Literal["fin_ia_canonical_event_ledger_snapshot_v1_2"] = (
        "fin_ia_canonical_event_ledger_snapshot_v1_2"
    )
    ledger_snapshot_id: NonEmptyStr
    repository_ref: NonEmptyStr
    session_id: NonEmptyStr
    store_revision: int = Field(ge=1)
    events: tuple[CanonicalSessionEventV1_2, ...] = Field(min_length=1)
    canonical_tip_digest: Sha256
    issued_by: Literal["host_canonical_event_repository"] = (
        "host_canonical_event_repository"
    )
    ledger_snapshot_digest: Sha256

    @model_validator(mode="after")
    def _invariants(self) -> "CanonicalEventLedgerSnapshot":
        events = validate_session_event_sequence(
            self.events,
            expected_session_id=self.session_id,
        )
        if events[-1].event_digest != self.canonical_tip_digest:
            raise ValueError("canonical_event_ledger_snapshot_tip_invalid")
        _assert_own_digest(
            self,
            "ledger_snapshot_digest",
            "canonical_event_ledger_snapshot_digest_invalid",
        )
        return self


_CURRENT_CONTEXT_MATERIAL_TUPLE_FIELDS = (
    "coverage_state_refs",
    "minimum_route_obligation_refs",
    "accepted_evidence_refs",
    "numeric_fact_refs",
    "claim_ledger_refs",
    "calculation_receipt_refs",
    "disclosure_receipt_refs",
    "skill_consumption_receipt_refs",
    "open_gap_refs",
    "unresolved_feedback_refs",
    "counterevidence_refs",
    "open_question_refs",
    "open_finding_refs",
    "pending_intervention_refs",
    "authority_refs",
)


def _derive_context_material_notebook_refs(value: Mapping[str, Any]) -> tuple[str, ...]:
    refs: set[str] = set()
    for name in _CURRENT_CONTEXT_MATERIAL_TUPLE_FIELDS:
        refs.update(value.get(name, ()))
    for name in (
        "active_stop_decision_ref",
        "budget_state_ref",
        "context_projection_ref",
        "langgraph_checkpoint_ref",
    ):
        ref = value.get(name)
        if ref is not None:
            refs.add(ref)
    return tuple(sorted(refs))


class CurrentContextMaterialSnapshotV1_2(StrictFrozenModel):
    """Host-owned current closure for one run checkpoint.

    This is the trust-port result, not a request model.  It binds the current
    accepted plan/graph, canonical event ledger, and every typed checkpoint
    material family (including evidence, facts, claims, calculations,
    disclosure/skill receipts, gaps, feedback, counterevidence, questions,
    findings, interventions, authority, stop/budget, projection, and the
    LangGraph checkpoint) into one revalidated snapshot.
    """

    schema_version: Literal[
        "fin_ia_current_context_material_snapshot_v1_2"
    ] = "fin_ia_current_context_material_snapshot_v1_2"
    material_snapshot_id: NonEmptyStr
    resolver_ref: NonEmptyStr
    store_revision: int = Field(ge=1)
    session_id: NonEmptyStr
    run_id: NonEmptyStr
    accepted_plan_ref: NonEmptyStr
    accepted_plan_digest: Sha256
    research_graph_digest: Sha256
    canonical_event_ledger: CanonicalEventLedgerSnapshot
    notebook_revision: int = Field(ge=0)
    notebook_refs: tuple[NonEmptyStr, ...]
    open_finding_refs: tuple[NonEmptyStr, ...]
    coverage_state_refs: tuple[NonEmptyStr, ...] = Field(min_length=1)
    minimum_route_obligation_refs: tuple[NonEmptyStr, ...] = Field(min_length=1)
    accepted_evidence_refs: tuple[NonEmptyStr, ...]
    numeric_fact_refs: tuple[NonEmptyStr, ...]
    claim_ledger_refs: tuple[NonEmptyStr, ...]
    calculation_receipt_refs: tuple[NonEmptyStr, ...]
    disclosure_receipt_refs: tuple[NonEmptyStr, ...]
    skill_consumption_receipt_refs: tuple[NonEmptyStr, ...]
    open_gap_refs: tuple[NonEmptyStr, ...]
    unresolved_feedback_refs: tuple[NonEmptyStr, ...]
    counterevidence_refs: tuple[NonEmptyStr, ...]
    open_question_refs: tuple[NonEmptyStr, ...]
    pending_intervention_refs: tuple[NonEmptyStr, ...]
    authority_refs: tuple[NonEmptyStr, ...] = Field(min_length=1)
    active_stop_decision_ref: NonEmptyStr
    budget_state_ref: NonEmptyStr
    context_projection_ref: NonEmptyStr
    langgraph_checkpoint_ref: NonEmptyStr
    issued_by: Literal["host_current_context_material_resolver"] = (
        "host_current_context_material_resolver"
    )
    material_snapshot_digest: Sha256

    @field_validator(
        "notebook_refs",
        "open_finding_refs",
        "coverage_state_refs",
        "minimum_route_obligation_refs",
        "accepted_evidence_refs",
        "numeric_fact_refs",
        "claim_ledger_refs",
        "calculation_receipt_refs",
        "disclosure_receipt_refs",
        "skill_consumption_receipt_refs",
        "open_gap_refs",
        "unresolved_feedback_refs",
        "counterevidence_refs",
        "open_question_refs",
        "pending_intervention_refs",
        "authority_refs",
    )
    @classmethod
    def _refs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _unique_refs(value, "current_context_material_snapshot_refs_invalid")

    @model_validator(mode="after")
    def _invariants(self) -> "CurrentContextMaterialSnapshotV1_2":
        if self.canonical_event_ledger.session_id != self.session_id:
            raise ValueError("current_context_material_event_ledger_session_mismatch")
        open_findings: set[str] = set()
        for event in self.canonical_event_ledger.events:
            if event.run_id != self.run_id or event.event_type not in {
                "finding_opened",
                "finding_resolved",
            }:
                continue
            finding_refs = {
                ref
                for ref in (
                    *event.input_refs,
                    *event.output_refs,
                    *event.feedback_refs,
                )
                if ref.startswith("finding://")
            }
            if len(finding_refs) != 1:
                raise ValueError("current_context_material_finding_event_ref_invalid")
            finding_ref = next(iter(finding_refs))
            if event.event_type == "finding_opened":
                if finding_ref in open_findings:
                    raise ValueError("current_context_material_finding_reopened")
                open_findings.add(finding_ref)
            else:
                if finding_ref not in open_findings:
                    raise ValueError("current_context_material_finding_resolved_without_open")
                open_findings.remove(finding_ref)
        if self.open_finding_refs != tuple(sorted(open_findings)):
            raise ValueError("current_context_material_open_finding_state_mismatch")
        if self.notebook_refs != _derive_context_material_notebook_refs(
            self.model_dump(mode="python")
        ):
            raise ValueError("current_context_material_notebook_closure_mismatch")
        _assert_own_digest(
            self,
            "material_snapshot_digest",
            "current_context_material_snapshot_digest_invalid",
        )
        return self


class CurrentContextMaterialResolver(Protocol):
    """Host trust port; API/model inputs never supply current material state."""

    def resolve_current_snapshot(
        self,
        *,
        session_id: str,
        run_id: str,
    ) -> CurrentContextMaterialSnapshotV1_2 | None: ...


class RunEventProjection(StrictFrozenModel):
    schema_version: Literal["fin_ia_run_event_projection_v1_2"] = (
        "fin_ia_run_event_projection_v1_2"
    )
    session_id: NonEmptyStr
    run_id: NonEmptyStr
    projection_sequence: int = Field(ge=1)
    source_session_sequence: int = Field(ge=1)
    source_event_id: NonEmptyStr
    source_event_digest: Sha256
    event_type: LegacyEventType | NewEventType
    occurred_at: datetime
    visible_input_refs: tuple[NonEmptyStr, ...] = ()
    visible_output_refs: tuple[NonEmptyStr, ...] = ()
    visible_feedback_refs: tuple[NonEmptyStr, ...] = ()
    projection_policy_digest: Sha256
    authorization_view_digest: Sha256
    projection_digest: Sha256

    @field_validator("visible_input_refs", "visible_output_refs", "visible_feedback_refs")
    @classmethod
    def _refs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _unique_refs(value, "run_event_projection_refs_invalid")

    @field_validator("occurred_at")
    @classmethod
    def _timestamp(cls, value: datetime) -> datetime:
        return _aware(value, "run_event_projection_timestamp_not_timezone_aware")

    @model_validator(mode="after")
    def _invariants(self) -> "RunEventProjection":
        _assert_own_digest(self, "projection_digest", "run_event_projection_digest_invalid")
        return self


class RunEventAuthorizationView(StrictFrozenModel):
    """Digest-bound ACL decision used to derive, never relabel, Run SSE rows."""

    schema_version: Literal["fin_ia_run_event_authorization_view_v1_2"] = (
        "fin_ia_run_event_authorization_view_v1_2"
    )
    authorization_view_id: NonEmptyStr
    principal_ref: NonEmptyStr
    session_id: NonEmptyStr
    run_id: NonEmptyStr
    projection_policy_digest: Sha256
    acl_snapshot_digest: Sha256
    authorization_basis_refs: tuple[NonEmptyStr, ...] = Field(min_length=1)
    visible_ref_ids: tuple[NonEmptyStr, ...] = ()
    authorization_view_digest: Sha256

    @field_validator("authorization_basis_refs", "visible_ref_ids")
    @classmethod
    def _refs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _unique_refs(value, "run_event_authorization_view_refs_invalid")

    @model_validator(mode="after")
    def _invariants(self) -> "RunEventAuthorizationView":
        _assert_own_digest(
            self,
            "authorization_view_digest",
            "run_event_authorization_view_digest_invalid",
        )
        return self


class ArtifactAclGrant(StrictFrozenModel):
    """One artifact visibility grant from the host-owned ACL index."""

    schema_version: Literal["fin_ia_artifact_acl_grant_v1_2"] = (
        "fin_ia_artifact_acl_grant_v1_2"
    )
    ref_id: NonEmptyStr
    allowed_principal_refs: tuple[NonEmptyStr, ...] = Field(min_length=1)
    authorization_basis_refs: tuple[NonEmptyStr, ...] = Field(min_length=1)
    grant_digest: Sha256

    @field_validator("allowed_principal_refs", "authorization_basis_refs")
    @classmethod
    def _refs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _unique_refs(value, "artifact_acl_grant_refs_invalid", allow_empty=False)

    @model_validator(mode="after")
    def _invariants(self) -> "ArtifactAclGrant":
        _assert_own_digest(self, "grant_digest", "artifact_acl_grant_digest_invalid")
        return self


class RunEventAclSnapshot(StrictFrozenModel):
    """Current request-principal view issued by the host ACL repository."""

    schema_version: Literal["fin_ia_run_event_acl_snapshot_v1_2"] = (
        "fin_ia_run_event_acl_snapshot_v1_2"
    )
    acl_snapshot_id: NonEmptyStr
    resolver_ref: NonEmptyStr
    store_revision: int = Field(ge=1)
    principal_ref: NonEmptyStr
    session_id: NonEmptyStr
    run_id: NonEmptyStr
    projection_policy_digest: Sha256
    grants: tuple[ArtifactAclGrant, ...]
    issued_by: Literal["host_acl_resolver"] = "host_acl_resolver"
    acl_snapshot_digest: Sha256

    @model_validator(mode="after")
    def _invariants(self) -> "RunEventAclSnapshot":
        refs = tuple(grant.ref_id for grant in self.grants)
        if len(refs) != len(set(refs)):
            raise ValueError("run_event_acl_snapshot_ref_duplicate")
        _assert_own_digest(
            self,
            "acl_snapshot_digest",
            "run_event_acl_snapshot_digest_invalid",
        )
        return self


class RunEventAclResolver(Protocol):
    """Host-injected, request-scoped resolver for the current ACL snapshot.

    Implementations own the authenticated principal and the authoritative ACL
    repository lookup.  Request payloads must never deserialize into this
    protocol or provide a ``RunEventAclSnapshot`` directly.
    """

    def resolve_current_snapshot(
        self,
        *,
        session_id: str,
        run_id: str,
    ) -> RunEventAclSnapshot:
        """Return the current host snapshot for this authenticated request."""


class RequiredMaterialRefSources(StrictFrozenModel):
    schema_version: Literal["fin_ia_required_material_ref_sources_v1_2"] = (
        "fin_ia_required_material_ref_sources_v1_2"
    )
    accepted_plan_refs: tuple[NonEmptyStr, ...] = Field(min_length=1)
    event_ledger_refs: tuple[NonEmptyStr, ...] = Field(min_length=1)
    notebook_refs: tuple[NonEmptyStr, ...]
    open_finding_refs: tuple[NonEmptyStr, ...]
    source_material_digest: Sha256

    @field_validator(
        "accepted_plan_refs", "event_ledger_refs", "notebook_refs", "open_finding_refs"
    )
    @classmethod
    def _refs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _unique_refs(value, "required_material_source_refs_invalid")

    @model_validator(mode="after")
    def _invariants(self) -> "RequiredMaterialRefSources":
        _assert_own_digest(self, "source_material_digest", "source_material_digest_invalid")
        return self

    def derive_required_refs(self) -> tuple[str, ...]:
        return tuple(sorted(set(
            self.accepted_plan_refs
            + self.event_ledger_refs
            + self.notebook_refs
            + self.open_finding_refs
        )))


class ContextCheckpointV1_2(StrictFrozenModel):
    schema_version: Literal["fin_ia_context_checkpoint_v1_2"] = (
        "fin_ia_context_checkpoint_v1_2"
    )
    checkpoint_id: NonEmptyStr
    session_id: NonEmptyStr
    session_digest: Sha256
    run_id: NonEmptyStr
    research_run_digest: Sha256
    run_invocation_id: NonEmptyStr
    run_invocation_digest: Sha256
    session_event_sequence: int = Field(ge=1)
    last_event_digest: Sha256
    canonical_event_ledger_snapshot_digest: Sha256
    current_material_snapshot_digest: Sha256
    notebook_revision: int = Field(ge=0)
    objective_digest: Sha256
    accepted_plan_ref: NonEmptyStr
    accepted_plan_digest: Sha256
    research_graph_digest: Sha256
    runtime_policy_digest: Sha256
    data_snapshot_digest: Sha256
    material_ref_sources: RequiredMaterialRefSources
    required_material_refs: tuple[NonEmptyStr, ...]
    coverage_state_refs: tuple[NonEmptyStr, ...]
    minimum_route_obligation_refs: tuple[NonEmptyStr, ...]
    accepted_evidence_refs: tuple[NonEmptyStr, ...]
    numeric_fact_refs: tuple[NonEmptyStr, ...]
    claim_ledger_refs: tuple[NonEmptyStr, ...]
    calculation_receipt_refs: tuple[NonEmptyStr, ...]
    disclosure_receipt_refs: tuple[NonEmptyStr, ...]
    skill_consumption_receipt_refs: tuple[NonEmptyStr, ...]
    open_gap_refs: tuple[NonEmptyStr, ...]
    unresolved_feedback_refs: tuple[NonEmptyStr, ...]
    counterevidence_refs: tuple[NonEmptyStr, ...]
    open_question_refs: tuple[NonEmptyStr, ...]
    unresolved_verifier_finding_refs: tuple[NonEmptyStr, ...]
    pending_intervention_refs: tuple[NonEmptyStr, ...]
    authority_refs: tuple[NonEmptyStr, ...]
    active_stop_decision_ref: NonEmptyStr
    budget_state_ref: NonEmptyStr
    context_projection_ref: NonEmptyStr
    langgraph_checkpoint_ref: NonEmptyStr
    created_at: datetime
    checkpoint_digest: Sha256

    @field_validator(
        "required_material_refs", "coverage_state_refs", "minimum_route_obligation_refs",
        "accepted_evidence_refs", "numeric_fact_refs", "claim_ledger_refs",
        "calculation_receipt_refs", "disclosure_receipt_refs",
        "skill_consumption_receipt_refs", "open_gap_refs", "unresolved_feedback_refs",
        "counterevidence_refs", "open_question_refs", "unresolved_verifier_finding_refs",
        "pending_intervention_refs", "authority_refs",
    )
    @classmethod
    def _refs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _unique_refs(value, "context_checkpoint_refs_invalid")

    @field_validator("created_at")
    @classmethod
    def _timestamp(cls, value: datetime) -> datetime:
        return _aware(value, "context_checkpoint_timestamp_not_timezone_aware")

    def typed_material_refs(self) -> set[str]:
        refs: set[str] = {
            self.accepted_plan_ref,
            self.active_stop_decision_ref,
            self.budget_state_ref,
            self.context_projection_ref,
            self.langgraph_checkpoint_ref,
        }
        refs.update(self.material_ref_sources.accepted_plan_refs)
        refs.update(self.material_ref_sources.event_ledger_refs)
        for field in (
            "coverage_state_refs", "minimum_route_obligation_refs", "accepted_evidence_refs",
            "numeric_fact_refs", "claim_ledger_refs", "calculation_receipt_refs",
            "disclosure_receipt_refs", "skill_consumption_receipt_refs", "open_gap_refs",
            "unresolved_feedback_refs", "counterevidence_refs", "open_question_refs",
            "unresolved_verifier_finding_refs", "pending_intervention_refs", "authority_refs",
        ):
            refs.update(getattr(self, field))
        return refs

    @model_validator(mode="after")
    def _invariants(self) -> "ContextCheckpointV1_2":
        derived = self.material_ref_sources.derive_required_refs()
        if self.required_material_refs != derived:
            raise ValueError("context_checkpoint_required_material_not_derived")
        missing = set(derived) - self.typed_material_refs()
        if missing:
            raise ValueError("context_checkpoint_required_material_untyped")
        _assert_own_digest(self, "checkpoint_digest", "context_checkpoint_digest_invalid")
        return self


class LegacyA02SourceBundle(StrictFrozenModel):
    """Exact, answer-free identity projection of the immutable A02 artifacts."""

    schema_version: Literal["fin_ia_legacy_a02_identity_import_bundle_v1_0"] = (
        "fin_ia_legacy_a02_identity_import_bundle_v1_0"
    )
    paid_full_chain_execution_id: Literal[
        "20260902-dell-reference-vertical-structured-a02"
    ]
    legacy_run_id: Literal["dell-reference-vertical-structured-run-a02"]
    canonical_session_id: Literal["SESSION::LEGACY::A02"]
    case_id: Literal["DELL_AI_INFRA_REFERENCE_VERTICAL"]
    case_version: Literal["FIN_0_1_3"]
    research_as_of: Literal["2026-09-02"]
    objective_ref: Literal["legacy-a02://start-input/research-question"]
    objective_digest: Sha256
    data_snapshot_ref: Literal[
        "legacy-a02://snapshot/20260902-dell-structured-s1-s2-external-a02"
    ]
    data_snapshot_digest: Sha256
    base_plan_ref: NonEmptyStr
    base_plan_digest: Sha256
    run_started_at: NonEmptyStr
    run_failed_at: NonEmptyStr
    planner_action_attempt_id: Literal[
        "planner-f8adf0fc5bf7-5d28981f08f4acc97e3a"
    ]
    planner_actor_id: Literal["planner:global:42f6b0499b02773c"]
    planner_started_at: NonEmptyStr
    planner_finished_at: NonEmptyStr
    planner_request_ref: NonEmptyStr
    planner_request_digest: Sha256
    planner_failure_receipt_ref: NonEmptyStr
    planner_failure_receipt_digest: Sha256
    failure_code: Literal["host_payload_validation_failed"]
    composition_artifact_sha256: Sha256
    start_input_artifact_sha256: Sha256
    planner_started_artifact_sha256: Sha256
    planner_outcome_artifact_sha256: Sha256
    failure_artifact_sha256: Sha256
    raw_response_omitted: Literal[True] = True
    source_bundle_digest: Sha256

    @model_validator(mode="after")
    def _invariants(self) -> "LegacyA02SourceBundle":
        for name in (
            "run_started_at",
            "run_failed_at",
            "planner_started_at",
            "planner_finished_at",
        ):
            _parse_aware(getattr(self, name), f"legacy_a02_{name}_invalid")
        if not (
            _parse_aware(self.run_started_at, "legacy_a02_run_started_at_invalid")
            <= _parse_aware(self.planner_started_at, "legacy_a02_planner_started_at_invalid")
            <= _parse_aware(self.planner_finished_at, "legacy_a02_planner_finished_at_invalid")
            <= _parse_aware(self.run_failed_at, "legacy_a02_run_failed_at_invalid")
        ):
            raise ValueError("legacy_a02_historical_time_order_invalid")
        _assert_own_digest(
            self,
            "source_bundle_digest",
            "legacy_a02_source_bundle_digest_invalid",
        )
        if self.source_bundle_digest != LEGACY_A02_SOURCE_BUNDLE_DIGEST:
            raise ValueError("legacy_a02_exact_source_bundle_required")
        return self


class LegacyA02IdentityMapping(StrictFrozenModel):
    schema_version: Literal["fin_ia_legacy_a02_identity_mapping_v1_2"] = (
        "fin_ia_legacy_a02_identity_mapping_v1_2"
    )
    legacy_paid_full_chain_execution_id: Literal[
        "20260902-dell-reference-vertical-structured-a02"
    ]
    source_bundle: LegacyA02SourceBundle
    agent_session: AgentSessionV1_2
    research_run: ResearchRun
    initial_run_invocation: RunInvocation
    planner_action_attempt: ActionAttempt
    imported_at: datetime
    mapping_digest: Sha256

    @model_validator(mode="after")
    def _invariants(self) -> "LegacyA02IdentityMapping":
        _aware(self.imported_at, "legacy_a02_import_timestamp_not_timezone_aware")
        if (
            self.source_bundle.paid_full_chain_execution_id
            != self.legacy_paid_full_chain_execution_id
            or self.source_bundle.legacy_run_id != self.research_run.run_id
        ):
            raise ValueError("legacy_a02_source_identity_mapping_mismatch")
        ids = {
            self.agent_session.session_id,
            self.research_run.session_id,
            self.initial_run_invocation.session_id,
            self.planner_action_attempt.session_id,
        }
        if len(ids) != 1:
            raise ValueError("legacy_a02_session_mapping_mismatch")
        run_ids = {
            self.research_run.run_id,
            self.initial_run_invocation.run_id,
            self.planner_action_attempt.run_id,
        }
        if run_ids != {LEGACY_A02_RUN_ID}:
            raise ValueError("legacy_a02_run_mapping_mismatch")
        if (
            self.research_run.origin_kind != "LEGACY_A02_IMPORT"
            or self.research_run.legacy_paid_full_chain_execution_label != "A02"
            or self.research_run.status != "START_FAILED"
        ):
            raise ValueError("legacy_a02_run_status_invalid")
        if (
            self.initial_run_invocation.invocation_id
            != "RUN_INVOCATION::LEGACY::A02::1"
            or self.initial_run_invocation.ordinal != 1
            or self.initial_run_invocation.invocation_kind != "START"
            or self.initial_run_invocation.status != "FAILED"
        ):
            raise ValueError("legacy_a02_initial_invocation_invalid")
        if (
            self.planner_action_attempt.run_invocation_id
            != self.initial_run_invocation.invocation_id
            or self.planner_action_attempt.action_attempt_id
            != self.source_bundle.planner_action_attempt_id
            or self.planner_action_attempt.actor_id
            != self.source_bundle.planner_actor_id
            or self.planner_action_attempt.action_kind != "MODEL"
            or self.planner_action_attempt.action_name != "planner"
            or self.planner_action_attempt.state != "TERMINAL"
            or self.planner_action_attempt.outcome != "APPLIED"
            or not self.planner_action_attempt.was_dispatched
            or not self.planner_action_attempt.potentially_chargeable
            or self.planner_action_attempt.receipt_kind != "FAILURE"
            or self.planner_action_attempt.failure_code
            != "host_payload_validation_failed"
        ):
            raise ValueError("legacy_a02_planner_failure_receipt_missing")
        if (
            self.agent_session.created_at
            != _parse_aware(
                self.source_bundle.run_started_at,
                "legacy_a02_run_started_at_invalid",
            )
            or self.agent_session.updated_at
            != _parse_aware(
                self.source_bundle.run_failed_at,
                "legacy_a02_run_failed_at_invalid",
            )
            or self.research_run.terminal_at != self.agent_session.updated_at
            or self.initial_run_invocation.finished_at != self.agent_session.updated_at
            or self.planner_action_attempt.created_at
            != _parse_aware(
                self.source_bundle.planner_started_at,
                "legacy_a02_planner_started_at_invalid",
            )
            or self.planner_action_attempt.terminal_at
            != _parse_aware(
                self.source_bundle.planner_finished_at,
                "legacy_a02_planner_finished_at_invalid",
            )
            or self.imported_at < self.agent_session.updated_at
        ):
            raise ValueError("legacy_a02_historical_timestamp_mapping_invalid")
        if (
            self.research_run.base_plan_ref != self.agent_session.active_plan_ref
            or self.research_run.current_plan_ref != self.agent_session.active_plan_ref
            or self.research_run.base_plan_digest != self.agent_session.active_plan_digest
            or self.research_run.current_plan_digest
            != self.agent_session.active_plan_digest
        ):
            raise ValueError("legacy_a02_plan_mapping_mismatch")
        if self.agent_session.authority_refs != (LEGACY_A02_READ_ONLY_AUTHORITY_REF,):
            raise ValueError("legacy_a02_read_only_authority_required")
        if (
            self.agent_session.runtime_policy_ref
            != LEGACY_A02_READ_ONLY_RUNTIME_POLICY_REF
            or self.agent_session.runtime_policy_digest
            != LEGACY_A02_READ_ONLY_RUNTIME_POLICY_DIGEST
        ):
            raise ValueError("legacy_a02_read_only_runtime_policy_required")
        _assert_own_digest(self, "mapping_digest", "legacy_a02_mapping_digest_invalid")
        return self


def _build(model: type[StrictFrozenModel], digest_field: str, body: Mapping[str, Any]) -> Any:
    unsigned = dict(body)
    return model(**unsigned, **{digest_field: canonical_json_sha256(unsigned)})


def _revalidate_boundary_model(
    value: Any,
    model: type[StrictFrozenModel],
    error_code: str,
) -> Any:
    """Re-run full Pydantic and digest validation at a trust boundary.

    ``frozen=True`` does not make ``model_copy`` or ``model_construct`` a trust
    boundary.  Public consumers therefore rebuild typed state from its Python
    projection before they inspect or authorize it.
    """

    if not isinstance(value, model):
        raise CanonicalV1_2Error(f"{error_code}_model_required")
    try:
        return model.model_validate(value.model_dump(mode="python"))
    except (AttributeError, TypeError, ValueError) as exc:
        raise CanonicalV1_2Error(f"{error_code}:{exc}") from exc


def load_runtime_contract_v1_2(repo_root: str | Path | None = None) -> dict[str, Any]:
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[3]
    path = root / CONTRACT_V1_2_REF
    try:
        contract = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CanonicalV1_2Error("runtime_contract_v1_2_unreadable") from exc
    if contract.get("schema_version") != "fin_ia_agent_runtime_reflection_context_continuity_contract_v1_2":
        raise CanonicalV1_2Error("runtime_contract_v1_2_schema_invalid")
    expected_top_level_keys = {
        "schema_version",
        "product_version",
        "status",
        "recorded_at",
        "authority",
        "immutable_predecessors",
        "canonicalization",
        "identity",
        "action_attempt",
        "session_event_envelope",
        "context_checkpoint",
        "authorization_projection",
        "progressive_disclosure_authority",
        "verified_artifact_registry_authority",
        "zero_model_transport",
        "immutable_A02_offline_replay",
        "implementation_boundary",
    }
    if set(contract) != expected_top_level_keys:
        raise CanonicalV1_2Error("runtime_contract_top_level_shape_invalid")
    authority = contract.get("authority")
    if not isinstance(authority, dict):
        raise CanonicalV1_2Error("runtime_contract_authority_invalid")
    expected_authority = {
        "design_ref": (
            "docs/architecture/research/"
            "FIN_0_1_3_DELL_AGENTIC_MULTI_AGENT_VERTICAL_DETAILED_"
            "TECHNICAL_DESIGN_20260903.zh-CN.md"
        ),
        "generation_model_calls": 0,
        "paid_tool_calls": 0,
        "A02_state": "immutable_start_failed_legacy_input_only",
        "A03_exists": False,
        "A03_placeholder_allowed": False,
        "paid_successor_authorized": False,
    }
    if authority != expected_authority:
        raise CanonicalV1_2Error("runtime_contract_authority_invalid")
    if (
        contract.get("product_version") != "FIN_0_1_3"
        or contract.get("status") != "zero_model_canonical_successor_contract"
        or contract.get("recorded_at") != "2026-09-03T00:00:00+08:00"
    ):
        raise CanonicalV1_2Error("runtime_contract_product_or_status_invalid")

    identity = contract.get("identity")
    expected_legacy_mapping = {
        "paid_full_chain_execution_id": LEGACY_A02_PAID_FULL_CHAIN_EXECUTION_ID,
        "run_id": LEGACY_A02_RUN_ID,
        "research_runs": 1,
        "run_invocations": 1,
        "planner_action_attempts": 1,
        "research_run_status": "START_FAILED",
        "planner_action_receipt_kind": "FAILURE",
        "authority_ref": LEGACY_A02_READ_ONLY_AUTHORITY_REF,
        "runtime_policy_ref": LEGACY_A02_READ_ONLY_RUNTIME_POLICY_REF,
        "runtime_policy_digest": LEGACY_A02_READ_ONLY_RUNTIME_POLICY_DIGEST,
        "source_bundle_ref": LEGACY_A02_SOURCE_BUNDLE_REF,
        "source_bundle_digest": LEGACY_A02_SOURCE_BUNDLE_DIGEST,
    }
    expected_identity_keys = {
        "AgentSessionV1_2",
        "ResearchRun",
        "RunInvocation",
        "ActionAttempt",
        "legacy_A02_mapping",
        "forbidden_legacy_labels",
        "phantom_identity_policy",
    }
    if (
        not isinstance(identity, dict)
        or set(identity) != expected_identity_keys
        or identity.get("AgentSessionV1_2")
        != "stable_case_conversation_and_top_level_langgraph_thread_one_to_many_research_runs"
        or identity.get("ResearchRun")
        != "one_complete_research_lifecycle_pause_resume_keep_identity_follow_up_creates_child"
        or identity.get("RunInvocation")
        != "one_start_resume_or_recovery_worker_dispatch_and_lease"
        or identity.get("ActionAttempt")
        != "one_model_tool_capture_or_publish_side_effect_attempt_retry_or_correction_gets_new_identity"
        or identity.get("legacy_A02_mapping") != expected_legacy_mapping
        or identity.get("forbidden_legacy_labels") != ["A03"]
        or identity.get("phantom_identity_policy") != "forbidden"
    ):
        raise CanonicalV1_2Error("runtime_contract_identity_boundary_invalid")

    exact_zero_model_sections = {
        "canonicalization": {
            "encoding": "UTF-8",
            "json_key_order": "lexicographic",
            "json_separators": [",", ":"],
            "ensure_ascii": False,
            "digest": "sha256_lowercase_hex",
            "digest_field_rule": "exclude_only_the_objects_own_digest_field",
        },
        "action_attempt": {
            "progress_states": ["INTENT_COMMITTED", "DISPATCHED", "RECEIPTED"],
            "terminal_state": "TERMINAL",
            "terminal_outcomes": [
                "APPLIED",
                "FAILED_BEFORE_DISPATCH",
                "AMBIGUOUS_AFTER_DISPATCH",
                "REJECTED_BEFORE_DISPATCH",
            ],
            "rules": [
                "progress_state_has_no_outcome",
                "terminal_state_has_exactly_one_outcome",
                "APPLIED_requires_a_durable_receipt_even_when_that_receipt_records_failure",
                "AMBIGUOUS_AFTER_DISPATCH_has_no_durable_result_receipt_and_is_never_auto_retried",
                "old_attempt_is_never_rewritten_by_recovery",
                "RecoveryDisposition_binds_exact_research_run_digest",
                "recovery_decision_precedes_any_new_invocation_or_replacement_action",
                "recovery_disposition_and_all_bound_identity_objects_revalidated_at_consumption",
            ],
        },
        "session_event_envelope": {
            "schema_version": "fin_ia_canonical_session_event_v1_2",
            "sequence_scope": "AgentSession",
            "sequence_origin": 1,
            "sequence_contiguous": True,
            "digest_chain": True,
            "legacy_event_types_inherited": 18,
            "projection_rule": (
                "filter_by_run_id_then_number_by_source_session_sequence_and_event_id"
            ),
            "projection_is_business_truth": False,
            "events_and_projections_revalidated_at_consumption": True,
        },
        "context_checkpoint": {
            "schema_version": "fin_ia_context_checkpoint_v1_2",
            "current_material_source": "host_current_context_material_resolver_only",
            "caller_supplied_expected_material_authoritative": False,
            "caller_authority_fields_forbidden_at_creation": True,
            "caller_extra_typed_refs_forbidden_at_creation": True,
            "current_material_snapshot_fields": [
                "accepted_plan_ref_and_digest",
                "research_graph_digest",
                "canonical_event_ledger_snapshot",
                "notebook_revision",
                "coverage_state_refs",
                "minimum_route_obligation_refs",
                "accepted_evidence_refs",
                "numeric_fact_refs",
                "claim_ledger_refs",
                "calculation_receipt_refs",
                "disclosure_receipt_refs",
                "skill_consumption_receipt_refs",
                "open_gap_refs",
                "unresolved_feedback_refs",
                "counterevidence_refs",
                "open_question_refs",
                "open_finding_refs",
                "pending_intervention_refs",
                "authority_refs",
                "active_stop_decision_ref",
                "budget_state_ref",
                "context_projection_ref",
                "langgraph_checkpoint_ref",
                "notebook_refs_derived_as_full_typed_state_closure",
            ],
            "required_material_source_sets": [
                "accepted_plan_refs",
                "event_ledger_refs",
                "notebook_refs",
                "open_finding_refs",
            ],
            "required_material_refs_rule": (
                "sorted_unique_union_derived_by_runtime_not_supplied_independently"
            ),
            "typed_material_families": [
                "coverage_state_refs",
                "minimum_route_obligation_refs",
                "accepted_evidence_refs",
                "numeric_fact_refs",
                "claim_ledger_refs",
                "calculation_receipt_refs",
                "disclosure_receipt_refs",
                "skill_consumption_receipt_refs",
                "open_gap_refs",
                "unresolved_feedback_refs",
                "counterevidence_refs",
                "open_question_refs",
                "unresolved_verifier_finding_refs",
                "pending_intervention_refs",
                "authority_refs",
                "active_stop_decision_ref",
                "budget_state_ref",
                "context_projection_ref",
                "langgraph_checkpoint_ref",
            ],
            "stale_checks": [
                "session_digest",
                "research_run_digest",
                "run_invocation_id",
                "run_invocation_digest",
                "objective_digest",
                "accepted_plan_ref",
                "accepted_plan_digest",
                "research_graph_digest",
                "runtime_policy_digest",
                "data_snapshot_digest",
                "source_material_digest",
                "current_material_snapshot_digest",
                "canonical_event_ledger_snapshot_digest",
                "notebook_revision",
                "coverage_state_refs",
                "minimum_route_obligation_refs",
                "accepted_evidence_refs",
                "numeric_fact_refs",
                "claim_ledger_refs",
                "calculation_receipt_refs",
                "disclosure_receipt_refs",
                "skill_consumption_receipt_refs",
                "open_gap_refs",
                "unresolved_feedback_refs",
                "counterevidence_refs",
                "open_question_refs",
                "open_finding_refs",
                "pending_intervention_refs",
                "authority_refs",
                "active_stop_decision_ref",
                "budget_state_ref",
                "context_projection_ref",
                "langgraph_checkpoint_ref",
                "session_event_sequence_and_last_event_digest",
                "latest_started_run_invocation_from_canonical_event_ledger",
            ],
            "open_finding_state_rebuilt_from_canonical_events": True,
            "checkpoint_material_sources_and_bound_identity_objects_revalidated_at_consumption": True,
        },
        "authorization_projection": {
            "visible_refs_source": "host_acl_resolver_current_snapshot_only",
            "caller_authored_visible_ref_list_authoritative": False,
            "acl_snapshot_digest_bound": True,
            "authenticated_principal_from_host_only": True,
            "store_revision_bound": True,
            "stale_view_revalidated_before_projection": True,
            "current_scope_authorization_record_revalidated": True,
            "assignment_issued_from_revalidated_accepted_plan": True,
            "task_owner_role_must_equal_sealed_scope_agent_role": True,
            "objective_plan_graph_and_assignment_digests_bound": True,
            "caller_authored_manifest_objective_authoritative": False,
            "current_acl_snapshot_and_nested_grants_revalidated_at_consumption": True,
        },
        "progressive_disclosure_authority": {
            "current_scope_authority_resolver_required": True,
            "current_canonical_ledger_reader_required": True,
            "current_catalog_resolver_required": True,
            "current_model_context_resolver_required": True,
            "model_visible_current_state_source": (
                "host_current_model_context_resolver_only"
            ),
            "caller_authored_manifest_current_state_authoritative": False,
            "manifest_current_state_fields": [
                "latest_plan_delta_refs",
                "observation_refs",
                "unresolved_feedback_refs",
                "available_next_actions",
                "budget_status",
                "stop_status",
                "intervention_status",
                "context_checkpoint_ref",
            ],
            "governance_summary_derived_from_runtime_policy": True,
            "current_model_context_snapshot_digest_bound": True,
            "current_model_context_snapshot_revalidated_at_consumption": True,
            "current_model_context_binds_scope_authorization_ledger_and_both_policies": True,
            "current_model_context_state_digest_bound_into_sealed_runtime_scope": True,
            "current_model_context_state_digest_includes_snapshot_resolver_and_store_revision": True,
            "re_signed_current_payload_without_scope_anchor_rejected": True,
            "runtime_policy_internal_identity_fields_cross_bound_to_scope": [
                "case_id",
                "case_version",
                "research_as_of",
            ],
            "runtime_policy_data_snapshot_cross_bound_to_scope_and_catalog_inventory": True,
            "runtime_policy_catalog_digest_cross_bound_to_current_catalog": True,
            "runtime_policy_disclosure_digest_cross_bound_to_current_disclosure_policy_and_scope": True,
            "runtime_scope_branches_and_permissions_subset_of_runtime_policy": True,
            "scope_authority_event_required": True,
            "request_must_precede_grant": True,
            "resource_identity_and_content_digest_bound": True,
            "runtime_and_disclosure_policy_digests_distinct": True,
            "runtime_policy_binds_disclosure_policy_digest": True,
            "scope_and_authorization_bind_both_policy_digests": True,
            "grant_view_revalidated_before_decision_and_manifest": True,
            "catalog_revalidated_before_decision_and_manifest": True,
            "catalog_nested_semantics_revalidated_at_consumption": True,
            "policy_self_digest_revalidated_at_consumption": True,
            "receipt_self_digest_revalidated_at_consumption": True,
            "canonical_ledger_snapshot_self_digest_revalidated_at_consumption": True,
            "manifest_binds_disclosure_policy_even_without_grants": True,
        },
        "verified_artifact_registry_authority": {
            "current_host_resolver_required": True,
            "caller_supplied_snapshot_authoritative": False,
            "store_revision_and_tip_bound": True,
            "coverage_gap_and_plan_delta_revalidate_current_registry": True,
            "plan_delta_and_nested_registry_artifacts_revalidated_at_consumption": True,
        },
        "zero_model_transport": {
            "provider_client_surface_exposed": False,
            "client_construction_count": 0,
            "structured_output_bind_count": 0,
            "invoke_count": 0,
            "provider_call_attempted": False,
            "runtime_policy_and_nested_authority_matrix_revalidated": True,
            "durable_event_type": "ZeroModelTransportAuditEvent",
            "typed_audit_port_required": True,
        },
        "immutable_A02_offline_replay": {
            "source_state": "start_failed",
            "input_projection": "parsed_payload_only_raw_response_omitted",
            "model_calls": 0,
            "network_calls": 0,
            "provider_calls": 0,
            "invalid_payload_result": "typed_feedback_not_host_crash",
            "host_source_record_revalidated_at_consumption": True,
        },
        "implementation_boundary": {
            "model_calls": False,
            "network_calls": False,
            "redis": False,
            "backend_or_queue": False,
            "A03_creation": False,
            "evidence_promotion": False,
            "s2_write": False,
            "provider_client_surface": False,
        },
    }
    if any(contract.get(name) != expected for name, expected in exact_zero_model_sections.items()):
        raise CanonicalV1_2Error("runtime_contract_zero_model_boundary_invalid")
    predecessors = contract.get("immutable_predecessors")
    if not isinstance(predecessors, list) or len(predecessors) != 2:
        raise CanonicalV1_2Error("runtime_contract_predecessor_set_invalid")
    expected_predecessors = {
        "configs/research/fin_ia_0_1_3_agent_runtime_reflection_context_continuity_contract_v1_0.json",
        "configs/research/fin_ia_0_1_3_agent_runtime_reflection_context_continuity_contract_v1_1.json",
    }
    if any(
        not isinstance(item, dict)
        or set(item) != {"ref", "schema_version", "file_sha256"}
        for item in predecessors
    ):
        raise CanonicalV1_2Error("runtime_contract_predecessor_shape_invalid")
    if {str(item.get("ref")) for item in predecessors} != expected_predecessors:
        raise CanonicalV1_2Error("runtime_contract_predecessor_set_invalid")
    expected_predecessor_schemas = {
        "configs/research/fin_ia_0_1_3_agent_runtime_reflection_context_continuity_contract_v1_0.json": (
            "fin_ia_agent_runtime_reflection_context_continuity_contract_v1_0"
        ),
        "configs/research/fin_ia_0_1_3_agent_runtime_reflection_context_continuity_contract_v1_1.json": (
            "fin_ia_agent_runtime_reflection_context_continuity_contract_v1_1"
        ),
    }
    for predecessor in predecessors:
        if predecessor.get("schema_version") != expected_predecessor_schemas[
            str(predecessor["ref"])
        ]:
            raise CanonicalV1_2Error("runtime_contract_predecessor_schema_invalid")
        predecessor_path = root / str(predecessor.get("ref") or "")
        if not predecessor_path.is_file():
            raise CanonicalV1_2Error("runtime_contract_predecessor_missing")
        if _file_sha256(predecessor_path) != predecessor.get("file_sha256"):
            raise CanonicalV1_2Error("runtime_contract_predecessor_digest_drift")
    return contract


def create_agent_session_v1_2(**fields: Any) -> AgentSessionV1_2:
    body = {"schema_version": "fin_ia_agent_session_v1_2", **fields}
    return _build(AgentSessionV1_2, "session_digest", body)


def create_research_run(**fields: Any) -> ResearchRun:
    body = {"schema_version": "fin_ia_research_run_v1_2", **fields}
    return _build(ResearchRun, "run_digest", body)


def create_run_invocation(**fields: Any) -> RunInvocation:
    body = {"schema_version": "fin_ia_run_invocation_v1_2", **fields}
    return _build(RunInvocation, "invocation_digest", body)


def create_action_attempt(**fields: Any) -> ActionAttempt:
    body = {"schema_version": "fin_ia_action_attempt_v1_2", **fields}
    return _build(ActionAttempt, "action_attempt_digest", body)


def create_recovery_disposition(**fields: Any) -> RecoveryDisposition:
    body = {"schema_version": "fin_ia_recovery_disposition_v1_2", **fields}
    return _build(RecoveryDisposition, "recovery_disposition_digest", body)


def create_required_material_ref_sources(**fields: Any) -> RequiredMaterialRefSources:
    body = {"schema_version": "fin_ia_required_material_ref_sources_v1_2", **fields}
    return _build(RequiredMaterialRefSources, "source_material_digest", body)


def create_current_context_material_snapshot_v1_2(
    **fields: Any,
) -> CurrentContextMaterialSnapshotV1_2:
    if "notebook_refs" in fields:
        raise CanonicalV1_2Error(
            "current_context_material_notebook_refs_are_runtime_derived"
        )
    body = {
        "schema_version": "fin_ia_current_context_material_snapshot_v1_2",
        "issued_by": "host_current_context_material_resolver",
        **fields,
    }
    for name in _CURRENT_CONTEXT_MATERIAL_TUPLE_FIELDS:
        body[name] = tuple(sorted(set(body.get(name, ()))))
    body["notebook_refs"] = _derive_context_material_notebook_refs(body)
    return _build(
        CurrentContextMaterialSnapshotV1_2,
        "material_snapshot_digest",
        body,
    )


def _resolve_current_context_material_snapshot(
    *,
    run: ResearchRun,
    material_resolver: CurrentContextMaterialResolver,
) -> CurrentContextMaterialSnapshotV1_2:
    try:
        snapshot = material_resolver.resolve_current_snapshot(
            session_id=run.session_id,
            run_id=run.run_id,
        )
    except CanonicalV1_2Error:
        raise
    except Exception as exc:
        raise CanonicalV1_2Error("current_context_material_resolver_failed") from exc
    if snapshot is None:
        raise CanonicalV1_2Error("current_context_material_snapshot_missing")
    snapshot = _revalidate_boundary_model(
        snapshot,
        CurrentContextMaterialSnapshotV1_2,
        "current_context_material_snapshot_invalid",
    )
    if snapshot.session_id != run.session_id or snapshot.run_id != run.run_id:
        raise CanonicalV1_2Error("current_context_material_snapshot_identity_mismatch")
    if (
        snapshot.accepted_plan_ref != run.current_plan_ref
        or snapshot.accepted_plan_digest != run.current_plan_digest
    ):
        raise CanonicalV1_2Error("current_context_material_snapshot_plan_stale")
    return snapshot


def _derive_required_material_ref_sources_from_snapshot(
    snapshot: CurrentContextMaterialSnapshotV1_2,
) -> RequiredMaterialRefSources:
    ledger = snapshot.canonical_event_ledger
    return create_required_material_ref_sources(
        accepted_plan_refs=(snapshot.accepted_plan_ref,),
        event_ledger_refs=(
            f"event-ledger://{snapshot.session_id}/{ledger.canonical_tip_digest}",
        ),
        notebook_refs=snapshot.notebook_refs,
        open_finding_refs=snapshot.open_finding_refs,
    )


def derive_required_material_ref_sources_v1_2(
    *,
    run: ResearchRun,
    material_resolver: CurrentContextMaterialResolver,
) -> RequiredMaterialRefSources:
    """Resolve checkpoint roots from the host-owned current material closure."""

    run = _revalidate_boundary_model(run, ResearchRun, "checkpoint_research_run_invalid")
    snapshot = _resolve_current_context_material_snapshot(
        run=run,
        material_resolver=material_resolver,
    )
    return _derive_required_material_ref_sources_from_snapshot(snapshot)


_CALLER_FORBIDDEN_CHECKPOINT_FIELDS = frozenset(
    {
        "schema_version",
        "checkpoint_digest",
        "session_id",
        "session_digest",
        "run_id",
        "research_run_digest",
        "run_invocation_id",
        "run_invocation_digest",
        "session_event_sequence",
        "last_event_digest",
        "canonical_event_ledger_snapshot_digest",
        "current_material_snapshot_digest",
        "notebook_revision",
        "objective_digest",
        "accepted_plan_ref",
        "accepted_plan_digest",
        "research_graph_digest",
        "runtime_policy_digest",
        "data_snapshot_digest",
        "material_ref_sources",
        "required_material_refs",
        "coverage_state_refs",
        "minimum_route_obligation_refs",
        "accepted_evidence_refs",
        "numeric_fact_refs",
        "claim_ledger_refs",
        "calculation_receipt_refs",
        "disclosure_receipt_refs",
        "skill_consumption_receipt_refs",
        "open_gap_refs",
        "unresolved_feedback_refs",
        "counterevidence_refs",
        "open_question_refs",
        "unresolved_verifier_finding_refs",
        "pending_intervention_refs",
        "authority_refs",
        "active_stop_decision_ref",
        "budget_state_ref",
        "context_projection_ref",
        "langgraph_checkpoint_ref",
    }
)


def _latest_started_invocation_id(
    events: Sequence[CanonicalSessionEventV1_2],
    *,
    run_id: str,
) -> str | None:
    started = tuple(
        event
        for event in events
        if event.run_id == run_id and event.event_type == "run_invocation_started"
    )
    return started[-1].run_invocation_id if started else None


def create_context_checkpoint_v1_2(
    *,
    session: AgentSessionV1_2,
    run: ResearchRun,
    invocation: RunInvocation,
    material_resolver: CurrentContextMaterialResolver,
    **fields: Any,
) -> ContextCheckpointV1_2:
    forbidden = _CALLER_FORBIDDEN_CHECKPOINT_FIELDS.intersection(fields)
    if forbidden:
        raise CanonicalV1_2Error("context_checkpoint_caller_authority_fields_forbidden")
    session = _revalidate_boundary_model(
        session,
        AgentSessionV1_2,
        "context_checkpoint_session_invalid",
    )
    run = _revalidate_boundary_model(
        run,
        ResearchRun,
        "context_checkpoint_research_run_invalid",
    )
    invocation = _revalidate_boundary_model(
        invocation,
        RunInvocation,
        "context_checkpoint_run_invocation_invalid",
    )
    if run.session_id != session.session_id:
        raise CanonicalV1_2Error("context_checkpoint_research_run_session_stale")
    if invocation.session_id != session.session_id or invocation.run_id != run.run_id:
        raise CanonicalV1_2Error("context_checkpoint_run_invocation_stale")
    snapshot = _resolve_current_context_material_snapshot(
        run=run,
        material_resolver=material_resolver,
    )
    ledger = snapshot.canonical_event_ledger
    canonical = validate_session_event_sequence(
        ledger.events,
        expected_session_id=session.session_id,
    )
    if _latest_started_invocation_id(canonical, run_id=run.run_id) != invocation.invocation_id:
        raise CanonicalV1_2Error("context_checkpoint_run_invocation_not_current")
    sources = _derive_required_material_ref_sources_from_snapshot(snapshot)
    body = {
        "schema_version": "fin_ia_context_checkpoint_v1_2",
        **fields,
        "session_id": session.session_id,
        "session_digest": session.session_digest,
        "run_id": run.run_id,
        "research_run_digest": run.run_digest,
        "run_invocation_id": invocation.invocation_id,
        "run_invocation_digest": invocation.invocation_digest,
        "session_event_sequence": len(canonical),
        "last_event_digest": canonical[-1].event_digest,
        "canonical_event_ledger_snapshot_digest": ledger.ledger_snapshot_digest,
        "current_material_snapshot_digest": snapshot.material_snapshot_digest,
        "notebook_revision": snapshot.notebook_revision,
        "objective_digest": session.objective_digest,
        "accepted_plan_ref": snapshot.accepted_plan_ref,
        "accepted_plan_digest": snapshot.accepted_plan_digest,
        "research_graph_digest": snapshot.research_graph_digest,
        "runtime_policy_digest": session.runtime_policy_digest,
        "data_snapshot_digest": session.data_snapshot_digest,
        "material_ref_sources": sources,
        "required_material_refs": sources.derive_required_refs(),
        "coverage_state_refs": snapshot.coverage_state_refs,
        "minimum_route_obligation_refs": snapshot.minimum_route_obligation_refs,
        "accepted_evidence_refs": snapshot.accepted_evidence_refs,
        "numeric_fact_refs": snapshot.numeric_fact_refs,
        "claim_ledger_refs": snapshot.claim_ledger_refs,
        "calculation_receipt_refs": snapshot.calculation_receipt_refs,
        "disclosure_receipt_refs": snapshot.disclosure_receipt_refs,
        "skill_consumption_receipt_refs": snapshot.skill_consumption_receipt_refs,
        "open_gap_refs": snapshot.open_gap_refs,
        "unresolved_feedback_refs": snapshot.unresolved_feedback_refs,
        "counterevidence_refs": snapshot.counterevidence_refs,
        "open_question_refs": snapshot.open_question_refs,
        "unresolved_verifier_finding_refs": snapshot.open_finding_refs,
        "pending_intervention_refs": snapshot.pending_intervention_refs,
        "authority_refs": snapshot.authority_refs,
        "active_stop_decision_ref": snapshot.active_stop_decision_ref,
        "budget_state_ref": snapshot.budget_state_ref,
        "context_projection_ref": snapshot.context_projection_ref,
        "langgraph_checkpoint_ref": snapshot.langgraph_checkpoint_ref,
    }
    return _build(ContextCheckpointV1_2, "checkpoint_digest", body)


def create_artifact_acl_grant(**fields: Any) -> ArtifactAclGrant:
    body = {"schema_version": "fin_ia_artifact_acl_grant_v1_2", **fields}
    body["allowed_principal_refs"] = tuple(
        sorted(set(body.get("allowed_principal_refs", ())))
    )
    body["authorization_basis_refs"] = tuple(
        sorted(set(body.get("authorization_basis_refs", ())))
    )
    return _build(ArtifactAclGrant, "grant_digest", body)


def create_canonical_event_ledger_snapshot(**fields: Any) -> CanonicalEventLedgerSnapshot:
    body = {
        "schema_version": "fin_ia_canonical_event_ledger_snapshot_v1_2",
        "issued_by": "host_canonical_event_repository",
        **fields,
    }
    return _build(CanonicalEventLedgerSnapshot, "ledger_snapshot_digest", body)


def _resolve_current_run_event_acl_snapshot(
    *,
    session_id: str,
    run_id: str,
    projection_policy_digest: str,
    acl_resolver: RunEventAclResolver,
) -> RunEventAclSnapshot:
    """Fetch and boundary-check the host's current request-scoped snapshot."""

    try:
        snapshot = acl_resolver.resolve_current_snapshot(
            session_id=session_id,
            run_id=run_id,
        )
    except CanonicalV1_2Error:
        raise
    except Exception as exc:
        raise CanonicalV1_2Error("run_event_acl_resolver_failed") from exc
    if not isinstance(snapshot, RunEventAclSnapshot):
        raise CanonicalV1_2Error("run_event_acl_resolver_snapshot_required")
    snapshot = _revalidate_boundary_model(
        snapshot,
        RunEventAclSnapshot,
        "run_event_acl_resolver_snapshot_invalid",
    )
    if (
        snapshot.session_id != session_id
        or snapshot.run_id != run_id
        or snapshot.projection_policy_digest != projection_policy_digest
    ):
        raise CanonicalV1_2Error("run_event_acl_snapshot_boundary_mismatch")
    return snapshot


def _derive_run_event_authorization_view(
    *,
    authorization_view_id: str,
    session_id: str,
    run_id: str,
    projection_policy_digest: str,
    acl_snapshot: RunEventAclSnapshot,
    requested_ref_ids: Sequence[str],
) -> RunEventAuthorizationView:
    """Derive one view from a snapshot already obtained by the host resolver."""

    acl_snapshot = _revalidate_boundary_model(
        acl_snapshot,
        RunEventAclSnapshot,
        "run_event_acl_snapshot_invalid",
    )
    if (
        acl_snapshot.session_id != session_id
        or acl_snapshot.run_id != run_id
        or acl_snapshot.projection_policy_digest != projection_policy_digest
    ):
        raise CanonicalV1_2Error("run_event_acl_snapshot_boundary_mismatch")
    requested = tuple(sorted(set(requested_ref_ids)))
    grant_index = {grant.ref_id: grant for grant in acl_snapshot.grants}
    unauthorized = tuple(
        ref
        for ref in requested
        if ref not in grant_index
        or acl_snapshot.principal_ref not in grant_index[ref].allowed_principal_refs
    )
    if unauthorized:
        raise CanonicalV1_2Error("run_event_acl_ref_not_authorized")
    basis_refs = tuple(sorted({
        basis_ref
        for ref in requested
        for basis_ref in grant_index[ref].authorization_basis_refs
    }))
    if not basis_refs:
        # Even an empty visible projection must be based on the host ACL snapshot.
        basis_refs = (f"acl-snapshot://sha256/{acl_snapshot.acl_snapshot_digest}",)
    body = {
        "schema_version": "fin_ia_run_event_authorization_view_v1_2",
        "authorization_view_id": authorization_view_id,
        "principal_ref": acl_snapshot.principal_ref,
        "session_id": session_id,
        "run_id": run_id,
        "projection_policy_digest": projection_policy_digest,
        "acl_snapshot_digest": acl_snapshot.acl_snapshot_digest,
        "authorization_basis_refs": basis_refs,
        "visible_ref_ids": requested,
    }
    return _build(
        RunEventAuthorizationView,
        "authorization_view_digest",
        body,
    )


def resolve_run_event_authorization_view(
    *,
    authorization_view_id: str,
    session_id: str,
    run_id: str,
    projection_policy_digest: str,
    acl_resolver: RunEventAclResolver,
    requested_ref_ids: Sequence[str],
) -> RunEventAuthorizationView:
    """Resolve visibility through the host; callers cannot submit snapshots."""

    snapshot = _resolve_current_run_event_acl_snapshot(
        session_id=session_id,
        run_id=run_id,
        projection_policy_digest=projection_policy_digest,
        acl_resolver=acl_resolver,
    )
    return _derive_run_event_authorization_view(
        authorization_view_id=authorization_view_id,
        session_id=session_id,
        run_id=run_id,
        projection_policy_digest=projection_policy_digest,
        acl_snapshot=snapshot,
        requested_ref_ids=requested_ref_ids,
    )


def validate_run_event_authorization_view(
    authorization_view: RunEventAuthorizationView,
    *,
    acl_resolver: RunEventAclResolver,
) -> RunEventAuthorizationView:
    """Re-resolve the current ACL state and reject stale or self-signed views."""

    authorization_view = _revalidate_boundary_model(
        authorization_view,
        RunEventAuthorizationView,
        "run_event_authorization_view_invalid",
    )
    snapshot = _resolve_current_run_event_acl_snapshot(
        session_id=authorization_view.session_id,
        run_id=authorization_view.run_id,
        projection_policy_digest=authorization_view.projection_policy_digest,
        acl_resolver=acl_resolver,
    )
    if snapshot.acl_snapshot_digest != authorization_view.acl_snapshot_digest:
        raise CanonicalV1_2Error("run_event_authorization_view_snapshot_stale")
    if snapshot.principal_ref != authorization_view.principal_ref:
        raise CanonicalV1_2Error("run_event_authorization_view_principal_stale")
    expected = _derive_run_event_authorization_view(
        authorization_view_id=authorization_view.authorization_view_id,
        session_id=authorization_view.session_id,
        run_id=authorization_view.run_id,
        projection_policy_digest=authorization_view.projection_policy_digest,
        acl_snapshot=snapshot,
        requested_ref_ids=authorization_view.visible_ref_ids,
    )
    if authorization_view != expected:
        raise CanonicalV1_2Error("run_event_authorization_view_not_resolver_derived")
    return authorization_view


def append_session_event_v1_2(
    events: Sequence[CanonicalSessionEventV1_2],
    *,
    session_id: str,
    event_type: LegacyEventType | NewEventType,
    actor_id: str,
    occurred_at: datetime,
    run_id: str | None = None,
    run_invocation_id: str | None = None,
    action_attempt_id: str | None = None,
    input_refs: tuple[str, ...] = (),
    output_refs: tuple[str, ...] = (),
    feedback_refs: tuple[str, ...] = (),
    legacy_source_event_id: str | None = None,
    legacy_source_event_digest: str | None = None,
) -> CanonicalSessionEventV1_2:
    current = validate_session_event_sequence(events, expected_session_id=session_id)
    sequence = len(current) + 1
    identity = {
        "session_id": session_id,
        "session_sequence": sequence,
        "event_type": event_type,
        "run_id": run_id,
        "run_invocation_id": run_invocation_id,
        "action_attempt_id": action_attempt_id,
        "actor_id": actor_id,
        "occurred_at": occurred_at,
    }
    body = {
        "schema_version": "fin_ia_canonical_session_event_v1_2",
        "event_id": "EVENT::V1_2::" + canonical_json_sha256(identity)[:24].upper(),
        **identity,
        "input_refs": input_refs,
        "output_refs": output_refs,
        "feedback_refs": feedback_refs,
        "prior_event_digest": current[-1].event_digest if current else None,
        "legacy_source_event_id": legacy_source_event_id,
        "legacy_source_event_digest": legacy_source_event_digest,
    }
    return _build(CanonicalSessionEventV1_2, "event_digest", body)


def validate_session_event_sequence(
    events: Sequence[CanonicalSessionEventV1_2],
    *,
    expected_session_id: str | None = None,
) -> tuple[CanonicalSessionEventV1_2, ...]:
    normalized = tuple(events)
    revalidated: list[CanonicalSessionEventV1_2] = []
    event_ids: set[str] = set()
    terminal_actions: set[str] = set()
    prior: str | None = None
    inferred_session_id: str | None = expected_session_id
    for sequence, event in enumerate(normalized, start=1):
        if not isinstance(event, CanonicalSessionEventV1_2):
            raise CanonicalV1_2Error("canonical_session_event_model_required")
        event = _revalidate_boundary_model(
            event,
            CanonicalSessionEventV1_2,
            "canonical_session_event_invalid",
        )
        try:
            _assert_own_digest(
                event,
                "event_digest",
                "canonical_session_event_digest_invalid",
            )
        except ValueError as exc:
            raise CanonicalV1_2Error("canonical_session_event_digest_invalid") from exc
        if event.session_sequence != sequence:
            raise CanonicalV1_2Error("canonical_session_event_sequence_invalid")
        if inferred_session_id is None:
            inferred_session_id = event.session_id
        if event.session_id != inferred_session_id:
            raise CanonicalV1_2Error("canonical_session_event_session_mismatch")
        if event.prior_event_digest != prior:
            raise CanonicalV1_2Error("canonical_session_event_prior_digest_invalid")
        if event.event_id in event_ids:
            raise CanonicalV1_2Error("canonical_session_event_id_duplicate")
        event_ids.add(event.event_id)
        if event.event_type in {
            "tool_execution_completed", "tool_execution_failed",
            "provider_attempt_completed", "provider_attempt_failed", "action_terminal",
        }:
            if event.action_attempt_id is None:
                raise CanonicalV1_2Error("canonical_terminal_event_action_attempt_missing")
            if event.action_attempt_id in terminal_actions:
                raise CanonicalV1_2Error("canonical_action_attempt_terminal_duplicate")
            terminal_actions.add(event.action_attempt_id)
        prior = event.event_digest
        revalidated.append(event)
    return tuple(revalidated)


def project_run_events(
    events: Sequence[CanonicalSessionEventV1_2],
    *,
    run_id: str,
    projection_policy_digest: str,
    authorization_view: RunEventAuthorizationView,
    acl_resolver: RunEventAclResolver,
) -> tuple[RunEventProjection, ...]:
    authorization_view = _revalidate_boundary_model(
        authorization_view,
        RunEventAuthorizationView,
        "run_event_authorization_view_invalid",
    )
    if authorization_view.run_id != run_id:
        raise CanonicalV1_2Error("run_event_authorization_view_run_mismatch")
    if authorization_view.projection_policy_digest != projection_policy_digest:
        raise CanonicalV1_2Error("run_event_authorization_view_policy_stale")
    validate_run_event_authorization_view(
        authorization_view,
        acl_resolver=acl_resolver,
    )
    canonical = validate_session_event_sequence(
        events,
        expected_session_id=authorization_view.session_id,
    )
    visible_refs = set(authorization_view.visible_ref_ids)
    selected = sorted(
        (event for event in canonical if event.run_id == run_id),
        key=lambda item: (item.session_sequence, item.event_id),
    )
    projected: list[RunEventProjection] = []
    for projection_sequence, event in enumerate(selected, start=1):
        body = {
            "schema_version": "fin_ia_run_event_projection_v1_2",
            "session_id": event.session_id,
            "run_id": run_id,
            "projection_sequence": projection_sequence,
            "source_session_sequence": event.session_sequence,
            "source_event_id": event.event_id,
            "source_event_digest": event.event_digest,
            "event_type": event.event_type,
            "occurred_at": event.occurred_at,
            "visible_input_refs": tuple(ref for ref in event.input_refs if ref in visible_refs),
            "visible_output_refs": tuple(ref for ref in event.output_refs if ref in visible_refs),
            "visible_feedback_refs": tuple(
                ref for ref in event.feedback_refs if ref in visible_refs
            ),
            "projection_policy_digest": projection_policy_digest,
            "authorization_view_digest": authorization_view.authorization_view_digest,
        }
        projected.append(_build(RunEventProjection, "projection_digest", body))
    return tuple(projected)


def validate_run_event_projection(
    projections: Sequence[RunEventProjection],
    events: Sequence[CanonicalSessionEventV1_2],
    *,
    run_id: str,
    expected_projection_policy_digest: str,
    expected_authorization_view: RunEventAuthorizationView,
    acl_resolver: RunEventAclResolver,
) -> tuple[RunEventProjection, ...]:
    expected_authorization_view = _revalidate_boundary_model(
        expected_authorization_view,
        RunEventAuthorizationView,
        "run_event_authorization_view_invalid",
    )
    actual = tuple(
        _revalidate_boundary_model(
            item,
            RunEventProjection,
            "run_event_projection_invalid",
        )
        for item in projections
    )
    if any(item.projection_policy_digest != expected_projection_policy_digest for item in actual):
        raise CanonicalV1_2Error("run_event_projection_policy_stale")
    if any(
        item.authorization_view_digest
        != expected_authorization_view.authorization_view_digest
        for item in actual
    ):
        raise CanonicalV1_2Error("run_event_projection_authorization_view_stale")
    expected = project_run_events(
        events,
        run_id=run_id,
        projection_policy_digest=expected_projection_policy_digest,
        authorization_view=expected_authorization_view,
        acl_resolver=acl_resolver,
    )
    if actual != expected:
        raise CanonicalV1_2Error("run_event_projection_source_or_sequence_stale")
    return actual


def validate_context_checkpoint_v1_2(
    checkpoint: ContextCheckpointV1_2,
    *,
    session: AgentSessionV1_2,
    run: ResearchRun,
    invocation: RunInvocation,
    material_resolver: CurrentContextMaterialResolver,
) -> ContextCheckpointV1_2:
    checkpoint = _revalidate_boundary_model(
        checkpoint,
        ContextCheckpointV1_2,
        "context_checkpoint_invalid",
    )
    session = _revalidate_boundary_model(
        session,
        AgentSessionV1_2,
        "context_checkpoint_session_invalid",
    )
    run = _revalidate_boundary_model(
        run,
        ResearchRun,
        "context_checkpoint_research_run_invalid",
    )
    invocation = _revalidate_boundary_model(
        invocation,
        RunInvocation,
        "context_checkpoint_run_invocation_invalid",
    )
    if run.session_id != session.session_id:
        raise CanonicalV1_2Error("context_checkpoint_research_run_session_stale")
    snapshot = _resolve_current_context_material_snapshot(
        run=run,
        material_resolver=material_resolver,
    )
    ledger = snapshot.canonical_event_ledger
    canonical = validate_session_event_sequence(
        ledger.events,
        expected_session_id=session.session_id,
    )
    if checkpoint.session_id != session.session_id or checkpoint.session_digest != session.session_digest:
        raise CanonicalV1_2Error("context_checkpoint_session_stale")
    if checkpoint.run_id != run.run_id or checkpoint.research_run_digest != run.run_digest:
        raise CanonicalV1_2Error("context_checkpoint_research_run_stale")
    if (
        invocation.session_id != session.session_id
        or invocation.run_id != run.run_id
        or checkpoint.run_invocation_id != invocation.invocation_id
        or checkpoint.run_invocation_digest != invocation.invocation_digest
    ):
        raise CanonicalV1_2Error("context_checkpoint_run_invocation_stale")
    if _latest_started_invocation_id(canonical, run_id=run.run_id) != invocation.invocation_id:
        raise CanonicalV1_2Error("context_checkpoint_run_invocation_not_current")
    if checkpoint.objective_digest != session.objective_digest:
        raise CanonicalV1_2Error("context_checkpoint_objective_stale")
    if (
        checkpoint.accepted_plan_ref != run.current_plan_ref
        or checkpoint.accepted_plan_digest != run.current_plan_digest
    ):
        raise CanonicalV1_2Error("context_checkpoint_plan_stale")
    if checkpoint.research_graph_digest != snapshot.research_graph_digest:
        raise CanonicalV1_2Error("context_checkpoint_research_graph_stale")
    if checkpoint.runtime_policy_digest != session.runtime_policy_digest:
        raise CanonicalV1_2Error("context_checkpoint_runtime_policy_stale")
    if checkpoint.data_snapshot_digest != session.data_snapshot_digest:
        raise CanonicalV1_2Error("context_checkpoint_data_snapshot_stale")
    if checkpoint.session_event_sequence != len(canonical):
        raise CanonicalV1_2Error("context_checkpoint_not_latest")
    if canonical[-1].event_digest != checkpoint.last_event_digest:
        raise CanonicalV1_2Error("context_checkpoint_event_digest_stale")
    if (
        checkpoint.canonical_event_ledger_snapshot_digest
        != ledger.ledger_snapshot_digest
    ):
        raise CanonicalV1_2Error("context_checkpoint_event_ledger_snapshot_stale")
    if checkpoint.current_material_snapshot_digest != snapshot.material_snapshot_digest:
        raise CanonicalV1_2Error("context_checkpoint_material_snapshot_stale")
    if checkpoint.notebook_revision != snapshot.notebook_revision:
        raise CanonicalV1_2Error("context_checkpoint_notebook_revision_stale")
    if checkpoint.coverage_state_refs != snapshot.coverage_state_refs:
        raise CanonicalV1_2Error("context_checkpoint_coverage_state_stale")
    if (
        checkpoint.minimum_route_obligation_refs
        != snapshot.minimum_route_obligation_refs
    ):
        raise CanonicalV1_2Error("context_checkpoint_minimum_route_stale")
    if checkpoint.unresolved_verifier_finding_refs != snapshot.open_finding_refs:
        raise CanonicalV1_2Error("context_checkpoint_open_findings_stale")
    checkpoint_snapshot_fields = {
        "accepted_evidence_refs": "accepted_evidence_refs",
        "numeric_fact_refs": "numeric_fact_refs",
        "claim_ledger_refs": "claim_ledger_refs",
        "calculation_receipt_refs": "calculation_receipt_refs",
        "disclosure_receipt_refs": "disclosure_receipt_refs",
        "skill_consumption_receipt_refs": "skill_consumption_receipt_refs",
        "open_gap_refs": "open_gap_refs",
        "unresolved_feedback_refs": "unresolved_feedback_refs",
        "counterevidence_refs": "counterevidence_refs",
        "open_question_refs": "open_question_refs",
        "pending_intervention_refs": "pending_intervention_refs",
        "authority_refs": "authority_refs",
        "active_stop_decision_ref": "active_stop_decision_ref",
        "budget_state_ref": "budget_state_ref",
        "context_projection_ref": "context_projection_ref",
        "langgraph_checkpoint_ref": "langgraph_checkpoint_ref",
    }
    for checkpoint_field, snapshot_field in checkpoint_snapshot_fields.items():
        if getattr(checkpoint, checkpoint_field) != getattr(snapshot, snapshot_field):
            raise CanonicalV1_2Error(
                f"context_checkpoint_current_material_state_stale:{checkpoint_field}"
            )
    expected_material_ref_sources = _derive_required_material_ref_sources_from_snapshot(
        snapshot
    )
    if checkpoint.material_ref_sources != expected_material_ref_sources:
        raise CanonicalV1_2Error("context_checkpoint_material_sources_stale")
    return checkpoint


def validate_recovery_disposition_v1_2(
    disposition: RecoveryDisposition,
    *,
    ambiguous_action: ActionAttempt,
    run: ResearchRun,
    source_invocation: RunInvocation,
    next_invocation: RunInvocation | None = None,
    replacement_action: ActionAttempt | None = None,
) -> RecoveryDisposition:
    """Validate a recovery decision against the immutable objects it names."""

    disposition = _revalidate_boundary_model(
        disposition,
        RecoveryDisposition,
        "recovery_disposition_invalid",
    )
    ambiguous_action = _revalidate_boundary_model(
        ambiguous_action,
        ActionAttempt,
        "recovery_source_action_invalid",
    )
    run = _revalidate_boundary_model(
        run,
        ResearchRun,
        "recovery_research_run_invalid",
    )
    source_invocation = _revalidate_boundary_model(
        source_invocation,
        RunInvocation,
        "recovery_source_invocation_invalid",
    )
    if next_invocation is not None:
        next_invocation = _revalidate_boundary_model(
            next_invocation,
            RunInvocation,
            "recovery_next_invocation_invalid",
        )
    if replacement_action is not None:
        replacement_action = _revalidate_boundary_model(
            replacement_action,
            ActionAttempt,
            "recovery_replacement_action_invalid",
        )

    if (
        run.run_id != disposition.run_id
        or run.session_id != disposition.session_id
        or run.run_digest != disposition.research_run_digest
        or run.status != "RECOVERY_REQUIRED"
    ):
        raise CanonicalV1_2Error("recovery_research_run_state_invalid")

    if (
        ambiguous_action.state != "TERMINAL"
        or ambiguous_action.outcome != "AMBIGUOUS_AFTER_DISPATCH"
        or not ambiguous_action.was_dispatched
        or ambiguous_action.receipt_ref is not None
    ):
        raise CanonicalV1_2Error("recovery_source_action_not_ambiguous")
    if (
        disposition.session_id != ambiguous_action.session_id
        or disposition.run_id != ambiguous_action.run_id
        or disposition.ambiguous_action_attempt_id
        != ambiguous_action.action_attempt_id
        or disposition.ambiguous_action_attempt_digest
        != ambiguous_action.action_attempt_digest
    ):
        raise CanonicalV1_2Error("recovery_source_action_stale")
    if (
        source_invocation.session_id != disposition.session_id
        or source_invocation.run_id != disposition.run_id
        or source_invocation.invocation_id
        != disposition.source_run_invocation_id
        or source_invocation.invocation_digest
        != disposition.source_run_invocation_digest
        or ambiguous_action.run_invocation_id != source_invocation.invocation_id
    ):
        raise CanonicalV1_2Error("recovery_source_invocation_stale")
    if disposition.potentially_duplicate_cost != ambiguous_action.potentially_chargeable:
        raise CanonicalV1_2Error("recovery_duplicate_cost_state_mismatch")
    if (
        ambiguous_action.terminal_at is None
        or disposition.created_at < ambiguous_action.terminal_at
        or (
            source_invocation.finished_at is not None
            and disposition.created_at < source_invocation.finished_at
        )
    ):
        raise CanonicalV1_2Error("recovery_disposition_time_invalid")

    continues = disposition.next_run_invocation_id is not None
    if continues != (next_invocation is not None):
        raise CanonicalV1_2Error("recovery_next_invocation_object_mismatch")
    if next_invocation is not None:
        if (
            next_invocation.invocation_id != disposition.next_run_invocation_id
            or next_invocation.invocation_digest
            != disposition.next_run_invocation_digest
            or next_invocation.invocation_id == source_invocation.invocation_id
            or next_invocation.session_id != disposition.session_id
            or next_invocation.run_id != disposition.run_id
            or next_invocation.invocation_kind != "RECOVERY"
            or next_invocation.ordinal != source_invocation.ordinal + 1
            or next_invocation.started_at < disposition.created_at
        ):
            raise CanonicalV1_2Error("recovery_next_invocation_invalid")

    retries = disposition.replacement_action_attempt_id is not None
    if retries != (replacement_action is not None):
        raise CanonicalV1_2Error("recovery_replacement_action_object_mismatch")
    if replacement_action is not None:
        if next_invocation is None or (
            replacement_action.action_attempt_id
            != disposition.replacement_action_attempt_id
            or replacement_action.action_attempt_digest
            != disposition.replacement_action_attempt_digest
            or replacement_action.action_attempt_id
            == ambiguous_action.action_attempt_id
            or replacement_action.parent_action_attempt_id
            != ambiguous_action.action_attempt_id
            or replacement_action.session_id != disposition.session_id
            or replacement_action.run_id != disposition.run_id
            or replacement_action.run_invocation_id != next_invocation.invocation_id
            or replacement_action.created_at < disposition.created_at
            or replacement_action.created_at < next_invocation.started_at
        ):
            raise CanonicalV1_2Error("recovery_replacement_action_invalid")
    return disposition


def _validate_legacy_agent_session_payload(
    legacy_session: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate the exact v1.0 AgentSession bytes before adapting them."""

    from .session import canonical_digest as legacy_canonical_digest
    from .session import validate_runtime_artifact

    raw = dict(legacy_session)
    expected_fields = {
        "session_id", "run_id", "case_id", "case_version", "as_of_date",
        "objective_ref", "active_plan_ref", "event_log_ref",
        "current_checkpoint_ref", "status", "created_at", "updated_at",
        "session_digest",
    }
    if set(raw) != expected_fields:
        raise CanonicalV1_2Error("legacy_session_field_set_invalid")
    supplied_digest = raw.get("session_digest")
    unsigned = {key: value for key, value in raw.items() if key != "session_digest"}
    if supplied_digest != legacy_canonical_digest(unsigned):
        raise CanonicalV1_2Error("legacy_session_digest_invalid")
    return validate_runtime_artifact("AgentSession", raw)


def _adapt_validated_legacy_agent_session_v1_0(
    current: Mapping[str, Any],
    *,
    objective_digest: str,
    data_snapshot_ref: str,
    data_snapshot_digest: str,
    runtime_policy_ref: str,
    runtime_policy_digest: str,
    authority_refs: tuple[str, ...],
    active_plan_digest: str,
) -> AgentSessionV1_2:
    status = {
        "active": "ACTIVE", "paused": "PAUSED", "stopped": "STOPPED", "completed": "COMPLETED"
    }[current["status"]]
    return create_agent_session_v1_2(
        session_id=current["session_id"],
        thread_id=current["session_id"],
        case_id=current["case_id"],
        case_version=current["case_version"],
        as_of_date=date.fromisoformat(current["as_of_date"]),
        objective_ref=current["objective_ref"],
        objective_digest=objective_digest,
        data_snapshot_ref=data_snapshot_ref,
        data_snapshot_digest=data_snapshot_digest,
        runtime_policy_ref=runtime_policy_ref,
        runtime_policy_digest=runtime_policy_digest,
        authority_refs=authority_refs,
        active_plan_ref=current["active_plan_ref"],
        active_plan_digest=active_plan_digest,
        status=status,
        created_at=_parse_aware(current["created_at"], "legacy_session_created_at_invalid"),
        updated_at=_parse_aware(current["updated_at"], "legacy_session_updated_at_invalid"),
    )


def adapt_legacy_agent_session_v1_0(
    legacy_session: Mapping[str, Any],
    *,
    objective_digest: str,
    data_snapshot_ref: str,
    data_snapshot_digest: str,
    runtime_policy_ref: str,
    runtime_policy_digest: str,
    authority_refs: tuple[str, ...],
    active_plan_digest: str,
) -> AgentSessionV1_2:
    """Project only the v1.0 session envelope; this is not a run/attempt import."""

    current = _validate_legacy_agent_session_payload(legacy_session)
    if (
        current["session_id"] == LEGACY_A02_CANONICAL_SESSION_ID
        or current["run_id"] in {
        LEGACY_A02_RUN_ID,
        LEGACY_A02_PAID_FULL_CHAIN_EXECUTION_ID,
        }
    ):
        raise CanonicalV1_2Error("legacy_a02_requires_exact_identity_mapper")
    if current["run_id"] in {
        LEGACY_A01_RUN_ID,
        LEGACY_A01_PAID_FULL_CHAIN_EXECUTION_ID,
    }:
        raise CanonicalV1_2Error("legacy_a01_exact_source_bundle_required")
    return _adapt_validated_legacy_agent_session_v1_0(
        current,
        objective_digest=objective_digest,
        data_snapshot_ref=data_snapshot_ref,
        data_snapshot_digest=data_snapshot_digest,
        runtime_policy_ref=runtime_policy_ref,
        runtime_policy_digest=runtime_policy_digest,
        authority_refs=authority_refs,
        active_plan_digest=active_plan_digest,
    )


def adapt_legacy_v1_1_event_log(
    legacy_events: Sequence[Mapping[str, Any]],
    *,
    research_run: ResearchRun,
    run_invocation: RunInvocation,
    legacy_action_attempt_bindings: Mapping[str, ActionAttempt],
) -> tuple[CanonicalSessionEventV1_2, ...]:
    """Project a single-invocation v1.1 log through verified identity objects."""

    from .session import validate_event_log

    try:
        research_run = ResearchRun.model_validate(
            research_run.model_dump(mode="python")
        )
        run_invocation = RunInvocation.model_validate(
            run_invocation.model_dump(mode="python")
        )
    except ValueError as exc:
        raise CanonicalV1_2Error("legacy_event_identity_object_invalid") from exc
    _assert_own_digest(research_run, "run_digest", "research_run_digest_invalid")
    _assert_own_digest(
        run_invocation,
        "invocation_digest",
        "run_invocation_digest_invalid",
    )
    if (
        run_invocation.session_id != research_run.session_id
        or run_invocation.run_id != research_run.run_id
    ):
        raise CanonicalV1_2Error("legacy_event_invocation_binding_invalid")
    if (
        research_run.session_id == LEGACY_A02_CANONICAL_SESSION_ID
        or research_run.run_id in {
        LEGACY_A02_RUN_ID,
        LEGACY_A02_PAID_FULL_CHAIN_EXECUTION_ID,
        }
    ):
        raise CanonicalV1_2Error("legacy_a02_event_log_requires_exact_identity_mapper")
    if research_run.run_id in {
        LEGACY_A01_RUN_ID,
        LEGACY_A01_PAID_FULL_CHAIN_EXECUTION_ID,
    }:
        raise CanonicalV1_2Error("legacy_a01_event_log_requires_exact_source_bundle")
    old = validate_event_log(
        legacy_events,
        expected_session_id=research_run.session_id,
    )
    if any(event["event_type"] == "session_resumed" for event in old):
        raise CanonicalV1_2Error("legacy_event_multi_invocation_binding_required")
    normalized_bindings: dict[str, ActionAttempt] = {}
    for legacy_attempt_id, action in legacy_action_attempt_bindings.items():
        if not isinstance(legacy_attempt_id, str) or not legacy_attempt_id:
            raise CanonicalV1_2Error("legacy_event_action_binding_id_invalid")
        try:
            action = ActionAttempt.model_validate(action.model_dump(mode="python"))
        except ValueError as exc:
            raise CanonicalV1_2Error("legacy_event_action_binding_object_invalid") from exc
        if (
            action.session_id != research_run.session_id
            or action.run_id != research_run.run_id
            or action.run_invocation_id != run_invocation.invocation_id
        ):
            raise CanonicalV1_2Error("legacy_event_action_binding_invalid")
        normalized_bindings[legacy_attempt_id] = action
    provider_events = {
        "provider_attempt_requested",
        "provider_attempt_completed",
        "provider_attempt_failed",
    }
    tool_events = {
        "tool_execution_requested",
        "tool_execution_completed",
        "tool_execution_failed",
    }
    requested_events = {"provider_attempt_requested", "tool_execution_requested"}
    completed_events = {"provider_attempt_completed", "tool_execution_completed"}
    failed_events = {"provider_attempt_failed", "tool_execution_failed"}
    new: list[CanonicalSessionEventV1_2] = []
    consumed_binding_ids: set[str] = set()
    for event in old:
        legacy_attempt_id = event.get("attempt_id")
        action = (
            normalized_bindings.get(legacy_attempt_id)
            if legacy_attempt_id is not None
            else None
        )
        if legacy_attempt_id is not None and action is None:
            raise CanonicalV1_2Error("legacy_event_action_binding_missing")
        if action is not None:
            consumed_binding_ids.add(str(legacy_attempt_id))
            event_type = event["event_type"]
            if event_type not in provider_events | tool_events:
                raise CanonicalV1_2Error("legacy_event_action_family_unsupported")
            if event["actor_id"] != action.actor_id:
                raise CanonicalV1_2Error("legacy_event_action_actor_mismatch")
            if event_type in provider_events and action.action_kind != "MODEL":
                raise CanonicalV1_2Error("legacy_provider_event_action_kind_mismatch")
            if event_type in tool_events and action.action_kind != "TOOL":
                raise CanonicalV1_2Error("legacy_tool_event_action_kind_mismatch")
            occurred_at = _parse_aware(
                event["occurred_at"],
                "legacy_event_occurred_at_invalid",
            )
            if event_type in requested_events and occurred_at != action.created_at:
                raise CanonicalV1_2Error("legacy_event_action_start_time_mismatch")
            if event_type in completed_events | failed_events:
                if action.state != "TERMINAL" or action.terminal_at != occurred_at:
                    raise CanonicalV1_2Error("legacy_event_action_terminal_time_mismatch")
                expected_receipt_kind = (
                    "SUCCESS" if event_type in completed_events else "FAILURE"
                )
                if action.receipt_kind != expected_receipt_kind:
                    raise CanonicalV1_2Error("legacy_event_action_receipt_kind_mismatch")
        new.append(append_session_event_v1_2(
            new,
            session_id=event["session_id"],
            event_type=event["event_type"],
            actor_id=event["actor_id"],
            occurred_at=_parse_aware(event["occurred_at"], "legacy_event_occurred_at_invalid"),
            run_id=research_run.run_id,
            run_invocation_id=run_invocation.invocation_id,
            action_attempt_id=(action.action_attempt_id if action is not None else None),
            input_refs=tuple(event["input_refs"]),
            output_refs=tuple(event["output_refs"]),
            feedback_refs=tuple(event["feedback_refs"]),
            legacy_source_event_id=event["event_id"],
            legacy_source_event_digest=event["event_digest"],
        ))
    if consumed_binding_ids != set(normalized_bindings):
        raise CanonicalV1_2Error("legacy_event_action_binding_unused")
    return tuple(new)


def load_legacy_a02_source_bundle(
    repo_root: str | Path | None = None,
) -> LegacyA02SourceBundle:
    """Load the one tracked, content-addressed A02 identity source bundle."""

    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[3]
    path = root / LEGACY_A02_SOURCE_BUNDLE_REF
    try:
        return LegacyA02SourceBundle.model_validate_json(
            path.read_text(encoding="utf-8")
        )
    except (OSError, ValueError) as exc:
        raise CanonicalV1_2Error("legacy_a02_exact_source_bundle_invalid") from exc


def map_legacy_a02_identity(
    source_bundle: LegacyA02SourceBundle,
    *,
    imported_at: datetime,
) -> LegacyA02IdentityMapping:
    """Map the exact A02 artifacts; migration time never replaces history time."""

    try:
        source_bundle = LegacyA02SourceBundle.model_validate(
            source_bundle.model_dump(mode="python")
        )
    except ValueError as exc:
        raise CanonicalV1_2Error("legacy_a02_exact_source_bundle_invalid") from exc
    if source_bundle.source_bundle_digest != LEGACY_A02_SOURCE_BUNDLE_DIGEST:
        raise CanonicalV1_2Error("legacy_a02_exact_source_bundle_required")
    imported_at = _aware(
        imported_at,
        "legacy_a02_import_timestamp_not_timezone_aware",
    )
    run_started_at = _parse_aware(
        source_bundle.run_started_at,
        "legacy_a02_run_started_at_invalid",
    )
    run_failed_at = _parse_aware(
        source_bundle.run_failed_at,
        "legacy_a02_run_failed_at_invalid",
    )
    if imported_at < run_failed_at:
        raise CanonicalV1_2Error("legacy_a02_import_precedes_historical_failure")
    session = create_agent_session_v1_2(
        session_id=source_bundle.canonical_session_id,
        thread_id=source_bundle.canonical_session_id,
        case_id=source_bundle.case_id,
        case_version=source_bundle.case_version,
        as_of_date=date.fromisoformat(source_bundle.research_as_of),
        objective_ref=source_bundle.objective_ref,
        objective_digest=source_bundle.objective_digest,
        data_snapshot_ref=source_bundle.data_snapshot_ref,
        data_snapshot_digest=source_bundle.data_snapshot_digest,
        runtime_policy_ref=LEGACY_A02_READ_ONLY_RUNTIME_POLICY_REF,
        runtime_policy_digest=LEGACY_A02_READ_ONLY_RUNTIME_POLICY_DIGEST,
        authority_refs=(LEGACY_A02_READ_ONLY_AUTHORITY_REF,),
        active_plan_ref=source_bundle.base_plan_ref,
        active_plan_digest=source_bundle.base_plan_digest,
        status="STOPPED",
        created_at=run_started_at,
        updated_at=run_failed_at,
    )
    run = create_research_run(
        run_id=source_bundle.legacy_run_id,
        session_id=session.session_id,
        parent_run_id=None,
        origin_kind="LEGACY_A02_IMPORT",
        legacy_paid_full_chain_execution_label="A02",
        status="START_FAILED",
        base_plan_ref=session.active_plan_ref,
        base_plan_digest=session.active_plan_digest,
        current_plan_ref=session.active_plan_ref,
        current_plan_digest=session.active_plan_digest,
        last_session_sequence=0,
        created_at=run_started_at,
        terminal_at=run_failed_at,
    )
    invocation_id = LEGACY_A02_INITIAL_INVOCATION_ID
    invocation = create_run_invocation(
        invocation_id=invocation_id,
        session_id=session.session_id,
        run_id=run.run_id,
        ordinal=1,
        invocation_kind="START",
        status="FAILED",
        trigger_ref="legacy://paid-full-chain/A02/start",
        lease_ref=None,
        started_at=run_started_at,
        finished_at=run_failed_at,
    )
    action = create_action_attempt(
        action_attempt_id=source_bundle.planner_action_attempt_id,
        session_id=session.session_id,
        run_id=run.run_id,
        run_invocation_id=invocation.invocation_id,
        actor_id=source_bundle.planner_actor_id,
        action_kind="MODEL",
        action_name="planner",
        request_ref=source_bundle.planner_request_ref,
        request_digest=source_bundle.planner_request_digest,
        state="TERMINAL",
        outcome="APPLIED",
        was_dispatched=True,
        potentially_chargeable=True,
        receipt_kind="FAILURE",
        receipt_ref=source_bundle.planner_failure_receipt_ref,
        receipt_digest=source_bundle.planner_failure_receipt_digest,
        failure_code=source_bundle.failure_code,
        parent_action_attempt_id=None,
        created_at=_parse_aware(
            source_bundle.planner_started_at,
            "legacy_a02_planner_started_at_invalid",
        ),
        terminal_at=_parse_aware(
            source_bundle.planner_finished_at,
            "legacy_a02_planner_finished_at_invalid",
        ),
    )
    body = {
        "schema_version": "fin_ia_legacy_a02_identity_mapping_v1_2",
        "legacy_paid_full_chain_execution_id": LEGACY_A02_PAID_FULL_CHAIN_EXECUTION_ID,
        "source_bundle": source_bundle,
        "agent_session": session,
        "research_run": run,
        "initial_run_invocation": invocation,
        "planner_action_attempt": action,
        "imported_at": imported_at,
    }
    return _build(LegacyA02IdentityMapping, "mapping_digest", body)


__all__ = [
    "ActionAttempt", "AgentSessionV1_2", "ArtifactAclGrant",
    "CanonicalEventLedgerSnapshot", "CanonicalSessionEventV1_2",
    "CanonicalV1_2Error", "ContextCheckpointV1_2", "CONTRACT_V1_2_REF",
    "CurrentContextMaterialResolver", "CurrentContextMaterialSnapshotV1_2",
    "LEGACY_A01_PAID_FULL_CHAIN_EXECUTION_ID", "LEGACY_A01_RUN_ID",
    "LEGACY_A02_CANONICAL_SESSION_ID", "LEGACY_A02_INITIAL_INVOCATION_ID",
    "LEGACY_A02_PAID_FULL_CHAIN_EXECUTION_ID",
    "LEGACY_A02_PLANNER_ACTION_ATTEMPT_ID",
    "LEGACY_A02_RUN_ID",
    "LEGACY_A02_READ_ONLY_AUTHORITY_REF",
    "LEGACY_A02_READ_ONLY_RUNTIME_POLICY_DIGEST",
    "LEGACY_A02_READ_ONLY_RUNTIME_POLICY_REF",
    "LEGACY_A02_SOURCE_BUNDLE_DIGEST", "LEGACY_A02_SOURCE_BUNDLE_REF",
    "LegacyA02IdentityMapping", "LegacyA02SourceBundle",
    "RecoveryDisposition", "RequiredMaterialRefSources", "ResearchRun",
    "RunEventAclResolver", "RunEventAclSnapshot", "RunEventAuthorizationView",
    "RunEventProjection", "RunInvocation",
    "StrictFrozenModel", "adapt_legacy_agent_session_v1_0",
    "adapt_legacy_v1_1_event_log", "append_session_event_v1_2", "canonical_json",
    "canonical_json_sha256", "create_action_attempt", "create_agent_session_v1_2",
    "create_artifact_acl_grant",
    "create_canonical_event_ledger_snapshot",
    "create_context_checkpoint_v1_2",
    "create_current_context_material_snapshot_v1_2",
    "create_recovery_disposition",
    "create_required_material_ref_sources", "create_research_run",
    "create_run_invocation", "load_legacy_a02_source_bundle",
    "load_runtime_contract_v1_2", "map_legacy_a02_identity",
    "derive_required_material_ref_sources_v1_2", "project_run_events",
    "resolve_run_event_authorization_view",
    "validate_context_checkpoint_v1_2",
    "validate_recovery_disposition_v1_2",
    "validate_run_event_authorization_view", "validate_run_event_projection",
    "validate_session_event_sequence",
]
