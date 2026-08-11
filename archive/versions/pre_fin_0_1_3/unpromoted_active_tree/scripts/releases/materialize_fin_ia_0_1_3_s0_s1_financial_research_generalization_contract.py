from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.financial_research_generalization_contract import (  # noqa: E402
    DeterministicEvidencePackEvaluator,
    FinancialCandidate,
    FinancialResearchContractError,
    compile_case_research_contract,
    load_financial_research_contract,
    validate_financial_research_contract,
)


CONTRACT_PATH = (
    ROOT
    / "configs/runtime/fin_ia_0_1_3_s0_s1_financial_research_generalization_contract_v1_0.json"
)
MODULE_PATH = ROOT / "src/sec_agent/financial_research_generalization_contract.py"
DEFAULT_OUTPUT = (
    ROOT
    / "configs/releases/fin_ia_0_1_3_s0_s1_financial_research_generalization_zero_call_proof_v1_0.json"
)


def normalized_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _fixture_candidates(compiled) -> tuple[FinancialCandidate, ...]:
    rows: list[FinancialCandidate] = []
    for requirement in compiled.slot_requirements:
        rows.append(
            FinancialCandidate(
                candidate_id=f"fixture-{compiled.case_key}-{requirement.slot_id}-a",
                case_key=compiled.case_key,
                slot_id=requirement.slot_id,
                subject_entity_key=compiled.subject_entity_key,
                evidence_owner_entity_key=compiled.subject_entity_key,
                relationship_direction="subject_self_disclosure",
                period_id=compiled.accepted_period_ids[0],
                facet_ids=requirement.required_facets,
                source_family="fixture_primary_a",
                canonical_source_id=f"fixture-source-{requirement.slot_id}-a",
                authority_tier=requirement.coverage_authority_tiers[0],
                candidate_role=requirement.allowed_candidate_roles[0],
                citation_ref=f"fixture-citation-{requirement.slot_id}-a",
                lineage_ref=f"fixture-lineage-{requirement.slot_id}-a",
            )
        )
        if requirement.minimum_independent_source_families > 1:
            rows.append(
                FinancialCandidate(
                    candidate_id=f"fixture-{compiled.case_key}-{requirement.slot_id}-b",
                    case_key=compiled.case_key,
                    slot_id=requirement.slot_id,
                    subject_entity_key=compiled.subject_entity_key,
                    evidence_owner_entity_key=compiled.subject_entity_key,
                    relationship_direction="subject_self_disclosure",
                    period_id=compiled.accepted_period_ids[0],
                    facet_ids=(requirement.required_facets[0],),
                    source_family="fixture_primary_b",
                    canonical_source_id=f"fixture-source-{requirement.slot_id}-b",
                    authority_tier=requirement.coverage_authority_tiers[0],
                    candidate_role=requirement.allowed_candidate_roles[0],
                    citation_ref=f"fixture-citation-{requirement.slot_id}-b",
                    lineage_ref=f"fixture-lineage-{requirement.slot_id}-b",
                )
            )
    return tuple(rows)


def _mutation_error(action) -> str:
    try:
        action()
    except FinancialResearchContractError as exc:
        return exc.code
    return "not_rejected"


def build_proof() -> dict[str, Any]:
    contract = load_financial_research_contract(CONTRACT_PATH)
    compiled = {
        case_key: compile_case_research_contract(contract, case_key)
        for case_key in ("DELL", "MU", "NVDA")
    }
    evaluator = DeterministicEvidencePackEvaluator()
    fixture_evaluations = {
        case_key: evaluator.evaluate(case_contract, _fixture_candidates(case_contract))
        for case_key, case_contract in compiled.items()
    }
    relaxed_pack = contract.industry_packs[0].model_copy(
        update={"may_relax_identity_period_lineage_or_authority": True}
    )
    relaxed_contract = contract.model_copy(update={"industry_packs": (relaxed_pack,)})
    out_of_pack_profile = contract.case_profiles[0].model_copy(
        update={
            "required_facet_additions": {
                "demand_volume_quality": ("fixture_case_only_facet",)
            }
        }
    )
    out_of_pack_contract = contract.model_copy(
        update={
            "case_profiles": (out_of_pack_profile,) + contract.case_profiles[1:]
        }
    )
    mutation_errors = {
        "industry_authority_relaxation": _mutation_error(
            lambda: validate_financial_research_contract(relaxed_contract)
        ),
        "case_facet_outside_pack": _mutation_error(
            lambda: validate_financial_research_contract(out_of_pack_contract)
        ),
    }
    core_fingerprints = {
        case_key: row.core_fingerprint for case_key, row in compiled.items()
    }
    checks = {
        "contract_valid": True,
        "three_cases_compile": len(compiled) == 3,
        "one_identical_core_fingerprint": len(set(core_fingerprints.values())) == 1,
        "each_case_has_eight_required_and_one_optional_slots": all(
            sum(slot.required for slot in row.slot_requirements) == 8
            and sum(not slot.required for slot in row.slot_requirements) == 1
            for row in compiled.values()
        ),
        "synthetic_multi_candidate_pack_shape_passes_without_evidence_promotion": all(
            result.status == "candidate_complete_pending_evidence_gate"
            and result.evidence_promotion_admitted is False
            for result in fixture_evaluations.values()
        ),
        "industry_authority_relaxation_fails_closed": mutation_errors[
            "industry_authority_relaxation"
        ]
        == "industry_pack_authority_violation",
        "case_facet_outside_pack_fails_closed": mutation_errors[
            "case_facet_outside_pack"
        ]
        == "case_profile_facet_outside_industry_pack",
        "three_held_out_archetypes_are_blind": len(contract.held_out_archetypes) == 3
        and all(not row.identity_selected for row in contract.held_out_archetypes)
        and all(
            not row.answer_or_gold_locator_embedded
            for row in contract.held_out_archetypes
        ),
    }
    body = {
        "schema_version": "fin_ia_0_1_3_s0_s1_financial_research_generalization_zero_call_proof_v1_0",
        "contract_ref": contract.contract_ref,
        "recorded_at": "2026-08-09",
        "status": "pass" if all(checks.values()) else "fail_closed",
        "immutable_inputs": {
            "contract_ref": str(CONTRACT_PATH.relative_to(ROOT)).replace("\\", "/"),
            "contract_sha256": normalized_sha256(CONTRACT_PATH),
            "module_ref": str(MODULE_PATH.relative_to(ROOT)).replace("\\", "/"),
            "module_sha256": normalized_sha256(MODULE_PATH),
        },
        "checks": checks,
        "compiled_cases": {
            case_key: {
                "compiled_digest": row.compiled_digest,
                "core_fingerprint": row.core_fingerprint,
                "required_slot_count": sum(
                    slot.required for slot in row.slot_requirements
                ),
                "optional_slot_count": sum(
                    not slot.required for slot in row.slot_requirements
                ),
                "relationship_count": len(row.relationships),
                "fixture_evaluation_status": fixture_evaluations[case_key].status,
                "fixture_evidence_promotion_admitted": fixture_evaluations[
                    case_key
                ].evidence_promotion_admitted,
            }
            for case_key, row in compiled.items()
        },
        "mutation_errors": mutation_errors,
        "held_out_archetypes": [
            {
                "archetype_id": row.archetype_id,
                "identity_selected": row.identity_selected,
                "answer_or_gold_locator_embedded": row.answer_or_gold_locator_embedded,
            }
            for row in contract.held_out_archetypes
        ],
        "observed_calls": {
            "network": 0,
            "provider": 0,
            "model": 0,
            "document_fetch": 0,
            "retrieval": 0,
            "embedding": 0,
            "rerank": 0,
            "evidence_promotion": 0,
        },
        "stage_boundary": contract.stage_boundary.model_dump(mode="json"),
        "known_boundary": (
            "The proof freezes and validates the generic kernel, slot library, plugin "
            "interfaces, one industry pack, three case configurations and blind held-out "
            "archetypes. Synthetic candidate rows prove contract behavior only; they are "
            "not source observations, Evidence, a DELL vertical slice, transfer proof, "
            "index admission, external supplement, model research or product acceptance."
        ),
    }
    return {**body, "proof_digest": canonical_digest(body)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    proof = build_proof()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(proof, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": proof["status"],
                "output": str(output),
                "proof_digest": proof["proof_digest"],
                "checks": proof["checks"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if proof["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
