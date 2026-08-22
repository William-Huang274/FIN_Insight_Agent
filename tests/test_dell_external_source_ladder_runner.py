from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

from ingestion.official_source_capture import CAPTURE_SCHEMA_VERSION
from retrieval.external_source_ladder import validate_external_source_ladder_plan
from retrieval.query_plan import canonical_digest
from scripts.data_retrieval.run_dell_external_source_ladder import (
    PLAN,
    _compile_original_capture_plan,
    build_public_projection,
    compile_captured_originals,
)


def _plan() -> dict:
    return validate_external_source_ladder_plan(
        json.loads(PLAN.read_text(encoding="utf-8"))
    )


def _locator(plan: dict) -> dict:
    unit = plan["query_units"][0]
    body = {
        "query_unit_id": unit["query_unit_id"],
        "proposition_id": unit["proposition_id"],
        "tier_id": unit["tier_id"],
        "expected_output_ids": unit["expected_output_ids"],
        "relationship_directions": unit["relationship_directions"],
        "provider_rank": 1,
        "canonical_url": "https://www.dell.com/en-us/shop/ai-server",
        "source_domain": "www.dell.com",
        "title": "Dell AI server configuration",
        "passage": "PowerEdge XE9680 configuration",
        "provider_date_telemetry": "2026-04-15",
        "provider_score": 0.9,
        "provider_result_is_locator_only": True,
        "candidate_not_evidence": True,
        "writer_citable": False,
        "numeric_authority": "none",
    }
    registry = next(
        row for row in plan["source_domain_registry"] if row["host"] == "dell.com"
    )
    return {
        **body,
        "locator_digest": canonical_digest(body),
        "source_registry": registry,
        "fetch_status": "approved_for_original_capture",
    }


def test_compile_captured_originals_keeps_material_candidate_only(tmp_path: Path) -> None:
    plan = _plan()
    locator = _locator(plan)
    shortlist = {"selected": [locator]}
    source_plan = _compile_original_capture_plan(plan=plan, shortlist=shortlist)
    route_id = source_plan["sources"][0]["route_id"]
    html = """
    <html><head><title>Dell AI server configuration</title>
    <meta property="article:published_time" content="2026-04-15T08:00:00Z">
    </head><body><article>
    <h1>PowerEdge XE9680 AI server configuration</h1>
    <p>PowerEdge XE9680 supports GPU, HBM, networking, storage and richer AI server configuration choices.</p>
    <p>Configuration choices vary by accelerator, networking, memory and storage and do not establish issuer average selling price.</p>
    <p>The public product catalog provides configuration taxonomy but a transaction price requires a captured quote.</p>
    <p>Additional product context keeps this original-source fixture sufficiently substantive for deterministic parsing.</p>
    <p>GPU HBM networking storage configuration evidence remains bound to Dell as the product speaker.</p>
    </article></body></html>
    """
    body = html.encode("utf-8")
    response = {
        "schema_version": CAPTURE_SCHEMA_VERSION,
        "capture_kind": "source_response",
        "case_key": "DELL",
        "route_id": route_id,
        "request_capture_ref": "sha256://request",
        "request_capture_digest": "a" * 64,
        "status_code": 200,
        "final_url": locator["canonical_url"],
        "headers": {"content-type": "text/html; charset=utf-8"},
        "redirect_chain": [],
        "body_base64": base64.b64encode(body).decode("ascii"),
        "body_sha256": hashlib.sha256(body).hexdigest(),
        "body_bytes": len(body),
        "capture_before_parse": True,
        "credential_cookie_authorization_present": False,
        "preflight_response_refs": [],
    }
    response_path = tmp_path / "response.json"
    response_path.write_text(json.dumps(response), encoding="utf-8")
    capture_result = {
        "sources": [
            {
                "route_id": route_id,
                "status": "captured",
                "failure_code": None,
                "content_type": "text/html",
                "response_capture": {
                    "object_ref": str(response_path),
                    "sha256": "b" * 64,
                },
            }
        ]
    }

    result = compile_captured_originals(
        plan=plan,
        shortlist=shortlist,
        capture_result=capture_result,
    )

    assert result["summary"]["source_object_count"] == 1
    assert result["summary"]["candidate_proposal_count"] >= 1
    assert result["candidate_proposals"][0]["candidate_not_evidence"] is True
    assert result["authority"]["evidence_promotion_allowed"] is False


def test_public_projection_never_claims_route_exhaustion() -> None:
    plan = _plan()
    locator = _locator(plan)
    provider_receipts = [
        {
            "query_unit_id": row["query_unit_id"],
            "proposition_id": row["proposition_id"],
            "tier_id": row["tier_id"],
            "status": "provider_locator_call_completed",
            "locator_count": 1,
            "provider_call_count": 1,
        }
        for row in plan["query_units"]
    ]
    result = build_public_projection(
        plan=plan,
        provider_receipts=provider_receipts,
        shortlist={
            "selected": [locator],
            "summary": {"selected_original_fetch_count": 1},
        },
        original_result=None,
        private_result_ref="private/result.json",
        private_result_sha256="a" * 64,
        prepared_from_commit="b" * 40,
        recorded_at="2026-08-22T00:00:00+00:00",
    )

    assert all(row["external_route_exhausted"] is False for row in result["propositions"])
    assert all(
        row["public_information_gap_eligible"] is False
        for row in result["propositions"]
    )
    assert result["authority"]["dynamic_single_unit_authorized"] is False
