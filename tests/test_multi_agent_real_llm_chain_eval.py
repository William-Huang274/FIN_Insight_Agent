from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "multi_agent_real_llm_chain_cases_v0_1.jsonl"
SCRIPT_PATH = REPO_ROOT / "scripts" / "eval_multi_agent_real_llm_chain.py"


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
        "claim_verification": {"status": "pass"},
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
        "specialist_route_results": [{"agent_id": "industry_supply_chain_analyst", "status": "pass"}],
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
