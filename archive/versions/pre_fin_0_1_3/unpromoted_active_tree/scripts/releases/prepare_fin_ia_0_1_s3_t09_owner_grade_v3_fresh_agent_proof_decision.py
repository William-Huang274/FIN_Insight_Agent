from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (
    BOUNDED_DEEPSEEK_BETA_BASE_URL,
    S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF,
    S3_THREE_CELL_BOUNDED_AGENT_PROFILE_REF,
    S3_THREE_CELL_DEEPSEEK_SEGMENTED_TRANSPORT_REF,
    S3ThreeCellBoundedAgentAdmission,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from apps.workbench.backend.application.case_service import CasePrincipal, CaseService
from apps.workbench.backend.application.evidence_service import EvidenceService
from apps.workbench.backend.application.local_research_service import P36LocalResearchService
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
    "fin01-s3-t09-three-cell-deepseek-owner-grade-v3-live-validation-r1"
)
PROSPECTIVE_ADMISSION_ID = (
    "fin01-s3-t09-three-cell-deepseek-owner-grade-v3-exact-admission-r1"
)
EXECUTION_MODE = "exact_live_three_cell_deepseek_owner_grade_v3_r1"
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


class FreshV3DecisionPreflightError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise FreshV3DecisionPreflightError(code)


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


def prepare(
    *,
    runtime_root: Path,
    baseline_result_path: Path,
    paired_decision_path: Path,
) -> dict[str, Any]:
    runtime_root = runtime_root.resolve()
    canonical_root = runtime_root / "canonical-runtime"
    database_path = canonical_root / "canonical.sqlite"
    object_root = canonical_root / "objects"
    baseline_result = json.loads(baseline_result_path.read_text(encoding="utf-8"))
    paired_decision = json.loads(paired_decision_path.read_text(encoding="utf-8"))
    source = baseline_result["source_binding"]
    case_id = str(source["case_id"])
    decision_surface_ref = str(source["decision_surface_ref"])

    before_database_digest = _sha256(database_path)
    before_object_digest = _tree_digest(object_root)
    before_snapshot = _logical_snapshot(database_path, case_id)
    _require(
        before_database_digest
        == str(baseline_result["canonical_delta"]["canonical_database_sha256_after"]),
        "target_database_not_at_frozen_post_baseline_head",
    )
    _require(
        before_object_digest
        == str(baseline_result["canonical_delta"]["canonical_object_tree_sha256_after"]),
        "target_object_tree_not_at_frozen_post_baseline_head",
    )
    _require(
        int(before_snapshot["case"]["case_version"]) == int(source["case_version"]),
        "case_version_mismatch",
    )
    _require(
        str(before_snapshot["case_control"]["as_of"]) == str(source["analysis_as_of"]),
        "case_as_of_mismatch",
    )

    with tempfile.TemporaryDirectory(prefix="fin01-s3-t09-owner-grade-v3-decision-") as temp_dir:
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
            execution_identity=EXECUTION_IDENTITY,
        )
        second = prepare_s3_three_cell_bounded_agent_exact_input(
            local_service,
            evidence_service,
            case_id,
            _principal(),
            decision_surface_contract_ref=decision_surface_ref,
            execution_identity=EXECUTION_IDENTITY,
        )
        clone_after = _execution_counts(case_service, case_id)
        first_payload = first.model_dump(mode="json")
        second_payload = second.model_dump(mode="json")
        _require(first_payload == second_payload, "fresh_v3_double_prepare_parity_failed")
        _require(clone_before == clone_after, "fresh_v3_prepare_created_execution_state")

    _require(
        tuple(first.input_pack.program_cell_ids) == EXPECTED_PROGRAM_CELLS,
        "fresh_v3_program_cells_mismatch",
    )
    _require(
        first.input_pack.case_id == case_id
        and first.input_pack.case_version == int(source["case_version"])
        and first.input_pack.as_of == str(source["analysis_as_of"])
        and first.decision_surface_contract_ref == decision_surface_ref
        and first.input_pack.input_head_digest == str(source["input_head_digest"]),
        "fresh_v3_shared_business_input_mismatch",
    )
    baseline_contract = dict(first.input_pack.paired_baseline_contract)
    _require(
        baseline_contract.get("baseline_output_body_exposed_to_agent") is False,
        "fresh_v3_baseline_body_exposure_forbidden",
    )
    _require(
        first.work_unit_id not in before_snapshot["work_unit_ids"],
        "fresh_v3_work_unit_not_fresh",
    )
    _require(
        first.attempt_id not in before_snapshot["attempt_ids"],
        "fresh_v3_attempt_not_fresh",
    )
    _require(
        first.research_run_id not in before_snapshot["research_run_ids"],
        "fresh_v3_run_not_fresh",
    )
    existing_run_ids = {
        str(source["source_agent_research_run_id"]),
        str(baseline_result["materialized_identity"]["research_run_id"]),
        *(
            str(row["research_run_id"])
            for row in paired_decision["paired_baseline_search"][
                "same_case_and_input_head_runs"
            ]
        ),
    }
    _require(
        first.research_run_id not in existing_run_ids,
        "fresh_v3_run_reuses_prior_agent_or_baseline_identity",
    )

    admission = S3ThreeCellBoundedAgentAdmission(
        admission_id=PROSPECTIVE_ADMISSION_ID,
        output_contract_ref=S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF,
        execution_enabled=True,
        execution_mode=EXECUTION_MODE,
        case_id=case_id,
        case_version=int(source["case_version"]),
        as_of=str(source["analysis_as_of"]),
        input_digest=first.input_digest,
        provider="deepseek",
        model="deepseek-v4-pro",
        model_ref="deepseek:deepseek-v4-pro",
        api_key_env="DEEPSEEK_API_KEY",
        base_url=BOUNDED_DEEPSEEK_BETA_BASE_URL,
        transport_ref=S3_THREE_CELL_DEEPSEEK_SEGMENTED_TRANSPORT_REF,
        reasoning_effort="none",
        max_semantic_model_calls=6,
        max_provider_calls=6,
        max_network_calls=6,
        max_total_cost_usd=0.10,
        specialist_max_output_tokens=2200,
        lead_max_output_tokens=1200,
        writer_max_output_tokens=1400,
        verifier_max_output_tokens=1000,
        timeout_seconds=120,
        max_transport_attempts_per_call=1,
        retry_budget=0,
        source_network_calls_allowed=False,
        external_tool_calls_allowed=False,
        live_business_case_head_writes_allowed=False,
    )
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
    return {
        "status": "pass_fresh_v3_exact_proof_contract_decided_no_admission_or_execution",
        "contract_ref": "fin01.s3.owner_grade_v3_fresh_agent_proof_decision:v1",
        "runtime_root": _display_path(runtime_root),
        "source_baseline_result_ref": _display_path(baseline_result_path),
        "identity": {
            "execution_identity": EXECUTION_IDENTITY,
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
            "distinct_from_all_prior_same_input_agent_runs_and_baseline": True,
            "prior_research_run_ids": sorted(existing_run_ids),
            "baseline_output_body_exposed_to_agent": False,
            "baseline_body_or_artifact_is_not_provider_input": True,
        },
        "prospective_admission": {
            "payload": admission.digest_payload(),
            "digest": canonical_digest(admission.digest_payload()),
            "admission_issued": False,
            "prospective_admission_file": (
                "configs/releases/fin_ia_0_1_s3_t09_three_cell_deepseek_"
                "owner_grade_v3_exact_admission_v1_0.json"
            ),
        },
        "provider_route_review": {
            "decision": "retain_deepseek_to_isolate_output_v3_contract_effect",
            "server_side_strict_json_schema_claimed": False,
            "provider_transport": "json_object",
            "local_v3_schema_and_semantic_validator_is_fail_closed_owner": True,
            "credential_present": bool(os.environ.get("DEEPSEEK_API_KEY")),
            "credential_value_read_output_or_persisted": False,
            "transport_retries_env_is_zero": transport_retries_value == "0",
            "transport_retries_env_state": (
                "zero" if transport_retries_value == "0" else "unset_or_nonzero"
            ),
            "execution_precondition": "LLM_GATEWAY_TRANSPORT_RETRIES must equal 0",
        },
        "budget_and_stop_contract": {
            "semantic_model_calls": 6,
            "provider_calls": 6,
            "network_calls": 6,
            "specialist_max_output_tokens_each": 2200,
            "lead_max_output_tokens": 1200,
            "writer_max_output_tokens": 1400,
            "verifier_max_output_tokens": 1000,
            "aggregate_max_output_tokens": 10200,
            "max_total_cost_usd": 0.10,
            "max_transport_attempts_per_call": 1,
            "retry_budget": 0,
            "automatic_repair_fallback_or_rerun": False,
            "first_parse_schema_semantic_or_length_failure": "terminal_fail_closed_stop",
        },
        "comparison_boundary": {
            "fresh_agent_artifact_comparison_state_remains": (
                "pending_distinct_terminal_deterministic_run"
            ),
            "paired_comparison_requires_separate_read_only_step": True,
            "paired_comparison_performed": False,
        },
        "target_read_only_audit": {
            "canonical_database_sha256": before_database_digest,
            "canonical_object_tree_sha256": before_object_digest,
            "logical_snapshot_unchanged": True,
            "canonical_database_file_unchanged": True,
            "canonical_object_tree_unchanged": True,
        },
        "observed_counts": {
            "admissions_issued": 0,
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
        / "configs"
        / "releases"
        / "fin_ia_0_1_s3_t09_paired_deterministic_baseline_materialization_v1_0.json",
    )
    parser.add_argument(
        "--paired-decision",
        type=Path,
        default=ROOT
        / "configs"
        / "releases"
        / "fin_ia_0_1_s3_t09_replacement_live_artifact_paired_baseline_decision_v1_0.json",
    )
    args = parser.parse_args()
    print(
        json.dumps(
            prepare(
                runtime_root=args.runtime_root,
                baseline_result_path=args.baseline_result.resolve(),
                paired_decision_path=args.paired_decision.resolve(),
            ),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
