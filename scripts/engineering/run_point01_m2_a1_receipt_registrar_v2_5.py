"""Authority-only registrar for a future exact v2.5 M2-A1 receipt.

Phase B0.2 never invokes this entrypoint.  Its code is frozen so a later
review can bind the actual registrar bytes rather than an external mutable
script.  It creates authority only after the production preflight passes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
PACKAGE_PATH = ROOT / "data/manifests/point01_m2_a1_execution_ready_audit_package_manifest_v2_5.json"
sys.path.insert(0, str(ROOT / "src"))


def _json(path: Path) -> Mapping[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, Mapping):
        raise ValueError(f"m2_a1_json_mapping_required:{path}")
    return loaded


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Register one exact v2.5 package-bound receipt without runtime materialization.")
    parser.add_argument("--register-exact-receipt", action="store_true")
    parser.add_argument("--admission", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--scenario-id")
    args = parser.parse_args(argv)
    if not args.register_exact_receipt:
        print(json.dumps({"status": "m2_a1_receipt_registration_not_requested", "runtime_or_output_materialized": False}, ensure_ascii=False))
        return 1
    if args.admission is None or args.receipt is None or not args.scenario_id:
        print(json.dumps({"status": "m2_a1_exact_receipt_registration_arguments_required"}, ensure_ascii=False))
        return 2
    from sec_agent.canonical_runtime.m2_a1_execution_receipt import (  # noqa: PLC0415
        M2A1ExecutionPreflightError,
        M2A1ExecutionReceipt,
        M2A1ExternalPackageAdmission,
        M2A1ReceiptAuthorityError,
        M2A1ReceiptLedger,
        preflight_exact_execution,
    )
    try:
        package = _json(PACKAGE_PATH)
        admission = M2A1ExternalPackageAdmission.model_validate(_json(args.admission))
        receipt = M2A1ExecutionReceipt.model_validate(_json(args.receipt))
        preflight = preflight_exact_execution(package, admission, repository_root=ROOT, receipt_id=receipt.receipt_id, scenario_id=args.scenario_id)
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
        )
        state = ledger.state(receipt.receipt_id)
    except (M2A1ExecutionPreflightError, M2A1ReceiptAuthorityError, ValueError) as exc:
        print(json.dumps({"status": str(exc), "runtime_or_output_materialized": False, "m2_runtime_imported": False}, ensure_ascii=False))
        return 2
    print(json.dumps({"status": registered["registration_status"], "receipt_id": receipt.receipt_id, "receipt_digest": registered["receipt_digest"], "state": state["state"] if state else None, "runtime_or_output_materialized": False, "m2_runtime_imported": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
