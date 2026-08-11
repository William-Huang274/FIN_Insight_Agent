from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest
from sec_agent.s2_context_yield_program import (
    S2ContextYieldError,
    compile_context_yield_program,
    compile_role_scoped_context,
    load_context_yield_policy,
    validate_compact_provider_output,
    validate_context_yield_program,
)


ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "configs" / "runtime" / (
    "fin_ia_0_1_3_repair_closeout_s2_03_context_yield_policy_v1_0.json"
)
S2_DECISION = ROOT / "configs" / "releases" / (
    "fin_ia_0_1_3_repair_closeout_s2_01_"
    "research_question_method_contract_translation_v1_0.json"
)
S2_NATURAL_RESULT = ROOT / "configs" / "releases" / (
    "fin_ia_0_1_3_repair_closeout_s2_02_"
    "three_family_natural_canary_result_v1_0.json"
)
PROGRAM = ROOT / "configs" / "releases" / (
    "fin_ia_0_1_3_repair_closeout_s2_03_"
    "context_yield_and_capacity_zero_call_v1_0.json"
)
ACTIVE = ROOT / "configs" / "releases" / (
    "fin_ia_0_1_3_repair_closeout_s2_03_active_test_suite_successor_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _inputs() -> tuple[dict, dict, dict]:
    return load_context_yield_policy(POLICY), _load(S2_DECISION), _load(S2_NATURAL_RESULT)


def _program() -> dict:
    policy, decision, natural = _inputs()
    return compile_context_yield_program(
        policy=policy,
        s2_decision=decision,
        natural_result=natural,
    )


def test_context_yield_program_is_deterministic_and_capacity_bounded() -> None:
    first = _program()
    second = _program()

    assert first == second
    assert len(first["role_scoped_contexts"]) == 9
    assert first["capacity"]["aggregate_character_reduction_ratio"] >= 0.25
    assert first["capacity"]["aggregate_compact_to_baseline_character_ratio"] <= 0.70
    assert all(
        row["capacity"]["compact_to_baseline_character_ratio"] <= 0.75
        for row in first["role_scoped_contexts"]
    )
    assert first["semantic_retention"] == {
        "evidence_aliases_retained": 26,
        "gap_aliases_retained": 2,
        "mechanism_aliases_retained": 18,
        "what_would_change_aliases_retained": 18,
        "evidence_alias_retention_ratio": 1.0,
        "gap_alias_retention_ratio": 1.0,
        "mechanism_alias_retention_ratio": 1.0,
        "what_would_change_alias_retention_ratio": 1.0,
        "counterevidence_and_gap_hidden_for_capacity": False,
        "candidate_ids_digests_and_slot_ids_model_visible": False,
        "full_lineage_retained_in_local_sidecar": True,
    }


def test_model_context_removes_local_governance_but_sidecar_keeps_lineage() -> None:
    program = _program()
    forbidden = (
        "candidate_id",
        "candidate_digest",
        "slot_id",
        "gap_code",
        "request_digest",
        "s1_query_digest",
    )
    for row in program["role_scoped_contexts"]:
        model_text = json.dumps(row["model_context"], ensure_ascii=False)
        assert all(value not in model_text for value in forbidden)
        sidecar = row["local_authority_sidecar"]
        assert sidecar["request_digest"]
        assert sidecar["s1_query_digest"]
        assert (
            sidecar["evidence_alias_authority"]
            or sidecar["gap_alias_authority"]
        )
        if sidecar["evidence_alias_authority"]:
            assert any(
                authority.get("candidate_id")
                for authority in sidecar["evidence_alias_authority"].values()
            )


def test_all_optional_evidence_semantics_and_natural_outputs_survive_projection() -> None:
    policy, decision, natural = _inputs()
    program = compile_context_yield_program(
        policy=policy,
        s2_decision=decision,
        natural_result=natural,
    )
    request_map = {
        row["request_id"]: row
        for row in decision["research_question_method_program"]["representative_requests"]
    }
    context_map = {row["request_id"]: row for row in program["role_scoped_contexts"]}

    assert program["natural_output_compatibility"][
        "S2_02_actual_outputs_revalidated_against_compact_contract"
    ] == 3
    for result in natural["family_results"]:
        validate_compact_provider_output(
            result["provider_output"],
            compiled=context_map[result["request_id"]],
        )
    for request_id, request in request_map.items():
        expected = {
            row["alias"]: {
                key: value
                for key, value in {
                    "metric_family": row.get("metric_family"),
                    "edge_type": row.get("edge_type"),
                    "target_entity": row.get("target_entity_id"),
                }.items()
                if value is not None
            }
            for row in request["model_visible_request"]["evidence_aliases"]
        }
        actual = {
            row["alias"]: {
                key: value
                for key, value in row.items()
                if key in {"metric_family", "edge_type", "target_entity"}
            }
            for row in context_map[request_id]["model_context"]["evidence_options"]
        }
        assert actual == expected


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("evidence_loss", "s2_context_yield_alias_loss"),
        ("gap_semantic_loss", "s2_context_yield_gap_semantic_loss"),
        ("evidence_semantic_loss", "s2_context_yield_evidence_semantic_loss"),
        ("local_field_leak", "s2_context_yield_local_field_leak"),
        ("sidecar_digest_drift", "s2_context_yield_local_lineage_loss"),
    ],
)
def test_context_projection_mutations_fail_closed(mutation: str, expected_code: str) -> None:
    _, decision, _ = _inputs()
    request = decision["research_question_method_program"]["representative_requests"][0]
    broken = compile_role_scoped_context(request)
    if mutation == "evidence_loss":
        broken["model_context"]["evidence_options"].pop()
    elif mutation == "gap_semantic_loss":
        request = next(
            row
            for row in decision["research_question_method_program"]["representative_requests"]
            if row["model_visible_request"]["gap_aliases"]
        )
        broken = compile_role_scoped_context(request)
        broken["model_context"]["gap_options"][0]["cannot_infer"] = "mutated"
    elif mutation == "evidence_semantic_loss":
        broken["model_context"]["evidence_options"][0]["claim_boundary"] = "mutated"
    elif mutation == "local_field_leak":
        broken["model_context"]["candidate_id"] = "forbidden"
    else:
        broken["local_authority_sidecar"]["request_digest"] = "0" * 64
    body = {
        key: value for key, value in broken.items() if key != "context_digest"
    }
    broken["context_digest"] = canonical_digest(body)

    policy, _, natural = _inputs()
    program = _program()
    index = next(
        i
        for i, row in enumerate(program["role_scoped_contexts"])
        if row["request_id"] == request["request_id"]
    )
    broken["capacity"] = program["role_scoped_contexts"][index]["capacity"]
    program["role_scoped_contexts"][index] = broken
    program_body = {key: value for key, value in program.items() if key != "program_digest"}
    program["program_digest"] = canonical_digest(program_body)
    with pytest.raises(S2ContextYieldError) as exc:
        validate_context_yield_program(
            program,
            policy=policy,
            s2_decision=decision,
            natural_result=natural,
        )
    assert exc.value.code == expected_code


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("unknown_alias", "s2_compact_output_alias_invalid"),
        ("cross_case_alias", "s2_compact_output_alias_invalid"),
        ("free_text", "s2_compact_output_shape_invalid"),
        ("cannot_infer_support", "s2_compact_output_cannot_infer_support"),
    ],
)
def test_compact_output_mutations_fail_closed(mutation: str, expected_code: str) -> None:
    _, decision, _ = _inputs()
    research = decision["research_question_method_program"]
    request = research["representative_requests"][0]
    compiled = compile_role_scoped_context(request)
    output = deepcopy(research["fake_provider_outputs"][0]["provider_output"])
    if mutation == "unknown_alias":
        output["support_aliases"] = ["UNKNOWN"]
    elif mutation == "cross_case_alias":
        output["support_aliases"] = ["MU_E_FIN_01"]
    elif mutation == "free_text":
        output["explanation"] = "not allowed"
    else:
        output["epistemic_state"] = "cannot_infer"
        output["support_aliases"] = [
            compiled["model_context"]["evidence_options"][0]["alias"]
        ]
    with pytest.raises(S2ContextYieldError) as exc:
        validate_compact_provider_output(output, compiled=compiled)
    assert exc.value.code == expected_code


def test_materialized_program_is_digest_bound_and_stops_before_full_chain() -> None:
    policy, decision, natural = _inputs()
    materialized = _load(PROGRAM)
    validate_context_yield_program(
        materialized,
        policy=policy,
        s2_decision=decision,
        natural_result=natural,
    )
    assert materialized["stage_boundary"]["S2_03_zero_call"] == "engineering_pass"
    assert materialized["stage_boundary"]["S2_03_natural_reproof"] == "required_not_run"
    assert materialized["stage_boundary"]["full_chain_authorized"] is False
    assert materialized["natural_output_compatibility"]["compact_bytes_seen_by_model"] is False

    active = _load(ACTIVE)
    active_body = {key: value for key, value in active.items() if key != "suite_digest"}
    assert active["suite_digest"] == canonical_digest(active_body)
    assert active["decision_sha256"] == hashlib.sha256(PROGRAM.read_bytes()).hexdigest()
    assert active["observed_result"] == "191 passed / 1 historical event-time assertion deselected"


def test_capacity_threshold_mutation_fails_closed() -> None:
    policy, decision, natural = _inputs()
    program = _program()
    program["capacity"]["aggregate_compact_to_baseline_character_ratio"] = 0.71
    program["capacity"]["aggregate_character_reduction_ratio"] = 0.29
    body = {key: value for key, value in program.items() if key != "program_digest"}
    program["program_digest"] = canonical_digest(body)

    with pytest.raises(S2ContextYieldError) as exc:
        validate_context_yield_program(
            program,
            policy=policy,
            s2_decision=decision,
            natural_result=natural,
        )
    assert exc.value.code == "s2_context_yield_capacity_gate_failed"
