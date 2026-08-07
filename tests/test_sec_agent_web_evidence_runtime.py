from __future__ import annotations

import json
from pathlib import Path

from sec_agent.official_source_attempt_program import SourceResponse
from sec_agent.web_evidence_runtime import execute_web_evidence_snapshot


class FixtureTransport:
    live_network = False

    def __init__(self, response: SourceResponse) -> None:
        self.response = response
        self.calls = 0

    def fetch(self, *, url, headers, allowed_hosts, timeout_seconds, byte_ceiling):
        self.calls += 1
        assert "Authorization" not in headers
        assert "Cookie" not in headers
        assert url in {self.response.final_url, "https://investor.example.com/start"}
        assert allowed_hosts == {"investor.example.com"}
        assert timeout_seconds == 7
        assert byte_ceiling == 4096
        return self.response


def _args(tmp_path: Path, **overrides):
    args = {
        "url": "https://investor.example.com/start",
        "domain": "investor.example.com",
        "source_class": "company_ir_material",
        "web_scope_policy_ids": ["official_ir_only"],
        "claim_types": ["issuer_demand_statement"],
        "company_domain_verified": True,
        "company_domains": ["investor.example.com"],
        "web_scope_allowed_domains": ["investor.example.com"],
        "web_capture_root": str(tmp_path),
        "fetch_timeout_s": 7,
        "byte_ceiling": 4096,
        "source_title": "Example IR results",
    }
    args.update(overrides)
    return args


def test_trusted_html_is_capture_first_parsed_and_promoted(tmp_path: Path) -> None:
    body = b"<html><body><h1>Quarterly results</h1><p>Data center demand increased while supply remained constrained.</p></body></html>"
    response = SourceResponse(
        200,
        "https://investor.example.com/results",
        {"content-type": "text/html"},
        body,
        ({"status_code": 302, "from_url": "https://investor.example.com/start", "to_url": "https://investor.example.com/results", "location": "/results"},),
    )
    transport = FixtureTransport(response)
    result = execute_web_evidence_snapshot(_args(tmp_path), transport=transport)

    assert result["status"] == "ok"
    assert result["capture_before_parse"] is True
    assert result["promotion"]["decision"] == "promote_parsed_evidence"
    assert result["evidence_rows"][0]["writer_citable"] is True
    assert result["evidence_rows"][0]["exact_value_authority"] is False
    assert result["redirect_chain"][0]["status_code"] == 302
    assert len(result["artifact_refs"]) == 4
    response_capture = json.loads(
        (tmp_path / "objects" / result["response_capture"]["object_key"]).read_text(encoding="utf-8")
    )
    assert response_capture["body_sha256"]
    assert response_capture["body_base64"]
    assert response_capture["capture_before_parse"] is True


def test_news_parses_but_cannot_promote_to_evidence(tmp_path: Path) -> None:
    response = SourceResponse(
        200,
        "https://investor.example.com/news",
        {"content-type": "application/json"},
        b'{"headline":"Supplier commentary","detail":"unverified demand context"}',
    )
    result = execute_web_evidence_snapshot(
        _args(
            tmp_path,
            url="https://investor.example.com/news",
            source_class="major_financial_news",
            company_domain_verified=False,
            company_domains=[],
        ),
        transport=FixtureTransport(response),
    )

    assert result["status"] == "partial"
    assert result["promotion"]["decision"] == "retain_context_only"
    assert result["evidence_rows"] == []
    assert result["context_rows"][0]["writer_citable"] is False
    assert result["source_gaps"][0]["reason_code"] == "web_evidence_source_class_context_only"


def test_unverified_or_cross_domain_request_fails_before_transport(tmp_path: Path) -> None:
    response = SourceResponse(200, "https://evil.example/a", {"content-type": "text/html"}, b"<p>ignored</p>")
    transport = FixtureTransport(response)
    unverified = execute_web_evidence_snapshot(
        _args(tmp_path, company_domain_verified=False),
        transport=transport,
    )
    cross_domain = execute_web_evidence_snapshot(
        _args(tmp_path, url="https://evil.example/a"),
        transport=transport,
    )

    assert unverified["error"] == "web_evidence_company_domain_not_verified"
    assert cross_domain["error"] == "web_evidence_domain_not_allowlisted"
    assert transport.calls == 0


def test_parser_failure_retains_request_and_response_without_promotion(tmp_path: Path) -> None:
    response = SourceResponse(
        200,
        "https://investor.example.com/start",
        {"content-type": "application/octet-stream"},
        b"\x00\x01\x02",
    )
    result = execute_web_evidence_snapshot(_args(tmp_path), transport=FixtureTransport(response))

    assert result["status"] == "error"
    assert result["error"] == "web_evidence_all_parsers_failed"
    assert result["promotion"]["decision"] == "reject"
    assert result["evidence_rows"] == []
    assert result["request_capture"]["digest"]
    assert result["response_capture"]["digest"]
    assert result["parser_capture"]["digest"]
    assert len(result["artifact_refs"]) == 3
