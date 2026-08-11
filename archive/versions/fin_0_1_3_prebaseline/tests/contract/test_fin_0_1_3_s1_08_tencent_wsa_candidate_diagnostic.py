from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from sec_agent.s1_08_tencent_wsa_candidate_diagnostic import (
    TencentWSADiagnosticError,
    build_terminal_result,
    canonicalize_candidate_locator,
    load_tencent_wsa_candidate_profile,
    normalize_search_pro_response,
    redact_runtime_value,
)


ROOT = Path(__file__).resolve().parents[2]
PROFILE = (
    ROOT
    / "configs/runtime/fin_ia_0_1_3_s1_08_tencent_wsa_candidate_provider_profile_v1_0.json"
)


def _response() -> dict:
    return {
        "Query": "Dell AI server demand customers supply chain 2026 earnings industry",
        "Pages": [
            json.dumps(
                {
                    "title": "Dell Technologies announces results",
                    "url": "https://investors.delltechnologies.com/news?a=1&utm_source=x",
                    "date": "2026/05/28 16:05:00",
                    "passage": "Official results and AI server demand commentary.",
                    "site": "Dell Technologies",
                    "score": 0.91,
                }
            ),
            json.dumps(
                {
                    "title": "Duplicate tracking form",
                    "url": "https://investors.delltechnologies.com/news?utm_medium=y&a=1",
                    "passage": "Duplicate locator.",
                    "score": 0.8,
                }
            ),
            "not-json",
        ],
        "Version": "standard",
        "RequestId": "fixture-request-id",
    }

def test_profile_is_one_call_secret_safe_and_non_promotable() -> None:
    profile = load_tencent_wsa_candidate_profile(PROFILE)
    assert profile["diagnostic_budget"]["provider_call_ceiling"] == 1
    assert profile["diagnostic_budget"]["retry_ceiling"] == 0
    assert profile["authentication"]["credential_persistence_allowed"] is False
    assert profile["capability_boundary"]["evidence_promotion_allowed"] is False
    assert profile["capability_boundary"]["production_capability_claim_allowed"] is False


def test_searchpro_pages_normalize_and_dedupe_without_evidence_authority() -> None:
    result = normalize_search_pro_response(_response())
    assert result["provider_version"] == "standard"
    assert result["raw_page_count"] == 3
    assert result["normalized_unique_locator_count"] == 1
    assert result["published_date_count"] == 1
    assert result["locators"][0]["canonical_url"].endswith("/news?a=1")
    assert result["locators"][0]["evidence_promotion_allowed"] is False
    assert result["locators"][0]["financial_fact_authority"] is False
    assert result["rejections"] == [{"provider_rank": 3, "code": "page_invalid_json"}]


def test_schema_and_locator_mutations_fail_closed() -> None:
    with pytest.raises(TencentWSADiagnosticError, match="response_pages_missing"):
        normalize_search_pro_response({"Query": "x"})
    with pytest.raises(TencentWSADiagnosticError, match="locator_credentials_forbidden"):
        canonicalize_candidate_locator("https://user:secret@example.com/a")

    profile = load_tencent_wsa_candidate_profile(PROFILE)
    mutated = deepcopy(profile)
    mutated["capability_boundary"]["evidence_promotion_allowed"] = True
    path = ROOT / ".codex_runtime/test-tencent-wsa-mutated-profile.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(mutated), encoding="utf-8")
    with pytest.raises(TencentWSADiagnosticError, match="false_promotion"):
        load_tencent_wsa_candidate_profile(path)


def test_terminal_and_redaction_keep_failure_auditable_without_secret() -> None:
    secret_id = "runtime-secret-id-fixture"
    secret_key = "runtime-secret-key-fixture"
    terminal = build_terminal_result(
        admission_id="fixture-admission",
        source_commit="a" * 40,
        status="failed",
        terminal_code="typed_failure",
        request_capture={"request_body": {"Query": "fixture"}},
        provider_projection=None,
        network_call_count=1,
        elapsed_ms=10,
        sdk_version="3.1.152",
        failure={"message": f"bad {secret_id} and {secret_key}"},
    )
    redacted = redact_runtime_value(terminal, (secret_id, secret_key))
    serialized = json.dumps(redacted)
    assert secret_id not in serialized
    assert secret_key not in serialized
    assert serialized.count("[REDACTED]") == 2
    assert redacted["observed_counts"] == {
        "provider_calls": 1,
        "network_calls": 1,
        "retry_calls": 0,
        "model_calls": 0,
        "document_fetches": 0,
        "evidence_promotions": 0,
    }
