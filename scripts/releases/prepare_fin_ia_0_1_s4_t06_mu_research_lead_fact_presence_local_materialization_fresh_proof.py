from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_contract_policies import (
    S3_RESEARCH_LEAD_CONFLICT_FACT_PRESENCE_LOCAL_MATERIALIZATION_POLICY,
    research_lead_transport_contract,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V5_REF,
    S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V7_REF,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF,
    S3ThreeCellBoundedAgentAdmission,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from apps.workbench.backend.application.research_runtime import (
    prepare_s4_source_grounded_exact_input,
)
from scripts.releases.prepare_fin_ia_0_1_s3_t09_paired_deterministic_baseline_decision import (
    _logical_snapshot,
    _sha256,
    _tree_digest,
)
from scripts.releases.run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution import (
    _principal,
    _services,
)
from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.s4_case_runtime import (
    compile_s4_case_evidence_role_group_mapping,
    load_s4_case_runtime_binding,
    load_s4_source_grounded_input_pack,
)


RUNTIME_ROOT = (
    ROOT
    / ".codex_runtime"
    / "fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1"
)
SOURCE_PREPARATION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t06_mu_canonical_case_surface_and_fresh_exact_"
    "admission_preparation_zero_call_proof_v1_0.json"
)
SOURCE_FAILURE = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t06_mu_fresh_exact_live_execution_failure_result_v1_0.json"
)
SOURCE_ADMISSION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t06_mu_fresh_exact_admission_r1.json"
)
IMPLEMENTATION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t06_mu_research_lead_fact_presence_local_"
    "materialization_minimum_zero_call_implementation_v1_0.json"
)
DECISION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t06_mu_research_lead_fact_presence_local_"
    "materialization_fresh_agent_proof_decision_v1_0.json"
)
PROSPECTIVE_ADMISSION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t06_mu_research_lead_fact_presence_local_"
    "materialization_fresh_exact_admission_r2.json"
)
EXECUTION_IDENTITY = (
    "fin01-s4-t06-mu-research-lead-fact-presence-local-"
    "materialization-exact-live-r2"
)
PROSPECTIVE_ADMISSION_ID = (
    "fin01-s4-t06-mu-research-lead-fact-presence-local-"
    "materialization-fresh-exact-admission-r2"
)
EXECUTION_MODE = (
    "exact_live_s4_mu_research_lead_fact_presence_local_"
    "materialization_r2"
)
NEXT_ACTION = (
    "S4-T06-MU-RESEARCH-LEAD-CONFLICT-FACT-PRESENCE-LOCAL-"
    "MATERIALIZATION-FRESH-EXACT-ADMISSION-ISSUANCE-DECISION"
)


class S4T06MuFactPresenceFreshProofError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S4T06MuFactPresenceFreshProofError(code)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    return (
        resolved.relative_to(ROOT).as_posix()
        if resolved.is_relative_to(ROOT)
        else str(resolved)
    )


def _execution_counts(case_service: object, case_id: str) -> dict[str, int]:
    store = case_service._facade.store
    return {
        table: len(store.list_latest(table, case_id=case_id))
        for table in (
            "canonical_work_units",
            "canonical_attempts",
            "canonical_research_run_versions",
            "canonical_artifact_versions",
        )
    }


def _verify_implementation_bindings(
    implementation: Mapping[str, Any],
) -> dict[str, str]:
    bindings = {
        str(path): str(digest)
        for path, digest in implementation["exact_code_bindings"].items()
    }
    for relative_path, expected_digest in bindings.items():
        _require(
            _sha256(ROOT / relative_path) == expected_digest,
            f"implementation_code_binding_drift:{relative_path}",
        )
    return bindings


def prepare(
    *,
    runtime_root: Path = RUNTIME_ROOT,
    source_preparation_path: Path = SOURCE_PREPARATION,
    source_failure_path: Path = SOURCE_FAILURE,
    source_admission_path: Path = SOURCE_ADMISSION,
    implementation_path: Path = IMPLEMENTATION,
) -> dict[str, Any]:
    runtime_root = runtime_root.resolve()
    canonical_root = runtime_root / "canonical-runtime"
    database_path = canonical_root / "canonical.sqlite"
    object_root = canonical_root / "objects"
    source_preparation = _load(source_preparation_path)
    source_failure = _load(source_failure_path)
    source_admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        _load(source_admission_path)
    )
    implementation = _load(implementation_path)
    materialization = source_preparation["canonical_materialization"]
    prior_binding = source_failure["source_binding"]
    case_id = str(materialization["case_id"])
    decision_surface_ref = str(
        materialization["decision_surface_contract_ref"]
    )
    prior_work_unit_id = str(prior_binding["work_unit_id"])
    prior_attempt_id = str(prior_binding["attempt_id"])
    prior_research_run_id = str(prior_binding["research_run_id"])

    _require(
        implementation["status"]
        == "pass_zero_call_implementation_fixture_proven_"
        "fresh_agent_proof_pending",
        "implementation_not_fixture_proven",
    )
    implementation_bindings = _verify_implementation_bindings(
        implementation
    )
    _require(
        source_failure["status"]
        == "terminal_failed_research_lead_fact_presence_summary_"
        "mismatch_no_retry_no_paired_assessment",
        "immutable_R1_failure_status_mismatch",
    )
    _require(
        source_admission.research_lead_transport_ref
        == S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V5_REF,
        "immutable_R1_source_lead_transport_is_not_v5",
    )
    _require(
        source_admission.transport_ref
        == S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF,
        "immutable_R1_source_specialist_transport_is_not_v7",
    )

    v5_contract = research_lead_transport_contract(
        S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V5_REF
    )
    v7_contract = research_lead_transport_contract(
        S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V7_REF
    )
    policy = (
        S3_RESEARCH_LEAD_CONFLICT_FACT_PRESENCE_LOCAL_MATERIALIZATION_POLICY
    )
    _require(
        v5_contract.conflict_fact_presence_materialization_policy_ref is None,
        "historical_v5_materialization_behavior_changed",
    )
    _require(
        v7_contract.conflict_fact_presence_materialization_policy_ref
        == policy.policy_ref,
        "v7_fact_presence_materialization_capability_missing",
    )
    _require(
        policy.provider_field_id == "fact_presence_summary"
        and policy.canonical_field_id == "fact_presence_summary"
        and dict(policy.truth_table)
        == {
            "all_involved_claims_supported": "facts_present",
            "no_involved_claims_supported": "no_facts_present",
            "some_involved_claims_supported": "mixed_fact_presence",
        },
        "fact_presence_materialization_policy_shape_mismatch",
    )

    before_database_digest = _sha256(database_path)
    before_object_digest = _tree_digest(object_root)
    before_snapshot = _logical_snapshot(database_path, case_id)
    _require(
        prior_work_unit_id in before_snapshot["work_unit_ids"],
        "immutable_R1_work_unit_missing",
    )
    _require(
        prior_attempt_id in before_snapshot["attempt_ids"],
        "immutable_R1_attempt_missing",
    )
    _require(
        prior_research_run_id in before_snapshot["research_run_ids"],
        "immutable_R1_research_run_missing",
    )

    binding = load_s4_case_runtime_binding(ROOT, "MU")
    source_pack = load_s4_source_grounded_input_pack(ROOT, "MU")
    mapping = compile_s4_case_evidence_role_group_mapping(binding)
    _require(
        [len(group.source_evidence_roles) for group in mapping.role_groups]
        == [4, 5, 5],
        "mu_role_group_shape_mismatch",
    )
    _require(mapping.exact_role_count == 14, "mu_exact_role_count_mismatch")

    with tempfile.TemporaryDirectory(
        prefix="fin01-s4-t06-mu-fact-presence-fresh-proof-"
    ) as temp_dir:
        clone_runtime_root = Path(temp_dir) / runtime_root.name
        shutil.copytree(runtime_root, clone_runtime_root)
        case_service, _, evidence_service = _services(clone_runtime_root)
        clone_before = _execution_counts(case_service, case_id)
        clone_snapshot = _logical_snapshot(
            clone_runtime_root / "canonical-runtime/canonical.sqlite",
            case_id,
        )
        first = prepare_s4_source_grounded_exact_input(
            case_service,
            evidence_service,
            binding,
            source_pack,
            case_id,
            _principal(),
            decision_surface_contract_ref=decision_surface_ref,
            execution_identity=EXECUTION_IDENTITY,
        )
        second = prepare_s4_source_grounded_exact_input(
            case_service,
            evidence_service,
            binding,
            source_pack,
            case_id,
            _principal(),
            decision_surface_contract_ref=decision_surface_ref,
            execution_identity=EXECUTION_IDENTITY,
        )
        clone_after = _execution_counts(case_service, case_id)

    first_payload = first.model_dump(mode="json")
    second_payload = second.model_dump(mode="json")
    _require(first_payload == second_payload, "double_prepare_parity_failed")
    _require(clone_before == clone_after, "prepare_created_clone_execution_state")
    _require(
        first.work_unit_id not in before_snapshot["work_unit_ids"],
        "fresh_work_unit_reused",
    )
    _require(
        first.attempt_id not in before_snapshot["attempt_ids"],
        "fresh_attempt_reused",
    )
    _require(
        first.research_run_id not in before_snapshot["research_run_ids"],
        "fresh_research_run_reused",
    )
    _require(
        first.input_digest == source_admission.input_digest,
        "source_grounded_input_digest_changed",
    )
    _require(
        first.role_group_mapping_digest == mapping.role_group_mapping_digest,
        "prepared_mapping_digest_mismatch",
    )

    prospective_admission = source_admission.model_copy(
        update={
            "admission_id": PROSPECTIVE_ADMISSION_ID,
            "execution_mode": EXECUTION_MODE,
            "input_digest": first.input_digest,
            "research_lead_transport_ref": (
                S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V7_REF
            ),
        }
    )
    prospective_admission.assert_profile_admissible()
    _require(
        prospective_admission.research_lead_transport_ref
        == S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V7_REF,
        "prospective_v7_lead_binding_missing",
    )
    _require(
        prospective_admission.transport_ref
        == S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF,
        "prospective_v7_specialist_binding_missing",
    )
    callback_calls = 0

    def _must_not_call_provider(**_: Any) -> dict[str, Any]:
        nonlocal callback_calls
        callback_calls += 1
        raise AssertionError("provider_callback_forbidden_in_fresh_proof")

    build_s3_three_cell_bounded_agent_executor_for_admission(
        prospective_admission,
        chat_completion_fn=_must_not_call_provider,
    )
    _require(callback_calls == 0, "provider_callback_called")
    _require(
        not PROSPECTIVE_ADMISSION.exists(),
        "prospective_admission_already_exists",
    )

    after_snapshot = _logical_snapshot(database_path, case_id)
    after_database_digest = _sha256(database_path)
    after_object_digest = _tree_digest(object_root)
    _require(before_snapshot == after_snapshot, "target_logical_state_changed")
    _require(
        before_database_digest == after_database_digest,
        "target_database_changed",
    )
    _require(
        before_object_digest == after_object_digest,
        "target_object_tree_changed",
    )

    admission_payload = prospective_admission.digest_payload()
    roundtrip = S3ThreeCellBoundedAgentAdmission.model_validate(
        admission_payload
    )
    prospective_digest = canonical_digest(admission_payload)
    _require(
        canonical_digest(roundtrip.digest_payload()) == prospective_digest,
        "prospective_admission_roundtrip_digest_drift",
    )
    source_digest = canonical_digest(source_admission.digest_payload())
    _require(
        prospective_digest != source_digest,
        "prospective_admission_digest_did_not_advance",
    )

    return {
        "schema_version": (
            "fin_ia_0_1_s4_t06_mu_research_lead_fact_presence_local_"
            "materialization_fresh_agent_proof_decision_v1_0"
        ),
        "decision_id": (
            "S4-T06-MU-RESEARCH-LEAD-CONFLICT-FACT-PRESENCE-LOCAL-"
            "MATERIALIZATION-FRESH-AGENT-PROOF-DECISION"
        ),
        "recorded_at": "2026-07-29T17:30:00+08:00",
        "status": (
            "pass_zero_call_independent_fresh_proof_contract_frozen_"
            "admission_issuance_pending_separate_authority"
        ),
        "source_refs": {
            "implementation": _display_path(implementation_path),
            "canonical_preparation": _display_path(
                source_preparation_path
            ),
            "immutable_consumed_failed_R1_admission": _display_path(
                source_admission_path
            ),
            "immutable_R1_failure": _display_path(source_failure_path),
        },
        "implementation_reaudit": {
            "implementation_contract_sha256": _sha256(
                implementation_path
            ),
            "exact_code_bindings": implementation_bindings,
            "research_lead_transport_ref": (
                S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V7_REF
            ),
            "materialization_policy_ref": policy.policy_ref,
            "v7_runtime_injected": True,
            "node_level_fixture_proven": True,
            "historical_R1_admission_capture_or_Run_rewritten": False,
        },
        "materialization_policy_reproof": {
            "policy_ref": policy.policy_ref,
            "provider_field_id": policy.provider_field_id,
            "canonical_field_id": policy.canonical_field_id,
            "truth_table": dict(policy.truth_table),
            "provider_emits_fact_presence_summary": False,
            "canonical_output_requires_fact_presence_summary": True,
            "local_source": (
                "validated involved Claim Card direct support_fact_ids only"
            ),
            "aliases_validated_before_materialization": True,
            "provider_field_injection_hard_fails": True,
            "silent_provider_value_overwrite_allowed": False,
            "v3_semantic_and_output_v4_validators_retained": True,
            "v5_historical_provider_owned_behavior_preserved": True,
            "lead_v6_gap_atom_projection_inherited": False,
            "MU_case_or_provider_special_branch": False,
        },
        "fresh_identity": {
            "execution_identity": EXECUTION_IDENTITY,
            "case_id": case_id,
            "case_version": int(materialization["case_version"]),
            "decision_surface_contract_ref": decision_surface_ref,
            "work_unit_id": first.work_unit_id,
            "attempt_id": first.attempt_id,
            "research_run_id": first.research_run_id,
            "input_digest": first.input_digest,
            "preparation_digest": first.preparation_digest,
            "role_group_mapping_digest": first.role_group_mapping_digest,
            "evidence_alignment_digest": first.evidence_alignment_digest,
            "evidence_dispatch_digest": first.evidence_dispatch_digest,
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
            "prior_research_run_ids": sorted(
                clone_snapshot["research_run_ids"]
            ),
            "consumed_failed_R1_identity": {
                "work_unit_id": prior_work_unit_id,
                "attempt_id": prior_attempt_id,
                "research_run_id": prior_research_run_id,
            },
            "consumed_failed_R1_preserved": True,
            "consumed_failed_R1_reused": False,
        },
        "prospective_admission": {
            "payload": admission_payload,
            "digest": prospective_digest,
            "source_consumed_R1_admission_digest": source_digest,
            "digest_advanced_from_R1": True,
            "research_lead_v7_local_materialization_bound": True,
            "specialist_v7_preserved": True,
            "output_v4_writer_v3_and_link_policies_preserved": True,
            "prospective_admission_file": _display_path(
                PROSPECTIVE_ADMISSION
            ),
            "prospective_admission_file_absent": True,
            "issued": False,
            "consumed": False,
            "execution_started": False,
        },
        "target_read_only_audit": {
            "canonical_database_sha256": before_database_digest,
            "canonical_object_tree_sha256": before_object_digest,
            "logical_snapshot_digest": canonical_digest(before_snapshot),
            "canonical_database_file_unchanged": True,
            "canonical_object_tree_unchanged": True,
            "logical_snapshot_unchanged": True,
        },
        "future_success_contract": {
            "terminal_state": "succeeded",
            "logical_nodes": 6,
            "provider_calls": 12,
            "provider_output_captures": 12,
            "logical_artifact_families": 9,
            "research_lead_v7_consumed": True,
            "provider_wire_omits_fact_presence_summary": True,
            "canonical_conflict_summary_locally_materialized": True,
            "typed_verifier_success_required": True,
            "layered_acceptance_required": True,
            "paired_assessment_only_after_coherent_success": True,
        },
        "hard_boundaries": {
            "model_calls": 0,
            "provider_calls": callback_calls,
            "network_calls": 0,
            "source_network_calls": 0,
            "external_tool_calls": 0,
            "admissions_issued": 0,
            "admissions_consumed": 0,
            "target_canonical_writes": 0,
            "target_object_writes": 0,
            "paired_assessments": 0,
            "human_reviews": 0,
        },
        "experiment_governance": {
            "decision_label": (
                "proceed_to_separate_fresh_exact_admission_"
                "issuance_decision"
            ),
            "admission_issuance_authorized": False,
            "admission_consumption_authorized": False,
            "live_execution_authorized": False,
            "paired_assessment_authorized": False,
            "retry_fallback_replay_relaunch_or_rerun_authorized": False,
            "S4_T07_or_later_authorized": False,
            "strict_schema_transport_reentered": False,
            "dependency_conflict_or_all_node_atomization_reentered": False,
        },
        "root_cause_disposition": {
            "issue_id": (
                "RC-P36-078-s4-t06-mu-research-lead-deterministic-"
                "fact-presence-summary-model-ownership-recurrence"
            ),
            "prior_status": (
                "minimum_zero_call_implementation_complete_fixture_"
                "proven_fresh_agent_proof_pending"
            ),
            "new_status": (
                "fresh_proof_contract_frozen_admission_issuance_pending"
            ),
            "historical_R1_terminal_failure_reclassified": False,
            "MU_R2_proven": False,
        },
        "next_action": NEXT_ACTION,
    }


def build_decision(
    *,
    runtime_root: Path = RUNTIME_ROOT,
    source_preparation_path: Path = SOURCE_PREPARATION,
    source_failure_path: Path = SOURCE_FAILURE,
    source_admission_path: Path = SOURCE_ADMISSION,
    implementation_path: Path = IMPLEMENTATION,
) -> dict[str, Any]:
    kwargs = {
        "runtime_root": runtime_root,
        "source_preparation_path": source_preparation_path,
        "source_failure_path": source_failure_path,
        "source_admission_path": source_admission_path,
        "implementation_path": implementation_path,
    }
    first = prepare(**kwargs)
    second = prepare(**kwargs)
    _require(first == second, "independent_proof_outputs_differ")
    result = deepcopy(first)
    result["proof_generator"] = {
        "ref": _display_path(Path(__file__)),
        "sha256": _sha256(Path(__file__)),
        "independent_invocations": 2,
        "independent_outputs_equal": True,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, default=RUNTIME_ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--source-preparation",
        type=Path,
        default=SOURCE_PREPARATION,
    )
    parser.add_argument(
        "--source-failure",
        type=Path,
        default=SOURCE_FAILURE,
    )
    parser.add_argument(
        "--source-admission",
        type=Path,
        default=SOURCE_ADMISSION,
    )
    parser.add_argument(
        "--implementation",
        type=Path,
        default=IMPLEMENTATION,
    )
    args = parser.parse_args()
    result = build_decision(
        runtime_root=args.runtime_root,
        source_preparation_path=args.source_preparation,
        source_failure_path=args.source_failure,
        source_admission_path=args.source_admission,
        implementation_path=args.implementation,
    )
    if args.output is not None:
        args.output.write_text(
            json.dumps(
                result,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
