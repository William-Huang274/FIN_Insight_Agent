from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any, Mapping

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore  # noqa: E402
from sec_agent.official_source_attempt_program import (  # noqa: E402
    CAPTURE_SCHEMA_SAFE_FAILURE_V1_1,
    CaptureFirstOfficialSourceClient,
    JinaReaderOfficialSourceTransport,
    OfficialSourceAttemptError,
    SourceResponse,
)
from sec_agent.s1_dell_official_source_recovery_successor import (  # noqa: E402
    DellOfficialSourceRecoverySuccessorError,
    execute_dell_official_source_recovery_successor,
    load_dell_official_source_recovery_policy,
)


POLICY_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s1_dell_official_source_recovery_successor_policy_v1_0.json"
)


def _dell_text() -> str:
    return (
        "In Q1, we booked 24.4 billion in AI orders and exited with 51.3 billion "
        "of AI backlog. Demand continues to exceed supply with memory as the primary "
        "constraint. Against memory uncertainty, customers proactively secured "
        "infrastructure; Dell maintained pricing and margin discipline. Management "
        "described AI server profitability against a mid-single-digit operating "
        "income rate target."
    )


def _micron_text() -> str:
    return (
        "DRAM and NAND industry demand continues to significantly exceed industry "
        "supply. We expect tight conditions to persist beyond calendar 2027. The "
        "Singapore site will become another center of excellence for advanced "
        "packaging and will contribute to HBM packaging capacity beginning in the "
        "first half of calendar year 2027."
    )


class FixtureManagedReaderTransport:
    live_network = False
    capture_metadata = {
        "transport_mode": "managed_reader_exact_url",
        "retrieval_intermediary": "jina_reader",
        "retrieval_intermediary_endpoint": "https://r.jina.ai/",
        "origin_direct_response_bytes_preserved": False,
        "intermediary_raw_response_preserved": True,
    }

    def __init__(
        self,
        *,
        fail_dell: bool = False,
        missing_micron_anchor: bool = False,
        final_url_override: str = "",
    ) -> None:
        self.fail_dell = fail_dell
        self.missing_micron_anchor = missing_micron_anchor
        self.final_url_override = final_url_override

    def fetch(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        allowed_hosts: set[str],
        timeout_seconds: int,
        byte_ceiling: int,
    ) -> SourceResponse:
        del headers, allowed_hosts, timeout_seconds, byte_ceiling
        if "delltechnologies.com" in url and self.fail_dell:
            raise OfficialSourceAttemptError("official_source_transport_timeout")
        content = _dell_text() if "delltechnologies.com" in url else _micron_text()
        if self.missing_micron_anchor and "micron.com" in url:
            content = "Micron discussed memory demand without a bounded capacity date."
        body = json.dumps(
            {"code": 200, "data": {"url": url, "content": content}},
            ensure_ascii=False,
        ).encode("utf-8")
        return SourceResponse(
            status_code=200,
            final_url=self.final_url_override or url,
            headers={"content-type": "application/json; charset=utf-8"},
            body=body,
            transport_metadata={**self.capture_metadata, "origin_url_echo": url},
        )


def _execute(tmp_path: Path, **kwargs: Any) -> dict[str, Any]:
    policy = load_dell_official_source_recovery_policy(
        POLICY_PATH, repo_root=ROOT
    )
    return execute_dell_official_source_recovery_successor(
        policy=policy,
        repo_root=ROOT,
        runtime_root=tmp_path / "runtime",
        transport=FixtureManagedReaderTransport(**kwargs),
        observed_at="2026-08-10T18:00:00Z",
        execution_commit="0" * 40,
    )


def test_recovery_successor_reuses_successes_and_materializes_five_items(
    tmp_path: Path,
) -> None:
    result = _execute(tmp_path)
    assert result["gate_status"] == {
        "core_research_ready": True,
        "supplier_context_ready": True,
        "valuation_input_ready": True,
        "valuation_ready": True,
        "successor_pack_ready_for_model_input": True,
    }
    assert result["observed_counts"]["official_source_network_calls"] == 0
    assert result["observed_counts"]["new_evidence_items"] == 5
    assert result["observed_counts"]["evidence_items_after"] == 27
    assert result["observed_counts"]["residual_gaps_after"] == 14
    assert result["observed_counts"]["reused_numeric_facts"] == 1
    for route in result["route_results"]:
        assert route["status"] == "captured_parsed_and_adjudicated"
        assert route["retrieval_intermediary_is_financial_authority"] is False


def test_dell_timeout_keeps_core_closed_but_preserves_partial_result(
    tmp_path: Path,
) -> None:
    result = _execute(tmp_path, fail_dell=True)
    assert result["gate_status"]["core_research_ready"] is False
    assert result["gate_status"]["supplier_context_ready"] is True
    assert result["gate_status"]["valuation_input_ready"] is True
    assert result["observed_counts"]["new_evidence_items"] == 2
    assert result["route_results"][0]["failure_code"] == (
        "official_source_transport_timeout"
    )


def test_micron_anchor_gap_is_optional_and_does_not_close_core(
    tmp_path: Path,
) -> None:
    result = _execute(tmp_path, missing_micron_anchor=True)
    assert result["gate_status"]["core_research_ready"] is True
    assert result["gate_status"]["supplier_context_ready"] is False
    assert result["gate_status"]["successor_pack_ready_for_model_input"] is True


def test_managed_reader_final_url_pollution_fails_closed(tmp_path: Path) -> None:
    result = _execute(
        tmp_path,
        final_url_override="https://example.com/cross-case-pollution",
    )
    assert result["gate_status"]["core_research_ready"] is False
    assert all(row["status"] == "rejected_final_url" for row in result["route_results"])


def test_timeout_capture_mutation_breaks_policy_load(tmp_path: Path) -> None:
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    pair = policy["immutable_bindings"]["timeout_capture_pairs"][0]
    failure = json.loads((ROOT / pair["failure_ref"]).read_text(encoding="utf-8"))
    failure["safe_cause_class"] = "dns_resolution_failure"
    mutated = tmp_path / "mutated-failure.json"
    mutated.write_text(json.dumps(failure), encoding="utf-8")
    from sec_agent.s1_six_case_local_evidence_pack import file_sha256

    pair["failure_ref"] = str(mutated)
    pair["failure_sha256"] = file_sha256(mutated)
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    with pytest.raises(
        DellOfficialSourceRecoverySuccessorError,
        match="dell_official_recovery_timeout_autopsy_invalid",
    ):
        load_dell_official_source_recovery_policy(policy_path, repo_root=ROOT)


class _FakeReaderResponse:
    def __init__(self, *, target: str, echoed: str | None = None, content: str = "") -> None:
        self.status_code = 200
        self.url = "https://r.jina.ai/" + target
        self.history: list[Any] = []
        self.headers = {"content-type": "application/json"}
        self.content = json.dumps(
            {
                "code": 200,
                "data": {"url": echoed or target, "content": content or _dell_text()},
            }
        ).encode()


def test_jina_transport_preserves_raw_response_and_declares_intermediary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import requests
    import sec_agent.official_source_attempt_program as program

    target = (
        "https://investors.delltechnologies.com/static-files/"
        "b63ffff9-b729-403b-a231-c6af05667759"
    )
    monkeypatch.setattr(program, "_require_public_network_host", lambda _host: None)
    monkeypatch.setattr(
        requests,
        "get",
        lambda *args, **kwargs: _FakeReaderResponse(target=target),
    )
    store = FileCanonicalObjectStore(tmp_path / "objects")
    client = CaptureFirstOfficialSourceClient(
        store=store,
        transport=JinaReaderOfficialSourceTransport(),
        capture_schema=CAPTURE_SCHEMA_SAFE_FAILURE_V1_1,
    )
    response, attempt = client.fetch(
        case_key="DELL",
        route_id="dell_q1_fy27_earnings_transcript",
        url=target,
        allowed_hosts={"investors.delltechnologies.com"},
        timeout_seconds=10,
        byte_ceiling=100_000,
    )
    assert attempt["status"] == "captured"
    assert response is not None and response.body.startswith(b'{"code": 200')
    capture = store.get_json(
        attempt["response_capture"]["object_key"],
        expected_digest=attempt["response_capture"]["digest"],
    )
    assert capture["transport_metadata"]["retrieval_intermediary"] == "jina_reader"
    assert capture["transport_metadata"]["origin_direct_response_bytes_preserved"] is False
    assert capture["transport_metadata"]["intermediary_raw_response_preserved"] is True


def test_jina_transport_rejects_origin_url_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import requests
    import sec_agent.official_source_attempt_program as program

    target = "https://investors.delltechnologies.com/static-files/expected"
    monkeypatch.setattr(program, "_require_public_network_host", lambda _host: None)
    monkeypatch.setattr(
        requests,
        "get",
        lambda *args, **kwargs: _FakeReaderResponse(
            target=target,
            echoed="https://investors.micron.com/static-files/cross-case",
        ),
    )
    with pytest.raises(
        OfficialSourceAttemptError,
        match="official_source_reader_original_url_mismatch",
    ):
        JinaReaderOfficialSourceTransport().fetch(
            url=target,
            headers={"User-Agent": "fixture"},
            allowed_hosts={"investors.delltechnologies.com"},
            timeout_seconds=10,
            byte_ceiling=100_000,
        )


def test_policy_rejects_provider_authority_escalation(tmp_path: Path) -> None:
    policy = deepcopy(json.loads(POLICY_PATH.read_text(encoding="utf-8")))
    policy["retrieval_transport"]["provider_is_financial_authority"] = True
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(policy), encoding="utf-8")
    with pytest.raises(
        DellOfficialSourceRecoverySuccessorError,
        match="dell_official_recovery_transport_contract_invalid",
    ):
        load_dell_official_source_recovery_policy(path, repo_root=ROOT)
