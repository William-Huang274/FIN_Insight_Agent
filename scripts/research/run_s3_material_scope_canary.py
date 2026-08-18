from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


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
    else:
        summary = run_material_scope_canary(
            _resolve(args.authority), root=ROOT
        )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if not str(summary.get("status") or "").startswith("terminal_failed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
