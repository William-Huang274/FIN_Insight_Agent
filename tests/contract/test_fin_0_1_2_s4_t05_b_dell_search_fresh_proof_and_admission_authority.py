from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Mapping

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "src"),
    str(ROOT / "scripts" / "releases"),
]

from apps.workbench.backend.application.fin_0_1_2_s4_t03_executable_agentic_search import (
    CASE_SEARCH_PROFILES,
    Fin012S4T03SearchError,
    SearchAdmission,
    SourceResponse,
    compile_current_case_executable_requests,
)
from run_fin_ia_0_1_2_s4_t05_current_search import (
    Fin012S4T05CurrentSearchRunner,
    ZeroCallIssuerTransport,
    compile_zero_call_admission,
    load_exact_admission,
    parse_dell_direct_ir_pdf_identity,
)
from sec_agent.canonical_runtime.models import canonical_digest


DECISION_REF = (
    "configs/releases/"
    "fin_ia_0_1_2_s4_t05_b_dell_current_search_fresh_zero_call_proof_"
    "and_admission_authority_decision_v1_0.json"
)
PROJECTION_REF = (
    "configs/runtime/fin_ia_0_1_2_current_program_projection_v2_52.json"
)
HISTORICAL_T03_RUNNER_REF = (
    "scripts/releases/run_fin_ia_0_1_2_s4_t03_agentic_search.py"
)


@pytest.fixture(scope="module")
def independent_proofs(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[dict[str, object], dict[str, object]]:
    root = tmp_path_factory.mktemp("fin012-s4-t05b-dell-independent")
    now = datetime(2026, 8, 5, 4, 0, 0, tzinfo=timezone.utc)
    admission = compile_zero_call_admission("DELL", now=now)
    rows = []
    for index in (1, 2):
        rows.append(
            Fin012S4T05CurrentSearchRunner(
                repository_root=ROOT,
                runtime_root=root / f"root-{index}",
                transport=ZeroCallIssuerTransport("DELL"),
            ).execute(
                admission=admission,
                now="2026-08-05T04:00:00Z",
                run_nonce=f"t05-b-dell-independent-proof-{index}",
            )
        )
    return rows[0], rows[1]


def _normalized_proof(result: Mapping[str, object]) -> dict[str, object]:
    request_results = result["request_results"]
    assert isinstance(request_results, list)
    return {
        "case_key": result["case_key"],
        "status": result["status"],
        "code": result["code"],
        "accepted_rejected": [
            [row["accepted_count"], row["rejected_count"]]
            for row in request_results
        ],
        "capture_count": len(result["capture_objects"]),
        "observed_counts": result["observed_counts"],
        "T04_consumption_authorized": result["T04_consumption_authorized"],
    }


def test_two_disposable_roots_prove_fresh_identity_and_stable_dell_search(
    independent_proofs: tuple[dict[str, object], dict[str, object]],
) -> None:
    first, second = independent_proofs
    assert (first["run_id"], first["attempt_id"]) != (
        second["run_id"],
        second["attempt_id"],
    )
    assert first["terminal_object"]["digest"] != second["terminal_object"]["digest"]
    assert _normalized_proof(first) == _normalized_proof(second)
    normalized = _normalized_proof(first)
    assert normalized == {
        "case_key": "DELL",
        "status": "success",
        "code": "three_request_current_evidence_candidate_pack_ready",
        "accepted_rejected": [[6, 9], [6, 0], [6, 3]],
        "capture_count": 8,
        "observed_counts": {
            "source_calls": 1,
            "live_source_network_calls": 0,
            "local_retrieval_or_tool_invocations": 6,
            "fallbacks": 0,
            "same_target_retries": 0,
            "model_calls": 0,
            "provider_calls": 0,
            "paid_api_cost_usd": 0.0,
            "accepted_candidates": 18,
            "rejected_candidates": 12,
            "business_artifacts": 0,
        },
        "T04_consumption_authorized": True,
    }


def test_dell_request_and_prospective_admission_are_exact_and_zero_model() -> None:
    requests = compile_current_case_executable_requests("DELL")
    assert [row.program_cell_id for row in requests] == [
        "bottleneck_counterevidence_and_what_would_change",
        "demand_authenticity_and_sustainability",
        "value_and_profit_capture",
    ]
    assert [row.request_digest for row in requests] == [
        "be255ecdf977f6f1db1fd0518b51c971cf87514685383fb7c7edd1eed5c04bd6",
        "39d1c34d94254a45be8fcdf35630721abd44ca04ebd1e8d9215ca6682bd2f214",
        "1d5ecad23a19cb1fa29bb7a4d3cfd21047bae42464c2b9c32639c7956ce30ec0",
    ]
    assert all(row.case_key == row.target_entity_ref == "DELL" for row in requests)
    assert all(row.candidate_ceiling == 6 for row in requests)
    profile = CASE_SEARCH_PROFILES["DELL"]
    assert profile["cik"] == "0001571996"
    assert str(profile["sec_submissions_url"]).startswith("https://")
    assert str(profile["ir_url"]).startswith("https://")
    admission = compile_zero_call_admission(
        "DELL", now=datetime(2026, 8, 5, 4, 0, 0, tzinfo=timezone.utc)
    )
    assert (
        admission.source_network_call_ceiling,
        admission.local_invocation_ceiling,
        admission.retry_ceiling,
        admission.fallback_ceiling,
        admission.wall_clock_seconds,
        admission.model_calls,
        admission.provider_calls,
        admission.paid_api_cost_usd,
    ) == (2, 8, 0, 1, 300, 0, 0, 0.0)


@dataclass
class _Budget:
    source_calls: int = 0
    local_invocations: int = 0
    fallbacks: int = 0


class _DellFallbackTransport:
    live_network = False

    def __init__(self) -> None:
        self.calls = 0

    def fetch(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        allowed_hosts: set[str],
        timeout_seconds: int,
    ) -> SourceResponse:
        self.calls += 1
        assert "Authorization" not in headers
        assert "Cookie" not in headers
        if self.calls == 1:
            return SourceResponse(
                status_code=200,
                final_url=url,
                headers={"content-type": "application/json"},
                body=b'{"filings":{"recent":{}}}',
            )
        return SourceResponse(
            status_code=200,
            final_url=str(CASE_SEARCH_PROFILES["DELL"]["ir_url"]),
            headers={
                "content-type": "application/pdf",
                "last-modified": "Thu, 28 May 2026 12:00:00 GMT",
            },
            body=b"%PDF-1.7 bounded-fixture",
        )


def test_dell_direct_pdf_fallback_is_capture_first_and_date_bound(tmp_path: Path) -> None:
    transport = _DellFallbackTransport()
    runner = Fin012S4T05CurrentSearchRunner(
        repository_root=ROOT,
        runtime_root=tmp_path / "fallback",
        transport=transport,
    )
    budget = _Budget()
    admission = compile_zero_call_admission(
        "DELL", now=datetime(2026, 8, 5, 4, 0, 0, tzinfo=timezone.utc)
    )
    identities = runner._load_official_filing_identities(
        case_key="DELL",
        as_of="2026-07-21T00:00:00Z",
        admission=admission,
        budget=budget,
    )
    assert [budget.source_calls, budget.fallbacks, transport.calls] == [2, 1, 2]
    assert len(runner.source_client.capture_objects) == 4
    assert len(identities) == 1
    identity = identities[0]
    assert identity.filed_at == "2026-05-28"
    assert identity.parser_adapter == "dell_ir_direct_pdf_last_modified_identity_v1"
    assert identity.source_url == CASE_SEARCH_PROFILES["DELL"]["ir_url"]


@pytest.mark.parametrize(
    ("headers", "body", "code"),
    (
        ({"content-type": "text/html"}, b"<html></html>", "t05_dell_ir_fallback_not_pdf"),
        ({"content-type": "application/pdf"}, b"%PDF", "t05_dell_ir_fallback_last_modified_invalid"),
        (
            {
                "content-type": "application/pdf",
                "last-modified": "Wed, 05 Aug 2027 00:00:00 GMT",
            },
            b"%PDF",
            "t05_dell_ir_fallback_future_dated",
        ),
    ),
)
def test_dell_pdf_fallback_mutations_fail_closed(
    headers: Mapping[str, str], body: bytes, code: str
) -> None:
    with pytest.raises(Fin012S4T03SearchError, match=code):
        parse_dell_direct_ir_pdf_identity(
            SourceResponse(
                status_code=200,
                final_url=str(CASE_SEARCH_PROFILES["DELL"]["ir_url"]),
                headers=headers,
                body=body,
            ),
            as_of="2026-07-21T00:00:00Z",
            response_capture={"object_key": "fixture/object", "digest": "a" * 64},
        )


def test_cross_case_admission_is_rejected_before_transport(tmp_path: Path) -> None:
    admission = compile_zero_call_admission(
        "MU", now=datetime(2026, 8, 5, 4, 0, 0, tzinfo=timezone.utc)
    )
    path = tmp_path / "wrong-case-admission.json"
    path.write_text(json.dumps(admission.as_dict()), encoding="utf-8")
    with pytest.raises(ValueError, match="t05_current_search_admission_case_mismatch"):
        load_exact_admission(path, case_key="DELL")


def test_authority_decision_and_projection_are_honest_and_content_addressed() -> None:
    decision = json.loads((ROOT / DECISION_REF).read_text(encoding="utf-8"))
    assert decision["decision_digest"] == canonical_digest(
        {key: value for key, value in decision.items() if key != "decision_digest"}
    )
    assert decision["status"] == (
        "pass_DELL_current_search_admission_issuance_authorized_not_issued_no_live"
    )
    assert decision["authority"]["admission_issuance_authorized_next"] is True
    assert decision["authority"]["admission_issued"] is False
    assert decision["authority"]["source_live_authorized_this_decision"] is False
    assert decision["authority"]["agent_or_model_live_authorized"] is False
    for binding in decision["immutable_bindings"]:
        assert hashlib.sha256((ROOT / binding["ref"]).read_bytes()).hexdigest() == (
            binding["sha256"]
        )
    assert hashlib.sha256((ROOT / HISTORICAL_T03_RUNNER_REF).read_bytes()).hexdigest() == (
        "988939424a7701b2a72dd1e90f833b69f545ebeb23420afdce07f3a69cb0e80d"
    )
    projection = json.loads((ROOT / PROJECTION_REF).read_text(encoding="utf-8"))
    assert projection["current_truth"]["S4_T05_B_DELL"] == (
        "search_admission_issuance_authorized_not_issued"
    )
    assert projection["current_truth"]["DELL_current_R2"] is False
    assert projection["authority_boundary"]["DELL_search_admission_issued"] is False
    assert projection["authority_boundary"]["DELL_source_live_executed"] is False
