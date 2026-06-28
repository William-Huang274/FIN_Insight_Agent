from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "data_expansion" / "build_broad_app_store_platform_context_rows.py"
SPEC = importlib.util.spec_from_file_location("build_broad_app_store_platform_context_rows", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_broad_app_store_platform_uses_brand_alias_for_holding_company(tmp_path: Path, monkeypatch) -> None:
    calls: list[str] = []

    def fake_fetch(url: str, timeout_s: float) -> tuple[str, str, str]:
        calls.append(url)
        assert timeout_s == 2
        return (
            "ok",
            json.dumps(
                {
                    "results": [
                        {
                            "trackId": 1,
                            "trackName": "Booking.com Travel Deals",
                            "sellerName": "Booking.com B.V.",
                            "averageUserRating": 4.8,
                            "userRatingCount": 1000,
                            "version": "1.0",
                            "currentVersionReleaseDate": "2026-06-01T00:00:00Z",
                        }
                    ]
                }
            ),
            "",
        )

    monkeypatch.setattr(MODULE, "_fetch_text", fake_fetch)
    result = MODULE.build_broad_app_store_platform_context_rows(
        matrix_rows=[
            {
                "ticker": "BKNG",
                "company_name": "Booking Holdings",
                "source_role_matrix": [
                    {"requirement_id": "app_rank_store_proxy"},
                    {"requirement_id": "platform_review_proxy"},
                ],
            }
        ],
        generated_at="2026-06-19T00:00:00Z",
        raw_dir=tmp_path,
        tickers=["BKNG"],
        timeout_s=2,
        sleep_s=0,
        limit=3,
        max_apps_per_company=1,
    )

    assert "Booking.com" in calls[0]
    assert {row["requirement_id"] for row in result["rows"]} == {"app_rank_store_proxy", "platform_review_proxy"}
    assert all(row["ticker"] == "BKNG" for row in result["rows"])


def test_broad_app_store_platform_uses_host_hotels_seller_alias(tmp_path: Path, monkeypatch) -> None:
    def fake_fetch(url: str, timeout_s: float) -> tuple[str, str, str]:
        assert "Host%20Hotels" in url
        return (
            "ok",
            json.dumps(
                {
                    "results": [
                        {
                            "trackId": 2,
                            "trackName": "CHAMPION Host Hotels",
                            "sellerName": "Host Hotels & Resorts, Inc.",
                            "averageUserRating": 0,
                            "userRatingCount": 0,
                            "version": "3.0",
                            "currentVersionReleaseDate": "2026-01-01T00:00:00Z",
                        }
                    ]
                }
            ),
            "",
        )

    monkeypatch.setattr(MODULE, "_fetch_text", fake_fetch)
    result = MODULE.build_broad_app_store_platform_context_rows(
        matrix_rows=[
            {
                "ticker": "HST",
                "company_name": "Host Hotels & Resorts",
                "source_role_matrix": [
                    {"requirement_id": "app_rank_store_proxy"},
                    {"requirement_id": "platform_review_proxy"},
                ],
            }
        ],
        generated_at="2026-06-20T00:00:00Z",
        raw_dir=tmp_path,
        tickers=["HST"],
        timeout_s=2,
        sleep_s=0,
        limit=3,
        max_apps_per_company=1,
    )

    assert {row["requirement_id"] for row in result["rows"]} == {"app_rank_store_proxy", "platform_review_proxy"}
    assert all(row["ticker"] == "HST" for row in result["rows"])
