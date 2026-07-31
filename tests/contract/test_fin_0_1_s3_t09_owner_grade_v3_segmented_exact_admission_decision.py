from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_REF,
    S3ThreeCellBoundedAgentAdmission,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from sec_agent.canonical_runtime.models import canonical_digest


RELEASES = ROOT / "configs" / "releases"
DECISION = (
    RELEASES
    / "fin_ia_0_1_s3_t09_owner_grade_v3_segmented_fresh_exact_admission_decision_v1_0.json"
)
ISSUANCE = (
    RELEASES
    / "fin_ia_0_1_s3_t09_owner_grade_v3_segmented_fresh_exact_admission_issuance_v1_0.json"
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


def test_decision_freezes_fresh_identity_without_issuance_or_execution() -> None:
    decision = _load(DECISION)
    assert decision["status"] == (
        "pass_fresh_segmented_v3_exact_admission_contract_decided_"
        "issuance_pending_separate_authority"
    )
    authority = decision["authority"]
    assert authority["fresh_segmented_exact_admission_decision_authorized"] is True
    assert authority["admission_issuance_authorized"] is False
    assert authority["admission_consumption_or_execution_authorized"] is False
    assert set(decision["observed_counts"].values()) == {0}
    assert decision["fresh_identity"]["research_run_id"] == (
        "research_run_fin01_613dad1d30f9ce5357213b21"
    )


def test_prospective_admission_payload_digest_and_factory_are_exact() -> None:
    decision = _load(DECISION)
    prospective = decision["prospective_admission"]
    payload = prospective["payload"]
    admission = S3ThreeCellBoundedAgentAdmission(**payload)
    admission.assert_profile_admissible()
    assert canonical_digest(admission.digest_payload()) == prospective["admission_digest"]
    assert admission.transport_ref == S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_REF
    assert (
        admission.max_semantic_model_calls,
        admission.max_provider_calls,
        admission.max_network_calls,
    ) == (12, 12, 12)
    assert admission.specialist_max_output_tokens == 4200
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
    issued_path = ROOT / prospective["prospective_admission_file"]
    assert issued_path.exists()
    assert _load(issued_path) == payload


def test_budget_nonreuse_blinding_and_first_failure_stop_are_frozen() -> None:
    decision = _load(DECISION)
    budget = decision["budget_and_stop_contract"]
    assert budget["specialist_segment_output_tokens"] == [1600, 1200, 1400]
    assert budget["aggregate_max_output_tokens"] == 16200
    assert budget["output_only_cost_ceiling_usd"] == 0.014094
    assert budget["maximum_total_cost_usd"] == 0.1
    assert budget["retry_budget"] == 0
    assert budget["automatic_repair_fallback_or_rerun"] is False
    assert budget["first_parse_shape_schema_semantic_or_length_failure"] == (
        "terminal_fail_closed_stop"
    )
    nonreuse = decision["freshness_and_nonreuse"]
    assert nonreuse["distinct_from_all_prior_agent_and_baseline_runs"] is True
    assert nonreuse["consumed_monolithic_v3_identity_reuse_allowed"] is False
    assert nonreuse["baseline_output_body_exposed_to_agent"] is False
    assert nonreuse["baseline_body_or_artifact_is_provider_input"] is False


def test_historical_clone_proof_remains_frozen_after_exact_issuance() -> None:
    decision = _load(DECISION)
    issuance = _load(ISSUANCE)
    assert decision["preflight_verification"]["disposable_clone_double_prepare_equal"] is True
    assert decision["preflight_verification"]["clone_execution_counts_unchanged"] is True
    assert decision["fresh_identity"]["double_prepared_payload_digest"] == (
        "65982670a912e82df4f10fe318d559781ce6078baaed5e2a3dc6cd98951fdd34"
    )
    assert issuance["source_decision_ref"] == (
        "configs/releases/fin_ia_0_1_s3_t09_owner_grade_v3_segmented_"
        "fresh_exact_admission_decision_v1_0.json"
    )
    assert issuance["issued_admission"]["admission_digest"] == decision[
        "prospective_admission"
    ]["admission_digest"]
    assert issuance["zero_call_preflight"]["canonical_database_sha256"] == decision[
        "preflight_verification"
    ]["canonical_database_sha256"]


def test_historical_decision_stays_frozen_and_remains_traced_in_backlog() -> None:
    decision = _load(DECISION)
    backlog = _load(BACKLOG)
    next_action = backlog["next_action"]
    assert decision["next_action"] == (
        "S3-T09-OWNER-GRADE-V3-SEGMENTED-SPECIALIST-FRESH-EXACT-ADMISSION-ISSUANCE"
    )
    assert next_action["fresh_segmented_exact_admission_decision_authorized"] is True
    assert next_action["fresh_segmented_exact_admission_issuance_authorized"] is True
    assert next_action["fresh_segmented_exact_admission_issued"] is True
    assert next_action["fresh_segmented_exact_admission_consumed"] is True
    assert next_action["agent_rerun_authorized"] is False
    issue = _latest_issue(
        "RC-P36-039-s3-owner-grade-v3-first-specialist-schema-and-observability-gap"
    )
    assert issue["status"] == (
        "closed_transport_v5_live_completed_all_three_specialists_and_"
            "nine_segments"
    )
    assert issue["full_chain_blocker"] is False
