from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (
    S3ThreeCellBoundedAgentAdmission,
)
from sec_agent.canonical_runtime.models import canonical_digest


DECISION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_action_planning_temporal_"
    "authority_and_capture_v2_terminal_result_materialization_fresh_"
    "exact_admission_r6_authority_decision_v1_0.json"
)
PROOF = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_action_planning_temporal_"
    "authority_and_capture_v2_terminal_result_materialization_fresh_"
    "agent_proof_decision_v1_0.json"
)
IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_action_planning_temporal_"
    "authority_and_capture_v2_terminal_result_materialization_minimum_"
    "zero_call_implementation_v1_0.json"
)
GENERATOR = ROOT / (
    "scripts/releases/prepare_fin_ia_0_1_s4_t06_mu_temporal_authority_"
    "terminal_result_fresh_proof.py"
)
RUNTIME_DB = ROOT / (
    ".codex_runtime/fin01-s3-t09-three-cell-deepseek-segmented-"
    "live-validation-r1/canonical-runtime/canonical.sqlite"
)
PROGRAM_BACKLOG = ROOT / (
    "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)
S4_BACKLOG = ROOT / (
    "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)
AUTHORITY = (
    "S4-T06-MU-ACTION-PLANNING-TEMPORAL-AUTHORITY-AND-CAPTURE-V2-"
    "TERMINAL-RESULT-MATERIALIZATION-FRESH-EXACT-ADMISSION-R6-"
    "AUTHORITY-DECISION"
)
NEXT = (
    "S4-T06-MU-ACTION-PLANNING-TEMPORAL-AUTHORITY-AND-CAPTURE-V2-"
    "TERMINAL-RESULT-MATERIALIZATION-FRESH-EXACT-ADMISSION-R6-ISSUANCE"
)
EXECUTION_AUTHORITY = (
    "S4-T06-MU-ACTION-PLANNING-TEMPORAL-AUTHORITY-AND-CAPTURE-V2-"
    "TERMINAL-RESULT-MATERIALIZATION-R6-EXACT-LIVE-EXECUTION-AND-"
    "SUCCESS-ONLY-PAIRED-ASSESSMENT-AUTHORITY-DECISION"
)


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_authority_binds_exact_fresh_proof_and_admission_payload() -> None:
    decision = _load(DECISION)
    proof = _load(PROOF)
    source = decision["source_authority"]
    frozen = decision["frozen_R6_admission"]

    assert source["fresh_proof_sha256"] == _sha256(PROOF)
    assert source["implementation_sha256"] == _sha256(IMPLEMENTATION)
    assert source["proof_generator_sha256"] == _sha256(GENERATOR)
    assert proof["implementation_reaudit"]["implementation_sha256"] == (
        _sha256(IMPLEMENTATION)
    )
    assert proof["proof_generator"]["sha256"] == _sha256(GENERATOR)
    for relative_path, expected in proof["implementation_reaudit"][
        "exact_code_bindings"
    ].items():
        assert _sha256(ROOT / relative_path) == expected

    payload = proof["prospective_R6_admission"]["payload"]
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(payload)
    admission.assert_profile_admissible()
    assert canonical_digest(admission.digest_payload()) == frozen[
        "admission_digest"
    ]
    assert frozen["admission_digest"] == proof[
        "prospective_R6_admission"
    ]["digest"]


def test_authority_preserves_temporal_capture_identity_and_budget() -> None:
    decision = _load(DECISION)
    frozen = decision["frozen_R6_admission"]
    payload = _load(PROOF)["prospective_R6_admission"]["payload"]

    for key in (
        "task_claim_link_policy_ref",
        "wwc_judgment_atom_policy_ref",
        "case_numeric_authority_policy_ref",
        "case_delivery_identity_policy_ref",
        "provider_output_capture_policy_ref",
        "transport_ref",
        "research_lead_transport_ref",
        "memo_writer_transport_ref",
        "output_contract_ref",
    ):
        assert frozen[key] == payload[key]
    assert frozen["retry_budget"] == 0
    assert frozen["maximum_semantic_model_calls"] == 12
    assert frozen["maximum_provider_calls"] == 12
    assert frozen["maximum_network_calls"] == 12
    assert frozen["maximum_transport_attempts_per_call"] == 1
    assert frozen["maximum_output_tokens_total"] == 16800
    assert frozen["maximum_total_cost_usd"] == 0.1
    assert frozen["source_network_calls_allowed"] is False
    assert frozen["external_tool_calls_allowed"] is False
    assert frozen["live_business_case_head_writes_allowed"] is False


def test_authority_is_zero_call_and_fresh_identity_remains_absent() -> None:
    decision = _load(DECISION)
    proof = _load(PROOF)
    frozen = decision["frozen_R6_admission"]
    candidate = ROOT / frozen["admission_ref_if_separately_issued"]
    if candidate.exists():
        assert _load(candidate) == proof["prospective_R6_admission"]["payload"]

    connection = sqlite3.connect(
        f"file:{RUNTIME_DB.resolve().as_posix()}?mode=ro",
        uri=True,
    )
    try:
        checks = (
            ("canonical_work_units", frozen["work_unit_id"]),
            ("canonical_attempts", frozen["attempt_id"]),
            ("canonical_research_run_versions", frozen["research_run_id"]),
        )
        for table, logical_id in checks:
            count = connection.execute(
                f"SELECT COUNT(*) FROM {table} WHERE logical_id = ?",
                (logical_id,),
            ).fetchone()[0]
            assert count == 0
    finally:
        connection.close()

    assert set(decision["current_turn_observed_counts"].values()) == {0}
    authority = decision["authority"]
    assert authority["future_exact_R6_admission_issuance_authorized"] is True
    assert authority["current_turn_admission_issuance_authorized"] is False
    assert authority["R6_exact_live_execution_authorized"] is False
    assert authority["credential_presence_or_value_read_authorized"] is False
    assert authority["model_provider_or_execution_network_calls_authorized"] is False
    assert authority["automatic_R7_authorized"] is False


def test_authority_advances_only_to_exact_issuance() -> None:
    decision = _load(DECISION)
    assert decision["next_action"] == NEXT
    assert decision["next_action_authorized"] is True
    assert decision["future_execution_boundary"][
        "R6_exact_live_requires_separate_zero_call_authority_decision"
    ] is True
    assert decision["future_execution_boundary"][
        "first_new_L1_failure_stops_without_R7"
    ] is True

    program = _load(PROGRAM_BACKLOG)
    s4 = _load(S4_BACKLOG)
    assert program["next_action"]["item_id"] in {
        AUTHORITY,
        NEXT,
        EXECUTION_AUTHORITY,
    }
    assert s4["current_next_action"] in {
        AUTHORITY,
        NEXT,
        EXECUTION_AUTHORITY,
    }
