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
    ChatCompletionToolStepResult,
    load_chat_completion_profile,
)
from sec_agent.research.multi_agent_preview import (  # noqa: E402
    LEAD_PLAN_SCHEMA_VERSION,
    RESEARCH_LEAD_AGENT_ID,
    SPECIALIST_AGENT_IDS,
    compile_analysis_completion_checkpoint,
    compile_analysis_fragment_checkpoint,
    compile_token_budget_basis,
    lead_plan_tool,
    load_multi_agent_role_topology,
    merge_analysis_draft_fragments,
    validate_analysis_completion_checkpoint,
    validate_analysis_continuation_completion,
    validate_analysis_fragment_checkpoint,
    validate_lead_plan,
    validate_specialist_plan_checkpoint,
)
from sec_agent.research.multi_agent_preview_runtime import (  # noqa: E402
    execute_checkpointed_preview_submission,
    start_preview_agent_session,
)


EVAL_ROOT = ROOT / "configs/research/evals"
TOPOLOGY = ROOT / "configs/research/fin_ia_0_1_3_multi_agent_role_topology_v1_0.json"
PLAN_CHECKPOINT = EVAL_ROOT / (
    "fin_ia_0_1_3_s3_dell_multi_agent_preview_"
    "R3_specialist_plan_checkpoint_v1_0.json"
)
FRAGMENT_CHECKPOINT = EVAL_ROOT / (
    "fin_ia_0_1_3_s3_dell_multi_agent_preview_"
    "R4_lead_analysis_checkpoint_v1_0.json"
)
R5_AUTHORITY = EVAL_ROOT / (
    "fin_ia_0_1_3_s3_dell_multi_agent_preview_live_authority_v1_4.json"
)
R5_RESULT = EVAL_ROOT / (
    "fin_ia_0_1_3_s3_dell_multi_agent_preview_live_result_v1_4.json"
)
R5_CAPTURE_ROOT = ROOT / (
    "data/captures/fin_0_1_3_s3_dell_multi_agent_preview_r5_20260820/"
    "FIN_0_1_3_S3_DELL_MULTI_AGENT_PREVIEW_R5_20260820/"
    "FIN_0_1_3_S3_DELL_MULTI_AGENT_PREVIEW_R5_20260820-AGENT-"
    "RESEARCH_LEAD-LEAD_PLAN-ANALYSIS-CONTINUATION-ATTEMPT-01"
)
R5_REQUEST = R5_CAPTURE_ROOT / "model_visible_request.json"
R5_RESPONSE = R5_CAPTURE_ROOT / "provider_response.json"
SUBMISSION_PROFILE = ROOT / (
    "configs/providers/fin_ia_0_1_3_deepseek_v4_pro_ga_"
    "contract_submission_non_thinking_profile_v1_0.json"
)
COMPLETION_CHECKPOINT = EVAL_ROOT / (
    "fin_ia_0_1_3_s3_dell_multi_agent_preview_"
    "R5_lead_analysis_completion_checkpoint_v1_0.json"
)
RESULT = EVAL_ROOT / (
    "fin_ia_0_1_3_s3_dell_multi_agent_preview_"
    "R6_submission_successor_zero_call_result_v1_0.json"
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


def _response_content(response: Mapping[str, Any]) -> str:
    try:
        return str(
            response["response_body"]["choices"][0]["message"]["content"]
        ).strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("visible_analysis_content_missing") from exc


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
                "供给与利润关系是否保留发行人归属和因果边界？",
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


def _is_rejected(action: Any) -> bool:
    try:
        action()
    except (TypeError, ValueError, RuntimeError):
        return True
    return False


def run() -> dict[str, Any]:
    topology = load_multi_agent_role_topology(_json(TOPOLOGY))
    plan_checkpoint = validate_specialist_plan_checkpoint(
        _json(PLAN_CHECKPOINT), topology=topology
    )
    opinions = [
        deepcopy(dict(row)) for row in plan_checkpoint["specialist_plans"]
    ]
    fragment = validate_analysis_fragment_checkpoint(_json(FRAGMENT_CHECKPOINT))
    authority = _json(R5_AUTHORITY)
    public_result = _json(R5_RESULT)
    request = _json(R5_REQUEST)
    response = _json(R5_RESPONSE)
    partial_response = _json(ROOT / fragment["response_capture_ref"])
    partial_draft = _response_content(partial_response)
    continuation_draft = _response_content(response)
    request_messages = request["request_body"]["messages"]
    continuation_messages_digest = canonical_digest(request_messages)

    if not (
        _sha(FRAGMENT_CHECKPOINT)
        == "ae97121a18afaa97f13956076030f8b4262060b96aae7261370f31714785a2bb"
        and _sha(R5_AUTHORITY)
        == "c90ce15b959c279c64fdd780e88a3f45d44cf2a17e3297df3e9b715aa9731f05"
        and _sha(R5_RESULT)
        == "391ad82660e11f04fd20133d78d31c5e4093f3bdfac38ea964a3166909059c24"
        and public_result.get("result_digest")
        == "1e96f65eef04da0b8ffa8c9cd78379d149b4f1c82c1c83d4999ff76153c588e6"
        and public_result.get("failure_code")
        == "multi_agent_analysis_continuation_semantically_incomplete"
        and _sha(R5_REQUEST)
        == "05a0b92f9af3732ae4277e2b35095b666899a95fb4c848eb2feeca5e5026cfc1"
        and request.get("request_digest")
        == "f61f1283f907fa19f9540ccd0dcf5b83f48f77c28d941d62937ae5614a9ba8d1"
        and _sha(R5_RESPONSE)
        == "0d9dd381f0fc986013847b363fcfd249b5dc89568f43b088c3aaa0bc7d4e627c"
        and response.get("response_digest")
        == "b5eb9fbbd1f7415f755820362f183ad85050afa7988edf82a8a43fb957294c3f"
        and response.get("response_body_complete") is True
        and response.get("eligible_for_business_promotion") is False
        and response["response_body"]["choices"][0]["finish_reason"] == "stop"
        and len(partial_draft) == 9_932
        and len(continuation_draft) == 5_003
        and continuation_messages_digest
        == "94e2c9ae7901bce4185c25941e68c198190a0c2da2a99a3b1b41a51d4d27a514"
    ):
        raise RuntimeError("R4_R5_immutable_capture_binding_invalid")

    validated_continuation = validate_analysis_continuation_completion(
        checkpoint=fragment,
        continuation_draft=continuation_draft,
    )
    merged_draft = merge_analysis_draft_fragments(
        checkpoint=fragment,
        partial_draft=partial_draft,
        continuation_draft=validated_continuation,
    )
    analysis_basis = compile_token_budget_basis(
        node_id=(
            "AGENT::RESEARCH_LEAD::LEAD_PLAN::ANALYSIS_CONTINUATION"
        ),
        purpose=(
            "汇总六个独立角色意见，覆盖全部研究面并冻结协调问题和终止条件。 "
            "本阶段只续写 checkpoint 标明的未完成内容，不重做已完成分析、"
            "不提交合同、不晋升业务事实。"
        ),
        input_characters=sum(
            len(str(row.get("content") or "")) for row in request_messages
        ),
        input_reference_count=1,
        required_outputs=(
            "visible_analysis_continuation",
            "coordination_questions",
            "expected_information_boundaries",
            "stop_conditions",
        ),
        schema_burden="analysis-only projection; no tool or JSON submission",
        materiality_quality_risk=(
            "dropping a role or Evidence Slot would create a structurally "
            "incomplete preview"
        ),
        comparable_run_evidence=(
            "DELL dynamic five-cell R7 content assessment",
            "DELL multi-agent zero-call preview v1.2",
            "DELL fragment analysis/submission FAS-R1",
            "DELL multi-agent preview R3 Lead capacity failure",
        ),
        reasoning_profile=(
            "deepseek-v4-pro thinking=low visible analysis_continuation"
        ),
        output_token_ceiling=4000,
        stop_truncation_behavior=(
            "require one non-empty continuation and finish_reason=stop; merge "
            "with the immutable partial draft; no second continuation or restart"
        ),
    )
    if analysis_basis["token_budget_basis_digest"] != (
        "0fdf2e58fe93165636ba8e4a51f313b89f7764dfa9727d812b56f77768b91f75"
    ):
        raise RuntimeError("R5_token_budget_basis_reconstruction_invalid")

    completion_checkpoint = compile_analysis_completion_checkpoint(
        fragment_checkpoint=fragment,
        fragment_checkpoint_ref=_ref(FRAGMENT_CHECKPOINT),
        fragment_checkpoint_sha256=_sha(FRAGMENT_CHECKPOINT),
        partial_draft=partial_draft,
        source_continuation_run_id=(
            "FIN_0_1_3_S3_DELL_MULTI_AGENT_PREVIEW_R5_20260820"
        ),
        source_continuation_authority_ref=_ref(R5_AUTHORITY),
        source_continuation_authority_sha256=_sha(R5_AUTHORITY),
        source_continuation_result_ref=_ref(R5_RESULT),
        source_continuation_result_sha256=_sha(R5_RESULT),
        source_continuation_result_digest=str(public_result["result_digest"]),
        continuation_request_capture_ref=_ref(R5_REQUEST),
        continuation_request_capture_sha256=_sha(R5_REQUEST),
        continuation_request_digest=str(request["request_digest"]),
        continuation_response_capture_ref=_ref(R5_RESPONSE),
        continuation_response_capture_sha256=_sha(R5_RESPONSE),
        continuation_response_digest=str(response["response_digest"]),
        continuation_messages_digest=continuation_messages_digest,
        continuation_draft=continuation_draft,
        finish_reason="stop",
        usage=dict(response["response_body"].get("usage") or {}),
        source_analysis_token_budget_basis=analysis_basis,
        recorded_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    )
    trusted_completion = validate_analysis_completion_checkpoint(
        completion_checkpoint
    )

    submission_profile = load_chat_completion_profile(_json(SUBMISSION_PROFILE))
    lead_payload = _deterministic_lead_plan(
        opinions=opinions, topology=topology
    )
    submission_calls: list[dict[str, Any]] = []

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
            request_digest="a" * 64,
            response_digest="b" * 64,
            private_reasoning_fields_redacted=0,
        )

    session = start_preview_agent_session(
        agent_id=RESEARCH_LEAD_AGENT_ID,
        run_id="ZERO-CALL-R6-SUBMISSION-SUCCESSOR",
        objective_ref="objective://dell/multi-agent-preview",
        active_plan_ref="plan://dell/pending-lead",
    )
    execution = execute_checkpointed_preview_submission(
        submission_profile=submission_profile,
        session_state=session,
        completed_analysis_checkpoint=trusted_completion,
        merged_analysis_draft=merged_draft,
        tool=lead_plan_tool(topology=topology),
        validator=lambda payload: validate_lead_plan(
            payload, opinions=opinions, topology=topology
        ),
        capture_root=ROOT / "data/captures/zero_call_not_written",
        run_id="ZERO-CALL-R6-SUBMISSION-SUCCESSOR",
        node_id="AGENT::RESEARCH_LEAD::LEAD_PLAN",
        purpose=(
            "复用 R4 与 R5 已完成并绑定的 Lead 分析，只执行严格合同交卷。"
        ),
        required_outputs=tuple(fragment["required_outputs"]),
        schema_burden="existing strict Lead plan tool contract",
        materiality_quality_risk=(
            "checkpoint drift or incomplete Lead mapping would corrupt all "
            "downstream workpapers"
        ),
        comparable_run_evidence=(
            "DELL multi-agent preview R4 length failure",
            "DELL multi-agent preview R5 completed continuation capture",
        ),
        submission_output_token_ceiling=2000,
        maximum_submission_successor_attempts=0,
        submission_transport=fake_submission,
    )
    submission_payload = json.loads(
        str(submission_calls[0]["messages"][1]["content"])
    )

    partial_heading_repeated = (
        "OUTPUT::coordination_questions\ncontinued\n"
        + continuation_draft[
            continuation_draft.index("OUTPUT::expected_information_boundaries"):
        ]
    )
    first_missing = continuation_draft[
        continuation_draft.index("OUTPUT::expected_information_boundaries"):
    ]
    missing_heading = continuation_draft.replace(
        "OUTPUT::expected_information_boundaries", "", 1
    )
    wrong_order = continuation_draft.replace(
        "OUTPUT::expected_information_boundaries",
        "OUTPUT::TEMP",
        1,
    ).replace(
        "OUTPUT::stop_conditions",
        "OUTPUT::expected_information_boundaries",
        1,
    ).replace("OUTPUT::TEMP", "OUTPUT::stop_conditions", 1)
    wrong_receipt = continuation_draft.rsplit("COMPLETED_OUTPUTS::", 1)[0] + (
        "COMPLETED_OUTPUTS::stop_conditions|expected_information_boundaries|"
        "coordination_questions"
    )

    mutated_completion = deepcopy(completion_checkpoint)
    mutated_completion["continuation_response_digest"] = "c" * 64

    second_partial_rejected = _is_rejected(
        lambda: compile_analysis_fragment_checkpoint(
            case_key="DELL",
            run_id="MUTATION",
            node_id="AGENT::RESEARCH_LEAD::LEAD_PLAN",
            source_authority_ref="authority.json",
            source_authority_sha256="1" * 64,
            source_public_result_ref="result.json",
            source_public_result_sha256="2" * 64,
            source_public_result_digest="3" * 64,
            request_capture_ref="request.json",
            request_capture_sha256="4" * 64,
            request_digest="5" * 64,
            response_capture_ref="response.json",
            response_capture_sha256="6" * 64,
            response_digest="7" * 64,
            partial_draft="A sufficiently long partial analysis fragment.",
            required_outputs=("a", "b"),
            completed_required_outputs=(),
            partial_required_outputs=("a", "b"),
            missing_required_outputs=(),
            usage={},
            recorded_at="2026-08-20T00:00:00+00:00",
        )
    )
    negative_mutations = {
        "empty_partial_prefix_rejected": _is_rejected(
            lambda: validate_analysis_continuation_completion(
                checkpoint=fragment, continuation_draft=first_missing
            )
        ),
        "partial_heading_repetition_rejected": _is_rejected(
            lambda: validate_analysis_continuation_completion(
                checkpoint=fragment,
                continuation_draft=partial_heading_repeated,
            )
        ),
        "missing_heading_rejected": _is_rejected(
            lambda: validate_analysis_continuation_completion(
                checkpoint=fragment, continuation_draft=missing_heading
            )
        ),
        "wrong_heading_order_rejected": _is_rejected(
            lambda: validate_analysis_continuation_completion(
                checkpoint=fragment, continuation_draft=wrong_order
            )
        ),
        "wrong_receipt_rejected": _is_rejected(
            lambda: validate_analysis_continuation_completion(
                checkpoint=fragment, continuation_draft=wrong_receipt
            )
        ),
        "completion_digest_drift_rejected": _is_rejected(
            lambda: validate_analysis_completion_checkpoint(
                mutated_completion
            )
        ),
        "second_partial_field_rejected": second_partial_rejected,
    }

    body = {
        "schema_version": (
            "fin_ia_s3_dell_multi_agent_preview_"
            "R6_submission_successor_zero_call_result_v1_0"
        ),
        "status": "R5_completed_analysis_submission_successor_zero_call_pass",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "case_key": "DELL",
        "bindings": {
            "fragment_checkpoint_ref": _ref(FRAGMENT_CHECKPOINT),
            "fragment_checkpoint_sha256": _sha(FRAGMENT_CHECKPOINT),
            "fragment_checkpoint_digest": fragment["checkpoint_digest"],
            "R5_authority_ref": _ref(R5_AUTHORITY),
            "R5_authority_sha256": _sha(R5_AUTHORITY),
            "R5_public_result_ref": _ref(R5_RESULT),
            "R5_public_result_sha256": _sha(R5_RESULT),
            "R5_public_result_digest": public_result["result_digest"],
            "R5_request_capture_ref": _ref(R5_REQUEST),
            "R5_request_capture_sha256": _sha(R5_REQUEST),
            "R5_response_capture_ref": _ref(R5_RESPONSE),
            "R5_response_capture_sha256": _sha(R5_RESPONSE),
            "completion_checkpoint_ref": _ref(COMPLETION_CHECKPOINT),
            "completion_checkpoint_digest": completion_checkpoint[
                "checkpoint_digest"
            ],
        },
        "replay_projection": {
            "partial_draft_character_count": len(partial_draft),
            "continuation_draft_character_count": len(continuation_draft),
            "merged_analysis_draft_character_count": len(merged_draft),
            "merged_analysis_draft_digest": canonical_digest(merged_draft),
            "continuation_finish_reason": "stop",
            "continuation_semantically_complete_under_corrected_contract": True,
            "R5_analysis_token_budget_basis_reconstructed": True,
            "R5_analysis_token_budget_basis_digest": analysis_basis[
                "token_budget_basis_digest"
            ],
            "analysis_or_continuation_rerun": False,
        },
        "runtime_projection": {
            "attempt_phases": [row["phase"] for row in execution.attempts],
            "provider_attempt_count": sum(
                1
                for row in execution.attempts
                if row["phase"] == "submission"
            ),
            "analysis_checkpoint_reuse_count": sum(
                1
                for row in execution.attempts
                if row["phase"] == "analysis_checkpoint_reuse"
            ),
            "submission_calls": len(submission_calls),
            "validated_lead_plan": (
                execution.validated_payload["lead_agent_id"]
                == RESEARCH_LEAD_AGENT_ID
            ),
            "merged_draft_reached_submission": (
                submission_payload["analysis_draft"] == merged_draft
            ),
            "analysis_context_digest_preserved": (
                submission_payload["analysis_messages_digest"]
                == continuation_messages_digest
            ),
            "checkpoint_event_present": any(
                row["event_type"] == "checkpoint_created"
                for row in session.events
            ),
            "resume_event_present": any(
                row["event_type"] == "session_resumed"
                for row in session.events
            ),
            "token_budget_surfaces": sorted(execution.token_budget_basis),
        },
        "negative_mutations": negative_mutations,
        "claims": {
            "new_analysis_model_calls": 0,
            "new_submission_model_calls": 0,
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
        == ["analysis_checkpoint_reuse", "submission"]
        and body["runtime_projection"]["provider_attempt_count"] == 1
        and body["runtime_projection"]["analysis_checkpoint_reuse_count"] == 1
        and body["runtime_projection"]["submission_calls"] == 1
        and body["runtime_projection"]["validated_lead_plan"]
        and body["runtime_projection"]["merged_draft_reached_submission"]
        and body["runtime_projection"]["analysis_context_digest_preserved"]
        and all(negative_mutations.values())
    ):
        raise RuntimeError("R6_submission_successor_zero_call_not_passed")
    result = {**body, "result_digest": canonical_digest(body)}
    _write_new(COMPLETION_CHECKPOINT, completion_checkpoint)
    _write_new(RESULT, result)
    return result


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2, sort_keys=True))
