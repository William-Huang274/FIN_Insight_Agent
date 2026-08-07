from __future__ import annotations

from pathlib import Path
import json

from sec_agent.project_os_preflight import run_project_os_preflight


ROOT = Path(__file__).resolve().parents[2]
S0_SCOPE = (
    "FIN_0_1_3_S0_04G_TYPED_BLOCKER_STATE_AND_RUN_SCOPE_REGISTRY_"
    "MINIMUM_ZERO_CALL_IMPLEMENTATION"
)
DIRECT_R3_SCOPE = "S1_08_V3_DELL_R3_EXACT_LIVE_ISSUANCE_AND_EXECUTION"


def test_current_S0_04G_scope_uses_typed_registry_and_passes() -> None:
    result = run_project_os_preflight(ROOT, run_scope=S0_SCOPE)

    assert result["status"] == "pass"
    assert result["schema_version"] == "fin_insight_project_os_full_chain_preflight_v0_2"
    assert result["run_scope_registry"]["registry_version"] == "v1_0"
    assert result["scope_resolution"]["owner_stage"] == "S0"
    assert result["contract_errors"] == []
    assert result["open_full_chain_blocker_count"] == 0


def test_unregistered_scope_and_diagnostic_override_fail_closed() -> None:
    result = run_project_os_preflight(
        ROOT,
        run_scope="FIN_0_1_3_S0_04G_typo",
        allow_open_blockers=True,
    )

    assert result["status"] == "blocked"
    assert result["scope_resolution"]["status"] == "unknown_or_non_executable"
    assert "project_os_contract_invalid" in result["errors"]


def test_direct_R3_scope_matches_latest_typed_product_projection() -> None:
    result = run_project_os_preflight(ROOT, run_scope=DIRECT_R3_SCOPE)
    rows = [
        json.loads(line)
        for line in (
            ROOT / "docs/project_os/root_cause_issue_ledger.jsonl"
        ).read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    latest = next(
        row
        for row in reversed(rows)
        if str(row.get("issue_id") or "").startswith("RC-P36-157-")
    )
    direct_allowed = DIRECT_R3_SCOPE in (latest.get("allowed_run_scopes") or [])

    assert result["contract_errors"] == []
    if direct_allowed:
        assert result["status"] == "pass"
        assert result["open_full_chain_blockers"] == []
    else:
        assert result["status"] == "blocked"
        assert any(
            item["issue_id"].startswith("RC-P36-157-")
            for item in result["open_full_chain_blockers"]
        )
