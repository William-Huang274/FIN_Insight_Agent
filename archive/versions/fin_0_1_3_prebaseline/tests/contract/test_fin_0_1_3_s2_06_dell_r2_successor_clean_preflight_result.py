from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_3_s2_06_dell_r2_supervisor_"
    "successor_entrypoint_clean_preflight_result_v1_0.json"
)


def _digest(value: dict) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def test_clean_preflight_result_is_digest_bound_and_zero_call() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    body = {key: value for key, value in result.items() if key != "result_digest"}

    assert result["result_digest"] == _digest(body)
    assert result["project_os_preflight"]["status"] == "pass"
    assert result["project_os_preflight"]["open_full_chain_blocker_count"] == 0
    assert result["runner_preflight"]["supervisor_plan_schema_version"].endswith(
        "v1_1"
    )
    assert result["runner_preflight"]["expected_provider_calls"] == 8
    assert result["runner_preflight"]["provider_call_ceiling"] == 11
    assert set(result["postflight"].values()) == {False, 0}


def test_clean_preflight_does_not_authorize_or_materialize_R2() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    acceptance = result["stage_acceptance"]

    assert acceptance["successor_entrypoint_clean_synced_preflight"] == "pass"
    assert acceptance["DELL_R2_execution_instruction"] is False
    assert acceptance["DELL_R2_admission"] is False
    assert acceptance["DELL_R2_execution"] is False
    assert acceptance["supervised_recoverability"] == "not_proven"
    assert result["next_action_authorized_automatically"] is False
