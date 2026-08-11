from __future__ import annotations

import argparse
import compileall
from datetime import datetime
import hashlib
import json
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
from sec_agent.s1_08_r3_successor import PREDECESSOR_PREFLIGHT_SHA256  # noqa: E402


RUN_SCOPE = (
    "FIN_0_1_3_S0_04G_TYPED_BLOCKER_STATE_AND_RUN_SCOPE_REGISTRY_"
    "MINIMUM_ZERO_CALL_IMPLEMENTATION"
)
DIRECT_R3_SCOPE = "S1_08_V3_DELL_R3_EXACT_LIVE_ISSUANCE_AND_EXECUTION"
RESULT_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_08_v3_dell_r3_"
    "successor_clean_zero_call_preflight_v1_2.json"
)
PREDECESSOR_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_08_v3_dell_r3_"
    "successor_clean_zero_call_preflight_v1_1.json"
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
RUNTIME_PATH = ROOT / "src/sec_agent/s1_08_r3_successor.py"
RUNNER_PATH = ROOT / (
    "scripts/releases/run_fin_ia_0_1_3_s1_08_v3_"
    "dell_current_search_r3.py"
)
R3_RESULT_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_08_v3_"
    "dell_current_search_r3_result_v1_0.json"
)
PREDECESSOR_SOURCE_COMMIT = "2f14684e60acf7b6def92498eb2bd68c4428d87a"
EXPECTED_CHANGED_RUNTIME_FILES = {
    "scripts/releases/prepare_fin_ia_0_1_3_s0_04g_r3_downstream_compatibility_requalification.py",
    "scripts/releases/run_fin_ia_0_1_3_s1_08_v3_dell_current_search_r3.py",
    "src/sec_agent/s1_08_r3_successor.py",
    "tests/contract/test_fin_0_1_3_s0_04g_typed_blocker_state_and_run_scope_registry.py",
    "tests/contract/test_fin_0_1_3_s1_08_v3_dell_r3_successor.py",
}
PYTEST_TARGETS = (
    "tests/test_project_os_preflight.py",
    "tests/contract/test_fin_0_1_3_s0_04g_typed_blocker_state_and_run_scope_registry.py",
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
EXPECTED_TESTS = 85
REQUIRED_TEST_FRAGMENTS = (
    "test_unknown_requested_scope_fails_closed_and_override_cannot_bypass",
    "test_post_adoption_projection_requires_typed_state_registry_and_lineage",
    "test_current_S0_04G_scope_uses_typed_registry_and_passes",
    "test_direct_R3_scope_matches_latest_typed_product_projection",
    "test_R3_admission_binds_decision_R2_v3_sources_and_budget_without_secret",
    "test_R3_exact_once_terminal_uses_v3_candidate_contract_and_fair_scheduler",
)


class S004GRequalificationError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S004GRequalificationError(code)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def _verify_predecessor_and_v3_bindings(root: Path) -> dict[str, Any]:
    predecessor_path = root / PREDECESSOR_PATH.relative_to(ROOT)
    predecessor = _load(predecessor_path)
    _require(
        _sha256(predecessor_path) == PREDECESSOR_PREFLIGHT_SHA256,
        "predecessor_preflight_sha256_drift",
    )
    _require(
        predecessor.get("source_commit") == PREDECESSOR_SOURCE_COMMIT,
        "predecessor_source_commit_invalid",
    )
    _require(predecessor.get("status") == "pass", "predecessor_status_invalid")
    proof = _load(root / V3_PROOF_PATH.relative_to(ROOT))
    bindings = dict((proof.get("source_bindings") or {}).get("implementation_files") or {})
    _require(bool(bindings), "v3_implementation_bindings_missing")
    observed = {ref: _sha256(root / ref) for ref in bindings}
    _require(observed == bindings, "v3_implementation_source_drift")
    return {
        "predecessor_sha256": PREDECESSOR_PREFLIGHT_SHA256,
        "predecessor_source_commit": PREDECESSOR_SOURCE_COMMIT,
        "v3_implementation_binding_digest": canonical_digest(bindings),
    }


def _worker_payload(runtime_root: Path) -> dict[str, Any]:
    if str(runtime_root / "src") not in sys.path:
        sys.path.insert(0, str(runtime_root / "src"))
    network_attempts: list[str] = []

    def blocked_network(*args: Any, **kwargs: Any) -> Any:
        network_attempts.append("socket")
        raise RuntimeError("s0_04g_requalification_network_forbidden")

    socket.socket.connect = blocked_network  # type: ignore[method-assign]
    socket.socket.connect_ex = blocked_network  # type: ignore[method-assign]
    socket.create_connection = blocked_network

    import pytest

    project_os = run_project_os_preflight(runtime_root, run_scope=RUN_SCOPE)
    _require(project_os.get("status") == "pass", "project_os_preflight_failed")
    _require(project_os.get("contract_errors") == [], "project_os_contract_errors")
    _require(
        (project_os.get("run_scope_registry") or {}).get("registry_version") == "v1_0",
        "run_scope_registry_version_invalid",
    )
    direct_r3 = run_project_os_preflight(runtime_root, run_scope=DIRECT_R3_SCOPE)
    _require(direct_r3.get("status") == "blocked", "direct_R3_unexpectedly_open")
    _require(
        any(
            str(item.get("issue_id") or "").startswith("RC-P36-157-")
            for item in direct_r3.get("open_full_chain_blockers") or []
        ),
        "direct_R3_product_blocker_missing",
    )
    binding_summary = _verify_predecessor_and_v3_bindings(runtime_root)
    for relative in EXPECTED_CHANGED_RUNTIME_FILES:
        path = runtime_root / relative
        _require(path.is_file(), f"changed_runtime_file_missing:{relative}")
        if path.suffix == ".py":
            _require(
                compileall.compile_file(str(path), quiet=1, force=True),
                f"compile_failed:{relative}",
            )

    plugin = _StablePytestResult()
    exit_code = pytest.main(
        ["-q", "--disable-warnings", *PYTEST_TARGETS], plugins=[plugin]
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
        not (runtime_root / RESULT_PATH.relative_to(ROOT)).exists(),
        "v1_2_result_exists_in_source_commit",
    )
    _require(
        not (runtime_root / R3_RESULT_PATH.relative_to(ROOT)).exists(),
        "R3_result_exists_in_source_commit",
    )
    return {
        "status": "pass",
        "project_os_preflight": {
            "schema_version": project_os["schema_version"],
            "status": "pass",
            "run_scope": RUN_SCOPE,
            "registry_version": project_os["run_scope_registry"]["registry_version"],
        },
        "binding_summary": binding_summary,
        "verification": {
            "tests_passed": len(nodeids),
            "tests_failed": 0,
            "tests_skipped": 0,
            "pytest_nodeids_sha256": hashlib.sha256(
                "\n".join(nodeids).encode("utf-8")
            ).hexdigest(),
            "direct_R3_remains_blocked": True,
            "external_calls": 0,
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
    _require(output_path.is_file(), "fresh_worker_output_missing")
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
    _require(not _git("status", "--porcelain"), "source_worktree_not_clean")
    head = _git("rev-parse", "HEAD")
    _require(head == _git("rev-parse", "@{upstream}"), "source_head_not_synced")
    _require(not RESULT_PATH.exists(), "v1_2_result_already_exists")
    _require(not R3_RESULT_PATH.exists(), "R3_result_already_exists")
    changed = {
        item
        for item in _git(
            "diff",
            "--name-only",
            f"{PREDECESSOR_SOURCE_COMMIT}..{head}",
            "--",
            "src",
            "scripts",
            "configs/runtime",
            "tests",
        ).splitlines()
        if item
    }
    _require(changed == EXPECTED_CHANGED_RUNTIME_FILES, "runtime_change_set_not_bounded")
    project_os = run_project_os_preflight(ROOT, run_scope=RUN_SCOPE)
    _require(project_os.get("status") == "pass", "root_project_os_preflight_failed")
    binding_summary = _verify_predecessor_and_v3_bindings(ROOT)
    restricted_before = _source_capture_manifest()

    with tempfile.TemporaryDirectory(prefix="fin013-s0-04g-r3-requal-") as parent:
        runtime_root = Path(parent).resolve() / "clean-archive"
        _extract_clean_archive(head, runtime_root)
        injected = _inject_restricted_captures(runtime_root)
        worker = _run_worker(runtime_root, runtime_root / "worker-result.json")

    _require(restricted_before == _source_capture_manifest(), "restricted_inputs_changed")
    _require(not _git("status", "--porcelain"), "worktree_changed_during_proof")
    _require(worker.get("binding_summary") == binding_summary, "clean_binding_mismatch")

    body = {
        "schema_version": (
            "fin_ia_0_1_3_s1_08_v3_dell_r3_"
            "successor_clean_zero_call_preflight_v1_2"
        ),
        "recorded_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(
            timespec="seconds"
        ),
        "stage": "013-S0-04G",
        "status": "pass",
        "source_commit": head,
        "source_branch": _git("branch", "--show-current"),
        "project_os_preflight": {
            "schema_version": project_os["schema_version"],
            "run_scope": RUN_SCOPE,
            "status": "pass",
            "allow_open_blockers": False,
            "open_full_chain_blocker_count": 0,
            "run_scope_registry_version": project_os["run_scope_registry"][
                "registry_version"
            ],
        },
        "predecessor_preflight": {
            "path": PREDECESSOR_PATH.relative_to(ROOT).as_posix(),
            "schema_version": (
                "fin_ia_0_1_3_s1_08_v3_dell_r3_"
                "successor_clean_zero_call_preflight_v1_1"
            ),
            "sha256": PREDECESSOR_PREFLIGHT_SHA256,
            "source_commit": PREDECESSOR_SOURCE_COMMIT,
        },
        "governance_requalification": {
            "project_os_preflight_schema": "fin_insight_project_os_full_chain_preflight_v0_2",
            "run_scope_registry_version": "v1_0",
            "previous_R3_runtime_contract_compatible": True,
            "changed_runtime_files": sorted(changed),
            "direct_R3_scope_remains_blocked": True,
        },
        "source_files": {
            "runtime": RUNTIME_PATH.relative_to(ROOT).as_posix(),
            "runtime_sha256": _sha256(RUNTIME_PATH),
            "runner": RUNNER_PATH.relative_to(ROOT).as_posix(),
            "runner_sha256": _sha256(RUNNER_PATH),
            "preflight_runner": Path(__file__).resolve().relative_to(ROOT).as_posix(),
            "preflight_runner_sha256": _sha256(Path(__file__).resolve()),
        },
        "authority_bindings": _authority_bindings(),
        "verification": {
            "clean_git_archive": True,
            "fresh_python_process": True,
            "restricted_R1_request_objects_injected": len(injected["R1_request_objects"]),
            "restricted_R2_content_objects_injected": len(injected["R2_content_objects"]),
            "restricted_inputs_unchanged": True,
            "tests_passed": worker["verification"]["tests_passed"],
            "tests_failed": 0,
            "tests_skipped": 0,
            "pytest_nodeids_sha256": worker["verification"]["pytest_nodeids_sha256"],
            "predecessor_and_v3_source_bindings": "pass",
            "bounded_runtime_change_set": "pass",
            "direct_R3_remains_blocked": True,
            "external_calls": 0,
            "admissions_issued": 0,
        },
        "observed_counts": {
            "network_calls": 0,
            "model_calls": 0,
            "provider_calls": 0,
            "retry_calls": 0,
            "formal_admissions_issued": 0,
            "live_runs": 0,
        },
        "known_boundary": (
            "This S0-04G proof requalifies the prior R3 successor against the typed "
            "Project OS contract. It does not issue an admission, execute R3, prove "
            "candidate quality, admit ranking or change the no-R4 stop rule."
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
