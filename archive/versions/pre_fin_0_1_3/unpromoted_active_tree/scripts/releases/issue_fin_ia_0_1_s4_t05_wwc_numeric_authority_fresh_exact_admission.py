from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_contract_policies import (
    S3_TASK_CLAIM_LINK_POLICY_REF,
    S3_WHAT_WOULD_CHANGE_AUTHORITY_POLICY_REF,
    specialist_transport_contract,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    S3ThreeCellBoundedAgentAdmission,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from scripts.releases.prepare_fin_ia_0_1_s3_t09_paired_deterministic_baseline_decision import (
    _logical_snapshot,
    _tree_digest,
)
from scripts.releases.prepare_fin_ia_0_1_s4_t05_wwc_numeric_authority_surface_fresh_proof import (
    IMPLEMENTATION,
    PROSPECTIVE_ADMISSION as ADMISSION,
    RUNTIME_ROOT,
)
from scripts.releases.run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution import (
    _load_admission,
    load_execution_target,
)
from sec_agent.canonical_runtime.models import canonical_digest


PROOF_DECISION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_wwc_numeric_authority_surface_"
    "fresh_agent_proof_decision_v1_0.json"
)
ISSUANCE = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_wwc_numeric_authority_surface_"
    "fresh_exact_admission_issuance_v1_0.json"
)
EXPECTED_PROOF_SHA256 = (
    "d6289f700bd88c38d568f869303a4c3273156082b6b4ee01cb57335a5d5a5697"
)
EXPECTED_ADMISSION_DIGEST = (
    "45eef7b1150ee54b3680e69d98b0d8ba3db577dc1b4464649ff561a4e8354b8b"
)
EXPECTED_PROOF_STATUS = (
    "pass_zero_call_independent_fresh_proof_contract_frozen_"
    "admission_issuance_pending_separate_authority"
)
EXPECTED_ISSUANCE_STATUS = "issued_unconsumed_zero_call_preflight_pass"
NEXT_ACTION = (
    "S4-T05-DELL-WWC-NUMERIC-AUTHORITY-SURFACE-R4-EXACT-LIVE-"
    "EXECUTION-AND-SUCCESS-ONLY-PAIRED-ASSESSMENT-AUTHORITY-DECISION"
)


class S4T05WhatWouldChangeAuthorityAdmissionIssuanceError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S4T05WhatWouldChangeAuthorityAdmissionIssuanceError(code)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_issued_admission() -> dict[str, Any]:
    proof = _load(PROOF_DECISION)
    payload = _load(ADMISSION)
    issuance = _load(ISSUANCE)

    _require(
        _sha256(PROOF_DECISION) == EXPECTED_PROOF_SHA256,
        "s4_t05_WWC_authority_frozen_proof_byte_drift",
    )
    _require(
        proof["status"] == EXPECTED_PROOF_STATUS,
        "s4_t05_WWC_authority_frozen_proof_status_mismatch",
    )
    _require(
        payload == proof["prospective_admission"]["payload"],
        "s4_t05_WWC_authority_issued_payload_not_frozen_payload",
    )
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(payload)
    admission.assert_profile_admissible()
    digest = canonical_digest(admission.digest_payload())
    _require(
        digest
        == proof["prospective_admission"]["digest"]
        == EXPECTED_ADMISSION_DIGEST,
        "s4_t05_WWC_authority_admission_digest_mismatch",
    )
    _require(
        admission.task_claim_link_policy_ref
        == S3_TASK_CLAIM_LINK_POLICY_REF,
        "s4_t05_WWC_authority_task_claim_policy_not_preserved",
    )
    transport = specialist_transport_contract(admission.transport_ref)
    _require(
        transport.field_local_what_would_change_authority,
        "s4_t05_WWC_authority_v7_capability_not_bound",
    )
    _require(
        proof["WWC_authority_reproof"]["contract_ref"]
        == S3_WHAT_WOULD_CHANGE_AUTHORITY_POLICY_REF,
        "s4_t05_WWC_authority_policy_ref_mismatch",
    )
    _require(
        issuance["status"] == EXPECTED_ISSUANCE_STATUS,
        "s4_t05_WWC_authority_issuance_status_mismatch",
    )
    _require(
        issuance["source_proof_decision_sha256"]
        == EXPECTED_PROOF_SHA256,
        "s4_t05_WWC_authority_issuance_proof_binding_mismatch",
    )
    _require(
        issuance["issued_admission"]["admission_digest"] == digest,
        "s4_t05_WWC_authority_issuance_admission_binding_mismatch",
    )
    _require(
        issuance["next_action"] == NEXT_ACTION,
        "s4_t05_WWC_authority_issuance_next_action_mismatch",
    )

    target = load_execution_target(ISSUANCE)
    loaded = _load_admission(ADMISSION, target)
    _require(
        loaded.digest_payload() == admission.digest_payload(),
        "s4_t05_WWC_authority_runner_load_payload_mismatch",
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
    _require(
        provider_calls == 0,
        "provider_called_during_WWC_authority_admission_issuance",
    )

    identity = proof["fresh_identity"]
    canonical_root = RUNTIME_ROOT / "canonical-runtime"
    database_path = canonical_root / "canonical.sqlite"
    object_root = canonical_root / "objects"
    database_sha_before = _sha256(database_path)
    object_sha_before = _tree_digest(object_root)
    snapshot = _logical_snapshot(database_path, identity["case_id"])
    _require(
        identity["work_unit_id"] not in snapshot["work_unit_ids"],
        "s4_t05_WWC_authority_work_unit_consumed_before_authority",
    )
    _require(
        identity["attempt_id"] not in snapshot["attempt_ids"],
        "s4_t05_WWC_authority_attempt_consumed_before_authority",
    )
    _require(
        identity["research_run_id"] not in snapshot["research_run_ids"],
        "s4_t05_WWC_authority_research_run_consumed_before_authority",
    )
    for prior_run_id in proof["freshness_and_nonreuse"][
        "prior_research_run_ids"
    ]:
        _require(
            prior_run_id in snapshot["research_run_ids"],
            f"s4_t05_WWC_authority_historical_run_missing:{prior_run_id}",
        )
    _require(
        _sha256(database_path) == database_sha_before
        and _tree_digest(object_root) == object_sha_before,
        "s4_t05_WWC_authority_issuance_changed_target_runtime",
    )
    _require(
        _sha256(IMPLEMENTATION)
        == proof["implementation_reaudit"][
            "implementation_contract_sha256"
        ],
        "s4_t05_WWC_authority_implementation_binding_drift",
    )
    for relative_path, expected_digest in proof[
        "implementation_reaudit"
    ]["exact_code_bindings"].items():
        _require(
            _sha256(ROOT / relative_path) == expected_digest,
            f"s4_t05_WWC_authority_runtime_binding_drift:{relative_path}",
        )

    boundary = issuance["issuance_boundary"]
    counts = issuance["observed_counts"]
    _require(
        boundary["admission_issued"] is True
        and boundary["admission_consumed"] is False
        and boundary["execution_started"] is False
        and boundary["model_or_provider_call_started"] is False,
        "s4_t05_WWC_authority_issuance_boundary_mismatch",
    )
    _require(
        counts["new_admissions"] == 1
        and all(
            counts[key] == 0
            for key in (
                "admission_consumptions",
                "work_units_created",
                "attempts_created",
                "research_runs_created",
                "artifacts_created",
                "model_calls",
                "provider_calls",
                "execution_network_calls",
                "source_network_calls",
                "external_tool_calls",
            )
        ),
        "s4_t05_WWC_authority_issuance_counts_mismatch",
    )
    return {
        "status": EXPECTED_ISSUANCE_STATUS,
        "admission_id": admission.admission_id,
        "admission_digest": digest,
        "fresh_identity_absent": True,
        "prior_runs_preserved": True,
        "provider_calls": provider_calls,
        "next_action": NEXT_ACTION,
    }


def main() -> int:
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
