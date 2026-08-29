from __future__ import annotations

from collections import Counter
import math
from typing import Any, Mapping, Sequence

from .dell_report_r14_common import (
    canonical_digest,
    canonical_json_bytes,
    domain_digest,
    domain_rows_digest,
    require,
    validate_result_digest,
)


_RECEIPT_SCHEMA = "fin_ia_dell_03B_R14_decision_vector_receipt_v1_0"
_DETAIL_SCHEMA = "fin_ia_dell_03B_R14_decision_detail_v1_0"
_ALPHABET_VERSION = "R14_outcome_2bit_C00_P01_N10_E11_v1"
_INDEX_VERSION = "R14_manifest_lane_index_v1"
_CODE_TO_OUTCOME = {0b00: "C", 0b01: "P", 0b10: "N", 0b11: "E"}


def _lane_entries(manifest: Mapping[str, Any], lane: str) -> list[Mapping[str, Any]]:
    require(lane in {"source", "compiled"}, "R14_rebuilder_lane_invalid")
    key = "source_canonical_order" if lane == "source" else "object_canonical_order"
    rows = list(manifest.get(key) or ())
    require(
        [int(row["manifest_index"]) for row in rows] == list(range(len(rows))),
        "R14_rebuilder_manifest_index_invalid",
    )
    return rows


def _decode(vector: bytes, length: int) -> list[str]:
    require(len(vector) == math.ceil(length / 4), "R14_rebuilder_byte_length_invalid")
    output: list[str] = []
    for index in range(length):
        shift = 6 - 2 * (index % 4)
        output.append(_CODE_TO_OUTCOME[(vector[index // 4] >> shift) & 0b11])
    if length % 4:
        unused_pairs = 4 - (length % 4)
        require(
            vector[-1] & ((1 << (unused_pairs * 2)) - 1) == 0,
            "R14_rebuilder_nonzero_padding",
        )
    return output


def rebuild_decision_vector_r14(
    *,
    manifest: Mapping[str, Any],
    receipt: Mapping[str, Any],
    details: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    validate_result_digest(receipt, code="R14_rebuilder_receipt")
    require(receipt.get("schema_version") == _RECEIPT_SCHEMA, "R14_rebuilder_schema_invalid")
    require(
        receipt.get("manifest_result_digest") == manifest.get("result_digest"),
        "R14_rebuilder_manifest_digest_mismatch",
    )
    require(
        receipt.get("canonical_index_version") == _INDEX_VERSION
        and receipt.get("outcome_alphabet", {}).get("version") == _ALPHABET_VERSION,
        "R14_rebuilder_encoding_contract_invalid",
    )
    lane = str(receipt.get("lane") or "")
    target_id = str(receipt.get("target_id") or "")
    entries = _lane_entries(manifest, lane)
    length = len(entries)
    require(
        int(receipt.get("expected_length") or -1) == length,
        "R14_rebuilder_expected_length_mismatch",
    )
    try:
        vector = bytes.fromhex(str(receipt.get("outcome_bytes_hex") or ""))
    except ValueError:
        require(False, "R14_rebuilder_hex_invalid")
    outcomes = _decode(vector, length)

    header = {
        "manifest_result_digest": manifest["result_digest"],
        "target_id": target_id,
        "lane": lane,
        "length": length,
        "outcome_alphabet_version": _ALPHABET_VERSION,
        "canonical_index_version": _INDEX_VERSION,
    }
    require(
        domain_digest(
            b"FIN_IA_R14_DECISION_VECTOR_V1\0",
            canonical_json_bytes(header),
            vector,
        )
        == receipt.get("vector_root"),
        "R14_rebuilder_vector_root_mismatch",
    )

    detail_by_index: dict[int, Mapping[str, Any]] = {}
    canonical_details: list[Mapping[str, Any]] = []
    for raw in details:
        row = dict(raw)
        require(
            set(row)
            == {
                "schema_version",
                "manifest_index",
                "input_digest",
                "target_id",
                "lane",
                "outcome",
                "vector_cell_code",
                "detail",
                "row_digest",
            }
            and row.get("schema_version") == _DETAIL_SCHEMA,
            "R14_rebuilder_detail_schema_invalid",
        )
        row_digest = row.pop("row_digest")
        require(
            row_digest == canonical_digest(row),
            "R14_rebuilder_detail_row_digest_mismatch",
        )
        row["row_digest"] = row_digest
        index = int(row["manifest_index"])
        require(index not in detail_by_index, "R14_rebuilder_detail_duplicate")
        require(0 <= index < length, "R14_rebuilder_detail_out_of_range")
        detail_by_index[index] = row
        canonical_details.append(row)
    canonical_details.sort(key=lambda row: int(row["manifest_index"]))
    require(
        canonical_details == list(details),
        "R14_rebuilder_detail_order_invalid",
    )
    require(
        domain_rows_digest(
            b"FIN_IA_R14_DECISION_DETAIL_V1\0",
            (canonical_json_bytes(row) for row in canonical_details),
        )
        == receipt.get("detail_root"),
        "R14_rebuilder_detail_root_mismatch",
    )

    for index, (entry, outcome) in enumerate(zip(entries, outcomes)):
        detail = detail_by_index.get(index)
        require(
            (detail is None) == (outcome == "N"),
            f"R14_rebuilder_detail_bijection_invalid:{index}",
        )
        if detail is None:
            continue
        require(
            detail["input_digest"] == entry["input_digest"]
            and detail["target_id"] == target_id
            and detail["lane"] == lane
            and detail["outcome"] == outcome
            and detail["vector_cell_code"]
            == {"C": "00", "P": "01", "N": "10", "E": "11"}[outcome],
            f"R14_rebuilder_detail_identity_mismatch:{index}",
        )

    counts = Counter(outcomes)
    rebuilt_counts = {key: int(counts.get(key, 0)) for key in ("C", "P", "N", "E")}
    require(
        rebuilt_counts == receipt.get("outcome_counts"),
        "R14_rebuilder_outcome_counts_mismatch",
    )
    require(
        len(details) == int(receipt.get("detail_count") or 0),
        "R14_rebuilder_detail_count_mismatch",
    )
    keyset_root = domain_rows_digest(
        b"FIN_IA_R14_REBUILT_OUTCOME_KEYSET_V1\0",
        (
            canonical_json_bytes(
                {
                    "manifest_index": index,
                    "input_digest": entry["input_digest"],
                    "target_id": target_id,
                    "lane": lane,
                    "outcome": outcomes[index],
                }
            )
            for index, entry in enumerate(entries)
        ),
    )
    return {
        "status": "PASS_INDEPENDENT_REBUILD",
        "target_id": target_id,
        "lane": lane,
        "length": length,
        "outcome_counts": rebuilt_counts,
        "detail_count": len(details),
        "vector_root": receipt["vector_root"],
        "detail_root": receipt["detail_root"],
        "outcome_keyset_root": keyset_root,
    }


__all__ = ["rebuild_decision_vector_r14"]
