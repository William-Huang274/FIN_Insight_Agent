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
    S3_SPECIALIST_WWC_JUDGMENT_ATOM_POLICY_REF,
    S4_DELL_THREE_CELL_RESEARCH_PROFILE_REF,
    S4_DELL_THREE_CELL_RESEARCH_PROFILE_V2_REF,
    SpecialistWWCJudgmentAtomPolicy,
    research_profile_for_ref,
    specialist_transport_contract,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V6_REF,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V8_REF,
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
SOURCE_DECISION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t04_dell_source_grounded_input_materialization_"
    "and_fresh_proof_decision_v1_0.json"
)
SOURCE_ADMISSION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_research_lead_gap_atom_projection_"
    "fresh_exact_admission_r5.json"
)
SOURCE_FAILURE = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_research_lead_gap_atom_projection_r5_"
    "exact_live_execution_failure_result_v1_0.json"
)
IMPLEMENTATION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_specialist_wwc_judgment_atom_deterministic_"
    "task_assembly_minimum_zero_call_implementation_v1_0.json"
)
DECISION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_specialist_wwc_judgment_atom_deterministic_"
    "assembly_fresh_agent_proof_decision_v1_0.json"
)
PROOF_TEST = (
    ROOT
    / "tests/contract/"
    "test_fin_0_1_s4_t05_specialist_wwc_judgment_atom_"
    "fresh_agent_proof_decision.py"
)
PROSPECTIVE_ADMISSION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_specialist_wwc_judgment_atom_"
    "fresh_exact_admission_r6.json"
)
EXECUTION_IDENTITY = (
    "fin01-s4-t05-dell-specialist-wwc-judgment-atom-exact-live-r6"
)
PROSPECTIVE_ADMISSION_ID = (
    "fin01-s4-t05-dell-specialist-wwc-judgment-atom-"
    "fresh-exact-admission-r6"
)
EXECUTION_MODE = "exact_live_s4_dell_specialist_wwc_judgment_atom_r6"
PRIOR_FAILED_RUN_IDS = (
    "research_run_fin01_9756044e7d7f23b3ff9fb395",
    "research_run_fin01_8905466e65d6259e54d42f6c",
    "research_run_fin01_9f2cc1412a2fd495db65b8b4",
    "research_run_fin01_3ce365aa075bacbc2cc31346",
)
NEXT_ACTION = (
    "S4-T05-DELL-SPECIALIST-WWC-JUDGMENT-ATOM-AND-DETERMINISTIC-"
    "TASK-ASSEMBLY-FRESH-EXACT-ADMISSION-ISSUANCE-DECISION"
)


class S4T05SpecialistWWCJudgmentAtomFreshProofError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S4T05SpecialistWWCJudgmentAtomFreshProofError(code)


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
    source_decision_path: Path = SOURCE_DECISION,
    source_admission_path: Path = SOURCE_ADMISSION,
    source_failure_path: Path = SOURCE_FAILURE,
    implementation_path: Path = IMPLEMENTATION,
) -> dict[str, Any]:
    runtime_root = runtime_root.resolve()
    canonical_root = runtime_root / "canonical-runtime"
    database_path = canonical_root / "canonical.sqlite"
    object_root = canonical_root / "objects"
    source_decision = _load(source_decision_path)
    source_failure = _load(source_failure_path)
    implementation = _load(implementation_path)
    source_admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        _load(source_admission_path)
    )
    materialization = source_decision["canonical_materialization"]
    case_id = str(materialization["case_id"])
    decision_surface_ref = str(
        materialization["decision_surface_contract_ref"]
    )

    _require(
        implementation["status"]
        == "pass_zero_call_implementation_fixture_proven_"
        "fresh_agent_proof_pending",
        "implementation_not_fixture_proven",
    )
    implementation_bindings = _verify_implementation_bindings(
        implementation
    )
    source_admission_digest = canonical_digest(
        source_admission.digest_payload()
    )
    _require(
        source_failure["admission"]["consumed"] is True
        and source_failure["admission"]["admission_digest"]
        == source_admission_digest,
        "immutable_R5_consumption_binding_mismatch",
    )
    _require(
        source_failure["terminal_result"]["artifact_count"] == 0
        and source_failure["identity"]["research_run_id"]
        == PRIOR_FAILED_RUN_IDS[-1],
        "immutable_R5_failure_truth_mismatch",
    )
    _require(
        source_admission.transport_ref
        == S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF
        and source_admission.research_profile_ref
        == S4_DELL_THREE_CELL_RESEARCH_PROFILE_REF
        and source_admission.wwc_judgment_atom_policy_ref is None,
        "immutable_R5_source_contract_mismatch",
    )

    v7_contract = specialist_transport_contract(
        S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF
    )
    v8_contract = specialist_transport_contract(
        S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V8_REF
    )
    profile_v2 = research_profile_for_ref(
        S4_DELL_THREE_CELL_RESEARCH_PROFILE_V2_REF
    )
    _require(
        not v7_contract.what_would_change_judgment_atom_assembly
        and v8_contract.what_would_change_judgment_atom_assembly,
        "v7_v8_WWC_atom_capability_boundary_mismatch",
    )
    _require(
        profile_v2.segment_token_budgets[
            "actionable_what_would_change_tasks"
        ]
        == 1800
        and profile_v2.stage_token_budgets(expanded_lead=True)[
            "specialist"
        ]
        == 4600
        and profile_v2.aggregate_output_tokens(expanded_lead=True)
        == 18000,
        "DELL_profile_v2_capacity_mismatch",
    )
    _require(
        SpecialistWWCJudgmentAtomPolicy.contract_ref
        == S3_SPECIALIST_WWC_JUDGMENT_ATOM_POLICY_REF
        and SpecialistWWCJudgmentAtomPolicy.provider_atom_minimum == 1
        and SpecialistWWCJudgmentAtomPolicy.provider_atom_maximum == 3
        and (
            SpecialistWWCJudgmentAtomPolicy
            .provider_atom_max_unicode_characters
        )
        == 160
        and SpecialistWWCJudgmentAtomPolicy.provider_output_max_utf8_bytes
        == 4800,
        "WWC_judgment_atom_policy_capacity_mismatch",
    )

    before_database_digest = _sha256(database_path)
    before_object_digest = _tree_digest(object_root)
    before_snapshot = _logical_snapshot(database_path, case_id)
    for prior_run_id in PRIOR_FAILED_RUN_IDS:
        _require(
            prior_run_id in before_snapshot["research_run_ids"],
            f"immutable_prior_failed_run_missing:{prior_run_id}",
        )

    binding = load_s4_case_runtime_binding(ROOT, "DELL")
    source_pack = load_s4_source_grounded_input_pack(ROOT, "DELL")
    mapping = compile_s4_case_evidence_role_group_mapping(binding)
    _require(
        [len(group.source_evidence_roles) for group in mapping.role_groups]
        == [4, 5, 5]
        and mapping.exact_role_count == 14,
        "DELL_role_group_mapping_mismatch",
    )

    with tempfile.TemporaryDirectory(
        prefix="fin01-s4-t05-WWC-atom-fresh-proof-"
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
        first.role_group_mapping_digest == mapping.role_group_mapping_digest,
        "prepared_mapping_digest_mismatch",
    )

    prospective_admission = source_admission.model_copy(
        update={
            "admission_id": PROSPECTIVE_ADMISSION_ID,
            "execution_mode": EXECUTION_MODE,
            "input_digest": first.input_digest,
            "transport_ref": (
                S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V8_REF
            ),
            "research_profile_ref": (
                S4_DELL_THREE_CELL_RESEARCH_PROFILE_V2_REF
            ),
            "wwc_judgment_atom_policy_ref": (
                S3_SPECIALIST_WWC_JUDGMENT_ATOM_POLICY_REF
            ),
            "specialist_max_output_tokens": 4600,
        }
    )
    prospective_admission.assert_profile_admissible()
    _require(
        prospective_admission.transport_ref
        == S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V8_REF
        and prospective_admission.research_profile_ref
        == S4_DELL_THREE_CELL_RESEARCH_PROFILE_V2_REF
        and prospective_admission.wwc_judgment_atom_policy_ref
        == S3_SPECIALIST_WWC_JUDGMENT_ATOM_POLICY_REF
        and prospective_admission.research_lead_transport_ref
        == S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V6_REF,
        "prospective_v8_profile_policy_or_lead_binding_missing",
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
    prospective_digest = canonical_digest(admission_payload)
    _require(
        prospective_digest != source_admission_digest,
        "prospective_admission_digest_did_not_advance",
    )
    return {
        "schema_version": (
            "fin_ia_0_1_s4_t05_specialist_wwc_judgment_atom_"
            "deterministic_assembly_fresh_agent_proof_decision_v1_0"
        ),
        "decision_id": (
            "S4-T05-DELL-SPECIALIST-WWC-JUDGMENT-ATOM-AND-"
            "DETERMINISTIC-TASK-ASSEMBLY-FRESH-AGENT-PROOF-DECISION"
        ),
        "recorded_at": "2026-07-27T20:00:00+08:00",
        "status": (
            "pass_zero_call_independent_fresh_proof_contract_frozen_"
            "admission_issuance_pending_separate_authority"
        ),
        "source_refs": {
            "implementation": _display_path(implementation_path),
            "source_materialization_decision": _display_path(
                source_decision_path
            ),
            "immutable_consumed_failed_R5_admission": _display_path(
                source_admission_path
            ),
            "immutable_R5_failure_result": _display_path(
                source_failure_path
            ),
        },
        "implementation_reaudit": {
            "implementation_contract_sha256": _sha256(
                implementation_path
            ),
            "exact_code_bindings": implementation_bindings,
            "policy_ref": S3_SPECIALIST_WWC_JUDGMENT_ATOM_POLICY_REF,
            "specialist_transport_ref": (
                S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V8_REF
            ),
            "research_profile_ref": (
                S4_DELL_THREE_CELL_RESEARCH_PROFILE_V2_REF
            ),
            "runtime_injected": True,
            "node_level_fixture_proven": True,
            "historical_R5_admission_capture_Run_or_failure_rewritten": False,
        },
        "exact_code_bindings": implementation_bindings,
        "WWC_judgment_atom_reproof": {
            "policy_ref": S3_SPECIALIST_WWC_JUDGMENT_ATOM_POLICY_REF,
            "provider_top_level_field": "what_would_change_judgment_atoms",
            "provider_atom_cardinality": "1..3",
            "provider_atom_narrative_maximum_unicode_characters": 160,
            "provider_output_maximum_utf8_bytes": 4800,
            "WWC_segment_output_tokens": 1800,
            "specialist_stage_output_tokens": 4600,
            "full_chain_output_tokens": 18000,
            "provider_emits_task_id_raw_refs_source_target_or_as_of": False,
            "local_assembly_owns_identity_authority_as_of_and_lineage": True,
            "v7_historical_provider_wire_preserved": True,
            "DELL_case_or_provider_special_branch": False,
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
            "prior_failed_run_ids_preserved": list(PRIOR_FAILED_RUN_IDS),
            "prior_failed_run_reused": False,
        },
        "prospective_admission": {
            "payload": admission_payload,
            "digest": prospective_digest,
            "source_consumed_R5_admission_digest": source_admission_digest,
            "digest_advanced_from_R5": True,
            "specialist_v8_bound": True,
            "DELL_profile_v2_bound": True,
            "WWC_judgment_atom_policy_bound": True,
            "research_lead_v6_and_prior_link_policies_preserved": True,
            "prospective_admission_file": _display_path(
                PROSPECTIVE_ADMISSION
            ),
            "prospective_admission_file_absent": True,
            "issued": False,
            "consumed": False,
            "execution_started": False,
        },
        "target_read_only_audit": {
            "canonical_object_tree_sha256": before_object_digest,
            "logical_snapshot_digest": canonical_digest(before_snapshot),
            "canonical_database_file_unchanged": True,
            "canonical_database_physical_hash_identity_bearing": False,
            "canonical_object_tree_unchanged": True,
            "logical_snapshot_unchanged": True,
        },
        "future_success_contract": {
            "terminal_state": "succeeded",
            "logical_nodes": 6,
            "provider_calls": 12,
            "logical_artifact_families": 9,
            "all_three_specialist_WWC_segments_consume_v8_atom_policy": True,
            "research_lead_v6_consumed": True,
            "gap_projection_live_observed": True,
            "canonical_atom_or_request_alias_residue": 0,
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
            "S4_T06_or_later_authorized": False,
            "dependency_conflict_Writer_Verifier_or_all_node_atomization_"
            "reentered": False,
        },
        "root_cause_disposition": {
            "issue_id": (
                "RC-P36-062-s4-specialist-v7-WWC-segment-output-"
                "truncation-recurrence"
            ),
            "prior_status": (
                "implementation_fixture_proven_fresh_agent_proof_pending"
            ),
            "new_status": (
                "fresh_proof_contract_frozen_admission_issuance_pending"
            ),
            "RC_P36_061_status": (
                "R5_consumed_failed_upstream_projection_"
                "live_observation_unproven"
            ),
            "historical_R5_terminal_failure_reclassified": False,
            "DELL_R2_proven": False,
        },
        "next_action": NEXT_ACTION,
    }


def build_decision(
    *,
    runtime_root: Path = RUNTIME_ROOT,
    source_decision_path: Path = SOURCE_DECISION,
    source_admission_path: Path = SOURCE_ADMISSION,
    source_failure_path: Path = SOURCE_FAILURE,
    implementation_path: Path = IMPLEMENTATION,
) -> dict[str, Any]:
    kwargs = {
        "runtime_root": runtime_root,
        "source_decision_path": source_decision_path,
        "source_admission_path": source_admission_path,
        "source_failure_path": source_failure_path,
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
    result["proof_contract_test"] = {
        "ref": _display_path(PROOF_TEST),
        "sha256": _sha256(PROOF_TEST),
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, default=RUNTIME_ROOT)
    parser.add_argument(
        "--source-decision",
        type=Path,
        default=SOURCE_DECISION,
    )
    parser.add_argument(
        "--source-admission",
        type=Path,
        default=SOURCE_ADMISSION,
    )
    parser.add_argument(
        "--source-failure",
        type=Path,
        default=SOURCE_FAILURE,
    )
    parser.add_argument(
        "--implementation",
        type=Path,
        default=IMPLEMENTATION,
    )
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()
    result = build_decision(
        runtime_root=args.runtime_root,
        source_decision_path=args.source_decision,
        source_admission_path=args.source_admission,
        source_failure_path=args.source_failure,
        implementation_path=args.implementation,
    )
    rendered = json.dumps(
        result,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
