from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3


ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_runtime_audit_evidence_v2_"
    "and_material_numeric_classifier_r5_exact_live_execution_failure_"
    "result_v1_0.json"
)
DISPOSITION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_r5_first_credible_failure_"
    "root_cause_scope_disposition_v1_0.json"
)
PROGRAM = ROOT / (
    "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)
DETAIL = ROOT / (
    "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)
ROOT_LEDGER = ROOT / "docs/project_os/root_cause_issue_ledger.jsonl"
RUNTIME_ROOT = ROOT / (
    ".codex_runtime/fin01-s3-t09-three-cell-deepseek-segmented-"
    "live-validation-r1"
)
SUPERVISION_ROOT = ROOT / (
    ".codex_runtime/fin01-s4-t06-mu-runtime-audit-numeric-classifier-"
    "r5-supervision-r1"
)
RUNNER = ROOT / (
    "scripts/releases/run_fin_ia_0_1_s3_t09_three_cell_deepseek_"
    "live_execution.py"
)
RUN_ID = "research_run_fin01_0b20402c2f8d5e5674626760"
NEXT = (
    "S4-T06-MU-ACTION-PLANNING-TEMPORAL-AUTHORITY-AND-CAPTURE-V2-"
    "TERMINAL-RESULT-MATERIALIZATION-MINIMUM-ZERO-CALL-IMPLEMENTATION"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _capture_path(digest: str) -> Path:
    return (
        RUNTIME_ROOT
        / "canonical-runtime/objects/fin01/provider-output-captures"
        / digest[:2]
        / digest[2:4]
        / f"{digest}.json"
    )


def _latest_issue(prefix: str) -> dict:
    rows = [
        json.loads(line)
        for line in ROOT_LEDGER.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return next(
        row for row in reversed(rows) if row["issue_id"].startswith(prefix)
    )


def test_R5_result_binds_exact_authority_and_terminal_usage() -> None:
    result = _load(RESULT)
    source = result["source_authority"]
    for ref_key, digest_key in (
        ("execution_authority_ref", "execution_authority_sha256"),
        ("admission_ref", "admission_sha256"),
        ("issuance_ref", "issuance_sha256"),
    ):
        assert _sha256(ROOT / source[ref_key]) == source[digest_key]

    assert result["status"] == (
        "terminal_failed_admission_consumed_no_retry_no_artifact_"
        "runner_result_materialization_failed"
    )
    terminal = result["terminal_truth"]
    assert [
        terminal["work_unit_state"],
        terminal["attempt_state"],
        terminal["research_run_state"],
    ] == ["failed", "failed", "failed"]
    assert terminal["target_run_artifacts"] == 0
    assert terminal["completed_logical_nodes"] == 0

    usage = result["usage_and_budget"]
    assert [
        usage["semantic_model_calls"],
        usage["provider_calls"],
        usage["network_calls"],
        usage["transport_attempts"],
    ] == [3, 3, 3, 3]
    assert [
        usage["input_tokens"],
        usage["output_tokens"],
        usage["total_tokens"],
    ] == [14122, 1406, 15528]
    assert usage["estimated_cost_usd"] == 0.00736628
    assert {
        usage["retry_count"],
        usage["fallback_count"],
        usage["replay_count"],
        usage["relaunch_count"],
        usage["rerun_count"],
    } == {0}


def test_R5_canonical_runtime_is_failed_failed_failed_with_zero_artifacts() -> None:
    result = _load(RESULT)
    identity = result["execution_identity"]
    connection = sqlite3.connect(
        "file:"
        + (
            RUNTIME_ROOT / "canonical-runtime/canonical.sqlite"
        ).resolve().as_posix()
        + "?mode=ro",
        uri=True,
    )
    try:
        observed = []
        for table, logical_id in (
            ("canonical_work_units", identity["work_unit_id"]),
            ("canonical_attempts", identity["attempt_id"]),
            (
                "canonical_research_run_versions",
                identity["research_run_id"],
            ),
        ):
            observed.append(
                connection.execute(
                    f"""
                    SELECT current_status
                    FROM {table}
                    WHERE logical_id = ?
                    ORDER BY row_id DESC
                    LIMIT 1
                    """,
                    (logical_id,),
                ).fetchone()[0]
            )
        artifact_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM canonical_artifact_versions
            WHERE json_extract(payload_json, '$.research_run_id') = ?
            """,
            (RUN_ID,),
        ).fetchone()[0]
    finally:
        connection.close()

    assert observed == ["failed", "failed", "failed"]
    assert artifact_count == 0


def test_R5_capture_v2_preserves_request_output_and_exact_failure_paths() -> None:
    result = _load(RESULT)
    capture_summary = result["capture_v2_evidence"]
    digests = capture_summary["capture_object_digests"]
    captures = []
    for digest in digests:
        path = _capture_path(digest)
        assert path.is_file()
        assert _sha256(path) == digest
        capture = _load(path)
        captures.append(capture)
        assert capture["schema_ref"] == (
            "fin01.provider_interaction_audit_capture:v2"
        )
        assert capture["capture_policy_ref"] == (
            "fin01.runtime.provider_interaction_audit_capture:v2"
        )
        assert capture["model_visible_request"]
        assert capture["assistant_output_text"]
        assert capture["credentials_included"] is False
        assert capture["private_reasoning_included"] is False
        assert capture["raw_provider_response_included"] is False

    failure_capture = captures[-1]
    assistant = json.loads(failure_capture["assistant_output_text"])
    assert [
        item["time_window"]["deadline_or_review_date"]
        for item in assistant["what_would_change"]
    ] == ["2026-09-30", "2026-09-30"]
    request = json.loads(failure_capture["model_visible_request"][1]["content"])
    assert request["case_numeric_authority_contract"][
        "allowed_reporting_period_labels"
    ] == ["2026-06-24", "2026-07-26", "FQ3_2026", "Q1 2026"]
    terminal_matches = [
        row
        for row in failure_capture["validator_match_index"]
        if row["terminal"]
    ]
    assert [row["field_path"] for row in terminal_matches] == [
        "$.what_would_change[0].time_window.deadline_or_review_date",
        "$.what_would_change[1].time_window.deadline_or_review_date",
    ]
    assert {row["semantic_class"] for row in terminal_matches} == {
        "unknown_reporting_period_label"
    }
    assert capture_summary["failed_output_promoted_to_business_artifact"] is (
        False
    )


def test_R5_runner_and_supervision_gaps_are_reconstructable_and_separate() -> None:
    result = _load(RESULT)
    observation = result["supervision_and_runner_observation"]
    runner_source = RUNNER.read_text(encoding="utf-8")
    exit_receipt = _load(SUPERVISION_ROOT / "exit_receipt.json")
    final_stderr = SUPERVISION_ROOT / "runner.stderr.log"

    assert "S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF" not in runner_source
    assert "admission.provider_output_capture_policy_ref" in runner_source
    assert (
        'raise RuntimeError("s3_t09_provider_output_capture_policy_mismatch")'
        not in runner_source
    )
    assert observation["canonical_failure_preceded_runner_exception"] is True
    assert observation["runner_result_materialized"] is False
    assert observation["post_terminal_exception"] == (
        "s3_t09_provider_output_capture_policy_mismatch"
    )
    assert exit_receipt["stderr_bytes"] == 299
    assert final_stderr.stat().st_size == 1073
    assert _sha256(final_stderr) == observation["final_stderr_sha256"]
    assert exit_receipt["stderr_sha256"] != _sha256(final_stderr)
    assert observation["exit_receipt_stderr_digest_matches_final_stderr"] is (
        False
    )


def test_R5_disposition_stops_paid_chain_and_advances_only_zero_call_scope() -> None:
    result = _load(RESULT)
    disposition = _load(DISPOSITION)
    program = _load(PROGRAM)
    detail = _load(DETAIL)

    assert disposition["source_failure"]["failure_result_sha256"] == _sha256(
        RESULT
    )
    root_cause = disposition["root_cause_hierarchy"]
    assert root_cause["provider_proximate_cause"]["established"] is True
    assert root_cause["earliest_project_owned_contract_cause"][
        "established"
    ] is True
    assert disposition["next_action"] == NEXT
    assert disposition["next_action_authorized"] is False
    progressed = (
        "S4-T06-MU-ACTION-PLANNING-TEMPORAL-AUTHORITY-AND-CAPTURE-V2-"
        "TERMINAL-RESULT-MATERIALIZATION-FRESH-AGENT-PROOF-DECISION"
    )
    assert program["next_action"]["item_id"] in {NEXT, progressed}
    assert detail["current_next_action"] in {NEXT, progressed}
    assert result["acceptance_disposition"][
        "automatic_R6_authorized_or_performed"
    ] is False
    assert result["acceptance_disposition"][
        "paired_assessment_performed"
    ] is False
    assert result["acceptance_disposition"]["S4_T07_entered"] is False

    rc_080 = _latest_issue("RC-P36-080")
    rc_081 = _latest_issue("RC-P36-081")
    rc_082 = _latest_issue("RC-P36-082")
    assert rc_080["status"] == "open"
    assert rc_080["verification_result"][
        "model_field_level_instruction_noncompliance"
    ] is True
    assert rc_080["verification_result"][
        "financial_fact_error_established"
    ] is False
    assert rc_081["status"].startswith("closed_")
    assert rc_082["status"] == "open"
    assert rc_082["allowed_run_scopes"] in [
        [
            NEXT.replace("-", "_"),
            "repository_and_git_hygiene",
        ],
        [
            progressed.replace("-", "_"),
            "repository_and_git_hygiene",
        ],
    ]
