from __future__ import annotations

from collections import Counter
import math
from typing import Any, Mapping, Sequence

from .dell_report_population_manifest_r14 import MANIFEST_SCHEMA_VERSION
from .dell_report_r14_common import (
    TARGET_IDS,
    canonical_digest,
    canonical_json_bytes,
    domain_digest,
    domain_rows_digest,
    require,
    require_identifier,
    require_sha256,
    validate_result_digest,
    with_result_digest,
)


DECISION_VECTOR_SCHEMA_VERSION = "fin_ia_dell_03B_R14_decision_vector_receipt_v1_0"
DECISION_DETAIL_SCHEMA_VERSION = "fin_ia_dell_03B_R14_decision_detail_v1_0"
OUTCOME_ALPHABET_VERSION = "R14_outcome_2bit_C00_P01_N10_E11_v1"
CANONICAL_INDEX_VERSION = "R14_manifest_lane_index_v1"
OUTCOME_TO_CODE = {"C": 0b00, "P": 0b01, "N": 0b10, "E": 0b11}
CODE_TO_OUTCOME = {value: key for key, value in OUTCOME_TO_CODE.items()}


def _manifest_entries(
    manifest: Mapping[str, Any], *, lane: str
) -> list[Mapping[str, Any]]:
    require(
        manifest.get("schema_version") == MANIFEST_SCHEMA_VERSION,
        "R14_vector_manifest_schema_invalid",
    )
    require(lane in {"source", "compiled"}, "R14_vector_lane_invalid")
    key = "source_canonical_order" if lane == "source" else "object_canonical_order"
    entries = list(manifest.get(key) or ())
    require(
        [int(row["manifest_index"]) for row in entries] == list(range(len(entries))),
        "R14_vector_manifest_index_invalid",
    )
    return entries


def _pack_outcomes(outcomes: Sequence[str]) -> bytes:
    output = bytearray(math.ceil(len(outcomes) / 4))
    for index, outcome in enumerate(outcomes):
        require(outcome in OUTCOME_TO_CODE, f"R14_vector_outcome_invalid:{outcome}")
        shift = 6 - 2 * (index % 4)
        output[index // 4] |= OUTCOME_TO_CODE[outcome] << shift
    return bytes(output)


def _detail_payload_valid(outcome: str, payload: Mapping[str, Any]) -> bool:
    if outcome == "C":
        return (
            set(payload)
            == {"accepted_event_ids", "target_topology_digest", "package_digest"}
            and
            bool(payload.get("accepted_event_ids"))
            and bool(payload.get("target_topology_digest"))
            and bool(payload.get("package_digest"))
        )
    if outcome == "P":
        return (
            set(payload)
            == {"candidate_proof_ids", "limitations", "graph_digest"}
            and
            bool(payload.get("candidate_proof_ids"))
            and bool(payload.get("limitations"))
            and bool(payload.get("graph_digest"))
        )
    if outcome == "E":
        return (
            set(payload) == {"malformed_input_key", "typed_error_code"}
            and bool(payload.get("malformed_input_key"))
            and bool(payload.get("typed_error_code"))
        )
    return not payload


def build_decision_vector_receipt_r14(
    *,
    manifest: Mapping[str, Any],
    target_id: str,
    lane: str,
    cells: Sequence[Mapping[str, Any]],
    parser_version: str,
    target_topology_digest: str,
    price_graph_version: str,
    pre_registered_malformed_keys: Sequence[str] = (),
) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    entries = _manifest_entries(manifest, lane=lane)
    require(target_id in TARGET_IDS, "R14_vector_target_invalid")
    require(len(cells) == len(entries), "R14_vector_cell_length_mismatch")
    malformed = set(pre_registered_malformed_keys)
    outcomes: list[str] = []
    details: list[dict[str, Any]] = []
    for index, (entry, raw_cell) in enumerate(zip(entries, cells)):
        cell = dict(raw_cell)
        require(
            set(cell) == {
                "manifest_index",
                "input_digest",
                "target_id",
                "lane",
                "outcome",
                "detail",
            },
            f"R14_vector_cell_schema_invalid:{index}",
        )
        require(
            cell["manifest_index"] == index
            and cell["input_digest"] == entry["input_digest"]
            and cell["target_id"] == target_id
            and cell["lane"] == lane,
            f"R14_vector_cell_identity_mismatch:{index}",
        )
        outcome = str(cell["outcome"])
        require(outcome in OUTCOME_TO_CODE, f"R14_vector_outcome_invalid:{index}")
        payload = dict(cell.get("detail") or {})
        if outcome == "N":
            require(not payload, f"R14_vector_N_detail_forbidden:{index}")
        else:
            require(
                _detail_payload_valid(outcome, payload),
                f"R14_vector_detail_payload_invalid:{index}:{outcome}",
            )
            if outcome == "C":
                require(
                    tuple(sorted(set(payload["accepted_event_ids"])))
                    == tuple(payload["accepted_event_ids"])
                    and
                    all(
                        bool(require_identifier(row, field="accepted_event_id"))
                        for row in payload["accepted_event_ids"]
                    ),
                    f"R14_vector_C_event_identity_invalid:{index}",
                )
                require_sha256(
                    payload["target_topology_digest"], field="target_topology"
                )
                require_sha256(payload["package_digest"], field="package")
            elif outcome == "P":
                require(
                    tuple(sorted(set(payload["candidate_proof_ids"])))
                    == tuple(payload["candidate_proof_ids"])
                    and tuple(sorted(set(payload["limitations"])))
                    == tuple(payload["limitations"])
                    and all(
                        bool(require_identifier(row, field="candidate_proof_id"))
                        for row in payload["candidate_proof_ids"]
                    )
                    and all(
                        bool(require_identifier(row, field="limitation"))
                        for row in payload["limitations"]
                    ),
                    f"R14_vector_P_evidence_invalid:{index}",
                )
                require_sha256(payload["graph_digest"], field="graph")
            if outcome == "E":
                require(
                    payload["malformed_input_key"] in malformed,
                    f"R14_vector_E_not_pre_registered:{index}",
                )
                require_identifier(
                    payload["typed_error_code"], field="typed_error_code"
                )
            detail_body = {
                "schema_version": DECISION_DETAIL_SCHEMA_VERSION,
                "manifest_index": index,
                "input_digest": entry["input_digest"],
                "target_id": target_id,
                "lane": lane,
                "outcome": outcome,
                "vector_cell_code": f"{OUTCOME_TO_CODE[outcome]:02b}",
                "detail": payload,
            }
            details.append({**detail_body, "row_digest": canonical_digest(detail_body)})
        outcomes.append(outcome)

    vector_bytes = _pack_outcomes(outcomes)
    expected_bytes = math.ceil(len(entries) / 4)
    require(len(vector_bytes) == expected_bytes, "R14_vector_byte_length_invalid")
    if len(entries) % 4:
        unused_pairs = 4 - (len(entries) % 4)
        require(
            vector_bytes[-1] & ((1 << (unused_pairs * 2)) - 1) == 0,
            "R14_vector_nonzero_padding",
        )
    header = {
        "manifest_result_digest": require_sha256(
            manifest.get("result_digest"), field="manifest_result_digest"
        ),
        "target_id": target_id,
        "lane": lane,
        "length": len(entries),
        "outcome_alphabet_version": OUTCOME_ALPHABET_VERSION,
        "canonical_index_version": CANONICAL_INDEX_VERSION,
    }
    vector_root = domain_digest(
        b"FIN_IA_R14_DECISION_VECTOR_V1\0",
        canonical_json_bytes(header),
        vector_bytes,
    )
    detail_root = domain_rows_digest(
        b"FIN_IA_R14_DECISION_DETAIL_V1\0",
        (canonical_json_bytes(row) for row in details),
    )
    counts = Counter(outcomes)
    body = {
        "schema_version": DECISION_VECTOR_SCHEMA_VERSION,
        "manifest_result_digest": manifest["result_digest"],
        "target_id": target_id,
        "lane": lane,
        "expected_length": len(entries),
        "canonical_index_version": CANONICAL_INDEX_VERSION,
        "outcome_alphabet": {
            "version": OUTCOME_ALPHABET_VERSION,
            "C": "00",
            "P": "01",
            "N": "10",
            "E": "11",
        },
        "outcome_bytes_hex": vector_bytes.hex(),
        "outcome_counts": {key: int(counts.get(key, 0)) for key in ("C", "P", "N", "E")},
        "vector_root": vector_root,
        "detail_root": detail_root,
        "detail_count": len(details),
        "checks": {
            "missing": 0,
            "duplicate": 0,
            "orphan": 0,
            "out_of_range": 0,
            "nonzero_padding": 0,
        },
        "parser_version": require_identifier(parser_version, field="parser_version"),
        "target_topology_digest": require_sha256(
            target_topology_digest, field="target_topology_digest"
        ),
        "price_graph_version": require_identifier(
            price_graph_version, field="price_graph_version"
        ),
    }
    receipt = with_result_digest(body)
    validate_decision_vector_receipt_r14(receipt)
    return receipt, tuple(details)


def validate_decision_vector_receipt_r14(value: Mapping[str, Any]) -> None:
    validate_result_digest(value, code="R14_vector_receipt")
    require(
        set(value)
        == {
            "schema_version",
            "manifest_result_digest",
            "target_id",
            "lane",
            "expected_length",
            "canonical_index_version",
            "outcome_alphabet",
            "outcome_bytes_hex",
            "outcome_counts",
            "vector_root",
            "detail_root",
            "detail_count",
            "checks",
            "parser_version",
            "target_topology_digest",
            "price_graph_version",
            "result_digest",
        },
        "R14_vector_receipt_keyset_invalid",
    )
    require(
        value.get("schema_version") == DECISION_VECTOR_SCHEMA_VERSION,
        "R14_vector_receipt_schema_invalid",
    )
    require(value.get("target_id") in TARGET_IDS, "R14_vector_receipt_target_invalid")
    require(value.get("lane") in {"source", "compiled"}, "R14_vector_receipt_lane_invalid")
    require(
        value.get("canonical_index_version") == CANONICAL_INDEX_VERSION
        and value.get("outcome_alphabet")
        == {
            "version": OUTCOME_ALPHABET_VERSION,
            "C": "00",
            "P": "01",
            "N": "10",
            "E": "11",
        },
        "R14_vector_receipt_encoding_contract_invalid",
    )
    require_sha256(value.get("manifest_result_digest"), field="manifest_result_digest")
    require_sha256(value.get("vector_root"), field="vector_root")
    require_sha256(value.get("detail_root"), field="detail_root")
    require_sha256(value.get("target_topology_digest"), field="target_topology_digest")
    require_identifier(value.get("parser_version"), field="parser_version")
    require_identifier(value.get("price_graph_version"), field="price_graph_version")
    require(
        isinstance(value.get("expected_length"), int)
        and int(value["expected_length"]) >= 0,
        "R14_vector_receipt_expected_length_invalid",
    )
    expected_length = int(value["expected_length"])
    try:
        vector_bytes = bytes.fromhex(str(value.get("outcome_bytes_hex") or ""))
    except ValueError:
        require(False, "R14_vector_receipt_hex_invalid")
        raise AssertionError("unreachable")
    require(
        len(vector_bytes) == math.ceil(expected_length / 4),
        "R14_vector_receipt_byte_length_invalid",
    )
    outcomes: list[str] = []
    for index in range(expected_length):
        shift = 6 - 2 * (index % 4)
        outcomes.append(CODE_TO_OUTCOME[(vector_bytes[index // 4] >> shift) & 0b11])
    if expected_length % 4:
        unused_pairs = 4 - (expected_length % 4)
        require(
            vector_bytes[-1] & ((1 << (unused_pairs * 2)) - 1) == 0,
            "R14_vector_receipt_nonzero_padding",
        )
    outcome_counts = value.get("outcome_counts")
    require(
        isinstance(outcome_counts, dict)
        and set(outcome_counts) == {"C", "P", "N", "E"}
        and all(
            isinstance(outcome_counts[key], int) and outcome_counts[key] >= 0
            for key in ("C", "P", "N", "E")
        ),
        "R14_vector_receipt_outcome_counts_schema_invalid",
    )
    recomputed_counts = Counter(outcomes)
    require(
        {key: int(recomputed_counts.get(key, 0)) for key in ("C", "P", "N", "E")}
        == outcome_counts,
        "R14_vector_receipt_counts_invalid",
    )
    header = {
        "manifest_result_digest": value["manifest_result_digest"],
        "target_id": value["target_id"],
        "lane": value["lane"],
        "length": expected_length,
        "outcome_alphabet_version": OUTCOME_ALPHABET_VERSION,
        "canonical_index_version": CANONICAL_INDEX_VERSION,
    }
    require(
        value.get("vector_root")
        == domain_digest(
            b"FIN_IA_R14_DECISION_VECTOR_V1\0",
            canonical_json_bytes(header),
            vector_bytes,
        ),
        "R14_vector_receipt_vector_root_invalid",
    )
    require(
        isinstance(value.get("detail_count"), int)
        and int(value["detail_count"])
        == sum(int(outcome_counts[key]) for key in ("C", "P", "E")),
        "R14_vector_receipt_detail_count_invalid",
    )
    require(
        value.get("checks")
        == {
            "missing": 0,
            "duplicate": 0,
            "orphan": 0,
            "out_of_range": 0,
            "nonzero_padding": 0,
        },
        "R14_vector_receipt_checks_invalid",
    )


__all__ = [
    "CANONICAL_INDEX_VERSION",
    "CODE_TO_OUTCOME",
    "DECISION_DETAIL_SCHEMA_VERSION",
    "DECISION_VECTOR_SCHEMA_VERSION",
    "OUTCOME_ALPHABET_VERSION",
    "OUTCOME_TO_CODE",
    "build_decision_vector_receipt_r14",
    "validate_decision_vector_receipt_r14",
]
