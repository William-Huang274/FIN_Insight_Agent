"""Execute the one admitted M1-A1 audit rerun without altering its frozen package.

This wrapper is deliberately *outside* the M1-A1 package input manifest.  It
does not build or amend package inputs; it validates the already-frozen
Git-index package, records a package-external total-reviewer admission, and
spends that admission once to invoke the frozen audit runner.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


PACKAGE_PATH = ROOT / "data/manifests/point01_m1_a1_adversarial_audit_package_manifest_v1_1.json"
ADMISSION_PATH = ROOT / "data/manifests/point01_m1_a1_exact_external_package_admission_v1_0.json"
GATE_OUTPUT_PATH = ROOT / "data/manifests/point01_m1_a1_exact_admitted_audit_gate_result_v1_1.json"
RECEIPT_LEDGER_PATH = ROOT / "data/manifests/point01_m1_a1_exact_admitted_execution_receipts_v1_0.jsonl"
RECEIPT_PROJECTION_PATH = ROOT / "data/manifests/point01_m1_a1_exact_admitted_execution_receipt_projection_v1_0.json"
CLOSEOUT_PATH = ROOT / "data/manifests/point01_m1_a1_exact_admitted_audit_execution_closeout_v1_0.json"
FIXED_APPROVAL_DB = ROOT / ".runtime_control/point01_m6_3_5_nvda_sec_document_parser_repaired_global_approval/canonical.sqlite"


def _runner() -> Any:
    path = ROOT / "scripts/engineering/run_point01_m1_a1_adversarial_audit.py"
    spec = importlib.util.spec_from_file_location("point01_m1_a1_admitted_frozen_runner", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("m1_a1_frozen_runner_import_failed")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixed_hash() -> str:
    return hashlib.sha256(FIXED_APPROVAL_DB.read_bytes()).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_receipt(ledger_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    record = {**payload, "record_digest": canonical_digest(payload)}
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
    return record


def _existing_consumption(ledger_path: Path, *, admission_digest: str) -> bool:
    if not ledger_path.exists():
        return False
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("admission_digest") == admission_digest and record.get("single_use_consumed") is True:
            return True
    return False


def _preflight(*, runner: Any, package: dict[str, Any], admission: dict[str, Any]) -> dict[str, Any]:
    package_from_index = runner.build_package_manifest()
    package_current = runner.verify_staged_package_manifest(package)
    admission_result = runner.verify_package_admission(package, admission)
    return {
        "stored_package_matches_index_rebuild": package == package_from_index,
        "stored_package_digest": package.get("package_digest"),
        "index_rebuilt_package_digest": package_from_index.get("package_digest"),
        "package_current_verify": package_current,
        "admission_verify": admission_result,
        "fixed_approval_store_sha256": _fixed_hash(),
        "admission_digest": canonical_digest(admission),
    }


def _preflight_passes(preflight: dict[str, Any]) -> bool:
    return (
        preflight["stored_package_matches_index_rebuild"] is True
        and preflight["package_current_verify"]["status"] == "pass"
        and preflight["admission_verify"]["status"] == "pass"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Spend the exact external admission for one isolated M1-A1 rerun.")
    parser.add_argument("--package", type=Path, default=PACKAGE_PATH)
    parser.add_argument("--admission", type=Path, default=ADMISSION_PATH)
    parser.add_argument("--gate-output", type=Path, default=GATE_OUTPUT_PATH)
    parser.add_argument("--receipt-ledger", type=Path, default=RECEIPT_LEDGER_PATH)
    parser.add_argument("--receipt-projection", type=Path, default=RECEIPT_PROJECTION_PATH)
    parser.add_argument("--closeout", type=Path, default=CLOSEOUT_PATH)
    args = parser.parse_args()

    package_path = args.package if args.package.is_absolute() else ROOT / args.package
    admission_path = args.admission if args.admission.is_absolute() else ROOT / args.admission
    gate_output = args.gate_output if args.gate_output.is_absolute() else ROOT / args.gate_output
    ledger_path = args.receipt_ledger if args.receipt_ledger.is_absolute() else ROOT / args.receipt_ledger
    receipt_projection = args.receipt_projection if args.receipt_projection.is_absolute() else ROOT / args.receipt_projection
    closeout_path = args.closeout if args.closeout.is_absolute() else ROOT / args.closeout

    runner = _runner()
    package = _load(package_path)
    admission = _load(admission_path)
    preflight_before = _preflight(runner=runner, package=package, admission=admission)
    if not _preflight_passes(preflight_before):
        _write_json(
            closeout_path,
            {
                "schema_version": "finsight_point01_m1_a1_exact_admitted_execution_closeout_v1_0",
                "status": "fail_closed_preflight",
                "preflight_before": preflight_before,
                "external_execution_counts": {"network": 0, "tool": 0, "model": 0, "provider": 0, "postgresql_schema_write": 0},
            },
        )
        return 1

    admission_digest = preflight_before["admission_digest"]
    if _existing_consumption(ledger_path, admission_digest=admission_digest):
        _write_json(
            closeout_path,
            {
                "schema_version": "finsight_point01_m1_a1_exact_admitted_execution_closeout_v1_0",
                "status": "fail_closed_execution_receipt_already_consumed",
                "preflight_before": preflight_before,
                "external_execution_counts": {"network": 0, "tool": 0, "model": 0, "provider": 0, "postgresql_schema_write": 0},
            },
        )
        return 1

    run_id = f"m1_a1_exact_admitted_rerun_{uuid.uuid4().hex}"
    receipt_id = f"point01-m1-a1-exact-admitted-execution:{run_id}"
    started_at = _utc_now()
    start_record = _append_receipt(
        ledger_path,
        {
            "schema_version": "finsight_point01_m1_a1_execution_receipt_event_v1_0",
            "event": "single_use_consumed_before_actual_audit",
            "receipt_id": receipt_id,
            "run_id": run_id,
            "started_at": started_at,
            "single_use_consumed": True,
            "approval_source": "total_review_delegation_019f44f4-48a0-73c0-bb8a-5aa2da584e73",
            "admission_ref": admission["admission_ref"],
            "admission_digest": admission_digest,
            "package_digest": package["package_digest"],
            "scope": package["scope"],
            "authority_boundary": package["authority_boundary"],
        },
    )

    try:
        gate = runner.build_result(package, package_admission=admission, run_broader=True)
        _write_json(gate_output, gate)
        terminal_status = "completed" if gate["gate_status"] == "pass" else "completed_fail_closed"
        execution_error: str | None = None
    except Exception as exc:  # Receipt stays consumed on every post-start failure.
        gate = None
        terminal_status = "execution_exception"
        execution_error = f"{type(exc).__name__}:{exc}"

    completed_at = _utc_now()
    preflight_after = _preflight(runner=runner, package=package, admission=admission)
    completion_record = _append_receipt(
        ledger_path,
        {
            "schema_version": "finsight_point01_m1_a1_execution_receipt_event_v1_0",
            "event": "single_use_execution_terminal",
            "receipt_id": receipt_id,
            "run_id": run_id,
            "started_at": started_at,
            "completed_at": completed_at,
            "single_use_consumed": True,
            "terminal_status": terminal_status,
            "admission_digest": admission_digest,
            "package_digest": package["package_digest"],
            "gate_result_digest": canonical_digest(gate) if gate is not None else None,
            "execution_error": execution_error,
        },
    )
    receipt_payload = {
        "schema_version": "finsight_point01_m1_a1_execution_receipt_projection_v1_0",
        "receipt_id": receipt_id,
        "run_id": run_id,
        "single_use_consumed": True,
        "approval_source": start_record["approval_source"],
        "admission_ref": admission["admission_ref"],
        "admission_digest": admission_digest,
        "package_digest": package["package_digest"],
        "started_at": started_at,
        "completed_at": completed_at,
        "terminal_status": terminal_status,
        "start_record_digest": start_record["record_digest"],
        "completion_record_digest": completion_record["record_digest"],
        "receipt_ledger_path": str(ledger_path.relative_to(ROOT)).replace("\\", "/"),
    }
    receipt = {**receipt_payload, "receipt_digest": canonical_digest(receipt_payload)}
    _write_json(receipt_projection, receipt)

    closeout_payload = {
        "schema_version": "finsight_point01_m1_a1_exact_admitted_execution_closeout_v1_0",
        "status": "completed_pending_independent_review" if gate is not None and gate["gate_status"] == "pass" and _preflight_passes(preflight_after) else "fail_closed",
        "historical_m1_claim": "not_redeclared_by_A1",
        "package_ref": package["package_ref"],
        "package_digest": package["package_digest"],
        "admission_digest": admission_digest,
        "execution_receipt_digest": receipt["receipt_digest"],
        "gate_result_digest": canonical_digest(gate) if gate is not None else None,
        "preflight_before": preflight_before,
        "preflight_after": preflight_after,
        "fixed_approval_store_sha256_before": preflight_before["fixed_approval_store_sha256"],
        "fixed_approval_store_sha256_after": preflight_after["fixed_approval_store_sha256"],
        "gate_status": gate["gate_status"] if gate is not None else "execution_exception",
        "gate_output": str(gate_output.relative_to(ROOT)).replace("\\", "/") if gate is not None else None,
        "execution_error": execution_error,
        "boundary": "This one receipt spends only the exact M1-A1 isolated temporary-SQLite audit authorization. It does not retain or complete M1 and authorizes neither M2-A1 nor M6/R3.",
    }
    closeout = {**closeout_payload, "closeout_digest": canonical_digest(closeout_payload)}
    _write_json(closeout_path, closeout)
    print(
        json.dumps(
            {
                "status": closeout["status"],
                "gate_status": closeout["gate_status"],
                "receipt_digest": receipt["receipt_digest"],
                "gate_result_digest": closeout["gate_result_digest"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if closeout["status"] == "completed_pending_independent_review" else 1


if __name__ == "__main__":
    raise SystemExit(main())
