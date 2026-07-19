"""Frozen helpers for a package-bound M2-A1 JIT execution entry.

The helpers are inert unless an external human-window approval has already
been validated by the package-bound orchestrator.  They never resolve ambient
stores or a package path from environment variables.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping


def load_mapping(path: Path) -> Mapping[str, Any]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError("m2_a1_jit_json_input_unreadable") from exc
    except json.JSONDecodeError as exc:
        raise ValueError("m2_a1_jit_json_input_invalid") from exc
    if not isinstance(loaded, Mapping):
        raise ValueError("m2_a1_jit_json_mapping_required")
    return loaded


def registrar_main(*, root: Path, package_path: Path, argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Register one exact frozen-package receipt without runtime materialization.")
    parser.add_argument("--register-exact-receipt", action="store_true")
    parser.add_argument("--admission", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--scenario-id")
    parser.add_argument("--human-approval-digest")
    args = parser.parse_args(argv)
    if not args.register_exact_receipt:
        print(json.dumps({"status": "m2_a1_receipt_registration_not_requested", "runtime_or_output_materialized": False}, sort_keys=True))
        return 1
    if args.admission is None or args.receipt is None or not args.scenario_id:
        print(json.dumps({"status": "m2_a1_exact_receipt_registration_arguments_required"}, sort_keys=True))
        return 2
    from .m2_a1_execution_receipt import (  # local to keep import boundary narrow
        M2A1ExecutionPreflightError,
        M2A1ExecutionReceipt,
        M2A1ExternalPackageAdmission,
        M2A1ReceiptAuthorityError,
        M2A1ReceiptLedger,
        preflight_exact_execution,
    )
    try:
        package = load_mapping(package_path)
        admission = M2A1ExternalPackageAdmission.model_validate(load_mapping(args.admission))
        receipt = M2A1ExecutionReceipt.model_validate(load_mapping(args.receipt))
        preflight = preflight_exact_execution(package, admission, repository_root=root, receipt_id=receipt.receipt_id, scenario_id=args.scenario_id, human_approval_digest=args.human_approval_digest)
        if receipt.scenario_id != preflight.scenario_id:
            raise M2A1ReceiptAuthorityError("receipt_scenario_id_mismatch")
        preflight.materialize_authority_for_registration()
        ledger = M2A1ReceiptLedger.create_for_registration(preflight.ledger_path, approved_authority_root=preflight.authority_root)
        registered = ledger.register(
            receipt,
            admission=admission,
            package_ref=str(package["package_ref"]),
            executable_package_digest=str(package["package_digest"]),
            scope=str(package["scope"]),
            authority_boundary=str(package["authority_boundary"]),
            execution_staging_namespace_id=admission.execution_staging_namespace_id,
            scenario_id=preflight.scenario_id,
            expected_admission_schema_version=preflight.package_contract.admission_schema_version,
            expected_receipt_schema_version=preflight.package_contract.receipt_schema_version,
            expected_human_approval_digest=preflight.human_approval_digest,
        )
        state = ledger.state(receipt.receipt_id)
    except (M2A1ExecutionPreflightError, M2A1ReceiptAuthorityError, ValueError) as exc:
        print(json.dumps({"status": str(exc), "runtime_or_output_materialized": False, "m2_runtime_imported": False}, sort_keys=True))
        return 2
    print(json.dumps({"status": registered["registration_status"], "receipt_id": receipt.receipt_id, "receipt_digest": registered["receipt_digest"], "state": state["state"] if state else None, "runtime_or_output_materialized": False, "m2_runtime_imported": False}, sort_keys=True))
    return 0


def clean_child_main(*, root: Path, package_path: Path, argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Consume one exact frozen-package receipt inside a clean Python child.")
    parser.add_argument("--transport-isolation-probe", action="store_true")
    parser.add_argument("--execute-admitted", action="store_true")
    parser.add_argument("--admission", type=Path)
    parser.add_argument("--receipt-id")
    parser.add_argument("--scenario-id")
    parser.add_argument("--human-approval-digest")
    args = parser.parse_args(argv)
    if args.transport_isolation_probe:
        from .m2_a1_audit_canary import M2A1AuditCanary
        canary = M2A1AuditCanary(allowed_temporary_roots=(root / ".frozen_jit_probe_never_materialized",), fixed_paths=(root / ".runtime_control" / "forbidden.sqlite",))
        before = canary.observe_transport_module_presence()
        with canary.instrument():
            from .m2_a1_audit_harness import M2A1ActualRunner  # noqa: F401
        print(json.dumps({"status": "frozen_jit_clean_child_canary_before_harness_import_pass", "transport_aliases_before_harness": before, "counts": canary.snapshot()["counts"], "network_success": 0}, sort_keys=True))
        return 0
    if not args.execute_admitted:
        print(json.dumps({"status": "m2_a1_actual_probes_not_authorized", "compiler_or_shadow_fixture_runs": 0, "network_requests": 0, "store_writes": 0}, sort_keys=True))
        return 1
    if args.admission is None or not args.receipt_id or not args.scenario_id:
        print(json.dumps({"status": "m2_a1_exact_admitted_cli_arguments_required"}, sort_keys=True))
        return 2
    from .m2_a1_execution_receipt import M2A1ExecutionPreflightError, M2A1ExternalPackageAdmission, M2A1ReceiptAuthorityError, M2A1ReceiptLedger, preflight_exact_execution
    try:
        package = load_mapping(package_path)
        admission = M2A1ExternalPackageAdmission.model_validate(load_mapping(args.admission))
        preflight = preflight_exact_execution(package, admission, repository_root=root, receipt_id=args.receipt_id, scenario_id=args.scenario_id, human_approval_digest=args.human_approval_digest)
        ledger = M2A1ReceiptLedger.open_existing(preflight.ledger_path, approved_authority_root=preflight.authority_root)
        grant = ledger.consume_before_run(
            preflight.receipt_id, admission=admission, package_ref=str(package["package_ref"]), executable_package_digest=str(package["package_digest"]), scope=str(package["scope"]), authority_boundary=str(package["authority_boundary"]), preflight_digest=preflight.preflight_digest, run_root=preflight.run_root, execution_staging_namespace_id=admission.execution_staging_namespace_id, scenario_id=preflight.scenario_id, expected_admission_schema_version=preflight.package_contract.admission_schema_version, expected_receipt_schema_version=preflight.package_contract.receipt_schema_version, expected_human_approval_digest=preflight.human_approval_digest,
        )
    except (M2A1ExecutionPreflightError, M2A1ReceiptAuthorityError, ValueError) as exc:
        print(json.dumps({"status": str(exc), "compiler_or_shadow_fixture_runs": 0, "receipt_consumed": False, "runtime_or_output_materialized": False, "store_writes": 0}, sort_keys=True))
        return 2
    try:
        preflight.reverify_current_execution_tree()
        consumed = preflight.verify_consumption_grant_before_runtime(grant, ledger=ledger)
        preflight.materialize_runtime_after_consumption(grant, ledger=ledger)
        from .m2_a1_audit_canary import M2A1AuditCanary
        canary = M2A1AuditCanary(allowed_temporary_roots=(preflight.runtime_root,), fixed_paths=(preflight.fixed_store_path,), oracle_paths=(preflight.run_root / ".reviewer_oracle_forbidden.json",))
        canary.observe_transport_module_presence()
        with canary.instrument():
            from .m2_a1_audit_harness import M2A1ActualRunner
            runner = M2A1ActualRunner(corpus_case=preflight.corpus_case, compiler_policy_ref="point01-m2-1-compiler-policy-v1", pack_registry_policy_ref="point01-m2-3-pack-registry-policy-v1", temporary_root=preflight.runtime_root, canary=canary)
            result = runner.execute_consumed_scenario(scenario=preflight.runtime_scenario, package=package, admission=admission, receipt_ledger=ledger, consumed_receipt=consumed, execution_preflight=preflight)
        preflight.output_path.write_text(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except Exception as exc:
        try:
            ledger.recover_consumed_without_terminal(preflight.receipt_id)
        except M2A1ReceiptAuthorityError:
            pass
        print(json.dumps({"status": "m2_a1_post_consume_outcome_unknown", "typed_error": type(exc).__name__, "receipt_consumed": True, "retry_permitted": False}, sort_keys=True))
        return 1
    print(json.dumps({"status": result.actual_status, "scenario_id": result.scenario_id, "actual_result_digest": result.actual_result_digest}, sort_keys=True))
    return 0 if result.actual_status in {"succeeded", "typed_stop"} else 1
