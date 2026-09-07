from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

import scripts.research.run_s3_current_dynamic_multi_agent as legacy


ROOT = Path(__file__).resolve().parents[2]
_LEGACY_MUTATION_CHECKS = legacy._mutation_checks


def premature_stop_compiles_to_no_progress(
    role_programs: Mapping[str, Any],
) -> bool:
    """Prove the current stop compiler preserves a rejected proposal receipt.

    The immutable predecessor runner expected an exception here.  The current
    compiler instead retains the model proposal and locally converts an
    under-covered ``stop_sufficient`` request into ``stop_no_progress``.  This
    successor checks that newer contract without modifying the historical
    runner that old authority manifests bind by SHA-256.
    """

    demand = legacy.role_program_by_agent(role_programs)[
        "AGENT::DEMAND_QUALITY"
    ]
    partial_request_id = str(demand["requests"][0]["request_id"])
    reflection = legacy.validate_reflection_payload(
        legacy._fake_reflection_payload(
            agent_id=demand["agent_id"],
            round_index=1,
            feedback_refs=[],
            next_request_ids=[],
            accepted_evidence_refs=[],
            decision="stop_sufficient",
        ),
        policy=demand["loop_policy"],
        request_catalog=demand["request_catalog"],
        feedback_receipts=[],
        accepted_evidence_refs=[],
        executed_request_ids=[partial_request_id],
        round_index=1,
    )
    artifacts = legacy.compile_reflection_artifacts(
        policy=demand["loop_policy"],
        reflection=reflection,
        session_id="SESSION::MUTATION-SUCCESSOR",
        agent_id=demand["agent_id"],
        base_plan={"executed_request_ids": []},
        base_graph_digest="a" * 64,
        executed_request_ids=[partial_request_id],
        open_gap_refs=["GAP::MUTATION"],
        model_calls_used=0,
    )
    receipt = artifacts["stop_compilation_receipt"]
    return (
        reflection["proposed_stop_decision"] == "stop_sufficient"
        and artifacts["stop_decision"]["decision"] == "stop_no_progress"
        and receipt["proposed_stop_decision"] == "stop_sufficient"
        and receipt["effective_stop_decision"] == "stop_no_progress"
        and receipt["model_research_judgment_changed"] is False
    )


def successor_mutation_checks(
    *,
    role_programs: Mapping[str, Any],
    role_bundles: Mapping[str, Any],
    lead_bundle: Mapping[str, Any],
) -> dict[str, bool]:
    checks = _LEGACY_MUTATION_CHECKS(
        role_programs=role_programs,
        role_bundles=role_bundles,
        lead_bundle=lead_bundle,
    )
    checks.pop("premature_stop_fails_closed", None)
    checks["premature_stop_compiles_to_no_progress"] = (
        premature_stop_compiles_to_no_progress(role_programs)
    )
    return checks


def run_zero_call(
    *, attempt_id: str, private_output: Path, public_output: Path
) -> dict[str, Any]:
    original = legacy._mutation_checks
    legacy._mutation_checks = successor_mutation_checks
    try:
        return legacy.run_zero_call(
            attempt_id=attempt_id,
            private_output=private_output,
            public_output=public_output,
        )
    finally:
        legacy._mutation_checks = original


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--private-output", required=True)
    parser.add_argument("--public-output", required=True)
    args = parser.parse_args()
    result = run_zero_call(
        attempt_id=args.attempt_id,
        private_output=Path(args.private_output).resolve(),
        public_output=Path(args.public_output).resolve(),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
