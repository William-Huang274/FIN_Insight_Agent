from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from sec_agent.canonical_runtime import FileCanonicalObjectStore, RuntimeFacade
from sec_agent.canonical_runtime.facade import RuntimeFacadeError
from sec_agent.canonical_runtime.feature_flags import FeatureFlagError, FeatureFlagRegistry
from sec_agent.canonical_runtime.models import CommandEnvelope, canonical_digest, utc_now
from sec_agent.canonical_runtime.store import IdempotencyConflict, SQLiteCanonicalStore
from sec_agent.runtime_resource_registry import (
    read_registered_runtime_json,
    resolve_registered_runtime_resource,
)


P36_CANDIDATE_PROFILE = "configs/releases/fin_ia_0_1_vt4_p36_candidate_profile_v1_0.json"
P36_CANDIDATE_PROFILE_RESOURCE_ID = "application.contract.p36_candidate_profile"
POINT01_FEATURE_FLAGS_RESOURCE_ID = "application.config.point01_feature_flags"


def load_p36_candidate_profile(repo_root: str | Path) -> dict[str, Any] | None:
    return read_registered_runtime_json(
        repo_root,
        P36_CANDIDATE_PROFILE_RESOURCE_ID,
    )


@dataclass(frozen=True)
class CasePrincipal:
    tenant_id: str
    project_id: str
    actor_id: str
    permissions: frozenset[str]


@dataclass(frozen=True)
class CreateCaseDraft:
    query: str
    as_of: datetime
    language: str
    source_policy_ref: str
    idempotency_key: str


class CaseServiceError(RuntimeError):
    def __init__(self, error_code: str, status_code: int, **detail: Any):
        super().__init__(error_code)
        self.error_code = error_code
        self.status_code = status_code
        self.detail = {"reason": error_code, **detail}


class CaseService:
    """Internal fixture Case service backed only by the canonical runtime boundary."""

    def __init__(self, facade: RuntimeFacade | None, *, unavailable_reason: str | None = None):
        self._facade = facade
        self._unavailable_reason = unavailable_reason

    @classmethod
    def for_fixture_root(cls, fixture_root: str | Path, *, repo_root: str | Path) -> "CaseService":
        root = Path(fixture_root).resolve()
        repo = Path(repo_root).resolve()
        flags = FeatureFlagRegistry.from_path(
            resolve_registered_runtime_resource(
                repo,
                POINT01_FEATURE_FLAGS_RESOURCE_ID,
            )
        )
        profile = load_p36_candidate_profile(repo)
        facade = RuntimeFacade(
            SQLiteCanonicalStore(root / "canonical.sqlite"),
            FileCanonicalObjectStore(root / "objects"),
            flags,
            mode="shadow",
            grants={"point01.shadow.write"},
            planning_fixture_profile=profile,
        )
        return cls(facade)

    @classmethod
    def unavailable(cls, reason: str = "explicit_fixture_root_required") -> "CaseService":
        return cls(None, unavailable_reason=reason)

    def create_case(self, command: CreateCaseDraft, principal: CasePrincipal, *, trace_id: str) -> dict[str, Any]:
        self._require_admitted()
        self._require_permission(principal, "case:create")
        self._validate_create(command)
        case_id = "case_" + canonical_digest(
            {
                "tenant_id": principal.tenant_id,
                "project_id": principal.project_id,
                "idempotency_key": command.idempotency_key,
            }
        )[:24]
        envelope = CommandEnvelope(
            command_id="p02_case_create_" + canonical_digest({"case_id": case_id, "key": command.idempotency_key})[:24],
            command_type="CREATE_RESEARCH_CASE",
            tenant_id=principal.tenant_id,
            project_id=principal.project_id,
            case_id=case_id,
            actor_snapshot_ref=f"fixture_actor:{principal.actor_id}",
            permission_snapshot_ref=f"fixture_permissions:{principal.tenant_id}:{principal.actor_id}",
            policy_config_refs=(command.source_policy_ref, "point02.fixture.internal"),
            idempotency_key=command.idempotency_key,
            expected_state_version=0,
            correlation_id=trace_id,
            requested_at=utc_now(),
            payload={
                "case_id": case_id,
                "query": command.query,
                "as_of": command.as_of,
                "language": command.language,
                "source_policy_ref": command.source_policy_ref,
                "accountable_owner_ref": f"fixture_analyst:{principal.actor_id}",
                "case_type": "fixture_internal",
            },
        )
        try:
            self._facade_or_raise().create_research_case(envelope)
        except IdempotencyConflict as exc:
            raise CaseServiceError("idempotency_conflict", 409, case_id=case_id) from exc
        except (RuntimeFacadeError, FeatureFlagError) as exc:
            raise CaseServiceError("fixture_case_create_rejected", 403, cause=str(exc)) from exc
        workspace = self._workspace_for_case(case_id, principal)
        self._facade_or_raise().object_store.put_json(
            workspace,
            namespace="point02/case-workspaces",
            artifact_type="fixture_case_workspace_projection",
        )
        return workspace

    def list_cases(self, principal: CasePrincipal) -> dict[str, Any]:
        self._require_admitted()
        self._require_permission(principal, "case:read")
        facade = self._facade_or_raise()
        rows = facade.store.list_latest("canonical_research_cases")
        items = []
        for case in rows:
            if not self._matches_scope(case, principal):
                continue
            summary = facade.store.get_latest("canonical_case_control_versions", str(case["case_control_summary_ref"]))
            if not summary:
                continue
            items.append(self._task_center_row(case, summary))
        return {"items": sorted(items, key=lambda item: (item["updated_at"], item["case_id"]), reverse=True), "next_cursor": None}

    def get_case(
        self,
        case_id: str,
        principal: CasePrincipal,
        *,
        expected_case_version: int | None = None,
    ) -> dict[str, Any]:
        self._require_admitted()
        self._require_permission(principal, "case:read")
        workspace = self._workspace_for_case(case_id, principal)
        if expected_case_version is not None and expected_case_version != workspace["case_version"]:
            raise CaseServiceError(
                "version_conflict",
                409,
                case_id=case_id,
                expected_version=expected_case_version,
                current_version=workspace["case_version"],
            )
        return workspace

    def _workspace_for_case(self, case_id: str, principal: CasePrincipal) -> dict[str, Any]:
        facade = self._facade_or_raise()
        case = facade.store.get_latest("canonical_research_cases", case_id)
        if not case or not self._matches_scope(case, principal):
            raise CaseServiceError("case_not_found", 404, case_id=case_id)
        summary = facade.store.get_latest("canonical_case_control_versions", str(case["case_control_summary_ref"]))
        if not summary or not self._matches_scope(summary, principal):
            raise CaseServiceError("case_not_found", 404, case_id=case_id)
        return {
            "case_id": str(case["case_id"]),
            "case_version": int(case["case_version"]),
            "summary_version": int(summary["summary_version"]),
            "query": str(summary["query"]),
            "as_of": str(summary["as_of"]),
            "language": str(summary["language"]),
            "planning_checkpoint_state": "legacy_authority_retained",
        }

    @staticmethod
    def _task_center_row(case: Mapping[str, Any], summary: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "case_id": str(case["case_id"]),
            "case_version": int(case["case_version"]),
            "query": str(summary["query"]),
            "status": str(case["current_status"]),
            "updated_at": str(case["recorded_at"]),
        }

    @staticmethod
    def _matches_scope(row: Mapping[str, Any], principal: CasePrincipal) -> bool:
        return row.get("tenant_id") == principal.tenant_id and row.get("project_id") == principal.project_id

    def _facade_or_raise(self) -> RuntimeFacade:
        if self._facade is None:
            raise CaseServiceError("operation_not_admitted", 403, reason_detail=self._unavailable_reason)
        return self._facade

    def _require_admitted(self) -> None:
        self._facade_or_raise()

    @staticmethod
    def _require_permission(principal: CasePrincipal, permission: str) -> None:
        if not principal.tenant_id or not principal.project_id or not principal.actor_id or permission not in principal.permissions:
            raise CaseServiceError("permission_denied", 403, required_permission=permission)

    @staticmethod
    def _validate_create(command: CreateCaseDraft) -> None:
        if not command.query.strip() or not command.language.strip() or not command.source_policy_ref.strip() or not command.idempotency_key.strip():
            raise CaseServiceError("request_validation_error", 422)
        if command.as_of.tzinfo is None or command.as_of.utcoffset() is None:
            raise CaseServiceError("request_validation_error", 422, field="as_of")


def case_service_from_env(repo_root: str | Path) -> CaseService:
    fixture_root = os.environ.get("FINSIGHT_P02_FIXTURE_ROOT", "").strip()
    if not fixture_root:
        return CaseService.unavailable()
    return CaseService.for_fixture_root(fixture_root, repo_root=repo_root)
