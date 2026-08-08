from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import pytest

from sec_agent.s1_08_candidate_generation_runtime import load_source_catalog
from sec_agent.s1_08_provider_wire_projection import (
    PROVIDER_IDS,
    S108ProviderWireProjectionError,
    compile_execution_units,
    compile_fair_comparator_plans,
    compile_wire_request,
    compile_wire_requests,
    load_wire_projection_policy,
    validate_wire_request,
    weighted_query_units,
)
from sec_agent.s1_08_search_intent_compiler import (
    GOLD_TOKEN_PREFIXES,
    compile_search_intents,
    load_search_intent_policy,
)


ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = (
    ROOT
    / "configs/runtime/fin_ia_0_1_3_s1_08_current_source_catalog_relationship_budget_policy_v3_0.json"
)
INTENT_POLICY_PATH = (
    ROOT
    / "configs/runtime/fin_ia_0_1_3_s1_08_relationship_aware_search_intent_policy_v1_0.json"
)
WIRE_POLICY_PATH = (
    ROOT
    / "configs/runtime/fin_ia_0_1_3_s1_08_domestic_provider_wire_projection_policy_v1_0.json"
)
VISIBLE_PATH = (
    ROOT
    / "eval_sets/fin_0_1_3_same_evidence_v1/model_visible/shared_benchmark_evidence_pack_v1.json"
)
PROOF_PATH = (
    ROOT
    / "configs/releases/fin_ia_0_1_3_s1_08_domestic_provider_wire_projection_and_fair_comparator_zero_call_proof_v1_0.json"
)


def _inputs():
    catalog = load_source_catalog(CATALOG_PATH)
    intent_policy = load_search_intent_policy(INTENT_POLICY_PATH)
    wire_policy = load_wire_projection_policy(WIRE_POLICY_PATH)
    visible = json.loads(VISIBLE_PATH.read_text(encoding="utf-8"))
    objectives = {
        str(row["case_key"]): str(row["research_objective"])
        for row in visible["cases"]
    }
    intents = compile_search_intents(
        catalog=catalog,
        policy=intent_policy,
        research_objectives=objectives,
    )
    return intents, wire_policy


def _requests():
    intents, policy = _inputs()
    return intents, policy, compile_wire_requests(intents=intents, policy=policy)


def test_four_provider_profiles_compile_separate_36_and_24_plans() -> None:
    _intents, policy, requests = _requests()

    assert len(requests) == 240
    assert len({(row.provider_id, row.intent_id) for row in requests}) == 240
    assert len({row.wire_digest for row in requests}) == 240
    for provider_id in PROVIDER_IDS:
        rows = [row for row in requests if row.provider_id == provider_id]
        assert len(rows) == 60
        assert sum(row.route_class == "precise_official_domain" for row in rows) == 36
        assert sum(row.route_class == "semantic_open_web" for row in rows) == 24
        assert len({row.compact_query_text for row in rows}) == 46
        assert len({row.request_payload_digest for row in rows}) == 46
        assert all(row.send_authorized is False for row in rows)

    execution_units = compile_execution_units(requests=requests)
    assert len(execution_units) == 184
    for provider_id in PROVIDER_IDS:
        rows = [row for row in execution_units if row.provider_id == provider_id]
        assert len(rows) == 46
        assert sum(row.route_class == "precise_official_domain" for row in rows) == 22
        assert sum(row.route_class == "semantic_open_web" for row in rows) == 24
        assert all(row.send_authorized is False for row in rows)
        assert all(len(row.consumer_intent_ids) >= 1 for row in rows)

    plans = compile_fair_comparator_plans(requests=requests, policy=policy)
    assert plans["semantic_query_parity"] == {
        "intent_count": 24,
        "provider_count": 4,
        "all_queries_identical_per_intent": True,
        "digest": "b3e71b82c76daadf590de29566a5327a3ad553d815e31204f57b7131536c905e",
    }
    assert plans["automatic_combined_live_execution_allowed"] is False
    assert all(
        value["combined_execution_unit_count"] == 46
        for value in plans["providers"].values()
    )
    assert [
        plans[key]
        for key in (
            "provider_calls",
            "network_calls",
            "model_calls",
            "document_fetches",
            "evidence_promotions",
        )
    ] == [0, 0, 0, 0, 0]


def test_baidu_projection_converts_zero_of_60_verbatim_fit_to_60_of_60() -> None:
    intents, _policy, requests = _requests()
    assert sum(weighted_query_units(row.query_text) <= 72 for row in intents) == 0

    baidu = [
        row for row in requests if row.provider_id == "baidu_qianfan_web_search_v2"
    ]
    assert len(baidu) == 60
    assert all(row.compact_query_units <= 72 for row in baidu)
    assert min(row.compact_query_units for row in baidu) == 37
    assert max(row.compact_query_units for row in baidu) == 66
    assert all(
        row.request_body["messages"][0]["content"] == row.compact_query_text
        for row in baidu
    )


def test_compact_query_keeps_owner_period_direction_source_and_neutral_context() -> None:
    _intents, _policy, requests = _requests()
    lookup = {(row.provider_id, row.intent_id): row for row in requests}

    demand = lookup[
        (
            "baidu_qianfan_web_search_v2",
            "search_intent::NVDA::customer_demand_and_deployment_validation::MSFT::en::semantic_open_web",
        )
    ]
    assert demand.compact_query_text == (
        "MSFT Q3 FY2026 Azure AI capex datacenter capacity earnings NVDA"
    )
    supply = lookup[
        (
            "baidu_qianfan_web_search_v2",
            "search_intent::MU::supply_chain_capacity_and_counterevidence::TSMC::zh::semantic_open_web",
        )
    ]
    assert supply.compact_query_text == (
        "台积电 Q2 2026 CoWoS先进封装 产能 业绩 美光"
    )
    assert "客户" not in demand.compact_query_text
    assert "供应商" not in supply.compact_query_text


def test_semantic_lane_has_literal_query_parity_and_no_hidden_filters() -> None:
    _intents, _policy, requests = _requests()
    semantic = [row for row in requests if row.route_class == "semantic_open_web"]
    by_intent: dict[str, list] = {}
    for row in semantic:
        by_intent.setdefault(row.intent_id, []).append(row)
    assert len(by_intent) == 24
    assert all(len({row.compact_query_text for row in rows}) == 1 for rows in by_intent.values())
    assert all(row.structured_filter_mode in {"none", "schema_capture_required"} for row in semantic)
    for row in semantic:
        body = json.dumps(row.request_body, ensure_ascii=False)
        assert "includeDomains" not in body
        assert "search_filter" not in body
        assert "FromTime" not in body
        assert "ToTime" not in body


def test_exact_payload_coalescing_is_explicit_and_never_crosses_route() -> None:
    _intents, _policy, requests = _requests()
    units = compile_execution_units(requests=requests)
    shared = [row for row in units if len(row.consumer_intent_ids) > 1]
    assert shared
    assert all(row.route_class == "precise_official_domain" for row in shared)
    assert all(
        len(row.consumer_intent_ids) == len(row.consumer_intent_digests)
        for row in shared
    )
    msft = next(
        row
        for row in shared
        if row.provider_id == "baidu_qianfan_web_search_v2"
        and row.compact_query_text
        == "MSFT Q3 FY2026 Azure AI capex datacenter capacity earnings"
    )
    assert msft.consumer_intent_ids == (
        "search_intent::DELL::customer_demand_and_deployment_validation::MSFT::en::precise_official_domain",
        "search_intent::MU::customer_demand_and_deployment_validation::MSFT::en::precise_official_domain",
        "search_intent::NVDA::customer_demand_and_deployment_validation::MSFT::en::precise_official_domain",
    )


def test_precise_lane_uses_only_declared_provider_native_filters() -> None:
    _intents, _policy, requests = _requests()
    precise = [
        row for row in requests if row.route_class == "precise_official_domain"
    ]
    tencent = next(
        row
        for row in precise
        if row.provider_id == "tencent_wsa_searchpro_standard"
        and row.evidence_slot_id == "regulatory_risk_and_financial_reconciliation"
        and row.case_key == "DELL"
        and row.language == "en"
    )
    assert tencent.request_body["Site"] == "data.sec.gov"
    assert set(tencent.request_body) == {"Query", "Site", "FromTime", "ToTime"}
    assert "Mode" not in tencent.request_body
    assert "Cnt" not in tencent.request_body

    baidu = next(
        row
        for row in precise
        if row.provider_id == "baidu_qianfan_web_search_v2"
        and row.case_key == "DELL"
        and row.evidence_slot_id == "issuer_results_and_management_commentary"
        and row.language == "en"
    )
    assert baidu.request_body["search_filter"] == {
        "match": {
            "site": ["data.sec.gov", "investors.delltechnologies.com"]
        },
        "range": {
            "page_time": {"gte": "2025-01-01", "lte": "2026-08-06"}
        },
    }

    firecrawl = next(
        row
        for row in precise
        if row.provider_id == "firecrawl_keyless_search"
        and row.case_key == "NVDA"
        and row.evidence_slot_id == "issuer_results_and_management_commentary"
        and row.language == "zh"
    )
    assert firecrawl.request_body["includeDomains"] == [
        "data.sec.gov",
        "investor.nvidia.com",
    ]
    assert "scrapeOptions" not in firecrawl.request_body


def test_alibaba_mcp_stays_schema_capture_required_and_not_admission_eligible() -> None:
    _intents, _policy, requests = _requests()
    rows = [
        row for row in requests if row.provider_id == "alibaba_bailian_web_search_mcp"
    ]
    assert len(rows) == 60
    assert all(row.structured_filter_mode == "schema_capture_required" for row in rows)
    assert all(row.admission_eligible_after_zero_call_proof is False for row in rows)
    assert all(set(row.request_body) == {"query", "count"} for row in rows)


def test_intent_and_wire_mutations_fail_closed() -> None:
    intents, policy, requests = _requests()
    intent = intents[0]
    with pytest.raises(
        S108ProviderWireProjectionError, match="s1_08_wire_intent_digest_invalid"
    ):
        compile_wire_request(
            intent=replace(intent, case_key="MU"),
            provider_id="baidu_qianfan_web_search_v2",
            policy=policy,
        )

    original = requests[0]
    with pytest.raises(
        S108ProviderWireProjectionError, match="s1_08_wire_request_drift"
    ):
        validate_wire_request(
            request=replace(original, compact_query_text="forged query"),
            intent=next(row for row in intents if row.intent_id == original.intent_id),
            policy=policy,
        )


def test_policy_limit_provider_and_atom_mutations_fail_closed(tmp_path: Path) -> None:
    intents, policy = _inputs()
    lowered = deepcopy(policy)
    lowered["common_comparator_query_unit_ceiling"] = 20
    with pytest.raises(
        S108ProviderWireProjectionError, match="s1_08_wire_common_query_limit_exceeded"
    ):
        compile_wire_requests(intents=intents, policy=lowered)

    with pytest.raises(
        S108ProviderWireProjectionError, match="s1_08_wire_provider_unknown"
    ):
        compile_wire_requests(intents=intents, policy=policy, provider_ids=["unknown"])

    missing_atom = deepcopy(policy)
    missing_atom["entity_slot_topic_terms"]["MSFT"][
        "customer_demand_and_deployment_validation"
    ]["zh"] = []
    path = tmp_path / "invalid_policy.json"
    path.write_text(json.dumps(missing_atom, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(
        S108ProviderWireProjectionError,
        match="s1_08_wire_policy_entity_topic_terms_invalid",
    ):
        load_wire_projection_policy(path)


def test_input_permutation_preserves_wire_and_plan_digests() -> None:
    intents, policy = _inputs()
    forward = compile_wire_requests(intents=intents, policy=policy)
    reverse = compile_wire_requests(intents=tuple(reversed(intents)), policy=policy)
    assert [row.as_dict() for row in forward] == [row.as_dict() for row in reverse]
    assert compile_fair_comparator_plans(
        requests=forward, policy=policy
    )["plan_digest"] == compile_fair_comparator_plans(
        requests=reverse, policy=policy
    )["plan_digest"]


def test_zero_call_wire_objects_do_not_leak_gold_locators_or_credentials() -> None:
    _intents, _policy, requests = _requests()
    serialized = json.dumps(
        [row.as_dict() for row in requests], ensure_ascii=False
    ).casefold()
    assert "authorization" not in serialized
    assert "secretkey" not in serialized
    assert "api_key" not in serialized
    assert "https://" in serialized  # endpoints and structured official domains are auditable
    for row in requests:
        query = row.compact_query_text.casefold()
        assert "http://" not in query
        assert "https://" not in query
        assert "www." not in query
        assert all(prefix.casefold() not in query for prefix in GOLD_TOKEN_PREFIXES)


def test_materialized_proof_is_digest_bound_and_claims_no_live_search() -> None:
    proof = json.loads(PROOF_PATH.read_text(encoding="utf-8"))
    assert proof["status"] == "zero_call_engineering_pass"
    assert proof["wire_requests"] == {
        "providers": 4,
        "requests": 240,
        "unique_wire_digests": 240,
        "unique_request_payload_digests": 184,
        "execution_units": 184,
        "execution_units_per_provider": 46,
        "precise_execution_units_per_provider": 22,
        "semantic_execution_units_per_provider": 24,
        "query_unit_range": [37, 66],
        "baidu_fit": [60, 60],
        "canonical_baidu_verbatim_fit": [0, 60],
    }
    assert proof["semantic_query_parity"]["all_queries_identical_per_intent"] is True
    assert proof["authority"] == {
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "document_fetches": 0,
        "evidence_promotions": 0,
        "live_comparator_authorized": False,
        "sourcehunter_integration_authorized": False,
    }
    assert proof["next"] == (
        "S1_08_DOMESTIC_PROVIDER_CREDENTIAL_READINESS_AND_"
        "FIRECRAWL_CONTROL_COMPARATOR_AUTHORITY_DECISION"
    )
