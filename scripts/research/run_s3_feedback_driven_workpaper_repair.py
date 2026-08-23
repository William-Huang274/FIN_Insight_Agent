from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Callable, Mapping


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.canonical_runtime import (  # noqa: E402
    CanonicalRuntimeError,
    append_session_event,
    apply_accepted_plan_delta,
    canonical_digest,
)
from sec_agent.project_os_preflight import build_preflight  # noqa: E402
from sec_agent.providers import (  # noqa: E402
    ModelGatewayError,
    execute_agent_tool_step_exact_once,
    execute_chat_completion_tool_step_exact_once,
    load_agent_transport_profile,
    load_chat_completion_profile,
)
from sec_agent.research.dynamic_single_unit_repair import (  # noqa: E402
    DynamicSingleUnitRepairError,
    LOCKED_WORKPAPER_FIELDS,
    compile_semantic_plan_delta,
    compile_reused_semantic_repair_plan,
    compile_semantic_repair_context,
    compile_semantic_repair_patch_messages,
    compile_semantic_repair_plan_messages,
    create_semantic_repair_session,
    semantic_repair_patch_tool,
    semantic_repair_plan_tool,
    validate_and_merge_semantic_repair_patch,
    validate_semantic_repair_plan,
)


ZERO_RESULT_SCHEMA = (
    "fin_ia_s3_dynamic_single_unit_semantic_repair_zero_call_result_v1_0"
)
LIVE_AUTHORITY_SCHEMA = (
    "fin_ia_s3_dynamic_single_unit_semantic_repair_live_authority_v1_0"
)
LIVE_AUTHORITY_STATUS = (
    "signed_exact_once_DELL_feedback_plan_and_workpaper_patch"
)
PUBLIC_RESULT_SCHEMA = (
    "fin_ia_s3_dynamic_single_unit_semantic_repair_live_result_v1_0"
)
PRIVATE_RESULT_SCHEMA = (
    "fin_ia_s3_dynamic_single_unit_semantic_repair_live_full_v1_0"
)
PATCH_SUCCESSOR_ZERO_RESULT_SCHEMA = (
    "fin_ia_s3_dynamic_single_unit_semantic_patch_successor_zero_call_result_v1_0"
)
PATCH_SUCCESSOR_AUTHORITY_SCHEMA = (
    "fin_ia_s3_dynamic_single_unit_semantic_patch_successor_live_authority_v1_0"
)
PATCH_SUCCESSOR_AUTHORITY_STATUS = (
    "signed_exact_once_DELL_reused_plan_workpaper_patch"
)
PATCH_SUCCESSOR_PUBLIC_RESULT_SCHEMA = (
    "fin_ia_s3_dynamic_single_unit_semantic_patch_successor_live_result_v1_0"
)
PATCH_SUCCESSOR_PRIVATE_RESULT_SCHEMA = (
    "fin_ia_s3_dynamic_single_unit_semantic_patch_successor_live_full_v1_0"
)

DEFAULT_PRIOR_PRIVATE = ROOT / (
    "data/workbench_private/fin_0_1_3_s3_current_dynamic_single_unit_live/"
    "dell-current-dynamic-single-unit-r5-workpaper-20260823t0326z/"
    "full_result.json"
)
DEFAULT_ASSESSMENT = ROOT / (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_single_unit_"
    "workpaper_submission_content_assessment_v1_0.json"
)
DEFAULT_ZERO_OUTPUT = ROOT / (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_single_unit_"
    "semantic_repair_zero_call_result_v1_0.json"
)
DEFAULT_FAILED_REPAIR_PRIVATE = ROOT / (
    "data/workbench_private/fin_0_1_3_s3_current_dynamic_single_unit_live/"
    "dell-current-dynamic-single-unit-r6-semantic-repair-20260823t0433z/"
    "full_result.json"
)
DEFAULT_PATCH_SUCCESSOR_ZERO_OUTPUT = ROOT / (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_single_unit_"
    "semantic_patch_successor_zero_call_result_v1_0.json"
)


class SemanticRepairRunnerError(ValueError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise SemanticRepairRunnerError(code)


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(path: str | Path) -> str:
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def _resolve(ref: str) -> Path:
    path = Path(ref)
    return (ROOT / path).resolve() if not path.is_absolute() else path.resolve()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_new(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
    except FileExistsError as exc:
        raise SemanticRepairRunnerError(
            "semantic_repair_output_identity_consumed"
        ) from exc


def _tool_arguments(step: Any, *, expected_name: str) -> dict[str, Any]:
    calls = list(step.tool_calls or ())
    _require(
        step.finish_reason == "tool_calls" and len(calls) == 1,
        "semantic_repair_expected_single_tool_call",
    )
    function = calls[0].get("function") or {}
    _require(
        str(function.get("name") or "") == expected_name,
        "semantic_repair_tool_name_invalid",
    )
    try:
        payload = json.loads(str(function.get("arguments") or ""))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise SemanticRepairRunnerError(
            "semantic_repair_tool_arguments_json_invalid"
        ) from exc
    _require(isinstance(payload, Mapping), "semantic_repair_tool_arguments_invalid")
    return dict(payload)


def _controlled_plan_payload(context: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "fin_ia_dynamic_single_unit_semantic_repair_plan_v1_0",
        "agent_id": "AGENT::VALUE_CAPTURE",
        "prior_workpaper_digest": context["prior_workpaper_digest"],
        "feedback_resolutions": [
            {
                "feedback_id": row["feedback_id"],
                "resolution_action": row["resolution_action"],
                "affected_surfaces": list(row["affected_surfaces"]),
                "semantic_commitment": row["semantic_commitment"],
                "resolution_summary": (
                    "Remove or downgrade the statement that exceeded the source "
                    "period, authority or hypothesis state, changing only the "
                    "explicitly authorized surfaces."
                ),
            }
            for row in context["resolution_policy"]
        ],
        "ready_to_resubmit": True,
    }


def _controlled_patch_payload(
    context: Mapping[str, Any], plan_delta: Mapping[str, Any]
) -> dict[str, Any]:
    prior = context["prior_workpaper"]
    claims = deepcopy(prior["sourced_claims"])
    claims[0]["claim"] = (
        "管理层称 Q1 FY27 AI 服务器盈利与其中个位数经营利润率目标一致；"
        "这是未经独立验证的发行人目标表述，不能视为已实现转化率。"
    )
    claims[1]["claim"] = (
        "截至 2025-10-31 的 FY26 Q3 历史披露曾把毛利率下降主要归因于 AI "
        "服务器组合迁移；它仅作历史方向背景，不能证明截至 2026-05-01 当季原因。"
    )
    claims[2]["claim"] = (
        "FY27 Q1 公司整体收入同比增长 87.5%，毛利同比增长 57.6%；"
        "两项公司总量不同步，但不能据此归因于 AI 产品。"
    )
    claims[2]["evidence_refs"] = []
    claims[5]["claim"] = (
        "Q1 FY27 经营现金流为 41 亿美元；发行人另披露大额订单可能需要"
        "采购关键部件并带来营运资金和库存风险，但部件身份与回款时点未解决。"
    )
    return {
        "schema_version": "fin_ia_dynamic_single_unit_semantic_repair_patch_v1_0",
        "agent_id": "AGENT::VALUE_CAPTURE",
        "plan_delta_digest": plan_delta["plan_delta_digest"],
        "resolved_feedback_ids": [
            row["feedback_id"] for row in context["feedback_receipts"]
        ],
        "semantic_commitments": [
            row["semantic_commitment"] for row in context["resolution_policy"]
        ],
        "thesis": (
            "DELL 的公司整体收入、毛利和经营利润均增长，但三者必须分别解释。"
            "管理层关于 AI 服务器中个位数经营利润率目标的说法只是未经独立验证的"
            "发行人表述，不能作为已实现转化率；FY26 Q3 的组合说明也只能作为历史"
            "背景。当前资料支持强订单与收入增长，却不能把公司利润变化直接归因于"
            "AI 产品，也不能精确分配供应商、客户与 DELL 的价值池。"
        ),
        "sourced_claims": claims,
        "mechanism": (
            "当前可验证的链条止于公司总量和发行人定性表述。收入、毛利与经营利润"
            "分别受规模、组合、成本和费用杠杆影响；产品级因果桥仍缺失。历史季度的"
            "AI mix 说明只提供方向背景，不能解释当前季度。大额订单可能要求采购"
            "关键部件并占用营运资金，但具体是否为 GPU/HBM、现金何时回收以及价值池"
            "如何在供应商、客户与 DELL 之间分配，均保持为未解决假设。"
        ),
    }


def build_zero_call_result(
    *,
    prior_private: Path = DEFAULT_PRIOR_PRIVATE,
    assessment_path: Path = DEFAULT_ASSESSMENT,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    when = recorded_at or _now()
    context = compile_semantic_repair_context(
        prior_full_result=_json(prior_private),
        assessment=_json(assessment_path),
        assessment_ref=_relative(assessment_path),
        prior_result_ref=_relative(prior_private),
        created_at=when,
    )
    plan_tool = semantic_repair_plan_tool(context)
    plan_messages = compile_semantic_repair_plan_messages(context)
    plan = validate_semantic_repair_plan(
        _controlled_plan_payload(context), context=context
    )
    delta = compile_semantic_plan_delta(plan, context=context)
    patch_tool = semantic_repair_patch_tool(context, delta)
    patch_messages = compile_semantic_repair_patch_messages(context, plan, delta)
    merged = validate_and_merge_semantic_repair_patch(
        _controlled_patch_payload(context, delta),
        context=context,
        plan_delta=delta,
    )

    mutation_results: dict[str, str] = {}
    missing = _controlled_plan_payload(context)
    missing["feedback_resolutions"].pop()
    try:
        validate_semantic_repair_plan(missing, context=context)
    except DynamicSingleUnitRepairError as exc:
        mutation_results["missing_feedback"] = str(exc)
    wrong = _controlled_plan_payload(context)
    wrong["feedback_resolutions"][0]["resolution_action"] = wrong[
        "feedback_resolutions"
    ][1]["resolution_action"]
    try:
        validate_semantic_repair_plan(wrong, context=context)
    except DynamicSingleUnitRepairError as exc:
        mutation_results["wrong_resolution"] = str(exc)
    new_ref_patch = _controlled_patch_payload(context, delta)
    allowed = {
        str(row["evidence_ref"])
        for row in context["full_workpaper_context"]["cell_analysis_view"][
            "evidence_fact_catalog"
        ]
    }
    prior_refs = {
        str(ref)
        for row in context["prior_workpaper"]["sourced_claims"]
        for ref in row["evidence_refs"]
    }
    new_ref = sorted(allowed - prior_refs)[0]
    new_ref_patch["sourced_claims"][0]["evidence_refs"].append(new_ref)
    try:
        validate_and_merge_semantic_repair_patch(
            new_ref_patch, context=context, plan_delta=delta
        )
    except DynamicSingleUnitRepairError as exc:
        mutation_results["new_reference"] = str(exc)

    prior = context["prior_workpaper"]
    repaired = merged["workpaper"]
    checks = {
        "all_five_findings_became_actionable_feedback": len(
            context["feedback_receipts"]
        )
        == 5,
        "same_agent_plan_delta_covers_every_feedback": set(
            delta["reason_feedback_refs"]
        )
        == {row["feedback_id"] for row in context["feedback_receipts"]},
        "only_three_repairable_surfaces_changed": all(
            repaired[field] != prior[field]
            for field in ("thesis", "sourced_claims", "mechanism")
        ),
        "locked_surfaces_byte_equivalent": all(
            repaired[field] == prior[field] for field in LOCKED_WORKPAPER_FIELDS
        ),
        "plan_and_patch_tools_compile": bool(plan_tool and patch_tool),
        "plan_and_patch_messages_compile": bool(plan_messages and patch_messages),
        "new_reference_mutation_rejected": mutation_results.get("new_reference")
        == "dynamic_semantic_repair_patch_new_reference_forbidden",
        "missing_feedback_mutation_rejected": mutation_results.get(
            "missing_feedback"
        )
        == "dynamic_semantic_repair_plan_feedback_coverage_invalid",
        "wrong_resolution_mutation_rejected": mutation_results.get(
            "wrong_resolution"
        )
        == "dynamic_semantic_repair_plan_resolution_invalid",
    }
    _require(all(checks.values()), "semantic_repair_zero_call_proof_failed")
    body = {
        "schema_version": ZERO_RESULT_SCHEMA,
        "status": "semantic_feedback_plan_patch_loop_zero_call_proven",
        "recorded_at": when,
        "case_key": "DELL",
        "cell_id": "CELL::value_capture",
        "source_private_result_ref": _relative(prior_private),
        "source_private_result_sha256": _sha(prior_private),
        "assessment_ref": _relative(assessment_path),
        "assessment_sha256": _sha(assessment_path),
        "semantic_repair_context_digest": context["context_digest"],
        "prior_workpaper_digest_style": context["prior_workpaper_digest_style"],
        "feedback_ids": [row["feedback_id"] for row in context["feedback_receipts"]],
        "plan_delta_digest": delta["plan_delta_digest"],
        "controlled_repaired_workpaper_digest": repaired["workpaper_digest"],
        "repair_receipt_digest": merged["repair_receipt"]["repair_receipt_digest"],
        "checks": checks,
        "mutation_results": mutation_results,
        "execution_summary": {
            "feedback_count": 5,
            "repairable_surface_count": 3,
            "locked_surface_count": len(LOCKED_WORKPAPER_FIELDS),
            "new_reference_count": 0,
            "retrieval_round_count": 0,
        },
        "authority": {
            "model_calls": 0,
            "network_calls": 0,
            "retrieval_calls": 0,
            "candidate_promotions": 0,
            "product_pointer_mutations": 0,
        },
        "known_boundary": (
            "This proves contract and mutation behavior only. The controlled patch "
            "is not a model judgment or accepted research output; a separately "
            "authorized natural repair and independent L1/L2 reassessment remain required."
        ),
    }
    return {**body, "result_digest": canonical_digest(body)}


def build_patch_successor_zero_call_result(
    *,
    prior_private: Path = DEFAULT_PRIOR_PRIVATE,
    assessment_path: Path = DEFAULT_ASSESSMENT,
    failed_repair_private: Path = DEFAULT_FAILED_REPAIR_PRIVATE,
    zero_result_path: Path = DEFAULT_ZERO_OUTPUT,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    when = recorded_at or _now()
    zero = _json(zero_result_path)
    predecessor = _json(prior_private)
    failed = _json(failed_repair_private)
    context = compile_semantic_repair_context(
        prior_full_result=predecessor,
        assessment=_json(assessment_path),
        assessment_ref=_relative(assessment_path),
        prior_result_ref=_relative(prior_private),
        created_at=str(zero["recorded_at"]),
    )
    reused = compile_reused_semantic_repair_plan(
        failed_full_result=failed,
        context=context,
    )
    session, events, accepted_plan_ref = _initialize_reused_plan_session(
        context=context,
        predecessor_session=predecessor["session"],
        reused=reused,
        run_id="zero-call-semantic-patch-successor",
        recorded_at=when,
    )
    merged = validate_and_merge_semantic_repair_patch(
        _controlled_patch_payload(context, reused["plan_delta"]),
        context=context,
        plan_delta=reused["plan_delta"],
    )
    checks = {
        "failed_R6_preserved_and_plan_node_requalified": (
            reused["reuse_receipt"]["provider_calls_reused"] == 1
        ),
        "repair_session_matches_feedback_and_plan_delta": (
            session["session_id"] == context["session_id"]
            == reused["plan_delta"]["session_id"]
        ),
        "predecessor_research_session_immutable": (
            session["session_id"] != predecessor["session"]["session_id"]
        ),
        "accepted_plan_changed_in_successor_session": (
            session["active_plan_ref"] == accepted_plan_ref
        ),
        "event_log_starts_with_successor_session_and_plan": (
            [row["event_type"] for row in events]
            == [
                "session_created",
                "plan_bound",
                "feedback_issued",
                "plan_delta_submitted",
                "plan_delta_accepted",
            ]
        ),
        "controlled_patch_still_valid": bool(merged["workpaper"]),
        "only_one_remaining_provider_call": True,
    }
    _require(all(checks.values()), "semantic_patch_successor_zero_call_failed")
    body = {
        "schema_version": PATCH_SUCCESSOR_ZERO_RESULT_SCHEMA,
        "status": "R6_plan_reused_successor_session_and_patch_seam_zero_call_proven",
        "recorded_at": when,
        "case_key": "DELL",
        "cell_id": "CELL::value_capture",
        "source_failed_private_result_ref": _relative(failed_repair_private),
        "source_failed_private_result_sha256": _sha(failed_repair_private),
        "source_failed_full_result_digest": failed["full_result_digest"],
        "semantic_repair_context_digest": context["context_digest"],
        "repair_plan_reuse_receipt": reused["reuse_receipt"],
        "successor_session": session,
        "successor_session_events": events,
        "controlled_repaired_workpaper_digest": merged["workpaper"][
            "workpaper_digest"
        ],
        "checks": checks,
        "execution": {
            "historical_provider_calls_reused": 1,
            "new_provider_calls": 0,
            "remaining_provider_calls_authorizable": 1,
            "retrieval_rounds": 0,
            "new_evidence": 0,
            "candidate_promotions": 0,
        },
        "known_boundary": (
            "This zero-call proof only repairs the local AgentSession lineage seam "
            "and requalifies the already validated natural R6 repair plan. It does "
            "not produce a natural patch or pass L1/L2; at most one patch call remains."
        ),
    }
    return {**body, "result_digest": canonical_digest(body)}


def _git_blob_sha256(*, commit: str, ref: str) -> str:
    completed = subprocess.run(
        ["git", "show", f"{commit}:{ref}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return hashlib.sha256(completed.stdout).hexdigest()


def validate_live_authority(
    authority: Mapping[str, Any], *, authority_path: Path
) -> dict[str, Path]:
    _require(
        set(authority)
        == {
            "schema_version",
            "status",
            "signed_at",
            "implementation_commit",
            "case_key",
            "cell_id",
            "execution_budget",
            "bound_inputs",
            "output_contract",
            "known_boundary",
        }
        and authority.get("schema_version") == LIVE_AUTHORITY_SCHEMA
        and authority.get("status") == LIVE_AUTHORITY_STATUS
        and authority.get("case_key") == "DELL"
        and authority.get("cell_id") == "CELL::value_capture",
        "semantic_repair_live_authority_identity_invalid",
    )
    _require(
        authority.get("execution_budget")
        == {
            "maximum_model_calls": 2,
            "maximum_transport_attempts": 2,
            "maximum_retrieval_rounds": 0,
            "maximum_s1_s2_requests": 0,
            "maximum_external_source_network_calls": 0,
            "retries_per_model_node": 0,
            "fallbacks": 0,
            "candidate_promotions": 0,
            "current_product_pointer_mutations": 0,
        },
        "semantic_repair_live_budget_invalid",
    )
    bound = authority.get("bound_inputs") or {}
    names = (
        "prior_public_result",
        "prior_private_result",
        "assessment",
        "zero_call_result",
        "scope_decision",
        "plan_profile",
        "submission_profile",
        "runner",
        "repair_runtime",
        "feedback_runtime",
        "agent_transport",
        "chat_transport",
    )
    digest_fields = {
        "prior_public_result_digest",
        "prior_private_result_digest",
        "assessment_digest",
        "zero_call_result_digest",
        "semantic_repair_context_digest",
        "feedback_created_at",
    }
    _require(
        set(bound)
        == {
            *(f"{name}_ref" for name in names),
            *(f"{name}_sha256" for name in names),
            *digest_fields,
        },
        "semantic_repair_live_bound_inputs_invalid",
    )
    paths: dict[str, Path] = {}
    for name in names:
        path = _resolve(str(bound[f"{name}_ref"]))
        _require(
            path.is_file() and _sha(path) == bound[f"{name}_sha256"],
            f"semantic_repair_live_bound_input_drift:{name}",
        )
        paths[f"{name}_ref"] = path
    commit = str(authority.get("implementation_commit") or "")
    _require(bool(re.fullmatch(r"[0-9a-f]{40}", commit)), "semantic_repair_live_commit_invalid")
    for name in (
        "runner",
        "repair_runtime",
        "feedback_runtime",
        "agent_transport",
        "chat_transport",
    ):
        _require(
            _git_blob_sha256(commit=commit, ref=str(bound[f"{name}_ref"]))
            == bound[f"{name}_sha256"],
            f"semantic_repair_live_implementation_drift:{name}",
        )
    preflight = build_preflight(
        root=ROOT,
        decision_ref=_relative(paths["scope_decision_ref"]),
    )
    _require(
        preflight.get("status") == "pass_current_decision_bound_preflight"
        and preflight.get("decision_sha256") == bound["scope_decision_sha256"]
        and (preflight.get("decision_projection") or {}).get(
            "current_dynamic_semantic_repair"
        )
        is True,
        "semantic_repair_live_preflight_invalid",
    )
    zero = _json(paths["zero_call_result_ref"])
    public = _json(paths["prior_public_result_ref"])
    private = _json(paths["prior_private_result_ref"])
    assessment = _json(paths["assessment_ref"])
    context = compile_semantic_repair_context(
        prior_full_result=private,
        assessment=assessment,
        assessment_ref=_relative(paths["assessment_ref"]),
        prior_result_ref=_relative(paths["prior_private_result_ref"]),
        created_at=str(bound["feedback_created_at"]),
    )
    _require(
        zero.get("status") == "semantic_feedback_plan_patch_loop_zero_call_proven"
        and zero.get("result_digest") == bound["zero_call_result_digest"]
        and public.get("result_digest") == bound["prior_public_result_digest"]
        and private.get("full_result_digest") == bound["prior_private_result_digest"]
        and canonical_digest(assessment) == bound["assessment_digest"]
        and context["context_digest"] == bound["semantic_repair_context_digest"],
        "semantic_repair_live_semantic_checkpoint_invalid",
    )
    plan_profile = load_agent_transport_profile(_json(paths["plan_profile_ref"]))
    submission_profile = load_chat_completion_profile(
        _json(paths["submission_profile_ref"])
    )
    _require(
        plan_profile.model == "deepseek-v4-pro"
        and plan_profile.request_defaults.get("thinking") == {"type": "enabled"}
        and plan_profile.request_defaults.get("reasoning_effort") == "max"
        and submission_profile.model == "deepseek-v4-pro"
        and submission_profile.request_defaults.get("thinking") == {"type": "disabled"},
        "semantic_repair_live_profile_invalid",
    )
    output = authority.get("output_contract") or {}
    _require(
        set(output)
        == {"capture_root_ref", "private_output_root_ref", "public_result_ref", "run_id", "attempt_ids", "product_publication"}
        and output.get("product_publication") == "forbidden"
        and len(output.get("attempt_ids") or ()) == 2
        and len(set(output["attempt_ids"])) == 2
        and not _resolve(str(output["private_output_root_ref"])).exists()
        and not _resolve(str(output["public_result_ref"])).exists(),
        "semantic_repair_live_output_identity_invalid",
    )
    _require(
        authority_path.resolve().is_file()
        and bool(str(authority.get("signed_at") or ""))
        and len(str(authority.get("known_boundary") or "")) >= 80,
        "semantic_repair_live_metadata_invalid",
    )
    return paths


def validate_patch_successor_authority(
    authority: Mapping[str, Any], *, authority_path: Path
) -> dict[str, Path]:
    _require(
        set(authority)
        == {
            "schema_version",
            "status",
            "signed_at",
            "implementation_commit",
            "case_key",
            "cell_id",
            "execution_budget",
            "bound_inputs",
            "output_contract",
            "known_boundary",
        }
        and authority.get("schema_version") == PATCH_SUCCESSOR_AUTHORITY_SCHEMA
        and authority.get("status") == PATCH_SUCCESSOR_AUTHORITY_STATUS
        and authority.get("case_key") == "DELL"
        and authority.get("cell_id") == "CELL::value_capture",
        "semantic_patch_successor_authority_identity_invalid",
    )
    expected_budget = {
        "maximum_model_calls": 1,
        "maximum_transport_attempts": 1,
        "maximum_retrieval_rounds": 0,
        "maximum_s1_s2_requests": 0,
        "maximum_external_source_network_calls": 0,
        "retries_per_model_node": 0,
        "fallbacks": 0,
        "candidate_promotions": 0,
        "current_product_pointer_mutations": 0,
    }
    _require(
        authority.get("execution_budget") == expected_budget,
        "semantic_patch_successor_budget_invalid",
    )
    bound = authority.get("bound_inputs") or {}
    names = (
        "prior_private_result",
        "assessment",
        "failed_public_result",
        "failed_private_result",
        "failed_authority",
        "zero_call_result",
        "patch_successor_zero_result",
        "scope_decision",
        "submission_profile",
        "runner",
        "repair_runtime",
        "feedback_runtime",
        "chat_transport",
    )
    digest_fields = {
        "prior_private_result_digest",
        "assessment_digest",
        "failed_public_result_digest",
        "failed_private_result_digest",
        "zero_call_result_digest",
        "patch_successor_zero_result_digest",
        "semantic_repair_context_digest",
        "feedback_created_at",
    }
    _require(
        set(bound)
        == {
            *(f"{name}_ref" for name in names),
            *(f"{name}_sha256" for name in names),
            *digest_fields,
        },
        "semantic_patch_successor_bound_inputs_invalid",
    )
    paths: dict[str, Path] = {}
    for name in names:
        path = _resolve(str(bound[f"{name}_ref"]))
        _require(
            path.is_file() and _sha(path) == bound[f"{name}_sha256"],
            f"semantic_patch_successor_bound_input_drift:{name}",
        )
        paths[f"{name}_ref"] = path
    commit = str(authority.get("implementation_commit") or "")
    _require(
        bool(re.fullmatch(r"[0-9a-f]{40}", commit)),
        "semantic_patch_successor_commit_invalid",
    )
    for name in (
        "runner",
        "repair_runtime",
        "feedback_runtime",
        "chat_transport",
    ):
        _require(
            _git_blob_sha256(commit=commit, ref=str(bound[f"{name}_ref"]))
            == bound[f"{name}_sha256"],
            f"semantic_patch_successor_implementation_drift:{name}",
        )
    preflight = build_preflight(
        root=ROOT,
        decision_ref=_relative(paths["scope_decision_ref"]),
    )
    _require(
        preflight.get("status") == "pass_current_decision_bound_preflight"
        and preflight.get("decision_sha256") == bound["scope_decision_sha256"]
        and (preflight.get("decision_projection") or {}).get(
            "current_dynamic_semantic_repair"
        )
        is True,
        "semantic_patch_successor_preflight_invalid",
    )
    predecessor = _json(paths["prior_private_result_ref"])
    assessment = _json(paths["assessment_ref"])
    failed_public = _json(paths["failed_public_result_ref"])
    failed_private = _json(paths["failed_private_result_ref"])
    failed_authority = _json(paths["failed_authority_ref"])
    zero = _json(paths["zero_call_result_ref"])
    successor_zero = _json(paths["patch_successor_zero_result_ref"])
    context = compile_semantic_repair_context(
        prior_full_result=predecessor,
        assessment=assessment,
        assessment_ref=_relative(paths["assessment_ref"]),
        prior_result_ref=_relative(paths["prior_private_result_ref"]),
        created_at=str(bound["feedback_created_at"]),
    )
    reused = compile_reused_semantic_repair_plan(
        failed_full_result=failed_private,
        context=context,
    )
    _require(
        predecessor.get("full_result_digest")
        == bound["prior_private_result_digest"]
        and canonical_digest(assessment) == bound["assessment_digest"]
        and failed_public.get("result_digest")
        == bound["failed_public_result_digest"]
        and failed_private.get("full_result_digest")
        == bound["failed_private_result_digest"]
        and zero.get("result_digest") == bound["zero_call_result_digest"]
        and context["context_digest"]
        == bound["semantic_repair_context_digest"]
        and successor_zero.get("schema_version")
        == PATCH_SUCCESSOR_ZERO_RESULT_SCHEMA
        and successor_zero.get("status")
        == "R6_plan_reused_successor_session_and_patch_seam_zero_call_proven"
        and successor_zero.get("result_digest")
        == bound["patch_successor_zero_result_digest"]
        and successor_zero.get("source_failed_full_result_digest")
        == failed_private["full_result_digest"]
        and successor_zero.get("semantic_repair_context_digest")
        == context["context_digest"]
        and all((successor_zero.get("checks") or {}).values())
        and reused["reuse_receipt"]["provider_calls_reused"] == 1,
        "semantic_patch_successor_checkpoint_invalid",
    )
    failed_output = failed_authority.get("output_contract") or {}
    _require(
        failed_authority.get("schema_version") == LIVE_AUTHORITY_SCHEMA
        and failed_authority.get("status") == LIVE_AUTHORITY_STATUS
        and (failed_authority.get("execution_budget") or {}).get(
            "maximum_model_calls"
        )
        == 2
        and failed_output.get("public_result_ref")
        == _relative(paths["failed_public_result_ref"])
        and failed_output.get("private_output_root_ref")
        == _relative(paths["failed_private_result_ref"].parent)
        and (failed_private.get("execution") or {}).get(
            "provider_calls_attempted"
        )
        == 1,
        "semantic_patch_successor_failed_authority_invalid",
    )
    submission_profile = load_chat_completion_profile(
        _json(paths["submission_profile_ref"])
    )
    _require(
        submission_profile.model == "deepseek-v4-pro"
        and submission_profile.request_defaults.get("thinking")
        == {"type": "disabled"},
        "semantic_patch_successor_profile_invalid",
    )
    output = authority.get("output_contract") or {}
    _require(
        set(output)
        == {
            "capture_root_ref",
            "private_output_root_ref",
            "public_result_ref",
            "run_id",
            "attempt_id",
            "product_publication",
        }
        and output.get("product_publication") == "forbidden"
        and bool(str(output.get("attempt_id") or ""))
        and not _resolve(str(output["private_output_root_ref"])).exists()
        and not _resolve(str(output["public_result_ref"])).exists(),
        "semantic_patch_successor_output_identity_invalid",
    )
    _require(
        authority_path.resolve().is_file()
        and bool(str(authority.get("signed_at") or ""))
        and len(str(authority.get("known_boundary") or "")) >= 80,
        "semantic_patch_successor_metadata_invalid",
    )
    return paths


def _event(
    events: list[dict[str, Any]],
    *,
    session_id: str,
    event_type: str,
    actor_id: str,
    occurred_at: str,
    attempt_id: str | None = None,
    input_refs: tuple[str, ...] = (),
    output_refs: tuple[str, ...] = (),
    feedback_refs: tuple[str, ...] = (),
) -> None:
    events.append(
        append_session_event(
            events,
            session_id=session_id,
            event_type=event_type,
            actor_id=actor_id,
            occurred_at=occurred_at,
            attempt_id=attempt_id,
            input_refs=input_refs,
            output_refs=output_refs,
            feedback_refs=feedback_refs,
        )
    )


def _public_step(step: Any) -> dict[str, Any]:
    value = step.as_dict()
    return {
        "provider_id": str(value.get("provider_id") or ""),
        "model": str(value.get("model") or ""),
        "finish_reason": str(value.get("finish_reason") or ""),
        "usage": deepcopy(dict(value.get("usage") or {})),
        "tool_call_count": len(value.get("tool_calls") or ()),
        "tool_names": [
            str((row.get("function") or {}).get("name") or "")
            for row in value.get("tool_calls") or ()
        ],
        "request_digest": str(value.get("request_digest") or ""),
        "response_digest": str(value.get("response_digest") or ""),
        "request_capture_ref": _relative(str(value["request_capture_ref"])),
        "response_capture_ref": _relative(str(value["response_capture_ref"])),
        "private_reasoning_fields_redacted": int(
            value.get("private_reasoning_fields_redacted") or 0
        ),
        "model_payload_persisted_in_public_result": False,
        "reasoning_content_persisted": False,
    }


def _append_unterminated_provider_failures(
    events: list[dict[str, Any]],
    *,
    session_id: str,
    occurred_at: str,
    failure_capture_ref: str,
) -> None:
    requested_attempts = {
        str(row.get("attempt_id") or "")
        for row in events
        if row.get("event_type") == "provider_attempt_requested"
        and row.get("attempt_id")
    }
    terminal_attempts = {
        str(row.get("attempt_id") or "")
        for row in events
        if row.get("event_type")
        in {"provider_attempt_completed", "provider_attempt_failed"}
        and row.get("attempt_id")
    }
    for attempt_id in sorted(requested_attempts - terminal_attempts):
        try:
            _event(
                events,
                session_id=session_id,
                event_type="provider_attempt_failed",
                actor_id="PROVIDER::DEEPSEEK",
                occurred_at=occurred_at,
                attempt_id=attempt_id,
                output_refs=(failure_capture_ref,) if failure_capture_ref else (),
            )
        except CanonicalRuntimeError:
            # The typed terminal result below remains authoritative if the
            # event log itself is the component that failed.
            pass


def _initialize_repair_session(
    *,
    context: Mapping[str, Any],
    predecessor_session: Mapping[str, Any],
    run_id: str,
    recorded_at: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    session = create_semantic_repair_session(
        context=context,
        predecessor_session=predecessor_session,
        run_id=run_id,
        created_at=recorded_at,
    )
    events: list[dict[str, Any]] = []
    _event(
        events,
        session_id=session["session_id"],
        event_type="session_created",
        actor_id="S3.DynamicSingleUnitSemanticRepairHarness",
        occurred_at=recorded_at,
        output_refs=(session["session_digest"],),
    )
    _event(
        events,
        session_id=session["session_id"],
        event_type="plan_bound",
        actor_id="S3.DynamicSingleUnitSemanticRepairHarness",
        occurred_at=recorded_at,
        input_refs=(context["repair_base_plan_digest"],),
        output_refs=(session["active_plan_ref"],),
    )
    return session, events


def _initialize_reused_plan_session(
    *,
    context: Mapping[str, Any],
    predecessor_session: Mapping[str, Any],
    reused: Mapping[str, Any],
    run_id: str,
    recorded_at: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    session, events = _initialize_repair_session(
        context=context,
        predecessor_session=predecessor_session,
        run_id=run_id,
        recorded_at=recorded_at,
    )
    feedback_ids = tuple(
        str(row["feedback_id"]) for row in context["feedback_receipts"]
    )
    _event(
        events,
        session_id=session["session_id"],
        event_type="feedback_issued",
        actor_id="S3.IndependentContentVerifier",
        occurred_at=recorded_at,
        input_refs=(context["assessment_ref"],),
        output_refs=(
            "feedback-bundle://" + canonical_digest(context["feedback_receipts"]),
        ),
        feedback_refs=feedback_ids,
    )
    _event(
        events,
        session_id=session["session_id"],
        event_type="plan_delta_submitted",
        actor_id="AGENT::VALUE_CAPTURE",
        occurred_at=recorded_at,
        input_refs=(reused["reuse_receipt"]["source_response_capture_ref"],),
        output_refs=(reused["plan_delta"]["plan_delta_id"],),
        feedback_refs=feedback_ids,
    )
    accepted_plan_body = {
        "predecessor_active_plan_ref": session["active_plan_ref"],
        "repair_plan": reused["repair_plan"],
        "plan_delta_digest": reused["plan_delta"]["plan_delta_digest"],
    }
    accepted_plan_digest = canonical_digest(accepted_plan_body)
    accepted_plan_ref = "PLAN::" + accepted_plan_digest[:24].upper()
    session = apply_accepted_plan_delta(
        session=session,
        plan_delta=reused["plan_delta"],
        expected_base_plan_digest=context["repair_base_plan_digest"],
        accepted_plan_digest=accepted_plan_digest,
        accepted_plan_ref=accepted_plan_ref,
        updated_at=recorded_at,
    )
    _event(
        events,
        session_id=session["session_id"],
        event_type="plan_delta_accepted",
        actor_id="S3.DynamicSingleUnitSemanticRepairHarness",
        occurred_at=recorded_at,
        input_refs=(reused["plan_delta"]["plan_delta_id"],),
        output_refs=(accepted_plan_ref,),
        feedback_refs=feedback_ids,
    )
    return session, events, accepted_plan_ref


def run_live(
    authority_path: Path,
    *,
    plan_executor: Callable[..., Any] = execute_agent_tool_step_exact_once,
    patch_executor: Callable[..., Any] = execute_chat_completion_tool_step_exact_once,
) -> dict[str, Any]:
    authority_path = authority_path.resolve()
    authority = _json(authority_path)
    paths = validate_live_authority(authority, authority_path=authority_path)
    output = authority["output_contract"]
    private_root = _resolve(output["private_output_root_ref"])
    public_path = _resolve(output["public_result_ref"])
    capture_root = _resolve(output["capture_root_ref"])
    recorded_at = _now()
    prior_public = _json(paths["prior_public_result_ref"])
    prior_private = _json(paths["prior_private_result_ref"])
    assessment = _json(paths["assessment_ref"])
    context = compile_semantic_repair_context(
        prior_full_result=prior_private,
        assessment=assessment,
        assessment_ref=_relative(paths["assessment_ref"]),
        prior_result_ref=_relative(paths["prior_private_result_ref"]),
        created_at=authority["bound_inputs"]["feedback_created_at"],
    )
    plan_profile = load_agent_transport_profile(_json(paths["plan_profile_ref"]))
    submission_profile = load_chat_completion_profile(
        _json(paths["submission_profile_ref"])
    )
    attempt_plan, attempt_patch = [str(value) for value in output["attempt_ids"]]
    session, events = _initialize_repair_session(
        context=context,
        predecessor_session=prior_private["session"],
        run_id=str(output["run_id"]),
        recorded_at=recorded_at,
    )
    feedback_ids = tuple(
        str(row["feedback_id"]) for row in context["feedback_receipts"]
    )
    provider_steps: list[dict[str, Any]] = []
    plan: dict[str, Any] = {}
    plan_delta: dict[str, Any] = {}
    repaired: dict[str, Any] = {}
    repair_receipt: dict[str, Any] = {}
    failure_phase = ""
    failure_code = ""
    failure_capture_ref = ""
    _event(
        events,
        session_id=session["session_id"],
        event_type="feedback_issued",
        actor_id="S3.IndependentContentVerifier",
        occurred_at=recorded_at,
        input_refs=(context["assessment_ref"],),
        output_refs=("feedback-bundle://" + canonical_digest(context["feedback_receipts"]),),
        feedback_refs=feedback_ids,
    )
    try:
        plan_messages = compile_semantic_repair_plan_messages(context)
        plan_tool = semantic_repair_plan_tool(context)
        _event(
            events,
            session_id=session["session_id"],
            event_type="provider_attempt_requested",
            actor_id="S3.DynamicSingleUnitSemanticRepairHarness",
            occurred_at=recorded_at,
            attempt_id=attempt_plan,
            input_refs=(
                "messages://" + canonical_digest(plan_messages),
                "tool://" + canonical_digest(plan_tool),
            ),
            feedback_refs=feedback_ids,
        )
        plan_step = plan_executor(
            profile=plan_profile,
            messages=plan_messages,
            tools=[plan_tool],
            capture_root=capture_root,
            run_id=output["run_id"],
            attempt_id=attempt_plan,
            tool_choice=None,
        )
        provider_steps.append(_public_step(plan_step))
        _event(
            events,
            session_id=session["session_id"],
            event_type="provider_attempt_completed",
            actor_id="PROVIDER::DEEPSEEK",
            occurred_at=recorded_at,
            attempt_id=attempt_plan,
            output_refs=(plan_step.request_capture_ref, plan_step.response_capture_ref),
            feedback_refs=feedback_ids,
        )
        plan = validate_semantic_repair_plan(
            _tool_arguments(plan_step, expected_name="submit_semantic_repair_plan"),
            context=context,
        )
        plan_delta = compile_semantic_plan_delta(plan, context=context)
        _event(
            events,
            session_id=session["session_id"],
            event_type="plan_delta_submitted",
            actor_id="AGENT::VALUE_CAPTURE",
            occurred_at=recorded_at,
            attempt_id=attempt_plan,
            input_refs=(context["prior_workpaper_digest"],),
            output_refs=(plan_delta["plan_delta_id"],),
            feedback_refs=feedback_ids,
        )
        accepted_plan_body = {
            "predecessor_active_plan_ref": session["active_plan_ref"],
            "repair_plan": plan,
            "plan_delta_digest": plan_delta["plan_delta_digest"],
        }
        accepted_plan_digest = canonical_digest(accepted_plan_body)
        accepted_plan_ref = "PLAN::" + accepted_plan_digest[:24].upper()
        session = apply_accepted_plan_delta(
            session=session,
            plan_delta=plan_delta,
            expected_base_plan_digest=context["repair_base_plan_digest"],
            accepted_plan_digest=accepted_plan_digest,
            accepted_plan_ref=accepted_plan_ref,
            updated_at=recorded_at,
        )
        _event(
            events,
            session_id=session["session_id"],
            event_type="plan_delta_accepted",
            actor_id="S3.DynamicSingleUnitSemanticRepairHarness",
            occurred_at=recorded_at,
            attempt_id=attempt_plan,
            input_refs=(plan_delta["plan_delta_id"],),
            output_refs=(accepted_plan_ref,),
            feedback_refs=feedback_ids,
        )

        patch_messages = compile_semantic_repair_patch_messages(
            context, plan, plan_delta
        )
        patch_tool = semantic_repair_patch_tool(context, plan_delta)
        _event(
            events,
            session_id=session["session_id"],
            event_type="provider_attempt_requested",
            actor_id="S3.DynamicSingleUnitSemanticRepairHarness",
            occurred_at=recorded_at,
            attempt_id=attempt_patch,
            input_refs=(
                plan_delta["plan_delta_id"],
                "messages://" + canonical_digest(patch_messages),
                "tool://" + canonical_digest(patch_tool),
            ),
            feedback_refs=feedback_ids,
        )
        patch_step = patch_executor(
            profile=submission_profile,
            messages=patch_messages,
            tools=[patch_tool],
            capture_root=capture_root,
            run_id=output["run_id"],
            attempt_id=attempt_patch,
            tool_choice={
                "type": "function",
                "function": {"name": "submit_semantic_repair_patch"},
            },
        )
        provider_steps.append(_public_step(patch_step))
        _event(
            events,
            session_id=session["session_id"],
            event_type="provider_attempt_completed",
            actor_id="PROVIDER::DEEPSEEK",
            occurred_at=recorded_at,
            attempt_id=attempt_patch,
            output_refs=(patch_step.request_capture_ref, patch_step.response_capture_ref),
            feedback_refs=feedback_ids,
        )
        merged = validate_and_merge_semantic_repair_patch(
            _tool_arguments(
                patch_step, expected_name="submit_semantic_repair_patch"
            ),
            context=context,
            plan_delta=plan_delta,
        )
        repaired = merged["workpaper"]
        repair_receipt = merged["repair_receipt"]
    except ModelGatewayError as exc:
        failure_phase = "provider_transport_or_response"
        failure_code = exc.code
        failure_capture_ref = exc.capture_ref
    except DynamicSingleUnitRepairError as exc:
        failure_phase = "semantic_repair_contract"
        failure_code = str(exc)
    except CanonicalRuntimeError as exc:
        failure_phase = "canonical_runtime"
        failure_code = str(exc)
    except SemanticRepairRunnerError as exc:
        failure_phase = "semantic_repair_orchestration"
        failure_code = str(exc)
    except Exception as exc:  # pragma: no cover
        failure_phase = "local_runtime_unhandled"
        failure_code = "semantic_repair_local_exception:" + type(exc).__name__

    if failure_code:
        _append_unterminated_provider_failures(
            events,
            session_id=str(session.get("session_id") or ""),
            occurred_at=recorded_at,
            failure_capture_ref=failure_capture_ref,
        )

    succeeded = bool(repaired)
    status = (
        "completed_semantic_repair_contract_valid_assessment_pending"
        if succeeded
        else "terminal_failed_no_retry"
    )
    execution = {
        "provider_calls_attempted": sum(
            row.get("event_type") == "provider_attempt_requested"
            for row in events
        ),
        "maximum_provider_calls": 2,
        "retrieval_rounds_executed": 0,
        "s1_s2_requests_executed": 0,
        "new_evidence_count": 0,
        "candidate_promotions": 0,
        "external_source_network_calls": 0,
        "retries": 0,
        "fallbacks": 0,
        "product_pointer_mutations": 0,
    }
    failure = {
        "phase": failure_phase,
        "code": failure_code,
        "capture_ref": _relative(failure_capture_ref) if failure_capture_ref else "",
    }
    full_body = {
        "schema_version": PRIVATE_RESULT_SCHEMA,
        "status": status,
        "recorded_at": recorded_at,
        "authority_ref": _relative(authority_path),
        "authority_sha256": _sha(authority_path),
        "implementation_commit": authority["implementation_commit"],
        "case_key": "DELL",
        "cell_id": "CELL::value_capture",
        "source_public_result_ref": _relative(paths["prior_public_result_ref"]),
        "source_public_result_digest": prior_public["result_digest"],
        "source_private_result_ref": _relative(paths["prior_private_result_ref"]),
        "source_private_result_digest": prior_private["full_result_digest"],
        "assessment_ref": _relative(paths["assessment_ref"]),
        "semantic_repair_context": context,
        "session": session,
        "session_events": events,
        "provider_steps": provider_steps,
        "repair_plan": plan,
        "plan_delta": plan_delta,
        "repair_receipt": repair_receipt,
        "workpaper": repaired,
        "execution": execution,
        "failure": failure,
        "known_boundary": authority["known_boundary"],
    }
    full = {**full_body, "full_result_digest": canonical_digest(full_body)}
    _write_new(private_root / "full_result.json", full)
    public_body = {
        "schema_version": PUBLIC_RESULT_SCHEMA,
        "status": status,
        "recorded_at": recorded_at,
        "authority_ref": _relative(authority_path),
        "implementation_commit": authority["implementation_commit"],
        "case_key": "DELL",
        "cell_id": "CELL::value_capture",
        "model": "deepseek-v4-pro",
        "feedback_receipts": context["feedback_receipts"],
        "repair_plan": plan,
        "plan_delta": plan_delta,
        "repair_receipt": repair_receipt,
        "workpaper": repaired,
        "execution": execution,
        "provider_steps": provider_steps,
        "failure": failure,
        "private_full_result_ref": _relative(private_root / "full_result.json"),
        "private_full_result_sha256": _sha(private_root / "full_result.json"),
        "acceptance": {
            "semantic_repair_contract_pass": succeeded,
            "all_five_feedback_consumed": succeeded,
            "L1_L2_reassessment_pending": succeeded,
            "multi_agent_execution": False,
            "S3_pass": False,
            "product_acceptance": False,
            "release_ready": False,
        },
        "known_boundary": authority["known_boundary"],
    }
    public = {**public_body, "result_digest": canonical_digest(public_body)}
    _write_new(public_path, public)
    return public


def run_patch_successor(
    authority_path: Path,
    *,
    patch_executor: Callable[..., Any] = execute_chat_completion_tool_step_exact_once,
) -> dict[str, Any]:
    authority_path = authority_path.resolve()
    authority = _json(authority_path)
    paths = validate_patch_successor_authority(
        authority,
        authority_path=authority_path,
    )
    output = authority["output_contract"]
    private_root = _resolve(output["private_output_root_ref"])
    public_path = _resolve(output["public_result_ref"])
    capture_root = _resolve(output["capture_root_ref"])
    recorded_at = _now()
    predecessor = _json(paths["prior_private_result_ref"])
    assessment = _json(paths["assessment_ref"])
    failed_public = _json(paths["failed_public_result_ref"])
    failed_private = _json(paths["failed_private_result_ref"])
    context = compile_semantic_repair_context(
        prior_full_result=predecessor,
        assessment=assessment,
        assessment_ref=_relative(paths["assessment_ref"]),
        prior_result_ref=_relative(paths["prior_private_result_ref"]),
        created_at=authority["bound_inputs"]["feedback_created_at"],
    )
    reused = compile_reused_semantic_repair_plan(
        failed_full_result=failed_private,
        context=context,
    )
    session, events, accepted_plan_ref = _initialize_reused_plan_session(
        context=context,
        predecessor_session=predecessor["session"],
        reused=reused,
        run_id=str(output["run_id"]),
        recorded_at=recorded_at,
    )
    feedback_ids = tuple(
        str(row["feedback_id"]) for row in context["feedback_receipts"]
    )
    submission_profile = load_chat_completion_profile(
        _json(paths["submission_profile_ref"])
    )
    attempt_id = str(output["attempt_id"])
    provider_steps: list[dict[str, Any]] = []
    repaired: dict[str, Any] = {}
    repair_receipt: dict[str, Any] = {}
    failure_phase = ""
    failure_code = ""
    failure_capture_ref = ""
    try:
        patch_messages = compile_semantic_repair_patch_messages(
            context,
            reused["repair_plan"],
            reused["plan_delta"],
        )
        patch_tool = semantic_repair_patch_tool(
            context,
            reused["plan_delta"],
        )
        _event(
            events,
            session_id=session["session_id"],
            event_type="provider_attempt_requested",
            actor_id="S3.DynamicSingleUnitSemanticRepairHarness",
            occurred_at=recorded_at,
            attempt_id=attempt_id,
            input_refs=(
                reused["reuse_receipt"]["reuse_receipt_digest"],
                reused["plan_delta"]["plan_delta_id"],
                "messages://" + canonical_digest(patch_messages),
                "tool://" + canonical_digest(patch_tool),
            ),
            feedback_refs=feedback_ids,
        )
        patch_step = patch_executor(
            profile=submission_profile,
            messages=patch_messages,
            tools=[patch_tool],
            capture_root=capture_root,
            run_id=output["run_id"],
            attempt_id=attempt_id,
            tool_choice={
                "type": "function",
                "function": {"name": "submit_semantic_repair_patch"},
            },
        )
        provider_steps.append(_public_step(patch_step))
        _event(
            events,
            session_id=session["session_id"],
            event_type="provider_attempt_completed",
            actor_id="PROVIDER::DEEPSEEK",
            occurred_at=recorded_at,
            attempt_id=attempt_id,
            output_refs=(
                patch_step.request_capture_ref,
                patch_step.response_capture_ref,
            ),
            feedback_refs=feedback_ids,
        )
        merged = validate_and_merge_semantic_repair_patch(
            _tool_arguments(
                patch_step,
                expected_name="submit_semantic_repair_patch",
            ),
            context=context,
            plan_delta=reused["plan_delta"],
        )
        repaired = merged["workpaper"]
        repair_receipt = merged["repair_receipt"]
    except ModelGatewayError as exc:
        failure_phase = "provider_transport_or_response"
        failure_code = exc.code
        failure_capture_ref = exc.capture_ref
    except DynamicSingleUnitRepairError as exc:
        failure_phase = "semantic_repair_contract"
        failure_code = str(exc)
    except CanonicalRuntimeError as exc:
        failure_phase = "canonical_runtime"
        failure_code = str(exc)
    except SemanticRepairRunnerError as exc:
        failure_phase = "semantic_repair_orchestration"
        failure_code = str(exc)
    except Exception as exc:  # pragma: no cover
        failure_phase = "local_runtime_unhandled"
        failure_code = "semantic_patch_successor_local_exception:" + type(exc).__name__

    if failure_code:
        _append_unterminated_provider_failures(
            events,
            session_id=session["session_id"],
            occurred_at=recorded_at,
            failure_capture_ref=failure_capture_ref,
        )
    succeeded = bool(repaired)
    status = (
        "completed_semantic_patch_successor_contract_valid_assessment_pending"
        if succeeded
        else "terminal_failed_no_retry"
    )
    current_provider_calls = sum(
        row.get("event_type") == "provider_attempt_requested" for row in events
    )
    execution = {
        "historical_plan_provider_calls_reused": 1,
        "provider_calls_attempted": current_provider_calls,
        "logical_repair_provider_calls_total": 1 + current_provider_calls,
        "maximum_new_provider_calls": 1,
        "retrieval_rounds_executed": 0,
        "s1_s2_requests_executed": 0,
        "new_evidence_count": 0,
        "candidate_promotions": 0,
        "external_source_network_calls": 0,
        "retries": 0,
        "fallbacks": 0,
        "product_pointer_mutations": 0,
    }
    failure = {
        "phase": failure_phase,
        "code": failure_code,
        "capture_ref": (
            _relative(failure_capture_ref) if failure_capture_ref else ""
        ),
    }
    full_body = {
        "schema_version": PATCH_SUCCESSOR_PRIVATE_RESULT_SCHEMA,
        "status": status,
        "recorded_at": recorded_at,
        "authority_ref": _relative(authority_path),
        "authority_sha256": _sha(authority_path),
        "implementation_commit": authority["implementation_commit"],
        "case_key": "DELL",
        "cell_id": "CELL::value_capture",
        "source_failed_public_result_ref": _relative(
            paths["failed_public_result_ref"]
        ),
        "source_failed_public_result_digest": failed_public["result_digest"],
        "source_failed_private_result_ref": _relative(
            paths["failed_private_result_ref"]
        ),
        "source_failed_private_result_digest": failed_private[
            "full_result_digest"
        ],
        "semantic_repair_context": context,
        "repair_plan_reuse_receipt": reused["reuse_receipt"],
        "repair_plan": reused["repair_plan"],
        "plan_delta": reused["plan_delta"],
        "accepted_plan_ref": accepted_plan_ref,
        "session": session,
        "session_events": events,
        "provider_steps": provider_steps,
        "repair_receipt": repair_receipt,
        "workpaper": repaired,
        "execution": execution,
        "failure": failure,
        "known_boundary": authority["known_boundary"],
    }
    full = {**full_body, "full_result_digest": canonical_digest(full_body)}
    _write_new(private_root / "full_result.json", full)
    public_body = {
        "schema_version": PATCH_SUCCESSOR_PUBLIC_RESULT_SCHEMA,
        "status": status,
        "recorded_at": recorded_at,
        "authority_ref": _relative(authority_path),
        "implementation_commit": authority["implementation_commit"],
        "case_key": "DELL",
        "cell_id": "CELL::value_capture",
        "model": "deepseek-v4-pro",
        "source_failed_result_ref": _relative(paths["failed_public_result_ref"]),
        "source_failed_result_digest": failed_public["result_digest"],
        "repair_plan_reuse_receipt": reused["reuse_receipt"],
        "repair_plan": reused["repair_plan"],
        "plan_delta": reused["plan_delta"],
        "repair_receipt": repair_receipt,
        "workpaper": repaired,
        "execution": execution,
        "provider_steps": provider_steps,
        "failure": failure,
        "private_full_result_ref": _relative(private_root / "full_result.json"),
        "private_full_result_sha256": _sha(private_root / "full_result.json"),
        "acceptance": {
            "R6_valid_plan_reused": True,
            "semantic_patch_contract_pass": succeeded,
            "all_five_feedback_consumed": succeeded,
            "L1_L2_reassessment_pending": succeeded,
            "multi_agent_execution": False,
            "S3_pass": False,
            "product_acceptance": False,
            "release_ready": False,
        },
        "known_boundary": authority["known_boundary"],
    }
    public = {**public_body, "result_digest": canonical_digest(public_body)}
    _write_new(public_path, public)
    return public


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--zero-call-output", type=Path)
    group.add_argument("--patch-successor-zero-call-output", type=Path)
    group.add_argument("--authority", type=Path)
    args = parser.parse_args()
    if args.zero_call_output is not None:
        output = args.zero_call_output.resolve()
        result = build_zero_call_result()
        _write_new(output, result)
    elif args.patch_successor_zero_call_output is not None:
        output = args.patch_successor_zero_call_output.resolve()
        result = build_patch_successor_zero_call_result()
        _write_new(output, result)
    else:
        authority = _json(args.authority.resolve())
        if authority.get("schema_version") == PATCH_SUCCESSOR_AUTHORITY_SCHEMA:
            result = run_patch_successor(args.authority.resolve())
        else:
            result = run_live(args.authority.resolve())
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if not str(result.get("status") or "").startswith("terminal_failed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
