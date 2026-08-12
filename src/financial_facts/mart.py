from __future__ import annotations

from collections import Counter
from contextlib import closing
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Mapping, Sequence

from retrieval.query_plan import canonical_digest

from .contracts import (
    COMPANY_FACT_MART_SCHEMA_VERSION,
    CompanyFactObservation,
    MetricDefinition,
)
from .sec_companyfacts import CompanyFactMartPolicy, parse_policy_sources


OBSERVATION_COLUMNS = (
    "observation_id",
    "ticker",
    "cik",
    "legal_name",
    "metric_id",
    "unit_family",
    "taxonomy",
    "concept",
    "concept_priority",
    "value_decimal",
    "unit",
    "period_start",
    "period_end",
    "duration_days",
    "period_role",
    "fiscal_year",
    "fiscal_period",
    "reported_fiscal_year",
    "reported_fiscal_period",
    "form",
    "accession_number",
    "filed_at",
    "accepted_at",
    "frame",
    "primary_document",
    "citation_url",
    "companyfacts_ref",
    "companyfacts_sha256",
    "submissions_ref",
    "submissions_sha256",
    "captured_at",
    "superseded_by_observation_id",
)


def build_company_fact_mart(
    policy: CompanyFactMartPolicy,
    *,
    repository_root: Path,
    sqlite_path: Path,
) -> dict[str, Any]:
    observations, source_summary = parse_policy_sources(
        policy,
        repository_root=repository_root,
    )
    write_company_fact_mart(
        sqlite_path,
        observations=observations,
        metrics=policy.metrics,
        policy=policy,
    )
    observation_digest = canonical_digest([row.as_dict() for row in observations])
    summary: dict[str, Any] = {
        "schema_version": "fin_ia_s2_company_financial_fact_mart_build_result_v1_0",
        "status": "company_financial_fact_mart_materialized_acceptance_pending",
        "recorded_at": policy.recorded_at,
        "research_as_of": policy.research_as_of,
        "storage": {
            "sqlite_ref": _relative(sqlite_path, repository_root),
            "sqlite_sha256": _sha256(sqlite_path),
            "sqlite_bytes": sqlite_path.stat().st_size,
            "observation_digest": observation_digest,
        },
        "counts": {
            "observations": len(observations),
            "tickers": len({row.ticker for row in observations}),
            "metrics": len({row.metric_id for row in observations}),
            "by_ticker": dict(Counter(row.ticker for row in observations)),
            "by_metric": dict(Counter(row.metric_id for row in observations)),
            "by_period_role": dict(
                Counter(row.period_role for row in observations)
            ),
            "superseded_observations": sum(
                row.superseded_by_observation_id is not None
                for row in observations
            ),
        },
        "source_summary": source_summary,
        "authority": {
            "candidate_or_metric_row_grants_numeric_authority": False,
            "source_capture_digest_required": True,
            "accepted_at_and_as_of_required": True,
            # The source parser intentionally rejects observations that cannot
            # be bound to a captured filing identity.  "All" therefore means
            # every admitted, source-bound vintage, not every row ever emitted
            # by SEC CompanyFacts.
            "all_admitted_vintages_preserved": True,
            "typed_conflict_fails_closed": True,
            "fact_signal_context_mixed_table_forbidden": True,
        },
    }
    return {**summary, "result_digest": canonical_digest(summary)}


def write_company_fact_mart(
    path: Path,
    *,
    observations: Sequence[CompanyFactObservation],
    metrics: Sequence[MetricDefinition],
    policy: CompanyFactMartPolicy,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    if temporary.exists():
        temporary.unlink()
    with closing(sqlite3.connect(str(temporary))) as connection:
        connection.executescript(
            """
            PRAGMA journal_mode=DELETE;
            PRAGMA synchronous=FULL;
            CREATE TABLE mart_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE metric_definitions (
                metric_id TEXT PRIMARY KEY,
                unit_family TEXT NOT NULL,
                formula TEXT,
                concepts_json TEXT NOT NULL,
                allowed_units_json TEXT NOT NULL
            );
            CREATE TABLE company_fact_observations (
                observation_id TEXT PRIMARY KEY,
                ticker TEXT NOT NULL,
                cik TEXT NOT NULL,
                legal_name TEXT NOT NULL,
                metric_id TEXT NOT NULL,
                unit_family TEXT NOT NULL,
                taxonomy TEXT NOT NULL,
                concept TEXT NOT NULL,
                concept_priority INTEGER NOT NULL,
                value_decimal TEXT NOT NULL,
                unit TEXT NOT NULL,
                period_start TEXT,
                period_end TEXT NOT NULL,
                duration_days INTEGER,
                period_role TEXT NOT NULL,
                fiscal_year INTEGER,
                fiscal_period TEXT,
                reported_fiscal_year INTEGER,
                reported_fiscal_period TEXT,
                form TEXT NOT NULL,
                accession_number TEXT NOT NULL,
                filed_at TEXT NOT NULL,
                accepted_at TEXT NOT NULL,
                frame TEXT,
                primary_document TEXT NOT NULL,
                citation_url TEXT NOT NULL,
                companyfacts_ref TEXT NOT NULL,
                companyfacts_sha256 TEXT NOT NULL,
                submissions_ref TEXT NOT NULL,
                submissions_sha256 TEXT NOT NULL,
                captured_at TEXT NOT NULL,
                superseded_by_observation_id TEXT
            );
            CREATE INDEX idx_company_fact_exact_lookup
                ON company_fact_observations(
                    ticker, metric_id, period_role, period_end, accepted_at
                );
            CREATE INDEX idx_company_fact_period
                ON company_fact_observations(
                    ticker, metric_id, fiscal_year, fiscal_period, period_end
                );
            CREATE INDEX idx_company_fact_accession
                ON company_fact_observations(accession_number);
            """
        )
        metadata = {
            "schema_version": COMPANY_FACT_MART_SCHEMA_VERSION,
            "recorded_at": policy.recorded_at,
            "research_as_of": policy.research_as_of,
            "policy_digest": canonical_digest(
                {
                    "recorded_at": policy.recorded_at,
                    "research_as_of": policy.research_as_of,
                    "minimum_period_end": policy.minimum_period_end,
                    "allowed_forms": policy.allowed_forms,
                    "sources": [asdict(row) for row in policy.sources],
                    "metrics": [asdict(row) for row in policy.metrics],
                    "authority": dict(policy.authority),
                }
            ),
            "observation_count": str(len(observations)),
        }
        connection.executemany(
            "INSERT INTO mart_metadata(key, value) VALUES (?, ?)",
            sorted(metadata.items()),
        )
        connection.executemany(
            """
            INSERT INTO metric_definitions(
                metric_id, unit_family, formula, concepts_json, allowed_units_json
            ) VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    metric.metric_id,
                    metric.unit_family,
                    metric.formula,
                    json.dumps(metric.concepts, ensure_ascii=False),
                    json.dumps(metric.allowed_units, ensure_ascii=False),
                )
                for metric in metrics
            ],
        )
        placeholders = ",".join("?" for _ in OBSERVATION_COLUMNS)
        connection.executemany(
            "INSERT INTO company_fact_observations("
            + ",".join(OBSERVATION_COLUMNS)
            + f") VALUES ({placeholders})",
            [
                tuple(getattr(row, column) for column in OBSERVATION_COLUMNS)
                for row in observations
            ],
        )
        connection.commit()
        observed = connection.execute(
            "SELECT COUNT(*) FROM company_fact_observations"
        ).fetchone()[0]
        if int(observed) != len(observations):
            raise ValueError("company_fact_mart_row_count_mismatch")
    temporary.replace(path)


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


__all__ = [
    "OBSERVATION_COLUMNS",
    "build_company_fact_mart",
    "write_company_fact_mart",
]
