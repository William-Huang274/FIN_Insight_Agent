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
from sec_agent.providers import (  # noqa: E402
    ChatCompletionResult,
    ChatCompletionToolStepResult,
    load_chat_completion_profile,
)
from sec_agent.research.multi_agent_preview import (  # noqa: E402
    LEAD_PLAN_SCHEMA_VERSION,
    RESEARCH_LEAD_AGENT_ID,
    SPECIALIST_AGENT_IDS,
    compile_analysis_continuation_messages,
    compile_analysis_fragment_checkpoint,
    lead_plan_tool,
    load_multi_agent_role_topology,
    validate_analysis_fragment_checkpoint,
    validate_lead_plan,
    validate_specialist_plan_checkpoint,
)
from sec_agent.research.multi_agent_preview_runtime import (  # noqa: E402
    MultiAgentPreviewRuntimeError,
    execute_analyzed_preview_node,
    start_preview_agent_session,
)


TOPOLOGY = ROOT / "configs/research/fin_ia_0_1_3_multi_agent_role_topology_v1_0.json"
PLAN_CHECKPOINT = (
    ROOT
    / "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_multi_agent_preview_"
    "R3_specialist_plan_checkpoint_v1_0.json"
)
R4_AUTHORITY = (
    ROOT
    / "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_multi_agent_preview_live_authority_v1_3.json"
)
R4_RESULT = (
    ROOT
    / "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_multi_agent_preview_live_result_v1_3.json"
)
R4_CAPTURE_ROOT = (
    ROOT
    / "data/captures/fin_0_1_3_s3_dell_multi_agent_preview_r4_20260820/"
    "FIN_0_1_3_S3_DELL_MULTI_AGENT_PREVIEW_R4_20260820/"
    "FIN_0_1_3_S3_DELL_MULTI_AGENT_PREVIEW_R4_20260820-"
    "AGENT-RESEARCH_LEAD-LEAD_PLAN-ANALYSIS-ATTEMPT-01"
)
R4_REQUEST = R4_CAPTURE_ROOT / "model_visible_request.json"
R4_RESPONSE = R4_CAPTURE_ROOT / "provider_response.json"
ANALYSIS_PROFILE = (
    ROOT
    / "configs/providers/fin_ia_0_1_3_deepseek_v4_pro_ga_agent_profile_v1_1.json"
)
CONTINUATION_PROFILE = (
    ROOT
    / "configs/providers/"
    "fin_ia_0_1_3_deepseek_v4_pro_ga_"
    "analysis_continuation_low_profile_v1_0.json"
)
SUBMISSION_PROFILE = (
    ROOT
    / "configs/providers/"
    "fin_ia_0_1_3_deepseek_v4_pro_ga_"
    "contract_submission_non_thinking_profile_v1_0.json"
)
CHECKPOINT = (
    ROOT
    / "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_multi_agent_preview_"
    "R4_lead_analysis_checkpoint_v1_0.json"
)
RESULT = (
    ROOT
    / "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_multi_agent_preview_"
    "R5_analysis_successor_zero_call_result_v1_0.json"
)


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _ref(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _write_new(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(
            json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n"
        )


def _partial_draft(response: Mapping[str, Any]) -> str:
    try:
        return str(
            response["response_body"]["choices"][0]["message"]["content"]
        ).strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("R4_visible_analysis_content_missing") from exc


def _deterministic_lead_plan(
    *, opinions: list[dict[str, Any]], topology: Mapping[str, Any]
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
                "订单、收入、利润与现金是否保持同公司、同期间和同事实状态？",
                "供给与利润关系是否仍保留发行人归属和因果边界？",
            ],
            "expected_information_boundaries": [
                "免费公开资料可能不披露订单取消与 backlog 账龄。",
                "当前权限不包含开放网络补证或生产级时点估值。",
            ],
            "stop_conditions": [
                "六个角色均形成可追溯底稿且所有 L1 冲突已路由。",
                "数据、工具或 Harness 缺陷留在原责任层并阻断报告。",
            ],
        },
        opinions=opinions,
        topology=topology,
    )


def run() -> dict[str, Any]:
    topology = load_multi_agent_role_topology(_json(TOPOLOGY))
    specialist_checkpoint = validate_specialist_plan_checkpoint(
        _json(PLAN_CHECKPOINT), topology=topology
    )
    opinions = [
        deepcopy(dict(row)) for row in specialist_checkpoint["specialist_plans"]
    ]
    authority = _json(R4_AUTHORITY)
    public_result = _json(R4_RESULT)
    request = _json(R4_REQUEST)
    response = _json(R4_RESPONSE)
    partial_draft = _partial_draft(response)
    usage = dict(response["response_body"].get("usage") or {})
    if not (
        authority.get("schema_version")
        == "fin_ia_s3_dell_multi_agent_preview_live_authority_v1_3"
        and public_result.get("failure_code")
        == "multi_agent_preview_analysis_finish_reason_invalid:length"
        and public_result.get("result_digest")
        == "f615698a118e249338fa8293e8d474a27561e29c7725184a300148c9c0d380eb"
        and request.get("request_digest")
        == "4fecfd503bd94795bdb3e81473179691da235b8de5b955b3998fc0617e0ca564"
        and response.get("response_digest")
        == "a1816773ed66bf996018d52fa7e0f8432d8a6d58049995c04ea6c6205b9acf41"
        and response.get("response_body_complete") is True
        and response.get("eligible_for_business_promotion") is False
        and response["response_body"]["choices"][0].get("finish_reason")
        == "length"
        and len(partial_draft) == 9_932
        and usage.get("completion_tokens") == 12_000
        and (usage.get("completion_tokens_details") or {}).get(
            "reasoning_tokens"
        )
        == 9_447
    ):
        raise RuntimeError("R4_visible_analysis_binding_invalid")

    required_outputs = (
        "accepted_agent_ids",
        "accepted_facets",
        "coordination_questions",
        "expected_information_boundaries",
        "stop_conditions",
    )
    checkpoint = compile_analysis_fragment_checkpoint(
        case_key="DELL",
        run_id=str(public_result.get("execution", {}).get("run_id") or authority["outputs"]["run_id"]),
        node_id="AGENT::RESEARCH_LEAD::LEAD_PLAN",
        source_authority_ref=_ref(R4_AUTHORITY),
        source_authority_sha256=_sha(R4_AUTHORITY),
        source_public_result_ref=_ref(R4_RESULT),
        source_public_result_sha256=_sha(R4_RESULT),
        source_public_result_digest=str(public_result["result_digest"]),
        request_capture_ref=_ref(R4_REQUEST),
        request_capture_sha256=_sha(R4_REQUEST),
        request_digest=str(request["request_digest"]),
        response_capture_ref=_ref(R4_RESPONSE),
        response_capture_sha256=_sha(R4_RESPONSE),
        response_digest=str(response["response_digest"]),
        partial_draft=partial_draft,
        required_outputs=required_outputs,
        completed_required_outputs=("accepted_agent_ids", "accepted_facets"),
        partial_required_outputs=("coordination_questions",),
        missing_required_outputs=(
            "expected_information_boundaries",
            "stop_conditions",
        ),
        usage=usage,
        recorded_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    )
    trusted_checkpoint = validate_analysis_fragment_checkpoint(checkpoint)

    analysis_profile = load_chat_completion_profile(_json(ANALYSIS_PROFILE))
    continuation_profile = load_chat_completion_profile(
        _json(CONTINUATION_PROFILE)
    )
    submission_profile = load_chat_completion_profile(_json(SUBMISSION_PROFILE))
    continuation_defaults = dict(continuation_profile.request_defaults)
    if continuation_defaults != {
        "max_tokens": 4000,
        "stream": False,
        "thinking": {"type": "enabled"},
        "reasoning_effort": "low",
    }:
        raise RuntimeError("analysis_continuation_profile_invalid")

    continuation = (
        "OUTPUT::coordination_questions\n"
        "Finish the preserved eleventh question without adding new authority.\n"
        "OUTPUT::expected_information_boundaries\n"
        "Preserve the public-information, source-route and PIT boundaries already "
        "stated in the draft.\n"
        "OUTPUT::stop_conditions\n"
        "Stop only after every activated role has a traceable workpaper and every "
        "material conflict is repaired or routed to its earliest owner.\n"
        "COMPLETED_OUTPUTS::coordination_questions|"
        "expected_information_boundaries|stop_conditions"
    )
    lead_payload = _deterministic_lead_plan(opinions=opinions, topology=topology)
    continuation_calls: list[dict[str, Any]] = []
    submission_calls: list[dict[str, Any]] = []

    def fake_continuation(**kwargs: Any) -> ChatCompletionResult:
        continuation_calls.append(deepcopy(dict(kwargs)))
        return ChatCompletionResult(
            status="completed_exact_once",
            provider_id="fake",
            model="zero-call",
            content=continuation,
            finish_reason="stop",
            usage={"prompt_tokens": 0, "completion_tokens": 0},
            request_capture_ref="zero-call://continuation-request",
            response_capture_ref="zero-call://continuation-response",
            request_digest="2" * 64,
            response_digest="3" * 64,
            private_reasoning_fields_redacted=0,
        )

    def fake_submission(**kwargs: Any) -> ChatCompletionToolStepResult:
        submission_calls.append(deepcopy(dict(kwargs)))
        return ChatCompletionToolStepResult(
            status="completed_exact_once",
            provider_id="fake",
            model="zero-call",
            content="",
            reasoning_content="",
            tool_calls=(
                {
                    "id": "call_zero",
                    "type": "function",
                    "function": {
                        "name": "submit_lead_plan",
                        "arguments": json.dumps(
                            {
                                key: value
                                for key, value in lead_payload.items()
                                if key != "lead_plan_digest"
                            },
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                    },
                },
            ),
            finish_reason="tool_calls",
            usage={"prompt_tokens": 0, "completion_tokens": 0},
            request_capture_ref="zero-call://submission-request",
            response_capture_ref="zero-call://submission-response",
            request_digest="4" * 64,
            response_digest="5" * 64,
            private_reasoning_fields_redacted=0,
        )

    session = start_preview_agent_session(
        agent_id=RESEARCH_LEAD_AGENT_ID,
        run_id="ZERO-CALL-R5-ANALYSIS-SUCCESSOR",
        objective_ref="objective://dell/multi-agent-preview",
        active_plan_ref="plan://dell/pending-lead",
    )
    sentinel = "ORIGINAL_R4_FULL_CONTEXT_MUST_NOT_BE_RESENT"
    execution = execute_analyzed_preview_node(
        analysis_profile=analysis_profile,
        submission_profile=submission_profile,
        analysis_continuation_profile=continuation_profile,
        session_state=session,
        messages=(
            {"role": "system", "content": sentinel},
            {"role": "user", "content": sentinel},
        ),
        tool=lead_plan_tool(topology=topology),
        validator=lambda payload: validate_lead_plan(
            payload, opinions=opinions, topology=topology
        ),
        capture_root=ROOT / "data/captures/zero_call_not_written",
        run_id="ZERO-CALL-R5-ANALYSIS-SUCCESSOR",
        node_id="AGENT::RESEARCH_LEAD::LEAD_PLAN",
        purpose="只续写 R4 被截断的 Lead 分析并映射既有 Lead 合同。",
        input_reference_count=0,
        required_outputs=required_outputs,
        schema_burden="existing strict Lead plan tool contract",
        materiality_quality_risk=(
            "incomplete Lead coordination would corrupt all downstream workpapers"
        ),
        comparable_run_evidence=("DELL multi-agent preview R4 length failure",),
        analysis_output_token_ceiling=4000,
        submission_output_token_ceiling=2000,
        maximum_submission_successor_attempts=0,
        analysis_checkpoint=trusted_checkpoint,
        analysis_checkpoint_draft=partial_draft,
        analysis_transport=fake_continuation,
        submission_transport=fake_submission,
    )
    continuation_prompt = json.dumps(
        continuation_calls[0]["messages"], ensure_ascii=False, sort_keys=True
    )
    submission_prompt = json.dumps(
        submission_calls[0]["messages"], ensure_ascii=False, sort_keys=True
    )
    submission_payload = json.loads(
        str(submission_calls[0]["messages"][1]["content"])
    )
    submitted_analysis_draft = str(submission_payload["analysis_draft"])

    digest_mutation_rejected = False
    mutated = deepcopy(checkpoint)
    mutated["checkpoint_digest"] = "0" * 64
    try:
        validate_analysis_fragment_checkpoint(mutated)
    except (ValueError, RuntimeError):
        digest_mutation_rejected = True

    semantic_incompletion_rejected = False
    semantic_calls = 0

    def incomplete_continuation(**_kwargs: Any) -> ChatCompletionResult:
        nonlocal semantic_calls
        semantic_calls += 1
        return ChatCompletionResult(
            status="completed_exact_once",
            provider_id="fake",
            model="zero-call",
            content="OUTPUT::coordination_questions\nOnly one field.",
            finish_reason="stop",
            usage={},
            request_capture_ref="zero-call://incomplete-request",
            response_capture_ref="zero-call://incomplete-response",
            request_digest="6" * 64,
            response_digest="7" * 64,
            private_reasoning_fields_redacted=0,
        )

    try:
        execute_analyzed_preview_node(
            analysis_profile=analysis_profile,
            submission_profile=submission_profile,
            analysis_continuation_profile=continuation_profile,
            session_state=start_preview_agent_session(
                agent_id=RESEARCH_LEAD_AGENT_ID,
                run_id="ZERO-CALL-R5-INCOMPLETE",
                objective_ref="objective://dell/multi-agent-preview",
                active_plan_ref="plan://dell/pending-lead",
            ),
            messages=({"role": "user", "content": sentinel},),
            tool=lead_plan_tool(topology=topology),
            validator=lambda payload: payload,
            capture_root=ROOT / "data/captures/zero_call_not_written",
            run_id="ZERO-CALL-R5-INCOMPLETE",
            node_id="AGENT::RESEARCH_LEAD::LEAD_PLAN",
            purpose="拒绝语义未完成的续写。",
            input_reference_count=0,
            required_outputs=required_outputs,
            schema_burden="existing strict Lead plan tool contract",
            materiality_quality_risk="partial plan must not submit",
            comparable_run_evidence=("R4 length failure",),
            analysis_output_token_ceiling=4000,
            submission_output_token_ceiling=2000,
            maximum_submission_successor_attempts=0,
            analysis_checkpoint=trusted_checkpoint,
            analysis_checkpoint_draft=partial_draft,
            analysis_transport=incomplete_continuation,
            submission_transport=fake_submission,
        )
    except MultiAgentPreviewRuntimeError as exc:
        semantic_incompletion_rejected = (
            exc.code
            == "multi_agent_analysis_continuation_semantically_incomplete"
        )

    compiled_messages = compile_analysis_continuation_messages(
        checkpoint=trusted_checkpoint,
        partial_draft=partial_draft,
        tool_name="submit_lead_plan",
    )
    body = {
        "schema_version": (
            "fin_ia_s3_dell_multi_agent_preview_"
            "R5_analysis_successor_zero_call_result_v1_0"
        ),
        "status": "R4_visible_analysis_checkpoint_successor_zero_call_pass",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "case_key": "DELL",
        "bindings": {
            "topology_ref": _ref(TOPOLOGY),
            "topology_sha256": _sha(TOPOLOGY),
            "specialist_plan_checkpoint_ref": _ref(PLAN_CHECKPOINT),
            "specialist_plan_checkpoint_sha256": _sha(PLAN_CHECKPOINT),
            "R4_authority_ref": _ref(R4_AUTHORITY),
            "R4_authority_sha256": _sha(R4_AUTHORITY),
            "R4_public_result_ref": _ref(R4_RESULT),
            "R4_public_result_sha256": _sha(R4_RESULT),
            "analysis_checkpoint_ref": _ref(CHECKPOINT),
            "analysis_checkpoint_digest": checkpoint["checkpoint_digest"],
            "continuation_profile_ref": _ref(CONTINUATION_PROFILE),
            "continuation_profile_sha256": _sha(CONTINUATION_PROFILE),
        },
        "checkpoint_projection": {
            "partial_draft_character_count": len(partial_draft),
            "partial_draft_content_persisted_in_public_artifact": False,
            "completed_required_outputs": checkpoint[
                "completed_required_outputs"
            ],
            "partial_required_outputs": checkpoint["partial_required_outputs"],
            "missing_required_outputs": checkpoint["missing_required_outputs"],
            "maximum_continuation_calls": 1,
        },
        "runtime_projection": {
            "continuation_calls": len(continuation_calls),
            "submission_calls": len(submission_calls),
            "attempt_phases": [row["phase"] for row in execution.attempts],
            "validated_lead_plan": execution.validated_payload[
                "lead_agent_id"
            ]
            == RESEARCH_LEAD_AGENT_ID,
            "checkpoint_event_present": any(
                row["event_type"] == "checkpoint_created"
                for row in session.events
            ),
            "feedback_event_present": any(
                row["event_type"] == "feedback_issued"
                for row in session.events
            ),
            "resume_event_present": any(
                row["event_type"] == "session_resumed" for row in session.events
            ),
            "feedback_receipt_count": len(session.feedback_receipts),
            "continuation_prompt_character_count": len(continuation_prompt),
            "submission_prompt_character_count": len(submission_prompt),
            "original_full_context_resent": sentinel in continuation_prompt,
            "merged_draft_reached_submission": (
                submitted_analysis_draft.startswith(partial_draft)
                and submitted_analysis_draft.endswith(continuation)
            ),
            "analysis_token_budget_basis": execution.token_budget_basis[
                "analysis"
            ],
            "submission_token_budget_basis": execution.token_budget_basis[
                "submission"
            ],
        },
        "negative_mutations": {
            "checkpoint_digest_mutation_rejected": digest_mutation_rejected,
            "semantic_incompletion_rejected_before_submission": (
                semantic_incompletion_rejected
            ),
            "semantic_incompletion_continuation_call_count": semantic_calls,
            "public_checkpoint_excludes_partial_draft": (
                partial_draft not in json.dumps(checkpoint, ensure_ascii=False)
            ),
            "continuation_messages_require_all_remaining_outputs": all(
                f"OUTPUT::{field}"
                in json.dumps(compiled_messages, ensure_ascii=False)
                for field in (
                    "coordination_questions",
                    "expected_information_boundaries",
                    "stop_conditions",
                )
            ),
        },
        "claims": {
            "model_calls": 0,
            "network_calls": 0,
            "paid_tool_calls": 0,
            "candidate_promotions": 0,
            "specialist_plan_reruns": 0,
            "S1_pass": False,
            "S3_pass": False,
            "true_multi_agent_live_completed": False,
        },
    }
    if not (
        body["runtime_projection"]["attempt_phases"]
        == ["analysis_continuation", "submission"]
        and body["runtime_projection"]["validated_lead_plan"]
        and body["runtime_projection"]["original_full_context_resent"] is False
        and body["runtime_projection"]["merged_draft_reached_submission"]
        and all(
            value is True
            for key, value in body["negative_mutations"].items()
            if key != "semantic_incompletion_continuation_call_count"
        )
        and body["negative_mutations"][
            "semantic_incompletion_continuation_call_count"
        ]
        == 1
    ):
        raise RuntimeError(
            "R5_analysis_successor_zero_call_not_passed:"
            + json.dumps(
                {
                    "attempt_phases": body["runtime_projection"][
                        "attempt_phases"
                    ],
                    "validated_lead_plan": body["runtime_projection"][
                        "validated_lead_plan"
                    ],
                    "original_full_context_resent": body[
                        "runtime_projection"
                    ]["original_full_context_resent"],
                    "merged_draft_reached_submission": body[
                        "runtime_projection"
                    ]["merged_draft_reached_submission"],
                    "negative_mutations": body["negative_mutations"],
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    result = {**body, "result_digest": canonical_digest(body)}
    _write_new(CHECKPOINT, checkpoint)
    _write_new(RESULT, result)
    return result


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2, sort_keys=True))
