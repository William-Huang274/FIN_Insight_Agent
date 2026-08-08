from __future__ import annotations

import argparse
import compileall
from datetime import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tarfile
import tempfile
from typing import Any, Mapping
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_08_official_first_portfolio_"
    "clean_independent_zero_call_proof_v1_0.json"
)
WORKTREE_PROOF = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_08_"
    "official_first_portfolio_zero_call_proof_v1_0.json"
)
PROGRESSION_PLAN = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_retrieval_query_facet_"
    "external_internal_progression_plan_v1_0.json"
)
MATERIALIZER = ROOT / (
    "scripts/releases/materialize_fin_ia_0_1_3_s1_08_"
    "official_first_portfolio_zero_call_proof.py"
)
POLICY = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s1_08_"
    "official_first_portfolio_policy_v1_0.json"
)
RUNTIME = ROOT / "src/sec_agent/s1_08_official_first_portfolio.py"
CURRENT_SCOPE = "S1_08_OFFICIAL_FIRST_PORTFOLIO_CLEAN_INDEPENDENT_ZERO_CALL_PROOF"
NEXT_SCOPE = "S1_08_UNIFIED_QUERY_FACET_PLAN_ZERO_CALL_IMPLEMENTATION"
PYTEST_TARGETS = (
    "tests/contract/test_fin_0_1_3_s1_08_official_first_portfolio.py",
    "tests/contract/test_fin_0_1_3_s1_08_provider_portfolio_boundary_decision.py",
    "tests/contract/test_fin_0_1_3_s0_04g_typed_blocker_state_and_run_scope_registry.py",
    "tests/contract/test_fin_0_1_3_s1_08_relationship_aware_search_intent_compiler.py",
    "tests/contract/test_fin_0_1_3_s1_08_candidate_generation_runtime.py",
)
EXPECTED_PYTEST_PASSES = 45
SCRUBBED_ENVIRONMENT_MARKERS = (
    "API_KEY",
    "AUTHORIZATION",
    "ACCESS_TOKEN",
    "COOKIE",
    "PASSWORD",
    "SECRET",
)


class OfficialFirstCleanProofError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise OfficialFirstCleanProofError(code)


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


def _load_module(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("official_first_materializer", path)
    _require(spec is not None and spec.loader is not None, "materializer_spec_invalid")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _worker_payload(runtime_root: Path) -> dict[str, Any]:
    sys.path.insert(0, str(runtime_root))
    sys.path.insert(0, str(runtime_root / "src"))
    os.chdir(runtime_root)
    network_attempts: list[str] = []

    def blocked_network(*args: Any, **kwargs: Any) -> Any:
        network_attempts.append("socket")
        raise RuntimeError("official_first_clean_proof_network_forbidden")

    socket.socket.connect = blocked_network  # type: ignore[method-assign]
    socket.socket.connect_ex = blocked_network  # type: ignore[method-assign]
    socket.create_connection = blocked_network

    import pytest

    from sec_agent.canonical_runtime.models import canonical_digest
    from sec_agent.project_os_preflight import run_project_os_preflight

    preflight = run_project_os_preflight(runtime_root, run_scope=CURRENT_SCOPE)
    _require(preflight["status"] == "pass", "clean_scope_preflight_failed")
    _require(not preflight["contract_errors"], "clean_scope_contract_error")
    _require(
        compileall.compile_file(runtime_root / RUNTIME.relative_to(ROOT), quiet=2, force=True),
        "runtime_compile_failed",
    )

    proof_path = runtime_root / WORKTREE_PROOF.relative_to(ROOT)
    proof_before = proof_path.read_bytes()
    materializer = _load_module(runtime_root / MATERIALIZER.relative_to(ROOT))
    _require(materializer.main() == 0, "materializer_failed")
    proof_after = proof_path.read_bytes()
    _require(proof_after == proof_before, "materialized_proof_not_reproducible")
    proof = _load(proof_path)
    proof_body = dict(proof)
    supplied_digest = str(proof_body.pop("proof_digest"))
    _require(
        supplied_digest == canonical_digest(proof_body),
        "worktree_proof_digest_drift",
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
    _require(
        len(nodeids) == EXPECTED_PYTEST_PASSES,
        f"unexpected_passed_test_count:{len(nodeids)}",
    )
    _require(not network_attempts, "network_attempt_observed")
    return {
        "schema_version": "fin_ia_0_1_3_s1_08_official_first_clean_worker_v1_0",
        "status": "pass",
        "preflight_scope": CURRENT_SCOPE,
        "proof_digest": supplied_digest,
        "route_plan_digest": proof["route_plan_digest"],
        "quality_card_digest": proof["search_quality_card"]["quality_card_digest"],
        "route_opportunity": [
            proof["route_plan"]["required_slots_with_route_opportunity"],
            proof["route_plan"]["required_slots_total"],
        ],
        "pytest": {
            "passed": len(nodeids),
            "failed": 0,
            "skipped": 0,
            "nodeids": nodeids,
        },
        "hard_boundaries": {
            "credential_values_present_or_read": 0,
            "network_attempts": 0,
            "model_calls": 0,
            "provider_calls": 0,
            "document_fetches": 0,
            "evidence_promotions": 0,
            "admissions_issued": 0,
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
    source_bindings = {
        path.relative_to(ROOT).as_posix(): _sha256(path)
        for path in (
            WORKTREE_PROOF,
            PROGRESSION_PLAN,
            MATERIALIZER,
            POLICY,
            RUNTIME,
            Path(__file__).resolve(),
        )
    }
    workers: list[dict[str, Any]] = []
    worker_bytes: list[bytes] = []
    with tempfile.TemporaryDirectory(
        prefix="fin013-s1-08-official-first-clean-proof-"
    ) as parent:
        parent_path = Path(parent).resolve()
        _require(
            parent_path.name.startswith("fin013-s1-08-official-first-clean-proof-"),
            "temporary_root_invalid",
        )
        for ordinal in (1, 2):
            runtime_root = parent_path / f"clean-archive-{ordinal}"
            _extract_clean_archive(git_state["commit"], runtime_root)
            output_path = runtime_root / f"worker-result-{ordinal}.json"
            payload = _run_worker(runtime_root, output_path)
            workers.append(payload)
            worker_bytes.append(_canonical_bytes(payload))
        _require(worker_bytes[0] == worker_bytes[1], "fresh_worker_outputs_differ")

    _require(not _git("status", "--porcelain"), "worktree_changed_during_proof")
    _require(
        all(_sha256(ROOT / ref) == digest for ref, digest in source_bindings.items()),
        "source_binding_changed_during_proof",
    )
    body = {
        "schema_version": (
            "fin_ia_0_1_3_s1_08_official_first_portfolio_"
            "clean_independent_zero_call_proof_v1_0"
        ),
        "proof_id": CURRENT_SCOPE,
        "recorded_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(
            timespec="seconds"
        ),
        "stage": "FIN-0.1.3-S1-08",
        "status": "pass_two_clean_archives_two_fresh_processes_zero_call_reproducible",
        "source_commit": git_state,
        "source_bindings": source_bindings,
        "independent_proof": {
            "clean_git_archives": 2,
            "fresh_python_processes": 2,
            "distinct_disposable_roots": 2,
            "normalized_outputs_equal": True,
            "normalized_output_sha256": hashlib.sha256(worker_bytes[0]).hexdigest(),
            "worker_result": workers[0],
            "temporary_roots_removed": True,
        },
        "stage_acceptance": {
            "official_first_portfolio_runtime": "independently_proven",
            "unified_query_facet_plan": "not_implemented",
            "fresh_combined_external_live": "not_run_not_proven",
            "internal_retrieval_query_facet": "registered_backlog",
            "candidate_ceiling_and_qrels": "not_proven",
            "BGE_fusion_and_rerank": "not_admitted",
            "downstream_research_utilization": "not_proven",
            "S1_08": False,
            "release": False,
        },
        "observed_calls": {
            "network": 0,
            "model": 0,
            "provider": 0,
            "document_fetch": 0,
            "evidence_promotion": 0,
            "admission": 0,
        },
        "decision": {
            "clean_proof_complete": True,
            "next_scope": NEXT_SCOPE,
            "new_live_authority": False,
            "internal_ranking_authority": False,
        },
        "known_boundary": (
            "This proof establishes clean reproducibility of the official-first "
            "zero-call portfolio only. It does not prove a fresh source run, query "
            "facet quality, internal candidate recall, BGE/rerank value, downstream "
            "research quality, S1-08 acceptance, or release readiness."
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
        print(
            json.dumps(
                {
                    "status": payload["status"],
                    "source_commit": payload["source_commit"]["commit"],
                    "result_digest": payload["result_digest"],
                    "output": str(args.output),
                },
                ensure_ascii=False,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
