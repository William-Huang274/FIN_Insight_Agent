from __future__ import annotations

from bisect import bisect_left
from collections import defaultdict
from typing import Iterable, Sequence

from .dell_report_graph_schema_r14 import (
    EventArgumentGraphR14,
    MentionNodeR14,
    NominalEdgeR14,
    PriceAttachmentGraphR14,
    PricePathProofR14,
    RoleEdgeR14,
    canonical_semantic_identity_ids_r14,
    validate_price_attachment_graph_r14,
)
from .dell_report_r14_contracts import R14ContractBundle


_COPULAR = frozenset({"am", "are", "be", "been", "being", "is", "was", "were"})
_BOUND_TOTAL = frozenset({"total", "totals", "totaling", "totalled", "totaled"})
_REPORTING_WORDS = frozenset({"announce", "announced", "report", "reported", "said", "says"})


def _covered(token_start: int, token_end: int, spans: Iterable[tuple[int, int]]) -> bool:
    return any(start <= token_start and token_end <= end for start, end in spans)


def _tokens_in_span(graph: EventArgumentGraphR14, low: int, high: int, *, scope_id: str):
    start_index = bisect_left(graph.tokens, low, key=lambda row: row.start)
    output = []
    for row in graph.tokens[start_index:]:
        if row.start >= high:
            break
        if row.local_scope_id == scope_id and row.end <= high:
            output.append(row)
    return tuple(output)


def _nominal_relation(words: Sequence[str]) -> str:
    values = set(words)
    if values.intersection({"which", "that", "who", "whose"}):
        return "relative"
    if any(value.endswith(("ing", "ed", "en")) for value in values):
        return "participial"
    if values.intersection({"of", "for", "with"}):
        return "complement"
    if values.intersection({"and", "or"}):
        return "coordination"
    return "apposition"


def _tokens_between(
    graph: EventArgumentGraphR14, left: int, right: int, *, scope_id: str
) -> tuple[str, ...]:
    low, high = sorted((left, right))
    return tuple(
        row.normalized
        for row in _tokens_in_span(graph, low, high, scope_id=scope_id)
        if row.kind == "WORD"
    )


def _new_head(
    *, graph: EventArgumentGraphR14, token, mention_type: str = "nominal_head"
) -> MentionNodeR14:
    return MentionNodeR14(
        mention_type=mention_type,
        raw_value=token.raw,
        normalized_value=token.normalized,
        start=token.start,
        end=token.end,
        type_proof_rule_id="G40-NOMINAL-HEAD",
        local_scope_id=token.local_scope_id,
        proof_state="PROVED" if mention_type == "bundle" else "UNSUPPORTED",
        semantic_identity_ids=canonical_semantic_identity_ids_r14(
            mention_type, token.normalized
        ),
    )


def build_price_attachment_graph_r14(
    *, graph: EventArgumentGraphR14, bundle: R14ContractBundle
) -> PriceAttachmentGraphR14:
    mention_by_id = {row.mention_id: row for row in graph.mentions}
    role_by_event: defaultdict[str, list[RoleEdgeR14]] = defaultdict(list)
    for edge in graph.role_edges:
        role_by_event[edge.event_id].append(edge)
    events_with_price_candidates = {
        event_id
        for event_id, edges in role_by_event.items()
        if any(row.role == "price" for row in edges)
    }
    event_by_id = {row.event_id: row for row in graph.events}
    price_event_count_by_clause: defaultdict[tuple[int, int], int] = defaultdict(int)
    for event_id in events_with_price_candidates:
        price_event_count_by_clause[event_by_id[event_id].clause_span] += 1

    function_words = set(bundle.grammar["structural_resources"]["function_words"])
    auxiliaries = set(bundle.grammar["structural_resources"]["auxiliaries"])
    coordinators = set(bundle.grammar["scope"]["soft_coordinators"])
    private_nodes: dict[str, MentionNodeR14] = {}
    nominal_edges: list[NominalEdgeR14] = []
    proofs: list[PricePathProofR14] = []

    for event in graph.events:
        event_edges = role_by_event[event.event_id]
        proved_edges = [row for row in event_edges if row.proof_state == "PROVED"]
        products = sorted(
            {
                mention_by_id[row.mention_id]
                for row in proved_edges
                if row.role == "object"
                and mention_by_id[row.mention_id].mention_type == "product_or_hardware"
            },
            key=lambda row: (row.start, row.end, row.mention_id),
        )
        prices = sorted(
            {
                mention_by_id[row.mention_id]
                for row in proved_edges
                if row.role == "price"
                and mention_by_id[row.mention_id].mention_type == "price"
            },
            key=lambda row: (row.start, row.end, row.mention_id),
        )
        candidate_products = sorted(
            {
                mention_by_id[row.mention_id]
                for row in event_edges
                if row.role == "object"
                and mention_by_id[row.mention_id].mention_type == "product_or_hardware"
            },
            key=lambda row: (row.start, row.end, row.mention_id),
        )
        candidate_prices = sorted(
            {
                mention_by_id[row.mention_id]
                for row in event_edges
                if row.role == "price"
                and mention_by_id[row.mention_id].mention_type == "price"
            },
            key=lambda row: (row.start, row.end, row.mention_id),
        )
        if not candidate_products and not candidate_prices:
            continue
        event_tokens = _tokens_in_span(
            graph,
            event.document_span[0],
            event.document_span[1],
            scope_id=event.local_scope_id,
        )

        limitations: set[str] = set()
        competing_heads: list[MentionNodeR14] = []
        competing_prices = tuple(row.mention_id for row in candidate_prices[1:])
        path_edges: list[NominalEdgeR14] = []
        rule_id = "G90-CONFLICT"
        state = "AMBIGUOUS"
        family: str | None = None
        governing_heads: tuple[str, ...] = ()
        explicit_nominal_head: MentionNodeR14 | None = None

        if event.ambiguities or event.subject_state in {"ambiguous", "unproved"}:
            limitations.add("ambiguous_or_unproved_event_owner")
        if any(row.proof_state != "PROVED" for row in event_edges if row.role in {"object", "price"}):
            limitations.add("object_or_price_role_not_PROVED")
        if len(candidate_prices) != 1:
            limitations.add("unique_price_unproved")
        if competing_prices:
            limitations.add("multiple_price_conflict")
        if price_event_count_by_clause[event.clause_span] > 1:
            limitations.add("multiple_event_owner_or_price_conflict")

        covered_spans = [event.predicate_span]
        covered_spans.extend((row.start, row.end) for row in candidate_products)
        covered_spans.extend((row.start, row.end) for row in candidate_prices)
        covered_spans.extend(
            (mention_by_id[row.mention_id].start, mention_by_id[row.mention_id].end)
            for row in event_edges
            if mention_by_id[row.mention_id].mention_type
            in {"entity", "period", "quantity", "quantity_or_percent"}
        )
        words = tuple(row.normalized for row in event_tokens if row.kind == "WORD")
        bundle_tokens = [
            row
            for row in event_tokens
            if row.kind == "WORD"
            and row.normalized == "bundle"
        ]
        total_surface = bool(set(words).intersection(_BOUND_TOTAL))
        nominal_price_surface = bool(set(words).intersection({"price", "cost"}))
        nominal_price_tokens = [
            row
            for row in event_tokens
            if row.kind == "WORD"
            and row.normalized in {"price", "cost"}
        ]

        ignored_positive_words = (
            function_words
            | auxiliaries
            | coordinators
            | _BOUND_TOTAL
            | _REPORTING_WORDS
            | ({"price", "cost"} if nominal_price_surface else set())
            | {"hardware"}
        )
        for token in event_tokens:
            if (
                token.kind != "WORD"
                or _covered(token.start, token.end, covered_spans)
                or token.normalized in ignored_positive_words
                or token.normalized == "bundle"
            ):
                continue
            head = _new_head(graph=graph, token=token)
            private_nodes[head.mention_id] = head
            competing_heads.append(head)
            nearest = min(
                candidate_products,
                key=lambda row: abs(row.start - token.end),
                default=None,
            )
            if nearest is not None:
                relation_words = _tokens_between(
                    graph, token.end, nearest.start, scope_id=event.local_scope_id
                )
                nominal_edges.append(
                    NominalEdgeR14(
                        source_node_id=head.mention_id,
                        source_node_type="nominal_head",
                        destination_node_id=nearest.mention_id,
                        destination_node_type="product_or_hardware",
                        direction="head_to_complement",
                        relation=_nominal_relation(relation_words),
                        rule_id="G40-NOMINAL-HEAD",
                        proof_state="UNSUPPORTED",
                        spans=((head.start, head.end), (nearest.start, nearest.end)),
                        precedence=40,
                    )
                )

        if competing_heads:
            limitations.add("competing_or_unknown_governing_nominal_head")

        event_type_pricing = "pricing" in event.event_types
        predicate_lemma = event.predicate_normalized.split()[-1]
        product_priced_at = (
            predicate_lemma in {"price", "priced"}
            and bool(candidate_products)
            and bool(candidate_prices)
            and "at" in _tokens_between(
                graph,
                candidate_products[0].end,
                candidate_prices[0].start,
                scope_id=event.local_scope_id,
            )
        )
        explicit_price_of = (
            nominal_price_surface
            and bool(candidate_products)
            and bool(candidate_prices)
            and bool(
                {"of", "for"}.intersection(
                    _tokens_between(
                        graph,
                        nominal_price_tokens[0].end,
                        candidate_products[0].start,
                        scope_id=event.local_scope_id,
                    )
                )
            )
            and bool(
                predicate_lemma in _COPULAR
                or _COPULAR.intersection(
                    _tokens_between(
                        graph,
                        candidate_products[0].end,
                        candidate_prices[0].start,
                        scope_id=event.local_scope_id,
                    )
                )
            )
        )
        bundle_positive = (
            len(bundle_tokens) == 1
            and total_surface
            and bool(products)
            and len(prices) == 1
            and not competing_heads
            and not limitations
        )

        head_node: MentionNodeR14 | None = None
        if bundle_positive:
            head_node = _new_head(
                graph=graph, token=bundle_tokens[0], mention_type="bundle"
            )
            private_nodes[head_node.mention_id] = head_node
            rule_id = "G52-HARDWARE-BUNDLE"
            state = "PROVED"
            family = "all_hardware_bounded_bundle_total"
            governing_heads = (head_node.mention_id,)
            for product in products:
                path_edges.append(
                    NominalEdgeR14(
                        source_node_id=product.mention_id,
                        source_node_type="product_or_hardware",
                        destination_node_id=head_node.mention_id,
                        destination_node_type="bundle",
                        direction="member_to_bundle",
                        relation="bundle_member",
                        rule_id=rule_id,
                        proof_state="PROVED",
                        spans=((product.start, product.end), (head_node.start, head_node.end)),
                        precedence=52,
                    )
                )
        elif (
            len(products) == 1
            and len(prices) == 1
            and not competing_heads
            and not limitations
            and event_type_pricing
        ):
            head_node = products[0]
            governing_heads = (head_node.mention_id,)
            state = "PROVED"
            if product_priced_at:
                rule_id = "G51-PRICE-NOMINAL"
                family = "product_priced_at_price"
            elif explicit_price_of:
                rule_id = "G51-PRICE-NOMINAL"
                family = "explicit_price_or_cost_of_for_product_copular_amount"
                explicit_nominal_head = MentionNodeR14(
                    mention_type="nominal_head",
                    raw_value=nominal_price_tokens[0].raw,
                    normalized_value=nominal_price_tokens[0].normalized,
                    start=nominal_price_tokens[0].start,
                    end=nominal_price_tokens[0].end,
                    type_proof_rule_id="G40-NOMINAL-HEAD",
                    local_scope_id=nominal_price_tokens[0].local_scope_id,
                    proof_state="PROVED",
                    semantic_identity_ids=canonical_semantic_identity_ids_r14(
                        "nominal_head", nominal_price_tokens[0].normalized
                    ),
                )
                private_nodes[explicit_nominal_head.mention_id] = explicit_nominal_head
            else:
                rule_id = "G50-PRICE-DIRECT"
                family = "pricing_event_product_and_price_complement"
        else:
            if not candidate_products:
                limitations.add("priced_hardware_object_missing")
            if len(candidate_products) > 1 and not bundle_positive:
                limitations.add("unique_priced_hardware_object_unproved")
            if not event_type_pricing:
                limitations.add("affirmative_pricing_event_type_unproved")

        if state == "PROVED" and head_node is not None:
            if explicit_nominal_head is not None:
                path_edges.extend(
                    [
                        NominalEdgeR14(
                            source_node_id=event.event_id,
                            source_node_type="event",
                            destination_node_id=explicit_nominal_head.mention_id,
                            destination_node_type="nominal_head",
                            direction="event_to_nominal",
                            relation="event_object_head",
                            rule_id=rule_id,
                            proof_state="PROVED",
                            spans=(
                                event.predicate_span,
                                (
                                    explicit_nominal_head.start,
                                    explicit_nominal_head.end,
                                ),
                            ),
                            precedence=51,
                        ),
                        NominalEdgeR14(
                            source_node_id=prices[0].mention_id,
                            source_node_type="price",
                            destination_node_id=explicit_nominal_head.mention_id,
                            destination_node_type="nominal_head",
                            direction="price_to_nominal",
                            relation="price_attachment",
                            rule_id=rule_id,
                            proof_state="PROVED",
                            spans=(
                                (prices[0].start, prices[0].end),
                                (
                                    explicit_nominal_head.start,
                                    explicit_nominal_head.end,
                                ),
                            ),
                            precedence=51,
                        ),
                        NominalEdgeR14(
                            source_node_id=explicit_nominal_head.mention_id,
                            source_node_type="nominal_head",
                            destination_node_id=head_node.mention_id,
                            destination_node_type="product_or_hardware",
                            direction="head_to_complement",
                            relation="complement",
                            rule_id="G40-NOMINAL-HEAD",
                            proof_state="PROVED",
                            spans=(
                                (
                                    explicit_nominal_head.start,
                                    explicit_nominal_head.end,
                                ),
                                (head_node.start, head_node.end),
                            ),
                            precedence=40,
                        ),
                    ]
                )
            else:
                path_edges.extend([
                    NominalEdgeR14(
                        source_node_id=event.event_id,
                        source_node_type="event",
                        destination_node_id=head_node.mention_id,
                        destination_node_type=head_node.mention_type,
                        direction="event_to_nominal",
                        relation="event_object_head",
                        rule_id=rule_id,
                        proof_state="PROVED",
                        spans=(event.predicate_span, (head_node.start, head_node.end)),
                        precedence=int(rule_id[1:3]),
                    ),
                    NominalEdgeR14(
                        source_node_id=prices[0].mention_id,
                        source_node_type="price",
                        destination_node_id=head_node.mention_id,
                        destination_node_type=head_node.mention_type,
                        direction="price_to_nominal",
                        relation="price_attachment",
                        rule_id=rule_id,
                        proof_state="PROVED",
                        spans=((prices[0].start, prices[0].end), (head_node.start, head_node.end)),
                        precedence=int(rule_id[1:3]),
                    ),
                ])
        else:
            rule_id = "G90-CONFLICT"
            state = "AMBIGUOUS" if candidate_products or candidate_prices else "UNSUPPORTED"
            family = None
            governing_heads = ()

        nominal_edges.extend(path_edges)
        provenance: tuple[str, ...] = ()
        if candidate_products and candidate_prices:
            provenance = _tokens_between(
                graph,
                candidate_products[0].end,
                candidate_prices[0].start,
                scope_id=event.local_scope_id,
            )
        proofs.append(
            PricePathProofR14(
                event_id=event.event_id,
                product_mention_ids=tuple(row.mention_id for row in candidate_products),
                price_mention_ids=tuple(row.mention_id for row in candidate_prices),
                governing_head_mention_ids=governing_heads,
                edge_ids=tuple(row.edge_id for row in path_edges),
                rule_id=rule_id,
                state=state,
                family=family,
                competing_head_ids=tuple(row.mention_id for row in competing_heads),
                competing_price_ids=competing_prices,
                connector_surface_provenance=provenance,
                limitations=tuple(sorted(limitations)),
            )
        )

    output = PriceAttachmentGraphR14(
        event_graph_digest=graph.graph_digest,
        nodes=tuple(
            sorted(
                private_nodes.values(),
                key=lambda row: (
                    row.start,
                    row.end,
                    row.mention_type,
                    row.type_proof_rule_id,
                    row.node_digest,
                ),
            )
        ),
        edges=tuple(
            sorted(
                nominal_edges,
                key=lambda row: (
                    row.spans,
                    row.source_node_type,
                    row.relation,
                    row.destination_node_type,
                    row.edge_digest,
                ),
            )
        ),
        proofs=tuple(sorted(proofs, key=lambda row: (row.event_id, row.proof_digest))),
    )
    validate_price_attachment_graph_r14(output, graph=graph)
    return output


__all__ = ["build_price_attachment_graph_r14"]
