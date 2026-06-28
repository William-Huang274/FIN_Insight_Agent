from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


RAW_SOURCE_DOCUMENT_SCHEMA_VERSION = "finsight_raw_source_document_v0_1"
RAW_FETCH_ATTEMPT_SCHEMA_VERSION = "finsight_raw_fetch_attempt_v0_1"
SOURCE_SNAPSHOT_SCHEMA_VERSION = "finsight_source_snapshot_v0_1"
RUNTIME_ROW_SOURCE_LINEAGE_SCHEMA_VERSION = "finsight_runtime_row_source_lineage_v0_1"
RAW_SOURCE_PROVENANCE_SUMMARY_SCHEMA_VERSION = "finsight_raw_source_provenance_summary_v0_1"


RAW_SOURCE_ROOTS: tuple[str, ...] = (
    "data/raw_private/sec",
    "data/raw_private/sec_filings",
    "data/raw_private/sec_8k_earnings",
    "data/raw_private/sec_tier1_sp500_annual",
    "data/raw_private/sec_tier2_supply_chain_annual",
    "data/raw_private/structured_financial_facts",
    "data/raw_private/global_public_disclosures",
    "data/raw_private/company_ir",
)

RUNTIME_ROWSET_PATTERNS: tuple[str, ...] = (
    "*_runtime_rows_v0_1.jsonl",
    "*_context_rows_v0_1.jsonl",
    "*_metric_slot_rows_v0_1.jsonl",
    "*_data_mart_rows_v0_1.jsonl",
)

RUNTIME_ROWSET_EXCLUDE_TOKENS: tuple[str, ...] = (
    "_tmp_",
    "_attempts_",
    "_rejections_",
    "_closeout_",
    "_queue_",
    "_docket_",
)

SOURCE_ROUTE_ATTEMPT_MANIFESTS: tuple[str, ...] = (
    "data/manifests/source_route_attempt_ledger_v0_1.jsonl",
    "data/manifests/r15_manual_public_source_attempts_v0_1.jsonl",
    "data/manifests/r15_product_kpi_exhaustion_attempts_v0_1.jsonl",
    "data/manifests/r16_product_kpi_deep_repair_attempts_v0_1.jsonl",
    "data/manifests/official_customer_deployment_surface_attempts_v0_1.jsonl",
    "data/manifests/family_channel_distributor_attempts_v0_1.jsonl",
    "data/manifests/broad_hiring_capacity_attempts_v0_1.jsonl",
    "data/manifests/broad_public_contract_award_attempts_v0_1.jsonl",
    "data/manifests/broad_app_store_platform_attempts_v0_1.jsonl",
    "data/manifests/broad_channel_offer_attempts_v0_1.jsonl",
    "data/manifests/developer_ecosystem_attempts_v0_1.jsonl",
    "data/manifests/local_public_tender_attempts_v0_1.jsonl",
)

RAW_DOCUMENT_EXTENSIONS: set[str] = {
    ".htm",
    ".html",
    ".json",
    ".xml",
    ".pdf",
    ".zip",
    ".csv",
    ".txt",
}

SECRET_QUERY_KEYS: set[str] = {
    "api_key",
    "apikey",
    "key",
    "token",
    "access_token",
    "crtfc_key",
    "client_secret",
    "password",
}


def build_raw_source_provenance_store(
    repo_root: str | Path,
    *,
    generated_at: str | None = None,
    max_hash_bytes: int = 64 * 1024 * 1024,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    generated_at = generated_at or _utc_now()
    source_documents: dict[str, dict[str, Any]] = {}
    fetch_attempts: dict[str, dict[str, Any]] = {}

    for row in _build_documents_from_raw_metadata(root, generated_at=generated_at, max_hash_bytes=max_hash_bytes):
        source_documents.setdefault(row["raw_source_document_id"], row)
        attempt = _fetch_attempt_from_document(row, generated_at=generated_at)
        fetch_attempts.setdefault(attempt["raw_fetch_attempt_id"], attempt)

    for row in _build_documents_for_unpaired_raw_files(
        root,
        existing_raw_paths={str(row.get("raw_path") or "").lower() for row in source_documents.values() if row.get("raw_path")},
        generated_at=generated_at,
        max_hash_bytes=max_hash_bytes,
    ):
        source_documents.setdefault(row["raw_source_document_id"], row)
        attempt = _fetch_attempt_from_document(row, generated_at=generated_at)
        fetch_attempts.setdefault(attempt["raw_fetch_attempt_id"], attempt)

    runtime_manifests = discover_runtime_rowset_paths(root)
    runtime_lineage_rows: list[dict[str, Any]] = []
    source_maps = _source_document_maps(source_documents.values())

    for manifest_path in runtime_manifests:
        rows = _read_jsonl(manifest_path)
        for ordinal, runtime_row in enumerate(rows, start=1):
            if not _is_runtime_candidate(runtime_row):
                continue
            source_url = _sanitize_url(_row_source_url(runtime_row))
            source_document_ref = _first_text(runtime_row, "source_document_id", "raw_path")
            raw_path = _runtime_row_raw_path(root, source_document_ref)
            existing_match = _match_source_document(
                root,
                runtime_row,
                source_url=source_url,
                raw_path=raw_path,
                source_maps=source_maps,
            )
            if str(existing_match.get("lineage_status") or "").startswith("unresolved"):
                document_row = _runtime_declared_source_document(
                    root,
                    manifest_path,
                    runtime_row,
                    generated_at=generated_at,
                    max_hash_bytes=max_hash_bytes,
                )
                if document_row and document_row["raw_source_document_id"] not in source_documents:
                    source_documents[document_row["raw_source_document_id"]] = document_row
                    _add_source_document_to_maps(source_maps, document_row)
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

    for attempt in _build_fetch_attempts_from_attempt_ledgers(root, generated_at=generated_at):
        fetch_attempts.setdefault(attempt["raw_fetch_attempt_id"], attempt)

    source_snapshots = [
        _snapshot_from_document(row, generated_at=generated_at)
        for row in sorted(source_documents.values(), key=lambda item: item["raw_source_document_id"])
    ]
    summary = build_raw_source_provenance_summary(
        source_documents=list(source_documents.values()),
        fetch_attempts=list(fetch_attempts.values()),
        source_snapshots=source_snapshots,
        runtime_lineage_rows=runtime_lineage_rows,
        runtime_manifest_paths=runtime_manifests,
        generated_at=generated_at,
    )
    return {
        "source_documents": sorted(source_documents.values(), key=lambda item: item["raw_source_document_id"]),
        "fetch_attempts": sorted(fetch_attempts.values(), key=lambda item: item["raw_fetch_attempt_id"]),
        "source_snapshots": source_snapshots,
        "runtime_lineage_rows": runtime_lineage_rows,
        "summary": summary,
    }


def discover_runtime_rowset_paths(repo_root: str | Path) -> list[Path]:
    root = Path(repo_root).resolve()
    manifest_root = root / "data" / "manifests"
    paths: set[Path] = set()
    for pattern in RUNTIME_ROWSET_PATTERNS:
        for path in manifest_root.glob(pattern):
            name = path.name
            if any(token in name for token in RUNTIME_ROWSET_EXCLUDE_TOKENS):
                continue
            if path.is_file():
                paths.add(path)
    return sorted(paths)


def build_raw_source_provenance_summary(
    *,
    source_documents: Sequence[Mapping[str, Any]],
    fetch_attempts: Sequence[Mapping[str, Any]],
    source_snapshots: Sequence[Mapping[str, Any]],
    runtime_lineage_rows: Sequence[Mapping[str, Any]],
    runtime_manifest_paths: Sequence[Path],
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or _utc_now()
    lineage_status_counts = Counter(str(row.get("lineage_status") or "") for row in runtime_lineage_rows)
    source_snapshot_counts = Counter(str(row.get("snapshot_storage_status") or "") for row in source_snapshots)
    exact_rows = [
        row
        for row in runtime_lineage_rows
        if row.get("exact_value_authority") is True or row.get("can_support_company_exact_fact") is True
    ]
    accepted_lineage_statuses = {
        "matched_raw_document",
        "matched_derived_structured_source_document",
        "runtime_declared_source_document",
    }
    exact_unresolved = [
        row
        for row in exact_rows
        if str(row.get("lineage_status") or "") not in accepted_lineage_statuses
    ]
    url_only_context_rows = [
        row
        for row in runtime_lineage_rows
        if str(row.get("snapshot_storage_status") or "") == "url_only_no_local_snapshot"
    ]
    unresolved_rows = [
        row
        for row in runtime_lineage_rows
        if str(row.get("lineage_status") or "").startswith("unresolved")
    ]
    status = "pass" if not exact_unresolved and not unresolved_rows else "action_required"
    return {
        "schema_version": RAW_SOURCE_PROVENANCE_SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": status,
        "raw_source_document_count": len(source_documents),
        "raw_fetch_attempt_count": len(fetch_attempts),
        "source_snapshot_count": len(source_snapshots),
        "runtime_manifest_count": len(runtime_manifest_paths),
        "runtime_lineage_count": len(runtime_lineage_rows),
        "runtime_lineage_status_counts": dict(lineage_status_counts),
        "source_snapshot_storage_counts": dict(source_snapshot_counts),
        "exact_authority_lineage_count": len(exact_rows),
        "exact_authority_unresolved_count": len(exact_unresolved),
        "url_only_context_lineage_count": len(url_only_context_rows),
        "unresolved_lineage_count": len(unresolved_rows),
        "fetch_attempt_status_class_counts": dict(Counter(str(row.get("attempt_status_class") or "") for row in fetch_attempts)),
        "source_document_kind_counts": dict(Counter(str(row.get("source_document_kind") or "") for row in source_documents)),
        "source_layer_counts": dict(Counter(str(row.get("source_layer") or "") for row in source_documents)),
        "runtime_manifest_samples": [_rel(path, Path.cwd()) for path in list(runtime_manifest_paths)[:30]],
        "unresolved_lineage_samples": [
            _compact_lineage_sample(row)
            for row in unresolved_rows[:50]
        ],
        "exact_unresolved_samples": [
            _compact_lineage_sample(row)
            for row in exact_unresolved[:50]
        ],
        "policy": (
            "RD1 is a Bronze provenance ledger. It creates source-document, fetch-attempt, source-snapshot, "
            "and runtime-row lineage rows. URL-only rows are traceable but not replayable until a local/API snapshot is cached; "
            "they must not be treated as stronger evidence than their authority gate allows."
        ),
    }


def render_raw_source_provenance_report(summary: Mapping[str, Any], *, output_paths: Mapping[str, str]) -> str:
    lines = [
        "# RD1 Bronze Raw Source Provenance Store",
        "",
        f"- Generated at: `{summary.get('generated_at', '')}`",
        f"- Status: `{summary.get('status', '')}`",
        f"- Raw source documents: `{summary.get('raw_source_document_count', 0)}`",
        f"- Fetch attempts: `{summary.get('raw_fetch_attempt_count', 0)}`",
        f"- Source snapshots: `{summary.get('source_snapshot_count', 0)}`",
        f"- Runtime row lineage rows: `{summary.get('runtime_lineage_count', 0)}`",
        f"- Exact-authority unresolved lineage: `{summary.get('exact_authority_unresolved_count', 0)}`",
        f"- URL-only context lineage: `{summary.get('url_only_context_lineage_count', 0)}`",
        "",
        "## Outputs",
        "",
    ]
    for key, path in output_paths.items():
        lines.append(f"- `{key}`: `{path}`")
    lines.extend(
        [
            "",
            "## Runtime Lineage Status",
            "",
            _markdown_counter_table(summary.get("runtime_lineage_status_counts") or {}, "Status", "Rows"),
            "",
            "## Snapshot Storage",
            "",
            _markdown_counter_table(summary.get("source_snapshot_storage_counts") or {}, "Storage status", "Rows"),
            "",
            "## Fetch Attempt Status",
            "",
            _markdown_counter_table(summary.get("fetch_attempt_status_class_counts") or {}, "Status class", "Rows"),
            "",
            "## Boundary",
            "",
            "- RD1 只建立 provenance，不新增事实提权。",
            "- `local_raw_snapshot_available` / `api_response_cached` 行可回放；`url_only_no_local_snapshot` 行只能说明 runtime row 声明了来源 URL，后续需要缓存快照或在 run audit 中绑定 fetch attempt。",
            "- exact-authority 行如果出现 unresolved，RD2/RD3 不允许把它们升级为主事实层。",
            "",
        ]
    )
    return "\n".join(lines)


def write_jsonl(path: str | Path, rows: Sequence[Mapping[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("".join(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _build_documents_from_raw_metadata(root: Path, *, generated_at: str, max_hash_bytes: int) -> Iterable[dict[str, Any]]:
    for raw_root in RAW_SOURCE_ROOTS:
        base = root / raw_root
        if not base.exists():
            continue
        for metadata_path in sorted(base.rglob("*.json")):
            if not _is_metadata_file(metadata_path):
                continue
            metadata = _read_json(metadata_path)
            if not metadata:
                continue
            document_path = _metadata_document_path(root, metadata_path, metadata)
            yield _source_document_row(
                root,
                source_document_kind="raw_metadata_document",
                source_url=_metadata_source_url(metadata),
                raw_path=document_path,
                metadata_path=metadata_path,
                metadata=metadata,
                generated_at=generated_at,
                max_hash_bytes=max_hash_bytes,
            )


def _build_documents_for_unpaired_raw_files(
    root: Path,
    *,
    existing_raw_paths: set[str],
    generated_at: str,
    max_hash_bytes: int,
) -> Iterable[dict[str, Any]]:
    for raw_root in RAW_SOURCE_ROOTS:
        base = root / raw_root
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in RAW_DOCUMENT_EXTENSIONS:
                continue
            if _is_metadata_file(path):
                continue
            resolved = str(path.resolve()).lower()
            rel = _rel(path, root).lower()
            if resolved in existing_raw_paths or rel in existing_raw_paths:
                continue
            yield _source_document_row(
                root,
                source_document_kind="raw_file_without_metadata",
                source_url="",
                raw_path=path,
                metadata_path=None,
                metadata={},
                generated_at=generated_at,
                max_hash_bytes=max_hash_bytes,
            )


def _build_fetch_attempts_from_attempt_ledgers(root: Path, *, generated_at: str) -> Iterable[dict[str, Any]]:
    for relative_path in SOURCE_ROUTE_ATTEMPT_MANIFESTS:
        path = root / relative_path
        if not path.exists():
            continue
        for ordinal, row in enumerate(_read_jsonl(path), start=1):
            attempts = row.get("sample_attempts") if isinstance(row.get("sample_attempts"), list) else [row]
            for attempt_ordinal, attempt in enumerate(attempts, start=1):
                if not isinstance(attempt, Mapping):
                    continue
                source_url = _sanitize_url(_first_text(attempt, "source_url", "api_url", "url"))
                status = _first_text(attempt, "status", "download_status", "attempt_status") or _first_text(row, "current_status", "gate_status")
                reason = _first_text(attempt, "reason", "error", "message") or _first_text(row, "gate_reason", "source_closeout_reason")
                ticker = _first_text(attempt, "ticker") or _first_text(row, "ticker")
                attempt_id = _stable_id("rd1_fetch_attempt", _rel(path, root), ordinal, attempt_ordinal, ticker, source_url, status, reason)
                source_document_id = _stable_id("rd1_attempt_source", ticker, source_url, _first_text(row, "source_role"), _first_text(row, "source_id"))
                yield {
                    "schema_version": RAW_FETCH_ATTEMPT_SCHEMA_VERSION,
                    "generated_at": generated_at,
                    "raw_fetch_attempt_id": attempt_id,
                    "raw_source_document_id": source_document_id,
                    "attempt_source": "source_route_attempt_ledger",
                    "attempt_manifest_path": _rel(path, root),
                    "ticker": ticker,
                    "source_url": source_url,
                    "api_url": _sanitize_url(_first_text(attempt, "api_url")),
                    "provider": _first_text(attempt, "provider"),
                    "source_id": _first_text(attempt, "source_id") or _first_text(row, "source_id"),
                    "source_role": _first_text(row, "source_role"),
                    "source_layer": _first_text(row, "source_layer"),
                    "download_status": status,
                    "attempt_status_class": _status_class(status, reason=reason),
                    "reason": reason,
                    "raw_path": _first_text(attempt, "raw_path"),
                    "http_status": _first_text(attempt, "http_status", "status_code"),
                    "claim_boundary": _first_text(row, "claim_boundary"),
                }


def _source_document_row(
    root: Path,
    *,
    source_document_kind: str,
    source_url: str,
    raw_path: Path | None,
    metadata_path: Path | None,
    metadata: Mapping[str, Any],
    generated_at: str,
    max_hash_bytes: int,
) -> dict[str, Any]:
    source_url = _sanitize_url(source_url)
    raw_path = raw_path.resolve() if raw_path else None
    metadata_path = metadata_path.resolve() if metadata_path else None
    stat = raw_path.stat() if raw_path and raw_path.exists() else None
    sha256 = _first_text(metadata, "sha256", "checksum")
    if not sha256 and raw_path and raw_path.exists() and stat and stat.st_size <= max_hash_bytes:
        sha256 = _sha256_file(raw_path)
    byte_count = _int(_first_text(metadata, "byte_count", "downloaded_byte_count")) or (stat.st_size if stat else 0)
    raw_source_document_id = _stable_id(
        "rd1_source_document",
        _first_text(metadata, "plan_id", "task_id", "accession_number", "rcept_no", "document_id"),
        _first_text(metadata, "ticker", "cik", "company"),
        source_url,
        _rel(raw_path, root) if raw_path else "",
        sha256,
    )
    source_layer = _infer_source_layer(metadata=metadata, raw_path=raw_path, source_url=source_url)
    download_status = _first_text(metadata, "download_status", "cache_status", "cleaned_text_status") or (
        "local_file_present" if raw_path and raw_path.exists() else "source_url_declared"
    )
    parser_status = _first_text(metadata, "parser_status", "structured_fact_status", "cleaned_text_status")
    source_family = _first_text(metadata, "source_family", "fact_source", "disclosure_profile")
    source_id = _first_text(metadata, "source_id", "fact_source", "underlying_source_id", "download_strategy")
    ticker = _metadata_ticker(metadata, raw_path)
    document_type = _first_text(metadata, "form_type", "report_type", "document_description", "fact_source") or _document_type_from_path(raw_path)
    return {
        "schema_version": RAW_SOURCE_DOCUMENT_SCHEMA_VERSION,
        "generated_at": generated_at,
        "raw_source_document_id": raw_source_document_id,
        "source_document_kind": source_document_kind,
        "ticker": ticker,
        "company_name": _first_text(metadata, "company_name", "company"),
        "issuer_id": _first_text(metadata, "cik", "cik10", "issuer_id"),
        "source_layer": source_layer,
        "source_role": _first_text(metadata, "source_tier", "source_role") or _role_from_path(raw_path),
        "source_family": source_family,
        "source_id": source_id,
        "source_url": source_url,
        "raw_path": _rel(raw_path, root) if raw_path else "",
        "absolute_raw_path": str(raw_path) if raw_path else "",
        "metadata_path": _rel(metadata_path, root) if metadata_path else "",
        "metadata_schema_version": _first_text(metadata, "schema_version"),
        "content_type": _first_text(metadata, "content_type") or _content_type_from_path(raw_path),
        "byte_count": byte_count,
        "sha256": sha256,
        "file_exists": bool(raw_path and raw_path.exists()),
        "fetched_at": _first_text(metadata, "downloaded_at", "downloaded_at_utc", "updated_at_utc"),
        "as_of_date": _first_text(metadata, "filing_date", "report_date", "released_date"),
        "document_type": document_type,
        "form_type": _first_text(metadata, "form_type"),
        "fiscal_year": _first_text(metadata, "fiscal_year", "requested_fiscal_year"),
        "period": _first_text(metadata, "fiscal_period", "period_type", "report_type"),
        "accession_number": _first_text(metadata, "accession_number"),
        "external_document_keys": _external_document_keys(
            metadata,
            source_url=source_url,
            raw_path=raw_path,
            root=root,
            ticker=ticker,
            source_family=source_family,
            source_id=source_id,
            document_type=document_type,
        ),
        "download_status": download_status,
        "fetch_status_class": _status_class(download_status, reason=parser_status),
        "parser_status": parser_status,
        "provenance_status": _provenance_status(raw_path=raw_path, source_url=source_url, metadata=metadata),
    }


def _runtime_declared_source_document(
    root: Path,
    manifest_path: Path,
    row: Mapping[str, Any],
    *,
    generated_at: str,
    max_hash_bytes: int,
) -> dict[str, Any] | None:
    source_url = _sanitize_url(_row_source_url(row))
    source_document_ref = _first_text(row, "source_document_id", "raw_path")
    raw_path = _runtime_row_raw_path(root, source_document_ref)
    if not source_url and not raw_path:
        return None
    metadata = {
        "ticker": _first_text(row, "ticker"),
        "company_name": _first_text(row, "company_name", "company"),
        "source_layer": _first_text(row, "source_layer", "source_layer_id", "layer_id"),
        "source_role": _first_text(row, "source_role"),
        "source_family": _first_text(row, "source_family", "runtime_source_family"),
        "source_id": _first_text(row, "source_id", "underlying_source_id"),
        "form_type": _first_text(row, "filing_type", "form_type"),
        "fiscal_year": _first_text(row, "fiscal_year"),
        "period": _first_text(row, "period", "fiscal_period"),
        "document_id": source_document_ref,
        "source_url": source_url,
        "parser_status": _first_text(row, "parser_status", "structured_fact_status"),
    }
    doc = _source_document_row(
        root,
        source_document_kind="runtime_declared_source",
        source_url=source_url,
        raw_path=raw_path,
        metadata_path=manifest_path,
        metadata=metadata,
        generated_at=generated_at,
        max_hash_bytes=max_hash_bytes,
    )
    doc["declared_by_runtime_manifest"] = _rel(manifest_path, root)
    doc["declared_runtime_row_ref"] = _runtime_row_id(row, manifest_path, 0)
    return doc


def _fetch_attempt_from_document(document: Mapping[str, Any], *, generated_at: str) -> dict[str, Any]:
    status = str(document.get("download_status") or document.get("provenance_status") or "")
    reason = str(document.get("parser_status") or "")
    return {
        "schema_version": RAW_FETCH_ATTEMPT_SCHEMA_VERSION,
        "generated_at": generated_at,
        "raw_fetch_attempt_id": _stable_id("rd1_fetch_attempt", document.get("raw_source_document_id"), document.get("source_url"), status),
        "raw_source_document_id": str(document.get("raw_source_document_id") or ""),
        "attempt_source": "raw_source_document_metadata",
        "attempt_manifest_path": str(document.get("metadata_path") or ""),
        "ticker": str(document.get("ticker") or ""),
        "source_url": str(document.get("source_url") or ""),
        "api_url": str(document.get("source_url") or ""),
        "provider": str(document.get("source_id") or ""),
        "source_id": str(document.get("source_id") or ""),
        "source_role": str(document.get("source_role") or ""),
        "source_layer": str(document.get("source_layer") or ""),
        "download_status": status,
        "attempt_status_class": _status_class(status, reason=reason),
        "reason": reason,
        "raw_path": str(document.get("raw_path") or ""),
        "http_status": "",
        "claim_boundary": "provenance only; no evidence promotion",
    }


def _snapshot_from_document(document: Mapping[str, Any], *, generated_at: str) -> dict[str, Any]:
    raw_path = str(document.get("raw_path") or "")
    source_url = str(document.get("source_url") or "")
    file_exists = bool(document.get("file_exists"))
    if file_exists and raw_path:
        storage_status = "api_response_cached" if _looks_like_api_url(source_url) or str(document.get("content_type") or "").endswith("json") else "local_raw_snapshot_available"
        snapshot_uri = raw_path
    elif source_url:
        storage_status = "url_only_no_local_snapshot"
        snapshot_uri = source_url
    else:
        storage_status = "missing_snapshot"
        snapshot_uri = ""
    return {
        "schema_version": SOURCE_SNAPSHOT_SCHEMA_VERSION,
        "generated_at": generated_at,
        "source_snapshot_id": _stable_id("rd1_source_snapshot", document.get("raw_source_document_id"), snapshot_uri, document.get("sha256")),
        "raw_source_document_id": str(document.get("raw_source_document_id") or ""),
        "snapshot_uri": snapshot_uri,
        "snapshot_storage_status": storage_status,
        "ticker": str(document.get("ticker") or ""),
        "source_url": source_url,
        "raw_path": raw_path,
        "byte_count": _int(document.get("byte_count")),
        "sha256": str(document.get("sha256") or ""),
        "content_type": str(document.get("content_type") or ""),
        "as_of_date": str(document.get("as_of_date") or ""),
        "fetched_at": str(document.get("fetched_at") or ""),
        "replayability": "replayable" if storage_status in {"api_response_cached", "local_raw_snapshot_available"} else "not_replayable_until_cached",
    }


def _runtime_lineage_row(
    root: Path,
    manifest_path: Path,
    row: Mapping[str, Any],
    *,
    ordinal: int,
    source_maps: Mapping[str, Mapping[str, Mapping[str, Any]]],
    generated_at: str,
) -> dict[str, Any]:
    runtime_row_id = _runtime_row_id(row, manifest_path, ordinal)
    source_url = _sanitize_url(_row_source_url(row))
    source_document_ref = _first_text(row, "source_document_id", "raw_path")
    raw_path = _runtime_row_raw_path(root, source_document_ref)
    match = _match_source_document(root, row, source_url=source_url, raw_path=raw_path, source_maps=source_maps)
    document = match.get("document") or {}
    snapshot_status = "missing_snapshot"
    if document:
        snapshot_status = _snapshot_from_document(document, generated_at=generated_at)["snapshot_storage_status"]
    return {
        "schema_version": RUNTIME_ROW_SOURCE_LINEAGE_SCHEMA_VERSION,
        "generated_at": generated_at,
        "lineage_id": _stable_id("rd1_runtime_lineage", _rel(manifest_path, root), runtime_row_id, source_url, source_document_ref),
        "runtime_manifest_path": _rel(manifest_path, root),
        "runtime_row_id": runtime_row_id,
        "ticker": _first_text(row, "ticker"),
        "source_layer": _first_text(row, "source_layer", "source_layer_id", "layer_id"),
        "source_id": _first_text(row, "source_id", "underlying_source_id"),
        "source_family": _first_text(row, "source_family", "runtime_source_family"),
        "source_url": source_url,
        "runtime_source_document_ref": source_document_ref,
        "raw_source_document_id": str(document.get("raw_source_document_id") or ""),
        "matched_raw_path": str(document.get("raw_path") or ""),
        "matched_source_url": str(document.get("source_url") or ""),
        "lineage_status": match.get("lineage_status") or "unresolved_missing_source_reference",
        "lineage_match_key": match.get("lineage_match_key") or "",
        "snapshot_storage_status": snapshot_status,
        "exact_value_authority": bool(row.get("exact_value_authority")),
        "can_support_company_exact_fact": bool(row.get("can_support_company_exact_fact")),
        "runtime_ready_context": bool(row.get("runtime_ready_context")),
        "parser_status": _first_text(row, "parser_status", "structured_fact_status"),
        "authority_boundary": _first_text(row, "authority_boundary", "claim_boundary"),
    }


def _match_source_document(
    root: Path,
    row: Mapping[str, Any],
    *,
    source_url: str,
    raw_path: Path | None,
    source_maps: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> dict[str, Any]:
    by_raw_path = source_maps["by_raw_path"]
    by_source_url = source_maps["by_source_url"]
    by_external_key = source_maps["by_external_key"]
    if raw_path:
        for key in (_rel(raw_path, root).lower(), str(raw_path.resolve()).lower()):
            if key in by_raw_path:
                return {"lineage_status": "matched_raw_document", "lineage_match_key": f"raw_path:{key}", "document": by_raw_path[key]}
    source_document_ref = _first_text(row, "source_document_id", "source_document_ref")
    for key in _candidate_external_keys(row, source_document_ref):
        normalized = key.lower()
        if normalized in by_external_key:
            document = by_external_key[normalized]
            status = "runtime_declared_source_document" if document.get("source_document_kind") == "runtime_declared_source" else "matched_raw_document"
            return {"lineage_status": status, "lineage_match_key": f"external_key:{normalized}", "document": document}
    if source_url:
        normalized_url = _normalize_url_for_key(source_url)
        if normalized_url in by_source_url:
            document = by_source_url[normalized_url]
            status = "runtime_declared_source_document" if document.get("source_document_kind") == "runtime_declared_source" else "matched_raw_document"
            return {"lineage_status": status, "lineage_match_key": f"source_url:{normalized_url}", "document": document}
    source_id = _first_text(row, "source_id", "underlying_source_id").lower()
    ticker = _first_text(row, "ticker").upper()
    if ticker and source_id in {"sec_financial_statement_data_sets", "sec_companyfacts_api"}:
        key = f"sec_companyfacts_by_ticker:{ticker}".lower()
        if key in by_external_key:
            return {
                "lineage_status": "matched_derived_structured_source_document",
                "lineage_match_key": key,
                "document": by_external_key[key],
            }
    return {"lineage_status": "unresolved_missing_source_reference", "lineage_match_key": "", "document": {}}


def _source_document_maps(source_documents: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Mapping[str, Any]]]:
    by_raw_path: dict[str, Mapping[str, Any]] = {}
    by_source_url: dict[str, Mapping[str, Any]] = {}
    by_external_key: dict[str, Mapping[str, Any]] = {}
    for row in source_documents:
        _add_source_document_to_maps(
            {"by_raw_path": by_raw_path, "by_source_url": by_source_url, "by_external_key": by_external_key},
            row,
        )
    return {"by_raw_path": by_raw_path, "by_source_url": by_source_url, "by_external_key": by_external_key}


def _add_source_document_to_maps(
    source_maps: Mapping[str, dict[str, Mapping[str, Any]]],
    row: Mapping[str, Any],
) -> None:
    by_raw_path = source_maps["by_raw_path"]
    by_source_url = source_maps["by_source_url"]
    by_external_key = source_maps["by_external_key"]
    raw_path = str(row.get("raw_path") or "").strip()
    absolute_raw_path = str(row.get("absolute_raw_path") or "").strip()
    if raw_path and row.get("file_exists"):
        by_raw_path[raw_path.lower()] = row
    if absolute_raw_path and row.get("file_exists"):
        by_raw_path[absolute_raw_path.lower()] = row
    source_url = str(row.get("source_url") or "").strip()
    if source_url:
        by_source_url[_normalize_url_for_key(source_url)] = row
    for key in row.get("external_document_keys") or []:
        if str(key).strip():
            by_external_key[str(key).strip().lower()] = row
    ticker = str(row.get("ticker") or "").strip().upper()
    source_family = str(row.get("source_family") or "").strip().lower()
    source_id = str(row.get("source_id") or "").strip().lower()
    if ticker and ("companyfacts" in source_family or "companyfacts" in source_id):
        by_external_key[f"sec_companyfacts_by_ticker:{ticker}".lower()] = row


def _metadata_document_path(root: Path, metadata_path: Path, metadata: Mapping[str, Any]) -> Path | None:
    for key in ("document_path", "local_html_path", "local_path", "raw_path", "file_path", "output_path"):
        value = _first_text(metadata, key)
        if value:
            return _resolve_path(root, value)
    if metadata_path.name.endswith(".metadata.json"):
        candidate_stem = metadata_path.name[: -len(".metadata.json")]
        for suffix in ("", ".html", ".htm", ".json", ".xml", ".pdf", ".zip", ".csv", ".txt"):
            candidate = metadata_path.with_name(candidate_stem + suffix)
            if candidate.exists() and candidate != metadata_path:
                return candidate
    return None


def _runtime_row_raw_path(root: Path, value: str) -> Path | None:
    value = str(value or "").strip()
    if not value:
        return None
    if value.startswith("data/") or value.startswith("D:") or value.startswith("Z:") or value.startswith("\\"):
        path = _resolve_path(root, value)
        return path if path and path.exists() else path
    return None


def _metadata_source_url(metadata: Mapping[str, Any]) -> str:
    selected = metadata.get("selected_candidate")
    selected_url = ""
    if isinstance(selected, Mapping):
        selected_url = _first_text(selected, "url", "source_url")
    return _first_text(metadata, "source_url", "filing_url", "api_url", "url") or selected_url


def _row_source_url(row: Mapping[str, Any]) -> str:
    citation = row.get("citation") if isinstance(row.get("citation"), Mapping) else {}
    return (
        _first_text(row, "source_url", "snapshot_url", "url", "api_url", "raw_url", "filing_url")
        or _first_text(citation, "source_url", "url")
    )


def _runtime_row_id(row: Mapping[str, Any], manifest_path: Path, ordinal: int) -> str:
    for key in ("evidence_id", "evidence_ref", "snapshot_id", "node_id", "edge_id", "ledger_id", "row_id", "id"):
        value = _first_text(row, key)
        if value:
            return value
    return _stable_id("rd1_runtime_row", manifest_path.name, ordinal, json.dumps(_compact_payload(row, max_items=12), sort_keys=True, ensure_ascii=False))


def _is_metadata_file(path: Path) -> bool:
    name = path.name.lower()
    return name.endswith(".metadata.json") or name == "locator_metadata.json" or name.endswith("_metadata.json")


def _is_runtime_candidate(row: Mapping[str, Any]) -> bool:
    if row.get("runtime_ready_context") is True:
        return True
    if row.get("exact_value_authority") is True or row.get("can_support_company_exact_fact") is True:
        return True
    if _row_source_url(row):
        return True
    if _first_text(row, "source_document_id", "raw_path"):
        return True
    return False


def _external_document_keys(
    metadata: Mapping[str, Any],
    *,
    source_url: str,
    raw_path: Path | None,
    root: Path,
    ticker: str = "",
    source_family: str = "",
    source_id: str = "",
    document_type: str = "",
) -> list[str]:
    keys: list[str] = []
    for key in ("accession_number", "plan_id", "task_id", "rcept_no", "document_id", "primary_document"):
        value = _first_text(metadata, key)
        if value:
            keys.append(value)
    if source_url:
        keys.append(source_url)
    if raw_path:
        keys.append(_rel(raw_path, root))
        keys.append(str(raw_path.resolve()))
    ticker = (ticker or _first_text(metadata, "ticker")).strip().upper()
    companyfacts_scope = " ".join(
        [
            source_family,
            source_id,
            document_type,
            _first_text(metadata, "fact_source"),
            str(raw_path or ""),
            source_url,
        ]
    ).lower()
    if ticker and "companyfacts" in companyfacts_scope:
        keys.append(f"sec_companyfacts_by_ticker:{ticker}")
    return _unique_strings(keys)


def _candidate_external_keys(row: Mapping[str, Any], source_document_ref: str) -> list[str]:
    values = [source_document_ref]
    for key in ("accession_number", "source_document_id", "snapshot_id"):
        value = _first_text(row, key)
        if value:
            values.append(value)
    source_url = _row_source_url(row)
    if source_url:
        values.append(_sanitize_url(source_url))
    return _unique_strings(values)


def _metadata_ticker(metadata: Mapping[str, Any], raw_path: Path | None) -> str:
    value = _first_text(metadata, "ticker")
    if value:
        return _ticker_from_path_token(value)
    if raw_path:
        parts = raw_path.parts
        for token in reversed(parts):
            if _looks_like_ticker_token(token):
                return _ticker_from_path_token(token)
    return ""


def _infer_source_layer(*, metadata: Mapping[str, Any], raw_path: Path | None, source_url: str) -> str:
    explicit = _first_text(metadata, "source_layer", "source_layer_id", "layer_id")
    if explicit:
        return explicit
    source_tier = _first_text(metadata, "source_tier", "source_role", "fact_source", "disclosure_profile").lower()
    path_text = str(raw_path or "").lower()
    url_text = source_url.lower()
    if "sec" in source_tier or "companyfacts" in source_tier or "primary" in source_tier or "annual_report" in source_tier:
        return "L1"
    if "global_public_disclosures" in path_text or "company_ir" in path_text or "sec" in path_text or "data.sec.gov" in url_text or "sec.gov" in url_text:
        return "L1"
    if "product" in url_text or "ir." in url_text:
        return "L2"
    return "unknown"


def _role_from_path(path: Path | None) -> str:
    text = str(path or "").replace("\\", "/").lower()
    if "structured_financial_facts" in text:
        return "primary_company_disclosure"
    if "/sec" in text:
        return "primary_company_disclosure"
    if "global_public_disclosures" in text:
        return "primary_company_disclosure"
    if "company_ir" in text:
        return "primary_company_disclosure"
    return ""


def _document_type_from_path(path: Path | None) -> str:
    if not path:
        return ""
    name = path.name.lower()
    if "10-k" in name:
        return "10-K"
    if "10-q" in name:
        return "10-Q"
    if "companyfacts" in name:
        return "sec_companyfacts"
    if "submissions" in name:
        return "sec_submissions"
    if name.endswith(".pdf"):
        return "pdf"
    return path.suffix.lower().lstrip(".")


def _content_type_from_path(path: Path | None) -> str:
    if not path:
        return ""
    suffix = path.suffix.lower()
    return {
        ".html": "text/html",
        ".htm": "text/html",
        ".json": "application/json",
        ".xml": "application/xml",
        ".pdf": "application/pdf",
        ".zip": "application/zip",
        ".csv": "text/csv",
        ".txt": "text/plain",
    }.get(suffix, "")


def _provenance_status(*, raw_path: Path | None, source_url: str, metadata: Mapping[str, Any]) -> str:
    if raw_path and raw_path.exists():
        return "local_raw_snapshot_available"
    if source_url:
        return "url_declared_no_local_snapshot"
    if metadata:
        return "metadata_only_no_document_or_url"
    return "raw_file_without_metadata"


def _status_class(status: str, *, reason: str = "") -> str:
    text = f"{status} {reason}".lower()
    if any(token in text for token in ("downloaded", "hit", "written", "present", "pass", "success", "available", "local_file")):
        return "success"
    if any(token in text for token in ("credential", "api_key", "forbidden", "unauthorized", "blocked", "access")):
        return "credential_or_access"
    if any(token in text for token in ("no matching", "locator", "not found", "candidate_absent", "no_document")):
        return "locator_miss"
    if any(token in text for token in ("parser", "parse", "unusable", "non_json")):
        return "parser_miss"
    if any(token in text for token in ("exhausted", "boundary", "no_bound_records", "no_supplier")):
        return "public_boundary"
    if any(token in text for token in ("fetch_failed", "http_0", "timeout", "retry")):
        return "source_unavailable"
    if text.strip():
        return "unknown_status"
    return "not_attempted"


def _looks_like_api_url(url: str) -> bool:
    text = url.lower()
    return "/api/" in text or "data.sec.gov" in text or text.endswith(".json")


def _looks_like_ticker_token(value: str) -> bool:
    token = value.strip()
    if not token or len(token) > 16:
        return False
    if any(ch.isdigit() for ch in token):
        return "." in token or "_" in token or token.isdigit()
    return token.upper() == token and token.replace("-", "").isalpha()


def _ticker_from_path_token(value: str) -> str:
    return value.replace("_", ".")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return dict(payload) if isinstance(payload, Mapping) else {}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, Mapping):
                    rows.append(dict(payload))
    except OSError:
        return []
    return rows


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sanitize_url(url: str) -> str:
    value = str(url or "").strip()
    if not value:
        return ""
    try:
        parsed = urlsplit(value)
    except ValueError:
        return value
    query = []
    for key, item in parse_qsl(parsed.query, keep_blank_values=True):
        query.append((key, "REDACTED" if key.lower() in SECRET_QUERY_KEYS else item))
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query, doseq=True), parsed.fragment))


def _normalize_url_for_key(url: str) -> str:
    sanitized = _sanitize_url(url).strip()
    if not sanitized:
        return ""
    try:
        parsed = urlsplit(sanitized)
    except ValueError:
        return sanitized.lower()
    path = parsed.path.rstrip("/") or parsed.path
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, parsed.query, "")).lower()


def _resolve_path(root: Path, value: str) -> Path | None:
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def _first_text(row: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        if isinstance(value, (dict, list, tuple, set)):
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _stable_id(*parts: Any) -> str:
    raw = "\x1f".join(str(part or "") for part in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:24]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rel(path: Path | None, root: Path) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _unique_strings(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _compact_payload(value: Any, *, max_items: int = 30) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _compact_payload(item, max_items=max_items) for key, item in list(value.items())[:max_items]}
    if isinstance(value, list):
        return [_compact_payload(item, max_items=max_items) for item in value[:max_items]]
    return value


def _compact_lineage_sample(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "runtime_manifest_path": str(row.get("runtime_manifest_path") or ""),
        "runtime_row_id": str(row.get("runtime_row_id") or ""),
        "ticker": str(row.get("ticker") or ""),
        "source_layer": str(row.get("source_layer") or ""),
        "source_id": str(row.get("source_id") or ""),
        "source_url": str(row.get("source_url") or ""),
        "runtime_source_document_ref": str(row.get("runtime_source_document_ref") or ""),
        "lineage_status": str(row.get("lineage_status") or ""),
    }


def _markdown_counter_table(counter: Mapping[str, Any], key_label: str, value_label: str) -> str:
    lines = [f"| {key_label} | {value_label} |", "| --- | ---: |"]
    for key, value in sorted(counter.items(), key=lambda item: str(item[0])):
        lines.append(f"| `{key}` | `{value}` |")
    return "\n".join(lines)
