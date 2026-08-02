from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DECISION_REF = Path(
    "configs/releases/fin_ia_0_1_2_version_consolidation_and_current_rebaseline_v1_0.json"
)
PROJECTION_REF = Path(
    "configs/runtime/fin_ia_0_1_2_current_program_projection_v2_0.json"
)
PROGRAM_BACKLOG_REF = Path(
    "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)
S4_BACKLOG_REF = Path(
    "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)
POLICY_REF = Path(
    "docs/project_os/senior_assistant_collaboration_policy.zh-CN.md"
)
PRODUCT_PLAN_REF = Path(
    "docs/product/FIN_0_1_2_CANONICAL_S0_TO_S5_PRODUCT_PROGRESSION_PLAN_20260802.zh-CN.md"
)
S0_PLAN_REF = Path(
    "docs/architecture/repository/FIN_0_1_2_S0_CURRENT_BASELINE_AND_CLEAN_ENVIRONMENT_QUALIFICATION_PLAN_20260802.zh-CN.md"
)
ASSET_AUDIT_REF = Path(
    "docs/architecture/repository/FIN_0_1_2_S0_CURRENT_CODE_ASSET_AUDIT_20260802.zh-CN.md"
)
CONSOLIDATION_NEXT = (
    "FIN-0.1.2-S0-CURRENT-BASELINE-AUDIT-OWNER-REVIEW-AND-REPAIR-"
    "AUTHORIZATION"
)


def _load(path: Path) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in (ROOT / path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_consolidation_restores_fin_0_1_2_without_rewriting_history() -> None:
    decision = _load(DECISION_REF)
    lineage = decision["canonical_version_lineage"]
    assert decision["status"].startswith("pass_FIN_0_1_2_restored")
    assert "current_full_second_S0_to_S5" in lineage["FIN_0_1_2"]
    assert "historical_FIN_0_1_2_S0" in lineage["FIN_0_1_3"]
    assert "historical_unexecuted" in lineage["FIN_0_1_4"]
    assert lineage["FIN_0_2"] == "Earnings_Review_Alpha_definition_preserved"
    assert decision["supersession"]["history_deleted_or_rewritten"] is False
    assert decision["repair_and_retry_policy"][
        "failure_automatically_creates_product_version"
    ] is False
    assert decision["next_action"] == CONSOLIDATION_NEXT


def test_current_projection_and_backlogs_have_one_current_truth() -> None:
    projection = _load(PROJECTION_REF)
    program = _load(PROGRAM_BACKLOG_REF)
    s4 = _load(S4_BACKLOG_REF)
    assert projection["current_truth"]["product_version"] == "FIN_0_1_2"
    assert projection["current_truth"]["stage"] == "S0"
    current_next = projection["current_truth"]["current_next_action"]
    assert current_next.startswith("FIN-0.1.2-S0-")
    assert current_next != CONSOLIDATION_NEXT
    assert program["version"] == "FIN_0_1_2_CURRENT_CONSOLIDATED_PRODUCT_ITERATION"
    assert program["current_version_rebaseline"]["authoritative_current_truth"] is False
    assert program["current_version_rebaseline"]["current_projection_is_authority"] is True
    assert program["next_action"]["item_id"] == current_next
    assert s4["current_version_rebaseline"]["historical_backlog_role"].startswith(
        "preserve_first_FIN_0_1_1_S4"
    )
    assert s4["current_next_action"] == current_next
    assert (ROOT / "configs/runtime/fin_ia_0_1_4_current_program_projection_v1_0.json").exists()
    assert projection["historical_projection_policy"][
        "superseded_projection_deleted_or_rewritten"
    ] is False


def test_plans_and_assistant_policy_are_durable_and_plainly_scoped() -> None:
    for path in (POLICY_REF, PRODUCT_PLAN_REF, S0_PLAN_REF, ASSET_AUDIT_REF):
        assert (ROOT / path).is_file(), path
    assert (ROOT / "AGENTS.md").is_file()
    policy = (ROOT / POLICY_REF).read_text(encoding="utf-8")
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "不得静默照做" in policy
    assert "先前授权不得被解释为永久禁止质疑" in policy
    assert "Do not act as a silent executor" in agents
    product_plan = (ROOT / PRODUCT_PLAN_REF).read_text(encoding="utf-8")
    for stage in ("S0 可靠基础", "S1 三案例确定性链", "S2 模型边界", "S3 单案例产品锚点", "S4 跨案例与工作台价值", "S5 发布判断"):
        assert stage in product_plan
    audit = (ROOT / ASSET_AUDIT_REF).read_text(encoding="utf-8")
    assert "57 passed / 3 failed" in audit
    assert "current_projection_next_action_drift" in audit


def test_latest_project_os_rows_reassign_current_scope_to_fin_0_1_2() -> None:
    capabilities = _jsonl(Path("docs/project_os/capability_status_ledger.jsonl"))
    current = [
        row
        for row in capabilities
        if row.get("capability_id")
        == "fin_0_1_2_version_consolidation_current_S0_rebaseline_and_senior_assistant_policy"
    ]
    assert current
    projection = _load(PROJECTION_REF)
    assert current[-1]["current_next"] == projection["current_truth"][
        "current_next_action"
    ]
    issues = _jsonl(Path("docs/project_os/root_cause_issue_ledger.jsonl"))
    for number in range(90, 97):
        matching = [row for row in issues if f"RC-P36-{number:03d}" in row.get("issue_id", "")]
        assert matching
        assert matching[-1]["state_detail"].startswith("reassigned_to_consolidated_FIN_0_1_2_S0")


def test_decision_did_not_authorize_runtime_or_external_execution() -> None:
    decision = _load(DECISION_REF)
    authority = decision["authority"]
    assert authority["runtime_or_test_implementation_authorized"] is False
    assert authority["clean_environment_acceptance_execution_authorized"] is False
    assert authority["credential_model_provider_network_business_run_authorized"] is False
    observed = decision["observed_this_decision"]
    assert all(value == 0 for value in observed.values())
