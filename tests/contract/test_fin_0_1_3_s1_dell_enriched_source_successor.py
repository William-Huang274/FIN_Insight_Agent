from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from sec_agent.market_data_adapter import (
    AkshareDailyShadowAdapter,
    AlphaVantageDailyAdapter,
    MarketDataRawResponse,
    MarketPointRequest,
)
from sec_agent.official_source_attempt_program import (
    OfficialSourceAttemptError,
    SourceResponse,
)
from sec_agent.s1_dell_enriched_source_successor import (
    _lf_normalized_utf8_sha256,
    execute_dell_enriched_source_successor,
    load_dell_enriched_source_policy,
)
from sec_agent.s1_six_case_local_evidence_pack import file_sha256


ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "configs/runtime/fin_ia_0_1_3_s1_dell_enriched_source_successor_policy_v1_0.json"


DELL_TEXT = """
<html><body>
Dell reported 24.4 billion of AI orders and 51.3 billion of backlog while demand continued to exceed supply.
Management discussed memory uncertainty, said it had proactively secured supply, and maintained pricing and margin discipline.
AI server profitability was measured against a mid-single-digit operating income rate target.
</body></html>
""".encode()

MICRON_TEXT = """
<html><body>
Micron expects supply-demand conditions to remain tight beyond 2027 across DRAM and NAND.
Its advanced packaging facility should add HBM packaging capacity in the first half of 2027.
</body></html>
""".encode()


class FixtureOfficialTransport:
    live_network = False

    def __init__(self, *, fail_dell: bool = False) -> None:
        self.fail_dell = fail_dell

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
        if "delltechnologies.com" in url:
            if self.fail_dell:
                raise OfficialSourceAttemptError("official_source_transport_failed")
            body = DELL_TEXT
        else:
            body = MICRON_TEXT
        return SourceResponse(
            status_code=200,
            final_url=url,
            headers={"content-type": "text/html; charset=utf-8"},
            body=body,
        )


class FixturePrimaryAdapter(AlphaVantageDailyAdapter):
    live_network = False

    def __init__(self, *, include_date: bool = True) -> None:
        self.include_date = include_date

    def fetch(
        self,
        *,
        request: MarketPointRequest,
        credential: str | None,
        timeout_seconds: int,
        byte_ceiling: int,
    ) -> MarketDataRawResponse:
        del credential, timeout_seconds, byte_ceiling
        selected_date = request.exact_date if self.include_date else "2026-08-05"
        payload = {
            "Meta Data": {"2. Symbol": request.ticker, "5. Time Zone": "US/Eastern"},
            "Time Series (Daily)": {selected_date: {"4. close": "142.3700"}},
        }
        return MarketDataRawResponse(
            status_code=200,
            safe_endpoint=(
                "https://www.alphavantage.co/query?"
                "function=TIME_SERIES_DAILY&symbol=DELL&outputsize=compact&datatype=json"
            ),
            headers={"content-type": "application/json"},
            body=json.dumps(payload).encode(),
        )


class FixtureShadowAdapter(AkshareDailyShadowAdapter):
    live_network = False

    def fetch(
        self,
        *,
        request: MarketPointRequest,
        credential: str | None,
        timeout_seconds: int,
        byte_ceiling: int,
    ) -> MarketDataRawResponse:
        del credential, timeout_seconds, byte_ceiling
        return MarketDataRawResponse(
            status_code=200,
            safe_endpoint="akshare://stock_us_hist?symbol=106.DELL&adjust=raw",
            headers={"content-type": "application/json"},
            body=json.dumps([{"日期": request.exact_date, "收盘": 142.37}], ensure_ascii=False).encode(),
        )


def _run(
    tmp_path: Path,
    *,
    fail_dell: bool = False,
    include_market_date: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    policy = load_dell_enriched_source_policy(POLICY, repo_root=ROOT)
    result = execute_dell_enriched_source_successor(
        policy=policy,
        repo_root=ROOT,
        runtime_root=tmp_path / "runtime",
        official_transport=FixtureOfficialTransport(fail_dell=fail_dell),
        primary_market_adapter=FixturePrimaryAdapter(include_date=include_market_date),
        primary_market_credential="fixture-secret",
        shadow_market_adapter=FixtureShadowAdapter(),
        observed_at="2026-08-10T10:00:00+08:00",
        execution_commit="a" * 40,
    )
    ref = result["successor_pack_artifact"]
    pack_path = tmp_path / "runtime/objects" / ref["object_key"]
    pack = json.loads(pack_path.read_text(encoding="utf-8"))
    return result, pack


def test_all_gates_true_compile_27_evidence_without_promoting_shadow(tmp_path: Path) -> None:
    policy = load_dell_enriched_source_policy(POLICY, repo_root=ROOT)
    predecessor = ROOT / policy["immutable_bindings"]["predecessor_dell_pack"]["ref"]
    before = file_sha256(predecessor)
    result, pack = _run(tmp_path)
    assert file_sha256(predecessor) == before
    assert result["gate_status"] == {
        "core_research_ready": True,
        "supplier_context_ready": True,
        "valuation_input_ready": True,
        "valuation_ready": True,
        "successor_pack_ready_for_model_input": True,
    }
    assert result["observed_counts"]["evidence_items_before"] == 20
    assert result["observed_counts"]["evidence_items_after"] == 27
    assert result["observed_counts"]["residual_gaps_after"] == 14
    assert pack["observed_counts"]["numeric_facts"] == 1
    assert len(pack["numeric_facts"]) == 1
    assert pack["numeric_facts"][0]["provider_id"] == "alpha_vantage_time_series_daily"
    assert all(
        fact["provider_id"] != "akshare_eastmoney_us_hist_shadow"
        for fact in pack["numeric_facts"]
    )
    assert result["shadow_comparison"]["equal_to_cent"] is True
    assert result["stage_acceptance"]["shadow_provider_promoted"] is False


def test_core_ready_does_not_fail_when_valuation_input_is_missing(tmp_path: Path) -> None:
    result, pack = _run(tmp_path, include_market_date=False)
    assert result["gate_status"]["core_research_ready"] is True
    assert result["gate_status"]["valuation_input_ready"] is False
    assert result["gate_status"]["successor_pack_ready_for_model_input"] is True
    assert result["status"] == "terminal_succeeded_core_research_ready_with_typed_optional_gaps"
    assert pack["observed_counts"]["numeric_facts"] == 0
    assert any(gap["gap_id"] == "dell-gap-valuation-basis" for gap in pack["residual_gaps"])


def test_valuation_input_cannot_override_missing_core_issuer_evidence(tmp_path: Path) -> None:
    result, pack = _run(tmp_path, fail_dell=True)
    assert result["gate_status"]["core_research_ready"] is False
    assert result["gate_status"]["valuation_input_ready"] is True
    assert result["gate_status"]["successor_pack_ready_for_model_input"] is False
    assert result["status"] == "terminal_completed_core_research_not_ready"
    assert pack["observed_counts"]["numeric_facts"] == 1
    assert any(gap["gap_id"] == "dell-gap-ai-system-margin" for gap in pack["residual_gaps"])


def test_single_close_never_removes_relative_valuation_or_scenario_gaps(tmp_path: Path) -> None:
    _result, pack = _run(tmp_path)
    gaps = {row["gap_id"] for row in pack["residual_gaps"]}
    assert "dell-gap-price-in-boundary" in gaps
    assert "dell-gap-scenario-sensitivity" in gaps
    assert "dell-gap-valuation-basis" not in gaps


def test_tracked_json_binding_is_stable_across_crlf_and_lf_checkouts(
    tmp_path: Path,
) -> None:
    lf_path = tmp_path / "lf.json"
    crlf_path = tmp_path / "crlf.json"
    lf_path.write_bytes(b'{\n  "case_key": "DELL"\n}\n')
    crlf_path.write_bytes(b'{\r\n  "case_key": "DELL"\r\n}\r\n')

    assert _lf_normalized_utf8_sha256(lf_path) == _lf_normalized_utf8_sha256(
        crlf_path
    )

    crlf_path.write_bytes(b'{\r\n  "case_key": "MU"\r\n}\r\n')
    assert _lf_normalized_utf8_sha256(lf_path) != _lf_normalized_utf8_sha256(
        crlf_path
    )
