from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Sequence

import pytest

from sec_agent.research_foundation.postgres import (
    CaptureAttemptRecord,
    ExactVectorQuery,
    ImmutableRecordConflict,
    KnowledgeChunkRecord,
    LegacyObjectMappingRecord,
    PostgresResearchFoundationRepository,
    ResearchFoundationError,
    SourceCaptureRecord,
    SourceLocatorRecord,
    load_default_schema_sql,
)


UTC = timezone.utc
NOW = datetime(2026, 9, 2, 2, 0, tzinfo=UTC)
DIGEST_A = "a" * 64
DIGEST_B = "b" * 64
DIGEST_C = "c" * 64
CASE_ID = "DELL_AI_INFRA_REFERENCE_VERTICAL"


class FakeCursor:
    def __init__(self, rows: Sequence[Sequence[Any]]) -> None:
        self._rows = list(rows)

    def fetchone(self) -> Sequence[Any] | None:
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list[Sequence[Any]]:
        return list(self._rows)


class FakeConnection:
    def __init__(self, results: Sequence[Sequence[Sequence[Any]]] = ()) -> None:
        self._results = [list(rows) for rows in results]
        self.executed: list[tuple[str, tuple[Any, ...] | None]] = []

    def execute(
        self, query: str, params: Sequence[Any] | None = None
    ) -> FakeCursor:
        captured_params = tuple(params) if params is not None else None
        self.executed.append((query, captured_params))
        rows = self._results.pop(0) if self._results else []
        return FakeCursor(rows)


def _locator() -> SourceLocatorRecord:
    return SourceLocatorRecord(
        locator_id="locator-dell-ir-001",
        source_family="F2_DELL_IR",
        source_type="issuer_web",
        canonical_uri="https://investors.dell.com/example",
        issuer_id="DELL",
        document_date=date(2026, 8, 28),
        source_published_at=datetime(2026, 8, 28, 12, tzinfo=UTC),
        recorded_at=NOW,
        metadata={"language": "en"},
    )


def _attempt() -> CaptureAttemptRecord:
    return CaptureAttemptRecord(
        attempt_id="attempt-dell-ir-001",
        source_locator_id="locator-dell-ir-001",
        case_id=CASE_ID,
        started_at=NOW,
        completed_at=datetime(2026, 9, 2, 2, 1, tzinfo=UTC),
        research_as_of=datetime(2026, 9, 2, 4, 30, tzinfo=UTC),
        status="succeeded",
        input_digest=DIGEST_A,
        request_receipt_digest=DIGEST_B,
        terminal_receipt_digest=DIGEST_C,
        metadata={"route": "issuer_ir"},
    )


def _capture() -> SourceCaptureRecord:
    return SourceCaptureRecord(
        capture_id="capture-dell-ir-001",
        attempt_id="attempt-dell-ir-001",
        source_locator_id="locator-dell-ir-001",
        captured_at=datetime(2026, 9, 2, 2, 0, 30, tzinfo=UTC),
        response_status=200,
        media_type="text/html",
        byte_length=1234,
        raw_sha256=DIGEST_A,
        extracted_text_sha256=DIGEST_B,
        object_uri="s3://fin-research/capture-dell-ir-001.html",
        capture_receipt_digest=DIGEST_C,
        metadata={"redirects": 0},
    )


def _chunk() -> KnowledgeChunkRecord:
    return KnowledgeChunkRecord(
        chunk_id="chunk-dell-ir-001-0000",
        capture_id="capture-dell-ir-001",
        ordinal=0,
        chunk_kind="narrative_passage",
        chunk_contract_version="fin_chunk_v1",
        parser_name="trafilatura",
        parser_version="2.2.0",
        parser_config_digest=DIGEST_A,
        materialized_at=datetime(2026, 9, 2, 2, 2, tzinfo=UTC),
        locator={"css": "main", "char_start": 0, "char_end": 16},
        text="Bound source text",
        embedding_model_id="Qwen/Qwen3-Embedding-0.6B",
        embedding_revision="local-qualified-revision",
        embedding=[0.0] * 1024,
        metadata={"language": "en"},
    )


def _mapping() -> LegacyObjectMappingRecord:
    return LegacyObjectMappingRecord(
        mapping_id="mapping-legacy-chunk-001",
        legacy_namespace="fin_ia_r38_objects",
        legacy_snapshot_id="snapshot-r38",
        legacy_snapshot_digest=DIGEST_A,
        legacy_object_id="COBJ::0123456789abcdef01234567",
        target_chunk_id="chunk-dell-ir-001-0000",
        mapping_receipt_digest=DIGEST_B,
        mapped_at=NOW,
    )


def test_schema_is_idempotent_bounded_and_authority_separated() -> None:
    sql = load_default_schema_sql()
    lowered = sql.casefold()

    assert "create schema if not exists fin_research" in lowered
    assert "create extension if not exists vector with version '0.8.6'" in lowered
    assert "postgresql major version 16" in lowered
    assert "embedding halfvec(1024) not null" in lowered
    assert "vector(1024)" in lowered
    assert "using hnsw" not in lowered
    assert "ivfflat" not in lowered
    assert "source_locator!=source_capture!=retrieval_candidate!=evidence" in lowered
    assert lowered.count("check (not evidence_authority)") >= 5
    assert lowered.count("check (not numeric_fact_authority)") >= 5
    assert "request_receipt_digest" in lowered
    assert "terminal_receipt_digest" in lowered
    assert "capture_receipt_digest" in lowered
    assert "research_as_of" in lowered
    assert "source_published_at" in lowered
    assert "check (response_status between 200 and 299)" in lowered
    assert "foreign key (attempt_id, source_locator_id, attempt_status)" in lowered
    assert "legacy_snapshot_digest" in lowered
    assert "reject_immutable_mutation" in lowered
    assert "temporal_authority_basis" in lowered
    assert "immutable_source_version" in lowered
    assert "archive_sealed_at" in lowered
    assert "validate_capture_attempt_window" in lowered
    assert not re.search(r"(?im)^\s*(?:begin|commit|rollback)\s*;", sql)
    assert "create table if not exists fin_research.financial" not in lowered


@pytest.mark.parametrize(
    ("method_name", "record", "expected_id", "sensitive_value"),
    [
        (
            "put_source_locator",
            _locator(),
            "locator-dell-ir-001",
            "https://investors.dell.com/example",
        ),
        (
            "put_capture_attempt",
            _attempt(),
            "attempt-dell-ir-001",
            CASE_ID,
        ),
        (
            "put_source_capture",
            _capture(),
            "capture-dell-ir-001",
            "s3://fin-research/capture-dell-ir-001.html",
        ),
        (
            "put_knowledge_chunk",
            _chunk(),
            "chunk-dell-ir-001-0000",
            "Bound source text",
        ),
        (
            "put_legacy_mapping",
            _mapping(),
            "mapping-legacy-chunk-001",
            "COBJ::0123456789abcdef01234567",
        ),
    ],
)
def test_write_ports_use_bound_parameters_and_return_inserted_identity(
    method_name: str,
    record: Any,
    expected_id: str,
    sensitive_value: str,
) -> None:
    results: list[list[tuple[Any, ...]]] = [[(expected_id,)]]
    if method_name == "put_source_capture":
        results.insert(
            0,
            [
                (
                    "locator-dell-ir-001",
                    NOW,
                    datetime(2026, 9, 2, 2, 1, tzinfo=UTC),
                )
            ],
        )
    connection = FakeConnection(results=results)
    repository = PostgresResearchFoundationRepository(connection)

    observed = getattr(repository, method_name)(record)

    assert observed == expected_id
    assert len(connection.executed) == (2 if method_name == "put_source_capture" else 1)
    statement, params = connection.executed[-1]
    assert "VALUES (%s" in statement or "VALUES (\n                %s" in statement
    assert sensitive_value not in statement
    assert params is not None
    assert sensitive_value in params
    assert isinstance(params[-1], str) and len(params[-1]) == 64


def test_immutable_replay_accepts_same_digest_and_rejects_drift() -> None:
    first_connection = FakeConnection(results=[[(_locator().locator_id,)]])
    first_repository = PostgresResearchFoundationRepository(first_connection)
    first_repository.put_source_locator(_locator())
    digest = first_connection.executed[0][1][-1]

    replay_connection = FakeConnection(results=[[], [(digest,)]])
    replay_repository = PostgresResearchFoundationRepository(replay_connection)
    assert replay_repository.put_source_locator(_locator()) == _locator().locator_id

    drift_connection = FakeConnection(results=[[], [(DIGEST_C,)]])
    drift_repository = PostgresResearchFoundationRepository(drift_connection)
    with pytest.raises(ImmutableRecordConflict, match="source_locators"):
        drift_repository.put_source_locator(_locator())


def test_exact_halfvec_search_is_parameterized_and_authority_capped() -> None:
    research_as_of = datetime(2026, 9, 2, 4, 30, tzinfo=UTC)
    candidate_row = (
        "chunk-dell-ir-001-0000",
        "capture-dell-ir-001",
        "locator-dell-ir-001",
        "F2_DELL_IR",
        "DELL",
        date(2026, 8, 28),
        datetime(2026, 8, 28, 12, tzinfo=UTC),
        {"css": "main"},
        "Bound source text",
        0.875,
        "retrieval_candidate",
        False,
        False,
        research_as_of,
        "attempt-dell-ir-001",
        DIGEST_C,
        DIGEST_B,
    )
    connection = FakeConnection(results=[[candidate_row]])
    repository = PostgresResearchFoundationRepository(connection)

    candidates = repository.search_exact(
        ExactVectorQuery(
            case_id=CASE_ID,
            research_as_of=research_as_of,
            embedding=[0.0] * 1024,
            limit=5,
            vector_kind="halfvec",
            issuer_id="DELL",
            source_family="F2_DELL_IR",
            document_date_from=date(2025, 1, 1),
            document_date_to=date(2026, 9, 2),
        )
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.record_class == "retrieval_candidate"
    assert candidate.evidence_authority is False
    assert candidate.numeric_fact_authority is False
    assert candidate.capture_receipt_digest == DIGEST_B

    statement, params = connection.executed[0]
    lowered = statement.casefold()
    assert "with query_vector(value) as (values (%s::halfvec(1024)))" in lowered
    assert "embedding <#> query_vector.value" in lowered
    assert "a.status = 'succeeded'" in lowered
    assert "c.captured_at between a.started_at and a.completed_at" in lowered
    assert "c.temporal_authority_basis = 'capture_time'" in lowered
    assert "c.captured_at <= %s" in lowered
    assert "c.temporal_authority_basis = 'immutable_source_version'" in lowered
    assert "c.source_version_id is not null" in lowered
    assert "c.temporal_authority_basis = 'archive_seal'" in lowered
    assert "c.archive_sealed_at <= %s" in lowered
    assert "l.document_date <= %s::date" in lowered
    assert "using hnsw" not in lowered
    assert "ivfflat" not in lowered
    assert CASE_ID.casefold() not in lowered
    assert "f2_dell_ir" not in lowered
    assert params is not None
    assert params[0].startswith("[") and params[0].endswith("]")
    assert params[-1] == 5


def test_candidate_locator_projection_removes_private_storage_and_file_paths() -> None:
    research_as_of = datetime(2026, 9, 2, 4, 30, tzinfo=UTC)
    unsafe_locator = {
        "css": "main article",
        "char_start": 4,
        "url": "https://investors.dell.com/public-source",
        "path": r"D:\private\capture.html",
        "unc_path": r"\\server\share\capture.html",
        "local_path": "/srv/fin/private/capture.html",
        "object_uri": "s3://fin-private/capture.html",
        "uri": "file:///D:/private/capture.html",
        "anchor": "s3://fin-private/embedded-object",
        "fragment": r"\\server\share\embedded-fragment",
        "heading": r"Z:\private\not-a-heading",
        "section": "/home/analyst/private",
        "bbox": {"x0": 1.5, "y0": 2, "path": "/tmp/private"},
    }
    candidate_row = (
        "chunk-dell-ir-001-0000",
        "capture-dell-ir-001",
        "locator-dell-ir-001",
        "F2_DELL_IR",
        "DELL",
        date(2026, 8, 28),
        datetime(2026, 8, 28, 12, tzinfo=UTC),
        unsafe_locator,
        "Bound source text",
        0.875,
        "retrieval_candidate",
        False,
        False,
        research_as_of,
        "attempt-dell-ir-001",
        DIGEST_C,
        DIGEST_B,
    )
    repository = PostgresResearchFoundationRepository(
        FakeConnection(results=[[candidate_row]])
    )

    candidate = repository.search_exact(
        ExactVectorQuery(
            case_id=CASE_ID,
            research_as_of=research_as_of,
            embedding=[0.0] * 1024,
        )
    )[0]

    assert candidate.locator == {
        "css": "main article",
        "char_start": 4,
        "url": "https://investors.dell.com/public-source",
        "bbox": {"x0": 1.5, "y0": 2},
    }
    projection = json.dumps(candidate.locator, sort_keys=True)
    for private_value in (
        "D:\\private",
        "server\\share",
        "/srv/fin",
        "s3://",
        "file://",
        "Z:\\private",
        "/home/analyst",
        "/tmp/private",
    ):
        assert private_value not in projection


def test_exact_vector_route_casts_without_creating_an_ann_path() -> None:
    connection = FakeConnection(results=[[]])
    repository = PostgresResearchFoundationRepository(connection)
    result = repository.search_exact(
        ExactVectorQuery(
            case_id=CASE_ID,
            research_as_of=NOW,
            embedding=[0.0] * 1024,
            vector_kind="vector",
        )
    )
    assert result == ()
    statement = connection.executed[0][0].casefold()
    assert "with query_vector(value) as (values (%s::vector(1024)))" in statement
    assert "embedding::vector(1024) <#> query_vector.value" in statement
    assert "create index" not in statement


@pytest.mark.parametrize(
    "record",
    [
        replace(_capture(), source_version_id="version-without-basis"),
        replace(
            _capture(),
            temporal_authority_basis="immutable_source_version",
        ),
        replace(_capture(), temporal_authority_basis="archive_seal"),
        replace(_capture(), temporal_authority_basis="unknown"),
    ],
)
def test_invalid_capture_temporal_claims_fail_before_sql(
    record: SourceCaptureRecord,
) -> None:
    connection = FakeConnection()
    with pytest.raises(ResearchFoundationError):
        PostgresResearchFoundationRepository(connection).put_source_capture(record)
    assert connection.executed == []


@pytest.mark.parametrize(
    "record",
    [
        replace(
            _capture(),
            temporal_authority_basis="immutable_source_version",
            source_version_id="sec-accession-0001571996-26-000001",
        ),
        replace(
            _capture(),
            temporal_authority_basis="archive_seal",
            archive_sealed_at=datetime(2026, 8, 28, 12, tzinfo=UTC),
        ),
    ],
)
def test_explicit_immutable_or_archive_capture_basis_is_accepted(
    record: SourceCaptureRecord,
) -> None:
    connection = FakeConnection(
        results=[
            [
                (
                    "locator-dell-ir-001",
                    NOW,
                    datetime(2026, 9, 2, 2, 1, tzinfo=UTC),
                )
            ],
            [(record.capture_id,)],
        ]
    )

    observed = PostgresResearchFoundationRepository(connection).put_source_capture(
        record
    )

    assert observed == record.capture_id
    assert record.temporal_authority_basis in connection.executed[-1][1]


def test_capture_time_must_be_inside_parent_attempt_window() -> None:
    connection = FakeConnection(
        results=[
            [
                (
                    "locator-dell-ir-001",
                    NOW,
                    datetime(2026, 9, 2, 2, 1, tzinfo=UTC),
                )
            ]
        ]
    )
    record = replace(
        _capture(), captured_at=datetime(2026, 9, 2, 2, 1, 1, tzinfo=UTC)
    )

    with pytest.raises(ResearchFoundationError, match="outside_attempt_window"):
        PostgresResearchFoundationRepository(connection).put_source_capture(record)

    assert len(connection.executed) == 1
    assert connection.executed[0][1] == (record.attempt_id,)


def test_legacy_lookup_is_snapshot_bound_and_parameterized() -> None:
    connection = FakeConnection(
        results=[
            [["mapping-1", None, None, "chunk-1", DIGEST_B]],
        ]
    )
    repository = PostgresResearchFoundationRepository(connection)
    target = repository.find_legacy_target(
        legacy_namespace="fin_ia_r38_objects",
        legacy_snapshot_digest=DIGEST_A,
        legacy_object_id="COBJ::0123456789abcdef01234567",
    )

    assert target is not None
    assert target.target_kind == "knowledge_chunk"
    assert target.target_id == "chunk-1"
    statement, params = connection.executed[0]
    assert "COBJ::0123456789abcdef01234567" not in statement
    assert params == (
        "fin_ia_r38_objects",
        DIGEST_A,
        "COBJ::0123456789abcdef01234567",
    )


def test_invalid_vectors_and_ambiguous_legacy_targets_fail_before_sql() -> None:
    connection = FakeConnection()
    repository = PostgresResearchFoundationRepository(connection)

    with pytest.raises(ResearchFoundationError, match="embedding_dimension_mismatch"):
        repository.search_exact(
            ExactVectorQuery(
                case_id=CASE_ID,
                research_as_of=NOW,
                embedding=[0.0] * 16,
            )
        )

    mapping = LegacyObjectMappingRecord(
        mapping_id="mapping-invalid",
        legacy_namespace="legacy",
        legacy_snapshot_id="snapshot",
        legacy_snapshot_digest=DIGEST_A,
        legacy_object_id="object",
        mapping_receipt_digest=DIGEST_B,
        mapped_at=NOW,
        target_capture_id="capture-1",
        target_chunk_id="chunk-1",
    )
    with pytest.raises(
        ResearchFoundationError, match="legacy_mapping_requires_exactly_one_target"
    ):
        repository.put_legacy_mapping(mapping)

    invalid_capture = SourceCaptureRecord(
        **{**_capture().__dict__, "response_status": 404}
    )
    with pytest.raises(ResearchFoundationError, match="response_status_out_of_range"):
        repository.put_source_capture(invalid_capture)

    assert connection.executed == []


def test_schema_installer_requires_caller_owned_transaction_boundary() -> None:
    connection = FakeConnection()
    repository = PostgresResearchFoundationRepository(connection)

    with pytest.raises(
        ResearchFoundationError, match="schema_sql_embeds_transaction_control"
    ):
        repository.install_schema("BEGIN;\nSELECT 1;\nCOMMIT;")
    assert connection.executed == []

    repository.install_schema("SELECT 1;")
    assert connection.executed == [("SELECT 1;", None)]


def test_default_schema_path_is_a_tracked_sql_artifact() -> None:
    expected = (
        Path(__file__).resolve().parents[1]
        / "docs"
        / "architecture"
        / "research"
        / "FIN_0_1_3_DELL_DATA_FOUNDATION_SCHEMA_20260902.sql"
    )
    assert expected.is_file()
    assert load_default_schema_sql() == expected.read_text(encoding="utf-8")


def test_schema_matches_frozen_data_seed_authority_boundaries() -> None:
    seed_path = (
        Path(__file__).resolve().parents[1]
        / "configs"
        / "research"
        / "fin_ia_0_1_3_dell_reference_vertical_data_seed_v1_0.json"
    )
    seed = json.loads(seed_path.read_text(encoding="utf-8"))
    sql = load_default_schema_sql().casefold()

    assert seed["case_id"] == CASE_ID
    assets = {row["asset_role"]: row for row in seed["verified_local_assets"]}
    assert assets["current_narrative_candidate_store"]["record_count"] == 1888
    assert assets["current_narrative_candidate_store"]["read_only_legacy_bridge"]
    assert assets["current_company_financial_fact_mart"]["observation_count"] == 1319
    assert (
        assets["current_company_financial_fact_mart"]["migration_policy"]
        == "do_not_recompute_or_relabel_during_foundation_cutover"
    )
    assert (
        seed["foundation_routes"]["legacy_s2_sqlite"]
        == "read_only_numeric_fact_port_until_a_separate_S2_authority_migration_is_approved"
    )
    assert "retrieval_candidate" in seed["promotion_states"]
    assert "source_capture" in seed["promotion_states"]
    assert "reviewed_evidence" in seed["promotion_states"]
    assert "migration_authority boolean not null default false" in sql
    assert "check (not migration_authority)" in sql
    assert "create table if not exists fin_research.numeric" not in sql
