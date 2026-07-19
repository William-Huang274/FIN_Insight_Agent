"""Immutable, replayable M2-A1 actual-run projection.

The projection contains the complete compiler/serializer/shadow lineage needed
by the reviewer oracle.  It is deliberately separate from the reviewer-side
expected oracle and validates its own digest before any evaluator or gate can
accept it.
"""

from __future__ import annotations

from typing import Any

from pydantic import field_validator, model_validator

from .models import StrictModel, canonical_digest


def _sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


class M2A1ActualCellProjection(StrictModel):
    cell_key: str
    owner_role: str
    evidence_roles: tuple[str, ...]
    forbidden_substitutions: tuple[str, ...]
    acceptance_roles: tuple[str, ...]


class M2A1SemanticLossProjection(StrictModel):
    legacy_required_item_id: str
    action: str
    target_cell_keys: tuple[str, ...]
    information_loss_tags: tuple[str, ...]


class M2A1PackLineageProjection(StrictModel):
    selection_digest: str = ""
    resolution_digest: str = ""
    registry_snapshot_digest: str = ""
    selected_pack_version_ids: tuple[str, ...] = ()


class M2A1ArtifactReplayProjection(StrictModel):
    envelope_digest: str | None = None
    replay_digest: str | None = None
    artifact_version_id: str | None = None


class M2A1ImmutableActualResult(StrictModel):
    schema_version: str = "finsight_point01_m2_a1_immutable_actual_result_v2_0"
    execution_scope: str
    scenario_id: str
    case_id: str
    executable_package_digest: str
    admission_digest: str
    consumed_receipt_digest: str
    actual_status: str
    pack_lineage: M2A1PackLineageProjection
    cells: tuple[M2A1ActualCellProjection, ...] = ()
    semantic_loss: tuple[M2A1SemanticLossProjection, ...] = ()
    artifact_replay: M2A1ArtifactReplayProjection
    asserted_claims: tuple[str, ...] = ()
    typed_stop: str | None = None
    canary_snapshot: dict[str, Any]
    terminalized: bool = True
    payload_digest: str
    actual_result_digest: str

    @field_validator("executable_package_digest", "admission_digest", "consumed_receipt_digest", "payload_digest", "actual_result_digest")
    @classmethod
    def require_sha256(cls, value: str) -> str:
        if not _sha256(value):
            raise ValueError("sha256_required")
        return value

    @classmethod
    def terminalize(
        cls,
        *,
        execution_scope: str,
        scenario_id: str,
        case_id: str,
        executable_package_digest: str,
        admission_digest: str,
        consumed_receipt_digest: str,
        actual_status: str,
        pack_lineage: M2A1PackLineageProjection | None = None,
        cells: tuple[M2A1ActualCellProjection, ...] = (),
        semantic_loss: tuple[M2A1SemanticLossProjection, ...] = (),
        artifact_replay: M2A1ArtifactReplayProjection | None = None,
        asserted_claims: tuple[str, ...] = (),
        typed_stop: str | None = None,
        canary_snapshot: dict[str, Any] | None = None,
    ) -> "M2A1ImmutableActualResult":
        payload = {
            "schema_version": "finsight_point01_m2_a1_immutable_actual_result_v2_0",
            "execution_scope": execution_scope,
            "scenario_id": scenario_id,
            "case_id": case_id,
            "executable_package_digest": executable_package_digest,
            "admission_digest": admission_digest,
            "consumed_receipt_digest": consumed_receipt_digest,
            "actual_status": actual_status,
            "pack_lineage": (pack_lineage or M2A1PackLineageProjection()).model_dump(mode="json"),
            "cells": [cell.model_dump(mode="json") for cell in cells],
            "semantic_loss": [row.model_dump(mode="json") for row in semantic_loss],
            "artifact_replay": (artifact_replay or M2A1ArtifactReplayProjection()).model_dump(mode="json"),
            "asserted_claims": asserted_claims,
            "typed_stop": typed_stop,
            "canary_snapshot": canary_snapshot or {"counts": {}, "events": []},
            "terminalized": True,
        }
        payload_digest = canonical_digest(payload)
        return cls(**payload, payload_digest=payload_digest, actual_result_digest=canonical_digest({**payload, "payload_digest": payload_digest}))

    def verify_immutable_digest(self) -> bool:
        payload = self.model_dump(mode="json", exclude={"payload_digest", "actual_result_digest"})
        expected_payload = canonical_digest(payload)
        expected_actual = canonical_digest({**payload, "payload_digest": expected_payload})
        return self.terminalized and self.payload_digest == expected_payload and self.actual_result_digest == expected_actual

    @model_validator(mode="after")
    def enforce_self_digest(self) -> "M2A1ImmutableActualResult":
        if not self.verify_immutable_digest():
            raise ValueError("immutable_actual_result_digest_invalid")
        if self.actual_status == "typed_stop" and not self.typed_stop:
            raise ValueError("typed_stop_code_required")
        if self.actual_status == "succeeded" and self.typed_stop is not None:
            raise ValueError("successful_actual_cannot_have_typed_stop")
        return self


class M2A1ActualDigestReference(StrictModel):
    scenario_id: str
    case_id: str
    executable_package_digest: str
    actual_result_digest: str
    actual_status: str

    @classmethod
    def from_result(cls, result: M2A1ImmutableActualResult) -> "M2A1ActualDigestReference":
        if not result.verify_immutable_digest():
            raise ValueError("immutable_actual_result_digest_invalid")
        return cls(
            scenario_id=result.scenario_id,
            case_id=result.case_id,
            executable_package_digest=result.executable_package_digest,
            actual_result_digest=result.actual_result_digest,
            actual_status=result.actual_status,
        )
