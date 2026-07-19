from __future__ import annotations

import json
from pathlib import Path

from sec_agent.project_os_preflight import run_project_os_preflight


def _write_project_os(root: Path, *, blocker_status: str = "closed") -> None:
    project_os = root / "docs" / "project_os"
    project_os.mkdir(parents=True)
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


def test_project_os_preflight_fails_when_required_files_missing(tmp_path: Path) -> None:
    result = run_project_os_preflight(tmp_path)

    assert result["status"] == "blocked"
    assert "missing_required_project_os_files" in result["errors"]
    assert "README.md" in result["missing_files"]
