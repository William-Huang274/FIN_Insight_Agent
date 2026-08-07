from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from sec_agent.official_source_attempt_program import SourceResponse
from sec_agent.s1_08_candidate_generation_runtime import load_source_catalog
from sec_agent.s1_08_r2_successor import (
    CONTRACT_REF,
    DellSearchR2Admission,
    S108R2SuccessorError,
    execute_dell_search_r2,
    project_os_preflight_passed,
    sha256_file,
)
from sec_agent.shared_admission_ledger import (
    SharedAdmissionConsumptionLedger,
    SharedAdmissionLedgerError,
)


ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = ROOT / "configs/runtime/fin_ia_0_1_3_s1_08_current_source_catalog_and_query_revision_policy_v2_0.json"
DECISION_PATH = ROOT / "configs/releases/fin_ia_0_1_3_s1_08q_h_dell_r2_replacement_authority_decision_v1_1.json"
PROOF_PATH = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_quality_first_sourcehunter_capture_replay_independent_fresh_proof_v1_0.json"
R1_PATH = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_dell_current_search_canary_result_v1_0.json"
R2_OUTPUT = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_dell_current_search_r2_result_v1_0.json"
RUNTIME_PATH = ROOT / "src/sec_agent/s1_08_r2_successor.py"
RUNNER_PATH = ROOT / "scripts/releases/run_fin_ia_0_1_3_s1_08_dell_current_search_r2.py"
COMMIT = "c" * 40
ISSUED = "2026-08-08T02:00:00Z"
EXPIRES = "2026-08-08T03:00:00Z"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _admission() -> DellSearchR2Admission:
    return DellSearchR2Admission.issue(
        authority_decision=_load(DECISION_PATH),
        independent_proof=_load(PROOF_PATH),
        independent_proof_sha256=sha256_file(PROOF_PATH),
        successor_preflight=_preflight(),
        successor_runtime_sha256=sha256_file(RUNTIME_PATH),
        successor_runner_sha256=sha256_file(RUNNER_PATH),
        r1_result=_load(R1_PATH),
        catalog=load_source_catalog(CATALOG_PATH),
        implementation_commit=COMMIT,
        run_nonce="test-dell-r2",
        issued_at=ISSUED,
        expires_at=EXPIRES,
    )


def _preflight() -> dict:
    return {
        "schema_version": "fin_ia_0_1_3_s1_08_dell_r2_successor_clean_zero_call_preflight_v1_1",
        "status": "pass",
        "project_os_preflight": {"status": "pass"},
        "source_files": {
            "runtime_sha256": sha256_file(RUNTIME_PATH),
            "runner_sha256": sha256_file(RUNNER_PATH),
        },
        "verification": {"tests_passed": 53, "external_calls": 0},
    }


class _EmptyOfficialTransport:
    live_network = True

    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def fetch(self, *, url, headers, allowed_hosts, timeout_seconds, byte_ceiling):
        self.calls.append((url, timeout_seconds))
        if "data.sec.gov/submissions" in url:
            match = next(
                row
                for row in load_source_catalog(CATALOG_PATH)["entities"]
                if url in row["official_landing_pages"]
            )
            body = json.dumps(
                {
                    "cik": match["cik"],
                    "filings": {
                        "recent": {
                            "accessionNumber": [],
                            "filingDate": [],
                            "form": [],
                            "primaryDocument": [],
                        }
                    },
                }
            ).encode()
            content_type = "application/json"
        else:
            body = b"<html><body>No matching current document links.</body></html>"
            content_type = "text/html"
        return SourceResponse(
            status_code=200,
            final_url=url,
            headers={"content-type": content_type},
            body=body,
        )


def test_R2_admission_binds_decision_proof_R1_and_budget_without_secret() -> None:
    admission = _admission()
    admission.require_active(
        authority_decision=_load(DECISION_PATH),
        independent_proof=_load(PROOF_PATH),
        independent_proof_sha256=sha256_file(PROOF_PATH),
        successor_preflight=_preflight(),
        successor_runtime_sha256=sha256_file(RUNTIME_PATH),
        successor_runner_sha256=sha256_file(RUNNER_PATH),
        r1_result=_load(R1_PATH),
        catalog=load_source_catalog(CATALOG_PATH),
        observed_at="2026-08-08T02:30:00Z",
        implementation_commit=COMMIT,
    )
    assert admission.contract_ref == CONTRACT_REF
    assert admission.network_call_ceiling == 16
    assert admission.overall_timeout_seconds == 300
    assert admission.r1_terminal_digest == _load(R1_PATH)["result"]["terminal_digest"]
    assert "@" not in json.dumps(admission.as_dict())
    assert not R2_OUTPUT.exists()


def test_R2_admission_source_or_commit_drift_fails_closed() -> None:
    admission = replace(_admission(), independent_proof_sha256="0" * 64)
    with pytest.raises(S108R2SuccessorError) as exc:
        admission.require_active(
            authority_decision=_load(DECISION_PATH),
            independent_proof=_load(PROOF_PATH),
            independent_proof_sha256=sha256_file(PROOF_PATH),
            successor_preflight=_preflight(),
            successor_runtime_sha256=sha256_file(RUNTIME_PATH),
            successor_runner_sha256=sha256_file(RUNNER_PATH),
            r1_result=_load(R1_PATH),
            catalog=load_source_catalog(CATALOG_PATH),
            observed_at="2026-08-08T02:30:00Z",
            implementation_commit=COMMIT,
        )
    assert exc.value.code == "s1_08_dell_r2_admission_invalid"


def test_R2_successor_preflight_source_drift_fails_before_issuance() -> None:
    preflight = _preflight()
    preflight["source_files"]["runtime_sha256"] = "0" * 64
    with pytest.raises(S108R2SuccessorError) as exc:
        DellSearchR2Admission.issue(
            authority_decision=_load(DECISION_PATH),
            independent_proof=_load(PROOF_PATH),
            independent_proof_sha256=sha256_file(PROOF_PATH),
            successor_preflight=preflight,
            successor_runtime_sha256=sha256_file(RUNTIME_PATH),
            successor_runner_sha256=sha256_file(RUNNER_PATH),
            r1_result=_load(R1_PATH),
            catalog=load_source_catalog(CATALOG_PATH),
            implementation_commit=COMMIT,
            run_nonce="drifted-preflight",
            issued_at=ISSUED,
            expires_at=EXPIRES,
        )
    assert exc.value.code == "s1_08_dell_r2_successor_preflight_invalid"


def test_R1_terminal_body_mutation_fails_before_R2_issuance() -> None:
    r1 = _load(R1_PATH)
    r1["result"]["observed_counts"]["network_calls"] = 18
    with pytest.raises(S108R2SuccessorError) as exc:
        DellSearchR2Admission.issue(
            authority_decision=_load(DECISION_PATH),
            independent_proof=_load(PROOF_PATH),
            independent_proof_sha256=sha256_file(PROOF_PATH),
            successor_preflight=_preflight(),
            successor_runtime_sha256=sha256_file(RUNTIME_PATH),
            successor_runner_sha256=sha256_file(RUNNER_PATH),
            r1_result=r1,
            catalog=load_source_catalog(CATALOG_PATH),
            implementation_commit=COMMIT,
            run_nonce="mutated-r1",
            issued_at=ISSUED,
            expires_at=EXPIRES,
        )
    assert exc.value.code == "s1_08_dell_r2_authority_source_invalid"


def test_missing_contact_stops_before_R2_ledger_consumption(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("FINSIGHT_SEC_CONTACT_EMAIL", raising=False)
    admission = _admission()
    ledger = SharedAdmissionConsumptionLedger(tmp_path / "shared/ledger.sqlite")
    transport = _EmptyOfficialTransport()
    with pytest.raises(S108R2SuccessorError) as exc:
        execute_dell_search_r2(
            admission=admission,
            authority_decision=_load(DECISION_PATH),
            independent_proof=_load(PROOF_PATH),
            independent_proof_sha256=sha256_file(PROOF_PATH),
            successor_preflight=_preflight(),
            successor_runtime_sha256=sha256_file(RUNTIME_PATH),
            successor_runner_sha256=sha256_file(RUNNER_PATH),
            r1_result=_load(R1_PATH),
            catalog_path=CATALOG_PATH,
            runtime_root=tmp_path / "runtime",
            shared_admission_ledger=ledger,
            transport=transport,
            implementation_commit=COMMIT,
            research_objective="Evaluate Dell current AI infrastructure evidence.",
            observed_at="2026-08-08T02:30:00Z",
        )
    assert exc.value.code == "s1_08_dell_r2_sec_contact_identity_required"
    assert transport.calls == []
    with pytest.raises(SharedAdmissionLedgerError):
        ledger.read(admission.admission_digest)


def test_R2_exact_once_terminal_preserves_authority_lineage(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("FINSIGHT_SEC_CONTACT_EMAIL", "operator@example.com")
    admission = _admission()
    ledger = SharedAdmissionConsumptionLedger(tmp_path / "shared/ledger.sqlite")
    transport = _EmptyOfficialTransport()
    result = execute_dell_search_r2(
        admission=admission,
        authority_decision=_load(DECISION_PATH),
        independent_proof=_load(PROOF_PATH),
        independent_proof_sha256=sha256_file(PROOF_PATH),
        successor_preflight=_preflight(),
        successor_runtime_sha256=sha256_file(RUNTIME_PATH),
        successor_runner_sha256=sha256_file(RUNNER_PATH),
        r1_result=_load(R1_PATH),
        catalog_path=CATALOG_PATH,
        runtime_root=tmp_path / "runtime",
        shared_admission_ledger=ledger,
        transport=transport,
        implementation_commit=COMMIT,
        research_objective="Evaluate Dell current AI infrastructure evidence.",
        observed_at="2026-08-08T02:30:00Z",
        market_snapshot={"ticker": "DELL", "as_of": "2026-08-06", "context_only": True},
    )
    assert result["status"] == "complete"
    assert result["attempt_label"] == "R2"
    assert result["authority_decision_digest"] == admission.authority_decision_digest
    assert result["independent_proof_digest"] == admission.independent_proof_digest
    assert result["r1_terminal_digest"] == admission.r1_terminal_digest
    assert result["observed_counts"]["network_calls"] == len(transport.calls)
    assert all(timeout <= 30 for _, timeout in transport.calls)
    assert result["shared_admission_receipt"]["state"] == "terminal"
    with pytest.raises(SharedAdmissionLedgerError):
        execute_dell_search_r2(
            admission=admission,
            authority_decision=_load(DECISION_PATH),
            independent_proof=_load(PROOF_PATH),
            independent_proof_sha256=sha256_file(PROOF_PATH),
            successor_preflight=_preflight(),
            successor_runtime_sha256=sha256_file(RUNTIME_PATH),
            successor_runner_sha256=sha256_file(RUNNER_PATH),
            r1_result=_load(R1_PATH),
            catalog_path=CATALOG_PATH,
            runtime_root=tmp_path / "runtime-2",
            shared_admission_ledger=ledger,
            transport=_EmptyOfficialTransport(),
            implementation_commit=COMMIT,
            research_objective="Evaluate Dell current AI infrastructure evidence.",
            observed_at="2026-08-08T02:31:00Z",
        )


def test_R2_runner_is_zero_call_until_explicit_main_and_uses_distinct_output() -> None:
    source = (ROOT / "scripts/releases/run_fin_ia_0_1_3_s1_08_dell_current_search_r2.py").read_text(
        encoding="utf-8"
    )
    assert "fin_ia_0_1_3_s1_08_dell_current_search_r2_result_v1_0.json" in source
    assert "S1_08_DELL_R2_exact_live_issuance_and_execution" in source
    assert "socket.getaddrinfo" not in source
    assert 'if __name__ == "__main__"' in source
    assert project_os_preflight_passed(
        {"status": "pass", "open_full_chain_blockers": []}
    )
    assert not project_os_preflight_passed(
        {"status": "pass", "open_full_chain_blockers": [{"issue_id": "blocked"}]}
    )
    assert datetime.now(timezone.utc).tzinfo is not None
