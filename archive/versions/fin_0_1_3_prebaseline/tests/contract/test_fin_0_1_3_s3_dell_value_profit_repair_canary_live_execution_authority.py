from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.s3_dell_value_profit_repair_canary_live import (  # noqa: E402
    LIVE_SCOPE,
    validate_live_execution_authority,
)


ISSUANCE_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s3_dell_value_profit_repair_canary_"
    "live_admission_issuance_v1_0.json"
)
PREFLIGHT_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s3_dell_value_profit_repair_canary_"
    "live_clean_preflight_result_v1_0.json"
)
AUTHORITY_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s3_dell_value_profit_repair_canary_"
    "live_execution_authority_decision_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_clean_preflight_is_canonical_zero_call_and_execution_disabled() -> None:
    result = _load(PREFLIGHT_PATH)
    body = {key: value for key, value in result.items() if key != "result_digest"}
    assert result["result_digest"] == canonical_digest(body)
    assert result["status"] == "preflight_pass_execution_not_authorized"
    assert result["run_scope"] == LIVE_SCOPE
    assert result["repository"]["clean"] is True
    assert result["repository"]["synced"] is True
    assert result["repository"]["source_bindings_valid"] == 10
    assert result["admission"]["within_valid_time_window"] is True
    assert result["admission"]["consumed"] is False
    assert result["admission"]["runtime_root_absent"] is True
    assert all(
        result["observed_counts"][key] == 0
        for key in (
            "admission_consumptions",
            "provider_calls",
            "model_calls",
            "network_calls",
            "source_calls",
            "retries",
            "fallbacks",
        )
    )


def test_execution_authority_is_canonical_and_exactly_bound_to_issuance() -> None:
    issuance = _load(ISSUANCE_PATH)
    authority = _load(AUTHORITY_PATH)
    body = {
        key: value
        for key, value in authority.items()
        if key != "execution_authority_digest"
    }
    assert authority["execution_authority_digest"] == canonical_digest(body)
    validate_live_execution_authority(authority, issuance=issuance)
    assert authority["execution_binding"]["run_scope"] == LIVE_SCOPE
    assert authority["execution_binding"]["run_id"] == (
        issuance["admission"]["run_id"]
    )
    assert authority["provider_calls_maximum"] == 1
    assert authority["model_calls_maximum"] == 1
    assert authority["retries"] == 0
    assert authority["fallbacks"] == 0


def test_authority_does_not_predeclare_natural_or_report_acceptance() -> None:
    authority = _load(AUTHORITY_PATH)
    stage = authority["stage_acceptance"]
    assert stage["execution_authority_decision"] is True
    assert stage["natural_model_canary"] is False
    assert stage["repaired_dell_report"] is False
    assert stage["qualified_human_acceptance"] is False
    assert stage["owner_acceptance"] is False
    assert stage["release"] is False
    assert authority["decision_boundary"]["provider_calls"] == 0
    assert authority["decision_boundary"]["model_calls"] == 0
    assert authority["authority"][
        "automatic_second_call_retry_fallback_replay_or_relaunch_authorized"
    ] is False
