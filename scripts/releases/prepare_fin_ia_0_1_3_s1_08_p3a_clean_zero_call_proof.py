from __future__ import annotations

import argparse
import compileall
from datetime import datetime
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
from typing import Any, Mapping
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[2]
IMPLEMENTATION_RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_08_p3a_"
    "protected_document_fetch_cache_zero_call_implementation_v1_0.json"
)
R3_RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_08_v3_"
    "dell_current_search_r3_result_v1_0.json"
)
R3_EVALUATION = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_08_v3_"
    "dell_current_search_r3_source_quality_evaluation_v1_0.json"
)
R3_CAPTURE_ROOT = ROOT / (
    ".codex_runtime/fin013_s1_08_v3_dell_current_search_r3/"
    "fin013_s1_08_dell_r3_admission_a3f1c96343823f83883b/adapter/objects/"
    "fin-0.1.3/s1-08/current-source-discovery"
)
RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_08_p3a_"
    "protected_document_fetch_cache_clean_zero_call_proof_v1_0.json"
)
CURRENT_ACTION = (
    "S1_08_P3A_PROTECTED_DOCUMENT_FETCH_BUDGET_AND_ATTEMPT_LOCAL_CACHE_"
    "CLEAN_ARCHIVE_FRESH_PROCESS_ZERO_CALL_PROOF"
)
NEXT_ACTION = (
    "S1_08_P3B_POST_REPAIR_PROVIDER_PRODUCT_SCOPE_AND_NO_R4_OWNER_DECISION"
)
EXPECTED_DEPENDENCIES = {
    "feedparser": "6.0.12",
    "trafilatura": "2.1.0",
    "lxml": "6.1.1",
}
EXPECTED_R3_SHA256 = {
    R3_RESULT: "731885330176f1d3a428ed3cdf62315e34c345f457ba39b749d60802d9c6b1d5",
    R3_EVALUATION: "b8af0d6e6a573ce2365d544972bfb74bbdf6ba8927c4a29f1d33cae8a6b6c5f2",
}
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
    "tests/contract/test_fin_0_1_3_s1_08_p3a_protected_document_fetch_and_cache_v4.py",
)
REQUIRED_TEST_FRAGMENTS = (
    "test_v4_is_a_true_successor_and_all_v3_r3_evidence_is_byte_stable",
    "test_landing_local_stop_does_not_poison_successor_attempt",
    "test_nested_structured_local_stop_does_not_cache_partial_landing",
    "test_pre_request_stop_is_attempt_local_and_cannot_poison_later_slot",
    "test_captured_remote_failure_is_typed_and_reused_without_retry",
    "test_parser_failure_has_distinct_typed_lineage_and_is_not_reparsed",
    "test_v4_three_case_full_fake_closes_slots_with_fixed_global_ceiling[DELL]",
    "test_v4_three_case_full_fake_closes_slots_with_fixed_global_ceiling[MU]",
    "test_v4_three_case_full_fake_closes_slots_with_fixed_global_ceiling[NVDA]",
    "test_immutable_r3_capture_replay_reaches_document_after_natural_route_topology",
)
SCRUBBED_ENVIRONMENT_MARKERS = (
    "API_KEY",
    "AUTHORIZATION",
    "ACCESS_TOKEN",
    "COOKIE",
    "PASSWORD",
    "SECRET",
    "FINSIGHT_SEC_CONTACT_EMAIL",
)


class P3ACleanProofError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise P3ACleanProofError(code)


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


def _canonical_digest(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


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
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "clean": True,
        "synced": True,
    }


def _verify_implementation(root: Path) -> dict[str, str]:
    proof_path = root / IMPLEMENTATION_RESULT.relative_to(ROOT)
    proof = _load(proof_path)
    _require(
        proof["status"]
        == "working_tree_zero_call_engineering_pass_clean_archive_fresh_process_proof_pending",
        "implementation_result_status_invalid",
    )
    _require(
        proof["verification"]["focused_P3A_tests_passed"] == 22
        and proof["verification"]["legacy_S1_08_tests_passed"] == 70
        and proof["verification"]["combined_tests_passed"] == 92,
        "implementation_test_count_invalid",
    )
    bindings = {
        proof["v4_successor"]["catalog_ref"]: proof["v4_successor"]["catalog_sha256"],
        proof["v4_successor"]["candidate_runtime_ref"]: proof["v4_successor"][
            "candidate_runtime_sha256"
        ],
        proof["v4_successor"]["official_adapter_ref"]: proof["v4_successor"][
            "official_adapter_sha256"
        ],
        proof["v4_successor"]["contract_test_ref"]: proof["v4_successor"][
            "contract_test_sha256"
        ],
    }
    observed: dict[str, str] = {}
    for relative, expected in bindings.items():
        digest = _sha256(root / relative)
        _require(digest == expected, f"implementation_binding_drift:{relative}")
        observed[relative] = digest
    return observed


def _r3_capture_manifest(root: Path) -> dict[str, Any]:
    _require(root.exists(), "restricted_R3_capture_root_missing")
    rows: dict[str, Any] = {}
    request_digests: set[str] = set()
    outcome_request_digests: set[str] = set()
    counts = {
        "source_request": 0,
        "source_response": 0,
        "source_transport_failure": 0,
        "derived_parser_or_other": 0,
    }
    for path in sorted(root.rglob("*.json")):
        relative = path.relative_to(root).as_posix()
        payload = _load(path)
        digest = _sha256(path)
        _require(path.stem == digest, f"capture_content_address_drift:{relative}")
        kind = str(payload.get("capture_kind") or "derived_parser_or_other")
        _require(kind in counts, f"unexpected_R3_capture_kind:{kind}")
        counts[kind] += 1
        if kind == "source_request":
            request_digests.add(path.stem)
        elif kind in {"source_response", "source_transport_failure"}:
            outcome_request_digests.add(str(payload.get("request_capture_digest") or ""))
        rows[relative] = {"file_sha256": digest, "bytes": path.stat().st_size}
    _require(counts["source_request"] == 13, "restricted_R3_request_count_invalid")
    _require(counts["source_response"] == 11, "restricted_R3_response_count_invalid")
    _require(
        counts["source_transport_failure"] == 2,
        "restricted_R3_transport_failure_count_invalid",
    )
    _require(counts["derived_parser_or_other"] == 13, "restricted_R3_parser_count_invalid")
    _require(
        request_digests == outcome_request_digests,
        "restricted_R3_request_outcome_pairing_invalid",
    )
    return {"counts": counts, "objects": rows, "request_outcome_pairs": 13}


def _extract_clean_archive(commit: str, target: Path) -> None:
    archive_path = target.parent / f"{target.name}.tar"
    with archive_path.open("wb") as handle:
        completed = subprocess.run(
            ["git", "archive", "--format=tar", commit],
            cwd=ROOT,
            stdout=handle,
            stderr=subprocess.PIPE,
            check=False,
        )
    _require(completed.returncode == 0, "git_archive_failed")
    target.mkdir(parents=True, exist_ok=False)
    with tarfile.open(archive_path, "r") as archive:
        archive.extractall(target)
    archive_path.unlink()


def _inject_r3_captures(target: Path) -> dict[str, Any]:
    destination_root = target / R3_CAPTURE_ROOT.relative_to(ROOT)
    for source in sorted(R3_CAPTURE_ROOT.rglob("*.json")):
        destination = destination_root / source.relative_to(R3_CAPTURE_ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        _require(
            _sha256(source) == _sha256(destination),
            f"R3_capture_copy_drift:{source.name}",
        )
    return _r3_capture_manifest(destination_root)


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
    sys.path.insert(0, str(runtime_root / "src"))
    network_attempts: list[str] = []

    def blocked_network(*args: Any, **kwargs: Any) -> Any:
        network_attempts.append("socket")
        raise RuntimeError("s1_08_p3a_clean_proof_network_forbidden")

    socket.socket.connect = blocked_network  # type: ignore[method-assign]
    socket.socket.connect_ex = blocked_network  # type: ignore[method-assign]
    socket.create_connection = blocked_network

    import pytest

    dependency_versions = {package: version(package) for package in EXPECTED_DEPENDENCIES}
    _require(dependency_versions == EXPECTED_DEPENDENCIES, "dependency_version_drift")
    implementation_bindings = _verify_implementation(runtime_root)
    r3_manifest = _r3_capture_manifest(runtime_root / R3_CAPTURE_ROOT.relative_to(ROOT))
    _require(
        compileall.compile_dir(
            runtime_root / "src/sec_agent",
            quiet=2,
            force=True,
        ),
        "compileall_failed",
    )

    plugin = _StablePytestResult()
    exit_code = pytest.main(
        ["-q", "--disable-warnings", *PYTEST_TARGETS],
        plugins=[plugin],
    )
    _require(exit_code == 0, f"pytest_failed:{exit_code}")
    _require(not plugin.failed, "pytest_reported_failure")
    _require(not plugin.skipped, "pytest_reported_skip")
    _require(len(plugin.passed) == 92, "unexpected_passed_test_count")
    nodeids = sorted(plugin.passed)
    for fragment in REQUIRED_TEST_FRAGMENTS:
        _require(
            any(fragment in nodeid for nodeid in nodeids),
            f"required_test_missing:{fragment}",
        )
    _require(not network_attempts, "network_attempt_observed")

    return {
        "schema_version": "fin_ia_0_1_3_s1_08_p3a_clean_worker_v1_0",
        "status": "pass",
        "dependency_versions": dependency_versions,
        "implementation_bindings": implementation_bindings,
        "R3_restricted_capture_manifest_digest": _canonical_digest(r3_manifest),
        "R3_request_outcome_pairs": r3_manifest["request_outcome_pairs"],
        "pytest": {
            "passed": len(nodeids),
            "failed": 0,
            "skipped": 0,
            "nodeids": nodeids,
        },
        "coverage": {
            "fixed_global_budget_16": True,
            "protected_document_fetch": True,
            "landing_and_structured_incomplete_cache_rejection": True,
            "typed_remote_parser_and_local_stop_lineage": True,
            "R3_natural_topology_replay": True,
            "DELL_MU_NVDA_full_fake": True,
            "identity_currentness_relationship_numeric_lineage_mutations": True,
            "immutable_v3_R3_bindings": True,
        },
        "hard_boundaries": {
            "credential_values_present_or_read": 0,
            "network_attempts": 0,
            "model_calls": 0,
            "provider_calls": 0,
            "retry_calls": 0,
            "admissions_issued": 0,
            "live_runs": 0,
        },
    }


def _clean_child_environment(runtime_root: Path) -> dict[str, str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not any(marker in key.upper() for marker in SCRUBBED_ENVIRONMENT_MARKERS)
    }
    environment.update(
        {
            "PYTHONHASHSEED": "0",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "LLM_GATEWAY_TRANSPORT_RETRIES": "0",
            "TMP": str(runtime_root / ".tmp"),
            "TEMP": str(runtime_root / ".tmp"),
            "PYTHONPYCACHEPREFIX": str(runtime_root / ".pycache"),
        }
    )
    return environment


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


def build_result() -> dict[str, Any]:
    git_state = _assert_clean_synced_head()
    implementation_bindings = _verify_implementation(ROOT)
    source_manifest_before = _r3_capture_manifest(R3_CAPTURE_ROOT)
    for path, expected in EXPECTED_R3_SHA256.items():
        _require(_sha256(path) == expected, f"immutable_R3_binding_drift:{path.name}")

    worker_payloads: list[dict[str, Any]] = []
    worker_bytes: list[bytes] = []
    injected_manifests: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="fin013-s1-08-p3a-clean-proof-") as parent:
        parent_path = Path(parent).resolve()
        _require(
            parent_path.name.startswith("fin013-s1-08-p3a-clean-proof-"),
            "temporary_root_invalid",
        )
        for ordinal in (1, 2):
            runtime_root = parent_path / f"clean-archive-{ordinal}"
            _extract_clean_archive(git_state["commit"], runtime_root)
            injected_manifests.append(_inject_r3_captures(runtime_root))
            output_path = runtime_root / f"worker-result-{ordinal}.json"
            payload = _run_worker(runtime_root, output_path)
            worker_payloads.append(payload)
            worker_bytes.append(_canonical_bytes(payload))
        _require(worker_bytes[0] == worker_bytes[1], "fresh_worker_outputs_differ")
        _require(
            injected_manifests[0] == injected_manifests[1],
            "fresh_worker_injected_inputs_differ",
        )

    source_manifest_after = _r3_capture_manifest(R3_CAPTURE_ROOT)
    _require(source_manifest_before == source_manifest_after, "source_R3_captures_changed")
    _require(
        _verify_implementation(ROOT) == implementation_bindings,
        "implementation_binding_changed_during_proof",
    )
    for path, expected in EXPECTED_R3_SHA256.items():
        _require(_sha256(path) == expected, f"immutable_R3_changed:{path.name}")
    _require(not _git("status", "--porcelain"), "worktree_changed_during_proof")

    body = {
        "schema_version": (
            "fin_ia_0_1_3_s1_08_p3a_protected_document_fetch_cache_"
            "clean_zero_call_proof_v1_0"
        ),
        "proof_id": CURRENT_ACTION,
        "recorded_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(
            timespec="seconds"
        ),
        "stage": "013-S1-08-P3A",
        "status": (
            "pass_two_clean_archives_two_fresh_processes_"
            "immutable_R3_replay_zero_call_reproducible"
        ),
        "source_commit": git_state,
        "source_bindings": {
            "implementation_result_ref": IMPLEMENTATION_RESULT.relative_to(ROOT).as_posix(),
            "implementation_result_sha256": _sha256(IMPLEMENTATION_RESULT),
            "implementation_files": implementation_bindings,
            "R3_result_ref": R3_RESULT.relative_to(ROOT).as_posix(),
            "R3_result_sha256": _sha256(R3_RESULT),
            "R3_evaluation_ref": R3_EVALUATION.relative_to(ROOT).as_posix(),
            "R3_evaluation_sha256": _sha256(R3_EVALUATION),
            "proof_runner_ref": Path(__file__).resolve().relative_to(ROOT).as_posix(),
            "proof_runner_sha256": _sha256(Path(__file__).resolve()),
        },
        "independent_proof": {
            "clean_git_archives": 2,
            "fresh_python_processes": 2,
            "distinct_disposable_roots": 2,
            "restricted_R3_objects_injected": len(source_manifest_before["objects"]),
            "restricted_R3_request_outcome_pairs": 13,
            "restricted_inputs_byte_identical": True,
            "restricted_raw_body_or_headers_emitted": False,
            "normalized_outputs_equal": True,
            "normalized_output_sha256": hashlib.sha256(worker_bytes[0]).hexdigest(),
            "worker_result": worker_payloads[0],
            "temporary_roots_removed": True,
        },
        "source_read_only_audit": {
            "restricted_R3_manifest_digest_before": _canonical_digest(
                source_manifest_before
            ),
            "restricted_R3_manifest_digest_after": _canonical_digest(
                source_manifest_after
            ),
            "restricted_R3_inputs_unchanged": True,
            "versioned_R3_artifacts_unchanged": True,
            "repository_status_unchanged_until_result_write": True,
        },
        "acceptance_boundary": {
            "P3A_deterministic_engineering": "independently_proven",
            "protected_document_fetch_and_cache_v4": "pass",
            "fresh_live_source_reachability": "not_run_not_proven",
            "target_in_pool_and_required_slot_recall": "not_run_not_proven",
            "ranking_and_selected_evidence_pack": "not_admitted",
            "research_content_quality": "not_measured",
            "business_promotion": False,
            "release": False,
        },
        "observed_counts": {
            "pytest_passed_per_worker": 92,
            "network_calls": 0,
            "model_calls": 0,
            "provider_calls": 0,
            "retry_calls": 0,
            "admissions_issued": 0,
            "live_runs": 0,
        },
        "decision": {
            "P3A_complete": True,
            "P3B_owner_decision_required": True,
            "new_live_authority": False,
            "provider_acquisition_authorized": False,
            "R4_authorized": False,
        },
        "next_action": NEXT_ACTION,
        "next_action_authorized": False,
        "known_boundary": (
            "This dual clean-archive proof establishes the P3A scheduling and "
            "cache repair only. It does not prove source reachability, target-in-pool, "
            "ranking, Evidence promotion, DeepSeek behavior, research-content quality "
            "or release readiness. P3B must decide product/provider scope before any R4."
        ),
    }
    return {**body, "result_digest": _canonical_digest(body)}


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
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    if not args.worker:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
