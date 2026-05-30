from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from sec_agent.coverage_matrix import build_coverage_matrix
from sec_agent.query_contract import validate_query_contract
from sec_agent.retrieval_plan import build_retrieval_plan


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_interactive_module():
    path = REPO_ROOT / "scripts" / "cloud" / "sec_agent_interactive.py"
    spec = importlib.util.spec_from_file_location("sec_agent_interactive_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _load_synthesis_module():
    scripts_root = str(REPO_ROOT / "scripts")
    if scripts_root not in sys.path:
        sys.path.insert(0, scripts_root)
    path = REPO_ROOT / "scripts" / "run_sec_eval_synthesis_qwen9b_backend.py"
    spec = importlib.util.spec_from_file_location("sec_agent_synthesis_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_query_contract_accepts_industry_snapshot_as_context_only_source() -> None:
    inventory = {
        "inventory_digest": "industry-inv",
        "companies": [
            {
                "ticker": "NVDA",
                "company": "NVIDIA",
                "category": "semiconductor",
                "filings": [
                    {
                        "year": 2025,
                        "form_type": "10-K",
                        "source_tier": "primary_sec_filing",
                    }
                ],
            }
        ],
    }
    contract = {
        "task_type": "general_sec_financial_question",
        "search_scope_tickers": ["NVDA"],
        "focus_tickers": ["NVDA"],
        "years": [2025],
        "filing_types": ["10-K"],
        "source_tiers": ["primary_sec_filing", "industry_snapshot"],
        "industry_snapshot": {
            "required": True,
            "source_families": ["industry_macro_rates_credit"],
            "as_of_date": "2026-05-29",
        },
        "metric_families": ["revenue"],
        "decomposed_tasks": [
            {
                "task_id": "industry_context",
                "question_zh": "结合利率和行业背景解释基本面变化",
                "priority": "supporting",
                "required_tickers": ["NVDA"],
                "required_metric_families": ["revenue"],
            }
        ],
    }

    result = validate_query_contract(contract, selected_tickers=["NVDA"], selected_years=[2025], project_inventory=inventory)
    clean = result["contract"]

    assert result["report"]["status"] == "pass"
    assert "industry_snapshot" in clean["source_tiers"]
    assert any("industry snapshot" in caveat.lower() for caveat in clean["required_caveats"])
    assert any("company-reported revenue" in claim.lower() for claim in clean["forbidden_claims"])
    assert not any(caveat == "SEC-only evidence boundary." for caveat in clean["required_caveats"])


def test_retrieval_plan_includes_industry_snapshot_route_without_bge_budget() -> None:
    contract = {
        "source_policy": "SEC_PRIMARY_MIXED_WITH_8K_EARNINGS",
        "focus_tickers": ["NVDA"],
        "search_scope_tickers": ["NVDA"],
        "years": [2025],
        "filing_types": ["10-K", "8-K"],
        "source_tiers": ["primary_sec_filing", "company_authored_unaudited_sec_filing", "industry_snapshot"],
        "metric_families": ["revenue"],
        "industry_snapshot": {"required": True, "source_families": ["industry_industrial_macro"]},
        "decomposed_tasks": [
            {
                "task_id": "industry_backdrop",
                "question_zh": "用行业订单和制造业背景解释公司收入变化",
                "priority": "supporting",
                "required_tickers": ["NVDA"],
                "required_metric_families": ["revenue"],
            }
        ],
    }

    plan = build_retrieval_plan(contract)
    routes = [route for route in plan["routes"] if route["retrieval_route"] == "industry_snapshot"]

    assert (plan["retrieval_plan_validation"] or {})["status"] == "pass"
    assert routes
    assert routes[0]["source_tiers"] == ["industry_snapshot"]
    assert routes[0]["filing_types"] == []
    assert routes[0]["rerank_budget"] == 0


def test_coverage_matrix_requires_industry_only_for_industry_tasks() -> None:
    query_contract = {
        "source_policy": "SEC_PRIMARY_MIXED_WITH_8K_EARNINGS",
        "focus_tickers": ["NVDA"],
        "search_scope_tickers": ["NVDA"],
        "years": [2025],
        "filing_types": ["10-K"],
        "source_tiers": ["primary_sec_filing", "industry_snapshot"],
        "metric_families": ["revenue"],
        "industry_snapshot": {"required": True, "source_families": ["industry_macro_rates_credit"]},
        "decomposed_tasks": [
            {
                "task_id": "company_revenue",
                "question_zh": "分析公司收入变化",
                "priority": "primary",
                "required_tickers": ["NVDA"],
                "required_metric_families": ["revenue"],
            },
            {
                "task_id": "industry_rate_context",
                "question_zh": "结合宏观利率背景解释估值和需求环境",
                "priority": "supporting",
                "required_tickers": ["NVDA"],
                "required_metric_families": ["revenue"],
            },
        ],
    }
    ledger_rows = [
        {
            "metric_id": "m1",
            "ticker": "NVDA",
            "fiscal_year": 2025,
            "form_type": "10-K",
            "source_tier": "primary_sec_filing",
            "metric_family": "revenue",
            "source_evidence_id": "SEC::NVDA::2025::revenue",
        }
    ]
    context_rows = [
        {
            "source_tier": "industry_snapshot",
            "source_type": "industry_snapshot",
            "source_family": "industry_macro_rates_credit",
            "as_of_date": "2026-05-29",
            "evidence_id": "INDUSTRY::industry_macro_rates_credit::DGS10::2026-05-29",
            "text": "10-year Treasury yield context.",
        }
    ]

    coverage = build_coverage_matrix(
        case={"case_id": "industry-unit"},
        query_contract=query_contract,
        context_rows=context_rows,
        ledger_rows=ledger_rows,
    )
    company_task, industry_task = coverage["tasks"]

    assert "industry_snapshot" not in company_task["missing_source_tiers"]
    assert "industry_snapshot" in industry_task["covered_source_tiers"]
    assert industry_task["missing_industry_source_families"] == []
    assert coverage["industry_snapshot_coverage"]["industry_snapshot_support_complete"] is True


def test_interactive_loads_and_normalizes_industry_evidence_rows(tmp_path: Path) -> None:
    interactive = _load_interactive_module()
    path = tmp_path / "industry_evidence_rows.jsonl"
    row = {
        "source_family": "industry_macro_rates_credit",
        "provider": "FRED",
        "dataset_id": "fred/DGS10",
        "series_id": "DGS10",
        "as_of_date": "2026-05-29",
        "summary": "DGS10 latest value supports rate-cycle context.",
    }
    path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")

    rows = interactive._load_industry_context_rows(
        str(path),
        {
            "source_tiers": ["primary_sec_filing", "industry_snapshot"],
            "industry_snapshot": {
                "required": True,
                "source_families": ["industry_macro_rates_credit"],
                "as_of_date": "2026-05-29",
            },
        },
    )

    assert len(rows) == 1
    assert rows[0]["source_tier"] == "industry_snapshot"
    assert rows[0]["evidence_id"] == "INDUSTRY::industry_macro_rates_credit::DGS10::2026-05-29"
    assert "context_only" in rows[0]["source_boundary"]


def test_synthesis_prompt_includes_industry_snapshot_usage_rule() -> None:
    synthesis = _load_synthesis_module()
    prompt = synthesis._build_prompt(
        {
            "case_id": "industry-prompt",
            "prompt": "结合利率和行业背景分析 NVDA",
            "query_contract": {
                "source_tiers": ["primary_sec_filing", "industry_snapshot"],
                "industry_snapshot": {"required": True, "source_families": ["industry_macro_rates_credit"]},
            },
            "evidence_coverage_matrix": {
                "source_tiers": ["primary_sec_filing", "industry_snapshot"],
                "industry_snapshot_coverage": {"industry_snapshot_requested": True},
                "summary": {},
                "tasks": [],
            },
        },
        context_rows=[
            {
                "source_tier": "industry_snapshot",
                "source_family": "industry_macro_rates_credit",
                "provider": "FRED",
                "dataset_id": "fred/DGS10",
                "series_id": "DGS10",
                "as_of_date": "2026-05-29",
                "evidence_id": "INDUSTRY::industry_macro_rates_credit::DGS10::2026-05-29",
                "text": "DGS10 latest value supports rate-cycle context.",
            }
        ],
        ledger_rows=[],
    )

    assert "Industry Snapshot Usage Rule" in prompt
    assert "industry_snapshot evidence_ids" in prompt
    assert "不得覆盖 SEC Exact-Value Ledger 中的公司财报事实" in prompt
