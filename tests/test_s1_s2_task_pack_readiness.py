from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from retrieval.integrated_pack_readiness import compile_integrated_requirement_readiness
from retrieval.task_pack_readiness import (
    TaskPackReadinessError,
    compile_requirement_review_successor,
    compile_task_pack_readiness,
)


ROOT = Path(__file__).resolve().parents[1]
PROGRAM = ROOT / "configs" / "retrieval" / (
    "fin_ia_0_1_3_s1_s2_dell_value_capture_task_readiness_program_v1_0.json"
)
SUCCESSOR_PROGRAM = ROOT / "configs" / "retrieval" / (
    "fin_ia_0_1_3_s1_s2_dell_value_capture_task_readiness_program_v1_1.json"
)


def _json(ref: str | Path) -> dict:
    path = Path(ref)
    if not path.is_absolute():
        path = ROOT / path
    return json.loads(path.read_text(encoding="utf-8"))


def _inputs() -> tuple[dict, dict[str, dict]]:
    program = _json(PROGRAM)
    inputs = {
        key: _json(binding["ref"])
        for key, binding in program["input_bindings"].items()
    }
    return program, inputs


def _compile() -> tuple[dict, dict, dict]:
    program, inputs = _inputs()
    successor = compile_requirement_review_successor(
        program=program["review_successor_program"],
        predecessor_review_plan=inputs["predecessor_review_plan"],
        predecessor_polarity_plan=inputs["predecessor_polarity_plan"],
        evidence_pack=inputs["evidence_pack"],
        recorded_at="2026-08-23T04:30:00+08:00",
    )
    integrated = compile_integrated_requirement_readiness(
        product_projection=inputs["product_replay"]["product_projection"],
        evidence_pack=inputs["evidence_pack"],
        review_plan=successor["review_plan"],
        polarity_plan=successor["polarity_plan"],
        anchor_catalog=inputs["anchor_catalog"],
        recorded_at="2026-08-23T04:30:00+08:00",
    )
    quantitative_public = inputs["task_quantitative_public_result"]
    quantitative_full = _json(quantitative_public["full_result_ref"])
    readiness = compile_task_pack_readiness(
        program=program["task_readiness_program"],
        integrated_readiness=integrated,
        quantitative_projection=quantitative_full["task_quantitative_projection"],
        evidence_pack=inputs["evidence_pack"],
        recorded_at="2026-08-23T04:30:00+08:00",
    )
    return successor, integrated, readiness


def test_current_dell_pack_is_ready_for_one_bounded_value_capture_unit() -> None:
    successor, integrated, readiness = _compile()

    assert len(successor["expected_new_evidence_item_digests"]) == 5
    assert integrated["summary"] == {
        "requirement_count": 20,
        "fully_satisfied_requirement_count": 5,
        "research_consumable_requirement_count": 15,
        "request_count": 12,
        "ready_request_count": 1,
        "research_consumable_request_count": 9,
        "integrated_state_counts": {
            "not_ready_s1_evidence": 5,
            "ready": 1,
            "ready_s1_numeric_context_only": 4,
            "ready_with_claim_boundary": 10,
        },
    }
    requests = {row["request_id"]: row for row in integrated["requests"]}
    assert requests["REQ::DELL::SUPPLY_UPSTREAM_CAPACITY::V1"]["state"] == (
        "research_consumable_with_boundaries_or_s2_gaps"
    )
    assert requests["REQ::DELL::SUPPLY_RELATIONSHIP::V1"]["state"] == "not_ready"
    assert readiness["status"] == (
        "ready_for_bounded_dynamic_single_unit_with_actionable_gaps"
    )
    assert readiness["authority"]["all_S1_requests_ready"] is False
    assert {row["request_id"] for row in readiness["actionable_gap_requests"]} == {
        "REQ::DELL::PRICE_CONFIGURATION::V1",
        "REQ::DELL::UNIT_VOLUME::V1",
        "REQ::DELL::SUPPLY_RELATIONSHIP::V1",
    }


def test_every_promoted_current_pack_item_requires_a_review_delta() -> None:
    program, inputs = _inputs()
    mutated = deepcopy(program["review_successor_program"])
    mutated["review_updates"][0]["append_evidence_bindings"] = []
    target_digest = (
        "7bbdc8b2799c12c824268c2f9f9ef45ff506587cebec3815b8f42f6fdbb03de6"
    )
    for update in mutated["review_updates"]:
        update["append_evidence_bindings"] = [
            row
            for row in update.get("append_evidence_bindings") or []
            if row["evidence_item_digest"] != target_digest
        ]
    for update in mutated["polarity_updates"]:
        for axis in update["axis_updates"]:
            axis["add_evidence_item_digests"] = [
                digest
                for digest in axis.get("add_evidence_item_digests") or []
                if digest != target_digest
            ]

    with pytest.raises(
        TaskPackReadinessError,
        match="task_pack_expected_new_evidence_not_exhaustively_reviewed",
    ):
        compile_requirement_review_successor(
            program=mutated,
            predecessor_review_plan=inputs["predecessor_review_plan"],
            predecessor_polarity_plan=inputs["predecessor_polarity_plan"],
            evidence_pack=inputs["evidence_pack"],
            recorded_at="2026-08-23T04:30:00+08:00",
        )


def test_task_readiness_fails_if_a_declared_gap_is_silently_closed() -> None:
    program, inputs = _inputs()
    successor = compile_requirement_review_successor(
        program=program["review_successor_program"],
        predecessor_review_plan=inputs["predecessor_review_plan"],
        predecessor_polarity_plan=inputs["predecessor_polarity_plan"],
        evidence_pack=inputs["evidence_pack"],
        recorded_at="2026-08-23T04:30:00+08:00",
    )
    integrated = compile_integrated_requirement_readiness(
        product_projection=inputs["product_replay"]["product_projection"],
        evidence_pack=inputs["evidence_pack"],
        review_plan=successor["review_plan"],
        polarity_plan=successor["polarity_plan"],
        anchor_catalog=inputs["anchor_catalog"],
        recorded_at="2026-08-23T04:30:00+08:00",
    )
    quantitative_public = inputs["task_quantitative_public_result"]
    projection = deepcopy(
        _json(quantitative_public["full_result_ref"])["task_quantitative_projection"]
    )
    next(
        row
        for row in projection["typed_gap_dispositions"]
        if row["gap_id"] == "dell-gap-pricing-asp"
    )["closed"] = True

    with pytest.raises(
        TaskPackReadinessError,
        match="task_pack_actionable_gap_not_preserved",
    ):
        compile_task_pack_readiness(
            program=program["task_readiness_program"],
            integrated_readiness=integrated,
            quantitative_projection=projection,
            evidence_pack=inputs["evidence_pack"],
            recorded_at="2026-08-23T04:30:00+08:00",
        )


def _compile_successor() -> tuple[dict, dict, dict, dict]:
    program = _json(SUCCESSOR_PROGRAM)
    inputs = {
        key: _json(binding["ref"])
        for key, binding in program["input_bindings"].items()
    }
    predecessor = inputs["predecessor_task_readiness_full_result"][
        "review_successor"
    ]
    successor = compile_requirement_review_successor(
        program=program["review_successor_program"],
        predecessor_review_plan=predecessor["review_plan"],
        predecessor_polarity_plan=predecessor["polarity_plan"],
        evidence_pack=inputs["evidence_pack"],
        recorded_at="2026-08-24T12:00:00+08:00",
    )
    integrated = compile_integrated_requirement_readiness(
        product_projection=inputs["product_replay"]["product_projection"],
        evidence_pack=inputs["evidence_pack"],
        review_plan=successor["review_plan"],
        polarity_plan=successor["polarity_plan"],
        anchor_catalog=inputs["anchor_catalog"],
        recorded_at="2026-08-24T12:00:00+08:00",
    )
    quantitative_public = inputs["task_quantitative_public_result"]
    quantitative = _json(quantitative_public["full_result_ref"])[
        "task_quantitative_projection"
    ]
    bridge_public = inputs["product_value_bridge_public_result"]
    bridge = _json(bridge_public["full_result_ref"])["product_value_bridge"]
    readiness = compile_task_pack_readiness(
        program=program["task_readiness_program"],
        integrated_readiness=integrated,
        quantitative_projection=quantitative,
        evidence_pack=inputs["evidence_pack"],
        recorded_at="2026-08-24T12:00:00+08:00",
        product_value_bridge=bridge,
    )
    return successor, integrated, readiness, bridge


def test_r4_successor_leaves_only_company_units_not_ready() -> None:
    successor, integrated, readiness, bridge = _compile_successor()

    assert len(successor["expected_new_evidence_item_digests"]) == 7
    assert integrated["summary"] == {
        "requirement_count": 20,
        "fully_satisfied_requirement_count": 7,
        "research_consumable_requirement_count": 18,
        "request_count": 12,
        "ready_request_count": 2,
        "research_consumable_request_count": 11,
        "integrated_state_counts": {
            "not_ready_s1_evidence": 2,
            "ready": 2,
            "ready_s1_numeric_context_only": 5,
            "ready_with_claim_boundary": 11,
        },
    }
    requests = {row["request_id"]: row for row in integrated["requests"]}
    assert requests["REQ::DELL::PRICE_CONFIGURATION::V1"]["state"] == (
        "research_consumable_with_boundaries_or_s2_gaps"
    )
    assert requests["REQ::DELL::SUPPLY_RELATIONSHIP::V1"]["state"] == "ready"
    assert requests["REQ::DELL::UNIT_VOLUME::V1"]["state"] == "not_ready"
    assert [row["request_id"] for row in readiness["actionable_gap_requests"]] == [
        "REQ::DELL::UNIT_VOLUME::V1"
    ]
    assert readiness["product_value_bridge"][
        "safe_for_bounded_dynamic_research"
    ] is True
    assert bridge["bridge_readiness"]["s2_stage_qualified"] is False


def test_r4_task_readiness_rejects_silent_bridge_gap_closure() -> None:
    program = _json(SUCCESSOR_PROGRAM)
    inputs = {
        key: _json(binding["ref"])
        for key, binding in program["input_bindings"].items()
    }
    predecessor = inputs["predecessor_task_readiness_full_result"][
        "review_successor"
    ]
    successor = compile_requirement_review_successor(
        program=program["review_successor_program"],
        predecessor_review_plan=predecessor["review_plan"],
        predecessor_polarity_plan=predecessor["polarity_plan"],
        evidence_pack=inputs["evidence_pack"],
        recorded_at="2026-08-24T12:00:00+08:00",
    )
    integrated = compile_integrated_requirement_readiness(
        product_projection=inputs["product_replay"]["product_projection"],
        evidence_pack=inputs["evidence_pack"],
        review_plan=successor["review_plan"],
        polarity_plan=successor["polarity_plan"],
        anchor_catalog=inputs["anchor_catalog"],
        recorded_at="2026-08-24T12:00:00+08:00",
    )
    quantitative_public = inputs["task_quantitative_public_result"]
    quantitative = _json(quantitative_public["full_result_ref"])[
        "task_quantitative_projection"
    ]
    bridge_public = inputs["product_value_bridge_public_result"]
    bridge = deepcopy(
        _json(bridge_public["full_result_ref"])["product_value_bridge"]
    )
    next(
        row
        for row in bridge["bridge_gap_receipts"]
        if row["gap_id"] == "dell-gap-product-profit-attribution"
    )["closed"] = True

    with pytest.raises(
        TaskPackReadinessError,
        match="task_pack_product_value_bridge_checks_failed",
    ):
        compile_task_pack_readiness(
            program=program["task_readiness_program"],
            integrated_readiness=integrated,
            quantitative_projection=quantitative,
            evidence_pack=inputs["evidence_pack"],
            recorded_at="2026-08-24T12:00:00+08:00",
            product_value_bridge=bridge,
        )
