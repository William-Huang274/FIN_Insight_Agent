"""Fixed-store, digest-bound, one-shot human approval for the M6 SEC pilot.

The approval store is deliberately separate from every local pilot store.  A
local Case/Grant/Budget may be recreated for deterministic tests, but it can
never recreate an active one-shot human receipt.  Consumption is append-only
and atomic in the fixed approval store before a network send is possible.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from .models import CommandEnvelope, ScopedVersion, StrictModel, canonical_digest, utc_now
from .store import SQLiteCanonicalStore
from .tool_planner import ToolSelectionPlan
from .evidence_request import EvidenceRequest


class M6GlobalOneShotApprovalError(RuntimeError):
    """Fail-closed error for the fixed M6 global approval authority."""


class M6PilotApprovalScope(StrictModel):
    approval_ref: str = Field(min_length=1)
    approved_execution_scope: Literal[
        "real_bounded_sec_metadata_pilot_only",
        "single_sec_document_positive_retrieval_parser_pilot_only",
    ]
    tenant_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    request_digest: str = Field(min_length=1)
    tool_selection_plan_id: str = Field(min_length=1)
    tool_selection_plan_digest: str = Field(min_length=1)
    tool_id: Literal["issuer_disclosure_metadata_tool", "issuer_filing_document_table_tool"]
    route_id: Literal["issuer_disclosure_metadata_route", "issuer_filing_document_table_route"]
    network_host: Literal["data.sec.gov", "www.sec.gov"]
    endpoint_path: str = Field(min_length=1)
    target_cik: str = Field(pattern=r"^\d{10}$")
    execution_policy_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    max_external_calls: Literal[1] = 1
    max_fallback_calls: Literal[0] = 0

    @property
    def scope_digest(self) -> str:
        return canonical_digest(self)


class M6GlobalOneShotApprovalReceipt(ScopedVersion):
    """Append-only authoritative human receipt, stored outside the pilot Case."""

    case_id: None = None
    approval_id: str = Field(min_length=1)
    approval_version: int = Field(ge=1)
    state_version: int = Field(ge=1)
    approval_state: Literal["active", "consumed", "revoked"]
    # A one-shot nonce is a secret-like authorization capability.  It is only
    # accepted at registration time so that its SHA-256 can bind the receipt;
    # it is never retained in the canonical approval authority.
    approval_nonce_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    scope_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    package_ref: str = Field(min_length=1)
    package_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    package_manifest_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    reviewer_name: str = Field(min_length=1)
    reviewer_employee_id: str = Field(min_length=1)
    reviewer_role: Literal["total_reviewer"]
    expires_at: datetime
    authority_store_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    consumed_at: datetime | None = None
    consumed_by_invocation_id: str | None = None
    consumed_local_store_identity: str | None = None

    @model_validator(mode="before")
    @classmethod
    def digest_nonce_before_persistence(cls, value: Any) -> Any:
        """Accept a registration-only raw nonce without serializing it.

        The legacy key is also recognized for read-only inspection of historic
        rows.  Their historic content digest will intentionally not validate
        under this v5 contract, preventing their reuse as executable authority
        while leaving the original SQLite evidence untouched.
        """
        if not isinstance(value, dict):
            return value
        payload = dict(value)
        raw_nonce = payload.pop("approval_nonce", None)
        if raw_nonce is not None:
            raw_nonce = str(raw_nonce)
            if len(raw_nonce) < 16:
                raise ValueError("approval_nonce_min_length_16_required")
            digest = hashlib.sha256(raw_nonce.encode("utf-8")).hexdigest()
            existing = payload.get("approval_nonce_sha256")
            if existing is not None and existing != digest:
                raise ValueError("approval_nonce_digest_mismatch")
            payload["approval_nonce_sha256"] = digest
        return payload

    @field_validator("expires_at", "consumed_at")
    @classmethod
    def require_utc(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value)):
            raise ValueError("timezone_aware_utc_required")
        return value

    @classmethod
    def create(cls, **payload: Any) -> "M6GlobalOneShotApprovalReceipt":
        draft = cls(**{**payload, "content_digest": ""})
        digest = canonical_digest({key: value for key, value in draft.model_dump(mode="json").items() if key != "content_digest"})
        return draft.model_copy(update={"content_digest": digest})


class M6GlobalOneShotApprovalService:
    """Authority reader/consumer. The live runner never registers a receipt."""

    table = "canonical_m6_global_one_shot_approval_versions"

    def __init__(
        self,
        *,
        store: SQLiteCanonicalStore,
        required_reviewer_name: str | None = None,
        required_reviewer_employee_id: str | None = None,
        required_reviewer_role: str | None = None,
    ):
        self.store = store
        self.required_reviewer_name = required_reviewer_name
        self.required_reviewer_employee_id = required_reviewer_employee_id
        self.required_reviewer_role = required_reviewer_role

    def _require_expected_reviewer(self, receipt: M6GlobalOneShotApprovalReceipt) -> None:
        expected = (
            self.required_reviewer_name,
            self.required_reviewer_employee_id,
            self.required_reviewer_role,
        )
        if any(value is not None for value in expected) and (
            receipt.reviewer_name,
            receipt.reviewer_employee_id,
            receipt.reviewer_role,
        ) != expected:
            raise M6GlobalOneShotApprovalError("global_approval_reviewer_mismatch")

    @staticmethod
    def _require_valid_content_digest(receipt: M6GlobalOneShotApprovalReceipt) -> None:
        expected = M6GlobalOneShotApprovalReceipt.create(
            **{key: value for key, value in receipt.model_dump(mode="python").items() if key != "content_digest"}
        )
        if receipt.content_digest != expected.content_digest:
            raise M6GlobalOneShotApprovalError("global_approval_receipt_content_digest_mismatch")

    def register_authoritative_receipt(self, receipt: M6GlobalOneShotApprovalReceipt) -> M6GlobalOneShotApprovalReceipt:
        """Record a separately reviewed receipt once; not called by any executor."""
        self._require_valid_content_digest(receipt)
        self._require_expected_reviewer(receipt)
        if receipt.approval_state != "active" or receipt.approval_version != 1:
            raise M6GlobalOneShotApprovalError("global_approval_initial_receipt_must_be_active_v1")
        if receipt.authority_store_identity != self.store.store_identity():
            raise M6GlobalOneShotApprovalError("global_approval_store_identity_mismatch")
        if receipt.expires_at <= utc_now():
            raise M6GlobalOneShotApprovalError("global_approval_initial_receipt_expired")
        with self.store.transaction() as tx:
            if tx.get_latest(self.table, receipt.approval_id):
                raise M6GlobalOneShotApprovalError("global_approval_receipt_already_registered")
            tx.insert(self.table, receipt.approval_id, 1, receipt.model_dump(mode="json"))
        return receipt

    def _require_active_exact_receipt(
        self,
        receipt: M6GlobalOneShotApprovalReceipt,
        *,
        scope: M6PilotApprovalScope,
        package_ref: str,
        package_digest: str,
        package_manifest_digest: str,
        at: datetime,
    ) -> None:
        self._require_valid_content_digest(receipt)
        self._require_expected_reviewer(receipt)
        if receipt.authority_store_identity != self.store.store_identity():
            raise M6GlobalOneShotApprovalError("global_approval_receipt_store_identity_mismatch")
        if receipt.approval_state != "active":
            raise M6GlobalOneShotApprovalError(f"global_approval_not_active:{receipt.approval_state}")
        if receipt.expires_at <= at:
            raise M6GlobalOneShotApprovalError("global_approval_expired")
        if receipt.scope_digest != scope.scope_digest:
            raise M6GlobalOneShotApprovalError("global_approval_scope_digest_mismatch")
        if (receipt.package_ref, receipt.package_digest, receipt.package_manifest_digest) != (package_ref, package_digest, package_manifest_digest):
            raise M6GlobalOneShotApprovalError("global_approval_package_digest_mismatch")

    def verify_active_exact_receipt(
        self,
        *,
        scope: M6PilotApprovalScope,
        package_ref: str,
        package_digest: str,
        package_manifest_digest: str,
        approval_id: str,
        at: datetime | None = None,
    ) -> M6GlobalOneShotApprovalReceipt:
        """Read-only preflight; consumption still happens atomically before send."""
        raw = self.store.get_latest(self.table, approval_id)
        if not raw:
            raise M6GlobalOneShotApprovalError("global_approval_receipt_not_registered")
        receipt = M6GlobalOneShotApprovalReceipt.model_validate(raw)
        self._require_active_exact_receipt(
            receipt,
            scope=scope,
            package_ref=package_ref,
            package_digest=package_digest,
            package_manifest_digest=package_manifest_digest,
            at=at or utc_now(),
        )
        return receipt

    def consume(
        self,
        *,
        scope: M6PilotApprovalScope,
        package_ref: str,
        package_digest: str,
        package_manifest_digest: str,
        approval_id: str,
        invocation_id: str,
        local_store_identity: str,
        at: datetime | None = None,
    ) -> M6GlobalOneShotApprovalReceipt:
        consumed_at = at or utc_now()
        with self.store.transaction() as tx:
            raw = tx.get_latest(self.table, approval_id)
            if not raw:
                raise M6GlobalOneShotApprovalError("global_approval_receipt_not_registered")
            receipt = M6GlobalOneShotApprovalReceipt.model_validate(raw)
            self._require_active_exact_receipt(
                receipt,
                scope=scope,
                package_ref=package_ref,
                package_digest=package_digest,
                package_manifest_digest=package_manifest_digest,
                at=consumed_at,
            )
            next_version = receipt.approval_version + 1
            consumed = M6GlobalOneShotApprovalReceipt.create(
                **{
                    **receipt.model_dump(mode="python"),
                    "approval_version": next_version,
                    "state_version": next_version,
                    "approval_state": "consumed",
                    "consumed_at": consumed_at,
                    "consumed_by_invocation_id": invocation_id,
                    "consumed_local_store_identity": local_store_identity,
                    "current_status": "consumed",
                    "supersedes_version_id": f"{receipt.approval_id}:v{receipt.approval_version}",
                }
            )
            tx.insert(self.table, receipt.approval_id, next_version, consumed.model_dump(mode="json"))
        return consumed


def build_m6_pilot_scope(
    *,
    command: CommandEnvelope,
    request: EvidenceRequest,
    plan: ToolSelectionPlan,
    approval_ref: str,
    approved_execution_scope: Literal[
        "real_bounded_sec_metadata_pilot_only",
        "single_sec_document_positive_retrieval_parser_pilot_only",
    ],
    tool_id: Literal["issuer_disclosure_metadata_tool", "issuer_filing_document_table_tool"],
    route_id: Literal["issuer_disclosure_metadata_route", "issuer_filing_document_table_route"],
    network_host: Literal["data.sec.gov", "www.sec.gov"],
    target_cik: str,
    endpoint_path: str | None = None,
    execution_policy_digest: str | None = None,
) -> M6PilotApprovalScope:
    if command.case_id is None:
        raise M6GlobalOneShotApprovalError("global_approval_case_id_required")
    return M6PilotApprovalScope(
        approval_ref=approval_ref,
        approved_execution_scope=approved_execution_scope,
        tenant_id=command.tenant_id,
        project_id=command.project_id,
        case_id=command.case_id,
        request_id=request.request_id,
        request_digest=request.request_digest,
        tool_selection_plan_id=plan.plan_id,
        tool_selection_plan_digest=plan.plan_digest,
        tool_id=tool_id,
        route_id=route_id,
        network_host=network_host,
        endpoint_path=endpoint_path or f"/submissions/CIK{target_cik}.json",
        target_cik=target_cik,
        execution_policy_digest=execution_policy_digest,
    )


M6_GLOBAL_ONE_SHOT_APPROVAL_MODELS = (
    M6PilotApprovalScope,
    M6GlobalOneShotApprovalReceipt,
)
