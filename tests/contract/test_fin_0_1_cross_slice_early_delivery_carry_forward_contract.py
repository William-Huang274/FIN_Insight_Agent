from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_cross_slice_early_delivery_carry_forward_contract_v1_0.json"
)
BACKLOG = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_program_release_backlog_v2_0.json"
)
PROGRAM_PLAN = (
    ROOT
    / "docs"
    / "architecture"
    / "repository"
    / "FIN_0_1_PROGRAM_EXECUTION_PLAN_DRAFT_20260719.zh-CN.md"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _slice(backlog: dict, slice_id: str) -> dict:
    return next(item for item in backlog["slices"] if item["slice_id"] == slice_id)


def _task(slice_contract: dict, item_id: str) -> dict:
    return next(item for item in slice_contract["items"] if item["item_id"] == item_id)


def test_contract_freezes_draft_finalize_and_consumer_owners() -> None:
    contract = _load(CONTRACT)
    producer = contract["producer_contract"]

    assert contract["status"] == (
        "S4_consumed_entry_decision_frozen_case_execution_pending"
    )
    assert producer["draft_trigger"] == "S3_T09_acceptance"
    assert producer["draft_owner"] == "S3-T09"
    assert producer["finalize_trigger"] == "S3_T10_owner_review_and_closeout"
    assert producer["finalize_owner"] == "S3-T10"
    assert producer["manifest_ref"].endswith(
        "fin_ia_0_1_s3_to_s4_early_delivery_carry_forward_manifest_v1_0.json"
    )


def test_manifest_requires_maturity_evidence_gaps_and_reuse_disposition() -> None:
    contract = _load(CONTRACT)
    required = set(contract["required_manifest_item_fields"])

    assert {
        "capability_id",
        "originally_planned_for",
        "maturity_state",
        "exact_status",
        "evidence_refs",
        "known_gaps",
        "remaining_acceptance",
        "reuse_instruction",
        "later_slice_disposition",
        "do_not_repeat_without_new_evidence",
    } <= required
    assert contract["allowed_maturity_states"] == [
        "documented",
        "contract_translated",
        "fixture_proven",
        "live_partial",
        "live_complete",
        "owner_accepted",
        "release_qualified",
    ]
    assert set(
        contract["consumer_contract"]["allowed_later_slice_dispositions"]
    ) == {
        "reuse_as_is",
        "extend",
        "revalidate_for_new_case_or_candidate",
        "defer_to_named_roadmap",
        "superseded_with_reason",
    }


def test_backlog_connects_T09_T10_S4_and_S5_to_the_contract() -> None:
    backlog = _load(BACKLOG)
    policy = backlog["execution_policy"]["cross_slice_early_delivery_carry_forward"]
    s3 = _slice(backlog, "S3")
    t09 = _task(s3, "S3-T09")
    t10 = _task(s3, "S3-T10")
    s4 = _slice(backlog, "S4")
    s5 = _slice(backlog, "S5")

    assert policy["contract_ref"] == CONTRACT.relative_to(ROOT).as_posix()
    assert policy["status"] == "S4_consumption_complete_T01_pass_S5_reconciliation_later"
    assert policy["S4_consumption_completed"] is True
    assert "draft_cross_slice_early_delivery_manifest_is_created" in t09["acceptance"]
    assert (
        "final_cross_slice_early_delivery_manifest_is_frozen_for_S4_and_S5"
        in t10["acceptance"]
    )
    assert "S3_to_S4_early_delivery_manifest_consumed" in s4["entry"]
    assert "S3_to_S4_early_delivery_manifest_consumption_recorded" in s4["exit"]
    assert s4["status"] == (
        "in_progress_T01_T04_pass_T05_T06_T07_honestly_blocked_closed_"
        "T08_read_only_next"
    )
    assert "S3_and_S4_carry_forward_records_reconciled" in s5["entry"]


def test_contract_prevents_maturity_inflation_and_duplicate_rebuilds() -> None:
    contract = _load(CONTRACT)
    rules = set(contract["non_inflation_rules"])
    s4_entry = set(contract["consumer_contract"]["S4_entry_requires"])

    assert "fixture_proven_must_not_be_reported_as_live_complete" in rules
    assert "S3_R2_must_not_be_reported_as_Alpha_release_or_production" in rules
    assert (
        "no_completed_capability_is_rebuilt_without_changed_requirement_failure_or_new_evidence"
        in s4_entry
    )
    assert contract["safety_and_storage"]["raw_provider_answer_copy_into_manifest"] is False
    assert (
        contract["safety_and_storage"][
            "private_reasoning_or_credential_copy_into_manifest"
        ]
        is False
    )


def test_program_plan_contains_the_cross_slice_handoff_rule() -> None:
    plan = PROGRAM_PLAN.read_text(encoding="utf-8")

    assert "跨 Slice 提前交付传递合同" in plan
    assert "T09 通过时生成草稿" in plan
    assert "S4、S5 开工前必须消费" in plan
