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

from retrieval.dell_report_internal_chain_ceiling import (  # noqa: E402
    validate_dell_report_source_compiled_identity_population,
)
from retrieval.dell_report_internal_chain_ceiling_r13 import (  # noqa: E402
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
    ZERO_EXECUTION_FIELDS,
    build_route_contract_identity_registry_r13,
    build_dell_report_internal_chain_ceiling_r13_public_projection,
    compile_dell_report_internal_chain_ceiling_r13_result,
    validate_dell_report_internal_chain_r13_saved_raw_execution,
    validate_dell_report_internal_chain_ceiling_r13_policy,
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
IMMUTABLE_R12_ATTEMPT_ID = "dell-rsq-03b-internal-chain-r12"
IMMUTABLE_CANONICAL_RAW_EXECUTION_SHA256 = (
    "0e9e4456ba75ecd07bc2e3bd6d5deddafc1972ba19700b029b2e6793e99f7458"
)
R13_RAW_REUSE_CAPTURE_SCHEMA_VERSION = (
    "fin_ia_dell_report_internal_chain_raw_reuse_capture_v2_0"
)
R13_RAW_REUSE_REASON = (
    "R13_changes_only_post_candidate_route_projection_semantic_compilation_"
    "and_reconciliation_R12_raw_reuse_candidate_union_and_ranks_are_immutable"
)
R13_NEW_CALL_COUNTERS = {
    "local_embedding_inference_batches": 0,
    **{field: 0 for field in ZERO_EXECUTION_FIELDS},
}


def _candidate_generation_equivalence_proof(
    execution: Mapping[str, Any],
) -> dict[str, Any]:
    summary = dict(execution.get("summary") or {})
    body = {
        "frozen_raw_execution_sha256": IMMUTABLE_CANONICAL_RAW_EXECUTION_SHA256,
        "frozen_request_count": summary.get("request_count"),
        "frozen_unique_candidate_union_count": summary.get(
            "hybrid_union_candidate_count"
        ),
        "frozen_final_review_count": summary.get(
            "hybrid_selected_candidate_count"
        ),
        "canonical_R11_local_embedding_inference_batches": summary.get(
            "local_embedding_inference_batches"
        ),
        "predecessor_R12_new_local_embedding_inference_batches": 0,
        "R13_new_local_embedding_inference_batches": 0,
        "request_payload_changed": False,
        "source_or_object_inventory_changed": False,
        "embedding_or_vector_changed": False,
        "candidate_union_or_raw_rank_changed": False,
        "R13_changed_stage": (
            "post_candidate_generation_route_projection_semantic_compiler_"
            "and_source_to_compiled_provenance_only"
        ),
    }
    if (
        body["frozen_request_count"] != 5
        or body["frozen_unique_candidate_union_count"] != 338
        or body["frozen_final_review_count"] != 80
        or body["canonical_R11_local_embedding_inference_batches"] != 1
    ):
        raise ValueError("dell_03B_R13_candidate_generation_equivalence_invalid")
    return {**body, "proof_digest": canonical_digest(body)}


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"dell_03B_R13_json_not_mapping:{path.name}")
    return value


def _bound_path(policy: Mapping[str, Any], binding_id: str) -> Path:
    row = dict((policy.get("bound_inputs") or {}).get(binding_id) or {})
    path = base._resolve(str(row.get("ref") or ""))  # noqa: SLF001
    if not path.is_file():
        raise ValueError(f"dell_03B_R13_bound_input_missing:{binding_id}")
    if base._sha256(path) != str(row.get("sha256") or ""):  # noqa: SLF001
        raise ValueError(f"dell_03B_R13_bound_input_sha_drift:{binding_id}")
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


def _self_digest(value: Mapping[str, Any]) -> bool:
    body = dict(value)
    observed = str(body.pop("result_digest", ""))
    return observed == canonical_digest(body)


def _expected_request_ids(
    r12_private: Mapping[str, Any],
) -> set[str]:
    return {
        str(request_id)
        for target in r12_private.get("target_results") or ()
        for request_id in target.get("request_ids") or ()
    }


def _validated_immutable_r12_execution(
    *,
    r12_private: Mapping[str, Any],
    r12_raw_capture: Mapping[str, Any],
) -> tuple[dict[str, Any], str]:
    """Return the frozen candidate surface through its immutable R12 wrapper."""

    raw = dict(r12_raw_capture)
    execution = dict(raw.get("raw_execution") or {})
    execution_sha256 = hashlib.sha256(
        base._canonical_json_bytes(execution)  # noqa: SLF001
    ).hexdigest()
    if (
        raw.get("schema_version")
        != "fin_ia_dell_report_internal_chain_raw_reuse_capture_v1_0"
        or raw.get("status")
        != "immutable_R11_raw_reused_before_R12_compilation_zero_new_calls"
        or raw.get("attempt_id") != IMMUTABLE_R12_ATTEMPT_ID
        or not _self_digest(raw)
        or r12_private.get("attempt_id") != IMMUTABLE_R12_ATTEMPT_ID
        or raw.get("policy_digest") != r12_private.get("policy_digest")
        or execution_sha256 != IMMUTABLE_CANONICAL_RAW_EXECUTION_SHA256
        or execution_sha256 != raw.get("raw_execution_sha256")
        or execution_sha256 != r12_private.get("raw_execution_sha256")
        or execution != dict(r12_private.get("raw_execution_receipt") or {})
        or dict(raw.get("R12_new_call_counters") or {}) != R13_NEW_CALL_COUNTERS
    ):
        raise ValueError("dell_03B_R13_R12_saved_raw_identity_mismatch")
    validate_dell_report_internal_chain_r13_saved_raw_execution(
        execution,
        expected_request_ids=_expected_request_ids(r12_private),
    )
    return execution, execution_sha256


def _validated_r13_raw_reuse_capture(
    *,
    capture: Mapping[str, Any],
    policy: Mapping[str, Any],
    r12_private: Mapping[str, Any],
    r12_raw_capture: Mapping[str, Any],
    r12_raw_ref: str,
    r12_raw_sha256: str,
) -> tuple[dict[str, Any], str]:
    """Validate R13's direct reuse receipt for immutable R12."""

    row = dict(capture)
    source = dict(row.get("source_R12_raw_reuse_capture") or {})
    if (
        row.get("schema_version") != R13_RAW_REUSE_CAPTURE_SCHEMA_VERSION
        or row.get("status")
        != "immutable_R12_raw_reused_before_R13_compilation_zero_new_calls"
        or row.get("attempt_id") != ATTEMPT_ID
        or row.get("policy_digest") != policy.get("result_digest")
        or not _self_digest(row)
        or source
        != {
            "ref": r12_raw_ref,
            "sha256": r12_raw_sha256,
            "result_digest": r12_raw_capture.get("result_digest"),
            "attempt_id": IMMUTABLE_R12_ATTEMPT_ID,
            "raw_execution_sha256": IMMUTABLE_CANONICAL_RAW_EXECUTION_SHA256,
        }
        or row.get("reuse_reason") != R13_RAW_REUSE_REASON
        or row.get("candidate_generation_equivalence_proof")
        != _candidate_generation_equivalence_proof(
            dict(row.get("raw_execution") or {})
        )
        or row.get("R13_new_call_counters") != R13_NEW_CALL_COUNTERS
    ):
        raise ValueError("dell_03B_R13_raw_reuse_capture_identity_invalid")
    execution, execution_sha256 = _validated_immutable_r12_execution(
        r12_private=r12_private,
        r12_raw_capture=r12_raw_capture,
    )
    if (
        dict(row.get("raw_execution") or {}) != execution
        or row.get("raw_execution_sha256") != execution_sha256
    ):
        raise ValueError("dell_03B_R13_raw_reuse_capture_payload_mismatch")
    return execution, execution_sha256


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
        raise RuntimeError("dell_03B_R13_clean_worktree_required")


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
        raise RuntimeError("dell_03B_R13_exact_clean_synced_git_identity_required")
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
        raise ValueError("dell_03B_R13_implementation_bindings_invalid")
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("dell_03B_R13_implementation_bindings_invalid")
        ref = str(row.get("path") or "")
        if ref in seen:
            raise ValueError("dell_03B_R13_implementation_binding_duplicate")
        seen.add(ref)
        path = base._resolve(ref)  # noqa: SLF001
        if not path.is_file() or base._sha256(path) != str(  # noqa: SLF001
            row.get("sha256") or ""
        ):
            raise ValueError(f"dell_03B_R13_implementation_binding_drift:{ref}")


def _validate_r17_bundle(manifest: Mapping[str, Any]) -> None:
    rows = dict(manifest.get("R17_report_quality_bundle") or {})
    if len(rows) != 14:
        raise ValueError("dell_03B_R13_R17_bundle_not_14_files")
    for binding_id, raw in rows.items():
        row = dict(raw or {})
        path = base._resolve(str(row.get("ref") or ""))  # noqa: SLF001
        if not path.is_file() or base._sha256(path) != str(  # noqa: SLF001
            row.get("sha256") or ""
        ):
            raise ValueError(
                f"dell_03B_R13_R17_bundle_sha_drift:{binding_id}"
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
        raise ValueError("dell_03B_R13_output_paths_must_be_distinct")
    if any(
        path.parent != DEFAULT_PRIVATE.resolve().parent
        for path in (
            ATTEMPT_RECEIPT.resolve(),
            RAW_EXECUTION_CAPTURE.resolve(),
            TERMINAL_FAILURE_RECEIPT.resolve(),
        )
    ):
        raise ValueError("dell_03B_R13_attempt_receipt_private_parent_mismatch")


def _require_output_disk_capacity() -> dict[str, int]:
    usage = shutil.disk_usage(ROOT)
    if usage.free < MIN_FREE_BYTES_BEFORE_ATTEMPT:
        raise RuntimeError("dell_03B_R13_minimum_free_disk_capacity_required")
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
        raise FileExistsError("dell_03B_R13_attempt_already_consumed")
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
    source_capture_ref: str,
    source_capture_sha256: str,
    source_capture_result_digest: str,
    recorded_at: str,
) -> dict[str, Any]:
    if RAW_EXECUTION_CAPTURE.exists():
        raise FileExistsError("dell_03B_R13_raw_execution_capture_exists")
    actual_execution_sha256 = hashlib.sha256(
        base._canonical_json_bytes(execution)  # noqa: SLF001
    ).hexdigest()
    if (
        execution_sha256 != IMMUTABLE_CANONICAL_RAW_EXECUTION_SHA256
        or execution_sha256 != actual_execution_sha256
        or not source_capture_ref.endswith(
            "/dell-rsq-03b-internal-chain-r12/raw_execution_capture.json"
        )
        or len(source_capture_sha256) != 64
        or len(source_capture_result_digest) != 64
    ):
        raise ValueError("dell_03B_R13_raw_reuse_capture_input_invalid")
    body = {
        "schema_version": R13_RAW_REUSE_CAPTURE_SCHEMA_VERSION,
        "status": (
            "immutable_R12_raw_reused_before_R13_compilation_zero_new_calls"
        ),
        "attempt_id": ATTEMPT_ID,
        "recorded_at": recorded_at,
        "policy_digest": policy.get("result_digest"),
        "source_R12_raw_reuse_capture": {
            "ref": source_capture_ref,
            "sha256": source_capture_sha256,
            "result_digest": source_capture_result_digest,
            "attempt_id": IMMUTABLE_R12_ATTEMPT_ID,
            "raw_execution_sha256": IMMUTABLE_CANONICAL_RAW_EXECUTION_SHA256,
        },
        "reuse_reason": R13_RAW_REUSE_REASON,
        "candidate_generation_equivalence_proof": (
            _candidate_generation_equivalence_proof(execution)
        ),
        "R13_new_call_counters": dict(R13_NEW_CALL_COUNTERS),
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
        raise FileExistsError("dell_03B_R13_terminal_failure_receipt_exists")
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
        raise FileExistsError("dell_03B_R13_output_collision")
    DEFAULT_PRIVATE.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_PUBLIC.parent.mkdir(parents=True, exist_ok=True)
    private_tmp = DEFAULT_PRIVATE.with_name(
        f".{DEFAULT_PRIVATE.name}.{ATTEMPT_ID}.tmp"
    )
    public_tmp = DEFAULT_PUBLIC.with_name(
        f".{DEFAULT_PUBLIC.name}.{ATTEMPT_ID}.tmp"
    )
    if private_tmp.exists() or public_tmp.exists():
        raise FileExistsError("dell_03B_R13_temporary_output_collision")
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
        raise ValueError("dell_03B_R13_runtime_source_or_object_sha_drift")
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
    r12_private: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], set[str]]:
    request_ids = {
        str(request_id)
        for target in r12_private.get("target_results") or ()
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
        raise ValueError("dell_03B_R13_request_payload_population_invalid")
    return payloads, request_ids


def run_authorized_formal() -> dict[str, Any]:
    """Consume the unique R13 authority after every fail-closed gate."""

    _validate_canonical_output_paths()
    disk_receipt = _require_output_disk_capacity()
    if not POLICY.is_file():
        raise FileNotFoundError("dell_03B_R13_canonical_policy_missing")
    policy = _read_json(POLICY)
    if policy.get("schema_version") != POLICY_SCHEMA_VERSION:
        raise ValueError("dell_03B_R13_policy_schema_invalid")
    git_receipt = _clean_exact_git_receipt(policy)
    _validate_implementation_bindings(policy)
    if (
        DEFAULT_PRIVATE.exists()
        or DEFAULT_PUBLIC.exists()
        or ATTEMPT_RECEIPT.parent.exists()
    ):
        raise FileExistsError("dell_03B_R13_attempt_or_output_exists")

    names = tuple(sorted(EXPECTED_BOUND_INPUT_IDS))
    bound = {name: _bound_value(policy, name) for name in names}
    values = {name: pair[1] for name, pair in bound.items()}
    r12_private = validate_dell_report_internal_chain_ceiling_r13_policy(
        policy,
        **values,
    )
    _validate_r17_bundle(values["R17_report_bundle_carry_forward"])
    object_path, source_path, object_rows, source_rows = _runtime_rows(values)
    if (
        object_path.resolve() != bound["compiled_objects"][0].resolve()
        or source_path.resolve() != bound["source_records"][0].resolve()
    ):
        raise ValueError("dell_03B_R13_runtime_and_policy_data_path_mismatch")
    _, request_ids = _request_payloads(
        execution_program=values["execution_program"],
        r12_private=r12_private,
    )
    if request_ids != _expected_request_ids(r12_private):
        raise ValueError("dell_03B_R13_request_identity_mismatch")
    r12_raw_path, r12_raw = bound["R12_raw_execution_capture"]
    r12_raw_ref = base._relative(r12_raw_path)  # noqa: SLF001
    r12_raw_sha256 = base._sha256(r12_raw_path)  # noqa: SLF001
    execution, execution_sha256 = _validated_immutable_r12_execution(
        r12_private=r12_private,
        r12_raw_capture=r12_raw,
    )

    recorded_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    attempt_receipt = _write_attempt_consumption_receipt(
        policy=policy,
        git_receipt=git_receipt,
        recorded_at=recorded_at,
    )
    failure_stage = "immutable_R12_raw_successor_capture"
    try:
        _write_raw_execution_capture(
            policy=policy,
            execution=execution,
            execution_sha256=execution_sha256,
            source_capture_ref=r12_raw_ref,
            source_capture_sha256=r12_raw_sha256,
            source_capture_result_digest=str(
                r12_raw.get("result_digest") or ""
            ),
            recorded_at=recorded_at,
        )
        failure_stage = "persisted_raw_reuse_capture_revalidation"
        execution, execution_sha256 = _validated_r13_raw_reuse_capture(
            capture=_read_json(RAW_EXECUTION_CAPTURE),
            policy=policy,
            r12_private=r12_private,
            r12_raw_capture=r12_raw,
            r12_raw_ref=r12_raw_ref,
            r12_raw_sha256=r12_raw_sha256,
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
                "R13_policy": {
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
        private_result = compile_dell_report_internal_chain_ceiling_r13_result(
            r12_private_result=r12_private,
            r13_policy=policy,
            execution=execution,
            execution_sha256=execution_sha256,
            source_rows=source_rows,
            object_rows=object_rows,
            residual_route_program=values["residual_route_program"],
            recorded_at=recorded_at,
            prepared_from_commit=str(git_receipt["head"]),
            input_bindings=input_bindings,
        )
        private_bytes = base._json_bytes(private_result)  # noqa: SLF001
        private_sha256 = hashlib.sha256(private_bytes).hexdigest()
        failure_stage = "public_projection"
        public_result = (
            build_dell_report_internal_chain_ceiling_r13_public_projection(
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


def preview_from_r12_saved_raw() -> dict[str, Any]:
    """Recompile the immutable R12 raw-reuse capture without calls or writes."""

    r12_private_path = ROOT / (
        "data/workbench_private/"
        "fin_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling/"
        "dell-rsq-03b-internal-chain-r12/full_result.json"
    )
    r12_raw_path = r12_private_path.with_name("raw_execution_capture.json")
    if not r12_private_path.is_file() or not r12_raw_path.is_file():
        raise FileNotFoundError("dell_03B_R13_R12_saved_raw_predecessor_missing")
    r12_private = _read_json(r12_private_path)
    r12_raw = _read_json(r12_raw_path)
    residual_route_program = _read_json(
        ROOT
        / "configs/retrieval/fin_ia_0_1_3_s1_dell_report_"
        "residual_source_ladder_program_v1_1.json"
    )
    route_registry = build_route_contract_identity_registry_r13(
        residual_route_program
    )
    bindings = dict(r12_private.get("input_bindings") or {})
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
        raise ValueError("dell_03B_R13_preview_source_or_object_sha_drift")
    source_rows = base._read_jsonl(source_path)  # noqa: SLF001
    object_rows = base._read_jsonl(object_path)  # noqa: SLF001
    execution, execution_sha256 = _validated_immutable_r12_execution(
        r12_private=r12_private,
        r12_raw_capture=r12_raw,
    )
    started_at = datetime.now(timezone.utc)
    compiled = compile_dell_report_internal_chain_ceiling_r13_result(
        r12_private_result=r12_private,
        r13_policy={"result_digest": "0" * 64},
        execution=execution,
        execution_sha256=execution_sha256,
        source_rows=source_rows,
        object_rows=object_rows,
        residual_route_program=residual_route_program,
        recorded_at=started_at.replace(microsecond=0).isoformat(),
        prepared_from_commit=_head(),
        input_bindings={},
    )
    predecessor_targets = {
        str(row.get("target_id") or ""): row
        for row in r12_private.get("target_results") or ()
    }
    package_stages = {
        "source": "private_source_packages",
        "compiled": "private_compiled_packages",
        "union": "private_union_packages",
        "final": "private_final_packages",
    }

    def complete_family_ids(target: Mapping[str, Any]) -> dict[str, list[str]]:
        return {
            stage: sorted(
                {
                    str(package.get("canonical_source_family_id") or "")
                    for package in target.get(field) or ()
                    if package.get("classification")
                    == "complete_bounded_target_package"
                }
            )
            for stage, field in package_stages.items()
        }

    def transformation_snapshot(target: Mapping[str, Any]) -> dict[str, Any]:
        summary = dict(target.get("private_frame_transformation_summary") or {})
        keys = (
            "summary_population_scope",
            "source_package_count",
            "source_package_set_digest",
            "compiled_package_count",
            "compiled_package_set_digest",
            "coverage_gap_count",
            "coverage_gap_set_digest",
            "binding_count",
            "accepted_binding_count",
            "failed_binding_count",
            "failed_complete_binding_count",
            "unbound_complete_source_family_count",
            "compiled_complete_without_source_antecedent_count",
            "unbound_partial_source_family_count",
            "proof_rebind_failure_count",
            "source_governing_nominal_head_partial_count",
            "compiled_governing_nominal_head_partial_count",
            "source_clause_ownership_decision_counts",
            "compiled_clause_ownership_decision_counts",
            "complete_transformation_coverage_pass",
            "complete_transformation_coverage_non_vacuous",
            "binding_set_digest",
            "reconciliation_digest",
        )
        return {key: summary.get(key) for key in keys}

    def downstream_snapshot(target: Mapping[str, Any]) -> dict[str, Any]:
        disposition = dict(target.get("downstream_disposition") or {})
        keys = (
            "03C_external_route_required_for_complete_bounded_target",
            "03C_residual_route_requires_prior_capture_crosswalk",
            "03C_scope_if_authorized",
            "03C_residual_scope_if_authorized",
            "03D_4B_embedding_recall_challenger_eligible",
            "03D_same_pool_reranker_challenger_eligible",
            "local_source_to_object_repair_required",
            "remaining_non_03C_research_boundaries",
        )
        return {key: disposition.get(key) for key in keys}

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
        before_families = complete_family_ids(predecessor)
        after_families = complete_family_ids(row)
        complete_family_delta = {
            stage: {
                "added": sorted(set(after_families[stage]) - set(before_families[stage])),
                "removed": sorted(set(before_families[stage]) - set(after_families[stage])),
            }
            for stage in package_stages
        }
        complete_family_population_equal = all(
            not delta["added"] and not delta["removed"]
            for delta in complete_family_delta.values()
        )
        before_rank = before["best_complete_package_final_completion_rank"]
        after_rank = after["best_complete_package_final_completion_rank"]
        before_transform = transformation_snapshot(predecessor)
        after_transform = transformation_snapshot(row)
        transformation_binding_population_equal = all(
            before_transform[key] == after_transform[key]
            for key in (
                "binding_count",
                "accepted_binding_count",
                "failed_binding_count",
                "failed_complete_binding_count",
            )
        )
        before_unbound_partial = set(
            predecessor["private_frame_transformation_summary"].get(
                "unbound_source_family_ids"
            )
            or ()
        )
        after_unbound_partial = set(
            row["private_frame_transformation_summary"].get(
                "unbound_source_family_ids"
            )
            or ()
        )
        partial_family_delta = {
            "added": sorted(after_unbound_partial - before_unbound_partial),
            "removed": sorted(before_unbound_partial - after_unbound_partial),
        }
        before_downstream = downstream_snapshot(predecessor)
        after_downstream = downstream_snapshot(row)
        before_route_ids = list(
            predecessor["downstream_disposition"].get(
                "mandatory_external_route_contract_ids_if_authorized"
            )
            or ()
        )
        after_route_ids = list(
            row["downstream_disposition"].get(
                "mandatory_external_route_contract_ids_if_authorized"
            )
            or ()
        )
        external_required = after_downstream[
            "03C_external_route_required_for_complete_bounded_target"
        ] is True
        expected_route_ids = (
            route_registry[row["target_id"]][
                "mandatory_external_route_contract_ids"
            ]
            if external_required
            else []
        )
        route_id_delta = {
            "added": sorted(set(after_route_ids) - set(before_route_ids)),
            "removed": sorted(set(before_route_ids) - set(after_route_ids)),
        }
        route_identity_digest = row["private_route_contract_identity"][
            "route_identity_digest"
        ]
        route_id_set_digest = canonical_digest(sorted(after_route_ids))
        diagnostic_keys = (
            "proof_rebind_failure_count",
            "source_governing_nominal_head_partial_count",
            "compiled_governing_nominal_head_partial_count",
            "source_clause_ownership_decision_counts",
            "compiled_clause_ownership_decision_counts",
        )
        invariants = {
            "complete_counts_equal": before_counts == after_counts,
            "complete_family_population_equal": complete_family_population_equal,
            "best_final_rank_equal": before_rank == after_rank,
            "complete_transformation_coverage_pass": after_transform[
                "complete_transformation_coverage_pass"
            ]
            is True,
            "failed_complete_binding_count_zero": after_transform[
                "failed_complete_binding_count"
            ]
            == 0,
            "unbound_complete_source_family_count_zero": after_transform[
                "unbound_complete_source_family_count"
            ]
            == 0,
            "compiled_complete_without_source_antecedent_count_zero": (
                after_transform[
                    "compiled_complete_without_source_antecedent_count"
                ]
                == 0
            ),
            "proof_rebind_failure_count_zero": after_transform[
                "proof_rebind_failure_count"
            ]
            == 0,
            "R13_structural_diagnostics_materialized": all(
                after_transform[key] is not None for key in diagnostic_keys
            ),
            "R13_authoritative_persisted_reconciliation_materialized": (
                after_transform["summary_population_scope"]
                == (
                    "persisted_target_semantic_source_and_compiled_packages_"
                    "plus_coverage_gaps_and_validated_transformation_bindings"
                )
                and all(
                    after_transform[key] is not None
                    for key in (
                        "source_package_count",
                        "source_package_set_digest",
                        "compiled_package_count",
                        "compiled_package_set_digest",
                        "coverage_gap_count",
                        "coverage_gap_set_digest",
                        "reconciliation_digest",
                    )
                )
            ),
            "non_route_downstream_disposition_equal": (
                before_downstream == after_downstream
            ),
            "route_identity_matches_frozen_03A_R2_program": (
                after_route_ids == expected_route_ids
            ),
            "route_identity_digest_matches_frozen_registry": (
                route_identity_digest
                == route_registry[row["target_id"]]["route_identity_digest"]
            ),
        }
        if partial_family_delta == {"added": [], "removed": []}:
            partial_delta_explanation = "no_partial_family_delta"
        else:
            partial_delta_explanation = (
                "R13_proof_schema_reclassifies_partial_only_transformation_"
                "diagnostics;_exact_family_delta_recorded_and_complete_"
                "families_coverage_rank_and_downstream_disposition_unchanged"
            )
        targets.append(
            {
                "target_id": row["target_id"],
                "R12_source_compiled_union_final": before_counts,
                "R13_source_compiled_union_final": after_counts,
                "complete_family_delta": complete_family_delta,
                "R12_best_final_rank": before_rank,
                "R13_best_final_rank": after_rank,
                "R12_partial_source_compiled": [
                    before["partial_context_in_source_record_corpus_count"],
                    before["partial_context_in_compiled_package_corpus_count"],
                ],
                "R13_partial_source_compiled": [
                    after["partial_context_in_source_record_corpus_count"],
                    after["partial_context_in_compiled_package_corpus_count"],
                ],
                "partial_unbound_family_delta": partial_family_delta,
                "partial_delta_explanation": partial_delta_explanation,
                "transformation_binding_population_equal": (
                    transformation_binding_population_equal
                ),
                "reconciliation_delta_explanation": (
                    "R13_intentionally_replaces_R12_mixed_full_corpus_"
                    "diagnostics_with_one_exactly_recomputable_persisted_"
                    "target_filtered_population;_digest_and_clause_count_"
                    "changes_are_expected_and_public_projection_rederives_"
                    "the_whole_summary_before_private_rows_are_discarded"
                ),
                "R12_transformation": before_transform,
                "R13_transformation": after_transform,
                "R12_downstream": before_downstream,
                "R13_downstream": after_downstream,
                "R12_active_mandatory_external_route_ids": before_route_ids,
                "R13_active_mandatory_external_route_ids": after_route_ids,
                "expected_03A_R2_mandatory_external_route_ids": (
                    expected_route_ids
                ),
                "R13_route_identity_digest": route_identity_digest,
                "R13_active_route_id_set_digest": route_id_set_digest,
                "route_id_delta": route_id_delta,
                "route_delta_explanation": (
                    "R13_restores_constant_frozen_03A_R2_route_identity_"
                    "independent_of_predecessor_active_state"
                    if route_id_delta != {"added": [], "removed": []}
                    else "no_route_identity_delta"
                ),
                "earliest_observed_limitation": after[
                    "earliest_observed_limitation"
                ],
                "invariants": invariants,
            }
        )
    if any(
        not all(row["invariants"].values())
        for row in targets
    ):
        raise ValueError("dell_03B_R13_preview_unexplained_material_delta")
    return {
        "mode": "preview_from_immutable_R12_saved_raw_zero_call",
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
    """Recompile captured R13 raw bytes and prove canonical private equality."""

    if not all(
        path.is_file()
        for path in (
            POLICY,
            DEFAULT_PRIVATE,
            DEFAULT_PUBLIC,
            RAW_EXECUTION_CAPTURE,
        )
    ):
        raise FileNotFoundError("dell_03B_R13_formal_replay_inputs_missing")
    policy = _read_json(POLICY)
    private = _read_json(DEFAULT_PRIVATE)
    raw = _read_json(RAW_EXECUTION_CAPTURE)
    bound = {
        name: _bound_value(policy, name)
        for name in sorted(EXPECTED_BOUND_INPUT_IDS)
    }
    values = {name: pair[1] for name, pair in bound.items()}
    r12_private = validate_dell_report_internal_chain_ceiling_r13_policy(
        policy,
        **values,
    )
    _, _, object_rows, source_rows = _runtime_rows(values)
    r12_raw_path, r12_raw = bound["R12_raw_execution_capture"]
    execution, execution_sha256 = _validated_r13_raw_reuse_capture(
        capture=raw,
        policy=policy,
        r12_private=r12_private,
        r12_raw_capture=r12_raw,
        r12_raw_ref=base._relative(r12_raw_path),  # noqa: SLF001
        r12_raw_sha256=base._sha256(r12_raw_path),  # noqa: SLF001
    )
    replay = compile_dell_report_internal_chain_ceiling_r13_result(
        r12_private_result=r12_private,
        r13_policy=policy,
        execution=execution,
        execution_sha256=execution_sha256,
        source_rows=source_rows,
        object_rows=object_rows,
        residual_route_program=values["residual_route_program"],
        recorded_at=str(private.get("recorded_at") or ""),
        prepared_from_commit=str(private.get("prepared_from_commit") or ""),
        input_bindings=dict(private.get("input_bindings") or {}),
    )
    equal = replay == private and base._json_bytes(replay) == base._json_bytes(  # noqa: SLF001
        private
    )
    if not equal:
        raise ValueError("dell_03B_R13_exact_private_replay_mismatch")
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
        result = preview_from_r12_saved_raw()
    elif args.mode == "replay":
        result = replay_saved_formal()
    else:
        result = run_authorized_formal()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
