from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_contract_policies import (
    S3_RESEARCH_LEAD_CONFLICT_FACT_PRESENCE_LOCAL_MATERIALIZATION_POLICY,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V7_REF,
    S3ThreeCellBoundedAgentAdmission,
)
from scripts.releases.run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution import (
    _load_admission,
    load_execution_target,
)
from sec_agent.canonical_runtime.models import canonical_digest


DECISION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_research_lead_fact_presence_"
    "local_materialization_r2_exact_live_execution_and_success_only_"
    "paired_assessment_authority_decision_v1_0.json"
)
CANONICAL_DATABASE = ROOT / (
    ".codex_runtime/fin01-s3-t09-three-cell-deepseek-segmented-"
    "live-validation-r1/canonical-runtime/canonical.sqlite"
)
PROGRAM_BACKLOG = (
    ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)
DETAILED_BACKLOG = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)
ROOT_CAUSE_LEDGER = (
    ROOT / "docs/project_os/root_cause_issue_ledger.jsonl"
)
NEXT_ACTION = (
    "S4-T06-MU-RESEARCH-LEAD-CONFLICT-FACT-PRESENCE-LOCAL-"
    "MATERIALIZATION-R2-EXACT-LIVE-EXECUTION-AND-SUCCESS-ONLY-"
    "PAIRED-ASSESSMENT"
)
ISSUE_ID = (
    "RC-P36-078-s4-t06-mu-research-lead-deterministic-"
    "fact-presence-summary-model-ownership-recurrence"
)
CURRENT_RUNTIME_IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_runtime_audit_evidence_v2_"
    "and_material_numeric_classifier_minimum_zero_call_"
    "implementation_v1_0.json"
)
CURRENT_IDENTITY_BOUNDARY_IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_current_case_aware_"
    "delivery_identity_boundary_scope_replacement_minimum_zero_call_"
    "implementation_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _assert_historical_or_current(
    relative_path: str,
    historical_sha256: str,
) -> None:
    observed = _sha256(ROOT / relative_path)
    if observed == historical_sha256:
        return
    identity_boundary = _load(
        CURRENT_IDENTITY_BOUNDARY_IMPLEMENTATION
    )
    if (
        identity_boundary["exact_code_bindings"].get(relative_path)
        == observed
    ):
        return
    current = _load(CURRENT_RUNTIME_IMPLEMENTATION)
    assert relative_path in current[
        "historical_exact_binding_supersession"
    ]["allowed_changed_paths"]
    assert current["exact_code_bindings"][relative_path] == observed


def _canonical_payload(table: str, identity_key: str, identity: str) -> dict | None:
    connection = sqlite3.connect(CANONICAL_DATABASE)
    try:
        latest = None
        for (payload_json,) in connection.execute(
            f"select payload_json from {table}"
        ):
            payload = json.loads(payload_json)
            if payload.get(identity_key) == identity:
                latest = payload
        return latest
    finally:
        connection.close()


def _latest_issue() -> dict:
    return [
        json.loads(line)
        for line in ROOT_CAUSE_LEDGER.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip() and json.loads(line)["issue_id"] == ISSUE_ID
    ][-1]


def test_R2_authority_binds_exact_issued_admission_and_preflights() -> None:
    decision = _load(DECISION)
    source = decision["source_authority"]
    admission_path = ROOT / source["admission_ref"]
    issuance_path = ROOT / source["issuance_ref"]
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        _load(admission_path)
    )
    target = load_execution_target(issuance_path)

    for ref_key, sha_key in (
        ("fresh_proof_ref", "fresh_proof_sha256"),
        ("admission_ref", "admission_file_sha256"),
        ("issuance_ref", "issuance_file_sha256"),
        ("project_os_preflight_ref", "project_os_preflight_sha256"),
        ("runner_preflight_ref", "runner_preflight_sha256"),
        ("host_capability_receipt_ref", "host_capability_receipt_sha256"),
    ):
        assert _sha256(ROOT / source[ref_key]) == source[sha_key]
    assert canonical_digest(admission.digest_payload()) == source[
        "admission_digest"
    ]
    assert _load_admission(admission_path, target) == admission
    exact = decision["exact_execution_target"]
    assert (
        target.work_unit_id,
        target.attempt_id,
        target.research_run_id,
    ) == (
        exact["work_unit_id"],
        exact["attempt_id"],
        exact["research_run_id"],
    )


def test_R2_authority_is_zero_call_exact_once_and_success_conditional() -> None:
    decision = _load(DECISION)
    authority = decision["authority"]

    assert decision["status"] == (
        "authorized_MU_R2_exact_once_and_conditional_read_only_paired_"
        "assessment_execution_not_started"
    )
    assert authority["MU_R2_admission_exact_once_consumption_authorized"]
    assert authority["MU_R2_exact_live_execution_authorized"]
    assert authority[
        "paired_assessment_authorized_only_after_coherent_terminal_success"
    ]
    assert not authority[
        "automatic_retry_fallback_replay_relaunch_patch_or_rerun_authorized"
    ]
    assert not authority["automatic_R3_authorized"]
    assert set(decision["decision_boundary"].values()) == {False}
    assert set(decision["observed_counts"].values()) == {0}


def test_R2_authority_binds_lead_v7_budget_and_zero_call_runner() -> None:
    decision = _load(DECISION)
    source = decision["source_authority"]
    verification = decision["pre_execution_verification"]
    exact = decision["exact_execution_target"]
    project_preflight = _load(ROOT / source["project_os_preflight_ref"])
    runner_preflight = _load(ROOT / source["runner_preflight_ref"])

    assert project_preflight["status"] == "pass"
    assert project_preflight["open_full_chain_blockers"] == []
    assert runner_preflight["status"] == (
        "pass_exact_zero_call_execution_preflight"
    )
    assert runner_preflight["execution_state_counts_before"] == (
        runner_preflight["execution_state_counts_after"]
    )
    assert list(runner_preflight["execution_state_counts_before"].values()) == [
        1,
        1,
        1,
        0,
    ]
    assert set(runner_preflight["observed_counts"].values()) == {0}
    assert verification["credential_present"]
    assert not verification["credential_value_read_output_or_persisted"]
    assert not verification["provider_health_probe_performed"]
    assert verification["exact_code_binding_count"] == 7
    for relative_path, expected_sha256 in verification[
        "exact_code_bindings"
    ].items():
        _assert_historical_or_current(
            relative_path, expected_sha256
        )
    assert exact["research_lead_transport_ref"] == (
        S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V7_REF
    )
    assert exact[
        "research_lead_fact_presence_materialization_policy_ref"
    ] == (
        S3_RESEARCH_LEAD_CONFLICT_FACT_PRESENCE_LOCAL_MATERIALIZATION_POLICY
        .policy_ref
    )
    assert (
        exact["maximum_semantic_model_calls"],
        exact["maximum_provider_calls"],
        exact["maximum_network_calls"],
        exact["maximum_output_tokens"],
        exact["maximum_total_cost_usd"],
        exact["transport_retry_count"],
        exact["maximum_transport_attempts_per_call"],
    ) == (12, 12, 12, 16800, 0.1, 0, 1)


def test_R2_identity_is_absent_while_failed_R1_is_preserved() -> None:
    exact = _load(DECISION)["exact_execution_target"]

    work_unit = _canonical_payload(
        "canonical_work_units", "work_unit_id", exact["work_unit_id"]
    )
    attempt = _canonical_payload(
        "canonical_attempts", "attempt_id", exact["attempt_id"]
    )
    run = _canonical_payload(
        "canonical_research_run_versions",
        "research_run_id",
        exact["research_run_id"],
    )
    later_success = ROOT / (
        "configs/releases/fin_ia_0_1_s4_t06_mu_research_lead_"
        "fact_presence_local_materialization_r2_exact_live_"
        "execution_success_result_v1_0.json"
    )
    if later_success.exists():
        assert work_unit is not None and work_unit["state"] == "succeeded"
        assert attempt is not None and attempt["state"] == "succeeded"
        assert run is not None and run["state"] == "succeeded"
    else:
        assert work_unit is None
        assert attempt is None
        assert run is None
    failed_R1 = _canonical_payload(
        "canonical_research_run_versions",
        "research_run_id",
        "research_run_fin01_c94013e1c3666739c35ff00c",
    )
    assert failed_R1 is not None
    assert failed_R1["state"] == "failed"


def test_project_state_advances_only_to_R2_execution() -> None:
    decision = _load(DECISION)
    program = _load(PROGRAM_BACKLOG)
    detailed = _load(DETAILED_BACKLOG)
    issue = _latest_issue()
    later_assessment = ROOT / (
        "configs/releases/fin_ia_0_1_s4_t06_mu_r2_"
        "success_only_paired_assessment_result_v1_0.json"
    )

    assert decision["next_action"] == NEXT_ACTION
    if later_assessment.exists():
        progressed = (
            "S4-T06-MU-ACTION-PLANNING-TEMPORAL-AUTHORITY-AND-CAPTURE-V2-"
            "TERMINAL-RESULT-MATERIALIZATION-MINIMUM-ZERO-CALL-IMPLEMENTATION"
        )
        assert program["next_action"]["item_id"] == progressed
        assert detailed["current_next_action"] == progressed
        assert issue["status"] == (
            "closed_exact_live_Lead_v7_local_materialization_proven"
        )
        assert issue["allowed_run_scopes"] == [
            (
                "S4_T06_MU_R2_L1_numeric_authority_and_case_identity_"
                "live_recurrence_root_cause_or_scope_disposition_decision"
            ),
            "repository_and_git_hygiene",
        ]
    else:
        assert program["next_action"]["item_id"] == NEXT_ACTION
        assert detailed["current_next_action"] == NEXT_ACTION
        assert issue["status"] == (
            "R2_exact_live_authorized_execution_not_started_"
            "success_only_paired_assessment"
        )
        assert issue["allowed_run_scopes"] == [
            (
                "S4_T06_MU_research_lead_conflict_fact_presence_local_"
                "materialization_R2_exact_live_execution_and_success_only_"
                "paired_assessment"
            ),
            "repository_and_git_hygiene",
        ]
    assert decision["conditional_next_action"][
        "on_terminal_failure_or_hard_integrity_failure"
    ] == (
        "S4-T06-MU-R2-FIRST-CREDIBLE-FAILURE-ROOT-CAUSE-OR-SCOPE-"
        "DISPOSITION-DECISION"
    )
