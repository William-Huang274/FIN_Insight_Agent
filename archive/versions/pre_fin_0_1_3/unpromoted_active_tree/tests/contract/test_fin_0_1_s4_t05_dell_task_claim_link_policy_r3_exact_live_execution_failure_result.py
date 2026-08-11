from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_contract_policies import (
    FactSupportAuthorityPolicy,
    S3_TASK_CLAIM_LINK_POLICY_REF,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    DeepSeekS3ThreeCellNodeExecutor,
    S3ThreeCellBoundedAgentExecutor,
)


RESULT = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_task_claim_link_policy_r3_"
    "exact_live_execution_failure_result_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _capture_path(digest: str) -> Path:
    root = (
        ROOT
        / ".codex_runtime/"
        "fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1/"
        "canonical-runtime/objects/fin01/provider-output-captures"
    )
    matches = list(root.rglob(f"{digest}.json"))
    assert len(matches) == 1
    return matches[0]


def test_r3_terminalized_and_stopped_without_pairing_or_retry() -> None:
    result = _load(RESULT)
    terminal = result["terminal_result"]
    stop = result["stop_contract_observation"]

    assert result["status"] == (
        "terminal_failed_WWC_numeric_authority_surface_mismatch_"
        "admission_consumed_no_retry"
    )
    assert [
        terminal["work_unit_state"],
        terminal["attempt_state"],
        terminal["research_run_state"],
    ] == ["failed", "failed", "failed"]
    assert terminal["artifact_count"] == 0
    assert terminal["orphaned_run"] is False
    assert terminal["runner_exit_code"] == 0
    assert stop["paired_assessment_performed"] is False
    assert stop["DELL_R2_proven"] is False
    assert [
        stop["automatic_retry_count"],
        stop["fallback_count"],
        stop["replay_count"],
        stop["relaunch_count"],
        stop["rerun_count"],
    ] == [0, 0, 0, 0, 0]


def test_r3_receipts_runtime_result_and_exact_input_are_digest_bound() -> None:
    result = _load(RESULT)
    assert _sha256(ROOT / result["authority_decision_ref"]) == (
        result["authority_decision_sha256"]
    )
    assert _sha256(ROOT / result["admission"]["admission_ref"]) == (
        result["admission"]["admission_file_sha256"]
    )
    for key in (
        "project_os_preflight",
        "preflight",
        "runtime_result",
        "terminal_inspection",
        "launch_receipt",
        "exit_receipt",
    ):
        assert _sha256(ROOT / result["runtime_evidence"][f"{key}_ref"]) == (
            result["runtime_evidence"][f"{key}_sha256"]
        )
    replay = result["authority_surface_replay"]
    assert _sha256(ROOT / replay["exact_input_object_ref"]) == (
        replay["exact_input_object_sha256"]
    )


def test_task_claim_policy_live_path_expanded_only_known_aliases() -> None:
    result = _load(RESULT)
    evidence = result["runtime_evidence"]
    claim_capture = _load(
        _capture_path(evidence["claim_capture_object_digest"])
    )
    task_capture = _load(_capture_path(evidence["WWC_capture_object_digest"]))
    claims = json.loads(claim_capture["assistant_output_text"])
    tasks = json.loads(task_capture["assistant_output_text"])
    input_head = _load(
        ROOT / result["authority_surface_replay"]["exact_input_object_ref"]
    )
    cell = next(
        row
        for row in input_head["input_pack"]["cell_inputs"]
        if row["program_cell_id"] == "demand_authenticity_and_sustainability"
    )

    expanded = (
        DeepSeekS3ThreeCellNodeExecutor._expand_specialist_task_claim_links(
            output=tasks,
            cell_input=cell,
            validated_segments={"owner_grade_claim_cards": claims},
            policy_ref=S3_TASK_CLAIM_LINK_POLICY_REF,
        )
    )
    aliases = [
        row["claim_alias"] for row in tasks["what_would_change"]
    ]
    expanded_claim_ids = [
        row["claim_id"] for row in expanded["what_would_change"]
    ]
    known_claim_ids = {
        row["claim_id"] for row in claims["judgment_layer"]
    }

    assert aliases == ["Q001", "Q002"]
    assert set(expanded_claim_ids) == known_claim_ids
    assert all(
        "claim_id" not in row for row in tasks["what_would_change"]
    )
    assert result["live_policy_observation"]["RC_P36_059_recurred"] is False
    assert result["first_credible_failure"]["unknown_claim_link_count"] == 0


def test_first_failure_is_owned_numeric_authority_surface_drift() -> None:
    result = _load(RESULT)
    evidence = result["runtime_evidence"]
    task_capture = _load(_capture_path(evidence["WWC_capture_object_digest"]))
    tasks = json.loads(task_capture["assistant_output_text"])
    input_head = _load(
        ROOT / result["authority_surface_replay"]["exact_input_object_ref"]
    )
    cell = next(
        row
        for row in input_head["input_pack"]["cell_inputs"]
        if row["program_cell_id"] == "demand_authenticity_and_sustainability"
    )

    fact_policy = FactSupportAuthorityPolicy.from_cell_input(cell)
    wwc_surface = (
        S3ThreeCellBoundedAgentExecutor._owner_grade_authority_surface(cell)
    )
    fact_numeric = set(fact_policy.numeric_refs)
    wwc_numeric = set(
        wwc_surface["numeric_fact_scope_and_cannot_support"]
    )
    first_task_refs = set(tasks["what_would_change"][0]["authority_refs"])
    second_task_refs = set(tasks["what_would_change"][1]["authority_refs"])
    accepted_evidence = set(wwc_surface["accepted_evidence_refs"])

    assert len(fact_numeric) == 6
    assert wwc_numeric == set()
    assert first_task_refs == fact_numeric
    assert first_task_refs - wwc_numeric == fact_numeric
    assert second_task_refs <= accepted_evidence
    assert result["root_cause_classification"][
        "immediate_failure_owner"
    ] == "project_runtime_validator_authority_surface"
    assert result["root_cause_classification"][
        "model_or_provider_fault"
    ] is False
