from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_eval_module():
    path = REPO_ROOT / "scripts" / "eval_sec_benchmark" / "run_sec_benchmark_eval.py"
    spec = importlib.util.spec_from_file_location("run_sec_benchmark_eval_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _load_coverage_module():
    path = REPO_ROOT / "src" / "sec_agent" / "coverage_matrix.py"
    spec = importlib.util.spec_from_file_location("coverage_matrix_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_mixed_recent_source_resolver_allows_sparse_10q_inventory() -> None:
    module = _load_eval_module()
    case = {
        "companies": ["MSFT"],
        "years": [2025, 2026],
        "filing_types": ["10-K", "10-Q"],
        "source_policy": "SEC_PRIMARY_MIXED_RECENT",
        "query_contract": {"source_policy": "SEC_PRIMARY_MIXED_RECENT", "filing_types": ["10-K", "10-Q"]},
    }
    manifest_index = {
        ("MSFT", 2025, "10-K"): {"ticker": "MSFT", "fiscal_year": 2025, "form_type": "10-K"},
        ("MSFT", 2026, "10-Q"): {"ticker": "MSFT", "fiscal_year": 2026, "form_type": "10-Q"},
    }

    resolver = module._source_resolver(case, manifest_index)

    assert resolver["status"] == "partial"
    assert resolver["available_count"] == 2
    assert resolver["missing_count"] == 2
    assert not module._source_missing_is_fatal(case, resolver)


def test_10k_only_source_resolver_keeps_missing_filing_fatal() -> None:
    module = _load_eval_module()
    case = {
        "companies": ["MSFT"],
        "years": [2025, 2026],
        "filing_types": ["10-K"],
        "source_policy": "SEC_ONLY_10K",
        "query_contract": {"source_policy": "SEC_ONLY_10K", "filing_types": ["10-K"]},
    }
    manifest_index = {
        ("MSFT", 2025, "10-K"): {"ticker": "MSFT", "fiscal_year": 2025, "form_type": "10-K"},
    }

    resolver = module._source_resolver(case, manifest_index)

    assert resolver["status"] == "partial"
    assert module._source_missing_is_fatal(case, resolver)


def test_source_resolver_uses_retrieval_plan_route_scope_for_mixed_10k_8k() -> None:
    module = _load_eval_module()
    case = {
        "companies": ["NVDA", "AMD"],
        "years": [2025, 2026],
        "filing_types": ["10-K", "8-K"],
        "source_policy": "SEC_PRIMARY_MIXED_WITH_8K_EARNINGS",
        "query_contract": {
            "source_policy": "SEC_PRIMARY_MIXED_WITH_8K_EARNINGS",
            "filing_types": ["10-K", "8-K"],
            "source_tiers": ["primary_sec_filing", "company_authored_unaudited_sec_filing"],
        },
        "retrieval_plan": {
            "schema_version": "sec_agent_retrieval_plan_v0.1",
            "retrieval_plan_validation": {"status": "pass"},
            "routes": [
                {
                    "route_id": "fundamental::filing_text",
                    "retrieval_route": "filing_text",
                    "tickers": ["NVDA", "AMD"],
                    "years": [2025],
                    "filing_types": ["10-K"],
                    "source_tiers": ["primary_sec_filing"],
                },
                {
                    "route_id": "management::8k_commentary",
                    "retrieval_route": "8k_commentary",
                    "tickers": ["NVDA", "AMD"],
                    "years": [2026],
                    "filing_types": ["8-K"],
                    "source_tiers": ["company_authored_unaudited_sec_filing"],
                },
            ],
        },
    }
    manifest_index = {
        ("NVDA", 2025, "10-K"): {"ticker": "NVDA", "fiscal_year": 2025, "form_type": "10-K"},
        ("AMD", 2025, "10-K"): {"ticker": "AMD", "fiscal_year": 2025, "form_type": "10-K"},
        ("NVDA", 2026, "8-K"): {"ticker": "NVDA", "fiscal_year": 2026, "form_type": "8-K"},
        ("AMD", 2026, "8-K"): {"ticker": "AMD", "fiscal_year": 2026, "form_type": "8-K"},
    }

    resolver = module._source_resolver(case, manifest_index)

    assert resolver["status"] == "complete"
    assert resolver["available_count"] == 4
    assert resolver["missing_count"] == 0
    assert not module._source_missing_is_fatal(case, resolver)
    assert {item["retrieval_route"] for item in resolver["available_filings"]} == {"filing_text", "8k_commentary"}


def test_requirement_queries_prioritize_qualitative_evidence_over_policy_traps() -> None:
    module = _load_eval_module()
    case = {
        "task_type": "single_or_multi_company_interactive",
        "query_contract": {
            "qualitative_queries": ["AI infrastructure demand data center capacity risk"],
            "decomposed_tasks": [
                {
                    "question_zh": "云收入增长是否伴随资本开支和现金流压力？",
                    "required_metric_families": ["cloud_revenue", "capital_expenditure_proxy", "operating_cash_flow"],
                }
            ],
            "facets": ["profitability_and_margin_pressure"],
        },
        "gold_points": ["All precise numeric values must come from the runtime Exact-Value Ledger."],
        "hallucination_traps": ["Do not use non-SEC sources."],
    }

    queries = module._requirement_queries(case)

    assert "AI infrastructure demand data center capacity risk" in queries
    assert any("cloud revenue" in query or "capital expenditure" in query for query in queries)
    assert "Do not use non-SEC sources." not in queries
    assert not any("Exact-Value Ledger" in query for query in queries)


def test_coverage_matrix_treats_capex_family_alias_as_supported() -> None:
    module = _load_coverage_module()
    matrix = module.build_coverage_matrix(
        case={"case_id": "case", "years": [2025]},
        query_contract={
            "task_type": "company_comparison",
            "focus_tickers": ["MSFT"],
            "years": [2025],
            "filing_types": ["10-K"],
            "source_tiers": ["primary_sec_filing"],
            "decomposed_tasks": [
                {
                    "task_id": "capex_check",
                    "priority": "primary",
                    "required_tickers": ["MSFT"],
                    "required_metric_families": ["capex"],
                }
            ],
        },
        context_rows=[],
        ledger_rows=[
            {
                "metric_id": "m1",
                "ticker": "MSFT",
                "fiscal_year": 2025,
                "form_type": "10-K",
                "source_tier": "primary_sec_filing",
                "metric_family": "capital_expenditure_proxy",
                "source_evidence_id": "e1",
            }
        ],
    )

    task = matrix["tasks"][0]
    assert task["missing_metric_families"] == []
    assert "capex" in task["covered_metric_families"]
    assert "capital_expenditure_proxy" in task["covered_metric_families"]
