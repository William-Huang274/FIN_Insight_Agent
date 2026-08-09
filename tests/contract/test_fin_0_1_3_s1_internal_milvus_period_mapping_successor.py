from __future__ import annotations

from pathlib import Path
import json
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_internal_query_facet_integration import (  # noqa: E402
    compile_internal_query_facet_requests,
    load_internal_query_facet_policy,
    validate_internal_route_request,
)


POLICY_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s1_internal_"
    "query_facet_integration_policy_v1_2.json"
)
SOURCE_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_08_"
    "unified_query_facet_zero_call_proof_v1_0.json"
)


def _compiled():
    policy = load_internal_query_facet_policy(POLICY_PATH)
    source = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    bundles, requests = compile_internal_query_facet_requests(
        query_facet_proof=source,
        policy=policy,
    )
    return policy, bundles, requests


def test_milvus_fiscal_year_filter_uses_reporting_authority() -> None:
    policy, bundles, requests = _compiled()
    dense = [item for item in requests if item.route_id == "internal_milvus_dense"]
    assert len(dense) == 18
    assert all(
        item.typed_filters["years"]
        == item.typed_filters["reporting_fiscal_years"]
        for item in dense
    )
    nvda = next(
        item
        for item in dense
        if item.case_key == "NVDA"
        and item.evidence_owner_ticker == "NVDA"
        and item.evidence_slot_id == "issuer_results_and_management_commentary"
    )
    assert nvda.typed_filters["years"] == [2027]
    assert nvda.typed_filters["index_filing_calendar_years"] == [2026]
    bundle_map = {bundle.bundle_id: bundle for bundle in bundles}
    for item in dense:
        validate_internal_route_request(item, bundles=bundle_map, policy=policy)


def test_sparse_event_index_period_mapping_is_unchanged() -> None:
    _, _, requests = _compiled()
    nvda_bm25 = next(
        item
        for item in requests
        if item.route_id == "internal_bm25"
        and item.case_key == "NVDA"
        and item.evidence_owner_ticker == "NVDA"
        and item.evidence_slot_id == "issuer_results_and_management_commentary"
    )
    assert nvda_bm25.typed_filters["reporting_fiscal_years"] == [2027]
    assert nvda_bm25.typed_filters["index_filing_calendar_years"] == [2026]
