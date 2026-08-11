from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.official_source_attempt_program import SourceResponse  # noqa: E402
from sec_agent.s1_internal_current_source_acquisition import (  # noqa: E402
    execute_internal_source_acquisition,
    execute_internal_source_acquisition_guarded,
    issue_internal_source_acquisition_admission,
    load_internal_source_acquisition_policy,
)
from sec_agent.shared_admission_ledger import (  # noqa: E402
    SharedAdmissionConsumptionLedger,
)


POLICY_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s1_internal_"
    "current_source_acquisition_policy_v1_0.json"
)


def _submissions(
    *, accession: str, filed: str, report: str, form: str, primary: str, items: str
) -> bytes:
    return json.dumps(
        {
            "filings": {
                "recent": {
                    "accessionNumber": [accession],
                    "filingDate": [filed],
                    "reportDate": [report],
                    "form": [form],
                    "primaryDocument": [primary],
                    "items": [items],
                }
            }
        }
    ).encode()


class FakeTransport:
    live_network = True

    def __init__(self, responses: dict[str, tuple[str, bytes]]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def fetch(
        self,
        *,
        url: str,
        headers: dict[str, str],
        allowed_hosts: set[str],
        timeout_seconds: int,
        byte_ceiling: int,
    ) -> SourceResponse:
        self.calls.append(url)
        content_type, body = self.responses[url]
        return SourceResponse(
            status_code=200,
            final_url=url,
            headers={"content-type": content_type},
            body=body,
        )


def test_capture_first_sec_discovery_acquires_three_current_source_families(
    tmp_path: Path,
) -> None:
    policy = load_internal_source_acquisition_policy(POLICY_PATH, repo_root=ROOT)
    dell_primary = (
        "https://www.sec.gov/Archives/edgar/data/1571996/"
        "000157199626000008/dell-20260130.htm"
    )
    mu_primary = (
        "https://www.sec.gov/Archives/edgar/data/723125/"
        "000072312526000020/mu-20260624.htm"
    )
    mu_exhibit = (
        "https://www.sec.gov/Archives/edgar/data/723125/"
        "000072312526000020/ex99-1.htm"
    )
    tsm_primary = (
        "https://www.sec.gov/Archives/edgar/data/1046179/"
        "000104617926000030/tsm-20260716.htm"
    )
    tsm_exhibit = (
        "https://www.sec.gov/Archives/edgar/data/1046179/"
        "000104617926000030/ex99-1.htm"
    )
    responses = {
        "https://data.sec.gov/submissions/CIK0001571996.json": (
            "application/json",
            _submissions(
                accession="0001571996-26-000008",
                filed="2026-03-16",
                report="2026-01-30",
                form="10-K",
                primary="dell-20260130.htm",
                items="",
            ),
        ),
        "https://data.sec.gov/submissions/CIK0000723125.json": (
            "application/json",
            _submissions(
                accession="0000723125-26-000020",
                filed="2026-06-24",
                report="2026-05-28",
                form="8-K",
                primary="mu-20260624.htm",
                items="2.02,9.01",
            ),
        ),
        "https://data.sec.gov/submissions/CIK0001046179.json": (
            "application/json",
            _submissions(
                accession="0001046179-26-000030",
                filed="2026-07-16",
                report="2026-06-30",
                form="6-K",
                primary="tsm-20260716.htm",
                items="",
            ),
        ),
        dell_primary: (
            "text/html",
            b"<html><body>Dell Technologies fiscal 2026 Infrastructure Solutions Group and AI-optimized servers risk factors.</body></html>",
        ),
        mu_primary: (
            "text/html",
            b'<html><body>Form 8-K <a href="ex99-1.htm">Exhibit 99.1 earnings results</a></body></html>',
        ),
        mu_exhibit: (
            "text/html",
            b"<html><body>Micron Technology third quarter fiscal 2026 HBM revenue and gross margin.</body></html>",
        ),
        tsm_primary: (
            "text/html",
            b'<html><body>Form 6-K <a href="ex99-1.htm">Exhibit 99.1 financial results</a></body></html>',
        ),
        tsm_exhibit: (
            "text/html",
            b"<html><body>Taiwan Semiconductor TSMC second quarter Q2 2026 revenue and gross margin capacity.</body></html>",
        ),
    }
    transport = FakeTransport(responses)
    admission = issue_internal_source_acquisition_admission(
        policy=policy,
        implementation_commit="0" * 40,
        implementation_file_sha256="1" * 64,
        policy_file_sha256="2" * 64,
        issued_at="2026-08-09T00:00:00Z",
        expires_at="2026-08-10T00:00:00Z",
        nonce="fake",
    )
    ledger = SharedAdmissionConsumptionLedger(tmp_path / "shared" / "ledger.sqlite")
    result = execute_internal_source_acquisition(
        policy=policy,
        admission=admission,
        runtime_root=tmp_path / "runtime",
        ledger=ledger,
        transport=transport,
        observed_at="2026-08-09T01:00:00Z",
    )
    assert result["status"] == "completed_all_targets_acquired"
    assert result["observed_counts"] == {
        "targets": 3,
        "acquired": 3,
        "typed_gaps": 0,
        "network_calls": 8,
        "retry_calls": 0,
        "model_calls": 0,
        "provider_calls": 0,
        "embedding_calls": 0,
        "rerank_calls": 0,
        "evidence_promotion_calls": 0,
    }
    assert all(
        row["benchmark_exact_url_used_for_discovery"] is False
        and row["candidate_state"] == "captured_source_not_evidence"
        for row in result["source_results"]
    )
    assert ledger.read(admission["admission_digest"]).state == "terminal"


class ExplodingTransport:
    live_network = True

    def fetch(self, **_: object) -> SourceResponse:
        raise RuntimeError("fixture_unexpected_parser_boundary")


def test_guarded_execution_terminalizes_unexpected_consumed_failure(
    tmp_path: Path,
) -> None:
    policy = load_internal_source_acquisition_policy(POLICY_PATH, repo_root=ROOT)
    admission = issue_internal_source_acquisition_admission(
        policy=policy,
        implementation_commit="0" * 40,
        implementation_file_sha256="1" * 64,
        policy_file_sha256="2" * 64,
        issued_at="2026-08-09T00:00:00Z",
        expires_at="2026-08-10T00:00:00Z",
        nonce="guarded-failure",
    )
    ledger = SharedAdmissionConsumptionLedger(tmp_path / "shared" / "ledger.sqlite")
    result = execute_internal_source_acquisition_guarded(
        policy=policy,
        admission=admission,
        runtime_root=tmp_path / "runtime",
        ledger=ledger,
        transport=ExplodingTransport(),
        observed_at="2026-08-09T01:00:00Z",
    )

    receipt = ledger.read(admission["admission_digest"])
    assert result["status"] == "terminal_failed"
    assert result["failure"]["code"] == (
        "internal_source_acquisition_unhandled_runtimeerror"
    )
    assert result["failure"]["raw_captures_retained"] is True
    assert result["observed_counts"]["network_calls"] == 1
    assert receipt.state == "terminal"
    assert receipt.terminal_status == "failed"
    assert receipt.terminal_result_digest == result["result_digest"]
