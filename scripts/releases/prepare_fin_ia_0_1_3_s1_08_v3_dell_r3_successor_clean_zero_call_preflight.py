from __future__ import annotations

import argparse
import compileall
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
from typing import Any, Mapping
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from scripts.releases.prepare_fin_ia_0_1_3_s1_08_v3_clean_independent_zero_call_proof import (  # noqa: E402
    _clean_child_environment,
    _extract_clean_archive,
    _inject_restricted_captures,
    _source_capture_manifest,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.project_os_preflight import run_project_os_preflight  # noqa: E402


RUN_SCOPE = "S1_08_V3_DELL_R3_SUCCESSOR_CLEAN_ZERO_CALL_PREFLIGHT"
RESULT_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_08_v3_dell_r3_"
    "successor_clean_zero_call_preflight_v1_0.json"
)
REPAIR_ARTIFACT_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_08_v3_dell_r3_"
    "successor_preflight_commit_lineage_and_test_selection_repair_v1_1.json"
)
IMPLEMENTATION_ARTIFACT_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_08_v3_dell_r3_"
    "successor_entrypoint_zero_call_implementation_v1_0.json"
)
DECISION_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_08_v3_dell_r3_"
    "fresh_live_authority_decision_v1_0.json"
)
V3_PROOF_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_08_v3_"
    "clean_independent_zero_call_proof_result_v1_0.json"
)
R2_RESULT_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_08_"
    "dell_current_search_r2_result_v1_0.json"
)
R2_QUALITY_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_08_"
    "dell_current_search_r2_source_quality_evaluation_v1_0.json"
)
CATALOG_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s1_08_"
    "current_source_catalog_relationship_budget_policy_v3_0.json"
)
R3_RESULT_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_08_v3_"
    "dell_current_search_r3_result_v1_0.json"
)
RUNTIME_PATH = ROOT / "src/sec_agent/s1_08_r3_successor.py"
RUNNER_PATH = ROOT / (
    "scripts/releases/run_fin_ia_0_1_3_s1_08_v3_"
    "dell_current_search_r3.py"
)
CONTRACT_TEST_PATH = ROOT / (
    "tests/contract/test_fin_0_1_3_s1_08_v3_"
    "dell_r3_successor.py"
)
EXPECTED_TESTS = 70
PYTEST_TARGETS = (
    "tests/contract/test_fin_0_1_3_s1_08_agentic_search_entry_audit.py",
    "tests/contract/test_fin_0_1_3_s1_08_candidate_generation_runtime.py",
    "tests/contract/test_fin_0_1_3_s1_08_dell_current_search_r1_terminal.py",
    "tests/contract/test_fin_0_1_3_s1_08_dell_r2_successor.py",
    "tests/contract/test_fin_0_1_3_s1_08_live_canary.py",
    "tests/contract/test_fin_0_1_3_s1_08_mature_component_v3_runtime.py",
    "tests/contract/test_fin_0_1_3_s1_08_quality_first_sourcehunter_capture_replay.py",
    "tests/contract/test_fin_0_1_3_s1_08_quality_first_sourcehunter_capture_replay_plan.py",
    "tests/contract/test_fin_0_1_3_s1_08_v3_dell_r3_fresh_live_authority_decision.py",
    "tests/contract/test_fin_0_1_3_s1_08_v3_dell_r3_successor.py",
)
REQUIRED_TEST_FRAGMENTS = (
    "test_R3_admission_binds_decision_R2_v3_sources_and_budget_without_secret",
    "test_R3_admission_or_bound_source_mutation_fails_closed",
    "test_missing_contact_stops_before_R3_ledger_consumption",
    "test_non_live_transport_stops_before_R3_ledger_consumption",
    "test_R3_exact_once_terminal_uses_v3_candidate_contract_and_fair_scheduler",
    "test_R3_runner_is_zero_call_until_explicit_main_and_cannot_reuse_R2",
)


class S108R3CleanPreflightError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S108R3CleanPreflightError(code)


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
        default=str,
    ).encode("utf-8")


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    _require(
        completed.returncode == 0,
        "git_command_failed:" + ":".join(args) + ":" + completed.stderr[-500:],
    )
    return completed.stdout.strip()


def _assert_clean_synced_head() -> dict[str, Any]:
    _require(not _git("status", "--porcelain"), "source_worktree_not_clean")
    head = _git("rev-parse", "HEAD")
    upstream = _git("rev-parse", "@{upstream}")
    _require(head == upstream, "source_head_not_synced_to_upstream")
    return {
        "commit": head,
        "upstream_commit": upstream,
        "branch": _git("branch", "--show-current"),
        "clean": True,
        "synced": True,
    }


def _verify_repair_artifact(root: Path) -> dict[str, str]:
    artifact_path = root / REPAIR_ARTIFACT_PATH.relative_to(ROOT)
    artifact = _load(artifact_path)
    _require(
        artifact.get("status")
        == "zero_call_repaired_clean_successor_preflight_pending",
        "repair_artifact_status_invalid",
    )
    observed: dict[str, str] = {}
    for binding in artifact.get("source_files") or []:
        relative = str(binding["path"])
        digest = _sha256(root / relative)
        _require(digest == binding["sha256"], f"repair_source_drift:{relative}")
        observed[relative] = digest
    previous = artifact.get("superseded_implementation_artifact") or {}
    previous_path = root / str(previous.get("path") or "")
    _require(
        previous_path.is_file() and _sha256(previous_path) == previous.get("sha256"),
        "superseded_implementation_artifact_binding_invalid",
    )
    return observed


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
    if str(runtime_root / "src") not in sys.path:
        sys.path.insert(0, str(runtime_root / "src"))
    network_attempts: list[str] = []

    def blocked_network(*args: Any, **kwargs: Any) -> Any:
        network_attempts.append("socket")
        raise RuntimeError("s1_08_r3_clean_preflight_network_forbidden")

    socket.socket.connect = blocked_network  # type: ignore[method-assign]
    socket.socket.connect_ex = blocked_network  # type: ignore[method-assign]
    socket.create_connection = blocked_network

    import pytest

    project_os = run_project_os_preflight(runtime_root, run_scope=RUN_SCOPE)
    _require(project_os.get("status") == "pass", "project_os_preflight_failed")
    _require(
        not (project_os.get("open_full_chain_blockers") or []),
        "project_os_preflight_has_blockers",
    )
    source_bindings = _verify_repair_artifact(runtime_root)
    compile_targets = (
        runtime_root / RUNTIME_PATH.relative_to(ROOT),
        runtime_root / RUNNER_PATH.relative_to(ROOT),
        runtime_root / CONTRACT_TEST_PATH.relative_to(ROOT),
        runtime_root / Path(__file__).resolve().relative_to(ROOT),
    )
    for path in compile_targets:
        _require(
            compileall.compile_file(str(path), quiet=1, force=True),
            f"compile_failed:{path.relative_to(runtime_root).as_posix()}",
        )

    plugin = _StablePytestResult()
    exit_code = pytest.main(
        ["-q", "--disable-warnings", *PYTEST_TARGETS],
        plugins=[plugin],
    )
    _require(exit_code == 0, f"pytest_failed:{exit_code}")
    _require(not plugin.failed, "pytest_reported_failure")
    _require(not plugin.skipped, "pytest_reported_skip")
    nodeids = sorted(plugin.passed)
    _require(len(nodeids) == EXPECTED_TESTS, "unexpected_passed_test_count")
    for fragment in REQUIRED_TEST_FRAGMENTS:
        _require(
            any(fragment in nodeid for nodeid in nodeids),
            f"required_test_missing:{fragment}",
        )
    _require(not network_attempts, "network_attempt_observed")
    _require(
        not (runtime_root / R3_RESULT_PATH.relative_to(ROOT)).exists(),
        "R3_result_exists_in_clean_archive",
    )
    _require(
        not (runtime_root / RESULT_PATH.relative_to(ROOT)).exists(),
        "successor_preflight_result_exists_in_source_commit",
    )
    return {
        "schema_version": (
            "fin_ia_0_1_3_s1_08_v3_dell_r3_"
            "successor_clean_zero_call_preflight_worker_v1_0"
        ),
        "status": "pass",
        "project_os_preflight": {
            "status": "pass",
            "run_scope": RUN_SCOPE,
            "open_full_chain_blocker_count": 0,
        },
        "source_bindings": source_bindings,
        "verification": {
            "compileall": "pass",
            "tests_passed": len(nodeids),
            "tests_failed": 0,
            "tests_skipped": 0,
            "pytest_nodeids_sha256": hashlib.sha256(
                "\n".join(nodeids).encode("utf-8")
            ).hexdigest(),
            "required_R3_contract_fragments": len(REQUIRED_TEST_FRAGMENTS),
            "explicit_test_files": len(PYTEST_TARGETS),
            "R3_result_absent": True,
        },
        "hard_boundaries": {
            "credential_values_present_or_read": 0,
            "network_attempts": 0,
            "model_calls": 0,
            "provider_calls": 0,
            "retry_calls": 0,
            "formal_admissions_issued": 0,
            "live_runs": 0,
        },
    }


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
        env=_clean_child_environment(runtime_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        check=False,
    )
    _require(
        completed.returncode == 0,
        "fresh_worker_failed:"
        + str(completed.returncode)
        + ":"
        + completed.stdout[-5000:]
        + ":"
        + completed.stderr[-3000:],
    )
    _require(output_path.exists(), "fresh_worker_output_missing")
    return _load(output_path)


def _authority_bindings() -> dict[str, Any]:
    decision = _load(DECISION_PATH)
    proof = _load(V3_PROOF_PATH)
    r2_result = _load(R2_RESULT_PATH)
    r2_quality = _load(R2_QUALITY_PATH)
    catalog = _load(CATALOG_PATH)
    implementation_files = dict(
        (proof.get("source_bindings") or {}).get("implementation_files") or {}
    )
    return {
        "authority_decision_sha256": _sha256(DECISION_PATH),
        "v3_proof_sha256": _sha256(V3_PROOF_PATH),
        "r2_result_sha256": _sha256(R2_RESULT_PATH),
        "r2_quality_evaluation_sha256": _sha256(R2_QUALITY_PATH),
        "catalog_sha256": _sha256(CATALOG_PATH),
        "v3_implementation_binding_digest": canonical_digest(implementation_files),
        "authority_decision_digest": canonical_digest(decision),
        "v3_proof_digest": canonical_digest(proof),
        "r2_result_digest": canonical_digest(r2_result),
        "r2_quality_evaluation_digest": canonical_digest(r2_quality),
        "catalog_digest": canonical_digest(catalog),
    }


def build_result() -> dict[str, Any]:
    git_state = _assert_clean_synced_head()
    _require(not RESULT_PATH.exists(), "successor_preflight_result_already_exists")
    _require(not R3_RESULT_PATH.exists(), "R3_result_already_exists")
    root_project_os = run_project_os_preflight(ROOT, run_scope=RUN_SCOPE)
    _require(root_project_os.get("status") == "pass", "root_project_os_preflight_failed")
    root_source_bindings = _verify_repair_artifact(ROOT)
    restricted_inputs_before = _source_capture_manifest()

    with tempfile.TemporaryDirectory(prefix="fin013-s1-08-r3-clean-preflight-") as parent:
        parent_path = Path(parent).resolve()
        runtime_root = parent_path / "clean-archive"
        _extract_clean_archive(git_state["commit"], runtime_root)
        injected_manifest = _inject_restricted_captures(runtime_root)
        worker_output = runtime_root / "worker-result.json"
        worker = _run_worker(runtime_root, worker_output)

    restricted_inputs_after = _source_capture_manifest()
    _require(
        restricted_inputs_before == restricted_inputs_after,
        "restricted_inputs_changed_during_preflight",
    )
    _require(
        worker.get("source_bindings") == root_source_bindings,
        "clean_archive_source_bindings_differ",
    )
    _require(not _git("status", "--porcelain"), "worktree_changed_during_preflight")

    body = {
        "schema_version": (
            "fin_ia_0_1_3_s1_08_v3_dell_r3_"
            "successor_clean_zero_call_preflight_v1_0"
        ),
        "recorded_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(
            timespec="seconds"
        ),
        "stage": "013-S1-08-P2C",
        "status": "pass",
        "proof_attempt_history": [
            {
                "attempt_id": "S1-08-V3-DELL-R3-CLEAN-PREFLIGHT-A1",
                "source_commit": "04e439bfd1e3f6e248cc6dea2b49789105d48f57",
                "status": "failed_before_result_materialization",
                "failure_code": "pytest_broad_collection_imported_unrelated_contract_resources",
                "reproduced_invocations": 2,
                "observed_collection_errors": 144,
                "disposition": (
                    "Retained as a proof-runner test-selection failure. The repair "
                    "uses the ten explicit S1-08 contract files; Runtime, authority, "
                    "network and formal admission behavior were not changed."
                ),
            }
        ],
        "source_commit": git_state["commit"],
        "source_branch": git_state["branch"],
        "project_os_preflight": {
            "run_scope": RUN_SCOPE,
            "status": "pass",
            "allow_open_blockers": False,
            "open_full_chain_blocker_count": 0,
        },
        "source_files": {
            "runtime": RUNTIME_PATH.relative_to(ROOT).as_posix(),
            "runtime_sha256": _sha256(RUNTIME_PATH),
            "runner": RUNNER_PATH.relative_to(ROOT).as_posix(),
            "runner_sha256": _sha256(RUNNER_PATH),
            "contract_test": CONTRACT_TEST_PATH.relative_to(ROOT).as_posix(),
            "contract_test_sha256": _sha256(CONTRACT_TEST_PATH),
            "preflight_runner": Path(__file__).resolve().relative_to(ROOT).as_posix(),
            "preflight_runner_sha256": _sha256(Path(__file__).resolve()),
        },
        "authority_bindings": _authority_bindings(),
        "verification": {
            "clean_git_archive": True,
            "fresh_python_process": True,
            "distinct_disposable_roots": 1,
            "restricted_R1_request_objects_injected": len(
                injected_manifest["R1_request_objects"]
            ),
            "restricted_R2_content_objects_injected": len(
                injected_manifest["R2_content_objects"]
            ),
            "restricted_inputs_unchanged": True,
            "compileall": worker["verification"]["compileall"],
            "tests_passed": worker["verification"]["tests_passed"],
            "tests_failed": worker["verification"]["tests_failed"],
            "tests_skipped": worker["verification"]["tests_skipped"],
            "pytest_nodeids_sha256": worker["verification"][
                "pytest_nodeids_sha256"
            ],
            "decision_R2_v3_catalog_source_and_commit_mutations": "fail_closed",
            "proven_source_commit_ancestry_and_runtime_tree_guard": "pass",
            "R3_result_absent": True,
            "external_calls": 0,
            "admissions_issued": 0,
        },
        "decision": {
            "successor_clean_preflight": "pass",
            "formal_admission_issued": False,
            "DELL_R3_executed": False,
            "exact_live_scope_projected": False,
            "MU_NVDA_ranking_DeepSeek_S3_authorized": [
                False,
                False,
                False,
                False,
                False,
            ],
        },
        "observed_counts": {
            "network_calls": 0,
            "model_calls": 0,
            "provider_calls": 0,
            "retry_calls": 0,
            "formal_admissions_issued": 0,
            "live_runs": 0,
        },
        "current_next": (
            "S1_08_V3_DELL_R3_EXACT_LIVE_ISSUANCE_"
            "AUTHORITY_PROJECTION_DECISION"
        ),
        "next_action_authorized": False,
        "known_boundary": (
            "This clean-archive/fresh-process proof establishes the R3 successor "
            "entrypoint, exact source and authority bindings, mutation behavior and "
            "zero-call exact-once contract only. It does not issue an admission, "
            "access a source, prove candidate quality, admit ranking, run DeepSeek, "
            "close S1-08 or authorize the next action."
        ),
    }
    return {**body, "result_digest": canonical_digest(body)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--output", type=Path, default=RESULT_PATH)
    args = parser.parse_args()
    if args.worker:
        _require(args.runtime_root is not None, "worker_runtime_root_required")
        payload = _worker_payload(args.runtime_root.resolve())
    else:
        payload = build_result()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    if not args.worker:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
