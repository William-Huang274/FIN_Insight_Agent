from __future__ import annotations

import argparse
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import time
from typing import Any


SCHEMA_VERSION = "fin_ia_s1_pgvector_candidate_plane_qualification_v1_0"
QUALIFICATION_ROOT = Path(r"Z:\FIN_Insight_Agent_qualification")
IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
EXPECTED_OBJECTS_SHA256 = (
    "1c3e48486f933d23306dbabacb1641e26cb9bbc5b474da932d602752dff3fa92"
)
EXPECTED_DENSE_SHA256 = (
    "6356da50cfcb53fdfb48541c72889e76f6aa7d43b4c8450e95b89a2dd8bb4b06"
)
EXPECTED_MANIFEST_SHA256 = (
    "f02c743217e6197c26c68e4c68e972634208151cc54f2c6fa996afa7fa90e409"
)
EXPECTED_QRELS_SHA256 = (
    "1d56f1deef3d7082b4e308a9caae1e7b70941a66cd025620adbcc80231b7562b"
)
EXPECTED_QREL_MANIFEST_DIGEST = (
    "116d52a44569109ac47f0ce8e0875987673862d741d952eccee1a29c607ab7f4"
)


class QualificationError(RuntimeError):
    pass


@dataclass(frozen=True)
class QrelFilter:
    ticker: str
    publication_date_lte: str | None
    fiscal_years: tuple[int, ...]
    source_types: tuple[str, ...]
    source_tiers: tuple[str, ...]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise QualificationError(f"expected_json_object:{path}")
    return value


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise QualificationError(
                    f"expected_jsonl_object:{path}:{line_number}"
                )
            yield value


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _require_qualification_path(path: Path) -> Path:
    resolved = path.resolve()
    root = QUALIFICATION_ROOT.resolve()
    try:
        common = Path(os.path.commonpath((str(root), str(resolved))))
    except ValueError as exc:
        raise QualificationError(f"qualification_path_drive_mismatch:{path}") from exc
    if str(common).casefold() != str(root).casefold() or resolved == root:
        raise QualificationError(f"qualification_path_outside_root:{path}")
    return resolved


def _identifier(value: str, *, field: str) -> str:
    if IDENTIFIER.fullmatch(value) is None:
        raise QualificationError(f"invalid_{field}:{value}")
    return value


def qrel_filter(qrel: Mapping[str, Any]) -> QrelFilter:
    ticker = str(qrel.get("evidence_owner_ticker") or "").strip().upper()
    if not ticker:
        raise QualificationError("qrel_evidence_owner_ticker_missing")
    raw_date = str(qrel.get("publication_date_lte") or "").strip()
    fiscal_years = tuple(int(value) for value in qrel.get("reporting_fiscal_years") or ())
    return QrelFilter(
        ticker=ticker,
        publication_date_lte=raw_date or None,
        fiscal_years=fiscal_years,
        source_types=tuple(str(value) for value in qrel.get("form_types") or ()),
        source_tiers=tuple(str(value) for value in qrel.get("source_tiers") or ()),
    )


def _query_text(qrel: Mapping[str, Any]) -> str:
    values = [
        str(value).strip()
        for value in qrel.get("sparse_query_texts") or ()
        if str(value).strip()
    ]
    if not values:
        raise QualificationError("qrel_sparse_query_text_missing")
    return " ".join(dict.fromkeys(values))


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9&'/-]*", text.lower())


def _postgres_lexical_query(text: str) -> tuple[str, int]:
    # Uppercase OR is PostgreSQL websearch disjunction.  Conservative
    # alphanumeric lexemes keep punctuation from altering the tsquery grammar.
    # This remains a native lexical challenger, not BM25 score parity.
    values = list(dict.fromkeys(re.findall(r"[a-z0-9]+", text.lower())))
    if not values:
        raise QualificationError("postgres_lexical_query_empty")
    return " OR ".join(values), len(values)


def _target_ids(qrel: Mapping[str, Any]) -> tuple[str, ...]:
    values = tuple(
        str(value).strip()
        for value in qrel.get("target_current_source_record_ids") or ()
        if str(value).strip()
    )
    if not values:
        raise QualificationError("qrel_target_current_source_record_ids_missing")
    return values


def _filter_clause(filters: QrelFilter) -> tuple[str, list[Any]]:
    clauses = ["ticker = %s"]
    parameters: list[Any] = [filters.ticker]
    if filters.publication_date_lte:
        clauses.append("publication_date <= %s::date")
        parameters.append(filters.publication_date_lte)
    if filters.fiscal_years:
        clauses.append("(fiscal_year IS NULL OR fiscal_year = ANY(%s))")
        parameters.append(list(filters.fiscal_years))
    if filters.source_types:
        clauses.append("source_type = ANY(%s)")
        parameters.append(list(filters.source_types))
    if filters.source_tiers:
        clauses.append("source_tier = ANY(%s)")
        parameters.append(list(filters.source_tiers))
    return " AND ".join(clauses), parameters


def _first_target_rank(
    rows: Sequence[Mapping[str, Any]], target_ids: Sequence[str]
) -> int | None:
    targets = set(target_ids)
    for rank, row in enumerate(rows, start=1):
        lineage = {str(value) for value in row.get("lineage_source_record_ids") or ()}
        if targets.intersection(lineage):
            return rank
    return None


def _aggregate_ranking(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    eligible = [row for row in rows if int(row["eligible_target_count"]) > 0]
    ranks = [int(row["target_rank"]) for row in eligible if row["target_rank"]]
    return {
        "qrel_count": len(rows),
        "eligible_qrel_count": len(eligible),
        "target_in_top_16": sum(rank <= 16 for rank in ranks),
        "target_in_top_64": sum(rank <= 64 for rank in ranks),
        "mean_reciprocal_rank_eligible": (
            round(sum(1.0 / rank for rank in ranks) / len(eligible), 8)
            if eligible
            else 0.0
        ),
        "zero_eligible_target_qrel_ids": [
            row["qrel_id"] for row in rows if int(row["eligible_target_count"]) == 0
        ],
    }


def _load_and_validate_inputs(
    *, objects_path: Path, dense_path: Path, manifest_path: Path
) -> tuple[list[dict[str, Any]], Any, dict[str, Any], dict[str, Any]]:
    import numpy as np

    manifest = _read_json(manifest_path)
    observed = {
        "objects_sha256": sha256_file(objects_path),
        "dense_sha256": sha256_file(dense_path),
        "manifest_sha256": sha256_file(manifest_path),
    }
    expected_digests = {
        "objects_sha256": EXPECTED_OBJECTS_SHA256,
        "dense_sha256": EXPECTED_DENSE_SHA256,
        "manifest_sha256": EXPECTED_MANIFEST_SHA256,
    }
    if observed != expected_digests:
        raise QualificationError("frozen_input_digest_mismatch")
    if observed["objects_sha256"] != str(manifest.get("object_sha256") or ""):
        raise QualificationError("compiled_objects_digest_mismatch")
    if observed["dense_sha256"] != str(manifest.get("dense_sha256") or ""):
        raise QualificationError("dense_cache_digest_mismatch")

    objects = list(_iter_jsonl(objects_path))
    dense = np.load(dense_path, mmap_mode="r", allow_pickle=False)
    expected_shape = (
        int(manifest.get("object_count") or 0),
        int(manifest.get("embedding_dimensions") or 0),
    )
    if dense.shape != expected_shape or len(objects) != expected_shape[0]:
        raise QualificationError(
            f"object_embedding_shape_mismatch:{len(objects)}:{dense.shape}:{expected_shape}"
        )
    object_ids = [str(row.get("compiled_object_id") or "") for row in objects]
    if not all(object_ids) or len(object_ids) != len(set(object_ids)):
        raise QualificationError("compiled_object_identity_invalid")
    for ordinal, row in enumerate(objects):
        base = row.get("base_object_view")
        if not isinstance(base, Mapping):
            raise QualificationError(f"base_object_view_missing:{ordinal}")
        source_record_id = str(base.get("source_record_id") or "")
        lineage = {
            str(value) for value in row.get("lineage_source_record_ids") or ()
        }
        if not source_record_id or source_record_id not in lineage:
            raise QualificationError(f"primary_source_outside_lineage:{ordinal}")
        if (
            row.get("candidate_not_evidence") is not True
            or row.get("evidence_promoted") is not False
            or row.get("numeric_authority") is not False
        ):
            raise QualificationError(f"candidate_authority_contract_invalid:{ordinal}")
    identity_digest = canonical_digest(object_ids)
    if identity_digest != str(manifest.get("object_identity_digest") or ""):
        raise QualificationError("compiled_object_order_identity_mismatch")
    if str(dense.dtype) != str(manifest.get("dense_dtype") or ""):
        raise QualificationError("dense_cache_dtype_mismatch")
    minimum_norm = float("inf")
    maximum_norm = 0.0
    non_finite_count = 0
    zero_norm_count = 0
    vector_fingerprints: set[bytes] = set()
    for offset in range(0, len(dense), 2048):
        batch = np.asarray(dense[offset : offset + 2048], dtype=np.float32)
        non_finite_count += int((~np.isfinite(batch)).sum())
        norms = np.linalg.norm(batch, axis=1)
        zero_norm_count += int((norms == 0).sum())
        minimum_norm = min(minimum_norm, float(norms.min()))
        maximum_norm = max(maximum_norm, float(norms.max()))
        for vector in dense[offset : offset + 2048]:
            vector_fingerprints.add(
                hashlib.blake2b(vector.tobytes(), digest_size=16).digest()
            )
    if non_finite_count or zero_norm_count:
        raise QualificationError("dense_cache_non_finite_or_zero_norm")
    if minimum_norm < 0.99 or maximum_norm > 1.01:
        raise QualificationError("dense_cache_normalization_drift")
    observed.update(
        {
            "object_count": len(objects),
            "embedding_dimensions": int(dense.shape[1]),
            "dense_dtype": str(dense.dtype),
            "object_identity_digest": identity_digest,
            "minimum_l2_norm": minimum_norm,
            "maximum_l2_norm": maximum_norm,
            "non_finite_value_count": non_finite_count,
            "zero_norm_vector_count": zero_norm_count,
            "unique_float16_vector_count": len(vector_fingerprints),
            "duplicate_float16_vector_row_count": len(dense)
            - len(vector_fingerprints),
        }
    )
    return objects, dense, manifest, observed


def _validate_qrels_payload(
    payload: Mapping[str, Any], *, observed_sha256: str
) -> list[dict[str, Any]]:
    if observed_sha256 != EXPECTED_QRELS_SHA256:
        raise QualificationError("development_qrels_digest_mismatch")
    if payload.get("schema_version") != "fin_ia_s1c_requalified_ranking_qrels_v1_0":
        raise QualificationError("development_qrels_schema_mismatch")
    if payload.get("qrel_manifest_digest") != EXPECTED_QREL_MANIFEST_DIGEST:
        raise QualificationError("development_qrel_manifest_digest_mismatch")
    policy = payload.get("policy")
    required_policy = {
        "labels_joined_after_candidate_generation": True,
        "target_ids_forbidden_from_query_text": True,
        "candidate_is_not_evidence": True,
        "owner_acceptance_not_evidence_promotion": True,
    }
    if not isinstance(policy, Mapping) or any(
        policy.get(key) is not expected for key, expected in required_policy.items()
    ):
        raise QualificationError("development_qrels_policy_mismatch")
    raw_qrels = payload.get("qrels")
    if not isinstance(raw_qrels, list) or len(raw_qrels) != 18:
        raise QualificationError("development_qrel_count_mismatch")
    qrels = [dict(row) for row in raw_qrels if isinstance(row, Mapping)]
    qrel_ids = [str(row.get("qrel_id") or "") for row in qrels]
    if len(qrels) != 18 or not all(qrel_ids) or len(set(qrel_ids)) != len(qrel_ids):
        raise QualificationError("development_qrel_identity_invalid")
    for qrel in qrels:
        query_text = _query_text(qrel).casefold()
        if any(target.casefold() in query_text for target in _target_ids(qrel)):
            raise QualificationError(
                f"development_qrel_target_leakage:{qrel.get('qrel_id')}"
            )
    return qrels


def _create_schema(connection: Any, *, schema: str) -> None:
    from psycopg import sql

    schema_id = sql.Identifier(schema)
    if connection.execute(
        "SELECT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = %s)",
        (schema,),
    ).fetchone()[0]:
        raise QualificationError(f"fresh_attempt_schema_already_exists:{schema}")
    connection.execute(sql.SQL("CREATE SCHEMA {}").format(schema_id))
    connection.execute(
        sql.SQL(
            """
            CREATE TABLE {}.candidate_objects (
                ordinal integer PRIMARY KEY CHECK (ordinal >= 0),
                compiled_object_id text NOT NULL UNIQUE
                    CHECK (compiled_object_id ~ '^COBJ::[0-9a-f]{{24}}$'),
                object_kind text NOT NULL
                    CHECK (object_kind IN ('claim', 'metric_row', 'bounded_parent_context')),
                ticker text NOT NULL,
                source_type text,
                source_tier text,
                fiscal_year integer,
                publication_date date,
                period_end date,
                parent_document_id text,
                source_record_id text NOT NULL,
                lineage_source_record_ids text[] NOT NULL,
                model_text text NOT NULL,
                candidate_not_evidence boolean NOT NULL,
                evidence_promoted boolean NOT NULL,
                numeric_authority boolean NOT NULL,
                payload jsonb NOT NULL,
                embedding halfvec(1024) NOT NULL,
                lexical_document tsvector GENERATED ALWAYS AS (
                    to_tsvector('simple', model_text)
                ) STORED,
                CHECK (cardinality(lineage_source_record_ids) > 0),
                CHECK (source_record_id = ANY(lineage_source_record_ids)),
                CHECK (candidate_not_evidence),
                CHECK (NOT evidence_promoted),
                CHECK (NOT numeric_authority)
            )
            """
        ).format(schema_id)
    )


def _copy_objects(
    connection: Any,
    *,
    schema: str,
    objects: Sequence[Mapping[str, Any]],
    dense: Any,
) -> None:
    from pgvector import HalfVector
    from psycopg import sql
    from psycopg.types.json import Jsonb

    statement = sql.SQL(
        """
        COPY {}.candidate_objects (
            ordinal, compiled_object_id, object_kind, ticker, source_type,
            source_tier, fiscal_year, publication_date, period_end,
            parent_document_id, source_record_id, lineage_source_record_ids,
            model_text, candidate_not_evidence, evidence_promoted,
            numeric_authority, payload, embedding
        ) FROM STDIN
        """
    ).format(sql.Identifier(schema))
    with connection.cursor().copy(statement) as copy:
        for ordinal, (row, vector) in enumerate(zip(objects, dense, strict=True)):
            base = row.get("base_object_view")
            if not isinstance(base, Mapping):
                raise QualificationError(f"base_object_view_missing:{ordinal}")
            lineage = [str(value) for value in row.get("lineage_source_record_ids") or ()]
            source_record_id = str(base.get("source_record_id") or "")
            if not lineage or not source_record_id:
                raise QualificationError(f"source_lineage_missing:{ordinal}")
            copy.write_row(
                (
                    ordinal,
                    str(row.get("compiled_object_id") or ""),
                    str(row.get("object_kind") or ""),
                    str(base.get("ticker") or ""),
                    str(base.get("source_type") or "") or None,
                    str(base.get("source_tier") or "") or None,
                    int(base["fiscal_year"]) if base.get("fiscal_year") is not None else None,
                    str(base.get("publication_date") or "") or None,
                    str(base.get("period_end") or "") or None,
                    str(base.get("parent_document_id") or "") or None,
                    source_record_id,
                    lineage,
                    str(row.get("model_text") or ""),
                    bool(row.get("candidate_not_evidence")),
                    bool(row.get("evidence_promoted")),
                    bool(row.get("numeric_authority")),
                    Jsonb(dict(row)),
                    HalfVector(vector),
                )
            )


def _create_indexes(
    connection: Any, *, schema: str, build_hnsw: bool
) -> None:
    from psycopg import sql

    schema_id = sql.Identifier(schema)
    table = sql.SQL("{}.candidate_objects").format(schema_id)
    statements = [
        sql.SQL("CREATE INDEX candidate_ticker_date_idx ON {} (ticker, publication_date)").format(table),
        sql.SQL("CREATE INDEX candidate_fiscal_year_idx ON {} (fiscal_year)").format(table),
        sql.SQL("CREATE INDEX candidate_source_record_idx ON {} (source_record_id)").format(table),
        sql.SQL("CREATE INDEX candidate_lineage_gin_idx ON {} USING gin (lineage_source_record_ids)").format(table),
        sql.SQL("CREATE INDEX candidate_lexical_gin_idx ON {} USING gin (lexical_document)").format(table),
    ]
    if build_hnsw:
        statements.append(
            sql.SQL(
                "CREATE INDEX candidate_embedding_hnsw_idx ON {} "
                "USING hnsw (embedding halfvec_ip_ops) "
                "WITH (m = 16, ef_construction = 64)"
            ).format(table)
        )
    for statement in statements:
        connection.execute(statement)
    connection.execute(sql.SQL("ANALYZE {}").format(table))


def _database_receipt(connection: Any, *, schema: str) -> dict[str, Any]:
    from psycopg import sql

    row = connection.execute(
        sql.SQL(
            """
            SELECT
              count(*) AS object_count,
              count(DISTINCT compiled_object_id) AS distinct_object_count,
              count(*) FILTER (WHERE candidate_not_evidence) AS candidate_count,
              count(*) FILTER (WHERE evidence_promoted OR numeric_authority) AS authority_violation_count,
              min(ordinal) AS minimum_ordinal,
              max(ordinal) AS maximum_ordinal
            FROM {}.candidate_objects
            """
        ).format(sql.Identifier(schema))
    ).fetchone()
    extension_version = connection.execute(
        "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
    ).fetchone()[0]
    server_version = connection.execute("SHOW server_version").fetchone()[0]
    relation_bytes = connection.execute(
        "SELECT pg_total_relation_size(%s::regclass)",
        (f"{schema}.candidate_objects",),
    ).fetchone()[0]
    index_rows = connection.execute(
        """
        SELECT indexname, pg_relation_size((schemaname || '.' || indexname)::regclass)
        FROM pg_indexes
        WHERE schemaname = %s AND tablename = 'candidate_objects'
        ORDER BY indexname
        """,
        (schema,),
    ).fetchall()
    return {
        "server_version": server_version,
        "pgvector_extension_version": extension_version,
        "object_count": int(row[0]),
        "distinct_object_count": int(row[1]),
        "candidate_not_evidence_count": int(row[2]),
        "authority_violation_count": int(row[3]),
        "minimum_ordinal": int(row[4]),
        "maximum_ordinal": int(row[5]),
        "table_and_indexes_bytes": int(relation_bytes),
        "indexes": [
            {"index_name": str(name), "bytes": int(size)}
            for name, size in index_rows
        ],
    }


def _roundtrip_and_vector_receipt(
    connection: Any,
    *,
    schema: str,
    objects: Sequence[Mapping[str, Any]],
    dense: Any,
) -> dict[str, Any]:
    from pgvector import HalfVector
    from psycopg import sql

    mismatch_counts = {
        "ordinal": 0,
        "compiled_object_id": 0,
        "payload": 0,
        "embedding": 0,
    }
    mismatch_examples: list[dict[str, Any]] = []
    database_object_ids: list[str] = []
    roundtrip_rows = 0
    cursor = connection.execute(
        sql.SQL(
            "SELECT ordinal, compiled_object_id, payload, embedding "
            "FROM {}.candidate_objects ORDER BY ordinal"
        ).format(sql.Identifier(schema))
    )
    for expected_ordinal, database_row in enumerate(cursor):
        ordinal, object_id, payload, stored_embedding = database_row
        if expected_ordinal >= len(objects):
            mismatch_counts["ordinal"] += 1
            break
        expected_object = objects[expected_ordinal]
        expected_embedding = dense[expected_ordinal]
        failures: list[str] = []
        if int(ordinal) != expected_ordinal:
            mismatch_counts["ordinal"] += 1
            failures.append("ordinal")
        if str(object_id) != str(expected_object["compiled_object_id"]):
            mismatch_counts["compiled_object_id"] += 1
            failures.append("compiled_object_id")
        if canonical_digest(payload) != canonical_digest(expected_object):
            mismatch_counts["payload"] += 1
            failures.append("payload")
        if not bool((stored_embedding.to_numpy() == expected_embedding).all()):
            mismatch_counts["embedding"] += 1
            failures.append("embedding")
        if failures and len(mismatch_examples) < 10:
            mismatch_examples.append(
                {
                    "expected_ordinal": expected_ordinal,
                    "observed_ordinal": int(ordinal),
                    "compiled_object_id": str(object_id),
                    "failures": failures,
                }
            )
        database_object_ids.append(str(object_id))
        roundtrip_rows += 1
    if roundtrip_rows != len(objects):
        mismatch_counts["ordinal"] += abs(len(objects) - roundtrip_rows)

    sample_ordinals = sorted({0, len(objects) // 2, len(objects) - 1})
    samples: list[dict[str, Any]] = []
    for ordinal in sample_ordinals:
        database_row = connection.execute(
            sql.SQL(
                "SELECT compiled_object_id, payload, embedding "
                "FROM {}.candidate_objects WHERE ordinal = %s"
            ).format(sql.Identifier(schema)),
            (ordinal,),
        ).fetchone()
        if database_row is None:
            raise QualificationError(f"roundtrip_row_missing:{ordinal}")
        object_id, payload, stored_embedding = database_row
        expected = dense[ordinal]
        embedding_exact = bool((stored_embedding.to_numpy() == expected).all())
        payload_digest_equal = canonical_digest(payload) == canonical_digest(objects[ordinal])
        exact_top = connection.execute(
            sql.SQL(
                "SELECT compiled_object_id, embedding, embedding <#> %s AS negative_inner_product "
                "FROM {}.candidate_objects "
                "ORDER BY embedding <#> %s, compiled_object_id LIMIT 1"
            ).format(sql.Identifier(schema)),
            (HalfVector(expected), HalfVector(expected)),
        ).fetchone()
        expected_inner_product = float(
            (expected.astype("float32") * expected.astype("float32")).sum()
        )
        top_embedding_equal = bool(
            (exact_top[1].to_numpy() == expected).all()
        )
        samples.append(
            {
                "ordinal": ordinal,
                "compiled_object_id": str(object_id),
                "compiled_object_id_matches": str(object_id)
                == str(objects[ordinal]["compiled_object_id"]),
                "payload_canonical_digest_matches": payload_digest_equal,
                "embedding_float16_exact": embedding_exact,
                "exact_top_compiled_object_id": str(exact_top[0]),
                "exact_top_vector_matches_query": top_embedding_equal,
                "exact_top_negative_inner_product": float(exact_top[2]),
                "expected_negative_self_inner_product": -expected_inner_product,
                "negative_inner_product_error": abs(
                    float(exact_top[2]) + expected_inner_product
                ),
            }
        )
    return {
        "full_roundtrip_row_count": roundtrip_rows,
        "database_object_identity_digest": canonical_digest(database_object_ids),
        "database_object_identity_digest_matches": canonical_digest(
            database_object_ids
        )
        == canonical_digest(
            [str(row["compiled_object_id"]) for row in objects]
        ),
        "mismatch_counts": mismatch_counts,
        "mismatch_examples": mismatch_examples,
        "sample_count": len(samples),
        "all_identity_payload_embedding_roundtrip": (
            roundtrip_rows == len(objects)
            and not any(mismatch_counts.values())
        ),
        "all_exact_top_vectors_equivalent": all(
            row["exact_top_vector_matches_query"]
            and row["negative_inner_product_error"] <= 1e-5
            for row in samples
        ),
        "samples": samples,
    }


def _lexical_evaluation(
    connection: Any,
    *,
    schema: str,
    qrels: Sequence[Mapping[str, Any]],
    limit: int,
) -> dict[str, Any]:
    from psycopg import sql

    rows: list[dict[str, Any]] = []
    schema_id = sql.Identifier(schema)
    for qrel in qrels:
        filters = qrel_filter(qrel)
        where, parameters = _filter_clause(filters)
        query_text = _query_text(qrel)
        postgres_query, query_token_count = _postgres_lexical_query(query_text)
        ranked = connection.execute(
            sql.SQL(
                "SELECT compiled_object_id, lineage_source_record_ids, "
                "ts_rank_cd(lexical_document, websearch_to_tsquery('simple', %s)) AS score "
                "FROM {}.candidate_objects "
                f"WHERE {where} "
                "AND lexical_document @@ websearch_to_tsquery('simple', %s) "
                "ORDER BY score DESC, compiled_object_id LIMIT %s"
            ).format(schema_id),
            (postgres_query, *parameters, postgres_query, limit),
        ).fetchall()
        candidates = [
            {
                "compiled_object_id": str(item[0]),
                "lineage_source_record_ids": list(item[1]),
                "score": float(item[2]),
            }
            for item in ranked
        ]
        # Labels are joined only after candidate generation.  Target IDs never
        # enter the ranking SQL or its parameters.
        target_ids = _target_ids(qrel)
        eligible_object_count = connection.execute(
            sql.SQL(
                "SELECT count(*) FROM {}.candidate_objects " f"WHERE {where}"
            ).format(schema_id),
            tuple(parameters),
        ).fetchone()[0]
        eligible = connection.execute(
            sql.SQL(
                "SELECT count(*) FROM {}.candidate_objects "
                f"WHERE {where} AND lineage_source_record_ids && %s"
            ).format(schema_id),
            (*parameters, list(target_ids)),
        ).fetchone()[0]
        rank = _first_target_rank(candidates, target_ids)
        rows.append(
            {
                "qrel_id": str(qrel.get("qrel_id") or ""),
                "eligible_object_count": int(eligible_object_count),
                "eligible_target_count": int(eligible),
                "query_token_count": query_token_count,
                "returned_candidate_count": len(candidates),
                "target_rank": rank,
                "target_in_top_16": rank is not None and rank <= 16,
                "target_in_top_64": rank is not None and rank <= 64,
                "top_compiled_object_ids": [
                    item["compiled_object_id"] for item in candidates[:5]
                ],
            }
        )
    return {
        "route_id": "postgresql_native_fts_simple_or_challenger",
        "bm25_score_parity_claimed": False,
        "summary": {
            **_aggregate_ranking(rows),
            "zero_return_qrel_ids": [
                row["qrel_id"]
                for row in rows
                if int(row["returned_candidate_count"]) == 0
            ],
        },
        "qrels": rows,
    }


def _object_eligible(row: Mapping[str, Any], filters: QrelFilter) -> bool:
    base = row["base_object_view"]
    if str(base.get("ticker") or "").upper() != filters.ticker:
        return False
    if filters.source_types and str(base.get("source_type") or "").upper() not in {
        value.upper() for value in filters.source_types
    }:
        return False
    if filters.source_tiers and str(base.get("source_tier") or "") not in set(
        filters.source_tiers
    ):
        return False
    if filters.publication_date_lte:
        try:
            publication = date.fromisoformat(str(base.get("publication_date") or ""))
        except ValueError:
            return False
        if publication > date.fromisoformat(filters.publication_date_lte):
            return False
    fiscal_year = base.get("fiscal_year")
    if (
        filters.fiscal_years
        and fiscal_year not in {None, ""}
        and int(fiscal_year) not in set(filters.fiscal_years)
    ):
        return False
    return True


def _python_bm25_evaluation(
    *,
    objects: Sequence[Mapping[str, Any]],
    qrels: Sequence[Mapping[str, Any]],
    limit: int,
) -> dict[str, Any]:
    from rank_bm25 import BM25Okapi

    tokenized_objects = [_tokens(str(row.get("model_text") or "")) for row in objects]
    rows: list[dict[str, Any]] = []
    for qrel in qrels:
        filters = qrel_filter(qrel)
        eligible_indices = [
            index
            for index, row in enumerate(objects)
            if _object_eligible(row, filters)
        ]
        target_ids = _target_ids(qrel)
        target_set = set(target_ids)
        eligible_target_count = sum(
            bool(target_set.intersection(objects[index]["lineage_source_record_ids"]))
            for index in eligible_indices
        )
        query_tokens = _tokens(_query_text(qrel))
        if eligible_indices and query_tokens:
            scores = BM25Okapi(
                [tokenized_objects[index] for index in eligible_indices]
            ).get_scores(query_tokens)
            ranked_indices = sorted(
                range(len(eligible_indices)),
                key=lambda local_index: (
                    -float(scores[local_index]),
                    str(objects[eligible_indices[local_index]]["compiled_object_id"]),
                ),
            )[:limit]
            candidates = [
                {
                    "compiled_object_id": str(
                        objects[eligible_indices[local_index]]["compiled_object_id"]
                    ),
                    "lineage_source_record_ids": list(
                        objects[eligible_indices[local_index]][
                            "lineage_source_record_ids"
                        ]
                    ),
                    "score": float(scores[local_index]),
                }
                for local_index in ranked_indices
            ]
        else:
            candidates = []
        rank = _first_target_rank(candidates, target_ids)
        rows.append(
            {
                "qrel_id": str(qrel.get("qrel_id") or ""),
                "eligible_object_count": len(eligible_indices),
                "eligible_target_count": eligible_target_count,
                "query_token_count": len(query_tokens),
                "returned_candidate_count": len(candidates),
                "target_rank": rank,
                "target_in_top_16": rank is not None and rank <= 16,
                "target_in_top_64": rank is not None and rank <= 64,
                "top_compiled_object_ids": [
                    item["compiled_object_id"] for item in candidates[:5]
                ],
            }
        )
    return {
        "route_id": "python_rank_bm25_0_2_2_filtered_baseline",
        "summary": _aggregate_ranking(rows),
        "qrels": rows,
    }


def _validate_evaluation_alignment(
    *,
    objects: Sequence[Mapping[str, Any]],
    qrels: Sequence[Mapping[str, Any]],
    postgres_lexical: Mapping[str, Any],
    python_bm25: Mapping[str, Any],
) -> dict[str, Any]:
    qrels_by_id = {str(row["qrel_id"]): row for row in qrels}
    objects_by_id = {str(row["compiled_object_id"]): row for row in objects}
    postgres_rows = {
        str(row["qrel_id"]): row for row in postgres_lexical["qrels"]
    }
    bm25_rows = {str(row["qrel_id"]): row for row in python_bm25["qrels"]}
    failures: list[str] = []
    for qrel_id, qrel in qrels_by_id.items():
        postgres_row = postgres_rows.get(qrel_id)
        bm25_row = bm25_rows.get(qrel_id)
        if postgres_row is None or bm25_row is None:
            failures.append(f"evaluation_row_missing:{qrel_id}")
            continue
        if int(postgres_row["eligible_object_count"]) != int(
            bm25_row["eligible_object_count"]
        ):
            failures.append(f"eligible_object_count_mismatch:{qrel_id}")
        if int(postgres_row["eligible_target_count"]) != int(
            bm25_row["eligible_target_count"]
        ):
            failures.append(f"eligible_target_count_mismatch:{qrel_id}")
        if int(postgres_row["eligible_target_count"]) <= 0:
            failures.append(f"eligible_target_missing:{qrel_id}")
        filters = qrel_filter(qrel)
        for object_id in postgres_row["top_compiled_object_ids"]:
            candidate = objects_by_id.get(str(object_id))
            if candidate is None or not _object_eligible(candidate, filters):
                failures.append(f"postgres_filter_violation:{qrel_id}:{object_id}")
    if failures:
        raise QualificationError(";".join(failures[:20]))
    return {
        "qrel_count": len(qrels_by_id),
        "postgres_python_eligible_counts_match": True,
        "source_level_targets_eligible_after_hard_filters": len(qrels_by_id),
        "postgres_top_candidate_filter_violation_count": 0,
    }


def _validate_receipt(
    *,
    input_receipt: Mapping[str, Any],
    database: Mapping[str, Any],
    roundtrip: Mapping[str, Any],
) -> None:
    expected_count = int(input_receipt["object_count"])
    failures: list[str] = []
    if int(database["object_count"]) != expected_count:
        failures.append("database_object_count_mismatch")
    if int(database["distinct_object_count"]) != expected_count:
        failures.append("database_object_identity_collision")
    if int(database["candidate_not_evidence_count"]) != expected_count:
        failures.append("candidate_authority_boundary_mismatch")
    if int(database["authority_violation_count"]) != 0:
        failures.append("database_authority_violation")
    if not roundtrip["all_identity_payload_embedding_roundtrip"]:
        failures.append("roundtrip_mismatch")
    if not roundtrip["all_exact_top_vectors_equivalent"]:
        failures.append("exact_vector_equivalence_mismatch")
    if failures:
        raise QualificationError(";".join(failures))


def run(args: argparse.Namespace) -> dict[str, Any]:
    import numpy as np
    import psycopg
    from pgvector.psycopg import register_vector

    qualification_root = _require_qualification_path(Path(args.qualification_root))
    receipt_path = _require_qualification_path(Path(args.receipt))
    if qualification_root not in receipt_path.parents:
        raise QualificationError("receipt_outside_attempt_qualification_root")
    schema = _identifier(args.schema, field="schema")
    if args.host not in {"127.0.0.1", "::1"}:
        raise QualificationError("database_host_must_be_loopback")
    if args.candidate_limit <= 0:
        raise QualificationError("candidate_limit_must_be_positive")
    password = os.environ.get(args.password_env)
    if not password:
        raise QualificationError(f"database_password_env_missing:{args.password_env}")

    objects_path = Path(args.objects).resolve()
    dense_path = Path(args.dense).resolve()
    manifest_path = Path(args.manifest).resolve()
    qrels_path = Path(args.qrels).resolve()
    for path in (objects_path, dense_path, manifest_path, qrels_path):
        if not path.is_file():
            raise QualificationError(f"input_file_missing:{path}")

    started = time.perf_counter()
    objects, dense, manifest, input_receipt = _load_and_validate_inputs(
        objects_path=objects_path,
        dense_path=dense_path,
        manifest_path=manifest_path,
    )
    qrels_sha256 = sha256_file(qrels_path)
    qrel_payload = _read_json(qrels_path)
    qrels = _validate_qrels_payload(
        qrel_payload,
        observed_sha256=qrels_sha256,
    )
    input_receipt.update(
        {
            "qrels_sha256": qrels_sha256,
            "qrel_manifest_digest": qrel_payload["qrel_manifest_digest"],
            "qrel_count": len(qrels),
            "model_id": str(manifest.get("model_id") or "Qwen/Qwen3-Embedding-0.6B"),
            "model_digest": str(manifest.get("model_digest") or ""),
        }
    )

    connection = psycopg.connect(
        host=args.host,
        port=args.port,
        dbname=args.database,
        user=args.user,
        password=password,
        application_name="finsight_s1_pgvector_qualification",
        connect_timeout=10,
        autocommit=True,
    )
    try:
        connection.execute("SET statement_timeout = '20min'")
        connection.execute("SET maintenance_work_mem = '128MB'")
        connection.execute("SET max_parallel_maintenance_workers = 0")
        connection.execute("CREATE EXTENSION IF NOT EXISTS vector")
        register_vector(connection)

        if args.verify_existing:
            if not connection.execute(
                "SELECT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = %s)",
                (schema,),
            ).fetchone()[0]:
                raise QualificationError(f"existing_schema_missing:{schema}")
            copy_seconds = 0.0
            index_seconds = 0.0
        else:
            import_started = time.perf_counter()
            with connection.transaction():
                _create_schema(connection, schema=schema)
                _copy_objects(connection, schema=schema, objects=objects, dense=dense)
            copy_seconds = time.perf_counter() - import_started

            index_started = time.perf_counter()
            with connection.transaction():
                _create_indexes(
                    connection,
                    schema=schema,
                    build_hnsw=args.build_hnsw,
                )
            index_seconds = time.perf_counter() - index_started

        database = _database_receipt(connection, schema=schema)
        roundtrip = _roundtrip_and_vector_receipt(
            connection,
            schema=schema,
            objects=objects,
            dense=dense,
        )
        lexical_started = time.perf_counter()
        lexical = _lexical_evaluation(
            connection,
            schema=schema,
            qrels=qrels,
            limit=args.candidate_limit,
        )
        lexical_seconds = time.perf_counter() - lexical_started
        bm25_started = time.perf_counter()
        bm25 = _python_bm25_evaluation(
            objects=objects,
            qrels=qrels,
            limit=args.candidate_limit,
        )
        bm25_seconds = time.perf_counter() - bm25_started
        evaluation_alignment = _validate_evaluation_alignment(
            objects=objects,
            qrels=qrels,
            postgres_lexical=lexical,
            python_bm25=bm25,
        )
        _validate_receipt(
            input_receipt=input_receipt,
            database=database,
            roundtrip=roundtrip,
        )
    finally:
        connection.close()

    receipt = {
        "schema_version": SCHEMA_VERSION,
        "status": (
            "bounded_development_restart_readback_pass"
            if args.verify_existing
            else "bounded_development_storage_and_lexical_pass"
        ),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "attempt_id": args.attempt_id,
        "authority": {
            "candidate_is_not_evidence": True,
            "development_qrels_only": True,
            "blind_qualification": False,
            "production_cutover_authorized": False,
            "evidence_admission_authorized": False,
            "numeric_authority": False,
        },
        "candidate": {
            "server_image_expected": "pgvector/pgvector:0.8.6-pg16-trixie",
            "server_image_digest_expected": (
                "sha256:c8483555ce48101872f888c1df8a895ff689d6c7c7a5f7ac266475f9dfe89e0b"
            ),
            "python_pgvector_version": importlib.metadata.version("pgvector"),
            "psycopg_version": importlib.metadata.version("psycopg"),
            "rank_bm25_version": importlib.metadata.version("rank-bm25"),
            "numpy_version": np.__version__,
            "schema": schema,
            "hnsw_built": any(
                row["index_name"] == "candidate_embedding_hnsw_idx"
                for row in database["indexes"]
            ),
            "operation_mode": (
                "verify_existing_after_restart"
                if args.verify_existing
                else "fresh_import"
            ),
        },
        "inputs": input_receipt,
        "database": database,
        "roundtrip": roundtrip,
        "development_lexical_evaluation": {
            "python_bm25_baseline": bm25,
            "postgresql_native_fts_challenger": lexical,
            "filter_and_target_alignment": evaluation_alignment,
        },
        "dense_query_evaluation": {
            "status": "not_run_query_embedding_runtime_not_yet_qualified",
            "reason": (
                "Stored frozen document embeddings were migrated and exact inner-product vector equivalence was tested, "
                "but query embeddings require a separately pinned local model runtime."
            ),
        },
        "timing_seconds": {
            "copy": round(copy_seconds, 3),
            "indexes": round(index_seconds, 3),
            "postgresql_lexical_evaluation": round(lexical_seconds, 3),
            "python_bm25_baseline": round(bm25_seconds, 3),
            "total": round(time.perf_counter() - started, 3),
        },
        "known_boundaries": [
            "The 18 qrels are development labels with historical exposure, not a blind holdout.",
            "This attempt tests storage, identity, filters, PostgreSQL full-text search and frozen-vector exact inner-product equivalence only.",
            "PostgreSQL native FTS is a challenger and does not claim rank_bm25 score parity.",
            "A candidate row remains Candidate and grants neither Evidence nor numeric authority.",
            "No reranker, graph route, Evidence admission, report, product or release decision is authorized.",
        ],
    }
    receipt["result_digest"] = canonical_digest(receipt)
    _atomic_write_json(receipt_path, receipt)
    return receipt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import the frozen S1 object/embedding plane into pgvector and run bounded development checks."
    )
    parser.add_argument("--qualification-root", required=True)
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--objects", required=True)
    parser.add_argument("--dense", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--qrels", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=55433)
    parser.add_argument("--database", default="finsight_s1")
    parser.add_argument("--user", default="finsight")
    parser.add_argument("--password-env", default="PGPASSWORD")
    parser.add_argument("--schema", default="s1_candidate_v1")
    parser.add_argument("--candidate-limit", type=int, default=64)
    parser.add_argument("--build-hnsw", action="store_true")
    parser.add_argument("--verify-existing", action="store_true")
    return parser


def _write_failure_receipt(args: argparse.Namespace, exc: Exception) -> None:
    try:
        path = _require_qualification_path(Path(args.receipt))
        if path.exists():
            return
        message = str(exc)
        secret = os.environ.get(getattr(args, "password_env", "PGPASSWORD"), "")
        if secret:
            message = message.replace(secret, "[REDACTED]")
        receipt: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "status": "failed_immutable_attempt",
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "attempt_id": str(getattr(args, "attempt_id", "unknown")),
            "error_type": type(exc).__name__,
            "error": message,
            "authority": {
                "candidate_is_not_evidence": True,
                "blind_qualification": False,
                "production_cutover_authorized": False,
                "failed_attempt_must_not_be_promoted": True,
            },
        }
        receipt["result_digest"] = canonical_digest(receipt)
        _atomic_write_json(path, receipt)
    except Exception:
        # Preserve the original error.  Failure-receipt problems must never
        # make the runner print credentials or replace the owning exception.
        return


def main() -> int:
    args = build_parser().parse_args()
    try:
        receipt = run(args)
    except Exception as exc:
        _write_failure_receipt(args, exc)
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 1
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "attempt_id": receipt["attempt_id"],
                "object_count": receipt["database"]["object_count"],
                "lexical_summaries": {
                    key: value["summary"]
                    for key, value in receipt["development_lexical_evaluation"].items()
                    if isinstance(value, Mapping) and "summary" in value
                },
                "result_digest": receipt["result_digest"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
