from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.workbench.backend.api.v1.research_retrieval import (
    build_research_retrieval_router,
)
from apps.workbench.backend.application.research_retrieval_service import (
    ResearchRetrievalPrincipal,
    ResearchRetrievalService,
    ResearchRetrievalServiceError,
)


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _request() -> dict:
    return _read(
        "configs/research/evals/"
        "fin_ia_0_1_3_s3_dell_material_scope_canary_input_v1_2.json"
    )["evidence_requests"][0]


class _HybridRuntime:
    def __init__(self) -> None:
        self.calls = []

    def retrieve_many(self, requests, **kwargs):
        self.calls.append((tuple(requests), dict(kwargs)))
        return tuple(
            {
                "request_id": request.request_id,
                "summary": {
                    "selected_count": 1,
                    "material_scope_ready": False,
                    "material_set_complete": False,
                },
                "candidate_decision_seed": [
                    {
                        "compiled_object_id": f"OBJ::{request.request_id}",
                    }
                ],
            }
            for request in requests
        )


def _service(tmp_path: Path, hybrid: _HybridRuntime) -> ResearchRetrievalService:
    return ResearchRetrievalService(
        snapshot=_read(
            "configs/runtime/"
            "fin_ia_0_1_3_current_retrieval_snapshot_v1_0.json"
        ),
        kernel=_read(
            "configs/retrieval/"
            "fin_ia_0_1_3_s1_financial_research_kernel_v1_3.json"
        ),
        route_policy=_read(
            "configs/retrieval/"
            "fin_ia_0_1_3_s1c_query_object_fact_route_policy_v1_3.json"
        ),
        hybrid_candidate_runtime=hybrid,
        material_scope_policy=_read(
            "configs/research/"
            "fin_ia_0_1_3_s3_material_scope_policy_v1_0.json"
        ),
        material_runtime_policy=_read(
            "configs/retrieval/"
            "fin_ia_0_1_3_s1_product_material_evidence_runtime_policy_v1_1.json"
        ),
        financial_intent_ontology=_read(
            "configs/retrieval/"
            "fin_ia_0_1_3_s1_financial_intent_ontology_v1_3.json"
        ),
        retrieval_need_policy=_read(
            "configs/retrieval/"
            "fin_ia_0_1_3_s1_vs5_retrieval_need_compiler_policy_v1_2.json"
        ),
        company_financial_fact_mart_path=tmp_path / "missing.sqlite",
    )


def _successor_service(
    tmp_path: Path,
    hybrid: _HybridRuntime,
) -> ResearchRetrievalService:
    return ResearchRetrievalService(
        snapshot=_read(
            "configs/runtime/"
            "fin_ia_0_1_3_current_retrieval_snapshot_v1_0.json"
        ),
        kernel=_read(
            "configs/retrieval/"
            "fin_ia_0_1_3_s1_financial_research_kernel_v1_4.json"
        ),
        route_policy=_read(
            "configs/retrieval/"
            "fin_ia_0_1_3_s1c_query_object_fact_route_policy_v1_4.json"
        ),
        hybrid_candidate_runtime=hybrid,
        company_financial_fact_mart_path=tmp_path / "missing.sqlite",
    )


def _public_successor_request() -> dict:
    return {
        "schema_version": "fin_ia_evidence_request_v1_0",
        "request_id": "REQ::DELL::INDUSTRY-PVM::CURRENT-RUNTIME",
        "cell_id": "CELL::value_capture",
        "requester_role": "fundamental_value_capture_analyst",
        "evidence_domain": "financial_research",
        "case_key": "DELL",
        "subject_ticker": "DELL",
        "research_as_of": "2026-08-06",
        "target_entities": ["ORG::13AAFF874F67F30C"],
        "requested_facet_ids": ["industry_pricing_mix_context"],
        "metric_intents": ["shipments", "average_selling_price"],
        "product_intents": ["AI server mix"],
        "period": {
            "start_date": "2025-01-01",
            "end_date": "2026-08-06",
            "fiscal_years": [],
        },
        "granularity": "source_bound_claim",
        "unit": "issuer_or_industry_reported",
        "acceptable_sources": ["PUBLIC_WEB"],
        "acceptable_proxy": True,
        "forbidden_proxy": ["industry fact treated as Dell fact"],
        "stop_condition": "reviewed evidence or typed gap",
        "clarification_policy": "return_typed_gap",
    }


def _principal() -> ResearchRetrievalPrincipal:
    return ResearchRetrievalPrincipal(
        mode="current",
        permissions=frozenset({"current_product:read"}),
    )


def test_direct_current_runtime_request_executes_hybrid_without_promotion(
    tmp_path: Path,
) -> None:
    hybrid = _HybridRuntime()
    service = _service(tmp_path, hybrid)

    result = service.execute_current_runtime_requests(
        "DELL", [_request()], _principal()
    )

    assert result["status"] == "current_runtime_request_batch_zero_call_executed"
    assert result["summary"]["request_count"] == 1
    assert result["summary"]["hybrid_selected_candidate_count"] == 1
    assert result["summary"]["hybrid_union_candidate_count"] == 1
    assert result["summary"]["network_calls"] == 0
    assert result["summary"]["model_calls"] == 0
    assert len(hybrid.calls) == 1
    request_result = result["request_results"][0]
    assert request_result["execution_mode"] == (
        "current_s2_snapshot_bm25_qwen_runtime"
    )
    assert request_result["hybrid_object_retrieval"]["request_id"] == (
        _request()["request_id"]
    )
    assert "Evidence or numeric authority" in result["known_boundary"]


def test_current_runtime_successor_lane_does_not_require_legacy_snapshot_lane(
    tmp_path: Path,
) -> None:
    hybrid = _HybridRuntime()
    service = _successor_service(tmp_path, hybrid)

    result = service.execute_current_runtime_requests(
        "DELL", [_public_successor_request()], _principal()
    )

    request_result = result["request_results"][0]
    assert request_result["lanes"][0]["snapshot_state"] in {
        "not_applicable_current_hybrid_successor_lane",
        "legacy_contract_not_applicable_to_current_hybrid_successor_lane",
    }
    assert not {
        "request_scoped_candidate_gap",
        "request_scoped_source_role_gap",
    }.intersection(
        str(row.get("gap_code") or "")
        for row in request_result["typed_gaps"]
    )
    assert result["summary"]["hybrid_selected_candidate_count"] == 1


def test_legacy_snapshot_endpoint_still_fails_closed_for_successor_lane(
    tmp_path: Path,
) -> None:
    service = _successor_service(tmp_path, _HybridRuntime())

    with pytest.raises(
        ResearchRetrievalServiceError,
        match="research_request_snapshot_lane_missing",
    ):
        service.execute_request(
            "DELL", _public_successor_request(), _principal()
        )


def test_direct_current_runtime_request_rejects_duplicate_identity(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path, _HybridRuntime())
    request = _request()

    with pytest.raises(
        ResearchRetrievalServiceError,
        match="current_runtime_request_id_duplicate",
    ):
        service.execute_current_runtime_requests(
            "DELL", [request, request], _principal()
        )


def test_direct_current_runtime_request_consumes_explicit_material_blueprint(
    tmp_path: Path,
) -> None:
    hybrid = _HybridRuntime()
    service = _service(tmp_path, hybrid)
    request = _request()
    request_id = request["request_id"]
    blueprint = {
        "material_requirements": [
            {
                "facet_id": request["requested_facet_ids"][0],
                "role": "direct",
                "metric_ids": list(request["metric_intents"]),
                "product_ids": list(request["product_intents"]),
                "target_entities": list(request["target_entities"]),
                "period_mode": "any",
                "fiscal_years": [],
                "minimum_candidates": 1,
                "coverage_mode": "collective_axes",
                "metric_coverage_mode": "retrieval_context_only",
                "product_coverage_mode": "all_of",
            }
        ]
    }

    result = service.execute_current_runtime_requests(
        "DELL",
        [request],
        _principal(),
        material_requirement_blueprints={request_id: blueprint},
    )

    assert result["material_scope"]["mode"] == (
        "explicit_program_blueprint_compiled"
    )
    assert result["material_scope"]["scope_compilation"]["request_ids"] == [
        request_id
    ]
    assert result["material_compilation_receipts"][0]["compiler_mode"] == (
        "explicit_research_blueprint"
    )
    runtime_inputs = hybrid.calls[0][1]["material_runtime_inputs"]
    assert runtime_inputs[request_id]["material_requirement_blueprint"] == blueprint


def test_direct_current_runtime_request_rejects_unknown_blueprint_request(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path, _HybridRuntime())

    with pytest.raises(
        ResearchRetrievalServiceError,
        match="current_runtime_material_blueprint_request_unknown",
    ):
        service.execute_current_runtime_requests(
            "DELL",
            [_request()],
            _principal(),
            material_requirement_blueprints={
                "REQ::UNKNOWN": {"material_requirements": []}
            },
        )


def test_current_runtime_request_endpoint_uses_same_product_surface(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path, _HybridRuntime())
    app = FastAPI()
    app.include_router(build_research_retrieval_router(service), prefix="/api/v1")

    response = TestClient(app).post(
        "/api/v1/research-cases/DELL/current-runtime-requests",
        json={"requests": [_request()]},
        headers={
            "X-Fin-Product-Mode": "current",
            "X-Fin-Case-Permissions": "current_product:read",
        },
    )

    assert response.status_code == 200
    assert response.headers["etag"].startswith('"current-runtime-requests=')
    assert response.json()["summary"]["hybrid_selected_candidate_count"] == 1
    assert response.json()["material_scope"]["mode"] == (
        "deterministic_runtime_fallback"
    )
