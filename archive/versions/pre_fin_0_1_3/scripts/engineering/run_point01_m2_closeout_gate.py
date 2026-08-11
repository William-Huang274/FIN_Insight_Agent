from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "configs/engineering_handoff/point01_m2_closeout_gate_manifest_v1_0.json"
PLAN_PATH = ROOT / "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md"
DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m2_closeout_gate_result_v1_0.json"


RUNNERS = {
    "M2.0": "scripts/engineering/run_point01_m2_design_lint.py",
    "M2.1": "scripts/engineering/run_point01_m2_1_compiler_validation_fixture.py",
    "M2.2": "scripts/engineering/run_point01_m2_2_full_serializer_fixture.py",
    "M2.3": "scripts/engineering/run_point01_m2_3_pack_registry_fixture.py",
    "M2.4": "scripts/engineering/run_point01_m2_4_pack_selection_fixture.py",
    "M2.5": "scripts/engineering/run_point01_m2_5_cell_composition_fixture.py",
    "M2.6": "scripts/engineering/run_point01_m2_6_evidence_slot_policy_fixture.py",
    "M2.7": "scripts/engineering/run_point01_m2_7_legacy_semantic_mapping_fixture.py",
    "M2.8": "scripts/engineering/run_point01_m2_8_model_admission_fixture.py",
    "M2.9": "scripts/engineering/run_point01_m2_9_shadow_orchestration_fixture.py",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_children(work_root: Path) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for point_id, relative_script in RUNNERS.items():
        output = work_root / f"{point_id.lower().replace('.', '_')}.json"
        command = [sys.executable, str(ROOT / relative_script), "--output", str(output)]
        if point_id in {"M2.2", "M2.9"}:
            command.extend(["--work-root", str(work_root / point_id.lower().replace('.', '_'))])
        completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
        payload: dict[str, Any] = {}
        if output.exists():
            payload = json.loads(output.read_text(encoding="utf-8"))
        results[point_id] = {
            "returncode": completed.returncode,
            "stdout_tail": completed.stdout[-1000:],
            "stderr_tail": completed.stderr[-1000:],
            "payload": payload,
        }
    return results


def evaluate(child_results: Mapping[str, Mapping[str, Any]], manifest: Mapping[str, Any]) -> dict[str, bool]:
    payloads = {point: dict(result.get("payload") or {}) for point, result in child_results.items()}
    child_pass = all(
        child_results.get(point, {}).get("returncode") == 0 and payloads.get(point, {}).get("status") == "pass"
        for point in ["M2.0", *manifest["required_children"]]
    )
    m29 = payloads.get("M2.9", {})
    m22 = payloads.get("M2.2", {})
    m26 = payloads.get("M2.6", {})
    m27 = payloads.get("M2.7", {})
    m28 = payloads.get("M2.8", {})
    return {
        "all_m2_0_to_m2_9_machine_artifacts_pass": child_pass,
        "four_positive_calibration_cases_pass": bool(m29.get("checks", {}).get("four_sector_shadow_compilations_pass")),
        "negative_pack_resolution_or_lineage_loss_rejected": bool(m22.get("checks", {}).get("selection_mismatch_rejected")),
        "negative_evidence_policy_or_typed_gap_loss_rejected": bool(m22.get("checks", {}).get("typed_gap_drop_rejected")) and bool(m26.get("checks", {}).get("relationship_overreach_rejected")),
        "negative_legacy_mapping_or_direct_equivalence_rejected": bool(m22.get("checks", {}).get("legacy_direct_equivalence_rejected")) and bool(m27.get("checks", {}).get("invalid_action_rejected")),
        "lead_boundary_and_no_model_or_external_execution_preserved": bool(m28.get("checks", {}).get("adapter_not_invoked"))
        and bool(m29.get("checks", {}).get("feature_flag_off_skips_all_writes"))
        and all(
            int((payload.get("authority_boundary") or {}).get("model_call_count", 0)) == 0
            and int((payload.get("authority_boundary") or {}).get("external_call_count", 0)) == 0
            for payload in payloads.values()
        ),
    }


def build_result(work_root: Path) -> dict[str, Any]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    child_results = _run_children(work_root)
    checks = evaluate(child_results, manifest)
    unmet = tuple(sorted(name for name, passed in checks.items() if not passed))
    return {
        "result_version": "finsight_point01_m2_closeout_gate_result_v1_0",
        "scope": manifest["scope"],
        "gate_status": "pass" if not unmet else "fail_closed",
        "milestone_status": "M2_complete" if not unmet else "M2_open",
        "checks": checks,
        "unmet_closeout_conditions": unmet,
        "child_results": child_results,
        "authority_boundary": {
            "legacy_task_run": "authoritative",
            "canonical_lane": "shadow_only",
            "model_execution_permitted": False,
            "paid_llm_run": False,
            "true_full_chain_run": False,
            "runtime_cutover": False,
        },
        "fixed_input_sha256": {
            "configs/engineering_handoff/point01_m2_closeout_gate_manifest_v1_0.json": _sha256(MANIFEST_PATH),
            "scripts/engineering/run_point01_m2_closeout_gate.py": _sha256(Path(__file__).resolve()),
            "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md": _sha256(PLAN_PATH),
            **{relative: _sha256(ROOT / relative) for relative in RUNNERS.values()},
        },
        "boundary": "This gate completes only the no-model DecisionSurface Planning Shadow compiler slice. It does not authorize M3 comparison, M4 cutover, provider execution, Evidence/Writer or full-chain.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Point 01 M2 aggregate closeout gate.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--work-root", type=Path, default=None)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    if args.work_root:
        work_root = args.work_root if args.work_root.is_absolute() else ROOT / args.work_root
        result = build_result(work_root)
    else:
        with tempfile.TemporaryDirectory(prefix="point01_m2_closeout_") as directory:
            result = build_result(Path(directory))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"gate_status": result["gate_status"], "output": str(output), "unmet": result["unmet_closeout_conditions"]}, ensure_ascii=False))
    return 0 if result["gate_status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
