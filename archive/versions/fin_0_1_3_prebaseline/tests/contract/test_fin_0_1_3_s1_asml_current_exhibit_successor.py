from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.financial_research_asml_exhibit_successor import (  # noqa: E402
    derive_asml_accession_index,
    evaluate_detailed_results,
    execute_asml_exhibit_successor,
    execute_asml_exhibit_successor_guarded,
    issue_asml_exhibit_admission,
    load_asml_exhibit_successor_policy,
    select_exhibit_candidates,
)
from sec_agent.official_source_attempt_program import SourceResponse  # noqa: E402
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger  # noqa: E402


POLICY_PATH = ROOT / "configs/runtime/fin_ia_0_1_3_s1_asml_current_exhibit_successor_policy_v1_0.json"


class FakeTransport:
    live_network = True

    def __init__(self, responses: dict[str, tuple[str, bytes]]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def fetch(self, *, url: str, **_: object) -> SourceResponse:
        self.calls.append(url)
        content_type, body = self.responses[url]
        return SourceResponse(status_code=200, final_url=url, headers={"content-type": content_type}, body=body)


def _admission(policy: dict[str, object], nonce: str = "fixture") -> dict[str, object]:
    return issue_asml_exhibit_admission(
        policy=policy,
        implementation_commit="0" * 40,
        implementation_file_sha256="1" * 64,
        policy_file_sha256="2" * 64,
        issued_at="2026-08-09T00:00:00Z",
        expires_at="2026-08-10T00:00:00Z",
        nonce=nonce,
    )


def _index(items: list[dict[str, object]]) -> bytes:
    return json.dumps({"directory": {"item": items}}).encode()


def test_lineage_is_derived_from_bound_live_capture() -> None:
    policy = load_asml_exhibit_successor_policy(POLICY_PATH, repo_root=ROOT)
    lineage = derive_asml_accession_index(policy=policy, repo_root=ROOT)
    assert lineage["accession_number"] == "0001628280-26-048235"
    assert lineage["index_url"].endswith("/000162828026048235/index.json")
    assert "form6-kquarterlyfilings.htm" not in lineage["index_url"]


def test_index_candidate_selection_rejects_primary_and_xbrl() -> None:
    payload = json.loads(
        _index(
            [
                {"name": "form6-kquarterlyfilings.htm", "size": 1000, "type": "text/html"},
                {"name": "asml-20260628_lab.xml", "size": 500, "type": "text/xml"},
                {"name": "exhibit991pressrelease.htm", "size": 10000, "type": "text/html"},
                {"name": "exhibit992financialresults.pdf", "size": 20000, "type": "application/pdf"},
            ]
        ).decode()
    )
    selected = select_exhibit_candidates(
        payload,
        accession_base_url="https://www.sec.gov/Archives/edgar/data/937966/000162828026048235/",
        primary_document="form6-kquarterlyfilings.htm",
        ceiling=2,
    )
    assert [row["name"] for row in selected] == ["exhibit991pressrelease.htm", "exhibit992financialresults.pdf"]


def test_capture_first_fallback_finds_detailed_second_exhibit(tmp_path: Path) -> None:
    policy = load_asml_exhibit_successor_policy(POLICY_PATH, repo_root=ROOT)
    lineage = derive_asml_accession_index(policy=policy, repo_root=ROOT)
    first = lineage["accession_base_url"] + "exhibit991pressrelease.htm"
    second = lineage["accession_base_url"] + "exhibit992financialresults.htm"
    responses = {
        lineage["index_url"]: (
            "application/json",
            _index(
                [
                    {"name": "exhibit991pressrelease.htm", "size": 10000, "type": "text/html"},
                    {"name": "exhibit992financialresults.htm", "size": 20000, "type": "text/html"},
                ]
            ),
        ),
        first: ("text/html", b"<html><body>ASML Q2 2026 gross margin outlook.</body></html>"),
        second: (
            "text/html",
            b"<html><body>ASML Q2 2026 net bookings EUV High-NA systems sold installed base gross margin cash flows outlook.</body></html>",
        ),
    }
    ledger = SharedAdmissionConsumptionLedger(tmp_path / "shared.sqlite")
    result = execute_asml_exhibit_successor(
        policy=policy,
        admission=_admission(policy),
        repo_root=ROOT,
        runtime_root=tmp_path / "runtime",
        ledger=ledger,
        transport=FakeTransport(responses),
        observed_at="2026-08-09T01:00:00Z",
    )
    assert result["status"] == "completed_detailed_exhibit_acquired"
    assert result["observed_counts"]["network_calls"] == 3
    assert result["selected_detailed_source"]["candidate"]["name"] == "exhibit992financialresults.htm"
    assert result["selected_detailed_source"]["assessment"]["facet_hit_count"] >= 4
    assert ledger.read(str(result["admission_digest"])).state == "terminal"


def test_detailed_gate_does_not_treat_headline_as_full_results() -> None:
    assessment = evaluate_detailed_results(
        "ASML reports net sales and gross margin in Q2 2026 outlook.", minimum_facet_hits=4
    )
    assert assessment["identity_pass"] is True
    assert assessment["period_pass"] is True
    assert assessment["detailed_results_pass"] is False
    assert assessment["facet_hit_count"] == 2


class ExplodingTransport:
    live_network = True

    def fetch(self, **_: object) -> SourceResponse:
        raise RuntimeError("unexpected fixture failure")


def test_consumed_unexpected_failure_is_terminal(tmp_path: Path) -> None:
    policy = load_asml_exhibit_successor_policy(POLICY_PATH, repo_root=ROOT)
    admission = _admission(policy, nonce="failure")
    ledger = SharedAdmissionConsumptionLedger(tmp_path / "shared.sqlite")
    result = execute_asml_exhibit_successor_guarded(
        policy=policy,
        admission=admission,
        repo_root=ROOT,
        runtime_root=tmp_path / "runtime",
        ledger=ledger,
        transport=ExplodingTransport(),
        observed_at="2026-08-09T01:00:00Z",
    )
    assert result["status"] == "terminal_failed"
    assert result["failure"]["raw_captures_retained"] is True
    assert result["observed_counts"]["network_calls"] == 1
    assert ledger.read(str(admission["admission_digest"])).state == "terminal"
