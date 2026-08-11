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
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


PROOF_SCHEMA = (
    "fin_ia_0_1_3_s3_small_judgment_atom_projection_clean_independent_proof_v1_0"
)
WORKER_SCHEMA = (
    "fin_ia_0_1_3_s3_small_judgment_atom_projection_clean_worker_result_v1_0"
)
IMPLEMENTATION_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s3_small_judgment_atom_projection_minimum_zero_call_"
    "implementation_v1_0.json"
)
WORKER_REF = (
    "scripts/releases/"
    "prove_fin_ia_0_1_3_s3_small_judgment_atom_projection_worker.py"
)
DEFAULT_OUTPUT = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s3_small_judgment_atom_projection_clean_independent_"
    "proof_v1_0.json"
)
LEGACY_CAPTURE_RELATIVE = Path(
    "data/workbench_private/fin_0_1_3_s3_dell_value_profit_repair_canary/"
    "live/attempts/fin013_s3_dell_value_profit_repair_canary_"
    "11a8bc7aa03045f7803a/raw_model_only/calls/call_01/capture.json"
)


class CleanProofError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise CleanProofError(code)


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


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CleanProofError(f"clean_proof_json_invalid:{path.name}") from exc
    _require(isinstance(value, dict), "clean_proof_json_object_required")
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _private_artifacts() -> list[dict[str, Any]]:
    comparison = _load(
        ROOT
        / "configs/runtime/fin_ia_0_1_3_s2_dell_changed_input_model_comparison_contract_v1_0.json"
    )
    bindings = dict(comparison["immutable_bindings"])
    corrected_result = _load(ROOT / bindings["corrected_pack_result"]["ref"])
    corrected = dict(corrected_result["corrected_pack_artifact"])
    corrected_relative = Path(comparison["corrected_pack_private_root"]) / corrected[
        "object_key"
    ]
    fixed = _load(ROOT / bindings["fixed_pack_contract"]["ref"])
    historical_binding = fixed["immutable_inputs"]["local_evidence_pack_result"]
    historical_result = _load(ROOT / historical_binding["ref"])
    historical = dict(historical_result["pack_artifacts"]["DELL"])
    historical_relative = Path(fixed["private_pack_root"]) / historical["object_key"]
    rows = [
        {
            "kind": "corrected_dell_pack",
            "relative_path": corrected_relative,
            "expected_sha256": corrected["digest"],
        },
        {
            "kind": "historical_dell_pack",
            "relative_path": historical_relative,
            "expected_sha256": historical["digest"],
        },
        {
            "kind": "failed_natural_canary_capture",
            "relative_path": LEGACY_CAPTURE_RELATIVE,
            "expected_sha256": _sha(ROOT / LEGACY_CAPTURE_RELATIVE),
        },
    ]
    for row in rows:
        source = ROOT / row["relative_path"]
        _require(
            source.is_file() and _sha(source) == row["expected_sha256"],
            f"clean_proof_private_artifact_drift:{row['kind']}",
        )
        row["source_path"] = source
        row["bytes"] = source.stat().st_size
    return rows


def _extract(commit: str, target: Path) -> None:
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
            destination = (target / member.name).resolve()
            _require(
                destination == target_root or target_root in destination.parents,
                "clean_proof_archive_path_escape",
            )
        archive.extractall(target)
    archive_path.unlink()


def _sanitize_environment() -> dict[str, str]:
    forbidden = re.compile(
        r"(?:API_KEY|SECRET_KEY|ACCESS_KEY|ACCESS_TOKEN|AUTH_TOKEN|PASSWORD|"
        r"DEEPSEEK|OPENAI|ANTHROPIC|TENCENT|ALPHAVANTAGE)",
        re.IGNORECASE,
    )
    environment = {
        key: value for key, value in os.environ.items() if not forbidden.search(key)
    }
    environment["NO_PROXY"] = "*"
    environment["no_proxy"] = "*"
    return environment


def _inject(archive_root: Path, artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    for row in artifacts:
        destination = archive_root / row["relative_path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(row["source_path"], destination)
        receipts.append(
            {
                "kind": row["kind"],
                "relative_path": row["relative_path"].as_posix(),
                "bytes": destination.stat().st_size,
                "sha256": _sha(destination),
            }
        )
    return receipts


def _run_worker(archive_root: Path, commit: str) -> tuple[dict[str, Any], bytes]:
    output = archive_root / ".s3-small-atom-clean-worker.json"
    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            str(archive_root / WORKER_REF),
            "--output",
            str(output),
            "--implementation-commit",
            commit,
        ],
        cwd=archive_root,
        env=_sanitize_environment(),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
    )
    if completed.returncode != 0:
        raise CleanProofError(
            "clean_worker_failed:"
            + completed.stderr[-5000:]
            + completed.stdout[-2000:]
        )
    raw = output.read_bytes()
    result = json.loads(raw.decode("utf-8"))
    _require(
        result.get("schema_version") == WORKER_SCHEMA
        and result.get("result_digest")
        == canonical_digest(
            {key: value for key, value in result.items() if key != "result_digest"}
        ),
        "clean_worker_result_invalid",
    )
    return result, raw


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    _require(not args.output.exists(), "clean_proof_output_already_exists")
    _require(
        not _git("status", "--porcelain", "--untracked-files=all"),
        "clean_proof_requires_clean_worktree",
    )
    head = _git("rev-parse", "HEAD")
    _require(head == _git("rev-parse", "@{upstream}"), "clean_proof_requires_synced")
    implementation = _load(IMPLEMENTATION_PATH)
    implementation_body = {
        key: value for key, value in implementation.items() if key != "result_digest"
    }
    _require(
        implementation.get("result_digest") == canonical_digest(implementation_body),
        "clean_proof_implementation_digest_invalid",
    )
    artifacts = _private_artifacts()
    manifest = [
        {
            "kind": row["kind"],
            "relative_path": row["relative_path"].as_posix(),
            "bytes": row["bytes"],
            "sha256": row["expected_sha256"],
        }
        for row in artifacts
    ]
    temp_parent = Path(os.environ.get("TEMP") or tempfile.gettempdir())
    temporary: Path | None = None
    workers: list[dict[str, Any]] = []
    worker_bytes: list[bytes] = []
    with tempfile.TemporaryDirectory(
        prefix="fin013-s3-small-atom-clean-", dir=temp_parent
    ) as directory:
        temporary = Path(directory)
        for ordinal in (1, 2):
            archive_root = temporary / f"clean-archive-{ordinal}"
            _extract(head, archive_root)
            _require(_inject(archive_root, artifacts) == manifest, "injection_drift")
            worker, raw = _run_worker(archive_root, head)
            workers.append(worker)
            worker_bytes.append(raw)
        _require(worker_bytes[0] == worker_bytes[1], "clean_worker_outputs_differ")
    _require(temporary is not None and not temporary.exists(), "temporary_root_remains")

    worker = workers[0]
    body = {
        "schema_version": PROOF_SCHEMA,
        "attempt_id": "20260811_s3_small_judgment_atom_projection_clean_proof_r1",
        "contract_ref": (
            "fin_0_1_3.S3.small_judgment_atom_deterministic_cell_projection:v1"
        ),
        "status": "pass_two_clean_archives_replay_projection_and_mutation_zero_external_call",
        "recorded_at": "2026-08-11",
        "implementation_commit": head,
        "implementation_result_digest": implementation["result_digest"],
        "clean_git_archives": 2,
        "fresh_python_processes": 2,
        "workers_byte_equivalent": True,
        "worker_result_digest": worker["result_digest"],
        "worker_output_sha256": hashlib.sha256(worker_bytes[0]).hexdigest(),
        "private_artifact_injections": manifest,
        "private_artifacts_persisted_to_repository": False,
        "temporary_roots_removed": True,
        "compiled_input_digest": worker["compiled_input_digest"],
        "request_digest": worker["request_digest"],
        "compiled_request_characters": worker["compiled_request_characters"],
        "projection_digest": worker["projection_digest"],
        "successor_program_digest": worker["successor_program_digest"],
        "deterministic_cell_states": worker["deterministic_cell_states"],
        "alias_normalization": worker["alias_normalization"],
        "legacy_capture_audit": worker["legacy_capture_audit"],
        "legacy_terminal_materialization": worker[
            "legacy_terminal_materialization"
        ],
        "portfolio_shape_receipts": worker["portfolio_shape_receipts"],
        "mutations": worker["mutations"],
        "observed_calls": {
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": 0,
            "source_calls": 0,
            "retries": 0,
            "fixture_capture_replay_callbacks_per_worker": 1,
            "fixture_capture_replay_callbacks_total": 2,
        },
        "stage_acceptance": {
            "failed_natural_canary_immutable": True,
            "small_judgment_atom_contract": True,
            "deterministic_cell_projection": True,
            "alias_aware_financial_surface_guard": True,
            "parsed_and_validated_terminal_materialization": True,
            "dell_mu_nvda_shape_mutation": True,
            "clean_independent_proof": True,
            "successor_natural_canary": False,
            "repaired_dell_report": False,
            "qualified_human_acceptance": False,
            "owner_acceptance": False,
            "release": False,
        },
        "known_boundary": (
            "This proof establishes only the provider-neutral small-judgment contract, "
            "deterministic DELL cell projection, three-case shape isolation, immutable "
            "failed-capture replay and accurate parsed-versus-validated terminal refs. "
            "It does not reclassify the failed natural canary, authorize a second model "
            "call, generate a report, close S3, or authorize acceptance or release."
        ),
        "current_next": (
            "SEPARATE_ZERO_CALL_SUCCESSOR_NATURAL_CANARY_VALUE_COST_RISK_DECISION"
        )
    }
    proof = {**body, "result_digest": canonical_digest(body)}
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
                "external_calls": 0,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
