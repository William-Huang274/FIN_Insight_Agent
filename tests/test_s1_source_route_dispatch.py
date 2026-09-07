from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from retrieval.query_plan import canonical_digest
from retrieval.source_route_dispatch import (
    SOURCE_NON_DISCLOSURE_SCHEMA_VERSION,
    SOURCE_ROUTE_ATTEMPT_SCHEMA_VERSION,
    SourceRouteDispatchError,
    compile_product_projection_source_route_successor,
    compile_source_route_execution_truth,
    load_source_route_portfolio_policy,
)


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "configs/retrieval/fin_ia_0_1_3_s1_source_route_portfolio_policy_v1_0.json"


def _policy():
    return load_source_route_portfolio_policy(
        json.loads(POLICY.read_text(encoding="utf-8"))
    )


def _request(*, sources: list[str] | None = None) -> dict:
    return {
        "request_id": "REQ-1",
        "case_key": "DELL",
        "subject_ticker": "DELL",
        "research_as_of": "2026-08-06",
        "acceptable_sources": sources or ["10-Q"],
    }


def _plan(*, sources: list[str] | None = None, owner: str = "DELL") -> dict:
    return {
        "case_key": "DELL",
        "subject_ticker": "DELL",
        "research_as_of": "2026-08-06",
        "lanes": [
            {
                "lane_id": "dell__operating__reported",
                "slot_id": "operating_performance",
                "facet_id": "reported_results",
                "source_types": sources or ["10-Q"],
                "required_source_roles": [
                    "issuer_disclosure" if owner == "DELL" else "related_entity_context"
                ],
                "owner_queries": [
                    {
                        "evidence_owner_ticker": owner,
                        "relationship_direction": (
                            "subject_self_disclosure"
                            if owner == "DELL"
                            else "supplier_to_subject"
                        ),
                    }
                ],
            }
        ],
    }


def _compile(**kwargs):
    return compile_source_route_execution_truth(
        request=kwargs.pop("request", _request()),
        query_plan=kwargs.pop("query_plan", _plan()),
        policy=_policy(),
        **kwargs,
    )


def _attempt(requirement_id: str, *, route_id: str = "sec_edgar_official_primary", status: str = "terminal_no_eligible_source", count: int = 0) -> dict:
    body = {
        "schema_version": SOURCE_ROUTE_ATTEMPT_SCHEMA_VERSION,
        "attempt_id": "ATTEMPT-1",
        "route_id": route_id,
        "requirement_id": requirement_id,
        "status": status,
        "terminal": status.startswith("terminal_"),
        "eligible_source_count": count,
        "request_capture_digest": "a" * 64,
        "response_capture_digest": "b" * 64,
        "failure_class": None if status.startswith("terminal_") else status,
    }
    return {**body, "attempt_digest": canonical_digest(body)}


def _non_disclosure(requirement_id: str) -> dict:
    body = {
        "schema_version": SOURCE_NON_DISCLOSURE_SCHEMA_VERSION,
        "requirement_id": requirement_id,
        "adjudication_state": "confirmed_non_disclosure",
        "reviewed_source_capture_digests": ["b" * 64],
        "adjudicator_class": "deterministic_source_contract",
    }
    return {**body, "receipt_digest": canonical_digest(body)}


def _route(result: dict, route_id: str) -> dict:
    return next(
        row
        for row in result["requirements"][0]["source_routes"]
        if row["route_id"] == route_id
    )


def test_local_material_complete_does_not_trigger_external_supplement() -> None:
    result = _compile(
        candidate_coverage_state="complete",
        local_candidate_rows=[
            {"ticker": "DELL", "source_type": "10-Q", "compiled_object_id": "OBJ-1"}
        ],
    )

    assert result["supplement_route_required"] is False
    assert _route(result, "current_local_snapshot")["eligible_source_count"] == 1
    assert _route(result, "sec_edgar_official_primary")["execution_state"] == (
        "not_required_local_candidate_set_complete"
    )


def test_local_candidate_complete_still_schedules_material_research_gap() -> None:
    result = _compile(
        candidate_coverage_state="complete",
        research_sufficiency_state="material_gap",
        local_candidate_rows=[
            {"ticker": "DELL", "source_type": "10-Q", "compiled_object_id": "OBJ-1"}
        ],
    )

    assert result["supplement_route_required"] is True
    assert result["supplement_trigger_reasons"] == ["material_research_gap"]
    assert result["research_sufficiency_state"] == "material_gap"
    assert _route(result, "sec_edgar_official_primary")["execution_state"] == (
        "available_not_executed"
    )


def test_research_sufficiency_cannot_be_an_untyped_boolean() -> None:
    with pytest.raises(
        SourceRouteDispatchError,
        match="source_route_research_sufficiency_state_invalid",
    ):
        _compile(
            candidate_coverage_state="complete",
            research_sufficiency_state="true",
        )


def test_direct_snapshot_does_not_mislabel_unevaluated_coverage_as_complete() -> None:
    result = _compile(
        local_candidate_rows=[
            {"ticker": "DELL", "source_type": "10-Q", "compiled_object_id": "OBJ-1"}
        ]
    )

    assert result["candidate_coverage_state"] == "not_evaluated"
    assert _route(result, "sec_edgar_official_primary")["execution_state"] == (
        "not_scheduled_candidate_coverage_not_evaluated"
    )

def test_candidate_coverage_gap_requires_unexecuted_official_route() -> None:
    result = _compile(candidate_coverage_state="incomplete")

    sec = _route(result, "sec_edgar_official_primary")
    assert sec["execution_state"] == "available_not_executed"
    assert sec["supplement_required_for_current_gap"] is True
    assert result["summary"]["official_or_external_supplement_route_exhausted"] is False
    assert result["summary"]["public_information_gap_authority"] is False


def test_registered_dell_transcript_capture_is_terminal_for_exact_route_only() -> None:
    result = _compile(
        request=_request(sources=["EARNINGS_CALL_TRANSCRIPT"]),
        query_plan=_plan(sources=["EARNINGS_CALL_TRANSCRIPT"]),
        candidate_coverage_state="incomplete",
        registered_intake_routes=[
            {
                "route_id": "DELL_Q1_FY2027_EARNINGS_CALL_TRANSCRIPT",
                "case_key": "DELL",
                "document_type": "earnings_call_transcript",
            }
        ],
        intake_attempts=[
            {
                "attempt_id": "UPLOAD-1",
                "route_id": "DELL_Q1_FY2027_EARNINGS_CALL_TRANSCRIPT",
                "status": "captured_ready_for_parse",
                "raw_object_sha256": "c" * 64,
            }
        ],
    )

    exact = _route(result, "registered_official_document_intake")
    assert exact["execution_state"] == "executed_exact_official_source_captured"
    assert exact["terminal_for_gap_evaluation"] is True
    assert exact["capture_digests"] == ["c" * 64]
    assert _route(result, "issuer_ir_feed_or_sitemap")["execution_state"] == (
        "not_executed_not_configured"
    )
    assert result["summary"]["official_or_external_supplement_route_exhausted"] is False


def test_unregistered_transcript_route_fails_closed() -> None:
    result = _compile(
        request=_request(sources=["EARNINGS_CALL_TRANSCRIPT"]),
        query_plan=_plan(sources=["EARNINGS_CALL_TRANSCRIPT"]),
        candidate_coverage_state="incomplete",
    )

    exact = _route(result, "registered_official_document_intake")
    assert exact["execution_state"] == "not_executed_no_registered_exact_route"
    assert exact["terminal_for_gap_evaluation"] is False


def test_transport_failure_cannot_become_exhaustion() -> None:
    first = _compile(candidate_coverage_state="incomplete")
    requirement_id = first["requirements"][0]["requirement_id"]
    attempt = _attempt(requirement_id, status="transport_failure")
    attempt["request_capture_digest"] = ""
    attempt["response_capture_digest"] = ""
    body = dict(attempt)
    body.pop("attempt_digest")
    attempt["attempt_digest"] = canonical_digest(body)

    result = _compile(
        candidate_coverage_state="incomplete",
        route_attempt_receipts=[attempt],
    )

    sec = _route(result, "sec_edgar_official_primary")
    assert sec["execution_state"] == "executed_nonterminal_or_non_authoritative"
    assert sec["route_exhausted"] is False
    assert result["summary"]["official_or_external_supplement_route_exhausted"] is False


def test_capture_bound_no_result_still_needs_non_disclosure_adjudication() -> None:
    first = _compile(candidate_coverage_state="incomplete")
    requirement_id = first["requirements"][0]["requirement_id"]
    attempt = _attempt(requirement_id)

    route_only = _compile(
        candidate_coverage_state="incomplete",
        route_attempt_receipts=[attempt],
    )
    requirement = route_only["requirements"][0]
    assert requirement["required_production_supplement_routes_terminal"] is True
    assert requirement["public_information_gap_eligible"] is False

    adjudicated = _compile(
        candidate_coverage_state="incomplete",
        route_attempt_receipts=[attempt],
        non_disclosure_receipts=[_non_disclosure(requirement_id)],
    )
    assert adjudicated["requirements"][0]["public_information_gap_eligible"] is True
    assert adjudicated["summary"]["all_requirements_public_information_gap_eligible"] is True
    assert adjudicated["summary"]["public_information_gap_authority"] is False


def test_diagnostic_route_cannot_claim_exhaustion_even_with_terminal_receipt() -> None:
    result = _compile(candidate_coverage_state="incomplete")
    requirement_id = result["requirements"][0]["requirement_id"]
    diagnostic_attempt = _attempt(
        requirement_id,
        route_id="broad_web_discovery_diagnostic",
    )

    replay = _compile(
        candidate_coverage_state="incomplete",
        route_attempt_receipts=[diagnostic_attempt],
    )
    route = _route(replay, "broad_web_discovery_diagnostic")
    assert route["execution_state"] == "executed_nonterminal_or_non_authoritative"
    assert route["terminal_for_gap_evaluation"] is False


def test_cross_case_registered_route_mutation_fails_closed() -> None:
    result = _compile(
        request=_request(sources=["EARNINGS_CALL_TRANSCRIPT"]),
        query_plan=_plan(sources=["EARNINGS_CALL_TRANSCRIPT"]),
        candidate_coverage_state="incomplete",
        registered_intake_routes=[
            {
                "route_id": "TSM_Q2_2026_EARNINGS_CALL_TRANSCRIPT",
                "case_key": "TSM",
                "document_type": "earnings_call_transcript",
            }
        ],
    )
    assert _route(result, "registered_official_document_intake")[
        "execution_state"
    ] == "not_executed_no_registered_exact_route"


def test_related_owner_uses_its_official_route_not_research_case_key() -> None:
    plan = _plan(sources=["EARNINGS_CALL_TRANSCRIPT"], owner="TSM")
    result = _compile(
        request={
            **_request(sources=["EARNINGS_CALL_TRANSCRIPT"]),
            "target_entities": ["TSM"],
        },
        query_plan=plan,
        candidate_coverage_state="incomplete",
        registered_intake_routes=[
            {
                "route_id": "TSM_Q2_2026_EARNINGS_CALL_TRANSCRIPT",
                "case_key": "TSM",
                "document_type": "earnings_call_transcript",
            }
        ],
        intake_attempts=[
            {
                "attempt_id": "TSM-CAPTURE-1",
                "route_id": "TSM_Q2_2026_EARNINGS_CALL_TRANSCRIPT",
                "status": "captured_ready_for_parse",
                "raw_object_sha256": "d" * 64,
            }
        ],
    )

    exact = _route(result, "registered_official_document_intake")
    assert result["requirements"][0]["evidence_owner_ticker"] == "TSM"
    assert exact["execution_state"] == "executed_exact_official_source_captured"
    assert exact["capture_digests"] == ["d" * 64]


def test_query_plan_identity_mutation_fails_closed() -> None:
    plan = deepcopy(_plan())
    plan["case_key"] = "MU"
    with pytest.raises(SourceRouteDispatchError, match="source_route_query_plan_identity_mismatch"):
        _compile(query_plan=plan)


def test_product_projection_successor_uses_material_receipts_and_deduplicates_candidates() -> None:
    hybrid = {
        "candidate_decision_seed": [
            {
                "source_record_id": "SRC-1",
                "evidence_owner_ticker": "DELL",
                "source_type": "10-Q",
            }
        ],
        "material_evidence": {
            "selection": {
                "requirement_receipts": [
                    {"requirement_id": "REQ-MAT-1", "complete": False}
                ]
            }
        },
    }
    product = {
        "schema_version": "fin_ia_controlled_research_plan_execution_projection_v1_1",
        "case_key": "DELL",
        "summary": {"evidence_request_count": 1},
        "request_results": [
            {
                "request": _request(),
                "query_plan": _plan(),
                "lanes": [
                    {
                        "candidates": [
                            {
                                "source_record_id": "SRC-1",
                                "evidence_owner_ticker": "DELL",
                                "source_type": "10-Q",
                            }
                        ]
                    }
                ],
                "hybrid_object_retrieval": hybrid,
                "projection_digest": "historical_base_projection_digest",
            }
        ],
    }

    result = compile_product_projection_source_route_successor(
        product_projection=product,
        policy=_policy(),
    )

    truth = result["request_results"][0]["source_route_execution_truth"]
    assert truth["candidate_coverage_state"] == "incomplete"
    assert truth["requirements"][0]["local_candidate_count"] == 1
    assert result["summary"]["source_route_execution"] == {
        "request_count": 1,
        "candidate_coverage_state_counts": {"incomplete": 1},
        "supplement_route_required_request_count": 1,
        "official_or_external_supplement_route_exhausted_request_count": 0,
        "public_information_gap_eligible_request_count": 0,
        "route_execution_state_counts": {
            "available_not_executed": 1,
            "executed_local_snapshot": 1,
            "not_executed_diagnostic_only": 1,
        },
        "network_calls": 0,
        "model_calls": 0,
        "vector_calls": 0,
    }
    body = dict(result)
    digest = body.pop("projection_digest")
    assert digest == canonical_digest(body)
