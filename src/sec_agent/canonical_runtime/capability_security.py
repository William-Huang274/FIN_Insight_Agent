from __future__ import annotations

from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any, Iterable

from pydantic import Field, field_validator

from .facade import RuntimeFacade
from .models import CommandEnvelope, ResultEnvelope, StrictModel, canonical_digest


CLASSIFICATION_RANK = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}


class CapabilityGrant(StrictModel):
    grant_id: str
    tenant_id: str
    project_id: str
    case_id: str | None = None
    permission_snapshot_ref: str
    capabilities: tuple[str, ...]
    allowed_tool_ids: tuple[str, ...]
    allowed_network_hosts: tuple[str, ...] = ()
    allowed_path_prefixes: tuple[str, ...] = ()
    allowed_data_classifications: tuple[str, ...] = ("internal",)
    issued_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None

    @field_validator("grant_id", "tenant_id", "project_id", "permission_snapshot_ref")
    @classmethod
    def require_nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("nonempty_value_required")
        return value

    @field_validator("issued_at", "expires_at", "revoked_at")
    @classmethod
    def require_utc(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value)):
            raise ValueError("timezone_aware_utc_required")
        return value


class ToolManifest(StrictModel):
    tool_id: str
    capabilities: tuple[str, ...]
    allowed_network_hosts: tuple[str, ...] = ()
    allowed_path_prefixes: tuple[str, ...] = ()
    allowed_data_classifications: tuple[str, ...] = ("internal",)


class SandboxAdmissionRequest(StrictModel):
    capability_grant_id: str
    capability: str
    tool_id: str
    target_tenant_id: str
    target_project_id: str
    target_case_id: str | None = None
    data_classification: str
    network_host: str | None = None
    path: str | None = None


class SecurityAdmissionDecision(StrictModel):
    decision_id: str
    allowed: bool
    denial_code: str | None = None
    grant_id: str | None = None
    grant_version: int | None = None
    grant_digest: str | None = None
    permission_snapshot_ref: str
    request_digest: str
    evaluated_at: datetime
    trace: tuple[str, ...]
    external_call_count: int = 0

    @field_validator("evaluated_at")
    @classmethod
    def require_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
            raise ValueError("timezone_aware_utc_required")
        return value


class CapabilitySecurityError(RuntimeError):
    def __init__(self, decision: SecurityAdmissionDecision):
        self.decision = decision
        super().__init__(decision.denial_code or "security_admission_denied")


class CapabilitySecurityService:
    """Fail-closed M5.4 grant/sandbox admission service.

    It evaluates manifest, grant, tenant/privacy, network and path constraints
    without invoking a provider or external tool.  Grant authority and every
    admission decision are append-only canonical records; tool manifests remain
    local policy configuration and are package-digest bound by M5.9.
    """

    def __init__(
        self,
        facade: RuntimeFacade,
        *,
        grants: Iterable[CapabilityGrant],
        tool_manifests: Iterable[ToolManifest],
    ):
        self.facade = facade
        grant_items = tuple(grants)
        manifest_items = tuple(tool_manifests)
        self._grant_seeds = {grant.grant_id: grant for grant in grant_items}
        self._tool_manifests = {manifest.tool_id: manifest for manifest in manifest_items}
        if len(self._grant_seeds) != len(grant_items) or len(self._tool_manifests) != len(manifest_items):
            raise ValueError("duplicate_security_registry_identity")

    def register_authority(self, command: CommandEnvelope, grant: CapabilityGrant) -> ResultEnvelope:
        """Record a grant/revocation state before it may authorize an admission.

        Constructor grants are intentionally only compatibility seeds.  They are
        never sufficient for admission, which prevents a restarted process from
        silently recreating authority from local memory.
        """
        self.facade._authorize("point01_shadow_compiler")
        case_id = self.facade._require_case(command)
        if grant.tenant_id != command.tenant_id or grant.project_id != command.project_id or grant.case_id not in {None, case_id}:
            raise ValueError("capability_grant_registration_scope_mismatch")
        if grant.permission_snapshot_ref != command.permission_snapshot_ref:
            raise ValueError("capability_grant_registration_permission_snapshot_mismatch")
        scope_key, payload_digest, _ = self.facade._idempotency(command, f"capability_grant:{grant.grant_id}")
        with self.facade.store.transaction() as tx:
            existing = tx.get_idempotency(scope_key)
            if existing:
                return self.facade._reuse_or_conflict(existing, payload_digest)
            previous = tx.get_latest("canonical_capability_grant_versions", grant.grant_id)
            version = int(previous.get("grant_version", 0)) + 1 if previous else 1
            row = {
                **self.facade._scope(command, case_id=case_id),
                "grant_id": grant.grant_id,
                "grant_version": version,
                "state_version": version,
                "grant": grant.model_dump(mode="json"),
                "grant_digest": canonical_digest(grant),
                "grant_state": "revoked" if grant.revoked_at is not None else "active",
                "current_status": "revoked" if grant.revoked_at is not None else "active",
                "supersedes_version_id": f"{grant.grant_id}:v{version - 1}" if previous else None,
            }
            tx.insert("canonical_capability_grant_versions", grant.grant_id, version, self._with_content_digest(row))
            event = self.facade._event(tx, command, "CAPABILITY_GRANT_RECORDED", {"grant_id": grant.grant_id, "grant_version": version, "grant_digest": canonical_digest(grant), "grant_state": row["grant_state"]})
            tx.append_event(event)
            result = ResultEnvelope(command_id=command.command_id, status="succeeded", state_version_before=version - 1, state_version_after=version, event_ids=(event.event_id,), projection_refs=(f"{grant.grant_id}:v{version}",))
            tx.put_idempotency(scope_key, payload_digest, result.model_dump(mode="json"))
        self._grant_seeds[grant.grant_id] = grant
        return result

    def admit(self, command: CommandEnvelope, request: SandboxAdmissionRequest) -> SecurityAdmissionDecision:
        with self.facade.store.transaction() as tx:
            return self._admit_in_tx(tx, command, request)

    def execute_checkpoint_write(
        self,
        command: CommandEnvelope,
        request: SandboxAdmissionRequest,
    ) -> ResultEnvelope:
        denied_decisions: list[SecurityAdmissionDecision] = []

        def checkpoint_mutation_guard(tx: Any) -> None:
            decision = self._admit_in_tx(tx, command, request)
            if not decision.allowed:
                denied_decisions.append(decision)
                raise CapabilitySecurityError(decision)
            if request.capability != "checkpoint.write" or request.tool_id != "canonical_checkpoint_store":
                denied = self._deny(tx, command, request, list(decision.trace), "protected_operation_scope_denied", grant_version=decision.grant_version)
                denied_decisions.append(denied)
                raise CapabilitySecurityError(denied)

        try:
            return self.facade.create_checkpoint_version(command, checkpoint_mutation_guard=checkpoint_mutation_guard)
        except CapabilitySecurityError:
            if denied_decisions:
                with self.facade.store.transaction() as tx:
                    self._record_decision(tx, command, denied_decisions[-1])
            raise

    def _admit_in_tx(self, tx: Any, command: CommandEnvelope, request: SandboxAdmissionRequest) -> SecurityAdmissionDecision:
        trace: list[str] = ["admission_started"]
        manifest = self._tool_manifests.get(request.tool_id)
        if manifest is None:
            return self._deny(tx, command, request, trace, "unknown_tool")
        trace.append("tool_manifest_resolved")
        known_capabilities = {capability for item in self._tool_manifests.values() for capability in item.capabilities}
        if request.capability not in known_capabilities:
            return self._deny(tx, command, request, trace, "unknown_capability")
        resolved = self._resolve_grant(tx, request.capability_grant_id)
        if resolved is None:
            return self._deny(tx, command, request, trace, "capability_grant_not_found")
        grant, grant_version = resolved
        trace.append("capability_grant_resolved")
        if request.target_tenant_id != command.tenant_id or request.target_project_id != command.project_id or request.target_case_id != command.case_id:
            return self._deny(tx, command, request, trace, "tenant_cross_read_denied", grant=grant, grant_version=grant_version)
        trace.append("request_scope_matches_command")
        if grant.tenant_id != command.tenant_id or grant.project_id != command.project_id or grant.case_id not in {None, command.case_id}:
            return self._deny(tx, command, request, trace, "grant_scope_mismatch", grant=grant, grant_version=grant_version)
        if grant.permission_snapshot_ref != command.permission_snapshot_ref:
            return self._deny(tx, command, request, trace, "permission_snapshot_mismatch", grant=grant, grant_version=grant_version)
        trace.append("grant_scope_and_permission_snapshot_bound")
        if grant.revoked_at is not None and grant.revoked_at <= command.requested_at:
            return self._deny(tx, command, request, trace, "capability_grant_revoked", grant=grant, grant_version=grant_version)
        if grant.expires_at <= command.requested_at:
            return self._deny(tx, command, request, trace, "capability_grant_expired", grant=grant, grant_version=grant_version)
        if request.capability not in manifest.capabilities:
            return self._deny(tx, command, request, trace, "tool_capability_not_supported", grant=grant, grant_version=grant_version)
        if request.capability not in grant.capabilities:
            return self._deny(tx, command, request, trace, "capability_not_granted", grant=grant, grant_version=grant_version)
        if request.tool_id not in grant.allowed_tool_ids:
            return self._deny(tx, command, request, trace, "tool_scope_denied", grant=grant, grant_version=grant_version)
        trace.append("capability_and_tool_scope_allowed")
        if request.data_classification not in CLASSIFICATION_RANK:
            return self._deny(tx, command, request, trace, "unknown_data_classification", grant=grant, grant_version=grant_version)
        if request.data_classification not in grant.allowed_data_classifications or request.data_classification not in manifest.allowed_data_classifications:
            return self._deny(tx, command, request, trace, "privacy_classification_denied", grant=grant, grant_version=grant_version)
        if request.network_host and not self._network_allowed(request.network_host, grant, manifest):
            return self._deny(tx, command, request, trace, "network_scope_denied", grant=grant, grant_version=grant_version)
        if request.path and not self._path_allowed(request.path, grant, manifest):
            return self._deny(tx, command, request, trace, "path_scope_denied", grant=grant, grant_version=grant_version)
        trace.extend(("privacy_scope_allowed", "sandbox_scope_allowed", "admission_allowed"))
        decision = self._decision(command, request, trace, allowed=True, grant=grant, grant_version=grant_version)
        self._record_decision(tx, command, decision)
        return decision

    def audit_view(self) -> dict[str, Any]:
        decisions = [SecurityAdmissionDecision.model_validate(row["decision"]) for row in self.facade.store.list_versions("canonical_security_admission_versions")]
        return {
            "scope": "Point01_M5_4_capability_security_sandbox_control_plane_only",
            "decision_count": len(decisions),
            "allowed_count": sum(1 for decision in decisions if decision.allowed),
            "denied_count": sum(1 for decision in decisions if not decision.allowed),
            "decisions": [decision.model_dump(mode="json") for decision in decisions],
            "external_tool_execution_count": 0,
            "provider_execution_count": 0,
        }

    def _deny(
        self,
        tx: Any,
        command: CommandEnvelope,
        request: SandboxAdmissionRequest,
        trace: list[str],
        denial_code: str,
        *,
        grant: CapabilityGrant | None = None,
        grant_version: int | None = None,
    ) -> SecurityAdmissionDecision:
        trace.append(f"denied:{denial_code}")
        decision = self._decision(command, request, trace, allowed=False, denial_code=denial_code, grant=grant, grant_version=grant_version)
        self._record_decision(tx, command, decision)
        return decision

    @staticmethod
    def _resolve_grant(tx: Any, grant_id: str) -> tuple[CapabilityGrant, int] | None:
        row = tx.get_latest("canonical_capability_grant_versions", grant_id)
        return (CapabilityGrant.model_validate(row["grant"]), int(row["grant_version"])) if row else None

    def _record_decision(self, tx: Any, command: CommandEnvelope, decision: SecurityAdmissionDecision) -> None:
        if tx.get_latest("canonical_security_admission_versions", decision.decision_id):
            return
        row = {
            **self.facade._scope(command, case_id=self.facade._require_case(command)),
            "decision_id": decision.decision_id,
            "decision_version": 1,
            "state_version": 1,
            "decision": decision.model_dump(mode="json"),
            "current_status": "allowed" if decision.allowed else "denied",
        }
        tx.insert("canonical_security_admission_versions", decision.decision_id, 1, self._with_content_digest(row))

    @staticmethod
    def _with_content_digest(row: dict[str, Any]) -> dict[str, Any]:
        return {**row, "content_digest": canonical_digest({key: value for key, value in row.items() if key != "content_digest"})}

    @staticmethod
    def _network_allowed(host: str, grant: CapabilityGrant, manifest: ToolManifest) -> bool:
        normalized = host.lower().strip().rstrip(".")
        return normalized in {item.lower().rstrip(".") for item in grant.allowed_network_hosts} and normalized in {
            item.lower().rstrip(".") for item in manifest.allowed_network_hosts
        }

    @staticmethod
    def _path_allowed(path: str, grant: CapabilityGrant, manifest: ToolManifest) -> bool:
        candidate = PurePosixPath(path)
        if candidate.is_absolute() or ".." in candidate.parts:
            return False
        normalized = str(candidate)
        return CapabilitySecurityService._within_any_prefix(normalized, grant.allowed_path_prefixes) and CapabilitySecurityService._within_any_prefix(
            normalized, manifest.allowed_path_prefixes
        )

    @staticmethod
    def _within_any_prefix(value: str, prefixes: tuple[str, ...]) -> bool:
        return any(value == prefix.rstrip("/") or value.startswith(prefix.rstrip("/") + "/") for prefix in prefixes)

    @staticmethod
    def _decision(
        command: CommandEnvelope,
        request: SandboxAdmissionRequest,
        trace: list[str],
        *,
        allowed: bool,
        denial_code: str | None = None,
        grant: CapabilityGrant | None = None,
        grant_version: int | None = None,
    ) -> SecurityAdmissionDecision:
        request_digest = canonical_digest(request)
        grant_digest = canonical_digest(grant) if grant else None
        decision_payload = {
            "command_id": command.command_id,
            "request_digest": request_digest,
            "grant_digest": grant_digest,
            "grant_version": grant_version,
            "allowed": allowed,
            "denial_code": denial_code,
            "evaluated_at": command.requested_at.isoformat(),
        }
        return SecurityAdmissionDecision(
            decision_id=f"security_{canonical_digest(decision_payload)[:24]}",
            allowed=allowed,
            denial_code=denial_code,
            grant_id=grant.grant_id if grant else None,
            grant_version=grant_version,
            grant_digest=grant_digest,
            permission_snapshot_ref=command.permission_snapshot_ref,
            request_digest=request_digest,
            evaluated_at=command.requested_at,
            trace=tuple(trace),
        )


CAPABILITY_SECURITY_MODELS = (CapabilityGrant, ToolManifest, SandboxAdmissionRequest, SecurityAdmissionDecision)
