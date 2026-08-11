from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, Mapping

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))


from apps.workbench.backend.application.bounded_agent_executor import (
    BOUNDED_DEEPSEEK_BETA_BASE_URL,
    S3_SPECIALIST_MODEL_VIEW_CONTRACT_REF,
    S3_THREE_CELL_BOUNDED_AGENT_INPUT_CONTRACT_REF,
    S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V2_REF,
    BoundedAgentExecutionError,
    DeepSeekS3ThreeCellNodeExecutor,
    S3ThreeCellBoundedAgentAdmission,
    S3ThreeCellBoundedAgentExecutor,
)
from sec_agent.canonical_runtime.models import canonical_digest


CELL_ID = "demand_authenticity_and_sustainability"
INPUT_DIGEST = "a" * 64
RESULT = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s3_t09_specialist_model_view_output_budget_zero_call_repair_v1_0.json"
)
BACKLOG = ROOT / "configs" / "releases" / "fin_ia_0_1_program_release_backlog_v2_0.json"
ROOT_CAUSES = ROOT / "docs" / "project_os" / "root_cause_issue_ledger.jsonl"


def _cell_input() -> dict[str, Any]:
    return {
        "program_cell_id": CELL_ID,
        "runtime_branch": {
            "owner_role": "industry_analyst",
            "evidence_role": "demand_signal",
            "decision_question": "Is demand authentic and durable?",
            "mandatory_judgment_chain": "signal_to_conversion_to_durability",
            "stop_rule": "Stop without promoted evidence and a counterindicator.",
            "what_would_change": "Two weaker conversion quarters.",
            "branch_state": "planned",
            "observation": {"observation_type": "no_runtime_observation", "refs": []},
            "lead_branch_decision": "continue_to_evidence_request",
            "terminal_reason": None,
            "research_run_id": "audit-only-run-id",
        },
        "role_contexts": [
            {
                "target_node": "domain_specialist",
                "context_payload": {
                    "decision_question": "Is demand authentic and durable?",
                    "mandatory_judgment_chain": "signal_to_conversion_to_durability",
                    "evidence_role": "demand_signal",
                    "stop_rule": "Stop without promoted evidence.",
                    "what_would_change": "Two weaker conversion quarters.",
                    "accepted_evidence_refs": ["evidence:1"],
                    "numeric_refs": ["numeric:1"],
                    "typed_gap_refs": ["gap:1"],
                },
                "authority": {
                    "may_request_evidence": True,
                    "may_form_cell_judgment": True,
                    "may_search_privately": False,
                    "may_promote_evidence": False,
                    "may_mutate_case": False,
                },
            },
            {
                "target_node": "evidence_operator",
                "context_payload": {"private_operator_plan": "must-not-enter-model-view"},
                "authority": {"may_execute_local_route": False},
            },
        ],
        "evidence_input": {
            "route_outcome": "candidate_observed_promotion_blocked",
            "candidate_bundle": {
                "candidates": [
                    {
                        "candidate_id": "candidate:1",
                        "document_id": "doc:1",
                        "document_version": "v1",
                        "source_snapshot_ref": "snapshot:1",
                        "source_policy_ref": "issuer-first",
                        "route_id": "local-route",
                        "source_role": "official_issuer",
                        "source_authority_rank": 5,
                        "entity_ref": "NVDA",
                        "period_ref": "latest_quarter",
                        "candidate_kind": "top_k_seed",
                        "section_or_table_ref": "revenue",
                        "metadata_rank": 1,
                        "content_ref": "fixture://doc/1",
                    }
                ]
            },
            "candidate_snapshot": {"duplicate_candidate_body": "x" * 12000},
            "tool_selection_plan": {"audit_plan": "x" * 12000},
            "tool_gateway_preflights": [{"audit_preflight": "x" * 12000}],
            "promotion_assessment": {
                "decision": "candidate_only_pending_claim_source_content_and_corroboration",
                "candidate_refs": ["candidate:1"],
                "context_refs": [],
                "rejected_refs": [],
                "typed_gap_codes": ["claim_source_required"],
                "accepted_evidence_refs": ["evidence:1"],
                "evidence_gate_owner_ref": "EvidenceService",
                "runtime_promotion_authorized": False,
                "writer_citable": False,
                "judgment_eligible": False,
                "persistence_authorized": False,
                "assessment_digest": "audit-only-digest",
            },
            "graph_observation": None,
            "source_followup_request": None,
            "sourcehunter_boundary": {
                "status": "not_eligible_until_parser_or_claim_binding",
                "trigger_reason": "candidate_is_not_evidence",
                "boundary_contract_ref": "source-boundary:v1",
                "source_followup_request_ref": None,
                "exact_network_admission_required": True,
                "network_execution_authorized": False,
                "external_tool_execution_authorized": False,
                "model_execution_authorized": False,
                "request_executed": False,
                "network_calls": 0,
            },
        },
        "numeric_input": {
            "fundamental_decision_cell": {
                "availability": "available_with_boundary",
                "typed_cannot_infer": ["durability_not_proven"],
                "support_boundary": "Revenue does not prove demand durability.",
                "specialist_input_eligible": True,
                "narrative_fill_authorized": False,
            },
            "selected_financial_rows": [
                {"financial_row_id": "numeric:1", "value": "10", "unit": "USD"}
            ],
            "derived_metrics": [],
        },
        "graph_context_input": {
            "product_industry_inputs": [
                {
                    "contract_ref": "product:v1",
                    "status": "context_only",
                    "candidate_refs": ["candidate:1"],
                    "typed_gaps": ["deployment_not_promoted"],
                    "direct_evidence_authorized": False,
                    "writer_citable": False,
                    "projection_input_ref": "graph-product:1",
                }
            ],
            "skill_contracts": [
                {
                    "contract_ref": "graph-skill:v1",
                    "role_ids": ["industry_supply_chain_analyst"],
                    "method_ids": ["customer_supplier_readthrough"],
                    "allowed_output": "bounded_context",
                    "forbidden_output": ["customer_capex_equals_supplier_revenue"],
                    "skill_definition_version_refs": ["skill:1"],
                    "authority_grants": [],
                    "model_execution_authorized": False,
                    "network_execution_authorized": False,
                    "business_write_authorized": False,
                    "contract_version_ref": "graph-skill-contract:1",
                }
            ],
            "graph_edges": [
                {
                    "edge_projection_id": "graph-edge:1",
                    "use_case": "durability_check",
                    "from_ref": "entity:NVDA",
                    "to_ref": f"decision_cell:{CELL_ID}",
                    "edge_type": "CONTEXT_TO_DURABILITY_CHECK",
                    "authority_mode": "candidate_context_only",
                    "claim_boundary": "Context is not evidence.",
                    "direct_evidence_authorized": False,
                    "numeric_authority": False,
                    "mechanism_path_is_fact": False,
                    "writer_citable": False,
                }
            ],
            "market_price_in_contexts": [
                {
                    "market_context_id": "market:1",
                    "status": "typed_gap_no_consensus",
                    "context_refs": [],
                    "authority": "typed_gap_only",
                    "exact_market_fact_authorized": False,
                    "writer_citable": False,
                }
            ],
            "risk_contexts": [
                {
                    "risk_context_id": "risk:1",
                    "risk_type": "demand_reversal",
                    "graph_edge_projection_ref": "graph-edge:1",
                    "impact_mechanism": "Conversion may weaken.",
                    "probability_status": "typed_cannot_infer",
                    "financial_impact_status": "typed_cannot_infer",
                    "support_boundary": "Risk context is not Evidence.",
                    "what_would_change": "Promoted subsequent-period evidence.",
                    "evidence_status": "context_not_evidence",
                    "writer_citable": False,
                }
            ],
            "decision_cells": [{"duplicate_decision_cell": "must-not-enter-model-view"}],
            "decision_cell": {"typed_gaps": ["typed_gap_no_consensus"]},
        },
        "authority_refs": {
            "accepted_evidence_refs": ["evidence:1"],
            "numeric_refs": ["numeric:1"],
            "candidate_refs_not_evidence": ["candidate:1"],
            "graph_context_refs_not_evidence": ["graph-edge:1", "market:1", "risk:1"],
        },
    }


def _payload() -> dict[str, Any]:
    return {
        "input_contract_ref": S3_THREE_CELL_BOUNDED_AGENT_INPUT_CONTRACT_REF,
        "input_digest": INPUT_DIGEST,
        "cell_input": _cell_input(),
        "required_output_layers": [
            "fact_layer",
            "explanation_layer",
            "judgment_layer",
            "remaining_gaps",
            "what_would_change",
        ],
    }


def _admission(**updates: Any) -> S3ThreeCellBoundedAgentAdmission:
    values = {
        "admission_id": "s3-t09-v2-zero-call-repair-test-only",
        "execution_mode": "fake_provider_test_only",
        "output_contract_ref": S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V2_REF,
        "execution_enabled": True,
        "case_id": "case:test",
        "case_version": 1,
        "as_of": "2026-07-21T00:00:00Z",
        "input_digest": INPUT_DIGEST,
        "provider": "deepseek",
        "model": "deepseek-v4-pro",
        "model_ref": "deepseek:deepseek-v4-pro",
        "api_key_env": "DEEPSEEK_API_KEY",
        "base_url": BOUNDED_DEEPSEEK_BETA_BASE_URL,
        "max_semantic_model_calls": 6,
        "max_provider_calls": 6,
        "max_network_calls": 6,
        "max_total_cost_usd": 0.10,
        "specialist_max_output_tokens": 2200,
        "lead_max_output_tokens": 1200,
        "writer_max_output_tokens": 1400,
        "verifier_max_output_tokens": 1000,
    }
    values.update(updates)
    return S3ThreeCellBoundedAgentAdmission(**values)


def _valid_output() -> dict[str, Any]:
    return {
        "program_cell_id": CELL_ID,
        "fact_layer": [
            {
                "fact_id": "fact:1",
                "statement": "The admitted numeric row equals 10 USD.",
                "support_type": "Numeric",
                "support_refs": ["numeric:1"],
                "boundary": "This does not prove demand durability.",
            }
        ],
        "explanation_layer": ["The admitted inputs remain bounded."],
        "judgment_layer": ["Durability cannot yet be inferred."],
        "remaining_gaps": ["Promoted counterevidence is absent."],
        "what_would_change": ["Admit subsequent-period issuer evidence."],
        "terminal_class": "typed_cannot_infer",
    }


def test_repair_result_closes_owned_implementation_gap_without_new_admission() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    backlog = json.loads(BACKLOG.read_text(encoding="utf-8"))
    latest = {
        row["issue_id"]: row
        for row in (
            json.loads(line)
            for line in ROOT_CAUSES.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    }
    assert result["status"] == (
        "pass_zero_call_repair_fixture_verified_replacement_admission_not_issued"
    )
    assert set(result["observed_counts"].values()) == {0}
    assert result["next_action"] == (
        "S3-T09-REPLACEMENT-EXACT-ADMISSION-ISSUANCE-DECISION"
    )
    assert backlog["next_action"]["item_id"] == (
        "S3-T09-OWNER-GRADE-V3-SEGMENTED-TRANSPORT-V5-RESEARCH-LEAD-OUTPUT-TRUNCATION-RESULT-AND-ROOT-CAUSE-DECISION"
    )
    assert backlog["next_action"]["fresh_v3_agent_proof_decision_authorized"] is True
    assert backlog["next_action"]["fresh_v3_exact_admission_issuance_authorized"] is True
    assert backlog["next_action"]["fresh_v3_exact_admission_issued"] is True
    assert backlog["next_action"]["fresh_v3_exact_live_execution_authorized"] is True
    assert backlog["next_action"][
        "S3_T09_specialist_model_view_and_output_budget_repair_execution_authorized"
    ] is True
    assert backlog["next_action"][
        "S3_T09_replacement_exact_admission_issuance_decision_authorized"
    ] is True
    assert backlog["next_action"]["replacement_admission_or_execution_authorized"] is False
    s3 = next(row for row in backlog["slices"] if row["slice_id"] == "S3")
    t09 = next(row for row in s3["items"] if row["item_id"] == "S3-T09")
    assert t09["repair_implemented"] is True
    assert t09["repair_fixture_verified"] is True
    assert t09["replacement_admission_issued"] is True
    assert t09["replacement_admission_consumed"] is True
    issue = latest["RC-P36-035-s3-first-specialist-output-budget-contract-mismatch"]
    assert issue["status"] == (
        "closed_root_cause_repaired_live_proven"
    )
    assert issue["full_chain_blocker"] is False


def test_v2_model_view_is_deterministic_compact_and_role_scoped() -> None:
    admission = _admission()
    _, first, first_binding = DeepSeekS3ThreeCellNodeExecutor._node_request(
        f"domain_specialist:{CELL_ID}", _payload(), admission
    )
    _, second, second_binding = DeepSeekS3ThreeCellNodeExecutor._node_request(
        f"domain_specialist:{CELL_ID}", _payload(), admission
    )
    assert first == second
    assert first_binding == second_binding
    model_view = first["analysis_input"]["cell_input"]
    assert first["analysis_input"]["model_view_contract_ref"] == (
        S3_SPECIALIST_MODEL_VIEW_CONTRACT_REF
    )
    assert first_binding == {
        "model_view_contract_ref": S3_SPECIALIST_MODEL_VIEW_CONTRACT_REF,
        "model_view_digest": canonical_digest(model_view),
    }
    serialized = json.dumps(first, ensure_ascii=False, sort_keys=True)
    assert "tool_selection_plan" not in serialized
    assert "tool_gateway_preflights" not in serialized
    assert "duplicate_candidate_body" not in serialized
    assert "duplicate_decision_cell" not in serialized
    assert "private_operator_plan" not in serialized
    assert "assessment_digest" not in serialized
    full_bytes = len(json.dumps(_payload(), ensure_ascii=False).encode("utf-8"))
    view_bytes = len(serialized.encode("utf-8"))
    assert view_bytes < full_bytes * 0.5


def test_v2_admission_requires_exact_10200_token_budget() -> None:
    _admission().assert_profile_admissible()
    with pytest.raises(ValueError, match="v2_exact_output_budget_required"):
        _admission(specialist_max_output_tokens=1400).assert_profile_admissible()
    with pytest.raises(ValueError, match="v2_exact_output_budget_required"):
        _admission(max_total_cost_usd=0.11).assert_profile_admissible()


def test_v2_specialist_validator_accepts_bounded_output_and_rejects_overflow() -> None:
    cell = _cell_input()
    valid = _valid_output()
    S3ThreeCellBoundedAgentExecutor._validate_specialist_output(
        valid, cell, output_contract_ref=S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V2_REF
    )

    too_many = {**valid, "fact_layer": [{**valid["fact_layer"][0], "fact_id": f"fact:{i}"} for i in range(4)]}
    with pytest.raises(ValueError, match="output_cardinality_invalid"):
        S3ThreeCellBoundedAgentExecutor._validate_specialist_output(
            too_many, cell, output_contract_ref=S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V2_REF
        )

    too_long = {**valid, "judgment_layer": ["x" * 321]}
    with pytest.raises(ValueError, match="output_text_length_invalid"):
        S3ThreeCellBoundedAgentExecutor._validate_specialist_output(
            too_long, cell, output_contract_ref=S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V2_REF
        )

    duplicate_refs = json.loads(json.dumps(valid))
    duplicate_refs["fact_layer"][0]["support_refs"] = ["numeric:1", "numeric:1"]
    with pytest.raises(ValueError, match="fact_or_ref_duplicate_invalid"):
        S3ThreeCellBoundedAgentExecutor._validate_specialist_output(
            duplicate_refs, cell, output_contract_ref=S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V2_REF
        )

    multibyte = json.loads(json.dumps(valid))
    multibyte["fact_layer"] = [
        {
            **valid["fact_layer"][0],
            "fact_id": f"fact:{i}",
            "statement": "界" * 320,
            "boundary": "界" * 320,
        }
        for i in range(3)
    ]
    multibyte["explanation_layer"] = ["界" * 320] * 3
    multibyte["judgment_layer"] = ["界" * 320] * 2
    multibyte["remaining_gaps"] = ["界" * 320] * 4
    multibyte["what_would_change"] = ["界" * 320] * 3
    with pytest.raises(ValueError, match="output_byte_budget_exceeded"):
        S3ThreeCellBoundedAgentExecutor._validate_specialist_output(
            multibyte, cell, output_contract_ref=S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V2_REF
        )


def test_fake_provider_receipt_binds_model_view_and_uses_2200_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_completion(**kwargs: Any) -> Mapping[str, Any]:
        calls.append(dict(kwargs))
        return {
            "status": "ok",
            "finish_reason": "stop",
            "content": json.dumps(_valid_output(), ensure_ascii=False, separators=(",", ":")),
            "input_tokens": 100,
            "output_tokens": 200,
            "total_tokens": 300,
            "call_id": "fake-call-1",
            "provider": "deepseek",
            "model": "deepseek-v4-pro",
            "latency_ms": 1,
            "transport_attempt_count": 1,
            "raw_response": {"usage": {"prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 100}},
        }

    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-placeholder")
    executor = DeepSeekS3ThreeCellNodeExecutor(chat_completion_fn=fake_completion)
    envelope = executor.execute_node(
        f"domain_specialist:{CELL_ID}",
        _payload(),
        _admission(),
        run_identity={"research_run_id": "run:test"},
    )
    request = json.loads(calls[0]["messages"][1]["content"])
    view = request["analysis_input"]["cell_input"]
    assert calls[0]["max_tokens"] == 2200
    assert len(calls) == 1
    assert envelope["version_bindings"]["model_view_contract_ref"] == (
        S3_SPECIALIST_MODEL_VIEW_CONTRACT_REF
    )
    assert envelope["version_bindings"]["model_view_digest"] == canonical_digest(view)
    assert envelope["observed_counts"] == {
        "model_calls": 1,
        "provider_calls": 1,
        "network_calls": 1,
        "source_network_calls": 0,
        "external_tool_calls": 0,
        "live_case_head_writes": 0,
        "evaluation_evidence_promotions": 0,
    }


def test_raw_specialist_output_over_6000_bytes_fails_after_one_fake_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def fake_completion(**_: Any) -> Mapping[str, Any]:
        nonlocal calls
        calls += 1
        return {
            "status": "ok",
            "finish_reason": "stop",
            "content": json.dumps(_valid_output(), ensure_ascii=False) + (" " * 6100),
            "input_tokens": 100,
            "output_tokens": 200,
            "total_tokens": 300,
            "call_id": "fake-call-byte-overflow",
            "provider": "deepseek",
            "model": "deepseek-v4-pro",
            "latency_ms": 1,
            "transport_attempt_count": 1,
            "raw_response": {"usage": {"prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 100}},
        }

    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-placeholder")
    executor = DeepSeekS3ThreeCellNodeExecutor(chat_completion_fn=fake_completion)
    with pytest.raises(BoundedAgentExecutionError) as caught:
        executor.execute_node(
            f"domain_specialist:{CELL_ID}",
            _payload(),
            _admission(),
            run_identity={"research_run_id": "run:byte-overflow"},
        )
    assert calls == 1
    assert caught.value.failure_observation["failure_codes"] == [
        "s3_bounded_specialist_output_byte_budget_exceeded"
    ]
    assert caught.value.failure_observation["raw_provider_response_persisted"] is False
