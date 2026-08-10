from __future__ import annotations

import argparse
import hashlib
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

from sec_agent.s1_six_case_local_evidence_pack import (  # noqa: E402
    compile_six_case_local_evidence_packs,
    load_six_case_local_evidence_pack_policy,
)
from sec_agent.s2_dell_changed_input_model_comparison import (  # noqa: E402
    compile_changed_input_case,
    load_changed_input_comparison_contract,
)
from sec_agent.s2_selected_evidence_numeric_cocompilation import (  # noqa: E402
    canonical_bytes,
    canonical_digest,
)


INPUT_SCHEMA = (
    "fin_ia_0_1_3_s2_selected_evidence_numeric_candidate_"
    "cocompilation_clean_proof_input_v1_0"
)
PROOF_SCHEMA = (
    "fin_ia_0_1_3_s2_selected_evidence_numeric_candidate_"
    "cocompilation_clean_independent_proof_v1_0"
)
WORKER_SCHEMA = (
    "fin_ia_0_1_3_s2_selected_evidence_numeric_candidate_"
    "cocompilation_clean_worker_result_v1_0"
)
CASES = ("DELL", "MU", "NVDA", "ORCL", "ASML", "ANET")
SIX_CASE_POLICY_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s1_six_case_local_evidence_pack_policy_v1_0.json"
)
DELL_CONTRACT_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s2_dell_changed_input_model_comparison_contract_v1_0.json"
)
IMPLEMENTATION_RESULT_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s2_selected_evidence_numeric_candidate_"
    "cocompilation_minimum_zero_call_implementation_v1_0.json"
)
WORKER_REF = (
    "scripts/releases/"
    "prove_fin_ia_0_1_3_s2_selected_evidence_numeric_candidate_"
    "cocompilation_worker.py"
)
DEFAULT_OUTPUT = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s2_selected_evidence_numeric_candidate_"
    "cocompilation_clean_independent_proof_v1_0.json"
)


class SelectedEvidenceNumericCocompilationCleanProofError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise SelectedEvidenceNumericCocompilationCleanProofError(code)


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
    _require(
        not _git("status", "--porcelain", "--untracked-files=all"),
        "numeric_cocompilation_clean_proof_requires_clean_worktree",
    )
    head = _git("rev-parse", "HEAD")
    _require(
        head == _git("rev-parse", "@{upstream}"),
        "numeric_cocompilation_clean_proof_requires_synced_head",
    )
    return head


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SelectedEvidenceNumericCocompilationCleanProofError(
            f"numeric_cocompilation_clean_proof_json_invalid:{path.name}"
        ) from exc
    _require(isinstance(value, dict), f"numeric_cocompilation_clean_proof_json_not_object:{path.name}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _compile_private_input_bundle() -> dict[str, Any]:
    dell_contract = load_changed_input_comparison_contract(
        DELL_CONTRACT_PATH,
        repo_root=ROOT,
    )
    dell_material = compile_changed_input_case(
        contract=dell_contract,
        repo_root=ROOT,
    )
    six_case_policy = load_six_case_local_evidence_pack_policy(
        SIX_CASE_POLICY_PATH,
        repo_root=ROOT,
    )
    six_packs, _six_result = compile_six_case_local_evidence_packs(
        policy=six_case_policy,
        repo_root=ROOT,
    )
    packs = {row["case_key"]: row for row in six_packs}
    packs["DELL"] = dell_material["pack"]
    _require(set(packs) == set(CASES), "numeric_cocompilation_clean_proof_case_set_invalid")
    body = {
        "schema_version": INPUT_SCHEMA,
        "case_order": list(CASES),
        "packs": {case_key: packs[case_key] for case_key in CASES},
        "dell_base_case_input": dell_material["case_input"],
        "source_boundary": (
            "Ephemeral private S1 pack payloads are injected into clean S2 workers. "
            "They are not persisted in the repository and this proof does not re-accept S1."
        ),
    }
    return {**body, "bundle_digest": canonical_digest(body)}


def _extract_archive(commit: str, target: Path) -> None:
    archive_path = target.parent / f"{target.name}.tar"
    subprocess.run(
        ["git", "archive", "--format=tar", "-o", str(archive_path), commit],
        cwd=ROOT,
        check=True,
    )
    target.mkdir(parents=True, exist_ok=False)
    with tarfile.open(archive_path, "r") as archive:
        target_root = target.resolve()
        for member in archive.getmembers():
            member_path = (target / member.name).resolve()
            _require(
                member_path == target_root or target_root in member_path.parents,
                "numeric_cocompilation_clean_proof_archive_path_escape",
            )
        archive.extractall(target)
    archive_path.unlink()


def _sanitized_environment() -> dict[str, str]:
    forbidden = re.compile(
        r"(?:API_KEY|SECRET_KEY|ACCESS_KEY|ACCESS_TOKEN|AUTH_TOKEN|PASSWORD|"
        r"DEEPSEEK|OPENAI|ANTHROPIC|TENCENT|ALPHAVANTAGE)",
        re.IGNORECASE,
    )
    environment = {
        name: value
        for name, value in os.environ.items()
        if not forbidden.search(name)
    }
    environment["NO_PROXY"] = "*"
    environment["no_proxy"] = "*"
    return environment


def _run_worker(
    *,
    archive_root: Path,
    input_path: Path,
    implementation_commit: str,
) -> tuple[dict[str, Any], bytes, dict[str, Any]]:
    injected_input = archive_root / ".private_proof_input.json"
    shutil.copy2(input_path, injected_input)
    output_path = archive_root / ".proof_output.json"
    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            str(archive_root / WORKER_REF),
            "--input",
            str(injected_input),
            "--output",
            str(output_path),
            "--implementation-commit",
            implementation_commit,
        ],
        cwd=archive_root,
        env=_sanitized_environment(),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
    )
    if completed.returncode != 0:
        raise SelectedEvidenceNumericCocompilationCleanProofError(
            "numeric_cocompilation_clean_worker_failed:"
            + completed.stderr[-3000:]
            + completed.stdout[-1000:]
        )
    _require(output_path.is_file(), "numeric_cocompilation_clean_worker_output_missing")
    output_bytes = output_path.read_bytes()
    output = json.loads(output_bytes.decode("utf-8"))
    _require(output.get("schema_version") == WORKER_SCHEMA, "numeric_cocompilation_clean_worker_schema_invalid")
    _require(
        output.get("result_digest")
        == canonical_digest({key: value for key, value in output.items() if key != "result_digest"}),
        "numeric_cocompilation_clean_worker_digest_invalid",
    )
    injection = {
        "bytes": injected_input.stat().st_size,
        "sha256": _sha256(injected_input),
    }
    return output, output_bytes, injection


def _validate_proof(proof: Mapping[str, Any]) -> None:
    _require(proof.get("schema_version") == PROOF_SCHEMA, "numeric_cocompilation_clean_proof_schema_invalid")
    _require(
        proof.get("result_digest")
        == canonical_digest({key: value for key, value in proof.items() if key != "result_digest"}),
        "numeric_cocompilation_clean_proof_digest_invalid",
    )
    _require(proof.get("fresh_worker_count") == 2, "numeric_cocompilation_clean_proof_worker_count_invalid")
    _require(proof.get("workers_byte_equivalent") is True, "numeric_cocompilation_clean_proof_workers_not_equal")
    _require(proof.get("temporary_roots_removed") is True, "numeric_cocompilation_clean_proof_temp_not_removed")
    observed = proof.get("observed_calls") or {}
    _require(
        all(observed.get(key) == 0 for key in ("model_calls", "provider_calls", "network_calls", "source_calls", "retries")),
        "numeric_cocompilation_clean_proof_nonzero_calls",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.output.exists():
        raise SelectedEvidenceNumericCocompilationCleanProofError(
            "numeric_cocompilation_clean_proof_output_already_exists"
        )

    head = _require_clean_synced()
    implementation_result = _load_json(IMPLEMENTATION_RESULT_PATH)
    implementation_body = {
        key: value for key, value in implementation_result.items() if key != "result_digest"
    }
    _require(
        implementation_result.get("result_digest") == canonical_digest(implementation_body),
        "numeric_cocompilation_implementation_result_digest_invalid",
    )
    input_bundle = _compile_private_input_bundle()

    temp_parent = Path(os.environ.get("TEMP") or tempfile.gettempdir())
    temporary_path: Path | None = None
    workers: list[dict[str, Any]] = []
    worker_bytes: list[bytes] = []
    injections: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(
        prefix="fin013-s2-numeric-cocompilation-clean-",
        dir=temp_parent,
    ) as directory:
        temporary_path = Path(directory)
        input_path = temporary_path / "private-input.json"
        input_path.write_bytes(canonical_bytes(input_bundle) + b"\n")
        for ordinal in (1, 2):
            archive_root = temporary_path / f"clean-archive-{ordinal}"
            _extract_archive(head, archive_root)
            worker, raw, injection = _run_worker(
                archive_root=archive_root,
                input_path=input_path,
                implementation_commit=head,
            )
            workers.append(worker)
            worker_bytes.append(raw)
            injections.append(injection)
        _require(worker_bytes[0] == worker_bytes[1], "numeric_cocompilation_clean_worker_outputs_differ")
        _require(injections[0] == injections[1], "numeric_cocompilation_clean_worker_inputs_differ")
    _require(temporary_path is not None, "numeric_cocompilation_clean_proof_temp_missing")
    temporary_roots_removed = not temporary_path.exists()

    observed_calls = dict(workers[0]["observed_calls"])
    body = {
        "schema_version": PROOF_SCHEMA,
        "contract_ref": "fin_0_1_3.S2.selected_evidence_numeric_candidate_cocompilation:v1",
        "status": "pass_two_clean_archives_two_fresh_processes_zero_call_reproducible",
        "recorded_at": "2026-08-11",
        "implementation_commit": head,
        "implementation_result_digest": str(implementation_result["result_digest"]),
        "private_input_bundle": {
            "digest": str(input_bundle["bundle_digest"]),
            "persisted_to_repository": False,
            "worker_injections_byte_identical": injections[0] == injections[1],
            "injected_bytes": injections[0]["bytes"],
            "injected_sha256": injections[0]["sha256"],
        },
        "fresh_worker_count": 2,
        "clean_git_archives": 2,
        "fresh_python_processes": 2,
        "workers_byte_equivalent": True,
        "worker_result_digest": str(workers[0]["result_digest"]),
        "normalized_worker_output_sha256": hashlib.sha256(worker_bytes[0]).hexdigest(),
        "temporary_roots_removed": temporary_roots_removed,
        "case_matrix": workers[0]["case_matrix"],
        "successor": workers[0]["successor"],
        "mutations": workers[0]["mutations"],
        "observed_calls": observed_calls,
        "credential_environment_variables_present_each_worker": 0,
        "stage_acceptance": {
            "runtime_implementation": True,
            "six_case_deterministic_replay": True,
            "mutation_suite": True,
            "successor_input_compilation": True,
            "clean_independent_proof": True,
            "natural_model_canary": False,
            "dell_delivery_pass": False,
            "owner_acceptance": False,
            "release": False,
        },
        "known_boundary": (
            "This proof establishes clean-source reproducibility of the S2 selected-Evidence "
            "numeric co-compilation runtime against six immutable, ephemeral S1 Pack payloads. "
            "It does not re-accept S1, test a natural model response, prove report-quality "
            "improvement, authorize a DELL rerun, or establish product/release acceptance."
        ),
        "current_next": (
            "SEPARATE_ZERO_CALL_NATURAL_NODE_CANARY_AUTHORITY_DECISION_NO_AUTOMATIC_MODEL_CALL"
        ),
    }
    proof = {**body, "result_digest": canonical_digest(body)}
    _validate_proof(proof)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(proof, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": proof["status"],
        "result_digest": proof["result_digest"],
        "implementation_commit": head,
        "workers_byte_equivalent": True,
        "observed_calls": observed_calls,
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
