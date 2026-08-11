from __future__ import annotations

import json
import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "eval_multi_agent" / "eval_multi_agent_specialist_real_evidence_quality.py"
SPEC = importlib.util.spec_from_file_location("eval_multi_agent_specialist_real_evidence_quality", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
evaluate_real_evidence_case = MODULE.evaluate_real_evidence_case
materialize_real_evidence_case = MODULE.materialize_real_evidence_case


def test_materializes_real_evidence_rows_from_runtime_artifacts(tmp_path: Path) -> None:
    ledger = tmp_path / "runtime_exact_value_ledger.json"
    ledger.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "metric_id": "CASE::JPM::2026::net_interest_income",
                        "ticker": "JPM",
                        "fiscal_year": 2026,
                        "period_role": "qtd",
                        "source_tier": "primary_sec_filing",
                        "form_type": "10-Q",
                        "metric_family": "net_interest_income",
                        "metric_role": "total_value",
                        "display_value_zh": "25,366（百万美元）",
                        "section": "Item 7",
                    },
                    {
                        "metric_id": "CASE::AMD::2026::revenue",
                        "ticker": "AMD",
                        "fiscal_year": 2026,
                        "period_role": "qtd",
                        "source_tier": "primary_sec_filing",
                        "metric_family": "revenue",
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    market = tmp_path / "market.jsonl"
    market.write_text(
        json.dumps(
            {
                "evidence_id": "MARKET_SNAPSHOT::fixture::JPM",
                "ticker": "JPM",
                "as_of_date": "2026-05-22",
                "snapshot_id": "fixture",
                "field_refs": [{"field_name": "return_3m", "value": 0.03}],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    case = materialize_real_evidence_case(
        {
            "case_id": "fixture",
            "agent_id": "fundamental_analyst",
            "user_query": "test",
            "evidence_sources": [
                {
                    "type": "runtime_ledger_json",
                    "path": str(ledger),
                    "filters": {"tickers": ["JPM"], "metric_families": ["net_interest_income"]},
                    "limit": 4,
                },
                {"type": "market_evidence_jsonl", "path": str(market), "filters": {"tickers": ["JPM"]}, "limit": 1},
            ],
        }
    )

    assert case["known_evidence_refs"] == ["CASE::JPM::2026::net_interest_income", "MARKET_SNAPSHOT::fixture::JPM"]
    assert {row["source_family"] for row in case["bounded_evidence_rows"]} == {"primary_sec_filing", "market_snapshot"}
    assert all(row["metadata"]["real_evidence_row"] for row in case["bounded_evidence_rows"])


def test_real_evidence_quality_scoring_rejects_unknown_refs() -> None:
    case = {
        "case_id": "quality",
        "agent_id": "fundamental_analyst",
        "expected_min_observations": 1,
        "expect_unsupported_or_conflict": False,
        "known_evidence_refs": ["known_ref"],
        "bounded_evidence_rows": [
            {"evidence_ref": "known_ref", "source_family": "primary_sec_filing", "metadata": {"real_evidence_row": True}}
        ],
        "quality_expectations": {
            "required_input_source_families": ["primary_sec_filing"],
            "allowed_observation_source_families": ["primary_sec_filing"],
        },
    }
    result = evaluate_real_evidence_case(
        case,
        route_result={
            "status": "pass",
            "memolet": {
                "agent_id": "fundamental_analyst",
                "observations": [
                    {
                        "claim": "supported",
                        "evidence_refs": ["unknown_ref"],
                        "source_families": ["primary_sec_filing"],
                        "unsupported": False,
                    }
                ],
                "unsupported_claims": [],
                "conflicts": [],
            },
            "validation": {"status": "pass"},
            "routing_trace": {"repair_attempts": 0},
            "model_diagnostics": {"calls": []},
        },
        elapsed_sec=0.1,
        ordinal=1,
        total=1,
        max_repair_attempts=1,
    )

    assert result["status"] == "fail"
    assert result["checks"]["evidence_refs_known"] is False
    assert result["unknown_evidence_refs"] == ["unknown_ref"]


def test_real_evidence_quality_scoring_requires_relationship_graph_ref_when_configured() -> None:
    case = {
        "case_id": "relationship_quality",
        "agent_id": "industry_supply_chain_analyst",
        "expected_min_observations": 1,
        "expect_unsupported_or_conflict": False,
        "known_evidence_refs": ["industry_ref", "rel_ref"],
        "bounded_evidence_rows": [
            {"evidence_ref": "industry_ref", "source_family": "industry_snapshot", "metadata": {"real_evidence_row": True}},
            {"evidence_ref": "rel_ref", "source_family": "relationship_graph", "metadata": {"real_evidence_row": True}},
        ],
        "quality_expectations": {
            "required_input_source_families": ["industry_snapshot", "relationship_graph"],
            "allowed_observation_source_families": ["industry_snapshot", "relationship_graph"],
            "required_observation_source_families": ["relationship_graph"],
            "required_cited_source_families": ["relationship_graph"],
        },
    }

    result = evaluate_real_evidence_case(
        case,
        route_result={
            "status": "pass",
            "memolet": {
                "agent_id": "industry_supply_chain_analyst",
                "observations": [
                    {
                        "claim": "Industry context only.",
                        "evidence_refs": ["industry_ref"],
                        "source_families": ["industry_snapshot"],
                        "unsupported": False,
                    }
                ],
                "unsupported_claims": [],
                "conflicts": [],
            },
            "validation": {"status": "pass"},
            "routing_trace": {"repair_attempts": 0},
            "model_diagnostics": {"calls": []},
        },
        elapsed_sec=0.1,
        ordinal=1,
        total=1,
        max_repair_attempts=1,
    )

    assert result["status"] == "fail"
    assert result["checks"]["required_observation_source_families_present"] is False
    assert result["checks"]["required_source_family_evidence_refs_cited"] is False


def test_real_evidence_quality_scoring_accepts_expected_unsupported() -> None:
    case = {
        "case_id": "risk",
        "agent_id": "risk_counterevidence_analyst",
        "expected_min_observations": 0,
        "expect_unsupported_or_conflict": True,
        "known_evidence_refs": ["gap_ref"],
        "bounded_evidence_rows": [
            {"evidence_ref": "gap_ref", "source_family": "run_artifact", "metadata": {"real_evidence_row": True}}
        ],
        "quality_expectations": {
            "required_input_source_families": ["run_artifact"],
            "expected_observation_source_families_any": [],
        },
    }
    result = evaluate_real_evidence_case(
        case,
        route_result={
            "status": "pass",
            "memolet": {
                "agent_id": "risk_counterevidence_analyst",
                "observations": [],
                "unsupported_claims": [{"claim": "missing operating income support", "reason": "not in bounded rows"}],
                "conflicts": [],
            },
            "validation": {"status": "pass"},
            "routing_trace": {"repair_attempts": 0},
            "model_diagnostics": {"calls": []},
        },
        elapsed_sec=0.1,
        ordinal=1,
        total=1,
        max_repair_attempts=1,
    )

    assert result["status"] == "pass"
    assert result["checks"]["expected_unsupported_or_conflict"] is True
