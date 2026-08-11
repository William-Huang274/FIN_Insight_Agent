from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.official_source_attempt_program import (  # noqa: E402
    OfficialSourceAttemptError,
    SourceResponse,
)
from sec_agent.s1_dell_official_source_recovery_successor import (  # noqa: E402
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
        if self.fail_dell and "delltechnologies.com" in url:
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


def _execute(
    *,
    policy: Mapping[str, Any],
    runtime: Path,
    implementation_commit: str,
    **kwargs: Any,
) -> dict[str, Any]:
    return execute_dell_official_source_recovery_successor(
        policy=policy,
        repo_root=ROOT,
        runtime_root=runtime,
        transport=FixtureManagedReaderTransport(**kwargs),
        observed_at="2026-08-10T18:00:00Z",
        execution_commit=implementation_commit,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--implementation-commit", required=True)
    args = parser.parse_args()
    policy = load_dell_official_source_recovery_policy(
        POLICY_PATH, repo_root=ROOT
    )
    success = _execute(
        policy=policy,
        runtime=args.runtime_root / "success",
        implementation_commit=args.implementation_commit,
    )
    dell_timeout = _execute(
        policy=policy,
        runtime=args.runtime_root / "dell_timeout",
        implementation_commit=args.implementation_commit,
        fail_dell=True,
    )
    micron_gap = _execute(
        policy=policy,
        runtime=args.runtime_root / "micron_gap",
        implementation_commit=args.implementation_commit,
        missing_micron_anchor=True,
    )
    cross_origin = _execute(
        policy=policy,
        runtime=args.runtime_root / "cross_origin",
        implementation_commit=args.implementation_commit,
        final_url_override="https://example.com/cross-case-pollution",
    )
    captures = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (args.runtime_root / "success" / "objects").rglob("*.json")
    ]
    response_captures = [
        row for row in captures if row.get("capture_kind") == "source_response"
    ]
    metadata_preserved = len(response_captures) == 2 and all(
        row.get("transport_metadata", {}).get("retrieval_intermediary")
        == "jina_reader"
        and row.get("transport_metadata", {}).get(
            "origin_direct_response_bytes_preserved"
        )
        is False
        and row.get("transport_metadata", {}).get(
            "intermediary_raw_response_preserved"
        )
        is True
        for row in response_captures
    )
    mutations = {
        "dell_timeout_closes_core_but_preserves_supplier_and_valuation": (
            dell_timeout["gate_status"]["core_research_ready"] is False
            and dell_timeout["gate_status"]["supplier_context_ready"] is True
            and dell_timeout["gate_status"]["valuation_input_ready"] is True
        ),
        "micron_anchor_gap_does_not_false_close_core": (
            micron_gap["gate_status"]["core_research_ready"] is True
            and micron_gap["gate_status"]["supplier_context_ready"] is False
        ),
        "cross_origin_pollution_rejected": (
            cross_origin["gate_status"]["core_research_ready"] is False
            and all(
                row["status"] == "rejected_final_url"
                for row in cross_origin["route_results"]
            )
        ),
        "managed_reader_metadata_preserved": metadata_preserved,
        "successful_tsmc_and_alpha_reused_without_network": (
            success["stage_acceptance"][
                "successful_tsmc_and_alpha_inputs_reused_without_network"
            ]
            is True
            and success["observed_counts"]["reused_numeric_facts"] == 1
        ),
    }
    if not all(mutations.values()):
        raise RuntimeError("dell_official_recovery_worker_mutation_failed")
    output = {
        "status": "pass",
        "result_digest": success["result_digest"],
        "successor_pack_payload_digest": success["successor_pack_payload_digest"],
        "observed_counts": {
            **success["observed_counts"],
            "network_calls": 0,
            "model_calls": 0,
        },
        "gate_status": success["gate_status"],
        "stage_acceptance": success["stage_acceptance"],
        "mutations": mutations,
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
