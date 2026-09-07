from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.canonical_runtime import (  # noqa: E402
    append_session_event,
    canonical_digest,
    compile_s1_feedback_receipts,
    compile_s2_feedback_receipt,
    compile_verifier_feedback_receipts,
    create_agent_session,
    create_context_checkpoint,
    resume_agent_session,
    validate_runtime_artifact,
)
from retrieval.human_operability import (  # noqa: E402
    compile_human_operability_preflight,
    load_human_operability_program,
)


READINESS_REFS = {
    "DELL": "configs/retrieval/fin_ia_0_1_3_s1_dell_current_product_readiness_result_v1_5.json",
    "MU": "configs/retrieval/fin_ia_0_1_3_s1_mu_current_product_readiness_result_v1_6.json",
    "NVDA": "configs/retrieval/fin_ia_0_1_3_s1_nvda_current_product_readiness_result_v1_6.json",
}
MU_SOURCE_TRUTH_REF = (
    "data/workbench_private/fin_0_1_3_s1_source_route_truth_replay/mu-r1/full_result.json"
)
VERIFIER_ASSESSMENT_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_dynamic_five_cell_R7_content_assessment_v1_0.json"
)
HUMAN_OPERABILITY_PROGRAM_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_human_operability_and_blind_gate_program_v1_0.json"
)


def _read(ref: str) -> dict[str, Any]:
    return json.loads((ROOT / ref).read_text(encoding="utf-8"))


def _sha256(ref: str) -> str:
    digest = hashlib.sha256()
    with (ROOT / ref).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _first_s2_states(source_truth: dict[str, Any]) -> tuple[dict, dict]:
    gaps = []
    conflicts = []
    for request in source_truth["product_projection"]["request_results"]:
        for result in request.get("typed_fact_results") or ():
            if result.get("status") == "typed_gap":
                gaps.append(result)
            elif result.get("status") == "typed_conflict":
                conflicts.append(result)
    if not gaps or not conflicts:
        raise ValueError("zero_call_proof_requires_real_s2_gap_and_conflict")
    return gaps[0], conflicts[0]


def compile_proof(recorded_at: str) -> dict[str, Any]:
    session = create_agent_session(
        session_id="SESSION::FIN013::ZERO-CALL-FEEDBACK-R1",
        run_id="FIN013-S0-S1-S2-S3-ZERO-CALL-FEEDBACK-R1",
        case_id="DELL",
        case_version="current-v1.4",
        as_of_date="2026-08-06",
        objective_ref="objective://agent-runtime-feedback-proof",
        active_plan_ref="plan://agent-runtime-feedback-proof/r1",
        created_at=recorded_at,
    )
    human_preflight = compile_human_operability_preflight(
        repo_root=ROOT,
        program=load_human_operability_program(
            ROOT / HUMAN_OPERABILITY_PROGRAM_REF
        ),
        recorded_at=recorded_at,
    )
    preflight_by_case = {
        str(row["case_key"]): row for row in human_preflight["cases"]
    }
    s1_receipts = []
    s1_by_case = {}
    for case_key, ref in READINESS_REFS.items():
        receipts = compile_s1_feedback_receipts(
            readiness=preflight_by_case[case_key],
            session_id=session["session_id"],
            artifact_ref=ref,
            created_at=recorded_at,
        )
        s1_receipts.extend(receipts)
        s1_by_case[case_key] = {
            "feedback_count": len(receipts),
            "failure_code_counts": {
                code: sum(row["failure_code"] == code for row in receipts)
                for code in sorted({row["failure_code"] for row in receipts})
            },
        }

    s2_source = _read(MU_SOURCE_TRUTH_REF)
    s2_gap, s2_conflict = _first_s2_states(s2_source)
    s2_receipts = [
        compile_s2_feedback_receipt(
            result=result,
            session_id=session["session_id"],
            source_node_id="S2.TypedFactExecutor",
            artifact_ref=MU_SOURCE_TRUTH_REF,
            created_at=recorded_at,
        )
        for result in (s2_gap, s2_conflict)
    ]
    if any(row is None for row in s2_receipts):
        raise ValueError("zero_call_proof_s2_feedback_missing")

    verifier = _read(VERIFIER_ASSESSMENT_REF)
    verifier_receipts = compile_verifier_feedback_receipts(
        findings=verifier["material_findings"],
        session_id=session["session_id"],
        source_node_id="S3.Verifier",
        artifact_ref=VERIFIER_ASSESSMENT_REF,
        created_at=recorded_at,
    )
    all_feedback = [*s1_receipts, *s2_receipts, *verifier_receipts]

    events = []
    events.append(
        append_session_event(
            events,
            session_id=session["session_id"],
            event_type="session_created",
            actor_id="Harness",
            occurred_at=recorded_at,
            output_refs=(session["session_id"],),
        )
    )
    events.append(
        append_session_event(
            events,
            session_id=session["session_id"],
            event_type="feedback_issued",
            actor_id="Harness.FeedbackRouter",
            occurred_at=recorded_at,
            input_refs=tuple(READINESS_REFS.values())
            + (
                HUMAN_OPERABILITY_PROGRAM_REF,
                MU_SOURCE_TRUTH_REF,
                VERIFIER_ASSESSMENT_REF,
            ),
            output_refs=("feedback-set://zero-call-r1",),
            feedback_refs=tuple(row["feedback_id"] for row in all_feedback),
        )
    )
    checkpoint = create_context_checkpoint(
        session=session,
        events=events,
        checkpoint_id="CHECKPOINT::FIN013::ZERO-CALL-FEEDBACK-R1",
        objective_digest=canonical_digest(session["objective_ref"]),
        plan_digest=canonical_digest(session["active_plan_ref"]),
        research_graph_digest=canonical_digest("graph://zero-call-proof"),
        open_gap_refs=("GAP::DELL::PRODUCT-PROFIT",),
        unresolved_feedback_refs=tuple(row["feedback_id"] for row in all_feedback),
        authority_refs=(
            "authority://case/dell",
            "authority://evidence/s1",
            "authority://numeric/s2",
        ),
        counterevidence_refs=("EV::DELL::PULL-FORWARD",),
        open_question_refs=("QUESTION::DELL::DURABILITY",),
    )
    resume = resume_agent_session(
        session=session,
        events=events,
        checkpoint=checkpoint,
        expected_case_id="DELL",
        expected_case_version="current-v1.4",
        expected_as_of_date="2026-08-06",
        expected_active_plan_ref="plan://agent-runtime-feedback-proof/r1",
        resumed_at=recorded_at,
        required_authority_refs=(
            "authority://case/dell",
            "authority://evidence/s1",
            "authority://numeric/s2",
        ),
        required_open_gap_refs=("GAP::DELL::PRODUCT-PROFIT",),
        required_unresolved_feedback_refs=tuple(
            row["feedback_id"] for row in all_feedback
        ),
        required_counterevidence_refs=("EV::DELL::PULL-FORWARD",),
        required_open_question_refs=("QUESTION::DELL::DURABILITY",),
    )

    plan_delta = {
        "plan_delta_id": "PLANDELTA::ZERO-CALL-R1",
        "session_id": session["session_id"],
        "base_plan_digest": canonical_digest(session["active_plan_ref"]),
        "proposed_by_agent_id": "S3.originating_research_node",
        "reason_feedback_refs": [verifier_receipts[0]["feedback_id"]],
        "add_actions": [],
        "modify_actions": ["reconcile_false_absence_against_case_truth"],
        "defer_actions": [],
        "cancel_actions": [],
        "expected_information_gain": "remove false absence without changing evidence authority",
        "budget_impact": {"model_calls": 0, "tool_calls": 0},
        "validation_status": "pending",
    }
    graph_delta = {
        "graph_delta_id": "GRAPHDELTA::ZERO-CALL-R1",
        "session_id": session["session_id"],
        "base_graph_digest": canonical_digest("graph://zero-call-proof"),
        "proposed_by_agent_id": "S3.originating_research_node",
        "edge_additions": [],
        "edge_corrections": [],
        "edge_retractions": [],
        "supporting_evidence_refs": [],
        "hypothesis_only_edges": [],
        "validation_status": "pending",
    }
    stop = {
        "stop_decision_id": "STOP::ZERO-CALL-R1",
        "session_id": session["session_id"],
        "decided_by_agent_id": "Harness",
        "decision": "pause_for_tool_recovery",
        "reason_codes": ["S1_EVIDENCE_AND_EXTERNAL_BLIND_GATES_OPEN"],
        "coverage_state_refs": ["coverage://s1/human-operability-r1"],
        "unresolved_feedback_refs": [row["feedback_id"] for row in all_feedback],
        "remaining_gap_refs": ["GAP::DELL::PRODUCT-PROFIT"],
        "budget_state": {"generation_model_calls": 0, "paid_tool_calls": 0},
        "quality_risk": "S1 Evidence admission and external blind gates remain open",
        "harness_validation_status": "accepted",
    }
    for kind, value in (
        ("AgentSession", session),
        ("FeedbackReceipt", all_feedback[0]),
        ("PlanDelta", plan_delta),
        ("GraphDelta", graph_delta),
        ("ContextCheckpoint", checkpoint),
        ("StopDecision", stop),
    ):
        validate_runtime_artifact(kind, value)

    examples = {
        "S1_source_present_retrieval": next(
            row
            for row in s1_receipts
            if row["failure_code"]
            == "source_present_candidate_material_requirement_not_recalled"
        )["model_visible_summary"],
        "S1_admission": next(
            row for row in s1_receipts if row["failure_code"] == "reviewed_evidence_admission_pending"
        )["model_visible_summary"],
        "S2": s2_receipts[0]["model_visible_summary"],
        "Verifier": verifier_receipts[0]["model_visible_summary"],
    }
    unsigned = {
        "schema_version": "fin_ia_agent_runtime_feedback_zero_call_proof_v1_0",
        "status": "zero_call_session_checkpoint_resume_and_feedback_routing_engineering_pass",
        "recorded_at": recorded_at,
        "source_bindings": {
            ref: _sha256(ref)
            for ref in (
                *READINESS_REFS.values(),
                HUMAN_OPERABILITY_PROGRAM_REF,
                MU_SOURCE_TRUTH_REF,
                VERIFIER_ASSESSMENT_REF,
            )
        },
        "execution": {
            "generation_model_calls": 0,
            "network_calls": 0,
            "paid_tool_calls": 0,
            "events": len(events),
            "feedback_receipts": len(all_feedback),
        },
        "session_proof": {
            "session_id": session["session_id"],
            "event_tail_digest": events[-1]["event_digest"],
            "checkpoint_digest": checkpoint["checkpoint_digest"],
            "resume_receipt_digest": resume["resume_receipt_digest"],
            "six_artifact_contracts_validated": True,
            "material_state_preserved": True,
        },
        "feedback_summary": {
            "S1": s1_by_case,
            "S2": {"typed_gap": 1, "typed_conflict": 1},
            "Verifier": {"material_findings": len(verifier_receipts)},
            "responsibility_planes": sorted(
                {row["owning_plane"] for row in all_feedback}
            ),
        },
        "business_examples_zh": examples,
        "authority": {
            "failed_runs_relabelled": False,
            "candidate_promoted": False,
            "numeric_fact_created": False,
            "public_gap_declared": False,
            "S1_qualified_stable": False,
            "natural_reflection_live_authorized": False,
            "release_authority": False,
        },
    }
    return {**unsigned, "result_digest": canonical_digest(unsigned)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recorded-at", default="2026-08-19T12:00:00+08:00")
    args = parser.parse_args()
    print(json.dumps(compile_proof(args.recorded_at), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
