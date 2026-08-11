from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "eval_multi_agent" / "audit_fin_agent_layer_quality.py"
RUBRIC_PATH = REPO_ROOT / "configs" / "fin_agent_quality_rubric_v0_1.json"


def test_research_lead_activation_audit_passes_clean_summary() -> None:
    module = _load_script()
    rubric = module._read_json(RUBRIC_PATH)
    summary = {
        "schema_version": "sec_agent_research_lead_activation_diagnostic_v0.1",
        "run_id": "unit_research_lead",
        "gate_status": "pass",
        "cases": [
            {
                "case_id": "case_a",
                "status": "pass",
                "checks": {
                    "llm_route_pass": True,
                    "validation_pass": True,
                    "mode_match": True,
                    "required_agents_present": True,
                    "forbidden_agents_absent": True,
                    "evidence_requirement_validation_pass": True,
                },
            }
        ],
    }

    audit = module.audit_summary(summary, rubric=rubric)

    assert audit["gate_status"] == "pass"
    assert audit["source_type"] == "research_lead_activation"
    assert audit["weighted_score"] >= 2.4
    assert audit["stages"][0]["stage_id"] == "research_lead"


def test_research_lead_activation_audit_fails_missing_required_check() -> None:
    module = _load_script()
    rubric = module._read_json(RUBRIC_PATH)
    summary = {
        "schema_version": "sec_agent_research_lead_activation_diagnostic_v0.1",
        "run_id": "unit_research_lead_fail",
        "gate_status": "fail",
        "cases": [
            {
                "case_id": "case_a",
                "status": "fail",
                "checks": {
                    "llm_route_pass": True,
                    "validation_pass": True,
                    "mode_match": False,
                    "required_agents_present": True,
                    "forbidden_agents_absent": True,
                    "evidence_requirement_validation_pass": True,
                },
            }
        ],
    }

    audit = module.audit_summary(summary, rubric=rubric)

    assert audit["gate_status"] == "fail"
    assert "research_lead_stage_gate_failed" in audit["quality_flags"]
    assert "mode_match" in audit["stages"][0]["failed_checks"]


def test_real_chain_audit_uses_layer_checks_and_output_quality_flags() -> None:
    module = _load_script()
    rubric = module._read_json(RUBRIC_PATH)
    summary = {
        "schema_version": "sec_agent_multi_agent_real_llm_chain_eval_v0.1",
        "run_id": "unit_full_chain",
        "gate_status": "pass",
        "output_quality_audit": {
            "issue_counts": {
                "low_rendered_claim_token_efficiency": 1,
                "low_memo_chars_per_token": 1,
                "memo_writer_retry_cost_present": 1,
            },
            "case_risk_levels": {"case_a": "medium"},
        },
        "cases": [
            {
                "case_id": "case_a",
                "required_agents": [
                    "research_lead",
                    "sec_operator",
                    "memo_writer",
                    "verifier",
                    "renderer",
                ],
                "expected_specialist_agents": [],
                "rendered_answer_chars": 400,
                "rendered_answer_has_evidence_refs": True,
                "rendered_answer_preview": "Key memo claims: claim refs=ref_1",
                "agent_audit": {
                    "verifier": {
                        "input_projection": {
                            "projected_claim_count": 1
                        }
                    }
                },
                "layer_checks": {
                    "research_lead": {
                        "llm_invoked": True,
                        "llm_calls_ok": True,
                        "validation_pass": True,
                        "execution_mode_match": True,
                        "required_agents_present": True,
                        "forbidden_agents_absent": True,
                        "forbidden_scope_absent": True,
                    },
                    "evidence_operators": {
                        "expected_operator_agents_called": True,
                        "expected_tool_names_called": True,
                        "tool_ownership_valid": True,
                        "tool_budget_lte": True,
                        "no_budget_loop_break": True,
                        "no_duplicate_loop_break": True,
                    },
                    "memo_verifier": {
                        "memo_llm_pass": True,
                        "memo_status_allowed": True,
                        "rendered_answer_has_memo_claims": True,
                        "rendered_answer_has_evidence_refs": True,
                        "claim_verification_pass": True,
                        "verifier_llm_pass": True,
                    },
                },
            }
        ],
    }

    audit = module.audit_summary(summary, rubric=rubric)

    assert audit["source_type"] == "real_llm_full_chain"
    assert audit["gate_status"] == "fail"
    assert "low_rendered_claim_token_efficiency" in audit["quality_flags"]
    assert any(stage["stage_id"] == "memo_writer" and stage["gate_status"] == "pass" for stage in audit["stages"])


def test_real_chain_audit_skips_memo_verifier_for_deterministic_lookup() -> None:
    module = _load_script()
    rubric = module._read_json(RUBRIC_PATH)
    summary = {
        "schema_version": "sec_agent_multi_agent_real_llm_chain_eval_v0.1",
        "run_id": "unit_exact_lookup",
        "gate_status": "pass",
        "output_quality_audit": {"issue_counts": {}, "case_risk_levels": {"case_exact": "none"}},
        "cases": [
            {
                "case_id": "case_exact",
                "execution_mode": "deterministic_lookup",
                "memo_status": "",
                "claim_verification": "",
                "required_agents": ["sec_operator", "renderer"],
                "expected_specialist_agents": [],
                "rendered_answer_chars": 200,
                "rendered_answer_has_evidence_refs": True,
                "rendered_answer_preview": "单指标结果 证据=ref_1",
                "layer_checks": {
                    "research_lead": {
                        "llm_invoked": True,
                        "llm_calls_ok": True,
                        "validation_pass": True,
                        "execution_mode_match": True,
                        "required_agents_present": True,
                        "forbidden_agents_absent": True,
                        "forbidden_scope_absent": True,
                    },
                    "evidence_operators": {
                        "expected_operator_agents_called": True,
                        "expected_tool_names_called": True,
                        "tool_ownership_valid": True,
                        "tool_budget_lte": True,
                        "no_budget_loop_break": True,
                        "no_duplicate_loop_break": True,
                    },
                    "memo_verifier": {
                        "memo_llm_pass": True,
                        "memo_status_allowed": True,
                        "rendered_answer_has_memo_claims": True,
                        "rendered_answer_has_evidence_refs": True,
                        "claim_verification_pass": True,
                        "verifier_llm_pass": True,
                    },
                },
            }
        ],
    }

    audit = module.audit_summary(summary, rubric=rubric)
    stages = {stage["stage_id"]: stage for stage in audit["stages"]}

    assert stages["memo_writer"]["gate_status"] == "skipped"
    assert stages["verifier"]["gate_status"] == "skipped"


def test_real_chain_audit_infers_universe_and_specialists_from_activated_agents() -> None:
    module = _load_script()
    rubric = module._read_json(RUBRIC_PATH)
    summary = {
        "schema_version": "sec_agent_multi_agent_real_llm_chain_eval_v0.1",
        "run_id": "unit_deep_research",
        "gate_status": "pass",
        "output_quality_audit": {"issue_counts": {}, "case_risk_levels": {"case_deep": "none"}},
        "cases": [
            {
                "case_id": "case_deep",
                "execution_mode": "deep_research",
                "memo_status": "draft",
                "claim_verification": "pass",
                "activated_agents": [
                    "research_lead",
                    "universe_relationship",
                    "fundamental_analyst",
                    "industry_supply_chain_analyst",
                    "memo_writer",
                    "verifier",
                    "renderer",
                ],
                "rendered_answer_chars": 500,
                "rendered_answer_has_evidence_refs": True,
                "rendered_answer_preview": "Key memo claims: claim refs=ref_1",
                "agent_audit": {"verifier": {"input_projection": {"projected_claim_count": 1}}},
                "layer_checks": {
                    "research_lead": {
                        "llm_invoked": True,
                        "llm_calls_ok": True,
                        "validation_pass": True,
                        "execution_mode_match": True,
                        "required_agents_present": True,
                        "forbidden_agents_absent": True,
                        "forbidden_scope_absent": True,
                    },
                    "universe_relationship": {
                        "llm_invoked_when_expected": True,
                        "llm_calls_ok": True,
                        "validation_pass_when_expected": True,
                    },
                    "evidence_operators": {
                        "expected_operator_agents_called": True,
                        "expected_tool_names_called": True,
                        "tool_ownership_valid": True,
                        "tool_budget_lte": True,
                        "no_budget_loop_break": True,
                        "no_duplicate_loop_break": True,
                    },
                    "specialists": {
                        "expected_routes_present": True,
                        "expected_routes_valid": True,
                        "real_evidence_quality_pass": True,
                        "verification_status_valid": True,
                    },
                    "memo_verifier": {
                        "memo_llm_pass": True,
                        "memo_status_allowed": True,
                        "rendered_answer_has_memo_claims": True,
                        "rendered_answer_has_evidence_refs": True,
                        "claim_verification_pass": True,
                        "verifier_llm_pass": True,
                    },
                },
            }
        ],
    }

    audit = module.audit_summary(summary, rubric=rubric)
    stages = {stage["stage_id"]: stage for stage in audit["stages"]}

    assert stages["universe_relationship"]["gate_status"] == "pass"
    assert stages["specialists"]["gate_status"] == "pass"


def test_universe_relationship_audit_passes_clean_summary() -> None:
    module = _load_script()
    rubric = module._read_json(RUBRIC_PATH)
    summary = {
        "schema_version": "sec_agent_universe_relationship_diagnostic_v0.1",
        "run_id": "unit_universe",
        "gate_status": "pass",
        "cases": [
            {
                "case_id": "case_a",
                "status": "pass",
                "checks": {
                    "relationship_lookup_has_rows": True,
                    "llm_route_pass": True,
                    "fallback_not_used": True,
                    "validation_pass": True,
                    "plan_relationships_present": True,
                    "relationship_refs_present": True,
                    "relationship_scope_only": True,
                    "financial_fact_policy_preserved": True,
                    "economic_link_map_pass": True,
                    "economic_entities_present": True,
                    "economic_links_present": True,
                    "economic_mechanisms_present": True,
                    "investment_implications_present": True,
                },
            }
        ],
    }

    audit = module.audit_summary(summary, rubric=rubric)

    assert audit["gate_status"] == "pass"
    assert audit["source_type"] == "universe_relationship"
    assert audit["stages"][0]["stage_id"] == "universe_relationship"


def test_evidence_operator_audit_passes_clean_summary() -> None:
    module = _load_script()
    rubric = module._read_json(RUBRIC_PATH)
    summary = {
        "schema_version": "sec_agent_evidence_operator_diagnostic_v0.1",
        "run_id": "unit_evidence_ops",
        "gate_status": "pass",
        "cases": [
            {
                "case_id": "case_a",
                "status": "pass",
                "checks": {
                    "expected_operator_agents_called": True,
                    "expected_tool_names_called": True,
                    "tool_ownership_valid": True,
                    "tool_budget_lte": True,
                    "no_budget_loop_break": True,
                    "no_duplicate_loop_break": True,
                    "real_retrieval_mode_required": True,
                    "sec_search_not_dry_run": True,
                    "sec_search_errors_absent": True,
                    "sec_search_context_rows_present": True,
                    "sec_search_bm25_candidates_present": True,
                    "sec_search_bge_rerank_present": True,
                    "bge_cuda_when_auto_and_available": True,
                    "exact_value_ledger_rows_present": True,
                    "market_rows_present": True,
                    "industry_rows_present": True,
                    "relationship_rows_available": True,
                    "row_payload_usable": True,
                },
            }
        ],
    }

    audit = module.audit_summary(summary, rubric=rubric)

    assert audit["gate_status"] == "pass"
    assert audit["source_type"] == "evidence_operators"
    assert audit["stages"][0]["stage_id"] == "evidence_operators"


def test_coverage_reflection_audit_passes_clean_summary() -> None:
    module = _load_script()
    rubric = module._read_json(RUBRIC_PATH)
    summary = {
        "schema_version": "sec_agent_coverage_reflection_diagnostic_v0.1",
        "run_id": "unit_coverage_reflection",
        "gate_status": "pass",
        "cases": [
            {
                "case_id": "case_a",
                "status": "pass",
                "checks": {
                    "coverage_report_present": True,
                    "searchable_gaps_classified": True,
                    "second_pass_decision_present": True,
                    "source_gap_boundary_valid": True,
                    "second_pass_gain_or_bounded_reason": True,
                    "no_duplicate_or_budget_loop_break": True,
                    "s3_rows_available_for_reflection": True,
                },
            }
        ],
    }

    audit = module.audit_summary(summary, rubric=rubric)

    assert audit["gate_status"] == "pass"
    assert audit["source_type"] == "coverage_reflection"
    assert audit["stages"][0]["stage_id"] == "coverage_reflection"


def test_judgment_memo_audit_passes_clean_summary() -> None:
    module = _load_script()
    rubric = module._read_json(RUBRIC_PATH)
    checks = {
        "graph_stopped_after_verifier": True,
        "s5_specialist_case_passed": True,
        "judgment_plan_present": True,
        "s6_aggregate_supported_claims_present": True,
        "memo_thesis_plan_present": True,
        "memo_thesis_pack_present": True,
        "memo_thesis_pack_ready": True,
        "memo_writer_allowed": True,
        "memo_route_pass": True,
        "memo_not_fallback": True,
        "memo_claims_present": True,
        "memo_claim_count_min_when_ready": True,
        "memo_thesis_plan_carried": True,
        "memo_raw_rows_not_consumed": True,
        "memo_tool_calls_not_requested": True,
        "verifier_pass": True,
    }
    summary = {
        "schema_version": "sec_agent_judgment_memo_diagnostic_v0.1",
        "run_id": "unit_judgment_memo",
        "gate_status": "pass",
        "metrics": {"memo_repair_attempts_total": 0},
        "cases": [{"case_id": "case_a", "status": "pass", "checks": checks}],
    }

    audit = module.audit_summary(summary, rubric=rubric)

    assert audit["gate_status"] == "pass"
    assert audit["source_type"] == "judgment_memo"
    assert audit["stages"][0]["stage_id"] == "judgment_memo_verifier"


def test_unknown_schema_fails() -> None:
    module = _load_script()
    rubric = module._read_json(RUBRIC_PATH)

    audit = module.audit_summary({"schema_version": "unknown", "run_id": "unit"}, rubric=rubric)

    assert audit["gate_status"] == "fail"
    assert "unknown_summary_schema" in audit["quality_flags"]


def _load_script():
    spec = importlib.util.spec_from_file_location("audit_fin_agent_layer_quality", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
