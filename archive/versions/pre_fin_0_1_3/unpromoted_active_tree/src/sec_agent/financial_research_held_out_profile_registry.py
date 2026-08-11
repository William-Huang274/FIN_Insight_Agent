from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from sec_agent.canonical_runtime.models import StrictModel, canonical_digest
from sec_agent.financial_research_generalization_contract import (
    CaseResearchProfile,
    FinancialResearchContractError,
    FinancialResearchGeneralizationContract,
    IndustryPackDefinition,
    compile_external_case_profile,
    load_financial_research_contract,
    validate_financial_research_contract,
)
from sec_agent.financial_research_source_object_vertical import normalized_sha256


HELD_OUT_PROFILE_POLICY_SCHEMA = (
    "fin_ia_0_1_3_s1_three_held_out_profile_selection_policy_v1_0"
)
HELD_OUT_PROFILE_RESULT_SCHEMA = (
    "fin_ia_0_1_3_s1_three_held_out_profile_selection_result_v1_0"
)
HELD_OUT_PROFILE_RUN_SCOPE = (
    "S1_THREE_HELD_OUT_FINANCIAL_RESEARCH_GENERALIZATION_PROOF"
)


class HeldOutProfileRegistryError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class LockedHeldOutArtifact(StrictModel):
    artifact_id: str
    path: str
    normalized_sha256: str
    role: str


class HeldOutCaseSelection(StrictModel):
    archetype_id: str
    profile: CaseResearchProfile
    research_questions_zh: tuple[str, ...]
    identity_selected_before_candidate_inspection: bool
    answer_or_gold_locator_embedded: bool


class HeldOutProfileSelectionPolicy(StrictModel):
    schema_version: str
    contract_ref: str
    run_scope: str
    recorded_at: str
    selection_attempt_id: str
    generalization_contract_ref: str
    generalization_contract_sha256: str
    expected_core_fingerprint: str
    locked_artifacts: tuple[LockedHeldOutArtifact, ...]
    industry_pack_overlays: tuple[IndustryPackDefinition, ...]
    selections: tuple[HeldOutCaseSelection, ...]
    pre_freeze_observation_boundary: dict[str, Any]
    hard_boundaries: dict[str, Any]


def load_held_out_profile_selection_policy(
    path: str | Path,
    *,
    repo_root: str | Path,
) -> tuple[
    HeldOutProfileSelectionPolicy,
    FinancialResearchGeneralizationContract,
    FinancialResearchGeneralizationContract,
]:
    root = Path(repo_root).resolve()
    try:
        policy = HeldOutProfileSelectionPolicy.model_validate(
            json.loads(Path(path).read_text(encoding="utf-8"))
        )
    except Exception as exc:
        raise HeldOutProfileRegistryError(
            "held_out_profile_policy_shape_invalid"
        ) from exc
    if (
        policy.schema_version != HELD_OUT_PROFILE_POLICY_SCHEMA
        or policy.run_scope != HELD_OUT_PROFILE_RUN_SCOPE
    ):
        raise HeldOutProfileRegistryError("held_out_profile_policy_identity_invalid")
    _validate_zero_call_boundary(policy.hard_boundaries)
    _validate_locked_artifacts(policy, repo_root=root)

    contract_path = _resolve(root, policy.generalization_contract_ref)
    if normalized_sha256(contract_path) != policy.generalization_contract_sha256:
        raise HeldOutProfileRegistryError(
            "held_out_generalization_contract_digest_mismatch"
        )
    base_contract = load_financial_research_contract(contract_path)
    validate_financial_research_contract(base_contract)
    _validate_selection(policy, base_contract=base_contract)

    overlay_refs = tuple(row.pack_ref for row in policy.industry_pack_overlays)
    if len(overlay_refs) != len(set(overlay_refs)):
        raise HeldOutProfileRegistryError("held_out_industry_pack_identity_invalid")
    if set(overlay_refs) & {row.pack_ref for row in base_contract.industry_packs}:
        raise HeldOutProfileRegistryError("held_out_industry_pack_overrides_base")
    extended = base_contract.model_copy(
        update={
            "industry_packs": (
                base_contract.industry_packs + policy.industry_pack_overlays
            )
        }
    )
    # The complete contract validator proves that overlay packs cannot relax the
    # kernel, plugin, authority, slot, or stage-boundary rules.
    try:
        validate_financial_research_contract(extended)
    except FinancialResearchContractError as exc:
        raise HeldOutProfileRegistryError(
            "held_out_industry_pack_contract_invalid"
        ) from exc
    pack_refs = set(overlay_refs)
    for row in policy.selections:
        if row.profile.industry_pack_ref not in pack_refs:
            raise HeldOutProfileRegistryError(
                "held_out_profile_pack_not_in_overlay"
            )
        try:
            compiled = compile_external_case_profile(extended, row.profile)
        except FinancialResearchContractError as exc:
            raise HeldOutProfileRegistryError(
                "held_out_profile_contract_invalid"
            ) from exc
        if compiled.core_fingerprint != policy.expected_core_fingerprint:
            raise HeldOutProfileRegistryError("held_out_core_fingerprint_mismatch")
    return policy, base_contract, extended


def execute_held_out_profile_selection(
    *,
    policy: HeldOutProfileSelectionPolicy,
    base_contract: FinancialResearchGeneralizationContract,
    extended_contract: FinancialResearchGeneralizationContract,
    repo_root: str | Path,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    before = _locked_digest_map(policy, repo_root=root)
    cases: list[dict[str, Any]] = []
    for selection in policy.selections:
        archetype = next(
            row
            for row in base_contract.held_out_archetypes
            if row.archetype_id == selection.archetype_id
        )
        compiled = compile_external_case_profile(
            extended_contract,
            selection.profile,
        )
        cases.append(
            {
                "archetype_id": selection.archetype_id,
                "case_key": selection.profile.case_key,
                "subject_entity_key": selection.profile.subject_entity_key,
                "industry_pack_ref": selection.profile.industry_pack_ref,
                "as_of_date": selection.profile.as_of_date,
                "accepted_period_ids": list(selection.profile.accepted_period_ids),
                "required_source_shapes": list(archetype.required_source_shapes),
                "required_mutations": list(archetype.required_mutations),
                "research_questions_zh": list(selection.research_questions_zh),
                "compiled_case_digest": compiled.compiled_digest,
                "compiled_core_fingerprint": compiled.core_fingerprint,
                "required_slot_count": sum(
                    1 for row in compiled.slot_requirements if row.required
                ),
                "optional_slot_count": sum(
                    1 for row in compiled.slot_requirements if not row.required
                ),
                "candidate_or_gold_inspection_count": 0,
            }
        )
    after = _locked_digest_map(policy, repo_root=root)
    if before != after:
        raise HeldOutProfileRegistryError("held_out_locked_artifact_changed")
    body = {
        "schema_version": HELD_OUT_PROFILE_RESULT_SCHEMA,
        "contract_ref": policy.contract_ref,
        "run_scope": policy.run_scope,
        "recorded_at": policy.recorded_at,
        "selection_attempt_id": policy.selection_attempt_id,
        "status": "held_out_identity_and_profile_freeze_pass",
        "expected_core_fingerprint": policy.expected_core_fingerprint,
        "locked_artifacts_before": before,
        "locked_artifacts_after": after,
        "case_selections": cases,
        "pre_freeze_observation_boundary": dict(
            policy.pre_freeze_observation_boundary
        ),
        "observed_calls": {
            "network": 0,
            "provider": 0,
            "model": 0,
            "retrieval": 0,
            "embedding": 0,
            "rerank": 0,
            "evidence_promotion": 0,
        },
        "stage_acceptance": {
            "identity_and_profile_selection_frozen": True,
            "external_profile_overlay_compiles": True,
            "locked_core_unchanged": True,
            "candidate_inspection_started": False,
            "held_out_generalization_complete": False,
            "sparse_dense_rebuild_admitted": False,
            "external_supplement_admitted": False,
            "model_synthesis_admitted": False,
        },
        "known_boundary": (
            "This freezes identities, questions, source shapes, mutations, "
            "industry-pack overlays and CaseResearchProfiles before retrieval. "
            "It does not establish local corpus presence, candidate quality, "
            "Evidence completeness, index admission, external supplement, "
            "model synthesis or report acceptance."
        ),
    }
    return {**body, "result_digest": canonical_digest(body)}


def _validate_selection(
    policy: HeldOutProfileSelectionPolicy,
    *,
    base_contract: FinancialResearchGeneralizationContract,
) -> None:
    expected_archetypes = tuple(
        row.archetype_id for row in base_contract.held_out_archetypes
    )
    actual_archetypes = tuple(row.archetype_id for row in policy.selections)
    if actual_archetypes != expected_archetypes:
        raise HeldOutProfileRegistryError(
            "held_out_archetype_order_or_identity_invalid"
        )
    case_keys = tuple(row.profile.case_key for row in policy.selections)
    subjects = tuple(row.profile.subject_entity_key for row in policy.selections)
    if len(case_keys) != len(set(case_keys)) or len(subjects) != len(set(subjects)):
        raise HeldOutProfileRegistryError("held_out_case_identity_duplicate")
    base_payload = json.dumps(
        base_contract.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
    ).casefold()
    for selection in policy.selections:
        if (
            not selection.identity_selected_before_candidate_inspection
            or selection.answer_or_gold_locator_embedded
            or len(selection.research_questions_zh) < 3
            or any(not value.strip() for value in selection.research_questions_zh)
        ):
            raise HeldOutProfileRegistryError("held_out_selection_boundary_invalid")
        identity_terms = (
            selection.profile.case_key,
            selection.profile.subject_entity_key,
        ) + selection.profile.subject_aliases
        if any(term.casefold() in base_payload for term in identity_terms):
            raise HeldOutProfileRegistryError(
                "held_out_identity_seen_in_base_contract"
            )
    serialized = json.dumps(policy.model_dump(mode="json"), ensure_ascii=False)
    forbidden = ("http://", "https://", "target_id", "accession_number")
    if any(token in serialized for token in forbidden):
        raise HeldOutProfileRegistryError("held_out_gold_or_locator_leakage")
    observation = policy.pre_freeze_observation_boundary
    if (
        observation.get("candidate_results_inspected") is not False
        or observation.get("qrels_or_gold_inspected") is not False
        or observation.get(
            "final_replacement_identities_selected_before_case_specific_candidate_inspection"
        )
        is not True
    ):
        raise HeldOutProfileRegistryError(
            "held_out_pre_freeze_observation_boundary_invalid"
        )


def _validate_zero_call_boundary(boundary: Mapping[str, Any]) -> None:
    required_zero = {
        "network",
        "provider",
        "model",
        "retrieval",
        "embedding",
        "rerank",
        "evidence_promotion",
    }
    if any(int(boundary.get(key, -1)) != 0 for key in required_zero):
        raise HeldOutProfileRegistryError("held_out_zero_call_boundary_invalid")
    if boundary.get("core_modification_allowed") is not False:
        raise HeldOutProfileRegistryError("held_out_core_modification_boundary_invalid")
    if boundary.get("candidate_inspection_before_freeze_allowed") is not False:
        raise HeldOutProfileRegistryError(
            "held_out_candidate_inspection_boundary_invalid"
        )


def _validate_locked_artifacts(
    policy: HeldOutProfileSelectionPolicy,
    *,
    repo_root: Path,
) -> None:
    identities = tuple(row.artifact_id for row in policy.locked_artifacts)
    if len(identities) < 4 or len(identities) != len(set(identities)):
        raise HeldOutProfileRegistryError("held_out_locked_artifact_identity_invalid")
    expected = {
        row.artifact_id: row.normalized_sha256 for row in policy.locked_artifacts
    }
    if _locked_digest_map(policy, repo_root=repo_root) != expected:
        raise HeldOutProfileRegistryError("held_out_locked_artifact_digest_mismatch")


def _locked_digest_map(
    policy: HeldOutProfileSelectionPolicy,
    *,
    repo_root: Path,
) -> dict[str, str]:
    return {
        row.artifact_id: normalized_sha256(_resolve(repo_root, row.path))
        for row in policy.locked_artifacts
    }


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


__all__ = [
    "HELD_OUT_PROFILE_POLICY_SCHEMA",
    "HELD_OUT_PROFILE_RESULT_SCHEMA",
    "HELD_OUT_PROFILE_RUN_SCOPE",
    "HeldOutProfileRegistryError",
    "HeldOutProfileSelectionPolicy",
    "execute_held_out_profile_selection",
    "load_held_out_profile_selection_policy",
]
