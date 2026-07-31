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

from apps.workbench.backend.application.bounded_agent_contract_policies import (
    S4_CASE_DELIVERY_IDENTITY_POLICY_REF,
    S4_CASE_NUMERIC_AUTHORITY_POLICY_REF,
    S4_CASE_RUNTIME_MANDATORY_MATERIAL_TRUTH_IDENTITY_SAFETY_REF,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    S3ThreeCellBoundedAgentAdmission,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from scripts.releases.prepare_fin_ia_0_1_s3_t09_paired_deterministic_baseline_decision import (
    _logical_snapshot,
    _tree_digest,
)
from scripts.releases.prepare_fin_ia_0_1_s4_t06_mu_mandatory_material_truth_identity_safety_fresh_proof import (
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


ISSUANCE = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t06_mu_mandatory_material_truth_identity_safety_"
    "closure_fresh_exact_admission_issuance_v1_0.json"
)
EXPECTED_PROOF_SHA256 = (
    "aae7a34e991bfd5a267c5cab9944a99ed06d543e95aedd629692d9d56a6952b0"
)
EXPECTED_ADMISSION_DIGEST = (
    "da4c91eb69499ab197332e2f263556f5528b66e451c33be54e925b20924632a5"
)
EXPECTED_ISSUANCE_STATUS = "issued_unconsumed_zero_call_preflight_pass"
NEXT_ACTION = (
    "S4-T06-MU-MANDATORY-MATERIAL-TRUTH-AND-IDENTITY-SAFETY-"
    "CLOSURE-R3-EXACT-LIVE-EXECUTION"
)
CODE_BINDING_PATHS = (
    Path("apps/workbench/backend/application/bounded_agent_contract_policies.py"),
    Path("apps/workbench/backend/application/bounded_agent_executor.py"),
    Path("apps/workbench/backend/application/research_runtime.py"),
    Path(
        "scripts/releases/"
        "prepare_fin_ia_0_1_s4_t06_mu_mandatory_material_truth_"
        "identity_safety_fresh_proof.py"
    ),
    Path(
        "scripts/releases/"
        "run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution.py"
    ),
    Path(
        "scripts/releases/"
        "issue_fin_ia_0_1_s4_t06_mu_mandatory_material_truth_"
        "identity_safety_fresh_exact_admission.py"
    ),
)


class S4T06MuSafetyAdmissionIssuanceError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S4T06MuSafetyAdmissionIssuanceError(code)


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


def _exact_code_bindings() -> dict[str, str]:
    return {
        path.as_posix(): _sha256(ROOT / path)
        for path in CODE_BINDING_PATHS
    }


def render_issuance() -> tuple[dict[str, Any], dict[str, Any]]:
    _require(not ADMISSION.exists(), "s4_t06_mu_R3_admission_already_exists")
    _require(not ISSUANCE.exists(), "s4_t06_mu_R3_issuance_already_exists")
    _require(
        _sha256(PROOF_DECISION) == EXPECTED_PROOF_SHA256,
        "s4_t06_mu_R3_frozen_proof_byte_drift",
    )
    frozen = _load(PROOF_DECISION)
    regenerated = build_decision()
    _require(
        regenerated == frozen,
        "s4_t06_mu_R3_frozen_proof_regeneration_mismatch",
    )
    prospective = frozen["prospective_admission"]
    payload = prospective["payload"]
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(payload)
    admission.assert_profile_admissible()
    digest = canonical_digest(admission.digest_payload())
    _require(
        digest
        == prospective["digest"]
        == EXPECTED_ADMISSION_DIGEST,
        "s4_t06_mu_R3_admission_digest_mismatch",
    )
    _require(
        admission.company == "MU"
        and admission.provider == "deepseek"
        and admission.model == "deepseek-v4-pro"
        and admission.base_url == "https://api.deepseek.com/beta"
        and admission.case_numeric_authority_policy_ref
        == S4_CASE_NUMERIC_AUTHORITY_POLICY_REF
        and admission.case_delivery_identity_policy_ref
        == S4_CASE_DELIVERY_IDENTITY_POLICY_REF
        and admission.retry_budget == 0
        and admission.max_transport_attempts_per_call == 1
        and admission.source_network_calls_allowed is False
        and admission.external_tool_calls_allowed is False
        and admission.live_business_case_head_writes_allowed is False,
        "s4_t06_mu_R3_admission_binding_mismatch",
    )
    provider_calls = 0

    def _must_not_call_provider(**_: Any) -> dict[str, Any]:
        nonlocal provider_calls
        provider_calls += 1
        raise AssertionError("provider_forbidden_during_R3_admission_issuance")

    build_s3_three_cell_bounded_agent_executor_for_admission(
        admission,
        chat_completion_fn=_must_not_call_provider,
    )
    _require(provider_calls == 0, "s4_t06_mu_R3_provider_called")

    identity = frozen["fresh_identity"]
    canonical_root = RUNTIME_ROOT / "canonical-runtime"
    database_path = canonical_root / "canonical.sqlite"
    object_root = canonical_root / "objects"
    database_sha_before = _sha256(database_path)
    object_sha_before = _tree_digest(object_root)
    snapshot_before = _logical_snapshot(database_path, identity["case_id"])
    _require(
        identity["work_unit_id"] not in snapshot_before["work_unit_ids"]
        and identity["attempt_id"] not in snapshot_before["attempt_ids"]
        and identity["research_run_id"]
        not in snapshot_before["research_run_ids"],
        "s4_t06_mu_R3_identity_not_fresh",
    )

    maximum_output_tokens = (
        3 * admission.specialist_max_output_tokens
        + admission.lead_max_output_tokens
        + admission.writer_max_output_tokens
        + admission.verifier_max_output_tokens
    )
    issuance = {
        "schema_version": (
            "fin_ia_0_1_s4_t06_mu_mandatory_material_truth_identity_"
            "safety_closure_fresh_exact_admission_issuance_v1_0"
        ),
        "issuance_id": (
            "S4-T06-MU-MANDATORY-MATERIAL-TRUTH-AND-IDENTITY-SAFETY-"
            "CLOSURE-FRESH-EXACT-ADMISSION-ISSUANCE-R3"
        ),
        "issued_at": "2026-07-29T23:55:00+08:00",
        "status": EXPECTED_ISSUANCE_STATUS,
        "authority": {
            "user_instruction": "按这个顺序往下做，我授权你做1-6点",
            "continuous_sequence_authority": True,
            "exact_once_execution_authorized_after_zero_call_preflight": True,
            "retry_fallback_patch_or_rerun_authorized": False,
        },
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
            "case_runtime_safety_profile_ref": (
                S4_CASE_RUNTIME_MANDATORY_MATERIAL_TRUTH_IDENTITY_SAFETY_REF
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
            "automatic_retry_repair_fallback_or_rerun_allowed": False,
            "first_credible_failure": "terminal_fail_closed_stop",
        },
        "proof_reverification": {
            "generator_rerun_before_materialization": True,
            "frozen_and_regenerated_decision_equal": True,
            "independent_proof_invocations": 2,
            "fresh_identity_absent": True,
            "three_case_path_and_mutation_reproof": True,
            "target_database_sha256": database_sha_before,
            "target_object_tree_sha256": object_sha_before,
            "target_logical_snapshot_digest": canonical_digest(
                snapshot_before
            ),
            "exact_code_bindings": _exact_code_bindings(),
            "runner_load_preflight_required": True,
        },
        "zero_call_preflight": {
            "provider_callback_invoked": False,
            "credential_presence_checked": False,
            "model_provider_network_source_tool_calls": [0, 0, 0, 0, 0],
        },
        "issuance_boundary": {
            "admission_issued": True,
            "admission_consumed": False,
            "execution_started": False,
            "supervisor_launched": False,
            "business_artifact_materialization_performed": False,
            "paired_comparison_performed": False,
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
            "provider_calls": provider_calls,
            "execution_network_calls": 0,
            "source_network_calls": 0,
            "external_tool_calls": 0,
        },
        "next_action": NEXT_ACTION,
    }
    _require(
        _sha256(database_path) == database_sha_before
        and _tree_digest(object_root) == object_sha_before
        and _logical_snapshot(database_path, identity["case_id"])
        == snapshot_before,
        "s4_t06_mu_R3_issuance_changed_target_runtime",
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
            prefix=".s4-t06-mu-R3-admission-",
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
            prefix=".s4-t06-mu-R3-issuance-",
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
            "s4_t06_mu_R3_runner_load_payload_mismatch",
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
        payload == proof["prospective_admission"]["payload"],
        "s4_t06_mu_R3_issued_payload_not_frozen_payload",
    )
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(payload)
    digest = canonical_digest(admission.digest_payload())
    _require(
        digest == EXPECTED_ADMISSION_DIGEST,
        "s4_t06_mu_R3_issued_admission_digest_mismatch",
    )
    target = load_execution_target(ISSUANCE)
    _load_admission(ADMISSION, target)
    identity = proof["fresh_identity"]
    snapshot = _logical_snapshot(
        RUNTIME_ROOT / "canonical-runtime/canonical.sqlite",
        identity["case_id"],
    )
    _require(
        identity["work_unit_id"] not in snapshot["work_unit_ids"]
        and identity["attempt_id"] not in snapshot["attempt_ids"]
        and identity["research_run_id"] not in snapshot["research_run_ids"],
        "s4_t06_mu_R3_identity_consumed_before_execution",
    )
    return {
        "status": EXPECTED_ISSUANCE_STATUS,
        "admission_id": admission.admission_id,
        "admission_digest": digest,
        "fresh_identity_absent": True,
        "safety_pair_bound": True,
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
