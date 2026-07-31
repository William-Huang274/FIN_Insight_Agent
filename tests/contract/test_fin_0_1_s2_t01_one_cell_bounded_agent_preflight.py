from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PREFLIGHT = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s2_t01_one_cell_bounded_agent_preflight_v1_0.json"
)
BACKLOG = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_program_release_backlog_v2_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_t01_is_one_cell_design_only_and_actual_execution_is_fail_closed() -> None:
    contract = _load(PREFLIGHT)
    assert contract["status"] == "accepted_design_preflight_actual_execution_not_admitted"
    assert contract["authority"]["actual_execution_admitted"] is False
    assert contract["case_and_cell_scope"] == {
        "company": "NVDA",
        "cell_id": "demand_authenticity_and_sustainability",
        "cell_alias_mapping": {
            "program_cell_id": "demand_authenticity_and_sustainability",
            "layer_4_semantic_role": "demand_signal",
        },
        "maximum_cell_count": 1,
        "execution_case_id": None,
        "execution_case_version": None,
        "decision_surface_version_ref": None,
        "as_of": None,
        "input_digest": None,
        "binding_status": "blocked_until_exact_evaluation_case_version_and_input_digest_are_frozen",
        "live_business_case_head_mutation_allowed": False,
    }
    assert contract["t01_observed_counts"] == {
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "external_tool_calls": 0,
        "evidence_promotions": 0,
        "real_business_case_mutations": 0,
        "human_reviews": 0,
        "release_admissions": 0,
    }


def test_profile_preserves_one_runtime_and_does_not_select_stale_provider_contract() -> None:
    contract = _load(PREFLIGHT)
    profile = contract["profile_contract"]
    admission = contract["provider_model_budget_admission"]
    assert profile["product_profile_id"] == "bounded_agent_internal"
    assert profile["future_execution_profile_version_ref"] is None
    assert profile["single_runtime"].endswith("research_runtime.py::Fin01ResearchRuntime")
    assert profile["parallel_runtime_or_standalone_runner_allowed"] is False
    assert profile["silent_deterministic_substitution_allowed"] is False
    assert admission["provider"] is None
    assert admission["model"] is None
    assert admission["max_semantic_model_calls"] is None
    assert admission["max_total_cost_usd"] is None
    assert admission["max_transport_attempts_per_call"] == 1
    assert admission["automatic_retry_allowed"] is False
    assert (
        admission["prior_three_cell_deepseek_freeze"]["disposition"]
        == "historical_noncanonical_scope_mismatch_not_selected_not_revalidated_not_authorized"
    )
    cardinality = contract["execution_cardinality"]
    assert cardinality["scope"] == "per_exact_execution_admission"
    assert cardinality["maximum_work_units_per_execution_admission"] == 1
    assert cardinality["maximum_attempts_per_work_unit"] == 1
    assert cardinality["retry_budget"] == 0


def test_evidence_writer_verifier_and_comparison_boundaries_are_exact() -> None:
    contract = _load(PREFLIGHT)
    assert contract["data_and_tool_boundary"]["candidate_is_evidence"] is False
    assert contract["data_and_tool_boundary"]["graph_edge_is_evidence"] is False
    assert contract["data_and_tool_boundary"]["writer_source_or_tool_calls"] == 0
    assert contract["promotion_and_write_boundary"]["live_case_head_writes"] == 0
    assert contract["promotion_and_write_boundary"]["adapter_direct_canonical_writes"] == 0
    assert contract["writer_and_verifier"]["verifier_layers"] == [
        "deterministic_integrity",
        "semantic_fidelity",
        "financial_coherence",
        "visual_delivery",
    ]
    comparison = contract["comparison_contract"]
    assert comparison["runs_must_be_distinct"] is True
    assert comparison["historical_mismatched_run_is_valid_baseline"] is False
    assert len(comparison["required_parity"]) == 6
    assert len(contract["hard_failure_floor"]) == 6
    assert (
        "release_contract_v1_3_still_admits_S1_fixture_only_and_must_be_superseded_before_execution"
        in contract["execution_admission_blockers"]
    )
    assert (
        "API_and_ExecutionService_do_not_admit_bounded_agent_internal_entry"
        in contract["execution_admission_blockers"]
    )


def test_backlog_preserves_t01_freeze_and_records_later_terminal_run_truth() -> None:
    backlog = _load(BACKLOG)
    s2 = next(row for row in backlog["slices"] if row["slice_id"] == "S2")
    tasks = {row["item_id"]: row for row in s2["items"]}
    assert backlog["active_slice"] == "S4"
    assert tasks["S2-T01"]["status"] == "accepted_after_independent_review"
    assert tasks["S2-T02"]["status"] == "accepted_after_independent_review"
    assert (
        tasks["S2-T03"]["status"]
        == "pass_deepseek_segmented_v4_terminal_succeeded_internal_review"
    )
    assert s2["actual_execution_started"] is True
    assert s2["model_provider_network_calls"] == 4
    assert s2["actual_run_cardinality"] == {
        "work_units": 1,
        "attempts": 1,
        "research_runs": 1,
        "artifacts": 9,
        "terminal_state": "succeeded",
        "fallback_performed": False,
        "rerun_performed": False,
    }
    assert backlog["next_action"]["item_id"].startswith("FIN-0.1-REPOSITORY-")
    assert backlog["next_action"]["status"].startswith(
        "repository_evidence_freeze_and_safe_classification_pass"
    )
    assert tasks["S2-T05"]["status"] == "pass_owner_accepted_bounded_material_gain"
    assert tasks["S2-T06"]["status"] == "pass_independent_S2_closeout"
    assert tasks["S2-T03"]["gpt_5_6_sol_native_live_validation_r2"][
        "provider_http_status"
    ] == 401
    assert tasks["S2-T03"]["deepseek_segmented_v4_adapter"] == {
        "status": "live_proven_terminal_succeeded",
        "implementation_ref": "configs/releases/fin_ia_0_1_s2_t03_deepseek_segmented_v4_implementation_v1_0.json",
        "transport_ref": "fin01.bounded_agent.deepseek_segmented_json_object:v1",
        "canonical_output_contract_ref": "fin01.bounded_agent.specialist_lead_output:v4",
        "provider_segments": 2,
        "deterministic_exact_v4_assembly": True,
        "future_semantic_provider_network_call_cap": 4,
        "retry_budget": 0,
        "live_provider_calls": 4,
        "live_admission_issued": True,
        "T03": "pass",
    }
    issuance = tasks["S2-T03"]["deepseek_segmented_v4_exact_admission_issuance"]
    assert issuance["admission_consumed"] is True
    assert issuance["actual_execution_authorized"] is True
    assert issuance["maximum_semantic_provider_network_calls"] == 4
    assert issuance["maximum_output_tokens"] == 4200
    assert tasks["S2-T03"]["first_stage_repair"] == {
        "status": "v2_live_validation_terminal_failed_shape_telemetry_repaired",
        "output_contract_ref": "fin01.bounded_agent.specialist_lead_output:v3",
        "contract_ref": "configs/releases/fin_ia_0_1_s2_t03_specialist_lead_output_contract_repair_v3_0.json",
        "historical_v1_admission_reusable": False,
        "consumed_v2_admission_ref": "configs/releases/fin_ia_0_1_s2_t03_bounded_agent_exact_admission_v2_0.json",
        "consumed_v2_work_unit_idempotency_key": "fin01-s2-t03-bounded-agent-work-unit-v2-contract-r1",
        "new_exact_v3_admission_issued": True,
        "real_model_calls": 1,
        "network_calls": 1,
        "rerun_performed": False,
    }
    assert tasks["S2-T03"]["v2_live_validation_result"] == {
        "admission_consumed": True,
        "work_unit_id": "wu_p02_5_5ab54cb4e6cf262915768e6b",
        "attempt_id": "attempt_fin01_c058cc2c206c715aa933bd8b",
        "research_run_id": "research_run_fin01_9239b033666398bd8dece2a5",
        "state": "failed",
        "terminal_reason": "bounded_agent_profile_error:BoundedAgentExecutionError:bounded_specialist_and_lead:contract_validation_failed",
        "failure_code": "bounded_agent_specialist_outer_schema_invalid",
        "model_provider_network_calls": 1,
        "transport_attempts": 1,
        "estimated_cost_usd": 0.00175479,
        "artifact_count": 0,
        "fallback_performed": False,
        "automatic_rerun_performed": False,
    }
    assert tasks["S2-T03"]["v3_live_validation_result"]["admission_consumed"] is True
    assert tasks["S2-T03"]["v3_live_validation_result"]["failure_code"] == (
        "bounded_agent_specialist_outer_keys_unexpected"
    )
    assert tasks["S2-T03"]["v3_live_validation_result"]["missing_outer_keys"] == 0
    assert tasks["S2-T03"]["v3_live_validation_result"][
        "unexpected_outer_key_count"
    ] == 5
    assert tasks["S2-T03"]["v3_live_validation_result"]["artifact_count"] == 0
    assert tasks["S2-T03"]["deterministic_v4_repair"] == {
        "status": "fixture_proven_no_live_admission",
        "output_contract_ref": "fin01.bounded_agent.specialist_lead_output:v4",
        "contract_ref": "configs/releases/fin_ia_0_1_s2_t03_specialist_lead_output_contract_repair_v4_0.json",
        "request_response_namespace_separated": True,
        "response_outer_keys": ["result"],
            "unknown_outer_or_result_fields_silently_dropped": False,
            "non_vt1_work_unit_identity_includes_execution_identity": True,
            "shared_store_distinct_work_unit_attempt_run_identity_proven": True,
            "pending_dispatch_selects_exact_execution_identity": True,
            "focused_regression": "26 passed in 41.85s",
            "related_regression": "75 passed in 70.53s",
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "new_exact_v4_admission_issued": False,
        "live_validation_performed": False,
    }
    assert tasks["S2-T03"]["v4_live_validation_decision"] == {
        "status": "v4_admission_consumed_terminal_failed_strict_tool_arguments_invalid_json",
        "decision_ref": "configs/releases/fin_ia_0_1_s2_t03_v4_live_validation_decision_v1_0.json",
        "ordinary_json_object_v4_admission_issued": False,
        "new_exact_v4_admission_issued": True,
        "issued_at": "2026-07-20T15:05:25+08:00",
        "admission_ref": "configs/releases/fin_ia_0_1_s2_t03_bounded_agent_exact_admission_v4_0.json",
        "admission_id": "fin01-s2-t03-bounded-agent-v4-strict-tool-live-validation-r1",
        "work_unit_idempotency_key": "fin01-s2-t03-bounded-agent-work-unit-v4-strict-tool-r1",
        "runtime_root": ".codex_runtime/fin01-s2-t03-v4-strict-tool-live-validation-r1",
        "strict_tool_adapter_selected": True,
        "strict_tool_adapter_implemented": True,
        "strict_tool_adapter_fixture_proven": True,
        "transport_ref": "fin01.bounded_agent.deepseek_strict_tool_output:v1",
        "provider_beta_base_url": "https://api.deepseek.com/beta",
        "forced_tool_name": "submit_specialist_lead_result",
        "parallel_tool_calls_parameter_adopted": False,
        "tool_call_cardinality_enforced_locally": True,
        "native_json_arguments_only": True,
        "duplicate_and_fenced_json_rejected": True,
        "local_candidate_evidence_and_semantic_validation_retained": True,
        "external_tool_execution_allowed": False,
        "execution_enabled_by_admission": True,
        "execution_command_authorized_by_user": True,
        "execution_started": True,
        "execution_consumed": True,
        "zero_call_preflight_status": "pass_no_model_call",
        "admission_digest": "61e9e21033eb6ab31e7400067eb455b172d63e421ba42bdd5ca2b09a978639f6",
        "exact_input_match": True,
        "candidate_count": 3,
        "output_only_cost_ceiling_usd": 0.003045,
        "issuance_contract_regression": "38 passed in 1.82s",
        "actual_execution_authorized": True,
        "focused_regression": "32 passed in 1.67s",
        "related_regression": "91 passed in 84.85s",
        "model_calls": 1,
        "provider_calls": 1,
        "network_calls": 1,
        "live_validation_result": {
            "state": "failed",
            "work_unit_id": "wu_p02_5_620b5f91fc25d0f4f2a59149",
            "attempt_id": "attempt_fin01_c078251c5487cc4c1f952523",
            "research_run_id": "research_run_fin01_b9f50318d58998a5a5c0506f",
            "terminal_reason": "bounded_agent_profile_error:BoundedAgentExecutionError:bounded_specialist_and_lead:strict_tool_arguments_invalid_json",
            "failure_code": "bounded_agent_strict_tool_arguments_invalid_json",
            "provider_finish_reason": "tool_calls",
            "transport_attempts": 1,
            "input_tokens": 1936,
            "output_tokens": 1336,
            "total_tokens": 3272,
            "latency_ms": 28026,
            "estimated_cost_usd": 0.00200448,
            "artifact_count": 0,
            "source_network_calls": 0,
            "external_tool_executions": 0,
            "fallback_performed": False,
            "automatic_retry_or_rerun_performed": False,
            "raw_provider_response_persisted": False,
        },
        "post_run_focused_regression": "39 passed in 2.17s",
        "post_run_related_regression": "93 passed in 61.57s",
        "consumed_identity_guards_proven": True,
    }
    assert tasks["S2-T03"]["post_v4_failure_parse_subtype_telemetry_repair"] == {
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
        "historical_v4_parse_subtype_reconstructed": False,
        "parser_relaxed": False,
        "focused_T03_regression": "39 passed in 2.39s",
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "new_exact_admission_issued": False,
    }
    assert tasks["S2-T03"]["post_telemetry_provider_strategy_decision"] == {
        "status": "fresh_r2_exact_admission_consumed_canonical_terminalization_failed",
        "decision_ref": (
            "configs/releases/"
            "fin_ia_0_1_s2_t03_post_telemetry_provider_strategy_decision_v1_0.json"
        ),
        "retain_deepseek_beta_strict_named_function": True,
        "switch_back_to_json_object": False,
        "switch_provider_now": False,
        "relax_native_json_parser": False,
        "recommend_one_fresh_exact_r2_admission": True,
        "local_argument_transformation_gap_found": False,
        "forward_parse_subtype_telemetry_fixture_proven": True,
        "new_admission_issued": True,
        "issued_admission_ref": (
            "configs/releases/"
            "fin_ia_0_1_s2_t03_bounded_agent_exact_admission_v4_r2.json"
        ),
        "issued_admission_id": (
            "fin01-s2-t03-bounded-agent-v4-strict-tool-live-validation-r2"
        ),
        "issued_admission_digest": (
            "671ec47b1085e51bfb43a8af46b8b89918498441ce6d92a3bdbbcd2b62ea0adf"
        ),
        "work_unit_idempotency_key": (
            "fin01-s2-t03-bounded-agent-work-unit-v4-strict-tool-r2"
        ),
        "runtime_root": (
            ".codex_runtime/fin01-s2-t03-v4-strict-tool-live-validation-r2"
        ),
        "zero_call_preflight_status": "pass_no_model_call",
        "execution_started": True,
        "execution_consumed": True,
        "actual_execution_authorized": True,
        "model_calls": 1,
        "provider_calls": 1,
        "network_calls": 1,
        "r2_live_validation_result": {
            "work_unit_id": "wu_p02_5_a5a256b148228113b4583b3a",
            "attempt_id": "attempt_fin01_9537a9c63622cf56604af914",
            "research_run_id": "research_run_fin01_81e6277f9df729f23ab20140",
            "canonical_state": "failed",
            "terminal_reason": (
                "bounded_agent_profile_error:BoundedAgentExecutionInterrupted:"
                "canonical_terminalization_gap_after_specialist_provider_call"
            ),
            "artifact_count": 0,
            "provider_finish_reason": "tool_calls",
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
            "failure_observation_persisted": True,
            "canonical_terminalization_failure": (
                "research_run_failure_observation_not_secret_safe"
            ),
            "earliest_owned_root_cause": (
                "canonical_failure_observation_allowlist_missing_failure_telemetry"
            ),
            "strict_arguments_parse_failure": (
                "inferred_from_unique_runtime_path_not_durably_persisted"
            ),
            "strict_arguments_parse_subtype": "not_reconstructable",
            "typed_closeout_failure_code": (
                "bounded_agent_canonical_terminalization_interrupted"
            ),
            "gateway_event_count_before_closeout": 2,
            "gateway_event_count_after_closeout": 2,
            "closeout_additional_model_provider_network_calls": [0, 0, 0],
        },
    }
    assert tasks["S2-T03"]["r2_orphaned_run_root_cause_repair"] == {
        "status": "closed_zero_call_fixture_and_exact_runtime_proven",
        "canonical_failure_telemetry_closed_allowlist": True,
        "arbitrary_failure_telemetry_content_rejected": True,
        "background_dispatch_errors_propagated": True,
        "runner_requires_terminal_state": True,
        "copy_dry_run_passed": True,
        "idempotent_replay_returns_already_closed": True,
        "work_unit_attempt_research_run_states": ["failed", "failed", "failed"],
        "artifact_count": 0,
        "gateway_events_before_after": [2, 2],
        "additional_model_provider_network_calls": [0, 0, 0],
        "parse_subtype_reconstructed": False,
        "focused_T02_T03_regression": "51 passed in 53.54s",
        "focused_S2_T01_T03_regression": "56 passed in 54.10s",
    }
    transport_pivot = tasks["S2-T03"][
        "post_r2_provider_transport_pivot_decision"
    ]
    assert transport_pivot == {
        "status": "native_json_schema_response_transport_selected_adapter_not_implemented",
        "decision_ref": "configs/releases/fin_ia_0_1_s2_t03_post_r2_provider_transport_pivot_decision_v1_0.json",
        "selected_internal_transport_family": "provider_native_json_schema_response",
        "selected_output_semantics": "structured_assistant_response_not_tool_invocation",
        "first_provider_candidate": "openai",
        "first_provider_api_candidate": "responses_api",
        "first_provider_wire_contract_candidate": "text.format.type=json_schema;strict=true",
        "provider_and_model_binding_deferred_to_exact_admission": True,
        "deepseek_beta_strict_named_function_retained_for_new_live_attempt": False,
        "deepseek_json_object_selected": False,
        "local_parser_relaxed": False,
        "adapter_implemented": False,
        "new_admission_issued": False,
        "actual_execution_started": False,
        "model_calls": 0,
        "provider_api_calls": 0,
        "execution_network_calls": 0,
        "external_tool_calls": 0,
        "focused_T03_contracts": "44 passed in 6.39s",
        "combined_S2_T01_T03_contracts": "57 passed in 95.50s",
        "project_os_preflight": "6 passed in 0.36s",
    }
    adapter = tasks["S2-T03"][
        "native_json_schema_transport_adapter_implementation"
    ]
    assert adapter["status"] == "fixture_proven_exact_live_admission_decision_pending"
    assert adapter["provider_neutral_parser"] is True
    assert adapter["tools_sent"] is False
    assert adapter["tool_choice_sent"] is False
    assert adapter["default_application_runtime_wired"] is False
    assert adapter["exact_model_bound"] is False
    assert adapter["new_admission_issued"] is False
    decision = tasks["S2-T03"]["native_json_schema_exact_live_admission_decision"]
    assert decision["exact_model"] == "gpt-5.6-sol"
    assert decision["account_model_availability_verified"] is True
    assert decision["model_inference_or_generation_calls"] == 0
    assert decision["runner_preflight_deepseek_hardcoded"] is True
    assert decision["admission_transport_binding_present"] is False
    assert decision["new_admission_issued"] is False
    assert backlog["next_action"]["S3_T08_initial_result_ref"] == (
        "configs/releases/"
        "fin_ia_0_1_s3_t08_deterministic_integration_and_exact_live_readiness_v1_0.json"
    )
    assert backlog["next_action"]["S3_T08_result_ref"] == (
        "configs/releases/"
        "fin_ia_0_1_s3_t08_three_cell_bounded_agent_adapter_repair_v1_0.json"
    )
    assert backlog["next_action"]["S3_T08_readiness_gate_status"] == (
        "pass_T09_ready_pending_separate_authority"
    )
    assert backlog["next_action"]["S3_T08_repair_execution_authorized"] is True
    assert backlog["next_action"]["S3_T09_execution_authorized"] is True
    assert backlog["next_action"]["consumed_admission_rerun_authorized"] is False
    assert backlog["next_action"][
        "source_network_or_external_tool_execution_authorized"
    ] is False
    assert backlog["next_action"]["release_or_production_authorized"] is False
    s3 = next(row for row in backlog["slices"] if row["slice_id"] == "S3")
    assert s3["status"] == (
        "pass_NVDA_R2_owner_accepted_S3_T10_closeout_complete"
    )


def test_frozen_digest_registry_only_allows_declared_living_sources_to_move() -> None:
    backlog = _load(BACKLOG)
    declared_living_sources = {
        "docs/architecture/repository/"
        "FIN_0_1_PROGRAM_EXECUTION_PLAN_DRAFT_20260719.zh-CN.md",
        "docs/product/"
        "FIN_PRD_FULL_ABSORPTION_AND_RELEASE_ALLOCATION_MATRIX_20260719.zh-CN.md",
    }
    seen: set[str] = set()
    changed_since_freeze: set[str] = set()
    for row in backlog["stable_source_digests"]:
        assert row["path"] not in seen
        seen.add(row["path"])
        assert len(row["sha256"]) == 64
        int(row["sha256"], 16)
        data = (ROOT / row["path"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != row["sha256"]:
            changed_since_freeze.add(row["path"])
    assert changed_since_freeze == declared_living_sources
