from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
for value in (REPO_ROOT, REPO_ROOT / "src"):
    if str(value) not in sys.path:
        sys.path.insert(0, str(value))

from sec_agent.prompt_metadata_contract import (  # noqa: E402
    PromptMetadataContractError,
    compact_prompt_metadata,
    prompt_metadata_type_policy,
    validate_prompt_metadata_types,
)
from sec_agent.retrieval_evidence_usefulness_program import canonical_digest  # noqa: E402
from sec_agent.s2_research_contract_program import (  # noqa: E402
    S2ResearchContractError,
    compile_s2_research_question_method_program,
    load_s2_research_contract_policy,
    validate_provider_judgment_choice,
    validate_s2_research_question_method_program,
)


POLICY_PATH = REPO_ROOT / "configs/runtime/fin_ia_0_1_3_repair_closeout_s2_research_question_method_contract_policy_v1_0.json"
S1_PATH = REPO_ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s1_05_retrieval_evidence_usefulness_and_s1_closeout_v1_0.json"
DECISION_PATH = REPO_ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s2_01_research_question_method_contract_translation_v1_0.json"
ACTIVE_PATH = REPO_ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s2_01_active_test_suite_successor_v1_0.json"


@lru_cache(maxsize=1)
def _inputs() -> tuple[dict, dict]:
    return (
        load_s2_research_contract_policy(POLICY_PATH),
        json.loads(S1_PATH.read_text(encoding="utf-8")),
    )


def _compile() -> tuple[dict, dict, dict]:
    policy, s1 = _inputs()
    program = compile_s2_research_question_method_program(
        policy=policy,
        s1_decision=s1,
    )
    return program, policy, s1


def _reseal_request_and_program(program: dict, request_index: int) -> None:
    request = program["representative_requests"][request_index]
    request["request_digest"] = canonical_digest(
        {key: value for key, value in request.items() if key != "request_digest"}
    )
    program["program_digest"] = canonical_digest(
        {key: value for key, value in program.items() if key != "program_digest"}
    )


def test_metadata_policy_preserves_native_integer_boolean_and_explicit_decimal_string() -> None:
    projected = compact_prompt_metadata(
        {
            "line_item_count": 10,
            "relationship_context_available": False,
            "required_slot_recall": Decimal("1.000"),
            "unregistered_numeric": 7,
        },
        max_items=8,
        text_limit=80,
    )
    assert projected["line_item_count"] == 10
    assert type(projected["line_item_count"]) is int
    assert projected["relationship_context_available"] is False
    assert projected["required_slot_recall"] == "1"
    assert "unregistered_numeric" not in projected
    assert projected["omitted_key_count"] == 1
    validate_prompt_metadata_types(projected)
    assert prompt_metadata_type_policy()["unknown_numeric_or_boolean_policy"] == (
        "omit_fail_closed"
    )


def test_metadata_type_mutations_fail_closed_without_stringifying_native_scalars() -> None:
    with pytest.raises(
        PromptMetadataContractError,
        match="prompt_metadata_integer_type_invalid:line_item_count",
    ):
        validate_prompt_metadata_types({"line_item_count": "10"})
    with pytest.raises(
        PromptMetadataContractError,
        match="prompt_metadata_boolean_type_invalid:relationship_context_available",
    ):
        validate_prompt_metadata_types({"relationship_context_available": 0})
    with pytest.raises(
        PromptMetadataContractError,
        match="prompt_metadata_decimal_string_invalid:required_slot_recall",
    ):
        validate_prompt_metadata_types({"required_slot_recall": 1.0})


def test_current_s1_pack_compiles_nine_company_specific_bounded_choice_requests() -> None:
    program, policy, s1 = _compile()
    validate_s2_research_question_method_program(
        program,
        policy=policy,
        s1_decision=s1,
    )
    assert program["observed_counts"] == {
        "case_count": 3,
        "representative_request_count": 9,
        "selected_candidate_alias_count": 26,
        "typed_gap_alias_count": 2,
        "company_specific_mechanism_choice_count": 18,
        "fake_provider_pass_count": 9,
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "source_calls": 0,
        "business_runs": 0,
    }
    requests = program["representative_requests"]
    assert {(row["case_key"], row["program_cell_id"]) for row in requests} == {
        (case_key, cell_id)
        for case_key in ("DELL", "MU", "NVDA")
        for cell_id in (
            "demand_authenticity_and_sustainability",
            "value_and_profit_capture",
            "bottleneck_counterevidence_and_what_would_change",
        )
    }
    assert all(
        type(row["model_visible_request"]["typed_metadata"]["line_item_count"])
        is int
        for row in requests
    )
    assert program["method_lifecycle"]["runtime_injected_into_representative_node"] is False
    assert program["stage_boundary"]["fixed_three_cells_are_final_product_plan"] is False


def test_provider_schema_fake_and_validator_share_alias_only_authority() -> None:
    program, _policy, _s1 = _compile()
    assert program["provider_contract"]["free_text_fields"] == []
    assert program["provider_contract"]["additional_properties"] is False
    for fake_row in program["fake_provider_outputs"]:
        request = next(
            row
            for row in program["representative_requests"]
            if row["request_id"] == fake_row["request_id"]
        )
        validate_provider_judgment_choice(
            fake_row["provider_output"],
            request=request,
        )

    request = program["representative_requests"][0]
    output = deepcopy(program["fake_provider_outputs"][0]["provider_output"])
    output["numeric_value"] = "113538000000"
    with pytest.raises(S2ResearchContractError, match="s2_provider_output_shape_invalid"):
        validate_provider_judgment_choice(output, request=request)
    output = deepcopy(program["fake_provider_outputs"][0]["provider_output"])
    output["mechanism_alias"] = "MU_M_HBM_DEMAND_WITH_CYCLE_BOUNDARY"
    with pytest.raises(S2ResearchContractError, match="s2_provider_mechanism_alias_invalid"):
        validate_provider_judgment_choice(output, request=request)


def test_cross_case_alias_typed_metadata_and_s1_authority_mutations_fail_closed() -> None:
    program, policy, s1 = _compile()
    mutated = deepcopy(program)
    mutated["representative_requests"][0]["model_visible_request"][
        "mechanism_aliases"
    ][0]["alias"] = "MU_M_CROSS_CASE"
    _reseal_request_and_program(mutated, 0)
    with pytest.raises(S2ResearchContractError, match="s2_cross_case_mechanism_alias"):
        validate_s2_research_question_method_program(
            mutated,
            policy=policy,
            s1_decision=s1,
        )

    mutated = deepcopy(program)
    mutated["representative_requests"][0]["model_visible_request"][
        "typed_metadata"
    ]["line_item_count"] = "2"
    _reseal_request_and_program(mutated, 0)
    with pytest.raises(PromptMetadataContractError, match="line_item_count"):
        validate_s2_research_question_method_program(
            mutated,
            policy=policy,
            s1_decision=s1,
        )

    stale_s1 = deepcopy(s1)
    stale_s1["retrieval_usefulness_program"]["stage_boundary"][
        "legacy_bm25_is_current_authority"
    ] = True
    stale_s1["record_digest"] = canonical_digest(
        {key: value for key, value in stale_s1.items() if key != "record_digest"}
    )
    with pytest.raises(S2ResearchContractError, match="s2_s1_authority_invalid"):
        compile_s2_research_question_method_program(
            policy=policy,
            s1_decision=stale_s1,
        )


def test_materialized_decision_and_active_suite_are_digest_bound_and_honest() -> None:
    decision = json.loads(DECISION_PATH.read_text(encoding="utf-8"))
    active = json.loads(ACTIVE_PATH.read_text(encoding="utf-8"))
    assert decision["record_digest"] == canonical_digest(
        {key: value for key, value in decision.items() if key != "record_digest"}
    )
    assert active["decision_sha256"] == hashlib.sha256(
        DECISION_PATH.read_bytes()
    ).hexdigest()
    assert active["suite_digest"] == canonical_digest(
        {key: value for key, value in active.items() if key != "suite_digest"}
    )
    assert decision["acceptance"]["S2_01"] == "engineering_pass"
    assert decision["stage_boundary"]["model_or_provider_calls"] == 0
    assert decision["stage_boundary"]["full_chain"] is False
    assert decision["root_cause_corrections"]["RC-P36-138"].startswith(
        "open_routed_to_S2_02"
    )
    assert decision["stage_boundary"][
        "S2_02_representative_node_runtime_consumption_and_natural_output_eval"
    ] == "entry_blocked_until_RC_P36_138_zero_call_repair"
    assert decision["stage_boundary"]["S3_dynamic_DecisionSurface_and_eight_dimension_quality"] == "not_started"
    assert active["observed_result"] == (
        "87 passed / 1 historical event-time assertion deselected"
    )
