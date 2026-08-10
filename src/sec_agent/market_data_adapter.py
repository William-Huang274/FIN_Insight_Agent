from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
import hashlib
import json
from typing import Any, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore


CAPTURE_SCHEMA = "fin_ia_0_1_3_market_data_capture_v1_0"
FACT_SCHEMA = "fin_ia_0_1_3_market_point_in_time_numeric_fact_v1_0"
ALPHA_VANTAGE_PROVIDER_ID = "alpha_vantage_time_series_daily"
AKSHARE_SHADOW_PROVIDER_ID = "akshare_eastmoney_us_hist_shadow"
_SAFE_HEADERS = {"content-type", "content-length", "last-modified", "etag"}


class MarketDataError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise MarketDataError(code)


def _decimal_text(value: Any) -> str:
    try:
        parsed = Decimal(str(value).strip().replace(",", ""))
    except (InvalidOperation, ValueError) as exc:
        raise MarketDataError("market_data_close_invalid") from exc
    _require(parsed.is_finite() and parsed > 0, "market_data_close_invalid")
    normalized = format(parsed.normalize(), "f")
    return normalized if "." in normalized else f"{normalized}.0"


def _safe_endpoint(url: str) -> str:
    """Remove credentials from a URL before it reaches capture or telemetry."""

    parsed = urlsplit(url)
    query = urlencode(
        [(key, value) for key, value in parse_qsl(parsed.query) if key.lower() != "apikey"]
    )
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, ""))


@dataclass(frozen=True)
class MarketPointRequest:
    case_key: str
    ticker: str
    exchange: str
    exact_date: str
    currency: str = "USD"
    price_basis: str = "raw_as_traded_close"

    def validate(self) -> None:
        _require(self.case_key and self.ticker and self.exchange, "market_data_request_identity_invalid")
        try:
            parsed = date.fromisoformat(self.exact_date)
        except ValueError as exc:
            raise MarketDataError("market_data_request_date_invalid") from exc
        _require(parsed.isoformat() == self.exact_date, "market_data_request_date_invalid")
        _require(
            self.currency == "USD" and self.price_basis == "raw_as_traded_close",
            "market_data_request_basis_invalid",
        )

    def as_capture_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "case_key": self.case_key,
            "ticker": self.ticker,
            "exchange": self.exchange,
            "exact_date": self.exact_date,
            "currency": self.currency,
            "price_basis": self.price_basis,
        }


@dataclass(frozen=True)
class MarketDataRawResponse:
    status_code: int
    safe_endpoint: str
    headers: Mapping[str, str]
    body: bytes


class MarketDataAdapter(Protocol):
    provider_id: str
    live_network: bool
    credential_env: str | None

    def fetch(
        self,
        *,
        request: MarketPointRequest,
        credential: str | None,
        timeout_seconds: int,
        byte_ceiling: int,
    ) -> MarketDataRawResponse: ...

    def parse_exact_close(
        self,
        *,
        request: MarketPointRequest,
        response: MarketDataRawResponse,
        response_capture: Mapping[str, Any],
    ) -> dict[str, Any]: ...


def _numeric_fact(
    *,
    request: MarketPointRequest,
    provider_id: str,
    provider_symbol: str,
    close: Any,
    source_coordinate: str,
    source_timezone: str,
    response_capture: Mapping[str, Any],
    source_endpoint: str,
) -> dict[str, Any]:
    value = _decimal_text(close)
    body = {
        "schema_version": FACT_SCHEMA,
        "fact_type": "market_point_in_time_close",
        "case_key": request.case_key,
        "entity_ticker": request.ticker,
        "exchange": request.exchange,
        "provider_id": provider_id,
        "provider_symbol": provider_symbol,
        "observation_date": request.exact_date,
        "normalized_value": value,
        "currency": request.currency,
        "unit": "USD_per_share",
        "price_basis": request.price_basis,
        "source_coordinate": source_coordinate,
        "source_timezone": source_timezone,
        "source_endpoint": source_endpoint,
        "response_capture_ref": str(response_capture.get("object_key") or ""),
        "response_capture_digest": str(response_capture.get("digest") or ""),
        "promotion_status": "accepted_exact_date_market_input",
        "authority_boundary": (
            "This fact is one exact-date raw close input. It does not by itself authorize "
            "a valuation multiple, fair value, target price or recommendation."
        ),
    }
    digest = canonical_digest(body)
    return {
        **body,
        "numeric_fact_id": f"market_pit_fact_{digest[:24]}",
        "numeric_fact_digest": digest,
    }


class AlphaVantageDailyAdapter:
    provider_id = ALPHA_VANTAGE_PROVIDER_ID
    live_network = True
    credential_env = "ALPHAVANTAGE_API_KEY"
    endpoint = "https://www.alphavantage.co/query"

    def fetch(
        self,
        *,
        request: MarketPointRequest,
        credential: str | None,
        timeout_seconds: int,
        byte_ceiling: int,
    ) -> MarketDataRawResponse:
        request.validate()
        _require(bool(str(credential or "").strip()), "market_data_credential_missing")
        params = {
            "function": "TIME_SERIES_DAILY",
            "symbol": request.ticker,
            "outputsize": "compact",
            "datatype": "json",
            "apikey": str(credential),
        }
        url = f"{self.endpoint}?{urlencode(params)}"
        http_request = Request(
            url,
            headers={"Accept": "application/json", "User-Agent": "FIN-Insight-Agent/0.1.3 market-data"},
            method="GET",
        )
        try:
            with urlopen(http_request, timeout=timeout_seconds) as response:
                body = response.read(byte_ceiling + 1)
                _require(len(body) <= byte_ceiling, "market_data_response_body_ceiling_exceeded")
                return MarketDataRawResponse(
                    status_code=int(response.status),
                    safe_endpoint=_safe_endpoint(response.geturl()),
                    headers={
                        key.lower(): str(value)
                        for key, value in response.headers.items()
                        if key.lower() in _SAFE_HEADERS
                    },
                    body=body,
                )
        except HTTPError as exc:
            body = exc.read(byte_ceiling + 1)[:byte_ceiling]
            return MarketDataRawResponse(
                status_code=int(exc.code),
                safe_endpoint=_safe_endpoint(exc.geturl()),
                headers={
                    key.lower(): str(value)
                    for key, value in exc.headers.items()
                    if key.lower() in _SAFE_HEADERS
                },
                body=body,
            )
        except (URLError, TimeoutError, OSError) as exc:
            raise MarketDataError("market_data_transport_failed") from exc

    def parse_exact_close(
        self,
        *,
        request: MarketPointRequest,
        response: MarketDataRawResponse,
        response_capture: Mapping[str, Any],
    ) -> dict[str, Any]:
        _require(200 <= response.status_code < 300, f"market_data_http_{response.status_code}")
        try:
            payload = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MarketDataError("market_data_json_invalid") from exc
        _require(isinstance(payload, dict), "market_data_json_invalid")
        if payload.get("Error Message"):
            raise MarketDataError("market_data_provider_symbol_error")
        if payload.get("Note"):
            raise MarketDataError("market_data_provider_rate_limited")
        if payload.get("Information"):
            raise MarketDataError("market_data_provider_information_response")
        metadata = dict(payload.get("Meta Data") or {})
        provider_symbol = str(metadata.get("2. Symbol") or "").strip().upper()
        _require(provider_symbol == request.ticker.upper(), "market_data_provider_symbol_mismatch")
        rows = payload.get("Time Series (Daily)")
        _require(isinstance(rows, dict), "market_data_daily_series_missing")
        row = rows.get(request.exact_date)
        _require(isinstance(row, dict), "market_data_exact_date_row_missing")
        _require("4. close" in row, "market_data_close_field_missing")
        return _numeric_fact(
            request=request,
            provider_id=self.provider_id,
            provider_symbol=provider_symbol,
            close=row["4. close"],
            source_coordinate=f"Time Series (Daily).{request.exact_date}.4. close",
            source_timezone=str(metadata.get("5. Time Zone") or "US/Eastern"),
            response_capture=response_capture,
            source_endpoint=response.safe_endpoint,
        )


class AkshareDailyShadowAdapter:
    """Optional diagnostic adapter; its output can never be promoted as authority."""

    provider_id = AKSHARE_SHADOW_PROVIDER_ID
    live_network = True
    credential_env = None
    _provider_symbols = {"DELL": "106.DELL", "MU": "105.MU", "NVDA": "105.NVDA"}

    def fetch(
        self,
        *,
        request: MarketPointRequest,
        credential: str | None,
        timeout_seconds: int,
        byte_ceiling: int,
    ) -> MarketDataRawResponse:
        del credential, timeout_seconds
        request.validate()
        try:
            import akshare as ak  # type: ignore[import-not-found]
        except ImportError as exc:
            raise MarketDataError("market_data_shadow_dependency_unavailable") from exc
        symbol = self._provider_symbols.get(request.ticker.upper())
        _require(bool(symbol), "market_data_shadow_symbol_mapping_missing")
        start = date.fromisoformat(request.exact_date)
        end = start + timedelta(days=1)
        try:
            frame = ak.stock_us_hist(
                symbol=symbol,
                period="daily",
                start_date=start.strftime("%Y%m%d"),
                end_date=end.strftime("%Y%m%d"),
                adjust="",
            )
        except Exception as exc:  # third-party library exception text is never persisted
            raise MarketDataError("market_data_shadow_transport_failed") from exc
        rows = frame.to_dict(orient="records")
        encoded = json.dumps(rows, ensure_ascii=False, default=str, sort_keys=True).encode("utf-8")
        _require(len(encoded) <= byte_ceiling, "market_data_response_body_ceiling_exceeded")
        return MarketDataRawResponse(
            status_code=200,
            safe_endpoint=f"akshare://stock_us_hist?symbol={symbol}&adjust=raw",
            headers={"content-type": "application/json"},
            body=encoded,
        )

    def parse_exact_close(
        self,
        *,
        request: MarketPointRequest,
        response: MarketDataRawResponse,
        response_capture: Mapping[str, Any],
    ) -> dict[str, Any]:
        try:
            rows = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MarketDataError("market_data_shadow_json_invalid") from exc
        _require(isinstance(rows, list), "market_data_shadow_json_invalid")
        matches = [
            row
            for row in rows
            if str(row.get("日期") or row.get("date") or "")[:10] == request.exact_date
        ]
        _require(len(matches) == 1, "market_data_shadow_exact_date_row_missing_or_duplicate")
        close = matches[0].get("收盘", matches[0].get("close"))
        fact = _numeric_fact(
            request=request,
            provider_id=self.provider_id,
            provider_symbol=self._provider_symbols[request.ticker.upper()],
            close=close,
            source_coordinate=f"stock_us_hist.{request.exact_date}.raw_close",
            source_timezone="US/Eastern",
            response_capture=response_capture,
            source_endpoint=response.safe_endpoint,
        )
        shadow = {
            **fact,
            "promotion_status": "diagnostic_shadow_only_never_authoritative",
            "authority_boundary": (
                "AKShare/Eastmoney is a diagnostic shadow. It can detect disagreement but "
                "cannot promote, replace or override the primary captured market fact."
            ),
        }
        digest_body = dict(shadow)
        digest_body.pop("numeric_fact_id", None)
        digest_body.pop("numeric_fact_digest", None)
        digest = canonical_digest(digest_body)
        return {
            **shadow,
            "numeric_fact_id": f"market_pit_shadow_{digest[:24]}",
            "numeric_fact_digest": digest,
        }


class CaptureFirstMarketDataClient:
    def __init__(
        self,
        *,
        store: FileCanonicalObjectStore,
        namespace: str,
    ) -> None:
        self.store = store
        self.namespace = namespace
        self.network_calls = 0
        self.provider_invocations = 0

    def _persist(self, payload: Mapping[str, Any], artifact_type: str) -> dict[str, Any]:
        return self.store.put_json(
            dict(payload),
            namespace=self.namespace,
            artifact_type=artifact_type,
        )

    def fetch_exact_close(
        self,
        *,
        request: MarketPointRequest,
        adapter: MarketDataAdapter,
        credential: str | None,
        timeout_seconds: int,
        byte_ceiling: int,
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        request.validate()
        request_capture = {
            "schema_version": CAPTURE_SCHEMA,
            "capture_kind": "market_data_request",
            "provider_id": adapter.provider_id,
            "request": request.as_capture_dict(),
            "credential_source": (
                f"environment:{adapter.credential_env}" if adapter.credential_env else "none"
            ),
            "credential_value_captured": False,
            "transport_parameters": {
                "function": "TIME_SERIES_DAILY" if adapter.provider_id == ALPHA_VANTAGE_PROVIDER_ID else "stock_us_hist",
                "outputsize": "compact" if adapter.provider_id == ALPHA_VANTAGE_PROVIDER_ID else "exact_date_window",
                "adjustment": "raw_unadjusted",
            },
        }
        request_ref = self._persist(request_capture, "market_data_request")
        self.provider_invocations += 1
        self.network_calls += int(bool(adapter.live_network))
        try:
            response = adapter.fetch(
                request=request,
                credential=credential,
                timeout_seconds=timeout_seconds,
                byte_ceiling=byte_ceiling,
            )
        except MarketDataError as exc:
            failure = {
                "schema_version": CAPTURE_SCHEMA,
                "capture_kind": "market_data_failure",
                "provider_id": adapter.provider_id,
                "request_capture_ref": request_ref["object_key"],
                "request_capture_digest": request_ref["digest"],
                "failure_code": exc.code,
                "failure_phase": "transport_or_dependency",
                "raw_exception_text_captured": False,
                "credential_value_captured": False,
            }
            failure_ref = self._persist(failure, "market_data_failure")
            return None, {
                "provider_id": adapter.provider_id,
                "status": "typed_failure",
                "failure_code": exc.code,
                "request_capture": request_ref,
                "response_capture": failure_ref,
            }
        secret = str(credential or "").encode("utf-8")
        if secret and secret in response.body:
            failure = {
                "schema_version": CAPTURE_SCHEMA,
                "capture_kind": "market_data_secret_rejection",
                "provider_id": adapter.provider_id,
                "request_capture_ref": request_ref["object_key"],
                "request_capture_digest": request_ref["digest"],
                "failure_code": "market_data_response_contains_credential",
                "response_body_sha256": hashlib.sha256(response.body).hexdigest(),
                "response_body_bytes": len(response.body),
                "response_body_captured": False,
                "credential_value_captured": False,
            }
            failure_ref = self._persist(failure, "market_data_secret_rejection")
            return None, {
                "provider_id": adapter.provider_id,
                "status": "typed_failure",
                "failure_code": "market_data_response_contains_credential",
                "request_capture": request_ref,
                "response_capture": failure_ref,
            }
        response_capture = {
            "schema_version": CAPTURE_SCHEMA,
            "capture_kind": "market_data_response",
            "provider_id": adapter.provider_id,
            "request_capture_ref": request_ref["object_key"],
            "request_capture_digest": request_ref["digest"],
            "status_code": response.status_code,
            "safe_endpoint": response.safe_endpoint,
            "headers": {
                key: str(value)
                for key, value in response.headers.items()
                if key.lower() in _SAFE_HEADERS
            },
            "body_base64": base64.b64encode(response.body).decode("ascii"),
            "body_sha256": hashlib.sha256(response.body).hexdigest(),
            "body_bytes": len(response.body),
            "capture_before_parse": True,
            "credential_value_captured": False,
        }
        response_ref = self._persist(response_capture, "market_data_response")
        try:
            fact = adapter.parse_exact_close(
                request=request,
                response=response,
                response_capture=response_ref,
            )
        except MarketDataError as exc:
            return None, {
                "provider_id": adapter.provider_id,
                "status": "parse_or_adjudication_failure",
                "failure_code": exc.code,
                "request_capture": request_ref,
                "response_capture": response_ref,
            }
        return fact, {
            "provider_id": adapter.provider_id,
            "status": "captured_parsed_and_adjudicated",
            "failure_code": "",
            "request_capture": request_ref,
            "response_capture": response_ref,
            "numeric_fact_digest": fact["numeric_fact_digest"],
        }


__all__ = [
    "AKSHARE_SHADOW_PROVIDER_ID",
    "ALPHA_VANTAGE_PROVIDER_ID",
    "AkshareDailyShadowAdapter",
    "AlphaVantageDailyAdapter",
    "CAPTURE_SCHEMA",
    "CaptureFirstMarketDataClient",
    "FACT_SCHEMA",
    "MarketDataAdapter",
    "MarketDataError",
    "MarketDataRawResponse",
    "MarketPointRequest",
]
