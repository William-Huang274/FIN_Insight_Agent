from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest  # noqa: E402


AUTHORITY_REF = (
    "configs/releases/"
    "fin_ia_0_1_3_s2_06_dell_replacement_"
    "supervisor_authority_decision_v1_0.json"
)
CONTRACT_IMPLEMENTATION_REF = (
    "configs/releases/"
    "fin_ia_0_1_3_s2_06_supervisor_nonempty_"
    "case_authority_compiled_contract_alignment_v1_1.json"
)
EXPECTED_SUPERVISOR_PLAN_SPEC_SCHEMA = (
    "fin_ia_0_1_3_s2_06_supervisor_plan_spec_v1_1"
)
FRESH_PROOF_REF = (
    "configs/releases/"
    "fin_ia_0_1_3_s2_06_supervisor_contract_v1_1_"
    "independent_fresh_zero_call_proof_result_v1_0.json"
)
ENTRYPOINT_IMPLEMENTATION_REF = (
    "configs/releases/"
    "fin_ia_0_1_3_s2_06_dell_r2_supervisor_"
    "successor_entrypoint_zero_call_implementation_v1_0.json"
)
SUPPORT_REF = (
    "scripts/releases/"
    "fin_ia_0_1_3_s2_06_dell_r2_supervisor_execution_support.py"
)
ISSUER_REF = (
    "scripts/releases/"
    "issue_fin_ia_0_1_3_s2_06_dell_r2_supervisor_admission.py"
)
RUNNER_REF = (
    "scripts/releases/"
    "run_fin_ia_0_1_3_s2_06_dell_r2_supervisor.py"
)
TEST_REF = (
    "tests/contract/"
    "test_fin_0_1_3_s2_06_dell_r2_supervisor_successor_entrypoint.py"
)
LEGACY_SUPPORT_REF = (
    "scripts/releases/fin_ia_0_1_3_s2_06_supervisor_execution_support.py"
)


def _load_legacy_support() -> Any:
    path = ROOT / LEGACY_SUPPORT_REF
    spec = importlib.util.spec_from_file_location(
        "fin_ia_0_1_3_s2_06_dell_r2_isolated_legacy_support",
        path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("s2_06_dell_r2_legacy_support_load_failed")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_legacy = _load_legacy_support()
SupervisorExecutionSupportError = _legacy.SupervisorExecutionSupportError
SUPERVISOR_ROOT = _legacy.SUPERVISOR_ROOT
SHARED_LEDGER = _legacy.SHARED_LEDGER
RAW_RUN_ROOT = _legacy.RAW_RUN_ROOT
CASE_RUNS = deepcopy(_legacy.CASE_RUNS)

_legacy.AUTHORITY_REF = AUTHORITY_REF
_legacy.IMPLEMENTATION_REF = CONTRACT_IMPLEMENTATION_REF
_legacy.SUPPORT_REF = SUPPORT_REF
_legacy.ISSUER_REF = ISSUER_REF
_legacy.RUNNER_REF = RUNNER_REF


def load_json(path: Path) -> dict[str, Any]:
    return _legacy.load_json(path)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validated_digest_record(
    ref: str,
    *,
    digest_field: str,
    expected_digest: str,
) -> dict[str, Any]:
    value = load_json(ROOT / ref)
    body = {key: item for key, item in value.items() if key != digest_field}
    if (
        str(value.get(digest_field) or "") != expected_digest
        or canonical_digest(body) != expected_digest
    ):
        raise SupervisorExecutionSupportError(
            "s2_06_dell_r2_bound_record_digest_drift:" + ref
        )
    return value


def _validate_entrypoint_implementation() -> dict[str, Any]:
    implementation = load_json(ROOT / ENTRYPOINT_IMPLEMENTATION_REF)
    body = {
        key: value
        for key, value in implementation.items()
        if key != "implementation_digest"
    }
    if implementation.get("implementation_digest") != canonical_digest(body):
        raise SupervisorExecutionSupportError(
            "s2_06_dell_r2_entrypoint_implementation_digest_drift"
        )
    for ref, expected in implementation["implementation_bindings"].items():
        if sha256(ROOT / ref) != str(expected):
            raise SupervisorExecutionSupportError(
                "s2_06_dell_r2_entrypoint_file_drift:" + ref
            )
    return implementation


def validate_authority_and_bindings() -> dict[str, Any]:
    authority = load_json(ROOT / AUTHORITY_REF)
    body = {key: value for key, value in authority.items() if key != "decision_digest"}
    auth = authority.get("authority") or {}
    contract = authority.get("replacement_contract") or {}
    if (
        authority.get("decision_digest") != canonical_digest(body)
        or authority.get("status")
        != "authority_pass_one_DELL_replacement_eligible_successor_entrypoint_required_admission_unissued_execution_not_started"
        or auth.get("decision_outcome")
        != "approve_one_DELL_replacement_after_successor_entrypoint_clean_synced_preflight"
        or auth.get("successor_entrypoint_implementation_required") is not True
        or auth.get("automatic_execution_from_this_decision") is not False
        or auth.get("automatic_R3_if_R2_fails") is not False
        or auth.get("MU_NVDA_execution_authorized") is not False
        or contract.get("case_key") != "DELL"
        or contract.get("R1_reuse_forbidden") is not True
        or contract.get("expected_provider_calls") != 8
        or contract.get("hard_provider_call_ceiling") != 11
        or contract.get("retry_count") != 0
        or contract.get("fallback_count") != 0
    ):
        raise SupervisorExecutionSupportError(
            "s2_06_dell_r2_replacement_authority_invalid"
        )

    evidence = authority.get("evidence_binding") or {}
    for name in (
        "R1_terminal_disposition",
        "successor_contract_implementation",
        "independent_fresh_proof",
    ):
        binding = evidence.get(name) or {}
        ref = str(binding.get("ref") or "")
        expected = str(binding.get("sha256") or "")
        if not ref or not expected or sha256(ROOT / ref) != expected:
            raise SupervisorExecutionSupportError(
                "s2_06_dell_r2_authority_evidence_binding_drift:" + name
            )

    contract_binding = evidence["successor_contract_implementation"]
    contract_implementation = _validated_digest_record(
        str(contract_binding["ref"]),
        digest_field="implementation_digest",
        expected_digest=str(contract_binding["implementation_digest"]),
    )
    proof_binding = evidence["independent_fresh_proof"]
    proof = _validated_digest_record(
        str(proof_binding["ref"]),
        digest_field="result_digest",
        expected_digest=str(proof_binding["result_digest"]),
    )
    if (
        proof["acceptance_boundary"]["RC_P36_147_engineering_repair"]
        != "independent_fresh_proof_pass"
        or proof["acceptance_boundary"]["DELL_replacement_authority"] is not False
        or proof["observed_counts"]["provider_calls"] != 0
        or contract_implementation["contract_alignment"][
            "supervisor_plan_schema_version"
        ]
        != "fin_ia_0_1_3_s2_06_supervisor_plan_v1_1"
    ):
        raise SupervisorExecutionSupportError(
            "s2_06_dell_r2_successor_contract_or_proof_invalid"
        )
    _validate_entrypoint_implementation()

    matrix = proof["independent_proof"]["worker_result"][
        "real_frozen_input_matrix"
    ]["DELL"]
    projected = deepcopy(authority)
    projected["case_capacity"] = {
        "DELL": {
            "findings": int(matrix["finding_count"]),
            "corrections": int(matrix["correction_count"]),
            "node_directives": int(matrix["node_directives"]),
            "supervisor_request_characters": int(
                matrix["supervisor_request_characters"]
            ),
            "corrected_graph_calls": int(matrix["corrected_graph_calls"]),
            "provider_calls": int(matrix["provider_calls"]),
            "pass": True,
        }
    }
    return projected


def expected_governance_binding(
    *, material: Mapping[str, Any], execution_git_commit: str
) -> dict[str, Any]:
    authority = material["authority"]
    contract_implementation = load_json(ROOT / CONTRACT_IMPLEMENTATION_REF)
    entrypoint_implementation = _validate_entrypoint_implementation()
    return {
        "authority_ref": AUTHORITY_REF,
        "authority_decision_digest": authority["decision_digest"],
        "contract_implementation_ref": CONTRACT_IMPLEMENTATION_REF,
        "contract_implementation_digest": contract_implementation[
            "implementation_digest"
        ],
        "fresh_proof_ref": FRESH_PROOF_REF,
        "fresh_proof_result_digest": authority["evidence_binding"][
            "independent_fresh_proof"
        ]["result_digest"],
        "successor_entrypoint_implementation_ref": ENTRYPOINT_IMPLEMENTATION_REF,
        "successor_entrypoint_implementation_digest": entrypoint_implementation[
            "implementation_digest"
        ],
        "execution_git_commit": execution_git_commit,
        "policy_ref": _legacy.POLICY_REF,
        "policy_sha256": material["policy_sha256"],
        "execution_entrypoint_bindings": {
            SUPPORT_REF: sha256(ROOT / SUPPORT_REF),
            ISSUER_REF: sha256(ROOT / ISSUER_REF),
            RUNNER_REF: sha256(ROOT / RUNNER_REF),
        },
        "raw_outputs_digest": material["raw_outputs_digest"],
        "evaluation_digest": material["evaluation_digest"],
        "boundary_digest": material["boundary_digest"],
        "supervisor_plan_schema_version": (
            "fin_ia_0_1_3_s2_06_supervisor_plan_v1_1"
        ),
        "case_expected_provider_calls": material["capacity"]["provider_calls"],
        "retry_count": 0,
        "fallback_count": 0,
    }


_legacy.validate_authority_and_bindings = validate_authority_and_bindings
_legacy.expected_governance_binding = expected_governance_binding


def validate_repository() -> str:
    return _legacy.validate_repository()


def load_case_material(case_key: str) -> dict[str, Any]:
    material = _legacy.load_case_material(case_key)
    if (
        material.get("spec", {}).get("schema_version")
        != EXPECTED_SUPERVISOR_PLAN_SPEC_SCHEMA
    ):
        raise SupervisorExecutionSupportError(
            "s2_06_dell_r2_successor_contract_superseded"
        )
    return material


def compile_governed_admission(
    *,
    material: Mapping[str, Any],
    corrected_run_id: str,
    corrected_attempt_id: str,
    admission_id: str,
    issued_at: str,
    expires_at: str,
    credential_present: bool,
    execution_git_commit: str,
) -> dict[str, Any]:
    return _legacy.compile_governed_admission(
        material=material,
        corrected_run_id=corrected_run_id,
        corrected_attempt_id=corrected_attempt_id,
        admission_id=admission_id,
        issued_at=issued_at,
        expires_at=expires_at,
        credential_present=credential_present,
        execution_git_commit=execution_git_commit,
    )


def validate_admission_governance(
    admission: Mapping[str, Any],
    *,
    material: Mapping[str, Any],
    execution_git_commit: str,
) -> None:
    _legacy.validate_admission_governance(
        admission,
        material=material,
        execution_git_commit=execution_git_commit,
    )
