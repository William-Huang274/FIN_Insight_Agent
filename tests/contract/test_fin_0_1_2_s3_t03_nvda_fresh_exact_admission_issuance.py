from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (
    S3ThreeCellBoundedAgentAdmission,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from apps.workbench.backend.application.fin_0_1_2_s3_t03_exact_live_runner import (
    Fin012S3T03RunnerError,
    load_bound_s3_t03_execution_envelope,
)
from scripts.releases.issue_fin_ia_0_1_2_s3_t03_nvda_fresh_exact_admission import (
    ADMISSION,
    EXPECTED_ADMISSION_DIGEST,
    ISSUANCE,
    NEXT_ACTION,
    RUNTIME_ROOT,
)
from sec_agent.canonical_runtime.models import canonical_digest


POST_ADMISSION_AUTHORITY_BLOCKED_NEXT = (
    "FIN-0.1.2-S3-T03-NVDA-BOUND-EXECUTION-LAUNCHER-PARENT-"
    "SUPERVISOR-AND-ZERO-CALL-PREFLIGHT-MINIMUM-IMPLEMENTATION"
)
LAUNCHER_SUPERVISOR_PASS_NEXT = (
    "FIN-0.1.2-S3-T03-NVDA-EXACT-LIVE-EXECUTION-AUTHORITY-DECISION-R2"
)
LAUNCHER_SUPERVISOR_IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_2_s3_t03_nvda_bound_execution_launcher_"
    "parent_supervisor_zero_call_preflight_minimum_implementation_v1_0.json"
)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_admission_is_issued_unconsumed_and_exactly_envelope_bound() -> None:
    issuance = _load(ISSUANCE)
    envelope = load_bound_s3_t03_execution_envelope(ROOT)
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(_load(ADMISSION))
    admission.assert_profile_admissible()

    assert issuance["status"] == "issued_unconsumed_zero_call_preflight_pass"
    assert canonical_digest(admission.digest_payload()) == EXPECTED_ADMISSION_DIGEST
    assert issuance["issued_admission"]["admission_digest"] == (
        EXPECTED_ADMISSION_DIGEST
    )
    assert admission.input_digest == envelope["fresh_t03"]["input_digest"]
    assert issuance["execution_envelope"]["envelope_digest"] == (
        envelope["envelope_digest"]
    )
    assert admission.runtime_contract_family_binding_ref == (
        envelope["runtime_contract"]["binding_ref"]
    )
    assert issuance["issued_admission"]["consumed"] is False
    assert issuance["issued_admission"]["execution_started"] is False


def test_issuance_did_not_claim_identity_or_access_execution_surfaces() -> None:
    issuance = _load(ISSUANCE)
    boundary = issuance["issuance_boundary"]
    counts = issuance["observed_counts"]

    assert not RUNTIME_ROOT.exists()
    assert boundary["admission_issued"]
    assert not boundary["admission_consumed"]
    assert not boundary["execution_identity_claimed"]
    assert not boundary["execution_started"]
    assert not boundary["supervisor_launched"]
    assert not boundary["model_or_provider_call_started"]
    assert counts == {
        "new_admissions": 1,
        "admission_consumptions": 0,
        "work_units_created": 0,
        "attempts_created": 0,
        "research_runs_created": 0,
        "artifacts_created": 0,
        "model_calls": 0,
        "provider_calls": 0,
        "execution_network_calls": 0,
        "source_network_calls": 0,
        "external_tool_calls": 0,
    }
    assert not issuance["zero_call_preflight"]["credential_presence_checked"]
    assert not issuance["zero_call_preflight"][
        "credential_value_read_output_or_persisted"
    ]


def test_executor_wiring_is_constructible_without_provider_call() -> None:
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(_load(ADMISSION))
    callback_calls = 0

    def forbidden(**_: Any) -> dict[str, Any]:
        nonlocal callback_calls
        callback_calls += 1
        raise AssertionError("provider callback invoked by executor construction")

    build_s3_three_cell_bounded_agent_executor_for_admission(
        admission,
        chat_completion_fn=forbidden,
    )
    assert callback_calls == 0


def test_issuance_bindings_are_immutable_or_have_an_exact_current_successor() -> None:
    issuance = _load(ISSUANCE)
    implementation = _load(LAUNCHER_SUPERVISOR_IMPLEMENTATION)
    for row in issuance["source_bindings"]:
        assert hashlib.sha256((ROOT / row["ref"]).read_bytes()).hexdigest() == (
            row["sha256"]
        )
    code_bindings = issuance["zero_call_preflight"]["exact_code_bindings"]
    assert issuance["zero_call_preflight"]["exact_code_binding_count"] == len(
        code_bindings
    )
    for relative, digest in code_bindings.items():
        current = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        if current == digest:
            continue
        assert relative == (
            "apps/workbench/backend/application/"
            "fin_0_1_2_s3_t03_exact_live_runner.py"
        )
        successor = implementation["controlled_runner_successor"]
        assert successor["historical_issuance_runner_sha256"] == digest
        assert successor["current_runner_sha256"] == current
        assert successor["historical_issuance_bytes_rewritten"] is False
        assert successor[
            "future_execution_authority_must_bind_current_runner_and_launcher_bytes"
        ] is True


def test_historical_unissued_envelope_remains_immutable() -> None:
    envelope = load_bound_s3_t03_execution_envelope(ROOT)
    assert envelope["admission"] == {
        "issued": False,
        "persisted": False,
        "execution_enabled": False,
    }
    assert envelope["observed_counts"]["admissions_issued_or_persisted"] == 0
    assert _load(ISSUANCE)["issued_admission"]["issued"] is True


def test_mutated_admission_or_envelope_fails_digest_validation(tmp_path: Path) -> None:
    raw = _load(ADMISSION)
    raw["input_digest"] = "0" * 64
    mutated = S3ThreeCellBoundedAgentAdmission.model_validate(raw)
    assert canonical_digest(mutated.digest_payload()) != EXPECTED_ADMISSION_DIGEST

    envelope = _load(ROOT / (
        "configs/runtime/fin_ia_0_1_2_s3_t03_nvda_fresh_identity_"
        "execution_envelope_v1_0.json"
    ))
    envelope["fresh_t03"]["input_digest"] = "0" * 64
    target = tmp_path / (
        "configs/runtime/fin_ia_0_1_2_s3_t03_nvda_fresh_identity_"
        "execution_envelope_v1_0.json"
    )
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(envelope), encoding="utf-8")
    with pytest.raises(Fin012S3T03RunnerError, match="envelope_digest_mismatch"):
        load_bound_s3_t03_execution_envelope(tmp_path)


def test_issuance_stops_before_exact_live_and_later_stage() -> None:
    issuance = _load(ISSUANCE)
    authority = issuance["authority"]
    assert authority["fresh_exact_admission_issuance_authorized"]
    assert not authority[
        "admission_consumption_or_exact_live_execution_authorized"
    ]
    assert not authority["paired_assessment_or_owner_acceptance_authorized"]
    assert not authority["S3_T04_or_later_authorized"]
    assert issuance["next_action"] == NEXT_ACTION


def test_historical_issuance_projection_and_current_backlog_preserve_lifecycle() -> None:
    projection_path = ROOT / (
        "configs/runtime/fin_ia_0_1_2_current_program_projection_v2_25.json"
    )
    backlog_path = ROOT / (
        "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
    )
    projection = _load(projection_path)
    backlog = _load(backlog_path)["next_action"]
    issuance_sha = hashlib.sha256(ISSUANCE.read_bytes()).hexdigest()

    assert projection["decision_binding"]["sha256"] == issuance_sha
    assert projection["current_truth"]["current_next_action"] == NEXT_ACTION
    assert backlog["item_id"] in {
        NEXT_ACTION,
        POST_ADMISSION_AUTHORITY_BLOCKED_NEXT,
        LAUNCHER_SUPERVISOR_PASS_NEXT,
    }
    if backlog["item_id"] == NEXT_ACTION:
        assert backlog["current_projection_ref"] == projection_path.relative_to(
            ROOT
        ).as_posix()
        assert backlog["current_projection_sha256"] == hashlib.sha256(
            projection_path.read_bytes()
        ).hexdigest()
    elif backlog["item_id"] == POST_ADMISSION_AUTHORITY_BLOCKED_NEXT:
        assert backlog["current_projection_ref"].endswith(
            "fin_ia_0_1_2_current_program_projection_v2_26.json"
        )
        assert backlog["S3_T03_bound_launcher_parent_supervisor_missing"] is True
    else:
        assert backlog["current_projection_ref"].endswith(
            "fin_ia_0_1_2_current_program_projection_v2_27.json"
        )
        assert backlog["S3_T03_bound_launcher_parent_supervisor_missing"] is False
        assert backlog[
            "S3_T03_bound_launcher_parent_supervisor_implementation_bundles_consumed"
        ] == 1
    assert backlog["S3_T03_fresh_admission_issued"] is True
    assert backlog["S3_T03_fresh_admission_consumed"] is False
    assert backlog["S3_T03_execution_started"] is False
