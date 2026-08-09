from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.financial_research_held_out_current_source_acquisition import (  # noqa: E402
    execute_held_out_current_source_acquisition,
    execute_held_out_current_source_acquisition_guarded,
    issue_held_out_current_source_admission,
    load_held_out_current_source_policy,
    select_target_submission,
)
from sec_agent.official_source_attempt_program import SourceResponse  # noqa: E402
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger  # noqa: E402


POLICY_PATH = ROOT / "configs/runtime/fin_ia_0_1_3_s1_held_out_current_source_acquisition_policy_v1_0.json"


def _submissions(rows: list[dict[str, str]]) -> bytes:
    return json.dumps(
        {
            "filings": {
                "recent": {
                    "accessionNumber": [row["accession"] for row in rows],
                    "filingDate": [row["filed"] for row in rows],
                    "reportDate": [row["report"] for row in rows],
                    "form": [row["form"] for row in rows],
                    "primaryDocument": [row["primary"] for row in rows],
                    "items": [row.get("items", "") for row in rows],
                }
            }
        }
    ).encode()


class FakeTransport:
    live_network = True

    def __init__(self, responses: dict[str, tuple[str, bytes]]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def fetch(self, *, url: str, **_: object) -> SourceResponse:
        self.calls.append(url)
        content_type, body = self.responses[url]
        return SourceResponse(
            status_code=200,
            final_url=url,
            headers={"content-type": content_type},
            body=body,
        )


def _fixture_responses() -> dict[str, tuple[str, bytes]]:
    orcl = "https://www.sec.gov/Archives/edgar/data/1341439/000134143926000111/orcl-20260531.htm"
    asml = "https://www.sec.gov/Archives/edgar/data/937966/000093796626000222/asml-20260715.htm"
    asml_exhibit = asml.rsplit("/", 1)[0] + "/ex99-1-q2-results.pdf"
    anet = "https://www.sec.gov/Archives/edgar/data/1596532/000159653226000333/anet-20260804.htm"
    anet_exhibit = anet.rsplit("/", 1)[0] + "/ex99-1.htm"
    return {
        "https://data.sec.gov/submissions/CIK0001341439.json": (
            "application/json",
            _submissions(
                [
                    {"accession": "0001341439-26-000111", "filed": "2026-06-22", "report": "2026-05-31", "form": "10-K", "primary": "orcl-20260531.htm"},
                    {"accession": "0001341439-25-000999", "filed": "2025-06-23", "report": "2025-05-31", "form": "10-K", "primary": "orcl-20250531.htm"},
                ]
            ),
        ),
        "https://data.sec.gov/submissions/CIK0000937966.json": (
            "application/json",
            _submissions(
                [{"accession": "0000937966-26-000222", "filed": "2026-07-15", "report": "2026-06-28", "form": "6-K", "primary": "asml-20260715.htm"}]
            ),
        ),
        "https://data.sec.gov/submissions/CIK0001596532.json": (
            "application/json",
            _submissions(
                [
                    {"accession": "0001596532-26-000333", "filed": "2026-08-04", "report": "2026-08-04", "form": "8-K", "primary": "anet-20260804.htm", "items": "2.02,9.01"},
                    {"accession": "0001596532-26-000332", "filed": "2026-08-03", "report": "2026-06-30", "form": "10-Q", "primary": "anet-20260630.htm"},
                ]
            ),
        ),
        orcl: (
            "text/html",
            b"<html><body>Oracle Corporation fiscal 2026 year ended May 31, 2026 cloud services and capital expenditures.</body></html>",
        ),
        asml: (
            "text/html",
            b'<html><body>Form 6-K <a href="ex99-1-q2-results.pdf">Exhibit 99.1 Q2 results</a></body></html>',
        ),
        asml_exhibit: (
            "text/html",
            b"<html><body>ASML Holding second quarter Q2 2026 EUV High NA bookings gross margin.</body></html>",
        ),
        # Form priority chooses 10-Q even though the 8-K is newer.
        "https://www.sec.gov/Archives/edgar/data/1596532/000159653226000332/anet-20260630.htm": (
            "text/html",
            b'<html><body>Arista Networks second quarter Q2 2026 revenue gross margin Ethernet AI.</body></html>',
        ),
        anet: ("text/html", b"<html><body>unused 8-K</body></html>"),
        anet_exhibit: ("text/html", b"<html><body>unused exhibit</body></html>"),
    }


def _admission(policy: dict[str, object], nonce: str = "fixture") -> dict[str, object]:
    return issue_held_out_current_source_admission(
        policy=policy,
        implementation_commit="0" * 40,
        implementation_file_sha256="1" * 64,
        policy_file_sha256="2" * 64,
        issued_at="2026-08-09T00:00:00Z",
        expires_at="2026-08-10T00:00:00Z",
        nonce=nonce,
    )


def test_capture_first_held_out_current_sources_and_form_priority(tmp_path: Path) -> None:
    policy = load_held_out_current_source_policy(POLICY_PATH, repo_root=ROOT)
    transport = FakeTransport(_fixture_responses())
    ledger = SharedAdmissionConsumptionLedger(tmp_path / "shared.sqlite")
    result = execute_held_out_current_source_acquisition(
        policy=policy,
        admission=_admission(policy),
        runtime_root=tmp_path / "runtime",
        ledger=ledger,
        transport=transport,
        observed_at="2026-08-09T01:00:00Z",
    )
    assert result["status"] == "completed_all_targets_acquired"
    assert result["observed_counts"]["network_calls"] == 7
    assert [row["source"]["form_type"] for row in result["source_results"]] == ["10-K", "6-K", "10-Q"]
    assert all(row["exact_accession_or_final_url_seeded"] is False for row in result["source_results"])
    assert all(row["candidate_state"] == "captured_source_not_evidence" for row in result["source_results"])


def test_selector_rejects_wrong_period_and_prefers_form_order() -> None:
    policy = load_held_out_current_source_policy(POLICY_PATH, repo_root=ROOT)
    target = policy["acquisition_targets"][2]
    payload = json.loads(
        _submissions(
            [
                {"accession": "0001596532-26-000010", "filed": "2026-08-04", "report": "2026-08-04", "form": "8-K", "primary": "newer.htm"},
                {"accession": "0001596532-26-000009", "filed": "2026-08-03", "report": "2026-06-30", "form": "10-Q", "primary": "preferred.htm"},
                {"accession": "0001596532-25-000100", "filed": "2025-08-05", "report": "2025-06-30", "form": "10-Q", "primary": "stale.htm"},
            ]
        ).decode()
    )
    selected = select_target_submission(payload, target=target)
    assert selected["form_type"] == "10-Q"
    assert selected["primary_document"] == "preferred.htm"
    assert "stale.htm" not in selected["primary_url"]


class ExplodingTransport:
    live_network = True

    def fetch(self, **_: object) -> SourceResponse:
        raise RuntimeError("unexpected fixture failure")


def test_consumed_failure_is_terminal_and_capture_retained(tmp_path: Path) -> None:
    policy = load_held_out_current_source_policy(POLICY_PATH, repo_root=ROOT)
    admission = _admission(policy, nonce="failure")
    ledger = SharedAdmissionConsumptionLedger(tmp_path / "shared.sqlite")
    result = execute_held_out_current_source_acquisition_guarded(
        policy=policy,
        admission=admission,
        runtime_root=tmp_path / "runtime",
        ledger=ledger,
        transport=ExplodingTransport(),
        observed_at="2026-08-09T01:00:00Z",
    )
    assert result["status"] == "terminal_failed"
    assert result["failure"]["raw_captures_retained"] is True
    assert result["observed_counts"]["network_calls"] == 1
    assert ledger.read(str(admission["admission_digest"])).state == "terminal"
