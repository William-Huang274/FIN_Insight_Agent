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
import tarfile
import tempfile
from typing import Any, Mapping
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[2]
IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_3_s2_06_three_case_unified_"
    "supervisor_zero_call_implementation_v1_0.json"
)
THREE_CASE_RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_3_s2_05_nvda_raw_replacement_"
    "r2_and_three_case_boundary_result_v1_0.json"
)
RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_3_s2_06_unified_supervisor_"
    "independent_fresh_zero_call_proof_result_v1_0.json"
)
TARGET_SUPERVISION_ROOT = ROOT / ".codex_runtime/fin013_s2_06"
RAW_RUN_ROOT = ROOT / ".codex_runtime/fin013_s2_05/runs"
CURRENT_ACTION = (
    "FIN-0.1.3-013-S2-06-UNIFIED-SUPERVISOR-INDEPENDENT-"
    "FRESH-ZERO-CALL-PROOF"
)
NEXT_ACTION = (
    "FIN-0.1.3-013-S2-06-THREE-CASE-SUPERVISOR-"
    "ADMISSION-AUTHORITY-DECISION"
)
CASE_RUNS = {
    "DELL": "fin013_s2_05_exp_a_dell_f9e9264951d69da5ed86",
    "MU": "fin013_s2_05_exp_a_mu_d94afa12295f83b18870",
    "NVDA": "fin013_s2_05_exp_a_nvda_04b01685650a1af46f43",
}
EXPECTED_REAL_MATRIX = {
    "DELL": {
        "evaluation_digest": (
            "68f89f4e33622a3dd5f65c06c7f75857c8a9833066910b723df674ed462c4af4"
        ),
        "supervisor_request_characters": 33590,
        "node_directives": 6,
        "provider_calls": 8,
    },
    "MU": {
        "evaluation_digest": (
            "786ff716e390f16ec3e1e2f9f50970338d11d3f6d436cd338ee1154da6928e6d"
        ),
        "supervisor_request_characters": 28104,
        "node_directives": 8,
        "provider_calls": 10,
    },
    "NVDA": {
        "evaluation_digest": (
            "746b777bd8d4b7f06f47b9ce6966d4cf03e04811c3d7d6da85c7ee29d81d8628"
        ),
        "supervisor_request_characters": 35650,
        "node_directives": 9,
        "provider_calls": 10,
    },
}
SCRUBBED_ENVIRONMENT_MARKERS = (
    "API_KEY",
    "AUTHORIZATION",
    "ACCESS_TOKEN",
    "SECRET_KEY",
    "PASSWORD",
)
PYTEST_TARGETS = (
    "tests/contract/test_fin_0_1_3_s2_06_supervision_boundary.py",
    "tests/contract/test_fin_0_1_3_s2_06_unified_supervisor_runtime.py",
)
FROZEN_WORKTREE_BYTE_BINDINGS = {
    (
        "eval_sets/fin_0_1_3_same_evidence_v1/model_visible/"
        "experiment_a_blind_inputs_v1.json"
    ): "689a4f957015c6b16f4d3ecdde6292450c044f9641af09537b1f0190176bdb59",
}


class UnifiedSupervisorFreshProofError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise UnifiedSupervisorFreshProofError(code)


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


def _tree_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "files": 0, "bytes": 0, "sha256": None}
    rows: list[tuple[str, int, str]] = []
    if path.is_file():
        rows.append((path.name, path.stat().st_size, _sha256(path)))
    else:
        for child in sorted(row for row in path.rglob("*") if row.is_file()):
            rows.append(
                (
                    child.relative_to(path).as_posix(),
                    child.stat().st_size,
                    _sha256(child),
                )
            )
    encoded = json.dumps(rows, separators=(",", ":")).encode("utf-8")
    return {
        "exists": True,
        "files": len(rows),
        "bytes": sum(row[1] for row in rows),
        "sha256": hashlib.sha256(encoded).hexdigest(),
    }


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
    status = _git("status", "--porcelain")
    _require(not status, "source_worktree_not_clean")
    head = _git("rev-parse", "HEAD")
    upstream = _git("rev-parse", "@{upstream}")
    _require(head == upstream, "source_head_not_synced_to_upstream")
    return {
        "commit": head,
        "upstream_commit": upstream,
        "clean": True,
        "synced": True,
    }


def _verify_implementation_bindings(root: Path) -> dict[str, str]:
    implementation_path = root / IMPLEMENTATION.relative_to(ROOT)
    implementation = _load(implementation_path)
    body = {
        key: value
        for key, value in implementation.items()
        if key != "implementation_digest"
    }
    _require(
        _canonical_digest(body) == implementation["implementation_digest"],
        "implementation_record_digest_drift",
    )
    observed: dict[str, str] = {}
    for binding in implementation["implementation"].values():
        relative = str(binding["ref"])
        digest = _sha256(root / relative)
        _require(digest == binding["sha256"], f"implementation_binding_drift:{relative}")
        observed[relative] = digest
    _require(
        implementation["stage_acceptance"]["supervised_recoverability"]
        == "not_proven",
        "implementation_overclaims_recoverability",
    )
    return observed


def _source_raw_roots() -> dict[str, Path]:
    return {
        case_key: RAW_RUN_ROOT / run_id / "raw_model_only"
        for case_key, run_id in CASE_RUNS.items()
    }


def _raw_source_snapshot() -> dict[str, Any]:
    rows: dict[str, Any] = {}
    for case_key, raw_root in _source_raw_roots().items():
        _require(raw_root.exists(), f"source_raw_root_missing:{case_key}")
        terminal = _load(raw_root / "layered_terminal_result.json")
        _require(
            terminal.get("run_id") == CASE_RUNS[case_key]
            and terminal.get("case_key") == case_key
            and terminal.get("status") == "terminal_completed_layered_raw_evaluation",
            f"source_raw_terminal_invalid:{case_key}",
        )
        rows[case_key] = {
            "run_id": terminal["run_id"],
            "terminal_result_digest": terminal["terminal_result_digest"],
            "tree": _tree_manifest(raw_root),
        }
    return rows


def _extract_clean_archive(commit: str, target: Path) -> None:
    archive_path = target.parent / (target.name + ".tar")
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


def _project_clean_worktree_byte_bindings(
    *,
    commit: str,
    target: Path,
) -> dict[str, Any]:
    """Recreate byte-bound clean Windows inputs in a Git archive.

    The frozen S2-05 policy predates the repository-wide LF rule and binds the
    clean Windows worktree CRLF bytes. Git stores the same semantic JSON as LF,
    so a raw archive cannot satisfy that historical byte digest. This projection
    is allowed only when Git reports no semantic diff and normalized bytes equal
    the committed blob exactly.
    """

    rows: dict[str, Any] = {}
    for relative, expected_worktree_sha in FROZEN_WORKTREE_BYTE_BINDINGS.items():
        source = ROOT / relative
        _require(_sha256(source) == expected_worktree_sha, f"worktree_byte_binding_drift:{relative}")
        clean_check = subprocess.run(
            ["git", "diff", "--quiet", commit, "--", relative],
            cwd=ROOT,
            check=False,
        )
        _require(clean_check.returncode == 0, f"projected_file_not_git_clean:{relative}")
        blob = subprocess.run(
            ["git", "show", f"{commit}:{relative}"],
            cwd=ROOT,
            capture_output=True,
            check=False,
        )
        _require(blob.returncode == 0, f"projected_git_blob_missing:{relative}")
        worktree_bytes = source.read_bytes()
        normalized = worktree_bytes.replace(b"\r\n", b"\n")
        _require(normalized == blob.stdout, f"projected_semantic_content_drift:{relative}")
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        _require(_sha256(destination) == expected_worktree_sha, f"projected_copy_drift:{relative}")
        rows[relative] = {
            "git_blob_sha256": hashlib.sha256(blob.stdout).hexdigest(),
            "clean_worktree_sha256": expected_worktree_sha,
            "normalized_content_matches_git_blob": True,
            "reason": "historical_frozen_policy_binds_clean_windows_CRLF_bytes",
        }
    return rows


def _inject_restricted_raw_inputs(target: Path) -> dict[str, Any]:
    input_root = target / ".proof_inputs"
    copied: dict[str, Any] = {}
    for case_key, source in _source_raw_roots().items():
        destination = input_root / case_key
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, destination)
        source_manifest = _tree_manifest(source)
        destination_manifest = _tree_manifest(destination)
        _require(
            source_manifest == destination_manifest,
            f"restricted_raw_copy_mismatch:{case_key}",
        )
        copied[case_key] = destination_manifest
    return copied


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


def _load_raw_outputs(capture_root: Path) -> dict[str, Any]:
    captures: list[tuple[int, str, dict[str, Any]]] = []
    for path in sorted(capture_root.glob("*.json")):
        row = _load(path)
        content = row.get("gateway_result", {}).get("content")
        _require(isinstance(content, str), f"capture_content_missing:{path.name}")
        captures.append((int(row["call_index"]), str(row["node_type"]), json.loads(content)))
    captures.sort(key=lambda row: row[0])
    by_type: dict[str, list[dict[str, Any]]] = {}
    for _, node_type, content in captures:
        by_type.setdefault(node_type, []).append(content)
    for node_type in ("lead_planning", "cross_cell_synthesis", "writer", "verifier"):
        _require(len(by_type.get(node_type, [])) == 1, f"required_capture_missing:{node_type}")
    specialists = by_type.get("specialist_judgment", [])
    _require(6 <= len(specialists) <= 8, "specialist_capture_count_invalid")
    _require(len(captures) == len(specialists) + 4, "unexpected_capture_type")
    return {
        "lead": by_type["lead_planning"][0],
        "specialists": specialists,
        "synthesis": by_type["cross_cell_synthesis"][0],
        "writer": by_type["writer"][0],
        "verifier": by_type["verifier"][0],
    }


def _worker_payload(runtime_root: Path) -> dict[str, Any]:
    sys.path.insert(0, str(runtime_root))
    sys.path.insert(0, str(runtime_root / "src"))
    sys.path.insert(0, str(runtime_root / "tests" / "contract"))

    network_attempts: list[str] = []

    def blocked_network(*args: Any, **kwargs: Any) -> Any:
        network_attempts.append("socket")
        raise RuntimeError("s2_06_independent_proof_network_forbidden")

    socket.socket.connect = blocked_network  # type: ignore[method-assign]
    socket.socket.connect_ex = blocked_network  # type: ignore[method-assign]
    socket.create_connection = blocked_network

    import pytest

    from sec_agent.retrieval_evidence_usefulness_program import canonical_digest
    from sec_agent.s2_same_evidence_experiment_runtime import (
        SECTION_IDS,
        load_frozen_blind_inputs,
        load_runtime_policy,
    )
    from sec_agent.s2_same_evidence_layered_evaluation import evaluate_raw_chain
    from sec_agent.s2_same_evidence_supervision import (
        compile_case_scoped_supervision_boundary,
    )
    from sec_agent.s2_same_evidence_supervisor_runtime import (
        compile_capacity_proof,
        compile_corrected_admission_candidate,
        compile_fixture_supervisor_plan,
        compile_supervisor_plan_spec,
        compile_supervisor_request,
        validate_supervisor_plan,
    )

    observed_bindings = _verify_implementation_bindings(runtime_root)
    plugin = _StablePytestResult()
    exit_code = pytest.main(
        ["-q", "--disable-warnings", *PYTEST_TARGETS],
        plugins=[plugin],
    )
    _require(exit_code == 0, f"pytest_failed:{exit_code}")
    _require(not plugin.failed, "pytest_reported_failure")
    _require(not plugin.skipped, "pytest_reported_skip")
    _require(len(plugin.passed) == 24, "unexpected_passed_test_count")

    policy = load_runtime_policy(runtime_root)
    case_inputs = {
        row["case_key"]: row
        for row in load_frozen_blind_inputs(runtime_root, policy)["cases"]
    }
    three_case_result = _load(runtime_root / THREE_CASE_RESULT.relative_to(ROOT))
    expected_digests = {
        case_key: row["evaluation_digest"]
        for case_key, row in three_case_result["evaluator_disposition"][
            "three_case_v1_4_replay"
        ].items()
        if case_key in CASE_RUNS
    }
    real_matrix: dict[str, Any] = {}
    raw_before = {
        case_key: _tree_manifest(runtime_root / ".proof_inputs" / case_key)
        for case_key in CASE_RUNS
    }
    for case_key, run_id in CASE_RUNS.items():
        raw_root = runtime_root / ".proof_inputs" / case_key
        terminal = _load(raw_root / "layered_terminal_result.json")
        raw_outputs = _load_raw_outputs(raw_root / "captures")
        evaluation = evaluate_raw_chain(
            raw_outputs,
            case_input=case_inputs[case_key],
            policy=policy,
            section_ids=SECTION_IDS,
        )
        evaluation_digest = canonical_digest(evaluation)
        expected = EXPECTED_REAL_MATRIX[case_key]
        _require(
            evaluation_digest == expected["evaluation_digest"]
            == expected_digests[case_key],
            f"real_evaluation_digest_drift:{case_key}",
        )
        boundary = compile_case_scoped_supervision_boundary(
            evaluation,
            case_key=case_key,
            raw_run_id=run_id,
            raw_terminal_digest=str(terminal["terminal_result_digest"]),
        )
        spec = compile_supervisor_plan_spec(
            boundary=boundary,
            case_input=case_inputs[case_key],
            raw_outputs=raw_outputs,
        )
        plan = compile_fixture_supervisor_plan(spec)
        validate_supervisor_plan(plan, spec)
        request = compile_supervisor_request(
            spec=spec,
            raw_outputs=raw_outputs,
            policy=policy,
            corrected_run_id=f"fresh-proof-{case_key.lower()}",
        )
        capacity = compile_capacity_proof(
            plan=plan,
            spec=spec,
            raw_outputs=raw_outputs,
        )
        request_chars = len(request["messages"][1]["content"])
        _require(
            request_chars == expected["supervisor_request_characters"],
            f"real_request_capacity_drift:{case_key}",
        )
        _require(
            len(plan["node_directives"]) == expected["node_directives"]
            and capacity["provider_calls"] == expected["provider_calls"]
            and capacity["pass"] is True,
            f"real_graph_capacity_drift:{case_key}",
        )
        candidate = compile_corrected_admission_candidate(
            spec=spec,
            raw_outputs=raw_outputs,
            corrected_run_id=f"fresh-proof-{case_key.lower()}",
            corrected_attempt_id=f"fresh-proof-{case_key.lower()}-attempt-1",
            admission_id=f"fresh-proof-{case_key.lower()}-prospective-only",
            issued_at="2026-08-07T00:00:00+00:00",
            expires_at="2026-08-08T00:00:00+00:00",
            credential_present=False,
            provider_execution_authorized=False,
        )
        _require(
            candidate["provider_execution_authorized"] is False,
            f"prospective_candidate_authorized:{case_key}",
        )
        real_matrix[case_key] = {
            "raw_run_id": run_id,
            "raw_terminal_digest": terminal["terminal_result_digest"],
            "raw_outputs_digest": canonical_digest(raw_outputs),
            "evaluation_digest": evaluation_digest,
            "finding_count": evaluation["finding_count"],
            "correction_count": len(boundary["corrections"]),
            "node_directives": len(plan["node_directives"]),
            "supervisor_request_characters": request_chars,
            "corrected_graph_calls": capacity["corrected_graph_calls"],
            "provider_calls": capacity["provider_calls"],
            "prospective_admission_digest": candidate["admission_digest"],
            "provider_execution_authorized": False,
        }
    raw_after = {
        case_key: _tree_manifest(runtime_root / ".proof_inputs" / case_key)
        for case_key in CASE_RUNS
    }
    _require(raw_before == raw_after, "worker_raw_inputs_mutated")
    _require(not network_attempts, "network_attempt_observed")

    nodeids = sorted(plugin.passed)
    required_mutations = (
        "test_cross_case_alias_and_hidden_surface_mutations_fail_closed",
        "test_eight_unit_full_graph_is_blocked_by_frozen_capacity",
        "test_failure_terminal_preserves_every_capture_and_stops_without_retry",
        "test_corrected_admission_is_exact_once_even_with_new_runtime_root",
    )
    for fragment in required_mutations:
        _require(
            any(fragment in nodeid for nodeid in nodeids),
            f"required_mutation_test_missing:{fragment}",
        )
    return {
        "schema_version": (
            "fin_ia_0_1_3_s2_06_unified_supervisor_"
            "independent_fresh_worker_proof_v1_0"
        ),
        "status": "pass",
        "implementation_bindings": observed_bindings,
        "real_frozen_input_matrix": real_matrix,
        "raw_input_manifests_before": raw_before,
        "raw_input_manifests_after": raw_after,
        "raw_inputs_unchanged": True,
        "pytest": {
            "passed": len(nodeids),
            "failed": 0,
            "skipped": 0,
            "nodeids": nodeids,
        },
        "hard_boundaries": {
            "credential_values_present_or_read": 0,
            "real_model_calls": 0,
            "real_provider_calls": 0,
            "network_attempts": 0,
            "source_calls": 0,
            "external_tool_calls": 0,
            "admissions_issued": 0,
            "admissions_consumed": 0,
            "corrected_paid_candidates": 0,
            "hidden_scores": 0,
            "business_promotions": 0,
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
        + completed.stderr[-2000:],
    )
    _require(output_path.exists(), "fresh_worker_output_missing")
    return _load(output_path)


def build_result() -> dict[str, Any]:
    git_state = _assert_clean_synced_head()
    implementation_bindings = _verify_implementation_bindings(ROOT)
    raw_before = _raw_source_snapshot()
    target_before = _tree_manifest(TARGET_SUPERVISION_ROOT)

    worker_payloads: list[dict[str, Any]] = []
    worker_bytes: list[bytes] = []
    injected_manifests: list[dict[str, Any]] = []
    projected_bindings: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="fin013-s2-06-fresh-proof-") as parent:
        parent_path = Path(parent)
        for ordinal in (1, 2):
            runtime_root = parent_path / f"clean-archive-{ordinal}"
            _extract_clean_archive(git_state["commit"], runtime_root)
            projected_bindings.append(
                _project_clean_worktree_byte_bindings(
                    commit=git_state["commit"],
                    target=runtime_root,
                )
            )
            injected_manifests.append(_inject_restricted_raw_inputs(runtime_root))
            output_path = runtime_root / f"worker-result-{ordinal}.json"
            payload = _run_worker(runtime_root, output_path)
            worker_payloads.append(payload)
            worker_bytes.append(_canonical_bytes(payload))
        _require(worker_bytes[0] == worker_bytes[1], "fresh_worker_outputs_differ")
        _require(
            injected_manifests[0] == injected_manifests[1],
            "fresh_worker_injected_inputs_differ",
        )
        _require(
            projected_bindings[0] == projected_bindings[1],
            "fresh_worker_projected_bindings_differ",
        )

    raw_after = _raw_source_snapshot()
    target_after = _tree_manifest(TARGET_SUPERVISION_ROOT)
    _require(raw_before == raw_after, "source_raw_state_changed")
    _require(target_before == target_after, "target_supervision_state_changed")
    _require(
        _verify_implementation_bindings(ROOT) == implementation_bindings,
        "implementation_binding_changed_during_proof",
    )
    _require(_git("status", "--porcelain") == "", "worktree_changed_during_proof")

    body = {
        "schema_version": (
            "fin_ia_0_1_3_s2_06_unified_supervisor_"
            "independent_fresh_zero_call_proof_result_v1_0"
        ),
        "proof_id": CURRENT_ACTION,
        "recorded_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(
            timespec="seconds"
        ),
        "status": (
            "pass_two_clean_commit_archives_two_fresh_processes_real_"
            "frozen_inputs_and_mutation_matrix_zero_call_reproducible"
        ),
        "source_commit": git_state,
        "source_bindings": {
            "implementation_ref": IMPLEMENTATION.relative_to(ROOT).as_posix(),
            "implementation_sha256": _sha256(IMPLEMENTATION),
            "implementation_files": implementation_bindings,
            "three_case_result_ref": THREE_CASE_RESULT.relative_to(ROOT).as_posix(),
            "three_case_result_sha256": _sha256(THREE_CASE_RESULT),
        },
        "independent_proof": {
            "clean_git_archives": 2,
            "fresh_python_processes": 2,
            "distinct_disposable_roots": 2,
            "restricted_raw_inputs_injected_byte_identical": True,
            "clean_worktree_byte_projection": projected_bindings[0],
            "projection_files": len(projected_bindings[0]),
            "normalized_outputs_equal": True,
            "normalized_output_sha256": hashlib.sha256(worker_bytes[0]).hexdigest(),
            "worker_result": worker_payloads[0],
            "temporary_roots_removed": True,
        },
        "source_and_target_read_only_audit": {
            "source_raw_before": raw_before,
            "source_raw_after": raw_after,
            "source_raw_unchanged": True,
            "target_supervision_before": target_before,
            "target_supervision_after": target_after,
            "target_supervision_unchanged": True,
            "repository_status_unchanged_until_result_write": True,
        },
        "acceptance_boundary": {
            "S2_06_shared_runtime_fresh_reproducibility": "pass",
            "real_frozen_input_compilation_and_capacity": "pass",
            "supervisor_natural_output": "not_run_not_proven",
            "corrected_candidate_live_execution": "not_run_not_proven",
            "supervised_recoverability": "not_proven",
            "corrected_report_quality": "not_measured",
            "formal_hidden_score": False,
            "qualified_human_acceptance": False,
            "business_promotion": False,
            "release": False,
        },
        "observed_counts": {
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": 0,
            "source_calls": 0,
            "external_tool_calls": 0,
            "admissions_issued": 0,
            "admissions_consumed": 0,
            "paid_corrected_candidates": 0,
            "raw_mutations": 0,
        },
        "next_action": NEXT_ACTION,
        "next_action_authorized": False,
        "known_boundary": (
            "This proof establishes clean-commit reproducibility, real frozen-input "
            "binding, case isolation, capacity and deterministic mutation behavior. "
            "It does not authorize an admission or show that DeepSeek can produce a "
            "valid SupervisorPlan, repair L1/L2 findings or improve research quality."
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
    )
    if not args.worker:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
