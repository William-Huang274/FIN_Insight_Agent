from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any


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


RUNTIME_ROOT = ROOT / ".codex_runtime/fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1"
R9_ADMISSION = ROOT / "configs/releases/fin_ia_0_1_s4_t05_dell_r9_specialist_validated_segment_union_capacity_fresh_exact_admission_r9.json"
R9_ISSUANCE = ROOT / "configs/releases/fin_ia_0_1_s4_t05_dell_r9_specialist_validated_segment_union_capacity_fresh_exact_admission_issuance_v1_0.json"
R9_FAILURE = ROOT / "configs/releases/fin_ia_0_1_s4_t05_dell_r9_specialist_validated_segment_union_capacity_exact_live_execution_failure_result_v1_0.json"
IMPLEMENTATION = ROOT / "configs/releases/fin_ia_0_1_s4_t05_dell_r9_profile_aware_artifact_lineage_validation_and_typed_subtype_minimum_zero_call_implementation_v1_0.json"
DECISION = ROOT / "configs/releases/fin_ia_0_1_s4_t05_dell_r10_profile_aware_artifact_lineage_fresh_agent_proof_decision_v1_0.json"
PROSPECTIVE_ADMISSION = ROOT / "configs/releases/fin_ia_0_1_s4_t05_dell_r10_profile_aware_artifact_lineage_fresh_exact_admission_r10.json"
EXECUTION_IDENTITY = "fin01-s4-t05-dell-r10-profile-aware-artifact-lineage-exact-live-r10"
ADMISSION_ID = "fin01-s4-t05-dell-r10-profile-aware-artifact-lineage-fresh-exact-admission-r10"
EXECUTION_MODE = "exact_live_s4_dell_r10_profile_aware_artifact_lineage_r10"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _counts(runtime_root: Path, case_id: str) -> dict[str, int]:
    return {
        key: len(value)
        for key, value in _read_only_execution_rows(
            runtime_root, case_id
        ).items()
    }


def _display(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def prepare(runtime_root: Path = RUNTIME_ROOT) -> dict[str, Any]:
    runtime_root = runtime_root.resolve()
    implementation = _load(IMPLEMENTATION)
    if not implementation["status"].startswith(
        "pass_zero_call_implementation_full_fake_s4_chain_proven"
    ):
        raise RuntimeError("R10_lineage_implementation_not_proven")
    r9 = S3ThreeCellBoundedAgentAdmission.model_validate(
        _load(R9_ADMISSION)
    )
    r9_failure = _load(R9_FAILURE)
    if (
        r9_failure["canonical_terminal_truth"]["artifact_count"] != 0
        or r9_failure["admission"]["consumed"] is not True
    ):
        raise RuntimeError("immutable_R9_failure_truth_mismatch")
    target = load_execution_target(R9_ISSUANCE)
    provisional = r9.model_copy(
        update={
            "admission_id": ADMISSION_ID,
            "execution_mode": EXECUTION_MODE,
        }
    )
    binding, overlay = resolve_s4_case_runtime_binding_for_admission(
        ROOT, provisional
    )
    if overlay is None:
        raise RuntimeError("R10_profile_overlay_missing")
    source_pack = load_s4_source_grounded_input_pack(ROOT, "DELL")
    case_id = str(r9.case_id)
    database = runtime_root / "canonical-runtime/canonical.sqlite"
    objects = runtime_root / "canonical-runtime/objects"
    before_db = _sha256(database)
    before_objects = _tree_digest(objects)
    before_snapshot = _logical_snapshot(database, case_id)
    before_counts = _counts(runtime_root, case_id)
    provider_calls = 0

    def forbidden_provider(**_: Any) -> dict[str, Any]:
        nonlocal provider_calls
        provider_calls += 1
        raise AssertionError("provider_forbidden_in_R10_fresh_proof")

    with tempfile.TemporaryDirectory(
        prefix="fin01-s4-t05-dell-r10-lineage-fresh-proof-"
    ) as temp:
        clone = Path(temp) / runtime_root.name
        shutil.copytree(runtime_root, clone)
        case_service, local_service, evidence_service = _services(clone)
        clone_before = _counts(clone, case_id)
        first = prepare_s4_source_grounded_exact_input(
            case_service,
            evidence_service,
            binding,
            source_pack,
            case_id,
            _principal(),
            decision_surface_contract_ref=target.decision_surface_ref,
            execution_identity=EXECUTION_IDENTITY,
            research_profile_overlay=overlay,
        )
        second = prepare_s4_source_grounded_exact_input(
            case_service,
            evidence_service,
            binding,
            source_pack,
            case_id,
            _principal(),
            decision_surface_contract_ref=target.decision_surface_ref,
            execution_identity=EXECUTION_IDENTITY,
            research_profile_overlay=overlay,
        )
        if first.model_dump(mode="json") != second.model_dump(mode="json"):
            raise RuntimeError("R10_double_prepare_parity_failed")
        prospective = provisional.model_copy(
            update={"input_digest": first.input_digest}
        )
        prospective.assert_profile_admissible()
        executor = build_s3_three_cell_bounded_agent_executor_for_admission(
            prospective,
            chat_completion_fn=forbidden_provider,
        )
        create_app(
            clone / "fresh-proof-workbench.sqlite",
            p02_case_service=case_service,
            p03_evidence_service=evidence_service,
            p36_local_research_service=local_service,
            s3_three_cell_bounded_agent_admission=prospective,
            s3_three_cell_bounded_agent_executor=executor,
        )
        clone_after = _counts(clone, case_id)

    after_snapshot = _logical_snapshot(database, case_id)
    if (
        provider_calls
        or clone_before != clone_after
        or before_snapshot != after_snapshot
        or before_db != _sha256(database)
        or before_objects != _tree_digest(objects)
        or first.work_unit_id in before_snapshot["work_unit_ids"]
        or first.attempt_id in before_snapshot["attempt_ids"]
        or first.research_run_id in before_snapshot["research_run_ids"]
        or PROSPECTIVE_ADMISSION.exists()
    ):
        raise RuntimeError("R10_freshness_or_zero_call_boundary_failed")
    payload = prospective.digest_payload()
    return {
        "schema_version": "fin_ia_0_1_s4_t05_dell_r10_profile_aware_artifact_lineage_fresh_agent_proof_decision_v1_0",
        "decision_id": "S4-T05-DELL-R10-PROFILE-AWARE-ARTIFACT-LINEAGE-FRESH-AGENT-PROOF-R1",
        "recorded_at": "2026-07-28T10:30:00+08:00",
        "status": "pass_zero_call_fresh_agent_proof_R10_admission_issuance_pending",
        "source_refs": {
            "implementation": _display(IMPLEMENTATION),
            "implementation_sha256": _sha256(IMPLEMENTATION),
            "immutable_R9_admission": _display(R9_ADMISSION),
            "immutable_R9_failure": _display(R9_FAILURE),
        },
        "fresh_identity": {
            "execution_identity": EXECUTION_IDENTITY,
            "case_id": case_id,
            "work_unit_id": first.work_unit_id,
            "attempt_id": first.attempt_id,
            "research_run_id": first.research_run_id,
            "input_digest": first.input_digest,
            "preparation_digest": first.preparation_digest,
        },
        "prospective_admission": {
            "payload": payload,
            "digest": canonical_digest(payload),
            "ref": _display(PROSPECTIVE_ADMISSION),
            "issued": False,
            "consumed": False,
        },
        "proof": {
            "double_prepare_equal": True,
            "create_app_wiring_passed": True,
            "target_counts_before": before_counts,
            "clone_counts_before": clone_before,
            "clone_counts_after": clone_after,
            "provider_calls": 0,
            "network_calls": 0,
            "canonical_writes": 0,
        },
        "future_exact_live": {
            "exact_once": True,
            "retry_count": 0,
            "maximum_model_provider_network_calls": [12, 12, 12],
            "success_artifact_count": 9,
            "stop_at_first_credible_terminal_result": True,
            "paired_assessment_authorized": False,
            "S4_T06_authorized": False,
        },
        "stage_acceptance": {
            "RC_P36_066": "fresh_proof_pass_R10_admission_issuance_pending",
            "DELL_R2": "not_proven",
            "S4_T06": "not_entered",
        },
        "next_action": "S4-T05-DELL-R10-PROFILE-AWARE-ARTIFACT-LINEAGE-FRESH-EXACT-ADMISSION-ISSUANCE",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, default=RUNTIME_ROOT)
    parser.add_argument("--output-json", type=Path, default=DECISION)
    args = parser.parse_args()
    first = prepare(args.runtime_root)
    second = prepare(args.runtime_root)
    if first != second:
        raise RuntimeError("R10_independent_fresh_proof_mismatch")
    result = deepcopy(first)
    result["proof_generator"] = {
        "ref": _display(Path(__file__)),
        "sha256": _sha256(Path(__file__)),
        "independent_invocations": 2,
    }
    args.output_json.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
