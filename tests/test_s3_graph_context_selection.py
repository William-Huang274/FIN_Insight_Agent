from __future__ import annotations

from copy import deepcopy

from sec_agent.research.research_context import compile_graph_context_packs


def _contract(*, maximum_nodes: int = 12, maximum_edges: int = 16) -> dict:
    return {
        "graph_context": {
            "maximum_nodes_per_cell": maximum_nodes,
            "maximum_edges_per_cell": maximum_edges,
        }
    }


def _cell(refs: list[str]) -> dict:
    return {
        "cell_id": "CELL::counterevidence",
        "primary_slot_id": "counterevidence_and_what_would_change",
        "supplemental_context_slot_ids": ["capacity_inputs_execution"],
        "allowed_evidence_refs": refs,
        "allowed_numeric_refs": [],
    }


def _card(index: int, *, owner: str = "DELL", slot: str | None = None) -> dict:
    slot_id = slot or "counterevidence_and_what_would_change"
    return {
        "evidence_ref": f"EV::{index:016X}",
        "evidence_owner_ticker": owner,
        "evidence_role": (
            "issuer_direct_source" if owner == "DELL" else "counterparty_or_ecosystem_readthrough"
        ),
        "source_tier": (
            "primary_sec_filing" if owner == "DELL" else "named_counterparty_or_standards_primary"
        ),
        "relationship_directions": [f"direction_{index:02d}"],
        "slot_bindings": [{"slot_id": slot_id, "facet_ids": [f"facet_{index:02d}"]}],
    }


def _compile(cards: list[dict], *, maximum_nodes: int = 12, maximum_edges: int = 16) -> dict:
    refs = [row["evidence_ref"] for row in cards]
    return compile_graph_context_packs(
        context_contract=_contract(
            maximum_nodes=maximum_nodes,
            maximum_edges=maximum_edges,
        ),
        case_identity={"case_key": "DELL", "subject_ticker": "DELL"},
        cells=[_cell(refs)],
        evidence_cards=cards,
        numeric_cards=[],
    )[0]


def test_graph_context_capacity_selects_and_receipts_without_losing_pack_authority() -> None:
    graph = _compile([_card(index) for index in range(17)])

    assert graph["schema_version"] == "fin_ia_graph_context_pack_v1_1"
    assert len(graph["edges"]) == 16
    receipt = graph["selection_receipt"]
    assert receipt["candidate_edge_count"] == 17
    assert receipt["selected_edge_count"] == 16
    assert receipt["omitted_edge_count"] == 1
    assert receipt["pack_evidence_or_numeric_authority_changed"] is False
    assert receipt["model_calls"] == 0
    assert set(receipt["selected_graph_edge_refs"]) == {
        row["graph_edge_ref"] for row in graph["edges"]
    }
    assert receipt["omitted_edges"][0]["evidence_refs"]


def test_graph_context_selection_is_stable_under_input_permutation() -> None:
    cards = [_card(index, owner=f"ORG::{index:02d}") for index in range(17)]
    forward = _compile(cards)
    reverse = _compile(list(reversed(deepcopy(cards))))

    assert forward == reverse
    assert len(forward["nodes"]) == 12
    assert len(forward["edges"]) == 11
    assert forward["selection_receipt"]["omitted_edge_count"] == 6
    assert forward["selection_receipt"]["omitted_node_count"] == 6


def test_graph_context_selection_prioritizes_primary_and_supplemental_facets() -> None:
    cards = [
        _card(1, slot="unrelated_slot"),
        _card(2, slot="capacity_inputs_execution"),
        _card(3, slot="counterevidence_and_what_would_change"),
    ]
    graph = _compile(cards, maximum_edges=2)
    selected_directions = {
        row["relationship_direction"] for row in graph["edges"]
    }

    assert selected_directions == {"direction_02", "direction_03"}
    assert graph["selection_receipt"]["omitted_edges"][0][
        "relationship_direction"
    ] == "direction_01"
