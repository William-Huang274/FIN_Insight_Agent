from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.research.dynamic_truth_spine import (
    DynamicTruthSpineError,
    bind_dynamic_evidence_responses_to_research_input,
    compile_dynamic_evidence_responses,
    compile_dynamic_claim_authority_policy,
    compile_dynamic_claim_surface_policy,
    compile_dynamic_reviewed_pack_view,
)
from sec_agent.research.claim_authority import (
    compile_claim_authority_research_input,
)
from sec_agent.research.claim_surface_authority import (
    compile_claim_surface_authority_research_input,
)
from sec_agent.research.reviewed_evidence_pack import canonical_digest


POLICY = ROOT / (
    "configs/research/fin_ia_0_1_3_s3_dynamic_truth_spine_policy_v1_0.json"
)
SUCCESSOR_POLICY = ROOT / (
    "configs/research/fin_ia_0_1_3_s3_dynamic_truth_spine_policy_v1_1.json"
)
CLAIM_TEMPLATE = ROOT / (
    "configs/research/"
    "fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_claim_authority_v1_0.json"
)
CLAIM_SURFACE_TEMPLATE = ROOT / (
    "configs/research/"
    "fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_"
    "claim_surface_authority_v1_2.json"
)


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _item(
    *,
    digest: str = "evidence-digest-1",
    source_id: str = "SOURCE::DELL::1",
    case_key: str = "DELL",
    owner: str = "DELL",
    slot_id: str = "pricing_mix_value_capture",
    source_type: str = "10-Q",
    publication_date: str = "2026-05-30",
    period_end: str = "2026-05-01",
    writer_citable: bool = True,
    source_content_digest: str = "source-text-digest",
) -> dict[str, object]:
    return {
        "case_key": case_key,
        "target_id": source_id,
        "source_record_id": source_id,
        "object_type": "source_segment",
        "disposition": "accepted_direct_source_evidence",
        "evidence_role": "issuer_direct_source",
        "publication_date": publication_date,
        "source_reporting_period_end": period_end,
        "research_as_of": "2026-08-06",
        "relationship_directions": ["subject_self_disclosure"],
        "slot_bindings": [
            {
                "business_meaning_zh": "公司披露了与利润承接有关的事实。",
                "claim_boundary_zh": "不得把公司口径直接归因到单一产品。",
                "facet_ids": ["profit_capture_bridge"],
                "qualification_id": "test-profit-bridge",
                "slot_id": slot_id,
            }
        ],
        "numeric_use_boundary": "typed facts only",
        "causal_attribution_authorized": False,
        "writer_citable": writer_citable,
        "evidence_item_digest": digest,
        "source_content_digest": source_content_digest,
        "source": {
            "material_ref": "MAT::1",
            "source_record_id": source_id,
            "evidence_owner_ticker": owner,
            "source_tier": "primary_sec_filing",
            "source_type": source_type,
            "source_url": "https://example.invalid/filing",
            "publication_date": publication_date,
            "period_end": period_end,
            "license_scope": "public",
            "redistributable": False,
            "source_text_digest": source_content_digest,
            "reviewed_source_excerpt": "reviewed evidence text",
            "excerpt_truncated": False,
            "excerpt_use_boundary": "internal review",
        },
    }


def test_public_web_item_without_reporting_period_uses_publication_date() -> None:
    item = _item(
        source_type="PUBLIC_WEB",
        publication_date="2026-03-09",
        period_end="",
    )
    item["claim_use"] = "bounded_channel_configuration_context"
    controlled = _controlled(
        [
            _candidate(
                str(item["source_record_id"]),
                owner="DELL",
                source_type="PUBLIC_WEB",
                source_content_digest=str(item["source_content_digest"]),
            )
        ]
    )
    controlled["request_results"][0]["request"]["acceptable_sources"] = [
        "PUBLIC_WEB"
    ]
    controlled["request_results"][0]["request"]["period"] = {
        "start_date": "2026-01-01",
        "end_date": "2026-08-06",
        "fiscal_years": [],
    }
    pack = _pack([item])

    result = compile_dynamic_evidence_responses(
        policy=_json(SUCCESSOR_POLICY),
        controlled_plan=controlled,
        evidence_pack=pack,
    )

    assert result["summary"]["accepted_reviewed_evidence_count"] == 1


def _pack(items: list[dict[str, object]]) -> dict[str, object]:
    body = {
        "schema_version": "fin_ia_current_research_evidence_pack_projection_v1_0",
        "projection_mode": "current",
        "status": "reviewed_local_evidence_pack_ready_with_declared_gaps",
        "result_digest": "result-digest",
        "case_key": "DELL",
        "evidence_object_ready": True,
        "artifact_digest": "artifact-digest",
        "pack_payload_digest": "pack-payload-digest",
        "summary": {},
        "evidence_items": items,
        "rejected_items": [],
        "residual_gaps": [
            {
                "gap_id": "GAP::PRODUCT-PROFIT-BRIDGE",
                "slot_id": "pricing_mix_value_capture",
                "facet_id": "profit_capture_bridge",
                "gap_code": "product_profit_bridge_missing",
                "business_reason_zh": "尚无产品到公司的利润桥。",
                "supplement_direction_zh": "补充分产品利润披露。",
            },
            {
                "gap_id": "GAP::UNRELATED",
                "slot_id": "demand_volume_quality",
                "facet_id": "orders_and_backlog",
                "gap_code": "order_detail_missing",
                "business_reason_zh": "订单拆分不足。",
                "supplement_direction_zh": "补订单资料。",
            },
        ],
        "consumer_contract": {
            "writer_may_consume_only_writer_citable_items": True,
            "rejected_items_must_not_enter_prompt": True,
            "residual_gaps_must_remain_visible": True,
            "exact_numeric_surface_must_be_source_visible_or_typed": True,
        },
        "hard_boundaries": {},
        "known_boundary": "fixture",
    }
    return {**body, "projection_digest": canonical_digest(body)}


def _controlled(candidates: list[dict[str, object]]) -> dict[str, object]:
    request = {
        "schema_version": "fin_ia_evidence_request_v1_0",
        "request_id": "REQ::DELL::VALUE",
        "cell_id": "CELL::value_capture",
        "requester_role": "research_lead",
        "evidence_domain": "financial_research",
        "case_key": "DELL",
        "subject_ticker": "DELL",
        "research_as_of": "2026-08-06",
        "target_entities": ["DELL"],
        "requested_facet_ids": ["margin_and_incremental_profit"],
        "metric_intents": ["gross_margin"],
        "product_intents": ["AI server product-to-company profit bridge"],
        "period": {
            "start_date": "2025-02-01",
            "end_date": None,
            "fiscal_years": [2026, 2027],
        },
        "granularity": "quarterly",
        "unit": "mixed",
        "acceptable_sources": ["10-Q", "8-K"],
        "acceptable_proxy": False,
        "forbidden_proxy": [],
        "stop_condition": "bounded",
        "clarification_policy": "return_typed_gap",
    }
    request_result = {
        "request": request,
        "request_digest": canonical_digest(request),
        "query_plan": {
            "lanes": [
                {
                    "lane_id": "LANE::VALUE",
                    "slot_id": "pricing_mix_value_capture",
                    "facet_id": "margin_and_incremental_profit",
                }
            ]
        },
        "typed_gaps": [],
        "typed_fact_results": [],
        "lanes": [],
        "hybrid_object_retrieval": {
            "candidate_state": "candidate_not_evidence",
            "candidates": candidates,
        },
    }
    return {
        "status": "controlled_research_plan_zero_call_executed",
        "objective": {
            "objective_id": "OBJ::DELL::VALUE",
            "case_key": "DELL",
            "subject_ticker": "DELL",
            "research_as_of": "2026-08-06",
        },
        "compiled_plan": {"evidence_requests": [request]},
        "request_results": [request_result],
        "projection_digest": "controlled-plan-digest",
    }


def _candidate(
    source_id: str,
    *,
    owner: str = "DELL",
    source_type: str = "10-Q",
    rank: int = 1,
    source_content_digest: str = "",
) -> dict[str, object]:
    return {
        "rank": rank,
        "compiled_object_id": f"COBJ::{rank}",
        "source_record_id": source_id,
        "source_content_digest": source_content_digest,
        "lineage_source_record_ids": [source_id],
        "ticker": owner,
        "source_type": source_type,
        "candidate_not_evidence": True,
        "numeric_authority": False,
        "evidence_role": {
            "recommended_role": "direct_support",
            "advisory_only": True,
        },
    }


def test_public_source_reselection_is_bound_to_exact_content_slice() -> None:
    first = _item(
        digest="evidence-public-1",
        source_id="PUBLIC::DELL::SHARED-PAGE",
        source_type="PUBLIC_WEB",
        source_content_digest="content-slice-1",
    )
    second = _item(
        digest="evidence-public-2",
        source_id="PUBLIC::DELL::SHARED-PAGE",
        source_type="PUBLIC_WEB",
        source_content_digest="content-slice-2",
    )
    controlled = _controlled(
        [
            _candidate(
                "PUBLIC::DELL::SHARED-PAGE",
                source_type="PUBLIC_WEB",
                source_content_digest="content-slice-1",
            )
        ]
    )
    controlled["request_results"][0]["request"]["acceptable_sources"] = [
        "PUBLIC_WEB"
    ]
    result = compile_dynamic_evidence_responses(
        policy=_json(POLICY),
        controlled_plan=controlled,
        evidence_pack=_pack([first, second]),
    )

    assert [
        row["evidence_item_digest"] for row in result["responses"][0]["accepted"]
    ] == ["evidence-public-1"]


def test_public_source_without_content_digest_cannot_unlock_page_level_review() -> None:
    item = _item(
        digest="evidence-public-1",
        source_id="PUBLIC::DELL::SHARED-PAGE",
        source_type="PUBLIC_WEB",
        source_content_digest="content-slice-1",
    )
    controlled = _controlled(
        [_candidate("PUBLIC::DELL::SHARED-PAGE", source_type="PUBLIC_WEB")]
    )
    controlled["request_results"][0]["request"]["acceptable_sources"] = [
        "PUBLIC_WEB"
    ]
    result = compile_dynamic_evidence_responses(
        policy=_json(POLICY),
        controlled_plan=controlled,
        evidence_pack=_pack([item]),
    )

    response = result["responses"][0]
    assert response["accepted"] == []
    assert response["needs_human_review"][0]["reason"] == (
        "public_candidate_source_content_digest_missing"
    )


def test_exact_reviewed_request_match_is_reselected_without_promotion() -> None:
    pack = _pack([_item()])
    result = compile_dynamic_evidence_responses(
        policy=_json(POLICY),
        controlled_plan=_controlled([_candidate("SOURCE::DELL::1")]),
        evidence_pack=pack,
    )

    assert result["summary"]["accepted_reviewed_evidence_count"] == 1
    assert result["summary"]["new_evidence_promotions"] == 0
    response = result["responses"][0]
    assert response["accepted"][0]["evidence_item_digest"] == "evidence-digest-1"
    assert response["request_bindings"] == [
        {
            "slot_id": "pricing_mix_value_capture",
            "facet_id": "margin_and_incremental_profit",
        }
    ]
    assert response["authority"] == {
        "candidate_promoted_to_evidence": False,
        "reviewed_evidence_reselected": True,
        "numeric_authority_remains_s2": True,
        "model_decision_used": False,
    }


def test_capture_bound_source_material_is_resolved_for_bounded_context() -> None:
    item = _item(period_end="")
    source_material = item.pop("source")
    source_material["period_end"] = None
    item["source_reporting_period_end"] = None
    item["source_material_ref"] = source_material["material_ref"]
    item["claim_use"] = "bounded_market_context"
    pack = _pack([item])
    pack["source_materials"] = [source_material]

    result = compile_dynamic_evidence_responses(
        policy=_json(POLICY),
        controlled_plan=_controlled([_candidate("SOURCE::DELL::1")]),
        evidence_pack=pack,
    )

    assert result["summary"]["accepted_reviewed_evidence_count"] == 1
    assert result["summary"]["new_evidence_promotions"] == 0
    assert result["responses"][0]["accepted"][0]["source_record_id"] == (
        "SOURCE::DELL::1"
    )

    view = compile_dynamic_reviewed_pack_view(
        evidence_pack=pack,
        evidence_responses=result,
        required_slot_ids=["pricing_mix_value_capture"],
    )
    assert [row["evidence_item_digest"] for row in view["evidence_items"]] == [
        "evidence-digest-1"
    ]
    assert {
        row["slot_id"] for row in view["residual_gaps"]
    } == {"pricing_mix_value_capture"}
    assert view["dynamic_selection_binding"]["candidate_promotions"] == 0
    assert view["dynamic_selection_binding"]["typed_evidence_response_gap_count"] == 0


def test_hybrid_candidates_cannot_erase_reviewed_snapshot_candidate() -> None:
    controlled = _controlled([_candidate("SOURCE::UNREVIEWED", rank=1)])
    controlled["request_results"][0]["lanes"] = [
        {
            "candidate_state": "candidate_not_evidence",
            "candidates": [_candidate("SOURCE::DELL::1", rank=7)],
        }
    ]

    result = compile_dynamic_evidence_responses(
        policy=_json(SUCCESSOR_POLICY),
        controlled_plan=controlled,
        evidence_pack=_pack([_item()]),
    )

    response = result["responses"][0]
    assert response["candidate_route"] == (
        "hybrid_plus_immutable_snapshot_union"
    )
    assert response["candidate_count"] == 2
    assert response["accepted"][0]["evidence_item_digest"] == (
        "evidence-digest-1"
    )
    assert response["needs_human_review"][0]["reason"] == (
        "candidate_not_present_in_reviewed_pack"
    )
    assert response["authority"]["candidate_promoted_to_evidence"] is False


def test_legacy_policy_preserves_historical_hybrid_only_replay() -> None:
    controlled = _controlled([_candidate("SOURCE::UNREVIEWED", rank=1)])
    controlled["request_results"][0]["lanes"] = [
        {
            "candidate_state": "candidate_not_evidence",
            "candidates": [_candidate("SOURCE::DELL::1", rank=7)],
        }
    ]

    result = compile_dynamic_evidence_responses(
        policy=_json(POLICY),
        controlled_plan=controlled,
        evidence_pack=_pack([_item()]),
    )

    response = result["responses"][0]
    assert response["candidate_route"] == "hybrid_object_retrieval"
    assert response["candidate_count"] == 1
    assert response["accepted"] == []


@pytest.mark.parametrize(
    ("mutator", "reason"),
    [
        (lambda item: item.update(case_key="MU"), "cross_case_reviewed_item"),
        (
            lambda item: item["slot_bindings"][0].update(
                slot_id="demand_volume_quality"
            ),
            "reviewed_item_outside_request_slot",
        ),
        (
            lambda item: (
                item.update(publication_date="2026-08-07"),
                item["source"].update(publication_date="2026-08-07"),
            ),
            "reviewed_item_after_research_as_of",
        ),
        (
            lambda item: item["source"].update(evidence_owner_ticker="MU"),
            "reviewed_item_owner_outside_request",
        ),
        (
            lambda item: item["source"].update(source_type="10-K"),
            "reviewed_item_source_type_outside_request",
        ),
    ],
)
def test_reviewed_item_must_pass_every_request_gate(mutator, reason: str) -> None:
    item = _item()
    mutator(item)
    result = compile_dynamic_evidence_responses(
        policy=_json(POLICY),
        controlled_plan=_controlled([_candidate("SOURCE::DELL::1")]),
        evidence_pack=_pack([item]),
    )

    response = result["responses"][0]
    assert not response["accepted"]
    assert response["rejected"][0]["reason"] == reason
    assert any(
        row["gap"]["gap_code"] == "no_request_matched_reviewed_evidence"
        for row in response["typed_gaps"]
    )


def test_rank_and_advisory_role_cannot_promote_unreviewed_candidate() -> None:
    result = compile_dynamic_evidence_responses(
        policy=_json(POLICY),
        controlled_plan=_controlled([_candidate("SOURCE::UNREVIEWED", rank=1)]),
        evidence_pack=_pack([_item()]),
    )

    response = result["responses"][0]
    assert not response["accepted"]
    assert response["needs_human_review"][0]["reason"] == (
        "candidate_not_present_in_reviewed_pack"
    )
    assert "model_text" not in response["needs_human_review"][0]
    with pytest.raises(DynamicTruthSpineError) as exc:
        compile_dynamic_reviewed_pack_view(
            evidence_pack=_pack([_item()]),
            evidence_responses=result,
        )
    assert str(exc.value) == "dynamic_truth_spine_no_reviewed_evidence_selected"


def test_candidate_lineage_can_reselect_exact_reviewed_child() -> None:
    candidate = _candidate("SOURCE::PARENT")
    candidate["lineage_source_record_ids"] = [
        "SOURCE::PARENT",
        "SOURCE::DELL::1",
    ]
    result = compile_dynamic_evidence_responses(
        policy=_json(POLICY),
        controlled_plan=_controlled([candidate]),
        evidence_pack=_pack([_item()]),
    )
    assert result["accepted_evidence_item_digests"] == ["evidence-digest-1"]


def test_compact_response_receipt_binds_to_cell_without_candidate_text() -> None:
    pack = _pack([_item()])
    responses = compile_dynamic_evidence_responses(
        policy=_json(POLICY),
        controlled_plan=_controlled([_candidate("SOURCE::DELL::1")]),
        evidence_pack=pack,
    )
    base = {
        "schema_version": "fin_ia_current_research_input_v1_1",
        "case_identity": {"case_key": "DELL"},
        "evidence_cards": [
            {
                "evidence_item_digest": "evidence-digest-1",
                "evidence_ref": "EV::REVIEWED1",
            },
            {
                "evidence_item_digest": "evidence-digest-not-returned",
                "evidence_ref": "EV::NOT-RETURNED",
            },
        ],
        "cells": [
            {
                "cell_id": "CELL::value_capture",
                "primary_slot_id": "pricing_mix_value_capture",
                "supplemental_context_slot_ids": [],
                "allowed_evidence_refs": [
                    "EV::REVIEWED1",
                    "EV::NOT-RETURNED",
                ],
                "graph_context_pack": {
                    "schema_version": "fin_ia_graph_context_pack_v1_0",
                    "cell_id": "CELL::value_capture",
                    "case_key": "DELL",
                    "nodes": [],
                    "edges": [
                        {
                            "graph_edge_ref": "GRAPH::CROSS-REQUEST",
                            "evidence_refs": [
                                "EV::REVIEWED1",
                                "EV::NOT-RETURNED",
                            ],
                        }
                    ],
                    "authority": {},
                    "graph_context_digest": "old-graph-digest",
                },
                "context_consumption_contract": {
                    "minimum_method_step_refs": 0,
                    "minimum_graph_edge_refs": 1,
                },
            }
        ],
        "known_boundary": "base",
        "research_input_digest": "base-digest",
    }
    dynamic = bind_dynamic_evidence_responses_to_research_input(
        research_input=base,
        evidence_responses=responses,
    )
    card = dynamic["dynamic_evidence_response_cards"][0]
    assert card["accepted_evidence_refs"] == ["EV::REVIEWED1"]
    assert "model_text" not in json.dumps(card)
    assert dynamic["cells"][0]["allowed_evidence_response_refs"] == [
        card["evidence_response_ref"]
    ]
    assert dynamic["cells"][0]["allowed_evidence_refs"] == [
        "EV::REVIEWED1"
    ]
    assert dynamic["cells"][0]["graph_context_pack"]["edges"] == []
    assert dynamic["cells"][0]["context_consumption_contract"][
        "minimum_graph_edge_refs"
    ] == 0


def test_reviewed_item_may_be_omitted_only_by_receipted_compact_view() -> None:
    second = _item(
        digest="evidence-digest-2",
        source_id="SOURCE::DELL::2",
        source_content_digest="source-text-digest-2",
    )
    responses = compile_dynamic_evidence_responses(
        policy=_json(POLICY),
        controlled_plan=_controlled(
            [
                _candidate("SOURCE::DELL::1"),
                _candidate(
                    "SOURCE::DELL::2",
                    source_content_digest="source-text-digest-2",
                ),
            ]
        ),
        evidence_pack=_pack([_item(), second]),
    )
    base = {
        "schema_version": "fin_ia_current_research_input_v1_1",
        "case_identity": {"case_key": "DELL"},
        "evidence_cards": [
            {
                "evidence_item_digest": "evidence-digest-1",
                "evidence_ref": "EV::REVIEWED1",
            }
        ],
        "cells": [
            {
                "cell_id": "CELL::value_capture",
                "primary_slot_id": "pricing_mix_value_capture",
                "supplemental_context_slot_ids": [],
                "allowed_evidence_refs": ["EV::REVIEWED1"],
            }
        ],
        "input_selection_summary": {
            "reviewed_pack_evidence_count": 2,
            "model_visible_evidence_count": 1,
            "cell_view_evidence_omission_count": 1,
        },
        "known_boundary": "base",
        "research_input_digest": "base-digest",
    }

    dynamic = bind_dynamic_evidence_responses_to_research_input(
        research_input=base,
        evidence_responses=responses,
    )
    card = dynamic["dynamic_evidence_response_cards"][0]
    assert card["accepted_reviewed_evidence_count"] == 2
    assert card["accepted_evidence_refs"] == ["EV::REVIEWED1"]
    assert card["reviewed_but_not_model_visible_count"] == 1
    assert dynamic["dynamic_truth_spine_contract"][
        "reviewed_but_not_model_visible_count"
    ] == 1

    invalid = deepcopy(base)
    invalid["input_selection_summary"]["reviewed_pack_evidence_count"] = 3
    with pytest.raises(DynamicTruthSpineError) as exc:
        bind_dynamic_evidence_responses_to_research_input(
            research_input=invalid,
            evidence_responses=responses,
        )
    assert str(exc.value) == (
        "dynamic_truth_spine_response_evidence_not_in_dynamic_input"
    )
    assert dynamic["dynamic_truth_spine_contract"]["candidate_promotions"] == 0
    assert dynamic["dynamic_truth_spine_contract"][
        "cell_evidence_is_request_scoped"
    ] is True


def test_dynamic_claim_policy_only_removes_unavailable_authority() -> None:
    pack = _pack([_item()])
    responses = compile_dynamic_evidence_responses(
        policy=_json(POLICY),
        controlled_plan=_controlled([_candidate("SOURCE::DELL::1")]),
        evidence_pack=pack,
    )
    template = _json(CLAIM_TEMPLATE)
    management_ref = template["evidence_bindings"][
        "management_assertion_evidence_refs"
    ][0]
    base = {
        "schema_version": "fin_ia_current_research_input_v1_1",
        "case_identity": {"case_key": "DELL"},
        "evidence_cards": [
            {
                "evidence_item_digest": "evidence-digest-1",
                "evidence_ref": management_ref,
            }
        ],
        "cells": [
            {
                "cell_id": "CELL::value_capture",
                "primary_slot_id": "pricing_mix_value_capture",
                "supplemental_context_slot_ids": [],
                "allowed_evidence_refs": [management_ref],
                "allowed_numeric_refs": ["NUM::CURRENT"],
                "allowed_numeric_relation_refs": [],
                "visible_gap_refs": list(template["bridge_gap_refs"]),
            }
        ],
        "model_output_contract": {
            "payload_schema_version": "fin_ia_current_research_judgment_payload_v1_2",
            "model_owned_cell_fields": [],
            "harness_injected_cell_fields": [],
        },
        "known_boundary": "base",
        "research_input_digest": "base-digest",
    }
    dynamic = bind_dynamic_evidence_responses_to_research_input(
        research_input=base,
        evidence_responses=responses,
    )
    policy = compile_dynamic_claim_authority_policy(
        research_input=dynamic,
        template_policy=template,
    )
    bridges = {
        row["causal_bridge_authority"] for row in policy["allowed_combinations"]
    }
    assert bridges == {
        "same_scope_observation_only",
        "management_assertion_only",
        "multi_driver_context_only",
        "bridge_unavailable",
    }
    assert policy["authority"]["candidate_promotion_forbidden"] is True

    compiled = compile_claim_authority_research_input(
        dynamic,
        policy=policy,
    )
    assert compiled["schema_version"] == (
        "fin_ia_dynamic_current_research_input_v1_1"
    )
    assert compiled["claim_authority_contract"]["dynamic_retrieval_executed"] is True
    assert compiled["claim_authority_contract"]["candidate_promotions"] == 0

    missing = deepcopy(dynamic)
    missing.pop("research_input_digest")
    missing["cells"][0]["allowed_evidence_refs"] = []
    missing["evidence_cards"] = []
    missing["research_input_digest"] = canonical_digest(missing)
    narrowed = compile_dynamic_claim_authority_policy(
        research_input=missing,
        template_policy=template,
    )
    assert {
        row["causal_bridge_authority"]
        for row in narrowed["allowed_combinations"]
    } == {"same_scope_observation_only", "bridge_unavailable"}


def test_dynamic_claim_surface_removes_missing_source_and_keeps_safe_abstention(
) -> None:
    pack = _pack([_item()])
    responses = compile_dynamic_evidence_responses(
        policy=_json(POLICY),
        controlled_plan=_controlled([]),
        evidence_pack=pack,
    )
    claim_template = _json(CLAIM_TEMPLATE)
    surface_template = _json(CLAIM_SURFACE_TEMPLATE)
    base = {
        "schema_version": "fin_ia_current_research_input_v1_1",
        "case_identity": {"case_key": "DELL"},
        "evidence_cards": [],
        "cells": [
            {
                "cell_id": "CELL::value_capture",
                "primary_slot_id": "pricing_mix_value_capture",
                "supplemental_context_slot_ids": [],
                "allowed_evidence_refs": [],
                "allowed_numeric_refs": ["NUM::CURRENT"],
                "allowed_numeric_relation_refs": ["REL::B60164179DFFDF5A"],
                "visible_gap_refs": list(claim_template["bridge_gap_refs"]),
            }
        ],
        "model_output_contract": {
            "payload_schema_version": (
                "fin_ia_current_research_judgment_payload_v1_2"
            ),
            "model_owned_cell_fields": [],
            "harness_injected_cell_fields": [],
        },
        "known_boundary": "base",
        "research_input_digest": "base-digest",
    }
    dynamic = bind_dynamic_evidence_responses_to_research_input(
        research_input=base,
        evidence_responses=responses,
    )
    claim_policy = compile_dynamic_claim_authority_policy(
        research_input=dynamic,
        template_policy=claim_template,
    )
    claim_input = compile_claim_authority_research_input(
        dynamic,
        policy=claim_policy,
    )
    surface_policy = compile_dynamic_claim_surface_policy(
        claim_authority_input=claim_input,
        template_policy=surface_template,
    )

    relations = {
        row["claim_relation_ref"]: row
        for row in surface_policy["allowed_structured_claim_combinations"]
    }
    assert set(relations) == {
        "CR::DELL::COMPANY_MARGIN_OBSERVATION",
        "CR::DELL::PROFIT_BRIDGE_GAP",
    }
    assert "thesis_atom" not in relations[
        "CR::DELL::COMPANY_MARGIN_OBSERVATION"
    ]["allowed_atom_fields"]
    assert "thesis_atom" in relations[
        "CR::DELL::PROFIT_BRIDGE_GAP"
    ]["allowed_atom_fields"]
    assert relations["CR::DELL::PROFIT_BRIDGE_GAP"][
        "allowed_inference_authorities"
    ] == ["not_inferable"]
    assert relations["CR::DELL::PROFIT_BRIDGE_GAP"][
        "allowed_judgment_statuses"
    ] == ["insufficient_evidence"]
    assert surface_policy["source_bound_qualitative_facts"] == []
    assert surface_policy["authority"]["gap_only_thesis_may_abstain"] is True

    compiled = compile_claim_surface_authority_research_input(
        claim_input,
        policy=surface_policy,
    )
    assert compiled["schema_version"] == (
        "fin_ia_dynamic_current_research_input_v1_2"
    )
    assert compiled["claim_surface_authority_contract"][
        "dynamic_retrieval_executed"
    ] is True
    assert compiled["claim_surface_authority_contract"][
        "fixed_pack_unit_test_only"
    ] is False
    assert compiled["claim_surface_authority_contract"][
        "candidate_promotions"
    ] == 0
    assert set(
        compiled["model_output_contract"]["allowed_claim_relation_refs"]
    ) == set(relations)


def test_pack_binding_and_case_mutations_fail_closed() -> None:
    pack = _pack([_item()])
    result = compile_dynamic_evidence_responses(
        policy=_json(POLICY),
        controlled_plan=_controlled([_candidate("SOURCE::DELL::1")]),
        evidence_pack=pack,
    )
    drift = deepcopy(pack)
    drift["artifact_digest"] = "different-artifact"
    with pytest.raises(DynamicTruthSpineError) as exc:
        compile_dynamic_reviewed_pack_view(
            evidence_pack=drift,
            evidence_responses=result,
        )
    assert str(exc.value) == "dynamic_truth_spine_pack_binding_drift"

    cross_case = deepcopy(_controlled([_candidate("SOURCE::DELL::1")]))
    cross_case["objective"]["case_key"] = "MU"
    with pytest.raises(DynamicTruthSpineError) as exc:
        compile_dynamic_evidence_responses(
            policy=_json(POLICY),
            controlled_plan=cross_case,
            evidence_pack=pack,
        )
    assert str(exc.value) == "dynamic_truth_spine_case_binding_invalid"
