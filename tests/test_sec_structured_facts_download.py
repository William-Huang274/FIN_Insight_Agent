from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "data_expansion" / "download_sec_structured_facts.py"
SPEC = importlib.util.spec_from_file_location("download_sec_structured_facts", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _companyfacts_plan_row() -> dict:
    return {
        "plan_id": "FINFACT::SEC::MSFT::SEC_COMPANYFACTS",
        "ticker": "MSFT",
        "issuer_id": "0000789019",
        "cik": "0000789019",
        "cik10": "0000789019",
        "company_name": "Microsoft Corporation",
        "fact_source": "sec_companyfacts",
        "source_family": "sec_companyfacts_structured_fact",
        "source_tier": "company_reported_structured_fact",
        "source_url": "https://data.sec.gov/api/xbrl/companyfacts/CIK0000789019.json",
    }


def test_normalize_companyfacts_filters_years_forms_and_classifies_revenue() -> None:
    payload = {
        "cik": 789019,
        "entityName": "MICROSOFT CORPORATION",
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "label": "Revenues",
                    "description": "Revenue from contracts with customers",
                    "units": {
                        "USD": [
                            {
                                "start": "2023-07-01",
                                "end": "2024-06-30",
                                "val": 245122000000,
                                "accn": "0000789019-24-000021",
                                "fy": 2024,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2024-07-30",
                            },
                            {
                                "start": "2021-07-01",
                                "end": "2022-06-30",
                                "val": 198270000000,
                                "accn": "old",
                                "fy": 2022,
                                "fp": "FY",
                                "form": "10-K",
                            },
                        ]
                    },
                }
            }
        },
    }

    rows = MODULE.normalize_companyfacts_payload(
        _companyfacts_plan_row(),
        payload,
        metadata={"sha256": "abc"},
        years={2024},
        forms={"10-K"},
    )

    assert len(rows) == 1
    assert rows[0]["ticker"] == "MSFT"
    assert rows[0]["concept"] == "Revenues"
    assert rows[0]["metric_family"] == "revenue"
    assert rows[0]["period_role"] == "annual"
    assert rows[0]["duration_months"] == 12
    assert rows[0]["accession_number"] == "0000789019-24-000021"
    assert rows[0]["exact_value_ledger_candidate"] is True


def test_normalize_companyfacts_infers_instant_balance_sheet_fact() -> None:
    payload = {
        "entityName": "MICROSOFT CORPORATION",
        "facts": {
            "us-gaap": {
                "Assets": {
                    "label": "Assets",
                    "units": {
                        "USD": [
                            {
                                "end": "2024-06-30",
                                "val": 512163000000,
                                "accn": "0000789019-24-000021",
                                "fy": 2024,
                                "fp": "FY",
                                "form": "10-K",
                            }
                        ]
                    },
                }
            }
        },
    }

    rows = MODULE.normalize_companyfacts_payload(_companyfacts_plan_row(), payload, years={2024}, forms={"10-K"})

    assert rows[0]["metric_family"] == "assets"
    assert rows[0]["period_role"] == "instant"
    assert rows[0]["duration_months"] is None
    assert rows[0]["metric_role"] == "point_in_time"


def test_normalize_submissions_filters_recent_rows() -> None:
    plan = {
        "plan_id": "FINFACT::SEC::MSFT::SEC_SUBMISSIONS",
        "ticker": "MSFT",
        "issuer_id": "0000789019",
        "cik": "0000789019",
        "cik10": "0000789019",
        "company_name": "Microsoft Corporation",
        "fact_source": "sec_submissions",
        "source_family": "sec_submissions_metadata",
        "source_tier": "company_reported_structured_fact",
    }
    payload = {
        "cik": "789019",
        "name": "MICROSOFT CORPORATION",
        "filings": {
            "recent": {
                "form": ["10-K", "8-K", "10-Q"],
                "filingDate": ["2024-07-30", "2024-08-01", "2024-04-25"],
                "reportDate": ["2024-06-30", "2024-08-01", "2024-03-31"],
                "accessionNumber": ["a1", "a2", "a3"],
                "primaryDocument": ["msft-20240630.htm", "8k.htm", "10q.htm"],
            }
        },
    }

    rows = MODULE.normalize_submissions_payload(plan, payload, years={2024}, forms={"10-K", "10-Q"})

    assert len(rows) == 2
    assert {row["form_type"] for row in rows} == {"10-K", "10-Q"}
    assert all(row["fiscal_year"] == 2024 for row in rows)


def test_group_sec_structured_fact_plan_rows_keeps_only_sec_api_rows() -> None:
    grouped = MODULE.group_sec_structured_fact_plan_rows(
        [
            {"ticker": "MSFT", "integration_mode": "new_sec_api_download", "fact_source": "sec_companyfacts"},
            {"ticker": "MSFT", "integration_mode": "new_sec_api_download", "fact_source": "sec_submissions"},
            {"ticker": "005930.KS", "integration_mode": "derive_from_downloaded_official_disclosure"},
        ]
    )

    assert set(grouped) == {"MSFT"}
    assert len(grouped["MSFT"]) == 2
