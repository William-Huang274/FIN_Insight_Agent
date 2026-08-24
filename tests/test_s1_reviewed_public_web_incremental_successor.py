from __future__ import annotations

from collections import deque
import hashlib
import json
from pathlib import Path

from retrieval.query_plan import canonical_digest


ROOT = Path(__file__).resolve().parents[1]
MISSING_PAGE_ID = "PUBLIC::DELL-EXT::2184F13EB685F627C757"


def _json(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def _sha256(relative: str) -> str:
    digest = hashlib.sha256()
    with (ROOT / relative).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _jsonl_tail(relative: str, count: int) -> list[dict]:
    rows: deque[dict] = deque(maxlen=count)
    with (ROOT / relative).open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return list(rows)


def test_public_web_incremental_successor_is_exact_append() -> None:
    result = _json(
        "configs/retrieval/"
        "fin_ia_0_1_3_s1_reviewed_public_web_incremental_successor_result_v1_0.json"
    )
    body = dict(result)
    assert body.pop("result_digest") == canonical_digest(body)
    assert result["summary"] == {
        "appended_canonical_source_record_count": 2,
        "appended_object_count": 9,
        "appended_page_ids": [MISSING_PAGE_ID],
        "appended_slice_ids": [
            MISSING_PAGE_ID + "::SLICE::62BC91E7D73822D5A187"
        ],
        "base_object_count": 34189,
        "base_source_record_count": 1886,
        "successor_object_count": 34198,
        "successor_source_record_count": 1888,
    }
    assert result["acceptance"]["base_objects_retained_exactly"] is True
    assert result["acceptance"][
        "base_source_records_retained_exactly"
    ] is True

    appended_records = _jsonl_tail(result["outputs"]["source_records_ref"], 2)
    assert {row["source_type"] for row in appended_records} == {"PUBLIC_WEB"}
    assert MISSING_PAGE_ID in {
        row["evidence_id"] for row in appended_records
    }
    appended_objects = _jsonl_tail(result["outputs"]["objects_ref"], 9)
    assert {
        row["base_object_view"]["source_lineage"]["source_page_record_id"]
        for row in appended_objects
    } == {MISSING_PAGE_ID}
    assert _sha256(result["outputs"]["objects_ref"]) == result["outputs"][
        "objects_sha256"
    ]


def test_public_web_incremental_embedding_is_cuda_fp16_append_only() -> None:
    result = _json(
        "configs/retrieval/"
        "fin_ia_0_1_3_s1c_qwen_embedding_cache_successor_result_v1_2.json"
    )
    assert result["runtime"] == {
        "base_object_count_reused": 34189,
        "cache_dtype": "float16",
        "cpu_fallback_count": 0,
        "device": "cuda:0",
        "model_generation_calls": 0,
        "network_calls": 0,
        "new_object_count_embedded": 9,
        "parameter_dtype": "torch.float16",
    }
    manifest = _json(result["outputs"]["cache_manifest_ref"])
    assert manifest["object_count"] == 34198
    assert manifest["append"]["object_count"] == 9
    assert manifest["append"]["cpu_fallback_count"] == 0


def test_r38_current_runtime_closes_only_the_source_object_sync_gap() -> None:
    receipt = _json(
        "configs/runtime/"
        "fin_ia_0_1_3_current_s1_runtime_binding_receipt_v1_14.json"
    )
    assert receipt["registry_binding"]["registry_id"].endswith("R38")
    assert receipt["source_object_index_lineage"]["source_record_count"] == 1888
    assert receipt["source_object_index_lineage"]["compiled_object_count"] == 34198
    assert receipt["embedding_index"]["object_count"] == 34198
    assert receipt["acceptance"]["s1_qualified_stable"] is False

    snapshot = _json(
        "configs/runtime/fin_ia_0_1_3_current_retrieval_snapshot_v1_4.json"
    )
    dell = next(row for row in snapshot["cases"] if row["case_key"] == "DELL")
    assert dell["source_gap_summary"][
        "reviewed_label_occurrences_missing_from_current_corpus"
    ] == 0
    assert dell["source_gap_summary"][
        "reviewed_label_occurrences_eligible_before_scoring"
    ] == 115
    assert dell["source_gap_summary"][
        "reviewed_label_occurrences_matched_after_scoring"
    ] == 35


def test_r37_and_r38_failure_receipts_are_immutable_and_digest_valid() -> None:
    for relative in (
        "configs/audits/"
        "fin_ia_0_1_3_r37_full_repository_gate_R1_failure_assessment_v1_0.json",
        "configs/audits/"
        "fin_ia_0_1_3_r38_public_web_runtime_promotion_P1_failure_assessment_v1_0.json",
    ):
        payload = _json(relative)
        body = dict(payload)
        assert body.pop("result_digest") == canonical_digest(body)
        assert payload["status"].startswith("failed")
        assert payload["authority"]["model_calls"] == 0
        assert payload["authority"]["network_calls"] == 0
