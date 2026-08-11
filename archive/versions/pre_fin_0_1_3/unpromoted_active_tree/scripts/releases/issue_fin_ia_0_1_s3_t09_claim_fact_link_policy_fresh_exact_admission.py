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
    S3_CLAIM_FACT_LINK_POLICY_REF,
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V3_REF,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V3_REF,
    S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V5_REF,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF,
    S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF,
    S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF,
    S3ThreeCellBoundedAgentAdmission,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from apps.workbench.backend.application.bounded_agent_identity_policies import (
    S3_CELL_SCOPED_RESEARCH_IDENTITY_CONTRACT_REF,
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
    "fin_ia_0_1_s3_t09_claim_fact_link_policy_"
    "fresh_agent_proof_decision_v1_0.json"
)
ADMISSION = RELEASES / (
    "fin_ia_0_1_s3_t09_three_cell_deepseek_"
    "claim_fact_link_policy_exact_admission_r1.json"
)
ISSUANCE = RELEASES / (
    "fin_ia_0_1_s3_t09_claim_fact_link_policy_"
    "fresh_exact_admission_issuance_v1_0.json"
)
EXPECTED_DECISION_STATUS = (
    "pass_zero_call_claim_fact_link_policy_fresh_exact_proof_contract_"
    "frozen_admission_issuance_pending_separate_authority"
)
EXPECTED_ADMISSION_DIGEST = (
    "65bcbedfa6d68f6932130aaffdddec5580abc8c4e683e0e5523e1da49b0b128d"
)
NEXT_ACTION = (
    "S3-T09-GENERALIZED-CLAIM-FACT-LINK-POLICY-"
    "FRESH-EXACT-LIVE-EXECUTION"
)


class ClaimFactLinkExactAdmissionIssuanceError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ClaimFactLinkExactAdmissionIssuanceError(code)


def render_issuance(
    *,
    decision_path: Path = DECISION,
    admission_path: Path = ADMISSION,
    issuance_path: Path = ISSUANCE,
    expected_decision_status: str = EXPECTED_DECISION_STATUS,
    expected_admission_digest: str = EXPECTED_ADMISSION_DIGEST,
    schema_version: str = (
        "fin_ia_0_1_s3_t09_claim_fact_link_policy_"
        "fresh_exact_admission_issuance_v1_0"
    ),
    issuance_id: str = (
        "S3-T09-GENERALIZED-CLAIM-FACT-LINK-POLICY-"
        "FRESH-EXACT-ADMISSION-ISSUANCE"
    ),
    user_instruction: str = "继续",
    live_execution_authorized: bool = False,
    next_action: str = NEXT_ACTION,
    expected_research_profile_ref: str = (
        S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V3_REF
    ),
) -> tuple[dict[str, Any], dict[str, Any]]:
    _require(not admission_path.exists(), "claim_fact_link_admission_already_exists")
    _require(not issuance_path.exists(), "claim_fact_link_issuance_already_exists")
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    _require(
        decision.get("status") == expected_decision_status,
        "claim_fact_link_proof_decision_not_issuable",
    )
    prospective = decision.get("prospective_admission")
    _require(
        isinstance(prospective, dict),
        "claim_fact_link_prospective_admission_missing",
    )
    payload = prospective.get("payload")
    _require(
        isinstance(payload, dict),
        "claim_fact_link_prospective_payload_invalid",
    )

    admission = S3ThreeCellBoundedAgentAdmission.model_validate(payload)
    admission.assert_profile_admissible()
    digest = canonical_digest(admission.digest_payload())
    _require(
        digest == prospective.get("digest") == expected_admission_digest,
        "claim_fact_link_admission_digest_mismatch",
    )
    _require(
        admission.claim_fact_link_policy_ref
        == S3_CLAIM_FACT_LINK_POLICY_REF
        and admission.output_contract_ref
        == S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF
        and admission.transport_ref
        == S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF
        and admission.research_lead_transport_ref
        == S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V5_REF
        and admission.memo_writer_transport_ref
        == S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V3_REF
        and admission.research_profile_ref
        == expected_research_profile_ref
        and admission.scoped_identity_contract_ref
        == S3_CELL_SCOPED_RESEARCH_IDENTITY_CONTRACT_REF
        and admission.provider_output_capture_policy_ref
        == S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF,
        "claim_fact_link_exact_contract_binding_mismatch",
    )
    _require(
        admission.retry_budget == 0
        and admission.max_transport_attempts_per_call == 1
        and admission.max_semantic_model_calls == 12
        and admission.max_provider_calls == 12
        and admission.max_network_calls == 12,
        "claim_fact_link_execution_envelope_mismatch",
    )

    callback_calls = 0

    def _must_not_call_provider(**_: Any) -> dict[str, Any]:
        nonlocal callback_calls
        callback_calls += 1
        raise AssertionError(
            "provider_callback_forbidden_during_claim_fact_link_issuance"
        )

    build_s3_three_cell_bounded_agent_executor_for_admission(
        admission,
        chat_completion_fn=_must_not_call_provider,
    )
    _require(
        callback_calls == 0,
        "provider_called_during_claim_fact_link_issuance",
    )

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
        "claim_fact_link_prospective_identity_already_exists",
    )
    _require(
        database_digest_before == audit["canonical_database_sha256"]
        and object_digest_before == audit["canonical_object_tree_sha256"],
        "claim_fact_link_target_digest_drift",
    )
    expected_counts = decision["double_prepare"][
        "clone_execution_counts_before"
    ]
    _require(
        snapshot_before["counts"] == expected_counts,
        "claim_fact_link_target_execution_counts_mismatch",
    )

    transport_retries_zero = (
        os.environ.get("LLM_GATEWAY_TRANSPORT_RETRIES") == "0"
    )
    issuance = {
        "schema_version": schema_version,
        "issuance_id": issuance_id,
        "issued_at": datetime.now(
            timezone(timedelta(hours=8))
        ).isoformat(timespec="seconds"),
        "status": "issued_unconsumed_zero_call_preflight_pass",
        "authority": {
            "user_instruction": user_instruction,
            "fresh_exact_admission_issuance_authorized": True,
            "admission_consumption_or_exact_live_execution_authorized": (
                live_execution_authorized
            ),
            "automatic_retry_fallback_patch_or_rerun_authorized": False,
            "paired_comparison_human_review_T10_S4_release_or_production_authorized": (
                False
            ),
        },
        "source_decision_ref": decision_path.relative_to(ROOT).as_posix(),
        "issued_admission": {
            "admission_ref": admission_path.relative_to(ROOT).as_posix(),
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
            "research_profile_ref": admission.research_profile_ref,
            "provider": admission.provider,
            "model": admission.model,
            "model_ref": admission.model_ref,
            "base_url": admission.base_url,
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
            "claim_fact_link_policy_ref": (
                admission.claim_fact_link_policy_ref
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
            "first_credible_failure": "terminal_fail_closed_stop",
        },
        "claim_fact_link_live_acceptance_contract": decision[
            "claim_fact_link_live_acceptance_contract"
        ],
        "artifact_acceptance_contract": decision[
            "artifact_acceptance_contract"
        ],
        "zero_call_preflight": {
            "fresh_predicted_work_unit_attempt_run_absent": True,
            "historical_admission_or_run_reused": False,
            "target_execution_counts": expected_counts,
            "canonical_database_sha256": database_digest_before,
            "canonical_object_tree_sha256": object_digest_before,
            "target_audit_mode": "direct_SQLite_mode_ro_and_object_digest",
            "provider_callback_invoked": False,
            "credential_present": bool(
                admission.api_key_env
                and os.environ.get(admission.api_key_env)
            ),
            "credential_value_read_output_or_persisted": False,
            "transport_retry_environment_zero": transport_retries_zero,
            "exact_live_execution_precondition": (
                "LLM_GATEWAY_TRANSPORT_RETRIES must equal 0"
            ),
        },
        "observed_counts": {
            "new_admissions": 1,
            "admission_consumptions": 0,
            "work_units_created": 0,
            "attempts_created": 0,
            "research_runs_created": 0,
            "artifacts_created": 0,
            "model_calls": 0,
            "provider_calls": callback_calls,
            "execution_network_calls": 0,
            "source_network_calls": 0,
            "external_tool_calls": 0,
        },
        "next_action": next_action,
    }

    _require(
        _sha256(database_path) == database_digest_before
        and _tree_digest(object_root) == object_digest_before
        and _target_snapshot(database_path, identity=identity)
        == snapshot_before,
        "claim_fact_link_issuance_changed_target_runtime",
    )
    return payload, issuance


def main() -> int:
    payload, issuance = render_issuance()
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
