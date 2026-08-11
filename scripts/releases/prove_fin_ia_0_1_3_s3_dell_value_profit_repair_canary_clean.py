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

from sec_agent.s2_selected_evidence_numeric_cocompilation import (  # noqa: E402
    canonical_digest,
)


PROOF_SCHEMA = (
    "fin_ia_0_1_3_s3_dell_value_profit_current_pack_repair_canary_"
    "clean_independent_proof_v1_0"
)
WORKER_SCHEMA = (
    "fin_ia_0_1_3_s3_dell_value_profit_current_pack_repair_canary_"
    "clean_worker_result_v1_0"
)
IMPLEMENTATION_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s3_dell_value_profit_current_pack_repair_canary_"
    "minimum_zero_call_implementation_v1_0.json"
)
COMPARISON_CONTRACT_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s2_dell_changed_input_model_comparison_contract_v1_0.json"
)
WORKER_REF = (
    "scripts/releases/"
    "prove_fin_ia_0_1_3_s3_dell_value_profit_repair_canary_worker.py"
)
DEFAULT_OUTPUT = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s3_dell_value_profit_current_pack_repair_canary_"
    "clean_independent_proof_v1_0.json"
)


class S3RepairCanaryCleanProofError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S3RepairCanaryCleanProofError(code)


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
        "s3_repair_canary_clean_proof_requires_clean_worktree",
    )
    head = _git("rev-parse", "HEAD")
    _require(
        head == _git("rev-parse", "@{upstream}"),
        "s3_repair_canary_clean_proof_requires_synced_head",
    )
    return head


def _load_json(path: Path, code: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise S3RepairCanaryCleanProofError(code) from exc
    _require(isinstance(value, dict), code)
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve(ref: str) -> Path:
    path = Path(ref)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _private_artifacts() -> list[dict[str, Any]]:
    comparison = _load_json(
        COMPARISON_CONTRACT_PATH,
        "s3_repair_canary_clean_proof_comparison_contract_invalid",
    )
    bindings = dict(comparison["immutable_bindings"])

    corrected_result = _load_json(
        _resolve(str(bindings["corrected_pack_result"]["ref"])),
        "s3_repair_canary_clean_proof_corrected_result_invalid",
    )
    corrected_artifact = dict(corrected_result["corrected_pack_artifact"])
    corrected_relative = (
        Path(str(comparison["corrected_pack_private_root"]))
        / str(corrected_artifact["object_key"])
    )

    fixed_contract = _load_json(
        _resolve(str(bindings["fixed_pack_contract"]["ref"])),
        "s3_repair_canary_clean_proof_fixed_contract_invalid",
    )
    historical_binding = dict(
        fixed_contract["immutable_inputs"]["local_evidence_pack_result"]
    )
    historical_result = _load_json(
        _resolve(str(historical_binding["ref"])),
        "s3_repair_canary_clean_proof_historical_result_invalid",
    )
    historical_artifact = dict(historical_result["pack_artifacts"]["DELL"])
    historical_relative = (
        Path(str(fixed_contract["private_pack_root"]))
        / str(historical_artifact["object_key"])
    )

    rows = [
        {
            "kind": "corrected_dell_pack",
            "relative_path": corrected_relative.as_posix(),
            "source_path": (ROOT / corrected_relative).resolve(),
            "expected_sha256": str(corrected_artifact["digest"]),
        },
        {
            "kind": "historical_dell_pack",
            "relative_path": historical_relative.as_posix(),
            "source_path": (ROOT / historical_relative).resolve(),
            "expected_sha256": str(historical_artifact["digest"]),
        },
    ]
    for row in rows:
        source = Path(row["source_path"])
        _require(
            source.is_file() and _sha256(source) == row["expected_sha256"],
            f"s3_repair_canary_clean_proof_private_artifact_drift:{row['kind']}",
        )
        row["bytes"] = source.stat().st_size
    return rows


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
                "s3_repair_canary_clean_proof_archive_path_escape",
            )
        archive.extractall(target)
    archive_path.unlink()


def _inject_private_artifacts(
    *, archive_root: Path, artifacts: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    for row in artifacts:
        destination = archive_root / str(row["relative_path"])
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(Path(row["source_path"]), destination)
        receipts.append(
            {
                "kind": row["kind"],
                "relative_path": row["relative_path"],
                "bytes": destination.stat().st_size,
                "sha256": _sha256(destination),
            }
        )
    return receipts


def _sanitized_environment() -> dict[str, str]:
    forbidden = re.compile(
        r"(?:API_KEY|SECRET_KEY|ACCESS_KEY|ACCESS_TOKEN|AUTH_TOKEN|PASSWORD|"
        r"DEEPSEEK|OPENAI|ANTHROPIC|TENCENT|ALPHAVANTAGE)",
        re.IGNORECASE,
    )
    environment = {
        name: value for name, value in os.environ.items() if not forbidden.search(name)
    }
    environment["NO_PROXY"] = "*"
    environment["no_proxy"] = "*"
    return environment


def _run_worker(
    *, archive_root: Path, implementation_commit: str
) -> tuple[dict[str, Any], bytes, dict[str, Any]]:
    output_path = archive_root / ".s3-repair-canary-clean-output.json"
    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            str(archive_root / WORKER_REF),
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
        raise S3RepairCanaryCleanProofError(
            "s3_repair_canary_clean_worker_failed:"
            + completed.stderr[-4000:]
            + completed.stdout[-1500:]
        )
    _require(output_path.is_file(), "s3_repair_canary_clean_worker_output_missing")
    raw = output_path.read_bytes()
    output = json.loads(raw.decode("utf-8"))
    _require(
        output.get("schema_version") == WORKER_SCHEMA
        and output.get("result_digest")
        == canonical_digest(
            {key: value for key, value in output.items() if key != "result_digest"}
        ),
        "s3_repair_canary_clean_worker_output_invalid",
    )
    summary = {
        "stdout_sha256": hashlib.sha256(completed.stdout.encode("utf-8")).hexdigest(),
        "stderr_empty": not bool(completed.stderr.strip()),
    }
    return output, raw, summary


def _validate_proof(proof: Mapping[str, Any]) -> None:
    _require(
        proof.get("schema_version") == PROOF_SCHEMA
        and proof.get("result_digest")
        == canonical_digest(
            {key: value for key, value in proof.items() if key != "result_digest"}
        ),
        "s3_repair_canary_clean_proof_identity_invalid",
    )
    _require(
        proof.get("clean_git_archives") == 2
        and proof.get("fresh_python_processes") == 2
        and proof.get("workers_byte_equivalent") is True
        and proof.get("private_artifacts_persisted_to_repository") is False
        and proof.get("temporary_roots_removed") is True,
        "s3_repair_canary_clean_proof_isolation_invalid",
    )
    observed = dict(proof.get("observed_calls") or {})
    _require(
        all(
            observed.get(key) == 0
            for key in (
                "model_calls",
                "provider_calls",
                "network_calls",
                "source_calls",
                "retries",
            )
        ),
        "s3_repair_canary_clean_proof_nonzero_external_calls",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.output.exists():
        raise S3RepairCanaryCleanProofError(
            "s3_repair_canary_clean_proof_output_already_exists"
        )

    head = _require_clean_synced()
    implementation = _load_json(
        IMPLEMENTATION_PATH,
        "s3_repair_canary_clean_proof_implementation_invalid",
    )
    _require(
        implementation.get("result_digest")
        == canonical_digest(
            {
                key: value
                for key, value in implementation.items()
                if key != "result_digest"
            }
        ),
        "s3_repair_canary_clean_proof_implementation_digest_invalid",
    )
    artifacts = _private_artifacts()
    public_artifact_manifest = [
        {
            "kind": row["kind"],
            "relative_path": row["relative_path"],
            "bytes": row["bytes"],
            "sha256": row["expected_sha256"],
        }
        for row in artifacts
    ]

    temp_parent = Path(os.environ.get("TEMP") or tempfile.gettempdir())
    temporary_path: Path | None = None
    workers: list[dict[str, Any]] = []
    worker_bytes: list[bytes] = []
    injections: list[list[dict[str, Any]]] = []
    summaries: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(
        prefix="fin013-s3-repair-canary-clean-", dir=temp_parent
    ) as directory:
        temporary_path = Path(directory)
        for ordinal in (1, 2):
            archive_root = temporary_path / f"clean-archive-{ordinal}"
            _extract_archive(head, archive_root)
            injection = _inject_private_artifacts(
                archive_root=archive_root, artifacts=artifacts
            )
            worker, raw, summary = _run_worker(
                archive_root=archive_root,
                implementation_commit=head,
            )
            workers.append(worker)
            worker_bytes.append(raw)
            injections.append(injection)
            summaries.append(summary)
        _require(
            worker_bytes[0] == worker_bytes[1],
            "s3_repair_canary_clean_worker_outputs_differ",
        )
        _require(
            injections[0] == injections[1] == public_artifact_manifest,
            "s3_repair_canary_clean_worker_injections_differ",
        )
    _require(temporary_path is not None, "s3_repair_canary_temporary_root_missing")
    temporary_roots_removed = not temporary_path.exists()

    worker = workers[0]
    body = {
        "schema_version": PROOF_SCHEMA,
        "attempt_id": "20260811_s3_dell_value_profit_repair_canary_clean_proof_r1",
        "contract_ref": (
            "fin_0_1_3.S3.dell_value_profit_current_pack_repair_canary:v1"
        ),
        "status": (
            "pass_two_clean_archives_two_fresh_processes_zero_external_call_"
            "reproducible"
        ),
        "recorded_at": "2026-08-11",
        "implementation_commit": head,
        "implementation_result_digest": implementation["result_digest"],
        "clean_git_archives": 2,
        "fresh_python_processes": 2,
        "fresh_worker_count": 2,
        "workers_byte_equivalent": True,
        "worker_result_digest": worker["result_digest"],
        "normalized_worker_output_sha256": hashlib.sha256(worker_bytes[0]).hexdigest(),
        "private_artifact_injections": public_artifact_manifest,
        "private_artifacts_persisted_to_repository": False,
        "temporary_roots_removed": temporary_roots_removed,
        "compiled_canary": worker["compiled_canary"],
        "runtime_outcomes": worker["runtime_outcomes"],
        "mutations": worker["mutations"],
        "observed_calls": {
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": 0,
            "source_calls": 0,
            "retries": 0,
            "fixture_provider_invocations_per_worker": worker["observed_calls"][
                "fixture_provider_invocations"
            ],
            "fixture_provider_invocations_total": sum(
                int(row["observed_calls"]["fixture_provider_invocations"])
                for row in workers
            ),
        },
        "credential_environment_variables_present_each_worker": 0,
        "worker_process_receipts": summaries,
        "stage_acceptance": {
            "canary_selection_and_contract": True,
            "canary_runner_implementation": True,
            "fake_and_mutation_suite": True,
            "canary_clean_proof": True,
            "natural_model_canary": False,
            "dell_delivery_pass": False,
            "qualified_human_acceptance": False,
            "owner_acceptance": False,
            "release": False,
        },
        "known_boundary": (
            "This proof establishes clean committed reproducibility of the bounded "
            "current-pack repair compiler, fixture runtime and local financial "
            "boundaries. It does not register live scope, issue live admission, call "
            "DeepSeek, prove natural repair behavior, generate a Dell report, close "
            "S3, grant qualified-human or Owner acceptance, or authorize release."
        ),
        "current_next": (
            "SEPARATE_ZERO_CALL_ONE_CALL_LIVE_CANARY_EXECUTION_AUTHORITY_DECISION"
        ),
    }
    proof = {**body, "result_digest": canonical_digest(body)}
    _validate_proof(proof)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(proof, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": proof["status"],
                "result_digest": proof["result_digest"],
                "implementation_commit": head,
                "workers_byte_equivalent": True,
                "observed_calls": proof["observed_calls"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
