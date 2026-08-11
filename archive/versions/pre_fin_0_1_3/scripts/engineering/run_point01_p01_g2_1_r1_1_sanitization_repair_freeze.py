"""Freeze the superseding P01-G2.1-R1.1 sanitization-repair package."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.canonical_runtime.p01_g2_1_forensic_repair import (
    R1_1_GATE_SCHEMA,
    R1_1_PACKAGE_SCHEMA,
    build_sanitization_reconciliation,
    validate_incident_input,
    validate_sanitization_reconciliation,
    validate_sanitization_repair_package,
)


POLICY = "configs/engineering_handoff/point01_p01_g2_1_r1_1_sanitization_repair_policy_v1_0.json"
R1_INPUTS = {
    "incident": "data/manifests/point01_p01_g2_1_r1_incident_input_manifest_v1_0.json",
    "reconciliation": "data/manifests/point01_p01_g2_1_r1_historical_incident_reconciliation_v1_0.json",
    "package": "data/manifests/point01_p01_g2_1_r1_forensic_repair_package_v1_0.json",
    "gate": "data/manifests/point01_p01_g2_1_r1_forensic_repair_gate_v1_0.json",
}
INPUTS = (
    POLICY,
    *R1_INPUTS.values(),
    "src/sec_agent/canonical_runtime/m2_a1_execution_receipt.py",
    "src/sec_agent/canonical_runtime/m2_a1_v2_10_execution_proof.py",
    "src/sec_agent/canonical_runtime/p01_g2_1_forensic_repair.py",
    "scripts/engineering/run_point01_p01_g2_1_r1_1_sanitization_repair_freeze.py",
    "tests/contract/test_point01_p01_g2_1_r1_forensic_repair.py",
)
OUTPUTS = {
    "reconciliation": ROOT / "data/manifests/point01_p01_g2_1_r1_1_sanitization_reconciliation_v1_0.json",
    "package": ROOT / "data/manifests/point01_p01_g2_1_r1_1_sanitization_repair_package_v1_0.json",
    "gate": ROOT / "data/manifests/point01_p01_g2_1_r1_1_sanitization_repair_gate_v1_0.json",
}


def _index_bytes(relative: str) -> bytes:
    completed = subprocess.run(["git", "show", f":{relative}"], cwd=ROOT, capture_output=True, check=False)
    if completed.returncode:
        raise RuntimeError(f"p01_g2_1_r1_1_index_input_missing:{relative}")
    return completed.stdout


def _mapping(relative: str) -> Mapping[str, Any]:
    value = json.loads(_index_bytes(relative).decode("utf-8"))
    if not isinstance(value, Mapping):
        raise RuntimeError(f"p01_g2_1_r1_1_mapping_required:{relative}")
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_artifacts() -> dict[str, Mapping[str, Any]]:
    policy = _mapping(POLICY)
    r1 = {name: _mapping(path) for name, path in R1_INPUTS.items()}
    if r1["package"].get("repair_package_digest") != policy["supersedes"]["r1_repair_package_digest"] or r1["gate"].get("gate_digest") != policy["supersedes"]["r1_gate_digest"]:
        raise RuntimeError("p01_g2_1_r1_1_rejected_r1_package_binding_invalid")
    incident_errors = validate_incident_input(r1["incident"], policy=policy)
    if incident_errors:
        raise RuntimeError("p01_g2_1_r1_1_incident_input_invalid:" + ",".join(incident_errors))
    reconciliation = build_sanitization_reconciliation(incident_input=r1["incident"], rejected_r1_reconciliation=r1["reconciliation"], policy=policy)
    reconciliation_errors = validate_sanitization_reconciliation(reconciliation, incident_input=r1["incident"], policy=policy)
    if reconciliation_errors:
        raise RuntimeError("p01_g2_1_r1_1_reconciliation_invalid:" + ",".join(reconciliation_errors))
    input_hashes = {relative: hashlib.sha256(_index_bytes(relative)).hexdigest() for relative in sorted(INPUTS)}
    package_payload = {
        "schema_version": R1_1_PACKAGE_SCHEMA,
        "repair_ref": "point01-p01-g2-1-r1-1-child-incident-sanitization-repair-v1",
        "status": "P01_G2_1_R1_1_SANITIZATION_REPAIR_PENDING_INDEPENDENT_REVIEW",
        "scope": policy["scope"],
        "supersedes": dict(policy["supersedes"]),
        "historical_bindings": {
            "incident_input_digest": r1["incident"]["incident_input_digest"],
            "r1_reconciliation_digest": r1["reconciliation"]["reconciliation_digest"],
            "r1_1_reconciliation_digest": reconciliation["reconciliation_digest"],
            "historical_terminal_digest": r1["incident"]["terminal_digest"],
            "fixed_approval_store_sha256": r1["incident"]["fixed_approval_store_sha256"],
        },
        "sanitization_contract": policy["sanitization_contract"],
        "root_cause_status": "not_determined; sanitizer repair proves only bounded secret-minimization contract",
        "input_bytes_source": "git_index",
        "input_file_sha256": input_hashes,
        "input_hash_count": len(input_hashes),
        "input_hashes_digest": canonical_digest(input_hashes),
        "execution_counts": {"operational_authority": 0, "receipt": 0, "baseline": 0, "negative_case": 0, "network": 0, "tool": 0, "model": 0, "provider": 0, "fixed_store_write": 0},
        "prohibitions": policy["prohibitions"],
    }
    package = {**package_payload, "repair_package_digest": canonical_digest(package_payload)}
    package_errors = validate_sanitization_repair_package(package, policy=policy)
    gate_payload = {
        "schema_version": R1_1_GATE_SCHEMA,
        "status": "pass" if not package_errors else "fail_closed",
        "repair_ref": package["repair_ref"],
        "repair_package_digest": package["repair_package_digest"],
        "r1_reconciliation_digest": r1["reconciliation"]["reconciliation_digest"],
        "r1_1_reconciliation_digest": reconciliation["reconciliation_digest"],
        "package_current_verify": "pass" if not package_errors else "fail_closed",
        "validation_errors": list(package_errors),
        "execution_counts": package["execution_counts"],
        "next_step": "independent_review_only_no_operational_authority",
    }
    gate = {**gate_payload, "gate_digest": canonical_digest(gate_payload)}
    return {"reconciliation": reconciliation, "package": package, "gate": gate}


def main() -> int:
    artifacts = build_artifacts()
    for name, path in OUTPUTS.items():
        _write(path, artifacts[name])
    print(json.dumps({"status": artifacts["gate"]["status"], "repair_package_digest": artifacts["package"]["repair_package_digest"], "gate_digest": artifacts["gate"]["gate_digest"], "reconciliation_digest": artifacts["reconciliation"]["reconciliation_digest"]}, sort_keys=True))
    return 0 if artifacts["gate"]["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
