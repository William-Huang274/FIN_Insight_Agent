from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "data_expansion" / "build_developer_ecosystem_context_rows.py"
SPEC = importlib.util.spec_from_file_location("build_developer_ecosystem_context_rows", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_developer_api_url_expands_supported_public_urls() -> None:
    assert MODULE.developer_api_url("https://github.com/microsoft/vscode") == (
        "https://api.github.com/repos/microsoft/vscode",
        "github",
    )
    assert MODULE.developer_api_url("https://www.npmjs.com/package/@azure/identity") == (
        "https://registry.npmjs.org/@azure/identity",
        "npm",
    )
    assert MODULE.developer_api_url("https://pypi.org/project/google-cloud-aiplatform/") == (
        "https://pypi.org/pypi/google-cloud-aiplatform/json",
        "pypi",
    )
    assert MODULE.developer_api_url("https://huggingface.co/google/gemma-2-2b") == (
        "https://huggingface.co/api/models/google/gemma-2-2b",
        "huggingface",
    )


def test_build_developer_ecosystem_context_rows_with_fixture_fetch(tmp_path: Path) -> None:
    payloads = {
        "https://api.github.com/repos/microsoft/vscode": {
            "full_name": "microsoft/vscode",
            "name": "vscode",
            "stargazers_count": 100,
            "forks_count": 20,
            "pushed_at": "2026-06-01T00:00:00Z",
        },
        "https://registry.npmjs.org/@azure/identity": {
            "name": "@azure/identity",
            "dist-tags": {"latest": "4.0.0"},
            "time": {"modified": "2026-06-01T00:00:00.000Z"},
        },
    }

    def fake_fetch(url: str, timeout_s: float) -> tuple[int, str, str]:
        assert timeout_s == 2
        return 200, "application/json", json.dumps(payloads[url])

    result = MODULE.build_developer_ecosystem_context_rows(
        probes=[
            {
                "ticker": "MSFT",
                "company_name": "Microsoft",
                "company_names": ["Microsoft", "Azure"],
                "product_terms": ["vscode", "@azure/identity"],
                "urls": ["https://github.com/microsoft/vscode", "https://www.npmjs.com/package/@azure/identity"],
            }
        ],
        generated_at="2026-06-16T00:00:00Z",
        raw_dir=tmp_path,
        timeout_s=2,
        max_rows_per_probe=3,
        fetch=fake_fetch,
    )
    rows = result["rows"]
    assert len(rows) == 2
    assert {row["provider"] for row in rows} == {"github", "npm"}
    assert all(row["source_id"] == MODULE.SOURCE_ID for row in rows)
    assert all(row["source_layer_id"] == "L3" for row in rows)
    assert all(row["exact_value_authority"] is False for row in rows)
    assert all(row["issuer_binding_status"] == "issuer_mentioned_in_snapshot" for row in rows)
    assert all(row["product_binding_status"] == "product_mentioned_in_snapshot" for row in rows)
    assert all(Path(row["raw_path"]).exists() for row in rows)


def test_developer_ecosystem_coverage_gate_passes_with_bound_rows(tmp_path: Path) -> None:
    result = MODULE.build_developer_ecosystem_context_rows(
        probes=[
            {
                "ticker": "NVDA",
                "company_name": "NVIDIA",
                "company_names": ["NVIDIA"],
                "product_terms": ["NVIDIA/cuda-samples", "cuda-samples"],
                "urls": ["https://github.com/NVIDIA/cuda-samples"],
            }
        ],
        generated_at="2026-06-16T00:00:00Z",
        raw_dir=tmp_path,
        fetch=lambda url, timeout_s: (
            200,
            "application/json",
            json.dumps(
                {
                    "full_name": "NVIDIA/cuda-samples",
                    "name": "cuda-samples",
                    "stargazers_count": 10,
                    "forks_count": 2,
                    "pushed_at": "2026-06-01T00:00:00Z",
                }
            ),
        ),
    )
    source_rows = [
        {
            "source_id": MODULE.SOURCE_ID,
            "layer_id": "L3",
            "evidence_graph_status": "structured_not_promoted",
            "can_crawl_or_download": True,
            "can_structure": True,
            "runtime_ready_context": False,
            "exact_value_authority_ready": False,
            "can_support_company_exact_fact": False,
        }
    ]
    coverage = MODULE.build_developer_ecosystem_coverage_gate(
        context_rows=result["rows"],
        source_layer_rows=source_rows,
        generated_at="2026-06-16T00:00:00Z",
    )
    req = coverage["requirements"][0]
    assert req["requirement_id"] == "developer_ecosystem_proxy"
    assert req["status"] == "pass"
    assert req["entity_bound_row_count"] == 1


def test_developer_ecosystem_fetch_retries_transient_read_failure(tmp_path: Path) -> None:
    calls = 0

    def flaky_fetch(url: str, timeout_s: float) -> tuple[int, str, str]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("transient incomplete read")
        return (
            200,
            "application/json",
            json.dumps(
                {
                    "name": "@salesforce/cli",
                    "dist-tags": {"latest": "2.0.0"},
                    "time": {"modified": "2026-06-01T00:00:00.000Z"},
                }
            ),
        )

    result = MODULE.build_developer_ecosystem_context_rows(
        probes=[
            {
                "ticker": "CRM",
                "company_name": "Salesforce",
                "company_names": ["Salesforce"],
                "product_terms": ["@salesforce/cli", "Salesforce CLI"],
                "urls": ["https://www.npmjs.com/package/@salesforce/cli"],
            }
        ],
        generated_at="2026-06-16T00:00:00Z",
        raw_dir=tmp_path,
        timeout_s=2,
        fetch_retries=1,
        fetch=flaky_fetch,
    )

    assert calls == 2
    assert len(result["rows"]) == 1
    assert result["attempts"][0]["status"] == "materialized"


def test_developer_ecosystem_github_api_rate_limit_uses_html_fallback(tmp_path: Path) -> None:
    api_url = "https://api.github.com/repos/vmware/govmomi"
    source_url = "https://github.com/vmware/govmomi"

    def fake_fetch(url: str, timeout_s: float) -> tuple[int, str, str]:
        if url == api_url:
            return 403, "application/json", '{"message":"API rate limit exceeded"}'
        if url == source_url:
            return (
                200,
                "text/html",
                """
                <html><head>
                  <title>GitHub - vmware/govmomi: Go library for the VMware vSphere API</title>
                  <meta property="og:description" content="Go library for the VMware vSphere API" />
                </head><body>
                  <span id="repo-stars-counter-star" title="2,504">2.5k</span>
                  <a href="/vmware/govmomi/forks"><strong>958</strong> forks</a>
                </body></html>
                """,
            )
        raise AssertionError(f"unexpected url: {url}")

    result = MODULE.build_developer_ecosystem_context_rows(
        probes=[
            {
                "ticker": "AVGO",
                "company_name": "Broadcom",
                "company_names": ["Broadcom", "VMware"],
                "product_terms": ["VMware vSphere", "govmomi"],
                "urls": [source_url],
            }
        ],
        generated_at="2026-06-16T00:00:00Z",
        raw_dir=tmp_path,
        fetch=fake_fetch,
    )

    assert len(result["rows"]) == 1
    assert result["rows"][0]["provider"] == "github"
    assert result["rows"][0]["payload_source_url"] == source_url
    assert result["rows"][0]["issuer_binding_status"] == "issuer_mentioned_in_snapshot"
    assert result["rows"][0]["product_binding_status"] == "product_mentioned_in_snapshot"
    assert result["attempts"][0]["status"] == "github_api_fallback_html_materialized"
    assert result["attempts"][1]["status"] == "materialized"


def test_developer_ecosystem_rows_expose_unsupported_urls_without_rows(tmp_path: Path) -> None:
    called = False

    def fake_fetch(url: str, timeout_s: float) -> tuple[int, str, str]:
        nonlocal called
        called = True
        return 200, "application/json", "{}"

    result = MODULE.build_developer_ecosystem_context_rows(
        probes=[
            {
                "ticker": "MSFT",
                "company_name": "Microsoft",
                "company_names": ["Microsoft"],
                "product_terms": ["Azure"],
                "urls": ["https://example.com/not-a-supported-developer-source"],
            }
        ],
        generated_at="2026-06-16T00:00:00Z",
        raw_dir=tmp_path,
        fetch=fake_fetch,
    )
    assert called is False
    assert result["rows"] == []
    assert result["attempts"][0]["status"] == "unsupported_url"
