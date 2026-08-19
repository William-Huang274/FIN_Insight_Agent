from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
for candidate in (ROOT, ROOT / "src"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from sec_agent.canonical_runtime import canonical_digest  # noqa: E402
from sec_agent.research.multi_agent_preview import (  # noqa: E402
    LEAD_PLAN_SCHEMA_VERSION,
    RESEARCH_LEAD_AGENT_ID,
    SPECIALIST_AGENT_IDS,
    compile_analyzed_node_messages,
    compile_analyzed_node_submission_messages,
    compile_lead_plan_messages,
    lead_plan_tool,
    load_multi_agent_role_topology,
    validate_lead_plan,
    validate_specialist_plan_checkpoint,
)
from sec_agent.research.multi_agent_preview_runtime import (  # noqa: E402
    compile_multi_agent_preview_materialization,
)


TOPOLOGY = ROOT / "configs/research/fin_ia_0_1_3_multi_agent_role_topology_v1_0.json"
OBJECTIVE = (
    ROOT
    / "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_multi_agent_preview_objective_v1_0.json"
)
CHECKPOINT = (
    ROOT
    / "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_multi_agent_preview_"
    "R3_specialist_plan_checkpoint_v1_0.json"
)
RESULT = (
    ROOT
    / "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_multi_agent_preview_"
    "R4_plan_successor_zero_call_result_v1_0.json"
)


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _ref(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _deterministic_lead_plan(
    *,
    opinions: list[dict[str, Any]],
    topology: Mapping[str, Any],
) -> dict[str, Any]:
    facets = list(
        dict.fromkeys(
            str(atom["facet_id"])
            for opinion in opinions
            for atom in opinion["requested_atoms"]
        )
    )
    return validate_lead_plan(
        {
            "schema_version": LEAD_PLAN_SCHEMA_VERSION,
            "lead_agent_id": RESEARCH_LEAD_AGENT_ID,
            "accepted_agent_ids": list(SPECIALIST_AGENT_IDS),
            "ordered_agent_ids": list(SPECIALIST_AGENT_IDS),
            "accepted_facets": facets,
            "coordination_questions": [
                "订单、收入、利润和现金是否保持相同公司、期间与事实状态？",
                "上游供给与发行人利润是否被错误升级为 Dell AI 的直接因果事实？",
            ],
            "expected_information_boundaries": [
                "免费公开资料可能不披露订单取消、积压账龄或 Dell 特定供给分配。",
                "当前 S1/S2 权限不包含开放网络补证或生产级时点估值。",
            ],
            "stop_conditions": [
                "六个角色均形成可追溯底稿且全部 L1 冲突已路由。",
                "无法修复的数据或 Harness 缺陷留在原责任层并阻断报告。",
            ],
        },
        opinions=opinions,
        topology=topology,
    )


def _analysis_context_projection_is_lossless(
    *,
    original_messages: list[dict[str, str]] | tuple[dict[str, str], ...],
    analysis_messages: tuple[dict[str, str], ...],
) -> bool:
    if len(analysis_messages) != 2:
        return False
    original_system = "\n\n".join(
        str(row.get("content") or "")
        for row in original_messages
        if row.get("role") == "system"
    )
    original_context = [
        {
            "role": str(row.get("role") or ""),
            "content": str(row.get("content") or ""),
        }
        for row in original_messages
        if row.get("role") != "system"
    ]
    try:
        projected = json.loads(analysis_messages[1]["content"])
    except (KeyError, TypeError, json.JSONDecodeError):
        return False
    return (
        bool(original_system)
        and original_system in analysis_messages[0].get("content", "")
        and projected.get("task_context") == original_context
    )


def run() -> dict[str, Any]:
    topology = load_multi_agent_role_topology(_json(TOPOLOGY))
    objective = _json(OBJECTIVE)
    checkpoint = validate_specialist_plan_checkpoint(
        _json(CHECKPOINT), topology=topology
    )
    opinions = [deepcopy(dict(row)) for row in checkpoint["specialist_plans"]]
    lead_messages = compile_lead_plan_messages(
        topology=topology,
        objective=objective,
        opinions=opinions,
    )
    required_outputs = (
        "accepted_agent_ids",
        "accepted_facets",
        "coordination_questions",
        "expected_information_boundaries",
        "stop_conditions",
    )
    analysis_messages = compile_analyzed_node_messages(
        messages=lead_messages,
        tool_name=str(lead_plan_tool(topology=topology)["function"]["name"]),
        required_outputs=required_outputs,
    )
    sentinel = "ORIGINAL_R3_PLAN_CONTEXT_MUST_NOT_BE_COPIED"
    submission_messages = compile_analyzed_node_submission_messages(
        analysis_draft=(
            "六个角色均被保留；十二个 facet 覆盖七个 Evidence Slot；"
            "所有命题保持原始角色、期间、边界与停止条件，不新增事实。"
        ),
        analysis_messages=(
            *analysis_messages,
            {"role": "user", "content": sentinel},
        ),
        tool_name=str(lead_plan_tool(topology=topology)["function"]["name"]),
        required_outputs=required_outputs,
    )
    analysis_context_projection_valid = _analysis_context_projection_is_lossless(
        original_messages=lead_messages,
        analysis_messages=analysis_messages,
    )
    lead = _deterministic_lead_plan(opinions=opinions, topology=topology)
    materialization = compile_multi_agent_preview_materialization(
        repo_root=ROOT,
        topology=topology,
        objective_payload=objective,
        opinions=opinions,
        lead_plan=lead,
    )
    readiness = materialization.readiness_summary()

    missing_plan_rejected = False
    try:
        validate_lead_plan(
            {
                key: deepcopy(value)
                for key, value in lead.items()
                if key != "lead_plan_digest"
            },
            opinions=opinions[:-1],
            topology=topology,
        )
    except (ValueError, RuntimeError):
        missing_plan_rejected = True
    mutated_checkpoint_rejected = False
    mutated = deepcopy(checkpoint)
    mutated["checkpoint_digest"] = "0" * 64
    try:
        validate_specialist_plan_checkpoint(mutated, topology=topology)
    except (ValueError, RuntimeError):
        mutated_checkpoint_rejected = True

    maximum_new_nodes = 1 + 6 + 1 + 3 + 2 + 2 + 1
    body = {
        "schema_version": (
            "fin_ia_s3_dell_multi_agent_preview_"
            "R4_plan_successor_zero_call_result_v1_0"
        ),
        "status": "R3_plan_checkpoint_successor_zero_call_pass",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "case_key": "DELL",
        "bindings": {
            "topology_ref": _ref(TOPOLOGY),
            "topology_sha256": _sha(TOPOLOGY),
            "objective_ref": _ref(OBJECTIVE),
            "objective_sha256": _sha(OBJECTIVE),
            "plan_checkpoint_ref": _ref(CHECKPOINT),
            "plan_checkpoint_sha256": _sha(CHECKPOINT),
            "plan_checkpoint_digest": checkpoint["checkpoint_digest"],
        },
        "checkpoint_resume": {
            "reused_specialist_plan_count": len(opinions),
            "reused_agent_ids": [str(row["agent_id"]) for row in opinions],
            "new_specialist_plan_model_calls": 0,
            "lead_start_node": "AGENT::RESEARCH_LEAD::LEAD_PLAN",
        },
        "two_phase_projection": {
            "analysis_message_count": len(analysis_messages),
            "submission_message_count": len(submission_messages),
            "analysis_has_original_role_context": (
                analysis_context_projection_valid
            ),
            "submission_contains_analysis_draft": "六个角色均被保留" in json.dumps(
                submission_messages, ensure_ascii=False
            ),
            "submission_excludes_original_context_sentinel": sentinel not in json.dumps(
                submission_messages, ensure_ascii=False
            ),
            "analysis_draft_business_promotion": False,
        },
        "materialization_readiness": readiness,
        "execution_budget_projection": {
            "maximum_new_model_nodes": maximum_new_nodes,
            "lead_nodes": 2,
            "specialist_workpaper_nodes": 6,
            "maximum_counter_repair_nodes": 3,
            "maximum_evaluator_nodes": 2,
            "maximum_evaluator_repair_nodes": 2,
            "conditional_writer_nodes": 1,
            "maximum_analysis_calls_per_node": 1,
            "maximum_submission_attempts_per_node": 2,
        },
        "negative_mutations": {
            "missing_specialist_plan_rejected": missing_plan_rejected,
            "checkpoint_digest_mutation_rejected": mutated_checkpoint_rejected,
            "original_context_not_copied_to_submission": sentinel
            not in json.dumps(submission_messages, ensure_ascii=False),
        },
        "claims": {
            "model_calls": 0,
            "network_calls": 0,
            "paid_tool_calls": 0,
            "candidate_promotions": 0,
            "S1_pass": False,
            "S3_pass": False,
            "true_multi_agent_live_completed": False,
        },
    }
    if not (
        len(opinions) == 6
        and readiness["blocking_empty_role_ids"] == []
        and maximum_new_nodes == 16
        and all(body["negative_mutations"].values())
        and body["two_phase_projection"]["analysis_has_original_role_context"]
        and body["two_phase_projection"]["submission_contains_analysis_draft"]
    ):
        raise RuntimeError("multi_agent_plan_successor_zero_call_not_passed")
    result = {**body, "result_digest": canonical_digest(body)}
    if RESULT.exists():
        raise RuntimeError("multi_agent_plan_successor_zero_call_result_exists")
    with RESULT.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n"
        )
    return result


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2, sort_keys=True))
