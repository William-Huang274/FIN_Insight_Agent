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
    build_dell_report_internal_chain_ceiling_public_projection,
    compile_dell_report_internal_chain_ceiling_result,
    validate_dell_report_internal_chain_ceiling_policy,
)


POLICY = (
    ROOT
    / "configs"
    / "retrieval"
    / "fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_policy_v1_0.json"
)
DEFAULT_PRIVATE_ROOT = (
    ROOT
    / "data"
    / "workbench_private"
    / "fin_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling"
)
DEFAULT_PUBLIC = (
    ROOT
    / "configs"
    / "retrieval"
    / "fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_result_v1_0.json"
)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"dell_03B_json_not_mapping:{path.name}")
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
                    f"dell_03B_jsonl_row_not_mapping:{path.name}:{line_number}"
                )
            rows.append(value)
    return rows


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_bytes(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _write_new_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(value)


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _resolve(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip().lower()


def _require_clean() -> None:
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if status:
        raise RuntimeError("dell_03B_clean_worktree_required")


def _bound_json(
    policy: Mapping[str, Any],
    *,
    ref_field: str,
    sha_field: str,
) -> tuple[Path, dict[str, Any]]:
    bindings = policy.get("bound_inputs") or {}
    path = _resolve(str(bindings.get(ref_field) or ""))
    if not path.is_file():
        raise ValueError(f"dell_03B_bound_input_missing:{ref_field}")
    actual_sha = _sha256(path)
    if actual_sha != str(bindings.get(sha_field) or ""):
        raise ValueError(f"dell_03B_bound_input_sha_drift:{ref_field}")
    return path, _read_json(path)


def _material_blueprints(
    program: Mapping[str, Any],
    *,
    request_ids: set[str],
) -> dict[str, dict[str, Any]]:
    contract = program.get("material_scope_blueprint")
    if not isinstance(contract, Mapping) or contract.get("mode") != (
        "explicit_all_visible_product_intents_hard_material_axes"
    ):
        raise ValueError("dell_03B_material_scope_blueprint_missing")
    roles_by_request = contract.get("required_roles_by_request")
    if not isinstance(roles_by_request, Mapping):
        raise ValueError("dell_03B_material_scope_roles_missing")
    metric_binding_roles = {
        str(value) for value in contract.get("metric_binding_roles") or ()
    }
    requests = {
        str(row.get("request_id") or ""): dict(row)
        for row in program.get("evidence_requests") or ()
        if isinstance(row, Mapping)
    }
    if not request_ids.issubset(requests) or not request_ids.issubset(
        set(roles_by_request)
    ):
        raise ValueError("dell_03B_material_scope_request_set_invalid")
    result: dict[str, dict[str, Any]] = {}
    for request_id in sorted(request_ids):
        request = requests[request_id]
        facets = [str(value) for value in request.get("requested_facet_ids") or ()]
        products = [str(value) for value in request.get("product_intents") or ()]
        metrics = [str(value) for value in request.get("metric_intents") or ()]
        entities = [str(value) for value in request.get("target_entities") or ()]
        roles = [str(value) for value in roles_by_request.get(request_id) or ()]
        if (
            len(facets) != 1
            or not products
            or not entities
            or not roles
            or len(roles) != len(set(roles))
        ):
            raise ValueError(f"dell_03B_material_scope_invalid:{request_id}")
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


def _source_record_ids(rows: Sequence[Mapping[str, Any]]) -> set[str]:
    result = set()
    for row in rows:
        source_id = str(row.get("source_record_id") or "")
        if not source_id:
            raise ValueError("dell_03B_source_record_id_missing")
        if source_id in result:
            raise ValueError(f"dell_03B_source_record_id_duplicate:{source_id}")
        result.add(source_id)
    return result


def run(
    *,
    policy_path: Path = POLICY,
    private_output: Path,
    public_output: Path,
) -> dict[str, Any]:
    _require_clean()
    if private_output.exists():
        raise FileExistsError(f"dell_03B_private_output_exists:{private_output}")
    if public_output.exists():
        raise FileExistsError(f"dell_03B_public_output_exists:{public_output}")
    policy = _read_json(policy_path)
    residual_path, residual_program = _bound_json(
        policy,
        ref_field="residual_program_ref",
        sha_field="residual_program_sha256",
    )
    execution_program_path, execution_program = _bound_json(
        policy,
        ref_field="execution_program_ref",
        sha_field="execution_program_sha256",
    )
    registry_path, runtime_registry = _bound_json(
        policy,
        ref_field="runtime_registry_ref",
        sha_field="runtime_registry_sha256",
    )
    receipt_path, runtime_binding_receipt = _bound_json(
        policy,
        ref_field="runtime_binding_receipt_ref",
        sha_field="runtime_binding_receipt_sha256",
    )
    readiness_path, readiness = _bound_json(
        policy,
        ref_field="dell_product_readiness_ref",
        sha_field="dell_product_readiness_sha256",
    )
    if readiness.get("result_digest") != policy["bound_inputs"][
        "dell_product_readiness_digest"
    ]:
        raise ValueError("dell_03B_readiness_digest_drift")
    validate_dell_report_internal_chain_ceiling_policy(
        policy,
        residual_program=residual_program,
        execution_program=execution_program,
        runtime_registry=runtime_registry,
        runtime_binding_receipt=runtime_binding_receipt,
    )
    request_ids = {
        str(request_id)
        for contract in policy["target_contracts"]
        for request_id in contract["request_ids"]
    }
    request_payloads = [
        dict(row)
        for row in execution_program.get("evidence_requests") or ()
        if str(row.get("request_id") or "") in request_ids
    ]
    if {str(row.get("request_id") or "") for row in request_payloads} != request_ids:
        raise ValueError("dell_03B_request_payload_population_invalid")
    blueprints = _material_blueprints(execution_program, request_ids=request_ids)

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
    bindings = runtime_binding_receipt.get("bindings") or {}
    objects_binding = bindings.get("compiled_objects") or {}
    sources_binding = bindings.get("source_records") or {}
    objects_path = _resolve(str(objects_binding.get("ref") or ""))
    sources_path = _resolve(str(sources_binding.get("ref") or ""))
    if _sha256(objects_path) != str(objects_binding.get("sha256") or ""):
        raise ValueError("dell_03B_compiled_object_sha_drift")
    if _sha256(sources_path) != str(sources_binding.get("sha256") or ""):
        raise ValueError("dell_03B_source_record_sha_drift")
    object_rows = _read_jsonl(objects_path)
    source_rows = _read_jsonl(sources_path)
    recorded_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    prepared_from_commit = _head()
    input_bindings = {
        "policy": {"ref": _relative(policy_path), "sha256": _sha256(policy_path)},
        "residual_program": {
            "ref": _relative(residual_path),
            "sha256": _sha256(residual_path),
            "program_digest": residual_program.get("program_digest"),
        },
        "execution_program": {
            "ref": _relative(execution_program_path),
            "sha256": _sha256(execution_program_path),
            "program_id": execution_program.get("program_id"),
        },
        "runtime_registry": {
            "ref": _relative(registry_path),
            "sha256": _sha256(registry_path),
            "registry_id": runtime_registry.get("registry_id"),
            "resource_canonical_digest": runtime_registry.get(
                "resource_canonical_digest"
            ),
        },
        "runtime_binding_receipt": {
            "ref": _relative(receipt_path),
            "sha256": _sha256(receipt_path),
            "result_digest": runtime_binding_receipt.get("result_digest"),
        },
        "dell_product_readiness": {
            "ref": _relative(readiness_path),
            "sha256": _sha256(readiness_path),
            "result_digest": readiness.get("result_digest"),
        },
        "compiled_objects": {
            "ref": _relative(objects_path),
            "sha256": _sha256(objects_path),
        },
        "source_records": {
            "ref": _relative(sources_path),
            "sha256": _sha256(sources_path),
        },
    }
    private_result = compile_dell_report_internal_chain_ceiling_result(
        policy=policy,
        residual_program=residual_program,
        execution_program=execution_program,
        runtime_registry=runtime_registry,
        runtime_binding_receipt=runtime_binding_receipt,
        execution=execution,
        object_rows=object_rows,
        source_record_ids=_source_record_ids(source_rows),
        recorded_at=recorded_at,
        prepared_from_commit=prepared_from_commit,
        attempt_id=str(policy["attempt_id"]),
        input_bindings=input_bindings,
    )
    private_bytes = _json_bytes(private_result)
    private_sha256 = hashlib.sha256(private_bytes).hexdigest()
    public_result = build_dell_report_internal_chain_ceiling_public_projection(
        private_result=private_result,
        private_ref=_relative(private_output),
        private_sha256=private_sha256,
    )
    public_bytes = _json_bytes(public_result)
    _require_clean()
    _write_new_bytes(private_output, private_bytes)
    _write_new_bytes(public_output, public_bytes)
    return public_result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the one-attempt DELL 03B current internal-chain ceiling audit."
    )
    parser.add_argument("--policy", default=str(POLICY))
    parser.add_argument("--private-output")
    parser.add_argument("--public-output", default=str(DEFAULT_PUBLIC))
    args = parser.parse_args(argv)
    policy_path = _resolve(args.policy)
    policy = _read_json(policy_path)
    private_output = (
        _resolve(args.private_output)
        if args.private_output
        else DEFAULT_PRIVATE_ROOT / str(policy["attempt_id"]) / "full_result.json"
    )
    result = run(
        policy_path=policy_path,
        private_output=private_output,
        public_output=_resolve(args.public_output),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
