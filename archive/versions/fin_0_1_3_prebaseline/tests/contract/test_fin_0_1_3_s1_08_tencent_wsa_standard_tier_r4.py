from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from sec_agent.project_os_preflight import run_project_os_preflight
from sec_agent.s1_08_tencent_wsa_query_only_replacement import (
    TencentWSAQueryOnlyReplacementError,
)
from sec_agent.s1_08_tencent_wsa_standard_tier_r4 import (
    PREDECESSOR_ATTEMPT_ID,
    RUN_SCOPE,
    TencentWSAStandardTierR4Error,
    build_safe_request_capture,
    build_standard_tier_r4_terminal_result,
    compile_query_only_request,
    load_standard_tier_r4_authority,
)


ROOT = Path(__file__).resolve().parents[2]
AUTHORITY = (
    ROOT
    / "configs/releases/fin_ia_0_1_3_s1_08_tencent_wsa_standard_tier_r4_authority_v1_0.json"
)
R3_RESULT = (
    ROOT
    / "configs/releases/fin_ia_0_1_3_s1_08_tencent_wsa_exact_copy_ak_sk_r3_result_v1_0.json"
)


def _query() -> dict:
    return {
        "query_id": "DELL-TENCENT-WSA-STANDARD-TIER-R4-Q1",
        "case_key": "DELL",
        "semantic_intent_ref": "DELL-DIAGNOSTIC-Q1",
        "query_text": (
            "Dell AI server demand customers supply chain 2026 earnings industry"
        ),
        "request_body_fields": ["Query"],
        "optional_fields": [],
        "result_ceiling": 10,
    }


def test_r4_changes_only_subscription_and_keeps_the_r3_query_exact() -> None:
    predecessor = json.loads(R3_RESULT.read_text(encoding="utf-8"))
    body = compile_query_only_request(_query())
    assert body == predecessor["request_capture"]["request_body"]
    assert body == {
        "Query": "Dell AI server demand customers supply chain 2026 earnings industry"
    }
    capture = build_safe_request_capture(
        endpoint="wsa.tencentcloudapi.com", request_body=body
    )
    assert capture["request_body_fields"] == ["Query"]
    assert capture["credential_fields_present"] is False


@pytest.mark.parametrize("field", ["Mode", "Site", "Cnt", "Freshness"])
def test_r4_rejects_optional_wire_mutations(field: str) -> None:
    query = deepcopy(_query())
    query[field] = 0
    with pytest.raises(
        TencentWSAQueryOnlyReplacementError,
        match="optional_field_surface_forbidden",
    ):
        compile_query_only_request(query)


def test_r4_terminal_has_distinct_lineage_and_changed_variable() -> None:
    capture = build_safe_request_capture(
        endpoint="wsa.tencentcloudapi.com",
        request_body=compile_query_only_request(_query()),
    )
    terminal = build_standard_tier_r4_terminal_result(
        admission_id="fin013-s1-08-tencent-wsa-standard-tier-r4",
        source_commit="a" * 40,
        status="completed",
        terminal_code="response_materialized",
        request_capture=capture,
        provider_projection={"provider_version": "standard"},
        network_call_count=1,
        elapsed_ms=100,
        sdk_version="3.1.152",
    )
    assert terminal["predecessor_attempt_id"] == PREDECESSOR_ATTEMPT_ID
    assert terminal["changed_variable"] == "provider_subscription_lite_to_standard"
    assert terminal["expected_provider_version"] == "standard"
    assert terminal["observed_counts"] == {
        "provider_calls": 1,
        "network_calls": 1,
        "retry_calls": 0,
        "model_calls": 0,
        "document_fetches": 0,
        "evidence_promotions": 0,
    }


def test_r4_terminal_rejects_more_than_one_call() -> None:
    capture = build_safe_request_capture(
        endpoint="wsa.tencentcloudapi.com",
        request_body=compile_query_only_request(_query()),
    )
    with pytest.raises(TencentWSAStandardTierR4Error, match="network_count_invalid"):
        build_standard_tier_r4_terminal_result(
            admission_id="fixture",
            source_commit="a" * 40,
            status="failed",
            terminal_code="typed_failure",
            request_capture=capture,
            provider_projection=None,
            network_call_count=2,
            elapsed_ms=100,
            sdk_version="3.1.152",
        )


def test_r4_authority_is_distinct_standard_tier_and_non_promotable() -> None:
    authority = load_standard_tier_r4_authority(AUTHORITY)
    assert authority["predecessor_attempt_id"] == PREDECESSOR_ATTEMPT_ID
    assert authority["admission_id"].endswith("r4")
    assert authority["changed_variable"] == "provider_subscription_lite_to_standard"
    assert authority["expected_provider_version"] == "standard"
    assert authority["execution_contract"]["provider_call_ceiling"] == 1
    assert authority["execution_contract"]["retry_ceiling"] == 0
    assert authority["execution_contract"]["same_query_as_predecessor_required"] is True
    assert authority["execution_contract"]["evidence_promotion_allowed"] is False


def test_consumed_r4_scope_is_registered_but_no_longer_current_authority() -> None:
    result = run_project_os_preflight(ROOT, run_scope=RUN_SCOPE)
    assert result["status"] == "blocked"
    assert result["scope_resolution"]["status"] == "registered"
    assert result["scope_resolution"]["owner_stage"] == "S1"
    assert result["contract_errors"] == []
    assert result["open_full_chain_blocker_count"] >= 1
    assert all(
        RUN_SCOPE not in blocker["allowed_run_scopes"]
        for blocker in result["open_full_chain_blockers"]
    )


def test_r4_authority_contains_no_credential_material() -> None:
    serialized = AUTHORITY.read_text(encoding="utf-8")
    assert "AKID" not in serialized
    assert "SecretKey" not in serialized
