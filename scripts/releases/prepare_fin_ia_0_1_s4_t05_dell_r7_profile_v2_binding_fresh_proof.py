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

from apps.workbench.backend.app import create_app
from apps.workbench.backend.application.bounded_agent_executor import (
    S3ThreeCellBoundedAgentAdmission,
    build_s3_three_cell_bounded_agent_executor_for_admission,
    resolve_s4_case_runtime_binding_for_admission,
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
    _read_only_execution_rows,
    _services,
    load_execution_target,
)
from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.s4_case_runtime import load_s4_source_grounded_input_pack


RUNTIME_ROOT = ROOT / (
    ".codex_runtime/"
    "fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1"
)
R6_ADMISSION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_specialist_wwc_judgment_"
    "atom_fresh_exact_admission_r6.json"
)
R6_ISSUANCE = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_specialist_wwc_judgment_atom_"
    "deterministic_assembly_fresh_exact_admission_issuance_v1_0.json"
)
R6_FAILURE = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_specialist_wwc_judgment_"
    "atom_r6_exact_live_execution_pre_admission_failure_result_v1_0.json"
)
IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_r7_profile_v2_versioned_"
    "case_runtime_binding_and_create_app_preflight_minimum_zero_call_"
    "implementation_v1_0.json"
)
DECISION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_r7_profile_v2_binding_"
    "fresh_agent_proof_decision_v1_0.json"
)
PROSPECTIVE_ADMISSION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_r7_profile_v2_binding_"
    "fresh_exact_admission_r7.json"
)
PROOF_TEST = ROOT / (
    "tests/contract/test_fin_0_1_s4_t05_dell_r7_profile_v2_binding_"
    "fresh_agent_proof_decision.py"
)
EXECUTION_IDENTITY = (
    "fin01-s4-t05-dell-r7-profile-v2-binding-exact-live-r7"
)
PROSPECTIVE_ADMISSION_ID = (
    "fin01-s4-t05-dell-r7-profile-v2-binding-fresh-exact-admission-r7"
)
EXECUTION_MODE = "exact_live_s4_dell_r7_profile_v2_binding_r7"
NEXT_ACTION = (
    "S4-T05-DELL-R7-PROFILE-V2-BINDING-FRESH-EXACT-ADMISSION-"
    "ISSUANCE-DECISION"
)


class S4T05DellR7FreshProofError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S4T05DellR7FreshProofError(code)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _display(path: Path) -> str:
    resolved = path.resolve()
    return (
        resolved.relative_to(ROOT).as_posix()
        if resolved.is_relative_to(ROOT)
        else str(resolved)
    )


def _counts(runtime_root: Path, case_id: str) -> dict[str, int]:
    rows = _read_only_execution_rows(runtime_root, case_id)
    return {key: len(value) for key, value in rows.items()}


def _verify_implementation(
    implementation: Mapping[str, Any],
) -> dict[str, str]:
    _require(
        implementation["status"]
        == "pass_zero_call_versioned_profile_overlay_shared_resolver_and_"
        "create_app_preflight_fixture_proven_fresh_agent_proof_pending",
        "R7_binding_implementation_not_fixture_proven",
    )
    bindings = {
        str(path): str(digest)
        for path, digest in implementation["exact_code_bindings"].items()
    }
    for relative_path, expected_digest in bindings.items():
        _require(
            _sha256(ROOT / relative_path) == expected_digest,
            f"R7_binding_implementation_code_drift:{relative_path}",
        )
    return bindings


def prepare(
    *,
    runtime_root: Path = RUNTIME_ROOT,
    r6_admission_path: Path = R6_ADMISSION,
    r6_issuance_path: Path = R6_ISSUANCE,
    r6_failure_path: Path = R6_FAILURE,
    implementation_path: Path = IMPLEMENTATION,
) -> dict[str, Any]:
    runtime_root = runtime_root.resolve()
    implementation = _load(implementation_path)
    exact_bindings = _verify_implementation(implementation)
    r6 = S3ThreeCellBoundedAgentAdmission.model_validate(
        _load(r6_admission_path)
    )
    r6_failure = _load(r6_failure_path)
    r6_target = load_execution_target(r6_issuance_path)
    r6_digest = canonical_digest(r6.digest_payload())
    _require(
        r6_failure["admission"]["admission_digest"] == r6_digest
        and r6_failure["admission"]["consumed"] is False
        and r6_failure["terminal_result"]["artifact_count"] == 0,
        "immutable_R6_failure_truth_mismatch",
    )
    _require(
        r6_failure["first_credible_failure"]["failure_code"]
        == "s4_admission_research_profile_binding_mismatch",
        "immutable_R6_failure_code_mismatch",
    )

    provisional = r6.model_copy(
        update={
            "admission_id": PROSPECTIVE_ADMISSION_ID,
            "execution_mode": EXECUTION_MODE,
        }
    )
    effective_binding, overlay = (
        resolve_s4_case_runtime_binding_for_admission(ROOT, provisional)
    )
    _require(overlay is not None, "R7_profile_overlay_missing")
    source_pack = load_s4_source_grounded_input_pack(ROOT, "DELL")
    case_id = str(r6.case_id)
    database_path = runtime_root / "canonical-runtime/canonical.sqlite"
    object_root = runtime_root / "canonical-runtime/objects"
    before_database_digest = _sha256(database_path)
    before_object_digest = _tree_digest(object_root)
    before_snapshot = _logical_snapshot(database_path, case_id)
    before_counts = _counts(runtime_root, case_id)

    provider_calls = 0

    def _forbidden_provider(**_: Any) -> dict[str, Any]:
        nonlocal provider_calls
        provider_calls += 1
        raise AssertionError("provider_forbidden_in_R7_fresh_proof")

    with tempfile.TemporaryDirectory(
        prefix="fin01-s4-t05-dell-r7-fresh-proof-"
    ) as temp_dir:
        clone_root = Path(temp_dir) / runtime_root.name
        shutil.copytree(runtime_root, clone_root)
        case_service, local_service, evidence_service = _services(clone_root)
        clone_before = _counts(clone_root, case_id)
        first = prepare_s4_source_grounded_exact_input(
            case_service,
            evidence_service,
            effective_binding,
            source_pack,
            case_id,
            _principal(),
            decision_surface_contract_ref=r6_target.decision_surface_ref,
            execution_identity=EXECUTION_IDENTITY,
            research_profile_overlay=overlay,
        )
        second = prepare_s4_source_grounded_exact_input(
            case_service,
            evidence_service,
            effective_binding,
            source_pack,
            case_id,
            _principal(),
            decision_surface_contract_ref=r6_target.decision_surface_ref,
            execution_identity=EXECUTION_IDENTITY,
            research_profile_overlay=overlay,
        )
        _require(
            first.model_dump(mode="json") == second.model_dump(mode="json"),
            "R7_double_prepare_parity_failed",
        )
        prospective = provisional.model_copy(
            update={"input_digest": first.input_digest}
        )
        prospective.assert_profile_admissible()
        executor = build_s3_three_cell_bounded_agent_executor_for_admission(
            prospective,
            chat_completion_fn=_forbidden_provider,
        )
        create_app(
            clone_root / "fresh-proof-workbench.sqlite",
            p02_case_service=case_service,
            p03_evidence_service=evidence_service,
            p36_local_research_service=local_service,
            s3_three_cell_bounded_agent_admission=prospective,
            s3_three_cell_bounded_agent_executor=executor,
        )
        clone_after = _counts(clone_root, case_id)

    _require(provider_calls == 0, "provider_called_in_R7_fresh_proof")
    _require(clone_before == clone_after, "R7_fresh_proof_created_state")
    _require(
        first.input_digest != r6.input_digest,
        "R7_input_digest_reused_R6_stale_input",
    )
    _require(
        first.work_unit_id not in before_snapshot["work_unit_ids"]
        and first.attempt_id not in before_snapshot["attempt_ids"]
        and first.research_run_id not in before_snapshot["research_run_ids"],
        "R7_fresh_identity_reused",
    )
    _require(
        not PROSPECTIVE_ADMISSION.exists(),
        "R7_prospective_admission_already_exists",
    )
    after_snapshot = _logical_snapshot(database_path, case_id)
    _require(
        before_snapshot == after_snapshot
        and before_database_digest == _sha256(database_path)
        and before_object_digest == _tree_digest(object_root),
        "R7_fresh_proof_changed_target_runtime",
    )

    admission_payload = prospective.digest_payload()
    admission_digest = canonical_digest(admission_payload)
    return {
        "schema_version": (
            "fin_ia_0_1_s4_t05_dell_r7_profile_v2_binding_"
            "fresh_agent_proof_decision_v1_0"
        ),
        "decision_id": (
            "S4-T05-DELL-R7-PROFILE-V2-BINDING-FRESH-AGENT-"
            "PROOF-DECISION-R1"
        ),
        "recorded_at": "2026-07-27T23:30:00+08:00",
        "status": (
            "pass_zero_call_independent_R7_profile_v2_binding_"
            "fresh_proof_admission_issuance_pending"
        ),
        "source_refs": {
            "implementation": _display(implementation_path),
            "immutable_R6_admission": _display(r6_admission_path),
            "immutable_R6_issuance": _display(r6_issuance_path),
            "immutable_R6_failure": _display(r6_failure_path),
        },
        "implementation_reaudit": {
            "implementation_sha256": _sha256(implementation_path),
            "exact_code_bindings": exact_bindings,
            "effective_runtime_binding_digest": (
                effective_binding.runtime_binding_digest
            ),
            "overlay_digest": overlay.overlay_digest,
            "research_profile_contract_digest": (
                overlay.research_profile_contract_digest
            ),
            "shared_resolver_and_create_app_path_passed": True,
        },
        "fresh_identity": {
            "execution_identity": EXECUTION_IDENTITY,
            "case_id": case_id,
            "case_version": int(r6.case_version or 0),
            "decision_surface_contract_ref": r6_target.decision_surface_ref,
            "work_unit_id": first.work_unit_id,
            "attempt_id": first.attempt_id,
            "research_run_id": first.research_run_id,
            "input_digest": first.input_digest,
            "preparation_digest": first.preparation_digest,
            "role_group_mapping_digest": first.role_group_mapping_digest,
            "evidence_alignment_digest": first.evidence_alignment_digest,
            "evidence_dispatch_digest": first.evidence_dispatch_digest,
        },
        "double_prepare_and_create_app": {
            "equal": True,
            "prepared_payload_digest": canonical_digest(
                first.model_dump(mode="json")
            ),
            "clone_counts_before": clone_before,
            "clone_counts_after": clone_after,
            "provider_callback_calls": provider_calls,
            "canonical_writes": 0,
        },
        "freshness_and_nonreuse": {
            "target_counts_before": before_counts,
            "work_unit_absent": True,
            "attempt_absent": True,
            "research_run_absent": True,
            "prior_research_run_ids_preserved": sorted(
                before_snapshot["research_run_ids"]
            ),
            "R6_admission_consumed": False,
            "R6_rebound_or_reused": False,
        },
        "prospective_admission": {
            "payload": admission_payload,
            "digest": admission_digest,
            "source_R6_admission_digest": r6_digest,
            "source_R6_input_digest": r6.input_digest,
            "input_digest_advanced_from_R6": True,
            "prospective_admission_ref": _display(PROSPECTIVE_ADMISSION),
            "issued": False,
            "consumed": False,
            "execution_started": False,
        },
        "future_exact_live_contract": {
            "terminal_state": "succeeded_or_typed_failed",
            "maximum_semantic_model_calls": 12,
            "maximum_provider_calls": 12,
            "maximum_output_tokens": 18000,
            "maximum_total_cost_usd": 0.10,
            "transport_retry_count": 0,
            "success_artifact_count": 9,
            "success_only_paired_assessment": True,
        },
        "hard_boundaries": {
            "model_calls": 0,
            "provider_calls": provider_calls,
            "network_calls": 0,
            "source_network_calls": 0,
            "external_tool_calls": 0,
            "admissions_issued": 0,
            "admissions_consumed": 0,
            "target_canonical_writes": 0,
            "paired_assessments": 0,
        },
        "stage_acceptance": {
            "RC_P36_063": "fresh_proof_pass_admission_issuance_pending",
            "RC_P36_062": "live_unproven",
            "RC_P36_061": "live_unproven",
            "DELL_R2": "not_proven",
            "S4_T06": "not_entered",
        },
        "next_action": NEXT_ACTION,
    }


def build_decision(**kwargs: Any) -> dict[str, Any]:
    first = prepare(**kwargs)
    second = prepare(**kwargs)
    _require(first == second, "independent_R7_proof_outputs_differ")
    result = deepcopy(first)
    result["proof_generator"] = {
        "ref": _display(Path(__file__)),
        "sha256": _sha256(Path(__file__)),
        "independent_invocations": 2,
        "independent_outputs_equal": True,
    }
    result["proof_contract_test"] = {
        "ref": _display(PROOF_TEST),
        "sha256": _sha256(PROOF_TEST),
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, default=RUNTIME_ROOT)
    parser.add_argument("--output-json", type=Path, default=DECISION)
    args = parser.parse_args()
    result = build_decision(runtime_root=args.runtime_root)
    rendered = json.dumps(
        result, ensure_ascii=False, indent=2, sort_keys=True
    ) + "\n"
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
