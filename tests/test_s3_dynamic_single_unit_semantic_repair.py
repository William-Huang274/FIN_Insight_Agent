from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from sec_agent.canonical_runtime import (
    append_session_event,
    apply_accepted_plan_delta,
    canonical_digest,
    create_agent_session,
)
from sec_agent.providers.chat_completions import ChatCompletionToolStepResult
from scripts.research.run_s3_feedback_driven_workpaper_repair import (
    PATCH_SUCCESSOR_AUTHORITY_SCHEMA,
    PATCH_SUCCESSOR_AUTHORITY_STATUS,
    SemanticRepairRunnerError,
    _append_unterminated_provider_failures,
    _public_step,
    build_patch_capture_requalification_zero_call_result,
    build_patch_successor_zero_call_result,
    run_patch_successor,
    validate_patch_successor_authority,
)
from sec_agent.research.dynamic_single_unit_repair import (
    DynamicSingleUnitRepairError,
    LOCKED_WORKPAPER_FIELDS,
    compile_reused_semantic_repair_plan,
    compile_semantic_plan_delta,
    compile_semantic_repair_context,
    compile_semantic_repair_reference_envelope,
    create_semantic_repair_session,
    semantic_repair_patch_tool,
    semantic_repair_plan_tool,
    validate_and_merge_semantic_repair_patch,
    validate_semantic_repair_plan,
)


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_RESULT = ROOT / (
    "data/workbench_private/fin_0_1_3_s3_current_dynamic_single_unit_live/"
    "dell-current-dynamic-single-unit-r5-workpaper-20260823t0326z/"
    "full_result.json"
)
ASSESSMENT = ROOT / (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_single_unit_"
    "workpaper_submission_content_assessment_v1_0.json"
)
FAILED_R6_RESULT = ROOT / (
    "data/workbench_private/fin_0_1_3_s3_current_dynamic_single_unit_live/"
    "dell-current-dynamic-single-unit-r6-semantic-repair-20260823t0433z/"
    "full_result.json"
)
FAILED_R7_RESULT = ROOT / (
    "data/workbench_private/fin_0_1_3_s3_current_dynamic_single_unit_live/"
    "dell-current-dynamic-single-unit-r7-semantic-patch-20260823t0504z/"
    "full_result.json"
)
REQUALIFIED_R7_RESULT = ROOT / (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_single_unit_"
    "semantic_patch_capture_requalification_zero_call_result_v1_0.json"
)
R7_CONTENT_ASSESSMENT = ROOT / (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_single_unit_"
    "semantic_patch_content_assessment_v1_0.json"
)


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _provider_step() -> ChatCompletionToolStepResult:
    return ChatCompletionToolStepResult(
        status="completed_exact_once_tool_step",
        provider_id="deepseek",
        model="deepseek-v4-pro",
        content="private content",
        reasoning_content="transient reasoning",
        tool_calls=(
            {
                "id": "call-1",
                "type": "function",
                "function": {
                    "name": "submit_semantic_repair_plan",
                    "arguments": json.dumps({"private_atom": "do-not-publish"}),
                },
            },
        ),
        finish_reason="tool_calls",
        usage={"prompt_tokens": 10, "completion_tokens": 5},
        request_capture_ref=str(ROOT / "data/captures/request.json"),
        response_capture_ref=str(ROOT / "data/captures/response.json"),
        request_digest="a" * 64,
        response_digest="b" * 64,
        private_reasoning_fields_redacted=1,
    )


def _context() -> dict:
    return compile_semantic_repair_context(
        prior_full_result=_json(PRIVATE_RESULT),
        assessment=_json(ASSESSMENT),
        assessment_ref=ASSESSMENT.relative_to(ROOT).as_posix(),
        prior_result_ref=PRIVATE_RESULT.relative_to(ROOT).as_posix(),
        created_at="2026-08-23T04:10:53.556772+00:00",
    )


def _plan_payload(context: dict) -> dict:
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
                    "我会删除或降级越过来源时期、权威和假设状态的表述，"
                    "并仅重写本反馈指定的正文表面。"
                ),
            }
            for row in context["resolution_policy"]
        ],
        "ready_to_resubmit": True,
    }


def _patch_payload(context: dict, plan_delta: dict) -> dict:
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


def test_semantic_repair_context_plan_and_merge_preserve_authority() -> None:
    context = _context()
    assert len(context["feedback_receipts"]) == 5
    assert len(context["resolution_policy"]) == 5
    assert "reliable realized" in context["feedback_receipts"][0][
        "model_visible_summary"
    ]
    assert semantic_repair_plan_tool(context)["function"]["name"] == (
        "submit_semantic_repair_plan"
    )

    plan = validate_semantic_repair_plan(_plan_payload(context), context=context)
    delta = compile_semantic_plan_delta(plan, context=context)
    assert delta["validation_status"] == "accepted"
    assert set(delta["reason_feedback_refs"]) == {
        row["feedback_id"] for row in context["feedback_receipts"]
    }
    assert semantic_repair_patch_tool(context, delta)["function"]["name"] == (
        "submit_semantic_repair_patch"
    )

    result = validate_and_merge_semantic_repair_patch(
        _patch_payload(context, delta), context=context, plan_delta=delta
    )
    repaired = result["workpaper"]
    assert repaired["workpaper_digest"] != context["prior_workpaper_digest"]
    for field in LOCKED_WORKPAPER_FIELDS:
        assert repaired[field] == context["prior_workpaper"][field]
    assert result["repair_receipt"]["new_reference_count"] == 0
    assert result["repair_receipt"][
        "new_evidence_or_authority_reference_count"
    ] == 0
    assert result["repair_receipt"][
        "context_bound_reference_addition_count"
    ] == 0
    assert result["repair_receipt"]["retrieval_round_count"] == 0


def test_semantic_repair_reference_envelope_is_plan_scoped_and_schema_aligned() -> None:
    context = _context()
    plan = validate_semantic_repair_plan(_plan_payload(context), context=context)
    delta = compile_semantic_plan_delta(plan, context=context)
    envelope = compile_semantic_repair_reference_envelope(context, delta)
    assert envelope["permitted_context_bound_additions"] == {
        "evidence_refs": [],
        "numeric_refs": [
            "NUM::BA153FB9939D66DF",
            "NUM::D0EA6489B2C138EE",
        ],
        "numeric_relation_refs": ["REL::E3A67501DFA73ACF"],
    }
    claim_schema = semantic_repair_patch_tool(context, delta)["function"][
        "parameters"
    ]["properties"]["sourced_claims"]["items"]["properties"]
    for field in ("evidence_refs", "numeric_refs", "numeric_relation_refs"):
        assert set(claim_schema[field]["items"]["enum"]) == set(
            envelope["allowed_refs"][field]
        )


def test_semantic_repair_rejects_missing_feedback_wrong_action_and_new_ref() -> None:
    context = _context()
    missing = _plan_payload(context)
    missing["feedback_resolutions"].pop()
    with pytest.raises(
        DynamicSingleUnitRepairError,
        match="dynamic_semantic_repair_plan_feedback_coverage_invalid",
    ):
        validate_semantic_repair_plan(missing, context=context)

    wrong = _plan_payload(context)
    wrong["feedback_resolutions"][0]["resolution_action"] = (
        wrong["feedback_resolutions"][1]["resolution_action"]
    )
    with pytest.raises(
        DynamicSingleUnitRepairError,
        match="dynamic_semantic_repair_plan_resolution_invalid",
    ):
        validate_semantic_repair_plan(wrong, context=context)

    plan = validate_semantic_repair_plan(_plan_payload(context), context=context)
    delta = compile_semantic_plan_delta(plan, context=context)
    patch = _patch_payload(context, delta)
    allowed = {
        row["evidence_ref"]
        for row in context["full_workpaper_context"]["cell_analysis_view"][
            "evidence_fact_catalog"
        ]
    }
    prior = {
        ref
        for row in context["prior_workpaper"]["sourced_claims"]
        for ref in row["evidence_refs"]
    }
    new_ref = sorted(allowed - prior)[0]
    patch["sourced_claims"][0]["evidence_refs"].append(new_ref)
    with pytest.raises(
        DynamicSingleUnitRepairError,
        match="dynamic_semantic_repair_patch_new_reference_forbidden",
    ):
        validate_and_merge_semantic_repair_patch(
            patch, context=context, plan_delta=delta
        )


def test_semantic_repair_rejects_assessment_or_context_drift() -> None:
    assessment = _json(ASSESSMENT)
    assessment["case_key"] = "MU"
    with pytest.raises(
        DynamicSingleUnitRepairError,
        match="dynamic_semantic_repair_assessment_invalid",
    ):
        compile_semantic_repair_context(
            prior_full_result=_json(PRIVATE_RESULT),
            assessment=assessment,
            assessment_ref="assessment.json",
            prior_result_ref="result.json",
            created_at="2026-08-23T04:30:00Z",
        )

    context = _context()
    context["locked_surfaces_digest"] = "0" * 64
    plan = validate_semantic_repair_plan(_plan_payload(context), context=context)
    delta = compile_semantic_plan_delta(plan, context=context)
    with pytest.raises(
        DynamicSingleUnitRepairError,
        match="dynamic_semantic_repair_locked_surface_drift",
    ):
        validate_and_merge_semantic_repair_patch(
            _patch_payload(context, delta), context=context, plan_delta=delta
        )


def test_semantic_repair_public_step_is_capture_index_not_model_payload() -> None:
    public = _public_step(_provider_step())
    rendered = json.dumps(public, ensure_ascii=False)
    assert public["tool_names"] == ["submit_semantic_repair_plan"]
    assert public["tool_call_count"] == 1
    assert public["model_payload_persisted_in_public_result"] is False
    assert "private_atom" not in rendered
    assert "private content" not in rendered
    assert "transient reasoning" not in rendered


def test_semantic_repair_appends_failed_terminal_for_requested_attempt() -> None:
    session = create_agent_session(
        session_id="SESSION::DELL::SEMANTIC-REPAIR-TEST",
        run_id="RUN::DELL::SEMANTIC-REPAIR-TEST",
        case_id="CASE::DELL",
        case_version="DELL::CURRENT::2026-08-06",
        as_of_date="2026-08-06",
        objective_ref="objective://dell/value-capture",
        active_plan_ref="plan://dell/value-capture/r5",
        created_at="2026-08-23T00:00:00Z",
    )
    events = [
        append_session_event(
            [],
            session_id=session["session_id"],
            event_type="provider_attempt_requested",
            actor_id="S3.DynamicSingleUnitSemanticRepairHarness",
            occurred_at="2026-08-23T00:00:01Z",
            attempt_id="ATTEMPT::REPAIR-PLAN",
        )
    ]
    _append_unterminated_provider_failures(
        events,
        session_id=session["session_id"],
        occurred_at="2026-08-23T00:00:02Z",
        failure_capture_ref="capture://failure",
    )
    assert [row["event_type"] for row in events] == [
        "provider_attempt_requested",
        "provider_attempt_failed",
    ]
    assert events[-1]["output_refs"] == ["capture://failure"]


def test_semantic_repair_uses_successor_session_and_reuses_completed_plan() -> None:
    context = _context()
    predecessor = _json(PRIVATE_RESULT)
    session = create_semantic_repair_session(
        context=context,
        predecessor_session=predecessor["session"],
        run_id="dell-semantic-repair-successor-test",
        created_at="2026-08-23T04:40:00Z",
    )
    assert session["session_id"] == context["session_id"]
    assert session["session_id"] != predecessor["session"]["session_id"]
    assert session["case_id"] == predecessor["session"]["case_id"]
    assert session["as_of_date"] == predecessor["session"]["as_of_date"]

    reused = compile_reused_semantic_repair_plan(
        failed_full_result=_json(FAILED_R6_RESULT),
        context=context,
    )
    assert reused["reuse_receipt"]["provider_calls_reused"] == 1
    assert reused["reuse_receipt"]["provider_calls_added"] == 0
    accepted_body = {
        "predecessor_active_plan_ref": session["active_plan_ref"],
        "repair_plan": reused["repair_plan"],
        "plan_delta_digest": reused["plan_delta"]["plan_delta_digest"],
    }
    accepted_digest = canonical_digest(accepted_body)
    advanced = apply_accepted_plan_delta(
        session=session,
        plan_delta=reused["plan_delta"],
        expected_base_plan_digest=context["repair_base_plan_digest"],
        accepted_plan_digest=accepted_digest,
        accepted_plan_ref="PLAN::" + accepted_digest[:24].upper(),
        updated_at="2026-08-23T04:40:01Z",
    )
    assert advanced["active_plan_ref"] != session["active_plan_ref"]


def test_semantic_repair_rejects_reuse_when_plan_or_failure_drifts() -> None:
    context = _context()
    failed = _json(FAILED_R6_RESULT)
    failed["failure"]["code"] = "some_other_failure"
    with pytest.raises(
        DynamicSingleUnitRepairError,
        match="dynamic_semantic_repair_reuse_predecessor_invalid",
    ):
        compile_reused_semantic_repair_plan(
            failed_full_result=failed,
            context=context,
        )

    failed = _json(FAILED_R6_RESULT)
    failed["repair_plan"]["feedback_resolutions"].pop()
    with pytest.raises(
        DynamicSingleUnitRepairError,
        match="dynamic_semantic_repair_plan_feedback_coverage_invalid",
    ):
        compile_reused_semantic_repair_plan(
            failed_full_result=failed,
            context=context,
        )


def test_semantic_patch_successor_zero_call_proves_remaining_seam() -> None:
    result = build_patch_successor_zero_call_result(
        recorded_at="2026-08-23T04:44:37.270569+00:00",
    )
    assert result["status"] == (
        "R6_plan_reused_successor_session_and_patch_seam_zero_call_proven"
    )
    assert all(result["checks"].values())
    assert result["execution"] == {
        "historical_provider_calls_reused": 1,
        "new_provider_calls": 0,
        "remaining_provider_calls_authorizable": 1,
        "retrieval_rounds": 0,
        "new_evidence": 0,
        "candidate_promotions": 0,
    }


def test_R7_capture_requalification_uses_no_new_call_or_evidence() -> None:
    result = build_patch_capture_requalification_zero_call_result(
        recorded_at="2026-08-23T05:20:00+00:00"
    )
    assert result["status"] == (
        "R7_capture_requalified_under_compiled_reference_envelope_"
        "assessment_pending"
    )
    assert all(result["checks"].values())
    assert result["execution"] == {
        "historical_plan_provider_calls_reused": 1,
        "historical_patch_provider_calls_reused": 1,
        "new_provider_calls": 0,
        "retrieval_rounds": 0,
        "s1_s2_requests": 0,
        "new_evidence": 0,
        "candidate_promotions": 0,
    }
    assert result["repair_receipt"][
        "context_bound_reference_additions"
    ] == {
        "evidence_refs": [],
        "numeric_refs": [
            "NUM::BA153FB9939D66DF",
            "NUM::D0EA6489B2C138EE",
        ],
        "numeric_relation_refs": ["REL::E3A67501DFA73ACF"],
    }
    assert result["acceptance"]["L1_L2_reassessment_pending"] is True


def test_R7_independent_assessment_is_bound_and_does_not_over_accept() -> None:
    result = _json(REQUALIFIED_R7_RESULT)
    assessment = _json(R7_CONTENT_ASSESSMENT)

    assert assessment["source_requalification_sha256"] == hashlib.sha256(
        REQUALIFIED_R7_RESULT.read_bytes()
    ).hexdigest()
    assert assessment["source_requalification_result_digest"] == result[
        "result_digest"
    ]
    assert assessment["source_workpaper_digest"] == canonical_digest(
        result["workpaper"]
    )
    assert assessment["source_repair_receipt_digest"] == canonical_digest(
        result["repair_receipt"]
    )
    assert assessment["l1_financial_truth"]["status"].startswith("pass_")
    assert assessment["l2_evidence_authority"]["status"].startswith("pass_")
    assert assessment["content_quality"]["diagnostic_applicable_score"] == 21
    assert assessment["content_quality"]["formal_eight_dimension_score"] is None
    assert assessment["acceptance"]["dynamic_single_unit_accepted"] is True
    assert assessment["acceptance"]["dynamic_multi_agent_entry_eligible"] is True
    assert assessment["acceptance"]["dynamic_multi_agent_live_authority_signed"] is False
    assert assessment["acceptance"]["S3_acceptance"] is False
    assert assessment["acceptance"]["qualified_human_acceptance"] is False
    assert assessment["execution_observation"][
        "new_provider_calls_for_requalification_or_assessment"
    ] == 0


def test_semantic_repair_envelope_still_rejects_unrelated_context_ref() -> None:
    context = _context()
    reused = compile_reused_semantic_repair_plan(
        failed_full_result=_json(FAILED_R6_RESULT),
        context=context,
    )
    result = build_patch_capture_requalification_zero_call_result(
        recorded_at="2026-08-23T05:20:00+00:00"
    )
    patch = {
        key: deepcopy(result["workpaper"][key])
        for key in ("thesis", "sourced_claims", "mechanism")
    }
    payload = {
        "schema_version": "fin_ia_dynamic_single_unit_semantic_repair_patch_v1_0",
        "agent_id": "AGENT::VALUE_CAPTURE",
        "plan_delta_digest": reused["plan_delta"]["plan_delta_digest"],
        "resolved_feedback_ids": [
            row["feedback_id"] for row in context["feedback_receipts"]
        ],
        "semantic_commitments": [
            row["semantic_commitment"] for row in context["resolution_policy"]
        ],
        **patch,
    }
    envelope = compile_semantic_repair_reference_envelope(
        context, reused["plan_delta"]
    )
    unrelated = sorted(
        set(
            context["full_workpaper_context"]["cell_analysis_view"]["cell"]
            ["allowed_numeric_refs"]
        )
        - set(envelope["allowed_refs"]["numeric_refs"])
    )[0]
    payload["sourced_claims"][0]["numeric_refs"].append(unrelated)
    with pytest.raises(
        DynamicSingleUnitRepairError,
        match="dynamic_semantic_repair_patch_new_reference_forbidden",
    ):
        validate_and_merge_semantic_repair_patch(
            payload,
            context=context,
            plan_delta=reused["plan_delta"],
        )


def test_semantic_patch_successor_authority_rejects_budget_drift_first(
    tmp_path: Path,
) -> None:
    authority = {
        "schema_version": PATCH_SUCCESSOR_AUTHORITY_SCHEMA,
        "status": PATCH_SUCCESSOR_AUTHORITY_STATUS,
        "signed_at": "2026-08-23T04:50:00Z",
        "implementation_commit": "0" * 40,
        "case_key": "DELL",
        "cell_id": "CELL::value_capture",
        "execution_budget": {"maximum_model_calls": 2},
        "bound_inputs": {},
        "output_contract": {},
        "known_boundary": "x" * 100,
    }
    path = tmp_path / "authority.json"
    path.write_text(json.dumps(authority), encoding="utf-8")
    with pytest.raises(
        SemanticRepairRunnerError,
        match="semantic_patch_successor_budget_invalid",
    ):
        validate_patch_successor_authority(authority, authority_path=path)

    assert run_patch_successor.__kwdefaults__["patch_executor"] is not None
