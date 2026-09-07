from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
import re
from typing import Any, Mapping, Sequence

from .dell_report_graph_schema_r14 import (
    EventArgumentGraphR14,
    PriceAttachmentGraphR14,
    validate_event_argument_graph_r14,
    validate_price_attachment_graph_r14,
)
from .dell_report_r14_common import canonical_digest, require
from .dell_report_r14_contracts import (
    TARGET_IDS,
    validate_target_topology_contract,
)


TARGET_GRAPH_VIEW_SCHEMA = "fin_ia_dell_03B_R14_target_graph_view_v1_0"
TARGET_DECISION_SCHEMA = "fin_ia_dell_03B_R14_target_decision_v1_0"


@dataclass(frozen=True)
class TypedNodeViewR14:
    node_id: str
    node_type: str
    semantic_identity_ids: tuple[str, ...]
    proof_state: str
    local_scope_id: str
    event_types: tuple[str, ...] = ()
    target_labels: tuple[str, ...] = ()
    predicate_operator_ids: tuple[str, ...] = ()
    polarity: str | None = None
    modality: str | None = None
    actuality: str | None = None
    lifecycle: str | None = None
    speech_mode: str | None = None
    assertion_owner_node_id: str | None = None
    assertion_owner_identity_ids: tuple[str, ...] = ()
    inference_barrier_ids: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "semantic_identity_ids": list(self.semantic_identity_ids),
            "proof_state": self.proof_state,
            "local_scope_id": self.local_scope_id,
            "event_types": list(self.event_types),
            "target_labels": list(self.target_labels),
            "predicate_operator_ids": list(self.predicate_operator_ids),
            "polarity": self.polarity,
            "modality": self.modality,
            "actuality": self.actuality,
            "lifecycle": self.lifecycle,
            "speech_mode": self.speech_mode,
            "assertion_owner_node_id": self.assertion_owner_node_id,
            "assertion_owner_identity_ids": list(
                self.assertion_owner_identity_ids
            ),
            "inference_barrier_ids": list(self.inference_barrier_ids),
        }


@dataclass(frozen=True)
class TypedEdgeViewR14:
    edge_id: str
    edge_family: str
    source_node_id: str
    destination_node_id: str
    edge_type: str
    proof_state: str
    semantic_identity_ids: tuple[str, ...] = ()
    subtype: str | None = None
    premise_proof_ids: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "edge_family": self.edge_family,
            "source_node_id": self.source_node_id,
            "destination_node_id": self.destination_node_id,
            "edge_type": self.edge_type,
            "proof_state": self.proof_state,
            "semantic_identity_ids": list(self.semantic_identity_ids),
            "subtype": self.subtype,
            "premise_proof_ids": list(self.premise_proof_ids),
        }


@dataclass(frozen=True)
class TypedProofViewR14:
    proof_id: str
    proof_family: str
    rule_id: str
    state: str
    event_id: str | None
    node_ids: tuple[str, ...]
    edge_ids: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "proof_id": self.proof_id,
            "proof_family": self.proof_family,
            "rule_id": self.rule_id,
            "state": self.state,
            "event_id": self.event_id,
            "node_ids": list(self.node_ids),
            "edge_ids": list(self.edge_ids),
        }


@dataclass(frozen=True)
class TargetGraphViewR14:
    event_graph_digest: str
    price_graph_digest: str
    graph_type_registry_digest: str
    typed_nodes: tuple[TypedNodeViewR14, ...]
    typed_edges: tuple[TypedEdgeViewR14, ...]
    proofs: tuple[TypedProofViewR14, ...]

    @cached_property
    def view_digest(self) -> str:
        return canonical_digest(self._body())

    def _body(self) -> dict[str, Any]:
        return {
            "schema_version": TARGET_GRAPH_VIEW_SCHEMA,
            "event_graph_digest": self.event_graph_digest,
            "price_graph_digest": self.price_graph_digest,
            "graph_type_registry_digest": self.graph_type_registry_digest,
            "typed_nodes": [row.as_dict() for row in self.typed_nodes],
            "typed_edges": [row.as_dict() for row in self.typed_edges],
            "proofs": [row.as_dict() for row in self.proofs],
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self._body(), "view_digest": self.view_digest}


@dataclass(frozen=True)
class TargetDecisionR14:
    target_id: str
    outcome: str
    event_ids: tuple[str, ...]
    proof_ids: tuple[str, ...]
    satisfied_roles: tuple[str, ...]
    missing_roles: tuple[str, ...]
    reason_codes: tuple[str, ...]

    @cached_property
    def decision_digest(self) -> str:
        return canonical_digest(self._body())

    def _body(self) -> dict[str, Any]:
        return {
            "schema_version": TARGET_DECISION_SCHEMA,
            "target_id": self.target_id,
            "outcome": self.outcome,
            "event_ids": list(self.event_ids),
            "proof_ids": list(self.proof_ids),
            "satisfied_roles": list(self.satisfied_roles),
            "missing_roles": list(self.missing_roles),
            "reason_codes": list(self.reason_codes),
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self._body(), "decision_digest": self.decision_digest}


def build_target_graph_view_r14(
    *,
    event_graph: EventArgumentGraphR14,
    price_graph: PriceAttachmentGraphR14,
) -> TargetGraphViewR14:
    validate_event_argument_graph_r14(event_graph)
    validate_price_attachment_graph_r14(price_graph, graph=event_graph)

    nodes: list[TypedNodeViewR14] = []
    event_mention_by_id = {row.mention_id: row for row in event_graph.mentions}
    for event in event_graph.events:
        owner = (
            event_mention_by_id.get(event.assertion_owner_mention_id)
            if event.assertion_owner_mention_id is not None
            else None
        )
        nodes.append(
            TypedNodeViewR14(
                node_id=event.event_id,
                node_type="event",
                semantic_identity_ids=tuple(
                    sorted(
                        {
                            *(f"EVENT_TYPE::{row}" for row in event.event_types),
                            *(f"TARGET::{row}" for row in event.semantic_labels),
                            *event.semantic_operator_ids,
                        }
                    )
                ),
                proof_state="AMBIGUOUS" if event.ambiguities else "PROVED",
                local_scope_id=event.local_scope_id,
                event_types=event.event_types,
                target_labels=event.semantic_labels,
                predicate_operator_ids=event.semantic_operator_ids,
                polarity=event.polarity,
                modality=event.modality,
                actuality=event.actuality,
                lifecycle=event.lifecycle,
                speech_mode=event.speech_mode,
                assertion_owner_node_id=event.assertion_owner_mention_id,
                assertion_owner_identity_ids=(
                    owner.semantic_identity_ids if owner is not None else ()
                ),
                inference_barrier_ids=event.inference_barrier_ids,
            )
        )
    for mention in (*event_graph.mentions, *price_graph.nodes):
        nodes.append(
            TypedNodeViewR14(
                node_id=mention.mention_id,
                node_type=mention.mention_type,
                semantic_identity_ids=mention.semantic_identity_ids,
                proof_state=mention.proof_state,
                local_scope_id=mention.local_scope_id,
            )
        )

    edges: list[TypedEdgeViewR14] = []
    for edge in event_graph.role_edges:
        edges.append(
            TypedEdgeViewR14(
                edge_id=edge.edge_id,
                edge_family="event_role",
                source_node_id=edge.event_id,
                destination_node_id=edge.mention_id,
                edge_type=edge.role,
                proof_state=edge.proof_state,
                premise_proof_ids=edge.premise_proof_ids,
            )
        )
    for edge in event_graph.temporal_edges:
        edges.append(
            TypedEdgeViewR14(
                edge_id=edge.edge_id,
                edge_family="temporal",
                source_node_id=edge.event_id,
                destination_node_id=edge.period_mention_id,
                edge_type="period",
                proof_state=edge.proof_state,
                premise_proof_ids=edge.premise_proof_ids,
            )
        )
    role_by_id = {row.edge_id: row for row in event_graph.role_edges}
    for edge in event_graph.target_bridge_edges:
        edges.append(
            TypedEdgeViewR14(
                edge_id=edge.edge_id,
                edge_family="event_role_or_bridge",
                source_node_id=edge.source_event_id,
                destination_node_id=edge.destination_event_id,
                edge_type="typed_target_bridge",
                proof_state=edge.proof_state,
                semantic_identity_ids=edge.shared_semantic_identity_ids,
                subtype=edge.bridge_type,
                premise_proof_ids=tuple(
                    sorted(
                        {
                            proof_id
                            for edge_id in edge.premise_edge_ids
                            for proof_id in role_by_id[edge_id].premise_proof_ids
                        }
                    )
                ),
            )
        )
    for edge in price_graph.edges:
        edges.append(
            TypedEdgeViewR14(
                edge_id=edge.edge_id,
                edge_family="nominal_relation",
                source_node_id=edge.source_node_id,
                destination_node_id=edge.destination_node_id,
                edge_type=edge.relation,
                proof_state=edge.proof_state,
                subtype=edge.rule_id,
            )
        )

    proofs = [
        TypedProofViewR14(
            proof_id=row.proof_id,
            proof_family="structural",
            rule_id=row.rule_id,
            state=row.state,
            event_id=(
                row.premise_node_ids[0]
                if row.premise_node_ids
                and row.premise_node_ids[0].startswith("EVENT::R14::")
                else None
            ),
            node_ids=row.premise_node_ids,
            edge_ids=row.premise_edge_ids,
        )
        for row in event_graph.proofs
    ]
    proofs.extend(
        TypedProofViewR14(
            proof_id=row.proof_id,
            proof_family="price_path",
            rule_id=row.rule_id,
            state=row.state,
            event_id=row.event_id,
            node_ids=tuple(
                (
                    *row.product_mention_ids,
                    *row.price_mention_ids,
                    *row.governing_head_mention_ids,
                )
            ),
            edge_ids=row.edge_ids,
        )
        for row in price_graph.proofs
    )
    output = TargetGraphViewR14(
        event_graph_digest=event_graph.graph_digest,
        price_graph_digest=price_graph.graph_digest,
        graph_type_registry_digest=event_graph.graph_type_registry_digest,
        typed_nodes=tuple(sorted(nodes, key=lambda row: (row.node_type, row.node_id))),
        typed_edges=tuple(
            sorted(edges, key=lambda row: (row.edge_family, row.edge_type, row.edge_id))
        ),
        proofs=tuple(sorted(proofs, key=lambda row: (row.proof_family, row.proof_id))),
    )
    validate_target_graph_view_r14(output)
    return output


def validate_target_graph_view_r14(view: TargetGraphViewR14) -> None:
    node_by_id = {row.node_id: row for row in view.typed_nodes}
    edge_by_id = {row.edge_id: row for row in view.typed_edges}
    proof_by_id = {row.proof_id: row for row in view.proofs}
    require(len(node_by_id) == len(view.typed_nodes), "R14_target_view_node_collision")
    require(len(edge_by_id) == len(view.typed_edges), "R14_target_view_edge_collision")
    require(len(proof_by_id) == len(view.proofs), "R14_target_view_proof_collision")
    require(
        tuple(view.typed_nodes)
        == tuple(sorted(view.typed_nodes, key=lambda row: (row.node_type, row.node_id))),
        "R14_target_view_node_order_invalid",
    )
    require(
        tuple(view.typed_edges)
        == tuple(
            sorted(
                view.typed_edges,
                key=lambda row: (row.edge_family, row.edge_type, row.edge_id),
            )
        ),
        "R14_target_view_edge_order_invalid",
    )
    require(
        tuple(view.proofs)
        == tuple(sorted(view.proofs, key=lambda row: (row.proof_family, row.proof_id))),
        "R14_target_view_proof_order_invalid",
    )
    for node in view.typed_nodes:
        require(
            tuple(sorted(set(node.semantic_identity_ids)))
            == node.semantic_identity_ids,
            "R14_target_view_node_identity_invalid",
        )
        if node.node_type == "event":
            owner_contract_valid = (
                node.assertion_owner_node_id is None
                and not node.assertion_owner_identity_ids
            ) or (
                node.assertion_owner_node_id in node_by_id
                and node_by_id[node.assertion_owner_node_id].node_type == "entity"
                and node.assertion_owner_identity_ids
                == node_by_id[node.assertion_owner_node_id].semantic_identity_ids
            )
            require(
                node.predicate_operator_ids
                and tuple(sorted(set(node.predicate_operator_ids)))
                == node.predicate_operator_ids
                and node.polarity in {"affirmative", "negative"}
                and node.modality in {"asserted", "modal"}
                and node.actuality in {"actual_or_current", "forward_looking"}
                and node.lifecycle in {"active_or_unspecified", "inactive"}
                and node.speech_mode
                in {"direct_or_unspecified", "issuer_reported", "reported_speech"}
                and owner_contract_valid,
                "R14_target_view_event_assertion_contract_invalid",
            )
            require(
                tuple(sorted(set(node.inference_barrier_ids)))
                == node.inference_barrier_ids,
                "R14_target_view_event_inference_barrier_invalid",
            )
        else:
            require(
                not node.predicate_operator_ids
                and node.polarity is None
                and node.modality is None
                and node.actuality is None
                and node.lifecycle is None
                and node.speech_mode is None
                and node.assertion_owner_node_id is None
                and not node.assertion_owner_identity_ids,
                "R14_target_view_non_event_assertion_leak",
            )
            require(
                not node.inference_barrier_ids,
                "R14_target_view_non_event_inference_barrier_leak",
            )
    for edge in view.typed_edges:
        require(
            edge.source_node_id in node_by_id
            and edge.destination_node_id in node_by_id,
            "R14_target_view_edge_orphan",
        )
    for proof in view.proofs:
        require(
            set(proof.node_ids).issubset(node_by_id)
            and set(proof.edge_ids).issubset(edge_by_id),
            "R14_target_view_proof_orphan",
        )
    for edge in view.typed_edges:
        require(
            set(edge.premise_proof_ids).issubset(proof_by_id),
            "R14_target_view_edge_premise_proof_orphan",
        )


def _identity_fragment(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", value.upper()).strip("_")


def _ontology_identity_sets(target: Mapping[str, Any]) -> tuple[set[str], set[str]]:
    ontology = target["candidate_ontology"]
    entities = {
        f"ENTITY::{_identity_fragment(str(row))}"
        for row in ontology["entity_terms"]
    }
    products: set[str] = set()
    for row in ontology["product_terms"]:
        value = _identity_fragment(str(row))
        products.add(f"PRODUCT::{value}")
        products.update(f"PRODUCT::{part}" for part in value.split("_") if part)
    return entities, products


def _node_matches_role_identity(
    *, node: TypedNodeViewR14, role_name: str, target: Mapping[str, Any]
) -> bool:
    identities = set(node.semantic_identity_ids)
    entities, products = _ontology_identity_sets(target)
    if role_name in {
        "dell_subject",
        "upstream_Dell_allocation",
        "directional_Dell_bridge",
        "Dell_AI_server_product",
    }:
        return bool(identities.intersection({"ENTITY::DELL", "PRODUCT::POWEREDGE"}))
    if role_name == "named_supplier":
        return bool(identities.intersection(entities - {"ENTITY::DELL"}))
    if role_name == "hbm_subject":
        return any(value.startswith("PRODUCT::HBM") for value in identities)
    if role_name == "process_owner":
        return bool(identities.intersection(entities))
    if role_name in {"relevant_supply", "bounded_object"}:
        return bool(identities.intersection(products)) or node.node_type in {
            "bundle",
            "nominal_head",
        }
    if role_name in {"physical_server_quantity", "observed_measure", "timing_surface"}:
        return True
    return True


def _event_role_evidence(
    *,
    event_id: str,
    role: Mapping[str, Any],
    target: Mapping[str, Any],
    node_by_id: Mapping[str, TypedNodeViewR14],
    edges: Sequence[TypedEdgeViewR14],
    registry: Mapping[str, Any],
) -> tuple[TypedEdgeViewR14, ...]:
    binding = registry["target_edge_bindings"][role["edge"]]
    allowed_types = set(binding["allowed_types"])
    edge_family = binding["edge_family"]
    concrete_types = set(
        registry["target_mention_type_bindings"][role["mention_type"]]
    )
    output: list[TypedEdgeViewR14] = []
    for edge in edges:
        if edge.proof_state != "PROVED":
            continue
        if edge_family == "event_type":
            continue
        if edge.edge_type not in allowed_types:
            continue
        if edge_family == "event_role_or_bridge":
            if edge.edge_family not in {"event_role", "event_role_or_bridge"}:
                continue
        elif edge.edge_family != edge_family:
            continue
        if edge.source_node_id != event_id:
            continue
        node = node_by_id[edge.destination_node_id]
        if edge.edge_type == "typed_target_bridge":
            if role["role"] == "directional_Dell_bridge" and (
                edge.subtype == "HBM_STATE_TO_DELL"
                or "ENTITY::DELL" in edge.semantic_identity_ids
                or "PRODUCT::POWEREDGE" in edge.semantic_identity_ids
            ):
                output.append(edge)
            continue
        if node.node_type not in concrete_types:
            continue
        required_identities = set(role.get("required_semantic_identity_ids") or ())
        if required_identities and not required_identities.intersection(
            node.semantic_identity_ids
        ):
            continue
        if _node_matches_role_identity(node=node, role_name=role["role"], target=target):
            output.append(edge)
    return tuple(output)


def _cardinality_satisfied(cardinality: str, count: int) -> bool:
    if cardinality == "at_least_one":
        return count >= 1
    if cardinality in {"exactly_one", "exactly_one_or_one_canonical_entity"}:
        return count == 1
    if cardinality == "exactly_one_or_proved_hardware_bundle":
        return count == 1
    return False


def _event_assertion_complete_r14(event: TypedNodeViewR14) -> bool:
    """Closed factual-authority gate shared by all six target compilers."""
    return (
        event.proof_state == "PROVED"
        and event.polarity == "affirmative"
        and event.modality == "asserted"
        and event.actuality == "actual_or_current"
        and event.lifecycle == "active_or_unspecified"
        and event.speech_mode in {"direct_or_unspecified", "issuer_reported"}
        and event.assertion_owner_node_id is not None
        and bool(event.assertion_owner_identity_ids)
        and bool(event.predicate_operator_ids)
    )


def compile_target_decisions_r14(
    *, view: TargetGraphViewR14, topology_contract: Mapping[str, Any]
) -> tuple[TargetDecisionR14, ...]:
    validate_target_graph_view_r14(view)
    validate_target_topology_contract(topology_contract)
    registry = topology_contract["graph_type_registry"]
    require(
        canonical_digest(registry) == view.graph_type_registry_digest,
        "R14_target_compiler_registry_digest_mismatch",
    )
    node_by_id = {row.node_id: row for row in view.typed_nodes}
    event_nodes = [row for row in view.typed_nodes if row.node_type == "event"]
    proved_price_by_event: dict[str, list[TypedProofViewR14]] = {}
    for proof in view.proofs:
        if (
            proof.proof_family == "price_path"
            and proof.state == "PROVED"
            and proof.event_id is not None
        ):
            proved_price_by_event.setdefault(proof.event_id, []).append(proof)
    edges_by_source: dict[str, tuple[TypedEdgeViewR14, ...]] = {}
    edge_rows_by_source: dict[str, list[TypedEdgeViewR14]] = {}
    predicate_proof_ids_by_event: dict[str, set[str]] = {}
    proved_bridge_edges: list[TypedEdgeViewR14] = []
    for edge in view.typed_edges:
        edge_rows_by_source.setdefault(edge.source_node_id, []).append(edge)
        if edge.edge_type == "typed_target_bridge" and edge.proof_state == "PROVED":
            proved_bridge_edges.append(edge)
        if edge.edge_family == "event_role" and edge.edge_type == "predicate":
            predicate_proof_ids_by_event.setdefault(
                edge.source_node_id, set()
            ).update(edge.premise_proof_ids)
    edges_by_source = {
        event_id: tuple(rows) for event_id, rows in edge_rows_by_source.items()
    }
    decisions: list[TargetDecisionR14] = []
    for target in sorted(
        topology_contract["targets"], key=lambda row: str(row["target_id"])
    ):
        target_id = str(target["target_id"])
        candidates = [
            row
            for row in event_nodes
            if target_id in row.target_labels
            and row.proof_state in {"PROVED", "AMBIGUOUS"}
        ]
        if not candidates:
            decisions.append(
                TargetDecisionR14(
                    target_id=target_id,
                    outcome="N",
                    event_ids=(),
                    proof_ids=(),
                    satisfied_roles=(),
                    missing_roles=(),
                    reason_codes=("no_target_candidate",),
                )
            )
            continue

        maximum = int(target["event_cardinality"]["maximum"])
        combinations: list[tuple[TypedNodeViewR14, ...]] = [(row,) for row in candidates]
        if maximum == 2:
            # Two-event target candidates exist only when the graph has already
            # proved the declared directed bridge.  Enumerating the Cartesian
            # product is both semantically wrong and quadratic on long text.
            candidate_by_id = {row.node_id: row for row in candidates}
            allowed_bridge_types = {
                row["bridge_id"] for row in target["allowed_bridges"]
            }
            bridged_pairs = {
                (edge.source_node_id, edge.destination_node_id)
                for edge in proved_bridge_edges
                if edge.subtype in allowed_bridge_types
                and edge.source_node_id in candidate_by_id
                and edge.destination_node_id in candidate_by_id
            }
            combinations.extend(
                (candidate_by_id[source], candidate_by_id[destination])
                for source, destination in sorted(bridged_pairs)
            )

        winning: tuple[tuple[TypedNodeViewR14, ...], tuple[str, ...], tuple[str, ...]] | None = None
        best_missing: tuple[str, ...] | None = None
        best_satisfied: tuple[str, ...] = ()
        best_proof_ids: tuple[str, ...] = ()
        best_barriers: tuple[str, ...] = ()
        for events in combinations:
            event_ids = {row.node_id for row in events}
            required_event_type = target["event_cardinality"]["event_type"]
            if not any(required_event_type in row.event_types for row in events):
                continue
            selected_bridge: TypedEdgeViewR14 | None = None
            if len(events) == 2:
                allowed_bridge_types = {
                    row["bridge_id"] for row in target["allowed_bridges"]
                }
                selected_bridge_rows = [
                    row
                    for row in edges_by_source.get(events[0].node_id, ())
                    if row.edge_type == "typed_target_bridge"
                    and row.subtype in allowed_bridge_types
                    and {row.source_node_id, row.destination_node_id} == event_ids
                    and row.proof_state == "PROVED"
                ]
                if len(selected_bridge_rows) != 1:
                    continue
                selected_bridge = selected_bridge_rows[0]

            satisfied: list[str] = []
            missing: list[str] = []
            proof_ids: set[str] = {
                proof_id
                for event in events
                for proof_id in predicate_proof_ids_by_event.get(event.node_id, ())
            }
            for role in target["required_roles"]:
                role_name = str(role["role"])
                binding = registry["target_edge_bindings"][role["edge"]]
                if binding["edge_family"] == "event_type":
                    count = sum(
                        bool(set(row.event_types).intersection(binding["allowed_types"]))
                        for row in events
                    )
                    evidence: tuple[TypedEdgeViewR14, ...] = ()
                elif target_id == "DELL-RSQ-03A-TARGET-ASP" and role_name in {
                    "price_surface",
                    "bounded_object",
                }:
                    price_proofs = [
                        proof
                        for row in events
                        for proof in proved_price_by_event.get(row.node_id, ())
                        if proof.rule_id in target["required_price_proof_rules"]
                    ]
                    count = len(price_proofs)
                    proof_ids.update(row.proof_id for row in price_proofs)
                    evidence = ()
                else:
                    role_events = events
                    if (
                        selected_bridge is not None
                        and bool(role["event_local"])
                        and selected_bridge.subtype == "HBM_STATE_TO_DELL"
                    ):
                        role_events = tuple(
                            row
                            for row in events
                            if row.node_id == selected_bridge.source_node_id
                        )
                    evidence_rows = [
                        edge
                        for event in role_events
                        for edge in _event_role_evidence(
                            event_id=event.node_id,
                            role=role,
                            target=target,
                            node_by_id=node_by_id,
                            edges=edges_by_source.get(event.node_id, ()),
                            registry=registry,
                        )
                    ]
                    evidence = tuple({row.edge_id: row for row in evidence_rows}.values())
                    count = len(evidence)
                    proof_ids.update(
                        proof_id
                        for row in evidence
                        for proof_id in row.premise_proof_ids
                    )
                if _cardinality_satisfied(str(role["cardinality"]), count):
                    satisfied.append(role_name)
                else:
                    missing.append(role_name)
            state_ambiguous = any(row.proof_state != "PROVED" for row in events)
            assertion_incomplete = any(
                not _event_assertion_complete_r14(row) for row in events
            )
            if assertion_incomplete:
                missing.append("affirmative_current_actual_assertion")
            forbidden = set(str(row) for row in target["forbidden_inference"])
            active_barriers = tuple(
                sorted(
                    forbidden.intersection(
                        barrier
                        for event in events
                        for barrier in event.inference_barrier_ids
                    )
                )
            )
            if active_barriers:
                missing.append("forbidden_inference_clear")
            if (
                not missing
                and not state_ambiguous
                and not assertion_incomplete
                and not active_barriers
            ):
                winning = (
                    events,
                    tuple(sorted(satisfied)),
                    tuple(sorted(proof_ids)),
                )
                break
            if best_missing is None or len(missing) < len(best_missing):
                best_missing = tuple(sorted(missing))
                best_satisfied = tuple(sorted(satisfied))
                best_proof_ids = tuple(sorted(proof_ids))
                best_barriers = active_barriers

        if winning is not None:
            events, satisfied, proof_ids = winning
            decisions.append(
                TargetDecisionR14(
                    target_id=target_id,
                    outcome="C",
                    event_ids=tuple(sorted(row.node_id for row in events)),
                    proof_ids=proof_ids,
                    satisfied_roles=satisfied,
                    missing_roles=(),
                    reason_codes=("all_required_typed_proofs_PROVED",),
                )
            )
        else:
            decisions.append(
                TargetDecisionR14(
                    target_id=target_id,
                    outcome="P",
                    event_ids=tuple(sorted(row.node_id for row in candidates)),
                    proof_ids=best_proof_ids,
                    satisfied_roles=best_satisfied,
                    missing_roles=best_missing or tuple(
                        sorted(str(row["role"]) for row in target["required_roles"])
                    ),
                    reason_codes=tuple(
                        sorted(
                            {
                                "candidate_missing_ambiguous_or_unsupported_proof",
                                *(f"forbidden_inference:{row}" for row in best_barriers),
                            }
                        )
                    ),
                )
            )
    require(
        tuple(row.target_id for row in decisions) == TARGET_IDS,
        "R14_target_compiler_decision_population_or_order_invalid",
    )
    return tuple(decisions)


__all__ = [
    "TARGET_DECISION_SCHEMA",
    "TARGET_GRAPH_VIEW_SCHEMA",
    "TargetDecisionR14",
    "TargetGraphViewR14",
    "TypedEdgeViewR14",
    "TypedNodeViewR14",
    "TypedProofViewR14",
    "build_target_graph_view_r14",
    "compile_target_decisions_r14",
    "validate_target_graph_view_r14",
]
