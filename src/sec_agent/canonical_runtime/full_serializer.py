from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from pydantic import Field, field_validator

from .cell_composition import CellCompositionResult, ComposedDecisionCell
from .evidence_policy import EvidencePolicyCompilationResult
from .facade import RuntimeFacade
from .legacy_objective_adapter import LegacyMigrationPlan
from .models import (
    CommandEnvelope,
    CompileTimeGapVersion,
    DecisionSurfaceCellVersion,
    DecisionSurfaceContractVersion,
    EvidenceSlotVersion,
    ResultEnvelope,
    StrictModel,
    canonical_digest,
)
from .pack_registry import PackResolution
from .pack_selection import ExplainedPackSelectionDecision
from .planning_service import (
    CompilerInputContract,
    CompilerInputValidationPolicy,
    CompilerObservation,
    DecisionSurfacePlanningService,
)


class DecisionSurfaceSerializationError(ValueError):
    """Fail-closed M2.2 serializer error; it must never create a partial shadow artifact."""


class FullSerializerPolicy(StrictModel):
    policy_ref: str
    envelope_version: str = "finsight_point01_decision_surface_artifact_envelope_v1"
    artifact_type: str = "decision_surface_artifact_envelope"
    require_case_delta_lineage: bool = True
    require_selection_reasons: bool = True
    require_legacy_information_loss_review: bool = True


class FullSerializerScope(StrictModel):
    tenant_id: str
    project_id: str
    case_id: str
    actor_snapshot_ref: str
    permission_snapshot_ref: str
    policy_config_refs: tuple[str, ...] = ()
    correlation_id: str
    created_at: datetime
    recorded_at: datetime
    retention_class: str = "institutional_audit"
    data_classification: str = "internal"

    @field_validator("created_at", "recorded_at")
    @classmethod
    def require_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
            raise ValueError("timezone_aware_utc_required")
        return value

    def scoped_kwargs(self, *, current_status: str) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "project_id": self.project_id,
            "case_id": self.case_id,
            "actor_snapshot_ref": self.actor_snapshot_ref,
            "permission_snapshot_ref": self.permission_snapshot_ref,
            "policy_config_refs": self.policy_config_refs,
            "correlation_id": self.correlation_id,
            "created_at": self.created_at,
            "recorded_at": self.recorded_at,
            "retention_class": self.retention_class,
            "data_classification": self.data_classification,
            "current_status": current_status,
        }


class FullSerializationRequest(StrictModel):
    contract_id: str
    contract_version: int = Field(ge=1)
    compiler_input: CompilerInputContract
    pack_selection: ExplainedPackSelectionDecision
    composition: CellCompositionResult
    evidence_policy: EvidencePolicyCompilationResult
    legacy_migration: LegacyMigrationPlan
    scope: FullSerializerScope


class DecisionSurfaceArtifactEnvelope(StrictModel):
    envelope_version: str
    envelope_digest: str
    lineage_digest: str
    serializer_policy_ref: str
    bundle: dict[str, Any]
    pack_resolution_snapshot: PackResolution
    pack_selection_decision: ExplainedPackSelectionDecision
    composition: CellCompositionResult
    evidence_policy: EvidencePolicyCompilationResult
    legacy_migration_plan: LegacyMigrationPlan
    planning_authority: str = "shadow"
    model_call_count: int = 0
    external_call_count: int = 0


class FullSerializationAssembly(StrictModel):
    envelope: DecisionSurfaceArtifactEnvelope
    input_validation_status: str
    bundle_validation_status: str
    contract_version_id: str
    cell_count: int
    slot_count: int
    gap_count: int
    model_call_count: int = 0
    external_call_count: int = 0


class DecisionSurfaceReadbackReport(StrictModel):
    status: str
    artifact_version_id: str
    contract_version_id: str
    expected_envelope_digest: str
    observed_envelope_digest: str | None = None
    errors: tuple[str, ...] = ()
    replay_digest: str = ""
    planning_authority: str = "legacy"
    model_call_count: int = 0
    external_call_count: int = 0


def canonical_bundle(bundle: Mapping[str, Any]) -> dict[str, Any]:
    """Stable comparison shape for persisted canonical rows and the envelope payload."""
    return {
        "contract": dict(bundle["contract"]),
        "cells": sorted((dict(row) for row in bundle.get("cells", ())), key=lambda row: str(row["cell_id"])),
        "slots": sorted((dict(row) for row in bundle.get("slots", ())), key=lambda row: str(row["evidence_slot_id"])),
        "gaps": sorted((dict(row) for row in bundle.get("gaps", ())), key=lambda row: str(row["gap_id"])),
        "compiler_observations": sorted(
            (dict(row) for row in bundle.get("compiler_observations", ())),
            key=lambda row: (str(row.get("observation_type", "")), str(row.get("message", ""))),
        ),
    }


class DecisionSurfaceBundleAssembler:
    """M2.2 deterministic full assembler: all upstream lineage is retained in an envelope."""

    def __init__(self, *, compiler_policy: CompilerInputValidationPolicy, serializer_policy: FullSerializerPolicy):
        self.compiler_policy = compiler_policy
        self.serializer_policy = serializer_policy

    def assemble(self, request: FullSerializationRequest) -> FullSerializationAssembly:
        validator = DecisionSurfacePlanningService(None)  # type: ignore[arg-type]
        input_report = validator.validate_compiler_input_full(request.compiler_input, policy=self.compiler_policy)
        if input_report.status != "pass":
            raise DecisionSurfaceSerializationError(f"full_compiler_input_invalid:{','.join(input_report.errors)}")
        self._validate_lineage(request)
        bundle = self._assemble_bundle(request)
        bundle_report = validator.validate_decision_surface_bundle_full(
            request.scope.case_id,
            bundle,
            policy=self.compiler_policy,
        )
        if bundle_report["status"] != "pass":
            raise DecisionSurfaceSerializationError(f"full_bundle_invalid:{','.join(bundle_report['errors'])}")
        envelope = self._envelope(request, bundle)
        return FullSerializationAssembly(
            envelope=envelope,
            input_validation_status=input_report.status,
            bundle_validation_status=str(bundle_report["status"]),
            contract_version_id=str(bundle["contract"]["contract_version_id"]),
            cell_count=len(bundle["cells"]),
            slot_count=len(bundle["slots"]),
            gap_count=len(bundle["gaps"]),
        )

    def _validate_lineage(self, request: FullSerializationRequest) -> None:
        inputs = request.compiler_input
        scope = request.scope
        selection = request.pack_selection
        resolution = selection.resolution
        if inputs.case_id != scope.case_id or request.composition.case_id != scope.case_id:
            raise DecisionSurfaceSerializationError("serializer_case_scope_mismatch")
        if selection.status != "selected" or resolution is None:
            raise DecisionSurfaceSerializationError("pack_selection_not_selected")
        if self.serializer_policy.require_selection_reasons and not selection.reasons:
            raise DecisionSurfaceSerializationError("pack_selection_reason_missing")
        if selection.resolution.resolution_digest != resolution.resolution_digest:
            raise DecisionSurfaceSerializationError("pack_selection_resolution_digest_mismatch")
        input_refs = {
            "universal_pack_refs": inputs.pack_selection.universal_pack_refs,
            "sector_pack_refs": inputs.pack_selection.sector_pack_refs,
            "report_type_pack_refs": inputs.pack_selection.report_type_pack_refs,
            "case_delta_pack_refs": inputs.pack_selection.case_delta_pack_refs,
        }
        resolution_refs = {
            "universal_pack_refs": resolution.universal_pack_refs,
            "sector_pack_refs": resolution.sector_pack_refs,
            "report_type_pack_refs": resolution.report_type_pack_refs,
            "case_delta_pack_refs": resolution.case_delta_pack_refs,
        }
        if input_refs != resolution_refs:
            raise DecisionSurfaceSerializationError("pack_resolution_mismatch")
        if self.serializer_policy.require_case_delta_lineage and not resolution.case_delta_pack_refs:
            raise DecisionSurfaceSerializationError("case_delta_pack_lineage_missing")
        composition_cells = tuple(cell.seed.model_dump(mode="json") for cell in request.composition.cells)
        input_cells = tuple(cell.model_dump(mode="json") for cell in inputs.required_cells)
        if composition_cells != input_cells:
            raise DecisionSurfaceSerializationError("composition_cells_do_not_match_validated_input")
        if len(request.composition.cells) != len(inputs.required_cells):
            raise DecisionSurfaceSerializationError("composition_cell_count_mismatch")
        if request.evidence_policy.errors:
            raise DecisionSurfaceSerializationError("evidence_policy_compile_failed")
        self._validate_compiled_slots(request.composition.cells, request.evidence_policy)
        typed_gap_slots = {
            (row.cell_key, row.slot_key)
            for row in request.evidence_policy.compiled_slots
            if row.resolution_status == "typed_gap"
        }
        actual_gap_slots = {(row.cell_key, row.slot_key) for row in request.evidence_policy.gaps}
        if typed_gap_slots != actual_gap_slots:
            raise DecisionSurfaceSerializationError("typed_gap_lineage_dropped_or_unexpected")
        migration = request.legacy_migration
        if migration.planning_authority != "legacy" or migration.one_to_one_equivalence_count != 0:
            raise DecisionSurfaceSerializationError("legacy_direct_equivalence_forbidden")
        if set(migration.legacy_required_item_ids) != {row.legacy_required_item_id for row in migration.information_loss_review}:
            raise DecisionSurfaceSerializationError("legacy_information_loss_review_incomplete")
        if self.serializer_policy.require_legacy_information_loss_review and not migration.information_loss_review:
            raise DecisionSurfaceSerializationError("legacy_information_loss_review_missing")

    @staticmethod
    def _slot_bindings(cell: ComposedDecisionCell) -> tuple[tuple[str, Any], ...]:
        slot_keys = tuple(sorted({slot_key for keys in cell.fact_to_slot_keys.values() for slot_key in keys}))
        if not slot_keys or len(slot_keys) != len(cell.seed.evidence_slots):
            raise DecisionSurfaceSerializationError(f"fact_to_slot_lineage_invalid:{cell.cell_key}")
        return tuple(zip(slot_keys, cell.seed.evidence_slots, strict=True))

    def _validate_compiled_slots(
        self,
        cells: tuple[ComposedDecisionCell, ...],
        evidence_policy: EvidencePolicyCompilationResult,
    ) -> None:
        expected = {
            (cell.cell_key, slot_key): slot
            for cell in cells
            for slot_key, slot in self._slot_bindings(cell)
        }
        compiled = {(row.cell_key, row.slot_key): row for row in evidence_policy.compiled_slots}
        if set(compiled) != set(expected):
            raise DecisionSurfaceSerializationError("compiled_evidence_slot_coverage_mismatch")
        for key, slot in expected.items():
            policy = compiled[key]
            if (
                policy.evidence_role != slot.evidence_role
                or policy.source_policy_ref != slot.source_policy_ref
                or policy.acceptance_role != slot.acceptance_role
                or policy.forbidden_substitutions != slot.forbidden_substitutions
            ):
                raise DecisionSurfaceSerializationError(f"compiled_evidence_slot_contract_mismatch:{key[0]}:{key[1]}")

    def _assemble_bundle(self, request: FullSerializationRequest) -> dict[str, Any]:
        inputs = request.compiler_input
        scope = request.scope
        version = request.contract_version
        cell_ids = {
            seed.cell_key: f"cell_{canonical_digest((request.contract_id, seed.cell_key))[:20]}"
            for seed in inputs.required_cells
        }
        contract_version_id = f"{request.contract_id}:v{version}"
        contract = DecisionSurfaceContractVersion(
            **scope.scoped_kwargs(current_status="shadow_created"),
            contract_id=request.contract_id,
            contract_version_id=contract_version_id,
            contract_version=version,
            query=inputs.query,
            as_of=inputs.as_of,
            universe=inputs.universe,
            language=inputs.language,
            universal_pack_refs=inputs.pack_selection.universal_pack_refs,
            sector_pack_refs=inputs.pack_selection.sector_pack_refs,
            report_type_pack_refs=inputs.pack_selection.report_type_pack_refs,
            compiler_policy_ref=inputs.compiler_policy_ref,
            required_cell_ids=tuple(cell_ids[seed.cell_key] for seed in inputs.required_cells),
        )
        composed_by_key = {cell.cell_key: cell for cell in request.composition.cells}
        cells: list[DecisionSurfaceCellVersion] = []
        slots: list[EvidenceSlotVersion] = []
        slot_version_ids: dict[tuple[str, str], str] = {}
        for seed in inputs.required_cells:
            cell_id = cell_ids[seed.cell_key]
            cell_version_id = f"{cell_id}:v{version}"
            cells.append(
                DecisionSurfaceCellVersion(
                    **scope.scoped_kwargs(current_status="shadow_created"),
                    contract_version_id=contract_version_id,
                    cell_id=cell_id,
                    cell_version_id=cell_version_id,
                    cell_version=version,
                    decision_question=seed.decision_question,
                    origin_type=seed.origin_type,
                    owner_role=seed.owner_role,
                    materiality=seed.materiality,
                    dependency_cell_ids=tuple(cell_ids[key] for key in seed.dependency_cell_keys),
                    stop_rule=seed.stop_rule,
                )
            )
            for slot_key, slot_seed in self._slot_bindings(composed_by_key[seed.cell_key]):
                slot_id = f"slot_{canonical_digest((cell_id, slot_key))[:20]}"
                slot_version_id = f"{slot_id}:v{version}"
                slot_version_ids[(seed.cell_key, slot_key)] = slot_version_id
                slots.append(
                    EvidenceSlotVersion(
                        **scope.scoped_kwargs(current_status="shadow_created"),
                        cell_version_id=cell_version_id,
                        evidence_slot_id=slot_id,
                        slot_version_id=slot_version_id,
                        slot_version=version,
                        evidence_role=slot_seed.evidence_role,
                        entity_scope=slot_seed.entity_scope,
                        period_scope=slot_seed.period_scope,
                        metric_scope=slot_seed.metric_scope,
                        source_policy_ref=slot_seed.source_policy_ref,
                        forbidden_substitutions=slot_seed.forbidden_substitutions,
                        acceptance_role=slot_seed.acceptance_role,
                        required=slot_seed.required,
                    )
                )
        gaps = [
            CompileTimeGapVersion(
                **scope.scoped_kwargs(current_status="shadow_created"),
                cell_version_id=f"{cell_ids[gap.cell_key]}:v{version}",
                slot_version_id=slot_version_ids[(gap.cell_key, gap.slot_key)],
                gap_id=f"gap_{canonical_digest((request.contract_id, gap.cell_key, gap.slot_key, gap.gap_type, gap.reason))[:20]}",
                gap_version_id=f"gap_{canonical_digest((request.contract_id, gap.cell_key, gap.slot_key, gap.gap_type, gap.reason))[:20]}:v{version}",
                gap_version=version,
                gap_type=gap.gap_type,
                reason=gap.reason,
                materiality=gap.materiality,
                owner_suggestion=gap.owner_suggestion,
                next_action=gap.next_action,
            )
            for gap in request.evidence_policy.gaps
        ]
        observations = (
            CompilerObservation(
                observation_type="full_serializer",
                message="M2.2 deterministic envelope assembled without model, external evidence retrieval or authority change.",
                refs=(
                    request.pack_selection.decision_digest,
                    request.composition.composition_digest,
                    request.evidence_policy.compilation_digest,
                    request.legacy_migration.legacy_input_digest,
                ),
            ),
        )
        return canonical_bundle(
            {
                "contract": contract.model_dump(mode="json"),
                "cells": [row.model_dump(mode="json") for row in cells],
                "slots": [row.model_dump(mode="json") for row in slots],
                "gaps": [row.model_dump(mode="json") for row in gaps],
                "compiler_observations": [row.model_dump(mode="json") for row in observations],
            }
        )

    def _envelope(self, request: FullSerializationRequest, bundle: Mapping[str, Any]) -> DecisionSurfaceArtifactEnvelope:
        resolution = request.pack_selection.resolution
        assert resolution is not None
        payload = {
            "envelope_version": self.serializer_policy.envelope_version,
            "serializer_policy_ref": self.serializer_policy.policy_ref,
            "bundle": canonical_bundle(bundle),
            "pack_resolution_snapshot": resolution.model_dump(mode="json"),
            "pack_selection_decision": request.pack_selection.model_dump(mode="json"),
            "composition": request.composition.model_dump(mode="json"),
            "evidence_policy": request.evidence_policy.model_dump(mode="json"),
            "legacy_migration_plan": request.legacy_migration.model_dump(mode="json"),
            "planning_authority": "shadow",
            "model_call_count": 0,
            "external_call_count": 0,
        }
        lineage_digest = canonical_digest(
            {
                key: payload[key]
                for key in ("pack_resolution_snapshot", "pack_selection_decision", "composition", "evidence_policy", "legacy_migration_plan")
            }
        )
        return DecisionSurfaceArtifactEnvelope(
            **payload,
            lineage_digest=lineage_digest,
            envelope_digest=canonical_digest({**payload, "lineage_digest": lineage_digest}),
        )


class DecisionSurfaceArtifactSerializer:
    """Commits a validated envelope through the existing atomic shadow RuntimeFacade path."""

    def __init__(self, policy: FullSerializerPolicy):
        self.policy = policy

    def commit(
        self,
        facade: RuntimeFacade,
        command: CommandEnvelope,
        assembly: FullSerializationAssembly,
        *,
        artifact_id: str,
    ) -> ResultEnvelope:
        if assembly.envelope.serializer_policy_ref != self.policy.policy_ref:
            raise DecisionSurfaceSerializationError("serializer_policy_ref_mismatch")
        payload = {
            **command.payload,
            "artifact_id": artifact_id,
            "bundle": assembly.envelope.bundle,
            "artifact_envelope": assembly.envelope.model_dump(mode="json"),
            "artifact_type": self.policy.artifact_type,
        }
        return facade.commit_decision_surface_bundle(command.model_copy(update={"payload": payload}))


class DecisionSurfaceReadbackVerifier:
    """Checks object payload, canonical rows and replay after an atomic M2.2 commit."""

    def verify(
        self,
        facade: RuntimeFacade,
        assembly: FullSerializationAssembly,
        *,
        artifact_version_id: str,
    ) -> DecisionSurfaceReadbackReport:
        errors: list[str] = []
        observed_digest: str | None = None
        replay_digest = ""
        try:
            loaded = facade.get_artifact_version(artifact_version_id, include_payload=True)
            observed = DecisionSurfaceArtifactEnvelope.model_validate(loaded["payload"])
            observed_digest = observed.envelope_digest
            if observed.envelope_digest != assembly.envelope.envelope_digest:
                errors.append("envelope_digest_mismatch")
            expected_payload = assembly.envelope.model_dump(mode="json")
            without_digest = {key: value for key, value in expected_payload.items() if key != "envelope_digest"}
            if canonical_digest(without_digest) != assembly.envelope.envelope_digest:
                errors.append("expected_envelope_self_digest_invalid")
            observed_without_digest = {key: value for key, value in observed.model_dump(mode="json").items() if key != "envelope_digest"}
            if canonical_digest(observed_without_digest) != observed.envelope_digest:
                errors.append("observed_envelope_self_digest_invalid")
            if canonical_bundle(observed.bundle) != canonical_bundle(assembly.envelope.bundle):
                errors.append("artifact_bundle_readback_mismatch")
            if canonical_digest(observed.model_dump(mode="json")) != loaded["artifact"]["object_digest"]:
                errors.append("artifact_object_digest_mismatch")
            contract = assembly.envelope.bundle["contract"]
            readback = DecisionSurfacePlanningService(facade.store).get_decision_surface(
                str(contract["contract_id"]),
                contract_version=int(contract["contract_version"]),
            )
            # Compiler observations are envelope lineage, not a canonical object table.
            # Compare the persisted Contract/Cell/Slot/Gap rows with the expected observation
            # portion restored from the immutable artifact envelope.
            readback = {**readback, "compiler_observations": assembly.envelope.bundle["compiler_observations"]}
            canonical_readback = canonical_bundle(readback)
            if canonical_readback != canonical_bundle(assembly.envelope.bundle):
                errors.append("canonical_rows_readback_mismatch")
            replay = facade.replay_projection()
            replay_digest = str(replay["projection_digest"])
            if artifact_version_id not in set(replay["artifacts"]):
                errors.append("artifact_missing_from_replay")
        except Exception as exc:  # Converted to deterministic evidence for the M2.2 gate.
            errors.append(f"readback_exception:{type(exc).__name__}:{exc}")
        return DecisionSurfaceReadbackReport(
            status="pass" if not errors else "fail",
            artifact_version_id=artifact_version_id,
            contract_version_id=assembly.contract_version_id,
            expected_envelope_digest=assembly.envelope.envelope_digest,
            observed_envelope_digest=observed_digest,
            errors=tuple(sorted(set(errors))),
            replay_digest=replay_digest,
        )
