from __future__ import annotations

from copy import deepcopy

from sec_agent.research.multi_agent_preview import (
    _project_specialist_graph_context,
)
from sec_agent.research.reviewed_evidence_pack import canonical_digest


def _base_graph() -> dict:
    body = {
        "schema_version": "fin_ia_graph_context_pack_v1_1",
        "cell_id": "CELL::counterevidence",
        "case_key": "DELL",
        "nodes": [
            {
                "entity_id": "DELL",
                "entity_role": "research_subject",
                "authority": "current_case_identity",
            },
            {
                "entity_id": "MU",
                "entity_role": "reviewed_evidence_owner",
                "authority": "current_reviewed_evidence",
            },
            {
                "entity_id": "NVDA",
                "entity_role": "reviewed_evidence_owner",
                "authority": "current_reviewed_evidence",
            },
        ],
        "edges": [
            {
                "graph_edge_ref": "GRAPH::BASE1",
                "cell_id": "CELL::counterevidence",
                "source_entity": "MU",
                "target_entity": "DELL",
                "relationship_direction": "supply_capacity_context",
                "evidence_refs": ["EV::SUPPLY", "EV::COUNTER"],
                "authority": "reviewed_evidence_bound_context",
                "grants_company_fact_or_causality": False,
            },
            {
                "graph_edge_ref": "GRAPH::BASE2",
                "cell_id": "CELL::counterevidence",
                "source_entity": "NVDA",
                "target_entity": "DELL",
                "relationship_direction": "regulatory_counterevidence",
                "evidence_refs": ["EV::COUNTER"],
                "authority": "reviewed_evidence_bound_context",
                "grants_company_fact_or_causality": False,
            },
        ],
        "authority": {
            "compiled_from_current_case_reviewed_evidence_and_numeric_facts": True,
            "archived_graph_rows_used": False,
            "scope_or_context_edge_grants_fact_authority": False,
        },
    }
    return {**body, "graph_context_digest": canonical_digest(body)}


def test_specialist_graph_projection_removes_other_role_authority() -> None:
    graph = _project_specialist_graph_context(
        graph_pack=_base_graph(),
        allowed_evidence_refs={"EV::SUPPLY"},
        role_slot_ids={"capacity_inputs_execution"},
        subject_ticker="DELL",
        allowed_numeric_refs=set(),
        numeric_cards=[],
    )

    assert graph["schema_version"] == "fin_ia_role_graph_context_view_v1_0"
    assert len(graph["edges"]) == 1
    assert graph["edges"][0]["evidence_refs"] == ["EV::SUPPLY"]
    assert {row["entity_id"] for row in graph["nodes"]} == {"DELL", "MU"}
    assert graph["projection"] == {
        "base_edge_count": 2,
        "role_edge_count": 1,
        "base_node_count": 3,
        "role_node_count": 2,
        "authority_expanded": False,
    }


def test_specialist_graph_projection_is_stable_and_never_adds_refs() -> None:
    base = _base_graph()
    forward = _project_specialist_graph_context(
        graph_pack=base,
        allowed_evidence_refs={"EV::COUNTER"},
        role_slot_ids={"counterevidence_and_what_would_change"},
        subject_ticker="DELL",
        allowed_numeric_refs=set(),
        numeric_cards=[],
    )
    reversed_base = deepcopy(base)
    reversed_base["edges"] = list(reversed(reversed_base["edges"]))
    reverse = _project_specialist_graph_context(
        graph_pack=reversed_base,
        allowed_evidence_refs={"EV::COUNTER"},
        role_slot_ids={"counterevidence_and_what_would_change"},
        subject_ticker="DELL",
        allowed_numeric_refs=set(),
        numeric_cards=[],
    )

    assert forward == reverse
    assert {
        ref for edge in forward["edges"] for ref in edge["evidence_refs"]
    } == {"EV::COUNTER"}
