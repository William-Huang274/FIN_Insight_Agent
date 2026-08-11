from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.raw_source_provenance_store import (  # noqa: E402
    _fetch_attempt_from_document,
    _first_text,
    _is_runtime_candidate,
    _match_source_document,
    _read_jsonl,
    _row_source_url,
    _runtime_declared_source_document,
    _runtime_lineage_row,
    _runtime_row_raw_path,
    _snapshot_from_document,
    _source_document_maps,
    build_raw_source_provenance_summary,
    discover_runtime_rowset_paths,
    render_raw_source_provenance_report,
    write_json,
    write_jsonl,
)


DEFAULT_OUTPUT_DOCUMENTS = REPO_ROOT / "data" / "manifests" / "raw_source_documents_v0_1.jsonl"
DEFAULT_OUTPUT_ATTEMPTS = REPO_ROOT / "data" / "manifests" / "raw_fetch_attempts_v0_1.jsonl"
DEFAULT_OUTPUT_SNAPSHOTS = REPO_ROOT / "data" / "manifests" / "source_snapshots_v0_1.jsonl"
DEFAULT_OUTPUT_LINEAGE = REPO_ROOT / "data" / "manifests" / "runtime_row_source_lineage_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "raw_source_provenance_summary_v0_1.json"
DEFAULT_OUTPUT_REPORT = REPO_ROOT / "docs" / "internal" / "vnext_20260610" / "rd1_raw_source_provenance_store.zh-CN.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Repair RD1 runtime lineage from existing source documents without rescanning the raw lake. "
            "Use after source documents already exist but lineage/summary are stale or half-built."
        )
    )
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--input-documents", type=Path, default=DEFAULT_OUTPUT_DOCUMENTS)
    parser.add_argument("--input-attempts", type=Path, default=DEFAULT_OUTPUT_ATTEMPTS)
    parser.add_argument("--output-documents", type=Path, default=DEFAULT_OUTPUT_DOCUMENTS)
    parser.add_argument("--output-attempts", type=Path, default=DEFAULT_OUTPUT_ATTEMPTS)
    parser.add_argument("--output-snapshots", type=Path, default=DEFAULT_OUTPUT_SNAPSHOTS)
    parser.add_argument("--output-lineage", type=Path, default=DEFAULT_OUTPUT_LINEAGE)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    return parser.parse_args()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        cleaned = str(value or "").strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        output.append(cleaned)
    return output


def _augment_existing_source_document(row: Mapping[str, Any]) -> dict[str, Any]:
    doc = dict(row)
    ticker = str(doc.get("ticker") or "").strip().upper()
    companyfacts_scope = " ".join(
        str(doc.get(key) or "")
        for key in ("source_family", "source_id", "document_type", "source_url", "raw_path", "absolute_raw_path")
    ).lower()
    if ticker and "companyfacts" in companyfacts_scope:
        keys = [str(key) for key in (doc.get("external_document_keys") or [])]
        keys.append(f"sec_companyfacts_by_ticker:{ticker}")
        doc["external_document_keys"] = _unique(keys)
    return doc


def repair_raw_source_provenance_lineage_from_existing_documents(
    repo_root: str | Path,
    *,
    input_documents: str | Path,
    input_attempts: str | Path,
    generated_at: str | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    generated_at = generated_at or _utc_now()
    documents_by_id: dict[str, dict[str, Any]] = {}
    for row in _read_jsonl(Path(input_documents)):
        doc = _augment_existing_source_document(row)
        document_id = str(doc.get("raw_source_document_id") or "")
        if document_id:
            documents_by_id[document_id] = doc

    source_maps = _source_document_maps(documents_by_id.values())
    runtime_manifests = discover_runtime_rowset_paths(root)
    runtime_lineage_rows: list[dict[str, Any]] = []

    for manifest_path in runtime_manifests:
        for ordinal, runtime_row in enumerate(_read_jsonl(manifest_path), start=1):
            if not _is_runtime_candidate(runtime_row):
                continue
            source_url = _row_source_url(runtime_row)
            source_document_ref = _first_text(runtime_row, "source_document_id", "raw_path")
            raw_path = _runtime_row_raw_path(root, source_document_ref)
            match = _match_source_document(
                root,
                runtime_row,
                source_url=source_url,
                raw_path=raw_path,
                source_maps=source_maps,
            )
            if str(match.get("lineage_status") or "").startswith("unresolved"):
                document_row = _runtime_declared_source_document(
                    root,
                    manifest_path,
                    runtime_row,
                    generated_at=generated_at,
                    max_hash_bytes=0,
                )
                if document_row and document_row["raw_source_document_id"] not in documents_by_id:
                    documents_by_id[document_row["raw_source_document_id"]] = document_row
                    source_maps = _source_document_maps(documents_by_id.values())
            runtime_lineage_rows.append(
                _runtime_lineage_row(
                    root,
                    manifest_path,
                    runtime_row,
                    ordinal=ordinal,
                    source_maps=source_maps,
                    generated_at=generated_at,
                )
            )

    source_documents = sorted(documents_by_id.values(), key=lambda item: str(item.get("raw_source_document_id") or ""))
    existing_attempts = _read_jsonl(Path(input_attempts)) if Path(input_attempts).exists() else []
    attempts_by_id = {
        str(row.get("raw_fetch_attempt_id") or ""): dict(row)
        for row in existing_attempts
        if str(row.get("raw_fetch_attempt_id") or "")
    }
    for document in source_documents:
        attempt = _fetch_attempt_from_document(document, generated_at=generated_at)
        attempts_by_id.setdefault(str(attempt.get("raw_fetch_attempt_id") or ""), attempt)
    fetch_attempts = sorted(attempts_by_id.values(), key=lambda item: str(item.get("raw_fetch_attempt_id") or ""))
    source_snapshots = [_snapshot_from_document(row, generated_at=generated_at) for row in source_documents]
    summary = build_raw_source_provenance_summary(
        source_documents=source_documents,
        fetch_attempts=fetch_attempts,
        source_snapshots=source_snapshots,
        runtime_lineage_rows=runtime_lineage_rows,
        runtime_manifest_paths=runtime_manifests,
        generated_at=generated_at,
    )
    summary["repair_mode"] = "existing_source_documents_runtime_lineage_rebuild"
    summary["companyfacts_external_key_document_count"] = sum(
        1
        for row in source_documents
        if any(str(key).lower().startswith("sec_companyfacts_by_ticker:") for key in (row.get("external_document_keys") or []))
    )
    return {
        "source_documents": source_documents,
        "fetch_attempts": fetch_attempts,
        "source_snapshots": source_snapshots,
        "runtime_lineage_rows": runtime_lineage_rows,
        "summary": summary,
    }


def main() -> int:
    args = parse_args()
    result = repair_raw_source_provenance_lineage_from_existing_documents(
        args.repo_root,
        input_documents=args.input_documents,
        input_attempts=args.input_attempts,
    )
    output_paths = {
        "raw_source_documents": str(args.output_documents),
        "raw_fetch_attempts": str(args.output_attempts),
        "source_snapshots": str(args.output_snapshots),
        "runtime_row_source_lineage": str(args.output_lineage),
        "summary": str(args.output_summary),
        "report": str(args.output_report),
    }
    write_jsonl(args.output_documents, result["source_documents"])
    write_jsonl(args.output_attempts, result["fetch_attempts"])
    write_jsonl(args.output_snapshots, result["source_snapshots"])
    write_jsonl(args.output_lineage, result["runtime_lineage_rows"])
    summary = {**result["summary"], "outputs": output_paths}
    write_json(args.output_summary, summary)
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(
        render_raw_source_provenance_report(summary, output_paths=output_paths),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
