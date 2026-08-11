from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Literal, Mapping

from pydantic import Field

from .facade import IllegalStateTransition, MissingDependency, RuntimeFacade
from .models import CommandEnvelope, ResultEnvelope, ScopedVersion, StrictModel, canonical_digest


MAX_CONTEXT_SNAPSHOT_BYTES = 32_768


class ContextRequirement(StrictModel):
    context_block_id: str
    dependency_refs: tuple[str, ...]
    context_key: str | None = None


class DependencyImpactAssessment(StrictModel):
    dependency_ref: str
    semantic_impact: Literal["material", "immaterial", "ambiguous"]
    rationale: str
    assessment_source: Literal["deterministic_policy", "manual_review"] = "deterministic_policy"


class ParallelSnapshot(ScopedVersion):
    snapshot_id: str
    snapshot_version: int = Field(ge=1)
    state_version: int = Field(ge=1)
    branch_id: str
    work_unit_id: str
    attempt_id: str
    checkpoint_ref: str
    dependency_refs: tuple[str, ...]
    dependency_digest: str
    context_requirements: tuple[ContextRequirement, ...]
    context_snapshot: dict[str, Any]
    context_digest: str
    branch_state: Literal["active", "rebase_required", "review_required", "cancelled"]
    parent_snapshot_ref: str | None = None
    recompiled_from_decision_id: str | None = None


class ParallelImpactDecision(ScopedVersion):
    decision_id: str
    decision_version: int = Field(ge=1)
    state_version: int = Field(ge=1)
    snapshot_ref: str
    branch_id: str
    delta_id: str
    changed_dependency_refs: tuple[str, ...]
    affected_dependency_refs: tuple[str, ...]
    action: Literal["continue", "rebase", "cancel", "review"]
    semantic_impact: Literal["none", "immaterial", "material", "ambiguous"]
    affected_context_block_ids: tuple[str, ...]
    classification_source: Literal["deterministic_policy", "manual_resolution"]
    context_recompile_requested: bool
    causation_snapshot_digest: str
    review_approval_id: str | None = None
    review_receipt_ref: str | None = None
    review_scope_digest: str | None = None


class ParallelContextError(RuntimeError):
    pass


class ParallelContextService:
    """M5.7 immutable branch snapshots and dependency-aware invalidation.

    Branches are persistent control-plane records rather than mutable agent
    contexts.  A relevant delta can only yield an explicit rebase request or a
    cancelled branch; a no-impact delta cannot silently change branch context.
    """

    def __init__(self, facade: RuntimeFacade):
        self.facade = facade

    def create_snapshot(self, command: CommandEnvelope) -> ResultEnvelope:
        self.facade._authorize("point01_shadow_compiler")
        case_id = self.facade._require_case(command)
        snapshot_id = str(command.payload.get("snapshot_id") or "")
        branch_id = str(command.payload.get("branch_id") or "")
        work_unit_id = str(command.payload.get("work_unit_id") or "")
        attempt_id = str(command.payload.get("attempt_id") or "")
        checkpoint_ref = str(command.payload.get("checkpoint_ref") or "")
        dependencies = tuple(sorted({str(value) for value in command.payload.get("dependency_refs") or ()}))
        context_snapshot = self._copy_context(command.payload.get("context_snapshot"))
        if not all((snapshot_id, branch_id, work_unit_id, attempt_id, checkpoint_ref)) or not dependencies:
            raise ParallelContextError("parallel_snapshot_required_fields_missing")
        scope_key, payload_digest, _ = self.facade._idempotency(command, snapshot_id)
        with self.facade.store.transaction() as tx:
            existing = tx.get_idempotency(scope_key)
            if existing:
                return self.facade._reuse_or_conflict(existing, payload_digest)
            if tx.get_latest("canonical_parallel_snapshot_versions", snapshot_id):
                raise ParallelContextError("parallel_snapshot_id_already_exists")
            _, attempt = self.facade._require_running_execution(tx, command, case_id, work_unit_id, attempt_id)
            self._require_checkpoint(tx, case_id=case_id, checkpoint_ref=checkpoint_ref, attempt_id=attempt_id)
            requirements = self._context_requirements(command.payload.get("context_requirements"), dependencies)
            snapshot = ParallelSnapshot(
                **self.facade._scope(command, case_id=case_id),
                snapshot_id=snapshot_id,
                snapshot_version=1,
                state_version=1,
                branch_id=branch_id,
                work_unit_id=work_unit_id,
                attempt_id=attempt_id,
                checkpoint_ref=checkpoint_ref,
                dependency_refs=dependencies,
                dependency_digest=canonical_digest(dependencies),
                context_requirements=requirements,
                context_snapshot=context_snapshot,
                context_digest=canonical_digest(context_snapshot),
                branch_state="active",
                parent_snapshot_ref=command.payload.get("parent_snapshot_ref"),
                current_status="active",
            )
            tx.insert("canonical_parallel_snapshot_versions", snapshot_id, 1, snapshot.model_dump(mode="json"))
            event = self.facade._event(
                tx,
                command.model_copy(update={"expected_state_version": 0}),
                "PARALLEL_SNAPSHOT_CREATED",
                {"snapshot_ref": f"{snapshot_id}:v1", "branch_id": branch_id, "checkpoint_ref": checkpoint_ref, "dependency_digest": snapshot.dependency_digest, "context_digest": snapshot.context_digest, "context_requirement_ids": [item.context_block_id for item in requirements], "parent_snapshot_ref": snapshot.parent_snapshot_ref},
                work_unit_id=work_unit_id,
                attempt_id=attempt_id,
            )
            tx.append_event(event)
            result = ResultEnvelope(command_id=command.command_id, status="succeeded", state_version_before=0, state_version_after=1, event_ids=(event.event_id,), artifact_refs=(checkpoint_ref,), projection_refs=(snapshot_id, branch_id))
            tx.put_idempotency(scope_key, payload_digest, result.model_dump(mode="json"))
        return result

    def apply_delta(self, command: CommandEnvelope) -> ResultEnvelope:
        self.facade._authorize("point01_shadow_compiler")
        case_id = self.facade._require_case(command)
        snapshot_id = str(command.payload.get("snapshot_id") or "")
        delta_id = str(command.payload.get("delta_id") or "")
        requested_action = str(command.payload.get("requested_action") or "")
        changed_refs = tuple(sorted({str(value) for value in command.payload.get("changed_dependency_refs") or ()}))
        if not snapshot_id or not delta_id or requested_action not in {"", "rebase", "cancel"} or not changed_refs:
            raise ParallelContextError("parallel_delta_required_fields_invalid")
        assessments = self._impact_assessments(command.payload.get("impact_assessments"), changed_refs)
        decision_id = f"impact:{snapshot_id}:{delta_id}"
        scope_key, payload_digest, _ = self.facade._idempotency(command, decision_id)
        with self.facade.store.transaction() as tx:
            existing = tx.get_idempotency(scope_key)
            if existing:
                return self.facade._reuse_or_conflict(existing, payload_digest)
            tx.assert_expected_state("canonical_parallel_snapshot_versions", snapshot_id, command.expected_state_version)
            snapshot = tx.get_latest("canonical_parallel_snapshot_versions", snapshot_id)
            if not snapshot or snapshot.get("case_id") != case_id:
                raise MissingDependency("parallel_snapshot_not_found")
            if snapshot.get("branch_state") != "active":
                raise IllegalStateTransition("parallel_delta_requires_active_branch")
            affected = tuple(sorted(set(changed_refs).intersection(str(value) for value in snapshot["dependency_refs"])))
            requirements = tuple(ContextRequirement.model_validate(item) for item in snapshot["context_requirements"])
            affected_blocks = tuple(sorted(item.context_block_id for item in requirements if set(item.dependency_refs).intersection(affected)))
            semantic_impact = self._semantic_impact(affected, assessments)
            if semantic_impact in {"none", "immaterial"}:
                action: Literal["continue", "rebase", "cancel", "review"] = "continue"
            elif semantic_impact == "ambiguous":
                action = "review"
            elif requested_action in {"rebase", "cancel"}:
                action = requested_action
            else:
                raise ParallelContextError("parallel_material_delta_resolution_required")
            decision = ParallelImpactDecision(
                **self.facade._scope(command, case_id=case_id),
                decision_id=decision_id,
                decision_version=1,
                state_version=1,
                snapshot_ref=f"{snapshot_id}:v{snapshot['snapshot_version']}",
                branch_id=str(snapshot["branch_id"]),
                delta_id=delta_id,
                changed_dependency_refs=changed_refs,
                affected_dependency_refs=affected,
                action=action,
                semantic_impact=semantic_impact,
                affected_context_block_ids=affected_blocks,
                classification_source="deterministic_policy",
                context_recompile_requested=action == "rebase",
                causation_snapshot_digest=str(snapshot["content_digest"] or canonical_digest(snapshot)),
                current_status=action,
            )
            tx.insert("canonical_parallel_impact_decisions", decision_id, 1, decision.model_dump(mode="json"))
            snapshot_ref = f"{snapshot_id}:v{snapshot['snapshot_version']}"
            event_type = "PARALLEL_DELTA_IGNORED"
            projection_refs: tuple[str, ...] = (decision_id, snapshot_id, str(snapshot["branch_id"]))
            state_after = command.expected_state_version
            if action != "continue":
                branch_state = "rebase_required" if action == "rebase" else "review_required" if action == "review" else "cancelled"
                updated = ParallelSnapshot.model_validate(
                    {
                        **snapshot,
                        "snapshot_version": int(snapshot["snapshot_version"]) + 1,
                        "state_version": int(snapshot["state_version"]) + 1,
                        "branch_state": branch_state,
                        "current_status": branch_state,
                        "supersedes_version_id": snapshot_ref,
                        "causation_event_id": command.causation_event_id,
                    }
                )
                tx.insert("canonical_parallel_snapshot_versions", snapshot_id, updated.snapshot_version, updated.model_dump(mode="json"))
                event_type = "PARALLEL_BRANCH_REBASE_REQUESTED" if action == "rebase" else "PARALLEL_BRANCH_REVIEW_REQUIRED" if action == "review" else "PARALLEL_BRANCH_CANCELLED"
                state_after = updated.state_version
                projection_refs = (decision_id, snapshot_id, f"{snapshot_id}:v{updated.snapshot_version}", str(snapshot["branch_id"]))
            event = self.facade._event(
                tx,
                command,
                event_type,
                {"decision_id": decision_id, "snapshot_ref": snapshot_ref, "branch_id": snapshot["branch_id"], "delta_id": delta_id, "changed_dependency_refs": list(changed_refs), "affected_dependency_refs": list(affected), "affected_context_block_ids": list(affected_blocks), "semantic_impact": semantic_impact, "action": action, "context_recompile_requested": action == "rebase"},
                work_unit_id=str(snapshot["work_unit_id"]),
                attempt_id=str(snapshot["attempt_id"]),
            )
            tx.append_event(event)
            result = ResultEnvelope(command_id=command.command_id, status="succeeded", state_version_before=command.expected_state_version, state_version_after=state_after, event_ids=(event.event_id,), projection_refs=projection_refs)
            tx.put_idempotency(scope_key, payload_digest, result.model_dump(mode="json"))
        return result

    def resolve_ambiguous_impact(self, command: CommandEnvelope) -> ResultEnvelope:
        """Record a human-reviewed resolution; no model or external reviewer is invoked here."""
        self.facade._authorize("point01_shadow_compiler")
        case_id = self.facade._require_case(command)
        snapshot_id = str(command.payload.get("snapshot_id") or "")
        decision_id = str(command.payload.get("decision_id") or "")
        action = str(command.payload.get("resolution_action") or "")
        approval_id = str(command.payload.get("approval_id") or "")
        review_receipt_ref = str(command.payload.get("review_receipt_ref") or "")
        if not snapshot_id or not decision_id or action not in {"rebase", "cancel"} or not approval_id or not review_receipt_ref:
            raise ParallelContextError("parallel_ambiguous_resolution_fields_invalid")
        resolution_id = f"{decision_id}:resolution"
        scope_key, payload_digest, _ = self.facade._idempotency(command, resolution_id)
        with self.facade.store.transaction() as tx:
            existing = tx.get_idempotency(scope_key)
            if existing:
                return self.facade._reuse_or_conflict(existing, payload_digest)
            tx.assert_expected_state("canonical_parallel_snapshot_versions", snapshot_id, command.expected_state_version)
            snapshot = tx.get_latest("canonical_parallel_snapshot_versions", snapshot_id)
            decision = tx.get_latest("canonical_parallel_impact_decisions", decision_id)
            if not snapshot or snapshot.get("case_id") != case_id or not decision or decision.get("case_id") != case_id:
                raise MissingDependency("parallel_ambiguous_resolution_dependency_missing")
            if snapshot.get("branch_state") != "review_required" or decision.get("action") != "review" or decision.get("semantic_impact") != "ambiguous":
                raise IllegalStateTransition("parallel_ambiguous_resolution_requires_review_required")
            review_scope_digest = self.review_scope_digest(
                command,
                snapshot=snapshot,
                decision=decision,
                resolution_action=action,
            )
            self._require_review_receipt(
                tx,
                case_id=case_id,
                approval_id=approval_id,
                receipt_ref=review_receipt_ref,
                scope_digest=review_scope_digest,
                at=command.requested_at,
            )
            resolved = ParallelImpactDecision(
                **self.facade._scope(command, case_id=case_id),
                decision_id=resolution_id,
                decision_version=1,
                state_version=1,
                snapshot_ref=f"{snapshot_id}:v{snapshot['snapshot_version']}",
                branch_id=str(snapshot["branch_id"]),
                delta_id=str(decision["delta_id"]),
                changed_dependency_refs=tuple(decision["changed_dependency_refs"]),
                affected_dependency_refs=tuple(decision["affected_dependency_refs"]),
                action=action,
                semantic_impact="ambiguous",
                affected_context_block_ids=tuple(decision["affected_context_block_ids"]),
                classification_source="manual_resolution",
                context_recompile_requested=action == "rebase",
                causation_snapshot_digest=str(snapshot["content_digest"] or canonical_digest(snapshot)),
                review_approval_id=approval_id,
                review_receipt_ref=review_receipt_ref,
                review_scope_digest=review_scope_digest,
                current_status=action,
            )
            tx.insert("canonical_parallel_impact_decisions", resolution_id, 1, resolved.model_dump(mode="json"))
            previous_ref = f"{snapshot_id}:v{snapshot['snapshot_version']}"
            updated = ParallelSnapshot.model_validate({**snapshot, "snapshot_version": int(snapshot["snapshot_version"]) + 1, "state_version": int(snapshot["state_version"]) + 1, "branch_state": "rebase_required" if action == "rebase" else "cancelled", "current_status": "rebase_required" if action == "rebase" else "cancelled", "supersedes_version_id": previous_ref, "causation_event_id": command.causation_event_id})
            tx.insert("canonical_parallel_snapshot_versions", snapshot_id, updated.snapshot_version, updated.model_dump(mode="json"))
            event = self.facade._event(tx, command, "PARALLEL_AMBIGUOUS_IMPACT_RESOLVED", {"resolution_id": resolution_id, "decision_id": decision_id, "approval_id": approval_id, "review_receipt_ref": review_receipt_ref, "review_scope_digest": review_scope_digest, "resolution_action": action, "snapshot_ref": previous_ref}, work_unit_id=str(snapshot["work_unit_id"]), attempt_id=str(snapshot["attempt_id"]))
            tx.append_event(event)
            result = ResultEnvelope(command_id=command.command_id, status="succeeded", state_version_before=command.expected_state_version, state_version_after=updated.state_version, event_ids=(event.event_id,), projection_refs=(resolution_id, snapshot_id, f"{snapshot_id}:v{updated.snapshot_version}"))
            tx.put_idempotency(scope_key, payload_digest, result.model_dump(mode="json"))
        return result

    def recompile_context(self, command: CommandEnvelope) -> ResultEnvelope:
        """Build a new immutable snapshot from approved replacement refs and blocks."""
        self.facade._authorize("point01_shadow_compiler")
        case_id = self.facade._require_case(command)
        snapshot_id = str(command.payload.get("snapshot_id") or "")
        decision_id = str(command.payload.get("decision_id") or "")
        block_updates = command.payload.get("context_block_updates")
        replacements = command.payload.get("dependency_ref_replacements")
        if not snapshot_id or not decision_id or not isinstance(block_updates, dict) or not isinstance(replacements, dict):
            raise ParallelContextError("parallel_context_recompile_fields_invalid")
        scope_key, payload_digest, _ = self.facade._idempotency(command, f"recompile:{snapshot_id}:{decision_id}")
        with self.facade.store.transaction() as tx:
            existing = tx.get_idempotency(scope_key)
            if existing:
                return self.facade._reuse_or_conflict(existing, payload_digest)
            tx.assert_expected_state("canonical_parallel_snapshot_versions", snapshot_id, command.expected_state_version)
            snapshot = tx.get_latest("canonical_parallel_snapshot_versions", snapshot_id)
            decision = tx.get_latest("canonical_parallel_impact_decisions", decision_id)
            if not snapshot or snapshot.get("case_id") != case_id or not decision or decision.get("case_id") != case_id:
                raise MissingDependency("parallel_context_recompile_dependency_missing")
            if snapshot.get("branch_state") != "rebase_required" or decision.get("action") != "rebase" or not decision.get("context_recompile_requested"):
                raise IllegalStateTransition("parallel_context_recompile_requires_rebase_request")
            requirements = tuple(ContextRequirement.model_validate(item) for item in snapshot["context_requirements"])
            affected_blocks = tuple(str(value) for value in decision["affected_context_block_ids"])
            if set(block_updates) != set(affected_blocks):
                raise ParallelContextError("parallel_context_recompile_affected_blocks_mismatch")
            required_refs = set(str(value) for value in decision["affected_dependency_refs"])
            if set(replacements) != required_refs or not all(isinstance(value, str) and value.strip() for value in replacements.values()):
                raise ParallelContextError("parallel_context_recompile_dependency_replacements_mismatch")
            context = self._copy_context(snapshot["context_snapshot"])
            requirement_by_id = {item.context_block_id: item for item in requirements}
            for block_id in affected_blocks:
                requirement = requirement_by_id.get(block_id)
                if not requirement or not requirement.context_key:
                    raise ParallelContextError("parallel_context_recompile_requirement_not_context_bound")
                context[requirement.context_key] = self._copy_context_value(block_updates[block_id])
            parent_ref = f"{snapshot_id}:v{snapshot['snapshot_version']}"
            dependency_refs = tuple(sorted(str(replacements.get(reference, reference)) for reference in snapshot["dependency_refs"]))
            updated = ParallelSnapshot.model_validate({**snapshot, "snapshot_version": int(snapshot["snapshot_version"]) + 1, "state_version": int(snapshot["state_version"]) + 1, "dependency_refs": dependency_refs, "dependency_digest": canonical_digest(dependency_refs), "context_snapshot": context, "context_digest": canonical_digest(context), "branch_state": "active", "current_status": "active", "parent_snapshot_ref": parent_ref, "recompiled_from_decision_id": decision_id, "supersedes_version_id": parent_ref, "causation_event_id": command.causation_event_id})
            tx.insert("canonical_parallel_snapshot_versions", snapshot_id, updated.snapshot_version, updated.model_dump(mode="json"))
            event = self.facade._event(tx, command, "PARALLEL_CONTEXT_RECOMPILED", {"decision_id": decision_id, "snapshot_ref": f"{snapshot_id}:v{updated.snapshot_version}", "parent_snapshot_ref": parent_ref, "affected_context_block_ids": list(affected_blocks), "dependency_ref_replacements": dict(replacements), "context_digest": updated.context_digest}, work_unit_id=str(snapshot["work_unit_id"]), attempt_id=str(snapshot["attempt_id"]))
            tx.append_event(event)
            result = ResultEnvelope(command_id=command.command_id, status="succeeded", state_version_before=command.expected_state_version, state_version_after=updated.state_version, event_ids=(event.event_id,), projection_refs=(snapshot_id, f"{snapshot_id}:v{updated.snapshot_version}", decision_id))
            tx.put_idempotency(scope_key, payload_digest, result.model_dump(mode="json"))
        return result

    def branch_view(self, *, case_id: str) -> dict[str, Any]:
        snapshots = self.facade.store.list_latest("canonical_parallel_snapshot_versions", case_id=case_id)
        decisions = self.facade.store.list_latest("canonical_parallel_impact_decisions", case_id=case_id)
        snapshots.sort(key=lambda item: (str(item["branch_id"]), str(item["snapshot_id"])))
        decisions.sort(key=lambda item: str(item["decision_id"]))
        return {"scope": "Point01_M5_7_parallel_snapshot_selective_invalidation_control_plane_only", "case_id": case_id, "snapshots": snapshots, "impact_decisions": decisions, "active_branch_count": sum(1 for item in snapshots if item["branch_state"] == "active"), "worker_started": False, "model_call_count": 0, "external_call_count": 0}

    @staticmethod
    def review_scope_digest(
        command: CommandEnvelope,
        *,
        snapshot: Mapping[str, Any],
        decision: Mapping[str, Any],
        resolution_action: str,
    ) -> str:
        """Bind a manual resolution to the exact persisted branch state and delta."""
        return canonical_digest(
            {
                "tenant_id": command.tenant_id,
                "project_id": command.project_id,
                "case_id": command.case_id,
                "permission_snapshot_ref": command.permission_snapshot_ref,
                "snapshot_ref": f"{snapshot['snapshot_id']}:v{snapshot['snapshot_version']}",
                "impact_decision_id": decision["decision_id"],
                "delta_id": decision["delta_id"],
                "resolution_action": resolution_action,
                "work_unit_id": snapshot["work_unit_id"],
                "attempt_id": snapshot["attempt_id"],
            }
        )

    @staticmethod
    def _require_review_receipt(
        tx: Any,
        *,
        case_id: str,
        approval_id: str,
        receipt_ref: str,
        scope_digest: str,
        at: datetime,
    ) -> None:
        persisted = tx.get_latest("canonical_hitl_registry_versions", approval_id)
        if not persisted:
            raise ParallelContextError("parallel_review_receipt_not_found")
        if persisted.get("case_id") != case_id:
            raise ParallelContextError("parallel_review_receipt_scope_mismatch")
        if persisted.get("approval_registry_ref") != receipt_ref or persisted.get("scope_digest") != scope_digest:
            raise ParallelContextError("parallel_review_receipt_ref_or_scope_mismatch")
        if persisted.get("approval_state") != "active":
            raise ParallelContextError("parallel_review_receipt_not_active")
        expires_at = datetime.fromisoformat(str(persisted["expires_at"]).replace("Z", "+00:00"))
        if expires_at <= at:
            raise ParallelContextError("parallel_review_receipt_expired")

    def _require_checkpoint(self, tx: Any, *, case_id: str, checkpoint_ref: str, attempt_id: str) -> Mapping[str, Any]:
        checkpoint_id, checkpoint_version = self.facade._parse_artifact_reference(checkpoint_ref, None)
        if not checkpoint_id or checkpoint_version is None:
            raise MissingDependency("checkpoint_exact_version_required")
        artifact = tx.get_version("canonical_artifact_versions", checkpoint_id, checkpoint_version)
        if not artifact or artifact.get("case_id") != case_id or artifact.get("artifact_version_id") != checkpoint_ref:
            raise MissingDependency("parallel_checkpoint_not_found_or_scope_mismatch")
        if artifact.get("artifact_type") != "runtime_checkpoint" or artifact.get("producer_attempt_id") != attempt_id:
            raise MissingDependency("parallel_checkpoint_producer_or_type_mismatch")
        self.facade._validate_checkpoint_artifact_payload(artifact)
        return artifact

    @staticmethod
    def _context_requirements(value: Any, dependencies: tuple[str, ...]) -> tuple[ContextRequirement, ...]:
        if value is None:
            return tuple(ContextRequirement(context_block_id=f"dependency:{canonical_digest(reference)[:16]}", dependency_refs=(reference,)) for reference in dependencies)
        if not isinstance(value, (list, tuple)):
            raise ParallelContextError("parallel_context_requirements_list_required")
        requirements = tuple(ContextRequirement.model_validate(item) for item in value)
        if not requirements or len({item.context_block_id for item in requirements}) != len(requirements):
            raise ParallelContextError("parallel_context_requirements_identity_invalid")
        covered = {reference for item in requirements for reference in item.dependency_refs}
        if covered != set(dependencies) or any(not item.dependency_refs for item in requirements):
            raise ParallelContextError("parallel_context_requirements_dependency_coverage_invalid")
        return requirements

    @staticmethod
    def _impact_assessments(value: Any, changed_refs: tuple[str, ...]) -> dict[str, DependencyImpactAssessment]:
        if not isinstance(value, (list, tuple)):
            raise ParallelContextError("parallel_delta_semantic_assessment_required")
        assessments = tuple(DependencyImpactAssessment.model_validate(item) for item in value)
        by_ref = {item.dependency_ref: item for item in assessments}
        if len(by_ref) != len(assessments) or set(by_ref) != set(changed_refs):
            raise ParallelContextError("parallel_delta_semantic_assessment_coverage_invalid")
        return by_ref

    @staticmethod
    def _semantic_impact(affected: tuple[str, ...], assessments: Mapping[str, DependencyImpactAssessment]) -> Literal["none", "immaterial", "material", "ambiguous"]:
        if not affected:
            return "none"
        values = {assessments[reference].semantic_impact for reference in affected}
        if "ambiguous" in values:
            return "ambiguous"
        return "material" if "material" in values else "immaterial"

    @staticmethod
    def _copy_context(value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ParallelContextError("parallel_context_snapshot_object_required")
        copied = json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str))
        size = len(json.dumps(copied, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        if size > MAX_CONTEXT_SNAPSHOT_BYTES:
            raise ParallelContextError("parallel_context_snapshot_size_exceeded")
        return copied

    @staticmethod
    def _copy_context_value(value: Any) -> Any:
        return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str))


PARALLEL_CONTEXT_MODELS = (ContextRequirement, DependencyImpactAssessment, ParallelSnapshot, ParallelImpactDecision)
