from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "data_expansion" / "build_app_marketplace_context_rows.py"
SPEC = importlib.util.spec_from_file_location("build_app_marketplace_context_rows", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_app_marketplace_api_url_expands_supported_app_store_urls() -> None:
    assert MODULE.app_marketplace_api_url("https://apps.apple.com/us/app/apple-store/id375380948") == (
        "https://itunes.apple.com/lookup?id=375380948",
        "apple_app_store",
    )
    assert MODULE.app_marketplace_api_url("https://itunes.apple.com/lookup?id=123456789") == (
        "https://itunes.apple.com/lookup?id=123456789",
        "apple_app_store",
    )
    assert MODULE.app_marketplace_api_url("https://play.google.com/store/apps/details?id=com.google.android.youtube") == ("", "")


def test_build_app_marketplace_context_rows_with_fixture_fetch(tmp_path: Path) -> None:
    def fake_fetch(url: str, timeout_s: float) -> tuple[int, str, str]:
        assert url == "https://itunes.apple.com/lookup?id=375380948"
        assert timeout_s == 2
        return (
            200,
            "application/json",
            json.dumps(
                {
                    "resultCount": 1,
                    "results": [
                        {
                            "trackName": "Apple Store",
                            "sellerName": "Apple",
                            "averageUserRating": 4.8,
                            "userRatingCount": 200000,
                            "version": "6.6",
                            "currentVersionReleaseDate": "2026-06-01T00:00:00Z",
                        }
                    ],
                }
            ),
        )

    result = MODULE.build_app_marketplace_context_rows(
        probes=[
            {
                "ticker": "AAPL",
                "company_name": "Apple",
                "company_names": ["Apple"],
                "product_terms": ["Apple Store"],
                "urls": ["https://apps.apple.com/us/app/apple-store/id375380948"],
            }
        ],
        generated_at="2026-06-17T00:00:00Z",
        raw_dir=tmp_path,
        timeout_s=2,
        fetch=fake_fetch,
    )

    rows = result["rows"]
    assert len(rows) == 1
    row = rows[0]
    assert row["source_id"] == MODULE.SOURCE_ID
    assert row["provider"] == "apple_app_store"
    assert row["source_layer_id"] == "L3"
    assert row["structured_context_type"] == "app_store_marketplace_context"
    assert row["issuer_binding_status"] == "issuer_mentioned_in_snapshot"
    assert row["product_binding_status"] == "product_mentioned_in_snapshot"
    assert row["exact_value_authority"] is False
    assert Path(row["raw_path"]).exists()


def test_app_marketplace_coverage_gate_passes_with_bound_rows(tmp_path: Path) -> None:
    result = MODULE.build_app_marketplace_context_rows(
        probes=[
            {
                "ticker": "MSFT",
                "company_name": "Microsoft",
                "company_names": ["Microsoft"],
                "product_terms": ["Microsoft Teams"],
                "urls": ["https://apps.apple.com/us/app/microsoft-teams/id1113153706"],
            }
        ],
        generated_at="2026-06-17T00:00:00Z",
        raw_dir=tmp_path,
        fetch=lambda url, timeout_s: (
            200,
            "application/json",
            json.dumps(
                {
                    "resultCount": 1,
                    "results": [
                        {
                            "trackName": "Microsoft Teams",
                            "sellerName": "Microsoft",
                            "averageUserRating": 4.7,
                            "userRatingCount": 150000,
                            "version": "7.0",
                            "currentVersionReleaseDate": "2026-06-01T00:00:00Z",
                        }
                    ],
                }
            ),
        ),
    )
    source_rows = [
        {
            "source_id": MODULE.SOURCE_ID,
            "layer_id": "L3",
            "evidence_graph_status": "runtime_ready_context",
            "can_crawl_or_download": True,
            "can_structure": True,
            "runtime_ready_context": True,
            "exact_value_authority_ready": False,
            "can_support_company_exact_fact": False,
        }
    ]

    coverage = MODULE.build_app_marketplace_coverage_gate(
        context_rows=result["rows"],
        source_layer_rows=source_rows,
        generated_at="2026-06-17T00:00:00Z",
    )
    req = coverage["requirements"][0]
    assert req["requirement_id"] == "app_rank_store_proxy"
    assert req["status"] == "pass"
    assert req["entity_bound_row_count"] == 1


def test_app_marketplace_fetch_retries_transient_failure(tmp_path: Path) -> None:
    calls = 0

    def flaky_fetch(url: str, timeout_s: float) -> tuple[int, str, str]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("transient read failure")
        return (
            200,
            "application/json",
            json.dumps({"resultCount": 1, "results": [{"trackName": "Netflix", "sellerName": "Netflix", "version": "1.0"}]}),
        )

    result = MODULE.build_app_marketplace_context_rows(
        probes=[
            {
                "ticker": "NFLX",
                "company_name": "Netflix",
                "company_names": ["Netflix"],
                "product_terms": ["Netflix"],
                "urls": ["https://apps.apple.com/us/app/netflix/id363590051"],
            }
        ],
        generated_at="2026-06-17T00:00:00Z",
        raw_dir=tmp_path,
        fetch_retries=1,
        fetch=flaky_fetch,
    )

    assert calls == 2
    assert len(result["rows"]) == 1
    assert result["attempts"][0]["status"] == "materialized"
