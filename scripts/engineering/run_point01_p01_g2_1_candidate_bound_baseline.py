"""Default-deny entrypoint for a reviewed candidate-bound P01-G2.1 baseline.

This runner never chooses a historical package.  It receives the frozen outer
bridge package and validates its derived v2.10 package before delegating the
only mutable execution lifecycle to the accepted v2.10 production kernel.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from sec_agent.canonical_runtime.m2_a1_execution_receipt import (
    ProductionHumanJITWindowApprovalV2_10,
    ProductionReviewerDecisionReceiptV2_10,
    preflight_exact_execution,
    validate_production_human_jit_window_approval_v2_10,
)
from sec_agent.canonical_runtime.m2_a1_v2_10_execution_proof import execute_approved_window_kernel, make_production_v2_10_adapter
from sec_agent.canonical_runtime.p01_g2_1_candidate_execution_bridge import preflight_candidate_bound_execution, validate_execution_package


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"candidate_bound_mapping_required:{path.name}")
    return value


def _relative_artifacts(package: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    paths = package.get("derived_artifact_paths")
    if not isinstance(paths, Mapping):
        raise ValueError("candidate_bound_paths_invalid")
    return {name: _load(ROOT / str(relative)) for name, relative in paths.items()}


def verify_frozen_bridge(package_path: Path, *, expected_digest: str) -> dict[str, Any]:
    package = _load(package_path)
    if package.get("package_digest") != expected_digest:
        raise ValueError("candidate_bound_expected_package_digest_mismatch")
    artifacts = _relative_artifacts(package)
    candidate_paths = {
        "manifest": ROOT / "data/manifests/point01_p01_g2_1_final_baseline_candidate_input_manifest_v1_0.json",
        "package": ROOT / "data/manifests/point01_p01_g2_1_final_baseline_candidate_package_v1_0.json",
        "preflight": ROOT / "data/manifests/point01_p01_g2_1_final_baseline_candidate_preflight_v1_0.json",
        "gate": ROOT / "data/manifests/point01_p01_g2_1_final_baseline_candidate_gate_v1_0.json",
    }
    candidate = {name: _load(path) for name, path in candidate_paths.items()}
    preflight = preflight_candidate_bound_execution(package, repository_root=ROOT, manifest=candidate["manifest"], candidate=candidate["package"], candidate_preflight=candidate["preflight"], candidate_gate=candidate["gate"], inner_package=artifacts["inner_package"], inner_package_gate=artifacts["inner_package_gate"], plan=artifacts["plan"], plan_gate=artifacts["plan_gate"], blueprint=artifacts["blueprint"], blueprint_gate=artifacts["blueprint_gate"], index_reader=lambda root, relative: __import__("subprocess").run(["git", "show", f":{relative}"], cwd=root, capture_output=True, check=True).stdout)
    if preflight["status"] != "pass":
        raise ValueError(f"candidate_bound_preflight_failed:{preflight['verification']['errors']}")
    return {"status": "pass", "package_digest": package["package_digest"], "preflight": preflight, "execution_counts": package["execution_counts"]}


def execute_approved_window(package_path: Path, *, expected_digest: str, approval_path: Path, reviewer_receipt_path: Path) -> Any:
    """Explicit future-only path: validates the bridge then invokes the existing v2.10 kernel."""

    verified = verify_frozen_bridge(package_path, expected_digest=expected_digest)
    package = _load(package_path)
    artifacts = _relative_artifacts(package)
    approval = ProductionHumanJITWindowApprovalV2_10.model_validate(_load(approval_path))
    reviewer_receipt = ProductionReviewerDecisionReceiptV2_10.model_validate(_load(reviewer_receipt_path))
    context, check = validate_production_human_jit_window_approval_v2_10(approval, reviewer_receipt=reviewer_receipt, package=artifacts["inner_package"], package_gate=artifacts["inner_package_gate"], plan=artifacts["plan"], plan_gate=artifacts["plan_gate"], blueprint=artifacts["blueprint"], blueprint_gate=artifacts["blueprint_gate"])
    if context is None or check.get("status") != "pass":
        raise ValueError("candidate_bound_production_authority_invalid")
    jit_path = ROOT / "scripts/engineering/run_point01_m2_a1_v2_10_frozen_jit_window.py"
    spec = importlib.util.spec_from_file_location("candidate_bound_v2_10_jit", jit_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("candidate_bound_v2_10_jit_unavailable")
    jit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(jit)
    admission, receipt = jit._issue_authority(approval, artifacts["inner_package"])
    preflight = preflight_exact_execution(artifacts["inner_package"], admission, repository_root=ROOT, receipt_id=receipt.receipt_id, scenario_id=package["baseline_contract"]["scenario_id"], human_approval_digest=approval.approval_digest)
    corpus = json.loads((ROOT / artifacts["inner_package"]["execution_preflight"]["runtime_inputs"]["corpus"]["relative_path"]).read_text(encoding="utf-8"))
    matrix = json.loads((ROOT / artifacts["inner_package"]["execution_preflight"]["runtime_inputs"]["scenario_matrix"]["relative_path"]).read_text(encoding="utf-8"))
    oracle = json.loads((ROOT / "configs/engineering_handoff/point01_m2_a1_independent_expected_cell_oracle_v1_1.json").read_text(encoding="utf-8"))
    input_ref = package["baseline_contract"]["input_ref"]
    scenario_id = package["baseline_contract"]["scenario_id"]
    oracle_case = next(item for item in oracle["oracle_cases"] if item["input_case_ref"] == input_ref)
    scenario = next(item for item in matrix["scenarios"] if item["scenario_id"] == scenario_id)
    parent = ROOT / "scripts/engineering/run_point01_m2_a1_actual_audit_v2_10.py"
    return execute_approved_window_kernel(adapter=make_production_v2_10_adapter(authority_context=context, package=artifacts["inner_package"], admission=admission, receipt=receipt, preflight=preflight, oracle_case=oracle_case, scenario=scenario, parent=parent))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Default-deny candidate-bound P01-G2.1 final baseline runner.")
    parser.add_argument("--executable-package", type=Path, required=True)
    parser.add_argument("--expected-package-digest", required=True)
    parser.add_argument("--verify-frozen-bridge", action="store_true")
    parser.add_argument("--execute-approved-window", action="store_true")
    parser.add_argument("--approval", type=Path)
    parser.add_argument("--reviewer-receipt", type=Path)
    args = parser.parse_args(argv)
    if args.verify_frozen_bridge and not args.execute_approved_window:
        print(json.dumps(verify_frozen_bridge(args.executable_package, expected_digest=args.expected_package_digest), sort_keys=True))
        return 0
    if not args.execute_approved_window:
        print(json.dumps({"status": "candidate_bound_execution_authority_required", "side_effects": 0}, sort_keys=True))
        return 2
    if args.approval is None or args.reviewer_receipt is None:
        print(json.dumps({"status": "candidate_bound_approval_and_reviewer_receipt_required", "side_effects": 0}, sort_keys=True))
        return 2
    result = execute_approved_window(args.executable_package, expected_digest=args.expected_package_digest, approval_path=args.approval, reviewer_receipt_path=args.reviewer_receipt)
    print(json.dumps({"state": result.state, "terminal_digest": result.terminal_digest}, sort_keys=True))
    return 0 if result.state == "succeeded" else 2


if __name__ == "__main__":
    raise SystemExit(main())
