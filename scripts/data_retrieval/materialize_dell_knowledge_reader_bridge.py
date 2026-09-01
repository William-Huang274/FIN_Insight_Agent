from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import urlsplit


RESULT_SCHEMA = "fin_ia_dell_knowledge_reader_bridge_result_v1_0"
ROW_AUTHORITY = "retrieval_candidate"
SOURCE_TIER = "official_primary_qualification_candidate"


class KnowledgeReaderBridgeError(ValueError):
    """Raised when the frozen input or mechanical field contract drifts."""


def _canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")) + "\n").encode("utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _mechanical_row(source: dict[str, Any], ordinal: int) -> dict[str, Any]:
    chunk_id = str(source.get("chunk_id") or "").strip()
    source_url = str(source.get("stable_url") or "").strip()
    text = str(source.get("text") or "").strip()
    publication_date = str(source.get("publication_date") or "").strip()
    source_role = str(source.get("source_role") or "").strip()
    title = str(source.get("title") or "").strip()
    parts = urlsplit(source_url)
    try:
        date.fromisoformat(publication_date)
    except ValueError as exc:
        raise KnowledgeReaderBridgeError(
            f"bridge_publication_date_invalid:{ordinal}"
        ) from exc
    if not (
        chunk_id and text and source_role and title
        and parts.scheme == "https" and parts.netloc
        and source.get("numeric_authority") is False
    ):
        raise KnowledgeReaderBridgeError(f"bridge_source_row_invalid:{ordinal}")
    return {
        "authority_state": ROW_AUTHORITY,
        "evidence_id": chunk_id,
        "source_url": source_url,
        "text": text,
        "publication_date": publication_date,
        "source_type": source_role,
        "source_tier": SOURCE_TIER,
        "section": title,
        "ticker": "",
        "period_end": "",
        "branches": source.get("branches") or [],
        "source_role": source_role,
        "publisher": str(source.get("publisher") or ""),
        "raw_body_sha256": str(source.get("raw_body_sha256") or ""),
        "candidate_is_not_evidence": True,
        "citation_eligible": False,
        "evidence_admission_performed": False,
    }


def materialize_bridge(
    *, input_chunks: Path | Sequence[Path],
    expected_input_sha256: str | Sequence[str],
    expected_input_count: int | Sequence[int],
    output_root: Path, attempt_id: str,
) -> dict[str, Any]:
    source_paths = (
        (input_chunks,) if isinstance(input_chunks, Path) else tuple(input_chunks)
    )
    expected_digests = (
        (expected_input_sha256,)
        if isinstance(expected_input_sha256, str)
        else tuple(expected_input_sha256)
    )
    expected_counts = (
        (expected_input_count,)
        if isinstance(expected_input_count, int)
        else tuple(expected_input_count)
    )
    if not (
        source_paths
        and len(source_paths) == len(expected_digests) == len(expected_counts)
    ):
        raise KnowledgeReaderBridgeError("bridge_input_set_shape_invalid")

    input_rows: list[dict[str, Any]] = []
    for input_index, (unresolved_path, raw_digest, raw_count) in enumerate(
        zip(source_paths, expected_digests, expected_counts, strict=True),
        start=1,
    ):
        source_path = unresolved_path.resolve()
        if not source_path.is_file():
            raise KnowledgeReaderBridgeError(
                f"bridge_input_unavailable:{input_index}"
            )
        expected_digest = str(raw_digest).strip().lower()
        if len(expected_digest) != 64 or any(
            character not in "0123456789abcdef" for character in expected_digest
        ):
            raise KnowledgeReaderBridgeError(
                f"bridge_expected_sha256_invalid:{input_index}"
            )
        observed_digest = _sha256(source_path)
        if observed_digest != expected_digest:
            raise KnowledgeReaderBridgeError(
                f"bridge_input_sha256_drift:{input_index}"
            )
        if int(raw_count) < 1:
            raise KnowledgeReaderBridgeError(
                f"bridge_expected_count_invalid:{input_index}"
            )
        input_rows.append({
            "input_index": input_index,
            "chunks_path": source_path.as_posix(),
            "expected_sha256": expected_digest,
            "observed_sha256": observed_digest,
            "expected_count": int(raw_count),
            "observed_count": 0,
        })

    output_lines: list[bytes] = []
    evidence_ids: set[str] = set()
    global_ordinal = 0
    for input_row in input_rows:
        observed_count = 0
        source_path = Path(input_row["chunks_path"])
        with source_path.open("r", encoding="utf-8") as stream:
            for source_ordinal, line in enumerate(stream, start=1):
                global_ordinal += 1
                try:
                    source = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise KnowledgeReaderBridgeError(
                        "bridge_source_json_invalid:"
                        f"{input_row['input_index']}:{source_ordinal}"
                    ) from exc
                if not isinstance(source, dict):
                    raise KnowledgeReaderBridgeError(
                        "bridge_source_shape_invalid:"
                        f"{input_row['input_index']}:{source_ordinal}"
                    )
                row = _mechanical_row(source, global_ordinal)
                if row["evidence_id"] in evidence_ids:
                    raise KnowledgeReaderBridgeError(
                        "bridge_evidence_id_duplicate:"
                        f"{input_row['input_index']}:{source_ordinal}"
                    )
                evidence_ids.add(row["evidence_id"])
                output_lines.append(_canonical_bytes(row))
                observed_count += 1
        input_row["observed_count"] = observed_count
        if observed_count != input_row["expected_count"]:
            raise KnowledgeReaderBridgeError(
                f"bridge_input_count_drift:{input_row['input_index']}"
            )

    total_expected_count = sum(row["expected_count"] for row in input_rows)
    if len(output_lines) != total_expected_count:
        raise KnowledgeReaderBridgeError("bridge_total_input_count_drift")

    root = output_root.resolve() / attempt_id
    try:
        root.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise KnowledgeReaderBridgeError("bridge_attempt_already_exists") from exc
    records_path = root / "records.jsonl"
    records_path.write_bytes(b"".join(output_lines))
    output_digest = _sha256(records_path)
    result = {
        "schema_version": RESULT_SCHEMA,
        "status": "qualification_candidate_bridge_materialized",
        "attempt_id": attempt_id,
        "authority_state": "retrieval_candidate_set",
        "input": (
            dict(input_rows[0])
            if len(input_rows) == 1
            else {
                "input_set_count": len(input_rows),
                "expected_count": total_expected_count,
                "observed_count": len(output_lines),
            }
        ),
        "inputs": input_rows,
        "output": {
            "records_path": records_path.as_posix(),
            "sha256": output_digest,
            "record_count": len(output_lines),
        },
        "mapping_contract": {
            "evidence_id": "chunk_id", "source_url": "stable_url",
            "text": "text", "publication_date": "publication_date",
            "source_type": "source_role", "source_tier": SOURCE_TIER,
            "section": "title", "ticker": "", "period_end": "",
            "input_order": "caller_declared_then_source_line_order",
        },
        "candidate_is_not_evidence": True,
        "citation_eligible": False,
        "evidence_admission_performed": False,
        "model_calls": 0,
        "network_calls": 0,
    }
    result_path = root / "result.json"
    result_path.write_bytes(_canonical_bytes(result))
    result["result_path"] = result_path.as_posix()
    result["result_sha256"] = _sha256(result_path)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-chunks", type=Path, action="append", required=True)
    parser.add_argument("--expected-input-sha256", action="append", required=True)
    parser.add_argument("--expected-input-count", type=int, action="append", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--attempt-id", required=True)
    args = parser.parse_args()
    result = materialize_bridge(
        input_chunks=args.input_chunks,
        expected_input_sha256=args.expected_input_sha256,
        expected_input_count=args.expected_input_count,
        output_root=args.output_root,
        attempt_id=args.attempt_id,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
