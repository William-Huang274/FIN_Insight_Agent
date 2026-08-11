from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from pydantic import Field

from .models import (
    CompileTimeGapVersion,
    DecisionSurfaceCellVersion,
    DecisionSurfaceContractVersion,
    EvidenceSlotVersion,
    StrictModel,
    canonical_digest,
)
from .protocols import CanonicalStore


class CompilerInputError(ValueError):
    pass


class CompilerInputValidationPolicy(StrictModel):
    """M2.1 full-shape policy; fixture compilation deliberately does not imply this policy passed."""

    policy_ref: str
    minimum_material_cells: int = Field(default=10, ge=1)
    maximum_material_cells: int = Field(default=20, ge=1)
    allowed_owner_roles: tuple[str, ...]
    allowed_materialities: tuple[str, ...]
    allowed_source_policy_refs: tuple[str, ...]
    allowed_acceptance_roles: tuple[str, ...]
    require_forbidden_substitutions: bool = True


class CompilerInputValidationReport(StrictModel):
    status: str
    policy_ref: str
    cell_count: int
    errors: tuple[str, ...] = ()
    external_call_count: int = 0
    validation_mode: str = "full"


class PackSelectionDecision(StrictModel):
    universal_pack_refs: tuple[str, ...] = ()
    sector_pack_refs: tuple[str, ...] = ()
    report_type_pack_refs: tuple[str, ...] = ()
    case_delta_pack_refs: tuple[str, ...] = ()


class EvidenceSlotSeed(StrictModel):
    evidence_role: str
    entity_scope: tuple[str, ...]
    period_scope: str
    metric_scope: tuple[str, ...] = ()
    source_policy_ref: str
    forbidden_substitutions: tuple[str, ...] = ()
    acceptance_role: str
    required: bool = True


class DecisionCellSeed(StrictModel):
    cell_key: str
    decision_question: str
    origin_type: str
    owner_role: str
    materiality: str
    stop_rule: str
    what_would_change: str = ""
    dependency_cell_keys: tuple[str, ...] = ()
    evidence_slots: tuple[EvidenceSlotSeed, ...] = ()


class Fin01S3ProgramCellContract(StrictModel):
    """Release-cell alias and decision semantics consumed by the FIN 0.1 runtime."""

    program_cell_id: str
    legacy_cell_key: str
    evidence_role: str
    owner_role: str
    decision_question: str
    mandatory_judgment_chain: str
    stop_rule: str
    what_would_change: str


class CompilerInputContract(StrictModel):
    tenant_id: str
    project_id: str
    case_id: str
    query: str
    as_of: datetime
    universe: tuple[str, ...]
    language: str
    compiler_policy_ref: str
    pack_selection: PackSelectionDecision
    required_cells: tuple[DecisionCellSeed, ...]


class CompilerObservation(StrictModel):
    observation_type: str
    message: str
    refs: tuple[str, ...] = ()


P02_4_CONTRACT_DIGEST = "83319c49d2c91616503e83a2fce31ff2837792ecbbdb6015aaa08f4c85cfffb7"
P02_4_COMPILER_POLICY_REF = "fixture:p36-three-cell-v1"
P02_4_PACK_SELECTION_REF = "fixture:p36-ai-infrastructure-v1"
P02_4_FIXED_CELL_SEEDS = (
    DecisionCellSeed(
        cell_key="demand_reality",
        decision_question="Is AI infrastructure demand real, durable, and converting into recognized revenue?",
        origin_type="fixed_p36_fixture",
        owner_role="industry_analyst",
        materiality="high",
        stop_rule="Do not advance without issuer or filing evidence for demand and revenue conversion plus one counterindicator.",
        what_would_change="Two consecutive quarters of weaker order-to-revenue conversion, material customer digestion, or evidence that demand is primarily inventory pull-forward.",
        evidence_slots=(
            EvidenceSlotSeed(
                evidence_role="demand_signal",
                entity_scope=("NVDA", "MSFT", "AMZN", "GOOGL", "META"),
                period_scope="latest_two_quarters",
                source_policy_ref="fixture:issuer_filing_first",
                acceptance_role="industry_analyst",
            ),
            EvidenceSlotSeed(
                evidence_role="revenue_conversion",
                entity_scope=("NVDA", "SMCI", "TSM"),
                period_scope="latest_two_quarters",
                source_policy_ref="fixture:issuer_filing_first",
                acceptance_role="industry_analyst",
            ),
        ),
    ),
    DecisionCellSeed(
        cell_key="value_profit_capture",
        decision_question="Where are value and incremental profit captured across accelerators, servers, foundry and packaging, HBM, and semicap?",
        origin_type="fixed_p36_fixture",
        owner_role="financial_analyst",
        materiality="high",
        stop_rule="Do not assign value capture without segment revenue or margin evidence and an explicit cross-chain comparison.",
        what_would_change="Evidence that pricing power is competed away, mix shifts to lower-margin products, or upstream capacity captures the incremental economics.",
        evidence_slots=(
            EvidenceSlotSeed(
                evidence_role="revenue_capture",
                entity_scope=("NVDA", "SMCI", "TSM", "AVGO", "MU", "ASML", "AMAT"),
                period_scope="latest_two_quarters",
                source_policy_ref="fixture:issuer_filing_first",
                acceptance_role="financial_analyst",
            ),
            EvidenceSlotSeed(
                evidence_role="margin_capture",
                entity_scope=("NVDA", "SMCI", "TSM", "AVGO", "MU"),
                period_scope="latest_two_quarters",
                source_policy_ref="fixture:issuer_filing_first",
                acceptance_role="financial_analyst",
            ),
        ),
    ),
    DecisionCellSeed(
        cell_key="bottleneck_counterevidence",
        decision_question="Which bottlenecks, constraints, and counterevidence could break the current AI infrastructure thesis?",
        origin_type="fixed_p36_fixture",
        owner_role="risk_reviewer",
        materiality="high",
        stop_rule="Do not close the thesis without one capacity bottleneck and one independent counterevidence route.",
        what_would_change="A credible supply release, export restriction, capex digestion, customer concentration break, or price-in evidence that invalidates the expected risk-reward.",
        evidence_slots=(
            EvidenceSlotSeed(
                evidence_role="capacity_constraint",
                entity_scope=("TSM", "AVGO", "MU", "ASML", "AMAT"),
                period_scope="latest_two_quarters",
                source_policy_ref="fixture:issuer_filing_first",
                acceptance_role="risk_reviewer",
            ),
            EvidenceSlotSeed(
                evidence_role="thesis_counterevidence",
                entity_scope=("NVDA", "MSFT", "AMZN", "GOOGL", "META"),
                period_scope="latest_two_quarters",
                source_policy_ref="fixture:issuer_and_policy_first",
                acceptance_role="risk_reviewer",
            ),
        ),
    ),
)

FIN01_S3_PROGRAM_CELL_CONTRACTS = (
    Fin01S3ProgramCellContract(
        program_cell_id="demand_authenticity_and_sustainability",
        legacy_cell_key="demand_reality",
        evidence_role="demand_signal",
        owner_role="industry_analyst",
        decision_question=(
            "Is NVDA AI infrastructure demand authentic and durable, and what "
            "evidence distinguishes recognized demand from temporary pull-forward?"
        ),
        mandatory_judgment_chain=(
            "demand_signal_to_company_specificity_to_real_deployment_to_"
            "durability_driver_to_cannot_infer"
        ),
        stop_rule=P02_4_FIXED_CELL_SEEDS[0].stop_rule,
        what_would_change=P02_4_FIXED_CELL_SEEDS[0].what_would_change,
    ),
    Fin01S3ProgramCellContract(
        program_cell_id="value_and_profit_capture",
        legacy_cell_key="value_profit_capture",
        evidence_role="revenue_capture",
        owner_role="financial_analyst",
        decision_question=(
            "Where and how does NVDA capture revenue and incremental profit from AI "
            "infrastructure demand, using segment, period, unit and formula-bound evidence?"
        ),
        mandatory_judgment_chain=(
            "demand_transmission_to_product_segment_attribution_to_revenue_to_margin_"
            "operating_profit_cash_conversion_to_unattributed_scope"
        ),
        stop_rule=P02_4_FIXED_CELL_SEEDS[1].stop_rule,
        what_would_change=P02_4_FIXED_CELL_SEEDS[1].what_would_change,
    ),
    Fin01S3ProgramCellContract(
        program_cell_id="bottleneck_counterevidence_and_what_would_change",
        legacy_cell_key="bottleneck_counterevidence",
        evidence_role="thesis_counterevidence",
        owner_role="risk_reviewer",
        decision_question=(
            "Which bottlenecks and counterevidence could break or qualify the NVDA "
            "thesis, and what exact evidence would change the judgment?"
        ),
        mandatory_judgment_chain=(
            "strongest_counterevidence_to_impact_mechanism_to_observed_state_to_"
            "probability_impact_boundary_to_what_would_change"
        ),
        stop_rule=P02_4_FIXED_CELL_SEEDS[2].stop_rule,
        what_would_change=P02_4_FIXED_CELL_SEEDS[2].what_would_change,
    ),
)


def _is_blank(value: str) -> bool:
    return not value.strip()


def _has_dependency_cycle(dependencies: Mapping[str, tuple[str, ...]]) -> bool:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(cell_key: str) -> bool:
        if cell_key in visiting:
            return True
        if cell_key in visited:
            return False
        visiting.add(cell_key)
        for dependency in dependencies[cell_key]:
            if dependency in dependencies and visit(dependency):
                return True
        visiting.remove(cell_key)
        visited.add(cell_key)
        return False

    return any(visit(cell_key) for cell_key in dependencies)


class DecisionSurfacePlanningService:
    """M1B deterministic validation/read boundary; it neither calls a model nor commits a bundle."""

    def __init__(self, store: CanonicalStore):
        self.store = store

    def compile_deterministic_fixture(
        self,
        inputs: CompilerInputContract,
        *,
        audit_scope: Mapping[str, Any],
    ) -> dict[str, Any]:
        self._validate_input(inputs, audit_scope)
        seed_digest = canonical_digest(inputs)
        contract_id = f"contract_{seed_digest[:20]}"
        contract_version_id = f"{contract_id}:v1"
        cell_ids = {seed.cell_key: f"cell_{canonical_digest((contract_version_id, seed.cell_key))[:20]}" for seed in inputs.required_cells}
        scope = dict(audit_scope)
        contract = DecisionSurfaceContractVersion(
            **scope,
            contract_id=contract_id,
            contract_version_id=contract_version_id,
            contract_version=1,
            query=inputs.query,
            as_of=inputs.as_of,
            universe=inputs.universe,
            language=inputs.language,
            universal_pack_refs=inputs.pack_selection.universal_pack_refs,
            sector_pack_refs=inputs.pack_selection.sector_pack_refs,
            report_type_pack_refs=inputs.pack_selection.report_type_pack_refs,
            compiler_policy_ref=inputs.compiler_policy_ref,
            required_cell_ids=tuple(cell_ids.values()),
            current_status="shadow_created",
        )
        cells: list[DecisionSurfaceCellVersion] = []
        slots: list[EvidenceSlotVersion] = []
        for seed in inputs.required_cells:
            cell_id = cell_ids[seed.cell_key]
            cell_version_id = f"{cell_id}:v1"
            dependencies = tuple(cell_ids[key] for key in seed.dependency_cell_keys)
            cells.append(
                DecisionSurfaceCellVersion(
                    **scope,
                    contract_version_id=contract_version_id,
                    cell_id=cell_id,
                    cell_version_id=cell_version_id,
                    cell_version=1,
                    decision_question=seed.decision_question,
                    origin_type=seed.origin_type,
                    owner_role=seed.owner_role,
                    materiality=seed.materiality,
                    dependency_cell_ids=dependencies,
                    stop_rule=seed.stop_rule,
                    what_would_change=seed.what_would_change,
                    current_status="shadow_created",
                )
            )
            for index, slot_seed in enumerate(seed.evidence_slots, 1):
                slot_id = f"slot_{canonical_digest((cell_version_id, index, slot_seed))[:20]}"
                slots.append(
                    EvidenceSlotVersion(
                        **scope,
                        cell_version_id=cell_version_id,
                        evidence_slot_id=slot_id,
                        slot_version_id=f"{slot_id}:v1",
                        slot_version=1,
                        evidence_role=slot_seed.evidence_role,
                        entity_scope=slot_seed.entity_scope,
                        period_scope=slot_seed.period_scope,
                        metric_scope=slot_seed.metric_scope,
                        source_policy_ref=slot_seed.source_policy_ref,
                        forbidden_substitutions=slot_seed.forbidden_substitutions,
                        acceptance_role=slot_seed.acceptance_role,
                        required=slot_seed.required,
                        current_status="shadow_created",
                    )
                )
        return {
            "contract": contract.model_dump(mode="json"),
            "cells": [cell.model_dump(mode="json") for cell in cells],
            "slots": [slot.model_dump(mode="json") for slot in slots],
            "gaps": [],
            "compiler_observations": [
                CompilerObservation(
                    observation_type="deterministic_fixture",
                    message="No model, web, tool or external write was invoked.",
                    refs=(seed_digest,),
                ).model_dump(mode="json")
            ],
        }

    def validate_decision_surface_bundle(self, case_id: str, bundle: Mapping[str, Any]) -> dict[str, Any]:
        contract = DecisionSurfaceContractVersion.model_validate(bundle["contract"])
        cells = [DecisionSurfaceCellVersion.model_validate(row) for row in bundle.get("cells", ())]
        slots = [EvidenceSlotVersion.model_validate(row) for row in bundle.get("slots", ())]
        gaps = [CompileTimeGapVersion.model_validate(row) for row in bundle.get("gaps", ())]
        errors: list[str] = []
        if contract.case_id != case_id:
            errors.append("bundle_case_scope_mismatch")
        cell_ids = {row.cell_id for row in cells}
        cell_version_ids = {row.cell_version_id for row in cells}
        slot_version_ids = {row.slot_version_id for row in slots}
        if len(cell_ids) != len(cells):
            errors.append("duplicate_cell_id")
        if set(contract.required_cell_ids) != cell_ids:
            errors.append("required_cell_ids_mismatch")
        for cell in cells:
            if cell.case_id != case_id or cell.contract_version_id != contract.contract_version_id:
                errors.append("cell_parent_or_case_mismatch")
            if not set(cell.dependency_cell_ids).issubset(cell_ids):
                errors.append("cell_dependency_missing")
        for slot in slots:
            if slot.case_id != case_id or slot.cell_version_id not in cell_version_ids:
                errors.append("slot_parent_or_case_mismatch")
        for gap in gaps:
            if gap.case_id != case_id or gap.cell_version_id not in cell_version_ids:
                errors.append("gap_parent_or_case_mismatch")
            if gap.slot_version_id and gap.slot_version_id not in slot_version_ids:
                errors.append("gap_slot_missing")
        errors = sorted(set(errors))
        return {
            "status": "pass" if not errors else "fail",
            "errors": errors,
            "contract_version_id": contract.contract_version_id,
            "cell_count": len(cells),
            "slot_count": len(slots),
            "gap_count": len(gaps),
            "planning_authority": "shadow",
            "external_call_count": 0,
        }

    def validate_compiler_input_full(
        self,
        inputs: CompilerInputContract,
        *,
        policy: CompilerInputValidationPolicy,
    ) -> CompilerInputValidationReport:
        """Validate the M2.1 full compiler-input contract without compiling, model calls or writes."""
        errors: list[str] = []
        if policy.minimum_material_cells > policy.maximum_material_cells:
            errors.append("policy_material_cell_range_invalid")
        if inputs.compiler_policy_ref != policy.policy_ref:
            errors.append("compiler_policy_ref_mismatch")
        if _is_blank(inputs.query):
            errors.append("query_blank")
        if not inputs.universe:
            errors.append("universe_empty")
        if inputs.as_of.tzinfo is None or inputs.as_of.utcoffset() != timezone.utc.utcoffset(inputs.as_of):
            errors.append("as_of_must_be_timezone_aware_utc")
        errors.extend(self._validate_full_cells_and_slots(inputs.required_cells, policy=policy))
        return CompilerInputValidationReport(
            status="pass" if not errors else "fail",
            policy_ref=policy.policy_ref,
            cell_count=len(inputs.required_cells),
            errors=tuple(sorted(set(errors))),
        )

    def validate_decision_surface_bundle_full(
        self,
        case_id: str,
        bundle: Mapping[str, Any],
        *,
        policy: CompilerInputValidationPolicy,
    ) -> dict[str, Any]:
        """M2.1 full validator for assembled Cell/Slot/Gap rows; basic fixture validation stays available."""
        basic = self.validate_decision_surface_bundle(case_id, bundle)
        errors = list(basic["errors"])
        try:
            contract = DecisionSurfaceContractVersion.model_validate(bundle["contract"])
            cells = [DecisionSurfaceCellVersion.model_validate(row) for row in bundle.get("cells", ())]
            slots = [EvidenceSlotVersion.model_validate(row) for row in bundle.get("slots", ())]
            gaps = [CompileTimeGapVersion.model_validate(row) for row in bundle.get("gaps", ())]
        except Exception:
            errors.append("bundle_schema_invalid")
            return {
                **basic,
                "status": "fail",
                "errors": sorted(set(errors)),
                "policy_ref": policy.policy_ref,
                "validation_mode": "full",
            }
        if contract.compiler_policy_ref != policy.policy_ref:
            errors.append("bundle_compiler_policy_ref_mismatch")
        if policy.minimum_material_cells > policy.maximum_material_cells:
            errors.append("policy_material_cell_range_invalid")
        if not policy.minimum_material_cells <= len(cells) <= policy.maximum_material_cells:
            errors.append(f"material_cell_count_out_of_range:{len(cells)}")
        cell_ids = {cell.cell_id for cell in cells}
        dependencies = {cell.cell_id: cell.dependency_cell_ids for cell in cells}
        if _has_dependency_cycle(dependencies):
            errors.append("bundle_dependency_cycle")
        slots_by_cell: dict[str, list[EvidenceSlotVersion]] = {}
        for slot in slots:
            slots_by_cell.setdefault(slot.cell_version_id, []).append(slot)
            errors.extend(self._validate_full_slot(slot, slot_label=slot.evidence_slot_id, policy=policy))
        for cell in cells:
            errors.extend(self._validate_full_cell_fields(cell, cell_label=cell.cell_id, policy=policy))
            if not set(cell.dependency_cell_ids).issubset(cell_ids):
                errors.append(f"bundle_dependency_missing:{cell.cell_id}")
            cell_slots = slots_by_cell.get(cell.cell_version_id, [])
            if not cell_slots:
                errors.append(f"cell_missing_evidence_slot:{cell.cell_id}")
            elif not any(slot.required for slot in cell_slots):
                errors.append(f"cell_missing_required_evidence_slot:{cell.cell_id}")
        for gap in gaps:
            if _is_blank(gap.gap_type):
                errors.append(f"gap_type_blank:{gap.gap_id}")
            if _is_blank(gap.reason):
                errors.append(f"gap_reason_blank:{gap.gap_id}")
            if gap.materiality not in policy.allowed_materialities:
                errors.append(f"gap_materiality_not_allowed:{gap.gap_id}")
            if gap.owner_suggestion not in policy.allowed_owner_roles:
                errors.append(f"gap_owner_not_allowed:{gap.gap_id}")
            if _is_blank(gap.next_action):
                errors.append(f"gap_next_action_blank:{gap.gap_id}")
        return {
            **basic,
            "status": "pass" if not errors else "fail",
            "errors": sorted(set(errors)),
            "policy_ref": policy.policy_ref,
            "validation_mode": "full",
            "external_call_count": 0,
        }

    def get_decision_surface(self, contract_id: str, *, contract_version: int | None = None) -> dict[str, Any]:
        contract = (
            self.store.get_version("canonical_decision_surface_contract_versions", contract_id, contract_version)
            if contract_version is not None
            else self.store.get_latest("canonical_decision_surface_contract_versions", contract_id)
        )
        if not contract:
            raise CompilerInputError("decision_surface_not_found")
        contract_version_id = str(contract["contract_version_id"])
        case_id = str(contract["case_id"])
        cells = [
            row
            for row in self.store.list_versions(
                "canonical_decision_surface_cell_versions",
                case_id=case_id,
                version=int(contract["contract_version"]),
            )
            if row["contract_version_id"] == contract_version_id
        ]
        cell_version_ids = {row["cell_version_id"] for row in cells}
        slots = [
            row
            for row in self.store.list_versions(
                "canonical_evidence_slot_versions",
                case_id=case_id,
                version=int(contract["contract_version"]),
            )
            if row["cell_version_id"] in cell_version_ids
        ]
        slot_version_ids = {row["slot_version_id"] for row in slots}
        gaps = [
            row
            for row in self.store.list_versions(
                "canonical_compile_gap_versions",
                case_id=case_id,
                version=int(contract["contract_version"]),
            )
            if row["cell_version_id"] in cell_version_ids and (not row.get("slot_version_id") or row["slot_version_id"] in slot_version_ids)
        ]
        return {
            "contract": contract,
            "cells": sorted(cells, key=lambda row: row["cell_id"]),
            "slots": sorted(slots, key=lambda row: row["evidence_slot_id"]),
            "gaps": sorted(gaps, key=lambda row: row["gap_id"]),
            "planning_authority": "shadow",
        }

    @staticmethod
    def _validate_input(inputs: CompilerInputContract, audit_scope: Mapping[str, Any]) -> None:
        if not inputs.required_cells:
            raise CompilerInputError("required_cells_empty")
        if audit_scope.get("case_id") != inputs.case_id:
            raise CompilerInputError("audit_scope_case_mismatch")
        cell_keys = [cell.cell_key for cell in inputs.required_cells]
        if len(set(cell_keys)) != len(cell_keys):
            raise CompilerInputError("duplicate_cell_key")
        unknown_dependencies = {dependency for cell in inputs.required_cells for dependency in cell.dependency_cell_keys if dependency not in cell_keys}
        if unknown_dependencies:
            raise CompilerInputError("unknown_cell_dependency")

    @staticmethod
    def _validate_full_cell_fields(
        cell: DecisionCellSeed | DecisionSurfaceCellVersion,
        *,
        cell_label: str,
        policy: CompilerInputValidationPolicy,
    ) -> list[str]:
        errors: list[str] = []
        if _is_blank(cell.decision_question):
            errors.append(f"decision_question_blank:{cell_label}")
        if _is_blank(cell.origin_type):
            errors.append(f"origin_type_blank:{cell_label}")
        if cell.owner_role not in policy.allowed_owner_roles:
            errors.append(f"owner_role_not_allowed:{cell_label}")
        if cell.materiality not in policy.allowed_materialities:
            errors.append(f"materiality_not_allowed:{cell_label}")
        if _is_blank(cell.stop_rule):
            errors.append(f"stop_rule_blank:{cell_label}")
        return errors

    @staticmethod
    def _validate_full_slot(
        slot: EvidenceSlotSeed | EvidenceSlotVersion,
        *,
        slot_label: str,
        policy: CompilerInputValidationPolicy,
    ) -> list[str]:
        errors: list[str] = []
        if _is_blank(slot.evidence_role):
            errors.append(f"evidence_role_blank:{slot_label}")
        if not slot.entity_scope or any(_is_blank(entity) for entity in slot.entity_scope):
            errors.append(f"entity_scope_invalid:{slot_label}")
        if _is_blank(slot.period_scope):
            errors.append(f"period_scope_blank:{slot_label}")
        if slot.source_policy_ref not in policy.allowed_source_policy_refs:
            errors.append(f"source_policy_not_allowed:{slot_label}")
        if policy.require_forbidden_substitutions and not slot.forbidden_substitutions:
            errors.append(f"forbidden_substitutions_required:{slot_label}")
        if slot.acceptance_role not in policy.allowed_acceptance_roles:
            errors.append(f"acceptance_role_not_allowed:{slot_label}")
        return errors

    @classmethod
    def _validate_full_cells_and_slots(
        cls,
        cells: tuple[DecisionCellSeed, ...],
        *,
        policy: CompilerInputValidationPolicy,
    ) -> list[str]:
        errors: list[str] = []
        if not policy.minimum_material_cells <= len(cells) <= policy.maximum_material_cells:
            errors.append(f"material_cell_count_out_of_range:{len(cells)}")
        cell_keys = [cell.cell_key for cell in cells]
        if len(set(cell_keys)) != len(cell_keys):
            errors.append("duplicate_cell_key")
        dependencies = {cell.cell_key: cell.dependency_cell_keys for cell in cells}
        if _has_dependency_cycle(dependencies):
            errors.append("dependency_cycle")
        for cell in cells:
            errors.extend(cls._validate_full_cell_fields(cell, cell_label=cell.cell_key, policy=policy))
            unknown_dependencies = set(cell.dependency_cell_keys) - set(cell_keys)
            if unknown_dependencies:
                errors.append(f"unknown_cell_dependency:{cell.cell_key}")
            if cell.cell_key in cell.dependency_cell_keys:
                errors.append(f"self_dependency:{cell.cell_key}")
            if not cell.evidence_slots:
                errors.append(f"cell_missing_evidence_slot:{cell.cell_key}")
            elif not any(slot.required for slot in cell.evidence_slots):
                errors.append(f"cell_missing_required_evidence_slot:{cell.cell_key}")
            for index, slot in enumerate(cell.evidence_slots, 1):
                errors.extend(cls._validate_full_slot(slot, slot_label=f"{cell.cell_key}:{index}", policy=policy))
        return errors
