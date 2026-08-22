from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

from ingestion.official_source_capture import CAPTURE_SCHEMA_VERSION
from retrieval.external_source_ladder import (
    source_family_allowed_hosts,
    validate_external_source_ladder_plan,
)
from retrieval.query_plan import canonical_digest
from scripts.data_retrieval.run_dell_external_source_ladder import (
    PLAN,
    SUCCESSOR_SPEC,
    _candidate_proposals,
    _compile_original_capture_plan,
    _load_successor_context,
    _predecessor_original_capture_index,
    build_public_projection,
    compile_captured_originals,
    execute_locator_queries,
    execute_original_capture_successor,
    run_capture_replay,
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


def test_original_capture_plan_accepts_reviewed_www_alias() -> None:
    plan = _plan()
    locator = _locator(plan)

    source_plan = _compile_original_capture_plan(
        plan=plan,
        shortlist={"selected": [locator]},
    )

    assert source_plan["sources"][0]["allowed_hosts"] == [
        "dell.com",
        "www.dell.com",
    ]


def test_candidate_window_rejects_navigation_tail_and_keeps_material_block() -> None:
    unit = {
        "query_unit_id": "Q::PRICE",
        "proposition_id": "DELL-PROP-PRICE-CONFIGURATION",
        "tier_id": "product_procurement_channel_deployment",
        "query": "Dell PowerEdge AI server configuration price",
        "expected_output_ids": ["OUT::PRICE"],
    }
    relevant = (
        "Dell PowerEdge XE9680 AI server configuration lists eight GPU accelerators "
        "and a channel asking price."
    )
    navigation = (
        "Dell investor relations navigation news support servers privacy careers."
    )
    source_object = {
        "source_id": "PUBLIC::DELL::TEST",
        "source_object_digest": "a" * 64,
        "segments": [
            {
                "segment_id": "SEG::1",
                "text": relevant + "\n\n" + navigation,
            }
        ],
    }
    policies = {
        "DELL-PROP-PRICE-CONFIGURATION": {
            "scope_anchor_terms": ["dell", "poweredge"],
            "material_signal_terms": ["configuration", "gpu", "price"],
            "minimum_scope_anchor_hits": 1,
            "minimum_material_signal_hits": 2,
            "context_blocks_before": 0,
            "context_blocks_after": 0,
        }
    }

    proposals = _candidate_proposals(
        source_object=source_object,
        query_unit=unit,
        candidate_selection_policy=policies,
    )

    assert len(proposals) == 1
    assert proposals[0]["excerpt"] == relevant
    assert "investor relations navigation" not in proposals[0]["excerpt"]
    assert proposals[0]["selection_method"] == (
        "capture_bound_central_block_identity_and_material_signal_v1"
    )


def test_relationship_output_compiles_relationship_candidate_facets() -> None:
    unit = {
        "query_unit_id": "Q::SUPPLIER-RELATIONSHIP",
        "proposition_id": "DELL-PROP-SUPPLY-CHAIN",
        "tier_id": "official_subject_regulator_customer_supplier",
        "query": "NVIDIA Dell PowerEdge platform availability",
        "expected_output_ids": [
            "supplier_names_dell",
            "observable_platform_delivery_relationship",
        ],
    }
    source_object = {
        "source_id": "PUBLIC::NVDA::RELATIONSHIP",
        "source_object_digest": "2" * 64,
        "segments": [
            {
                "segment_id": "SEG::RELATIONSHIP",
                "text": (
                    "NVIDIA announced Dell PowerEdge AI-ready servers will be "
                    "available by year-end."
                ),
            }
        ],
    }
    policies = {
        "DELL-PROP-SUPPLY-CHAIN": {
            "scope_anchor_terms": ["gpu", "blackwell", "server", "poweredge"],
            "material_signal_terms": ["capacity", "supply", "allocation"],
            "minimum_scope_anchor_hits": 1,
            "minimum_material_signal_hits": 2,
            "context_blocks_before": 0,
            "context_blocks_after": 0,
        }
    }

    proposals = _candidate_proposals(
        source_object=source_object,
        query_unit=unit,
        candidate_selection_policy=policies,
    )

    assert len(proposals) == 1
    assert proposals[0]["material_signal_hits"] == ["available"]
    assert proposals[0]["selection_method"] == (
        "capture_bound_relationship_facets_and_material_signal_v1"
    )


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


def test_actual_r1_locator_replay_calls_provider_only_for_15_residual_queries(
    tmp_path: Path,
) -> None:
    plan, predecessor, _spec = _load_successor_context(SUCCESSOR_SPEC)
    calls: list[dict] = []

    def fake_provider(request_body, _timeout):
        calls.append(dict(request_body))
        return {
            "Response": {
                "Pages": [],
                "Version": "zero-call-fixture",
                "RequestId": f"FAKE-{len(calls):02d}",
            }
        }

    bundles, receipts = execute_locator_queries(
        plan=plan,
        attempt_root=tmp_path / "actual-r1-replay",
        provider_call=fake_provider,
        predecessor_private_result=predecessor,
    )

    assert len(bundles) == 43
    assert len(calls) == 15
    assert sum(
        row["status"] == "predecessor_locator_bundle_replayed" for row in receipts
    ) == 28
    assert sum(row["provider_call_count"] for row in receipts) == 15
    assert all(row["model_call_count"] == 0 for row in receipts)


def test_provider_parse_failure_keeps_raw_response_and_failure_captures(
    tmp_path: Path,
) -> None:
    plan = _plan()
    plan["query_units"] = [plan["query_units"][0]]
    plan["execution_budget"]["provider_call_ceiling"] = 1

    def malformed_provider(_request_body, _timeout):
        return {"Response": {"RequestId": "REQ-MALFORMED", "Version": "standard"}}

    _bundles, receipts = execute_locator_queries(
        plan=plan,
        attempt_root=tmp_path / "parse-failure",
        provider_call=malformed_provider,
    )

    receipt = receipts[0]
    assert receipt["status"] == "provider_locator_call_failed"
    assert receipt["raw_capture_kind"] == "provider_response"
    assert receipt["raw_capture_ref"] == receipt["provider_response_capture_ref"]
    assert receipt["provider_response_capture_sha256"]
    assert receipt["provider_failure_capture_ref"]
    assert receipt["provider_failure_capture_sha256"]
    assert Path(receipt["provider_response_capture_ref"]).name == "raw_response.json"
    assert Path(receipt["provider_failure_capture_ref"]).name == "provider_failure.json"


def test_actual_r1_same_family_redirect_capture_is_reused_without_network(
    tmp_path: Path,
    monkeypatch,
) -> None:
    plan, predecessor, spec = _load_successor_context(SUCCESSOR_SPEC)
    predecessor_plan = validate_external_source_ladder_plan(
        json.loads(
            Path(spec["predecessor_binding"]["plan_ref"]).read_text(encoding="utf-8")
        )
    )
    predecessor_index = _predecessor_original_capture_index(
        predecessor_plan=predecessor_plan,
        predecessor_private_result=predecessor,
    )
    selected = None
    for old in predecessor_index.values():
        capture_row = old["capture_row"]
        if capture_row.get("status") != "rejected_final_url":
            continue
        locator = dict(old["locator"])
        observed_host = str(locator["source_domain"])
        registry = next(
            row
            for row in plan["source_domain_registry"]
            if observed_host == row["host"]
            or observed_host.endswith("." + str(row["host"]))
        )
        response = json.loads(
            Path(capture_row["response_capture"]["object_ref"]).read_text(
                encoding="utf-8"
            )
        )
        final_host = str(urlsplit(response["final_url"]).hostname or "").lower()
        if final_host not in source_family_allowed_hosts(
            registry,
            observed_host=observed_host,
        ):
            continue
        selected = {
            **locator,
            "source_registry": dict(registry),
            "source_family_id": registry["source_family_id"],
        }
        break
    assert selected is not None

    def forbidden_network(*_args, **_kwargs):
        raise AssertionError("same-family immutable capture must not use network")

    monkeypatch.setattr(
        "scripts.data_retrieval.run_dell_external_source_ladder.capture_plan",
        forbidden_network,
    )
    result, receipt = execute_original_capture_successor(
        plan=plan,
        shortlist={"selected": [selected]},
        attempt_root=tmp_path / "same-family-reuse",
        predecessor_plan=predecessor_plan,
        predecessor_private_result=predecessor,
    )

    assert result["predecessor_captures_reused"] == 1
    assert result["fresh_network_routes"] == 0
    assert result["sources"][0]["status"] == "captured"
    assert result["sources"][0]["predecessor_capture_status"] == (
        "rejected_final_url"
    )
    assert receipt["summary"]["predecessor_capture_reused_count"] == 1


def test_capture_replay_reuses_immutable_originals_without_network(
    tmp_path: Path,
    monkeypatch,
) -> None:
    plan = _plan()
    plan_path = tmp_path / "effective_plan.json"
    plan_path.write_text(
        json.dumps(plan, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    locator = _locator(plan)
    shortlist = {"selected": [locator]}
    source_plan = _compile_original_capture_plan(plan=plan, shortlist=shortlist)
    route_id = source_plan["sources"][0]["route_id"]
    html = """
    <html><head><meta property="article:published_time" content="2026-04-15"></head>
    <body><form><div class="module_body">
    <div>Dell PowerEdge XE9680 AI server configuration includes GPU accelerators.</div>
    <div>Public product configuration supports memory networking and storage choices.</div>
    <div>{}</div>
    </div></form></body></html>
    """.format("Captured product context remains candidate-only. " * 30)
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
    response_path.write_text(
        json.dumps(response, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    response_sha = hashlib.sha256(response_path.read_bytes()).hexdigest()
    capture_result = {
        "sources": [
            {
                "route_id": route_id,
                "status": "captured",
                "failure_code": None,
                "content_type": "text/html",
                "response_capture": {
                    "object_ref": str(response_path),
                    "sha256": response_sha,
                },
            }
        ]
    }
    prior_compilation = compile_captured_originals(
        plan=plan,
        shortlist=shortlist,
        capture_result=capture_result,
    )
    predecessor_body = {
        "schema_version": "test_predecessor",
        "plan_binding": {
            "ref": str(plan_path),
            "sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest(),
            "plan_digest": plan["plan_digest"],
        },
        "fetch_shortlist": shortlist,
        "original_capture_result": capture_result,
        "original_compilation_result": prior_compilation,
    }
    predecessor = {
        **predecessor_body,
        "result_digest": canonical_digest(predecessor_body),
    }
    predecessor_path = tmp_path / "predecessor.json"
    predecessor_path.write_text(
        json.dumps(predecessor, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "scripts.data_retrieval.run_dell_external_source_ladder._require_clean",
        lambda: None,
    )
    monkeypatch.setattr(
        "scripts.data_retrieval.run_dell_external_source_ladder._head",
        lambda: "3" * 40,
    )

    public_output = tmp_path / "public.json"
    result = run_capture_replay(
        attempt_id="replay-r1",
        private_root=tmp_path / "private",
        public_output=public_output,
        predecessor_private_result_path=predecessor_path,
    )

    assert result["observed_counts"] == {
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "retry_count": 0,
        "candidate_evidence_promotions": 0,
    }
    assert result["original_summary"]["source_object_count"] == 1
    assert result["authority"]["candidate_decision_complete"] is False
    assert public_output.exists()
