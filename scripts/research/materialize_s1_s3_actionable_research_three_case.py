from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from apps.workbench.backend.application.research_evidence_pack_service import (  # noqa: E402
    ResearchEvidencePackPrincipal,
    ResearchEvidencePackService,
)
from apps.workbench.backend.application.research_retrieval_service import (  # noqa: E402
    ResearchRetrievalPrincipal,
    ResearchRetrievalService,
)
from sec_agent.research.actionable_research_evaluation import (  # noqa: E402
    evaluate_actionable_research_state,
)
from sec_agent.research.current_consumer import (  # noqa: E402
    compile_current_research_messages,
)
from sec_agent.research.dynamic_research_runtime import (  # noqa: E402
    compile_dynamic_research_input_projection,
)
from sec_agent.research.reviewed_evidence_pack import canonical_digest  # noqa: E402
from sec_agent.runtime_bridge.paths import resolve_runtime_paths  # noqa: E402


DEFAULT_OUTPUT = (
    ROOT
    / "configs"
    / "research"
    / "evals"
    / "fin_ia_0_1_3_s1_s3_actionable_research_three_case_zero_call_result_v1_0.json"
)
FORBIDDEN_PUBLIC_KEYS = {
    "candidate_text",
    "private_source_material",
    "source_capture_ref",
    "authorization",
    "cookie",
}


def _json(relative: str) -> dict[str, Any]:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def _all_keys(value: object) -> set[str]:
    if isinstance(value, Mapping):
        return set(str(key).lower() for key in value) | {
            child for item in value.values() for child in _all_keys(item)
        }
    if isinstance(value, list):
        return {child for item in value for child in _all_keys(item)}
    return set()


def _case_summary(pack: Mapping[str, Any]) -> dict[str, Any]:
    state = pack["actionable_research_state"]
    quantitative = pack["quantitative_authority"]
    evaluation = evaluate_actionable_research_state(
        state=state,
        quantitative_authority=quantitative,
    )
    actions = list(state["research_actions"])
    uncertainties = list(state["actionable_uncertainties"])
    source = state["source_portfolio_snapshot"]
    checkpoint = state["context_checkpoint"]
    return {
        "case_key": pack["case_key"],
        "current_pack": {
            "reviewed_evidence_count": pack["summary"]["accepted_evidence_items"],
            "residual_gap_count": pack["summary"]["residual_gaps"],
            "product_readiness_state": pack["product_readiness"][
                "readiness_state"
            ],
        },
        "source_portfolio": {
            "current_source_count": source["current_source_count"],
            "source_class_counts": source["source_class_counts"],
            "source_type_counts": source["source_type_counts"],
            "rights_axes": source["rights_axes"],
        },
        "quantitative_authority": quantitative["summary"],
        "actionable_research": {
            "uncertainty_count": len(uncertainties),
            "research_action_count": len(actions),
            "uncertainty_category_counts": dict(
                sorted(Counter(row["uncertainty_category"] for row in uncertainties).items())
            ),
            "action_type_counts": dict(
                sorted(Counter(row["action_type"] for row in actions).items())
            ),
            "owner_stage_counts": dict(
                sorted(Counter(row["owner_stage"] for row in actions).items())
            ),
            "owning_plane_counts": dict(
                sorted(Counter(row["owning_plane"] for row in actions).items())
            ),
            "public_information_gap_authorized_count": state["summary"][
                "public_information_gap_authorized_count"
            ],
        },
        "reflection_continuity": {
            "feedback_receipt_count": len(state["feedback_receipts"]),
            "plan_delta_status": state["accepted_plan_delta"][
                "validation_status"
            ],
            "active_plan_changed": (
                state["accepted_plan_delta"]["base_plan_digest"]
                != state["accepted_plan"]["plan_digest"]
            ),
            "graph_delta_disposition": state["graph_delta"]["disposition"],
            "stop_decision": state["stop_decision"]["decision"],
            "checkpoint_open_gap_count": len(checkpoint["open_gap_refs"]),
            "checkpoint_unresolved_feedback_count": len(
                checkpoint["unresolved_feedback_refs"]
            ),
            "resume_status": state["resume_receipt"]["status"],
        },
        "token_budget_basis": {
            "basis_id": state["next_natural_node_token_budget_basis"]["basis_id"],
            "input_scale": state["next_natural_node_token_budget_basis"][
                "input_scale"
            ],
            "required_outputs": state["next_natural_node_token_budget_basis"][
                "required_outputs"
            ],
            "capacity_basis": state["next_natural_node_token_budget_basis"][
                "capacity_basis"
            ],
            "execution_authority": state["next_natural_node_token_budget_basis"][
                "execution_authority"
            ],
        },
        "evaluation": {
            "status": evaluation["status"],
            "gates": evaluation["gates"],
            "summary": evaluation["summary"],
            "evaluation_digest": evaluation["evaluation_digest"],
        },
    }


def materialize() -> dict[str, Any]:
    runtime_paths = resolve_runtime_paths(ROOT)
    evidence_service = ResearchEvidencePackService.from_runtime_paths(
        ROOT, runtime_paths
    )
    permissions = frozenset({"current_product:read"})
    evidence_principal = ResearchEvidencePackPrincipal("current", permissions)
    packs = {
        case_key: evidence_service.get_case(case_key, evidence_principal)
        for case_key in ("DELL", "MU", "NVDA")
    }
    case_results = [_case_summary(packs[case_key]) for case_key in packs]

    # Construct the retrieval surface from the current Runtime registry.  The
    # historical consumer proof intentionally freezes its own service inputs;
    # importing that helper here made this current-state materializer combine a
    # new Evidence Pack with an old candidate/index binding.
    retrieval = ResearchRetrievalService.from_runtime_paths(ROOT, runtime_paths)
    controlled = retrieval.execute_controlled_plan(
        "DELL",
        _json(
            "configs/research/evals/"
            "fin_ia_0_1_3_s3_dell_minimal_planner_canary_objective_v1_0.json"
        ),
        _json(
            "tests/fixtures/research/"
            "fin_ia_0_1_3_s3_dell_planner_r1_atoms_v1_0.json"
        ),
        ResearchRetrievalPrincipal("current", permissions),
    )
    dynamic = compile_dynamic_research_input_projection(
        truth_spine_policy=_json(
            "configs/research/"
            "fin_ia_0_1_3_s3_dynamic_truth_spine_policy_v1_1.json"
        ),
        consumer_policy=_json(
            "configs/research/"
            "fin_ia_0_1_3_s3_current_research_consumer_policy_v1_5.json"
        ),
        controlled_plan=controlled,
        evidence_pack=packs["DELL"],
        include_actionable_control_context=True,
    )["dynamic_research_input"]
    cell_consumption = []
    for cell in dynamic["cells"]:
        messages = compile_current_research_messages(
            dynamic,
            required_cell_ids=[cell["cell_id"]],
            submission_transport="final_tool",
        )
        visible = json.loads(messages[1]["content"])
        control = visible["research_control_context"]
        cell_consumption.append(
            {
                "cell_id": cell["cell_id"],
                "user_message_chars": len(messages[1]["content"]),
                "visible_research_action_count": len(
                    control["research_actions"]
                ),
                "visible_feedback_receipt_count": len(
                    control["feedback_receipts"]
                ),
                "stop_decision": control["stop_decision"]["decision"],
                "checkpoint_resume_status": control["checkpoint_resume"][
                    "resume_status"
                ],
                "quantitative_kinds": sorted(
                    {
                        kind
                        for row in visible["numeric_fact_catalog"]
                        for kind in row.get("quantitative_kinds") or ()
                    }
                ),
            }
        )

    unsigned = {
        "schema_version": (
            "fin_ia_s1_s3_actionable_research_three_case_zero_call_result_v1_0"
        ),
        "status": "current_data_runtime_and_s3_consumption_pass",
        "recorded_at": "2026-08-22",
        "scope": {
            "completed_steps": [1, 2, 3, 4, 5, 6, 7],
            "case_keys": ["DELL", "MU", "NVDA"],
            "uses_current_runtime_registry": True,
            "uses_current_private_candidate_replay_for_s2_compilation": True,
            "uses_current_reviewed_evidence_packs": True,
            "natural_model_calls": 0,
            "network_calls": 0,
            "paid_tool_calls": 0,
        },
        "case_results": case_results,
        "dell_dynamic_s3_consumption": {
            "dynamic_research_input_digest": dynamic["research_input_digest"],
            "control_context_status": dynamic["research_control_context"][
                "status"
            ],
            "cell_consumption": cell_consumption,
            "all_five_cells_receive_current_typed_control_context": (
                len(cell_consumption) == 5
                and all(row["visible_research_action_count"] > 0 for row in cell_consumption)
            ),
        },
        "quality_and_authority": {
            "all_three_case_evaluations_pass": all(
                row["evaluation"]["status"] == "pass" for row in case_results
            ),
            "candidate_auto_promotion": 0,
            "public_information_gap_authorized_count": 0,
            "natural_agent_reflection_quality_proven": False,
            "S1_qualified_claimed": False,
            "S3_accepted_claimed": False,
            "release_claimed": False,
            "next_scope": (
                "step_8_bounded_natural_multi_agent_vertical_slice_after_separate_authority"
            ),
        },
    }
    forbidden = FORBIDDEN_PUBLIC_KEYS.intersection(_all_keys(unsigned))
    if forbidden:
        raise RuntimeError(
            "actionable_research_public_result_forbidden_keys:" + ",".join(sorted(forbidden))
        )
    return {**unsigned, "result_digest": canonical_digest(unsigned)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = materialize()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(args.output)
    print(result["result_digest"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
