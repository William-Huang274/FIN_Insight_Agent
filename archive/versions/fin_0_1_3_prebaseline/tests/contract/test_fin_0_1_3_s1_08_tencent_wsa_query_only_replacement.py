from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from sec_agent.project_os_preflight import run_project_os_preflight
from sec_agent.s1_08_tencent_wsa_query_only_replacement import (
    RUN_SCOPE,
    TencentWSAQueryOnlyReplacementError,
    build_query_only_terminal_result,
    build_safe_request_capture,
    compile_query_only_request,
    load_query_only_replacement_authority,
)


ROOT = Path(__file__).resolve().parents[2]
AUTHORITY = (
    ROOT
    / "configs/releases/fin_ia_0_1_3_s1_08_tencent_wsa_query_only_replacement_authority_v1_0.json"
)


def _query() -> dict:
    return {
        "query_id": "DELL-TENCENT-WSA-QUERY-ONLY-R2-Q1",
        "case_key": "DELL",
        "semantic_intent_ref": "DELL-DIAGNOSTIC-Q1",
        "query_text": (
            "Dell AI server demand customers supply chain 2026 earnings industry"
        ),
        "request_body_fields": ["Query"],
        "optional_fields": [],
        "result_ceiling": 10,
    }


def test_query_only_compiler_and_capture_omit_every_optional_field() -> None:
    body = compile_query_only_request(_query())
    assert body == {
        "Query": "Dell AI server demand customers supply chain 2026 earnings industry"
    }
    capture = build_safe_request_capture(
        endpoint="wsa.tencentcloudapi.com", request_body=body
    )
    assert capture["request_body"] == body
    assert capture["request_body_fields"] == ["Query"]
    assert "Mode" not in json.dumps(capture["request_body"])
    assert capture["credential_fields_present"] is False
    assert capture["capture_before_transport"] is True


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("mode", 0),
        ("Site", "example.com"),
        ("Cnt", 10),
        ("Freshness", "oneMonth"),
    ],
)
def test_query_only_compiler_rejects_optional_field_mutations(
    field: str, value: object
) -> None:
    query = deepcopy(_query())
    query[field] = value
    with pytest.raises(
        TencentWSAQueryOnlyReplacementError,
        match="optional_field_surface_forbidden",
    ):
        compile_query_only_request(query)


def test_query_only_terminal_keeps_exact_request_and_zero_downstream_counts() -> None:
    request = build_safe_request_capture(
        endpoint="wsa.tencentcloudapi.com",
        request_body=compile_query_only_request(_query()),
    )
    terminal = build_query_only_terminal_result(
        admission_id="fixture-query-only-r2",
        source_commit="a" * 40,
        status="failed",
        terminal_code="typed_failure",
        request_capture=request,
        provider_projection=None,
        network_call_count=1,
        elapsed_ms=100,
        sdk_version="3.1.152",
        failure={"error_code": "fixture"},
    )
    assert terminal["request_capture"]["request_body"] == request["request_body"]
    assert terminal["observed_counts"] == {
        "provider_calls": 1,
        "network_calls": 1,
        "retry_calls": 0,
        "model_calls": 0,
        "document_fetches": 0,
        "evidence_promotions": 0,
    }
    assert terminal["capability_boundary"]["production_capability_claim_allowed"] is False


def test_query_only_authority_is_distinct_exact_once_and_non_promotable() -> None:
    authority = load_query_only_replacement_authority(AUTHORITY)
    assert authority["status"] == "issued_unconsumed"
    assert authority["predecessor_attempt_id"].endswith("r1")
    assert authority["admission_id"].endswith("r2")
    assert compile_query_only_request(authority["query"]) == {
        "Query": authority["query"]["query_text"]
    }
    assert authority["execution_contract"]["provider_call_ceiling"] == 1
    assert authority["execution_contract"]["retry_ceiling"] == 0
    assert authority["execution_contract"]["evidence_promotion_allowed"] is False


def test_replacement_scope_is_registered_and_latest_projection_is_consistent() -> None:
    result = run_project_os_preflight(ROOT, run_scope=RUN_SCOPE)
    assert result["scope_resolution"]["status"] == "registered"
    assert result["scope_resolution"]["owner_stage"] == "S1"
    assert result["contract_errors"] == []
