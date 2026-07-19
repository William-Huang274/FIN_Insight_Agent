"""One-shot, reviewer-approved M2-A1 v2.4 baseline JIT execution window.

This package-external orchestrator is intentionally outside the frozen v2.4
package inputs.  It binds the approved package, three gates and Phase-A repair
evidence into one short-lived external admission and one receipt.  It runs
only ``p01-baseline-separated-input`` and always stops after terminal audit.
No retry, replay, renewal or follow-on scenario is implemented.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

PACKAGE = ROOT / "data/manifests/point01_m2_a1_execution_ready_audit_package_manifest_v2_4.json"
PACKAGE_GATE = ROOT / "data/manifests/point01_m2_a1_execution_ready_audit_package_freeze_gate_result_v2_4.json"
PLAN = ROOT / "data/manifests/point01_m2_a1_receipt_execution_plan_v1_1_operational_qualification.json"
PLAN_GATE = ROOT / "data/manifests/point01_m2_a1_receipt_execution_plan_v1_1_operational_qualification_gate.json"
BLUEPRINT = ROOT / "data/manifests/point01_m2_a1_baseline_authority_blueprint_v1_1_operational_qualification.json"
BLUEPRINT_GATE = ROOT / "data/manifests/point01_m2_a1_baseline_authority_blueprint_v1_1_operational_qualification_gate.json"
ORACLE = ROOT / "configs/engineering_handoff/point01_m2_a1_independent_expected_cell_oracle_v1_1.json"
MATRIX = ROOT / "configs/engineering_handoff/point01_m2_a1_execution_ready_scenario_matrix_v2_1.json"
FIXED = ROOT / ".runtime_control/point01_m6_3_5_nvda_sec_document_parser_repaired_global_approval/canonical.sqlite"
PARENT = ROOT / "scripts/engineering/run_point01_m2_a1_actual_audit_v2_4.py"
REGISTRAR = ROOT / "scripts/engineering/run_point01_m2_a1_receipt_registrar_v2_4.py"

SCENARIO = "p01-baseline-separated-input"
INPUT_REF = "m2-a1-ai-semis-input"
MUTATION = "none"
REVIEWER = "william/003/total_reviewer"
PHASE_A = {
    "classification": "537801860ceb455c1ce035621776128c3d8647e2d3af00e66b02d27e8b1e0b71",
    "repair_package": "11f4cd9267e56e9c6c33eaeb32119194731d76dbe0040e34b441e6daf66bd7cd",
    "repair_gate": "52cd13eda74affc99352a14a3ffff322e96b992b252c40d9dd6335d9f9e181fe",
}
OUT = {
    "admission": ROOT / "data/manifests/point01_m2_a1_external_package_admission_v2_4_baseline_jit.json",
    "authority": ROOT / "data/manifests/point01_m2_a1_external_package_admission_authority_v2_4_baseline_jit.json",
    "receipt": ROOT / "data/manifests/point01_m2_a1_single_use_execution_receipt_v2_4_baseline_jit.json",
    "preflight": ROOT / "data/manifests/point01_m2_a1_v2_4_baseline_jit_preflight_result.json",
    "oracle": ROOT / "data/manifests/point01_m2_a1_v2_4_baseline_jit_oracle_evaluation.json",
    "reviewer": ROOT / "data/manifests/point01_m2_a1_v2_4_baseline_jit_reviewer_gate.json",
    "closeout": ROOT / "data/manifests/point01_m2_a1_v2_4_baseline_jit_execution_closeout.json",
}


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def utc(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
        raise RuntimeError("baseline_jit_utc_required")
    return value.isoformat().replace("+00:00", "Z")


def load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"baseline_jit_mapping_required:{path}")
    return payload


def write(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def verify_file_staged(path: Path) -> None:
    relative = path.relative_to(ROOT).as_posix()
    staged = subprocess.run(["git", "show", f":{relative}"], cwd=ROOT, capture_output=True, check=False)
    if staged.returncode or staged.stdout.replace(b"\r\n", b"\n") != path.read_bytes().replace(b"\r\n", b"\n"):
        raise RuntimeError(f"baseline_jit_working_index_drift:{relative}")


def verify_frozen_inputs(package: Mapping[str, Any], package_gate: Mapping[str, Any], plan: Mapping[str, Any], plan_gate: Mapping[str, Any], blueprint: Mapping[str, Any], blueprint_gate: Mapping[str, Any]) -> None:
    for path in (PACKAGE, PACKAGE_GATE, PLAN, PLAN_GATE, BLUEPRINT, BLUEPRINT_GATE, ORACLE, MATRIX):
        verify_file_staged(path)
    for payload, field in ((package, "package_digest"), (package_gate, "gate_digest"), (plan, "plan_digest"), (plan_gate, "gate_digest"), (blueprint, "blueprint_digest"), (blueprint_gate, "gate_digest")):
        if payload.get(field) != digest({key: value for key, value in payload.items() if key != field}):
            raise RuntimeError(f"baseline_jit_digest_invalid:{field}")
    if package_gate.get("status") != "pass" or package_gate.get("package_digest") != package.get("package_digest"):
        raise RuntimeError("baseline_jit_package_gate_binding_invalid")
    if plan_gate.get("status") != "pass" or plan_gate.get("package_digest") != package.get("package_digest") or plan.get("exact_package", {}).get("package_gate_digest") != package_gate.get("gate_digest"):
        raise RuntimeError("baseline_jit_plan_gate_binding_invalid")
    binding = blueprint.get("exact_binding")
    if not isinstance(binding, Mapping) or blueprint_gate.get("status") != "pass" or binding.get("package_digest") != package.get("package_digest") or binding.get("package_gate_digest") != package_gate.get("gate_digest") or binding.get("plan_digest") != plan.get("plan_digest") or binding.get("plan_gate_digest") != plan_gate.get("gate_digest") or binding.get("phase_a_digests") != PHASE_A:
        raise RuntimeError("baseline_jit_blueprint_cross_gate_binding_invalid")
    if (binding.get("scenario_id"), binding.get("input_ref"), binding.get("mutation"), binding.get("reviewer_identity")) != (SCENARIO, INPUT_REF, MUTATION, REVIEWER):
        raise RuntimeError("baseline_jit_baseline_binding_invalid")
    if package.get("phase_a_digests") != PHASE_A or package.get("execution_eligibility") != "fresh_exact_admission_and_receipt_required":
        raise RuntimeError("baseline_jit_package_phase_a_or_eligibility_invalid")
    if any(value != "do_not_invoke" for value in blueprint.get("command_contracts", {}).values()):
        raise RuntimeError("baseline_jit_blueprint_command_contract_invalid")


def main() -> int:
    from sec_agent.canonical_runtime.m2_a1_execution_receipt import M2A1ExecutionReceipt, M2A1ExternalPackageAdmission, M2A1ReceiptLedger, preflight_exact_execution

    package, package_gate, plan, plan_gate, blueprint, blueprint_gate = (load(path) for path in (PACKAGE, PACKAGE_GATE, PLAN, PLAN_GATE, BLUEPRINT, BLUEPRINT_GATE))
    verify_frozen_inputs(package, package_gate, plan, plan_gate, blueprint, blueprint_gate)
    fixed_before = hashlib.sha256(FIXED.read_bytes()).hexdigest()
    if fixed_before != package["fixed_store_fingerprints"]["fixed_approval_store"]["sha256"]:
        raise RuntimeError("baseline_jit_fixed_fingerprint_before_mismatch")
    issued_at = datetime.now(timezone.utc)
    admission_expiry = issued_at + timedelta(minutes=30)
    receipt_expiry = issued_at + timedelta(minutes=15)
    admission = M2A1ExternalPackageAdmission.create(
        admission_ref="approve_m2_a1_v2_4_single_fresh_baseline_jit_window_only",
        admission_id=f"point01-m2-a1-v2-4-baseline-{issued_at.strftime('%Y%m%dT%H%M%SZ')}",
        admission_version=1,
        reviewer_identity=REVIEWER,
        package_ref=str(package["package_ref"]),
        executable_package_digest=str(package["package_digest"]),
        scope=str(package["scope"]),
        authority_boundary=str(package["authority_boundary"]),
        execution_staging_namespace_id=str(package["execution_preflight"]["execution_staging_namespace_id"]),
        expires_at=admission_expiry,
        schema_version="finsight_point01_m2_a1_external_package_admission_v2_4",
    )
    nonce_sha256 = hashlib.sha256(secrets.token_bytes(32)).hexdigest()
    receipt_id = f"point01-m2-a1-v2-4-baseline-{nonce_sha256[:24]}"
    receipt = M2A1ExecutionReceipt.create(
        receipt_id=receipt_id,
        receipt_version=1,
        approval_id=admission.admission_id,
        package_ref=admission.package_ref,
        executable_package_digest=admission.executable_package_digest,
        scope=admission.scope,
        admission_digest=admission.admission_digest,
        nonce_sha256=nonce_sha256,
        expires_at=receipt_expiry,
        reviewer_identity=REVIEWER,
        execution_staging_namespace_id=admission.execution_staging_namespace_id,
        scenario_id=SCENARIO,
        schema_version="finsight_point01_m2_a1_single_use_execution_receipt_v2_4",
    )
    authority_payload = {
        "schema_version": "finsight_point01_m2_a1_external_admission_authority_wrapper_v2_4",
        "artifact_kind": "single_fresh_v2_4_baseline_jit_window_only",
        "reviewer_identity": REVIEWER,
        "decision": "admitted_single_baseline_jit_window_only",
        "issued_at": utc(issued_at),
        "expires_at": utc(admission_expiry),
        "package_ref": package["package_ref"], "package_digest": package["package_digest"], "package_gate_digest": package_gate["gate_digest"],
        "plan_digest": plan["plan_digest"], "plan_gate_digest": plan_gate["gate_digest"], "blueprint_digest": blueprint["blueprint_digest"], "blueprint_gate_digest": blueprint_gate["gate_digest"],
        "phase_a_digests": PHASE_A, "scope": package["scope"], "authority_boundary": package["authority_boundary"],
        "execution_staging_namespace_id": admission.execution_staging_namespace_id, "scenario_id": SCENARIO, "input_ref": INPUT_REF, "mutation": MUTATION,
        "runtime_admission_digest": admission.admission_digest, "receipt_digest": receipt.receipt_digest, "nonce_sha256": nonce_sha256,
        "receipt_expiry": utc(receipt_expiry), "fixed_store_fingerprint": package["fixed_store_fingerprints"]["fixed_approval_store"],
        "raw_nonce_persisted": False, "user_agent_persisted": False, "retry": "forbidden", "replay": "forbidden", "renewal": "forbidden",
    }
    authority = {**authority_payload, "authority_artifact_digest": digest(authority_payload)}
    write(OUT["admission"], admission.model_dump(mode="json"))
    write(OUT["authority"], authority)
    write(OUT["receipt"], receipt.model_dump(mode="json"))

    # The registrar owns only the authority SQLite file.  Its production
    # preflight runs after registration arguments exist but before SQLite.
    registered = subprocess.run([sys.executable, str(REGISTRAR), "--register-exact-receipt", "--admission", str(OUT["admission"]), "--receipt", str(OUT["receipt"]), "--scenario-id", SCENARIO], cwd=ROOT, capture_output=True, text=True, check=False)
    if registered.returncode != 0:
        raise RuntimeError(f"baseline_jit_registration_failed:{registered.stdout.strip()}:{registered.stderr.strip()}")
    preflight = preflight_exact_execution(package, admission, repository_root=ROOT, receipt_id=receipt_id, scenario_id=SCENARIO)
    preflight_payload = {
        "schema_version": "finsight_point01_m2_a1_v2_4_baseline_jit_preflight_v1",
        "status": "registered_preflight_pass_ready_for_single_consume",
        "package_digest": package["package_digest"], "package_gate_digest": package_gate["gate_digest"], "plan_digest": plan["plan_digest"], "plan_gate_digest": plan_gate["gate_digest"],
        "blueprint_digest": blueprint["blueprint_digest"], "blueprint_gate_digest": blueprint_gate["gate_digest"], "phase_a_digests": PHASE_A,
        "admission_digest": admission.admission_digest, "receipt_digest": receipt.receipt_digest, "receipt_id": receipt_id,
        "run_root": str(preflight.run_root), "authority_root": str(preflight.authority_root), "runtime_root": str(preflight.runtime_root), "output_path": str(preflight.output_path),
        "fixed_before_sha256": fixed_before, "external_count": 0, "model_count": 0, "tool_count": 0,
    }
    preflight_result = {**preflight_payload, "preflight_digest": digest(preflight_payload)}
    write(OUT["preflight"], preflight_result)

    executed = subprocess.run([sys.executable, str(PARENT), "--", "--execute-admitted", "--admission", str(OUT["admission"]), "--receipt-id", receipt_id, "--scenario-id", SCENARIO], cwd=ROOT, capture_output=True, text=True, check=False)
    ledger = M2A1ReceiptLedger.open_existing(preflight.ledger_path, approved_authority_root=preflight.authority_root)
    events = ledger.events(receipt_id)
    state = ledger.state(receipt_id)
    fixed_after = hashlib.sha256(FIXED.read_bytes()).hexdigest()
    if fixed_before != fixed_after:
        raise RuntimeError("baseline_jit_fixed_fingerprint_after_mismatch")
    if [event["event_type"] for event in events] != ["REGISTERED", "CONSUMED_BEFORE_RUN", "TERMINAL"]:
        raise RuntimeError("baseline_jit_receipt_event_sequence_invalid")
    with sqlite3.connect(f"{preflight.ledger_path.as_uri()}?mode=ro", uri=True) as connection:
        row = connection.execute("select payload_json from point01_m2_a1_execution_receipts where receipt_id = ?", (receipt_id,)).fetchone()
    if row is None:
        raise RuntimeError("baseline_jit_consumed_receipt_missing")
    consumed = M2A1ExecutionReceipt.model_validate(json.loads(str(row[0])))
    terminal_digest = str(events[-1]["payload_digest"])
    closeout: dict[str, Any] = {
        "schema_version": "finsight_point01_m2_a1_v2_4_baseline_jit_execution_closeout_v1",
        "package_digest": package["package_digest"], "package_gate_digest": package_gate["gate_digest"], "plan_digest": plan["plan_digest"], "plan_gate_digest": plan_gate["gate_digest"],
        "blueprint_digest": blueprint["blueprint_digest"], "blueprint_gate_digest": blueprint_gate["gate_digest"], "phase_a_digests": PHASE_A,
        "admission_digest": admission.admission_digest, "authority_artifact_digest": authority["authority_artifact_digest"], "receipt_digest": receipt.receipt_digest,
        "receipt_id": receipt_id, "receipt_state": state, "ledger_events": [{"event_type": event["event_type"], "payload_digest": event["payload_digest"]} for event in events],
        "parent_returncode": executed.returncode, "parent_stdout": executed.stdout.strip(), "parent_stderr": executed.stderr.strip(),
        "fixed_before_sha256": fixed_before, "fixed_after_sha256": fixed_after,
        "run_root": str(preflight.run_root), "runtime_root": str(preflight.runtime_root), "output_path": str(preflight.output_path),
        "counts": {"admission": 1, "receipt_created": 1, "receipt_registered": 1, "receipt_consumed": 1, "actual": 1, "network_success": 0, "model": 0, "tool": 0, "provider": 0, "fixed_store_open": 0, "business_or_legacy_mutation": 0},
    }
    if not preflight.output_path.is_file():
        closeout.update({"status": "outcome_unknown_fail_fast_no_oracle", "terminal_digest": terminal_digest})
        closeout["closeout_digest"] = digest(closeout)
        write(OUT["closeout"], closeout)
        return 1
    # The actual is terminal and immutable now.  Only at this point may the
    # independent evaluator import/read the reviewer oracle and gate modules.
    from sec_agent.canonical_runtime.m2_a1_audit_oracle import evaluate_independent_oracle
    from sec_agent.canonical_runtime.m2_a1_audit_result import M2A1ImmutableActualResult
    from sec_agent.canonical_runtime.m2_a1_audit_reviewer_gate import review_future_actual

    actual = M2A1ImmutableActualResult.model_validate(load(preflight.output_path))
    oracle_doc, matrix_doc = load(ORACLE), load(MATRIX)
    oracle_case = next(item for item in oracle_doc["oracle_cases"] if item["input_case_ref"] == actual.case_id)
    scenario = next(item for item in matrix_doc["scenarios"] if item["scenario_id"] == SCENARIO)
    oracle_eval = evaluate_independent_oracle(actual, oracle_case, scenario)
    reviewer = review_future_actual(package=package, actual_results=(actual,), oracle_evaluations=(oracle_eval,), expected_scenario_ids=(SCENARIO,), admission=admission, consumed_receipt=consumed, receipt_ledger_state=state, receipt_terminal_event_digest=terminal_digest)
    write(OUT["oracle"], oracle_eval.model_dump(mode="json"))
    write(OUT["reviewer"], reviewer.model_dump(mode="json"))
    closeout.update({"status": "completed_pending_independent_review" if reviewer.status == "pass" else "reviewer_fail_closed_no_retry", "terminal_digest": terminal_digest, "actual_digest": actual.actual_result_digest, "actual_status": actual.actual_status, "oracle_digest": oracle_eval.evaluation_digest, "oracle_status": oracle_eval.status, "reviewer_gate_digest": reviewer.gate_digest, "reviewer_status": reviewer.status})
    closeout["closeout_digest"] = digest(closeout)
    write(OUT["closeout"], closeout)
    print(json.dumps({"status": closeout["status"], "admission_digest": admission.admission_digest, "authority_digest": authority["authority_artifact_digest"], "receipt_digest": receipt.receipt_digest, "actual_digest": actual.actual_result_digest, "oracle_digest": oracle_eval.evaluation_digest, "reviewer_gate_digest": reviewer.gate_digest}, ensure_ascii=False, sort_keys=True))
    return 0 if reviewer.status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
