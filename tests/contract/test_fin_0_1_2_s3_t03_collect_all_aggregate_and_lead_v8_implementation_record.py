from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AGGREGATE = ROOT / (
    "configs/releases/fin_ia_0_1_2_s3_t03_nvda_quarantined_collect_all_"
    "diagnostic_aggregate_and_stage_disposition_v1_0.json"
)
IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_2_s3_t03_research_lead_v8_local_semantic_"
    "materialization_minimum_zero_call_implementation_v1_0.json"
)
PROJECTION = ROOT / (
    "configs/runtime/fin_ia_0_1_2_current_program_projection_v2_30.json"
)
FORMAL_FAILURE = ROOT / (
    "configs/releases/fin_ia_0_1_2_s3_t03_nvda_exact_live_execution_"
    "terminal_failure_result_v1_0.json"
)
BACKLOG = ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
NEXT = (
    "FIN-0.1.2-S3-T03-RESEARCH-LEAD-V8-LOCAL-SEMANTIC-"
    "MATERIALIZATION-INDEPENDENT-ZERO-CALL-PROOF-DECISION"
)


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_collect_all_aggregate_preserves_formal_failure_and_stage_boundary() -> None:
    aggregate = _json(AGGREGATE)
    assert aggregate["status"] == (
        "diagnostic_complete_non_promotable_structural_S3_T03_repair_selected"
    )
    assert aggregate["formal_source"]["result_sha256"] == _sha256(
        FORMAL_FAILURE
    )
    assert aggregate["formal_source"]["business_artifacts"] == 0
    diagnostic = aggregate["diagnostic_result"]
    assert diagnostic["source_capture_replays"] == 7
    assert diagnostic["new_live_calls"] == ["memo_writer", "verifier"]
    assert diagnostic["quarantined_artifact_count"] == 9
    assert diagnostic["business_artifact_promotions"] == 0
    assert aggregate["stage_disposition"]["S3_T04"].startswith(
        "blocked_until_a_fresh_replacement"
    )
    assert aggregate["next_action"] == NEXT


def test_lead_v8_record_binds_current_code_and_does_not_claim_acceptance() -> None:
    implementation = _json(IMPLEMENTATION)
    assert implementation["design"]["research_lead_transport_ref"].endswith(
        ":v8"
    )
    for relative, digest in implementation["exact_code_bindings"].items():
        assert _sha256(ROOT / relative) == digest
    proofs = implementation["proofs"]
    assert proofs["natural_failed_Lead_body_reused_without_C002_C003_manual_swap"]
    assert proofs["natural_failed_Lead_body_false_fact_narrative_survived"] is False
    assert proofs["current_NVDA_full_fake_9_artifacts"]
    assert proofs["model_provider_network_calls"] == 0
    assert set(implementation["acceptance_boundary"].values()) == {False}
    assert implementation["next_action"] == NEXT


def test_current_projection_and_backlog_point_only_to_independent_proof() -> None:
    projection = _json(PROJECTION)
    assert projection["decision_binding"]["sha256"] == _sha256(AGGREGATE)
    assert projection["decision_binding"]["bytes"] == AGGREGATE.stat().st_size
    assert projection["current_truth"]["current_next_action"] == NEXT
    assert projection["current_truth"]["current_NVDA_R2"] is False
    assert projection["execution_policy"][
        "replacement_admission_or_execution_authorized"
    ] is False
    backlog = _json(BACKLOG)
    assert backlog["next_action"]["item_id"] == NEXT
    assert backlog["next_action"]["current_projection_ref"].endswith(
        "current_program_projection_v2_30.json"
    )
    assert backlog["next_action"]["current_projection_sha256"] == _sha256(
        PROJECTION
    )
