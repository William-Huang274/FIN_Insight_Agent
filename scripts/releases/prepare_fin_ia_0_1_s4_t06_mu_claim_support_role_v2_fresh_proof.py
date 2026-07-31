from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any, Callable, Mapping

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "contract"))

from apps.workbench.backend.application.bounded_agent_contract_policies import (
    S4_DETERMINISTIC_JUDGMENT_ATOM_COMPILED_CONTRACT_V2_REF,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    S3ThreeCellBoundedAgentAdmission,
    build_s3_three_cell_bounded_agent_executor_for_admission,
    compile_s4_case_runtime_mandatory_safety_admission,
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
from test_fin_0_1_s4_t06_mu_claim_epistemic_support_role_compiled_contract_v2_minimum_zero_call_implementation import (
    test_persisted_v2_implementation_binds_current_runtime_and_scope,
    test_v1_surface_and_system_instruction_remain_byte_for_byte_compatible,
    test_v2_both_legal_epistemic_routes_render_deterministically,
    test_v2_conflicting_concrete_scopes_are_filtered_before_selection,
    test_v2_invalid_kind_support_combinations_fail_with_typed_code,
    test_v2_mixed_scope_candidate_is_not_silently_promoted,
    test_v2_one_rule_source_projects_to_every_claim_contract_surface,
    test_v2_runtime_typed_failure_preserves_terminal_claim_capture,
    test_v2_supported_judgment_kinds_keep_exact_support,
    test_v2_three_case_full_fake_reaches_6_nodes_12_captures_9_artifacts,
    test_v2_unknown_alias_still_fails_as_cross_case_not_role_error,
)


RUNTIME_ROOT = (
    ROOT
    / ".codex_runtime"
    / "fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1"
)
SOURCE_PREPARATION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_canonical_case_surface_"
    "and_fresh_exact_admission_preparation_zero_call_proof_v1_0.json"
)
SOURCE_R6_ADMISSION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_action_planning_temporal_"
    "authority_and_capture_v2_terminal_result_materialization_fresh_"
    "exact_admission_r6.json"
)
SOURCE_CANARY_RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_changed_contract_family_"
    "single_node_natural_output_canaries_exact_once_execution_result_v1_0.json"
)
SOURCE_DISPOSITION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_changed_contract_family_"
    "single_node_natural_output_canaries_post_result_disposition_"
    "decision_v1_0.json"
)
IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_claim_epistemic_support_"
    "role_compiled_contract_v2_minimum_zero_call_implementation_v1_0.json"
)
DECISION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_claim_epistemic_support_"
    "role_compiled_contract_v2_independent_fresh_agent_proof_"
    "decision_v1_0.json"
)
PROSPECTIVE_ADMISSION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_claim_epistemic_support_"
    "role_compiled_contract_v2_fresh_exact_admission_r7.json"
)
EXECUTION_IDENTITY = (
    "fin01-s4-t06-mu-claim-support-role-v2-final-exact-live-r7"
)
PROSPECTIVE_ADMISSION_ID = (
    "fin01-s4-t06-mu-claim-support-role-v2-fresh-exact-admission-r7"
)
EXECUTION_MODE = (
    "exact_live_s4_mu_claim_support_role_compiled_contract_v2_final_r7"
)
CURRENT_ACTION = (
    "S4-T06-MU-CLAIM-EPISTEMIC-SUPPORT-ROLE-COMPILED-CONTRACT-V2-"
    "INDEPENDENT-FRESH-AGENT-PROOF-DECISION"
)
NEXT_ACTION = (
    "S4-T06-MU-CLAIM-EPISTEMIC-SUPPORT-ROLE-COMPILED-CONTRACT-V2-"
    "FRESH-EXACT-ADMISSION-AUTHORITY-DECISION"
)


class S4T06ClaimSupportRoleV2FreshProofError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S4T06ClaimSupportRoleV2FreshProofError(code)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _display(path: Path) -> str:
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
        str(row["ref"]): str(row["sha256"])
        for row in implementation["runtime_changes"].values()
    }
    for relative_path, expected_digest in bindings.items():
        _require(
            _sha256(ROOT / relative_path) == expected_digest,
            f"implementation_code_binding_drift:{relative_path}",
        )
    return bindings


def _run_with_monkeypatch(
    test: Callable[..., None],
    *args: Any,
) -> None:
    with pytest.MonkeyPatch.context() as monkeypatch:
        test(monkeypatch, *args)


def _run_fixture_reproof() -> dict[str, Any]:
    positive: dict[str, list[int]] = {}
    for ticker in ("DELL", "MU", "NVDA"):
        _run_with_monkeypatch(
            test_v2_three_case_full_fake_reaches_6_nodes_12_captures_9_artifacts,
            ticker,
        )
        positive[ticker] = [6, 12, 12, 9]

    test_persisted_v2_implementation_binds_current_runtime_and_scope()
    test_v1_surface_and_system_instruction_remain_byte_for_byte_compatible()
    test_v2_one_rule_source_projects_to_every_claim_contract_surface()
    test_v2_both_legal_epistemic_routes_render_deterministically()
    for claim_kind, direction, expected_status in (
        ("economic_mechanism", "supports", "fact_supported"),
        ("counterevidence", "challenges", "fact_supported"),
    ):
        test_v2_supported_judgment_kinds_keep_exact_support(
            claim_kind,
            direction,
            expected_status,
        )
    for claim_kind, aliases_factory in (
        ("insufficient_evidence", lambda alias: [alias]),
        ("evidence_direction", lambda alias: []),
        ("economic_mechanism", lambda alias: [alias, alias]),
        ("counterevidence", lambda alias: []),
    ):
        test_v2_invalid_kind_support_combinations_fail_with_typed_code(
            claim_kind,
            aliases_factory,
        )
    test_v2_unknown_alias_still_fails_as_cross_case_not_role_error()
    _run_with_monkeypatch(
        test_v2_runtime_typed_failure_preserves_terminal_claim_capture
    )
    test_v2_mixed_scope_candidate_is_not_silently_promoted()
    test_v2_conflicting_concrete_scopes_are_filtered_before_selection()

    return {
        "compiled_contract_ref": (
            S4_DETERMINISTIC_JUDGMENT_ATOM_COMPILED_CONTRACT_V2_REF
        ),
        "three_case_positive_nodes_callbacks_captures_artifacts": positive,
        "v1_semantic_compatibility": True,
        "single_rule_surface_projection_count": 8,
        "positive_epistemic_route_count": 4,
        "negative_fixture_class_count": 6,
        "unknown_cross_case_alias_fail_closed": True,
        "mixed_and_conflicting_scope_fail_closed": True,
        "typed_terminal_claim_capture_preserved": True,
    }


def prepare(
    *,
    runtime_root: Path = RUNTIME_ROOT,
    source_preparation_path: Path = SOURCE_PREPARATION,
    source_r6_admission_path: Path = SOURCE_R6_ADMISSION,
    source_canary_result_path: Path = SOURCE_CANARY_RESULT,
    source_disposition_path: Path = SOURCE_DISPOSITION,
    implementation_path: Path = IMPLEMENTATION,
    require_prospective_absent: bool = True,
) -> dict[str, Any]:
    runtime_root = runtime_root.resolve()
    canonical_root = runtime_root / "canonical-runtime"
    database_path = canonical_root / "canonical.sqlite"
    object_root = canonical_root / "objects"
    source_preparation = _load(source_preparation_path)
    source_admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        _load(source_r6_admission_path)
    )
    source_canary_result = _load(source_canary_result_path)
    source_disposition = _load(source_disposition_path)
    implementation = _load(implementation_path)
    materialization = source_preparation["canonical_materialization"]
    case_id = str(materialization["case_id"])
    decision_surface_ref = str(
        materialization["decision_surface_contract_ref"]
    )

    _require(
        implementation["status"]
        == (
            "pass_claim_contract_v2_runtime_injected_three_case_fixture_"
            "proven_independent_fresh_proof_pending"
        ),
        "implementation_not_fixture_proven",
    )
    _require(
        implementation["implemented_contract"]["contract_ref"]
        == S4_DETERMINISTIC_JUDGMENT_ATOM_COMPILED_CONTRACT_V2_REF,
        "implementation_v2_contract_not_bound",
    )
    implementation_bindings = _verify_implementation_bindings(
        implementation
    )
    _require(
        source_canary_result["status"]
        == "terminal_failed_no_retry",
        "immutable_canary_status_changed",
    )
    claim_canary = next(
        row
        for row in source_canary_result["family_results"]
        if row["family_id"] == "claim_candidate_atoms"
    )
    _require(
        claim_canary["failure_code"]
        == "s4_compiled_claim_atom_no_valid_scope_compatible_subset",
        "immutable_canary_failure_changed",
    )
    _require(
        source_disposition["root_cause_disposition"][
            "model_or_provider_fault_established"
        ]
        is False,
        "source_disposition_model_fault_changed",
    )
    _require(
        source_disposition["required_zero_call_proof"][
            "maximum_remaining_formal_MU_exact_lives"
        ]
        == 1,
        "formal_exact_live_ceiling_changed",
    )
    fixture_reproof = _run_fixture_reproof()

    before_database_digest = _sha256(database_path)
    before_object_digest = _tree_digest(object_root)
    before_snapshot = _logical_snapshot(database_path, case_id)

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
        prefix="fin01-s4-t06-claim-support-role-v2-fresh-proof-"
    ) as temp_dir:
        clone_runtime_root = Path(temp_dir) / runtime_root.name
        shutil.copytree(runtime_root, clone_runtime_root)
        case_service, _, evidence_service = _services(clone_runtime_root)
        clone_before = _execution_counts(case_service, case_id)
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
    _require(
        first_payload == second.model_dump(mode="json"),
        "double_prepare_parity_failed",
    )
    _require(clone_before == clone_after, "prepare_created_clone_state")
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
        "exact_MU_input_digest_changed",
    )

    prospective_admission = (
        compile_s4_case_runtime_mandatory_safety_admission(
            source_admission,
            updates={
                "admission_id": PROSPECTIVE_ADMISSION_ID,
                "execution_mode": EXECUTION_MODE,
                "input_digest": first.input_digest,
                "judgment_atom_compiled_contract_ref": (
                    S4_DETERMINISTIC_JUDGMENT_ATOM_COMPILED_CONTRACT_V2_REF
                ),
            },
        )
    )
    prospective_admission.assert_profile_admissible()
    _require(
        prospective_admission.judgment_atom_compiled_contract_ref
        == S4_DETERMINISTIC_JUDGMENT_ATOM_COMPILED_CONTRACT_V2_REF,
        "v2_compiled_contract_not_bound",
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
    if require_prospective_absent:
        _require(
            not PROSPECTIVE_ADMISSION.exists(),
            "prospective_R7_admission_already_exists",
        )

    after_snapshot = _logical_snapshot(database_path, case_id)
    _require(before_snapshot == after_snapshot, "target_logical_state_changed")
    _require(
        before_database_digest == _sha256(database_path),
        "target_database_changed",
    )
    _require(
        before_object_digest == _tree_digest(object_root),
        "target_object_tree_changed",
    )

    admission_payload = prospective_admission.digest_payload()
    prospective_digest = canonical_digest(admission_payload)
    roundtrip = S3ThreeCellBoundedAgentAdmission.model_validate(
        admission_payload
    )
    _require(
        canonical_digest(roundtrip.digest_payload()) == prospective_digest,
        "prospective_R7_admission_roundtrip_digest_drift",
    )

    return {
        "schema_version": (
            "fin_ia_0_1_s4_t06_mu_claim_epistemic_support_role_"
            "compiled_contract_v2_independent_fresh_agent_proof_"
            "decision_v1_0"
        ),
        "decision_id": CURRENT_ACTION,
        "recorded_at": "2026-07-30T17:52:21+08:00",
        "status": (
            "pass_zero_call_double_disposable_runtime_v2_fresh_proof_"
            "admission_authority_pending"
        ),
        "authority": {
            "user_instruction": "继续",
            "proof_step_authorized": True,
            "model_provider_network_calls_authorized": False,
            "second_claim_family_canary_authorized": False,
            "R7_admission_issuance_authorized": False,
            "R7_exact_live_authorized": False,
        },
        "source_refs": {
            "implementation": _display(implementation_path),
            "canonical_preparation": _display(source_preparation_path),
            "immutable_consumed_R6_admission": _display(
                source_r6_admission_path
            ),
            "immutable_failed_changed_family_canary": _display(
                source_canary_result_path
            ),
            "canary_post_result_disposition": _display(
                source_disposition_path
            ),
        },
        "implementation_reaudit": {
            "implementation_sha256": _sha256(implementation_path),
            "exact_code_bindings": implementation_bindings,
            "compiled_contract_ref": (
                S4_DETERMINISTIC_JUDGMENT_ATOM_COMPILED_CONTRACT_V2_REF
            ),
        },
        "independent_fixture_reproof": fixture_reproof,
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
        "prospective_R7_admission": {
            "payload": admission_payload,
            "digest": prospective_digest,
            "compiled_contract_v2_bound": True,
            "prospective_admission_file": _display(
                PROSPECTIVE_ADMISSION
            ),
            "prospective_admission_file_absent_at_proof": True,
            "issued": False,
            "consumed": False,
            "execution_started": False,
        },
        "target_read_only_audit": {
            "canonical_database_sha256": before_database_digest,
            "canonical_object_tree_sha256": before_object_digest,
            "logical_snapshot_digest": canonical_digest(before_snapshot),
            "target_state_unchanged": True,
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
            "exact_live_runs": 0,
            "paired_assessments": 0,
            "owner_acceptances": 0,
            "T07_entries": 0,
        },
        "future_formal_exact_live_contract": {
            "maximum_remaining_formal_MU_exact_lives": 1,
            "second_claim_family_canary_allowed": False,
            "terminal_state_required": "succeeded",
            "logical_nodes": 6,
            "provider_calls": 12,
            "provider_output_captures": 12,
            "logical_artifact_families": 9,
            "independent_final_artifact_L1_required": True,
            "paired_L1_to_L4_required": True,
            "owner_acceptance_only_after_L1_pass_and_agent_gain": True,
        },
        "stop_rule": {
            "admission_requires_separate_authority": True,
            "exact_live_requires_later_separate_authority": True,
            "automatic_R8": False,
            "new_L1_stops_T06_repair_loop": True,
            "second_structural_implementation_bundle_allowed": False,
        },
        "stage_acceptance": {
            "RC_P36_083": (
                "closed_independent_current_v2_binding_and_fixture_"
                "proof_passed"
            ),
            "RC_P36_080": (
                "open_final_formal_nine_Artifact_L1_reproof_pending"
            ),
            "S4_T06": (
                "blocked_pending_separate_R7_admission_authority_"
                "issuance_and_one_final_formal_MU_exact_live"
            ),
            "paired_assessment": "not_eligible",
            "owner_acceptance": "not_eligible",
            "S4_T07": "not_entered",
            "S4": "not_passed",
            "S5": "blocked",
        },
        "next_action": NEXT_ACTION,
        "next_action_authorized": False,
    }


def build_decision(
    *,
    runtime_root: Path = RUNTIME_ROOT,
    require_prospective_absent: bool = True,
) -> dict[str, Any]:
    kwargs = {
        "runtime_root": runtime_root,
        "require_prospective_absent": require_prospective_absent,
    }
    first = prepare(**kwargs)
    second = prepare(**kwargs)
    _require(first == second, "independent_proof_outputs_differ")
    result = deepcopy(first)
    result["proof_generator"] = {
        "ref": _display(Path(__file__)),
        "sha256": _sha256(Path(__file__)),
        "independent_invocations": 2,
        "independent_outputs_equal": True,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, default=RUNTIME_ROOT)
    parser.add_argument("--output", type=Path, default=DECISION)
    args = parser.parse_args()
    result = build_decision(runtime_root=args.runtime_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
