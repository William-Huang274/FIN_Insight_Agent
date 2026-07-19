from __future__ import annotations

from typing import Mapping

from .models import StrictModel, canonical_digest
from .planning_service import EvidenceSlotSeed


class EvidencePolicyCompileError(ValueError):
    pass


class EvidenceRoleRule(StrictModel):
    allowed_source_policy_refs: tuple[str, ...]
    allowed_acceptance_roles: tuple[str, ...]
    required_forbidden_substitutions: tuple[str, ...] = ()
    parser_required: bool = False
    commercial_gap_role: bool = False
    relationship_scope_only: bool = False


class SectorEvidenceOntology(StrictModel):
    sector: str
    evidence_role_rules: dict[str, EvidenceRoleRule]


class SlotCompilationInput(StrictModel):
    cell_key: str
    slot_key: str
    slot: EvidenceSlotSeed


class CompiledEvidenceSlotPolicy(StrictModel):
    cell_key: str
    slot_key: str
    evidence_role: str
    source_policy_ref: str
    acceptance_role: str
    resolution_status: str
    forbidden_substitutions: tuple[str, ...]


class CompileTimeGapSeed(StrictModel):
    cell_key: str
    slot_key: str
    gap_type: str
    reason: str
    materiality: str
    owner_suggestion: str
    next_action: str


class EvidencePolicyCompilationResult(StrictModel):
    status: str
    sector: str
    compiled_slots: tuple[CompiledEvidenceSlotPolicy, ...]
    gaps: tuple[CompileTimeGapSeed, ...]
    errors: tuple[str, ...] = ()
    compilation_digest: str
    planning_authority: str = "shadow"
    model_call_count: int = 0
    external_call_count: int = 0


class EvidenceSlotPolicyCompiler:
    """M2.6 sector evidence-policy compiler; typed gaps are explicit output, never silent substitutions."""

    def __init__(self, ontologies: Mapping[str, SectorEvidenceOntology]):
        self.ontologies = dict(ontologies)

    def compile(
        self,
        *,
        sector: str,
        slots: tuple[SlotCompilationInput, ...],
        available_parser_source_policy_refs: tuple[str, ...],
    ) -> EvidencePolicyCompilationResult:
        ontology = self.ontologies.get(sector)
        if ontology is None:
            raise EvidencePolicyCompileError("sector_ontology_not_found")
        available = set(available_parser_source_policy_refs)
        errors: list[str] = []
        gaps: list[CompileTimeGapSeed] = []
        compiled: list[CompiledEvidenceSlotPolicy] = []
        for item in slots:
            rule = ontology.evidence_role_rules.get(item.slot.evidence_role)
            if rule is None:
                errors.append(f"evidence_role_not_in_sector_ontology:{item.slot_key}")
                continue
            if item.slot.source_policy_ref not in rule.allowed_source_policy_refs:
                errors.append(f"source_policy_not_allowed:{item.slot_key}")
            if item.slot.acceptance_role not in rule.allowed_acceptance_roles:
                errors.append(f"acceptance_role_not_allowed:{item.slot_key}")
            missing_forbidden = set(rule.required_forbidden_substitutions) - set(item.slot.forbidden_substitutions)
            if missing_forbidden:
                errors.append(f"required_forbidden_substitution_missing:{item.slot_key}")
            if rule.relationship_scope_only and item.slot.acceptance_role != "bounded_context_only":
                errors.append(f"relationship_scope_overreach:{item.slot_key}")
            resolution_status = "ready"
            if rule.parser_required and item.slot.source_policy_ref not in available:
                resolution_status = "typed_gap"
                gaps.append(
                    CompileTimeGapSeed(
                        cell_key=item.cell_key,
                        slot_key=item.slot_key,
                        gap_type="parser_gap",
                        reason=f"parser unavailable for {item.slot.source_policy_ref}",
                        materiality="high",
                        owner_suggestion="fundamental_analyst",
                        next_action="repair or add parser route before accepting an exact fact",
                    )
                )
            if rule.commercial_gap_role:
                resolution_status = "typed_gap"
                gaps.append(
                    CompileTimeGapSeed(
                        cell_key=item.cell_key,
                        slot_key=item.slot_key,
                        gap_type="commercial_data_gap",
                        reason="commercial-only metric has no approved public substitution",
                        materiality="high",
                        owner_suggestion="research_lead",
                        next_action="record commercial-data gap or obtain an approved licensed source",
                    )
                )
            compiled.append(
                CompiledEvidenceSlotPolicy(
                    cell_key=item.cell_key,
                    slot_key=item.slot_key,
                    evidence_role=item.slot.evidence_role,
                    source_policy_ref=item.slot.source_policy_ref,
                    acceptance_role=item.slot.acceptance_role,
                    resolution_status=resolution_status,
                    forbidden_substitutions=item.slot.forbidden_substitutions,
                )
            )
        digest = canonical_digest(
            {
                "sector": sector,
                "slots": [slot.model_dump(mode="json") for slot in compiled],
                "gaps": [gap.model_dump(mode="json") for gap in gaps],
                "errors": sorted(set(errors)),
            }
        )
        return EvidencePolicyCompilationResult(
            status="fail" if errors else ("pass_with_typed_gaps" if gaps else "pass"),
            sector=sector,
            compiled_slots=tuple(compiled),
            gaps=tuple(gaps),
            errors=tuple(sorted(set(errors))),
            compilation_digest=digest,
        )
