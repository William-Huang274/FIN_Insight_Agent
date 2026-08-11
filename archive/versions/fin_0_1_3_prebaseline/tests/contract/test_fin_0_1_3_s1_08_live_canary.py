from __future__ import annotations

import json
from pathlib import Path

import pytest

from sec_agent.official_source_attempt_program import SourceResponse
from sec_agent.s1_08_candidate_generation_runtime import load_source_catalog
from sec_agent.s1_08_live_canary import (
    DellSearchCanaryAdmission,
    S108LiveCanaryError,
    execute_dell_search_canary,
)
from sec_agent.shared_admission_ledger import (
    SharedAdmissionConsumptionLedger,
    SharedAdmissionLedgerError,
)


ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = ROOT / "configs/runtime/fin_ia_0_1_3_s1_08_current_source_catalog_and_query_revision_policy_v2_0.json"
COMMIT = "a" * 40
ISSUED = "2026-08-07T12:00:00Z"
EXPIRES = "2026-08-07T13:00:00Z"


class _EmptyOfficialTransport:
    live_network = True

    def __init__(self) -> None:
        self.calls: list[str] = []

    def fetch(self, *, url: str, headers: dict, allowed_hosts: set[str], timeout_seconds: int, byte_ceiling: int) -> SourceResponse:
        self.calls.append(url)
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


def _admission() -> DellSearchCanaryAdmission:
    return DellSearchCanaryAdmission.issue(
        catalog=load_source_catalog(CATALOG_PATH),
        implementation_commit=COMMIT,
        run_nonce="test-r1",
        issued_at=ISSUED,
        expires_at=EXPIRES,
        network_call_ceiling=16,
        document_ceiling_per_query=1,
    )


def test_admission_is_digest_bound_and_secret_free() -> None:
    admission = _admission()
    admission.require_active(
        catalog=load_source_catalog(CATALOG_PATH),
        observed_at="2026-08-07T12:30:00Z",
        implementation_commit=COMMIT,
    )
    serialized = json.dumps(admission.as_dict())
    assert "@" not in serialized
    assert admission.retry_ceiling == 0
    assert admission.model_call_ceiling == 0


def test_missing_runtime_sec_identity_stops_before_consumption(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FINSIGHT_SEC_CONTACT_EMAIL", raising=False)
    admission = _admission()
    ledger = SharedAdmissionConsumptionLedger(tmp_path / "shared" / "ledger.sqlite")
    transport = _EmptyOfficialTransport()
    with pytest.raises(S108LiveCanaryError) as exc:
        execute_dell_search_canary(
            admission=admission,
            catalog_path=CATALOG_PATH,
            runtime_root=tmp_path / "runtime",
            shared_admission_ledger=ledger,
            transport=transport,
            implementation_commit=COMMIT,
            research_objective="Evaluate Dell AI infrastructure demand, value capture and risks.",
            observed_at="2026-08-07T12:30:00Z",
        )
    assert exc.value.code == "s1_08_dell_canary_sec_contact_identity_required"
    assert transport.calls == []
    with pytest.raises(SharedAdmissionLedgerError):
        ledger.read(admission.admission_digest)


def test_exact_once_runner_materializes_typed_gap_terminal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FINSIGHT_SEC_CONTACT_EMAIL", "operator@example.com")
    admission = _admission()
    ledger = SharedAdmissionConsumptionLedger(tmp_path / "shared" / "ledger.sqlite")
    transport = _EmptyOfficialTransport()
    result = execute_dell_search_canary(
        admission=admission,
        catalog_path=CATALOG_PATH,
        runtime_root=tmp_path / "runtime",
        shared_admission_ledger=ledger,
        transport=transport,
        implementation_commit=COMMIT,
        research_objective="Evaluate Dell AI infrastructure demand, value capture and risks.",
        observed_at="2026-08-07T12:30:00Z",
        market_snapshot={"ticker": "DELL", "as_of": "2026-08-06", "context_only": True},
    )
    assert result["status"] == "complete"
    assert result["code"] == "dell_current_search_candidate_run_complete_with_typed_gaps"
    assert result["candidate_result"]["typed_gaps"]
    assert result["candidate_result"]["observed_counts"]["model_calls"] == 0
    assert result["observed_counts"]["network_calls"] == len(transport.calls)
    assert result["completed_at"].endswith("Z")
    assert result["shared_admission_receipt"]["finalized_at"] == result["completed_at"]
    assert result["shared_admission_receipt"]["state"] == "terminal"
    assert result["terminal_object"]["object_key"]
    assert len(result["terminal_object"]["digest"]) == 64
    with pytest.raises(SharedAdmissionLedgerError) as exc:
        execute_dell_search_canary(
            admission=admission,
            catalog_path=CATALOG_PATH,
            runtime_root=tmp_path / "runtime-2",
            shared_admission_ledger=ledger,
            transport=_EmptyOfficialTransport(),
            implementation_commit=COMMIT,
            research_objective="Evaluate Dell AI infrastructure demand, value capture and risks.",
            observed_at="2026-08-07T12:31:00Z",
        )
    assert exc.value.code.startswith("shared_admission_already_consumed")


def test_admission_commit_or_catalog_drift_fails_closed() -> None:
    admission = _admission()
    with pytest.raises(S108LiveCanaryError) as exc:
        admission.require_active(
            catalog=load_source_catalog(CATALOG_PATH),
            observed_at="2026-08-07T12:30:00Z",
            implementation_commit="b" * 40,
        )
    assert exc.value.code == "s1_08_dell_canary_admission_invalid"
