from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from sec_agent.hermetic_test_runner import (
    validate_host_current_program_projection,
)


ROOT = Path(__file__).resolve().parents[2]
RESULT_REF = Path(
    "configs/releases/"
    "fin_ia_0_1_2_s0_fresh_clean_environment_qualification_"
    "terminal_failure_and_project_level_disposition_required_v1_0.json"
)
AUTHORITY_REF = Path(
    "configs/releases/"
    "fin_ia_0_1_2_s0_fresh_clean_environment_qualification_"
    "authority_decision_v1_0.json"
)
PROJECTION_REF = Path(
    "configs/runtime/fin_ia_0_1_2_current_program_projection_v2_2.json"
)
PROGRAM_REF = Path(
    "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)
S4_REF = Path(
    "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)
CAPABILITY_REF = Path("docs/project_os/capability_status_ledger.jsonl")
ISSUE_REF = Path("docs/project_os/root_cause_issue_ledger.jsonl")
NEXT = (
    "FIN-0.1.2-S0-CLEAN-QUALIFICATION-FIRST-CREDIBLE-FAILURE-"
    "PROJECT-LEVEL-DISPOSITION-DECISION"
)


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _load(path: Path) -> dict:
    return json.loads(
        (ROOT / path).read_text(encoding="utf-8"),
        object_pairs_hook=_strict_object,
    )


def _jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line, object_pairs_hook=_strict_object)
        for line in (ROOT / path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _sha256(path: Path) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def test_terminal_result_binds_consumed_authority_and_restricted_evidence() -> None:
    result = _load(RESULT_REF)
    assert result["status"] == (
        "terminal_failed_no_retry_project_level_disposition_required"
    )
    assert result["authority_binding"] == {
        "ref": AUTHORITY_REF.as_posix(),
        "sha256": _sha256(AUTHORITY_REF),
    }
    execution = result["execution"]
    assert execution["attempt_consumed"] is True
    assert execution["maximum_attempts"] == 1
    assert execution["automatic_retry_or_replacement_attempts"] == 0
    assert execution["credential_model_provider_network_business_calls"] == [
        0,
        0,
        0,
        0,
        0,
    ]
    evidence = result["restricted_evidence"]
    assert evidence["business_promotable"] is False
    for key, value in evidence.items():
        if key.endswith("_sha256"):
            assert re.fullmatch(r"[0-9a-f]{64}", value)


def test_terminal_counts_and_structural_root_cause_are_honest() -> None:
    result = _load(RESULT_REF)
    summary = result["result_summary"]
    assert summary["disposable_a_tests"] == {"passed": 45, "failed": 54}
    assert summary["disposable_b_tests"] == {"passed": 45, "failed": 54}
    assert summary["gating_failures_each"] == 41
    assert summary["historical_findings_each"] == 13
    assert summary["registered_runtime_resources_present"] == [29, 29]
    assert summary["semantic_unknown_absolute_path_count"] == [53, 53]
    failure = result["first_credible_failure"]
    assert failure["failure_code"] == (
        "current_manifest_phase_and_test_dependency_closure_incomplete"
    )
    assert failure["project_owned"] is True
    assert failure["model_or_provider_fault"] is False
    assert failure["financial_runtime_L1_failure"] is False
    assert failure["one_file_at_a_time_patch_forbidden"] is True


def test_current_projection_is_blocked_without_attempt_state_or_version_bump() -> None:
    projection = _load(PROJECTION_REF)
    assert validate_host_current_program_projection(
        ROOT, PROJECTION_REF.as_posix()
    ) == PROJECTION_REF
    assert projection["lifecycle_state"] == "blocked"
    assert projection["current_truth"]["product_version"] == "FIN_0_1_2"
    assert projection["current_truth"]["current_next_action"] == NEXT
    assert projection["execution_authority"][
        "clean_environment_acceptance_authorized"
    ] is False
    assert not {
        "attempt_id",
        "run_id",
        "execution_started",
        "terminal_result",
    }.intersection(projection["current_truth"])


def test_backlogs_and_project_os_share_terminal_truth() -> None:
    program = _load(PROGRAM_REF)
    s4 = _load(S4_REF)
    projection = _load(PROJECTION_REF)
    assert program["current_version_rebaseline"]["projection_ref"] == (
        PROJECTION_REF.as_posix()
    )
    assert program["next_action"]["item_id"] == NEXT
    assert s4["current_next_action"] == NEXT
    assert projection["current_truth"]["current_next_action"] == NEXT
    capability = _jsonl(CAPABILITY_REF)[-1]
    assert capability["current_next"] == NEXT
    assert capability["stage_acceptance"]["FIN_0_1_2_S0"] == (
        "blocked_project_level_disposition_required"
    )


def test_issue_disposition_closes_only_live_proven_boundaries() -> None:
    result = _load(RESULT_REF)
    dispositions = result["issue_disposition"]
    assert dispositions["RC-P36-092"].startswith("closed_")
    assert dispositions["RC-P36-096"].startswith("closed_")
    for number in (90, 91, 93, 94, 95, 97):
        assert dispositions[f"RC-P36-{number:03d}"].startswith(
            ("open_", "new_open_")
        )

    issues = _jsonl(ISSUE_REF)
    latest = {}
    for number in range(90, 98):
        latest[number] = [
            row
            for row in issues
            if f"RC-P36-{number:03d}" in row.get("issue_id", "")
        ][-1]
    assert {number for number, row in latest.items() if row["status"] == "closed"} == {
        92,
        96,
    }
    assert {number for number, row in latest.items() if row["status"] == "open"} == {
        90,
        91,
        93,
        94,
        95,
        97,
    }
