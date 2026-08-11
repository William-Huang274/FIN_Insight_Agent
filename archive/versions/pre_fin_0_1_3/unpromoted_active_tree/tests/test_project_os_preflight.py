from __future__ import annotations

import json
from pathlib import Path

from sec_agent.project_os_preflight import (
    compact_preflight_stdout,
    run_project_os_preflight,
)


REGISTRY = {
    "schema_version": "fin_insight_project_os_run_scope_registry_v1_0",
    "registry_id": "test_registry",
    "registry_version": "v1_0",
    "adoption_sequence_after_projection": "v2_1",
    "owner_stages": ["shared", "repository", "S0", "S1"],
    "operation_classes": ["namespace", "full_chain", "test", "repository_hygiene"],
    "blocker_states": {
        "open": {"is_open": True},
        "mitigated_open": {"is_open": True},
        "blocked_external": {"is_open": True},
        "closed": {"is_open": False},
        "superseded": {"is_open": False},
    },
    "legacy_compatibility": {
        "through_sequence_after_projection": "v2_1",
        "unknown_full_chain_blocker_state": "open",
        "unknown_non_blocker_state": "closed",
        "ledger_declared_scope_refs_are_read_only": True,
        "status_aliases": {"open": "open", "closed": "closed"},
    },
    "scopes": {
        "broad_full_chain": {
            "owner_stage": "shared",
            "operation_class": "full_chain",
            "parent_scope_id": None,
            "executable": True,
            "allowed_projection_owner_stages": ["shared", "S0", "S1"],
        },
        "test_namespace": {
            "owner_stage": "S0",
            "operation_class": "namespace",
            "parent_scope_id": None,
            "executable": False,
            "allowed_projection_owner_stages": ["shared", "S0"],
        },
        "p33_single_gold_case": {
            "owner_stage": "S0",
            "operation_class": "test",
            "parent_scope_id": "test_namespace",
            "executable": True,
            "allowed_projection_owner_stages": ["shared", "S0", "S1"],
        },
        "case_expansion": {
            "owner_stage": "S1",
            "operation_class": "test",
            "parent_scope_id": None,
            "executable": True,
            "allowed_projection_owner_stages": ["shared", "S1"],
        },
        "release_eval": {
            "owner_stage": "S1",
            "operation_class": "test",
            "parent_scope_id": None,
            "executable": True,
            "allowed_projection_owner_stages": ["shared", "S1"],
        },
        "repository_and_git_hygiene": {
            "owner_stage": "repository",
            "operation_class": "repository_hygiene",
            "parent_scope_id": None,
            "executable": True,
            "allowed_projection_owner_stages": ["shared", "repository", "S0", "S1"],
        },
    },
}


def _write_project_os(root: Path, *, blocker_status: str = "closed") -> None:
    project_os = root / "docs" / "project_os"
    project_os.mkdir(parents=True)
    registry = root / "configs" / "runtime"
    registry.mkdir(parents=True)
    (registry / "fin_ia_project_os_run_scope_registry_v1_0.json").write_text(
        json.dumps(REGISTRY), encoding="utf-8"
    )
    for name in [
        "README.md",
        "current_context_pack.zh-CN.md",
        "full_chain_run_policy.zh-CN.md",
        "token_budget_policy.zh-CN.md",
        "done_definition_l4_scope_pass.zh-CN.md",
    ]:
        (project_os / name).write_text("# test\n", encoding="utf-8")
    (project_os / "full_chain_preflight_checklist.json").write_text(
        json.dumps({"schema_version": "test", "checks": [{"check_id": "x"}]}),
        encoding="utf-8",
    )
    (project_os / "external_pattern_registry.jsonl").write_text(
        json.dumps({"pattern_id": "p", "status": "active_reference"}) + "\n",
        encoding="utf-8",
    )
    (project_os / "financial_research_method_registry.jsonl").write_text(
        json.dumps({"method_id": "m", "status": "active"}) + "\n",
        encoding="utf-8",
    )
    (project_os / "capability_status_ledger.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"capability_id": "p31_project_os_core", "status": "L4_scope_pass"}),
                json.dumps({"capability_id": "p31_full_chain_preflight_guard", "status": "L4_scope_pass"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (project_os / "root_cause_issue_ledger.jsonl").write_text(
        json.dumps(
            {
                "issue_id": "RC-test",
                "status": blocker_status,
                "full_chain_blocker": blocker_status != "closed",
                "symptom": "test blocker",
                "required_fix": "fix it",
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _append_issue(root: Path, row: dict[str, object]) -> None:
    path = root / "docs" / "project_os" / "root_cause_issue_ledger.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def test_project_os_preflight_passes_without_open_blockers(tmp_path: Path) -> None:
    _write_project_os(tmp_path, blocker_status="closed")

    result = run_project_os_preflight(tmp_path)

    assert result["status"] == "pass"
    assert result["missing_files"] == []
    assert result["open_full_chain_blockers"] == []
    assert result["scope_resolution"]["status"] == "registered"
    assert result["run_scope_registry"]["registry_version"] == "v1_0"


def test_project_os_preflight_blocks_open_full_chain_blocker(tmp_path: Path) -> None:
    _write_project_os(tmp_path, blocker_status="open")

    result = run_project_os_preflight(tmp_path)

    assert result["status"] == "blocked"
    assert result["errors"] == ["open_full_chain_blockers"]
    assert result["open_full_chain_blockers"][0]["issue_id"] == "RC-test"
    assert result["run_scope"] == "broad_full_chain"


def test_project_os_preflight_allows_explicit_diagnostic_override(tmp_path: Path) -> None:
    _write_project_os(tmp_path, blocker_status="open")

    result = run_project_os_preflight(tmp_path, allow_open_blockers=True)

    assert result["status"] == "diagnostic_override"
    assert result["errors"] == []
    assert result["open_full_chain_blockers"][0]["required_fix"] == "fix it"


def test_project_os_preflight_uses_latest_append_only_issue_row(tmp_path: Path) -> None:
    _write_project_os(tmp_path, blocker_status="open")
    _append_issue(
        tmp_path,
        {
            "issue_id": "RC-test",
            "status": "closed",
            "full_chain_blocker": False,
            "symptom": "fixed",
            "required_fix": "already fixed",
        },
    )

    result = run_project_os_preflight(tmp_path)

    assert result["status"] == "pass"
    assert result["open_full_chain_blockers"] == []


def test_project_os_preflight_allows_scoped_controlled_run_but_blocks_broad(tmp_path: Path) -> None:
    _write_project_os(tmp_path, blocker_status="closed")
    _append_issue(
        tmp_path,
        {
            "issue_id": "RC-scoped",
            "status": "open",
            "full_chain_blocker": True,
            "symptom": "single proof pending",
            "required_fix": "run one controlled gold case",
            "blocking_run_scopes": ["broad_full_chain", "case_expansion", "release_eval"],
            "allowed_run_scopes": ["p33_single_gold_case"],
        },
    )

    broad = run_project_os_preflight(tmp_path)
    scoped = run_project_os_preflight(tmp_path, run_scope="p33_single_gold_case")

    assert broad["status"] == "blocked"
    assert broad["open_full_chain_blockers"][0]["issue_id"] == "RC-scoped"
    assert scoped["status"] == "pass"
    assert scoped["open_full_chain_blockers"] == []


def test_unknown_requested_scope_fails_closed_and_override_cannot_bypass(
    tmp_path: Path,
) -> None:
    _write_project_os(tmp_path, blocker_status="closed")

    result = run_project_os_preflight(
        tmp_path, run_scope="typo_unregistered_scope", allow_open_blockers=True
    )

    assert result["status"] == "blocked"
    assert result["scope_resolution"]["status"] == "unknown_or_non_executable"
    assert result["contract_errors"][0]["code"] == "unknown_or_non_executable_run_scope"


def test_unknown_legacy_full_chain_state_is_open_fail_closed(tmp_path: Path) -> None:
    _write_project_os(tmp_path, blocker_status="closed")
    _append_issue(
        tmp_path,
        {
            "issue_id": "RC-legacy-unknown",
            "status": "descriptive_state_not_registered",
            "full_chain_blocker": True,
            "blocking_run_scopes": ["broad_full_chain"],
        },
    )

    result = run_project_os_preflight(tmp_path)

    assert result["status"] == "blocked"
    blocker = result["open_full_chain_blockers"][0]
    assert blocker["blocker_state"] == "open"
    assert blocker["blocker_state_source"] == "legacy_unknown_fail_closed"


def test_post_adoption_projection_requires_typed_state_registry_and_lineage(
    tmp_path: Path,
) -> None:
    _write_project_os(tmp_path, blocker_status="closed")
    _append_issue(
        tmp_path,
        {
            "issue_id": "RC-test",
            "sequence_after_projection": "v2_2",
            "status": "descriptive",
            "full_chain_blocker": True,
            "blocking_run_scopes": ["broad_full_chain"],
        },
    )

    result = run_project_os_preflight(tmp_path)
    codes = {item["code"] for item in result["contract_errors"]}

    assert result["status"] == "blocked"
    assert "projection_blocker_state_unknown" in codes
    assert "projection_registry_version_mismatch" in codes
    assert "projection_owner_stage_unknown" in codes
    assert "projection_lineage_mismatch" not in codes


def test_canonical_projection_and_parent_scope_matching(tmp_path: Path) -> None:
    _write_project_os(tmp_path, blocker_status="closed")
    _append_issue(
        tmp_path,
        {
            "issue_id": "RC-canonical",
            "sequence_after_projection": "v2_2",
            "previous_projection_sequence": None,
            "status": "still_open_with_detail",
            "blocker_state": "open",
            "run_scope_registry_version": "v1_0",
            "owner_stage": "S0",
            "full_chain_blocker": True,
            "blocking_run_scopes": ["test_namespace"],
            "allowed_run_scopes": [],
        },
    )

    result = run_project_os_preflight(tmp_path, run_scope="p33_single_gold_case")

    assert result["status"] == "blocked"
    assert result["contract_errors"] == []
    assert result["open_full_chain_blockers"][0]["matched_blocking_scope_refs"] == [
        "test_namespace"
    ]


def test_projection_scope_owner_mismatch_and_registry_cycle_fail_closed(
    tmp_path: Path,
) -> None:
    _write_project_os(tmp_path, blocker_status="closed")
    _append_issue(
        tmp_path,
        {
            "issue_id": "RC-owner",
            "sequence_after_projection": "v2_2",
            "previous_projection_sequence": None,
            "status": "open",
            "blocker_state": "open",
            "run_scope_registry_version": "v1_0",
            "owner_stage": "S0",
            "full_chain_blocker": True,
            "blocking_run_scopes": ["case_expansion"],
        },
    )
    registry_path = (
        tmp_path
        / "configs"
        / "runtime"
        / "fin_ia_project_os_run_scope_registry_v1_0.json"
    )
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    payload["scopes"]["test_namespace"]["parent_scope_id"] = "p33_single_gold_case"
    payload["scopes"]["case_expansion"]["parent_scope_id"] = "test_namespace"
    registry_path.write_text(json.dumps(payload), encoding="utf-8")

    result = run_project_os_preflight(tmp_path)
    codes = {item["code"] for item in result["contract_errors"]}

    assert result["status"] == "blocked"
    assert "projection_scope_owner_mismatch" in codes
    assert "run_scope_parent_cycle" in codes
    assert "run_scope_parent_owner_mismatch" in codes


def test_compact_and_full_output_share_typed_contract_shape(tmp_path: Path) -> None:
    _write_project_os(tmp_path, blocker_status="open")

    full = run_project_os_preflight(tmp_path)
    compact = compact_preflight_stdout(full)

    for field in (
        "schema_version",
        "status",
        "policy",
        "run_scope",
        "scope_resolution",
        "run_scope_registry",
        "open_full_chain_blocker_count",
        "open_full_chain_blockers",
        "contract_errors",
        "errors",
    ):
        assert compact[field] == full[field]


def test_project_os_preflight_fails_when_required_files_missing(tmp_path: Path) -> None:
    result = run_project_os_preflight(tmp_path)

    assert result["status"] == "blocked"
    assert "missing_required_project_os_files" in result["errors"]
    assert "README.md" in result["missing_files"]
