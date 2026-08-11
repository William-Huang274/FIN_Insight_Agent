from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3


ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s3_t09_layered_verifier_typed_ref_and_finding_disposition_"
    "final_exact_live_and_paired_assessment_v1_0.json"
)
RUNTIME = ROOT / (
    ".codex_runtime/fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1/"
    "layered_verifier_typed_ref_finding_disposition_r1_live_execution_result.json"
)
DATABASE = ROOT / (
    ".codex_runtime/fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1/"
    "canonical-runtime/canonical.sqlite"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_exact_live_terminal_truth_calls_and_receipts_are_bound() -> None:
    assessment = _load(RESULT)
    runtime = _load(RUNTIME)

    assert assessment["status"] == (
        "pass_engineering_product_and_research_with_L4_quality_debt_"
        "owner_acceptance_pending"
    )
    assert runtime["status"] == "terminal_succeeded_admission_consumed_no_retry"
    assert runtime["canonical_terminal_truth"]["artifact_count"] == 9
    assert runtime["canonical_terminal_truth"]["orphaned_run"] is False
    assert assessment["exact_live_execution"]["canonical_terminal_states"] == [
        "succeeded",
        "succeeded",
        "succeeded",
    ]
    assert assessment["exact_live_execution"]["model_provider_network_calls"] == [
        12,
        12,
        12,
    ]
    assert assessment["exact_live_execution"][
        "retry_fallback_replay_relaunch_rerun_counts"
    ] == [0, 0, 0, 0, 0]
    for ref_key, digest_key in (
        ("runtime_result_ref", "runtime_result_sha256"),
        ("preflight_ref", "preflight_sha256"),
        ("launch_receipt_ref", "launch_receipt_sha256"),
        ("exit_receipt_ref", "exit_receipt_sha256"),
        ("paired_baseline_ref", "paired_baseline_sha256"),
        ("acceptance_standard_ref", "acceptance_standard_sha256"),
    ):
        source = assessment["source_evidence"]
        assert _sha256(ROOT / source[ref_key]) == source[digest_key]


def test_nine_artifacts_are_one_run_and_all_object_digests_verify() -> None:
    assessment = _load(RESULT)
    attempt_id = assessment["identity"]["attempt_id"]
    connection = sqlite3.connect(DATABASE.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        rows = connection.execute(
            "select logical_id, payload_json from canonical_artifact_versions "
            "order by row_id"
        ).fetchall()
    finally:
        connection.close()
    latest = {str(logical_id): json.loads(str(payload_json)) for logical_id, payload_json in rows}
    artifacts = {
        payload["artifact_type"]: payload
        for payload in latest.values()
        if payload.get("producer_attempt_id") == attempt_id
    }
    assert set(artifacts) == set(assessment["artifact_manifest"])
    object_root = DATABASE.parent / "objects"
    for artifact_type, expected in assessment["artifact_manifest"].items():
        artifact = artifacts[artifact_type]
        assert artifact["artifact_version_id"] == expected["artifact_ref"]
        assert artifact["object_digest"] == expected["object_digest"]
        assert _sha256(object_root / artifact["object_key"]) == expected["object_digest"]


def test_L1_L2_and_soft_quality_findings_match_current_product() -> None:
    runtime = _load(RUNTIME)
    artifacts = runtime["artifact_payloads"]
    cells = artifacts["bounded_agent_workpaper"]["cells"]
    fact_supported = [
        claim
        for cell in cells
        for claim in cell["judgment_layer"]
        if claim["epistemic_status"] == "fact_supported"
    ]
    assert len(fact_supported) == 1
    assert fact_supported[0]["scope"]["business_scope_kind"] == "company_total"
    assert fact_supported[0]["support_fact_ids"] == ["f1"]
    assert sum(len(cell["fact_layer"]) for cell in cells) == 1

    verification = artifacts["bounded_agent_verification"]["verification"]
    assert verification["decision"] == "accept_for_internal_review"
    assert [finding["status"] for finding in verification["findings"]] == [
        "pass",
        "pass",
        "pass",
        "pass",
    ]
    assert all(not finding["issue_codes"] for finding in verification["findings"])

    quality = artifacts["bounded_agent_judgment"]["quality_observations"]
    assert len(quality) == 3
    assert all(row["acceptance_layer"] == "L4_user_fit_and_delivery" for row in quality)
    assert all(row["terminal"] is False for row in quality)
    assert max(row["maximum_observed_unicode_characters"] for row in quality) == 531


def test_read_only_paired_comparison_and_gate_are_honest() -> None:
    assessment = _load(RESULT)
    runtime = _load(RUNTIME)
    lead = runtime["artifact_payloads"]["bounded_agent_judgment"]["cross_cell_lead"]
    cells = runtime["artifact_payloads"]["bounded_agent_workpaper"]["cells"]

    assert sum(len(cell["what_would_change"]) for cell in cells) == 9
    assert len(lead["cross_cell_dependencies"]) == 1
    assert len(lead["conflict_adjudications"]) == 1
    assert len(lead["remaining_gaps"]) == 3
    assert lead["variant_view"]
    assert assessment["paired_comparison"]["canonical_or_object_writes_from_comparison"] == 0
    assert assessment["stage_decision"]["engineering_integrity"] == "pass"
    assert assessment["stage_decision"]["product_completeness"] == "pass"
    assert assessment["stage_decision"]["research_quality"] == (
        "pass_with_L4_quality_debt"
    )
    assert assessment["stage_decision"]["owner_acceptance"] == "pending_not_written"
    assert assessment["stage_decision"]["S3_T09"] == (
        "conditional_pass_pending_explicit_owner_acceptance"
    )
