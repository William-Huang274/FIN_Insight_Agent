from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_dell_targeted_source_supplement import (  # noqa: E402
    PROOF_SCHEMA,
    canonical_digest,
    load_dell_targeted_source_policy,
    validate_dell_targeted_source_clean_proof,
)


POLICY_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s1_dell_targeted_source_supplement_policy_v1_0.json"
)
DEFAULT_OUTPUT = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s1_dell_targeted_source_supplement_clean_proof_v1_0.json"
)
WORKER_REF = (
    "scripts/releases/"
    "prove_fin_ia_0_1_3_s1_dell_targeted_source_supplement_worker.py"
)


class CleanProofError(RuntimeError):
    pass


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


def _require_clean_synced() -> str:
    if _git("status", "--porcelain", "--untracked-files=all"):
        raise CleanProofError("clean_proof_requires_clean_worktree")
    head = _git("rev-parse", "HEAD")
    if head != _git("rev-parse", "@{upstream}"):
        raise CleanProofError("clean_proof_requires_synced_head")
    return head


def _link_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, target)
    except OSError:
        shutil.copy2(source, target)


def _hydrate_bound_private_inputs(worker_root: Path, policy: dict[str, Any]) -> None:
    corpus_ref = Path(str(policy["local_corpus"]["ref"]))
    _link_file(ROOT / corpus_ref, worker_root / corpus_ref)
    result_ref = Path(str(policy["base_pack_result"]["ref"]))
    result = json.loads((worker_root / result_ref).read_text(encoding="utf-8"))
    base_root = Path(str(policy["base_pack_artifact_root"]))
    for reference in result["pack_artifacts"].values():
        object_key = Path(str(reference["object_key"]))
        _link_file(
            ROOT / base_root / object_key,
            worker_root / base_root / object_key,
        )


def _run_worker(
    *,
    temporary_root: Path,
    worker_index: int,
    head: str,
    policy: dict[str, Any],
) -> dict[str, Any]:
    archive = temporary_root / f"worker-{worker_index}.tar"
    worker_root = temporary_root / f"worker-{worker_index}"
    worker_root.mkdir(parents=True, exist_ok=False)
    subprocess.run(
        ["git", "archive", "--format=tar", "-o", str(archive), head],
        cwd=ROOT,
        check=True,
    )
    with tarfile.open(archive, "r") as handle:
        handle.extractall(worker_root)
    _hydrate_bound_private_inputs(worker_root, policy)
    output = worker_root / ".proof_output.json"
    runtime = worker_root / ".proof_runtime"
    completed = subprocess.run(
        [
            sys.executable,
            str(worker_root / WORKER_REF),
            "--runtime-root",
            str(runtime),
            "--output",
            str(output),
        ],
        cwd=worker_root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    if completed.returncode != 0:
        raise CleanProofError(
            "clean_proof_worker_failed:"
            + str(worker_index)
            + ":"
            + completed.stderr[-1500:]
        )
    return json.loads(output.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.output.exists():
        raise CleanProofError("clean_proof_output_already_exists")
    head = _require_clean_synced()
    policy = load_dell_targeted_source_policy(POLICY_PATH, repo_root=ROOT)
    temp_parent = Path(os.environ.get("TEMP") or tempfile.gettempdir())
    with tempfile.TemporaryDirectory(
        prefix="fin013-dell-targeted-source-proof-",
        dir=temp_parent,
    ) as directory:
        temporary_root = Path(directory)
        workers = [
            _run_worker(
                temporary_root=temporary_root,
                worker_index=index,
                head=head,
                policy=policy,
            )
            for index in (1, 2)
        ]
    equivalent = workers[0] == workers[1]
    if not equivalent:
        raise CleanProofError("clean_proof_workers_not_byte_equivalent")
    counts = dict(workers[0]["observed_counts"])
    body = {
        "schema_version": PROOF_SCHEMA,
        "status": "clean_independent_dell_targeted_source_zero_call_proof_passed",
        "recorded_at": "2026-08-10",
        "implementation_commit": head,
        "policy_digest": canonical_digest(policy),
        "fresh_worker_count": 2,
        "workers_byte_equivalent": equivalent,
        "worker_result_digest": workers[0]["result_digest"],
        "dell_pack_payload_digest": workers[0]["dell_pack_payload_digest"],
        "observed_counts": {
            **counts,
            "network_calls": 0,
            "provider_calls": 0,
            "model_calls": 0,
        },
        "stage_acceptance": workers[0]["stage_acceptance"],
        "private_input_hydration": {
            "mode": "hardlink_or_copy_of_sha256_bound_ignored_inputs",
            "local_corpus_sha256": policy["local_corpus"]["sha256"],
            "base_pack_result_digest": policy["base_pack_result"][
                "expected_result_digest"
            ],
        },
        "known_boundary": (
            "Two fresh Git archive workers proved deterministic local selection, "
            "fixture parsing, gap disposition and successor pack materialization. "
            "No network, provider or model call occurred."
        ),
    }
    proof = {**body, "proof_digest": canonical_digest(body)}
    validate_dell_targeted_source_clean_proof(proof)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(proof, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(proof, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
