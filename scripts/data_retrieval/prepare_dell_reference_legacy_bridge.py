"""Prepare a replayable, locator-only bridge for the frozen S1 v5 store.

The output is a JSONL plan.  It never connects to PostgreSQL and never creates
SourceCapture, KnowledgeChunk, Evidence, or NumericFact records.  The frozen
legacy objects remain read-only inputs until a separately approved importer
consumes this plan.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import SplitResult, urlsplit, urlunsplit


SCHEMA_VERSION = "fin_ia_dell_legacy_source_locator_bridge_plan_v1_0"
INVENTORY_RECEIPT_SCHEMA_VERSION = (
    "fin_ia_dell_legacy_source_inventory_receipt_v1_0"
)
MAPPING_RECEIPT_SCHEMA_VERSION = (
    "fin_ia_dell_legacy_source_locator_mapping_receipt_v1_0"
)
LEGACY_NAMESPACE = "fin_ia_0_1_3_s1b_current_financial_object_store"
LEGACY_SNAPSHOT_ID = "v5"
LEGACY_SNAPSHOT_REF = (
    "data/workbench_private/fin_0_1_3_s1b_current_financial_object_store/"
    "v5/records.jsonl"
)
LEGACY_SNAPSHOT_SHA256 = (
    "d4c7e51790713d32fc10a9d0382b617f8ebd60861a3741d3adcee34392045d45"
)
LEGACY_SNAPSHOT_RECORD_COUNT = 1888

_AUTHORITY_BOUNDARY = {
    "migration_authority": False,
    "evidence_authority": False,
    "numeric_fact_authority": False,
}


class BridgePreparationError(ValueError):
    """The frozen input or requested output violates the bridge contract."""


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def canonical_sha256(value: Any) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_frozen_records(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise BridgePreparationError(f"input_not_file:{path}")
    observed_digest = file_sha256(path)
    if observed_digest != LEGACY_SNAPSHOT_SHA256:
        raise BridgePreparationError(
            "legacy_snapshot_sha256_mismatch:"
            f"{observed_digest}:{LEGACY_SNAPSHOT_SHA256}"
        )

    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                raise BridgePreparationError(f"blank_jsonl_line:{line_number}")
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise BridgePreparationError(
                    f"invalid_jsonl_line:{line_number}"
                ) from exc
            if not isinstance(value, dict):
                raise BridgePreparationError(
                    f"jsonl_record_not_object:{line_number}"
                )
            records.append(value)

    if len(records) != LEGACY_SNAPSHOT_RECORD_COUNT:
        raise BridgePreparationError(
            "legacy_snapshot_record_count_mismatch:"
            f"{len(records)}:{LEGACY_SNAPSHOT_RECORD_COUNT}"
        )
    legacy_ids = [_required_text(row, "evidence_id", index) for index, row in enumerate(records)]
    if len(set(legacy_ids)) != len(legacy_ids):
        raise BridgePreparationError("legacy_object_id_duplicate")
    return records


def _required_text(record: Mapping[str, Any], key: str, ordinal: int) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise BridgePreparationError(f"required_field_missing:{ordinal}:{key}")
    return value.strip()


def _publication_date(record: Mapping[str, Any], ordinal: int) -> str:
    value = _required_text(record, "publication_date", ordinal)
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise BridgePreparationError(
            f"publication_date_invalid:{ordinal}:{value}"
        ) from exc
    if parsed.isoformat() != value:
        raise BridgePreparationError(
            f"publication_date_not_canonical:{ordinal}:{value}"
        )
    return value


def _canonical_http_uri(value: str, ordinal: int) -> str:
    if "\r" in value or "\n" in value:
        raise BridgePreparationError(f"source_url_control_character:{ordinal}")
    parsed = urlsplit(value)
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
        raise BridgePreparationError(f"source_url_not_http:{ordinal}")
    if parsed.username is not None or parsed.password is not None:
        raise BridgePreparationError(f"source_url_contains_credentials:{ordinal}")
    host = parsed.hostname.encode("idna").decode("ascii").casefold()
    try:
        port = parsed.port
    except ValueError as exc:
        raise BridgePreparationError(f"source_url_port_invalid:{ordinal}") from exc
    default_port = (parsed.scheme.casefold() == "http" and port == 80) or (
        parsed.scheme.casefold() == "https" and port == 443
    )
    netloc = host if port is None or default_port else f"{host}:{port}"
    normalized = SplitResult(
        scheme=parsed.scheme.casefold(),
        netloc=netloc,
        path=parsed.path or "/",
        query=parsed.query,
        fragment="",
    )
    return urlunsplit(normalized)


def _canonical_uri(record: Mapping[str, Any], ordinal: int) -> tuple[str, str]:
    source_url = record.get("source_url")
    if isinstance(source_url, str) and source_url.strip():
        return _canonical_http_uri(source_url.strip(), ordinal), "legacy_source_url"

    source_type = _required_text(record, "source_type", ordinal)
    if source_type != "MARKET_SNAPSHOT":
        raise BridgePreparationError(
            f"source_url_missing_for_non_snapshot:{ordinal}:{source_type}"
        )
    metadata = record.get("metadata")
    if not isinstance(metadata, Mapping):
        raise BridgePreparationError(f"metadata_not_object:{ordinal}")
    parent_document_id = metadata.get("parent_document_id")
    legacy_object_id = _required_text(record, "evidence_id", ordinal)
    identity_basis = (
        str(parent_document_id).strip()
        if isinstance(parent_document_id, str) and parent_document_id.strip()
        else legacy_object_id
    )
    identity_digest = canonical_sha256(
        {
            "legacy_namespace": LEGACY_NAMESPACE,
            "legacy_snapshot_id": LEGACY_SNAPSHOT_ID,
            "identity_basis": identity_basis,
        }
    )
    return (
        f"urn:fin-insight:legacy-source:{LEGACY_SNAPSHOT_ID}:{identity_digest}",
        "content_addressed_legacy_snapshot_urn",
    )


def _authority_metadata(**values: Any) -> dict[str, Any]:
    return {**values, **_AUTHORITY_BOUNDARY}


def _bridge_row(record: Mapping[str, Any], ordinal: int) -> dict[str, Any]:
    legacy_object_id = _required_text(record, "evidence_id", ordinal)
    issuer_id = _required_text(record, "ticker", ordinal)
    source_type = _required_text(record, "source_type", ordinal)
    document_date = _publication_date(record, ordinal)
    canonical_uri, uri_basis = _canonical_uri(record, ordinal)
    metadata = record.get("metadata")
    if not isinstance(metadata, Mapping):
        raise BridgePreparationError(f"metadata_not_object:{ordinal}")
    parent_document_id = metadata.get("parent_document_id")
    if not isinstance(parent_document_id, str) or not parent_document_id.strip():
        raise BridgePreparationError(
            f"legacy_parent_document_id_missing:{ordinal}"
        )

    locator_identity = {
        "canonical_uri": canonical_uri,
        "issuer_id": issuer_id,
        "source_type": source_type,
        "document_date": document_date,
    }
    locator_id = "LEGACY_LOC::" + canonical_sha256(locator_identity)[:24]
    locator_metadata = _authority_metadata(
        bridge_scope="source_locator_only",
        canonical_uri_basis=uri_basis,
        date_precision="date_only",
        legacy_parent_document_id=parent_document_id,
        legacy_source_tier=record.get("source_tier"),
        license_scope=record.get("license_scope"),
        redistributable=record.get("redistributable"),
    )
    source_locator = {
        "locator_id": locator_id,
        "source_family": "LEGACY_S1_V5",
        "source_type": source_type,
        "canonical_uri": canonical_uri,
        "issuer_id": issuer_id,
        "document_date": document_date,
        "source_published_at": None,
        "metadata": locator_metadata,
    }
    source_locator_digest = canonical_sha256(source_locator)

    mapping_identity = {
        "legacy_namespace": LEGACY_NAMESPACE,
        "legacy_snapshot_id": LEGACY_SNAPSHOT_ID,
        "legacy_snapshot_digest": LEGACY_SNAPSHOT_SHA256,
        "legacy_object_id": legacy_object_id,
        "target_kind": "source_locator",
        "target_locator_id": locator_id,
        "source_locator_digest": source_locator_digest,
    }
    mapping_id = "LEGACY_MAP::" + canonical_sha256(mapping_identity)[:24]
    mapping_metadata = _authority_metadata(
        bridge_scope="source_locator_only",
        legacy_ordinal=ordinal,
    )
    mapping_receipt_payload = {
        "schema_version": MAPPING_RECEIPT_SCHEMA_VERSION,
        "mapping_id": mapping_id,
        **mapping_identity,
        "authority": dict(_AUTHORITY_BOUNDARY),
        "metadata": mapping_metadata,
    }
    mapping_receipt_digest = canonical_sha256(mapping_receipt_payload)
    legacy_mapping = {
        **mapping_receipt_payload,
        "mapping_receipt_digest": mapping_receipt_digest,
    }
    return {
        "record_type": "legacy_source_locator_mapping",
        "schema_version": SCHEMA_VERSION,
        "source_locator": source_locator,
        "source_locator_digest": source_locator_digest,
        "legacy_mapping": legacy_mapping,
    }


def _sorted_counts(values: Iterable[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def _inventory_receipt(
    records: Sequence[Mapping[str, Any]],
    selected_rows: Sequence[Mapping[str, Any]],
    issuer_filter: str | None,
) -> dict[str, Any]:
    issuers = [_required_text(row, "ticker", index) for index, row in enumerate(records)]
    source_types = [
        _required_text(row, "source_type", index) for index, row in enumerate(records)
    ]
    publication_dates = [
        _publication_date(row, index) for index, row in enumerate(records)
    ]
    url_present = sum(
        isinstance(row.get("source_url"), str) and bool(row["source_url"].strip())
        for row in records
    )
    selected_receipts = sorted(
        str(row["legacy_mapping"]["mapping_receipt_digest"])
        for row in selected_rows
    )
    receipt_payload = {
        "record_type": "source_inventory_receipt",
        "schema_version": INVENTORY_RECEIPT_SCHEMA_VERSION,
        "legacy_namespace": LEGACY_NAMESPACE,
        "legacy_snapshot_id": LEGACY_SNAPSHOT_ID,
        "legacy_snapshot_ref": LEGACY_SNAPSHOT_REF,
        "legacy_snapshot_sha256": LEGACY_SNAPSHOT_SHA256,
        "legacy_snapshot_record_count": LEGACY_SNAPSHOT_RECORD_COUNT,
        "unique_legacy_object_count": len(
            {_required_text(row, "evidence_id", index) for index, row in enumerate(records)}
        ),
        "records_by_issuer": _sorted_counts(issuers),
        "records_by_source_type": _sorted_counts(source_types),
        "publication_date_min": min(publication_dates),
        "publication_date_max": max(publication_dates),
        "source_url_present_count": url_present,
        "source_url_absent_count": len(records) - url_present,
        "issuer_filter": issuer_filter,
        "selected_mapping_count": len(selected_rows),
        "selected_unique_locator_count": len(
            {str(row["source_locator"]["locator_id"]) for row in selected_rows}
        ),
        "selected_mapping_receipts_digest": canonical_sha256(selected_receipts),
        "authority": dict(_AUTHORITY_BOUNDARY),
    }
    return {
        **receipt_payload,
        "inventory_receipt_digest": canonical_sha256(receipt_payload),
    }


def prepare_bridge_plan(
    *,
    input_path: Path,
    output_path: Path,
    issuer: str | None = None,
) -> dict[str, Any]:
    """Validate the frozen store and write a deterministic locator-only plan."""

    input_path = input_path.resolve()
    output_path = output_path.resolve()
    if input_path == output_path:
        raise BridgePreparationError("output_must_differ_from_input")
    if output_path.exists():
        raise BridgePreparationError(f"output_exists:{output_path}")
    if not output_path.parent.is_dir():
        raise BridgePreparationError(f"output_parent_missing:{output_path.parent}")

    issuer_filter = issuer.strip().upper() if issuer is not None else None
    if issuer is not None and not issuer_filter:
        raise BridgePreparationError("issuer_filter_empty")
    records = _read_frozen_records(input_path)
    rows = [
        _bridge_row(record, ordinal)
        for ordinal, record in enumerate(records)
        if issuer_filter is None
        or _required_text(record, "ticker", ordinal).upper() == issuer_filter
    ]
    if not rows:
        raise BridgePreparationError(f"issuer_filter_no_records:{issuer_filter}")
    rows.sort(key=lambda row: str(row["legacy_mapping"]["legacy_object_id"]))
    receipt = _inventory_receipt(records, rows, issuer_filter)
    payload = "\n".join(canonical_json(row) for row in (receipt, *rows)) + "\n"

    try:
        with output_path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
    except FileExistsError as exc:
        raise BridgePreparationError(f"output_exists:{output_path}") from exc

    return {
        "status": "locator_only_bridge_plan_written",
        "output_path": str(output_path),
        "output_sha256": sha256(payload.encode("utf-8")).hexdigest(),
        "output_line_count": len(rows) + 1,
        "selected_mapping_count": len(rows),
        "selected_unique_locator_count": receipt["selected_unique_locator_count"],
        "inventory_receipt_digest": receipt["inventory_receipt_digest"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare a frozen S1 v5 source-locator bridge plan without database writes."
        )
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--issuer", type=str)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = prepare_bridge_plan(
            input_path=args.input,
            output_path=args.output,
            issuer=args.issuer,
        )
    except BridgePreparationError as exc:
        parser.error(str(exc))
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
