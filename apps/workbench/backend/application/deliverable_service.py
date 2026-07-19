from __future__ import annotations

import html
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from sec_agent.canonical_runtime.models import (
    ArtifactProvenanceManifestVersion,
    CanonicalPresentationModelVersion,
    DeliverableReviewActionVersion,
    EventEnvelope,
    canonical_digest,
    utc_now,
)
from sec_agent.canonical_runtime.store import IdempotencyConflict, TransactionConflict

from .case_service import CasePrincipal, CaseService, load_p36_candidate_profile
from .evidence_service import EvidenceService, EvidenceServiceError


CONTRACT_RELATIVE_PATH = (
    "configs/releases/fin_ia_0_1_vt3_deliverable_review_trace_contract_v1_0.json"
)
WORKPAPER_TABLE = "canonical_workpaper_projection_versions"
LEAD_REVIEW_TABLE = "canonical_lead_review_decision_versions"
DELIVERABLE_TABLE = "canonical_deliverable_projection_versions"
REVIEW_TABLE = "canonical_deliverable_review_action_versions"
TRACE_TABLE = "canonical_artifact_provenance_manifest_versions"


@dataclass(frozen=True)
class CompileDeliverablePreviewDraft:
    expected_workpaper_version: int
    expected_workpaper_content_digest: str
    writer_admission_id: str
    actor_ref: str
    idempotency_key: str


@dataclass(frozen=True)
class ReviewDeliverableDraft:
    expected_artifact_version: int
    expected_content_digest: str
    expected_canonical_presentation_digest: str
    action_type: str
    reason: str
    actor_ref: str
    idempotency_key: str


class DeliverableServiceError(RuntimeError):
    def __init__(self, error_code: str, status_code: int, **detail: Any):
        super().__init__(error_code)
        self.error_code = error_code
        self.status_code = status_code
        self.detail = {"reason": error_code, **detail}


class DeliverableService:
    """VT3's deterministic, no-source deliverable preview boundary."""

    def __init__(
        self,
        facade: Any | None,
        evidence: EvidenceService,
        *,
        contract: Mapping[str, Any],
        p36_profile: Mapping[str, Any] | None = None,
    ):
        self._facade = facade
        self._evidence = evidence
        self._contract = dict(contract)
        self._p36_profile = dict(p36_profile or {})
        self._configure()

    @classmethod
    def from_services(
        cls,
        case_service: CaseService,
        evidence_service: EvidenceService,
        *,
        repo_root: str | Path,
    ) -> "DeliverableService":
        contract = json.loads(
            (Path(repo_root) / CONTRACT_RELATIVE_PATH).read_text(encoding="utf-8")
        )
        return cls(
            getattr(case_service, "_facade", None),
            evidence_service,
            contract=contract,
            p36_profile=load_p36_candidate_profile(repo_root),
        )

    def get_latest(self, case_id: str, principal: CasePrincipal) -> dict[str, Any]:
        self._require_permission(principal, "deliverable:read")
        artifact = self._single_row(
            DELIVERABLE_TABLE, case_id, principal, "deliverable_preview_not_found"
        )
        return self._deliverable_view(artifact, principal)

    def compile_preview(
        self,
        case_id: str,
        draft: CompileDeliverablePreviewDraft,
        principal: CasePrincipal,
        *,
        trace_id: str,
    ) -> dict[str, Any]:
        self._require_command(
            case_id,
            draft.actor_ref,
            draft.idempotency_key,
            principal,
            "deliverable:write",
            trace_id,
        )
        store = self._store()
        payload_digest = canonical_digest(
            {"operation": "compile_deliverable_preview", "case_id": case_id, **draft.__dict__}
        )
        scope_key = self._scope(case_id, draft.idempotency_key, principal)
        try:
            with store.transaction() as tx:
                reused = self._check_idempotency(tx, scope_key, payload_digest)
                if not reused:
                    self._evidence._case_row(tx, case_id, principal)
                    self._evidence._actor_snapshot(tx, draft.actor_ref, principal)
                    if self._rows(tx, DELIVERABLE_TABLE, case_id, principal):
                        raise DeliverableServiceError("deliverable_preview_already_compiled", 409)
                    workpaper, lead_review, admission = self._admitted_workpaper(
                        tx, case_id, principal, draft
                    )
                    presentation = self._compose_presentation(
                        case_id=case_id,
                        workpaper=workpaper,
                        lead_review=lead_review,
                        admission=admission,
                    )
                    artifact = self._presentation_model(
                        case_id=case_id,
                        actor_ref=draft.actor_ref,
                        principal=principal,
                        trace_id=trace_id,
                        workpaper=workpaper,
                        lead_review=lead_review,
                        admission=admission,
                        presentation=presentation,
                    )
                    artifact = self._with_digest(artifact)
                    manifest = self._trace_manifest(
                        case_id=case_id,
                        actor_ref=draft.actor_ref,
                        principal=principal,
                        trace_id=trace_id,
                        artifact=artifact,
                    )
                    manifest = self._with_digest(manifest)
                    tx.insert(
                        DELIVERABLE_TABLE,
                        artifact.deliverable_id,
                        artifact.artifact_version,
                        artifact.model_dump(mode="json"),
                    )
                    tx.insert(
                        TRACE_TABLE,
                        manifest.manifest_id,
                        manifest.manifest_version,
                        manifest.model_dump(mode="json"),
                    )
                    preview_event = self._event(
                        tx,
                        event_type="DELIVERABLE_PREVIEW_COMPILED",
                        actor_ref=draft.actor_ref,
                        trace_id=trace_id,
                        state_before=0,
                        state_after=1,
                        payload={
                            "artifact_version_id": artifact.artifact_version_id,
                            "artifact_version": artifact.artifact_version,
                            "content_digest": artifact.content_digest,
                            "canonical_presentation_digest": artifact.canonical_presentation_digest,
                            "workpaper_projection_version_id": artifact.workpaper_projection_version_id,
                            "workpaper_content_digest": artifact.workpaper_content_digest,
                            "writer_admission_id": artifact.writer_admission_id,
                        },
                    )
                    tx.append_event(preview_event)
                    trace_event = self._event(
                        tx,
                        event_type="TRACE_MANIFEST_COMPILED",
                        actor_ref=draft.actor_ref,
                        trace_id=trace_id,
                        state_before=0,
                        state_after=1,
                        causation_event_id=preview_event.event_id,
                        payload={
                            "manifest_id": manifest.manifest_id,
                            "manifest_version_id": manifest.manifest_version_id,
                            "artifact_version_id": artifact.artifact_version_id,
                            "artifact_version": artifact.artifact_version,
                            "artifact_content_digest": artifact.content_digest,
                            "canonical_presentation_digest": artifact.canonical_presentation_digest,
                            "claim_count": len(manifest.claim_to_source),
                            "source_count": len(manifest.source_to_claim),
                        },
                    )
                    tx.append_event(trace_event)
                    tx.put_idempotency(
                        scope_key,
                        payload_digest,
                        {
                            "artifact_version_id": artifact.artifact_version_id,
                            "manifest_version_id": manifest.manifest_version_id,
                        },
                    )
        except Exception as exc:
            raise self._service_error(exc) from exc
        return self.get_latest(case_id, principal)

    def review_version(
        self,
        deliverable_id: str,
        artifact_version: int,
        draft: ReviewDeliverableDraft,
        principal: CasePrincipal,
        *,
        trace_id: str,
    ) -> dict[str, Any]:
        self._require_permission(principal, "deliverable_review:decide")
        if draft.actor_ref != principal.actor_id:
            raise DeliverableServiceError("actor_scope_mismatch", 403)
        if not deliverable_id.strip() or not draft.idempotency_key.strip() or not trace_id.strip():
            raise DeliverableServiceError("request_validation_error", 422)
        if draft.action_type not in self._contract["review_contract"]["actions"]:
            raise DeliverableServiceError("deliverable_review_action_not_allowed", 422)
        if not draft.reason.strip():
            raise DeliverableServiceError("deliverable_review_reason_required", 422)
        store = self._store()
        try:
            with store.transaction() as tx:
                artifact = self._artifact_row_by_identity(
                    tx, deliverable_id, artifact_version, principal
                )
                case_id = str(artifact["case_id"])
                payload_digest = canonical_digest(
                    {
                        "operation": "create_deliverable_review_action",
                        "case_id": case_id,
                        "deliverable_id": deliverable_id,
                        "artifact_version": artifact_version,
                        **draft.__dict__,
                    }
                )
                scope_key = self._scope(case_id, draft.idempotency_key, principal)
                reused = self._check_idempotency(tx, scope_key, payload_digest)
                if not reused:
                    self._evidence._case_row(tx, case_id, principal)
                    self._evidence._actor_snapshot(tx, draft.actor_ref, principal)
                    self._require_exact_artifact(artifact, draft)
                    previous_actions = self._review_actions_for_artifact(
                        tx, case_id, artifact, principal
                    )
                    if any(row["terminal"] for row in previous_actions):
                        raise DeliverableServiceError("deliverable_review_terminal_action_exists", 409)
                    review_id = "deliverable_review_" + canonical_digest(
                        {
                            "artifact_version_id": artifact["artifact_version_id"],
                            "action_type": draft.action_type,
                            "reason": draft.reason.strip(),
                            "actor_ref": draft.actor_ref,
                            "idempotency_key": draft.idempotency_key,
                        }
                    )[:24]
                    terminal = draft.action_type in self._contract["review_contract"]["terminal_actions"]
                    review = DeliverableReviewActionVersion(
                        tenant_id=principal.tenant_id,
                        project_id=principal.project_id,
                        case_id=case_id,
                        actor_snapshot_ref=f"fixture_actor:{draft.actor_ref}",
                        permission_snapshot_ref=self._evidence._permission_ref(principal),
                        policy_config_refs=(
                            "vt4.p36.deliverable.review.fixture.internal"
                            if len(artifact["material_claims"]) > 3
                            else "vt3.deliverable.review.fixture.internal",
                            str(artifact["policy_config_refs"][-1]),
                        ),
                        correlation_id=trace_id,
                        current_status=draft.action_type,
                        review_action_id=review_id,
                        review_action_version_id=f"{review_id}:v1",
                        review_action_version=1,
                        artifact_version_id=str(artifact["artifact_version_id"]),
                        artifact_version=int(artifact["artifact_version"]),
                        artifact_content_digest=str(artifact["content_digest"]),
                        canonical_presentation_digest=str(
                            artifact["canonical_presentation_digest"]
                        ),
                        action_type=draft.action_type,
                        reason=draft.reason.strip(),
                        terminal=terminal,
                    )
                    review = self._with_digest(review)
                    tx.insert(
                        REVIEW_TABLE,
                        review_id,
                        review.review_action_version,
                        review.model_dump(mode="json"),
                    )
                    event = self._event(
                        tx,
                        event_type="DELIVERABLE_REVIEW_RECORDED",
                        actor_ref=draft.actor_ref,
                        trace_id=trace_id,
                        state_before=len(previous_actions),
                        state_after=len(previous_actions) + 1,
                        payload={
                            "review_action_id": review.review_action_id,
                            "artifact_version_id": review.artifact_version_id,
                            "artifact_version": review.artifact_version,
                            "artifact_content_digest": review.artifact_content_digest,
                            "canonical_presentation_digest": review.canonical_presentation_digest,
                            "action_type": review.action_type,
                            "terminal": review.terminal,
                        },
                    )
                    tx.append_event(event)
                    tx.put_idempotency(
                        scope_key,
                        payload_digest,
                        {"review_action_id": review.review_action_id},
                    )
        except Exception as exc:
            raise self._service_error(exc) from exc
        return self.get_latest(case_id, principal)

    def get_trace(self, case_id: str, principal: CasePrincipal) -> dict[str, Any]:
        self._require_permission(principal, "trace:read")
        store = self._store()
        artifact = self._single_row(
            DELIVERABLE_TABLE, case_id, principal, "deliverable_preview_not_found"
        )
        manifests = [
            row
            for row in self._rows(store, TRACE_TABLE, case_id, principal)
            if row["artifact_version_id"] == artifact["artifact_version_id"]
            and row["artifact_content_digest"] == artifact["content_digest"]
            and row["canonical_presentation_digest"]
            == artifact["canonical_presentation_digest"]
        ]
        if len(manifests) > 1:
            raise DeliverableServiceError("trace_manifest_cardinality_violation", 409)
        if not manifests:
            raise DeliverableServiceError("trace_manifest_not_found", 404)
        manifest = manifests[0]
        return {
            "case_id": case_id,
            "manifest_id": manifest["manifest_id"],
            "artifact_version_id": manifest["artifact_version_id"],
            "artifact_version": manifest["artifact_version"],
            "artifact_content_digest": manifest["artifact_content_digest"],
            "canonical_presentation_digest": manifest["canonical_presentation_digest"],
            "nodes": list(manifest["nodes"]),
            "edges": list(manifest["edges"]),
            "claim_to_source": {
                key: list(value) for key, value in manifest["claim_to_source"].items()
            },
            "source_to_claim": {
                key: list(value) for key, value in manifest["source_to_claim"].items()
            },
            "redaction_summary": dict(manifest["redaction_summary"]),
        }

    def _configure(self) -> None:
        if self._contract.get("schema_version") != (
            "fin_ia_0_1_vt3_deliverable_review_trace_contract_v1_0"
        ):
            raise ValueError("vt3_deliverable_contract_version_invalid")
        for key, value in self._contract["hard_boundaries"].items():
            if key in {"real_business_case_mutation", "production_cutover"}:
                if value != "forbidden":
                    raise ValueError(f"vt3_deliverable_boundary_open:{key}")
            elif value != 0:
                raise ValueError(f"vt3_deliverable_boundary_open:{key}")
        composer = self._contract["composer_contract"]
        if composer["mode"] != "deterministic_no_source_fixture_composer":
            raise ValueError("vt3_deliverable_composer_not_deterministic")
        if any(composer["call_counts"].values()):
            raise ValueError("vt3_deliverable_composer_calls_not_zero")
        if self._contract["presentation_contract"]["renderers"] != ["html", "markdown"]:
            raise ValueError("vt3_deliverable_renderers_invalid")
        wire = self._contract["wire_contract"]
        if wire["compile_command_fields"] != [
            "expected_workpaper_version",
            "expected_workpaper_content_digest",
            "writer_admission_id",
            "actor_ref",
            "idempotency_key",
        ]:
            raise ValueError("vt3_deliverable_compile_wire_contract_invalid")
        if wire["review_command_fields"] != [
            "expected_artifact_version",
            "expected_content_digest",
            "expected_canonical_presentation_digest",
            "action_type",
            "reason",
            "actor_ref",
            "idempotency_key",
        ]:
            raise ValueError("vt3_deliverable_review_wire_contract_invalid")
        if wire["deliverable_view_fields"] != [
            "case_id",
            "deliverable_id",
            "artifact_version_id",
            "artifact_version",
            "content_digest",
            "canonical_presentation_digest",
            "status",
            "title",
            "sections",
            "material_claims",
            "renderings",
            "review_actions",
            "hard_boundaries",
        ]:
            raise ValueError("vt3_deliverable_view_wire_contract_invalid")
        if wire["trace_view_fields"] != [
            "case_id",
            "manifest_id",
            "artifact_version_id",
            "artifact_version",
            "artifact_content_digest",
            "canonical_presentation_digest",
            "nodes",
            "edges",
            "claim_to_source",
            "source_to_claim",
            "redaction_summary",
        ]:
            raise ValueError("vt3_trace_view_wire_contract_invalid")
        if self._contract["routes"] != [
            {
                "method": "GET",
                "path": "/api/v1/cases/{case_id}/deliverables",
                "operation": "getDeliverableHead",
                "permission": "deliverable:read",
            },
            {
                "method": "POST",
                "path": "/api/v1/cases/{case_id}/deliverables",
                "operation": "compileDeliverablePreviewFixture",
                "permission": "deliverable:write",
            },
            {
                "method": "POST",
                "path": "/api/v1/artifacts/{deliverable_id}/versions/{artifact_version}/review-actions",
                "operation": "createDeliverableReviewAction",
                "permission": "deliverable_review:decide",
            },
            {
                "method": "GET",
                "path": "/api/v1/cases/{case_id}/trace",
                "operation": "getCaseTrace",
                "permission": "trace:read",
            },
        ]:
            raise ValueError("vt3_deliverable_routes_contract_invalid")
        self._contract_digest = canonical_digest(self._contract)

    def _admitted_workpaper(
        self,
        catalog: Any,
        case_id: str,
        principal: CasePrincipal,
        draft: CompileDeliverablePreviewDraft,
    ) -> tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]]:
        workpaper = self._single_row_from(
            catalog, WORKPAPER_TABLE, case_id, principal, "workpaper_required"
        )
        if int(workpaper["workpaper_version"]) != draft.expected_workpaper_version:
            raise DeliverableServiceError(
                "version_conflict",
                409,
                expected_version=draft.expected_workpaper_version,
                current_version=workpaper["workpaper_version"],
            )
        if workpaper["content_digest"] != draft.expected_workpaper_content_digest:
            raise DeliverableServiceError("workpaper_content_digest_mismatch", 409)
        self._require_zero_vt2_boundaries(workpaper)
        reviews = [
            row
            for row in self._rows(catalog, LEAD_REVIEW_TABLE, case_id, principal)
            if row["workpaper_id"] == workpaper["workpaper_id"]
            and row["workpaper_projection_version_id"]
            == workpaper["workpaper_projection_version_id"]
            and row["workpaper_content_digest"] == workpaper["content_digest"]
        ]
        if len(reviews) > 1:
            raise DeliverableServiceError("writer_admission_cardinality_violation", 409)
        if not reviews:
            raise DeliverableServiceError("fixture_writer_admission_required", 409)
        lead_review = reviews[0]
        if lead_review["decision"] != self._contract["consumes"]["required_lead_review_decision"]:
            raise DeliverableServiceError("fixture_writer_admission_required", 409)
        admission = lead_review.get("writer_admission")
        if not isinstance(admission, Mapping):
            raise DeliverableServiceError("fixture_writer_admission_required", 409)
        if admission.get("writer_admission_id") != draft.writer_admission_id:
            raise DeliverableServiceError("writer_admission_identity_mismatch", 409)
        if admission.get("scope") != self._contract["consumes"]["required_writer_admission_scope"]:
            raise DeliverableServiceError("writer_admission_scope_not_admitted", 409)
        if admission.get("fixture_only") is not True or admission.get("writer_execution_authorized") is not False:
            raise DeliverableServiceError("writer_admission_execution_boundary_violated", 409)
        return workpaper, lead_review, dict(admission)

    def _compose_presentation(
        self,
        *,
        case_id: str,
        workpaper: Mapping[str, Any],
        lead_review: Mapping[str, Any],
        admission: Mapping[str, Any],
    ) -> dict[str, Any]:
        judgments_by_role = {str(row["evidence_role"]): row for row in workpaper["judgments"]}
        profile = self._deliverable_profile_for(tuple(judgments_by_role))
        expected_roles = list(profile["active_cell_roles"])
        if list(sorted(judgments_by_role)) != list(sorted(expected_roles)) or len(judgments_by_role) != len(
            expected_roles
        ):
            raise DeliverableServiceError("p36_judgment_cardinality_violation", 409)
        claims = tuple(
            self._material_claim(judgments_by_role[role]) for role in expected_roles
        )
        sections = self._sections(
            claims,
            judgments_by_role,
            expected_roles,
            str(profile["executive_line"]),
        )
        writer_brief = {
            "mode": self._contract["composer_contract"]["mode"],
            "workpaper_projection_version_id": workpaper["workpaper_projection_version_id"],
            "workpaper_content_digest": workpaper["content_digest"],
            "lead_review_id": lead_review["lead_review_id"],
            "writer_admission_id": admission["writer_admission_id"],
            "sections": sections,
            "material_claims": claims,
        }
        writer_brief_digest = canonical_digest(writer_brief)
        canonical_presentation_id = "presentation_" + canonical_digest(
            {"writer_brief_digest": writer_brief_digest, "case_id": case_id}
        )[:24]
        title = str(profile["title"])
        canonical_presentation_digest = canonical_digest(
            {
                "canonical_presentation_id": canonical_presentation_id,
                "writer_brief_digest": writer_brief_digest,
                "title": title,
                "sections": sections,
                "material_claims": claims,
            }
        )
        deliverable_id = "deliverable_" + canonical_digest(
            {
                "case_id": case_id,
                "workpaper_projection_version_id": workpaper["workpaper_projection_version_id"],
                "workpaper_content_digest": workpaper["content_digest"],
                "writer_admission_id": admission["writer_admission_id"],
                "canonical_presentation_digest": canonical_presentation_digest,
            }
        )[:24]
        artifact_version_id = f"{deliverable_id}:v1"
        renderings = {
            "html": self._render_html(
                title,
                artifact_version_id,
                canonical_presentation_digest,
                sections,
                claims,
            ),
            "markdown": self._render_markdown(
                title,
                artifact_version_id,
                canonical_presentation_digest,
                sections,
                claims,
            ),
        }
        return {
            "deliverable_id": deliverable_id,
            "artifact_version_id": artifact_version_id,
            "writer_brief_digest": writer_brief_digest,
            "canonical_presentation_id": canonical_presentation_id,
            "canonical_presentation_digest": canonical_presentation_digest,
            "title": title,
            "sections": sections,
            "material_claims": claims,
            "renderings": renderings,
            "profile_digest": (
                canonical_digest(self._p36_profile)
                if len(expected_roles) > 3
                else self._contract_digest
            ),
        }

    def _presentation_model(
        self,
        *,
        case_id: str,
        actor_ref: str,
        principal: CasePrincipal,
        trace_id: str,
        workpaper: Mapping[str, Any],
        lead_review: Mapping[str, Any],
        admission: Mapping[str, Any],
        presentation: Mapping[str, Any],
    ) -> CanonicalPresentationModelVersion:
        return CanonicalPresentationModelVersion(
            tenant_id=principal.tenant_id,
            project_id=principal.project_id,
            case_id=case_id,
            actor_snapshot_ref=f"fixture_actor:{actor_ref}",
            permission_snapshot_ref=self._evidence._permission_ref(principal),
            policy_config_refs=(
                "vt3.deliverable.preview.fixture.internal",
                f"contract:{presentation['profile_digest']}",
            ),
            correlation_id=trace_id,
            current_status="fixture_preview_compiled",
            deliverable_id=str(presentation["deliverable_id"]),
            artifact_version_id=str(presentation["artifact_version_id"]),
            artifact_version=1,
            workpaper_id=str(workpaper["workpaper_id"]),
            workpaper_projection_version_id=str(workpaper["workpaper_projection_version_id"]),
            workpaper_version=int(workpaper["workpaper_version"]),
            workpaper_content_digest=str(workpaper["content_digest"]),
            lead_review_id=str(lead_review["lead_review_id"]),
            writer_admission_id=str(admission["writer_admission_id"]),
            writer_brief_digest=str(presentation["writer_brief_digest"]),
            canonical_presentation_id=str(presentation["canonical_presentation_id"]),
            canonical_presentation_digest=str(presentation["canonical_presentation_digest"]),
            title=str(presentation["title"]),
            sections=tuple(presentation["sections"]),
            material_claims=tuple(presentation["material_claims"]),
            renderings=dict(presentation["renderings"]),
            hard_boundaries=self._boundaries(),
        )

    def _trace_manifest(
        self,
        *,
        case_id: str,
        actor_ref: str,
        principal: CasePrincipal,
        trace_id: str,
        artifact: CanonicalPresentationModelVersion,
    ) -> ArtifactProvenanceManifestVersion:
        claim_to_source: dict[str, tuple[str, ...]] = {}
        source_to_claim: dict[str, list[str]] = {}
        nodes: dict[str, dict[str, Any]] = {}
        edges: list[dict[str, str]] = []
        for claim in artifact.material_claims:
            claim_id = str(claim["claim_id"])
            nodes[claim_id] = {
                "node_id": claim_id,
                "node_type": "material_claim",
                "cell_id": claim["cell_id"],
                "claim_kind": claim["claim_kind"],
                "display_label": claim["claim_text"],
                "reference": claim_id,
            }
            source_groups = (
                ("evidence_candidate", claim["evidence_refs"]),
                ("numeric_fact", claim["numeric_refs"]),
                ("repair_outcome", claim["repair_outcome_refs"]),
                ("explicit_gap", claim["gap_refs"]),
            )
            sources = tuple(sorted({str(ref) for _, refs in source_groups for ref in refs}))
            if not sources:
                raise DeliverableServiceError("claim_lineage_required", 409, claim_id=claim_id)
            claim_to_source[claim_id] = sources
            for node_type, refs in source_groups:
                for source_id in sorted({str(ref) for ref in refs}):
                    nodes.setdefault(
                        source_id,
                        {
                            "node_id": source_id,
                            "node_type": node_type,
                            "display_label": source_id,
                            "reference": source_id,
                        },
                    )
                    source_to_claim.setdefault(source_id, []).append(claim_id)
                    edges.extend(
                        (
                            {
                                "from_node_id": claim_id,
                                "to_node_id": source_id,
                                "direction": "claim_to_source",
                            },
                            {
                                "from_node_id": source_id,
                                "to_node_id": claim_id,
                                "direction": "source_to_claim",
                            },
                        )
                    )
        manifest_id = "trace_manifest_" + canonical_digest(
            {
                "artifact_version_id": artifact.artifact_version_id,
                "artifact_content_digest": artifact.content_digest,
                "canonical_presentation_digest": artifact.canonical_presentation_digest,
            }
        )[:24]
        return ArtifactProvenanceManifestVersion(
            tenant_id=principal.tenant_id,
            project_id=principal.project_id,
            case_id=case_id,
            actor_snapshot_ref=f"fixture_actor:{actor_ref}",
            permission_snapshot_ref=self._evidence._permission_ref(principal),
            policy_config_refs=(
                "vt3.deliverable.trace.fixture.internal",
                str(artifact.policy_config_refs[-1]),
            ),
            correlation_id=trace_id,
            current_status="fixture_trace_compiled",
            manifest_id=manifest_id,
            manifest_version_id=f"{manifest_id}:v1",
            manifest_version=1,
            artifact_version_id=artifact.artifact_version_id,
            artifact_version=artifact.artifact_version,
            artifact_content_digest=artifact.content_digest,
            canonical_presentation_digest=artifact.canonical_presentation_digest,
            nodes=tuple(nodes[key] for key in sorted(nodes)),
            edges=tuple(
                sorted(
                    edges,
                    key=lambda row: (
                        row["direction"],
                        row["from_node_id"],
                        row["to_node_id"],
                    ),
                )
            ),
            claim_to_source=dict(sorted(claim_to_source.items())),
            source_to_claim={
                key: tuple(sorted(value)) for key, value in sorted(source_to_claim.items())
            },
            redaction_summary={
                "raw_chain_of_thought": "not_persisted",
                "prompt": "not_persisted",
                "secret": "not_persisted",
                "unredacted_tool_observation": "not_persisted",
                "forbidden_input_count": len(self._contract["composer_contract"]["forbidden_inputs"]),
            },
        )

    def _material_claim(self, judgment: Mapping[str, Any]) -> dict[str, Any]:
        gap_refs = [
            f"gap:{judgment['cell_id']}:{gap}"
            for gap in sorted({str(value) for value in judgment["remaining_gaps"]})
        ]
        payload = {
            "cell_id": str(judgment["cell_id"]),
            "claim_text": str(judgment["judgment"]),
            "claim_kind": f"fixture_{judgment['evidence_role']}_judgment",
            "evidence_refs": sorted({str(value) for value in judgment["evidence_refs"]}),
            "numeric_refs": sorted({str(value) for value in judgment["numeric_refs"]}),
            "repair_outcome_refs": sorted(
                {str(value) for value in judgment["repair_outcome_refs"]}
            ),
            "gap_refs": gap_refs,
        }
        if not any(
            payload[key]
            for key in ("evidence_refs", "numeric_refs", "repair_outcome_refs", "gap_refs")
        ):
            raise DeliverableServiceError(
                "claim_lineage_required", 409, cell_id=payload["cell_id"]
            )
        return {
            "claim_id": "material_claim_" + canonical_digest(payload)[:24],
            **payload,
        }

    def _sections(
        self,
        claims: tuple[dict[str, Any], ...],
        judgments_by_role: Mapping[str, Mapping[str, Any]],
        ordered_roles: list[str],
        executive_line: str,
    ) -> tuple[dict[str, Any], ...]:
        claim_by_role = dict(zip(ordered_roles, claims, strict=True))
        changes = [
            f"{judgments_by_role[role]['cell_id']}: {judgments_by_role[role]['what_would_change']}"
            for role in ordered_roles
        ]
        gaps = [
            gap_ref
            for claim in claims
            for gap_ref in claim["gap_refs"]
        ]
        return (
            {
                "section_id": "executive_answer",
                "heading": "Executive answer",
                "lines": [executive_line],
                "claim_ids": [claim["claim_id"] for claim in claims],
            },
            *(
                {
                    "section_id": role,
                    "heading": role.replace("_", " ").title(),
                    "lines": [],
                    "claim_ids": [claim_by_role[role]["claim_id"]],
                }
                for role in ordered_roles
            ),
            {
                "section_id": "what_would_change",
                "heading": "What would change",
                "lines": changes,
                "claim_ids": [],
            },
            {
                "section_id": "remaining_gaps",
                "heading": "Remaining gaps",
                "lines": gaps,
                "claim_ids": [],
            },
        )

    def _deliverable_profile_for(self, roles: tuple[str, ...]) -> Mapping[str, Any]:
        profile = self._p36_profile.get("deliverable_profile", {})
        profile_roles = tuple(profile.get("active_cell_roles", ()))
        if profile_roles and set(roles) == set(profile_roles):
            return profile
        base_roles = tuple(self._contract["consumes"]["active_cell_roles"])
        if set(roles) != set(base_roles):
            raise DeliverableServiceError("deliverable_profile_not_admitted", 409)
        return {
            "active_cell_roles": base_roles,
            "title": "Fixture-only three-cell deliverable preview",
            "executive_line": "Fixture-only synthesis of the admitted three-cell Workpaper.",
        }

    @staticmethod
    def _render_html(
        title: str,
        artifact_version_id: str,
        presentation_digest: str,
        sections: tuple[dict[str, Any], ...],
        claims: tuple[dict[str, Any], ...],
    ) -> dict[str, str]:
        claims_by_id = {claim["claim_id"]: claim for claim in claims}
        rendered_sections = []
        for section in sections:
            entries = [html.escape(str(line)) for line in section["lines"]]
            entries.extend(
                html.escape(str(claims_by_id[claim_id]["claim_text"]))
                for claim_id in section["claim_ids"]
            )
            body = "".join(f"<p>{entry}</p>" for entry in entries)
            rendered_sections.append(
                f'<section id="{html.escape(str(section["section_id"]))}">'
                f"<h2>{html.escape(str(section['heading']))}</h2>{body}</section>"
            )
        content = (
            "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            f"<title>{html.escape(title)}</title></head><body "
            f'data-artifact-version-id="{html.escape(artifact_version_id)}" '
            f'data-canonical-presentation-digest="{presentation_digest}">'
            f"<article><h1>{html.escape(title)}</h1>{''.join(rendered_sections)}</article>"
            "</body></html>"
        )
        return {
            "content": content,
            "content_digest": canonical_digest(content),
            "canonical_presentation_digest": presentation_digest,
        }

    @staticmethod
    def _render_markdown(
        title: str,
        artifact_version_id: str,
        presentation_digest: str,
        sections: tuple[dict[str, Any], ...],
        claims: tuple[dict[str, Any], ...],
    ) -> dict[str, str]:
        claims_by_id = {claim["claim_id"]: claim for claim in claims}
        lines = [
            f"# {title}",
            "",
            f"Artifact version: `{artifact_version_id}`",
            f"Canonical presentation digest: `{presentation_digest}`",
        ]
        for section in sections:
            lines.extend(("", f"## {section['heading']}"))
            lines.extend(str(line) for line in section["lines"])
            lines.extend(
                str(claims_by_id[claim_id]["claim_text"])
                for claim_id in section["claim_ids"]
            )
        content = "\n".join(lines) + "\n"
        return {
            "content": content,
            "content_digest": canonical_digest(content),
            "canonical_presentation_digest": presentation_digest,
        }

    def _deliverable_view(
        self, artifact: Mapping[str, Any], principal: CasePrincipal
    ) -> dict[str, Any]:
        actions = self._review_actions_for_artifact(
            self._store(), str(artifact["case_id"]), artifact, principal
        )
        terminal = next((row for row in reversed(actions) if row["terminal"]), None)
        return {
            "case_id": artifact["case_id"],
            "deliverable_id": artifact["deliverable_id"],
            "artifact_version_id": artifact["artifact_version_id"],
            "artifact_version": artifact["artifact_version"],
            "content_digest": artifact["content_digest"],
            "canonical_presentation_digest": artifact["canonical_presentation_digest"],
            "status": terminal["action_type"] if terminal else artifact["current_status"],
            "title": artifact["title"],
            "sections": list(artifact["sections"]),
            "material_claims": list(artifact["material_claims"]),
            "renderings": dict(artifact["renderings"]),
            "review_actions": [self._review_action_view(row) for row in actions],
            "hard_boundaries": dict(artifact["hard_boundaries"]),
        }

    @staticmethod
    def _review_action_view(row: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "review_action_id": row["review_action_id"],
            "review_action_version_id": row["review_action_version_id"],
            "action_type": row["action_type"],
            "reason": row["reason"],
            "terminal": row["terminal"],
            "actor_ref": row["actor_snapshot_ref"],
            "reviewed_at": row["recorded_at"],
            "artifact_version_id": row["artifact_version_id"],
            "artifact_version": row["artifact_version"],
            "content_digest": row["artifact_content_digest"],
            "canonical_presentation_digest": row["canonical_presentation_digest"],
        }

    def _artifact_row_by_identity(
        self,
        catalog: Any,
        deliverable_id: str,
        artifact_version: int,
        principal: CasePrincipal,
    ) -> Mapping[str, Any]:
        rows = [
            row
            for row in catalog.list_versions(DELIVERABLE_TABLE)
            if row.get("tenant_id") == principal.tenant_id
            and row.get("project_id") == principal.project_id
            and row.get("deliverable_id") == deliverable_id
            and int(row.get("artifact_version") or 0) == artifact_version
        ]
        if len(rows) > 1:
            raise DeliverableServiceError("artifact_version_cardinality_violation", 409)
        if not rows:
            raise DeliverableServiceError("artifact_version_not_found", 404)
        return rows[0]

    def _require_exact_artifact(
        self, artifact: Mapping[str, Any], draft: ReviewDeliverableDraft
    ) -> None:
        if int(artifact["artifact_version"]) != draft.expected_artifact_version:
            raise DeliverableServiceError("version_conflict", 409)
        if artifact["content_digest"] != draft.expected_content_digest:
            raise DeliverableServiceError("artifact_content_digest_mismatch", 409)
        if (
            artifact["canonical_presentation_digest"]
            != draft.expected_canonical_presentation_digest
        ):
            raise DeliverableServiceError("canonical_presentation_digest_mismatch", 409)

    def _review_actions_for_artifact(
        self,
        catalog: Any,
        case_id: str,
        artifact: Mapping[str, Any],
        principal: CasePrincipal,
    ) -> list[Mapping[str, Any]]:
        rows = [
            row
            for row in self._rows(catalog, REVIEW_TABLE, case_id, principal)
            if row["artifact_version_id"] == artifact["artifact_version_id"]
            and int(row["artifact_version"]) == int(artifact["artifact_version"])
            and row["artifact_content_digest"] == artifact["content_digest"]
            and row["canonical_presentation_digest"]
            == artifact["canonical_presentation_digest"]
        ]
        return sorted(rows, key=lambda row: (str(row["recorded_at"]), str(row["review_action_id"])))

    def _single_row(
        self, table: str, case_id: str, principal: CasePrincipal, missing_code: str
    ) -> Mapping[str, Any]:
        return self._single_row_from(self._store(), table, case_id, principal, missing_code)

    def _single_row_from(
        self,
        catalog: Any,
        table: str,
        case_id: str,
        principal: CasePrincipal,
        missing_code: str,
    ) -> Mapping[str, Any]:
        rows = self._rows(catalog, table, case_id, principal)
        if len(rows) > 1:
            raise DeliverableServiceError(f"{missing_code}_cardinality_violation", 409)
        if not rows:
            raise DeliverableServiceError(missing_code, 404, case_id=case_id)
        return rows[0]

    def _rows(
        self, catalog: Any, table: str, case_id: str, principal: CasePrincipal
    ) -> list[Mapping[str, Any]]:
        return [
            row
            for row in catalog.list_versions(table, case_id=case_id)
            if self._matches(row, case_id, principal)
        ]

    @staticmethod
    def _matches(row: Mapping[str, Any], case_id: str, principal: CasePrincipal) -> bool:
        return (
            row.get("tenant_id") == principal.tenant_id
            and row.get("project_id") == principal.project_id
            and row.get("case_id") == case_id
        )

    def _require_command(
        self,
        case_id: str,
        actor_ref: str,
        idempotency_key: str,
        principal: CasePrincipal,
        permission: str,
        trace_id: str,
    ) -> None:
        self._require_permission(principal, permission)
        if actor_ref != principal.actor_id:
            raise DeliverableServiceError("actor_scope_mismatch", 403)
        if not case_id.strip() or not idempotency_key.strip() or not trace_id.strip():
            raise DeliverableServiceError("request_validation_error", 422)

    @staticmethod
    def _require_permission(principal: CasePrincipal, permission: str) -> None:
        if (
            not principal.tenant_id
            or not principal.project_id
            or not principal.actor_id
            or permission not in principal.permissions
        ):
            raise DeliverableServiceError("permission_denied", 403, required_permission=permission)

    @staticmethod
    def _require_zero_vt2_boundaries(workpaper: Mapping[str, Any]) -> None:
        for key in (
            "network_calls",
            "tool_invocations",
            "model_calls",
            "provider_calls",
            "paid_full_chain",
            "writer_execution",
            "runtime_promotion",
            "release_evidence",
        ):
            if workpaper["hard_boundaries"].get(key) != 0:
                raise DeliverableServiceError("workpaper_boundary_violation", 409, boundary=key)

    def _boundaries(self) -> dict[str, int | str]:
        boundaries = dict(self._contract["hard_boundaries"])
        for key, value in self._contract["composer_contract"]["call_counts"].items():
            boundaries[f"{key}_calls"] = value
        return boundaries

    def _store(self) -> Any:
        if self._facade is None:
            raise DeliverableServiceError("operation_not_admitted", 403)
        return self._facade.store

    @staticmethod
    def _scope(case_id: str, key: str, principal: CasePrincipal) -> str:
        return f"vt3:{principal.tenant_id}:{principal.project_id}:{case_id}:{key}"

    @staticmethod
    def _check_idempotency(catalog: Any, scope_key: str, payload_digest: str) -> bool:
        existing = catalog.get_idempotency(scope_key)
        if not existing:
            return False
        if existing["payload_digest"] != payload_digest:
            raise IdempotencyConflict("vt3_idempotency_payload_conflict")
        return True

    @staticmethod
    def _with_digest(model: Any) -> Any:
        payload = model.model_dump(mode="json")
        payload["content_digest"] = ""
        return model.model_copy(update={"content_digest": canonical_digest(payload)})

    @staticmethod
    def _event(
        catalog: Any,
        *,
        event_type: str,
        actor_ref: str,
        trace_id: str,
        state_before: int,
        state_after: int,
        payload: dict[str, Any],
        causation_event_id: str | None = None,
    ) -> EventEnvelope:
        now = utc_now()
        return EventEnvelope(
            event_id="event_vt3_" + canonical_digest(
                {"event_type": event_type, "trace_id": trace_id, "payload": payload}
            )[:24],
            event_type=event_type,
            sequence_no=catalog.next_event_sequence(None),
            occurred_at=now,
            recorded_at=now,
            actor_snapshot_ref=f"fixture_actor:{actor_ref}",
            causation_event_id=causation_event_id,
            correlation_id=trace_id,
            state_version_before=state_before,
            state_version_after=state_after,
            payload_digest=canonical_digest(payload),
            payload=payload,
        )

    @staticmethod
    def _service_error(error: Exception) -> DeliverableServiceError:
        if isinstance(error, DeliverableServiceError):
            return error
        if isinstance(error, EvidenceServiceError):
            detail = {key: value for key, value in error.detail.items() if key != "reason"}
            return DeliverableServiceError(error.error_code, error.status_code, **detail)
        if isinstance(error, IdempotencyConflict):
            return DeliverableServiceError("idempotency_conflict", 409)
        if isinstance(error, TransactionConflict):
            return DeliverableServiceError("version_conflict", 409, conflict_reason=str(error))
        if isinstance(error, (KeyError, ValueError, TypeError)):
            return DeliverableServiceError("vt3_fixture_contract_invalid", 409, cause=str(error))
        return DeliverableServiceError("deliverable_backend_unavailable", 503, cause=str(error))
