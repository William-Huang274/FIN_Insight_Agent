from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_3_s2_06_dell_supervisor_"
    "r1_terminal_and_contract_drift_disposition_v1_0.json"
)


def _digest(value: dict) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def test_r1_terminal_disposition_is_digest_bound_and_fail_closed() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    body = {key: value for key, value in result.items() if key != "result_digest"}

    assert result["result_digest"] == _digest(body)
    assert result["execution"]["terminal_status"] == "terminal_failed_no_retry"
    assert result["execution"]["completed_provider_calls"] == 1
    assert result["execution"]["candidate_frozen"] is False
    assert result["root_cause"]["classification"] == (
        "project_owned_model_visible_contract_drift_not_model_instruction_failure"
    )
    assert result["campaign_disposition"] == {
        "DELL_R1": "immutable_invalidated_by_project_contract_drift",
        "MU_started": False,
        "NVDA_started": False,
        "campaign_stopped": True,
        "automatic_retry": False,
        "automatic_replacement": False,
        "maximum_shared_structural_repair_packages_remaining": 1,
        "replacement_requires_separate_authority": True,
    }


def test_r1_terminal_disposition_preserves_capture_and_no_promotion_boundary() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))

    assert result["verification"]["raw_capture_preserved"] is True
    assert result["verification"]["credential_value_persisted"] is False
    assert result["verification"]["candidate_or_hidden_score_created"] is False
    assert result["verification"]["model_provider_network_calls_after_terminal"] == [0, 0, 0]
    assert result["execution"]["business_promotable"] is False
