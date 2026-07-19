"""M6.3 receipt-bound CandidateBundle persistence for the one-call SEC pilot.

The M6.2 receipt deliberately contains filing headers only.  This adapter
records that exact source boundary without inventing a period, section, table,
numeric fact, or evidence candidate.  Its only permitted positive effect is a
durable, receipt-bound typed exhaustion that downstream code cannot mistake for
formal Evidence.
"""

from __future__ import annotations

from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import Field

from .bounded_sec_metadata_execution import ToolInvocationReceiptVersion
from .candidate_bundle import CandidateBundle
from .evidence_request import EvidenceRequest
from .facade import RuntimeFacade
from .models import CommandEnvelope, ScopedVersion, StrictModel, canonical_digest
from .tool_planner import ToolSelectionPlan


class ReceiptBoundCandidateBundleError(RuntimeError):
    """Fail-closed error for receipt-to-bundle conversion."""


class ReceiptBoundCandidateBundlePolicy(StrictModel):
    policy_ref: str = Field(min_length=1)
    approval_ref: str = Field(min_length=1)
    approved_execution_scope: Literal["real_bounded_sec_metadata_pilot_only"]
    receipt_table: Literal["canonical_tool_invocation_receipt_versions"]
    bundle_table: Literal["canonical_candidate_bundle_versions"]
    allowed_tool_id: Literal["issuer_disclosure_metadata_tool"]
    allowed_route_id: Literal["issuer_disclosure_metadata_route"]
    allowed_network_host: Literal["data.sec.gov"]
    allowed_cik: str = Field(pattern=r"^\d{10}$")
    required_target_entity: Literal["NVDA"]
    required_evidence_role: Literal["numeric_fact"]
    typed_gap_codes: tuple[str, ...] = Field(min_length=1)


class ReceiptBoundCandidateBundleVersion(ScopedVersion):
    case_id: str
    candidate_bundle_id: str = Field(min_length=1)
    candidate_bundle_version_id: str = Field(min_length=1)
    candidate_bundle_version: int = Field(ge=1)
    state_version: int = Field(ge=1)
    bundle: CandidateBundle
    receipt_version_ref: str = Field(min_length=1)
    receipt_content_digest: str = Field(min_length=1)
    receipt_source_metadata_digest: str = Field(min_length=1)
    persistence_scope: Literal["m6_3_receipt_bound_synthetic_pilot_only"]
    source_execution_count: Literal[1] = 1
    new_external_call_count: Literal[0] = 0
    model_call_count: Literal[0] = 0

    @classmethod
    def create(cls, **payload: Any) -> "ReceiptBoundCandidateBundleVersion":
        draft = cls(**{**payload, "content_digest": ""})
        digest = canonical_digest({key: value for key, value in draft.model_dump(mode="json").items() if key != "content_digest"})
        return draft.model_copy(update={"content_digest": digest})


class ReceiptBoundCandidateBundleResult(StrictModel):
    status: Literal["typed_exhaustion_persisted"] = "typed_exhaustion_persisted"
    version: ReceiptBoundCandidateBundleVersion
    reused_idempotent_result: bool = False
    model_call_count: Literal[0] = 0
    external_call_count: Literal[0] = 0
    tool_invocation_count: Literal[0] = 0
    store_write_count: Literal[1] = 1


class ReceiptBoundCandidateBundleService:
    """Persist a no-invention M6.3 typed exhaustion from an exact M6.2 receipt."""

    def __init__(self, *, facade: RuntimeFacade, policy: ReceiptBoundCandidateBundlePolicy):
        self.facade = facade
        self.policy = policy

    def persist(
        self,
        *,
        command: CommandEnvelope,
        request: EvidenceRequest,
        plan: ToolSelectionPlan,
        receipt_version_ref: str,
    ) -> ReceiptBoundCandidateBundleResult:
        self.facade._authorize("point01_shadow_compiler")
        receipt_id, receipt_version = self._parse_exact_ref(receipt_version_ref)
        receipt_row = self.facade.store.get_version(self.policy.receipt_table, receipt_id, receipt_version)
        if not receipt_row:
            raise ReceiptBoundCandidateBundleError("receipt_exact_version_not_found")
        receipt = ToolInvocationReceiptVersion.model_validate(receipt_row)
        self._validate_inputs(command=command, request=request, plan=plan, receipt=receipt, receipt_version_ref=receipt_version_ref)
        bundle = self._typed_exhaustion_bundle(request=request, plan=plan, receipt=receipt, receipt_version_ref=receipt_version_ref)
        existing = self.facade.store.get_latest(self.policy.bundle_table, bundle.bundle_id)
        if existing:
            version = ReceiptBoundCandidateBundleVersion.model_validate(existing)
            if version.receipt_version_ref != receipt_version_ref or version.receipt_content_digest != receipt.content_digest:
                raise ReceiptBoundCandidateBundleError("candidate_bundle_idempotency_receipt_conflict")
            return ReceiptBoundCandidateBundleResult(version=version, reused_idempotent_result=True)

        version = ReceiptBoundCandidateBundleVersion.create(
            **self.facade._scope(command, case_id=self.facade._require_case(command)),
            candidate_bundle_id=bundle.bundle_id,
            candidate_bundle_version_id=f"{bundle.bundle_id}:v1",
            candidate_bundle_version=1,
            state_version=1,
            bundle=bundle,
            receipt_version_ref=receipt_version_ref,
            receipt_content_digest=receipt.content_digest,
            receipt_source_metadata_digest=str(receipt.source_metadata_digest),
            persistence_scope="m6_3_receipt_bound_synthetic_pilot_only",
            current_status="typed_exhaustion_persisted",
        )
        with self.facade.store.transaction() as tx:
            self.facade._require_running_execution(
                tx,
                command,
                self.facade._require_case(command),
                str(command.payload["work_unit_id"]),
                str(command.payload["attempt_id"]),
            )
            if tx.get_latest(self.policy.bundle_table, bundle.bundle_id):
                raise ReceiptBoundCandidateBundleError("candidate_bundle_concurrent_insert_conflict")
            # Re-read the pinned receipt inside the mutation transaction.
            persisted_receipt = tx.get_version(self.policy.receipt_table, receipt_id, receipt_version)
            if not persisted_receipt or persisted_receipt.get("content_digest") != receipt.content_digest:
                raise ReceiptBoundCandidateBundleError("receipt_changed_before_candidate_bundle_persistence")
            tx.insert(self.policy.bundle_table, bundle.bundle_id, 1, version.model_dump(mode="json"))
            event = self.facade._event(
                tx,
                command,
                "RECEIPT_BOUND_CANDIDATE_BUNDLE_PERSISTED",
                {
                    "candidate_bundle_version_id": version.candidate_bundle_version_id,
                    "candidate_bundle_digest": bundle.bundle_digest,
                    "receipt_version_ref": receipt_version_ref,
                    "receipt_content_digest": receipt.content_digest,
                    "status": bundle.status,
                    "typed_gap_codes": list(bundle.typed_gap_codes),
                },
                work_unit_id=str(command.payload["work_unit_id"]),
                attempt_id=str(command.payload["attempt_id"]),
            ).model_copy(update={"state_version_before": 0, "state_version_after": 1})
            tx.append_event(event)
        return ReceiptBoundCandidateBundleResult(version=version)

    def _validate_inputs(
        self,
        *,
        command: CommandEnvelope,
        request: EvidenceRequest,
        plan: ToolSelectionPlan,
        receipt: ToolInvocationReceiptVersion,
        receipt_version_ref: str,
    ) -> None:
        if command.case_id is None or (request.tenant_id, request.project_id, request.case_id) != (command.tenant_id, command.project_id, command.case_id):
            raise ReceiptBoundCandidateBundleError("request_command_scope_mismatch")
        if plan.request_id != request.request_id or plan.request_digest != request.request_digest:
            raise ReceiptBoundCandidateBundleError("plan_request_lineage_mismatch")
        if receipt.invocation_state != "succeeded" or receipt.external_call_count != 1 or receipt.source_metadata is None:
            raise ReceiptBoundCandidateBundleError("successful_single_call_receipt_required")
        if receipt.invocation_version < 2 or receipt_version_ref != f"{receipt.invocation_id}:v{receipt.invocation_version}":
            raise ReceiptBoundCandidateBundleError("receipt_exact_terminal_version_required")
        if receipt.request_id != request.request_id or receipt.request_digest != request.request_digest:
            raise ReceiptBoundCandidateBundleError("receipt_request_lineage_mismatch")
        if receipt.tool_selection_plan_id != plan.plan_id or receipt.tool_selection_plan_digest != plan.plan_digest:
            raise ReceiptBoundCandidateBundleError("receipt_plan_lineage_mismatch")
        if receipt.approved_execution_scope != self.policy.approved_execution_scope or receipt.approval_ref != self.policy.approval_ref:
            raise ReceiptBoundCandidateBundleError("receipt_approval_scope_mismatch")
        if receipt.tool_id != self.policy.allowed_tool_id or receipt.route_id != self.policy.allowed_route_id or receipt.endpoint_host != self.policy.allowed_network_host:
            raise ReceiptBoundCandidateBundleError("receipt_tool_or_network_scope_mismatch")
        if receipt.target_cik != self.policy.allowed_cik or receipt.source_metadata.cik != self.policy.allowed_cik:
            raise ReceiptBoundCandidateBundleError("receipt_cik_scope_mismatch")
        if request.accepted_evidence_role != self.policy.required_evidence_role or self.policy.required_target_entity not in request.target_entities:
            raise ReceiptBoundCandidateBundleError("receipt_request_role_or_entity_not_approved")
        if self.policy.required_target_entity not in receipt.source_metadata.tickers:
            raise ReceiptBoundCandidateBundleError("receipt_issuer_ticker_binding_missing")
        expected_receipt_digest = canonical_digest({key: value for key, value in receipt.model_dump(mode="json").items() if key != "content_digest"})
        if receipt.content_digest != expected_receipt_digest:
            raise ReceiptBoundCandidateBundleError("receipt_content_digest_mismatch")
        if receipt.source_metadata_digest != canonical_digest(receipt.source_metadata):
            raise ReceiptBoundCandidateBundleError("receipt_source_metadata_digest_mismatch")
        parsed = urlparse(receipt.source_metadata.source_url)
        if parsed.scheme != "https" or parsed.hostname != self.policy.allowed_network_host or parsed.path != f"/submissions/CIK{self.policy.allowed_cik}.json":
            raise ReceiptBoundCandidateBundleError("receipt_source_url_not_approved")

    def _typed_exhaustion_bundle(
        self,
        *,
        request: EvidenceRequest,
        plan: ToolSelectionPlan,
        receipt: ToolInvocationReceiptVersion,
        receipt_version_ref: str,
    ) -> CandidateBundle:
        snapshot_payload = {
            "receipt_version_ref": receipt_version_ref,
            "receipt_content_digest": receipt.content_digest,
            "source_metadata_digest": receipt.source_metadata_digest,
            "metadata_kind": "sec_submission_headers_only",
        }
        metadata_snapshot_digest = canonical_digest(snapshot_payload)
        payload = {
            "request_id": request.request_id,
            "request_digest": request.request_digest,
            "tool_selection_plan_id": plan.plan_id,
            "tool_selection_plan_digest": plan.plan_digest,
            "metadata_snapshot_id": f"receipt_metadata_{metadata_snapshot_digest[:20]}",
            "metadata_snapshot_digest": metadata_snapshot_digest,
            "retrieval_policy_ref": self.policy.policy_ref,
            "status": "retrieval_exhausted",
            "exhaustion_status": "receipt_metadata_insufficient_for_numeric_binding",
            "typed_gap_codes": self.policy.typed_gap_codes,
            "candidates": (),
            "top_k_candidate_ids": (),
            "neighbor_candidate_ids": (),
            "table_context_candidate_ids": (),
            "candidate_count": 0,
            "execution_admission": "receipt_bound_no_new_execution",
            "persistence_admission": "m6_3_receipt_bound_synthetic_pilot_only",
        }
        digest = canonical_digest(payload)
        return CandidateBundle(bundle_id=f"candidate_bundle_{digest[:20]}", bundle_digest=digest, **payload)

    @staticmethod
    def _parse_exact_ref(reference: str) -> tuple[str, int]:
        logical_id, marker, raw_version = reference.rpartition(":v")
        if not marker or not logical_id or not raw_version.isdigit() or int(raw_version) < 1:
            raise ReceiptBoundCandidateBundleError("receipt_exact_version_ref_required")
        return logical_id, int(raw_version)


RECEIPT_BOUND_CANDIDATE_BUNDLE_MODELS = (
    ReceiptBoundCandidateBundlePolicy,
    ReceiptBoundCandidateBundleVersion,
    ReceiptBoundCandidateBundleResult,
)
