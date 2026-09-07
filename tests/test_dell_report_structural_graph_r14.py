from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import time

import pytest

from retrieval.dell_report_r14_common import DellReportR14ContractError
from retrieval.dell_report_r14_contracts import load_and_validate_r14_contracts
from retrieval.dell_report_structural_graph_r14 import (
    MentionNodeR14,
    PricePathProofR14,
    ProofRecordR14,
    build_event_argument_graph_r14,
    build_price_attachment_graph_r14,
    tokenize_r14,
    validate_event_argument_graph_r14,
    validate_price_attachment_graph_r14,
)


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def bundle():
    return load_and_validate_r14_contracts(root=ROOT)


def _event_by_surface(graph, surface: str):
    matches = [row for row in graph.events if row.predicate_normalized.endswith(surface)]
    assert len(matches) == 1
    return matches[0]


def _role_surfaces(graph, event, role: str) -> set[str]:
    mention_by_id = {row.mention_id: row for row in graph.mentions}
    return {
        mention_by_id[row.mention_id].normalized_value
        for row in graph.role_edges
        if row.event_id == event.event_id and row.role == role
    }


@pytest.mark.parametrize(
    "text",
    [
        "Dell offered PowerEdge at $100.",
        "戴尔 Dell offered PowerEdge at ＄１００。",
        "Dell offered PowerEdge 😀 at USD 100.00.\r\n",
        "De\u0301ll offered PowerEdge at €100.",
        "Dell\u00a0offered\u00a0PowerEdge\u00a0at\u00a0$100.",
    ],
)
def test_r14_tokenizer_is_lossless_contiguous_and_code_point_exact(bundle, text: str) -> None:
    tokens = tokenize_r14(text, bundle.grammar)

    assert "".join(row.raw for row in tokens) == text
    assert tokens[0].start == 0
    assert tokens[-1].end == len(text)
    assert all(left.end == right.start for left, right in zip(tokens, tokens[1:]))
    assert all(row.raw == text[row.start : row.end] for row in tokens)


def test_r14_normalization_equivalent_apostrophe_and_fullwidth_money_are_structurally_equal(
    bundle,
) -> None:
    ascii_graph = build_event_argument_graph_r14(
        text="Dell's offered PowerEdge at $100.", bundle=bundle
    )
    smart_graph = build_event_argument_graph_r14(
        text="Dell’s offered PowerEdge at ＄１００.", bundle=bundle
    )

    ascii_event = _event_by_surface(ascii_graph, "offered")
    smart_event = _event_by_surface(smart_graph, "offered")
    assert ascii_event.assertion_owner == smart_event.assertion_owner == "dell"
    assert _role_surfaces(ascii_graph, ascii_event, "price") == {"$100"}
    assert _role_surfaces(smart_graph, smart_event, "price") == {"$100"}


def test_r14_em_dash_and_parenthetical_scope_block_material_role_leakage(bundle) -> None:
    text = "Dell offered PowerEdge at $100—Acme blorp HBM $200."
    graph = build_event_argument_graph_r14(text=text, bundle=bundle)
    dash = text.index("—")
    offered = _event_by_surface(graph, "offered")

    assert offered.clause_span[1] <= dash + 1
    assert "$200" not in _role_surfaces(graph, offered, "price")

    parenthetical = build_event_argument_graph_r14(
        text="Dell offered PowerEdge ($100).", bundle=bundle
    )
    parenthetical_event = _event_by_surface(parenthetical, "offered")
    assert hasattr(parenthetical_event, "local_scope_id")
    assert not _role_surfaces(parenthetical, parenthetical_event, "price")
    price_graph = build_price_attachment_graph_r14(graph=parenthetical, bundle=bundle)
    assert not any(row.state == "PROVED" for row in price_graph.proofs)


def test_r14_three_coordinated_events_preserve_each_explicit_subject(bundle) -> None:
    graph = build_event_argument_graph_r14(
        text=(
            "Dell offered PowerEdge at $100 and Nvidia supplied HBM today "
            "and Micron shipped HBM in 2026."
        ),
        bundle=bundle,
    )
    events = {
        surface: _event_by_surface(graph, surface)
        for surface in ("offered", "supplied", "shipped")
    }

    assert {key: row.assertion_owner for key, row in events.items()} == {
        "offered": "dell",
        "supplied": "nvidia",
        "shipped": "micron",
    }
    assert not graph.subject_share_edges


@pytest.mark.parametrize(
    ("text", "bridge_type", "required_identity"),
    [
        (
            "Dell partnered with Nvidia and Nvidia supplied Dell PowerEdge in 2026.",
            "SUPPLIER_RELATIONSHIP_TO_DELIVERY",
            "ENTITY::NVIDIA",
        ),
        (
            "Micron supplied HBM in 2026 and Dell shipped HBM PowerEdge in 2026.",
            "HBM_STATE_TO_DELL",
            "PRODUCT::HBM",
        ),
    ],
)
def test_r14_typed_target_bridge_is_identity_bound_and_scope_local(
    bundle, text: str, bridge_type: str, required_identity: str
) -> None:
    graph = build_event_argument_graph_r14(text=text, bundle=bundle)
    bridge = next(
        row for row in graph.target_bridge_edges if row.bridge_type == bridge_type
    )
    assert required_identity in bridge.shared_semantic_identity_ids
    assert all(
        row.startswith(("ENTITY::", "PRODUCT::"))
        for row in bridge.shared_semantic_identity_ids
    )

    forged = replace(bridge, shared_semantic_identity_ids=("ENTITY::ACME",))
    with pytest.raises(DellReportR14ContractError, match="R14_graph_target_bridge"):
        validate_event_argument_graph_r14(
            replace(graph, target_bridge_edges=(forged,))
        )

    hard = build_event_argument_graph_r14(
        text=text.replace(" and ", ". ", 1), bundle=bundle
    )
    assert not hard.target_bridge_edges


def test_r14_unknown_subject_and_hard_scope_reset_block_false_inheritance(bundle) -> None:
    coordinated = build_event_argument_graph_r14(
        text="Dell offered PowerEdge at $100 and Acme shipped HBM today.",
        bundle=bundle,
    )
    shipped = _event_by_surface(coordinated, "shipped")
    assert shipped.assertion_owner != "dell"
    assert shipped.subject_state in {"ambiguous", "explicit_unknown"}
    assert not any(row.right_event_id == shipped.event_id for row in coordinated.subject_share_edges)

    hard = build_event_argument_graph_r14(
        text="Dell offered PowerEdge at $100. Acme expanded and shipped HBM today.",
        bundle=bundle,
    )
    assert all(
        row.assertion_owner != "dell"
        for row in hard.events
        if row.predicate_normalized.endswith(("expanded", "shipped"))
    )
    assert all(
        hard.raw_text[row.coordinator_span[0] : row.coordinator_span[1]].casefold()
        in bundle.grammar["scope"]["soft_coordinators"]
        for row in hard.subject_share_edges
    )


def test_r14_shared_subject_copies_only_actor_and_object_list_has_proof(bundle) -> None:
    graph = build_event_argument_graph_r14(
        text=(
            "Dell offered XE9680 at $100 and shipped 20 PowerEdge systems in 2026."
        ),
        bundle=bundle,
    )
    offered = _event_by_surface(graph, "offered")
    shipped = _event_by_surface(graph, "shipped")

    assert shipped.assertion_owner == "dell"
    assert _role_surfaces(graph, offered, "price") == {"$100"}
    assert not _role_surfaces(graph, shipped, "price")
    assert not _role_surfaces(graph, offered, "quantity")
    assert _role_surfaces(graph, shipped, "quantity") == {"20"}
    assert not _role_surfaces(graph, offered, "period")
    assert _role_surfaces(graph, shipped, "period") == {"2026"}

    listed = build_event_argument_graph_r14(
        text="Dell shipped PowerEdge and AI server in 2026.", bundle=bundle
    )
    assert any(
        row.rule_id == "G22-OBJECT-LIST"
        and row.state == "PROVED"
        and row.premise_spans
        for row in listed.proofs
    )

    quantified = build_event_argument_graph_r14(
        text=(
            "Dell shipped 10 PowerEdge systems and 20 PowerEdge appliances "
            "in 2026."
        ),
        bundle=bundle,
    )
    assert len(quantified.events) == 1
    assert any(
        row.rule_id == "G22-OBJECT-LIST" and row.state == "PROVED"
        for row in quantified.proofs
    )


def test_r14_passive_product_priced_at_has_local_object_and_complete_path(bundle) -> None:
    graph = build_event_argument_graph_r14(
        text="Dell PowerEdge was priced at USD 100.", bundle=bundle
    )
    price_graph = build_price_attachment_graph_r14(graph=graph, bundle=bundle)

    assert len(graph.events) == 1
    assert graph.events[0].predicate_normalized == "was priced"
    assert any(
        row.role == "object"
        and row.event_id == graph.events[0].event_id
        and row.proof_state == "PROVED"
        for row in graph.role_edges
    )
    assert any(
        row.rule_id == "G51-PRICE-NOMINAL" and row.state == "PROVED"
        for row in price_graph.proofs
    )


@pytest.mark.parametrize(
    ("text", "rule_id"),
    [
        ("Dell offered PowerEdge XE9680 at $15,000.", "G50-PRICE-DIRECT"),
        ("Dell priced PowerEdge XE9680 at $15,000.", "G51-PRICE-NOMINAL"),
        ("Dell said the price of PowerEdge XE9680 was $15,000.", "G51-PRICE-NOMINAL"),
        (
            "Dell offered a hardware bundle of PowerEdge R760 and PowerEdge XE9680 "
            "for a total of $30,000.",
            "G52-HARDWARE-BUNDLE",
        ),
    ],
)
def test_r14_price_graph_accepts_only_registered_positive_topologies(
    bundle, text: str, rule_id: str
) -> None:
    event_graph = build_event_argument_graph_r14(text=text, bundle=bundle)
    price_graph = build_price_attachment_graph_r14(graph=event_graph, bundle=bundle)
    proved = [row for row in price_graph.proofs if row.state == "PROVED"]

    assert len(proved) == 1
    assert proved[0].rule_id == rule_id
    assert proved[0].edge_ids
    assert proved[0].governing_head_mention_ids


def test_r14_explicit_price_nominal_uses_continuous_G40_path(bundle) -> None:
    graph = build_event_argument_graph_r14(
        text="Dell said the price of PowerEdge XE9680 was $15,000.", bundle=bundle
    )
    price_graph = build_price_attachment_graph_r14(graph=graph, bundle=bundle)
    proof = next(row for row in price_graph.proofs if row.state == "PROVED")
    path_edges = [
        row for row in price_graph.edges if row.edge_id in proof.edge_ids
    ]

    assert proof.rule_id == "G51-PRICE-NOMINAL"
    assert {row.relation for row in path_edges} == {
        "event_object_head",
        "price_attachment",
        "complement",
    }
    assert any(row.rule_id == "G40-NOMINAL-HEAD" for row in path_edges)
    assert any(
        row.mention_type == "nominal_head"
        and row.normalized_value == "price"
        and row.proof_state == "PROVED"
        for row in price_graph.nodes
    )

    complement = next(row for row in path_edges if row.relation == "complement")
    removed_edges = tuple(
        row for row in price_graph.edges if row.edge_id != complement.edge_id
    )
    removed_proof = replace(
        proof,
        edge_ids=tuple(row for row in proof.edge_ids if row != complement.edge_id),
    )
    with pytest.raises(DellReportR14ContractError, match="R14_price_positive"):
        validate_price_attachment_graph_r14(
            replace(price_graph, edges=removed_edges, proofs=(removed_proof,)),
            graph=graph,
        )


@pytest.mark.parametrize(
    "text",
    [
        "Dell offered a service bundle with PowerEdge for $100.",
        "Dell price of support was $100 for PowerEdge.",
        "Dell offered PowerEdge at $50 and bundle PowerEdge $100.",
        "Dell offered PowerEdge ($100).",
        "Dell offered a support package covering PowerEdge for $100.",
        "Dell offered a support package encompassing PowerEdge for $100.",
        "Dell offered a support package incorporating PowerEdge for $100.",
        "Dell offered a nonce package flurbling PowerEdge for $100.",
        "Dell offered PowerEdge for $100 under service agreement.",
        "Dell offered PowerEdge near $100.",
    ],
)
def test_r14_price_graph_fails_closed_for_higher_head_scope_or_ambiguous_event(
    bundle, text: str
) -> None:
    event_graph = build_event_argument_graph_r14(text=text, bundle=bundle)
    price_graph = build_price_attachment_graph_r14(graph=event_graph, bundle=bundle)

    assert not any(row.state == "PROVED" for row in price_graph.proofs)
    assert all(
        row.competing_head_ids
        or row.competing_price_ids
        or row.limitations
        or row.state in {"AMBIGUOUS", "UNSUPPORTED"}
        for row in price_graph.proofs
    )


def test_r14_graph_validator_recomputes_tokens_roles_and_subject_share(bundle) -> None:
    graph = build_event_argument_graph_r14(
        text="Dell offered PowerEdge at $100 and shipped HBM today.", bundle=bundle
    )
    bad_token = replace(graph.tokens[0], raw="Acme", start=999, end=1003)
    with pytest.raises(DellReportR14ContractError, match="R14_graph_token"):
        validate_event_argument_graph_r14(replace(graph, tokens=(bad_token, *graph.tokens[1:])))

    price = next(row for row in graph.mentions if row.mention_type == "price")
    actor_edge = next(row for row in graph.role_edges if row.role == "actor")
    bad_actor = replace(
        actor_edge,
        mention_id=price.mention_id,
        event_scope_id="WRONG-SCOPE",
        proof_rule_id="G23-SUBJECT-INHERIT",
        proof_state="PROVED",
    )
    role_edges = tuple(bad_actor if row is actor_edge else row for row in graph.role_edges)
    with pytest.raises(DellReportR14ContractError, match="R14_graph_"):
        validate_event_argument_graph_r14(replace(graph, role_edges=role_edges))

    wrong_proof = next(
        row.proof_id
        for row in graph.proofs
        if row.conclusion.startswith("event_role:predicate:")
    )
    bad_premise = replace(actor_edge, premise_proof_ids=(wrong_proof,))
    premise_edges = tuple(
        bad_premise if row is actor_edge else row for row in graph.role_edges
    )
    with pytest.raises(DellReportR14ContractError, match="R14_graph_role_premise"):
        validate_event_argument_graph_r14(replace(graph, role_edges=premise_edges))


def test_r14_subject_share_validator_recomputes_exact_adjacent_coordinator(bundle) -> None:
    graph = build_event_argument_graph_r14(
        text=(
            "Dell offered PowerEdge at $100 and shipped HBM today "
            "and sold 20 PowerEdge systems in 2026."
        ),
        bundle=bundle,
    )
    assert len(graph.subject_share_edges) == 2
    first, second = sorted(
        graph.subject_share_edges, key=lambda row: row.coordinator_span
    )
    rebound = replace(second, coordinator_span=first.coordinator_span)
    edges = tuple(
        rebound if row is second else row for row in graph.subject_share_edges
    )

    with pytest.raises(DellReportR14ContractError, match="R14_graph_subject_share"):
        validate_event_argument_graph_r14(replace(graph, subject_share_edges=edges))


def test_r14_price_validator_rejects_fabricated_proved_path(bundle) -> None:
    event_graph = build_event_argument_graph_r14(
        text="Dell offered PowerEdge at $100.", bundle=bundle
    )
    price_graph = build_price_attachment_graph_r14(graph=event_graph, bundle=bundle)
    event = event_graph.events[0]
    fake = PricePathProofR14(
        event_id=event.event_id,
        product_mention_ids=("MISSING-PRODUCT",),
        price_mention_ids=("MISSING-PRICE",),
        governing_head_mention_ids=(),
        edge_ids=(),
        rule_id="G50-PRICE-DIRECT",
        state="PROVED",
        family="pricing_event_product_and_price_complement",
        competing_head_ids=(),
        competing_price_ids=(),
        connector_surface_provenance=(),
        limitations=(),
    )

    with pytest.raises(DellReportR14ContractError, match="R14_price_"):
        validate_price_attachment_graph_r14(
            replace(price_graph, proofs=(fake,)), graph=event_graph
        )

    proved = next(row for row in price_graph.proofs if row.state == "PROVED")
    price_edge = next(
        row
        for row in price_graph.edges
        if row.relation == "price_attachment"
    )
    reversed_edge = replace(price_edge, direction="nominal_to_price")
    reversed_edges = tuple(
        reversed_edge if row is price_edge else row for row in price_graph.edges
    )
    rebound_proof = replace(
        proved,
        edge_ids=tuple(
            reversed_edge.edge_id if edge_id == price_edge.edge_id else edge_id
            for edge_id in proved.edge_ids
        ),
    )
    with pytest.raises(DellReportR14ContractError, match="R14_price_graph_edge"):
        validate_price_attachment_graph_r14(
            replace(price_graph, edges=reversed_edges, proofs=(rebound_proof,)),
            graph=event_graph,
        )


def test_r14_graph_validator_rejects_forged_or_orphan_proof_records(bundle) -> None:
    graph = build_event_argument_graph_r14(
        text="Dell shipped PowerEdge and AI server in 2026.", bundle=bundle
    )
    forged = ProofRecordR14(
        rule_id="G22-OBJECT-LIST",
        state="PROVED",
        conclusion="forged",
        premise_spans=((0, 4),),
    )
    with pytest.raises(DellReportR14ContractError, match="R14_graph_proof"):
        validate_event_argument_graph_r14(
            replace(graph, proofs=(*graph.proofs, forged))
        )

    original = graph.proofs[0]
    orphan = replace(original, premise_edge_ids=("ORPHAN-EDGE",))
    proofs = tuple(orphan if row is original else row for row in graph.proofs)
    with pytest.raises(DellReportR14ContractError, match="R14_graph_proof"):
        validate_event_argument_graph_r14(replace(graph, proofs=proofs))

    existing = next(row for row in graph.proofs if row.rule_id == "G22-OBJECT-LIST")
    resigned = replace(
        existing,
        premise_node_ids=tuple(reversed(existing.premise_node_ids)),
    )
    resigned_proofs = tuple(
        sorted(
            (resigned if row is existing else row for row in graph.proofs),
            key=lambda row: (
                row.premise_spans,
                row.rule_id,
                row.conclusion,
                row.proof_digest,
            ),
        )
    )
    with pytest.raises(DellReportR14ContractError, match="R14_graph_proof_G22"):
        validate_event_argument_graph_r14(replace(graph, proofs=resigned_proofs))


def test_r14_graph_validator_recomputes_predicate_operator_identity(bundle) -> None:
    graph = build_event_argument_graph_r14(
        text="Micron allocated HBM capacity to Dell in 2026.", bundle=bundle
    )
    event = next(row for row in graph.events if row.semantic_operator_ids)
    forged = replace(event, semantic_operator_ids=("OPERATOR::SUPPLY",))
    events = tuple(forged if row.event_id == event.event_id else row for row in graph.events)

    with pytest.raises(
        DellReportR14ContractError,
        match="R14_graph_event_operator_identity_recomputation_failed",
    ):
        validate_event_argument_graph_r14(replace(graph, events=events))


def test_r14_graph_validator_recomputes_event_labels_types_and_assertion(bundle) -> None:
    graph = build_event_argument_graph_r14(
        text="Dell discussed PowerEdge in 2026.", bundle=bundle
    )
    event = graph.events[0]
    forged_semantics = replace(
        event,
        semantic_labels=("DELL-RSQ-03A-TARGET-UNITS",),
        event_types=("delivery",),
    )
    with pytest.raises(
        DellReportR14ContractError,
        match="R14_graph_event_semantics_recomputation_failed",
    ):
        validate_event_argument_graph_r14(
            replace(graph, events=(forged_semantics,))
        )

    forged_assertion = replace(event, modality="modal", actuality="forward_looking")
    with pytest.raises(
        DellReportR14ContractError,
        match="R14_graph_event_assertion_semantics_recomputation_failed",
    ):
        validate_event_argument_graph_r14(
            replace(graph, events=(forged_assertion,))
        )


def test_r14_HBM_bridge_requires_shared_HBM_and_adjacent_events(bundle) -> None:
    unrelated = build_event_argument_graph_r14(
        text=(
            "Dell shipped 10 PowerEdge systems in 2026 and "
            "Dell shipped 20 PowerEdge systems in 2026."
        ),
        bundle=bundle,
    )
    separated = build_event_argument_graph_r14(
        text=(
            "Micron supplied HBM in 2026 and Acme reported utilization in 2026 "
            "and Dell shipped HBM PowerEdge in 2026."
        ),
        bundle=bundle,
    )

    assert not unrelated.target_bridge_edges
    assert not any(
        edge.bridge_type == "HBM_STATE_TO_DELL"
        for edge in separated.target_bridge_edges
    )


def test_r14_pathological_single_sentence_scaling_is_bounded(bundle) -> None:
    elapsed: dict[int, float] = {}
    for count in (80, 320):
        text = " and ".join(
            f"Dell shipped {index + 1} PowerEdge systems in 2026"
            for index in range(count)
        ) + "."
        started = time.perf_counter()
        graph = build_event_argument_graph_r14(text=text, bundle=bundle)
        price_graph = build_price_attachment_graph_r14(graph=graph, bundle=bundle)
        elapsed[count] = time.perf_counter() - started

        assert len(graph.events) == count
        assert not graph.target_bridge_edges
        assert len(price_graph.proofs) == count

    assert elapsed[320] < 5.0
    assert elapsed[320] <= max(2.0, elapsed[80] * 8.0)


def test_r14_graph_validator_rejects_duplicate_or_mutated_subject_share(bundle) -> None:
    graph = build_event_argument_graph_r14(
        text="Dell offered PowerEdge at $100 and shipped HBM today.", bundle=bundle
    )
    edge = graph.subject_share_edges[0]
    with pytest.raises(DellReportR14ContractError, match="R14_graph_subject_share"):
        validate_event_argument_graph_r14(
            replace(graph, subject_share_edges=(*graph.subject_share_edges, edge))
        )

    mutated = replace(
        edge,
        destination_role="price",
        proof_rule_id="G30-ROLE-LOCAL",
        cardinality="many",
    )
    with pytest.raises(DellReportR14ContractError, match="R14_graph_subject_share"):
        validate_event_argument_graph_r14(
            replace(graph, subject_share_edges=(mutated,))
        )


def test_r14_graph_validator_rejects_duplicate_or_mutated_temporal_edge(bundle) -> None:
    graph = build_event_argument_graph_r14(
        text="Dell shipped PowerEdge in 2026.", bundle=bundle
    )
    edge = graph.temporal_edges[0]
    with pytest.raises(DellReportR14ContractError, match="R14_graph_temporal"):
        validate_event_argument_graph_r14(
            replace(graph, temporal_edges=(*graph.temporal_edges, edge))
        )

    mutated = replace(
        edge,
        scope_type="forged",
        evidence_spans=((0, 1),),
        premise_proof_ids=("ORPHAN",),
    )
    with pytest.raises(DellReportR14ContractError, match="R14_graph_temporal"):
        validate_event_argument_graph_r14(
            replace(graph, temporal_edges=(mutated,))
        )


def test_r14_price_validator_rejects_cross_clause_product_rebind(bundle) -> None:
    graph = build_event_argument_graph_r14(
        text="Dell offered PowerEdge at $100; AI server.", bundle=bundle
    )
    price_graph = build_price_attachment_graph_r14(graph=graph, bundle=bundle)
    proved = next(row for row in price_graph.proofs if row.state == "PROVED")
    other = next(
        row
        for row in graph.mentions
        if row.mention_type == "product_or_hardware"
        and row.mention_id not in proved.product_mention_ids
    )
    rebound = replace(proved, product_mention_ids=(other.mention_id,))

    with pytest.raises(DellReportR14ContractError, match="R14_price_positive"):
        validate_price_attachment_graph_r14(
            replace(price_graph, proofs=(rebound,)), graph=graph
        )


def test_r14_price_validator_requires_all_bundle_members_and_unique_proof(bundle) -> None:
    graph = build_event_argument_graph_r14(
        text=(
            "Dell offered a hardware bundle of PowerEdge R760 and PowerEdge XE9680 "
            "for a total of $30,000."
        ),
        bundle=bundle,
    )
    price_graph = build_price_attachment_graph_r14(graph=graph, bundle=bundle)
    proved = next(row for row in price_graph.proofs if row.state == "PROVED")
    member_ids = {
        row.edge_id for row in price_graph.edges if row.relation == "bundle_member"
    }
    kept_edges = tuple(
        row for row in price_graph.edges if row.edge_id not in member_ids
    )
    stripped = replace(
        proved, edge_ids=tuple(row for row in proved.edge_ids if row not in member_ids)
    )
    with pytest.raises(DellReportR14ContractError, match="R14_price_positive"):
        validate_price_attachment_graph_r14(
            replace(price_graph, edges=kept_edges, proofs=(stripped,)), graph=graph
        )

    with pytest.raises(DellReportR14ContractError, match="R14_price_proof"):
        validate_price_attachment_graph_r14(
            replace(price_graph, proofs=(proved, proved)), graph=graph
        )


def test_r14_price_validator_rejects_out_of_bounds_private_nominal_node(bundle) -> None:
    graph = build_event_argument_graph_r14(
        text="Dell offered PowerEdge at $100.", bundle=bundle
    )
    price_graph = build_price_attachment_graph_r14(graph=graph, bundle=bundle)
    forged = MentionNodeR14(
        mention_type="nominal_head",
        raw_value="",
        normalized_value="forged",
        start=999,
        end=999,
        type_proof_rule_id="G40-NOMINAL-HEAD",
        local_scope_id=graph.local_scopes[0].scope_id,
        proof_state="MALFORMED",
    )
    nodes = tuple(
        sorted(
            (*price_graph.nodes, forged),
            key=lambda row: (
                row.start,
                row.end,
                row.mention_type,
                row.type_proof_rule_id,
                row.node_digest,
            ),
        )
    )
    with pytest.raises(DellReportR14ContractError, match="R14_price_graph_private_node"):
        validate_price_attachment_graph_r14(
            replace(price_graph, nodes=nodes), graph=graph
        )


def test_r14_whole_text_nfkc_and_compatibility_fraction_are_valid(bundle) -> None:
    tokens = tokenize_r14("De\u0301ll offered ½ PowerEdge.", bundle.grammar)
    assert any(row.kind == "WORD" and row.normalized == "déll" for row in tokens)
    graph = build_event_argument_graph_r14(
        text="Dell offered ½ PowerEdge at $100.", bundle=bundle
    )
    validate_event_argument_graph_r14(graph)


def test_r14_unclosed_quote_propagates_ambiguity_to_price_proof(bundle) -> None:
    graph = build_event_argument_graph_r14(
        text='"Dell offered PowerEdge at $100', bundle=bundle
    )
    price_graph = build_price_attachment_graph_r14(graph=graph, bundle=bundle)
    assert not any(row.state == "PROVED" for row in price_graph.proofs)


def test_r14_bare_ontology_noun_does_not_create_complete_event(bundle) -> None:
    graph = build_event_argument_graph_r14(
        text="Dell sale PowerEdge at $100.", bundle=bundle
    )
    price_graph = build_price_attachment_graph_r14(graph=graph, bundle=bundle)
    assert not any(row.state == "PROVED" for row in price_graph.proofs)


def test_r14_unknown_event_does_not_prove_roles_by_span_cooccurrence(bundle) -> None:
    graph = build_event_argument_graph_r14(
        text="Dell discussed PowerEdge in 2026.", bundle=bundle
    )
    discussed = _event_by_surface(graph, "discussed")
    assert not any(
        row.event_id == discussed.event_id
        and row.role in {"object", "period"}
        and row.proof_state == "PROVED"
        for row in graph.role_edges
    )
    unsupported = next(
        row
        for row in graph.role_edges
        if row.event_id == discussed.event_id and row.role == "object"
    )
    old_proof = next(
        row for row in graph.proofs if row.proof_id == unsupported.premise_proof_ids[0]
    )
    forged_proof = replace(old_proof, state="PROVED")
    forged_edge = replace(
        unsupported,
        proof_state="PROVED",
        premise_proof_ids=(forged_proof.proof_id,),
    )
    proofs = tuple(
        sorted(
            (forged_proof if row is old_proof else row for row in graph.proofs),
            key=lambda row: (
                row.premise_spans,
                row.rule_id,
                row.conclusion,
                row.proof_digest,
            ),
        )
    )
    edges = tuple(
        sorted(
            (forged_edge if row is unsupported else row for row in graph.role_edges),
            key=lambda row: (
                row.event_id,
                row.role,
                row.mention_id,
                row.edge_digest,
            ),
        )
    )
    with pytest.raises(
        DellReportR14ContractError,
        match="R14_graph_role_population_recomputation_failed",
    ):
        validate_event_argument_graph_r14(
            replace(graph, role_edges=edges, proofs=proofs)
        )


def test_r14_object_list_nonce_barrier_fails_closed(bundle) -> None:
    graph = build_event_argument_graph_r14(
        text="Dell shipped PowerEdge and glorp AI server in 2026.", bundle=bundle
    )
    assert not any(
        row.rule_id == "G22-OBJECT-LIST" and row.state == "PROVED"
        for row in graph.proofs
    )


def test_r14_pre_predicate_service_head_blocks_price_complete(bundle) -> None:
    graph = build_event_argument_graph_r14(
        text="Dell's service agreement offered PowerEdge for $100.", bundle=bundle
    )
    price_graph = build_price_attachment_graph_r14(graph=graph, bundle=bundle)
    assert not any(row.state == "PROVED" for row in price_graph.proofs)


def test_r14_pre_predicate_generic_supply_before_available_is_not_material_proof(
    bundle,
) -> None:
    graph = build_event_argument_graph_r14(
        text="Even where multiple sources of supply are available, qualification could be delayed.",
        bundle=bundle,
    )
    available = _event_by_surface(graph, "are available")
    supply_mentions = {
        row.mention_id
        for row in graph.mentions
        if row.normalized_value == "supply"
    }
    assert supply_mentions
    assert all(
        row.proof_state == "UNSUPPORTED"
        for row in graph.role_edges
        if row.event_id == available.event_id and row.mention_id in supply_mentions
    )


def test_r14_morphology_transducer_preserves_running_target_semantics(bundle) -> None:
    graph = build_event_argument_graph_r14(
        text="Micron is running HBM utilization at 95% today.", bundle=bundle
    )
    event = _event_by_surface(graph, "running")

    assert "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD" in event.semantic_labels
    assert "observed_measurement" in event.event_types


@pytest.mark.parametrize(
    ("text", "predicate", "expected_mode"),
    [
        (
            "An analyst claimed: Dell offered PowerEdge at $100.",
            "offered",
            "reported_speech",
        ),
        (
            "Dell offered PowerEdge at $100, according to an analyst.",
            "offered",
            "reported_speech",
        ),
        (
            "Dell offered PowerEdge at $100, an analyst stated.",
            "offered",
            "reported_speech",
        ),
        (
            "Dell stated: Dell offered PowerEdge at $100.",
            "offered",
            "issuer_reported",
        ),
        (
            "Dell offered PowerEdge at $100, Dell stated.",
            "offered",
            "issuer_reported",
        ),
        (
            "Dell offered PowerEdge at $100, according to Dell.",
            "offered",
            "issuer_reported",
        ),
        (
            "Dell said the price of PowerEdge was $100.",
            "was",
            "issuer_reported",
        ),
    ],
)
def test_r14_typed_attribution_scope_separates_reporter_from_factual_actor(
    bundle, text: str, predicate: str, expected_mode: str
) -> None:
    graph = build_event_argument_graph_r14(text=text, bundle=bundle)
    event = _event_by_surface(graph, predicate)

    assert event.speech_mode == expected_mode
    validate_event_argument_graph_r14(graph)


def test_r14_graphs_are_byte_exact_deterministic(bundle) -> None:
    text = "Dell offered PowerEdge XE9680 at $15,000 and shipped HBM today."
    first = build_event_argument_graph_r14(text=text, bundle=bundle)
    second = build_event_argument_graph_r14(text=text, bundle=bundle)
    assert first.as_dict() == second.as_dict()
    assert first.graph_digest == second.graph_digest

    first_price = build_price_attachment_graph_r14(graph=first, bundle=bundle)
    second_price = build_price_attachment_graph_r14(graph=second, bundle=bundle)
    assert first_price.as_dict() == second_price.as_dict()
    assert first_price.graph_digest == second_price.graph_digest
