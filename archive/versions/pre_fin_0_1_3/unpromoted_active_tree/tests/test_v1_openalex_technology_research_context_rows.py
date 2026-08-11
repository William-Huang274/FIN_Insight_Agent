from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "data_expansion" / "build_v1_openalex_technology_research_context_rows.py"
SPEC = importlib.util.spec_from_file_location("build_v1_openalex_technology_research_context_rows", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_openalex_rows_require_issuer_and_topic_binding(tmp_path: Path) -> None:
    payload = {
        "results": [
            {
                "id": "https://openalex.org/W1",
                "title": "NVIDIA CUDA software and GPU parallel computing architecture",
                "publication_year": 2025,
                "cited_by_count": 12,
                "concepts": [{"display_name": "CUDA"}, {"display_name": "Parallel computing"}],
                "authorships": [{"institutions": [{"display_name": "Nvidia"}]}],
            },
            {
                "id": "https://openalex.org/W2",
                "title": "Generic EUV lithography review without issuer",
                "publication_year": 2024,
                "cited_by_count": 9,
                "concepts": [{"display_name": "EUV"}],
                "authorships": [{"institutions": [{"display_name": "University"}]}],
            },
        ]
    }

    def fake_fetch(url: str, timeout_s: float) -> tuple[int, str, str]:
        assert "api.openalex.org/works" in url
        assert timeout_s == 2
        return 200, "application/json", json.dumps(payload)

    result = MODULE.build_v1_openalex_technology_research_context_rows(
        probes=[
            {
                "ticker": "NVDA",
                "company_name": "NVIDIA",
                "company_names": ["NVIDIA", "Nvidia"],
                "product_terms": ["CUDA", "GPU"],
                "search_query": "NVIDIA CUDA GPU",
            }
        ],
        generated_at="2026-06-17T00:00:00Z",
        raw_dir=tmp_path,
        timeout_s=2,
        max_rows_per_company=3,
        fetch=fake_fetch,
    )

    rows = result["rows"]
    assert len(rows) == 1
    row = rows[0]
    assert row["source_id"] == MODULE.SOURCE_ID
    assert row["source_layer_id"] == "L3"
    assert row["structured_context_type"] == "technology_research_proxy_context"
    assert row["issuer_binding_status"] == "issuer_mentioned_in_snapshot"
    assert row["product_binding_status"] == "technology_topic_bound"
    assert row["exact_value_authority"] is False
    assert "product_launch" in row["forbidden_claims"]
    assert Path(row["raw_path"]).exists()
    attempt = result["attempts"][0]
    assert attempt["source_id"] == MODULE.SOURCE_ID
    assert attempt["provider"] == "openalex"
    assert attempt["status"] == "materialized"


def test_v1_openalex_coverage_gate_passes_with_bound_rows(tmp_path: Path) -> None:
    result = MODULE.build_v1_openalex_technology_research_context_rows(
        probes=[
            {
                "ticker": "AMD",
                "company_name": "Advanced Micro Devices",
                "company_names": ["AMD"],
                "product_terms": ["ROCm", "GPU"],
                "search_query": "AMD ROCm GPU",
            }
        ],
        generated_at="2026-06-17T00:00:00Z",
        raw_dir=tmp_path,
        fetch=lambda url, timeout_s: (
            200,
            "application/json",
            json.dumps(
                {
                    "results": [
                        {
                            "id": "https://openalex.org/W3",
                            "title": "Designing a ROCm-Aware MPI Library for AMD GPUs",
                            "publication_year": 2025,
                            "cited_by_count": 3,
                            "concepts": [{"display_name": "ROCm"}, {"display_name": "GPU"}],
                            "authorships": [],
                        }
                    ]
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

    coverage = MODULE.build_v1_openalex_coverage_gate(
        context_rows=result["rows"],
        source_layer_rows=source_rows,
        generated_at="2026-06-17T00:00:00Z",
    )
    req = coverage["requirements"][0]
    assert req["requirement_id"] == "technology_research_proxy"
    assert req["status"] == "pass"
    assert req["entity_bound_row_count"] == 1


def test_openalex_attempts_are_deduped_for_persistent_closeout() -> None:
    attempts = MODULE._dedupe_attempts(
        [
            {"ticker": "AMD", "api_url": "https://api.openalex.org/works?search=AMD", "status": "no_issuer_topic_bound_works"},
            {"ticker": "AMD", "api_url": "https://api.openalex.org/works?search=AMD", "status": "no_issuer_topic_bound_works"},
            {"ticker": "AMD", "api_url": "https://api.openalex.org/works?search=AMD+ROCm", "status": "no_issuer_topic_bound_works"},
        ]
    )

    assert len(attempts) == 2


def test_openalex_family_plan_uses_company_alias_overrides_for_issuer_binding() -> None:
    probes = MODULE.openalex_probes_from_family_route_plan(
        [
            {
                "route_id": "technology_research_proxy",
                "ticker": "GOOGL",
                "company_name": "Alphabet Inc. (Class A)",
                "family_name": "AI infrastructure",
                "query_terms": ["TPU", "machine learning accelerator"],
            }
        ],
        tickers=["GOOGL"],
    )

    assert len(probes) == 1
    probe = probes[0]
    assert "Google" in probe["company_names"]
    assert probe["search_query"].startswith("Google ")

    rows = MODULE.technology_rows_from_openalex_payload(
        {
            "results": [
                {
                    "id": "https://openalex.org/WGOOG",
                    "title": "Google TPU machine learning accelerator systems",
                    "publication_year": 2024,
                    "cited_by_count": 8,
                    "concepts": [{"display_name": "TPU"}, {"display_name": "machine learning accelerator"}],
                    "authorships": [{"institutions": [{"display_name": "Google"}]}],
                }
            ]
        },
        probe=probe,
        api_url="https://api.openalex.org/works?search=Google+TPU",
        raw_path=Path("raw.json"),
        generated_at="2026-06-17T00:00:00Z",
        max_rows=3,
    )
    assert len(rows) == 1
    assert "Google" in rows[0]["entity_binding"]["issuer_matched_terms"]


def test_openalex_family_plan_uses_ticker_topic_overrides_for_misclassified_routes() -> None:
    probes = MODULE.openalex_probes_from_family_route_plan(
        [
            {
                "route_id": "technology_research_proxy",
                "ticker": "TER",
                "company_name": "Teradyne",
                "family_name": "Semicap Equipment",
                "query_terms": ["EUV", "lithography", "etch"],
            }
        ],
        tickers=["TER"],
    )

    assert len(probes) == 1
    probe = probes[0]
    assert "semiconductor test" in probe["product_terms"]
    assert "lithography" not in probe["search_query"]
