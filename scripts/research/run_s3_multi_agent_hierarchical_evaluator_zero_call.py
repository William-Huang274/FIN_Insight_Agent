from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Callable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

import scripts.research.run_s3_multi_agent_preview_live as live_runner  # noqa: E402
from sec_agent.canonical_runtime import canonical_digest  # noqa: E402
from sec_agent.research.multi_agent_preview import (  # noqa: E402
    MULTI_AGENT_EVALUATION_SCHEMA_VERSION,
    MultiAgentPreviewError,
    compile_case_truth_model_view,
    compile_challenge_catalog,
    compile_cross_role_evaluation_content_view,
    compile_cross_role_evaluation_messages,
    compile_role_evaluation_messages,
    local_case_absence_findings,
    validate_evaluation,
    validate_lead_coordination_checkpoint,
    validate_lead_plan_checkpoint,
    validate_role_evaluation,
    validate_specialist_plan_checkpoint,
    validate_specialist_workpaper_checkpoint,
)
from sec_agent.research.multi_agent_preview_runtime import (  # noqa: E402
    compile_multi_agent_preview_materialization,
)
from sec_agent.research.multi_agent_successor import (  # noqa: E402
    MultiAgentSuccessorError,
    compile_hierarchical_evaluator_zero_call_proof,
    validate_successor_execution_frontier,
)


TOPOLOGY_REF = (
    "configs/research/fin_ia_0_1_3_multi_agent_role_topology_v1_0.json"
)
OBJECTIVE_REF = (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_preview_"
    "objective_v1_0.json"
)
PLAN_CHECKPOINT_REF = (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_preview_"
    "R3_specialist_plan_checkpoint_v1_0.json"
)
LEAD_CHECKPOINT_REF = (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_preview_"
    "R6_lead_plan_checkpoint_v1_0.json"
)
WORKPAPER_CHECKPOINT_REF = (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_preview_"
    "R8_five_workpaper_checkpoint_v1_0.json"
)
COORDINATION_CHECKPOINT_REF = (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_preview_"
    "R10_lead_coordination_checkpoint_v1_0.json"
)


def _load(ref: str | Path) -> dict[str, Any]:
    path = Path(ref)
    if not path.is_absolute():
        path = ROOT / path
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _expect_failure(
    operation: Callable[[], object],
    *,
    error_type: type[Exception],
    code: str,
) -> bool:
    try:
        operation()
    except error_type as exc:
        return code in str(exc)
    return False


def _empty_role_evaluation(workpaper: Mapping[str, Any]) -> dict[str, Any]:
    return validate_role_evaluation(
        {
            "schema_version": MULTI_AGENT_EVALUATION_SCHEMA_VERSION,
            "findings": [],
            "cross_role_conflicts": [],
            "report_may_proceed": True,
        },
        workpaper=workpaper,
    )


def _load_current_research_state(
    *, frontier: Mapping[str, Any]
) -> tuple[
    list[dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, Any],
]:
    topology = _load(TOPOLOGY_REF)
    plan_checkpoint = validate_specialist_plan_checkpoint(
        _load(PLAN_CHECKPOINT_REF), topology=topology
    )
    opinions = plan_checkpoint["specialist_plans"]
    lead_checkpoint = validate_lead_plan_checkpoint(
        _load(LEAD_CHECKPOINT_REF),
        opinions=opinions,
        topology=topology,
    )
    materialization = compile_multi_agent_preview_materialization(
        repo_root=ROOT,
        topology=topology,
        objective_payload=_load(OBJECTIVE_REF),
        opinions=opinions,
        lead_plan=lead_checkpoint["lead_plan"],
    )
    contexts = materialization.context_by_agent()

    workpaper_checkpoint_raw = _load(WORKPAPER_CHECKPOINT_REF)
    workpaper_checkpoint = validate_specialist_workpaper_checkpoint(
        workpaper_checkpoint_raw,
        terminal_failure=_load(
            str(workpaper_checkpoint_raw["source_terminal_result_ref"])
        ),
        contexts=contexts,
    )
    coordination_raw = _load(COORDINATION_CHECKPOINT_REF)
    initial_six = [
        *workpaper_checkpoint["revalidated_workpapers"],
        live_runner._load_bound_counter_workpaper(coordination_raw),
    ]
    validated_coordination = validate_lead_coordination_checkpoint(
        coordination_raw,
        workpapers=initial_six,
        contexts=contexts,
        challenge_catalog=compile_challenge_catalog(workpapers=initial_six),
        coordination_decision=live_runner._load_bound_lead_coordination_decision(
            coordination_raw
        ),
    )
    by_agent = {
        str(row["agent_id"]): deepcopy(dict(row))
        for row in validated_coordination["revalidated_workpapers"]
    }
    completed, completed_contexts, _ = (
        live_runner._load_bound_generic_successor_frontier(frontier=frontier)
    )
    for challenge_id, workpaper in completed.items():
        agent_id = str(workpaper["agent_id"])
        by_agent[agent_id] = deepcopy(dict(workpaper))
        contexts[agent_id] = deepcopy(dict(completed_contexts[challenge_id]))

    ordered_ids = list(lead_checkpoint["lead_plan"]["ordered_agent_ids"])
    ordered_workpapers = [by_agent[agent_id] for agent_id in ordered_ids]
    return (
        ordered_workpapers,
        contexts,
        compile_case_truth_model_view(materialization.case_truth_packet),
    )


def build_proof(*, frontier_path: Path) -> dict[str, Any]:
    frontier = validate_successor_execution_frontier(_load(frontier_path))
    workpapers, contexts, case_truth = _load_current_research_state(
        frontier=frontier
    )
    role_evaluations: dict[str, dict[str, Any]] = {}
    role_receipts: list[dict[str, Any]] = []
    for workpaper in workpapers:
        agent_id = str(workpaper["agent_id"])
        messages = compile_role_evaluation_messages(
            workpaper=workpaper,
            case_truth_model_view=case_truth,
            specialist_context=contexts[agent_id],
        )
        view = json.loads(messages[1]["content"])
        coverage = view["reference_coverage_receipt"]
        role_receipts.append(
            {
                "agent_id": agent_id,
                "workpaper_digest": str(workpaper["workpaper_digest"]),
                "context_digest": str(contexts[agent_id]["context_digest"]),
                "content_view_digest": str(
                    view["evaluation_content_view_digest"]
                ),
                "input_characters": len(messages[1]["content"]),
                "evidence_ref_count": int(coverage["evidence_ref_count"]),
                "numeric_ref_count": int(coverage["numeric_ref_count"]),
                "numeric_relation_ref_count": int(
                    coverage["numeric_relation_ref_count"]
                ),
                "typed_gap_ref_count": int(coverage["typed_gap_ref_count"]),
            }
        )
        role_evaluations[agent_id] = _empty_role_evaluation(workpaper)

    cross_messages = compile_cross_role_evaluation_messages(
        workpapers=workpapers,
        role_evaluations=role_evaluations,
    )
    cross_view = json.loads(cross_messages[1]["content"])

    wrong_target_payload = {
        "schema_version": MULTI_AGENT_EVALUATION_SCHEMA_VERSION,
        "findings": [
            {
                "finding_code": "WRONG_TARGET",
                "severity": "L2",
                "target_agent_id": str(workpapers[1]["agent_id"]),
                "failure_owner": "model_judgment",
                "explanation": "This finding deliberately targets another role.",
                "evidence_refs": [],
                "permitted_repair": "Do not accept a cross-role target in one role audit.",
                "blocks_report": True,
            }
        ],
        "cross_role_conflicts": [],
        "report_may_proceed": False,
    }
    unresolved = deepcopy(workpapers[0])
    unresolved["sourced_claims"][0]["evidence_refs"].append(
        "EV::UNRESOLVED_MUTATION"
    )
    budget_mutation = deepcopy(frontier)
    budget_mutation["execution_limits"]["maximum_new_model_nodes"] += 1
    budget_mutation["result_digest"] = canonical_digest(
        {
            key: value
            for key, value in budget_mutation.items()
            if key != "result_digest"
        }
    )
    reversed_cross = compile_cross_role_evaluation_content_view(
        workpapers=list(reversed(workpapers)),
        role_evaluations=role_evaluations,
    )
    mutation_checks = {
        "missing_role_fails_closed": _expect_failure(
            lambda: compile_cross_role_evaluation_content_view(
                workpapers=workpapers[:-1],
                role_evaluations={
                    key: value
                    for key, value in role_evaluations.items()
                    if key != str(workpapers[-1]["agent_id"])
                },
            ),
            error_type=MultiAgentPreviewError,
            code="multi_agent_cross_role_evaluation_coverage_invalid",
        ),
        "wrong_role_target_fails_closed": _expect_failure(
            lambda: validate_role_evaluation(
                wrong_target_payload, workpaper=workpapers[0]
            ),
            error_type=MultiAgentPreviewError,
            code="multi_agent_finding_invalid",
        ),
        "unresolved_authority_ref_fails_closed": _expect_failure(
            lambda: compile_role_evaluation_messages(
                workpaper=unresolved,
                case_truth_model_view=case_truth,
                specialist_context=contexts[str(unresolved["agent_id"])],
            ),
            error_type=MultiAgentPreviewError,
            code="multi_agent_evaluation_reference_projection_incomplete",
        ),
        "workpaper_permutation_is_stable": (
            reversed_cross["cross_role_evaluation_view_digest"]
            == cross_view["cross_role_evaluation_view_digest"]
        ),
        "frontier_budget_mutation_fails_closed": _expect_failure(
            lambda: validate_successor_execution_frontier(budget_mutation),
            error_type=MultiAgentSuccessorError,
            code="multi_agent_successor_frontier_recompile_drift",
        ),
        "unaffected_role_reevaluation_is_forbidden": (
            frontier["constraints"]["unaffected_role_reevaluation_forbidden"]
            is True
            and frontier["execution_limits"][
                "maximum_affected_role_reevaluation_nodes"
            ]
            == 2
        ),
    }
    local_findings = local_case_absence_findings(
        workpapers=workpapers,
        case_truth_model_view=case_truth,
    )
    return compile_hierarchical_evaluator_zero_call_proof(
        frontier_ref=frontier_path.relative_to(ROOT).as_posix(),
        frontier_sha256=_sha(frontier_path),
        frontier=frontier,
        role_view_receipts=role_receipts,
        cross_role_view_receipt={
            "cross_role_view_digest": cross_view[
                "cross_role_evaluation_view_digest"
            ],
            "input_characters": len(cross_messages[1]["content"]),
            "role_count": len(workpapers),
            "referenced_authority_included": (
                "referenced_authority" in cross_view
            ),
        },
        local_case_absence_blocking_finding_count=len(local_findings),
        mutation_checks=mutation_checks,
        fake_execution_receipt={
            "pass_without_repair_node_count": 8,
            "maximum_two_repair_path_node_count": 13,
            "third_repair_path_node_count": 15,
            "maximum_authorized_model_nodes": 13,
            "conditional_writer_count": 1,
            "unaffected_role_reevaluation_count": 0,
        },
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frontier", required=True)
    args = parser.parse_args(argv)
    frontier_path = Path(args.frontier).resolve()
    proof = build_proof(frontier_path=frontier_path)
    print(json.dumps(proof, ensure_ascii=True, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
