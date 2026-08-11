from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_module():
    path = REPO_ROOT / "scripts" / "data_expansion" / "audit_public_source_full_availability.py"
    spec = importlib.util.spec_from_file_location("public_source_full_availability_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_field_completeness_passes_required_fred_fields() -> None:
    module = _load_module()
    records = [
        {
            "schema_version": "unit",
            "source_id": "fred_api",
            "provider": "FRED",
            "record_type": "macro_time_series_observation",
            "source_family": "macro_industry_indicator",
            "source_families": ["macro_industry_indicator"],
            "claim_scope": "industry_context_only",
            "claim_boundary": "Context only.",
            "source_policy": "unit",
            "api_route": "https://api.stlouisfed.org/fred/series/observations?api_key=REDACTED",
            "series_id": "FEDFUNDS",
            "observation_date": "2026-05-01",
            "value": 4.33,
            "unit": "percent",
        }
    ]

    audit = module.field_completeness("fred_api", records)

    assert audit["status"] == "pass"
    assert audit["missing_required_fields"] == []
    assert audit["empty_required_field_counts"] == {}


def test_field_completeness_flags_empty_required_values() -> None:
    module = _load_module()
    records = [
        {
            "schema_version": "unit",
            "source_id": "fred_api",
            "provider": "FRED",
            "record_type": "macro_time_series_observation",
            "source_family": "macro_industry_indicator",
            "source_families": ["macro_industry_indicator"],
            "claim_scope": "industry_context_only",
            "claim_boundary": "Context only.",
            "source_policy": "unit",
            "api_route": "https://api.stlouisfed.org/fred/series/observations?api_key=REDACTED",
            "series_id": "FEDFUNDS",
            "observation_date": "",
            "value": 4.33,
            "unit": "percent",
        }
    ]

    audit = module.field_completeness("fred_api", records)

    assert audit["status"] == "partial"
    assert audit["empty_required_field_counts"]["observation_date"] == 1


def test_plan_only_row_marks_missing_required_key(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.delenv("EDINET_API_KEY", raising=False)
    row = {
        "source_id": "jp_edinet_api",
        "provider": "EDINET",
        "phase": "P2",
        "auth_status": "free_key",
        "env_var": "EDINET_API_KEY",
        "source_families": ["global_public_annual_report"],
        "claim_scope": "primary_company_disclosure",
        "boundary_notes": "Requires key.",
        "collector_status": "blocked_auth",
        "parser_status": "blocked_until_downloader_pass",
        "gap_type": "auth_gap",
        "priority": "P2_free_key_non_us",
        "official_url": "https://disclosure2.edinet-fsa.go.jp/week0020.aspx",
        "current_repo_status": "profile_configured_blocked_requires_key",
        "live_probe_supported": False,
    }

    audit = module.build_plan_only_row("jp_edinet_api", row, fetched_at="2026-06-11T00:00:00+00:00")

    assert audit["audit_status"] == "not_audited_blocked"
    assert audit["availability_decision"] == "blocked_missing_credential"
    assert audit["agent_promotion_allowed"] is False


def test_live_test_redacts_fred_key(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setenv("FRED_API_KEY", "unit-test-secret")

    class Response:
        status_code = 200
        url = "https://api.stlouisfed.org/fred/series/observations?series_id=FEDFUNDS&api_key=unit-test-secret"
        headers = {"content-type": "application/json"}

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "count": 1,
                "limit": 1,
                "offset": 0,
                "observations": [
                    {
                        "date": "2026-05-01",
                        "value": "4.33",
                        "realtime_start": "2026-06-01",
                        "realtime_end": "2026-06-01",
                    }
                ],
            }

    def fake_request(method, url, params, headers, json, timeout) -> Response:
        assert params["api_key"] == "unit-test-secret"
        return Response()

    monkeypatch.setattr(module.requests, "request", fake_request)
    test_row = module.run_collector_live_test(
        "fred_api",
        module.normalized.COLLECTOR_PROFILES["fred_api"],
        {
            "source_id": "fred_api",
            "provider": "FRED",
            "source_families": ["macro_industry_indicator"],
            "claim_scope": "industry_context_only",
            "boundary_notes": "Context only.",
        },
        {"name": "unit"},
        fetched_at="2026-06-11T00:00:00+00:00",
        timeout_s=3,
    )

    assert test_row["status"] == "pass"
    assert "unit-test-secret" not in test_row["api_route"]
    assert "api_key=REDACTED" in test_row["api_route"]
    assert test_row["payload_stats"]["provider_total_count"] == 1
