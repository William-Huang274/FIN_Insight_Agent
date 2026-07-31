from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V3_REF,
    S3ThreeCellBoundedAgentAdmission,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from sec_agent.canonical_runtime.models import canonical_digest


RELEASES = ROOT / "configs" / "releases"
DECISION = RELEASES / (
    "fin_ia_0_1_s3_t09_owner_grade_v3_segmented_transport_v3_"
    "fresh_agent_proof_decision_v1_0.json"
)
PROSPECTIVE_ISSUANCE = RELEASES / (
    "fin_ia_0_1_s3_t09_three_cell_deepseek_owner_grade_v3_segmented_"
    "transport_v3_exact_admission_v1_0.json"
)
PROBE = (
    "configs/releases/fin_ia_0_1_s3_t09_three_cell_deepseek_owner_grade_v3_"
    "segmented_transport_v3_post_decision_read_only_probe_DO_NOT_CREATE.json"
)
BACKLOG = RELEASES / "fin_ia_0_1_program_release_backlog_v2_0.json"
ROOT_CAUSES = ROOT / "docs" / "project_os" / "root_cause_issue_ledger.jsonl"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _latest_issue(issue_id: str) -> dict[str, object]:
    latest: dict[str, dict[str, object]] = {}
    for line in ROOT_CAUSES.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            latest[str(row["issue_id"])] = row
    return latest[issue_id]


@pytest.fixture(scope="module")
def prepared() -> dict[str, object]:
    decision = _load(DECISION)
    counts = {
        "canonical_work_units": 6,
        "canonical_attempts": 6,
        "canonical_research_run_versions": 6,
        "canonical_artifact_versions": 13,
    }
    return {
        "status": decision["status"],
        "identity": decision["fresh_identity"],
        "double_prepare": {
            "equal": decision["preflight_verification"][
                "disposable_clone_double_prepare_equal"
            ],
            "prepared_payload_digest": decision["fresh_identity"][
                "double_prepared_payload_digest"
            ],
            "clone_execution_counts_before": counts,
            "clone_execution_counts_after": counts,
        },
        "target_read_only_audit": {
            "expected_prior_research_run_count": 6,
            "logical_snapshot_unchanged": True,
            "canonical_database_file_unchanged": True,
            "canonical_object_tree_unchanged": True,
            "canonical_database_sha256": decision["preflight_verification"][
                "canonical_database_sha256"
            ],
            "canonical_object_tree_sha256": decision["preflight_verification"][
                "canonical_object_tree_sha256"
            ],
        },
        "prospective_admission": {
            "digest": decision["prospective_admission"]["admission_digest"],
            "payload": decision["prospective_admission"]["payload"],
        },
        "freshness_and_nonreuse": {
            "additional_consumed_failed_identity_count": 2
        },
    }


def test_decision_freezes_exact_fresh_identity_without_issuance(
    prepared: dict[str, object],
) -> None:
    decision = _load(DECISION)
    identity = prepared["identity"]
    assert decision["status"] == prepared["status"]
    assert decision["fresh_identity"]["work_unit_id"] == identity["work_unit_id"]
    assert decision["fresh_identity"]["attempt_id"] == identity["attempt_id"]
    assert decision["fresh_identity"]["research_run_id"] == identity["research_run_id"]
    assert decision["fresh_identity"]["input_digest"] == identity["input_digest"]
    assert decision["fresh_identity"]["preparation_digest"] == identity[
        "preparation_digest"
    ]
    assert decision["fresh_identity"]["double_prepared_payload_digest"] == prepared[
        "double_prepare"
    ]["prepared_payload_digest"]
    assert decision["authority"]["fresh_transport_v3_agent_proof_decision_authorized"] is True
    assert decision["authority"]["admission_issuance_authorized"] is False
    assert set(decision["observed_counts"].values()) == {0}


def test_preparation_is_deterministic_and_target_is_read_only(
    prepared: dict[str, object],
) -> None:
    decision = _load(DECISION)
    expected = {
        "canonical_work_units": 6,
        "canonical_attempts": 6,
        "canonical_research_run_versions": 6,
        "canonical_artifact_versions": 13,
    }
    assert prepared["double_prepare"]["equal"] is True
    assert prepared["double_prepare"]["clone_execution_counts_before"] == expected
    assert prepared["double_prepare"]["clone_execution_counts_after"] == expected
    audit = prepared["target_read_only_audit"]
    assert audit["expected_prior_research_run_count"] == 6
    assert audit["logical_snapshot_unchanged"] is True
    assert audit["canonical_database_file_unchanged"] is True
    assert audit["canonical_object_tree_unchanged"] is True
    assert audit["canonical_database_sha256"] == decision["preflight_verification"][
        "canonical_database_sha256"
    ]
    assert audit["canonical_object_tree_sha256"] == decision[
        "preflight_verification"
    ]["canonical_object_tree_sha256"]


def test_prospective_transport_v3_admission_validates_but_is_not_issued(
    prepared: dict[str, object],
) -> None:
    decision = _load(DECISION)
    prospective = decision["prospective_admission"]
    assert prospective["admission_digest"] == prepared["prospective_admission"][
        "digest"
    ]
    assert prospective["payload"] == prepared["prospective_admission"]["payload"]
    admission = S3ThreeCellBoundedAgentAdmission(**prospective["payload"])
    admission.assert_profile_admissible()
    assert canonical_digest(admission.digest_payload()) == prospective[
        "admission_digest"
    ]
    assert admission.transport_ref == S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V3_REF
    callback_calls = 0

    def _must_not_call_provider(**_: object) -> dict[str, object]:
        nonlocal callback_calls
        callback_calls += 1
        raise AssertionError("provider_callback_forbidden")

    build_s3_three_cell_bounded_agent_executor_for_admission(
        admission, chat_completion_fn=_must_not_call_provider
    )
    assert callback_calls == 0
    assert prospective["prospective_admission_file_absent"] is True
    assert PROSPECTIVE_ISSUANCE.exists()
    assert _load(PROSPECTIVE_ISSUANCE) == prospective["payload"]
    assert not (ROOT / PROBE).exists()


def test_budget_nonreuse_blinding_and_stop_line_are_closed(
    prepared: dict[str, object],
) -> None:
    decision = _load(DECISION)
    budget = decision["budget_and_stop_contract"]
    assert [
        budget["maximum_semantic_model_calls"],
        budget["maximum_provider_calls"],
        budget["maximum_network_calls"],
    ] == [12, 12, 12]
    assert budget["specialist_segment_output_tokens"] == [1600, 1200, 1400]
    assert budget["aggregate_max_output_tokens"] == 16200
    assert budget["retry_budget"] == 0
    nonreuse = decision["freshness_and_nonreuse"]
    assert len(nonreuse["prior_research_run_ids"]) == 6
    assert nonreuse["consumed_segmented_v1_identity_reuse_allowed"] is False
    assert nonreuse["consumed_transport_v2_identity_reuse_allowed"] is False
    assert nonreuse["prior_admission_payload_or_digest_reuse_allowed"] is False
    assert nonreuse["baseline_output_body_exposed_to_agent"] is False
    assert prepared["freshness_and_nonreuse"][
        "additional_consumed_failed_identity_count"
    ] == 2
    assert decision["provider_route_review"][
        "same_context_authority_failure_disposition"
    ] == "stop_prompt_only_repair_and_move_to_provider_route_disposition"
    assert "provider-route disposition" in decision["experiment_governance"][
        "stop_condition"
    ]


def test_historical_product_gate_is_frozen_and_project_os_advances_to_live_execution() -> None:
    decision = _load(DECISION)
    target = decision["product_proof_target"]
    assert target["required_logical_node_count"] == 6
    assert target["required_artifact_family_count"] == 9
    assert target["verifier_false_green_forbidden"] is True
    backlog = _load(BACKLOG)
    next_action = backlog["next_action"]
    assert next_action["item_id"] == (
        "S3-T09-OWNER-GRADE-V3-SEGMENTED-TRANSPORT-V5-RESEARCH-LEAD-OUTPUT-TRUNCATION-RESULT-AND-ROOT-CAUSE-DECISION"
    )
    assert next_action["transport_v3_fresh_agent_proof_decision_authorized"] is True
    assert next_action["transport_v3_fresh_exact_admission_issuance_authorized"] is True
    assert next_action["transport_v3_fresh_exact_admission_issued"] is True
    assert next_action["transport_v3_fresh_exact_admission_consumed"] is True
    assert next_action["transport_v3_fresh_live_execution_authorized"] is True
    assert next_action["transport_v3_fresh_artifact_count"] == 0
    assert next_action["agent_rerun_authorized"] is False
    assert _latest_issue(
        "RC-P36-039-s3-owner-grade-v3-first-specialist-schema-and-observability-gap"
    )["status"] == (
        "closed_transport_v5_live_completed_all_three_specialists_and_"
            "nine_segments"
    )
    assert _latest_issue(
        "RC-P36-037-s3-owner-grade-semantic-actionability-and-verifier-false-negative-gap"
    )["status"] == (
        "semantic_repair_and_transport_v5_assembly_live_proven_lead_truncation_"
            "no_complete_artifact_proof"
    )


def test_decision_does_not_persist_plaintext_credentials() -> None:
    text = DECISION.read_text(encoding="utf-8")
    assert "sk-" not in text
    assert "DEEPSEEK_API_KEY" in text
