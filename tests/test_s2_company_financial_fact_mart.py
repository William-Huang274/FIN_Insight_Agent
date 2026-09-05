from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from financial_facts import (
    CompanyFactMartPolicy,
    CompanyFactObservation,
    CompanySourceBinding,
    FactLookup,
    MetricDefinition,
    execute_fact_lookup,
    execute_typed_fact_request,
    parse_company_source,
    write_company_fact_mart,
)
from retrieval.route_compiler import TypedFactRequest
from retrieval.query_plan import canonical_digest
from scripts.data_retrieval.build_s2_company_financial_fact_mart import (
    PROTECTED_RESULT_OUTPUTS,
    _compose_outer_result,
    _validated_result_output,
    _validated_unsigned_build_result,
)
from apps.workbench.backend.application.research_retrieval_service import (
    ResearchRetrievalPrincipal,
    ResearchRetrievalService,
)


def _policy(*, metrics: tuple[MetricDefinition, ...]) -> CompanyFactMartPolicy:
    return CompanyFactMartPolicy(
        recorded_at="2026-08-13",
        research_as_of="2026-08-06",
        minimum_period_end="2022-01-01",
        allowed_forms=("10-K", "10-Q"),
        sources=(),
        metrics=metrics,
        acceptance_qrels=(),
        authority={
            "raw_capture_digest_required": True,
            "accepted_at_required": True,
            "preserve_all_vintages": True,
            "fact_signal_context_mixed_table_forbidden": True,
            "typed_conflict_fails_closed": True,
        },
    )


def _metric(
    metric_id: str,
    *,
    unit_family: str = "currency",
    formula: str | None = None,
) -> MetricDefinition:
    return MetricDefinition(
        metric_id=metric_id,
        unit_family=unit_family,
        concepts=() if formula else (("us-gaap", metric_id),),
        allowed_units=() if formula else ("USD",),
        formula=formula,
    )


def _observation(
    observation_id: str,
    metric_id: str,
    value: str,
    *,
    accepted_at: str = "2026-06-09T20:11:41+00:00",
    accession: str = "0001571996-26-000030",
    concept: str | None = None,
    period_role: str = "quarter_discrete",
    period_start: str = "2026-01-31",
    period_end: str = "2026-05-01",
    fiscal_year: int = 2027,
    fiscal_period: str = "Q1",
) -> CompanyFactObservation:
    return CompanyFactObservation(
        observation_id=observation_id,
        ticker="DELL",
        cik="0001571996",
        legal_name="Dell Technologies Inc.",
        metric_id=metric_id,
        unit_family="currency",
        taxonomy="us-gaap",
        concept=concept or metric_id,
        concept_priority=0,
        value_decimal=value,
        unit="USD",
        period_start=period_start,
        period_end=period_end,
        duration_days=91,
        period_role=period_role,
        fiscal_year=fiscal_year,
        fiscal_period=fiscal_period,
        reported_fiscal_year=fiscal_year,
        reported_fiscal_period=fiscal_period,
        form="10-Q" if period_role != "fiscal_year" else "10-K",
        accession_number=accession,
        filed_at=accepted_at[:10],
        accepted_at=accepted_at,
        frame=None,
        primary_document="dell-20260501.htm",
        citation_url="https://www.sec.gov/Archives/example",
        companyfacts_ref="capture/companyfacts.json",
        companyfacts_sha256="a" * 64,
        submissions_ref="capture/submissions.json",
        submissions_sha256="b" * 64,
        captured_at="2026-08-06T03:51:44+00:00",
    )


def _lookup(
    metric_id: str,
    *,
    research_as_of: str = "2026-08-06",
    granularity: str = "quarter_discrete",
) -> FactLookup:
    return FactLookup(
        fact_request_id=f"TEST::{metric_id}",
        ticker="DELL",
        metric_id=metric_id,
        research_as_of=research_as_of,
        period={
            "start_date": "2026-01-31",
            "end_date": "2026-05-01",
            "fiscal_years": [2027],
            "selection_mode": "exact_period_end",
        },
        granularity=granularity,
        requested_unit="reported_source_unit",
    )


def test_exact_lookup_is_point_in_time_and_preserves_vintages(tmp_path: Path) -> None:
    metrics = (_metric("revenue"),)
    older = _observation(
        "OBS-OLD",
        "revenue",
        "40000000000",
        accepted_at="2026-05-20T20:00:00+00:00",
        accession="0001571996-26-000020",
    )
    latest = _observation("OBS-LATEST", "revenue", "43842000000")
    sqlite_path = tmp_path / "facts.sqlite"
    write_company_fact_mart(
        sqlite_path,
        observations=(older, latest),
        metrics=metrics,
        policy=_policy(metrics=metrics),
    )

    before = execute_fact_lookup(
        sqlite_path,
        _lookup("revenue", research_as_of="2026-06-01"),
    )
    after = execute_fact_lookup(sqlite_path, _lookup("revenue"))

    assert before.status == "resolved"
    assert before.facts[0].value_decimal == "40000000000"
    assert before.facts[0].accession_numbers == ("0001571996-26-000020",)
    assert after.status == "resolved"
    assert after.facts[0].value_decimal == "43842000000"
    assert len(after.facts[0].source_digests) == 2


@pytest.mark.parametrize("explicit_null_start", [False, True])
def test_exact_period_without_start_ignores_unrelated_latest_filing_cohort(
    tmp_path: Path, explicit_null_start: bool,
) -> None:
    metrics = (_metric("revenue"),)
    rows = (
        _observation("OBS-Q1", "revenue", "43842000000"),
        _observation(
            "OBS-PRIOR-FY", "revenue", "113538000000",
            accepted_at="2026-03-16T20:00:00+00:00",
            accession="0001571996-26-000008", period_role="fiscal_year",
            period_start="2025-02-01", period_end="2026-01-30",
            fiscal_year=2026, fiscal_period="FY",
        ),
    )
    sqlite_path = tmp_path / "facts.sqlite"
    write_company_fact_mart(sqlite_path, observations=rows, metrics=metrics, policy=_policy(metrics=metrics))
    period = {"end_date": "2026-05-01", "selection_mode": "exact_period_end"}
    if explicit_null_start:
        period["start_date"] = None
    lookup = replace(_lookup("revenue"), period=period)
    result = execute_fact_lookup(sqlite_path, lookup)
    assert result.status == "resolved"
    assert [(fact.period_end, fact.value_decimal) for fact in result.facts] == [("2026-05-01", "43842000000")]
    assert execute_fact_lookup(sqlite_path, replace(lookup, research_as_of="2026-06-01")).status == "typed_gap"
    assert execute_fact_lookup(sqlite_path, replace(lookup, period={**period, "end_date": "2026-04-30"})).status == "typed_gap"


def test_direct_period_selection_exact_does_not_fall_back_but_latest_does(
    tmp_path: Path,
) -> None:
    metrics = (_metric("revenue"),)
    rows = (
        _observation(
            "OBS-Q1-REV",
            "revenue",
            "200",
            accepted_at="2026-05-20T20:00:00+00:00",
            accession="0001571996-26-000020",
        ),
        _observation(
            "OBS-Q2-REV",
            "revenue",
            "240",
            accepted_at="2026-08-20T20:00:00+00:00",
            accession="0001571996-26-000040",
            period_start="2026-05-02",
            period_end="2026-07-31",
            fiscal_period="Q2",
        ),
    )
    sqlite_path = tmp_path / "facts.sqlite"
    write_company_fact_mart(
        sqlite_path,
        observations=rows,
        metrics=metrics,
        policy=_policy(metrics=metrics),
    )
    boundary = {
        "start_date": "2026-01-31",
        "end_date": "2026-06-30",
        "fiscal_years": [2027],
    }
    base = _lookup("revenue", research_as_of="2026-09-30")

    exact = execute_fact_lookup(
        sqlite_path,
        replace(
            base,
            fact_request_id="TEST::DIRECT-EXACT",
            period={**boundary, "selection_mode": "exact_period_end"},
        ),
    )
    latest = execute_fact_lookup(
        sqlite_path,
        replace(
            base,
            fact_request_id="TEST::DIRECT-LATEST",
            period={**boundary, "selection_mode": "latest_on_or_before"},
        ),
    )
    missing_mode = execute_fact_lookup(
        sqlite_path,
        replace(
            base,
            fact_request_id="TEST::DIRECT-MISSING-MODE",
            period=boundary,
        ),
    )

    assert exact.status == "typed_gap"
    assert exact.typed_gap["gap_code"] == (
        "typed_fact_not_found_for_as_of_and_period"
    )
    assert latest.status == "resolved"
    assert [(fact.period_end, fact.value_decimal) for fact in latest.facts] == [
        ("2026-05-01", "200")
    ]
    assert missing_mode.status == "typed_gap"
    assert missing_mode.typed_gap == {
        "gap_code": "typed_fact_period_selection_mode_required",
        "supported_selection_modes": [
            "exact_period_end",
            "latest_on_or_before",
        ],
    }


def test_invalid_or_incomplete_period_selection_mode_fails_closed(
    tmp_path: Path,
) -> None:
    metrics = (_metric("revenue"),)
    sqlite_path = tmp_path / "facts.sqlite"
    write_company_fact_mart(
        sqlite_path,
        observations=(_observation("OBS-REV", "revenue", "200"),),
        metrics=metrics,
        policy=_policy(metrics=metrics),
    )
    base = _lookup("revenue")

    missing = execute_fact_lookup(
        sqlite_path,
        replace(
            base,
            period={
                key: value
                for key, value in base.period.items()
                if key != "selection_mode"
            },
        ),
    )
    invalid = execute_fact_lookup(
        sqlite_path,
        replace(
            base,
            period={**base.period, "selection_mode": "nearest"},
        ),
    )
    missing_exact_end = execute_fact_lookup(
        sqlite_path,
        replace(
            base,
            period={
                "start_date": "2026-01-31",
                "end_date": None,
                "fiscal_years": [2027],
                "selection_mode": "exact_period_end",
            },
        ),
    )

    assert missing.status == "typed_gap"
    assert missing.facts == ()
    assert missing.typed_gap == {
        "gap_code": "typed_fact_period_selection_mode_required",
        "supported_selection_modes": [
            "exact_period_end",
            "latest_on_or_before",
        ],
    }
    assert invalid.status == "typed_gap"
    assert invalid.facts == ()
    assert invalid.typed_gap == {
        "gap_code": "typed_fact_period_selection_mode_invalid",
        "selection_mode": "nearest",
        "supported_selection_modes": [
            "exact_period_end",
            "latest_on_or_before",
        ],
    }
    assert missing_exact_end.status == "typed_gap"
    assert missing_exact_end.facts == ()
    assert missing_exact_end.typed_gap == {
        "gap_code": "typed_fact_exact_period_end_required"
    }


def test_open_period_uses_one_current_interim_filing_cohort(tmp_path: Path) -> None:
    metrics = (_metric("revenue"),)
    rows = (
        _observation("OBS-Q1", "revenue", "43842000000"),
        _observation(
            "OBS-Q1-COMPARABLE-ORIGIN",
            "revenue",
            "23378000000",
            accepted_at="2025-05-29T20:00:00+00:00",
            accession="0001571996-25-000011",
            period_start="2025-02-01",
            period_end="2025-05-02",
            fiscal_year=2026,
            fiscal_period="Q1",
        ),
        _observation(
            "OBS-Q1-COMPARABLE",
            "revenue",
            "23378000000",
            period_start="2025-02-01",
            period_end="2025-05-02",
            fiscal_year=2026,
            fiscal_period="Q1",
        ),
        _observation(
            "OBS-STALE-YTD",
            "revenue",
            "80159000000",
            accepted_at="2025-11-20T20:00:00+00:00",
            accession="0001571996-25-000099",
            period_role="fiscal_ytd",
            period_start="2025-02-01",
            period_end="2025-10-31",
            fiscal_year=2026,
            fiscal_period="Q3",
        ),
        _observation(
            "OBS-FY",
            "revenue",
            "113538000000",
            accepted_at="2026-03-16T20:00:00+00:00",
            accession="0001571996-26-000008",
            period_role="fiscal_year",
            period_start="2025-02-01",
            period_end="2026-01-30",
            fiscal_year=2026,
            fiscal_period="FY",
        ),
    )
    sqlite_path = tmp_path / "facts.sqlite"
    write_company_fact_mart(
        sqlite_path,
        observations=rows,
        metrics=metrics,
        policy=_policy(metrics=metrics),
    )
    lookup = FactLookup(
        fact_request_id="TEST::CURRENT-SERIES",
        ticker="DELL",
        metric_id="revenue",
        research_as_of="2026-08-06",
        period={
            "start_date": None,
            "end_date": "2026-08-06",
            "fiscal_years": [2026, 2027],
            "selection_mode": "latest_on_or_before",
        },
        granularity="quarter_and_fiscal_year",
        requested_unit="reported_source_unit",
    )

    result = execute_fact_lookup(sqlite_path, lookup)

    assert result.status == "resolved"
    assert {fact.period_role for fact in result.facts} == {
        "quarter_discrete",
        "fiscal_year",
    }
    assert {
        (fact.fiscal_year, fact.fiscal_period, fact.value_decimal)
        for fact in result.facts
        if fact.period_role == "quarter_discrete"
    } == {
        (2027, "Q1", "43842000000"),
        (2026, "Q1", "23378000000"),
    }
    assert all(fact.period_end != "2025-10-31" for fact in result.facts)


def test_latest_vintage_numeric_conflict_fails_closed(tmp_path: Path) -> None:
    metrics = (_metric("revenue"),)
    first = replace(
        _observation("OBS-A", "revenue", "43842000000"),
        # The source parser may link same-vintage concept rows while choosing
        # one physical-period successor.  Equal-time disagreement must still
        # remain visible to the conflict gate.
        superseded_by_observation_id="OBS-B",
    )
    second = replace(
        _observation(
            "OBS-B",
            "revenue",
            "43843000000",
            concept="RevenueFromContractWithCustomerExcludingAssessedTax",
        ),
        concept_priority=1,
    )
    sqlite_path = tmp_path / "facts.sqlite"
    write_company_fact_mart(
        sqlite_path,
        observations=(first, second),
        metrics=metrics,
        policy=_policy(metrics=metrics),
    )

    result = execute_fact_lookup(sqlite_path, _lookup("revenue"))

    assert result.status == "typed_conflict"
    assert result.facts == ()
    assert result.typed_conflict["conflict_code"] == (
        "authoritative_numeric_fact_conflict"
    )


def test_contemporaneous_period_identity_rejects_later_comparable_relabels(
    tmp_path: Path,
) -> None:
    metrics = (_metric("net_income"),)
    contemporaneous_q2 = _observation(
        "OBS-Q2-CONTEMPORANEOUS",
        "net_income",
        "1583000000",
        accepted_at="2025-03-20T23:20:23+00:00",
        accession="0000723125-25-000009",
        period_start="2024-11-29",
        period_end="2025-02-27",
        fiscal_year=2025,
        fiscal_period="Q2",
    )
    later_q3_copy = _observation(
        "OBS-Q2-LATER-Q3-COPY",
        "net_income",
        "1583000000",
        accepted_at="2025-06-25T22:50:42+00:00",
        accession="0000723125-25-000021",
        period_start="2024-11-29",
        period_end="2025-02-27",
        fiscal_year=2025,
        fiscal_period="Q3",
    )
    later_q2_copy = _observation(
        "OBS-Q2-LATER-Q2-COPY",
        "net_income",
        "1583000000",
        accepted_at="2026-03-18T23:00:06+00:00",
        accession="0000723125-26-000006",
        period_start="2024-11-29",
        period_end="2025-02-27",
        fiscal_year=2025,
        fiscal_period="Q2",
    )
    comparable_q3_origin = _observation(
        "OBS-Q3-COMPARABLE-ORIGIN",
        "net_income",
        "1885000000",
        accepted_at="2025-06-25T22:50:42+00:00",
        accession="0000723125-25-000021",
        period_start="2025-02-28",
        period_end="2025-05-29",
        fiscal_year=2025,
        fiscal_period="Q3",
    )
    comparable_q3 = _observation(
        "OBS-Q3-COMPARABLE",
        "net_income",
        "1885000000",
        accepted_at="2026-06-24T22:59:46+00:00",
        accession="0000723125-26-000015",
        period_start="2025-02-28",
        period_end="2025-05-29",
        fiscal_year=2025,
        fiscal_period="Q3",
    )
    current_q3 = _observation(
        "OBS-Q3-CURRENT",
        "net_income",
        "28243000000",
        accepted_at="2026-06-24T22:59:46+00:00",
        accession="0000723125-26-000015",
        period_start="2026-02-27",
        period_end="2026-05-28",
        fiscal_year=2026,
        fiscal_period="Q3",
    )
    sqlite_path = tmp_path / "facts.sqlite"
    write_company_fact_mart(
        sqlite_path,
        observations=(
            contemporaneous_q2,
            later_q3_copy,
            later_q2_copy,
            comparable_q3_origin,
            comparable_q3,
            current_q3,
        ),
        metrics=metrics,
        policy=_policy(metrics=metrics),
    )

    after_wrong_copy = execute_fact_lookup(
        sqlite_path,
        FactLookup(
            fact_request_id="TEST::MU-Q2-AFTER-WRONG-COPY",
            ticker="DELL",
            metric_id="net_income",
            research_as_of="2025-12-31",
            period={
                "start_date": "2024-11-29",
                "end_date": "2025-02-27",
                "fiscal_years": [2025],
                "selection_mode": "exact_period_end",
            },
            granularity="quarter_discrete",
            requested_unit="reported_source_unit",
        ),
    )
    after_same_identity_copy = execute_fact_lookup(
        sqlite_path,
        FactLookup(
            fact_request_id="TEST::MU-Q2-AFTER-SAME-IDENTITY-COPY",
            ticker="DELL",
            metric_id="net_income",
            research_as_of="2026-08-06",
            period={
                "start_date": "2024-11-29",
                "end_date": "2025-02-27",
                "fiscal_years": [2025],
                "selection_mode": "exact_period_end",
            },
            granularity="quarter_discrete",
            requested_unit="reported_source_unit",
        ),
    )
    current_series = execute_fact_lookup(
        sqlite_path,
        FactLookup(
            fact_request_id="TEST::MU-CURRENT-NET-INCOME",
            ticker="DELL",
            metric_id="net_income",
            research_as_of="2026-08-06",
            period={
                "start_date": "2024-09-01",
                "end_date": "2026-08-06",
                "fiscal_years": [2025, 2026],
                "selection_mode": "latest_on_or_before",
            },
            granularity="quarter_and_fiscal_year",
            requested_unit="reported_source_unit",
        ),
    )

    assert after_wrong_copy.status == "resolved"
    assert after_wrong_copy.facts[0].fiscal_period == "Q2"
    assert after_wrong_copy.facts[0].source_observation_ids == (
        "OBS-Q2-CONTEMPORANEOUS",
    )
    assert after_same_identity_copy.status == "resolved"
    assert after_same_identity_copy.facts[0].fiscal_period == "Q2"
    assert after_same_identity_copy.facts[0].source_observation_ids == (
        "OBS-Q2-LATER-Q2-COPY",
    )
    assert current_series.status == "resolved"
    assert {
        (
            fact.fiscal_year,
            fact.fiscal_period,
            fact.period_start,
            fact.period_end,
        )
        for fact in current_series.facts
    } == {
        (2026, "Q3", "2026-02-27", "2026-05-28"),
        (2025, "Q3", "2025-02-28", "2025-05-29"),
    }


def test_multi_vintage_period_identity_is_stable_at_every_research_as_of(
    tmp_path: Path,
) -> None:
    metrics = (_metric("net_income"),)
    rows = (
        _observation(
            "OBS-Q1-ORIGIN",
            "net_income",
            "-195000000",
            accepted_at="2022-12-22T17:38:24+00:00",
            period_start="2022-09-02",
            period_end="2022-12-01",
            fiscal_year=2023,
            fiscal_period="Q1",
        ),
        _observation(
            "OBS-Q1-AS-Q2-COPY",
            "net_income",
            "-195000000",
            accepted_at="2023-03-29T20:48:21+00:00",
            period_start="2022-09-02",
            period_end="2022-12-01",
            fiscal_year=2022,
            fiscal_period="Q2",
        ),
        _observation(
            "OBS-Q1-AS-Q3-COPY",
            "net_income",
            "-195000000",
            accepted_at="2023-06-29T19:34:20+00:00",
            period_start="2022-09-02",
            period_end="2022-12-01",
            fiscal_year=2022,
            fiscal_period="Q3",
        ),
        _observation(
            "OBS-Q1-LATER-SAME-IDENTITY",
            "net_income",
            "-196000000",
            accepted_at="2023-12-21T18:05:34+00:00",
            period_start="2022-09-02",
            period_end="2022-12-01",
            fiscal_year=2023,
            fiscal_period="Q1",
        ),
    )
    sqlite_path = tmp_path / "facts.sqlite"
    write_company_fact_mart(
        sqlite_path,
        observations=rows,
        metrics=metrics,
        policy=_policy(metrics=metrics),
    )

    def lookup(research_as_of: str):
        return execute_fact_lookup(
            sqlite_path,
            FactLookup(
                fact_request_id=f"TEST::MU-Q1::{research_as_of}",
                ticker="DELL",
                metric_id="net_income",
                research_as_of=research_as_of,
                period={
                    "start_date": "2022-09-02",
                    "end_date": "2022-12-01",
                    "fiscal_years": [2022, 2023],
                    "selection_mode": "exact_period_end",
                },
                granularity="quarter_discrete",
                requested_unit="reported_source_unit",
            ),
        )

    for research_as_of in ("2022-12-31", "2023-04-01", "2023-07-01"):
        result = lookup(research_as_of)
        assert result.status == "resolved"
        assert (result.facts[0].fiscal_year, result.facts[0].fiscal_period) == (
            2023,
            "Q1",
        )
        assert result.facts[0].value_decimal == "-195000000"
        assert result.facts[0].source_observation_ids == ("OBS-Q1-ORIGIN",)

    latest = lookup("2024-01-01")
    assert latest.status == "resolved"
    assert (latest.facts[0].fiscal_year, latest.facts[0].fiscal_period) == (
        2023,
        "Q1",
    )
    assert latest.facts[0].value_decimal == "-196000000"
    assert latest.facts[0].source_observation_ids == (
        "OBS-Q1-LATER-SAME-IDENTITY",
    )


def test_period_identity_without_timely_origin_fails_closed(tmp_path: Path) -> None:
    metrics = (_metric("net_income"),)
    rows = (
        _observation(
            "OBS-LATE-Q1",
            "net_income",
            "10",
            accepted_at="2025-07-01T00:00:00+00:00",
            period_start="2025-01-01",
            period_end="2025-03-31",
            fiscal_year=2025,
            fiscal_period="Q1",
        ),
        _observation(
            "OBS-LATE-Q2",
            "net_income",
            "10",
            accepted_at="2025-10-01T00:00:00+00:00",
            period_start="2025-01-01",
            period_end="2025-03-31",
            fiscal_year=2025,
            fiscal_period="Q2",
        ),
    )
    sqlite_path = tmp_path / "facts.sqlite"
    write_company_fact_mart(
        sqlite_path,
        observations=rows,
        metrics=metrics,
        policy=_policy(metrics=metrics),
    )

    result = execute_fact_lookup(
        sqlite_path,
        FactLookup(
            fact_request_id="TEST::AMBIGUOUS-PERIOD-IDENTITY",
            ticker="DELL",
            metric_id="net_income",
            research_as_of="2025-12-31",
            period={
                "start_date": "2025-01-01",
                "end_date": "2025-03-31",
                "fiscal_years": [2025],
                "selection_mode": "exact_period_end",
            },
            granularity="quarter_discrete",
            requested_unit="reported_source_unit",
        ),
    )

    assert result.status == "typed_conflict"
    assert result.facts == ()
    assert result.typed_conflict["conflicts"][0]["code"] == (
        "typed_fact_physical_period_identity_ambiguous"
    )


def test_unanimous_late_copies_do_not_create_period_identity_authority(
    tmp_path: Path,
) -> None:
    metrics = (_metric("net_income"),)
    rows = (
        _observation(
            "OBS-LATE-FY-COPY-1",
            "net_income",
            "10",
            accepted_at="2026-03-01T00:00:00+00:00",
            period_start="2025-01-01",
            period_end="2025-03-31",
            fiscal_year=2026,
            fiscal_period="FY",
        ),
        _observation(
            "OBS-LATE-FY-COPY-2",
            "net_income",
            "10",
            accepted_at="2026-06-01T00:00:00+00:00",
            period_start="2025-01-01",
            period_end="2025-03-31",
            fiscal_year=2026,
            fiscal_period="FY",
        ),
    )
    sqlite_path = tmp_path / "facts.sqlite"
    write_company_fact_mart(
        sqlite_path,
        observations=rows,
        metrics=metrics,
        policy=_policy(metrics=metrics),
    )

    result = execute_fact_lookup(
        sqlite_path,
        FactLookup(
            fact_request_id="TEST::UNVERIFIED-PERIOD-IDENTITY",
            ticker="DELL",
            metric_id="net_income",
            research_as_of="2026-08-01",
            period={
                "start_date": "2025-01-01",
                "end_date": "2025-03-31",
                "fiscal_years": [2026],
                "selection_mode": "exact_period_end",
            },
            granularity="quarter_discrete",
            requested_unit="reported_source_unit",
        ),
    )

    assert result.status == "typed_conflict"
    assert result.facts == ()
    assert result.typed_conflict["conflicts"][0]["code"] == (
        "typed_fact_physical_period_identity_source_unavailable"
    )


def test_requested_or_automatic_comparable_identity_conflict_is_not_dropped(
    tmp_path: Path,
) -> None:
    metrics = (_metric("revenue"),)
    current = _observation(
        "OBS-CURRENT-Q1-ORIGIN",
        "revenue",
        "200",
    )
    unverified_comparable = replace(
        _observation(
            "OBS-COMPARABLE-Q1-LATE-COPY",
            "revenue",
            "100",
            period_start="2025-02-01",
            period_end="2025-05-02",
            fiscal_year=2026,
            fiscal_period="Q1",
        ),
        accession_number=current.accession_number,
    )
    sqlite_path = tmp_path / "facts.sqlite"
    write_company_fact_mart(
        sqlite_path,
        observations=(current, unverified_comparable),
        metrics=metrics,
        policy=_policy(metrics=metrics),
    )

    def run(fiscal_years: list[int]):
        return execute_fact_lookup(
            sqlite_path,
            FactLookup(
                fact_request_id="TEST::CURRENT-WITH-UNVERIFIED-COMPARABLE",
                ticker="DELL",
                metric_id="revenue",
                research_as_of="2026-08-06",
                period={
                    "start_date": None,
                    "end_date": "2026-08-06",
                    "fiscal_years": fiscal_years,
                    "selection_mode": "latest_on_or_before",
                },
                granularity="quarter_discrete",
                requested_unit="reported_source_unit",
            ),
        )

    for result in (run([2026, 2027]), run([])):
        assert result.status == "typed_conflict"
        assert result.facts == ()
        conflicts = result.typed_conflict["conflicts"]
        assert len(conflicts) == 1
        assert conflicts[0]["code"] == (
            "typed_fact_physical_period_identity_source_unavailable"
        )
        assert conflicts[0]["period_end"] == "2025-05-02"
        assert conflicts[0]["candidate_fiscal_identities"] == [
            {"fiscal_year": 2026, "fiscal_period": "Q1"}
        ]


def test_derived_formula_propagates_requested_comparable_identity_conflict(
    tmp_path: Path,
) -> None:
    metrics = (
        _metric("revenue"),
        _metric("gross_profit"),
        _metric(
            "gross_margin",
            unit_family="percentage",
            formula="gross_profit / revenue * 100",
        ),
    )
    current_revenue = _observation(
        "OBS-CURRENT-REV-ORIGIN",
        "revenue",
        "200",
    )
    current_gross_profit = _observation(
        "OBS-CURRENT-GP-ORIGIN",
        "gross_profit",
        "50",
    )
    unverified_comparable = replace(
        _observation(
            "OBS-COMPARABLE-REV-LATE-COPY",
            "revenue",
            "100",
            period_start="2025-02-01",
            period_end="2025-05-02",
            fiscal_year=2026,
            fiscal_period="Q1",
        ),
        accession_number=current_revenue.accession_number,
    )
    sqlite_path = tmp_path / "facts.sqlite"
    write_company_fact_mart(
        sqlite_path,
        observations=(
            current_revenue,
            current_gross_profit,
            unverified_comparable,
        ),
        metrics=metrics,
        policy=_policy(metrics=metrics),
    )

    result = execute_fact_lookup(
        sqlite_path,
        FactLookup(
            fact_request_id="TEST::DERIVED-WITH-UNVERIFIED-COMPARABLE",
            ticker="DELL",
            metric_id="gross_margin",
            research_as_of="2026-08-06",
            period={
                "start_date": None,
                "end_date": "2026-08-06",
                "fiscal_years": [2026, 2027],
                "selection_mode": "latest_on_or_before",
            },
            granularity="quarter_discrete",
            requested_unit="reported_source_unit",
        ),
    )

    assert result.status == "typed_conflict"
    assert result.typed_gap is None
    propagated = result.typed_conflict["conflicts"][0]
    assert propagated["code"] == "derived_formula_input_conflict"
    assert propagated["input_metric"] == "revenue"
    assert propagated["input_conflicts"][0]["period_end"] == "2025-05-02"
    assert propagated["input_conflicts"][0]["code"] == (
        "typed_fact_physical_period_identity_source_unavailable"
    )


def test_v1_5_requested_comparable_successor_receipt_is_canonical() -> None:
    path = (
        ROOT
        / "configs/financial_facts/"
        "fin_ia_0_1_3_s2_mu_physical_period_identity_successor_result_v1_5.json"
    )
    result = json.loads(path.read_text(encoding="utf-8"))
    unsigned = {
        key: value for key, value in result.items() if key != "result_digest"
    }

    assert result["result_digest"] == canonical_digest(unsigned)
    assert result["status"] == (
        "s2_mu_requested_comparable_conflict_successor_pass"
    )
    assert all(result["checks"].values())
    assert result["checks"][
        "explicit_requested_comparable_identity_conflict_propagates"
    ] is True
    assert result["checks"][
        "automatic_comparable_identity_conflict_propagates"
    ] is True
    assert result["checks"][
        "derived_requested_comparable_conflict_propagates"
    ] is True
    assert result["calls"] == {"network": 0, "provider": 0, "model": 0}
    assert result["authority"]["s2_stage_qualification_authorized"] is False


def test_derived_margin_and_fcf_require_aligned_source_period(tmp_path: Path) -> None:
    metrics = (
        _metric("revenue"),
        _metric("gross_profit"),
        _metric("operating_cash_flow"),
        _metric("capital_expenditures"),
        _metric("gross_margin", unit_family="percentage", formula="gross_profit / revenue * 100"),
        _metric("free_cash_flow", formula="operating_cash_flow - capital_expenditures"),
    )
    rows = (
        _observation("OBS-REV", "revenue", "200"),
        _observation("OBS-GP", "gross_profit", "50"),
        _observation("OBS-OCF", "operating_cash_flow", "40"),
        _observation("OBS-CAPEX", "capital_expenditures", "10"),
    )
    sqlite_path = tmp_path / "facts.sqlite"
    write_company_fact_mart(
        sqlite_path,
        observations=rows,
        metrics=metrics,
        policy=_policy(metrics=metrics),
    )

    margin = execute_fact_lookup(sqlite_path, _lookup("gross_margin"))
    fcf = execute_fact_lookup(sqlite_path, _lookup("free_cash_flow"))

    assert margin.status == "resolved"
    assert margin.facts[0].value_decimal == "25"
    assert margin.facts[0].unit == "percent"
    assert margin.facts[0].formula_trace["input_metrics"] == [
        "gross_profit",
        "revenue",
    ]
    assert fcf.status == "resolved"
    assert fcf.facts[0].value_decimal == "30"


def test_derived_period_selection_exact_does_not_fall_back_but_latest_does(
    tmp_path: Path,
) -> None:
    metrics = (
        _metric("revenue"),
        _metric("gross_profit"),
        _metric(
            "gross_margin",
            unit_family="percentage",
            formula="gross_profit / revenue * 100",
        ),
    )
    rows = (
        _observation(
            "OBS-Q1-REV",
            "revenue",
            "200",
            accepted_at="2026-05-20T20:00:00+00:00",
            accession="0001571996-26-000020",
        ),
        _observation(
            "OBS-Q1-GP",
            "gross_profit",
            "50",
            accepted_at="2026-05-20T20:00:00+00:00",
            accession="0001571996-26-000020",
        ),
        _observation(
            "OBS-Q2-REV",
            "revenue",
            "240",
            accepted_at="2026-08-20T20:00:00+00:00",
            accession="0001571996-26-000040",
            period_start="2026-05-02",
            period_end="2026-07-31",
            fiscal_period="Q2",
        ),
        _observation(
            "OBS-Q2-GP",
            "gross_profit",
            "72",
            accepted_at="2026-08-20T20:00:00+00:00",
            accession="0001571996-26-000040",
            period_start="2026-05-02",
            period_end="2026-07-31",
            fiscal_period="Q2",
        ),
    )
    sqlite_path = tmp_path / "facts.sqlite"
    write_company_fact_mart(
        sqlite_path,
        observations=rows,
        metrics=metrics,
        policy=_policy(metrics=metrics),
    )
    boundary = {
        "start_date": "2026-01-31",
        "end_date": "2026-06-30",
        "fiscal_years": [2027],
    }
    base = _lookup("gross_margin", research_as_of="2026-09-30")

    exact = execute_fact_lookup(
        sqlite_path,
        replace(
            base,
            fact_request_id="TEST::DERIVED-EXACT",
            period={**boundary, "selection_mode": "exact_period_end"},
        ),
    )
    latest = execute_fact_lookup(
        sqlite_path,
        replace(
            base,
            fact_request_id="TEST::DERIVED-LATEST",
            period={**boundary, "selection_mode": "latest_on_or_before"},
        ),
    )

    assert exact.status == "typed_gap"
    assert exact.typed_gap["gap_code"] == "derived_formula_input_missing"
    assert latest.status == "resolved"
    assert [(fact.period_end, fact.value_decimal) for fact in latest.facts] == [
        ("2026-05-01", "25")
    ]


def test_derived_formula_propagates_input_identity_conflict(tmp_path: Path) -> None:
    metrics = (
        _metric("revenue"),
        _metric("gross_profit"),
        _metric(
            "gross_margin",
            unit_family="percentage",
            formula="gross_profit / revenue * 100",
        ),
    )
    rows = (
        _observation("OBS-GP-ORIGIN", "gross_profit", "50"),
        _observation(
            "OBS-REV-LATE-Q1",
            "revenue",
            "200",
            accepted_at="2026-09-01T00:00:00+00:00",
            fiscal_period="Q1",
        ),
        _observation(
            "OBS-REV-LATE-Q2",
            "revenue",
            "200",
            accepted_at="2026-10-01T00:00:00+00:00",
            fiscal_period="Q2",
        ),
    )
    sqlite_path = tmp_path / "facts.sqlite"
    write_company_fact_mart(
        sqlite_path,
        observations=rows,
        metrics=metrics,
        policy=_policy(metrics=metrics),
    )

    result = execute_fact_lookup(
        sqlite_path,
        _lookup("gross_margin", research_as_of="2026-12-31"),
    )

    assert result.status == "typed_conflict"
    assert result.typed_gap is None
    propagated = result.typed_conflict["conflicts"][0]
    assert propagated["code"] == "derived_formula_input_conflict"
    assert propagated["input_side"] == "right"
    assert propagated["input_metric"] == "revenue"
    assert propagated["input_conflicts"][0]["code"] == (
        "typed_fact_physical_period_identity_ambiguous"
    )


def test_unrelated_period_role_cannot_create_identity_conflict(
    tmp_path: Path,
) -> None:
    metrics = (_metric("revenue"),)
    annual_copy = _observation(
        "OBS-LATE-ANNUAL-COPY",
        "revenue",
        "200",
        accepted_at="2027-06-01T00:00:00+00:00",
        period_role="fiscal_year",
        period_start="2026-01-01",
        period_end="2026-12-31",
        fiscal_year=2027,
        fiscal_period="FY",
    )
    sqlite_path = tmp_path / "facts.sqlite"
    write_company_fact_mart(
        sqlite_path,
        observations=(annual_copy,),
        metrics=metrics,
        policy=_policy(metrics=metrics),
    )

    result = execute_fact_lookup(
        sqlite_path,
        FactLookup(
            fact_request_id="TEST::NO-UNRELATED-ROLE-CONFLICT",
            ticker="DELL",
            metric_id="revenue",
            research_as_of="2027-12-31",
            period={
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
                "fiscal_years": [2027],
                "selection_mode": "exact_period_end",
            },
            granularity="quarter_discrete",
            requested_unit="reported_source_unit",
        ),
    )

    assert result.status == "typed_gap"
    assert result.typed_conflict is None
    assert result.typed_gap["gap_code"] == (
        "typed_fact_not_found_for_as_of_and_period"
    )


def test_s1_typed_fact_request_executes_against_s2_mart(tmp_path: Path) -> None:
    metrics = (_metric("revenue"),)
    sqlite_path = tmp_path / "facts.sqlite"
    write_company_fact_mart(
        sqlite_path,
        observations=(_observation("OBS-REV", "revenue", "43842000000"),),
        metrics=metrics,
        policy=_policy(metrics=metrics),
    )
    request = TypedFactRequest(
        schema_version="fin_ia_typed_fact_request_v1_0",
        fact_request_id="TFR::TEST",
        source_evidence_request_id="REQ::TEST",
        source_cell_id="CELL::TEST",
        case_key="DELL",
        subject_ticker="DELL",
        target_entity="DELL",
        metric_id="revenue",
        query_family_ids=("reported_financial_results",),
        research_as_of="2026-08-06",
        period={
            "start_date": "2026-01-31",
            "end_date": "2026-05-01",
            "fiscal_years": [2027],
            "selection_mode": "exact_period_end",
        },
        granularity="quarter_discrete",
        requested_unit="reported_source_unit",
        unit_family="currency",
        authority_domain="company_reported_exact",
        storage_route="company_financial_fact_mart",
        formula=None,
        execution_status="ready_for_typed_fact_executor",
        numeric_fact_authority=False,
    )

    result = execute_typed_fact_request(sqlite_path, request)

    assert result.status == "resolved"
    assert result.facts[0].numeric_fact_authority is True
    assert result.fact_request_is_not_numeric_fact is True


def test_current_request_runtime_executes_company_fact_sibling(
    tmp_path: Path,
) -> None:
    metrics = (_metric("revenue"),)
    sqlite_path = tmp_path / "facts.sqlite"
    write_company_fact_mart(
        sqlite_path,
        observations=(_observation("OBS-REV", "revenue", "43842000000"),),
        metrics=metrics,
        policy=_policy(metrics=metrics),
    )
    service = ResearchRetrievalService(
        snapshot=json.loads(
            (
                ROOT
                / "configs/runtime/fin_ia_0_1_3_current_retrieval_snapshot_v1_0.json"
            ).read_text(encoding="utf-8")
        ),
        kernel=json.loads(
            (
                ROOT
                / "configs/retrieval/fin_ia_0_1_3_s1_financial_research_kernel_v1_0.json"
            ).read_text(encoding="utf-8")
        ),
        route_policy=json.loads(
            (
                ROOT
                / "configs/retrieval/fin_ia_0_1_3_s1c_query_object_fact_route_policy_v1_0.json"
            ).read_text(encoding="utf-8")
        ),
        company_financial_fact_mart_path=sqlite_path,
    )
    request = {
        "schema_version": "fin_ia_evidence_request_v1_0",
        "request_id": "REQ::DELL-S2-RUNTIME",
        "cell_id": "CELL::DELL-RESULTS",
        "requester_role": "research_lead",
        "evidence_domain": "financial_research",
        "case_key": "DELL",
        "subject_ticker": "DELL",
        "research_as_of": "2026-08-06",
        "target_entities": ["DELL"],
        "requested_facet_ids": ["reported_results"],
        "metric_intents": ["revenue"],
        "product_intents": ["AI-optimized servers"],
        "period": {
            "start_date": "2026-01-31",
            "end_date": "2026-05-01",
            "fiscal_years": [2027],
        },
        "granularity": "quarter_discrete",
        "unit": "reported_source_unit",
        "acceptable_sources": ["10-K", "10-Q", "8-K"],
        "acceptable_proxy": False,
        "forbidden_proxy": ["unbound industry demand"],
        "stop_condition": "return candidates, typed facts, or typed gaps",
        "clarification_policy": "return_typed_gap",
    }

    projection = service.execute_request(
        "DELL",
        request,
        ResearchRetrievalPrincipal(
            mode="current",
            permissions=frozenset({"current_product:read"}),
        ),
    )

    assert projection["schema_version"] == (
        "fin_ia_request_scoped_retrieval_projection_v1_2"
    )
    assert projection["summary"]["typed_fact_store_ready_count"] == 1
    assert projection["summary"]["typed_fact_resolved_count"] == 1
    assert projection["summary"]["typed_fact_gap_count"] == 0
    assert projection["typed_fact_results"][0]["facts"][0][
        "value_decimal"
    ] == "43842000000"
    assert projection["typed_fact_results"][0]["facts"][0][
        "numeric_fact_authority"
    ] is True


def test_sec_parser_separates_q3_discrete_from_fiscal_ytd(tmp_path: Path) -> None:
    source_root = tmp_path / "capture"
    source_root.mkdir()
    accession = "0000723125-26-000015"
    companyfacts = {
        "cik": 723125,
        "entityName": "Micron Technology, Inc.",
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {
                        "USD": [
                            {
                                "start": "2025-08-29",
                                "end": "2026-05-28",
                                "val": 78959000000,
                                "accn": accession,
                                "fy": 2026,
                                "fp": "Q3",
                                "form": "10-Q",
                                "filed": "2026-06-25"
                            },
                            {
                                "start": "2026-02-27",
                                "end": "2026-05-28",
                                "val": 41456000000,
                                "accn": accession,
                                "fy": 2026,
                                "fp": "Q3",
                                "form": "10-Q",
                                "filed": "2026-06-25",
                                "frame": "CY2026Q2"
                            }
                        ]
                    }
                }
            }
        }
    }
    submissions = {
        "filings": {
            "recent": {
                "accessionNumber": [accession],
                "filingDate": ["2026-06-25"],
                "acceptanceDateTime": ["2026-06-24T22:59:46.000Z"],
                "reportDate": ["2026-05-28"],
                "form": ["10-Q"],
                "primaryDocument": ["mu-20260528.htm"]
            }
        }
    }
    companyfacts_path = source_root / "companyfacts.json"
    submissions_path = source_root / "submissions.json"
    companyfacts_path.write_text(json.dumps(companyfacts), encoding="utf-8")
    submissions_path.write_text(json.dumps(submissions), encoding="utf-8")
    companyfacts_sha = _canonical_sha(companyfacts)
    submissions_sha = _canonical_sha(submissions)
    companyfacts_metadata = {
        "ticker": "MU",
        "fact_source": "sec_companyfacts",
        "sha256": companyfacts_sha,
        "downloaded_at_utc": "2026-08-06T00:00:00+00:00"
    }
    submissions_metadata = {
        "ticker": "MU",
        "fact_source": "sec_submissions",
        "sha256": submissions_sha,
        "downloaded_at_utc": "2026-08-06T00:00:01+00:00"
    }
    (source_root / "companyfacts.metadata.json").write_text(
        json.dumps(companyfacts_metadata), encoding="utf-8"
    )
    (source_root / "submissions.metadata.json").write_text(
        json.dumps(submissions_metadata), encoding="utf-8"
    )
    source = CompanySourceBinding(
        ticker="MU",
        cik="0000723125",
        legal_name="Micron Technology, Inc.",
        companyfacts_ref="capture/companyfacts.json",
        companyfacts_metadata_ref="capture/companyfacts.metadata.json",
        companyfacts_sha256=companyfacts_sha,
        submissions_ref="capture/submissions.json",
        submissions_metadata_ref="capture/submissions.metadata.json",
        submissions_sha256=submissions_sha,
    )
    metrics = (
        MetricDefinition(
            metric_id="revenue",
            unit_family="currency",
            concepts=(("us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax"),),
            allowed_units=("USD",),
        ),
    )
    policy = replace(_policy(metrics=metrics), sources=(source,))

    rows, summary = parse_company_source(policy, source, repository_root=tmp_path)

    assert summary["accepted_observations"] == 2
    assert {(row.period_role, row.value_decimal) for row in rows} == {
        ("quarter_discrete", "41456000000"),
        ("fiscal_ytd", "78959000000"),
    }


def test_tracked_real_build_closes_annual_and_current_interim_qrels() -> None:
    result = json.loads(
        (
            ROOT
            / "configs/financial_facts/fin_ia_0_1_3_s2_company_financial_fact_mart_result_v1_1.json"
        ).read_text(encoding="utf-8")
    )

    assert result["status"] == "s2_company_financial_fact_mart_engineering_pass"
    assert result["qrel_evaluation"]["strata"] == {
        "current_interim": {"qrel_count": 15, "exact_match_count": 15},
        "latest_fiscal_year": {"qrel_count": 9, "exact_match_count": 9},
    }
    assert result["mutation_evaluation"]["all_pass"] is True
    assert result["acceptance"]["candidate_or_metric_row_grants_numeric_authority"] is False


def test_outer_result_digest_does_not_overwrite_an_inner_digest_dependency() -> None:
    inner_unsigned = {
        "schema_version": "fin_ia_s2_company_financial_fact_mart_build_result_v1_0",
        "status": "company_financial_fact_mart_materialized_acceptance_pending",
        "counts": {"observations": 1},
    }
    inner = {
        **inner_unsigned,
        "result_digest": canonical_digest(inner_unsigned),
    }

    outer = _compose_outer_result(
        inner,
        {
            "status": "s2_company_financial_fact_mart_engineering_pass",
            "acceptance": {"all_qrels_exact": True},
        },
    )

    assert "result_digest" not in _validated_unsigned_build_result(inner)
    assert outer["result_digest"] == canonical_digest(
        {key: value for key, value in outer.items() if key != "result_digest"}
    )
    with pytest.raises(
        ValueError,
        match="company_fact_mart_build_result_digest_invalid",
    ):
        _validated_unsigned_build_result({**inner, "counts": {"observations": 2}})
    with pytest.raises(ValueError, match="outer_result_digest_field_forbidden"):
        _compose_outer_result(inner, {"result_digest": "forbidden"})
    with pytest.raises(
        ValueError,
        match="outer_result_reserved_field_override_forbidden",
    ):
        _compose_outer_result(inner, {"counts": {"observations": 999}})


@pytest.mark.parametrize("protected_output", sorted(PROTECTED_RESULT_OUTPUTS))
def test_builder_cannot_overwrite_protected_results(
    protected_output: Path,
) -> None:
    with pytest.raises(
        ValueError,
        match="protected_s2_result_output_forbidden",
    ):
        _validated_result_output(protected_output)


def test_current_transcript_objects_cannot_enter_the_s2_numeric_fact_mart() -> None:
    policy = json.loads(
        (
            ROOT
            / "configs/financial_facts/fin_ia_0_1_3_s2_company_financial_fact_mart_policy_v1_0.json"
        ).read_text(encoding="utf-8")
    )
    source_manifest = json.loads(
        (
            ROOT
            / "configs/retrieval/fin_ia_0_1_3_s1b_current_source_object_manifest_v1_1.json"
        ).read_text(encoding="utf-8")
    )
    mart_result = json.loads(
        (
            ROOT
            / "configs/financial_facts/fin_ia_0_1_3_s2_company_financial_fact_mart_result_v1_1.json"
        ).read_text(encoding="utf-8")
    )

    assert any(
        row.get("source_type") == "EARNINGS_CALL_TRANSCRIPT"
        for row in source_manifest["sources"]
    )
    assert policy["allowed_forms"] == ["10-K", "10-Q"]
    assert all(
        set(row) >= {
            "companyfacts_ref",
            "companyfacts_sha256",
            "submissions_ref",
            "submissions_sha256",
        }
        and "transcript" not in json.dumps(row, ensure_ascii=False).casefold()
        for row in policy["source_bindings"]
    )

    assert mart_result["source_summary"]["source_count"] == 3
    assert {
        row["ticker"] for row in mart_result["source_summary"]["sources"]
    } == {"DELL", "MU", "NVDA"}
    assert "transcript" not in json.dumps(
        mart_result["source_summary"], ensure_ascii=False
    ).casefold()
    assert (
        mart_result["authority"]["candidate_or_metric_row_grants_numeric_authority"]
        is False
    )


def _canonical_sha(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
