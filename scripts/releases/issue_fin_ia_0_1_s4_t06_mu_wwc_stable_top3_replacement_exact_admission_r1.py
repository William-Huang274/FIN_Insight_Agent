from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from typing import Any, Mapping
from zoneinfo import ZoneInfo


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
from scripts.releases.prepare_fin_ia_0_1_s4_t06_mu_wwc_stable_top3_replacement_fresh_proof import (
    DECISION as PROOF_DECISION,
    IMPLEMENTATION,
    PROSPECTIVE_ADMISSION as ADMISSION,
    RUNTIME_ROOT,
)
from scripts.releases.run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution import (
    _load_admission,
    load_execution_target,
)
from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.project_os_preflight import run_project_os_preflight


ISSUANCE = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_wwc_stable_top3_"
    "replacement_exact_admission_r1_issuance_v1_0.json"
)
ISSUANCE_SCOPE = (
    "S4_T06_MU_WWC_STABLE_TOP3_REPLACEMENT_EXACT_ADMISSION_R1_ISSUANCE"
)
EXPECTED_PROOF_STATUS = (
    "pass_zero_call_double_disposable_runtime_WWC_stable_top3_fresh_"
    "proof_replacement_exact_live_authorized_by_user_sequence"
)
NEXT_ACTION = "S4-T06-MU-WWC-STABLE-TOP3-REPLACEMENT-EXACT-LIVE-R1"


class S4T06WWCStableTop3AdmissionIssuanceError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S4T06WWCStableTop3AdmissionIssuanceError(code)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _display(path: Path) -> str:
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
    _require(not ADMISSION.exists(), "replacement_admission_already_exists")
    _require(not ISSUANCE.exists(), "replacement_issuance_already_exists")

    proof = _load(PROOF_DECISION)
    _require(proof["status"] == EXPECTED_PROOF_STATUS, "proof_not_passed")
    _require(proof["next_action_authorized"] is True, "next_action_not_authorized")
    _require(
        proof["hard_boundaries"]
        == {
            "T07_entries": 0,
            "exact_live_runs": 0,
            "model_calls": 0,
            "network_calls": 0,
            "owner_acceptances": 0,
            "paired_assessments": 0,
            "provider_calls": 0,
            "source_network_calls": 0,
            "target_canonical_writes": 0,
            "target_object_writes": 0,
        },
        "proof_hard_boundary_mismatch",
    )
    _require(
        proof["double_prepare"]["equal"] is True
        and proof["target_read_only_audit"]["target_state_unchanged"] is True,
        "proof_freshness_or_read_only_audit_failed",
    )
    _require(
        proof["independent_fixture_reproof"][
            "three_case_positive_nodes_calls_captures_artifacts"
        ]
        == {
            "DELL": [6, 12, 12, 9],
            "MU": [6, 12, 12, 9],
            "NVDA": [6, 12, 12, 9],
        },
        "three_case_fixture_reproof_mismatch",
    )
    _require(
        _sha256(IMPLEMENTATION)
        == proof["implementation_reaudit"]["implementation_sha256"],
        "implementation_record_byte_drift",
    )
    for relative_path, expected_sha256 in proof["implementation_reaudit"][
        "exact_code_bindings"
    ].items():
        _require(
            _sha256(ROOT / relative_path) == expected_sha256,
            f"runtime_binding_byte_drift:{relative_path}",
        )

    preflight = run_project_os_preflight(ROOT, run_scope=ISSUANCE_SCOPE)
    _require(
        preflight["status"] == "pass"
        and preflight["open_full_chain_blockers"] == [],
        "issuance_project_os_preflight_not_passed",
    )

    prospective = proof["prospective_replacement_admission"]
    payload = prospective["payload"]
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(payload)
    admission.assert_profile_admissible()
    digest = canonical_digest(admission.digest_payload())
    _require(
        payload == admission.digest_payload()
        and digest == prospective["digest"],
        "admission_digest_or_roundtrip_mismatch",
    )
    _require(
        admission.company == "MU"
        and admission.provider == "deepseek"
        and admission.model == "deepseek-v4-pro"
        and admission.retry_budget == 0
        and admission.max_transport_attempts_per_call == 1
        and admission.max_provider_calls == 12
        and admission.live_business_case_head_writes_allowed is False,
        "replacement_admission_binding_mismatch",
    )

    provider_calls = 0

    def _must_not_call_provider(**_: Any) -> dict[str, Any]:
        nonlocal provider_calls
        provider_calls += 1
        raise AssertionError("provider_forbidden_during_admission_issuance")

    build_s3_three_cell_bounded_agent_executor_for_admission(
        admission,
        chat_completion_fn=_must_not_call_provider,
    )
    _require(provider_calls == 0, "provider_called_during_issuance")

    identity = proof["fresh_identity"]
    fresh_counts = _fresh_identity_counts(identity)
    _require(set(fresh_counts.values()) == {0}, "execution_identity_not_fresh")

    canonical_root = RUNTIME_ROOT / "canonical-runtime"
    database_path = canonical_root / "canonical.sqlite"
    object_root = canonical_root / "objects"
    database_sha_before = _sha256(database_path)
    object_sha_before = _tree_digest(object_root)
    snapshot_before = _logical_snapshot(database_path, identity["case_id"])

    maximum_output_tokens = (
        3 * admission.specialist_max_output_tokens
        + admission.lead_max_output_tokens
        + admission.writer_max_output_tokens
        + admission.verifier_max_output_tokens
    )
    issuance = {
        "schema_version": (
            "fin_ia_0_1_s4_t06_mu_wwc_stable_top3_replacement_exact_"
            "admission_r1_issuance_v1_0"
        ),
        "issuance_id": (
            "S4-T06-MU-WWC-STABLE-TOP3-REPLACEMENT-EXACT-ADMISSION-R1-"
            "ISSUANCE"
        ),
        "issued_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "status": "issued_unconsumed_zero_call_preflight_pass",
        "authority": {
            "user_instruction": "按照这个顺序修",
            "sequence_authorizes_one_replacement_exact_live": True,
            "automatic_second_replacement_or_R8_R9_loop_authorized": False,
            "new_L1_authorizes_one_project_level_disposition_only": True,
            "L2_to_L4_findings_carry_forward_without_blocking_T06": True,
        },
        "source_proof_decision_ref": _display(PROOF_DECISION),
        "source_proof_decision_sha256": _sha256(PROOF_DECISION),
        "issued_admission": {
            "admission_ref": _display(ADMISSION),
            "admission_id": admission.admission_id,
            "admission_digest": digest,
            "runtime_root": _display(RUNTIME_ROOT),
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
            "predicted_work_unit_id": identity["work_unit_id"],
            "predicted_attempt_id": identity["attempt_id"],
            "predicted_research_run_id": identity["research_run_id"],
            "provider": admission.provider,
            "model": admission.model,
            "model_ref": admission.model_ref,
            "base_url": admission.base_url,
            "credential_env": admission.api_key_env,
            "output_contract_ref": admission.output_contract_ref,
            "judgment_atom_compiled_contract_ref": (
                admission.judgment_atom_compiled_contract_ref
            ),
            "wwc_judgment_atom_policy_ref": admission.wwc_judgment_atom_policy_ref,
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
            "automatic_retry_fallback_replay_relaunch_allowed": False,
        },
        "proof_reverification": {
            "proof_status_match": True,
            "implementation_and_runtime_bindings_match": True,
            "three_case_fixture_reproof_match": True,
            "double_prepare_equal": True,
            "target_runtime_read_only": True,
            "admission_schema_profile_and_digest_match": True,
            "issuance_scope_project_os_preflight": "pass_open_blockers_0",
            "fresh_identity_rows": fresh_counts,
            "target_database_sha256": database_sha_before,
            "target_object_tree_sha256": object_sha_before,
            "target_logical_snapshot_digest": canonical_digest(snapshot_before),
        },
        "zero_call_preflight": {
            "provider_callback_invoked": False,
            "credential_value_read": False,
            "provider_health_probe_performed": False,
            "model_provider_network_source_tool_calls": [0, 0, 0, 0, 0],
        },
        "issuance_boundary": {
            "admission_issued": True,
            "admission_consumed": False,
            "execution_started": False,
            "supervisor_launched": False,
            "paired_assessment_performed": False,
            "owner_acceptance_performed": False,
            "S4_T07_entered": False,
        },
        "next_action": NEXT_ACTION,
    }
    _require(
        _sha256(database_path) == database_sha_before
        and _tree_digest(object_root) == object_sha_before
        and _logical_snapshot(database_path, identity["case_id"])
        == snapshot_before,
        "issuance_changed_target_runtime",
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
            prefix=".s4-t06-mu-stable-top3-admission-",
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
            prefix=".s4-t06-mu-stable-top3-issuance-",
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
            == issuance["issued_admission"]["admission_digest"],
            "runner_load_payload_mismatch",
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
    print(
        json.dumps(
            {
                "status": issuance["status"],
                "admission_id": issuance["issued_admission"]["admission_id"],
                "admission_digest": issuance["issued_admission"][
                    "admission_digest"
                ],
                "fresh_identity_rows": issuance["proof_reverification"][
                    "fresh_identity_rows"
                ],
                "provider_calls": 0,
                "next_action": NEXT_ACTION,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
