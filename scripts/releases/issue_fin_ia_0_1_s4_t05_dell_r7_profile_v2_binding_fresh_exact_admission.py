from __future__ import annotations

import argparse
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
from scripts.releases.prepare_fin_ia_0_1_s3_t09_paired_deterministic_baseline_decision import (
    _logical_snapshot,
    _sha256,
    _tree_digest,
)
from scripts.releases.prepare_fin_ia_0_1_s4_t05_dell_r7_profile_v2_binding_fresh_proof import (
    DECISION,
    PROSPECTIVE_ADMISSION as ADMISSION,
    RUNTIME_ROOT,
    build_decision,
)
from sec_agent.canonical_runtime.models import canonical_digest


ISSUANCE = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_r7_profile_v2_binding_"
    "fresh_exact_admission_issuance_v1_0.json"
)
ISSUANCE_TEST = ROOT / (
    "tests/contract/test_fin_0_1_s4_t05_dell_r7_profile_v2_binding_"
    "fresh_exact_admission_issuance.py"
)
NEXT_ACTION = (
    "S4-T05-DELL-R7-PROFILE-V2-BINDING-EXACT-LIVE-EXECUTION-AND-"
    "SUCCESS-ONLY-PAIRED-ASSESSMENT-AUTHORITY-DECISION"
)


class S4T05DellR7IssuanceError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S4T05DellR7IssuanceError(code)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _display(path: Path) -> str:
    resolved = path.resolve()
    return (
        resolved.relative_to(ROOT).as_posix()
        if resolved.is_relative_to(ROOT)
        else str(resolved)
    )


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    os.replace(temp_path, path)


def build_issuance() -> tuple[dict[str, Any], dict[str, Any]]:
    _require(not ADMISSION.exists(), "R7_admission_already_exists")
    _require(not ISSUANCE.exists(), "R7_issuance_already_exists")
    proof = _load(DECISION)
    _require(
        proof["status"]
        == "pass_zero_call_independent_R7_profile_v2_binding_"
        "fresh_proof_admission_issuance_pending",
        "R7_proof_status_invalid",
    )
    _require(build_decision() == proof, "R7_frozen_proof_not_reproducible")
    generator = proof["proof_generator"]
    contract_test = proof["proof_contract_test"]
    _require(
        _sha256(ROOT / generator["ref"]) == generator["sha256"]
        and _sha256(ROOT / contract_test["ref"]) == contract_test["sha256"],
        "R7_proof_code_or_test_binding_drift",
    )
    payload = proof["prospective_admission"]["payload"]
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(payload)
    admission.assert_profile_admissible()
    admission_digest = canonical_digest(admission.digest_payload())
    _require(
        admission_digest == proof["prospective_admission"]["digest"],
        "R7_admission_digest_mismatch",
    )

    provider_calls = 0

    def _forbidden_provider(**_: Any) -> dict[str, Any]:
        nonlocal provider_calls
        provider_calls += 1
        raise AssertionError("provider_forbidden_during_R7_issuance")

    build_s3_three_cell_bounded_agent_executor_for_admission(
        admission, chat_completion_fn=_forbidden_provider
    )
    _require(provider_calls == 0, "provider_called_during_R7_issuance")
    identity = proof["fresh_identity"]
    database_path = RUNTIME_ROOT / "canonical-runtime/canonical.sqlite"
    object_root = RUNTIME_ROOT / "canonical-runtime/objects"
    database_sha = _sha256(database_path)
    object_sha = _tree_digest(object_root)
    snapshot = _logical_snapshot(database_path, identity["case_id"])
    _require(
        identity["work_unit_id"] not in snapshot["work_unit_ids"]
        and identity["attempt_id"] not in snapshot["attempt_ids"]
        and identity["research_run_id"] not in snapshot["research_run_ids"],
        "R7_identity_consumed_before_issuance",
    )
    _require(
        database_sha == _sha256(database_path)
        and object_sha == _tree_digest(object_root),
        "R7_issuance_preflight_changed_runtime",
    )

    issuance = {
        "schema_version": (
            "fin_ia_0_1_s4_t05_dell_r7_profile_v2_binding_"
            "fresh_exact_admission_issuance_v1_0"
        ),
        "issuance_id": (
            "S4-T05-DELL-R7-PROFILE-V2-BINDING-FRESH-EXACT-"
            "ADMISSION-ISSUANCE-R1"
        ),
        "issued_at": "2026-07-27T23:40:00+08:00",
        "status": "issued_unconsumed_zero_call_preflight_pass",
        "source_proof_decision_ref": _display(DECISION),
        "source_proof_decision_sha256": _sha256(DECISION),
        "issued_admission": {
            "admission_id": admission.admission_id,
            "admission_digest": admission_digest,
            "admission_ref": _display(ADMISSION),
            "runtime_root": _display(RUNTIME_ROOT),
            "work_unit_idempotency_key": identity["execution_identity"],
            "issued": True,
            "consumed": False,
            "execution_started": False,
        },
        "exact_binding": {
            "case_id": identity["case_id"],
            "case_version": identity["case_version"],
            "decision_surface_contract_ref": (
                identity["decision_surface_contract_ref"]
            ),
            "input_digest": identity["input_digest"],
            "preparation_digest": identity["preparation_digest"],
            "role_group_mapping_digest": (
                identity["role_group_mapping_digest"]
            ),
            "evidence_alignment_digest": (
                identity["evidence_alignment_digest"]
            ),
            "evidence_dispatch_digest": (
                identity["evidence_dispatch_digest"]
            ),
            "predicted_work_unit_id": identity["work_unit_id"],
            "predicted_attempt_id": identity["attempt_id"],
            "predicted_research_run_id": identity["research_run_id"],
            "effective_runtime_binding_digest": proof[
                "implementation_reaudit"
            ]["effective_runtime_binding_digest"],
            "overlay_digest": proof["implementation_reaudit"][
                "overlay_digest"
            ],
        },
        "execution_envelope": {
            "provider": admission.provider,
            "model": admission.model,
            "maximum_semantic_model_calls": (
                admission.max_semantic_model_calls
            ),
            "maximum_provider_calls": admission.max_provider_calls,
            "maximum_network_calls": admission.max_network_calls,
            "maximum_output_tokens_total": (
                3 * admission.specialist_max_output_tokens
                + admission.lead_max_output_tokens
                + admission.writer_max_output_tokens
                + admission.verifier_max_output_tokens
            ),
            "maximum_total_cost_usd": admission.max_total_cost_usd,
            "transport_retry_count": admission.retry_budget,
            "source_network_calls_allowed": (
                admission.source_network_calls_allowed
            ),
            "external_tool_calls_allowed": (
                admission.external_tool_calls_allowed
            ),
            "live_business_case_head_writes_allowed": (
                admission.live_business_case_head_writes_allowed
            ),
        },
        "zero_call_preflight": {
            "fresh_proof_reproduced": True,
            "admission_schema_and_profile_valid": True,
            "executor_factory_constructed": True,
            "fresh_identity_absent": True,
            "target_database_unchanged": True,
            "target_object_tree_unchanged": True,
            "provider_callback_calls": provider_calls,
        },
        "issuance_boundary": {
            "admission_issued": True,
            "admission_consumed": False,
            "execution_started": False,
            "model_or_provider_call_started": False,
            "paired_assessment_performed": False,
            "S4_T06_entered": False,
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
    return admission.digest_payload(), issuance


def issue() -> dict[str, Any]:
    admission_payload, issuance = build_issuance()
    _write_json_atomic(ADMISSION, admission_payload)
    _write_json_atomic(ISSUANCE, issuance)
    return issuance


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    result = (
        {"status": "already_issued", "issuance": _load(ISSUANCE)}
        if args.verify_only and ISSUANCE.exists()
        else issue()
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
