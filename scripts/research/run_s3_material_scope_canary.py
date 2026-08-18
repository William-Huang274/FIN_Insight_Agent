from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path[:0] = [str(ROOT), str(SRC)]

from apps.workbench.backend.application.research_retrieval_service import (  # noqa: E402
    ResearchRetrievalPrincipal,
    ResearchRetrievalService,
)
from retrieval.contracts import (  # noqa: E402
    load_evidence_request,
    load_financial_research_kernel,
)
from retrieval.candidate_ceiling_provenance import (  # noqa: E402
    candidate_provenance_scope_mode_valid,
)
from retrieval.query_plan import canonical_digest  # noqa: E402
from sec_agent.research.material_scope import (  # noqa: E402
    compile_research_material_scope_messages,
)
from sec_agent.research.material_scope_canary import (  # noqa: E402
    build_material_scope_canary_input,
    file_sha256,
    load_json,
    run_material_scope_canary,
    write_new_json,
)
from sec_agent.runtime_resource_registry import (  # noqa: E402
    resolve_registered_runtime_resource,
)


DEFAULT_OBJECTIVE = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_minimal_planner_canary_objective_v1_0.json"
)
DEFAULT_PLANNER_ATOMS = (
    "tests/fixtures/research/"
    "fin_ia_0_1_3_s3_dell_planner_r1_atoms_v1_0.json"
)
DEFAULT_R3_SCOPE_PAYLOAD = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_material_scope_payload_v1_2.json"
)
DEFAULT_R3_LIVE_RESULT = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_material_scope_canary_live_result_v1_2.json"
)
DEFAULT_R3_FULL_RESULT = (
    "data/workbench_private/fin_0_1_3_s3_material_scope_canary/"
    "dell-r3/full_result.json"
)
DEFAULT_PRODUCT_REPLAY_PRIVATE_OUTPUT = (
    "data/workbench_private/fin_0_1_3_s1_material_scope_product_replay/"
    "dell-r3-v1/full_result.json"
)
DEFAULT_PRODUCT_REPLAY_PUBLIC_OUTPUT = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_dell_material_scope_product_replay_result_v1_0.json"
)


def _resolve(ref: str) -> Path:
    path = Path(ref)
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip().lower()


def _binding(path: Path) -> dict[str, str]:
    return {"ref": _relative(path), "sha256": file_sha256(path)}


def prepare(*, objective_path: Path, planner_path: Path, output_path: Path) -> dict:
    service = ResearchRetrievalService.from_runtime_paths(ROOT)
    principal = ResearchRetrievalPrincipal(
        mode="current",
        permissions=frozenset({"current_product:read"}),
    )
    projection = service.execute_controlled_plan(
        "DELL",
        load_json(objective_path),
        load_json(planner_path),
        principal,
    )
    material_scope = projection["material_scope"]
    kernel_path = resolve_registered_runtime_resource(
        ROOT, "application.config.current_financial_research_kernel"
    )
    policy_path = resolve_registered_runtime_resource(
        ROOT, "application.config.current_research_material_scope_policy"
    )
    runtime_policy_path = resolve_registered_runtime_resource(
        ROOT, "application.config.current_product_material_evidence_runtime_policy"
    )
    ontology_path = resolve_registered_runtime_resource(
        ROOT, "application.config.current_financial_intent_ontology"
    )
    registry_path = (
        ROOT
        / "configs/runtime/"
        "fin_ia_0_1_3_clean_baseline_runtime_resource_registry_v1_0.json"
    )
    kernel = load_financial_research_kernel(load_json(kernel_path))
    requests = [
        load_evidence_request(row, kernel)
        for row in projection["compiled_plan"]["evidence_requests"]
    ]
    messages = compile_research_material_scope_messages(
        research_plan_digest=projection["compiled_plan"]["plan_digest"],
        requests=requests,
        required_request_ids=material_scope["required_request_ids"],
        policy=load_json(policy_path),
        material_runtime_policy=load_json(runtime_policy_path),
        intent_ontology=load_json(ontology_path),
    )
    source_bindings = {
        "objective": _binding(objective_path),
        "planner_atoms": _binding(planner_path),
        "runtime_registry": _binding(registry_path),
        "kernel": _binding(kernel_path),
        "material_scope_policy": _binding(policy_path),
        "material_runtime_policy": _binding(runtime_policy_path),
        "intent_ontology": _binding(ontology_path),
        "workbench_service": _binding(
            ROOT
            / "apps/workbench/backend/application/research_retrieval_service.py"
        ),
        "hybrid_candidate_runtime": _binding(
            ROOT / "src/retrieval/hybrid_candidate_runtime.py"
        ),
        "material_scope_implementation": _binding(
            ROOT / "src/sec_agent/research/material_scope.py"
        ),
    }
    result = build_material_scope_canary_input(
        case_key="DELL",
        product_projection=projection,
        model_visible_messages=messages,
        source_bindings=source_bindings,
        prepared_from_commit=_head(),
    )
    write_new_json(output_path, result)
    return result


def _cuda_execution_receipt() -> dict[str, Any]:
    import torch

    if not torch.cuda.is_available() or torch.cuda.device_count() < 1:
        raise RuntimeError("material_scope_product_replay_cuda_required")
    return {
        "device": "cuda:0",
        "device_name": torch.cuda.get_device_name(0),
        "torch_version": torch.__version__,
        "embedding_precision": "float16",
        "cpu_vector_fallbacks": 0,
        "embedding_runtime_ref": "src/retrieval/embedding_runtime.py",
        "embedding_runtime_sha256": file_sha256(
            ROOT / "src/retrieval/embedding_runtime.py"
        ),
    }


def _public_product_replay_projection(
    projection: Mapping[str, Any],
) -> dict[str, Any]:
    request_rows: list[dict[str, Any]] = []
    for result in projection.get("request_results") or ():
        request = result.get("request") or {}
        hybrid = result.get("hybrid_object_retrieval") or {}
        hybrid_summary = hybrid.get("summary") or {}
        material = hybrid.get("material_evidence") or {}
        plan = material.get("requirement_plan") or {}
        selection = material.get("selection") or {}
        provenance = result.get("candidate_ceiling_provenance") or {}
        ceiling = provenance.get("hybrid_candidate_ceiling") or {}
        loss_counts: dict[str, int] = {}
        for row in provenance.get("material_requirements") or ():
            loss = str(row.get("observed_loss_stage") or "unknown")
            loss_counts[loss] = loss_counts.get(loss, 0) + 1
        request_rows.append(
            {
                "request_id": request.get("request_id"),
                "facet_ids": list(request.get("requested_facet_ids") or ()),
                "requirement_group_count": len(
                    plan.get("requirement_groups") or ()
                ),
                "maximum_reserved_capacity": plan.get(
                    "maximum_reserved_capacity"
                ),
                "selected_candidate_count": hybrid_summary.get(
                    "selected_count", 0
                ),
                "material_scope_ready": hybrid_summary.get(
                    "material_scope_ready", False
                ),
                "material_set_complete": hybrid_summary.get(
                    "material_set_complete", False
                ),
                "hard_reserved_material_candidate_count": hybrid_summary.get(
                    "material_reserved_candidate_count", 0
                ),
                "material_review_order_candidate_count": hybrid_summary.get(
                    "material_review_order_candidate_count", 0
                ),
                "met_requirement_ids": list(
                    selection.get("met_requirement_ids") or ()
                ),
                "unmet_requirement_ids": list(
                    selection.get("unmet_requirement_ids") or ()
                ),
                "selected_material_candidate_count": len(
                    selection.get("selected_candidate_ids") or ()
                ),
                "candidate_union_count": ceiling.get(
                    "candidate_union_count"
                ),
                "candidate_union_limit": ceiling.get(
                    "candidate_union_limit"
                ),
                "union_ceiling_reached": ceiling.get(
                    "union_ceiling_reached"
                ),
                "first_stage_ceiling_reached": {
                    "bm25": ceiling.get("bm25_first_stage_ceiling_reached"),
                    "qwen": ceiling.get("qwen_first_stage_ceiling_reached"),
                },
                "earliest_observed_limitation": provenance.get(
                    "earliest_observed_limitation"
                ),
                "requirement_loss_stage_counts": dict(
                    sorted(loss_counts.items())
                ),
                "public_information_gap_eligible": (
                    (provenance.get("gap_eligibility") or {}).get(
                        "public_information_gap_eligible"
                    )
                ),
            }
        )
    summary = dict(projection.get("summary") or {})
    required = int(summary.get("material_scope_required_request_count") or 0)
    ready = int(summary.get("material_scope_ready_request_count") or 0)
    complete = int(summary.get("material_set_complete_request_count") or 0)
    material_scope = projection.get("material_scope") or {}
    material_scope_mode = material_scope.get("mode")
    scope_request_count = (
        int(summary.get("evidence_request_count") or 0)
        if material_scope_mode == "deterministic_scope_ready"
        else required
    )
    if (
        scope_request_count
        and ready == scope_request_count
        and complete == scope_request_count
    ):
        status = "completed_material_sets_ready_candidate_review_pending"
    elif scope_request_count and ready == scope_request_count:
        status = "completed_scope_ready_material_sets_incomplete"
    else:
        status = "completed_material_scope_not_ready"
    public = {
        "status": status,
        "case_key": projection.get("case_key"),
        "research_plan_digest": (
            projection.get("compiled_plan") or {}
        ).get("plan_digest"),
        "projection_digest": projection.get("projection_digest"),
        "material_scope_mode": material_scope_mode,
        "scope_compilation_digest": (
            material_scope.get("scope_compilation")
            or {}
        ).get("compilation_digest"),
        "summary": summary,
        "request_diagnostics": request_rows,
    }
    if material_scope_mode == "deterministic_scope_ready":
        public["fallback_compiler_receipt_digests"] = [
            row.get("receipt_digest")
            for row in material_scope.get("fallback_compiler_receipts") or ()
        ]
    return public


def _materialize_product_replay(
    *,
    projection: Mapping[str, Any],
    bindings: Mapping[str, Mapping[str, str]],
    cuda_receipt: Mapping[str, Any],
    private_output_path: Path,
    public_output_path: Path,
    replay_mode: str | None,
    full_schema_version: str,
    public_schema_version: str,
    known_boundary: str,
) -> dict[str, Any]:
    public_projection = _public_product_replay_projection(projection)
    full_body = {
        "schema_version": full_schema_version,
        "status": public_projection["status"],
        "recorded_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "prepared_from_commit": _head(),
        "source_bindings": dict(bindings),
        "cuda_execution": dict(cuda_receipt),
        "public_projection": public_projection,
        "product_projection": projection,
        "authority": {
            "generation_model_calls": 0,
            "network_calls": 0,
            "candidate_is_not_evidence": True,
            "numeric_authority": False,
            "product_publication": False,
            "s1_qualification_claimed": False,
        },
        "known_boundary": known_boundary,
    }
    if replay_mode is not None:
        full_body["replay_mode"] = replay_mode
    full = {**full_body, "result_digest": canonical_digest(full_body)}
    write_new_json(private_output_path, full)
    public_body = {
        "schema_version": public_schema_version,
        "status": public_projection["status"],
        "recorded_at": full["recorded_at"],
        "prepared_from_commit": full["prepared_from_commit"],
        "source_bindings": dict(bindings),
        "cuda_execution": dict(cuda_receipt),
        **public_projection,
        "full_result_ref": _relative(private_output_path),
        "full_result_sha256": file_sha256(private_output_path),
        "authority": dict(full["authority"]),
        "known_boundary": known_boundary,
    }
    if replay_mode is not None:
        public_body["replay_mode"] = replay_mode
    public = {**public_body, "result_digest": canonical_digest(public_body)}
    write_new_json(public_output_path, public)
    return public


def replay_product_scope(
    *,
    objective_path: Path,
    planner_path: Path,
    scope_payload_path: Path,
    live_result_path: Path,
    full_result_path: Path,
    private_output_path: Path,
    public_output_path: Path,
) -> dict[str, Any]:
    scope_payload = load_json(scope_payload_path)
    live_result = load_json(live_result_path)
    source_full = load_json(full_result_path)
    if not (
        live_result.get("status") == "completed_contract_valid"
        and source_full.get("status") == "completed_contract_valid"
        and source_full.get("scope_payload") == scope_payload
        and live_result.get("full_result_sha256") == file_sha256(full_result_path)
        and live_result.get("research_plan_digest")
        == scope_payload.get("research_plan_digest")
    ):
        raise ValueError("material_scope_product_replay_R3_binding_invalid")

    cuda_receipt = _cuda_execution_receipt()
    service = ResearchRetrievalService.from_runtime_paths(ROOT)
    principal = ResearchRetrievalPrincipal(
        mode="current",
        permissions=frozenset({"current_product:read"}),
    )
    projection = service.execute_controlled_plan(
        "DELL",
        load_json(objective_path),
        load_json(planner_path),
        principal,
        material_scope_payload=scope_payload,
    )
    bindings = {
        "objective": _binding(objective_path),
        "planner_atoms": _binding(planner_path),
        "scope_payload": _binding(scope_payload_path),
        "R3_live_result": _binding(live_result_path),
        "R3_full_result": _binding(full_result_path),
        "workbench_service": _binding(
            ROOT
            / "apps/workbench/backend/application/research_retrieval_service.py"
        ),
        "material_scope_implementation": _binding(
            ROOT / "src/sec_agent/research/material_scope.py"
        ),
        "hybrid_candidate_runtime": _binding(
            ROOT / "src/retrieval/hybrid_candidate_runtime.py"
        ),
        "candidate_ceiling_provenance": _binding(
            ROOT / "src/retrieval/candidate_ceiling_provenance.py"
        ),
    }
    return _materialize_product_replay(
        projection=projection,
        bindings=bindings,
        cuda_receipt=cuda_receipt,
        private_output_path=private_output_path,
        public_output_path=public_output_path,
        replay_mode=None,
        full_schema_version="fin_ia_s1_material_scope_product_replay_full_v1_1",
        public_schema_version="fin_ia_s1_material_scope_product_replay_v1_1",
        known_boundary=(
            "This zero-call replay applies the immutable candidate-blind R3 "
            "scope to the current Workbench BM25 plus Qwen CUDA path. Candidate "
            "rows remain private and are not Evidence. Incomplete material sets "
            "are retrieval or binding findings, not public-information gaps."
        ),
    )


def replay_current_deterministic_scope(
    *,
    case_key: str,
    objective_path: Path,
    planner_path: Path,
    private_output_path: Path,
    public_output_path: Path,
) -> dict[str, Any]:
    """Run one current case through the registered zero-model product path."""

    key = str(case_key).strip().upper()
    objective_payload = load_json(objective_path)
    planner_payload = load_json(planner_path)
    if objective_payload.get("case_key") != key:
        raise ValueError("current_candidate_replay_objective_case_mismatch")
    if int((objective_payload.get("budget") or {}).get("max_model_calls", -1)) != 0:
        raise ValueError("current_candidate_replay_zero_model_budget_required")

    cuda_receipt = _cuda_execution_receipt()
    service = ResearchRetrievalService.from_runtime_paths(ROOT)
    principal = ResearchRetrievalPrincipal(
        mode="current",
        permissions=frozenset({"current_product:read"}),
    )
    projection = service.execute_controlled_plan(
        key,
        objective_payload,
        planner_payload,
        principal,
    )
    material_scope = projection.get("material_scope") or {}
    summary = projection.get("summary") or {}
    if not (
        projection.get("case_key") == key
        and candidate_provenance_scope_mode_valid(material_scope)
        and int(summary.get("model_calls") or 0) == 0
        and int(summary.get("network_calls") or 0) == 0
    ):
        raise ValueError("current_candidate_replay_scope_state_invalid")

    registry_path = (
        ROOT
        / "configs/runtime/"
        "fin_ia_0_1_3_clean_baseline_runtime_resource_registry_v1_0.json"
    )
    bindings = {
        "objective": _binding(objective_path),
        "planner_atoms": _binding(planner_path),
        "runtime_registry": _binding(registry_path),
        "workspace_catalog": _binding(
            resolve_registered_runtime_resource(
                ROOT, "application.config.current_research_workspace_catalog"
            )
        ),
        "kernel": _binding(
            resolve_registered_runtime_resource(
                ROOT, "application.config.current_financial_research_kernel"
            )
        ),
        "planning_policy": _binding(
            resolve_registered_runtime_resource(
                ROOT, "application.config.current_research_planning_policy"
            )
        ),
        "material_runtime_policy": _binding(
            resolve_registered_runtime_resource(
                ROOT,
                "application.config.current_product_material_evidence_runtime_policy",
            )
        ),
        "intent_ontology": _binding(
            resolve_registered_runtime_resource(
                ROOT, "application.config.current_financial_intent_ontology"
            )
        ),
        "workbench_service": _binding(
            ROOT
            / "apps/workbench/backend/application/research_retrieval_service.py"
        ),
        "hybrid_candidate_runtime": _binding(
            ROOT / "src/retrieval/hybrid_candidate_runtime.py"
        ),
        "candidate_ceiling_provenance": _binding(
            ROOT / "src/retrieval/candidate_ceiling_provenance.py"
        ),
    }
    return _materialize_product_replay(
        projection=projection,
        bindings=bindings,
        cuda_receipt=cuda_receipt,
        private_output_path=private_output_path,
        public_output_path=public_output_path,
        replay_mode=(
            "current_case_question_kernel_ontology_deterministic_scope"
            if material_scope.get("mode") == "deterministic_scope_ready"
            else "current_case_question_candidate_provenance_explicit_scope_pending"
        ),
        full_schema_version=(
            "fin_ia_s1_current_candidate_provenance_replay_full_v1_0"
        ),
        public_schema_version="fin_ia_s1_current_candidate_provenance_replay_v1_0",
        known_boundary=(
            "This zero-model S1 development replay compiles the current case "
            "question, kernel facets and provider-neutral ontology into the "
            "registered Workbench BM25 plus Qwen CUDA path. It is not a model-"
            "planned dynamic research run, does not read qrels, gold or hidden "
            "labels, and grants no Evidence, NumericFact, public-gap, S1 "
            "qualification or publication authority. A result whose material "
            "scope mode is explicit_scope_required is retained only as a "
            "candidate-provenance audit and remains material-scope incomplete."
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare or execute the candidate-blind current-product material "
            "scope canary."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--objective", default=DEFAULT_OBJECTIVE)
    prepare_parser.add_argument("--planner-atoms", default=DEFAULT_PLANNER_ATOMS)
    prepare_parser.add_argument("--output", required=True)
    execute_parser = subparsers.add_parser("execute")
    execute_parser.add_argument("--authority", required=True)
    replay_parser = subparsers.add_parser("replay")
    replay_parser.add_argument("--objective", default=DEFAULT_OBJECTIVE)
    replay_parser.add_argument("--planner-atoms", default=DEFAULT_PLANNER_ATOMS)
    replay_parser.add_argument("--scope-payload", default=DEFAULT_R3_SCOPE_PAYLOAD)
    replay_parser.add_argument("--live-result", default=DEFAULT_R3_LIVE_RESULT)
    replay_parser.add_argument("--full-result", default=DEFAULT_R3_FULL_RESULT)
    replay_parser.add_argument(
        "--private-output", default=DEFAULT_PRODUCT_REPLAY_PRIVATE_OUTPUT
    )
    replay_parser.add_argument(
        "--public-output", default=DEFAULT_PRODUCT_REPLAY_PUBLIC_OUTPUT
    )
    current_replay_parser = subparsers.add_parser("current-replay")
    current_replay_parser.add_argument("--case-key", required=True)
    current_replay_parser.add_argument("--objective", required=True)
    current_replay_parser.add_argument("--planner-atoms", required=True)
    current_replay_parser.add_argument("--private-output", required=True)
    current_replay_parser.add_argument("--public-output", required=True)
    args = parser.parse_args()

    if args.command == "prepare":
        result = prepare(
            objective_path=_resolve(args.objective),
            planner_path=_resolve(args.planner_atoms),
            output_path=_resolve(args.output),
        )
        summary = {
            "status": result["status"],
            "result_digest": result["result_digest"],
            "research_plan_digest": result["research_plan_digest"],
            "required_request_count": len(result["required_request_ids"]),
            "product_diagnostic": result["product_diagnostic"],
        }
    elif args.command == "execute":
        summary = run_material_scope_canary(
            _resolve(args.authority), root=ROOT
        )
    elif args.command == "replay":
        summary = replay_product_scope(
            objective_path=_resolve(args.objective),
            planner_path=_resolve(args.planner_atoms),
            scope_payload_path=_resolve(args.scope_payload),
            live_result_path=_resolve(args.live_result),
            full_result_path=_resolve(args.full_result),
            private_output_path=_resolve(args.private_output),
            public_output_path=_resolve(args.public_output),
        )
    else:
        summary = replay_current_deterministic_scope(
            case_key=args.case_key,
            objective_path=_resolve(args.objective),
            planner_path=_resolve(args.planner_atoms),
            private_output_path=_resolve(args.private_output),
            public_output_path=_resolve(args.public_output),
        )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if not str(summary.get("status") or "").startswith("terminal_failed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
