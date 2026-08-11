"""Freeze P01-G2.1-R1 forensic-repair inputs without touching prior evidence."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.canonical_runtime.p01_g2_1_forensic_repair import (
    R1_GATE_SCHEMA,
    R1_INCIDENT_INPUT_SCHEMA,
    R1_PACKAGE_SCHEMA,
    build_historical_reconciliation,
    validate_incident_input,
    validate_reconciliation,
    validate_repair_package,
)


POLICY = "configs/engineering_handoff/point01_p01_g2_1_r1_forensic_repair_policy_v1_0.json"
HISTORICAL_PACKAGE = "data/manifests/point01_p01_g2_1_operational_execution_package_manifest_v1_0.json"
HISTORICAL_GATE = "data/manifests/point01_p01_g2_1_operational_execution_package_gate_v1_0.json"
INPUTS = (
    POLICY,
    HISTORICAL_PACKAGE,
    HISTORICAL_GATE,
    "src/sec_agent/canonical_runtime/m2_a1_execution_receipt.py",
    "src/sec_agent/canonical_runtime/m2_a1_v2_10_execution_proof.py",
    "src/sec_agent/canonical_runtime/p01_g2_1_forensic_repair.py",
    "scripts/engineering/run_point01_p01_g2_1_r1_forensic_repair_freeze.py",
    "tests/contract/test_point01_p01_g2_1_r1_forensic_repair.py",
)
OUTPUTS = {
    "incident_input": ROOT / "data/manifests/point01_p01_g2_1_r1_incident_input_manifest_v1_0.json",
    "reconciliation": ROOT / "data/manifests/point01_p01_g2_1_r1_historical_incident_reconciliation_v1_0.json",
    "package": ROOT / "data/manifests/point01_p01_g2_1_r1_forensic_repair_package_v1_0.json",
    "gate": ROOT / "data/manifests/point01_p01_g2_1_r1_forensic_repair_gate_v1_0.json",
}

# These inputs are historical, restricted, and read only.  Their raw child
# streams were never captured and are intentionally not copied into Git.
HISTORICAL_CASE_RESULT = Path("D:/temp/FIN_Insight_Agent/point01_p01_g2_1_exact_operational_tranche/g2-baseline/baseline_case_result.json")
HISTORICAL_LEDGER = Path("D:/temp/FIN_Insight_Agent/point01_m2_a1_exact_admitted_runs_v2_10/6dd0249b2a76578e8c0f3e1edbe50968918a6db1f3a428a4ac55a165d35caf35/authority/m2_a1_execution_receipts.sqlite")


def _index_bytes(relative: str) -> bytes:
    completed = subprocess.run(["git", "show", f":{relative}"], cwd=ROOT, capture_output=True, check=False)
    if completed.returncode:
        raise RuntimeError(f"p01_g2_1_r1_index_input_missing:{relative}")
    return completed.stdout


def _index_mapping(relative: str) -> Mapping[str, Any]:
    value = json.loads(_index_bytes(relative).decode("utf-8"))
    if not isinstance(value, Mapping):
        raise RuntimeError(f"p01_g2_1_r1_mapping_required:{relative}")
    return value


def _sha_index(relative: str) -> str:
    return hashlib.sha256(_index_bytes(relative)).hexdigest()


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _historical_event_sequence() -> list[str]:
    if not HISTORICAL_LEDGER.is_file():
        raise RuntimeError("p01_g2_1_r1_historical_ledger_missing")
    uri = f"file:{HISTORICAL_LEDGER.as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        rows = connection.execute(
            "select event_type, payload_json from point01_m2_a1_execution_receipt_events order by event_id"
        ).fetchall()
    sequence: list[str] = []
    for event_type, payload_json in rows:
        payload = json.loads(str(payload_json))
        sequence.append(f"{event_type}:{payload['terminal_status']}" if event_type == "TERMINAL" else str(event_type))
    return sequence


def build_artifacts() -> dict[str, Mapping[str, Any]]:
    policy = _index_mapping(POLICY)
    prior_package = _index_mapping(HISTORICAL_PACKAGE)
    prior_gate = _index_mapping(HISTORICAL_GATE)
    if prior_package.get("package_digest") != policy["historical_incident"]["execution_package_digest"] or prior_gate.get("gate_digest") != policy["historical_incident"]["execution_gate_digest"]:
        raise RuntimeError("p01_g2_1_r1_prior_package_binding_mismatch")
    if not HISTORICAL_CASE_RESULT.is_file():
        raise RuntimeError("p01_g2_1_r1_historical_result_missing")
    result = json.loads(HISTORICAL_CASE_RESULT.read_text(encoding="utf-8"))
    if result.get("result_digest") != policy["historical_incident"]["baseline_result_digest"]:
        raise RuntimeError("p01_g2_1_r1_historical_result_digest_mismatch")
    if result.get("details", {}).get("terminal_digest") != policy["historical_incident"]["terminal_digest"]:
        raise RuntimeError("p01_g2_1_r1_historical_terminal_digest_mismatch")
    sequence = _historical_event_sequence()
    if sequence != policy["historical_incident"]["ledger_sequence"]:
        raise RuntimeError("p01_g2_1_r1_historical_ledger_sequence_mismatch")
    incident_payload = {
        "schema_version": R1_INCIDENT_INPUT_SCHEMA,
        "execution_package_digest": prior_package["package_digest"],
        "execution_gate_digest": prior_gate["gate_digest"],
        "baseline_result_digest": result["result_digest"],
        "terminal_digest": result["details"]["terminal_digest"],
        "fixed_approval_store_sha256": policy["historical_incident"]["fixed_approval_store_sha256"],
        "ledger_sequence": sequence,
        "restricted_authority_root_ref": policy["historical_incident"]["restricted_authority_root_ref"],
        "historical_capture_status": "not_persisted_pre_r1",
        "restricted_input_fingerprints": {
            "baseline_case_result_sha256": _sha_file(HISTORICAL_CASE_RESULT),
            "consumed_receipt_ledger_sha256": _sha_file(HISTORICAL_LEDGER),
        },
    }
    incident = {**incident_payload, "incident_input_digest": canonical_digest(incident_payload)}
    errors = validate_incident_input(incident, policy=policy)
    if errors:
        raise RuntimeError("p01_g2_1_r1_incident_input_invalid:" + ",".join(errors))
    reconciliation = build_historical_reconciliation(incident_input=incident, policy=policy)
    reconciliation_errors = validate_reconciliation(reconciliation, incident_input=incident, policy=policy)
    if reconciliation_errors:
        raise RuntimeError("p01_g2_1_r1_reconciliation_invalid:" + ",".join(reconciliation_errors))
    input_hashes = {relative: _sha_index(relative) for relative in sorted(INPUTS)}
    package_payload = {
        "schema_version": R1_PACKAGE_SCHEMA,
        "repair_ref": "point01-p01-g2-1-r1-child-failure-forensic-repair-v1",
        "status": "P01_G2_1_R1_FORENSIC_REPAIR_PENDING_INDEPENDENT_REVIEW",
        "scope": policy["scope"],
        "historical_bindings": {
            "incident_input_digest": incident["incident_input_digest"],
            "reconciliation_digest": reconciliation["reconciliation_digest"],
            "execution_package_digest": incident["execution_package_digest"],
            "execution_gate_digest": incident["execution_gate_digest"],
            "baseline_result_digest": incident["baseline_result_digest"],
            "terminal_digest": incident["terminal_digest"],
            "fixed_approval_store_sha256": incident["fixed_approval_store_sha256"],
        },
        "future_nonzero_child_contract": policy["future_nonzero_child_contract"],
        "root_cause_status": "hypothesis_only_no_historical_stdout_stderr; deterministic_fixture_proof_required",
        "input_bytes_source": "git_index",
        "input_file_sha256": input_hashes,
        "input_hash_count": len(input_hashes),
        "input_hashes_digest": canonical_digest(input_hashes),
        "execution_counts": {"operational_authority": 0, "receipt": 0, "baseline": 0, "negative_case": 0, "network": 0, "tool": 0, "model": 0, "provider": 0, "fixed_store_write": 0},
        "prohibitions": policy["prohibitions"],
    }
    package = {**package_payload, "repair_package_digest": canonical_digest(package_payload)}
    package_errors = validate_repair_package(package, policy=policy)
    gate_payload = {
        "schema_version": R1_GATE_SCHEMA,
        "status": "pass" if not package_errors else "fail_closed",
        "repair_ref": package["repair_ref"],
        "repair_package_digest": package["repair_package_digest"],
        "incident_input_digest": incident["incident_input_digest"],
        "reconciliation_digest": reconciliation["reconciliation_digest"],
        "package_current_verify": "pass" if not package_errors else "fail_closed",
        "validation_errors": list(package_errors),
        "execution_counts": package["execution_counts"],
        "next_step": "independent_review_only_no_fresh_operational_receipt",
    }
    gate = {**gate_payload, "gate_digest": canonical_digest(gate_payload)}
    return {"incident_input": incident, "reconciliation": reconciliation, "package": package, "gate": gate}


def main() -> int:
    artifacts = build_artifacts()
    for name, path in OUTPUTS.items():
        _write(path, artifacts[name])
    print(json.dumps({"status": artifacts["gate"]["status"], "repair_package_digest": artifacts["package"]["repair_package_digest"], "gate_digest": artifacts["gate"]["gate_digest"], "incident_input_digest": artifacts["incident_input"]["incident_input_digest"], "reconciliation_digest": artifacts["reconciliation"]["reconciliation_digest"]}, sort_keys=True))
    return 0 if artifacts["gate"]["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
