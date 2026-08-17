from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from apps.workbench.backend.application.research_evidence_pack_service import (
    ResearchEvidencePackPrincipal,
)
from apps.workbench.backend.application.research_retrieval_service import (
    ResearchRetrievalPrincipal,
)
from scripts.research.run_s3_current_research_consumer_zero_call import _services
from scripts.research.run_s3_case_truth_reconciliation_live import (
    assess_pre_registered_targets,
)
from sec_agent.providers import load_chat_completion_profile
from sec_agent.research.case_truth_reconciliation import (
    CASE_TRUTH_MODEL_VIEW_SCHEMA_VERSION,
    CaseTruthReconciliationError,
    aggregate_case_truth_reconciliation_receipts,
    compile_case_truth_reconciliation_analysis_messages,
    compile_case_truth_claim_model_view,
    compile_case_truth_model_view,
    compile_case_truth_packet,
    compile_case_truth_reconciliation_submission,
    compile_case_truth_reconciliation_submission_from_analysis,
    compile_cell_judgment_claim_document,
    compile_claim_document_slice,
    compile_synthesis_claim_document,
    validate_case_truth_packet,
    validate_case_truth_reconciliation,
)
from sec_agent.research.current_consumer import (
    compile_current_research_deliverable,
    compile_current_research_input,
)
from sec_agent.research.five_cell_runtime import (
    FIVE_CELL_TRUTH_RECONCILED_REPORT_SCHEMA_VERSION,
    compile_five_cell_report,
    compile_five_cell_synthesis_analysis_messages,
    validate_five_cell_synthesis,
)
from sec_agent.research.reviewed_evidence_pack import canonical_digest


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def base_research_input() -> dict[str, object]:
    evidence_service, retrieval_service = _services()
    permissions = frozenset({"current_product:read"})
    evidence_pack = evidence_service.get_case(
        "DELL", ResearchEvidencePackPrincipal("current", permissions)
    )
    controlled = retrieval_service.execute_controlled_plan(
        "DELL",
        _json(
            ROOT
            / "configs/research/evals/"
            "fin_ia_0_1_3_s3_dell_minimal_planner_canary_objective_v1_0.json"
        ),
        _json(
            ROOT
            / "tests/fixtures/research/"
            "fin_ia_0_1_3_s3_dell_planner_r1_atoms_v1_0.json"
        ),
        ResearchRetrievalPrincipal("current", permissions),
    )
    return compile_current_research_input(
        policy=_json(
            ROOT
            / "configs/research/"
            "fin_ia_0_1_3_s3_current_research_consumer_policy_v1_3.json"
        ),
        evidence_pack=evidence_pack,
        controlled_plan=controlled,
    )


@pytest.fixture(scope="module")
def research_input(base_research_input: dict[str, object]) -> dict[str, object]:
    value = deepcopy(base_research_input)
    value_cell = next(
        row for row in value["cells"] if row["cell_id"] == "CELL::value_capture"
    )
    bridge_gaps = [
        row["gap_ref"]
        for row in value["residual_gap_cards"]
        if row["slot_id"] == "pricing_mix_value_capture"
    ]
    value_cell["claim_relation_card"] = {
        "allowed_combinations": [
            {
                "causal_bridge_authority": "bridge_unavailable",
                "claim_relation": "bridge_not_established",
                "claim_relation_ref": "CR::GENERIC::PROFIT_BRIDGE_GAP",
                "claim_subject": "current_case_product",
                "claim_outcome": "company_or_segment_profit_bridge",
                "required_gap_refs": bridge_gaps,
            }
        ]
    }
    counter = next(
        row for row in value["cells"] if row["cell_id"] == "CELL::counterevidence"
    )
    counter["allowed_evidence_refs"] = ["EV::734A9C177164E08E"]
    return value


@pytest.fixture(scope="module")
def judgment_and_deliverable(
    base_research_input: dict[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    payload = _json(
        ROOT
        / "tests/fixtures/research/"
        "fin_ia_0_1_3_s3_dell_current_research_consumer_fake_payload_v1_3.json"
    )
    deliverable = compile_current_research_deliverable(
        research_input=base_research_input,
        judgment_output=payload,
    )
    judgment = {
        "schema_version": "fin_ia_current_research_judgment_v1_2",
        "research_input_digest": base_research_input["research_input_digest"],
        "cells": [
            {
                key: deepcopy(value)
                for key, value in row.items()
                if key
                not in {
                    "title_zh",
                    "evidence_uses_rendered",
                    "numeric_facts",
                    "numeric_relations",
                    "remaining_gaps",
                }
            }
            for row in deliverable["cells"]
        ],
        "judgment_output_digest": deliverable["judgment_output_digest"],
    }
    return judgment, deliverable


def _eligible_reconciliation(
    packet: dict[str, object], document: dict[str, object]
) -> dict[str, object]:
    matrix = {row["cell_id"]: row for row in packet["cell_visibility_matrix"]}
    first_case_presence = packet["presence_catalog"][0]["truth_alias"]
    surfaces = []
    for row in document["claim_surfaces"]:
        if row["truth_assertion_required"] is False:
            status = "no_case_truth_claim"
            assertions = []
        elif row["cell_id"] is None:
            status = "claims_mapped"
            assertions = [
                {
                    "truth_alias": first_case_presence,
                    "asserted_state": "present_in_current_case",
                }
            ]
        else:
            visible = matrix[row["cell_id"]]["visible_presence_aliases"]
            assert visible
            status = "claims_mapped"
            assertions = [
                {
                    "truth_alias": visible[0],
                    "asserted_state": "present_in_current_case",
                }
            ]
        surfaces.append(
            {
                "claim_surface_id": row["claim_surface_id"],
                "claim_surface_digest": row["claim_surface_digest"],
                "coverage_status": status,
                "assertions": assertions,
            }
        )
    return {"surface_assertions": surfaces}


def _set_assertions(
    payload: dict[str, object],
    surface_id: str,
    assertions: list[dict[str, str]],
) -> None:
    row = next(
        item
        for item in payload["surface_assertions"]
        if item["claim_surface_id"] == surface_id
    )
    row["coverage_status"] = "claims_mapped"
    row["assertions"] = assertions


def _synthesis_payload(judgment: dict[str, object]) -> dict[str, object]:
    cells = judgment["cells"]
    evidence = []
    numeric = []
    relations = []
    gaps = []
    for row in cells:
        evidence.extend(use["evidence_ref"] for use in row["evidence_uses"])
        numeric.extend(row["numeric_refs"])
        relations.extend(row["numeric_relation_refs"])
        gaps.extend(row["remaining_gap_refs"])
    return {
        "overall_judgment": "mixed",
        "confidence_basis": "mixed_source_strength",
        "inference_authority": "bounded_inference",
        "executive_thesis": "需求获得直接支持，但利润与现金转化仍缺少产品层桥接。",
        "cross_cell_mechanism": "需求与经营规模提供转化条件，产品组合和营运资金限制价值沉淀。",
        "strongest_counterargument": "订单可能包含提前采购，集团改善也可能来自其他业务。",
        "key_cell_ids": [row["cell_id"] for row in cells],
        "cell_links": [
            {
                "from_cell_id": "CELL::demand_quality",
                "to_cell_id": "CELL::operating_performance",
                "relation": "supports",
                "explanation": "订单为经营规模提供需求背景，但不能单独证明利润贡献。",
            },
            {
                "from_cell_id": "CELL::cash_conversion",
                "to_cell_id": "CELL::value_capture",
                "relation": "limits",
                "explanation": "集团现金改善不能替代产品收入到利润和现金的直接桥接。",
            },
        ],
        "evidence_refs": list(dict.fromkeys(evidence))[:6],
        "numeric_refs": list(dict.fromkeys(numeric))[:6],
        "numeric_relation_refs": list(dict.fromkeys(relations))[:4],
        "remaining_gap_refs": list(dict.fromkeys(gaps))[:5],
        "what_would_change": {
            "observable": "产品收入、利润与营运资金形成可复算且连续的桥接",
            "direction": "resolve_gap",
            "time_horizon": "后续连续披露期",
            "evidence_route": "公司申报材料、业绩说明与可复算产品财务桥",
            "threshold_numeric_ref": "",
        },
    }


def test_packet_separates_case_presence_cell_visibility_and_typed_absence(
    research_input: dict[str, object],
) -> None:
    packet = compile_case_truth_packet(research_input)
    validate_case_truth_packet(packet, research_input=research_input)
    presence = {row["truth_alias"]: row for row in packet["presence_catalog"]}
    gaps = {row["truth_alias"]: row for row in packet["typed_gap_catalog"]}
    matrix = {row["cell_id"]: row for row in packet["cell_visibility_matrix"]}

    revenue = (
        "TRUTH::FACET::operating_performance::"
        "accelerated_compute_or_ai_infrastructure_revenue"
    )
    orders = "TRUTH::FACET::demand_volume_quality::ai_orders"
    backlog = "TRUTH::FACET::demand_volume_quality::ai_backlog"
    pull_forward = (
        "TRUTH::FACET::demand_volume_quality::pull_forward_or_digestion"
    )
    asp = "TRUTH::FACET::pricing_mix_value_capture::price_or_asp"

    assert revenue in presence
    assert orders in presence
    assert backlog in presence
    assert revenue in matrix["CELL::operating_performance"][
        "visible_presence_aliases"
    ]
    assert backlog in matrix["CELL::counterevidence"][
        "not_visible_presence_aliases"
    ]
    assert gaps[pull_forward]["coverage_state"] == "present_with_typed_gap"
    assert gaps[pull_forward]["case_absence_authorized"] is False
    assert gaps[asp]["coverage_state"] == "typed_gap_only"
    assert gaps[asp]["case_absence_authorized"] is True
    assert packet["typed_bridge_boundary_catalog"][0]["claim_relation_ref"] == (
        "CR::GENERIC::PROFIT_BRIDGE_GAP"
    )


def test_model_view_is_compact_but_remains_bound_to_full_authority(
    research_input: dict[str, object],
) -> None:
    packet = compile_case_truth_packet(research_input)
    model_view = compile_case_truth_model_view(packet)

    assert model_view["schema_version"] == CASE_TRUTH_MODEL_VIEW_SCHEMA_VERSION
    assert model_view["case_truth_packet_digest"] == packet[
        "case_truth_packet_digest"
    ]
    assert all(
        "not_visible_presence_aliases" not in row
        for row in model_view["cell_visibility_matrix"]
    )
    assert any(
        row["not_visible_presence_aliases"]
        for row in packet["cell_visibility_matrix"]
    )
    assert len(
        json.dumps(model_view, ensure_ascii=False, sort_keys=True)
    ) < len(json.dumps(packet, ensure_ascii=False, sort_keys=True))


def test_semantic_analysis_profile_is_bounded_visible_classification() -> None:
    profile = load_chat_completion_profile(
        _json(
            ROOT
            / "configs/providers/"
            "fin_ia_0_1_3_deepseek_v4_pro_ga_"
            "semantic_reconciliation_analysis_non_thinking_profile_v1_0.json"
        )
    )
    assert profile.provider_id == "deepseek"
    assert profile.model == "deepseek-v4-pro"
    assert profile.base_url == "https://api.deepseek.com"
    assert dict(profile.request_defaults) == {
        "max_tokens": 4000,
        "stream": False,
        "thinking": {"type": "disabled"},
    }
    assert profile.authority["retry_count"] == 0

    submission_profile = load_chat_completion_profile(
        _json(
            ROOT
            / "configs/providers/"
            "fin_ia_0_1_3_deepseek_v4_pro_ga_"
            "case_truth_submission_non_thinking_strict_beta_profile_v1_0.json"
        )
    )
    assert submission_profile.base_url == "https://api.deepseek.com/beta"
    assert dict(submission_profile.request_defaults) == {
        "max_tokens": 4000,
        "stream": False,
        "thinking": {"type": "disabled"},
    }
    assert submission_profile.authority["retry_count"] == 0


def test_r7_false_absence_bundle_is_blocked_but_real_profit_gap_is_legal(
    research_input: dict[str, object],
    judgment_and_deliverable: tuple[dict[str, object], dict[str, object]],
) -> None:
    judgment, _ = judgment_and_deliverable
    replay = deepcopy(judgment)
    operating = next(
        row
        for row in replay["cells"]
        if row["cell_id"] == "CELL::operating_performance"
    )
    counter = next(
        row
        for row in replay["cells"]
        if row["cell_id"] == "CELL::counterevidence"
    )
    operating["thesis_atom"] = (
        "The AI narrative lacks sourced quarter-discrete AI revenue."
    )
    counter["thesis_atom"] = (
        "The issuer did not separately provide AI orders, backlog or a "
        "product-to-company profit bridge."
    )
    replay["judgment_output_digest"] = canonical_digest(replay["cells"])
    packet = compile_case_truth_packet(research_input)
    document = compile_cell_judgment_claim_document(replay)
    payload = _eligible_reconciliation(packet, document)
    _set_assertions(
        payload,
        "CELL::operating_performance::thesis_atom",
        [
            {
                "truth_alias": (
                    "TRUTH::FACET::operating_performance::"
                    "accelerated_compute_or_ai_infrastructure_revenue"
                ),
                "asserted_state": "absent_from_current_case",
            }
        ],
    )
    _set_assertions(
        payload,
        "CELL::counterevidence::thesis_atom",
        [
            {
                "truth_alias": "TRUTH::FACET::demand_volume_quality::ai_orders",
                "asserted_state": "absent_from_current_case",
            },
            {
                "truth_alias": "TRUTH::FACET::demand_volume_quality::ai_backlog",
                "asserted_state": "absent_from_current_case",
            },
            {
                "truth_alias": (
                    "TRUTH::BRIDGE::CR::GENERIC::PROFIT_BRIDGE_GAP"
                ),
                "asserted_state": "absent_from_current_case",
            },
        ],
    )
    receipt = validate_case_truth_reconciliation(
        payload,
        case_truth_packet=packet,
        claim_document=document,
    )

    assert receipt["downstream_eligible"] is False
    assert [row["finding_code"] for row in receipt["findings"]] == [
        "asserted_absent_but_present_in_case",
        "asserted_absent_but_present_in_case",
        "asserted_absent_but_present_in_case",
    ]
    assert not any(
        row["truth_alias"].endswith("PROFIT_BRIDGE_GAP")
        for row in receipt["findings"]
    )


def test_presence_and_residual_gap_can_coexist_without_false_absence(
    research_input: dict[str, object],
    judgment_and_deliverable: tuple[dict[str, object], dict[str, object]],
) -> None:
    judgment, _ = judgment_and_deliverable
    packet = compile_case_truth_packet(research_input)
    document = compile_cell_judgment_claim_document(judgment)
    payload = _eligible_reconciliation(packet, document)
    alias = "TRUTH::FACET::demand_volume_quality::pull_forward_or_digestion"
    _set_assertions(
        payload,
        "CELL::demand_quality::counterargument_atom",
        [
            {
                "truth_alias": alias,
                "asserted_state": "unresolved_or_partially_covered",
            }
        ],
    )
    receipt = validate_case_truth_reconciliation(
        payload,
        case_truth_packet=packet,
        claim_document=document,
    )
    assert receipt["downstream_eligible"] is True

    _set_assertions(
        payload,
        "CELL::demand_quality::counterargument_atom",
        [{"truth_alias": alias, "asserted_state": "absent_from_current_case"}],
    )
    blocked = validate_case_truth_reconciliation(
        payload,
        case_truth_packet=packet,
        claim_document=document,
    )
    assert blocked["findings"][0]["finding_code"] == (
        "asserted_absent_but_present_in_case"
    )

    hidden_backlog = "TRUTH::FACET::demand_volume_quality::ai_backlog"
    hidden_payload = _eligible_reconciliation(packet, document)
    _set_assertions(
        hidden_payload,
        "CELL::counterevidence::mechanism_atom",
        [
            {
                "truth_alias": hidden_backlog,
                "asserted_state": "present_in_current_case",
            }
        ],
    )
    hidden = validate_case_truth_reconciliation(
        hidden_payload,
        case_truth_packet=packet,
        claim_document=document,
    )
    assert hidden["findings"][0]["finding_code"] == (
        "asserted_present_outside_cell_visibility"
    )


def test_reconciler_contract_is_exhaustive_and_fails_closed_on_drift(
    research_input: dict[str, object],
    judgment_and_deliverable: tuple[dict[str, object], dict[str, object]],
) -> None:
    judgment, _ = judgment_and_deliverable
    packet = compile_case_truth_packet(research_input)
    document = compile_cell_judgment_claim_document(judgment)
    messages, tool = compile_case_truth_reconciliation_submission(
        case_truth_packet=packet,
        claim_document=document,
    )
    assert len(messages) == 2
    assert tool["function"]["strict"] is True
    assertion_schema = tool["function"]["parameters"]["properties"][
        "surface_assertions"
    ]["items"]["properties"]["assertions"]
    assert assertion_schema["maxItems"] == 12
    assert set(assertion_schema["items"]["properties"]) == {
        "truth_alias",
        "claim_polarity",
    }
    assert tool["function"]["parameters"]["properties"][
        "surface_assertions"
    ]["minItems"] == 15

    omitted = {
        "surface_assertions": [
            {
                "claim_surface_id": row["claim_surface_id"],
                "claim_surface_digest": row["claim_surface_digest"],
                "coverage_status": "no_case_truth_claim",
                "assertions": [],
            }
            for row in document["claim_surfaces"]
        ]
    }
    omitted_receipt = validate_case_truth_reconciliation(
        omitted,
        case_truth_packet=packet,
        claim_document=document,
    )
    assert omitted_receipt["downstream_eligible"] is False
    assert {row["finding_code"] for row in omitted_receipt["findings"]} == {
        "required_material_surface_unmapped"
    }

    missing = _eligible_reconciliation(packet, document)
    missing["surface_assertions"].pop()
    with pytest.raises(CaseTruthReconciliationError) as exc:
        validate_case_truth_reconciliation(
            missing,
            case_truth_packet=packet,
            claim_document=document,
        )
    assert exc.value.code == "case_truth_reconciliation_surface_coverage_invalid"

    forged = deepcopy(packet)
    forged["case_identity"]["case_key"] = "MU"
    with pytest.raises(CaseTruthReconciliationError) as exc:
        validate_case_truth_packet(forged, research_input=research_input)
    assert exc.value.code == "case_truth_packet_binding_drift"


def test_claim_scoped_view_and_claim_polarity_separate_text_from_truth(
    research_input: dict[str, object],
    judgment_and_deliverable: tuple[dict[str, object], dict[str, object]],
) -> None:
    judgment, _ = judgment_and_deliverable
    packet = compile_case_truth_packet(research_input)
    parent = compile_cell_judgment_claim_document(judgment)
    cell_id = "CELL::counterevidence"
    document = compile_claim_document_slice(
        parent,
        claim_surface_ids=[
            row["claim_surface_id"]
            for row in parent["claim_surfaces"]
            if row["cell_id"] == cell_id
        ],
    )
    view = compile_case_truth_claim_model_view(packet, document)
    assert view["scope_mode"] == "single_cell_claim_slice"
    assert view["claim_cell_id"] == cell_id
    assert "cell_visibility_matrix" not in view
    assert "whole_case_truth_view" not in view
    assert {
        row["truth_alias"] for row in view["case_only_outside_cell_alias_index"]
    }.issuperset(
        {
            "TRUTH::FACET::demand_volume_quality::ai_orders",
            "TRUTH::FACET::demand_volume_quality::ai_backlog",
        }
    )

    cross_alias = next(
        alias
        for alias in view["cross_case_context_aliases_visible_in_claim_cell"]
    )
    payload = _eligible_reconciliation(packet, document)
    _set_assertions(
        payload,
        f"{cell_id}::mechanism_atom",
        [
            {
                "truth_alias": cross_alias,
                "claim_polarity": "claim_uses_cross_case_context",
            }
        ],
    )
    receipt = validate_case_truth_reconciliation(
        payload,
        case_truth_packet=packet,
        claim_document=document,
    )
    assert not any(
        row.get("truth_alias") == cross_alias for row in receipt["findings"]
    )

    subject_alias = next(
        alias
        for row in packet["presence_catalog"]
        if packet["case_identity"]["subject_ticker"] in row.get(
            "owner_tickers", []
        )
        for alias in [row["truth_alias"]]
        if alias
        in next(
            matrix["visible_presence_aliases"]
            for matrix in packet["cell_visibility_matrix"]
            if matrix["cell_id"] == cell_id
        )
    )
    _set_assertions(
        payload,
        f"{cell_id}::mechanism_atom",
        [
            {
                "truth_alias": subject_alias,
                "claim_polarity": "claim_uses_cross_case_context",
            }
        ],
    )
    blocked = validate_case_truth_reconciliation(
        payload,
        case_truth_packet=packet,
        claim_document=document,
    )
    assert any(
        row["finding_code"] == "claimed_cross_case_context_for_subject_fact"
        for row in blocked["findings"]
    )


def test_cell_slices_separate_analysis_submission_and_aggregate_exhaustively(
    research_input: dict[str, object],
    judgment_and_deliverable: tuple[dict[str, object], dict[str, object]],
) -> None:
    judgment, _ = judgment_and_deliverable
    packet = compile_case_truth_packet(research_input)
    parent = compile_cell_judgment_claim_document(judgment)
    direct_messages, _ = compile_case_truth_reconciliation_submission(
        case_truth_packet=packet,
        claim_document=parent,
    )
    direct_chars = len(direct_messages[1]["content"])
    revenue_alias = (
        "TRUTH::FACET::operating_performance::"
        "accelerated_compute_or_ai_infrastructure_revenue"
    )
    order_alias = "TRUTH::FACET::demand_volume_quality::ai_orders"
    backlog_alias = "TRUTH::FACET::demand_volume_quality::ai_backlog"
    bridge_alias = "TRUTH::BRIDGE::CR::GENERIC::PROFIT_BRIDGE_GAP"
    documents = []
    receipts = []
    for cell_id in [row["cell_id"] for row in judgment["cells"]]:
        surface_ids = [
            row["claim_surface_id"]
            for row in parent["claim_surfaces"]
            if row["cell_id"] == cell_id
        ]
        document = compile_claim_document_slice(
            parent,
            claim_surface_ids=surface_ids,
        )
        assert document["parent_claim_document_digest"] == parent[
            "claim_document_digest"
        ]
        assert len(document["claim_surfaces"]) == 3
        analysis_messages = compile_case_truth_reconciliation_analysis_messages(
            case_truth_packet=packet,
            claim_document=document,
        )
        analysis_view = json.loads(analysis_messages[1]["content"])
        assert len(analysis_view["claim_document"]["claim_surfaces"]) == 3
        assert analysis_view["task"] == (
            "analyze_case_truth_claim_slice_without_tool_submission"
        )
        submission_messages, tool = (
            compile_case_truth_reconciliation_submission_from_analysis(
                case_truth_packet=packet,
                claim_document=document,
                analysis_draft=(
                    "Prepared mapping for the three supplied surfaces; every "
                    "alias and state remains bound to the immutable truth view."
                ),
            )
        )
        submission_view = json.loads(submission_messages[1]["content"])
        assert "case_truth_packet" not in submission_view
        assert submission_view["case_truth_packet_digest"] == packet[
            "case_truth_packet_digest"
        ]
        assert len(submission_messages[1]["content"]) < direct_chars
        items = tool["function"]["parameters"]["properties"][
            "surface_assertions"
        ]
        assert items["minItems"] == items["maxItems"] == 3

        payload = _eligible_reconciliation(packet, document)
        if cell_id == "CELL::operating_performance":
            _set_assertions(
                payload,
                f"{cell_id}::thesis_atom",
                [
                    {
                        "truth_alias": revenue_alias,
                        "asserted_state": "absent_from_current_case",
                    }
                ],
            )
        elif cell_id == "CELL::counterevidence":
            _set_assertions(
                payload,
                f"{cell_id}::thesis_atom",
                [
                    {
                        "truth_alias": order_alias,
                        "asserted_state": "absent_from_current_case",
                    },
                    {
                        "truth_alias": backlog_alias,
                        "asserted_state": "absent_from_current_case",
                    },
                    {
                        "truth_alias": bridge_alias,
                        "asserted_state": "absent_from_current_case",
                    },
                ],
            )
        receipts.append(
            validate_case_truth_reconciliation(
                payload,
                case_truth_packet=packet,
                claim_document=document,
            )
        )
        documents.append(document)

    aggregate = aggregate_case_truth_reconciliation_receipts(
        case_truth_packet=packet,
        parent_claim_document=parent,
        slice_claim_documents=documents,
        slice_receipts=receipts,
    )
    assert aggregate["claim_surfaces_checked"] == 15
    assert aggregate["surface_assertion_count"] == 17
    assert aggregate["downstream_eligible"] is False
    assert [row["finding_code"] for row in aggregate["findings"]] == [
        "asserted_absent_but_present_in_case",
        "asserted_absent_but_present_in_case",
        "asserted_absent_but_present_in_case",
    ]
    assert not any(
        row["truth_alias"] == bridge_alias for row in aggregate["findings"]
    )

    with pytest.raises(CaseTruthReconciliationError) as exc:
        aggregate_case_truth_reconciliation_receipts(
            case_truth_packet=packet,
            parent_claim_document=parent,
            slice_claim_documents=documents[:-1],
            slice_receipts=receipts[:-1],
        )
    assert exc.value.code == (
        "case_truth_receipt_aggregation_surface_coverage_invalid"
    )

    with pytest.raises(CaseTruthReconciliationError) as exc:
        aggregate_case_truth_reconciliation_receipts(
            case_truth_packet=packet,
            parent_claim_document=parent,
            slice_claim_documents=documents + [documents[0]],
            slice_receipts=receipts + [receipts[0]],
        )
    assert exc.value.code == "case_truth_receipt_aggregation_surface_overlap"


def test_truth_reconciliation_gates_synthesis_and_final_report(
    research_input: dict[str, object],
    judgment_and_deliverable: tuple[dict[str, object], dict[str, object]],
) -> None:
    judgment, deliverable = judgment_and_deliverable
    packet = compile_case_truth_packet(research_input)
    cell_document = compile_cell_judgment_claim_document(judgment)
    cell_receipt = validate_case_truth_reconciliation(
        _eligible_reconciliation(packet, cell_document),
        case_truth_packet=packet,
        claim_document=cell_document,
    )
    analysis = compile_five_cell_synthesis_analysis_messages(
        research_input=research_input,
        judgment_output=judgment,
        structured_deliverable=deliverable,
        case_truth_packet=packet,
        cell_truth_reconciliation=cell_receipt,
    )
    assert json.loads(analysis[1]["content"])["schema_version"] == (
        "fin_ia_five_cell_synthesis_input_v1_1"
    )
    truth_view = json.loads(analysis[1]["content"])["case_truth_packet"]
    assert truth_view["schema_version"] == CASE_TRUTH_MODEL_VIEW_SCHEMA_VERSION
    assert all(
        "not_visible_presence_aliases" not in row
        for row in truth_view["cell_visibility_matrix"]
    )

    synthesis = validate_five_cell_synthesis(
        _synthesis_payload(judgment),
        research_input=research_input,
        judgment_output=judgment,
    )
    synthesis_document = compile_synthesis_claim_document(synthesis)
    synthesis_receipt = validate_case_truth_reconciliation(
        _eligible_reconciliation(packet, synthesis_document),
        case_truth_packet=packet,
        claim_document=synthesis_document,
    )
    report = compile_five_cell_report(
        research_input=research_input,
        structured_deliverable=deliverable,
        synthesis=synthesis,
        case_truth_packet=packet,
        cell_truth_reconciliation=cell_receipt,
        synthesis_truth_reconciliation=synthesis_receipt,
    )
    assert report["schema_version"] == (
        FIVE_CELL_TRUTH_RECONCILED_REPORT_SCHEMA_VERSION
    )
    assert report["rendering_authority"][
        "case_truth_reconciliation_required_and_passed"
    ] is True

    bad_payload = _eligible_reconciliation(packet, cell_document)
    _set_assertions(
        bad_payload,
        "CELL::operating_performance::thesis_atom",
        [
            {
                "truth_alias": (
                    "TRUTH::FACET::operating_performance::"
                    "accelerated_compute_or_ai_infrastructure_revenue"
                ),
                "asserted_state": "absent_from_current_case",
            }
        ],
    )
    blocked = validate_case_truth_reconciliation(
        bad_payload,
        case_truth_packet=packet,
        claim_document=cell_document,
    )
    with pytest.raises(CaseTruthReconciliationError) as exc:
        compile_five_cell_synthesis_analysis_messages(
            research_input=research_input,
            judgment_output=judgment,
            structured_deliverable=deliverable,
            case_truth_packet=packet,
            cell_truth_reconciliation=blocked,
        )
    assert exc.value.code == "case_truth_reconciliation_not_eligible"


def test_compiler_is_case_generic_and_cross_case_packet_cannot_be_reused() -> None:
    packets = {}
    for case_key in ("MU", "NVDA", "ORCL"):
        research_input = {
            "case_identity": {
                "case_key": case_key,
                "subject_ticker": case_key,
                "research_as_of": "2026-08-17",
            },
            "research_input_digest": f"DIGEST::{case_key}",
            "evidence_cards": [
                {
                    "evidence_ref": f"EV::{case_key}",
                    "evidence_owner_ticker": case_key,
                    "publication_date": "2026-08-01",
                    "source_reporting_period_end": "2026-07-31",
                    "slot_bindings": [
                        {
                            "slot_id": "operating_performance",
                            "facet_ids": ["reported_revenue"],
                            "business_meaning_zh": "当期收入事实",
                            "claim_boundary_zh": "不自动证明利润因果",
                        }
                    ],
                }
            ],
            "numeric_fact_cards": [],
            "numeric_relation_cards": [],
            "residual_gap_cards": [
                {
                    "gap_ref": f"GAP::{case_key}",
                    "slot_id": "pricing_mix_value_capture",
                    "facet_id": "product_profit_bridge",
                    "gap_code": "metric_not_disclosed",
                    "business_reason_zh": "产品利润桥未披露",
                }
            ],
            "cells": [
                {
                    "cell_id": f"CELL::{index}",
                    "allowed_evidence_refs": (
                        [f"EV::{case_key}"] if index == 0 else []
                    ),
                    "allowed_numeric_refs": [],
                    "allowed_numeric_relation_refs": [],
                    "visible_gap_refs": (
                        [f"GAP::{case_key}"] if index == 1 else []
                    ),
                }
                for index in range(5)
            ],
        }
        packets[case_key] = compile_case_truth_packet(research_input)
        assert packets[case_key]["case_identity"]["case_key"] == case_key
        assert not any(
            other in json.dumps(packets[case_key])
            for other in {"MU", "NVDA", "ORCL"} - {case_key}
        )

    mutated_input = {
        **deepcopy(
            {
                "case_identity": {
                    "case_key": "NVDA",
                    "subject_ticker": "NVDA",
                    "research_as_of": "2026-08-17",
                },
                "research_input_digest": "DIGEST::NVDA",
                "evidence_cards": [],
                "numeric_fact_cards": [],
                "numeric_relation_cards": [],
                "residual_gap_cards": [],
                "cells": [],
            }
        )
    }
    with pytest.raises(CaseTruthReconciliationError):
        validate_case_truth_packet(packets["MU"], research_input=mutated_input)


def test_live_target_assessment_requires_false_absences_and_real_gap(
    research_input: dict[str, object],
    judgment_and_deliverable: tuple[dict[str, object], dict[str, object]],
) -> None:
    judgment, _ = judgment_and_deliverable
    packet = compile_case_truth_packet(research_input)
    document = compile_cell_judgment_claim_document(judgment)
    payload = _eligible_reconciliation(packet, document)
    targets = {
        "required_surface_count": 15,
        "required_false_absence_detections": [
            {
                "claim_surface_id": "CELL::operating_performance::thesis_atom",
                "truth_alias": (
                    "TRUTH::FACET::operating_performance::"
                    "accelerated_compute_or_ai_infrastructure_revenue"
                ),
            },
            {
                "claim_surface_id": "CELL::counterevidence::thesis_atom",
                "truth_alias": "TRUTH::FACET::demand_volume_quality::ai_orders",
            },
            {
                "claim_surface_id": "CELL::counterevidence::thesis_atom",
                "truth_alias": "TRUTH::FACET::demand_volume_quality::ai_backlog",
            },
        ],
        "required_legitimate_absence": {
            "claim_surface_id": "CELL::counterevidence::thesis_atom",
            "truth_alias": "TRUTH::BRIDGE::CR::GENERIC::PROFIT_BRIDGE_GAP",
        },
    }
    _set_assertions(
        payload,
        "CELL::operating_performance::thesis_atom",
        [
            {
                "truth_alias": targets["required_false_absence_detections"][0][
                    "truth_alias"
                ],
                "asserted_state": "absent_from_current_case",
            }
        ],
    )
    _set_assertions(
        payload,
        "CELL::counterevidence::thesis_atom",
        [
            {
                "truth_alias": row["truth_alias"],
                "asserted_state": "absent_from_current_case",
            }
            for row in targets["required_false_absence_detections"][1:]
        ]
        + [
            {
                "truth_alias": targets["required_legitimate_absence"][
                    "truth_alias"
                ],
                "asserted_state": "absent_from_current_case",
            }
        ],
    )
    receipt = validate_case_truth_reconciliation(
        payload,
        case_truth_packet=packet,
        claim_document=document,
    )
    assessment = assess_pre_registered_targets(
        arguments=payload,
        receipt=receipt,
        targets=targets,
    )
    assert assessment["automatic_critical_targets_pass"] is True

    payload["surface_assertions"] = [
        row
        for row in payload["surface_assertions"]
        if row["claim_surface_id"]
        != "CELL::cash_conversion::counterargument_atom"
    ]
    assessment = assess_pre_registered_targets(
        arguments=payload,
        receipt=receipt,
        targets=targets,
    )
    assert assessment["automatic_critical_targets_pass"] is False
