from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from decimal import Decimal, localcontext
from pathlib import Path
import sqlite3
from typing import Any, Mapping, Sequence

from retrieval.query_plan import canonical_digest
from retrieval.route_compiler import TypedFactRequest

from .contracts import (
    COMPANY_FACT_MART_SCHEMA_VERSION,
    NUMERIC_FACT_SCHEMA_VERSION,
    TYPED_FACT_EXECUTION_RESULT_SCHEMA_VERSION,
    NumericFact,
    TypedFactExecutionResult,
)


_ROLE_ORDER = {
    "quarter_discrete": 0,
    "fiscal_ytd": 1,
    "fiscal_year": 2,
    "instant": 3,
}
_DERIVED_FORMULAS = {
    "gross_margin": ("gross_profit", "revenue", "divide_percent"),
    "operating_margin": ("operating_income", "revenue", "divide_percent"),
    "free_cash_flow": (
        "operating_cash_flow",
        "capital_expenditures",
        "subtract",
    ),
}


@dataclass(frozen=True)
class FactLookup:
    fact_request_id: str
    ticker: str
    metric_id: str
    research_as_of: str
    period: Mapping[str, Any]
    granularity: str
    requested_unit: str
    unit_family: str | None = None


def execute_typed_fact_request(
    sqlite_path: Path,
    request: TypedFactRequest,
) -> TypedFactExecutionResult:
    if request.storage_route != "company_financial_fact_mart":
        return _gap(
            fact_request_id=request.fact_request_id,
            ticker=request.target_entity,
            metric_id=request.metric_id,
            code="typed_fact_storage_route_unsupported",
        )
    lookup = FactLookup(
        fact_request_id=request.fact_request_id,
        ticker=request.target_entity,
        metric_id=request.metric_id,
        research_as_of=request.research_as_of,
        period=request.period,
        granularity=request.granularity,
        requested_unit=request.requested_unit,
        unit_family=request.unit_family,
    )
    return execute_fact_lookup(sqlite_path, lookup)


def execute_fact_lookup(
    sqlite_path: Path,
    lookup: FactLookup,
) -> TypedFactExecutionResult:
    if not sqlite_path.is_file():
        return _gap(
            fact_request_id=lookup.fact_request_id,
            ticker=lookup.ticker,
            metric_id=lookup.metric_id,
            code="typed_fact_store_unavailable",
        )
    # sqlite3.Connection's context manager handles transactions but does not
    # close the underlying handle.  The fact mart is rebuilt atomically on
    # Windows, so readers must release the file deterministically.
    with closing(_read_only_connection(sqlite_path)) as connection:
        _verify_mart(connection)
        definition = connection.execute(
            "SELECT metric_id, unit_family, formula FROM metric_definitions "
            "WHERE metric_id = ?",
            (lookup.metric_id,),
        ).fetchone()
        if definition is None:
            return _gap(
                fact_request_id=lookup.fact_request_id,
                ticker=lookup.ticker,
                metric_id=lookup.metric_id,
                code="metric_not_in_company_fact_mart",
            )
        if lookup.unit_family and definition["unit_family"] != lookup.unit_family:
            return _gap(
                fact_request_id=lookup.fact_request_id,
                ticker=lookup.ticker,
                metric_id=lookup.metric_id,
                code="metric_unit_family_mismatch",
            )
        formula = str(definition["formula"] or "")
        if formula:
            return _execute_derived(connection, lookup, formula=formula)
        return _execute_direct(connection, lookup)


def _execute_direct(
    connection: sqlite3.Connection,
    lookup: FactLookup,
) -> TypedFactExecutionResult:
    rows = _candidate_rows(connection, lookup)
    if not rows:
        return _gap(
            fact_request_id=lookup.fact_request_id,
            ticker=lookup.ticker,
            metric_id=lookup.metric_id,
            code="typed_fact_not_found_for_as_of_and_period",
        )
    groups: dict[tuple[Any, ...], list[Mapping[str, Any]]] = {}
    for row in rows:
        groups.setdefault(
            (
                row["period_start"],
                row["period_end"],
                row["period_role"],
                row["fiscal_year"],
                row["fiscal_period"],
                row["unit"],
            ),
            [],
        ).append(row)
    resolved: list[tuple[tuple[Any, ...], list[Mapping[str, Any]]]] = []
    conflicts: list[dict[str, Any]] = []
    for key, group_rows in groups.items():
        latest_accepted = max(str(row["accepted_at"]) for row in group_rows)
        latest = [
            row for row in group_rows if str(row["accepted_at"]) == latest_accepted
        ]
        values = {str(row["value_decimal"]) for row in latest}
        if len(values) != 1:
            conflicts.append(
                {
                    "period_start": key[0],
                    "period_end": key[1],
                    "period_role": key[2],
                    "fiscal_year": key[3],
                    "fiscal_period": key[4],
                    "unit": key[5],
                    "accepted_at": latest_accepted,
                    "forms": sorted({str(row["form"]) for row in latest}),
                    "accession_numbers": sorted(
                        {str(row["accession_number"]) for row in latest}
                    ),
                    "values": sorted(values),
                    "observation_ids": sorted(
                        str(row["observation_id"]) for row in latest
                    ),
                }
            )
            continue
        resolved.append((key, latest))
    filing_cohorts = (
        _latest_filing_cohorts(connection, lookup)
        if not lookup.period.get("start_date")
        else {}
    )
    selected, selected_conflicts = _select_latest_period_roles(
        resolved,
        conflicts,
        granularity=lookup.granularity,
        filing_cohorts=filing_cohorts,
    )
    if selected_conflicts:
        return _conflict(lookup, selected_conflicts)
    if not selected:
        return _gap(
            fact_request_id=lookup.fact_request_id,
            ticker=lookup.ticker,
            metric_id=lookup.metric_id,
            code="typed_fact_period_role_not_available",
        )
    facts = tuple(
        _direct_numeric_fact(lookup, key=key, rows=group_rows)
        for key, group_rows in selected
    )
    return TypedFactExecutionResult(
        schema_version=TYPED_FACT_EXECUTION_RESULT_SCHEMA_VERSION,
        status="resolved",
        fact_request_id=lookup.fact_request_id,
        ticker=lookup.ticker,
        metric_id=lookup.metric_id,
        facts=facts,
        typed_gap=None,
        typed_conflict=None,
        fact_request_is_not_numeric_fact=True,
    )


def _execute_derived(
    connection: sqlite3.Connection,
    lookup: FactLookup,
    *,
    formula: str,
) -> TypedFactExecutionResult:
    formula_contract = _DERIVED_FORMULAS.get(lookup.metric_id)
    if formula_contract is None:
        return _gap(
            fact_request_id=lookup.fact_request_id,
            ticker=lookup.ticker,
            metric_id=lookup.metric_id,
            code="derived_formula_not_implemented",
        )
    left_metric, right_metric, operation = formula_contract
    left = _execute_direct(
        connection,
        FactLookup(
            **{
                **lookup.__dict__,
                "fact_request_id": lookup.fact_request_id + "::LEFT",
                "metric_id": left_metric,
                "unit_family": None,
            }
        ),
    )
    right = _execute_direct(
        connection,
        FactLookup(
            **{
                **lookup.__dict__,
                "fact_request_id": lookup.fact_request_id + "::RIGHT",
                "metric_id": right_metric,
                "unit_family": None,
            }
        ),
    )
    if left.status != "resolved" or right.status != "resolved":
        return _gap(
            fact_request_id=lookup.fact_request_id,
            ticker=lookup.ticker,
            metric_id=lookup.metric_id,
            code="derived_formula_input_missing",
            details={
                "formula": formula,
                "left_status": left.status,
                "right_status": right.status,
            },
        )
    left_by_period = {_fact_period_key(fact): fact for fact in left.facts}
    right_by_period = {_fact_period_key(fact): fact for fact in right.facts}
    common = sorted(
        set(left_by_period).intersection(right_by_period),
        key=lambda key: (_ROLE_ORDER.get(str(key[2]), 99), str(key[1])),
    )
    if not common:
        return _gap(
            fact_request_id=lookup.fact_request_id,
            ticker=lookup.ticker,
            metric_id=lookup.metric_id,
            code="derived_formula_period_alignment_gap",
        )
    facts: list[NumericFact] = []
    for key in common:
        left_fact = left_by_period[key]
        right_fact = right_by_period[key]
        if set(left_fact.accession_numbers) != set(right_fact.accession_numbers):
            return _conflict(
                lookup,
                [
                    {
                        "code": "derived_formula_vintage_mismatch",
                        "period": key,
                        "left_accessions": left_fact.accession_numbers,
                        "right_accessions": right_fact.accession_numbers,
                    }
                ],
            )
        left_value = Decimal(left_fact.value_decimal)
        right_value = Decimal(right_fact.value_decimal)
        if operation == "divide_percent":
            if right_value == 0:
                return _conflict(
                    lookup,
                    [{"code": "derived_formula_division_by_zero", "period": key}],
                )
            with localcontext() as context:
                context.prec = 34
                value = left_value / right_value * Decimal("100")
            unit = "percent"
        elif operation == "subtract":
            if left_fact.unit != right_fact.unit:
                return _conflict(
                    lookup,
                    [{"code": "derived_formula_unit_mismatch", "period": key}],
                )
            value = left_value - right_value
            unit = left_fact.unit
        else:
            raise ValueError("derived_formula_operation_invalid")
        identity = {
            "fact_request_id": lookup.fact_request_id,
            "metric_id": lookup.metric_id,
            "period": key,
            "value": _decimal_text(value),
            "inputs": (left_fact.numeric_fact_id, right_fact.numeric_fact_id),
        }
        facts.append(
            NumericFact(
                schema_version=NUMERIC_FACT_SCHEMA_VERSION,
                numeric_fact_id="NUMFACT::" + canonical_digest(identity)[:32],
                fact_request_id=lookup.fact_request_id,
                ticker=lookup.ticker,
                metric_id=lookup.metric_id,
                value_decimal=_decimal_text(value),
                unit=unit,
                unit_family=(
                    "percentage" if operation == "divide_percent" else "currency"
                ),
                period_start=left_fact.period_start,
                period_end=left_fact.period_end,
                period_role=left_fact.period_role,
                fiscal_year=left_fact.fiscal_year,
                fiscal_period=left_fact.fiscal_period,
                research_as_of=lookup.research_as_of,
                authority_mode="deterministically_derived_numeric_fact",
                accession_numbers=left_fact.accession_numbers,
                accepted_at=max(left_fact.accepted_at, right_fact.accepted_at),
                source_observation_ids=tuple(
                    sorted(
                        set(left_fact.source_observation_ids)
                        | set(right_fact.source_observation_ids)
                    )
                ),
                citation_urls=tuple(
                    sorted(
                        set(left_fact.citation_urls) | set(right_fact.citation_urls)
                    )
                ),
                source_digests=tuple(
                    sorted(
                        set(left_fact.source_digests) | set(right_fact.source_digests)
                    )
                ),
                formula_trace={
                    "formula": formula,
                    "operation": operation,
                    "input_numeric_fact_ids": [
                        left_fact.numeric_fact_id,
                        right_fact.numeric_fact_id,
                    ],
                    "input_metrics": [left_metric, right_metric],
                },
                numeric_fact_authority=True,
            )
        )
    return TypedFactExecutionResult(
        schema_version=TYPED_FACT_EXECUTION_RESULT_SCHEMA_VERSION,
        status="resolved",
        fact_request_id=lookup.fact_request_id,
        ticker=lookup.ticker,
        metric_id=lookup.metric_id,
        facts=tuple(facts),
        typed_gap=None,
        typed_conflict=None,
        fact_request_is_not_numeric_fact=True,
    )


def _candidate_rows(
    connection: sqlite3.Connection,
    lookup: FactLookup,
) -> list[Mapping[str, Any]]:
    clauses = [
        "current.ticker = ?",
        "current.metric_id = ?",
        "substr(current.accepted_at, 1, 10) <= ?",
        "current.period_end <= ?",
        "(current.superseded_by_observation_id IS NULL OR NOT EXISTS ("
        "SELECT 1 FROM company_fact_observations AS successor "
        "WHERE successor.observation_id = current.superseded_by_observation_id "
        "AND successor.accepted_at > current.accepted_at "
        "AND substr(successor.accepted_at, 1, 10) <= ?))",
    ]
    as_of_end = str(lookup.period.get("end_date") or lookup.research_as_of)
    params: list[Any] = [
        lookup.ticker.upper(),
        lookup.metric_id,
        lookup.research_as_of,
        min(as_of_end, lookup.research_as_of),
        lookup.research_as_of,
    ]
    start_date = lookup.period.get("start_date")
    if start_date:
        clauses.append("(current.period_start IS NULL OR current.period_start >= ?)")
        params.append(str(start_date))
    fiscal_years = lookup.period.get("fiscal_years") or ()
    if fiscal_years:
        placeholders = ",".join("?" for _ in fiscal_years)
        clauses.append(f"current.fiscal_year IN ({placeholders})")
        params.extend(int(value) for value in fiscal_years)
    query = (
        "SELECT current.* FROM company_fact_observations AS current WHERE "
        + " AND ".join(clauses)
        + " ORDER BY current.period_end, current.accepted_at, "
        "current.concept_priority, current.observation_id"
    )
    return [dict(row) for row in connection.execute(query, params).fetchall()]


def _select_latest_period_roles(
    resolved: Sequence[tuple[tuple[Any, ...], list[Mapping[str, Any]]]],
    conflicts: Sequence[Mapping[str, Any]],
    *,
    granularity: str,
    filing_cohorts: Mapping[str, str],
) -> tuple[
    list[tuple[tuple[Any, ...], list[Mapping[str, Any]]]],
    list[Mapping[str, Any]],
]:
    allowed_roles = _roles_for_granularity(granularity)
    resolved_by_role: dict[str, list[tuple[tuple[Any, ...], list[Mapping[str, Any]]]]] = {}
    for item in resolved:
        role = str(item[0][2])
        if role in allowed_roles and _rows_match_filing_cohort(
            item[1], role=role, filing_cohorts=filing_cohorts
        ):
            resolved_by_role.setdefault(role, []).append(item)
    conflict_by_role: dict[str, list[Mapping[str, Any]]] = {}
    for conflict in conflicts:
        role = str(conflict.get("period_role") or "")
        if role in allowed_roles and _conflict_matches_filing_cohort(
            conflict, role=role, filing_cohorts=filing_cohorts
        ):
            conflict_by_role.setdefault(role, []).append(conflict)
    selected: list[tuple[tuple[Any, ...], list[Mapping[str, Any]]]] = []
    selected_conflicts: list[Mapping[str, Any]] = []
    for role in sorted(allowed_roles, key=lambda value: _ROLE_ORDER.get(value, 99)):
        candidates = resolved_by_role.get(role, [])
        role_conflicts = conflict_by_role.get(role, [])
        newest_end = max(
            [str(item[0][1]) for item in candidates]
            + [str(item.get("period_end") or "") for item in role_conflicts],
            default="",
        )
        if not newest_end:
            continue
        newest_conflicts = [
            item for item in role_conflicts if str(item.get("period_end")) == newest_end
        ]
        if newest_conflicts:
            selected_conflicts.extend(newest_conflicts)
            continue
        newest_candidates = [item for item in candidates if str(item[0][1]) == newest_end]
        if len(newest_candidates) != 1:
            selected_conflicts.append(
                {
                    "code": "typed_fact_period_boundary_ambiguous",
                    "period_role": role,
                    "period_end": newest_end,
                    "candidate_periods": [item[0] for item in newest_candidates],
                }
            )
            continue
        current = newest_candidates[0]
        selected.append(current)
        if role not in {"quarter_discrete", "fiscal_ytd"}:
            continue

        # A current 10-Q normally repeats the prior-year comparable column.  It
        # is part of the same filing cohort and is the only safe basis for
        # phrases such as "year over year".  Preserve that row alongside the
        # current interim value instead of forcing S3 to compare a quarter with
        # the latest fiscal year.
        current_fiscal_year = current[0][3]
        current_fiscal_period = current[0][4]
        if not isinstance(current_fiscal_year, int) or not current_fiscal_period:
            continue
        comparable_year = current_fiscal_year - 1
        comparable_conflicts = [
            item
            for item in role_conflicts
            if item.get("fiscal_year") == comparable_year
            and item.get("fiscal_period") == current_fiscal_period
        ]
        if comparable_conflicts:
            selected_conflicts.extend(comparable_conflicts)
            continue
        comparable_candidates = [
            item
            for item in candidates
            if item[0][3] == comparable_year
            and item[0][4] == current_fiscal_period
        ]
        if len(comparable_candidates) > 1:
            selected_conflicts.append(
                {
                    "code": "typed_fact_comparable_period_ambiguous",
                    "period_role": role,
                    "fiscal_year": comparable_year,
                    "fiscal_period": current_fiscal_period,
                    "candidate_periods": [item[0] for item in comparable_candidates],
                }
            )
            continue
        if comparable_candidates:
            selected.append(comparable_candidates[0])
    return selected, selected_conflicts


def _latest_filing_cohorts(
    connection: sqlite3.Connection,
    lookup: FactLookup,
) -> dict[str, str]:
    cutoff = min(
        str(lookup.period.get("end_date") or lookup.research_as_of),
        lookup.research_as_of,
    )
    output: dict[str, str] = {}
    for form, key in (("10-Q", "interim"), ("10-K", "annual")):
        row = connection.execute(
            "SELECT accession_number, accepted_at FROM company_fact_observations "
            "WHERE ticker = ? AND form = ? AND substr(accepted_at, 1, 10) <= ? "
            "ORDER BY accepted_at DESC, accession_number DESC LIMIT 1",
            (lookup.ticker.upper(), form, cutoff),
        ).fetchone()
        if row is not None:
            output[key] = str(row["accession_number"])
    return output


def _rows_match_filing_cohort(
    rows: Sequence[Mapping[str, Any]],
    *,
    role: str,
    filing_cohorts: Mapping[str, str],
) -> bool:
    if not filing_cohorts:
        return True
    cohort_key = "annual" if role == "fiscal_year" else "interim"
    expected = filing_cohorts.get(cohort_key)
    return bool(expected) and all(
        str(row["accession_number"]) == expected for row in rows
    )


def _conflict_matches_filing_cohort(
    conflict: Mapping[str, Any],
    *,
    role: str,
    filing_cohorts: Mapping[str, str],
) -> bool:
    if not filing_cohorts:
        return True
    cohort_key = "annual" if role == "fiscal_year" else "interim"
    expected = filing_cohorts.get(cohort_key)
    accessions = {str(value) for value in conflict.get("accession_numbers") or ()}
    return bool(expected) and accessions == {expected}


def _roles_for_granularity(value: str) -> set[str]:
    normalized = value.strip().casefold()
    if normalized in _ROLE_ORDER:
        return {normalized}
    if normalized == "quarter":
        return {"quarter_discrete"}
    if normalized == "fiscal_year":
        return {"fiscal_year"}
    if normalized == "instant":
        return {"instant"}
    if normalized == "quarter_and_fiscal_year":
        return {"quarter_discrete", "fiscal_ytd", "fiscal_year", "instant"}
    return set(_ROLE_ORDER)


def _direct_numeric_fact(
    lookup: FactLookup,
    *,
    key: tuple[Any, ...],
    rows: Sequence[Mapping[str, Any]],
) -> NumericFact:
    ordered = sorted(
        rows,
        key=lambda row: (int(row["concept_priority"]), str(row["observation_id"])),
    )
    primary = ordered[0]
    identity = {
        "fact_request_id": lookup.fact_request_id,
        "ticker": lookup.ticker,
        "metric_id": lookup.metric_id,
        "value": primary["value_decimal"],
        "unit": primary["unit"],
        "period": key,
        "observations": sorted(str(row["observation_id"]) for row in ordered),
    }
    return NumericFact(
        schema_version=NUMERIC_FACT_SCHEMA_VERSION,
        numeric_fact_id="NUMFACT::" + canonical_digest(identity)[:32],
        fact_request_id=lookup.fact_request_id,
        ticker=lookup.ticker,
        metric_id=lookup.metric_id,
        value_decimal=str(primary["value_decimal"]),
        unit=str(primary["unit"]),
        unit_family=str(primary["unit_family"]),
        period_start=primary["period_start"],
        period_end=str(primary["period_end"]),
        period_role=str(primary["period_role"]),
        fiscal_year=primary["fiscal_year"],
        fiscal_period=primary["fiscal_period"],
        research_as_of=lookup.research_as_of,
        authority_mode="source_bound_company_reported_numeric_fact",
        accession_numbers=tuple(
            sorted({str(row["accession_number"]) for row in ordered})
        ),
        accepted_at=max(str(row["accepted_at"]) for row in ordered),
        source_observation_ids=tuple(
            sorted(str(row["observation_id"]) for row in ordered)
        ),
        citation_urls=tuple(sorted({str(row["citation_url"]) for row in ordered})),
        source_digests=tuple(
            sorted(
                {
                    *(
                        str(row["companyfacts_sha256"])
                        for row in ordered
                    ),
                    *(str(row["submissions_sha256"]) for row in ordered),
                }
            )
        ),
        formula_trace=None,
        numeric_fact_authority=True,
    )


def _fact_period_key(fact: NumericFact) -> tuple[Any, ...]:
    return (
        fact.period_start,
        fact.period_end,
        fact.period_role,
        fact.fiscal_year,
        fact.fiscal_period,
    )


def _gap(
    *,
    fact_request_id: str,
    ticker: str,
    metric_id: str,
    code: str,
    details: Mapping[str, Any] | None = None,
) -> TypedFactExecutionResult:
    return TypedFactExecutionResult(
        schema_version=TYPED_FACT_EXECUTION_RESULT_SCHEMA_VERSION,
        status="typed_gap",
        fact_request_id=fact_request_id,
        ticker=ticker,
        metric_id=metric_id,
        facts=(),
        typed_gap={"gap_code": code, **dict(details or {})},
        typed_conflict=None,
        fact_request_is_not_numeric_fact=True,
    )


def _conflict(
    lookup: FactLookup,
    conflicts: Sequence[Mapping[str, Any]],
) -> TypedFactExecutionResult:
    return TypedFactExecutionResult(
        schema_version=TYPED_FACT_EXECUTION_RESULT_SCHEMA_VERSION,
        status="typed_conflict",
        fact_request_id=lookup.fact_request_id,
        ticker=lookup.ticker,
        metric_id=lookup.metric_id,
        facts=(),
        typed_gap=None,
        typed_conflict={
            "conflict_code": "authoritative_numeric_fact_conflict",
            "conflicts": [dict(value) for value in conflicts],
        },
        fact_request_is_not_numeric_fact=True,
    )


def _verify_mart(connection: sqlite3.Connection) -> None:
    metadata = dict(connection.execute("SELECT key, value FROM mart_metadata"))
    if metadata.get("schema_version") != COMPANY_FACT_MART_SCHEMA_VERSION:
        raise ValueError("company_fact_mart_schema_invalid")


def _read_only_connection(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


__all__ = [
    "FactLookup",
    "execute_fact_lookup",
    "execute_typed_fact_request",
]
