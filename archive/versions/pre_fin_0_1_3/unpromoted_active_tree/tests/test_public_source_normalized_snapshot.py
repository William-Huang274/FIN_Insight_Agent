from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_module():
    path = REPO_ROOT / "scripts" / "data_expansion" / "download_public_source_normalized_snapshots.py"
    spec = importlib.util.spec_from_file_location("public_source_normalized_snapshot_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_prepare_request_redacts_query_key(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setenv("FRED_API_KEY", "unit-test-secret")

    request_spec = module.prepare_request(module.COLLECTOR_PROFILES["fred_api"])

    assert request_spec["params"]["api_key"] == "unit-test-secret"
    assert "unit-test-secret" not in request_spec["logged_url"]
    assert "api_key=REDACTED" in request_spec["logged_url"]


def test_collect_source_normalizes_fred_and_redacts_response_url(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setenv("FRED_API_KEY", "unit-test-secret")

    class Response:
        url = "https://api.stlouisfed.org/fred/series/observations?series_id=FEDFUNDS&api_key=unit-test-secret"

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "observations": [
                    {
                        "date": "2026-05-01",
                        "value": "4.33",
                        "realtime_start": "2026-06-01",
                        "realtime_end": "2026-06-01",
                    }
                ]
            }

    def fake_request(method, url, params, headers, json, timeout) -> Response:
        assert method == "GET"
        assert params["api_key"] == "unit-test-secret"
        assert headers["User-Agent"].startswith("FinSight-Agent/")
        assert timeout == 3
        return Response()

    monkeypatch.setattr(module.requests, "request", fake_request)
    records = module.collect_source(
        source_id="fred_api",
        profile=module.COLLECTOR_PROFILES["fred_api"],
        plan_row={
            "source_id": "fred_api",
            "provider": "FRED",
            "source_families": ["macro_industry_indicator"],
            "claim_scope": "industry_context_only",
            "boundary_notes": "Context only.",
        },
        snapshot_id="unit_snapshot",
        as_of_date="2026-06-11",
        fetched_at="2026-06-11T00:00:00+00:00",
        timeout_s=3,
        max_records=10,
        skip_live=False,
    )

    assert len(records) == 1
    assert records[0]["record_type"] == "macro_time_series_observation"
    assert records[0]["value"] == 4.33
    assert records[0]["source_family"] == "macro_industry_indicator"
    assert "unit-test-secret" not in records[0]["api_route"]
    assert "api_key=REDACTED" in records[0]["api_route"]
    assert "attributes" not in records[0]
    assert "provider_realtime_start" in records[0]["attributes_json"]


def test_build_evidence_row_preserves_claim_boundary() -> None:
    module = _load_module()
    records = [
        {
            "source_id": "openfda_api",
            "record_type": "fda_product_status_record",
            "source_family": "official_product_status",
            "api_route": "https://api.fda.gov/drug/drugsfda.json?api_key=REDACTED",
        }
    ]

    evidence = module.build_evidence_row(
        "openfda_api",
        {"collector_line": "identity_product_disclosure", "source_family": "official_product_status"},
        {
            "provider": "openFDA",
            "source_families": ["macro_industry_indicator", "official_product_status"],
            "claim_scope": "healthcare_regulatory_context",
            "boundary_notes": "Regulatory context only.",
        },
        records,
        snapshot_id="unit_snapshot",
        as_of_date="2026-06-11",
        fetched_at="2026-06-11T00:00:00+00:00",
    )

    assert evidence["normalized_record_count"] == 1
    assert evidence["primary_source_family"] == "official_product_status"
    assert evidence["caveats"][0] == "Regulatory context only."


def test_parse_fred_graph_csv_normalizes_rows() -> None:
    module = _load_module()
    payload = "observation_date,FEDFUNDS\n2026-04-01,3.64\n2026-05-01,.\n"

    records = module.parse_fred_graph_csv(
        payload,
        {
            "source_id": "fred_graph_csv",
            "profile": {
                "collector_line": "macro_industry",
                "series_id": "FEDFUNDS",
                "unit": "percent",
                "source_policy": "context_only",
            },
            "plan_row": {"provider": "FRED", "source_families": ["macro_industry_indicator"]},
            "snapshot_id": "unit",
            "as_of_date": "2026-06-11",
            "fetched_at": "2026-06-11T00:00:00+00:00",
            "api_route": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=FEDFUNDS",
        },
    )

    assert len(records) == 1
    assert records[0]["source_id"] == "fred_graph_csv"
    assert records[0]["series_id"] == "FEDFUNDS"
    assert records[0]["value"] == 3.64


def test_parse_cms_catalog_payload_builds_dataset_records() -> None:
    module = _load_module()
    records = module.parse_cms_catalog_payload(
        {"dataset": [{"identifier": "cms-1", "title": "Provider test", "distribution": [{}, {}]}]},
        {
            "source_id": "cms_public_data",
            "profile": {"collector_line": "macro_industry", "source_policy": "context_only"},
            "plan_row": {"provider": "CMS", "source_families": ["macro_industry_indicator"]},
            "snapshot_id": "unit",
            "as_of_date": "2026-06-11",
            "fetched_at": "2026-06-11T00:00:00+00:00",
            "api_route": "https://data.cms.gov/data.json",
        },
    )

    assert len(records) == 1
    assert records[0]["record_type"] == "public_dataset_catalog_record"
    assert records[0]["identifier"] == "cms-1"
    assert "distribution_count" in records[0]["attributes_json"]


def test_parse_census_trade_payload_builds_context_observations() -> None:
    module = _load_module()
    payload = [
        ["I_COMMODITY", "I_COMMODITY_LDESC", "GEN_VAL_MO", "CTY_CODE", "CTY_NAME", "time"],
        ["8542", "Integrated circuits", "12345", "5520", "VIETNAM", "2026-03"],
    ]

    records = module.parse_census_trade_payload(
        payload,
        {
            "source_id": "usitc_dataweb_and_trade",
            "profile": {"collector_line": "macro_industry", "source_policy": "context_only"},
            "plan_row": {"provider": "Census", "source_families": ["macro_industry_indicator"]},
            "snapshot_id": "unit",
            "as_of_date": "2026-06-11",
            "fetched_at": "2026-06-11T00:00:00+00:00",
            "api_route": "https://api.census.gov/data/timeseries/intltrade/imports/hs",
        },
    )

    assert len(records) == 1
    assert records[0]["record_type"] == "trade_context_observation"
    assert records[0]["series_id"] == "CENSUS_TRADE_IMPORTS_HS::8542"
    assert records[0]["value"] == 12345.0


def test_parse_openalex_wikidata_and_common_crawl_records() -> None:
    module = _load_module()
    base_context = {
        "profile": {"collector_line": "lead_discovery", "source_policy": "lead_only"},
        "plan_row": {"provider": "provider", "source_families": ["external_event_lead"]},
        "snapshot_id": "unit",
        "as_of_date": "2026-06-11",
        "fetched_at": "2026-06-11T00:00:00+00:00",
        "api_route": "https://example.test",
    }

    openalex = module.parse_openalex_payload(
        {
            "results": [
                {
                    "id": "https://openalex.org/W1",
                    "display_name": "Semiconductor test",
                    "publication_year": 2026,
                    "publication_date": "2026-01-01",
                    "cited_by_count": 7,
                    "host_venue": {"display_name": "Journal"},
                    "concepts": [{"id": "C1", "display_name": "AI", "score": 0.9}],
                }
            ]
        },
        {**base_context, "source_id": "openalex_api"},
    )
    wikidata = module.parse_wikidata_search_payload(
        {"search": [{"id": "Q312", "label": "Apple Inc.", "description": "technology company"}]},
        {**base_context, "source_id": "wikidata"},
    )
    common_crawl = module.parse_common_crawl_collinfo_payload(
        [{"id": "CC-MAIN-2026-21", "name": "May 2026", "cdx-api": "https://index.commoncrawl.org/CC-MAIN-2026-21-index"}],
        {**base_context, "source_id": "common_crawl_index"},
    )

    assert openalex[0]["record_type"] == "research_work_lead_record"
    assert openalex[0]["source_family"] == "external_event_lead"
    assert wikidata[0]["record_type"] == "alias_identifier_candidate_record"
    assert wikidata[0]["identifier"] == "Q312"
    assert common_crawl[0]["record_type"] == "crawl_index_metadata_record"


def test_parse_gdelt_yahoo_and_patentsview_records() -> None:
    module = _load_module()
    base_context = {
        "plan_row": {"provider": "provider", "source_families": ["external_event_lead"]},
        "snapshot_id": "unit",
        "as_of_date": "2026-06-11",
        "fetched_at": "2026-06-11T00:00:00+00:00",
        "api_route": "https://example.test",
    }

    gdelt = module.parse_gdelt_lastupdate_payload(
        "67647 abc http://data.gdeltproject.org/gdeltv2/20260611121500.export.CSV.zip\n",
        {
            **base_context,
            "source_id": "gdelt",
            "profile": {"collector_line": "lead_discovery", "source_policy": "event_index_only"},
        },
    )
    yahoo = module.parse_yahoo_chart_payload(
        {
            "chart": {
                "result": [
                    {
                        "meta": {"symbol": "AAPL", "currency": "USD", "shortName": "Apple"},
                        "timestamp": [1781136000],
                        "indicators": {"quote": [{"close": [200.5], "volume": [1234]}]},
                    }
                ]
            }
        },
        {
            **base_context,
            "source_id": "yahoo_chart",
            "profile": {
                "collector_line": "market_context",
                "source_policy": "provisional",
                "params": {"range": "1mo", "interval": "1d"},
            },
        },
    )
    patentsview = module.parse_patentsview_migration_payload(
        '<html><head><title>PatentsView migrating</title></head><body><a href="https://www.patentsview.org/apis">API</a></body></html>',
        {
            **base_context,
            "source_id": "patentsview_api",
            "profile": {
                "collector_line": "lead_discovery",
                "source_policy": "migration_metadata_only",
                "url": "https://www.uspto.gov/subscription-center/2026/patentsview-migrating-uspto-open-data-portal-march-20",
            },
        },
    )

    assert gdelt[0]["record_type"] == "event_data_index_record"
    assert gdelt[0]["value"] == 67647.0
    assert yahoo[0]["record_type"] == "market_price_observation"
    assert yahoo[0]["source_family"] == "market_price_snapshot"
    assert patentsview[0]["record_type"] == "patent_data_access_metadata_record"
    assert patentsview[0]["status"] == "migration_metadata_materialized"
