"""M6.5 durable no-parser decision for the exact one-call SEC receipt path.

The M6.2 response intentionally has disclosure-header metadata only.  After
M6.3 records the missing table/period context and M6.4 consumes the sole call
budget, this module records why parser/numeric extraction was *not* attempted.
It creates neither ParserCandidate nor NumericFact nor NumericProgramTrace.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from .bounded_sec_metadata_execution import ToolInvocationReceiptVersion
from .evidence_request import EvidenceRequest
from .facade import RuntimeFacade
from .models import CommandEnvelope, ScopedVersion, StrictModel, canonical_digest
from .receipt_bound_candidate_bundle import ReceiptBoundCandidateBundleVersion
from .receipt_bound_repair_ticket import ReceiptBoundRepairTicketVersion


class ReceiptBoundParserNumericStopError(RuntimeError):
    """Fail-closed error for the receipt-bound M6.5 parser/numeric boundary."""


class ReceiptBoundParserNumericStopPolicy(StrictModel):
    policy_ref: str = Field(min_length=1)
    approval_ref: str = Field(min_length=1)
    candidate_bundle_table: Literal["canonical_candidate_bundle_versions"]
    repair_ticket_table: Literal["canonical_repair_ticket_versions"]
    receipt_table: Literal["canonical_tool_invocation_receipt_versions"]
    parser_stop_table: Literal["canonical_parser_numeric_stop_versions"]
    required_bundle_persistence_scope: Literal["m6_3_receipt_bound_synthetic_pilot_only"]
    required_ticket_persistence_scope: Literal["m6_4_receipt_bound_synthetic_pilot_only"]
    required_gap_codes: tuple[str, ...] = Field(min_length=1)
    required_terminal_gap_code: Literal["pilot_tool_call_budget_exhausted"]
    stop_code: Literal["candidate_bundle_has_no_verified_table_context"]


class ParserNumericAdmissionStop(StrictModel):
    parser_numeric_stop_id: str = Field(min_length=1)
    parser_numeric_stop_digest: str = Field(min_length=1)
    origin_evidence_request_id: str = Field(min_length=1)
    origin_evidence_request_digest: str = Field(min_length=1)
    candidate_bundle_id: str = Field(min_length=1)
    candidate_bundle_digest: str = Field(min_length=1)
    repair_ticket_id: str = Field(min_length=1)
    repair_ticket_digest: str = Field(min_length=1)
    parser_numeric_policy_ref: str = Field(min_length=1)
    status: Literal["not_attempted_typed_gap"] = "not_attempted_typed_gap"
    stop_code: Literal["candidate_bundle_has_no_verified_table_context"]
    parser_execution_count: Literal[0] = 0
    numeric_fact_count: Literal[0] = 0
    numeric_trace_count: Literal[0] = 0
    execution_admission: Literal["not_admitted"] = "not_admitted"
    persistence_admission: Literal["m6_5_receipt_bound_synthetic_pilot_only"] = "m6_5_receipt_bound_synthetic_pilot_only"


class ReceiptBoundParserNumericStopVersion(ScopedVersion):
    case_id: str
    parser_numeric_stop_id: str = Field(min_length=1)
    parser_numeric_stop_version_id: str = Field(min_length=1)
    parser_numeric_stop_version: int = Field(ge=1)
    state_version: int = Field(ge=1)
    stop: ParserNumericAdmissionStop
    candidate_bundle_version_ref: str = Field(min_length=1)
    candidate_bundle_content_digest: str = Field(min_length=1)
    repair_ticket_version_ref: str = Field(min_length=1)
    repair_ticket_content_digest: str = Field(min_length=1)
    receipt_version_ref: str = Field(min_length=1)
    receipt_content_digest: str = Field(min_length=1)
    persistence_scope: Literal["m6_5_receipt_bound_synthetic_pilot_only"]
    new_external_call_count: Literal[0] = 0
    model_call_count: Literal[0] = 0

    @classmethod
    def create(cls, **payload: Any) -> "ReceiptBoundParserNumericStopVersion":
        draft = cls(**{**payload, "content_digest": ""})
        digest = canonical_digest({key: value for key, value in draft.model_dump(mode="json").items() if key != "content_digest"})
        return draft.model_copy(update={"content_digest": digest})


class ReceiptBoundParserNumericStopResult(StrictModel):
    status: Literal["parser_numeric_stop_persisted"] = "parser_numeric_stop_persisted"
    version: ReceiptBoundParserNumericStopVersion
    reused_idempotent_result: bool = False
    model_call_count: Literal[0] = 0
    external_call_count: Literal[0] = 0
    tool_invocation_count: Literal[0] = 0
    parser_execution_count: Literal[0] = 0
    store_write_count: Literal[1] = 1


class ReceiptBoundParserNumericStopService:
    """Persist the terminal no-parser outcome; never parse or create a fact."""

    def __init__(self, *, facade: RuntimeFacade, policy: ReceiptBoundParserNumericStopPolicy):
        self.facade = facade
        self.policy = policy

    def persist(
        self,
        *,
        command: CommandEnvelope,
        request: EvidenceRequest,
        candidate_bundle_version_ref: str,
        repair_ticket_version_ref: str,
    ) -> ReceiptBoundParserNumericStopResult:
        self.facade._authorize("point01_shadow_compiler")
        bundle_id, bundle_version = self._parse_exact_ref(candidate_bundle_version_ref)
        ticket_id, ticket_version = self._parse_exact_ref(repair_ticket_version_ref)
        bundle_row = self.facade.store.get_version(self.policy.candidate_bundle_table, bundle_id, bundle_version)
        ticket_row = self.facade.store.get_version(self.policy.repair_ticket_table, ticket_id, ticket_version)
        if not bundle_row:
            raise ReceiptBoundParserNumericStopError("candidate_bundle_exact_version_not_found")
        if not ticket_row:
            raise ReceiptBoundParserNumericStopError("repair_ticket_exact_version_not_found")
        bundle_version_row = ReceiptBoundCandidateBundleVersion.model_validate(bundle_row)
        ticket_version_row = ReceiptBoundRepairTicketVersion.model_validate(ticket_row)
        receipt = self._validate_inputs(
            command=command,
            request=request,
            bundle_version_row=bundle_version_row,
            ticket_version_row=ticket_version_row,
            candidate_bundle_version_ref=candidate_bundle_version_ref,
            repair_ticket_version_ref=repair_ticket_version_ref,
        )
        stop = self._stop(request=request, bundle_version_row=bundle_version_row, ticket_version_row=ticket_version_row)
        existing = self.facade.store.get_latest(self.policy.parser_stop_table, stop.parser_numeric_stop_id)
        if existing:
            version = ReceiptBoundParserNumericStopVersion.model_validate(existing)
            if version.candidate_bundle_version_ref != candidate_bundle_version_ref or version.repair_ticket_version_ref != repair_ticket_version_ref:
                raise ReceiptBoundParserNumericStopError("parser_numeric_stop_idempotency_lineage_conflict")
            return ReceiptBoundParserNumericStopResult(version=version, reused_idempotent_result=True)
        version = ReceiptBoundParserNumericStopVersion.create(
            **self.facade._scope(command, case_id=self.facade._require_case(command)),
            parser_numeric_stop_id=stop.parser_numeric_stop_id,
            parser_numeric_stop_version_id=f"{stop.parser_numeric_stop_id}:v1",
            parser_numeric_stop_version=1,
            state_version=1,
            stop=stop,
            candidate_bundle_version_ref=candidate_bundle_version_ref,
            candidate_bundle_content_digest=bundle_version_row.content_digest,
            repair_ticket_version_ref=repair_ticket_version_ref,
            repair_ticket_content_digest=ticket_version_row.content_digest,
            receipt_version_ref=bundle_version_row.receipt_version_ref,
            receipt_content_digest=receipt.content_digest,
            persistence_scope="m6_5_receipt_bound_synthetic_pilot_only",
            current_status="parser_numeric_stop_persisted",
        )
        with self.facade.store.transaction() as tx:
            self.facade._require_running_execution(
                tx,
                command,
                self.facade._require_case(command),
                str(command.payload["work_unit_id"]),
                str(command.payload["attempt_id"]),
            )
            if tx.get_latest(self.policy.parser_stop_table, stop.parser_numeric_stop_id):
                raise ReceiptBoundParserNumericStopError("parser_numeric_stop_concurrent_insert_conflict")
            persisted_bundle = tx.get_version(self.policy.candidate_bundle_table, bundle_id, bundle_version)
            persisted_ticket = tx.get_version(self.policy.repair_ticket_table, ticket_id, ticket_version)
            if not persisted_bundle or persisted_bundle.get("content_digest") != bundle_version_row.content_digest:
                raise ReceiptBoundParserNumericStopError("candidate_bundle_changed_before_parser_stop_persistence")
            if not persisted_ticket or persisted_ticket.get("content_digest") != ticket_version_row.content_digest:
                raise ReceiptBoundParserNumericStopError("repair_ticket_changed_before_parser_stop_persistence")
            tx.insert(self.policy.parser_stop_table, stop.parser_numeric_stop_id, 1, version.model_dump(mode="json"))
            event = self.facade._event(
                tx,
                command,
                "RECEIPT_BOUND_PARSER_NUMERIC_STOP_PERSISTED",
                {
                    "parser_numeric_stop_version_id": version.parser_numeric_stop_version_id,
                    "parser_numeric_stop_digest": stop.parser_numeric_stop_digest,
                    "candidate_bundle_version_ref": candidate_bundle_version_ref,
                    "repair_ticket_version_ref": repair_ticket_version_ref,
                    "receipt_version_ref": bundle_version_row.receipt_version_ref,
                    "stop_code": self.policy.stop_code,
                },
                work_unit_id=str(command.payload["work_unit_id"]),
                attempt_id=str(command.payload["attempt_id"]),
            ).model_copy(update={"state_version_before": 0, "state_version_after": 1})
            tx.append_event(event)
        return ReceiptBoundParserNumericStopResult(version=version)

    def _validate_inputs(
        self,
        *,
        command: CommandEnvelope,
        request: EvidenceRequest,
        bundle_version_row: ReceiptBoundCandidateBundleVersion,
        ticket_version_row: ReceiptBoundRepairTicketVersion,
        candidate_bundle_version_ref: str,
        repair_ticket_version_ref: str,
    ) -> ToolInvocationReceiptVersion:
        if command.case_id is None or (request.tenant_id, request.project_id, request.case_id) != (command.tenant_id, command.project_id, command.case_id):
            raise ReceiptBoundParserNumericStopError("request_command_scope_mismatch")
        if bundle_version_row.persistence_scope != self.policy.required_bundle_persistence_scope:
            raise ReceiptBoundParserNumericStopError("candidate_bundle_persistence_scope_not_approved")
        if ticket_version_row.persistence_scope != self.policy.required_ticket_persistence_scope:
            raise ReceiptBoundParserNumericStopError("repair_ticket_persistence_scope_not_approved")
        if bundle_version_row.candidate_bundle_version_id != candidate_bundle_version_ref:
            raise ReceiptBoundParserNumericStopError("candidate_bundle_exact_version_ref_required")
        if ticket_version_row.repair_ticket_version_id != repair_ticket_version_ref:
            raise ReceiptBoundParserNumericStopError("repair_ticket_exact_version_ref_required")
        bundle = bundle_version_row.bundle
        ticket = ticket_version_row.ticket
        if bundle.request_id != request.request_id or bundle.request_digest != request.request_digest:
            raise ReceiptBoundParserNumericStopError("candidate_bundle_request_lineage_mismatch")
        if ticket.origin_evidence_request_id != request.request_id or ticket.origin_evidence_request_digest != request.request_digest:
            raise ReceiptBoundParserNumericStopError("repair_ticket_request_lineage_mismatch")
        if ticket.candidate_bundle_id != bundle.bundle_id or ticket.candidate_bundle_digest != bundle.bundle_digest:
            raise ReceiptBoundParserNumericStopError("repair_ticket_candidate_bundle_lineage_mismatch")
        if bundle.status != "retrieval_exhausted" or bundle.candidate_count != 0 or bundle.candidates:
            raise ReceiptBoundParserNumericStopError("receipt_bound_typed_exhaustion_required")
        if tuple(bundle.typed_gap_codes) != self.policy.required_gap_codes:
            raise ReceiptBoundParserNumericStopError("candidate_bundle_typed_gap_set_mismatch")
        if not ticket.terminal or ticket.attempt_budget != 0 or ticket.gap_code != self.policy.required_terminal_gap_code:
            raise ReceiptBoundParserNumericStopError("terminal_zero_attempt_repair_ticket_required")
        receipt_id, receipt_version = self._parse_exact_ref(bundle_version_row.receipt_version_ref)
        receipt_row = self.facade.store.get_version(self.policy.receipt_table, receipt_id, receipt_version)
        if not receipt_row or receipt_row.get("content_digest") != bundle_version_row.receipt_content_digest:
            raise ReceiptBoundParserNumericStopError("receipt_content_digest_changed_or_missing")
        receipt = ToolInvocationReceiptVersion.model_validate(receipt_row)
        if receipt.invocation_state != "succeeded" or receipt.external_call_count != 1:
            raise ReceiptBoundParserNumericStopError("successful_single_call_receipt_required")
        if receipt.approval_ref != self.policy.approval_ref:
            raise ReceiptBoundParserNumericStopError("receipt_approval_scope_mismatch")
        expected_bundle_digest = canonical_digest({key: value for key, value in bundle_version_row.model_dump(mode="json").items() if key != "content_digest"})
        expected_ticket_digest = canonical_digest({key: value for key, value in ticket_version_row.model_dump(mode="json").items() if key != "content_digest"})
        if bundle_version_row.content_digest != expected_bundle_digest:
            raise ReceiptBoundParserNumericStopError("candidate_bundle_content_digest_mismatch")
        if ticket_version_row.content_digest != expected_ticket_digest:
            raise ReceiptBoundParserNumericStopError("repair_ticket_content_digest_mismatch")
        return receipt

    def _stop(
        self,
        *,
        request: EvidenceRequest,
        bundle_version_row: ReceiptBoundCandidateBundleVersion,
        ticket_version_row: ReceiptBoundRepairTicketVersion,
    ) -> ParserNumericAdmissionStop:
        bundle = bundle_version_row.bundle
        ticket = ticket_version_row.ticket
        payload = {
            "origin_evidence_request_id": request.request_id,
            "origin_evidence_request_digest": request.request_digest,
            "candidate_bundle_id": bundle.bundle_id,
            "candidate_bundle_digest": bundle.bundle_digest,
            "repair_ticket_id": ticket.repair_ticket_id,
            "repair_ticket_digest": ticket.repair_ticket_digest,
            "parser_numeric_policy_ref": self.policy.policy_ref,
            "status": "not_attempted_typed_gap",
            "stop_code": self.policy.stop_code,
            "parser_execution_count": 0,
            "numeric_fact_count": 0,
            "numeric_trace_count": 0,
            "execution_admission": "not_admitted",
            "persistence_admission": "m6_5_receipt_bound_synthetic_pilot_only",
        }
        digest = canonical_digest(payload)
        return ParserNumericAdmissionStop(
            parser_numeric_stop_id=f"parser_numeric_stop_{digest[:20]}",
            parser_numeric_stop_digest=digest,
            **payload,
        )

    @staticmethod
    def _parse_exact_ref(reference: str) -> tuple[str, int]:
        logical_id, marker, raw_version = reference.rpartition(":v")
        if not marker or not logical_id or not raw_version.isdigit() or int(raw_version) < 1:
            raise ReceiptBoundParserNumericStopError("exact_version_ref_required")
        return logical_id, int(raw_version)


RECEIPT_BOUND_PARSER_NUMERIC_STOP_MODELS = (
    ReceiptBoundParserNumericStopPolicy,
    ParserNumericAdmissionStop,
    ReceiptBoundParserNumericStopVersion,
    ReceiptBoundParserNumericStopResult,
)
