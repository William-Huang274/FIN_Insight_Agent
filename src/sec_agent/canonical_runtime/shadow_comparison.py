"""Deterministic M3 shadow-comparison contracts.

These objects compare a legacy planning objective with a DecisionSurface
shadow bundle.  They intentionally do not retrieve evidence, invoke a model,
write legacy state, or decide planning authority.
"""

from __future__ import annotations

from collections import Counter
from typing import Literal

from pydantic import Field

from .models import StrictModel, canonical_digest


class ShadowComparisonError(ValueError):
    """Raised when a comparison input is internally inconsistent."""


Materiality = Literal["low", "medium", "high", "critical"]
LegacyItemKind = Literal["decision", "fact_lookup", "generic_dimension"]
SemanticMappingKind = Literal["merge", "split", "downgrade"]
CellQuestionKind = Literal["decision", "fact_lookup", "generic_dimension"]


class LegacyRequiredItem(StrictModel):
    required_item_id: str
    semantic_intent: str
    materiality: Materiality
    item_kind: LegacyItemKind = "decision"


class ShadowCell(StrictModel):
    cell_key: str
    decision_question: str
    materiality: Materiality
    owner_role: str | None
    evidence_roles: tuple[str, ...]
    source_policy_refs: tuple[str, ...]
    semantic_key: str
    question_kind: CellQuestionKind = "decision"
    dependency_cell_keys: tuple[str, ...] = ()
    what_would_change: tuple[str, ...] = ()
    counterevidence_owner_role: str | None = None


class SemanticMappingRow(StrictModel):
    legacy_required_item_id: str
    mapping_kind: SemanticMappingKind
    target_cell_keys: tuple[str, ...] = ()
    information_loss_tags: tuple[str, ...]
    rationale: str
    downgrade_reason: str | None = None


class ComparatorPolicy(StrictModel):
    policy_ref: str
    materiality_weights: dict[Materiality, float] = {
        "low": 0.25,
        "medium": 0.5,
        "high": 1.0,
        "critical": 1.5,
    }
    minimum_weighted_coverage: float = Field(default=1.0, ge=0.0, le=1.0)
    material_omission_levels: tuple[Materiality, ...] = ("high", "critical")
    disallow_direct_equivalence: bool = True


class LegacyItemComparison(StrictModel):
    legacy_required_item_id: str
    status: Literal["covered", "properly_downgraded", "missing", "invalid_mapping"]
    mapping_kind: SemanticMappingKind | None = None
    target_cell_keys: tuple[str, ...] = ()
    weighted_coverage: float
    reason: str


class LegacyRequiredItemComparisonReport(StrictModel):
    case_id: str
    policy_ref: str
    status: Literal["pass", "fail"]
    rows: tuple[LegacyItemComparison, ...]
    extra_shadow_cell_keys: tuple[str, ...]
    material_omission_ids: tuple[str, ...]
    materiality_weighted_coverage: float
    mapping_digest: str
    planning_authority: str = "legacy"
    canonical_lane: str = "shadow_only"
    model_call_count: int = 0
    external_call_count: int = 0


class LegacyRequiredItemComparator:
    """Compare semantic mappings; count parity is deliberately not an outcome."""

    def __init__(self, policy: ComparatorPolicy):
        self.policy = policy

    def compare(
        self,
        *,
        case_id: str,
        legacy_items: tuple[LegacyRequiredItem, ...],
        shadow_cells: tuple[ShadowCell, ...],
        mappings: tuple[SemanticMappingRow, ...],
    ) -> LegacyRequiredItemComparisonReport:
        if not case_id.strip() or not legacy_items or not shadow_cells:
            raise ShadowComparisonError("comparison_required_input_missing")
        legacy_by_id = {item.required_item_id: item for item in legacy_items}
        cell_keys = {cell.cell_key for cell in shadow_cells}
        if len(legacy_by_id) != len(legacy_items) or len(cell_keys) != len(shadow_cells):
            raise ShadowComparisonError("comparison_ids_must_be_unique")
        mapping_by_id = {row.legacy_required_item_id: row for row in mappings}
        if len(mapping_by_id) != len(mappings) or set(mapping_by_id) - set(legacy_by_id):
            raise ShadowComparisonError("comparison_mapping_ids_invalid")

        rows: list[LegacyItemComparison] = []
        target_keys: set[str] = set()
        covered_weight = 0.0
        total_weight = 0.0
        material_omissions: list[str] = []
        for item in legacy_items:
            weight = self.policy.materiality_weights[item.materiality]
            total_weight += weight
            mapping = mapping_by_id.get(item.required_item_id)
            if mapping is None:
                rows.append(
                    LegacyItemComparison(
                        legacy_required_item_id=item.required_item_id,
                        status="missing",
                        weighted_coverage=0.0,
                        reason="legacy_item_has_no_semantic_mapping",
                    )
                )
                if item.item_kind == "decision" and item.materiality in self.policy.material_omission_levels:
                    material_omissions.append(item.required_item_id)
                continue
            status, reason = self._validate_mapping(item, mapping, cell_keys)
            target_keys.update(mapping.target_cell_keys)
            weight_credit = 1.0 if status in {"covered", "properly_downgraded"} else 0.0
            covered_weight += weight * weight_credit
            rows.append(
                LegacyItemComparison(
                    legacy_required_item_id=item.required_item_id,
                    status=status,
                    mapping_kind=mapping.mapping_kind,
                    target_cell_keys=mapping.target_cell_keys,
                    weighted_coverage=weight_credit,
                    reason=reason,
                )
            )
            if status in {"missing", "invalid_mapping"} and item.item_kind == "decision" and item.materiality in self.policy.material_omission_levels:
                material_omissions.append(item.required_item_id)
        coverage = covered_weight / total_weight if total_weight else 0.0
        status = "pass" if not material_omissions and coverage >= self.policy.minimum_weighted_coverage else "fail"
        digest = canonical_digest(
            {
                "case_id": case_id,
                "policy": self.policy.model_dump(mode="json"),
                "legacy_items": [item.model_dump(mode="json") for item in legacy_items],
                "shadow_cells": [cell.model_dump(mode="json") for cell in shadow_cells],
                "mappings": [row.model_dump(mode="json") for row in mappings],
            }
        )
        return LegacyRequiredItemComparisonReport(
            case_id=case_id,
            policy_ref=self.policy.policy_ref,
            status=status,
            rows=tuple(rows),
            extra_shadow_cell_keys=tuple(sorted(cell_keys - target_keys)),
            material_omission_ids=tuple(sorted(material_omissions)),
            materiality_weighted_coverage=coverage,
            mapping_digest=digest,
        )

    @staticmethod
    def _validate_mapping(
        item: LegacyRequiredItem,
        mapping: SemanticMappingRow,
        cell_keys: set[str],
    ) -> tuple[Literal["covered", "properly_downgraded", "invalid_mapping"], str]:
        if not mapping.information_loss_tags or not mapping.rationale.strip():
            return "invalid_mapping", "information_loss_or_rationale_missing"
        if set(mapping.target_cell_keys) - cell_keys:
            return "invalid_mapping", "mapping_target_cell_missing"
        if mapping.mapping_kind == "merge" and len(mapping.target_cell_keys) != 1:
            return "invalid_mapping", "merge_requires_exactly_one_target_cell"
        if mapping.mapping_kind == "split" and len(mapping.target_cell_keys) < 2:
            return "invalid_mapping", "split_requires_multiple_target_cells"
        if mapping.mapping_kind == "downgrade":
            if mapping.target_cell_keys or not (mapping.downgrade_reason or "").strip():
                return "invalid_mapping", "downgrade_requires_reason_without_target_cell"
            if item.item_kind != "fact_lookup":
                return "invalid_mapping", "only_fact_lookup_may_be_downgraded"
            return "properly_downgraded", "fact_lookup_downgraded_to_evidence_slot"
        if item.item_kind == "generic_dimension":
            return "invalid_mapping", "generic_dimension_cannot_be_promoted_to_decision_cell"
        return "covered", "semantic_mapping_covered"


class CellAuditPolicy(StrictModel):
    policy_ref: str
    minimum_weighted_coverage: float = Field(default=1.0, ge=0.0, le=1.0)
    maximum_ownerless_cells: int = Field(default=0, ge=0)
    maximum_lookup_cells: int = Field(default=0, ge=0)
    maximum_generic_dimension_cells: int = Field(default=0, ge=0)
    maximum_duplicate_cells: int = Field(default=0, ge=0)
    maximum_unanswerable_cells: int = Field(default=0, ge=0)
    require_what_would_change: bool = True
    require_counterevidence_owner: bool = True


class CellCoverageAuditReport(StrictModel):
    case_id: str
    policy_ref: str
    status: Literal["pass", "fail"]
    materiality_weighted_coverage: float
    ownerless_cell_keys: tuple[str, ...]
    lookup_cell_keys: tuple[str, ...]
    generic_dimension_cell_keys: tuple[str, ...]
    duplicate_cell_keys: tuple[str, ...]
    unanswerable_cell_keys: tuple[str, ...]
    missing_wwc_cell_keys: tuple[str, ...]
    missing_counterevidence_owner_cell_keys: tuple[str, ...]
    dependency_issue_cell_keys: tuple[str, ...]
    audit_digest: str
    planning_authority: str = "legacy"
    canonical_lane: str = "shadow_only"
    model_call_count: int = 0
    external_call_count: int = 0


class CellCoverageGranularityAuditor:
    """Audit cells as decisions, never as generic dimensions or fact lookups."""

    def __init__(self, policy: CellAuditPolicy):
        self.policy = policy

    def audit(
        self,
        *,
        case_id: str,
        cells: tuple[ShadowCell, ...],
        comparison: LegacyRequiredItemComparisonReport,
    ) -> CellCoverageAuditReport:
        if not case_id.strip() or not cells or comparison.case_id != case_id:
            raise ShadowComparisonError("cell_audit_required_input_missing_or_case_mismatch")
        cell_keys = {cell.cell_key for cell in cells}
        if len(cell_keys) != len(cells):
            raise ShadowComparisonError("cell_audit_duplicate_cell_keys")
        semantic_counts = Counter(cell.semantic_key for cell in cells)
        ownerless = tuple(sorted(cell.cell_key for cell in cells if not (cell.owner_role or "").strip()))
        lookup = tuple(sorted(cell.cell_key for cell in cells if cell.question_kind == "fact_lookup"))
        generic = tuple(sorted(cell.cell_key for cell in cells if cell.question_kind == "generic_dimension"))
        duplicates = tuple(sorted(cell.cell_key for cell in cells if semantic_counts[cell.semantic_key] > 1))
        unanswerable = tuple(
            sorted(cell.cell_key for cell in cells if not cell.evidence_roles or not cell.source_policy_refs)
        )
        missing_wwc = tuple(sorted(cell.cell_key for cell in cells if not cell.what_would_change))
        missing_counter = tuple(sorted(cell.cell_key for cell in cells if not (cell.counterevidence_owner_role or "").strip()))
        dependency_issues = tuple(
            sorted(cell.cell_key for cell in cells if set(cell.dependency_cell_keys) - cell_keys or cell.cell_key in cell.dependency_cell_keys)
        )
        passing = (
            comparison.materiality_weighted_coverage >= self.policy.minimum_weighted_coverage
            and len(ownerless) <= self.policy.maximum_ownerless_cells
            and len(lookup) <= self.policy.maximum_lookup_cells
            and len(generic) <= self.policy.maximum_generic_dimension_cells
            and len(duplicates) <= self.policy.maximum_duplicate_cells
            and len(unanswerable) <= self.policy.maximum_unanswerable_cells
            and (not self.policy.require_what_would_change or not missing_wwc)
            and (not self.policy.require_counterevidence_owner or not missing_counter)
            and not dependency_issues
        )
        digest = canonical_digest(
            {
                "case_id": case_id,
                "policy": self.policy.model_dump(mode="json"),
                "comparison_digest": comparison.mapping_digest,
                "cells": [cell.model_dump(mode="json") for cell in cells],
            }
        )
        return CellCoverageAuditReport(
            case_id=case_id,
            policy_ref=self.policy.policy_ref,
            status="pass" if passing else "fail",
            materiality_weighted_coverage=comparison.materiality_weighted_coverage,
            ownerless_cell_keys=ownerless,
            lookup_cell_keys=lookup,
            generic_dimension_cell_keys=generic,
            duplicate_cell_keys=duplicates,
            unanswerable_cell_keys=unanswerable,
            missing_wwc_cell_keys=missing_wwc,
            missing_counterevidence_owner_cell_keys=missing_counter,
            dependency_issue_cell_keys=dependency_issues,
            audit_digest=digest,
        )
