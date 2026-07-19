from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "configs/engineering_handoff/point01_m1_closeout_gate_manifest_v1_0.json"
DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m1_closeout_gate_result_v1_0.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    output = f"{completed.stdout}\n{completed.stderr}".strip()
    passed = re.search(r"(\d+) passed", output)
    return {
        "command": command,
        "returncode": completed.returncode,
        "passed_count": int(passed.group(1)) if passed else 0,
        "output_tail": output[-4000:],
    }


def _resolved_point(row: dict[str, Any], *, machine_checks_pass: bool) -> dict[str, Any]:
    result = dict(row)
    for field in ("implementation_maturity", "calibration_status"):
        if result.get(field) == "conditional_on_local_contract_suite":
            result[field] = "full_implemented" if field == "implementation_maturity" and machine_checks_pass else (
                "calibrated" if machine_checks_pass else "not_run"
            )
    result["gate_pass"] = (
        result.get("design_maturity") == "frozen"
        and result.get("implementation_maturity") == "full_implemented"
        and (not result.get("calibration_required") or result.get("calibration_status") == "calibrated")
        and not result.get("material_gaps")
    )
    return result


def build_result(manifest: dict[str, Any], checks: dict[str, dict[str, Any]]) -> dict[str, Any]:
    machine_checks_pass = all(row["returncode"] == 0 for row in checks.values())
    points = [_resolved_point(row, machine_checks_pass=machine_checks_pass) for row in manifest["execution_points"]]
    acceptance_gates = []
    for row in manifest["acceptance_gates"]:
        resolved = dict(row)
        evidence_status = None
        evidence: dict[str, Any] = {}
        evidence_path_value = str(resolved["evidence_path"])
        if evidence_path_value != "not_recorded":
            evidence_path = ROOT / evidence_path_value
            try:
                evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
                evidence_status = evidence.get("status")
            except (OSError, json.JSONDecodeError):
                evidence_status = None
        resolved["evidence_status"] = evidence_status
        if resolved["status"] == "conditional_on_local_contract_suite":
            resolved["gate_pass"] = machine_checks_pass and evidence_status == "pass"
        elif resolved["status"] == "external_required":
            resolved["gate_pass"] = bool(
                evidence_status == "approved"
                and str(evidence.get("approver_type") or "") == "human"
                and str(evidence.get("approver_id") or "").strip()
            )
        else:
            resolved["gate_pass"] = False
        acceptance_gates.append(resolved)
    unmet = [
        f"{row['point_id']}: maturity/calibration/material-gap gate not satisfied"
        for row in points
        if not row["gate_pass"]
    ]
    unmet.extend(f"{row['gate_id']} accepted" for row in acceptance_gates if not row["gate_pass"])
    evidence_paths = (
        MANIFEST_PATH,
        ROOT / "scripts/engineering/run_point01_m1_closeout_gate.py",
        ROOT / "scripts/engineering/run_point01_postgresql_conformance_sample.py",
        ROOT / "src/sec_agent/canonical_runtime/models.py",
        ROOT / "src/sec_agent/canonical_runtime/store.py",
        ROOT / "src/sec_agent/canonical_runtime/facade.py",
        ROOT / "tests/contract/test_point01_runtime_facade.py",
        ROOT / "tests/contract/test_point01_sqlite_store.py",
        ROOT / "configs/engineering_handoff/point01_generated_json_schemas_v1_0.json",
        ROOT / "configs/engineering_handoff/point01_m1_rollback_recovery_drill_result_v1_0.json",
        ROOT / "configs/engineering_handoff/point01_m1_human_reviewer_approval_v1_0.json",
        ROOT / "data/manifests/point01_m1_postgresql_conformance_sample_result_v1_0.json",
        ROOT / "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md",
    )
    return {
        "result_version": "finsight_point01_m1_closeout_gate_result_v1_0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": manifest["scope"],
        "authority_boundary": manifest["authority_boundary"],
        "machine_checks": checks,
        "machine_checks_pass": machine_checks_pass,
        "execution_points": points,
        "acceptance_gates": acceptance_gates,
        "unmet_closeout_conditions": unmet,
        "gate_status": "pass" if not unmet else "fail_closed",
        "milestone_status": "M1_complete" if not unmet else "M1_open",
        "fixed_input_sha256": {str(path.relative_to(ROOT)).replace("\\", "/"): _sha256(path) for path in evidence_paths},
        "boundary": "No authority cutover, model compiler, paid model, full-chain, Evidence, Writer, release, OA, or Monitoring runtime is exercised by this gate.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Point 01 M1 closeout gate.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    checks = {name: _run(command) for name, command in manifest["verification"].items()}
    result = build_result(manifest, checks)
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"gate_status": result["gate_status"], "output": str(output), "unmet": result["unmet_closeout_conditions"]}, ensure_ascii=False))
    return 0 if result["gate_status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
