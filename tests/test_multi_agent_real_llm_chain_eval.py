from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "multi_agent_real_llm_chain_cases_v0_1.jsonl"
FULL_CHAIN_MULTITURN_FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "fin_agent_full_chain_multiturn_cases_v0_1.jsonl"
SCRIPT_PATH = REPO_ROOT / "scripts" / "eval_multi_agent" / "eval_multi_agent_real_llm_chain.py"


def test_multi_agent_real_llm_chain_fixture_schema() -> None:
    rows = _read_jsonl(FIXTURE_PATH)

    assert len(rows) == 10
    assert {row["category"] for row in rows} == {"detailed_probe", "single_turn", "multi_turn", "sector_depth"}
    assert any(row.get("detailed_probe") for row in rows)
    assert any(row.get("conversation_id") for row in rows)
    assert all(row["case_id"].startswith("ma_real_") for row in rows)
    assert any(row["expected_execution_mode"] == "deep_research" for row in rows)
    assert sum(1 for row in rows if row.get("require_real_retrieval_pass")) == 4
    sector_cases = [row for row in rows if row["category"] == "sector_depth"]
    assert all(row.get("expected_relationship_pack_ids") for row in sector_cases)
    assert all(row.get("require_rendered_memo_claims") for row in sector_cases)
    assert all(row.get("require_rendered_evidence_refs") for row in sector_cases)


def test_fin_agent_full_chain_multiturn_fixture_schema() -> None:
    rows = _read_jsonl(FULL_CHAIN_MULTITURN_FIXTURE_PATH)

    assert len(rows) == 20
    assert {row["category"] for row in rows} >= {"exact_lookup", "focused_answer", "standard_memo", "sector_depth", "multi_turn"}
    assert sum(1 for row in rows if row.get("category") == "scope_decision") == 3
    assert any(row.get("response_language") == "en-US" for row in rows)
    assert sum(1 for row in rows if row.get("conversation_id")) >= 4
    assert sum(1 for row in rows if row.get("require_real_retrieval_pass")) >= 5
    assert all(row["case_id"].startswith("fin_full_") for row in rows)
    assert all(row.get("response_language") for row in rows)
    scope_cases = [row for row in rows if row.get("require_scope_decision_contract")]
    assert len(scope_cases) == 3
    assert all(row.get("expected_scoping_patterns") for row in scope_cases)
    assert all(row.get("expected_expansion_modes") for row in scope_cases)
    assert all(row.get("expected_catalogs_to_inspect") for row in scope_cases)
    assert all(row.get("expected_candidate_lenses") for row in scope_cases)
    assert all(row.get("max_total_tokens_lte") for row in scope_cases)
    exact_cases = [row for row in rows if row.get("category") == "exact_lookup"]
    assert all(row.get("require_lead_llm_pass") is False for row in exact_cases)
    sector_cases = [row for row in rows if row["category"] == "sector_depth"]
    assert all(row.get("expected_relationship_pack_ids") for row in sector_cases)
    assert all(row.get("require_rendered_memo_claims") for row in sector_cases)
    assert all(row.get("require_rendered_evidence_refs") for row in sector_cases)


def test_api_key_marker_detection_ignores_plain_english_sk_sequence() -> None:
    module = _load_script_module()

    assert module._contains_api_key_marker("Risk-balanced memo requires downside checks.") is False
    assert module._contains_api_key_marker("leaked sk-1234567890abcdef1234567890abcdef marker") is True


def test_deep_research_default_performance_budget_allows_quality_second_pass_latency() -> None:
    module = _load_script_module()

    assert module._default_performance_limits({"expected_execution_mode": "deep_research"})["max_case_elapsed_ms_lte"] == 360_000


def test_multi_agent_real_llm_chain_scoring_accepts_layered_success() -> None:
    module = _load_script_module()
    case = _read_jsonl(FIXTURE_PATH)[0]
    result = {
        "status": "completed",
        "agent_activation_plan": {
            "execution_mode": "focused_answer",
            "activate_agents": [
                "research_lead",
                "sec_operator",
                "eight_k_operator",
                "coverage_reflection",
                "memo_writer",
                "verifier",
                "renderer",
            ],
            "focus_tickers": ["AMZN"],
            "search_scope_tickers": ["AMZN"],
        },
        "agent_activation_validation": {"status": "pass"},
        "tool_call_ledger": {
            "records": [
                {"agent_id": "sec_operator", "tool_name": "sec_search_filings", "status": "dry_run", "row_count": 1},
                {"agent_id": "eight_k_operator", "tool_name": "sec_search_filings", "status": "dry_run", "row_count": 1},
            ]
        },
        "memo_answer": {"answer_status": "draft", "bounded_answer_allowed": False},
        "memo_route_result": {"status": "pass", "attempt_count": 1},
        "claim_verification": {
            "status": "pass",
            "verifier_input_projection": {
                "projection_policy": "final_memo_claims_and_referenced_evidence_only",
                "projected_claim_count": 2,
            },
        },
        "rendered_answer": "bounded rendered answer",
    }
    summary = {
        "payload_policy": {"raw_evidence": "not_included"},
        "llm_routes": {
            "research_lead": {"diagnostics": _ok_diag()},
            "memo_writer": {"diagnostics": _ok_diag()},
            "verifier": {"diagnostics": _ok_diag()},
        },
    }

    score = module.score_case(case, result, summary, {}, elapsed_ms=12)

    assert score["gate_status"] == "pass"
    assert all(score["checks"].values())
    assert score["agent_audit"]["research_lead"]["validation_status"] == "pass"
    assert score["agent_audit"]["verifier"]["input_projection"]["projected_claim_count"] == 2


def test_exact_lookup_real_retrieval_accepts_structured_ledger_first_without_bge_rerank() -> None:
    module = _load_script_module()
    case = {
        "case_id": "fin_full_exact_unit",
        "category": "exact_lookup",
        "expected_execution_mode": "deterministic_lookup",
        "required_agents": ["sec_operator", "renderer"],
        "expected_operator_agents": ["sec_operator"],
        "expected_tool_names": ["sec_search_filings", "sec_query_exact_value_ledger"],
        "require_real_retrieval_pass": True,
        "require_runtime_ledger_rows": True,
        "max_tool_calls_total_lte": 2,
    }
    result = {
        "status": "completed",
        "agent_activation_plan": {
            "execution_mode": "deterministic_lookup",
            "activate_agents": ["sec_operator", "renderer"],
            "focus_tickers": ["MSFT"],
            "search_scope_tickers": ["MSFT"],
        },
        "agent_activation_validation": {"status": "pass"},
        "context_rows": [{"evidence_ref": "ctx_1"}],
        "runtime_ledger_rows": [{"metric_id": "m1", "source_family": "primary_sec_filing"}],
        "tool_call_ledger": {
            "records": [
                {
                    "agent_id": "sec_operator",
                    "tool_name": "sec_search_filings",
                    "status": "ok",
                    "row_count": 4,
                    "metadata": {
                        "runtime_summary": {
                            "candidate_counts": {
                                "candidate_row_count_pre_rerank": 4,
                                "candidate_sent_to_bge": 0,
                                "route_candidate_stats": [
                                    {"retrieval_route": "ledger_first", "candidate_count": 4, "rerank_eligible_count": 0}
                                ],
                            }
                        }
                    },
                }
            ]
        },
        "rendered_answer": "单指标结果：MSFT capex。证据=ctx_1",
    }
    summary = {"payload_policy": {"raw_evidence": "not_included"}}

    score = module.score_case(case, result, summary, {}, elapsed_ms=1)

    assert score["gate_status"] == "pass"
    assert score["checks"]["evidence_operators.sec_search_bge_rerank_present"] is True
    assert score["checks"]["evidence_operators.sec_search_runtime_ledger_rows_present"] is True


def test_real_llm_chain_tool_budget_excludes_cached_calls() -> None:
    module = _load_script_module()
    case = {
        "case_id": "cached_budget_unit",
        "category": "standard_memo",
        "expected_execution_mode": "standard_memo",
        "required_agents": ["research_lead", "sec_operator", "memo_writer", "renderer"],
        "expected_operator_agents": ["sec_operator"],
        "expected_tool_names": ["sec_search_filings"],
        "max_tool_calls_total_lte": 1,
    }
    result = {
        "status": "completed",
        "agent_activation_plan": {
            "execution_mode": "standard_memo",
            "activate_agents": ["research_lead", "sec_operator", "memo_writer", "renderer"],
        },
        "agent_activation_validation": {"status": "pass"},
        "tool_call_ledger": {
            "records": [
                {"agent_id": "sec_operator", "tool_name": "sec_search_filings", "status": "ok", "row_count": 2},
                {"agent_id": "sec_operator", "tool_name": "sec_search_filings", "status": "cached", "row_count": 2},
                {"agent_id": "sec_operator", "tool_name": "sec_search_filings", "status": "cached", "row_count": 2},
            ]
        },
        "memo_answer": {"answer_status": "draft"},
        "rendered_answer": "bounded answer",
    }
    summary = {"payload_policy": {"raw_evidence": "not_included"}}

    score = module.score_case(case, result, summary, {}, elapsed_ms=1)

    assert score["tool_call_count"] == 3
    assert score["budgeted_tool_call_count"] == 1
    assert score["cached_tool_call_count"] == 2
    assert score["checks"]["evidence_operators.tool_budget_lte"] is True


def test_multi_agent_real_llm_chain_scoring_rejects_memo_fallback_from_summary() -> None:
    module = _load_script_module()
    case = _read_jsonl(FIXTURE_PATH)[0]
    result = {
        "status": "completed",
        "agent_activation_plan": {
            "execution_mode": "focused_answer",
            "activate_agents": [
                "research_lead",
                "sec_operator",
                "eight_k_operator",
                "coverage_reflection",
                "memo_writer",
                "verifier",
                "renderer",
            ],
            "focus_tickers": ["AMZN"],
            "search_scope_tickers": ["AMZN"],
        },
        "agent_activation_validation": {"status": "pass"},
        "tool_call_ledger": {
            "records": [
                {"agent_id": "sec_operator", "tool_name": "sec_search_filings", "status": "dry_run", "row_count": 1},
                {"agent_id": "eight_k_operator", "tool_name": "sec_search_filings", "status": "dry_run", "row_count": 1},
            ]
        },
        "memo_answer": {"answer_status": "draft", "bounded_answer_allowed": False},
        "claim_verification": {"status": "pass"},
        "rendered_answer": "fallback rendered answer",
    }
    summary = {
        "payload_policy": {"raw_evidence": "not_included"},
        "llm_routes": {
            "research_lead": {"diagnostics": _ok_diag()},
            "memo_writer": {"route_result": {"status": "fallback"}, "diagnostics": _ok_diag()},
            "verifier": {"diagnostics": _ok_diag()},
        },
    }

    score = module.score_case(case, result, summary, {}, elapsed_ms=12)

    assert score["gate_status"] == "fail"
    assert score["checks"]["memo_verifier.memo_llm_pass"] is False


def test_multi_agent_real_llm_chain_scoring_requires_rendered_claim_refs_when_configured() -> None:
    module = _load_script_module()
    case = {
        **_read_jsonl(FIXTURE_PATH)[0],
        "require_rendered_memo_claims": True,
        "require_rendered_evidence_refs": True,
    }
    result = {
        "status": "completed",
        "agent_activation_plan": {
            "execution_mode": "focused_answer",
            "activate_agents": [
                "research_lead",
                "sec_operator",
                "eight_k_operator",
                "coverage_reflection",
                "memo_writer",
                "verifier",
                "renderer",
            ],
            "focus_tickers": ["AMZN"],
            "search_scope_tickers": ["AMZN"],
        },
        "agent_activation_validation": {"status": "pass"},
        "tool_call_ledger": {
            "records": [
                {"agent_id": "sec_operator", "tool_name": "sec_search_filings", "status": "dry_run", "row_count": 1},
                {"agent_id": "eight_k_operator", "tool_name": "sec_search_filings", "status": "dry_run", "row_count": 1},
            ]
        },
        "memo_answer": {
            "answer_status": "draft",
            "bounded_answer_allowed": False,
            "memo_claims": [{"claim": "Supported claim.", "evidence_refs": ["ref_1"]}],
        },
        "memo_route_result": {"status": "pass", "attempt_count": 1},
        "claim_verification": {"status": "pass"},
        "rendered_answer": "Supported claim without rendered refs.",
    }
    summary = {
        "payload_policy": {"raw_evidence": "not_included"},
        "llm_routes": {
            "research_lead": {"diagnostics": _ok_diag()},
            "memo_writer": {"diagnostics": _ok_diag()},
            "verifier": {"diagnostics": _ok_diag()},
        },
    }

    score = module.score_case(case, result, summary, {}, elapsed_ms=12)

    assert score["gate_status"] == "fail"
    assert score["checks"]["memo_verifier.rendered_answer_has_memo_claims"] is False
    assert score["checks"]["memo_verifier.rendered_answer_has_evidence_refs"] is False


def test_real_llm_chain_scoring_accepts_chinese_rendered_claim_refs_and_language() -> None:
    module = _load_script_module()
    case = {
        **_read_jsonl(FULL_CHAIN_MULTITURN_FIXTURE_PATH)[4],
        "require_rendered_memo_claims": True,
        "require_rendered_evidence_refs": True,
        "require_response_language_match": True,
    }
    result = {
        "status": "completed",
        "agent_activation_plan": {
            "execution_mode": "standard_memo",
            "activate_agents": [
                "research_lead",
                "sec_operator",
                "eight_k_operator",
                "market_operator",
                "coverage_reflection",
                "fundamental_analyst",
                "market_valuation_analyst",
                "risk_counterevidence_analyst",
                "memo_writer",
                "verifier",
                "renderer",
            ],
            "focus_tickers": ["NVDA", "AMD"],
            "search_scope_tickers": ["NVDA", "AMD"],
        },
        "agent_activation_validation": {"status": "pass"},
        "tool_call_ledger": {
            "records": [
                {"agent_id": "sec_operator", "tool_name": "sec_search_filings", "status": "completed", "row_count": 2},
                {"agent_id": "eight_k_operator", "tool_name": "sec_search_filings", "status": "completed", "row_count": 1},
                {"agent_id": "market_operator", "tool_name": "market_get_snapshot", "status": "completed", "row_count": 1},
            ]
        },
        "specialist_route_results": [
            {"agent_id": "fundamental_analyst", "status": "pass"},
            {"agent_id": "market_valuation_analyst", "status": "pass"},
            {"agent_id": "risk_counterevidence_analyst", "status": "pass"},
        ],
        "specialist_verification": {"status": "pass"},
        "memo_answer": {
            "answer_status": "draft",
            "response_language": {"language": "zh-CN"},
            "memo_claims": [{"claim": "中文支持性论据。", "evidence_refs": ["ref_1"]}],
        },
        "memo_route_result": {"status": "pass", "attempt_count": 1},
        "claim_verification": {"status": "pass"},
        "rendered_answer": "这是中文投研结论，包含足够中文正文用于语言门控，并说明基本面、市场反应、估值风险和证据边界都已经被综合。关键论据:\n1. 中文支持性论据。 证据=ref_1",
    }
    summary = {
        "payload_policy": {"raw_evidence": "not_included"},
        "llm_routes": {
            "research_lead": {"diagnostics": _ok_diag()},
            "specialist": {"diagnostics": _ok_diag()},
            "memo_writer": {"diagnostics": _ok_diag()},
            "verifier": {"diagnostics": _ok_diag()},
        },
    }

    score = module.score_case(case, result, summary, {}, elapsed_ms=12)

    assert score["gate_status"] == "pass"
    assert score["checks"]["memo_verifier.rendered_answer_has_memo_claims"] is True
    assert score["checks"]["memo_verifier.rendered_answer_has_evidence_refs"] is True
    assert score["checks"]["memo_verifier.response_language_matches_query"] is True
    assert score["checks"]["memo_verifier.rendered_user_language_ok"] is True


def test_real_llm_chain_specialist_quality_requires_industry_relationship_ref_for_sector_depth() -> None:
    module = _load_script_module()
    case = {
        "case_id": "sector_relationship_gate",
        "category": "sector_depth",
        "source_tiers": ["industry_snapshot", "relationship_graph"],
        "expected_tool_names": ["relationship_graph_lookup"],
    }
    result = {
        "specialist_route_results": [{"agent_id": "industry_supply_chain_analyst", "status": "pass"}],
        "specialist_outputs": [
            {
                "agent_id": "industry_supply_chain_analyst",
                "status": "pass",
                "evidence_boundary": "bounded_rows_only",
                "summary": "Industry-only output.",
                "observations": [
                    {
                        "claim": "Power demand is relevant context.",
                        "claim_type": "industry_context_only",
                        "evidence_refs": ["industry_ref"],
                        "source_families": ["industry_snapshot"],
                        "confidence": "medium",
                        "unsupported": False,
                    }
                ],
                "unsupported_claims": [],
                "conflicts": [],
            }
        ],
        "industry_snapshot_rows": [
            {"evidence_ref": "industry_ref", "source_family": "industry_snapshot", "summary": "Power demand context."}
        ],
        "universe_relationship_plan": {
            "relationships": [
                {
                    "ticker": "SRE",
                    "related_ticker": "XEL",
                    "relationship_type": "peer",
                    "evidence_refs": ["rel_ref"],
                    "inclusion_rationale": "Utilities relationship hypothesis.",
                }
            ]
        },
    }

    quality = module._specialist_real_evidence_quality(
        case,
        result,
        {"industry_supply_chain_analyst"},
        required=True,
    )
    detail = quality["details"]["industry_supply_chain_analyst"]

    assert quality["quality_pass"] is False
    assert detail["relationship_gate_required"] is True
    assert detail["checks"]["relationship_input_present_when_required"] is True
    assert detail["checks"]["relationship_evidence_ref_cited_when_required"] is False


def test_real_llm_chain_relationship_pack_gate_rejects_off_sector_citation_without_cross_sector_prompt() -> None:
    module = _load_script_module()
    case = {
        "case_id": "sector_pack_gate",
        "category": "sector_depth",
        "prompt": "用 energy infrastructure 和 real estate utilities sector-depth packs 分析电力负荷和利率背景。",
        "source_tiers": ["industry_snapshot", "relationship_graph"],
        "expected_tool_names": ["relationship_graph_lookup"],
        "expected_relationship_pack_ids": ["energy_infrastructure_depth", "real_estate_utilities_depth"],
        "allowed_cross_sector_relationship_pack_ids": ["technology_ai_infrastructure_depth"],
    }
    result = _industry_relationship_result(
        "sector_depth_pack:technology_ai_infrastructure_depth:VRT",
        "AI infrastructure power readthrough.",
        extra_relationship_refs=["sector_depth_pack:real_estate_utilities_depth:XEL"],
    )

    quality = module._specialist_real_evidence_quality(
        case,
        result,
        {"industry_supply_chain_analyst"},
        required=True,
    )
    detail = quality["details"]["industry_supply_chain_analyst"]

    assert quality["quality_pass"] is False
    assert detail["relationship_pack_gate_required"] is True
    assert detail["cross_sector_relationship_query_allowed"] is False
    assert detail["relationship_pack_ids_cited"] == ["technology_ai_infrastructure_depth"]
    assert detail["checks"]["relationship_available_pack_relevance_when_required"] is False
    assert detail["checks"]["relationship_cited_pack_relevance_when_required"] is False


def test_real_llm_chain_relationship_pack_gate_allows_explicit_ai_power_transmission() -> None:
    module = _load_script_module()
    case = {
        "case_id": "sector_pack_cross_sector_allowed",
        "category": "sector_depth",
        "prompt": "分析 utilities 的 data center power load 和 AI infrastructure demand transmission。",
        "source_tiers": ["industry_snapshot", "relationship_graph"],
        "expected_tool_names": ["relationship_graph_lookup"],
        "expected_relationship_pack_ids": ["real_estate_utilities_depth"],
        "allowed_cross_sector_relationship_pack_ids": ["technology_ai_infrastructure_depth"],
    }
    result = _industry_relationship_result(
        "sector_depth_pack:technology_ai_infrastructure_depth:VRT",
        "AI infrastructure power readthrough.",
        extra_relationship_refs=["sector_depth_pack:real_estate_utilities_depth:XEL"],
    )

    quality = module._specialist_real_evidence_quality(
        case,
        result,
        {"industry_supply_chain_analyst"},
        required=True,
    )
    detail = quality["details"]["industry_supply_chain_analyst"]

    assert quality["quality_pass"] is True
    assert detail["cross_sector_relationship_query_allowed"] is True
    assert detail["effective_allowed_relationship_pack_ids"] == [
        "real_estate_utilities_depth",
        "technology_ai_infrastructure_depth",
    ]
    assert detail["checks"]["relationship_cited_pack_relevance_when_required"] is True


def test_real_llm_chain_specialist_quality_requires_comparative_primary_rows_or_gap() -> None:
    module = _load_script_module()
    case = {
        "case_id": "comparative_primary_gate",
        "focus_tickers": ["NVDA", "AMD"],
        "category": "standard_memo",
    }
    result = {
        "specialist_route_results": [
            {
                "agent_id": "fundamental_analyst",
                "status": "pass",
                "prompt_row_distribution": {"by_ticker": {"AMD": 1}, "by_source_family": {"primary_sec_filing": 1}},
            }
        ],
        "specialist_outputs": [
            {
                "agent_id": "fundamental_analyst",
                "status": "pass",
                "evidence_boundary": "bounded_rows_only",
                "summary": "AMD-only output.",
                "observations": [
                    {
                        "claim": "AMD has bounded revenue evidence.",
                        "claim_type": "business_observation",
                        "ticker_scope": ["AMD"],
                        "metric_scope": ["revenue"],
                        "memo_slot": "fundamentals",
                        "evidence_refs": ["amd_ref"],
                        "source_families": ["primary_sec_filing"],
                        "confidence": "medium",
                        "unsupported": False,
                    }
                ],
                "unsupported_claims": [],
                "conflicts": [],
            }
        ],
        "runtime_ledger_rows": [
            {"metric_id": "amd_ref", "source_family": "primary_sec_filing", "ticker": "AMD", "metric": "revenue"}
        ],
    }

    quality = module._specialist_real_evidence_quality(case, result, {"fundamental_analyst"}, required=True)
    detail = quality["details"]["fundamental_analyst"]

    assert quality["quality_pass"] is False
    assert detail["comparative_primary_gate_required"] is True
    assert detail["focus_ticker_primary_missing"] == ["NVDA"]
    assert detail["checks"]["comparative_focus_ticker_primary_visible_or_gap"] is False


def test_real_llm_chain_specialist_quality_rejects_single_ref_temporal_inference() -> None:
    module = _load_script_module()
    case = {
        "case_id": "temporal_ref_depth_gate",
        "focus_tickers": ["NVDA", "AMD"],
        "category": "standard_memo",
    }
    result = {
        "specialist_route_results": [
            {
                "agent_id": "risk_counterevidence_analyst",
                "status": "pass",
                "prompt_row_distribution": {
                    "by_ticker": {"NVDA": 1, "AMD": 1},
                    "by_source_family": {"primary_sec_filing": 2},
                },
            }
        ],
        "specialist_outputs": [
            {
                "agent_id": "risk_counterevidence_analyst",
                "status": "pass",
                "evidence_boundary": "bounded_rows_only",
                "summary": "Risk output.",
                "observations": [
                    {
                        "claim": "NVDA revenue implies a sequential decline from prior quarters.",
                        "claim_type": "business_observation",
                        "ticker_scope": ["NVDA"],
                        "metric_scope": ["revenue"],
                        "memo_slot": "risk_counterevidence",
                        "evidence_refs": ["nvda_ref"],
                        "source_families": ["primary_sec_filing"],
                        "confidence": "medium",
                        "unsupported": False,
                    }
                ],
                "unsupported_claims": [],
                "conflicts": [],
            }
        ],
        "runtime_ledger_rows": [
            {"metric_id": "nvda_ref", "source_family": "primary_sec_filing", "ticker": "NVDA", "metric": "revenue"},
            {"metric_id": "amd_ref", "source_family": "primary_sec_filing", "ticker": "AMD", "metric": "revenue"},
        ],
    }

    quality = module._specialist_real_evidence_quality(case, result, {"risk_counterevidence_analyst"}, required=True)
    detail = quality["details"]["risk_counterevidence_analyst"]

    assert quality["quality_pass"] is False
    assert detail["checks"]["temporal_claim_ref_depth_valid"] is False
    assert detail["temporal_claim_ref_depth_failures"]


def test_real_llm_chain_exact_lookup_accepts_runtime_ledger_as_real_retrieval() -> None:
    module = _load_script_module()
    case = {
        "case_id": "exact_lookup_ledger_gate",
        "category": "exact_lookup",
        "expected_execution_mode": "deterministic_lookup",
        "expected_tool_names": ["sec_search_filings", "sec_query_exact_value_ledger"],
        "require_real_retrieval_pass": True,
        "require_runtime_ledger_rows": True,
    }
    result = {
        "runtime_ledger_rows": [
            {
                "metric_id": "MSFT_CAPEX",
                "source_family": "primary_sec_filing",
                "ticker": "MSFT",
                "metric_family": "capital_expenditure_proxy",
            }
        ],
    }
    tool_calls = [
        {
            "agent_id": "sec_operator",
            "tool_name": "sec_query_exact_value_ledger",
            "status": "completed",
            "row_count": 1,
        }
    ]

    checks = module._real_operator_checks(case, result, tool_calls, required=True)

    assert checks["sec_search_not_dry_run"] is True
    assert checks["sec_search_context_rows_present"] is True
    assert checks["sec_search_bm25_candidates_present"] is True
    assert checks["sec_search_bge_rerank_present"] is True
    assert checks["sec_search_runtime_ledger_rows_present"] is True


def test_real_llm_chain_specialist_quality_allows_single_ref_yoy_row_with_raw_value() -> None:
    module = _load_script_module()
    case = {
        "case_id": "temporal_single_row_yoy_gate",
        "focus_tickers": ["JPM", "C"],
        "category": "sector_depth",
    }
    result = {
        "specialist_route_results": [
            {
                "agent_id": "fundamental_analyst",
                "status": "pass",
                "prompt_row_distribution": {
                    "by_ticker": {"JPM": 1, "C": 1},
                    "by_source_family": {"company_authored_unaudited_sec_filing": 2},
                },
            }
        ],
        "specialist_outputs": [
            {
                "agent_id": "fundamental_analyst",
                "status": "pass",
                "evidence_boundary": "bounded_rows_only",
                "summary": "Fundamental output.",
                "observations": [
                    {
                        "claim": "JPM reported 1Q26 net revenue of $23.4 billion, up 19% YoY.",
                        "claim_type": "business_observation",
                        "ticker_scope": ["JPM"],
                        "metric_scope": ["revenue"],
                        "memo_slot": "fundamentals",
                        "evidence_refs": ["jpm_ref"],
                        "source_families": ["primary_sec_filing"],
                        "confidence": "medium",
                        "unsupported": False,
                    }
                ],
                "unsupported_claims": [],
                "conflicts": [],
            }
        ],
        "context_rows": [
                {
                    "evidence_ref": "jpm_ref",
                    "source_family": "primary_sec_filing",
                    "ticker": "JPM",
                    "metric": "net revenue",
                    "raw_value_text": "$23.4 billion, up 19% YoY",
                },
                {
                    "evidence_ref": "c_ref",
                    "source_family": "primary_sec_filing",
                    "ticker": "C",
                    "metric": "revenue",
                },
        ],
    }

    quality = module._specialist_real_evidence_quality(case, result, {"fundamental_analyst"}, required=True)
    detail = quality["details"]["fundamental_analyst"]

    assert detail["checks"]["temporal_claim_ref_depth_valid"] is True


def test_real_llm_chain_specialist_quality_does_not_treat_growth_from_sector_as_temporal() -> None:
    module = _load_script_module()

    assert (
        module._looks_like_temporal_inference(
            "NEE storm cost recovery may mask underlying demand-driven growth from AI data centers."
        )
        is False
    )


def test_real_llm_chain_specialist_quality_allows_self_comparative_single_row() -> None:
    module = _load_script_module()
    case = {
        "case_id": "temporal_self_comparative_gate",
        "focus_tickers": ["CVX", "XOM"],
        "category": "standard_memo",
    }
    result = {
        "specialist_route_results": [
            {
                "agent_id": "risk_counterevidence_analyst",
                "status": "pass",
                "prompt_row_distribution": {
                    "by_ticker": {"CVX": 1, "XOM": 1},
                    "by_source_family": {"primary_sec_filing": 2},
                },
            }
        ],
        "specialist_outputs": [
            {
                "agent_id": "risk_counterevidence_analyst",
                "status": "pass",
                "evidence_boundary": "bounded_rows_only",
                "summary": "Risk output.",
                "observations": [
                    {
                        "claim": "CVX capex rose 4% YoY to $16.4B.",
                        "claim_type": "business_observation",
                        "ticker_scope": ["CVX"],
                        "metric_scope": ["capex"],
                        "memo_slot": "risk_counterevidence",
                        "evidence_refs": ["cvx_ref"],
                        "source_families": ["primary_sec_filing"],
                        "confidence": "medium",
                        "unsupported": False,
                    }
                ],
                "unsupported_claims": [],
                "conflicts": [],
            }
        ],
        "runtime_ledger_rows": [
            {
                "metric_id": "cvx_ref",
                "source_family": "primary_sec_filing",
                "ticker": "CVX",
                "metric": "capex",
                "summary": "Capex for 2024 was $16.4 billion, 4 percent higher than 2023.",
            },
            {"metric_id": "xom_ref", "source_family": "primary_sec_filing", "ticker": "XOM", "metric": "capex"},
        ],
    }

    quality = module._specialist_real_evidence_quality(case, result, {"risk_counterevidence_analyst"}, required=True)
    detail = quality["details"]["risk_counterevidence_analyst"]

    assert detail["checks"]["temporal_claim_ref_depth_valid"] is True


def test_real_llm_chain_scope_gap_and_performance_contracts_pass() -> None:
    module = _load_script_module()
    case = {
        "case_id": "scope_gap_contract_unit",
        "category": "scope_decision",
        "expected_execution_mode": "deep_research",
        "required_agents": ["research_lead", "universe_relationship", "memo_writer", "renderer"],
        "expected_operator_agents": ["universe_relationship"],
        "expected_tool_names": ["relationship_graph_lookup"],
        "require_scope_decision_contract": True,
        "expected_scoping_patterns": ["supply_chain_readthrough"],
        "expected_expansion_modes": ["required_expansion"],
        "expected_catalogs_to_inspect": ["relationship_graph"],
        "expected_candidate_lenses": ["memory_foundry_equipment_supply_chain"],
        "require_universe_scope_contract": True,
        "required_universe_candidate_lenses": ["upstream_supplier"],
        "required_relationship_strengths": ["hypothesis"],
        "require_evidence_gap_request_types": ["relationship_confirmation"],
        "require_gap_preserved_to_judgment": True,
        "require_gap_preserved_to_memo": True,
        "require_rendered_gap_boundary": True,
        "require_hypothesis_boundary_rendered": True,
        "max_case_elapsed_ms_lte": 1000,
        "max_total_tokens_lte": 5000,
        "max_research_lead_tokens_lte": 1000,
        "max_universe_tokens_lte": 1000,
        "max_specialist_tokens_lte": 2000,
        "max_memo_tokens_lte": 1000,
        "max_verifier_tokens_lte": 500,
    }
    gap = {
        "request_type": "relationship_confirmation",
        "owner_agent": "universe_relationship",
        "tickers": ["NVDA", "TSM"],
        "source_family": "relationship_graph",
        "reason": "Need company-confirmed relationship evidence.",
        "blocking_level": "material",
        "can_answer_bounded_without": True,
    }
    result = {
        "status": "completed",
        "agent_activation_plan": {
            "execution_mode": "deep_research",
            "activate_agents": ["research_lead", "universe_relationship", "memo_writer", "renderer"],
            "metadata": {
                "scope_decision": {
                    "scoping_pattern": "supply_chain_readthrough",
                    "expansion_mode": "required_expansion",
                    "why": "The question needs supply-chain confirmation.",
                    "catalogs_to_inspect": ["relationship_graph", "source_family_inventory"],
                    "candidate_lenses": ["memory_foundry_equipment_supply_chain"],
                    "expansion_budget": {"max_expanded_tickers": 4},
                    "stop_condition": "Stop when bounded catalog lacks relationship confirmation.",
                }
            },
        },
        "agent_activation_validation": {"status": "pass"},
        "universe_relationship_validation": {"status": "pass"},
        "relationship_graph_observation": {
            "status": "ok",
            "relationships": [{"evidence_refs": ["rel_1"], "claim_scope": "scope_or_hypothesis_only"}],
        },
        "tool_call_ledger": {
            "records": [
                {
                    "agent_id": "universe_relationship",
                    "tool_name": "relationship_graph_lookup",
                    "status": "completed",
                    "row_count": 1,
                }
            ]
        },
        "universe_relationship_plan": {
            "included_ticker_contracts": [
                {
                    "included_ticker": "TSM",
                    "candidate_lens": "upstream_supplier",
                    "inclusion_rationale": "Candidate supplier lens from bounded catalog.",
                    "available_source_families": ["relationship_graph", "primary_sec_filing"],
                    "relationship_strength": "hypothesis",
                    "downstream_operator_owner": "universe_relationship",
                }
            ],
            "excluded_ticker_contracts": [],
        },
        "specialist_outputs": [{"agent_id": "industry_supply_chain_analyst", "evidence_gap_requests": [gap]}],
        "judgment_plan": {"evidence_gap_requests": [gap]},
        "memo_answer": {"answer_status": "draft", "evidence_gap_requests": [gap]},
        "rendered_answer": "关键论据:\n1. 这是 hypothesis-only 的供应链假设。证据=rel_1\n来源限制：存在 relationship confirmation evidence gap，不能证明直接商业关系。",
        "claim_verification": {},
    }
    summary = {
        "payload_policy": {"raw_evidence": "not_included"},
        "llm_routes": {
            "research_lead": {"diagnostics": {**_ok_diag(), "total_tokens": 800}},
            "universe_relationship": {"diagnostics": {**_ok_diag(), "total_tokens": 900}},
            "memo_writer": {"diagnostics": {**_ok_diag(), "total_tokens": 700}},
            "verifier": {"diagnostics": {**_ok_diag(), "total_tokens": 300}},
        },
    }

    score = module.score_case(case, result, summary, {}, elapsed_ms=500)

    assert score["gate_status"] == "pass"
    assert score["checks"]["scope_gap_contract.scope_decision_present"] is True
    assert score["checks"]["scope_gap_contract.universe_included_ticker_fields_present"] is True
    assert score["checks"]["scope_gap_contract.required_evidence_gap_types_present"] is True
    assert score["checks"]["scope_gap_contract.gap_requests_preserved_to_memo"] is True
    assert score["checks"]["performance.total_tokens_lte"] is True
    assert score["token_usage"]["total_tokens"] == 2700


def test_real_llm_chain_performance_eval_applies_default_standard_memo_latency_gate() -> None:
    module = _load_script_module()

    performance = module._performance_eval(
        {
            "case_id": "standard_default_perf_unit",
            "category": "standard_memo",
            "expected_execution_mode": "standard_memo",
        },
        result={},
        summary={},
        specialist_routes=[],
        elapsed_ms=181_000,
    )

    assert performance["limits"]["max_case_elapsed_ms_lte"] == 180_000
    assert performance["limits"]["max_total_tokens_lte"] == 90_000
    assert performance["checks"]["case_elapsed_ms_lte"] is False
    assert performance["checks"]["total_tokens_lte"] is True


def test_real_llm_chain_scope_contract_rejects_missing_scope_metadata() -> None:
    module = _load_script_module()
    case = {
        "case_id": "scope_missing_unit",
        "category": "scope_decision",
        "expected_execution_mode": "standard_memo",
        "required_agents": ["research_lead", "memo_writer", "renderer"],
        "require_scope_decision_contract": True,
        "expected_scoping_patterns": ["single_company_fundamental"],
    }
    result = {
        "status": "completed",
        "agent_activation_plan": {
            "execution_mode": "standard_memo",
            "activate_agents": ["research_lead", "memo_writer", "renderer"],
        },
        "agent_activation_validation": {"status": "pass"},
        "memo_answer": {"answer_status": "draft"},
        "rendered_answer": "bounded answer",
    }
    summary = {"payload_policy": {"raw_evidence": "not_included"}}

    score = module.score_case(case, result, summary, {}, elapsed_ms=1)

    assert score["gate_status"] == "fail"
    assert score["checks"]["scope_gap_contract.scope_decision_present"] is False
    assert score["checks"]["scope_gap_contract.scope_scoping_pattern_expected"] is False


def _industry_relationship_result(
    evidence_ref: str,
    rationale: str,
    *,
    extra_relationship_refs: list[str] | None = None,
) -> dict:
    relationships = [
        {
            "ticker": "SRE",
            "related_ticker": "VRT",
            "relationship_type": "sector",
            "evidence_refs": [evidence_ref],
            "inclusion_rationale": rationale,
            "claim_scope": "scope_or_hypothesis_only",
        }
    ]
    for index, ref in enumerate(extra_relationship_refs or [], start=1):
        relationships.append(
            {
                "ticker": "SRE",
                "related_ticker": f"REL{index}",
                "relationship_type": "sector",
                "evidence_refs": [ref],
                "inclusion_rationale": "Expected sector relationship context.",
                "claim_scope": "scope_or_hypothesis_only",
            }
        )
    return {
        "specialist_route_results": [
            {
                "agent_id": "industry_supply_chain_analyst",
                "status": "pass",
                "prompt_row_distribution": {
                    "by_ticker": {"SRE": 1},
                    "by_source_family": {"relationship_graph": 1},
                },
            }
        ],
        "specialist_outputs": [
            {
                "agent_id": "industry_supply_chain_analyst",
                "status": "pass",
                "evidence_boundary": "bounded_rows_only",
                "summary": "Relationship-cited output.",
                "observations": [
                    {
                        "claim": "The cited relationship evidence is relevant.",
                        "claim_type": "relationship_hypothesis",
                        "evidence_refs": [evidence_ref],
                        "source_families": ["relationship_graph"],
                        "confidence": "medium",
                        "unsupported": False,
                    }
                ],
                "unsupported_claims": [],
                "conflicts": [],
            }
        ],
        "universe_relationship_plan": {"relationships": relationships},
    }


def _ok_diag() -> dict:
    return {
        "call_count": 1,
        "provider": "deepseek",
        "model": "deepseek-v4-pro",
        "latency_ms": 100,
        "total_tokens": 1000,
        "finish_reasons": ["stop"],
        "all_calls_ok": True,
        "direct_tool_call_count": 0,
        "raw_response_saved": False,
    }


def _read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _load_script_module():
    spec = importlib.util.spec_from_file_location("eval_multi_agent_real_llm_chain_under_test", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
