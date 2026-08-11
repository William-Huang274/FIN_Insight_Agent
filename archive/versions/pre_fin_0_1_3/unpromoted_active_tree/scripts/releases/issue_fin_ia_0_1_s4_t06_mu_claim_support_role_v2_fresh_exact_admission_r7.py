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
from scripts.releases.prepare_fin_ia_0_1_s4_t06_mu_claim_support_role_v2_fresh_proof import (
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
from sec_agent.project_os_preflight import run_project_os_preflight


AUTHORITY = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_claim_epistemic_support_role_"
    "compiled_contract_v2_fresh_exact_admission_authority_decision_v1_0.json"
)
IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_claim_epistemic_support_role_"
    "compiled_contract_v2_minimum_zero_call_implementation_v1_0.json"
)
PROOF_GENERATOR = ROOT / (
    "scripts/releases/prepare_fin_ia_0_1_s4_t06_mu_claim_support_role_"
    "v2_fresh_proof.py"
)
CANARY_RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_changed_contract_family_single_"
    "node_natural_output_canaries_exact_once_execution_result_v1_0.json"
)
ISSUANCE = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_claim_epistemic_support_role_"
    "compiled_contract_v2_fresh_exact_admission_r7_issuance_v1_0.json"
)
ISSUANCE_SCOPE = (
    "S4_T06_MU_CLAIM_EPISTEMIC_SUPPORT_ROLE_COMPILED_CONTRACT_V2_"
    "FRESH_EXACT_ADMISSION_R7_ISSUANCE"
)
EXPECTED_AUTHORITY_SHA256 = (
    "33c2a7b8ca96bb22aea9ce5b3b58d6791f538d24e4b4d32203f1dfaa8064873f"
)
EXPECTED_PROOF_SHA256 = (
    "1dd3d6eff30702ed8edf326d137ad1f0265f9c4145b11fcf0e6ba4aef7d78fb6"
)
EXPECTED_IMPLEMENTATION_SHA256 = (
    "0b727c201e4b93b5b60488341b90cb461cf8bc79f4c5e369aa5d91b6672b9cb9"
)
EXPECTED_PROOF_GENERATOR_SHA256 = (
    "d8192c40092f372d8ec46e4dc74a2c78b0d08753968375a6fc05d9542ec1ad67"
)
EXPECTED_CANARY_RESULT_SHA256 = (
    "410051c4dc94eb94c8d2f06fbc601e57dfc5b8e759cb6a938bbc17d99d7ae9bb"
)
EXPECTED_ADMISSION_DIGEST = (
    "4ed2a62d43c4bda4c0a41097b81dfc2dbd71151725fd12c6d1c9112c47077e75"
)
EXPECTED_ISSUANCE_STATUS = "issued_unconsumed_zero_call_preflight_pass"
NEXT_ACTION = (
    "S4-T06-MU-CLAIM-EPISTEMIC-SUPPORT-ROLE-COMPILED-CONTRACT-V2-"
    "R7-EXACT-LIVE-EXECUTION-AND-SUCCESS-ONLY-PAIRED-ASSESSMENT-"
    "AUTHORITY-DECISION"
)


class S4T06MuR7AdmissionIssuanceError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S4T06MuR7AdmissionIssuanceError(code)


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
                "SELECT COUNT(*) FROM canonical_work_units WHERE logical_id = ?",
                (identity["work_unit_id"],),
            ).fetchone()[0],
            "attempts": connection.execute(
                "SELECT COUNT(*) FROM canonical_attempts WHERE logical_id = ?",
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
    _require(not ADMISSION.exists(), "s4_t06_mu_R7_admission_already_exists")
    _require(not ISSUANCE.exists(), "s4_t06_mu_R7_issuance_already_exists")
    _require(
        _sha256(AUTHORITY) == EXPECTED_AUTHORITY_SHA256,
        "s4_t06_mu_R7_authority_byte_drift",
    )
    _require(
        _sha256(PROOF_DECISION) == EXPECTED_PROOF_SHA256,
        "s4_t06_mu_R7_proof_byte_drift",
    )
    _require(
        _sha256(IMPLEMENTATION) == EXPECTED_IMPLEMENTATION_SHA256,
        "s4_t06_mu_R7_implementation_byte_drift",
    )
    _require(
        _sha256(PROOF_GENERATOR) == EXPECTED_PROOF_GENERATOR_SHA256,
        "s4_t06_mu_R7_proof_generator_byte_drift",
    )
    _require(
        _sha256(CANARY_RESULT) == EXPECTED_CANARY_RESULT_SHA256,
        "s4_t06_mu_R7_immutable_canary_result_drift",
    )

    preflight = run_project_os_preflight(ROOT, run_scope=ISSUANCE_SCOPE)
    _require(
        preflight["status"] == "pass"
        and preflight["open_full_chain_blockers"] == [],
        "s4_t06_mu_R7_issuance_scope_preflight_not_passed",
    )

    authority = _load(AUTHORITY)
    _require(
        authority["decision_label"]
        == "authorize_frozen_R7_admission_issuance_only"
        and authority["authority"][
            "future_exact_R7_admission_issuance_authorized"
        ]
        is True
        and authority["authority"]["admission_consumption_authorized"]
        is False
        and authority["authority"]["R7_exact_live_execution_authorized"]
        is False
        and authority["next_action_authorized"] is True,
        "s4_t06_mu_R7_issuance_not_authorized",
    )

    frozen_proof = _load(PROOF_DECISION)
    _require(
        build_decision() == frozen_proof,
        "s4_t06_mu_R7_frozen_proof_regeneration_mismatch",
    )
    prospective = frozen_proof["prospective_R7_admission"]
    payload = prospective["payload"]
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(payload)
    admission.assert_profile_admissible()
    digest = canonical_digest(admission.digest_payload())
    _require(
        digest
        == prospective["digest"]
        == authority["frozen_R7_admission"]["admission_digest"]
        == EXPECTED_ADMISSION_DIGEST,
        "s4_t06_mu_R7_admission_digest_mismatch",
    )
    _require(
        payload == admission.digest_payload(),
        "s4_t06_mu_R7_persisted_payload_not_digest_payload",
    )
    for relative_path, expected in frozen_proof["implementation_reaudit"][
        "exact_code_bindings"
    ].items():
        _require(
            _sha256(ROOT / relative_path) == expected,
            "s4_t06_mu_R7_runtime_code_binding_drift",
        )

    frozen = authority["frozen_R7_admission"]
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
        and admission.judgment_atom_compiled_contract_ref
        == (
            "fin01.s4.deterministic_judgment_atom_planner_and_compiled_"
            "contract_invariants:v2"
        )
        and admission.transport_ref
        == "fin01.s3.bounded_agent.deepseek_segmented_owner_grade_specialist:v8"
        and admission.task_claim_link_policy_ref
        == "fin01.s3.task_claim_link_policy:v1"
        and admission.wwc_judgment_atom_policy_ref
        == (
            "fin01.s4.specialist_WWC_judgment_atom_deterministic_"
            "temporal_authority:v2"
        )
        and admission.retry_budget == 0
        and admission.max_transport_attempts_per_call == 1
        and admission.source_network_calls_allowed is False
        and admission.external_tool_calls_allowed is False
        and admission.live_business_case_head_writes_allowed is False,
        "s4_t06_mu_R7_admission_binding_mismatch",
    )

    provider_calls = 0

    def _must_not_call_provider(**_: Any) -> dict[str, Any]:
        nonlocal provider_calls
        provider_calls += 1
        raise AssertionError("provider_forbidden_during_R7_admission_issuance")

    build_s3_three_cell_bounded_agent_executor_for_admission(
        admission,
        chat_completion_fn=_must_not_call_provider,
    )
    _require(provider_calls == 0, "s4_t06_mu_R7_provider_called")

    canonical_root = RUNTIME_ROOT / "canonical-runtime"
    database_path = canonical_root / "canonical.sqlite"
    object_root = canonical_root / "objects"
    database_sha_before = _sha256(database_path)
    object_sha_before = _tree_digest(object_root)
    snapshot_before = _logical_snapshot(database_path, identity["case_id"])
    fresh_counts = _fresh_identity_counts(identity)
    _require(
        set(fresh_counts.values()) == {0},
        "s4_t06_mu_R7_identity_not_fresh",
    )

    maximum_output_tokens = (
        3 * admission.specialist_max_output_tokens
        + admission.lead_max_output_tokens
        + admission.writer_max_output_tokens
        + admission.verifier_max_output_tokens
    )
    issuance = {
        "schema_version": (
            "fin_ia_0_1_s4_t06_mu_claim_support_role_v2_fresh_exact_"
            "admission_r7_issuance_v1_0"
        ),
        "issuance_id": (
            "S4-T06-MU-CLAIM-EPISTEMIC-SUPPORT-ROLE-COMPILED-CONTRACT-"
            "V2-FRESH-EXACT-ADMISSION-R7-ISSUANCE"
        ),
        "issued_at": "2026-07-30T18:10:23+08:00",
        "status": EXPECTED_ISSUANCE_STATUS,
        "authority": {
            "user_instruction": "继续",
            "fresh_exact_R7_admission_issuance_authorized": True,
            "admission_consumption_or_exact_live_execution_authorized": False,
            "credential_presence_or_value_read_authorized": False,
            "model_provider_or_execution_network_calls_authorized": False,
            "second_claim_family_canary_authorized": False,
            "paired_assessment_or_owner_acceptance_authorized": False,
            "S4_T07_or_later_authorized": False,
            "automatic_retry_fallback_replay_relaunch_R8_or_rerun_authorized": (
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
            "research_lead_transport_ref": admission.research_lead_transport_ref,
            "memo_writer_transport_ref": admission.memo_writer_transport_ref,
            "judgment_atom_compiled_contract_ref": (
                admission.judgment_atom_compiled_contract_ref
            ),
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
            "automatic_retry_fallback_replay_relaunch_R8_or_rerun_allowed": (
                False
            ),
            "first_new_L1_failure": (
                "terminal_fail_closed_project_level_stop_without_R8"
            ),
        },
        "proof_reverification": {
            "frozen_proof_regenerated_equal": True,
            "fresh_proof_sha256_match": True,
            "authority_sha256_match": True,
            "implementation_sha256_match": True,
            "proof_generator_sha256_match": True,
            "implementation_code_test_bindings_match": 5,
            "compiled_contract_v2_bound": True,
            "admission_schema_and_profile_admissible": True,
            "admission_roundtrip_digest_match": True,
            "changed_family_canary_result_immutable": True,
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
            "second_claim_family_canaries": 0,
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
        "s4_t06_mu_R7_issuance_changed_target_runtime",
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
            prefix=".s4-t06-mu-R7-admission-",
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
            prefix=".s4-t06-mu-R7-issuance-",
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
            "s4_t06_mu_R7_runner_load_payload_mismatch",
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
        payload == proof["prospective_R7_admission"]["payload"],
        "s4_t06_mu_R7_issued_payload_not_frozen_payload",
    )
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(payload)
    admission.assert_profile_admissible()
    digest = canonical_digest(admission.digest_payload())
    _require(
        digest == EXPECTED_ADMISSION_DIGEST,
        "s4_t06_mu_R7_issued_admission_digest_mismatch",
    )
    target = load_execution_target(ISSUANCE)
    _load_admission(ADMISSION, target)
    fresh_counts = _fresh_identity_counts(proof["fresh_identity"])
    _require(
        set(fresh_counts.values()) == {0},
        "s4_t06_mu_R7_identity_consumed_before_execution",
    )
    _require(
        issuance["issuance_boundary"]["admission_consumed"] is False
        and issuance["issuance_boundary"]["execution_started"] is False,
        "s4_t06_mu_R7_issuance_boundary_invalid",
    )
    return {
        "status": EXPECTED_ISSUANCE_STATUS,
        "admission_id": admission.admission_id,
        "admission_digest": digest,
        "fresh_identity_rows": fresh_counts,
        "claim_compiled_contract_v2_bound": True,
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
