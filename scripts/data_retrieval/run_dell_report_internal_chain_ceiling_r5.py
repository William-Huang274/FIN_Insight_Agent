from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path[:0] = [str(ROOT), str(SRC)]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")

from apps.workbench.backend.application.research_retrieval_service import (  # noqa: E402
    ResearchRetrievalPrincipal,
    ResearchRetrievalService,
)
from retrieval.dell_report_internal_chain_ceiling import (  # noqa: E402
    validate_dell_report_source_compiled_identity_population,
)
from retrieval.dell_report_internal_chain_ceiling_r5 import (  # noqa: E402
    ATTEMPT_ID,
    ATTEMPT_RECEIPT_REF,
    BRANCH,
    MIN_FREE_BYTES_BEFORE_ATTEMPT,
    POLICY_REF,
    POLICY_SCHEMA_VERSION,
    PRIVATE_REF,
    PUBLIC_REF,
    build_dell_report_internal_chain_ceiling_r5_public_projection,
    compile_dell_report_internal_chain_ceiling_r5_result,
    validate_dell_report_internal_chain_ceiling_r5_policy,
)
from retrieval.query_plan import canonical_digest  # noqa: E402
from scripts.data_retrieval import (  # noqa: E402
    run_dell_report_internal_chain_ceiling_r4 as base,
)


POLICY = ROOT / POLICY_REF
DEFAULT_PRIVATE = ROOT / PRIVATE_REF
DEFAULT_PUBLIC = ROOT / PUBLIC_REF
ATTEMPT_RECEIPT = ROOT / ATTEMPT_RECEIPT_REF


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"dell_03B_R5_json_not_mapping:{path.name}")
    return value


def _bound_json(
    policy: Mapping[str, Any], binding_id: str
) -> tuple[Path, dict[str, Any]]:
    row = dict((policy.get("bound_inputs") or {}).get(binding_id) or {})
    path = base._resolve(str(row.get("ref") or ""))  # noqa: SLF001
    if not path.is_file():
        raise ValueError(f"dell_03B_R5_bound_input_missing:{binding_id}")
    if base._sha256(path) != str(row.get("sha256") or ""):  # noqa: SLF001
        raise ValueError(f"dell_03B_R5_bound_input_sha_drift:{binding_id}")
    return path, _read_json(path)


def _require_clean() -> None:
    if base._git("status", "--porcelain", "--untracked-files=all"):  # noqa: SLF001
        raise RuntimeError("dell_03B_R5_clean_worktree_required")


def _clean_exact_git_receipt(policy: Mapping[str, Any]) -> dict[str, Any]:
    identity = dict(policy.get("execution_identity") or {})
    status = base._git(  # noqa: SLF001
        "status", "--porcelain", "--untracked-files=all"
    )
    branch = base._git("rev-parse", "--abbrev-ref", "HEAD")  # noqa: SLF001
    head = base._git("rev-parse", "HEAD").lower()  # noqa: SLF001
    upstream = base._git("rev-parse", "@{upstream}").lower()  # noqa: SLF001
    parents = base._git(  # noqa: SLF001
        "show", "-s", "--format=%P", "HEAD"
    ).lower().split()
    implementation_commit = str(
        identity.get("implementation_commit") or ""
    ).lower()
    implementation_tree = str(identity.get("implementation_tree") or "").lower()
    actual_implementation_tree = base._git(  # noqa: SLF001
        "show", "-s", "--format=%T", implementation_commit
    ).lower()
    changed_paths = sorted(
        line.replace("\\", "/")
        for line in base._git(  # noqa: SLF001
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
        raise RuntimeError("dell_03B_R5_exact_clean_synced_git_identity_required")
    return {
        "branch": branch,
        "head": head,
        "head_tree": base._git(  # noqa: SLF001
            "show", "-s", "--format=%T", "HEAD"
        ).lower(),
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
        raise ValueError("dell_03B_R5_implementation_bindings_invalid")
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("dell_03B_R5_implementation_bindings_invalid")
        ref = str(row.get("path") or "")
        if ref in seen:
            raise ValueError("dell_03B_R5_implementation_binding_duplicate")
        seen.add(ref)
        path = base._resolve(ref)  # noqa: SLF001
        if not path.is_file() or base._sha256(path) != str(  # noqa: SLF001
            row.get("sha256") or ""
        ):
            raise ValueError(f"dell_03B_R5_implementation_binding_drift:{ref}")


def _validate_canonical_output_paths() -> None:
    private_resolved = DEFAULT_PRIVATE.resolve()
    public_resolved = DEFAULT_PUBLIC.resolve()
    receipt_resolved = ATTEMPT_RECEIPT.resolve()
    if private_resolved == public_resolved or len(
        {private_resolved, public_resolved, receipt_resolved}
    ) != 3:
        raise ValueError("dell_03B_R5_output_paths_must_be_distinct")
    if private_resolved.parent != receipt_resolved.parent:
        raise ValueError("dell_03B_R5_attempt_receipt_private_parent_mismatch")


def _require_output_disk_capacity() -> dict[str, int]:
    usage = shutil.disk_usage(ROOT)
    if usage.free < MIN_FREE_BYTES_BEFORE_ATTEMPT:
        raise RuntimeError("dell_03B_R5_minimum_free_disk_capacity_required")
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
        raise FileExistsError("dell_03B_R5_attempt_already_consumed")
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


def _publish_atomic_pair(*, private_bytes: bytes, public_bytes: bytes) -> None:
    if DEFAULT_PRIVATE.exists() or DEFAULT_PUBLIC.exists():
        raise FileExistsError("dell_03B_R5_output_collision")
    DEFAULT_PRIVATE.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_PUBLIC.parent.mkdir(parents=True, exist_ok=True)
    private_tmp = DEFAULT_PRIVATE.with_name(
        f".{DEFAULT_PRIVATE.name}.{ATTEMPT_ID}.tmp"
    )
    public_tmp = DEFAULT_PUBLIC.with_name(
        f".{DEFAULT_PUBLIC.name}.{ATTEMPT_ID}.tmp"
    )
    if private_tmp.exists() or public_tmp.exists():
        raise FileExistsError("dell_03B_R5_temporary_output_collision")
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


def run() -> dict[str, Any]:
    _validate_canonical_output_paths()
    disk_receipt = _require_output_disk_capacity()
    if not POLICY.is_file():
        raise FileNotFoundError("dell_03B_R5_canonical_policy_missing")
    policy = _read_json(POLICY)
    if policy.get("schema_version") != POLICY_SCHEMA_VERSION:
        raise ValueError("dell_03B_R5_policy_schema_invalid")
    git_receipt = _clean_exact_git_receipt(policy)
    _validate_implementation_bindings(policy)
    if (
        DEFAULT_PRIVATE.exists()
        or DEFAULT_PUBLIC.exists()
        or ATTEMPT_RECEIPT.parent.exists()
    ):
        raise FileExistsError("dell_03B_R5_attempt_or_output_exists")

    names = (
        "R1_policy",
        "R3_policy",
        "R3_public",
        "R3_private",
        "R3_fresh_audit",
        "R4_policy",
        "R4_public",
        "R4_private",
        "R4_fresh_audit",
        "R4_audit_correction",
        "R39_repair_result",
        "R39_embedding_result",
        "R39_route_policy",
        "R39_hybrid_policy",
        "runtime_registry",
        "runtime_binding_receipt",
        "residual_program",
        "execution_program",
        "dell_product_readiness",
    )
    bound = {name: _bound_json(policy, name) for name in names}
    values = {name: pair[1] for name, pair in bound.items()}
    legacy_policy = validate_dell_report_internal_chain_ceiling_r5_policy(
        policy,
        r1_policy=values["R1_policy"],
        r3_policy=values["R3_policy"],
        r3_public=values["R3_public"],
        r3_private=values["R3_private"],
        r3_fresh_audit=values["R3_fresh_audit"],
        r4_policy=values["R4_policy"],
        r4_public=values["R4_public"],
        r4_private=values["R4_private"],
        r4_fresh_audit=values["R4_fresh_audit"],
        r4_audit_correction=values["R4_audit_correction"],
        r39_repair_result=values["R39_repair_result"],
        r39_embedding_result=values["R39_embedding_result"],
        r39_route_policy=values["R39_route_policy"],
        r39_hybrid_policy=values["R39_hybrid_policy"],
        runtime_registry=values["runtime_registry"],
        runtime_binding_receipt=values["runtime_binding_receipt"],
        residual_program=values["residual_program"],
        execution_program=values["execution_program"],
        dell_product_readiness=values["dell_product_readiness"],
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
        raise ValueError("dell_03B_R5_request_payload_population_invalid")
    blueprints = base._material_blueprints(  # noqa: SLF001
        execution_program,
        request_ids=request_ids,
    )
    runtime_binding = values["runtime_binding_receipt"]
    bindings = runtime_binding.get("bindings") or {}
    objects_path = base._resolve(  # noqa: SLF001
        str(bindings.get("compiled_objects", {}).get("ref") or "")
    )
    sources_path = base._resolve(  # noqa: SLF001
        str(bindings.get("source_records", {}).get("ref") or "")
    )
    if base._sha256(objects_path) != str(  # noqa: SLF001
        bindings.get("compiled_objects", {}).get("sha256") or ""
    ):
        raise ValueError("dell_03B_R5_compiled_object_sha_drift")
    if base._sha256(sources_path) != str(  # noqa: SLF001
        bindings.get("source_records", {}).get("sha256") or ""
    ):
        raise ValueError("dell_03B_R5_source_record_sha_drift")
    object_rows = base._read_jsonl(objects_path)  # noqa: SLF001
    source_rows = base._read_jsonl(sources_path)  # noqa: SLF001
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
    service = ResearchRetrievalService.from_runtime_paths(ROOT)
    principal = ResearchRetrievalPrincipal(
        mode="current", permissions=frozenset({"current_product:read"})
    )
    execution = service.execute_current_runtime_requests(
        "DELL",
        request_payloads,
        principal,
        material_requirement_blueprints=blueprints,
    )
    execution_sha256 = hashlib.sha256(
        base._canonical_json_bytes(execution)  # noqa: SLF001
    ).hexdigest()
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
            "R5_policy": {
                "ref": POLICY_REF,
                "sha256": base._sha256(POLICY),  # noqa: SLF001
                "result_digest": policy.get("result_digest"),
            },
            "compiled_objects": {
                "ref": base._relative(objects_path),  # noqa: SLF001
                "sha256": base._sha256(objects_path),  # noqa: SLF001
            },
            "source_records": {
                "ref": base._relative(sources_path),  # noqa: SLF001
                "sha256": base._sha256(sources_path),  # noqa: SLF001
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
    private_result = compile_dell_report_internal_chain_ceiling_r5_result(
        legacy_policy=legacy_policy,
        r5_policy=policy,
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
    public_result = build_dell_report_internal_chain_ceiling_r5_public_projection(
        private_result=private_result,
        private_ref=PRIVATE_REF,
        private_sha256=private_sha256,
    )
    public_bytes = base._json_bytes(public_result)  # noqa: SLF001
    _require_clean()
    _publish_atomic_pair(
        private_bytes=private_bytes,
        public_bytes=public_bytes,
    )
    return public_result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the exact-once canonical DELL 03B R5 raw-position, typed-anchor "
            "and semantic coverage audit."
        )
    )
    parser.parse_args(argv)
    result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
