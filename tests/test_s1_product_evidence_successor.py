from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path

import pytest

from retrieval.product_evidence_successor import (
    ADJUDICATION_PLAN_SCHEMA_VERSION,
    POLICY_SCHEMA_VERSION,
    ProductEvidenceSuccessorError,
    build_product_evidence_successor,
    compile_product_evidence_adjudication_policy,
)
from retrieval.query_plan import canonical_digest
from sec_agent.research.reviewed_evidence_pack import (
    REVIEWED_EVIDENCE_PACK_CONTRACT,
    REVIEWED_EVIDENCE_PACK_SCHEMA,
    validate_reviewed_evidence_pack,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_graph(tmp_path: Path) -> tuple[dict, dict, dict, Path]:
    capture = tmp_path / "capture.json"
    capture.write_text('{"official": true}', encoding="utf-8")
    parent = {
        "document_id": "DOC-1",
        "ticker": "MU",
        "source_type": "10-Q",
        "publication_date": "2026-06-25",
        "period_end": "2026-05-28",
        "lineage_state": "immutable_capture_bound",
        "capture_ref": str(capture),
        "capture_sha256": _sha256(capture),
    }
    source = {
        "evidence_id": "SRC-1",
        "company": "Micron Technology, Inc.",
        "ticker": "MU",
        "source_type": "10-Q",
        "source_tier": "primary_sec_filing",
        "publication_date": "2026-06-25",
        "period_end": "2026-05-28",
        "source_url": "https://www.sec.gov/example",
        "license_scope": "public",
        "redistributable": False,
        "text": (
            "We have entered into strategic customer agreements that include "
            "take-or-pay commitments."
        ),
        "metadata": {"parent_document_id": "DOC-1"},
    }
    surface = (
        "We have entered into strategic customer agreements that include "
        "take-or-pay commitments."
    )
    compiled = {
        "compiled_object_id": "COBJ::ONE",
        "candidate_not_evidence": True,
        "evidence_promoted": False,
        "numeric_authority": False,
        "object_kind": "claim",
        "base_object_view": {
            "source_record_id": "SRC-1",
            "source_record_digest": canonical_digest(source),
            "parent_document_id": "DOC-1",
            "parent_document_digest": canonical_digest(parent),
            "ticker": "MU",
            "source_type": "10-Q",
            "source_tier": "primary_sec_filing",
            "publication_date": "2026-06-25",
            "period_end": "2026-05-28",
            "surface_text": surface,
            "surface_digest": canonical_digest(surface),
        },
    }
    return compiled, source, parent, capture


def _predecessor() -> dict:
    body = {
        "schema_version": REVIEWED_EVIDENCE_PACK_SCHEMA,
        "contract_ref": REVIEWED_EVIDENCE_PACK_CONTRACT,
        "case_key": "MU",
        "research_as_of": "2026-08-06",
        "evidence_items": [
            {
                "case_key": "MU",
                "target_id": "OLD-TARGET",
                "object_type": "claim",
                "compiled_object_id": "COBJ::ONE",
                "source_record_id": "SRC-1",
                "source_material_ref": "OLD-MAT",
                "evidence_item_digest": "a" * 64,
                "publication_date": "2026-06-25",
                "source_reporting_period_end": "2026-05-28",
                "research_as_of": "2026-08-06",
                "disposition": "accepted_direct_source_evidence",
                "evidence_role": "issuer_direct_source",
                "relationship_directions": ["subject_self_disclosure"],
                "slot_bindings": [
                    {
                        "slot_id": "demand_volume_quality",
                        "facet_ids": ["orders_and_backlog"],
                    }
                ],
                "writer_citable": True,
                "causal_attribution_authorized": False,
            }
        ],
        "source_materials": [
            {
                "material_ref": "OLD-MAT",
                "evidence_owner_ticker": "MU",
                "source_type": "10-Q",
                "period_end": "2026-05-28",
            }
        ],
        "rejected_items": [],
        "residual_gaps": [
            {"gap_id": "GAP-1", "gap_code": "open", "slot_id": "demand_volume_quality"}
        ],
        "observed_counts": {},
    }
    return {**body, "pack_payload_digest": canonical_digest(body)}


def _projection() -> dict:
    return {
        "case_key": "MU",
        "objective": {"research_as_of": "2026-08-06"},
        "request_results": [
            {
                "request": {"request_id": "REQ-1"},
                "lanes": [
                    {
                        "lane": {
                            "slot_id": "demand_volume_quality",
                            "facet_id": "orders_and_backlog",
                            "owner_queries": [
                                {
                                    "evidence_owner_ticker": "MU",
                                    "relationship_direction": "subject_self_disclosure",
                                }
                            ],
                        }
                    }
                ],
            },
            {
                "request": {"request_id": "REQ-2"},
                "lanes": [
                    {
                        "lane": {
                            "slot_id": "demand_volume_quality",
                            "facet_id": "conversion_and_durability",
                            "owner_queries": [
                                {
                                    "evidence_owner_ticker": "MU",
                                    "relationship_direction": "subject_self_disclosure",
                                }
                            ],
                        }
                    }
                ],
            },
        ],
    }


def _review_item(*, request_id: str, requirement_id: str, suffix: str) -> dict:
    body = {
        "review_item_ref": f"CANDOBJ::{suffix}",
        "request_id": request_id,
        "compiled_object_id": "COBJ::ONE",
        "source_record_id": "SRC-1",
        "evidence_owner_ticker": "MU",
        "object_kind": "claim",
        "requirement_contexts": [{"requirement_id": requirement_id}],
    }
    return {**body, "review_item_digest": canonical_digest(body)}


def _packet() -> dict:
    first = _review_item(request_id="REQ-1", requirement_id="MER-1", suffix="ONE")
    second = _review_item(request_id="REQ-2", requirement_id="MER-2", suffix="TWO")
    body = {
        "case_key": "MU",
        "review_item_count": 2,
        "requests": [
            {"request_id": "REQ-1", "review_items": [first]},
            {"request_id": "REQ-2", "review_items": [second]},
        ],
    }
    return {**body, "review_packet_digest": canonical_digest(body)}


def _policy(packet: dict, predecessor: dict) -> dict:
    decisions = []
    for request in packet["requests"]:
        item = request["review_items"][0]
        requirement_id = item["requirement_contexts"][0]["requirement_id"]
        decisions.append(
            {
                "review_item_ref": item["review_item_ref"],
                "review_item_digest": item["review_item_digest"],
                "action": "accept_for_requirements",
                "requirement_ids": [requirement_id],
                "business_meaning_zh": "多年期客户承诺支持需求可见性。",
                "claim_boundary_zh": "仅证明合同结构，不证明最终出货或利润实现。",
                "reason_codes": ["official_current_claim_material"],
            }
        )
    body = {
        "schema_version": POLICY_SCHEMA_VERSION,
        "status": "approved_internal_engineering_adjudication",
        "policy_id": "POLICY-1",
        "case_key": "MU",
        "research_as_of": "2026-08-06",
        "candidate_review_packet_digest": packet["review_packet_digest"],
        "predecessor_pack_payload_digest": predecessor["pack_payload_digest"],
        "qualified_human_review": False,
        "S1_qualification_authorized": False,
        "product_publication_authorized": False,
        "successor_known_boundary": "Internal engineering Evidence successor only.",
        "decisions": decisions,
    }
    return {**body, "policy_digest": canonical_digest(body)}


def _plan(packet: dict, predecessor: dict) -> dict:
    accepted = packet["requests"][0]["review_items"][0]
    requirement_id = accepted["requirement_contexts"][0]["requirement_id"]
    body = {
        "schema_version": ADJUDICATION_PLAN_SCHEMA_VERSION,
        "status": "approved_internal_engineering_plan",
        "plan_id": "PLAN-1",
        "case_key": "MU",
        "research_as_of": "2026-08-06",
        "candidate_review_packet_digest": packet["review_packet_digest"],
        "predecessor_pack_payload_digest": predecessor["pack_payload_digest"],
        "default_claim_action": "reject_for_current_scope",
        "metric_row_action": "delegate_to_s2_numeric_authority",
        "qualified_human_review": False,
        "S1_qualification_authorized": False,
        "product_publication_authorized": False,
        "successor_known_boundary": "Internal engineering Evidence successor only.",
        "accepted_items": [
            {
                "review_item_ref": accepted["review_item_ref"],
                "action": "accept_for_requirements",
                "requirement_ids": [requirement_id],
                "business_meaning_zh": "多年期客户承诺支持需求可见性。",
                "claim_boundary_zh": "不证明最终出货或利润实现。",
                "reason_codes": ["official_current_claim_material"],
            }
        ],
    }
    return {**body, "plan_digest": canonical_digest(body)}


def test_compact_plan_expands_to_complete_item_decisions() -> None:
    packet = _packet()
    predecessor = _predecessor()

    policy = compile_product_evidence_adjudication_policy(
        candidate_review_packet=packet,
        plan=_plan(packet, predecessor),
    )

    actions = {
        row["review_item_ref"]: row["action"] for row in policy["decisions"]
    }
    assert actions == {
        "CANDOBJ::ONE": "accept_for_requirements",
        "CANDOBJ::TWO": "reject_for_current_scope",
    }
    assert policy["source_plan_digest"] == _plan(packet, predecessor)["plan_digest"]


def test_compact_plan_cannot_reference_candidate_outside_bound_packet() -> None:
    packet = _packet()
    predecessor = _predecessor()
    plan = _plan(packet, predecessor)
    plan["accepted_items"][0]["review_item_ref"] = "CANDOBJ::UNKNOWN"
    plan_body = deepcopy(plan)
    plan_body.pop("plan_digest")
    plan["plan_digest"] = canonical_digest(plan_body)

    with pytest.raises(
        ProductEvidenceSuccessorError,
        match="product_evidence_adjudication_override_identity_invalid",
    ):
        compile_product_evidence_adjudication_policy(
            candidate_review_packet=packet,
            plan=plan,
        )


def test_successor_merges_one_claim_into_explicit_proposition_bindings(
    tmp_path: Path,
) -> None:
    compiled, source, parent, _ = _source_graph(tmp_path)
    predecessor = _predecessor()
    packet = _packet()

    result = build_product_evidence_successor(
        predecessor=predecessor,
        product_projection=_projection(),
        candidate_review_packet=packet,
        policy=_policy(packet, predecessor),
        compiled_objects_by_id={"COBJ::ONE": compiled},
        source_records_by_id={"SRC-1": source},
        parent_documents_by_id={"DOC-1": parent},
        capture_resolver=Path,
        recorded_at="2026-08-19",
    )

    successor = result["successor_pack"]
    validate_reviewed_evidence_pack(successor)
    assert len(successor["evidence_items"]) == 1
    item = successor["evidence_items"][0]
    assert item["target_id"] != "OLD-TARGET"
    assert {
        requirement_id
        for binding in item["slot_bindings"]
        for requirement_id in binding["requirement_ids"]
    } == {"MER-1", "MER-2"}
    assert result["coverage_delta"] == {
        "predecessor_evidence_count": 1,
        "successor_evidence_count": 1,
        "retired_evidence_count": 1,
        "added_or_rebound_evidence_count": 1,
        "numeric_rows_delegated_to_S2": 0,
        "candidate_text_promoted_count": 0,
        "numeric_authority_granted_count": 0,
    }
    assert result["authority"]["qualified_human_review"] is False


def test_policy_must_decide_every_bounded_review_item(tmp_path: Path) -> None:
    compiled, source, parent, _ = _source_graph(tmp_path)
    predecessor = _predecessor()
    packet = _packet()
    policy = _policy(packet, predecessor)
    policy["decisions"] = policy["decisions"][:1]
    body = deepcopy(policy)
    body.pop("policy_digest")
    policy["policy_digest"] = canonical_digest(body)

    with pytest.raises(
        ProductEvidenceSuccessorError,
        match="product_evidence_policy_decision_coverage_invalid",
    ):
        build_product_evidence_successor(
            predecessor=predecessor,
            product_projection=_projection(),
            candidate_review_packet=packet,
            policy=policy,
            compiled_objects_by_id={"COBJ::ONE": compiled},
            source_records_by_id={"SRC-1": source},
            parent_documents_by_id={"DOC-1": parent},
            capture_resolver=Path,
            recorded_at="2026-08-19",
        )


def test_contract_description_without_execution_cannot_be_promoted(
    tmp_path: Path,
) -> None:
    compiled, source, parent, _ = _source_graph(tmp_path)
    surface = "Strategic customer agreements may include take-or-pay commitments."
    source["text"] = surface
    compiled["base_object_view"]["surface_text"] = surface
    compiled["base_object_view"]["surface_digest"] = canonical_digest(surface)
    compiled["base_object_view"]["source_record_digest"] = canonical_digest(source)
    predecessor = _predecessor()
    packet = _packet()

    with pytest.raises(
        ProductEvidenceSuccessorError,
        match="product_evidence_role_incompatible",
    ):
        build_product_evidence_successor(
            predecessor=predecessor,
            product_projection=_projection(),
            candidate_review_packet=packet,
            policy=_policy(packet, predecessor),
            compiled_objects_by_id={"COBJ::ONE": compiled},
            source_records_by_id={"SRC-1": source},
            parent_documents_by_id={"DOC-1": parent},
            capture_resolver=Path,
            recorded_at="2026-08-19",
        )


def test_metric_row_can_only_delegate_to_s2(tmp_path: Path) -> None:
    compiled, source, parent, _ = _source_graph(tmp_path)
    compiled["compiled_object_id"] = "COBJ::METRIC"
    compiled["object_kind"] = "metric_row"
    packet = _packet()
    packet["requests"] = packet["requests"][:1]
    item = packet["requests"][0]["review_items"][0]
    item["compiled_object_id"] = "COBJ::METRIC"
    item["object_kind"] = "metric_row"
    item_body = deepcopy(item)
    item_body.pop("review_item_digest")
    item["review_item_digest"] = canonical_digest(item_body)
    packet_body = deepcopy(packet)
    packet_body["review_item_count"] = 1
    packet_body.pop("review_packet_digest")
    packet_body["requests"][0]["review_items"][0] = item
    packet = {**packet_body, "review_packet_digest": canonical_digest(packet_body)}
    predecessor = _predecessor()
    policy = _policy(packet, predecessor)
    policy["decisions"][0] = {
        "review_item_ref": item["review_item_ref"],
        "review_item_digest": item["review_item_digest"],
        "action": "delegate_to_s2_numeric_authority",
        "requirement_ids": [],
        "reason_codes": ["metric_authority_owned_by_S2"],
    }
    policy_body = deepcopy(policy)
    policy_body.pop("policy_digest")
    policy["policy_digest"] = canonical_digest(policy_body)

    result = build_product_evidence_successor(
        predecessor=predecessor,
        product_projection={
            **_projection(),
            "request_results": _projection()["request_results"][:1],
        },
        candidate_review_packet=packet,
        policy=policy,
        compiled_objects_by_id={"COBJ::METRIC": compiled},
        source_records_by_id={"SRC-1": source},
        parent_documents_by_id={"DOC-1": parent},
        capture_resolver=Path,
        recorded_at="2026-08-19",
    )

    assert result["decision_counts"]["delegate_to_s2_numeric_authority"] == 1
    assert result["successor_pack"]["evidence_items"] == predecessor["evidence_items"]
    assert result["authority"]["numeric_fact_authority"] is False


def test_request_context_is_preserved_without_satisfying_a_requirement(
    tmp_path: Path,
) -> None:
    compiled, source, parent, _ = _source_graph(tmp_path)
    predecessor = _predecessor()
    packet = _packet()
    packet["requests"] = packet["requests"][:1]
    item = packet["requests"][0]["review_items"][0]
    item["review_scope"] = "material_review_context"
    item["requirement_contexts"] = []
    item_body = deepcopy(item)
    item_body.pop("review_item_digest")
    item["review_item_digest"] = canonical_digest(item_body)
    packet_body = deepcopy(packet)
    packet_body["review_item_count"] = 1
    packet_body.pop("review_packet_digest")
    packet = {**packet_body, "review_packet_digest": canonical_digest(packet_body)}
    policy_body = {
        "schema_version": POLICY_SCHEMA_VERSION,
        "status": "approved_internal_engineering_adjudication",
        "policy_id": "POLICY-CONTEXT",
        "case_key": "MU",
        "research_as_of": "2026-08-06",
        "candidate_review_packet_digest": packet["review_packet_digest"],
        "predecessor_pack_payload_digest": predecessor["pack_payload_digest"],
        "qualified_human_review": False,
        "S1_qualification_authorized": False,
        "product_publication_authorized": False,
        "successor_known_boundary": "Internal request context only.",
        "decisions": [
            {
                "review_item_ref": item["review_item_ref"],
                "review_item_digest": item["review_item_digest"],
                "action": "accept_for_request_context",
                "requirement_ids": [],
                "business_meaning_zh": "作为当前需求判断的反方背景。",
                "claim_boundary_zh": "不直接证明订单、出货或利润实现。",
                "reason_codes": ["material_counter_context"],
            }
        ],
    }
    policy = {**policy_body, "policy_digest": canonical_digest(policy_body)}

    result = build_product_evidence_successor(
        predecessor=predecessor,
        product_projection={
            **_projection(),
            "request_results": _projection()["request_results"][:1],
        },
        candidate_review_packet=packet,
        policy=policy,
        compiled_objects_by_id={"COBJ::ONE": compiled},
        source_records_by_id={"SRC-1": source},
        parent_documents_by_id={"DOC-1": parent},
        capture_resolver=Path,
        recorded_at="2026-08-19",
    )

    binding = result["successor_pack"]["evidence_items"][0]["slot_bindings"][0]
    assert binding["binding_kind"] == "request_context"
    assert binding["requirement_ids"] == []
    assert result["decision_counts"]["accept_for_request_context"] == 1
