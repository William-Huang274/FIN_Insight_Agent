from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.official_source_attempt_program import (
    OfficialSourceAttemptError,
    OfficialSourceExecutionAuthority,
    SourceResponse,
    compile_official_source_attempt_program,
    load_official_source_policy,
    parse_source_document,
    validate_official_source_attempt_program,
    _require_public_network_host,
    _official_source_user_agent,
    _sec_contact_declared,
)
from sec_agent.shared_admission_ledger import (
    SharedAdmissionConsumptionLedger,
    SharedAdmissionLedgerError,
)


POLICY = ROOT / (
    "configs/runtime/fin_ia_0_1_3_repair_closeout_"
    "official_source_attempt_policy_v1_0.json"
)


class FixtureTransport:
    live_network = False

    def __init__(self, *, corrupt_route: str | None = None) -> None:
        self.corrupt_route = corrupt_route

    def fetch(self, *, url, headers, allowed_hosts, timeout_seconds, byte_ceiling):
        assert "Authorization" not in headers
        assert "Cookie" not in headers
        assert timeout_seconds == 30
        if self.corrupt_route and self.corrupt_route in url:
            return SourceResponse(200, url, {"content-type": "application/octet-stream"}, b"\x00\x01\x02")
        if "submissions" in url:
            body = json.dumps(
                {
                    "filings": {"recent": {"form": ["10-K"]}},
                    "issuer context": "revenue consolidated statements risk factors",
                }
            ).encode()
            return SourceResponse(200, url, {"content-type": "application/json"}, body)
        if "delltechnologies.com" in url:
            # Deliberately mislabeled: PDF must fail before the bounded HTML fallback succeeds.
            body = b"<html><body>AI-optimized server demand backlog net revenue gross profit risk factors inventory</body></html>"
            return SourceResponse(
                200,
                url,
                {"content-type": "application/pdf"},
                body,
                ({"status_code": 302, "from_url": url + "?redirect=1", "to_url": url, "location": url},),
            )
        if "micron" in url or "mu-20250828" in url:
            body = b"<html><body>High Bandwidth Memory HBM revenue gross margin operating income risk factors export supply inventory</body></html>"
            return SourceResponse(200, url, {"content-type": "text/html"}, body)
        body = b"<html><body>Data Center accelerated computing Blackwell revenue gross margin operating income risk factors export control supply</body></html>"
        return SourceResponse(200, url, {"content-type": "text/html"}, body)


class LiveFixtureTransport(FixtureTransport):
    live_network = True


def test_policy_and_three_case_fixture_cover_every_current_source_slot(tmp_path: Path) -> None:
    policy = load_official_source_policy(POLICY)
    result = compile_official_source_attempt_program(
        policy=policy,
        runtime_root=tmp_path,
        transport=FixtureTransport(),
    )
    validate_official_source_attempt_program(result, policy=policy)
    assert result["observed_counts"] == {
        "cases": 3,
        "required_source_slots": 17,
        "accepted_evidence": 9,
        "attempt_backed_typed_gaps": 8,
        "network_calls": 0,
        "model_calls": 0,
        "provider_calls": 0,
        "business_runs": 0,
    }
    assert len(result["capture_refs"]) == 20
    assert all(
        row["status"] in {"accepted_evidence", "attempt_backed_typed_gap"}
        for case in result["case_results"]
        for row in case["slot_results"]
    )
    assert all(
        not row["writer_citable"] and not row["domain_judgment_eligible"]
        for case in result["case_results"]
        for row in case["slot_results"]
    )
    dell_ir = next(
        row
        for case in result["case_results"]
        if case["case_key"] == "DELL"
        for row in case["route_results"]
        if row["route_id"] == "issuer_ir"
    )
    assert dell_ir["parser"]["adapter"] == "official_source_html_text_v1"
    assert dell_ir["parser"]["parser_attempts"][0]["adapter"] == "pdf"
    assert dell_ir["parser"]["parser_attempts"][0]["status"] == "failed"
    response_capture = json.loads(
        (tmp_path / "objects" / dell_ir["response_capture"]["object_key"]).read_text(encoding="utf-8")
    )
    assert response_capture["capture_before_parse"] is True
    assert len(response_capture["redirect_chain"]) == 1


def test_empty_parsed_routes_produce_attempt_backed_bounded_exhaustion(tmp_path: Path) -> None:
    policy = deepcopy(load_official_source_policy(POLICY))
    for profile in policy["case_profiles"].values():
        for slot in profile["required_slots"]:
            if slot.get("promotion_mode") != "attempt_only":
                slot.pop("match_groups", None)
                slot["match_any"] = ["definitely absent phrase"]
    result = compile_official_source_attempt_program(
        policy=policy,
        runtime_root=tmp_path,
        transport=FixtureTransport(),
    )
    gaps = [row for case in result["case_results"] for row in case["slot_results"]]
    assert len(gaps) == 17
    assert all(row["status"] == "attempt_backed_typed_gap" for row in gaps)
    assert all(row["source_exhaustion_proven"] is True for row in gaps)
    assert all(
        len(row["attempt_refs"])
        == len(policy["case_profiles"][row["case_key"]]["source_routes"])
        for row in gaps
    )
    assert all(row["exhaustion_scope"] == "bounded_case_profile_official_routes_only" for row in gaps)


def test_policy_rejects_non_https_or_cross_host_route(tmp_path: Path) -> None:
    payload = json.loads(POLICY.read_text(encoding="utf-8"))
    payload["case_profiles"]["NVDA"]["source_routes"][0]["url"] = "http://evil.invalid/a"
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(OfficialSourceAttemptError, match="official_source_policy_route_not_allowlisted"):
        load_official_source_policy(path)


def test_synthetic_dns_requires_explicit_runtime_mode(monkeypatch) -> None:
    monkeypatch.setattr(
        "sec_agent.official_source_attempt_program.socket.getaddrinfo",
        lambda *args, **kwargs: [(2, 1, 6, "", ("198.18.1.52", 443))],
    )
    monkeypatch.delenv("FINSIGHT_ALLOW_SYNTHETIC_DNS", raising=False)
    with pytest.raises(OfficialSourceAttemptError, match="official_source_private_network_forbidden"):
        _require_public_network_host("investor.example.com")
    monkeypatch.setenv("FINSIGHT_ALLOW_SYNTHETIC_DNS", "1")
    _require_public_network_host("investor.example.com")


def test_SEC_contact_identity_is_runtime_only_and_fail_closed(monkeypatch) -> None:
    monkeypatch.delenv("FINSIGHT_SEC_CONTACT_EMAIL", raising=False)
    assert _sec_contact_declared({"User-Agent": _official_source_user_agent()}) is False
    monkeypatch.setenv("FINSIGHT_SEC_CONTACT_EMAIL", "invalid-contact")
    assert _sec_contact_declared({"User-Agent": _official_source_user_agent()}) is False
    monkeypatch.setenv("FINSIGHT_SEC_CONTACT_EMAIL", "operator@example.com")
    user_agent = _official_source_user_agent()
    assert user_agent == "FIN-Insight-Agent/0.1.3 contact=operator@example.com"
    assert _sec_contact_declared({"User-Agent": user_agent}) is True


def test_validator_rejects_false_promotion(tmp_path: Path) -> None:
    policy = load_official_source_policy(POLICY)
    result = compile_official_source_attempt_program(
        policy=policy,
        runtime_root=tmp_path,
        transport=FixtureTransport(),
    )
    mutated = deepcopy(result)
    row = next(
        slot
        for case in mutated["case_results"]
        for slot in case["slot_results"]
        if slot["status"] == "accepted_evidence"
    )
    row["writer_citable"] = True
    row_body = dict(row)
    row_body.pop("result_digest")
    row["result_digest"] = canonical_digest(row_body)
    body = dict(mutated)
    body.pop("program_digest")
    mutated["program_digest"] = canonical_digest(body)
    with pytest.raises(OfficialSourceAttemptError, match="official_source_false_promotion"):
        validate_official_source_attempt_program(mutated, policy=policy)


def test_parser_failure_is_terminal_but_not_falsely_exhausted(tmp_path: Path) -> None:
    parsed = parse_source_document(
        SourceResponse(200, "https://www.sec.gov/a", {"content-type": "application/octet-stream"}, b"\x00\x01")
    )
    assert parsed["status"] == "parser_failure"
    assert [row["adapter"] for row in parsed["parser_attempts"]] == ["html", "json", "pdf"]


def test_semantic_match_uses_smallest_document_window_not_glossary_first_hit(tmp_path: Path) -> None:
    policy = deepcopy(load_official_source_policy(POLICY))
    mu = policy["case_profiles"]["MU"]
    mu["source_routes"] = [mu["source_routes"][0]]

    class GlossaryThenBodyTransport(FixtureTransport):
        def fetch(self, **kwargs):
            filler = " unrelated" * 400
            body = (
                "<html><body>HBM High-bandwidth memory glossary "
                + filler
                + " HBM customer demand remains strong. revenue risk factors</body></html>"
            ).encode()
            return SourceResponse(200, kwargs["url"], {"content-type": "text/html"}, body)

    result = compile_official_source_attempt_program(
        policy=policy,
        runtime_root=tmp_path,
        transport=GlossaryThenBodyTransport(),
    )
    demand = next(
        row
        for case in result["case_results"]
        if case["case_key"] == "MU"
        for row in case["slot_results"]
        if row["slot_id"] == "current_issuer_demand_signal"
    )
    assert demand["status"] == "accepted_evidence"
    assert demand["matched_phrase"] == "hbm + demand"


def test_dell_official_table_numeric_extractors_bind_scope_period_and_scale(tmp_path: Path) -> None:
    policy = load_official_source_policy(POLICY)

    class DellTableTransport(FixtureTransport):
        def fetch(self, **kwargs):
            if "delltechnologies.com" in kwargs["url"]:
                body = b"""<html><body>AI-optimized demand. net revenue risk factors.
                Net revenue: AI-optimized servers $ 8,952 $ 2,026 342% $ 24,683 $ 9,286 166%
                ISG operating income $ 2,900 $ 2,051 41% $ 7,111 $ 5,579 27%
                </body></html>"""
                return SourceResponse(200, kwargs["url"], {"content-type": "text/html"}, body)
            return super().fetch(**kwargs)

    result = compile_official_source_attempt_program(
        policy=policy,
        runtime_root=tmp_path,
        transport=DellTableTransport(),
    )
    numeric = {
        row["slot_id"]: row["numeric_fact"]
        for case in result["case_results"]
        if case["case_key"] == "DELL"
        for row in case["slot_results"]
        if row.get("numeric_fact")
    }
    assert numeric["dell_server_or_isg_revenue"] == {
        "raw_value": "24,683",
        "normalized_value": "24683000000",
        "unit": "USD",
        "scale_multiplier": "1000000",
        "fiscal_year": 2026,
        "fiscal_period": "FY",
        "period_role": "annual",
        "period_start": "2025-02-01",
        "period_end": "2026-01-30",
        "duration_days": 364,
        "source_filed_at": "2026-02-26",
        "published_at": "2026-02-26",
        "aggregation_scope": "AI_optimized_servers",
        "metric_family": "AI_optimized_server_revenue",
        "formula": None,
    }
    assert numeric["dell_server_or_isg_profit"]["normalized_value"] == "7111000000"
    assert numeric["dell_server_or_isg_profit"]["aggregation_scope"] == "Infrastructure_Solutions_Group"


def test_live_transport_requires_shared_exact_once_authority(tmp_path: Path) -> None:
    policy = load_official_source_policy(POLICY)
    with pytest.raises(OfficialSourceAttemptError, match="official_source_live_authority_required"):
        compile_official_source_attempt_program(
            policy=policy,
            runtime_root=tmp_path / "unauthorized",
            transport=LiveFixtureTransport(),
        )
    authority = OfficialSourceExecutionAuthority.issue(
        policy=policy,
        run_nonce="fixture-authority-a",
        issued_at="2026-08-06T00:00:00Z",
        expires_at="2026-08-06T01:00:00Z",
    )
    ledger = SharedAdmissionConsumptionLedger(tmp_path / "shared" / "admissions.sqlite3")
    result = compile_official_source_attempt_program(
        policy=policy,
        runtime_root=tmp_path / "authorized",
        transport=LiveFixtureTransport(),
        authority=authority,
        shared_admission_ledger=ledger,
        observed_at="2026-08-06T00:30:00Z",
    )
    receipt = ledger.read(authority.admission_digest)
    assert result["execution"]["attempt_id"] == authority.attempt_id
    assert receipt.state == "terminal"
    assert receipt.terminal_result_digest == result["program_digest"]
    with pytest.raises(SharedAdmissionLedgerError, match="shared_admission_already_consumed:terminal"):
        compile_official_source_attempt_program(
            policy=policy,
            runtime_root=tmp_path / "replay",
            transport=LiveFixtureTransport(),
            authority=authority,
            shared_admission_ledger=ledger,
            observed_at="2026-08-06T00:40:00Z",
        )
