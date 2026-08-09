from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from sec_agent.financial_research_generalization_contract import (
    CandidateRetriever,
    CaseResearchProfile,
    DeterministicEvidencePackEvaluator,
    EvidencePackEvaluator,
    FinancialCandidate,
    FinancialResearchContractError,
    ParserAdapter,
    SourceAdapter,
    TypedResidualGap,
    compile_case_research_contract,
    compile_external_case_profile,
    load_financial_research_contract,
    validate_financial_research_contract,
)


pytestmark = pytest.mark.fast_contract

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = (
    ROOT
    / "configs/runtime/fin_ia_0_1_3_s0_s1_financial_research_generalization_contract_v1_0.json"
)
PROOF_PATH = (
    ROOT
    / "configs/releases/fin_ia_0_1_3_s0_s1_financial_research_generalization_zero_call_proof_v1_0.json"
)
MATERIALIZER_PATH = (
    ROOT
    / "scripts/releases/materialize_fin_ia_0_1_3_s0_s1_financial_research_generalization_contract.py"
)


@pytest.fixture(scope="module")
def contract():
    return load_financial_research_contract(CONTRACT_PATH)


def _complete_candidates(compiled) -> tuple[FinancialCandidate, ...]:
    rows: list[FinancialCandidate] = []
    for requirement in compiled.slot_requirements:
        rows.append(
            FinancialCandidate(
                candidate_id=f"candidate-{requirement.slot_id}-a",
                case_key=compiled.case_key,
                slot_id=requirement.slot_id,
                subject_entity_key=compiled.subject_entity_key,
                evidence_owner_entity_key=compiled.subject_entity_key,
                relationship_direction="subject_self_disclosure",
                period_id=compiled.accepted_period_ids[0],
                facet_ids=requirement.required_facets,
                source_family="issuer_primary",
                canonical_source_id=f"source-{requirement.slot_id}-a",
                authority_tier=requirement.coverage_authority_tiers[0],
                candidate_role=requirement.allowed_candidate_roles[0],
                citation_ref=f"citation-{requirement.slot_id}-a",
                lineage_ref=f"lineage-{requirement.slot_id}-a",
            )
        )
        if requirement.minimum_independent_source_families > 1:
            rows.append(
                FinancialCandidate(
                    candidate_id=f"candidate-{requirement.slot_id}-b",
                    case_key=compiled.case_key,
                    slot_id=requirement.slot_id,
                    subject_entity_key=compiled.subject_entity_key,
                    evidence_owner_entity_key=compiled.subject_entity_key,
                    relationship_direction="subject_self_disclosure",
                    period_id=compiled.accepted_period_ids[0],
                    facet_ids=(requirement.required_facets[0],),
                    source_family="regulatory_or_counterparty_primary",
                    canonical_source_id=f"source-{requirement.slot_id}-b",
                    authority_tier=requirement.coverage_authority_tiers[0],
                    candidate_role=requirement.allowed_candidate_roles[0],
                    citation_ref=f"citation-{requirement.slot_id}-b",
                    lineage_ref=f"lineage-{requirement.slot_id}-b",
                )
            )
    return tuple(rows)


def test_contract_loads_and_freezes_only_the_first_step(contract) -> None:
    assert contract.status == "contract_frozen_zero_call"
    assert contract.stage_boundary.contract_frozen is True
    assert contract.stage_boundary.dell_vertical_slice_complete is False
    assert contract.stage_boundary.mu_nvda_transfer_complete is False
    assert contract.stage_boundary.held_out_generalization_complete is False
    assert contract.stage_boundary.sparse_dense_rebuild_admitted is False
    assert contract.stage_boundary.external_residual_supplement_complete is False
    assert contract.stage_boundary.model_research_synthesis_complete is False


def test_three_cases_compile_with_one_identical_core_fingerprint(contract) -> None:
    compiled = [
        compile_case_research_contract(contract, case_key)
        for case_key in ("DELL", "MU", "NVDA")
    ]
    assert len({row.core_fingerprint for row in compiled}) == 1
    assert len({row.compiled_digest for row in compiled}) == 3
    assert all(sum(slot.required for slot in row.slot_requirements) == 8 for row in compiled)
    assert all(sum(not slot.required for slot in row.slot_requirements) == 1 for row in compiled)


def test_core_and_slot_library_do_not_contain_case_or_industry_tokens(contract) -> None:
    payload = json.dumps(
        {
            "kernel": contract.kernel.model_dump(
                mode="json",
                exclude={"reserved_case_tokens", "reserved_industry_tokens"},
            ),
            "slots": [row.model_dump(mode="json") for row in contract.slot_library],
            "plugins": [row.model_dump(mode="json") for row in contract.plugin_interfaces],
        },
        ensure_ascii=False,
    ).casefold()
    for token in contract.kernel.reserved_case_tokens + contract.kernel.reserved_industry_tokens:
        assert token.casefold() not in payload.split()


def test_new_case_configuration_does_not_change_the_core(contract) -> None:
    baseline = compile_case_research_contract(contract, "DELL")
    profile = CaseResearchProfile(
        case_key="TRANSFER_FIXTURE",
        subject_entity_key="TRANSFER_SUBJECT",
        subject_aliases=("Transfer Subject",),
        industry_pack_ref="industry-ai-compute-infrastructure:v1",
        as_of_date="2026-08-06",
        accepted_period_ids=("TRANSFER_CURRENT_PERIOD",),
    )
    transferred = compile_external_case_profile(contract, profile)
    assert transferred.core_fingerprint == baseline.core_fingerprint
    assert transferred.case_key == "TRANSFER_FIXTURE"


def test_industry_pack_cannot_relax_core_authority(contract) -> None:
    mutated_pack = contract.industry_packs[0].model_copy(
        update={"may_relax_identity_period_lineage_or_authority": True}
    )
    mutated = contract.model_copy(update={"industry_packs": (mutated_pack,)})
    with pytest.raises(
        FinancialResearchContractError,
        match="industry_pack_authority_violation",
    ):
        validate_financial_research_contract(mutated)


def test_case_cannot_invent_a_facet_outside_the_industry_pack(contract) -> None:
    profile = contract.case_profiles[0].model_copy(
        update={
            "required_facet_additions": {
                "demand_volume_quality": ("case_only_hidden_answer_facet",)
            }
        }
    )
    with pytest.raises(
        FinancialResearchContractError,
        match="case_profile_facet_outside_industry_pack",
    ):
        compile_external_case_profile(contract, profile)


def test_plugin_protocols_are_provider_neutral_runtime_boundaries() -> None:
    class DummySource:
        def discover(self, intent):
            return ()

    class DummyParser:
        def parse(self, capture):
            return ()

    class DummyRetriever:
        def search(self, request):
            return ()

    assert isinstance(DummySource(), SourceAdapter)
    assert isinstance(DummyParser(), ParserAdapter)
    assert isinstance(DummyRetriever(), CandidateRetriever)
    assert isinstance(DeterministicEvidencePackEvaluator(), EvidencePackEvaluator)


def test_multi_candidate_evaluator_proves_completeness_without_promoting_evidence(
    contract,
) -> None:
    compiled = compile_case_research_contract(contract, "DELL")
    result = DeterministicEvidencePackEvaluator().evaluate(
        compiled, _complete_candidates(compiled)
    )
    assert result.status == "candidate_complete_pending_evidence_gate"
    assert result.evidence_promotion_admitted is False
    assert not result.uncovered_required_facets
    assert all(
        row.status == "candidate_complete_pending_evidence_gate"
        for row, requirement in zip(
            result.slot_evaluations, compiled.slot_requirements, strict=True
        )
        if requirement.required
    )


def test_duplicate_source_bindings_do_not_fake_source_diversity(contract) -> None:
    compiled = compile_case_research_contract(contract, "DELL")
    candidates = list(_complete_candidates(compiled))
    target_slot = next(
        row
        for row in compiled.slot_requirements
        if row.minimum_independent_source_families > 1
    )
    for index, candidate in enumerate(candidates):
        if candidate.slot_id == target_slot.slot_id:
            candidates[index] = candidate.model_copy(
                update={
                    "source_family": "one_family",
                    "canonical_source_id": "same-canonical-document",
                }
            )
    result = DeterministicEvidencePackEvaluator().evaluate(compiled, candidates)
    target = next(row for row in result.slot_evaluations if row.slot_id == target_slot.slot_id)
    assert target.status == "open_residual_gaps"
    assert target.independent_source_families == ("one_family",)
    assert target.unique_canonical_source_ids == ("same-canonical-document",)


def test_cross_case_period_relationship_and_evidence_state_mutations_fail_closed(
    contract,
) -> None:
    compiled = compile_case_research_contract(contract, "DELL")
    requirement = compiled.slot_requirements[0]
    base = FinancialCandidate(
        candidate_id="base",
        case_key=compiled.case_key,
        slot_id=requirement.slot_id,
        subject_entity_key=compiled.subject_entity_key,
        evidence_owner_entity_key=compiled.subject_entity_key,
        relationship_direction="subject_self_disclosure",
        period_id=compiled.accepted_period_ids[0],
        facet_ids=requirement.required_facets,
        source_family="issuer_primary",
        canonical_source_id="source-base",
        authority_tier=requirement.coverage_authority_tiers[0],
        candidate_role=requirement.allowed_candidate_roles[0],
        citation_ref="citation-base",
        lineage_ref="lineage-base",
    )
    relationship = compiled.relationships[0]
    mutations = (
        base.model_copy(update={"candidate_id": "cross", "case_key": "OTHER"}),
        base.model_copy(update={"candidate_id": "period", "period_id": "FUTURE"}),
        base.model_copy(update={"candidate_id": "state", "candidate_state": "accepted_evidence"}),
        base.model_copy(
            update={
                "candidate_id": "reversed",
                "slot_id": relationship.allowed_slot_ids[0],
                "evidence_owner_entity_key": relationship.evidence_owner_entity_key,
                "relationship_direction": "reversed_direction",
                "facet_ids": (
                    next(
                        row
                        for row in compiled.slot_requirements
                        if row.slot_id == relationship.allowed_slot_ids[0]
                    ).required_facets[0],
                ),
                "candidate_role": next(
                    row
                    for row in compiled.slot_requirements
                    if row.slot_id == relationship.allowed_slot_ids[0]
                ).allowed_candidate_roles[0],
                "authority_tier": next(
                    row
                    for row in compiled.slot_requirements
                    if row.slot_id == relationship.allowed_slot_ids[0]
                ).coverage_authority_tiers[0],
            }
        ),
    )
    result = DeterministicEvidencePackEvaluator().evaluate(compiled, mutations)
    assert {row.code for row in result.rejected_candidates} == {
        "cross_case_candidate",
        "wrong_period",
        "candidate_evidence_boundary_violation",
        "relationship_binding_missing_or_reversed",
    }


def test_typed_gap_terminalizes_a_missing_facet_but_does_not_make_pack_complete(
    contract,
) -> None:
    compiled = compile_case_research_contract(contract, "DELL")
    requirement = compiled.slot_requirements[0]
    missing_facet = requirement.required_facets[-1]
    candidate = FinancialCandidate(
        candidate_id="partial",
        case_key=compiled.case_key,
        slot_id=requirement.slot_id,
        subject_entity_key=compiled.subject_entity_key,
        evidence_owner_entity_key=compiled.subject_entity_key,
        relationship_direction="subject_self_disclosure",
        period_id=compiled.accepted_period_ids[0],
        facet_ids=requirement.required_facets[:-1],
        source_family="issuer_primary",
        canonical_source_id="partial-source",
        authority_tier=requirement.coverage_authority_tiers[0],
        candidate_role=requirement.allowed_candidate_roles[0],
        citation_ref="partial-citation",
        lineage_ref="partial-lineage",
    )
    gap = TypedResidualGap(
        gap_id="gap-1",
        case_key=compiled.case_key,
        slot_id=requirement.slot_id,
        facet_id=missing_facet,
        gap_code=requirement.typed_gap_codes[0],
    )
    result = DeterministicEvidencePackEvaluator().evaluate(
        compiled, (candidate,), (gap,)
    )
    target = result.slot_evaluations[0]
    assert target.status == "terminal_with_declared_gaps"
    assert target.declared_gap_facets == (missing_facet,)
    assert result.status == "incomplete_not_admitted"


def test_support_counter_conflict_remains_visible(contract) -> None:
    compiled = compile_case_research_contract(contract, "DELL")
    candidates = list(_complete_candidates(compiled))
    target = candidates[0]
    candidates[0] = target.model_copy(
        update={"semantic_claim_key": "demand-durable", "polarity": "support"}
    )
    candidates.append(
        target.model_copy(
            update={
                "candidate_id": "counter-candidate",
                "canonical_source_id": "counter-source",
                "source_family": "counterparty_primary",
                "citation_ref": "counter-citation",
                "lineage_ref": "counter-lineage",
                "semantic_claim_key": "demand-durable",
                "polarity": "counter",
            }
        )
    )
    result = DeterministicEvidencePackEvaluator().evaluate(compiled, candidates)
    assert result.status == "incomplete_not_admitted"
    assert result.unresolved_conflict_keys == ("demand-durable",)


def test_three_held_out_archetypes_are_blind_and_non_overlapping(contract) -> None:
    assert [row.archetype_id for row in contract.held_out_archetypes] == [
        "heldout-us-non-semiconductor",
        "heldout-non-us-primary-disclosure",
        "heldout-sparse-disclosure",
    ]
    assert all(not row.identity_selected for row in contract.held_out_archetypes)
    assert all(
        not row.answer_or_gold_locator_embedded
        for row in contract.held_out_archetypes
    )


def test_checked_in_zero_call_proof_is_reproducible() -> None:
    spec = importlib.util.spec_from_file_location(
        "financial_research_generalization_materializer", MATERIALIZER_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.build_proof() == json.loads(PROOF_PATH.read_text(encoding="utf-8"))
