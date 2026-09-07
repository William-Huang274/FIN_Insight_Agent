from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .reviewed_evidence_pack import canonical_digest


RESEARCH_CONTEXT_CONTRACT_SCHEMA_VERSION = (
    "fin_ia_research_context_closure_contract_v1_0"
)


class ResearchContextError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ResearchContextError(code)


def _strings(value: object, code: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    _require(isinstance(value, list), code)
    rows = tuple(str(item).strip() for item in value)
    _require(
        (allow_empty or bool(rows))
        and all(rows)
        and len(rows) == len(set(rows)),
        code,
    )
    return rows


@dataclass(frozen=True)
class EvidenceRequestSourceClass:
    source_class: str
    allowed_gap_codes: tuple[str, ...]
    availability_signal: str
    executable_route_ids: tuple[str, ...]
    intent_mode: str
    allowed_source_types: tuple[str, ...]
    forbidden_intent_terms: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_class": self.source_class,
            "allowed_gap_codes": list(self.allowed_gap_codes),
            "availability_signal": self.availability_signal,
            "executable_route_ids": list(self.executable_route_ids),
            "intent_mode": self.intent_mode,
            "allowed_source_types": list(self.allowed_source_types),
            "forbidden_intent_terms": list(self.forbidden_intent_terms),
        }


def load_research_context_contract(payload: Mapping[str, Any]) -> dict[str, Any]:
    expected = {
        "role_method_packs",
        "evidence_request_source_classes",
        "gap_facet_query_bindings",
        "non_retrieval_gap_codes",
        "graph_context",
        "receipts",
    }
    _require(set(payload) == expected, "research_context_contract_fields_invalid")

    raw_packs = payload.get("role_method_packs")
    _require(isinstance(raw_packs, list), "research_context_role_packs_invalid")
    packs: list[dict[str, Any]] = []
    cell_ids: set[str] = set()
    pack_ids: set[str] = set()
    for raw in raw_packs:
        _require(isinstance(raw, Mapping), "research_context_role_pack_invalid")
        _require(
            set(raw)
            == {
                "pack_id",
                "cell_id",
                "role_id",
                "minimum_consumed_method_steps",
                "method_steps",
            },
            "research_context_role_pack_invalid",
        )
        pack_id = str(raw.get("pack_id") or "").strip()
        cell_id = str(raw.get("cell_id") or "").strip()
        role_id = str(raw.get("role_id") or "").strip()
        steps = raw.get("method_steps")
        _require(
            pack_id
            and cell_id.startswith("CELL::")
            and role_id
            and pack_id not in pack_ids
            and cell_id not in cell_ids
            and isinstance(steps, list)
            and bool(steps),
            "research_context_role_pack_invalid",
        )
        step_refs: set[str] = set()
        clean_steps = []
        for step in steps:
            _require(
                isinstance(step, Mapping)
                and set(step) == {"method_step_ref", "instruction_zh"},
                "research_context_method_step_invalid",
            )
            ref = str(step.get("method_step_ref") or "").strip()
            instruction = str(step.get("instruction_zh") or "").strip()
            _require(
                ref.startswith("METHOD::")
                and ref not in step_refs
                and instruction,
                "research_context_method_step_invalid",
            )
            step_refs.add(ref)
            clean_steps.append({"method_step_ref": ref, "instruction_zh": instruction})
        minimum = int(raw.get("minimum_consumed_method_steps") or 0)
        _require(
            1 <= minimum <= len(clean_steps),
            "research_context_method_consumption_minimum_invalid",
        )
        pack_ids.add(pack_id)
        cell_ids.add(cell_id)
        body = {
            "pack_id": pack_id,
            "cell_id": cell_id,
            "role_id": role_id,
            "minimum_consumed_method_steps": minimum,
            "method_steps": clean_steps,
        }
        packs.append({**body, "pack_digest": canonical_digest(body)})

    raw_classes = payload.get("evidence_request_source_classes")
    _require(
        isinstance(raw_classes, list) and bool(raw_classes),
        "research_context_source_classes_invalid",
    )
    source_classes: list[EvidenceRequestSourceClass] = []
    source_ids: set[str] = set()
    allowed_modes = {
        "product_intent_required_metric_context_optional",
        "metric_intent_required_product_intent_forbidden",
    }
    for raw in raw_classes:
        _require(
            isinstance(raw, Mapping)
            and set(raw)
            == {
                "source_class",
                "allowed_gap_codes",
                "availability_signal",
                "executable_route_ids",
                "intent_mode",
                "allowed_source_types",
                "forbidden_intent_terms",
            },
            "research_context_source_class_invalid",
        )
        source_id = str(raw.get("source_class") or "").strip()
        mode = str(raw.get("intent_mode") or "").strip()
        _require(
            source_id and source_id not in source_ids and mode in allowed_modes,
            "research_context_source_class_invalid",
        )
        source_ids.add(source_id)
        source_classes.append(
            EvidenceRequestSourceClass(
                source_class=source_id,
                allowed_gap_codes=_strings(
                    raw.get("allowed_gap_codes"),
                    "research_context_source_gap_codes_invalid",
                ),
                availability_signal=str(raw.get("availability_signal") or "").strip(),
                executable_route_ids=_strings(
                    raw.get("executable_route_ids"),
                    "research_context_executable_routes_invalid",
                ),
                intent_mode=mode,
                allowed_source_types=_strings(
                    raw.get("allowed_source_types"),
                    "research_context_source_types_invalid",
                ),
                forbidden_intent_terms=_strings(
                    raw.get("forbidden_intent_terms"),
                    "research_context_forbidden_intents_invalid",
                    allow_empty=True,
                ),
            )
        )

    raw_bindings = payload.get("gap_facet_query_bindings")
    _require(
        isinstance(raw_bindings, list) and bool(raw_bindings),
        "research_context_gap_facet_bindings_invalid",
    )
    bindings: list[dict[str, Any]] = []
    bound_gap_facets: set[str] = set()
    for raw in raw_bindings:
        _require(
            isinstance(raw, Mapping)
            and set(raw)
            == {
                "gap_facet_id",
                "requested_query_facet_ids",
                "typed_metric_ids",
            },
            "research_context_gap_facet_binding_invalid",
        )
        gap_facet_id = str(raw.get("gap_facet_id") or "").strip()
        query_facets = _strings(
            raw.get("requested_query_facet_ids"),
            "research_context_gap_query_facets_invalid",
        )
        typed_metrics = _strings(
            raw.get("typed_metric_ids"),
            "research_context_gap_metric_ids_invalid",
            allow_empty=True,
        )
        _require(
            gap_facet_id and gap_facet_id not in bound_gap_facets,
            "research_context_gap_facet_binding_invalid",
        )
        bound_gap_facets.add(gap_facet_id)
        bindings.append(
            {
                "gap_facet_id": gap_facet_id,
                "requested_query_facet_ids": list(query_facets),
                "typed_metric_ids": list(typed_metrics),
            }
        )

    non_retrieval = _strings(
        payload.get("non_retrieval_gap_codes"),
        "research_context_non_retrieval_gaps_invalid",
        allow_empty=True,
    )
    graph = payload.get("graph_context")
    _require(
        isinstance(graph, Mapping)
        and set(graph)
        == {
            "current_case_and_current_governed_objects_only",
            "archived_graph_rows_forbidden",
            "maximum_nodes_per_cell",
            "maximum_edges_per_cell",
            "minimum_consumed_graph_edges_when_available",
            "scope_edges_do_not_grant_fact_authority",
        }
        and graph.get("current_case_and_current_governed_objects_only") is True
        and graph.get("archived_graph_rows_forbidden") is True
        and graph.get("scope_edges_do_not_grant_fact_authority") is True
        and 1 <= int(graph.get("maximum_nodes_per_cell") or 0) <= 64
        and 1 <= int(graph.get("maximum_edges_per_cell") or 0) <= 128
        and 0
        <= int(graph.get("minimum_consumed_graph_edges_when_available") or 0)
        <= int(graph.get("maximum_edges_per_cell") or 0),
        "research_context_graph_contract_invalid",
    )
    receipts = payload.get("receipts")
    _require(
        isinstance(receipts, Mapping)
        and dict(receipts)
        == {
            "selection_required": True,
            "compression_required": True,
            "injection_required": True,
            "model_consumption_refs_required": True,
        },
        "research_context_receipt_contract_invalid",
    )
    return {
        "role_method_packs": packs,
        "evidence_request_source_classes": [row.as_dict() for row in source_classes],
        "gap_facet_query_bindings": bindings,
        "non_retrieval_gap_codes": list(non_retrieval),
        "graph_context": deepcopy(dict(graph)),
        "receipts": deepcopy(dict(receipts)),
    }


def _route_signal_availability(controlled_plan: Mapping[str, Any]) -> dict[str, bool]:
    summary = controlled_plan.get("summary") or {}
    return {
        "current_narrative_object_store": (
            controlled_plan.get("status") == "controlled_research_plan_zero_call_executed"
            and int(summary.get("nonempty_lane_count") or 0) > 0
        ),
        "company_financial_fact_mart": (
            int(summary.get("typed_fact_resolved_count") or 0) > 0
        ),
        # These stores/providers are not implemented by the current controlled
        # Runtime.  A route-policy declaration alone must never make them look
        # executable to the model.
        "market_snapshot_fact_mart": False,
        "commercial_data_provider": False,
    }


def compile_evidence_request_route_catalog(
    *,
    context_contract: Mapping[str, Any],
    controlled_plan: Mapping[str, Any],
    gap_cards: Sequence[Mapping[str, Any]],
    objective: Mapping[str, Any],
) -> dict[str, Any]:
    availability = _route_signal_availability(controlled_plan)
    objective_sources = {
        str(value) for value in objective.get("allowed_source_types") or ()
    }
    forbidden_sources = {
        str(value) for value in objective.get("forbidden_source_types") or ()
    }
    classes = context_contract["evidence_request_source_classes"]
    binding_by_gap_facet = {
        str(row["gap_facet_id"]): row
        for row in context_contract["gap_facet_query_bindings"]
    }
    non_retrieval = set(context_contract["non_retrieval_gap_codes"])
    decisions: list[dict[str, Any]] = []
    for gap in gap_cards:
        gap_code = str(gap.get("gap_code") or "")
        gap_facet_id = str(gap.get("facet_id") or "")
        binding = binding_by_gap_facet.get(gap_facet_id)
        _require(binding is not None, "research_context_gap_facet_unbound")
        candidates = [
            deepcopy(dict(row))
            for row in classes
            if gap_code in set(row["allowed_gap_codes"])
        ]
        available: list[dict[str, Any]] = []
        unavailable: list[dict[str, Any]] = []
        for row in candidates:
            permitted_sources = sorted(
                (
                    set(row["allowed_source_types"])
                    & objective_sources
                )
                - forbidden_sources
            )
            signal_available = availability.get(row["availability_signal"]) is True
            result = {
                "source_class": row["source_class"],
                "availability_signal": row["availability_signal"],
                "executable_route_ids": list(row["executable_route_ids"]),
                "intent_mode": row["intent_mode"],
                "acceptable_source_types": permitted_sources,
                "forbidden_intent_terms": list(row["forbidden_intent_terms"]),
            }
            if signal_available and permitted_sources:
                available.append(result)
            else:
                unavailable.append(
                    {
                        **result,
                        "unavailable_reason": (
                            "runtime_route_unavailable"
                            if not signal_available
                            else "source_type_not_allowed_by_objective"
                        ),
                    }
                )
        if gap_code in non_retrieval:
            status = "non_retrieval_gap"
        elif available:
            status = "requestable_on_current_runtime"
        else:
            status = "typed_gap_no_executable_route"
        decisions.append(
            {
                "gap_ref": str(gap["gap_ref"]),
                "slot_id": str(gap["slot_id"]),
                "declared_gap_facet_id": str(gap.get("facet_id") or ""),
                "requested_query_facet_ids": list(
                    binding["requested_query_facet_ids"]
                ),
                "typed_metric_ids": list(binding["typed_metric_ids"]),
                "gap_code": gap_code,
                "route_status": status,
                "available_source_routes": available,
                "unavailable_source_routes": unavailable,
            }
        )
    body = {
        "schema_version": "fin_ia_evidence_request_route_catalog_v1_0",
        "runtime_availability": availability,
        "gap_route_decisions": decisions,
        "candidate_route_declaration_does_not_equal_runtime_availability": True,
    }
    return {**body, "route_catalog_digest": canonical_digest(body)}


def compile_graph_context_packs(
    *,
    context_contract: Mapping[str, Any],
    case_identity: Mapping[str, Any],
    cells: Sequence[Mapping[str, Any]],
    evidence_cards: Sequence[Mapping[str, Any]],
    numeric_cards: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    evidence_by_ref = {str(row["evidence_ref"]): row for row in evidence_cards}
    numeric_by_ref = {str(row["numeric_ref"]): row for row in numeric_cards}
    subject = str(case_identity.get("subject_ticker") or "").upper()
    graph_policy = context_contract["graph_context"]
    maximum_nodes = int(graph_policy["maximum_nodes_per_cell"])
    maximum_edges = int(graph_policy["maximum_edges_per_cell"])
    output: list[dict[str, Any]] = []
    for cell in cells:
        evidence_metadata: dict[str, Mapping[str, Any]] = {}
        edge_evidence: dict[tuple[str, str, str], set[str]] = {}
        for ref in cell["allowed_evidence_refs"]:
            row = evidence_by_ref[str(ref)]
            evidence_metadata[str(ref)] = row
            owner = str(row["evidence_owner_ticker"]).upper()
            directions = row.get("relationship_directions") or [
                "subject_self_disclosure" if owner == subject else "bounded_context"
            ]
            for direction in directions:
                edge_evidence.setdefault(
                    (owner, subject, str(direction)), set()
                ).add(str(ref))
        primary_slot = str(cell.get("primary_slot_id") or "")
        supplemental_slots = {
            str(value)
            for value in cell.get("supplemental_context_slot_ids") or ()
        }
        edge_candidates: list[dict[str, Any]] = []
        for (source, target, direction), refs in sorted(edge_evidence.items()):
            identity = {
                "cell_id": cell["cell_id"],
                "source_entity": source,
                "target_entity": target,
                "relationship_direction": direction,
                "evidence_refs": sorted(refs),
            }
            binding_keys = {
                (str(binding.get("slot_id") or ""), str(facet))
                for ref in refs
                for binding in evidence_metadata[ref].get("slot_bindings") or ()
                if isinstance(binding, Mapping)
                for facet in binding.get("facet_ids") or ("__slot__",)
            }
            source_authority_rank = max(
                (
                    4
                    if (
                        str(evidence_metadata[ref].get("evidence_owner_ticker") or "").upper()
                        == subject
                        and evidence_metadata[ref].get("evidence_role")
                        == "issuer_direct_source"
                    )
                    else 3
                    if evidence_metadata[ref].get("source_tier")
                    in {
                        "primary_sec_filing",
                        "issuer_regulator_or_government_primary",
                        "company_authored_unaudited_sec_filing",
                        "official_hosted_management_call_transcript",
                        "named_counterparty_or_standards_primary",
                    }
                    else 2
                    if evidence_metadata[ref].get("source_tier")
                    == "official_market_or_industry_primary"
                    else 1
                )
                for ref in refs
            )
            edge_candidates.append(
                {
                    "graph_edge_ref": "GRAPH::" + canonical_digest(identity)[:16].upper(),
                    **identity,
                    "authority": "reviewed_evidence_bound_context",
                    "grants_company_fact_or_causality": False,
                    "_primary_facets": {
                        facet for slot, facet in binding_keys if slot == primary_slot
                    },
                    "_supplemental_facets": {
                        facet
                        for slot, facet in binding_keys
                        if slot in supplemental_slots
                    },
                    "_source_authority_rank": source_authority_rank,
                }
            )

        # The full reviewed Evidence Pack remains authoritative.  A role-local
        # graph is only a bounded navigation/context view, so select diverse,
        # proposition-relevant edges rather than failing when a richer Pack
        # contains one more relationship alias than a model node can consume.
        selected_candidates: list[dict[str, Any]] = []
        remaining = list(edge_candidates)
        selected_entities = {subject}
        covered_primary_facets: set[str] = set()
        covered_supplemental_facets: set[str] = set()
        covered_evidence_refs: set[str] = set()
        while remaining and len(selected_candidates) < maximum_edges:
            feasible = [
                row
                for row in remaining
                if row["source_entity"] in selected_entities
                or len(selected_entities) < maximum_nodes
            ]
            if not feasible:
                break

            def _selection_key(value: Mapping[str, Any]) -> tuple[Any, ...]:
                new_primary = len(
                    set(value["_primary_facets"]) - covered_primary_facets
                )
                new_supplemental = len(
                    set(value["_supplemental_facets"])
                    - covered_supplemental_facets
                )
                new_evidence = len(
                    set(value["evidence_refs"]) - covered_evidence_refs
                )
                return (
                    -new_primary,
                    -new_supplemental,
                    -(1 if value["_primary_facets"] else 0),
                    -(1 if value["source_entity"] not in selected_entities else 0),
                    -int(value["_source_authority_rank"]),
                    -(1 if value["source_entity"] == subject else 0),
                    -new_evidence,
                    -len(value["evidence_refs"]),
                    str(value["source_entity"]),
                    str(value["target_entity"]),
                    str(value["relationship_direction"]),
                    str(value["graph_edge_ref"]),
                )

            chosen = min(feasible, key=_selection_key)
            selected_candidates.append(chosen)
            remaining.remove(chosen)
            selected_entities.add(str(chosen["source_entity"]))
            covered_primary_facets.update(chosen["_primary_facets"])
            covered_supplemental_facets.update(chosen["_supplemental_facets"])
            covered_evidence_refs.update(chosen["evidence_refs"])

        selected_edge_refs = {
            str(row["graph_edge_ref"]) for row in selected_candidates
        }
        omitted_candidates = [
            row
            for row in edge_candidates
            if str(row["graph_edge_ref"]) not in selected_edge_refs
        ]
        edges = [
            {
                key: deepcopy(value)
                for key, value in row.items()
                if not key.startswith("_")
            }
            for row in sorted(
                selected_candidates,
                key=lambda value: (
                    str(value["source_entity"]),
                    str(value["target_entity"]),
                    str(value["relationship_direction"]),
                    str(value["graph_edge_ref"]),
                ),
            )
        ]

        nodes: dict[str, dict[str, Any]] = {
            subject: {
                "entity_id": subject,
                "entity_role": "research_subject",
                "authority": "current_case_identity",
            }
        }
        for edge in edges:
            owner = str(edge["source_entity"])
            nodes.setdefault(
                owner,
                {
                    "entity_id": owner,
                    "entity_role": (
                        "research_subject" if owner == subject else "reviewed_evidence_owner"
                    ),
                    "authority": "current_reviewed_evidence",
                },
            )
        numeric_entities = sorted(
            {
                str(numeric_by_ref[str(ref)]["ticker"]).upper()
                for ref in cell["allowed_numeric_refs"]
            }
        )
        for ticker in numeric_entities:
            if ticker in nodes:
                continue
            if len(nodes) >= maximum_nodes:
                break
            nodes[ticker] = {
                "entity_id": ticker,
                "entity_role": "numeric_fact_owner",
                "authority": "current_numeric_fact",
            }

        candidate_entities = {
            subject,
            *numeric_entities,
            *(str(row["source_entity"]) for row in edge_candidates),
        }
        selected_entity_ids = set(nodes)
        omitted_edges = [
            {
                "graph_edge_ref": str(row["graph_edge_ref"]),
                "source_entity": str(row["source_entity"]),
                "target_entity": str(row["target_entity"]),
                "relationship_direction": str(row["relationship_direction"]),
                "evidence_refs": list(row["evidence_refs"]),
                "omission_reason": "bounded_role_graph_context_capacity",
            }
            for row in sorted(
                omitted_candidates,
                key=lambda value: str(value["graph_edge_ref"]),
            )
        ]
        selection_receipt_body = {
            "schema_version": "fin_ia_graph_context_selection_receipt_v1_0",
            "strategy": "deterministic_role_slot_facet_owner_coverage_v1",
            "primary_slot_id": primary_slot,
            "supplemental_context_slot_ids": sorted(supplemental_slots),
            "candidate_edge_count": len(edge_candidates),
            "selected_edge_count": len(edges),
            "omitted_edge_count": len(omitted_edges),
            "maximum_edges_per_cell": maximum_edges,
            "candidate_node_count": len(candidate_entities),
            "selected_node_count": len(nodes),
            "omitted_node_count": len(candidate_entities - selected_entity_ids),
            "maximum_nodes_per_cell": maximum_nodes,
            "selected_graph_edge_refs": [
                str(row["graph_edge_ref"]) for row in edges
            ],
            "omitted_edges": omitted_edges,
            "omitted_entity_ids": sorted(candidate_entities - selected_entity_ids),
            "pack_evidence_or_numeric_authority_changed": False,
            "model_calls": 0,
        }
        selection_receipt = {
            **selection_receipt_body,
            "selection_receipt_digest": canonical_digest(selection_receipt_body),
        }
        _require(
            len(nodes) <= maximum_nodes and len(edges) <= maximum_edges,
            "research_context_graph_capacity_exceeded",
        )
        selection_applied = bool(
            omitted_edges or candidate_entities - selected_entity_ids
        )
        body = {
            "schema_version": (
                "fin_ia_graph_context_pack_v1_1"
                if selection_applied
                else "fin_ia_graph_context_pack_v1_0"
            ),
            "cell_id": str(cell["cell_id"]),
            "case_key": str(case_identity.get("case_key") or ""),
            "nodes": [nodes[key] for key in sorted(nodes)],
            "edges": edges,
            **(
                {"selection_receipt": selection_receipt}
                if selection_applied
                else {}
            ),
            "authority": {
                "compiled_from_current_case_reviewed_evidence_and_numeric_facts": True,
                "archived_graph_rows_used": False,
                "scope_or_context_edge_grants_fact_authority": False,
            },
        }
        output.append({**body, "graph_context_digest": canonical_digest(body)})
    return output


def bind_research_context_to_cells(
    *,
    context_contract: Mapping[str, Any],
    cells: Sequence[Mapping[str, Any]],
    graph_packs: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    methods = {
        str(row["cell_id"]): row for row in context_contract["role_method_packs"]
    }
    graphs = {str(row["cell_id"]): row for row in graph_packs}
    bound: list[dict[str, Any]] = []
    selections: list[dict[str, Any]] = []
    for cell in cells:
        cell_id = str(cell["cell_id"])
        method = deepcopy(methods.get(cell_id))
        graph = deepcopy(graphs[cell_id])
        bound.append(
            {
                **deepcopy(dict(cell)),
                "role_method_pack": method,
                "graph_context_pack": graph,
                "context_consumption_contract": {
                    "minimum_method_step_refs": (
                        int(method["minimum_consumed_method_steps"])
                        if method
                        else 0
                    ),
                    "minimum_graph_edge_refs": (
                        int(
                            context_contract["graph_context"][
                                "minimum_consumed_graph_edges_when_available"
                            ]
                        )
                        if graph["edges"]
                        else 0
                    ),
                },
            }
        )
        selections.append(
            {
                "cell_id": cell_id,
                "role_method_pack_id": method["pack_id"] if method else None,
                "role_method_pack_digest": method["pack_digest"] if method else None,
                "graph_context_digest": graph["graph_context_digest"],
                "injected_method_step_count": len(method["method_steps"]) if method else 0,
                "injected_graph_edge_count": len(graph["edges"]),
            }
        )
    receipt_body = {
        "schema_version": RESEARCH_CONTEXT_CONTRACT_SCHEMA_VERSION,
        "selection": selections,
        "compression": {
            "method_steps_omitted_after_selection": 0,
            "archived_skill_or_graph_rows_loaded": 0,
            "only_cell_local_current_context_retained": True,
        },
        "injection": {
            "role_method_pack_model_visible": True,
            "graph_context_pack_model_visible": True,
            "evidence_request_route_catalog_model_visible": True,
            "provider_request_capture_required": True,
        },
    }
    return bound, {**receipt_body, "context_receipt_digest": canonical_digest(receipt_body)}


__all__ = [
    "RESEARCH_CONTEXT_CONTRACT_SCHEMA_VERSION",
    "EvidenceRequestSourceClass",
    "ResearchContextError",
    "bind_research_context_to_cells",
    "compile_evidence_request_route_catalog",
    "compile_graph_context_packs",
    "load_research_context_contract",
]
