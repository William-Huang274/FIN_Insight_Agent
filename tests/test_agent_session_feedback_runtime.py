from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from sec_agent.canonical_runtime import (
    CanonicalRuntimeError,
    append_session_event,
    canonical_digest,
    compile_s1_feedback_receipts,
    compile_s2_feedback_receipt,
    compile_verifier_feedback_receipts,
    create_agent_session,
    create_context_checkpoint,
    resume_agent_session,
    validate_event_log,
    validate_runtime_artifact,
)


ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-08-19T12:00:00+08:00"


def _session_and_events() -> tuple[dict, list[dict]]:
    session = create_agent_session(
        session_id="SESSION::DELL::RUNTIME-R1",
        run_id="RUN::DELL::RUNTIME-R1",
        case_id="DELL",
        case_version="current-v1.4",
        as_of_date="2026-08-06",
        objective_ref="objective://dell/value-capture",
        active_plan_ref="plan://dell/r1",
        created_at=NOW,
    )
    events: list[dict] = []
    events.append(
        append_session_event(
            events,
            session_id=session["session_id"],
            event_type="session_created",
            actor_id="Harness",
            occurred_at=NOW,
            output_refs=(session["session_id"],),
        )
    )
    events.append(
        append_session_event(
            events,
            session_id=session["session_id"],
            event_type="tool_execution_completed",
            actor_id="S1",
            attempt_id="S1-LOOKUP-R1",
            occurred_at="2026-08-19T12:00:01+08:00",
            input_refs=("request://dell/value-capture",),
            output_refs=("readiness://dell/value-capture",),
        )
    )
    return session, events


def test_session_event_checkpoint_resume_preserves_material_state() -> None:
    session, events = _session_and_events()
    checkpoint = create_context_checkpoint(
        session=session,
        events=events,
        checkpoint_id="CHECKPOINT::DELL::R1",
        objective_digest="1" * 64,
        plan_digest="2" * 64,
        research_graph_digest="3" * 64,
        accepted_evidence_refs=("EV::DELL::ORDER",),
        numeric_fact_refs=("NUMFACT::DELL::REVENUE",),
        open_gap_refs=("GAP::DELL::PRODUCT-PROFIT",),
        unresolved_feedback_refs=("FEEDBACK::DELL::FALSE-ABSENCE",),
        agent_local_state_refs=("state://dell/value-cell",),
        authority_refs=("authority://case/dell", "authority://numeric/s2"),
        counterevidence_refs=("EV::DELL::PULL-FORWARD",),
        open_question_refs=("QUESTION::DELL::DURABILITY",),
    )
    receipt = resume_agent_session(
        session=session,
        events=events,
        checkpoint=checkpoint,
        expected_case_id="DELL",
        expected_case_version="current-v1.4",
        expected_as_of_date="2026-08-06",
        expected_active_plan_ref="plan://dell/r1",
        resumed_at="2026-08-19T12:01:00+08:00",
        required_authority_refs=("authority://case/dell", "authority://numeric/s2"),
        required_open_gap_refs=("GAP::DELL::PRODUCT-PROFIT",),
        required_unresolved_feedback_refs=("FEEDBACK::DELL::FALSE-ABSENCE",),
        required_counterevidence_refs=("EV::DELL::PULL-FORWARD",),
        required_open_question_refs=("QUESTION::DELL::DURABILITY",),
    )

    assert receipt["status"] == "resume_replay_verified"
    assert receipt["preserved_state_counts"] == {
        "accepted_evidence": 1,
        "numeric_facts": 1,
        "open_gaps": 1,
        "unresolved_feedback": 1,
        "authority_refs": 2,
        "counterevidence": 1,
        "open_questions": 1,
    }


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ("event_digest", "runtime_event_digest_invalid"),
        ("event_order", "runtime_event_sequence_invalid"),
        ("checkpoint_case", "runtime_checkpoint_digest_invalid"),
        ("resume_case", "runtime_resume_case_id_mismatch"),
        ("drop_gap", "runtime_resume_material_state_dropped:open_gap_refs"),
        (
            "drop_counterevidence",
            "runtime_resume_material_state_dropped:counterevidence_refs",
        ),
    ),
)
def test_session_resume_mutations_fail_closed(mutation: str, message: str) -> None:
    session, events = _session_and_events()
    checkpoint = create_context_checkpoint(
        session=session,
        events=events,
        checkpoint_id="CHECKPOINT::DELL::R1",
        objective_digest="1" * 64,
        plan_digest="2" * 64,
        research_graph_digest="3" * 64,
        open_gap_refs=("GAP::DELL::PRODUCT-PROFIT",),
        authority_refs=("authority://case/dell",),
        counterevidence_refs=("EV::DELL::PULL-FORWARD",),
        open_question_refs=("QUESTION::DELL::DURABILITY",),
    )
    expected_case = "DELL"
    required_gaps = ("GAP::DELL::PRODUCT-PROFIT",)
    required_counter = ("EV::DELL::PULL-FORWARD",)
    if mutation == "event_digest":
        events[1]["event_digest"] = "0" * 64
    elif mutation == "event_order":
        events.reverse()
    elif mutation == "checkpoint_case":
        checkpoint["case_id"] = "MU"
    elif mutation == "resume_case":
        expected_case = "MU"
    elif mutation == "drop_gap":
        required_gaps = ("GAP::DELL::PRODUCT-PROFIT", "GAP::DELL::MISSING",)
    elif mutation == "drop_counterevidence":
        required_counter = ("EV::DELL::PULL-FORWARD", "EV::DELL::MISSING",)

    with pytest.raises(CanonicalRuntimeError, match=message):
        resume_agent_session(
            session=session,
            events=events,
            checkpoint=checkpoint,
            expected_case_id=expected_case,
            expected_case_version="current-v1.4",
            expected_as_of_date="2026-08-06",
            expected_active_plan_ref="plan://dell/r1",
            resumed_at="2026-08-19T12:01:00+08:00",
            required_authority_refs=("authority://case/dell",),
            required_open_gap_refs=required_gaps,
            required_counterevidence_refs=required_counter,
            required_open_question_refs=("QUESTION::DELL::DURABILITY",),
        )


def test_attempt_cannot_have_two_terminal_events() -> None:
    session, events = _session_and_events()
    duplicate = deepcopy(events[-1])
    duplicate["sequence"] = 3
    duplicate["event_id"] = "EVENT::DUPLICATE"
    duplicate["prior_event_digest"] = events[-1]["event_digest"]
    unsigned = {key: value for key, value in duplicate.items() if key != "event_digest"}
    duplicate["event_digest"] = canonical_digest(unsigned)

    with pytest.raises(CanonicalRuntimeError, match="runtime_attempt_terminal_duplicate"):
        validate_event_log([*events, duplicate], expected_session_id=session["session_id"])


def test_six_frozen_runtime_artifact_skeletons_validate() -> None:
    session, events = _session_and_events()
    checkpoint = create_context_checkpoint(
        session=session,
        events=events,
        checkpoint_id="CHECKPOINT::DELL::R1",
        objective_digest="1" * 64,
        plan_digest="2" * 64,
        research_graph_digest="3" * 64,
    )
    feedback = compile_s2_feedback_receipt(
        result={
            "status": "typed_gap",
            "fact_request_id": "TFR::1",
            "ticker": "DELL",
            "metric_id": "product_operating_profit",
            "typed_gap": {"gap_code": "typed_fact_not_found_for_as_of_and_period"},
        },
        session_id=session["session_id"],
        source_node_id="S2",
        artifact_ref="artifact://s2/result",
        created_at=NOW,
    )
    assert feedback is not None
    plan_delta = {
        "plan_delta_id": "PLANDELTA::1",
        "session_id": session["session_id"],
        "base_plan_digest": "2" * 64,
        "proposed_by_agent_id": "CELL::VALUE",
        "reason_feedback_refs": [feedback["feedback_id"]],
        "add_actions": [],
        "modify_actions": [],
        "defer_actions": [],
        "cancel_actions": [],
        "expected_information_gain": "resolve product profit bridge",
        "budget_impact": {"model_steps": 0, "tool_calls": 1},
        "validation_status": "pending",
    }
    graph_delta = {
        "graph_delta_id": "GRAPHDELTA::1",
        "session_id": session["session_id"],
        "base_graph_digest": "3" * 64,
        "proposed_by_agent_id": "CELL::VALUE",
        "edge_additions": [],
        "edge_corrections": [],
        "edge_retractions": [],
        "supporting_evidence_refs": [],
        "hypothesis_only_edges": [],
        "validation_status": "pending",
    }
    stop = {
        "stop_decision_id": "STOP::1",
        "session_id": session["session_id"],
        "decided_by_agent_id": "LEAD",
        "decision": "pause_for_tool_recovery",
        "reason_codes": ["typed_fact_not_found_for_as_of_and_period"],
        "coverage_state_refs": ["coverage://dell/value"],
        "unresolved_feedback_refs": [feedback["feedback_id"]],
        "remaining_gap_refs": ["gap://dell/product-profit"],
        "budget_state": {"remaining_tool_calls": 1},
        "quality_risk": "material product-profit bridge unresolved",
        "harness_validation_status": "accepted",
    }

    assert validate_runtime_artifact("AgentSession", session)["case_id"] == "DELL"
    assert validate_runtime_artifact("FeedbackReceipt", feedback)["owning_stage"] == "S2"
    assert validate_runtime_artifact("PlanDelta", plan_delta)["validation_status"] == "pending"
    assert validate_runtime_artifact("GraphDelta", graph_delta)["validation_status"] == "pending"
    assert validate_runtime_artifact("ContextCheckpoint", checkpoint)["event_sequence"] == 2
    assert validate_runtime_artifact("StopDecision", stop)["decision"] == "pause_for_tool_recovery"


def test_current_s1_failures_route_to_different_earliest_owners() -> None:
    mu_path = (
        ROOT
        / "configs/retrieval/fin_ia_0_1_3_s1_mu_current_product_readiness_result_v1_6.json"
    )
    readiness = json.loads(mu_path.read_text(encoding="utf-8"))
    receipts = compile_s1_feedback_receipts(
        readiness=readiness,
        session_id="SESSION::MU::S1",
        artifact_ref=mu_path.relative_to(ROOT).as_posix(),
        created_at=NOW,
    )

    assert len(receipts) == 7
    assert sum(row["failure_code"] == "source_route_not_executed_or_not_terminal" for row in receipts) == 4
    assert sum(row["failure_code"] == "reviewed_evidence_admission_pending" for row in receipts) == 3
    assert {row["owning_plane"] for row in receipts} == {
        "infrastructure_and_tool_plane",
        "harness_control_plane",
    }
    assert all("公开信息" in "".join(row["forbidden_interpretations"]) for row in receipts)


def test_source_asset_reconciliation_prevents_repeat_download_and_preserves_parallel_admission() -> None:
    mu_path = (
        ROOT
        / "configs/retrieval/fin_ia_0_1_3_s1_mu_current_product_readiness_result_v1_6.json"
    )
    readiness = json.loads(mu_path.read_text(encoding="utf-8"))
    request = next(
        row
        for row in readiness["requests"]
        if row["readiness_state"] == "blocked_by_candidate_coverage"
    )
    request["source_asset_reconciliation"] = {
        "state": "current_official_source_asset_present",
        "official_source_acquisition_required": False,
    }
    request["pending_evidence_admission_requirement_ids"] = ["REQMAT::PENDING"]
    readiness["requests"] = [request]

    receipts = compile_s1_feedback_receipts(
        readiness=readiness,
        session_id="SESSION::MU::S1::RECONCILED",
        artifact_ref=mu_path.relative_to(ROOT).as_posix(),
        created_at=NOW,
    )

    assert [row["failure_code"] for row in receipts] == [
        "source_present_candidate_material_requirement_not_recalled",
        "reviewed_evidence_admission_pending_alongside_other_blocker",
    ]
    assert receipts[0]["target_node_id"] == "S1.query_recall_ranking"
    assert "不能重复下载" in receipts[0]["model_visible_summary"]
    assert receipts[1]["target_node_id"] == "S1.EvidenceGate"
    assert any(
        ref == "requirement://REQMAT::PENDING"
        for ref in receipts[1]["artifact_refs"]
    )


def test_s2_gap_and_conflict_never_invite_model_number_selection() -> None:
    gap = compile_s2_feedback_receipt(
        result={
            "status": "typed_gap",
            "fact_request_id": "TFR::GAP",
            "ticker": "MU",
            "metric_id": "operating_income",
            "typed_gap": {"gap_code": "typed_fact_not_found_for_as_of_and_period"},
        },
        session_id="SESSION::MU::S2",
        source_node_id="S2.TypedFactExecutor",
        artifact_ref="artifact://s2/gap",
        created_at=NOW,
    )
    conflict = compile_s2_feedback_receipt(
        result={
            "status": "typed_conflict",
            "fact_request_id": "TFR::CONFLICT",
            "ticker": "MU",
            "metric_id": "revenue",
            "typed_conflict": {"conflict_code": "authoritative_numeric_fact_conflict"},
        },
        session_id="SESSION::MU::S2",
        source_node_id="S2.TypedFactExecutor",
        artifact_ref="artifact://s2/conflict",
        created_at=NOW,
    )

    assert gap and conflict
    assert "公开信息不存在" in gap["model_visible_summary"]
    assert "模型不得自行挑选" in conflict["model_visible_summary"]
    assert all(row["owning_stage"] == "S2" for row in (gap, conflict))


def test_verifier_feedback_returns_false_absence_to_research_node() -> None:
    receipts = compile_verifier_feedback_receipts(
        findings=(
            {
                "finding_code": "asserted_absent_but_present_in_case",
                "claim_surface_id": "SURFACE::VALUE",
                "truth_alias": "EV_ALIAS::AI_ORDERS",
            },
            {"finding_code": "identity_mismatch", "claim_surface_id": "SURFACE::ID"},
        ),
        session_id="SESSION::DELL::S3",
        source_node_id="S3.Verifier",
        artifact_ref="artifact://s3/reconciliation",
        created_at=NOW,
    )

    assert receipts[0]["owning_plane"] == "agent_work_mode_plane"
    assert receipts[0]["target_node_id"] == "S3.originating_research_node"
    assert "不得让 Verifier" in "".join(receipts[0]["forbidden_interpretations"])
    assert receipts[1]["owning_plane"] == "harness_control_plane"


def test_verifier_feedback_preserves_detailed_semantic_repair_instruction() -> None:
    receipts = compile_verifier_feedback_receipts(
        findings=(
            {
                "finding_code": "historical_context_promoted_to_current_cause",
                "target_node_id": "AGENT::VALUE_CAPTURE",
                "model_visible_summary": (
                    "2025-10-31 的历史 mix 说明不能证明 2026-05-01 当季原因。"
                ),
                "permitted_next_actions": ["恢复来源时期并降级为历史背景"],
                "forbidden_interpretations": ["不得写成当季原因"],
            },
        ),
        session_id="SESSION::DELL::S3::REPAIR",
        source_node_id="S3.IndependentContentVerifier",
        artifact_ref="artifact://s3/content-assessment",
        created_at=NOW,
    )

    assert receipts[0]["target_node_id"] == "AGENT::VALUE_CAPTURE"
    assert receipts[0]["model_visible_summary"].startswith("2025-10-31")
    assert receipts[0]["permitted_next_actions"] == [
        "恢复来源时期并降级为历史背景"
    ]
    assert receipts[0]["forbidden_interpretations"] == ["不得写成当季原因"]
