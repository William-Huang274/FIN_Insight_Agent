from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.s1_08_tencent_wsa_candidate_diagnostic import PROMOTION_STATUS
from sec_agent.s1_08_tencent_wsa_query_only_replacement import (
    build_safe_request_capture,
    compile_query_only_request,
)


AUTHORITY_SCHEMA = (
    "fin_ia_0_1_3_s1_08_tencent_wsa_standard_tier_r4_authority_v1_0"
)
RESULT_SCHEMA = "fin_ia_0_1_3_s1_08_tencent_wsa_standard_tier_r4_result_v1_0"
CONTRACT_REF = "fin_0_1_3.S1_08.tencent_wsa_standard_tier_r4:v1"
RUN_SCOPE = "S1_08_PAID_BROAD_SEARCH_TENCENT_WSA_STANDARD_TIER_R4_DIAGNOSTIC"
PREDECESSOR_ATTEMPT_ID = "fin013-s1-08-tencent-wsa-exact-copy-ak-sk-r3"


class TencentWSAStandardTierR4Error(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def load_standard_tier_r4_authority(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    body = dict(payload)
    digest = body.pop("authority_digest", None)
    if (
        body.get("schema_version") != AUTHORITY_SCHEMA
        or body.get("contract_ref") != CONTRACT_REF
        or body.get("status") != "issued_unconsumed"
        or body.get("authorized_scope") != RUN_SCOPE
        or digest != canonical_digest(body)
    ):
        raise TencentWSAStandardTierR4Error(
            "tencent_wsa_standard_tier_r4_authority_identity_invalid"
        )
    if body.get("predecessor_attempt_id") != PREDECESSOR_ATTEMPT_ID:
        raise TencentWSAStandardTierR4Error(
            "tencent_wsa_standard_tier_r4_predecessor_invalid"
        )
    if body.get("changed_variable") != "provider_subscription_lite_to_standard":
        raise TencentWSAStandardTierR4Error(
            "tencent_wsa_standard_tier_r4_changed_variable_invalid"
        )
    if body.get("expected_provider_version") != "standard":
        raise TencentWSAStandardTierR4Error(
            "tencent_wsa_standard_tier_r4_expected_version_invalid"
        )
    execution = body.get("execution_contract") or {}
    if (
        execution.get("provider_call_ceiling") != 1
        or execution.get("network_call_ceiling") != 1
        or execution.get("retry_ceiling") != 0
        or execution.get("model_call_ceiling") != 0
        or execution.get("document_fetch_ceiling") != 0
        or execution.get("same_query_as_predecessor_required") is not True
        or execution.get("evidence_promotion_allowed") is not False
        or execution.get("production_capability_claim_allowed") is not False
        or execution.get("credentials_interactive_hidden_only") is not True
    ):
        raise TencentWSAStandardTierR4Error(
            "tencent_wsa_standard_tier_r4_authority_boundary_invalid"
        )
    compile_query_only_request(body.get("query") or {})
    return payload


def build_standard_tier_r4_terminal_result(
    *,
    admission_id: str,
    source_commit: str,
    status: str,
    terminal_code: str,
    request_capture: Mapping[str, Any],
    provider_projection: Mapping[str, Any] | None,
    network_call_count: int,
    elapsed_ms: int,
    sdk_version: str,
    failure: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if set((request_capture.get("request_body") or {}).keys()) != {"Query"}:
        raise TencentWSAStandardTierR4Error(
            "tencent_wsa_standard_tier_r4_terminal_request_not_exact"
        )
    if network_call_count not in {0, 1}:
        raise TencentWSAStandardTierR4Error(
            "tencent_wsa_standard_tier_r4_network_count_invalid"
        )
    body = {
        "schema_version": RESULT_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "admission_id": admission_id,
        "predecessor_attempt_id": PREDECESSOR_ATTEMPT_ID,
        "changed_variable": "provider_subscription_lite_to_standard",
        "expected_provider_version": "standard",
        "admission_consumed": bool(network_call_count),
        "source_commit": source_commit,
        "status": status,
        "terminal_code": terminal_code,
        "request_capture": dict(request_capture),
        "provider_projection": dict(provider_projection or {}),
        "failure": dict(failure or {}),
        "observed_counts": {
            "provider_calls": network_call_count,
            "network_calls": network_call_count,
            "retry_calls": 0,
            "model_calls": 0,
            "document_fetches": 0,
            "evidence_promotions": 0,
        },
        "elapsed_ms": int(elapsed_ms),
        "sdk": {"package": "tencentcloud-sdk-python", "version": sdk_version},
        "capability_boundary": {
            "promotion_status": PROMOTION_STATUS,
            "evidence_promotion_allowed": False,
            "writer_citable": False,
            "financial_fact_authority": False,
            "numeric_authority": "none",
            "production_capability_claim_allowed": False,
        },
    }
    return {**body, "result_digest": canonical_digest(body)}


__all__ = [
    "AUTHORITY_SCHEMA",
    "CONTRACT_REF",
    "PREDECESSOR_ATTEMPT_ID",
    "RESULT_SCHEMA",
    "RUN_SCOPE",
    "TencentWSAStandardTierR4Error",
    "build_safe_request_capture",
    "build_standard_tier_r4_terminal_result",
    "compile_query_only_request",
    "load_standard_tier_r4_authority",
]
