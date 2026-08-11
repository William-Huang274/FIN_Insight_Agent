from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
from typing import Any, Mapping
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[2]
AUTHORITY = ROOT / (
    "configs/releases/fin_ia_0_1_s4_shared_runtime_deterministic_fact_"
    "candidate_pool_planner_independent_fresh_agent_proof_authority_"
    "decision_v1_0.json"
)
RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_s4_shared_runtime_deterministic_fact_"
    "candidate_pool_planner_independent_fresh_agent_proof_result_v1_0.json"
)
TARGET_RUNTIME_ROOT = ROOT / (
    ".codex_runtime/"
    "fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1/"
    "canonical-runtime"
)
CURRENT_ACTION = (
    "S4-SHARED-RUNTIME-DETERMINISTIC-FACT-CANDIDATE-POOL-PLANNER-"
    "INDEPENDENT-FRESH-AGENT-PROOF"
)
NEXT_ACTION = (
    "S4-T06-POST-FACT-CANDIDATE-POOL-INDEPENDENT-PROOF-"
    "FINAL-PRODUCT-REPROOF-DISPOSITION-DECISION"
)
COPY_TREES = (
    "apps/workbench/backend",
    "src",
    "tests/contract",
    "configs/releases",
    "scripts",
)
COPY_FILES = ("pyproject.toml", "requirements.txt", "requirements-workbench.txt")
SCRUBBED_ENVIRONMENT_NAMES = (
    "DEEPSEEK_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_API_KEY",
    "GEMINI_API_KEY",
    "EDINET_API_KEY",
)
PYTEST_TARGETS = (
    "tests/contract/"
    "test_fin_0_1_s4_shared_runtime_deterministic_fact_candidate_pool_"
    "planner_minimum_zero_call_implementation.py",
    "tests/contract/"
    "test_fin_0_1_s4_t06_mu_deterministic_judgment_atom_planner_"
    "compiled_contract_implementation.py::"
    "test_downstream_failure_preserves_all_prior_and_failing_capture",
    "tests/contract/"
    "test_fin_0_1_s4_t06_mu_case_runtime_mandatory_material_truth_"
    "identity_safety_closure_zero_call_implementation.py::"
    "test_final_mu_artifact_envelope_rejects_projection_numeric_and_"
    "identity_mutations",
    "tests/contract/"
    "test_fin_0_1_s4_t06_mu_temporal_authority_and_terminal_result_"
    "zero_call_implementation.py::"
    "test_runner_uses_admission_bound_capture_v2_and_materializes_"
    "failure_result",
)


class IndependentFactCandidatePoolProofError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise IndependentFactCandidatePoolProofError(code)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _tree_digest(path: Path) -> str:
    digest = hashlib.sha256()
    if not path.exists():
        digest.update(b"<absent>")
        return digest.hexdigest()
    if path.is_file():
        digest.update(b"file\0")
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        return digest.hexdigest()
    for child in sorted(row for row in path.rglob("*") if row.is_file()):
        digest.update(child.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(child.stat().st_size).encode("ascii"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(child.read_bytes()).digest())
    return digest.hexdigest()


def _target_snapshot() -> dict[str, Any]:
    database = TARGET_RUNTIME_ROOT / "canonical.sqlite"
    objects = TARGET_RUNTIME_ROOT / "objects"
    return {
        "target_runtime_root_exists": TARGET_RUNTIME_ROOT.exists(),
        "canonical_database_exists": database.exists(),
        "canonical_database_sha256": (
            _sha256(database) if database.exists() else None
        ),
        "canonical_object_tree_exists": objects.exists(),
        "canonical_object_tree_sha256": _tree_digest(objects),
    }


def _verify_frozen_bindings(
    root: Path,
    authority: Mapping[str, Any],
) -> dict[str, str]:
    observed: dict[str, str] = {}
    for relative_path, expected in authority["frozen_current_bindings"].items():
        current = _sha256(root / relative_path)
        _require(
            current == expected,
            f"frozen_binding_drift:{relative_path}",
        )
        observed[str(relative_path)] = current
    implementation = authority["source_evidence"]
    implementation_digest = _sha256(root / implementation["implementation_ref"])
    _require(
        implementation_digest == implementation["implementation_sha256"],
        "implementation_binding_drift",
    )
    observed[str(implementation["implementation_ref"])] = (
        implementation_digest
    )
    return observed


def _copy_disposable_runtime(source: Path, target: Path) -> None:
    ignore = shutil.ignore_patterns(
        "__pycache__",
        "*.pyc",
        "*.pyo",
        ".pytest_cache",
        ".mypy_cache",
    )
    for relative_path in COPY_TREES:
        source_path = source / relative_path
        target_path = target / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source_path, target_path, ignore=ignore)
    for relative_path in COPY_FILES:
        source_path = source / relative_path
        if source_path.exists():
            shutil.copy2(source_path, target / relative_path)


class _StablePytestResult:
    def __init__(self) -> None:
        self.passed: list[str] = []
        self.failed: list[str] = []
        self.skipped: list[str] = []

    def pytest_runtest_logreport(self, report: Any) -> None:
        if report.when != "call":
            return
        if report.passed:
            self.passed.append(str(report.nodeid))
        elif report.failed:
            self.failed.append(str(report.nodeid))
        elif report.skipped:
            self.skipped.append(str(report.nodeid))


def _worker_payload(runtime_root: Path) -> dict[str, Any]:
    sys.path.insert(0, str(runtime_root))
    sys.path.insert(0, str(runtime_root / "src"))
    sys.path.insert(0, str(runtime_root / "tests" / "contract"))

    network_attempts: list[str] = []

    def _blocked_connect(*args: Any, **kwargs: Any) -> Any:
        network_attempts.append("socket.connect")
        raise RuntimeError("independent_proof_network_disabled")

    def _blocked_connect_ex(*args: Any, **kwargs: Any) -> Any:
        network_attempts.append("socket.connect_ex")
        raise RuntimeError("independent_proof_network_disabled")

    def _blocked_create_connection(*args: Any, **kwargs: Any) -> Any:
        network_attempts.append("socket.create_connection")
        raise RuntimeError("independent_proof_network_disabled")

    socket.socket.connect = _blocked_connect  # type: ignore[method-assign]
    socket.socket.connect_ex = _blocked_connect_ex  # type: ignore[method-assign]
    socket.create_connection = _blocked_create_connection

    import pytest

    authority = _load(runtime_root / AUTHORITY.relative_to(ROOT))
    observed_bindings = _verify_frozen_bindings(runtime_root, authority)
    plugin = _StablePytestResult()
    exit_code = pytest.main(
        ["-q", "--disable-warnings", *PYTEST_TARGETS],
        plugins=[plugin],
    )
    _require(exit_code == 0, f"pytest_failed:{exit_code}")
    _require(not plugin.failed, "pytest_reported_failure")
    _require(not plugin.skipped, "pytest_reported_skip")
    _require(len(plugin.passed) == 20, "unexpected_passed_test_count")
    _require(not network_attempts, "network_attempt_observed")

    nodeids = sorted(plugin.passed)
    required_node_fragments = (
        "test_catalog_cardinality_is_bounded_before_provider",
        "test_zero_catalog_fails_closed_before_provider",
        "test_catalog_permutation_has_identical_pool_and_digest",
        "test_unknown_and_overlapping_semantic_roles_fail_closed",
        "test_profile_scope_minimum_and_registry_digest_fail_closed",
        "test_mu_value_cell_exposes_six_of_twenty_two_and_accepts_all_six",
        "test_hidden_duplicate_and_seventh_provider_candidates_fail_closed",
        "test_pre_provider_profile_fault_is_typed_and_makes_zero_calls",
        "test_three_case_zero_call_full_chain_remains_6_12_12_9",
        "test_downstream_failure_preserves_all_prior_and_failing_capture",
        "test_final_mu_artifact_envelope_rejects_projection_numeric_and_identity_mutations",
        "test_runner_uses_admission_bound_capture_v2_and_materializes_failure_result",
    )
    for fragment in required_node_fragments:
        _require(
            any(fragment in nodeid for nodeid in nodeids),
            f"required_test_missing:{fragment}",
        )

    profile_set = _load(
        runtime_root
        / "configs/releases/fin_ia_0_1_s4_fact_candidate_pool_profiles_v1_0.json"
    )
    return {
        "schema_version": (
            "fin_ia_0_1_s4_fact_candidate_pool_independent_worker_proof_v1"
        ),
        "proof_package_id": CURRENT_ACTION,
        "frozen_bindings": observed_bindings,
        "profile_set_contract_digest": profile_set["profile_set_digest"],
        "registered_profile_cell_pairs": len(profile_set["profiles"]),
        "pytest": {
            "passed": len(nodeids),
            "failed": 0,
            "skipped": 0,
            "passed_nodeids": nodeids,
        },
        "verified_matrix": {
            "candidate_catalog_counts": [0, 1, 3, 6, 7, 22],
            "eligible_at_most_six_preserved": True,
            "eligible_over_six_visible_count": 6,
            "provider_returning_all_six_visible_candidates_valid": True,
            "local_final_selected_maximum": 3,
            "permutation_stable": True,
            "DELL_MU_NVDA_each": [6, 12, 12, 9],
            "downstream_failure_capture_sequences": [10, 11, 12],
            "terminal_result_materialized": True,
            "numeric_identity_manifest_trace_mutations_fail_closed": True,
            "pre_provider_failure_provider_calls": 0,
            "public_failure_telemetry_contains_raw_fact_or_numeric": False,
        },
        "network_attempts": 0,
        "model_provider_network_source_external_tool_calls": [0, 0, 0, 0, 0],
        "target_business_writes": 0,
    }


def _run_worker(runtime_root: Path, output_path: Path) -> dict[str, Any]:
    worker_script = runtime_root / Path(__file__).resolve().relative_to(ROOT)
    temp_path = runtime_root / ".worker_tmp"
    cache_path = runtime_root / ".worker_pycache"
    temp_path.mkdir(parents=True, exist_ok=True)
    cache_path.mkdir(parents=True, exist_ok=True)
    python_command = subprocess.list2cmdline(
        [
            sys.executable,
            str(worker_script),
            "--worker",
            "--runtime-root",
            str(runtime_root),
            "--output",
            str(output_path),
        ]
    )
    environment_prefix = "".join(
        f'set "{name}="&&' for name in SCRUBBED_ENVIRONMENT_NAMES
    )
    environment_prefix += (
        'set "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1"&&'
        'set "LLM_GATEWAY_TRANSPORT_RETRIES=0"&&'
        f'set "TMP={temp_path}"&&'
        f'set "TEMP={temp_path}"&&'
        f'set "PYTHONPYCACHEPREFIX={cache_path}"&&'
    )
    completed = subprocess.run(
        ["cmd.exe", "/d", "/s", "/c", environment_prefix + python_command],
        cwd=runtime_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        check=False,
    )
    _require(
        completed.returncode == 0,
        "disposable_worker_failed:"
        f"{completed.returncode}:"
        f"{completed.stdout[-500:]}:"
        f"{completed.stderr[-500:]}",
    )
    _require(output_path.exists(), "disposable_worker_output_missing")
    return _load(output_path)


def build_result() -> dict[str, Any]:
    authority = _load(AUTHORITY)
    _require(
        authority["decision_id"]
        == (
            "S4-SHARED-RUNTIME-DETERMINISTIC-FACT-CANDIDATE-POOL-"
            "PLANNER-INDEPENDENT-FRESH-AGENT-PROOF-DECISION"
        ),
        "authority_identity_mismatch",
    )
    _require(
        authority["authority"]["future_independent_zero_call_proof_authorized"]
        is True,
        "proof_not_authorized",
    )
    _require(
        authority["authority"]["maximum_future_proof_packages"] == 1,
        "proof_package_ceiling_mismatch",
    )
    _require(
        authority["authority"]["required_independent_disposable_runtime_invocations"]
        == 2,
        "proof_invocation_count_mismatch",
    )
    source_bindings_before = _verify_frozen_bindings(ROOT, authority)
    target_before = _target_snapshot()

    worker_payloads: list[dict[str, Any]] = []
    worker_payload_bytes: list[bytes] = []
    with tempfile.TemporaryDirectory(
        prefix="fin01-s4-fact-candidate-pool-independent-proof-"
    ) as parent:
        parent_path = Path(parent)
        runtime_roots = [parent_path / "runtime-a", parent_path / "runtime-b"]
        for index, runtime_root in enumerate(runtime_roots, start=1):
            _copy_disposable_runtime(ROOT, runtime_root)
            output_path = runtime_root / f"worker-result-{index}.json"
            payload = _run_worker(runtime_root, output_path)
            worker_payloads.append(payload)
            worker_payload_bytes.append(_canonical_bytes(payload))
        _require(
            runtime_roots[0] != runtime_roots[1],
            "disposable_runtime_roots_not_distinct",
        )
        _require(
            worker_payload_bytes[0] == worker_payload_bytes[1],
            "independent_normalized_outputs_differ",
        )

    target_after = _target_snapshot()
    _require(target_before == target_after, "target_runtime_state_changed")
    source_bindings_after = _verify_frozen_bindings(ROOT, authority)
    _require(
        source_bindings_before == source_bindings_after,
        "source_binding_changed_during_proof",
    )
    worker_digest = hashlib.sha256(worker_payload_bytes[0]).hexdigest()
    return {
        "schema_version": (
            "fin_ia_0_1_s4_shared_runtime_deterministic_fact_candidate_"
            "pool_planner_independent_fresh_agent_proof_result_v1_0"
        ),
        "proof_id": CURRENT_ACTION,
        "recorded_at": datetime.now(
            ZoneInfo("Asia/Shanghai")
        ).isoformat(timespec="seconds"),
        "status": (
            "pass_zero_call_two_independent_disposable_runtime_outputs_"
            "byte_equal_full_matrix_and_target_read_only_proven"
        ),
        "authority": {
            "ref": AUTHORITY.relative_to(ROOT).as_posix(),
            "sha256": _sha256(AUTHORITY),
            "user_instruction": "继续",
            "proof_packages_authorized": 1,
            "proof_packages_executed": 1,
            "automatic_follow_on_packages": 0,
        },
        "proof_generator": {
            "ref": Path(__file__).resolve().relative_to(ROOT).as_posix(),
            "sha256": _sha256(Path(__file__).resolve()),
            "independent_invocations": 2,
            "fresh_python_processes": 2,
            "separate_disposable_runtime_roots": 2,
            "temporary_runtime_roots_removed": True,
        },
        "source_binding_audit": {
            "before": source_bindings_before,
            "after": source_bindings_after,
            "unchanged": True,
        },
        "independent_proof": {
            "normalized_outputs_equal": True,
            "normalized_output_sha256": worker_digest,
            "worker_result": worker_payloads[0],
            "worker_test_results": ["20 passed", "20 passed"],
        },
        "target_read_only_audit": {
            "before": target_before,
            "after": target_after,
            "unchanged": True,
            "target_writes": 0,
        },
        "observed_counts": {
            "credential_presence_or_value_reads": 0,
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": 0,
            "source_calls": 0,
            "external_tool_calls": 0,
            "target_WorkUnit_Attempt_Run_business_Artifact_writes": 0,
            "admissions_issued_or_consumed": 0,
            "exact_live_runs": 0,
            "paired_assessments": 0,
            "owner_acceptances": 0,
            "T07_entries": 0,
        },
        "stage_acceptance": {
            "RC_P36_084": (
                "independent_zero_call_current_binding_proof_pass_"
                "project_level_disposition_pending"
            ),
            "RC_P36_080": "open_final_formal_nine_Artifact_L1_not_achieved",
            "S4_T06": "engineering_pass_live_product_blocked_not_closed",
            "paired_assessment": "not_eligible_not_performed",
            "owner_acceptance": "not_eligible_not_performed",
            "S4_T07": "not_entered",
            "S4": "not_passed",
            "S5": "blocked",
        },
        "next_action": NEXT_ACTION,
        "next_action_authorized": False,
        "known_boundary": (
            "Independent zero-call reproducibility passed. This result does "
            "not close RC-P36-084 and authorizes no runtime repair credential "
            "model Provider network source admission exact-live paired owner "
            "T06 closeout or T07 operation. The next project-level product "
            "reproof disposition requires separate authority."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--output", type=Path, default=RESULT)
    args = parser.parse_args()
    if args.worker:
        _require(args.runtime_root is not None, "worker_runtime_root_required")
        payload = _worker_payload(args.runtime_root.resolve())
    else:
        payload = build_result()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    if not args.worker:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
