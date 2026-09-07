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
from retrieval.dell_report_internal_chain_ceiling_r10 import (  # noqa: E402
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
    build_dell_report_internal_chain_ceiling_r10_public_projection,
    compile_dell_report_internal_chain_ceiling_r10_result,
    validate_dell_report_internal_chain_ceiling_r10_policy,
)
from retrieval.query_plan import canonical_digest  # noqa: E402
from scripts.data_retrieval import (  # noqa: E402
    run_dell_report_internal_chain_ceiling_r4 as base,
)


POLICY = ROOT / POLICY_REF
DEFAULT_PRIVATE = ROOT / PRIVATE_REF
DEFAULT_PUBLIC = ROOT / PUBLIC_REF
ATTEMPT_RECEIPT = ROOT / ATTEMPT_RECEIPT_REF
RAW_EXECUTION_CAPTURE = ROOT / RAW_EXECUTION_CAPTURE_REF
TERMINAL_FAILURE_RECEIPT = ROOT / TERMINAL_FAILURE_RECEIPT_REF


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"dell_03B_R10_json_not_mapping:{path.name}")
    return value


def _bound_path(policy: Mapping[str, Any], binding_id: str) -> Path:
    row = dict((policy.get("bound_inputs") or {}).get(binding_id) or {})
    path = base._resolve(str(row.get("ref") or ""))  # noqa: SLF001
    if not path.is_file():
        raise ValueError(f"dell_03B_R10_bound_input_missing:{binding_id}")
    if base._sha256(path) != str(row.get("sha256") or ""):  # noqa: SLF001
        raise ValueError(f"dell_03B_R10_bound_input_sha_drift:{binding_id}")
    return path


def _bound_json(
    policy: Mapping[str, Any], binding_id: str
) -> tuple[Path, dict[str, Any]]:
    path = _bound_path(policy, binding_id)
    return path, _read_json(path)


def _bound_value(
    policy: Mapping[str, Any], binding_id: str
) -> tuple[Path, dict[str, Any]]:
    path = _bound_path(policy, binding_id)
    if binding_id in {"source_records", "compiled_objects"}:
        return path, {
            "ref": base._relative(path),  # noqa: SLF001
            "sha256": base._sha256(path),  # noqa: SLF001
        }
    return path, _read_json(path)


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


def _head() -> str:
    return _git("rev-parse", "HEAD").lower()


def _require_clean() -> None:
    if _git("status", "--porcelain", "--untracked-files=all"):
        raise RuntimeError("dell_03B_R10_clean_worktree_required")


def _clean_exact_git_receipt(policy: Mapping[str, Any]) -> dict[str, Any]:
    identity = dict(policy.get("execution_identity") or {})
    status = _git("status", "--porcelain", "--untracked-files=all")
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    head = _head()
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
        raise RuntimeError("dell_03B_R10_exact_clean_synced_git_identity_required")
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
        raise ValueError("dell_03B_R10_implementation_bindings_invalid")
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("dell_03B_R10_implementation_bindings_invalid")
        ref = str(row.get("path") or "")
        if ref in seen:
            raise ValueError("dell_03B_R10_implementation_binding_duplicate")
        seen.add(ref)
        path = base._resolve(ref)  # noqa: SLF001
        if not path.is_file() or base._sha256(path) != str(  # noqa: SLF001
            row.get("sha256") or ""
        ):
            raise ValueError(f"dell_03B_R10_implementation_binding_drift:{ref}")


def _validate_r17_bundle(manifest: Mapping[str, Any]) -> None:
    rows = dict(manifest.get("R17_report_quality_bundle") or {})
    if len(rows) != 14:
        raise ValueError("dell_03B_R10_R17_bundle_not_14_files")
    for binding_id, raw in rows.items():
        row = dict(raw or {})
        path = base._resolve(str(row.get("ref") or ""))  # noqa: SLF001
        if not path.is_file() or base._sha256(path) != str(  # noqa: SLF001
            row.get("sha256") or ""
        ):
            raise ValueError(
                f"dell_03B_R10_R17_bundle_sha_drift:{binding_id}"
            )


def _validate_canonical_output_paths() -> None:
    paths = {
        DEFAULT_PRIVATE.resolve(),
        DEFAULT_PUBLIC.resolve(),
        ATTEMPT_RECEIPT.resolve(),
        RAW_EXECUTION_CAPTURE.resolve(),
        TERMINAL_FAILURE_RECEIPT.resolve(),
    }
    if len(paths) != 5:
        raise ValueError("dell_03B_R10_output_paths_must_be_distinct")
    if any(
        path.parent != DEFAULT_PRIVATE.resolve().parent
        for path in (
            ATTEMPT_RECEIPT.resolve(),
            RAW_EXECUTION_CAPTURE.resolve(),
            TERMINAL_FAILURE_RECEIPT.resolve(),
        )
    ):
        raise ValueError("dell_03B_R10_attempt_receipt_private_parent_mismatch")


def _require_output_disk_capacity() -> dict[str, int]:
    usage = shutil.disk_usage(ROOT)
    if usage.free < MIN_FREE_BYTES_BEFORE_ATTEMPT:
        raise RuntimeError("dell_03B_R10_minimum_free_disk_capacity_required")
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
        raise FileExistsError("dell_03B_R10_attempt_already_consumed")
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
        raise FileExistsError("dell_03B_R10_raw_execution_capture_exists")
    body = {
        "schema_version": (
            "fin_ia_dell_report_internal_chain_raw_execution_capture_v1_0"
        ),
        "status": "raw_execution_captured_before_R10_compilation",
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
        raise FileExistsError("dell_03B_R10_terminal_failure_receipt_exists")
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
        raise FileExistsError("dell_03B_R10_output_collision")
    DEFAULT_PRIVATE.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_PUBLIC.parent.mkdir(parents=True, exist_ok=True)
    private_tmp = DEFAULT_PRIVATE.with_name(
        f".{DEFAULT_PRIVATE.name}.{ATTEMPT_ID}.tmp"
    )
    public_tmp = DEFAULT_PUBLIC.with_name(
        f".{DEFAULT_PUBLIC.name}.{ATTEMPT_ID}.tmp"
    )
    if private_tmp.exists() or public_tmp.exists():
        raise FileExistsError("dell_03B_R10_temporary_output_collision")
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


def _runtime_rows(
    values: Mapping[str, Mapping[str, Any]],
) -> tuple[Path, Path, list[dict[str, Any]], list[dict[str, Any]]]:
    runtime_binding = values["runtime_binding_receipt"]
    bindings = dict(runtime_binding.get("bindings") or {})
    object_path = base._resolve(  # noqa: SLF001
        str((bindings.get("compiled_objects") or {}).get("ref") or "")
    )
    source_path = base._resolve(  # noqa: SLF001
        str((bindings.get("source_records") or {}).get("ref") or "")
    )
    if (
        base._sha256(object_path)  # noqa: SLF001
        != str((bindings.get("compiled_objects") or {}).get("sha256") or "")
        or base._sha256(source_path)  # noqa: SLF001
        != str((bindings.get("source_records") or {}).get("sha256") or "")
    ):
        raise ValueError("dell_03B_R10_runtime_source_or_object_sha_drift")
    object_rows = base._read_jsonl(object_path)  # noqa: SLF001
    source_rows = base._read_jsonl(source_path)  # noqa: SLF001
    validate_dell_report_source_compiled_identity_population(
        object_rows=object_rows,
        source_record_ids=base._source_record_ids(source_rows),  # noqa: SLF001
        runtime_binding_receipt=runtime_binding,
    )
    return object_path, source_path, object_rows, source_rows


def _request_payloads(
    *,
    execution_program: Mapping[str, Any],
    r9_private: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], set[str]]:
    request_ids = {
        str(request_id)
        for target in r9_private.get("target_results") or ()
        for request_id in target.get("request_ids") or ()
    }
    payloads = [
        dict(row)
        for row in execution_program.get("evidence_requests") or ()
        if str(row.get("request_id") or "") in request_ids
    ]
    if len(payloads) != 5 or {
        str(row.get("request_id") or "") for row in payloads
    } != request_ids:
        raise ValueError("dell_03B_R10_request_payload_population_invalid")
    return payloads, request_ids


def run_authorized_formal() -> dict[str, Any]:
    """Consume the unique R10 authority after every fail-closed gate."""

    _validate_canonical_output_paths()
    disk_receipt = _require_output_disk_capacity()
    if not POLICY.is_file():
        raise FileNotFoundError("dell_03B_R10_canonical_policy_missing")
    policy = _read_json(POLICY)
    if policy.get("schema_version") != POLICY_SCHEMA_VERSION:
        raise ValueError("dell_03B_R10_policy_schema_invalid")
    git_receipt = _clean_exact_git_receipt(policy)
    _validate_implementation_bindings(policy)
    if (
        DEFAULT_PRIVATE.exists()
        or DEFAULT_PUBLIC.exists()
        or ATTEMPT_RECEIPT.parent.exists()
    ):
        raise FileExistsError("dell_03B_R10_attempt_or_output_exists")

    names = tuple(sorted(EXPECTED_BOUND_INPUT_IDS))
    bound = {name: _bound_value(policy, name) for name in names}
    values = {name: pair[1] for name, pair in bound.items()}
    r9_private = validate_dell_report_internal_chain_ceiling_r10_policy(
        policy,
        **values,
    )
    _validate_r17_bundle(values["R17_report_bundle_carry_forward"])
    object_path, source_path, object_rows, source_rows = _runtime_rows(values)
    if (
        object_path.resolve() != bound["compiled_objects"][0].resolve()
        or source_path.resolve() != bound["source_records"][0].resolve()
    ):
        raise ValueError("dell_03B_R10_runtime_and_policy_data_path_mismatch")
    request_payloads, request_ids = _request_payloads(
        execution_program=values["execution_program"],
        r9_private=r9_private,
    )
    blueprints = base._material_blueprints(  # noqa: SLF001
        values["execution_program"],
        request_ids=request_ids,
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
            raise TypeError("dell_03B_R10_execution_not_mapping")
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
                "R10_policy": {
                    "ref": POLICY_REF,
                    "sha256": base._sha256(POLICY),  # noqa: SLF001
                    "result_digest": policy.get("result_digest"),
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
        private_result = compile_dell_report_internal_chain_ceiling_r10_result(
            r9_private_result=r9_private,
            r10_policy=policy,
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
            build_dell_report_internal_chain_ceiling_r10_public_projection(
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


def preview_from_r9_saved_raw() -> dict[str, Any]:
    """Recompile immutable R9 raw bytes without calls or output writes."""

    r9_private_path = ROOT / (
        "data/workbench_private/"
        "fin_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling/"
        "dell-rsq-03b-internal-chain-r9/full_result.json"
    )
    r9_raw_path = r9_private_path.with_name("raw_execution_capture.json")
    if not r9_private_path.is_file() or not r9_raw_path.is_file():
        raise FileNotFoundError("dell_03B_R10_R9_saved_raw_predecessor_missing")
    r9_private = _read_json(r9_private_path)
    r9_raw = _read_json(r9_raw_path)
    bindings = dict(r9_private.get("input_bindings") or {})
    source_path = base._resolve(  # noqa: SLF001
        str((bindings.get("source_records") or {}).get("ref") or "")
    )
    object_path = base._resolve(  # noqa: SLF001
        str((bindings.get("compiled_objects") or {}).get("ref") or "")
    )
    if (
        base._sha256(source_path)  # noqa: SLF001
        != str((bindings.get("source_records") or {}).get("sha256") or "")
        or base._sha256(object_path)  # noqa: SLF001
        != str((bindings.get("compiled_objects") or {}).get("sha256") or "")
    ):
        raise ValueError("dell_03B_R10_preview_source_or_object_sha_drift")
    source_rows = base._read_jsonl(source_path)  # noqa: SLF001
    object_rows = base._read_jsonl(object_path)  # noqa: SLF001
    execution = dict(r9_raw.get("raw_execution") or {})
    execution_sha256 = hashlib.sha256(
        base._canonical_json_bytes(execution)  # noqa: SLF001
    ).hexdigest()
    if (
        execution_sha256 != r9_raw.get("raw_execution_sha256")
        or execution_sha256 != r9_private.get("raw_execution_sha256")
        or execution != dict(r9_private.get("raw_execution_receipt") or {})
    ):
        raise ValueError("dell_03B_R10_R9_saved_raw_identity_mismatch")
    started_at = datetime.now(timezone.utc)
    compiled = compile_dell_report_internal_chain_ceiling_r10_result(
        r9_private_result=r9_private,
        r10_policy={"result_digest": "0" * 64},
        execution=execution,
        execution_sha256=execution_sha256,
        source_rows=source_rows,
        object_rows=object_rows,
        recorded_at=started_at.replace(microsecond=0).isoformat(),
        prepared_from_commit=_head(),
        input_bindings={},
    )
    predecessor_targets = {
        str(row.get("target_id") or ""): row
        for row in r9_private.get("target_results") or ()
    }
    targets = []
    for row in compiled["target_results"]:
        predecessor = predecessor_targets[row["target_id"]]
        before = predecessor["candidate_ceiling"]
        after = row["candidate_ceiling"]
        before_counts = [
            before["complete_target_in_source_record_corpus_count"],
            before["complete_target_in_compiled_package_corpus_count"],
            before["complete_target_in_candidate_union_package_count"],
            before["complete_target_in_final_review_package_count"],
        ]
        after_counts = [
            after["complete_target_in_source_record_corpus_count"],
            after["complete_target_in_compiled_package_corpus_count"],
            after["complete_target_in_candidate_union_package_count"],
            after["complete_target_in_final_review_package_count"],
        ]
        if before_counts == after_counts:
            delta_explanation = "no_complete_count_delta"
        elif row["target_id"].endswith("ASP") and after_counts == [0, 0, 0, 0]:
            delta_explanation = (
                "R9_only_complete_family_PUBLIC_DELL_EXT_329F1654BF36A1B63B37_"
                "used_generic_bounded_hardware_configuration_for_the_surface_"
                "hardware_without_a_specific_same_group_product;_R10_correctly_"
                "fails_closed_and_restores_ASP_external_source_requirement"
            )
        else:
            delta_explanation = "unexpected_complete_count_delta_requires_stop"
        targets.append(
            {
                "target_id": row["target_id"],
                "R9_source_compiled_union_final": before_counts,
                "R10_source_compiled_union_final": after_counts,
                "complete_count_delta_explanation": delta_explanation,
                "best_final_rank": after[
                    "best_complete_package_final_completion_rank"
                ],
                "earliest_observed_limitation": after[
                    "earliest_observed_limitation"
                ],
                "complete_transformation_coverage_pass": row[
                    "private_frame_transformation_summary"
                ]["complete_transformation_coverage_pass"],
                "partial_transformation_diagnostic_count": row[
                    "private_frame_transformation_summary"
                ]["unbound_partial_source_family_count"],
            }
        )
    if any(
        row["complete_count_delta_explanation"]
        == "unexpected_complete_count_delta_requires_stop"
        for row in targets
    ):
        raise ValueError("dell_03B_R10_preview_unexplained_complete_count_delta")
    return {
        "mode": "preview_from_immutable_R9_saved_raw_zero_call",
        "elapsed_seconds": (
            datetime.now(timezone.utc) - started_at
        ).total_seconds(),
        "source_record_count": len(source_rows),
        "compiled_object_count": len(object_rows),
        "targets": targets,
        "summary": compiled["summary"],
        "preview_digest": canonical_digest(targets),
    }


def replay_saved_formal() -> dict[str, Any]:
    """Recompile captured R10 raw bytes and prove canonical private equality."""

    if not all(
        path.is_file()
        for path in (
            POLICY,
            DEFAULT_PRIVATE,
            DEFAULT_PUBLIC,
            RAW_EXECUTION_CAPTURE,
        )
    ):
        raise FileNotFoundError("dell_03B_R10_formal_replay_inputs_missing")
    policy = _read_json(POLICY)
    private = _read_json(DEFAULT_PRIVATE)
    raw = _read_json(RAW_EXECUTION_CAPTURE)
    bound = {
        name: _bound_value(policy, name)
        for name in sorted(EXPECTED_BOUND_INPUT_IDS)
    }
    values = {name: pair[1] for name, pair in bound.items()}
    r9_private = validate_dell_report_internal_chain_ceiling_r10_policy(
        policy,
        **values,
    )
    _, _, object_rows, source_rows = _runtime_rows(values)
    execution = dict(raw.get("raw_execution") or {})
    replay = compile_dell_report_internal_chain_ceiling_r10_result(
        r9_private_result=r9_private,
        r10_policy=policy,
        execution=execution,
        execution_sha256=str(raw.get("raw_execution_sha256") or ""),
        source_rows=source_rows,
        object_rows=object_rows,
        recorded_at=str(private.get("recorded_at") or ""),
        prepared_from_commit=str(private.get("prepared_from_commit") or ""),
        input_bindings=dict(private.get("input_bindings") or {}),
    )
    equal = replay == private and base._json_bytes(replay) == base._json_bytes(  # noqa: SLF001
        private
    )
    if not equal:
        raise ValueError("dell_03B_R10_exact_private_replay_mismatch")
    return {
        "mode": "exact_saved_formal_replay",
        "private_dict_and_bytes_equal": True,
        "private_result_digest": private.get("result_digest"),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=("preview", "formal", "replay"),
        required=True,
    )
    args = parser.parse_args(argv)
    if args.mode == "preview":
        result = preview_from_r9_saved_raw()
    elif args.mode == "replay":
        result = replay_saved_formal()
    else:
        result = run_authorized_formal()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
