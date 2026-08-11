from __future__ import annotations

from pydantic import Field

from .candidate_bundle import CandidateBundle
from .evidence_request import EvidenceRequest
from .models import StrictModel, canonical_digest


class RepairTicketError(ValueError):
    """Raised when a typed candidate gap cannot become a bounded repair contract."""


class RepairGapRoute(StrictModel):
    classification: str = Field(min_length=1)
    terminal: bool
    stop_reason: str = Field(min_length=1)


class RepairTicketPolicy(StrictModel):
    policy_ref: str = Field(min_length=1)
    max_internal_repair_attempts: int = Field(ge=0)
    gap_routes: dict[str, RepairGapRoute]


class RepairTicket(StrictModel):
    repair_ticket_id: str = Field(min_length=1)
    repair_ticket_digest: str = Field(min_length=1)
    origin_evidence_request_id: str = Field(min_length=1)
    origin_evidence_request_digest: str = Field(min_length=1)
    candidate_bundle_id: str = Field(min_length=1)
    candidate_bundle_digest: str = Field(min_length=1)
    repair_policy_ref: str = Field(min_length=1)
    gap_code: str = Field(min_length=1)
    classification: str = Field(min_length=1)
    source_policy_ref: str = Field(min_length=1)
    permitted_route_scope: tuple[str, ...] = ()
    attempt_budget: int = Field(ge=0)
    terminal: bool
    stop_reason: str = Field(min_length=1)
    execution_admission: str = "not_admitted"
    persistence_admission: str = "not_admitted"


class RepairAttempt(StrictModel):
    repair_attempt_id: str = Field(min_length=1)
    repair_attempt_digest: str = Field(min_length=1)
    repair_ticket_id: str = Field(min_length=1)
    repair_ticket_digest: str = Field(min_length=1)
    attempt_no: int = Field(ge=1)
    route_id: str = Field(min_length=1)
    attempt_state: str = "planned_not_executed"
    outcome: str = "not_executed"
    next_owner: str = "M6_2_tool_registry_planner"
    execution_admission: str = "not_admitted"
    persistence_admission: str = "not_admitted"


class RepairTicketResult(StrictModel):
    status: str
    ticket: RepairTicket
    model_call_count: int = 0
    external_call_count: int = 0
    tool_invocation_count: int = 0
    store_write_count: int = 0


class RepairAttemptResult(StrictModel):
    status: str
    attempt: RepairAttempt
    model_call_count: int = 0
    external_call_count: int = 0
    tool_invocation_count: int = 0
    store_write_count: int = 0


class RepairTicketRouter:
    """M6.4 typed-gap router; it can create repair contracts but cannot execute or rewrite upstream artifacts."""

    def __init__(self, *, policy: RepairTicketPolicy):
        self.policy = policy

    @staticmethod
    def _gap_key(code: str) -> str:
        return code.split(":", 1)[0]

    def route(self, *, request: EvidenceRequest, bundle: CandidateBundle) -> RepairTicketResult:
        if bundle.request_id != request.request_id or bundle.request_digest != request.request_digest:
            raise RepairTicketError("candidate_bundle_request_lineage_mismatch")
        if bundle.persistence_admission != "not_admitted" or bundle.execution_admission != "not_admitted":
            raise RepairTicketError("candidate_bundle_must_be_not_admitted")
        if bundle.status not in {"retrieval_exhausted", "not_attempted_typed_stop"}:
            raise RepairTicketError("repair_ticket_requires_typed_gap_bundle")
        if not bundle.typed_gap_codes:
            raise RepairTicketError("typed_gap_code_required")
        gap_code = bundle.typed_gap_codes[0]
        gap_route = self.policy.gap_routes.get(self._gap_key(gap_code))
        if gap_route is None:
            raise RepairTicketError(f"repair_policy_missing_gap_route:{self._gap_key(gap_code)}")
        permitted_routes = () if gap_route.terminal else tuple(request.preferred_routes) + tuple(request.fallback_routes)
        if not gap_route.terminal and not permitted_routes:
            raise RepairTicketError("internal_repair_requires_declared_route_scope")
        attempt_budget = 0 if gap_route.terminal else self.policy.max_internal_repair_attempts
        payload = {
            "origin_evidence_request_id": request.request_id,
            "origin_evidence_request_digest": request.request_digest,
            "candidate_bundle_id": bundle.bundle_id,
            "candidate_bundle_digest": bundle.bundle_digest,
            "repair_policy_ref": self.policy.policy_ref,
            "gap_code": gap_code,
            "classification": gap_route.classification,
            "source_policy_ref": request.source_policy,
            "permitted_route_scope": permitted_routes,
            "attempt_budget": attempt_budget,
            "terminal": gap_route.terminal,
            "stop_reason": gap_route.stop_reason,
            "execution_admission": "not_admitted",
            "persistence_admission": "not_admitted",
        }
        digest = canonical_digest(payload)
        ticket = RepairTicket(repair_ticket_id=f"repair_ticket_{digest[:20]}", repair_ticket_digest=digest, **payload)
        return RepairTicketResult(status="pass", ticket=ticket)


class RepairAttemptPlanner:
    """Records a bounded planned-only attempt; M6.2 is the sole future ToolSelectionPlan writer."""

    def plan_not_executed(self, *, ticket: RepairTicket, attempt_no: int, route_id: str) -> RepairAttemptResult:
        if ticket.terminal:
            raise RepairTicketError("terminal_repair_ticket_cannot_create_attempt")
        if attempt_no > ticket.attempt_budget:
            raise RepairTicketError("repair_attempt_budget_exhausted")
        if route_id not in ticket.permitted_route_scope:
            raise RepairTicketError("repair_attempt_route_not_permitted")
        payload = {
            "repair_ticket_id": ticket.repair_ticket_id,
            "repair_ticket_digest": ticket.repair_ticket_digest,
            "attempt_no": attempt_no,
            "route_id": route_id,
            "attempt_state": "planned_not_executed",
            "outcome": "not_executed",
            "next_owner": "M6_2_tool_registry_planner",
            "execution_admission": "not_admitted",
            "persistence_admission": "not_admitted",
        }
        digest = canonical_digest(payload)
        attempt = RepairAttempt(repair_attempt_id=f"repair_attempt_{digest[:20]}", repair_attempt_digest=digest, **payload)
        return RepairAttemptResult(status="pass", attempt=attempt)
