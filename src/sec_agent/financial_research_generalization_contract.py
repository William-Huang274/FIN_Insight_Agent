from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Mapping, Protocol, Sequence, runtime_checkable

from pydantic import Field

from sec_agent.canonical_runtime.models import StrictModel, canonical_digest


CONTRACT_SCHEMA = "fin_ia_0_1_3_s0_s1_financial_research_generalization_contract_v1_0"
CONTRACT_REF = "fin_0_1_3.S0_S1.financial_research_generalization:v1"
EXPECTED_PLUGIN_INTERFACES = {
    "SourceAdapter": ("discover", "SearchIntent", "SourceLocator"),
    "ParserAdapter": ("parse", "RawCaptureRef", "FinancialDocumentObject"),
    "CandidateRetriever": (
        "search",
        "TypedRetrievalRequest",
        "FinancialCandidate",
    ),
    "EvidencePackEvaluator": (
        "evaluate",
        "CandidatePackInput",
        "CandidatePackEvaluation",
    ),
}


class FinancialResearchContractError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class ModelAuthorityBoundary(StrictModel):
    may_propose_query_atoms: bool
    may_propose_follow_up_facets: bool
    may_change_identity: bool
    may_change_period: bool
    may_change_relationship_direction: bool
    may_change_source_authority: bool
    may_change_budget: bool
    may_promote_candidate_to_evidence: bool


class KernelPolicy(StrictModel):
    required_dimensions: tuple[str, ...]
    candidate_evidence_boundary: str
    missing_information_policy: str
    source_diversity_counting_unit: str
    model_authority: ModelAuthorityBoundary
    reserved_case_tokens: tuple[str, ...]
    reserved_industry_tokens: tuple[str, ...]


class EvidenceSlotDefinition(StrictModel):
    slot_id: str
    purpose: str
    required_facets: tuple[str, ...]
    optional_facets: tuple[str, ...] = ()
    minimum_independent_source_families: int = Field(default=1, ge=1)
    coverage_authority_tiers: tuple[str, ...]
    allowed_candidate_roles: tuple[str, ...]
    legacy_family_refs: tuple[str, ...] = ()
    typed_gap_codes: tuple[str, ...]


class PluginInterfaceDefinition(StrictModel):
    interface_name: str
    method: str
    input_contract: str
    output_contract: str
    authority_boundary: str


class IndustrySlotExtension(StrictModel):
    slot_id: str
    available_facets: tuple[str, ...]
    default_required_facets: tuple[str, ...] = ()
    query_atoms: tuple[str, ...] = ()
    mechanism_axes: tuple[str, ...] = ()
    source_role_preferences: tuple[str, ...] = ()
    forbidden_substitutions: tuple[str, ...] = ()


class IndustryPackDefinition(StrictModel):
    pack_ref: str
    industry_family: str
    required_slot_ids: tuple[str, ...]
    optional_slot_ids: tuple[str, ...] = ()
    slot_extensions: tuple[IndustrySlotExtension, ...]
    may_override_kernel_dimensions: bool = False
    may_relax_identity_period_lineage_or_authority: bool = False
    may_embed_case_urls_or_gold_targets: bool = False


class RelationshipBinding(StrictModel):
    relationship_id: str
    evidence_owner_entity_key: str
    evidence_owner_aliases: tuple[str, ...]
    evidence_owner_role: str
    direction: str
    allowed_slot_ids: tuple[str, ...]


class CaseResearchProfile(StrictModel):
    case_key: str
    subject_entity_key: str
    subject_aliases: tuple[str, ...]
    industry_pack_ref: str
    as_of_date: str
    accepted_period_ids: tuple[str, ...]
    required_slot_ids: tuple[str, ...] = ()
    optional_slot_ids: tuple[str, ...] = ()
    required_facet_additions: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    relationships: tuple[RelationshipBinding, ...] = ()


class HeldOutArchetype(StrictModel):
    archetype_id: str
    purpose: str
    required_source_shapes: tuple[str, ...]
    required_mutations: tuple[str, ...]
    identity_selected: bool = False
    answer_or_gold_locator_embedded: bool = False


class StageBoundary(StrictModel):
    contract_frozen: bool
    dell_vertical_slice_complete: bool
    mu_nvda_transfer_complete: bool
    held_out_generalization_complete: bool
    sparse_dense_rebuild_admitted: bool
    external_residual_supplement_complete: bool
    model_research_synthesis_complete: bool


class FinancialResearchGeneralizationContract(StrictModel):
    schema_version: str
    contract_ref: str
    recorded_at: str
    status: str
    kernel: KernelPolicy
    slot_library: tuple[EvidenceSlotDefinition, ...]
    plugin_interfaces: tuple[PluginInterfaceDefinition, ...]
    industry_packs: tuple[IndustryPackDefinition, ...]
    case_profiles: tuple[CaseResearchProfile, ...]
    held_out_archetypes: tuple[HeldOutArchetype, ...]
    execution_order: tuple[str, ...]
    stage_boundary: StageBoundary


class CompiledSlotRequirement(StrictModel):
    slot_id: str
    required: bool
    required_facets: tuple[str, ...]
    optional_facets: tuple[str, ...]
    minimum_independent_source_families: int
    coverage_authority_tiers: tuple[str, ...]
    allowed_candidate_roles: tuple[str, ...]
    typed_gap_codes: tuple[str, ...]


class CompiledCaseResearchContract(StrictModel):
    case_key: str
    subject_entity_key: str
    industry_pack_ref: str
    as_of_date: str
    accepted_period_ids: tuple[str, ...]
    slot_requirements: tuple[CompiledSlotRequirement, ...]
    relationships: tuple[RelationshipBinding, ...]
    core_fingerprint: str
    compiled_digest: str


class FinancialCandidate(StrictModel):
    candidate_id: str
    case_key: str
    slot_id: str
    subject_entity_key: str
    evidence_owner_entity_key: str
    relationship_direction: str
    period_id: str
    facet_ids: tuple[str, ...]
    source_family: str
    canonical_source_id: str
    authority_tier: str
    candidate_role: str
    citation_ref: str
    lineage_ref: str
    candidate_state: str = "candidate_only"
    semantic_claim_key: str | None = None
    polarity: str = "neutral"


class TypedResidualGap(StrictModel):
    gap_id: str
    case_key: str
    slot_id: str
    facet_id: str
    gap_code: str
    attempted_route_refs: tuple[str, ...] = ()


class CandidateRejection(StrictModel):
    candidate_id: str
    code: str


class SlotCoverageEvaluation(StrictModel):
    slot_id: str
    status: str
    covered_facets: tuple[str, ...]
    missing_facets: tuple[str, ...]
    declared_gap_facets: tuple[str, ...]
    unique_candidate_ids: tuple[str, ...]
    unique_canonical_source_ids: tuple[str, ...]
    independent_source_families: tuple[str, ...]
    unresolved_conflict_keys: tuple[str, ...]


class CandidatePackEvaluation(StrictModel):
    case_key: str
    status: str
    slot_evaluations: tuple[SlotCoverageEvaluation, ...]
    rejected_candidates: tuple[CandidateRejection, ...]
    uncovered_required_facets: tuple[str, ...]
    unresolved_conflict_keys: tuple[str, ...]
    evidence_promotion_admitted: bool = False
    evaluator_boundary: str = (
        "candidate completeness only; Evidence Gate and reviewer remain authoritative"
    )
    evaluation_digest: str


@runtime_checkable
class SourceAdapter(Protocol):
    def discover(self, intent: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]: ...


@runtime_checkable
class ParserAdapter(Protocol):
    def parse(self, capture: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]: ...


@runtime_checkable
class CandidateRetriever(Protocol):
    def search(self, request: Mapping[str, Any]) -> Sequence[FinancialCandidate]: ...


@runtime_checkable
class EvidencePackEvaluator(Protocol):
    def evaluate(
        self,
        compiled_case: CompiledCaseResearchContract,
        candidates: Sequence[FinancialCandidate],
        declared_gaps: Sequence[TypedResidualGap] = (),
    ) -> CandidatePackEvaluation: ...


def load_financial_research_contract(
    path: str | Path,
) -> FinancialResearchGeneralizationContract:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    try:
        contract = FinancialResearchGeneralizationContract.model_validate(payload)
    except Exception as exc:  # pydantic emits implementation-shaped detail
        raise FinancialResearchContractError("generalization_contract_shape_invalid") from exc
    validate_financial_research_contract(contract)
    return contract


def validate_financial_research_contract(
    contract: FinancialResearchGeneralizationContract,
) -> None:
    if (
        contract.schema_version != CONTRACT_SCHEMA
        or contract.contract_ref != CONTRACT_REF
        or contract.status != "contract_frozen_zero_call"
    ):
        raise FinancialResearchContractError("generalization_contract_identity_invalid")
    _require_unique((row.slot_id for row in contract.slot_library), "slot_identity")
    _require_unique((row.interface_name for row in contract.plugin_interfaces), "plugin_identity")
    _require_unique((row.pack_ref for row in contract.industry_packs), "industry_pack_identity")
    _require_unique((row.case_key for row in contract.case_profiles), "case_profile_identity")
    _require_unique((row.archetype_id for row in contract.held_out_archetypes), "held_out_identity")
    _validate_kernel_boundary(contract)
    _validate_plugin_interfaces(contract.plugin_interfaces)
    slots = {row.slot_id: row for row in contract.slot_library}
    packs = {row.pack_ref: row for row in contract.industry_packs}
    for slot in slots.values():
        if (
            not slot.required_facets
            or not slot.coverage_authority_tiers
            or not slot.allowed_candidate_roles
            or not slot.typed_gap_codes
        ):
            raise FinancialResearchContractError("slot_contract_incomplete")
        _require_unique(slot.required_facets + slot.optional_facets, "slot_facet")
    for pack in packs.values():
        available = set(pack.required_slot_ids) | set(pack.optional_slot_ids)
        if not pack.required_slot_ids or available - set(slots):
            raise FinancialResearchContractError("industry_pack_slot_reference_invalid")
        if (
            pack.may_override_kernel_dimensions
            or pack.may_relax_identity_period_lineage_or_authority
            or pack.may_embed_case_urls_or_gold_targets
        ):
            raise FinancialResearchContractError("industry_pack_authority_violation")
        _require_unique((row.slot_id for row in pack.slot_extensions), "industry_extension_slot")
        for extension in pack.slot_extensions:
            if extension.slot_id not in available:
                raise FinancialResearchContractError("industry_extension_slot_invalid")
            if set(extension.default_required_facets) - set(extension.available_facets):
                raise FinancialResearchContractError("industry_extension_required_facet_invalid")
            _require_unique(
                extension.available_facets,
                "industry_extension_available_facet",
            )
    for profile in contract.case_profiles:
        _validate_case_profile(profile, slots=slots, packs=packs)
    if len(contract.held_out_archetypes) != 3:
        raise FinancialResearchContractError("held_out_archetype_count_invalid")
    if any(
        row.identity_selected or row.answer_or_gold_locator_embedded
        for row in contract.held_out_archetypes
    ):
        raise FinancialResearchContractError("held_out_leakage_boundary_invalid")
    if contract.execution_order != (
        "freeze_contract",
        "dell_vertical_slice",
        "mu_nvda_core_unchanged_transfer",
        "three_held_out_generalization_proof",
        "sparse_dense_rebuild_decision",
        "residual_gap_external_supplement",
        "model_dynamic_follow_up_and_synthesis",
    ):
        raise FinancialResearchContractError("execution_order_invalid")
    if contract.stage_boundary != StageBoundary(
        contract_frozen=True,
        dell_vertical_slice_complete=False,
        mu_nvda_transfer_complete=False,
        held_out_generalization_complete=False,
        sparse_dense_rebuild_admitted=False,
        external_residual_supplement_complete=False,
        model_research_synthesis_complete=False,
    ):
        raise FinancialResearchContractError("stage_boundary_invalid")


def compile_case_research_contract(
    contract: FinancialResearchGeneralizationContract,
    case_key: str,
) -> CompiledCaseResearchContract:
    try:
        profile = next(row for row in contract.case_profiles if row.case_key == case_key)
    except StopIteration as exc:
        raise FinancialResearchContractError("case_profile_unknown") from exc
    return compile_external_case_profile(contract, profile)


def compile_external_case_profile(
    contract: FinancialResearchGeneralizationContract,
    profile: CaseResearchProfile,
) -> CompiledCaseResearchContract:
    slots = {row.slot_id: row for row in contract.slot_library}
    packs = {row.pack_ref: row for row in contract.industry_packs}
    _validate_case_profile(profile, slots=slots, packs=packs)
    pack = packs[profile.industry_pack_ref]
    extensions = {row.slot_id: row for row in pack.slot_extensions}
    required_ids = _ordered_unique(pack.required_slot_ids + profile.required_slot_ids)
    optional_ids = tuple(
        value
        for value in _ordered_unique(pack.optional_slot_ids + profile.optional_slot_ids)
        if value not in set(required_ids)
    )
    requirements: list[CompiledSlotRequirement] = []
    for slot_id in required_ids + optional_ids:
        slot = slots[slot_id]
        extension = extensions.get(slot_id)
        required_facets = list(slot.required_facets)
        if extension:
            required_facets.extend(extension.default_required_facets)
        required_facets.extend(profile.required_facet_additions.get(slot_id, ()))
        optional_facets = list(slot.optional_facets)
        if extension:
            optional_facets.extend(
                facet
                for facet in extension.available_facets
                if facet not in set(required_facets)
            )
        requirements.append(
            CompiledSlotRequirement(
                slot_id=slot_id,
                required=slot_id in set(required_ids),
                required_facets=_ordered_unique(tuple(required_facets)),
                optional_facets=_ordered_unique(tuple(optional_facets)),
                minimum_independent_source_families=(
                    slot.minimum_independent_source_families
                ),
                coverage_authority_tiers=slot.coverage_authority_tiers,
                allowed_candidate_roles=slot.allowed_candidate_roles,
                typed_gap_codes=slot.typed_gap_codes,
            )
        )
    core_fingerprint = canonical_digest(
        {
            "kernel": contract.kernel.model_dump(mode="json"),
            "slot_library": [row.model_dump(mode="json") for row in contract.slot_library],
            "plugin_interfaces": [
                row.model_dump(mode="json") for row in contract.plugin_interfaces
            ],
        }
    )
    body = {
        "case_key": profile.case_key,
        "subject_entity_key": profile.subject_entity_key,
        "industry_pack_ref": profile.industry_pack_ref,
        "as_of_date": profile.as_of_date,
        "accepted_period_ids": profile.accepted_period_ids,
        "slot_requirements": [row.model_dump(mode="json") for row in requirements],
        "relationships": [row.model_dump(mode="json") for row in profile.relationships],
        "core_fingerprint": core_fingerprint,
    }
    return CompiledCaseResearchContract(
        **body,
        compiled_digest=canonical_digest(body),
    )


class DeterministicEvidencePackEvaluator:
    def evaluate(
        self,
        compiled_case: CompiledCaseResearchContract,
        candidates: Sequence[FinancialCandidate],
        declared_gaps: Sequence[TypedResidualGap] = (),
    ) -> CandidatePackEvaluation:
        requirements = {row.slot_id: row for row in compiled_case.slot_requirements}
        relationships = {
            (row.evidence_owner_entity_key, row.direction, slot_id)
            for row in compiled_case.relationships
            for slot_id in row.allowed_slot_ids
        }
        accepted: dict[str, list[FinancialCandidate]] = {
            slot_id: [] for slot_id in requirements
        }
        rejections: list[CandidateRejection] = []
        seen_candidate_ids: set[str] = set()
        for candidate in candidates:
            code = _candidate_rejection_code(
                candidate,
                compiled_case=compiled_case,
                requirements=requirements,
                relationships=relationships,
            )
            if candidate.candidate_id in seen_candidate_ids:
                code = "duplicate_candidate_id"
            seen_candidate_ids.add(candidate.candidate_id)
            if code:
                rejections.append(
                    CandidateRejection(candidate_id=candidate.candidate_id, code=code)
                )
                continue
            accepted[candidate.slot_id].append(candidate)
        gap_index = {
            (gap.slot_id, gap.facet_id): gap
            for gap in declared_gaps
            if gap.case_key == compiled_case.case_key
        }
        slot_results: list[SlotCoverageEvaluation] = []
        all_missing: list[str] = []
        all_conflicts: set[str] = set()
        for requirement in compiled_case.slot_requirements:
            rows = accepted[requirement.slot_id]
            covered = {
                facet
                for row in rows
                if row.authority_tier in set(requirement.coverage_authority_tiers)
                for facet in row.facet_ids
                if facet in set(requirement.required_facets)
            }
            missing = tuple(
                facet for facet in requirement.required_facets if facet not in covered
            )
            declared = tuple(
                facet
                for facet in missing
                if (requirement.slot_id, facet) in gap_index
                and gap_index[(requirement.slot_id, facet)].gap_code
                in set(requirement.typed_gap_codes)
            )
            source_families = tuple(sorted({row.source_family for row in rows}))
            conflicts = _conflict_keys(rows)
            all_conflicts.update(conflicts)
            if conflicts:
                status = "conflicted_not_ready"
            elif not missing and len(source_families) >= requirement.minimum_independent_source_families:
                status = "candidate_complete_pending_evidence_gate"
            elif missing and set(declared) == set(missing):
                status = "terminal_with_declared_gaps"
            else:
                status = "open_residual_gaps"
            if requirement.required:
                all_missing.extend(
                    f"{requirement.slot_id}:{facet}" for facet in missing
                )
            slot_results.append(
                SlotCoverageEvaluation(
                    slot_id=requirement.slot_id,
                    status=status,
                    covered_facets=tuple(sorted(covered)),
                    missing_facets=missing,
                    declared_gap_facets=declared,
                    unique_candidate_ids=tuple(sorted({row.candidate_id for row in rows})),
                    unique_canonical_source_ids=tuple(
                        sorted({row.canonical_source_id for row in rows})
                    ),
                    independent_source_families=source_families,
                    unresolved_conflict_keys=conflicts,
                )
            )
        required_results = [
            row
            for row, requirement in zip(
                slot_results, compiled_case.slot_requirements, strict=True
            )
            if requirement.required
        ]
        status = (
            "candidate_complete_pending_evidence_gate"
            if required_results
            and all(
                row.status == "candidate_complete_pending_evidence_gate"
                for row in required_results
            )
            else "incomplete_not_admitted"
        )
        body = {
            "case_key": compiled_case.case_key,
            "status": status,
            "slot_evaluations": [row.model_dump(mode="json") for row in slot_results],
            "rejected_candidates": [row.model_dump(mode="json") for row in rejections],
            "uncovered_required_facets": sorted(set(all_missing)),
            "unresolved_conflict_keys": sorted(all_conflicts),
            "evidence_promotion_admitted": False,
            "evaluator_boundary": (
                "candidate completeness only; Evidence Gate and reviewer remain authoritative"
            ),
        }
        return CandidatePackEvaluation(
            **body,
            evaluation_digest=canonical_digest(body),
        )


def _validate_kernel_boundary(
    contract: FinancialResearchGeneralizationContract,
) -> None:
    model = contract.kernel.model_authority
    if (
        not model.may_propose_query_atoms
        or not model.may_propose_follow_up_facets
        or model.may_change_identity
        or model.may_change_period
        or model.may_change_relationship_direction
        or model.may_change_source_authority
        or model.may_change_budget
        or model.may_promote_candidate_to_evidence
    ):
        raise FinancialResearchContractError("kernel_model_authority_invalid")
    core_payload = json.dumps(
        {
            "kernel": contract.kernel.model_dump(
                mode="json",
                exclude={"reserved_case_tokens", "reserved_industry_tokens"},
            ),
            "slot_library": [row.model_dump(mode="json") for row in contract.slot_library],
            "plugin_interfaces": [
                row.model_dump(mode="json") for row in contract.plugin_interfaces
            ],
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    searchable = set(_semantic_tokens(core_payload))
    forbidden = {
        token.casefold()
        for token in (
            contract.kernel.reserved_case_tokens
            + contract.kernel.reserved_industry_tokens
        )
    }
    if searchable & forbidden:
        raise FinancialResearchContractError("kernel_case_or_industry_contamination")


def _validate_plugin_interfaces(
    interfaces: Sequence[PluginInterfaceDefinition],
) -> None:
    actual = {
        row.interface_name: (row.method, row.input_contract, row.output_contract)
        for row in interfaces
    }
    if actual != EXPECTED_PLUGIN_INTERFACES:
        raise FinancialResearchContractError("plugin_interface_contract_invalid")
    if any("authority" not in row.authority_boundary.casefold() for row in interfaces):
        raise FinancialResearchContractError("plugin_interface_authority_missing")


def _validate_case_profile(
    profile: CaseResearchProfile,
    *,
    slots: Mapping[str, EvidenceSlotDefinition],
    packs: Mapping[str, IndustryPackDefinition],
) -> None:
    pack = packs.get(profile.industry_pack_ref)
    if pack is None:
        raise FinancialResearchContractError("case_industry_pack_unknown")
    available_slots = set(pack.required_slot_ids) | set(pack.optional_slot_ids)
    selected_slots = set(profile.required_slot_ids) | set(profile.optional_slot_ids)
    if (
        not profile.case_key
        or not profile.subject_entity_key
        or not profile.subject_aliases
        or not profile.accepted_period_ids
        or selected_slots - available_slots
        or available_slots - set(slots)
    ):
        raise FinancialResearchContractError("case_profile_scope_invalid")
    extension_facets = {
        row.slot_id: set(row.available_facets) for row in pack.slot_extensions
    }
    for slot_id, facets in profile.required_facet_additions.items():
        if slot_id not in available_slots or set(facets) - extension_facets.get(slot_id, set()):
            raise FinancialResearchContractError("case_profile_facet_outside_industry_pack")
    relationship_ids: set[str] = set()
    for relation in profile.relationships:
        if (
            relation.relationship_id in relationship_ids
            or relation.evidence_owner_entity_key == profile.subject_entity_key
            or not relation.evidence_owner_aliases
            or set(relation.allowed_slot_ids) - available_slots
        ):
            raise FinancialResearchContractError("case_relationship_invalid")
        relationship_ids.add(relation.relationship_id)


def _candidate_rejection_code(
    candidate: FinancialCandidate,
    *,
    compiled_case: CompiledCaseResearchContract,
    requirements: Mapping[str, CompiledSlotRequirement],
    relationships: set[tuple[str, str, str]],
) -> str | None:
    requirement = requirements.get(candidate.slot_id)
    if candidate.case_key != compiled_case.case_key:
        return "cross_case_candidate"
    if candidate.subject_entity_key != compiled_case.subject_entity_key:
        return "wrong_subject_identity"
    if requirement is None:
        return "unknown_slot"
    if candidate.period_id not in set(compiled_case.accepted_period_ids):
        return "wrong_period"
    if candidate.candidate_state not in {"candidate_only", "qualified_candidate"}:
        return "candidate_evidence_boundary_violation"
    if not candidate.citation_ref or not candidate.lineage_ref:
        return "citation_or_lineage_missing"
    if candidate.candidate_role not in set(requirement.allowed_candidate_roles):
        return "candidate_role_not_allowed"
    if set(candidate.facet_ids) - set(
        requirement.required_facets + requirement.optional_facets
    ):
        return "facet_outside_compiled_contract"
    if candidate.evidence_owner_entity_key == compiled_case.subject_entity_key:
        if candidate.relationship_direction != "subject_self_disclosure":
            return "subject_relationship_direction_invalid"
    elif (
        candidate.evidence_owner_entity_key,
        candidate.relationship_direction,
        candidate.slot_id,
    ) not in relationships:
        return "relationship_binding_missing_or_reversed"
    if candidate.polarity not in {"support", "counter", "neutral"}:
        return "candidate_polarity_invalid"
    return None


def _conflict_keys(candidates: Sequence[FinancialCandidate]) -> tuple[str, ...]:
    polarities: dict[str, set[str]] = {}
    for candidate in candidates:
        if candidate.semantic_claim_key and candidate.polarity in {"support", "counter"}:
            polarities.setdefault(candidate.semantic_claim_key, set()).add(
                candidate.polarity
            )
    return tuple(
        sorted(key for key, values in polarities.items() if values == {"support", "counter"})
    )


def _semantic_tokens(value: str) -> tuple[str, ...]:
    return tuple(token.casefold() for token in re.findall(r"[A-Za-z][A-Za-z0-9_-]+", value))


def _ordered_unique(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _require_unique(values: Sequence[str] | Any, label: str) -> None:
    rows = tuple(values)
    if any(not str(value).strip() for value in rows) or len(rows) != len(set(rows)):
        raise FinancialResearchContractError(f"{label}_invalid")


__all__ = [
    "CONTRACT_REF",
    "CONTRACT_SCHEMA",
    "CandidatePackEvaluation",
    "CaseResearchProfile",
    "CompiledCaseResearchContract",
    "DeterministicEvidencePackEvaluator",
    "EvidencePackEvaluator",
    "FinancialCandidate",
    "FinancialResearchContractError",
    "FinancialResearchGeneralizationContract",
    "HeldOutArchetype",
    "ParserAdapter",
    "SourceAdapter",
    "CandidateRetriever",
    "TypedResidualGap",
    "compile_case_research_contract",
    "compile_external_case_profile",
    "load_financial_research_contract",
    "validate_financial_research_contract",
]
