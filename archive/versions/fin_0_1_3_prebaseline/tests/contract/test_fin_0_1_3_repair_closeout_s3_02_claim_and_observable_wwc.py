from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
for value in (ROOT, ROOT / "src"):
    if str(value) not in sys.path:
        sys.path.insert(0, str(value))

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest  # noqa: E402
from sec_agent.s3_claim_quality_program import (  # noqa: E402
    S3ClaimQualityError,
    compile_s3_claim_quality_program,
    load_s3_claim_quality_policy,
    validate_s3_claim_quality_program,
)


PATHS = {
    "policy": "configs/runtime/fin_ia_0_1_3_repair_closeout_s3_claim_and_observable_wwc_policy_v1_0.json",
    "s1": "configs/releases/fin_ia_0_1_3_repair_closeout_s1_05_retrieval_evidence_usefulness_and_s1_closeout_v1_0.json",
    "s2": "configs/releases/fin_ia_0_1_3_repair_closeout_s2_01_research_question_method_contract_translation_v1_0.json",
    "representative": "configs/releases/fin_ia_0_1_3_repair_closeout_s2_02_representative_node_context_precedence_and_canary_entry_v1_0.json",
    "s3": "configs/releases/fin_ia_0_1_3_repair_closeout_s3_01_dynamic_decision_surface_v1_0.json",
    "natural_s2": "configs/releases/fin_ia_0_1_3_repair_closeout_s2_02_three_family_natural_canary_result_v1_0.json",
    "natural_s2_03": "configs/releases/fin_ia_0_1_3_repair_closeout_s2_03_context_yield_natural_reproof_result_v1_0.json",
}
DECISION_PATH = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_02_claim_and_observable_wwc_v1_0.json"
ACTIVE_PATH = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_02_active_test_suite_successor_v1_0.json"


def _load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _inputs() -> dict[str, dict]:
    return {
        "policy": load_s3_claim_quality_policy(ROOT / PATHS["policy"]),
        **{key: _load(path) for key, path in PATHS.items() if key != "policy"},
    }


def _compile() -> tuple[dict, dict]:
    rows = _inputs()
    program = compile_s3_claim_quality_program(
        policy=rows["policy"],
        s1_decision=rows["s1"],
        s2_decision=rows["s2"],
        representative_decision=rows["representative"],
        s3_surface_decision=rows["s3"],
        natural_s2_result=rows["natural_s2"],
        natural_s2_03_result=rows["natural_s2_03"],
    )
    return program, rows["policy"]


def _reseal_card_and_program(program: dict, index: int) -> None:
    card = program["core_claim_cards"][index]
    card["claim_card_digest"] = canonical_digest({key: value for key, value in card.items() if key != "claim_card_digest"})
    program["program_digest"] = canonical_digest({key: value for key, value in program.items() if key != "program_digest"})


def test_nine_core_claim_contracts_preserve_four_natural_and_five_fixture_boundaries() -> None:
    program, policy = _compile()
    validate_s3_claim_quality_program(program, policy=policy)
    assert program["observed_counts"] == {
        "core_claim_cards": 9,
        "live_natural_claim_cards": 4,
        "fixture_only_claim_cards": 5,
        "structured_wwc": 13,
        "numeric_fact_bindings": 12,
        "typed_gap_bindings": 2,
        "planned_dynamic_cells_without_claim_choice": 29,
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "source_calls": 0,
        "business_runs": 0,
    }
    assert sum(card["natural_result_ref"] is not None for card in program["core_claim_cards"]) == 4
    assert sum(card["choice_authority"] == "fixture_choice_engineering_only" for card in program["core_claim_cards"]) == 5


def test_live_natural_choices_take_precedence_without_reusing_fixture_directions() -> None:
    program, _ = _compile()
    cards = {(row["case_key"], row["program_cell_id"]): row for row in program["core_claim_cards"]}
    assert cards[("DELL", "demand_authenticity_and_sustainability")]["answer_direction"] == "cannot_infer"
    assert cards[("MU", "value_and_profit_capture")]["confidence"] == "high"
    assert cards[("NVDA", "bottleneck_counterevidence_and_what_would_change")]["epistemic_state"] == "cannot_infer"
    assert cards[("NVDA", "demand_authenticity_and_sustainability")]["answer_direction"] == "mixed"
    assert cards[("DELL", "value_and_profit_capture")]["choice_authority"] == "fixture_choice_engineering_only"


def test_claims_are_company_specific_evidence_or_gap_bound_and_never_generic_renderer_text() -> None:
    program, policy = _compile()
    for card in program["core_claim_cards"]:
        assert card["company_name"].split()[0].lower() in card["mechanism_atom"].lower()
        assert card["evidence_boundary"] or card["typed_gaps"]
        assert not any(fragment.lower() in card["mechanism_atom"].lower() for fragment in policy["forbidden_generic_fragments"])
        assert card["display_ready"] is False
    numeric = [fact for card in program["core_claim_cards"] for fact in card["numeric_facts"]]
    assert len(numeric) == 12
    assert all(fact["normalized_value"].isdigit() and fact["unit"] == "USD" for fact in numeric)


def test_every_selected_wwc_has_metric_direction_time_threshold_and_next_route() -> None:
    program, policy = _compile()
    required = set(policy["required_wwc_fields"])
    rows = [row for card in program["core_claim_cards"] for row in card["what_would_change"]]
    assert len(rows) == 13
    assert all(required <= set(row) and all(str(row[field]).strip() for field in required) for row in rows)
    assert len({(row["metric_or_event"], row["threshold"], row["next_evidence_route"]) for row in rows}) >= 9


def test_unjudged_dynamic_cells_remain_explicitly_planned_without_fabricated_claims() -> None:
    program, _ = _compile()
    rows = program["planned_dynamic_cells_without_claim_choice"]
    assert len(rows) == 29
    assert {row["case_key"] for row in rows} == {"DELL", "MU", "NVDA"}
    assert all(row["status"] == "planned_no_claim_choice" and row["evidence_roles"] and row["stop_rule"] for row in rows)


def test_cross_case_numeric_generic_wwc_and_fixture_promotion_mutations_fail_closed() -> None:
    program, policy = _compile()
    numeric_index = next(index for index, card in enumerate(program["core_claim_cards"]) if card["numeric_facts"])
    mutated = deepcopy(program)
    mutated["core_claim_cards"][numeric_index]["numeric_facts"][0]["case_key"] = "CROSS_CASE"
    _reseal_card_and_program(mutated, numeric_index)
    with pytest.raises(S3ClaimQualityError, match="numeric_binding_invalid"):
        validate_s3_claim_quality_program(mutated, policy=policy)

    mutated = deepcopy(program)
    mutated["core_claim_cards"][0]["mechanism_atom"] = "证据方向支持当前单元判断；详见本地绑定事实"
    _reseal_card_and_program(mutated, 0)
    with pytest.raises(S3ClaimQualityError, match="company_mechanism_invalid|generic_statement_forbidden"):
        validate_s3_claim_quality_program(mutated, policy=policy)

    fixture_index = next(index for index, card in enumerate(program["core_claim_cards"]) if card["choice_authority"] == "fixture_choice_engineering_only")
    mutated = deepcopy(program)
    mutated["core_claim_cards"][fixture_index]["choice_authority"] = "live_natural_exact_once"
    _reseal_card_and_program(mutated, fixture_index)
    with pytest.raises(S3ClaimQualityError, match="natural_ref_missing"):
        validate_s3_claim_quality_program(mutated, policy=policy)

    mutated = deepcopy(program)
    mutated["core_claim_cards"][0]["what_would_change"][0].pop("threshold")
    _reseal_card_and_program(mutated, 0)
    with pytest.raises(S3ClaimQualityError, match="wwc_shape_invalid"):
        validate_s3_claim_quality_program(mutated, policy=policy)


def test_materialized_decision_is_digest_bound_and_does_not_request_another_canary() -> None:
    decision = json.loads(DECISION_PATH.read_text(encoding="utf-8"))
    active = json.loads(ACTIVE_PATH.read_text(encoding="utf-8"))
    assert decision["record_digest"] == canonical_digest({key: value for key, value in decision.items() if key != "record_digest"})
    assert active["decision_sha256"] == hashlib.sha256(DECISION_PATH.read_bytes()).hexdigest()
    assert active["suite_digest"] == canonical_digest({key: value for key, value in active.items() if key != "suite_digest"})
    assert active["observed_result"] == "214 passed / 1 historical assertion deselected"
    assert decision["acceptance"]["S3_02"] == "engineering_pass"
    assert decision["canary_disposition"]["additional_paid_canary"] == "not_required"
    assert decision["stage_boundary"]["all_dynamic_cells_naturally_judged"] is False
    assert decision["stage_boundary"]["full_chain"] is False
    assert decision["stage_boundary"]["release"] is False
