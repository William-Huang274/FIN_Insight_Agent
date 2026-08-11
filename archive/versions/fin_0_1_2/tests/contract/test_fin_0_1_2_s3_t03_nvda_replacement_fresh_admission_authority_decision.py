from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DECISION = ROOT / (
    "configs/releases/fin_ia_0_1_2_s3_t03_nvda_replacement_fresh_"
    "admission_authority_decision_v1_0.json"
)


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_decision_binds_fresh_proof_implementation_and_immutable_failure() -> None:
    decision = _load(DECISION)
    source = decision["source_authority"]
    for prefix in ("fresh_proof", "implementation", "immutable_primary_failure"):
        assert _sha256(ROOT / source[f"{prefix}_ref"]) == source[
            f"{prefix}_sha256"
        ]
    proof = _load(ROOT / source["fresh_proof_ref"])
    implementation = _load(ROOT / source["implementation_ref"])
    assert proof["fresh_process_proof"]["normalized_outputs_equal"] is True
    assert proof["acceptance_boundary"]["replacement_admission_issued"] is False
    for relative_path, expected in implementation["exact_code_bindings"].items():
        assert _sha256(ROOT / relative_path) == expected


def test_decision_detects_primary_only_issuer_envelope_and_supervisor() -> None:
    decision = _load(DECISION)
    evidence = decision["owned_blocker"]["evidence"]
    for prefix in (
        "primary_execution_envelope",
        "primary_admission",
        "primary_issuance",
        "primary_issuer",
        "primary_supervisor",
        "exact_live_runner",
    ):
        assert _sha256(ROOT / evidence[f"{prefix}_ref"]) == evidence[
            f"{prefix}_sha256"
        ]

    issuer = (ROOT / evidence["primary_issuer_ref"]).read_text(encoding="utf-8")
    supervisor = (ROOT / evidence["primary_supervisor_ref"]).read_text(
        encoding="utf-8"
    )
    runner = (ROOT / evidence["exact_live_runner_ref"]).read_text(
        encoding="utf-8"
    )
    assert "nvda_fresh_exact_\"\n    \"admission_r1.json" in issuer
    assert "s3_t03_admission_already_exists" in issuer
    assert "nvda_fresh_exact_admission_r1.json" in supervisor
    assert "nvda_fresh_exact_\"\n    \"admission_issuance_v1_0.json" in supervisor
    assert "admission.input_digest != prepared.input_digest" in runner
    assert "prepared.input_digest != execution_envelope" in runner


def test_decision_blocks_issuance_and_does_not_freeze_compiler_observation() -> None:
    decision = _load(DECISION)
    authority = decision["authority"]
    observation = decision["non_issuable_compiler_observation"]
    assert decision["status"].startswith("blocked_no_replacement_admission")
    assert authority["replacement_admission_issuance_authorized"] is False
    assert authority["admission_consumption_authorized"] is False
    assert authority["replacement_exact_live_execution_authorized"] is False
    assert authority["model_provider_or_execution_network_calls_authorized"] is False
    assert authority["third_exact_attempt_authorized"] is False
    assert observation["profile_admissible"] is True
    assert observation["issuable"] is False
    assert observation["prepared_execution_identity"].startswith("fin01-s3-t09-")


def test_replacement_targets_and_runtime_roots_remain_absent() -> None:
    decision = _load(DECISION)
    read_only = decision["read_only_revalidation"]
    candidates = (
        ROOT
        / "configs/releases/fin_ia_0_1_2_s3_t03_nvda_replacement_fresh_exact_admission_r2.json",
        ROOT
        / "configs/releases/fin_ia_0_1_2_s3_t03_nvda_replacement_fresh_exact_admission_issuance_v1_0.json",
        ROOT
        / "configs/runtime/fin_ia_0_1_2_s3_t03_nvda_replacement_fresh_identity_execution_envelope_v1_0.json",
        ROOT / ".codex_runtime/fin012-s3-t03-nvda-replacement-r2",
        ROOT / ".codex_runtime/fin012-s3-t03-nvda-replacement-r2-supervision",
    )
    assert not any(path.exists() for path in candidates)
    assert read_only["replacement_admission_file_absent"] is True
    assert read_only["replacement_issuance_file_absent"] is True
    assert read_only["replacement_execution_envelope_absent"] is True
    assert read_only["replacement_runtime_root_absent"] is True
    assert read_only["replacement_supervision_root_absent"] is True


def test_decision_selects_one_zero_call_controlled_successor_only() -> None:
    decision = _load(DECISION)
    disposition = decision["selected_disposition"]
    assert disposition["bundle_maximum"] == 1
    assert disposition["automatic_second_bundle"] is False
    assert disposition["after_bundle_pass"].startswith("repeat_separate_zero_call")
    assert disposition["after_bundle_failure"].startswith("S3_T03_honest_block")
    assert decision["next_action"].endswith(
        "CONTROLLED-SUCCESSOR-MINIMUM-ZERO-CALL-IMPLEMENTATION"
    )
    assert decision["next_action_authorized"] is False
    assert set(decision["current_turn_observed_counts"].values()) == {0}
