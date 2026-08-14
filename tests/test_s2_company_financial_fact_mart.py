from __future__ import annotations

from dataclasses import replace
from datetime import date
import hashlib
import json
from pathlib import Path
import sys


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


def test_open_period_uses_one_current_interim_filing_cohort(tmp_path: Path) -> None:
    metrics = (_metric("revenue"),)
    rows = (
        _observation("OBS-Q1", "revenue", "43842000000"),
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
    first = _observation("OBS-A", "revenue", "43842000000")
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
            / "configs/financial_facts/fin_ia_0_1_3_s2_company_financial_fact_mart_result_v1_0.json"
        ).read_text(encoding="utf-8")
    )

    assert result["status"] == "s2_company_financial_fact_mart_engineering_pass"
    assert result["qrel_evaluation"]["strata"] == {
        "current_interim": {"qrel_count": 15, "exact_match_count": 15},
        "latest_fiscal_year": {"qrel_count": 9, "exact_match_count": 9},
    }
    assert result["mutation_evaluation"]["all_pass"] is True
    assert result["acceptance"]["candidate_or_metric_row_grants_numeric_authority"] is False


def _canonical_sha(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
