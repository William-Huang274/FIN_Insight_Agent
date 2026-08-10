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
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.s1_dell_official_source_recovery_successor import (  # noqa: E402
    CONTRACT_REF,
    PROOF_SCHEMA,
    load_dell_official_source_recovery_policy,
    validate_dell_official_source_recovery_clean_proof,
)


POLICY_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s1_dell_official_source_recovery_successor_policy_v1_0.json"
)
DEFAULT_OUTPUT = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s1_dell_official_source_recovery_successor_clean_proof_v1_0.json"
)
WORKER_REF = (
    "scripts/releases/"
    "prove_fin_ia_0_1_3_s1_dell_official_source_recovery_worker.py"
)


class DellOfficialSourceRecoveryCleanProofError(RuntimeError):
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
        raise DellOfficialSourceRecoveryCleanProofError(
            "dell_official_recovery_clean_proof_requires_clean_worktree"
        )
    head = _git("rev-parse", "HEAD")
    if head != _git("rev-parse", "@{upstream}"):
        raise DellOfficialSourceRecoveryCleanProofError(
            "dell_official_recovery_clean_proof_requires_synced_head"
        )
    return head


def _link_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, target)
    except OSError:
        shutil.copy2(source, target)


def _hydrate_private_inputs(
    worker_root: Path, policy: Mapping[str, Any]
) -> list[dict[str, str]]:
    bindings = policy["immutable_bindings"]
    refs = [str(bindings["predecessor_private_pack"]["ref"])]
    for pair in bindings["timeout_capture_pairs"]:
        refs.extend((str(pair["request_ref"]), str(pair["failure_ref"])))
    hydrated: list[dict[str, str]] = []
    for ref in refs:
        source = ROOT / ref
        target = worker_root / ref
        _link_file(source, target)
        hydrated.append({"ref": ref, "sha256": str(_git_file_hash(source))})
    return hydrated


def _git_file_hash(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_worker(
    *,
    temporary_root: Path,
    worker_index: int,
    head: str,
    policy: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, str]]]:
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
    hydrated = _hydrate_private_inputs(worker_root, policy)
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
            "--implementation-commit",
            head,
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
        raise DellOfficialSourceRecoveryCleanProofError(
            f"dell_official_recovery_clean_worker_failed:{worker_index}:"
            + completed.stderr[-3000:]
        )
    return json.loads(output.read_text(encoding="utf-8")), hydrated


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.output.exists():
        raise DellOfficialSourceRecoveryCleanProofError(
            "dell_official_recovery_clean_proof_output_already_exists"
        )
    head = _require_clean_synced()
    policy = load_dell_official_source_recovery_policy(
        POLICY_PATH, repo_root=ROOT
    )
    temp_parent = Path(os.environ.get("TEMP") or tempfile.gettempdir())
    with tempfile.TemporaryDirectory(
        prefix="fin013-dell-official-recovery-proof-",
        dir=temp_parent,
    ) as directory:
        temporary_root = Path(directory)
        worker_pairs = [
            _run_worker(
                temporary_root=temporary_root,
                worker_index=index,
                head=head,
                policy=policy,
            )
            for index in (1, 2)
        ]
    workers = [pair[0] for pair in worker_pairs]
    equivalent = workers[0] == workers[1]
    if not equivalent:
        raise DellOfficialSourceRecoveryCleanProofError(
            "dell_official_recovery_clean_workers_not_byte_equivalent"
        )
    counts = dict(workers[0]["observed_counts"])
    body = {
        "schema_version": PROOF_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "status": (
            "clean_independent_dell_official_source_recovery_zero_call_proof_passed"
        ),
        "recorded_at": "2026-08-10",
        "implementation_commit": head,
        "policy_digest": canonical_digest(policy),
        "fresh_worker_count": 2,
        "workers_byte_equivalent": equivalent,
        "worker_result_digest": workers[0]["result_digest"],
        "successor_pack_payload_digest": workers[0][
            "successor_pack_payload_digest"
        ],
        "observed_counts": counts,
        "gate_status": workers[0]["gate_status"],
        "mutations": workers[0]["mutations"],
        "stage_acceptance": workers[0]["stage_acceptance"],
        "private_input_hydration": {
            "mode": "hardlink_or_copy_of_sha256_bound_ignored_inputs",
            "input_count": len(worker_pairs[0][1]),
            "worker_manifests_equal": worker_pairs[0][1] == worker_pairs[1][1],
            "input_digests": worker_pairs[0][1],
        },
        "known_boundary": (
            "Two fresh Git archive workers proved timeout-capture replay, managed-reader "
            "capture lineage, origin isolation, anchor handling, partial-result retention, "
            "successful TSMC/Alpha reuse and successor Pack materialization. No network "
            "or model call occurred."
        ),
    }
    proof = {**body, "proof_digest": canonical_digest(body)}
    validate_dell_official_source_recovery_clean_proof(proof)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(proof, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(proof, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
