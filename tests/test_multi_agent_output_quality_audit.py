from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "eval_multi_agent" / "audit_multi_agent_output_quality.py"


def test_output_quality_audit_flags_high_cost_and_gap_without_second_pass() -> None:
    module = _load_script()
    summary = {
        "run_id": "unit_run",
        "cases": [
            {
                "case_id": "case_a",
                "category": "sector_depth",
                "gate_status": "pass",
                "execution_mode": "deep_research",
                "memo_status": "draft",
                "claim_verification": "pass",
                "specialist_verification": "pass",
                "rendered_answer_preview": "Evidence is incomplete and missing company data.",
                "agent_audit": {
                    "memo_writer": {"diagnostics": {"total_tokens": 21000}},
                    "verifier": {"diagnostics": {"total_tokens": 13000}},
                    "research_lead": {"diagnostics": {"total_tokens": 7000}},
                    "universe_relationship": {"diagnostics": {"total_tokens": 5000}},
                    "evidence_operators": {
                        "tool_calls": [
                            {
                                "agent_id": "sec_operator",
                                "tool_name": "sec_search_filings",
                                "row_count": 16,
                                "source_gap_count": 1,
                                "runtime_summary": {
                                    "candidate_counts": {
                                        "candidate_row_count_pre_rerank": 16,
                                        "candidate_sent_to_bge": 16,
                                    }
                                },
                            }
                        ]
                    },
                    "specialists": {
                        "route_results": [
                            {"agent_id": "fundamental_analyst", "status": "pass", "total_tokens": 6000},
                            {"agent_id": "industry_supply_chain_analyst", "status": "pass", "total_tokens": 6000},
                            {"agent_id": "market_valuation_analyst", "status": "pass", "total_tokens": 6000},
                            {"agent_id": "risk_counterevidence_analyst", "status": "pass", "total_tokens": 6000},
                        ],
                        "real_evidence_quality": {
                            "quality_pass": True,
                            "details": {
                                "fundamental_analyst": {"input_row_count": 16, "input_source_families": ["primary_sec_filing"]},
                                "industry_supply_chain_analyst": {"input_row_count": 16, "input_source_families": ["relationship_graph"]},
                            },
                        },
                    },
                },
            }
        ],
    }
    audit = module.audit_summary(summary)
    case = audit["cases"][0]
    assert case["quality_risk_level"] == "high"
    assert "source_gaps_without_second_pass" in case["quality_flags"]
    assert "specialist_inputs_tightly_capped" in case["quality_flags"]
    assert audit["issue_counts"]["memo_writer_high_token_cost"] == 1


def test_output_quality_audit_markdown_contains_case_table() -> None:
    module = _load_script()
    audit = {"run_id": "unit_run", "cases": [], "run_hypotheses": ["hypothesis"], "issue_counts": {}}
    rendered = module.render_markdown(audit)
    assert "Multi-agent Output Quality Audit" in rendered
    assert "Case Summary" in rendered
    assert "hypothesis" in rendered


def test_output_quality_audit_flags_low_claim_card_density_from_sidecar(tmp_path) -> None:
    module = _load_script()
    case_dir = tmp_path / "case_low_cards"
    case_dir.mkdir()
    (case_dir / "multi_agent_summary.json").write_text(
        """{
  "judgment_plan": {
    "claim_card_stats": {
      "supported_claim_count": 3,
      "memo_slot_count": 4,
      "supported_memo_slot_count": 2
    }
  }
}""",
        encoding="utf-8",
    )
    summary = {
        "run_id": "unit_run",
        "cases": [
            {
                "case_id": "case_low_cards",
                "category": "sector_depth",
                "gate_status": "pass",
                "execution_mode": "deep_research",
                "agent_audit": {"specialists": {"route_results": []}},
            }
        ],
    }

    audit = module.audit_summary(summary, artifact_root=tmp_path)
    flags = audit["cases"][0]["quality_flags"]

    assert "claim_card_density_low" in flags
    assert "memo_outline_under_supported" in flags


def test_output_quality_audit_flags_zero_claim_cards_when_stats_present(tmp_path) -> None:
    module = _load_script()
    case_dir = tmp_path / "case_zero_cards"
    case_dir.mkdir()
    (case_dir / "multi_agent_summary.json").write_text(
        """{
  "verified_judgment_plan": {
    "claim_card_stats": {
      "supported_claim_count": 0,
      "memo_slot_count": 4,
      "supported_memo_slot_count": 0
    }
  }
}""",
        encoding="utf-8",
    )
    summary = {
        "run_id": "unit_run",
        "cases": [
            {
                "case_id": "case_zero_cards",
                "category": "sector_depth",
                "gate_status": "pass",
                "execution_mode": "deep_research",
                "agent_audit": {"specialists": {"route_results": []}},
            }
        ],
    }

    audit = module.audit_summary(summary, artifact_root=tmp_path)
    flags = audit["cases"][0]["quality_flags"]

    assert "claim_card_density_zero" in flags
    assert "claim_card_density_low" in flags


def test_output_quality_audit_does_not_flag_all_specialists_when_priorities_are_distinct(tmp_path) -> None:
    module = _load_script()
    case_dir = tmp_path / "case_prioritized"
    case_dir.mkdir()
    (case_dir / "multi_agent_summary.json").write_text(
        """{
  "agent_priorities": {
    "fundamental_analyst": "primary",
    "industry_supply_chain_analyst": "primary",
    "market_valuation_analyst": "supporting",
    "risk_counterevidence_analyst": "supporting"
  }
}""",
        encoding="utf-8",
    )
    summary = {
        "run_id": "unit_run",
        "cases": [
            {
                "case_id": "case_prioritized",
                "category": "sector_depth",
                "gate_status": "pass",
                "execution_mode": "deep_research",
                "agent_audit": {
                    "specialists": {
                        "route_results": [
                            {"agent_id": "fundamental_analyst", "status": "pass"},
                            {"agent_id": "industry_supply_chain_analyst", "status": "pass"},
                            {"agent_id": "market_valuation_analyst", "status": "pass"},
                            {"agent_id": "risk_counterevidence_analyst", "status": "pass"},
                        ]
                    }
                },
            }
        ],
    }

    audit = module.audit_summary(summary, artifact_root=tmp_path)

    assert "deep_research_all_specialists_active" not in audit["cases"][0]["quality_flags"]


def test_output_quality_audit_does_not_flag_unsearchable_source_gaps_as_second_pass_miss(tmp_path) -> None:
    module = _load_script()
    case_dir = tmp_path / "case_unsearchable_gap"
    case_dir.mkdir()
    (case_dir / "multi_agent_summary.json").write_text(
        """{
  "second_pass": {
    "attempts": 0,
    "quality_gap_count": 0,
    "quality_decision": {"allowed": false, "reason": "no_second_pass_requests"}
  }
}""",
        encoding="utf-8",
    )
    summary = {
        "run_id": "unit_run",
        "cases": [
            {
                "case_id": "case_unsearchable_gap",
                "category": "sector_depth",
                "gate_status": "pass",
                "execution_mode": "deep_research",
                "agent_audit": {
                    "evidence_operators": {
                        "tool_calls": [
                            {"agent_id": "industry_operator", "tool_name": "industry_get_snapshot", "row_count": 1, "source_gap_count": 2}
                        ]
                    },
                    "specialists": {"route_results": []},
                },
            }
        ],
    }

    audit = module.audit_summary(summary, artifact_root=tmp_path)

    assert "source_gaps_without_second_pass" not in audit["cases"][0]["quality_flags"]


def test_output_quality_audit_reports_cost_quality_metrics(tmp_path) -> None:
    module = _load_script()
    case_dir = tmp_path / "case_cost_quality"
    case_dir.mkdir()
    (case_dir / "multi_agent_summary.json").write_text(
        """{
  "verified_judgment_plan": {
    "claim_card_stats": {
      "supported_claim_count": 5,
      "memo_slot_count": 4,
      "supported_memo_slot_count": 4
    }
  }
}""",
        encoding="utf-8",
    )
    summary = {
        "run_id": "unit_run",
        "output_dir": str(tmp_path),
        "cases": [
            {
                "case_id": "case_cost_quality",
                "category": "sector_depth",
                "gate_status": "pass",
                "execution_mode": "deep_research",
                "memo_status": "draft",
                "memo_claim_count": 2,
                "rendered_answer_chars": 500,
                "agent_audit": {
                    "research_lead": {"diagnostics": {"total_tokens": 3000}},
                    "memo_writer": {
                        "route_result": {"attempt_count": 2, "repair_attempts": 1},
                        "diagnostics": {
                            "total_tokens": 4000,
                            "calls": [{"total_tokens": 1000}, {"total_tokens": 3000}],
                        },
                    },
                    "verifier": {"diagnostics": {"total_tokens": 3000}},
                    "specialists": {
                        "route_results": [
                            {"agent_id": "fundamental_analyst", "status": "pass", "total_tokens": 50000}
                        ]
                    },
                },
            }
        ],
    }

    audit = module.audit_summary(summary, artifact_root=tmp_path)
    case = audit["cases"][0]
    stats = case["cost_quality_stats"]

    assert stats["tokens_per_supported_claim_card"] == 12000
    assert stats["tokens_per_rendered_memo_claim"] == 30000
    assert stats["memo_writer_repair_token_ratio"] == 0.75
    assert "low_rendered_claim_token_efficiency" in case["quality_flags"]
    assert "low_claim_card_token_efficiency" in case["quality_flags"]
    assert "low_memo_chars_per_token" in case["quality_flags"]
    assert "memo_writer_retry_cost_present" in case["quality_flags"]


def _load_script():
    spec = importlib.util.spec_from_file_location("multi_agent_output_quality_audit_under_test", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
