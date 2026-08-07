from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_3_s2_06_supervisor_contract_v1_1_"
    "independent_fresh_zero_call_proof_result_v1_0.json"
)


def _digest(value: dict) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def test_successor_fresh_proof_is_digest_bound_and_zero_call() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    body = {key: value for key, value in result.items() if key != "result_digest"}

    assert result["result_digest"] == _digest(body)
    assert result["source_commit"] == {
        "clean": True,
        "commit": "978c7c337489b0b48d39fc3a12107f2a65f4755f",
        "synced": True,
        "upstream_commit": "978c7c337489b0b48d39fc3a12107f2a65f4755f",
    }
    assert result["independent_proof"]["clean_git_archives"] == 2
    assert result["independent_proof"]["fresh_python_processes"] == 2
    assert result["independent_proof"]["worker_result"]["pytest"]["passed"] == 27
    assert set(result["observed_counts"].values()) == {0}


def test_successor_fresh_proof_keeps_replacement_and_product_claims_closed() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    boundary = result["acceptance_boundary"]

    assert boundary["RC_P36_147_engineering_repair"] == (
        "independent_fresh_proof_pass"
    )
    assert boundary["DELL_replacement_authority"] is False
    assert boundary["supervised_recoverability"] == "not_proven"
    assert boundary["business_promotion"] is False
    assert boundary["release"] is False
    assert result["next_action_authorized"] is False
