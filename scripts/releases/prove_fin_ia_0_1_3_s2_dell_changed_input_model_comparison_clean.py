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

from sec_agent.s1_six_case_local_evidence_pack import canonical_digest  # noqa: E402
from sec_agent.s2_dell_changed_input_model_comparison import (  # noqa: E402
    PROOF_SCHEMA,
    RUN_SCOPE,
    load_changed_input_comparison_contract,
    validate_changed_input_clean_proof,
)


CONTRACT_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s2_dell_changed_input_model_comparison_contract_v1_0.json"
)
DEFAULT_OUTPUT = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s2_dell_changed_input_model_comparison_clean_proof_v1_0.json"
)
WORKER_REF = (
    "scripts/releases/"
    "prove_fin_ia_0_1_3_s2_dell_changed_input_model_comparison_worker.py"
)


class ChangedInputCleanProofError(RuntimeError):
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
        raise ChangedInputCleanProofError(
            "changed_input_clean_proof_requires_clean_worktree"
        )
    head = _git("rev-parse", "HEAD")
    if head != _git("rev-parse", "@{upstream}"):
        raise ChangedInputCleanProofError(
            "changed_input_clean_proof_requires_synced_head"
        )
    return head


def _link_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, target)
    except OSError:
        shutil.copy2(source, target)


def _private_input_refs(contract: dict[str, Any]) -> list[str]:
    corrected_binding = contract["immutable_bindings"]["corrected_pack_result"]
    corrected_result = json.loads(
        (ROOT / corrected_binding["ref"]).read_text(encoding="utf-8")
    )
    corrected_ref = (
        str(contract["corrected_pack_private_root"])
        + "/"
        + str(corrected_result["corrected_pack_artifact"]["object_key"])
    )

    fixed_binding = contract["immutable_bindings"]["fixed_pack_contract"]
    fixed_contract = json.loads(
        (ROOT / fixed_binding["ref"]).read_text(encoding="utf-8")
    )
    pack_result_binding = fixed_contract["immutable_inputs"][
        "local_evidence_pack_result"
    ]
    pack_result = json.loads(
        (ROOT / pack_result_binding["ref"]).read_text(encoding="utf-8")
    )
    historical_ref = (
        str(fixed_contract["private_pack_root"])
        + "/"
        + str(pack_result["pack_artifacts"]["DELL"]["object_key"])
    )
    return [corrected_ref, historical_ref]


def _clean_env() -> dict[str, str]:
    env = dict(os.environ)
    for key in tuple(env):
        upper = key.upper()
        if any(marker in upper for marker in ("API_KEY", "SECRET", "TOKEN", "PASSWORD")):
            env.pop(key, None)
    return env


def _run_worker(
    *,
    temporary_root: Path,
    worker_index: int,
    head: str,
    private_refs: list[str],
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
    for ref in private_refs:
        _link_file(ROOT / ref, worker_root / ref)
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
        env=_clean_env(),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    if completed.returncode != 0:
        raise ChangedInputCleanProofError(
            f"changed_input_clean_worker_failed:{worker_index}:"
            + completed.stderr[-4000:]
            + completed.stdout[-1500:]
        )
    return json.loads(output.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.output.exists():
        raise ChangedInputCleanProofError(
            "changed_input_clean_proof_output_already_exists"
        )
    head = _require_clean_synced()
    contract = load_changed_input_comparison_contract(
        CONTRACT_PATH, repo_root=ROOT
    )
    private_refs = _private_input_refs(contract)
    temp_parent = Path(os.environ.get("TEMP") or tempfile.gettempdir())
    with tempfile.TemporaryDirectory(
        prefix="fin013-s2-dell-changed-input-proof-",
        dir=temp_parent,
    ) as directory:
        temporary_root = Path(directory)
        workers = [
            _run_worker(
                temporary_root=temporary_root,
                worker_index=index,
                head=head,
                private_refs=private_refs,
            )
            for index in (1, 2)
        ]
    if workers[0] != workers[1]:
        raise ChangedInputCleanProofError(
            "changed_input_clean_workers_not_byte_equivalent"
        )
    worker = workers[0]
    body = {
        "schema_version": PROOF_SCHEMA,
        "contract_ref": contract["contract_ref"],
        "run_scope": RUN_SCOPE,
        "status": "clean_independent_changed_input_thirteen_node_proof_passed",
        "recorded_at": "2026-08-10",
        "implementation_commit": head,
        "fresh_worker_count": 2,
        "workers_byte_equivalent": True,
        "credential_environment_scrubbed": True,
        "socket_and_dns_blocked_in_workers": True,
        "worker_digest": worker["worker_digest"],
        "case_input_digest": worker["case_input_digest"],
        "historical_case_input_digest": worker["historical_case_input_digest"],
        "source_pack_digest": worker["source_pack_digest"],
        "numeric_authority_digest": worker["numeric_authority_digest"],
        "terminal_digest": worker["terminal_digest"],
        "terminal_status": worker["terminal_status"],
        "terminal_code": worker["terminal_code"],
        "request_characters": worker["request_characters"],
        "maximum_request_characters": worker["maximum_request_characters"],
        "observed_counts": {
            "fixture_provider_calls_per_worker": worker["observed_counts"][
                "fixture_provider_calls"
            ],
            "request_captures_per_worker": worker["observed_counts"][
                "request_captures"
            ],
            "response_captures_per_worker": worker["observed_counts"][
                "response_captures"
            ],
            "real_provider_calls": 0,
            "model_calls": 0,
            "network_calls": 0,
            "retries": 0,
            "fallbacks": 0,
        },
        "mutations": worker["mutations"],
        "private_input_hydration": {
            "mode": "sha256_bound_ignored_pack_artifacts_only",
            "input_count_per_worker": len(private_refs),
            "refs": private_refs,
        },
        "known_boundary": (
            "Two clean Git archive workers proved fresh thirteen-node wiring, current-Pack "
            "visibility, capacity, capture-first persistence and stable numeric rebinding. "
            "No real model or source call occurred and report quality remains unproven."
        ),
    }
    proof = {**body, "proof_digest": canonical_digest(body)}
    validate_changed_input_clean_proof(proof)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(proof, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(proof, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
