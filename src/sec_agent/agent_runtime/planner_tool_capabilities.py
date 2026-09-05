"""Answer-free Planner capabilities derived from the frozen S2 fact mart.

This is a read-only projection of what the already-existing tools can accept.
It does not inspect methods, qrels, expected answers, or policy as-of labels.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .dell_reference_vertical_contracts import canonical_sha256


PLANNER_TOOL_CAPABILITY_SCHEMA_VERSION = (
    "fin_ia_dell_planner_tool_capabilities_v1_0"
)
_CANONICAL_GRANULARITIES = (
    "quarter_discrete",
    "fiscal_ytd",
    "fiscal_year",
    "instant",
)
_NON_CAPABILITIES = (
    "backlog_or_orders",
    "ai_server_or_segment_revenue",
    "unit_shipments_or_asp_or_price_volume_mix",
    "customer_deployments_or_procurement",
    "gpu_or_hbm_or_dram_or_nand_shipments_and_prices",
    "greater_china_revenue_or_export_control_exposure",
    "management_guidance_or_future_capex_or_leases",
    "model_demand_or_hyperscaler_demand_forecasts",
)


class PlannerToolCapabilityError(ValueError):
    """The supplied mart cannot truthfully support a capability projection."""


class _FrozenCapabilityModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class FinancialMetricCapability(_FrozenCapabilityModel):
    metric_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,95}$")
    unit_family: str = Field(min_length=1, max_length=64)
    availability: Literal["direct_observation", "derived_at_query_time"]
    formula: str | None = None
    observed_tickers: tuple[str, ...]
    observed_period_roles: tuple[str, ...] = Field(default=(), exclude_if=lambda value: not value)

    @model_validator(mode="after")
    def validate_availability(self) -> "FinancialMetricCapability":
        if self.availability == "derived_at_query_time" and not self.formula:
            raise ValueError("derived_metric_formula_required")
        if self.availability == "direct_observation" and self.formula:
            raise ValueError("direct_metric_formula_forbidden")
        return self


class FinancialToolCapability(_FrozenCapabilityModel):
    supported_tickers: tuple[str, ...] = Field(min_length=1)
    metrics: tuple[FinancialMetricCapability, ...] = Field(min_length=1)
    canonical_granularities: tuple[
        Literal["quarter_discrete", "fiscal_ytd", "fiscal_year", "instant"], ...
    ] = Field(min_length=1)
    date_format: Literal["YYYY-MM-DD"]
    latest_query_rule: Literal[
        "omit_period_bounds_and_fiscal_years_for_latest_available_observations"
    ]
    maximum_fiscal_year_count: Literal[4]
    non_capabilities: tuple[str, ...] = Field(min_length=1)
    derived_metric_rule: Literal[
        "derived_metrics_are_computed_by_the_existing_fact_executor_and_may_return_typed_gap_when_inputs_do_not_align"
    ]


class EvidenceRouteCapability(_FrozenCapabilityModel):
    source_route: Literal["reviewed_first", "local_only", "external_required"]
    semantics: str = Field(min_length=1, max_length=600)
    candidate_is_not_evidence: Literal[True]


class PlannerToolCapabilityProjection(_FrozenCapabilityModel):
    schema_version: Literal["fin_ia_dell_planner_tool_capabilities_v1_0"]
    snapshot_id: str = Field(min_length=1, max_length=240)
    mart_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    data_cutoff_kind: Literal["latest_through_observation_accepted_at"]
    data_latest_through_accepted_at: str = Field(min_length=1, max_length=40)
    point_in_time_claimed: Literal[False]
    finance: FinancialToolCapability
    evidence_routes: tuple[EvidenceRouteCapability, ...] = Field(min_length=3, max_length=3)
    projection_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("data_latest_through_accepted_at")
    @classmethod
    def validate_latest_through(cls, value: str) -> str:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("accepted_at_must_be_iso_datetime") from exc
        if parsed.tzinfo is None:
            raise ValueError("accepted_at_timezone_required")
        return value

    @model_validator(mode="after")
    def validate_projection_digest(self) -> "PlannerToolCapabilityProjection":
        unsigned = self.model_dump(mode="json", exclude={"projection_digest"})
        if canonical_sha256(unsigned) != self.projection_digest:
            raise ValueError("planner_tool_capability_digest_mismatch")
        if tuple(row.source_route for row in self.evidence_routes) != (
            "reviewed_first",
            "local_only",
            "external_required",
        ):
            raise ValueError("evidence_route_capabilities_incomplete_or_unordered")
        return self


def _stream_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_columns(
    connection: sqlite3.Connection,
    *,
    table: str,
    required: set[str],
) -> None:
    columns = {
        str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")
    }
    missing = sorted(required.difference(columns))
    if missing:
        raise PlannerToolCapabilityError(
            f"planner_capability_schema_missing:{table}:{','.join(missing)}"
        )


def derive_planner_tool_capabilities(
    *,
    sqlite_path: str | Path,
    expected_mart_sha256: str,
    snapshot_id: str,
) -> PlannerToolCapabilityProjection:
    """Derive a deterministic capability envelope without mutating the mart."""

    path = Path(sqlite_path).expanduser().resolve(strict=True)
    expected = expected_mart_sha256.strip().lower()
    if len(expected) != 64 or any(char not in "0123456789abcdef" for char in expected):
        raise PlannerToolCapabilityError("expected_mart_sha256_invalid")
    actual = _stream_sha256(path)
    if actual != expected:
        raise PlannerToolCapabilityError("planner_capability_mart_sha256_mismatch")
    if not snapshot_id.strip():
        raise PlannerToolCapabilityError("planner_capability_snapshot_id_required")

    uri = f"file:{path.as_posix()}?mode=ro"
    try:
        connection = sqlite3.connect(uri, uri=True)
        connection.row_factory = sqlite3.Row
        _require_columns(
            connection,
            table="company_fact_observations",
            required={"ticker", "metric_id", "period_role", "accepted_at"},
        )
        _require_columns(
            connection,
            table="metric_definitions",
            required={"metric_id", "unit_family", "formula"},
        )

        observed = connection.execute(
            """
            SELECT metric_id, ticker, period_role
            FROM company_fact_observations
            GROUP BY metric_id, ticker, period_role
            ORDER BY metric_id, ticker, period_role
            """
        ).fetchall()
        tickers_by_metric: dict[str, list[str]] = {}
        roles_by_metric: dict[str, set[str]] = {}
        for row in observed:
            ticker_list = tickers_by_metric.setdefault(str(row["metric_id"]), [])
            if str(row["ticker"]) not in ticker_list:
                ticker_list.append(str(row["ticker"]))
            roles_by_metric.setdefault(str(row["metric_id"]), set()).add(str(row["period_role"]))
        supported_tickers = tuple(
            sorted({ticker for values in tickers_by_metric.values() for ticker in values})
        )
        if not supported_tickers:
            raise PlannerToolCapabilityError("planner_capability_mart_empty")

        metric_rows = connection.execute(
            """
            SELECT metric_id, unit_family, formula
            FROM metric_definitions
            ORDER BY metric_id
            """
        ).fetchall()
        metrics = tuple(
            FinancialMetricCapability(
                metric_id=str(row["metric_id"]),
                unit_family=str(row["unit_family"]),
                availability=(
                    "derived_at_query_time"
                    if row["formula"] is not None
                    else "direct_observation"
                ),
                formula=str(row["formula"]) if row["formula"] is not None else None,
                observed_tickers=tuple(tickers_by_metric.get(str(row["metric_id"]), ())),
                observed_period_roles=tuple(sorted(roles_by_metric.get(str(row["metric_id"]), ()))),
            )
            for row in metric_rows
        )
        if not metrics:
            raise PlannerToolCapabilityError("planner_capability_metric_definitions_empty")

        observed_roles = {
            str(row[0])
            for row in connection.execute(
                "SELECT DISTINCT period_role FROM company_fact_observations"
            )
        }
        unexpected_roles = sorted(observed_roles.difference(_CANONICAL_GRANULARITIES))
        if unexpected_roles:
            raise PlannerToolCapabilityError(
                "planner_capability_unexpected_period_roles:"
                + ",".join(unexpected_roles)
            )
        granularities = tuple(
            role for role in _CANONICAL_GRANULARITIES if role in observed_roles
        )
        if not granularities:
            raise PlannerToolCapabilityError("planner_capability_granularities_empty")

        latest_raw = connection.execute(
            "SELECT MAX(accepted_at) FROM company_fact_observations"
        ).fetchone()[0]
        if not isinstance(latest_raw, str) or not latest_raw.strip():
            raise PlannerToolCapabilityError("planner_capability_accepted_at_missing")
        try:
            latest = datetime.fromisoformat(latest_raw.replace("Z", "+00:00"))
        except ValueError as exc:
            raise PlannerToolCapabilityError(
                "planner_capability_accepted_at_invalid"
            ) from exc
        if latest.tzinfo is None:
            raise PlannerToolCapabilityError(
                "planner_capability_accepted_at_timezone_missing"
            )
        latest_through = latest.astimezone(timezone.utc).isoformat()
    except sqlite3.Error as exc:
        raise PlannerToolCapabilityError("planner_capability_sqlite_read_failed") from exc
    finally:
        if "connection" in locals():
            connection.close()

    unsigned = {
        "schema_version": PLANNER_TOOL_CAPABILITY_SCHEMA_VERSION,
        "snapshot_id": snapshot_id.strip(),
        "mart_sha256": actual,
        "data_cutoff_kind": "latest_through_observation_accepted_at",
        "data_latest_through_accepted_at": latest_through,
        "point_in_time_claimed": False,
        "finance": FinancialToolCapability(
            supported_tickers=supported_tickers,
            metrics=metrics,
            canonical_granularities=granularities,
            date_format="YYYY-MM-DD",
            latest_query_rule=(
                "omit_period_bounds_and_fiscal_years_for_latest_available_observations"
            ),
            maximum_fiscal_year_count=4,
            non_capabilities=_NON_CAPABILITIES,
            derived_metric_rule=(
                "derived_metrics_are_computed_by_the_existing_fact_executor_and_may_return_typed_gap_when_inputs_do_not_align"
            ),
        ).model_dump(mode="json"),
        "evidence_routes": [
            {
                "source_route": "reviewed_first",
                "semantics": (
                    "Search reviewed Evidence first; if none is available, return frozen local retrieval candidates. Do not escalate externally."
                ),
                "candidate_is_not_evidence": True,
            },
            {
                "source_route": "local_only",
                "semantics": (
                    "Search only the frozen local knowledge package and return retrieval candidates, never reviewed Evidence."
                ),
                "candidate_is_not_evidence": True,
            },
            {
                "source_route": "external_required",
                "semantics": (
                    "Use external discovery and bounded capture; captured or discovered material remains a candidate until a separate Evidence-admission step."
                ),
                "candidate_is_not_evidence": True,
            },
        ],
    }
    return PlannerToolCapabilityProjection.model_validate_json(
        json.dumps(
            {**unsigned, "projection_digest": canonical_sha256(unsigned)},
            ensure_ascii=False,
            allow_nan=False,
        )
    )
