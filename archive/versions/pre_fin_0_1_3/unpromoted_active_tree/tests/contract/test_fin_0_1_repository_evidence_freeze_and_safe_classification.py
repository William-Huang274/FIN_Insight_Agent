from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INVENTORY_PATH = (
    PROJECT_ROOT
    / "configs/releases/"
    "fin_ia_0_1_repository_evidence_freeze_and_safe_classification_inventory_v1_0.json"
)
PROGRAM_BACKLOG_PATH = (
    PROJECT_ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)
S4_BACKLOG_PATH = (
    PROJECT_ROOT / "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)
TECHNICAL_RECORD_PATH = (
    PROJECT_ROOT
    / "docs/architecture/repository/"
    "FIN_0_1_REPOSITORY_EVIDENCE_FREEZE_AND_SAFE_CLASSIFICATION_20260731.zh-CN.md"
)
NEXT_ACTION = (
    "FIN-0.1-REPOSITORY-CLASSIFICATION-OWNER-REVIEW-AND-"
    "COHERENT-COMMIT-SLICE-AUTHORITY-DECISION"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _count(entries: list[dict], field: str) -> dict[str, int]:
    return dict(sorted(Counter(str(item[field]) for item in entries).items()))


def _strict_object(pairs: list[tuple[str, object]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def test_inventory_digest_and_capture_boundary_are_self_consistent() -> None:
    inventory = _load(INVENTORY_PATH)
    frozen_digest = inventory.pop("inventory_digest")
    assert frozen_digest == _canonical_sha256(inventory)
    assert inventory["schema_version"] == (
        "fin_ia_0_1_repository_evidence_freeze_and_safe_classification_"
        "inventory_v1_0"
    )
    assert inventory["decision_id"] == (
        "FIN-0.1-REPOSITORY-EVIDENCE-FREEZE-AND-SAFE-CLASSIFICATION-EXECUTION"
    )
    assert inventory["capture_boundary"]["HEAD"] == (
        "54d2e072b30d51cd7aaa3b55288d186782853a97"
    )
    assert inventory["capture_boundary"]["secret_values_persisted"] is False
    assert inventory["capture_boundary"]["file_bodies_persisted"] is False
    assert len(inventory["capture_boundary"]["cached_binary_diff"]["sha256"]) == 64
    assert len(inventory["capture_boundary"]["unstaged_binary_diff"]["sha256"]) == 64


def test_every_status_path_is_unique_classified_and_summary_derived() -> None:
    inventory = _load(INVENTORY_PATH)
    entries = inventory["entries"]
    summary = inventory["summary"]
    paths = [item["path"] for item in entries]
    assert len(entries) == summary["status_rows"] == 1127
    assert len(paths) == len(set(paths))
    assert (
        "configs/releases/"
        "fin_ia_0_1_repository_evidence_freeze_and_safe_classification_"
        "inventory_v1_0.json"
    ) not in paths
    assert summary["status_code_counts"] == _count(entries, "status_code")
    assert summary["stage_slice_counts"] == _count(entries, "stage_slice")
    assert summary["artifact_role_counts"] == _count(entries, "artifact_role")
    assert summary["commit_slice_counts"] == _count(entries, "commit_slice")
    assert summary["risk_counts"] == _count(entries, "risk")
    assert summary["recommended_disposition_counts"] == _count(
        entries, "recommended_disposition"
    )
    assert not any(
        item["stage_slice"] == "other_historical_or_unclassified"
        for item in entries
    )
    assert not any(
        item["commit_slice"] == "slice_08_owner_review_required"
        for item in entries
    )


def test_untracked_and_split_states_are_preserved_not_deleted() -> None:
    inventory = _load(INVENTORY_PATH)
    entries = inventory["entries"]
    untracked = [item for item in entries if item["status_code"] == "??"]
    split = [
        item
        for item in entries
        if item["status_code"] != "??" and item["status_code"][1] != " "
    ]
    assert len(untracked) == inventory["summary"]["untracked_paths"] == 326
    assert len(split) == inventory["summary"]["index_worktree_split_paths"] == 29

    for item in untracked:
        assert item["HEAD"]["exists"] is False
        assert item["index"]["exists"] is False
        assert item["worktree"]["exists"] is True
        assert len(item["worktree"]["sha256"]) == 64
        assert item["recoverability"] == "worktree_only_not_recoverable_from_Git"
        assert "delete" not in item["recommended_disposition"]

    for item in split:
        assert item["index"]["exists"] is True
        assert len(item["index"]["sha256"]) == 64
        assert item["worktree"]["exists"] is True
        assert len(item["worktree"]["sha256"]) == 64
        assert item["recommended_disposition"] == (
            "preserve_index_and_worktree_versions_before_any_unstage"
        )

    findings = inventory["safety_findings"]
    assert findings["cleanup_ready"] is False
    assert findings["safe_delete_candidates_proven"] == 0
    assert findings["ephemeral_candidates_not_authorized_for_delete"] == []


def test_credential_shaped_test_fixtures_are_redacted_and_not_real_findings() -> None:
    inventory = _load(INVENTORY_PATH)
    findings = inventory["safety_findings"]
    assert findings["potential_plaintext_secret_findings"] == []
    fixtures = findings["intentional_non_secret_credential_test_fixtures"]
    assert {item["path"] for item in fixtures} == {
        (
            "tests/contract/"
            "test_fin_0_1_s4_t06_entry_single_node_strict_schema_canary_runner.py"
        ),
        (
            "tests/contract/"
            "test_fin_0_1_s4_t06_runtime_audit_evidence_v2_and_material_numeric_"
            "classifier_zero_call_implementation.py"
        ),
    }
    fixture_entries = {
        item["path"]: item
        for item in inventory["entries"]
        if item["secret_scan_classification"]
        == "intentional_non_secret_credential_test_fixture"
    }
    assert set(fixture_entries) == {item["path"] for item in fixtures}
    assert all(item["risk"] != "critical" for item in fixture_entries.values())


def test_commit_slice_order_is_dependency_aware_and_has_no_unclassified_paths() -> None:
    inventory = _load(INVENTORY_PATH)
    plan = inventory["commit_slice_plan"]
    assert [item["order"] for item in plan] == list(range(9))
    assert [item["slice_id"] for item in plan] == [
        "slice_00_foundation_and_product_shell",
        "slice_01_shared_runtime_and_workbench",
        "slice_02_FIN_0_1_one_cell_baseline",
        "slice_03_FIN_0_1_NVDA_anchor",
        "slice_04_FIN_0_1_three_case_transfer",
        "slice_05_execution_evidence",
        "slice_06_repository_recovery_governance",
        "slice_07_Project_OS_finalization",
        "slice_08_owner_review_required",
    ]
    assert inventory["summary"]["commit_slice_counts"] == {
        "slice_00_foundation_and_product_shell": 33,
        "slice_01_shared_runtime_and_workbench": 30,
        "slice_02_FIN_0_1_one_cell_baseline": 103,
        "slice_03_FIN_0_1_NVDA_anchor": 427,
        "slice_04_FIN_0_1_three_case_transfer": 516,
        "slice_05_execution_evidence": 2,
        "slice_06_repository_recovery_governance": 8,
        "slice_07_Project_OS_finalization": 8,
    }
    assert inventory["rollback_policy"]["delete_policy"].startswith(
        "No delete candidate exists"
    )


def test_execution_guard_and_product_boundaries_remain_fail_closed() -> None:
    inventory = _load(INVENTORY_PATH)
    guard = inventory["execution_guard"]
    assert guard["status_before_and_after_excluding_output_equal"] is True
    assert guard["unexpected_path_mutations"] == []
    assert guard["inventory_scope_status_rows_excluding_output"] == 1127
    assert guard["post_write_status_rows_including_output"] == 1128
    assert guard["output_status_entries"] == [
        {
            "status_code": "??",
            "path": (
                "configs/releases/"
                "fin_ia_0_1_repository_evidence_freeze_and_safe_classification_"
                "inventory_v1_0.json"
            ),
            "original_path": None,
        }
    ]
    assert guard["file_deletes_moves_unstage_reset_checkout_commit_push_tag_release"] == 0
    assert guard["model_provider_network_source_external_tool_or_live"] == 0
    assert inventory["next_action"] == NEXT_ACTION

    program = _load(PROGRAM_BACKLOG_PATH)
    s4 = _load(S4_BACKLOG_PATH)
    assert program["next_action"]["item_id"] == NEXT_ACTION
    assert program["next_action"]["repository_inventory_ref"] == (
        INVENTORY_PATH.relative_to(PROJECT_ROOT).as_posix()
    )
    assert (
        program["next_action"]["repository_post_write_status_rows_including_inventory"]
        == 1128
    )
    assert program["next_action"]["repository_cleanup_executed"] is False
    assert program["next_action"]["S4_closeout_executed"] is False
    assert program["next_action"]["S5_entered"] is False
    assert s4["current_next_action"] == NEXT_ACTION
    recovery = s4["repository_recovery_and_version_lineage_scope"]
    assert recovery["repository_inventory_ref"] == (
        INVENTORY_PATH.relative_to(PROJECT_ROOT).as_posix()
    )
    assert recovery["repository_post_write_untracked_paths_including_inventory"] == 327
    assert recovery["safe_delete_candidates_proven"] == 0
    assert recovery["cleanup_executed"] is False


def test_human_readable_record_matches_the_machine_boundary() -> None:
    record = TECHNICAL_RECORD_PATH.read_text(encoding="utf-8")
    assert "1,127" in record
    assert "799 / 29 / 326" in record
    assert "safe_delete_candidates_proven=0" in record
    assert NEXT_ACTION in record
    assert "S4 honest-block" in record


def test_current_release_json_and_project_os_jsonl_parse_without_duplicate_keys() -> None:
    release_files = sorted((PROJECT_ROOT / "configs/releases").glob("*.json"))
    assert len(release_files) == 409
    for path in release_files:
        json.loads(
            path.read_text(encoding="utf-8-sig"),
            object_pairs_hook=_strict_object,
        )

    jsonl_files = sorted((PROJECT_ROOT / "docs/project_os").glob("*.jsonl"))
    assert len(jsonl_files) == 24
    row_count = 0
    for path in jsonl_files:
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if not line.strip():
                continue
            row_count += 1
            json.loads(line, object_pairs_hook=_strict_object)
    assert row_count >= 1504
