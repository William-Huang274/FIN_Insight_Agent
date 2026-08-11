from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (
    S3ThreeCellBoundedAgentAdmission,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from scripts.releases.prepare_fin_ia_0_1_s4_t05_evidence_role_group_mapping_repair_fresh_proof import (
    IMPLEMENTATION,
    PROSPECTIVE_ADMISSION as ADMISSION,
    RUNTIME_ROOT,
    SOURCE_DECISION,
    _sha256,
    _tree_digest,
    prepare,
)
from scripts.releases.run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution import (
    _load_admission,
    load_execution_target,
)
from sec_agent.canonical_runtime.models import canonical_digest


PROOF_DECISION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_evidence_role_group_mapping_repair_"
    "fresh_agent_proof_decision_v1_0.json"
)
ISSUANCE = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_evidence_role_group_mapping_repair_"
    "fresh_exact_admission_issuance_v1_0.json"
)
PHYSICAL_DRIFT_AUDIT = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_replacement_admission_pre_issuance_"
    "physical_digest_drift_audit_v1_0.json"
)
ISSUED_AT = "2026-07-27T00:06:00+08:00"
EXPECTED_PROOF_STATUS = (
    "pass_zero_call_independent_fresh_proof_contract_frozen_"
    "replacement_admission_issuance_pending_separate_authority"
)
EXPECTED_ADMISSION_DIGEST = (
    "058c579211eb1f4573959d86f0b904b64e2535e749631ab7ee208571ef601af3"
)
NEXT_ACTION = (
    "S4-T05-DELL-REPLACEMENT-EXACT-R2-EXECUTION-AND-"
    "PAIRED-ASSESSMENT-AUTHORITY-DECISION"
)
CODE_BINDING_PATHS = (
    Path("apps/workbench/backend/application/bounded_agent_executor.py"),
    Path("apps/workbench/backend/application/evidence_service.py"),
    Path("apps/workbench/backend/application/research_runtime.py"),
    Path("src/sec_agent/s4_case_runtime.py"),
    Path(
        "scripts/releases/"
        "run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution.py"
    ),
    Path(
        "scripts/releases/"
        "prepare_fin_ia_0_1_s4_t04_dell_source_grounded_input_and_"
        "fresh_proof.py"
    ),
    Path(
        "tests/contract/"
        "test_fin_0_1_s4_t05_evidence_role_group_mapping_actual_dispatch_"
        "preflight_implementation.py"
    ),
    Path(
        "scripts/releases/"
        "prepare_fin_ia_0_1_s4_t05_evidence_role_group_mapping_repair_"
        "fresh_proof.py"
    ),
    Path(
        "scripts/releases/"
        "issue_fin_ia_0_1_s4_t05_evidence_role_group_mapping_repair_"
        "fresh_exact_admission.py"
    ),
)
REPREPARED_KEYS = (
    "status",
    "implementation_reaudit",
    "fresh_identity",
    "double_prepare",
    "freshness_and_nonreuse",
    "prospective_admission",
    "hard_boundaries",
    "root_cause_disposition",
    "next_action",
)


class S4T05ReplacementAdmissionIssuanceError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S4T05ReplacementAdmissionIssuanceError(code)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _exact_code_bindings() -> dict[str, str]:
    return {
        path.as_posix(): _sha256(ROOT / path)
        for path in CODE_BINDING_PATHS
    }


def _assert_frozen_proof_reprepared(
    frozen: Mapping[str, Any],
    regenerated: Mapping[str, Any],
) -> None:
    _require(
        frozen.get("status") == EXPECTED_PROOF_STATUS,
        "s4_t05_frozen_proof_status_mismatch",
    )
    for key in REPREPARED_KEYS:
        _require(
            regenerated.get(key) == frozen.get(key),
            f"s4_t05_frozen_proof_reprepare_mismatch:{key}",
        )
    frozen_target = frozen["target_read_only_audit"]
    regenerated_target = regenerated["target_read_only_audit"]
    drift_audit = _load(PHYSICAL_DRIFT_AUDIT)
    classification = drift_audit["classification"]
    _require(
        drift_audit["status"]
        == "pass_benign_sqlite_physical_digest_drift_"
        "logical_identity_and_object_tree_unchanged",
        "s4_t05_physical_drift_audit_not_pass",
    )
    _require(
        frozen_target["canonical_database_sha256"]
        == classification["prior_canonical_database_sha256"]
        and regenerated_target["canonical_database_sha256"]
        == classification["current_canonical_database_sha256"]
        and frozen_target["canonical_database_sha256"]
        != regenerated_target["canonical_database_sha256"],
        "s4_t05_physical_drift_digest_binding_mismatch",
    )
    for key in (
        "canonical_object_tree_sha256",
        "logical_snapshot_digest",
        "canonical_database_file_unchanged",
        "canonical_object_tree_unchanged",
        "logical_snapshot_unchanged",
    ):
        _require(
            frozen_target[key] == regenerated_target[key],
            f"s4_t05_nonphysical_target_drift:{key}",
        )
    _require(
        regenerated["double_prepare"]["equal"] is True
        and regenerated["double_prepare"]["clone_execution_counts_before"]
        == regenerated["double_prepare"]["clone_execution_counts_after"],
        "s4_t05_double_prepare_or_clone_state_mismatch",
    )
    _require(
        all(
            regenerated["freshness_and_nonreuse"][key] is True
            for key in (
                "work_unit_absent",
                "attempt_absent",
                "research_run_absent",
            )
        ),
        "s4_t05_fresh_identity_reused_before_issuance",
    )


def render_issuance() -> tuple[dict[str, Any], dict[str, Any]]:
    _require(not ADMISSION.exists(), "s4_t05_replacement_admission_exists")
    _require(not ISSUANCE.exists(), "s4_t05_replacement_issuance_exists")

    frozen_bytes = PROOF_DECISION.read_bytes()
    frozen = json.loads(frozen_bytes)
    regenerated = prepare()
    _assert_frozen_proof_reprepared(frozen, regenerated)
    _require(
        PROOF_DECISION.read_bytes() == frozen_bytes,
        "s4_t05_frozen_proof_decision_byte_drift",
    )

    prospective = regenerated["prospective_admission"]
    payload = prospective["payload"]
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(payload)
    admission.assert_profile_admissible()
    admission_digest = canonical_digest(admission.digest_payload())
    _require(
        admission_digest
        == prospective["digest"]
        == EXPECTED_ADMISSION_DIGEST,
        "s4_t05_replacement_admission_digest_mismatch",
    )
    _require(
        admission.company == "DELL"
        and admission.execution_mode
        == "exact_live_s4_dell_evidence_role_group_mapping_repair_r2"
        and admission.research_profile_ref
        == "fin01.s4.research_profile.dell_oem_three_cell:v1"
        and admission.retry_budget == 0
        and admission.max_transport_attempts_per_call == 1
        and admission.source_network_calls_allowed is False
        and admission.external_tool_calls_allowed is False
        and admission.live_business_case_head_writes_allowed is False,
        "s4_t05_replacement_admission_contract_binding_mismatch",
    )

    provider_callback_calls = 0

    def _must_not_call_provider(**_: Any) -> dict[str, Any]:
        nonlocal provider_callback_calls
        provider_callback_calls += 1
        raise AssertionError("provider_callback_forbidden_during_issuance")

    build_s3_three_cell_bounded_agent_executor_for_admission(
        admission,
        chat_completion_fn=_must_not_call_provider,
    )
    _require(provider_callback_calls == 0, "provider_called_during_issuance")

    canonical_root = RUNTIME_ROOT / "canonical-runtime"
    database_path = canonical_root / "canonical.sqlite"
    object_root = canonical_root / "objects"
    database_digest_before = _sha256(database_path)
    object_digest_before = _tree_digest(object_root)
    code_bindings = _exact_code_bindings()
    implementation_bindings = _load(IMPLEMENTATION)["exact_code_bindings"]
    _require(
        all(
            code_bindings[path] == digest
            for path, digest in implementation_bindings.items()
        ),
        "s4_t05_implementation_code_binding_drift",
    )

    identity = regenerated["fresh_identity"]
    maximum_output_tokens = (
        3 * admission.specialist_max_output_tokens
        + admission.lead_max_output_tokens
        + admission.writer_max_output_tokens
        + admission.verifier_max_output_tokens
    )
    issuance = {
        "schema_version": (
            "fin_ia_0_1_s4_t05_evidence_role_group_mapping_repair_"
            "fresh_exact_admission_issuance_v1_0"
        ),
        "issuance_id": (
            "S4-T05-DELL-EVIDENCE-ROLE-GROUP-MAPPING-REPAIR-"
            "FRESH-EXACT-ADMISSION-ISSUANCE-R2"
        ),
        "issued_at": ISSUED_AT,
        "status": "issued_unconsumed_zero_call_preflight_pass",
        "authority": {
            "user_instruction": "继续",
            "replacement_exact_admission_issuance_authorized": True,
            "admission_consumption_or_exact_live_execution_authorized": False,
            "automatic_retry_fallback_patch_or_rerun_authorized": False,
            "paired_assessment_or_Human_review_authorized": False,
            "S4_T06_or_later_authorized": False,
        },
        "source_proof_decision_ref": (
            PROOF_DECISION.relative_to(ROOT).as_posix()
        ),
        "source_proof_decision_sha256": _sha256(PROOF_DECISION),
        "source_implementation_ref": IMPLEMENTATION.relative_to(ROOT).as_posix(),
        "source_implementation_sha256": _sha256(IMPLEMENTATION),
        "physical_digest_drift_audit_ref": (
            PHYSICAL_DRIFT_AUDIT.relative_to(ROOT).as_posix()
        ),
        "physical_digest_drift_audit_sha256": _sha256(
            PHYSICAL_DRIFT_AUDIT
        ),
        "source_materialization_decision_ref": (
            SOURCE_DECISION.relative_to(ROOT).as_posix()
        ),
        "issued_admission": {
            "admission_ref": ADMISSION.relative_to(ROOT).as_posix(),
            "admission_id": admission.admission_id,
            "admission_digest": admission_digest,
            "runtime_root": RUNTIME_ROOT.relative_to(ROOT).as_posix(),
            "work_unit_idempotency_key": identity["execution_identity"],
            "fresh_identity": True,
            "execution_enabled": True,
            "consumed": False,
            "execution_started": False,
        },
        "exact_binding": {
            "case_id": identity["case_id"],
            "case_version": identity["case_version"],
            "decision_surface_contract_ref": identity[
                "decision_surface_contract_ref"
            ],
            "as_of": admission.as_of,
            "input_digest": identity["input_digest"],
            "preparation_digest": identity["preparation_digest"],
            "role_group_mapping_digest": identity[
                "role_group_mapping_digest"
            ],
            "evidence_alignment_digest": identity[
                "evidence_alignment_digest"
            ],
            "evidence_dispatch_digest": identity[
                "evidence_dispatch_digest"
            ],
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
            "memo_writer_transport_ref": admission.memo_writer_transport_ref,
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
            "maximum_output_tokens_total": maximum_output_tokens,
            "maximum_total_cost_usd": admission.max_total_cost_usd,
            "source_network_calls_allowed": False,
            "external_tool_calls_allowed": False,
            "live_business_case_head_writes_allowed": False,
            "automatic_retry_repair_fallback_or_rerun_allowed": False,
            "first_credible_failure": "terminal_fail_closed_stop",
        },
        "proof_reverification": {
            "generator_rerun_before_materialization": True,
            "frozen_and_regenerated_contract_equal": True,
            "double_prepare_equal": True,
            "freshness_and_nonreuse": {
                key: regenerated["freshness_and_nonreuse"][key]
                for key in (
                    "work_unit_absent",
                    "attempt_absent",
                    "research_run_absent",
                )
            },
            "mapping_alignment_dispatch_digests_equal": True,
            "target_database_sha256": database_digest_before,
            "target_object_tree_sha256": object_digest_before,
            "target_logical_snapshot_digest": regenerated[
                "target_read_only_audit"
            ]["logical_snapshot_digest"],
            "exact_code_bindings": code_bindings,
            "exact_code_binding_count": len(code_bindings),
            "actual_Runtime_and_exact_preflight_share_dispatcher": True,
            "S4_fixture_candidate_fallback_absent": True,
            "S4_ticker_mapping_branch_absent": True,
        },
        "zero_call_preflight": {
            "provider_callback_invoked": False,
            "credential_presence_checked": False,
            "credential_value_read_output_or_persisted": False,
            "transport_retry_environment_zero": (
                os.environ.get("LLM_GATEWAY_TRANSPORT_RETRIES") == "0"
            ),
            "exact_live_execution_precondition": (
                "LLM_GATEWAY_TRANSPORT_RETRIES must equal 0 and the "
                "configured provider credential must be present"
            ),
        },
        "issuance_boundary": {
            "admission_issued": True,
            "admission_consumed": False,
            "execution_started": False,
            "supervisor_launched": False,
            "model_or_provider_call_started": False,
            "business_artifact_materialization_performed": False,
            "paired_assessment_performed": False,
            "human_review_performed": False,
        },
        "observed_counts": {
            "new_admissions": 1,
            "admission_consumptions": 0,
            "work_units_created": 0,
            "attempts_created": 0,
            "research_runs_created": 0,
            "artifacts_created": 0,
            "model_calls": 0,
            "provider_calls": provider_callback_calls,
            "execution_network_calls": 0,
            "source_network_calls": 0,
            "external_tool_calls": 0,
        },
        "next_action": NEXT_ACTION,
    }
    _require(
        _sha256(database_path) == database_digest_before
        and _tree_digest(object_root) == object_digest_before,
        "s4_t05_issuance_changed_target_runtime",
    )
    return payload, issuance


def _write_and_validate(
    payload: Mapping[str, Any],
    issuance: Mapping[str, Any],
) -> None:
    temporary_paths: list[Path] = []
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".json",
            prefix=".s4-t05-replacement-admission-",
            dir=ADMISSION.parent,
            delete=False,
        ) as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            temporary_admission = Path(handle.name)
            temporary_paths.append(temporary_admission)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".json",
            prefix=".s4-t05-replacement-issuance-",
            dir=ISSUANCE.parent,
            delete=False,
        ) as handle:
            json.dump(issuance, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            temporary_issuance = Path(handle.name)
            temporary_paths.append(temporary_issuance)

        target = load_execution_target(temporary_issuance)
        loaded = _load_admission(temporary_admission, target)
        _require(
            loaded.admission_id
            == issuance["issued_admission"]["admission_id"],
            "s4_t05_runner_load_admission_id_mismatch",
        )
        os.replace(temporary_admission, ADMISSION)
        temporary_paths.remove(temporary_admission)
        os.replace(temporary_issuance, ISSUANCE)
        temporary_paths.remove(temporary_issuance)
    finally:
        for path in temporary_paths:
            path.unlink(missing_ok=True)


def main() -> int:
    payload, issuance = render_issuance()
    _write_and_validate(payload, issuance)
    print(json.dumps(issuance, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
