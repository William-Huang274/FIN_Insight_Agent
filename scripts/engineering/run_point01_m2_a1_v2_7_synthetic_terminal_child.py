"""Isolated no-network child used only by the v2.7 authority-chain fixture."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write one synthetic immutable M2-A1 result; no runtime services.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--package-digest", required=True)
    parser.add_argument("--admission-digest", required=True)
    parser.add_argument("--receipt-digest", required=True)
    parser.add_argument("--scenario-id", required=True)
    args = parser.parse_args(argv)
    from sec_agent.canonical_runtime.m2_a1_audit_result import M2A1ArtifactReplayProjection, M2A1ImmutableActualResult, M2A1PackLineageProjection

    result = M2A1ImmutableActualResult.terminalize(
        execution_scope="M2_A1_v2_7_synthetic_temporary_authority_chain_only",
        scenario_id=args.scenario_id,
        case_id="m2-a1-synthetic-case",
        executable_package_digest=args.package_digest,
        admission_digest=args.admission_digest,
        consumed_receipt_digest=args.receipt_digest,
        actual_status="succeeded",
        pack_lineage=M2A1PackLineageProjection(selection_digest="a" * 64, resolution_digest="b" * 64, registry_snapshot_digest="c" * 64, selected_pack_version_ids=("synthetic-pack:v1",)),
        artifact_replay=M2A1ArtifactReplayProjection(envelope_digest="d" * 64, replay_digest="e" * 64, artifact_version_id="synthetic-v1"),
        canary_snapshot={"counts": {"network_request_success_count": 0, "store_write_open_count": 0, "model_constructor_success_count": 0, "tool_transport_success_count": 0}, "events": []},
    )
    args.output.write_text(json.dumps(result.model_dump(mode="json"), sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
