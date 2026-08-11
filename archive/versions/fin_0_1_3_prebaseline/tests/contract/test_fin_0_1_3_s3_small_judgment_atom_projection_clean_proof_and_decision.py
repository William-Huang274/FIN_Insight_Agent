from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


PROOF_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s3_small_judgment_atom_projection_clean_independent_"
    "proof_v1_0.json"
)
DECISION_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s3_small_judgment_atom_successor_natural_canary_"
    "value_cost_risk_decision_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_clean_proof_is_canonical_isolated_and_zero_external_call() -> None:
    proof = _load(PROOF_PATH)
    body = {key: value for key, value in proof.items() if key != "result_digest"}
    assert proof["result_digest"] == canonical_digest(body)
    assert proof["clean_git_archives"] == 2
    assert proof["fresh_python_processes"] == 2
    assert proof["workers_byte_equivalent"] is True
    assert proof["private_artifacts_persisted_to_repository"] is False
    assert proof["temporary_roots_removed"] is True
    calls = proof["observed_calls"]
    assert [
        calls[key]
        for key in (
            "model_calls",
            "provider_calls",
            "network_calls",
            "source_calls",
            "retries",
        )
    ] == [0, 0, 0, 0, 0]


def test_clean_proof_replays_failure_and_materializes_truthful_terminal_refs() -> None:
    proof = _load(PROOF_PATH)
    legacy = proof["legacy_capture_audit"]
    assert legacy["accepted_evidence_refs_exact"] is True
    assert legacy["target_changed_flag_valid"] is False
    assert legacy["price_in_boundary_valid"] is False
    assert legacy["failed_output_promotable"] is False
    terminal = proof["legacy_terminal_materialization"]
    assert terminal["parsed_output_ref"] == "parsed/repair_output.json"
    assert terminal["parsed_output_exists"] is True
    assert terminal["validated_output_ref"] is None
    assert terminal["validated_output_exists"] is False
    assert terminal["raw_capture_exists"] is True
    assert [row["case_key"] for row in proof["portfolio_shape_receipts"]] == [
        "DELL",
        "MU",
        "NVDA",
    ]


def test_successor_canary_decision_binds_proof_and_separates_execution() -> None:
    decision = _load(DECISION_PATH)
    body = {
        key: value for key, value in decision.items() if key != "decision_digest"
    }
    assert decision["decision_digest"] == canonical_digest(body)
    binding = decision["immutable_basis"]["clean_proof"]
    assert binding["expected_result_digest"] == _load(PROOF_PATH)["result_digest"]
    assert binding["sha256"] == hashlib.sha256(
        PROOF_PATH.read_text(encoding="utf-8").encode("utf-8")
    ).hexdigest()
    cost = decision["cost"]
    assert cost["provider_calls_maximum"] == 1
    assert cost["model_calls_maximum"] == 1
    assert cost["retries"] == 0
    authority = decision["authority_boundary"]
    assert authority["this_decision_authorizes_one_fresh_admission_issuance"] is True
    assert authority["this_decision_authorizes_provider_execution"] is False
    assert authority["execution_requires_separate_clean_preflight_and_authority"] is True
    assert authority["success_authorizes_complete_report"] is False
