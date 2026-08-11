from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3


ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_fresh_exact_live_"
    "execution_failure_result_v1_0.json"
)
CANONICAL_DATABASE = ROOT / (
    ".codex_runtime/fin01-s3-t09-three-cell-deepseek-segmented-"
    "live-validation-r1/canonical-runtime/canonical.sqlite"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _logical_payload(table: str, logical_id: str) -> dict:
    logical_id_field = {
        "canonical_work_units": "work_unit_id",
        "canonical_attempts": "attempt_id",
        "canonical_research_run_versions": "research_run_id",
    }[table]
    connection = sqlite3.connect(CANONICAL_DATABASE)
    try:
        rows = [
            json.loads(payload_json)
            for (payload_json,) in connection.execute(
                f"select payload_json from {table}"
            )
        ]
    finally:
        connection.close()
    matches = [
        row for row in rows if row.get(logical_id_field) == logical_id
    ]
    return matches[-1]


def test_mu_failure_result_binds_exact_execution_evidence() -> None:
    result = _load(RESULT)

    assert result["status"] == (
        "terminal_failed_research_lead_fact_presence_summary_mismatch_"
        "no_retry_no_paired_assessment"
    )
    assert result["authority"]["decision_sha256"] == _sha256(
        ROOT / result["authority"]["decision_ref"]
    )
    for ref_key, sha_key in (
        ("admission_ref", "admission_sha256"),
        ("issuance_ref", "issuance_sha256"),
    ):
        assert _sha256(ROOT / result["source_binding"][ref_key]) == (
            result["source_binding"][sha_key]
        )
    for ref_key, sha_key in (
        ("project_os_preflight_ref", "project_os_preflight_sha256"),
        ("runner_preflight_ref", "runner_preflight_sha256"),
        ("runtime_result_ref", "runtime_result_sha256"),
        ("terminal_inspection_ref", "terminal_inspection_sha256"),
        ("launch_receipt_ref", "launch_receipt_sha256"),
        ("exit_receipt_ref", "exit_receipt_sha256"),
    ):
        assert _sha256(ROOT / result["execution_evidence"][ref_key]) == (
            result["execution_evidence"][sha_key]
        )


def test_mu_failure_is_terminal_consistent_non_orphan_and_zero_artifact() -> None:
    result = _load(RESULT)
    binding = result["source_binding"]
    truth = result["canonical_terminal_truth"]

    assert truth["terminal_consistent"] is True
    assert truth["orphaned_run"] is False
    assert truth["artifact_count"] == 0
    for table, logical_id in (
        ("canonical_work_units", binding["work_unit_id"]),
        ("canonical_attempts", binding["attempt_id"]),
        ("canonical_research_run_versions", binding["research_run_id"]),
    ):
        assert _logical_payload(table, logical_id)["state"] == "failed"


def test_mu_failure_preserves_calls_captures_and_exact_budget() -> None:
    result = _load(RESULT)
    provider = result["provider_execution"]
    capture = result["provider_output_capture"]

    assert (
        provider["completed_specialist_nodes"],
        provider["completed_specialist_segments"],
        provider["model_calls"],
        provider["provider_calls"],
        provider["network_calls"],
        provider["transport_attempts"],
    ) == (3, 9, 10, 10, 10, 10)
    assert provider["transport_failures"] == 0
    assert provider["research_lead_provider_status"] == "ok"
    assert provider["research_lead_finish_reason"] == "stop"
    assert provider["memo_writer_called"] is False
    assert provider["verifier_called"] is False
    assert provider["total_tokens"] == 58046
    assert provider["estimated_cost_usd"] == 0.02702893
    assert provider["estimated_cost_usd"] < provider["maximum_total_cost_usd"]
    assert (
        provider["retry_count"],
        provider["fallback_count"],
        provider["replay_count"],
        provider["relaunch_count"],
        provider["rerun_count"],
    ) == (0, 0, 0, 0, 0)
    assert (
        capture["usage_receipt_count"],
        capture["restricted_capture_count"],
        capture["restricted_readback_count"],
    ) == (10, 10, 10)
    assert capture["assistant_output_text_in_release_result"] is False
    assert capture["credential_value_persisted"] is False


def test_mu_first_failure_is_typed_semantic_not_transport_or_capacity() -> None:
    result = _load(RESULT)
    failure = result["first_credible_failure"]

    assert failure["stage"] == "research_lead"
    assert failure["failure_code"] == (
        "s3_bounded_research_lead_v3_semantic_"
        "fact_presence_summary_mismatch"
    )
    assert failure["validator_contract"] == "closed_research_lead_output:v3"
    assert failure["field_id"] == (
        "conflict_adjudications.fact_presence_summary"
    )
    assert failure["failing_item_count"] == 1
    assert failure["provider_transport_success"] is True
    assert failure["native_JSON_parse_failure"] is False
    assert failure["finish_reason_length_or_truncation"] is False
    assert failure["credential_network_rate_or_quota_failure"] is False
    assert failure["token_or_cost_ceiling_failure"] is False
    assert failure["final_root_cause_or_scope_disposition_completed"] is False


def test_mu_failure_stops_before_pairing_owner_acceptance_and_t07() -> None:
    result = _load(RESULT)
    stop = result["stop_contract_compliance"]

    assert stop["first_credible_failure_stopped_chain"] is True
    assert stop["automatic_second_execution_performed"] is False
    assert stop["same_input_deterministic_baseline_materialized"] is False
    assert stop["paired_assessment_performed"] is False
    assert stop[
        "paired_assessment_forbidden_because_terminal_success_absent"
    ] is True
    assert stop["owner_acceptance_performed"] is False
    assert stop["S4_T07_entered"] is False
    assert result["truth_and_product_acceptance"]["MU_R2"] is False
    assert result["next_action"] == (
        "S4-T06-MU-RESEARCH-LEAD-FACT-PRESENCE-SUMMARY-MISMATCH-"
        "FIRST-CREDIBLE-FAILURE-ROOT-CAUSE-OR-SCOPE-DISPOSITION-DECISION"
    )
