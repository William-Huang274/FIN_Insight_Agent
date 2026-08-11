from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.market_data_adapter import (  # noqa: E402
    AkshareDailyShadowAdapter,
    AlphaVantageDailyAdapter,
    MarketDataRawResponse,
    MarketPointRequest,
)
from sec_agent.official_source_attempt_program import (  # noqa: E402
    OfficialSourceAttemptError,
    SourceResponse,
)
from sec_agent.s1_dell_enriched_source_successor import (  # noqa: E402
    execute_dell_enriched_source_successor,
    load_dell_enriched_source_policy,
)


POLICY_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s1_dell_enriched_source_successor_policy_v1_0.json"
)


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
            text = (
                "Dell reported 24.4 billion of AI orders and 51.3 billion of backlog "
                "while demand continued to exceed supply. Management discussed memory "
                "uncertainty, said it had proactively secured supply, and maintained "
                "pricing and margin discipline. AI server profitability was measured "
                "against a mid-single-digit operating income rate target."
            )
        else:
            text = (
                "Micron expects supply-demand conditions to remain tight beyond 2027 "
                "across DRAM and NAND. Its advanced packaging facility should add HBM "
                "packaging capacity in the first half of 2027."
            )
        return SourceResponse(
            status_code=200,
            final_url=url,
            headers={"content-type": "text/html; charset=utf-8"},
            body=f"<html><body>{text}</body></html>".encode(),
        )


class FixturePrimaryAdapter(AlphaVantageDailyAdapter):
    live_network = False

    def __init__(self, *, mode: str = "success") -> None:
        self.mode = mode

    def fetch(
        self,
        *,
        request: MarketPointRequest,
        credential: str | None,
        timeout_seconds: int,
        byte_ceiling: int,
    ) -> MarketDataRawResponse:
        del timeout_seconds, byte_ceiling
        if self.mode == "secret_echo":
            payload: dict[str, Any] = {"Information": str(credential)}
        else:
            selected_date = request.exact_date if self.mode == "success" else "2026-08-05"
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
            body=json.dumps(
                [{"日期": request.exact_date, "收盘": 142.37}],
                ensure_ascii=False,
            ).encode(),
        )


def _execute(
    *,
    policy: Mapping[str, Any],
    runtime: Path,
    implementation_commit: str,
    fail_dell: bool = False,
    market_mode: str = "success",
) -> dict[str, Any]:
    return execute_dell_enriched_source_successor(
        policy=policy,
        repo_root=ROOT,
        runtime_root=runtime,
        official_transport=FixtureOfficialTransport(fail_dell=fail_dell),
        primary_market_adapter=FixturePrimaryAdapter(mode=market_mode),
        primary_market_credential="fixture-secret-never-capture",
        shadow_market_adapter=FixtureShadowAdapter(),
        observed_at="2026-08-10T10:00:00Z",
        execution_commit=implementation_commit,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--implementation-commit", required=True)
    args = parser.parse_args()
    policy = load_dell_enriched_source_policy(POLICY_PATH, repo_root=ROOT)
    all_true = _execute(
        policy=policy,
        runtime=args.runtime_root / "all_true",
        implementation_commit=args.implementation_commit,
    )
    valuation_missing = _execute(
        policy=policy,
        runtime=args.runtime_root / "valuation_missing",
        implementation_commit=args.implementation_commit,
        market_mode="missing_date",
    )
    core_missing = _execute(
        policy=policy,
        runtime=args.runtime_root / "core_missing",
        implementation_commit=args.implementation_commit,
        fail_dell=True,
    )
    secret_runtime = args.runtime_root / "secret_echo"
    secret_echo = _execute(
        policy=policy,
        runtime=secret_runtime,
        implementation_commit=args.implementation_commit,
        market_mode="secret_echo",
    )
    serialized = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (secret_runtime / "objects").rglob("*.json")
    )
    secret_rejected = (
        "fixture-secret-never-capture" not in serialized
        and any(
            row.get("failure_code") == "market_data_response_contains_credential"
            for row in secret_echo["route_results"]
        )
    )
    output = {
        "status": "pass",
        "result_digest": all_true["result_digest"],
        "successor_pack_payload_digest": all_true["successor_pack_payload_digest"],
        "observed_counts": all_true["observed_counts"],
        "stage_acceptance": all_true["stage_acceptance"],
        "gate_mutations": {
            "core_true_valuation_false": (
                valuation_missing["gate_status"]["core_research_ready"] is True
                and valuation_missing["gate_status"]["valuation_input_ready"] is False
                and valuation_missing["gate_status"]["successor_pack_ready_for_model_input"] is True
            ),
            "core_false_valuation_true": (
                core_missing["gate_status"]["core_research_ready"] is False
                and core_missing["gate_status"]["valuation_input_ready"] is True
                and core_missing["gate_status"]["successor_pack_ready_for_model_input"] is False
            ),
            "both_true": all(
                all_true["gate_status"][key] is True
                for key in (
                    "core_research_ready",
                    "supplier_context_ready",
                    "valuation_input_ready",
                )
            ),
        },
        "credential_capture_mutation_rejected": secret_rejected,
        "real_network_calls": 0,
        "model_calls": 0,
    }
    if not all(output["gate_mutations"].values()) or not secret_rejected:
        raise RuntimeError("dell_enriched_worker_mutation_failed")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
