from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.project_os_preflight import run_project_os_preflight  # noqa: E402
from sec_agent.s1_08_candidate_generation_runtime import (  # noqa: E402
    load_source_catalog,
)
from sec_agent.s1_08_query_facet_plan import (  # noqa: E402
    ModelQueryAtomCandidate,
    compile_query_facet_plans,
    load_query_facet_policy,
)
from sec_agent.s1_08_query_facet_three_way_evaluation import (  # noqa: E402
    S108QueryFacetThreeWayError,
    build_three_way_zero_call_evaluation,
    load_three_way_policy,
)
from sec_agent.s1_08_search_intent_compiler import (  # noqa: E402
    compile_search_intents,
    load_search_intent_policy,
)


POLICY_PATH = (
    ROOT
    / "configs/runtime/fin_ia_0_1_3_s1_08_query_facet_three_way_evaluation_policy_v1_0.json"
)
FACET_POLICY_PATH = (
    ROOT
    / "configs/runtime/fin_ia_0_1_3_s1_08_unified_query_facet_policy_v1_0.json"
)
PROOF_PATH = (
    ROOT
    / "configs/releases/fin_ia_0_1_3_s1_08_unified_query_facet_zero_call_proof_v1_0.json"
)
OUTPUT_PATH = (
    ROOT
    / "configs/releases/fin_ia_0_1_3_s1_08_query_facet_three_way_zero_call_proof_v1_0.json"
)
VISIBLE_PATH = (
    ROOT
    / "eval_sets/fin_0_1_3_same_evidence_v1/model_visible/shared_benchmark_evidence_pack_v1.json"
)
FIRECRAWL_RESULT_PATH = (
    ROOT
    / "configs/releases/fin_ia_0_1_3_s1_08_firecrawl_relationship_aware_semantic_control_result_v1_0.json"
)
FIRECRAWL_ASSESSMENT_PATH = (
    ROOT
    / "configs/releases/fin_ia_0_1_3_s1_08_firecrawl_relationship_aware_semantic_control_assessment_v1_0.json"
)
FIRECRAWL_SCORING_PATH = (
    ROOT
    / "configs/eval/fin_ia_0_1_3_s1_08_firecrawl_relationship_aware_semantic_control_scoring_v1_0.json"
)
CURRENT_SCOPE = "S1_08_QUERY_FACET_THREE_WAY_DELL_MU_NVDA_EVALUATION"
COMPLETED_SCOPE = "S1_08_UNIFIED_QUERY_FACET_PLAN_ZERO_CALL_IMPLEMENTATION"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalized_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


@pytest.fixture(scope="module")
def inputs() -> dict[str, dict]:
    return {
        "policy": load_three_way_policy(POLICY_PATH),
        "proof": _load(PROOF_PATH),
        "visible": _load(VISIBLE_PATH),
        "result": _load(FIRECRAWL_RESULT_PATH),
        "assessment": _load(FIRECRAWL_ASSESSMENT_PATH),
        "scoring": _load(FIRECRAWL_SCORING_PATH),
    }


def _evaluate(
    inputs: dict[str, dict],
    *,
    proof: dict | None = None,
    visible: dict | None = None,
    result: dict | None = None,
    assisted_plans: list[dict] | None = None,
) -> dict:
    return build_three_way_zero_call_evaluation(
        policy=inputs["policy"],
        query_facet_proof=proof or inputs["proof"],
        model_visible_case_pack=visible or inputs["visible"],
        firecrawl_result=result or inputs["result"],
        firecrawl_assessment=inputs["assessment"],
        firecrawl_scoring=inputs["scoring"],
        model_assisted_plans=assisted_plans,
        deterministic_permutation_stable=True,
    )


def _compiled_model_assisted_plans(inputs: dict[str, dict]) -> list[dict]:
    facet_policy = load_query_facet_policy(FACET_POLICY_PATH)
    bindings = facet_policy["immutable_inputs"]
    objectives = {
        str(row["case_key"]): str(row["research_objective"])
        for row in inputs["visible"]["cases"]
    }
    intents = compile_search_intents(
        catalog=load_source_catalog(ROOT / bindings["source_catalog_ref"]),
        policy=load_search_intent_policy(
            ROOT / bindings["search_intent_policy_ref"]
        ),
        research_objectives=objectives,
    )
    atom = ModelQueryAtomCandidate(
        case_key="DELL",
        evidence_slot_id="issuer_results_and_management_commentary",
        evidence_owner_entity_key="DELL",
        language="en",
        atom_kind="metric",
        value="remaining performance obligations",
    )
    return [
        row.as_dict()
        for row in compile_query_facet_plans(
            intents=intents,
            policy=facet_policy,
            model_atoms=(atom,),
        )
    ]


def test_policy_binds_all_replay_inputs_and_authorizes_no_calls(
    inputs: dict[str, dict],
) -> None:
    policy = inputs["policy"]
    bindings = policy["immutable_inputs"]
    for key, ref in bindings.items():
        if not key.endswith("_ref"):
            continue
        stem = key.removesuffix("_ref")
        assert _normalized_sha256(ROOT / ref) == bindings[f"{stem}_sha256"]
    assert not any(policy["calls_authorized_by_this_policy"].values())
    assert policy["replay_contract"][
        "historical_target_in_pool_may_be_attributed_to_new_variant"
    ] is False


def test_zero_call_A_B_evaluation_proves_local_structure_not_live_recall(
    inputs: dict[str, dict],
) -> None:
    evaluation = _evaluate(inputs)
    raw = evaluation["variant_summary"]["user_raw_query"]
    local = evaluation["variant_summary"]["deterministic_local_compiler"]
    model = evaluation["variant_summary"][
        "deepseek_query_atoms_plus_deterministic_local_compiler"
    ]
    assert evaluation["status"] == "zero_call_A_B_pass_model_atom_observation_pending"
    assert raw["mean_facet_coverage"] == 0.138889
    assert raw["duplicate_query_rate"] == 0.916667
    assert local["mean_facet_coverage"] == 1.0
    assert local["minimum_facet_coverage"] == 1.0
    assert local["contamination_count"] == 0
    assert local["duplicate_query_rate"] == 0.0
    assert model["status"] == "not_observed_no_natural_model_atoms"
    assert evaluation["quality_gates"]["fresh_provider_recall_proven"] is False


def test_target_route_opportunity_distinguishes_direct_and_canonical_reuse(
    inputs: dict[str, dict],
) -> None:
    opportunity = _evaluate(inputs)["target_route_opportunity"]
    assert opportunity["target_source_direct_opportunity"] == [9, 10]
    assert opportunity["slot_direct_opportunity"] == [6, 6]
    assert opportunity["global_document_owner_opportunity"] == [10, 10]
    assert opportunity["missing_direct_alternatives"] == [
        {
            "case_key": "MU",
            "evidence_slot_id": "customer_demand_and_deployment_validation",
            "source_id": "SRC_NVDA_Q1_FY27_10Q",
            "source_owner_entity_key": "NVDA",
        }
    ]


def test_local_query_saturates_frozen_english_addressability_proxy(
    inputs: dict[str, dict],
) -> None:
    proxy = _evaluate(inputs)["english_target_addressability_proxy"]
    assert proxy["variant_summary"]["user_raw_query"]["addressable"] == [0, 9]
    assert proxy["variant_summary"]["deterministic_local_compiler"][
        "addressable"
    ] == [9, 9]
    assert "not provider candidate generation" in proxy["proxy_definition"]


def test_historical_firecrawl_pool_is_preserved_without_variant_attribution(
    inputs: dict[str, dict],
) -> None:
    replay = _evaluate(inputs)["historical_capture_replay"]
    assert replay["query_pools"] == 24
    assert replay["unique_locators"] == 176
    assert replay["case_slot_target_in_pool"] == [5, 6]
    assert replay["credits_used"] == 48
    assert replay["attributable_to_user_raw_query"] is False
    assert replay["attributable_to_deterministic_local_compiler"] is False
    assert replay["attributable_to_model_atoms"] is False


def test_fixture_atoms_can_exercise_third_variant_but_cannot_prove_model_value(
    inputs: dict[str, dict],
) -> None:
    assisted = _compiled_model_assisted_plans(inputs)
    evaluation = _evaluate(inputs, assisted_plans=assisted)
    model = evaluation["variant_summary"][
        "deepseek_query_atoms_plus_deterministic_local_compiler"
    ]
    assert evaluation["status"] == "three_way_replay_proxy_complete"
    assert model["accepted_model_atom_count"] == 1
    assert model["contamination_count"] == 0
    assert evaluation["decision"]["deepseek_query_atoms"]["status"] == (
        "rejected_no_incremental_addressability_or_quality_regression"
    )
    assert evaluation["decision"]["deepseek_query_atoms"][
        "runtime_admitted"
    ] is False


def test_empty_natural_atom_result_is_observed_no_gain_and_authority_drift_fails(
    inputs: dict[str, dict],
) -> None:
    empty = deepcopy(inputs["proof"]["plans"])
    empty_result = _evaluate(inputs, assisted_plans=empty)
    assert empty_result["status"] == "three_way_replay_proxy_complete"
    assert empty_result["decision"]["deepseek_query_atoms"]["status"] == (
        "rejected_no_incremental_addressability_or_quality_regression"
    )
    assert empty_result["variant_summary"][
        "deepseek_query_atoms_plus_deterministic_local_compiler"
    ]["accepted_model_atom_count"] == 0

    drifted = _compiled_model_assisted_plans(inputs)
    drifted[0]["route_specific_filters"]["publication_date_on_or_before"] = (
        "2027-01-01"
    )
    with pytest.raises(S108QueryFacetThreeWayError) as exc_info:
        _evaluate(inputs, assisted_plans=drifted)
    assert exc_info.value.code == (
        "s1_08_query_facet_three_way_model_plan_authority_drift"
    )


def test_tampered_base_proof_or_incomplete_replay_fails_closed(
    inputs: dict[str, dict],
) -> None:
    proof = deepcopy(inputs["proof"])
    proof["plans"][0]["period_terms"] = ["Q4 FY2030"]
    with pytest.raises(S108QueryFacetThreeWayError) as exc_info:
        _evaluate(inputs, proof=proof)
    assert exc_info.value.code == "s1_08_query_facet_three_way_base_proof_invalid"

    result = deepcopy(inputs["result"])
    result["observed_counts"]["terminalized_queries"] = 23
    with pytest.raises(S108QueryFacetThreeWayError) as exc_info:
        _evaluate(inputs, result=result)
    assert exc_info.value.code == "s1_08_query_facet_three_way_replay_input_invalid"


def test_raw_query_leak_is_measured_not_silently_sanitized(
    inputs: dict[str, dict],
) -> None:
    visible = deepcopy(inputs["visible"])
    visible["cases"][0]["research_objective"] += (
        " https://example.com SRC_FAKE AKID12345678901234567890"
    )
    evaluation = _evaluate(inputs, visible=visible)
    raw = evaluation["variant_summary"]["user_raw_query"]
    assert raw["contamination_count"] > 0
    assert evaluation["quality_gates"]["raw_query_not_misrepresented_as_compiled"]
    assert evaluation["quality_gates"]["deterministic_local_structure_pass"]


def test_materialized_output_is_digest_bound_and_honest() -> None:
    output = _load(OUTPUT_PATH)
    body = dict(output)
    supplied = body.pop("evaluation_digest")
    assert supplied == canonical_digest(body)
    assert output["deterministic_recompilation"]["byte_equal"] is True
    assert output["implementation"]["natural_model_atoms_supplied"] == 0
    assert not any(output["observed_calls"].values())
    assert output["stage_acceptance"]["three_way_effectiveness_evaluation"] is False
    assert output["decision"]["combined_external_live_authorized"] is False


def test_policy_call_or_replay_authority_mutation_is_rejected(tmp_path: Path) -> None:
    policy = _load(POLICY_PATH)
    policy["calls_authorized_by_this_policy"]["model"] = 1
    target = tmp_path / "mutated_policy.json"
    target.write_text(json.dumps(policy), encoding="utf-8")
    with pytest.raises(S108QueryFacetThreeWayError) as exc_info:
        load_three_way_policy(target)
    assert exc_info.value.code == (
        "s1_08_query_facet_three_way_zero_call_boundary_invalid"
    )

    policy = _load(POLICY_PATH)
    policy["replay_contract"][
        "historical_target_in_pool_may_be_attributed_to_new_variant"
    ] = True
    target.write_text(json.dumps(policy), encoding="utf-8")
    with pytest.raises(S108QueryFacetThreeWayError) as exc_info:
        load_three_way_policy(target)
    assert exc_info.value.code == (
        "s1_08_query_facet_three_way_replay_boundary_invalid"
    )


def test_project_os_closes_three_way_zero_call_scope_after_clean_authority() -> None:
    completed = run_project_os_preflight(ROOT, run_scope=COMPLETED_SCOPE)
    assert completed["status"] == "blocked"
    assert completed["contract_errors"] == []
    prior = run_project_os_preflight(ROOT, run_scope=CURRENT_SCOPE)
    assert prior["status"] == "blocked"
    assert prior["contract_errors"] == []
