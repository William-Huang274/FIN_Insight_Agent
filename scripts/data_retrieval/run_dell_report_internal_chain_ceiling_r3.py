from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
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
from retrieval.dell_report_internal_chain_ceiling_r3 import (  # noqa: E402
    ATTEMPT_ID,
    ATTEMPT_RECEIPT_REF,
    BRANCH,
    POLICY_REF,
    POLICY_SCHEMA_VERSION,
    PRIVATE_REF,
    PUBLIC_REF,
    build_dell_report_internal_chain_ceiling_r3_public_projection,
    compile_dell_report_internal_chain_ceiling_r3_result,
    validate_dell_report_internal_chain_ceiling_r3_policy,
)
from retrieval.query_plan import canonical_digest  # noqa: E402


POLICY = ROOT / POLICY_REF
DEFAULT_PRIVATE = ROOT / PRIVATE_REF
DEFAULT_PUBLIC = ROOT / PUBLIC_REF
ATTEMPT_RECEIPT = ROOT / ATTEMPT_RECEIPT_REF


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"dell_03B_R3_json_not_mapping:{path.name}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(
                    f"dell_03B_R3_jsonl_row_not_mapping:{path.name}:{line_number}"
                )
            rows.append(value)
    return rows


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _json_bytes(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _resolve(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


def _require_clean() -> None:
    if _git("status", "--porcelain", "--untracked-files=all"):
        raise RuntimeError("dell_03B_R3_clean_worktree_required")


def _clean_exact_git_receipt(policy: Mapping[str, Any]) -> dict[str, Any]:
    identity = policy.get("execution_identity") or {}
    status = _git("status", "--porcelain", "--untracked-files=all")
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    head = _git("rev-parse", "HEAD").lower()
    upstream = _git("rev-parse", "@{upstream}").lower()
    parents = _git("show", "-s", "--format=%P", "HEAD").lower().split()
    implementation_commit = str(identity.get("implementation_commit") or "").lower()
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
    expected_changed_paths = sorted(identity.get("authority_commit_changed_paths") or ())
    if (
        status
        or branch != BRANCH
        or branch != identity.get("branch")
        or head != upstream
        or parents != [implementation_commit]
        or actual_implementation_tree != implementation_tree
        or changed_paths != expected_changed_paths
    ):
        raise RuntimeError("dell_03B_R3_exact_clean_synced_git_identity_required")
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


def _bound_json(
    owner: Mapping[str, Any], *, ref_field: str, sha_field: str
) -> tuple[Path, dict[str, Any]]:
    path = _resolve(str(owner.get(ref_field) or ""))
    if not path.is_file():
        raise ValueError(f"dell_03B_R3_bound_input_missing:{ref_field}")
    if _sha256(path) != str(owner.get(sha_field) or ""):
        raise ValueError(f"dell_03B_R3_bound_input_sha_drift:{ref_field}")
    return path, _read_json(path)


def _legacy_bound_json(
    r1_policy: Mapping[str, Any], *, ref_field: str, sha_field: str
) -> tuple[Path, dict[str, Any]]:
    return _bound_json(
        r1_policy.get("bound_inputs") or {},
        ref_field=ref_field,
        sha_field=sha_field,
    )


def _validate_implementation_bindings(policy: Mapping[str, Any]) -> None:
    rows = policy.get("implementation_bindings")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        raise ValueError("dell_03B_R3_implementation_bindings_invalid")
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("dell_03B_R3_implementation_bindings_invalid")
        ref = str(row.get("path") or "")
        if ref in seen:
            raise ValueError("dell_03B_R3_implementation_binding_duplicate")
        seen.add(ref)
        path = _resolve(ref)
        if not path.is_file() or _sha256(path) != str(row.get("sha256") or ""):
            raise ValueError(f"dell_03B_R3_implementation_binding_drift:{ref}")


def _source_record_ids(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for row_number, row in enumerate(rows, start=1):
        if "source_record_id" in row:
            raise ValueError(
                f"dell_03B_R3_source_record_id_alias_forbidden:{row_number}"
            )
        source_id = row.get("evidence_id")
        if (
            not isinstance(source_id, str)
            or not source_id.strip()
            or source_id != source_id.strip()
        ):
            raise ValueError(f"dell_03B_R3_source_evidence_id_missing:{row_number}")
        if source_id in seen:
            raise ValueError(f"dell_03B_R3_source_evidence_id_duplicate:{source_id}")
        seen.add(source_id)
        result.append(source_id)
    return result


def _validate_canonical_output_paths(
    private_output: Path, public_output: Path, attempt_receipt: Path
) -> None:
    private_resolved = private_output.resolve()
    public_resolved = public_output.resolve()
    receipt_resolved = attempt_receipt.resolve()
    if private_resolved != DEFAULT_PRIVATE.resolve():
        raise ValueError("dell_03B_R3_canonical_private_output_required")
    if public_resolved != DEFAULT_PUBLIC.resolve():
        raise ValueError("dell_03B_R3_canonical_public_output_required")
    if receipt_resolved != ATTEMPT_RECEIPT.resolve():
        raise ValueError("dell_03B_R3_canonical_attempt_receipt_required")
    if len({private_resolved, public_resolved, receipt_resolved}) != 3:
        raise ValueError("dell_03B_R3_output_paths_must_be_distinct")
    if private_resolved.parent != receipt_resolved.parent:
        raise ValueError("dell_03B_R3_attempt_receipt_private_parent_mismatch")


def _write_attempt_consumption_receipt(
    *, path: Path, policy: Mapping[str, Any], git_receipt: Mapping[str, Any], recorded_at: str
) -> dict[str, Any]:
    if path.exists() or path.parent.exists():
        raise FileExistsError("dell_03B_R3_attempt_already_consumed")
    body = {
        "schema_version": "fin_ia_dell_report_internal_chain_attempt_consumption_v1_0",
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
    path.parent.mkdir(parents=True, exist_ok=False)
    with path.open("xb") as handle:
        handle.write(_json_bytes(receipt))
        handle.flush()
        os.fsync(handle.fileno())
    return receipt


def _publish_atomic_pair(
    *, private_output: Path, private_bytes: bytes, public_output: Path, public_bytes: bytes
) -> None:
    if private_output.resolve() == public_output.resolve():
        raise ValueError("dell_03B_R3_output_paths_must_be_distinct")
    if private_output.exists() or public_output.exists():
        raise FileExistsError("dell_03B_R3_output_collision")
    private_output.parent.mkdir(parents=True, exist_ok=True)
    public_output.parent.mkdir(parents=True, exist_ok=True)
    private_tmp = private_output.with_name(f".{private_output.name}.{ATTEMPT_ID}.tmp")
    public_tmp = public_output.with_name(f".{public_output.name}.{ATTEMPT_ID}.tmp")
    if private_tmp.exists() or public_tmp.exists():
        raise FileExistsError("dell_03B_R3_temporary_output_collision")
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
        os.link(private_tmp, private_output)
        created_finals.append(private_output)
        os.link(public_tmp, public_output)
        created_finals.append(public_output)
    except BaseException:
        for path in reversed(created_finals):
            if path.exists():
                path.unlink()
        raise
    finally:
        for path in (private_tmp, public_tmp):
            if path.exists():
                path.unlink()


def _material_blueprints(
    program: Mapping[str, Any], *, request_ids: set[str]
) -> dict[str, dict[str, Any]]:
    contract = program.get("material_scope_blueprint")
    if not isinstance(contract, Mapping) or contract.get("mode") != (
        "explicit_all_visible_product_intents_hard_material_axes"
    ):
        raise ValueError("dell_03B_R3_material_scope_blueprint_missing")
    roles_by_request = contract.get("required_roles_by_request")
    if not isinstance(roles_by_request, Mapping):
        raise ValueError("dell_03B_R3_material_scope_roles_missing")
    metric_binding_roles = {
        str(value) for value in contract.get("metric_binding_roles") or ()
    }
    requests = {
        str(row.get("request_id") or ""): dict(row)
        for row in program.get("evidence_requests") or ()
        if isinstance(row, Mapping)
    }
    if not request_ids.issubset(requests) or not request_ids.issubset(roles_by_request):
        raise ValueError("dell_03B_R3_material_scope_request_set_invalid")
    result: dict[str, dict[str, Any]] = {}
    for request_id in sorted(request_ids):
        request = requests[request_id]
        facets = [str(value) for value in request.get("requested_facet_ids") or ()]
        products = [str(value) for value in request.get("product_intents") or ()]
        metrics = [str(value) for value in request.get("metric_intents") or ()]
        entities = [str(value) for value in request.get("target_entities") or ()]
        roles = [str(value) for value in roles_by_request.get(request_id) or ()]
        if len(facets) != 1 or not products or not entities or not roles:
            raise ValueError(f"dell_03B_R3_material_scope_invalid:{request_id}")
        result[request_id] = {
            "material_requirements": [
                {
                    "facet_id": facets[0],
                    "role": role,
                    "metric_ids": metrics if role in metric_binding_roles else [],
                    "product_ids": products,
                    "target_entities": entities,
                    "period_mode": "any",
                    "fiscal_years": [],
                    "minimum_candidates": 1,
                    "coverage_mode": "collective_axes",
                    "metric_coverage_mode": "retrieval_context_only",
                    "product_coverage_mode": "all_of",
                }
                for role in roles
            ]
        }
    return result


def run() -> dict[str, Any]:
    _validate_canonical_output_paths(DEFAULT_PRIVATE, DEFAULT_PUBLIC, ATTEMPT_RECEIPT)
    if not POLICY.is_file():
        raise FileNotFoundError("dell_03B_R3_canonical_policy_missing")
    policy = _read_json(POLICY)
    if policy.get("schema_version") != POLICY_SCHEMA_VERSION:
        raise ValueError("dell_03B_R3_policy_schema_invalid")
    git_receipt = _clean_exact_git_receipt(policy)
    _validate_implementation_bindings(policy)
    if DEFAULT_PRIVATE.exists() or DEFAULT_PUBLIC.exists() or ATTEMPT_RECEIPT.parent.exists():
        raise FileExistsError("dell_03B_R3_attempt_or_output_exists")

    predecessor = policy.get("predecessor") or {}
    r1_policy_path, r1_policy = _bound_json(
        predecessor, ref_field="R1_policy_ref", sha_field="R1_policy_sha256"
    )
    r1_failure_path, r1_failure = _bound_json(
        predecessor, ref_field="R1_failure_ref", sha_field="R1_failure_sha256"
    )
    r2_policy_path, r2_policy = _bound_json(
        predecessor, ref_field="R2_policy_ref", sha_field="R2_policy_sha256"
    )
    r2_public_path, r2_public = _bound_json(
        predecessor, ref_field="R2_public_ref", sha_field="R2_public_sha256"
    )
    r2_private_path, r2_private = _bound_json(
        predecessor, ref_field="R2_private_ref", sha_field="R2_private_sha256"
    )
    r2_audit_path, r2_audit = _bound_json(
        predecessor, ref_field="R2_audit_ref", sha_field="R2_audit_sha256"
    )
    residual_path, residual = _legacy_bound_json(
        r1_policy,
        ref_field="residual_program_ref",
        sha_field="residual_program_sha256",
    )
    execution_program_path, execution_program = _legacy_bound_json(
        r1_policy,
        ref_field="execution_program_ref",
        sha_field="execution_program_sha256",
    )
    registry_path, runtime_registry = _legacy_bound_json(
        r1_policy,
        ref_field="runtime_registry_ref",
        sha_field="runtime_registry_sha256",
    )
    binding_path, runtime_binding = _legacy_bound_json(
        r1_policy,
        ref_field="runtime_binding_receipt_ref",
        sha_field="runtime_binding_receipt_sha256",
    )
    readiness_path, readiness = _legacy_bound_json(
        r1_policy,
        ref_field="dell_product_readiness_ref",
        sha_field="dell_product_readiness_sha256",
    )
    legacy_policy = validate_dell_report_internal_chain_ceiling_r3_policy(
        policy,
        r2_policy=r2_policy,
        r1_policy=r1_policy,
        r1_failure_receipt=r1_failure,
        r2_public_result=r2_public,
        r2_private_result=r2_private,
        r2_audit=r2_audit,
        residual_program=residual,
        execution_program=execution_program,
        runtime_registry=runtime_registry,
        runtime_binding_receipt=runtime_binding,
    )
    request_ids = {
        str(request_id)
        for contract in legacy_policy["target_contracts"]
        for request_id in contract["request_ids"]
    }
    request_payloads = [
        dict(row)
        for row in execution_program.get("evidence_requests") or ()
        if str(row.get("request_id") or "") in request_ids
    ]
    if len(request_payloads) != 5 or {
        str(row.get("request_id") or "") for row in request_payloads
    } != request_ids:
        raise ValueError("dell_03B_R3_request_payload_population_invalid")
    blueprints = _material_blueprints(execution_program, request_ids=request_ids)

    bindings = runtime_binding.get("bindings") or {}
    object_binding = bindings.get("compiled_objects") or {}
    source_binding = bindings.get("source_records") or {}
    objects_path = _resolve(str(object_binding.get("ref") or ""))
    sources_path = _resolve(str(source_binding.get("ref") or ""))
    if _sha256(objects_path) != str(object_binding.get("sha256") or ""):
        raise ValueError("dell_03B_R3_compiled_object_sha_drift")
    if _sha256(sources_path) != str(source_binding.get("sha256") or ""):
        raise ValueError("dell_03B_R3_source_record_sha_drift")
    object_rows = _read_jsonl(objects_path)
    source_rows = _read_jsonl(sources_path)
    source_ids = _source_record_ids(source_rows)
    validate_dell_report_source_compiled_identity_population(
        object_rows=object_rows,
        source_record_ids=source_ids,
        runtime_binding_receipt=runtime_binding,
    )

    recorded_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    attempt_receipt = _write_attempt_consumption_receipt(
        path=ATTEMPT_RECEIPT,
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
    execution_sha256 = hashlib.sha256(_canonical_json_bytes(execution)).hexdigest()
    input_bindings = {
        "R3_policy": {
            "ref": POLICY_REF,
            "sha256": _sha256(POLICY),
            "result_digest": policy.get("result_digest"),
        },
        "R1_policy": {"ref": _relative(r1_policy_path), "sha256": _sha256(r1_policy_path)},
        "R1_failure": {"ref": _relative(r1_failure_path), "sha256": _sha256(r1_failure_path)},
        "R2_policy": {"ref": _relative(r2_policy_path), "sha256": _sha256(r2_policy_path)},
        "R2_public": {"ref": _relative(r2_public_path), "sha256": _sha256(r2_public_path), "result_digest": r2_public.get("result_digest")},
        "R2_private": {"ref": _relative(r2_private_path), "sha256": _sha256(r2_private_path), "result_digest": r2_private.get("result_digest")},
        "R2_audit": {"ref": _relative(r2_audit_path), "sha256": _sha256(r2_audit_path), "result_digest": r2_audit.get("result_digest")},
        "residual_program": {"ref": _relative(residual_path), "sha256": _sha256(residual_path), "program_digest": residual.get("program_digest")},
        "execution_program": {"ref": _relative(execution_program_path), "sha256": _sha256(execution_program_path), "program_id": execution_program.get("program_id")},
        "runtime_registry": {"ref": _relative(registry_path), "sha256": _sha256(registry_path), "registry_id": runtime_registry.get("registry_id")},
        "runtime_binding_receipt": {"ref": _relative(binding_path), "sha256": _sha256(binding_path), "result_digest": runtime_binding.get("result_digest")},
        "dell_product_readiness": {"ref": _relative(readiness_path), "sha256": _sha256(readiness_path), "result_digest": readiness.get("result_digest")},
        "compiled_objects": {"ref": _relative(objects_path), "sha256": _sha256(objects_path)},
        "source_records": {"ref": _relative(sources_path), "sha256": _sha256(sources_path)},
        "attempt_consumption_receipt": {"ref": ATTEMPT_RECEIPT_REF, "sha256": _sha256(ATTEMPT_RECEIPT), "result_digest": attempt_receipt.get("result_digest")},
        "git_identity": dict(git_receipt),
    }
    private_result = compile_dell_report_internal_chain_ceiling_r3_result(
        legacy_policy=legacy_policy,
        r3_policy=policy,
        residual_program=residual,
        runtime_registry=runtime_registry,
        runtime_binding_receipt=runtime_binding,
        execution=execution,
        execution_sha256=execution_sha256,
        source_rows=source_rows,
        object_rows=object_rows,
        recorded_at=recorded_at,
        prepared_from_commit=str(git_receipt["head"]),
        input_bindings=input_bindings,
    )
    private_bytes = _json_bytes(private_result)
    private_sha256 = hashlib.sha256(private_bytes).hexdigest()
    public_result = build_dell_report_internal_chain_ceiling_r3_public_projection(
        private_result=private_result,
        private_ref=PRIVATE_REF,
        private_sha256=private_sha256,
    )
    public_bytes = _json_bytes(public_result)
    _require_clean()
    _publish_atomic_pair(
        private_output=DEFAULT_PRIVATE,
        private_bytes=private_bytes,
        public_output=DEFAULT_PUBLIC,
        public_bytes=public_bytes,
    )
    return public_result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the exact-once canonical DELL 03B R3 bounded package audit."
    )
    parser.parse_args(argv)
    result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
