from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import hashlib
import json
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = ROOT / "scripts" / "releases"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import fin_ia_0_1_3_s2_06_supervisor_execution_support as r1_support  # noqa: E402
from fin_ia_0_1_3_s2_06_dell_r2_supervisor_execution_support import (  # noqa: E402
    ENTRYPOINT_IMPLEMENTATION_REF,
    SupervisorExecutionSupportError,
    compile_governed_admission,
    load_case_material,
    validate_admission_governance,
    validate_authority_and_bindings,
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_successor_authority_and_real_DELL_capacity_are_bound() -> None:
    authority = validate_authority_and_bindings()
    material = load_case_material("DELL")

    assert authority["authority"]["admission_issuance_eligible_now"] is False
    assert authority["case_capacity"]["DELL"] == material["observed_capacity"]
    assert material["observed_capacity"] == {
        "findings": 27,
        "corrections": 27,
        "node_directives": 6,
        "supervisor_request_characters": 33689,
        "corrected_graph_calls": 7,
        "provider_calls": 8,
        "pass": True,
    }
    assert material["spec"]["schema_version"].endswith("v1_1")
    assert material["spec"]["output_schema"]["properties"]["node_directives"][
        "items"
    ]["anyOf"] == [
        {"properties": {"evidence_ids": {"minItems": 1}}},
        {"properties": {"gap_ids": {"minItems": 1}}},
    ]


def test_successor_admission_binds_v1_1_proof_entrypoints_and_immutable_raw() -> None:
    material = load_case_material("DELL")
    admission = compile_governed_admission(
        material=material,
        corrected_run_id="fin013_s2_06_supervised_dell_r2_test",
        corrected_attempt_id="fin013_s2_06_supervised_dell_r2_test_attempt_1",
        admission_id="fin013-s2-06-dell-r2-supervisor-test",
        issued_at="2026-08-07T08:00:00Z",
        expires_at="2026-08-07T12:00:00Z",
        credential_present=True,
        execution_git_commit="a" * 40,
    )

    validate_admission_governance(
        admission,
        material=material,
        execution_git_commit="a" * 40,
    )
    binding = admission["governance_binding"]
    assert binding["supervisor_plan_schema_version"].endswith("v1_1")
    assert binding["case_expected_provider_calls"] == 8
    assert binding["retry_count"] == 0
    assert binding["fallback_count"] == 0
    assert binding["fresh_proof_result_digest"] == (
        "f1be7598c1afe72847fce503ddcf74636c8ce4f2ff57f046993dd06d64fefb4d"
    )
    assert binding["raw_outputs_digest"] == (
        "87f68f67de68aafb29c760b8b74aa17f86e01c7a781017fe4062350e9c04552d"
    )


def test_successor_admission_governance_mutation_fails_closed() -> None:
    material = load_case_material("DELL")
    admission = compile_governed_admission(
        material=material,
        corrected_run_id="fin013_s2_06_supervised_dell_r2_mutation",
        corrected_attempt_id="fin013_s2_06_supervised_dell_r2_mutation_attempt_1",
        admission_id="fin013-s2-06-dell-r2-supervisor-mutation",
        issued_at="2026-08-07T08:00:00Z",
        expires_at="2026-08-07T12:00:00Z",
        credential_present=True,
        execution_git_commit="b" * 40,
    )
    mutated = deepcopy(admission)
    mutated["governance_binding"]["supervisor_plan_schema_version"] = (
        "fin_ia_0_1_3_s2_06_supervisor_plan_v1_0"
    )

    with pytest.raises(
        SupervisorExecutionSupportError,
        match="s2_06_admission_digest_invalid",
    ):
        validate_admission_governance(
            mutated,
            material=material,
            execution_git_commit="b" * 40,
        )


def test_successor_loading_does_not_reactivate_consumed_R1_entrypoint() -> None:
    validate_authority_and_bindings()
    with pytest.raises(
        r1_support.SupervisorExecutionSupportError,
        match="s2_06_implementation_file_drift",
    ):
        r1_support.validate_authority_and_bindings()


def test_successor_entrypoint_implementation_record_is_digest_and_file_bound() -> None:
    implementation = _load(ROOT / ENTRYPOINT_IMPLEMENTATION_REF)
    body = {
        key: value
        for key, value in implementation.items()
        if key != "implementation_digest"
    }
    encoded = json.dumps(
        body,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    assert implementation["implementation_digest"] == hashlib.sha256(
        encoded
    ).hexdigest()
    for ref, expected in implementation["implementation_bindings"].items():
        assert _sha256(ROOT / ref) == expected
    assert implementation["verification"]["admissions_issued"] == 0
    assert implementation["verification"]["provider_calls"] == 0
    assert implementation["stage_acceptance"]["DELL_R2_execution"] is False
