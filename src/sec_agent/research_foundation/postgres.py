"""Thin PostgreSQL/pgvector ports for the DELL research data foundation.

This module deliberately does not implement Evidence admission, NumericFact
authority, financial calculations, or S2 persistence.  It stores immutable
source/capture/chunk lineage and exposes exact candidate retrieval.  Callers
must inject a psycopg-compatible connection; importing this module therefore
does not make PostgreSQL a mandatory dependency for the rest of FIN.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from hashlib import sha256
import ipaddress
import json
import math
from pathlib import Path
import re
from typing import Any, Mapping, Protocol, Sequence
from urllib.parse import urlsplit


SCHEMA_NAME = "fin_research"
SCHEMA_CONTRACT_VERSION = "fin_ia_dell_data_foundation_v1_0"
EMBEDDING_DIMENSION = 1024
DEFAULT_SCHEMA_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "architecture"
    / "research"
    / "FIN_0_1_3_DELL_DATA_FOUNDATION_SCHEMA_20260902.sql"
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_TERMINAL_ATTEMPT_STATUSES = frozenset(
    {"succeeded", "failed", "bounded_hold", "not_modified"}
)
_VECTOR_KINDS = frozenset({"halfvec", "vector"})
_CAPTURE_TEMPORAL_BASES = frozenset(
    {"capture_time", "immutable_source_version", "archive_seal"}
)
_MODEL_SAFE_LOCATOR_SCALAR_FIELDS = frozenset(
    {
        "anchor",
        "cell",
        "cell_range",
        "char_end",
        "char_start",
        "column",
        "column_end",
        "column_index",
        "column_start",
        "css",
        "fragment",
        "heading",
        "line_end",
        "line_start",
        "ordinal",
        "page",
        "page_index",
        "page_number",
        "paragraph_id",
        "row",
        "row_end",
        "row_index",
        "row_start",
        "section",
        "section_id",
        "sheet",
        "table",
        "table_id",
    }
)
_MODEL_SAFE_LOCATOR_URI_FIELDS = frozenset({"url", "uri"})
_MODEL_SAFE_BBOX_FIELDS = frozenset(
    {"bottom", "height", "left", "right", "top", "width", "x0", "x1", "y0", "y1"}
)
_WINDOWS_PATH_RE = re.compile(r"(?<![a-zA-Z0-9])[a-zA-Z]:[\\/]")
_POSIX_PRIVATE_PATH_RE = re.compile(
    r"(?:^|\s)/(?:data|etc|home|media|mnt|opt|private|root|srv|tmp|usr|var|volumes)/",
    re.IGNORECASE,
)
_PRIVATE_URI_RE = re.compile(
    r"(?:file|s3|gs|az|azure|blob|minio|r2|ssh|sftp)://", re.IGNORECASE
)


class ResearchFoundationError(ValueError):
    """Base error for invalid records or repository contract violations."""


class ImmutableRecordConflict(ResearchFoundationError):
    """An existing immutable ID has a different canonical record digest."""


class ConnectionLike(Protocol):
    """Small psycopg connection surface used by this repository."""

    def execute(
        self, query: str, params: Sequence[Any] | None = None
    ) -> Any: ...


@dataclass(frozen=True)
class SourceLocatorRecord:
    locator_id: str
    source_family: str
    source_type: str
    canonical_uri: str
    recorded_at: datetime
    issuer_id: str | None = None
    document_date: date | None = None
    source_published_at: datetime | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CaptureAttemptRecord:
    attempt_id: str
    source_locator_id: str
    case_id: str
    started_at: datetime
    completed_at: datetime
    research_as_of: datetime
    status: str
    input_digest: str
    request_receipt_digest: str
    terminal_receipt_digest: str
    failure_class: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SourceCaptureRecord:
    capture_id: str
    attempt_id: str
    source_locator_id: str
    captured_at: datetime
    response_status: int
    media_type: str
    byte_length: int
    raw_sha256: str
    object_uri: str
    capture_receipt_digest: str
    extracted_text_sha256: str | None = None
    temporal_authority_basis: str = "capture_time"
    source_version_id: str | None = None
    archive_sealed_at: datetime | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class KnowledgeChunkRecord:
    chunk_id: str
    capture_id: str
    ordinal: int
    chunk_kind: str
    chunk_contract_version: str
    parser_name: str
    parser_version: str
    parser_config_digest: str
    materialized_at: datetime
    locator: Mapping[str, Any]
    text: str
    embedding_model_id: str
    embedding_revision: str
    embedding: Sequence[float]
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LegacyObjectMappingRecord:
    mapping_id: str
    legacy_namespace: str
    legacy_snapshot_id: str
    legacy_snapshot_digest: str
    legacy_object_id: str
    mapping_receipt_digest: str
    mapped_at: datetime
    target_locator_id: str | None = None
    target_capture_id: str | None = None
    target_chunk_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExactVectorQuery:
    case_id: str
    research_as_of: datetime
    embedding: Sequence[float]
    limit: int = 8
    vector_kind: str = "halfvec"
    issuer_id: str | None = None
    source_family: str | None = None
    document_date_from: date | None = None
    document_date_to: date | None = None


@dataclass(frozen=True)
class RetrievalCandidate:
    chunk_id: str
    capture_id: str
    source_locator_id: str
    source_family: str
    issuer_id: str | None
    document_date: date | None
    source_published_at: datetime | None
    locator: Mapping[str, Any]
    text: str
    score: float
    research_as_of: datetime
    attempt_id: str
    attempt_receipt_digest: str
    capture_receipt_digest: str
    record_class: str = "retrieval_candidate"
    evidence_authority: bool = False
    numeric_fact_authority: bool = False


@dataclass(frozen=True)
class LegacyTarget:
    mapping_id: str
    target_kind: str
    target_id: str
    mapping_receipt_digest: str


def load_default_schema_sql() -> str:
    """Load the reviewed DDL without opening a connection or mutating state."""

    return DEFAULT_SCHEMA_PATH.read_text(encoding="utf-8")


class PostgresResearchFoundationRepository:
    """Append-only writes and exact read ports over an injected connection."""

    def __init__(self, connection: ConnectionLike) -> None:
        self._connection = connection

    def install_schema(self, schema_sql: str | None = None) -> None:
        """Apply the idempotent reviewed DDL.

        The SQL is trusted repository content, not user input.  All data-facing
        methods below use bind parameters.  This dedicated installer does not
        begin, commit or roll back: its caller must own the deployment
        transaction and decide what to do after an error.
        """

        sql = schema_sql or load_default_schema_sql()
        if re.search(
            r"(?im)^\s*(?:begin(?:\s+(?:work|transaction))?"
            r"|commit(?:\s+work)?|rollback(?:\s+work)?)\s*;",
            sql,
        ):
            raise ResearchFoundationError("schema_sql_embeds_transaction_control")
        self._connection.execute(sql)

    def put_source_locator(self, record: SourceLocatorRecord) -> str:
        _require_texts(
            (record.locator_id, "locator_id"),
            (record.source_family, "source_family"),
            (record.source_type, "source_type"),
            (record.canonical_uri, "canonical_uri"),
        )
        _require_aware(record.recorded_at, "recorded_at")
        if record.source_published_at is not None:
            _require_aware(record.source_published_at, "source_published_at")
        return self._put_immutable(
            table="source_locators",
            key_column="locator_id",
            values={
                "locator_id": record.locator_id,
                "source_family": record.source_family,
                "source_type": record.source_type,
                "canonical_uri": record.canonical_uri,
                "issuer_id": record.issuer_id,
                "document_date": record.document_date,
                "source_published_at": record.source_published_at,
                "recorded_at": record.recorded_at,
                "metadata": record.metadata,
            },
            casts={"metadata": "jsonb"},
        )

    def put_capture_attempt(self, record: CaptureAttemptRecord) -> str:
        _require_texts(
            (record.attempt_id, "attempt_id"),
            (record.source_locator_id, "source_locator_id"),
            (record.case_id, "case_id"),
        )
        for value, name in (
            (record.started_at, "started_at"),
            (record.completed_at, "completed_at"),
            (record.research_as_of, "research_as_of"),
        ):
            _require_aware(value, name)
        if record.completed_at < record.started_at:
            raise ResearchFoundationError("completed_at_before_started_at")
        if record.status not in _TERMINAL_ATTEMPT_STATUSES:
            raise ResearchFoundationError("capture_attempt_status_not_terminal")
        _require_digests(
            (record.input_digest, "input_digest"),
            (record.request_receipt_digest, "request_receipt_digest"),
            (record.terminal_receipt_digest, "terminal_receipt_digest"),
        )
        return self._put_immutable(
            table="capture_attempts",
            key_column="attempt_id",
            values={
                "attempt_id": record.attempt_id,
                "source_locator_id": record.source_locator_id,
                "case_id": record.case_id,
                "started_at": record.started_at,
                "completed_at": record.completed_at,
                "research_as_of": record.research_as_of,
                "status": record.status,
                "input_digest": record.input_digest,
                "request_receipt_digest": record.request_receipt_digest,
                "terminal_receipt_digest": record.terminal_receipt_digest,
                "failure_class": record.failure_class,
                "metadata": record.metadata,
            },
            casts={"metadata": "jsonb"},
        )

    def put_source_capture(self, record: SourceCaptureRecord) -> str:
        _require_texts(
            (record.capture_id, "capture_id"),
            (record.attempt_id, "attempt_id"),
            (record.source_locator_id, "source_locator_id"),
            (record.media_type, "media_type"),
            (record.object_uri, "object_uri"),
        )
        _require_aware(record.captured_at, "captured_at")
        _validate_capture_temporal_basis(record)
        if not 200 <= record.response_status <= 299:
            raise ResearchFoundationError("response_status_out_of_range")
        if record.byte_length < 0:
            raise ResearchFoundationError("byte_length_negative")
        _require_digests(
            (record.raw_sha256, "raw_sha256"),
            (record.capture_receipt_digest, "capture_receipt_digest"),
        )
        if record.extracted_text_sha256 is not None:
            _require_sha256(record.extracted_text_sha256, "extracted_text_sha256")
        attempt_row = self._connection.execute(
            f"SELECT source_locator_id, started_at, completed_at "
            f"FROM {SCHEMA_NAME}.capture_attempts WHERE attempt_id = %s",
            (record.attempt_id,),
        ).fetchone()
        if attempt_row is None:
            raise ResearchFoundationError("capture_attempt_not_found")
        if str(attempt_row[0]) != record.source_locator_id:
            raise ResearchFoundationError("capture_attempt_locator_mismatch")
        attempt_started_at = attempt_row[1]
        attempt_completed_at = attempt_row[2]
        if not isinstance(attempt_started_at, datetime) or not isinstance(
            attempt_completed_at, datetime
        ):
            raise ResearchFoundationError("capture_attempt_time_invalid")
        _require_aware(attempt_started_at, "attempt_started_at")
        _require_aware(attempt_completed_at, "attempt_completed_at")
        if not attempt_started_at <= record.captured_at <= attempt_completed_at:
            raise ResearchFoundationError("capture_outside_attempt_window")
        return self._put_immutable(
            table="source_captures",
            key_column="capture_id",
            values={
                "capture_id": record.capture_id,
                "attempt_id": record.attempt_id,
                "source_locator_id": record.source_locator_id,
                "captured_at": record.captured_at,
                "response_status": record.response_status,
                "media_type": record.media_type,
                "byte_length": record.byte_length,
                "raw_sha256": record.raw_sha256,
                "extracted_text_sha256": record.extracted_text_sha256,
                "object_uri": record.object_uri,
                "capture_receipt_digest": record.capture_receipt_digest,
                "temporal_authority_basis": record.temporal_authority_basis,
                "source_version_id": record.source_version_id,
                "archive_sealed_at": record.archive_sealed_at,
                "metadata": record.metadata,
            },
            casts={"metadata": "jsonb"},
        )

    def put_knowledge_chunk(self, record: KnowledgeChunkRecord) -> str:
        _require_texts(
            (record.chunk_id, "chunk_id"),
            (record.capture_id, "capture_id"),
            (record.chunk_kind, "chunk_kind"),
            (record.chunk_contract_version, "chunk_contract_version"),
            (record.parser_name, "parser_name"),
            (record.parser_version, "parser_version"),
            (record.embedding_model_id, "embedding_model_id"),
            (record.embedding_revision, "embedding_revision"),
        )
        if record.ordinal < 0:
            raise ResearchFoundationError("chunk_ordinal_negative")
        _require_sha256(record.parser_config_digest, "parser_config_digest")
        _require_aware(record.materialized_at, "materialized_at")
        if not record.text.strip():
            raise ResearchFoundationError("chunk_text_empty")
        vector_text = _vector_text(record.embedding)
        text_digest = sha256(record.text.encode("utf-8")).hexdigest()
        embedding_digest = sha256(vector_text.encode("ascii")).hexdigest()
        return self._put_immutable(
            table="knowledge_chunks",
            key_column="chunk_id",
            values={
                "chunk_id": record.chunk_id,
                "capture_id": record.capture_id,
                "ordinal": record.ordinal,
                "chunk_kind": record.chunk_kind,
                "chunk_contract_version": record.chunk_contract_version,
                "parser_name": record.parser_name,
                "parser_version": record.parser_version,
                "parser_config_digest": record.parser_config_digest,
                "materialized_at": record.materialized_at,
                "locator": record.locator,
                "chunk_text": record.text,
                "chunk_text_sha256": text_digest,
                "embedding_model_id": record.embedding_model_id,
                "embedding_revision": record.embedding_revision,
                "embedding_input_sha256": embedding_digest,
                "embedding": vector_text,
                "metadata": record.metadata,
            },
            casts={
                "locator": "jsonb",
                "embedding": "halfvec(1024)",
                "metadata": "jsonb",
            },
        )

    def put_legacy_mapping(self, record: LegacyObjectMappingRecord) -> str:
        _require_texts(
            (record.mapping_id, "mapping_id"),
            (record.legacy_namespace, "legacy_namespace"),
            (record.legacy_snapshot_id, "legacy_snapshot_id"),
            (record.legacy_object_id, "legacy_object_id"),
        )
        _require_digests(
            (record.legacy_snapshot_digest, "legacy_snapshot_digest"),
            (record.mapping_receipt_digest, "mapping_receipt_digest"),
        )
        _require_aware(record.mapped_at, "mapped_at")
        targets = (
            record.target_locator_id,
            record.target_capture_id,
            record.target_chunk_id,
        )
        if sum(value is not None for value in targets) != 1:
            raise ResearchFoundationError("legacy_mapping_requires_exactly_one_target")
        return self._put_immutable(
            table="legacy_object_mappings",
            key_column="mapping_id",
            values={
                "mapping_id": record.mapping_id,
                "legacy_namespace": record.legacy_namespace,
                "legacy_snapshot_id": record.legacy_snapshot_id,
                "legacy_snapshot_digest": record.legacy_snapshot_digest,
                "legacy_object_id": record.legacy_object_id,
                "target_locator_id": record.target_locator_id,
                "target_capture_id": record.target_capture_id,
                "target_chunk_id": record.target_chunk_id,
                "mapping_receipt_digest": record.mapping_receipt_digest,
                "mapped_at": record.mapped_at,
                "metadata": record.metadata,
            },
            casts={"metadata": "jsonb"},
        )

    def search_exact(self, query: ExactVectorQuery) -> tuple[RetrievalCandidate, ...]:
        """Return exact pgvector candidates; this never grants Evidence authority."""

        _require_text(query.case_id, "case_id")
        _require_aware(query.research_as_of, "research_as_of")
        if not 1 <= query.limit <= 50:
            raise ResearchFoundationError("candidate_limit_out_of_range")
        if query.vector_kind not in _VECTOR_KINDS:
            raise ResearchFoundationError("vector_kind_invalid")
        vector_text = _vector_text(query.embedding)

        if query.vector_kind == "halfvec":
            query_cast = "%s::halfvec(1024)"
            distance = "k.embedding <#> query_vector.value"
        else:
            query_cast = "%s::vector(1024)"
            distance = "k.embedding::vector(1024) <#> query_vector.value"

        filters = [
            "a.case_id = %s",
            "a.status = 'succeeded'",
            "a.research_as_of <= %s",
            "c.captured_at BETWEEN a.started_at AND a.completed_at",
            "((l.source_published_at IS NOT NULL "
            "AND l.source_published_at <= a.research_as_of) "
            "OR (l.source_published_at IS NULL "
            "AND l.document_date IS NOT NULL "
            "AND l.document_date <= a.research_as_of::date))",
            "((l.source_published_at IS NOT NULL "
            "AND l.source_published_at <= %s) "
            "OR (l.source_published_at IS NULL "
            "AND l.document_date IS NOT NULL "
            "AND l.document_date <= %s::date))",
            "((c.temporal_authority_basis = 'capture_time' "
            "AND c.captured_at <= %s) "
            "OR (c.temporal_authority_basis = 'immutable_source_version' "
            "AND c.source_version_id IS NOT NULL) "
            "OR (c.temporal_authority_basis = 'archive_seal' "
            "AND c.archive_sealed_at <= %s))",
        ]
        filter_params: list[Any] = [
            query.case_id,
            query.research_as_of,
            query.research_as_of,
            query.research_as_of,
            query.research_as_of,
            query.research_as_of,
        ]
        if query.issuer_id is not None:
            filters.append("l.issuer_id = %s")
            filter_params.append(query.issuer_id)
        if query.source_family is not None:
            filters.append("l.source_family = %s")
            filter_params.append(query.source_family)
        if query.document_date_from is not None:
            filters.append("l.document_date >= %s")
            filter_params.append(query.document_date_from)
        if query.document_date_to is not None:
            filters.append("l.document_date <= %s")
            filter_params.append(query.document_date_to)
        where = " AND ".join(filters)
        statement = f"""
            WITH query_vector(value) AS (VALUES ({query_cast}))
            SELECT
                k.chunk_id,
                c.capture_id,
                l.locator_id,
                l.source_family,
                l.issuer_id,
                l.document_date,
                l.source_published_at,
                k.locator,
                k.chunk_text,
                -({distance})::double precision AS score,
                'retrieval_candidate'::text AS record_class,
                false AS evidence_authority,
                false AS numeric_fact_authority,
                a.research_as_of,
                a.attempt_id,
                a.terminal_receipt_digest,
                c.capture_receipt_digest
            FROM {SCHEMA_NAME}.knowledge_chunks AS k
            JOIN {SCHEMA_NAME}.source_captures AS c
              ON c.capture_id = k.capture_id
            JOIN {SCHEMA_NAME}.capture_attempts AS a
              ON a.attempt_id = c.attempt_id
             AND a.source_locator_id = c.source_locator_id
            JOIN {SCHEMA_NAME}.source_locators AS l
              ON l.locator_id = c.source_locator_id
            CROSS JOIN query_vector
            WHERE {where}
            ORDER BY {distance}, k.chunk_id
            LIMIT %s
        """
        params = (
            vector_text,
            *filter_params,
            query.limit,
        )
        rows = self._connection.execute(statement, params).fetchall()
        return tuple(_candidate_from_row(row) for row in rows)

    def find_legacy_target(
        self,
        *,
        legacy_namespace: str,
        legacy_snapshot_digest: str,
        legacy_object_id: str,
    ) -> LegacyTarget | None:
        _require_text(legacy_namespace, "legacy_namespace")
        _require_sha256(legacy_snapshot_digest, "legacy_snapshot_digest")
        _require_text(legacy_object_id, "legacy_object_id")
        statement = f"""
            SELECT mapping_id, target_locator_id, target_capture_id,
                   target_chunk_id, mapping_receipt_digest
            FROM {SCHEMA_NAME}.legacy_object_mappings
            WHERE legacy_namespace = %s
              AND legacy_snapshot_digest = %s
              AND legacy_object_id = %s
        """
        row = self._connection.execute(
            statement,
            (legacy_namespace, legacy_snapshot_digest, legacy_object_id),
        ).fetchone()
        if row is None:
            return None
        targets = (
            ("source_locator", row[1]),
            ("source_capture", row[2]),
            ("knowledge_chunk", row[3]),
        )
        target_kind, target_id = next(
            (kind, value) for kind, value in targets if value is not None
        )
        return LegacyTarget(
            mapping_id=str(row[0]),
            target_kind=target_kind,
            target_id=str(target_id),
            mapping_receipt_digest=str(row[4]),
        )

    def _put_immutable(
        self,
        *,
        table: str,
        key_column: str,
        values: Mapping[str, Any],
        casts: Mapping[str, str] | None = None,
    ) -> str:
        casts = dict(casts or {})
        _require_identifier(table)
        _require_identifier(key_column)
        if key_column not in values:
            raise ResearchFoundationError("immutable_key_missing")
        for column in values:
            _require_identifier(column)
        allowed_casts = {"jsonb", "halfvec(1024)"}
        if not set(casts.values()) <= allowed_casts:
            raise ResearchFoundationError("sql_cast_not_allowed")

        record_digest = _digest(values)
        stored = {**dict(values), "record_digest": record_digest}
        columns = tuple(stored)
        params: list[Any] = []
        placeholders: list[str] = []
        for column, value in stored.items():
            cast = casts.get(column)
            if cast == "jsonb":
                params.append(_canonical_json(value))
            else:
                params.append(value)
            placeholders.append("%s" + (f"::{cast}" if cast else ""))
        statement = (
            f"INSERT INTO {SCHEMA_NAME}.{table} ({', '.join(columns)}) "
            f"VALUES ({', '.join(placeholders)}) "
            f"ON CONFLICT ({key_column}) DO NOTHING RETURNING {key_column}"
        )
        inserted = self._connection.execute(statement, params).fetchone()
        if inserted is not None:
            return str(inserted[0])
        key = str(values[key_column])
        lookup = (
            f"SELECT record_digest FROM {SCHEMA_NAME}.{table} "
            f"WHERE {key_column} = %s"
        )
        existing = self._connection.execute(lookup, (key,)).fetchone()
        if existing is None or str(existing[0]) != record_digest:
            raise ImmutableRecordConflict(f"immutable_record_conflict:{table}:{key}")
        return key


def _candidate_from_row(row: Sequence[Any]) -> RetrievalCandidate:
    locator = row[7]
    if isinstance(locator, str):
        locator = json.loads(locator)
    if not isinstance(locator, Mapping):
        raise ResearchFoundationError("candidate_locator_not_object")
    if str(row[10]) != "retrieval_candidate" or bool(row[11]) or bool(row[12]):
        raise ResearchFoundationError("candidate_authority_boundary_violated")
    return RetrievalCandidate(
        chunk_id=str(row[0]),
        capture_id=str(row[1]),
        source_locator_id=str(row[2]),
        source_family=str(row[3]),
        issuer_id=str(row[4]) if row[4] is not None else None,
        document_date=row[5],
        source_published_at=row[6],
        locator=_model_safe_locator(locator),
        text=str(row[8]),
        score=float(row[9]),
        research_as_of=row[13],
        attempt_id=str(row[14]),
        attempt_receipt_digest=str(row[15]),
        capture_receipt_digest=str(row[16]),
    )


def _validate_capture_temporal_basis(record: SourceCaptureRecord) -> None:
    basis = record.temporal_authority_basis
    if basis not in _CAPTURE_TEMPORAL_BASES:
        raise ResearchFoundationError("capture_temporal_authority_basis_invalid")
    if basis == "capture_time":
        if record.source_version_id is not None or record.archive_sealed_at is not None:
            raise ResearchFoundationError("capture_time_has_immutable_claim")
        return
    if basis == "immutable_source_version":
        if record.source_version_id is None:
            raise ResearchFoundationError("immutable_source_version_id_required")
        _require_text(record.source_version_id, "source_version_id")
        if record.archive_sealed_at is not None:
            raise ResearchFoundationError("immutable_source_version_has_archive_seal")
        return
    if record.source_version_id is not None:
        raise ResearchFoundationError("archive_seal_has_source_version_id")
    if record.archive_sealed_at is None:
        raise ResearchFoundationError("archive_sealed_at_required")
    _require_aware(record.archive_sealed_at, "archive_sealed_at")


def _model_safe_locator(locator: Mapping[str, Any]) -> dict[str, Any]:
    """Project only public, structural coordinates into model-visible output.

    Stored locators may retain local/object-store coordinates for trusted
    adapters.  Retrieval candidates intentionally expose neither unknown
    fields nor values that resemble filesystem or private object paths.
    """

    projected: dict[str, Any] = {}
    for raw_key, value in locator.items():
        if not isinstance(raw_key, str):
            continue
        key = raw_key.casefold()
        if key in _MODEL_SAFE_LOCATOR_SCALAR_FIELDS:
            safe_value = _model_safe_scalar(value)
            if safe_value is not None:
                projected[key] = safe_value
            continue
        if key in _MODEL_SAFE_LOCATOR_URI_FIELDS:
            if isinstance(value, str) and _is_public_http_uri(value):
                projected[key] = value
            continue
        if key == "bbox" and isinstance(value, Mapping):
            bbox: dict[str, int | float] = {}
            for bbox_key, coordinate in value.items():
                if (
                    isinstance(bbox_key, str)
                    and bbox_key.casefold() in _MODEL_SAFE_BBOX_FIELDS
                    and isinstance(coordinate, (int, float))
                    and not isinstance(coordinate, bool)
                    and math.isfinite(float(coordinate))
                ):
                    bbox[bbox_key.casefold()] = coordinate
            if bbox:
                projected["bbox"] = bbox
    return projected


def _model_safe_scalar(value: Any) -> str | int | float | bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if not isinstance(value, str) or not value or len(value) > 2048:
        return None
    stripped = value.strip()
    if not stripped or "\x00" in stripped or "\\" in stripped:
        return None
    lowered = stripped.casefold()
    if (
        stripped.startswith(("/", "//", "~/"))
        or _WINDOWS_PATH_RE.search(stripped)
        or _POSIX_PRIVATE_PATH_RE.search(stripped)
        or _PRIVATE_URI_RE.search(stripped)
        or "file:" in lowered
    ):
        return None
    return value


def _is_public_http_uri(value: str) -> bool:
    if not value or len(value) > 4096 or "\x00" in value or "\\" in value:
        return False
    parsed = urlsplit(value)
    if parsed.scheme.casefold() not in {"http", "https"}:
        return False
    if not parsed.hostname or parsed.username is not None or parsed.password is not None:
        return False
    try:
        parsed.port
    except ValueError:
        return False
    host = parsed.hostname.casefold().rstrip(".")
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return True
    return address.is_global


def _vector_text(values: Sequence[float]) -> str:
    if len(values) != EMBEDDING_DIMENSION:
        raise ResearchFoundationError(
            f"embedding_dimension_mismatch:{len(values)}:{EMBEDDING_DIMENSION}"
        )
    normalized: list[str] = []
    for value in values:
        number = float(value)
        if not math.isfinite(number):
            raise ResearchFoundationError("embedding_contains_non_finite_value")
        normalized.append(format(number, ".9g"))
    return "[" + ",".join(normalized) + "]"


def _canonical_json(value: Mapping[str, Any]) -> str:
    if not isinstance(value, Mapping):
        raise ResearchFoundationError("json_metadata_not_object")
    try:
        return json.dumps(
            _json_ready(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ResearchFoundationError("json_metadata_not_canonicalizable") from exc


def _digest(value: Mapping[str, Any]) -> str:
    payload = json.dumps(
        _json_ready(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return sha256(payload).hexdigest()


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ResearchFoundationError("record_contains_non_finite_value")
        return value
    raise ResearchFoundationError("record_not_canonicalizable")


def _require_text(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ResearchFoundationError(f"{name}_empty")


def _require_sha256(value: str, name: str) -> None:
    if not _SHA256_RE.fullmatch(value):
        raise ResearchFoundationError(f"{name}_invalid")


def _require_texts(*items: tuple[str, str]) -> None:
    for value, name in items:
        _require_text(value, name)


def _require_digests(*items: tuple[str, str]) -> None:
    for value, name in items:
        _require_sha256(value, name)


def _require_identifier(value: str) -> None:
    if not _IDENTIFIER_RE.fullmatch(value):
        raise ResearchFoundationError("sql_identifier_invalid")


def _require_aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ResearchFoundationError(f"{name}_timezone_required")


__all__ = [
    "CaptureAttemptRecord",
    "DEFAULT_SCHEMA_PATH",
    "EMBEDDING_DIMENSION",
    "ExactVectorQuery",
    "ImmutableRecordConflict",
    "KnowledgeChunkRecord",
    "LegacyObjectMappingRecord",
    "LegacyTarget",
    "PostgresResearchFoundationRepository",
    "ResearchFoundationError",
    "RetrievalCandidate",
    "SCHEMA_CONTRACT_VERSION",
    "SourceCaptureRecord",
    "SourceLocatorRecord",
    "load_default_schema_sql",
]
