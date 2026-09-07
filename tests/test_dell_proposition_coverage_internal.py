from __future__ import annotations

import json
from pathlib import Path

from scripts.data_retrieval.run_dell_proposition_coverage_internal import (
    PROGRAM,
    _program_material_blueprints,
    build_public_projection,
)


ROOT = Path(__file__).resolve().parents[1]


def _request_result(request_id: str, *, complete: bool) -> dict:
    return {
        "request": {
            "request_id": request_id,
            "cell_id": f"CELL::{request_id}",
            "requested_facet_ids": ["pricing_and_mix"],
            "target_entities": ["DELL"],
        },
        "summary": {
            "compiled_lane_count": 2,
            "nonempty_lane_count": 2,
            "typed_fact_resolved_count": 1,
            "typed_fact_gap_count": 1,
            "typed_fact_conflict_count": 0,
        },
        "hybrid_object_retrieval": {
            "summary": {
                "eligible_object_count": 20,
                "bm25_first_stage_count": 10,
                "qwen_first_stage_count": 10,
                "union_count_before_source_quota": 12,
                "selected_count": 6,
                "selected_both_routes": 4,
                "selected_bm25_only": 1,
                "selected_qwen_only": 1,
                "selected_candidate_count_by_owner": {"DELL": 6},
                "owner_floor_unmet": [],
                "material_scope_ready": complete,
                "material_set_complete": complete,
            },
            "material_evidence": {
                "selection": {
                    "requirement_receipts": [
                        {"requirement_id": "MAT-1", "complete": complete}
                    ],
                    "unmet_requirement_ids": [] if complete else ["MAT-1"],
                }
            },
        },
        "route_execution_truth": {
            "narrative_route_requests": [
                {
                    "routes": [
                        {"execution_state": "executed"},
                        {"execution_state": "not_executed_route_unavailable"},
                    ]
                }
            ],
            "typed_fact_route_requests": [],
        },
        "source_route_execution_truth": {
            "candidate_coverage_state": "complete" if complete else "incomplete",
            "supplement_route_required": not complete,
            "summary": {
                "route_execution_state_counts": {"executed_local_snapshot": 1},
                "official_or_external_supplement_route_exhausted": False,
                "all_requirements_public_information_gap_eligible": False,
            },
        },
        "candidate_ceiling_provenance": {
            "earliest_observed_limitation": None,
            "gap_eligibility": {"public_information_gap_eligible": False},
        },
    }


def test_public_projection_keeps_candidate_and_evidence_authority_separate() -> None:
    program = {
        "program_id": "PROGRAM-1",
        "research_as_of": "2026-08-06",
        "propositions": [
            {
                "proposition_id": "PROP-1",
                "business_question_zh": "问题",
                "request_ids": ["REQ-1", "REQ-2"],
            }
        ],
    }
    execution = {
        "summary": {"request_count": 2, "model_calls": 0, "network_calls": 0},
        "request_results": [
            _request_result("REQ-1", complete=True),
            _request_result("REQ-2", complete=False),
        ],
    }

    result = build_public_projection(
        program=program,
        execution=execution,
        private_ref="data/workbench_private/result.json",
        private_sha256="a" * 64,
        recorded_at="2026-08-22T00:00:00+00:00",
        prepared_from_commit="b" * 40,
    )

    assert result["summary"]["model_calls"] == 0
    assert result["propositions"][0]["selected_candidate_count"] == 12
    assert result["propositions"][0]["internal_coverage_state"] == (
        "external_or_review_successor_required"
    )
    assert result["authority"] == {
        "candidate_decision_complete": False,
        "evidence_promotion_authorized": False,
        "numeric_authority_granted_by_text_retrieval": False,
        "public_information_gap_authorized": False,
        "evidence_pack_readiness_authorized": False,
        "dynamic_single_unit_authorized": False,
    }
    assert result["requests"][0]["local_route_execution_state_counts"] == {
        "executed": 1,
        "not_executed_route_unavailable": 1,
    }


def test_program_material_blueprints_preserve_all_twelve_business_requests() -> None:
    program = json.loads(PROGRAM.read_text(encoding="utf-8"))

    blueprints = _program_material_blueprints(program)

    assert len(blueprints) == 12
    price = blueprints["REQ::DELL::PRICE_CONFIGURATION::V1"]
    assert [row["role"] for row in price["material_requirements"]] == [
        "direct",
        "context",
    ]
    assert all(
        row["product_ids"]
        == [
            "AI server observable price range",
            "AI server configuration tiers",
            "GPU HBM networking and storage configuration mix",
        ]
        for row in price["material_requirements"]
    )
    assert price["material_requirements"][0]["metric_ids"]
    assert price["material_requirements"][1]["metric_ids"] == []


def test_program_keeps_derived_s2_and_s3_outputs_out_of_s1_material_axes() -> None:
    program = json.loads(PROGRAM.read_text(encoding="utf-8"))
    requests = {
        row["request_id"]: row for row in program["evidence_requests"]
    }
    visible_products = {
        product
        for request in requests.values()
        for product in request["product_intents"]
    }

    assert "unit-volume sensitivity range" not in visible_products
    assert "bounded PVM scenario" not in visible_products
    assert "supplier cost share sensitivity" not in visible_products
    assert "observable invalidation threshold" not in visible_products
    assert program["material_scope_blueprint"]["stage_scope"] == (
        "observable_source_inputs_only"
    )

    handoffs = program["stage_output_handoffs"]
    assert {row["handoff_id"] for row in handoffs["S2"]} == {
        "DELL-S2-UNIT-VOLUME-RANGE",
        "DELL-S2-PVM-BRIDGE",
        "DELL-S2-VALUE-POOL-SENSITIVITY",
    }
    assert [row["handoff_id"] for row in handoffs["S3"]] == [
        "DELL-S3-WHAT-WOULD-CHANGE"
    ]
