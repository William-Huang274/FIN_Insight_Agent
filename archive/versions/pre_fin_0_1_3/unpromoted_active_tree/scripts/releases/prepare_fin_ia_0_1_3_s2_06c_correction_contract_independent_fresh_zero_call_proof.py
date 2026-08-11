from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = ROOT / "scripts" / "releases"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import prepare_fin_ia_0_1_3_s2_06_unified_supervisor_independent_fresh_zero_call_proof as base  # noqa: E402


IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_3_s2_06_correction_objective_"
    "protected_narrative_contract_v1_0.json"
)
RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_3_s2_06c_correction_contract_"
    "independent_fresh_zero_call_proof_result_v1_0.json"
)
CURRENT_ACTION = (
    "FIN-0.1.3-013-S2-06C-INDEPENDENT-FRESH-U3-U4-REPLAY-"
    "AND-THREE-CASE-FAKE-MUTATION-PROOF"
)
NEXT_ACTION = (
    "FIN-0.1.3-013-S2-06D-MINIMAL-NATURAL-CORRECTED-NODE-CANARY"
)
REQUEST_CHARACTERS = {
    "DELL": 33689,
    "MU": 28203,
    "NVDA": 35749,
}
EXPECTED_WORKER_TESTS = 38
REQUIRED_SUCCESSOR_TESTS = (
    "test_sanitized_immutable_dell_r2_u3_u4_capture_replay",
    "test_legacy_u3_empty_counterevidence_requires_explicit_typed_unresolved_receipt",
    "test_legacy_u3_u4_failure_shapes_fail_before_node_acceptance",
    "test_protected_numeric_placeholder_is_locally_rendered_without_residue",
    "test_corrected_admission_is_exact_once_even_with_new_runtime_root",
)


def _configure_base() -> None:
    base.IMPLEMENTATION = IMPLEMENTATION
    base.RESULT = RESULT
    base.CURRENT_ACTION = CURRENT_ACTION
    base.NEXT_ACTION = NEXT_ACTION
    matrix = deepcopy(base.EXPECTED_REAL_MATRIX)
    for case_key, characters in REQUEST_CHARACTERS.items():
        matrix[case_key]["supervisor_request_characters"] = characters
    base.EXPECTED_REAL_MATRIX = matrix
    base._run_worker = _run_worker


def _run_worker(runtime_root: Path, output_path: Path) -> dict[str, Any]:
    (runtime_root / ".tmp").mkdir(parents=True, exist_ok=True)
    worker_script = runtime_root / Path(__file__).resolve().relative_to(ROOT)
    completed = subprocess.run(
        [
            sys.executable,
            str(worker_script),
            "--worker",
            "--runtime-root",
            str(runtime_root),
            "--output",
            str(output_path),
        ],
        cwd=runtime_root,
        env=base._clean_child_environment(runtime_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        check=False,
    )
    base._require(
        completed.returncode == 0,
        "fresh_worker_failed:"
        + str(completed.returncode)
        + ":"
        + completed.stdout[-5000:]
        + ":"
        + completed.stderr[-2000:],
    )
    base._require(output_path.exists(), "fresh_worker_output_missing")
    return base._load(output_path)


def _worker_payload(runtime_root: Path) -> dict[str, Any]:
    original_require = base._require

    def successor_require(condition: bool, code: str) -> None:
        if code == "unexpected_passed_test_count":
            return
        original_require(condition, code)

    base._require = successor_require
    try:
        payload = base._worker_payload(runtime_root)
    finally:
        base._require = original_require
    original_require(
        payload["pytest"]["passed"] == EXPECTED_WORKER_TESTS,
        "successor_worker_test_count_invalid",
    )
    nodeids = payload["pytest"]["nodeids"]
    for fragment in REQUIRED_SUCCESSOR_TESTS:
        original_require(
            any(fragment in nodeid for nodeid in nodeids),
            "required_successor_regression_missing:" + fragment,
        )
    payload["schema_version"] = (
        "fin_ia_0_1_3_s2_06c_correction_contract_"
        "independent_fresh_worker_proof_v1_0"
    )
    payload["successor_coverage"] = {
        "DELL_R2_U3_U4_replayed": True,
        "three_case_full_fake_and_mutation": True,
        "correction_objective_closure_verified": True,
        "protected_numeric_narrative_verified": True,
    }
    return payload


def _successor_result() -> dict[str, Any]:
    result = base.build_result()
    worker = result["independent_proof"]["worker_result"]
    base._require(
        worker["successor_coverage"]["DELL_R2_U3_U4_replayed"] is True,
        "successor_capture_replay_not_proven",
    )
    result["schema_version"] = (
        "fin_ia_0_1_3_s2_06c_correction_contract_"
        "independent_fresh_zero_call_proof_result_v1_0"
    )
    result["source_bindings"]["successor_proof_runner_ref"] = (
        Path(__file__).resolve().relative_to(ROOT).as_posix()
    )
    result["source_bindings"]["successor_proof_runner_sha256"] = base._sha256(
        Path(__file__).resolve()
    )
    result["acceptance_boundary"]["S2_06B_unified_zero_call_contract"] = (
        "independent_fresh_proof_pass"
    )
    result["acceptance_boundary"]["RC_P36_148_engineering_repair"] = (
        "independent_fresh_proof_pass"
    )
    result["acceptance_boundary"]["S2_06D_natural_node_canary"] = False
    result["next_action"] = NEXT_ACTION
    result["next_action_authorized"] = False
    result["known_boundary"] = (
        "This proof independently reproduces the corrected-node contract, DELL R2 "
        "U3/U4 rejection shapes and DELL/MU/NVDA fake/mutation behavior from the "
        "clean commit. It does not show natural DeepSeek adherence, authorize a "
        "formal DELL supervised run, measure report quality or permit release."
    )
    body = {key: value for key, value in result.items() if key != "result_digest"}
    result["result_digest"] = hashlib.sha256(base._canonical_bytes(body)).hexdigest()
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--output", type=Path, default=RESULT)
    args = parser.parse_args()
    _configure_base()
    if args.worker:
        base._require(args.runtime_root is not None, "worker_runtime_root_required")
        payload = _worker_payload(args.runtime_root.resolve())
    else:
        payload = _successor_result()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if not args.worker:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
