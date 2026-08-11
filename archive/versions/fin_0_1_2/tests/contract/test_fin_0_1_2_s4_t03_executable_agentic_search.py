from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.fin_0_1_2_s4_t03_executable_agentic_search import (
    ALLOWED_SOURCE_HOSTS,
    CaptureFirstSourceClient,
    Fin012S4T03SearchError,
    Fin012S4T03SearchRunner,
    ROUTE_REGISTRY,
    SearchAdmission,
    SearchCandidate,
    SourceResponse,
    compile_current_nvda_executable_requests,
    parse_sec_submissions,
    qualify_candidates,
)
from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore


FILINGS = (
    ("0001045810-26-000051", "8-K", "2026-05-20", "nvda-20260520.htm"),
    ("0001045810-25-000230", "10-Q", "2025-11-19", "nvda-20251026.htm"),
    ("0001045810-25-000023", "10-K", "2025-02-26", "nvda-20250126.htm"),
    ("0001045810-24-000029", "10-K", "2024-02-21", "nvda-20240128.htm"),
    ("0001045810-23-000017", "10-K", "2023-02-24", "nvda-20230129.htm"),
)


def _submissions_payload(*, include_future: bool = False) -> bytes:
    rows = list(FILINGS)
    if include_future:
        rows.insert(
            0,
            ("0001045810-26-999999", "8-K", "2026-07-22", "future.htm"),
        )
    payload = {
        "filings": {
            "recent": {
                "accessionNumber": [row[0] for row in rows],
                "form": [row[1] for row in rows],
                "filingDate": [row[2] for row in rows],
                "primaryDocument": [row[3] for row in rows],
            }
        }
    }
    return json.dumps(payload).encode("utf-8")


class _FakeSecTransport:
    live_network = False

    def __init__(self, *, body: bytes | None = None, final_url: str | None = None) -> None:
        self.body = body if body is not None else _submissions_payload()
        self.final_url = final_url
        self.calls: list[str] = []

    def fetch(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        allowed_hosts: set[str],
        timeout_seconds: int,
    ) -> SourceResponse:
        self.calls.append(url)
        assert "Authorization" not in headers
        assert "Cookie" not in headers
        return SourceResponse(
            status_code=200,
            final_url=self.final_url or url,
            headers={"content-type": "application/json", "set-cookie": "must-not-persist"},
            body=self.body,
        )


class _SecThenIrTransport:
    live_network = False

    def __init__(self) -> None:
        self.calls = 0

    def fetch(self, *, url: str, headers: Mapping[str, str], allowed_hosts: set[str], timeout_seconds: int) -> SourceResponse:
        self.calls += 1
        if self.calls == 1:
            return SourceResponse(200, url, {"content-type": "application/json"}, b"not-json")
        body = b'<html><a href="/financial-info/quarterly-results/2026-05-20">Quarterly results 2026-05-20</a></html>'
        return SourceResponse(200, url, {"content-type": "text/html"}, body)


class _UnexpectedFailureTransport:
    live_network = False

    def fetch(self, **_: Any) -> SourceResponse:
        raise AssertionError("injected unexpected transport defect")


def _admission() -> SearchAdmission:
    requests = compile_current_nvda_executable_requests()
    return SearchAdmission.create(
        issued_at="2026-08-04T00:00:00Z",
        expires_at="2026-08-05T00:00:00Z",
        request_digests=tuple(row.request_digest for row in requests),
    )


def _candidate(request, **overrides: Any) -> SearchCandidate:
    payload: dict[str, Any] = {
        "request_digest": request.request_digest,
        "program_cell_id": request.program_cell_id,
        "entity_ref": "NVDA",
        "candidate_role": request.accepted_candidate_roles[0],
        "adapter_id": "fixture_read_only",
        "route_id": request.metadata_route_ids[0],
        "title": "fixture",
        "excerpt": "fixture evidence excerpt",
        "published_at": "2026-05-20",
        "source_url": "https://www.sec.gov/Archives/edgar/data/1045810/fixture.htm",
        "locator": "Item 1",
        "source_snapshot_ref": "objects/source.json",
        "source_snapshot_digest": canonical_digest({"source": "fixture"}),
        "parser_adapter": "fixture_parser_v1",
        "parser_digest": canonical_digest({"parser": "fixture"}),
        "source_authority_rank": 100,
        "score": 1.0,
        "exact_value_authority": False,
    }
    payload.update(overrides)
    return SearchCandidate.create(**payload)


def test_compiler_binds_three_requests_to_queries_routes_sources_and_nonpromotion() -> None:
    requests = compile_current_nvda_executable_requests()
    assert len(requests) == 3
    assert len({row.request_digest for row in requests}) == 3
    assert {route for row in requests for route in row.metadata_route_ids} == set(ROUTE_REGISTRY)
    for request in requests:
        request.require_valid()
        assert request.case_key == request.target_entity_ref == "NVDA"
        assert request.query_text
        assert request.candidate_ceiling == 6
        assert set(request.source_allowlist) == ALLOWED_SOURCE_HOSTS
        assert request.writer_citable is False
        assert request.domain_judgment_eligible is False


def test_request_and_admission_digest_or_identity_mutation_fails_closed() -> None:
    requests = compile_current_nvda_executable_requests()
    with pytest.raises(Fin012S4T03SearchError, match="t03_executable_request_digest_mismatch"):
        replace(requests[0], query_text="mutated").require_valid()
    admission = _admission()
    with pytest.raises(Fin012S4T03SearchError, match="t03_admission_digest_mismatch"):
        replace(admission, local_invocation_ceiling=7).require_active(
            now="2026-08-04T12:00:00Z", requests=requests
        )
    with pytest.raises(Fin012S4T03SearchError, match="t03_admission_not_active"):
        admission.require_active(now="2026-08-06T00:00:00Z", requests=requests)


def test_source_capture_is_request_then_complete_response_before_parse_and_redacts_headers(tmp_path: Path) -> None:
    store = FileCanonicalObjectStore(tmp_path / "objects")
    client = CaptureFirstSourceClient(store=store, transport=_FakeSecTransport())
    response = client.fetch(
        url="https://data.sec.gov/submissions/CIK0001045810.json",
        allowed_hosts=ALLOWED_SOURCE_HOSTS,
    )
    assert len(client.capture_objects) == 2
    request_capture = store.get_json(client.capture_objects[0]["object_key"])
    response_capture = store.get_json(client.capture_objects[1]["object_key"])
    assert request_capture["capture_kind"] == "source_request"
    assert response_capture["capture_kind"] == "source_response"
    assert response_capture["capture_before_parse"] is True
    assert response_capture["body_sha256"] == hashlib.sha256(response.body).hexdigest()
    assert "set-cookie" not in response_capture["headers"]
    assert response_capture["credential_cookie_authorization_present"] is False


def test_nonallowlisted_final_url_is_captured_then_blocked(tmp_path: Path) -> None:
    store = FileCanonicalObjectStore(tmp_path / "objects")
    client = CaptureFirstSourceClient(
        store=store,
        transport=_FakeSecTransport(final_url="https://evil.example/redirected"),
    )
    with pytest.raises(Fin012S4T03SearchError, match="t03_source_final_url_not_allowlisted_https"):
        client.fetch(
            url="https://data.sec.gov/submissions/CIK0001045810.json",
            allowed_hosts=ALLOWED_SOURCE_HOSTS,
        )
    assert len(client.capture_objects) == 2


def test_sec_parser_rejects_future_filings_without_losing_source_capture_ref() -> None:
    response = SourceResponse(
        200,
        "https://data.sec.gov/submissions/CIK0001045810.json",
        {"content-type": "application/json"},
        _submissions_payload(include_future=True),
    )
    capture = {"object_key": "capture.json", "digest": canonical_digest({"capture": 1})}
    rows = parse_sec_submissions(response, as_of="2026-07-21T00:00:00Z", response_capture=capture)
    assert rows
    assert all(row.filed_at <= "2026-07-21" for row in rows)
    assert all(row.source_capture_ref == "capture.json" for row in rows)
    assert "000104581026999999" not in {row.accession for row in rows}


def test_evidence_gate_rejects_duplicate_cross_case_future_and_missing_citation() -> None:
    request = compile_current_nvda_executable_requests()[0]
    good = _candidate(request)
    rows = (
        good,
        good,
        _candidate(request, entity_ref="MU"),
        _candidate(request, published_at="2026-07-22"),
        _candidate(request, source_url=""),
    )
    accepted, rejected = qualify_candidates(request, rows)
    assert len(accepted) == 1
    reasons = {reason for row in rejected for reason in row["reason_codes"]}
    assert {
        "duplicate_candidate_id",
        "cross_case_entity",
        "candidate_after_as_of",
        "https_citation_required",
    }.issubset(reasons)


def test_three_request_full_fake_executes_real_local_6_call_chain_and_terminalizes(tmp_path: Path) -> None:
    runner = Fin012S4T03SearchRunner(
        repository_root=ROOT,
        runtime_root=tmp_path / "runtime",
        transport=_FakeSecTransport(),
    )
    result = runner.execute(
        admission=_admission(),
        now="2026-08-04T12:00:00Z",
        run_nonce="full-fake-three-request-proof",
    )
    assert result["status"] == "success"
    assert result["code"] == "three_request_current_evidence_candidate_pack_ready"
    assert len(result["request_results"]) == 3
    assert all(row["accepted_count"] > 0 for row in result["request_results"])
    assert result["observed_counts"] == {
        "source_calls": 1,
        "live_source_network_calls": 0,
        "local_retrieval_or_tool_invocations": 6,
        "fallbacks": 0,
        "same_target_retries": 0,
        "model_calls": 0,
        "provider_calls": 0,
        "paid_api_cost_usd": 0.0,
        "accepted_candidates": sum(row["accepted_count"] for row in result["request_results"]),
        "rejected_candidates": sum(row["rejected_count"] for row in result["request_results"]),
        "business_artifacts": 0,
    }
    assert result["T04_consumption_authorized"] is True
    assert result["writer_citable_in_T03"] is False
    assert result["domain_judgment_eligible_in_T03"] is False
    assert result["terminal_object"]["digest"] == canonical_digest(
        {key: value for key, value in result.items() if key != "terminal_object"}
    )


def test_parser_failure_uses_single_ir_fallback_and_preserves_typed_gap(tmp_path: Path) -> None:
    runner = Fin012S4T03SearchRunner(
        repository_root=ROOT,
        runtime_root=tmp_path / "runtime",
        transport=_SecThenIrTransport(),
    )
    result = runner.execute(
        admission=_admission(),
        now="2026-08-04T12:00:00Z",
        run_nonce="single-fallback-proof",
    )
    assert result["status"] == "bounded_gap"
    assert result["observed_counts"]["source_calls"] == 2
    assert result["observed_counts"]["fallbacks"] == 1
    assert result["observed_counts"]["same_target_retries"] == 0
    assert len(runner.source_client.capture_objects) == 4
    assert any(row["typed_gap_codes"] for row in result["request_results"])


def test_unexpected_post_request_failure_still_materializes_terminal_and_capture(tmp_path: Path) -> None:
    runner = Fin012S4T03SearchRunner(
        repository_root=ROOT,
        runtime_root=tmp_path / "runtime",
        transport=_UnexpectedFailureTransport(),
    )
    result = runner.execute(
        admission=_admission(),
        now="2026-08-04T12:00:00Z",
        run_nonce="terminal-preservation-proof",
    )
    assert result["status"] == "failed"
    assert result["phase"] == "official_source_identity"
    assert result["code"] == "unexpected_project_failure:AssertionError"
    assert len(result["capture_objects"]) == 1
    assert result["terminal_object"]["artifact_type"] == "typed_terminal_result"
