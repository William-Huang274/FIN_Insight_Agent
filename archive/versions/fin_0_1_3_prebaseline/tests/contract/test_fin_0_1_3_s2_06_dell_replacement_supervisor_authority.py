from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DECISION = ROOT / (
    "configs/releases/fin_ia_0_1_3_s2_06_dell_replacement_"
    "supervisor_authority_decision_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _digest(value: dict) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def test_replacement_authority_binds_failure_repair_and_fresh_proof() -> None:
    decision = _load(DECISION)
    body = {key: value for key, value in decision.items() if key != "decision_digest"}

    assert decision["decision_digest"] == _digest(body)
    for binding_name in (
        "R1_terminal_disposition",
        "successor_contract_implementation",
        "independent_fresh_proof",
    ):
        binding = decision["evidence_binding"][binding_name]
        assert binding["sha256"] == _sha256(ROOT / binding["ref"])
    assert decision["evidence_binding"]["R1_terminal_disposition"]["model_fault_established"] is False
    assert decision["evidence_binding"]["independent_fresh_proof"]["tests_per_process"] == 27


def test_replacement_decision_requires_successor_entrypoint_before_issuance() -> None:
    decision = _load(DECISION)
    authority = decision["authority"]

    assert authority["decision_outcome"].startswith("approve_one_DELL_replacement")
    assert authority["admission_issuance_eligible_now"] is False
    assert authority["successor_entrypoint_implementation_required"] is True
    assert authority["automatic_execution_from_this_decision"] is False
    assert authority["automatic_R3_if_R2_fails"] is False
    assert authority["MU_NVDA_execution_authorized"] is False
    assert decision["next_action_authorized_automatically"] is False
    assert set(decision["verification"].values()) == {"zero_call", 0}


def test_replacement_contract_is_bounded_and_stops_on_new_project_failure() -> None:
    decision = _load(DECISION)
    contract = decision["replacement_contract"]

    assert contract["case_key"] == "DELL"
    assert contract["R1_reuse_forbidden"] is True
    assert contract["expected_provider_calls"] == 8
    assert contract["hard_provider_call_ceiling"] == 11
    assert contract["retry_count"] == 0
    assert contract["fallback_count"] == 0
    assert "stop_without_R3" in decision["terminal_disposition"][
        "new_project_owned_L1_or_contract_failure"
    ]
