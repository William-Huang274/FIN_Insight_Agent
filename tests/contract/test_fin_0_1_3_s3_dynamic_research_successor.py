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

from sec_agent.canonical_runtime.evidence_request import EvidenceRequest  # noqa: E402
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.s3_dynamic_research_successor import (  # noqa: E402
    S3DynamicResearchSuccessorError,
    apply_repair_observation,
    compile_s3_dynamic_research_successor_program,
    compile_wwc_authority,
    evaluate_information_economy,
    load_s3_dynamic_research_successor_policy,
    record_affected_cell_readjudication,
    validate_s3_dynamic_research_successor_program,
)


PATHS = {
    "policy": "configs/runtime/fin_ia_0_1_3_s3_dynamic_research_planner_evidence_request_and_content_quality_entry_policy_v1_0.json",
    "surface": "configs/releases/fin_ia_0_1_3_repair_closeout_s3_01_dynamic_decision_surface_v1_0.json",
    "claim": "configs/releases/fin_ia_0_1_3_repair_closeout_s3_02_claim_and_observable_wwc_v1_0.json",
    "synthesis": "configs/releases/fin_ia_0_1_3_repair_closeout_s3_03_cross_cell_synthesis_v1_0.json",
    "writer": "configs/releases/fin_ia_0_1_3_repair_closeout_s3_04_workpaper_writer_decision_ready_content_v1_0.json",
    "quality": "configs/releases/fin_ia_0_1_3_repair_closeout_s3_05_research_quality_gate_v1_0.json",
    "assessment": "configs/releases/fin_ia_0_1_3_s2_dell_changed_input_business_content_assessment_v1_0.json",
}
RESULT_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s3_dynamic_research_successor_"
    "minimum_zero_call_implementation_and_proof_v1_0.json"
)
PROGRAM_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s3_dynamic_research_successor_program_v1_0.json"
)


def _load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _inputs() -> dict[str, dict]:
    return {
        "policy": load_s3_dynamic_research_successor_policy(ROOT / PATHS["policy"]),
        **{key: _load(path) for key, path in PATHS.items() if key != "policy"},
    }


def _compile() -> tuple[dict, dict]:
    rows = _inputs()
    return (
        compile_s3_dynamic_research_successor_program(
            policy=rows["policy"],
            surface_decision=rows["surface"],
            claim_decision=rows["claim"],
            synthesis_decision=rows["synthesis"],
            writer_decision=rows["writer"],
            quality_decision=rows["quality"],
            dell_business_assessment=rows["assessment"],
        ),
        rows["policy"],
    )


def _accepted_observation(program: dict, policy: dict, request_id: str) -> dict:
    return apply_repair_observation(
        program,
        policy=policy,
        request_id=request_id,
        observation={
            "outcome": "accepted",
            "capture_ref": "fixture://s3-successor/accepted",
            "capture_digest": hashlib.sha256(b"accepted-capture").hexdigest(),
            "evidence_gate_status": "accepted",
            "evidence_ref": "E_FIXTURE_ACCEPTED",
        },
    )


def _readjudication_rows(program: dict, request_id: str) -> list[dict]:
    request = next(
        row
        for row in program["repair_requests"]
        if row["canonical_request"]["request_id"] == request_id
    )
    observation = next(
        row for row in program["repair_observations"] if row["request_id"] == request_id
    )
    return [
        {
            "cell_id": cell_id,
            "judgment_state": "supported_with_limits",
            "judgment_changed": cell_id == request["cell_id"],
            "support_refs": ["E_FIXTURE_ACCEPTED"],
            "counterevidence_refs": ["E_FIXTURE_COUNTER"],
            "mechanism": "The accepted observation changes only the bounded operating mechanism under review.",
            "boundary": "The fixture proves loop control, not a business or financial conclusion.",
            "wwc_ref": "WWC_FIXTURE",
            "observation_digest": observation["observation_digest"],
        }
        for cell_id in request["affected_cell_ids"]
    ]


def _point(
    text: str,
    *,
    evidence: tuple[str, ...] = ("E1",),
    gaps: tuple[str, ...] = (),
    status: str = "fact_supported",
) -> dict:
    return {
        "text": text,
        "epistemic_status": status,
        "evidence_aliases": list(evidence),
        "numeric_refs": [],
        "gap_aliases": list(gaps),
    }


def _report() -> dict:
    repeated = "Dell demand supports the current thesis because backlog growth improves shipment visibility."
    return {
        "sections": [
            {
                "section_id": "executive_thesis",
                "points": [
                    _point(
                        "Dell demand supports the current thesis because backlog growth improves shipment visibility. "
                        + "The conclusion remains bounded by conversion, margin, supply, competition and valuation evidence. "
                        + "This intentionally long executive point carries too many decisions and references for one point.",
                        evidence=("E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8", "E9"),
                    )
                ],
            },
            {"section_id": "demand_and_revenue_quality", "points": [_point(repeated)]},
            {
                "section_id": "counter_thesis_risks_and_gaps",
                "points": [
                    _point(
                        repeated,
                        gaps=("G1",),
                        status="bounded_inference",
                    )
                ],
            },
            {
                "section_id": "what_would_change",
                "points": [
                    _point(
                        "A reported cancellation or digestion event would weaken the judgment and trigger re-adjudication.",
                        evidence=("E2",),
                    )
                ],
            },
        ]
    }


def test_existing_s3_assets_compile_one_dynamic_zero_call_successor() -> None:
    program, policy = _compile()
    validate_s3_dynamic_research_successor_program(program, policy=policy)
    assert program["observed_counts"] == {
        "cases": 3,
        "decision_cells": 38,
        "current_pack_adjudicated_cells": 4,
        "planned_cells_without_current_judgment": 29,
        "compiled_repair_requests": 5,
        "mechanism_chains": 9,
        "wwc_conditions": 13,
        "numeric_wwc_without_authority": 0,
        "formal_quality_scores": 0,
        "paired_assessments": 0,
        "qualified_human_acceptances": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "network_calls": 0,
        "source_calls": 0,
        "retries": 0,
        "fallbacks": 0,
        "business_artifact_promotions": 0,
    }
    assert [row["cell_count"] for row in program["planner_states"]] == [13, 12, 13]
    assert all(row["fixed_call_count"] is None for row in program["planner_states"])
    assert all(
        cell["business_decision_role"]
        and cell["why_material"]
        and cell["downstream_decision"]
        for state in program["planner_states"]
        for cell in state["cells"]
    )


def test_five_gaps_compile_through_the_existing_canonical_evidence_request_contract() -> None:
    program, _ = _compile()
    requests = program["repair_requests"]
    assert {row["gap_id"] for row in requests} == {
        "DELL_GAP_DEMAND_DURABILITY",
        "DELL_GAP_AI_SERVER_PROFIT_ATTRIBUTION",
        "MU_GAP_HBM_ECONOMICS_ATTRIBUTION",
        "NVDA_GAP_PRODUCT_ECONOMICS_ATTRIBUTION",
        "NVDA_GAP_REALIZED_COUNTEREVIDENCE",
    }
    for row in requests:
        request = EvidenceRequest.model_validate(row["canonical_request"])
        assert request.execution_admission == "not_admitted"
        assert request.planning_authority == "shadow"
        assert request.budget.tool_call_limit == 1
        assert request.preferred_routes == ("shared_evidence_orchestrator",)
        assert request.fallback_routes == ()
        assert row["status"] == "compiled_not_admitted"
        assert row["return_contract"] == ["accepted", "rejected", "typed_gap", "needs_repair"]


def test_accepted_evidence_marks_only_the_target_and_transitive_dependents_for_readjudication() -> None:
    program, policy = _compile()
    request = next(
        row for row in program["repair_requests"] if row["gap_id"] == "DELL_GAP_AI_SERVER_PROFIT_ATTRIBUTION"
    )
    request_id = request["canonical_request"]["request_id"]
    before_refs = {
        cell["cell_id"]: cell["current_judgment_ref"]
        for cell in program["planner_states"][0]["cells"]
    }
    observed = _accepted_observation(program, policy, request_id)
    revised_request = next(
        row for row in observed["repair_requests"] if row["canonical_request"]["request_id"] == request_id
    )
    assert revised_request["status"] == "observation_accepted_pending_readjudication"
    assert revised_request["affected_cell_ids"] == [
        "bottleneck_counterevidence_and_what_would_change",
        "cross_chain_price_in_and_expectations",
        "value_and_profit_capture",
        "writer_admission_boundary",
    ]
    for cell in observed["planner_states"][0]["cells"]:
        if cell["cell_id"] in revised_request["affected_cell_ids"]:
            assert cell["state"] == "needs_readjudication"
        assert cell["current_judgment_ref"] == before_refs[cell["cell_id"]]
    assert observed["observed_counts"]["source_calls"] == 0
    assert observed["repair_observations"][0]["simulation_or_saved_replay_only"] is True


def test_readjudication_requires_exact_affected_coverage_and_new_evidence_for_a_changed_judgment() -> None:
    program, policy = _compile()
    request_id = program["repair_requests"][0]["canonical_request"]["request_id"]
    observed = _accepted_observation(program, policy, request_id)
    decisions = _readjudication_rows(observed, request_id)
    completed = record_affected_cell_readjudication(
        observed,
        policy=policy,
        request_id=request_id,
        decisions=decisions,
    )
    request = next(
        row for row in completed["repair_requests"] if row["canonical_request"]["request_id"] == request_id
    )
    assert request["status"] == "re_adjudicated"
    assert len(completed["readjudication_receipts"]) == len(request["affected_cell_ids"])
    assert all(
        cell["state"] == "adjudicated_after_repair"
        for cell in completed["planner_states"][0]["cells"]
        if cell["cell_id"] in request["affected_cell_ids"]
    )

    with pytest.raises(S3DynamicResearchSuccessorError, match="readjudication_coverage_invalid"):
        record_affected_cell_readjudication(
            observed,
            policy=policy,
            request_id=request_id,
            decisions=decisions[:-1],
        )
    missing_new_evidence = deepcopy(decisions)
    changed = next(row for row in missing_new_evidence if row["judgment_changed"])
    changed["support_refs"] = ["OLD_EVIDENCE_ONLY"]
    changed["counterevidence_refs"] = []
    with pytest.raises(S3DynamicResearchSuccessorError, match="changed_judgment_new_evidence_missing"):
        record_affected_cell_readjudication(
            observed,
            policy=policy,
            request_id=request_id,
            decisions=missing_new_evidence,
        )


@pytest.mark.parametrize("outcome", ["rejected", "typed_gap"])
def test_nonaccepted_observation_terminalizes_without_promoting_evidence_or_reopening_dependents(outcome: str) -> None:
    program, policy = _compile()
    request_id = program["repair_requests"][0]["canonical_request"]["request_id"]
    observed = apply_repair_observation(
        program,
        policy=policy,
        request_id=request_id,
        observation={
            "outcome": outcome,
            "capture_ref": f"fixture://s3-successor/{outcome}",
            "capture_digest": hashlib.sha256(outcome.encode()).hexdigest(),
            "evidence_gate_status": outcome,
            "reason_code": "bounded_route_did_not_return_acceptable_evidence",
        },
    )
    request = next(
        row for row in observed["repair_requests"] if row["canonical_request"]["request_id"] == request_id
    )
    assert request["status"] == outcome
    assert request["affected_cell_ids"] == []
    assert observed["repair_observations"][0]["evidence_ref"] is None
    assert not any(
        cell["state"] == "needs_readjudication"
        for state in observed["planner_states"]
        for cell in state["cells"]
    )


def test_unbound_numeric_wwc_is_typed_unoperationalizable_while_bound_and_qualitative_conditions_survive() -> None:
    unbound = compile_wwc_authority(
        {"threshold": "revenue declines by 15%", "threshold_authority_ref": "NUM:UNKNOWN"},
        allowed_numeric_authority_refs=("NUM:BOUND",),
    )
    assert unbound["operationalization_status"] == (
        "cannot_operationalize_numeric_threshold_with_current_evidence"
    )
    assert unbound["threshold_authority_ref"] is None
    bound = compile_wwc_authority(
        {"threshold": "revenue declines by 15%", "threshold_authority_ref": "NUM:BOUND"},
        allowed_numeric_authority_refs=("NUM:BOUND",),
    )
    assert bound["operationalization_status"] == "operationalizable"
    qualitative = compile_wwc_authority(
        {"threshold": "issuer reports a material cancellation or digestion event"}
    )
    assert qualitative["threshold_kind"] == "qualitative_observable_condition"
    program, _ = _compile()
    assert len(program["mechanism_and_wwc"]["what_would_change"]) == 13
    assert all(
        row["operationalization_status"] == "operationalizable"
        for row in program["mechanism_and_wwc"]["what_would_change"]
    )


def test_information_economy_separates_hard_truth_failures_from_quality_findings_without_persisting_prose() -> None:
    result = evaluate_information_economy(
        _report(),
        terminal_l1_codes=("numeric_surface_not_authorized",),
    )
    hard = {row["code"] for row in result["hard_failures"]}
    quality = {row["code"] for row in result["quality_findings"]}
    assert hard == {"numeric_or_identity_authority_violation"}
    assert {"cross_section_repetition", "overloaded_executive_point"} <= quality
    assert result["raw_prose_persisted"] is False
    assert "Dell demand" not in json.dumps(result, ensure_ascii=False)


def test_current_dell_quality_packet_is_honestly_blocked_before_scoring_and_preserves_other_stage_gaps() -> None:
    program, _ = _compile()
    packet = program["dell_fixed_pack_quality_packet"]
    assert packet["L1_status"] == "fail_immutable_historical_candidate"
    assert packet["L1_finding_count"] == 2
    assert packet["formal_scoreability"] == "blocked_before_L3_scoring"
    assert packet["total_score"] is None
    assert packet["formal_pass"] is False
    assert packet["paired_contract"]["formal_paired_assessment"] is False
    assert packet["qualified_human_content_acceptance"]["status"] == "pending"
    assert packet["historical_candidate_relabelled_or_promoted"] is False
    assert packet["non_S3_boundaries_preserved"] == [
        "external_candidate_coverage_RC_P36_157",
        "valuation_and_issuer_specific_supply_semantics_RC_P36_165",
    ]
    assert all(row["score"] is None for row in packet["dimensions"])


def test_saved_dell_report_pair_projection_is_prose_free_digest_bound_and_replayable_without_private_capture() -> None:
    program = json.loads(PROGRAM_PATH.read_text(encoding="utf-8"))
    policy = _inputs()["policy"]
    validate_s3_dynamic_research_successor_program(program, policy=policy)
    economy = program["information_economy"]
    assert economy["source_mode"] == "immutable_private_capture_in_memory_prose_free_projection"
    assert economy["source_terminal_sha256"] == "bbedc7b250bc84433a748c8ba8d612fcf1fa80eb8c535697ccc198e3ac0ca00d"
    assert economy["baseline"]["point_count"] == 42
    assert economy["agent"]["point_count"] == 30
    assert {row["code"] for row in economy["agent"]["hard_failures"]} == {
        "numeric_or_identity_authority_violation"
    }
    assert {row["code"] for row in economy["agent"]["quality_findings"]} == {
        "cross_section_repetition",
        "overloaded_executive_point",
        "weak_decision_density",
    }
    serialized = json.dumps(economy, ensure_ascii=False)
    assert "Dell demand" not in serialized
    assert economy["raw_prose_persisted"] is False


def test_cross_case_and_digest_mutations_fail_closed() -> None:
    program, policy = _compile()
    mutated = deepcopy(program)
    mutated["planner_states"][0]["case_key"] = "MU"
    mutated["program_digest"] = canonical_digest(
        {key: value for key, value in mutated.items() if key != "program_digest"}
    )
    with pytest.raises(S3DynamicResearchSuccessorError, match="case_surface_invalid"):
        validate_s3_dynamic_research_successor_program(mutated, policy=policy)

    mutated = deepcopy(program)
    mutated["repair_requests"][0]["canonical_request"]["execution_admission"] = "admitted"
    mutated["repair_requests"][0]["repair_request_digest"] = canonical_digest(
        {
            key: value
            for key, value in mutated["repair_requests"][0].items()
            if key != "repair_request_digest"
        }
    )
    mutated["program_digest"] = canonical_digest(
        {key: value for key, value in mutated.items() if key != "program_digest"}
    )
    with pytest.raises(S3DynamicResearchSuccessorError, match="request_boundary_invalid"):
        validate_s3_dynamic_research_successor_program(mutated, policy=policy)


def test_materialized_result_is_digest_bound_and_does_not_claim_live_or_acceptance() -> None:
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    body = {key: value for key, value in result.items() if key != "result_digest"}
    assert result["result_digest"] == canonical_digest(body)
    implementation = ROOT / result["implementation"]["runtime_ref"]
    assert result["implementation"]["runtime_sha256"] == hashlib.sha256(
        implementation.read_text(encoding="utf-8").encode("utf-8")
    ).hexdigest()
    assert result["acceptance"]["zero_call_successor"] == "engineering_pass"
    assert result["acceptance"]["formal_S3"] is False
    assert result["acceptance"]["post_repair_report"] is False
    assert result["acceptance"]["paired"] is False
    assert result["acceptance"]["qualified_human"] is False
    assert result["acceptance"]["release"] is False
    assert all(value == 0 for value in result["observed_calls"].values())
