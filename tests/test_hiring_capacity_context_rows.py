from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "data_expansion" / "build_hiring_capacity_context_rows.py"
SPEC = importlib.util.spec_from_file_location("build_hiring_capacity_context_rows", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_ats_api_url_expands_supported_providers() -> None:
    assert MODULE.ats_api_url(provider="greenhouse", board_token="datadog") == (
        "https://boards-api.greenhouse.io/v1/boards/datadog/jobs?content=true"
    )
    assert MODULE.ats_api_url(provider="lever", board_token="palantir") == "https://api.lever.co/v0/postings/palantir?mode=json"
    assert MODULE.ats_api_url(provider="workday", board_token="x") == ""


def test_build_hiring_capacity_context_rows_with_greenhouse_fixture(tmp_path: Path) -> None:
    payload = {
        "jobs": [
            {
                "id": 1,
                "title": "Senior AI Platform Engineer",
                "absolute_url": "https://job.example/1",
                "updated_at": "2026-06-16T00:00:00Z",
                "location": {"name": "New York"},
                "departments": [{"name": "AI Platform"}],
            },
            {
                "id": 2,
                "title": "Accounting Manager",
                "absolute_url": "https://job.example/2",
                "updated_at": "2026-06-15T00:00:00Z",
                "location": {"name": "Remote"},
                "departments": [{"name": "Finance"}],
            },
        ]
    }

    def fake_fetch(url: str, timeout_s: float) -> tuple[int, str, str]:
        assert url == "https://boards-api.greenhouse.io/v1/boards/datadog/jobs?content=true"
        assert timeout_s == 2
        return 200, "application/json", json.dumps(payload)

    result = MODULE.build_hiring_capacity_context_rows(
        probes=[
            {
                "ticker": "DDOG",
                "company_name": "Datadog",
                "provider": "greenhouse",
                "board_token": "datadog",
                "company_names": ["Datadog"],
                "role_focus_terms": ["AI", "Platform"],
            }
        ],
        generated_at="2026-06-17T00:00:00Z",
        raw_dir=tmp_path,
        timeout_s=2,
        max_jobs_per_company=1,
        fetch=fake_fetch,
    )

    rows = result["rows"]
    assert len(rows) == 1
    row = rows[0]
    assert row["source_id"] == MODULE.SOURCE_ID
    assert row["provider"] == "greenhouse"
    assert row["source_layer_id"] == "L3"
    assert row["structured_context_type"] == "hiring_signal_context"
    assert row["issuer_binding_status"] == "issuer_mentioned_in_snapshot"
    assert row["product_binding_status"] == "product_mentioned_in_snapshot"
    assert row["exact_value_authority"] is False
    assert row["job_department"] == "AI Platform"
    assert Path(row["raw_path"]).exists()


def test_build_hiring_capacity_context_rows_with_workday_fixture(tmp_path: Path) -> None:
    payload = {
        "total": 1,
        "jobPostings": [
            {
                "title": "Senior GPU AI Platform Engineer",
                "externalPath": "/job/Santa-Clara-CA/Senior-GPU-AI-Platform-Engineer_JR1",
                "locationsText": "Santa Clara, CA",
                "postedOn": "Posted Yesterday",
                "bulletFields": ["JR1"],
            }
        ],
    }

    def fake_fetch(url: str, timeout_s: float) -> tuple[int, str, str]:
        assert url == "https://nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/NVIDIAExternalCareerSite/jobs"
        assert timeout_s == 2
        return 200, "application/json", json.dumps(payload)

    result = MODULE.build_hiring_capacity_context_rows(
        probes=[
            {
                "ticker": "NVDA",
                "company_name": "NVIDIA",
                "provider": "workday",
                "api_url": "https://nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/NVIDIAExternalCareerSite/jobs",
                "job_base_url": "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite",
                "company_names": ["NVIDIA"],
                "role_focus_terms": ["GPU", "AI", "Platform"],
            }
        ],
        generated_at="2026-06-17T00:00:00Z",
        raw_dir=tmp_path,
        timeout_s=2,
        max_jobs_per_company=1,
        fetch=fake_fetch,
    )

    rows = result["rows"]
    assert len(rows) == 1
    row = rows[0]
    assert row["provider"] == "workday"
    assert row["source_layer_id"] == "L3"
    assert row["structured_context_type"] == "hiring_signal_context"
    assert row["issuer_binding_status"] == "issuer_mentioned_in_snapshot"
    assert row["product_binding_status"] == "product_mentioned_in_snapshot"
    assert row["job_url"].endswith("/job/Santa-Clara-CA/Senior-GPU-AI-Platform-Engineer_JR1")
    assert row["exact_value_authority"] is False


def test_hiring_capacity_coverage_gate_passes_with_bound_rows(tmp_path: Path) -> None:
    result = MODULE.build_hiring_capacity_context_rows(
        probes=[
            {
                "ticker": "PLTR",
                "company_name": "Palantir",
                "provider": "lever",
                "board_token": "palantir",
                "company_names": ["Palantir"],
                "role_focus_terms": ["AIP", "Platform"],
            }
        ],
        generated_at="2026-06-17T00:00:00Z",
        raw_dir=tmp_path,
        fetch=lambda url, timeout_s: (
            200,
            "application/json",
            json.dumps(
                [
                    {
                        "id": "job1",
                        "text": "AIP Deployment Strategist",
                        "hostedUrl": "https://jobs.example/job1",
                        "createdAt": 1781654400000,
                        "categories": {"department": "AIP", "team": "Platform", "location": "London"},
                    }
                ]
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

    coverage = MODULE.build_hiring_capacity_coverage_gate(
        context_rows=result["rows"],
        source_layer_rows=source_rows,
        generated_at="2026-06-17T00:00:00Z",
    )
    req = coverage["requirements"][0]
    assert req["requirement_id"] == "hiring_capacity_proxy"
    assert req["status"] == "pass"
    assert req["entity_bound_row_count"] == 1


def test_hiring_capacity_fetch_retries_transient_failure(tmp_path: Path) -> None:
    calls = 0

    def flaky_fetch(url: str, timeout_s: float) -> tuple[int, str, str]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("transient read failure")
        return (
            200,
            "application/json",
            json.dumps({"jobs": [{"title": "Security Platform Engineer", "departments": [{"name": "Security"}]}]}),
        )

    result = MODULE.build_hiring_capacity_context_rows(
        probes=[
            {
                "ticker": "NET",
                "company_name": "Cloudflare",
                "provider": "greenhouse",
                "board_token": "cloudflare",
                "company_names": ["Cloudflare"],
                "role_focus_terms": ["Security", "Platform"],
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
