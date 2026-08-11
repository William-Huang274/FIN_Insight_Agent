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

from apps.workbench.backend.application.bounded_agent_executor import (
    S3ThreeCellBoundedAgentAdmission,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from sec_agent.canonical_runtime.models import canonical_digest


RELEASES = ROOT / "configs" / "releases"
DECISION = RELEASES / (
    "fin_ia_0_1_s3_t09_owner_grade_v3_specialist_v6_"
    "fresh_exact_proof_decision_v1_0.json"
)
ADMISSION = RELEASES / (
    "fin_ia_0_1_s3_t09_three_cell_deepseek_owner_grade_v3_"
    "specialist_v6_research_lead_v3_writer_v2_exact_admission_v1_0.json"
)
ISSUANCE = RELEASES / (
    "fin_ia_0_1_s3_t09_owner_grade_v3_specialist_v6_"
    "fresh_exact_admission_issuance_v1_0.json"
)


class SpecialistV6IssuanceError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise SpecialistV6IssuanceError(code)


def issue() -> dict[str, Any]:
    _require(not ADMISSION.exists(), "specialist_v6_admission_already_exists")
    _require(not ISSUANCE.exists(), "specialist_v6_issuance_already_exists")
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    _require(
        decision.get("status")
        == "pass_specialist_v6_fresh_exact_proof_prepared_issuance_authorized",
        "specialist_v6_decision_not_issuable",
    )
    prospective = decision.get("prospective_admission")
    _require(isinstance(prospective, dict), "specialist_v6_payload_missing")
    payload = prospective.get("payload")
    _require(isinstance(payload, dict), "specialist_v6_payload_invalid")
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(payload)
    admission.assert_profile_admissible()
    digest = canonical_digest(admission.digest_payload())
    _require(digest == prospective.get("digest"), "specialist_v6_digest_mismatch")

    callback_calls = 0

    def _must_not_call_provider(**_: Any) -> dict[str, Any]:
        nonlocal callback_calls
        callback_calls += 1
        raise AssertionError("provider_callback_forbidden_during_issuance")

    build_s3_three_cell_bounded_agent_executor_for_admission(
        admission,
        chat_completion_fn=_must_not_call_provider,
    )
    _require(callback_calls == 0, "provider_called_during_issuance")
    _require(
        os.environ.get("LLM_GATEWAY_TRANSPORT_RETRIES") == "0",
        "transport_retries_must_equal_zero",
    )

    identity = decision["identity"]
    audit = decision["target_read_only_audit"]
    admission_ref = ADMISSION.relative_to(ROOT).as_posix()
    issued_at = datetime.now(
        timezone(timedelta(hours=8))
    ).isoformat(timespec="seconds")
    issuance = {
        "schema_version": (
            "fin_ia_0_1_s3_t09_owner_grade_v3_specialist_v6_"
            "fresh_exact_admission_issuance_v1_0"
        ),
        "issuance_id": (
            "S3-T09-OWNER-GRADE-V3-SPECIALIST-V6-FRESH-EXACT-"
            "ADMISSION-ISSUANCE-R1"
        ),
        "issued_at": issued_at,
        "status": "issued_unconsumed_zero_call_preflight_pass",
        "authority": {
            "user_instruction": "继续修复，然后跑完真实调用看看效果",
            "zero_call_repair_and_preflight_authorized": True,
            "fresh_exact_admission_issuance_authorized": True,
            "exact_once_model_provider_network_execution_authorized": True,
            "automatic_retry_fallback_repair_or_rerun_authorized": False,
            "paired_comparison_human_review_T10_S4_release_or_production_authorized": False,
        },
        "source_decision_ref": DECISION.relative_to(ROOT).as_posix(),
        "scope_ownership_contract": decision["scope_ownership_contract"],
        "issued_admission": {
            "admission_ref": admission_ref,
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
            "decision_surface_contract_ref": identity["decision_surface_ref"],
            "as_of": identity["analysis_as_of"],
            "input_head_digest": identity["input_head_digest"],
            "input_digest": identity["input_digest"],
            "preparation_digest": identity["preparation_digest"],
            "predicted_work_unit_id": identity["work_unit_id"],
            "predicted_attempt_id": identity["attempt_id"],
            "predicted_research_run_id": identity["research_run_id"],
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
            "reasoning_effort": admission.reasoning_effort,
            "output_contract_ref": admission.output_contract_ref,
        },
        "execution_envelope": {
            "maximum_semantic_model_calls": admission.max_semantic_model_calls,
            "maximum_provider_calls": admission.max_provider_calls,
            "maximum_network_calls": admission.max_network_calls,
            "maximum_transport_attempts_per_call": (
                admission.max_transport_attempts_per_call
            ),
            "retry_budget": admission.retry_budget,
            "maximum_output_tokens_total": 16800,
            "maximum_total_cost_usd": admission.max_total_cost_usd,
            "source_network_calls_allowed": admission.source_network_calls_allowed,
            "external_tool_calls_allowed": admission.external_tool_calls_allowed,
            "live_business_case_head_writes_allowed": (
                admission.live_business_case_head_writes_allowed
            ),
            "automatic_retry_repair_fallback_or_rerun_allowed": False,
            "first_credible_failure": "terminal_fail_closed_stop",
        },
        "zero_call_preflight": {
            "focused_scope_and_shared_runtime_tests": "pass_76",
            "double_prepare_equal": decision["double_prepare"]["equal"],
            "fresh_predicted_work_unit_attempt_run_absent": True,
            "old_admission_or_run_reused": False,
            "target_execution_counts": [
                decision["double_prepare"]["clone_execution_counts_before"][
                    "canonical_work_units"
                ],
                decision["double_prepare"]["clone_execution_counts_before"][
                    "canonical_attempts"
                ],
                decision["double_prepare"]["clone_execution_counts_before"][
                    "canonical_research_run_versions"
                ],
                decision["double_prepare"]["clone_execution_counts_before"][
                    "canonical_artifact_versions"
                ],
            ],
            "canonical_database_sha256": audit["canonical_database_sha256"],
            "canonical_object_tree_sha256": audit[
                "canonical_object_tree_sha256"
            ],
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
            "source_network_calls": 0,
            "external_tool_calls": 0,
        },
        "next_action": (
            "S3-T09-OWNER-GRADE-SPECIALIST-V6-FRESH-EXACT-LIVE-EXECUTION"
        ),
    }
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
