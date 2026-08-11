from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import pytest

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.market_data_adapter import (
    AKSHARE_SHADOW_PROVIDER_ID,
    ALPHA_VANTAGE_PROVIDER_ID,
    AkshareDailyShadowAdapter,
    AlphaVantageDailyAdapter,
    CaptureFirstMarketDataClient,
    MarketDataRawResponse,
    MarketPointRequest,
)


class FixtureAlphaAdapter(AlphaVantageDailyAdapter):
    live_network = False

    def __init__(self, payload: Mapping[str, Any]) -> None:
        self.payload = dict(payload)

    def fetch(
        self,
        *,
        request: MarketPointRequest,
        credential: str | None,
        timeout_seconds: int,
        byte_ceiling: int,
    ) -> MarketDataRawResponse:
        del request, credential, timeout_seconds, byte_ceiling
        return MarketDataRawResponse(
            status_code=200,
            safe_endpoint=(
                "https://www.alphavantage.co/query?"
                "function=TIME_SERIES_DAILY&symbol=DELL&outputsize=compact&datatype=json"
            ),
            headers={"content-type": "application/json"},
            body=json.dumps(self.payload, sort_keys=True).encode("utf-8"),
        )


class FixtureShadowAdapter(AkshareDailyShadowAdapter):
    live_network = False

    def fetch(
        self,
        *,
        request: MarketPointRequest,
        credential: str | None,
        timeout_seconds: int,
        byte_ceiling: int,
    ) -> MarketDataRawResponse:
        del credential, timeout_seconds, byte_ceiling
        return MarketDataRawResponse(
            status_code=200,
            safe_endpoint="akshare://stock_us_hist?symbol=106.DELL&adjust=raw",
            headers={"content-type": "application/json"},
            body=json.dumps(
                [{"日期": request.exact_date, "收盘": 142.37}],
                ensure_ascii=False,
            ).encode("utf-8"),
        )


def _request() -> MarketPointRequest:
    return MarketPointRequest(
        case_key="DELL",
        ticker="DELL",
        exchange="NYSE",
        exact_date="2026-08-06",
    )


def _alpha_payload(*, symbol: str = "DELL", include_date: bool = True) -> dict[str, Any]:
    rows = {"2026-08-06": {"1. open": "140.00", "4. close": "142.3700"}}
    if not include_date:
        rows = {"2026-08-05": {"1. open": "139.00", "4. close": "140.00"}}
    return {
        "Meta Data": {"2. Symbol": symbol, "5. Time Zone": "US/Eastern"},
        "Time Series (Daily)": rows,
    }


def test_alpha_exact_date_fact_is_capture_first_and_secret_free(tmp_path: Path) -> None:
    store = FileCanonicalObjectStore(tmp_path / "objects")
    client = CaptureFirstMarketDataClient(store=store, namespace="fixture/market")
    secret = "fixture-secret-must-never-be-captured"
    fact, attempt = client.fetch_exact_close(
        request=_request(),
        adapter=FixtureAlphaAdapter(_alpha_payload()),
        credential=secret,
        timeout_seconds=5,
        byte_ceiling=100_000,
    )

    assert fact is not None
    assert fact["provider_id"] == ALPHA_VANTAGE_PROVIDER_ID
    assert fact["normalized_value"] == "142.37"
    assert fact["observation_date"] == "2026-08-06"
    assert fact["price_basis"] == "raw_as_traded_close"
    assert attempt["status"] == "captured_parsed_and_adjudicated"
    assert client.network_calls == 0
    assert client.provider_invocations == 1
    serialized = "\n".join(
        path.read_text(encoding="utf-8") for path in (tmp_path / "objects").rglob("*.json")
    )
    assert secret not in serialized
    assert "apikey" not in serialized.lower()


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (_alpha_payload(symbol="MU"), "market_data_provider_symbol_mismatch"),
        (_alpha_payload(include_date=False), "market_data_exact_date_row_missing"),
        (
            {
                "Meta Data": {"2. Symbol": "DELL"},
                "Time Series (Daily)": {"2026-08-06": {"4. close": "-1"}},
            },
            "market_data_close_invalid",
        ),
        ({"Note": "rate limit"}, "market_data_provider_rate_limited"),
    ],
)
def test_alpha_mutations_fail_closed(
    tmp_path: Path, payload: Mapping[str, Any], code: str
) -> None:
    client = CaptureFirstMarketDataClient(
        store=FileCanonicalObjectStore(tmp_path / "objects"),
        namespace="fixture/market",
    )
    fact, attempt = client.fetch_exact_close(
        request=_request(),
        adapter=FixtureAlphaAdapter(payload),
        credential="fixture-secret",
        timeout_seconds=5,
        byte_ceiling=100_000,
    )
    assert fact is None
    assert attempt["status"] == "parse_or_adjudication_failure"
    assert attempt["failure_code"] == code


def test_captured_body_containing_secret_is_rejected_without_body_capture(
    tmp_path: Path,
) -> None:
    secret = "fixture-secret-in-provider-body"
    adapter = FixtureAlphaAdapter({"Information": secret})
    client = CaptureFirstMarketDataClient(
        store=FileCanonicalObjectStore(tmp_path / "objects"),
        namespace="fixture/market",
    )
    fact, attempt = client.fetch_exact_close(
        request=_request(),
        adapter=adapter,
        credential=secret,
        timeout_seconds=5,
        byte_ceiling=100_000,
    )
    assert fact is None
    assert attempt["failure_code"] == "market_data_response_contains_credential"
    serialized = "\n".join(
        path.read_text(encoding="utf-8") for path in (tmp_path / "objects").rglob("*.json")
    )
    assert secret not in serialized
    assert '"response_body_captured":false' in serialized.replace(" ", "")


def test_akshare_shadow_is_diagnostic_only(tmp_path: Path) -> None:
    client = CaptureFirstMarketDataClient(
        store=FileCanonicalObjectStore(tmp_path / "objects"),
        namespace="fixture/shadow",
    )
    fact, attempt = client.fetch_exact_close(
        request=_request(),
        adapter=FixtureShadowAdapter(),
        credential=None,
        timeout_seconds=5,
        byte_ceiling=100_000,
    )
    assert fact is not None
    assert fact["provider_id"] == AKSHARE_SHADOW_PROVIDER_ID
    assert fact["promotion_status"] == "diagnostic_shadow_only_never_authoritative"
    digest_body = dict(fact)
    digest_body.pop("numeric_fact_id")
    digest_body.pop("numeric_fact_digest")
    assert fact["numeric_fact_digest"] == canonical_digest(digest_body)
    assert attempt["status"] == "captured_parsed_and_adjudicated"
