"""M6.4 terminal repair ledger for the exact one-call receipt-bound bundle."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from .bounded_sec_metadata_execution import ToolInvocationReceiptVersion
from .evidence_request import EvidenceRequest
from .facade import RuntimeFacade
from .models import CommandEnvelope, ScopedVersion, StrictModel, canonical_digest
from .receipt_bound_candidate_bundle import ReceiptBoundCandidateBundleVersion
from .repair_ticket import RepairTicket


class ReceiptBoundRepairTicketError(RuntimeError):
    """Fail-closed error for the bounded M6.4 terminal repair route."""


class ReceiptBoundRepairTicketPolicy(StrictModel):
    policy_ref: str = Field(min_length=1)
    approval_ref: str = Field(min_length=1)
    candidate_bundle_table: Literal["canonical_candidate_bundle_versions"]
    receipt_table: Literal["canonical_tool_invocation_receipt_versions"]
    repair_ticket_table: Literal["canonical_repair_ticket_versions"]
    required_bundle_persistence_scope: Literal["m6_3_receipt_bound_synthetic_pilot_only"]
    required_gap_codes: tuple[str, ...] = Field(min_length=1)
    terminal_gap_code: Literal["pilot_tool_call_budget_exhausted"]
    terminal_classification: Literal["bounded_pilot_call_budget_exhausted"]
    terminal_stop_reason: Literal["m6_2_single_call_budget_exhausted_no_repair_execution"]


class ReceiptBoundRepairTicketVersion(ScopedVersion):
    case_id: str
    repair_ticket_id: str = Field(min_length=1)
    repair_ticket_version_id: str = Field(min_length=1)
    repair_ticket_version: int = Field(ge=1)
    state_version: int = Field(ge=1)
    ticket: RepairTicket
    candidate_bundle_version_ref: str = Field(min_length=1)
    candidate_bundle_content_digest: str = Field(min_length=1)
    receipt_version_ref: str = Field(min_length=1)
    receipt_content_digest: str = Field(min_length=1)
    persistence_scope: Literal["m6_4_receipt_bound_synthetic_pilot_only"]
    new_external_call_count: Literal[0] = 0
    model_call_count: Literal[0] = 0

    @classmethod
    def create(cls, **payload: Any) -> "ReceiptBoundRepairTicketVersion":
        draft = cls(**{**payload, "content_digest": ""})
        digest = canonical_digest({key: value for key, value in draft.model_dump(mode="json").items() if key != "content_digest"})
        return draft.model_copy(update={"content_digest": digest})


class ReceiptBoundRepairTicketResult(StrictModel):
    status: Literal["terminal_repair_ticket_persisted"] = "terminal_repair_ticket_persisted"
    version: ReceiptBoundRepairTicketVersion
    reused_idempotent_result: bool = False
    model_call_count: Literal[0] = 0
    external_call_count: Literal[0] = 0
    tool_invocation_count: Literal[0] = 0
    store_write_count: Literal[1] = 1


class ReceiptBoundRepairTicketService:
    """Record why the approved pilot may not create another repair invocation."""

    def __init__(self, *, facade: RuntimeFacade, policy: ReceiptBoundRepairTicketPolicy):
        self.facade = facade
        self.policy = policy

    def persist(self, *, command: CommandEnvelope, request: EvidenceRequest, candidate_bundle_version_ref: str) -> ReceiptBoundRepairTicketResult:
        self.facade._authorize("point01_shadow_compiler")
        bundle_id, bundle_version = self._parse_exact_ref(candidate_bundle_version_ref)
        row = self.facade.store.get_version(self.policy.candidate_bundle_table, bundle_id, bundle_version)
        if not row:
            raise ReceiptBoundRepairTicketError("candidate_bundle_exact_version_not_found")
        bundle_version_row = ReceiptBoundCandidateBundleVersion.model_validate(row)
        self._validate_inputs(command=command, request=request, bundle_version_row=bundle_version_row, candidate_bundle_version_ref=candidate_bundle_version_ref)
        ticket = self._terminal_ticket(request=request, bundle_version_row=bundle_version_row)
        existing = self.facade.store.get_latest(self.policy.repair_ticket_table, ticket.repair_ticket_id)
        if existing:
            version = ReceiptBoundRepairTicketVersion.model_validate(existing)
            if version.candidate_bundle_version_ref != candidate_bundle_version_ref or version.candidate_bundle_content_digest != bundle_version_row.content_digest:
                raise ReceiptBoundRepairTicketError("repair_ticket_idempotency_bundle_conflict")
            return ReceiptBoundRepairTicketResult(version=version, reused_idempotent_result=True)
        version = ReceiptBoundRepairTicketVersion.create(
            **self.facade._scope(command, case_id=self.facade._require_case(command)),
            repair_ticket_id=ticket.repair_ticket_id,
            repair_ticket_version_id=f"{ticket.repair_ticket_id}:v1",
            repair_ticket_version=1,
            state_version=1,
            ticket=ticket,
            candidate_bundle_version_ref=candidate_bundle_version_ref,
            candidate_bundle_content_digest=bundle_version_row.content_digest,
            receipt_version_ref=bundle_version_row.receipt_version_ref,
            receipt_content_digest=bundle_version_row.receipt_content_digest,
            persistence_scope="m6_4_receipt_bound_synthetic_pilot_only",
            current_status="terminal_repair_ticket_persisted",
        )
        with self.facade.store.transaction() as tx:
            self.facade._require_running_execution(
                tx,
                command,
                self.facade._require_case(command),
                str(command.payload["work_unit_id"]),
                str(command.payload["attempt_id"]),
            )
            if tx.get_latest(self.policy.repair_ticket_table, ticket.repair_ticket_id):
                raise ReceiptBoundRepairTicketError("repair_ticket_concurrent_insert_conflict")
            persisted_bundle = tx.get_version(self.policy.candidate_bundle_table, bundle_id, bundle_version)
            if not persisted_bundle or persisted_bundle.get("content_digest") != bundle_version_row.content_digest:
                raise ReceiptBoundRepairTicketError("candidate_bundle_changed_before_repair_ticket_persistence")
            tx.insert(self.policy.repair_ticket_table, ticket.repair_ticket_id, 1, version.model_dump(mode="json"))
            event = self.facade._event(
                tx,
                command,
                "RECEIPT_BOUND_TERMINAL_REPAIR_TICKET_PERSISTED",
                {
                    "repair_ticket_version_id": version.repair_ticket_version_id,
                    "repair_ticket_digest": ticket.repair_ticket_digest,
                    "candidate_bundle_version_ref": candidate_bundle_version_ref,
                    "receipt_version_ref": bundle_version_row.receipt_version_ref,
                    "terminal_gap_code": self.policy.terminal_gap_code,
                },
                work_unit_id=str(command.payload["work_unit_id"]),
                attempt_id=str(command.payload["attempt_id"]),
            ).model_copy(update={"state_version_before": 0, "state_version_after": 1})
            tx.append_event(event)
        return ReceiptBoundRepairTicketResult(version=version)

    def _validate_inputs(
        self,
        *,
        command: CommandEnvelope,
        request: EvidenceRequest,
        bundle_version_row: ReceiptBoundCandidateBundleVersion,
        candidate_bundle_version_ref: str,
    ) -> None:
        if command.case_id is None or (request.tenant_id, request.project_id, request.case_id) != (command.tenant_id, command.project_id, command.case_id):
            raise ReceiptBoundRepairTicketError("request_command_scope_mismatch")
        if bundle_version_row.persistence_scope != self.policy.required_bundle_persistence_scope:
            raise ReceiptBoundRepairTicketError("candidate_bundle_persistence_scope_not_approved")
        if candidate_bundle_version_ref != bundle_version_row.candidate_bundle_version_id:
            raise ReceiptBoundRepairTicketError("candidate_bundle_exact_version_ref_required")
        bundle = bundle_version_row.bundle
        if bundle.request_id != request.request_id or bundle.request_digest != request.request_digest:
            raise ReceiptBoundRepairTicketError("candidate_bundle_request_lineage_mismatch")
        if bundle.status != "retrieval_exhausted" or bundle.candidate_count != 0 or bundle.candidates:
            raise ReceiptBoundRepairTicketError("receipt_bound_typed_exhaustion_required")
        if tuple(bundle.typed_gap_codes) != self.policy.required_gap_codes:
            raise ReceiptBoundRepairTicketError("candidate_bundle_typed_gap_set_mismatch")
        receipt_id, receipt_version = self._parse_exact_ref(bundle_version_row.receipt_version_ref)
        receipt_row = self.facade.store.get_version(self.policy.receipt_table, receipt_id, receipt_version)
        if not receipt_row or receipt_row.get("content_digest") != bundle_version_row.receipt_content_digest:
            raise ReceiptBoundRepairTicketError("receipt_content_digest_changed_or_missing")
        receipt = ToolInvocationReceiptVersion.model_validate(receipt_row)
        if receipt.invocation_state != "succeeded" or receipt.external_call_count != 1:
            raise ReceiptBoundRepairTicketError("successful_single_call_receipt_required")
        if receipt.approval_ref != self.policy.approval_ref:
            raise ReceiptBoundRepairTicketError("receipt_approval_scope_mismatch")
        expected_bundle_digest = canonical_digest({key: value for key, value in bundle_version_row.model_dump(mode="json").items() if key != "content_digest"})
        if bundle_version_row.content_digest != expected_bundle_digest:
            raise ReceiptBoundRepairTicketError("candidate_bundle_content_digest_mismatch")

    def _terminal_ticket(self, *, request: EvidenceRequest, bundle_version_row: ReceiptBoundCandidateBundleVersion) -> RepairTicket:
        bundle = bundle_version_row.bundle
        payload = {
            "origin_evidence_request_id": request.request_id,
            "origin_evidence_request_digest": request.request_digest,
            "candidate_bundle_id": bundle.bundle_id,
            "candidate_bundle_digest": bundle.bundle_digest,
            "repair_policy_ref": self.policy.policy_ref,
            "gap_code": self.policy.terminal_gap_code,
            "classification": self.policy.terminal_classification,
            "source_policy_ref": request.source_policy,
            "permitted_route_scope": (),
            "attempt_budget": 0,
            "terminal": True,
            "stop_reason": self.policy.terminal_stop_reason,
            "execution_admission": "not_admitted",
            "persistence_admission": "m6_4_receipt_bound_synthetic_pilot_only",
        }
        digest = canonical_digest(payload)
        return RepairTicket(repair_ticket_id=f"repair_ticket_{digest[:20]}", repair_ticket_digest=digest, **payload)

    @staticmethod
    def _parse_exact_ref(reference: str) -> tuple[str, int]:
        logical_id, marker, raw_version = reference.rpartition(":v")
        if not marker or not logical_id or not raw_version.isdigit() or int(raw_version) < 1:
            raise ReceiptBoundRepairTicketError("exact_version_ref_required")
        return logical_id, int(raw_version)


RECEIPT_BOUND_REPAIR_TICKET_MODELS = (
    ReceiptBoundRepairTicketPolicy,
    ReceiptBoundRepairTicketVersion,
    ReceiptBoundRepairTicketResult,
)
