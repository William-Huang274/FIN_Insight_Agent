from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3
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
from scripts.releases.prepare_fin_ia_0_1_s3_t09_paired_deterministic_baseline_decision import (
    _logical_snapshot,
    _tree_digest,
)
from scripts.releases.prepare_fin_ia_0_1_s4_t06_mu_temporal_authority_terminal_result_fresh_proof import (
    DECISION as PROOF_DECISION,
    PROSPECTIVE_ADMISSION as ADMISSION,
    RUNTIME_ROOT,
    build_decision,
)
from scripts.releases.run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution import (
    _load_admission,
    load_execution_target,
)
from sec_agent.canonical_runtime.models import canonical_digest


AUTHORITY = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_action_planning_temporal_"
    "authority_and_capture_v2_terminal_result_materialization_fresh_"
    "exact_admission_r6_authority_decision_v1_0.json"
)
IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_action_planning_temporal_"
    "authority_and_capture_v2_terminal_result_materialization_minimum_"
    "zero_call_implementation_v1_0.json"
)
PROOF_GENERATOR = ROOT / (
    "scripts/releases/prepare_fin_ia_0_1_s4_t06_mu_temporal_authority_"
    "terminal_result_fresh_proof.py"
)
R5_ADMISSION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_runtime_audit_evidence_v2_"
    "and_material_numeric_classifier_fresh_exact_admission_r5.json"
)
R5_FAILURE = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_runtime_audit_evidence_v2_"
    "and_material_numeric_classifier_r5_exact_live_execution_failure_"
    "result_v1_0.json"
)
ISSUANCE_SCOPE_PREFLIGHT = ROOT / (
    ".codex_runtime/s4_t06_temporal_R6_admission_issuance_scope_"
    "preflight.json"
)
ISSUANCE = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_action_planning_temporal_"
    "authority_and_capture_v2_terminal_result_materialization_fresh_"
    "exact_admission_r6_issuance_v1_0.json"
)
EXPECTED_AUTHORITY_SHA256 = (
    "3d96b78f704d99147b7475447a9c647aa46940fdc92ab888caed74881b4e6033"
)
EXPECTED_PROOF_SHA256 = (
    "72cfcd0f5f730be3be08288d9fe50f1eea95f4e1886167bbe7fb3bcad5aa26ca"
)
EXPECTED_IMPLEMENTATION_SHA256 = (
    "cf1042db86a2ddc4175295cc3c4c4f8ce7d269edb3f67db936c9c72b91ab6449"
)
EXPECTED_PROOF_GENERATOR_SHA256 = (
    "95e1808f23944f66cd2b90db656d60bfa7dda9bb8fd7dbf10d55dc96c7c5918f"
)
EXPECTED_R5_ADMISSION_SHA256 = (
    "1f49070ddce794ebf097abed4cd07cec2675d85822a0d7a8547236460c5fbff7"
)
EXPECTED_R5_FAILURE_SHA256 = (
    "9662458edd0cfcddd4c999bbd2cb6374ade88b20fad473c7d432697a2ef6790f"
)
EXPECTED_ADMISSION_DIGEST = (
    "a30d6977df984f1002ec95992c3e6d3bf8e7a7271dd54a626bb5271315bb2ac3"
)
EXPECTED_ISSUANCE_STATUS = "issued_unconsumed_zero_call_preflight_pass"
NEXT_ACTION = (
    "S4-T06-MU-ACTION-PLANNING-TEMPORAL-AUTHORITY-AND-CAPTURE-V2-"
    "TERMINAL-RESULT-MATERIALIZATION-R6-EXACT-LIVE-EXECUTION-AND-"
    "SUCCESS-ONLY-PAIRED-ASSESSMENT-AUTHORITY-DECISION"
)


class S4T06MuR6AdmissionIssuanceError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S4T06MuR6AdmissionIssuanceError(code)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    return (
        resolved.relative_to(ROOT).as_posix()
        if resolved.is_relative_to(ROOT)
        else str(resolved)
    )


def _fresh_identity_counts(identity: Mapping[str, Any]) -> dict[str, int]:
    database_path = RUNTIME_ROOT / "canonical-runtime/canonical.sqlite"
    connection = sqlite3.connect(
        f"file:{database_path.resolve().as_posix()}?mode=ro",
        uri=True,
    )
    try:
        return {
            "work_units": connection.execute(
                "SELECT COUNT(*) FROM canonical_work_units "
                "WHERE logical_id = ?",
                (identity["work_unit_id"],),
            ).fetchone()[0],
            "attempts": connection.execute(
                "SELECT COUNT(*) FROM canonical_attempts "
                "WHERE logical_id = ?",
                (identity["attempt_id"],),
            ).fetchone()[0],
            "research_runs": connection.execute(
                "SELECT COUNT(*) FROM canonical_research_run_versions "
                "WHERE logical_id = ?",
                (identity["research_run_id"],),
            ).fetchone()[0],
        }
    finally:
        connection.close()


def render_issuance() -> tuple[dict[str, Any], dict[str, Any]]:
    _require(not ADMISSION.exists(), "s4_t06_mu_R6_admission_already_exists")
    _require(not ISSUANCE.exists(), "s4_t06_mu_R6_issuance_already_exists")
    _require(
        _sha256(AUTHORITY) == EXPECTED_AUTHORITY_SHA256,
        "s4_t06_mu_R6_authority_byte_drift",
    )
    _require(
        _sha256(PROOF_DECISION) == EXPECTED_PROOF_SHA256,
        "s4_t06_mu_R6_proof_byte_drift",
    )
    _require(
        _sha256(IMPLEMENTATION) == EXPECTED_IMPLEMENTATION_SHA256,
        "s4_t06_mu_R6_implementation_byte_drift",
    )
    _require(
        _sha256(PROOF_GENERATOR) == EXPECTED_PROOF_GENERATOR_SHA256,
        "s4_t06_mu_R6_proof_generator_byte_drift",
    )
    _require(
        _sha256(R5_ADMISSION) == EXPECTED_R5_ADMISSION_SHA256
        and _sha256(R5_FAILURE) == EXPECTED_R5_FAILURE_SHA256,
        "s4_t06_mu_R6_immutable_R5_history_drift",
    )

    preflight = _load(ISSUANCE_SCOPE_PREFLIGHT)
    _require(
        preflight["status"] == "pass"
        and preflight["run_scope"]
        == (
            "S4_T06_MU_ACTION_PLANNING_TEMPORAL_AUTHORITY_AND_CAPTURE_"
            "V2_TERMINAL_RESULT_MATERIALIZATION_FRESH_EXACT_ADMISSION_"
            "R6_ISSUANCE"
        )
        and preflight["open_full_chain_blockers"] == [],
        "s4_t06_mu_R6_issuance_scope_preflight_not_passed",
    )

    authority = _load(AUTHORITY)
    _require(
        authority["decision_label"]
        == "authorize_frozen_R6_admission_issuance_only"
        and authority["authority"][
            "future_exact_R6_admission_issuance_authorized"
        ]
        is True
        and authority["authority"]["admission_consumption_authorized"]
        is False
        and authority["authority"]["R6_exact_live_execution_authorized"]
        is False
        and authority["next_action_authorized"] is True,
        "s4_t06_mu_R6_issuance_not_authorized",
    )

    frozen_proof = _load(PROOF_DECISION)
    _require(
        build_decision() == frozen_proof,
        "s4_t06_mu_R6_frozen_proof_regeneration_mismatch",
    )
    prospective = frozen_proof["prospective_R6_admission"]
    payload = prospective["payload"]
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(payload)
    admission.assert_profile_admissible()
    digest = canonical_digest(admission.digest_payload())
    _require(
        digest
        == prospective["digest"]
        == authority["frozen_R6_admission"]["admission_digest"]
        == EXPECTED_ADMISSION_DIGEST,
        "s4_t06_mu_R6_admission_digest_mismatch",
    )
    _require(
        payload == admission.digest_payload(),
        "s4_t06_mu_R6_persisted_payload_not_digest_payload",
    )

    for relative_path, expected in frozen_proof["implementation_reaudit"][
        "exact_code_bindings"
    ].items():
        _require(
            _sha256(ROOT / relative_path) == expected,
            "s4_t06_mu_R6_runtime_code_binding_drift",
        )

    frozen = authority["frozen_R6_admission"]
    identity = frozen_proof["fresh_identity"]
    _require(
        admission.admission_id == frozen["admission_id"]
        and admission.company == "MU"
        and admission.provider == frozen["provider"] == "deepseek"
        and admission.model == frozen["model"] == "deepseek-v4-pro"
        and admission.base_url
        == frozen["base_url"]
        == "https://api.deepseek.com/beta"
        and admission.input_digest == frozen["input_digest"]
        and admission.transport_ref
        == "fin01.s3.bounded_agent.deepseek_segmented_owner_grade_specialist:v8"
        and admission.task_claim_link_policy_ref
        == "fin01.s3.task_claim_link_policy:v1"
        and admission.wwc_judgment_atom_policy_ref
        == (
            "fin01.s4.specialist_WWC_judgment_atom_deterministic_"
            "temporal_authority:v2"
        )
        and admission.case_numeric_authority_policy_ref
        == frozen["case_numeric_authority_policy_ref"]
        and admission.case_delivery_identity_policy_ref
        == frozen["case_delivery_identity_policy_ref"]
        and admission.provider_output_capture_policy_ref
        == frozen["provider_output_capture_policy_ref"]
        and admission.retry_budget == 0
        and admission.max_transport_attempts_per_call == 1
        and admission.source_network_calls_allowed is False
        and admission.external_tool_calls_allowed is False
        and admission.live_business_case_head_writes_allowed is False,
        "s4_t06_mu_R6_admission_binding_mismatch",
    )

    provider_calls = 0

    def _must_not_call_provider(**_: Any) -> dict[str, Any]:
        nonlocal provider_calls
        provider_calls += 1
        raise AssertionError("provider_forbidden_during_R6_admission_issuance")

    build_s3_three_cell_bounded_agent_executor_for_admission(
        admission,
        chat_completion_fn=_must_not_call_provider,
    )
    _require(provider_calls == 0, "s4_t06_mu_R6_provider_called")

    canonical_root = RUNTIME_ROOT / "canonical-runtime"
    database_path = canonical_root / "canonical.sqlite"
    object_root = canonical_root / "objects"
    database_sha_before = _sha256(database_path)
    object_sha_before = _tree_digest(object_root)
    snapshot_before = _logical_snapshot(database_path, identity["case_id"])
    fresh_counts = _fresh_identity_counts(identity)
    _require(
        set(fresh_counts.values()) == {0},
        "s4_t06_mu_R6_identity_not_fresh",
    )

    maximum_output_tokens = (
        3 * admission.specialist_max_output_tokens
        + admission.lead_max_output_tokens
        + admission.writer_max_output_tokens
        + admission.verifier_max_output_tokens
    )
    issuance = {
        "schema_version": (
            "fin_ia_0_1_s4_t06_mu_temporal_authority_terminal_result_"
            "fresh_exact_admission_r6_issuance_v1_0"
        ),
        "issuance_id": (
            "S4-T06-MU-ACTION-PLANNING-TEMPORAL-AUTHORITY-AND-"
            "CAPTURE-V2-TERMINAL-RESULT-MATERIALIZATION-FRESH-EXACT-"
            "ADMISSION-R6-ISSUANCE"
        ),
        "issued_at": "2026-07-30T21:00:00+08:00",
        "status": EXPECTED_ISSUANCE_STATUS,
        "authority": {
            "user_instruction": "继续",
            "fresh_exact_R6_admission_issuance_authorized": True,
            "admission_consumption_or_exact_live_execution_authorized": False,
            "credential_presence_or_value_read_authorized": False,
            "model_provider_or_execution_network_calls_authorized": False,
            "paired_assessment_or_owner_acceptance_authorized": False,
            "S4_T07_or_later_authorized": False,
            "automatic_retry_fallback_replay_relaunch_R7_or_rerun_authorized": (
                False
            ),
        },
        "source_authority_ref": _display_path(AUTHORITY),
        "source_authority_sha256": EXPECTED_AUTHORITY_SHA256,
        "source_proof_decision_ref": _display_path(PROOF_DECISION),
        "source_proof_decision_sha256": EXPECTED_PROOF_SHA256,
        "issued_admission": {
            "admission_ref": _display_path(ADMISSION),
            "admission_id": admission.admission_id,
            "admission_digest": digest,
            "runtime_root": _display_path(RUNTIME_ROOT),
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
            "task_claim_link_policy_ref": admission.task_claim_link_policy_ref,
            "wwc_judgment_atom_policy_ref": (
                admission.wwc_judgment_atom_policy_ref
            ),
            "case_numeric_authority_policy_ref": (
                admission.case_numeric_authority_policy_ref
            ),
            "case_delivery_identity_policy_ref": (
                admission.case_delivery_identity_policy_ref
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
            "automatic_retry_fallback_replay_relaunch_R7_or_rerun_allowed": (
                False
            ),
            "first_new_L1_failure": (
                "terminal_fail_closed_block_agent_authored_surface_without_R7"
            ),
        },
        "proof_reverification": {
            "frozen_proof_regenerated_equal": True,
            "fresh_proof_sha256_match": True,
            "authority_sha256_match": True,
            "implementation_sha256_match": True,
            "proof_generator_sha256_match": True,
            "implementation_runtime_code_bindings_match": 5,
            "admission_schema_and_profile_admissible": True,
            "admission_roundtrip_digest_match": True,
            "R5_admission_and_failure_immutable": True,
            "issuance_scope_project_os_preflight": "pass_open_blockers_0",
            "fresh_identity_rows": fresh_counts,
            "target_database_sha256": database_sha_before,
            "target_object_tree_sha256": object_sha_before,
            "target_logical_snapshot_digest": canonical_digest(
                snapshot_before
            ),
        },
        "zero_call_preflight": {
            "provider_callback_invoked": False,
            "credential_presence_checked": False,
            "credential_value_read": False,
            "provider_health_probe_performed": False,
            "model_provider_network_source_tool_calls": [0, 0, 0, 0, 0],
        },
        "issuance_boundary": {
            "admission_issued": True,
            "admission_consumed": False,
            "execution_started": False,
            "supervisor_launched": False,
            "business_artifact_materialization_performed": False,
            "paired_assessment_performed": False,
            "owner_acceptance_performed": False,
            "S4_T07_entered": False,
        },
        "observed_counts": {
            "new_admissions": 1,
            "admission_consumptions": 0,
            "work_units_created": 0,
            "attempts_created": 0,
            "research_runs_created": 0,
            "artifacts_created": 0,
            "model_calls": 0,
            "provider_calls": provider_calls,
            "execution_network_calls": 0,
            "source_network_calls": 0,
            "external_tool_calls": 0,
            "credential_reads_or_probes": 0,
            "paired_assessments": 0,
            "owner_acceptances": 0,
            "T07_operations": 0,
        },
        "next_action": NEXT_ACTION,
    }
    _require(
        _sha256(database_path) == database_sha_before
        and _tree_digest(object_root) == object_sha_before
        and _logical_snapshot(database_path, identity["case_id"])
        == snapshot_before,
        "s4_t06_mu_R6_issuance_changed_target_runtime",
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
            prefix=".s4-t06-mu-R6-admission-",
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
            prefix=".s4-t06-mu-R6-issuance-",
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
            canonical_digest(loaded.digest_payload())
            == EXPECTED_ADMISSION_DIGEST,
            "s4_t06_mu_R6_runner_load_payload_mismatch",
        )
        os.replace(temporary_admission, ADMISSION)
        temporary_paths.remove(temporary_admission)
        os.replace(temporary_issuance, ISSUANCE)
        temporary_paths.remove(temporary_issuance)
    finally:
        for path in temporary_paths:
            path.unlink(missing_ok=True)


def verify_issued_admission() -> dict[str, Any]:
    proof = _load(PROOF_DECISION)
    payload = _load(ADMISSION)
    issuance = _load(ISSUANCE)
    _require(
        payload == proof["prospective_R6_admission"]["payload"],
        "s4_t06_mu_R6_issued_payload_not_frozen_payload",
    )
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(payload)
    admission.assert_profile_admissible()
    digest = canonical_digest(admission.digest_payload())
    _require(
        digest == EXPECTED_ADMISSION_DIGEST,
        "s4_t06_mu_R6_issued_admission_digest_mismatch",
    )
    target = load_execution_target(ISSUANCE)
    _load_admission(ADMISSION, target)
    fresh_counts = _fresh_identity_counts(proof["fresh_identity"])
    _require(
        set(fresh_counts.values()) == {0},
        "s4_t06_mu_R6_identity_consumed_before_execution",
    )
    _require(
        issuance["issuance_boundary"]["admission_consumed"] is False
        and issuance["issuance_boundary"]["execution_started"] is False,
        "s4_t06_mu_R6_issuance_boundary_invalid",
    )
    return {
        "status": EXPECTED_ISSUANCE_STATUS,
        "admission_id": admission.admission_id,
        "admission_digest": digest,
        "fresh_identity_rows": fresh_counts,
        "temporal_v2_specialist_v8_task_claim_capture_v2_numeric_v2_identity_v2_bound": (
            True
        ),
        "credential_checked": False,
        "provider_calls": 0,
        "next_action": NEXT_ACTION,
    }


def main() -> int:
    payload, issuance = render_issuance()
    _write_and_validate(payload, issuance)
    print(
        json.dumps(
            verify_issued_admission(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
