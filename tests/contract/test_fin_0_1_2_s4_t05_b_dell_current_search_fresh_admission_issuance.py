from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "src"),
    str(ROOT / "scripts" / "releases"),
]

from apps.workbench.backend.application.fin_0_1_2_s4_t03_executable_agentic_search import (
    Fin012S4T03SearchError,
    SearchAdmission,
    compile_current_case_executable_requests,
)
import issue_fin_ia_0_1_2_s4_t05_b_dell_current_search_fresh_admission as issuer_module
from issue_fin_ia_0_1_2_s4_t05_b_dell_current_search_fresh_admission import (
    ADMISSION_REF,
    EXPIRES_AT,
    ISSUANCE_REF,
    ISSUED_AT,
    RUNTIME_ROOT_REF,
    AdmissionIssuanceError,
    compile_exact_admission,
    issue,
)
from run_fin_ia_0_1_2_s4_t05_current_search import load_exact_admission
from sec_agent.canonical_runtime.models import canonical_digest


PROJECTION_REF = Path(
    "configs/runtime/fin_ia_0_1_2_current_program_projection_v2_53.json"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_historical_issuer_fails_closed_after_bound_source_evolves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        issuer_module, "_current_commit", lambda: issuer_module.BASE_COMMIT
    )
    admission_path = tmp_path / "admission.json"
    issuance_path = tmp_path / "issuance.json"
    runtime_root = tmp_path / "runtime"
    with pytest.raises(
        AdmissionIssuanceError,
        match="t05_b_dell_search_authority_binding_drift",
    ):
        issue(
            admission_output=admission_path,
            issuance_output=issuance_path,
            runtime_root=runtime_root,
        )
    assert not admission_path.exists()
    assert not issuance_path.exists()
    assert not runtime_root.exists()


def test_historical_admission_payload_still_round_trips_and_mutation_fails_closed(
    tmp_path: Path,
) -> None:
    exact_dir = tmp_path / "exact"
    exact_dir.mkdir()
    admission_path = exact_dir / "admission.json"
    admission_path.write_text(
        json.dumps(compile_exact_admission().as_dict(), indent=2), encoding="utf-8"
    )
    loaded = load_exact_admission(admission_path, case_key="DELL")
    loaded.require_active(
        now=ISSUED_AT,
        requests=compile_current_case_executable_requests("DELL"),
    )
    assert loaded.as_dict() == compile_exact_admission().as_dict()

    mutated = compile_exact_admission().as_dict()
    mutated["case_key"] = "MU"
    with pytest.raises(
        Fin012S4T03SearchError,
        match="t03_admission_digest_mismatch",
    ):
        SearchAdmission.from_dict(mutated).require_active(
            now=ISSUED_AT,
            requests=compile_current_case_executable_requests("DELL"),
        )


def test_tracked_admission_and_issuance_are_content_addressed_and_unconsumed() -> None:
    admission_path = ROOT / ADMISSION_REF
    issuance_path = ROOT / ISSUANCE_REF
    admission = load_exact_admission(admission_path, case_key="DELL")
    admission.require_active(
        now=ISSUED_AT,
        requests=compile_current_case_executable_requests("DELL"),
    )
    issuance = json.loads(issuance_path.read_text(encoding="utf-8"))
    observed_digest = issuance.pop("issuance_digest")
    assert observed_digest == canonical_digest(issuance)
    assert issuance["issued_admission"]["sha256"] == _sha256(admission_path)
    assert issuance["issued_admission"]["admission_digest"] == (
        admission.admission_digest
    )
    assert issuance["issued_admission"]["consumed"] is False
    assert issuance["authority"]["source_live_execution_authorized_this_issuance"] is False
    assert issuance["reserved_execution_boundary"] == {
        "runtime_root": str(RUNTIME_ROOT_REF).replace("\\", "/"),
        "runtime_root_absent": True,
        "single_declared_runtime_root_only": True,
        "cross_runtime_global_lock_proven": False,
        "cross_runtime_boundary_issue": "RC-P36-115",
    }
    # This record is immutable issuance-time evidence.  After the separately
    # authorized exact-live, the declared runtime root may legitimately exist;
    # current consumption truth belongs to the later result/projection record.
    for binding in issuance["immutable_bindings"]:
        assert _sha256(ROOT / binding["ref"]) == binding["sha256"]


def test_projection_preserves_product_truth_and_only_advances_to_search_live() -> None:
    projection = json.loads((ROOT / PROJECTION_REF).read_text(encoding="utf-8"))
    assert projection["current_truth"]["S4_T05_B_DELL"] == (
        "search_admission_issued_unconsumed"
    )
    assert projection["current_truth"]["DELL_current_R2"] is False
    assert projection["authority_boundary"]["DELL_source_live_executed"] is False
    assert projection["authority_boundary"]["DELL_Agent_admission_or_live_authorized"] is False
    assert projection["current_truth"]["current_next_action"] == (
        "FIN-0.1.2-S4-T05-B-DELL-CURRENT-SEARCH-EXACT-LIVE-EXECUTION"
    )
