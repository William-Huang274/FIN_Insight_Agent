"""Clean-process M2-A1 executor.

This executable is entered only through the non-runtime supervisor.  It keeps
the receipt lifecycle and staged-tree verification ahead of runtime import,
then installs the canary before importing the compiler/shadow audit harness.
It never reads the reviewer oracle or reviewer expectations.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
PACKAGE_PATH = ROOT / "data/manifests/point01_m2_a1_execution_ready_audit_package_manifest_v2_3.json"
sys.path.insert(0, str(ROOT / "src"))


def _json(path: Path) -> Mapping[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, Mapping):
        raise ValueError(f"m2_a1_json_mapping_required:{path}")
    return loaded


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Consume one exact M2-A1 receipt inside a clean Python child.")
    parser.add_argument("--execute-admitted", action="store_true")
    parser.add_argument("--admission", type=Path)
    parser.add_argument("--receipt-id")
    parser.add_argument("--scenario-id")
    args = parser.parse_args(argv)
    if not args.execute_admitted:
        print(json.dumps({"status": "m2_a1_actual_probes_not_authorized", "compiler_or_shadow_fixture_runs": 0, "model_calls": 0, "network_requests": 0, "store_writes": 0}, ensure_ascii=False))
        return 1
    if args.admission is None or not args.receipt_id or not args.scenario_id:
        print(json.dumps({"status": "m2_a1_exact_admitted_cli_arguments_required"}, ensure_ascii=False))
        return 2

    # Authority-only lifecycle imports no compiler, shadow, canary or oracle.
    from sec_agent.canonical_runtime.m2_a1_execution_receipt import (  # noqa: PLC0415
        M2A1ExecutionPreflightError,
        M2A1ExternalPackageAdmission,
        M2A1ReceiptAuthorityError,
        M2A1ReceiptLedger,
        preflight_exact_execution,
    )

    try:
        package = _json(PACKAGE_PATH)
        admission = M2A1ExternalPackageAdmission.model_validate(_json(args.admission))
        preflight = preflight_exact_execution(
            package,
            admission,
            repository_root=ROOT,
            receipt_id=args.receipt_id,
            scenario_id=args.scenario_id,
        )
        ledger = M2A1ReceiptLedger.open_existing(
            preflight.ledger_path,
            approved_authority_root=preflight.authority_root,
        )
        grant = ledger.consume_before_run(
            preflight.receipt_id,
            admission=admission,
            package_ref=str(package["package_ref"]),
            executable_package_digest=str(package["package_digest"]),
            scope=str(package["scope"]),
            authority_boundary=str(package["authority_boundary"]),
            preflight_digest=preflight.preflight_digest,
            run_root=preflight.run_root,
            execution_staging_namespace_id=admission.execution_staging_namespace_id,
            scenario_id=preflight.scenario_id,
        )
    except (M2A1ExecutionPreflightError, M2A1ReceiptAuthorityError, ValueError) as exc:
        print(json.dumps({"status": str(exc), "compiler_or_shadow_fixture_runs": 0, "receipt_consumed": False, "runtime_or_output_materialized": False, "store_writes": 0}, ensure_ascii=False))
        return 2

    try:
        # This must happen before runtime materialization and before importing
        # any M2 business module.  A drift leaves the receipt spent.
        preflight.reverify_current_execution_tree()
        consumed = preflight.verify_consumption_grant_before_runtime(grant, ledger=ledger)
        preflight.materialize_runtime_after_consumption(grant, ledger=ledger)

        # The canary is installed before the harness/compiler/shadow import.
        from sec_agent.canonical_runtime.m2_a1_audit_canary import M2A1AuditCanary  # noqa: PLC0415

        canary = M2A1AuditCanary(
            allowed_temporary_roots=(preflight.runtime_root,),
            fixed_paths=(preflight.fixed_store_path,),
            oracle_paths=(preflight.run_root / ".reviewer_oracle_forbidden.json",),
        )
        canary.observe_transport_module_presence()
        with canary.instrument():
            from sec_agent.canonical_runtime.m2_a1_audit_harness import M2A1ActualRunner  # noqa: PLC0415

            runner = M2A1ActualRunner(
                corpus_case=preflight.corpus_case,
                compiler_policy_ref="point01-m2-1-compiler-policy-v1",
                pack_registry_policy_ref="point01-m2-3-pack-registry-policy-v1",
                temporary_root=preflight.runtime_root,
                canary=canary,
            )
            result = runner.execute_consumed_scenario(
                scenario=preflight.runtime_scenario,
                package=package,
                admission=admission,
                receipt_ledger=ledger,
                consumed_receipt=consumed,
                execution_preflight=preflight,
            )
        preflight.output_path.write_text(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except Exception as exc:  # consumed remains spent; reconcile outcome without replay.
        try:
            ledger.recover_consumed_without_terminal(preflight.receipt_id)
        except M2A1ReceiptAuthorityError:
            pass
        print(json.dumps({"status": "m2_a1_post_consume_outcome_unknown", "typed_error": type(exc).__name__, "receipt_consumed": True, "retry_permitted": False}, ensure_ascii=False))
        return 1
    print(json.dumps({"status": result.actual_status, "scenario_id": result.scenario_id, "actual_result_digest": result.actual_result_digest}, ensure_ascii=False))
    return 0 if result.actual_status in {"succeeded", "typed_stop"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
