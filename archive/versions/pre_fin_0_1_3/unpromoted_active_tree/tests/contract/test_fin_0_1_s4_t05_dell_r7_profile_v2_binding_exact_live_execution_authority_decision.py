from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AUTHORITY = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_r7_profile_v2_binding_"
    "exact_live_execution_authority_decision_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_R7_execution_authority_binds_exact_fresh_chain() -> None:
    authority = _load(AUTHORITY)
    source = authority["source_authority"]
    target = authority["exact_execution_target"]

    for ref_key, sha_key in (
        ("fresh_proof_ref", "fresh_proof_sha256"),
        ("admission_ref", "admission_file_sha256"),
        ("issuance_ref", "issuance_file_sha256"),
        ("project_os_preflight_ref", "project_os_preflight_sha256"),
        ("runner_preflight_ref", "runner_preflight_sha256"),
        ("host_capability_receipt_ref", "host_capability_receipt_sha256"),
    ):
        assert _sha256(ROOT / source[ref_key]) == source[sha_key]
    assert target["input_digest"] == (
        "affb9eb031b9b8f85573fc7077f69a09b35e88a3ab6687dcd85f921b68b983a0"
    )
    assert target["research_run_id"] == (
        "research_run_fin01_32fda07ef9f6d273b30a1732"
    )


def test_R7_authority_is_exact_once_without_scope_expansion() -> None:
    authority = _load(AUTHORITY)
    granted = authority["authority"]
    boundary = authority["decision_boundary"]

    assert authority["status"] == "authorized_R7_exact_once_execution_not_started"
    assert granted["R7_admission_exact_once_consumption_authorized"] is True
    assert granted["DELL_R7_exact_live_execution_authorized"] is True
    assert granted[
        "automatic_retry_fallback_replay_relaunch_patch_or_rerun_authorized"
    ] is False
    assert granted["paired_assessment_authorized_in_this_turn"] is False
    assert granted["S4_T06_or_later_authorized"] is False
    assert set(boundary.values()) == {False}


def test_R7_authority_binds_current_code_and_zero_call_preflights() -> None:
    authority = _load(AUTHORITY)
    verification = authority["pre_execution_verification"]

    assert verification["project_os_full_chain_preflight"] == "pass"
    assert verification["open_full_chain_blocker_count"] == 0
    assert verification["exact_runner_zero_call_preflight"] == (
        "pass_exact_zero_call_execution_preflight"
    )
    assert verification["credential_present"] is True
    assert verification["transport_retry_environment_zero"] is True
    assert verification["fresh_identity_absent"] is True
    for relative_path, expected in verification[
        "exact_code_bindings"
    ].items():
        assert _sha256(ROOT / relative_path) == expected
