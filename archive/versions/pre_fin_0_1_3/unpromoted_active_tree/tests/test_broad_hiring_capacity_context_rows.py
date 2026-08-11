from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "data_expansion"
    / "build_broad_hiring_capacity_context_rows.py"
)
SPEC = importlib.util.spec_from_file_location("build_broad_hiring_capacity_context_rows", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_parse_ashby_jobs_into_bound_hiring_rows() -> None:
    rows = MODULE.parse_jobs(
        {"ticker": "TST", "company_name": "TestCo"},
        provider="ashby",
        token="testco",
        url="https://api.ashbyhq.com/posting-api/job-board/testco",
        payload={
            "jobs": [
                {
                    "title": "AI Platform Engineer",
                    "location": "San Francisco",
                    "department": "Engineering",
                    "publishedAt": "2026-06-01T00:00:00Z",
                    "jobUrl": "https://jobs.example/ai-platform",
                }
            ]
        },
        generated_at="2026-06-18T00:00:00Z",
        max_jobs=1,
    )

    assert len(rows) == 1
    assert rows[0]["source_id"] == "job_postings_hiring_signals"
    assert rows[0]["provider"] == "ashby"
    assert rows[0]["job_location"] == "San Francisco"
    assert rows[0]["issuer_binding_status"] == "issuer_mentioned_in_snapshot"
    assert rows[0]["product_binding_status"] == "product_mentioned_in_snapshot"


def test_parse_smartrecruiters_jobs_into_bound_hiring_rows() -> None:
    rows = MODULE.parse_jobs(
        {"ticker": "V", "company_name": "Visa"},
        provider="smartrecruiters",
        token="Visa",
        url="https://api.smartrecruiters.com/v1/companies/Visa/postings?limit=25",
        payload={
            "content": [
                {
                    "name": "Director, AI Platform",
                    "releasedDate": "2026-06-03T11:08:12Z",
                    "location": {"city": "Bengaluru", "region": "KA", "country": "India", "fullLocation": "Bengaluru, KA, India"},
                    "department": {"label": "Technology"},
                    "applyUrl": "https://jobs.smartrecruiters.com/Visa/123",
                }
            ]
        },
        generated_at="2026-06-18T00:00:00Z",
        max_jobs=1,
    )

    assert len(rows) == 1
    assert rows[0]["provider"] == "smartrecruiters"
    assert rows[0]["job_department"] == "Technology"
    assert rows[0]["source_url"].startswith("https://api.smartrecruiters.com/")


def test_known_board_tokens_include_verified_hubspot_greenhouse_board() -> None:
    urls = MODULE.board_token_candidates("HUBS", "HubSpot Inc.")

    assert urls[0] == (
        "greenhouse",
        "hubspotjobs",
        "https://boards-api.greenhouse.io/v1/boards/hubspotjobs/jobs?content=true",
    )
