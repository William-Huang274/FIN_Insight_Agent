from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
POLICY_REF = Path(
    "configs/runtime/fin_ia_0_1_3_s1_three_held_out_"
    "current_source_reparse_successor_r4_policy_v1_0.json"
)
SOURCE_RESULT_REF = Path(
    "configs/releases/fin_ia_0_1_3_s1_three_held_out_"
    "current_source_reparse_successor_r4_result_v1_0.json"
)
PROOF_REF = Path(
    "configs/releases/fin_ia_0_1_3_s1_three_held_out_"
    "current_source_reparse_successor_r4_clean_independent_proof_v1_0.json"
)
CURRENT_SCOPE = (
    "S1_THREE_HELD_OUT_CURRENT_SOURCE_TABLE_PRESERVING_REPARSE_AND_OBJECT_MIGRATION"
)
EXPECTED_RESULT_DIGEST = (
    "924c656e32e5e279c12883a6374f53b7e424d5e3046c2ed18e6a4d2f11878ffc"
)
ATTEMPT_ID = "S1-THREE-HELD-OUT-CURRENT-SOURCE-REPARSE-R4-CLEAN-PROOF-A3"
PREDECESSOR_FAILURE_REFS = (
    Path(
        "configs/releases/fin_ia_0_1_3_s1_three_held_out_current_source_"
        "reparse_successor_r4_clean_independent_proof_a1_failure_v1_0.json"
    ),
    Path(
        "configs/releases/fin_ia_0_1_3_s1_three_held_out_current_source_"
        "reparse_successor_r4_clean_independent_proof_a2_failure_v1_0.json"
    ),
)
SCRUBBED_ENVIRONMENT_MARKERS = (
    "API_KEY",
    "AUTHORIZATION",
    "ACCESS_TOKEN",
    "COOKIE",
    "PASSWORD",
    "SECRET",
)


class CleanReparseProofError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise CleanReparseProofError(code)


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


def _assert_committed_source_synced() -> dict[str, Any]:
    _require(not _git("diff", "--name-only"), "source_tracked_worktree_not_clean")
    _require(
        not _git("diff", "--cached", "--name-only"),
        "source_index_not_clean",
    )
    head = _git("rev-parse", "HEAD")
    upstream = _git("rev-parse", "@{upstream}")
    _require(head == upstream, "source_head_not_synced_to_upstream")
    return {
        "commit": head,
        "upstream_commit": upstream,
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "tracked_clean": True,
        "archive_excludes_untracked_files": True,
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
        for member in archive.getmembers():
            resolved = (target / member.name).resolve()
            try:
                resolved.relative_to(target)
            except ValueError as exc:
                raise CleanReparseProofError("git_archive_member_outside_root") from exc
        # Python 3.11 does not expose the newer ``filter=`` parameter.  The
        # complete member list was already resolved and checked above, so the
        # compatibility extraction retains the same traversal boundary.
        archive.extractall(target)
    archive_path.unlink()


def _selected_capture_descriptor(
    *,
    case_key: str,
    selector: str,
    public_result: Mapping[str, Any],
) -> Mapping[str, Any]:
    if selector == "held_out_case_source":
        matches = [
            row
            for row in public_result.get("source_results") or []
            if str(row.get("case_key") or "") == case_key
        ]
        _require(len(matches) == 1, f"capture_case_selection_invalid:{case_key}")
        descriptor = matches[0].get("source") or {}
    elif selector == "selected_detailed_source":
        descriptor = public_result.get("selected_detailed_source") or {}
    else:
        raise CleanReparseProofError(f"capture_selector_unsupported:{selector}")
    _require(bool(descriptor), f"capture_descriptor_missing:{case_key}")
    return descriptor


def _copy_bound_captures(archive_root: Path) -> list[dict[str, Any]]:
    policy = _load(ROOT / POLICY_REF)
    artifacts = {
        str(row["artifact_id"]): row
        for row in policy.get("locked_artifacts") or []
    }
    copied: list[dict[str, Any]] = []
    for binding in policy.get("source_bindings") or []:
        case_key = str(binding["case_key"])
        artifact = artifacts[str(binding["source_result_artifact_id"])]
        public_result = _load(ROOT / str(artifact["path"]))
        descriptor = _selected_capture_descriptor(
            case_key=case_key,
            selector=str(binding["source_result_selector"]),
            public_result=public_result,
        )
        runtime_ref = Path(
            str((public_result.get("public_private_separation") or {})["runtime_root_ref"])
        )
        _require(not runtime_ref.is_absolute(), "capture_runtime_ref_absolute")
        object_ref = Path(PurePosixPath(str(descriptor["response_capture_ref"])))
        _require(not object_ref.is_absolute(), "capture_object_ref_absolute")
        source = (ROOT / runtime_ref / "objects" / object_ref).resolve()
        destination = (archive_root / runtime_ref / "objects" / object_ref).resolve()
        try:
            source.relative_to(ROOT)
            destination.relative_to(archive_root)
        except ValueError as exc:
            raise CleanReparseProofError("capture_copy_path_outside_root") from exc
        expected_digest = str(descriptor["response_capture_digest"])
        _require(source.is_file(), f"capture_source_missing:{case_key}")
        _require(_sha256(source) == expected_digest, f"capture_source_digest_drift:{case_key}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        _require(_sha256(destination) == expected_digest, f"capture_copy_digest_drift:{case_key}")
        copied.append(
            {
                "case_key": case_key,
                "response_capture_ref": PurePosixPath(object_ref).as_posix(),
                "response_capture_digest": expected_digest,
                "bytes": destination.stat().st_size,
            }
        )
    _require([row["case_key"] for row in copied] == ["ORCL", "ASML", "ANET"], "capture_case_order_drift")
    _require(len({row["response_capture_digest"] for row in copied}) == 3, "capture_digest_not_unique")
    return copied


def _blocked_network(*args: Any, **kwargs: Any) -> Any:
    raise CleanReparseProofError("clean_reparse_proof_network_forbidden")


def _worker_payload(runtime_root: Path) -> dict[str, Any]:
    sys.path.insert(0, str(runtime_root))
    sys.path.insert(0, str(runtime_root / "src"))
    os.chdir(runtime_root)
    socket.socket.connect = _blocked_network  # type: ignore[method-assign]
    socket.socket.connect_ex = _blocked_network  # type: ignore[method-assign]
    socket.create_connection = _blocked_network

    from sec_agent.financial_research_current_source_reparse import (
        execute_current_source_reparse,
        load_current_source_reparse_policy,
        validate_current_source_reparse_result,
    )
    from sec_agent.project_os_preflight import run_project_os_preflight

    preflight = run_project_os_preflight(runtime_root, run_scope=CURRENT_SCOPE)
    _require(preflight.get("status") == "pass", "clean_scope_preflight_failed")
    _require(not preflight.get("contract_errors"), "clean_scope_contract_error")
    committed = _load(runtime_root / SOURCE_RESULT_REF)
    _require(
        str(committed.get("result_digest") or "") == EXPECTED_RESULT_DIGEST,
        "committed_result_digest_unexpected",
    )
    policy = load_current_source_reparse_policy(
        runtime_root / POLICY_REF,
        repo_root=runtime_root,
    )
    execution_root = (
        runtime_root
        / "data/workbench_private/fin_0_1_3_s1_three_held_out_current_source_reparse/clean-proof-r4"
    )
    _require(not execution_root.exists(), "clean_worker_execution_root_exists")
    reproduced = execute_current_source_reparse(
        policy=policy,
        repo_root=runtime_root,
        runtime_root=execution_root,
    )
    validate_current_source_reparse_result(reproduced)
    _require(
        _canonical_bytes(reproduced) == _canonical_bytes(committed),
        "clean_worker_result_not_exact_match",
    )
    observed_calls = reproduced["observed_calls"]
    _require(set(observed_calls.values()) == {0}, "clean_worker_nonzero_call")
    return {
        "schema_version": "fin_ia_0_1_3_s1_three_held_out_current_source_reparse_r4_clean_worker_v1_0",
        "status": "pass",
        "preflight_scope": CURRENT_SCOPE,
        "preflight": "pass",
        "matches_committed_result": True,
        "result_digest": reproduced["result_digest"],
        "case_bundle_counts": [
            row["observed_counts"]["bundle_projected"]
            for row in reproduced["case_results"]
        ],
        "case_slot_counts": [
            len(row["projected_slot_ids"])
            for row in reproduced["case_results"]
        ],
        "case_admitted_table_metrics": [
            row["observed_counts"]["admitted_table_metrics"]
            for row in reproduced["case_results"]
        ],
        "case_typed_rejects": [
            row["observed_counts"]["rejected_table_metrics"]
            for row in reproduced["case_results"]
        ],
        "mutations_passed": [
            sum(bool(row["passed"]) for row in reproduced["mutation_results"]),
            len(reproduced["mutation_results"]),
        ],
        "observed_calls": observed_calls,
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
    completed = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve()),
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
        + completed.stdout[-3000:]
        + ":"
        + completed.stderr[-3000:],
    )
    _require(output_path.is_file(), "fresh_worker_output_missing")
    return _load(output_path)


def build_result() -> dict[str, Any]:
    git_state = _assert_committed_source_synced()
    committed = _load(ROOT / SOURCE_RESULT_REF)
    _require(
        str(committed.get("result_digest") or "") == EXPECTED_RESULT_DIGEST,
        "source_result_digest_unexpected",
    )
    source_bindings = {
        ref.as_posix(): _sha256(ROOT / ref)
        for ref in (
            POLICY_REF,
            SOURCE_RESULT_REF,
            Path("src/sec_agent/financial_research_current_source_reparse.py"),
            Path("src/sec_agent/financial_research_candidate_bundle_v2.py"),
            Path("src/evidence/structured_extractor.py"),
        )
    }
    workers: list[dict[str, Any]] = []
    capture_manifests: list[list[dict[str, Any]]] = []
    with tempfile.TemporaryDirectory(prefix="fin013-s1-held-out-reparse-r4-clean-proof-") as parent:
        parent_path = Path(parent).resolve()
        _require(
            parent_path.name.startswith("fin013-s1-held-out-reparse-r4-clean-proof-"),
            "temporary_root_invalid",
        )
        for ordinal in (1, 2):
            archive_root = parent_path / f"clean-archive-{ordinal}"
            _extract_clean_archive(git_state["commit"], archive_root)
            capture_manifests.append(_copy_bound_captures(archive_root))
            workers.append(
                _run_worker(
                    archive_root,
                    archive_root / f"worker-result-{ordinal}.json",
                )
            )
        _require(
            _canonical_bytes(workers[0]) == _canonical_bytes(workers[1]),
            "fresh_worker_outputs_differ",
        )
        _require(
            _canonical_bytes({"rows": capture_manifests[0]})
            == _canonical_bytes({"rows": capture_manifests[1]}),
            "capture_manifests_differ",
        )

    _require(_git("rev-parse", "HEAD") == git_state["commit"], "source_head_changed")
    _require(not _git("diff", "--name-only"), "source_tracked_worktree_changed")
    _require(
        all(_sha256(ROOT / ref) == digest for ref, digest in source_bindings.items()),
        "source_binding_changed_during_proof",
    )
    proof_runs = [
        {"run_id": f"archive-{label}", **worker}
        for label, worker in zip(("a", "b"), workers, strict=True)
    ]
    body = {
        "schema_version": "fin_ia_0_1_3_s1_three_held_out_current_source_reparse_successor_r4_clean_independent_proof_v1_0",
        "contract_ref": "fin_0_1_3.S1.three_held_out_current_source_reparse_successor_r4_clean_independent_proof:v1",
        "recorded_at": "2026-08-10",
        "attempt_id": ATTEMPT_ID,
        "predecessor_failure_refs": [
            ref.as_posix() for ref in PREDECESSOR_FAILURE_REFS
        ],
        "source_commit": git_state["commit"],
        "source_git_state": git_state,
        "source_result_ref": SOURCE_RESULT_REF.as_posix(),
        "source_result_digest": EXPECTED_RESULT_DIGEST,
        "source_bindings": source_bindings,
        "preparer_sha256": _sha256(Path(__file__).resolve()),
        "proof_method": {
            "git_archives": 2,
            "fresh_python_processes": 2,
            "archive_shared_code_directory": False,
            "capture_copy_mode": "three_exact_publicly_referenced_response_capture_objects_only",
            "capture_digest_verification": True,
            "project_os_preflight_each_archive": True,
            "credential_environment_scrubbed": True,
            "socket_network_blocked": True,
        },
        "capture_manifest": capture_manifests[0],
        "proof_runs": proof_runs,
        "observed_calls_each_run": {
            "network": 0,
            "provider": 0,
            "model": 0,
            "embedding": 0,
            "rerank": 0,
            "evidence_promotion": 0,
        },
        "stage_acceptance": {
            "clean_independent_reproof": True,
            "table_semantic_coordinate_engineering": True,
            "candidate_bundle_only_sparse_dense_manifest_rebaseline_admitted": True,
            "real_embedding_or_index_build": False,
            "ranking": False,
            "held_out_product_generalization": False,
            "external_residual_supplement": False,
            "model_research_synthesis": False,
            "release": False,
        },
        "decision_zh": (
            "两个独立 Git archive 在两个 fresh process 中仅注入三份 digest-bound 原始响应，"
            "均逐字节重现 R4 result。旧 R1 可复现事实继续保留，但索引授权正式改由 R4；"
            "下一步只准入 CandidateBundle-only manifest 重定基，不准入真实 BGE、Milvus、"
            "ranking、Evidence、外源补源或 DeepSeek。"
        ),
        "known_boundary": (
            "This proof establishes clean reproducibility of the R4 table-coordinate "
            "successor only. It does not establish a physical index, ranking quality, "
            "Evidence Pack completeness, external coverage, model synthesis, report "
            "quality or release readiness."
        ),
    }
    return {**body, "result_digest": _canonical_digest(body)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / PROOF_REF)
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
                    "status": "pass",
                    "source_commit": payload["source_commit"],
                    "source_result_digest": payload["source_result_digest"],
                    "proof_digest": payload["result_digest"],
                    "proof_runs": len(payload["proof_runs"]),
                    "output": str(args.output),
                },
                ensure_ascii=False,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
