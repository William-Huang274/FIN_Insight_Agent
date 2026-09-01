from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import sqlite3

import pytest

from sec_agent.agent_runtime.planner_tool_capabilities import (
    PlannerToolCapabilityError,
    derive_planner_tool_capabilities,
)


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _mart(path: Path) -> str:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE company_fact_observations (
                observation_id TEXT PRIMARY KEY,
                ticker TEXT NOT NULL,
                metric_id TEXT NOT NULL,
                period_role TEXT NOT NULL,
                accepted_at TEXT NOT NULL
            );
            CREATE TABLE metric_definitions (
                metric_id TEXT PRIMARY KEY,
                unit_family TEXT NOT NULL,
                formula TEXT
            );
            CREATE TABLE mart_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            INSERT INTO metric_definitions VALUES
                ('gross_margin', 'ratio_percent', 'gross_profit / revenue * 100'),
                ('gross_profit', 'monetary', NULL),
                ('revenue', 'monetary', NULL);
            INSERT INTO company_fact_observations VALUES
                ('o1', 'DELL', 'revenue', 'quarter_discrete', '2026-08-05T10:00:00Z'),
                ('o2', 'NVDA', 'revenue', 'fiscal_year', '2026-08-31T18:21:23Z'),
                ('o3', 'NVDA', 'gross_profit', 'quarter_discrete', '2026-08-31T18:21:23Z');
            INSERT INTO mart_metadata VALUES ('research_as_of', '2026-08-06');
            """
        )
    return _sha256(path)


def test_projection_is_answer_free_deterministic_and_uses_observation_cutoff(
    tmp_path: Path,
) -> None:
    path = tmp_path / "facts.sqlite"
    mart_sha = _mart(path)

    projection = derive_planner_tool_capabilities(
        sqlite_path=path,
        expected_mart_sha256=mart_sha,
        snapshot_id="fixture-snapshot",
    )
    repeat = derive_planner_tool_capabilities(
        sqlite_path=path,
        expected_mart_sha256=mart_sha,
        snapshot_id="fixture-snapshot",
    )

    assert projection == repeat
    assert projection.finance.supported_tickers == ("DELL", "NVDA")
    assert projection.finance.canonical_granularities == (
        "quarter_discrete",
        "fiscal_year",
    )
    metrics = {row.metric_id: row for row in projection.finance.metrics}
    assert metrics["revenue"].observed_tickers == ("DELL", "NVDA")
    assert metrics["gross_margin"].availability == "derived_at_query_time"
    assert metrics["gross_margin"].observed_tickers == ()
    assert projection.data_cutoff_kind == "latest_through_observation_accepted_at"
    assert projection.data_latest_through_accepted_at == (
        "2026-08-31T18:21:23+00:00"
    )
    assert projection.point_in_time_claimed is False
    assert "2026-08-06" not in projection.model_dump_json()
    assert tuple(row.source_route for row in projection.evidence_routes) == (
        "reviewed_first",
        "local_only",
        "external_required",
    )


def test_projection_rejects_wrong_mart_digest(tmp_path: Path) -> None:
    path = tmp_path / "facts.sqlite"
    _mart(path)

    with pytest.raises(
        PlannerToolCapabilityError,
        match="planner_capability_mart_sha256_mismatch",
    ):
        derive_planner_tool_capabilities(
            sqlite_path=path,
            expected_mart_sha256="0" * 64,
            snapshot_id="fixture-snapshot",
        )


def test_projection_rejects_missing_read_contract(tmp_path: Path) -> None:
    path = tmp_path / "facts.sqlite"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE unrelated (value TEXT)")

    with pytest.raises(
        PlannerToolCapabilityError,
        match="planner_capability_schema_missing:company_fact_observations",
    ):
        derive_planner_tool_capabilities(
            sqlite_path=path,
            expected_mart_sha256=_sha256(path),
            snapshot_id="fixture-snapshot",
        )
