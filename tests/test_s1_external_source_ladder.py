from __future__ import annotations

from copy import deepcopy
import json

import pytest

from retrieval.external_source_ladder import (
    EXTERNAL_SOURCE_LADDER_PLAN_SCHEMA_VERSION,
    ExternalSourceLadderError,
    build_external_fetch_shortlist,
    canonicalize_external_url,
    compile_safe_provider_request,
    normalize_tencent_search_response,
    validate_external_source_ladder_plan,
)
from retrieval.query_plan import canonical_digest


PROPOSITIONS = [
    "DELL-PROP-PRICE-CONFIGURATION",
    "DELL-PROP-UNIT-VOLUME",
    "DELL-PROP-PVM-BRIDGE",
    "DELL-PROP-CUSTOMER-DEMAND",
    "DELL-PROP-SUPPLY-CHAIN",
    "DELL-PROP-VALUE-POOL",
    "DELL-PROP-COUNTEREVIDENCE-WWC",
]


def _plan() -> dict:
    units = []
    for index, proposition in enumerate(PROPOSITIONS, start=1):
        units.append(
            {
                "query_unit_id": f"Q::{index}",
                "proposition_id": proposition,
                "tier_id": "official_subject_regulator_customer_supplier",
                "query": f"Dell AI server {proposition}",
                "site": "dell.com",
                "expected_output_ids": [f"OUT::{index}"],
                "relationship_directions": ["issuer_to_research_subject"],
                "speaker_or_source_targets": ["Dell Technologies"],
            }
        )
    body = {
        "schema_version": EXTERNAL_SOURCE_LADDER_PLAN_SCHEMA_VERSION,
        "plan_id": "PLAN::TEST",
        "status": "approved_exact_once_external_locator_and_original_capture_plan",
        "case_key": "DELL",
        "research_as_of": "2026-08-06",
        "execution_budget": {
            "provider_call_ceiling": 7,
            "original_fetch_ceiling": 7,
            "original_fetch_ceiling_per_query": 1,
            "original_fetch_ceiling_per_domain": 7,
            "result_ceiling_per_call": 10,
            "retry_ceiling": 0,
            "model_call_ceiling": 0,
        },
        "token_budget_basis": {
            "model_tokens": 0,
            "node_purpose": "Locate original public sources.",
            "input_scale_basis": "Seven proposition queries.",
            "required_outputs": ["safe requests", "locator receipts"],
            "materiality_and_quality_risk": "A wrong locator can contaminate research.",
            "comparable_run_evidence": "Historical provider diagnostic.",
            "stop_and_truncation_behavior": "Exact once, no retry.",
            "cost_and_latency_are_secondary_constraints": True,
        },
        "query_units": units,
        "source_domain_registry": [
            {
                "host": "dell.com",
                "speaker_entity": "Dell Technologies Inc.",
                "speaker_ticker": "DELL",
                "source_class": "issuer_regulator_or_government_primary",
                "source_role": "issuer_primary",
                "relationship_directions": ["issuer_to_research_subject"],
            }
        ],
    }
    return {**body, "plan_digest": canonical_digest(body)}


def test_plan_and_safe_request_never_persist_credentials() -> None:
    plan = validate_external_source_ladder_plan(_plan())
    request = compile_safe_provider_request(plan["query_units"][0])

    assert request["request_body"] == {
        "Query": "Dell AI server DELL-PROP-PRICE-CONFIGURATION",
        "Site": "dell.com",
    }
    assert request["credential_fields_present"] is False
    assert "secret" not in json.dumps(request).casefold()


def test_url_canonicalization_removes_tracking_and_rejects_private_hosts() -> None:
    assert canonicalize_external_url(
        "https://WWW.DELL.COM/page?utm_source=x&id=7#fragment"
    ) == "https://www.dell.com/page?id=7"
    with pytest.raises(
        ExternalSourceLadderError,
        match="external_ladder_locator_host_forbidden",
    ):
        canonicalize_external_url("https://127.0.0.1/internal")


def test_provider_normalization_retains_locator_only_boundary() -> None:
    plan = _plan()
    unit = plan["query_units"][0]
    request = compile_safe_provider_request(unit)
    result = normalize_tencent_search_response(
        raw_payload={
            "Response": {
                "Pages": [
                    json.dumps(
                        {
                            "url": "https://www.dell.com/en-us/shop/server.aspx?utm_source=x",
                            "title": "Dell server catalog",
                            "date": "2026-07-01",
                            "passage": "AI server configurations",
                            "score": 0.8,
                        }
                    )
                ],
                "Version": "standard",
                "RequestId": "REQ-1",
            }
        },
        query_unit=unit,
        safe_request=request,
    )

    assert result["locators"][0]["canonical_url"].startswith(
        "https://www.dell.com/"
    )
    assert result["locators"][0]["candidate_not_evidence"] is True
    assert result["evidence_promotion_allowed"] is False


def test_shortlist_is_fair_and_rejects_unreviewed_domain() -> None:
    plan = _plan()
    bundles = []
    for unit in plan["query_units"]:
        request = compile_safe_provider_request(unit)
        bundles.append(
            normalize_tencent_search_response(
                raw_payload={
                    "Pages": [
                        {
                            "url": f"https://www.dell.com/{unit['query_unit_id'].split('::')[-1]}",
                            "title": "Dell original",
                            "passage": "Relevant original source",
                        },
                        {
                            "url": "https://unreviewed.example/story",
                            "title": "Unknown source",
                        },
                    ]
                },
                query_unit=unit,
                safe_request=request,
            )
        )

    shortlist = build_external_fetch_shortlist(plan=plan, locator_bundles=bundles)

    assert shortlist["summary"]["selected_original_fetch_count"] == 7
    assert shortlist["summary"]["selected_proposition_count"] == 7
    assert all(
        row["source_domain"].endswith("dell.com") for row in shortlist["selected"]
    )
    assert any(
        row["reason"] == "source_domain_not_in_reviewed_registry"
        for row in shortlist["rejected"]
    )


def test_plan_digest_detects_mutation() -> None:
    plan = _plan()
    mutated = deepcopy(plan)
    mutated["execution_budget"]["retry_ceiling"] = 1
    with pytest.raises(
        ExternalSourceLadderError,
        match="external_ladder_plan_digest_invalid",
    ):
        validate_external_source_ladder_plan(mutated)
