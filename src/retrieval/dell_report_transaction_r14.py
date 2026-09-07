from __future__ import annotations

from dataclasses import dataclass, field
import ctypes
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import shutil
import subprocess
from typing import Any, Callable, Mapping

from .dell_report_r14_common import (
    canonical_digest,
    canonical_json_bytes,
    domain_rows_digest,
    file_sha256,
    read_json,
    require,
    require_identifier,
    require_sha256,
    sha256_bytes,
    with_result_digest,
)


TRANSACTION_MANIFEST_SCHEMA = "fin_ia_dell_03B_R14_transaction_manifest_v1_0"
COMMITTED_MARKER_SCHEMA = "fin_ia_dell_03B_R14_committed_marker_v1_0"
RESERVATION_SCHEMA = "fin_ia_dell_03B_R14_attempt_reservation_v1_0"
_SAFE_COMPONENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
_HEX40 = re.compile(r"[0-9a-f]{40}")
_REPARSE_ATTRIBUTE = 0x400
_MOVEFILE_WRITE_THROUGH = 0x00000008
_AUTHORITY_SEAL = object()
_DURABILITY_SEAL = object()
R14_GOVERNANCE_COMMIT = "50fc4a706f00f40d831ec9624d33889180e1baa0"
R14_REQUIREMENT_PATH = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_dell_03b_r14_requirement_manifest_v1_0.json"
)
R14_PREFORMAL_COMMITMENT_PATH = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_dell_03b_r14_preformal_decision_commitment_v1_0.json"
)
R14_PREFORMAL_AUDIT_PATH = (
    "configs/audits/"
    "fin_ia_0_1_3_dell_03b_r14_preformal_audit_pass_v1_0.json"
)
R14_FORMAL_POLICY_PATH = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_dell_03b_r14_formal_policy_v1_0.json"
)
R14_IMPLEMENTATION_EXACT_PATHS = tuple(
    sorted(
        {
            "configs/retrieval/fin_ia_0_1_3_s1_dell_03b_r14_lifecycle_transition_table_v1_0.json",
            "configs/retrieval/fin_ia_0_1_3_s1_dell_03b_r14_requirement_manifest_v1_0.json",
            "configs/retrieval/fin_ia_0_1_3_s1_dell_03b_r14_structural_proof_grammar_v1_0.json",
            "configs/retrieval/fin_ia_0_1_3_s1_dell_03b_r14_target_topology_contract_v1_0.json",
            "scripts/data_retrieval/run_dell_report_r14_preview.py",
            "scripts/data_retrieval/scan_dell_report_r14_corpus_contracts.py",
            "src/retrieval/dell_report_decision_vector_r14.py",
            "src/retrieval/dell_report_decision_vector_rebuilder_r14.py",
            "src/retrieval/dell_report_delta_r14.py",
            "src/retrieval/dell_report_graph_schema_r14.py",
            "src/retrieval/dell_report_mutation_oracle_r14.py",
            "src/retrieval/dell_report_population_manifest_r14.py",
            "src/retrieval/dell_report_population_rebuilder_r14.py",
            "src/retrieval/dell_report_price_graph_r14.py",
            "src/retrieval/dell_report_program_contract_r14.py",
            "src/retrieval/dell_report_property_oracle_r14.py",
            "src/retrieval/dell_report_r14_common.py",
            "src/retrieval/dell_report_r14_contracts.py",
            "src/retrieval/dell_report_reconciliation_r14.py",
            "src/retrieval/dell_report_resource_gate_r14.py",
            "src/retrieval/dell_report_runner_r14.py",
            "src/retrieval/dell_report_structural_graph_r14.py",
            "src/retrieval/dell_report_target_compiler_r14.py",
            "src/retrieval/dell_report_transaction_r14.py",
            "src/retrieval/dell_report_transformation_r14.py",
            "tests/test_dell_report_decision_vector_r14.py",
            "tests/test_dell_report_mutation_oracle_r14.py",
            "tests/test_dell_report_population_manifest_r14.py",
            "tests/test_dell_report_property_oracle_r14.py",
            "tests/test_dell_report_r14_contracts.py",
            "tests/test_dell_report_reconciliation_r14.py",
            "tests/test_dell_report_resource_gate_r14.py",
            "tests/test_dell_report_runner_r14.py",
            "tests/test_dell_report_structural_graph_r14.py",
            "tests/test_dell_report_target_compiler_r14.py",
            "tests/test_dell_report_transaction_r14.py",
            "tests/test_dell_report_transformation_r14.py",
        }
    )
)
R14_BUNDLE_EXACT_PATHS = tuple(
    sorted(
        {
            "configs/retrieval/fin_ia_0_1_3_s1_dell_03b_r14_population_commitment_v1_0.json",
            "configs/retrieval/fin_ia_0_1_3_s1_dell_03b_r14_preformal_decision_commitment_v1_0.json",
            "configs/retrieval/fin_ia_0_1_3_s1_dell_03b_r14_critical_mutation_manifest_v1_0.json",
            "configs/retrieval/fin_ia_0_1_3_s1_dell_03b_r14_critical_mutation_kill_receipt_v1_0.json",
            "configs/retrieval/fin_ia_0_1_3_s1_dell_03b_r14_property_manifest_v1_0.json",
            "configs/retrieval/fin_ia_0_1_3_s1_dell_03b_r14_property_receipt_v1_0.json",
            "docs/worklog/fin_0_1_3_s1/125_dell_03b_R14_preformal_preview.md",
        }
    )
)


@dataclass(frozen=True, init=False)
class FormalTransactionAuthorityR14:
    lifecycle_state: str
    governance_commit: str
    implementation_commit: str
    bundle_commit: str
    audit_commit: str
    policy_commit: str
    commitment_digest: str
    durability_probe_receipt_digest: str
    minimum_free_bytes: int
    expected_artifact_paths: tuple[str, ...]
    expected_artifact_contracts: Mapping[str, Mapping[str, Any]]
    authority_evidence_digest: str
    _seal: object = field(repr=False, compare=False)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        del args, kwargs
        raise TypeError(
            "FormalTransactionAuthorityR14 is minted only by "
            "mint_formal_transaction_authority_r14"
        )

    @classmethod
    def _mint(
        cls,
        *,
        lifecycle_state: str,
        governance_commit: str,
        implementation_commit: str,
        bundle_commit: str,
        audit_commit: str,
        policy_commit: str,
        commitment_digest: str,
        durability_probe_receipt_digest: str,
        minimum_free_bytes: int,
        expected_artifact_paths: tuple[str, ...],
        expected_artifact_contracts: Mapping[str, Mapping[str, Any]],
        authority_evidence_digest: str,
        seal: object,
    ) -> "FormalTransactionAuthorityR14":
        require(seal is _AUTHORITY_SEAL, "R14_transaction_authority_mint_forbidden")
        instance = object.__new__(cls)
        values = {
            "lifecycle_state": lifecycle_state,
            "governance_commit": governance_commit,
            "implementation_commit": implementation_commit,
            "bundle_commit": bundle_commit,
            "audit_commit": audit_commit,
            "policy_commit": policy_commit,
            "commitment_digest": commitment_digest,
            "durability_probe_receipt_digest": durability_probe_receipt_digest,
            "minimum_free_bytes": minimum_free_bytes,
            "expected_artifact_paths": expected_artifact_paths,
            "expected_artifact_contracts": expected_artifact_contracts,
            "authority_evidence_digest": authority_evidence_digest,
            "_seal": seal,
        }
        for name, value in values.items():
            object.__setattr__(instance, name, value)
        return instance


@dataclass(frozen=True, init=False)
class TransactionDurabilityCapabilityR14:
    attempt_root: Path
    volume_identity: int
    backend: str
    probe_receipt_digest: str
    _seal: object = field(repr=False, compare=False)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        del args, kwargs
        raise TypeError(
            "TransactionDurabilityCapabilityR14 is minted only by "
            "probe_transaction_durability_r14"
        )

    @classmethod
    def _mint(
        cls,
        *,
        attempt_root: Path,
        volume_identity: int,
        backend: str,
        probe_receipt_digest: str,
        seal: object,
    ) -> "TransactionDurabilityCapabilityR14":
        require(seal is _DURABILITY_SEAL, "R14_transaction_durability_mint_forbidden")
        instance = object.__new__(cls)
        object.__setattr__(instance, "attempt_root", attempt_root)
        object.__setattr__(instance, "volume_identity", volume_identity)
        object.__setattr__(instance, "backend", backend)
        object.__setattr__(instance, "probe_receipt_digest", probe_receipt_digest)
        object.__setattr__(instance, "_seal", seal)
        return instance


@dataclass(frozen=True)
class TransactionArtifactR14:
    payload: bytes
    semantic_root: str


@dataclass(frozen=True)
class AttemptTransactionPathsR14:
    attempt_root: Path
    reservation_path: Path
    staging_path: Path
    final_path: Path


@dataclass(frozen=True)
class CommittedAttemptR14:
    final_path: Path
    reservation: Mapping[str, Any]
    transaction_manifest: Mapping[str, Any]
    committed_marker: Mapping[str, Any]


BoundaryHookR14 = Callable[[str, AttemptTransactionPathsR14], None]


def _safe_component(value: str, *, field: str) -> str:
    require(bool(_SAFE_COMPONENT.fullmatch(value)), f"R14_transaction_{field}_invalid")
    require(value not in {".", ".."}, f"R14_transaction_{field}_invalid")
    return value


def _safe_relative_path(value: str) -> str:
    candidate = PurePosixPath(value)
    require(
        bool(value)
        and not candidate.is_absolute()
        and "\\" not in value
        and all(part not in {"", ".", ".."} for part in candidate.parts)
        and all(bool(_SAFE_COMPONENT.fullmatch(part)) for part in candidate.parts),
        f"R14_transaction_relative_path_invalid:{value}",
    )
    require(
        value not in {"TRANSACTION_MANIFEST.json", "COMMITTED.json"},
        f"R14_transaction_reserved_path:{value}",
    )
    return candidate.as_posix()


def _is_reparse_point(path: Path) -> bool:
    stat = os.lstat(path)
    return bool(getattr(stat, "st_file_attributes", 0) & _REPARSE_ATTRIBUTE)


def _assert_existing_path_chain_safe(root: Path, path: Path) -> None:
    require(path == root or root in path.parents, "R14_transaction_path_escape")
    current = root
    require(not _is_reparse_point(current), "R14_transaction_root_reparse_point")
    for part in path.relative_to(root).parts:
        current = current / part
        if current.exists():
            require(
                not current.is_symlink() and not _is_reparse_point(current),
                "R14_transaction_descendant_reparse_point",
            )


def resolve_attempt_transaction_paths_r14(
    *, attempt_root: Path, attempt_id: str, nonce: str
) -> AttemptTransactionPathsR14:
    attempt_id = _safe_component(attempt_id, field="attempt_id")
    nonce = _safe_component(nonce, field="nonce")
    require(attempt_root.is_dir(), "R14_transaction_attempt_root_missing")
    root = attempt_root.resolve(strict=True)
    reservation_root = root / "attempt_reservations"
    require(
        reservation_root.is_dir(),
        "R14_transaction_reservation_root_not_preflighted",
    )
    _assert_existing_path_chain_safe(root, reservation_root)
    paths = AttemptTransactionPathsR14(
        attempt_root=root,
        reservation_path=reservation_root / f"{attempt_id}.json",
        staging_path=root / f".{attempt_id}.incomplete.{nonce}",
        final_path=root / attempt_id,
    )
    for path in (paths.reservation_path, paths.staging_path, paths.final_path):
        _assert_existing_path_chain_safe(root, path)
    require(
        not paths.reservation_path.exists()
        and not paths.staging_path.exists()
        and not paths.final_path.exists(),
        "R14_transaction_target_already_exists",
    )
    require(
        os.stat(root).st_dev == os.stat(reservation_root).st_dev,
        "R14_transaction_not_same_volume",
    )
    return paths


def _flush_file(handle: Any) -> None:
    handle.flush()
    os.fsync(handle.fileno())


def _windows_move_no_replace_write_through(source: Path, destination: Path) -> None:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    move_file = kernel32.MoveFileExW
    move_file.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
    move_file.restype = ctypes.c_int
    moved = move_file(str(source), str(destination), _MOVEFILE_WRITE_THROUGH)
    if not moved:
        error = ctypes.get_last_error()
        require(False, f"R14_transaction_no_replace_write_through_rename_failed:{error}")


def _platform_move_no_replace_write_through(
    source: Path, destination: Path
) -> None:
    require(source.exists(), "R14_transaction_rename_source_missing")
    require(not destination.exists(), "R14_transaction_rename_destination_exists")
    if os.name == "nt":
        _windows_move_no_replace_write_through(source, destination)
        return
    os.rename(source, destination)
    descriptor = os.open(destination.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def probe_transaction_durability_r14(
    *, attempt_root: Path
) -> TransactionDurabilityCapabilityR14:
    """Prove the exact no-replace/write-through primitives before consumption.

    Windows does not support POSIX-style directory ``fsync`` through
    ``FlushFileBuffers`` on a directory handle on every filesystem.  R14
    therefore probes the primitive it actually uses: flushed create-new files
    plus same-volume ``MoveFileExW(MOVEFILE_WRITE_THROUGH)`` for both files and
    the terminal directory publication.  Any unsupported operation fails here,
    before an attempt reservation can exist.
    """
    require(attempt_root.is_dir(), "R14_transaction_attempt_root_missing")
    root = attempt_root.resolve(strict=True)
    _assert_existing_path_chain_safe(root, root)
    require(os.name == "nt", "R14_transaction_formal_host_not_windows")
    reservation_root = root / "attempt_reservations"
    reservation_root.mkdir(exist_ok=True)
    _assert_existing_path_chain_safe(root, reservation_root)
    require(
        os.stat(root).st_dev == os.stat(reservation_root).st_dev,
        "R14_transaction_reservation_not_same_volume",
    )
    nonce = f"{os.getpid()}-{secrets.token_hex(8)}"
    probe_root = root / f".r14-transaction-capability-{nonce}"
    renamed_root = root / f".r14-transaction-capability-renamed-{nonce}"
    collision = root / f".r14-transaction-capability-collision-{nonce}"
    reparse_link = root / f".r14-transaction-capability-reparse-{nonce}"
    completed_steps: list[str] = []
    try:
        probe_root.mkdir(exist_ok=False)
        completed_steps.append("exclusive_directory_create")
        source_file = probe_root / "probe.tmp"
        final_file = probe_root / "probe.bin"
        with source_file.open("xb") as handle:
            handle.write(b"FIN_IA_R14_TRANSACTION_CAPABILITY\n")
            _flush_file(handle)
        completed_steps.append("create_new_file_flush")
        _platform_move_no_replace_write_through(source_file, final_file)
        require(
            final_file.read_bytes() == b"FIN_IA_R14_TRANSACTION_CAPABILITY\n",
            "R14_transaction_capability_file_reopen_failed",
        )
        completed_steps.append("file_no_replace_write_through_reopen")
        collision.mkdir(exist_ok=False)
        collision_rejected = False
        try:
            _platform_move_no_replace_write_through(probe_root, collision)
        except Exception:
            collision_rejected = True
        require(collision_rejected, "R14_transaction_capability_collision_not_rejected")
        completed_steps.append("destination_collision_rejected")
        _platform_move_no_replace_write_through(probe_root, renamed_root)
        require(
            (renamed_root / "probe.bin").read_bytes()
            == b"FIN_IA_R14_TRANSACTION_CAPABILITY\n",
            "R14_transaction_capability_directory_reopen_failed",
        )
        completed_steps.append("directory_no_replace_write_through_reopen")
        reparse_target = renamed_root / "reparse-target"
        reparse_target.mkdir(exist_ok=False)
        try:
            os.symlink(reparse_target, reparse_link, target_is_directory=True)
        except OSError as exc:
            require(
                getattr(exc, "winerror", None) == 1314,
                f"R14_transaction_capability_reparse_probe_unavailable:{getattr(exc, 'winerror', None) or exc.errno}",
            )
            junction = subprocess.run(
                [
                    "cmd.exe",
                    "/d",
                    "/c",
                    "mklink",
                    "/J",
                    str(reparse_link),
                    str(reparse_target),
                ],
                check=False,
                capture_output=True,
                text=False,
            )
            require(
                junction.returncode == 0 and reparse_link.exists(),
                "R14_transaction_capability_junction_probe_unavailable",
            )
        reparse_rejected = False
        try:
            _assert_existing_path_chain_safe(root, reparse_link)
        except Exception:
            reparse_rejected = True
        require(
            reparse_rejected,
            "R14_transaction_capability_reparse_chain_not_rejected",
        )
        completed_steps.append("actual_reparse_chain_rejected")
        receipt = with_result_digest(
            {
                "schema_version": "fin_ia_dell_03B_R14_transaction_capability_v1_0",
                "backend": "Windows_MoveFileExW_WRITE_THROUGH_no_replace",
                "volume_identity": int(os.stat(root).st_dev),
                "completed_steps": completed_steps,
                "reservation_root_prepared": True,
            }
        )
        return TransactionDurabilityCapabilityR14._mint(
            attempt_root=root,
            volume_identity=int(os.stat(root).st_dev),
            backend=str(receipt["backend"]),
            probe_receipt_digest=str(receipt["result_digest"]),
            seal=_DURABILITY_SEAL,
        )
    finally:
        if reparse_link.is_symlink():
            reparse_link.unlink()
        elif reparse_link.exists() and _is_reparse_point(reparse_link):
            os.rmdir(reparse_link)
        for candidate in (probe_root, renamed_root, collision):
            if candidate.is_dir():
                shutil.rmtree(candidate)
            elif candidate.exists():
                candidate.unlink()


def _write_new_and_verify(
    path: Path,
    payload: bytes,
    *,
    boundary_prefix: str,
    hook: BoundaryHookR14 | None,
    paths: AttemptTransactionPathsR14,
) -> tuple[int, str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    _assert_existing_path_chain_safe(paths.attempt_root, path)
    with path.open("xb") as handle:
        handle.write(payload)
        _emit_boundary(hook, f"after_{boundary_prefix}_write_before_flush", paths)
        _flush_file(handle)
        _emit_boundary(hook, f"after_{boundary_prefix}_flush_before_close", paths)
    require(path.stat().st_size == len(payload), "R14_transaction_reopen_size_mismatch")
    actual = file_sha256(path)
    require(actual == sha256_bytes(payload), "R14_transaction_reopen_sha256_mismatch")
    return len(payload), actual


def _rename_no_replace(source: Path, destination: Path) -> None:
    _platform_move_no_replace_write_through(source, destination)


def _emit_boundary(
    hook: BoundaryHookR14 | None,
    name: str,
    paths: AttemptTransactionPathsR14,
) -> None:
    if hook is not None:
        hook(name, paths)


def _git_output(repository_root: Path, *args: str, binary: bool = False) -> Any:
    completed = subprocess.run(
        ["git", *args],
        cwd=repository_root,
        check=False,
        capture_output=True,
        text=not binary,
    )
    require(completed.returncode == 0, f"R14_transaction_git_command_failed:{args[0]}")
    return completed.stdout if binary else completed.stdout.strip()


def _git_parent(repository_root: Path, commit: str) -> str:
    parents = str(_git_output(repository_root, "show", "-s", "--format=%P", commit)).split()
    require(len(parents) == 1, "R14_transaction_git_parent_not_unique")
    return parents[0]


def _git_tree(repository_root: Path, commit: str) -> str:
    return str(_git_output(repository_root, "show", "-s", "--format=%T", commit))


def _git_changed_paths(repository_root: Path, commit: str) -> tuple[str, ...]:
    parent = _git_parent(repository_root, commit)
    output = str(
        _git_output(
            repository_root,
            "diff-tree",
            "--no-commit-id",
            "--name-only",
            "-r",
            parent,
            commit,
        )
    )
    return tuple(sorted(row for row in output.splitlines() if row))


def _git_json_blob(repository_root: Path, commit: str, path: str) -> tuple[dict[str, Any], bytes]:
    safe_path = _safe_relative_path(path)
    raw = bytes(_git_output(repository_root, "show", f"{commit}:{safe_path}", binary=True))
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        require(False, f"R14_transaction_git_json_blob_invalid:{safe_path}:{exc}")
    require(isinstance(parsed, dict), f"R14_transaction_git_json_blob_not_object:{safe_path}")
    return parsed, raw


def _git_blob_oid(repository_root: Path, commit: str, path: str) -> str:
    safe_path = _safe_relative_path(path)
    oid = str(_git_output(repository_root, "rev-parse", f"{commit}:{safe_path}"))
    require(
        bool(_HEX40.fullmatch(oid)),
        f"R14_transaction_git_blob_identity_invalid:{safe_path}",
    )
    return oid


def _validate_frozen_blobs_unchanged(
    *,
    repository_root: Path,
    frozen_commit: str,
    descendant_commits: tuple[str, ...],
    paths: tuple[str, ...],
    code: str,
) -> None:
    frozen = {
        path: _git_blob_oid(repository_root, frozen_commit, path) for path in paths
    }
    for commit in descendant_commits:
        require(
            all(
                _git_blob_oid(repository_root, commit, path) == blob
                for path, blob in frozen.items()
            ),
            code,
        )


def _validate_self_digest(value: Mapping[str, Any], *, code: str) -> None:
    expected = value.get("result_digest")
    require(
        with_result_digest(value).get("result_digest") == expected,
        f"{code}_result_digest_mismatch",
    )


def _validate_r14_governance_from_implementation(
    *, repository_root: Path, implementation_commit: str
) -> None:
    requirement, _ = _git_json_blob(
        repository_root, implementation_commit, R14_REQUIREMENT_PATH
    )
    from .dell_report_r14_contracts import (
        validate_plan_frozen_git,
        validate_requirement_manifest,
    )

    validate_requirement_manifest(requirement)
    frozen = validate_plan_frozen_git(requirement, root=repository_root)
    require(
        frozen.get("governance") == R14_GOVERNANCE_COMMIT
        and frozen.get("status") == "PLAN_FROZEN_PASS",
        "R14_transaction_PLAN_FROZEN_governance_invalid",
    )


def mint_formal_transaction_authority_r14(
    *,
    repository_root: Path,
    governance_commit: str,
    implementation_commit: str,
    bundle_commit: str,
    audit_commit: str,
    policy_commit: str,
    commitment_path: str,
    preformal_audit_path: str,
    policy_path: str,
) -> FormalTransactionAuthorityR14:
    """Mint formal authority only after rebuilding exact I/B/A/P evidence.

    No caller-supplied boolean can authorize publication.  The factory reads
    the commitment, independent audit and policy from their exact Git commits,
    verifies the linear topology and changed pathsets, and derives the artifact
    contract exclusively from the reviewed commitment.
    """
    repo = repository_root.resolve(strict=True)
    require((repo / ".git").exists(), "R14_transaction_repository_not_git")
    commits = (
        governance_commit,
        implementation_commit,
        bundle_commit,
        audit_commit,
        policy_commit,
    )
    require(
        all(bool(_HEX40.fullmatch(value)) for value in commits),
        "R14_transaction_authority_git_identity_invalid",
    )
    for commit in commits:
        require(
            str(_git_output(repo, "cat-file", "-t", commit)) == "commit",
            "R14_transaction_authority_commit_missing",
        )
    require(
        governance_commit == R14_GOVERNANCE_COMMIT
        and _git_parent(repo, implementation_commit) == governance_commit
        and _git_parent(repo, bundle_commit) == implementation_commit
        and _git_parent(repo, audit_commit) == bundle_commit
        and _git_parent(repo, policy_commit) == audit_commit,
        "R14_transaction_authority_topology_invalid",
    )
    _validate_r14_governance_from_implementation(
        repository_root=repo,
        implementation_commit=implementation_commit,
    )
    commitment_path = _safe_relative_path(commitment_path)
    preformal_audit_path = _safe_relative_path(preformal_audit_path)
    policy_path = _safe_relative_path(policy_path)
    require(
        commitment_path == R14_PREFORMAL_COMMITMENT_PATH,
        "R14_transaction_commitment_path_not_fixed",
    )
    require(
        preformal_audit_path == R14_PREFORMAL_AUDIT_PATH,
        "R14_transaction_audit_path_not_fixed",
    )
    require(
        policy_path == R14_FORMAL_POLICY_PATH,
        "R14_transaction_policy_path_not_fixed",
    )
    control_paths = {commitment_path, preformal_audit_path, policy_path}
    require(
        len(control_paths) == 3
        and control_paths.isdisjoint(R14_IMPLEMENTATION_EXACT_PATHS)
        and preformal_audit_path not in R14_BUNDLE_EXACT_PATHS
        and policy_path not in R14_BUNDLE_EXACT_PATHS,
        "R14_transaction_I_B_A_P_path_classes_overlap",
    )
    commitment, commitment_bytes = _git_json_blob(
        repo, bundle_commit, commitment_path
    )
    audit, audit_bytes = _git_json_blob(repo, audit_commit, preformal_audit_path)
    policy, policy_bytes = _git_json_blob(repo, policy_commit, policy_path)
    _validate_self_digest(commitment, code="R14_transaction_commitment")
    _validate_self_digest(audit, code="R14_transaction_preformal_audit")
    _validate_self_digest(policy, code="R14_transaction_policy")
    from .dell_report_reconciliation_r14 import (
        validate_preformal_decision_commitment_r14,
    )

    validate_preformal_decision_commitment_r14(commitment)
    require(
        commitment.get("implementation_commit") == implementation_commit
        and commitment.get("implementation_tree") == _git_tree(repo, implementation_commit)
        and commitment.get("implementation_parent")
        == _git_parent(repo, implementation_commit),
        "R14_transaction_commitment_implementation_identity_invalid",
    )
    implementation_paths = _git_changed_paths(repo, implementation_commit)
    bundle_paths = _git_changed_paths(repo, bundle_commit)
    audit_paths = _git_changed_paths(repo, audit_commit)
    policy_paths = _git_changed_paths(repo, policy_commit)
    _validate_frozen_blobs_unchanged(
        repository_root=repo,
        frozen_commit=implementation_commit,
        descendant_commits=(bundle_commit, audit_commit, policy_commit),
        paths=implementation_paths,
        code="R14_transaction_I_frozen_blob_changed_in_B_A_or_P",
    )
    _validate_frozen_blobs_unchanged(
        repository_root=repo,
        frozen_commit=bundle_commit,
        descendant_commits=(audit_commit, policy_commit),
        paths=bundle_paths,
        code="R14_transaction_B_frozen_blob_changed_in_A_or_P",
    )
    require(
        implementation_paths == R14_IMPLEMENTATION_EXACT_PATHS
        and bundle_paths == R14_BUNDLE_EXACT_PATHS
        and commitment_path in bundle_paths
        and audit_paths == (preformal_audit_path,)
        and policy_paths == (policy_path,),
        "R14_transaction_authority_I_B_A_or_P_pathset_invalid",
    )
    audit_expected_keys = {
        "schema_version",
        "review_task_id",
        "reviewer_identity",
        "author_identity",
        "author_separated",
        "reviewed_implementation_commit",
        "reviewed_implementation_tree",
        "reviewed_implementation_parent",
        "reviewed_implementation_changed_paths",
        "reviewed_bundle_commit",
        "reviewed_bundle_tree",
        "reviewed_bundle_parent",
        "reviewed_bundle_changed_paths",
        "commitment_path",
        "commitment_sha256",
        "commitment_result_digest",
        "mutation_execution_root",
        "property_result_root",
        "fresh_holdout_root",
        "findings",
        "verdict",
        "lifecycle_state",
        "reviewer_fresh_no_fork",
        "reviewer_read_only",
        "prohibited_action_counts",
        "result_digest",
    }
    require(set(audit) == audit_expected_keys, "R14_transaction_preformal_audit_schema_invalid")
    findings = audit.get("findings")
    require(
        audit.get("schema_version")
        == "fin_ia_dell_03B_R14_preformal_audit_receipt_v1_0"
        and bool(require_identifier(audit.get("review_task_id"), field="preformal_review_task"))
        and bool(require_identifier(audit.get("reviewer_identity"), field="preformal_reviewer"))
        and bool(require_identifier(audit.get("author_identity"), field="preformal_author"))
        and audit.get("author_separated") is True
        and audit.get("reviewed_implementation_commit") == implementation_commit
        and audit.get("reviewed_implementation_tree")
        == _git_tree(repo, implementation_commit)
        and audit.get("reviewed_implementation_parent")
        == _git_parent(repo, implementation_commit)
        and tuple(audit.get("reviewed_implementation_changed_paths") or ())
        == implementation_paths
        and audit.get("reviewed_bundle_commit") == bundle_commit
        and audit.get("reviewed_bundle_tree") == _git_tree(repo, bundle_commit)
        and audit.get("reviewed_bundle_parent") == implementation_commit
        and tuple(audit.get("reviewed_bundle_changed_paths") or ()) == bundle_paths
        and audit.get("commitment_path") == commitment_path
        and audit.get("commitment_sha256") == sha256_bytes(commitment_bytes)
        and audit.get("commitment_result_digest") == commitment.get("result_digest")
        and audit.get("mutation_execution_root")
        == commitment.get("critical_mutation_execution_root")
        and audit.get("property_result_root")
        == commitment.get("property_result_root")
        and bool(require_sha256(audit.get("fresh_holdout_root"), field="preformal_holdout"))
        and findings == {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
        and audit.get("verdict") == "PREFORMAL_PASS"
        and audit.get("lifecycle_state") == "PREFORMAL_PASS"
        and audit.get("reviewer_fresh_no_fork") is True
        and audit.get("reviewer_read_only") is True
        and isinstance(audit.get("prohibited_action_counts"), dict)
        and bool(audit["prohibited_action_counts"])
        and all(value == 0 for value in audit["prohibited_action_counts"].values()),
        "R14_transaction_preformal_audit_not_exact_PASS",
    )
    policy_expected_keys = {
        "schema_version",
        "implementation_commit",
        "bundle_commit",
        "audit_commit",
        "commitment_result_digest",
        "preformal_audit_result_digest",
        "expected_artifact_paths",
        "minimum_free_bytes",
        "lifecycle_state",
        "model_provider_calls",
        "result_digest",
    }
    require(set(policy) == policy_expected_keys, "R14_transaction_policy_schema_invalid")
    planned_rows = list(commitment.get("planned_artifacts") or ())
    expected_contracts: dict[str, dict[str, Any]] = {}
    for row in planned_rows:
        require(
            isinstance(row, dict)
            and set(row)
            == {"relative_path", "exact_bytes", "sha256", "semantic_root"}
            and type(row.get("exact_bytes")) is int
            and row["exact_bytes"] >= 0,
            "R14_transaction_commitment_artifact_row_invalid",
        )
        path = _safe_relative_path(str(row["relative_path"]))
        require(path not in expected_contracts, "R14_transaction_commitment_duplicate_path")
        require_sha256(row.get("sha256"), field="transaction_planned_artifact_sha256")
        require_sha256(row.get("semantic_root"), field="transaction_planned_artifact_root")
        expected_contracts[path] = dict(row)
    expected_paths = tuple(sorted(expected_contracts))
    require(bool(expected_paths), "R14_transaction_commitment_artifact_pathset_empty")
    require(
        policy.get("schema_version") == "fin_ia_dell_03B_R14_formal_policy_v1_0"
        and policy.get("implementation_commit") == implementation_commit
        and policy.get("bundle_commit") == bundle_commit
        and policy.get("audit_commit") == audit_commit
        and policy.get("commitment_result_digest") == commitment.get("result_digest")
        and policy.get("preformal_audit_result_digest") == audit.get("result_digest")
        and tuple(policy.get("expected_artifact_paths") or ()) == expected_paths
        and type(policy.get("minimum_free_bytes")) is int
        and policy["minimum_free_bytes"] == commitment.get("required_free_bytes")
        and policy["minimum_free_bytes"] >= 512 * 1024 * 1024
        and policy.get("lifecycle_state") == "POLICY_BOUND"
        and policy.get("model_provider_calls") == 0,
        "R14_transaction_policy_binding_invalid",
    )
    evidence = {
        "governance_commit": governance_commit,
        "governance_tree": _git_tree(repo, governance_commit),
        "implementation_commit": implementation_commit,
        "implementation_tree": _git_tree(repo, implementation_commit),
        "implementation_parent": _git_parent(repo, implementation_commit),
        "implementation_changed_paths": list(implementation_paths),
        "bundle_commit": bundle_commit,
        "bundle_tree": _git_tree(repo, bundle_commit),
        "bundle_changed_paths": list(bundle_paths),
        "audit_commit": audit_commit,
        "audit_tree": _git_tree(repo, audit_commit),
        "audit_sha256": sha256_bytes(audit_bytes),
        "policy_commit": policy_commit,
        "policy_tree": _git_tree(repo, policy_commit),
        "policy_sha256": sha256_bytes(policy_bytes),
        "commitment_result_digest": commitment["result_digest"],
    }
    return FormalTransactionAuthorityR14._mint(
        lifecycle_state="POLICY_BOUND",
        governance_commit=governance_commit,
        implementation_commit=implementation_commit,
        bundle_commit=bundle_commit,
        audit_commit=audit_commit,
        policy_commit=policy_commit,
        commitment_digest=str(commitment["result_digest"]),
        durability_probe_receipt_digest=str(
            commitment["durability_probe_receipt_digest"]
        ),
        minimum_free_bytes=int(policy["minimum_free_bytes"]),
        expected_artifact_paths=expected_paths,
        expected_artifact_contracts=expected_contracts,
        authority_evidence_digest=canonical_digest(evidence),
        seal=_AUTHORITY_SEAL,
    )


def _validate_authority(authority: FormalTransactionAuthorityR14) -> None:
    require(
        isinstance(authority, FormalTransactionAuthorityR14)
        and authority._seal is _AUTHORITY_SEAL,
        "R14_transaction_formal_not_authorized",
    )
    require(
        authority.lifecycle_state == "POLICY_BOUND",
        "R14_transaction_lifecycle_not_POLICY_BOUND",
    )
    require_sha256(
        authority.durability_probe_receipt_digest,
        field="transaction_authority_durability_probe",
    )
    require(
        all(
            bool(_HEX40.fullmatch(value))
            for value in (
                authority.governance_commit,
                authority.implementation_commit,
                authority.bundle_commit,
                authority.audit_commit,
                authority.policy_commit,
            )
        ),
        "R14_transaction_git_commit_invalid",
    )
    require_sha256(authority.commitment_digest, field="transaction_commitment_digest")
    require(
        authority.minimum_free_bytes >= 512 * 1024 * 1024,
        "R14_transaction_minimum_free_below_floor",
    )
    expected = tuple(_safe_relative_path(row) for row in authority.expected_artifact_paths)
    require(
        tuple(sorted(set(expected))) == expected,
        "R14_transaction_expected_pathset_invalid",
    )
    require(
        tuple(sorted(authority.expected_artifact_contracts)) == expected,
        "R14_transaction_expected_contract_pathset_invalid",
    )
    require_sha256(
        authority.authority_evidence_digest,
        field="transaction_authority_evidence",
    )


def _validate_durability_capability(
    capability: TransactionDurabilityCapabilityR14, *, attempt_root: Path
) -> Path:
    require(
        isinstance(capability, TransactionDurabilityCapabilityR14)
        and capability._seal is _DURABILITY_SEAL,
        "R14_transaction_durability_capability_invalid",
    )
    root = attempt_root.resolve(strict=True)
    require(
        capability.attempt_root == root
        and capability.volume_identity == int(os.stat(root).st_dev)
        and capability.backend == "Windows_MoveFileExW_WRITE_THROUGH_no_replace",
        "R14_transaction_durability_capability_binding_invalid",
    )
    require_sha256(
        capability.probe_receipt_digest,
        field="transaction_capability_receipt",
    )
    return root


def validate_transaction_durability_capability_r14(
    capability: TransactionDurabilityCapabilityR14, *, attempt_root: Path
) -> Mapping[str, Any]:
    root = _validate_durability_capability(capability, attempt_root=attempt_root)
    return {
        "attempt_root": str(root),
        "volume_identity": capability.volume_identity,
        "backend": capability.backend,
        "probe_receipt_digest": capability.probe_receipt_digest,
    }


def publish_atomic_attempt_r14(
    *,
    attempt_root: Path,
    attempt_id: str,
    nonce: str,
    authority: FormalTransactionAuthorityR14,
    durability_capability: TransactionDurabilityCapabilityR14,
    artifacts: Mapping[str, TransactionArtifactR14],
    boundary_hook: BoundaryHookR14 | None = None,
) -> CommittedAttemptR14:
    """Publish one immutable attempt directory or leave failed evidence.

    No cleanup is attempted after reservation.  A caller crash or exception
    therefore cannot make the consumed attempt ID reusable.
    """
    _validate_authority(authority)
    root = _validate_durability_capability(
        durability_capability, attempt_root=attempt_root
    )
    require(
        durability_capability.probe_receipt_digest
        == authority.durability_probe_receipt_digest,
        "R14_transaction_durability_capability_not_commitment_bound",
    )
    normalized_artifacts = {
        _safe_relative_path(path): artifact for path, artifact in artifacts.items()
    }
    require(
        tuple(sorted(normalized_artifacts)) == authority.expected_artifact_paths,
        "R14_transaction_artifact_pathset_mismatch",
    )
    for relative_path, artifact in normalized_artifacts.items():
        require(isinstance(artifact.payload, bytes), "R14_transaction_payload_not_bytes")
        require_sha256(artifact.semantic_root, field="transaction_semantic_root")
        from .dell_report_reconciliation_r14 import (
            recompute_program_artifact_semantic_root_r14,
        )

        recomputed_semantic_root = recompute_program_artifact_semantic_root_r14(
            relative_path=relative_path, payload=artifact.payload
        )
        contract = authority.expected_artifact_contracts[relative_path]
        require(
            len(artifact.payload) == contract["exact_bytes"]
            and sha256_bytes(artifact.payload) == contract["sha256"]
            and recomputed_semantic_root
            == artifact.semantic_root
            == contract["semantic_root"],
            f"R14_transaction_artifact_not_precommitted:{relative_path}",
        )

    required_now = authority.minimum_free_bytes
    require(
        shutil.disk_usage(root).free >= required_now,
        "R14_transaction_disk_gate_failed_before_reservation",
    )
    paths = resolve_attempt_transaction_paths_r14(
        attempt_root=root, attempt_id=attempt_id, nonce=nonce
    )
    _emit_boundary(boundary_hook, "before_reservation", paths)

    reservation = with_result_digest(
        {
            "schema_version": RESERVATION_SCHEMA,
            "attempt_id": attempt_id,
            "policy_commit": authority.policy_commit,
            "commitment_digest": authority.commitment_digest,
            "expected_artifact_paths": list(authority.expected_artifact_paths),
            "lifecycle_state": "ATTEMPT_CONSUMED",
        }
    )
    reservation_bytes = canonical_json_bytes(reservation)
    _, reservation_sha = _write_new_and_verify(
        paths.reservation_path,
        reservation_bytes,
        boundary_prefix="reservation",
        hook=boundary_hook,
        paths=paths,
    )
    _emit_boundary(boundary_hook, "after_reservation_flush", paths)

    paths.staging_path.mkdir(exist_ok=False)
    _emit_boundary(boundary_hook, "after_staging_create", paths)
    artifact_rows: list[dict[str, Any]] = []
    staged_payload_bytes = 0
    for index, relative_path in enumerate(sorted(normalized_artifacts)):
        artifact = normalized_artifacts[relative_path]
        require(
            shutil.disk_usage(root).free
            >= max(512 * 1024 * 1024, authority.minimum_free_bytes - staged_payload_bytes),
            f"R14_transaction_disk_gate_failed_before_artifact:{index}",
        )
        final_artifact = paths.staging_path.joinpath(*PurePosixPath(relative_path).parts)
        final_artifact.parent.mkdir(parents=True, exist_ok=True)
        _assert_existing_path_chain_safe(paths.attempt_root, final_artifact.parent)
        temp_artifact = final_artifact.with_name(f".{final_artifact.name}.tmp.{nonce}")
        size, sha = _write_new_and_verify(
            temp_artifact,
            artifact.payload,
            boundary_prefix=f"artifact_{index}",
            hook=boundary_hook,
            paths=paths,
        )
        _emit_boundary(boundary_hook, f"after_artifact_flush:{index}", paths)
        _rename_no_replace(temp_artifact, final_artifact)
        _emit_boundary(boundary_hook, f"after_artifact_rename:{index}", paths)
        artifact_rows.append(
            {
                "relative_path": relative_path,
                "size": size,
                "sha256": sha,
                "semantic_root": artifact.semantic_root,
            }
        )
        staged_payload_bytes += len(artifact.payload)

    bundle_root = domain_rows_digest(
        b"FIN_IA_R14_TRANSACTION_BUNDLE_V1\0",
        (canonical_json_bytes(row) for row in artifact_rows),
    )
    transaction_manifest = with_result_digest(
        {
            "schema_version": TRANSACTION_MANIFEST_SCHEMA,
            "attempt_id": attempt_id,
            "commitment_digest": authority.commitment_digest,
            "artifacts": artifact_rows,
            "artifact_count": len(artifact_rows),
            "bundle_root": bundle_root,
        }
    )
    manifest_path = paths.staging_path / "TRANSACTION_MANIFEST.json"
    manifest_temp = paths.staging_path / f".TRANSACTION_MANIFEST.json.tmp.{nonce}"
    manifest_bytes = canonical_json_bytes(transaction_manifest)
    _, manifest_sha = _write_new_and_verify(
        manifest_temp,
        manifest_bytes,
        boundary_prefix="manifest",
        hook=boundary_hook,
        paths=paths,
    )
    _emit_boundary(boundary_hook, "after_manifest_flush", paths)
    _rename_no_replace(manifest_temp, manifest_path)
    _emit_boundary(boundary_hook, "after_manifest_rename", paths)

    marker = with_result_digest(
        {
            "schema_version": COMMITTED_MARKER_SCHEMA,
            "attempt_id": attempt_id,
            "reservation_sha256": reservation_sha,
            "transaction_manifest_sha256": manifest_sha,
            "bundle_root": bundle_root,
            "lifecycle_state": "ATTEMPT_CONSUMED",
        }
    )
    marker_path = paths.staging_path / "COMMITTED.json"
    marker_temp = paths.staging_path / f".COMMITTED.json.tmp.{nonce}"
    marker_bytes = canonical_json_bytes(marker)
    _write_new_and_verify(
        marker_temp,
        marker_bytes,
        boundary_prefix="marker",
        hook=boundary_hook,
        paths=paths,
    )
    _emit_boundary(boundary_hook, "after_marker_flush", paths)
    _rename_no_replace(marker_temp, marker_path)
    _emit_boundary(boundary_hook, "after_marker_rename", paths)

    require(
        shutil.disk_usage(paths.attempt_root).free >= authority.minimum_free_bytes,
        "R14_transaction_disk_gate_failed_before_publish",
    )
    _emit_boundary(boundary_hook, "before_publish_rename", paths)
    _rename_no_replace(paths.staging_path, paths.final_path)
    _emit_boundary(boundary_hook, "after_publish_rename", paths)
    return read_committed_attempt_r14(
        attempt_root=paths.attempt_root, attempt_id=attempt_id
    )


def _validate_result_digest(value: Mapping[str, Any], *, code: str) -> None:
    expected = value.get("result_digest")
    rebuilt = with_result_digest(value)
    require(rebuilt.get("result_digest") == expected, f"{code}_result_digest_mismatch")


def read_committed_attempt_r14(
    *, attempt_root: Path, attempt_id: str
) -> CommittedAttemptR14:
    attempt_id = _safe_component(attempt_id, field="attempt_id")
    root = attempt_root.resolve(strict=True)
    reservation_path = root / "attempt_reservations" / f"{attempt_id}.json"
    final_path = root / attempt_id
    require(final_path.is_dir(), "R14_transaction_final_attempt_not_visible")
    _assert_existing_path_chain_safe(root, reservation_path)
    _assert_existing_path_chain_safe(root, final_path)
    reservation = read_json(reservation_path)
    manifest_path = final_path / "TRANSACTION_MANIFEST.json"
    marker_path = final_path / "COMMITTED.json"
    manifest = read_json(manifest_path)
    marker = read_json(marker_path)
    _validate_result_digest(reservation, code="R14_transaction_reservation")
    _validate_result_digest(manifest, code="R14_transaction_manifest")
    _validate_result_digest(marker, code="R14_transaction_marker")
    require(
        set(reservation)
        == {
            "schema_version",
            "attempt_id",
            "policy_commit",
            "commitment_digest",
            "expected_artifact_paths",
            "lifecycle_state",
            "result_digest",
        }
        and set(manifest)
        == {
            "schema_version",
            "attempt_id",
            "commitment_digest",
            "artifacts",
            "artifact_count",
            "bundle_root",
            "result_digest",
        }
        and set(marker)
        == {
            "schema_version",
            "attempt_id",
            "reservation_sha256",
            "transaction_manifest_sha256",
            "bundle_root",
            "lifecycle_state",
            "result_digest",
        },
        "R14_transaction_sidecar_keyset_invalid",
    )
    require(
        reservation.get("schema_version") == RESERVATION_SCHEMA
        and manifest.get("schema_version") == TRANSACTION_MANIFEST_SCHEMA
        and marker.get("schema_version") == COMMITTED_MARKER_SCHEMA,
        "R14_transaction_schema_invalid",
    )
    require(
        reservation.get("attempt_id")
        == manifest.get("attempt_id")
        == marker.get("attempt_id")
        == attempt_id,
        "R14_transaction_attempt_binding_mismatch",
    )
    require(
        bool(_HEX40.fullmatch(str(reservation.get("policy_commit") or "")))
        and reservation.get("lifecycle_state") == "ATTEMPT_CONSUMED"
        and marker.get("lifecycle_state") == "ATTEMPT_CONSUMED"
        and reservation.get("commitment_digest") == manifest.get("commitment_digest"),
        "R14_transaction_authority_binding_mismatch",
    )
    require_sha256(
        reservation.get("commitment_digest"), field="transaction_commitment_digest"
    )
    require_sha256(marker.get("reservation_sha256"), field="transaction_reservation")
    require_sha256(
        marker.get("transaction_manifest_sha256"), field="transaction_manifest"
    )
    require(
        file_sha256(reservation_path) == marker.get("reservation_sha256")
        and file_sha256(manifest_path)
        == marker.get("transaction_manifest_sha256"),
        "R14_transaction_marker_file_binding_mismatch",
    )
    rows = list(manifest.get("artifacts") or ())
    require(
        int(manifest.get("artifact_count", -1)) == len(rows),
        "R14_transaction_artifact_count_mismatch",
    )
    rebuilt_rows: list[dict[str, Any]] = []
    declared_paths: list[str] = []
    for row in rows:
        require(
            isinstance(row, dict)
            and set(row) == {"relative_path", "size", "sha256", "semantic_root"}
            and type(row.get("size")) is int
            and row["size"] >= 0,
            "R14_transaction_artifact_row_schema_invalid",
        )
        relative_path = _safe_relative_path(str(row.get("relative_path") or ""))
        declared_paths.append(relative_path)
        artifact_path = final_path.joinpath(*PurePosixPath(relative_path).parts)
        _assert_existing_path_chain_safe(root, artifact_path)
        require(artifact_path.is_file(), "R14_transaction_artifact_missing")
        require_sha256(row.get("sha256"), field="transaction_artifact")
        require_sha256(row.get("semantic_root"), field="transaction_semantic_root")
        artifact_payload = artifact_path.read_bytes()
        from .dell_report_reconciliation_r14 import (
            recompute_program_artifact_semantic_root_r14,
        )

        try:
            recomputed_semantic_root = recompute_program_artifact_semantic_root_r14(
                relative_path=relative_path,
                payload=artifact_payload,
            )
        except Exception:
            require(False, "R14_transaction_artifact_reopen_mismatch")
        rebuilt_rows.append(
            {
                "relative_path": relative_path,
                "size": artifact_path.stat().st_size,
                "sha256": file_sha256(artifact_path),
                "semantic_root": recomputed_semantic_root,
            }
        )
    require(rebuilt_rows == rows, "R14_transaction_artifact_reopen_mismatch")
    require(
        tuple(declared_paths) == tuple(sorted(set(declared_paths)))
        and tuple(declared_paths)
        == tuple(reservation.get("expected_artifact_paths") or ()),
        "R14_transaction_artifact_path_bijection_failed",
    )
    rebuilt_bundle = domain_rows_digest(
        b"FIN_IA_R14_TRANSACTION_BUNDLE_V1\0",
        (canonical_json_bytes(row) for row in rebuilt_rows),
    )
    require(
        rebuilt_bundle == manifest.get("bundle_root") == marker.get("bundle_root"),
        "R14_transaction_bundle_root_mismatch",
    )
    actual_files: set[str] = set()
    for current_root, directory_names, file_names in os.walk(
        final_path, topdown=True, followlinks=False
    ):
        current = Path(current_root)
        _assert_existing_path_chain_safe(root, current)
        for name in (*directory_names, *file_names):
            child = current / name
            require(
                not _is_reparse_point(child),
                "R14_transaction_reader_descendant_reparse_point",
            )
        for name in file_names:
            actual_files.add((current / name).relative_to(final_path).as_posix())
    expected_files = set(declared_paths) | {
        "TRANSACTION_MANIFEST.json",
        "COMMITTED.json",
    }
    require(actual_files == expected_files, "R14_transaction_extra_or_missing_sidecar")
    return CommittedAttemptR14(
        final_path=final_path,
        reservation=reservation,
        transaction_manifest=manifest,
        committed_marker=marker,
    )


def load_committed_attempt_replay_material_r14(
    *,
    repository_root: Path,
    committed_attempt: CommittedAttemptR14,
    authority: FormalTransactionAuthorityR14,
    formal_policy: Mapping[str, Any],
) -> tuple[dict[str, bytes], Mapping[str, Any]]:
    """Reopen and bind the immutable transaction used as the replay oracle.

    Replay is intentionally anchored in one already committed attempt.  This
    preflight re-mints the Git authority, byte-binds the caller's policy to P,
    reopens all transaction sidecars, and captures the exact committed
    private/public payloads.  A second current recomputation is not evidence.
    """
    require(
        isinstance(committed_attempt, CommittedAttemptR14),
        "R14_replay_committed_attempt_type_invalid",
    )
    _validate_authority(authority)
    supplied_final_path = Path(committed_attempt.final_path).resolve(strict=True)
    supplied_reservation = committed_attempt.reservation
    supplied_manifest = committed_attempt.transaction_manifest
    supplied_marker = committed_attempt.committed_marker
    require(
        isinstance(supplied_reservation, Mapping)
        and isinstance(supplied_manifest, Mapping)
        and isinstance(supplied_marker, Mapping),
        "R14_replay_committed_sidecar_type_invalid",
    )
    attempt_id = _safe_component(
        str(supplied_reservation.get("attempt_id") or ""), field="attempt_id"
    )
    reopened = read_committed_attempt_r14(
        attempt_root=supplied_final_path.parent,
        attempt_id=attempt_id,
    )
    require(
        reopened.final_path == supplied_final_path
        and canonical_json_bytes(supplied_reservation)
        == canonical_json_bytes(reopened.reservation)
        and canonical_json_bytes(supplied_manifest)
        == canonical_json_bytes(reopened.transaction_manifest)
        and canonical_json_bytes(supplied_marker)
        == canonical_json_bytes(reopened.committed_marker),
        "R14_replay_supplied_committed_attempt_not_exact",
    )

    reminted = mint_formal_transaction_authority_r14(
        repository_root=repository_root,
        governance_commit=authority.governance_commit,
        implementation_commit=authority.implementation_commit,
        bundle_commit=authority.bundle_commit,
        audit_commit=authority.audit_commit,
        policy_commit=authority.policy_commit,
        commitment_path=R14_PREFORMAL_COMMITMENT_PATH,
        preformal_audit_path=R14_PREFORMAL_AUDIT_PATH,
        policy_path=R14_FORMAL_POLICY_PATH,
    )
    require(reminted == authority, "R14_replay_authority_not_exact")
    policy, policy_bytes = _git_json_blob(
        Path(repository_root).resolve(strict=True),
        authority.policy_commit,
        R14_FORMAL_POLICY_PATH,
    )
    require(
        isinstance(formal_policy, Mapping)
        and canonical_json_bytes(formal_policy) == policy_bytes
        and canonical_json_bytes(policy) == policy_bytes,
        "R14_replay_policy_not_exact",
    )

    reservation = reopened.reservation
    manifest = reopened.transaction_manifest
    marker = reopened.committed_marker
    expected_paths = authority.expected_artifact_paths
    from .dell_report_reconciliation_r14 import (
        PRIVATE_PROGRAM_ARTIFACT_PATH,
        PUBLIC_PROGRAM_ARTIFACT_PATH,
        recompute_program_artifact_semantic_root_r14,
    )

    require(
        expected_paths
        == tuple(sorted((PRIVATE_PROGRAM_ARTIFACT_PATH, PUBLIC_PROGRAM_ARTIFACT_PATH))),
        "R14_replay_formal_artifact_pathset_invalid",
    )
    expected_rows = [
        {
            "relative_path": path,
            "size": authority.expected_artifact_contracts[path]["exact_bytes"],
            "sha256": authority.expected_artifact_contracts[path]["sha256"],
            "semantic_root": authority.expected_artifact_contracts[path][
                "semantic_root"
            ],
        }
        for path in expected_paths
    ]
    require(
        reservation.get("policy_commit") == authority.policy_commit
        and reservation.get("commitment_digest") == authority.commitment_digest
        and tuple(reservation.get("expected_artifact_paths") or ())
        == expected_paths
        and manifest.get("commitment_digest") == authority.commitment_digest
        and manifest.get("artifacts") == expected_rows
        and marker.get("bundle_root") == manifest.get("bundle_root"),
        "R14_replay_transaction_authority_binding_mismatch",
    )

    reservation_path = (
        supplied_final_path.parent
        / "attempt_reservations"
        / f"{attempt_id}.json"
    )
    manifest_path = supplied_final_path / "TRANSACTION_MANIFEST.json"
    marker_path = supplied_final_path / "COMMITTED.json"
    reservation_bytes = reservation_path.read_bytes()
    manifest_bytes = manifest_path.read_bytes()
    marker_bytes = marker_path.read_bytes()
    require(
        reservation_bytes == canonical_json_bytes(reservation)
        and manifest_bytes == canonical_json_bytes(manifest)
        and marker_bytes == canonical_json_bytes(marker)
        and sha256_bytes(reservation_bytes) == marker["reservation_sha256"]
        and sha256_bytes(manifest_bytes)
        == marker["transaction_manifest_sha256"],
        "R14_replay_committed_sidecar_bytes_mismatch",
    )

    payloads: dict[str, bytes] = {}
    for row in expected_rows:
        relative_path = row["relative_path"]
        artifact_path = supplied_final_path.joinpath(
            *PurePosixPath(relative_path).parts
        )
        payload = artifact_path.read_bytes()
        semantic_root = recompute_program_artifact_semantic_root_r14(
            relative_path=relative_path,
            payload=payload,
        )
        require(
            len(payload) == row["size"]
            and sha256_bytes(payload) == row["sha256"]
            and semantic_root == row["semantic_root"],
            f"R14_replay_committed_artifact_bytes_mismatch:{relative_path}",
        )
        payloads[relative_path] = payload

    binding = with_result_digest(
        {
            "schema_version": "fin_ia_dell_03B_R14_replay_binding_v1_0",
            "attempt_id": attempt_id,
            "policy_commit": authority.policy_commit,
            "policy_sha256": sha256_bytes(policy_bytes),
            "policy_result_digest": policy["result_digest"],
            "authority_evidence_digest": authority.authority_evidence_digest,
            "commitment_digest": authority.commitment_digest,
            "reservation_sha256": sha256_bytes(reservation_bytes),
            "reservation_result_digest": reservation["result_digest"],
            "transaction_manifest_sha256": sha256_bytes(manifest_bytes),
            "transaction_manifest_result_digest": manifest["result_digest"],
            "committed_marker_sha256": sha256_bytes(marker_bytes),
            "committed_marker_result_digest": marker["result_digest"],
            "transaction_bundle_root": manifest["bundle_root"],
            "committed_marker_bundle_root": marker["bundle_root"],
            "sidecar_root": domain_rows_digest(
                b"FIN_IA_R14_REPLAY_SIDECARS_V1\0",
                (reservation_bytes, manifest_bytes, marker_bytes),
            ),
            "artifact_contracts": [
                {
                    "relative_path": row["relative_path"],
                    "exact_bytes": row["size"],
                    "sha256": row["sha256"],
                    "semantic_root": row["semantic_root"],
                }
                for row in expected_rows
            ],
            "exact_committed_sidecars": True,
            "model_provider_calls": 0,
        }
    )
    return payloads, binding


__all__ = [
    "AttemptTransactionPathsR14",
    "CommittedAttemptR14",
    "FormalTransactionAuthorityR14",
    "R14_FORMAL_POLICY_PATH",
    "R14_PREFORMAL_AUDIT_PATH",
    "R14_PREFORMAL_COMMITMENT_PATH",
    "TransactionDurabilityCapabilityR14",
    "TransactionArtifactR14",
    "load_committed_attempt_replay_material_r14",
    "mint_formal_transaction_authority_r14",
    "probe_transaction_durability_r14",
    "publish_atomic_attempt_r14",
    "read_committed_attempt_r14",
    "resolve_attempt_transaction_paths_r14",
    "validate_transaction_durability_capability_r14",
]
