import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DECISION = ROOT / "configs/releases/fin_ia_0_1_2_s2_t04_blinded_paired_assessment_model_local_surface_disposition_and_s2_closeout_authority_decision_v1_0.json"
PROJECTION = ROOT / "configs/runtime/fin_ia_0_1_2_current_program_projection_v2_19.json"
BACKLOG = ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
ROOT_CAUSES = ROOT / "docs/project_os/root_cause_issue_ledger.jsonl"
CAPABILITIES = ROOT / "docs/project_os/capability_status_ledger.jsonl"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_decision_binds_exactly_six_fair_hard_pass_inputs():
    decision = load_json(DECISION)
    inputs = decision["fair_assessment_inputs"]
    assert inputs["outcome_count"] == 6
    assert inputs["hard_integrity_pass_count"] == 6
    assert len(inputs["selected_capture_sha256"]) == 6
    assert len(set(inputs["selected_capture_sha256"])) == 6
    assert len(inputs["excluded_primary_WWC_capture_sha256"]) == 2
    for binding in decision["bindings"]:
        path = ROOT / binding["ref"]
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == binding["sha256"]


def test_same_context_is_ineligible_and_mapping_is_revealed_only_after_score_freeze():
    decision = load_json(DECISION)
    independence = decision["independence_contract"]
    assert independence["current_task_or_same_context_is_eligible_to_score"] is False
    assert "fresh_isolated" in independence["eligible_assessor"]
    assert independence["mapping"]["storage"].startswith("separate_restricted")
    assert independence["mapping"]["assessor_packet_contains"] == "mapping_commitment_digest_only"
    assert "score_record" in independence["mapping"]["reveal_condition"]
    assert independence["mapping"]["mapping_change_after_packet_freeze"] == "forbidden"


def test_rubric_and_deterministic_selection_rules_are_frozen_before_scoring():
    decision = load_json(DECISION)
    rubric = decision["blind_quality_rubric"]
    assert set(rubric["dimensions"]) == {
        "evidence_selection_relevance",
        "epistemic_discipline",
        "decision_usefulness",
        "concise_information_density",
    }
    assert rubric["maximum_total_per_candidate"] == 24
    rules = decision["deterministic_post_score_rules"]
    assert "more than two points below Pro" in rules["stable_candidate_preference_rule"]
    assert rules["tie_or_quality_gap_at_most_two"] == "select_Flash_stable"
    threshold = rules["retained_model_surface_threshold_per_family"]
    assert threshold["family_total_minimum"] == 4
    assert threshold["evidence_selection_relevance_minimum"] == 1
    assert threshold["epistemic_discipline_minimum"] == 1
    assert threshold["decision_usefulness_minimum"] == 1
    assert rules["automatic_runtime_fallback"] is False


def test_this_decision_authorizes_packet_handoff_but_not_scoring_selection_or_closeout():
    decision = load_json(DECISION)
    authority = decision["authorized_next_work"]
    assert authority["zero_call_packet_builder_and_preflight_authorized"] is True
    assert authority["independent_assessor_handoff_authorized"] is True
    assert authority["another_authority_decision_required_before_packet_implementation"] is False
    assert authority["model_provider_or_execution_network_calls"] == 0
    assert authority["same_context_scoring_authorized"] is False
    counts = decision["current_turn_observed_counts"]
    assert counts["model_calls"] == counts["provider_calls"] == counts["execution_network_calls"] == 0
    assert counts["quality_scores_recorded"] == counts["models_selected"] == 0
    assert decision["closeout_gate"]["S2_closeout_allowed_in_this_decision"] is False
    assert decision["closeout_gate"]["S3_entry_allowed_in_this_decision"] is False
    assert decision["stage_acceptance"]["S2"] == "not_yet_passed"
    assert decision["next_action"].endswith("INDEPENDENT-EVALUATOR-HANDOFF-MINIMUM-ZERO-CALL-IMPLEMENTATION")


def test_historical_projection_remains_honest_after_current_backlog_advances():
    decision = load_json(DECISION)
    projection = load_json(PROJECTION)
    backlog = load_json(BACKLOG)["next_action"]
    decision_ref = DECISION.relative_to(ROOT).as_posix()
    decision_sha = hashlib.sha256(DECISION.read_bytes()).hexdigest()
    projection_ref = PROJECTION.relative_to(ROOT).as_posix()
    projection_sha = hashlib.sha256(PROJECTION.read_bytes()).hexdigest()

    assert projection["implementation_binding"] == {
        "ref": decision_ref,
        "sha256": decision_sha,
        "binding_role": "S2_T04_independent_identity_sealed_blind_assessment_authority_and_scope",
    }
    assert projection["current_truth"]["quality_scores_recorded"] == 0
    assert projection["current_truth"]["model_local_surface_disposition"] == "not_started"
    assert projection["execution_authority"]["S2_closeout_executed"] is False
    assert projection["execution_authority"]["S3_entry_authorized"] is False
    assert projection_ref.endswith("current_program_projection_v2_19.json")
    assert len(projection_sha) == 64
    assert backlog["item_id"] != decision["next_action"]
    assert backlog["current_projection_ref"].endswith(
        "current_program_projection_v2_21.json"
    )
    assert backlog["S2_T04_quality_scores_recorded"] == 2
    assert backlog["S2_T04_model_selected"] is True

    issue = next(
        row
        for row in load_jsonl(ROOT_CAUSES)
        if row["issue_id"].startswith("RC-P36-104-")
        and row["status"] == "open"
        and row["state_detail"].startswith("authority_scope_pass_")
    )
    assert issue["status"] == "open"
    assert issue["owned_by_project"] is True
    assert issue["model_or_provider_fault_established"] is False
    capability = [
        row
        for row in load_jsonl(CAPABILITIES)
        if row["capability_id"]
        == "fin_0_1_2_S2_T04_blinded_assessment_authority_and_independence_protocol"
    ][-1]
    assert capability["stage_acceptance"]["FIN_0_1_2_S2_T04_assessment"] == "not_started"
    assert capability["verification"]["quality_scores_recorded"] == 0
