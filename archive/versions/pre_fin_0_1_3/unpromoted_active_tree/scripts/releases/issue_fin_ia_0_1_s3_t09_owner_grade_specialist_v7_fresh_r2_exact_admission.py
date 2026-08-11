from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_contract_policies import (
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE_REF,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF,
    S3ThreeCellBoundedAgentAdmission,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from scripts.releases.issue_fin_ia_0_1_s3_t09_owner_grade_specialist_v7_exact_admission import (
    _target_snapshot,
)
from scripts.releases.prepare_fin_ia_0_1_s3_t09_paired_deterministic_baseline_decision import (
    _sha256,
    _tree_digest,
)
from sec_agent.canonical_runtime.models import canonical_digest


RELEASES = ROOT / "configs" / "releases"
DECISION = RELEASES / (
    "fin_ia_0_1_s3_t09_owner_grade_specialist_v7_"
    "fresh_r2_exact_proof_decision_v1_0.json"
)
ADMISSION = RELEASES / (
    "fin_ia_0_1_s3_t09_three_cell_deepseek_owner_grade_v3_"
    "specialist_v7_research_lead_v3_writer_v2_exact_admission_r2.json"
)
ISSUANCE = RELEASES / (
    "fin_ia_0_1_s3_t09_owner_grade_specialist_v7_"
    "fresh_r2_exact_admission_issuance_v1_0.json"
)
EXPECTED_DECISION_STATUS = (
    "pass_specialist_v7_fresh_r2_exact_proof_decided_"
    "admission_issuance_authorized"
)
EXPECTED_ADMISSION_DIGEST = (
    "006a280d8aa28dddbb285f36f1386fce5029c76743dd42b4b732d6271124b92a"
)


class SpecialistV7R2IssuanceError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise SpecialistV7R2IssuanceError(code)


def issue() -> dict[str, Any]:
    _require(not ADMISSION.exists(), "specialist_v7_r2_admission_already_exists")
    _require(not ISSUANCE.exists(), "specialist_v7_r2_issuance_already_exists")
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    _require(
        decision.get("status") == EXPECTED_DECISION_STATUS,
        "specialist_v7_r2_decision_not_issuable",
    )
    prospective = decision.get("prospective_admission")
    _require(isinstance(prospective, dict), "specialist_v7_r2_payload_missing")
    payload = prospective.get("payload")
    _require(isinstance(payload, dict), "specialist_v7_r2_payload_invalid")

    admission = S3ThreeCellBoundedAgentAdmission.model_validate(payload)
    admission.assert_profile_admissible()
    digest = canonical_digest(admission.digest_payload())
    _require(
        digest == prospective.get("digest") == EXPECTED_ADMISSION_DIGEST,
        "specialist_v7_r2_digest_mismatch",
    )
    _require(
        admission.transport_ref
        == S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF
        and admission.research_profile_ref
        == S3_NVDA_THREE_CELL_RESEARCH_PROFILE_REF,
        "specialist_v7_r2_transport_or_profile_mismatch",
    )
    _require(
        admission.retry_budget == 0
        and admission.max_transport_attempts_per_call == 1,
        "specialist_v7_r2_retry_contract_mismatch",
    )

    callback_calls = 0

    def _must_not_call_provider(**_: Any) -> dict[str, Any]:
        nonlocal callback_calls
        callback_calls += 1
        raise AssertionError("provider_callback_forbidden_during_v7_r2_issuance")

    build_s3_three_cell_bounded_agent_executor_for_admission(
        admission,
        chat_completion_fn=_must_not_call_provider,
    )
    _require(callback_calls == 0, "provider_called_during_v7_r2_issuance")

    runtime_root = ROOT / decision["runtime_root"]
    canonical_root = runtime_root / "canonical-runtime"
    database_path = canonical_root / "canonical.sqlite"
    object_root = canonical_root / "objects"
    identity = decision["identity"]
    audit = decision["target_read_only_audit"]
    database_digest_before = _sha256(database_path)
    object_digest_before = _tree_digest(object_root)
    snapshot_before = _target_snapshot(database_path, identity=identity)
    _require(
        set(snapshot_before["prospective_identity_rows"].values()) == {0},
        "specialist_v7_r2_prospective_identity_already_exists",
    )
    _require(
        database_digest_before == audit["canonical_database_sha256"]
        and object_digest_before == audit["canonical_object_tree_sha256"],
        "specialist_v7_r2_target_digest_drift",
    )
    _require(
        os.environ.get("LLM_GATEWAY_TRANSPORT_RETRIES") == "0",
        "specialist_v7_r2_transport_retries_not_zero",
    )

    issued_at = datetime.now(
        timezone(timedelta(hours=8))
    ).isoformat(timespec="seconds")
    issuance = {
        "schema_version": (
            "fin_ia_0_1_s3_t09_owner_grade_specialist_v7_"
            "fresh_r2_exact_admission_issuance_v1_0"
        ),
        "issuance_id": (
            "S3-T09-OWNER-GRADE-SPECIALIST-V7-FRESH-R2-"
            "EXACT-ADMISSION-ISSUANCE"
        ),
        "issued_at": issued_at,
        "status": "issued_unconsumed_zero_call_preflight_pass",
        "authority": {
            "user_instruction": "修复，修复完做真实模型调用看看修复效果",
            "fresh_r2_exact_admission_issuance_authorized": True,
            "one_exact_live_execution_authorized": True,
            "automatic_retry_fallback_patch_normalization_or_rerun_authorized": False,
            "paired_comparison_human_review_T10_S4_release_or_production_authorized": False,
        },
        "source_decision_ref": DECISION.relative_to(ROOT).as_posix(),
        "issued_admission": {
            "admission_ref": ADMISSION.relative_to(ROOT).as_posix(),
            "admission_id": admission.admission_id,
            "admission_digest": digest,
            "runtime_root": decision["runtime_root"],
            "work_unit_idempotency_key": identity["execution_identity"],
            "fresh_identity": True,
            "consumed": False,
            "execution_started": False,
        },
        "exact_binding": {
            "case_id": identity["case_id"],
            "case_version": identity["case_version"],
            "decision_surface_contract_ref": identity["decision_surface_ref"],
            "as_of": identity["analysis_as_of"],
            "input_head_digest": identity["input_head_digest"],
            "input_digest": identity["input_digest"],
            "preparation_digest": identity["preparation_digest"],
            "predicted_work_unit_id": identity["work_unit_id"],
            "predicted_attempt_id": identity["attempt_id"],
            "predicted_research_run_id": identity["research_run_id"],
            "research_profile_ref": admission.research_profile_ref,
            "provider": admission.provider,
            "model": admission.model,
            "model_ref": admission.model_ref,
            "base_url": admission.base_url,
            "credential_env": admission.api_key_env,
            "specialist_transport_ref": admission.transport_ref,
            "research_lead_transport_ref": admission.research_lead_transport_ref,
            "memo_writer_transport_ref": admission.memo_writer_transport_ref,
            "provider_output_capture_policy_ref": (
                admission.provider_output_capture_policy_ref
            ),
        },
        "execution_envelope": {
            "maximum_semantic_model_calls": admission.max_semantic_model_calls,
            "maximum_provider_calls": admission.max_provider_calls,
            "maximum_network_calls": admission.max_network_calls,
            "maximum_transport_attempts_per_call": (
                admission.max_transport_attempts_per_call
            ),
            "retry_budget": admission.retry_budget,
            "maximum_output_tokens_total": decision[
                "budget_and_stop_contract"
            ]["aggregate_max_output_tokens"],
            "maximum_total_cost_usd": admission.max_total_cost_usd,
            "automatic_retry_repair_fallback_or_rerun_allowed": False,
            "first_credible_failure": "terminal_fail_closed_stop",
        },
        "zero_call_preflight": {
            "fresh_predicted_work_unit_attempt_run_absent": True,
            "old_r1_admission_or_run_reused": False,
            "target_execution_counts": [
                snapshot_before["counts"]["canonical_work_units"],
                snapshot_before["counts"]["canonical_attempts"],
                snapshot_before["counts"]["canonical_research_run_versions"],
                snapshot_before["counts"]["canonical_artifact_versions"],
            ],
            "canonical_database_sha256": database_digest_before,
            "canonical_object_tree_sha256": object_digest_before,
            "target_audit_mode": "direct_SQLite_mode_ro_and_object_digest",
            "provider_callback_invoked": False,
            "credential_present": bool(os.environ.get("DEEPSEEK_API_KEY")),
            "credential_value_read_output_or_persisted": False,
            "transport_retry_environment_zero": True,
        },
        "observed_counts": {
            "new_admissions": 1,
            "admission_consumptions": 0,
            "work_units_created": 0,
            "attempts_created": 0,
            "research_runs_created": 0,
            "artifacts_created": 0,
            "model_calls": 0,
            "provider_calls": 0,
            "execution_network_calls": 0,
        },
        "next_action": (
            "S3-T09-OWNER-GRADE-SPECIALIST-V7-FRESH-R2-EXACT-LIVE-EXECUTION"
        ),
    }

    _require(
        _sha256(database_path) == database_digest_before
        and _tree_digest(object_root) == object_digest_before
        and _target_snapshot(database_path, identity=identity) == snapshot_before,
        "specialist_v7_r2_issuance_changed_target_runtime",
    )
    ADMISSION.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    ISSUANCE.write_text(
        json.dumps(issuance, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return issuance


def main() -> int:
    print(json.dumps(issue(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
