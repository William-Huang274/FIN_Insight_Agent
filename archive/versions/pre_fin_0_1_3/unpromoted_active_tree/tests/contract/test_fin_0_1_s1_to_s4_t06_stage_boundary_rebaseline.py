from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
AUDIT_REF = (
    "configs/releases/"
    "fin_ia_0_1_s1_to_s4_t06_stage_boundary_and_task_ownership_rebaseline_v1_0.json"
)
AUDIT_PATH = ROOT / AUDIT_REF
PROGRAM_PATH = ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
S4_PATH = ROOT / "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_strict_object)


def test_stage_boundary_audit_preserves_release_truth_and_stops_case_loops() -> None:
    audit = _load(AUDIT_PATH)

    assert audit["status"] == (
        "pass_boundaries_rebaselined_T05_T06_closed_honestly_blocked_"
        "T07_next_no_acceptance_inflation"
    )
    assert audit["release_truth"] == {
        "FIN_0_1_release_requirements_changed": False,
        "three_case_R2_requirement": "still_required_for_release",
        "NVDA_R3_requirement": "still_required_for_release",
        "current_release_status": "not_qualified",
        "permitted_closeout": "honest_blocked_candidate_without_release_claim",
        "reason": (
            "Reassigning work prevents a task loop; it does not convert missing "
            "DELL MU R2 or NVDA R3 evidence into a pass."
        ),
    }
    policy = audit["execution_policy_after_rebaseline"]
    assert policy["T05_additional_model_provider_network_calls"] == 0
    assert policy["T06_additional_model_provider_network_calls"] == 0
    assert policy["T06_additional_proof_packages"] == 0
    assert policy["T07_exact_live_ceiling"] == 1
    assert policy["T08_model_provider_network_calls"] == 0
    assert policy["failed_or_quarantined_output_promotion"] is False


def test_task_ownership_separates_t07_s5_and_fin_0_2() -> None:
    audit = _load(AUDIT_PATH)
    owners = {item["owner"]: item for item in audit["task_ownership_rebaseline"]}

    assert owners["S4-T05"]["decision"] == "closed_honestly_blocked"
    assert owners["S4-T06"]["decision"] == "closed_honestly_blocked"
    assert owners["S4-T07"]["decision"] == "next_active_slice_item"
    assert "fix disposable proof hermeticity" in owners["S4-T07"]["non_goals"]
    assert "hermetic independent reproducibility and RC-P36-085 disposition" in owners[
        "S5"
    ]["scope"]
    assert (
        "single compiled contract source across prompt schema validator fake selector "
        "renderer capacity budget telemetry and capture index"
        in owners["FIN_0_2"]["scope"]
    )


def test_program_and_s4_backlogs_preserve_the_boundary_without_claiming_T05_T07_pass() -> None:
    program = _load(PROGRAM_PATH)
    s4_backlog = _load(S4_PATH)

    assert program["stage_boundary_rebaseline_ref"] == AUDIT_REF
    assert program["current_truth"]["stage_boundary_rebaseline_status"] == (
        "active_T05_T06_closed_no_acceptance_inflation"
    )
    s4_slice = next(item for item in program["slices"] if item["slice_id"] == "S4")
    items = {item["item_id"]: item for item in s4_slice["items"]}
    assert items["S4-T05"]["status"].startswith("closed_honestly_blocked")
    assert items["S4-T06"]["status"].startswith("closed_honestly_blocked")
    assert items["S4-T07"]["status"].startswith("closed_honestly_blocked")
    assert items["S4-T08"]["status"].startswith("pass_read_only")
    assert program["current_truth"]["release_gate_status"]["RG3_research_outcome"] == (
        "NVDA_R2_pass_DELL_and_MU_not_proven"
    )

    assert s4_backlog["stage_boundary_rebaseline"]["release_requirements_weakened"] is False
    assert s4_backlog["current_next_action"].startswith("FIN-0.1-REPOSITORY-")


def test_living_docs_and_project_os_reference_the_rebaseline() -> None:
    expected_docs = [
        ROOT
        / "docs/architecture/repository/"
        "FIN_0_1_S1_TO_S5_STAGE_BOUNDARY_REBASELINE_20260731.zh-CN.md",
        ROOT
        / "docs/architecture/repository/"
        "FIN_0_1_PROGRAM_EXECUTION_PLAN_DRAFT_20260719.zh-CN.md",
        ROOT
        / "docs/architecture/repository/"
        "FIN_0_1_S4_THREE_CASE_TRANSFER_AND_HUMAN_CALIBRATION_EXECUTION_PLAN_"
        "20260726.zh-CN.md",
        ROOT
        / "docs/architecture/repository/"
        "RELEASE_FIN_IA_0_1_DETAILED_PRODUCT_TECHNICAL_DESIGN_20260717.zh-CN.md",
        ROOT / "docs/project_os/current_context_pack.zh-CN.md",
        ROOT
        / "docs/worklog/product_strategy/"
        "516_fin_0_1_s1_to_s4_t06_stage_boundary_rebaseline.md",
    ]
    for path in expected_docs:
        assert AUDIT_REF in path.read_text(encoding="utf-8")

    capability_lines = [
        json.loads(line, object_pairs_hook=_strict_object)
        for line in (
            ROOT / "docs/project_os/capability_status_ledger.jsonl"
        ).read_text(encoding="utf-8").splitlines()
    ]
    capability = next(
        record
        for record in reversed(capability_lines)
        if record["capability_id"]
        == "fin_0_1_s1_to_s4_t06_stage_boundary_and_task_ownership_rebaseline"
    )
    assert capability["current_next"].startswith("S4-T07-ENTRY-")

    root_cause_lines = [
        json.loads(line, object_pairs_hook=_strict_object)
        for line in (
            ROOT / "docs/project_os/root_cause_issue_ledger.jsonl"
        ).read_text(encoding="utf-8").splitlines()
    ]
    latest = {line["issue_id"]: line for line in root_cause_lines}
    assert latest[
        "RC-P36-085-s4-independent-proof-disposable-runtime-hermeticity-and-"
        "failure-observability"
    ]["status"] == "open_reassigned_S5_release_reproducibility_no_T06_block"
