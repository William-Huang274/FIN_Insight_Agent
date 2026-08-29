from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path

import pytest

from retrieval.dell_report_decision_vector_r14 import (
    build_decision_vector_receipt_r14,
)
from retrieval.dell_report_decision_vector_rebuilder_r14 import (
    rebuild_decision_vector_r14,
)
from retrieval.dell_report_population_manifest_r14 import (
    build_input_population_manifest_r14,
)
from retrieval.dell_report_r14_common import (
    DellReportR14ContractError,
    domain_rows_digest,
    canonical_json_bytes,
    with_result_digest,
)


ROOT = Path(__file__).resolve().parents[1]
TARGET = "DELL-RSQ-03A-TARGET-ASP"


def _source(index: int) -> dict:
    return {
        "evidence_id": f"S{index}",
        "text": f"text {index}",
        "metadata": {"source_page_record_id": f"F{index}"},
    }


def _manifest() -> dict:
    return build_input_population_manifest_r14(
        source_rows=[_source(index) for index in range(5)],
        object_rows=[],
        source_ref="private/sources.jsonl",
        source_sha256="a" * 64,
        object_ref="private/objects.jsonl",
        object_sha256="b" * 64,
        implementation_identity="TEST::R14::I",
        changed_path_digest="c" * 64,
        recorded_at="2026-08-29T00:00:00+08:00",
    )


def _cells(manifest: dict) -> list[dict]:
    outcomes = ["C", "P", "N", "E", "N"]
    details = [
        {
            "accepted_event_ids": ["EVENT::R14::A"],
            "target_topology_digest": "d" * 64,
            "package_digest": "e" * 64,
        },
        {
            "candidate_proof_ids": ["PROOF::R14::P"],
            "limitations": ["missing_price"],
            "graph_digest": "f" * 64,
        },
        {},
        {
            "malformed_input_key": "S3",
            "typed_error_code": "PRE_REGISTERED_BAD_ENCODING",
        },
        {},
    ]
    return [
        {
            "manifest_index": index,
            "input_digest": row["input_digest"],
            "target_id": TARGET,
            "lane": "source",
            "outcome": outcomes[index],
            "detail": details[index],
        }
        for index, row in enumerate(manifest["source_canonical_order"])
    ]


def _build():
    manifest = _manifest()
    receipt, details = build_decision_vector_receipt_r14(
        manifest=manifest,
        target_id=TARGET,
        lane="source",
        cells=_cells(manifest),
        parser_version="conservative_event_proof_v1",
        target_topology_digest="1" * 64,
        price_graph_version="price_attachment_graph_v1",
        pre_registered_malformed_keys=("S3",),
    )
    return manifest, receipt, details


def test_r14_decision_vector_exact_big_endian_bits_padding_counts_and_roots() -> None:
    manifest, receipt, details = _build()

    assert receipt["outcome_bytes_hex"] == "1b80"
    assert receipt["expected_length"] == 5
    assert receipt["outcome_counts"] == {"C": 1, "P": 1, "N": 2, "E": 1}
    assert receipt["detail_count"] == 3
    assert [row["manifest_index"] for row in details] == [0, 1, 3]
    assert all(row["row_digest"] for row in details)

    rebuilt = rebuild_decision_vector_r14(
        manifest=manifest, receipt=receipt, details=details
    )
    assert rebuilt["status"] == "PASS_INDEPENDENT_REBUILD"
    assert rebuilt["outcome_counts"] == receipt["outcome_counts"]
    assert rebuilt["vector_root"] == receipt["vector_root"]
    assert rebuilt["detail_root"] == receipt["detail_root"]


def test_r14_independent_rebuilder_rejects_bit_flip_and_nonzero_padding() -> None:
    manifest, receipt, details = _build()
    bit_flip = deepcopy(receipt)
    bit_flip["outcome_bytes_hex"] = "5b80"
    bit_flip = with_result_digest(bit_flip)
    with pytest.raises(DellReportR14ContractError, match="R14_rebuilder_vector_root"):
        rebuild_decision_vector_r14(
            manifest=manifest, receipt=bit_flip, details=details
        )

    padding = deepcopy(receipt)
    padding["outcome_bytes_hex"] = "1b81"
    padding = with_result_digest(padding)
    with pytest.raises(DellReportR14ContractError, match="R14_rebuilder_nonzero_padding"):
        rebuild_decision_vector_r14(
            manifest=manifest, receipt=padding, details=details
        )


def test_r14_independent_rebuilder_rejects_detail_delete_after_all_derived_resigned() -> None:
    manifest, receipt, details = _build()
    reduced = tuple(row for row in details if row["manifest_index"] != 1)
    mutated = deepcopy(receipt)
    mutated["detail_count"] = len(reduced)
    mutated["detail_root"] = domain_rows_digest(
        b"FIN_IA_R14_DECISION_DETAIL_V1\0",
        (canonical_json_bytes(row) for row in reduced),
    )
    mutated = with_result_digest(mutated)

    with pytest.raises(
        DellReportR14ContractError,
        match="R14_rebuilder_detail_bijection_invalid",
    ):
        rebuild_decision_vector_r14(
            manifest=manifest, receipt=mutated, details=reduced
        )


def test_r14_vector_producer_rejects_N_detail_and_unregistered_E() -> None:
    manifest = _manifest()
    cells = _cells(manifest)
    cells[2]["detail"] = {"author_note": "not allowed"}
    with pytest.raises(DellReportR14ContractError, match="R14_vector_N_detail"):
        build_decision_vector_receipt_r14(
            manifest=manifest,
            target_id=TARGET,
            lane="source",
            cells=cells,
            parser_version="parser",
            target_topology_digest="1" * 64,
            price_graph_version="price",
            pre_registered_malformed_keys=("S3",),
        )

    cells = _cells(manifest)
    with pytest.raises(DellReportR14ContractError, match="R14_vector_E_not_pre_registered"):
        build_decision_vector_receipt_r14(
            manifest=manifest,
            target_id=TARGET,
            lane="source",
            cells=cells,
            parser_version="parser",
            target_topology_digest="1" * 64,
            price_graph_version="price",
            pre_registered_malformed_keys=(),
        )


def test_r14_independent_rebuilder_has_no_producer_or_summary_dependency() -> None:
    path = ROOT / "src/retrieval/dell_report_decision_vector_rebuilder_r14.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert "dell_report_decision_vector_r14" not in imports
    assert "summary" not in source
    assert "project" not in source
