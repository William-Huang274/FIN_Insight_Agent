from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from retrieval.dell_report_r14_contracts import load_and_validate_r14_contracts
from retrieval.dell_report_structural_graph_r14 import (
    build_event_argument_graph_r14,
    build_price_attachment_graph_r14,
)
from retrieval.dell_report_target_compiler_r14 import build_target_graph_view_r14
from retrieval.dell_report_transformation_r14 import (
    build_graph_transformation_receipt_r14,
    build_graph_transformation_receipt_from_inventories_r14,
    build_transformation_inventory_r14,
    validate_graph_transformation_receipt_r14,
)
from retrieval.dell_report_r14_common import (
    DellReportR14ContractError,
    with_result_digest,
)


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def bundle():
    return load_and_validate_r14_contracts(root=ROOT)


def _view(text: str, bundle):
    graph = build_event_argument_graph_r14(text=text, bundle=bundle)
    price = build_price_attachment_graph_r14(graph=graph, bundle=bundle)
    return build_target_graph_view_r14(event_graph=graph, price_graph=price)


def _receipt(source, compiled, *, source_passed=True, compiled_passed=True):
    return build_graph_transformation_receipt_r14(
        source_view=source,
        compiled_view=compiled,
        source_manifest_index=0,
        compiled_manifest_index=0,
        source_record_id="SOURCE-R14-TEST",
        compiled_object_id="OBJECT-R14-TEST",
        source_input_digest="c" * 64,
        source_slice_mode="exact_text",
        source_slice_digest="f" * 64,
        source_slice_binding_digest="0" * 64,
        compiled_input_digest="d" * 64,
        canonical_source_family_id="FAMILY-R14-TEST",
        compiled_lineage_source_record_ids=("SOURCE-R14-TEST",),
        compiled_lineage_source_keyset_digest="e" * 64,
        source_extraction_receipt_digest="a" * 64,
        compiled_extraction_receipt_digest="b" * 64,
        source_extraction_passed=source_passed,
        compiled_extraction_passed=compiled_passed,
    )


def test_r14_transformation_accepts_offset_only_change_and_is_non_vacuous(bundle) -> None:
    source = _view("Dell offered PowerEdge at $100.", bundle)
    compiled = _view("  Dell offered PowerEdge at $100.", bundle)
    result = _receipt(source, compiled)

    assert source.view_digest != compiled.view_digest
    assert result["status"] == "PASS_PRESERVATION"
    assert not result["findings"]
    assert result["coverage"]["non_vacuous"] is True
    assert result["truth_claim"] == "preservation_only_not_parser_truth"


def test_r14_transformation_detects_role_rebind_with_same_node_population(bundle) -> None:
    source = _view("Dell shipped 20 PowerEdge systems in 2026.", bundle)
    quantity = next(
        row
        for row in source.typed_edges
        if row.edge_family == "event_role" and row.edge_type == "quantity"
    )
    period = next(row for row in source.typed_nodes if row.node_type == "period")
    rebound = replace(quantity, destination_node_id=period.node_id)
    compiled = replace(
        source,
        typed_edges=tuple(
            sorted(
                (rebound if row is quantity else row for row in source.typed_edges),
                key=lambda row: (row.edge_family, row.edge_type, row.edge_id),
            )
        ),
    )
    result = _receipt(source, compiled)

    assert result["status"] == "FAIL_TYPED_FINDING"
    assert result["finding_counts"]["TOPOLOGY_REBIND"] == 1
    assert result["finding_counts"]["EDGE_ADDITION"] >= 1
    assert result["finding_counts"]["EDGE_LOSS"] >= 1


def test_r14_transformation_detects_node_addition(bundle) -> None:
    source = _view("Acme discussed topic.", bundle)
    template = source.typed_nodes[0]
    added = replace(template, node_id="MENTION::R14::FORGED-ADDITION")
    compiled = replace(
        source,
        typed_nodes=tuple(
            sorted(
                (*source.typed_nodes, added),
                key=lambda row: (row.node_type, row.node_id),
            )
        ),
    )
    result = _receipt(source, compiled)

    assert result["status"] == "FAIL_TYPED_FINDING"
    assert result["finding_counts"]["NODE_ADDITION"] == 1
    assert result["coverage"]["non_vacuous"] is False


def test_r14_transformation_blocks_common_mode_equality_when_extraction_gate_open(
    bundle,
) -> None:
    source = _view("Dell offered PowerEdge at $100.", bundle)
    result = _receipt(source, source, source_passed=False, compiled_passed=False)

    assert result["status"] == "FAIL_TYPED_FINDING"
    assert result["finding_counts"] == {"COMMON_MODE_EXTRACTION_GATE_OPEN": 1}


def test_r14_transformation_validator_rejects_resigned_semantic_forgery(bundle) -> None:
    view = _view("Dell offered PowerEdge at $100.", bundle)
    receipt = _receipt(view, view)

    forged = deepcopy(receipt)
    forged["coverage"]["source_node_count"] += 1
    forged = with_result_digest(forged)
    with pytest.raises(
        DellReportR14ContractError, match="R14_transformation_coverage_invalid"
    ):
        validate_graph_transformation_receipt_r14(forged)

    forged = deepcopy(receipt)
    forged["findings"] = [
        {
            "finding_type": "NODE_ADDITION",
            "signature_digest": "c" * 64,
            "source_count": 1,
            "compiled_count": 1,
            "delta": 0,
        }
    ]
    forged["finding_counts"] = {"NODE_ADDITION": 1}
    forged["status"] = "FAIL_TYPED_FINDING"
    forged = with_result_digest(forged)
    with pytest.raises(
        DellReportR14ContractError,
        match="R14_transformation_finding_delta_invalid",
    ):
        validate_graph_transformation_receipt_r14(forged)


def test_r14_compact_transformation_inventory_is_exactly_receipt_equivalent(bundle) -> None:
    source = _view("Dell offered PowerEdge at $100.", bundle)
    compiled = _view("  Dell offered PowerEdge at $100.", bundle)
    direct = _receipt(source, compiled)
    compact = build_graph_transformation_receipt_from_inventories_r14(
        source_inventory_receipt=build_transformation_inventory_r14(source),
        compiled_inventory_receipt=build_transformation_inventory_r14(compiled),
        source_manifest_index=0,
        compiled_manifest_index=0,
        source_record_id="SOURCE-R14-TEST",
        compiled_object_id="OBJECT-R14-TEST",
        source_input_digest="c" * 64,
        source_slice_mode="exact_text",
        source_slice_digest="f" * 64,
        source_slice_binding_digest="0" * 64,
        compiled_input_digest="d" * 64,
        canonical_source_family_id="FAMILY-R14-TEST",
        compiled_lineage_source_record_ids=("SOURCE-R14-TEST",),
        compiled_lineage_source_keyset_digest="e" * 64,
        source_extraction_receipt_digest="a" * 64,
        compiled_extraction_receipt_digest="b" * 64,
        source_extraction_passed=True,
        compiled_extraction_passed=True,
    )

    assert compact == direct
