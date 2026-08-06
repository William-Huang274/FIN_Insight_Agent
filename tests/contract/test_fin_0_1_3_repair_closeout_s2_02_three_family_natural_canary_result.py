from __future__ import annotations

import json
import hashlib
from pathlib import Path

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest


ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_3_repair_closeout_s2_02_"
    "three_family_natural_canary_result_v1_0.json"
)
ACTIVE_SUITE = ROOT / (
    "configs/releases/fin_ia_0_1_3_repair_closeout_s2_02_"
    "active_test_suite_successor_v1_1.json"
)


def test_public_natural_canary_result_is_exact_once_secret_safe_and_bounded() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    body = {key: value for key, value in result.items() if key != "record_digest"}
    assert result["record_digest"] == canonical_digest(body)
    assert result["execution"] == {
        "status": "terminal_succeeded_exact_once",
        "terminal_code": "three_family_canary_pass",
        "provider_calls": 3,
        "captures": 3,
        "retry_count": 0,
        "fallback_count": 0,
        "business_artifact_promotions": 0,
        "skipped_request_ids": [],
        "total_usage": {
            "input_tokens": 3093,
            "output_tokens": 362,
            "total_tokens": 3455,
        },
    }
    assert [row["case_key"] for row in result["family_results"]] == [
        "DELL",
        "MU",
        "NVDA",
    ]
    assert all(row["rubric"]["pass"] for row in result["family_results"])
    assert all(row["rubric"]["total"] == 10 for row in result["family_results"])
    assert result["disposition"]["S2_02"] == "pass_closed"
    assert result["disposition"]["S3_dynamic_decision_surface"] == "not_proven"
    text = RESULT.read_text(encoding="utf-8").lower()
    assert "\\.codex_runtime" not in text
    assert "admission.json" not in text
    assert "terminal_result.json" not in text
    assert "deepseek_api_key" not in text
    assert "authorization" not in text


def test_active_suite_closes_s2_02_without_authorizing_full_chain() -> None:
    suite = json.loads(ACTIVE_SUITE.read_text(encoding="utf-8"))
    body = {key: value for key, value in suite.items() if key != "suite_digest"}
    assert suite["suite_digest"] == canonical_digest(body)
    assert suite["decision_sha256"] == hashlib.sha256(RESULT.read_bytes()).hexdigest()
    assert suite["observed_result"] == (
        "169 passed / 1 historical event-time assertion deselected"
    )
    assert suite["stage_boundary"]["S2_02_natural_canary"] == "pass_closed"
    assert suite["stage_boundary"]["S2_03"] == "next"
    assert suite["stage_boundary"]["full_chain_authorized"] is False
