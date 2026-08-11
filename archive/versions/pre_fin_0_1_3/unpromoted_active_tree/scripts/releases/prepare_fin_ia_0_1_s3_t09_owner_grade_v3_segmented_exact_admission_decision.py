from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (
    BOUNDED_DEEPSEEK_BETA_BASE_URL,
    S3_OWNER_GRADE_SEGMENTED_AGGREGATE_OUTPUT_TOKEN_BUDGET,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_REF,
    S3_OWNER_GRADE_SEGMENTED_STAGE_OUTPUT_TOKEN_BUDGETS,
    S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF,
    S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF,
    S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF,
    S3_THREE_CELL_BOUNDED_AGENT_PROFILE_REF,
    S3ThreeCellBoundedAgentAdmission,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from apps.workbench.backend.application.case_service import CasePrincipal, CaseService
from apps.workbench.backend.application.evidence_service import EvidenceService
from apps.workbench.backend.application.local_research_service import (
    P36LocalResearchService,
)
from apps.workbench.backend.application.research_runtime import (
    prepare_s3_three_cell_bounded_agent_exact_input,
)
from scripts.releases.prepare_fin_ia_0_1_s3_t09_paired_deterministic_baseline_decision import (
    _logical_snapshot,
    _sha256,
    _tree_digest,
)
from sec_agent.canonical_runtime.models import canonical_digest


TENANT_ID = "tenant-fin01-s3-t09-eval"
PROJECT_ID = "project-fin01-s3-t09-eval"
ACTOR_ID = "analyst-fin01-s3-t09-eval"
EXECUTION_IDENTITY = (
    "fin01-s3-t09-three-cell-deepseek-owner-grade-v3-segmented-"
    "live-validation-r1"
)
PROSPECTIVE_ADMISSION_ID = (
    "fin01-s3-t09-three-cell-deepseek-owner-grade-v3-segmented-"
    "exact-admission-r1"
)
PROSPECTIVE_ADMISSION_FILE = (
    "configs/releases/fin_ia_0_1_s3_t09_three_cell_deepseek_"
    "owner_grade_v3_segmented_exact_admission_v1_0.json"
)
EXECUTION_MODE = "exact_live_three_cell_deepseek_owner_grade_v3_segmented_r1"
EXPECTED_PROGRAM_CELLS = (
    "demand_authenticity_and_sustainability",
    "value_and_profit_capture",
    "bottleneck_counterevidence_and_what_would_change",
)
PERMISSIONS = frozenset(
    {
        "case:read",
        "planning:read",
        "execution:read",
        "evidence:read",
    }
)


class SegmentedAdmissionDecisionPreflightError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise SegmentedAdmissionDecisionPreflightError(code)


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    return (
        resolved.relative_to(ROOT).as_posix()
        if resolved.is_relative_to(ROOT)
        else str(resolved)
    )


def _principal() -> CasePrincipal:
    return CasePrincipal(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        actor_id=ACTOR_ID,
        permissions=PERMISSIONS,
    )


def _execution_counts(case_service: CaseService, case_id: str) -> dict[str, int]:
    return {
        table: len(case_service._facade.store.list_latest(table, case_id=case_id))
        for table in (
            "canonical_work_units",
            "canonical_attempts",
            "canonical_research_run_versions",
            "canonical_artifact_versions",
        )
    }


def _nested_binding(
    payload: Mapping[str, Any],
    path: tuple[str, ...],
) -> Any:
    current: Any = payload
    for key in path:
        if not isinstance(current, Mapping) or key not in current:
            raise SegmentedAdmissionDecisionPreflightError(
                "segmented_transport_result_binding_missing"
            )
        current = current[key]
    return current


def prepare(
    *,
    runtime_root: Path,
    baseline_result_path: Path,
    paired_decision_path: Path,
    monolithic_v3_result_path: Path,
    transport_implementation_result_path: Path,
    additional_prior_failed_result_path: Path | None = None,
    additional_prior_failed_result_paths: tuple[Path, ...] = (),
    execution_identity: str = EXECUTION_IDENTITY,
    prospective_admission_id: str = PROSPECTIVE_ADMISSION_ID,
    prospective_admission_file: str = PROSPECTIVE_ADMISSION_FILE,
    execution_mode: str = EXECUTION_MODE,
    transport_ref: str = S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_REF,
    required_transport_result_status: str = (
        "pass_zero_call_segmented_specialist_transport_fixture_proven_"
        "fresh_exact_admission_decision_pending"
    ),
    decision_status: str = (
        "pass_fresh_segmented_v3_exact_admission_contract_decided_"
        "issuance_pending_separate_authority"
    ),
    decision_contract_ref: str = (
        "fin01.s3.owner_grade_v3_segmented_exact_admission_decision:v1"
    ),
    transport_result_binding_path: tuple[str, ...] = (
        "implementation",
        "transport_ref",
    ),
    required_transport_result_binding_value: str | None = None,
    provider_output_capture_policy_ref: str | None = None,
    research_lead_transport_ref: str | None = None,
    memo_writer_transport_ref: str | None = None,
    research_profile_ref: str | None = None,
    output_contract_ref: str = S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF,
    scoped_identity_contract_ref: str | None = None,
    stage_output_token_budgets: Mapping[str, int] = (
        S3_OWNER_GRADE_SEGMENTED_STAGE_OUTPUT_TOKEN_BUDGETS
    ),
    aggregate_output_token_budget: int = (
        S3_OWNER_GRADE_SEGMENTED_AGGREGATE_OUTPUT_TOKEN_BUDGET
    ),
) -> dict[str, Any]:
    runtime_root = runtime_root.resolve()
    canonical_root = runtime_root / "canonical-runtime"
    database_path = canonical_root / "canonical.sqlite"
    object_root = canonical_root / "objects"
    baseline_result = json.loads(baseline_result_path.read_text(encoding="utf-8"))
    paired_decision = json.loads(paired_decision_path.read_text(encoding="utf-8"))
    monolithic_v3_result = json.loads(
        monolithic_v3_result_path.read_text(encoding="utf-8")
    )
    transport_result = json.loads(
        transport_implementation_result_path.read_text(encoding="utf-8")
    )
    additional_prior_failed_paths = (
        *((additional_prior_failed_result_path,) if additional_prior_failed_result_path else ()),
        *additional_prior_failed_result_paths,
    )
    _require(
        len(additional_prior_failed_paths)
        == len({path.resolve() for path in additional_prior_failed_paths}),
        "additional_prior_failed_result_path_duplicate",
    )
    additional_prior_failed_results = [
        (path, json.loads(path.read_text(encoding="utf-8")))
        for path in additional_prior_failed_paths
    ]
    source = baseline_result["source_binding"]
    case_id = str(source["case_id"])
    decision_surface_ref = str(source["decision_surface_ref"])

    _require(
        transport_result["status"] == required_transport_result_status,
        "segmented_transport_implementation_not_fixture_proven",
    )
    _require(
        _nested_binding(transport_result, transport_result_binding_path)
        == (
            transport_ref
            if required_transport_result_binding_value is None
            else required_transport_result_binding_value
        ),
        "segmented_transport_ref_mismatch",
    )
    _require(
        monolithic_v3_result["canonical_terminal_truth"]["research_run_state"]
        == "failed"
        and monolithic_v3_result["canonical_terminal_truth"]["artifact_count"] == 0,
        "monolithic_v3_terminal_failure_truth_mismatch",
    )
    for _, additional_prior_failed_result in additional_prior_failed_results:
        _require(
            additional_prior_failed_result["canonical_terminal_truth"][
                "research_run_state"
            ]
            == "failed"
            and additional_prior_failed_result["canonical_terminal_truth"][
                "artifact_count"
            ]
            == 0,
            "additional_prior_terminal_failure_truth_mismatch",
        )

    before_database_digest = _sha256(database_path)
    before_object_digest = _tree_digest(object_root)
    before_snapshot = _logical_snapshot(database_path, case_id)
    _require(
        int(before_snapshot["case"]["case_version"]) == int(source["case_version"]),
        "case_version_mismatch",
    )
    _require(
        str(before_snapshot["case_control"]["as_of"])
        == str(source["analysis_as_of"]),
        "case_as_of_mismatch",
    )
    expected_prior_run_ids = {
        str(baseline_result["materialized_identity"]["research_run_id"]),
        str(monolithic_v3_result["identity"]["research_run_id"]),
        *(
            str(row["research_run_id"])
            for row in paired_decision["paired_baseline_search"][
                "same_case_and_input_head_runs"
            ]
        ),
    }
    for _, additional_prior_failed_result in additional_prior_failed_results:
        expected_prior_run_ids.add(
            str(additional_prior_failed_result["identity"]["research_run_id"])
        )
    _require(
        set(before_snapshot["research_run_ids"]) == expected_prior_run_ids,
        "target_research_run_set_not_at_expected_four_run_head",
    )

    with tempfile.TemporaryDirectory(
        prefix="fin01-s3-t09-owner-grade-v3-segmented-decision-"
    ) as temp_dir:
        clone_root = Path(temp_dir) / "canonical-runtime"
        shutil.copytree(canonical_root, clone_root)
        case_service = CaseService.for_fixture_root(clone_root, repo_root=ROOT)
        local_service = P36LocalResearchService.from_case_service(
            case_service, repo_root=ROOT
        )
        evidence_service = EvidenceService.from_case_service(
            case_service, repo_root=ROOT
        )
        clone_before = _execution_counts(case_service, case_id)
        first = prepare_s3_three_cell_bounded_agent_exact_input(
            local_service,
            evidence_service,
            case_id,
            _principal(),
            decision_surface_contract_ref=decision_surface_ref,
            execution_identity=execution_identity,
        )
        second = prepare_s3_three_cell_bounded_agent_exact_input(
            local_service,
            evidence_service,
            case_id,
            _principal(),
            decision_surface_contract_ref=decision_surface_ref,
            execution_identity=execution_identity,
        )
        clone_after = _execution_counts(case_service, case_id)
        first_payload = first.model_dump(mode="json")
        second_payload = second.model_dump(mode="json")
        _require(first_payload == second_payload, "segmented_double_prepare_parity_failed")
        _require(
            clone_before == clone_after,
            "segmented_decision_prepare_created_execution_state",
        )

    _require(
        tuple(first.input_pack.program_cell_ids) == EXPECTED_PROGRAM_CELLS,
        "segmented_program_cells_mismatch",
    )
    _require(
        first.input_pack.case_id == case_id
        and first.input_pack.case_version == int(source["case_version"])
        and first.input_pack.as_of == str(source["analysis_as_of"])
        and first.decision_surface_contract_ref == decision_surface_ref
        and first.input_pack.input_head_digest == str(source["input_head_digest"]),
        "segmented_shared_business_input_mismatch",
    )
    baseline_contract = dict(first.input_pack.paired_baseline_contract)
    _require(
        baseline_contract.get("baseline_output_body_exposed_to_agent") is False,
        "segmented_baseline_body_exposure_forbidden",
    )
    _require(
        first.work_unit_id not in before_snapshot["work_unit_ids"],
        "segmented_work_unit_not_fresh",
    )
    _require(
        first.attempt_id not in before_snapshot["attempt_ids"],
        "segmented_attempt_not_fresh",
    )
    _require(
        first.research_run_id not in before_snapshot["research_run_ids"],
        "segmented_run_not_fresh",
    )
    prospective_admission_path = ROOT / prospective_admission_file
    _require(
        not prospective_admission_path.exists(),
        "segmented_prospective_admission_file_already_exists",
    )

    admission_kwargs: dict[str, Any] = {
        "admission_id": prospective_admission_id,
        "output_contract_ref": output_contract_ref,
        "execution_enabled": True,
        "execution_mode": execution_mode,
        "case_id": case_id,
        "case_version": int(source["case_version"]),
        "as_of": str(source["analysis_as_of"]),
        "input_digest": first.input_digest,
        "provider": "deepseek",
        "model": "deepseek-v4-pro",
        "model_ref": "deepseek:deepseek-v4-pro",
        "api_key_env": "DEEPSEEK_API_KEY",
        "base_url": BOUNDED_DEEPSEEK_BETA_BASE_URL,
        "transport_ref": transport_ref,
        "reasoning_effort": "none",
        "max_semantic_model_calls": 12,
        "max_provider_calls": 12,
        "max_network_calls": 12,
        "max_total_cost_usd": 0.10,
        "specialist_max_output_tokens": stage_output_token_budgets[
            "specialist"
        ],
        "lead_max_output_tokens": stage_output_token_budgets[
            "lead"
        ],
        "writer_max_output_tokens": stage_output_token_budgets[
            "writer"
        ],
        "verifier_max_output_tokens": stage_output_token_budgets[
            "verifier"
        ],
        "timeout_seconds": 120,
        "max_transport_attempts_per_call": 1,
        "retry_budget": 0,
        "source_network_calls_allowed": False,
        "external_tool_calls_allowed": False,
        "live_business_case_head_writes_allowed": False,
    }
    if provider_output_capture_policy_ref is not None:
        _require(
            provider_output_capture_policy_ref
            == S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF,
            "provider_output_capture_policy_ref_mismatch",
        )
        admission_kwargs["provider_output_capture_policy_ref"] = (
            provider_output_capture_policy_ref
        )
    if research_lead_transport_ref is not None:
        admission_kwargs["research_lead_transport_ref"] = (
            research_lead_transport_ref
        )
    if memo_writer_transport_ref is not None:
        admission_kwargs["memo_writer_transport_ref"] = (
            memo_writer_transport_ref
        )
    if research_profile_ref is not None:
        admission_kwargs["research_profile_ref"] = research_profile_ref
    if scoped_identity_contract_ref is not None:
        _require(
            output_contract_ref == S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF,
            "scoped_identity_contract_requires_output_v4",
        )
        admission_kwargs["scoped_identity_contract_ref"] = (
            scoped_identity_contract_ref
        )
    admission = S3ThreeCellBoundedAgentAdmission(**admission_kwargs)
    admission.assert_profile_admissible()
    callback_calls = 0

    def _must_not_call_provider(**_: Any) -> dict[str, Any]:
        nonlocal callback_calls
        callback_calls += 1
        raise AssertionError("provider_callback_forbidden_in_decision_preflight")

    build_s3_three_cell_bounded_agent_executor_for_admission(
        admission, chat_completion_fn=_must_not_call_provider
    )
    _require(callback_calls == 0, "provider_callback_called_during_decision")

    after_snapshot = _logical_snapshot(database_path, case_id)
    after_database_digest = _sha256(database_path)
    after_object_digest = _tree_digest(object_root)
    _require(before_snapshot == after_snapshot, "target_canonical_logical_state_changed")
    _require(before_database_digest == after_database_digest, "target_database_changed")
    _require(before_object_digest == after_object_digest, "target_object_tree_changed")

    transport_retries_value = os.environ.get("LLM_GATEWAY_TRANSPORT_RETRIES")
    admission_payload = admission.digest_payload()
    output_only_cost_ceiling = (
        aggregate_output_token_budget
        * admission.output_usd_per_million
        / 1_000_000
    )
    input_cache_miss_pricing_units_under_total_cap = int(
        (admission.max_total_cost_usd - output_only_cost_ceiling)
        * 1_000_000
        / admission.input_cache_miss_usd_per_million
    )
    return {
        "status": decision_status,
        "contract_ref": decision_contract_ref,
        "runtime_root": _display_path(runtime_root),
        "source_refs": {
            "baseline_result": _display_path(baseline_result_path),
            "paired_decision": _display_path(paired_decision_path),
            "monolithic_v3_result": _display_path(monolithic_v3_result_path),
            "transport_implementation_result": _display_path(
                transport_implementation_result_path
            ),
            **(
                {
                    "additional_prior_failed_result": _display_path(
                        additional_prior_failed_paths[0]
                    )
                }
                if len(additional_prior_failed_paths) == 1
                else {}
            ),
            **(
                {
                    "additional_prior_failed_results": [
                        _display_path(path)
                        for path in additional_prior_failed_paths
                    ]
                }
                if len(additional_prior_failed_paths) > 1
                else {}
            ),
        },
        "identity": {
            "execution_identity": execution_identity,
            "case_id": case_id,
            "case_version": int(source["case_version"]),
            "analysis_as_of": source["analysis_as_of"],
            "decision_surface_ref": decision_surface_ref,
            "input_head_digest": first.input_pack.input_head_digest,
            "work_unit_id": first.work_unit_id,
            "attempt_id": first.attempt_id,
            "research_run_id": first.research_run_id,
            "execution_profile_version_ref": S3_THREE_CELL_BOUNDED_AGENT_PROFILE_REF,
            "input_digest": first.input_digest,
            "preparation_digest": first.preparation_digest,
            "program_cell_ids": list(first.input_pack.program_cell_ids),
        },
        "double_prepare": {
            "equal": True,
            "prepared_payload_digest": canonical_digest(first_payload),
            "clone_execution_counts_before": clone_before,
            "clone_execution_counts_after": clone_after,
        },
        "freshness_and_nonreuse": {
            "work_unit_absent": True,
            "attempt_absent": True,
            "research_run_absent": True,
            "distinct_from_all_prior_agent_and_baseline_runs": True,
            "prior_research_run_ids": sorted(expected_prior_run_ids),
            "consumed_monolithic_v3_identity_reusable": False,
            "additional_consumed_failed_identity_reusable": False,
            "additional_consumed_failed_identity_count": len(
                additional_prior_failed_results
            ),
            "baseline_output_body_exposed_to_agent": False,
            "baseline_body_or_artifact_is_not_provider_input": True,
        },
        "prospective_admission": {
            "payload": admission_payload,
            "digest": canonical_digest(admission_payload),
            "admission_issued": False,
            "admission_consumed": False,
            "execution_started": False,
            "prospective_admission_file_absent": True,
            "prospective_admission_file": prospective_admission_file,
        },
        "provider_route_review": {
            "decision": "retain_deepseek_with_fixture_proven_segmented_transport",
            "provider_transport": "json_object_three_segment_specialist",
            "server_side_strict_json_schema_claimed": False,
            "local_segment_and_full_output_validators_are_fail_closed_owners": True,
            "credential_present": bool(os.environ.get("DEEPSEEK_API_KEY")),
            "credential_value_read_output_or_persisted": False,
            "provider_health_probe_performed": False,
            "transport_retries_env_is_zero": transport_retries_value == "0",
            "transport_retries_env_state": (
                "zero" if transport_retries_value == "0" else "unset_or_nonzero"
            ),
            "execution_precondition": "LLM_GATEWAY_TRANSPORT_RETRIES must equal 0",
        },
        "budget_and_stop_contract": {
            "semantic_model_calls": 12,
            "provider_calls": 12,
            "network_calls": 12,
            "specialist_segment_output_tokens": [1600, 1200, 1400],
            "specialist_total_output_tokens_each": (
                stage_output_token_budgets["specialist"]
            ),
            "lead_max_output_tokens": stage_output_token_budgets[
                "lead"
            ],
            "writer_max_output_tokens": stage_output_token_budgets[
                "writer"
            ],
            "verifier_max_output_tokens": stage_output_token_budgets[
                "verifier"
            ],
            "aggregate_max_output_tokens": aggregate_output_token_budget,
            "output_only_cost_ceiling_usd": round(output_only_cost_ceiling, 8),
            "input_cache_miss_pricing_units_under_total_cap": (
                input_cache_miss_pricing_units_under_total_cap
            ),
            "max_total_cost_usd": 0.10,
            "max_transport_attempts_per_call": 1,
            "retry_budget": 0,
            "automatic_repair_fallback_or_rerun": False,
            "first_parse_shape_schema_semantic_or_length_failure": (
                "terminal_fail_closed_stop"
            ),
        },
        "comparison_boundary": {
            "paired_comparison_requires_separate_read_only_step": True,
            "paired_comparison_performed": False,
            "owner_acceptance_performed": False,
        },
        "target_read_only_audit": {
            "expected_prior_research_run_count": len(expected_prior_run_ids),
            "canonical_database_sha256": before_database_digest,
            "canonical_object_tree_sha256": before_object_digest,
            "logical_snapshot_unchanged": True,
            "canonical_database_file_unchanged": True,
            "canonical_object_tree_unchanged": True,
        },
        "observed_counts": {
            "admissions_issued": 0,
            "admissions_consumed": 0,
            "model_calls": 0,
            "provider_calls": callback_calls,
            "network_calls": 0,
            "source_network_calls": 0,
            "external_tool_calls": 0,
            "target_canonical_writes": 0,
            "target_object_writes": 0,
            "agent_runs_created": 0,
            "paired_comparisons": 0,
            "human_review_writes": 0,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--runtime-root",
        type=Path,
        default=ROOT
        / ".codex_runtime"
        / "fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1",
    )
    parser.add_argument(
        "--baseline-result",
        type=Path,
        default=ROOT
        / "configs/releases/fin_ia_0_1_s3_t09_paired_deterministic_"
        "baseline_materialization_v1_0.json",
    )
    parser.add_argument(
        "--paired-decision",
        type=Path,
        default=ROOT
        / "configs/releases/fin_ia_0_1_s3_t09_replacement_live_artifact_"
        "paired_baseline_decision_v1_0.json",
    )
    parser.add_argument(
        "--monolithic-v3-result",
        type=Path,
        default=ROOT
        / "configs/releases/fin_ia_0_1_s3_t09_owner_grade_v3_fresh_"
        "live_execution_result_v1_0.json",
    )
    parser.add_argument(
        "--transport-implementation-result",
        type=Path,
        default=ROOT
        / "configs/releases/fin_ia_0_1_s3_t09_owner_grade_v3_segmented_"
        "specialist_transport_implementation_v1_0.json",
    )
    args = parser.parse_args()
    print(
        json.dumps(
            prepare(
                runtime_root=args.runtime_root,
                baseline_result_path=args.baseline_result.resolve(),
                paired_decision_path=args.paired_decision.resolve(),
                monolithic_v3_result_path=args.monolithic_v3_result.resolve(),
                transport_implementation_result_path=(
                    args.transport_implementation_result.resolve()
                ),
            ),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
