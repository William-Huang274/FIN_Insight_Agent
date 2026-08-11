from __future__ import annotations

import json
from pathlib import Path

from sec_agent.canonical_runtime.models import canonical_digest


ROOT = Path(__file__).resolve().parents[2]
RESULT = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_3_s1_08_dell_current_search_canary_result_v1_0.json"
)
RESULT_CANONICAL_DIGEST = "b6d145788647a9b620457a54641848b748209c0bd53f2f724566bc85917822ce"


def _load() -> dict:
    return json.loads(RESULT.read_text(encoding="utf-8"))


def test_r1_is_immutable_terminal_and_secret_free() -> None:
    assert "@" not in RESULT.read_text(encoding="utf-8")
    payload = _load()
    assert canonical_digest(payload) == RESULT_CANONICAL_DIGEST
    result = payload["result"]
    assert result["status"] == "failed"
    assert result["phase"] == "candidate_generation"
    assert result["code"] == "unexpected_project_failure:RemoteDisconnected"
    assert result["candidate_result"] is None
    assert result["ranking_admitted"] is False
    assert result["observed_counts"] == {
        "model_calls": 0,
        "provider_calls": 0,
        "retry_calls": 0,
        "network_calls": 19,
    }
    assert payload["runtime_identity"]["SEC_contact_plaintext_persisted"] is False


def test_r1_terminal_and_shared_receipt_are_digest_bound() -> None:
    result = _load()["result"]
    body = dict(result)
    terminal_digest = body.pop("terminal_digest")
    body.pop("terminal_object")
    receipt = body.pop("shared_admission_receipt")
    assert canonical_digest(body) == terminal_digest
    assert receipt["state"] == "terminal"
    assert receipt["terminal_status"] == "failed"
    assert receipt["terminal_code"] == result["code"]
    assert receipt["terminal_result_digest"] == terminal_digest
    assert receipt["finalized_at"] == result["completed_at"]
