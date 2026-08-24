from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
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
    / "fin_ia_0_1_3_s1_s3_actionable_research_three_case_zero_call_result_v1_2.json"
)
CURRENT_BINDING_RECEIPT = (
    ROOT
    / "configs"
    / "runtime"
    / "fin_ia_0_1_3_current_s1_runtime_binding_receipt_v1_12.json"
)
CURRENT_PACK_RESULT = (
    ROOT
    / "configs"
    / "runtime"
    / "fin_ia_current_research_evidence_pack_result_v1_6.json"
)
CURRENT_READINESS = {
    "DELL": ROOT
    / "configs"
    / "retrieval"
    / "fin_ia_0_1_3_s1_dell_current_product_readiness_result_v1_7.json",
    "MU": ROOT
    / "configs"
    / "retrieval"
    / "fin_ia_0_1_3_s1_mu_current_product_readiness_result_v1_6.json",
    "NVDA": ROOT
    / "configs"
    / "retrieval"
    / "fin_ia_0_1_3_s1_nvda_current_product_readiness_result_v1_6.json",
}
FORBIDDEN_PUBLIC_KEYS = {
    "candidate_text",
    "private_source_material",
    "source_capture_ref",
    "authorization",
    "cookie",
}


def _json(relative: str) -> dict[str, Any]:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def _json_path(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"three_case_json_object_required:{path.name}")
    return payload


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_output(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


def _write_new(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(dict(payload), handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    except FileExistsError as exc:
        raise FileExistsError(
            f"three_case_generalization_output_exists:{path.resolve()}"
        ) from exc


def _current_binding_projection(
    packs: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    receipt = _json_path(CURRENT_BINDING_RECEIPT)
    pack_result = _json_path(CURRENT_PACK_RESULT)
    bindings = dict(receipt.get("bindings") or {})
    runtime_registry = dict(bindings.get("runtime_registry") or {})
    if runtime_registry.get("registry_id") != (
        "FIN-0.1.3-CURRENT-PRODUCT-RUNTIME-RESOURCE-REGISTRY-R36"
    ):
        raise ValueError("three_case_current_registry_R36_required")

    expected_paths = {
        "current_evidence_pack_result": CURRENT_PACK_RESULT,
        **{
            f"{case_key.lower()}_product_readiness": path
            for case_key, path in CURRENT_READINESS.items()
        },
    }
    for binding_key, path in expected_paths.items():
        binding = dict(bindings.get(binding_key) or {})
        if binding.get("ref") != _relative(path) or binding.get("sha256") != _sha256(
            path
        ):
            raise ValueError(f"three_case_current_binding_invalid:{binding_key}")

    readiness_projection: dict[str, Any] = {}
    pack_projection: dict[str, Any] = {}
    for case_key in ("DELL", "MU", "NVDA"):
        pack = packs[case_key]
        readiness = _json_path(CURRENT_READINESS[case_key])
        pack_readiness = dict(pack.get("product_readiness") or {})
        if readiness.get("result_digest") != pack_readiness.get("result_digest"):
            raise ValueError(
                f"three_case_pack_readiness_digest_mismatch:{case_key}"
            )
        if readiness.get("readiness_state") != pack_readiness.get("readiness_state"):
            raise ValueError(
                f"three_case_pack_readiness_state_mismatch:{case_key}"
            )
        readiness_projection[case_key] = {
            "ref": _relative(CURRENT_READINESS[case_key]),
            "sha256": _sha256(CURRENT_READINESS[case_key]),
            "result_digest": readiness["result_digest"],
            "readiness_state": readiness["readiness_state"],
            "request_count": readiness["request_count"],
            "accepted_reviewed_evidence_count": readiness[
                "accepted_reviewed_evidence_count"
            ],
            "candidate_count": readiness["candidate_count"],
        }
        pack_projection[case_key] = {
            "artifact_digest": pack["artifact_digest"],
            "pack_payload_digest": pack["pack_payload_digest"],
            "projection_digest": pack["projection_digest"],
        }

    lineage = dict(pack_result.get("current_composition_lineage") or {})
    retained = set(lineage.get("retained_case_keys") or ())
    if not {"MU", "NVDA"}.issubset(retained):
        raise ValueError("three_case_MU_NVDA_retained_digest_lineage_required")
    if "DELL" not in set(lineage.get("replacement_case_keys") or ()):
        raise ValueError("three_case_DELL_R34_replacement_required")

    return {
        "runtime_binding_receipt": {
            "ref": _relative(CURRENT_BINDING_RECEIPT),
            "sha256": _sha256(CURRENT_BINDING_RECEIPT),
            "policy_id": receipt["policy_id"],
            "registry_id": runtime_registry["registry_id"],
        },
        "current_pack_result": {
            "ref": _relative(CURRENT_PACK_RESULT),
            "sha256": _sha256(CURRENT_PACK_RESULT),
            "result_digest": pack_result["result_digest"],
            "attempt_id": pack_result["attempt_id"],
            "DELL_replaced_in_current_composition": True,
            "MU_NVDA_retained_by_digest_without_rematerialization": True,
        },
        "case_pack_identities": pack_projection,
        "case_readiness": readiness_projection,
    }


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


def materialize(
    *,
    attempt_id: str,
    recorded_at: str,
    prepared_from_commit: str,
) -> dict[str, Any]:
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
    current_bindings = _current_binding_projection(packs)
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
            "fin_ia_0_1_3_s3_current_research_consumer_policy_v1_6.json"
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
            "fin_ia_s1_s3_actionable_research_three_case_zero_call_result_v1_2"
        ),
        "attempt_id": attempt_id,
        "status": "current_data_runtime_and_s3_consumption_pass",
        "recorded_at": recorded_at,
        "prepared_from_commit": prepared_from_commit,
        "current_bindings": current_bindings,
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
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(
            f"three_case_generalization_output_exists:{args.output.resolve()}"
        )
    if _git_output("status", "--porcelain"):
        raise RuntimeError("three_case_generalization_clean_worktree_required")
    result = materialize(
        attempt_id=args.attempt_id,
        recorded_at=datetime.now(timezone.utc).astimezone().isoformat(
            timespec="seconds"
        ),
        prepared_from_commit=_git_output("rev-parse", "HEAD"),
    )
    _write_new(args.output, result)
    print(args.output)
    print(result["result_digest"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
