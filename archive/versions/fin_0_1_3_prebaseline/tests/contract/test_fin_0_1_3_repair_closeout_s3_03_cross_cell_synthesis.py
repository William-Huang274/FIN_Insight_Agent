from __future__ import annotations

from copy import deepcopy
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
from sec_agent.s3_cross_cell_synthesis_program import (  # noqa: E402
    S3CrossCellSynthesisError,
    compile_s3_cross_cell_synthesis_program,
    load_s3_cross_cell_policy,
    validate_s3_cross_cell_synthesis_program,
)


POLICY_PATH = ROOT / "configs/runtime/fin_ia_0_1_3_repair_closeout_s3_cross_cell_synthesis_policy_v1_0.json"
CLAIM_PATH = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_02_claim_and_observable_wwc_v1_0.json"
DECISION_PATH = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_03_cross_cell_synthesis_v1_0.json"
ACTIVE_PATH = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_03_active_test_suite_successor_v1_0.json"


def _compile() -> tuple[dict, dict]:
    policy = load_s3_cross_cell_policy(POLICY_PATH)
    claim = json.loads(CLAIM_PATH.read_text(encoding="utf-8"))
    return compile_s3_cross_cell_synthesis_program(policy=policy, claim_decision=claim), policy


def _reseal(program: dict, index: int) -> None:
    synthesis = program["case_syntheses"][index]
    synthesis["synthesis_digest"] = canonical_digest({key: value for key, value in synthesis.items() if key != "synthesis_digest"})
    program["program_digest"] = canonical_digest({key: value for key, value in program.items() if key != "program_digest"})


def test_three_cases_have_real_cross_cell_dependencies_conflicts_and_owned_gaps() -> None:
    program, policy = _compile()
    validate_s3_cross_cell_synthesis_program(program, policy=policy)
    assert program["observed_counts"] == {
        "case_syntheses": 3, "dependencies": 3, "conflicts": 3, "gaps": 5,
        "resolved_conflicts": 0, "deferred_conflicts": 3, "blocked_conflicts": 0,
        "all_natural_case_syntheses": 0, "planned_no_claim_cells_included": 0,
        "model_calls": 0, "provider_calls": 0, "network_calls": 0, "business_runs": 0,
    }
    for synthesis in program["case_syntheses"]:
        assert synthesis["dependencies"][0]["from_claim_id"] != synthesis["dependencies"][0]["to_claim_id"]
        assert synthesis["dependencies"][0]["evidence_candidate_ids"]
        assert synthesis["conflicts"][0]["disposition"] == "defer"
        assert synthesis["conflicts"][0]["reason"]
        assert all(all(gap[field] for field in ("impact", "priority", "owner", "stop_condition", "next_evidence_route")) for gap in synthesis["gaps"])


def test_synthesis_is_not_status_repetition_or_false_all_natural_authority() -> None:
    program, _ = _compile()
    assert [row["natural_claim_count"] for row in program["case_syntheses"]] == [1, 1, 2]
    assert all(row["synthesis_authority"] == "fixture_mixed_engineering_only" for row in program["case_syntheses"])
    assert all(
        len(row["conflicts"][0]["reason"]) > 80
        and "cross_cell_direction_divergence" not in row["conflicts"][0]["reason"]
        for row in program["case_syntheses"]
    )
    assert all(row["display_ready"] is False for row in program["case_syntheses"])


def test_typed_and_claim_boundary_gaps_remain_distinct_and_non_repeated() -> None:
    program, _ = _compile()
    gaps = [gap for row in program["case_syntheses"] for gap in row["gaps"]]
    assert len({gap["gap_id"] for gap in gaps}) == 5
    assert {gap["source_basis"]["type"] for gap in gaps} == {"typed_gap", "claim_boundary"}
    assert len({(gap["impact"], gap["next_evidence_route"]) for gap in gaps}) == 5


def test_cross_claim_missing_gap_and_false_resolve_mutations_fail_closed() -> None:
    program, policy = _compile()
    mutated = deepcopy(program)
    mutated["case_syntheses"][0]["dependencies"][0]["from_claim_id"] = mutated["case_syntheses"][1]["claim_card_ids"][0]
    _reseal(mutated, 0)
    with pytest.raises(S3CrossCellSynthesisError, match="dependency_binding_invalid"):
        validate_s3_cross_cell_synthesis_program(mutated, policy=policy)

    mutated = deepcopy(program)
    mutated["case_syntheses"][0]["gaps"][0]["stop_condition"] = ""
    _reseal(mutated, 0)
    with pytest.raises(S3CrossCellSynthesisError, match="gap_disposition_invalid"):
        validate_s3_cross_cell_synthesis_program(mutated, policy=policy)

    mutated = deepcopy(program)
    mutated["case_syntheses"][0]["conflicts"][0]["disposition"] = "resolve"
    _reseal(mutated, 0)
    with pytest.raises(S3CrossCellSynthesisError, match="fixture_conflict_resolve_forbidden"):
        validate_s3_cross_cell_synthesis_program(mutated, policy=policy)


def test_materialized_decision_is_digest_bound_and_honest() -> None:
    decision = json.loads(DECISION_PATH.read_text(encoding="utf-8"))
    active = json.loads(ACTIVE_PATH.read_text(encoding="utf-8"))
    assert decision["record_digest"] == canonical_digest({key: value for key, value in decision.items() if key != "record_digest"})
    assert active["decision_sha256"] == hashlib.sha256(DECISION_PATH.read_bytes()).hexdigest()
    assert active["suite_digest"] == canonical_digest({key: value for key, value in active.items() if key != "suite_digest"})
    assert active["observed_result"] == "219 passed / 1 historical assertion deselected"
    assert decision["acceptance"]["S3_03"] == "engineering_pass"
    assert decision["acceptance"]["all_natural_business_syntheses"] == 0
    assert decision["canary_disposition"]["additional_paid_canary"] == "not_required"
    assert decision["stage_boundary"]["writer_ready"] is False
    assert decision["stage_boundary"]["release"] is False
