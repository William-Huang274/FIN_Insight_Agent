from __future__ import annotations

import argparse
import hashlib
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
    S3_TASK_CLAIM_LINK_POLICY_REF,
)
from apps.workbench.backend.application.bounded_agent_executor import (
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
    "fin_ia_0_1_s4_t05_dell_evidence_role_group_mapping_repair_"
    "fresh_exact_admission_r2.json"
)
IMPLEMENTATION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_task_claim_link_policy_minimum_"
    "zero_call_implementation_v1_0.json"
)
PROSPECTIVE_ADMISSION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_task_claim_link_policy_"
    "fresh_exact_admission_r3.json"
)
EXECUTION_IDENTITY = (
    "fin01-s4-t05-dell-task-claim-link-policy-exact-live-r3"
)
PROSPECTIVE_ADMISSION_ID = (
    "fin01-s4-t05-dell-task-claim-link-policy-"
    "fresh-exact-admission-r3"
)
EXECUTION_MODE = "exact_live_s4_dell_task_claim_link_policy_r3"
PRIOR_FAILED_RUN_ID = "research_run_fin01_9756044e7d7f23b3ff9fb395"
NEXT_ACTION = (
    "S4-T05-DELL-WWC-TASK-TO-CLAIM-CLOSED-IDENTITY-"
    "FRESH-EXACT-ADMISSION-ISSUANCE-DECISION"
)


class S4T05TaskClaimFreshProofError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S4T05TaskClaimFreshProofError(code)


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
    implementation_path: Path = IMPLEMENTATION,
) -> dict[str, Any]:
    runtime_root = runtime_root.resolve()
    canonical_root = runtime_root / "canonical-runtime"
    database_path = canonical_root / "canonical.sqlite"
    object_root = canonical_root / "objects"
    source_decision = _load(source_decision_path)
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
    _require(
        source_admission.task_claim_link_policy_ref is None,
        "historical_source_admission_unexpectedly_mutated",
    )

    before_database_digest = _sha256(database_path)
    before_object_digest = _tree_digest(object_root)
    before_snapshot = _logical_snapshot(database_path, case_id)
    _require(
        PRIOR_FAILED_RUN_ID in before_snapshot["research_run_ids"],
        "immutable_prior_failed_run_missing",
    )

    binding = load_s4_case_runtime_binding(ROOT, "DELL")
    source_pack = load_s4_source_grounded_input_pack(ROOT, "DELL")
    mapping = compile_s4_case_evidence_role_group_mapping(binding)
    _require(
        [len(group.source_evidence_roles) for group in mapping.role_groups]
        == [4, 5, 5],
        "dell_role_group_shape_mismatch",
    )
    _require(mapping.exact_role_count == 14, "dell_exact_role_count_mismatch")

    with tempfile.TemporaryDirectory(
        prefix="fin01-s4-t05-task-claim-fresh-proof-"
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
        first.role_group_mapping_digest
        == mapping.role_group_mapping_digest,
        "prepared_mapping_digest_mismatch",
    )
    _require(
        bool(first.evidence_alignment_digest),
        "prepared_alignment_digest_missing",
    )
    _require(
        bool(first.evidence_dispatch_digest),
        "prepared_dispatch_digest_missing",
    )

    prospective_admission = source_admission.model_copy(
        update={
            "admission_id": PROSPECTIVE_ADMISSION_ID,
            "execution_mode": EXECUTION_MODE,
            "input_digest": first.input_digest,
            "task_claim_link_policy_ref": S3_TASK_CLAIM_LINK_POLICY_REF,
        }
    )
    prospective_admission.assert_profile_admissible()
    _require(
        prospective_admission.task_claim_link_policy_ref
        == S3_TASK_CLAIM_LINK_POLICY_REF,
        "prospective_admission_task_claim_policy_binding_missing",
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
    source_admission_payload = source_admission.digest_payload()
    prospective_digest = canonical_digest(admission_payload)
    source_digest = canonical_digest(source_admission_payload)
    _require(
        prospective_digest != source_digest,
        "prospective_admission_digest_did_not_advance",
    )
    return {
        "schema_version": (
            "fin_ia_0_1_s4_t05_task_claim_link_policy_"
            "fresh_agent_proof_decision_v1_0"
        ),
        "decision_id": (
            "S4-T05-DELL-WWC-TASK-TO-CLAIM-CLOSED-IDENTITY-"
            "FRESH-AGENT-PROOF-DECISION"
        ),
        "status": (
            "pass_zero_call_independent_fresh_proof_contract_frozen_"
            "admission_issuance_pending_separate_authority"
        ),
        "source_refs": {
            "implementation": _display_path(implementation_path),
            "source_materialization_decision": _display_path(
                source_decision_path
            ),
            "immutable_consumed_failed_admission": _display_path(
                source_admission_path
            ),
        },
        "implementation_reaudit": {
            "implementation_contract_sha256": _sha256(
                implementation_path
            ),
            "exact_code_bindings": implementation_bindings,
            "task_claim_link_policy_ref": S3_TASK_CLAIM_LINK_POLICY_REF,
            "runtime_injected": True,
            "node_level_fixture_proven": True,
            "historical_admission_or_Run_rewritten": False,
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
            "prior_failed_run_preserved": PRIOR_FAILED_RUN_ID,
            "prior_failed_run_reused": False,
        },
        "prospective_admission": {
            "payload": admission_payload,
            "digest": prospective_digest,
            "source_consumed_admission_digest": source_digest,
            "digest_advanced_from_source": True,
            "task_claim_link_policy_explicitly_bound": True,
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
            "all_three_WWC_segments_consume_task_claim_policy": True,
            "persisted_request_alias_residue": 0,
            "unknown_or_cross_Cell_task_claim_link_count": 0,
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
            "deferred_task_identity_or_taxonomy_work_reentered": False,
        },
        "root_cause_disposition": {
            "issue_id": (
                "RC-P36-059-s4-WWC-task-to-claim-open-identity-surface"
            ),
            "prior_status": (
                "minimum_shared_policy_runtime_injected_fixture_proven_"
                "fresh_agent_proof_pending"
            ),
            "new_status": (
                "fresh_proof_contract_frozen_admission_issuance_pending"
            ),
            "DELL_R2_proven": False,
        },
        "next_action": NEXT_ACTION,
    }


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
        "--implementation",
        type=Path,
        default=IMPLEMENTATION,
    )
    args = parser.parse_args()
    result = prepare(
        runtime_root=args.runtime_root,
        source_decision_path=args.source_decision,
        source_admission_path=args.source_admission,
        implementation_path=args.implementation,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
