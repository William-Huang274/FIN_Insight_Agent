from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.project_os_preflight import run_project_os_preflight  # noqa: E402
from sec_agent.s1_candidate_bundle_physical_index import (  # noqa: E402
    canonical_digest,
    file_sha256,
    load_physical_index_policy,
    normalized_sha256,
)


POLICY_REF = Path(
    "configs/runtime/"
    "fin_ia_0_1_3_s1_candidate_bundle_physical_index_build_policy_v1_1.json"
)
IMPLEMENTATION_PROOF_REF = Path(
    "configs/releases/"
    "fin_ia_0_1_3_s1_candidate_bundle_physical_index_implementation_proof_v1_1.json"
)
MICROCANARY_POLICY_REF = Path(
    "configs/runtime/"
    "fin_ia_0_1_3_s1_candidate_bundle_physical_store_microcanary_policy_v1_0.json"
)
MICROCANARY_RESULT_REF = Path(
    "configs/releases/"
    "fin_ia_0_1_3_s1_candidate_bundle_physical_store_microcanary_result_v1_0.json"
)
OUTPUT_REF = Path(
    "configs/releases/"
    "fin_ia_0_1_3_s1_candidate_bundle_physical_index_v1_1_clean_proof.json"
)
MATERIALIZER_REF = Path(
    "scripts/releases/"
    "materialize_fin_ia_0_1_3_s1_candidate_bundle_physical_index_implementation_proof_v1_1.py"
)
MICROCANARY_RUNNER_REF = Path(
    "scripts/releases/"
    "run_fin_ia_0_1_3_s1_candidate_bundle_physical_store_microcanary_r1.py"
)


class CandidateBundlePhysicalCleanProofError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise CandidateBundlePhysicalCleanProofError(code)


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def _clean_synced_git() -> dict[str, Any]:
    status = _git("status", "--porcelain", "--untracked-files=all")
    upstream = _git("rev-parse", "@{upstream}")
    head = _git("rev-parse", "HEAD")
    _require(status == "" and head == upstream, "physical_index_v1_1_clean_source_required")
    return {
        "commit": head,
        "upstream_commit": upstream,
        "branch": _git("branch", "--show-current"),
        "clean": True,
        "synced": True,
    }


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), "physical_index_v1_1_json_object_required")
    return value


def _extract_archive(commit: str, target: Path) -> None:
    archive_path = target.parent / f"{target.name}.tar"
    with archive_path.open("wb") as handle:
        completed = subprocess.run(
            ["git", "archive", "--format=tar", commit],
            cwd=ROOT,
            stdout=handle,
            stderr=subprocess.PIPE,
            check=False,
        )
    _require(completed.returncode == 0, "physical_index_v1_1_git_archive_failed")
    target.mkdir(parents=True, exist_ok=False)
    with tarfile.open(archive_path, "r") as archive:
        for member in archive.getmembers():
            resolved = (target / member.name).resolve()
            try:
                resolved.relative_to(target)
            except ValueError as exc:
                raise CandidateBundlePhysicalCleanProofError(
                    "physical_index_v1_1_archive_path_escape"
                ) from exc
        archive.extractall(target)
    archive_path.unlink()


def _copy_private_manifest(archive_root: Path) -> dict[str, Any]:
    policy = load_physical_index_policy(ROOT / POLICY_REF, repo_root=ROOT)
    inputs = dict(policy["immutable_inputs"])
    relative = (
        Path(str(inputs["private_manifest_root_ref"]))
        / str(inputs["private_manifest_object_key"])
    )
    source = (ROOT / relative).resolve()
    destination = (archive_root / relative).resolve()
    source.relative_to(ROOT)
    destination.relative_to(archive_root)
    _require(
        source.is_file()
        and file_sha256(source) == inputs["private_manifest_file_sha256"],
        "physical_index_v1_1_private_manifest_source_invalid",
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    _require(
        file_sha256(destination) == inputs["private_manifest_file_sha256"],
        "physical_index_v1_1_private_manifest_copy_invalid",
    )
    return {
        "relative_ref": relative.as_posix(),
        "sha256": inputs["private_manifest_file_sha256"],
        "bytes": destination.stat().st_size,
    }


def _run_archive(archive_root: Path) -> dict[str, Any]:
    committed_output = archive_root / IMPLEMENTATION_PROOF_REF
    _require(committed_output.is_file(), "physical_index_v1_1_committed_proof_missing")
    committed_output.unlink()
    environment = dict(os.environ)
    for name in tuple(environment):
        upper = name.upper()
        if any(marker in upper for marker in ("API_KEY", "SECRET", "TOKEN", "PASSWORD")):
            environment.pop(name, None)
    environment.update(
        {
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "HF_DATASETS_OFFLINE": "1",
        }
    )
    tests = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/contract/test_fin_0_1_3_s1_candidate_bundle_physical_index.py",
            "-q",
        ],
        cwd=archive_root,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=180,
    )
    subprocess.run(
        [sys.executable, MATERIALIZER_REF.as_posix()],
        cwd=archive_root,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=180,
    )
    regenerated = _read(committed_output)
    terminal_line = tests.stdout.strip().splitlines()[-1]
    counts_match = re.search(
        r"(?P<passed>\d+) passed(?:, (?P<skipped>\d+) skipped)?",
        terminal_line,
    )
    _require(counts_match is not None, "physical_index_v1_1_pytest_summary_invalid")
    return {
        "proof_digest": regenerated["proof_digest"],
        "proof_file_sha256": normalized_sha256(committed_output),
        "pytest_counts": {
            "passed": int(counts_match.group("passed")),
            "skipped": int(counts_match.group("skipped") or 0),
        },
        "mutation_count": regenerated["mutation_proof"]["scenario_count"],
        "directory_artifact_digest": regenerated["store_artifact_proof"]["directory"][
            "artifact_digest"
        ],
        "observed_real_calls": regenerated["observed_real_calls"],
    }


def _verify_microcanary_in_wsl(policy: Mapping[str, Any]) -> dict[str, Any]:
    runtime = dict(policy["runtime_contract"])
    repo = str(runtime["repository_root"])
    completed = subprocess.run(
        [
            "wsl",
            "-d",
            str(runtime["distribution"]),
            "--",
            str(runtime["python_executable"]),
            f"{repo}/{MICROCANARY_RUNNER_REF.as_posix()}",
            "--repo-root",
            repo,
            "--policy",
            f"{repo}/{MICROCANARY_POLICY_REF.as_posix()}",
            "--verify-published",
            "--result",
            f"{repo}/{MICROCANARY_RESULT_REF.as_posix()}",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=180,
    )
    return json.loads(completed.stdout)


def main() -> int:
    output = ROOT / OUTPUT_REF
    if output.exists():
        raise RuntimeError("physical_index_v1_1_clean_proof_already_exists")
    git_state = _clean_synced_git()
    policy = load_physical_index_policy(ROOT / POLICY_REF, repo_root=ROOT)
    committed = _read(ROOT / IMPLEMENTATION_PROOF_REF)
    committed_body = {
        key: value for key, value in committed.items() if key != "proof_digest"
    }
    microcanary = _read(ROOT / MICROCANARY_RESULT_REF)
    microcanary_body = {
        key: value for key, value in microcanary.items() if key != "result_digest"
    }
    _require(
        committed.get("proof_digest") == canonical_digest(committed_body)
        and microcanary.get("result_digest") == canonical_digest(microcanary_body)
        and microcanary.get("status")
        == "terminal_succeeded_directory_store_publication_microcanary",
        "physical_index_v1_1_committed_inputs_invalid",
    )
    preflight = run_project_os_preflight(ROOT, run_scope=str(policy["run_scope"]))
    _require(preflight.get("status") == "pass", "physical_index_v1_1_preflight_failed")
    workers: list[dict[str, Any]] = []
    copied: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="fin013-s1-physical-v1-1-clean-") as parent:
        parent_path = Path(parent).resolve()
        for ordinal in (1, 2):
            archive_root = parent_path / f"archive-{ordinal}"
            _extract_archive(git_state["commit"], archive_root)
            copied.append(_copy_private_manifest(archive_root))
            workers.append(_run_archive(archive_root))
    _require(
        workers[0] == workers[1]
        and workers[0]["proof_digest"] == committed["proof_digest"],
        "physical_index_v1_1_clean_archive_mismatch",
    )
    published_reverification = _verify_microcanary_in_wsl(policy)
    source_refs = (
        POLICY_REF,
        IMPLEMENTATION_PROOF_REF,
        MICROCANARY_POLICY_REF,
        MICROCANARY_RESULT_REF,
        MATERIALIZER_REF,
        MICROCANARY_RUNNER_REF,
        Path("src/sec_agent/s1_candidate_bundle_physical_index.py"),
        Path("tests/contract/test_fin_0_1_3_s1_candidate_bundle_physical_index.py"),
    )
    body = {
        "schema_version": "fin_ia_0_1_3_s1_candidate_bundle_physical_index_v1_1_clean_proof",
        "contract_ref": policy["contract_ref"],
        "run_scope": policy["run_scope"],
        "recorded_at": policy["recorded_at"],
        "attempt_id": "20260810_s1_candidate_bundle_physical_index_v1_1_clean_proof_a2",
        "status": "terminal_succeeded_two_clean_archive_reproduction",
        "source_git_state": git_state,
        "source_bindings": {
            ref.as_posix(): normalized_sha256(ROOT / ref) for ref in source_refs
        },
        "private_manifest_copy": copied[0],
        "implementation_proof_digest": committed["proof_digest"],
        "microcanary_result_digest": microcanary["result_digest"],
        "published_microcanary_reverification": published_reverification,
        "proof_runs": [
            {"run_id": f"clean-archive-{index}", **worker}
            for index, worker in enumerate(workers, start=1)
        ],
        "observed_calls_each_archive": workers[0]["observed_real_calls"],
        "stage_acceptance": {
            "two_clean_archive_reproduction": True,
            "directory_microcanary_published_and_reverified": True,
            "r2_authority_issuance": True,
            "r2_execution": False,
            "retrieval_quality": False,
            "evidence": False,
            "external_supplement": False,
            "deepseek": False,
            "release": False,
        },
        "decision_zh": (
            "两个 clean archive 均逐字重现 v1.1 零调用 proof，且已发布的一向量目录型 "
            "microcanary 在 WSL 中只读复核通过。现在只允许另行签发一次 fresh R2；"
            "不得复用 R1 目录或把物理索引成功等同于检索质量。"
        ),
        "known_boundary": (
            "This proof admits a separate exact-once R2 authority decision only. It does not "
            "execute the 93-vector build, search, rank, promote Evidence, supplement externally, "
            "call DeepSeek or accept release."
        ),
    }
    result = {**body, "proof_digest": canonical_digest(body)}
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(output)
    print(
        json.dumps(
            {
                "status": result["status"],
                "proof_runs": result["proof_runs"],
                "published_microcanary_reverification": published_reverification,
                "proof_digest": result["proof_digest"],
                "output": output.as_posix(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
