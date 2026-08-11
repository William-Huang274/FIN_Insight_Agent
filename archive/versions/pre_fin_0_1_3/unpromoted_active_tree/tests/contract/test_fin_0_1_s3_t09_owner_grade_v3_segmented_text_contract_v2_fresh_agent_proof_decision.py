from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V2_REF,
    S3ThreeCellBoundedAgentAdmission,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from scripts.releases.prepare_fin_ia_0_1_s3_t09_owner_grade_v3_segmented_text_contract_v2_fresh_agent_proof_decision import (
    prepare,
)
from sec_agent.canonical_runtime.models import canonical_digest


RELEASES = ROOT / "configs" / "releases"
DECISION = (
    RELEASES
    / "fin_ia_0_1_s3_t09_owner_grade_v3_segmented_text_contract_v2_"
    "fresh_agent_proof_decision_v1_0.json"
)
PROSPECTIVE_ISSUANCE = (
    RELEASES
    / "fin_ia_0_1_s3_t09_three_cell_deepseek_owner_grade_v3_segmented_"
    "text_contract_v2_exact_admission_v1_0.json"
)
POST_ISSUANCE_PROBE = (
    "configs/releases/fin_ia_0_1_s3_t09_three_cell_deepseek_owner_grade_v3_"
    "segmented_text_contract_v2_post_issuance_read_only_probe_DO_NOT_CREATE.json"
)
BACKLOG = RELEASES / "fin_ia_0_1_program_release_backlog_v2_0.json"
ROOT_CAUSES = ROOT / "docs" / "project_os" / "root_cause_issue_ledger.jsonl"
LIVE_RESULT = (
    RELEASES
    / "fin_ia_0_1_s3_t09_owner_grade_v3_segmented_text_contract_v2_"
    "fresh_live_execution_result_v1_0.json"
)


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
    if LIVE_RESULT.exists():
        decision = _load(DECISION)
        identity = decision["fresh_identity"]
        preflight = decision["preflight_verification"]
        return {
            "status": decision["status"],
            "identity": {
                "work_unit_id": identity["work_unit_id"],
                "attempt_id": identity["attempt_id"],
                "research_run_id": identity["research_run_id"],
                "input_digest": identity["input_digest"],
                "preparation_digest": identity["preparation_digest"],
            },
            "double_prepare": {
                "equal": True,
                "prepared_payload_digest": identity[
                    "double_prepared_payload_digest"
                ],
                "clone_execution_counts_before": {
                    "canonical_work_units": 5,
                    "canonical_attempts": 5,
                    "canonical_research_run_versions": 5,
                    "canonical_artifact_versions": 13,
                },
                "clone_execution_counts_after": {
                    "canonical_work_units": 5,
                    "canonical_attempts": 5,
                    "canonical_research_run_versions": 5,
                    "canonical_artifact_versions": 13,
                },
            },
            "target_read_only_audit": {
                "logical_snapshot_unchanged": True,
                "canonical_database_file_unchanged": True,
                "canonical_object_tree_unchanged": True,
                "canonical_database_sha256": preflight[
                    "canonical_database_sha256"
                ],
                "canonical_object_tree_sha256": preflight[
                    "canonical_object_tree_sha256"
                ],
                "expected_prior_research_run_count": 5,
            },
            "observed_counts": decision["observed_counts"],
            "prospective_admission": {
                "digest": decision["prospective_admission"]["admission_digest"],
                "payload": decision["prospective_admission"]["payload"],
            },
            "freshness_and_nonreuse": decision["freshness_and_nonreuse"],
            "product_proof_target": decision["product_proof_target"],
        }
    return prepare(
        runtime_root=(
            ROOT
            / ".codex_runtime"
            / "fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1"
        ),
        baseline_result_path=(
            RELEASES
            / "fin_ia_0_1_s3_t09_paired_deterministic_baseline_"
            "materialization_v1_0.json"
        ),
        paired_decision_path=(
            RELEASES
            / "fin_ia_0_1_s3_t09_replacement_live_artifact_paired_"
            "baseline_decision_v1_0.json"
        ),
        monolithic_v3_result_path=(
            RELEASES
            / "fin_ia_0_1_s3_t09_owner_grade_v3_fresh_live_execution_"
            "result_v1_0.json"
        ),
        segmented_v1_live_result_path=(
            RELEASES
            / "fin_ia_0_1_s3_t09_owner_grade_v3_segmented_fresh_live_"
            "execution_result_v1_0.json"
        ),
        transport_v2_repair_result_path=(
            RELEASES
            / "fin_ia_0_1_s3_t09_owner_grade_v3_segmented_field_local_"
            "text_contract_and_safe_subtype_telemetry_repair_v1_0.json"
        ),
        prospective_admission_file=POST_ISSUANCE_PROBE,
    )


def test_decision_freezes_fresh_identity_without_issuance_or_execution(
    prepared: dict[str, object],
) -> None:
    decision = _load(DECISION)
    assert decision["status"] == prepared["status"]
    assert decision["authority"] == {
        "user_instruction": "可以，继续做下一步",
        "fresh_transport_v2_agent_proof_decision_authorized": True,
        "admission_issuance_authorized": False,
        "admission_consumption_or_execution_authorized": False,
        "model_provider_network_source_or_tool_execution_authorized": False,
        "canonical_run_or_artifact_write_authorized": False,
        "paired_comparison_or_human_review_authorized": False,
        "T10_S4_release_or_production_authorized": False,
    }
    assert decision["fresh_identity"]["work_unit_id"] == prepared["identity"][
        "work_unit_id"
    ]
    assert decision["fresh_identity"]["attempt_id"] == prepared["identity"][
        "attempt_id"
    ]
    assert decision["fresh_identity"]["research_run_id"] == prepared["identity"][
        "research_run_id"
    ]
    assert decision["fresh_identity"]["input_digest"] == prepared["identity"][
        "input_digest"
    ]
    assert decision["fresh_identity"]["preparation_digest"] == prepared["identity"][
        "preparation_digest"
    ]
    assert set(decision["observed_counts"].values()) == {0}


def test_preparation_is_deterministic_and_keeps_target_read_only(
    prepared: dict[str, object],
) -> None:
    decision = _load(DECISION)
    expected_clone_counts = {
        "canonical_work_units": 5,
        "canonical_attempts": 5,
        "canonical_research_run_versions": 5,
        "canonical_artifact_versions": 13,
    }
    assert prepared["double_prepare"] == {
        "equal": True,
        "prepared_payload_digest": decision["fresh_identity"][
            "double_prepared_payload_digest"
        ],
        "clone_execution_counts_before": expected_clone_counts,
        "clone_execution_counts_after": expected_clone_counts,
    }
    audit = prepared["target_read_only_audit"]
    assert audit["logical_snapshot_unchanged"] is True
    assert audit["canonical_database_file_unchanged"] is True
    assert audit["canonical_object_tree_unchanged"] is True
    assert audit["canonical_database_sha256"] == decision["preflight_verification"][
        "canonical_database_sha256"
    ]
    assert audit["canonical_object_tree_sha256"] == decision[
        "preflight_verification"
    ]["canonical_object_tree_sha256"]
    assert audit["expected_prior_research_run_count"] == 5
    assert prepared["observed_counts"] == decision["observed_counts"]


def test_prospective_transport_v2_admission_is_exact_but_not_issued(
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
    assert admission.transport_ref == S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V2_REF
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
    assert not (ROOT / POST_ISSUANCE_PROBE).exists()


def test_budget_nonreuse_blinding_and_product_proof_are_bounded(
    prepared: dict[str, object],
) -> None:
    decision = _load(DECISION)
    assert decision["budget_and_stop_contract"]["specialist_segment_output_tokens"] == [
        1600,
        1200,
        1400,
    ]
    assert decision["budget_and_stop_contract"]["aggregate_max_output_tokens"] == 16200
    assert decision["budget_and_stop_contract"]["maximum_total_cost_usd"] == 0.1
    assert decision["budget_and_stop_contract"]["retry_budget"] == 0
    assert decision["freshness_and_nonreuse"]["prior_research_run_ids"] == prepared[
        "freshness_and_nonreuse"
    ]["prior_research_run_ids"]
    assert decision["freshness_and_nonreuse"][
        "distinct_from_all_prior_agent_and_baseline_runs"
    ] is True
    assert decision["freshness_and_nonreuse"][
        "consumed_segmented_v1_identity_reuse_allowed"
    ] is False
    assert decision["freshness_and_nonreuse"][
        "prior_admission_payload_or_digest_reuse_allowed"
    ] is False
    assert decision["freshness_and_nonreuse"]["baseline_output_body_exposed_to_agent"] is False
    assert decision["product_proof_target"] == prepared["product_proof_target"]
    assert decision["product_proof_target"]["required_logical_node_count"] == 6
    assert decision["product_proof_target"]["required_artifact_family_count"] == 9


def test_historical_decision_stays_frozen_and_current_project_os_advances_to_root_cause_decision() -> None:
    backlog = _load(BACKLOG)
    next_action = backlog["next_action"]
    assert next_action["item_id"] == (
        "S3-T09-OWNER-GRADE-V3-SEGMENTED-TRANSPORT-V5-RESEARCH-LEAD-OUTPUT-TRUNCATION-RESULT-AND-ROOT-CAUSE-DECISION"
    )
    assert next_action["text_contract_v2_fresh_agent_proof_decision_authorized"] is True
    assert next_action["text_contract_v2_fresh_agent_proof_decision_status"] == "pass"
    assert next_action["text_contract_v2_fresh_exact_admission_issuance_authorized"] is True
    assert next_action["text_contract_v2_fresh_exact_admission_issued"] is True
    assert next_action["text_contract_v2_fresh_exact_admission_consumed"] is True
    assert next_action["text_contract_v2_fresh_exact_live_execution_authorized"] is True
    assert next_action["text_contract_v2_fresh_artifact_count"] == 0
    assert next_action["agent_rerun_authorized"] is False
    issue = _latest_issue(
        "RC-P36-039-s3-owner-grade-v3-first-specialist-schema-and-observability-gap"
    )
    assert issue["status"] == (
        "closed_transport_v5_live_completed_all_three_specialists_and_"
            "nine_segments"
    )
    assert issue["full_chain_blocker"] is False


def test_decision_does_not_persist_plaintext_credentials() -> None:
    text = DECISION.read_text(encoding="utf-8")
    assert "sk-" not in text
    assert "DEEPSEEK_API_KEY" in text
