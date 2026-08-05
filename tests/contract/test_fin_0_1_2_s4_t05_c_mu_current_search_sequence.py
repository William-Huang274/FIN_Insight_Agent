from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "scripts" / "releases")]

from apps.workbench.backend.application.fin_0_1_2_s4_t03_executable_agentic_search import (  # noqa: E402
    compile_current_case_executable_requests,
)
from run_fin_ia_0_1_2_s4_t05_c_mu_current_search_sequence import (  # noqa: E402
    CASE_KEY,
    EXPECTED_ACCEPTED_REJECTED,
    T05CMUSearchError,
    build_proof_and_issuance,
    prepare_and_issue,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


def test_mu_entry_fresh_proof_and_issuance_are_exact_and_zero_call(
    tmp_path: Path,
) -> None:
    decision, admission, issuance = build_proof_and_issuance(
        recorded_at="2026-08-05T08:00:00Z",
        reserved_runtime_root=tmp_path / "reserved-runtime",
    )
    assert decision["status"] == (
        "pass_MU_current_search_fresh_proof_and_admission_authority"
    )
    assert decision["fresh_zero_call_proof"]["accepted_rejected_by_cell"] == [
        list(row) for row in EXPECTED_ACCEPTED_REJECTED
    ]
    assert decision["fresh_zero_call_proof"]["model_provider_live_source_calls"] == [0, 0, 0]
    assert decision["decision_digest"] == canonical_digest(
        {key: value for key, value in decision.items() if key != "decision_digest"}
    )
    assert admission["case_key"] == CASE_KEY
    assert admission["request_digests"] == [
        row.request_digest for row in compile_current_case_executable_requests(CASE_KEY)
    ]
    assert issuance["status"] == "issued_unconsumed_zero_call_preflight_pass"
    assert issuance["issued_admission"]["consumed"] is False
    assert issuance["observed_counts"] == {
        "source_network_calls": 0,
        "local_invocations": 0,
        "model_calls": 0,
        "provider_calls": 0,
        "business_artifacts": 0,
    }


def test_prepare_and_issue_is_atomic_and_second_different_issue_fails_closed(
    tmp_path: Path,
) -> None:
    paths = [tmp_path / name for name in ("authority.json", "admission.json", "issuance.json")]
    first = prepare_and_issue(
        recorded_at="2026-08-05T08:00:00Z",
        authority_path=paths[0],
        admission_path=paths[1],
        issuance_path=paths[2],
        reserved_runtime_root=tmp_path / "reserved-runtime",
    )
    assert first["status"].startswith("pass_entry_audit")
    assert all(path.is_file() for path in paths)
    assert json.loads(paths[1].read_text(encoding="utf-8"))["case_key"] == "MU"
    with pytest.raises(T05CMUSearchError, match="existing_output_mismatch"):
        prepare_and_issue(
            recorded_at="2026-08-05T08:01:00Z",
            authority_path=paths[0],
            admission_path=paths[1],
            issuance_path=paths[2],
            reserved_runtime_root=tmp_path / "reserved-runtime",
        )


def test_admission_window_is_active_for_declared_issue_time(tmp_path: Path) -> None:
    _, admission, _ = build_proof_and_issuance(
        recorded_at="2026-08-05T08:00:00Z",
        reserved_runtime_root=tmp_path / "reserved-runtime",
    )
    issued = datetime.fromisoformat(admission["issued_at"].replace("Z", "+00:00"))
    expires = datetime.fromisoformat(admission["expires_at"].replace("Z", "+00:00"))
    assert issued < datetime(2026, 8, 5, 8, 0, tzinfo=timezone.utc) < expires
