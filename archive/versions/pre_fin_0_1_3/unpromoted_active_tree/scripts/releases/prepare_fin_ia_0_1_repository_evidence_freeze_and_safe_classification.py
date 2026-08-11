from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "fin_ia_0_1_repository_evidence_freeze_and_safe_classification_inventory_v1_0"
DECISION_ID = "FIN-0.1-REPOSITORY-EVIDENCE-FREEZE-AND-SAFE-CLASSIFICATION-EXECUTION"
NEXT_ACTION = "FIN-0.1-REPOSITORY-CLASSIFICATION-OWNER-REVIEW-AND-COHERENT-COMMIT-SLICE-AUTHORITY-DECISION"

SECRET_PATTERNS = {
    "openai_style_key": re.compile(
        rb"(?<![A-Za-z0-9_])sk-(?:proj-)?[A-Za-z0-9_-]{20,}"
    ),
    "bearer_token": re.compile(
        rb"(?i)(?<![-A-Za-z])Bearer[ \t]+[A-Za-z0-9._~-]{20,}"
    ),
    "environment_secret_assignment": re.compile(
        rb"(?im)^(?:export[ \t]+)?[A-Z0-9_]*(?:API_KEY|TOKEN|SECRET)[A-Z0-9_]*"
        rb"[ \t]*=[ \t]*[\"']?([A-Za-z0-9._~+/=-]{20,})"
    ),
}

INTENTIONAL_NON_SECRET_CREDENTIAL_FIXTURES = {
    (
        "tests/contract/"
        "test_fin_0_1_s4_t06_entry_single_node_strict_schema_canary_runner.py"
    ): {
        "match_types": {"openai_style_key"},
        "evidence": (
            "zero-call and fake-completion tests set a declared non-real key and "
            "assert that it is not persisted"
        ),
    },
    (
        "tests/contract/"
        "test_fin_0_1_s4_t06_runtime_audit_evidence_v2_and_material_numeric_"
        "classifier_zero_call_implementation.py"
    ): {
        "match_types": {"bearer_token"},
        "evidence": (
            "unsafe-capture fixture intentionally embeds an authorization-shaped "
            "value to prove capture refusal and redaction"
        ),
    },
}

EPHEMERAL_PATTERNS = (
    re.compile(r"(^|/)(__pycache__|\.pytest_cache|\.mypy_cache|\.ruff_cache)(/|$)"),
    re.compile(r"\.(pyc|pyo|tmp|temp|bak|swp|log)$"),
    re.compile(r"(^|/)(tmp|temp|cache)(/|$)"),
)


def _git(root: Path, *args: str, check: bool = True) -> bytes:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and completed.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed: "
            f"{completed.stderr.decode('utf-8', errors='replace').strip()}"
        )
    return completed.stdout


def _decode(value: bytes) -> str:
    return value.decode("utf-8", errors="surrogateescape")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return _sha256_bytes(payload)


def _parse_status(root: Path, excluded_paths: set[str]) -> tuple[bytes, list[dict[str, Any]]]:
    raw = _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    chunks = raw.split(b"\0")
    entries: list[dict[str, Any]] = []
    index = 0
    while index < len(chunks):
        chunk = chunks[index]
        index += 1
        if not chunk:
            continue
        if len(chunk) < 4:
            raise RuntimeError(f"unexpected porcelain entry: {chunk!r}")
        code = _decode(chunk[:2])
        path = _decode(chunk[3:]).replace("\\", "/")
        original_path: str | None = None
        if code[0] in {"R", "C"}:
            if index >= len(chunks):
                raise RuntimeError(f"rename/copy missing origin: {path}")
            original_path = _decode(chunks[index]).replace("\\", "/")
            index += 1
        if path in excluded_paths:
            continue
        entries.append(
            {
                "status_code": code,
                "path": path,
                "original_path": original_path,
            }
        )
    entries.sort(key=lambda item: (item["path"], item["status_code"]))
    return raw, entries


def _parse_index(root: Path) -> dict[str, dict[str, str]]:
    raw = _git(root, "ls-files", "--stage", "-z")
    result: dict[str, dict[str, str]] = {}
    for chunk in raw.split(b"\0"):
        if not chunk:
            continue
        meta, path_raw = chunk.split(b"\t", 1)
        mode_raw, oid_raw, stage_raw = meta.split(b" ", 2)
        if stage_raw != b"0":
            continue
        path = _decode(path_raw).replace("\\", "/")
        result[path] = {
            "mode": _decode(mode_raw),
            "git_oid": _decode(oid_raw),
        }
    return result


def _parse_head(root: Path) -> dict[str, dict[str, str]]:
    raw = _git(root, "ls-tree", "-r", "-z", "HEAD")
    result: dict[str, dict[str, str]] = {}
    for chunk in raw.split(b"\0"):
        if not chunk:
            continue
        meta, path_raw = chunk.split(b"\t", 1)
        mode_raw, object_type_raw, oid_raw = meta.split(b" ", 2)
        path = _decode(path_raw).replace("\\", "/")
        result[path] = {
            "mode": _decode(mode_raw),
            "object_type": _decode(object_type_raw),
            "git_oid": _decode(oid_raw),
        }
    return result


def _blob_sha256(root: Path, oids: Iterable[str]) -> dict[str, str]:
    unique = sorted(set(oids))
    if not unique:
        return {}
    proc = subprocess.Popen(
        ["git", "cat-file", "--batch"],
        cwd=root,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert proc.stdin is not None
    assert proc.stdout is not None
    result: dict[str, str] = {}
    try:
        for oid in unique:
            proc.stdin.write(oid.encode("ascii") + b"\n")
            proc.stdin.flush()
            header = proc.stdout.readline()
            parts = header.rstrip(b"\n").split(b" ")
            if len(parts) == 2 and parts[1] == b"missing":
                raise RuntimeError(f"missing git object: {oid}")
            if len(parts) != 3:
                raise RuntimeError(f"unexpected cat-file header for {oid}: {header!r}")
            size = int(parts[2])
            data = proc.stdout.read(size)
            terminator = proc.stdout.read(1)
            if len(data) != size or terminator != b"\n":
                raise RuntimeError(f"truncated cat-file payload for {oid}")
            result[oid] = _sha256_bytes(data)
    finally:
        proc.stdin.close()
        proc.wait(timeout=30)
    if proc.returncode != 0:
        stderr = b""
        if proc.stderr is not None:
            stderr = proc.stderr.read()
        raise RuntimeError(stderr.decode("utf-8", errors="replace"))
    return result


def _stage_slice(path: str) -> str:
    lower = path.lower()
    if (
        "repository_recovery" in lower
        or "repository_evidence_freeze" in lower
        or "safe_classification" in lower
        or "version_lineage" in lower
    ):
        return "repository_recovery_governance"
    stage_match = re.search(r"(?:fin(?:_ia)?_0_1|fin01).*?_s([0-5])(?:_|/)", lower)
    if stage_match:
        stage = stage_match.group(1)
        if stage == "3" and "_t09_" in lower:
            return "FIN_0_1_S3_T09_anchor_convergence"
        if stage == "4" and "_t05_" in lower:
            return "FIN_0_1_S4_T05_DELL_transfer"
        if stage == "4" and "_t06_" in lower:
            return "FIN_0_1_S4_T06_MU_transfer"
        return f"FIN_0_1_S{stage}"
    if "point01" in lower or "point_01" in lower:
        return "Point01_foundation"
    if "point02" in lower or "point_02" in lower:
        return "Point02_product_shell"
    if lower.startswith("docs/project_os/"):
        return "Project_OS"
    if "fin_ia_0_1" in lower or "fin_0_1" in lower or "fin01" in lower:
        return "FIN_0_1_program_shared"
    if lower == "docs/worklog/readme.md":
        return "Project_OS"
    if lower.startswith(
        (
            "docs/architecture/",
            "docs/product/",
            "docs/worklog/product_strategy/",
        )
    ):
        return "FIN_0_1_program_shared"
    if lower.startswith(("src/sec_agent/canonical_runtime/", "apps/workbench/")):
        return "shared_runtime_or_workbench"
    if lower.startswith(("src/sec_agent/", "tests/")):
        return "shared_runtime_or_workbench"
    if lower.startswith(("reports/", "data/manifests/")):
        return "execution_evidence"
    return "other_historical_or_unclassified"


def _artifact_role(path: str) -> str:
    lower = path.lower()
    if lower.startswith("configs/releases/"):
        return "machine_release_contract"
    if lower.startswith("configs/"):
        return "runtime_or_eval_config"
    if lower.startswith("tests/"):
        return "contract_or_regression_test"
    if lower.startswith("scripts/"):
        return "runner_generator_or_migration_script"
    if lower.startswith("docs/worklog/"):
        return "worklog"
    if lower.startswith("docs/project_os/"):
        return "project_os_ledger_or_context"
    if lower.startswith("docs/product/"):
        return "product_document"
    if lower.startswith("docs/architecture/"):
        return "architecture_or_technical_document"
    if lower.startswith(("src/", "apps/")):
        return "implementation"
    if lower.startswith(("reports/", "data/manifests/")):
        return "execution_or_evidence_artifact"
    return "other"


def _commit_slice(stage_slice: str, role: str) -> str:
    if stage_slice == "repository_recovery_governance":
        return "slice_06_repository_recovery_governance"
    if stage_slice in {
        "Point01_foundation",
        "Point02_product_shell",
        "FIN_0_1_program_shared",
    }:
        return "slice_00_foundation_and_product_shell"
    if stage_slice in {"FIN_0_1_S0", "FIN_0_1_S1", "FIN_0_1_S2"}:
        return "slice_02_FIN_0_1_one_cell_baseline"
    if stage_slice.startswith("FIN_0_1_S3"):
        return "slice_03_FIN_0_1_NVDA_anchor"
    if stage_slice.startswith("FIN_0_1_S4"):
        return "slice_04_FIN_0_1_three_case_transfer"
    if stage_slice == "Project_OS":
        return "slice_07_Project_OS_finalization"
    if stage_slice == "shared_runtime_or_workbench" or role == "implementation":
        return "slice_01_shared_runtime_and_workbench"
    if stage_slice == "execution_evidence":
        return "slice_05_execution_evidence"
    return "slice_08_owner_review_required"


def _is_ephemeral(path: str) -> bool:
    lower = path.lower()
    return any(pattern.search(lower) for pattern in EPHEMERAL_PATTERNS)


def _scan_secret_types(data: bytes) -> list[str]:
    if len(data) > 10 * 1024 * 1024 or b"\x00" in data[:8192]:
        return []
    return sorted(name for name, pattern in SECRET_PATTERNS.items() if pattern.search(data))


def _secret_scan_classification(path: str, secret_types: list[str]) -> str:
    if not secret_types:
        return "none"
    fixture = INTENTIONAL_NON_SECRET_CREDENTIAL_FIXTURES.get(path)
    if fixture and set(secret_types) == fixture["match_types"]:
        return "intentional_non_secret_credential_test_fixture"
    return "potential_plaintext_secret"


def _worktree_details(root: Path, path: str) -> dict[str, Any]:
    absolute = root / Path(path)
    if not absolute.exists() and not absolute.is_symlink():
        return {
            "exists": False,
            "kind": "missing",
            "size_bytes": None,
            "sha256": None,
            "secret_match_types": [],
        }
    if absolute.is_symlink():
        data = os.readlink(absolute).encode("utf-8", errors="surrogateescape")
        kind = "symlink"
    elif absolute.is_file():
        data = absolute.read_bytes()
        kind = "file"
    else:
        data = b""
        kind = "directory"
    return {
        "exists": True,
        "kind": kind,
        "size_bytes": len(data),
        "sha256": _sha256_bytes(data),
        "secret_match_types": _scan_secret_types(data),
    }


def _recoverability(code: str, has_head: bool, has_index: bool) -> str:
    index_state, worktree_state = code
    if code == "??":
        return "worktree_only_not_recoverable_from_Git"
    if index_state == "A" and worktree_state != " ":
        return "index_snapshot_and_distinct_worktree_delta_both_must_be_preserved"
    if index_state == "A":
        return "index_snapshot_only_no_HEAD_version"
    if index_state != " " and worktree_state != " ":
        return "HEAD_index_and_worktree_three_way_state"
    if worktree_state != " ":
        return "HEAD_plus_unstaged_worktree_state"
    if has_head and has_index:
        return "HEAD_plus_index_snapshot"
    if has_index:
        return "index_snapshot"
    return "manual_review"


def _risk_and_disposition(
    code: str,
    role: str,
    ephemeral: bool,
    secret_types: list[str],
    secret_scan_classification: str,
) -> tuple[str, str]:
    if secret_scan_classification == "potential_plaintext_secret":
        return (
            "critical",
            "quarantine_and_credential_rotation_review_before_any_commit_no_value_logged",
        )
    if ephemeral:
        return (
            "medium",
            "ephemeral_candidate_reference_and_reproducibility_review_before_delete",
        )
    if code == "??":
        if role in {
            "implementation",
            "contract_or_regression_test",
            "machine_release_contract",
            "runtime_or_eval_config",
            "runner_generator_or_migration_script",
        }:
            return "high", "retain_untracked_high_priority_commit_slice_candidate"
        return "medium", "retain_untracked_owner_review_required"
    if code[1] != " ":
        return "high", "preserve_index_and_worktree_versions_before_any_unstage"
    if code[0] == "A":
        return "medium", "retain_staged_addition_commit_slice_candidate"
    return "low", "retain_tracked_change_commit_slice_candidate"


def _build_inventory(
    root: Path,
    captured_at: str,
    excluded_paths: set[str],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    raw_status, status_entries = _parse_status(root, excluded_paths)
    index_map = _parse_index(root)
    head_map = _parse_head(root)
    relevant_oids: list[str] = []
    for status in status_entries:
        path = status["path"]
        if path in index_map:
            relevant_oids.append(index_map[path]["git_oid"])
        if path in head_map and head_map[path]["object_type"] == "blob":
            relevant_oids.append(head_map[path]["git_oid"])
    blob_sha = _blob_sha256(root, relevant_oids)

    entries: list[dict[str, Any]] = []
    for status in status_entries:
        path = status["path"]
        code = status["status_code"]
        head = head_map.get(path)
        index = index_map.get(path)
        worktree = _worktree_details(root, path)
        stage_slice = _stage_slice(path)
        role = _artifact_role(path)
        commit_slice = _commit_slice(stage_slice, role)
        ephemeral = _is_ephemeral(path)
        secret_scan_classification = _secret_scan_classification(
            path,
            worktree["secret_match_types"],
        )
        risk, disposition = _risk_and_disposition(
            code,
            role,
            ephemeral,
            worktree["secret_match_types"],
            secret_scan_classification,
        )
        entry = {
            "path": path,
            "original_path": status["original_path"],
            "status_code": code,
            "stage_slice": stage_slice,
            "artifact_role": role,
            "commit_slice": commit_slice,
            "risk": risk,
            "recommended_disposition": disposition,
            "ephemeral_candidate": ephemeral,
            "secret_scan_classification": secret_scan_classification,
            "recoverability": _recoverability(
                code,
                has_head=head is not None,
                has_index=index is not None,
            ),
            "HEAD": {
                "exists": head is not None,
                "mode": head["mode"] if head else None,
                "git_oid": head["git_oid"] if head else None,
                "sha256": blob_sha.get(head["git_oid"]) if head else None,
            },
            "index": {
                "exists": index is not None,
                "mode": index["mode"] if index else None,
                "git_oid": index["git_oid"] if index else None,
                "sha256": blob_sha.get(index["git_oid"]) if index else None,
            },
            "worktree": worktree,
        }
        entries.append(entry)

    def count(field: str) -> dict[str, int]:
        return dict(sorted(Counter(str(item[field]) for item in entries).items()))

    status_counts = dict(sorted(Counter(item["status_code"] for item in entries).items()))
    top_counts = dict(
        sorted(Counter(item["path"].split("/", 1)[0] for item in entries).items())
    )
    secret_paths = [
        {
            "path": item["path"],
            "match_types": item["worktree"]["secret_match_types"],
        }
        for item in entries
        if item["secret_scan_classification"] == "potential_plaintext_secret"
    ]
    intentional_secret_fixture_paths = [
        {
            "path": item["path"],
            "match_types": item["worktree"]["secret_match_types"],
            "evidence": INTENTIONAL_NON_SECRET_CREDENTIAL_FIXTURES[item["path"]][
                "evidence"
            ],
        }
        for item in entries
        if item["secret_scan_classification"]
        == "intentional_non_secret_credential_test_fixture"
    ]
    split_paths = [
        item["path"]
        for item in entries
        if item["status_code"] not in {"??"}
        and item["status_code"][1] != " "
    ]
    untracked_paths = [item["path"] for item in entries if item["status_code"] == "??"]
    ephemeral_paths = [item["path"] for item in entries if item["ephemeral_candidate"]]
    worktree_bytes = sum(
        item["worktree"]["size_bytes"] or 0
        for item in entries
        if item["worktree"]["exists"]
    )
    cached_diff = _git(root, "diff", "--cached", "--binary", "--no-ext-diff")
    worktree_diff = _git(root, "diff", "--binary", "--no-ext-diff")

    branch = _decode(_git(root, "branch", "--show-current")).strip()
    head = _decode(_git(root, "rev-parse", "HEAD")).strip()
    upstream_proc = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        cwd=root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    upstream = (
        _decode(upstream_proc.stdout).strip()
        if upstream_proc.returncode == 0
        else None
    )
    ahead = behind = None
    if upstream:
        counts = _decode(
            _git(root, "rev-list", "--left-right", "--count", f"{upstream}...HEAD")
        ).strip()
        behind_raw, ahead_raw = counts.split()
        ahead = int(ahead_raw)
        behind = int(behind_raw)

    summary = {
        "status_rows": len(entries),
        "status_code_counts": status_counts,
        "top_level_counts": top_counts,
        "stage_slice_counts": count("stage_slice"),
        "artifact_role_counts": count("artifact_role"),
        "commit_slice_counts": count("commit_slice"),
        "risk_counts": count("risk"),
        "recommended_disposition_counts": count("recommended_disposition"),
        "untracked_paths": len(untracked_paths),
        "index_worktree_split_paths": len(split_paths),
        "ephemeral_candidate_paths": len(ephemeral_paths),
        "potential_plaintext_secret_paths": len(secret_paths),
        "intentional_non_secret_credential_test_fixture_paths": len(
            intentional_secret_fixture_paths
        ),
        "worktree_bytes_in_status_scope": worktree_bytes,
    }
    inventory = {
        "schema_version": SCHEMA_VERSION,
        "decision_id": DECISION_ID,
        "captured_at": captured_at,
        "status": "pass_content_addressed_inventory_and_safe_classification_complete_no_repository_cleanup_or_git_mutation",
        "authority": {
            "user_instruction": "继续",
            "interpretation": "execute the frozen repository evidence inventory and safe classification only",
            "file_delete_move_unstage_reset_checkout_commit_push_tag_release_authorized": False,
            "model_provider_network_source_external_tool_or_live_authorized": False,
        },
        "capture_boundary": {
            "project_root": root.as_posix(),
            "branch": branch,
            "HEAD": head,
            "upstream": upstream,
            "ahead_behind": [ahead, behind],
            "excluded_output_paths": sorted(excluded_paths),
            "raw_git_status_sha256_before_output_exclusion": _sha256_bytes(raw_status),
            "cached_binary_diff": {
                "bytes": len(cached_diff),
                "sha256": _sha256_bytes(cached_diff),
                "content_persisted_in_inventory": False,
            },
            "unstaged_binary_diff": {
                "bytes": len(worktree_diff),
                "sha256": _sha256_bytes(worktree_diff),
                "content_persisted_in_inventory": False,
            },
            "secret_values_persisted": False,
            "file_bodies_persisted": False,
        },
        "summary": summary,
        "safety_findings": {
            "cleanup_ready": False,
            "safe_delete_candidates_proven": 0,
            "reason": "Every path remains retain-by-default until owner review, reference closure and recoverability proof. Untracked and index/worktree split paths are especially non-destructive.",
            "potential_plaintext_secret_findings": secret_paths,
            "intentional_non_secret_credential_test_fixtures": (
                intentional_secret_fixture_paths
            ),
            "ephemeral_candidates_not_authorized_for_delete": ephemeral_paths,
            "index_worktree_split_paths": split_paths,
        },
        "commit_slice_plan": [
            {
                "order": 0,
                "slice_id": "slice_00_foundation_and_product_shell",
                "purpose": "Point01 foundation Point02 product shell and program-wide contracts",
            },
            {
                "order": 1,
                "slice_id": "slice_01_shared_runtime_and_workbench",
                "purpose": "shared implementation consumed across stages",
            },
            {
                "order": 2,
                "slice_id": "slice_02_FIN_0_1_one_cell_baseline",
                "purpose": "S0 S1 S2 baseline and one-cell product evidence",
            },
            {
                "order": 3,
                "slice_id": "slice_03_FIN_0_1_NVDA_anchor",
                "purpose": "S3 NVDA anchor implementation contracts tests and evidence",
            },
            {
                "order": 4,
                "slice_id": "slice_04_FIN_0_1_three_case_transfer",
                "purpose": "S4 DELL MU NVDA transfer and honest-block evidence",
            },
            {
                "order": 5,
                "slice_id": "slice_05_execution_evidence",
                "purpose": "content-addressed reports manifests and execution evidence",
            },
            {
                "order": 6,
                "slice_id": "slice_06_repository_recovery_governance",
                "purpose": "audit version lineage inventory tests and no-mutation decision",
            },
            {
                "order": 7,
                "slice_id": "slice_07_Project_OS_finalization",
                "purpose": "current context capability root-cause and handoff ledgers after other slices",
            },
            {
                "order": 8,
                "slice_id": "slice_08_owner_review_required",
                "purpose": "paths not safely attributable by convention",
            },
        ],
        "rollback_policy": {
            "before_any_unstage_or_commit": [
                "owner_accepts_exact_path_classification",
                "all_potential_secret_findings_are_disposed_without_value_logging",
                "all_index_worktree_split_paths_have_both_digests_preserved",
                "each_commit_slice_has_exact_path_manifest_and_parent_HEAD",
                "no_slice_claims_release_or_product_pass"
            ],
            "delete_policy": "No delete candidate exists until a separate exact target list proves reproducibility no references and recovery path.",
        },
        "entries": entries,
        "execution_guard": {
            "status_before_and_after_excluding_output_equal": None,
            "unexpected_path_mutations": [],
            "file_deletes_moves_unstage_reset_checkout_commit_push_tag_release": 0,
            "model_provider_network_source_external_tool_or_live": 0,
        },
        "next_action": NEXT_ACTION,
    }
    return inventory, status_entries


def _status_signature(entries: list[dict[str, Any]]) -> str:
    compact = [
        [item["status_code"], item["path"], item["original_path"]]
        for item in entries
    ]
    return _canonical_sha256(compact)


def _write_inventory(
    root: Path,
    output: Path,
    inventory: dict[str, Any],
    before_entries: list[dict[str, Any]],
    excluded_paths: set[str],
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    preliminary = dict(inventory)
    preliminary["inventory_digest"] = _canonical_sha256(inventory)
    output.write_text(
        json.dumps(preliminary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    _, after_entries = _parse_status(root, excluded_paths)
    _, after_entries_including_output = _parse_status(root, set())
    before_signature = _status_signature(before_entries)
    after_signature = _status_signature(after_entries)
    guard = inventory["execution_guard"]
    guard["status_before_and_after_excluding_output_equal"] = (
        before_signature == after_signature
    )
    if before_signature != after_signature:
        before = {
            (item["status_code"], item["path"], item["original_path"])
            for item in before_entries
        }
        after = {
            (item["status_code"], item["path"], item["original_path"])
            for item in after_entries
        }
        guard["unexpected_path_mutations"] = sorted(
            [list(item) for item in before.symmetric_difference(after)]
        )
        raise RuntimeError("repository status changed outside the inventory output")

    output_entries = [
        item
        for item in after_entries_including_output
        if item["path"] in excluded_paths
    ]
    guard["inventory_scope_status_rows_excluding_output"] = len(after_entries)
    guard["post_write_status_rows_including_output"] = len(
        after_entries_including_output
    )
    guard["output_status_entries"] = output_entries
    if len(output_entries) != 1:
        raise RuntimeError("inventory output status entry was not uniquely observable")

    final_payload = dict(inventory)
    final_payload["inventory_digest"] = _canonical_sha256(inventory)
    output.write_text(
        json.dumps(final_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Freeze a content-addressed FIN 0.1 Git/index/worktree inventory."
    )
    parser.add_argument("--project-root", default=".")
    parser.add_argument(
        "--output",
        default=(
            "configs/releases/"
            "fin_ia_0_1_repository_evidence_freeze_and_safe_classification_inventory_v1_0.json"
        ),
    )
    parser.add_argument("--captured-at")
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    git_root = Path(_decode(_git(root, "rev-parse", "--show-toplevel")).strip()).resolve()
    output = Path(args.output)
    if not output.is_absolute():
        output = git_root / output
    try:
        relative_output = output.resolve().relative_to(git_root).as_posix()
    except ValueError as exc:
        raise RuntimeError("output must stay inside the repository") from exc
    excluded_paths = {relative_output}
    captured_at = args.captured_at or datetime.now().astimezone().isoformat(timespec="seconds")

    inventory, entries = _build_inventory(git_root, captured_at, excluded_paths)
    if args.summary_only:
        print(
            json.dumps(
                {
                    "captured_at": captured_at,
                    "summary": inventory["summary"],
                    "commit_slice_plan": inventory["commit_slice_plan"],
                    "potential_secret_finding_count": len(
                        inventory["safety_findings"]["potential_plaintext_secret_findings"]
                    ),
                    "potential_secret_findings_redacted": inventory["safety_findings"][
                        "potential_plaintext_secret_findings"
                    ],
                    "intentional_non_secret_credential_test_fixtures": inventory[
                        "safety_findings"
                    ]["intentional_non_secret_credential_test_fixtures"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    _write_inventory(git_root, output, inventory, entries, excluded_paths)
    result = json.loads(output.read_text(encoding="utf-8"))
    print(
        json.dumps(
            {
                "output": relative_output,
                "inventory_digest": result["inventory_digest"],
                "summary": result["summary"],
                "execution_guard": result["execution_guard"],
                "next_action": result["next_action"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
