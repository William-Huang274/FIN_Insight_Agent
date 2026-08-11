from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sec_agent.runtime_bridge.object_store import put_object, put_json_object


USER_PROVIDED_EVIDENCE_PACK_SCHEMA_VERSION = "finsight_user_provided_evidence_pack_v0_1"


def parse_user_input_file(
    path: str | Path,
    *,
    object_store_root: str | Path,
    run_id: str = "",
) -> dict[str, Any]:
    source = Path(path).resolve()
    if not source.exists() or not source.is_file():
        raise FileNotFoundError(str(source))
    source_ref = put_object(source, object_store_root=object_store_root, namespace="uploads", artifact_type="user_upload")
    suffix = source.suffix.lower()
    parser_result = _parse_supported_file(source, suffix=suffix)
    artifact_payload = {
        "schema_version": USER_PROVIDED_EVIDENCE_PACK_SCHEMA_VERSION,
        "run_id": run_id,
        "source_file": source_ref,
        "parser": parser_result["parser"],
        "status": parser_result["status"],
        "records": parser_result["records"],
        "gaps": parser_result["gaps"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "promotion_policy": "user_provided_rows_require_provenance_and_claim_gate_before_runtime_fact_v0_1",
    }
    parsed_ref = put_json_object(
        artifact_payload,
        object_store_root=object_store_root,
        namespace="parsed_inputs",
        artifact_type="user_provided_evidence_pack",
        stem=source.stem,
    )
    return {
        **artifact_payload,
        "artifact_ref": parsed_ref,
        "uploaded_file": {
            "file_id": source_ref["sha256"],
            "filename": source.name,
            "path": str(source),
            "artifact_uri": source_ref["artifact_uri"],
            "checksum": source_ref["sha256"],
        },
        "parsed_input_artifact": {
            "artifact_id": parsed_ref["sha256"],
            "source_file_id": source_ref["sha256"],
            "artifact_uri": parsed_ref["artifact_uri"],
            "parser": parser_result["parser"],
            "status": parser_result["status"],
        },
    }


def _parse_supported_file(path: Path, *, suffix: str) -> dict[str, Any]:
    if suffix in {".txt", ".md"}:
        text = path.read_text(encoding="utf-8", errors="replace")
        return {
            "parser": "plain_text_markdown_parser_v0_1",
            "status": "pass",
            "records": [_record(path, text=text, record_type="text")],
            "gaps": [],
        }
    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        return {
            "parser": "json_parser_v0_1",
            "status": "pass",
            "records": [_record(path, text=json.dumps(payload, ensure_ascii=False, sort_keys=True), record_type="json", payload=payload)],
            "gaps": [],
        }
    if suffix == ".csv":
        records = []
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for index, row in enumerate(reader, start=1):
                records.append(_record(path, text=json.dumps(row, ensure_ascii=False, sort_keys=True), record_type="table_row", row_index=index, payload=row))
        return {
            "parser": "csv_table_parser_v0_1",
            "status": "pass",
            "records": records,
            "gaps": [],
        }
    return {
        "parser": "parser_not_configured",
        "status": "gap",
        "records": [],
        "gaps": [
            {
                "gap_type": "parser_not_configured",
                "suffix": suffix,
                "reason": "Install/configure a parser for this file type before promoting it into evidence.",
            }
        ],
    }


def _record(path: Path, *, text: str, record_type: str, row_index: int | None = None, payload: Any | None = None) -> dict[str, Any]:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    record = {
        "record_id": f"{path.stem}:{digest[:16]}",
        "source_path": str(path),
        "record_type": record_type,
        "text": text,
        "sha256": digest,
        "source_boundary": "user_provided_context_not_runtime_fact_until_gate",
    }
    if row_index is not None:
        record["table_id"] = path.stem
        record["row_index"] = row_index
    if payload is not None:
        record["payload"] = payload
    return record
