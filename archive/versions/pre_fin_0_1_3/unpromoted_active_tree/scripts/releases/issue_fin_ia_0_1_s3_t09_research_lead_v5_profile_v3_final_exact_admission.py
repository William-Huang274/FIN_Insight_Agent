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
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V3_REF,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V3_REF,
    S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V5_REF,
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
    "fin_ia_0_1_s3_t09_research_lead_v5_profile_v3_"
    "final_fresh_exact_proof_decision_v1_0.json"
)
ADMISSION = RELEASES / (
    "fin_ia_0_1_s3_t09_three_cell_deepseek_owner_grade_research_lead_"
    "v5_profile_v3_final_exact_admission_r1.json"
)
ISSUANCE = RELEASES / (
    "fin_ia_0_1_s3_t09_research_lead_v5_profile_v3_"
    "final_fresh_exact_admission_issuance_v1_0.json"
)
EXPECTED_STATUS = (
    "pass_zero_call_profile_v3_final_fresh_exact_proof_contract_frozen_"
    "issuance_ready"
)
EXPECTED_DIGEST = (
    "e3db9ce6eb89372983cca3696a8223e7e29d612060189568c604352f8efadd12"
)


def render() -> tuple[dict[str, Any], dict[str, Any]]:
    if ADMISSION.exists() or ISSUANCE.exists():
        raise RuntimeError("profile_v3_final_admission_or_issuance_already_exists")
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    if decision.get("status") != EXPECTED_STATUS:
        raise RuntimeError("profile_v3_final_decision_not_issuable")
    prospective = decision.get("prospective_admission") or {}
    payload = prospective.get("payload")
    if not isinstance(payload, dict):
        raise RuntimeError("profile_v3_final_admission_payload_missing")

    admission = S3ThreeCellBoundedAgentAdmission.model_validate(payload)
    admission.assert_profile_admissible()
    digest = canonical_digest(admission.digest_payload())
    if digest != prospective.get("digest") or digest != EXPECTED_DIGEST:
        raise RuntimeError("profile_v3_final_admission_digest_mismatch")
    if (
        admission.research_profile_ref
        != S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V3_REF
        or admission.transport_ref
        != S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF
        or admission.research_lead_transport_ref
        != S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V5_REF
        or admission.memo_writer_transport_ref
        != S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V3_REF
        or admission.retry_budget != 0
        or admission.max_transport_attempts_per_call != 1
    ):
        raise RuntimeError("profile_v3_final_admission_contract_mismatch")

    provider_calls = 0

    def _must_not_call_provider(**_: Any) -> dict[str, Any]:
        nonlocal provider_calls
        provider_calls += 1
        raise AssertionError("provider_forbidden_during_issuance")

    build_s3_three_cell_bounded_agent_executor_for_admission(
        admission,
        chat_completion_fn=_must_not_call_provider,
    )
    if provider_calls:
        raise RuntimeError("provider_called_during_profile_v3_issuance")

    runtime_root = ROOT / decision["runtime_root"]
    canonical_root = runtime_root / "canonical-runtime"
    database_path = canonical_root / "canonical.sqlite"
    object_root = canonical_root / "objects"
    identity = decision["identity"]
    expected_audit = decision["target_read_only_audit"]
    database_digest = _sha256(database_path)
    object_digest = _tree_digest(object_root)
    snapshot = _target_snapshot(database_path, identity=identity)
    if set(snapshot["prospective_identity_rows"].values()) != {0}:
        raise RuntimeError("profile_v3_final_identity_not_fresh")
    if (
        database_digest != expected_audit["canonical_database_sha256"]
        or object_digest != expected_audit["canonical_object_tree_sha256"]
    ):
        raise RuntimeError("profile_v3_final_target_drift")

    issuance = {
        "schema_version": (
            "fin_ia_0_1_s3_t09_research_lead_v5_profile_v3_"
            "final_fresh_exact_admission_issuance_v1_0"
        ),
        "issuance_id": (
            "S3-T09-OWNER-GRADE-RESEARCH-LEAD-V5-PROFILE-V3-"
            "FINAL-FRESH-EXACT-ADMISSION-ISSUANCE"
        ),
        "issued_at": datetime.now(
            timezone(timedelta(hours=8))
        ).isoformat(timespec="seconds"),
        "status": "issued_unconsumed_zero_call_preflight_pass",
        "authority": {
            "user_instruction": "按这个顺序做",
            "issuance_and_one_exact_live_authorized": True,
            "automatic_retry_fallback_or_second_live_authorized": False,
            "owner_acceptance_authorized_for_codex": False,
            "release_or_production_authorized": False,
        },
        "source_decision_ref": DECISION.relative_to(ROOT).as_posix(),
        "issued_admission": {
            "admission_ref": ADMISSION.relative_to(ROOT).as_posix(),
            "admission_id": admission.admission_id,
            "admission_digest": digest,
            "runtime_root": decision["runtime_root"],
            "work_unit_idempotency_key": identity["execution_identity"],
            "fresh_identity": True,
            "execution_enabled": True,
            "consumed": False,
            "execution_started": False,
        },
        "exact_binding": {
            "case_id": identity["case_id"],
            "case_version": identity["case_version"],
            "decision_surface_contract_ref": (
                identity["decision_surface_ref"]
            ),
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
            "credential_env": admission.api_key_env,
            "output_contract_ref": admission.output_contract_ref,
            "specialist_transport_ref": admission.transport_ref,
            "research_lead_transport_ref": (
                admission.research_lead_transport_ref
            ),
            "memo_writer_transport_ref": (
                admission.memo_writer_transport_ref
            ),
            "scoped_identity_contract_ref": (
                admission.scoped_identity_contract_ref
            ),
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
            "source_network_calls_allowed": False,
            "external_tool_calls_allowed": False,
            "live_business_case_head_writes_allowed": False,
            "automatic_retry_repair_fallback_or_rerun_allowed": False,
            "second_live_execution_allowed": False,
        },
        "zero_call_preflight": {
            "fresh_predicted_work_unit_attempt_run_absent": True,
            "target_counts": snapshot["counts"],
            "canonical_database_sha256": database_digest,
            "canonical_object_tree_sha256": object_digest,
            "provider_calls": provider_calls,
            "credential_present": bool(
                admission.api_key_env
                and os.environ.get(admission.api_key_env)
            ),
            "credential_value_read_output_or_persisted": False,
            "transport_retries_env_is_zero": (
                os.environ.get("LLM_GATEWAY_TRANSPORT_RETRIES") == "0"
            ),
        },
        "next_action": (
            "S3-T09-OWNER-GRADE-RESEARCH-LEAD-V5-PROFILE-V3-"
            "FINAL-FRESH-EXACT-LIVE-EXECUTION"
        ),
    }
    return payload, issuance


def main() -> int:
    payload, issuance = render()
    ADMISSION.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    ISSUANCE.write_text(
        json.dumps(issuance, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(issuance, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
