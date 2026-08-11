from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DECISION_REF = (
    "configs/releases/fin_ia_0_1_3_terminal_honest_block_and_fin_0_1_4_"
    "s0_version_scope_disposition_v1_0.json"
)
TERMINAL_DECISION_REF = (
    "configs/releases/fin_ia_0_1_3_s0_exit_contract_v3_eligibility_authority_"
    "transition_structural_blocker_terminal_decision_v1_0.json"
)
PROJECTION_REF = "configs/runtime/fin_ia_0_1_4_current_program_projection_v1_0.json"
PROGRAM_REF = "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
S4_REF = "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
CAPABILITY_REF = "docs/project_os/capability_status_ledger.jsonl"
ROOT_CAUSE_REF = "docs/project_os/root_cause_issue_ledger.jsonl"
PATTERN_REF = "docs/project_os/external_pattern_registry.jsonl"
LINEAGE_REF = (
    "docs/product/FIN_0_1_1_0_1_2_VERSION_LINEAGE_AND_RELEASE_CADENCE_"
    "DECISION_20260731.zh-CN.md"
)
CANONICAL_REF = (
    "docs/product/FIN_0_1_3_CANONICAL_S0_TO_S5_PRODUCT_PROGRESSION_PLAN_"
    "20260801.zh-CN.md"
)
TECHNICAL_REF = (
    "docs/architecture/repository/FIN_0_1_3_S0_HERMETIC_RUNTIME_DEPENDENCY_"
    "AND_SEMANTIC_PARITY_STAGE_PLAN_20260801.zh-CN.md"
)
WORKLOG_REF = (
    "docs/worklog/product_strategy/547_fin_0_1_3_terminal_closeout_and_fin_"
    "0_1_4_s0_version_scope_disposition.md"
)
NEXT = (
    "FIN-0.1.4-S0-PROOF-LIFECYCLE-STATE-MACHINE-AND-HERMETIC-"
    "QUALIFICATION-STAGE-PLAN"
)
ISSUES = [
    "RC-P36-090-fin-0-1-2-pre-s2-t03-disposable-self-introspection-git-inventory-dependency",
    "RC-P36-091-fin-0-1-2-hermetic-package-recursive-json-ref-admits-ignored-runtime-state",
    "RC-P36-092-fin-0-1-2-code-declared-static-runtime-resource-missing-from-hermetic-inventory",
    "RC-P36-093-fin-0-1-2-hermetic-semantic-parity-untyped-host-python-traceback-path",
    "RC-P36-094-fin-0-1-3-hermetic-reference-role-taxonomy-conflates-semantic-audit-and-repository-paths",
    "RC-P36-095-fin-0-1-3-v2-host-proof-manifest-policy-enum-contract-drift",
    "RC-P36-096-fin-0-1-3-v3-eligibility-authority-transition-projection-status-hard-coded-pre-authority-state",
]


def _load_json(ref: str) -> dict[str, Any]:
    return json.loads((ROOT / ref).read_text(encoding="utf-8"))


def _jsonl(ref: str) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in (ROOT / ref).read_text(encoding="utf-8").splitlines()
    ]


def _sha256(ref: str) -> str:
    return hashlib.sha256((ROOT / ref).read_bytes()).hexdigest()


def test_decision_is_digest_bound_and_selects_only_bounded_fin_0_1_4_entry() -> None:
    decision = _load_json(DECISION_REF)

    for binding in decision["source_bindings"]:
        assert _sha256(binding["ref"]) == binding["sha256"]

    selected = [row for row in decision["decision_options"] if row["selected"]]
    assert [row["option"] for row in selected] == ["B"]
    assert decision["selected_version_lineage"]["FIN_0_1_3"]["status"] == (
        "frozen_internal_honest_block_S0_terminal_S1_S2_not_entered"
    )
    assert decision["selected_version_lineage"]["FIN_0_1_3"][
        "exit_contract_v4_created"
    ] is False
    assert decision["selected_version_lineage"]["FIN_0_1_4"]["status"] == (
        "S0_stage_plan_ready_not_started"
    )
    assert decision["selected_version_lineage"]["FIN_0_2"][
        "original_definition_preserved"
    ] is True
    assert [row["issue_id"] for row in decision["issue_owner_transfer"]] == ISSUES
    assert decision["next_action"] == NEXT


def test_decision_does_not_inflate_stage_plan_implementation_or_proof() -> None:
    decision = _load_json(DECISION_REF)
    authority = decision["authority"]
    observed = decision["observed_counts_this_decision"]
    stop = decision["fixed_budgets_and_stop_rules"]

    assert authority["FIN_0_1_4_S0_stage_plan_created_or_executed"] is False
    assert authority["runtime_or_test_implementation_authorized"] is False
    assert authority["eligibility_host_or_formal_proof_authorized"] is False
    assert all(value == 0 for value in observed.values())
    assert stop["automatic_FIN_0_1_4_S0_T05_R_H_or_replacement_family"] is False
    assert stop["automatic_FIN_0_1_5_on_failure"] is False
    assert stop["FIN_0_1_3_v3_patch_retry_replacement_or_v4"] is False
    assert decision["product_truth"]["FIN_0_1_4_S0"] == "not_started"
    assert decision["product_truth"]["FIN_0_1_release_qualified"] is False
    assert decision["product_truth"]["FIN_0_2_definition_changed"] is False


def test_projection_backlogs_and_project_os_share_fin_0_1_4_stage_plan_truth() -> None:
    decision = _load_json(DECISION_REF)
    projection = _load_json(PROJECTION_REF)
    program = _load_json(PROGRAM_REF)
    s4 = _load_json(S4_REF)
    capability = _jsonl(CAPABILITY_REF)[-1]
    roots = _jsonl(ROOT_CAUSE_REF)[-7:]
    pattern = _jsonl(PATTERN_REF)[-1]
    expected = projection["expectations"]

    assert projection["decision_binding"] == {
        "ref": DECISION_REF,
        "sha256": _sha256(DECISION_REF),
    }
    assert expected["FIN_0_1_3_terminal_decision_ref"] == TERMINAL_DECISION_REF
    assert expected["FIN_0_1_3_terminal_decision_sha256"] == _sha256(
        TERMINAL_DECISION_REF
    )
    assert expected["current_next_action"] == NEXT
    assert expected["capability_id"] == capability["capability_id"]
    assert expected["capability_stage_acceptance"] == capability["stage_acceptance"]
    assert expected["open_issue_ids"] == ISSUES
    assert expected[
        "FIN_0_1_4_S0_stage_plan_implementation_eligibility_host_formal_observed"
    ] == [0, 0, 0, 0, 0]

    assert program["version"] == "FIN_0_1_4_CURRENT_INTERNAL_PATCH"
    assert program["active_slice"] == expected["active_slice"]
    assert program["next_action"]["item_id"] == NEXT
    assert program["next_action"]["FIN_0_1_4_current_projection_ref"] == PROJECTION_REF
    assert program["next_action"]["FIN_0_1_4_current_projection_sha256"] == _sha256(
        PROJECTION_REF
    )
    assert s4["current_next_action"] == NEXT
    transfer = s4["FIN_0_1_3_to_FIN_0_1_4_version_scope_disposition"]
    assert transfer["decision_ref"] == DECISION_REF
    assert transfer["decision_sha256"] == _sha256(DECISION_REF)
    assert transfer["current_projection_ref"] == PROJECTION_REF
    assert transfer["current_projection_sha256"] == _sha256(PROJECTION_REF)
    assert transfer["open_issue_ids"] == ISSUES
    assert transfer["FIN_0_1_4_S0_stage_plan_created_or_executed"] is False

    assert [row["issue_id"] for row in roots] == ISSUES
    assert all(row["status"] == "open" for row in roots)
    assert all(NEXT in row["allowed_run_scopes"] for row in roots)
    assert pattern["pattern_id"] == expected["pattern_id"]
    assert pattern["status"] == expected["pattern_status"]
    assert decision["product_truth"]["FIN_0_1_4"] == "S0_stage_plan_ready_not_started"


def test_living_docs_preserve_product_boundary_and_next_stage_plan() -> None:
    lineage = (ROOT / LINEAGE_REF).read_text(encoding="utf-8")
    canonical = (ROOT / CANONICAL_REF).read_text(encoding="utf-8")
    technical = (ROOT / TECHNICAL_REF).read_text(encoding="utf-8")
    context = (ROOT / "docs/project_os/current_context_pack.zh-CN.md").read_text(
        encoding="utf-8"
    )
    worklog = (ROOT / WORKLOG_REF).read_text(encoding="utf-8")

    for text in (lineage, canonical, technical, context, worklog):
        assert NEXT in text
        assert "FIN 0.1.3" in text
        assert "FIN 0.1.4" in text
        assert "FIN 0.2" in text or "FIN0.2" in text
    assert "无自动 T05" in worklog
    assert "observed=`[0,0,0,0,0]`" in context
    assert "S0 StagePlan" in lineage
