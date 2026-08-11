from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s0_to_s4_t05_full_chain_global_audit_and_forward_plan_v1_0.json"
)
PROGRAM_BACKLOG = ROOT / (
    "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)
S4_BACKLOG = ROOT / (
    "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)
ROOT_CAUSE_LEDGER = ROOT / "docs/project_os/root_cause_issue_ledger.jsonl"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _strict_object(pairs: list[tuple[str, object]]) -> dict:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def test_audit_freezes_global_verdict_and_bounded_forward_sequence() -> None:
    audit = _load(AUDIT)

    assert audit["global_verdict"]["product_maturity"] == (
        "internal_engineering_alpha_with_one_owner_accepted_anchor_case_"
        "not_yet_transfer_qualified"
    )
    assert audit["stage_assessment"][5]["stage"] == "S4_T05"
    assert audit["stage_assessment"][5]["evidence"]["provider_calls"] == 70
    assert audit["stage_assessment"][5]["evidence"]["total_tokens"] == 400866
    assert audit["stage_assessment"][5]["evidence"]["paired_L1"].startswith("fail_")
    assert audit["next_action_governance"] == {
        "this_is_the_last_planned_T05_runtime_repair_bundle": True,
        "R11_is_the_only_planned_remaining_T05_paid_execution": True,
        "automatic_R12_or_scope_expansion": False,
        "new_non_L1_quality_findings_defer_to_S4_T08_T10_or_S5": True,
        "new_L1_after_R11_requires_explicit_program_level_block_or_scope_swap_decision": True,
    }


def test_backlogs_preserve_the_final_audit_and_its_two_historical_T05_blockers() -> None:
    audit = _load(AUDIT)
    program = _load(PROGRAM_BACKLOG)
    s4 = _load(S4_BACKLOG)
    audit_sha256 = _sha256(AUDIT)

    expected_blockers = audit["evidence_snapshot"][
        "actual_current_S4_T05_blockers"
    ]
    assert expected_blockers == [
        "RC-P36-067-s4-R10-numeric-reference-value-correspondence-false-negative",
        "RC-P36-068-s4-R10-case-identity-title-contract-hardcoded-NVDA",
    ]
    assert program["current_truth"]["global_audit_sha256"] == audit_sha256
    assert s4["global_audit"]["audit_sha256"] == audit_sha256
    assert set(expected_blockers).issubset(
        s4["global_audit"]["actual_current_T05_blockers"]
    )
    assert s4["global_audit"]["only_planned_remaining_T05_paid_execution"].startswith(
        "DELL_R11"
    )
    assert s4["global_audit"]["automatic_R12"] is False


def test_latest_root_cause_projection_matches_reconciled_blocker_counts() -> None:
    latest: dict[str, dict] = {}
    for line in ROOT_CAUSE_LEDGER.read_text(encoding="utf-8-sig").splitlines():
        if line.strip():
            record = json.loads(line)
            latest[record["issue_id"]] = record

    global_blockers = [
        record for record in latest.values() if record.get("full_chain_blocker")
    ]
    s4_blockers = [
        record
        for issue_id, record in latest.items()
        if "-s4-" in issue_id and record.get("full_chain_blocker")
    ]

    assert len(global_blockers) >= 44
    assert {
        "RC-P36-067-s4-R10-numeric-reference-value-correspondence-false-negative",
        "RC-P36-068-s4-R10-case-identity-title-contract-hardcoded-NVDA",
    }.issubset({record["issue_id"] for record in s4_blockers})


def test_release_and_project_os_machine_sources_reject_no_duplicate_keys() -> None:
    release_files = sorted((ROOT / "configs/releases").glob("*.json"))
    assert len(release_files) >= 296
    for path in release_files:
        json.loads(
            path.read_text(encoding="utf-8-sig"),
            object_pairs_hook=_strict_object,
        )

    jsonl_files = sorted((ROOT / "docs/project_os").glob("*.jsonl"))
    assert len(jsonl_files) == 24
    row_count = 0
    for path in jsonl_files:
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if line.strip():
                row_count += 1
                json.loads(line, object_pairs_hook=_strict_object)
    assert row_count >= 1193
