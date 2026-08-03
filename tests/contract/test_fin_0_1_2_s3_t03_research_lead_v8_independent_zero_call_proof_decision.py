from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from scripts.releases.prepare_fin_ia_0_1_2_s3_t03_research_lead_v8_independent_zero_call_proof import (
    DECISION,
    FORMAL_FAILURE,
    IMPLEMENTATION,
    NEXT_ACTION,
    build_decision,
)


PROJECTION = ROOT / (
    "configs/runtime/fin_ia_0_1_2_current_program_projection_v2_31.json"
)
BACKLOG = ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_frozen_decision_reproduces_two_fresh_process_proof() -> None:
    decision = _load(DECISION)
    assert build_decision() == decision
    proof = decision["fresh_process_proof"]
    assert proof["independent_processes"] == 2
    assert proof["distinct_disposable_roots"] == 2
    assert proof["normalized_outputs_equal"] is True
    assert proof["credential_environment_scrubbed_before_import"] is True
    assert proof["socket_network_guard_installed"] is True
    assert proof["diagnostic_capture_replay_or_repair_callback_used"] is False


def test_current_nvda_full_fake_and_mutation_matrix_passes() -> None:
    matrix = _load(DECISION)["fresh_process_proof"]["matrix"]
    assert matrix["status"] == "pass"
    assert matrix["current_input"]["mutation_rejected"] is True
    assert matrix["current_full_fake"] == {
        "logical_nodes": 6,
        "logical_interactions": 12,
        "local_fact_receipts": 3,
        "provider_calls": 9,
        "provider_captures": 9,
        "artifacts": 9,
        "artifact_types": [
            "agent_fallback_comparison",
            "bounded_agent_evidence",
            "bounded_agent_judgment",
            "bounded_agent_manifest",
            "bounded_agent_numeric",
            "bounded_agent_report",
            "bounded_agent_trace",
            "bounded_agent_verification",
            "bounded_agent_workpaper",
        ],
    }
    adjacent = matrix["adjacent_alias_semantic_mutation"]
    assert adjacent["provider_narrative_survived"] is False
    assert adjacent["selected_dependency_claim_count"] == 1
    assert adjacent["selected_conflict_claim_count"] == 2
    assert adjacent["local_resolution_status"] == "unresolved"
    assert adjacent["artifacts"] == 9
    assert set(matrix["negative_mutations"]) == {
        "runtime_owned_field",
        "unknown_alias",
        "duplicate_alias",
    }
    assert all(
        row["stage"] == "research_lead"
        for row in matrix["negative_mutations"].values()
    )
    assert set(matrix["hard_boundaries"].values()) == {0}


def test_implementation_and_primary_failure_remain_immutable() -> None:
    decision = _load(DECISION)
    implementation = _load(IMPLEMENTATION)
    source = decision["source_bindings"]
    assert source["implementation"]["sha256"] == _sha256(IMPLEMENTATION)
    assert source["immutable_primary_failure"]["sha256"] == _sha256(
        FORMAL_FAILURE
    )
    assert source["immutable_primary_failure"]["status"] == "failed"
    assert source["immutable_primary_failure"]["artifacts"] == 0
    assert source["immutable_primary_failure"]["reclassified"] is False
    for relative, digest in implementation["exact_code_bindings"].items():
        assert _sha256(ROOT / relative) == digest


def test_proof_advances_only_to_replacement_admission_authority() -> None:
    decision = _load(DECISION)
    assert decision["status"] == (
        "pass_independent_two_fresh_process_zero_call_proof_"
        "replacement_admission_authority_pending"
    )
    assert decision["next_action"] == NEXT_ACTION
    boundary = decision["acceptance_boundary"]
    assert boundary["Lead_v8_engineering_proof"] is True
    assert set(
        value
        for key, value in boundary.items()
        if key != "Lead_v8_engineering_proof"
    ) == {False}
    governance = decision["experiment_governance"]
    assert governance[
        "replacement_admission_authority_decision_authorized_next"
    ] is True
    assert governance["replacement_admission_issuance_authorized_now"] is False
    assert governance["live_execution_authorized_now"] is False
    assert governance["third_exact_attempt_ever_authorized"] is False
    assert decision["root_cause_disposition"]["closed"] is False


def test_generator_binding_is_current() -> None:
    decision = _load(DECISION)
    generator = decision["proof_generator"]
    assert generator["sha256"] == _sha256(ROOT / generator["ref"])


def test_current_projection_and_backlog_advance_only_to_authority_decision() -> None:
    decision = _load(DECISION)
    projection = _load(PROJECTION)
    backlog = _load(BACKLOG)["next_action"]
    assert projection["decision_binding"]["sha256"] == _sha256(DECISION)
    assert projection["decision_binding"]["bytes"] == DECISION.stat().st_size
    assert projection["current_truth"]["current_next_action"] == NEXT_ACTION
    assert projection["current_truth"]["current_NVDA_R2"] is False
    policy = projection["execution_policy"]
    assert policy["replacement_admission_authority_decision_authorized_next"]
    assert not policy["replacement_admission_issuance_authorized_now"]
    assert not policy["replacement_exact_live_execution_authorized_now"]
    assert backlog["item_id"] == NEXT_ACTION
    assert backlog["current_projection_ref"].endswith(
        "current_program_projection_v2_31.json"
    )
    assert backlog["current_projection_sha256"] == _sha256(PROJECTION)
    assert backlog["S3_T03_Lead_v8_independent_proof_sha256"] == _sha256(
        DECISION
    )
    assert backlog["S3_T03_replacement_admission_issued"] is False
    assert backlog["S3_T03_replacement_exact_live_executed"] is False
