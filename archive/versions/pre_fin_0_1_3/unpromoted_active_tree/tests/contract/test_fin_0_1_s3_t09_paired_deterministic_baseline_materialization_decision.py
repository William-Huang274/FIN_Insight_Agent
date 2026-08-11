from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

RELEASES = ROOT / "configs" / "releases"
DECISION = (
    RELEASES
    / "fin_ia_0_1_s3_t09_paired_deterministic_baseline_materialization_decision_v1_0.json"
)
BACKLOG = RELEASES / "fin_ia_0_1_program_release_backlog_v2_0.json"
RUNTIME_ROOT = (
    ROOT
    / ".codex_runtime"
    / "fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1"
)


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_decision_freezes_exact_same_input_distinct_baseline_without_materializing() -> None:
    decision = _load(DECISION)
    source = decision["source_binding"]
    baseline = decision["prospective_baseline"]
    assert decision["status"] == (
        "pass_materialization_contract_decided_execution_deferred_until_owner_grade_repair"
    )
    assert source["input_head_digest"] == (
        "c9867b54b86cf17982b4cebfaf0c0ebcae2a6f46d894ff82dbb643f693c9836d"
    )
    assert baseline["research_run_id"] != source["agent_research_run_id"]
    assert baseline["all_identities_absent_and_distinct_from_agent"] is True
    assert baseline["materialized"] is False
    assert set(baseline["artifact_refs"]) == {
        "deterministic_research_result",
        "s3_three_cell_workpaper",
        "s3_three_cell_report",
        "s3_three_cell_trace_review",
    }


def test_materialization_boundary_is_zero_call_fail_closed_and_separately_authorized() -> None:
    decision = _load(DECISION)
    authority = decision["authority"]
    contract = decision["materialization_contract"]
    counts = decision["observed_counts"]
    assert authority["baseline_materialization_decision_authorized"] is True
    assert authority["baseline_materialization_authorized"] is False
    assert authority["agent_rerun_authorized"] is False
    assert contract["maximum_attempts"] == 1
    assert contract["retry_budget"] == 0
    assert contract["automatic_fallback_or_agent_substitution"] is False
    assert contract["baseline_body_may_be_exposed_to_future_agent"] is False
    assert set(counts.values()) == {0}


def test_disposable_clone_preflight_froze_exact_historical_target_guard() -> None:
    decision = _load(DECISION)
    expected = decision["prospective_baseline"]
    audit = decision["preflight_safety"]
    assert expected["double_prepare_equal"] is True
    assert expected["prospective_payload_digest"] == (
        "71784beb7b2f3a8c5f73b134589b3171087f1ba14f017d5467f1ee2f9204e57b"
    )
    assert audit["corrected_preflight_status"] == "pass"
    assert audit["target_logical_snapshot_unchanged"] is True
    assert audit["target_database_sha256_before_and_after"] == (
        "876e98a85517b4959fd95258592847d3f76a5a8305e349601b27dffcb34addac"
    )


def test_decision_recorded_program_order_at_decision_time() -> None:
    decision = _load(DECISION)
    assert decision["next_action"] == (
        "S3-T09-OWNER-GRADE-SEMANTIC-ACTIONABILITY-ZERO-CALL-REPAIR-DECISION"
    )
