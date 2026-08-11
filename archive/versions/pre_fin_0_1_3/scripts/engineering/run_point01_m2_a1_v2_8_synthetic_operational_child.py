"""Local child for the v2.8 non-human operational-proof integration fixture.

It never accepts a human approval, transport setting, provider, or source path.
Its output is deterministic synthetic test data only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="M2-A1 v2.8 synthetic nonhuman operational-proof child.")
    parser.add_argument("--synthetic-nonhuman-fixture", action="store_true", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--package-digest", required=True)
    parser.add_argument("--admission-digest", required=True)
    parser.add_argument("--receipt-digest", required=True)
    parser.add_argument("--scenario-id", required=True)
    parser.add_argument("--mode", choices=("happy", "corrupt", "reviewer_fail", "exit_after_consume"), required=True)
    args = parser.parse_args(argv)
    if args.mode == "exit_after_consume":
        return 73
    if args.mode == "corrupt":
        args.output.write_text("{\"corrupted\":true}\n", encoding="utf-8")
        return 0
    from sec_agent.canonical_runtime.m2_a1_audit_result import (
        M2A1ActualCellProjection,
        M2A1ArtifactReplayProjection,
        M2A1ImmutableActualResult,
        M2A1PackLineageProjection,
        M2A1SemanticLossProjection,
    )

    asserted_claims = ("synthetic_forbidden_claim",) if args.mode == "reviewer_fail" else ()
    actual = M2A1ImmutableActualResult.terminalize(
        execution_scope="M2_A1_v2_8_synthetic_nonhuman_fixture_only",
        scenario_id=args.scenario_id,
        case_id="m2-a1-v2-8-synthetic-case",
        executable_package_digest=args.package_digest,
        admission_digest=args.admission_digest,
        consumed_receipt_digest=args.receipt_digest,
        actual_status="succeeded",
        pack_lineage=M2A1PackLineageProjection(
            selection_digest="a" * 64,
            resolution_digest="b" * 64,
            registry_snapshot_digest="c" * 64,
            selected_pack_version_ids=("synthetic-pack:v1",),
        ),
        cells=(M2A1ActualCellProjection(cell_key="synthetic.revenue", owner_role="EvidenceOperator", evidence_roles=("issuer_financial",), forbidden_substitutions=(), acceptance_roles=("EvidenceOperator",)),),
        semantic_loss=(M2A1SemanticLossProjection(legacy_required_item_id="legacy-synthetic", action="mapped", target_cell_keys=("synthetic.revenue",), information_loss_tags=("synthetic",)),),
        artifact_replay=M2A1ArtifactReplayProjection(envelope_digest="d" * 64, replay_digest="e" * 64, artifact_version_id="synthetic-v2-8"),
        asserted_claims=asserted_claims,
        canary_snapshot={"counts": {"network_request_success_count": 0, "store_write_open_count": 0, "model_constructor_success_count": 0, "tool_transport_success_count": 0}, "events": ["synthetic_nonhuman_fixture"]},
    )
    args.output.write_text(json.dumps(actual.model_dump(mode="json"), sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
