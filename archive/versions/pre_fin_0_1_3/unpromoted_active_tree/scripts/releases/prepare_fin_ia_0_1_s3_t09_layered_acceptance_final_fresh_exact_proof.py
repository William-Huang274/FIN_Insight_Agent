from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_contract_policies import (
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V4_REF,
)
from scripts.releases.prepare_fin_ia_0_1_s3_t09_claim_fact_link_policy_fresh_exact_proof import (
    prepare as prepare_claim_fact_proof,
)
from scripts.releases.supervise_fin_ia_0_1_s3_t09_exact_live_execution import (
    SUPERVISION_CONTRACT_REF,
    _validate_host_capability_receipt,
)


RELEASES = ROOT / "configs" / "releases"
RUNTIME_ROOT = (
    ROOT
    / ".codex_runtime"
    / "fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1"
)
IMPLEMENTATION = RELEASES / (
    "fin_ia_0_1_s3_t09_layered_acceptance_runtime_alignment_"
    "zero_call_implementation_v1_0.json"
)
CLAIM_FACT_IMPLEMENTATION = RELEASES / (
    "fin_ia_0_1_s3_t09_claim_fact_link_policy_closed_alias_"
    "zero_call_implementation_v1_0.json"
)
PROFILE_V3_FINAL_FAILURE = RELEASES / (
    "fin_ia_0_1_s3_t09_research_lead_v5_profile_v3_final_"
    "exact_live_execution_result_v1_0.json"
)
LATEST_FINAL_FAILURE = RELEASES / (
    "fin_ia_0_1_s3_t09_nullable_owner_and_supervision_v2_final_"
    "exact_live_execution_result_v1_0.json"
)
CLAIM_FACT_LIVE_FAILURE = RELEASES / (
    "fin_ia_0_1_s3_t09_claim_fact_link_policy_fresh_exact_"
    "live_execution_result_v1_0.json"
)
OUTPUT_V4_ORPHAN_CLOSEOUT = RELEASES / (
    "fin_ia_0_1_s3_t09_output_v4_verifier_schema_repair_"
    "orphan_typed_closeout_result_v1_0.json"
)
ATOMIC_LIVE_FAILURE = RELEASES / (
    "fin_ia_0_1_s3_t09_atomic_terminalization_and_typed_verifier_"
    "state_machine_fresh_exact_live_execution_result_v1_0.json"
)
HOST_CAPABILITY_RECEIPT = (
    ROOT
    / ".codex_runtime"
    / "fin01-s3-t09-supervision-v2-final-host-capability-r1"
    / "host_capability_receipt.json"
)
EXECUTION_IDENTITY = (
    "fin01-s3-t09-three-cell-deepseek-layered-acceptance-"
    "final-live-validation-r1"
)
PROSPECTIVE_ADMISSION_ID = (
    "fin01-s3-t09-three-cell-deepseek-layered-acceptance-"
    "final-exact-admission-r1"
)
PROSPECTIVE_ADMISSION_FILE = (
    "configs/releases/fin_ia_0_1_s3_t09_three_cell_deepseek_"
    "layered_acceptance_final_exact_admission_r1.json"
)
DECISION_STATUS = (
    "pass_zero_call_layered_acceptance_final_fresh_exact_proof_"
    "contract_frozen_admission_issuance_and_one_live_execution_authorized"
)
DECISION_CONTRACT_REF = (
    "fin01.s3.layered_acceptance_final_fresh_exact_proof_decision:v1"
)
IMPLEMENTATION_STATUS = (
    "pass_zero_call_layered_acceptance_runtime_alignment_"
    "profile_v4_fixture_proven"
)
CODE_BINDING_PATHS = (
    Path("apps/workbench/backend/application/bounded_agent_contract_policies.py"),
    Path("apps/workbench/backend/application/bounded_agent_executor.py"),
    Path(
        "scripts/releases/"
        "run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution.py"
    ),
    Path(
        "scripts/releases/"
        "supervise_fin_ia_0_1_s3_t09_exact_live_execution.py"
    ),
)


class LayeredAcceptanceFreshProofError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise LayeredAcceptanceFreshProofError(code)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(
    *,
    runtime_root: Path = RUNTIME_ROOT,
    implementation_path: Path = IMPLEMENTATION,
    host_capability_receipt_path: Path = HOST_CAPABILITY_RECEIPT,
) -> dict[str, Any]:
    implementation = json.loads(
        implementation_path.read_text(encoding="utf-8")
    )
    _require(
        implementation.get("status") == IMPLEMENTATION_STATUS,
        "layered_runtime_alignment_implementation_status_invalid",
    )
    _require(
        implementation.get("runtime_alignment", {}).get(
            "research_profile_ref"
        )
        == S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V4_REF
        and implementation.get("runtime_alignment", {}).get(
            "ordinary_character_limit_exceedance_terminal"
        )
        is False
        and implementation.get("deterministic_verification", {}).get(
            "fixture_artifact_count"
        )
        == 9
        and set((implementation.get("observed_counts") or {}).values())
        == {0},
        "layered_runtime_alignment_contract_incomplete",
    )
    for relative, expected in (
        implementation.get("source_digests") or {}
    ).items():
        _require(
            _sha256(ROOT / relative) == expected,
            f"layered_runtime_alignment_source_digest_drift:{relative}",
        )

    capability, capability_digest = _validate_host_capability_receipt(
        host_capability_receipt_path
    )
    _require(
        capability.get("contract_ref") == SUPERVISION_CONTRACT_REF
        and capability.get("self_finalized_exit_receipt") is True,
        "layered_exact_host_capability_invalid",
    )

    result = prepare_claim_fact_proof(
        runtime_root=runtime_root,
        implementation_result_path=CLAIM_FACT_IMPLEMENTATION,
        final_failure_result_path=PROFILE_V3_FINAL_FAILURE,
        execution_identity=EXECUTION_IDENTITY,
        prospective_admission_id=PROSPECTIVE_ADMISSION_ID,
        prospective_admission_file=PROSPECTIVE_ADMISSION_FILE,
        execution_mode=(
            "exact_live_three_cell_deepseek_layered_acceptance_final_r1"
        ),
        decision_status=DECISION_STATUS,
        decision_contract_ref=DECISION_CONTRACT_REF,
        additional_source_failed_result_paths=(
            CLAIM_FACT_LIVE_FAILURE,
            OUTPUT_V4_ORPHAN_CLOSEOUT,
            ATOMIC_LIVE_FAILURE,
            LATEST_FINAL_FAILURE,
        ),
        research_profile_ref=S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V4_REF,
    )
    result["source_refs"]["layered_runtime_alignment_implementation"] = (
        implementation_path.resolve().relative_to(ROOT).as_posix()
    )
    result["source_refs"]["layered_acceptance_standard"] = (
        "configs/releases/"
        "fin_ia_0_1_layered_agent_acceptance_standard_v1_0.json"
    )
    result["exact_code_bindings"] = {
        path.as_posix(): _sha256(ROOT / path) for path in CODE_BINDING_PATHS
    }
    result["layered_runtime_acceptance_contract"] = {
        "research_profile_ref": S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V4_REF,
        "ordinary_512_and_3200_character_thresholds_terminal": False,
        "quality_findings_must_be_persisted": True,
        "wire_alias_and_local_expanded_byte_capacities_remain_hard": True,
        "L1_truth_provenance_numeric_scope_identity_permission_and_lineage_remain_hard": (
            True
        ),
        "silent_truncation_rewrite_or_fact_guessing_allowed": False,
        "historical_terminal_truth_rewrite_allowed": False,
    }
    result["supervision_v2_acceptance_contract"] = {
        "contract_ref": SUPERVISION_CONTRACT_REF,
        "host_capability_receipt_ref": (
            host_capability_receipt_path.resolve()
            .relative_to(ROOT)
            .as_posix()
        ),
        "host_capability_receipt_sha256": capability_digest,
        "direct_actual_runner_no_parent_timeout": True,
        "actual_runner_self_finalized_exit_receipt_required": True,
        "monitoring_is_read_only": True,
        "retry_fallback_replay_relaunch_or_rerun_allowed": False,
    }
    result["artifact_acceptance_contract"].update(
        {
            "same_coherent_run_required": True,
            "L1_hard_integrity_pass_required": True,
            "L3_or_L4_quality_findings_may_coexist_with_success": True,
            "success_requires_artifact_families": 9,
        }
    )
    result["experiment_governance"].update(
        {
            "decision_label": (
                "proceed_to_exact_admission_and_one_exact_live_execution"
            ),
            "admission_issuance_authorized": True,
            "admission_consumption_authorized": True,
            "live_execution_authorized": True,
            "automatic_retry_fallback_patch_or_rerun_authorized": False,
            "paired_comparison_or_owner_acceptance_authorized": False,
        }
    )
    result["next_action"] = (
        "S3-T09-LAYERED-ACCEPTANCE-FINAL-EXACT-ADMISSION-ISSUANCE-"
        "AND-ONE-EXACT-LIVE"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, default=RUNTIME_ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = prepare(runtime_root=args.runtime_root)
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output is None:
        print(rendered)
    else:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
