from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = ROOT / "scripts" / "releases"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from fin_ia_0_1_3_s2_06_supervisor_execution_support import (  # noqa: E402
    SupervisorExecutionSupportError,
    compile_governed_admission,
    load_case_material,
    validate_admission_governance,
    validate_authority_and_bindings,
)


def _times() -> tuple[str, str]:
    issued = datetime.now(timezone.utc).replace(microsecond=0)
    expires = issued + timedelta(hours=4)
    return (
        issued.isoformat().replace("+00:00", "Z"),
        expires.isoformat().replace("+00:00", "Z"),
    )


def test_dell_real_frozen_material_matches_authorized_capacity() -> None:
    authority = validate_authority_and_bindings()
    material = load_case_material("DELL")

    assert authority["case_capacity"]["DELL"] == material["observed_capacity"]
    assert material["observed_capacity"] == {
        "findings": 27,
        "corrections": 27,
        "node_directives": 6,
        "supervisor_request_characters": 33590,
        "corrected_graph_calls": 7,
        "provider_calls": 8,
        "pass": True,
    }
    severity_counts = {level: 0 for level in ("L1", "L2", "L3", "L4")}
    for finding in material["evaluation"]["findings"]:
        severity_counts[str(finding["severity"])] += 1
    assert severity_counts == {
        "L1": 3,
        "L2": 1,
        "L3": 23,
        "L4": 0,
    }


def test_governed_admission_binds_authority_runtime_raw_and_boundary() -> None:
    material = load_case_material("DELL")
    issued, expires = _times()
    admission = compile_governed_admission(
        material=material,
        corrected_run_id="test-supervised-dell",
        corrected_attempt_id="test-supervised-dell-attempt-1",
        admission_id="test-supervised-dell-admission",
        issued_at=issued,
        expires_at=expires,
        credential_present=True,
        execution_git_commit="a" * 40,
    )

    validate_admission_governance(
        admission,
        material=material,
        execution_git_commit="a" * 40,
    )
    assert admission["capacity_proof"]["provider_calls"] == 8
    assert admission["retry_count"] == 0
    assert admission["fallback_count"] == 0
    assert admission["provider_execution_authorized"] is True


def test_admission_governance_mutation_fails_closed() -> None:
    material = load_case_material("DELL")
    issued, expires = _times()
    admission = compile_governed_admission(
        material=material,
        corrected_run_id="test-supervised-dell",
        corrected_attempt_id="test-supervised-dell-attempt-1",
        admission_id="test-supervised-dell-admission",
        issued_at=issued,
        expires_at=expires,
        credential_present=True,
        execution_git_commit="b" * 40,
    )
    mutated = deepcopy(admission)
    mutated["governance_binding"]["raw_outputs_digest"] = "0" * 64

    with pytest.raises(
        SupervisorExecutionSupportError,
        match="s2_06_admission_digest_invalid",
    ):
        validate_admission_governance(
            mutated,
            material=material,
            execution_git_commit="b" * 40,
        )


def test_unknown_case_is_rejected_before_any_provider_work() -> None:
    with pytest.raises(
        SupervisorExecutionSupportError,
        match="s2_06_case_not_allowed",
    ):
        load_case_material("UNKNOWN")
