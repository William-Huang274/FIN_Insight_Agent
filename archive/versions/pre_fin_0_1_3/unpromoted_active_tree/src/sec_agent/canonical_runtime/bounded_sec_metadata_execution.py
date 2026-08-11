"""M6.2 narrowly-admitted, single-call SEC submissions metadata execution.

This is intentionally not a generic tool runner.  Its only executable route is
the user-approved synthetic NVDA pilot against ``data.sec.gov``.  A network
request cannot share an ACID transaction with a SQLite store, so the lifecycle
is durable and fail-closed: prepare -> execution-time re-admission -> one send
-> append-only terminal receipt.  A request error after the send boundary is
conservatively charged and is never retried by this module.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import re
from typing import Any, Callable, Literal, Protocol
from urllib.parse import urlparse

import requests
from pydantic import Field

from .budget_control import BudgetControlService, BudgetReservationRequest
from .capability_security import (
    CapabilitySecurityError,
    CapabilitySecurityService,
    SandboxAdmissionRequest,
    SecurityAdmissionDecision,
)
from .evidence_request import EvidenceRequest
from .facade import RuntimeFacade
from .m6_pilot_global_approval import (
    M6GlobalOneShotApprovalReceipt,
    M6GlobalOneShotApprovalService,
    build_m6_pilot_scope,
)
from .m6_pilot_package import M6PilotPackageDigest
from .models import CommandEnvelope, ScopedVersion, StrictModel, canonical_digest, utc_now
from .tool_planner import ToolSelectionPlan


class BoundedSecMetadataExecutionError(RuntimeError):
    """Typed fail-closed error for the only M6.2 executable route."""


class SecMetadataTransportError(BoundedSecMetadataExecutionError):
    """The one outbound request may have reached SEC; no retry is safe here."""


class HttpSession(Protocol):
    def get(self, url: str, **kwargs: Any) -> requests.Response: ...


class BoundedSecMetadataExecutionPolicy(StrictModel):
    policy_ref: str = Field(min_length=1)
    approval_ref: str = Field(min_length=1)
    approved_execution_scope: Literal["real_bounded_sec_metadata_pilot_only"]
    tool_id: Literal["issuer_disclosure_metadata_tool"]
    route_id: Literal["issuer_disclosure_metadata_route"]
    capability: Literal["evidence.metadata.read"]
    required_registry_snapshot_id: str = Field(min_length=1)
    allowed_network_host: Literal["data.sec.gov"]
    allowed_endpoint_path_prefix: Literal["/submissions/"]
    allowed_cik: str = Field(pattern=r"^\d{10}$")
    max_external_calls: Literal[1] = 1
    max_fallback_calls: Literal[0] = 0
    timeout_seconds: int = Field(ge=1, le=30)
    metadata_filing_limit: int = Field(ge=1, le=5)
    user_agent_environment_variable: str = Field(min_length=1)
    user_agent_min_length: int = Field(ge=16, le=256)
    forbidden_user_agent_values: tuple[str, ...] = Field(min_length=1)


class SecFilingMetadata(StrictModel):
    form: str
    filing_date: str | None = None
    report_date: str | None = None
    accession_number: str | None = None
    primary_document: str | None = None


class SecMetadataFetchResult(StrictModel):
    source_url: str
    source_host: Literal["data.sec.gov"]
    cik: str = Field(pattern=r"^\d{10}$")
    issuer_name: str | None = None
    tickers: tuple[str, ...] = ()
    filing_metadata: tuple[SecFilingMetadata, ...] = ()
    response_status_code: int = Field(ge=200, lt=300)


class ToolInvocationReceiptVersion(ScopedVersion):
    """Versioned, append-only lifecycle receipt; it contains no raw SEC body."""

    case_id: str
    invocation_id: str = Field(min_length=1)
    invocation_version: int = Field(ge=1)
    state_version: int = Field(ge=1)
    invocation_state: Literal[
        "prepared",
        "blocked_before_send",
        "send_authorized",
        "send_started",
        "succeeded",
        "outcome_unknown",
        "aborted_before_send_reconciled",
    ]
    request_id: str = Field(min_length=1)
    request_digest: str = Field(min_length=1)
    tool_selection_plan_id: str = Field(min_length=1)
    tool_selection_plan_digest: str = Field(min_length=1)
    registry_snapshot_id: str = Field(min_length=1)
    registry_snapshot_digest: str = Field(min_length=1)
    tool_id: Literal["issuer_disclosure_metadata_tool"]
    route_id: Literal["issuer_disclosure_metadata_route"]
    policy_ref: str = Field(min_length=1)
    policy_digest: str = Field(min_length=1)
    approval_ref: str = Field(min_length=1)
    global_approval_id: str = Field(min_length=1)
    global_approval_nonce_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    global_approval_receipt_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    global_approval_store_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    approved_execution_scope: Literal["real_bounded_sec_metadata_pilot_only"]
    target_cik: str = Field(pattern=r"^\d{10}$")
    endpoint_host: Literal["data.sec.gov"]
    endpoint_path: str = Field(min_length=1)
    capability_grant_id: str = Field(min_length=1)
    admission_decision_id: str = Field(min_length=1)
    admission_decision_digest: str = Field(min_length=1)
    budget_reservation_id: str = Field(min_length=1)
    external_call_count: int = Field(ge=0, le=1)
    fallback_call_count: Literal[0] = 0
    request_sent_at: datetime | None = None
    send_authorized_at: datetime | None = None
    send_started_at: datetime | None = None
    user_agent_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    terminal_at: datetime | None = None
    source_metadata: SecMetadataFetchResult | None = None
    source_metadata_digest: str | None = None
    error_code: str | None = None

    @classmethod
    def create(cls, **payload: Any) -> "ToolInvocationReceiptVersion":
        draft = cls(**{**payload, "content_digest": ""})
        digest = canonical_digest({key: value for key, value in draft.model_dump(mode="json").items() if key != "content_digest"})
        return draft.model_copy(update={"content_digest": digest})


class ToolInvocationExecutionResult(StrictModel):
    status: Literal["succeeded", "blocked_before_send", "outcome_unknown"]
    receipt: ToolInvocationReceiptVersion
    reused_terminal_receipt: bool = False
    model_call_count: Literal[0] = 0
    external_call_count: int = Field(ge=0, le=1)
    tool_invocation_count: int = Field(ge=0, le=1)
    store_write_count: int = Field(ge=0)


class SingleCallSecSubmissionsClient:
    """One SEC submissions request with host/path pinning and no local cache/retry."""

    def __init__(
        self,
        *,
        user_agent: str,
        timeout_seconds: int,
        user_agent_min_length: int = 20,
        forbidden_user_agent_values: tuple[str, ...] = ("x", "placeholder", "your-app your-email@example.com", "app contact@example.com"),
        session: HttpSession | None = None,
    ):
        self._user_agent = self._validate_user_agent(
            user_agent,
            minimum_length=user_agent_min_length,
            forbidden_values=forbidden_user_agent_values,
        )
        self.user_agent_fingerprint = hashlib.sha256(self._user_agent.encode("utf-8")).hexdigest()
        self._timeout_seconds = timeout_seconds
        self._session = session or requests.Session()

    @staticmethod
    def _validate_user_agent(value: str, *, minimum_length: int, forbidden_values: tuple[str, ...]) -> str:
        user_agent = value.strip()
        lowered = user_agent.lower()
        forbidden = {item.strip().lower() for item in forbidden_values}
        if len(user_agent) < minimum_length:
            raise BoundedSecMetadataExecutionError("sec_user_agent_too_short")
        if lowered in forbidden:
            raise BoundedSecMetadataExecutionError("sec_user_agent_placeholder_forbidden")
        parts = user_agent.split()
        if len(parts) < 2 or not re.fullmatch(r"[A-Za-z][A-Za-z0-9._/-]{2,}", parts[0]):
            raise BoundedSecMetadataExecutionError("sec_user_agent_application_identifier_required")
        contact = parts[-1]
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", contact):
            raise BoundedSecMetadataExecutionError("sec_user_agent_contact_required")
        if contact.lower() in {"test@example.com", "contact@example.com", "your-email@example.com"}:
            raise BoundedSecMetadataExecutionError("sec_user_agent_placeholder_contact_forbidden")
        return user_agent

    @staticmethod
    def endpoint_for(cik: str) -> str:
        normalized = cik.strip()
        if len(normalized) != 10 or not normalized.isdigit():
            raise BoundedSecMetadataExecutionError("sec_cik_must_be_10_digits")
        return f"https://data.sec.gov/submissions/CIK{normalized}.json"

    def fetch_metadata(self, *, cik: str, filing_limit: int) -> SecMetadataFetchResult:
        url = self.endpoint_for(cik)
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != "data.sec.gov" or not parsed.path.startswith("/submissions/"):
            raise BoundedSecMetadataExecutionError("sec_endpoint_policy_violation")
        try:
            response = self._session.get(
                url,
                headers={"User-Agent": self._user_agent, "Accept": "application/json"},
                timeout=self._timeout_seconds,
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            raise SecMetadataTransportError("sec_single_call_transport_error") from exc
        if response.status_code < 200 or response.status_code >= 300:
            raise SecMetadataTransportError(f"sec_single_call_http_status:{response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise SecMetadataTransportError("sec_single_call_invalid_json") from exc
        if not isinstance(payload, dict):
            raise SecMetadataTransportError("sec_single_call_payload_not_object")
        recent = payload.get("filings", {}).get("recent", {}) if isinstance(payload.get("filings"), dict) else {}
        forms = recent.get("form") if isinstance(recent, dict) else None
        filings: list[SecFilingMetadata] = []
        if isinstance(forms, list):
            for index, form in enumerate(forms[:filing_limit]):
                filings.append(
                    SecFilingMetadata(
                        form=str(form),
                        filing_date=_indexed(recent, "filingDate", index),
                        report_date=_indexed(recent, "reportDate", index),
                        accession_number=_indexed(recent, "accessionNumber", index),
                        primary_document=_indexed(recent, "primaryDocument", index),
                    )
                )
        return SecMetadataFetchResult(
            source_url=url,
            source_host="data.sec.gov",
            cik=cik,
            issuer_name=_as_optional_text(payload.get("name")),
            tickers=tuple(sorted({str(item).upper() for item in payload.get("tickers", []) if str(item).strip()})),
            filing_metadata=tuple(filings),
            response_status_code=int(response.status_code),
        )


class BoundedSecMetadataExecutor:
    """The only M6.2 path admitted by the current user approval."""

    def __init__(
        self,
        *,
        facade: RuntimeFacade,
        security: CapabilitySecurityService,
        budgets: BudgetControlService,
        policy: BoundedSecMetadataExecutionPolicy,
        global_approval_service: M6GlobalOneShotApprovalService,
        global_approval_id: str,
        pilot_package: M6PilotPackageDigest,
        after_send_started_hook: Callable[[], None] | None = None,
        after_http_send_hook: Callable[[], None] | None = None,
    ) -> None:
        self.facade = facade
        self.security = security
        self.budgets = budgets
        self.policy = policy
        self.global_approval_service = global_approval_service
        self.global_approval_id = global_approval_id
        self.pilot_package = pilot_package
        self.after_send_started_hook = after_send_started_hook
        self.after_http_send_hook = after_http_send_hook

    def execute(
        self,
        *,
        command: CommandEnvelope,
        request: EvidenceRequest,
        plan: ToolSelectionPlan,
        capability_grant_id: str,
        reservation: BudgetReservationRequest,
        target_cik: str,
        client: SingleCallSecSubmissionsClient,
    ) -> ToolInvocationExecutionResult:
        self._validate_execution_inputs(command=command, request=request, plan=plan, reservation=reservation, target_cik=target_cik)
        invocation_id = self._invocation_id(request=request, plan=plan, target_cik=target_cik)
        existing = self.facade.store.get_latest("canonical_tool_invocation_receipt_versions", invocation_id)
        if existing:
            receipt = ToolInvocationReceiptVersion.model_validate(existing)
            if receipt.invocation_state in {"prepared", "send_authorized", "send_started"}:
                raise BoundedSecMetadataExecutionError("prepared_invocation_requires_explicit_reconciliation")
            return ToolInvocationExecutionResult(
                status=_result_status(receipt.invocation_state),
                receipt=receipt,
                reused_terminal_receipt=True,
                external_call_count=receipt.external_call_count,
                tool_invocation_count=receipt.external_call_count,
                store_write_count=0,
            )

        admission_request = self._admission_request(command, capability_grant_id)
        initial_admission = self.security.admit(command, admission_request)
        if not initial_admission.allowed:
            raise CapabilitySecurityError(initial_admission)
        self.budgets.reserve(reservation)
        try:
            global_approval = self.global_approval_service.consume(
                scope=build_m6_pilot_scope(
                    command=command,
                    request=request,
                    plan=plan,
                    approval_ref=self.policy.approval_ref,
                    approved_execution_scope=self.policy.approved_execution_scope,
                    tool_id=self.policy.tool_id,
                    route_id=self.policy.route_id,
                    network_host=self.policy.allowed_network_host,
                    target_cik=target_cik,
                ),
                package_ref=self.pilot_package.package_ref,
                package_digest=self.pilot_package.package_digest,
                package_manifest_digest=self.pilot_package.manifest_digest,
                approval_id=self.global_approval_id,
                invocation_id=invocation_id,
                local_store_identity=self.facade.store.store_identity(),
                at=command.requested_at,
            )
        except Exception:
            # A missing, expired, or already-consumed global receipt must not
            # strand local budget merely because this local store was opened.
            self._refund_if_reserved(
                reservation.reservation_id,
                reason="m6_2_global_approval_denied_before_send",
            )
            raise
        try:
            prepared = self._record_receipt(
                command=command,
                request=request,
                plan=plan,
                target_cik=target_cik,
                capability_grant_id=capability_grant_id,
                reservation_id=reservation.reservation_id,
                admission=initial_admission,
                previous=None,
                global_approval=global_approval,
                invocation_state="prepared",
                external_call_count=0,
                request_sent_at=None,
                send_authorized_at=None,
                send_started_at=None,
                user_agent_fingerprint=client.user_agent_fingerprint,
                terminal_at=None,
                source_metadata=None,
                error_code=None,
            )
        except Exception:
            self.budgets.refund(
                reservation.reservation_id,
                token_units=reservation.token_units,
                tool_calls=reservation.tool_calls,
                time_seconds=reservation.time_seconds,
                reason="m6_2_prepare_receipt_failed_before_send",
            )
            raise

        # Do not trust a preflight decision across the durable prepare boundary.
        execution_command = command.model_copy(
            update={"command_id": f"{command.command_id}:execution-gate", "requested_at": utc_now()}
        )
        execution_admission = self.security.admit(execution_command, admission_request)
        if not execution_admission.allowed:
            blocked = self._record_receipt(
                command=execution_command,
                request=request,
                plan=plan,
                target_cik=target_cik,
                capability_grant_id=capability_grant_id,
                reservation_id=reservation.reservation_id,
                admission=execution_admission,
                previous=prepared,
                global_approval=None,
                invocation_state="blocked_before_send",
                external_call_count=0,
                request_sent_at=None,
                send_authorized_at=None,
                send_started_at=None,
                user_agent_fingerprint=client.user_agent_fingerprint,
                terminal_at=utc_now(),
                source_metadata=None,
                error_code=execution_admission.denial_code or "security_admission_denied",
            )
            self.budgets.refund(
                reservation.reservation_id,
                token_units=reservation.token_units,
                tool_calls=reservation.tool_calls,
                time_seconds=reservation.time_seconds,
                reason="m6_2_execution_gate_denied_before_send",
            )
            return ToolInvocationExecutionResult(
                status="blocked_before_send",
                receipt=blocked,
                external_call_count=0,
                tool_invocation_count=0,
                store_write_count=2,
            )

        send_authorized_at = utc_now()
        send_authorized = self._record_receipt(
            command=execution_command,
            request=request,
            plan=plan,
            target_cik=target_cik,
            capability_grant_id=capability_grant_id,
            reservation_id=reservation.reservation_id,
            admission=execution_admission,
            previous=prepared,
            global_approval=None,
            invocation_state="send_authorized",
            external_call_count=0,
            request_sent_at=None,
            send_authorized_at=send_authorized_at,
            send_started_at=None,
            user_agent_fingerprint=client.user_agent_fingerprint,
            terminal_at=None,
            source_metadata=None,
            error_code=None,
        )
        sent_at = utc_now()
        send_started = self._record_receipt(
            command=execution_command,
            request=request,
            plan=plan,
            target_cik=target_cik,
            capability_grant_id=capability_grant_id,
            reservation_id=reservation.reservation_id,
            admission=execution_admission,
            previous=send_authorized,
            global_approval=None,
            invocation_state="send_started",
            external_call_count=1,
            request_sent_at=sent_at,
            send_authorized_at=send_authorized_at,
            send_started_at=sent_at,
            user_agent_fingerprint=client.user_agent_fingerprint,
            terminal_at=None,
            source_metadata=None,
            error_code=None,
        )
        if self.after_send_started_hook is not None:
            self.after_send_started_hook()
        try:
            metadata = client.fetch_metadata(cik=target_cik, filing_limit=self.policy.metadata_filing_limit)
        except SecMetadataTransportError as exc:
            self._consume_if_reserved(reservation.reservation_id, reason="m6_2_sec_single_send_outcome_unknown")
            unknown = self._record_receipt(
                command=execution_command,
                request=request,
                plan=plan,
                target_cik=target_cik,
                capability_grant_id=capability_grant_id,
                reservation_id=reservation.reservation_id,
                admission=execution_admission,
                previous=send_started,
                global_approval=None,
                invocation_state="outcome_unknown",
                external_call_count=1,
                request_sent_at=sent_at,
                send_authorized_at=send_authorized_at,
                send_started_at=sent_at,
                user_agent_fingerprint=client.user_agent_fingerprint,
                terminal_at=utc_now(),
                source_metadata=None,
                error_code=str(exc),
            )
            return ToolInvocationExecutionResult(
                status="outcome_unknown",
                receipt=unknown,
                external_call_count=1,
                tool_invocation_count=1,
                store_write_count=4,
            )

        # This runs after the request returned but before budget/terminal
        # persistence.  A process death here deliberately leaves send_started
        # for conservative restart reconciliation; it can never re-send.
        if self.after_http_send_hook is not None:
            self.after_http_send_hook()

        self._consume_if_reserved(reservation.reservation_id, reason="m6_2_sec_single_send_succeeded")
        succeeded = self._record_receipt(
            command=execution_command,
            request=request,
            plan=plan,
            target_cik=target_cik,
            capability_grant_id=capability_grant_id,
            reservation_id=reservation.reservation_id,
            admission=execution_admission,
            previous=send_started,
            global_approval=None,
            invocation_state="succeeded",
            external_call_count=1,
            request_sent_at=sent_at,
            send_authorized_at=send_authorized_at,
            send_started_at=sent_at,
            user_agent_fingerprint=client.user_agent_fingerprint,
            terminal_at=utc_now(),
            source_metadata=metadata,
            error_code=None,
        )
        return ToolInvocationExecutionResult(
            status="succeeded",
            receipt=succeeded,
            external_call_count=1,
            tool_invocation_count=1,
            store_write_count=4,
        )

    def reconcile(
        self,
        *,
        command: CommandEnvelope,
        request: EvidenceRequest,
        plan: ToolSelectionPlan,
        reservation: BudgetReservationRequest,
        target_cik: str,
    ) -> ToolInvocationExecutionResult:
        """Terminally resolve a crash-interrupted send boundary without re-sending."""
        self._validate_execution_inputs(command=command, request=request, plan=plan, reservation=reservation, target_cik=target_cik)
        invocation_id = self._invocation_id(request=request, plan=plan, target_cik=target_cik)
        raw = self.facade.store.get_latest("canonical_tool_invocation_receipt_versions", invocation_id)
        if not raw:
            raise BoundedSecMetadataExecutionError("reconciliation_receipt_not_found")
        previous = ToolInvocationReceiptVersion.model_validate(raw)
        if previous.invocation_state in {"succeeded", "blocked_before_send", "outcome_unknown", "aborted_before_send_reconciled"}:
            return ToolInvocationExecutionResult(
                status=_result_status(previous.invocation_state),
                receipt=previous,
                reused_terminal_receipt=True,
                external_call_count=previous.external_call_count,
                tool_invocation_count=previous.external_call_count,
                store_write_count=0,
            )
        if previous.invocation_state in {"prepared", "send_authorized"}:
            self._refund_if_reserved(reservation.reservation_id, reason="m6_2_reconcile_before_send_marker")
            reconciled = self._record_receipt(
                command=command,
                request=request,
                plan=plan,
                target_cik=target_cik,
                capability_grant_id=previous.capability_grant_id,
                reservation_id=reservation.reservation_id,
                admission=None,
                previous=previous,
                global_approval=None,
                invocation_state="aborted_before_send_reconciled",
                external_call_count=0,
                request_sent_at=None,
                send_authorized_at=previous.send_authorized_at,
                send_started_at=None,
                user_agent_fingerprint=previous.user_agent_fingerprint,
                terminal_at=utc_now(),
                source_metadata=None,
                error_code="m6_2_reconciled_before_send_marker_no_resend",
            )
            return ToolInvocationExecutionResult(status="blocked_before_send", receipt=reconciled, store_write_count=1, external_call_count=0, tool_invocation_count=0)
        if previous.invocation_state != "send_started":
            raise BoundedSecMetadataExecutionError(f"reconciliation_state_not_supported:{previous.invocation_state}")
        self._consume_if_reserved(reservation.reservation_id, reason="m6_2_reconcile_send_started_outcome_unknown")
        reconciled = self._record_receipt(
            command=command,
            request=request,
            plan=plan,
            target_cik=target_cik,
            capability_grant_id=previous.capability_grant_id,
            reservation_id=reservation.reservation_id,
            admission=None,
            previous=previous,
            global_approval=None,
            invocation_state="outcome_unknown",
            external_call_count=1,
            request_sent_at=previous.request_sent_at,
            send_authorized_at=previous.send_authorized_at,
            send_started_at=previous.send_started_at,
            user_agent_fingerprint=previous.user_agent_fingerprint,
            terminal_at=utc_now(),
            source_metadata=None,
            error_code="m6_2_reconciled_after_send_started_no_resend",
        )
        return ToolInvocationExecutionResult(status="outcome_unknown", receipt=reconciled, store_write_count=1, external_call_count=1, tool_invocation_count=1)

    def _validate_execution_inputs(
        self,
        *,
        command: CommandEnvelope,
        request: EvidenceRequest,
        plan: ToolSelectionPlan,
        reservation: BudgetReservationRequest,
        target_cik: str,
    ) -> None:
        self.facade._authorize("point01_shadow_compiler")
        if request.execution_admission != "not_admitted":
            raise BoundedSecMetadataExecutionError("evidence_request_execution_state_not_eligible")
        if (request.tenant_id, request.project_id, request.case_id) != (command.tenant_id, command.project_id, command.case_id):
            raise BoundedSecMetadataExecutionError("execution_request_scope_mismatch")
        if plan.request_id != request.request_id or plan.request_digest != request.request_digest:
            raise BoundedSecMetadataExecutionError("execution_plan_request_lineage_mismatch")
        if plan.registry_snapshot_id != self.policy.required_registry_snapshot_id:
            raise BoundedSecMetadataExecutionError("execution_registry_snapshot_not_approved")
        if plan.status != "await_execution_admission" or not plan.steps:
            raise BoundedSecMetadataExecutionError("execution_plan_not_ready")
        first = plan.steps[0]
        if first.selected_tool_id != self.policy.tool_id or first.selected_route_id != self.policy.route_id:
            raise BoundedSecMetadataExecutionError("execution_primary_route_not_approved")
        if first.required_capability != self.policy.capability:
            raise BoundedSecMetadataExecutionError("execution_capability_not_approved")
        if reservation.tool_calls != 1 or reservation.work_unit_id != str(command.payload.get("work_unit_id") or "") or reservation.attempt_id != str(command.payload.get("attempt_id") or ""):
            raise BoundedSecMetadataExecutionError("execution_reservation_not_exactly_one_bound_to_attempt")
        if target_cik != self.policy.allowed_cik:
            raise BoundedSecMetadataExecutionError("execution_cik_not_approved")
        endpoint_path = f"/submissions/CIK{target_cik}.json"
        if not endpoint_path.startswith(self.policy.allowed_endpoint_path_prefix):
            raise BoundedSecMetadataExecutionError("execution_endpoint_path_not_approved")
        if command.case_id is None:
            raise BoundedSecMetadataExecutionError("execution_case_id_required")

    def _admission_request(self, command: CommandEnvelope, capability_grant_id: str) -> SandboxAdmissionRequest:
        return SandboxAdmissionRequest(
            capability_grant_id=capability_grant_id,
            capability=self.policy.capability,
            tool_id=self.policy.tool_id,
            target_tenant_id=command.tenant_id,
            target_project_id=command.project_id,
            target_case_id=command.case_id,
            data_classification="public",
            network_host=self.policy.allowed_network_host,
            path=f"submissions/CIK{self.policy.allowed_cik}.json",
        )

    def _record_receipt(
        self,
        *,
        command: CommandEnvelope,
        request: EvidenceRequest,
        plan: ToolSelectionPlan,
        target_cik: str,
        capability_grant_id: str,
        reservation_id: str,
        admission: SecurityAdmissionDecision | None,
        previous: ToolInvocationReceiptVersion | None,
        global_approval: M6GlobalOneShotApprovalReceipt | None,
        invocation_state: Literal["prepared", "blocked_before_send", "send_authorized", "send_started", "succeeded", "outcome_unknown", "aborted_before_send_reconciled"],
        external_call_count: int,
        request_sent_at: datetime | None,
        send_authorized_at: datetime | None,
        send_started_at: datetime | None,
        user_agent_fingerprint: str,
        terminal_at: datetime | None,
        source_metadata: SecMetadataFetchResult | None,
        error_code: str | None,
    ) -> ToolInvocationReceiptVersion:
        invocation_id = self._invocation_id(request=request, plan=plan, target_cik=target_cik)
        version = 1 if previous is None else previous.invocation_version + 1
        before = 0 if previous is None else previous.state_version
        endpoint_path = f"/submissions/CIK{target_cik}.json"
        if global_approval is None and previous is None:
            raise BoundedSecMetadataExecutionError("global_approval_receipt_required")
        approval_id = global_approval.approval_id if global_approval else str(previous.global_approval_id)
        approval_nonce_sha256 = global_approval.approval_nonce_sha256 if global_approval else str(previous.global_approval_nonce_sha256)
        approval_digest = global_approval.content_digest if global_approval else str(previous.global_approval_receipt_digest)
        approval_store_identity = global_approval.authority_store_identity if global_approval else str(previous.global_approval_store_identity)
        admission_id = admission.decision_id if admission else str(previous.admission_decision_id)
        admission_digest = canonical_digest(admission) if admission else str(previous.admission_decision_digest)
        receipt = ToolInvocationReceiptVersion.create(
            **self.facade._scope(command, case_id=self.facade._require_case(command)),
            invocation_id=invocation_id,
            invocation_version=version,
            state_version=version,
            invocation_state=invocation_state,
            request_id=request.request_id,
            request_digest=request.request_digest,
            tool_selection_plan_id=plan.plan_id,
            tool_selection_plan_digest=plan.plan_digest,
            registry_snapshot_id=plan.registry_snapshot_id,
            registry_snapshot_digest=plan.registry_snapshot_digest,
            tool_id=self.policy.tool_id,
            route_id=self.policy.route_id,
            policy_ref=self.policy.policy_ref,
            policy_digest=canonical_digest(self.policy),
            approval_ref=self.policy.approval_ref,
            global_approval_id=approval_id,
            global_approval_nonce_sha256=approval_nonce_sha256,
            global_approval_receipt_digest=approval_digest,
            global_approval_store_identity=approval_store_identity,
            approved_execution_scope=self.policy.approved_execution_scope,
            target_cik=target_cik,
            endpoint_host=self.policy.allowed_network_host,
            endpoint_path=endpoint_path,
            capability_grant_id=capability_grant_id,
            admission_decision_id=admission_id,
            admission_decision_digest=admission_digest,
            budget_reservation_id=reservation_id,
            external_call_count=external_call_count,
            request_sent_at=request_sent_at,
            send_authorized_at=send_authorized_at,
            send_started_at=send_started_at,
            user_agent_fingerprint=user_agent_fingerprint,
            terminal_at=terminal_at,
            source_metadata=source_metadata,
            source_metadata_digest=canonical_digest(source_metadata) if source_metadata else None,
            error_code=error_code,
            current_status=invocation_state,
            supersedes_version_id=f"{invocation_id}:v{version - 1}" if previous else None,
        )
        with self.facade.store.transaction() as tx:
            self.facade._require_running_execution(
                tx,
                command,
                self.facade._require_case(command),
                str(command.payload["work_unit_id"]),
                str(command.payload["attempt_id"]),
            )
            existing = tx.get_latest("canonical_tool_invocation_receipt_versions", invocation_id)
            if previous is None and existing is not None:
                raise BoundedSecMetadataExecutionError("tool_invocation_receipt_already_exists")
            if previous is not None and (existing is None or existing.get("content_digest") != previous.content_digest):
                raise BoundedSecMetadataExecutionError("tool_invocation_receipt_transition_conflict")
            tx.insert("canonical_tool_invocation_receipt_versions", invocation_id, version, receipt.model_dump(mode="json"))
            event = self.facade._event(
                tx,
                command,
                "TOOL_INVOCATION_RECEIPT_RECORDED",
                {
                    "invocation_id": invocation_id,
                    "invocation_version": version,
                    "invocation_state": invocation_state,
                    "external_call_count": external_call_count,
                    "request_digest": request.request_digest,
                    "tool_selection_plan_digest": plan.plan_digest,
                },
                work_unit_id=str(command.payload["work_unit_id"]),
                attempt_id=str(command.payload["attempt_id"]),
            ).model_copy(update={"state_version_before": before, "state_version_after": version})
            tx.append_event(event)
        return receipt

    def _consume_if_reserved(self, reservation_id: str, *, reason: str) -> None:
        state = self.facade.store.get_latest("canonical_budget_reservation_versions", reservation_id)
        if not state:
            raise BoundedSecMetadataExecutionError("send_boundary_budget_reservation_not_found")
        if state.get("reservation_state") == "consumed":
            return
        if state.get("reservation_state") != "reserved":
            raise BoundedSecMetadataExecutionError("send_boundary_budget_not_consumable")
        self.budgets.consume(reservation_id, reason=reason)

    def _refund_if_reserved(self, reservation_id: str, *, reason: str) -> None:
        state = self.facade.store.get_latest("canonical_budget_reservation_versions", reservation_id)
        if not state:
            raise BoundedSecMetadataExecutionError("send_boundary_budget_reservation_not_found")
        if state.get("reservation_state") == "released":
            return
        if state.get("reservation_state") != "reserved":
            raise BoundedSecMetadataExecutionError("send_boundary_budget_not_refundable")
        request = BudgetReservationRequest.model_validate(state["request"])
        self.budgets.refund(
            reservation_id,
            token_units=request.token_units,
            tool_calls=request.tool_calls,
            time_seconds=request.time_seconds,
            reason=reason,
        )

    @staticmethod
    def _invocation_id(*, request: EvidenceRequest, plan: ToolSelectionPlan, target_cik: str) -> str:
        digest = canonical_digest(
            {
                "request_id": request.request_id,
                "request_digest": request.request_digest,
                "plan_id": plan.plan_id,
                "plan_digest": plan.plan_digest,
                "target_cik": target_cik,
            }
        )
        return f"tool_invocation_{digest[:24]}"


def _indexed(payload: dict[str, Any], key: str, index: int) -> str | None:
    values = payload.get(key)
    if not isinstance(values, list) or index >= len(values):
        return None
    return _as_optional_text(values[index])


def _as_optional_text(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _result_status(state: str) -> Literal["succeeded", "blocked_before_send", "outcome_unknown"]:
    if state == "succeeded":
        return "succeeded"
    if state == "blocked_before_send":
        return "blocked_before_send"
    if state == "outcome_unknown":
        return "outcome_unknown"
    if state == "aborted_before_send_reconciled":
        return "blocked_before_send"
    raise BoundedSecMetadataExecutionError(f"terminal_receipt_state_not_supported:{state}")


BOUNDED_SEC_METADATA_EXECUTION_MODELS = (
    BoundedSecMetadataExecutionPolicy,
    SecFilingMetadata,
    SecMetadataFetchResult,
    ToolInvocationReceiptVersion,
    ToolInvocationExecutionResult,
)
