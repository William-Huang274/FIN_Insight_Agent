from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (
    BOUNDED_AGENT_ARTIFACT_TYPES,
    BOUNDED_AGENT_COMPARISON_ARTIFACT_TYPE,
    BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE,
    BOUNDED_DEEPSEEK_BETA_BASE_URL,
    BOUNDED_OPENAI_BASE_URL,
    BOUNDED_SPECIALIST_LEAD_OUTPUT_CONTRACT_V1,
    BOUNDED_SPECIALIST_LEAD_OUTPUT_CONTRACT_V2,
    BOUNDED_SPECIALIST_LEAD_OUTPUT_CONTRACT_V3,
    BOUNDED_SPECIALIST_LEAD_OUTPUT_CONTRACT_V4,
    BOUNDED_SPECIALIST_LEAD_JSON_OBJECT_TRANSPORT_REF,
    BOUNDED_SPECIALIST_LEAD_SEGMENTED_TRANSPORT_REF,
    BOUNDED_SPECIALIST_LEAD_STRICT_TOOL_NAME,
    BOUNDED_SPECIALIST_LEAD_STRICT_TRANSPORT_REF,
    BOUNDED_SPECIALIST_LEAD_NATIVE_JSON_SCHEMA_NAME,
    BOUNDED_SPECIALIST_LEAD_NATIVE_JSON_SCHEMA_TRANSPORT_REF,
    CONSUMED_BOUNDED_AGENT_ADMISSION_IDS,
    BoundedAgentAdmission,
    BoundedAgentExecutionError,
    BoundedAgentInputPack,
    DeepSeekBoundedAgentExecutor,
    NativeJsonSchemaResponseAdapter,
    NativeJsonSchemaResponseError,
    build_bounded_agent_executor_for_admission,
)
from sec_agent.canonical_runtime.models import canonical_digest


ADMISSION = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s2_t03_bounded_agent_exact_admission_v1_0.json"
)
ADMISSION_V2 = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s2_t03_bounded_agent_exact_admission_v2_0.json"
)
ADMISSION_V3 = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s2_t03_bounded_agent_exact_admission_v3_0.json"
)
ADMISSION_V4 = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s2_t03_bounded_agent_exact_admission_v4_0.json"
)
ADMISSION_V4_R2 = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s2_t03_bounded_agent_exact_admission_v4_r2.json"
)
REPAIR_CONTRACT = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s2_t03_specialist_lead_output_contract_repair_v2_0.json"
)
REPAIR_CONTRACT_V3 = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s2_t03_specialist_lead_output_contract_repair_v3_0.json"
)
REPAIR_CONTRACT_V4 = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s2_t03_specialist_lead_output_contract_repair_v4_0.json"
)
V4_LIVE_DECISION = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s2_t03_v4_live_validation_decision_v1_0.json"
)
POST_TELEMETRY_STRATEGY_DECISION = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s2_t03_post_telemetry_provider_strategy_decision_v1_0.json"
)
POST_R2_TRANSPORT_PIVOT_DECISION = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s2_t03_post_r2_provider_transport_pivot_decision_v1_0.json"
)
NATIVE_JSON_SCHEMA_EXACT_LIVE_ADMISSION_DECISION = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s2_t03_native_json_schema_exact_live_admission_decision_v1_0.json"
)
NATIVE_JSON_SCHEMA_BINDING_RUNNER_REPAIR = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s2_t03_native_json_schema_admission_binding_runner_wiring_repair_v1_0.json"
)
ADMISSION_V5 = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s2_t03_bounded_agent_exact_admission_v5_0.json"
)
ADMISSION_V5_R2 = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s2_t03_bounded_agent_exact_admission_v5_r2.json"
)
ADMISSION_V6 = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s2_t03_bounded_agent_exact_admission_v6_0.json"
)
GPT_5_6_SOL_ADMISSION_ISSUANCE = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s2_t03_gpt_5_6_sol_exact_admission_issuance_v1_0.json"
)
GPT_5_6_SOL_LIVE_VALIDATION_RESULT = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s2_t03_gpt_5_6_sol_native_live_validation_result_v1_0.json"
)
GPT_5_6_SOL_V5_R2_ADMISSION_ISSUANCE = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s2_t03_gpt_5_6_sol_native_v5_r2_exact_admission_issuance_v1_0.json"
)
GPT_5_6_SOL_V5_R2_LIVE_VALIDATION_RESULT = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s2_t03_gpt_5_6_sol_native_live_validation_r2_result_v1_0.json"
)
DEEPSEEK_SEGMENTED_V4_IMPLEMENTATION = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s2_t03_deepseek_segmented_v4_implementation_v1_0.json"
)
DEEPSEEK_SEGMENTED_V4_ADMISSION_ISSUANCE = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s2_t03_deepseek_segmented_v4_exact_admission_issuance_v1_0.json"
)
DEEPSEEK_SEGMENTED_V4_LIVE_VALIDATION_RESULT = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s2_t03_deepseek_segmented_v4_live_validation_result_v1_0.json"
)


def _admission() -> BoundedAgentAdmission:
    return BoundedAgentAdmission.model_validate(
        json.loads(ADMISSION.read_text(encoding="utf-8"))
    )


def _live_v2_admission() -> BoundedAgentAdmission:
    return BoundedAgentAdmission.model_validate(
        json.loads(ADMISSION_V2.read_text(encoding="utf-8"))
    )


def _v3_admission() -> BoundedAgentAdmission:
    return BoundedAgentAdmission.model_validate(
        json.loads(ADMISSION_V3.read_text(encoding="utf-8"))
    ).model_copy(
        update={
            "admission_id": "fixture-unconsumed-v3-admission",
            "specialist_transport_ref": BOUNDED_SPECIALIST_LEAD_STRICT_TRANSPORT_REF,
            "reasoning_effort": "none",
        }
    )


def _consumed_v4_admission() -> BoundedAgentAdmission:
    return BoundedAgentAdmission.model_validate(
        json.loads(ADMISSION_V4.read_text(encoding="utf-8"))
    )


def _v4_admission() -> BoundedAgentAdmission:
    return _consumed_v4_admission().model_copy(
        update={
            "admission_id": "fixture-unconsumed-v4-admission",
            "specialist_transport_ref": BOUNDED_SPECIALIST_LEAD_STRICT_TRANSPORT_REF,
            "reasoning_effort": "none",
        }
    )


def _issued_v4_r2_admission() -> BoundedAgentAdmission:
    return BoundedAgentAdmission.model_validate(
        json.loads(ADMISSION_V4_R2.read_text(encoding="utf-8"))
    )


def _segmented_v4_admission() -> BoundedAgentAdmission:
    return _v4_admission().model_copy(
        update={
            "admission_id": "fixture-unconsumed-v4-segmented-admission",
            "execution_mode": "bounded_real_agent_one_cell_v4_segmented_fixture",
            "specialist_transport_ref": (
                BOUNDED_SPECIALIST_LEAD_SEGMENTED_TRANSPORT_REF
            ),
            "lead_max_output_tokens": 800,
            "max_semantic_model_calls": 4,
            "max_provider_calls": 4,
            "max_network_calls": 4,
        }
    )


def _input_pack() -> BoundedAgentInputPack:
    candidate = {
        "candidate_id": "candidate-1",
        "title": "NVDA filing",
        "excerpt": "Data center demand and deployments increased; forecasting remains uncertain.",
        "published_at": "2026-01-01",
        "citation_span": "Risk factors",
        "claim_boundary": "Company text does not prove durable market demand.",
        "citation_url": "https://www.sec.gov/Archives/example",
        "promotion_status": "candidate_not_promoted",
    }
    return BoundedAgentInputPack(
        case_id="case_87682fa72e72d7d042dabba0",
        case_version=1,
        query="分析 NVDA 需求真实性与持续性",
        as_of="2026-07-20T00:00:00Z",
        company="NVDA",
        program_cell_id="demand_authenticity_and_sustainability",
        evidence_role="demand_signal",
        source_preview_digest="a" * 64,
        deterministic_analysis_digest="b" * 64,
        decision_question="How durable is demand conversion?",
        candidates=(candidate,),
        deterministic_baseline={
            "judgment": {"judgment_zh_cn": "基线判断"},
            "observed_calls": {
                "model_calls": 0,
                "provider_calls": 0,
                "network_calls": 0,
                "external_tool_calls": 0,
            },
        },
        source_boundary={
            "source_network_calls_allowed": False,
            "candidate_is_evidence": False,
            "writer_source_or_tool_calls": 0,
        },
        input_digest="ce6f5758ecb1e3f5d18d50028cf23214e2c1628ed00a99038c7a8bb5cec228ea",
    )


def test_t03_runner_waits_for_canonical_terminal_state() -> None:
    from scripts.releases.run_fin_ia_0_1_s2_t03_bounded_agent_first_run import (
        _wait_for_bounded_terminal_run,
    )

    profile_ref = "fin01.execution_profile.bounded_agent_internal:v1"

    class _ProjectionResponse:
        status_code = 200
        text = ""

        def __init__(self, state: str) -> None:
            self.state = state

        def json(self) -> dict[str, Any]:
            return {
                "runs": [
                    {
                        "research_run_id": "run-1",
                        "execution_profile_version_ref": profile_ref,
                        "state": self.state,
                    }
                ]
            }

    class _ProjectionClient:
        def __init__(self) -> None:
            self.states = iter(("running", "failed"))
            self.read_count = 0

        def get(self, *_: Any, **__: Any) -> _ProjectionResponse:
            self.read_count += 1
            return _ProjectionResponse(next(self.states))

    client = _ProjectionClient()
    run = _wait_for_bounded_terminal_run(
        client,  # type: ignore[arg-type]
        case_id="case-1",
        execution_profile_version_ref=profile_ref,
        timeout_seconds=1.0,
        poll_interval_seconds=0.0,
    )

    assert client.read_count == 2
    assert run["state"] == "failed"


def _valid_v4_result() -> dict[str, Any]:
    return {
        "output_contract_ref": BOUNDED_SPECIALIST_LEAD_OUTPUT_CONTRACT_V4,
        "specialist_judgment": {
            "thesis": "Bounded thesis",
            "confidence": "medium",
            "evidence_findings": [
                {
                    "candidate_id": "candidate-1",
                    "supported_claim": "Supported",
                    "boundary": "Bounded",
                }
            ],
            "counter_thesis": "Counter",
            "unresolved_gaps": [],
        },
        "lead_adjudication": {
            "decision": "accept",
            "adjudicated_judgment": "Judgment",
            "confidence": "medium",
            "evidence_refs": ["candidate-1"],
            "remaining_gaps": [],
            "what_would_change": [],
        },
    }


def _strict_tool_call(
    arguments: str,
    *,
    name: str = BOUNDED_SPECIALIST_LEAD_STRICT_TOOL_NAME,
) -> dict[str, Any]:
    return {
        "id": "strict-output-fixture",
        "type": "function",
        "function": {"name": name, "arguments": arguments},
    }


def test_t03_admission_is_exact_single_cell_and_fail_closed() -> None:
    admission = _admission()
    admission.assert_profile_admissible()
    assert admission.execution_enabled is True
    assert (
        admission.specialist_output_contract_ref
        == BOUNDED_SPECIALIST_LEAD_OUTPUT_CONTRACT_V1
    )
    assert admission.company == "NVDA"
    assert admission.program_cell_id == "demand_authenticity_and_sustainability"
    assert admission.evidence_role == "demand_signal"
    assert admission.maximum_cell_count == 1
    assert admission.case_id == "case_87682fa72e72d7d042dabba0"
    assert admission.case_version == 1
    assert admission.input_digest == "ce6f5758ecb1e3f5d18d50028cf23214e2c1628ed00a99038c7a8bb5cec228ea"
    assert admission.provider == "deepseek"
    assert admission.model == "deepseek-v4-pro"
    assert admission.max_semantic_model_calls == 3
    assert admission.max_provider_calls == 3
    assert admission.max_network_calls == 3
    assert admission.max_transport_attempts_per_call == 1
    assert admission.retry_budget == 0
    assert admission.max_total_cost_usd == 0.05
    assert admission.source_network_calls_allowed is False
    assert admission.external_tool_calls_allowed is False
    assert admission.live_business_case_head_writes_allowed is False


def test_t03_first_stage_repair_contract_preserves_v1_and_admits_distinct_v2() -> None:
    contract = json.loads(REPAIR_CONTRACT.read_text(encoding="utf-8"))
    assert (
        contract["status"]
        == "live_validation_terminal_failed_shape_telemetry_repaired_no_further_run_admitted"
    )
    assert contract["output_contract_ref"] == BOUNDED_SPECIALIST_LEAD_OUTPUT_CONTRACT_V2
    assert contract["historical_admission"]["consumed"] is True
    assert contract["historical_admission"]["rerunnable"] is False
    assert contract["provider_output_mode"]["deepseek_beta_strict_tool_mode_adopted"] is False
    assert contract["verification"] == {
        "mode": "one_live_validation_then_deterministic_post_run_repair",
        "real_model_calls": 1,
        "network_calls": 1,
        "new_exact_admission_issued": True,
        "rerun_performed": False,
    }
    assert contract["live_validation_admission"] == {
        "admission_ref": "configs/releases/fin_ia_0_1_s2_t03_bounded_agent_exact_admission_v2_0.json",
        "admission_id": "fin01-s2-t03-bounded-agent-v2-contract-live-validation-r1",
        "work_unit_idempotency_key": "fin01-s2-t03-bounded-agent-work-unit-v2-contract-r1",
        "runtime_root": ".codex_runtime/fin01-s2-t03-v2-live-validation-r1",
        "user_authorized": True,
        "execution_started": True,
        "execution_consumed": True,
    }
    assert contract["live_validation_result"]["failure_code"] == (
        "bounded_agent_specialist_outer_schema_invalid"
    )
    assert contract["live_validation_result"]["estimated_cost_usd"] == 0.00175479
    assert contract["live_validation_result"]["artifact_count"] == 0
    assert contract["post_run_deterministic_repair"][
        "secret_safe_output_shape_telemetry"
    ] is True


def test_t03_v2_live_validation_admission_is_new_exact_and_still_bounded() -> None:
    historical = _admission()
    admission = _live_v2_admission()
    admission.assert_profile_admissible()
    assert admission.admission_id != historical.admission_id
    assert admission.execution_mode == "bounded_real_agent_one_cell_v2_contract_live_validation"
    assert admission.specialist_output_contract_ref == BOUNDED_SPECIALIST_LEAD_OUTPUT_CONTRACT_V2
    assert admission.case_id == historical.case_id
    assert admission.case_version == historical.case_version
    assert admission.as_of == historical.as_of
    assert admission.input_digest == historical.input_digest
    assert admission.max_semantic_model_calls == 3
    assert admission.max_provider_calls == 3
    assert admission.max_network_calls == 3
    assert admission.max_transport_attempts_per_call == 1
    assert admission.retry_budget == 0
    assert admission.max_total_cost_usd == 0.05
    assert admission.source_network_calls_allowed is False
    assert admission.external_tool_calls_allowed is False
    assert admission.live_business_case_head_writes_allowed is False


def test_t03_v3_contract_has_one_distinct_exact_admission() -> None:
    contract = json.loads(REPAIR_CONTRACT_V3.read_text(encoding="utf-8"))
    admission = BoundedAgentAdmission.model_validate(
        json.loads(ADMISSION_V3.read_text(encoding="utf-8"))
    )
    admission.assert_profile_admissible()
    assert contract["status"] == (
        "live_validation_terminal_failed_unexpected_outer_keys_admission_consumed"
    )
    assert contract["output_contract_ref"] == BOUNDED_SPECIALIST_LEAD_OUTPUT_CONTRACT_V3
    assert contract["historical_v2_live_validation"]["consumed"] is True
    assert contract["historical_v2_live_validation"]["reusable"] is False
    assert contract["verification"]["real_model_calls_after_v2_failure"] == 1
    assert contract["verification"]["new_exact_admission_issued"] is True
    assert contract["verification"]["live_validation_performed"] is True
    assert contract["live_validation_admission"]["execution_consumed"] is True
    assert contract["live_validation_result"]["failure_code"] == (
        "bounded_agent_specialist_outer_keys_unexpected"
    )
    assert contract["live_validation_result"]["missing_outer_keys"] == []
    assert contract["live_validation_result"]["unexpected_outer_key_count"] == 5
    assert admission.admission_id not in {
        _admission().admission_id,
        _live_v2_admission().admission_id,
    }
    assert admission.execution_mode == (
        "bounded_real_agent_one_cell_v3_contract_live_validation"
    )
    assert admission.specialist_output_contract_ref == (
        BOUNDED_SPECIALIST_LEAD_OUTPUT_CONTRACT_V3
    )
    assert admission.case_id == _admission().case_id
    assert admission.input_digest == _admission().input_digest
    assert admission.max_semantic_model_calls == 3
    assert admission.max_provider_calls == 3
    assert admission.max_network_calls == 3
    assert admission.max_transport_attempts_per_call == 1
    assert admission.retry_budget == 0
    assert admission.max_total_cost_usd == 0.05
    assert admission.source_network_calls_allowed is False
    assert admission.external_tool_calls_allowed is False
    assert admission.live_business_case_head_writes_allowed is False


def test_t03_v4_contract_closes_namespace_and_records_issued_admission() -> None:
    contract = json.loads(REPAIR_CONTRACT_V4.read_text(encoding="utf-8"))
    assert contract["status"] == (
        "v4_live_validation_terminal_failed_strict_tool_arguments_invalid_json"
    )
    assert contract["output_contract_ref"] == BOUNDED_SPECIALIST_LEAD_OUTPUT_CONTRACT_V4
    assert contract["request_document"]["exact_top_level_keys"] == [
        "request_contract",
        "analysis_input",
        "response_shape_example",
    ]
    assert contract["response_envelope"] == {
        "required_outer_keys": ["result"],
        "additional_outer_keys_allowed": False,
        "result_required_keys": [
            "output_contract_ref",
            "specialist_judgment",
            "lead_adjudication",
        ],
        "additional_result_keys_allowed": False,
        "unknown_fields_silently_dropped": False,
        "semantic_synonyms_repaired": False,
    }
    assert contract["canonical_execution_identity"]["execution_identity_source"] == (
        "request idempotency_key"
    )
    assert contract["verification"]["deterministic_fixture_proven"] is True
    assert contract["verification"]["shared_store_distinct_identity_proven"] is True
    assert contract["verification"]["real_model_calls"] == 1
    assert contract["verification"]["network_calls"] == 1
    assert contract["verification"]["new_exact_admission_issued"] is True
    assert contract["verification"]["live_validation_performed"] is True
    assert contract["issued_live_validation_admission"]["execution_consumed"] is True
    assert contract["live_validation_result"]["failure_code"] == (
        "bounded_agent_strict_tool_arguments_invalid_json"
    )
    assert contract["live_validation_result"]["artifact_count"] == 0
    assert contract["post_failure_telemetry_repair"] == {
        "status": "fixture_proven_no_new_admission",
        "generic_failure_code_retained": (
            "bounded_agent_strict_tool_arguments_invalid_json"
        ),
        "observable_parse_subtypes": [
            "json_decode_error",
            "duplicate_key",
            "non_object",
        ],
        "parser_contract": "native_json_object_no_fence_no_duplicate_keys",
        "raw_arguments_persisted": False,
        "argument_digest_persisted": False,
        "argument_length_persisted": False,
        "historical_live_result_subtype_reconstructed": False,
        "parser_relaxed": False,
        "focused_T03_regression": "39 passed in 2.39s",
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "new_exact_admission_issued": False,
    }


def test_t03_v4_live_admission_is_fresh_exact_and_now_consumed() -> None:
    admission = _consumed_v4_admission()
    admission.assert_profile_admissible()
    assert admission.admission_id == (
        "fin01-s2-t03-bounded-agent-v4-strict-tool-live-validation-r1"
    )
    assert admission.admission_id in CONSUMED_BOUNDED_AGENT_ADMISSION_IDS
    assert admission.admission_id not in {
        _admission().admission_id,
        _live_v2_admission().admission_id,
        json.loads(ADMISSION_V3.read_text(encoding="utf-8"))["admission_id"],
    }
    assert admission.execution_enabled is True
    assert admission.execution_mode == (
        "bounded_real_agent_one_cell_v4_strict_tool_live_validation"
    )
    assert admission.specialist_output_contract_ref == (
        BOUNDED_SPECIALIST_LEAD_OUTPUT_CONTRACT_V4
    )
    assert admission.base_url == BOUNDED_DEEPSEEK_BETA_BASE_URL
    assert admission.case_id == _admission().case_id
    assert admission.case_version == _admission().case_version
    assert admission.as_of == _admission().as_of
    assert admission.input_digest == _admission().input_digest
    assert admission.max_semantic_model_calls == 3
    assert admission.max_provider_calls == 3
    assert admission.max_network_calls == 3
    assert admission.max_transport_attempts_per_call == 1
    assert admission.retry_budget == 0
    assert admission.max_total_cost_usd == 0.05
    assert admission.source_network_calls_allowed is False
    assert admission.external_tool_calls_allowed is False
    assert admission.live_business_case_head_writes_allowed is False


def test_t03_v4_live_decision_records_consumed_terminal_failure() -> None:
    decision = json.loads(V4_LIVE_DECISION.read_text(encoding="utf-8"))
    assert decision["status"] == (
        "v4_admission_consumed_terminal_failed_strict_tool_arguments_invalid_json"
    )
    assert decision["decision"] == {
        "issue_ordinary_json_object_v4_admission": False,
        "implement_provider_strict_tool_adapter_first": True,
        "reason": (
            "DeepSeek json_object guarantees valid JSON but not the required nested "
            "key schema; two prior live validations already terminated on output "
            "shape. DeepSeek strict function calling can server-validate a supported "
            "JSON Schema and a named tool choice can force the exact output carrier."
        ),
    }
    transport = decision["selected_output_transport"]
    assert transport["base_url"] == "https://api.deepseek.com/beta"
    assert transport["response_format"] is None
    assert transport["strict"] is True
    assert transport["parallel_tool_calls_parameter_adopted"] is False
    assert transport["tool_call_cardinality_enforced_locally"] is True
    assert transport["tool_name"] == "submit_specialist_lead_result"
    assert transport["tool_choice"]["function"]["name"] == transport["tool_name"]
    assert transport["expected_tool_call_count"] == 1
    assert transport["expected_finish_reason"] == "tool_calls"
    assert transport["external_tool_execution_performed"] is False
    assert decision["implementation_status"] == "deterministic_fixture_proven"
    assert decision["new_exact_v4_admission_issued"] is True
    assert ADMISSION_V4.exists()
    assert decision["issued_admission"] == {
        "issued_at": "2026-07-20T15:05:25+08:00",
        "admission_ref": "configs/releases/fin_ia_0_1_s2_t03_bounded_agent_exact_admission_v4_0.json",
        "admission_id": "fin01-s2-t03-bounded-agent-v4-strict-tool-live-validation-r1",
        "work_unit_idempotency_key": "fin01-s2-t03-bounded-agent-work-unit-v4-strict-tool-r1",
        "runtime_root": ".codex_runtime/fin01-s2-t03-v4-strict-tool-live-validation-r1",
        "specialist_output_contract_ref": BOUNDED_SPECIALIST_LEAD_OUTPUT_CONTRACT_V4,
        "specialist_output_transport_ref": BOUNDED_SPECIALIST_LEAD_STRICT_TRANSPORT_REF,
        "execution_enabled": True,
        "execution_command_authorized_by_user": True,
        "execution_started": True,
        "execution_consumed": True,
        "automatic_execution_or_retry_allowed": False,
    }
    assert decision["actual_model_execution_authorized"] is True
    assert decision["model_calls"] == decision["provider_calls"] == decision["network_calls"] == 1
    result = decision["live_validation_result"]
    assert result["research_run_id"] == "research_run_fin01_b9f50318d58998a5a5c0506f"
    assert result["failure_code"] == "bounded_agent_strict_tool_arguments_invalid_json"
    assert result["provider_finish_reason"] == "tool_calls"
    assert result["total_tokens"] == 3272
    assert result["estimated_cost_usd"] == 0.00200448
    assert result["artifact_count"] == 0
    assert result["automatic_retry_or_rerun_performed"] is False
    assert result["raw_provider_response_persisted"] is False
    assert decision["post_run_verification"] == {
        "focused_T01_T03": "39 passed in 2.17s",
        "related_runtime_S1_S2_workbench": "93 passed in 61.57s",
        "consumed_admission_rejected_before_provider": True,
        "consumed_work_unit_identity_rejected_before_provider": True,
        "stable_source_digests_match": True,
    }
    assert decision["post_failure_telemetry_repair"] == {
        "status": "fixture_proven_no_new_admission",
        "generic_failure_code_retained": (
            "bounded_agent_strict_tool_arguments_invalid_json"
        ),
        "observable_parse_subtypes": [
            "json_decode_error",
            "duplicate_key",
            "non_object",
        ],
        "parser_contract": "native_json_object_no_fence_no_duplicate_keys",
        "raw_arguments_persisted": False,
        "argument_digest_persisted": False,
        "argument_length_persisted": False,
        "historical_live_result_subtype_reconstructed": False,
        "parser_relaxed": False,
        "focused_T03_regression": "39 passed in 2.39s",
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "new_exact_admission_issued": False,
    }
    assert decision["next_action"] == (
        "S2-T03-R2-ORPHANED-RUN-ROOT-CAUSE-REPAIR-DECISION"
    )
    assert decision["independent_review"]["status"] == (
        "pass_after_native_json_and_duplicate_key_repair"
    )
    verification = decision["deterministic_verification"]
    assert verification["arguments_native_json_only"] is True
    assert verification["duplicate_keys_rejected"] is True
    assert verification["fenced_json_rejected"] is True
    assert verification["external_tool_execution_performed"] is False
    assert verification["issued_admission_zero_call_preflight"] == {
        "status": "pass_no_model_call",
        "admission_digest": "61e9e21033eb6ab31e7400067eb455b172d63e421ba42bdd5ca2b09a978639f6",
        "exact_input_match": True,
        "candidate_count": 3,
        "credential_present": True,
        "credential_value_persisted": False,
        "transport_retries": 0,
        "max_output_tokens": 3500,
        "output_only_cost_ceiling_usd": 0.003045,
        "observed_model_provider_network_external_tool_calls": [0, 0, 0, 0],
    }
    assert verification["issuance_contract_regression"] == "38 passed in 1.82s"


def test_t03_consumed_r2_admission_contract_remains_exact() -> None:
    admission = _issued_v4_r2_admission()
    admission.assert_profile_admissible()
    assert admission.admission_id == (
        "fin01-s2-t03-bounded-agent-v4-strict-tool-live-validation-r2"
    )
    assert admission.admission_id in CONSUMED_BOUNDED_AGENT_ADMISSION_IDS
    assert admission.admission_id != _consumed_v4_admission().admission_id
    assert admission.execution_enabled is True
    assert admission.execution_mode == (
        "bounded_real_agent_one_cell_v4_strict_tool_live_validation_r2"
    )
    assert admission.specialist_output_contract_ref == (
        BOUNDED_SPECIALIST_LEAD_OUTPUT_CONTRACT_V4
    )
    assert admission.case_id == "case_87682fa72e72d7d042dabba0"
    assert admission.case_version == 1
    assert admission.input_digest == (
        "ce6f5758ecb1e3f5d18d50028cf23214e2c1628ed00a99038c7a8bb5cec228ea"
    )
    assert admission.base_url == BOUNDED_DEEPSEEK_BETA_BASE_URL
    assert admission.max_semantic_model_calls == 3
    assert admission.max_provider_calls == 3
    assert admission.max_network_calls == 3
    assert admission.max_transport_attempts_per_call == 1
    assert admission.retry_budget == 0
    assert admission.max_total_cost_usd == 0.05
    assert admission.source_network_calls_allowed is False
    assert admission.external_tool_calls_allowed is False
    assert admission.live_business_case_head_writes_allowed is False


@pytest.mark.parametrize(
    ("path", "expected_digest"),
    [
        (ADMISSION, "48db768981ef9e637b065670d40ee4661a8c7bda9c2991be61a5d8269147ea0e"),
        (ADMISSION_V2, "03cf4bfaaa0148f585003b030ae1efa9604cc308a90eea2fe369a7fe3a9136ea"),
        (ADMISSION_V3, "8e058866434b8fe8e276af6deb59df9d11010a01aa869e6ca072f8554473f710"),
        (ADMISSION_V4, "61e9e21033eb6ab31e7400067eb455b172d63e421ba42bdd5ca2b09a978639f6"),
        (
            ADMISSION_V4_R2,
            "671ec47b1085e51bfb43a8af46b8b89918498441ce6d92a3bdbbcd2b62ea0adf",
        ),
    ],
)
def test_t03_historical_admission_digests_survive_new_binding_fields(
    path: Path, expected_digest: str
) -> None:
    admission = BoundedAgentAdmission.model_validate(
        json.loads(path.read_text(encoding="utf-8"))
    )
    assert admission.specialist_transport_ref is None
    assert admission.reasoning_effort is None
    assert canonical_digest(admission.digest_payload()) == expected_digest
    expected_transport = (
        BOUNDED_SPECIALIST_LEAD_JSON_OBJECT_TRANSPORT_REF
        if path in {ADMISSION, ADMISSION_V2, ADMISSION_V3}
        else BOUNDED_SPECIALIST_LEAD_STRICT_TRANSPORT_REF
    )
    assert admission.resolved_specialist_transport_ref() == expected_transport


def test_t03_new_enabled_admission_requires_transport_and_reasoning_binding() -> None:
    unbound = _consumed_v4_admission().model_copy(
        update={"admission_id": "fixture-new-unbound-admission"}
    )
    with pytest.raises(
        ValueError,
        match="bounded_admission_transport_and_reasoning_binding_required",
    ):
        unbound.assert_profile_admissible()

    unsupported = unbound.model_copy(
        update={
            "specialist_transport_ref": "fin01.bounded_agent.unknown:v1",
            "reasoning_effort": "none",
        }
    )
    with pytest.raises(
        ValueError, match="bounded_admission_specialist_transport_unsupported"
    ):
        unsupported.assert_profile_admissible()


def test_t03_native_binding_drives_factory_and_zero_call_preflight(
    tmp_path: Path, monkeypatch
) -> None:
    from scripts.releases.run_fin_ia_0_1_s2_t03_bounded_agent_first_run import preflight

    admission = _native_openai_admission()
    admission.assert_profile_admissible()
    executor = build_bounded_agent_executor_for_admission(admission)
    assert isinstance(executor, DeepSeekBoundedAgentExecutor)
    assert isinstance(
        executor._native_json_schema_adapter, NativeJsonSchemaResponseAdapter
    )

    prepared = {
        "case_id": admission.case_id,
        "case_version": admission.case_version,
        "as_of": admission.as_of,
        "input_digest": admission.input_digest,
        "candidate_count": 3,
    }
    (tmp_path / "prepared_input.json").write_text(
        json.dumps(prepared), encoding="utf-8"
    )
    admission_path = tmp_path / "fixture_native_admission.json"
    admission_path.write_text(
        json.dumps(admission.model_dump(mode="json")), encoding="utf-8"
    )
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-secret-not-persisted")
    result = preflight(
        tmp_path,
        admission_path,
        work_unit_idempotency_key=(
            "fin01-s2-t03-bounded-agent-work-unit-native-fixture"
        ),
    )
    assert result["specialist_output_transport_ref"] == (
        BOUNDED_SPECIALIST_LEAD_NATIVE_JSON_SCHEMA_TRANSPORT_REF
    )
    assert result["specialist_output_tool_name"] is None
    assert result["reasoning_effort"] == "medium"
    assert result["admission_digest"] == canonical_digest(admission.digest_payload())
    assert result["observed_counts"] == {
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "external_tool_calls": 0,
    }
    assert "fixture-secret-not-persisted" not in json.dumps(result)
def test_t03_gpt_5_6_sol_exact_admission_is_bound_consumed_and_reuse_rejected(
    tmp_path: Path, monkeypatch
) -> None:
    from scripts.releases.run_fin_ia_0_1_s2_t03_bounded_agent_first_run import preflight

    admission = BoundedAgentAdmission.model_validate(
        json.loads(ADMISSION_V5.read_text(encoding="utf-8"))
    )
    decision = json.loads(GPT_5_6_SOL_ADMISSION_ISSUANCE.read_text(encoding="utf-8"))
    execution_result = json.loads(
        GPT_5_6_SOL_LIVE_VALIDATION_RESULT.read_text(encoding="utf-8")
    )
    admission.assert_profile_admissible()
    assert admission.provider == "openai"
    assert admission.model_ref == "openai:gpt-5.6-sol"
    assert admission.specialist_transport_ref == (
        BOUNDED_SPECIALIST_LEAD_NATIVE_JSON_SCHEMA_TRANSPORT_REF
    )
    assert admission.reasoning_effort == "medium"
    assert admission.max_transport_attempts_per_call == 1
    assert admission.retry_budget == 0
    assert canonical_digest(admission.digest_payload()) == (
        "fddf22daf385ae09883ad1140dccaa6f7725b9339ce15aba91d949190469dd30"
    )

    prepared = {
        "case_id": admission.case_id,
        "case_version": admission.case_version,
        "as_of": admission.as_of,
        "input_digest": admission.input_digest,
        "candidate_count": 3,
    }
    (tmp_path / "prepared_input.json").write_text(
        json.dumps(prepared), encoding="utf-8"
    )
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-secret-not-persisted")
    work_unit_key = (
        "fin01-s2-t03-bounded-agent-work-unit-native-json-schema-gpt-5-6-sol-r1"
    )
    assert admission.admission_id in CONSUMED_BOUNDED_AGENT_ADMISSION_IDS
    with pytest.raises(RuntimeError, match="t03_consumed_admission_reuse_forbidden"):
        preflight(
            tmp_path,
            ADMISSION_V5,
            work_unit_idempotency_key=work_unit_key,
        )

    fixture_admission = admission.model_copy(
        update={"admission_id": "fixture-unconsumed-gpt-5-6-sol-admission"}
    )
    fixture_path = tmp_path / "fixture_unconsumed_v5.json"
    fixture_path.write_text(
        json.dumps(fixture_admission.model_dump(mode="json")), encoding="utf-8"
    )
    result = preflight(
        tmp_path,
        fixture_path,
        work_unit_idempotency_key="fixture-unconsumed-gpt-5-6-sol-work-unit",
    )
    assert result["status"] == "pass_no_model_call"
    assert result["output_only_cost_ceiling_usd"] == 0.105
    assert result["max_total_cost_usd"] == 0.25
    assert result["observed_counts"] == {
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "external_tool_calls": 0,
    }
    assert decision["status"] == (
        "fresh_exact_admission_consumed_terminal_failed_http_429"
    )
    assert decision["authority"]["actual_model_execution_authorized"] is True
    assert decision["issued_admission"]["consumed"] is True
    assert decision["issued_admission"]["admission_digest"] == canonical_digest(
        admission.digest_payload()
    )
    assert execution_result["status"] == (
        "terminal_failed_http_429_admission_consumed_no_retry"
    )
    assert execution_result["provider_result"]["http_status"] == 429
    assert execution_result["provider_result"]["total_tokens"] == 0
    assert execution_result["canonical_result"]["artifact_count"] == 0
    assert execution_result["failure_classification"] == {
        "class": "openai_http_429_subtype_undetermined",
        "could_be_insufficient_quota_or_credit": True,
        "could_be_rate_limit": True,
        "specific_openai_error_code_persisted": False,
        "specific_openai_error_message_persisted": False,
        "quota_exhaustion_proven": False,
        "ordinary_rate_limit_proven": False,
        "project_owned_subtype_telemetry_gap": True,
        "model_json_schema_failure": False,
        "local_parser_failure": False,
        "known_boundary": (
            "The secret-safe gateway event retained HTTP 429 but not the provider "
            "error code or message, so quota exhaustion and ordinary rate limiting "
            "cannot be distinguished from durable evidence."
        ),
    }
    assert "fixture-secret-not-persisted" not in json.dumps(result)
def test_t03_gpt_5_6_sol_r2_is_same_contract_fresh_identity_and_zero_call_ready(
    tmp_path: Path, monkeypatch
) -> None:
    from scripts.releases.run_fin_ia_0_1_s2_t03_bounded_agent_first_run import preflight

    r1 = BoundedAgentAdmission.model_validate(
        json.loads(ADMISSION_V5.read_text(encoding="utf-8"))
    )
    r2 = BoundedAgentAdmission.model_validate(
        json.loads(ADMISSION_V5_R2.read_text(encoding="utf-8"))
    )
    r2.assert_profile_admissible()
    assert r2.admission_id.endswith("live-validation-r2")
    assert r2.admission_id in CONSUMED_BOUNDED_AGENT_ADMISSION_IDS
    assert r2.execution_mode.endswith("live_validation_r2")
    assert r2.model_copy(
        update={
            "admission_id": r1.admission_id,
            "execution_mode": r1.execution_mode,
        }
    ).model_dump(mode="json") == r1.model_dump(mode="json")

    prepared = {
        "case_id": r2.case_id,
        "case_version": r2.case_version,
        "as_of": r2.as_of,
        "input_digest": r2.input_digest,
        "candidate_count": 3,
    }
    (tmp_path / "prepared_input.json").write_text(
        json.dumps(prepared), encoding="utf-8"
    )
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-secret-not-persisted")
    with pytest.raises(RuntimeError, match="t03_consumed_admission_reuse_forbidden"):
        preflight(
            tmp_path,
            ADMISSION_V5_R2,
            work_unit_idempotency_key=(
                "fin01-s2-t03-bounded-agent-work-unit-native-json-schema-"
                "gpt-5-6-sol-r2"
            ),
        )
    fixture = r2.model_copy(update={"admission_id": "fixture-unconsumed-v5-r2"})
    fixture_path = tmp_path / "fixture_unconsumed_v5_r2.json"
    fixture_path.write_text(
        json.dumps(fixture.model_dump(mode="json")), encoding="utf-8"
    )
    result = preflight(
        tmp_path,
        fixture_path,
        work_unit_idempotency_key="fixture-unconsumed-v5-r2-work-unit",
    )
    assert result["status"] == "pass_no_model_call"
    assert result["admission_digest"] == canonical_digest(fixture.digest_payload())
    assert result["observed_counts"] == {
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "external_tool_calls": 0,
    }
    assert "fixture-secret-not-persisted" not in json.dumps(result)
    issuance = json.loads(
        GPT_5_6_SOL_V5_R2_ADMISSION_ISSUANCE.read_text(encoding="utf-8")
    )
    live_result = json.loads(
        GPT_5_6_SOL_V5_R2_LIVE_VALIDATION_RESULT.read_text(encoding="utf-8")
    )
    assert issuance["status"] == (
        "fresh_same_contract_admission_consumed_terminal_failed_http_401"
    )
    assert issuance["issued_admission"]["admission_digest"] == canonical_digest(
        r2.digest_payload()
    )
    assert live_result["status"] == (
        "terminal_failed_http_401_admission_consumed_no_retry"
    )
    assert live_result["provider_result"]["http_status"] == 401
    assert live_result["provider_result"]["total_tokens"] == 0
    assert live_result["canonical_result"]["orphaned_run"] is False


def test_t03_deepseek_segmented_v6_exact_admission_is_consumed_and_reuse_blocked(
    tmp_path: Path, monkeypatch
) -> None:
    from scripts.releases.run_fin_ia_0_1_s2_t03_bounded_agent_first_run import preflight

    admission = BoundedAgentAdmission.model_validate(
        json.loads(ADMISSION_V6.read_text(encoding="utf-8"))
    )
    admission.assert_profile_admissible()
    assert admission.admission_id == (
        "fin01-s2-t03-bounded-agent-deepseek-segmented-v4-live-validation-r1"
    )
    assert admission.admission_id in CONSUMED_BOUNDED_AGENT_ADMISSION_IDS
    assert admission.provider == "deepseek"
    assert admission.model_ref == "deepseek:deepseek-v4-pro"
    assert admission.specialist_output_contract_ref == (
        BOUNDED_SPECIALIST_LEAD_OUTPUT_CONTRACT_V4
    )
    assert admission.specialist_transport_ref == (
        BOUNDED_SPECIALIST_LEAD_SEGMENTED_TRANSPORT_REF
    )
    assert admission.reasoning_effort == "none"
    assert admission.max_semantic_model_calls == 4
    assert admission.max_provider_calls == 4
    assert admission.max_network_calls == 4
    assert admission.lead_max_output_tokens == 900
    assert admission.max_transport_attempts_per_call == 1
    assert admission.retry_budget == 0
    fixture_admission = admission.model_copy(
        update={"admission_id": "fixture-unconsumed-deepseek-segmented-v4-admission"}
    )
    fixture_path = tmp_path / "fixture_unconsumed_v6.json"
    fixture_path.write_text(
        json.dumps(fixture_admission.model_dump(mode="json")), encoding="utf-8"
    )
    executor = build_bounded_agent_executor_for_admission(fixture_admission)
    assert executor._segmented_specialist_lead is True

    prepared = {
        "case_id": admission.case_id,
        "case_version": admission.case_version,
        "as_of": admission.as_of,
        "input_digest": admission.input_digest,
        "candidate_count": 3,
    }
    (tmp_path / "prepared_input.json").write_text(
        json.dumps(prepared), encoding="utf-8"
    )
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-secret-not-persisted")
    with pytest.raises(RuntimeError, match="t03_consumed_admission_reuse_forbidden"):
        preflight(
            tmp_path,
            ADMISSION_V6,
            work_unit_idempotency_key="fixture-unused-deepseek-segmented-work-unit",
        )
    result = preflight(
        tmp_path,
        fixture_path,
        work_unit_idempotency_key="fixture-unconsumed-deepseek-segmented-work-unit",
    )
    assert result["status"] == "pass_no_model_call"
    assert result["admission_digest"] == canonical_digest(
        fixture_admission.digest_payload()
    )
    assert result["max_output_tokens"] == 4200
    assert result["output_only_cost_ceiling_usd"] == 0.003654
    assert result["specialist_output_tool_name"] is None
    assert result["specialist_strict_schema_requested"] is False
    assert result["observed_counts"] == {
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "external_tool_calls": 0,
    }
    assert "fixture-secret-not-persisted" not in json.dumps(result)
    issuance = json.loads(
        DEEPSEEK_SEGMENTED_V4_ADMISSION_ISSUANCE.read_text(encoding="utf-8")
    )
    assert issuance["status"] == "consumed_terminal_succeeded_no_retry"
    assert issuance["issued_admission"]["admission_digest"] == canonical_digest(
        admission.digest_payload()
    )
    assert issuance["issued_admission"]["consumed"] is True
    assert issuance["authority"]["actual_model_execution_authorized"] is True
    assert issuance["segmented_contract"] == {
        "provider_output_segment_count": 2,
        "specialist_output": "flat_specialist_judgment_object",
        "lead_output": "flat_lead_adjudication_object",
        "provider_tool_calls": 0,
        "provider_strict_schema_requested": False,
        "deterministic_local_exact_v4_assembly": True,
        "canonical_v4_shape_changed": False,
        "writer_and_verifier_paths_changed": False,
        "candidate_and_evidence_validation": "fail_closed",
    }


def test_t03_terminal_inspection_labels_success_without_failure_gap() -> None:
    from scripts.releases.run_fin_ia_0_1_s2_t03_bounded_agent_first_run import (
        _terminal_inspection_labels,
    )

    assert _terminal_inspection_labels("succeeded", None) == (
        "inspected_after_terminal_success",
        None,
    )


def test_t03_deepseek_segmented_v4_live_result_closes_one_cell_without_retry() -> None:
    result = json.loads(
        DEEPSEEK_SEGMENTED_V4_LIVE_VALIDATION_RESULT.read_text(encoding="utf-8")
    )

    assert result["status"] == "terminal_succeeded_admission_consumed_no_retry"
    assert result["canonical_terminal_truth"]["work_unit_state"] == "succeeded"
    assert result["canonical_terminal_truth"]["attempt_state"] == "succeeded"
    assert result["canonical_terminal_truth"]["research_run_state"] == "succeeded"
    assert result["canonical_terminal_truth"]["artifact_count"] == 9
    assert result["provider_execution"]["model_calls"] == 4
    assert result["provider_execution"]["transport_attempts_per_call"] == [
        1,
        1,
        1,
        1,
    ]
    assert result["provider_execution"]["retry_count"] == 0
    assert result["provider_execution"]["fallback_count"] == 0
    assert result["boundary_observation"]["external_tool_calls"] == 0
    assert result["research_quality_review"]["disposition"] == (
        "accept_for_internal_review"
    )
    assert result["acceptance"]["S2_T03"] == "pass"
    assert result["acceptance"]["S2_T04"] == (
        "ready_pending_separate_authorization"
    )


def test_t03_post_telemetry_strategy_records_r2_orphaned_run_truth() -> None:
    decision = json.loads(
        POST_TELEMETRY_STRATEGY_DECISION.read_text(encoding="utf-8")
    )

    assert decision["status"] == (
        "fresh_r2_exact_admission_consumed_canonical_terminalization_failed"
    )
    assert decision["authority"] == {
        "provider_strategy_decision_authorized": True,
        "new_admission_issuance_authorized": True,
        "actual_model_execution_authorized": True,
        "T04_authorized": False,
        "S3_release_or_production_authorized": False,
    }
    assert decision["decision"]["retain_deepseek_beta_strict_named_function"] is True
    assert decision["decision"]["switch_back_to_json_object"] is False
    assert decision["decision"]["switch_provider_now"] is False
    assert decision["decision"]["relax_native_json_parser"] is False
    assert decision["decision"]["recommend_one_fresh_exact_r2_admission"] is True
    assert decision["local_transport_audit"] == {
        "request_uses_exact_beta_base_url": True,
        "request_sends_one_strict_function": True,
        "request_forces_exact_named_tool": True,
        "parallel_tool_calls_parameter_sent": False,
        "outer_provider_response_json_parsed_successfully": True,
        "tool_calls_passed_through_without_normalization": True,
        "function_arguments_passed_through_as_string": True,
        "historical_arguments_persisted": False,
        "project_owned_argument_transformation_gap_found": False,
    }
    proposed = decision["proposed_r2_admission_boundary"]
    assert proposed["status"] == "consumed_running_orphaned"
    assert proposed["same_output_contract_ref"] == (
        BOUNDED_SPECIALIST_LEAD_OUTPUT_CONTRACT_V4
    )
    assert proposed["same_transport_ref"] == (
        BOUNDED_SPECIALIST_LEAD_STRICT_TRANSPORT_REF
    )
    assert proposed["fresh_admission_id_required"] is True
    assert proposed["fresh_work_unit_idempotency_key_required"] is True
    assert proposed["retry_budget"] == 0
    assert proposed["raw_arguments_persisted"] is False
    assert decision["issued_r2_admission"] == {
        "issued_at": "2026-07-20T15:59:55+08:00",
        "issuance_authorized_by_user": True,
        "admission_ref": (
            "configs/releases/"
            "fin_ia_0_1_s2_t03_bounded_agent_exact_admission_v4_r2.json"
        ),
        "admission_id": (
            "fin01-s2-t03-bounded-agent-v4-strict-tool-live-validation-r2"
        ),
        "admission_digest": (
            "671ec47b1085e51bfb43a8af46b8b89918498441ce6d92a3bdbbcd2b62ea0adf"
        ),
        "work_unit_idempotency_key": (
            "fin01-s2-t03-bounded-agent-work-unit-v4-strict-tool-r2"
        ),
        "runtime_root": (
            ".codex_runtime/fin01-s2-t03-v4-strict-tool-live-validation-r2"
        ),
        "execution_enabled": True,
        "execution_command_authorized": True,
        "execution_started": True,
        "execution_consumed": True,
        "zero_call_preflight_status": "pass_no_model_call",
        "exact_input_match": True,
        "candidate_count": 3,
        "credential_value_persisted": False,
        "output_only_cost_ceiling_usd": 0.003045,
        "live_validation_result": {
            "executed_at": "2026-07-20T16:23:18+08:00",
            "provider_call_completed_at": "2026-07-20T16:23:45+08:00",
            "work_unit_id": "wu_p02_5_a5a256b148228113b4583b3a",
            "attempt_id": "attempt_fin01_9537a9c63622cf56604af914",
            "research_run_id": "research_run_fin01_81e6277f9df729f23ab20140",
            "canonical_state": "running",
            "canonical_terminal_reason": None,
            "artifact_count": 0,
            "provider_finish_reason": "tool_calls",
            "model_provider_network_calls": 1,
            "transport_attempts": 1,
            "input_tokens": 1936,
            "output_tokens": 1138,
            "total_tokens": 3074,
            "latency_ms": 19747,
            "maximum_reconstructable_cost_usd": 0.00183222,
            "writer_calls": 0,
            "verifier_calls": 0,
            "fallback_performed": False,
            "automatic_retry_or_rerun_performed": False,
            "raw_provider_response_persisted": False,
            "failure_observation_persisted": False,
            "proven_terminalization_root_cause": (
                "canonical_failure_observation_allowlist_rejects_failure_telemetry"
            ),
            "strict_arguments_parse_failure": (
                "inferred_from_unique_runtime_path_not_durably_persisted"
            ),
            "strict_arguments_parse_subtype": "not_reconstructable",
        },
    }
    assert decision["observed_counts_this_decision"] == {
        "model_calls": 1,
        "provider_calls": 1,
        "network_calls": 1,
        "external_tool_calls": 0,
        "new_admissions_issued": 1,
        "actual_executions": 1,
    }
    assert decision["next_action"] == (
        "S2-T03-R2-ORPHANED-RUN-ROOT-CAUSE-REPAIR-DECISION"
    )


def test_t03_post_r2_transport_pivot_is_distinct_zero_call_and_fail_closed() -> None:
    decision = json.loads(
        POST_R2_TRANSPORT_PIVOT_DECISION.read_text(encoding="utf-8")
    )

    assert decision["status"] == (
        "native_json_schema_response_transport_selected_adapter_not_implemented"
    )
    assert decision["authority"] == {
        "provider_transport_pivot_decision_authorized": True,
        "adapter_implementation_authorized": False,
        "credential_configuration_authorized": False,
        "model_selection_authorized": False,
        "new_admission_issuance_authorized": False,
        "actual_model_execution_authorized": False,
        "T04_authorized": False,
        "S3_release_or_production_authorized": False,
    }
    selected = decision["decision"]
    assert selected["pivot_required"] is True
    assert selected["selected_internal_transport_family"] == (
        "provider_native_json_schema_response"
    )
    assert selected["selected_output_semantics"] == (
        "structured_assistant_response_not_tool_invocation"
    )
    assert selected["first_provider_candidate"] == "openai"
    assert selected["first_provider_api_candidate"] == "responses_api"
    assert selected["provider_and_model_binding_deferred_to_exact_admission"] is True
    assert selected["deepseek_beta_strict_named_function_retained_for_new_live_attempt"] is False
    assert selected["deepseek_json_object_selected"] is False
    assert selected["local_json_repair_or_parser_relaxation_selected"] is False

    historical = decision["historical_evidence"]
    assert historical["deepseek_beta_strict_named_function_live_attempts"] == 2
    assert historical["deepseek_beta_strict_named_function_closed_v4_outputs"] == 0
    assert historical["r2_parse_subtype_reconstructable"] is False
    assert historical["project_owned_terminalization_defect_repaired"] is True
    assert historical["third_same_route_strict_attempt_allowed"] is False

    adapter = decision["adapter_contract_to_implement"]
    assert adapter["internal_transport_ref"] == (
        "fin01.bounded_agent.native_json_schema_response:v1"
    )
    assert adapter["output_contract_ref"] == (
        BOUNDED_SPECIALIST_LEAD_OUTPUT_CONTRACT_V4
    )
    assert adapter["tools_sent"] is False
    assert adapter["tool_choice_sent"] is False
    assert adapter["external_tools_executed"] is False
    assert adapter["schema_strict"] is True
    assert adapter["unknown_properties_allowed"] is False
    assert adapter["local_candidate_evidence_and_semantic_validators_retained"] is True
    assert adapter["response_refusal_is_typed_failure"] is True
    assert adapter["response_incomplete_is_typed_failure"] is True
    assert adapter["raw_provider_response_persisted"] is False
    assert adapter["automatic_transport_fallback_allowed"] is False
    assert adapter["automatic_retry_or_rerun_allowed"] is False

    rejected = {row["option"] for row in decision["rejected_options"]}
    assert rejected == {
        "third_deepseek_beta_strict_named_function_attempt",
        "deepseek_json_object",
        "relax_or_repair_provider_json_locally",
        "provider_switch_with_immediate_live_execution",
    }
    assert decision["deterministic_verification"] == {
        "focused_T03_contracts": "44 passed in 6.39s",
        "combined_S2_T01_T03_contracts": "57 passed in 95.50s",
        "project_os_preflight": "6 passed in 0.36s",
        "json_and_jsonl_parse": "pass",
        "git_diff_check": "pass",
    }
    assert decision["observed_counts_this_decision"] == {
        "model_calls": 0,
        "provider_api_calls": 0,
        "execution_network_calls": 0,
        "external_tool_calls": 0,
        "new_admissions_issued": 0,
        "actual_executions": 0,
        "documentation_network_research_performed": True,
    }
    assert decision["next_action"] == (
        "S2-T03-NATIVE-JSON-SCHEMA-TRANSPORT-ADAPTER-IMPLEMENTATION-DECISION"
    )


def test_t03_exact_model_access_decision_blocks_unsafe_admission_issuance() -> None:
    decision = json.loads(
        NATIVE_JSON_SCHEMA_EXACT_LIVE_ADMISSION_DECISION.read_text(
            encoding="utf-8"
        )
    )

    assert decision["status"] == (
        "exact_model_access_verified_changes_required_before_admission_issuance"
    )
    assert decision["authority"]["account_model_availability_preflight_authorized"] is True
    assert decision["authority"]["new_admission_issuance_authorized"] is False
    assert decision["authority"]["actual_model_execution_authorized"] is False
    preflight = decision["account_model_availability_preflight"]
    assert preflight["requested_exact_model"] == "gpt-5.6-sol"
    assert preflight["available_to_configured_project"] is True
    assert preflight["fallback_model_probe_performed"] is False
    assert preflight["inference_or_generation_performed"] is False

    binding = decision["selected_candidate_binding"]
    assert binding["model_ref"] == "openai:gpt-5.6-sol"
    assert binding["specialist_transport_ref"] == (
        BOUNDED_SPECIALIST_LEAD_NATIVE_JSON_SCHEMA_TRANSPORT_REF
    )
    assert binding["specialist_output_contract_ref"] == (
        BOUNDED_SPECIALIST_LEAD_OUTPUT_CONTRACT_V4
    )
    assert binding["reasoning_effort_machine_bound"] is False
    assert binding["exact_admission_issued"] is False

    blockers = set(decision["independent_review"]["project_owned_blockers"])
    assert blockers == {
        "runner_preflight_hardcodes_deepseek_v4_pro_and_beta_base_url",
        "runner_factory_hardcodes_DeepSeekBoundedAgentExecutor_without_native_adapter",
        "BoundedAgentAdmission_has_no_specialist_transport_ref_binding",
        "BoundedAgentAdmission_has_no_reasoning_effort_binding",
        "native_adapter_is_fixture_proven_only_through_explicit_test_injection",
    }
    assert decision["observed_counts_this_decision"] == {
        "provider_api_metadata_calls": 1,
        "model_inference_or_generation_calls": 0,
        "execution_network_calls": 0,
        "external_tool_calls": 0,
        "new_admissions_issued": 0,
        "actual_executions": 0,
    }
    assert decision["next_action"] == (
        "S2-T03-NATIVE-JSON-SCHEMA-ADMISSION-BINDING-AND-RUNNER-WIRING-REPAIR"
    )


def test_t03_binding_runner_repair_contract_closes_owned_gap_without_issuance() -> None:
    repair = json.loads(
        NATIVE_JSON_SCHEMA_BINDING_RUNNER_REPAIR.read_text(encoding="utf-8")
    )
    assert repair["status"] == (
        "fixture_proven_after_independent_review_exact_admission_issuance_decision_pending"
    )
    assert repair["authority"]["zero_call_admission_binding_repair_authorized"] is True
    assert repair["authority"]["new_admission_issuance_authorized"] is False
    assert repair["authority"]["actual_model_execution_authorized"] is False
    implementation = repair["implementation"]
    assert implementation["admission_fields_added"] == [
        "specialist_transport_ref",
        "reasoning_effort",
    ]
    assert implementation["transport_selected_from_provider_guessing"] is False
    assert implementation["transport_selected_from_exact_admission_binding"] is True
    assert implementation["runner_factory_uses_exact_binding"] is True
    assert implementation["default_application_runtime_silently_switched"] is False
    assert implementation["automatic_fallback_added"] is False
    assert repair["historical_compatibility"][
        "historical_admission_digests"
    ] == {
        "fin_ia_0_1_s2_t03_bounded_agent_exact_admission_v1_0.json": (
            "48db768981ef9e637b065670d40ee4661a8c7bda9c2991be61a5d8269147ea0e"
        ),
        "fin_ia_0_1_s2_t03_bounded_agent_exact_admission_v2_0.json": (
            "03cf4bfaaa0148f585003b030ae1efa9604cc308a90eea2fe369a7fe3a9136ea"
        ),
        "fin_ia_0_1_s2_t03_bounded_agent_exact_admission_v3_0.json": (
            "8e058866434b8fe8e276af6deb59df9d11010a01aa869e6ca072f8554473f710"
        ),
        "fin_ia_0_1_s2_t03_bounded_agent_exact_admission_v4_0.json": (
            "61e9e21033eb6ab31e7400067eb455b172d63e421ba42bdd5ca2b09a978639f6"
        ),
        "fin_ia_0_1_s2_t03_bounded_agent_exact_admission_v4_r2.json": (
            "671ec47b1085e51bfb43a8af46b8b89918498441ce6d92a3bdbbcd2b62ea0adf"
        ),
    }
    assert repair["historical_compatibility"][
        "historical_v1_v2_v3_transport_ref"
    ] == BOUNDED_SPECIALIST_LEAD_JSON_OBJECT_TRANSPORT_REF
    assert repair["historical_compatibility"][
        "historical_json_object_transport_reopened_for_new_admissions"
    ] is False
    assert repair["deterministic_verification"]["provider_calls"] == 0
    assert repair["deterministic_verification"]["new_admissions_issued"] == 0
    assert repair["next_action"] == (
        "S2-T03-NATIVE-JSON-SCHEMA-GPT-5-6-SOL-EXACT-ADMISSION-ISSUANCE-DECISION"
    )


def test_t03_strict_tool_schema_closes_every_object_and_binds_candidate_enum() -> None:
    tool = DeepSeekBoundedAgentExecutor._specialist_strict_tool(
        _input_pack(),
        output_contract_ref=BOUNDED_SPECIALIST_LEAD_OUTPUT_CONTRACT_V4,
    )
    function = tool["function"]
    assert tool["type"] == "function"
    assert function["name"] == BOUNDED_SPECIALIST_LEAD_STRICT_TOOL_NAME
    assert function["strict"] is True

    observed_types: set[str] = set()

    def visit(schema: dict[str, Any]) -> None:
        schema_type = schema.get("type")
        if isinstance(schema_type, str):
            observed_types.add(schema_type)
        if schema_type == "object":
            properties = schema["properties"]
            assert schema["required"] == list(properties)
            assert schema["additionalProperties"] is False
            for child in properties.values():
                visit(child)
        elif schema_type == "array":
            assert "minItems" not in schema
            assert "maxItems" not in schema
            visit(schema["items"])

    visit(function["parameters"])
    assert observed_types == {"object", "array", "string"}
    result = function["parameters"]["properties"]["result"]
    candidate = result["properties"]["specialist_judgment"]["properties"][
        "evidence_findings"
    ]["items"]["properties"]["candidate_id"]
    assert candidate["enum"] == ["candidate-1"]


def test_t03_v4_strict_tool_preflight_is_zero_call_and_rejects_consumed_identity(
    tmp_path: Path, monkeypatch
) -> None:
    from scripts.releases.run_fin_ia_0_1_s2_t03_bounded_agent_first_run import preflight

    prepared = {
        "case_id": "case_87682fa72e72d7d042dabba0",
        "case_version": 1,
        "as_of": "2026-07-20T00:00:00Z",
        "input_digest": "ce6f5758ecb1e3f5d18d50028cf23214e2c1628ed00a99038c7a8bb5cec228ea",
        "candidate_count": 3,
    }
    (tmp_path / "prepared_input.json").write_text(
        json.dumps(prepared), encoding="utf-8"
    )
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-secret-not-persisted")
    v4_admission_path = tmp_path / "fixture_v4_admission.json"
    v4_admission_path.write_text(
        json.dumps(_v4_admission().model_dump(mode="json")), encoding="utf-8"
    )
    key = "fin01-s2-t03-bounded-agent-work-unit-v4-fixture"
    result = preflight(tmp_path, v4_admission_path, work_unit_idempotency_key=key)
    assert result["status"] == "pass_no_model_call"
    assert result["work_unit_idempotency_key"] == key
    assert result["credential_present"] is True
    assert result["credential_value_persisted"] is False
    assert (
        result["specialist_output_transport_ref"]
        == BOUNDED_SPECIALIST_LEAD_STRICT_TRANSPORT_REF
    )
    assert result["specialist_output_tool_name"] == BOUNDED_SPECIALIST_LEAD_STRICT_TOOL_NAME
    assert result["specialist_strict_schema_requested"] is True
    assert result["specialist_external_tool_execution_allowed"] is False
    assert result["observed_counts"] == {
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "external_tool_calls": 0,
    }
    assert "fixture-secret-not-persisted" not in json.dumps(result)
    non_beta_path = tmp_path / "fixture_v4_non_beta_admission.json"
    non_beta_path.write_text(
        json.dumps(
            _v4_admission()
            .model_copy(update={"base_url": "https://api.deepseek.com"})
            .model_dump(mode="json")
        ),
        encoding="utf-8",
    )
    with pytest.raises(
        RuntimeError, match="t03_strict_tool_provider_binding_required"
    ):
        preflight(tmp_path, non_beta_path, work_unit_idempotency_key=key)
    with pytest.raises(
        RuntimeError, match="t03_specialist_output_contract_v4_required"
    ):
        preflight(tmp_path, ADMISSION_V2, work_unit_idempotency_key=key)
    with pytest.raises(
        RuntimeError, match="t03_consumed_work_unit_identity_reuse_forbidden"
    ):
        preflight(
            tmp_path,
            v4_admission_path,
            work_unit_idempotency_key="fin01-s2-t03-bounded-agent-work-unit-v1",
        )
    with pytest.raises(
        RuntimeError, match="t03_consumed_work_unit_identity_reuse_forbidden"
    ):
        preflight(
            tmp_path,
            v4_admission_path,
            work_unit_idempotency_key=(
                "fin01-s2-t03-bounded-agent-work-unit-v4-strict-tool-r1"
            ),
        )
    with pytest.raises(RuntimeError, match="t03_consumed_admission_reuse_forbidden"):
        preflight(tmp_path, ADMISSION_V3, work_unit_idempotency_key=key)
    with pytest.raises(RuntimeError, match="t03_consumed_admission_reuse_forbidden"):
        preflight(tmp_path, ADMISSION_V4, work_unit_idempotency_key=key)


def test_t03_consumed_v1_contract_is_rejected_before_provider_call(monkeypatch) -> None:
    import sec_agent.llm_gateway as gateway

    calls = []
    monkeypatch.setattr(gateway, "chat_completion", lambda **kwargs: calls.append(kwargs))
    with pytest.raises(
        ValueError, match="bounded_specialist_output_contract_v4_required"
    ):
        DeepSeekBoundedAgentExecutor().execute(
            _input_pack(),
            _admission(),
            run_identity={
                "case_id": "case_87682fa72e72d7d042dabba0",
                "work_unit_id": "wu-1",
                "attempt_id": "attempt-1",
                "research_run_id": "run-1",
            },
        )
    assert calls == []


def test_t03_consumed_v2_contract_is_rejected_before_provider_call(monkeypatch) -> None:
    import sec_agent.llm_gateway as gateway

    calls = []
    monkeypatch.setattr(gateway, "chat_completion", lambda **kwargs: calls.append(kwargs))
    with pytest.raises(
        ValueError, match="bounded_specialist_output_contract_v4_required"
    ):
        DeepSeekBoundedAgentExecutor().execute(
            _input_pack(),
            _live_v2_admission(),
            run_identity={
                "case_id": "case_87682fa72e72d7d042dabba0",
                "work_unit_id": "wu-v2-consumed",
                "attempt_id": "attempt-v2-consumed",
                "research_run_id": "run-v2-consumed",
            },
        )
    assert calls == []


def test_t03_unconsumed_v3_contract_is_rejected_before_provider_call(monkeypatch) -> None:
    import sec_agent.llm_gateway as gateway

    calls = []
    monkeypatch.setattr(gateway, "chat_completion", lambda **kwargs: calls.append(kwargs))
    with pytest.raises(ValueError, match="bounded_specialist_output_contract_v4_required"):
        DeepSeekBoundedAgentExecutor().execute(
            _input_pack(),
            _v3_admission(),
            run_identity={
                "case_id": "case_87682fa72e72d7d042dabba0",
                "work_unit_id": "wu-v3-contract",
                "attempt_id": "attempt-v3-contract",
                "research_run_id": "run-v3-contract",
            },
        )
    assert calls == []


def test_t03_consumed_v3_admission_is_rejected_before_provider_call(monkeypatch) -> None:
    import sec_agent.llm_gateway as gateway

    calls = []
    monkeypatch.setattr(gateway, "chat_completion", lambda **kwargs: calls.append(kwargs))
    consumed = BoundedAgentAdmission.model_validate(
        json.loads(ADMISSION_V3.read_text(encoding="utf-8"))
    )
    with pytest.raises(ValueError, match="bounded_agent_admission_consumed"):
        DeepSeekBoundedAgentExecutor().execute(
            _input_pack(),
            consumed,
            run_identity={
                "case_id": "case_87682fa72e72d7d042dabba0",
                "work_unit_id": "wu-v3-consumed",
                "attempt_id": "attempt-v3-consumed",
                "research_run_id": "run-v3-consumed",
            },
        )
    assert calls == []


def test_t03_consumed_v4_admission_is_rejected_before_provider_call(monkeypatch) -> None:
    import sec_agent.llm_gateway as gateway

    calls = []
    monkeypatch.setattr(gateway, "chat_completion", lambda **kwargs: calls.append(kwargs))
    with pytest.raises(ValueError, match="bounded_agent_admission_consumed"):
        DeepSeekBoundedAgentExecutor().execute(
            _input_pack(),
            _consumed_v4_admission(),
            run_identity={
                "case_id": "case_87682fa72e72d7d042dabba0",
                "work_unit_id": "wu-v4-consumed",
                "attempt_id": "attempt-v4-consumed",
                "research_run_id": "run-v4-consumed",
            },
        )
    assert calls == []


def test_t03_consumed_v4_r2_admission_is_rejected_before_provider_call(monkeypatch) -> None:
    import sec_agent.llm_gateway as gateway

    calls = []
    monkeypatch.setattr(gateway, "chat_completion", lambda **kwargs: calls.append(kwargs))
    with pytest.raises(ValueError, match="bounded_agent_admission_consumed"):
        DeepSeekBoundedAgentExecutor().execute(
            _input_pack(),
            _issued_v4_r2_admission(),
            run_identity={
                "case_id": "case_87682fa72e72d7d042dabba0",
                "work_unit_id": "wu-v4-r2-consumed",
                "attempt_id": "attempt-v4-r2-consumed",
                "research_run_id": "run-v4-r2-consumed",
            },
        )
    assert calls == []


def test_t03_v4_executor_rejects_non_beta_provider_binding_before_call(
    monkeypatch,
) -> None:
    import sec_agent.llm_gateway as gateway

    calls = []
    monkeypatch.setattr(gateway, "chat_completion", lambda **kwargs: calls.append(kwargs))
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-secret-not-persisted")
    admission = _v4_admission().model_copy(
        update={"base_url": "https://api.deepseek.com"}
    )
    with pytest.raises(
        ValueError, match="bounded_specialist_strict_tool_provider_binding_required"
    ):
        DeepSeekBoundedAgentExecutor().execute(
            _input_pack(),
            admission,
            run_identity={
                "case_id": "case_87682fa72e72d7d042dabba0",
                "work_unit_id": "wu-non-beta",
                "attempt_id": "attempt-non-beta",
                "research_run_id": "run-non-beta",
            },
        )
    assert calls == []


def test_t03_executor_is_three_call_secret_safe_and_persists_no_raw_reasoning(
    monkeypatch,
) -> None:
    import sec_agent.llm_gateway as gateway

    responses = [
        {"result": {
            "output_contract_ref": BOUNDED_SPECIALIST_LEAD_OUTPUT_CONTRACT_V4,
            "specialist_judgment": {
                "thesis": "Reported deployment supports conversion but not proven durability.",
                "confidence": "medium",
                "evidence_findings": [
                    {
                        "candidate_id": "candidate-1",
                        "supported_claim": "Reported demand conversion is visible.",
                        "boundary": "Durability is not established.",
                    }
                ],
                "counter_thesis": "Timing and forecasting may reverse.",
                "unresolved_gaps": ["Cross-period persistence"],
            },
            "lead_adjudication": {
                "decision": "accept",
                "adjudicated_judgment": "Conversion is supported; sustainability remains conditional.",
                "confidence": "medium",
                "evidence_refs": ["candidate-1"],
                "remaining_gaps": ["Cross-period persistence"],
                "what_would_change": ["Subsequent filing evidence"],
            },
        }},
        {
            "title_zh_cn": "NVDA 需求真实性与持续性",
            "executive_summary_zh_cn": "需求转化获得支持，但持续性仍待跨期验证。",
            "sections": [
                {
                    "heading_zh_cn": "判断",
                    "content_zh_cn": "当前证据支持转化，不足以证明持续性。",
                    "evidence_refs": ["candidate-1"],
                }
            ],
            "limitations_zh_cn": ["缺少跨期持续性证据"],
        },
        {
            "semantic_fidelity": {"status": "pass", "score": 90, "issues": []},
            "financial_coherence": {"status": "pass", "score": 88, "issues": []},
            "recommendation": "accept_for_internal_review",
            "material_gain_assessment": "Agent output makes the conditionality more explicit.",
        },
    ]
    calls = []

    def fake_chat_completion(**kwargs):
        calls.append(kwargs)
        index = len(calls) - 1
        first_stage = index == 0
        return {
            "status": "ok",
            "call_id": f"call-{index + 1}",
            "provider": "deepseek",
            "model": "deepseek-v4-pro",
            "content": "" if first_stage else json.dumps(responses[index]),
            "tool_calls": (
                [
                    {
                        "id": "strict-output-1",
                        "type": "function",
                        "function": {
                            "name": BOUNDED_SPECIALIST_LEAD_STRICT_TOOL_NAME,
                            "arguments": json.dumps(responses[index]),
                        },
                    }
                ]
                if first_stage
                else []
            ),
            "finish_reason": "tool_calls" if first_stage else "stop",
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
            "latency_ms": 10,
            "transport_attempt_count": 1,
            "raw_response": {
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "prompt_cache_miss_tokens": 100,
                },
                "choices": [{"message": {"reasoning_content": "must not persist"}}],
            },
        }

    monkeypatch.setattr(gateway, "chat_completion", fake_chat_completion)
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-secret-never-persist")
    output = DeepSeekBoundedAgentExecutor().execute(
        _input_pack(),
        _v4_admission(),
        run_identity={
            "case_id": "case_87682fa72e72d7d042dabba0",
            "work_unit_id": "wu-1",
            "attempt_id": "attempt-1",
            "research_run_id": "run-1",
        },
    )
    assert len(calls) == 3
    assert all(row["enable_thinking"] is False for row in calls)
    assert all(row["api_key_env"] == "DEEPSEEK_API_KEY" for row in calls)
    assert all(row["base_url"] == BOUNDED_DEEPSEEK_BETA_BASE_URL for row in calls)
    assert all(row["chat_completions_path"] == "/chat/completions" for row in calls)
    assert all("test-secret-never-persist" not in json.dumps(row) for row in calls)
    assert tuple(row.artifact_type for row in output.artifacts) == BOUNDED_AGENT_ARTIFACT_TYPES
    comparison = next(
        row.payload
        for row in output.artifacts
        if row.artifact_type == BOUNDED_AGENT_COMPARISON_ARTIFACT_TYPE
    )
    assert comparison["comparison_status"] == "pending_distinct_deterministic_run"
    assert comparison["agent_research_run_id"] == "run-1"
    assert comparison["deterministic_research_run_id"] is None
    assert comparison["runs_must_be_distinct"] is True
    manifest = next(
        row.payload
        for row in output.artifacts
        if row.artifact_type == BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE
    )
    assert manifest["observed_counts"]["model_calls"] == 3
    assert manifest["observed_counts"]["source_network_calls"] == 0
    assert (
        manifest["specialist_output_contract_ref"]
        == BOUNDED_SPECIALIST_LEAD_OUTPUT_CONTRACT_V4
    )
    assert manifest["specialist_output_adaptations"] == []
    assert (
        manifest["specialist_output_transport_ref"]
        == BOUNDED_SPECIALIST_LEAD_STRICT_TRANSPORT_REF
    )
    assert manifest["specialist_output_tool_name"] == BOUNDED_SPECIALIST_LEAD_STRICT_TOOL_NAME
    assert manifest["specialist_strict_schema_requested"] is True
    assert manifest["specialist_external_tool_executed"] is False
    strict_call = calls[0]
    assert strict_call["response_format"] is None
    assert strict_call["tool_choice"] == {
        "type": "function",
        "function": {"name": BOUNDED_SPECIALIST_LEAD_STRICT_TOOL_NAME},
    }
    assert "parallel_tool_calls" not in strict_call
    assert len(strict_call["tools"]) == 1
    function = strict_call["tools"][0]["function"]
    assert function["name"] == BOUNDED_SPECIALIST_LEAD_STRICT_TOOL_NAME
    assert function["strict"] is True
    parameters = function["parameters"]
    assert parameters["required"] == ["result"]
    assert parameters["additionalProperties"] is False
    result_schema = parameters["properties"]["result"]
    assert set(result_schema["required"]) == {
        "output_contract_ref",
        "specialist_judgment",
        "lead_adjudication",
    }
    assert result_schema["additionalProperties"] is False
    finding_schema = result_schema["properties"]["specialist_judgment"][
        "properties"
    ]["evidence_findings"]["items"]
    assert finding_schema["properties"]["candidate_id"]["enum"] == ["candidate-1"]
    assert all(row["tools"] is None for row in calls[1:])
    assert all(row["tool_choice"] is None for row in calls[1:])
    assert all(row["response_format"] == {"type": "json_object"} for row in calls[1:])
    specialist_prompt = json.loads(calls[0]["messages"][1]["content"])
    assert (
        specialist_prompt["request_contract"]["output_contract_ref"]
        == BOUNDED_SPECIALIST_LEAD_OUTPUT_CONTRACT_V4
    )
    assert (
        specialist_prompt["response_shape_example"]["result"]["specialist_judgment"][
            "evidence_findings"
        ][0]["candidate_id"]
        == "candidate-1"
    )
    assert set(specialist_prompt) == {
        "request_contract",
        "analysis_input",
        "response_shape_example",
    }
    assert specialist_prompt["request_contract"]["response_outer_keys"] == ["result"]
    assert specialist_prompt["request_contract"]["additional_properties_allowed"] is False
    assert "required_schema" not in specialist_prompt
    serialized = output.model_dump_json()
    assert "reasoning_content" not in serialized
    assert "must not persist" not in serialized
    assert "test-secret-never-persist" not in serialized


def test_t03_deepseek_segmented_route_assembles_exact_v4_and_uses_four_calls(
    monkeypatch,
) -> None:
    import sec_agent.llm_gateway as gateway

    responses = [
        {
            "thesis": "Reported deployment supports conversion but not proven durability.",
            "confidence": "medium",
            "evidence_findings": [
                {
                    "candidate_id": "candidate-1",
                    "supported_claim": "Reported demand conversion is visible.",
                    "boundary": "Durability is not established.",
                }
            ],
            "counter_thesis": "Timing and forecasting may reverse.",
            "unresolved_gaps": ["Cross-period persistence"],
        },
        {
            "decision": "accept",
            "adjudicated_judgment": (
                "Conversion is supported; sustainability remains conditional."
            ),
            "confidence": "medium",
            "evidence_refs": ["candidate-1"],
            "remaining_gaps": ["Cross-period persistence"],
            "what_would_change": ["Subsequent filing evidence"],
        },
        {
            "title_zh_cn": "NVDA 需求真实性与持续性",
            "executive_summary_zh_cn": "需求转化获得支持，但持续性仍待跨期验证。",
            "sections": [
                {
                    "heading_zh_cn": "判断",
                    "content_zh_cn": "当前证据支持转化，不足以证明持续性。",
                    "evidence_refs": ["candidate-1"],
                }
            ],
            "limitations_zh_cn": ["缺少跨期持续性证据"],
        },
        {
            "semantic_fidelity": {"status": "pass", "score": 90, "issues": []},
            "financial_coherence": {"status": "pass", "score": 88, "issues": []},
            "recommendation": "accept_for_internal_review",
            "material_gain_assessment": "Conditionality is explicit.",
        },
    ]
    calls: list[dict[str, Any]] = []

    def fake_chat_completion(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        value = responses[len(calls) - 1]
        return {
            "status": "ok",
            "call_id": f"segmented-{len(calls)}",
            "provider": "deepseek",
            "model": "deepseek-v4-pro",
            "content": json.dumps(value),
            "tool_calls": [],
            "finish_reason": "stop",
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
            "latency_ms": 10,
            "transport_attempt_count": 1,
            "raw_response": {"usage": {"prompt_cache_miss_tokens": 100}},
        }

    admission = _segmented_v4_admission()
    admission.assert_profile_admissible()
    executor = build_bounded_agent_executor_for_admission(admission)
    assert executor._segmented_specialist_lead is True
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-secret-never-persist")
    monkeypatch.setattr(gateway, "chat_completion", fake_chat_completion)
    output = executor.execute(
        _input_pack(),
        admission,
        run_identity={
            "case_id": "case_87682fa72e72d7d042dabba0",
            "work_unit_id": "wu-segmented",
            "attempt_id": "attempt-segmented",
            "research_run_id": "run-segmented",
        },
    )

    assert len(calls) == 4
    assert all(row["response_format"] == {"type": "json_object"} for row in calls)
    assert all(row["tools"] is None and row["tool_choice"] is None for row in calls)
    specialist_request = json.loads(calls[0]["messages"][1]["content"])
    lead_request = json.loads(calls[1]["messages"][1]["content"])
    assert "lead_adjudication" not in specialist_request["required_schema"]
    assert set(lead_request["validated_specialist_judgment"]) == {
        "thesis",
        "confidence",
        "evidence_findings",
        "counter_thesis",
        "unresolved_gaps",
    }
    manifest = next(
        row.payload
        for row in output.artifacts
        if row.artifact_type == BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE
    )
    assert manifest["observed_counts"]["model_calls"] == 4
    assert manifest["specialist_output_contract_ref"] == (
        BOUNDED_SPECIALIST_LEAD_OUTPUT_CONTRACT_V4
    )
    assert manifest["specialist_output_transport_ref"] == (
        BOUNDED_SPECIALIST_LEAD_SEGMENTED_TRANSPORT_REF
    )
    assert manifest["specialist_output_segment_count"] == 2
    assert manifest["specialist_output_assembly"] == "deterministic_local_v4"
    assert manifest["specialist_strict_schema_requested"] is False
    judgment = next(
        row.payload
        for row in output.artifacts
        if row.artifact_type == "bounded_agent_judgment"
    )
    assert judgment["specialist_judgment"] == responses[0]
    assert judgment["lead_adjudication"] == responses[1]
    trace = next(
        event
        for event in output.trace_events
        if event["event_type"] == "BOUNDED_AGENT_LEAD_ADJUDICATED"
    )
    assert trace["event_payload"]["call_ref"] == "segmented-2"
    assert "test-secret-never-persist" not in output.model_dump_json()
    implementation = json.loads(
        DEEPSEEK_SEGMENTED_V4_IMPLEMENTATION.read_text(encoding="utf-8")
    )
    assert implementation["status"] == "implemented_fixture_pass_live_not_executed"
    assert implementation["contract_invariants"]["canonical_v4_shape_changed"] is False
    assert implementation["segmented_transport"]["future_exact_call_cap"] == 4
    assert implementation["authority"]["deepseek_live_execution_performed"] is False


def test_t03_deepseek_segmented_route_fails_closed_before_writer_on_bad_lead_ref(
    monkeypatch,
) -> None:
    import sec_agent.llm_gateway as gateway

    values = iter(
        (
            {
                "thesis": "Bounded thesis.",
                "confidence": "medium",
                "evidence_findings": [
                    {
                        "candidate_id": "candidate-1",
                        "supported_claim": "Bounded claim.",
                        "boundary": "Durability is not established.",
                    }
                ],
                "counter_thesis": "Bounded counter-thesis.",
                "unresolved_gaps": ["Cross-period persistence"],
            },
            {
                "decision": "accept",
                "adjudicated_judgment": "Invalid evidence binding.",
                "confidence": "medium",
                "evidence_refs": ["candidate-not-supplied"],
                "remaining_gaps": ["Cross-period persistence"],
                "what_would_change": ["Subsequent filing evidence"],
            },
        )
    )
    calls: list[dict[str, Any]] = []

    def fake_chat_completion(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {
            "status": "ok",
            "call_id": f"segmented-failure-{len(calls)}",
            "provider": "deepseek",
            "model": "deepseek-v4-pro",
            "content": json.dumps(next(values)),
            "tool_calls": [],
            "finish_reason": "stop",
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
            "latency_ms": 10,
            "transport_attempt_count": 1,
            "raw_response": {"usage": {"prompt_cache_miss_tokens": 100}},
        }

    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-secret-never-persist")
    monkeypatch.setattr(gateway, "chat_completion", fake_chat_completion)
    with pytest.raises(BoundedAgentExecutionError) as caught:
        build_bounded_agent_executor_for_admission(
            _segmented_v4_admission()
        ).execute(
            _input_pack(),
            _segmented_v4_admission(),
            run_identity={
                "case_id": "case-segmented-failure",
                "work_unit_id": "wu-segmented-failure",
                "attempt_id": "attempt-segmented-failure",
                "research_run_id": "run-segmented-failure",
            },
        )
    assert caught.value.stage == (
        "bounded_lead_adjudication:contract_validation_failed"
    )
    assert caught.value.failure_observation["failure_codes"] == [
        "bounded_agent_lead_segment_evidence_ref_invalid"
    ]
    assert caught.value.failure_observation["observed_counts"]["model_calls"] == 2
    assert len(calls) == 2
    assert "test-secret-never-persist" not in json.dumps(
        caught.value.failure_observation
    )


def test_t03_schema_failure_preserves_safe_one_call_observation(monkeypatch) -> None:
    import sec_agent.llm_gateway as gateway

    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-secret-never-persist")
    monkeypatch.setattr(
        gateway,
        "chat_completion",
        lambda **_: {
            "status": "ok",
            "call_id": "call-invalid-schema",
            "provider": "deepseek",
            "model": "deepseek-v4-pro",
            "content": "",
            "tool_calls": [
                {
                    "id": "strict-output-invalid-candidate",
                    "type": "function",
                    "function": {
                        "name": BOUNDED_SPECIALIST_LEAD_STRICT_TOOL_NAME,
                        "arguments": json.dumps({"result": {
                    "output_contract_ref": BOUNDED_SPECIALIST_LEAD_OUTPUT_CONTRACT_V4,
                    "specialist_judgment": {
                        "thesis": "Bounded thesis",
                        "confidence": "medium",
                        "evidence_findings": [
                            {
                                "candidate_id": "candidate-not-supplied",
                                "supported_claim": "Unsupported reference",
                                "boundary": "Must fail closed",
                            }
                        ],
                        "counter_thesis": "Counter",
                        "unresolved_gaps": [],
                    },
                    "lead_adjudication": {
                        "decision": "accept",
                        "adjudicated_judgment": "Judgment",
                        "confidence": "medium",
                        "evidence_refs": ["candidate-not-supplied"],
                        "remaining_gaps": [],
                        "what_would_change": [],
                    },
                        }}),
                    },
                }
            ],
            "finish_reason": "tool_calls",
            "input_tokens": 100,
            "output_tokens": 10,
            "total_tokens": 110,
            "latency_ms": 10,
            "transport_attempt_count": 1,
            "raw_response": {
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 10,
                    "prompt_cache_miss_tokens": 100,
                }
            },
        },
    )
    try:
        DeepSeekBoundedAgentExecutor().execute(
            _input_pack(),
            _v4_admission(),
            run_identity={
                "case_id": "case_87682fa72e72d7d042dabba0",
                "work_unit_id": "wu-1",
                "attempt_id": "attempt-1",
                "research_run_id": "run-1",
            },
        )
    except BoundedAgentExecutionError as exc:
        assert exc.stage == "bounded_specialist_and_lead:contract_validation_failed"
        assert exc.failure_observation["failure_codes"] == [
            "bounded_agent_evidence_ref_not_in_input"
        ]
        assert exc.failure_observation["output_shape"] == {
            "outer_key_count": 1,
            "expected_outer_keys_present": ["result"],
            "missing_outer_keys": [],
            "unexpected_outer_key_count": 0,
            "unexpected_outer_keys_digest": None,
            "recognized_wrapper_keys_present": ["result"],
            "expected_outer_value_types": {"result": "dict"},
            "result_key_count": 3,
            "expected_result_keys_present": [
                "lead_adjudication",
                "output_contract_ref",
                "specialist_judgment",
            ],
            "missing_result_keys": [],
            "unexpected_result_key_count": 0,
            "unexpected_result_keys_digest": None,
            "expected_result_value_types": {
                "lead_adjudication": "dict",
                "output_contract_ref": "str",
                "specialist_judgment": "dict",
            },
        }
        assert exc.failure_observation["observed_counts"]["model_calls"] == 1
        assert len(exc.failure_observation["usage_receipts"]) == 1
        assert "test-secret-never-persist" not in json.dumps(exc.failure_observation)
    else:
        raise AssertionError("schema failure must be terminal")


def test_t03_lossless_normalizer_does_not_repair_semantic_synonyms() -> None:
    normalized, adaptations = DeepSeekBoundedAgentExecutor._normalize_specialist_stage_output(
        {"result": {
            "output_contract_ref": BOUNDED_SPECIALIST_LEAD_OUTPUT_CONTRACT_V4,
            "specialist_judgment": {
                "thesis": "Bounded thesis",
                "confidence": "medium",
                "evidence_findings": {
                    "candidate_id": "candidate-1",
                    "supported_claim": "Supported",
                    "boundary": "Bounded",
                },
                "counter_thesis": "Counter",
                "unresolved_gaps": [],
            },
            "lead_adjudication": {
                "decision": "accepted",
                "adjudicated_judgment": "Judgment",
                "confidence": "medium",
                "evidence_refs": ["candidate-1"],
                "remaining_gaps": [],
                "what_would_change": [],
            },
        }}
    )
    assert "wrapped_single_evidence_finding" in adaptations
    assert normalized["result"]["lead_adjudication"]["decision"] == "accepted"
    with pytest.raises(ValueError, match="bounded_agent_lead_adjudication_invalid"):
        DeepSeekBoundedAgentExecutor._validate_specialist(
            normalized,
            _input_pack(),
            output_contract_ref=BOUNDED_SPECIALIST_LEAD_OUTPUT_CONTRACT_V4,
        )


def test_t03_v4_closed_envelope_does_not_flatten_contract_ref_plus_result() -> None:
    normalized, adaptations = DeepSeekBoundedAgentExecutor._normalize_specialist_stage_output(
        {
            "output_contract_ref": BOUNDED_SPECIALIST_LEAD_OUTPUT_CONTRACT_V4,
            "result": {
                "output_contract_ref": BOUNDED_SPECIALIST_LEAD_OUTPUT_CONTRACT_V4,
                "specialist_judgment": {
                    "thesis": "Bounded thesis",
                    "confidence": "medium",
                    "evidence_findings": [
                        {
                            "candidate_id": "candidate-1",
                            "supported_claim": "Supported",
                            "boundary": "Bounded",
                        }
                    ],
                    "counter_thesis": "Counter",
                    "unresolved_gaps": [],
                },
                "lead_adjudication": {
                    "decision": "accept",
                    "adjudicated_judgment": "Judgment",
                    "confidence": "medium",
                    "evidence_refs": ["candidate-1"],
                    "remaining_gaps": [],
                    "what_would_change": [],
                },
            },
        }
    )
    assert adaptations == ()
    with pytest.raises(
        ValueError, match="bounded_agent_specialist_envelope_keys_unexpected"
    ):
        DeepSeekBoundedAgentExecutor._validate_specialist(
            normalized,
            _input_pack(),
            output_contract_ref=BOUNDED_SPECIALIST_LEAD_OUTPUT_CONTRACT_V4,
        )


def test_t03_v4_rejects_v3_style_three_required_plus_five_outer_keys() -> None:
    v3_style = {
        **_valid_v4_result(),
        "task": "must not become response data",
        "decision_question": "must not become response data",
        "as_of": "must not become response data",
        "contract_rules": {"must_not": "persist"},
        "candidates": [{"must_not": "persist"}],
    }
    normalized, adaptations = DeepSeekBoundedAgentExecutor._normalize_specialist_stage_output(
        v3_style
    )
    assert normalized == v3_style
    assert adaptations == ()
    with pytest.raises(ValueError, match="bounded_agent_specialist_envelope_keys_missing"):
        DeepSeekBoundedAgentExecutor._validate_specialist(
            normalized,
            _input_pack(),
            output_contract_ref=BOUNDED_SPECIALIST_LEAD_OUTPUT_CONTRACT_V4,
        )
    shape = DeepSeekBoundedAgentExecutor._specialist_output_shape(normalized)
    assert shape["outer_key_count"] == 8
    assert shape["expected_outer_keys_present"] == []
    assert shape["missing_outer_keys"] == ["result"]
    assert shape["unexpected_outer_key_count"] == 8
    assert shape["unexpected_outer_keys_digest"]
    assert shape["result_key_count"] == 0


def test_t03_v4_rejects_unknown_result_extension_without_dropping_it() -> None:
    envelope = {
        "result": {
            **_valid_v4_result(),
            "provider_extension": {"must_not": "persist"},
        }
    }
    normalized, adaptations = DeepSeekBoundedAgentExecutor._normalize_specialist_stage_output(
        envelope
    )
    assert adaptations == ()
    assert "provider_extension" in normalized["result"]
    with pytest.raises(ValueError, match="bounded_agent_specialist_result_keys_unexpected"):
        DeepSeekBoundedAgentExecutor._validate_specialist(
            normalized,
            _input_pack(),
            output_contract_ref=BOUNDED_SPECIALIST_LEAD_OUTPUT_CONTRACT_V4,
        )
    shape = DeepSeekBoundedAgentExecutor._specialist_output_shape(normalized)
    serialized = json.dumps(shape)
    assert shape["unexpected_result_key_count"] == 1
    assert shape["unexpected_result_keys_digest"]
    assert "provider_extension" not in serialized
    assert "must_not" not in serialized


def test_t03_output_shape_telemetry_contains_no_unknown_key_or_value() -> None:
    value = {
        "result": {
            "output_contract_ref": BOUNDED_SPECIALIST_LEAD_OUTPUT_CONTRACT_V4,
            "secret-provider-prose": "must never persist",
        },
        "unknown-secret-shaped-key": "must never persist",
    }
    shape = DeepSeekBoundedAgentExecutor._specialist_output_shape(value)
    serialized = json.dumps(shape)
    assert shape["outer_key_count"] == 2
    assert shape["expected_outer_keys_present"] == ["result"]
    assert shape["missing_outer_keys"] == []
    assert shape["recognized_wrapper_keys_present"] == ["result"]
    assert shape["unexpected_outer_key_count"] == 1
    assert shape["result_key_count"] == 2
    assert shape["expected_result_keys_present"] == ["output_contract_ref"]
    assert shape["missing_result_keys"] == [
        "lead_adjudication",
        "specialist_judgment",
    ]
    assert shape["unexpected_result_key_count"] == 1
    assert shape["unexpected_outer_keys_digest"]
    assert shape["unexpected_result_keys_digest"]
    assert "unknown-secret-shaped-key" not in serialized
    assert "secret-provider-prose" not in serialized
    assert "must never persist" not in serialized


@pytest.mark.parametrize(
    ("arguments", "failure_code"),
    [
        (
            "{invalid-secret-provider-argument",
            "bounded_agent_strict_tool_arguments_json_decode_failed",
        ),
        (
            '```json\n{"secret-fenced-provider-value": {}}\n```',
            "bounded_agent_strict_tool_arguments_json_decode_failed",
        ),
        (
            (
                '{"secret-duplicate-provider-key": {}, '
                '"secret-duplicate-provider-key": {}}'
            ),
            "bounded_agent_strict_tool_duplicate_key",
        ),
        (
            '["secret-non-object-provider-value"]',
            "bounded_agent_strict_tool_arguments_not_object",
        ),
    ],
)
def test_t03_strict_tool_parser_exposes_only_exact_parse_subtype(
    arguments: str,
    failure_code: str,
) -> None:
    with pytest.raises(ValueError, match=failure_code):
        DeepSeekBoundedAgentExecutor._parse_strict_tool_arguments(arguments)


def test_t03_strict_tool_failure_telemetry_rejects_non_allowlisted_subtype() -> None:
    error = BoundedAgentExecutionError(
        "bounded_specialist_and_lead:strict_tool_arguments_invalid_json",
        usage_receipts=[],
        estimated_cost_usd=0.0,
        failure_codes=("bounded_agent_strict_tool_arguments_invalid_json",),
        strict_tool_parse_subtype="secret-unclassified-provider-detail",
    )

    serialized = json.dumps(error.failure_observation)
    assert "failure_telemetry" not in error.failure_observation
    assert "secret-unclassified-provider-detail" not in serialized


@pytest.mark.parametrize(
    ("content", "finish_reason", "tool_calls", "failure_code"),
    [
        ("", "stop", [], "bounded_agent_strict_tool_finish_reason_invalid"),
        ("", "length", [], "bounded_agent_provider_output_truncated"),
        (
            "",
            "tool_calls",
            [_strict_tool_call("{invalid-secret-provider-argument")],
            "bounded_agent_strict_tool_arguments_invalid_json",
        ),
        (
            "",
            "tool_calls",
            [
                _strict_tool_call(
                    '```json\n{"secret-fenced-provider-value": {}}\n```'
                )
            ],
            "bounded_agent_strict_tool_arguments_invalid_json",
        ),
        (
            "",
            "tool_calls",
            [
                _strict_tool_call(
                    '{"secret-duplicate-provider-key": {}, '
                    '"secret-duplicate-provider-key": {}}'
                )
            ],
            "bounded_agent_strict_tool_arguments_invalid_json",
        ),
        (
            "",
            "tool_calls",
            [_strict_tool_call('["secret-non-object-provider-value"]')],
            "bounded_agent_strict_tool_arguments_invalid_json",
        ),
        (
            "secret-provider-prose",
            "tool_calls",
            [_strict_tool_call(json.dumps({"result": _valid_v4_result()}))],
            "bounded_agent_strict_tool_unexpected_content",
        ),
        (
            "",
            "tool_calls",
            [],
            "bounded_agent_strict_tool_call_cardinality_invalid",
        ),
        (
            "",
            "tool_calls",
            [
                _strict_tool_call(json.dumps({"result": _valid_v4_result()})),
                _strict_tool_call(json.dumps({"result": _valid_v4_result()})),
            ],
            "bounded_agent_strict_tool_call_cardinality_invalid",
        ),
        (
            "",
            "tool_calls",
            [_strict_tool_call("{}", name="unexpected_tool")],
            "bounded_agent_strict_tool_name_invalid",
        ),
        (
            "",
            "tool_calls",
            [{"id": "invalid", "type": "not_function", "function": {}}],
            "bounded_agent_strict_tool_call_schema_invalid",
        ),
        (
            "",
            "tool_calls",
            [_strict_tool_call("")],
            "bounded_agent_strict_tool_arguments_empty",
        ),
    ],
)
def test_t03_strict_tool_transport_failure_is_typed_and_secret_safe(
    monkeypatch,
    content: str,
    finish_reason: str,
    tool_calls: list[dict[str, Any]],
    failure_code: str,
) -> None:
    import sec_agent.llm_gateway as gateway

    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-secret-never-persist")
    monkeypatch.setattr(
        gateway,
        "chat_completion",
        lambda **_: {
            "status": "ok",
            "call_id": "call-terminal-shape",
            "provider": "deepseek",
            "model": "deepseek-v4-pro",
            "content": content,
            "tool_calls": tool_calls,
            "finish_reason": finish_reason,
            "input_tokens": 100,
            "output_tokens": 10,
            "total_tokens": 110,
            "latency_ms": 10,
            "transport_attempt_count": 1,
            "raw_response": {"usage": {"prompt_cache_miss_tokens": 100}},
        },
    )
    with pytest.raises(BoundedAgentExecutionError) as caught:
        DeepSeekBoundedAgentExecutor().execute(
            _input_pack(),
            _v4_admission(),
            run_identity={
                "case_id": "case_87682fa72e72d7d042dabba0",
                "work_unit_id": "wu-1",
                "attempt_id": "attempt-1",
                "research_run_id": "run-1",
            },
        )
    assert caught.value.failure_observation["failure_codes"] == [failure_code]
    assert caught.value.failure_observation["observed_counts"]["model_calls"] == 1
    serialized = json.dumps(caught.value.failure_observation)
    arguments = (
        tool_calls[0].get("function", {}).get("arguments")
        if len(tool_calls) == 1 and isinstance(tool_calls[0], dict)
        else None
    )
    expected_parse_subtypes = {
        "{invalid-secret-provider-argument": "json_decode_error",
        '```json\n{"secret-fenced-provider-value": {}}\n```': "json_decode_error",
        (
            '{"secret-duplicate-provider-key": {}, '
            '"secret-duplicate-provider-key": {}}'
        ): "duplicate_key",
        '["secret-non-object-provider-value"]': "non_object",
    }
    if arguments in expected_parse_subtypes:
        assert caught.value.failure_observation["failure_telemetry"] == {
            "strict_tool_arguments": {
                "parser_contract": "native_json_object_no_fence_no_duplicate_keys",
                "parse_subtype": expected_parse_subtypes[arguments],
                "raw_arguments_persisted": False,
                "argument_digest_persisted": False,
                "argument_length_persisted": False,
            }
        }
    else:
        assert "failure_telemetry" not in caught.value.failure_observation
    assert "secret-provider-prose" not in serialized
    assert "unexpected_tool" not in serialized
    for secret_fragment in (
        "invalid-secret-provider-argument",
        "secret-fenced-provider-value",
        "secret-duplicate-provider-key",
        "secret-non-object-provider-value",
    ):
        assert secret_fragment not in serialized


def _native_openai_admission() -> BoundedAgentAdmission:
    return _v4_admission().model_copy(
        update={
            "provider": "openai",
            "model": "fixture-structured-model",
            "model_ref": "openai:fixture-structured-model",
            "api_key_env": "OPENAI_API_KEY",
            "base_url": BOUNDED_OPENAI_BASE_URL,
            "specialist_transport_ref": (
                BOUNDED_SPECIALIST_LEAD_NATIVE_JSON_SCHEMA_TRANSPORT_REF
            ),
            "reasoning_effort": "medium",
        }
    )


def _native_completed_response(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "ok",
        "call_id": "native-response-1",
        "provider": "openai",
        "model": "fixture-structured-model",
        "response_status": "completed",
        "response_output": [
            {"type": "reasoning", "summary": []},
            {
                "type": "message",
                "content": [
                    {"type": "output_text", "text": json.dumps(value)}
                ],
            },
        ],
        "finish_reason": "completed",
        "input_tokens": 100,
        "output_tokens": 50,
        "total_tokens": 150,
        "latency_ms": 10,
        "transport_attempt_count": 1,
        "raw_response": {
            "usage": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}
        },
    }


def test_t03_native_json_schema_format_reuses_closed_v4_schema_without_tools() -> None:
    text = NativeJsonSchemaResponseAdapter.text_format(
        _input_pack(),
        output_contract_ref=BOUNDED_SPECIALIST_LEAD_OUTPUT_CONTRACT_V4,
    )
    format_value = text["format"]
    assert format_value["type"] == "json_schema"
    assert format_value["name"] == BOUNDED_SPECIALIST_LEAD_NATIVE_JSON_SCHEMA_NAME
    assert format_value["strict"] is True
    assert set(text) == {"format"}

    def visit(schema: dict[str, Any]) -> None:
        if schema.get("type") == "object":
            properties = schema["properties"]
            assert schema["required"] == list(properties)
            assert schema["additionalProperties"] is False
            for child in properties.values():
                visit(child)
        elif schema.get("type") == "array":
            visit(schema["items"])

    schema = format_value["schema"]
    visit(schema)
    candidate_enum = schema["properties"]["result"]["properties"][
        "specialist_judgment"
    ]["properties"]["evidence_findings"]["items"]["properties"]["candidate_id"][
        "enum"
    ]
    assert candidate_enum == ["candidate-1"]


@pytest.mark.parametrize(
    ("result", "failure_code"),
    [
        (
            {
                "response_status": "incomplete",
                "incomplete_reason": "max_output_tokens",
            },
            "bounded_agent_native_json_schema_response_incomplete_max_output_tokens",
        ),
        (
            {
                "response_status": "incomplete",
                "incomplete_reason": "content_filter",
            },
            "bounded_agent_native_json_schema_response_incomplete_content_filter",
        ),
        (
            {
                "response_status": "completed",
                "response_output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "refusal",
                                "refusal": "secret-provider-refusal-text",
                            }
                        ],
                    }
                ],
            },
            "bounded_agent_native_json_schema_response_refusal",
        ),
        (
            {"response_status": "completed", "response_output": []},
            "bounded_agent_native_json_schema_message_cardinality_invalid",
        ),
        (
            {
                "response_status": "completed",
                "response_output": [
                    {"type": "message", "content": []},
                    {"type": "message", "content": []},
                ],
            },
            "bounded_agent_native_json_schema_message_cardinality_invalid",
        ),
        (
            {
                "response_status": "completed",
                "response_output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": '{"secret-duplicate":1,"secret-duplicate":2}',
                            }
                        ],
                    }
                ],
            },
            "bounded_agent_native_json_schema_duplicate_key",
        ),
        (
            {
                "response_status": "completed",
                "response_output": [
                    {
                        "type": "message",
                        "content": [
                            {"type": "output_text", "text": "```json secret fenced```"}
                        ],
                    }
                ],
            },
            "bounded_agent_native_json_schema_json_decode_failed",
        ),
        (
            {
                "response_status": "completed",
                "response_output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "[]"}],
                    }
                ],
            },
            "bounded_agent_native_json_schema_output_not_object",
        ),
    ],
)
def test_t03_native_json_schema_terminal_shapes_are_typed_and_text_free(
    result: dict[str, Any], failure_code: str
) -> None:
    with pytest.raises(NativeJsonSchemaResponseError) as caught:
        NativeJsonSchemaResponseAdapter.parse_response(result)
    assert str(caught.value) == failure_code
    assert "secret" not in str(caught.value)


def test_t03_native_json_schema_binding_is_fail_closed_before_provider_call(
    monkeypatch,
) -> None:
    import sec_agent.llm_gateway as gateway

    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        gateway, "responses_completion", lambda **kwargs: calls.append(kwargs)
    )
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret-never-persist")
    admission = _native_openai_admission().model_copy(
        update={"base_url": "https://example.invalid/v1"}
    )
    with pytest.raises(
        ValueError,
        match="bounded_native_json_schema_openai_provider_binding_required",
    ):
        DeepSeekBoundedAgentExecutor(
            native_json_schema_adapter=NativeJsonSchemaResponseAdapter()
        ).execute(
            _input_pack(),
            admission,
            run_identity={
                "case_id": "case_87682fa72e72d7d042dabba0",
                "work_unit_id": "wu-native-binding-fixture",
                "attempt_id": "attempt-native-binding-fixture",
                "research_run_id": "run-native-binding-fixture",
            },
        )
    assert calls == []

    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "1")
    with pytest.raises(
        ValueError,
        match="llm_gateway_transport_retries_must_equal_zero",
    ):
        DeepSeekBoundedAgentExecutor(
            native_json_schema_adapter=NativeJsonSchemaResponseAdapter()
        ).execute(
            _input_pack(),
            _native_openai_admission(),
            run_identity={
                "case_id": "case_87682fa72e72d7d042dabba0",
                "work_unit_id": "wu-native-retry-fixture",
                "attempt_id": "attempt-native-retry-fixture",
                "research_run_id": "run-native-retry-fixture",
            },
        )
    assert calls == []


@pytest.mark.parametrize(
    ("response", "failure_code"),
    [
        (
            {
                **_native_completed_response({"result": _valid_v4_result()}),
                "response_output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "refusal",
                                "refusal": "secret-provider-refusal-text",
                            }
                        ],
                    }
                ],
            },
            "bounded_agent_native_json_schema_response_refusal",
        ),
        (
            _native_completed_response(
                {
                    "result": {
                        **_valid_v4_result(),
                        "specialist_judgment": {
                            **_valid_v4_result()["specialist_judgment"],
                            "evidence_findings": [
                                {
                                    "candidate_id": "secret-unknown-candidate",
                                    "supported_claim": "Unsupported fixture",
                                    "boundary": "Fixture boundary",
                                }
                            ],
                        },
                    }
                }
            ),
            "bounded_agent_evidence_ref_not_in_input",
        ),
    ],
)
def test_t03_native_json_schema_failures_reach_canonical_typed_closeout_without_raw_text(
    monkeypatch,
    response: dict[str, Any],
    failure_code: str,
) -> None:
    import sec_agent.llm_gateway as gateway

    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret-never-persist")
    monkeypatch.setattr(gateway, "responses_completion", lambda **_: response)
    monkeypatch.setattr(
        gateway,
        "chat_completion",
        lambda **_: pytest.fail("writer/verifier must not run after specialist failure"),
    )
    with pytest.raises(BoundedAgentExecutionError) as caught:
        DeepSeekBoundedAgentExecutor(
            native_json_schema_adapter=NativeJsonSchemaResponseAdapter()
        ).execute(
            _input_pack(),
            _native_openai_admission(),
            run_identity={
                "case_id": "case_87682fa72e72d7d042dabba0",
                "work_unit_id": "wu-native-failure-fixture",
                "attempt_id": "attempt-native-failure-fixture",
                "research_run_id": "run-native-failure-fixture",
            },
        )
    observation = caught.value.failure_observation
    assert observation["failure_codes"] == [failure_code]
    assert observation["observed_counts"]["model_calls"] == 1
    serialized = json.dumps(observation)
    assert "secret-provider-refusal-text" not in serialized
    assert "secret-unknown-candidate" not in serialized


def test_t03_native_json_schema_adapter_executes_fixture_path_without_tool_call(
    monkeypatch,
) -> None:
    import sec_agent.llm_gateway as gateway

    writer = {
        "title_zh_cn": "NVDA 需求真实性与持续性",
        "executive_summary_zh_cn": "需求转化获得支持，但持续性仍待验证。",
        "sections": [
            {
                "heading_zh_cn": "判断",
                "content_zh_cn": "当前证据支持转化，不足以证明持续性。",
                "evidence_refs": ["candidate-1"],
            }
        ],
        "limitations_zh_cn": ["缺少跨期持续性证据"],
    }
    verifier = {
        "semantic_fidelity": {"status": "pass", "score": 90, "issues": []},
        "financial_coherence": {"status": "pass", "score": 88, "issues": []},
        "recommendation": "accept_for_internal_review",
        "material_gain_assessment": "Conditionality is explicit.",
    }
    chat_values = iter((writer, verifier))
    response_calls: list[dict[str, Any]] = []
    chat_calls: list[dict[str, Any]] = []

    def fake_responses_completion(**kwargs: Any) -> dict[str, Any]:
        response_calls.append(kwargs)
        return _native_completed_response({"result": _valid_v4_result()})

    def fake_chat_completion(**kwargs: Any) -> dict[str, Any]:
        chat_calls.append(kwargs)
        value = next(chat_values)
        return {
            "status": "ok",
            "call_id": f"chat-{len(chat_calls)}",
            "provider": "openai",
            "model": "fixture-structured-model",
            "content": json.dumps(value),
            "tool_calls": [],
            "finish_reason": "stop",
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
            "latency_ms": 10,
            "transport_attempt_count": 1,
            "raw_response": {"usage": {"prompt_cache_miss_tokens": 100}},
        }

    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret-never-persist")
    monkeypatch.setattr(gateway, "responses_completion", fake_responses_completion)
    monkeypatch.setattr(gateway, "chat_completion", fake_chat_completion)

    output = DeepSeekBoundedAgentExecutor(
        native_json_schema_adapter=NativeJsonSchemaResponseAdapter()
    ).execute(
        _input_pack(),
        _native_openai_admission(),
        run_identity={
            "case_id": "case_87682fa72e72d7d042dabba0",
            "work_unit_id": "wu-native-fixture",
            "attempt_id": "attempt-native-fixture",
            "research_run_id": "run-native-fixture",
        },
    )

    assert len(response_calls) == 1
    assert len(chat_calls) == 2
    native_call = response_calls[0]
    assert native_call["base_url"] == BOUNDED_OPENAI_BASE_URL
    assert native_call["responses_path"] == "/responses"
    assert native_call["api_key_env"] == "OPENAI_API_KEY"
    assert native_call["text"]["format"]["type"] == "json_schema"
    assert native_call["text"]["format"]["strict"] is True
    assert native_call["reasoning"] == {"effort": "medium"}
    assert "tools" not in native_call
    assert "tool_choice" not in native_call
    assert (
        BOUNDED_SPECIALIST_LEAD_STRICT_TOOL_NAME
        not in native_call["input"][0]["content"]
    )
    assert all(call["enable_thinking"] is True for call in chat_calls)
    assert all(call["reasoning_effort"] == "medium" for call in chat_calls)

    manifest = next(
        row.payload
        for row in output.artifacts
        if row.artifact_type == BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE
    )
    assert manifest["observed_counts"]["model_calls"] == 3
    assert (
        manifest["specialist_output_transport_ref"]
        == BOUNDED_SPECIALIST_LEAD_NATIVE_JSON_SCHEMA_TRANSPORT_REF
    )
    assert manifest["reasoning_effort"] == "medium"
    assert manifest["specialist_output_tool_name"] is None
    verification = next(
        row.payload
        for row in output.artifacts
        if row.artifact_type == "bounded_agent_verification"
    )
    assert verification["deterministic_integrity"]["specialist_output_tool_calls"] == 0
    serialized = output.model_dump_json()
    assert "test-secret-never-persist" not in serialized
