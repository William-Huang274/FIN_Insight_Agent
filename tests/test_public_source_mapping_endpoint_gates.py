from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_module():
    path = REPO_ROOT / "scripts" / "data_expansion" / "build_public_source_mapping_endpoint_gates.py"
    spec = importlib.util.spec_from_file_location("public_source_mapping_gate_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_build_openfigi_jobs_uses_exchange_symbol_and_exchange_code() -> None:
    module = _load_module()
    jobs = module.build_openfigi_jobs(
        [
            {
                "ticker": "AAPL",
                "exchange_symbol": "AAPL",
                "listing_exchange": "NASDAQ",
                "company_name": "Apple Inc.",
            },
            {
                "ticker": "005930.KS",
                "exchange_symbol": "005930",
                "listing_exchange": "KRX",
                "company_name": "Samsung Electronics Co., Ltd.",
            },
        ]
    )

    assert jobs[0]["request"] == {"idType": "TICKER", "idValue": "AAPL", "exchCode": "US"}
    assert jobs[1]["request"] == {"idType": "TICKER", "idValue": "005930", "exchCode": "KS"}


def test_auto_targets_include_known_make_aliases_and_auto_category() -> None:
    module = _load_module()
    targets = module.auto_targets(
        [
            {"ticker": "TSLA", "company_name": "Tesla, Inc.", "category": "automobiles", "sector": "Consumer Discretionary"},
            {"ticker": "ABC", "company_name": "ABC Corp.", "category": "software", "sector": "Information Technology"},
        ]
    )

    assert [row["ticker"] for row in targets] == ["TSLA"]


def test_name_match_confidence_is_conservative() -> None:
    module = _load_module()

    assert module.name_match_confidence("Apple Inc.", "APPLE INC") == "high"
    assert module.name_match_confidence("JPMorgan Chase & Co.", "JPMORGAN CHASE BANK, NATIONAL ASSOCIATION") == "medium"
    assert module.name_match_confidence("Bank", "First National Bank") == "low"


def test_redact_url_hides_query_keys() -> None:
    module = _load_module()
    url = "https://example.test/api?crtfc_key=secret123&api_key=secret456&x=1"

    redacted = module.redact_url(url)

    assert "secret123" not in redacted
    assert "secret456" not in redacted
    assert "crtfc_key=REDACTED" in redacted
    assert "api_key=REDACTED" in redacted


def test_make_name_matches_rejects_fuzzy_wrong_make() -> None:
    module = _load_module()

    assert module.make_name_matches("BYD", "BYD")
    assert module.make_name_matches("Li Auto", "LI AUTO INC")
    assert not module.make_name_matches("NIO", "COMPANION TRAILERS")
    assert not module.make_name_matches("Li Auto", "Jialing")
