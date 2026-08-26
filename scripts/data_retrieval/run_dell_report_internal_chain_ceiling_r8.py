from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path[:0] = [str(ROOT), str(SRC)]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from apps.workbench.backend.application.research_retrieval_service import (  # noqa: E402
    ResearchRetrievalPrincipal,
    ResearchRetrievalService,
)
from retrieval.dell_report_internal_chain_ceiling import (  # noqa: E402
    validate_dell_report_source_compiled_identity_population,
)
from retrieval import dell_report_internal_chain_ceiling_r7 as r7  # noqa: E402
from retrieval.dell_report_internal_chain_ceiling_r8 import (  # noqa: E402
    ATTEMPT_ID,
    ATTEMPT_RECEIPT_REF,
    BRANCH,
    EXPECTED_BOUND_INPUT_IDS,
    MIN_FREE_BYTES_BEFORE_ATTEMPT,
    POLICY_REF,
    POLICY_SCHEMA_VERSION,
    PRIVATE_REF,
    PUBLIC_REF,
    RAW_EXECUTION_CAPTURE_REF,
    TERMINAL_FAILURE_RECEIPT_REF,
    build_dell_report_internal_chain_ceiling_r8_public_projection,
    compile_dell_report_internal_chain_ceiling_r8_result,
    validate_dell_report_internal_chain_ceiling_r8_policy,
)
from retrieval.query_plan import canonical_digest  # noqa: E402
from scripts.data_retrieval import (  # noqa: E402
    run_dell_report_internal_chain_ceiling_r4 as base,
)


R7_POLICY = ROOT / r7.POLICY_REF
R7_PRIVATE = ROOT / r7.PRIVATE_REF
POLICY = ROOT / POLICY_REF
DEFAULT_PRIVATE = ROOT / PRIVATE_REF
DEFAULT_PUBLIC = ROOT / PUBLIC_REF
ATTEMPT_RECEIPT = ROOT / ATTEMPT_RECEIPT_REF
RAW_EXECUTION_CAPTURE = ROOT / RAW_EXECUTION_CAPTURE_REF
TERMINAL_FAILURE_RECEIPT = ROOT / TERMINAL_FAILURE_RECEIPT_REF


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"dell_03B_R8_json_not_mapping:{path.name}")
    return value


def _bound_path(policy: Mapping[str, Any], binding_id: str) -> Path:
    row = dict((policy.get("bound_inputs") or {}).get(binding_id) or {})
    path = base._resolve(str(row.get("ref") or ""))  # noqa: SLF001
    if not path.is_file():
        raise ValueError(f"dell_03B_R8_bound_input_missing:{binding_id}")
    if base._sha256(path) != str(row.get("sha256") or ""):  # noqa: SLF001
        raise ValueError(f"dell_03B_R8_bound_input_sha_drift:{binding_id}")
    return path


def _bound_json(
    policy: Mapping[str, Any], binding_id: str
) -> tuple[Path, dict[str, Any]]:
    path = _bound_path(policy, binding_id)
    return path, _read_json(path)


def _head() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip().lower()


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


def _require_clean() -> None:
    if _git("status", "--porcelain", "--untracked-files=all"):
        raise RuntimeError("dell_03B_R8_clean_worktree_required")


def _clean_exact_git_receipt(policy: Mapping[str, Any]) -> dict[str, Any]:
    identity = dict(policy.get("execution_identity") or {})
    status = _git("status", "--porcelain", "--untracked-files=all")
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    head = _git("rev-parse", "HEAD").lower()
    upstream = _git("rev-parse", "@{upstream}").lower()
    parents = _git("show", "-s", "--format=%P", "HEAD").lower().split()
    implementation_commit = str(
        identity.get("implementation_commit") or ""
    ).lower()
    implementation_tree = str(identity.get("implementation_tree") or "").lower()
    actual_implementation_tree = _git(
        "show", "-s", "--format=%T", implementation_commit
    ).lower()
    changed_paths = sorted(
        line.replace("\\", "/")
        for line in _git(
            "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"
        ).splitlines()
        if line.strip()
    )
    expected_changed_paths = sorted(
        identity.get("authority_commit_changed_paths") or ()
    )
    if (
        status
        or branch != BRANCH
        or branch != identity.get("branch")
        or head != upstream
        or parents != [implementation_commit]
        or actual_implementation_tree != implementation_tree
        or changed_paths != expected_changed_paths
    ):
        raise RuntimeError("dell_03B_R8_exact_clean_synced_git_identity_required")
    return {
        "branch": branch,
        "head": head,
        "head_tree": _git("show", "-s", "--format=%T", "HEAD").lower(),
        "upstream": upstream,
        "implementation_commit": implementation_commit,
        "implementation_tree": implementation_tree,
        "authority_commit_changed_paths": changed_paths,
        "clean": True,
        "upstream_equal": True,
        "authority_parent_exact": True,
    }


def _validate_implementation_bindings(policy: Mapping[str, Any]) -> None:
    rows = policy.get("implementation_bindings")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        raise ValueError("dell_03B_R8_implementation_bindings_invalid")
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("dell_03B_R8_implementation_bindings_invalid")
        ref = str(row.get("path") or "")
        if ref in seen:
            raise ValueError("dell_03B_R8_implementation_binding_duplicate")
        seen.add(ref)
        path = base._resolve(ref)  # noqa: SLF001
        if not path.is_file() or base._sha256(path) != str(  # noqa: SLF001
            row.get("sha256") or ""
        ):
            raise ValueError(f"dell_03B_R8_implementation_binding_drift:{ref}")


def _validate_canonical_output_paths() -> None:
    private_resolved = DEFAULT_PRIVATE.resolve()
    public_resolved = DEFAULT_PUBLIC.resolve()
    receipt_resolved = ATTEMPT_RECEIPT.resolve()
    raw_capture_resolved = RAW_EXECUTION_CAPTURE.resolve()
    terminal_failure_resolved = TERMINAL_FAILURE_RECEIPT.resolve()
    resolved_paths = {
        private_resolved,
        public_resolved,
        receipt_resolved,
        raw_capture_resolved,
        terminal_failure_resolved,
    }
    if len(resolved_paths) != 5:
        raise ValueError("dell_03B_R8_output_paths_must_be_distinct")
    if any(
        path.parent != private_resolved.parent
        for path in (
            receipt_resolved,
            raw_capture_resolved,
            terminal_failure_resolved,
        )
    ):
        raise ValueError("dell_03B_R8_attempt_receipt_private_parent_mismatch")


def _require_output_disk_capacity() -> dict[str, int]:
    usage = shutil.disk_usage(ROOT)
    if usage.free < MIN_FREE_BYTES_BEFORE_ATTEMPT:
        raise RuntimeError("dell_03B_R8_minimum_free_disk_capacity_required")
    return {
        "free_bytes": int(usage.free),
        "minimum_free_bytes": MIN_FREE_BYTES_BEFORE_ATTEMPT,
    }


def _write_attempt_consumption_receipt(
    *,
    policy: Mapping[str, Any],
    git_receipt: Mapping[str, Any],
    recorded_at: str,
) -> dict[str, Any]:
    if ATTEMPT_RECEIPT.exists() or ATTEMPT_RECEIPT.parent.exists():
        raise FileExistsError("dell_03B_R8_attempt_already_consumed")
    body = {
        "schema_version": (
            "fin_ia_dell_report_internal_chain_attempt_consumption_v1_0"
        ),
        "status": "attempt_consumed_execution_started_no_retry",
        "attempt_id": ATTEMPT_ID,
        "recorded_at": recorded_at,
        "policy_digest": policy.get("result_digest"),
        "authority_commit": git_receipt.get("head"),
        "authority_tree": git_receipt.get("head_tree"),
        "implementation_commit": git_receipt.get("implementation_commit"),
        "implementation_tree": git_receipt.get("implementation_tree"),
        "canonical_private_result_ref": PRIVATE_REF,
        "canonical_public_result_ref": PUBLIC_REF,
        "same_attempt_retry_authorized": False,
    }
    receipt = {**body, "result_digest": canonical_digest(body)}
    ATTEMPT_RECEIPT.parent.mkdir(parents=True, exist_ok=False)
    with ATTEMPT_RECEIPT.open("xb") as handle:
        handle.write(base._json_bytes(receipt))  # noqa: SLF001
        handle.flush()
        os.fsync(handle.fileno())
    return receipt


def _write_raw_execution_capture(
    *,
    policy: Mapping[str, Any],
    execution: Mapping[str, Any],
    execution_sha256: str,
    recorded_at: str,
) -> dict[str, Any]:
    if RAW_EXECUTION_CAPTURE.exists():
        raise FileExistsError("dell_03B_R8_raw_execution_capture_exists")
    body = {
        "schema_version": (
            "fin_ia_dell_report_internal_chain_raw_execution_capture_v1_0"
        ),
        "status": "raw_execution_captured_before_R8_compilation",
        "attempt_id": ATTEMPT_ID,
        "recorded_at": recorded_at,
        "policy_digest": policy.get("result_digest"),
        "raw_execution_sha256": execution_sha256,
        "raw_execution": dict(execution),
    }
    capture = {**body, "result_digest": canonical_digest(body)}
    with RAW_EXECUTION_CAPTURE.open("xb") as handle:
        handle.write(base._json_bytes(capture))  # noqa: SLF001
        handle.flush()
        os.fsync(handle.fileno())
    return capture


def _write_terminal_failure_receipt(
    *,
    policy: Mapping[str, Any],
    stage: str,
    exception_type: str,
    recorded_at: str,
) -> dict[str, Any]:
    if TERMINAL_FAILURE_RECEIPT.exists():
        raise FileExistsError("dell_03B_R8_terminal_failure_receipt_exists")
    raw_binding: dict[str, Any] | None = None
    if RAW_EXECUTION_CAPTURE.is_file():
        raw = _read_json(RAW_EXECUTION_CAPTURE)
        raw_binding = {
            "ref": RAW_EXECUTION_CAPTURE_REF,
            "sha256": base._sha256(RAW_EXECUTION_CAPTURE),  # noqa: SLF001
            "result_digest": raw.get("result_digest"),
            "raw_execution_sha256": raw.get("raw_execution_sha256"),
        }
    body = {
        "schema_version": (
            "fin_ia_dell_report_internal_chain_terminal_failure_v1_0"
        ),
        "status": "attempt_consumed_terminal_failure_no_retry",
        "attempt_id": ATTEMPT_ID,
        "recorded_at": recorded_at,
        "policy_digest": policy.get("result_digest"),
        "failure_stage": stage,
        "exception_type": exception_type,
        "exception_message_persisted": False,
        "same_attempt_retry_authorized": False,
        "raw_execution_capture": raw_binding,
    }
    receipt = {**body, "result_digest": canonical_digest(body)}
    with TERMINAL_FAILURE_RECEIPT.open("xb") as handle:
        handle.write(base._json_bytes(receipt))  # noqa: SLF001
        handle.flush()
        os.fsync(handle.fileno())
    return receipt


def _publish_atomic_pair(*, private_bytes: bytes, public_bytes: bytes) -> None:
    if DEFAULT_PRIVATE.exists() or DEFAULT_PUBLIC.exists():
        raise FileExistsError("dell_03B_R8_output_collision")
    DEFAULT_PRIVATE.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_PUBLIC.parent.mkdir(parents=True, exist_ok=True)
    private_tmp = DEFAULT_PRIVATE.with_name(
        f".{DEFAULT_PRIVATE.name}.{ATTEMPT_ID}.tmp"
    )
    public_tmp = DEFAULT_PUBLIC.with_name(
        f".{DEFAULT_PUBLIC.name}.{ATTEMPT_ID}.tmp"
    )
    if private_tmp.exists() or public_tmp.exists():
        raise FileExistsError("dell_03B_R8_temporary_output_collision")
    created_finals: list[Path] = []
    try:
        for path, payload in (
            (private_tmp, private_bytes),
            (public_tmp, public_bytes),
        ):
            with path.open("xb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        os.link(private_tmp, DEFAULT_PRIVATE)
        created_finals.append(DEFAULT_PRIVATE)
        os.link(public_tmp, DEFAULT_PUBLIC)
        created_finals.append(DEFAULT_PUBLIC)
    except BaseException:
        for path in reversed(created_finals):
            if path.exists():
                path.unlink()
        raise
    finally:
        for path in (private_tmp, public_tmp):
            if path.exists():
                path.unlink()


def _complete_family_ids(rows: Sequence[Mapping[str, Any]]) -> set[str]:
    return {
        str(row.get("canonical_source_family_id") or "")
        for row in rows
        if row.get("classification") == "complete_bounded_target_package"
    }


def _safe_layer_crosswalk(
    *,
    predecessor_rows: Sequence[Mapping[str, Any]],
    successor_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    predecessor_ids = _complete_family_ids(predecessor_rows)
    successor_ids = _complete_family_ids(successor_rows)
    changed_ids = sorted(predecessor_ids ^ successor_ids)
    successor_by_id = {
        str(row.get("canonical_source_family_id") or ""): row
        for row in successor_rows
    }
    return {
        "R7_complete_family_ids": sorted(predecessor_ids),
        "R8_complete_family_ids": sorted(successor_ids),
        "removed_by_R8": sorted(predecessor_ids - successor_ids),
        "added_by_R8": sorted(successor_ids - predecessor_ids),
        "R8_changed_family_assessments": [
            {
                "canonical_source_family_id": family_id,
                "classification": successor_by_id.get(family_id, {}).get(
                    "classification"
                ),
                "limitations": list(
                    successor_by_id.get(family_id, {}).get("limitations") or ()
                ),
                "accepted_frame_role_anchors": list(
                    successor_by_id.get(family_id, {}).get(
                        "accepted_frame_role_anchors"
                    )
                    or ()
                ),
            }
            for family_id in changed_ids
        ],
    }


def run_authorized_formal() -> dict[str, Any]:
    """Consume the unique R8 authority only after every fail-closed gate."""

    _validate_canonical_output_paths()
    disk_receipt = _require_output_disk_capacity()
    if not POLICY.is_file():
        raise FileNotFoundError("dell_03B_R8_canonical_policy_missing")
    policy = _read_json(POLICY)
    if policy.get("schema_version") != POLICY_SCHEMA_VERSION:
        raise ValueError("dell_03B_R8_policy_schema_invalid")
    git_receipt = _clean_exact_git_receipt(policy)
    _validate_implementation_bindings(policy)
    if (
        DEFAULT_PRIVATE.exists()
        or DEFAULT_PUBLIC.exists()
        or ATTEMPT_RECEIPT.parent.exists()
    ):
        raise FileExistsError("dell_03B_R8_attempt_or_output_exists")

    names = tuple(sorted(EXPECTED_BOUND_INPUT_IDS))
    bound = {name: _bound_json(policy, name) for name in names}
    values = {name: pair[1] for name, pair in bound.items()}
    validator_kwargs = {
        name[0].lower() + name[1:]: value for name, value in values.items()
    }
    legacy_policy = validate_dell_report_internal_chain_ceiling_r8_policy(
        policy,
        **validator_kwargs,
    )
    request_ids = {
        str(request_id)
        for contract in legacy_policy["target_contracts"]
        for request_id in contract["request_ids"]
    }
    execution_program = values["execution_program"]
    request_payloads = [
        dict(row)
        for row in execution_program.get("evidence_requests") or ()
        if str(row.get("request_id") or "") in request_ids
    ]
    if len(request_payloads) != 5 or {
        str(row.get("request_id") or "") for row in request_payloads
    } != request_ids:
        raise ValueError("dell_03B_R8_request_payload_population_invalid")
    blueprints = base._material_blueprints(  # noqa: SLF001
        execution_program,
        request_ids=request_ids,
    )
    runtime_binding = values["runtime_binding_receipt"]
    bindings = runtime_binding.get("bindings") or {}
    object_path = base._resolve(  # noqa: SLF001
        str((bindings.get("compiled_objects") or {}).get("ref") or "")
    )
    source_path = base._resolve(  # noqa: SLF001
        str((bindings.get("source_records") or {}).get("ref") or "")
    )
    if base._sha256(object_path) != str(  # noqa: SLF001
        (bindings.get("compiled_objects") or {}).get("sha256") or ""
    ):
        raise ValueError("dell_03B_R8_compiled_object_sha_drift")
    if base._sha256(source_path) != str(  # noqa: SLF001
        (bindings.get("source_records") or {}).get("sha256") or ""
    ):
        raise ValueError("dell_03B_R8_source_record_sha_drift")
    object_rows = base._read_jsonl(object_path)  # noqa: SLF001
    source_rows = base._read_jsonl(source_path)  # noqa: SLF001
    source_ids = base._source_record_ids(source_rows)  # noqa: SLF001
    validate_dell_report_source_compiled_identity_population(
        object_rows=object_rows,
        source_record_ids=source_ids,
        runtime_binding_receipt=runtime_binding,
    )

    recorded_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    attempt_receipt = _write_attempt_consumption_receipt(
        policy=policy,
        git_receipt=git_receipt,
        recorded_at=recorded_at,
    )
    failure_stage = "runtime_service_initialization"
    try:
        service = ResearchRetrievalService.from_runtime_paths(ROOT)
        principal = ResearchRetrievalPrincipal(
            mode="current",
            permissions=frozenset({"current_product:read"}),
        )
        failure_stage = "current_runtime_request_execution"
        execution = service.execute_current_runtime_requests(
            "DELL",
            request_payloads,
            principal,
            material_requirement_blueprints=blueprints,
        )
        if not isinstance(execution, Mapping):
            raise TypeError("dell_03B_R8_execution_not_mapping")
        execution_sha256 = hashlib.sha256(
            base._canonical_json_bytes(execution)  # noqa: SLF001
        ).hexdigest()
        failure_stage = "raw_execution_capture"
        _write_raw_execution_capture(
            policy=policy,
            execution=execution,
            execution_sha256=execution_sha256,
            recorded_at=recorded_at,
        )
        failure_stage = "private_result_compilation"
        input_bindings = {
            name: {
                "ref": base._relative(path),  # noqa: SLF001
                "sha256": base._sha256(path),  # noqa: SLF001
                **(
                    {"result_digest": value.get("result_digest")}
                    if value.get("result_digest")
                    else {}
                ),
            }
            for name, (path, value) in bound.items()
        }
        input_bindings.update(
            {
                "R8_policy": {
                    "ref": POLICY_REF,
                    "sha256": base._sha256(POLICY),  # noqa: SLF001
                    "result_digest": policy.get("result_digest"),
                },
                "compiled_objects": {
                    "ref": base._relative(object_path),  # noqa: SLF001
                    "sha256": base._sha256(object_path),  # noqa: SLF001
                },
                "source_records": {
                    "ref": base._relative(source_path),  # noqa: SLF001
                    "sha256": base._sha256(source_path),  # noqa: SLF001
                },
                "attempt_consumption_receipt": {
                    "ref": ATTEMPT_RECEIPT_REF,
                    "sha256": base._sha256(ATTEMPT_RECEIPT),  # noqa: SLF001
                    "result_digest": attempt_receipt.get("result_digest"),
                },
                "git_identity": dict(git_receipt),
                "disk_capacity_preflight": disk_receipt,
            }
        )
        private_result = compile_dell_report_internal_chain_ceiling_r8_result(
            legacy_policy=legacy_policy,
            r8_policy=policy,
            residual_program=values["residual_program"],
            runtime_registry=values["runtime_registry"],
            runtime_binding_receipt=runtime_binding,
            execution=execution,
            execution_sha256=execution_sha256,
            source_rows=source_rows,
            object_rows=object_rows,
            recorded_at=recorded_at,
            prepared_from_commit=str(git_receipt["head"]),
            input_bindings=input_bindings,
        )
        private_bytes = base._json_bytes(private_result)  # noqa: SLF001
        private_sha256 = hashlib.sha256(private_bytes).hexdigest()
        failure_stage = "public_projection"
        public_result = (
            build_dell_report_internal_chain_ceiling_r8_public_projection(
                private_result=private_result,
                private_ref=PRIVATE_REF,
                private_sha256=private_sha256,
            )
        )
        public_bytes = base._json_bytes(public_result)  # noqa: SLF001
        failure_stage = "clean_identity_recheck"
        _require_clean()
        failure_stage = "atomic_private_public_publish"
        _publish_atomic_pair(
            private_bytes=private_bytes,
            public_bytes=public_bytes,
        )
        return public_result
    except BaseException as exc:
        try:
            _write_terminal_failure_receipt(
                policy=policy,
                stage=failure_stage,
                exception_type=type(exc).__name__,
                recorded_at=(
                    datetime.now(timezone.utc)
                    .replace(microsecond=0)
                    .isoformat()
                ),
            )
        except BaseException:
            pass
        raise


def preview_from_r7_saved_raw() -> dict[str, Any]:
    """Recompile immutable R7 raw bytes without model, network or output writes."""

    if not R7_POLICY.is_file() or not R7_PRIVATE.is_file():
        raise FileNotFoundError("dell_03B_R8_R7_saved_raw_predecessor_missing")
    if any(
        (ROOT / ref).exists()
        for ref in (POLICY_REF, PRIVATE_REF, PUBLIC_REF)
    ):
        raise FileExistsError("dell_03B_R8_preview_requires_no_R8_policy_or_result")

    r7_policy = _read_json(R7_POLICY)
    r7_private = _read_json(R7_PRIVATE)
    if r7_private.get("attempt_id") != r7.ATTEMPT_ID:
        raise ValueError("dell_03B_R8_predecessor_attempt_invalid")
    r1_policy = _read_json(_bound_path(r7_policy, "R1_policy"))
    residual_program = _read_json(_bound_path(r7_policy, "residual_program"))
    runtime_registry = _read_json(_bound_path(r7_policy, "runtime_registry"))
    runtime_binding = _read_json(
        _bound_path(r7_policy, "runtime_binding_receipt")
    )
    bindings = dict(runtime_binding.get("bindings") or {})
    object_path = base._resolve(  # noqa: SLF001
        str((bindings.get("compiled_objects") or {}).get("ref") or "")
    )
    source_path = base._resolve(  # noqa: SLF001
        str((bindings.get("source_records") or {}).get("ref") or "")
    )
    if base._sha256(object_path) != str(  # noqa: SLF001
        (bindings.get("compiled_objects") or {}).get("sha256") or ""
    ):
        raise ValueError("dell_03B_R8_compiled_object_sha_drift")
    if base._sha256(source_path) != str(  # noqa: SLF001
        (bindings.get("source_records") or {}).get("sha256") or ""
    ):
        raise ValueError("dell_03B_R8_source_record_sha_drift")
    object_rows = base._read_jsonl(object_path)  # noqa: SLF001
    source_rows = base._read_jsonl(source_path)  # noqa: SLF001
    execution = dict(r7_private.get("raw_execution_receipt") or {})
    execution_sha256 = hashlib.sha256(
        json.dumps(
            execution,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    if execution_sha256 != r7_private.get("raw_execution_sha256"):
        raise ValueError("dell_03B_R8_saved_raw_execution_sha_drift")

    started_at = datetime.now(timezone.utc)
    compiled = compile_dell_report_internal_chain_ceiling_r8_result(
        legacy_policy=r1_policy,
        r8_policy={"result_digest": "0" * 64},
        residual_program=residual_program,
        runtime_registry=runtime_registry,
        runtime_binding_receipt=runtime_binding,
        execution=execution,
        execution_sha256=execution_sha256,
        source_rows=source_rows,
        object_rows=object_rows,
        recorded_at=started_at.replace(microsecond=0).isoformat(),
        prepared_from_commit=_head(),
        input_bindings={},
    )
    elapsed_seconds = (datetime.now(timezone.utc) - started_at).total_seconds()
    predecessor_targets = {
        str(row.get("target_id") or ""): row
        for row in r7_private.get("target_results") or ()
    }
    targets = []
    for row in compiled["target_results"]:
        ceiling = row["candidate_ceiling"]
        downstream = row["downstream_disposition"]
        predecessor = predecessor_targets[row["target_id"]]
        predecessor_ceiling = predecessor["candidate_ceiling"]
        layers = {
            "source": ("private_source_packages", "private_source_packages"),
            "compiled": (
                "private_compiled_packages",
                "private_compiled_packages",
            ),
            "union": ("private_union_packages", "private_union_packages"),
            "final": ("private_final_packages", "private_final_packages"),
        }
        targets.append(
            {
                "target_id": row["target_id"],
                "R7_source_compiled_union_final": [
                    predecessor_ceiling[
                        "complete_target_in_source_record_corpus_count"
                    ],
                    predecessor_ceiling[
                        "complete_target_in_compiled_package_corpus_count"
                    ],
                    predecessor_ceiling[
                        "complete_target_in_candidate_union_package_count"
                    ],
                    predecessor_ceiling[
                        "complete_target_in_final_review_package_count"
                    ],
                ],
                "source_compiled_union_final": [
                    ceiling["complete_target_in_source_record_corpus_count"],
                    ceiling["complete_target_in_compiled_package_corpus_count"],
                    ceiling["complete_target_in_candidate_union_package_count"],
                    ceiling["complete_target_in_final_review_package_count"],
                ],
                "best_final_rank": ceiling[
                    "best_complete_package_final_completion_rank"
                ],
                "coverage_gap_canonical": ceiling[
                    "material_source_claim_coverage_gap_canonical_count"
                ],
                "coverage_gap_summaries": [
                    {
                        "canonical_source_family_id": gap[
                            "canonical_source_family_id"
                        ],
                        "source_occurrence_count": gap[
                            "source_occurrence_count"
                        ],
                        "required_material_group_ids": list(
                            gap["required_material_group_ids"]
                        ),
                        "material_anchors": list(gap["material_anchors"]),
                        "anchor_mode": gap["anchor_mode"],
                        "reason": gap["reason"],
                    }
                    for gap in row[
                        "private_source_to_object_coverage_gaps"
                    ]
                ],
                "local_repair_required": downstream[
                    "local_source_to_object_repair_required"
                ],
                "external_required": downstream[
                    "03C_external_route_required_for_complete_bounded_target"
                ],
                "4B_eligible": downstream[
                    "03D_4B_embedding_recall_challenger_eligible"
                ],
                "reranker_eligible": downstream[
                    "03D_same_pool_reranker_challenger_eligible"
                ],
                "layer_crosswalk": {
                    layer: _safe_layer_crosswalk(
                        predecessor_rows=predecessor[predecessor_key],
                        successor_rows=row[successor_key],
                    )
                    for layer, (predecessor_key, successor_key) in layers.items()
                },
            }
        )
    body = {
        "schema_version": "fin_ia_dell_report_internal_chain_r8_zero_model_preview_v1_0",
        "status": "R8_zero_model_saved_R7_raw_recompile_preview_no_attempt_no_output_write",
        "attempt_id": ATTEMPT_ID,
        "prepared_from_commit": _head(),
        "predecessor_attempt_id": r7.ATTEMPT_ID,
        "predecessor_private_result_digest": r7_private.get("result_digest"),
        "predecessor_raw_execution_sha256": execution_sha256,
        "source_record_count": len(source_rows),
        "compiled_object_count": len(object_rows),
        "elapsed_seconds": round(elapsed_seconds, 3),
        "targets": targets,
        "summary": {
            "external_required": sum(row["external_required"] is True for row in targets),
            "local_repair_required": sum(
                row["local_repair_required"] is True for row in targets
            ),
            "4B_eligible": sum(row["4B_eligible"] is True for row in targets),
            "reranker_eligible": sum(
                row["reranker_eligible"] is True for row in targets
            ),
        },
        "forbidden_activity": {
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": 0,
            "embedding_batches": 0,
            "4B_calls": 0,
            "reranker_calls": 0,
            "external_calls": 0,
            "policy_writes": 0,
            "attempt_writes": 0,
            "private_result_writes": 0,
            "public_result_writes": 0,
        },
        "known_boundary": (
            "This preview recompiles immutable saved R7 raw execution through "
            "the R8 classifier in memory. It is not an R8 authority, attempt, "
            "private/public result, independent audit or downstream permission."
        ),
    }
    return {**body, "result_digest": canonical_digest(body)}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Preview the DELL 03B R8 span-bound predicate-frame compiler from "
            "immutable R7 saved raw execution without consuming an attempt."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--preview-from-r7-saved-raw",
        action="store_true",
        help="Run the zero-model, zero-write R8 implementation preview.",
    )
    mode.add_argument(
        "--execute-authorized-formal",
        action="store_true",
        help=(
            "Consume the unique R8 attempt only from a clean, synced, "
            "policy-only authority commit."
        ),
    )
    args = parser.parse_args(argv)
    result = (
        preview_from_r7_saved_raw()
        if args.preview_from_r7_saved_raw
        else run_authorized_formal()
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
