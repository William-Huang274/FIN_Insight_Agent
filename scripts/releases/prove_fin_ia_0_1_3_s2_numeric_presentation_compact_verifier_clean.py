from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Mapping
import zipfile


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_six_case_local_evidence_pack import (  # noqa: E402
    canonical_digest,
    file_sha256,
)


REPLAY_SCRIPT = Path(
    "scripts/releases/"
    "prove_fin_ia_0_1_3_s2_numeric_presentation_compact_verifier_repair.py"
)
REPLAY_RESULT = Path(
    "configs/releases/"
    "fin_ia_0_1_3_s2_numeric_presentation_compact_verifier_"
    "zero_call_replay_proof_v1_0.json"
)
PRIVATE_PACK_ROOT = Path(
    "data/workbench_private/fin_0_1_3_s1_six_case_local_evidence_pack/"
    "zero-call-r1/objects"
)
PRIVATE_ATTEMPT_ROOT = Path(
    "data/workbench_private/fin_0_1_3_s2_fixed_pack_capture_reuse_successor/"
    "live/attempts/fin013_s2_fixed_pack_dell_successor_f63f66ff0998aa146c7a"
)
BASE_CONTRACT = Path(
    "configs/runtime/fin_ia_0_1_3_s2_fixed_pack_research_contract_v1_0.json"
)
SUCCESSOR_CONTRACT = Path(
    "configs/runtime/"
    "fin_ia_0_1_3_s2_dell_fixed_pack_capture_reuse_successor_contract_v1_0.json"
)
DEFAULT_OUTPUT = ROOT / (
    "configs/releases/fin_ia_0_1_3_s2_numeric_presentation_compact_verifier_"
    "clean_independent_proof_v1_0.json"
)
PROOF_SCHEMA = (
    "fin_ia_0_1_3_s2_numeric_presentation_compact_verifier_"
    "clean_independent_proof_v1_0"
)


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


def _clean_environment(*, checkout: Path, blocker_root: Path) -> dict[str, str]:
    env = dict(os.environ)
    for key in tuple(env):
        upper = key.upper()
        if any(
            marker in upper
            for marker in (
                "API_KEY",
                "SECRET",
                "AUTH_TOKEN",
                "PASSWORD",
                "CREDENTIAL",
            )
        ):
            env.pop(key, None)
    env["PYTHONPATH"] = os.pathsep.join(
        (str(blocker_root), str(checkout), str(checkout / "src"))
    )
    return env


def _write_socket_blocker(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "sitecustomize.py").write_text(
        "import socket\n"
        "_original_socket = socket.socket\n"
        "class _BlockedSocket(_original_socket):\n"
        "    def connect(self, *args, **kwargs):\n"
        "        raise RuntimeError('clean_proof_socket_forbidden')\n"
        "    def connect_ex(self, *args, **kwargs):\n"
        "        raise RuntimeError('clean_proof_socket_forbidden')\n"
        "socket.socket = _BlockedSocket\n"
        "def _blocked(*args, **kwargs):\n"
        "    raise RuntimeError('clean_proof_network_forbidden')\n"
        "socket.create_connection = _blocked\n"
        "socket.getaddrinfo = _blocked\n",
        encoding="utf-8",
        newline="\n",
    )


def _copy_private_inputs(checkout: Path) -> None:
    for relative in (PRIVATE_PACK_ROOT, PRIVATE_ATTEMPT_ROOT):
        source = ROOT / relative
        destination = checkout / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, destination)
    base_contract = json.loads((ROOT / BASE_CONTRACT).read_text(encoding="utf-8"))
    successor_contract = json.loads(
        (ROOT / SUCCESSOR_CONTRACT).read_text(encoding="utf-8")
    )
    exact_bound_refs = {
        BASE_CONTRACT,
        SUCCESSOR_CONTRACT,
        *(
            Path(str(row["ref"]))
            for row in base_contract.get("immutable_inputs", {}).values()
        ),
        Path(
            str(successor_contract["predecessor"]["public_result"]["ref"])
        ),
    }
    for relative in exact_bound_refs:
        source = ROOT / relative
        destination = checkout / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def _run_archive_worker(
    *,
    archive_path: Path,
    worker_root: Path,
) -> dict[str, Any]:
    checkout = worker_root / "checkout"
    checkout.mkdir(parents=True)
    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(checkout)
    _copy_private_inputs(checkout)
    blocker_root = worker_root / "socket_blocker"
    _write_socket_blocker(blocker_root)
    completed = subprocess.run(
        [sys.executable, str(checkout / REPLAY_SCRIPT)],
        cwd=checkout,
        env=_clean_environment(checkout=checkout, blocker_root=blocker_root),
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "compact_verifier_archive_worker_failed:"
            + str(completed.stderr or "")[-6000:]
        )
    return json.loads((checkout / REPLAY_RESULT).read_text(encoding="utf-8"))


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temp.replace(path)


def build_clean_proof(*, output_path: Path) -> dict[str, Any]:
    if _git("status", "--porcelain", "--untracked-files=all"):
        raise RuntimeError("compact_verifier_clean_proof_requires_clean_worktree")
    execution_git_commit = _git("rev-parse", "HEAD")
    if _git("rev-list", "--left-right", "--count", "HEAD...@{u}").split() != [
        "0",
        "0",
    ]:
        raise RuntimeError("compact_verifier_clean_proof_requires_synced_branch")
    with tempfile.TemporaryDirectory(prefix="fin013_s2_compact_verifier_") as temp:
        temp_root = Path(temp)
        archive_path = temp_root / "source.zip"
        subprocess.run(
            [
                "git",
                "archive",
                "--format=zip",
                "--output",
                str(archive_path),
                execution_git_commit,
            ],
            cwd=ROOT,
            check=True,
        )
        archive_sha = file_sha256(archive_path)
        worker_a = _run_archive_worker(
            archive_path=archive_path,
            worker_root=temp_root / "worker_a",
        )
        worker_b = _run_archive_worker(
            archive_path=archive_path,
            worker_root=temp_root / "worker_b",
        )
    if worker_a != worker_b:
        raise RuntimeError("compact_verifier_clean_proof_worker_mismatch")
    if not (
        worker_a.get("status") == "zero_call_replay_passed"
        and worker_a.get("numeric_replay", {}).get("repaired", {}).get("total") == 0
        and worker_a.get("compact_verifier", {}).get(
            "shape_complete_fixture_findings"
        )
        == 0
        and worker_a.get("compact_verifier", {}).get(
            "historical_terminal_classification"
        )
        == "verification_incomplete_finish_reason_length"
        and all(
            int(value) == 0
            for value in worker_a.get("observed_counts", {}).values()
        )
    ):
        raise RuntimeError("compact_verifier_clean_proof_worker_result_invalid")
    body = {
        "schema_version": PROOF_SCHEMA,
        "status": "clean_independent_zero_call_proof_passed",
        "product_version": "FIN_0_1_3",
        "owner_stage": "S2",
        "recorded_at": "2026-08-10",
        "execution_git_commit": execution_git_commit,
        "git_archive_sha256": archive_sha,
        "fresh_archive_worker_count": 2,
        "workers_byte_equivalent": True,
        "credential_environment_scrubbed": True,
        "socket_and_dns_blocked_in_workers": True,
        "worker_replay_proof_digest": worker_a["proof_digest"],
        "numeric_replay": deepcopy(worker_a["numeric_replay"]),
        "compact_verifier": deepcopy(worker_a["compact_verifier"]),
        "observed_counts_across_workers": {
            "provider_calls": 0,
            "model_calls": 0,
            "network_calls": 0,
            "retries": 0,
            "fallbacks": 0,
            "business_promotions": 0,
        },
        "acceptance": {
            "historical_raw_outputs_immutable": True,
            "all_material_numeric_surfaces_deterministically_bound": True,
            "fiscal_year_numeric_false_positive_closed": True,
            "numeric_ref_lineage_materialized_locally": True,
            "compact_verifier_claim_coverage_fail_closed": True,
            "selected_captured_source_excerpts_visible_to_verifier": True,
            "length_or_invalid_json_is_hard_incomplete": True,
            "new_live_or_promotion_authority": False,
        },
        "known_boundary": (
            "This proves the S2 numeric and Verifier structure against the saved DELL "
            "candidate in two clean archives. It does not add S1 source coverage, "
            "repair S3 causal/WWC quality, or authorize a model run."
        ),
        "current_next": "S1_TARGETED_DELL_EVIDENCE_SLOT_SUPPLEMENT",
    }
    proof = {**body, "proof_digest": canonical_digest(body)}
    _atomic_json(output_path, proof)
    return proof


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    proof = build_clean_proof(output_path=args.output)
    print(json.dumps(proof, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
