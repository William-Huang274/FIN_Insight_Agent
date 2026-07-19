from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.agent_information_economy import (  # noqa: E402
    build_agent_information_economy_summary,
    build_preflight_information_economy,
)


def test_agent_information_economy_passes_dense_low_cost_case() -> None:
    summary = {
        "run_id": "unit_aie_healthy",
        "cases": [
            {
                "case_id": "healthy_case",
                "category": "sector_depth",
                "execution_mode": "deep_research",
                "memo_claim_count": 5,
                "rendered_answer_chars": 3200,
                "agent_audit": {
                    "research_lead": {"diagnostics": {"total_tokens": 4000}},
                    "memo_writer": {"diagnostics": {"total_tokens": 7000}},
                    "verifier": {"diagnostics": {"total_tokens": 2000}},
                    "specialists": {
                        "route_results": [
                            {"agent_id": "fundamental_analyst", "status": "pass", "total_tokens": 5000},
                            {"agent_id": "product_technology_analyst", "status": "pass", "total_tokens": 4500},
                        ],
                        "real_evidence_quality": {
                            "details": {
                                "fundamental_analyst": {"status": "pass", "checks": {"bounded_rows_present": True}},
                                "product_technology_analyst": {"status": "pass", "checks": {"bounded_rows_present": True}},
                            }
                        },
                    },
                },
                "verified_judgment_plan": {
                    "claim_cards": [
                        {"id": "c1", "evidence_refs": ["ev1"]},
                        {"id": "c2", "evidence_refs": ["ev2"]},
                    ]
                },
            }
        ],
    }
    quality = {
        "cases": [
            {
                "case_id": "healthy_case",
                "token_stats": {"total_tokens": 22500, "specialist_tokens": 9500, "memo_writer_tokens": 7000, "verifier_tokens": 2000},
                "cost_quality_stats": {
                    "tokens_per_supported_claim_card": 2812.5,
                    "tokens_per_rendered_memo_claim": 4500,
                    "memo_chars_per_total_token": 0.14222,
                },
                "specialist_stats": {
                    "route_count": 2,
                    "route_results": [
                        {"agent_id": "fundamental_analyst", "status": "pass", "total_tokens": 5000},
                        {"agent_id": "product_technology_analyst", "status": "pass", "total_tokens": 4500},
                    ],
                    "claim_card_stats": {"supported_claim_count": 8},
                },
                "quality_flags": [],
            }
        ]
    }

    audit = build_agent_information_economy_summary(summary, output_quality_audit=quality)

    assert audit["status"] == "pass"
    assert audit["cases"][0]["gate_status"] == "pass"
    assert audit["cases"][0]["issues"] == []
    assert audit["aggregate_metrics"]["tokens_per_supported_claim_card"] == 2812.5


def test_agent_information_economy_fails_high_cost_low_yield_fanout() -> None:
    summary = {
        "run_id": "unit_aie_bad",
        "cases": [
            {
                "case_id": "bad_case",
                "category": "sector_depth",
                "execution_mode": "deep_research",
                "memo_claim_count": 1,
                "rendered_answer_chars": 900,
                "agent_audit": {
                    "memo_writer": {"route_result": {"attempt_count": 2, "repair_attempts": 1}},
                    "specialists": {
                        "route_results": [
                            {
                                "agent_id": "fundamental_analyst",
                                "status": "pass",
                                "total_tokens": 20000,
                                "matched_requirement_count": 0,
                                "reason": "priority_and_required_item_gate_allow_run",
                            },
                            {"agent_id": "product_technology_analyst", "status": "pass", "total_tokens": 18000},
                            {"agent_id": "industry_supply_chain_analyst", "status": "pass", "total_tokens": 17000},
                            {"agent_id": "market_valuation_analyst", "status": "pass", "total_tokens": 15000},
                            {"agent_id": "risk_counterevidence_analyst", "status": "pass", "total_tokens": 14000},
                        ]
                    },
                },
                "memo_answer": {
                    "memo_claims": [
                        {"claim": "weak", "evidence_refs": ["dup_ref", "dup_ref"]},
                    ]
                },
                "verified_judgment_plan": {
                    "claim_cards": [
                        {"id": "c1", "evidence_refs": ["dup_ref"]},
                        {"id": "c2", "evidence_refs": ["dup_ref"]},
                    ]
                },
            }
        ],
    }
    quality = {
        "cases": [
            {
                "case_id": "bad_case",
                "token_stats": {"total_tokens": 129000, "specialist_tokens": 84000, "memo_writer_tokens": 25000, "verifier_tokens": 8000},
                "cost_quality_stats": {
                    "tokens_per_supported_claim_card": 57500,
                    "tokens_per_rendered_memo_claim": 115000,
                    "memo_chars_per_total_token": 0.00783,
                    "memo_writer_repair_attempt_ratio": 0.5,
                    "memo_writer_repair_token_ratio": 0.6,
                },
                "specialist_stats": {
                    "route_count": 5,
                    "route_results": [
                        {"agent_id": "fundamental_analyst", "status": "pass", "total_tokens": 20000},
                        {"agent_id": "product_technology_analyst", "status": "pass", "total_tokens": 18000},
                        {"agent_id": "industry_supply_chain_analyst", "status": "pass", "total_tokens": 17000},
                        {"agent_id": "market_valuation_analyst", "status": "pass", "total_tokens": 15000},
                        {"agent_id": "risk_counterevidence_analyst", "status": "pass", "total_tokens": 14000},
                    ],
                    "unsupported_claim_count": 10,
                    "claim_card_stats": {"supported_claim_count": 2},
                },
                "quality_flags": [
                    "high_total_token_cost",
                    "low_claim_card_token_efficiency",
                    "low_rendered_claim_token_efficiency",
                    "memo_payload_not_dense_enough",
                    "specialist_claim_yield_low",
                    "memo_writer_retry_cost_present",
                ],
                "claim_yield_diagnosis": {
                    "suspected_root_layers": ["specialist_claim_conversion_or_selector", "memo_logic_plan_to_writer_payload"]
                },
            }
        ]
    }

    audit = build_agent_information_economy_summary(summary, output_quality_audit=quality)
    case = audit["cases"][0]

    assert audit["status"] == "fail"
    assert case["gate_status"] == "fail"
    assert "high_token_low_supported_claim_yield" in case["issues"]
    assert "high_token_low_rendered_claim_yield" in case["issues"]
    assert "overbroad_specialist_fanout" in case["issues"]
    assert "invalid_information_transfer_proxy" in case["issues"]
    assert "duplicate_evidence_ref_transfer_proxy" in case["issues"]
    assert "repair_loop_agent_failure_proxy" in case["issues"]
    assert "specialist_claim_conversion_or_selector" in case["root_cause_candidates"]
    assert "context_pack_deduplication" in case["root_cause_candidates"]


def test_agent_information_economy_allows_four_specialists_when_claim_yield_is_healthy() -> None:
    summary = {
        "run_id": "unit_aie_four_specialist_cap",
        "cases": [
            {
                "case_id": "four_specialists",
                "execution_mode": "deep_research",
                "memo_claim_count": 6,
                "rendered_answer_chars": 3600,
                "agent_audit": {
                    "specialists": {
                        "route_results": [
                            {"agent_id": "fundamental_analyst", "status": "pass", "total_tokens": 5000},
                            {"agent_id": "product_technology_analyst", "status": "pass", "total_tokens": 5000},
                            {"agent_id": "industry_supply_chain_analyst", "status": "pass", "total_tokens": 5000},
                            {"agent_id": "market_valuation_analyst", "status": "pass", "total_tokens": 5000},
                        ]
                    }
                },
            }
        ],
    }
    quality = {
        "cases": [
            {
                "case_id": "four_specialists",
                "token_stats": {"total_tokens": 36000, "specialist_tokens": 20000, "memo_writer_tokens": 7000, "verifier_tokens": 2000},
                "cost_quality_stats": {
                    "tokens_per_supported_claim_card": 3000,
                    "tokens_per_rendered_memo_claim": 6000,
                    "memo_chars_per_total_token": 0.1,
                },
                "specialist_stats": {
                    "route_count": 4,
                    "route_results": [
                        {"agent_id": "fundamental_analyst", "status": "pass", "total_tokens": 5000},
                        {"agent_id": "product_technology_analyst", "status": "pass", "total_tokens": 5000},
                        {"agent_id": "industry_supply_chain_analyst", "status": "pass", "total_tokens": 5000},
                        {"agent_id": "market_valuation_analyst", "status": "pass", "total_tokens": 5000},
                    ],
                    "claim_card_stats": {"supported_claim_count": 12},
                },
                "quality_flags": [],
            }
        ]
    }

    audit = build_agent_information_economy_summary(summary, output_quality_audit=quality)
    case = audit["cases"][0]

    assert audit["status"] == "pass"
    assert "overbroad_specialist_fanout" not in case["issues"]


def test_agent_information_economy_uses_activation_decisions_for_required_item_fanout() -> None:
    summary = {
        "run_id": "unit_aie_activation_decisions",
        "cases": [
            {
                "case_id": "activation_case",
                "execution_mode": "deep_research",
                "memo_claim_count": 4,
                "agent_audit": {
                    "specialists": {
                        "activation_decisions": [
                            {
                                "agent_id": "fundamental_analyst",
                                "priority": "primary",
                                "decision": "run",
                                "reason": "fundamental_core_financial_rows_visible",
                                "matched_requirement_count": 0,
                                "explicit_intent": False,
                            },
                            {
                                "agent_id": "market_valuation_analyst",
                                "priority": "supporting",
                                "decision": "run",
                                "reason": "priority_and_required_item_gate_allow_run",
                                "matched_requirement_count": 0,
                                "explicit_intent": False,
                            },
                            {
                                "agent_id": "risk_counterevidence_analyst",
                                "priority": "supporting",
                                "decision": "skipped",
                                "reason": "supporting_specialist_skipped_no_matching_required_item_or_explicit_intent",
                                "matched_requirement_count": 0,
                                "explicit_intent": False,
                            },
                        ],
                        "route_results": [
                            {
                                "agent_id": "fundamental_analyst",
                                "status": "pass",
                                "priority": "primary",
                                "total_tokens": 4000,
                                "matched_requirement_count": 0,
                            },
                            {
                                "agent_id": "market_valuation_analyst",
                                "status": "pass",
                                "priority": "supporting",
                                "total_tokens": 3500,
                                "matched_requirement_count": 0,
                                "activation_reason": "priority_and_required_item_gate_allow_run",
                            },
                            {
                                "agent_id": "risk_counterevidence_analyst",
                                "status": "skipped",
                                "priority": "supporting",
                                "total_tokens": 0,
                                "matched_requirement_count": 0,
                                "activation_decision": "skipped",
                            },
                        ],
                    }
                },
            }
        ],
    }
    quality = {
        "cases": [
            {
                "case_id": "activation_case",
                "token_stats": {"total_tokens": 18000, "specialist_tokens": 7500, "memo_writer_tokens": 5000, "verifier_tokens": 1500},
                "specialist_stats": {
                    "route_results": [
                        {"agent_id": "fundamental_analyst", "status": "pass"},
                        {"agent_id": "market_valuation_analyst", "status": "pass"},
                        {"agent_id": "risk_counterevidence_analyst", "status": "skipped"},
                    ],
                    "claim_card_stats": {"supported_claim_count": 8},
                },
            }
        ]
    }

    audit = build_agent_information_economy_summary(summary, output_quality_audit=quality)
    case = audit["cases"][0]

    assert case["gate_status"] == "fail"
    assert case["specialists"]["active_agents"] == ["fundamental_analyst", "market_valuation_analyst"]
    assert case["specialists"]["skipped_route_count"] == 1
    assert case["specialists"]["agents_without_required_item_match"] == ["market_valuation_analyst"]
    assert "specialist_without_required_item_match" in case["issues"]


def test_agent_information_economy_flags_prompt_pack_overlap_from_fingerprints() -> None:
    overlap_fingerprint_a = {
        "schema_version": "sec_agent_specialist_input_pack_fingerprint_v0_1",
        "agent_id": "fundamental_analyst",
        "digest": "sha256:fundamental",
        "known_evidence_ref_count": 9,
        "known_evidence_refs": [f"shared_ref_{idx}" for idx in range(9)],
        "component_summaries": {
            "bounded_evidence_rows": {
                "digest": "sha256:samebounded",
                "item_count": 9,
                "evidence_ref_count": 9,
                "approx_chars": 2400,
            }
        },
        "approx_prompt_payload_chars": 2400,
    }
    overlap_fingerprint_b = {
        **overlap_fingerprint_a,
        "agent_id": "product_technology_analyst",
        "digest": "sha256:product",
    }
    summary = {
        "run_id": "unit_aie_prompt_overlap",
        "cases": [
            {
                "case_id": "overlap_case",
                "execution_mode": "deep_research",
                "memo_claim_count": 5,
                "agent_audit": {
                    "specialists": {
                        "route_results": [
                            {
                                "agent_id": "fundamental_analyst",
                                "status": "pass",
                                "input_pack_fingerprint": overlap_fingerprint_a,
                            },
                            {
                                "agent_id": "product_technology_analyst",
                                "status": "pass",
                                "input_pack_fingerprint": overlap_fingerprint_b,
                            },
                        ]
                    }
                },
            }
        ],
    }
    quality = {
        "cases": [
            {
                "case_id": "overlap_case",
                "token_stats": {"total_tokens": 65000, "specialist_tokens": 42000},
                "specialist_stats": {
                    "route_count": 2,
                    "claim_card_stats": {"supported_claim_count": 9},
                    "route_results": [
                        {
                            "agent_id": "fundamental_analyst",
                            "status": "pass",
                            "input_pack_fingerprint": overlap_fingerprint_a,
                        },
                        {
                            "agent_id": "product_technology_analyst",
                            "status": "pass",
                            "input_pack_fingerprint": overlap_fingerprint_b,
                        },
                    ],
                },
                "quality_flags": [],
            }
        ]
    }

    audit = build_agent_information_economy_summary(summary, output_quality_audit=quality)
    case = audit["cases"][0]
    overlap = case["information_transfer"]["prompt_pack_overlap"]

    assert audit["status"] == "fail"
    assert "prompt_pack_overlap_proxy" in case["issues"]
    assert "specialist_input_pack_deduplication_or_coalescing" in case["root_cause_candidates"]
    assert overlap["available"] is True
    assert overlap["same_component_digest_count"] == 1
    assert overlap["duplicate_prompt_evidence_ref_count"] == 9
    assert overlap["same_component_digest_sample"][0]["agents"] == [
        "fundamental_analyst",
        "product_technology_analyst",
    ]


def test_agent_information_economy_reads_memo_writer_input_fingerprint() -> None:
    memo_fingerprint = {
        "schema_version": "sec_agent_memo_writer_input_pack_fingerprint_v0_1",
        "agent_id": "memo_writer",
        "memo_profile": "standard",
        "digest": "sha256:memo",
        "known_evidence_ref_count": 3,
        "known_evidence_refs": ["ref_a", "ref_b", "ref_c"],
        "component_summaries": {
            "memo_logic_plan": {
                "digest": "sha256:logic",
                "item_count": 4,
                "evidence_ref_count": 2,
                "approx_chars": 1400,
            },
            "verified_judgment_plan": {
                "digest": "sha256:judgment",
                "item_count": 6,
                "evidence_ref_count": 3,
                "approx_chars": 2200,
            },
        },
        "approx_prompt_payload_chars": 3600,
        "fingerprint_policy": "fingerprint_only_no_prompt_text_persisted_v0_1",
    }
    summary = {
        "run_id": "unit_aie_memo_fingerprint",
        "cases": [
            {
                "case_id": "memo_case",
                "memo_claim_count": 4,
                "agent_audit": {
                    "memo_writer": {
                        "route_result": {
                            "status": "pass",
                            "attempt_count": 1,
                            "input_pack_fingerprint": memo_fingerprint,
                        }
                    }
                },
            }
        ],
    }

    audit = build_agent_information_economy_summary(summary, output_quality_audit={"cases": []})
    memo_pack = audit["cases"][0]["information_transfer"]["memo_writer_input_pack"]

    assert memo_pack["available"] is True
    assert memo_pack["schema_version"] == "sec_agent_memo_writer_input_pack_fingerprint_v0_1"
    assert memo_pack["known_evidence_ref_count"] == 3
    assert memo_pack["known_evidence_refs_sample"] == ["ref_a", "ref_b", "ref_c"]
    assert memo_pack["largest_components"][0]["component"] == "verified_judgment_plan"
    assert memo_pack["fingerprint_policy"] == "fingerprint_only_no_prompt_text_persisted_v0_1"


def test_agent_information_economy_flags_memo_writer_raw_gate_salvage_failure() -> None:
    summary = {
        "run_id": "unit_aie_memo_raw_gate_failure",
        "cases": [
            {
                "case_id": "memo_gate_case",
                "memo_claim_count": 5,
                "agent_audit": {
                    "memo_writer": {
                        "route_result": {
                            "status": "pass",
                            "attempt_count": 1,
                            "deterministic_salvage_used": True,
                            "raw_output_audit": {
                                "schema_version": "sec_agent_memo_raw_output_audit_v0_1",
                                "deterministic_gate_status": "fail",
                                "deterministic_gate_error_types": [
                                    "analyst_depth_dimension_missing_mechanism_bridge"
                                ],
                                "salvage_triggered": True,
                                "raw_text_persisted": False,
                            },
                        }
                    }
                },
            }
        ],
    }

    audit = build_agent_information_economy_summary(summary, output_quality_audit={"cases": []})
    case = audit["cases"][0]

    assert audit["status"] == "fail"
    assert "memo_writer_raw_gate_or_salvage_failure" in case["issues"]
    assert "memo_raw_output_to_normalized_writer_contract" in case["root_cause_candidates"]
    assert case["repair_loop"]["memo_writer_raw_gate_failed"] is True
    assert case["repair_loop"]["memo_writer_deterministic_salvage_used"] is True


def test_agent_information_economy_reads_research_lead_and_universe_input_fingerprints() -> None:
    lead_fingerprint = {
        "schema_version": "sec_agent_research_lead_input_pack_fingerprint_v0_1",
        "agent_id": "research_lead",
        "digest": "sha256:lead",
        "known_evidence_ref_count": 1,
        "known_evidence_refs": ["lead_ref"],
        "component_summaries": {
            "source_inventory": {
                "digest": "sha256:inventory",
                "item_count": 3,
                "evidence_ref_count": 1,
                "approx_chars": 1200,
            }
        },
        "approx_prompt_payload_chars": 1200,
        "fingerprint_policy": "fingerprint_only_no_prompt_text_persisted_v0_1",
    }
    universe_fingerprint = {
        "schema_version": "sec_agent_universe_relationship_input_pack_fingerprint_v0_1",
        "agent_id": "universe_relationship",
        "digest": "sha256:universe",
        "known_evidence_ref_count": 2,
        "known_evidence_refs": ["rel_ref_a", "rel_ref_b"],
        "component_summaries": {
            "relationship_lookup_prompt_view": {
                "digest": "sha256:lookup",
                "item_count": 4,
                "evidence_ref_count": 2,
                "approx_chars": 1800,
            }
        },
        "approx_prompt_payload_chars": 1800,
        "fingerprint_policy": "fingerprint_only_no_prompt_text_persisted_v0_1",
    }
    summary = {
        "run_id": "unit_aie_upstream_fingerprints",
        "cases": [
            {
                "case_id": "upstream_case",
                "memo_claim_count": 2,
                "agent_audit": {
                    "research_lead": {"input_pack_fingerprint": lead_fingerprint},
                    "universe_relationship": {"input_pack_fingerprint": universe_fingerprint},
                },
            }
        ],
    }

    audit = build_agent_information_economy_summary(summary, output_quality_audit={"cases": []})
    transfer = audit["cases"][0]["information_transfer"]
    lead_pack = transfer["research_lead_input_pack"]
    universe_pack = transfer["universe_relationship_input_pack"]

    assert lead_pack["available"] is True
    assert lead_pack["schema_version"] == "sec_agent_research_lead_input_pack_fingerprint_v0_1"
    assert lead_pack["known_evidence_refs_sample"] == ["lead_ref"]
    assert lead_pack["largest_components"][0]["component"] == "source_inventory"
    assert universe_pack["available"] is True
    assert universe_pack["schema_version"] == "sec_agent_universe_relationship_input_pack_fingerprint_v0_1"
    assert universe_pack["known_evidence_ref_count"] == 2
    assert universe_pack["largest_components"][0]["component"] == "relationship_lookup_prompt_view"


def test_agent_information_economy_reads_verifier_input_fingerprint() -> None:
    verifier_fingerprint = {
        "schema_version": "sec_agent_verifier_input_pack_fingerprint_v0_1",
        "agent_id": "verifier",
        "digest": "sha256:verifier",
        "known_evidence_ref_count": 2,
        "known_evidence_refs": ["ref_a", "ref_b"],
        "component_summaries": {
            "memo_answer": {
                "digest": "sha256:memo",
                "item_count": 3,
                "evidence_ref_count": 2,
                "approx_chars": 900,
            },
            "memo_claim_ref_inventory": {
                "digest": "sha256:claims",
                "item_count": 2,
                "evidence_ref_count": 2,
                "approx_chars": 700,
            },
        },
        "approx_prompt_payload_chars": 1600,
        "fingerprint_policy": "fingerprint_only_no_prompt_text_persisted_v0_1",
    }
    summary = {
        "run_id": "unit_aie_verifier_fingerprint",
        "cases": [
            {
                "case_id": "verifier_case",
                "memo_claim_count": 2,
                "agent_audit": {
                    "verifier": {
                        "input_projection": {
                            "input_pack_fingerprint": verifier_fingerprint,
                        }
                    }
                },
            }
        ],
    }

    audit = build_agent_information_economy_summary(summary, output_quality_audit={"cases": []})
    verifier_pack = audit["cases"][0]["information_transfer"]["verifier_input_pack"]

    assert verifier_pack["available"] is True
    assert verifier_pack["schema_version"] == "sec_agent_verifier_input_pack_fingerprint_v0_1"
    assert verifier_pack["known_evidence_ref_count"] == 2
    assert verifier_pack["largest_components"][0]["component"] == "memo_answer"
    assert verifier_pack["measurement_boundary"] == "verifier_fingerprint_only_no_prompt_text_persisted"


def test_preflight_information_economy_flags_expensive_fanout_before_model_calls() -> None:
    plan = {
        "run_id": "preflight_unit",
        "allowed": False,
        "status": "blocked_preflight_token_budget",
        "estimated_total_tokens": 272000,
        "estimated_paid_call_count": 18,
        "scheduler_advice": {"status": "case_budget_repair_required", "recommended_batch_count": 0},
        "cases": [
            {
                "case_id": "ai_case",
                "estimated_total_tokens": 150000,
                "estimated_paid_call_count": 9,
                "estimated_specialist_count": 5,
                "expected_specialist_agents": [
                    "fundamental_analyst",
                    "product_technology_analyst",
                    "industry_supply_chain_analyst",
                    "market_valuation_analyst",
                    "risk_counterevidence_analyst",
                ],
                "cost_aware_specialist_agents": [
                    "fundamental_analyst",
                    "product_technology_analyst",
                    "industry_supply_chain_analyst",
                    "risk_counterevidence_analyst",
                ],
                "prunable_specialist_agents": ["market_valuation_analyst"],
                "estimated_total_tokens_after_specialist_pruning": 138000,
                "estimated_paid_call_count_after_specialist_pruning": 8,
                "nodes": [
                    {"node": "research_lead", "estimated_total_tokens": 11000},
                    {"node": "fundamental_analyst", "estimated_total_tokens": 20000},
                    {"node": "product_technology_analyst", "estimated_total_tokens": 18000},
                    {"node": "industry_supply_chain_analyst", "estimated_total_tokens": 17000},
                    {"node": "market_valuation_analyst", "estimated_total_tokens": 15000},
                    {"node": "risk_counterevidence_analyst", "estimated_total_tokens": 16000},
                    {"node": "memo_writer", "estimated_total_tokens": 25000},
                    {"node": "verifier", "estimated_total_tokens": 9000},
                    {"node": "universe_relationship", "estimated_total_tokens": 11000},
                ],
            }
        ],
    }

    audit = build_preflight_information_economy(plan)

    assert audit["status"] == "fail"
    assert audit["cases"][0]["status"] == "fail"
    assert audit["issue_counts"]["preflight_case_token_budget_high"] == 1
    assert audit["issue_counts"]["preflight_paid_call_fanout_high"] == 1
    assert audit["issue_counts"]["preflight_specialist_fanout_broad"] == 1
    assert audit["issue_counts"]["preflight_specialist_pruning_available"] == 1
    assert audit["scheduler_advice"]["status"] == "case_budget_repair_required"
    assert audit["cases"][0]["prunable_specialist_agents"] == ["market_valuation_analyst"]
    assert audit["cases"][0]["estimated_paid_call_count_after_specialist_pruning"] == 8


def test_agent_information_economy_prefers_prompt_row_counts_over_data_view_counts() -> None:
    summary = {
        "run_id": "unit_aie_prompt_rows",
        "cases": [
            {
                "case_id": "ai_case",
                "category": "sector_depth",
                "execution_mode": "deep_research",
                "agent_audit": {
                    "specialists": {
                        "route_results": [
                            {
                                "agent_id": "product_technology_analyst",
                                "status": "pass",
                                "prompt_bounded_evidence_row_count": 24,
                            },
                            {
                                "agent_id": "industry_supply_chain_analyst",
                                "status": "pass",
                                "prompt_bounded_evidence_row_count": 20,
                            },
                        ],
                    }
                },
            }
        ],
    }
    quality = {
        "cases": [
            {
                "case_id": "ai_case",
                "specialist_stats": {
                    "route_count": 2,
                    "route_results": [
                        {"agent_id": "product_technology_analyst", "status": "pass"},
                        {"agent_id": "industry_supply_chain_analyst", "status": "pass"},
                    ],
                    "input_rows_by_agent": {
                        "product_technology_analyst": 48,
                        "industry_supply_chain_analyst": 48,
                    },
                },
            }
        ]
    }

    audit = build_agent_information_economy_summary(summary, output_quality_audit=quality)
    specialists = audit["cases"][0]["specialists"]
    transfer = audit["cases"][0]["information_transfer"]

    assert specialists["input_rows_by_agent"] == {
        "product_technology_analyst": 24,
        "industry_supply_chain_analyst": 20,
    }
    assert specialists["data_view_rows_by_agent"] == {
        "product_technology_analyst": 48,
        "industry_supply_chain_analyst": 48,
    }
    assert specialists["input_row_measurement_boundary"] == "prompt_bounded_evidence_row_count_from_route_summary"
    assert transfer["max_specialist_input_rows"] == 24
