from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.official_source_attempt_program import SourceResponse  # noqa: E402
from sec_agent.s1_dell_targeted_source_supplement import (  # noqa: E402
    execute_dell_targeted_source_supplement,
    load_dell_targeted_source_policy,
)


POLICY_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s1_dell_targeted_source_supplement_policy_v1_0.json"
)


class FixtureTransport:
    live_network = False

    def __init__(self, responses: Mapping[str, SourceResponse]) -> None:
        self.responses = dict(responses)
        self.calls: list[str] = []

    def fetch(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        allowed_hosts: set[str],
        timeout_seconds: int,
        byte_ceiling: int,
    ) -> SourceResponse:
        del headers, timeout_seconds
        response = self.responses[url]
        if response.final_url.split("/", 3)[2] not in allowed_hosts:
            raise RuntimeError("fixture_host_not_allowlisted")
        if len(response.body) > byte_ceiling:
            raise RuntimeError("fixture_body_exceeds_ceiling")
        self.calls.append(url)
        return response


def _text(url: str, value: str) -> SourceResponse:
    return SourceResponse(
        status_code=200,
        final_url=url,
        headers={"content-type": "text/html"},
        body=value.encode("utf-8"),
    )


def _responses(policy: Mapping[str, Any]) -> dict[str, SourceResponse]:
    routes = {row["route_id"]: row for row in policy["external_routes"]}
    dell = (
        "Dell booked $24.4 billion in AI orders, recognized $16.1 billion in AI "
        "server revenue and ended with $51.3 billion of backlog. Demand continues "
        "to exceed supply, with memory the primary constraint, across more than "
        "5,000 customers. Memory uncertainty is leading customers to proactively "
        "secure infrastructure across AI and traditional workloads over longer "
        "periods, while Dell maintains pricing and margin discipline. AI server "
        "profitability remains in line with our mid-single-digit operating income "
        "rate target."
    )
    micron = (
        "DRAM and NAND supply-demand conditions remain tight beyond 2027. Our "
        "Singapore advanced packaging facility will contribute meaningfully to HBM "
        "packaging capacity beginning in the first half of 2027."
    )
    tsmc = (
        "CoWoS remains our main supply for advanced AI packaging, and we are "
        "working hard to provide customers enough capacity."
    )
    market = {
        "data": {
            "tradesTable": {
                "rows": [
                    {
                        "date": "08/06/2026",
                        "close": "$437.65",
                        "volume": "6,094,432",
                        "open": "$450.55",
                        "high": "$455.8699",
                        "low": "$426.00",
                    }
                ]
            }
        }
    }
    market_url = routes["nasdaq_dell_historical_2026_08_06"]["url"]
    return {
        routes["dell_q1_fy27_earnings_transcript"]["url"]: _text(
            routes["dell_q1_fy27_earnings_transcript"]["url"], dell
        ),
        routes["micron_q3_fy26_earnings_slides"]["url"]: _text(
            routes["micron_q3_fy26_earnings_slides"]["url"], micron
        ),
        routes["tsmc_q1_2026_earnings_transcript"]["url"]: _text(
            routes["tsmc_q1_2026_earnings_transcript"]["url"], tsmc
        ),
        market_url: SourceResponse(
            status_code=200,
            final_url=market_url,
            headers={"content-type": "application/json"},
            body=json.dumps(market).encode("utf-8"),
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    policy = load_dell_targeted_source_policy(POLICY_PATH, repo_root=ROOT)
    transport = FixtureTransport(_responses(policy))
    result = execute_dell_targeted_source_supplement(
        policy=policy,
        repo_root=ROOT,
        runtime_root=args.runtime_root,
        transport=transport,
        observed_at="2026-08-10T10:00:00Z",
        execution_commit="clean-zero-call-fixture",
    )
    if result["status"] != "terminal_succeeded_targeted_source_successor_pack_ready":
        raise RuntimeError("clean_worker_successor_pack_not_ready")
    output = {
        "status": "pass",
        "result_digest": result["result_digest"],
        "dell_pack_payload_digest": result["pack_payload_digests"]["DELL"],
        "observed_counts": result["observed_counts"],
        "stage_acceptance": result["stage_acceptance"],
        "transport_invocations": len(transport.calls),
        "real_network_calls": 0,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
