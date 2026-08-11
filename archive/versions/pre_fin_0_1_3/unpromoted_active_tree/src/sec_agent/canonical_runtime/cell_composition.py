from __future__ import annotations

from typing import Any

from pydantic import Field

from .models import StrictModel, canonical_digest
from .planning_service import DecisionCellSeed, EvidenceSlotSeed


class CellCompositionError(ValueError):
    pass


class CellCompositionPolicy(StrictModel):
    policy_ref: str
    minimum_material_cells: int = Field(default=10, ge=1)
    maximum_material_cells: int = Field(default=20, ge=1)
    allowed_owner_roles: tuple[str, ...]


class CellSlotTemplate(StrictModel):
    slot_key: str
    evidence_role: str
    entity_scope: tuple[str, ...]
    period_scope: str
    metric_scope: tuple[str, ...] = ()
    source_policy_ref: str
    forbidden_substitutions: tuple[str, ...]
    acceptance_role: str
    fact_keys: tuple[str, ...]
    required: bool = True

    def to_seed(self) -> EvidenceSlotSeed:
        return EvidenceSlotSeed(
            evidence_role=self.evidence_role,
            entity_scope=self.entity_scope,
            period_scope=self.period_scope,
            metric_scope=self.metric_scope,
            source_policy_ref=self.source_policy_ref,
            forbidden_substitutions=self.forbidden_substitutions,
            acceptance_role=self.acceptance_role,
            required=self.required,
        )


class CellArchetype(StrictModel):
    archetype_id: str
    source_pack_ref: str
    merge_key: str
    decision_question: str
    owner_role: str
    materiality: str
    stop_rule: str
    slots: tuple[CellSlotTemplate, ...]
    what_would_change: tuple[str, ...]
    counterevidence_owner_role: str
    dependency_merge_keys: tuple[str, ...] = ()
    split_labels: tuple[str, ...] = ()


class ComposedDecisionCell(StrictModel):
    cell_key: str
    seed: DecisionCellSeed
    origin_pack_refs: tuple[str, ...]
    what_would_change: tuple[str, ...]
    counterevidence_owner_role: str
    fact_to_slot_keys: dict[str, tuple[str, ...]]


class CellCompositionResult(StrictModel):
    case_id: str
    cells: tuple[ComposedDecisionCell, ...]
    merged_archetype_ids: tuple[str, ...]
    split_cell_keys: tuple[str, ...]
    composition_digest: str
    planning_authority: str = "shadow"
    model_call_count: int = 0
    external_call_count: int = 0


class CellCompositionEngine:
    """Deterministic M2.5 composition; it consumes pack templates but never a model or legacy write path."""

    def __init__(self, policy: CellCompositionPolicy):
        self.policy = policy

    def compose(
        self,
        *,
        case_id: str,
        selected_pack_refs: tuple[str, ...],
        archetypes: tuple[CellArchetype, ...],
    ) -> CellCompositionResult:
        if not case_id.strip() or not selected_pack_refs or not archetypes:
            raise CellCompositionError("composition_required_input_missing")
        selected = set(selected_pack_refs)
        groups: dict[str, list[CellArchetype]] = {}
        for archetype in archetypes:
            if archetype.source_pack_ref not in selected:
                raise CellCompositionError(f"archetype_pack_not_selected:{archetype.archetype_id}")
            self._validate_archetype(archetype)
            groups.setdefault(archetype.merge_key, []).append(archetype)

        group_output_keys: dict[str, tuple[str, ...]] = {}
        group_payloads: list[dict[str, Any]] = []
        for merge_key in sorted(groups):
            group = sorted(groups[merge_key], key=lambda row: row.archetype_id)
            self._validate_merge_group(merge_key, group)
            split_labels = tuple(sorted({label for row in group for label in row.split_labels})) or ("base",)
            output_keys = tuple(merge_key if label == "base" else f"{merge_key}__{label}" for label in split_labels)
            group_output_keys[merge_key] = output_keys
            group_payloads.append({"merge_key": merge_key, "group": group, "labels": split_labels, "output_keys": output_keys})

        cells: list[ComposedDecisionCell] = []
        merged_ids: list[str] = []
        split_keys: list[str] = []
        for payload in group_payloads:
            group = payload["group"]
            merge_key = payload["merge_key"]
            labels = payload["labels"]
            canonical = group[0]
            if len(group) > 1:
                merged_ids.extend(row.archetype_id for row in group)
            dependencies = self._resolve_dependencies(merge_key, group, group_output_keys)
            slots, fact_to_slot_keys = self._merge_slots(group)
            pack_refs = tuple(sorted({row.source_pack_ref for row in group}))
            for label, cell_key in zip(labels, payload["output_keys"], strict=True):
                question = canonical.decision_question if label == "base" else f"{canonical.decision_question} [{label}]"
                seed = DecisionCellSeed(
                    cell_key=cell_key,
                    decision_question=question,
                    origin_type="pack_composition",
                    owner_role=canonical.owner_role,
                    materiality=canonical.materiality,
                    stop_rule=canonical.stop_rule,
                    what_would_change="; ".join(canonical.what_would_change),
                    dependency_cell_keys=dependencies,
                    evidence_slots=slots,
                )
                cells.append(
                    ComposedDecisionCell(
                        cell_key=cell_key,
                        seed=seed,
                        origin_pack_refs=pack_refs,
                        what_would_change=canonical.what_would_change,
                        counterevidence_owner_role=canonical.counterevidence_owner_role,
                        fact_to_slot_keys=fact_to_slot_keys,
                    )
                )
                if label != "base":
                    split_keys.append(cell_key)
        if not self.policy.minimum_material_cells <= len(cells) <= self.policy.maximum_material_cells:
            raise CellCompositionError(f"material_cell_count_out_of_range:{len(cells)}")
        digest = canonical_digest(
            {
                "case_id": case_id,
                "selected_pack_refs": selected_pack_refs,
                "cells": [cell.model_dump(mode="json") for cell in cells],
            }
        )
        return CellCompositionResult(
            case_id=case_id,
            cells=tuple(cells),
            merged_archetype_ids=tuple(sorted(set(merged_ids))),
            split_cell_keys=tuple(sorted(split_keys)),
            composition_digest=digest,
        )

    def _validate_archetype(self, archetype: CellArchetype) -> None:
        if archetype.owner_role not in self.policy.allowed_owner_roles:
            raise CellCompositionError(f"owner_role_not_allowed:{archetype.archetype_id}")
        if not archetype.what_would_change:
            raise CellCompositionError(f"what_would_change_missing:{archetype.archetype_id}")
        if archetype.counterevidence_owner_role not in self.policy.allowed_owner_roles:
            raise CellCompositionError(f"counterevidence_owner_not_allowed:{archetype.archetype_id}")
        if not archetype.slots or any(not slot.fact_keys for slot in archetype.slots):
            raise CellCompositionError(f"fact_to_slot_mapping_missing:{archetype.archetype_id}")

    @staticmethod
    def _validate_merge_group(merge_key: str, group: list[CellArchetype]) -> None:
        baseline = group[0]
        attributes = ("decision_question", "owner_role", "materiality", "stop_rule", "what_would_change", "counterevidence_owner_role")
        for row in group[1:]:
            if any(getattr(row, attribute) != getattr(baseline, attribute) for attribute in attributes):
                raise CellCompositionError(f"merge_contract_conflict:{merge_key}")

    @staticmethod
    def _resolve_dependencies(
        merge_key: str,
        group: list[CellArchetype],
        output_keys: dict[str, tuple[str, ...]],
    ) -> tuple[str, ...]:
        dependency_merge_keys = sorted({key for row in group for key in row.dependency_merge_keys})
        dependencies: list[str] = []
        for dependency_key in dependency_merge_keys:
            targets = output_keys.get(dependency_key)
            if not targets:
                raise CellCompositionError(f"dependency_merge_key_missing:{merge_key}:{dependency_key}")
            if len(targets) != 1:
                raise CellCompositionError(f"dependency_merge_key_ambiguous:{merge_key}:{dependency_key}")
            dependencies.append(targets[0])
        return tuple(dependencies)

    @staticmethod
    def _merge_slots(group: list[CellArchetype]) -> tuple[tuple[EvidenceSlotSeed, ...], dict[str, tuple[str, ...]]]:
        slot_specs: dict[str, CellSlotTemplate] = {}
        fact_map: dict[str, set[str]] = {}
        for row in group:
            for slot in row.slots:
                previous = slot_specs.get(slot.slot_key)
                if previous and previous.model_dump(mode="json", exclude={"fact_keys"}) != slot.model_dump(mode="json", exclude={"fact_keys"}):
                    raise CellCompositionError(f"slot_contract_conflict:{row.merge_key}:{slot.slot_key}")
                slot_specs[slot.slot_key] = slot
                for fact_key in slot.fact_keys:
                    fact_map.setdefault(fact_key, set()).add(slot.slot_key)
        slots = tuple(slot_specs[key].to_seed() for key in sorted(slot_specs))
        fact_to_slot_keys = {key: tuple(sorted(value)) for key, value in sorted(fact_map.items())}
        return slots, fact_to_slot_keys
