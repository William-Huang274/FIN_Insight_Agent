from __future__ import annotations

import json
from pathlib import Path

from sec_agent.claim_evidence_ledger import (
    CLAIM_EVIDENCE_LEDGER_SCHEMA_VERSION,
    TYPED_GAP_LEDGER_SCHEMA_VERSION,
    build_claim_evidence_ledger,
    build_evidence_governance_ledgers,
    build_typed_gap_ledger,
    normalize_gap_type,
    validate_claim_evidence_ledger,
    validate_typed_gap_ledger,
)
from sec_agent.langgraph_orchestrator import build_multi_agent_orchestration_graph, make_multi_agent_smoke_state


def test_typed_gap_ledger_normalizes_commercial_and_parser_gaps() -> None:
    ledger = build_typed_gap_ledger(
        {
            "source_gaps": [
                {
                    "gap_id": "gap_market_share_tracker",
                    "gap_type": "commercial_tracker_gap",
                    "ticker": "AAPL",
                    "metric": "iPhone shipments",
                    "source_family": "public_source_context",
                    "reason": "Commercial tracker required for true shipments.",
                },
                {
                    "gap_id": "gap_region_schema",
                    "gap_type": "region_schema_gap",
                    "ticker": "LLY",
                    "metric": "product sales",
                    "source_family": "company_product_evidence_graph",
                    "reason": "Regional columns need source-specific parser repair.",
                },
            ]
        }
    )

    assert ledger["schema_version"] == TYPED_GAP_LEDGER_SCHEMA_VERSION
    assert ledger["validation"]["status"] == "pass"
    by_type = ledger["summary"]["by_gap_type"]
    assert by_type["commercial_gap"] == 1
    assert by_type["parser_failed"] == 1
    commercial = next(row for row in ledger["gaps"] if row["gap_type"] == "commercial_gap")
    assert commercial["raw_gap_type"] == "commercial_tracker_gap"
    assert commercial["treatment_action"] == "expose_commercial_gap_do_not_proxy"
    assert "never_filled_with_public_proxy" in commercial["claim_boundary"]


def test_typed_gap_ledger_suppresses_non_blocking_route_scope_notes() -> None:
    ledger = build_typed_gap_ledger(
        {
            "focus_tickers": ["DELL", "NVDA"],
            "pre_memo_fact_selection": {
                "approved_facts": [
                    {
                        "ticker": "DELL",
                        "source_family": "company_authored_unaudited_sec_filing",
                        "evidence_ref": "dell_8k_ref",
                    },
                    {
                        "ticker": "NVDA",
                        "source_family": "primary_sec_filing",
                        "evidence_ref": "nvda_10k_ref",
                    },
                ]
            },
            "source_gaps": [
                {
                    "ticker": "DELL",
                    "reason_code": "not_in_manifest_for_mcp_route_scope",
                    "source_family": "company_authored_unaudited_sec_filing",
                },
                {
                    "ticker": "NVDA",
                    "reason_code": "not_in_manifest_for_mcp_route_scope",
                    "source_family": "company_authored_unaudited_sec_filing",
                },
                {
                    "ticker": "ANET",
                    "reason_code": "not_in_manifest_for_mcp_route_scope",
                    "source_family": "company_authored_unaudited_sec_filing",
                },
            ],
        }
    )

    assert ledger["gaps"] == []


def test_typed_gap_ledger_keeps_focus_route_scope_gap_without_visible_evidence() -> None:
    ledger = build_typed_gap_ledger(
        {
            "focus_tickers": ["ASML"],
            "source_gaps": [
                {
                    "ticker": "ASML",
                    "reason_code": "not_in_manifest_for_mcp_route_scope",
                    "source_family": "company_authored_unaudited_sec_filing",
                }
            ],
        }
    )

    assert ledger["gap_count"] == 1
    assert ledger["gaps"][0]["ticker"] == "ASML"


def test_claim_evidence_ledger_projects_supported_conflict_and_gap_claims() -> None:
    typed_gaps = build_typed_gap_ledger(
        {
            "source_gaps": [
                {
                    "gap_id": "gap_nvda_units",
                    "gap_type": "commercial_tracker_gap",
                    "ticker": "NVDA",
                    "metric": "shipments",
                    "source_family": "public_source_context",
                }
            ]
        }
    )
    judgment = {
        "supported_claims": [
            {
                "claim_id": "cl_nvda_dc",
                "agent_id": "fundamental_analyst",
                "claim": "NVDA Data Center revenue is supported by company-disclosed evidence.",
                "claim_type": "company_reported_financial_fact",
                "ticker_scope": ["NVDA"],
                "metric_scope": ["revenue"],
                "evidence_refs": ["sec_ref_1"],
                "source_families": ["primary_sec_filing"],
                "confidence": "high",
            }
        ],
        "conflicts": [
            {
                "claim": "Unit shipment detail remains unavailable.",
                "evidence_refs": ["gap_nvda_units"],
                "ticker": "NVDA",
                "metric": "shipments",
            }
        ],
        "unsupported_claims": [
            {
                "claim": "Customer-level GPU units are disclosed.",
                "reason": "Not in public evidence.",
                "ticker": "NVDA",
                "metric": "shipments",
            }
        ],
    }

    ledger = build_claim_evidence_ledger(judgment, typed_gap_ledger=typed_gaps, run_id="unit_run", as_of_date="2026-06-12")

    assert ledger["schema_version"] == CLAIM_EVIDENCE_LEDGER_SCHEMA_VERSION
    assert ledger["validation"]["status"] == "pass"
    assert ledger["summary"]["by_claim_status"] == {
        "contradicted": 1,
        "gap_exposed": 1,
        "supported": 1,
    }
    supported = next(row for row in ledger["claims"] if row["claim_status"] == "supported")
    assert supported["source_strength"] == "S5"
    assert supported["supporting_evidence_ids"] == ["sec_ref_1"]
    gap_claim = next(row for row in ledger["claims"] if row["claim_status"] == "gap_exposed")
    assert "gap_nvda_units" in gap_claim["gap_ids"]


def test_ledger_validators_fail_closed_on_bad_supported_claim_and_gap_type() -> None:
    claim_validation = validate_claim_evidence_ledger(
        {
            "claims": [
                {
                    "claim_id": "cl_bad",
                    "claim_text": "Supported claim without evidence.",
                    "claim_status": "supported",
                    "source_strength": "S5",
                }
            ]
        }
    )
    gap_validation = validate_typed_gap_ledger(
        {
            "gaps": [
                {
                    "gap_id": "gap_bad",
                    "gap_type": "unknown",
                    "claim_boundary": "bounded",
                }
            ]
        }
    )

    assert claim_validation["status"] == "fail"
    assert claim_validation["errors"][0]["type"] == "supported_claim_without_supporting_evidence"
    assert gap_validation["status"] == "fail"
    assert gap_validation["errors"][0]["type"] == "invalid_gap_type"
    assert normalize_gap_type("commercial_market_tracker_gap_after_public_source_check") == "commercial_gap"


def test_graph_writes_claim_evidence_and_typed_gap_ledgers(tmp_path: Path) -> None:
    def injected_execute(state: dict) -> dict:
        return {
            "tool_observations": [],
            "tool_call_ledger": state.get("tool_call_ledger") or {},
            "runtime_ledger_rows": [
                {
                    "evidence_ref": "msft_revenue_ref",
                    "source_family": "primary_sec_filing",
                    "ticker": "MSFT",
                    "metric_family": "revenue",
                    "value": "100",
                }
            ],
            "source_gaps": [
                {
                    "gap_id": "gap_msft_share",
                    "gap_type": "commercial_tracker_gap",
                    "source_family": "public_source_context",
                    "ticker": "MSFT",
                    "metric": "market_share",
                }
            ],
        }

    graph = build_multi_agent_orchestration_graph(execute_evidence_operators=injected_execute)
    initial = make_multi_agent_smoke_state(
        user_query="写一段 MSFT 基本面和产品表现 memo。",
        output_dir=tmp_path,
        query_contract={
            "companies": ["MSFT"],
            "source_tiers": ["primary_sec_filing", "public_source_context"],
            "intent": "standard_memo",
        },
        focus_tickers=["MSFT"],
        search_scope_tickers=["MSFT"],
    )

    result = graph.invoke(initial, config={"configurable": {"thread_id": "unit-claim-evidence-ledger"}})
    ledgers = build_evidence_governance_ledgers(result)

    assert result["claim_evidence_ledger"]["schema_version"] == CLAIM_EVIDENCE_LEDGER_SCHEMA_VERSION
    assert result["typed_gap_ledger"]["schema_version"] == TYPED_GAP_LEDGER_SCHEMA_VERSION
    assert result["typed_gap_ledger"]["summary"]["commercial_gap_count"] == 1
    assert result["claim_card_store_barrier"]["claim_evidence_ledger_schema_version"] == CLAIM_EVIDENCE_LEDGER_SCHEMA_VERSION
    assert ledgers["typed_gap_ledger"]["validation"]["status"] == "pass"
    assert "claim_evidence_ledger" in result["artifact_refs"]
    assert "typed_gap_ledger" in result["artifact_refs"]
    claim_ledger_artifact = json.loads((tmp_path / "claim_evidence_ledger.json").read_text(encoding="utf-8"))
    gap_ledger_artifact = json.loads((tmp_path / "typed_gap_ledger.json").read_text(encoding="utf-8"))
    assert claim_ledger_artifact["schema_version"] == CLAIM_EVIDENCE_LEDGER_SCHEMA_VERSION
    assert gap_ledger_artifact["schema_version"] == TYPED_GAP_LEDGER_SCHEMA_VERSION
    assert gap_ledger_artifact["summary"]["commercial_gap_count"] == 1
    summary = json.loads((tmp_path / "multi_agent_summary.json").read_text(encoding="utf-8"))
    assert summary["claim_evidence_ledger"]["schema_version"] == CLAIM_EVIDENCE_LEDGER_SCHEMA_VERSION
    assert summary["typed_gap_ledger"]["commercial_gap_count"] == 1
