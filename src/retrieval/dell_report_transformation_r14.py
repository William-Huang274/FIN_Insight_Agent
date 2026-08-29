from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Mapping

from .dell_report_r14_common import (
    canonical_digest,
    require,
    require_identifier,
    require_sha256,
    with_result_digest,
)
from .dell_report_target_compiler_r14 import (
    TargetGraphViewR14,
    TypedEdgeViewR14,
    TypedNodeViewR14,
    TypedProofViewR14,
    validate_target_graph_view_r14,
)


TRANSFORMATION_SCHEMA_VERSION = "fin_ia_dell_03B_R14_transformation_receipt_v1_0"
TRANSFORMATION_INVENTORY_SCHEMA_VERSION = (
    "fin_ia_dell_03B_R14_transformation_inventory_v1_0"
)


def _node_signature(node: TypedNodeViewR14) -> dict[str, Any]:
    return {
        "node_type": node.node_type,
        "semantic_identity_ids": list(node.semantic_identity_ids),
        "proof_state": node.proof_state,
        "event_types": list(node.event_types),
        "target_labels": list(node.target_labels),
    }


def _edge_signature(
    edge: TypedEdgeViewR14, *, node_by_id: Mapping[str, TypedNodeViewR14]
) -> dict[str, Any]:
    return {
        "edge_family": edge.edge_family,
        "edge_type": edge.edge_type,
        "proof_state": edge.proof_state,
        "semantic_identity_ids": list(edge.semantic_identity_ids),
        "subtype": edge.subtype,
        "source": _node_signature(node_by_id[edge.source_node_id]),
        "destination": _node_signature(node_by_id[edge.destination_node_id]),
    }


def _proof_signature(
    proof: TypedProofViewR14,
    *,
    node_by_id: Mapping[str, TypedNodeViewR14],
    edge_by_id: Mapping[str, TypedEdgeViewR14],
) -> dict[str, Any]:
    return {
        "proof_family": proof.proof_family,
        "rule_id": proof.rule_id,
        "state": proof.state,
        "event": _node_signature(node_by_id[proof.event_id]) if proof.event_id else None,
        "nodes": sorted(
            (_node_signature(node_by_id[row]) for row in proof.node_ids),
            key=canonical_digest,
        ),
        "edges": sorted(
            (
                _edge_signature(edge_by_id[row], node_by_id=node_by_id)
                for row in proof.edge_ids
            ),
            key=canonical_digest,
        ),
    }


def _signature_inventory(view: TargetGraphViewR14) -> dict[str, Any]:
    node_by_id = {row.node_id: row for row in view.typed_nodes}
    edge_by_id = {row.edge_id: row for row in view.typed_edges}
    node_groups: defaultdict[str, list[str]] = defaultdict(list)
    edge_groups: defaultdict[str, list[str]] = defaultdict(list)
    proof_groups: defaultdict[str, list[str]] = defaultdict(list)
    for node in view.typed_nodes:
        node_groups[canonical_digest(_node_signature(node))].append(node.node_id)
    for edge in view.typed_edges:
        edge_groups[
            canonical_digest(_edge_signature(edge, node_by_id=node_by_id))
        ].append(edge.edge_id)
    for proof in view.proofs:
        proof_groups[
            canonical_digest(
                _proof_signature(
                    proof, node_by_id=node_by_id, edge_by_id=edge_by_id
                )
            )
        ].append(proof.proof_id)
    return {
        "nodes": {key: tuple(sorted(value)) for key, value in node_groups.items()},
        "edges": {key: tuple(sorted(value)) for key, value in edge_groups.items()},
        "proofs": {key: tuple(sorted(value)) for key, value in proof_groups.items()},
    }


def _count(groups: Mapping[str, tuple[str, ...]]) -> Counter[str]:
    return Counter({key: len(value) for key, value in groups.items()})


def build_transformation_inventory_r14(
    view: TargetGraphViewR14,
) -> dict[str, Any]:
    validate_target_graph_view_r14(view)
    groups = _signature_inventory(view)
    body = {
        "schema_version": TRANSFORMATION_INVENTORY_SCHEMA_VERSION,
        "view_digest": view.view_digest,
        "signature_groups": {
            layer: {key: list(values) for key, values in sorted(rows.items())}
            for layer, rows in sorted(groups.items())
        },
        "node_count": len(view.typed_nodes),
        "edge_count": len(view.typed_edges),
        "proof_count": len(view.proofs),
        "non_vacuous": any(
            bool(row.target_labels)
            for row in view.typed_nodes
            if row.node_type == "event"
        ),
    }
    return with_result_digest(body)


def validate_transformation_inventory_r14(value: Mapping[str, Any]) -> None:
    require(
        set(value)
        == {
            "schema_version",
            "view_digest",
            "signature_groups",
            "node_count",
            "edge_count",
            "proof_count",
            "non_vacuous",
            "result_digest",
        },
        "R14_transformation_inventory_keyset_invalid",
    )
    require(
        value.get("schema_version") == TRANSFORMATION_INVENTORY_SCHEMA_VERSION
        and bool(require_sha256(value.get("view_digest"), field="transformation_inventory_view"))
        and with_result_digest(value) == dict(value),
        "R14_transformation_inventory_identity_invalid",
    )
    groups = value.get("signature_groups")
    require(
        isinstance(groups, dict)
        and set(groups) == {"nodes", "edges", "proofs"}
        and all(
            isinstance(rows, dict)
            and list(rows) == sorted(rows)
            and all(
                bool(require_sha256(key, field="transformation_signature"))
                and isinstance(ids, list)
                and ids == sorted(set(ids))
                for key, ids in rows.items()
            )
            for rows in groups.values()
        ),
        "R14_transformation_inventory_groups_invalid",
    )
    require(
        value.get("node_count") == sum(len(row) for row in groups["nodes"].values())
        and value.get("edge_count") == sum(len(row) for row in groups["edges"].values())
        and value.get("proof_count") == sum(len(row) for row in groups["proofs"].values())
        and type(value.get("non_vacuous")) is bool,
        "R14_transformation_inventory_counts_invalid",
    )


def _inventory_groups(value: Mapping[str, Any]) -> dict[str, dict[str, tuple[str, ...]]]:
    return {
        layer: {key: tuple(ids) for key, ids in rows.items()}
        for layer, rows in value["signature_groups"].items()
    }


def _delta_rows(
    source: Counter[str], compiled: Counter[str], *, layer: str
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for signature in sorted(set(source) | set(compiled)):
        source_count = int(source.get(signature, 0))
        compiled_count = int(compiled.get(signature, 0))
        if source_count == compiled_count:
            continue
        output.append(
            {
                "finding_type": (
                    f"{layer}_LOSS" if source_count > compiled_count else f"{layer}_ADDITION"
                ),
                "signature_digest": signature,
                "source_count": source_count,
                "compiled_count": compiled_count,
                "delta": compiled_count - source_count,
            }
        )
    return output


def build_graph_transformation_receipt_from_inventories_r14(
    *,
    source_inventory_receipt: Mapping[str, Any],
    compiled_inventory_receipt: Mapping[str, Any],
    source_manifest_index: int,
    compiled_manifest_index: int,
    source_record_id: str,
    compiled_object_id: str,
    source_input_digest: str,
    source_slice_mode: str,
    source_slice_digest: str,
    source_slice_binding_digest: str,
    compiled_input_digest: str,
    canonical_source_family_id: str,
    compiled_lineage_source_record_ids: tuple[str, ...],
    compiled_lineage_source_keyset_digest: str,
    source_extraction_receipt_digest: str,
    compiled_extraction_receipt_digest: str,
    source_extraction_passed: bool,
    compiled_extraction_passed: bool,
) -> dict[str, Any]:
    validate_transformation_inventory_r14(source_inventory_receipt)
    validate_transformation_inventory_r14(compiled_inventory_receipt)
    source_inventory = _inventory_groups(source_inventory_receipt)
    compiled_inventory = _inventory_groups(compiled_inventory_receipt)
    findings: list[dict[str, Any]] = []
    for layer in ("nodes", "edges", "proofs"):
        findings.extend(
            _delta_rows(
                _count(source_inventory[layer]),
                _count(compiled_inventory[layer]),
                layer=layer[:-1].upper(),
            )
        )
    if (
        _count(source_inventory["nodes"]) == _count(compiled_inventory["nodes"])
        and _count(source_inventory["edges"]) != _count(compiled_inventory["edges"])
    ):
        findings.append(
            {
                "finding_type": "TOPOLOGY_REBIND",
                "signature_digest": canonical_digest(
                    {
                        "source_edge_inventory": sorted(
                            _count(source_inventory["edges"]).items()
                        ),
                        "compiled_edge_inventory": sorted(
                            _count(compiled_inventory["edges"]).items()
                        ),
                    }
                ),
                "source_count": source_inventory_receipt["edge_count"],
                "compiled_count": compiled_inventory_receipt["edge_count"],
                "delta": 0,
            }
        )
    if not source_extraction_passed or not compiled_extraction_passed:
        findings.append(
            {
                "finding_type": "COMMON_MODE_EXTRACTION_GATE_OPEN",
                "signature_digest": canonical_digest(
                    {
                        "source": bool(source_extraction_passed),
                        "compiled": bool(compiled_extraction_passed),
                    }
                ),
                "source_count": int(bool(source_extraction_passed)),
                "compiled_count": int(bool(compiled_extraction_passed)),
                "delta": 0,
            }
        )

    node_mappings = []
    for signature in sorted(
        set(source_inventory["nodes"]) | set(compiled_inventory["nodes"])
    ):
        source_ids = source_inventory["nodes"].get(signature, ())
        compiled_ids = compiled_inventory["nodes"].get(signature, ())
        node_mappings.append(
            {
                "signature_digest": signature,
                "source_node_ids": list(source_ids),
                "compiled_node_ids": list(compiled_ids),
                "source_count": len(source_ids),
                "compiled_count": len(compiled_ids),
                "mapping_state": (
                    "EXACT_ONE_TO_ONE"
                    if len(source_ids) == len(compiled_ids) == 1
                    else "EXACT_GROUPED_MULTISET"
                    if len(source_ids) == len(compiled_ids)
                    else "NON_BIJECTIVE"
                ),
            }
        )

    non_vacuous = bool(
        source_inventory_receipt["non_vacuous"]
        or compiled_inventory_receipt["non_vacuous"]
    )
    body = {
        "schema_version": TRANSFORMATION_SCHEMA_VERSION,
        "source_manifest_index": source_manifest_index,
        "compiled_manifest_index": compiled_manifest_index,
        "source_record_id": require_identifier(
            source_record_id, field="transformation_source_record_id"
        ),
        "compiled_object_id": require_identifier(
            compiled_object_id, field="transformation_compiled_object_id"
        ),
        "source_input_digest": require_sha256(
            source_input_digest, field="transformation_source_input"
        ),
        "source_slice_mode": require_identifier(
            source_slice_mode, field="transformation_source_slice_mode"
        ),
        "source_slice_digest": require_sha256(
            source_slice_digest, field="transformation_source_slice"
        ),
        "source_slice_binding_digest": require_sha256(
            source_slice_binding_digest,
            field="transformation_source_slice_binding",
        ),
        "compiled_input_digest": require_sha256(
            compiled_input_digest, field="transformation_compiled_input"
        ),
        "canonical_source_family_id": str(canonical_source_family_id),
        "compiled_lineage_source_record_ids": list(
            compiled_lineage_source_record_ids
        ),
        "compiled_lineage_source_keyset_digest": require_sha256(
            compiled_lineage_source_keyset_digest,
            field="transformation_lineage_keyset",
        ),
        "source_view_digest": source_inventory_receipt["view_digest"],
        "compiled_view_digest": compiled_inventory_receipt["view_digest"],
        "source_extraction_receipt_digest": require_sha256(
            source_extraction_receipt_digest, field="source_extraction_receipt"
        ),
        "compiled_extraction_receipt_digest": require_sha256(
            compiled_extraction_receipt_digest, field="compiled_extraction_receipt"
        ),
        "source_extraction_passed": bool(source_extraction_passed),
        "compiled_extraction_passed": bool(compiled_extraction_passed),
        "node_mapping_groups": node_mappings,
        "findings": sorted(
            findings,
            key=lambda row: (row["finding_type"], row["signature_digest"]),
        ),
        "finding_counts": dict(
            sorted(Counter(row["finding_type"] for row in findings).items())
        ),
        "coverage": {
            "non_vacuous": non_vacuous,
            "source_node_count": source_inventory_receipt["node_count"],
            "compiled_node_count": compiled_inventory_receipt["node_count"],
            "source_edge_count": source_inventory_receipt["edge_count"],
            "compiled_edge_count": compiled_inventory_receipt["edge_count"],
            "source_proof_count": source_inventory_receipt["proof_count"],
            "compiled_proof_count": compiled_inventory_receipt["proof_count"],
        },
        "status": "PASS_PRESERVATION" if not findings else "FAIL_TYPED_FINDING",
        "truth_claim": "preservation_only_not_parser_truth",
    }
    receipt = with_result_digest(body)
    validate_graph_transformation_receipt_r14(receipt)
    return receipt


def build_graph_transformation_receipt_r14(
    *,
    source_view: TargetGraphViewR14,
    compiled_view: TargetGraphViewR14,
    **metadata: Any,
) -> dict[str, Any]:
    return build_graph_transformation_receipt_from_inventories_r14(
        source_inventory_receipt=build_transformation_inventory_r14(source_view),
        compiled_inventory_receipt=build_transformation_inventory_r14(compiled_view),
        **metadata,
    )


def validate_graph_transformation_receipt_r14(value: Mapping[str, Any]) -> None:
    expected_keys = {
        "schema_version",
        "source_manifest_index",
        "compiled_manifest_index",
        "source_record_id",
        "compiled_object_id",
        "source_input_digest",
        "source_slice_mode",
        "source_slice_digest",
        "source_slice_binding_digest",
        "compiled_input_digest",
        "canonical_source_family_id",
        "compiled_lineage_source_record_ids",
        "compiled_lineage_source_keyset_digest",
        "source_view_digest",
        "compiled_view_digest",
        "source_extraction_receipt_digest",
        "compiled_extraction_receipt_digest",
        "source_extraction_passed",
        "compiled_extraction_passed",
        "node_mapping_groups",
        "findings",
        "finding_counts",
        "coverage",
        "status",
        "truth_claim",
        "result_digest",
    }
    require(set(value) == expected_keys, "R14_transformation_keyset_invalid")
    body = dict(value)
    result_digest = body.pop("result_digest")
    require(result_digest == canonical_digest(body), "R14_transformation_result_digest_mismatch")
    require(
        value.get("schema_version") == TRANSFORMATION_SCHEMA_VERSION,
        "R14_transformation_schema_invalid",
    )
    require(
        value.get("truth_claim") == "preservation_only_not_parser_truth",
        "R14_transformation_truth_claim_invalid",
    )
    require(
        type(value.get("source_manifest_index")) is int
        and value["source_manifest_index"] >= 0
        and type(value.get("compiled_manifest_index")) is int
        and value["compiled_manifest_index"] >= 0
        and bool(
            require_identifier(
                value.get("canonical_source_family_id"),
                field="transformation_source_family",
            )
        )
        and bool(
            require_identifier(
                value.get("source_record_id"),
                field="transformation_source_record_id",
            )
        )
        and bool(
            require_identifier(
                value.get("compiled_object_id"),
                field="transformation_compiled_object_id",
            )
        )
        and isinstance(value.get("compiled_lineage_source_record_ids"), list)
        and value["compiled_lineage_source_record_ids"]
        == sorted(set(value["compiled_lineage_source_record_ids"]))
        and value.get("source_record_id")
        in value["compiled_lineage_source_record_ids"],
        "R14_transformation_population_binding_invalid",
    )
    for field in (
        "source_input_digest",
        "source_slice_digest",
        "source_slice_binding_digest",
        "compiled_input_digest",
        "compiled_lineage_source_keyset_digest",
        "source_view_digest",
        "compiled_view_digest",
        "source_extraction_receipt_digest",
        "compiled_extraction_receipt_digest",
    ):
        require_sha256(value.get(field), field=f"transformation_{field}")
    require_identifier(
        value.get("source_slice_mode"), field="transformation_source_slice_mode"
    )
    require(
        type(value.get("source_extraction_passed")) is bool
        and type(value.get("compiled_extraction_passed")) is bool,
        "R14_transformation_extraction_gate_type_invalid",
    )

    mapping_rows = list(value.get("node_mapping_groups") or ())
    mapping_signatures: list[str] = []
    for row in mapping_rows:
        require(
            isinstance(row, dict)
            and set(row)
            == {
                "signature_digest",
                "source_node_ids",
                "compiled_node_ids",
                "source_count",
                "compiled_count",
                "mapping_state",
            },
            "R14_transformation_mapping_schema_invalid",
        )
        signature = require_sha256(
            row.get("signature_digest"), field="transformation_mapping_signature"
        )
        source_ids = list(row.get("source_node_ids") or ())
        compiled_ids = list(row.get("compiled_node_ids") or ())
        require(
            source_ids == sorted(set(source_ids))
            and compiled_ids == sorted(set(compiled_ids))
            and all(isinstance(item, str) and item for item in (*source_ids, *compiled_ids)),
            "R14_transformation_mapping_ids_invalid",
        )
        expected_state = (
            "EXACT_ONE_TO_ONE"
            if len(source_ids) == len(compiled_ids) == 1
            else "EXACT_GROUPED_MULTISET"
            if len(source_ids) == len(compiled_ids)
            else "NON_BIJECTIVE"
        )
        require(
            type(row.get("source_count")) is int
            and type(row.get("compiled_count")) is int
            and row["source_count"] == len(source_ids)
            and row["compiled_count"] == len(compiled_ids)
            and row.get("mapping_state") == expected_state,
            "R14_transformation_mapping_semantics_invalid",
        )
        mapping_signatures.append(signature)
    require(
        mapping_signatures == sorted(set(mapping_signatures)),
        "R14_transformation_mapping_order_or_duplicate_invalid",
    )

    findings = list(value.get("findings") or ())
    finding_keys: list[tuple[str, str]] = []
    allowed_findings = {
        "NODE_LOSS",
        "NODE_ADDITION",
        "EDGE_LOSS",
        "EDGE_ADDITION",
        "PROOF_LOSS",
        "PROOF_ADDITION",
        "TOPOLOGY_REBIND",
        "COMMON_MODE_EXTRACTION_GATE_OPEN",
    }
    for row in findings:
        require(
            isinstance(row, dict)
            and set(row)
            == {
                "finding_type",
                "signature_digest",
                "source_count",
                "compiled_count",
                "delta",
            },
            "R14_transformation_finding_schema_invalid",
        )
        finding_type = str(row.get("finding_type") or "")
        signature = require_sha256(
            row.get("signature_digest"), field="transformation_finding_signature"
        )
        require(
            finding_type in allowed_findings
            and type(row.get("source_count")) is int
            and type(row.get("compiled_count")) is int
            and type(row.get("delta")) is int
            and row["source_count"] >= 0
            and row["compiled_count"] >= 0,
            "R14_transformation_finding_value_invalid",
        )
        if finding_type not in {
            "TOPOLOGY_REBIND",
            "COMMON_MODE_EXTRACTION_GATE_OPEN",
        }:
            require(
                row["delta"] == row["compiled_count"] - row["source_count"]
                and row["delta"] != 0,
                "R14_transformation_finding_delta_invalid",
            )
        else:
            require(row["delta"] == 0, "R14_transformation_gate_delta_invalid")
        finding_keys.append((finding_type, signature))
    require(
        finding_keys == sorted(set(finding_keys)),
        "R14_transformation_finding_order_or_duplicate_invalid",
    )
    expected_counts = dict(
        sorted(Counter(row["finding_type"] for row in findings).items())
    )
    require(
        value.get("finding_counts") == expected_counts,
        "R14_transformation_finding_counts_invalid",
    )

    coverage = value.get("coverage")
    require(
        isinstance(coverage, dict)
        and set(coverage)
        == {
            "non_vacuous",
            "source_node_count",
            "compiled_node_count",
            "source_edge_count",
            "compiled_edge_count",
            "source_proof_count",
            "compiled_proof_count",
        }
        and type(coverage.get("non_vacuous")) is bool
        and all(
            type(coverage.get(field)) is int and coverage[field] >= 0
            for field in (
                "source_node_count",
                "compiled_node_count",
                "source_edge_count",
                "compiled_edge_count",
                "source_proof_count",
                "compiled_proof_count",
            )
        ),
        "R14_transformation_coverage_invalid",
    )
    require(
        coverage["source_node_count"]
        == sum(int(row["source_count"]) for row in mapping_rows)
        and coverage["compiled_node_count"]
        == sum(int(row["compiled_count"]) for row in mapping_rows),
        "R14_transformation_coverage_invalid",
    )
    require(
        value.get("status")
        == ("PASS_PRESERVATION" if not findings else "FAIL_TYPED_FINDING"),
        "R14_transformation_status_invalid",
    )
    require(
        bool(value.get("source_extraction_passed"))
        and bool(value.get("compiled_extraction_passed"))
        if value.get("status") == "PASS_PRESERVATION"
        else True,
        "R14_transformation_common_mode_gate_invalid",
    )
    gate_findings = [
        row for row in findings if row["finding_type"] == "COMMON_MODE_EXTRACTION_GATE_OPEN"
    ]
    require(
        bool(gate_findings)
        == (
            not value["source_extraction_passed"]
            or not value["compiled_extraction_passed"]
        )
        and len(gate_findings) <= 1,
        "R14_transformation_common_mode_finding_invalid",
    )


__all__ = [
    "TRANSFORMATION_INVENTORY_SCHEMA_VERSION",
    "TRANSFORMATION_SCHEMA_VERSION",
    "build_graph_transformation_receipt_r14",
    "build_graph_transformation_receipt_from_inventories_r14",
    "build_transformation_inventory_r14",
    "validate_transformation_inventory_r14",
    "validate_graph_transformation_receipt_r14",
]
