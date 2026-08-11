from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from sec_agent.project_os_preflight import run_project_os_preflight
from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.s1_08_tencent_wsa_exact_copy_ak_sk_r3 import (
    PREDECESSOR_ATTEMPT_ID,
    RUN_SCOPE,
    TencentWSAExactCopyR3Error,
    build_exact_copy_r3_terminal_result,
    build_safe_request_capture,
    compile_query_only_request,
    load_exact_copy_r3_authority,
)
from sec_agent.s1_08_tencent_wsa_query_only_replacement import (
    TencentWSAQueryOnlyReplacementError,
)


ROOT = Path(__file__).resolve().parents[2]
AUTHORITY = (
    ROOT
    / "configs/releases/fin_ia_0_1_3_s1_08_tencent_wsa_exact_copy_ak_sk_r3_authority_v1_0.json"
)


def _query() -> dict:
    return {
        "query_id": "DELL-TENCENT-WSA-EXACT-COPY-R3-Q1",
        "case_key": "DELL",
        "semantic_intent_ref": "DELL-DIAGNOSTIC-Q1",
        "query_text": (
            "Dell AI server demand customers supply chain 2026 earnings industry"
        ),
        "request_body_fields": ["Query"],
        "optional_fields": [],
        "result_ceiling": 10,
    }


def test_r3_reuses_only_the_proven_query_only_wire_shape() -> None:
    body = compile_query_only_request(_query())
    assert body == {
        "Query": "Dell AI server demand customers supply chain 2026 earnings industry"
    }
    capture = build_safe_request_capture(
        endpoint="wsa.tencentcloudapi.com", request_body=body
    )
    assert capture["request_body_fields"] == ["Query"]
    assert capture["credential_fields_present"] is False
    assert capture["authorization_or_signature_present"] is False


@pytest.mark.parametrize("field", ["Mode", "Site", "Cnt", "Freshness"])
def test_r3_still_rejects_every_optional_wire_field(field: str) -> None:
    query = deepcopy(_query())
    query[field] = 0
    with pytest.raises(
        TencentWSAQueryOnlyReplacementError,
        match="optional_field_surface_forbidden",
    ):
        compile_query_only_request(query)


def test_r3_terminal_has_distinct_lineage_and_exact_once_counts() -> None:
    capture = build_safe_request_capture(
        endpoint="wsa.tencentcloudapi.com",
        request_body=compile_query_only_request(_query()),
    )
    terminal = build_exact_copy_r3_terminal_result(
        admission_id="fin013-s1-08-tencent-wsa-exact-copy-ak-sk-r3",
        source_commit="a" * 40,
        status="failed",
        terminal_code="typed_failure",
        request_capture=capture,
        provider_projection=None,
        network_call_count=1,
        elapsed_ms=100,
        sdk_version="3.1.152",
        failure={"error_code": "fixture"},
    )
    assert terminal["predecessor_attempt_id"] == PREDECESSOR_ATTEMPT_ID
    assert terminal["admission_consumed"] is True
    assert terminal["observed_counts"] == {
        "provider_calls": 1,
        "network_calls": 1,
        "retry_calls": 0,
        "model_calls": 0,
        "document_fetches": 0,
        "evidence_promotions": 0,
    }
    assert terminal["capability_boundary"]["production_capability_claim_allowed"] is False


def test_r3_terminal_rejects_more_than_one_network_call() -> None:
    capture = build_safe_request_capture(
        endpoint="wsa.tencentcloudapi.com",
        request_body=compile_query_only_request(_query()),
    )
    with pytest.raises(TencentWSAExactCopyR3Error, match="network_count_invalid"):
        build_exact_copy_r3_terminal_result(
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


def test_r3_authority_is_distinct_exact_copy_and_non_promotable() -> None:
    authority = load_exact_copy_r3_authority(AUTHORITY)
    assert authority["status"] == "issued_unconsumed"
    assert authority["predecessor_attempt_id"] == PREDECESSOR_ATTEMPT_ID
    assert authority["admission_id"].endswith("r3")
    assert authority["credential_delivery_class"] == "owner_exact_text_hidden_input"
    assert authority["execution_contract"]["provider_call_ceiling"] == 1
    assert authority["execution_contract"]["retry_ceiling"] == 0
    assert authority["execution_contract"]["evidence_promotion_allowed"] is False
    assert compile_query_only_request(authority["query"]) == {
        "Query": authority["query"]["query_text"]
    }


def test_consumed_r3_scope_remains_registered_but_latest_projection_blocks_reuse() -> None:
    result = run_project_os_preflight(ROOT, run_scope=RUN_SCOPE)
    assert result["status"] == "blocked"
    assert result["scope_resolution"]["status"] == "registered"
    assert result["scope_resolution"]["owner_stage"] == "S1"
    assert result["contract_errors"] == []
    assert any(
        row["issue_id"].startswith("RC-P36-157-")
        for row in result["open_full_chain_blockers"]
    )


def test_authority_file_contains_no_credential_material() -> None:
    serialized = json.dumps(
        json.loads(AUTHORITY.read_text(encoding="utf-8")), ensure_ascii=False
    )
    assert "SecretId" not in serialized
    assert "SecretKey" not in serialized
    assert "AKID" not in serialized


def test_r3_live_terminal_is_digest_bound_exact_once_and_non_promotable() -> None:
    path = (
        ROOT
        / "configs/releases/fin_ia_0_1_3_s1_08_tencent_wsa_exact_copy_ak_sk_r3_result_v1_0.json"
    )
    result = json.loads(path.read_text(encoding="utf-8"))
    body = dict(result)
    digest = body.pop("result_digest")
    assert digest == canonical_digest(body)
    assert result["status"] == "completed"
    assert result["source_commit"].startswith("b9dfa025")
    assert result["request_capture"]["request_body_fields"] == ["Query"]
    assert result["observed_counts"] == {
        "provider_calls": 1,
        "network_calls": 1,
        "retry_calls": 0,
        "model_calls": 0,
        "document_fetches": 0,
        "evidence_promotions": 0,
    }
    assert result["provider_projection"]["provider_version"] == "lite"
    assert result["provider_projection"]["normalized_unique_locator_count"] == 10
    assert all(
        row["promotion_status"] == "candidate_locator_diagnostic_only"
        and row["evidence_promotion_allowed"] is False
        for row in result["provider_projection"]["locators"]
    )
    serialized = json.dumps(result, ensure_ascii=False)
    assert "AKID" not in serialized
    assert "SecretKey" not in serialized


def test_r3_quality_assessment_separates_transport_from_research_usefulness() -> None:
    path = (
        ROOT
        / "configs/releases/fin_ia_0_1_3_s1_08_tencent_wsa_exact_copy_ak_sk_r3_quality_assessment_v1_0.json"
    )
    assessment = json.loads(path.read_text(encoding="utf-8"))
    body = dict(assessment)
    digest = body.pop("assessment_digest")
    assert digest == canonical_digest(body)
    assert assessment["authentication_and_transport_assessment"][
        "standard_ak_sk_authentication"
    ] == "pass"
    assert assessment["research_quality_assessment"][
        "research_relevant_locator_count"
    ] == 0
    assert assessment["stage_and_promotion_boundary"][
        "candidate_locator_quality_passed"
    ] is False
    assert assessment["stage_and_promotion_boundary"][
        "sourcehunter_integration_allowed"
    ] is False
