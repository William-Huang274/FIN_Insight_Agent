from __future__ import annotations

import zipfile
from pathlib import Path

from sec_agent.capital_macro_pack import build_capital_macro_pack
from sec_agent.capital_macro_source_adapters import (
    CAPITAL_MACRO_SOURCE_ADAPTER_SCHEMA_VERSION,
    adapt_public_source_rows,
    adapt_sec_capital_text_rows,
    build_capital_macro_source_adapter,
    merge_capital_macro_source_adapter_state,
    parse_sec_13f_bulk_zip,
)


def test_sec_capital_text_adapter_promotes_only_parser_complete_rows() -> None:
    result = adapt_sec_capital_text_rows(
        [
            {
                "ticker": "NVDA",
                "source_id": "nvda_10k_debt_note",
                "chunk_id": "nvda_debt_note_1",
                "form_type": "10-K",
                "snippet": "The company issued an aggregate principal amount of $1.25 billion in 2.85% senior notes due April 1, 2030.",
            },
            {
                "ticker": "TSLA",
                "source_id": "tsla_424b5",
                "form_type": "424B5",
                "filing_date": "2026-05-01",
                "snippet": "Tesla announced an offering of $2.0 billion of common stock.",
            },
            {
                "ticker": "AAPL",
                "source_id": "aapl_form4",
                "form_type": "4",
                "insider_name": "Jane Executive",
                "transaction_code": "S",
                "transaction_date": "2026-05-10",
                "transaction_shares": "1000",
                "transaction_price": "200.00",
            },
            {
                "ticker": "MSFT",
                "source_id": "msft_debt_note_incomplete",
                "form_type": "10-K",
                "snippet": "The company has senior notes outstanding and debt maturities disclosed in the note.",
            },
        ]
    )
    rows = result["capital_ownership_rows"]
    pack = build_capital_macro_pack({"run_id": "unit-k5-text", "capital_ownership_rows": rows})

    assert {row["object_type"] for row in rows} == {"DebtInstrument", "EquityOffering", "InsiderTransaction"}
    assert pack["status"] == "pass"
    assert pack["summary"]["debt_instrument_count"] == 1
    assert pack["summary"]["equity_offering_count"] == 1
    assert pack["summary"]["insider_transaction_count"] == 1
    assert any(gap["target_source"] == "sec_debt_footnote" for gap in result["source_gaps"])


def test_sec_capital_text_adapter_does_not_promote_generic_10k_offering_language() -> None:
    result = adapt_sec_capital_text_rows(
        [
            {
                "ticker": "AAPL",
                "source_id": "aapl_10k_item1",
                "chunk_id": "aapl_generic_offering_text",
                "form_type": "10-K",
                "filing_date": "2026-10-30",
                "snippet": "The company offers common stock compensation plans and had $10.0 billion of share repurchases.",
            }
        ]
    )

    assert result["capital_ownership_rows"] == []
    assert not any(gap["target_source"] == "sec_offering" for gap in result["source_gaps"])


def test_sec_debt_parser_requires_local_relation_and_skips_issue_price_percent() -> None:
    result = adapt_sec_capital_text_rows(
        [
            {
                "ticker": "A",
                "source_id": "agilent_10k_debt_note",
                "chunk_id": "agilent_2030_notes",
                "form_type": "10-K",
                "snippet": (
                    "On June 4, 2020, we issued an aggregate principal amount of $500 million in senior notes "
                    "(\"2030 senior notes\"). The 2030 senior notes were issued at 99.812% of their principal amount. "
                    "The 2030 senior notes will mature on June 4, 2030, and bear interest at a fixed rate of 2.10% per annum."
                ),
            },
            {
                "ticker": "BAD",
                "source_id": "bad_mixed_chunk",
                "chunk_id": "bad_mixed_chunk",
                "form_type": "10-K",
                "snippet": (
                    "The company had $1.5 billion of liquidity. The 2031 senior notes were issued at 99.812% "
                    "of their principal amount. The notes will mature on March 12, 2031."
                ),
            },
        ]
    )

    debt_rows = [row for row in result["capital_ownership_rows"] if row["object_type"] == "DebtInstrument"]
    assert len(debt_rows) == 1
    assert debt_rows[0]["company_id"] == "A"
    assert debt_rows[0]["coupon"] == "2.10%"
    assert debt_rows[0]["principal"] == "500"


def test_sec_credit_facility_parser_prefers_named_facility_amount() -> None:
    result = adapt_sec_capital_text_rows(
        [
            {
                "ticker": "A",
                "source_id": "agilent_10k_credit_note",
                "chunk_id": "agilent_credit_facility",
                "form_type": "10-K",
                "snippet": (
                    "During the year, we paid $72 million in contingent consideration. Short-term Debt Credit Facilities. "
                    "On June 7, 2023, we entered into a new credit agreement with a group of financial institutions "
                    "which provides for a $1.5 billion five-year unsecured credit facility that will expire on June 7, 2028."
                ),
            }
        ]
    )

    facility_rows = [row for row in result["capital_ownership_rows"] if row["object_type"] == "CreditFacility"]
    assert len(facility_rows) == 1
    assert facility_rows[0]["facility_size"] == "1.5"
    assert facility_rows[0]["maturity_date"] == "2028-06-07"


def test_sec_debt_parser_rejects_outstanding_total_mixed_with_repayment_note() -> None:
    result = adapt_sec_capital_text_rows(
        [
            {
                "ticker": "AMAT",
                "source_id": "amat_10k_debt_note",
                "chunk_id": "amat_outstanding_mixed",
                "form_type": "10-K",
                "snippet": (
                    "We used net proceeds to repay the outstanding $700 million in aggregate principal amount "
                    "of our 3.900% senior unsecured notes due October 1, 2025. "
                    "We had senior unsecured notes in the aggregate principal amount of $6.5 billion outstanding."
                ),
            }
        ]
    )

    assert not [row for row in result["capital_ownership_rows"] if row["object_type"] == "DebtInstrument"]


def test_sec_debt_parser_accepts_zero_coupon_convertible_notes() -> None:
    result = adapt_sec_capital_text_rows(
        [
            {
                "ticker": "ABNB",
                "source_id": "abnb_10k_convertible_note",
                "chunk_id": "abnb_zero_coupon_note",
                "form_type": "10-K",
                "snippet": (
                    "On March 8, 2021, the Company issued $2.0 billion aggregate principal amount "
                    "of 0% convertible senior notes due March 15, 2026."
                ),
            }
        ]
    )

    debt_rows = [row for row in result["capital_ownership_rows"] if row["object_type"] == "DebtInstrument"]
    assert len(debt_rows) == 1
    assert debt_rows[0]["coupon"] == "0%"


def test_sec_credit_facility_parser_rejects_available_under_amount() -> None:
    result = adapt_sec_capital_text_rows(
        [
            {
                "ticker": "AIG",
                "source_id": "aig_credit_note",
                "chunk_id": "aig_available_under_facility",
                "form_type": "10-K",
                "snippet": (
                    "As of December 31, 2023, a total of $4.5 billion remained available under the Facility. "
                    "Corebridge maintains a committed, revolving syndicated credit facility with aggregate commitments "
                    "to provide unsecured revolving loans and standby letters of credit of up to $2.5 billion. "
                    "The Corebridge Facility is scheduled to expire in May 2027."
                ),
            }
        ]
    )

    facility_rows = [row for row in result["capital_ownership_rows"] if row["object_type"] == "CreditFacility"]
    assert len(facility_rows) == 1
    assert facility_rows[0]["facility_size"] == "2.5"


def test_parse_sec_13f_bulk_zip_maps_lagged_positions_to_pack_input(tmp_path: Path) -> None:
    archive_path = tmp_path / "unit_13f.zip"
    _write_13f_fixture_zip(archive_path)

    result = parse_sec_13f_bulk_zip(
        archive_path,
        target_companies=[{"ticker": "AAPL", "company_name": "Apple Inc."}],
        max_positions=10,
    )
    pack = build_capital_macro_pack({"run_id": "unit-k5-13f", "capital_ownership_rows": result["capital_ownership_rows"]})

    assert len(result["capital_ownership_rows"]) == 1
    assert pack["status"] == "pass"
    position = pack["ownership_positions"][0]
    assert position["company_id"] == "AAPL"
    assert position["investor_id"] == "Example Capital LLC"
    assert position["not_realtime_flag"] is True
    assert position["lag_days"] == "45"
    assert position["claim_scope"] == "lagged_ownership_context_only"


def test_public_source_adapter_maps_macro_vertical_objects_and_blocks_unbound_leads() -> None:
    result = adapt_public_source_rows(
        [
            {
                "record_id": "fred-fedfunds-2026-05",
                "source_id": "fred_api",
                "provider": "FRED",
                "record_type": "macro_time_series_observation",
                "series_id": "FEDFUNDS",
                "metric_name": "Federal funds effective rate",
                "value": "4.33",
                "unit": "percent",
                "observation_date": "2026-05-01",
            },
            {
                "record_id": "eia-unavailable",
                "source_id": "eia_open_data",
                "record_type": "macro_time_series_observation",
                "series_id": "EIA.TEST",
                "metric_name": "EIA unavailable value",
                "value": "Not Available",
                "period": "2026-05",
            },
            {
                "record_id": "openfda-abbv-1",
                "source_id": "openfda_api",
                "record_type": "fda_product_status_record",
                "ticker": "ABBV",
                "external_id": "NDA010021",
                "attributes": {"product_names": ["PLACIDYL"], "sponsor_name": "ABBVIE"},
                "as_of_date": "2026-06-11",
            },
            {
                "record_id": "openalex-unbound",
                "source_id": "openalex_api",
                "record_type": "research_work_lead_record",
                "external_name": "Semiconductor research work",
                "as_of_date": "2026-06-11",
            },
        ],
        target_companies=[{"ticker": "JPM", "company_name": "JPMorgan Chase", "sector": "Financials"}],
    )
    pack = build_capital_macro_pack(
        {
            "run_id": "unit-k6-public",
            "macro_driver_rows": result["macro_driver_rows"],
            "macro_exposure_rows": result["macro_exposure_rows"],
            "vertical_official_object_rows": result["vertical_official_object_rows"],
        }
    )

    assert pack["status"] == "pass"
    assert pack["summary"]["macro_driver_count"] == 1
    assert pack["summary"]["company_exposure_edge_count"] == 1
    assert pack["summary"]["vertical_official_object_count"] == 1
    assert any(gap["reason"] == "macro_driver_required_fields_missing_or_value_unavailable" for gap in result["source_gaps"])
    assert any(gap["reason"] == "research_work_lead_record_requires_company_or_product_binding" for gap in result["source_gaps"])


def test_capital_macro_source_adapter_payload_is_consumed_by_pack() -> None:
    adapter = build_capital_macro_source_adapter(
        {
            "run_id": "unit-adapter",
            "target_companies": [{"ticker": "JPM", "company_name": "JPMorgan Chase", "sector": "Financials"}],
            "public_source_normalized_records": [
                {
                    "record_id": "fred-fedfunds-2026-05",
                    "source_id": "fred_api",
                    "provider": "FRED",
                    "record_type": "macro_time_series_observation",
                    "series_id": "FEDFUNDS",
                    "metric_name": "Federal funds effective rate",
                    "value": "4.33",
                    "unit": "percent",
                    "observation_date": "2026-05-01",
                }
            ],
        }
    )
    state = merge_capital_macro_source_adapter_state({"run_id": "unit-adapter"}, adapter)
    pack = build_capital_macro_pack(state)
    direct_pack = build_capital_macro_pack({"run_id": "unit-adapter-direct", "capital_macro_source_adapter": adapter})

    assert adapter["schema_version"] == CAPITAL_MACRO_SOURCE_ADAPTER_SCHEMA_VERSION
    assert adapter["summary"]["macro_driver_row_count"] == 1
    assert pack["summary"]["macro_driver_count"] == 1
    assert direct_pack["summary"]["macro_driver_count"] == 1


def _write_13f_fixture_zip(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "COVERPAGE.tsv",
            "\n".join(
                [
                    "ACCESSION_NUMBER\tREPORTCALENDARORQUARTER\tFILINGMANAGER_NAME",
                    "0000000000-26-000001\t31-MAR-2026\tExample Capital LLC",
                ]
            )
            + "\n",
        )
        archive.writestr(
            "SUBMISSION.tsv",
            "\n".join(
                [
                    "ACCESSION_NUMBER\tFILING_DATE\tSUBMISSIONTYPE\tCIK\tPERIODOFREPORT",
                    "0000000000-26-000001\t15-MAY-2026\t13F-HR\t0000000000\t31-MAR-2026",
                ]
            )
            + "\n",
        )
        archive.writestr(
            "INFOTABLE.tsv",
            "\n".join(
                [
                    "ACCESSION_NUMBER\tINFOTABLE_SK\tNAMEOFISSUER\tTITLEOFCLASS\tCUSIP\tFIGI\tVALUE\tSSHPRNAMT\tSSHPRNAMTTYPE",
                    "0000000000-26-000001\t1\tAPPLE INC\tCOM\t037833100\t\t250000\t1000000\tSH",
                    "0000000000-26-000001\t2\tUNMAPPED INC\tCOM\t000000000\t\t10\t1\tSH",
                ]
            )
            + "\n",
        )
