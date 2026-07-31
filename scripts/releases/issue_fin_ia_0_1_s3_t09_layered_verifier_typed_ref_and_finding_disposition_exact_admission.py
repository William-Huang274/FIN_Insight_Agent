from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_contract_policies import (
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V4_REF,
)
from scripts.releases.issue_fin_ia_0_1_s3_t09_claim_fact_link_policy_fresh_exact_admission import (
    render_issuance,
)
from scripts.releases.prepare_fin_ia_0_1_s3_t09_layered_verifier_typed_ref_and_finding_disposition_fresh_agent_proof_decision import (
    CODE_BINDING_PATHS,
    DECISION_STATUS,
    prepare,
)
from scripts.releases.prepare_fin_ia_0_1_s3_t09_nullable_owner_and_supervision_v2_final_fresh_proof import (
    HOST_CAPABILITY_RECEIPT,
)
from scripts.releases.run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution import (
    _load_admission,
    load_execution_target,
)
from scripts.releases.supervise_fin_ia_0_1_s3_t09_exact_live_execution import (
    SUPERVISION_CONTRACT_REF,
    _validate_host_capability_receipt,
)


RELEASES = ROOT / "configs" / "releases"
DECISION = RELEASES / (
    "fin_ia_0_1_s3_t09_layered_verifier_typed_ref_and_finding_"
    "disposition_fresh_agent_proof_decision_v1_0.json"
)
ADMISSION = RELEASES / (
    "fin_ia_0_1_s3_t09_three_cell_deepseek_layered_verifier_typed_ref_"
    "finding_disposition_exact_admission_r1.json"
)
ISSUANCE = RELEASES / (
    "fin_ia_0_1_s3_t09_layered_verifier_typed_ref_and_finding_"
    "disposition_fresh_exact_admission_issuance_v1_0.json"
)
EXPECTED_ADMISSION_DIGEST = (
    "fdc5dab0a6045dce123fdee897f337638eb297d961b514cd52e44f1cbf6ac7c2"
)
ISSUANCE_ID = (
    "S3-T09-LAYERED-VERIFIER-TYPED-REF-AND-FINDING-DISPOSITION-"
    "FRESH-EXACT-ADMISSION-ISSUANCE"
)
NEXT_ACTION = (
    "S3-T09-LAYERED-VERIFIER-TYPED-REF-AND-FINDING-DISPOSITION-"
    "FRESH-EXACT-LIVE-EXECUTION-AND-T09-FINAL-ASSESSMENT"
)


class LayeredVerifierExactAdmissionIssuanceError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise LayeredVerifierExactAdmissionIssuanceError(code)


def _assert_reprepared_proof(
    frozen: dict[str, Any], regenerated: dict[str, Any]
) -> None:
    for key in (
        "identity",
        "double_prepare",
        "prospective_admission",
        "target_read_only_audit",
        "exact_code_bindings",
        "architecture_contract",
        "verifier_typed_scoped_ref_acceptance_contract",
        "finding_disposition_acceptance_contract",
        "layered_runtime_acceptance_contract",
        "supervision_v2_acceptance_contract",
        "budget_and_stop_contract",
        "artifact_acceptance_contract",
    ):
        _require(
            regenerated.get(key) == frozen.get(key),
            f"frozen_proof_reprepare_mismatch:{key}",
        )
    _require(
        regenerated.get("status") == DECISION_STATUS,
        "reprepared_proof_status_mismatch",
    )
    _require(
        regenerated.get("double_prepare", {}).get("equal") is True,
        "reprepared_proof_double_prepare_not_equal",
    )
    _require(
        set((regenerated.get("observed_counts") or {}).values()) == {0},
        "reprepared_proof_not_zero_call",
    )


def render_final_issuance() -> tuple[dict[str, Any], dict[str, Any]]:
    _require(not ADMISSION.exists(), "layered_verifier_admission_exists")
    _require(not ISSUANCE.exists(), "layered_verifier_issuance_exists")

    frozen = json.loads(DECISION.read_text(encoding="utf-8"))
    regenerated = prepare()
    _assert_reprepared_proof(frozen, regenerated)
    capability, capability_digest = _validate_host_capability_receipt(
        HOST_CAPABILITY_RECEIPT
    )
    supervision = frozen["supervision_v2_acceptance_contract"]
    _require(
        supervision["contract_ref"] == SUPERVISION_CONTRACT_REF
        and supervision["actual_runner_self_finalized_exit_receipt_required"]
        is True
        and supervision["process_identity_requires_pid_and_creation_time"]
        is True
        and supervision["monitoring_is_read_only"] is True
        and supervision[
            "retry_fallback_replay_relaunch_or_rerun_allowed"
        ]
        is False,
        "supervision_v2_contract_not_frozen",
    )
    _require(
        set(frozen["exact_code_bindings"])
        == {path.as_posix() for path in CODE_BINDING_PATHS},
        "exact_code_binding_surface_mismatch",
    )

    payload, issuance = render_issuance(
        decision_path=DECISION,
        admission_path=ADMISSION,
        issuance_path=ISSUANCE,
        expected_decision_status=DECISION_STATUS,
        expected_admission_digest=EXPECTED_ADMISSION_DIGEST,
        schema_version=(
            "fin_ia_0_1_s3_t09_layered_verifier_typed_ref_and_finding_"
            "disposition_fresh_exact_admission_issuance_v1_0"
        ),
        issuance_id=ISSUANCE_ID,
        user_instruction=(
            "授权你一直做完exact-live并返回t09最终结果为止"
        ),
        live_execution_authorized=True,
        next_action=NEXT_ACTION,
        expected_research_profile_ref=(
            S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V4_REF
        ),
    )
    issuance["authority"].update(
        {
            "paired_comparison_read_only_authorized_after_success": True,
            "layered_T09_final_assessment_authorized_after_live": True,
            "owner_acceptance_write_authorized": False,
        }
    )
    issuance["proof_reverification"] = {
        "generator_rerun_before_materialization": True,
        "frozen_and_regenerated_critical_sections_equal": True,
        "double_prepare_equal": True,
        "prepared_payload_digest": regenerated["double_prepare"][
            "prepared_payload_digest"
        ],
        "prospective_admission_digest": EXPECTED_ADMISSION_DIGEST,
        "target_database_and_object_tree_digests_unchanged": True,
        "fresh_work_unit_attempt_and_research_run_absent": True,
        "exact_code_bindings": frozen["exact_code_bindings"],
        "exact_code_binding_count": len(frozen["exact_code_bindings"]),
        "host_capability_receipt_ref": (
            HOST_CAPABILITY_RECEIPT.resolve()
            .relative_to(ROOT)
            .as_posix()
        ),
        "host_capability_receipt_sha256": capability_digest,
        "host_durable_process_strategy": capability[
            "durable_process_strategy"
        ],
    }
    issuance["verifier_typed_scoped_ref_acceptance_contract"] = frozen[
        "verifier_typed_scoped_ref_acceptance_contract"
    ]
    issuance["finding_disposition_acceptance_contract"] = frozen[
        "finding_disposition_acceptance_contract"
    ]
    issuance["layered_runtime_acceptance_contract"] = frozen[
        "layered_runtime_acceptance_contract"
    ]
    issuance["supervision_v2_acceptance_contract"] = {
        **supervision,
        "host_capability_receipt_ref": (
            HOST_CAPABILITY_RECEIPT.resolve()
            .relative_to(ROOT)
            .as_posix()
        ),
        "host_capability_receipt_sha256": capability_digest,
    }
    issuance["issuance_boundary"] = {
        "admission_issued": True,
        "admission_consumed": False,
        "execution_started": False,
        "supervisor_launched": False,
        "live_execution_started": False,
        "capture_replay_performed": False,
        "business_artifact_materialization_performed": False,
        "paired_comparison_performed": False,
        "owner_acceptance_performed": False,
    }
    issuance["observed_counts"].update(
        {
            "host_capability_smoke_model_calls": 0,
            "supervisor_launches_for_exact_run": 0,
            "live_executions": 0,
            "capture_replays": 0,
            "paired_comparisons": 0,
            "owner_acceptance_writes": 0,
        }
    )
    return payload, issuance


def _write_and_validate(
    payload: dict[str, Any], issuance: dict[str, Any]
) -> None:
    temp_paths: list[Path] = []
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".json",
            prefix=".layered-verifier-admission-",
            dir=RELEASES,
            delete=False,
        ) as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            temp_admission = Path(handle.name)
            temp_paths.append(temp_admission)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".json",
            prefix=".layered-verifier-issuance-",
            dir=RELEASES,
            delete=False,
        ) as handle:
            json.dump(issuance, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            temp_issuance = Path(handle.name)
            temp_paths.append(temp_issuance)

        target = load_execution_target(temp_issuance)
        loaded = _load_admission(temp_admission, target)
        _require(
            loaded.admission_id
            == issuance["issued_admission"]["admission_id"],
            "runner_load_admission_id_mismatch",
        )
        os.replace(temp_admission, ADMISSION)
        temp_paths.remove(temp_admission)
        os.replace(temp_issuance, ISSUANCE)
        temp_paths.remove(temp_issuance)
    finally:
        for path in temp_paths:
            path.unlink(missing_ok=True)


def main() -> int:
    payload, issuance = render_final_issuance()
    _write_and_validate(payload, issuance)
    print(json.dumps(issuance, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
