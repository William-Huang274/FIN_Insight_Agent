from __future__ import annotations

import ast
from dataclasses import replace
import json
from pathlib import Path
import time

import pytest

from retrieval.dell_report_r14_contracts import TARGET_IDS, load_and_validate_r14_contracts
from retrieval.dell_report_structural_graph_r14 import (
    build_event_argument_graph_r14,
    build_price_attachment_graph_r14,
)
from retrieval.dell_report_target_compiler_r14 import (
    build_target_graph_view_r14,
    compile_target_decisions_r14,
)


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def bundle():
    return load_and_validate_r14_contracts(root=ROOT)


def _compile(text: str, bundle):
    event_graph = build_event_argument_graph_r14(text=text, bundle=bundle)
    price_graph = build_price_attachment_graph_r14(graph=event_graph, bundle=bundle)
    view = build_target_graph_view_r14(
        event_graph=event_graph, price_graph=price_graph
    )
    decisions = compile_target_decisions_r14(
        view=view, topology_contract=bundle.topology
    )
    return event_graph, price_graph, view, decisions


@pytest.mark.parametrize(
    ("target_id", "text"),
    [
        ("DELL-RSQ-03A-TARGET-ASP", "Dell offered PowerEdge at $100."),
        (
            "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH",
            "Dell partnered with Nvidia and Nvidia supplied Dell PowerEdge in 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE",
            "Micron allocated HBM capacity to Dell in 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD",
            "Micron reported HBM utilization at 95% in 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-HBM-SUPPLY",
            "Micron supplied HBM in 2026 and Dell shipped HBM PowerEdge in 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-UNITS",
            "Dell shipped 20 PowerEdge systems in 2026.",
        ),
    ],
)
def test_r14_graph_only_compiler_has_complete_positive_for_each_target(
    bundle, target_id: str, text: str
) -> None:
    _, _, _, decisions = _compile(text, bundle)
    by_id = {row.target_id: row for row in decisions}

    assert tuple(row.target_id for row in decisions) == TARGET_IDS
    assert by_id[target_id].outcome == "C"
    assert not by_id[target_id].missing_roles
    assert by_id[target_id].event_ids


def test_r14_target_graph_view_contains_no_text_or_token_surface(bundle) -> None:
    _, _, view, _ = _compile(
        "Dell offered PowerEdge XE9680 at $15,000.", bundle
    )
    payload = view.as_dict()
    serialized = json.dumps(payload, sort_keys=True)

    forbidden_keys = {
        "raw_text",
        "raw_value",
        "normalized_value",
        "predicate_surface",
        "token_surface",
        "tokens",
    }

    def walk(value):
        if isinstance(value, dict):
            assert forbidden_keys.isdisjoint(value)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(payload)
    assert "Dell offered" not in serialized
    assert "PowerEdge XE9680" not in serialized
    assert "$15,000" not in serialized


def test_r14_compiler_source_cannot_access_sentence_tokens_R13_or_preview() -> None:
    path = ROOT / "src/retrieval/dell_report_target_compiler_r14.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    attributes = {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }

    assert "raw_text" not in attributes
    assert "tokens" not in attributes
    assert "predicate_surface" not in attributes
    assert "normalized_value" not in attributes
    assert "r13" not in source.casefold()
    assert "preview_vector" not in source


def test_r14_compiler_role_deletion_degrades_C_to_P_without_reclassification(
    bundle,
) -> None:
    _, _, view, decisions = _compile(
        "Dell shipped 20 PowerEdge systems in 2026.", bundle
    )
    original = next(
        row for row in decisions if row.target_id == "DELL-RSQ-03A-TARGET-UNITS"
    )
    assert original.outcome == "C"

    quantity_edge = next(
        row
        for row in view.typed_edges
        if row.edge_family == "event_role" and row.edge_type == "quantity"
    )
    mutated = replace(
        view,
        typed_edges=tuple(
            row for row in view.typed_edges if row.edge_id != quantity_edge.edge_id
        ),
    )
    result = compile_target_decisions_r14(
        view=mutated, topology_contract=bundle.topology
    )
    units = next(
        row for row in result if row.target_id == "DELL-RSQ-03A-TARGET-UNITS"
    )
    assert units.outcome == "P"
    assert "physical_server_quantity" in units.missing_roles


def test_r14_compiler_requires_typed_bridge_for_two_event_HBM(bundle) -> None:
    _, _, view, decisions = _compile(
        "Micron supplied HBM in 2026 and Dell shipped HBM PowerEdge in 2026.",
        bundle,
    )
    original = next(
        row for row in decisions if row.target_id == "DELL-RSQ-03A-TARGET-HBM-SUPPLY"
    )
    assert original.outcome == "C"

    mutated = replace(
        view,
        typed_edges=tuple(
            row for row in view.typed_edges if row.edge_type != "typed_target_bridge"
        ),
    )
    result = compile_target_decisions_r14(
        view=mutated, topology_contract=bundle.topology
    )
    hbm = next(
        row for row in result if row.target_id == "DELL-RSQ-03A-TARGET-HBM-SUPPLY"
    )
    assert hbm.outcome == "P"
    assert "directional_Dell_bridge" in hbm.missing_roles


def test_r14_generic_supply_is_not_capacity_release(bundle) -> None:
    event_graph, _, view, decisions = _compile(
        "Micron supplied HBM to Dell in 2026.", bundle
    )
    capacity = next(
        row
        for row in decisions
        if row.target_id == "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE"
    )

    assert any(
        "OPERATOR::SUPPLY" in event.semantic_operator_ids
        for event in event_graph.events
    )
    assert any(
        node.node_type == "predicate"
        and "OPERATOR::SUPPLY" in node.semantic_identity_ids
        for node in view.typed_nodes
    )
    assert capacity.outcome == "P"
    assert "capacity_or_availability_event" in capacity.missing_roles
    assert capacity.proof_ids


@pytest.mark.parametrize(
    ("target_id", "text", "expected_barrier"),
    [
        (
            "DELL-RSQ-03A-TARGET-ASP",
            "An analyst claimed: Dell offered PowerEdge at USD 100.",
            None,
        ),
        (
            "DELL-RSQ-03A-TARGET-ASP",
            "Dell offered PowerEdge at USD 100, according to an analyst.",
            None,
        ),
        (
            "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH",
            "Dell included Nvidia in a lawsuit in 2026.",
            "non_relationship_include_context_is_not_supplier_relationship",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE",
            "Micron supplied HBM to Dell in 2026.",
            "generic_supply_or_delivery_is_not_Dell_capacity_release",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD",
            "Micron reported a target HBM utilization of 95% in 2026.",
            "plan_goal_capability_or_industry_figure_is_not_observed_issuer_measure",
        ),
        (
            "DELL-RSQ-03A-TARGET-HBM-SUPPLY",
            "Micron supplied an HBM brochure to Dell in 2026.",
            "document_brochure_guidance_or_announcement_is_not_Dell_supply_state",
        ),
        (
            "DELL-RSQ-03A-TARGET-UNITS",
            "Dell shipped a customer project with 20 PowerEdge nodes in 2026.",
            "project_node_install_customer_or_noncompany_count_is_not_Dell_company_units",
        ),
    ],
)
def test_r14_six_target_typed_forbidden_inference_controls_fail_closed(
    bundle, target_id: str, text: str, expected_barrier: str | None
) -> None:
    event_graph, _, _, decisions = _compile(text, bundle)
    decision = next(row for row in decisions if row.target_id == target_id)

    assert decision.outcome == "P"
    if expected_barrier is None:
        assert any(
            event.speech_mode == "reported_speech"
            for event in event_graph.events
            if target_id in event.semantic_labels
        )
        assert "affirmative_current_actual_assertion" in decision.missing_roles
    else:
        assert any(
            expected_barrier in event.inference_barrier_ids
            for event in event_graph.events
        )
        assert "forbidden_inference_clear" in decision.missing_roles
        assert f"forbidden_inference:{expected_barrier}" in decision.reason_codes


def test_r14_graph_only_compiler_pathological_80_320_scaling_is_bounded(bundle) -> None:
    elapsed: dict[int, float] = {}
    for count in (80, 320):
        text = " and ".join(
            f"Dell shipped {index + 1} PowerEdge systems in 2026"
            for index in range(count)
        ) + "."
        started = time.perf_counter()
        graph, _, view, decisions = _compile(text, bundle)
        elapsed[count] = time.perf_counter() - started

        units = next(
            row
            for row in decisions
            if row.target_id == "DELL-RSQ-03A-TARGET-UNITS"
        )
        assert len(graph.events) == count
        assert units.outcome == "C"
        assert not any(
            node.inference_barrier_ids
            for node in view.typed_nodes
            if node.node_type == "event"
        )

    assert elapsed[320] < 12.0
    assert elapsed[320] <= max(4.0, elapsed[80] * 8.0)


@pytest.mark.parametrize(
    "text",
    [
        "Dell may offer PowerEdge at $100.",
        "Dell will offer PowerEdge at $100.",
        "Dell did not offer PowerEdge at $100.",
        "Dell withdrew the price of PowerEdge at $100.",
        "Analyst said Dell offered PowerEdge at $100.",
        "An analyst claimed: Dell offered PowerEdge at $100.",
        "Dell offered PowerEdge at $100, according to an analyst.",
    ],
)
def test_r14_assertion_semantics_cannot_reach_complete_asp(bundle, text: str) -> None:
    _, _, view, decisions = _compile(text, bundle)
    asp = next(
        row
        for row in decisions
        if row.target_id == "DELL-RSQ-03A-TARGET-ASP"
    )

    assert asp.outcome != "C"
    if any(
        node.node_type == "event"
        and "DELL-RSQ-03A-TARGET-ASP" in node.target_labels
        for node in view.typed_nodes
    ):
        assert "affirmative_current_actual_assertion" in asp.missing_roles
