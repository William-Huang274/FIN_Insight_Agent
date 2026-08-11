"""Package-external admission and authoritative one-shot receipt ledger for M2-A1.

The executable package declares only that execution is externally gated.  A
reviewer admission and a receipt in this separate append-only SQLite ledger
are the mutable authority objects.  They never change package bytes.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import stat
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from pydantic import field_validator, model_validator

from .models import StrictModel, canonical_digest


SHA256_LENGTH = 64
V2_3_PACKAGE_SCHEMA = "finsight_point01_m2_a1_execution_ready_audit_package_manifest_v2_3"
V2_4_PACKAGE_SCHEMA = "finsight_point01_m2_a1_execution_ready_audit_package_manifest_v2_4"
V2_5_PACKAGE_SCHEMA = "finsight_point01_m2_a1_execution_ready_audit_package_manifest_v2_5"
V2_6_PACKAGE_SCHEMA = "finsight_point01_m2_a1_execution_ready_audit_package_manifest_v2_6"
V2_7_PACKAGE_SCHEMA = "finsight_point01_m2_a1_execution_ready_audit_package_manifest_v2_7"
V2_8_PACKAGE_SCHEMA = "finsight_point01_m2_a1_execution_ready_audit_package_manifest_v2_8"
V2_9_PACKAGE_SCHEMA = "finsight_point01_m2_a1_execution_ready_audit_package_manifest_v2_9"
V2_10_PACKAGE_SCHEMA = "finsight_point01_m2_a1_execution_ready_audit_package_manifest_v2_10"
V2_3_ADMISSION_SCHEMA = "finsight_point01_m2_a1_external_package_admission_v2_3"
V2_4_ADMISSION_SCHEMA = "finsight_point01_m2_a1_external_package_admission_v2_4"
V2_5_ADMISSION_SCHEMA = "finsight_point01_m2_a1_external_package_admission_v2_5"
V2_6_ADMISSION_SCHEMA = "finsight_point01_m2_a1_external_package_admission_v2_6"
V2_7_ADMISSION_SCHEMA = "finsight_point01_m2_a1_external_package_admission_v2_7"
V2_8_ADMISSION_SCHEMA = "finsight_point01_m2_a1_external_package_admission_v2_8"
V2_9_ADMISSION_SCHEMA = "finsight_point01_m2_a1_external_package_admission_v2_9"
V2_10_ADMISSION_SCHEMA = "finsight_point01_m2_a1_external_package_admission_v2_10"
V2_3_RECEIPT_SCHEMA = "finsight_point01_m2_a1_single_use_execution_receipt_v2_3"
V2_4_RECEIPT_SCHEMA = "finsight_point01_m2_a1_single_use_execution_receipt_v2_4"
V2_5_RECEIPT_SCHEMA = "finsight_point01_m2_a1_single_use_execution_receipt_v2_5"
V2_6_RECEIPT_SCHEMA = "finsight_point01_m2_a1_single_use_execution_receipt_v2_6"
V2_7_RECEIPT_SCHEMA = "finsight_point01_m2_a1_single_use_execution_receipt_v2_7"
V2_8_RECEIPT_SCHEMA = "finsight_point01_m2_a1_single_use_execution_receipt_v2_8"
V2_9_RECEIPT_SCHEMA = "finsight_point01_m2_a1_single_use_execution_receipt_v2_9"
V2_10_RECEIPT_SCHEMA = "finsight_point01_m2_a1_single_use_execution_receipt_v2_10"
HUMAN_JIT_WINDOW_APPROVAL_SCHEMA = "finsight_point01_m2_a1_human_jit_window_approval_v1"
PRODUCTION_HUMAN_JIT_WINDOW_APPROVAL_V2_10_SCHEMA = "finsight_point01_m2_a1_production_human_jit_window_approval_v2_10"
PRODUCTION_REVIEWER_DECISION_RECEIPT_V2_10_SCHEMA = "finsight_point01_m2_a1_production_reviewer_decision_receipt_v2_10"
SYNTHETIC_NONHUMAN_AUTHORITY_V2_10_SCHEMA = "finsight_point01_m2_a1_synthetic_nonhuman_authority_v2_10"
_SUPPORTED_ADMISSION_SCHEMAS = frozenset({V2_3_ADMISSION_SCHEMA, V2_4_ADMISSION_SCHEMA, V2_5_ADMISSION_SCHEMA, V2_6_ADMISSION_SCHEMA, V2_7_ADMISSION_SCHEMA, V2_8_ADMISSION_SCHEMA, V2_9_ADMISSION_SCHEMA, V2_10_ADMISSION_SCHEMA})
_SUPPORTED_RECEIPT_SCHEMAS = frozenset({V2_3_RECEIPT_SCHEMA, V2_4_RECEIPT_SCHEMA, V2_5_RECEIPT_SCHEMA, V2_6_RECEIPT_SCHEMA, V2_7_RECEIPT_SCHEMA, V2_8_RECEIPT_SCHEMA, V2_9_RECEIPT_SCHEMA, V2_10_RECEIPT_SCHEMA})

_EVENT_APPEND_ONLY_TRIGGER_DDL = {
    "point01_m2_a1_execution_receipt_events_no_update": """
        create trigger point01_m2_a1_execution_receipt_events_no_update
        before update on point01_m2_a1_execution_receipt_events
        begin
            select raise(abort, 'point01_m2_a1_execution_receipt_events_append_only_update_denied');
        end;
    """,
    "point01_m2_a1_execution_receipt_events_no_delete": """
        create trigger point01_m2_a1_execution_receipt_events_no_delete
        before delete on point01_m2_a1_execution_receipt_events
        begin
            select raise(abort, 'point01_m2_a1_execution_receipt_events_append_only_delete_denied');
        end;
    """,
}


def _normalise_event_trigger_ddl(value: str) -> str:
    """Canonicalise only SQLite's terminal-semicolon storage difference.

    SQLite drops the outer DDL semicolon from ``sqlite_master``.  No semantic
    token is stripped: a ``WHEN`` clause, changed action/table, or abort body
    still changes the normalized contract and blocks the ledger before use.
    """

    return re.sub(r"\s+", " ", value.strip().rstrip(";").strip()).lower()


_NORMALISED_EVENT_APPEND_ONLY_TRIGGER_DDL = {
    name: _normalise_event_trigger_ddl(ddl)
    for name, ddl in _EVENT_APPEND_ONLY_TRIGGER_DDL.items()
}


def event_append_only_trigger_ddl_digest() -> str:
    """Return the reviewed canonical DDL contract for the SQLite event log.

    This deliberately describes application-controlled SQLite enforcement.  It
    prevents accidental or application-level UPDATE/DELETE paths, while the
    payload digest protects readers against an offline tamper copy.  It does
    not claim to defeat a party with arbitrary filesystem/database access.
    """

    return canonical_digest(_NORMALISED_EVENT_APPEND_ONLY_TRIGGER_DDL)


def _requires_human_approval_lineage(schema_version: str) -> bool:
    """Return whether a durable authority schema requires approval lineage.

    v2.7 introduced the field and v2.8 makes the event source-of-truth
    verification mandatory.  Keeping the discriminator centralized prevents a
    later lifecycle branch from silently treating a v2.8 object as legacy.
    """

    return schema_version in {V2_7_ADMISSION_SCHEMA, V2_8_ADMISSION_SCHEMA, V2_9_ADMISSION_SCHEMA, V2_10_ADMISSION_SCHEMA, V2_7_RECEIPT_SCHEMA, V2_8_RECEIPT_SCHEMA, V2_9_RECEIPT_SCHEMA, V2_10_RECEIPT_SCHEMA}


class M2A1ReceiptAuthorityError(RuntimeError):
    pass


class M2A1ExecutionPreflightError(RuntimeError):
    """The exact execution package cannot safely cross into any write path."""


def _is_sha256(value: str) -> bool:
    return len(value) == SHA256_LENGTH and all(character in "0123456789abcdef" for character in value)


def _utc_json(value: datetime) -> str:
    """Return the exact JSON representation used by model_dump(mode="json")."""

    if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
        raise M2A1ReceiptAuthorityError("timezone_aware_utc_required")
    return value.isoformat().replace("+00:00", "Z")


class M2A1ExternalPackageAdmission(StrictModel):
    schema_version: str = V2_3_ADMISSION_SCHEMA
    admission_ref: str
    admission_id: str
    admission_version: int
    reviewer_identity: str
    decision: str
    package_ref: str
    executable_package_digest: str
    scope: str
    authority_boundary: str
    execution_staging_namespace_id: str
    execution_mode: str = "external_admission_gated"
    expires_at: datetime
    # v2.7 makes the exact external human decision durable authority lineage.
    # Keeping it optional preserves the canonical bytes of v2.3-v2.6 history.
    human_approval_digest: str | None = None
    admission_digest: str

    @field_validator("executable_package_digest", "admission_digest", "human_approval_digest")
    @classmethod
    def require_sha256(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not _is_sha256(value):
            raise ValueError("sha256_required")
        return value

    @model_validator(mode="after")
    def require_human_approval_lineage(self) -> "M2A1ExternalPackageAdmission":
        if _requires_human_approval_lineage(self.schema_version) and not self.human_approval_digest:
            raise ValueError("human_approval_digest_required")
        return self

    @field_validator("schema_version")
    @classmethod
    def require_supported_schema(cls, value: str) -> str:
        if value not in _SUPPORTED_ADMISSION_SCHEMAS:
            raise ValueError("unsupported_admission_schema")
        return value

    @field_validator("expires_at")
    @classmethod
    def require_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
            raise ValueError("timezone_aware_utc_required")
        return value

    @classmethod
    def create(
        cls,
        *,
        admission_ref: str,
        admission_id: str,
        admission_version: int,
        reviewer_identity: str,
        package_ref: str,
        executable_package_digest: str,
        scope: str,
        authority_boundary: str,
        execution_staging_namespace_id: str,
        expires_at: datetime,
        schema_version: str = V2_3_ADMISSION_SCHEMA,
        human_approval_digest: str | None = None,
    ) -> "M2A1ExternalPackageAdmission":
        payload = {
            "schema_version": schema_version,
            "admission_ref": admission_ref,
            "admission_id": admission_id,
            "admission_version": admission_version,
            "reviewer_identity": reviewer_identity,
            "decision": "admitted",
            "package_ref": package_ref,
            "executable_package_digest": executable_package_digest,
            "scope": scope,
            "authority_boundary": authority_boundary,
            "execution_staging_namespace_id": execution_staging_namespace_id,
            "execution_mode": "external_admission_gated",
            "expires_at": _utc_json(expires_at),
        }
        if human_approval_digest is not None:
            payload["human_approval_digest"] = human_approval_digest
        return cls(**payload, admission_digest=canonical_digest(payload))

    def verify_digest(self) -> bool:
        payload = self.model_dump(mode="json", exclude={"admission_digest"}, exclude_none=True)
        return self.admission_digest == canonical_digest(payload)


class M2A1ExecutionReceipt(StrictModel):
    schema_version: str = V2_3_RECEIPT_SCHEMA
    receipt_id: str
    receipt_version: int
    approval_id: str
    package_ref: str
    executable_package_digest: str
    scope: str
    admission_digest: str
    nonce_sha256: str
    expires_at: datetime
    reviewer_identity: str
    execution_staging_namespace_id: str
    scenario_id: str
    state: str
    single_use: bool = True
    human_approval_digest: str | None = None
    receipt_digest: str

    @field_validator("executable_package_digest", "admission_digest", "nonce_sha256", "receipt_digest", "human_approval_digest")
    @classmethod
    def require_sha256(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not _is_sha256(value):
            raise ValueError("sha256_required")
        return value

    @model_validator(mode="after")
    def require_human_approval_lineage(self) -> "M2A1ExecutionReceipt":
        if _requires_human_approval_lineage(self.schema_version) and not self.human_approval_digest:
            raise ValueError("human_approval_digest_required")
        return self

    @field_validator("schema_version")
    @classmethod
    def require_supported_schema(cls, value: str) -> str:
        if value not in _SUPPORTED_RECEIPT_SCHEMAS:
            raise ValueError("unsupported_receipt_schema")
        return value

    @field_validator("expires_at")
    @classmethod
    def require_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
            raise ValueError("timezone_aware_utc_required")
        return value

    @classmethod
    def create(
        cls,
        *,
        receipt_id: str,
        receipt_version: int,
        approval_id: str,
        package_ref: str,
        executable_package_digest: str,
        scope: str,
        admission_digest: str,
        nonce_sha256: str,
        expires_at: datetime,
        reviewer_identity: str,
        execution_staging_namespace_id: str,
        scenario_id: str,
        state: str = "active_unconsumed",
        schema_version: str = V2_3_RECEIPT_SCHEMA,
        human_approval_digest: str | None = None,
    ) -> "M2A1ExecutionReceipt":
        payload = {
            "schema_version": schema_version,
            "receipt_id": receipt_id,
            "receipt_version": receipt_version,
            "approval_id": approval_id,
            "package_ref": package_ref,
            "executable_package_digest": executable_package_digest,
            "scope": scope,
            "admission_digest": admission_digest,
            "nonce_sha256": nonce_sha256,
            "expires_at": _utc_json(expires_at),
            "reviewer_identity": reviewer_identity,
            "execution_staging_namespace_id": execution_staging_namespace_id,
            "scenario_id": scenario_id,
            "state": state,
            "single_use": True,
        }
        if human_approval_digest is not None:
            payload["human_approval_digest"] = human_approval_digest
        return cls(**payload, receipt_digest=canonical_digest(payload))

    def verify_digest(self) -> bool:
        payload = self.model_dump(mode="json", exclude={"receipt_digest"}, exclude_none=True)
        return self.receipt_digest == canonical_digest(payload)


class HumanJITWindowApproval(StrictModel):
    """Package-external human decision that may activate one frozen JIT window.

    The package only ships an unresolved field template.  A reviewer must
    create this object after package freeze; it carries no raw nonce or
    credentials and its digest is independent of package bytes.
    """

    schema_version: str = HUMAN_JIT_WINDOW_APPROVAL_SCHEMA
    approval_ref: str
    approval_id: str
    approval_version: int
    reviewer_identity: str
    decision: str
    issued_at: datetime
    expires_at: datetime
    package_ref: str
    package_digest: str
    package_gate_digest: str
    plan_digest: str
    plan_gate_digest: str
    blueprint_digest: str
    blueprint_gate_digest: str
    phase_a_digests: Mapping[str, str]
    incident_digest: str
    expired_terminal_digest: str
    scenario_id: str
    input_ref: str
    mutation: str
    authority_boundary: str
    execution_staging_namespace_id: str
    admission_ttl_minutes: int
    receipt_ttl_minutes: int
    single_use: bool
    no_retry_replay_or_renewal: bool
    approval_digest: str

    @field_validator("package_digest", "package_gate_digest", "plan_digest", "plan_gate_digest", "blueprint_digest", "blueprint_gate_digest", "incident_digest", "expired_terminal_digest", "approval_digest")
    @classmethod
    def require_sha256(cls, value: str) -> str:
        if not _is_sha256(value):
            raise ValueError("sha256_required")
        return value

    @field_validator("schema_version")
    @classmethod
    def require_schema(cls, value: str) -> str:
        if value != HUMAN_JIT_WINDOW_APPROVAL_SCHEMA:
            raise ValueError("human_jit_window_approval_schema_invalid")
        return value

    @field_validator("issued_at", "expires_at")
    @classmethod
    def require_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
            raise ValueError("timezone_aware_utc_required")
        return value

    @classmethod
    def create(cls, **payload: Any) -> "HumanJITWindowApproval":
        if "approval_digest" in payload:
            raise M2A1ReceiptAuthorityError("human_jit_window_approval_digest_caller_supplied")
        payload = {"schema_version": HUMAN_JIT_WINDOW_APPROVAL_SCHEMA, **payload}
        # Digest exactly the JSON representation that ``verify_digest`` later
        # recomputes.  Hashing raw ``datetime`` objects would make a correctly
        # formed external approval look tampered after model validation.
        for field in ("issued_at", "expires_at"):
            value = payload.get(field)
            if isinstance(value, datetime):
                payload[field] = _utc_json(value)
        return cls(**payload, approval_digest=canonical_digest(payload))

    def verify_digest(self) -> bool:
        return self.approval_digest == canonical_digest(self.model_dump(mode="json", exclude={"approval_digest"}))


class ProductionReviewerDecisionReceiptV2_10(StrictModel):
    """Immutable package-external total-reviewer decision provenance."""

    schema_version: str = PRODUCTION_REVIEWER_DECISION_RECEIPT_V2_10_SCHEMA
    receipt_id: str
    receipt_version: int
    actor_id: str
    reviewer_identity: str
    decision: str
    decision_source: str
    package_ref: str
    package_digest: str
    package_gate_digest: str
    plan_digest: str
    plan_gate_digest: str
    blueprint_digest: str
    blueprint_gate_digest: str
    scenario_id: str
    scope: str
    authority_boundary: str
    execution_staging_namespace_id: str
    issued_at: datetime
    expires_at: datetime
    receipt_digest: str

    @field_validator("package_digest", "package_gate_digest", "plan_digest", "plan_gate_digest", "blueprint_digest", "blueprint_gate_digest", "receipt_digest")
    @classmethod
    def require_sha256(cls, value: str) -> str:
        if not _is_sha256(value):
            raise ValueError("sha256_required")
        return value

    @field_validator("schema_version")
    @classmethod
    def require_schema(cls, value: str) -> str:
        if value != PRODUCTION_REVIEWER_DECISION_RECEIPT_V2_10_SCHEMA:
            raise ValueError("production_reviewer_decision_receipt_schema_invalid")
        return value

    @field_validator("issued_at", "expires_at")
    @classmethod
    def require_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
            raise ValueError("timezone_aware_utc_required")
        return value

    @model_validator(mode="after")
    def require_total_reviewer(self) -> "ProductionReviewerDecisionReceiptV2_10":
        if self.actor_id != "003" or self.reviewer_identity != "william/003/total_reviewer" or self.decision != "approved_single_jit_window" or self.decision_source != "total_reviewer_recorded_decision":
            raise ValueError("production_reviewer_decision_receipt_provenance_invalid")
        if not self.receipt_id:
            raise ValueError("production_reviewer_decision_receipt_id_required")
        return self

    @classmethod
    def create(cls, **payload: Any) -> "ProductionReviewerDecisionReceiptV2_10":
        if "receipt_digest" in payload:
            raise M2A1ReceiptAuthorityError("production_reviewer_decision_receipt_digest_caller_supplied")
        payload = {"schema_version": PRODUCTION_REVIEWER_DECISION_RECEIPT_V2_10_SCHEMA, **payload}
        for field in ("issued_at", "expires_at"):
            if isinstance(payload.get(field), datetime):
                payload[field] = _utc_json(payload[field])
        return cls(**payload, receipt_digest=canonical_digest(payload))

    def verify_digest(self) -> bool:
        return self.receipt_digest == canonical_digest(self.model_dump(mode="json", exclude={"receipt_digest"}))


class ProductionHumanJITWindowApprovalV2_10(StrictModel):
    """The only authority shape accepted by the v2.10 production entry.

    Earlier ``HumanJITWindowApproval`` records remain historical evidence.  A
    separately versioned model prevents a test fixture from becoming valid
    merely by using the same reviewer-looking string.  The provenance fields
    are intentionally part of ``approval_digest`` and travel into the durable
    admission/receipt/event lineage as the digest, never as mutable runtime
    metadata.
    """

    schema_version: str = PRODUCTION_HUMAN_JIT_WINDOW_APPROVAL_V2_10_SCHEMA
    authority_class: str
    approval_ref: str
    approval_id: str
    approval_version: int
    reviewer_identity: str
    decision: str
    decision_source: str
    actor_id: str
    review_receipt_id: str
    review_receipt_digest: str
    issued_at: datetime
    expires_at: datetime
    package_ref: str
    package_digest: str
    package_gate_digest: str
    plan_digest: str
    plan_gate_digest: str
    blueprint_digest: str
    blueprint_gate_digest: str
    phase_a_digests: Mapping[str, str]
    incident_digest: str
    expired_terminal_digest: str
    scenario_id: str
    input_ref: str
    mutation: str
    authority_boundary: str
    execution_staging_namespace_id: str
    admission_ttl_minutes: int
    receipt_ttl_minutes: int
    single_use: bool
    no_retry_replay_or_renewal: bool
    approval_digest: str

    @field_validator(
        "package_digest", "package_gate_digest", "plan_digest", "plan_gate_digest",
        "blueprint_digest", "blueprint_gate_digest", "incident_digest",
        "expired_terminal_digest", "review_receipt_digest", "approval_digest",
    )
    @classmethod
    def require_sha256(cls, value: str) -> str:
        if not _is_sha256(value):
            raise ValueError("sha256_required")
        return value

    @field_validator("schema_version")
    @classmethod
    def require_schema(cls, value: str) -> str:
        if value != PRODUCTION_HUMAN_JIT_WINDOW_APPROVAL_V2_10_SCHEMA:
            raise ValueError("production_human_jit_window_approval_schema_invalid")
        return value

    @field_validator("issued_at", "expires_at")
    @classmethod
    def require_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
            raise ValueError("timezone_aware_utc_required")
        return value

    @model_validator(mode="after")
    def require_production_provenance(self) -> "ProductionHumanJITWindowApprovalV2_10":
        if self.authority_class != "production_human_total_reviewer":
            raise ValueError("production_authority_class_required")
        if self.approval_ref.startswith("test_") or "synthetic" in self.approval_ref or "nonhuman" in self.approval_ref:
            raise ValueError("test_or_synthetic_approval_ref_forbidden")
        if self.reviewer_identity != "william/003/total_reviewer" or self.actor_id != "003" or self.decision_source != "total_reviewer_recorded_decision":
            raise ValueError("production_reviewer_provenance_invalid")
        if not self.review_receipt_id:
            raise ValueError("review_receipt_id_required")
        return self

    @classmethod
    def create(cls, **payload: Any) -> "ProductionHumanJITWindowApprovalV2_10":
        if "approval_digest" in payload:
            raise M2A1ReceiptAuthorityError("production_human_approval_digest_caller_supplied")
        payload = {
            "schema_version": PRODUCTION_HUMAN_JIT_WINDOW_APPROVAL_V2_10_SCHEMA,
            "authority_class": "production_human_total_reviewer",
            "decision_source": "total_reviewer_recorded_decision",
            **payload,
        }
        for field in ("issued_at", "expires_at"):
            if isinstance(payload.get(field), datetime):
                payload[field] = _utc_json(payload[field])
        return cls(**payload, approval_digest=canonical_digest(payload))

    def verify_digest(self) -> bool:
        return self.approval_digest == canonical_digest(self.model_dump(mode="json", exclude={"approval_digest"}))


class SyntheticNonhumanAuthorityV2_10(StrictModel):
    """Test-only authority that can never cross the production CLI boundary."""

    schema_version: str = SYNTHETIC_NONHUMAN_AUTHORITY_V2_10_SCHEMA
    authority_class: str
    fixture_id: str
    fixture_digest: str
    package_digest: str
    scenario_id: str

    @field_validator("fixture_digest", "package_digest")
    @classmethod
    def require_sha256(cls, value: str) -> str:
        if not _is_sha256(value):
            raise ValueError("sha256_required")
        return value

    @model_validator(mode="after")
    def require_fixture_class(self) -> "SyntheticNonhumanAuthorityV2_10":
        if self.schema_version != SYNTHETIC_NONHUMAN_AUTHORITY_V2_10_SCHEMA or self.authority_class != "synthetic_nonhuman_fixture":
            raise ValueError("synthetic_nonhuman_authority_required")
        return self

    @classmethod
    def create(cls, *, package_digest: str, scenario_id: str, fixture_id: str = "point01-m2-a1-v2-10-execution-proof") -> "SyntheticNonhumanAuthorityV2_10":
        payload = {
            "schema_version": SYNTHETIC_NONHUMAN_AUTHORITY_V2_10_SCHEMA,
            "authority_class": "synthetic_nonhuman_fixture",
            "fixture_id": fixture_id,
            "package_digest": package_digest,
            "scenario_id": scenario_id,
        }
        return cls(**payload, fixture_digest=canonical_digest(payload))

    def verify_digest(self) -> bool:
        return self.fixture_digest == canonical_digest(self.model_dump(mode="json", exclude={"fixture_digest"}))


@dataclass(frozen=True)
class ValidatedAuthorityContext:
    """Classified input to the shared lifecycle core, never raw JSON."""

    authority_class: str
    authority_digest: str
    reviewer_identity: str
    scenario_id: str
    source_ref: str
    production: bool

    def require_production(self) -> None:
        if not self.production or self.authority_class != "production_human_total_reviewer":
            raise M2A1ReceiptAuthorityError("production_validated_human_authority_required")


class M2A1ConsumptionGrant(StrictModel):
    """Ledger-backed proof that one exact receipt was atomically consumed.

    This object is deliberately not an authority token by itself.  Before a
    preflight may materialize runtime paths, it must be matched against the
    append-only ``CONSUMED_BEFORE_RUN`` event in the existing ledger.
    """

    schema_version: str = "finsight_point01_m2_a1_consumption_grant_v2_3"
    receipt_id: str
    consumed_receipt_digest: str
    admission_digest: str
    executable_package_digest: str
    scenario_id: str
    run_root: str
    preflight_digest: str
    human_approval_digest: str | None = None
    state: str = "consumed_before_run"
    grant_digest: str

    @field_validator("consumed_receipt_digest", "admission_digest", "executable_package_digest", "preflight_digest", "human_approval_digest", "grant_digest")
    @classmethod
    def require_sha256(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not _is_sha256(value):
            raise ValueError("sha256_required")
        return value

    @field_validator("run_root")
    @classmethod
    def require_absolute_run_root(cls, value: str) -> str:
        if not Path(value).is_absolute():
            raise ValueError("absolute_run_root_required")
        return value

    @classmethod
    def create(
        cls,
        *,
        receipt_id: str,
        consumed_receipt_digest: str,
        admission_digest: str,
        executable_package_digest: str,
        scenario_id: str,
        run_root: str,
        preflight_digest: str,
        human_approval_digest: str | None = None,
    ) -> "M2A1ConsumptionGrant":
        payload = {
            "schema_version": "finsight_point01_m2_a1_consumption_grant_v2_3",
            "receipt_id": receipt_id,
            "consumed_receipt_digest": consumed_receipt_digest,
            "admission_digest": admission_digest,
            "executable_package_digest": executable_package_digest,
            "scenario_id": scenario_id,
            "run_root": run_root,
            "preflight_digest": preflight_digest,
            "state": "consumed_before_run",
        }
        if human_approval_digest is not None:
            payload["human_approval_digest"] = human_approval_digest
        return cls(**payload, grant_digest=canonical_digest(payload))

    def verify_digest(self) -> bool:
        payload = self.model_dump(mode="json", exclude={"grant_digest"}, exclude_none=True)
        return self.grant_digest == canonical_digest(payload)


def receipt_digest(receipt: M2A1ExecutionReceipt) -> str:
    return receipt.receipt_digest


def validate_external_admission(
    admission: M2A1ExternalPackageAdmission | None,
    *,
    package_ref: str,
    executable_package_digest: str,
    scope: str,
    authority_boundary: str,
    execution_staging_namespace_id: str | None = None,
    expected_schema_version: str | None = None,
    expected_human_approval_digest: str | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    if admission is None:
        return {"status": "package_admission_required", "admission_digest": None}
    current = now or datetime.now(timezone.utc)
    errors: list[str] = []
    if not admission.verify_digest():
        errors.append("admission_digest_invalid")
    if admission.decision != "admitted":
        errors.append("admission_not_admitted")
    if admission.execution_mode != "external_admission_gated":
        errors.append("admission_execution_mode_invalid")
    if _requires_human_approval_lineage(admission.schema_version) and not admission.human_approval_digest:
        errors.append("admission_human_approval_digest_missing")
    if _requires_human_approval_lineage(admission.schema_version) and expected_human_approval_digest is None:
        errors.append("admission_human_approval_digest_required")
    if expected_human_approval_digest is not None and admission.human_approval_digest != expected_human_approval_digest:
        errors.append("admission_human_approval_digest_mismatch")
    if expected_schema_version is not None and admission.schema_version != expected_schema_version:
        # A schema-version mismatch is an authority-family failure, not a
        # generic payload discrepancy.  Surface it as the terminal type so a
        # v2.3 authority can never be mistaken for a v2.4 package admission.
        return {
            "status": "admission_schema_version_mismatch",
            "errors": ("admission_schema_version_mismatch",),
            "admission_digest": admission.admission_digest,
        }
    if admission.expires_at <= current:
        errors.append("admission_expired")
    expected = {
        "package_ref": package_ref,
        "executable_package_digest": executable_package_digest,
        "scope": scope,
        "authority_boundary": authority_boundary,
    }
    if execution_staging_namespace_id is not None:
        expected["execution_staging_namespace_id"] = execution_staging_namespace_id
    errors.extend(f"admission_{field}_mismatch" for field, value in expected.items() if getattr(admission, field) != value)
    human_error = next((error for error in errors if "human_approval_digest" in error), None)
    return {
        "status": "pass" if not errors else human_error or "package_admission_binding_mismatch",
        "errors": tuple(sorted(errors)),
        "admission_digest": admission.admission_digest,
    }


def validate_unconsumed_receipt(
    receipt: M2A1ExecutionReceipt | None,
    *,
    package_ref: str,
    executable_package_digest: str,
    scope: str,
    admission: M2A1ExternalPackageAdmission | None = None,
    authority_boundary: str = "",
    execution_staging_namespace_id: str | None = None,
    scenario_id: str | None = None,
    actual_probes_authorized: bool | None = None,
    expected_admission_schema_version: str | None = None,
    expected_receipt_schema_version: str | None = None,
    expected_human_approval_digest: str | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    """Validate receipt binding; legacy boolean cannot grant authority by itself."""

    if actual_probes_authorized is False:
        return {"status": "actual_execution_not_authorized", "receipt_digest": None}
    admission_check = validate_external_admission(
        admission,
        package_ref=package_ref,
        executable_package_digest=executable_package_digest,
        scope=scope,
        authority_boundary=authority_boundary,
        execution_staging_namespace_id=execution_staging_namespace_id,
        expected_schema_version=expected_admission_schema_version,
        expected_human_approval_digest=expected_human_approval_digest,
        now=now,
    )
    if admission_check["status"] != "pass":
        return {"status": str(admission_check["status"]), "receipt_digest": None, "errors": admission_check.get("errors", ())}
    if receipt is None:
        return {"status": "single_use_execution_receipt_required", "receipt_digest": None}
    current = now or datetime.now(timezone.utc)
    errors: list[str] = []
    if not receipt.verify_digest():
        errors.append("receipt_digest_invalid")
    if receipt.single_use is not True:
        errors.append("receipt_not_single_use")
    if expected_receipt_schema_version is not None and receipt.schema_version != expected_receipt_schema_version:
        errors.append("receipt_schema_version_mismatch")
    if _requires_human_approval_lineage(receipt.schema_version) and not receipt.human_approval_digest:
        errors.append("receipt_human_approval_digest_missing")
    if _requires_human_approval_lineage(receipt.schema_version) and expected_human_approval_digest is None:
        errors.append("receipt_human_approval_digest_required")
    if expected_human_approval_digest is not None and receipt.human_approval_digest != expected_human_approval_digest:
        errors.append("receipt_human_approval_digest_mismatch")
    if admission is not None and receipt.human_approval_digest != admission.human_approval_digest:
        errors.append("receipt_human_approval_admission_binding_mismatch")
    if receipt.state != "active_unconsumed":
        errors.append("receipt_not_active_unconsumed")
    if receipt.expires_at <= current:
        errors.append("receipt_expired")
    if receipt.expires_at > admission.expires_at:  # type: ignore[union-attr]
        errors.append("receipt_expiry_exceeds_admission")
    expected = {
        "package_ref": package_ref,
        "executable_package_digest": executable_package_digest,
        "scope": scope,
        "admission_digest": admission.admission_digest,  # type: ignore[union-attr]
        "reviewer_identity": admission.reviewer_identity,  # type: ignore[union-attr]
    }
    if execution_staging_namespace_id is not None:
        expected["execution_staging_namespace_id"] = execution_staging_namespace_id
    if scenario_id is not None:
        expected["scenario_id"] = scenario_id
    errors.extend(f"receipt_{field}_mismatch" for field, value in expected.items() if getattr(receipt, field) != value)
    human_error = next((error for error in errors if "human_approval_digest" in error), None)
    return {"status": "pass" if not errors else human_error or "receipt_binding_mismatch", "errors": tuple(sorted(errors)), "receipt_digest": receipt.receipt_digest}


def validate_human_jit_window_approval(
    approval: HumanJITWindowApproval | None,
    *,
    package: Mapping[str, Any],
    package_gate: Mapping[str, Any],
    plan: Mapping[str, Any],
    plan_gate: Mapping[str, Any],
    blueprint: Mapping[str, Any],
    blueprint_gate: Mapping[str, Any],
    now: datetime | None = None,
) -> dict[str, object]:
    """Validate the external decision before any admission or path exists."""

    if approval is None:
        return {"status": "human_jit_window_approval_required", "approval_digest": None}
    current = now or datetime.now(timezone.utc)
    if approval.schema_version != HUMAN_JIT_WINDOW_APPROVAL_SCHEMA:
        return {"status": "human_jit_window_approval_schema_mismatch", "approval_digest": approval.approval_digest}
    errors: list[str] = []
    if not approval.verify_digest():
        errors.append("approval_digest_invalid")
    if approval.decision != "approved_single_jit_window":
        errors.append("approval_decision_invalid")
    if approval.expires_at <= current or approval.issued_at > current or approval.issued_at >= approval.expires_at:
        errors.append("approval_expiry_invalid")
    expected = {
        "package_ref": package.get("package_ref"),
        "package_digest": package.get("package_digest"),
        "package_gate_digest": package_gate.get("gate_digest"),
        "plan_digest": plan.get("plan_digest"),
        "plan_gate_digest": plan_gate.get("gate_digest"),
        "blueprint_digest": blueprint.get("blueprint_digest"),
        "blueprint_gate_digest": blueprint_gate.get("gate_digest"),
        "phase_a_digests": package.get("phase_a_digests"),
        "incident_digest": package.get("incident_evidence", {}).get("incident_digest") if isinstance(package.get("incident_evidence"), Mapping) else None,
        "expired_terminal_digest": package.get("incident_evidence", {}).get("expired_terminal_digest") if isinstance(package.get("incident_evidence"), Mapping) else None,
        "scenario_id": blueprint.get("exact_binding", {}).get("scenario_id") if isinstance(blueprint.get("exact_binding"), Mapping) else None,
        "input_ref": blueprint.get("exact_binding", {}).get("input_ref") if isinstance(blueprint.get("exact_binding"), Mapping) else None,
        "mutation": blueprint.get("exact_binding", {}).get("mutation") if isinstance(blueprint.get("exact_binding"), Mapping) else None,
        "authority_boundary": package.get("authority_boundary"),
        "execution_staging_namespace_id": package.get("execution_preflight", {}).get("execution_staging_namespace_id") if isinstance(package.get("execution_preflight"), Mapping) else None,
    }
    errors.extend(f"approval_{field}_mismatch" for field, value in expected.items() if getattr(approval, field) != value)
    if approval.reviewer_identity != "william/003/total_reviewer":
        errors.append("approval_reviewer_identity_mismatch")
    if approval.admission_ttl_minutes != 30 or approval.receipt_ttl_minutes != 15:
        errors.append("approval_ttl_policy_invalid")
    if approval.single_use is not True or approval.no_retry_replay_or_renewal is not True:
        errors.append("approval_single_use_or_replay_policy_invalid")
    if approval.receipt_ttl_minutes > approval.admission_ttl_minutes:
        errors.append("approval_receipt_ttl_exceeds_admission")
    return {
        "status": "pass" if not errors else "human_jit_window_approval_binding_mismatch",
        "errors": tuple(sorted(errors)),
        "approval_digest": approval.approval_digest,
    }


def validate_production_human_jit_window_approval_v2_10(
    approval: ProductionHumanJITWindowApprovalV2_10 | None,
    *,
    reviewer_receipt: ProductionReviewerDecisionReceiptV2_10 | None,
    package: Mapping[str, Any],
    package_gate: Mapping[str, Any],
    plan: Mapping[str, Any],
    plan_gate: Mapping[str, Any],
    blueprint: Mapping[str, Any],
    blueprint_gate: Mapping[str, Any],
    now: datetime | None = None,
) -> tuple[ValidatedAuthorityContext | None, dict[str, object]]:
    """Validate only an auditable v2.10 human decision before any side effect."""

    if approval is None:
        return None, {"status": "production_human_jit_window_approval_required", "approval_digest": None}
    current = now or datetime.now(timezone.utc)
    errors: list[str] = []
    if not approval.verify_digest():
        errors.append("approval_digest_invalid")
    if approval.decision != "approved_single_jit_window":
        errors.append("approval_decision_invalid")
    if approval.expires_at <= current or approval.issued_at > current or approval.issued_at >= approval.expires_at:
        errors.append("approval_expiry_invalid")
    if approval.authority_class != "production_human_total_reviewer" or approval.decision_source != "total_reviewer_recorded_decision":
        errors.append("approval_authority_class_or_source_invalid")
    if approval.approval_ref.startswith("test_") or "synthetic" in approval.approval_ref or "nonhuman" in approval.approval_ref:
        errors.append("approval_test_or_synthetic_ref_forbidden")
    if approval.reviewer_identity != "william/003/total_reviewer" or approval.actor_id != "003" or not approval.review_receipt_id:
        errors.append("approval_reviewer_provenance_invalid")
    if reviewer_receipt is None:
        errors.append("approval_reviewer_decision_receipt_required")
    else:
        if not reviewer_receipt.verify_digest():
            errors.append("approval_reviewer_decision_receipt_digest_invalid")
        receipt_expected = {
            "receipt_id": approval.review_receipt_id,
            "receipt_digest": approval.review_receipt_digest,
            "actor_id": approval.actor_id,
            "reviewer_identity": approval.reviewer_identity,
            "decision": approval.decision,
            "decision_source": approval.decision_source,
        }
        errors.extend(f"approval_reviewer_decision_receipt_{field}_mismatch" for field, value in receipt_expected.items() if getattr(reviewer_receipt, field) != value)
    expected = {
        "package_ref": package.get("package_ref"),
        "package_digest": package.get("package_digest"),
        "package_gate_digest": package_gate.get("gate_digest"),
        "plan_digest": plan.get("plan_digest"),
        "plan_gate_digest": plan_gate.get("gate_digest"),
        "blueprint_digest": blueprint.get("blueprint_digest"),
        "blueprint_gate_digest": blueprint_gate.get("gate_digest"),
        "phase_a_digests": package.get("phase_a_digests"),
        "incident_digest": package.get("incident_evidence", {}).get("incident_digest") if isinstance(package.get("incident_evidence"), Mapping) else None,
        "expired_terminal_digest": package.get("incident_evidence", {}).get("expired_terminal_digest") if isinstance(package.get("incident_evidence"), Mapping) else None,
        "scenario_id": blueprint.get("exact_binding", {}).get("scenario_id") if isinstance(blueprint.get("exact_binding"), Mapping) else None,
        "input_ref": blueprint.get("exact_binding", {}).get("input_ref") if isinstance(blueprint.get("exact_binding"), Mapping) else None,
        "mutation": blueprint.get("exact_binding", {}).get("mutation") if isinstance(blueprint.get("exact_binding"), Mapping) else None,
        "authority_boundary": package.get("authority_boundary"),
        "execution_staging_namespace_id": package.get("execution_preflight", {}).get("execution_staging_namespace_id") if isinstance(package.get("execution_preflight"), Mapping) else None,
    }
    errors.extend(f"approval_{field}_mismatch" for field, value in expected.items() if getattr(approval, field) != value)
    if reviewer_receipt is not None:
        receipt_binding = {
            "package_ref": package.get("package_ref"),
            "package_digest": package.get("package_digest"),
            "package_gate_digest": package_gate.get("gate_digest"),
            "plan_digest": plan.get("plan_digest"),
            "plan_gate_digest": plan_gate.get("gate_digest"),
            "blueprint_digest": blueprint.get("blueprint_digest"),
            "blueprint_gate_digest": blueprint_gate.get("gate_digest"),
            "scenario_id": expected["scenario_id"],
            "scope": package.get("scope"),
            "authority_boundary": package.get("authority_boundary"),
            "execution_staging_namespace_id": expected["execution_staging_namespace_id"],
        }
        errors.extend(f"approval_reviewer_decision_receipt_{field}_mismatch" for field, value in receipt_binding.items() if getattr(reviewer_receipt, field) != value)
        if reviewer_receipt.expires_at <= current or reviewer_receipt.issued_at > current or reviewer_receipt.issued_at >= reviewer_receipt.expires_at:
            errors.append("approval_reviewer_decision_receipt_expiry_invalid")
        if approval.expires_at > reviewer_receipt.expires_at or approval.issued_at < reviewer_receipt.issued_at:
            errors.append("approval_reviewer_decision_receipt_window_mismatch")
    if approval.admission_ttl_minutes != 30 or approval.receipt_ttl_minutes != 15 or approval.receipt_ttl_minutes > approval.admission_ttl_minutes:
        errors.append("approval_ttl_policy_invalid")
    if approval.single_use is not True or approval.no_retry_replay_or_renewal is not True:
        errors.append("approval_single_use_or_replay_policy_invalid")
    result: dict[str, object] = {"status": "pass" if not errors else "production_human_jit_window_approval_binding_mismatch", "errors": tuple(sorted(errors)), "approval_digest": approval.approval_digest}
    if errors:
        return None, result
    return ValidatedAuthorityContext(
        authority_class=approval.authority_class,
        authority_digest=approval.approval_digest,
        reviewer_identity=approval.reviewer_identity,
        scenario_id=approval.scenario_id,
        source_ref=approval.review_receipt_id,
        production=True,
    ), result


_V2_3_EXECUTION_PACKAGE_PAYLOAD_FIELDS = frozenset(
    {
        "schema_version",
        "scope",
        "package_ref",
        "authority_boundary",
        "input_bytes_source",
        "a0_design_digest",
        "design_package_digest",
        "supersedes_rejected_package_digest",
        "input_file_sha256",
        "fixed_store_fingerprints",
        "corpus_digest",
        "oracle_digest",
        "scenario_matrix_digest",
        "execution_ready_policy_digest",
        "execution_preflight",
        "receipt_lifecycle",
        "execution_mode",
        "external_package_admission_ref",
        "external_package_admission_required",
        "single_use_execution_receipt_required",
        "receipt_authority_ledger_required",
        "actual_execution_authorized_by_package",
        "compiler_shadow_execution_authorized_by_package",
    }
)
_V2_4_EXECUTION_PACKAGE_PAYLOAD_FIELDS = frozenset(
    {
        "schema_version",
        "package_ref",
        "scope",
        "authority_boundary",
        "input_bytes_source",
        "input_file_sha256",
        "phase_a_digests",
        "phase_a_artifacts",
        "fixed_store_fingerprints",
        "corpus_digest",
        "oracle_digest",
        "scenario_matrix_digest",
        "execution_policy_digest",
        "scenario_matrix_summary",
        "execution_preflight",
        "receipt_lifecycle",
        "transport_isolation",
        "execution_mode",
        "actual_execution_authorized_by_package",
        "execution_eligibility",
        "fresh_external_admission_required",
        "single_use_execution_receipt_required",
        "cross_gate_contract",
        "supersedes",
        "zero_execution_counts",
    }
)
_V2_5_EXECUTION_PACKAGE_PAYLOAD_FIELDS = _V2_4_EXECUTION_PACKAGE_PAYLOAD_FIELDS | frozenset({"incident_evidence"})
_V2_6_EXECUTION_PACKAGE_PAYLOAD_FIELDS = _V2_5_EXECUTION_PACKAGE_PAYLOAD_FIELDS | frozenset({"jit_window_contract"})
_V2_7_EXECUTION_PACKAGE_PAYLOAD_FIELDS = _V2_6_EXECUTION_PACKAGE_PAYLOAD_FIELDS | frozenset({"approval_lineage_contract", "b0_4_policy_digest"})
_V2_8_EXECUTION_PACKAGE_PAYLOAD_FIELDS = _V2_7_EXECUTION_PACKAGE_PAYLOAD_FIELDS | frozenset({"operational_proof_contract", "b0_5_policy_digest"})
_V2_9_EXECUTION_PACKAGE_PAYLOAD_FIELDS = _V2_8_EXECUTION_PACKAGE_PAYLOAD_FIELDS | frozenset({"executable_authority_contract", "b0_6_policy_digest"})
_V2_10_EXECUTION_PACKAGE_PAYLOAD_FIELDS = _V2_9_EXECUTION_PACKAGE_PAYLOAD_FIELDS | frozenset({"b0_7_policy_digest", "trigger_ddl_contract"})


@dataclass(frozen=True)
class M2A1ExecutionPackageContract:
    """Versioned production contract for an exact M2-A1 execution package."""

    schema_version: str
    payload_fields: frozenset[str]
    admission_schema_version: str
    receipt_schema_version: str


_V2_3_PACKAGE_CONTRACT = M2A1ExecutionPackageContract(
    schema_version=V2_3_PACKAGE_SCHEMA,
    payload_fields=_V2_3_EXECUTION_PACKAGE_PAYLOAD_FIELDS,
    admission_schema_version=V2_3_ADMISSION_SCHEMA,
    receipt_schema_version=V2_3_RECEIPT_SCHEMA,
)
_V2_4_PACKAGE_CONTRACT = M2A1ExecutionPackageContract(
    schema_version=V2_4_PACKAGE_SCHEMA,
    payload_fields=_V2_4_EXECUTION_PACKAGE_PAYLOAD_FIELDS,
    admission_schema_version=V2_4_ADMISSION_SCHEMA,
    receipt_schema_version=V2_4_RECEIPT_SCHEMA,
)
_V2_5_PACKAGE_CONTRACT = M2A1ExecutionPackageContract(
    schema_version=V2_5_PACKAGE_SCHEMA,
    payload_fields=_V2_5_EXECUTION_PACKAGE_PAYLOAD_FIELDS,
    admission_schema_version=V2_5_ADMISSION_SCHEMA,
    receipt_schema_version=V2_5_RECEIPT_SCHEMA,
)
_V2_6_PACKAGE_CONTRACT = M2A1ExecutionPackageContract(
    schema_version=V2_6_PACKAGE_SCHEMA,
    payload_fields=_V2_6_EXECUTION_PACKAGE_PAYLOAD_FIELDS,
    admission_schema_version=V2_6_ADMISSION_SCHEMA,
    receipt_schema_version=V2_6_RECEIPT_SCHEMA,
)
_V2_7_PACKAGE_CONTRACT = M2A1ExecutionPackageContract(
    schema_version=V2_7_PACKAGE_SCHEMA,
    payload_fields=_V2_7_EXECUTION_PACKAGE_PAYLOAD_FIELDS,
    admission_schema_version=V2_7_ADMISSION_SCHEMA,
    receipt_schema_version=V2_7_RECEIPT_SCHEMA,
)
_V2_8_PACKAGE_CONTRACT = M2A1ExecutionPackageContract(
    schema_version=V2_8_PACKAGE_SCHEMA,
    payload_fields=_V2_8_EXECUTION_PACKAGE_PAYLOAD_FIELDS,
    admission_schema_version=V2_8_ADMISSION_SCHEMA,
    receipt_schema_version=V2_8_RECEIPT_SCHEMA,
)
_V2_9_PACKAGE_CONTRACT = M2A1ExecutionPackageContract(
    schema_version=V2_9_PACKAGE_SCHEMA,
    payload_fields=_V2_9_EXECUTION_PACKAGE_PAYLOAD_FIELDS,
    admission_schema_version=V2_9_ADMISSION_SCHEMA,
    receipt_schema_version=V2_9_RECEIPT_SCHEMA,
)
_V2_10_PACKAGE_CONTRACT = M2A1ExecutionPackageContract(
    schema_version=V2_10_PACKAGE_SCHEMA,
    payload_fields=_V2_10_EXECUTION_PACKAGE_PAYLOAD_FIELDS,
    admission_schema_version=V2_10_ADMISSION_SCHEMA,
    receipt_schema_version=V2_10_RECEIPT_SCHEMA,
)
_PACKAGE_CONTRACTS = {
    V2_3_PACKAGE_SCHEMA: _V2_3_PACKAGE_CONTRACT,
    V2_4_PACKAGE_SCHEMA: _V2_4_PACKAGE_CONTRACT,
    V2_5_PACKAGE_SCHEMA: _V2_5_PACKAGE_CONTRACT,
    V2_6_PACKAGE_SCHEMA: _V2_6_PACKAGE_CONTRACT,
    V2_7_PACKAGE_SCHEMA: _V2_7_PACKAGE_CONTRACT,
    V2_8_PACKAGE_SCHEMA: _V2_8_PACKAGE_CONTRACT,
    V2_9_PACKAGE_SCHEMA: _V2_9_PACKAGE_CONTRACT,
    V2_10_PACKAGE_SCHEMA: _V2_10_PACKAGE_CONTRACT,
}
_RECEIPT_ID_RE = re.compile(r"^[A-Za-z0-9:_-]{1,160}$")
_REPARSE_POINT = 0x0400


def _normalised_execution_bytes(value: bytes) -> bytes:
    """Compare staged/working text without treating CRLF conversion as code drift."""

    return value.replace(b"\r\n", b"\n")


def _is_reparse_or_symlink(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except OSError:
        return True
    return bool(attributes & _REPARSE_POINT)


def _assert_no_reparse_escape(anchor: Path, target: Path) -> None:
    """Require every existing component from anchor to target to be non-reparse."""

    if not anchor.is_absolute() or not target.is_absolute():
        raise M2A1ExecutionPreflightError("execution_path_must_be_absolute")
    try:
        relative = target.relative_to(anchor)
    except ValueError as exc:
        raise M2A1ExecutionPreflightError("execution_path_outside_approved_namespace") from exc
    current = anchor
    if current.exists() and _is_reparse_or_symlink(current):
        raise M2A1ExecutionPreflightError("execution_namespace_anchor_reparse_forbidden")
    for component in relative.parts:
        current = current / component
        if current.exists() and _is_reparse_or_symlink(current):
            raise M2A1ExecutionPreflightError("execution_path_reparse_or_symlink_forbidden")


def _git_index_bytes(repository_root: Path, relative_path: str) -> bytes:
    completed = subprocess.run(
        ["git", "show", f":{relative_path}"],
        cwd=repository_root,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise M2A1ExecutionPreflightError(f"execution_preflight_git_index_input_missing:{relative_path}")
    return completed.stdout


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class M2A1ExecutionPreflight:
    """Pure pre-write proof for one exact M2-A1 admitted execution.

    The object is created before any staging-directory creation, SQLite connect,
    receipt lookup/consumption or M2 runtime import.  Its returned paths are
    derived from the admitted package; callers cannot supply their own roots.
    """

    repository_root: Path
    package: Mapping[str, Any]
    package_contract: M2A1ExecutionPackageContract
    admission: M2A1ExternalPackageAdmission
    human_approval_digest: str | None
    receipt_id: str
    scenario_id: str
    execution_staging_namespace: Path
    run_root: Path
    authority_root: Path
    ledger_path: Path
    runtime_root: Path
    output_path: Path
    fixed_store_path: Path
    corpus_case: Mapping[str, Any]
    runtime_scenario: Mapping[str, str]
    input_count: int
    preflight_digest: str

    def materialize_authority_for_registration(self) -> bool:
        """Create only the derived authority root for a receipt registrar.

        No runtime/output path is materialized in this phase.  Reopening the
        same authority-only root is allowed solely to recover an interrupted
        registrar; any runtime/output residue is a fail-closed lifecycle
        violation.
        """

        _assert_no_reparse_escape(self.execution_staging_namespace.parent, self.execution_staging_namespace)
        for forbidden in (self.runtime_root, self.output_path.parent):
            if forbidden.exists():
                raise M2A1ExecutionPreflightError("receipt_registration_runtime_or_output_already_materialized")
        if self.run_root.exists():
            _assert_no_reparse_escape(self.execution_staging_namespace, self.run_root)
            if not self.authority_root.is_dir():
                raise M2A1ExecutionPreflightError("receipt_registration_authority_root_missing")
            _assert_no_reparse_escape(self.execution_staging_namespace, self.authority_root)
            return False
        self.run_root.mkdir(parents=True, exist_ok=False)
        _assert_no_reparse_escape(self.execution_staging_namespace, self.run_root)
        self.authority_root.mkdir(parents=False, exist_ok=False)
        _assert_no_reparse_escape(self.execution_staging_namespace, self.authority_root)
        return True

    def verify_consumption_grant_before_runtime(
        self,
        grant: M2A1ConsumptionGrant,
        *,
        ledger: "M2A1ReceiptLedger",
    ) -> M2A1ExecutionReceipt:
        """Verify an event-backed grant before any runtime/output materialization.

        An active/registered receipt, a boolean flag or a caller-constructed
        grant cannot enter this method.  The ledger reopens its own append-only
        event and verifies every preflight/package/admission/scenario binding.
        """

        if not self.run_root.is_dir() or not self.authority_root.is_dir() or not self.ledger_path.is_file():
            raise M2A1ExecutionPreflightError("receipt_consumption_authority_layout_missing")
        for path in (self.run_root, self.authority_root, self.ledger_path):
            _assert_no_reparse_escape(self.execution_staging_namespace, path)
        if ledger.db_path.absolute() != self.ledger_path.absolute() or ledger.approved_authority_root != self.authority_root.absolute():
            raise M2A1ExecutionPreflightError("receipt_consumption_ledger_not_preflight_bound")
        try:
            consumed = ledger.verify_consumption_grant(
                grant,
                admission=self.admission,
                package_ref=str(self.package["package_ref"]),
                executable_package_digest=str(self.package["package_digest"]),
                scope=str(self.package["scope"]),
                authority_boundary=str(self.package["authority_boundary"]),
                execution_staging_namespace_id=self.admission.execution_staging_namespace_id,
                scenario_id=self.scenario_id,
                run_root=self.run_root,
                preflight_digest=self.preflight_digest,
                expected_admission_schema_version=self.package_contract.admission_schema_version,
                expected_receipt_schema_version=self.package_contract.receipt_schema_version,
                expected_human_approval_digest=self.human_approval_digest,
            )
        except M2A1ReceiptAuthorityError as exc:
            raise M2A1ExecutionPreflightError(str(exc)) from exc
        return consumed

    def materialize_runtime_after_consumption(
        self,
        grant: M2A1ConsumptionGrant,
        *,
        ledger: "M2A1ReceiptLedger",
    ) -> M2A1ExecutionReceipt:
        """Materialize runtime/output only after an exact ledger-backed grant."""

        consumed = self.verify_consumption_grant_before_runtime(grant, ledger=ledger)
        if self.runtime_root.exists() or self.output_path.parent.exists():
            raise M2A1ExecutionPreflightError("runtime_or_output_already_materialized")
        self.runtime_root.mkdir(parents=False, exist_ok=False)
        self.output_path.parent.mkdir(parents=False, exist_ok=False)
        for path in (self.runtime_root, self.output_path.parent):
            _assert_no_reparse_escape(self.execution_staging_namespace, path)
        return consumed

    def reverify_current_execution_tree(self) -> None:
        """Close the package-to-runtime TOCTOU window before importing M2 modules."""

        _verify_index_and_working_inputs(self.repository_root, self.package["input_file_sha256"])


def execution_package_contract(package: Mapping[str, Any]) -> M2A1ExecutionPackageContract:
    schema_version = package.get("schema_version")
    contract = _PACKAGE_CONTRACTS.get(schema_version)
    if contract is None:
        raise M2A1ExecutionPreflightError("execution_package_schema_invalid")
    return contract


def _package_payload(package: Mapping[str, Any]) -> dict[str, Any]:
    contract = execution_package_contract(package)
    if set(package) != contract.payload_fields | {"package_digest"}:
        raise M2A1ExecutionPreflightError("execution_package_schema_invalid")
    try:
        return {field: package[field] for field in contract.payload_fields}
    except KeyError as exc:
        raise M2A1ExecutionPreflightError("execution_package_schema_invalid") from exc


def _validate_v2_4_package_contract(package: Mapping[str, Any], contract: M2A1ExecutionPackageContract) -> None:
    if package.get("scope") != "M2_A1_exact_admission_gated_future_actual_only":
        raise M2A1ExecutionPreflightError("execution_package_scope_invalid")
    if package.get("execution_eligibility") != "fresh_exact_admission_and_receipt_required":
        raise M2A1ExecutionPreflightError("execution_package_eligibility_invalid")
    if package.get("fresh_external_admission_required") is not True or package.get("single_use_execution_receipt_required") is not True:
        raise M2A1ExecutionPreflightError("execution_package_authority_requirement_invalid")
    phase_a = package.get("phase_a_digests")
    phase_artifacts = package.get("phase_a_artifacts")
    expected_phase_keys = {"classification", "repair_package", "repair_gate"}
    if not isinstance(phase_a, Mapping) or set(phase_a) != expected_phase_keys or any(not _is_sha256(str(value)) for value in phase_a.values()):
        raise M2A1ExecutionPreflightError("execution_package_phase_a_digest_invalid")
    if not isinstance(phase_artifacts, Mapping) or set(phase_artifacts) != expected_phase_keys:
        raise M2A1ExecutionPreflightError("execution_package_phase_a_artifact_binding_invalid")
    hashes = package.get("input_file_sha256")
    for key, expected_field in (("classification", "classification_digest"), ("repair_package", "package_digest"), ("repair_gate", "gate_digest")):
        binding = phase_artifacts.get(key)
        if not isinstance(binding, Mapping) or set(binding) != {"relative_path", "digest_field", "digest"}:
            raise M2A1ExecutionPreflightError("execution_package_phase_a_artifact_binding_invalid")
        if binding.get("digest_field") != expected_field or binding.get("digest") != phase_a[key] or not isinstance(binding.get("relative_path"), str) or not isinstance(hashes, Mapping) or binding["relative_path"] not in hashes:
            raise M2A1ExecutionPreflightError("execution_package_phase_a_artifact_binding_invalid")
    transport = package.get("transport_isolation")
    if not isinstance(transport, Mapping) or transport.get("public_exports") != "lazy" or transport.get("parent") != "stdlib_clean_child_supervisor" or transport.get("module_presence") != "context_only" or transport.get("constructor_connect_request") != "hard_fail" or transport.get("parent_preload") != "cannot_contaminate_python_I_child":
        raise M2A1ExecutionPreflightError("execution_package_transport_policy_invalid")
    bindings = transport.get("runtime_hash_bindings")
    required_bindings = {"parent_runner", "clean_child", "canary", "registrar"}
    if not isinstance(bindings, Mapping) or set(bindings) != required_bindings or not isinstance(hashes, Mapping):
        raise M2A1ExecutionPreflightError("execution_package_transport_runtime_binding_invalid")
    for binding in bindings.values():
        if not isinstance(binding, Mapping) or set(binding) != {"relative_path", "sha256"} or binding.get("relative_path") not in hashes or binding.get("sha256") != hashes[binding["relative_path"]]:
            raise M2A1ExecutionPreflightError("execution_package_transport_runtime_binding_invalid")
    supersedes = package.get("supersedes")
    if not isinstance(supersedes, Mapping) or supersedes.get("authority_disposition") != "historical_only_expired_consumed_or_non_replayable" or any(not _is_sha256(str(supersedes.get(key))) for key in ("v2_3_package_digest", "v2_3_blueprint_digest", "prior_failed_actual_digest")):
        raise M2A1ExecutionPreflightError("execution_package_nonreplay_supersedes_invalid")
    lifecycle = package.get("receipt_lifecycle")
    expected_lifecycle = {
        "registrar": "authority_only_register_exact_package_and_scenario",
        "executor": "open_existing_consume_reverify_verify_grant_before_runtime",
        "post_consume": "materialize_runtime_then_import_m2",
        "crash_recovery": "consumed_without_terminal_outcome_unknown",
        "execution_eligibility": "fresh_exact_admission_and_receipt_required",
    }
    if lifecycle != expected_lifecycle:
        raise M2A1ExecutionPreflightError("execution_package_receipt_lifecycle_invalid")
    if package.get("cross_gate_contract") != {
        "phase_a_exact_digests_required": True,
        "plan_must_bind_package_gate_digest": True,
        "blueprint_must_bind_package_and_plan_gate_digests": True,
    }:
        raise M2A1ExecutionPreflightError("execution_package_cross_gate_contract_invalid")


def _validate_v2_5_package_contract(package: Mapping[str, Any], contract: M2A1ExecutionPackageContract) -> None:
    """Extend the v2.4 production contract with immutable incident binding."""

    # Reuse the stable v2.4 checks only for its common shape.  v2.5 has an
    # additional immutable incident binding, a fifth frozen supervisor hash,
    # and an expiry-terminal rule; none may be silently dropped while using
    # the v2.4 validator.
    v2_4_shape = {key: value for key, value in package.items() if key != "incident_evidence"}
    transport = dict(v2_4_shape["transport_isolation"])
    runtime_bindings = dict(transport["runtime_hash_bindings"])
    runtime_bindings.pop("jit_orchestrator", None)
    transport["runtime_hash_bindings"] = runtime_bindings
    v2_4_shape["transport_isolation"] = transport
    lifecycle = dict(v2_4_shape["receipt_lifecycle"])
    lifecycle.pop("expiry_terminal", None)
    v2_4_shape["receipt_lifecycle"] = lifecycle
    supersedes = dict(v2_4_shape["supersedes"])
    supersedes.update({
        "v2_3_package_digest": "ff5476b9a8c4d9a82a11b163039e118922b09c945a0d53ff9df031b7c268b318",
        "v2_3_blueprint_digest": "683f3df509735466c33394e3771dded3c0c1bb129ab1c53462902f7b6b5e485f",
        "prior_failed_actual_digest": "934fb16b76f1e1b19371603f0d69c2e3e25c9357c8427c84e1e626b1247795d7",
    })
    v2_4_shape["supersedes"] = supersedes
    _validate_v2_4_package_contract(v2_4_shape, _V2_4_PACKAGE_CONTRACT)
    hashes = package.get("input_file_sha256")
    bindings = package.get("transport_isolation", {}).get("runtime_hash_bindings") if isinstance(package.get("transport_isolation"), Mapping) else None
    required_bindings = {"parent_runner", "clean_child", "canary", "registrar", "jit_orchestrator"}
    if not isinstance(bindings, Mapping) or set(bindings) != required_bindings or not isinstance(hashes, Mapping):
        raise M2A1ExecutionPreflightError("execution_package_v2_5_transport_runtime_binding_invalid")
    for binding in bindings.values():
        if not isinstance(binding, Mapping) or set(binding) != {"relative_path", "sha256"} or binding.get("relative_path") not in hashes or binding.get("sha256") != hashes[binding["relative_path"]]:
            raise M2A1ExecutionPreflightError("execution_package_v2_5_transport_runtime_binding_invalid")
    expected_lifecycle = {
        "registrar": "authority_only_register_exact_package_and_scenario",
        "executor": "open_existing_consume_reverify_verify_grant_before_runtime",
        "post_consume": "materialize_runtime_then_import_m2",
        "crash_recovery": "consumed_without_terminal_outcome_unknown",
        "execution_eligibility": "fresh_exact_admission_and_receipt_required",
        "expiry_terminal": "exact_expired_unconsumed_append_only_no_payload_overwrite",
    }
    if package.get("receipt_lifecycle") != expected_lifecycle:
        raise M2A1ExecutionPreflightError("execution_package_v2_5_receipt_lifecycle_invalid")
    actual_supersedes = package.get("supersedes")
    expected_v2_5_supersedes = {
        "v2_4_package_digest": "615a73da64eff69a56a13b42d6c59c892820f15c4de7dc3a2be3c425d2aee68e",
        "v2_4_blueprint_digest": "09ee9176a8090f1c42885fb2fab33c118a2d7b41cab2b66d694e478ff0b873a8",
        "prior_failed_actual_digest": "934fb16b76f1e1b19371603f0d69c2e3e25c9357c8427c84e1e626b1247795d7",
        "authority_disposition": "historical_only_expired_consumed_or_non_replayable",
    }
    if actual_supersedes != expected_v2_5_supersedes:
        raise M2A1ExecutionPreflightError("execution_package_v2_5_nonreplay_supersedes_invalid")
    incident = package.get("incident_evidence")
    if not isinstance(incident, Mapping) or set(incident) != {"relative_path", "incident_digest", "expired_terminal_relative_path", "expired_terminal_digest"}:
        raise M2A1ExecutionPreflightError("execution_package_incident_evidence_invalid")
    if not isinstance(incident.get("relative_path"), str) or not isinstance(incident.get("expired_terminal_relative_path"), str) or not _is_sha256(str(incident.get("incident_digest"))) or not _is_sha256(str(incident.get("expired_terminal_digest"))):
        raise M2A1ExecutionPreflightError("execution_package_incident_evidence_invalid")
    if incident["relative_path"] != "data/manifests/point01_m2_a1_v2_4_baseline_jit_dispatch_incident.json" or incident["incident_digest"] != "a59076a127c0b76902dc362aee94980427660fbc695b47e9c94fd73228cb9a18" or incident["expired_terminal_relative_path"] != "data/manifests/point01_m2_a1_v2_4_baseline_jit_expired_unconsumed_terminal.json":
        raise M2A1ExecutionPreflightError("execution_package_v2_5_incident_identity_invalid")
    if not isinstance(hashes, Mapping) or incident["relative_path"] not in hashes or incident["expired_terminal_relative_path"] not in hashes:
        raise M2A1ExecutionPreflightError("execution_package_incident_evidence_not_hashed")


def _validate_v2_6_package_contract(package: Mapping[str, Any], contract: M2A1ExecutionPackageContract) -> None:
    """Require a frozen approval-driven JIT entry, never a mutable stub."""

    v2_5_shape = {key: value for key, value in package.items() if key != "jit_window_contract"}
    v2_5_shape["schema_version"] = V2_5_PACKAGE_SCHEMA
    v2_5_shape["supersedes"] = {
        "v2_4_package_digest": "615a73da64eff69a56a13b42d6c59c892820f15c4de7dc3a2be3c425d2aee68e",
        "v2_4_blueprint_digest": "09ee9176a8090f1c42885fb2fab33c118a2d7b41cab2b66d694e478ff0b873a8",
        "prior_failed_actual_digest": "934fb16b76f1e1b19371603f0d69c2e3e25c9357c8427c84e1e626b1247795d7",
        "authority_disposition": "historical_only_expired_consumed_or_non_replayable",
    }
    _validate_v2_5_package_contract(v2_5_shape, _V2_5_PACKAGE_CONTRACT)
    hashes = package.get("input_file_sha256")
    jit = package.get("jit_window_contract")
    expected_keys = {
        "approval_schema_version", "approval_required_before_issue", "orchestrator", "dry_run", "execute_sequence", "default_command", "active_command", "supersedes_v2_5_package_digest",
    }
    if not isinstance(jit, Mapping) or set(jit) != expected_keys or not isinstance(hashes, Mapping):
        raise M2A1ExecutionPreflightError("execution_package_v2_6_jit_contract_invalid")
    binding = jit.get("orchestrator")
    if not isinstance(binding, Mapping) or set(binding) != {"relative_path", "sha256"} or binding.get("relative_path") not in hashes or binding.get("sha256") != hashes[binding["relative_path"]]:
        raise M2A1ExecutionPreflightError("execution_package_v2_6_jit_orchestrator_binding_invalid")
    if jit.get("approval_schema_version") != HUMAN_JIT_WINDOW_APPROVAL_SCHEMA or jit.get("approval_required_before_issue") is not True or jit.get("dry_run") != "approval_validate_only_no_admission_receipt_namespace_or_write" or jit.get("execute_sequence") != ["verify_approval", "issue_admission", "verify", "register", "preflight", "consume", "reverify", "grant", "materialize", "parent_clean_child_execute", "immutable_actual", "independent_oracle", "reviewer", "closeout"] or jit.get("default_command") != "do_not_invoke" or jit.get("active_command") != "execute_approved_window_only" or jit.get("supersedes_v2_5_package_digest") != "a23dac3931164b4910a6182b97fa37e10d788e893991e4bc1d079e78439ebe6a":
        raise M2A1ExecutionPreflightError("execution_package_v2_6_jit_contract_invalid")
    expected_supersedes = {
        "v2_5_package_digest": "a23dac3931164b4910a6182b97fa37e10d788e893991e4bc1d079e78439ebe6a",
        "v2_5_blueprint_digest": "9d2ae58f371d57bd4e827eda398933623886f74126a015ee6a7a167a41ea3020",
        "v2_4_package_digest": "615a73da64eff69a56a13b42d6c59c892820f15c4de7dc3a2be3c425d2aee68e",
        "authority_disposition": "historical_only_expired_consumed_or_non_replayable",
    }
    if package.get("supersedes") != expected_supersedes:
        raise M2A1ExecutionPreflightError("execution_package_v2_6_nonreplay_supersedes_invalid")


def _validate_v2_7_package_contract(package: Mapping[str, Any], contract: M2A1ExecutionPackageContract) -> None:
    """v2.7 binds the human approval digest across every durable authority event."""

    hashes = package.get("input_file_sha256")
    if not isinstance(hashes, Mapping) or not hashes:
        raise M2A1ExecutionPreflightError("execution_package_v2_7_input_hashes_invalid")
    if not _is_sha256(str(package.get("b0_4_policy_digest"))) or "configs/engineering_handoff/point01_m2_a1_approval_lineage_policy_v2_7.json" not in hashes:
        raise M2A1ExecutionPreflightError("execution_package_v2_7_policy_binding_invalid")
    if package.get("scope") != "M2_A1_exact_admission_gated_future_actual_only" or package.get("execution_eligibility") != "fresh_exact_admission_and_receipt_required":
        raise M2A1ExecutionPreflightError("execution_package_v2_7_scope_or_eligibility_invalid")
    if package.get("execution_mode") != "external_admission_gated" or package.get("fresh_external_admission_required") is not True or package.get("single_use_execution_receipt_required") is not True:
        raise M2A1ExecutionPreflightError("execution_package_v2_7_authority_boundary_invalid")
    jit = package.get("jit_window_contract")
    if not isinstance(jit, Mapping) or jit.get("approval_schema_version") != HUMAN_JIT_WINDOW_APPROVAL_SCHEMA or jit.get("approval_required_before_issue") is not True or jit.get("default_command") != "do_not_invoke" or jit.get("active_command") != "execute_approved_window_only":
        raise M2A1ExecutionPreflightError("execution_package_v2_7_jit_contract_invalid")
    binding = jit.get("orchestrator")
    if not isinstance(binding, Mapping) or binding.get("relative_path") not in hashes or binding.get("sha256") != hashes[binding["relative_path"]]:
        raise M2A1ExecutionPreflightError("execution_package_v2_7_orchestrator_binding_invalid")
    lineage = package.get("approval_lineage_contract")
    expected = {
        "admission_schema_version": V2_7_ADMISSION_SCHEMA,
        "receipt_schema_version": V2_7_RECEIPT_SCHEMA,
        "human_approval_digest_required": True,
        "ledger_events": ["REGISTERED", "CONSUMED_BEFORE_RUN", "TERMINAL"],
        "terminal_sequence": ["immutable_actual_validated", "independent_oracle", "preterminal_reviewer", "terminal_append"],
        "post_consume_exception_terminal": "outcome_unknown_no_success",
        "supersedes_v2_6_package_digest": "e85ceffb0922ceda99e105b519a7f2dac19d5e5bdcea357925ee451d066ad4ed",
    }
    if lineage != expected:
        raise M2A1ExecutionPreflightError("execution_package_v2_7_approval_lineage_contract_invalid")


def _validate_v2_8_package_contract(package: Mapping[str, Any], contract: M2A1ExecutionPackageContract) -> None:
    """Bind v2.8 operational proof to an event-digest source of truth."""

    hashes = package.get("input_file_sha256")
    if not isinstance(hashes, Mapping) or not hashes or not _is_sha256(str(package.get("b0_4_policy_digest"))) or not _is_sha256(str(package.get("b0_5_policy_digest"))):
        raise M2A1ExecutionPreflightError("execution_package_v2_8_policy_binding_invalid")
    if package.get("scope") != "M2_A1_exact_admission_gated_future_actual_only" or package.get("execution_eligibility") != "fresh_exact_admission_and_receipt_required":
        raise M2A1ExecutionPreflightError("execution_package_v2_8_scope_or_eligibility_invalid")
    if package.get("execution_mode") != "external_admission_gated" or package.get("fresh_external_admission_required") is not True or package.get("single_use_execution_receipt_required") is not True:
        raise M2A1ExecutionPreflightError("execution_package_v2_8_authority_boundary_invalid")
    jit = package.get("jit_window_contract")
    if not isinstance(jit, Mapping) or jit.get("approval_schema_version") != HUMAN_JIT_WINDOW_APPROVAL_SCHEMA or jit.get("approval_required_before_issue") is not True or jit.get("default_command") != "do_not_invoke" or jit.get("active_command") != "execute_approved_window_only":
        raise M2A1ExecutionPreflightError("execution_package_v2_8_jit_contract_invalid")
    binding = jit.get("orchestrator")
    if not isinstance(binding, Mapping) or binding.get("relative_path") not in hashes or binding.get("sha256") != hashes[binding["relative_path"]]:
        raise M2A1ExecutionPreflightError("execution_package_v2_8_orchestrator_binding_invalid")
    policy_path = "configs/engineering_handoff/point01_m2_a1_operational_proof_policy_v2_8.json"
    if policy_path not in hashes or "configs/engineering_handoff/point01_m2_a1_approval_lineage_policy_v2_7.json" not in hashes:
        raise M2A1ExecutionPreflightError("execution_package_v2_8_policy_not_hashed")
    lineage = package.get("approval_lineage_contract")
    expected_lineage = {
        "admission_schema_version": V2_8_ADMISSION_SCHEMA,
        "receipt_schema_version": V2_8_RECEIPT_SCHEMA,
        "human_approval_digest_required": True,
        "ledger_events": ["REGISTERED", "CONSUMED_BEFORE_RUN", "TERMINAL"],
        "terminal_sequence": ["immutable_actual_validated", "independent_oracle", "preterminal_reviewer", "terminal_append"],
        "post_consume_exception_terminal": "outcome_unknown_no_success",
        "supersedes_v2_7_package_digest": "0335e114950db227ac67d8dbb16e554626fec194d8acb8c84d0f29f90ccd1367",
    }
    if lineage != expected_lineage:
        raise M2A1ExecutionPreflightError("execution_package_v2_8_approval_lineage_contract_invalid")
    proof = package.get("operational_proof_contract")
    expected = {
        "admission_schema_version": V2_8_ADMISSION_SCHEMA,
        "receipt_schema_version": V2_8_RECEIPT_SCHEMA,
        "event_source_of_truth": "point01_m2_a1_execution_receipt_events_append_only_sqlite_triggers",
        "event_payload_digest_reverified_on_read": True,
        "integration_entry": "frozen_dependency_injected_v2_8_execute_core",
        "synthetic_fixture_authority": "synthetic_nonhuman_fixture_only",
        "required_integration_branches": ["happy_path", "corrupted_actual", "reviewer_failure", "post_consume_child_exit"],
        "supersedes_v2_7_package_digest": "0335e114950db227ac67d8dbb16e554626fec194d8acb8c84d0f29f90ccd1367",
    }
    if proof != expected:
        raise M2A1ExecutionPreflightError("execution_package_v2_8_operational_proof_contract_invalid")


def _validate_v2_9_package_contract(package: Mapping[str, Any], contract: M2A1ExecutionPackageContract) -> None:
    """Require B0.6's executable external-authority path, not a synthetic stub.

    v2.9 deliberately retains v2.8's synthetic proof as historical evidence,
    but it adds a separately hash-bound production entry.  The future approval
    is package-external; changing an approval must never require rewriting this
    immutable package.
    """

    hashes = package.get("input_file_sha256")
    if not isinstance(hashes, Mapping) or not hashes or not _is_sha256(str(package.get("b0_6_policy_digest"))):
        raise M2A1ExecutionPreflightError("execution_package_v2_9_policy_binding_invalid")
    policy_path = "configs/engineering_handoff/point01_m2_a1_executable_authority_policy_v2_9.json"
    if policy_path not in hashes:
        raise M2A1ExecutionPreflightError("execution_package_v2_9_policy_not_hashed")

    # v2.8's binding remains immutable evidence, with versioned authority
    # fields projected back only for its strict historical validator.
    v2_8_shape = {key: value for key, value in package.items() if key not in {"executable_authority_contract", "b0_6_policy_digest"}}
    v2_8_shape["schema_version"] = V2_8_PACKAGE_SCHEMA
    lineage = dict(v2_8_shape["approval_lineage_contract"])
    lineage.update(
        {
            "admission_schema_version": V2_8_ADMISSION_SCHEMA,
            "receipt_schema_version": V2_8_RECEIPT_SCHEMA,
            "supersedes_v2_7_package_digest": "0335e114950db227ac67d8dbb16e554626fec194d8acb8c84d0f29f90ccd1367",
        }
    )
    v2_8_shape["approval_lineage_contract"] = lineage
    proof = dict(v2_8_shape["operational_proof_contract"])
    proof.update(
        {
            "admission_schema_version": V2_8_ADMISSION_SCHEMA,
            "receipt_schema_version": V2_8_RECEIPT_SCHEMA,
            "supersedes_v2_7_package_digest": "0335e114950db227ac67d8dbb16e554626fec194d8acb8c84d0f29f90ccd1367",
        }
    )
    v2_8_shape["operational_proof_contract"] = proof
    _validate_v2_8_package_contract(v2_8_shape, _V2_8_PACKAGE_CONTRACT)

    if package.get("scope") != "M2_A1_exact_admission_gated_future_actual_only" or package.get("execution_eligibility") != "fresh_exact_admission_and_receipt_required":
        raise M2A1ExecutionPreflightError("execution_package_v2_9_scope_or_eligibility_invalid")
    if package.get("execution_mode") != "external_admission_gated" or package.get("actual_execution_authorized_by_package") is not False:
        raise M2A1ExecutionPreflightError("execution_package_v2_9_authority_boundary_invalid")

    lineage = package.get("approval_lineage_contract")
    if not isinstance(lineage, Mapping) or lineage.get("admission_schema_version") != V2_9_ADMISSION_SCHEMA or lineage.get("receipt_schema_version") != V2_9_RECEIPT_SCHEMA or lineage.get("human_approval_digest_required") is not True:
        raise M2A1ExecutionPreflightError("execution_package_v2_9_approval_lineage_contract_invalid")
    proof = package.get("operational_proof_contract")
    if not isinstance(proof, Mapping) or proof.get("admission_schema_version") != V2_9_ADMISSION_SCHEMA or proof.get("receipt_schema_version") != V2_9_RECEIPT_SCHEMA:
        raise M2A1ExecutionPreflightError("execution_package_v2_9_operational_proof_contract_invalid")

    executable = package.get("executable_authority_contract")
    expected_keys = {
        "approval_schema_version", "admission_schema_version", "receipt_schema_version", "default_deny", "exact_approval_required", "synthetic_fixture_may_not_use_production_flag", "entries", "sequence", "supersedes_v2_8_package_digest",
    }
    if not isinstance(executable, Mapping) or set(executable) != expected_keys:
        raise M2A1ExecutionPreflightError("execution_package_v2_9_executable_authority_contract_invalid")
    if executable.get("approval_schema_version") != HUMAN_JIT_WINDOW_APPROVAL_SCHEMA or executable.get("admission_schema_version") != V2_9_ADMISSION_SCHEMA or executable.get("receipt_schema_version") != V2_9_RECEIPT_SCHEMA or executable.get("default_deny") is not True or executable.get("exact_approval_required") is not True or executable.get("synthetic_fixture_may_not_use_production_flag") is not True or executable.get("supersedes_v2_8_package_digest") != "36d39bf4d7d3cf39c32bc96d8027c922514f54d0eb7e4ef64ea0b98bd9f17ac8":
        raise M2A1ExecutionPreflightError("execution_package_v2_9_executable_authority_contract_invalid")
    expected_entries = {
        "orchestrator": "scripts/engineering/run_point01_m2_a1_v2_9_frozen_jit_window.py",
        "registrar": "scripts/engineering/run_point01_m2_a1_receipt_registrar_v2_9.py",
        "parent": "scripts/engineering/run_point01_m2_a1_actual_audit_v2_9.py",
        "clean_child": "scripts/engineering/run_point01_m2_a1_actual_audit_clean_child_v2_9.py",
    }
    entries = executable.get("entries")
    if not isinstance(entries, Mapping) or set(entries) != set(expected_entries):
        raise M2A1ExecutionPreflightError("execution_package_v2_9_entry_binding_invalid")
    for name, relative_path in expected_entries.items():
        binding = entries.get(name)
        if not isinstance(binding, Mapping) or binding != {"relative_path": relative_path, "sha256": hashes.get(relative_path)} or relative_path not in hashes:
            raise M2A1ExecutionPreflightError("execution_package_v2_9_entry_binding_invalid")
    expected_sequence = ["approval_preflight", "issue_v2_9_admission_and_receipt", "register", "preflight", "consume", "grant_verify", "materialize", "exact_bounded_actual_child", "immutable_actual_validation", "independent_oracle", "preterminal_reviewer", "terminal_append"]
    if executable.get("sequence") != expected_sequence:
        raise M2A1ExecutionPreflightError("execution_package_v2_9_sequence_invalid")


def _validate_v2_10_package_contract(package: Mapping[str, Any], contract: M2A1ExecutionPackageContract) -> None:
    """Validate the final B0.7 route as a single v2.10 authority family."""

    hashes = package.get("input_file_sha256")
    if not isinstance(hashes, Mapping) or not hashes or not _is_sha256(str(package.get("b0_6_policy_digest"))) or not _is_sha256(str(package.get("b0_7_policy_digest"))):
        raise M2A1ExecutionPreflightError("execution_package_v2_10_policy_binding_invalid")
    for policy_path in (
        "configs/engineering_handoff/point01_m2_a1_executable_authority_policy_v2_9.json",
        "configs/engineering_handoff/point01_m2_a1_execution_proof_policy_v2_10.json",
    ):
        if policy_path not in hashes:
            raise M2A1ExecutionPreflightError("execution_package_v2_10_policy_not_hashed")
    if package.get("scope") != "M2_A1_exact_admission_gated_future_actual_only" or package.get("execution_mode") != "external_admission_gated" or package.get("execution_eligibility") != "fresh_exact_admission_and_receipt_required" or package.get("actual_execution_authorized_by_package") is not False:
        raise M2A1ExecutionPreflightError("execution_package_v2_10_authority_boundary_invalid")
    trigger = package.get("trigger_ddl_contract")
    if trigger != {
        "normalized_ddl_digest": event_append_only_trigger_ddl_digest(),
        "enforcement_boundary": "application_controlled_sqlite_append_only_plus_payload_digest_not_malicious_admin_proof",
    }:
        raise M2A1ExecutionPreflightError("execution_package_v2_10_trigger_ddl_contract_invalid")
    lineage = package.get("approval_lineage_contract")
    if not isinstance(lineage, Mapping) or lineage.get("admission_schema_version") != V2_10_ADMISSION_SCHEMA or lineage.get("receipt_schema_version") != V2_10_RECEIPT_SCHEMA or lineage.get("human_approval_digest_required") is not True or lineage.get("reviewer_decision_receipt_schema_version") != PRODUCTION_REVIEWER_DECISION_RECEIPT_V2_10_SCHEMA or lineage.get("reviewer_decision_receipt_resolution_required") is not True:
        raise M2A1ExecutionPreflightError("execution_package_v2_10_approval_lineage_invalid")
    executable = package.get("executable_authority_contract")
    expected_entries = {
        "orchestrator": "scripts/engineering/run_point01_m2_a1_v2_10_frozen_jit_window.py",
        "registrar": "scripts/engineering/run_point01_m2_a1_receipt_registrar_v2_10.py",
        "parent": "scripts/engineering/run_point01_m2_a1_actual_audit_v2_10.py",
        "clean_child": "scripts/engineering/run_point01_m2_a1_actual_audit_clean_child_v2_10.py",
        "lifecycle_kernel": "src/sec_agent/canonical_runtime/m2_a1_v2_10_execution_proof.py",
    }
    if not isinstance(executable, Mapping) or executable.get("approval_schema_version") != PRODUCTION_HUMAN_JIT_WINDOW_APPROVAL_V2_10_SCHEMA or executable.get("reviewer_decision_receipt_schema_version") != PRODUCTION_REVIEWER_DECISION_RECEIPT_V2_10_SCHEMA or executable.get("synthetic_authority_schema_version") != SYNTHETIC_NONHUMAN_AUTHORITY_V2_10_SCHEMA or executable.get("admission_schema_version") != V2_10_ADMISSION_SCHEMA or executable.get("receipt_schema_version") != V2_10_RECEIPT_SCHEMA or executable.get("default_deny") is not True or executable.get("exact_approval_required") is not True or executable.get("shared_lifecycle_kernel_required") is not True:
        raise M2A1ExecutionPreflightError("execution_package_v2_10_authority_contract_invalid")
    entries = executable.get("entries")
    if not isinstance(entries, Mapping) or set(entries) != set(expected_entries):
        raise M2A1ExecutionPreflightError("execution_package_v2_10_entry_binding_invalid")
    for name, relative_path in expected_entries.items():
        if entries.get(name) != {"relative_path": relative_path, "sha256": hashes.get(relative_path)} or relative_path not in hashes:
            raise M2A1ExecutionPreflightError("execution_package_v2_10_entry_binding_invalid")
    transport = package.get("transport_isolation")
    bindings = transport.get("runtime_hash_bindings") if isinstance(transport, Mapping) else None
    required_transport = {**expected_entries, "canary": "src/sec_agent/canonical_runtime/m2_a1_audit_canary.py"}
    if not isinstance(bindings, Mapping) or set(bindings) != set(required_transport):
        raise M2A1ExecutionPreflightError("execution_package_v2_10_runtime_routing_invalid")
    for name, relative_path in required_transport.items():
        if bindings.get(name) != {"relative_path": relative_path, "sha256": hashes.get(relative_path)} or relative_path not in hashes:
            raise M2A1ExecutionPreflightError("execution_package_v2_10_runtime_routing_invalid")
    if executable.get("sequence") != ["production_approval_preflight", "resolve_reviewer_decision_receipt", "issue_v2_10_admission_and_receipt", "register", "preflight", "consume", "reverify", "grant_verify", "materialize", "exact_bounded_actual_child", "immutable_actual_validation", "independent_oracle_artifact_verified", "preterminal_reviewer_artifact_verified", "terminal_append"]:
        raise M2A1ExecutionPreflightError("execution_package_v2_10_sequence_invalid")


def _validate_package_identity(package: Mapping[str, Any]) -> M2A1ExecutionPackageContract:
    contract = execution_package_contract(package)
    payload = _package_payload(package)
    if package.get("package_digest") != canonical_digest(payload):
        raise M2A1ExecutionPreflightError("execution_package_digest_mismatch")
    if package.get("input_bytes_source") != "git_index" or package.get("execution_mode") != "external_admission_gated":
        raise M2A1ExecutionPreflightError("execution_package_authority_mode_invalid")
    if contract is _V2_3_PACKAGE_CONTRACT:
        lifecycle = package.get("receipt_lifecycle")
        if not isinstance(lifecycle, Mapping) or lifecycle.get("registrar") != "authority_only_register_exact_package_and_scenario" or lifecycle.get("executor") != "open_existing_consume_reverify_verify_grant_before_runtime" or lifecycle.get("post_consume") != "materialize_runtime_then_import_m2" or lifecycle.get("crash_recovery") != "consumed_without_terminal_outcome_unknown":
            raise M2A1ExecutionPreflightError("execution_package_receipt_lifecycle_invalid")
    elif contract is _V2_4_PACKAGE_CONTRACT:
        _validate_v2_4_package_contract(package, contract)
    elif contract is _V2_5_PACKAGE_CONTRACT:
        _validate_v2_5_package_contract(package, contract)
    elif contract is _V2_6_PACKAGE_CONTRACT:
        _validate_v2_6_package_contract(package, contract)
    elif contract is _V2_7_PACKAGE_CONTRACT:
        _validate_v2_7_package_contract(package, contract)
    elif contract is _V2_8_PACKAGE_CONTRACT:
        _validate_v2_8_package_contract(package, contract)
    elif contract is _V2_9_PACKAGE_CONTRACT:
        _validate_v2_9_package_contract(package, contract)
    else:
        _validate_v2_10_package_contract(package, contract)
    hashes = package.get("input_file_sha256")
    if not isinstance(hashes, Mapping) or not hashes or any(not isinstance(path, str) or not _is_sha256(str(value)) for path, value in hashes.items()):
        raise M2A1ExecutionPreflightError("execution_package_input_hash_schema_invalid")
    return contract


def _verify_index_and_working_inputs(
    repository_root: Path,
    input_file_sha256: Mapping[str, Any],
    *,
    index_reader: Callable[[Path, str], bytes] = _git_index_bytes,
    working_reader: Callable[[Path], bytes] = lambda path: path.read_bytes(),
) -> None:
    for relative_path, expected_sha256 in sorted(input_file_sha256.items()):
        if not isinstance(relative_path, str) or Path(relative_path).is_absolute() or ".." in Path(relative_path).parts:
            raise M2A1ExecutionPreflightError("execution_package_input_path_invalid")
        index_bytes = index_reader(repository_root, relative_path)
        if hashlib.sha256(index_bytes).hexdigest() != expected_sha256:
            raise M2A1ExecutionPreflightError(f"execution_git_index_hash_mismatch:{relative_path}")
        working_path = repository_root / relative_path
        try:
            working_bytes = working_reader(working_path)
        except OSError as exc:
            raise M2A1ExecutionPreflightError(f"execution_working_input_missing:{relative_path}") from exc
        if _normalised_execution_bytes(working_bytes) != _normalised_execution_bytes(index_bytes):
            raise M2A1ExecutionPreflightError(f"execution_working_index_drift:{relative_path}")


def _verify_v2_4_phase_a_artifacts(
    package: Mapping[str, Any],
    repository_root: Path,
    *,
    index_reader: Callable[[Path, str], bytes],
) -> None:
    """Prove Phase-A digests came from exact staged artifacts, not self-report."""

    phase_a = package["phase_a_digests"]
    bindings = package["phase_a_artifacts"]
    for name, binding in bindings.items():
        staged = index_reader(repository_root, str(binding["relative_path"]))
        try:
            artifact = json.loads(staged.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise M2A1ExecutionPreflightError(f"execution_phase_a_artifact_json_invalid:{name}") from exc
        if not isinstance(artifact, Mapping) or artifact.get(binding["digest_field"]) != phase_a[name]:
            raise M2A1ExecutionPreflightError(f"execution_phase_a_artifact_digest_mismatch:{name}")


def _verify_v2_5_incident_evidence(
    package: Mapping[str, Any],
    repository_root: Path,
    *,
    index_reader: Callable[[Path, str], bytes],
) -> None:
    incident = package["incident_evidence"]
    for path_key, digest_key, field in (
        ("relative_path", "incident_digest", "incident_digest"),
        ("expired_terminal_relative_path", "expired_terminal_digest", "expired_terminal_digest"),
    ):
        staged = index_reader(repository_root, str(incident[path_key]))
        try:
            artifact = json.loads(staged.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise M2A1ExecutionPreflightError("execution_incident_evidence_json_invalid") from exc
        if not isinstance(artifact, Mapping) or artifact.get(field) != incident[digest_key]:
            raise M2A1ExecutionPreflightError("execution_incident_evidence_digest_mismatch")
    if incident_artifact := json.loads(index_reader(repository_root, str(incident["relative_path"])).decode("utf-8")):
        if not isinstance(incident_artifact, Mapping) or incident_artifact.get("receipt_digest") != "596fcf570a7abc1d4344ec6db354a4670e1c8a59e48f97396d5bf27c2401b870":
            raise M2A1ExecutionPreflightError("execution_incident_receipt_identity_mismatch")
    terminal_artifact = json.loads(index_reader(repository_root, str(incident["expired_terminal_relative_path"])).decode("utf-8"))
    if not isinstance(terminal_artifact, Mapping) or terminal_artifact.get("status") not in {"expired_unconsumed", "already_expired_unconsumed_exact"} or terminal_artifact.get("receipt_digest") != "596fcf570a7abc1d4344ec6db354a4670e1c8a59e48f97396d5bf27c2401b870" or terminal_artifact.get("incident_digest") != incident["incident_digest"]:
        raise M2A1ExecutionPreflightError("execution_expired_terminal_identity_mismatch")


def _bound_json_input(
    package: Mapping[str, Any],
    preflight_contract: Mapping[str, Any],
    kind: str,
    repository_root: Path,
    *,
    index_reader: Callable[[Path, str], bytes],
) -> tuple[Path, Mapping[str, Any]]:
    runtime_inputs = preflight_contract.get("runtime_inputs")
    if not isinstance(runtime_inputs, Mapping) or not isinstance(runtime_inputs.get(kind), Mapping):
        raise M2A1ExecutionPreflightError("execution_runtime_input_binding_missing")
    binding = runtime_inputs[kind]
    relative_path = binding.get("relative_path")
    expected_digest = binding.get("canonical_digest")
    if not isinstance(relative_path, str) or not _is_sha256(str(expected_digest)):
        raise M2A1ExecutionPreflightError("execution_runtime_input_binding_invalid")
    input_hashes = package["input_file_sha256"]
    if relative_path not in input_hashes:
        raise M2A1ExecutionPreflightError(f"execution_runtime_input_not_in_package:{kind}")
    staged_bytes = index_reader(repository_root, relative_path)
    if hashlib.sha256(staged_bytes).hexdigest() != input_hashes[relative_path]:
        raise M2A1ExecutionPreflightError(f"execution_runtime_input_index_hash_mismatch:{kind}")
    try:
        parsed = json.loads(staged_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise M2A1ExecutionPreflightError(f"execution_runtime_input_json_invalid:{kind}") from exc
    if not isinstance(parsed, Mapping) or canonical_digest(parsed) != expected_digest:
        raise M2A1ExecutionPreflightError(f"execution_runtime_input_digest_mismatch:{kind}")
    return repository_root / relative_path, parsed


def _derived_run_root(namespace: Path, *, package_digest: str, admission_digest: str, receipt_id: str) -> Path:
    if not _RECEIPT_ID_RE.fullmatch(receipt_id):
        raise M2A1ExecutionPreflightError("execution_receipt_id_invalid")
    run_id = hashlib.sha256(f"{package_digest}:{admission_digest}:{receipt_id}".encode("utf-8")).hexdigest()
    return namespace / run_id


def preflight_exact_execution(
    package: Mapping[str, Any],
    admission: M2A1ExternalPackageAdmission | None,
    *,
    repository_root: Path,
    receipt_id: str,
    scenario_id: str,
    human_approval_digest: str | None = None,
    index_reader: Callable[[Path, str], bytes] = _git_index_bytes,
    working_reader: Callable[[Path], bytes] = lambda path: path.read_bytes(),
    fixed_fingerprint_reader: Callable[[Path], str] = _sha256_file,
    now: datetime | None = None,
) -> M2A1ExecutionPreflight:
    """Validate exact package/code/inputs before any mutable execution resource exists."""

    root = repository_root.resolve()
    package_contract = _validate_package_identity(package)
    _verify_index_and_working_inputs(root, package["input_file_sha256"], index_reader=index_reader, working_reader=working_reader)
    if package_contract in {_V2_4_PACKAGE_CONTRACT, _V2_5_PACKAGE_CONTRACT, _V2_6_PACKAGE_CONTRACT, _V2_7_PACKAGE_CONTRACT, _V2_8_PACKAGE_CONTRACT, _V2_9_PACKAGE_CONTRACT, _V2_10_PACKAGE_CONTRACT}:
        _verify_v2_4_phase_a_artifacts(package, root, index_reader=index_reader)
    if package_contract in {_V2_5_PACKAGE_CONTRACT, _V2_6_PACKAGE_CONTRACT, _V2_7_PACKAGE_CONTRACT, _V2_8_PACKAGE_CONTRACT, _V2_9_PACKAGE_CONTRACT, _V2_10_PACKAGE_CONTRACT}:
        _verify_v2_5_incident_evidence(package, root, index_reader=index_reader)
    contract = package.get("execution_preflight")
    if not isinstance(contract, Mapping):
        raise M2A1ExecutionPreflightError("execution_preflight_contract_missing")
    namespace_id = contract.get("execution_staging_namespace_id")
    namespace_raw = contract.get("execution_staging_namespace_path")
    if not isinstance(namespace_id, str) or not isinstance(namespace_raw, str):
        raise M2A1ExecutionPreflightError("execution_staging_namespace_contract_invalid")
    admission_check = validate_external_admission(
        admission,
        package_ref=str(package["package_ref"]),
        executable_package_digest=str(package["package_digest"]),
        scope=str(package["scope"]),
        authority_boundary=str(package["authority_boundary"]),
        execution_staging_namespace_id=namespace_id,
        expected_schema_version=package_contract.admission_schema_version,
        expected_human_approval_digest=human_approval_digest,
        now=now,
    )
    if admission_check["status"] != "pass" or admission is None:
        raise M2A1ExecutionPreflightError(str(admission_check["status"]))
    namespace = Path(namespace_raw)
    if not namespace.is_absolute() or namespace != Path(namespace_raw).resolve():
        raise M2A1ExecutionPreflightError("execution_staging_namespace_not_canonical_absolute")
    if any(part in {".runtime_control", "data", "archive"} for part in namespace.parts):
        raise M2A1ExecutionPreflightError("execution_staging_namespace_forbidden_root")
    _assert_no_reparse_escape(namespace.parent, namespace)
    corpus_path, corpus = _bound_json_input(package, contract, "corpus", root, index_reader=index_reader)
    matrix_path, matrix = _bound_json_input(package, contract, "scenario_matrix", root, index_reader=index_reader)
    policy_path, _ = _bound_json_input(package, contract, "execution_policy", root, index_reader=index_reader)
    scenarios = matrix.get("scenarios")
    if not isinstance(scenarios, list):
        raise M2A1ExecutionPreflightError("execution_scenario_matrix_invalid")
    scenario = next((item for item in scenarios if isinstance(item, Mapping) and item.get("scenario_id") == scenario_id), None)
    if scenario is None:
        raise M2A1ExecutionPreflightError("execution_scenario_not_bound")
    runtime_scenario = {key: str(scenario[key]) for key in ("scenario_id", "input_ref", "mutation") if key in scenario}
    if set(runtime_scenario) != {"scenario_id", "input_ref", "mutation"}:
        raise M2A1ExecutionPreflightError("execution_runtime_scenario_shape_invalid")
    cases = corpus.get("cases")
    corpus_case = next((item for item in cases if isinstance(item, Mapping) and item.get("case_id") == runtime_scenario["input_ref"]), None) if isinstance(cases, list) else None
    if corpus_case is None:
        raise M2A1ExecutionPreflightError("execution_scenario_corpus_binding_invalid")
    fixed = package.get("fixed_store_fingerprints")
    if not isinstance(fixed, Mapping) or not isinstance(fixed.get("fixed_approval_store"), Mapping):
        raise M2A1ExecutionPreflightError("execution_fixed_store_fingerprint_missing")
    fixed_store = fixed["fixed_approval_store"]
    fixed_relative = fixed_store.get("path")
    expected_fixed_sha = fixed_store.get("sha256")
    if not isinstance(fixed_relative, str) or not _is_sha256(str(expected_fixed_sha)):
        raise M2A1ExecutionPreflightError("execution_fixed_store_fingerprint_invalid")
    fixed_path = (root / fixed_relative).resolve()
    if fixed_path != (root / ".runtime_control/point01_m6_3_5_nvda_sec_document_parser_repaired_global_approval/canonical.sqlite").resolve():
        raise M2A1ExecutionPreflightError("execution_fixed_store_path_invalid")
    if fixed_fingerprint_reader(fixed_path) != expected_fixed_sha:
        raise M2A1ExecutionPreflightError("execution_fixed_store_fingerprint_mismatch")
    run_root = _derived_run_root(namespace, package_digest=str(package["package_digest"]), admission_digest=admission.admission_digest, receipt_id=receipt_id)
    _assert_no_reparse_escape(namespace, run_root)
    authority_root = run_root / "authority"
    runtime_root = run_root / "runtime"
    output_path = run_root / "output" / f"{scenario_id}.actual_result.json"
    for path in (authority_root, runtime_root, output_path):
        _assert_no_reparse_escape(namespace, path)
    payload = {
        "package_digest": package["package_digest"],
        "admission_digest": admission.admission_digest,
        "receipt_id": receipt_id,
        "scenario_id": scenario_id,
        "execution_staging_namespace": str(namespace),
        "run_root": str(run_root),
        "authority_root": str(authority_root),
        "runtime_root": str(runtime_root),
        "output_path": str(output_path),
        "corpus_path": str(corpus_path),
        "matrix_path": str(matrix_path),
        "policy_path": str(policy_path),
        "fixed_store_path": str(fixed_path),
        "input_count": len(package["input_file_sha256"]),
    }
    if package_contract in {_V2_7_PACKAGE_CONTRACT, _V2_8_PACKAGE_CONTRACT, _V2_9_PACKAGE_CONTRACT, _V2_10_PACKAGE_CONTRACT} and human_approval_digest is None:
        raise M2A1ExecutionPreflightError("human_approval_digest_required")
    return M2A1ExecutionPreflight(
        repository_root=root,
        package=package,
        package_contract=package_contract,
        admission=admission,
        human_approval_digest=human_approval_digest,
        receipt_id=receipt_id,
        scenario_id=scenario_id,
        execution_staging_namespace=namespace,
        run_root=run_root,
        authority_root=authority_root,
        ledger_path=authority_root / "m2_a1_execution_receipts.sqlite",
        runtime_root=runtime_root,
        output_path=output_path,
        fixed_store_path=fixed_path,
        corpus_case=corpus_case,
        runtime_scenario=runtime_scenario,
        input_count=len(package["input_file_sha256"]),
        preflight_digest=canonical_digest(payload),
    )


class M2A1ReceiptLedger:
    """Append-only receipt ledger with explicit registrar/executor factories.

    A registrar is the sole lifecycle phase allowed to create/migrate the
    authority SQLite file.  The executor opens an already-existing database in
    ``mode=rw``; it cannot manufacture an authority root or receipt ledger.
    """

    def __init__(self, db_path: str | Path, *, approved_authority_root: str | Path, lifecycle_mode: str) -> None:
        # Do not call ``resolve`` here: resolving first would erase the very
        # symlink/reparse component that this constructor must reject.
        self.approved_authority_root = Path(approved_authority_root).absolute()
        self.db_path = Path(db_path).absolute()
        expected = self.approved_authority_root / "m2_a1_execution_receipts.sqlite"
        if self.db_path != expected or ".runtime_control" in self.db_path.parts:
            raise M2A1ReceiptAuthorityError("m2_a1_receipt_ledger_path_not_preflight_bound")
        if lifecycle_mode not in {"registration_create", "existing_no_create"}:
            raise M2A1ReceiptAuthorityError("m2_a1_receipt_ledger_lifecycle_mode_invalid")
        _assert_no_reparse_escape(self.approved_authority_root.parent, self.approved_authority_root)
        if lifecycle_mode == "registration_create":
            if not self.approved_authority_root.is_dir():
                raise M2A1ReceiptAuthorityError("receipt_registration_authority_root_missing")
            _assert_no_reparse_escape(self.approved_authority_root, self.db_path)
            if self.db_path.exists():
                self._validate_existing_schema()
            else:
                self._migrate_create()
            return
        if not self.approved_authority_root.is_dir() or not self.db_path.is_file():
            raise M2A1ReceiptAuthorityError("receipt_ledger_not_registered_no_create")
        _assert_no_reparse_escape(self.approved_authority_root, self.db_path)
        self._validate_existing_schema()

    @classmethod
    def create_for_registration(cls, db_path: str | Path, *, approved_authority_root: str | Path) -> "M2A1ReceiptLedger":
        return cls(db_path, approved_authority_root=approved_authority_root, lifecycle_mode="registration_create")

    @classmethod
    def open_existing(cls, db_path: str | Path, *, approved_authority_root: str | Path) -> "M2A1ReceiptLedger":
        return cls(db_path, approved_authority_root=approved_authority_root, lifecycle_mode="existing_no_create")

    def _connect(self, *, create: bool = False) -> sqlite3.Connection:
        if create:
            connection = sqlite3.connect(self.db_path, isolation_level=None)
        else:
            connection = sqlite3.connect(f"{self.db_path.as_uri()}?mode=rw", uri=True, isolation_level=None)
        connection.row_factory = sqlite3.Row
        return connection

    def _migrate_create(self) -> None:
        with self._connect(create=True) as connection:
            connection.executescript(
                """
                create table if not exists point01_m2_a1_execution_receipts (
                    receipt_id text primary key,
                    admission_digest text not null unique,
                    receipt_digest text not null,
                    state text not null,
                    payload_json text not null,
                    registered_at text not null,
                    consumed_at text
                );
                create table if not exists point01_m2_a1_execution_receipt_events (
                    event_id integer primary key autoincrement,
                    receipt_id text not null,
                    event_type text not null,
                    recorded_at text not null,
                    payload_digest text not null,
                    payload_json text not null,
                    unique(receipt_id, event_type)
                );
                """
            )
            for ddl in _EVENT_APPEND_ONLY_TRIGGER_DDL.values():
                connection.execute(ddl)

    def _validate_existing_schema(self) -> None:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    "select name from sqlite_master where type = 'table' and name in (?, ?)",
                    ("point01_m2_a1_execution_receipts", "point01_m2_a1_execution_receipt_events"),
                ).fetchall()
                triggers = connection.execute(
                    "select name, sql from sqlite_master where type = 'trigger' and name in (?, ?)",
                    (
                        "point01_m2_a1_execution_receipt_events_no_update",
                        "point01_m2_a1_execution_receipt_events_no_delete",
                    ),
                ).fetchall()
        except sqlite3.Error as exc:
            raise M2A1ReceiptAuthorityError("receipt_ledger_existing_open_failed") from exc
        if {str(row["name"]) for row in rows} != {"point01_m2_a1_execution_receipts", "point01_m2_a1_execution_receipt_events"}:
            raise M2A1ReceiptAuthorityError("receipt_ledger_schema_missing_no_create")
        observed = {str(row["name"]): _normalise_event_trigger_ddl(str(row["sql"] or "")) for row in triggers}
        if set(observed) != set(_NORMALISED_EVENT_APPEND_ONLY_TRIGGER_DDL):
            raise M2A1ReceiptAuthorityError("receipt_ledger_event_append_only_triggers_missing")
        if observed != _NORMALISED_EVENT_APPEND_ONLY_TRIGGER_DDL:
            raise M2A1ReceiptAuthorityError("receipt_ledger_event_append_only_trigger_invalid")

    @staticmethod
    def _event_payload_from_row(row: sqlite3.Row | None, *, event_type: str, error_prefix: str) -> Mapping[str, Any]:
        """Decode one immutable event and make its digest part of every read.

        Events are the source of truth; the ``receipts`` table deliberately is
        a mutable lifecycle projection.  Never use an event payload before
        proving that its stored canonical digest still matches.
        """

        if row is None:
            raise M2A1ReceiptAuthorityError(f"{error_prefix}_{event_type.lower()}_missing")
        try:
            payload = json.loads(str(row["payload_json"]))
        except (TypeError, json.JSONDecodeError) as exc:
            raise M2A1ReceiptAuthorityError(f"{error_prefix}_{event_type.lower()}_payload_invalid") from exc
        if not isinstance(payload, Mapping):
            raise M2A1ReceiptAuthorityError(f"{error_prefix}_{event_type.lower()}_payload_invalid")
        if str(row["payload_digest"]) != canonical_digest(payload):
            raise M2A1ReceiptAuthorityError(f"{error_prefix}_{event_type.lower()}_payload_digest_mismatch")
        return payload

    @staticmethod
    def _registered_event_payload(*, receipt_digest: str, admission_digest: str, human_approval_digest: str | None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "receipt_digest": receipt_digest,
            "admission_digest": admission_digest,
            "state": "active_unconsumed",
        }
        if human_approval_digest is not None:
            payload["human_approval_digest"] = human_approval_digest
        return payload

    @staticmethod
    def _assert_exact_event_payload(actual: Mapping[str, Any], expected: Mapping[str, Any], *, error: str) -> None:
        if dict(actual) != dict(expected):
            raise M2A1ReceiptAuthorityError(error)

    @staticmethod
    def _now(now: datetime | None = None) -> datetime:
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None or current.utcoffset() != timezone.utc.utcoffset(current):
            raise M2A1ReceiptAuthorityError("receipt_ledger_now_must_be_utc")
        return current

    def register(
        self,
        receipt: M2A1ExecutionReceipt,
        *,
        admission: M2A1ExternalPackageAdmission,
        package_ref: str,
        executable_package_digest: str,
        scope: str,
        authority_boundary: str,
        execution_staging_namespace_id: str | None = None,
        scenario_id: str | None = None,
        expected_admission_schema_version: str | None = None,
        expected_receipt_schema_version: str | None = None,
        expected_human_approval_digest: str | None = None,
        now: datetime | None = None,
    ) -> dict[str, str]:
        current = self._now(now)
        if not _is_sha256(executable_package_digest) or receipt.executable_package_digest != executable_package_digest:
            raise M2A1ReceiptAuthorityError("receipt_executable_package_digest_mismatch")
        admission_check = validate_external_admission(
            admission,
            package_ref=package_ref,
            executable_package_digest=executable_package_digest,
            scope=scope,
            authority_boundary=authority_boundary,
            execution_staging_namespace_id=execution_staging_namespace_id,
            expected_schema_version=expected_admission_schema_version,
            expected_human_approval_digest=expected_human_approval_digest,
            now=current,
        )
        if admission_check["status"] != "pass":
            raise M2A1ReceiptAuthorityError(str(admission_check["status"]))
        check = validate_unconsumed_receipt(
            receipt,
            package_ref=package_ref,
            executable_package_digest=executable_package_digest,
            scope=scope,
            admission=admission,
            authority_boundary=authority_boundary,
            execution_staging_namespace_id=execution_staging_namespace_id,
            scenario_id=scenario_id,
            expected_admission_schema_version=expected_admission_schema_version,
            expected_receipt_schema_version=expected_receipt_schema_version,
            expected_human_approval_digest=expected_human_approval_digest,
            now=current,
        )
        if check["status"] != "pass":
            raise M2A1ReceiptAuthorityError(str(check["status"]))
        payload = receipt.model_dump(mode="json")
        event_payload = self._registered_event_payload(
            receipt_digest=receipt.receipt_digest,
            admission_digest=admission.admission_digest,
            human_approval_digest=receipt.human_approval_digest if _requires_human_approval_lineage(receipt.schema_version) else None,
        )
        try:
            with self._connect() as connection:
                connection.execute("begin immediate")
                existing = connection.execute(
                    "select admission_digest, receipt_digest, state, payload_json from point01_m2_a1_execution_receipts where receipt_id = ?",
                    (receipt.receipt_id,),
                ).fetchone()
                if existing is not None:
                    if (
                        str(existing["admission_digest"]) != receipt.admission_digest
                        or str(existing["receipt_digest"]) != receipt.receipt_digest
                        or str(existing["state"]) != "active_unconsumed"
                        or json.loads(str(existing["payload_json"])) != payload
                    ):
                        connection.rollback()
                        raise M2A1ReceiptAuthorityError("receipt_registration_binding_mismatch")
                    event = connection.execute(
                        "select payload_digest, payload_json from point01_m2_a1_execution_receipt_events where receipt_id = ? and event_type = ?",
                        (receipt.receipt_id, "REGISTERED"),
                    ).fetchone()
                    try:
                        existing_event_payload = self._event_payload_from_row(event, event_type="REGISTERED", error_prefix="receipt_registration_event")
                        self._assert_exact_event_payload(existing_event_payload, event_payload, error="receipt_registration_event_mismatch")
                    except M2A1ReceiptAuthorityError:
                        connection.rollback()
                        raise
                    connection.commit()
                    return {"receipt_digest": receipt.receipt_digest, "registration_status": "already_registered_exact"}
                connection.execute(
                    "insert into point01_m2_a1_execution_receipts (receipt_id, admission_digest, receipt_digest, state, payload_json, registered_at) values (?, ?, ?, ?, ?, ?)",
                    (receipt.receipt_id, receipt.admission_digest, receipt.receipt_digest, receipt.state, json.dumps(payload, sort_keys=True), current.isoformat()),
                )
                connection.execute(
                    "insert into point01_m2_a1_execution_receipt_events (receipt_id, event_type, recorded_at, payload_digest, payload_json) values (?, ?, ?, ?, ?)",
                    (receipt.receipt_id, "REGISTERED", current.isoformat(), canonical_digest(event_payload), json.dumps(event_payload, sort_keys=True)),
                )
                connection.commit()
        except sqlite3.IntegrityError as exc:
            raise M2A1ReceiptAuthorityError("receipt_or_admission_already_registered") from exc
        return {"receipt_digest": receipt.receipt_digest, "registration_status": "registered"}

    def consume_before_run(
        self,
        receipt_id: str,
        *,
        admission: M2A1ExternalPackageAdmission,
        package_ref: str,
        executable_package_digest: str,
        scope: str,
        authority_boundary: str,
        preflight_digest: str,
        run_root: str | Path,
        execution_staging_namespace_id: str | None = None,
        scenario_id: str | None = None,
        expected_admission_schema_version: str | None = None,
        expected_receipt_schema_version: str | None = None,
        expected_human_approval_digest: str | None = None,
        now: datetime | None = None,
    ) -> M2A1ConsumptionGrant:
        current = self._now(now)
        normalized_run_root = Path(run_root).absolute()
        if not _is_sha256(preflight_digest):
            raise M2A1ReceiptAuthorityError("receipt_consumption_preflight_digest_invalid")
        if normalized_run_root != self.approved_authority_root.parent:
            raise M2A1ReceiptAuthorityError("receipt_consumption_run_root_mismatch")
        with self._connect() as connection:
            connection.execute("begin immediate")
            row = connection.execute(
                "select payload_json, state from point01_m2_a1_execution_receipts where receipt_id = ?", (receipt_id,)
            ).fetchone()
            if row is None:
                connection.rollback()
                raise M2A1ReceiptAuthorityError("receipt_not_registered")
            receipt = M2A1ExecutionReceipt.model_validate(json.loads(str(row["payload_json"])))
            check = validate_unconsumed_receipt(
                receipt,
                package_ref=package_ref,
                executable_package_digest=executable_package_digest,
                scope=scope,
                admission=admission,
                authority_boundary=authority_boundary,
                execution_staging_namespace_id=execution_staging_namespace_id,
                scenario_id=scenario_id,
                expected_admission_schema_version=expected_admission_schema_version,
                expected_receipt_schema_version=expected_receipt_schema_version,
                expected_human_approval_digest=expected_human_approval_digest,
                now=current,
            )
            if check["status"] != "pass" or str(row["state"]) != "active_unconsumed":
                connection.rollback()
                raise M2A1ReceiptAuthorityError(str(check["status"]))
            if _requires_human_approval_lineage(receipt.schema_version):
                registered_event = connection.execute(
                    "select payload_digest, payload_json from point01_m2_a1_execution_receipt_events where receipt_id = ? and event_type = ?",
                    (receipt.receipt_id, "REGISTERED"),
                ).fetchone()
                try:
                    registered_payload = self._event_payload_from_row(
                        registered_event,
                        event_type="REGISTERED",
                        error_prefix="receipt_consumption_registered_event",
                    )
                    self._assert_exact_event_payload(
                        registered_payload,
                        self._registered_event_payload(
                            receipt_digest=receipt.receipt_digest,
                            admission_digest=admission.admission_digest,
                            human_approval_digest=expected_human_approval_digest,
                        ),
                        error="receipt_consumption_registered_event_binding_mismatch",
                    )
                except M2A1ReceiptAuthorityError:
                    connection.rollback()
                    raise
            consumed = M2A1ExecutionReceipt.create(
                receipt_id=receipt.receipt_id,
                receipt_version=receipt.receipt_version,
                approval_id=receipt.approval_id,
                package_ref=receipt.package_ref,
                executable_package_digest=receipt.executable_package_digest,
                scope=receipt.scope,
                admission_digest=receipt.admission_digest,
                nonce_sha256=receipt.nonce_sha256,
                expires_at=receipt.expires_at,
                reviewer_identity=receipt.reviewer_identity,
                execution_staging_namespace_id=receipt.execution_staging_namespace_id,
                scenario_id=receipt.scenario_id,
                state="consumed_before_run",
                schema_version=receipt.schema_version,
                human_approval_digest=receipt.human_approval_digest,
            )
            grant = M2A1ConsumptionGrant.create(
                receipt_id=receipt.receipt_id,
                consumed_receipt_digest=consumed.receipt_digest,
                admission_digest=admission.admission_digest,
                executable_package_digest=executable_package_digest,
                scenario_id=receipt.scenario_id,
                run_root=str(normalized_run_root),
                preflight_digest=preflight_digest,
                human_approval_digest=receipt.human_approval_digest,
            )
            event_payload = {
                "grant": grant.model_dump(mode="json"),
                "prior_receipt_digest": receipt.receipt_digest,
            }
            if _requires_human_approval_lineage(receipt.schema_version):
                event_payload["human_approval_digest"] = receipt.human_approval_digest
            updated = connection.execute(
                "update point01_m2_a1_execution_receipts set receipt_digest = ?, state = ?, payload_json = ?, consumed_at = ? where receipt_id = ? and state = ?",
                (consumed.receipt_digest, consumed.state, json.dumps(consumed.model_dump(mode="json"), sort_keys=True), current.isoformat(), receipt_id, "active_unconsumed"),
            )
            if updated.rowcount != 1:
                connection.rollback()
                raise M2A1ReceiptAuthorityError("receipt_already_consumed")
            connection.execute(
                "insert into point01_m2_a1_execution_receipt_events (receipt_id, event_type, recorded_at, payload_digest, payload_json) values (?, ?, ?, ?, ?)",
                (receipt_id, "CONSUMED_BEFORE_RUN", current.isoformat(), canonical_digest(event_payload), json.dumps(event_payload, sort_keys=True)),
            )
            connection.commit()
        return grant

    def expire_unconsumed_exact(
        self,
        receipt_id: str,
        *,
        admission: M2A1ExternalPackageAdmission,
        executable_package_digest: str,
        scenario_id: str,
        now: datetime | None = None,
    ) -> dict[str, str]:
        """Append the sole permitted terminal for an expired unconsumed receipt.

        This is deliberately narrower than normal lifecycle handling: it may
        only transition ``active_unconsumed`` after both the receipt and its
        bound admission have actually expired.  It never alters the receipt
        payload, expiry, nonce digest, or receipt digest, so the historical
        registered authority remains independently auditable.
        """

        current = self._now(now)
        if not _is_sha256(executable_package_digest):
            raise M2A1ReceiptAuthorityError("receipt_expiry_terminal_package_digest_invalid")
        if not _RECEIPT_ID_RE.fullmatch(receipt_id):
            raise M2A1ReceiptAuthorityError("receipt_expiry_terminal_receipt_id_invalid")
        if not admission.verify_digest():
            raise M2A1ReceiptAuthorityError("receipt_expiry_terminal_admission_digest_invalid")
        with self._connect() as connection:
            connection.execute("begin immediate")
            row = connection.execute(
                "select admission_digest, receipt_digest, state, payload_json, consumed_at from point01_m2_a1_execution_receipts where receipt_id = ?",
                (receipt_id,),
            ).fetchone()
            if row is None:
                connection.rollback()
                raise M2A1ReceiptAuthorityError("receipt_expiry_terminal_receipt_not_registered")
            if str(row["admission_digest"]) != admission.admission_digest:
                connection.rollback()
                raise M2A1ReceiptAuthorityError("receipt_expiry_terminal_admission_binding_mismatch")
            receipt = M2A1ExecutionReceipt.model_validate(json.loads(str(row["payload_json"])))
            if (
                receipt.receipt_id != receipt_id
                or receipt.admission_digest != admission.admission_digest
                or receipt.executable_package_digest != executable_package_digest
                or receipt.scenario_id != scenario_id
                or receipt.state != "active_unconsumed"
                or receipt.receipt_digest != str(row["receipt_digest"])
            ):
                connection.rollback()
                raise M2A1ReceiptAuthorityError("receipt_expiry_terminal_receipt_binding_mismatch")
            if current <= receipt.expires_at or current <= admission.expires_at:
                connection.rollback()
                raise M2A1ReceiptAuthorityError("receipt_expiry_terminal_not_yet_expired")
            event_payload = {
                "admission_digest": admission.admission_digest,
                "receipt_digest": receipt.receipt_digest,
                "terminal_status": "expired_unconsumed",
                "reason": "receipt_and_admission_expiry_reached_without_consumption",
            }
            if str(row["state"]) == "expired_unconsumed":
                event = connection.execute(
                    "select payload_digest from point01_m2_a1_execution_receipt_events where receipt_id = ? and event_type = ?",
                    (receipt_id, "EXPIRED_UNCONSUMED"),
                ).fetchone()
                if event is None or str(event["payload_digest"]) != canonical_digest(event_payload):
                    connection.rollback()
                    raise M2A1ReceiptAuthorityError("receipt_expiry_terminal_event_mismatch")
                connection.commit()
                return {
                    "receipt_digest": receipt.receipt_digest,
                    "terminal_event_digest": canonical_digest(event_payload),
                    "terminal_status": "already_expired_unconsumed_exact",
                }
            if str(row["state"]) != "active_unconsumed" or row["consumed_at"] is not None:
                connection.rollback()
                raise M2A1ReceiptAuthorityError("receipt_expiry_terminal_state_not_eligible")
            updated = connection.execute(
                "update point01_m2_a1_execution_receipts set state = ? where receipt_id = ? and state = ? and consumed_at is null",
                ("expired_unconsumed", receipt_id, "active_unconsumed"),
            )
            if updated.rowcount != 1:
                connection.rollback()
                raise M2A1ReceiptAuthorityError("receipt_expiry_terminal_concurrent_state_change")
            try:
                connection.execute(
                    "insert into point01_m2_a1_execution_receipt_events (receipt_id, event_type, recorded_at, payload_digest, payload_json) values (?, ?, ?, ?, ?)",
                    (receipt_id, "EXPIRED_UNCONSUMED", current.isoformat(), canonical_digest(event_payload), json.dumps(event_payload, sort_keys=True)),
                )
            except sqlite3.IntegrityError as exc:
                connection.rollback()
                raise M2A1ReceiptAuthorityError("receipt_expiry_terminal_event_already_recorded") from exc
            connection.commit()
        return {
            "receipt_digest": receipt.receipt_digest,
            "terminal_event_digest": canonical_digest(event_payload),
            "terminal_status": "expired_unconsumed",
        }

    def verify_consumption_grant(
        self,
        grant: M2A1ConsumptionGrant,
        *,
        admission: M2A1ExternalPackageAdmission,
        package_ref: str,
        executable_package_digest: str,
        scope: str,
        authority_boundary: str,
        execution_staging_namespace_id: str,
        scenario_id: str,
        run_root: Path,
        preflight_digest: str,
        expected_admission_schema_version: str | None = None,
        expected_receipt_schema_version: str | None = None,
        expected_human_approval_digest: str | None = None,
    ) -> M2A1ExecutionReceipt:
        """Return the stored consumed receipt only for an exact event-backed grant."""

        if not grant.verify_digest():
            raise M2A1ReceiptAuthorityError("receipt_consumption_grant_digest_invalid")
        expected = {
            "admission_digest": admission.admission_digest,
            "executable_package_digest": executable_package_digest,
            "scenario_id": scenario_id,
            "run_root": str(run_root.absolute()),
            "preflight_digest": preflight_digest,
            "state": "consumed_before_run",
        }
        if expected_human_approval_digest is not None:
            expected["human_approval_digest"] = expected_human_approval_digest
        if any(getattr(grant, field) != value for field, value in expected.items()):
            raise M2A1ReceiptAuthorityError("receipt_consumption_grant_binding_mismatch")
        if grant.run_root != str(self.approved_authority_root.parent):
            raise M2A1ReceiptAuthorityError("receipt_consumption_grant_authority_root_mismatch")
        with self._connect() as connection:
            row = connection.execute(
                "select payload_json, receipt_digest, state from point01_m2_a1_execution_receipts where receipt_id = ?",
                (grant.receipt_id,),
            ).fetchone()
            registered_event = connection.execute(
                "select payload_digest, payload_json from point01_m2_a1_execution_receipt_events where receipt_id = ? and event_type = ?",
                (grant.receipt_id, "REGISTERED"),
            ).fetchone()
            event = connection.execute(
                "select payload_digest, payload_json from point01_m2_a1_execution_receipt_events where receipt_id = ? and event_type = ?",
                (grant.receipt_id, "CONSUMED_BEFORE_RUN"),
            ).fetchone()
        if row is None or str(row["state"]) != "consumed_before_run":
            raise M2A1ReceiptAuthorityError("receipt_consumption_grant_receipt_not_consumed")
        consumed = M2A1ExecutionReceipt.model_validate(json.loads(str(row["payload_json"])))
        if str(row["receipt_digest"]) != grant.consumed_receipt_digest or consumed.receipt_digest != grant.consumed_receipt_digest:
            raise M2A1ReceiptAuthorityError("receipt_consumption_grant_receipt_digest_mismatch")
        receipt_check = validate_external_admission(
            admission,
            package_ref=package_ref,
            executable_package_digest=executable_package_digest,
            scope=scope,
            authority_boundary=authority_boundary,
            execution_staging_namespace_id=execution_staging_namespace_id,
            expected_schema_version=expected_admission_schema_version,
            expected_human_approval_digest=expected_human_approval_digest,
        )
        if receipt_check["status"] != "pass":
            raise M2A1ReceiptAuthorityError(str(receipt_check["status"]))
        if expected_receipt_schema_version is not None and consumed.schema_version != expected_receipt_schema_version:
            raise M2A1ReceiptAuthorityError("receipt_schema_version_mismatch")
        if (
            consumed.package_ref != package_ref
            or consumed.executable_package_digest != executable_package_digest
            or consumed.scope != scope
            or consumed.admission_digest != admission.admission_digest
            or consumed.execution_staging_namespace_id != execution_staging_namespace_id
            or consumed.scenario_id != scenario_id
            or consumed.state != "consumed_before_run"
            or (expected_human_approval_digest is not None and consumed.human_approval_digest != expected_human_approval_digest)
        ):
            raise M2A1ReceiptAuthorityError("receipt_consumption_grant_consumed_receipt_binding_mismatch")
        event_payload = self._event_payload_from_row(
            event,
            event_type="CONSUMED_BEFORE_RUN",
            error_prefix="receipt_consumption_grant_event",
        )
        expected_consumed: dict[str, Any] = {
            "grant": grant.model_dump(mode="json"),
            "prior_receipt_digest": str(event_payload.get("prior_receipt_digest") or ""),
        }
        if expected_human_approval_digest is not None:
            expected_consumed["human_approval_digest"] = expected_human_approval_digest
        self._assert_exact_event_payload(event_payload, expected_consumed, error="receipt_consumption_grant_event_mismatch")
        prior_receipt_digest = str(event_payload["prior_receipt_digest"])
        registered_payload = self._event_payload_from_row(
            registered_event,
            event_type="REGISTERED",
            error_prefix="receipt_consumption_grant_event",
        )
        self._assert_exact_event_payload(
            registered_payload,
            self._registered_event_payload(
                receipt_digest=prior_receipt_digest,
                admission_digest=admission.admission_digest,
                human_approval_digest=expected_human_approval_digest if _requires_human_approval_lineage(consumed.schema_version) else None,
            ),
            error="receipt_consumption_grant_registered_event_mismatch",
        )
        return consumed

    def record_terminal_event(
        self,
        receipt_id: str,
        *,
        terminal_status: str,
        actual_result_digest: str | None,
        oracle_evaluation_digest: str | None = None,
        reviewer_gate_digest: str | None = None,
        expected_human_approval_digest: str | None = None,
        now: datetime | None = None,
    ) -> str:
        current = self._now(now)
        if terminal_status not in {"succeeded", "typed_stop", "outcome_unknown"}:
            raise M2A1ReceiptAuthorityError("receipt_terminal_status_invalid")
        with self._connect() as connection:
            row = connection.execute("select state, admission_digest, receipt_digest, payload_json from point01_m2_a1_execution_receipts where receipt_id = ?", (receipt_id,)).fetchone()
            if row is None or str(row["state"]) != "consumed_before_run":
                raise M2A1ReceiptAuthorityError("receipt_terminal_without_consumption")
            receipt = M2A1ExecutionReceipt.model_validate(json.loads(str(row["payload_json"])))
            if _requires_human_approval_lineage(receipt.schema_version):
                if not expected_human_approval_digest or receipt.human_approval_digest != expected_human_approval_digest:
                    raise M2A1ReceiptAuthorityError("receipt_terminal_human_approval_digest_mismatch")
                if terminal_status in {"succeeded", "typed_stop"} and (not _is_sha256(str(actual_result_digest)) or not _is_sha256(str(oracle_evaluation_digest)) or not _is_sha256(str(reviewer_gate_digest))):
                    raise M2A1ReceiptAuthorityError("receipt_terminal_preterminal_digest_required")
                registered = connection.execute(
                    "select payload_digest, payload_json from point01_m2_a1_execution_receipt_events where receipt_id = ? and event_type = ?",
                    (receipt_id, "REGISTERED"),
                ).fetchone()
                consumed = connection.execute(
                    "select payload_digest, payload_json from point01_m2_a1_execution_receipt_events where receipt_id = ? and event_type = ?",
                    (receipt_id, "CONSUMED_BEFORE_RUN"),
                ).fetchone()
                registered_payload = self._event_payload_from_row(
                    registered,
                    event_type="REGISTERED",
                    error_prefix="receipt_terminal_authority_event",
                )
                consumed_payload = self._event_payload_from_row(
                    consumed,
                    event_type="CONSUMED_BEFORE_RUN",
                    error_prefix="receipt_terminal_authority_event",
                )
                try:
                    grant = M2A1ConsumptionGrant.model_validate(consumed_payload.get("grant"))
                except Exception as exc:
                    raise M2A1ReceiptAuthorityError("receipt_terminal_consumed_grant_invalid") from exc
                if not grant.verify_digest() or grant.consumed_receipt_digest != receipt.receipt_digest or grant.admission_digest != receipt.admission_digest or grant.human_approval_digest != expected_human_approval_digest:
                    raise M2A1ReceiptAuthorityError("receipt_terminal_consumed_grant_binding_mismatch")
                expected_consumed = {
                    "grant": grant.model_dump(mode="json"),
                    "prior_receipt_digest": str(consumed_payload.get("prior_receipt_digest") or ""),
                    "human_approval_digest": expected_human_approval_digest,
                }
                self._assert_exact_event_payload(
                    consumed_payload,
                    expected_consumed,
                    error="receipt_terminal_consumed_event_mismatch",
                )
                self._assert_exact_event_payload(
                    registered_payload,
                    self._registered_event_payload(
                        receipt_digest=str(consumed_payload["prior_receipt_digest"]),
                        admission_digest=receipt.admission_digest,
                        human_approval_digest=expected_human_approval_digest,
                    ),
                    error="receipt_terminal_registered_event_mismatch",
                )
                payload = {
                    "terminal_status": terminal_status,
                    "human_approval_digest": expected_human_approval_digest,
                    "admission_digest": str(row["admission_digest"]),
                    "actual_result_digest": actual_result_digest,
                    "oracle_evaluation_digest": oracle_evaluation_digest,
                    "reviewer_gate_digest": reviewer_gate_digest,
                }
                if receipt.schema_version in {V2_8_RECEIPT_SCHEMA, V2_9_RECEIPT_SCHEMA, V2_10_RECEIPT_SCHEMA}:
                    payload["consumed_receipt_digest"] = str(row["receipt_digest"])
                else:
                    payload["receipt_digest"] = str(row["receipt_digest"])
            else:
                payload = {"terminal_status": terminal_status, "actual_result_digest": actual_result_digest}
            try:
                connection.execute(
                    "insert into point01_m2_a1_execution_receipt_events (receipt_id, event_type, recorded_at, payload_digest, payload_json) values (?, ?, ?, ?, ?)",
                    (receipt_id, "TERMINAL", current.isoformat(), canonical_digest(payload), json.dumps(payload, sort_keys=True)),
                )
            except sqlite3.IntegrityError as exc:
                raise M2A1ReceiptAuthorityError("receipt_terminal_already_recorded") from exc
        return canonical_digest(payload)

    def recover_consumed_without_terminal(
        self,
        receipt_id: str,
        *,
        incident_envelope_digest: str | None = None,
        incident_envelope_ref: str | None = None,
        now: datetime | None = None,
    ) -> str:
        """Record the only safe recovery state after a consume-before-run crash.

        A consumed receipt is never made active again.  If a process dies before
        it can persist a terminal result, the registrar/executor lineage keeps a
        durable ``outcome_unknown`` terminal event and rejects any replay.
        """

        if (incident_envelope_digest is None) != (incident_envelope_ref is None):
            raise M2A1ReceiptAuthorityError("receipt_outcome_unknown_incident_link_incomplete")
        if incident_envelope_digest is not None and not _is_sha256(incident_envelope_digest):
            raise M2A1ReceiptAuthorityError("receipt_outcome_unknown_incident_digest_invalid")
        current = self._now(now)
        with self._connect() as connection:
            connection.execute("begin immediate")
            row = connection.execute(
                "select state, admission_digest, receipt_digest, payload_json from point01_m2_a1_execution_receipts where receipt_id = ?", (receipt_id,)
            ).fetchone()
            if row is None or str(row["state"]) != "consumed_before_run":
                connection.rollback()
                raise M2A1ReceiptAuthorityError("receipt_outcome_unknown_without_consumption")
            prior = connection.execute(
                "select 1 from point01_m2_a1_execution_receipt_events where receipt_id = ? and event_type = ?",
                (receipt_id, "TERMINAL"),
            ).fetchone()
            if prior is not None:
                connection.rollback()
                raise M2A1ReceiptAuthorityError("receipt_terminal_already_recorded")
            receipt = M2A1ExecutionReceipt.model_validate(json.loads(str(row["payload_json"])))
            if _requires_human_approval_lineage(receipt.schema_version):
                registered = connection.execute(
                    "select payload_digest, payload_json from point01_m2_a1_execution_receipt_events where receipt_id = ? and event_type = ?",
                    (receipt_id, "REGISTERED"),
                ).fetchone()
                consumed = connection.execute(
                    "select payload_digest, payload_json from point01_m2_a1_execution_receipt_events where receipt_id = ? and event_type = ?",
                    (receipt_id, "CONSUMED_BEFORE_RUN"),
                ).fetchone()
                registered_payload = self._event_payload_from_row(
                    registered,
                    event_type="REGISTERED",
                    error_prefix="receipt_outcome_unknown_authority_event",
                )
                consumed_payload = self._event_payload_from_row(
                    consumed,
                    event_type="CONSUMED_BEFORE_RUN",
                    error_prefix="receipt_outcome_unknown_authority_event",
                )
                try:
                    grant = M2A1ConsumptionGrant.model_validate(consumed_payload.get("grant"))
                except Exception as exc:
                    raise M2A1ReceiptAuthorityError("receipt_outcome_unknown_consumed_grant_invalid") from exc
                if not grant.verify_digest() or grant.consumed_receipt_digest != receipt.receipt_digest or grant.admission_digest != receipt.admission_digest or grant.human_approval_digest != receipt.human_approval_digest:
                    raise M2A1ReceiptAuthorityError("receipt_outcome_unknown_consumed_grant_binding_mismatch")
                self._assert_exact_event_payload(
                    consumed_payload,
                    {
                        "grant": grant.model_dump(mode="json"),
                        "prior_receipt_digest": str(consumed_payload.get("prior_receipt_digest") or ""),
                        "human_approval_digest": receipt.human_approval_digest,
                    },
                    error="receipt_outcome_unknown_consumed_event_mismatch",
                )
                self._assert_exact_event_payload(
                    registered_payload,
                    self._registered_event_payload(
                        receipt_digest=str(consumed_payload["prior_receipt_digest"]),
                        admission_digest=receipt.admission_digest,
                        human_approval_digest=receipt.human_approval_digest,
                    ),
                    error="receipt_outcome_unknown_registered_event_mismatch",
                )
                payload = {
                    "terminal_status": "outcome_unknown",
                    "human_approval_digest": receipt.human_approval_digest,
                    "admission_digest": str(row["admission_digest"]),
                    "actual_result_digest": None,
                    "oracle_evaluation_digest": None,
                    "reviewer_gate_digest": None,
                }
                if receipt.schema_version in {V2_8_RECEIPT_SCHEMA, V2_9_RECEIPT_SCHEMA, V2_10_RECEIPT_SCHEMA}:
                    payload["consumed_receipt_digest"] = str(row["receipt_digest"])
                else:
                    payload["receipt_digest"] = str(row["receipt_digest"])
                if incident_envelope_digest is not None:
                    payload["child_execution_incident_envelope_digest"] = incident_envelope_digest
                    payload["child_execution_incident_envelope_ref"] = incident_envelope_ref
            else:
                payload = {"terminal_status": "outcome_unknown", "actual_result_digest": None}
            connection.execute(
                "insert into point01_m2_a1_execution_receipt_events (receipt_id, event_type, recorded_at, payload_digest, payload_json) values (?, ?, ?, ?, ?)",
                (receipt_id, "TERMINAL", current.isoformat(), canonical_digest(payload), json.dumps(payload, sort_keys=True)),
            )
            connection.commit()
        return canonical_digest(payload)

    def state(self, receipt_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "select receipt_digest, state, registered_at, consumed_at from point01_m2_a1_execution_receipts where receipt_id = ?", (receipt_id,)
            ).fetchone()
        return dict(row) if row else None

    def receipt(self, receipt_id: str) -> M2A1ExecutionReceipt | None:
        """Read an immutable receipt projection for post-terminal review."""

        with self._connect() as connection:
            row = connection.execute(
                "select payload_json from point01_m2_a1_execution_receipts where receipt_id = ?", (receipt_id,)
            ).fetchone()
        return M2A1ExecutionReceipt.model_validate(json.loads(str(row["payload_json"]))) if row else None

    def verify_terminal_event(
        self,
        receipt_id: str,
        *,
        expected_human_approval_digest: str | None = None,
        expected_actual_result_digest: str | None = None,
        expected_oracle_evaluation_digest: str | None = None,
        expected_reviewer_gate_digest: str | None = None,
        expected_incident_envelope_digest: str | None = None,
        expected_incident_envelope_ref: str | None = None,
    ) -> Mapping[str, Any]:
        """Read a terminal event only after digest and full v2.8 lineage checks."""

        with self._connect() as connection:
            receipt_row = connection.execute(
                "select admission_digest, receipt_digest, payload_json from point01_m2_a1_execution_receipts where receipt_id = ?",
                (receipt_id,),
            ).fetchone()
            terminal_row = connection.execute(
                "select payload_digest, payload_json from point01_m2_a1_execution_receipt_events where receipt_id = ? and event_type = ?",
                (receipt_id, "TERMINAL"),
            ).fetchone()
        if receipt_row is None:
            raise M2A1ReceiptAuthorityError("receipt_terminal_read_receipt_missing")
        receipt = M2A1ExecutionReceipt.model_validate(json.loads(str(receipt_row["payload_json"])))
        payload = self._event_payload_from_row(terminal_row, event_type="TERMINAL", error_prefix="receipt_terminal_read")
        if _requires_human_approval_lineage(receipt.schema_version):
            if expected_human_approval_digest is None or payload.get("human_approval_digest") != expected_human_approval_digest:
                raise M2A1ReceiptAuthorityError("receipt_terminal_read_human_approval_digest_mismatch")
            receipt_key = "consumed_receipt_digest" if receipt.schema_version in {V2_8_RECEIPT_SCHEMA, V2_9_RECEIPT_SCHEMA, V2_10_RECEIPT_SCHEMA} else "receipt_digest"
            if (expected_incident_envelope_digest is None) != (expected_incident_envelope_ref is None):
                raise M2A1ReceiptAuthorityError("receipt_terminal_read_incident_link_incomplete")
            expected = {
                "terminal_status": payload.get("terminal_status"),
                "human_approval_digest": expected_human_approval_digest,
                "admission_digest": str(receipt_row["admission_digest"]),
                receipt_key: str(receipt_row["receipt_digest"]),
                "actual_result_digest": expected_actual_result_digest,
                "oracle_evaluation_digest": expected_oracle_evaluation_digest,
                "reviewer_gate_digest": expected_reviewer_gate_digest,
            }
            if expected_incident_envelope_digest is not None:
                expected["child_execution_incident_envelope_digest"] = expected_incident_envelope_digest
                expected["child_execution_incident_envelope_ref"] = expected_incident_envelope_ref
            elif "child_execution_incident_envelope_digest" in payload or "child_execution_incident_envelope_ref" in payload:
                raise M2A1ReceiptAuthorityError("receipt_terminal_read_unexpected_incident_link")
            self._assert_exact_event_payload(payload, expected, error="receipt_terminal_read_binding_mismatch")
        return payload

    def events(self, receipt_id: str) -> tuple[dict[str, Any], ...]:
        with self._connect() as connection:
            rows = connection.execute(
                "select event_type, payload_digest, payload_json from point01_m2_a1_execution_receipt_events where receipt_id = ? order by event_id",
                (receipt_id,),
            ).fetchall()
        for row in rows:
            self._event_payload_from_row(row, event_type=str(row["event_type"]), error_prefix="receipt_events_read")
        return tuple(dict(row) for row in rows)
