from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_industry_snapshot_module():
    path = REPO_ROOT / "scripts" / "industry" / "10_download_industry_source_snapshot.py"
    spec = importlib.util.spec_from_file_location("industry_source_snapshot_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_eia_v2_source_normalizes_rows_and_redacts_key(monkeypatch) -> None:
    module = _load_industry_snapshot_module()
    monkeypatch.setenv("EIA_API_KEY", "unit-secret")

    class Response:
        url = "https://api.eia.gov/v2/total-energy/data/?frequency=monthly&api_key=unit-secret"

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "response": {
                    "total": "2",
                    "data": [
                        {
                            "period": "2026-04",
                            "msn": "TESTBUS",
                            "seriesDescription": "Test Energy Series in Trillion Btu",
                            "value": "123.4",
                            "unit": "Trillion Btu",
                        },
                        {
                            "period": "2026-04",
                            "msn": "MISSBUS",
                            "seriesDescription": "Unavailable Series",
                            "value": "Not Available",
                            "unit": "Trillion Btu",
                        },
                    ],
                }
            }

    def fake_get(endpoint: str, params: dict, timeout: int) -> Response:
        assert endpoint == "https://api.eia.gov/v2/total-energy/data/"
        assert params["api_key"] == "unit-secret"
        assert timeout == 25
        return Response()

    monkeypatch.setattr(module.requests, "get", fake_get)
    rows, evidence = module.download_eia_v2_source(
        {
            "source_family": "industry_energy_commodities",
            "provider": "EIA",
            "route_type": "eia_v2_json",
            "endpoint": "https://api.eia.gov/v2/total-energy/data/",
            "api_key_env_var": "EIA_API_KEY",
            "default_frequency": "monthly",
            "allowed_claim_types": ["energy_demand_context"],
            "params": {"frequency": "monthly", "data[0]": "value", "length": 5000},
            "dataset": {"dataset_id": "eia/total-energy/monthly", "unit": "mixed"},
        },
        as_of_date="2026-05-30",
        fetched_at="2026-05-30T00:00:00+00:00",
        timeout=25,
    )

    assert len(rows) == 1
    assert rows[0]["series_id"] == "TESTBUS"
    assert rows[0]["observation_date"] == "2026-04-01"
    assert rows[0]["value"] == 123.4
    assert rows[0]["api_route"].endswith("api_key=<redacted>")
    assert evidence["provider"] == "EIA"
    assert evidence["latest_observation_date"] == "2026-04-01"
    assert "1 non-numeric" in evidence["caveats"][2]
    assert evidence["api_route"].endswith("api_key=<redacted>")


def test_eia_v2_source_expands_retail_sales_metric_columns(monkeypatch) -> None:
    module = _load_industry_snapshot_module()
    monkeypatch.setenv("EIA_API_KEY", "retail-secret")

    class Response:
        url = "https://api.eia.gov/v2/electricity/retail-sales/data/?api_key=retail-secret"

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "response": {
                    "total": "1",
                    "data": [
                        {
                            "period": "2026-03",
                            "stateid": "US",
                            "stateDescription": "U.S. Total",
                            "sectorid": "ALL",
                            "sectorName": "all sectors",
                            "sales": "314308.22665",
                            "revenue": "44562.95799",
                            "price": "14.18",
                            "customers": "166374115",
                            "sales-units": "million kilowatt hours",
                            "revenue-units": "million dollars",
                            "price-units": "cents per kilowatt-hour",
                            "customers-units": "number of customers",
                        }
                    ],
                }
            }

    def fake_get(endpoint: str, params: dict, timeout: int) -> Response:
        assert endpoint == "https://api.eia.gov/v2/electricity/retail-sales/data/"
        assert params["api_key"] == "retail-secret"
        assert params["facets[sectorid][]"] == ["ALL", "RES"]
        return Response()

    monkeypatch.setattr(module.requests, "get", fake_get)
    rows, evidence = module.download_eia_v2_source(
        {
            "source_family": "industry_utilities_power_demand",
            "provider": "EIA",
            "route_type": "eia_v2_json",
            "endpoint": "https://api.eia.gov/v2/electricity/retail-sales/data/",
            "api_key_env_var": "EIA_API_KEY",
            "default_frequency": "monthly",
            "allowed_claim_types": ["power_demand_context"],
            "params": {
                "frequency": "monthly",
                "data[0]": "sales",
                "data[1]": "revenue",
                "data[2]": "price",
                "data[3]": "customers",
                "facets[stateid][]": ["US"],
                "facets[sectorid][]": ["ALL", "RES"],
            },
            "dataset": {
                "dataset_id": "eia/electricity/retail-sales",
                "unit": "mixed",
                "data_fields": ["sales", "revenue", "price", "customers"],
                "series_id_template": "EIA_RETAIL_SALES::{stateid}::{sectorid}::{metric}",
            },
        },
        as_of_date="2026-05-30",
        fetched_at="2026-05-30T00:00:00+00:00",
        timeout=25,
    )

    assert len(rows) == 4
    assert {row["series_id"] for row in rows} == {
        "EIA_RETAIL_SALES::US::ALL::sales",
        "EIA_RETAIL_SALES::US::ALL::revenue",
        "EIA_RETAIL_SALES::US::ALL::price",
        "EIA_RETAIL_SALES::US::ALL::customers",
    }
    assert rows[0]["observation_date"] == "2026-03-01"
    assert any(row["unit"] == "cents per kilowatt-hour" for row in rows)
    assert evidence["source_family"] == "industry_utilities_power_demand"
    assert evidence["dataset_id"] == "eia/electricity/retail-sales"
    assert evidence["api_route"].endswith("api_key=<redacted>")
