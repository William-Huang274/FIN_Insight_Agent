"""Clean child for the single v2.10 lifecycle kernel.

The parent routes both the production leaf and the explicitly non-human
fixture leaf here.  Neither leaf consumes a receipt: consumption belongs to
the package-bound lifecycle kernel before this child is spawned.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PACKAGE_PATH = ROOT / "data/manifests/point01_m2_a1_execution_ready_audit_package_manifest_v2_10.json"
sys.path.insert(0, str(ROOT / "src"))


def _write_synthetic_actual(args: argparse.Namespace) -> int:
    if args.mode == "exit_after_consume":
        return 73
    if args.mode == "corrupt":
        args.output.write_text('{"corrupted":true}\n', encoding="utf-8")
        return 0
    from sec_agent.canonical_runtime.m2_a1_audit_result import (
        M2A1ActualCellProjection,
        M2A1ArtifactReplayProjection,
        M2A1ImmutableActualResult,
        M2A1PackLineageProjection,
        M2A1SemanticLossProjection,
    )

    actual = M2A1ImmutableActualResult.terminalize(
        execution_scope="M2_A1_v2_10_synthetic_nonhuman_fixture_only",
        scenario_id=args.scenario_id,
        case_id="m2-a1-v2-8-synthetic-case",
        executable_package_digest=args.package_digest,
        admission_digest=args.admission_digest,
        consumed_receipt_digest=args.receipt_digest,
        actual_status="succeeded",
        pack_lineage=M2A1PackLineageProjection(selection_digest="a" * 64, resolution_digest="b" * 64, registry_snapshot_digest="c" * 64, selected_pack_version_ids=("synthetic-pack:v1",)),
        cells=(M2A1ActualCellProjection(cell_key="synthetic.revenue", owner_role="EvidenceOperator", evidence_roles=("issuer_financial",), forbidden_substitutions=(), acceptance_roles=("EvidenceOperator",)),),
        semantic_loss=(M2A1SemanticLossProjection(legacy_required_item_id="legacy-synthetic", action="mapped", target_cell_keys=("synthetic.revenue",), information_loss_tags=("synthetic",)),),
        artifact_replay=M2A1ArtifactReplayProjection(envelope_digest="d" * 64, replay_digest="e" * 64, artifact_version_id="synthetic-v2-10"),
        asserted_claims=("synthetic_forbidden_claim",) if args.mode == "reviewer_fail" else (),
        canary_snapshot={"counts": {"network_request_success_count": 0, "store_write_open_count": 0, "model_constructor_success_count": 0, "tool_transport_success_count": 0}, "events": ["synthetic_nonhuman_fixture_v2_10"]},
    )
    args.output.write_text(json.dumps(actual.model_dump(mode="json"), sort_keys=True), encoding="utf-8")
    return 0


def _write_production_actual(args: argparse.Namespace) -> int:
    """The eventual approved leaf: no lifecycle mutation is allowed here."""

    from sec_agent.canonical_runtime.m2_a1_audit_canary import M2A1AuditCanary
    from sec_agent.canonical_runtime.m2_a1_audit_harness import M2A1ActualRunner
    from sec_agent.canonical_runtime.m2_a1_execution_receipt import (
        M2A1ExecutionReceipt,
        M2A1ExternalPackageAdmission,
        M2A1ReceiptLedger,
        preflight_exact_execution,
    )

    package = json.loads(PACKAGE_PATH.read_text(encoding="utf-8"))
    admission = M2A1ExternalPackageAdmission.model_validate(json.loads(args.admission.read_text(encoding="utf-8")))
    grant = json.loads(args.grant.read_text(encoding="utf-8"))
    preflight = preflight_exact_execution(package, admission, repository_root=ROOT, receipt_id=args.receipt_id, scenario_id=args.scenario_id, human_approval_digest=args.human_approval_digest)
    ledger = M2A1ReceiptLedger.open_existing(preflight.ledger_path, approved_authority_root=preflight.authority_root)
    from sec_agent.canonical_runtime.m2_a1_execution_receipt import M2A1ConsumptionGrant

    consumed = preflight.verify_consumption_grant_before_runtime(M2A1ConsumptionGrant.model_validate(grant), ledger=ledger)
    canary = M2A1AuditCanary(allowed_temporary_roots=(preflight.runtime_root,), fixed_paths=(preflight.fixed_store_path,), oracle_paths=(preflight.run_root / ".reviewer_oracle_forbidden.json",))
    canary.observe_transport_module_presence()
    with canary.instrument():
        runner = M2A1ActualRunner(corpus_case=preflight.corpus_case, compiler_policy_ref="point01-m2-1-compiler-policy-v1", pack_registry_policy_ref="point01-m2-3-pack-registry-policy-v1", temporary_root=preflight.runtime_root, canary=canary)
        actual = runner.execute_consumed_scenario(scenario=preflight.runtime_scenario, package=package, admission=admission, receipt_ledger=ledger, consumed_receipt=consumed, execution_preflight=preflight)
    args.output.write_text(json.dumps(actual.model_dump(mode="json"), ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return 0


def _kernel_leaf_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="M2-A1 v2.10 lifecycle-kernel leaf.")
    parser.add_argument("--execute-kernel-leaf", action="store_true", required=True)
    parser.add_argument("--leaf-kind", choices=("synthetic_fixture", "production_actual"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--package-digest")
    parser.add_argument("--admission-digest")
    parser.add_argument("--receipt-digest")
    parser.add_argument("--admission", type=Path)
    parser.add_argument("--grant", type=Path)
    parser.add_argument("--receipt-id")
    parser.add_argument("--scenario-id", required=True)
    parser.add_argument("--human-approval-digest")
    parser.add_argument("--mode", choices=("happy", "corrupt", "reviewer_fail", "exit_after_consume"))
    args = parser.parse_args(argv)
    if args.leaf_kind == "synthetic_fixture":
        if not all((args.package_digest, args.admission_digest, args.receipt_digest, args.mode)):
            return 2
        return _write_synthetic_actual(args)
    if args.mode is not None or not all((args.admission, args.grant, args.receipt_id, args.human_approval_digest)):
        return 2
    return _write_production_actual(args)


def main(argv: list[str] | None = None) -> int:
    values = list(sys.argv[1:] if argv is None else argv)
    if values == ["--help"]:
        argparse.ArgumentParser(description="M2-A1 v2.10 lifecycle-kernel clean child.").print_help()
        return 0
    if values and values[0] == "--execute-kernel-leaf":
        return _kernel_leaf_main(values)
    # Historical explicit mode remains default-deny and is deliberately not a
    # second lifecycle implementation.
    print(json.dumps({"status": "m2_a1_v2_10_kernel_leaf_required", "receipt_consumed": False}, sort_keys=True))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
