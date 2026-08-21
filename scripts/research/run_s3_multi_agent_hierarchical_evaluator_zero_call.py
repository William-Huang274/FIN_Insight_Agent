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
    compile_role_evaluation_progress_checkpoint,
    compile_role_evaluation_messages,
    local_case_absence_findings,
    validate_evaluation,
    validate_lead_coordination_checkpoint,
    validate_lead_plan_checkpoint,
    validate_role_evaluation,
    validate_role_evaluation_progress_checkpoint,
    validate_specialist_plan_checkpoint,
    validate_specialist_workpaper_checkpoint,
)
from sec_agent.research.multi_agent_preview_runtime import (  # noqa: E402
    compile_multi_agent_preview_materialization,
)
from sec_agent.research.multi_agent_successor import (  # noqa: E402
    HIERARCHICAL_EVALUATION_STRATEGY,
    MultiAgentSuccessorError,
    compile_hierarchical_evaluator_zero_call_proof,
    compile_successor_execution_frontier,
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


def build_role_evaluation_checkpoint(
    *,
    frontier_path: Path,
    source_authority_path: Path,
    source_result_path: Path,
    source_terminal_path: Path,
    source_evaluator_profile_path: Path,
) -> dict[str, Any]:
    frontier = validate_successor_execution_frontier(_load(frontier_path))
    workpapers, contexts, _ = _load_current_research_state(frontier=frontier)
    source_authority = _load(source_authority_path)
    source_result = _load(source_result_path)
    source_terminal = _load(source_terminal_path)
    checkpoint = compile_role_evaluation_progress_checkpoint(
        case_key="DELL",
        source_run_id=str(source_authority["outputs"]["run_id"]),
        source_authority_ref=source_authority_path.relative_to(ROOT).as_posix(),
        source_authority_sha256=_sha(source_authority_path),
        source_public_result_ref=source_result_path.relative_to(ROOT).as_posix(),
        source_public_result_sha256=_sha(source_result_path),
        source_public_result_digest=str(source_result["result_digest"]),
        source_terminal_result_ref=source_terminal_path.relative_to(ROOT).as_posix(),
        source_terminal_result_sha256=_sha(source_terminal_path),
        terminal_failure=source_terminal,
        evaluator_analysis_profile_ref=(
            source_evaluator_profile_path.relative_to(ROOT).as_posix()
        ),
        evaluator_analysis_profile_sha256=_sha(source_evaluator_profile_path),
        workpapers=workpapers,
        contexts=contexts,
    )
    return validate_role_evaluation_progress_checkpoint(
        checkpoint,
        terminal_failure=source_terminal,
        workpapers=workpapers,
        contexts=contexts,
    )


def build_proof(
    *,
    frontier_path: Path,
    evaluation_progress_checkpoint_path: Path | None = None,
) -> dict[str, Any]:
    frontier = validate_successor_execution_frontier(_load(frontier_path))
    workpapers, contexts, case_truth = _load_current_research_state(
        frontier=frontier
    )
    completed_role_evaluation_ids = list(
        frontier.get("completed_role_evaluation_agent_ids") or []
    )
    evaluation_progress_checkpoint = None
    if completed_role_evaluation_ids:
        if evaluation_progress_checkpoint_path is None:
            raise MultiAgentSuccessorError(
                "multi_agent_hierarchical_proof_evaluation_checkpoint_missing"
            )
        checkpoint_raw = _load(evaluation_progress_checkpoint_path)
        checkpoint_terminal = _load(
            str(checkpoint_raw["source_terminal_result_ref"])
        )
        evaluation_progress_checkpoint = (
            validate_role_evaluation_progress_checkpoint(
                checkpoint_raw,
                terminal_failure=checkpoint_terminal,
                workpapers=workpapers,
                contexts=contexts,
            )
        )
        if not (
            evaluation_progress_checkpoint["completed_agent_ids"]
            == completed_role_evaluation_ids
            and evaluation_progress_checkpoint["checkpoint_digest"]
            == frontier["evaluation_progress_checkpoint_digest"]
        ):
            raise MultiAgentSuccessorError(
                "multi_agent_hierarchical_proof_evaluation_checkpoint_drift"
            )
    elif evaluation_progress_checkpoint_path is not None:
        raise MultiAgentSuccessorError(
            "multi_agent_hierarchical_proof_evaluation_checkpoint_unexpected"
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
        **(
            {
                "completed_role_evaluation_rerun_is_forbidden": (
                    evaluation_progress_checkpoint is not None
                    and frontier["constraints"][
                        "completed_role_evaluation_rerun_forbidden"
                    ]
                    is True
                    and evaluation_progress_checkpoint["resume_policy"][
                        "completed_role_evaluation_rerun_forbidden"
                    ]
                    is True
                )
            }
            if completed_role_evaluation_ids
            else {}
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
            "pass_without_repair_node_count": (
                8 - len(completed_role_evaluation_ids)
            ),
            "maximum_two_repair_path_node_count": (
                13 - len(completed_role_evaluation_ids)
            ),
            "third_repair_path_node_count": (
                15 - len(completed_role_evaluation_ids)
            ),
            "maximum_authorized_model_nodes": (
                13 - len(completed_role_evaluation_ids)
            ),
            "conditional_writer_count": 1,
            "unaffected_role_reevaluation_count": 0,
        },
    )


def build_checkpointed_frontier(
    *,
    base_frontier_path: Path,
    evaluation_progress_checkpoint_path: Path,
    source_authority_path: Path,
    source_result_path: Path,
    source_terminal_path: Path,
    source_evaluator_profile_path: Path,
) -> dict[str, Any]:
    base_frontier = validate_successor_execution_frontier(
        _load(base_frontier_path)
    )
    checkpoint = build_role_evaluation_checkpoint(
        frontier_path=base_frontier_path,
        source_authority_path=source_authority_path,
        source_result_path=source_result_path,
        source_terminal_path=source_terminal_path,
        source_evaluator_profile_path=source_evaluator_profile_path,
    )
    if checkpoint != _load(evaluation_progress_checkpoint_path):
        raise MultiAgentSuccessorError(
            "multi_agent_checkpointed_frontier_evaluation_checkpoint_drift"
        )
    source_result = _load(source_result_path)
    source_terminal = _load(source_terminal_path)
    predecessor_failure = {
        "authority_ref": source_authority_path.relative_to(ROOT).as_posix(),
        "authority_sha256": _sha(source_authority_path),
        "public_result_ref": source_result_path.relative_to(ROOT).as_posix(),
        "public_result_sha256": _sha(source_result_path),
        "public_result_digest": str(source_result["result_digest"]),
        "terminal_result_ref": source_terminal_path.relative_to(ROOT).as_posix(),
        "terminal_result_sha256": _sha(source_terminal_path),
        "terminal_result_digest": str(source_terminal["full_result_digest"]),
        "failure_code": str(source_result["failure_code"]),
        "provider_attempt_count": int(
            source_result["execution"]["provider_attempts_preserved"]
        ),
    }
    return compile_successor_execution_frontier(
        case_key=str(base_frontier["case_key"]),
        cell_id=str(base_frontier["cell_id"]),
        accepted_challenge_ids=base_frontier["accepted_challenge_ids"],
        lead_coordination_checkpoint_digest=str(
            base_frontier["lead_coordination_checkpoint_digest"]
        ),
        predecessor_failure=predecessor_failure,
        nodes=base_frontier["nodes"],
        evaluation_strategy=HIERARCHICAL_EVALUATION_STRATEGY,
        completed_role_evaluation_agent_ids=checkpoint["completed_agent_ids"],
        evaluation_progress_checkpoint_digest=checkpoint["checkpoint_digest"],
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frontier", required=True)
    parser.add_argument(
        "--output-kind",
        choices=("proof", "evaluation-checkpoint", "checkpointed-frontier"),
        default="proof",
    )
    parser.add_argument("--evaluation-progress-checkpoint")
    parser.add_argument("--source-authority")
    parser.add_argument("--source-result")
    parser.add_argument("--source-terminal")
    parser.add_argument("--source-evaluator-profile")
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    frontier_path = Path(args.frontier).resolve()
    if args.output_kind in {
        "evaluation-checkpoint",
        "checkpointed-frontier",
    }:
        required = (
            args.source_authority,
            args.source_result,
            args.source_terminal,
            args.source_evaluator_profile,
        )
        if any(value is None for value in required):
            parser.error(
                "evaluation-checkpoint requires source authority, result, "
                "terminal, and evaluator profile"
            )
        source_authority_path = Path(args.source_authority).resolve()
        source_result_path = Path(args.source_result).resolve()
        source_terminal_path = Path(args.source_terminal).resolve()
        source_evaluator_profile_path = Path(
            args.source_evaluator_profile
        ).resolve()
        if args.output_kind == "checkpointed-frontier":
            if not args.evaluation_progress_checkpoint:
                parser.error(
                    "checkpointed-frontier requires "
                    "--evaluation-progress-checkpoint"
                )
            output = build_checkpointed_frontier(
                base_frontier_path=frontier_path,
                evaluation_progress_checkpoint_path=Path(
                    args.evaluation_progress_checkpoint
                ).resolve(),
                source_authority_path=source_authority_path,
                source_result_path=source_result_path,
                source_terminal_path=source_terminal_path,
                source_evaluator_profile_path=source_evaluator_profile_path,
            )
        else:
            output = build_role_evaluation_checkpoint(
                frontier_path=frontier_path,
                source_authority_path=source_authority_path,
                source_result_path=source_result_path,
                source_terminal_path=source_terminal_path,
                source_evaluator_profile_path=source_evaluator_profile_path,
            )
    else:
        output = build_proof(
            frontier_path=frontier_path,
            evaluation_progress_checkpoint_path=(
                Path(args.evaluation_progress_checkpoint).resolve()
                if args.evaluation_progress_checkpoint
                else None
            ),
        )
    rendered = json.dumps(output, ensure_ascii=True, indent=2, sort_keys=True)
    if args.output:
        output_path = Path(args.output).resolve()
        output_path.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
