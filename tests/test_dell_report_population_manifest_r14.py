from __future__ import annotations

import ast
from copy import deepcopy
import json
from pathlib import Path

import pytest

from retrieval.dell_report_population_manifest_r14 import (
    build_input_population_manifest_r14,
    build_population_commitment_r14,
    validate_input_population_manifest_r14,
    validate_population_commitment_r14,
)
from retrieval.dell_report_population_rebuilder_r14 import (
    rebuild_input_population_r14,
)
from retrieval.dell_report_r14_common import (
    DellReportR14ContractError,
    canonical_json_bytes,
    sha256_bytes,
    with_result_digest,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE_REF = (
    "data/workbench_private/"
    "fin_0_1_3_s1b_current_financial_object_store/v5/records.jsonl"
)
OBJECT_REF = (
    "data/workbench_private/"
    "fin_0_1_3_s1c_compiled_financial_object_views/v9/objects.jsonl"
)


def _source(source_id: str, text: str, *, family: str | None = None) -> dict:
    metadata = {"period_end": "2026-01-31", "source_tier": "primary"}
    if family is not None:
        metadata["source_page_record_id"] = family
    return {
        "evidence_id": source_id,
        "text": text,
        "ticker": "DELL",
        "metadata": metadata,
        "local_path": f"D:/private/{source_id}.json",
    }


def _object(
    object_id: str, source_id: str, text: str, *, family: str | None = None
) -> dict:
    lineage = {} if family is None else {"source_page_record_id": family}
    return {
        "compiled_object_id": object_id,
        "model_text": text,
        "object_kind": "sentence",
        "lineage_source_record_ids": [source_id],
        "base_object_view": {
            "source_record_id": source_id,
            "source_lineage": lineage,
            "surface_text": text,
            "focus_binding": {
                "mode": "exact_text",
                "char_start": 0,
                "char_end": len(text),
            },
        },
    }


def _manifest(sources: list[dict], objects: list[dict]) -> dict:
    return build_input_population_manifest_r14(
        source_rows=sources,
        object_rows=objects,
        source_ref="private/sources.jsonl",
        source_sha256="a" * 64,
        object_ref="private/objects.jsonl",
        object_sha256="b" * 64,
        implementation_identity="TEST::R14::I",
        changed_path_digest="c" * 64,
        recorded_at="2026-08-28T00:00:00+08:00",
    )


def test_r14_population_producer_and_independent_rebuilder_are_exact_and_order_invariant() -> None:
    sources = [
        _source("S2", "Dell and NVIDIA partner.", family="F1"),
        _source("S1", "Dell offered a PowerEdge server.", family="F1"),
    ]
    objects = [
        _object("O2", "S2", "Dell and NVIDIA partner.", family="F1"),
        _object(
            "O1",
            "S1",
            "Dell offered a PowerEdge server.",
            family="F1",
        ),
    ]
    produced = _manifest(sources, objects)
    rebuilt = rebuild_input_population_r14(
        source_rows=list(reversed(sources)),
        object_rows=list(reversed(objects)),
    )

    for field in (
        "source_canonical_order",
        "object_canonical_order",
        "parent_document_receipts",
        "canonical_source_family_count",
        "expected_lane_counts",
        "source_keyset_digest",
        "object_keyset_digest",
        "parent_document_receipt_root",
        "canonical_family_occurrence_digest",
        "target_cross_product_digest",
        "manifest_root",
    ):
        assert produced[field] == rebuilt[field]
    assert produced == _manifest(list(reversed(sources)), list(reversed(objects)))
    assert produced["source_canonical_order"][0]["source_record_id"] == "S1"
    assert [row["occurrence_index"] for row in produced["source_canonical_order"]] == [
        0,
        1,
    ]
    assert produced["expected_lane_counts"] == {
        "source_per_target": 2,
        "compiled_per_target": 2,
        "source_all_targets": 12,
        "compiled_all_targets": 12,
        "total": 24,
    }


def test_r14_population_input_mutation_changes_roots_and_duplicate_or_orphan_rejects() -> None:
    sources = [_source("S1", "original")]
    objects = [_object("O1", "S1", "original")]
    original = _manifest(sources, objects)

    changed_sources = deepcopy(sources)
    changed_sources[0]["text"] = "changed"
    changed_objects = [_object("O1", "S1", "changed")]
    changed = _manifest(changed_sources, changed_objects)
    assert changed["source_keyset_digest"] != original["source_keyset_digest"]
    assert changed["target_cross_product_digest"] != original[
        "target_cross_product_digest"
    ]
    assert changed["manifest_root"] != original["manifest_root"]

    with pytest.raises(
        DellReportR14ContractError,
        match="R14_compiled_object_source_slice_offset_mismatch",
    ):
        _manifest(changed_sources, objects)

    with pytest.raises(DellReportR14ContractError, match="R14_source_duplicate"):
        _manifest([sources[0], deepcopy(sources[0])], objects)
    with pytest.raises(
        DellReportR14ContractError,
        match="R14_compiled_object_family_missing",
    ):
        _manifest(sources, [_object("O2", "MISSING", "orphan")])


def test_r14_population_rejects_resigned_source_record_or_slice_binding() -> None:
    sources = [_source("S1", "Dell offered PowerEdge at $100.")]
    object_row = _object("O1", "S1", sources[0]["text"])
    object_row["base_object_view"]["source_record_digest"] = "f" * 64
    with pytest.raises(
        DellReportR14ContractError,
        match="R14_compiled_object_source_record_digest_mismatch",
    ):
        _manifest(sources, [object_row])

    object_row = _object("O1", "S1", sources[0]["text"])
    object_row["base_object_view"]["surface_digest"] = "e" * 64
    with pytest.raises(
        DellReportR14ContractError,
        match="R14_compiled_object_source_slice_digest_mismatch",
    ):
        _manifest(sources, [object_row])


def test_r14_parent_context_and_cross_family_lineage_require_raw_source_proof() -> None:
    first = _source("S1", "one", family="F1")
    first.update(
        {
            "company": "Dell Technologies",
            "ticker": "DELL",
            "fiscal_year": 2026,
        }
    )
    second = _source("S2", "two", family="F2")
    row = _object("O1", "S1", "company: Acme", family="F1")
    row["lineage_source_record_ids"] = ["S1", "S2"]
    row["base_object_view"]["focus_binding"] = {
        "mode": "parent_context",
        "parent_context": {"company": "Acme"},
    }

    with pytest.raises(
        DellReportR14ContractError,
        match="R14_compiled_object_lineage_relationship_unproved",
    ):
        _manifest([first, second], [row])

    first["metadata"]["parent_document_id"] = "DOC-1"
    second["metadata"]["parent_document_id"] = "DOC-1"
    first["source_url"] = "https://example.test/doc-1"
    second["source_url"] = "https://example.test/doc-1"
    with pytest.raises(
        DellReportR14ContractError,
        match="R14_compiled_object_parent_context_surface_mismatch",
    ):
        _manifest([first, second], [row])

    row["base_object_view"]["surface_text"] = "company: Dell Technologies"
    row["base_object_view"]["focus_binding"]["parent_context"] = {
        "company": "Dell Technologies"
    }
    produced = _manifest([first, second], [row])
    binding = produced["object_canonical_order"][0]["lineage_bindings"][1]
    assert binding["relationship_to_primary"] == "shared_parent_document"
    assert binding["source_record_input_digest"]
    assert binding["parent_document_receipt_digest"]
    assert produced["parent_document_receipts"][0]["authority_state"] == "PROVED"


def test_r14_cross_family_lineage_rejects_reused_parent_label_without_shared_document_authority() -> None:
    first = _source("S1", "one", family="F1")
    second = _source("S2", "two", family="F2")
    first["metadata"]["parent_document_id"] = "DOC-1"
    second["metadata"]["parent_document_id"] = "DOC-1"
    first["source_url"] = "https://example.test/real-document"
    second["source_url"] = "https://example.test/different-document"
    row = _object("O1", "S1", "one", family="F1")
    row["lineage_source_record_ids"] = ["S1", "S2"]

    with pytest.raises(
        DellReportR14ContractError,
        match="R14_compiled_object_lineage_relationship_unproved",
    ):
        _manifest([first, second], [row])


@pytest.mark.parametrize(
    "operator",
    [
        "delete_cell",
        "duplicate_cell",
        "move_cell",
        "resign_all_derived_surfaces",
        "replace_manifest_index_or_input_digest",
    ],
)
def test_r14_population_operator_specific_mutant_is_rejected(operator: str) -> None:
    sources = [_source("S1", "one"), _source("S2", "two")]
    objects = [_object("O1", "S1", "one"), _object("O2", "S2", "two")]
    mutated = deepcopy(_manifest(sources, objects))
    if operator == "delete_cell":
        mutated["source_canonical_order"].pop()
    elif operator == "duplicate_cell":
        mutated["object_canonical_order"].append(
            deepcopy(mutated["object_canonical_order"][0])
        )
    elif operator == "move_cell":
        mutated["source_canonical_order"][0]["manifest_index"] = 1
        mutated["source_canonical_order"][1]["manifest_index"] = 0
    elif operator == "resign_all_derived_surfaces":
        mutated["source_canonical_order"][0]["input_digest"] = "f" * 64
        mutated["source_keyset_digest"] = "e" * 64
        mutated["manifest_root"] = "d" * 64
    else:
        mutated["object_canonical_order"][0]["input_digest"] = "c" * 64
    mutated = with_result_digest(mutated)

    with pytest.raises(DellReportR14ContractError):
        validate_input_population_manifest_r14(mutated)

def test_r14_population_commitment_is_public_safe_and_does_not_repeat_private_ids() -> None:
    produced = _manifest(
        [_source("PRIVATE-SOURCE-ID", "private model text")],
        [_object("PRIVATE-OBJECT-ID", "PRIVATE-SOURCE-ID", "private model text")],
    )
    private_bytes = canonical_json_bytes(produced)
    commitment = build_population_commitment_r14(
        produced,
        private_sha256=sha256_bytes(private_bytes),
        private_bytes=len(private_bytes),
    )
    surface = canonical_json_bytes(commitment).decode("utf-8")

    assert "PRIVATE-SOURCE-ID" not in surface
    assert "PRIVATE-OBJECT-ID" not in surface
    assert "private source text" not in surface
    assert "private model text" not in surface
    assert "D:/private" not in surface
    assert commitment["privacy_contract"] == {
        "contains_raw_text": False,
        "contains_private_locator": False,
        "contains_source_or_object_ID_rows": False,
    }

    forged = deepcopy(commitment)
    forged["expected_lane_counts"]["total"] -= 1
    forged = with_result_digest(forged)
    with pytest.raises(
        DellReportR14ContractError,
        match="R14_population_commitment_lane_counts_invalid",
    ):
        validate_population_commitment_r14(forged)


def test_r14_population_rebuilder_has_no_producer_classifier_package_or_projection_dependency() -> None:
    path = ROOT / "src/retrieval/dell_report_population_rebuilder_r14.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert imports == {
        "__future__",
        "collections",
        "typing",
        "dell_report_r14_common",
    }
    for forbidden in (
        "population_manifest_r14",
        "predicate_frames",
        "internal_chain_ceiling",
        "classify_package",
        "candidate_ceiling",
        "public_projection",
        "private_result",
    ):
        assert forbidden not in source


def test_r14_real_population_exact_counts_families_and_independent_roots() -> None:
    source_rows = [
        json.loads(line)
        for line in (ROOT / SOURCE_REF).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    object_rows = [
        json.loads(line)
        for line in (ROOT / OBJECT_REF).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    produced = build_input_population_manifest_r14(
        source_rows=source_rows,
        object_rows=object_rows,
        source_ref=SOURCE_REF,
        source_sha256="d4c7e51790713d32fc10a9d0382b617f8ebd60861a3741d3adcee34392045d45",
        object_ref=OBJECT_REF,
        object_sha256="1c3e48486f933d23306dbabacb1641e26cb9bbc5b474da932d602752dff3fa92",
        implementation_identity="TEST::R14::REAL-POPULATION",
        changed_path_digest="d" * 64,
        recorded_at="2026-08-28T00:00:00+08:00",
    )
    rebuilt = rebuild_input_population_r14(
        source_rows=source_rows,
        object_rows=object_rows,
    )

    assert produced["source_records"]["count"] == 1888
    assert produced["compiled_objects"]["count"] == 34199
    assert produced["canonical_source_family_count"] == 1862
    assert produced["expected_lane_counts"]["total"] == 216522
    for field in (
        "source_keyset_digest",
        "object_keyset_digest",
        "parent_document_receipt_root",
        "canonical_family_occurrence_digest",
        "target_cross_product_digest",
        "manifest_root",
    ):
        assert produced[field] == rebuilt[field]
