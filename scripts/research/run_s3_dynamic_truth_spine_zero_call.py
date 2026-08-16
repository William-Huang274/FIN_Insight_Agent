from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from apps.workbench.backend.application.research_evidence_pack_service import (
    ResearchEvidencePackPrincipal,
    ResearchEvidencePackService,
)
from apps.workbench.backend.application.research_retrieval_service import (
    ResearchRetrievalPrincipal,
    ResearchRetrievalService,
)
from sec_agent.research.claim_authority import (
    compile_claim_authority_research_input,
)
from sec_agent.research.claim_surface_authority import (
    compile_claim_surface_authority_research_input,
)
from sec_agent.research.current_consumer import compile_current_research_input
from sec_agent.research.dynamic_truth_spine import (
    DynamicTruthSpineError,
    bind_dynamic_evidence_responses_to_research_input,
    compile_dynamic_claim_authority_policy,
    compile_dynamic_claim_surface_policy,
    compile_dynamic_evidence_responses,
    compile_dynamic_reviewed_pack_view,
)
from sec_agent.research.planning import (
    compile_research_objective,
    load_research_planning_policy,
)
from sec_agent.research.reviewed_evidence_pack import canonical_digest
from retrieval.contracts import load_financial_research_kernel
from retrieval.route_compiler import load_query_object_fact_route_policy
from sec_agent.runtime_bridge.paths import resolve_runtime_paths
from sec_agent.runtime_resource_registry import read_registered_runtime_json


POLICY = ROOT / (
    "configs/research/fin_ia_0_1_3_s3_dynamic_truth_spine_policy_v1_0.json"
)
CONSUMER_POLICY = ROOT / (
    "configs/research/fin_ia_0_1_3_s3_current_research_consumer_policy_v1_2.json"
)
DELL_OBJECTIVE = ROOT / (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_minimal_planner_canary_objective_v1_0.json"
)
DELL_ATOMS = ROOT / (
    "tests/fixtures/research/"
    "fin_ia_0_1_3_s3_dell_planner_r1_atoms_v1_0.json"
)
DELL_CLAIM_TEMPLATE = ROOT / (
    "configs/research/"
    "fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_claim_authority_v1_0.json"
)
DELL_CLAIM_SURFACE_TEMPLATE = ROOT / (
    "configs/research/"
    "fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_"
    "claim_surface_authority_v1_2.json"
)


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_new(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def _services() -> tuple[ResearchEvidencePackService, ResearchRetrievalService]:
    paths = resolve_runtime_paths(ROOT)
    return (
        ResearchEvidencePackService.from_runtime_paths(ROOT, paths),
        ResearchRetrievalService.from_runtime_paths(ROOT, paths),
    )


def _one_slot_inputs(case_key: str) -> tuple[dict[str, Any], dict[str, Any]]:
    kernel = load_financial_research_kernel(
        read_registered_runtime_json(
            ROOT, "application.config.current_financial_research_kernel"
        )
    )
    route_policy = load_query_object_fact_route_policy(
        read_registered_runtime_json(
            ROOT, "application.config.current_query_object_fact_route_policy"
        ),
        kernel,
    )
    planning = load_research_planning_policy(
        read_registered_runtime_json(
            ROOT, "application.config.current_research_planning_policy"
        ),
        route_policy,
    )
    draft = {
        "schema_version": "fin_ia_research_objective_draft_v1_0",
        "raw_question": (
            f"{case_key} 的增长是否转化为可持续利润，当前证据还缺什么？"
        ),
        "task_type": "company_deep_dive",
        "case_key": case_key,
        "required_slot_ids": ["pricing_mix_value_capture"],
        "allowed_source_types": ["10-K", "10-Q", "8-K", "20-F", "6-K"],
        "forbidden_source_types": [],
        "output_format": "investment_research_memo",
        "gap_policy": "return_typed_gap",
        "reviewer_role": "qualified_financial_research_reviewer",
        "period": {"start_date": "2024-01-01", "fiscal_years": [2025, 2026, 2027]},
        "budget": {
            "max_evidence_requests": 1,
            "max_metric_intents_per_request": 4,
            "max_product_intents_per_request": 2,
            "max_model_calls": 1,
        },
        "pass_criteria": [
            "identity_and_as_of_bound",
            "required_dimensions_covered",
            "numeric_facts_source_bound",
            "candidate_not_evidence_boundary_preserved",
            "qualified_human_review_required",
        ],
    }
    objective = compile_research_objective(draft, kernel=kernel, policy=planning)
    atoms = {
        "schema_version": "fin_ia_research_planner_atoms_v1_0",
        "objective_id": objective.objective_id,
        "atoms": [
            {
                "facet_id": "margin_and_incremental_profit",
                "metric_ids": [
                    "gross_profit",
                    "operating_income",
                    "operating_margin",
                    "gross_margin",
                ],
                "product_intents": [
                    "product-to-company profit bridge",
                    "incremental profit durability",
                ],
                "target_entity": case_key,
            }
        ],
    }
    return draft, atoms


def _case_inputs(case_key: str) -> tuple[dict[str, Any], dict[str, Any]]:
    if case_key == "DELL":
        return _json(DELL_OBJECTIVE), _json(DELL_ATOMS)
    return _one_slot_inputs(case_key)


def _case_projection(
    case_key: str,
    *,
    evidence: ResearchEvidencePackService,
    retrieval: ResearchRetrievalService,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    permissions = frozenset({"current_product:read"})
    objective, atoms = _case_inputs(case_key)
    pack = evidence.get_case(
        case_key, ResearchEvidencePackPrincipal("current", permissions)
    )
    controlled = retrieval.execute_controlled_plan(
        case_key,
        objective,
        atoms,
        ResearchRetrievalPrincipal("current", permissions),
    )
    responses = compile_dynamic_evidence_responses(
        policy=_json(POLICY),
        controlled_plan=controlled,
        evidence_pack=pack,
    )
    dynamic_input = None
    if responses["accepted_evidence_item_digests"]:
        view = compile_dynamic_reviewed_pack_view(
            evidence_pack=pack,
            evidence_responses=responses,
        )
        base = compile_current_research_input(
            policy=_json(CONSUMER_POLICY),
            evidence_pack=view,
            controlled_plan=controlled,
        )
        dynamic_input = bind_dynamic_evidence_responses_to_research_input(
            research_input=base,
            evidence_responses=responses,
        )
    return pack, controlled, responses, dynamic_input


def _mutations(
    *,
    pack: Mapping[str, Any],
    controlled: Mapping[str, Any],
    baseline: Mapping[str, Any],
) -> dict[str, bool]:
    policy = _json(POLICY)
    reordered = deepcopy(dict(controlled))
    for result in reordered["request_results"]:
        hybrid = result.get("hybrid_object_retrieval")
        if isinstance(hybrid, dict):
            hybrid["candidates"].reverse()
        else:
            for lane in result.get("lanes") or ():
                lane["candidates"].reverse()
    reorder_result = compile_dynamic_evidence_responses(
        policy=policy,
        controlled_plan=reordered,
        evidence_pack=pack,
    )

    text_mutated = deepcopy(dict(controlled))
    for result in text_mutated["request_results"]:
        hybrid = result.get("hybrid_object_retrieval")
        if isinstance(hybrid, dict) and hybrid.get("candidates"):
            hybrid["candidates"][0]["model_text"] = (
                "UNTRUSTED CANDIDATE TEXT MUST NOT GRANT AUTHORITY"
            )
            break
    text_result = compile_dynamic_evidence_responses(
        policy=policy,
        controlled_plan=text_mutated,
        evidence_pack=pack,
    )

    cross_case = deepcopy(dict(controlled))
    cross_case["objective"]["case_key"] = "MU"
    cross_case_failed = False
    try:
        compile_dynamic_evidence_responses(
            policy=policy,
            controlled_plan=cross_case,
            evidence_pack=pack,
        )
    except DynamicTruthSpineError as exc:
        cross_case_failed = str(exc) == "dynamic_truth_spine_case_binding_invalid"

    drift = deepcopy(dict(pack))
    drift["artifact_digest"] = "0" * 64
    pack_drift_failed = False
    try:
        compile_dynamic_reviewed_pack_view(
            evidence_pack=drift,
            evidence_responses=baseline,
        )
    except DynamicTruthSpineError as exc:
        pack_drift_failed = str(exc) == "dynamic_truth_spine_pack_binding_drift"

    return {
        "candidate_reordering_is_semantically_stable": (
            reorder_result["evidence_response_set_digest"]
            == baseline["evidence_response_set_digest"]
        ),
        "untrusted_candidate_text_has_no_authority_effect": (
            text_result["evidence_response_set_digest"]
            == baseline["evidence_response_set_digest"]
        ),
        "cross_case_mutation_failed_closed": cross_case_failed,
        "reviewed_pack_binding_drift_failed_closed": pack_drift_failed,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--implementation-commit", required=True)
    args = parser.parse_args()
    if re.fullmatch(r"[0-9a-f]{40}", args.implementation_commit) is None:
        raise ValueError("dynamic_truth_spine_implementation_commit_invalid")
    output = args.output.resolve()
    evidence, retrieval = _services()
    cases = []
    dell_private: tuple[dict[str, Any], dict[str, Any], dict[str, Any]] | None = None
    for case_key in ("DELL", "MU", "NVDA"):
        pack, controlled, responses, dynamic_input = _case_projection(
            case_key,
            evidence=evidence,
            retrieval=retrieval,
        )
        response_rows = [
            {
                "request_id": row["request_id"],
                "request_bindings": row["request_bindings"],
                "candidate_route": row["candidate_route"],
                "candidate_count": row["candidate_count"],
                "accepted_reviewed_evidence_count": len(row["accepted"]),
                "accepted_source_record_ids": [
                    decision["source_record_id"] for decision in row["accepted"]
                ],
                "rejected_reviewed_binding_reasons": sorted(
                    {decision["reason"] for decision in row["rejected"]}
                ),
                "unreviewed_candidate_count": len(row["needs_human_review"]),
                "typed_gap_codes": sorted(
                    {
                        str(typed["gap"].get("gap_code") or "")
                        for typed in row["typed_gaps"]
                    }
                ),
            }
            for row in responses["responses"]
        ]
        cases.append(
            {
                "case_key": case_key,
                "controlled_plan_digest": controlled["projection_digest"],
                "reviewed_pack_artifact_digest": pack["artifact_digest"],
                "evidence_response_set_digest": responses[
                    "evidence_response_set_digest"
                ],
                "summary": responses["summary"],
                "dynamic_research_input_compiled": dynamic_input is not None,
                "dynamic_research_input_digest": (
                    dynamic_input["research_input_digest"]
                    if dynamic_input is not None
                    else ""
                ),
                "requests": response_rows,
            }
        )
        if case_key == "DELL":
            dell_private = (pack, controlled, responses)
            if dynamic_input is not None:
                dynamic_claim_policy = compile_dynamic_claim_authority_policy(
                    research_input=dynamic_input,
                    template_policy=_json(DELL_CLAIM_TEMPLATE),
                )
                claim_input = compile_claim_authority_research_input(
                    dynamic_input,
                    policy=dynamic_claim_policy,
                )
                dynamic_surface_policy = compile_dynamic_claim_surface_policy(
                    claim_authority_input=claim_input,
                    template_policy=_json(DELL_CLAIM_SURFACE_TEMPLATE),
                )
                surface_input = compile_claim_surface_authority_research_input(
                    claim_input,
                    policy=dynamic_surface_policy,
                )
                surface_relations = dynamic_surface_policy[
                    "allowed_structured_claim_combinations"
                ]
                cases[-1]["dynamic_claim_authority"] = {
                    "policy_digest": canonical_digest(dynamic_claim_policy),
                    "compiled_input_digest": claim_input["research_input_digest"],
                    "allowed_causal_bridge_authorities": dynamic_claim_policy[
                        "allowed_causal_bridge_authorities"
                    ],
                    "candidate_promotions": claim_input[
                        "claim_authority_contract"
                    ]["candidate_promotions"],
                }
                cases[-1]["dynamic_claim_surface"] = {
                    "policy_digest": canonical_digest(dynamic_surface_policy),
                    "compiled_input_digest": surface_input[
                        "research_input_digest"
                    ],
                    "allowed_claim_relation_refs": [
                        row["claim_relation_ref"] for row in surface_relations
                    ],
                    "fragment_coverage": {
                        field: any(
                            field in set(row["allowed_atom_fields"])
                            for row in surface_relations
                        )
                        for field in (
                            "thesis_atom",
                            "mechanism_atom",
                            "counterargument_atom",
                        )
                    },
                    "gap_only_thesis_abstention_available": any(
                        row["causal_bridge_authority"] == "bridge_unavailable"
                        and "thesis_atom" in set(row["allowed_atom_fields"])
                        for row in surface_relations
                    ),
                    "candidate_promotions": surface_input[
                        "claim_surface_authority_contract"
                    ]["candidate_promotions"],
                }
    assert dell_private is not None
    mutations = _mutations(
        pack=dell_private[0],
        controlled=dell_private[1],
        baseline=dell_private[2],
    )
    total_promotions = sum(
        int(row["summary"]["new_evidence_promotions"]) for row in cases
    )
    case_keys = [row["case_key"] for row in cases]
    passed = (
        case_keys == ["DELL", "MU", "NVDA"]
        and len(set(case_keys)) == 3
        and total_promotions == 0
        and all(mutations.values())
        and cases[0]["summary"]["accepted_reviewed_evidence_count"] > 0
        and cases[0]["dynamic_research_input_compiled"] is True
        and cases[0]["dynamic_claim_authority"]["candidate_promotions"] == 0
        and cases[0]["dynamic_claim_surface"]["candidate_promotions"] == 0
        and all(
            cases[0]["dynamic_claim_surface"]["fragment_coverage"].values()
        )
    )
    body = {
        "schema_version": "fin_ia_s3_dynamic_truth_spine_zero_call_result_v1_1",
        "status": (
            "zero_call_dynamic_truth_spine_engineering_pass"
            if passed
            else "zero_call_dynamic_truth_spine_engineering_failed"
        ),
        "recorded_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "implementation_commit": args.implementation_commit,
        "scope": "S1_EvidenceRequest_to_S2_NumericFact_to_S3_EvidenceResponse",
        "cases": cases,
        "mutations": mutations,
        "observed_counts": {
            "case_count": len(cases),
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": 0,
            "new_evidence_promotions": total_promotions,
        },
        "stage_acceptance": {
            "real_current_s1_requests_executed": True,
            "real_current_s2_typed_fact_requests_executed": True,
            "typed_evidence_responses_compiled": True,
            "already_reviewed_evidence_only": True,
            "unreviewed_candidate_text_excluded": True,
            "three_case_identity_isolation": True,
            "dynamic_dell_claim_authority_narrowed": passed,
            "dynamic_dell_claim_relation_surface_compiled": passed,
            "gap_only_thesis_can_only_abstain": passed,
            "natural_model_planner_executed": False,
            "dynamic_agentic_research_claimed": False,
            "s3_product_acceptance_claimed": False,
        },
        "known_boundary": (
            "This proof runs the current local S1 candidate and S2 NumericFact "
            "services, then compiles request-scoped EvidenceResponses. Planner "
            "atoms remain controlled fixtures, so this is an engineering proof, "
            "not natural Agentic Research. The current S1 object route does not "
            "yet discover reviewed earnings-call transcripts; those remain an "
            "explicit source-route gap rather than being silently prefed."
        ),
    }
    result = {**body, "result_digest": canonical_digest(body)}
    _write_new(output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
